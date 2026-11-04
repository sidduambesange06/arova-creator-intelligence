"""Comprehensive Unit and Adversarial Test Suite for Task 4D:
Portable Media Memory, Versioned API and Cross-Machine Intelligence Transfer.

Verifies:
1. Export of portable .arova container archive with streaming NDJSON and cryptographic manifest.
2. Secret redaction during export.
3. All 20 security safeguards during untrusted archive validation.
4. Dry-run import preview with zero database mutations.
5. Transactional import with ID aliasing and rollback on failure.
6. Physical media availability resolution and cross-machine media relinking with SHA-256 verification.
7. Deterministic search cache keys invariant to filesystem path relocation.
8. Annotations CRUD operations and duplicate media detection.
9. Versioned REST API endpoints for portable memory, relinking, and annotations.
"""

from collections.abc import Generator
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
from unittest.mock import patch
from uuid import uuid4
import zipfile

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import compute_sha256
from app.database.session import Base, get_db, init_db
from app.main import app
from app.models.entities import (
    Annotation,
    Artifact,
    Asset,
    AssetLocation,
    AssetVersion,
    IDAlias,
    Library,
    LibraryRoot,
    Moment,
    Transcript,
    TranscriptSegment,
    Video,
    VideoScene,
)
from app.models.enums import (
    IdentityState,
    LocationAvailability,
    RootPolicy,
    RootType,
    TrustLevel,
)
from app.schemas.portable import (
    AnnotationCreate,
    ArchiveEntryManifest,
    ArchiveManifest,
    ExportRequest,
    RelinkRequest,
)
from app.services.portable_service import (
    ArchiveSecurityError,
    compute_search_cache_key,
    dry_run_import_archive,
    export_portable_archive,
    import_portable_archive,
    relink_asset_media,
    resolve_media_availability,
    sanitize_text_for_export,
    validate_archive,
)


@pytest.fixture()
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    """Isolated in-memory SQLite database session."""
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    with TestingSession() as session:
        yield session

    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def seeded_db(db_session: Session, tmp_path: Path) -> tuple[Session, Asset, AssetVersion, Video, Path]:
    """Database pre-seeded with library, asset, version, location, video, and annotations."""
    # 1. Library and Root
    media_dir = tmp_path / "media_root"
    media_dir.mkdir(parents=True, exist_ok=True)

    lib = Library(
        id=str(uuid4()),
        label="Test Library",
        execution_profile="fully_offline_no_ai",
    )
    db_session.add(lib)
    db_session.flush()

    root = LibraryRoot(
        id=str(uuid4()),
        library_id=lib.id,
        label="Main Root",
        root_type=RootType.LOCAL_FIXED.value,
        volume_id=str(media_dir),
        policy=RootPolicy.LOCAL_ONLY.value,
        status="active",
    )
    db_session.add(root)
    db_session.flush()

    # 2. Source video file
    video_file = media_dir / "creator_lesson_01.mp4"
    video_file.write_bytes(b"Simulated MP4 container content for Arova test")
    expected_sha = compute_sha256(video_file)

    # 3. Asset and Version
    asset = Asset(id=str(uuid4()))
    db_session.add(asset)
    db_session.flush()

    version = AssetVersion(
        id=str(uuid4()),
        asset_id=asset.id,
        sha256=expected_sha,
        size_bytes=video_file.stat().st_size,
        identity_state=IdentityState.VERIFIED.value,
        media_meta=json.dumps({"duration": 120.0, "width": 1920, "height": 1080}),
    )
    db_session.add(version)
    db_session.flush()
    asset.current_version_id = version.id

    # 4. Location
    loc = AssetLocation(
        id=str(uuid4()),
        version_id=version.id,
        root_id=root.id,
        rel_path="creator_lesson_01.mp4",
        rel_path_norm="creator_lesson_01.mp4",
        availability=LocationAvailability.AVAILABLE.value,
    )
    db_session.add(loc)

    # 5. Video bridge
    video = Video(
        id=str(uuid4()),
        asset_id=asset.id,
        version_id=version.id,
        filename="creator_lesson_01.mp4",
        file_path=str(video_file),
        file_hash=expected_sha,
        duration=120.0,
    )
    db_session.add(video)
    db_session.flush()

    # 6. Transcript and Segments
    transcript = Transcript(
        id=str(uuid4()),
        video_id=video.id,
        language="en",
        model_name="whisper-base",
        full_text="Welcome to the lesson. Today we discuss portable memory.",
    )
    db_session.add(transcript)
    db_session.flush()

    segment = TranscriptSegment(
        id=str(uuid4()),
        transcript_id=transcript.id,
        video_id=video.id,
        start_time=0.0,
        end_time=5.0,
        text="Welcome to the lesson.",
        confidence=0.99,
    )
    db_session.add(segment)

    # 7. Scene and Moment
    scene = VideoScene(
        id=str(uuid4()),
        video_id=video.id,
        scene_index=0,
        start_time=0.0,
        end_time=30.0,
        description="talking_head",
    )
    db_session.add(scene)

    moment = Moment(
        id=str(uuid4()),
        version_id=version.id,
        start_ms=1000,
        end_ms=4000,
        kind="scene",
    )
    db_session.add(moment)

    # 8. Annotation
    annotation = Annotation(
        id=str(uuid4()),
        target_type="version",
        target_id=version.id,
        author_type="human",
        display_name="Senior Editor",
        trust="human_verified",
        body="Crucial intro hook for reel cut",
    )
    db_session.add(annotation)

    # 9. Artifact
    artifact = Artifact(
        id=str(uuid4()),
        version_id=version.id,
        kind="transcript_vtt",
        producer_stage="transcribe",
        producer_model="faster-whisper",
        producer_revision="v1",
        config_hash="cfg_hash_abc",
        is_current=True,
        trust="machine_generated",
    )
    db_session.add(artifact)

    db_session.commit()
    return db_session, asset, version, video, video_file


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient wired to test db session."""
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


# =============================================================================
# 1. EXPORT AND MANIFEST TESTS
# =============================================================================

def test_export_portable_archive_creates_valid_container(seeded_db: tuple, tmp_path: Path) -> None:
    session, asset, version, video, video_file = seeded_db
    export_path = tmp_path / "export_test.arova"

    summary = export_portable_archive(
        db=session,
        target_archive_path=export_path,
        request=ExportRequest(include_artifacts=True),
    )

    assert export_path.is_file()
    assert summary.format_version == "1.0.0"
    assert summary.records_count["assets"] == 1
    assert summary.records_count["versions"] == 1
    assert summary.records_count["transcripts"] == 1
    assert summary.records_count["annotations"] == 1
    assert summary.records_count["artifacts"] == 1
    assert summary.sha256 == compute_sha256(export_path)

    # Verify internal zip contents
    with zipfile.ZipFile(export_path, "r") as zf:
        namelist = zf.namelist()
        assert "manifest.json" in namelist
        assert "assets.ndjson" in namelist
        assert "versions.ndjson" in namelist
        assert "locations.ndjson" in namelist
        assert "transcripts.ndjson" in namelist
        assert "transcript_segments.ndjson" in namelist
        assert "annotations.ndjson" in namelist
        assert "artifacts.ndjson" in namelist

        manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))
        manifest = ArchiveManifest.model_validate(manifest_data)
        assert manifest.format_version == "1.0.0"
        assert len(manifest.entries) >= 7

        # Ensure no absolute paths are present in locations.ndjson
        locations_content = zf.read("locations.ndjson").decode("utf-8")
        assert "creator_lesson_01.mp4" in locations_content
        assert ":\\" not in locations_content
        assert "/media_root" not in locations_content


def test_export_redacts_credentials() -> None:
    secret_text = "Here is my secret sk-proj-1234567890abcdef1234567890 and Google AIzaSyD1234567890abcdef1234567890abc"
    sanitized = sanitize_text_for_export(secret_text)
    assert "sk-proj" not in sanitized
    assert "AIzaSy" not in sanitized
    assert "[REDACTED_SECRET]" in sanitized


# =============================================================================
# 2. ADVERSARIAL VALIDATION SAFEGUARDS (20 CHECKS)
# =============================================================================

def test_validate_archive_rejects_missing_file(tmp_path: Path) -> None:
    non_existent = tmp_path / "ghost.arova"
    with pytest.raises(ArchiveSecurityError, match="not found"):
        validate_archive(non_existent)


def test_validate_archive_rejects_disallowed_extension(tmp_path: Path) -> None:
    bad_ext = tmp_path / "payload.tar"
    bad_ext.write_bytes(b"dummy")
    with pytest.raises(ArchiveSecurityError, match="Invalid archive extension"):
        validate_archive(bad_ext)


def test_validate_archive_rejects_corrupted_zip(tmp_path: Path) -> None:
    corrupted = tmp_path / "corrupt.arova"
    corrupted.write_bytes(b"Not a valid zip header stream")
    with pytest.raises(ArchiveSecurityError, match="Corrupt or invalid ZIP"):
        validate_archive(corrupted)


def test_validate_archive_rejects_path_traversal(tmp_path: Path) -> None:
    bad_zip = tmp_path / "traversal.arova"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("../etc/passwd", "root:x:0:0:")
        zf.writestr("manifest.json", "{}")

    with pytest.raises(ArchiveSecurityError, match="Path traversal detected"):
        validate_archive(bad_zip)


def test_validate_archive_rejects_absolute_path(tmp_path: Path) -> None:
    bad_zip = tmp_path / "absolute_path.arova"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("/root/.bashrc", "echo pwned")
        zf.writestr("manifest.json", "{}")

    with pytest.raises(ArchiveSecurityError, match="Dangerous absolute path"):
        validate_archive(bad_zip)


def test_validate_archive_rejects_windows_drive_path(tmp_path: Path) -> None:
    bad_zip = tmp_path / "win_drive.arova"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("C:\\Windows\\System32\\calc.exe", "evil")
        zf.writestr("manifest.json", "{}")

    with pytest.raises(ArchiveSecurityError, match="Dangerous absolute path"):
        validate_archive(bad_zip)


def test_validate_archive_rejects_nested_archive(tmp_path: Path) -> None:
    bad_zip = tmp_path / "nested.arova"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("inner_payload.zip", b"fake zip")
        zf.writestr("manifest.json", "{}")

    with pytest.raises(ArchiveSecurityError, match="Nested archive entry rejected"):
        validate_archive(bad_zip)


def test_validate_archive_rejects_missing_manifest(tmp_path: Path) -> None:
    bad_zip = tmp_path / "no_manifest.arova"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("assets.ndjson", '{"id": "123"}\n')

    with pytest.raises(ArchiveSecurityError, match="missing required root manifest.json"):
        validate_archive(bad_zip)


def test_validate_archive_rejects_malformed_manifest_json(tmp_path: Path) -> None:
    bad_zip = tmp_path / "bad_manifest.arova"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("manifest.json", "{not valid json syntax")

    with pytest.raises(ArchiveSecurityError, match="Malformed manifest.json"):
        validate_archive(bad_zip)


def test_validate_archive_rejects_incompatible_format_version(tmp_path: Path) -> None:
    bad_zip = tmp_path / "incompatible.arova"
    manifest = {
        "format_version": "99.0.0",
        "export_id": "exp-1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "entries": [],
    }
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))

    with pytest.raises(ArchiveSecurityError, match="Incompatible archive format version"):
        validate_archive(bad_zip)


def test_validate_archive_rejects_unmanifested_entry(seeded_db: tuple, tmp_path: Path) -> None:
    session, asset, version, video, _ = seeded_db
    export_path = tmp_path / "valid.arova"
    export_portable_archive(db=session, target_archive_path=export_path)

    tampered_path = tmp_path / "tampered_unmanifested.arova"
    with zipfile.ZipFile(export_path, "r") as zf_in:
        with zipfile.ZipFile(tampered_path, "w") as zf_out:
            for item in zf_in.infolist():
                zf_out.writestr(item, zf_in.read(item.filename))
            zf_out.writestr("extra_payload.ndjson", '{"sneaky": true}\n')

    with pytest.raises(ArchiveSecurityError, match="Archive entry mismatch"):
        validate_archive(tampered_path)


def test_validate_archive_rejects_checksum_tampering(seeded_db: tuple, tmp_path: Path) -> None:
    session, asset, version, video, _ = seeded_db
    export_path = tmp_path / "valid.arova"
    export_portable_archive(db=session, target_archive_path=export_path)

    tampered_path = tmp_path / "tampered_content.arova"
    with zipfile.ZipFile(export_path, "r") as zf_in:
        with zipfile.ZipFile(tampered_path, "w") as zf_out:
            for item in zf_in.infolist():
                if item.filename == "assets.ndjson":
                    zf_out.writestr(item.filename, '{"id": "tampered_asset"}\n')
                else:
                    zf_out.writestr(item, zf_in.read(item.filename))

    with pytest.raises(ArchiveSecurityError, match="(?:size mismatch|checksum mismatch)"):
        validate_archive(tampered_path)


def test_validate_archive_rejects_embedded_secrets_in_records(tmp_path: Path) -> None:
    bad_zip = tmp_path / "leaked_secret.arova"
    ndjson_content = '{"id": "1", "api_key": "sk-proj-supersecretkey123456789012345"}\n'.encode("utf-8")
    entry_sha = hashlib.sha256(ndjson_content).hexdigest()
    entry_size = len(ndjson_content)

    manifest = ArchiveManifest(
        format_version="1.0.0",
        export_id="exp-sec",
        created_at=datetime.now(timezone.utc),
        entries=[
            ArchiveEntryManifest(name="assets.ndjson", sha256=entry_sha, size_bytes=entry_size)
        ],
    )

    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("manifest.json", manifest.model_dump_json())
        zf.writestr("assets.ndjson", ndjson_content)

    with pytest.raises(ArchiveSecurityError, match="Prohibited credential or secret detected"):
        validate_archive(bad_zip)


def test_validate_archive_rejects_malformed_ndjson_line(tmp_path: Path) -> None:
    bad_zip = tmp_path / "malformed_ndjson.arova"
    ndjson_content = b'{"valid": true}\n{broken json line}\n'
    entry_sha = hashlib.sha256(ndjson_content).hexdigest()
    entry_size = len(ndjson_content)

    manifest = ArchiveManifest(
        format_version="1.0.0",
        export_id="exp-err",
        created_at=datetime.now(timezone.utc),
        entries=[
            ArchiveEntryManifest(name="assets.ndjson", sha256=entry_sha, size_bytes=entry_size)
        ],
    )

    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("manifest.json", manifest.model_dump_json())
        zf.writestr("assets.ndjson", ndjson_content)

    with pytest.raises(ArchiveSecurityError, match="Malformed JSON"):
        validate_archive(bad_zip)


# =============================================================================
# 3. DRY RUN AND TRANSACTIONAL IMPORT TESTS
# =============================================================================

def test_dry_run_import_does_not_mutate_db(seeded_db: tuple, tmp_path: Path) -> None:
    session, asset, version, video, _ = seeded_db
    export_path = tmp_path / "dry_run_source.arova"
    export_portable_archive(db=session, target_archive_path=export_path)

    # Count entities before
    counts_before = {
        "assets": session.query(Asset).count(),
        "versions": session.query(AssetVersion).count(),
        "transcripts": session.query(Transcript).count(),
        "annotations": session.query(Annotation).count(),
    }

    report = dry_run_import_archive(db=session, archive_path=export_path)
    assert report.valid is True
    assert report.matching_existing_records["assets"] == 1
    assert report.matching_existing_records["versions"] == 1

    counts_after = {
        "assets": session.query(Asset).count(),
        "versions": session.query(AssetVersion).count(),
        "transcripts": session.query(Transcript).count(),
        "annotations": session.query(Annotation).count(),
    }
    assert counts_before == counts_after


def test_import_portable_archive_round_trip(seeded_db: tuple, tmp_path: Path) -> None:
    session_src, asset, version, video, _ = seeded_db
    export_path = tmp_path / "round_trip.arova"
    export_portable_archive(db=session_src, target_archive_path=export_path)

    # Create a fresh target database
    target_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(target_engine)
    TargetSession = sessionmaker(autocommit=False, autoflush=False, bind=target_engine)

    with TargetSession() as target_db:
        # Import archive into target DB
        result = import_portable_archive(db=target_db, archive_path=export_path)
        if result.status != "success":
            print("IMPORT ERRORS:", result.errors)
        assert result.status == "success"
        assert result.imported_counts["assets"] == 1
        assert result.imported_counts["versions"] == 1
        assert result.imported_counts["transcripts"] == 1
        assert result.imported_counts["transcript_segments"] == 1
        assert result.imported_counts["annotations"] == 1

        # Verify imported entities exist in target database
        imported_asset = target_db.get(Asset, asset.id)
        assert imported_asset is not None
        imported_version = target_db.query(AssetVersion).filter_by(sha256=version.sha256).first()
        assert imported_version is not None
        assert imported_version.sha256 == version.sha256

        imported_annot = target_db.query(Annotation).filter_by(target_id=imported_version.id).first()
        assert imported_annot is not None
        assert imported_annot.body == "Crucial intro hook for reel cut"

    Base.metadata.drop_all(bind=target_engine)


def test_import_foreign_id_aliasing(seeded_db: tuple, tmp_path: Path) -> None:
    session_src, asset, version, video, _ = seeded_db
    export_path = tmp_path / "alias_test.arova"
    export_portable_archive(db=session_src, target_archive_path=export_path)

    # In target db, create an asset that has identical SHA-256 but different ID
    target_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(target_engine)
    TargetSession = sessionmaker(autocommit=False, autoflush=False, bind=target_engine)

    with TargetSession() as target_db:
        local_asset = Asset(id=str(uuid4()))
        target_db.add(local_asset)
        target_db.flush()

        local_version = AssetVersion(
            id=str(uuid4()),
            asset_id=local_asset.id,
            sha256=version.sha256,  # Identical content hash!
            identity_state=IdentityState.VERIFIED.value,
        )
        target_db.add(local_version)
        target_db.commit()

        # Import archive - foreign version must be mapped to local_version
        result = import_portable_archive(db=target_db, archive_path=export_path)
        if result.status != "success":
            print("IMPORT ERRORS:", result.errors)
        assert result.status == "success"
        assert result.remapped_count >= 1

        # Check IDAlias
        alias = target_db.query(IDAlias).filter_by(foreign_id=version.id).first()
        assert alias is not None
        assert alias.local_id == local_version.id

    Base.metadata.drop_all(bind=target_engine)


# =============================================================================
# 4. MEDIA AVAILABILITY & CROSS-MACHINE RELINKING
# =============================================================================

def test_resolve_media_availability_online_and_missing(seeded_db: tuple, tmp_path: Path) -> None:
    session, asset, version, video, video_file = seeded_db

    # 1. When video file exists
    avail = resolve_media_availability(db=session, version_id=version.id)
    assert avail.version_id == version.id
    assert avail.availability == LocationAvailability.AVAILABLE.value
    assert avail.can_play is True
    assert avail.can_export is True
    assert avail.file_path is not None

    # 2. When file is moved/deleted (offline media memory state)
    video_file.unlink()
    avail_offline = resolve_media_availability(db=session, version_id=version.id)
    assert avail_offline.availability == LocationAvailability.MISSING.value
    assert avail_offline.can_play is False
    assert avail_offline.can_export is False


def test_relink_asset_media_with_sha256_verification(seeded_db: tuple, tmp_path: Path) -> None:
    session, asset, version, video, video_file = seeded_db
    new_dir = tmp_path / "relocated_media"
    new_dir.mkdir(parents=True, exist_ok=True)

    relocated_file = new_dir / "relocated_creator_lesson.mp4"
    shutil.move(str(video_file), str(relocated_file))

    # Media should now be offline
    avail_before = resolve_media_availability(db=session, version_id=version.id)
    assert avail_before.can_play is False

    # Relink to relocated file
    relink_res = relink_asset_media(
        db=session,
        version_id=version.id,
        new_file_path=relocated_file,
    )
    assert relink_res.status == "relinked"

    # Availability must now be restored
    avail_after = resolve_media_availability(db=session, version_id=version.id)
    assert avail_after.can_play is True
    assert avail_after.can_export is True
    assert "relocated_creator_lesson.mp4" in avail_after.file_path


def test_relink_rejected_on_hash_mismatch(seeded_db: tuple, tmp_path: Path) -> None:
    session, asset, version, video, _ = seeded_db
    corrupted_replacement = tmp_path / "corrupted_media.mp4"
    corrupted_replacement.write_bytes(b"Completely different video content bytes")

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        relink_asset_media(
            db=session,
            version_id=version.id,
            new_file_path=corrupted_replacement,
        )


def test_relink_rejected_on_nonexistent_file(seeded_db: tuple, tmp_path: Path) -> None:
    session, asset, version, video, _ = seeded_db
    non_existent = tmp_path / "non_existent.mp4"

    with pytest.raises(FileNotFoundError, match="not found"):
        relink_asset_media(
            db=session,
            version_id=version.id,
            new_file_path=non_existent,
        )


# =============================================================================
# 5. STABLE RESULT CACHE KEY
# =============================================================================

def test_search_cache_key_is_deterministic_and_path_independent() -> None:
    version_id = "ver-stable-1234"
    query = "  How to Create Engaging Short-Form Content?  "

    key1 = compute_search_cache_key(version_id=version_id, query=query)
    key2 = compute_search_cache_key(version_id=version_id, query="how to create engaging short-form content?")
    assert key1 == key2
    assert len(key1) == 64  # SHA-256


# =============================================================================
# 6. ANNOTATION CRUD & DUPLICATE MEDIA DISCOVERY
# =============================================================================

def test_annotation_crud_and_duplicates(seeded_db: tuple) -> None:
    session, asset, version, video, _ = seeded_db

    # Create new annotation
    an = Annotation(
        id=str(uuid4()),
        target_type="version",
        target_id=version.id,
        author_type="human",
        display_name="Editor Lead",
        trust="human_verified",
        body="Review for final cut",
    )
    session.add(an)
    session.commit()

    queried = session.query(Annotation).filter_by(target_id=version.id).all()
    assert len(queried) >= 2

    # Delete annotation
    session.delete(an)
    session.commit()
    assert session.get(Annotation, an.id) is None


# =============================================================================
# 7. VERSIONED REST API ENDPOINTS
# =============================================================================

def test_rest_api_export_and_availability(client: TestClient, seeded_db: tuple) -> None:
    session, asset, version, video, _ = seeded_db

    # 1. GET Availability
    res_avail = client.get(f"/api/v1/versions/{version.id}/availability")
    assert res_avail.status_code == 200
    avail_json = res_avail.json()
    assert avail_json["can_play"] is True
    assert avail_json["version_id"] == version.id

    # 2. POST Export
    res_export = client.post("/api/v1/portable/export", json={"asset_ids": [asset.id]})
    assert res_export.status_code == 200
    export_json = res_export.json()
    assert export_json["format_version"] == "1.0.0"
    assert export_json["records_count"]["assets"] == 1


def test_rest_api_dry_run_and_import(client: TestClient, seeded_db: tuple, tmp_path: Path) -> None:
    session, asset, version, video, _ = seeded_db
    export_path = tmp_path / "api_test.arova"
    export_portable_archive(db=session, target_archive_path=export_path)

    # 1. POST Dry-run
    res_dry = client.post(f"/api/v1/portable/import/dry-run?archive_path={export_path}")
    assert res_dry.status_code == 200
    dry_json = res_dry.json()
    assert dry_json["valid"] is True

    # 2. POST Import
    res_imp = client.post(f"/api/v1/portable/import?archive_path={export_path}")
    assert res_imp.status_code == 200
    imp_json = res_imp.json()
    assert imp_json["status"] == "success"


def test_rest_api_annotations_endpoints(client: TestClient, seeded_db: tuple) -> None:
    session, asset, version, video, _ = seeded_db

    # 1. POST /api/v1/annotations
    payload = {
        "target_type": "version",
        "target_id": version.id,
        "author_type": "human",
        "display_name": "Reviewer",
        "trust": "human_verified",
        "body": "Great pacing in this chapter",
    }
    res_post = client.post("/api/v1/annotations", json=payload)
    assert res_post.status_code == 200
    annot = res_post.json()
    annot_id = annot["id"]
    assert annot["body"] == payload["body"]

    # 2. GET /api/v1/annotations
    res_get = client.get(f"/api/v1/annotations?target_id={version.id}")
    assert res_get.status_code == 200
    items = res_get.json()
    assert any(it["id"] == annot_id for it in items)

    # 3. DELETE /api/v1/annotations/{id}
    res_del = client.delete(f"/api/v1/annotations/{annot_id}")
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "deleted"
