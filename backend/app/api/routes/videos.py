from collections.abc import Iterator
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.media import VideoImportRequest, VideoImportResponse, VideoOut
from app.services import media_service

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
