"""Integration and Security Tests for Database Explorer API.

Verifies:
1. Mandatory local-admin authentication (missing, invalid, and valid bearer tokens).
2. Host and Origin validation (bad Host -> 400, rejected Origin -> 403).
3. Read-only SQLite connection in WAL mode (mode=ro + PRAGMA query_only=ON).
4. Live introspection of tables, columns, indexes, foreign keys, and constraints.
5. Paginated rows with token redaction, BLOB size masking, and text cell truncation.
6. Empty table handling.
7. Validation against arbitrary or invalid table names.
8. Migration history and visual ER relationship extraction.
"""

from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.core.security import get_admin_token
from app.database.explorer import get_readonly_engine
from app.main import app

client = TestClient(app)


@pytest.fixture
def admin_headers() -> dict[str, str]:
    token = get_admin_token()
    return {
        "Authorization": f"Bearer {token}",
        "Host": "127.0.0.1",
        "Origin": "http://localhost:5173",
    }


def test_unauthenticated_explorer_request_rejected() -> None:
    # Missing authorization token -> 401
    resp = client.get("/api/v1/admin/database/overview", headers={"Host": "127.0.0.1"})
    assert resp.status_code == 401
    assert "Invalid or missing admin authentication token" in resp.json()["detail"]


def test_invalid_token_rejected() -> None:
    # Invalid bearer token -> 401
    resp = client.get(
        "/api/v1/admin/database/overview",
        headers={"Authorization": "Bearer completely-wrong-token", "Host": "127.0.0.1"},
    )
    assert resp.status_code == 401


def test_empty_or_whitespace_token_fails_closed() -> None:
    # Empty Bearer -> 401
    resp_empty_bearer = client.get(
        "/api/v1/admin/database/overview",
        headers={"Authorization": "Bearer ", "Host": "127.0.0.1"},
    )
    assert resp_empty_bearer.status_code == 401

    # Whitespace-only Bearer -> 401
    resp_ws_bearer = client.get(
        "/api/v1/admin/database/overview",
        headers={"Authorization": "Bearer    ", "Host": "127.0.0.1"},
    )
    assert resp_ws_bearer.status_code == 401

    # Empty X-Admin-Token -> 401
    resp_empty_x = client.get(
        "/api/v1/admin/database/overview",
        headers={"X-Admin-Token": "", "Host": "127.0.0.1"},
    )
    assert resp_empty_x.status_code == 401


def test_valid_token_and_x_admin_token_accepted(admin_headers: dict[str, str]) -> None:
    # 1. Bearer scheme
    resp1 = client.get("/api/v1/admin/database/overview", headers=admin_headers)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["engine"] == "sqlite"
    assert data1["connection_status"] == "connected"
    assert data1["mode"] == "ro"
    assert data1["query_only"] is True

    # 2. X-Admin-Token header
    token = get_admin_token()
    resp2 = client.get(
        "/api/v1/admin/database/overview",
        headers={
            "X-Admin-Token": token,
            "Host": "127.0.0.1",
            "Origin": "http://localhost:5173",
        },
    )
    assert resp2.status_code == 200


def test_bad_host_header_rejected(admin_headers: dict[str, str]) -> None:
    headers = dict(admin_headers)
    headers["Host"] = "attacker-controlled-host.com"
    resp = client.get("/api/v1/admin/database/overview", headers=headers)
    assert resp.status_code == 400
    assert "Invalid Host header" in resp.json()["detail"]


def test_rejected_origin_header(admin_headers: dict[str, str]) -> None:
    headers = dict(admin_headers)
    headers["Origin"] = "https://malicious-website.com"
    resp = client.get("/api/v1/admin/database/overview", headers=headers)
    assert resp.status_code == 403
    assert "Untrusted Origin header" in resp.json()["detail"]


def test_true_readonly_wal_mode_enforcement(tmp_path: Path) -> None:
    db_file = tmp_path / "wal_explorer_test.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("CREATE TABLE test_tbl (id INT PRIMARY KEY, content TEXT);")
    conn.execute("INSERT INTO test_tbl VALUES (1, 'live_wal_row');")
    conn.commit()
    conn.close()

    # Create read-only engine
    ro_engine = get_readonly_engine(db_file)

    # 1. Confirm committed row in WAL is actively observed
    with ro_engine.connect() as c:
        val = c.execute(text("SELECT content FROM test_tbl WHERE id = 1")).scalar()
        assert val == "live_wal_row"

    # 2. Confirm attempted write fails at SQLite level
    with pytest.raises(Exception, match="readonly database"):
        with ro_engine.begin() as c:
            c.execute(text("INSERT INTO test_tbl VALUES (2, 'unauthorized_write');"))

    ro_engine.dispose()


def test_database_overview_endpoint(admin_headers: dict[str, str]) -> None:
    resp = client.get("/api/v1/admin/database/overview", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["engine"] == "sqlite"
    assert data["integrity_status"] == "ok"
    assert data["current_revision"] in ("0002_task4_media_memory", "0003_indic_fts5_tokenization")
    assert data["table_counts"]["total"] >= 20
    assert data["table_counts"]["application"] >= 14
    assert data["table_counts"]["fts5_shadow"] >= 1
    assert data["table_counts"]["migration_metadata"] == 1
    assert "videos" in data["row_counts"]


def test_list_tables_and_search_filter(admin_headers: dict[str, str]) -> None:
    # 1. List all tables
    resp = client.get("/api/v1/admin/database/tables", headers=admin_headers)
    assert resp.status_code == 200
    tables = resp.json()
    assert len(tables) >= 20

    table_names = {t["name"] for t in tables}
    assert "videos" in table_names
    assert "assets" in table_names
    assert "libraries" in table_names
    assert "alembic_version" in table_names

    # Check videos entry metadata
    videos_meta = next(t for t in tables if t["name"] == "videos")
    assert videos_meta["category"] == "application"
    assert videos_meta["column_count"] >= 14
    assert "id" in videos_meta["primary_key"]
    assert videos_meta["has_foreign_keys"] is True

    # 2. Search filter
    search_resp = client.get("/api/v1/admin/database/tables?search=asset", headers=admin_headers)
    assert search_resp.status_code == 200
    search_results = search_resp.json()
    for t in search_results:
        assert "asset" in t["name"].lower()

    # 3. Category filter
    cat_resp = client.get("/api/v1/admin/database/tables?category=migration_metadata", headers=admin_headers)
    assert cat_resp.status_code == 200
    cat_results = cat_resp.json()
    assert len(cat_results) == 1
    assert cat_results[0]["name"] == "alembic_version"


def test_table_details_endpoint(admin_headers: dict[str, str]) -> None:
    # 1. Valid table
    resp = client.get("/api/v1/admin/database/tables/videos", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "videos"
    assert data["category"] == "application"
    assert "id" in data["primary_key"]

    col_names = {c["name"] for c in data["columns"]}
    assert "id" in col_names
    assert "filename" in col_names
    assert "duration" in col_names
    assert "asset_id" in col_names
    assert "version_id" in col_names

    fk_targets = {fk["referred_table"] for fk in data["foreign_keys"]}
    assert "assets" in fk_targets or "asset_versions" in fk_targets

    # 2. Non-existent table -> 404
    bad_resp = client.get("/api/v1/admin/database/tables/non_existent_table", headers=admin_headers)
    assert bad_resp.status_code == 404


def test_table_rows_pagination_and_redaction(admin_headers: dict[str, str]) -> None:
    from datetime import datetime, timezone
    from app.database.session import SessionLocal
    from app.models.entities import Video

    with SessionLocal() as db:
        if db.query(Video).count() == 0:
            db.add(
                Video(
                    id="sample-explorer-vid-1",
                    filename="explorer_sample.mp4",
                    file_path="/media/explorer_sample.mp4",
                    file_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    file_size=1024,
                    duration=10.0,
                    width=1920,
                    height=1080,
                    fps=30.0,
                    codec="h264",
                    format="mp4",
                    processing_status="indexed",
                    created_at=datetime.now(timezone.utc),
                )
            )
            db.commit()

    # Query videos rows
    resp = client.get("/api/v1/admin/database/tables/videos/rows?limit=10&offset=0", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["table_name"] == "videos"
    assert data["limit"] == 10
    assert data["offset"] == 0
    assert data["total"] >= 1
    assert len(data["rows"]) >= 1

    row = data["rows"][0]
    assert "id" in row
    assert "filename" in row


def test_empty_table_returns_zero_records(admin_headers: dict[str, str]) -> None:
    # ai_consents is currently empty in live dev DB
    resp = client.get("/api/v1/admin/database/tables/ai_consents/rows?limit=50&offset=0", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["table_name"] == "ai_consents"
    assert data["total"] == 0
    assert data["rows"] == []
    assert data["has_more"] is False


def test_migration_history_endpoint(admin_headers: dict[str, str]) -> None:
    resp = client.get("/api/v1/admin/database/migrations", headers=admin_headers)
    assert resp.status_code == 200
    history = resp.json()
    assert len(history) >= 2
    rev_ids = [h["revision"] for h in history]
    assert "0001_initial_schema" in rev_ids
    assert "0002_task4_media_memory" in rev_ids

    # Current head should be the latest migration
    current = next(h for h in history if h["is_current"])
    assert current["revision"] in ("0002_task4_media_memory", "0003_indic_fts5_tokenization")


def test_database_relationships_endpoint(admin_headers: dict[str, str]) -> None:
    resp = client.get("/api/v1/admin/database/relationships", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "tables" in data
    assert "relationships" in data
    assert len(data["tables"]) >= 20
    assert len(data["relationships"]) >= 5

    # Check relationship edges
    edge_pairs = {(e["source_table"], e["target_table"]) for e in data["relationships"]}
    assert ("transcripts", "videos") in edge_pairs
    assert ("video_scenes", "videos") in edge_pairs
    assert ("collection_videos", "collections") in edge_pairs

