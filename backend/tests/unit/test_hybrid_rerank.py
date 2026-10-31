from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.providers.embeddings import index_video_chunks
from app.ai.reranking.cross_encoder_reranker import CrossEncoderReranker
from app.ai.retrieval.hybrid_search import run_hybrid_search
from app.database.session import Base, get_db, init_db
from app.main import app
from app.models.entities import Transcript, TranscriptSegment, Video


def test_cross_encoder_reranker_scoring() -> None:
    reranker = CrossEncoderReranker()
    query = "vector database indexing"
    candidates = [
        {"embedding_id": "c1", "chunk_text": "We discussed deploying docker containers on linux servers."},
        {"embedding_id": "c2", "chunk_text": "This chapter explains vector database indexing with high recall."},
        {"embedding_id": "c3", "chunk_text": "Styling components using tailwind css framework."},
    ]
    reranked, elapsed_ms = reranker.rerank(query, candidates, top_k=3)
    assert len(reranked) == 3
    assert elapsed_ms >= 0.0
    # c2 must rank first because it explicitly matches vector database indexing
    assert reranked[0]["embedding_id"] == "c2"
    assert reranked[0]["rerank_score"] > reranked[1]["rerank_score"]


def test_hybrid_search_rrf_and_api(tmp_path: Path) -> None:
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def _override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db

    with TestingSession() as db:
        video = Video(
            filename="rag_tutorial.mp4",
            file_path="/tmp/rag_tutorial.mp4",
            file_hash="hash999",
            duration=60.0,
        )
        db.add(video)
        db.commit()

        transcript = Transcript(
            video_id=video.id,
            language="en",
            model_name="whisper-base",
            full_text="Today we cover hybrid search with reciprocal rank fusion.",
        )
        db.add(transcript)
        db.commit()

        seg = TranscriptSegment(
            transcript_id=transcript.id,
            video_id=video.id,
            start_time=0.0,
            end_time=30.0,
            text="Today we cover hybrid search with reciprocal rank fusion.",
        )
        db.add(seg)
        db.commit()

        # Index chunks
        index_video_chunks(db, video.id, storage_dir=tmp_path / "vectors")

        # 1. Run hybrid search service
        resp = run_hybrid_search(
            db=db,
            query="hybrid search reciprocal rank fusion",
            top_k=5,
            use_reranker=True,
            storage_dir=str(tmp_path / "vectors"),
        )
        assert resp.total_results >= 1
        assert resp.results[0].video_id == video.id
        assert resp.results[0].stage1_score > 0.0
        assert resp.results[0].rerank_score > 0.0
        assert resp.stage1_ms >= 0.0

    # 2. Test API endpoints
    with TestClient(app) as client:
        sem_res = client.post(
            "/api/v1/search/semantic",
            json={"query": "reciprocal rank fusion", "top_k": 3, "use_reranker": True},
        )
        assert sem_res.status_code == 200
        assert "results" in sem_res.json()

        lex_res = client.post(
            "/api/v1/search/transcripts",
            json={"query": "hybrid search"},
        )
        assert lex_res.status_code == 200
        assert len(lex_res.json()) >= 1
        assert lex_res.json()[0]["filename"] == "rag_tutorial.mp4"

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)

