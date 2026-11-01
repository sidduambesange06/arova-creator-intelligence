import pytest
from app.ai.evaluation.metrics import (
    compute_mrr_at_k,
    compute_ndcg_at_k,
    compute_recall_at_k,
    evaluate_query_ranking,
    average_metrics,
)


def test_retrieval_metric_exact_reconciliation():
    """
    Verifies the mathematical reconciliation of the Tears of Steel benchmark queries:
    - tos_q1: rank 2 -> MRR=0.5000, Recall@5=1.0, NDCG=0.6309
    - tos_q2: rank 2 -> MRR=0.5000, Recall@5=1.0, NDCG=0.6309
    - tos_q3: rank 7 -> MRR=0.1429, Recall@5=0.0, NDCG=0.3333
    - tos_q4: unranked -> MRR=0.0000, Recall@5=0.0, NDCG=0.0000
    - tos_q5: unranked -> MRR=0.0000, Recall@5=0.0, NDCG=0.0000

    Mean Recall@5 = (1.0 + 1.0 + 0.0 + 0.0 + 0.0) / 5 = 0.4000
    Mean MRR@10   = (0.5 + 0.5 + 0.142857 + 0.0 + 0.0) / 5 = 0.2286
    Mean NDCG@10  = (0.6309 + 0.6309 + 0.3333 + 0.0 + 0.0) / 5 = 0.3190
    """
    # Simulate retrieved doc IDs where doc "target" is the relevant passage
    q1_retrieved = ["irrel_1", "target", "irrel_2", "irrel_3"]
    q2_retrieved = ["irrel_1", "target", "irrel_2", "irrel_3"]
    q3_retrieved = ["irrel_1", "irrel_2", "irrel_3", "irrel_4", "irrel_5", "irrel_6", "target"]
    q4_retrieved = ["irrel_1", "irrel_2", "irrel_3", "irrel_4", "irrel_5"]
    q5_retrieved = ["irrel_1", "irrel_2", "irrel_3", "irrel_4", "irrel_5"]

    relevant = {"target"}

    m1 = evaluate_query_ranking(q1_retrieved, relevant)
    m2 = evaluate_query_ranking(q2_retrieved, relevant)
    m3 = evaluate_query_ranking(q3_retrieved, relevant)
    m4 = evaluate_query_ranking(q4_retrieved, relevant)
    m5 = evaluate_query_ranking(q5_retrieved, relevant)

    assert m1.recall_at_5 == 1.0
    assert m1.mrr_at_10 == 0.5000
    assert pytest.approx(m1.ndcg_at_10, abs=0.001) == 0.6309

    assert m2.recall_at_5 == 1.0
    assert m2.mrr_at_10 == 0.5000

    assert m3.recall_at_5 == 0.0
    assert pytest.approx(m3.mrr_at_10, abs=0.001) == 0.1429
    assert pytest.approx(m3.ndcg_at_10, abs=0.001) == 0.3333

    assert m4.recall_at_5 == 0.0
    assert m4.mrr_at_10 == 0.0

    assert m5.recall_at_5 == 0.0
    assert m5.mrr_at_10 == 0.0

    avg = average_metrics([m1, m2, m3, m4, m5])
    assert avg.recall_at_5 == 0.4000
    assert pytest.approx(avg.mrr_at_10, abs=0.0001) == 0.2286
    assert pytest.approx(avg.ndcg_at_10, abs=0.001) == 0.3190


def test_compute_metrics_edge_cases():
    assert compute_recall_at_k([], {"a"}, k=5) == 0.0
    assert compute_recall_at_k(["a"], set(), k=5) == 0.0
    assert compute_mrr_at_k([], {"a"}, k=10) == 0.0
    assert compute_ndcg_at_k([], {"a"}, k=10) == 0.0

