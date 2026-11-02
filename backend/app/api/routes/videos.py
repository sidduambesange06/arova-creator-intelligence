from collections.abc import Iterator
import mimetypes
from pathlib import Path
import re
import unicodedata

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.models.entities import Transcript, Video, VideoScene
from app.processing.clip_export import (
    _validate_clip_timestamps,
    export_subclip,
    measure_clip_duration,
)
from app.schemas.media import (
    ClipExportRequest,
    ClipExportResponse,
    SubtitleIngestRequest,
    VideoImportRequest,
    VideoImportResponse,
    VideoOut,
)
from app.schemas.pipeline import TranscriptOut, TranscriptSegmentOut, VideoSceneOut
from app.services import media_service
from app.services.subtitle_service import ingest_subtitles_for_video
from app.workers.pipeline_runner import run_video_pipeline

router = APIRouter(prefix="/api/v1/videos", tags=["videos"])


@router.post("/import", response_model=VideoImportResponse)
def import_videos_endpoint(
    payload: VideoImportRequest,
    db: Session = Depends(get_db),
) -> VideoImportResponse:
    try:
        return media_service.import_videos(
            db=db,
            target_path=payload.path,
            collection_id=payload.collection_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[VideoOut])
def list_videos_endpoint(
    collection_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[VideoOut]:
    return media_service.list_videos(db=db, collection_id=collection_id, status=status)


@router.get("/stats/summary")
def get_library_stats_endpoint(db: Session = Depends(get_db)) -> dict:
    return media_service.get_library_stats(db=db)


@router.get("/{video_id}", response_model=VideoOut)
def get_video_endpoint(video_id: str, db: Session = Depends(get_db)) -> VideoOut:
    try:
        return media_service.get_video_out(db=db, video_id=video_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{video_id}/thumbnail")
def get_video_thumbnail_endpoint(video_id: str, db: Session = Depends(get_db)) -> FileResponse:
    try:
        video = media_service.get_video(db=db, video_id=video_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not video.thumbnail_path or not Path(video.thumbnail_path).is_file():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(video.thumbnail_path, media_type="image/jpeg")


@router.delete("/{video_id}/index")
def delete_video_index_endpoint(
    video_id: str,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    try:
        return media_service.delete_video_index(db=db, video_id=video_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{video_id}/process")
def process_video_endpoint(
    video_id: str,
    background_tasks: BackgroundTasks,
    sync: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    video = db.query(Video).filter_by(id=video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    if sync:
        job_id = run_video_pipeline(video_id=video_id, db=db)
        return {"video_id": video_id, "status": "completed", "job_id": job_id}

    background_tasks.add_task(run_video_pipeline, video_id=video_id)
    return {"video_id": video_id, "status": "scheduled"}


@router.get("/{video_id}/transcript", response_model=TranscriptOut)
def get_video_transcript_endpoint(
    video_id: str,
    db: Session = Depends(get_db),
) -> TranscriptOut:
    transcript = db.query(Transcript).filter_by(video_id=video_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail=f"No transcript found for video {video_id}")
    return TranscriptOut(
        id=transcript.id,
        video_id=transcript.video_id,
        language=transcript.language,
        model_name=transcript.model_name,
        full_text=transcript.full_text,
        segments=[TranscriptSegmentOut.model_validate(s) for s in transcript.segments],
    )


@router.get("/{video_id}/scenes", response_model=list[VideoSceneOut])
def get_video_scenes_endpoint(
    video_id: str,
    db: Session = Depends(get_db),
) -> list[VideoSceneOut]:
    scenes = (
        db.query(VideoScene)
        .filter_by(video_id=video_id)
        .order_by(VideoScene.scene_index.asc())
        .all()
    )
    return [VideoSceneOut.model_validate(s) for s in scenes]


def _iter_file_range(file_path: Path, start: int, end: int, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
    with file_path.open("rb") as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            data = f.read(min(chunk_size, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


@router.get("/{video_id}/stream")
def stream_video_endpoint(
    video_id: str,
    range_header: str | None = Header(default=None, alias="Range"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    try:
        video = media_service.get_video(db=db, video_id=video_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    file_path = Path(video.file_path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Source video file missing on disk")

    file_size = file_path.stat().st_size
    content_type, _ = mimetypes.guess_type(str(file_path))
    media_type = content_type or "video/mp4"

    if not range_header or not range_header.startswith("bytes="):
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
        }
        return StreamingResponse(
            _iter_file_range(file_path, 0, file_size - 1),
            status_code=200,
            media_type=media_type,
            headers=headers,
        )

    range_spec = range_header.replace("bytes=", "", 1).split(",", 1)[0].strip()
    start_str, end_str = range_spec.split("-", 1) if "-" in range_spec else (range_spec, "")
    try:
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1
    except ValueError as exc:
        raise HTTPException(status_code=416, detail="Invalid Range header") from exc

    if start < 0 or start >= file_size or end < start:
        raise HTTPException(
            status_code=416,
            detail="Requested Range Not Satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    end = min(end, file_size - 1)
    content_length = end - start + 1
    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
    }
    return StreamingResponse(
        _iter_file_range(file_path, start, end),
        status_code=206,
        media_type=media_type,
        headers=headers,
    )


_WINDOWS_DEVICE_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


def _is_safe_filename_char(ch: str) -> bool:
    if ch in ("_", "-", ".", " "):
        return True
    cat = unicodedata.category(ch)
    # Allow Unicode letters (L*), numbers (N*), and combining marks (M*)
    return cat[0] in ("L", "N", "M")


def is_safe_clip_filename(filename: str) -> bool:
    if (
        not filename
        or ".." in filename
        or "/" in filename
        or "\\" in filename
        or "\x00" in filename
        or Path(filename).name != filename
    ):
        return False

    base = filename.split(".")[0].upper()
    if base in _WINDOWS_DEVICE_NAMES:
        return False

    return all(_is_safe_filename_char(c) for c in filename)


@router.post("/{video_id}/export-clip", response_model=ClipExportResponse)
def export_video_clip_endpoint(
    video_id: str,
    payload: ClipExportRequest,
    db: Session = Depends(get_db),
) -> ClipExportResponse:
    try:
        video = media_service.get_video(db=db, video_id=video_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        start_time, end_time = _validate_clip_timestamps(
            start_time=payload.start_time,
            end_time=payload.end_time,
            max_duration=video.duration,
        )
    except (ValueError, TypeError) as val_err:
        raise HTTPException(status_code=400, detail=str(val_err)) from val_err

    try:
        clip_path = export_subclip(
            video_path=video.file_path,
            start_time=start_time,
            end_time=end_time,
            video_id=video.id,
            max_duration=video.duration,
        )
        actual_duration = measure_clip_duration(clip_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to export video clip: {exc}") from exc

    return ClipExportResponse(
        video_id=video.id,
        clip_filename=clip_path.name,
        start_time=start_time,
        end_time=end_time,
        duration=actual_duration,
        file_size=clip_path.stat().st_size,
        download_url=f"/api/v1/videos/clips/{clip_path.name}",
    )


@router.get("/clips/{clip_filename}")
def download_clip_endpoint(clip_filename: str) -> FileResponse:
    if not is_safe_clip_filename(clip_filename):
        raise HTTPException(status_code=400, detail="Invalid clip filename")

    clips_dir = (Path(settings.MEDIA_STORAGE_DIR) / "clips").resolve()
    clip_path = (clips_dir / clip_filename).resolve()

    try:
        is_contained = clip_path.is_relative_to(clips_dir)
    except ValueError:
        is_contained = False

    if not is_contained or clip_path == clips_dir:
        raise HTTPException(status_code=400, detail="Invalid clip path or directory escape attempt")

    if not clip_path.is_file():
        raise HTTPException(status_code=404, detail="Exported clip not found")

    return FileResponse(
        path=str(clip_path),
        media_type="video/mp4",
        filename=clip_filename,
    )


@router.post("/{video_id}/subtitles", response_model=TranscriptOut)
def ingest_subtitles_endpoint(
    video_id: str,
    payload: SubtitleIngestRequest,
    db: Session = Depends(get_db),
) -> TranscriptOut:
    video = db.query(Video).filter_by(id=video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        transcript = ingest_subtitles_for_video(
            db=db,
            video=video,
            content=payload.content,
            source_name=payload.filename,
            language=payload.language,
        )
        return TranscriptOut.model_validate(transcript)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to ingest subtitles: {exc}") from exc


