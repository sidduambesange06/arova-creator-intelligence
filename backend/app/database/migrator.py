"""Database migration runner, pre-migration backup, idempotent backfill,
and remote execution policy evaluation for Arova Creator Intelligence.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models.entities import (
    AIConsent,
    Artifact,
    Asset,
    AssetLocation,
    AssetVersion,
    Library,
    LibraryRoot,
    Video,
)
from app.models.enums import (
    CapabilityReason,
    ExecutionProfile,
    IdentityState,
    LocationAvailability,
    RootPolicy,
    RootType,
)


def _get_alembic_config(engine: Engine | None = None) -> Config:
    backend_dir = Path(__file__).resolve().parent.parent.parent
    ini_path = backend_dir / "alembic.ini"
    migrations_dir = backend_dir / "app" / "database" / "migrations"

    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(migrations_dir))
    cfg.set_main_option("path_separator", "os")
    if engine is not None:
        cfg.attributes["connection"] = engine.connect()
    return cfg


def create_backup(db_path: str | Path) -> Path | None:
    """Create a verified physical backup of the SQLite database before migration.

    Uses SQLite's online backup API with fallback to VACUUM INTO.
    Guarantees WAL safety and verifies integrity with PRAGMA integrity_check.
    Returns the backup Path or None if in-memory or nonexistent.
    """
    path_str = str(db_path)
    if path_str == ":memory:" or "sqlite:///:memory:" in path_str:
        return None

    source_path = Path(path_str).resolve()
    if not source_path.is_file():
        return None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    backup_path = source_path.with_name(f"{source_path.name}.backup.{timestamp}")

    # Use SQLite Online Backup API (safely captures uncheckpointed WAL frames)
    try:
        source_conn = sqlite3.connect(str(source_path))
        try:
            try:
                source_conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
            except sqlite3.OperationalError:
                pass
            backup_conn = sqlite3.connect(str(backup_path))
            try:
                source_conn.backup(backup_conn)
            finally:
                backup_conn.close()
        finally:
            source_conn.close()

        if backup_path.is_file() and backup_path.stat().st_size > 0:
            verify_conn = sqlite3.connect(str(backup_path))
            try:
                res = verify_conn.execute("PRAGMA integrity_check;").fetchall()
                if res == [("ok",)]:
                    return backup_path
            finally:
                verify_conn.close()
    except Exception:
        pass

    # Fallback to VACUUM INTO
    try:
        conn = sqlite3.connect(str(source_path))
        try:
            conn.execute(f"VACUUM INTO '{backup_path.as_posix()}'")
        finally:
            conn.close()
        if backup_path.is_file() and backup_path.stat().st_size > 0:
            verify_conn = sqlite3.connect(str(backup_path))
            try:
                res = verify_conn.execute("PRAGMA integrity_check;").fetchall()
                if res == [("ok",)]:
                    return backup_path
            finally:
                verify_conn.close()
    except Exception:
        pass

    return None


def restore_backup(backup_path: str | Path, target_db_path: str | Path) -> None:
    """Restore target database from a previous backup using verified atomic restore."""
    b_path = Path(backup_path).resolve()
    t_path = Path(target_db_path).resolve()
    if not b_path.is_file():
        raise FileNotFoundError(f"Backup file not found: {b_path}")

    # 1. Verify backup file integrity before touching target
    b_conn = sqlite3.connect(str(b_path))
    try:
        check = b_conn.execute("PRAGMA integrity_check;").fetchall()
        if check != [("ok",)]:
            raise RuntimeError(f"Corrupt backup file: {check}")
    finally:
        b_conn.close()

    # 2. Destructive restore into target database via online backup API
    t_conn = sqlite3.connect(str(t_path))
    try:
        try:
            t_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        except sqlite3.OperationalError:
            pass
        b_conn = sqlite3.connect(str(b_path))
        try:
            b_conn.backup(t_conn)
        finally:
            b_conn.close()
        try:
            t_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        except sqlite3.OperationalError:
            pass
    finally:
        t_conn.close()

    # 3. Verify target database integrity after restore
    verify_conn = sqlite3.connect(str(t_path))
    try:
        verify_check = verify_conn.execute("PRAGMA integrity_check;").fetchall()
        if verify_check != [("ok",)]:
            raise RuntimeError(f"Target DB corrupted after restore: {verify_check}")
    finally:
        verify_conn.close()


class SchemaStateError(RuntimeError):
    """Raised when the database schema is in a partial, malformed, or unexpected state."""
    pass


BASELINE_V010_TABLES = frozenset({
    "videos",
    "collections",
    "collection_videos",
    "transcripts",
    "transcript_segments",
    "video_scenes",
    "embedding_records",
    "video_summaries",
    "processing_jobs",
})

BASELINE_VIDEOS_REQUIRED_COLUMNS = frozenset({
    "id",
    "filename",
    "file_path",
    "file_hash",
    "file_size",
    "duration",
    "width",
    "height",
    "fps",
    "codec",
    "format",
    "processing_status",
    "created_at",
})


def run_database_migrations(
    engine: Engine | None = None,
    db_path: str | Path | None = None,
) -> None:
    """Execute Alembic migrations according to the four-path decision matrix.

    Paths:
    1. Already versioned database: check revision. If head, return; else upgrade normally to head.
    2. Brand-new empty database: run from base revision through head (no stamping).
    3. Existing v0.1.0-alpha create_all database: verify all 9 baseline tables and required columns;
       stamp baseline 0001_initial_schema, then upgrade to head.
    4. Partial, malformed, or unexpected schema: stop with SchemaStateError diagnostic.
       Never stamp, drop, or silently repair.
    """
    target_engine = engine
    if target_engine is None:
        from app.database.session import engine as default_engine
        target_engine = default_engine

    # Step 1: Inspect actual schema state
    with target_engine.connect() as conn:
        inspector = inspect(conn)
        all_tables = set(inspector.get_table_names())
        # Ignore SQLite internals and FTS virtual/shadow tables for state categorization
        app_tables = {
            t for t in all_tables
            if not t.startswith("sqlite_") and not t.startswith("transcript_chunks_fts")
        }

        # Path 1: Already versioned database
        if "alembic_version" in all_tables:
            current_rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            if current_rev == "0003_indic_fts5_tokenization":
                # Already at head: zero backup, zero migration rerun
                return
            decision = "versioned_upgrade"

        # Path 2: Brand-new empty database (no application tables)
        elif len(app_tables) == 0:
            # Clean database: run Alembic from base revision through head.
            # Do NOT stamp baseline first.
            decision = "empty_upgrade"

        # Path 3 & 4: Unversioned database with application tables
        else:
            missing_tables = BASELINE_V010_TABLES - app_tables
            if not missing_tables:
                # All 9 baseline tables exist; inspect required columns on videos table
                video_cols = {col["name"] for col in inspector.get_columns("videos")}
                missing_video_cols = BASELINE_VIDEOS_REQUIRED_COLUMNS - video_cols
                if not missing_video_cols:
                    # Verified complete v0.1.0-alpha create_all database
                    decision = "v010_legacy_stamp_and_upgrade"
                else:
                    raise SchemaStateError(
                        f"Malformed legacy database: table 'videos' is missing required columns: {sorted(missing_video_cols)}. "
                        "Cannot safely stamp or upgrade. Manual review required."
                    )
            else:
                # Path 4: Partial, malformed, or unexpected schema
                unexpected_tables = app_tables - BASELINE_V010_TABLES
                raise SchemaStateError(
                    f"Partial, malformed, or unexpected schema detected without alembic_version. "
                    f"Existing tables: {sorted(app_tables)}. Missing baseline tables: {sorted(missing_tables)}. "
                    f"Unexpected tables: {sorted(unexpected_tables)}. "
                    "Automatic repair refused to prevent data corruption. A narrowly scoped repair must be proposed."
                )

    # Step 2: Create pre-migration backup before modifying database
    target_path = db_path or settings.SQLITE_DB_PATH
    if target_path and target_path != ":memory:":
        create_backup(target_path)

    # Step 3: Execute migration according to decision
    backend_dir = Path(__file__).resolve().parent.parent.parent
    ini_path = backend_dir / "alembic.ini"
    migrations_dir = backend_dir / "app" / "database" / "migrations"

    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(migrations_dir))
    cfg.set_main_option("path_separator", "os")

    with target_engine.begin() as conn:
        cfg.attributes["connection"] = conn
        if decision == "v010_legacy_stamp_and_upgrade":
            # Verified legacy baseline: stamp 0001, then upgrade to head
            command.stamp(cfg, "0001_initial_schema")
            command.upgrade(cfg, "head")
        else:
            # Brand-new empty DB or versioned DB at older revision: upgrade to head
            command.upgrade(cfg, "head")


def run_idempotent_backfill(session: Session) -> dict[str, int]:
    """Backfill existing unlinked Video rows into Asset, AssetVersion, and AssetLocation.

    Guarantees idempotence: running again backfills 0 rows.
    """
    unlinked_videos = session.query(Video).filter(Video.asset_id.is_(None)).all()
    if not unlinked_videos:
        return {"assets": 0, "versions": 0, "locations": 0}

    # Ensure default Library exists
    default_library = session.query(Library).filter_by(label="Default Library").first()
    if not default_library:
        default_library = Library(
            id=str(uuid.uuid4()),
            label="Default Library",
            execution_profile=ExecutionProfile.FULLY_OFFLINE_NO_AI.value,
        )
        session.add(default_library)
        session.flush()

    # Ensure default LibraryRoot exists
    default_root = session.query(LibraryRoot).filter_by(library_id=default_library.id, label="Default Root").first()
    if not default_root:
        default_root = LibraryRoot(
            id=str(uuid.uuid4()),
            library_id=default_library.id,
            label="Default Root",
            root_type=RootType.LOCAL_FIXED.value,
            policy=RootPolicy.LOCAL_ONLY.value,
            status="active",
        )
        session.add(default_root)
        session.flush()

    assets_count = 0
    versions_count = 0
    locations_count = 0

    for vid in unlinked_videos:
        # Create Asset
        asset = Asset(
            id=vid.id,
            created_at=vid.created_at,
        )
        session.add(asset)
        session.flush()

        # Create AssetVersion
        media_meta = json.dumps(
            {
                "duration": vid.duration,
                "width": vid.width,
                "height": vid.height,
                "fps": vid.fps,
                "codec": vid.codec,
                "format": vid.format,
            }
        )
        version = AssetVersion(
            id=str(uuid.uuid4()),
            asset_id=asset.id,
            sha256=None,  # Nullable while unverified per Task 4 specification
            size_bytes=vid.file_size,
            media_meta=media_meta,
            identity_state=IdentityState.IDENTITY_UNVERIFIED.value,
            created_at=vid.created_at,
        )
        session.add(version)
        session.flush()

        asset.current_version_id = version.id

        # Create AssetLocation
        location = AssetLocation(
            id=str(uuid.uuid4()),
            version_id=version.id,
            root_id=default_root.id,
            rel_path=vid.filename,
            rel_path_norm=vid.filename.strip().lower(),
            last_seen_at=vid.created_at,
            availability=LocationAvailability.AVAILABLE.value,
        )
        session.add(location)

        # Bridge back to Video
        vid.asset_id = asset.id
        vid.version_id = version.id

        assets_count += 1
        versions_count += 1
        locations_count += 1

    session.commit()
    return {"assets": assets_count, "versions": versions_count, "locations": locations_count}


def supersede_artifact(session: Session, new_artifact: Artifact) -> None:
    """Atomically supersede an existing artifact of the same version_id and kind."""
    session.query(Artifact).filter(
        Artifact.version_id == new_artifact.version_id,
        Artifact.kind == new_artifact.kind,
        Artifact.is_current.is_(True),
    ).update({"is_current": False})

    new_artifact.is_current = True
    session.add(new_artifact)
    session.commit()


def check_remote_processing_permission(
    library: Library,
    root: LibraryRoot,
    provider: str,
    endpoint_host: str,
    capability: str,
    data_categories: list[str],
    consents: list[AIConsent],
    provider_available: bool = True,
    current_budget_spent: float = 0.0,
) -> tuple[bool, CapabilityReason | None]:
    """Evaluate effective remote-processing permission based on mandatory 5-gate precedence.

    Returns (True, None) if permitted; otherwise (False, CapabilityReason).
    """
    # Gate 1: Library Execution Profile
    if library.execution_profile not in (ExecutionProfile.BYOK_REMOTE_AI.value, ExecutionProfile.HYBRID_AI.value):
        return False, CapabilityReason.REMOTE_NOT_ALLOWED

    # Gate 2: Root Policy
    if root.policy != RootPolicy.ALLOW_REMOTE.value:
        return False, CapabilityReason.PRIVACY_POLICY_BLOCKED

    # Gate 3: Active, unexpired, unrevoked consent
    now = datetime.now(timezone.utc)
    matching_consent = None
    for c in consents:
        if c.revoked_at is not None:
            continue
        if c.expires_at is not None and c.expires_at <= now:
            continue
        if c.provider != provider or c.endpoint_host.strip().lower() != endpoint_host.strip().lower():
            continue

        try:
            caps = json.loads(c.capabilities)
            cats = json.loads(c.data_categories)
        except Exception:
            continue

        if capability not in caps:
            continue
        if not all(cat in cats for cat in data_categories):
            continue

        matching_consent = c
        break

    if matching_consent is None:
        return False, CapabilityReason.CONSENT_REQUIRED

    # Gate 4: Provider capability validated & available
    if not provider_available:
        return False, CapabilityReason.PROVIDER_UNAVAILABLE

    # Gate 5: Budget limit check
    if matching_consent.budget_limit is not None and current_budget_spent >= matching_consent.budget_limit:
        return False, CapabilityReason.DISABLED_BY_USER

    return True, None
