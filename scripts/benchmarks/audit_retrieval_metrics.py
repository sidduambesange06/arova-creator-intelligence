#!/usr/bin/env python3
"""Arova Creator Intelligence — Retrieval Benchmark Metrics Audit Script.

Audits Information Retrieval (IR) metrics against ground-truth annotations.
Enforces:
- Schema compatibility across v0.1.0 baseline and modern v0.2.0+ schemas.
- Strict read-only database connections (no mutations to target database).
- Verified foreign-key and database integrity checks.
- Optional migration testing using disposable temporary copies.
- Clear separation between real-media ground truth and synthetic benchmarks.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.ai.retrieval.hybrid_search import run_hybrid_search


def inspect_database_schema(db_path: Path) -> dict[str, Any]:
    """Inspect database schema, version, tables, and integrity without mutating."""
    if not db_path.is_file():
        raise FileNotFoundError(f"Benchmark database file not found: {db_path}")

    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        cur = con.cursor()
        integrity = cur.execute("PRAGMA integrity_check;").fetchall()
        fk_check = cur.execute("PRAGMA foreign_key_check;").fetchall()

        table_rows = cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        ).fetchall()
        tables = {r[0] for r in table_rows}

        video_columns: list[str] = []
        if "videos" in tables:
            col_rows = cur.execute("PRAGMA table_info(videos);").fetchall()
            video_columns = [c[1] for c in col_rows]

        # Detect schema revision
        if "assets" in tables and "asset_id" in video_columns:
            detected_schema = "v0.2.0-media-memory"
        elif "videos" in tables:
            detected_schema = "v0.1.0-alpha-baseline"
        else:
            detected_schema = "unknown-schema"

        video_count = 0
        if "videos" in tables:
            row = cur.execute("SELECT COUNT(*) FROM videos;").fetchone()
            video_count = row[0] if row else 0

        embedding_count = 0
        if "embedding_records" in tables:
            row = cur.execute("SELECT COUNT(*) FROM embedding_records;").fetchone()
            embedding_count = row[0] if row else 0

        return {
            "db_path": str(db_path),
            "integrity": integrity == [("ok",)],
            "foreign_key_violations": len(fk_check),
            "tables": sorted(tables),
            "detected_schema": detected_schema,
            "has_asset_id": "asset_id" in video_columns,
            "video_count": video_count,
            "embedding_records_count": embedding_count,
        }
    finally:
        con.close()


def test_migration_on_disposable_copy(db_path: Path) -> dict[str, Any]:
    """Test Alembic upgrade on a temporary, disposable copy of the database."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_db = Path(tmp_dir) / "disposable_benchmark.db"
        shutil.copy2(db_path, tmp_db)

        # Run migration on the disposable copy
        from app.database.migrator import run_database_migrations
        engine = create_engine(f"sqlite:///{tmp_db.as_posix()}")
        try:
            run_database_migrations(engine=engine, db_path=tmp_db)

            # Verify upgraded schema on disposable copy
            con = sqlite3.connect(str(tmp_db))
            try:
                cur = con.cursor()
                post_integrity = cur.execute("PRAGMA integrity_check;").fetchall()
                post_cols = [c[1] for c in cur.execute("PRAGMA table_info(videos);").fetchall()]
                post_vcount = cur.execute("SELECT COUNT(*) FROM videos;").fetchone()[0]
            finally:
                con.close()

            return {
                "migration_tested": True,
                "disposable_path": str(tmp_db),
                "integrity_after_migration": post_integrity == [("ok",)],
                "has_asset_id_after_migration": "asset_id" in post_cols,
                "video_count_preserved": post_vcount,
            }
        finally:
            engine.dispose()


def run_retrieval_metrics_audit(
    db_path: Path,
    vectors_dir: Path,
    queries_path: Path,
    test_migration: bool = False,
) -> dict[str, Any]:
    """Execute evaluation queries and calculate MRR@10 and Recall@5."""
    schema_info = inspect_database_schema(db_path)
    print(f"[*] Auditing Benchmark DB: {db_path}")
    print(f"    Detected Schema: {schema_info['detected_schema']}")
    print(f"    Integrity: {'OK' if schema_info['integrity'] else 'FAILED'}")
    print(f"    Videos: {schema_info['video_count']} | Embedding Records: {schema_info['embedding_records_count']}")

    migration_report = None
    if test_migration:
        print("[*] Testing migration on disposable copy...")
        migration_report = test_migration_on_disposable_copy(db_path)
        print(f"    Disposable migration success: {migration_report['integrity_after_migration']}")

    # Connect with read-only SQLite URI to guarantee original database cannot be mutated
    read_only_uri = f"sqlite:///file:{db_path.resolve().as_posix()}?mode=ro&uri=true"
    engine = create_engine(read_only_uri, connect_args={"uri": True})
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Fetch target video_id via raw SQL to ensure backwards-compatibility
        video_row = session.execute(text("SELECT id FROM videos LIMIT 1;")).fetchone()
        video_id = str(video_row[0]) if video_row else None
        print(f"    Target Video ID: {video_id}")

        if not queries_path.is_file():
            raise FileNotFoundError(f"Queries file not found: {queries_path}")

        data = json.loads(queries_path.read_text(encoding="utf-8"))
        queries = data.get("queries", [])
        print(f"[*] Running {len(queries)} retrieval evaluation queries against {data.get('media_name', 'media')}...")

        query_results = []
        recalls_at_5 = []
        mrrs_at_10 = []

        for q in queries:
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
            print(f"    - {q['query_id']}: rank={hit_rank}, R@5={r5}, MRR@10={mrr:.4f} ('{q['query']}')")

        mean_r5 = (sum(recalls_at_5) / len(recalls_at_5)) if recalls_at_5 else 0.0
        mean_mrr = (sum(mrrs_at_10) / len(mrrs_at_10)) if mrrs_at_10 else 0.0

        print(f"\n[+] Real Media Retrieval Results (Human Ground-Truth):")
        print(f"    Recall@5 = {mean_r5:.4f}")
        print(f"    MRR@10   = {mean_mrr:.4f}")
        print(f"    (Note: Distinguish real-media retrieval from synthetic MRR@10=1.0000)")

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "benchmark_dataset": "Tears of Steel (2012) 720p Real Media",
            "benchmark_type": "real_world_human_ground_truth",
            "database_schema": schema_info,
            "disposable_migration_test": migration_report,
            "metrics": {
                "recall@5": round(mean_r5, 4),
                "mrr@10": round(mean_mrr, 4),
            },
            "queries": query_results,
        }
    finally:
        session.close()
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit retrieval benchmark metrics against ground truth")
    default_db = Path(r"C:\Arova-Benchmark\workspace\data\benchmark.db")
    if not default_db.is_file():
        default_db = ROOT_DIR / "data" / "app.db"

    default_vectors = Path(r"C:\Arova-Benchmark\workspace\data\vectors")
    if not default_vectors.is_dir():
        default_vectors = ROOT_DIR / "data" / "vectors"

    default_queries = ROOT_DIR / "benchmarks" / "annotations" / "tears_of_steel" / "retrieval_queries.json"

    parser.add_argument("--db-path", type=Path, default=default_db, help="Path to benchmark SQLite database")
    parser.add_argument("--vectors-dir", type=Path, default=default_vectors, help="Path to vectors directory")
    parser.add_argument("--queries-file", type=Path, default=default_queries, help="Path to ground truth queries JSON")
    parser.add_argument("--test-migration", action="store_true", help="Test Alembic upgrade on a temporary disposable copy")
    parser.add_argument("--json-out", type=Path, default=None, help="Optional path to write JSON audit report")

    args = parser.parse_args()

    try:
        report = run_retrieval_metrics_audit(
            db_path=args.db_path,
            vectors_dir=args.vectors_dir,
            queries_path=args.queries_file,
            test_migration=args.test_migration,
        )
        if args.json_out:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 0
    except Exception as exc:
        print(f"\n[!] Audit failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
