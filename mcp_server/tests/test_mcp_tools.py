from collections.abc import Generator
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.providers.embeddings import index_video_chunks
from app.core.config import settings
from app.database.session import Base, init_db
from app.models.entities import Transcript, TranscriptSegment, Video
from mcp_server.tools import video_tools


@pytest.fixture()
def db_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Session, None, None]:
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

    with TestingSession() as session:
        video = Video(
            filename="mcp_deep_dive.mp4",
            file_path=str(tmp_path / "mcp_deep_dive.mp4"),
            file_hash="hash_mcp_demo_123",
            duration=75.0,
            width=1920,
            height=1080,
            fps=30.0,
            codec="h264",
            format="mp4",
        )
        session.add(video)
        session.commit()

        transcript = Transcript(
            video_id=video.id,
            language="en",
            model_name="whisper-base",
            full_text="Model Context Protocol enables agents to connect to local tools and video knowledge.",
        )
        session.add(transcript)
        session.commit()

        segments = [
            (0.0, 25.0, "Model Context Protocol enables agents to connect to local tools and video knowledge."),
            (25.0, 50.0, "We implement eight read only tools for semantic retrieval and indexing."),
            (50.0, 75.0, "The system delivers real time transcript search and grounded summaries."),
        ]
        for s, e, text_val in segments:
            seg = TranscriptSegment(
                transcript_id=transcript.id,
                video_id=video.id,
                start_time=s,
                end_time=e,
                text=text_val,
                confidence=0.96,
            )
            session.add(seg)
        session.commit()

        index_video_chunks(session, video.id, storage_dir=tmp_path / "vectors")
        yield session

    Base.metadata.drop_all(bind=test_engine)


def test_all_eight_mcp_tools(db_session: Session) -> None:
    # 1. list_videos
    videos = video_tools.list_videos(db=db_session)
    assert len(videos) == 1
    assert videos[0]["filename"] == "mcp_deep_dive.mp4"
    video_id = videos[0]["id"]

    # 2. get_video_metadata
    meta = video_tools.get_video_metadata(video_id=video_id, db=db_session)
    assert meta["id"] == video_id
    assert meta["width"] == 1920
    assert meta["height"] == 1080
    assert meta["duration"] == 75.0

    # 3. search_video_content
    search_res = video_tools.search_video_content(query="Model Context Protocol", top_k=3, db=db_session)
    assert len(search_res) >= 1
    assert search_res[0]["video_id"] == video_id
    assert search_res[0]["stage1_score"] > 0.0

    # 4. search_transcripts
    lex_res = video_tools.search_transcripts(query="Protocol", db=db_session)
    assert len(lex_res) >= 1
    assert "Model Context Protocol" in lex_res[0]["text"]

    # 5. find_video_clips
    clips = video_tools.find_video_clips(
        query="semantic retrieval",
        min_duration=10.0,
        max_duration=60.0,
        db=db_session,
    )
    assert len(clips) >= 1
    assert clips[0]["duration"] >= 10.0
    assert clips[0]["duration"] <= 60.0

    # 6. summarize_video
    summary = video_tools.summarize_video(video_id=video_id, db=db_session)
    assert summary["video_id"] == video_id
    assert len(summary["summary"]) > 0
    assert len(summary["topics"]) >= 1

    # 7. get_video_chapters
    chapters = video_tools.get_video_chapters(video_id=video_id, db=db_session)
    assert len(chapters) >= 1
    assert "start_time" in chapters[0]
    assert "title" in chapters[0]

    # 8. get_media_library_stats
    stats = video_tools.get_media_library_stats(db=db_session)
    assert stats["total_videos"] == 1
    assert stats["total_duration_sec"] == 75.0
    assert stats["total_transcripts_indexed"] == 1

