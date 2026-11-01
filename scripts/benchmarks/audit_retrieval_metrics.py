import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.ai.retrieval.hybrid_search import run_hybrid_search
from app.models.entities import Video

db_path = Path(r"C:\Arova-Benchmark\workspace\data\benchmark.db")
vectors_dir = Path(r"C:\Arova-Benchmark\workspace\data\vectors")
engine = create_engine(f"sqlite:///{db_path.as_posix()}")
Session = sessionmaker(bind=engine)
session = Session()

video = session.query(Video).first()
video_id = video.id if video else None
print(f"Video ID: {video_id}")

queries_file = ROOT_DIR / "benchmarks" / "annotations" / "tears_of_steel" / "retrieval_queries.json"
data = json.loads(queries_file.read_text(encoding="utf-8"))

query_results = []
recalls_at_5 = []
mrrs_at_10 = []

for q in data["queries"]:
    resp = run_hybrid_search(
        db=session,
        query=q["query"],
        top_k=10,
        use_reranker=True,
        video_id_filter=video_id,
        storage_dir=str(vectors_dir),
    )
    rel = q["relevant_intervals"]
    hit_rank = 0
    ranks = []
    for rank_idx, h in enumerate(resp.results, start=1):
        is_hit = any(
            (h.start_time <= iv["end_time"] and h.end_time >= iv["start_time"])
            for iv in rel
        )
        if is_hit:
            ranks.append(rank_idx)
            if hit_rank == 0:
                hit_rank = rank_idx

    r5 = 1.0 if (0 < hit_rank <= 5) else 0.0
    mrr = (1.0 / hit_rank) if (0 < hit_rank <= 10) else 0.0
    recalls_at_5.append(r5)
    mrrs_at_10.append(mrr)
    query_results.append({
        "query_id": q["query_id"],
        "query": q["query"],
        "hit_rank": hit_rank,
        "all_hit_ranks": ranks,
        "recall@5": r5,
        "mrr@10": mrr,
    })
    print(f"{q['query_id']}: hit_rank={hit_rank}, all_ranks={ranks}, R@5={r5}, MRR@10={mrr:.4f}")

mean_r5 = sum(recalls_at_5) / len(recalls_at_5)
mean_mrr = sum(mrrs_at_10) / len(mrrs_at_10)
print(f"\nAggregated: Recall@5={mean_r5:.4f}, MRR@10={mean_mrr:.4f}")

