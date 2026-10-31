from dataclasses import asdict, dataclass
import re
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.providers.embeddings import (
    EmbeddingProvider,
    LocalMiniLMEmbeddingProvider,
    load_vectors_from_disk,
)
from app.ai.reranking.cross_encoder_reranker import CrossEncoderReranker
from app.models.entities import EmbeddingRecord, Video


@dataclass
class SearchResultItem:
    embedding_id: str
    video_id: str
    filename: str
    chunk_text: str
    start_time: float
    end_time: float
    stage1_score: float
    rerank_score: float
    rank: int


@dataclass
class HybridSearchResponse:
    query: str
    total_results: int
    stage1_ms: float
    stage2_rerank_ms: float
    total_ms: float
    results: list[SearchResultItem]


def _sanitize_fts_query(raw_query: str) -> str:
    tokens = re.findall(r"\w+", raw_query)
    if not tokens:
        return '""'
    return " OR ".join(f'"{t}"' for t in tokens)


def run_hybrid_search(
    db: Session,
    query: str,
    top_k: int = 10,
    use_reranker: bool = True,
    video_id_filter: str | None = None,
    storage_dir: str | None = None,
    embedder: EmbeddingProvider | None = None,
    reranker: CrossEncoderReranker | None = None,
) -> HybridSearchResponse:
    t_start = time.perf_counter()
    q_clean = query.strip()
    if not q_clean:
        return HybridSearchResponse(
            query=query,
            total_results=0,
            stage1_ms=0.0,
            stage2_rerank_ms=0.0,
            total_ms=0.0,
            results=[],
        )

    t_s1_start = time.perf_counter()
    active_embedder = embedder or LocalMiniLMEmbeddingProvider()
    q_vec = active_embedder.embed_text(q_clean)
    stored_vectors = load_vectors_from_disk(storage_dir=storage_dir)

    # 1. Dense Vector Scoring (Cosine similarity)
    dense_scores: dict[str, float] = {}
    for emb_id, vec in stored_vectors.items():
        if len(vec) == len(q_vec):
            # L2 normalized dot product = cosine similarity
            sim = sum(a * b for a, b in zip(q_vec, vec, strict=False))
            dense_scores[emb_id] = round(sim, 4)

    # Filter by video_id if requested
    if video_id_filter:
        valid_ids = {
            r[0]
            for r in db.execute(
                text("SELECT embedding_id FROM embedding_records WHERE video_id = :vid"),
                {"vid": video_id_filter},
            ).fetchall()
        }
        dense_scores = {k: v for k, v in dense_scores.items() if k in valid_ids}

    sorted_dense = sorted(dense_scores.items(), key=lambda x: x[1], reverse=True)[:20]
    dense_ranks = {item[0]: rank for rank, item in enumerate(sorted_dense, start=1)}

    # 2. Lexical Scoring (SQLite FTS5)
    fts_query = _sanitize_fts_query(q_clean)
    lexical_ranks: dict[str, int] = {}
    try:
        sql = """
            SELECT embedding_id, rank
            FROM transcript_chunks_fts
            WHERE transcript_chunks_fts MATCH :fts_q
        """
        params: dict[str, Any] = {"fts_q": fts_query}
        if video_id_filter:
            sql += " AND video_id = :vid"
            params["vid"] = video_id_filter
        sql += " ORDER BY rank LIMIT 20"

        fts_rows = db.execute(text(sql), params).fetchall()
        for rank, row in enumerate(fts_rows, start=1):
            lexical_ranks[str(row[0])] = rank
    except Exception:
        lexical_ranks = {}

    # 3. Reciprocal Rank Fusion (RRF)
    all_candidate_ids = set(dense_ranks.keys()) | set(lexical_ranks.keys())
    rrf_scores: dict[str, float] = {}
    k_const = 60.0

    for cid in all_candidate_ids:
        score = 0.0
        if cid in dense_ranks:
            score += 1.0 / (k_const + dense_ranks[cid])
        if cid in lexical_ranks:
            score += 1.0 / (k_const + lexical_ranks[cid])
        rrf_scores[cid] = round(score, 6)

    # Fetch candidate records from DB
    candidate_records = (
        db.query(EmbeddingRecord)
        .filter(EmbeddingRecord.embedding_id.in_(all_candidate_ids))
        .all()
    ) if all_candidate_ids else []

    record_map = {r.embedding_id: r for r in candidate_records}
    video_map = {
        v.id: v.filename
        for v in db.query(Video).filter(Video.id.in_({r.video_id for r in candidate_records})).all()
    } if candidate_records else {}

    candidates: list[dict[str, Any]] = []
    for cid in sorted(all_candidate_ids, key=lambda x: rrf_scores[x], reverse=True):
        rec = record_map.get(cid)
        if rec:
            candidates.append(
                {
                    "embedding_id": cid,
                    "video_id": rec.video_id,
                    "filename": video_map.get(rec.video_id, "unknown.mp4"),
                    "chunk_text": rec.chunk_text,
                    "start_time": rec.start_time,
                    "end_time": rec.end_time,
                    "stage1_score": rrf_scores[cid],
                    "rerank_score": rrf_scores[cid],
                }
            )

    t_s1_end = time.perf_counter()
    stage1_ms = round((t_s1_end - t_s1_start) * 1000.0, 2)

    # 4. Stage-2 ML Cross-Encoder Re-Ranking
    stage2_rerank_ms = 0.0
    if use_reranker and candidates:
        active_reranker = reranker or CrossEncoderReranker()
        reranked_items, stage2_rerank_ms = active_reranker.rerank(
            query=q_clean,
            candidates=candidates[:20],
            top_k=top_k,
        )
        final_list = reranked_items
    else:
        final_list = candidates[:top_k]

    results: list[SearchResultItem] = []
    for rank, item in enumerate(final_list, start=1):
        results.append(
            SearchResultItem(
                embedding_id=item["embedding_id"],
                video_id=item["video_id"],
                filename=item["filename"],
                chunk_text=item["chunk_text"],
                start_time=item["start_time"],
                end_time=item["end_time"],
                stage1_score=item["stage1_score"],
                rerank_score=item["rerank_score"],
                rank=rank,
            )
        )

    t_total = (time.perf_counter() - t_start) * 1000.0
    return HybridSearchResponse(
        query=q_clean,
        total_results=len(results),
        stage1_ms=stage1_ms,
        stage2_rerank_ms=stage2_rerank_ms,
        total_ms=round(t_total, 2),
        results=results,
    )

