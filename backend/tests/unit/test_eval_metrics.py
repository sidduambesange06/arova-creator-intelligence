import math
from pathlib import Path

from fastapi.testclient import TestClient

from app.ai.evaluation.eval_harness import run_evaluation
from app.ai.evaluation.metrics import (
    compute_mrr_at_k,
    compute_ndcg_at_k,
    compute_recall_at_k,
    evaluate_query_ranking,
)
from app.main import app


def test_ranking_metrics_formulas() -> None:
    # 1. Recall@K
    retrieved = ["doc_A", "doc_B", "doc_C", "doc_D"]
    relevant = {"doc_B", "doc_E"}
    # at k=1: retrieved=["doc_A"] -> 0/2 = 0.0
    assert compute_recall_at_k(retrieved, relevant, k=1) == 0.0
    # at k=2: retrieved=["doc_A", "doc_B"] -> 1/2 = 0.5
    assert compute_recall_at_k(retrieved, relevant, k=2) == 0.5
    # at k=4: 1/2 = 0.5
    assert compute_recall_at_k(retrieved, relevant, k=4) == 0.5

    # 2. MRR@10
    # doc_B is at rank 2 (1-indexed) -> 1/2 = 0.5
    assert compute_mrr_at_k(retrieved, relevant, k=10) == 0.5
    # no relevant docs in top 10 -> 0.0
    assert compute_mrr_at_k(["x", "y"], {"z"}, k=10) == 0.0

    # 3. NDCG@10
    # doc_B at rank 2 -> DCG = 1.0 / log2(2 + 1) = 1.0 / log2(3) = 0.6309
    # IDCG (1 relevant doc at rank 1) = 1.0 / log2(1 + 1) = 1.0
    # NDCG = 0.6309 / 1.0 = 0.6309
    ndcg = compute_ndcg_at_k(retrieved, {"doc_B"}, k=10)
    expected_ndcg = round(1.0 / math.log2(3), 4)
    assert abs(ndcg - expected_ndcg) < 1e-3


def test_eval_harness_and_endpoints(tmp_path: Path) -> None:
    # 1. Run evaluation on golden set
    report = run_evaluation(storage_dir=tmp_path / "eval_vecs")
    assert report.num_queries == 10
    assert report.corpus_size == 10
    assert report.stage1_metrics.mrr_at_10 > 0.0
    assert report.stage2_metrics.mrr_at_10 > 0.0
    assert report.stage1_latency_p50_ms >= 0.0
    assert report.stage2_latency_p50_ms >= 0.0

    # 2. Test endpoints
    with TestClient(app) as client:
        run_res = client.post("/api/v1/ml/eval/run")
        assert run_res.status_code == 200
        assert run_res.json()["num_queries"] == 10

        rep_res = client.get("/api/v1/ml/eval/report")
        assert rep_res.status_code == 200
        assert "stage1_metrics" in rep_res.json()

        tel_res = client.get("/api/v1/system/telemetry")
        assert tel_res.status_code == 200
        body = tel_res.json()
        assert "worker" in body
        assert "ml_benchmark" in body
        assert body["ml_benchmark"]["mrr_at_10_stage1"] is not None

