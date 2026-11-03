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
from app.processing.metadata import get_ffmpeg_binary


def _synthesize_mp4(target: Path, duration: float = 2.0, with_audio: bool = True) -> Path:
    ffmpeg_bin = get_ffmpeg_binary()
    if with_audio:
        cmd = [
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
        ]
    else:
        cmd = [
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
        ]
    subprocess.run(cmd, capture_output=True, check=True, timeout=30)
    return target


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setattr(settings, "ALLOWED_MEDIA_ROOTS", str(tmp_path))
    monkeypatch.setattr(settings, "MEDIA_STORAGE_DIR", str(tmp_path / "media"))

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

    import app.workers.pipeline_runner as runner_mod
    monkeypatch.setattr(runner_mod, "SessionLocal", TestingSession)

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


def test_video_processing_pipeline_and_jobs_api(client: TestClient, tmp_path: Path) -> None:
    video_path = _synthesize_mp4(tmp_path / "full_demo.mp4", duration=2.0, with_audio=True)
    # Provide genuine sidecar subtitle file
    sub_path = tmp_path / "full_demo.srt"
    sub_path.write_text(
        "1\n00:00:00,000 --> 00:00:01,800\nDemonstrating unified media pipeline without fake transcripts.\n",
        encoding="utf-8",
    )

    # 1. Import video
    imp_res = client.post("/api/v1/videos/import", json={"path": str(video_path)})
    assert imp_res.status_code == 200
    video_id = imp_res.json()["imported"][0]["id"]

    # 2. Before processing: transcript should be 404
    t_before = client.get(f"/api/v1/videos/{video_id}/transcript")
    assert t_before.status_code == 404

    # 3. Trigger processing with sync=true
    proc_res = client.post(f"/api/v1/videos/{video_id}/process?sync=true")
    assert proc_res.status_code == 200
    job_id = proc_res.json()["job_id"]
    assert proc_res.json()["status"] == "completed"

    # 4. Check transcript endpoint -> genuine subtitle text
    t_after = client.get(f"/api/v1/videos/{video_id}/transcript")
    assert t_after.status_code == 200
    transcript_body = t_after.json()
    assert transcript_body["video_id"] == video_id
    assert len(transcript_body["segments"]) == 1
    assert "Demonstrating unified media pipeline" in transcript_body["segments"][0]["text"]

    # 5. Check scenes endpoint
    scenes_res = client.get(f"/api/v1/videos/{video_id}/scenes")
    assert scenes_res.status_code == 200
    scenes_body = scenes_res.json()
    assert len(scenes_body) >= 1
    assert scenes_body[0]["start_time"] == 0.0

    # 6. Check job status endpoint
    job_res = client.get(f"/api/v1/jobs/{job_id}")
    assert job_res.status_code == 200
    job_body = job_res.json()
    assert job_body["status"] == "completed"
    assert job_body["progress"] == 100.0

    # 7. Check telemetry endpoint
    tel_res = client.get("/api/v1/jobs/telemetry/stats")
    assert tel_res.status_code == 200
    assert tel_res.json()["jobs_completed"] >= 1


def test_video_without_audio_or_subtitles_completes_cleanly_without_fake_transcript(
    client: TestClient, tmp_path: Path
) -> None:
    # Synthesize silent video without audio stream
    silent_path = _synthesize_mp4(tmp_path / "silent_demo.mp4", duration=2.0, with_audio=False)

    imp_res = client.post("/api/v1/videos/import", json={"path": str(silent_path)})
    assert imp_res.status_code == 200
    video_id = imp_res.json()["imported"][0]["id"]

    # Run processing
    proc_res = client.post(f"/api/v1/videos/{video_id}/process?sync=true")
    assert proc_res.status_code == 200
    assert proc_res.json()["status"] == "completed"

    # Core indexing succeeded: scenes and thumbnails are created
    scenes_res = client.get(f"/api/v1/videos/{video_id}/scenes")
    assert scenes_res.status_code == 200
    assert len(scenes_res.json()) >= 1

    # Transcript is genuinely unavailable: 404, zero fake speech segments fabricated
    t_res = client.get(f"/api/v1/videos/{video_id}/transcript")
    assert t_res.status_code == 404

    # Verify zero 1-second silent WAV was created on disk
    silent_wav = tmp_path / "media" / "audio" / f"{video_id}.wav"
    assert not silent_wav.is_file()
