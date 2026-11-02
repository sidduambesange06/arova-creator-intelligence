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
from app.models.entities import ProcessingJob, Transcript, Video
from app.processing.metadata import get_ffmpeg_binary
from app.workers.pipeline_runner import _execute_pipeline


def _make_test_mp4(target: Path, duration: float = 2.0) -> Path:
    ffmpeg_bin = get_ffmpeg_binary()
    subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=duration={duration}:size=320x240:rate=24",
            "-c:v",
            "libx264",
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
def test_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    monkeypatch.setattr(settings, "ALLOWED_MEDIA_ROOTS", str(tmp_path))
    storage_dir = tmp_path / "media_storage"
    monkeypatch.setattr(settings, "MEDIA_STORAGE_DIR", str(storage_dir))

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def _override_get_db() -> Generator[Session, None, None]:
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db

    # Also monkeypatch SessionLocal in pipeline runner so worker runs against the same in-memory DB
    import app.workers.pipeline_runner as runner
    monkeypatch.setattr(runner, "SessionLocal", TestingSession)

    client = TestClient(app)
    db = TestingSession()

    yield {"client": client, "db": db, "tmp_path": tmp_path, "storage_dir": storage_dir}

    app.dependency_overrides.clear()
    db.close()


def test_ingest_subtitles_endpoint_success(test_setup: dict) -> None:
    client = test_setup["client"]
    db = test_setup["db"]
    tmp_path = test_setup["tmp_path"]

    video_path = _make_test_mp4(tmp_path / "presentation.mp4")
    import_resp = client.post("/api/v1/videos/import", json={"path": str(video_path)})
    assert import_resp.status_code == 200
    video_id = import_resp.json()["imported"][0]["id"]

    srt_content = """1
00:00:00,500 --> 00:00:01,800
Deep learning and neural networks

2
00:00:02,000 --> 00:00:03,500
Vector search indexing local media
"""
    resp = client.post(
        f"/api/v1/videos/{video_id}/subtitles",
        json={"content": srt_content, "filename": "presentation.srt", "language": "en"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["video_id"] == video_id
    assert len(data["segments"]) == 2
    assert "Vector search indexing local media" in data["full_text"]
    assert data["segments"][0]["start_time"] == 0.5
    assert data["segments"][0]["end_time"] == 1.8

    # Verify search finds the ingested subtitle segment
    search_resp = client.post("/api/v1/search/semantic", json={"query": "neural networks"})
    assert search_resp.status_code == 200
    results = search_resp.json()["results"]
    assert len(results) > 0
    assert any("neural networks" in r["chunk_text"].lower() for r in results)


def test_ingest_subtitles_endpoint_vtt_format(test_setup: dict) -> None:
    client = test_setup["client"]
    tmp_path = test_setup["tmp_path"]

    video_path = _make_test_mp4(tmp_path / "keynote.mp4")
    import_resp = client.post("/api/v1/videos/import", json={"path": str(video_path)})
    video_id = import_resp.json()["imported"][0]["id"]

    vtt_content = """WEBVTT

00:00.500 --> 00:01.800
<v Speaker>Welcome to the keynote speech.</v>
"""
    resp = client.post(
        f"/api/v1/videos/{video_id}/subtitles",
        json={"content": vtt_content, "filename": "keynote.vtt"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["segments"]) == 1
    assert resp.json()["segments"][0]["text"] == "Welcome to the keynote speech."


def test_ingest_subtitles_endpoint_404_and_400(test_setup: dict) -> None:
    client = test_setup["client"]

    # 404 on nonexistent video
    resp_404 = client.post(
        "/api/v1/videos/nonexistent-id-999/subtitles",
        json={"content": "1\n00:00:01,000 --> 00:00:02,000\nHello", "filename": "test.srt"},
    )
    assert resp_404.status_code == 404

    # 400 on invalid subtitle cues
    tmp_path = test_setup["tmp_path"]
    video_path = _make_test_mp4(tmp_path / "valid.mp4")
    import_resp = client.post("/api/v1/videos/import", json={"path": str(video_path)})
    video_id = import_resp.json()["imported"][0]["id"]

    resp_400 = client.post(
        f"/api/v1/videos/{video_id}/subtitles",
        json={"content": "This is not a valid srt file at all.", "filename": "bad.srt"},
    )
    assert resp_400.status_code == 400


def test_pipeline_runner_auto_discovers_sidecar_subtitles(test_setup: dict) -> None:
    db = test_setup["db"]
    tmp_path = test_setup["tmp_path"]

    video_path = _make_test_mp4(tmp_path / "course_lesson.mp4")
    # Put a sidecar .srt right beside the video file
    sidecar_srt = tmp_path / "course_lesson.srt"
    sidecar_srt.write_text(
        """1
00:00:00,500 --> 00:00:01,800
Sidecar subtitle discovered automatically
""",
        encoding="utf-8",
    )

    client = test_setup["client"]
    import_resp = client.post("/api/v1/videos/import", json={"path": str(video_path)})
    video_id = import_resp.json()["imported"][0]["id"]

    # Run the pipeline runner directly
    _execute_pipeline(db=db, video_id=video_id, media_storage_dir=test_setup["storage_dir"])

    # Check transcript in DB
    transcript = db.query(Transcript).filter_by(video_id=video_id).first()
    assert transcript is not None
    assert "course_lesson.srt" in transcript.model_name
    assert "Sidecar subtitle discovered automatically" in transcript.full_text
