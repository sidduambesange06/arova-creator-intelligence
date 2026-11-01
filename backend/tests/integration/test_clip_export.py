from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
import errno
import hashlib
import math
import os
from pathlib import Path
import subprocess

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.database.session import Base, get_db, init_db
from app.main import app
from app.models.entities import Video
from app.processing.clip_export import (
    _atomically_claim_and_move,
    _validate_clip_timestamps,
    export_subclip,
    measure_clip_duration,
)
from app.processing.metadata import get_ffmpeg_binary, probe_video_metadata
from mcp_server.tools.video_tools import export_video_clip as mcp_export_video_clip


def _make_test_mp4(target: Path, duration: float = 3.0) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = get_ffmpeg_binary()
    subprocess.run(
        [
            ffmpeg_bin,
            "-nostdin",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=duration={duration}:size=320x240:rate=24",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=1000:duration={duration}",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-pix_fmt",
            "yuv420p",
            str(target),
        ],
        capture_output=True,
        check=True,
        timeout=30,
    )
    return target


@pytest.fixture()
def test_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    media_dir = tmp_path / "media"
    clips_dir = media_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "ALLOWED_MEDIA_ROOTS", str(tmp_path))
    monkeypatch.setattr(settings, "MEDIA_STORAGE_DIR", str(media_dir))

    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def _override_get_db() -> Generator[Session, None, None]:
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db

    # Create dummy video 1: root sample_lecture.mp4
    video1_path = tmp_path / "sample_lecture.mp4"
    _make_test_mp4(video1_path, duration=3.0)

    # Create dummy video 2: subdir sample_lecture.mp4 (identical basename, different location)
    video2_path = tmp_path / "sub_folder" / "sample_lecture.mp4"
    _make_test_mp4(video2_path, duration=3.0)

    with TestingSession() as session:
        v1 = Video(
            id="video-clip-test-1",
            filename="sample_lecture.mp4",
            file_path=str(video1_path),
            file_hash="hash_clip_1",
            file_size=video1_path.stat().st_size,
            duration=3.0,
            width=320,
            height=240,
            fps=24.0,
            codec="h264",
            format="mp4",
            processing_status="completed",
        )
        v2 = Video(
            id="video-clip-test-2",
            filename="sample_lecture.mp4",
            file_path=str(video2_path),
            file_hash="hash_clip_2",
            file_size=video2_path.stat().st_size,
            duration=3.0,
            width=320,
            height=240,
            fps=24.0,
            codec="h264",
            format="mp4",
            processing_status="completed",
        )
        session.add_all([v1, v2])
        session.commit()

    with TestClient(app) as test_client:
        yield {
            "client": test_client,
            "session_factory": TestingSession,
            "tmp_path": tmp_path,
            "clips_dir": clips_dir,
            "video1_path": video1_path,
            "video2_path": video2_path,
        }

    app.dependency_overrides.clear()


@pytest.fixture()
def client(test_env: dict) -> TestClient:
    return test_env["client"]


# 1. Fractional timestamps disambiguation
def test_export_clip_fractional_timestamps_no_collision(test_env: dict) -> None:
    client = test_env["client"]
    resp1 = client.post(
        "/api/v1/videos/video-clip-test-1/export-clip",
        json={"start_time": 1.2, "end_time": 2.4},
    )
    assert resp1.status_code == 200, resp1.text
    file1 = resp1.json()["clip_filename"]

    resp2 = client.post(
        "/api/v1/videos/video-clip-test-1/export-clip",
        json={"start_time": 1.8, "end_time": 2.9},
    )
    assert resp2.status_code == 200, resp2.text
    file2 = resp2.json()["clip_filename"]

    assert file1 != file2, f"Fractional timestamps must not collide: {file1} vs {file2}"
    assert "1.2s-2.4s" in file1
    assert "1.8s-2.9s" in file2
    assert (test_env["clips_dir"] / file1).is_file()
    assert (test_env["clips_dir"] / file2).is_file()


# 2. Distinct source videos with identical basenames disambiguation
def test_export_clip_same_basename_different_sources_no_collision(test_env: dict) -> None:
    client = test_env["client"]
    resp1 = client.post(
        "/api/v1/videos/video-clip-test-1/export-clip",
        json={"start_time": 0.5, "end_time": 1.5},
    )
    assert resp1.status_code == 200
    file1 = resp1.json()["clip_filename"]

    resp2 = client.post(
        "/api/v1/videos/video-clip-test-2/export-clip",
        json={"start_time": 0.5, "end_time": 1.5},
    )
    assert resp2.status_code == 200
    file2 = resp2.json()["clip_filename"]

    assert file1 != file2, f"Clips from distinct source videos must not collide: {file1} vs {file2}"
    assert "video_clip_t" in file1 or "video-clip-t" in file1
    assert (test_env["clips_dir"] / file1).is_file()
    assert (test_env["clips_dir"] / file2).is_file()


# 3. Existing output file remains unmodified (no silent overwrite)
def test_export_clip_existing_file_remains_unmodified(test_env: dict) -> None:
    client = test_env["client"]
    resp1 = client.post(
        "/api/v1/videos/video-clip-test-1/export-clip",
        json={"start_time": 0.2, "end_time": 1.2},
    )
    assert resp1.status_code == 200
    file1 = resp1.json()["clip_filename"]
    path1 = test_env["clips_dir"] / file1
    hash1 = hashlib.sha256(path1.read_bytes()).hexdigest()

    # Re-exporting identical range
    resp2 = client.post(
        "/api/v1/videos/video-clip-test-1/export-clip",
        json={"start_time": 0.2, "end_time": 1.2},
    )
    assert resp2.status_code == 200
    file2 = resp2.json()["clip_filename"]
    path2 = test_env["clips_dir"] / file2

    assert file1 != file2, f"Repeated export must create disambiguated file, got: {file1} and {file2}"
    assert file2.endswith("_1.mp4")
    assert path2.is_file()
    # Original file must remain 100% identical and intact
    assert hashlib.sha256(path1.read_bytes()).hexdigest() == hash1


# 4. Safe concurrent export requests
def test_export_clip_concurrent_requests(test_env: dict) -> None:
    client = test_env["client"]

    def _export_call(times: tuple[float, float]) -> int:
        s, e = times
        r = client.post(
            "/api/v1/videos/video-clip-test-1/export-clip",
            json={"start_time": s, "end_time": e},
        )
        return r.status_code

    ranges = [(0.1, 1.1), (0.1, 1.1), (0.3, 1.3), (0.3, 1.3)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(pool.map(_export_call, ranges))

    assert statuses == [200, 200, 200, 200]
    # Verify no partial temporary files left behind
    leftover_tmps = list(test_env["clips_dir"].glob(".tmp_export_*"))
    assert len(leftover_tmps) == 0


# 5. Negative start time validation
def test_export_clip_negative_start_time(test_env: dict) -> None:
    client = test_env["client"]
    resp = client.post(
        "/api/v1/videos/video-clip-test-1/export-clip",
        json={"start_time": -1.0, "end_time": 2.0},
    )
    assert resp.status_code in (400, 422)

    # MCP tool check
    session = test_env["session_factory"]()
    try:
        with pytest.raises(ValueError, match="cannot be negative"):
            mcp_export_video_clip("video-clip-test-1", start_time=-0.5, end_time=1.0, db=session)
    finally:
        session.close()


# 6. End time <= start time validation
def test_export_clip_end_time_le_start_time(test_env: dict) -> None:
    client = test_env["client"]
    resp_eq = client.post(
        "/api/v1/videos/video-clip-test-1/export-clip",
        json={"start_time": 1.5, "end_time": 1.5},
    )
    assert resp_eq.status_code == 400

    resp_lt = client.post(
        "/api/v1/videos/video-clip-test-1/export-clip",
        json={"start_time": 2.0, "end_time": 1.0},
    )
    assert resp_lt.status_code == 400

    # MCP tool check
    session = test_env["session_factory"]()
    try:
        with pytest.raises(ValueError, match="strictly greater than start_time"):
            mcp_export_video_clip("video-clip-test-1", start_time=2.0, end_time=1.5, db=session)
    finally:
        session.close()


# 7. Strict end time exceeds video duration validation (no tolerance allowed)
def test_export_clip_end_time_exceeds_duration_strict(test_env: dict) -> None:
    client = test_env["client"]
    # Video duration is 3.0s. 3.01s must be strictly rejected
    resp = client.post(
        "/api/v1/videos/video-clip-test-1/export-clip",
        json={"start_time": 1.0, "end_time": 3.01},
    )
    assert resp.status_code == 400
    assert "exceeds video duration" in resp.text

    # MCP tool check
    session = test_env["session_factory"]()
    try:
        with pytest.raises(ValueError, match="exceeds video duration"):
            mcp_export_video_clip("video-clip-test-1", start_time=1.0, end_time=3.01, db=session)
    finally:
        session.close()


# 8. Non-finite timestamp validation (NaN, +inf, -inf)
def test_export_clip_non_finite_timestamps(test_env: dict) -> None:
    client = test_env["client"]

    # Shared validator direct checks
    with pytest.raises(ValueError, match="finite"):
        _validate_clip_timestamps(float("nan"), 2.0)
    with pytest.raises(ValueError, match="finite"):
        _validate_clip_timestamps(0.0, float("inf"))
    with pytest.raises(ValueError, match="finite"):
        _validate_clip_timestamps(float("-inf"), 2.0)
    with pytest.raises(ValueError, match="finite"):
        _validate_clip_timestamps(0.0, 2.0, max_duration=float("nan"))

    # Direct export_subclip checks
    with pytest.raises(ValueError, match="finite"):
        export_subclip(test_env["video1_path"], start_time=float("nan"), end_time=2.0)

    # MCP check
    session = test_env["session_factory"]()
    try:
        with pytest.raises(ValueError, match="finite"):
            mcp_export_video_clip("video-clip-test-1", start_time=float("nan"), end_time=2.0, db=session)
    finally:
        session.close()


# 9. Symlink escape rejection
def test_download_clip_symlink_escape(test_env: dict) -> None:
    client = test_env["client"]
    clips_dir = test_env["clips_dir"]
    outside_file = test_env["tmp_path"] / "outside_secret.txt"
    outside_file.write_text("SENSITIVE_SECRET_DATA")

    symlink_path = clips_dir / "symlink_escape.mp4"
    try:
        os.symlink(str(outside_file), str(symlink_path))
        can_symlink = True
    except (OSError, NotImplementedError):
        can_symlink = False

    if can_symlink:
        resp = client.get("/api/v1/videos/clips/symlink_escape.mp4")
        assert resp.status_code == 400
        assert "escape attempt" in resp.text
    else:
        # On Windows without SeCreateSymbolicLinkPrivilege, verify that resolution boundary logic works
        assert not symlink_path.resolve().is_relative_to(clips_dir) if symlink_path.exists() else True


# 10. Path traversal attempts
def test_download_clip_path_traversal(client: TestClient) -> None:
    # Directory traversal
    resp1 = client.get("/api/v1/videos/clips/..%2F..%2Fsecret.txt")
    assert resp1.status_code in (400, 404)

    resp2 = client.get("/api/v1/videos/clips/%2e%2e%5csecret.txt")
    assert resp2.status_code in (400, 404)

    # Windows reserved device name
    resp3 = client.get("/api/v1/videos/clips/CON.mp4")
    assert resp3.status_code == 400

    # Subdirectory slash
    resp4 = client.get("/api/v1/videos/clips/sub%2Fclip.mp4")
    assert resp4.status_code in (400, 404)

    # Nonexistent valid filename
    resp5 = client.get("/api/v1/videos/clips/nonexistent_clip.mp4")
    assert resp5.status_code == 404


# 11. FFmpeg failure cleans up partial file
def test_ffmpeg_failure_cleans_up_partial_file(test_env: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    clips_dir = test_env["clips_dir"]
    video1_path = test_env["video1_path"]

    # Simulate transcode failure returning non-zero exit code
    def fake_subprocess_run(cmd, *args, **kwargs):
        class FakeProc:
            returncode = 1
            stderr = "Simulated synthetic FFmpeg decoding error"
            stdout = ""
        # Create an artificial partial temporary file during the run
        for arg in cmd:
            if isinstance(arg, str) and ".tmp_export_" in arg:
                Path(arg).write_bytes(b"CORRUPT_PARTIAL_BYTES")
        return FakeProc()

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)

    with pytest.raises(RuntimeError, match="FFmpeg clip export failed"):
        export_subclip(
            video_path=video1_path,
            start_time=0.5,
            end_time=1.5,
            output_dir=clips_dir,
        )

    # Verify no partial temporary files left behind
    leftover_tmps = list(clips_dir.glob(".tmp_export_*"))
    assert len(leftover_tmps) == 0


# 12. Original source video checksum remains unchanged
def test_source_video_immutability(test_env: dict) -> None:
    client = test_env["client"]
    video_path = test_env["video1_path"]
    sha_before = hashlib.sha256(video_path.read_bytes()).hexdigest()

    # Perform multiple exports
    client.post(
        "/api/v1/videos/video-clip-test-1/export-clip",
        json={"start_time": 0.1, "end_time": 1.0},
    )
    client.post(
        "/api/v1/videos/video-clip-test-1/export-clip",
        json={"start_time": 0.5, "end_time": 2.5},
    )

    sha_after = hashlib.sha256(video_path.read_bytes()).hexdigest()
    assert sha_before == sha_after, "Source media file must remain strictly immutable"


# 13. Valid clip export succeeds with probed duration and correct download
def test_export_clip_actual_duration_and_success(test_env: dict) -> None:
    client = test_env["client"]
    resp = client.post(
        "/api/v1/videos/video-clip-test-1/export-clip",
        json={"start_time": 0.5, "end_time": 2.0},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["video_id"] == "video-clip-test-1"
    assert data["start_time"] == 0.5
    assert data["end_time"] == 2.0

    # Independently inspect the generated output using probe_video_metadata (FFprobe)
    exported_path = test_env["clips_dir"] / data["clip_filename"]
    assert exported_path.is_file()
    probed_meta = probe_video_metadata(exported_path)
    # Justified tolerance: container header format duration rounded to millisecond precision (0.005s)
    assert data["duration"] == pytest.approx(probed_meta.duration, abs=0.005)
    assert data["duration"] > 0
    assert data["file_size"] == exported_path.stat().st_size
    assert "download_url" in data

    # Test downloading the exported clip
    dl_resp = client.get(data["download_url"])
    assert dl_resp.status_code == 200
    assert dl_resp.headers["content-type"] == "video/mp4"
    assert int(dl_resp.headers["content-length"]) == data["file_size"]


# 14. Probe failure or corrupt duration measurement raises RuntimeError and cleans up
def test_export_clip_probe_failure_raises_and_cleans_up(test_env: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    clips_dir = test_env["clips_dir"]
    video1_path = test_env["video1_path"]

    import app.processing.clip_export as ce

    # Case A: probe raises an exception
    def fake_probe_error(p):
        raise ValueError("Corrupt container header")

    monkeypatch.setattr(ce, "probe_video_metadata", fake_probe_error)

    with pytest.raises(RuntimeError, match="could not be measured"):
        export_subclip(
            video_path=video1_path,
            start_time=0.5,
            end_time=1.5,
            output_dir=clips_dir,
        )

    # Verify unmeasurable file was removed
    assert len(list(clips_dir.glob("*.mp4"))) == 0

    # Case B: probe returns non-positive / invalid duration
    class FakeMetaZero:
        duration = 0.0

    monkeypatch.setattr(ce, "probe_video_metadata", lambda p: FakeMetaZero())

    with pytest.raises(RuntimeError, match="invalid or non-positive"):
        export_subclip(
            video_path=video1_path,
            start_time=0.5,
            end_time=1.5,
            output_dir=clips_dir,
        )

    assert len(list(clips_dir.glob("*.mp4"))) == 0


# 15. Atomic claim and move unit tests: collision, fallback, reservation cleanup
def test_atomic_claim_and_move_unit_cases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.processing.clip_export as ce

    temp_file = tmp_path / "temp.mp4"
    temp_file.write_bytes(b"temp_content")
    target_file = tmp_path / "target.mp4"

    # A: Normal claim (hardlink succeeds)
    assert _atomically_claim_and_move(temp_file, target_file) is True
    assert target_file.is_file()
    assert not temp_file.exists()

    # B: Hardlink collision (target already exists)
    temp_file2 = tmp_path / "temp2.mp4"
    temp_file2.write_bytes(b"temp2_content")
    assert _atomically_claim_and_move(temp_file2, target_file) is False
    assert target_file.read_bytes() == b"temp_content"  # Existing file untouched

    # C: Unsupported hardlink fallback succeeds
    temp_file3 = tmp_path / "temp3.mp4"
    temp_file3.write_bytes(b"temp3_content")
    target_file3 = tmp_path / "target3.mp4"

    def fake_os_link_unsupported(src, dst):
        raise OSError(errno.ENOSYS, "Function not implemented on this filesystem")

    monkeypatch.setattr(os, "link", fake_os_link_unsupported)
    assert _atomically_claim_and_move(temp_file3, target_file3) is True
    assert target_file3.read_bytes() == b"temp3_content"

    # D: Unsupported hardlink collision (fallback target already exists)
    temp_file4 = tmp_path / "temp4.mp4"
    temp_file4.write_bytes(b"temp4_content")
    assert _atomically_claim_and_move(temp_file4, target_file3) is False
    assert target_file3.read_bytes() == b"temp3_content"  # Target 3 untouched

    # E: Promotion failure after reservation (reservation cleaned up, pre-existing preserved)
    temp_file5 = tmp_path / "temp5.mp4"
    temp_file5.write_bytes(b"temp5_content")
    target_file5 = tmp_path / "target5.mp4"

    def fake_replace_fail(src, dst):
        raise OSError(errno.EIO, "Simulated disk I/O error during replace")

    monkeypatch.setattr(Path, "replace", fake_replace_fail)
    with pytest.raises(OSError, match="Simulated disk I/O error"):
        _atomically_claim_and_move(temp_file5, target_file5)
    # The empty reservation must be cleaned up
    assert not target_file5.exists()

    # F: Non-unsupported OSError in link (e.g. EACCES) must re-raise, NOT fall back
    temp_file6 = tmp_path / "temp6.mp4"
    temp_file6.write_bytes(b"temp6_content")
    target_file6 = tmp_path / "target6.mp4"

    def fake_os_link_eacces(src, dst):
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(os, "link", fake_os_link_eacces)
    with pytest.raises(PermissionError):
        _atomically_claim_and_move(temp_file6, target_file6)

    # G: Substituted file identity protection: if file at target_path has non-zero size or different identity, do NOT delete it
    temp_file7 = tmp_path / "temp7.mp4"
    temp_file7.write_bytes(b"temp7_content")
    target_file7 = tmp_path / "target7.mp4"

    monkeypatch.setattr(os, "link", fake_os_link_unsupported)

    def fake_replace_with_substitution(src, dst):
        # Simulate an external actor or process substituting a file at dst
        dst.write_bytes(b"SUBSTITUTED_IMPORTANT_DATA")
        raise OSError(errno.EIO, "Replace failed after external write")

    monkeypatch.setattr(Path, "replace", fake_replace_with_substitution)
    with pytest.raises(OSError, match="Replace failed"):
        _atomically_claim_and_move(temp_file7, target_file7)
    # Must NOT delete the substituted file!
    assert target_file7.exists()
    assert target_file7.read_bytes() == b"SUBSTITUTED_IMPORTANT_DATA"


# 16. Unicode source filenames (Kannada, Hindi, spaces, punctuation, ASCII)
def test_unicode_filename_support_and_download(test_env: dict) -> None:
    client = test_env["client"]
    clips_dir = test_env["clips_dir"]
    tmp_path = test_env["tmp_path"]
    session_factory = test_env["session_factory"]

    test_cases = [
        ("ಕನ್ನಡ_ಚಿತ್ರ_2024.mp4", "kannada-test-vid"),
        ("हिन्दी_सिनेमा.mp4", "hindi-test-vid"),
        ("lecture recording 2024.mp4", "spaces-test-vid"),
        ("clip [final] (part 1)!.mp4", "punct-test-vid"),
        ("standard_ascii_lecture.mp4", "ascii-test-vid"),
    ]

    for filename, vid_id in test_cases:
        src_path = tmp_path / filename
        _make_test_mp4(src_path, duration=2.0)

        with session_factory() as session:
            v = Video(
                id=vid_id,
                filename=filename,
                file_path=str(src_path),
                file_hash=f"hash_{vid_id}",
                file_size=src_path.stat().st_size,
                duration=2.0,
                width=320,
                height=240,
                fps=24.0,
                codec="h264",
                format="mp4",
                processing_status="completed",
            )
            session.add(v)
            session.commit()

        # Export clip
        resp = client.post(
            f"/api/v1/videos/{vid_id}/export-clip",
            json={"start_time": 0.2, "end_time": 1.2},
        )
        assert resp.status_code == 200, f"Export failed for {filename}: {resp.text}"
        data = resp.json()
        clip_name = data["clip_filename"]

        # Download clip via GET endpoint
        dl_resp = client.get(f"/api/v1/videos/clips/{clip_name}")
        assert dl_resp.status_code == 200, f"Download failed for {clip_name}: {dl_resp.status_code}"
        assert dl_resp.headers["content-type"] == "video/mp4"
        assert int(dl_resp.headers["content-length"]) > 0


def test_export_clip_not_found(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/videos/nonexistent-id/export-clip",
        json={"start_time": 0.0, "end_time": 1.0},
    )
    assert resp.status_code == 404
