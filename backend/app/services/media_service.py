from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.security import compute_sha256, discover_video_files
from app.models.entities import Collection, CollectionVideo, ProcessingJob, Video
from app.processing.metadata import probe_video_metadata
from app.processing.thumbnails import generate_video_thumbnail
from app.schemas.media import CollectionOut, VideoImportResponse, VideoOut


def _to_video_out(video: Video) -> VideoOut:
    return VideoOut(
        id=video.id,
        filename=video.filename,
        file_path=video.file_path,
        file_hash=video.file_hash,
        file_size=video.file_size,
        duration=video.duration,
        width=video.width,
        height=video.height,
        fps=video.fps,
        codec=video.codec,
        format=video.format,
        thumbnail_path=video.thumbnail_path,
        processing_status=video.processing_status,
        created_at=video.created_at,
        collection_ids=[cv.collection_id for cv in video.collections],
    )


def import_videos(
    db: Session,
    target_path: str,
    collection_id: str | None = None,
    allowed_roots: list[Path] | None = None,
    media_storage_dir: str | Path | None = None,
) -> VideoImportResponse:
    if collection_id:
        col = db.query(Collection).filter_by(id=collection_id).first()
        if not col:
            raise LookupError(f"Collection not found: {collection_id}")

    files = discover_video_files(target_path, allowed_roots=allowed_roots)
    imported: list[VideoOut] = []
    skipped_duplicates = 0

    for file_path in files:
        norm_path = str(file_path.resolve())
        file_hash = compute_sha256(file_path)

        existing = (
            db.query(Video)
            .filter((Video.file_path == norm_path) | (Video.file_hash == file_hash))
            .first()
        )
        if existing:
            skipped_duplicates += 1
            if collection_id:
                _ensure_collection_link(db, collection_id, existing.id)
                db.commit()
            continue

        video_id = str(uuid4())
        meta = probe_video_metadata(file_path)
        thumb_time = min(max(meta.duration * 0.25, 0.1), 5.0) if meta.duration > 0 else 0.0
        thumb_path = generate_video_thumbnail(
            video_path=file_path,
            video_id=video_id,
            timestamp_sec=thumb_time,
            output_dir=media_storage_dir,
        )

        video = Video(
            id=video_id,
            filename=file_path.name,
            file_path=norm_path,
            file_hash=file_hash,
            file_size=meta.file_size,
            duration=meta.duration,
            width=meta.width,
            height=meta.height,
            fps=meta.fps,
            codec=meta.codec,
            format=meta.format,
            thumbnail_path=str(thumb_path),
            processing_status="indexed",
        )
        db.add(video)
        db.flush()

        job = ProcessingJob(
            video_id=video.id,
            job_type="probe",
            status="completed",
            progress=100.0,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(job)

        if collection_id:
            _ensure_collection_link(db, collection_id, video.id)

        db.commit()
        db.refresh(video)
        imported.append(_to_video_out(video))

    return VideoImportResponse(imported=imported, skipped_duplicates=skipped_duplicates)


def _ensure_collection_link(db: Session, collection_id: str, video_id: str) -> None:
    exists = (
        db.query(CollectionVideo)
        .filter_by(collection_id=collection_id, video_id=video_id)
        .first()
    )
    if not exists:
        db.add(CollectionVideo(collection_id=collection_id, video_id=video_id))


def list_videos(
    db: Session,
    collection_id: str | None = None,
    status: str | None = None,
) -> list[VideoOut]:
    query = db.query(Video)
    if collection_id:
        query = query.join(CollectionVideo).filter(CollectionVideo.collection_id == collection_id)
    if status:
        query = query.filter(Video.processing_status == status)
    videos = query.order_by(Video.created_at.desc()).all()
    return [_to_video_out(v) for v in videos]


def get_video(db: Session, video_id: str) -> Video:
    video = db.query(Video).filter_by(id=video_id).first()
    if not video:
        raise LookupError(f"Video not found: {video_id}")
    return video


def get_video_out(db: Session, video_id: str) -> VideoOut:
    return _to_video_out(get_video(db, video_id))


def delete_video_index(db: Session, video_id: str) -> dict[str, str]:
    video = get_video(db, video_id)
    thumb_path = Path(video.thumbnail_path) if video.thumbnail_path else None
    source_path = video.file_path

    db.delete(video)
    db.commit()

    if thumb_path and thumb_path.is_file():
        thumb_path.unlink(missing_ok=True)

    return {"deleted_video_id": video_id, "preserved_source_path": source_path}


def create_collection(db: Session, name: str, description: str | None = None) -> CollectionOut:
    clean_name = name.strip()
    existing = db.query(Collection).filter_by(name=clean_name).first()
    if existing:
        raise ValueError(f"Collection '{clean_name}' already exists.")
    col = Collection(name=clean_name, description=description)
    db.add(col)
    db.commit()
    db.refresh(col)
    return CollectionOut(
        id=col.id,
        name=col.name,
        description=col.description,
        created_at=col.created_at,
        video_count=0,
    )


def list_collections(db: Session) -> list[CollectionOut]:
    cols = db.query(Collection).order_by(Collection.created_at.desc()).all()
    return [
        CollectionOut(
            id=c.id,
            name=c.name,
            description=c.description,
            created_at=c.created_at,
            video_count=len(c.videos),
        )
        for c in cols
    ]


def add_video_to_collection(db: Session, collection_id: str, video_id: str) -> CollectionOut:
    col = db.query(Collection).filter_by(id=collection_id).first()
    if not col:
        raise LookupError(f"Collection not found: {collection_id}")
    _ = get_video(db, video_id)
    _ensure_collection_link(db, collection_id, video_id)
    db.commit()
    db.refresh(col)
    return CollectionOut(
        id=col.id,
        name=col.name,
        description=col.description,
        created_at=col.created_at,
        video_count=len(col.videos),
    )

