"""Stabilization regression tests for DB backup isolation, CORS admin headers, and read-only explorer."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine

from app.core.config import settings
from app.core.security import get_admin_token
from app.database.explorer import (
    get_database_overview,
    get_database_relationships,
    get_table_rows,
    list_database_tables,
)
from app.database.migrator import run_database_migrations
from app.database.session import init_db
from app.main import app


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_migrating_isolated_engine_never_backs_up_live_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_live_dir = tmp_path / "live_data"
    fake_live_dir.mkdir()
    fake_live_db = fake_live_dir / "app.db"
    conn = sqlite3.connect(str(fake_live_db))
    conn.execute("CREATE TABLE sentinel (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    before_hash = _sha256(fake_live_db)

    monkeypatch.setattr(settings, "SQLITE_DB_PATH", str(fake_live_db))

    # 1. Migrating an in-memory engine must create 0 backups of settings.SQLITE_DB_PATH
    mem_engine = create_engine("sqlite:///:memory:")
    init_db(target_engine=mem_engine)
    mem_engine.dispose()

    # 2. Migrating a brand-new temp DB must create 0 backups of settings.SQLITE_DB_PATH
    temp_db = tmp_path / "isolated_test.db"
    temp_engine = create_engine(f"sqlite:///{temp_db.as_posix()}")
    run_database_migrations(engine=temp_engine)
    temp_engine.dispose()

    live_backups = list(fake_live_dir.glob("app.db.backup.*"))
    assert live_backups == [], f"Spurious live DB backups created during isolated migrations: {live_backups}"
    assert _sha256(fake_live_db) == before_hash


def test_cors_preflight_allows_x_admin_token_and_default_preview_origins() -> None:
    from app.core.config import Settings

    default_settings = Settings(_env_file=None)
    assert "http://127.0.0.1:4173" in default_settings.cors_origin_list
    assert "http://localhost:4173" in default_settings.cors_origin_list

    client = TestClient(app)
    resp = client.options(
        "/api/v1/admin/database/overview",
        headers={
            "Host": "127.0.0.1",
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization, X-Admin-Token",
        },
    )
    assert resp.status_code == 200
    allow_headers = resp.headers.get("access-control-allow-headers", "").lower()
    assert "x-admin-token" in allow_headers
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_database_explorer_reads_are_strictly_readonly_and_support_empty_and_fts(
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "empty_schema.db"
    eng = create_engine(f"sqlite:///{db_file.as_posix()}")
    init_db(target_engine=eng)
    eng.dispose()

    # Checkpoint WAL so file bytes are stable before read-only check
    c = sqlite3.connect(str(db_file))
    c.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    c.close()
    before_sha = _sha256(db_file)

    ov = get_database_overview(db_path=db_file)
    assert ov["integrity_status"] == "ok"
    assert ov["mode"] == "ro"
    assert ov["query_only"] is True
    assert ov["table_counts"]["application"] > 0

    tbls = list_database_tables(db_path=db_file)
    assert any(t["name"] == "videos" and t["row_count"] == 0 for t in tbls)

    rels = get_database_relationships(db_path=db_file)
    assert len(rels["tables"]) == ov["table_counts"]["total"]
    assert len(rels["relationships"]) > 0
    for edge in rels["relationships"]:
        assert edge["source_table"]
        assert edge["target_table"]
        assert edge["is_inferred"] is False

    # FTS5 virtual table must return cleanly without 500 error
    if any(t["name"] == "transcript_chunks_fts" for t in tbls):
        fts_rows = get_table_rows("transcript_chunks_fts", limit=10, offset=0, db_path=db_file)
        assert fts_rows["table_name"] == "transcript_chunks_fts"
        assert isinstance(fts_rows["rows"], list)

    assert _sha256(db_file) == before_sha


def test_admin_database_rejects_unauthorized_and_returns_real_fks() -> None:
    client = TestClient(app)
    token = get_admin_token()

    unauth = client.get(
        "/api/v1/admin/database/relationships",
        headers={"Host": "127.0.0.1", "Origin": "http://localhost:5173"},
    )
    assert unauth.status_code == 401

    ok = client.get(
        "/api/v1/admin/database/relationships",
        headers={
            "Host": "127.0.0.1",
            "Origin": "http://localhost:5173",
            "X-Admin-Token": token,
        },
    )
    assert ok.status_code == 200
    body = ok.json()
    assert len(body["relationships"]) > 0
    assert body["relationships"][0]["is_inferred"] is False
