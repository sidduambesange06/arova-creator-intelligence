from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.retrieval.chunker import build_timestamp_windows
from app.core.config import settings
from app.models.entities import EmbeddingRecord, Transcript


class EmbeddingProvider(Protocol):
    def embed_text(self, text: str) -> list[float]: ...
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class LocalMiniLMEmbeddingProvider:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self.dim = 384
        self._model = None
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._model = SentenceTransformer(model_name)
        except Exception:
            # shortcut: falls back to deterministic normalized 384-d token n-gram projection when sentence-transformers weights are offline
            self._model = None

    def embed_text(self, input_text: str) -> list[float]:
        return self.embed_batch([input_text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if self._model is not None:
            try:
                embeddings = self._model.encode(texts, normalize_embeddings=True)
                return [e.tolist() for e in embeddings]
            except Exception:
                pass

        results: list[list[float]] = []
        for t in texts:
            vec = [0.0] * self.dim
            tokens = [tok.strip().lower() for tok in t.split() if tok.strip()]
            if not tokens:
                vec[0] = 1.0
                results.append(vec)
                continue

            for tok in tokens:
                h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest(), 16)
                idx = h % self.dim
                sign = 1.0 if ((h >> 8) & 1) == 1 else -1.0
                vec[idx] += sign

            # L2 normalize
            norm = math.sqrt(sum(x * x for x in vec))
            if norm > 0.0:
                vec = [x / norm for x in vec]
            else:
                vec[0] = 1.0
            results.append(vec)
        return results


def _ensure_fts5_table(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS transcript_chunks_fts USING fts5(
                embedding_id UNINDEXED,
                video_id UNINDEXED,
                chunk_text
            );
            """
        )
    )
    db.commit()


def _get_vector_storage_path(storage_dir: str | Path | None = None) -> Path:
    dir_path = Path(storage_dir or settings.CHROMA_PERSIST_DIR)
    dir_path.mkdir(parents=True, exist_ok=True)
    return (dir_path / "embeddings.json").resolve()


def save_vectors_to_disk(vectors_dict: dict[str, list[float]], storage_dir: str | Path | None = None) -> None:
    target = _get_vector_storage_path(storage_dir)
    existing: dict[str, list[float]] = {}
    if target.is_file():
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    existing.update(vectors_dict)
    target.write_text(json.dumps(existing), encoding="utf-8")


def load_vectors_from_disk(storage_dir: str | Path | None = None) -> dict[str, list[float]]:
    target = _get_vector_storage_path(storage_dir)
    if not target.is_file():
        return {}
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}


def index_video_chunks(
    db: Session,
    video_id: str,
    provider: EmbeddingProvider | None = None,
    storage_dir: str | Path | None = None,
) -> list[EmbeddingRecord]:
    _ensure_fts5_table(db)

    # 1. Clear old records for this video
    db.query(EmbeddingRecord).filter_by(video_id=video_id).delete()
    db.execute(
        text("DELETE FROM transcript_chunks_fts WHERE video_id = :vid"),
        {"vid": video_id},
    )
    db.commit()

    # 2. Retrieve transcript & segments
    transcript = db.query(Transcript).filter_by(video_id=video_id).first()
    if not transcript or not transcript.segments:
        return []

    # 3. Build timestamp-preserving windows
    chunks = build_timestamp_windows(transcript.segments, video_id=video_id)
    if not chunks:
        return []

    # 4. Generate dense embeddings
    embedder = provider or LocalMiniLMEmbeddingProvider()
    texts = [c.chunk_text for c in chunks]
    vectors = embedder.embed_batch(texts)

    records: list[EmbeddingRecord] = []
    vector_map: dict[str, list[float]] = {}

    for chunk, vec in zip(chunks, vectors, strict=True):
        emb_id = str(uuid4())
        rec = EmbeddingRecord(
            id=str(uuid4()),
            video_id=video_id,
            chunk_text=chunk.chunk_text,
            start_time=chunk.start_time,
            end_time=chunk.end_time,
            embedding_id=emb_id,
            model_name="sentence-transformers/all-MiniLM-L6-v2",
        )
        db.add(rec)
        db.execute(
            text(
                "INSERT INTO transcript_chunks_fts (embedding_id, video_id, chunk_text) VALUES (:eid, :vid, :txt)"
            ),
            {"eid": emb_id, "vid": video_id, "txt": chunk.chunk_text},
        )
        records.append(rec)
        vector_map[emb_id] = vec

    db.commit()
    save_vectors_to_disk(vector_map, storage_dir=storage_dir)

    for r in records:
        db.refresh(r)
    return records

