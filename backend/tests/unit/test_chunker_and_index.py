from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.ai.providers.embeddings import (
    LocalMiniLMEmbeddingProvider,
    index_video_chunks,
    load_vectors_from_disk,
)
from app.ai.retrieval.chunker import build_timestamp_windows
from app.database.session import Base, init_db
from app.models.entities import EmbeddingRecord, Transcript, TranscriptSegment, Video


def test_build_timestamp_windows() -> None:
    segments = [
        {"id": "s1", "start_time": 0.0, "end_time": 10.0, "text": "First section on database."},
        {"id": "s2", "start_time": 10.0, "end_time": 25.0, "text": "Second section on index."},
        {"id": "s3", "start_time": 25.0, "end_time": 35.0, "text": "Third section on queries."},
        {"id": "s4", "start_time": 35.0, "end_time": 50.0, "text": "Fourth section on scaling."},
    ]
    chunks = build_timestamp_windows(segments, video_id="vid_test_1", window_sec=30.0, overlap_sec=5.0)
    assert len(chunks) >= 2
    assert chunks[0].start_time == 0.0
    assert chunks[0].end_time >= 30.0
    assert "First section" in chunks[0].chunk_text
    assert "Third section" in chunks[0].chunk_text
    assert chunks[1].start_time > 0.0


def test_minilm_embedding_provider_dimension_and_norm() -> None:
    provider = LocalMiniLMEmbeddingProvider()
    vec = provider.embed_text("Timestamp video search with hybrid retrieval")
    assert len(vec) == 384
    norm = sum(x * x for x in vec) ** 0.5
    assert abs(norm - 1.0) < 1e-4

    batch = provider.embed_batch(["query one", "query two"])
    assert len(batch) == 2
    assert len(batch[0]) == 384


def test_index_video_chunks_dual_storage(tmp_path: Path) -> None:
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    init_db(test_engine)
    Session = sessionmaker(bind=test_engine)

    with Session() as db:
        video = Video(
            filename="lecture.mp4",
            file_path="/tmp/lecture.mp4",
            file_hash="hash555",
            duration=45.0,
        )
        db.add(video)
        db.commit()

        transcript = Transcript(
            video_id=video.id,
            language="en",
            model_name="test-whisper",
            full_text="Segment one on architecture. Segment two on retrieval and database search.",
        )
        db.add(transcript)
        db.commit()

        seg1 = TranscriptSegment(
            transcript_id=transcript.id,
            video_id=video.id,
            start_time=0.0,
            end_time=15.0,
            text="Segment one on architecture.",
        )
        seg2 = TranscriptSegment(
            transcript_id=transcript.id,
            video_id=video.id,
            start_time=15.0,
            end_time=35.0,
            text="Segment two on retrieval and database search.",
        )
        db.add_all([seg1, seg2])
        db.commit()

        # 1. Index video chunks
        records = index_video_chunks(db, video.id, storage_dir=tmp_path / "vectors")
        assert len(records) >= 1
        assert records[0].video_id == video.id
        assert db.query(EmbeddingRecord).filter_by(video_id=video.id).count() == len(records)

        # 2. Check FTS5 virtual table
        fts_rows = db.execute(
            text("SELECT embedding_id, chunk_text FROM transcript_chunks_fts WHERE transcript_chunks_fts MATCH 'architecture'")
        ).fetchall()
        assert len(fts_rows) >= 1

        # 3. Check vector disk file
        vec_dict = load_vectors_from_disk(tmp_path / "vectors")
        assert records[0].embedding_id in vec_dict
        assert len(vec_dict[records[0].embedding_id]) == 384

        # 4. Re-index video -> verifies no duplicates
        re_records = index_video_chunks(db, video.id, storage_dir=tmp_path / "vectors")
        assert len(re_records) == len(records)
        assert db.query(EmbeddingRecord).filter_by(video_id=video.id).count() == len(records)

    Base.metadata.drop_all(bind=test_engine)
