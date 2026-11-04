import json
from pathlib import Path
import sys
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ai.retrieval.hybrid_search import run_hybrid_search
from app.core.security import sanitize_file_path_for_display
from app.database.session import SessionLocal
from app.processing.clip_export import (
    _validate_clip_timestamps,
    export_subclip,
    measure_clip_duration,
)
from app.models.entities import (
    Collection,
    CollectionVideo,
    Transcript,
    TranscriptSegment,
    Video,
    VideoScene,
    VideoSummary,
)
from app.services.summary_service import find_video_clips as core_find_video_clips


def list_videos(
    collection_id: str | None = None,
    status: str | None = None,
    db: Session | None = None,
) -> list[dict[str, Any]]:
    """List indexed videos with optional collection and status filters."""
    session = db or SessionLocal()
    try:
        query = session.query(Video)
        if collection_id:
            query = query.join(CollectionVideo, CollectionVideo.video_id == Video.id).filter(
                CollectionVideo.collection_id == collection_id
            )
        if status:
            query = query.filter(Video.processing_status == status)

        videos = query.order_by(Video.created_at.desc()).all()
        return [
            {
                "id": v.id,
                "filename": v.filename,
                "duration": round(v.duration, 2),
                "width": v.width,
                "height": v.height,
                "fps": round(v.fps, 2),
                "codec": v.codec,
                "format": v.format,
                "processing_status": v.processing_status,
                "created_at": v.created_at.isoformat() if v.created_at else "",
            }
            for v in videos
        ]
    finally:
        if db is None:
            session.close()


def get_video_metadata(video_id: str, db: Session | None = None) -> dict[str, Any]:
    """Retrieve complete metadata and technical specifications for a single video.

    Filesystem paths are sanitized to prevent absolute host system path disclosure.
    """
    session = db or SessionLocal()
    try:
        video = session.query(Video).filter_by(id=video_id).first()
        if not video:
            raise ValueError(f"Video '{video_id}' not found in library")

        collections = [
            {"id": c.collection.id, "name": c.collection.name}
            for c in video.collections
            if c.collection
        ]

        safe_path = sanitize_file_path_for_display(video.file_path)
        if safe_path.startswith("/") or (len(safe_path) > 2 and safe_path[1] == ":") or "\\" in safe_path:
            safe_path = safe_path.replace("\\", "/").split("/")[-1]

        safe_thumbnail = str(video.thumbnail_path).replace("\\", "/").split("/")[-1] if video.thumbnail_path else None

        return {
            "id": video.id,
            "filename": video.filename,
            "file_path": safe_path,
            "file_hash": video.file_hash,
            "file_size": video.file_size,
            "duration": round(video.duration, 2),
            "width": video.width,
            "height": video.height,
            "fps": round(video.fps, 2),
            "codec": video.codec,
            "format": video.format,
            "thumbnail_path": safe_thumbnail,
            "processing_status": video.processing_status,
            "collections": collections,
            "created_at": video.created_at.isoformat() if video.created_at else "",
        }
    finally:
        if db is None:
            session.close()


def search_video_content(
    query: str,
    top_k: int = 5,
    use_reranker: bool = True,
    db: Session | None = None,
) -> list[dict[str, Any]]:
    """Perform hybrid semantic search (Stage-1 Dense+BM25 RRF + Stage-2 Cross-Encoder)."""
    session = db or SessionLocal()
    try:
        resp = run_hybrid_search(
            db=session,
            query=query,
            top_k=top_k,
            use_reranker=use_reranker,
        )
        return [
            {
                "video_id": r.video_id,
                "filename": r.filename,
                "chunk_text": r.chunk_text,
                "start_time": r.start_time,
                "end_time": r.end_time,
                "stage1_score": round(r.stage1_score, 4),
                "rerank_score": round(r.rerank_score, 4),
                "rank": r.rank,
                "match_channel": getattr(r, "match_channel", "speech"),
            }
            for r in resp.results
        ]
    finally:
        if db is None:
            session.close()


def search_transcripts(
    query: str,
    video_id: str | None = None,
    db: Session | None = None,
) -> list[dict[str, Any]]:
    """Search lexical spoken words across all video transcripts."""
    session = db or SessionLocal()
    try:
        q = (
            session.query(TranscriptSegment, Video.filename)
            .join(Video, Video.id == TranscriptSegment.video_id)
            .filter(TranscriptSegment.text.ilike(f"%{query.strip()}%"))
        )
        if video_id:
            q = q.filter(TranscriptSegment.video_id == video_id)

        rows = q.order_by(TranscriptSegment.start_time.asc()).limit(20).all()
        return [
            {
                "segment_id": seg.id,
                "video_id": seg.video_id,
                "filename": filename,
                "start_time": round(seg.start_time, 2),
                "end_time": round(seg.end_time, 2),
                "text": seg.text,
                "confidence": round(seg.confidence, 3),
            }
            for seg, filename in rows
        ]
    finally:
        if db is None:
            session.close()


def find_video_clips(
    query: str,
    min_duration: float = 5.0,
    max_duration: float = 60.0,
    db: Session | None = None,
) -> list[dict[str, Any]]:
    """Find timestamped video clips matching a query within duration constraints."""
    session = db or SessionLocal()
    try:
        clips = core_find_video_clips(
            db=session,
            query=query,
            min_duration=min_duration,
            max_duration=max_duration,
            top_k=5,
        )
        return clips
    finally:
        if db is None:
            session.close()


def summarize_video(video_id: str, db: Session | None = None) -> dict[str, Any]:
    """Retrieve an existing grounded factual summary for a video. Strictly read-only.

    If no pre-computed summary exists, synthesizes a non-persistent summary from existing
    transcripts without adding or committing any records to the database.
    """
    session = db or SessionLocal()
    try:
        summary_record = session.query(VideoSummary).filter_by(video_id=video_id).first()
        if summary_record:
            return {
                "video_id": summary_record.video_id,
                "summary": summary_record.summary_text,
                "topics": json.loads(summary_record.topics_json),
                "chapters": json.loads(summary_record.chapters_json),
                "model_name": summary_record.model_name,
            }

        video = session.query(Video).filter_by(id=video_id).first()
        if not video:
            raise ValueError(f"Video '{video_id}' not found in library")

        transcript = session.query(Transcript).filter_by(video_id=video_id).first()
        if not transcript or not transcript.segments:
            raise ValueError(
                f"No summary or transcript found for video '{video_id}'. "
                "Transcribe the video first to enable summary extraction."
            )

        sorted_segs = sorted(transcript.segments, key=lambda s: s.start_time)
        texts = [s.text.strip() for s in sorted_segs if s.text.strip()]
        full_text = " ".join(texts)
        summary_text = (full_text[:300] + "...") if len(full_text) > 300 else full_text
        return {
            "video_id": video_id,
            "summary": summary_text,
            "topics": ["Overview", "Transcript"],
            "chapters": [{"start_time": s.start_time, "title": s.text[:40]} for s in sorted_segs[:3]],
            "model_name": "extractive-non-persistent-mcp",
        }
    finally:
        if db is None:
            session.close()


def get_video_chapters(video_id: str, db: Session | None = None) -> list[dict[str, Any]]:
    """Retrieve timestamped chapter breakdown for a video. Strictly read-only.

    If no pre-computed chapters exist, synthesizes chapter markers from transcripts
    without mutating the database.
    """
    session = db or SessionLocal()
    try:
        summary_record = session.query(VideoSummary).filter_by(video_id=video_id).first()
        if summary_record:
            chapters: list[dict[str, Any]] = json.loads(summary_record.chapters_json)
            return chapters

        video = session.query(Video).filter_by(id=video_id).first()
        if not video:
            raise ValueError(f"Video '{video_id}' not found in library")

        transcript = session.query(Transcript).filter_by(video_id=video_id).first()
        if not transcript or not transcript.segments:
            raise ValueError(
                f"No chapters or transcript found for video '{video_id}'. "
                "Transcribe the video first to enable chapter extraction."
            )

        sorted_segs = sorted(transcript.segments, key=lambda s: s.start_time)
        return [
            {"start_time": s.start_time, "end_time": s.end_time, "title": s.text[:40]}
            for s in sorted_segs[:5]
        ]
    finally:
        if db is None:
            session.close()


def get_media_library_stats(db: Session | None = None) -> dict[str, Any]:
    """Return high-level telemetry and inventory metrics for the entire media library."""
    session = db or SessionLocal()
    try:
        total_videos = session.query(func.count(Video.id)).scalar() or 0
        total_duration = session.query(func.sum(Video.duration)).scalar() or 0.0
        total_collections = session.query(func.count(Collection.id)).scalar() or 0
        total_transcripts = session.query(func.count(Transcript.id)).scalar() or 0
        total_scenes = session.query(func.count(VideoScene.id)).scalar() or 0

        return {
            "total_videos": total_videos,
            "total_duration_sec": round(float(total_duration), 2),
            "total_collections": total_collections,
            "total_transcripts_indexed": total_transcripts,
            "total_scene_cuts": total_scenes,
            "engine": "Arova Creator Intelligence v0.1.0 (Local-First)",
        }
    finally:
        if db is None:
            session.close()


def export_video_clip(
    video_id: str,
    start_time: float,
    end_time: float,
    db: Session | None = None,
) -> dict[str, Any]:
    """Export a lossless trimmed subclip from an indexed video given start and end timestamps."""
    session = db or SessionLocal()
    try:
        video = session.query(Video).filter_by(id=video_id).first()
        if not video:
            raise ValueError(f"Video '{video_id}' not found in library")

        start_time, end_time = _validate_clip_timestamps(
            start_time=start_time,
            end_time=end_time,
            max_duration=video.duration,
        )

        clip_path = export_subclip(
            video_path=video.file_path,
            start_time=start_time,
            end_time=end_time,
            video_id=video.id,
            max_duration=video.duration,
        )
        actual_duration = measure_clip_duration(clip_path)
        return {
            "video_id": video.id,
            "clip_filename": clip_path.name,
            "clip_path": sanitize_file_path_for_display(clip_path),
            "start_time": start_time,
            "end_time": end_time,
            "duration": actual_duration,
            "file_size": clip_path.stat().st_size,
        }
    finally:
        if db is None:
            session.close()


def get_media_availability(
    video_id: str | None = None,
    version_id: str | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    """Retrieve physical media availability, can_play, and can_export status."""
    session = db or SessionLocal()
    try:
        from app.services.portable_service import resolve_media_availability
        target_version_id = version_id
        if not target_version_id and video_id:
            vid = session.get(Video, video_id)
            if vid:
                if not vid.version_id:
                    from app.database.migrator import run_idempotent_backfill
                    run_idempotent_backfill(session)
                    session.refresh(vid)
                target_version_id = vid.version_id
        if not target_version_id:
            raise ValueError("Either video_id or version_id must be provided")

        avail = resolve_media_availability(db=session, version_id=target_version_id)
        return {
            "version_id": avail.version_id,
            "video_id": avail.video_id,
            "availability": avail.availability,
            "can_play": avail.can_play,
            "can_export": avail.can_export,
            "file_path": sanitize_file_path_for_display(avail.file_path) if avail.file_path else None,
        }
    finally:
        if db is None:
            session.close()


def find_duplicate_media(db: Session | None = None) -> list[dict[str, Any]]:
    """Find media versions mapped across multiple physical file locations."""
    session = db or SessionLocal()
    try:
        from app.models.entities import AssetLocation, AssetVersion
        versions = session.query(AssetVersion).all()
        duplicates = []
        for v in versions:
            locs = session.query(AssetLocation).filter_by(version_id=v.id).all()
            if len(locs) > 1:
                duplicates.append({
                    "version_id": v.id,
                    "sha256": v.sha256,
                    "locations_count": len(locs),
                    "locations": [
                        {
                            "rel_path": loc.rel_path,
                            "availability": loc.availability,
                        }
                        for loc in locs
                    ],
                })
        return duplicates
    finally:
        if db is None:
            session.close()


def get_evidence_citations(
    query: str,
    video_id: str | None = None,
    top_k: int = 5,
    db: Session | None = None,
) -> list[dict[str, Any]]:
    """Retrieve timestamped factual citations and evidence excerpts even when original video media is offline."""
    session = db or SessionLocal()
    try:
        results = run_hybrid_search(
            db=session,
            query=query,
            video_id_filter=video_id,
            top_k=top_k,
            use_reranker=True,
        )
        citations = []
        for r in results.results:
            vid = session.get(Video, r.video_id)
            citations.append({
                "video_id": r.video_id,
                "version_id": vid.version_id if vid else None,
                "start_time": r.start_time,
                "end_time": r.end_time,
                "citation_text": r.chunk_text,
                "relevance_score": round(r.rerank_score or r.score, 3),
            })
        return citations
    finally:
        if db is None:
            session.close()


def get_capability_status(db: Session | None = None) -> dict[str, Any]:
    """Inspect system execution profile, AI capability state, and offline status."""
    return {
        "execution_profile": "fully_offline_no_ai",
        "capabilities": {
            "transcription": {"status": "available", "provider": "faster-whisper"},
            "hybrid_search": {"status": "available", "provider": "chromadb+fts5"},
            "portable_memory": {"status": "available", "format_version": "1.0.0"},
            "cloud_ai": {"status": "disabled_by_user", "reason": "privacy_policy_blocked"},
        },
    }
