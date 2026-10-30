from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.providers.embeddings import index_video_chunks
from app.core.config import settings
from app.database.session import Base, get_db, init_db
from app.main import app
from app.models.entities import Transcript, TranscriptSegment, Video


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setattr(settings, "ALLOWED_MEDIA_ROOTS", str(tmp_path))
    monkeypatch.setattr(settings, "MEDIA_STORAGE_DIR", str(tmp_path / "media"))
    monkeypatch.setattr(settings, "CHROMA_PERSIST_DIR", str(tmp_path / "vectors"))

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

    # Seed test video and multi-segment transcript
    with TestingSession() as db:
        video = Video(
            filename="creator_ai_tutorial.mp4",
            file_path=str(tmp_path / "creator_ai_tutorial.mp4"),
            file_hash="hash_clip_summary_01",
            duration=90.0,
        )
        db.add(video)
        db.commit()

        transcript = Transcript(
            video_id=video.id,
            language="en",
            model_name="whisper-base",
            full_text=(
                "Welcome to this lecture on neural network architecture and deep learning fundamentals. "
                "In part one we examine reciprocal rank fusion and vector indexing. "
                "In part two we transition to cross encoder re ranking for precision video retrieval. "
                "Finally we conclude with latency benchmarks and summary extraction."
            ),
        )
        db.add(transcript)
        db.commit()

        segments_data = [
            (0.0, 20.0, "Welcome to this lecture on neural network architecture and deep learning fundamentals."),
            (20.0, 45.0, "In part one we examine reciprocal rank fusion and vector indexing."),
            (45.0, 70.0, "In part two we transition to cross encoder re ranking for precision video retrieval."),
            (70.0, 90.0, "Finally we conclude with latency benchmarks and summary extraction."),
        ]
        for s_time, e_time, text_val in segments_data:
            seg = TranscriptSegment(
                transcript_id=transcript.id,
                video_id=video.id,
                start_time=s_time,
                end_time=e_time,
                text=text_val,
                confidence=0.95,
            )
            db.add(seg)
        db.commit()

        # Build index
        index_video_chunks(db, video.id, storage_dir=tmp_path / "vectors")

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


def test_search_clips_api_bounds_and_rationale(client: TestClient) -> None:
    # 1. Search clips with duration limits
    res = client.post(
        "/api/v1/search/clips",
        json={
            "query": "neural network architecture",
            "min_duration": 15.0,
            "max_duration": 45.0,
            "top_k": 3,
        },
    )
    assert res.status_code == 200
    clips = res.json()
    assert len(clips) >= 1

    first = clips[0]
    assert "creator_ai_tutorial.mp4" in first["filename"]
    assert first["duration"] >= 15.0
    assert first["duration"] <= 45.0
    assert "Matches 'neural network architecture'" in first["rationale"]
    assert first["relevance_score"] > 0.0
    assert len(first["transcript_snippet"]) > 0


def test_summarize_video_api_grounded_and_cached(client: TestClient) -> None:
    # 1. Get video ID from list
    videos_res = client.get("/api/v1/videos")
    assert videos_res.status_code == 200
    video_id = videos_res.json()[0]["id"]

    # 2. Call summarize
    sum_res = client.post("/api/v1/ai/summarize", json={"video_id": video_id})
    assert sum_res.status_code == 200
    data = sum_res.json()
    assert data["video_id"] == video_id
    assert len(data["summary"]) > 0
    assert len(data["topics"]) >= 1
    assert len(data["chapters"]) >= 3
    assert data["chapters"][0]["start_time"] == 0.0
    assert "title" in data["chapters"][0]
    assert data["model_name"] == "extractive-grounded-local"

    # 3. Call summarize second time to verify DB caching
    sum_res_cached = client.post("/api/v1/ai/summarize", json={"video_id": video_id})
    assert sum_res_cached.status_code == 200
    assert sum_res_cached.json()["summary"] == data["summary"]

    # 4. Error check: non-existent video -> 404
    missing_res = client.post("/api/v1/ai/summarize", json={"video_id": "non-existent-uuid"})
    assert missing_res.status_code == 404
