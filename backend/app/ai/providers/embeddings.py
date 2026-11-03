from dataclasses import dataclass
import json
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.retrieval.chunker import build_timestamp_windows
from app.core.config import settings
from app.models.entities import EmbeddingRecord, Transcript, VideoScene


class EmbeddingProvider(Protocol):
    def is_available(self) -> bool: ...
    def embed_text(self, text: str) -> list[float]: ...
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class LocalMiniLMEmbeddingProvider:
    """Embedding provider using sentence-transformers all-MiniLM-L6-v2.

    Enforces genuine embedding inference. When offline or uninstalled, reports
    unavailable rather than fabricating synthetic hash projections.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self.dim = 384
        self._model = None
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._model = SentenceTransformer(model_name)
        except Exception:
            self._model = None

    def is_available(self) -> bool:
        return self._model is not None

    def embed_text(self, text: str) -> list[float]:
        res = self.embed_batch([text])
        return res[0] if res else []

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._model is not None:
            try:
                embeddings = self._model.encode(texts, normalize_embeddings=True)
                return [e.tolist() for e in embeddings]
            except Exception:
                pass
        return []


def get_indic_tokenchars() -> str:
    chars = []
    # Devanagari, Tamil, Telugu, and Kannada combining vowel marks and virama
    for cp in list(range(0x0901, 0x0904)) + [0x093C] + list(range(0x093E, 0x0950)) + list(range(0x0951, 0x0958)) + list(range(0x0962, 0x0964)):
        chars.append(chr(cp))
    for cp in [0x0B82] + list(range(0x0BBE, 0x0BCE)) + [0x0BD7]:
        chars.append(chr(cp))
    for cp in list(range(0x0C00, 0x0C04)) + list(range(0x0C3E, 0x0C4E)) + list(range(0x0C55, 0x0C57)) + list(range(0x0C62, 0x0C64)):
        chars.append(chr(cp))
    for cp in list(range(0x0C81, 0x0C84)) + [0x0CBC] + list(range(0x0CBE, 0x0CCE)) + list(range(0x0CD5, 0x0CD7)) + list(range(0x0CE2, 0x0CE4)):
        chars.append(chr(cp))
    return "".join(chars)


def _ensure_fts5_table(db: Session) -> None:
    tokenchars = get_indic_tokenchars().replace("'", "''")
    db.execute(
        text(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS transcript_chunks_fts USING fts5(
                embedding_id UNINDEXED,
                video_id UNINDEXED,
                chunk_text,
                tokenize="unicode61 tokenchars '{tokenchars}'"
            );
            """
        )
    )
    db.commit()


def _get_vector_storage_path(storage_dir: str | Path | None = None) -> Path:
    dir_path = Path(storage_dir or getattr(settings, "VECTOR_STORAGE_DIR", None) or getattr(settings, "CHROMA_PERSIST_DIR", None) or "./data/vectors")
    dir_path.mkdir(parents=True, exist_ok=True)
    return (dir_path / "embeddings.json").resolve()


def save_vectors_to_disk(vectors_dict: dict[str, list[float]], storage_dir: str | Path | None = None) -> None:
    if not vectors_dict:
        return
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

    # 3. Retrieve video scenes to fuse on-screen visual text
    scenes = db.query(VideoScene).filter_by(video_id=video_id).order_by(VideoScene.start_time.asc()).all()

    # 4. Build timestamp-preserving windows with multimodal context
    chunks = build_timestamp_windows(transcript.segments, video_id=video_id, scenes=scenes)
    if not chunks:
        return []

    # 5. Generate dense embeddings ONLY if provider is available
    embedder = provider or LocalMiniLMEmbeddingProvider()
    texts = [c.chunk_text for c in chunks]
    vectors: list[list[float]] = []
    if hasattr(embedder, "is_available"):
        if embedder.is_available():
            vectors = embedder.embed_batch(texts)
    else:
        try:
            vectors = embedder.embed_batch(texts)
        except Exception:
            vectors = []

    has_vectors = bool(vectors and len(vectors) == len(chunks))
    records: list[EmbeddingRecord] = []
    vector_map: dict[str, list[float]] = {}

    for idx, chunk in enumerate(chunks):
        emb_id = str(uuid4())
        rec = EmbeddingRecord(
            id=str(uuid4()),
            video_id=video_id,
            chunk_text=chunk.chunk_text,
            start_time=chunk.start_time,
            end_time=chunk.end_time,
            embedding_id=emb_id,
            model_name=getattr(embedder, "model_name", "all-MiniLM-L6-v2") if has_vectors else "lexical-fts5-only",
        )
        db.add(rec)
        db.execute(
            text(
                "INSERT INTO transcript_chunks_fts (embedding_id, video_id, chunk_text) VALUES (:eid, :vid, :txt)"
            ),
            {"eid": emb_id, "vid": video_id, "txt": chunk.chunk_text},
        )
        records.append(rec)
        if has_vectors and vectors[idx]:
            vector_map[emb_id] = vectors[idx]

    db.commit()

    if vector_map:
        save_vectors_to_disk(vector_map, storage_dir=storage_dir)

    for r in records:
        db.refresh(r)
    return records
