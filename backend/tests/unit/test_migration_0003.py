"""Unit tests for Alembic migration 0003_indic_fts5_tokenization."""

from __future__ import annotations

from pathlib import Path
import sqlite3
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.database.migrator import _get_alembic_config

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent


def test_migration_0003_upgrade_downgrade_idempotence(tmp_path):
    test_db_path = tmp_path / "test_migration_0003.db"
    db_url = f"sqlite:///{test_db_path.as_posix()}"
    engine = create_engine(db_url)

    cfg = _get_alembic_config(engine)

    # 1. Upgrade through head (includes 0001, 0002, 0003)
    command.upgrade(cfg, "head")

    # Verify alembic_version is at 0003_indic_fts5_tokenization
    with engine.connect() as conn:
        rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert rev == "0003_indic_fts5_tokenization"

        # Verify transcript_chunks_fts virtual table exists
        tables = [row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()]
        assert "transcript_chunks_fts" in tables

        # Insert Indic words and test MATCH
        conn.execute(
            text("INSERT INTO transcript_chunks_fts (embedding_id, video_id, chunk_text) VALUES ('e1', 'v1', 'भारत और नमस्ते')")
        )
        conn.commit()

        # Check vocab tokens: "भारत" and "नमस्ते" must be preserved intact
        vocab_rows = conn.execute(text("SELECT term FROM transcript_chunks_fts_vocab")).fetchall() if "transcript_chunks_fts_vocab" in tables else []
        # Query MATCH
        match_res = conn.execute(
            text("SELECT count(*) FROM transcript_chunks_fts WHERE transcript_chunks_fts MATCH '\"भारत\"'")
        ).scalar()
        assert match_res == 1

        match_res2 = conn.execute(
            text("SELECT count(*) FROM transcript_chunks_fts WHERE transcript_chunks_fts MATCH '\"नमस्ते\"'")
        ).scalar()
        assert match_res2 == 1

    # 2. Downgrade to 0002_task4_media_memory
    command.downgrade(cfg, "0002_task4_media_memory")
    with engine.connect() as conn:
        rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert rev == "0002_task4_media_memory"

    # 3. Re-upgrade to head (idempotence)
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert rev == "0003_indic_fts5_tokenization"

    engine.dispose()

