"""Stage 4A Unit and Integration Tests: Schema, State Machine, and Migration.

Verifies:
1. Deterministic version identity (UUIDv5 with fixed namespace and lowercase SHA-256).
2. Schema migration from pre-Task-4 DB preserving all rows table-by-table.
3. Baseline stamping for unversioned databases and idempotent re-migration.
4. Pre-migration backup creation, verify, and restore.
5. Unique constraints (partial unique SHA-256, location uniqueness, alias uniqueness).
6. Atomic artifact superseding.
7. Remote processing 5-gate permission precedence (most restrictive wins).
8. Schema operations run in clean offline mode without importing optional AI packages.
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import sys
import uuid

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.migrator import (
    SchemaStateError,
    check_remote_processing_permission,
    create_backup,
    restore_backup,
    run_database_migrations,
    run_idempotent_backfill,
    supersede_artifact,
)
from app.database.session import Base
from app.models.entities import (
    AIConsent,
    AIRun,
    Annotation,
    Artifact,
    Asset,
    AssetLocation,
    AssetRelation,
    AssetVersion,
    Collection,
    CollectionVideo,
    EmbeddingRecord,
    IDAlias,
    Library,
    LibraryRoot,
    Moment,
    ProcessingJob,
    ScanRun,
    StageRun,
    Transcript,
    TranscriptSegment,
    Video,
    VideoScene,
    VideoSummary,
)
from app.models.enums import (
    CapabilityReason,
    ExecutionProfile,
    IdentityState,
    LocationAvailability,
    NAMESPACE_AROVA_VERSION,
    RootPolicy,
    RootType,
    compute_deterministic_version_id,
)


def test_deterministic_uuidv5_version_identity() -> None:
    # 1. Deterministic repeatability for same SHA-256
    sha1 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    id1 = compute_deterministic_version_id(sha1)
    id2 = compute_deterministic_version_id(sha1)
    assert id1 == id2
    assert uuid.UUID(id1).version == 5

    # 2. Case normalization (uppercase vs lowercase yields identical UUID)
    id_upper = compute_deterministic_version_id(sha1.upper())
    assert id_upper == id1

    # 3. Different SHA yields different UUID
    sha2 = "efa9062d9cdb7a338e40ad530dfdf234806743f29ae6a1a136b97ece4e588e8f"
    id_diff = compute_deterministic_version_id(sha2)
    assert id_diff != id1

    # 4. Independent process math match
    expected_uuid = str(uuid.uuid5(NAMESPACE_AROVA_VERSION, sha1.lower()))
    assert id1 == expected_uuid

    # 5. Invalid SHA length raises ValueError
    with pytest.raises(ValueError, match="Invalid SHA-256 digest"):
        compute_deterministic_version_id("too_short")


def test_migration_preserves_pre_task4_rows(tmp_path: Path) -> None:
    db_file = tmp_path / "legacy_pre_task4.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(db_url)

    # 1. Build baseline DB using 0001_initial_schema
    from alembic import command
    from app.database.migrator import _get_alembic_config

    with engine.begin() as conn:
        cfg = _get_alembic_config(engine)
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "0001_initial_schema")

    # 2. Populate baseline rows across all 9 pre-Task-4 tables using raw SQL
    # (avoiding ORM Video model which expects post-Task-4 columns asset_id, version_id)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO videos (id, filename, file_path, file_hash, file_size, duration, width, height, fps, codec, format, processing_status, created_at) "
                "VALUES ('v1-legacy-uuid', 'lecture.mp4', :path, 'hash123', 10240, 42.0, 1920, 1080, 30.0, 'h264', 'mp4', 'completed', '2026-11-01 10:00:00')"
            ),
            {"path": str(tmp_path / "lecture.mp4")},
        )
        conn.execute(
            text("INSERT INTO collections (id, name, created_at) VALUES ('c1-uuid', 'Spring 2026 Lectures', '2026-11-01 10:00:00')")
        )
        conn.execute(
            text("INSERT INTO collection_videos (collection_id, video_id) VALUES ('c1-uuid', 'v1-legacy-uuid')")
        )
        conn.execute(
            text("INSERT INTO transcripts (id, video_id, language, model_name, full_text, created_at) VALUES ('tr1-uuid', 'v1-legacy-uuid', 'en', 'whisper', 'Hello world', '2026-11-01 10:00:00')")
        )
        conn.execute(
            text("INSERT INTO transcript_segments (id, transcript_id, video_id, start_time, end_time, text) VALUES ('seg1-uuid', 'tr1-uuid', 'v1-legacy-uuid', 0.0, 5.0, 'Hello world')")
        )
        conn.execute(
            text("INSERT INTO video_scenes (id, video_id, scene_index, start_time, end_time) VALUES ('sc1-uuid', 'v1-legacy-uuid', 1, 0.0, 10.0)")
        )
        conn.execute(
            text("INSERT INTO embedding_records (id, video_id, chunk_text, start_time, end_time, embedding_id, model_name, created_at) VALUES ('em1-uuid', 'v1-legacy-uuid', 'Hello world', 0.0, 5.0, 'emb-001', 'minilm', '2026-11-01 10:00:00')")
        )
        conn.execute(
            text("INSERT INTO video_summaries (id, video_id, summary_text, topics_json, chapters_json, model_name, created_at) VALUES ('sm1-uuid', 'v1-legacy-uuid', 'Lecture overview', '[]', '[]', 'extractive', '2026-11-01 10:00:00')")
        )
        conn.execute(
            text("INSERT INTO processing_jobs (id, video_id, job_type, status, progress, created_at) VALUES ('jb1-uuid', 'v1-legacy-uuid', 'full_pipeline', 'completed', 1.0, '2026-11-01 10:00:00')")
        )

    # Record row counts before migration using raw SQL
    with engine.connect() as conn:
        counts_before = {
            "videos": conn.execute(text("SELECT count(*) FROM videos")).scalar(),
            "collections": conn.execute(text("SELECT count(*) FROM collections")).scalar(),
            "collection_videos": conn.execute(text("SELECT count(*) FROM collection_videos")).scalar(),
            "transcripts": conn.execute(text("SELECT count(*) FROM transcripts")).scalar(),
            "transcript_segments": conn.execute(text("SELECT count(*) FROM transcript_segments")).scalar(),
            "video_scenes": conn.execute(text("SELECT count(*) FROM video_scenes")).scalar(),
            "embedding_records": conn.execute(text("SELECT count(*) FROM embedding_records")).scalar(),
            "video_summaries": conn.execute(text("SELECT count(*) FROM video_summaries")).scalar(),
            "processing_jobs": conn.execute(text("SELECT count(*) FROM processing_jobs")).scalar(),
        }

    # 3. Execute Task 4 migration and backfill
    run_database_migrations(engine=engine, db_path=db_file)
    SessionMaker = sessionmaker(bind=engine)
    with SessionMaker() as session:
        backfill_res = run_idempotent_backfill(session)

    assert backfill_res["assets"] == 1
    assert backfill_res["versions"] == 1
    assert backfill_res["locations"] == 1

    # Record row counts after migration table-by-table
    with SessionMaker() as session:
        counts_after = {
            "videos": session.query(Video).count(),
            "collections": session.query(Collection).count(),
            "collection_videos": session.query(CollectionVideo).count(),
            "transcripts": session.query(Transcript).count(),
            "transcript_segments": session.query(TranscriptSegment).count(),
            "video_scenes": session.query(VideoScene).count(),
            "embedding_records": session.query(EmbeddingRecord).count(),
            "video_summaries": session.query(VideoSummary).count(),
            "processing_jobs": session.query(ProcessingJob).count(),
        }

        # Assert every single baseline row is 100% preserved
        assert counts_before == counts_after

        # Verify backfilled Asset and Version relationships
        migrated_vid = session.query(Video).filter_by(id="v1-legacy-uuid").one()
        assert migrated_vid.asset_id == "v1-legacy-uuid"
        assert migrated_vid.version_id is not None

        asset = session.query(Asset).filter_by(id=migrated_vid.asset_id).one()
        assert asset.current_version_id == migrated_vid.version_id

        version = session.query(AssetVersion).filter_by(id=migrated_vid.version_id).one()
        assert version.identity_state == IdentityState.IDENTITY_UNVERIFIED.value
        assert version.sha256 is None  # Nullable while unverified per spec
        assert version.size_bytes == 10240

        loc = session.query(AssetLocation).filter_by(version_id=version.id).one()
        assert loc.rel_path == "lecture.mp4"
        assert loc.availability == LocationAvailability.AVAILABLE.value

        # 4. Rerun backfill: must be a strict no-op (idempotence)
        rerun_res = run_idempotent_backfill(session)
        assert rerun_res == {"assets": 0, "versions": 0, "locations": 0}


def test_stamping_and_idempotent_migration(tmp_path: Path) -> None:
    db_file = tmp_path / "unversioned_db.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(db_url)

    # 1. Simulate database created via create_all without alembic_version table
    from alembic import command
    from app.database.migrator import _get_alembic_config

    with engine.begin() as conn:
        cfg = _get_alembic_config(engine)
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "0001_initial_schema")
        # Drop alembic_version to simulate legacy unversioned DB
        conn.execute(text("DROP TABLE alembic_version"))

    # Verify alembic_version is absent but videos is present
    inspector = inspect(engine)
    assert "alembic_version" not in inspector.get_table_names()
    assert "videos" in inspector.get_table_names()

    # 2. Run migration: should detect unversioned DB, stamp 0001, and upgrade to head
    run_database_migrations(engine=engine, db_path=db_file)

    inspector = inspect(engine)
    assert "alembic_version" in inspector.get_table_names()
    assert "libraries" in inspector.get_table_names()
    assert "asset_versions" in inspector.get_table_names()

    # 3. Second run must be a clean no-op
    run_database_migrations(engine=engine, db_path=db_file)


def test_pre_migration_backup_and_restore(tmp_path: Path) -> None:
    db_file = tmp_path / "live_db.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")

    # Populate a test table
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE test_data (id INT, val TEXT)"))
        conn.execute(text("INSERT INTO test_data VALUES (1, 'initial')"))

    # Create backup
    backup_path = create_backup(db_file)
    assert backup_path is not None
    assert backup_path.is_file()
    assert backup_path.stat().st_size > 0

    # Mutate source database
    with engine.begin() as conn:
        conn.execute(text("UPDATE test_data SET val = 'mutated'"))

    # Close/dispose pool connections on Windows before overwriting file
    engine.dispose()

    # Restore from backup
    restore_backup(backup_path, db_file)

    # Verify restored state
    engine_restored = create_engine(f"sqlite:///{db_file.as_posix()}")
    with engine_restored.connect() as conn:
        val = conn.execute(text("SELECT val FROM test_data WHERE id = 1")).scalar()
        assert val == "initial"
    engine_restored.dispose()


def test_asset_version_sha256_constraints() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    run_database_migrations(engine=engine)
    SessionMaker = sessionmaker(bind=engine)

    with SessionMaker() as session:
        asset = Asset(id="ast-c1")
        session.add(asset)
        session.commit()

        # 1. Multiple AssetVersions with sha256=None are allowed (legacy unverified versions)
        v1 = AssetVersion(id="v1", asset_id=asset.id, sha256=None, identity_state="identity_unverified")
        v2 = AssetVersion(id="v2", asset_id=asset.id, sha256=None, identity_state="identity_unverified")
        session.add_all([v1, v2])
        session.commit()

        # 2. Duplicate non-null SHA-256 raises IntegrityError
        v3 = AssetVersion(id="v3", asset_id=asset.id, sha256="abc123sha", identity_state="verified")
        session.add(v3)
        session.commit()

        v4 = AssetVersion(id="v4", asset_id=asset.id, sha256="abc123sha", identity_state="verified")
        session.add(v4)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_asset_location_uniqueness() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    run_database_migrations(engine=engine)
    SessionMaker = sessionmaker(bind=engine)

    with SessionMaker() as session:
        lib = Library(id="lib1", label="Test Lib")
        root = LibraryRoot(id="root1", library_id=lib.id, label="Root")
        asset = Asset(id="a1")
        v = AssetVersion(id="v1", asset_id=asset.id, identity_state="verified")
        session.add_all([lib, root, asset, v])
        session.commit()

        loc1 = AssetLocation(id="loc1", version_id=v.id, root_id=root.id, rel_path="video.mp4", rel_path_norm="video.mp4")
        session.add(loc1)
        session.commit()

        # Duplicate (root_id, rel_path_norm) violates uniqueness
        loc2 = AssetLocation(id="loc2", version_id=v.id, root_id=root.id, rel_path="VIDEO.mp4", rel_path_norm="video.mp4")
        session.add(loc2)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_id_alias_uniqueness_rules() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    run_database_migrations(engine=engine)
    SessionMaker = sessionmaker(bind=engine)

    with SessionMaker() as session:
        # 1. Local legacy remap (source_export_id is None)
        alias1 = IDAlias(entity_type="version", foreign_id="legacy-001", local_id="det-001", source_export_id=None)
        session.add(alias1)
        session.commit()

        # Duplicate local remap violates partial unique index
        alias2 = IDAlias(entity_type="version", foreign_id="legacy-001", local_id="det-002", source_export_id=None)
        session.add(alias2)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        # 2. Export-scoped remap
        alias3 = IDAlias(entity_type="asset", foreign_id="f-asset-1", local_id="l-asset-1", source_export_id="export-A")
        session.add(alias3)
        session.commit()

        # Same foreign_id under a DIFFERENT source_export_id is permitted
        alias4 = IDAlias(entity_type="asset", foreign_id="f-asset-1", local_id="l-asset-2", source_export_id="export-B")
        session.add(alias4)
        session.commit()

        # Duplicate under SAME source_export_id violates unique index
        alias5 = IDAlias(entity_type="asset", foreign_id="f-asset-1", local_id="l-asset-3", source_export_id="export-A")
        session.add(alias5)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_artifact_atomic_supersede() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    run_database_migrations(engine=engine)
    SessionMaker = sessionmaker(bind=engine)

    with SessionMaker() as session:
        asset = Asset(id="ast-art")
        version = AssetVersion(id="ver-art", asset_id=asset.id)
        session.add_all([asset, version])
        session.commit()

        art1 = Artifact(
            id="art1",
            version_id=version.id,
            kind="transcript",
            producer_stage="asr",
            producer_model="whisper-base",
            is_current=True,
        )
        session.add(art1)
        session.commit()

        # Supersede with art2
        art2 = Artifact(
            id="art2",
            version_id=version.id,
            kind="transcript",
            producer_stage="asr",
            producer_model="whisper-large",
        )
        supersede_artifact(session, art2)

        # Verify art1 is no longer current and art2 is current
        refreshed_art1 = session.query(Artifact).filter_by(id="art1").one()
        refreshed_art2 = session.query(Artifact).filter_by(id="art2").one()
        assert refreshed_art1.is_current is False
        assert refreshed_art2.is_current is True

        # Exactly one current artifact exists for this kind
        current_count = session.query(Artifact).filter_by(version_id=version.id, kind="transcript", is_current=True).count()
        assert current_count == 1


def test_remote_processing_permission_precedence() -> None:
    now = datetime.now(timezone.utc)
    lib = Library(id="lib1", label="Studio", execution_profile=ExecutionProfile.FULLY_OFFLINE_NO_AI.value)
    root = LibraryRoot(id="root1", library_id=lib.id, label="Local Root", policy=RootPolicy.LOCAL_ONLY.value)

    consent = AIConsent(
        id="c1",
        scope_type="library",
        scope_id=lib.id,
        provider="google-gemini",
        endpoint_host="generativelanguage.googleapis.com",
        data_categories=json.dumps(["transcript"]),
        capabilities=json.dumps(["summarization"]),
        budget_limit=10.0,
        granted_at=now,
    )

    # Gate 1: Profile is FULLY_OFFLINE_NO_AI -> denies egress
    ok, reason = check_remote_processing_permission(
        library=lib,
        root=root,
        provider="google-gemini",
        endpoint_host="generativelanguage.googleapis.com",
        capability="summarization",
        data_categories=["transcript"],
        consents=[consent],
    )
    assert ok is False
    assert reason == CapabilityReason.REMOTE_NOT_ALLOWED

    # Gate 2: Root policy is LOCAL_ONLY -> denies egress even if profile allows
    lib.execution_profile = ExecutionProfile.BYOK_REMOTE_AI.value
    ok, reason = check_remote_processing_permission(
        library=lib,
        root=root,
        provider="google-gemini",
        endpoint_host="generativelanguage.googleapis.com",
        capability="summarization",
        data_categories=["transcript"],
        consents=[consent],
    )
    assert ok is False
    assert reason == CapabilityReason.PRIVACY_POLICY_BLOCKED

    # Gate 3: Active consent required (revoked consent)
    root.policy = RootPolicy.ALLOW_REMOTE.value
    consent.revoked_at = now
    ok, reason = check_remote_processing_permission(
        library=lib,
        root=root,
        provider="google-gemini",
        endpoint_host="generativelanguage.googleapis.com",
        capability="summarization",
        data_categories=["transcript"],
        consents=[consent],
    )
    assert ok is False
    assert reason == CapabilityReason.CONSENT_REQUIRED

    # Gate 4: Provider unavailable
    consent.revoked_at = None
    ok, reason = check_remote_processing_permission(
        library=lib,
        root=root,
        provider="google-gemini",
        endpoint_host="generativelanguage.googleapis.com",
        capability="summarization",
        data_categories=["transcript"],
        consents=[consent],
        provider_available=False,
    )
    assert ok is False
    assert reason == CapabilityReason.PROVIDER_UNAVAILABLE

    # Gate 5: Budget exceeded
    ok, reason = check_remote_processing_permission(
        library=lib,
        root=root,
        provider="google-gemini",
        endpoint_host="generativelanguage.googleapis.com",
        capability="summarization",
        data_categories=["transcript"],
        consents=[consent],
        provider_available=True,
        current_budget_spent=15.0,
    )
    assert ok is False
    assert reason == CapabilityReason.DISABLED_BY_USER

    # All gates passed: positive authorization
    ok, reason = check_remote_processing_permission(
        library=lib,
        root=root,
        provider="google-gemini",
        endpoint_host="generativelanguage.googleapis.com",
        capability="summarization",
        data_categories=["transcript"],
        consents=[consent],
        provider_available=True,
        current_budget_spent=5.0,
    )
    assert ok is True
    assert reason is None


def test_schema_offline_isolation_no_ai_imports() -> None:
    # Ensure heavy AI packages are not imported by the schema/migration system
    forbidden = ["torch", "faster_whisper", "sentence_transformers", "nemo", "onnxruntime"]
    loaded = [pkg for pkg in forbidden if pkg in sys.modules]
    assert len(loaded) == 0, f"Schema module illegally imported AI packages: {loaded}"


def test_migration_partially_initialized_legacy_db_raises_diagnostic(tmp_path: Path) -> None:
    """Test unversioned database with partial pre-Task-4 tables stops with SchemaStateError diagnostic."""
    db_file = tmp_path / "partial_legacy.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")

    # Setup unversioned database with only videos table (missing 8 other baseline tables)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE videos ("
                "id TEXT PRIMARY KEY, filename TEXT NOT NULL, file_path TEXT NOT NULL, "
                "file_hash TEXT NOT NULL, file_size INT NOT NULL, duration REAL NOT NULL, "
                "width INT NOT NULL, height INT NOT NULL, fps REAL NOT NULL, codec TEXT NOT NULL, "
                "format TEXT NOT NULL, thumbnail_path TEXT, processing_status TEXT NOT NULL, "
                "created_at TEXT NOT NULL)"
            )
        )

    # Attempt migration: must raise SchemaStateError and refuse to silently repair
    with pytest.raises(SchemaStateError, match="Partial, malformed, or unexpected schema detected"):
        run_database_migrations(engine=engine, db_path=db_file)
    engine.dispose()


def test_migration_malformed_legacy_db_missing_columns(tmp_path: Path) -> None:
    """Test unversioned database with malformed table schema stops with SchemaStateError."""
    db_file = tmp_path / "malformed_legacy.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")

    # Create all 9 baseline table names, but videos is missing required columns
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE videos (id TEXT PRIMARY KEY, filename TEXT NOT NULL)"))
        conn.execute(text("CREATE TABLE collections (id TEXT PRIMARY KEY, name TEXT NOT NULL)"))
        conn.execute(text("CREATE TABLE collection_videos (id INT PRIMARY KEY, collection_id TEXT, video_id TEXT)"))
        conn.execute(text("CREATE TABLE transcripts (id TEXT PRIMARY KEY, video_id TEXT)"))
        conn.execute(text("CREATE TABLE transcript_segments (id TEXT PRIMARY KEY, video_id TEXT)"))
        conn.execute(text("CREATE TABLE video_scenes (id TEXT PRIMARY KEY, video_id TEXT)"))
        conn.execute(text("CREATE TABLE embedding_records (id TEXT PRIMARY KEY, video_id TEXT)"))
        conn.execute(text("CREATE TABLE video_summaries (id TEXT PRIMARY KEY, video_id TEXT)"))
        conn.execute(text("CREATE TABLE processing_jobs (id TEXT PRIMARY KEY, video_id TEXT)"))

    with pytest.raises(SchemaStateError, match="missing required columns"):
        run_database_migrations(engine=engine, db_path=db_file)
    engine.dispose()


def test_migration_brand_new_empty_db(tmp_path: Path) -> None:
    """Test brand-new empty database runs Alembic from base revision through head without stamping first."""
    db_file = tmp_path / "fresh_empty.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")

    # Verify initially 0 application tables
    insp = inspect(engine)
    assert len(insp.get_table_names()) == 0

    run_database_migrations(engine=engine, db_path=db_file)

    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert "alembic_version" in tables
    assert "videos" in tables
    assert "libraries" in tables
    assert "asset_versions" in tables

    # Verify PRAGMA integrity_check
    with engine.connect() as conn:
        res = conn.execute(text("PRAGMA integrity_check;")).fetchall()
        assert res == [("ok",)]
    engine.dispose()


def test_migration_schema_zero_rows_handled_correctly(tmp_path: Path) -> None:
    """Test existing schema with zero rows upgrades according to its actual migration state."""
    db_file = tmp_path / "zero_rows_schema.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")

    from alembic import command
    from app.database.migrator import _get_alembic_config

    # Setup versioned DB at 0001 with zero rows
    cfg = _get_alembic_config(engine)
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "0001_initial_schema")

    # Confirm zero rows in videos
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM videos")).scalar() == 0

    # Migrate to head
    run_database_migrations(engine=engine, db_path=db_file)

    insp = inspect(engine)
    assert "libraries" in insp.get_table_names()
    with engine.connect() as conn:
        rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert rev in ("0002_task4_media_memory", "0003_indic_fts5_tokenization")
        assert conn.execute(text("PRAGMA integrity_check;")).fetchall() == [("ok",)]
    engine.dispose()


def test_migration_downgrade_and_reupgrade(tmp_path: Path) -> None:
    """Test full cycle: upgrade head -> downgrade 0001 -> downgrade base -> upgrade head."""
    db_file = tmp_path / "cycle_test.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")

    from alembic import command
    from app.database.migrator import _get_alembic_config

    cfg = _get_alembic_config(engine)

    # 1. Upgrade to head
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")

    insp = inspect(engine)
    assert "libraries" in insp.get_table_names()
    assert "videos" in insp.get_table_names()
    video_cols = {c["name"] for c in insp.get_columns("videos")}
    assert "asset_id" in video_cols

    # 2. Downgrade to 0001_initial_schema
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.downgrade(cfg, "0001_initial_schema")

    insp = inspect(engine)
    assert "libraries" not in insp.get_table_names()
    assert "videos" in insp.get_table_names()
    video_cols = {c["name"] for c in insp.get_columns("videos")}
    assert "asset_id" not in video_cols

    # 3. Downgrade to base
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.downgrade(cfg, "base")

    insp = inspect(engine)
    assert "videos" not in insp.get_table_names()
    assert "libraries" not in insp.get_table_names()

    # 4. Re-upgrade back to head
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")

    insp = inspect(engine)
    assert "videos" in insp.get_table_names()
    assert "libraries" in insp.get_table_names()
    engine.dispose()


def test_sqlite_wal_backup_and_restore_integrity(tmp_path: Path) -> None:
    """Verify backup and restore under active SQLite WAL mode with uncheckpointed data."""
    db_file = tmp_path / "wal_mode_test.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("CREATE TABLE wal_items (id INT PRIMARY KEY, name TEXT);")
    conn.execute("INSERT INTO wal_items VALUES (1, 'initial_entry');")
    conn.commit()
    conn.close()

    # Create backup with online API
    backup_file = create_backup(db_file)
    assert backup_file is not None
    assert backup_file.is_file()

    # Verify backup integrity check
    b_conn = sqlite3.connect(str(backup_file))
    b_check = b_conn.execute("PRAGMA integrity_check;").fetchall()
    assert b_check == [("ok",)]
    b_val = b_conn.execute("SELECT name FROM wal_items WHERE id = 1;").fetchone()[0]
    assert b_val == "initial_entry"
    b_conn.close()

    # Mutate source in WAL mode
    conn = sqlite3.connect(str(db_file))
    conn.execute("UPDATE wal_items SET name = 'mutated_in_wal' WHERE id = 1;")
    conn.commit()
    conn.close()

    # Restore from backup
    restore_backup(backup_file, db_file)

    # Verify source database integrity and data restored
    v_conn = sqlite3.connect(str(db_file))
    v_check = v_conn.execute("PRAGMA integrity_check;").fetchall()
    assert v_check == [("ok",)]
    v_val = v_conn.execute("SELECT name FROM wal_items WHERE id = 1;").fetchone()[0]
    assert v_val == "initial_entry"
    v_conn.close()


def test_database_init_skips_redundant_backups_when_at_head(tmp_path: Path) -> None:
    """Verify database init does not repeatedly write backup files when already at head."""
    db_file = tmp_path / "app_live.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")

    # First run: performs migration and creates backup
    run_database_migrations(engine=engine, db_path=db_file)

    # Count backup files created
    backups_first = list(tmp_path.glob("*.backup.*"))

    # Second run: database is already at head
    run_database_migrations(engine=engine, db_path=db_file)
    backups_second = list(tmp_path.glob("*.backup.*"))

    assert len(backups_second) == len(backups_first)
    engine.dispose()
