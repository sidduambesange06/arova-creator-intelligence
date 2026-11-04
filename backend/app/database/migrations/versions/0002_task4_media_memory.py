"""Task 4 Media Memory Schema: Libraries, Roots, Assets, Versions, Locations, Stages, Artifacts, AI Consents, and ID Aliases."""

from alembic import op
import sqlalchemy as sa

revision = "0002_task4_media_memory"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Libraries
    if "libraries" not in existing_tables:
        op.create_table(
            "libraries",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("label", sa.String(length=128), nullable=False),
            sa.Column("execution_profile", sa.String(length=32), nullable=False, server_default="fully_offline_no_ai"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    # 2. Library Roots
    if "library_roots" not in existing_tables:
        op.create_table(
            "library_roots",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("library_id", sa.String(length=36), sa.ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("label", sa.String(length=128), nullable=False),
            sa.Column("root_type", sa.String(length=32), nullable=False, server_default="unknown"),
            sa.Column("volume_id", sa.String(length=128), nullable=True),
            sa.Column("marker_id", sa.String(length=128), nullable=True),
            sa.Column("policy", sa.String(length=32), nullable=False, server_default="local_only"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("last_scan_at", sa.DateTime(timezone=True), nullable=True),
        )

    # 3. Assets
    if "assets" not in existing_tables:
        op.create_table(
            "assets",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("current_version_id", sa.String(length=36), nullable=True, index=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    # 4. Asset Versions
    if "asset_versions" not in existing_tables:
        op.create_table(
            "asset_versions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("asset_id", sa.String(length=36), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("sha256", sa.String(length=64), nullable=True),
            sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("media_meta", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("supersedes_version_id", sa.String(length=36), sa.ForeignKey("asset_versions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("identity_state", sa.String(length=32), nullable=False, server_default="identity_unverified"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "uq_asset_versions_sha256",
            "asset_versions",
            ["sha256"],
            unique=True,
            sqlite_where=sa.text("sha256 IS NOT NULL"),
        )

    # 5. Asset Locations
    if "asset_locations" not in existing_tables:
        op.create_table(
            "asset_locations",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("version_id", sa.String(length=36), sa.ForeignKey("asset_versions.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("root_id", sa.String(length=36), sa.ForeignKey("library_roots.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("rel_path", sa.Text(), nullable=False),
            sa.Column("rel_path_norm", sa.Text(), nullable=False),
            sa.Column("stat_key", sa.String(length=255), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("availability", sa.String(length=32), nullable=False, server_default="available"),
            sa.Column("missing_since", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            "uq_asset_locations_root_relpath",
            "asset_locations",
            ["root_id", "rel_path_norm"],
            unique=True,
        )

    # 6. Stage Runs
    if "stage_runs" not in existing_tables:
        op.create_table(
            "stage_runs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("version_id", sa.String(length=36), sa.ForeignKey("asset_versions.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("stage", sa.String(length=64), nullable=False),
            sa.Column("fingerprint", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("skip_reason", sa.String(length=64), nullable=True),
            sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_code", sa.String(length=64), nullable=True),
            sa.Column("error_detail", sa.Text(), nullable=True),
            sa.Column("output_ref", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("version_id", "stage", "fingerprint", name="uq_stage_runs_version_stage_fp"),
        )

    # 7. Artifacts
    if "artifacts" not in existing_tables:
        op.create_table(
            "artifacts",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("version_id", sa.String(length=36), sa.ForeignKey("asset_versions.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("kind", sa.String(length=64), nullable=False),
            sa.Column("producer_stage", sa.String(length=64), nullable=False),
            sa.Column("producer_model", sa.String(length=128), nullable=True),
            sa.Column("producer_revision", sa.String(length=64), nullable=True),
            sa.Column("config_hash", sa.String(length=64), nullable=True),
            sa.Column("is_current", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("trust", sa.String(length=32), nullable=False, server_default="unverified"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    # 8. Moments
    if "moments" not in existing_tables:
        op.create_table(
            "moments",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("version_id", sa.String(length=36), sa.ForeignKey("asset_versions.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("start_ms", sa.Integer(), nullable=False),
            sa.Column("end_ms", sa.Integer(), nullable=False),
            sa.Column("kind", sa.String(length=64), nullable=False, server_default="scene"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    # 9. AI Consents
    if "ai_consents" not in existing_tables:
        op.create_table(
            "ai_consents",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("scope_type", sa.String(length=32), nullable=False),
            sa.Column("scope_id", sa.String(length=36), nullable=False, index=True),
            sa.Column("provider", sa.String(length=64), nullable=False),
            sa.Column("endpoint_host", sa.String(length=255), nullable=False),
            sa.Column("data_categories", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("capabilities", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("budget_limit", sa.Float(), nullable=True),
            sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        )

    # 10. AI Runs
    if "ai_runs" not in existing_tables:
        op.create_table(
            "ai_runs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("provider", sa.String(length=64), nullable=False),
            sa.Column("model", sa.String(length=128), nullable=False),
            sa.Column("execution_location", sa.String(length=32), nullable=False),
            sa.Column("data_categories", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("prompt_hash", sa.String(length=64), nullable=False),
            sa.Column("input_refs", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("consent_id", sa.String(length=36), sa.ForeignKey("ai_consents.id", ondelete="SET NULL"), nullable=True),
            sa.Column("tokens_in", sa.Integer(), nullable=True),
            sa.Column("tokens_out", sa.Integer(), nullable=True),
            sa.Column("cost", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    # 11. Annotations
    if "annotations" not in existing_tables:
        op.create_table(
            "annotations",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("target_type", sa.String(length=32), nullable=False),
            sa.Column("target_id", sa.String(length=36), nullable=False, index=True),
            sa.Column("author_type", sa.String(length=32), nullable=False),
            sa.Column("display_name", sa.String(length=128), nullable=True),
            sa.Column("trust", sa.String(length=32), nullable=False, server_default="unverified"),
            sa.Column("ai_run_id", sa.String(length=36), sa.ForeignKey("ai_runs.id", ondelete="SET NULL"), nullable=True),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    # 12. ID Aliases
    if "id_aliases" not in existing_tables:
        op.create_table(
            "id_aliases",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("entity_type", sa.String(length=32), nullable=False),
            sa.Column("foreign_id", sa.String(length=64), nullable=False),
            sa.Column("local_id", sa.String(length=36), nullable=False),
            sa.Column("source_export_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "uq_id_aliases_export",
            "id_aliases",
            ["entity_type", "foreign_id", "source_export_id"],
            unique=True,
            sqlite_where=sa.text("source_export_id IS NOT NULL"),
        )
        op.create_index(
            "uq_id_aliases_local",
            "id_aliases",
            ["entity_type", "foreign_id"],
            unique=True,
            sqlite_where=sa.text("source_export_id IS NULL"),
        )

    # 13. Asset Relations
    if "asset_relations" not in existing_tables:
        op.create_table(
            "asset_relations",
            sa.Column("src_asset_id", sa.String(length=36), sa.ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("dst_asset_id", sa.String(length=36), sa.ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("relation", sa.String(length=32), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    # 14. Scan Runs
    if "scan_runs" not in existing_tables:
        op.create_table(
            "scan_runs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("root_id", sa.String(length=36), sa.ForeignKey("library_roots.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("checkpoint", sa.Text(), nullable=True),
            sa.Column("counts", sa.Text(), nullable=True),
        )

    # 15. Alter videos table to add asset_id and version_id
    if "videos" in existing_tables:
        video_cols = {col["name"] for col in inspector.get_columns("videos")}
        if "asset_id" not in video_cols:
            op.execute("ALTER TABLE videos ADD COLUMN asset_id VARCHAR(36) REFERENCES assets(id) ON DELETE SET NULL")
            op.create_index("ix_videos_asset_id", "videos", ["asset_id"])
        if "version_id" not in video_cols:
            op.execute("ALTER TABLE videos ADD COLUMN version_id VARCHAR(36) REFERENCES asset_versions(id) ON DELETE SET NULL")
            op.create_index("ix_videos_version_id", "videos", ["version_id"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())
    if "videos" in existing_tables:
        video_cols = {col["name"] for col in inspector.get_columns("videos")}
        if "version_id" in video_cols:
            op.drop_index("ix_videos_version_id", table_name="videos")
            op.execute("ALTER TABLE videos DROP COLUMN version_id")
        if "asset_id" in video_cols:
            op.drop_index("ix_videos_asset_id", table_name="videos")
            op.execute("ALTER TABLE videos DROP COLUMN asset_id")

    tables = [
        "scan_runs",
        "asset_relations",
        "id_aliases",
        "annotations",
        "ai_runs",
        "ai_consents",
        "moments",
        "artifacts",
        "stage_runs",
        "asset_locations",
        "asset_versions",
        "assets",
        "library_roots",
        "libraries",
    ]
    for table_name in tables:
        if table_name in existing_tables:
            op.drop_table(table_name)
