from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.database.session import Base, init_db
from app.models.entities import Transcript, TranscriptSegment, Video
from app.services.summary_service import answer_video_question, generate_video_summary


@pytest.fixture()
def db_session() -> Session:
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSession()

    video = Video(
        filename="consent_test.mp4",
        file_path="/tmp/consent_test.mp4",
        file_hash="hash_consent_123",
        duration=60.0,
    )
    session.add(video)
    session.commit()

    transcript = Transcript(
        video_id=video.id,
        language="en",
        model_name="whisper-base",
        full_text="This video discusses privacy by design, consent boundaries, and local-first execution.",
    )
    session.add(transcript)
    session.commit()

    seg = TranscriptSegment(
        transcript_id=transcript.id,
        video_id=video.id,
        start_time=0.0,
        end_time=30.0,
        text="This video discusses privacy by design, consent boundaries, and local-first execution.",
        confidence=0.99,
    )
    session.add(seg)
    session.commit()

    from app.ai.providers.embeddings import index_video_chunks
    index_video_chunks(session, video.id)

    yield session
    session.close()
    Base.metadata.drop_all(bind=test_engine)


def test_consent_boundary_enforced_when_api_key_provided(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Ensure system-level remote consent is FALSE
    monkeypatch.setattr(settings, "AI_REMOTE_CONSENT", False)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "env_gemini_key_12345")

    # 1. Calling answer_video_question with request-level api_key but consent_remote_ai=False
    res = answer_video_question(
        db=db_session,
        query="privacy by design",
        api_key="request_gemini_key_999",
        consent_remote_ai=False,
    )
    assert res["remote_egress"] is False
    assert res["provider"] == "local"
    assert res["model_name"] == "grounded-extractive-local"
    assert res["consent_source"] is None
    assert len(res["egress_data_categories"]) == 0

    # 2. Calling generate_video_summary with request-level api_key but consent_remote_ai=False
    summary = generate_video_summary(
        db=db_session,
        video_id=db_session.query(Video).first().id,
        api_key="request_gemini_key_999",
        consent_remote_ai=False,
    )
    assert summary.model_name == "extractive-grounded-local"
    assert "gemini" not in summary.model_name


def test_openai_api_key_setting_removed_from_config() -> None:
    # Verify that unused OPENAI_API_KEY setting has been removed from Settings schema
    assert not hasattr(settings, "OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY") is None
