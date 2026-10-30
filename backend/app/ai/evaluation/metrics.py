from dataclasses import dataclass
import math


@dataclass(frozen=True)
class RankingMetrics:
    mrr_at_10: float
    ndcg_at_10: float
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    recall_at_10: float


def compute_recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    top_k_set = set(retrieved_ids[:k])
    intersect = len(top_k_set & relevant_ids)
    return round(intersect / float(len(relevant_ids)), 4)


def compute_mrr_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int = 10) -> float:
    if not relevant_ids:
        return 0.0
    for idx, doc_id in enumerate(retrieved_ids[:k], start=1):
        if doc_id in relevant_ids:
            return round(1.0 / idx, 4)
    return 0.0


def compute_ndcg_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int = 10) -> float:
    if not relevant_ids:
        return 0.0

    dcg = 0.0
    for idx, doc_id in enumerate(retrieved_ids[:k], start=1):
        rel = 1.0 if doc_id in relevant_ids else 0.0
        if rel > 0.0:
            dcg += rel / math.log2(idx + 1)

    idcg = 0.0
    num_relevant = min(len(relevant_ids), k)
    for idx in range(1, num_relevant + 1):
        idcg += 1.0 / math.log2(idx + 1)

    if idcg == 0.0:
        return 0.0
    return round(dcg / idcg, 4)


def evaluate_query_ranking(retrieved_ids: list[str], relevant_ids: set[str]) -> RankingMetrics:
    return RankingMetrics(
        mrr_at_10=compute_mrr_at_k(retrieved_ids, relevant_ids, k=10),
        ndcg_at_10=compute_ndcg_at_k(retrieved_ids, relevant_ids, k=10),
        recall_at_1=compute_recall_at_k(retrieved_ids, relevant_ids, k=1),
        recall_at_3=compute_recall_at_k(retrieved_ids, relevant_ids, k=3),
        recall_at_5=compute_recall_at_k(retrieved_ids, relevant_ids, k=5),
        recall_at_10=compute_recall_at_k(retrieved_ids, relevant_ids, k=10),
    )


def average_metrics(metrics_list: list[RankingMetrics]) -> RankingMetrics:
    if not metrics_list:
        return RankingMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    n = float(len(metrics_list))
    return RankingMetrics(
        mrr_at_10=round(sum(m.mrr_at_10 for m in metrics_list) / n, 4),
        ndcg_at_10=round(sum(m.ndcg_at_10 for m in metrics_list) / n, 4),
        recall_at_1=round(sum(m.recall_at_1 for m in metrics_list) / n, 4),
        recall_at_3=round(sum(m.recall_at_3 for m in metrics_list) / n, 4),
        recall_at_5=round(sum(m.recall_at_5 for m in metrics_list) / n, 4),
        recall_at_10=round(sum(m.recall_at_10 for m in metrics_list) / n, 4),
    )
