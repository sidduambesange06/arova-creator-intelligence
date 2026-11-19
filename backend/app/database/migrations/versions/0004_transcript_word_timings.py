"""Add optional word-level timing columns to transcript_segments.

Revision ID: 0004_transcript_word_timings
Revises: 0003_indic_fts5_tokenization
Create Date: 2026-11-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_transcript_word_timings"
down_revision = "0003_indic_fts5_tokenization"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "transcript_segments" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("transcript_segments")}
    if "words_json" not in cols:
        op.add_column("transcript_segments", sa.Column("words_json", sa.Text(), nullable=True))
    if "timing_source" not in cols:
        op.add_column("transcript_segments", sa.Column("timing_source", sa.String(length=32), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "transcript_segments" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("transcript_segments")}
    with op.batch_alter_table("transcript_segments") as batch_op:
        if "timing_source" in cols:
            batch_op.drop_column("timing_source")
        if "words_json" in cols:
            batch_op.drop_column("words_json")
