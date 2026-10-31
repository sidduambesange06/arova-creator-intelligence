from collections.abc import Generator
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
from app.processing.metadata import get_ffmpeg_binary


def _make_test_mp4(target: Path, duration: float = 3.0) -> Path:
    ffmpeg_bin = get_ffmpeg_binary()
    subprocess.run(
        [
            ffmpeg_bin,
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
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
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

    # Create dummy video entry with real test MP4
    video_path = tmp_path / "sample_lecture.mp4"
    _make_test_mp4(video_path, duration=3.0)

    with TestingSession() as session:
        v = Video(
            id="video-clip-test-1",
            filename="sample_lecture.mp4",
            file_path=str(video_path),
            file_hash="hash_clip_1",
            file_size=video_path.stat().st_size,
            duration=3.0,
            width=320,
            height=240,
            fps=24.0,
            codec="h264",
            format="mp4",
            processing_status="completed",
        )
        session.add(v)
        session.commit()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_export_clip_success(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/videos/video-clip-test-1/export-clip",
        json={"start_time": 0.5, "end_time": 2.0},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["video_id"] == "video-clip-test-1"
    assert data["start_time"] == 0.5
    assert data["end_time"] == 2.0
    assert data["duration"] == 1.5
    assert data["file_size"] > 0
    assert "download_url" in data

    # Test downloading the exported clip
    dl_resp = client.get(data["download_url"])
    assert dl_resp.status_code == 200
    assert dl_resp.headers["content-type"] == "video/mp4"
    assert int(dl_resp.headers["content-length"]) == data["file_size"]


def test_export_clip_invalid_bounds(client: TestClient) -> None:
    # start_time >= end_time
    resp = client.post(
        "/api/v1/videos/video-clip-test-1/export-clip",
        json={"start_time": 2.5, "end_time": 1.0},
    )
    assert resp.status_code == 400

    # start_time >= duration
    resp = client.post(
        "/api/v1/videos/video-clip-test-1/export-clip",
        json={"start_time": 5.0, "end_time": 7.0},
    )
    assert resp.status_code == 400


def test_export_clip_not_found(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/videos/nonexistent-id/export-clip",
        json={"start_time": 0.0, "end_time": 1.0},
    )
    assert resp.status_code == 404


def test_download_clip_path_traversal(client: TestClient) -> None:
    resp = client.get("/api/v1/videos/clips/..%2F..%2Fsecret.txt")
    assert resp.status_code in (400, 404)
