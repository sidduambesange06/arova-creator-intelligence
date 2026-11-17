"""Database Explorer Service: Read-only live schema introspection, table rows inspection,
and relationship mapping for Arova Creator Intelligence.

Enforces:
- True read-only SQLite connections (mode=ro and PRAGMA query_only=ON).
- Live introspection via SQLAlchemy Inspector (never mocked).
- Table identifier validation (rejection of arbitrary SQL or non-existent tables).
- Redaction of tokens, API keys, credentials, and passwords.
- Representation of BLOBs by size only (never leaking binary payloads/embeddings).
- Truncation of large text cells.
- Clear classification of application, internal, FTS5 shadow, and Alembic metadata tables.
"""

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, Table, create_engine, event, func, inspect, select, text
from sqlalchemy.engine import Engine

from app.core.config import settings

SENSITIVE_FIELD_PATTERNS = re.compile(
    r"(token|key|secret|password|credential|auth_token|api_key)", re.IGNORECASE
)
MAX_TEXT_DISPLAY_LEN = 200
MAX_ROWS_PER_PAGE = 50


def classify_table(name: str) -> str:
    """Classify physical database tables into distinct functional categories."""
    if name.startswith("sqlite_"):
        return "internal"
    if name.startswith("transcript_chunks_fts"):
        return "fts5_shadow"
    if name == "alembic_version":
        return "migration_metadata"
    return "application"


def safe_table_count(conn: Any, table_name: str, max_cap: int = 100_000) -> int:
    """Safe bounded row count preventing indefinite full scans on huge datasets or virtual tables."""
    try:
        count = conn.execute(
            text(f'SELECT COUNT(*) FROM (SELECT 1 FROM "{table_name}" LIMIT {max_cap + 1})')
        ).scalar()
        return count or 0
    except Exception:
        return 0


def get_readonly_engine(db_path: str | Path | None = None) -> Engine:
    """Create a verified read-only SQLAlchemy engine with PRAGMA query_only=ON.

    Uses SQLite URI mode=ro without immutable=1, ensuring committed WAL frames
    are actively visible while strictly preventing any write operations.
    """
    raw_path = db_path or settings.SQLITE_DB_PATH
    if str(raw_path) == ":memory:" or "sqlite:///:memory:" in str(raw_path):
        uri = "sqlite:///:memory:"
    else:
        target = Path(raw_path).resolve()
        uri = f"sqlite:///file:{target.as_posix()}?mode=ro&uri=true"

    ro_engine = create_engine(uri, connect_args={"check_same_thread": False})

    @event.listens_for(ro_engine, "connect")
    def _enforce_query_only(dbapi_connection: Any, _: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA query_only=ON;")
        cursor.close()

    return ro_engine


def get_database_overview(
    db_path: str | Path | None = None,
    engine: Engine | None = None,
) -> dict[str, Any]:
    """Return high-level technical overview of the live SQLite database."""
    ro_engine = engine or get_readonly_engine(db_path)
    try:
        raw_path = db_path or settings.SQLITE_DB_PATH
        target_file = Path(raw_path).resolve() if str(raw_path) != ":memory:" else None
        file_size = target_file.stat().st_size if target_file and target_file.is_file() else 0

        inspector = inspect(ro_engine)
        all_tables = sorted(inspector.get_table_names())

        table_counts = {
            "total": len(all_tables),
            "application": 0,
            "internal": 0,
            "fts5_shadow": 0,
            "migration_metadata": 0,
        }
        for t in all_tables:
            cat = classify_table(t)
            table_counts[cat] = table_counts.get(cat, 0) + 1

        with ro_engine.connect() as conn:
            # PRAGMA integrity check
            check_res = conn.execute(text("PRAGMA integrity_check;")).fetchall()
            integrity_status = "ok" if check_res == [("ok",)] else str(check_res)

            # Alembic revision
            current_revision = None
            if "alembic_version" in all_tables:
                current_revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()

            # Record counts (safe bounded counts preventing runaway table scans)
            row_counts: dict[str, int] = {}
            for t in all_tables:
                cat = classify_table(t)
                if cat == "fts5_shadow":
                    row_counts[t] = 0
                else:
                    row_counts[t] = safe_table_count(conn, t)

        return {
            "engine": "sqlite",
            "database_name": target_file.name if target_file else ":memory:",
            "file_size_bytes": file_size,
            "connection_status": "connected",
            "mode": "ro",
            "query_only": True,
            "integrity_status": integrity_status,
            "current_revision": current_revision,
            "table_counts": table_counts,
            "row_counts": row_counts,
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        if engine is None:
            ro_engine.dispose()


def list_database_tables(
    search: str | None = None,
    category: str | None = None,
    db_path: str | Path | None = None,
    engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """List all database tables with structural metadata, row counts, and categories."""
    ro_engine = engine or get_readonly_engine(db_path)
    try:
        inspector = inspect(ro_engine)
        all_tables = sorted(inspector.get_table_names())
        results: list[dict[str, Any]] = []

        with ro_engine.connect() as conn:
            for t in all_tables:
                cat = classify_table(t)
                if category and cat != category:
                    continue
                if search and search.strip().lower() not in t.lower():
                    continue

                # Primary key
                pk_constraint = inspector.get_pk_constraint(t)
                pk_cols = pk_constraint.get("constrained_columns", []) if pk_constraint else []

                # Columns count
                cols = inspector.get_columns(t)

                # Foreign keys
                fks = inspector.get_foreign_keys(t)

                # Row count (safe bounded count)
                if cat == "fts5_shadow":
                    count = 0
                else:
                    count = safe_table_count(conn, t)

                results.append({
                    "name": t,
                    "category": cat,
                    "row_count": count,
                    "column_count": len(cols),
                    "primary_key": pk_cols,
                    "has_foreign_keys": len(fks) > 0,
                    "foreign_key_count": len(fks),
                    "is_empty": count == 0,
                })

        # Sort: application tables first, then alphabetical
        category_order = {"application": 0, "migration_metadata": 1, "fts5_shadow": 2, "internal": 3}
        results.sort(key=lambda x: (category_order.get(x["category"], 9), x["name"]))
        return results
    finally:
        if engine is None:
            ro_engine.dispose()


def get_table_details(
    table_name: str,
    db_path: str | Path | None = None,
    engine: Engine | None = None,
) -> dict[str, Any]:
    """Retrieve column specifications, indexes, foreign keys, and constraints for a table."""
    ro_engine = engine or get_readonly_engine(db_path)
    try:
        inspector = inspect(ro_engine)
        all_tables = set(inspector.get_table_names())
        if table_name not in all_tables:
            raise KeyError(f"Table '{table_name}' does not exist in database schema.")

        raw_columns = inspector.get_columns(table_name)
        pk_constraint = inspector.get_pk_constraint(table_name)
        pk_cols = set(pk_constraint.get("constrained_columns", []) if pk_constraint else [])
        foreign_keys = inspector.get_foreign_keys(table_name)
        indexes = inspector.get_indexes(table_name)
        unique_constraints = inspector.get_unique_constraints(table_name)

        columns = []
        for c in raw_columns:
            columns.append({
                "name": c["name"],
                "type": str(c["type"]),
                "nullable": bool(c.get("nullable", True)),
                "default": str(c.get("default")) if c.get("default") is not None else None,
                "primary_key": c["name"] in pk_cols,
            })

        formatted_fks = [
            {
                "constrained_columns": fk.get("constrained_columns", []),
                "referred_table": fk.get("referred_table"),
                "referred_columns": fk.get("referred_columns", []),
            }
            for fk in foreign_keys
        ]

        formatted_indexes = [
            {
                "name": idx.get("name"),
                "column_names": idx.get("column_names", []),
                "unique": bool(idx.get("unique", False)),
            }
            for idx in indexes
        ]

        formatted_uniques = [
            {
                "name": uq.get("name"),
                "column_names": uq.get("column_names", []),
            }
            for uq in unique_constraints
        ]

        return {
            "name": table_name,
            "category": classify_table(table_name),
            "columns": columns,
            "primary_key": list(pk_cols),
            "foreign_keys": formatted_fks,
            "indexes": formatted_indexes,
            "unique_constraints": formatted_uniques,
        }
    finally:
        if engine is None:
            ro_engine.dispose()


def get_table_rows(
    table_name: str,
    limit: int = 50,
    offset: int = 0,
    db_path: str | Path | None = None,
    engine: Engine | None = None,
) -> dict[str, Any]:
    """Retrieve safe, read-only paginated rows with token redaction and BLOB size display."""
    ro_engine = engine or get_readonly_engine(db_path)
    try:
        inspector = inspect(ro_engine)
        all_tables = set(inspector.get_table_names())
        if table_name not in all_tables:
            raise KeyError(f"Table '{table_name}' does not exist in database schema.")

        limit_clamped = max(1, min(limit, MAX_ROWS_PER_PAGE))
        offset_clamped = max(0, offset)

        metadata = MetaData()
        table_obj = Table(table_name, metadata, autoload_with=ro_engine)

        columns_meta = [{"name": c.name, "type": str(c.type)} for c in table_obj.columns]

        with ro_engine.connect() as conn:
            total_count = conn.execute(select(func.count()).select_from(table_obj)).scalar() or 0

            # Select paginated rows
            stmt = select(table_obj).limit(limit_clamped).offset(offset_clamped)
            rows_cursor = conn.execute(stmt)
            raw_rows = rows_cursor.fetchall()

            sanitized_rows: list[dict[str, Any]] = []
            for row in raw_rows:
                row_dict = dict(row._mapping)
                for col_name, val in list(row_dict.items()):
                    # Redact sensitive credentials/tokens
                    if SENSITIVE_FIELD_PATTERNS.search(col_name) and val is not None:
                        row_dict[col_name] = "[REDACTED]"
                        continue

                    # Mask BLOBs by byte size
                    if isinstance(val, (bytes, bytearray, memoryview)):
                        row_dict[col_name] = f"<BLOB {len(val)} bytes>"
                        continue

                    # Truncate long text strings
                    if isinstance(val, str) and len(val) > MAX_TEXT_DISPLAY_LEN:
                        row_dict[col_name] = f"{val[:MAX_TEXT_DISPLAY_LEN]}..."
                        continue

                    # Format timestamps cleanly
                    if isinstance(val, datetime):
                        row_dict[col_name] = val.isoformat()

                sanitized_rows.append(row_dict)

        return {
            "table_name": table_name,
            "category": classify_table(table_name),
            "columns": columns_meta,
            "rows": sanitized_rows,
            "total": total_count,
            "limit": limit_clamped,
            "offset": offset_clamped,
            "has_more": (offset_clamped + len(sanitized_rows)) < total_count,
        }
    finally:
        if engine is None:
            ro_engine.dispose()


def get_migration_history(
    db_path: str | Path | None = None,
    engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """Return historical and pending Alembic migration revisions."""
    ro_engine = engine or get_readonly_engine(db_path)
    try:
        inspector = inspect(ro_engine)
        all_tables = set(inspector.get_table_names())
        current_rev = None

        if "alembic_version" in all_tables:
            with ro_engine.connect() as conn:
                current_rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()

        # Introspect Alembic revisions from migrations directory
        backend_dir = Path(__file__).resolve().parent.parent.parent
        migrations_dir = backend_dir / "app" / "database" / "migrations"
        script_dir = ScriptDirectory(str(migrations_dir))

        revisions: list[dict[str, Any]] = []
        for script in script_dir.walk_revisions():
            revisions.append({
                "revision": script.revision,
                "down_revision": script.down_revision,
                "description": script.doc or "No description",
                "is_current": script.revision == current_rev,
            })

        # Return oldest first (ascending chronological order)
        revisions.reverse()
        return revisions
    finally:
        if engine is None:
            ro_engine.dispose()


def get_database_relationships(
    db_path: str | Path | None = None,
    engine: Engine | None = None,
) -> dict[str, Any]:
    """Extract table nodes and foreign key edges for visual Entity-Relationship diagrams."""
    ro_engine = engine or get_readonly_engine(db_path)
    try:
        inspector = inspect(ro_engine)
        all_tables = sorted(inspector.get_table_names())
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        edge_idx = 0

        with ro_engine.connect() as conn:
            for t in all_tables:
                cat = classify_table(t)
                cols = inspector.get_columns(t)
                pk_constraint = inspector.get_pk_constraint(t)
                pk_cols = set(pk_constraint.get("constrained_columns", []) if pk_constraint else [])
                fks = inspector.get_foreign_keys(t)

                try:
                    count = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar() or 0
                except Exception:
                    count = 0

                nodes.append({
                    "id": t,
                    "label": t,
                    "category": cat,
                    "row_count": count,
                    "column_count": len(cols),
                    "columns": [
                        {
                            "name": c["name"],
                            "type": str(c["type"]),
                            "primary_key": c["name"] in pk_cols,
                        }
                        for c in cols
                    ],
                })

                for fk in fks:
                    referred_table = fk.get("referred_table")
                    constrained_cols = fk.get("constrained_columns", [])
                    referred_cols = fk.get("referred_columns", [])
                    if referred_table and constrained_cols:
                        edges.append({
                            "id": f"edge_{edge_idx}",
                            "source_table": t,
                            "source_columns": constrained_cols,
                            "target_table": referred_table,
                            "target_columns": referred_cols,
                            "label": f"{', '.join(constrained_cols)} -> {', '.join(referred_cols)}",
                        })
                        edge_idx += 1

        return {
            "tables": nodes,
            "relationships": edges,
        }
    finally:
        if engine is None:
            ro_engine.dispose()

