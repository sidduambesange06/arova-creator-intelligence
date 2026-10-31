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
from app.database.session import SessionLocal
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
from app.services.summary_service import generate_video_summary


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
    """Retrieve complete metadata and technical specifications for a single video."""
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

        return {
            "id": video.id,
            "filename": video.filename,
            "file_path": video.file_path,
            "file_hash": video.file_hash,
            "file_size": video.file_size,
            "duration": round(video.duration, 2),
            "width": video.width,
            "height": video.height,
            "fps": round(video.fps, 2),
            "codec": video.codec,
            "format": video.format,
            "thumbnail_path": video.thumbnail_path,
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
    """Generate or retrieve a grounded factual summary for a video."""
    session = db or SessionLocal()
    try:
        summary_record = generate_video_summary(db=session, video_id=video_id)
        return {
            "video_id": summary_record.video_id,
            "summary": summary_record.summary_text,
            "topics": json.loads(summary_record.topics_json),
            "chapters": json.loads(summary_record.chapters_json),
            "model_name": summary_record.model_name,
        }
    finally:
        if db is None:
            session.close()


def get_video_chapters(video_id: str, db: Session | None = None) -> list[dict[str, Any]]:
    """Extract timestamped chapter breakdown for a video."""
    session = db or SessionLocal()
    try:
        summary_record = generate_video_summary(db=session, video_id=video_id)
        chapters: list[dict[str, Any]] = json.loads(summary_record.chapters_json)
        return chapters
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

