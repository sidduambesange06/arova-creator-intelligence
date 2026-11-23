"""Subtitle Retrieval Proxy Evaluation (Recall@5) for Tears of Steel.

Evaluates 30 distinctive dialogue phrases sampled deterministically (seed 42)
from official Blender TOS-en.srt subtitles against the ASR-built FTS5 / hybrid index.
A query is considered a hit if a top-5 result overlaps the cue time range within 5 seconds.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import re
import sys
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT_DIR / "reports" / "benchmarks" / "tears_of_steel_subtitles_manifest.json"
REPORTS_DIR = ROOT_DIR / "reports" / "benchmarks"

NEGATIVE_QUERIES = [
    "Enterprise warp drive nacelle malfunction",
    "Quantum entanglement cryptographic supercomputer",
    "Medieval dragon castle siege catapult",
    "Ancient Roman gladiator colosseum championship",
    "Deep sea hydrothermal vent bacterial ecosystem",
]


def select_distinctive_cues(cues: list[dict[str, Any]], count: int = 30, seed: int = 42) -> list[dict[str, Any]]:
    # Filter cues with at least 3 distinct alphabetic words and length > 12
    candidates = []
    for c in cues:
        txt = c["text"]
        words = [w for w in re.findall(r"[A-Za-z]+", txt) if len(w) > 1]
        if len(words) >= 3 and len(txt) >= 12:
            candidates.append(c)

    rng = random.Random(seed)
    rng.shuffle(candidates)
    return sorted(candidates[:count], key=lambda x: x["start_seconds"])


def evaluate_retrieval_proxy(db_path: Path, manifest_path: Path = DEFAULT_MANIFEST, top_k: int = 5) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cues = manifest["dialogue_cues"]
    selected_queries = select_distinctive_cues(cues, count=30, seed=42)

    db_url = f"sqlite:///{db_path.as_posix()}"
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)

    results: list[dict[str, Any]] = []
    hits = 0

    with SessionLocal() as session:
        # Check if transcript_chunks_fts or embedding_records exists
        tables = [r[0] for r in session.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()]
        if "transcript_chunks_fts" not in tables:
            return {
                "status": "NOT_APPLICABLE",
                "reason": "transcript_chunks_fts table not found in database",
                "recall_at_5": None,
                "hits": 0,
                "total_queries": len(selected_queries),
            }

        for idx, q_item in enumerate(selected_queries, start=1):
            q_text = q_item["text"]
            cue_start = q_item["start_seconds"]
            cue_end = q_item["end_seconds"]

            # Query FTS table
            # Strip punctuation for query
            punct_pattern = r'[!"#$%&\'()*+,-./:;<=>?@\[\\\]^_`{|}~]'
            clean_q = re.sub(punct_pattern, " ", q_text)
            tokens = [t.strip() for t in clean_q.split() if len(t.strip()) > 2]
            fts_q = " OR ".join(f'"{t}"' for t in tokens) if tokens else '""'

            sql = """
                SELECT r.embedding_id, r.chunk_text, r.start_time, r.end_time, f.rank
                FROM transcript_chunks_fts f
                JOIN embedding_records r ON f.embedding_id = r.embedding_id
                WHERE transcript_chunks_fts MATCH :q
                ORDER BY f.rank
                LIMIT :k
            """
            try:
                rows = session.execute(text(sql), {"q": fts_q, "k": top_k}).fetchall()
            except Exception:
                rows = []

            # Check if any top_k result overlaps [cue_start - 5.0, cue_end + 5.0]
            is_hit = False
            matched_row = None
            for r in rows:
                r_start = r[2]
                r_end = r[3]
                # Overlap condition
                if not (r_end < (cue_start - 5.0) or r_start > (cue_end + 5.0)):
                    is_hit = True
                    matched_row = {
                        "chunk_text": r[1],
                        "start_time": r[2],
                        "end_time": r[3],
                    }
                    break

            if is_hit:
                hits += 1

            results.append({
                "query_index": idx,
                "query_text": q_text,
                "cue_interval": [cue_start, cue_end],
                "is_hit": is_hit,
                "top_k_count": len(rows),
                "matched_result": matched_row,
            })

        # Negative query test
        negative_hits = 0
        for nq in NEGATIVE_QUERIES:
            clean_nq = re.sub(punct_pattern, " ", nq)
            tokens = [t.strip() for t in clean_nq.split() if len(t.strip()) > 2]
            fts_q = " OR ".join(f'"{t}"' for t in tokens) if tokens else '""'
            try:
                rows = session.execute(text(sql), {"q": fts_q, "k": top_k}).fetchall()
                if rows:
                    negative_hits += 1
            except Exception:
                pass

    recall_at_5 = hits / float(len(selected_queries)) if selected_queries else 0.0

    report = {
        "status": "COMPLETED",
        "benchmark": "Tears of Steel Subtitle Retrieval Proxy (Recall@5)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_queries": len(selected_queries),
        "hits_at_5": hits,
        "recall_at_5": round(recall_at_5, 4),
        "negative_queries_tested": len(NEGATIVE_QUERIES),
        "negative_queries_returned_rows": negative_hits,
        "queries": results,
    }

    report_path = REPORTS_DIR / "tears_of_steel_retrieval_proxy_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Subtitle Retrieval Proxy: Recall@5 = {hits}/{len(selected_queries)} ({recall_at_5 * 100:.1f}%)")
    print(f"Report saved to {report_path}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Subtitle Retrieval Proxy")
    parser.add_argument("--db-path", type=Path, required=True, help="Path to SQLite database containing ASR index")
    args = parser.parse_args()
    evaluate_retrieval_proxy(args.db_path)
