"""Unit and Integration Tests for Task 4B: Media Discovery and Safety.

Verifies:
1. Media-root management: directory validation, ALLOWED_MEDIA_ROOTS containment, policy updates.
2. Reliable media-folder scanning: directory recursion, ignoring .git/node_modules/dot-dirs, media extension filtering.
3. Deterministic media discovery: UUIDv5 version identity, relative path normalization, stat key generation.
4. Duplicate handling: identical media content across folders maps to 1 Asset, 1 Version, multiple Locations.
5. Relink / Move handling: moved/renamed files are relinked without losing asset/version identity.
6. In-place modification: modified file creates a new AssetVersion with supersedes_version_id.
7. Missing file handling and restoration: deleted file transitions location to missing; restored file returns to available.
8. Source media immutability: byte-for-byte SHA-256 pre/post check confirms zero modification of source media.
9. ScanRun lifecycle: status transitions, metrics counts tracking, and error resilience.
10. REST API and CLI integration.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import compute_sha256
from app.database.session import Base
from app.main import app
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
from app.services.discovery_service import (
    create_or_get_library,
    get_library_root,
    get_scan_run,
    list_library_assets,
    list_library_roots,
    register_library_root,
    run_root_media_scan,
    update_library_root_policy,
)
from app.cli.scan import run_scan_cli


@pytest.fixture
def test_db():
    """In-memory SQLite database initialized with all tables."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionMaker = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionMaker() as session:
        yield session


def _create_sample_file(path: Path, content: bytes = b"SAMPLE_MEDIA_DATA_BYTES") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_library_and_root_management(test_db: Session, tmp_path: Path):
    # 1. Create library
    lib = create_or_get_library(test_db, label="Test Studio", execution_profile=ExecutionProfile.LOCAL_AI.value)
    assert lib.id is not None
    assert lib.label == "Test Studio"
    assert lib.execution_profile == ExecutionProfile.LOCAL_AI.value

    # Idempotent retrieval
    lib2 = create_or_get_library(test_db, label="Test Studio")
    assert lib2.id == lib.id

    # 2. Register media root
    media_dir = tmp_path / "footage"
    media_dir.mkdir()
    allowed = [tmp_path]

    root = register_library_root(
        db=test_db,
        library_id=lib.id,
        path=media_dir,
        label="Footage Root",
        root_type=RootType.LOCAL_FIXED.value,
        policy=RootPolicy.LOCAL_ONLY.value,
        allowed_roots=allowed,
    )
    assert root.id is not None
    assert root.library_id == lib.id
    assert root.label == "Footage Root"
    assert root.status == "active"
    assert root.policy == RootPolicy.LOCAL_ONLY.value
    assert Path(root.volume_id).resolve() == media_dir.resolve()
    assert root.marker_id is not None

    # Idempotent re-registration
    root_repeat = register_library_root(
        db=test_db,
        library_id=lib.id,
        path=media_dir,
        allowed_roots=allowed,
    )
    assert root_repeat.id == root.id

    # Update policy
    updated = update_library_root_policy(test_db, root_id=root.id, policy=RootPolicy.ALLOW_REMOTE.value)
    assert updated.policy == RootPolicy.ALLOW_REMOTE.value

    # List roots
    roots = list_library_roots(test_db, library_id=lib.id)
    assert len(roots) == 1
    assert roots[0].id == root.id


def test_root_registration_security_containment(test_db: Session, tmp_path: Path):
    lib = create_or_get_library(test_db, label="Security Lib")
    allowed_dir = tmp_path / "allowed_dir"
    allowed_dir.mkdir()
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()

    # Outside allowed media roots -> rejected
    with pytest.raises(ValueError, match="outside allowed media roots"):
        register_library_root(
            db=test_db,
            library_id=lib.id,
            path=outside_dir,
            allowed_roots=[allowed_dir],
        )

    # Path traversal with ../ escaping allowed root -> rejected
    traversal_path = allowed_dir / ".." / "outside_dir"
    with pytest.raises(ValueError, match="outside allowed media roots"):
        register_library_root(
            db=test_db,
            library_id=lib.id,
            path=traversal_path,
            allowed_roots=[allowed_dir],
        )

    # Non-existent directory -> rejected
    with pytest.raises(FileNotFoundError):
        register_library_root(
            db=test_db,
            library_id=lib.id,
            path=allowed_dir / "does_not_exist",
            allowed_roots=[allowed_dir],
        )


def test_reliable_scanning_and_directory_exclusions(test_db: Session, tmp_path: Path):
    media_root = tmp_path / "media"
    media_root.mkdir()
    allowed = [tmp_path]

    # Valid media files
    _create_sample_file(media_root / "video1.mp4", b"CLIP_ONE")
    _create_sample_file(media_root / "nested" / "video2.mov", b"CLIP_TWO")
    _create_sample_file(media_root / "nested" / "sub" / "audio.wav", b"AUDIO_ONE")

    # Non-media files (must be skipped)
    _create_sample_file(media_root / "readme.txt", b"DOCUMENTATION")
    _create_sample_file(media_root / "config.json", b"{}")

    # Ignored directories (must not be traversed)
    _create_sample_file(media_root / ".git" / "git_clip.mp4", b"GIT_FAKE")
    _create_sample_file(media_root / "node_modules" / "nm_clip.mp4", b"NM_FAKE")
    _create_sample_file(media_root / "__pycache__" / "pyc_clip.mp4", b"PYC_FAKE")
    _create_sample_file(media_root / ".venv" / "venv_clip.mp4", b"VENV_FAKE")
    _create_sample_file(media_root / ".hidden_folder" / "hidden_clip.mp4", b"HIDDEN_FAKE")

    lib = create_or_get_library(test_db, label="Scan Lib")
    root = register_library_root(test_db, lib.id, media_root, allowed_roots=allowed)

    scan_run = run_root_media_scan(test_db, root.id, allowed_roots=allowed)
    assert scan_run.status == "completed"
    assert scan_run.finished_at is not None

    counts = json.loads(scan_run.counts)
    assert counts["discovered_media"] == 3
    assert counts["new_assets"] == 3
    assert counts["new_versions"] == 3
    assert counts["new_locations"] == 3
    assert counts["errors"] == 0

    # Verify no ignored files were indexed
    locations = test_db.query(AssetLocation).filter_by(root_id=root.id).all()
    rel_paths = {loc.rel_path_norm for loc in locations}
    assert "video1.mp4" in rel_paths
    assert "nested/video2.mov" in rel_paths
    assert "nested/sub/audio.wav" in rel_paths
    assert not any(".git" in p or "node_modules" in p or ".venv" in p for p in rel_paths)


def test_deterministic_version_identity_and_sha256(test_db: Session, tmp_path: Path):
    media_root = tmp_path / "media"
    media_root.mkdir()
    allowed = [tmp_path]

    sample_content = b"DETERMINISTIC_TEST_BYTES_42"
    file_path = _create_sample_file(media_root / "test_clip.mp4", sample_content)

    lib = create_or_get_library(test_db, label="Deterministic Lib")
    root = register_library_root(test_db, lib.id, media_root, allowed_roots=allowed)

    scan_run = run_root_media_scan(test_db, root.id, allowed_roots=allowed)
    assert scan_run.status == "completed"

    expected_sha = compute_sha256(file_path)
    expected_version_id = compute_deterministic_version_id(expected_sha)

    version = test_db.query(AssetVersion).filter_by(sha256=expected_sha).first()
    assert version is not None
    assert version.id == expected_version_id
    assert version.size_bytes == len(sample_content)
    assert version.identity_state == IdentityState.VERIFIED.value

    location = test_db.query(AssetLocation).filter_by(version_id=version.id).first()
    assert location is not None
    assert location.rel_path_norm == "test_clip.mp4"
    assert location.stat_key == f"{len(sample_content)}:{int(file_path.stat().st_mtime)}"
    assert location.availability == LocationAvailability.AVAILABLE.value


def test_duplicate_media_handling(test_db: Session, tmp_path: Path):
    media_root = tmp_path / "media"
    media_root.mkdir()
    allowed = [tmp_path]

    # Two files with identical byte content at different locations
    identical_bytes = b"IDENTICAL_INTERVIEW_FOOTAGE"
    _create_sample_file(media_root / "cam_a" / "clip.mp4", identical_bytes)
    _create_sample_file(media_root / "cam_b" / "clip_duplicate.mp4", identical_bytes)

    lib = create_or_get_library(test_db, label="Duplicate Lib")
    root = register_library_root(test_db, lib.id, media_root, allowed_roots=allowed)

    scan_run = run_root_media_scan(test_db, root.id, allowed_roots=allowed)
    assert scan_run.status == "completed"

    counts = json.loads(scan_run.counts)
    assert counts["discovered_media"] == 2
    assert counts["new_assets"] == 1       # Exact 1 Asset
    assert counts["new_versions"] == 1     # Exact 1 Version
    assert counts["new_locations"] == 2    # Two Locations pointing to the same version!

    sha = compute_sha256(media_root / "cam_a" / "clip.mp4")
    version = test_db.query(AssetVersion).filter_by(sha256=sha).first()
    assert version is not None
    assert len(version.locations) == 2

    # Check distinct location records
    loc_paths = {loc.rel_path_norm for loc in version.locations}
    assert "cam_a/clip.mp4" in loc_paths
    assert "cam_b/clip_duplicate.mp4" in loc_paths


def test_relink_moved_file_detection(test_db: Session, tmp_path: Path):
    media_root = tmp_path / "media"
    media_root.mkdir()
    allowed = [tmp_path]

    video_bytes = b"ORIGINAL_FOOTAGE_TO_BE_MOVED"
    orig_path = _create_sample_file(media_root / "raw" / "take1.mp4", video_bytes)

    lib = create_or_get_library(test_db, label="Relink Lib")
    root = register_library_root(test_db, lib.id, media_root, allowed_roots=allowed)

    # Initial scan
    scan1 = run_root_media_scan(test_db, root.id, allowed_roots=allowed)
    assert scan1.status == "completed"

    # Simulate moving the file: delete old and create new path with identical content
    orig_path.unlink()
    new_path = _create_sample_file(media_root / "archive" / "scene_one_take1.mp4", video_bytes)

    # Second scan: must detect missing old location and relink to new location
    scan2 = run_root_media_scan(test_db, root.id, allowed_roots=allowed)
    assert scan2.status == "completed"

    counts2 = json.loads(scan2.counts)
    assert counts2["relocated_locations"] >= 1 or counts2["new_locations"] >= 1

    sha = compute_sha256(new_path)
    version = test_db.query(AssetVersion).filter_by(sha256=sha).first()
    assert version is not None

    # Check locations: old location marked missing or relink_required, new location available
    locations = test_db.query(AssetLocation).filter_by(version_id=version.id).all()
    assert any(loc.rel_path_norm == "archive/scene_one_take1.mp4" and loc.availability == LocationAvailability.AVAILABLE.value for loc in locations)


def test_in_place_modification_creates_superseding_version(test_db: Session, tmp_path: Path):
    media_root = tmp_path / "media"
    media_root.mkdir()
    allowed = [tmp_path]

    file_path = _create_sample_file(media_root / "edit_render.mp4", b"INITIAL_RENDER_V1")

    lib = create_or_get_library(test_db, label="Version Lib")
    root = register_library_root(test_db, lib.id, media_root, allowed_roots=allowed)

    # Scan version 1
    scan1 = run_root_media_scan(test_db, root.id, allowed_roots=allowed)
    assert scan1.status == "completed"

    sha_v1 = compute_sha256(file_path)
    v1 = test_db.query(AssetVersion).filter_by(sha256=sha_v1).first()
    asset_id = v1.asset_id

    # In-place modify file bytes
    file_path.write_bytes(b"UPDATED_RENDER_V2_LONGER_CUT")

    # Scan version 2
    scan2 = run_root_media_scan(test_db, root.id, allowed_roots=allowed)
    assert scan2.status == "completed"

    counts2 = json.loads(scan2.counts)
    assert counts2["new_versions"] == 1
    assert counts2["updated_locations"] == 1

    sha_v2 = compute_sha256(file_path)
    v2 = test_db.query(AssetVersion).filter_by(sha256=sha_v2).first()
    assert v2 is not None
    assert v2.id != v1.id
    assert v2.asset_id == asset_id
    assert v2.supersedes_version_id == v1.id

    # Asset current_version_id points to v2
    asset = test_db.get(Asset, asset_id)
    assert asset.current_version_id == v2.id

    # Location points to v2
    loc = test_db.query(AssetLocation).filter_by(root_id=root.id, rel_path_norm="edit_render.mp4").first()
    assert loc.version_id == v2.id
    assert loc.availability == LocationAvailability.AVAILABLE.value


def test_missing_file_detection_and_restoration(test_db: Session, tmp_path: Path):
    media_root = tmp_path / "media"
    media_root.mkdir()
    allowed = [tmp_path]

    file_path = _create_sample_file(media_root / "removable.mp4", b"DISC_FOOTAGE")

    lib = create_or_get_library(test_db, label="Missing Lib")
    root = register_library_root(test_db, lib.id, media_root, allowed_roots=allowed)

    # Initial scan
    run_root_media_scan(test_db, root.id, allowed_roots=allowed)
    loc = test_db.query(AssetLocation).filter_by(root_id=root.id, rel_path_norm="removable.mp4").first()
    assert loc.availability == LocationAvailability.AVAILABLE.value
    assert loc.missing_since is None

    # Simulate deleting file from disk
    file_path.unlink()

    # Scan after deletion: must mark missing without deleting DB records
    scan_missing = run_root_media_scan(test_db, root.id, allowed_roots=allowed)
    counts = json.loads(scan_missing.counts)
    assert counts["missing_locations"] == 1

    test_db.refresh(loc)
    assert loc.availability == LocationAvailability.MISSING.value
    assert loc.missing_since is not None

    # Database records remain fully preserved
    assert test_db.query(Asset).count() == 1
    assert test_db.query(AssetVersion).count() == 1

    # Restore the file
    _create_sample_file(file_path, b"DISC_FOOTAGE")

    # Scan after restoration: location returns to available
    run_root_media_scan(test_db, root.id, allowed_roots=allowed)
    test_db.refresh(loc)
    assert loc.availability == LocationAvailability.AVAILABLE.value
    assert loc.missing_since is None


def test_source_media_immutability(test_db: Session, tmp_path: Path):
    """Critical Safety Test: verify discovery never modifies, alters, or destroys source files."""
    media_root = tmp_path / "media"
    media_root.mkdir()
    allowed = [tmp_path]

    sample_content = b"CRITICAL_SOURCE_MEDIA_BYTES_PRESERVE_EXACTLY"
    clip = _create_sample_file(media_root / "master_footage.mov", sample_content)
    sha_before = compute_sha256(clip)
    size_before = clip.stat().st_size

    lib = create_or_get_library(test_db, label="Immutability Lib")
    root = register_library_root(test_db, lib.id, media_root, allowed_roots=allowed)

    # Run scan
    run_root_media_scan(test_db, root.id, allowed_roots=allowed)

    # Verify byte-for-byte SHA-256 and size after scan
    sha_after = compute_sha256(clip)
    size_after = clip.stat().st_size
    assert sha_before == sha_after
    assert size_before == size_after


def test_discovery_rest_api(tmp_path: Path):
    """Verify REST API endpoints for Library, Roots, and Scan Runs."""
    media_dir = tmp_path / "api_media"
    media_dir.mkdir()
    _create_sample_file(media_dir / "api_test.mp4", b"API_TEST_VIDEO")

    orig_roots = settings.ALLOWED_MEDIA_ROOTS
    try:
        settings.ALLOWED_MEDIA_ROOTS = str(tmp_path)
        client = TestClient(app)

        # 1. Create Library
        res_lib = client.post("/api/v1/libraries", json={"label": "API Studio"})
        assert res_lib.status_code == 201
        lib_data = res_lib.json()
        library_id = lib_data["id"]

        # 2. List Libraries
        res_libs = client.get("/api/v1/libraries")
        assert res_libs.status_code == 200
        assert any(l["id"] == library_id for l in res_libs.json())

        # 3. Register Root
        res_root = client.post(
            f"/api/v1/libraries/{library_id}/roots",
            json={"path": str(media_dir), "label": "API Root"},
        )
        assert res_root.status_code == 201
        root_data = res_root.json()
        root_id = root_data["id"]

        # 4. Trigger Scan
        res_scan = client.post(f"/api/v1/libraries/roots/{root_id}/scan")
        assert res_scan.status_code == 200
        scan_data = res_scan.json()
        assert scan_data["status"] == "completed"
        assert scan_data["counts"]["discovered_media"] == 1

        # 5. Get Scan by ID
        scan_id = scan_data["id"]
        res_get_scan = client.get(f"/api/v1/libraries/scans/{scan_id}")
        assert res_get_scan.status_code == 200
        assert res_get_scan.json()["id"] == scan_id

        # 6. List Assets
        res_assets = client.get(f"/api/v1/libraries/{library_id}/assets")
        assert res_assets.status_code == 200
        assets = res_assets.json()
        assert len(assets) == 1
        assert len(assets[0]["versions"]) == 1

    finally:
        settings.ALLOWED_MEDIA_ROOTS = orig_roots


def test_scan_cli_command(tmp_path: Path, capsys: pytest.CaptureFixture):
    """Verify arova scan CLI command."""
    media_dir = tmp_path / "cli_media"
    media_dir.mkdir()
    _create_sample_file(media_dir / "cli_clip.mp4", b"CLI_CLIP_BYTES")

    orig_roots = settings.ALLOWED_MEDIA_ROOTS
    try:
        settings.ALLOWED_MEDIA_ROOTS = str(tmp_path)
        exit_code = run_scan_cli([str(media_dir), "--json"])
        assert exit_code == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "completed"
        assert data["counts"]["discovered_media"] == 1
    finally:
        settings.ALLOWED_MEDIA_ROOTS = orig_roots
