"""Baseline initial schema for Arova Creator Intelligence.

Defines the pre-Task-4 baseline tables: videos, collections, collection_videos,
transcripts, transcript_segments, video_scenes, embedding_records, video_summaries,
and processing_jobs.
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "videos" not in existing_tables:
        op.create_table(
            "videos",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("filename", sa.String(length=255), nullable=False),
            sa.Column("file_path", sa.Text(), nullable=False, unique=True),
            sa.Column("file_hash", sa.String(length=64), nullable=False, index=True),
            sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("duration", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("width", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("height", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("fps", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("codec", sa.String(length=64), nullable=False, server_default="unknown"),
            sa.Column("format", sa.String(length=64), nullable=False, server_default="unknown"),
            sa.Column("thumbnail_path", sa.Text(), nullable=True),
            sa.Column("processing_status", sa.String(length=32), nullable=False, server_default="pending", index=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "collections" not in existing_tables:
        op.create_table(
            "collections",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("name", sa.String(length=128), nullable=False, unique=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "collection_videos" not in existing_tables:
        op.create_table(
            "collection_videos",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("collection_id", sa.String(length=36), sa.ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("video_id", sa.String(length=36), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.UniqueConstraint("collection_id", "video_id", name="uq_collection_video"),
        )

    if "transcripts" not in existing_tables:
        op.create_table(
            "transcripts",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("video_id", sa.String(length=36), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("language", sa.String(length=32), nullable=False, server_default="en"),
            sa.Column("model_name", sa.String(length=128), nullable=False),
            sa.Column("full_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "transcript_segments" not in existing_tables:
        op.create_table(
            "transcript_segments",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("transcript_id", sa.String(length=36), sa.ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("video_id", sa.String(length=36), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("start_time", sa.Float(), nullable=False),
            sa.Column("end_time", sa.Float(), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        )

    if "video_scenes" not in existing_tables:
        op.create_table(
            "video_scenes",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("video_id", sa.String(length=36), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("scene_index", sa.Integer(), nullable=False),
            sa.Column("start_time", sa.Float(), nullable=False),
            sa.Column("end_time", sa.Float(), nullable=False),
            sa.Column("thumbnail_path", sa.Text(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
        )

    if "embedding_records" not in existing_tables:
        op.create_table(
            "embedding_records",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("video_id", sa.String(length=36), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("chunk_text", sa.Text(), nullable=False),
            sa.Column("start_time", sa.Float(), nullable=False),
            sa.Column("end_time", sa.Float(), nullable=False),
            sa.Column("embedding_id", sa.String(length=128), nullable=False, unique=True),
            sa.Column("model_name", sa.String(length=128), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "video_summaries" not in existing_tables:
        op.create_table(
            "video_summaries",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("video_id", sa.String(length=36), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("summary_text", sa.Text(), nullable=False),
            sa.Column("topics_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("chapters_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("model_name", sa.String(length=128), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "processing_jobs" not in existing_tables:
        op.create_table(
            "processing_jobs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("video_id", sa.String(length=36), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("job_type", sa.String(length=64), nullable=False, server_default="full_pipeline"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending", index=True),
            sa.Column("progress", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    tables = [
        "processing_jobs",
        "video_summaries",
        "embedding_records",
        "video_scenes",
        "transcript_segments",
        "transcripts",
        "collection_videos",
        "collections",
        "videos",
    ]
    for table_name in tables:
        op.drop_table(table_name)
