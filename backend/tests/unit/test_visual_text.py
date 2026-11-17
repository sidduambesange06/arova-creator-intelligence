from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.providers.embeddings import index_video_chunks
from app.ai.retrieval.chunker import build_timestamp_windows
from app.ai.retrieval.hybrid_search import run_hybrid_search
from app.database.session import Base, init_db
from app.models.entities import Transcript, TranscriptSegment, Video, VideoScene
from app.processing.visual_text import extract_visual_text_from_frame


def test_extract_visual_text_fallback_handling() -> None:
    # 1. Non-existent path returns empty string without crashing
    assert extract_visual_text_from_frame(None) == ""
    assert extract_visual_text_from_frame("non_existent_thumbnail.jpg") == ""


def test_chunker_fuses_on_screen_visual_text() -> None:
    segments = [
        {"id": "s1", "start_time": 0.0, "end_time": 10.0, "text": "Now we initialize our backend server."},
        {"id": "s2", "start_time": 10.0, "end_time": 25.0, "text": "We configure the routes."},
    ]
    scenes = [
        {"start_time": 0.0, "end_time": 15.0, "description": "const app = express(); app.listen(3000);"},
    ]

    chunks = build_timestamp_windows(segments, video_id="v1", window_sec=30.0, scenes=scenes)
    assert len(chunks) == 1
    assert "Now we initialize our backend server." in chunks[0].chunk_text
    assert "[On-Screen Visual Text]: const app = express(); app.listen(3000);" in chunks[0].chunk_text


def test_multimodal_search_match_channel_tagging(tmp_path: Path) -> None:
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    with TestingSession() as db:
        video = Video(
            filename="full_stack_course.mp4",
            file_path="/tmp/full_stack_course.mp4",
            file_hash="hash_multimodal_99",
            duration=60.0,
        )
        db.add(video)
        db.commit()

        transcript = Transcript(
            video_id=video.id,
            language="en",
            model_name="whisper-base",
            full_text="Let us write our database connection logic now.",
        )
        db.add(transcript)
        db.commit()

        seg = TranscriptSegment(
            transcript_id=transcript.id,
            video_id=video.id,
            start_time=0.0,
            end_time=30.0,
            text="Let us write our database connection logic now.",
        )
        db.add(seg)
        db.commit()

        # Add visual scene with on-screen code that was NOT spoken aloud
        scene = VideoScene(
            video_id=video.id,
            scene_index=0,
            start_time=0.0,
            end_time=30.0,
            description="postgresql://postgres:secret@localhost:5432/production_db",
        )
        db.add(scene)
        db.commit()

        # Index video chunks (now multimodal)
        index_video_chunks(db, video.id, storage_dir=tmp_path / "vectors")

        # Search for code shown on screen
        resp = run_hybrid_search(
            db=db,
            query="postgresql localhost 5432",
            top_k=3,
            storage_dir=str(tmp_path / "vectors"),
        )
        assert resp.total_results >= 1
        top_result = resp.results[0]
        assert top_result.video_id == video.id
        assert top_result.match_channel == "visual"
        assert resp.visual_evidence_count == 1

        # Retrieval-layer channel filtering:
        # 1. Searching in 'speech' channel for visual-only code ('postgresql') must return 0 results
        resp_speech_only = run_hybrid_search(
            db=db,
            query="postgresql localhost 5432",
            top_k=3,
            channel_filter="speech",
            storage_dir=str(tmp_path / "vectors"),
        )
        assert resp_speech_only.total_results == 0
        assert resp_speech_only.channel_filter == "speech"

        # 2. Searching in 'visual' channel for spoken-only words ('connection logic') must return 0 results
        resp_visual_only_mismatch = run_hybrid_search(
            db=db,
            query="connection logic",
            top_k=3,
            channel_filter="visual",
            storage_dir=str(tmp_path / "vectors"),
        )
        assert resp_visual_only_mismatch.total_results == 0

        # 3. Searching in 'visual' channel for on-screen code ('postgresql') returns the visual chunk
        resp_visual_hit = run_hybrid_search(
            db=db,
            query="postgresql 5432",
            top_k=3,
            channel_filter="visual",
            storage_dir=str(tmp_path / "vectors"),
        )
        assert resp_visual_hit.total_results == 1
        assert resp_visual_hit.results[0].match_channel == "visual"

        # 4. Grounded Q&A (/api/v1/ai/ask / answer_video_question) obeys channel filter
        from app.services.summary_service import answer_video_question

        qa_speech_blocked = answer_video_question(
            db=db,
            query="postgresql 5432",
            channel="speech",
        )
        assert qa_speech_blocked["citations"] == []
        assert qa_speech_blocked["channel_filter"] == "speech"
        assert "Spoken Dialogue channel" in qa_speech_blocked["answer"]

        qa_visual_allowed = answer_video_question(
            db=db,
            query="postgresql 5432",
            channel="visual",
        )
        assert len(qa_visual_allowed["citations"]) == 1
        assert qa_visual_allowed["channel_filter"] == "visual"
        assert "postgresql://postgres:secret@localhost:5432/production_db" in qa_visual_allowed["answer"]
        # Ensure spoken text was stripped when answering strictly from visual channel
        assert "connection logic" not in qa_visual_allowed["answer"]

    Base.metadata.drop_all(bind=test_engine)
