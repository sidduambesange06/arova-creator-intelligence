"""Media Discovery and Root Management Service for Arova Creator Intelligence.

Fulfills Task 4B acceptance criteria:
1. Reliable media-folder scanning with directory exclusion and format filtering.
2. Media-root management enforcing ALLOWED_MEDIA_ROOTS and marker tracking.
3. Deterministic media discovery (UUIDv5 version identity, relative path normalization, stat keys).
4. Duplicate, relink, in-place modification, and missing file handling.
5. Network-path and file safety (read-only probing, zero source media mutation/deletion).
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import compute_sha256, get_allowed_roots, validate_media_path
from app.models.entities import (
    Asset,
    AssetLocation,
    AssetVersion,
    Library,
    LibraryRoot,
    ScanRun,
    Video,
)
from app.models.enums import (
    ExecutionProfile,
    IdentityState,
    LocationAvailability,
    RootPolicy,
    RootType,
    compute_deterministic_version_id,
)

# Supported media extensions for discovery
DISCOVERY_MEDIA_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".mp4",
        ".mov",
        ".mkv",
        ".webm",
        ".avi",
        ".flv",
        ".m4v",
        ".wmv",
        ".m4a",
        ".wav",
        ".mp3",
    }
)

# Ignored directory names (case-insensitive) to prevent scanning deep dependency or VCS trees
IGNORED_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        ".svn",
        ".hg",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "dist",
        "build",
        ".pytest_cache",
        ".ruff_cache",
        ".idea",
        ".cursor",
        ".vscode",
    }
)

ROOT_MARKER_FILENAME = ".arova_root"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Library and Media-Root Management
# ---------------------------------------------------------------------------


def create_or_get_library(
    db: Session,
    label: str = "Default Library",
    execution_profile: str = ExecutionProfile.FULLY_OFFLINE_NO_AI.value,
) -> Library:
    """Retrieve an existing Library by label or create a new one."""
    library = db.query(Library).filter_by(label=label).first()
    if not library:
        library = Library(
            id=str(uuid.uuid4()),
            label=label,
            execution_profile=execution_profile,
            created_at=_utcnow(),
        )
        db.add(library)
        db.commit()
        db.refresh(library)
    return library


def _resolve_marker_id(root_canonical_path: Path) -> str:
    """Read or create root marker file to identify the storage volume reliably across mount point changes."""
    marker_file = root_canonical_path / ROOT_MARKER_FILENAME
    if marker_file.is_file():
        try:
            content = marker_file.read_text(encoding="utf-8").strip()
            if content:
                # If content is JSON or bare UUID
                if content.startswith("{"):
                    data = json.loads(content)
                    return data.get("marker_id", str(uuid.uuid5(uuid.NAMESPACE_DNS, str(root_canonical_path))))
                return content
        except Exception:
            pass

    # Try creating marker file if directory is writable
    generated_id = str(uuid.uuid4())
    try:
        marker_data = {
            "marker_id": generated_id,
            "created_at": _utcnow().isoformat(),
            "generator": "arova-creator-intelligence",
        }
        marker_file.write_text(json.dumps(marker_data, indent=2), encoding="utf-8")
        return generated_id
    except (OSError, PermissionError):
        # Fallback to deterministic UUID derived from canonical path string
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, str(root_canonical_path)))


def register_library_root(
    db: Session,
    library_id: str,
    path: str | Path,
    label: str | None = None,
    root_type: str = RootType.LOCAL_FIXED.value,
    policy: str = RootPolicy.LOCAL_ONLY.value,
    allowed_roots: list[Path] | None = None,
) -> LibraryRoot:
    """Validate and register a new media root under a library.

    Enforces:
    - Path existence and directory check.
    - Security containment against ALLOWED_MEDIA_ROOTS.
    - Path canonicalization (volume_id stores canonical absolute path).
    - Marker ID identification.
    - Rejection of path traversal escapes.
    """
    library = db.query(Library).filter_by(id=library_id).first()
    if not library:
        raise LookupError(f"Library not found: {library_id}")

    # Validate directory containment
    canonical_dir = validate_media_path(path, allowed_roots=allowed_roots)
    if not canonical_dir.is_dir():
        raise ValueError(f"Target media root path is not a directory: '{canonical_dir}'")

    volume_id = str(canonical_dir)
    marker_id = _resolve_marker_id(canonical_dir)
    effective_label = label.strip() if label and label.strip() else canonical_dir.name or str(canonical_dir)

    # Check for existing root matching volume_id or marker_id within this library
    existing_root = (
        db.query(LibraryRoot)
        .filter(
            LibraryRoot.library_id == library_id,
            (LibraryRoot.volume_id == volume_id) | (LibraryRoot.marker_id == marker_id),
        )
        .first()
    )
    if existing_root:
        existing_root.status = "active"
        existing_root.policy = policy
        existing_root.volume_id = volume_id  # Update volume_id in case drive letter/mount moved
        db.commit()
        db.refresh(existing_root)
        return existing_root

    root = LibraryRoot(
        id=str(uuid.uuid4()),
        library_id=library_id,
        label=effective_label,
        root_type=root_type,
        volume_id=volume_id,
        marker_id=marker_id,
        policy=policy,
        status="active",
        last_scan_at=None,
    )
    db.add(root)
    db.commit()
    db.refresh(root)
    return root


def list_library_roots(db: Session, library_id: str) -> list[LibraryRoot]:
    """List all registered roots for a library."""
    return db.query(LibraryRoot).filter_by(library_id=library_id).all()


def get_library_root(db: Session, root_id: str) -> LibraryRoot | None:
    """Retrieve specific LibraryRoot by ID."""
    return db.query(LibraryRoot).filter_by(id=root_id).first()


def update_library_root_policy(db: Session, root_id: str, policy: str) -> LibraryRoot:
    """Update root execution policy (e.g. LOCAL_ONLY vs ALLOW_REMOTE)."""
    root = db.query(LibraryRoot).filter_by(id=root_id).first()
    if not root:
        raise LookupError(f"LibraryRoot not found: {root_id}")
    root.policy = policy
    db.commit()
    db.refresh(root)
    return root


# ---------------------------------------------------------------------------
# Reliable Media-Folder Scanning & Deterministic Discovery
# ---------------------------------------------------------------------------


def _scan_directory_files(
    root_canonical_path: Path,
    allowed_roots: list[Path] | None = None,
) -> tuple[list[Path], list[str]]:
    """Recursively collect media files under root_canonical_path, safely skipping ignored dirs.

    Returns (discovered_media_paths, error_messages).
    Enforces read-only safety: does not touch or write to discovered files.
    """
    discovered: list[Path] = []
    errors: list[str] = []
    roots = allowed_roots if allowed_roots is not None else get_allowed_roots()

    stack: list[Path] = [root_canonical_path]

    while stack:
        current_dir = stack.pop()
        try:
            with os.scandir(current_dir) as entries:
                for entry in entries:
                    try:
                        name = entry.name
                        # Skip ignored directory names and dot-directories
                        if entry.is_dir(follow_symlinks=False):
                            if name.lower() in IGNORED_DIR_NAMES or name.startswith("."):
                                continue
                            canonical_sub = Path(entry.path).resolve()
                            # Reject directory symlinks escaping allowed roots
                            if not any(canonical_sub == r or r in canonical_sub.parents for r in roots):
                                errors.append(f"Symlink directory escape rejected: {entry.path}")
                                continue
                            stack.append(Path(entry.path))

                        elif entry.is_file(follow_symlinks=True):
                            # Skip marker file or dot-files
                            if name.startswith("."):
                                continue
                            suffix = Path(name).suffix.lower()
                            if suffix in DISCOVERY_MEDIA_EXTENSIONS:
                                canonical_file = Path(entry.path).resolve()
                                # Verify file target does not escape allowed roots
                                if any(canonical_file == r or r in canonical_file.parents for r in roots):
                                    discovered.append(Path(entry.path))
                                else:
                                    errors.append(f"Symlink file escape rejected: {entry.path}")

                    except (OSError, PermissionError) as exc:
                        errors.append(f"Error reading entry '{entry.name}' in '{current_dir}': {exc}")
                        continue

        except (OSError, PermissionError) as exc:
            errors.append(f"Error accessing directory '{current_dir}': {exc}")
            continue

    # Deterministic alphabetical ordering by normalized relative path
    discovered.sort(key=lambda p: str(p.relative_to(root_canonical_path)).replace("\\", "/").lower())
    return discovered, errors


def run_root_media_scan(
    db: Session,
    root_id: str,
    allowed_roots: list[Path] | None = None,
) -> ScanRun:
    """Execute deterministic media discovery scan across a LibraryRoot.

    Fulfills:
    - Non-destructive read-only probing.
    - Checkpointed ScanRun tracking.
    - Duplicate detection (same content in multiple locations).
    - Relink detection (moved/renamed files).
    - In-place modification (new version creation with supersedes_version_id).
    - Missing file transition (availability='missing', missing_since=now).
    - Restoration of missing files when reappearing.
    - Zero accidental deletion of source files or database artifacts.
    """
    root = db.query(LibraryRoot).filter_by(id=root_id).first()
    if not root:
        raise LookupError(f"LibraryRoot not found: {root_id}")

    if not root.volume_id:
        raise ValueError(f"LibraryRoot '{root.id}' does not have a configured volume_id filesystem path.")

    root_path = Path(root.volume_id)
    canonical_root = validate_media_path(root_path, allowed_roots=allowed_roots)

    scan_run = ScanRun(
        id=str(uuid.uuid4()),
        root_id=root.id,
        status="running",
        started_at=_utcnow(),
        finished_at=None,
        checkpoint=None,
        counts=json.dumps(
            {
                "scanned_files": 0,
                "discovered_media": 0,
                "new_assets": 0,
                "new_versions": 0,
                "new_locations": 0,
                "updated_locations": 0,
                "missing_locations": 0,
                "relocated_locations": 0,
                "errors": 0,
            }
        ),
    )
    db.add(scan_run)
    db.commit()
    db.refresh(scan_run)

    seen_location_ids: set[str] = set()
    counts = {
        "scanned_files": 0,
        "discovered_media": 0,
        "new_assets": 0,
        "new_versions": 0,
        "new_locations": 0,
        "updated_locations": 0,
        "missing_locations": 0,
        "relocated_locations": 0,
        "errors": 0,
    }

    try:
        discovered_files, dir_errors = _scan_directory_files(canonical_root, allowed_roots=allowed_roots)
        counts["errors"] += len(dir_errors)
        counts["discovered_media"] = len(discovered_files)

        # Process each media file deterministically
        for file_path in discovered_files:
            counts["scanned_files"] += 1
            try:
                # 1. Compute normalized paths
                rel_path = str(file_path.relative_to(canonical_root))
                rel_path_norm = rel_path.replace("\\", "/").strip().lower()

                # 2. File stat key
                st = file_path.stat()
                file_size = st.st_size
                stat_key = f"{file_size}:{int(st.st_mtime)}"

                # 3. Read-only streaming SHA-256
                sha256 = compute_sha256(file_path)
                version_id = compute_deterministic_version_id(sha256)

                # 4. Check location record for (root_id, rel_path_norm)
                location = (
                    db.query(AssetLocation)
                    .filter_by(root_id=root.id, rel_path_norm=rel_path_norm)
                    .first()
                )

                if location:
                    # Existing location on this root
                    seen_location_ids.add(location.id)
                    if location.version_id == version_id:
                        # Case A: Same version in same location (unchanged or restored)
                        if location.availability != LocationAvailability.AVAILABLE.value:
                            location.availability = LocationAvailability.AVAILABLE.value
                            location.missing_since = None
                            counts["updated_locations"] += 1
                        location.last_seen_at = _utcnow()
                        location.stat_key = stat_key
                        location.rel_path = rel_path
                    else:
                        # Case B: In-place file content modification
                        old_version = db.get(AssetVersion, location.version_id)
                        asset_id = old_version.asset_id if old_version else str(uuid.uuid4())

                        # Find or create new version
                        new_version = db.get(AssetVersion, version_id)
                        if not new_version:
                            new_version = AssetVersion(
                                id=version_id,
                                asset_id=asset_id,
                                sha256=sha256,
                                size_bytes=file_size,
                                media_meta=json.dumps({"filename": file_path.name}),
                                supersedes_version_id=old_version.id if old_version else None,
                                identity_state=IdentityState.VERIFIED.value,
                                created_at=_utcnow(),
                            )
                            db.add(new_version)
                            db.flush()
                            counts["new_versions"] += 1

                        # Update asset current version
                        asset = db.get(Asset, asset_id)
                        if asset:
                            asset.current_version_id = version_id

                        # Re-point location to new version
                        location.version_id = version_id
                        location.stat_key = stat_key
                        location.last_seen_at = _utcnow()
                        location.availability = LocationAvailability.AVAILABLE.value
                        location.missing_since = None
                        counts["updated_locations"] += 1

                else:
                    # Location does not exist at this relative path
                    # Check if an AssetVersion for this SHA-256 already exists
                    existing_version = db.query(AssetVersion).filter_by(sha256=sha256).first()

                    if existing_version:
                        # Content is already known
                        # Check for relink candidate: missing location with same version in this root
                        missing_loc = (
                            db.query(AssetLocation)
                            .filter(
                                AssetLocation.root_id == root.id,
                                AssetLocation.version_id == existing_version.id,
                                AssetLocation.availability == LocationAvailability.MISSING.value,
                            )
                            .first()
                        )

                        if missing_loc:
                            # Case C: Move / Rename Relink detected
                            missing_loc.availability = LocationAvailability.RELINK_REQUIRED.value
                            counts["relocated_locations"] += 1

                        # Create new location pointing to the existing version
                        new_loc_id = str(uuid.uuid4())
                        seen_location_ids.add(new_loc_id)
                        new_loc = AssetLocation(
                            id=new_loc_id,
                            version_id=existing_version.id,
                            root_id=root.id,
                            rel_path=rel_path,
                            rel_path_norm=rel_path_norm,
                            stat_key=stat_key,
                            last_seen_at=_utcnow(),
                            availability=LocationAvailability.AVAILABLE.value,
                            missing_since=None,
                        )
                        db.add(new_loc)
                        counts["new_locations"] += 1

                    else:
                        # Case D: Completely new media asset
                        new_asset = Asset(
                            id=str(uuid.uuid4()),
                            created_at=_utcnow(),
                        )
                        db.add(new_asset)
                        db.flush()

                        new_version = AssetVersion(
                            id=version_id,
                            asset_id=new_asset.id,
                            sha256=sha256,
                            size_bytes=file_size,
                            media_meta=json.dumps({"filename": file_path.name}),
                            supersedes_version_id=None,
                            identity_state=IdentityState.VERIFIED.value,
                            created_at=_utcnow(),
                        )
                        db.add(new_version)
                        db.flush()

                        new_asset.current_version_id = new_version.id

                        new_loc_id = str(uuid.uuid4())
                        seen_location_ids.add(new_loc_id)
                        new_loc = AssetLocation(
                            id=new_loc_id,
                            version_id=new_version.id,
                            root_id=root.id,
                            rel_path=rel_path,
                            rel_path_norm=rel_path_norm,
                            stat_key=stat_key,
                            last_seen_at=_utcnow(),
                            availability=LocationAvailability.AVAILABLE.value,
                            missing_since=None,
                        )
                        db.add(new_loc)

                        # Maintain backward-compatible Video entry if not present
                        existing_vid = db.query(Video).filter_by(file_hash=sha256).first()
                        if not existing_vid:
                            video_entry = Video(
                                id=new_asset.id,
                                filename=file_path.name,
                                file_path=str(file_path.resolve()),
                                file_hash=sha256,
                                file_size=file_size,
                                duration=0.0,
                                width=0,
                                height=0,
                                fps=0.0,
                                codec="unknown",
                                format=file_path.suffix.lstrip(".").lower(),
                                processing_status="discovered",
                                asset_id=new_asset.id,
                                version_id=new_version.id,
                                created_at=_utcnow(),
                            )
                            db.add(video_entry)

                        counts["new_assets"] += 1
                        counts["new_versions"] += 1
                        counts["new_locations"] += 1

            except (OSError, PermissionError) as exc:
                counts["errors"] += 1
                continue

        # 5. Missing File Detection: Locations not seen in this scan run
        unseen_locations = (
            db.query(AssetLocation)
            .filter(
                AssetLocation.root_id == root.id,
                AssetLocation.id.notin_(seen_location_ids) if seen_location_ids else True,
                AssetLocation.availability == LocationAvailability.AVAILABLE.value,
            )
            .all()
        )
        for missing_loc in unseen_locations:
            missing_loc.availability = LocationAvailability.MISSING.value
            missing_loc.missing_since = _utcnow()
            counts["missing_locations"] += 1

        # 6. Finalize ScanRun and Root
        root.last_scan_at = _utcnow()
        scan_run.status = "completed"
        scan_run.finished_at = _utcnow()
        scan_run.counts = json.dumps(counts)
        db.commit()
        db.refresh(scan_run)
        return scan_run

    except Exception as exc:
        db.rollback()
        scan_run.status = "failed"
        scan_run.finished_at = _utcnow()
        scan_run.checkpoint = f"Fatal scan exception: {exc}"
        scan_run.counts = json.dumps(counts)
        db.commit()
        db.refresh(scan_run)
        raise


def get_scan_run(db: Session, scan_id: str) -> ScanRun | None:
    """Retrieve ScanRun by ID."""
    return db.query(ScanRun).filter_by(id=scan_id).first()


def list_scan_runs_for_root(db: Session, root_id: str) -> list[ScanRun]:
    """List recent scan runs for a LibraryRoot."""
    return db.query(ScanRun).filter_by(root_id=root_id).order_by(ScanRun.started_at.desc()).all()


def list_library_assets(
    db: Session,
    library_id: str,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Asset], int]:
    """List assets belonging to a library through its root locations."""
    # Find all root IDs in this library
    root_ids = [r.id for r in db.query(LibraryRoot).filter_by(library_id=library_id).all()]
    if not root_ids:
        return [], 0

    # Query distinct assets with locations in these roots
    asset_ids_query = (
        db.query(AssetVersion.asset_id)
        .join(AssetLocation, AssetLocation.version_id == AssetVersion.id)
        .filter(AssetLocation.root_id.in_(root_ids))
        .distinct()
    )
    total = asset_ids_query.count()
    asset_ids = [row[0] for row in asset_ids_query.offset(offset).limit(limit).all()]

    assets = db.query(Asset).filter(Asset.id.in_(asset_ids)).all() if asset_ids else []
    return assets, total
