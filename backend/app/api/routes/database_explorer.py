"""Database Explorer API: Administrative read-only schema introspection and data exploration.

Endpoints are gated by mandatory admin authentication (Bearer / X-Admin-Token)
and Host/Origin validation.
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import require_admin_auth
from app.database.explorer import (
    get_database_overview,
    get_database_relationships,
    get_migration_history,
    get_table_details,
    get_table_rows,
    list_database_tables,
)

router = APIRouter(
    prefix="/api/v1/admin/database",
    tags=["Database Explorer"],
    dependencies=[Depends(require_admin_auth)],
)


@router.get("/overview", summary="High-level database health and table counts")
def get_overview() -> dict[str, Any]:
    """Retrieve database technical specifications, size, integrity check, and revision."""
    return get_database_overview()


@router.get("/tables", summary="List database tables and structural categories")
def get_tables(
    search: str | None = Query(default=None, description="Filter table names"),
    category: str | None = Query(default=None, description="Filter by category (application, internal, fts5_shadow, migration_metadata)"),
) -> list[dict[str, Any]]:
    """List all physical tables with row counts, column counts, and PK/FK indicators."""
    return list_database_tables(search=search, category=category)


@router.get("/tables/{table_name}", summary="Detailed column, index, and constraint specifications")
def get_table(table_name: str) -> dict[str, Any]:
    """Inspect schema specifications for a single table."""
    try:
        return get_table_details(table_name)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get("/tables/{table_name}/rows", summary="Read-only paginated table rows")
def get_rows(
    table_name: str,
    limit: int = Query(default=50, ge=1, le=50, description="Max 50 rows per page"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
) -> dict[str, Any]:
    """Retrieve paginated rows with sensitive token redaction and BLOB masking."""
    try:
        return get_table_rows(table_name, limit=limit, offset=offset)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get("/migrations", summary="Alembic revision and migration history")
def get_migrations() -> list[dict[str, Any]]:
    """Inspect migration revisions and current applied head status."""
    return get_migration_history()


@router.get("/relationships", summary="Entity-Relationship nodes and foreign key edges")
def get_relationships() -> dict[str, Any]:
    """Extract schema nodes and directed edges for ER diagram visualization."""
    return get_database_relationships()

