"""REST API Routes for Task 4D: Portable Media Memory, Availability, Relinking, and Annotations."""

from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.models.entities import (
    Annotation,
    AssetLocation,
    AssetVersion,
)
from app.models.enums import LocationAvailability
from app.schemas.portable import (
    AnnotationCreate,
    AnnotationOut,
    DuplicateGroupOut,
    DuplicateLocationItem,
    ExportRequest,
    ExportSummary,
    ImportDryRunReport,
    ImportResult,
    MediaAvailabilityOut,
    RelinkRequest,
    RelinkResponse,
)
from app.services.portable_service import (
    ArchiveSecurityError,
    dry_run_import_archive,
    export_portable_archive,
    import_portable_archive,
    relink_asset_media,
    resolve_media_availability,
)

router = APIRouter(prefix="/api/v1", tags=["portable"])


# -----------------------------------------------------------------------------
# PORTABLE ARCHIVE ENDPOINTS
# -----------------------------------------------------------------------------

def _resolve_safe_export_target(export_dir: Path, output_filename: str | None) -> Path:
    """Resolve export target strictly inside export_dir without allowing traversal or overwrites."""
    resolved_dir = export_dir.resolve()
    resolved_dir.mkdir(parents=True, exist_ok=True)

    if output_filename is not None:
        raw = output_filename.strip()
        win_path = PureWindowsPath(raw)
        posix_path = Path(raw)
        if (
            not raw
            or raw in (".", "..")
            or "/" in raw
            or "\\" in raw
            or ".." in posix_path.parts
            or ".." in win_path.parts
            or posix_path.is_absolute()
            or win_path.is_absolute()
            or bool(win_path.drive)
            or posix_path.name != raw
            or win_path.name != raw
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid export filename: absolute paths and directory components are not permitted",
            )
        filename = raw if raw.endswith((".arova", ".zip")) else f"{raw}.arova"
        if Path(filename).stem in ("", ".", ".."):
            raise HTTPException(status_code=400, detail="Invalid export filename")
    else:
        ts = int(datetime.now(timezone.utc).timestamp())
        filename = f"arova_memory_export_{ts}.arova"
        if (resolved_dir / filename).exists() or (resolved_dir / filename).is_symlink():
            filename = f"arova_memory_export_{ts}_{uuid4().hex[:8]}.arova"

    candidate = resolved_dir / filename
    if candidate.is_symlink():
        raise HTTPException(status_code=400, detail="Export target cannot be a symbolic link")

    target_path = candidate.resolve()
    if target_path.parent != resolved_dir or resolved_dir not in target_path.parents:
        raise HTTPException(status_code=400, detail="Export target must remain within the export directory")

    if candidate.exists() or target_path.exists():
        raise HTTPException(
            status_code=409,
            detail=f"Export archive '{filename}' already exists; refusing to overwrite",
        )

    return target_path


@router.post("/portable/export", response_model=ExportSummary)
def export_archive_endpoint(
    req: ExportRequest | None = None,
    output_filename: str | None = None,
    db: Session = Depends(get_db),
) -> ExportSummary:
    """Export media memory into a versioned .arova container archive."""
    export_dir = Path(settings.DATA_DIR) / "exports"
    target_path = _resolve_safe_export_target(export_dir, output_filename)

    try:
        summary = export_portable_archive(
            db=db,
            target_archive_path=target_path,
            request=req,
        )
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ArchiveSecurityError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return summary


@router.post("/portable/import/dry-run", response_model=ImportDryRunReport)
def dry_run_import_endpoint(
    archive_path: str = Query(description="Filesystem path to the .arova archive"),
    db: Session = Depends(get_db),
) -> ImportDryRunReport:
    """Validate archive integrity and preview planned imports without modifying database."""
    target_path = Path(archive_path).resolve()
    if not target_path.is_file():
        raise HTTPException(status_code=404, detail=f"Archive file not found: {archive_path}")

    try:
        report = dry_run_import_archive(db=db, archive_path=target_path)
        return report
    except ArchiveSecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Dry run failed: {exc}")


@router.post("/portable/import", response_model=ImportResult)
def import_archive_endpoint(
    archive_path: str = Query(description="Filesystem path to the .arova archive"),
    library_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ImportResult:
    """Safely import validated records from .arova archive into database."""
    target_path = Path(archive_path).resolve()
    if not target_path.is_file():
        raise HTTPException(status_code=404, detail=f"Archive file not found: {archive_path}")

    try:
        result = import_portable_archive(db=db, archive_path=target_path, library_id=library_id)
        if result.status == "rejected":
            raise HTTPException(status_code=400, detail="; ".join(result.errors))
        return result
    except ArchiveSecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Import failed: {exc}")


# -----------------------------------------------------------------------------
# AVAILABILITY & RELINKING ENDPOINTS
# -----------------------------------------------------------------------------

@router.get("/versions/{version_id}/availability", response_model=MediaAvailabilityOut)
def get_media_availability_endpoint(
    version_id: str,
    db: Session = Depends(get_db),
) -> MediaAvailabilityOut:
    """Retrieve media file presence, can_play, and can_export flags for an asset version."""
    try:
        return resolve_media_availability(db=db, version_id=version_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/versions/{version_id}/relink", response_model=RelinkResponse)
def relink_version_endpoint(
    version_id: str,
    req: RelinkRequest,
    db: Session = Depends(get_db),
) -> RelinkResponse:
    """Relink an asset version to a relocated media file."""
    try:
        return relink_asset_media(db=db, version_id=version_id, new_file_path=req.new_file_path)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/libraries/duplicates", response_model=list[DuplicateGroupOut])
def list_duplicate_media_endpoint(
    db: Session = Depends(get_db),
) -> list[DuplicateGroupOut]:
    """Find media versions mapped across multiple physical file locations."""
    # Group locations by version_id
    versions = db.query(AssetVersion).all()
    duplicates = []

    for v in versions:
        locs = db.query(AssetLocation).filter_by(version_id=v.id).all()
        if len(locs) > 1:
            loc_items = [
                DuplicateLocationItem(
                    location_id=loc.id,
                    root_id=loc.root_id,
                    rel_path=loc.rel_path,
                    availability=loc.availability,
                    last_seen_at=loc.last_seen_at,
                )
                for loc in locs
            ]
            duplicates.append(
                DuplicateGroupOut(
                    sha256=v.sha256 or "unknown",
                    version_id=v.id,
                    size_bytes=v.size_bytes or 0,
                    locations_count=len(locs),
                    locations=loc_items,
                )
            )

    return duplicates


# -----------------------------------------------------------------------------
# ANNOTATIONS CRUD ENDPOINTS
# -----------------------------------------------------------------------------

@router.post("/annotations", response_model=AnnotationOut)
def create_annotation_endpoint(
    req: AnnotationCreate,
    db: Session = Depends(get_db),
) -> AnnotationOut:
    """Create an annotation attached to an asset, version, or moment."""
    annotation = Annotation(
        id=str(uuid4()),
        target_type=req.target_type,
        target_id=req.target_id,
        author_type=req.author_type,
        display_name=req.display_name,
        trust=req.trust,
        ai_run_id=req.ai_run_id,
        body=req.body,
        created_at=datetime.now(timezone.utc),
    )
    db.add(annotation)
    db.commit()
    db.refresh(annotation)
    return AnnotationOut.model_validate(annotation)


@router.get("/annotations", response_model=list[AnnotationOut])
def list_annotations_endpoint(
    target_type: str | None = None,
    target_id: str | None = None,
    author_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[AnnotationOut]:
    """List annotations with optional target or author filters."""
    query = db.query(Annotation)
    if target_type:
        query = query.filter(Annotation.target_type == target_type)
    if target_id:
        query = query.filter(Annotation.target_id == target_id)
    if author_type:
        query = query.filter(Annotation.author_type == author_type)

    annotations = query.order_by(Annotation.created_at.desc()).offset(offset).limit(limit).all()
    return [AnnotationOut.model_validate(an) for an in annotations]


@router.delete("/annotations/{annotation_id}")
def delete_annotation_endpoint(
    annotation_id: str,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Delete an annotation."""
    annotation = db.get(Annotation, annotation_id)
    if not annotation:
        raise HTTPException(status_code=404, detail=f"Annotation {annotation_id} not found")

    db.delete(annotation)
    db.commit()
    return {"id": annotation_id, "status": "deleted"}

