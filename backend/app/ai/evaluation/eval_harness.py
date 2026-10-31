from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.evaluation.metrics import (
    RankingMetrics,
    average_metrics,
    evaluate_query_ranking,
)
from app.ai.providers.embeddings import (
    LocalMiniLMEmbeddingProvider,
    index_video_chunks,
)
from app.ai.retrieval.hybrid_search import run_hybrid_search
from app.core.config import settings
from app.database.session import Base, init_db
from app.models.entities import Transcript, TranscriptSegment, Video


@dataclass
class EvaluationReport:
    timestamp: str
    num_queries: int
    corpus_size: int
    stage1_metrics: RankingMetrics
    stage2_metrics: RankingMetrics
    stage1_latency_p50_ms: float
    stage1_latency_p95_ms: float
    stage2_latency_p50_ms: float
    stage2_latency_p95_ms: float
    mrr_delta_percent: float
    ndcg_delta_percent: float


_latest_eval_report: EvaluationReport | None = None


def get_latest_evaluation_report() -> EvaluationReport | None:
    global _latest_eval_report
    if _latest_eval_report is not None:
        return _latest_eval_report
    disk_path = Path(settings.DATA_DIR) / "eval_report_latest.json"
    if disk_path.is_file():
        try:
            data = json.loads(disk_path.read_text(encoding="utf-8"))
            s1 = RankingMetrics(**data["stage1_metrics"])
            s2 = RankingMetrics(**data["stage2_metrics"])
            del data["stage1_metrics"]
            del data["stage2_metrics"]
            _latest_eval_report = EvaluationReport(
                stage1_metrics=s1,
                stage2_metrics=s2,
                **data,
            )
            return _latest_eval_report
        except Exception:
            return None
    return None


def run_evaluation(
    manifest_path: Path | str | None = None,
    storage_dir: Path | str | None = None,
) -> EvaluationReport:
    global _latest_eval_report

    default_manifest = Path("sample_data/evaluation_golden_set.json")
    target_manifest = Path(manifest_path) if manifest_path else default_manifest
    if not target_manifest.is_file():
        # try relative to project root
        target_manifest = Path(__file__).resolve().parent.parent.parent.parent.parent / "sample_data" / "evaluation_golden_set.json"

    if not target_manifest.is_file():
        raise FileNotFoundError(f"Evaluation golden set not found: {target_manifest}")

    data = json.loads(target_manifest.read_text(encoding="utf-8"))
    corpus = data.get("corpus", [])
    queries = data.get("queries", [])

    # Setup isolated in-memory test SQLite DB
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(test_engine)
    TestingSession = sessionmaker(bind=test_engine)

    embedder = LocalMiniLMEmbeddingProvider()
    temp_vec_dir = Path(storage_dir or (Path(settings.DATA_DIR) / "eval_vectors"))

    with TestingSession() as db:
        # 1. Populate corpus into DB
        video_ids = sorted(list({c["video_id"] for c in corpus}))
        for vid in video_ids:
            v_obj = Video(
                id=vid,
                filename=f"{vid}.mp4",
                file_path=f"/eval/{vid}.mp4",
                file_hash=f"hash_{vid}",
                duration=120.0,
            )
            db.add(v_obj)
            db.commit()

            t_obj = Transcript(
                id=f"t_{vid}",
                video_id=vid,
                language="en",
                model_name="golden-eval-model",
                full_text=" ".join(c["text"] for c in corpus if c["video_id"] == vid),
            )
            db.add(t_obj)
            db.commit()

            for c in corpus:
                if c["video_id"] == vid:
                    db.add(
                        TranscriptSegment(
                            id=c["id"],
                            transcript_id=t_obj.id,
                            video_id=vid,
                            start_time=c["start_time"],
                            end_time=c["end_time"],
                            text=c["text"],
                        )
                    )
            db.commit()
            index_video_chunks(db, vid, provider=embedder, storage_dir=temp_vec_dir)

        # 2. Benchmark queries
        stage1_metrics_list = []
        stage2_metrics_list = []
        s1_latencies = []
        s2_latencies = []

        for q_entry in queries:
            q_text = q_entry["query"]
            rel_ids = set(q_entry["relevant_ids"])

            # Stage 1 search (no cross-encoder)
            t0 = time.perf_counter()
            resp_s1 = run_hybrid_search(
                db=db,
                query=q_text,
                top_k=10,
                use_reranker=False,
                storage_dir=str(temp_vec_dir),
                embedder=embedder,
            )
            s1_latencies.append((time.perf_counter() - t0) * 1000.0)
            # Find which corpus items matched by text segment overlap
            s1_retrieved = []
            for r in resp_s1.results:
                matched_c = next((c["id"] for c in corpus if c["text"] in r.chunk_text or r.chunk_text in c["text"]), None)
                if matched_c:
                    s1_retrieved.append(matched_c)
            stage1_metrics_list.append(evaluate_query_ranking(s1_retrieved, rel_ids))

            # Stage 2 search (with cross-encoder re-ranking)
            t1 = time.perf_counter()
            resp_s2 = run_hybrid_search(
                db=db,
                query=q_text,
                top_k=10,
                use_reranker=True,
                storage_dir=str(temp_vec_dir),
                embedder=embedder,
            )
            s2_latencies.append((time.perf_counter() - t1) * 1000.0)
            s2_retrieved = []
            for r in resp_s2.results:
                matched_c = next((c["id"] for c in corpus if c["text"] in r.chunk_text or r.chunk_text in c["text"]), None)
                if matched_c:
                    s2_retrieved.append(matched_c)
            stage2_metrics_list.append(evaluate_query_ranking(s2_retrieved, rel_ids))

    Base.metadata.drop_all(bind=test_engine)

    avg_s1 = average_metrics(stage1_metrics_list)
    avg_s2 = average_metrics(stage2_metrics_list)

    s1_latencies.sort()
    s2_latencies.sort()
    p50_idx = max(0, int(len(s1_latencies) * 0.5) - 1)
    p95_idx = max(0, int(len(s1_latencies) * 0.95) - 1)

    mrr_delta = round(((avg_s2.mrr_at_10 - avg_s1.mrr_at_10) / max(avg_s1.mrr_at_10, 0.001)) * 100.0, 2)
    ndcg_delta = round(((avg_s2.ndcg_at_10 - avg_s1.ndcg_at_10) / max(avg_s1.ndcg_at_10, 0.001)) * 100.0, 2)

    report = EvaluationReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        num_queries=len(queries),
        corpus_size=len(corpus),
        stage1_metrics=avg_s1,
        stage2_metrics=avg_s2,
        stage1_latency_p50_ms=round(s1_latencies[p50_idx], 2) if s1_latencies else 0.0,
        stage1_latency_p95_ms=round(s1_latencies[p95_idx], 2) if s1_latencies else 0.0,
        stage2_latency_p50_ms=round(s2_latencies[p50_idx], 2) if s2_latencies else 0.0,
        stage2_latency_p95_ms=round(s2_latencies[p95_idx], 2) if s2_latencies else 0.0,
        mrr_delta_percent=mrr_delta,
        ndcg_delta_percent=ndcg_delta,
    )

    _latest_eval_report = report
    # Persist report
    try:
        disk_path = Path(settings.DATA_DIR) / "eval_report_latest.json"
        disk_path.parent.mkdir(parents=True, exist_ok=True)
        dump_data = asdict(report)
        disk_path.write_text(json.dumps(dump_data, indent=2), encoding="utf-8")
    except Exception:
        pass

    return report

