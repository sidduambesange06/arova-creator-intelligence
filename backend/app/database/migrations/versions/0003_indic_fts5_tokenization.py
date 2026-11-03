"""Indic-Safe FTS5 Tokenization: unicode61 with tokenchars for Indic vowel marks and virama.

Revision ID: 0003_indic_fts5_tokenization
Revises: 0002_task4_media_memory
Create Date: 2026-11-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_indic_fts5_tokenization"
down_revision = "0002_task4_media_memory"
branch_labels = None
depends_on = None


def get_indic_tokenchars() -> str:
    """Generate tokenchars string for Devanagari, Tamil, Telugu, and Kannada marks/virama."""
    chars = []
    # Devanagari: 0x0901-0x0903, 0x093C, 0x093E-0x094F, 0x0951-0x0957, 0x0962-0x0963
    for cp in list(range(0x0901, 0x0904)) + [0x093C] + list(range(0x093E, 0x0950)) + list(range(0x0951, 0x0958)) + list(range(0x0962, 0x0964)):
        chars.append(chr(cp))
    # Tamil: 0x0B82, 0x0BBE-0x0BCD, 0x0BD7
    for cp in [0x0B82] + list(range(0x0BBE, 0x0BCE)) + [0x0BD7]:
        chars.append(chr(cp))
    # Telugu: 0x0C00-0x0C03, 0x0C3E-0x0C4D, 0x0C55-0x0C56, 0x0C62-0x0C63
    for cp in list(range(0x0C00, 0x0C04)) + list(range(0x0C3E, 0x0C4E)) + list(range(0x0C55, 0x0C57)) + list(range(0x0C62, 0x0C64)):
        chars.append(chr(cp))
    # Kannada: 0x0C81-0x0C83, 0x0CBC, 0x0CBE-0x0CCD, 0x0CD5-0x0CD6, 0x0CE2-0x0CE3
    for cp in list(range(0x0C81, 0x0C84)) + [0x0CBC] + list(range(0x0CBE, 0x0CCE)) + list(range(0x0CD5, 0x0CD7)) + list(range(0x0CE2, 0x0CE4)):
        chars.append(chr(cp))
    return "".join(chars)


def upgrade() -> None:
    bind = op.get_bind()
    tokenchars = get_indic_tokenchars().replace("'", "''")
    tokenizer_sql = f"unicode61 tokenchars '{tokenchars}'"

    # Drop existing virtual table
    bind.execute(sa.text("DROP TABLE IF EXISTS transcript_chunks_fts;"))

    # Create FTS5 virtual table configured with Indic tokenchars
    bind.execute(
        sa.text(
            f"""
            CREATE VIRTUAL TABLE transcript_chunks_fts USING fts5(
                embedding_id UNINDEXED,
                video_id UNINDEXED,
                chunk_text,
                tokenize="{tokenizer_sql}"
            );
            """
        )
    )

    # Rebuild index from authoritative source embedding_records if present
    inspector = sa.inspect(bind)
    if "embedding_records" in inspector.get_table_names():
        bind.execute(
            sa.text(
                """
                INSERT INTO transcript_chunks_fts (embedding_id, video_id, chunk_text)
                SELECT embedding_id, video_id, chunk_text
                FROM embedding_records
                WHERE chunk_text IS NOT NULL AND chunk_text != '';
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP TABLE IF EXISTS transcript_chunks_fts;"))
    bind.execute(
        sa.text(
            """
            CREATE VIRTUAL TABLE transcript_chunks_fts USING fts5(
                embedding_id UNINDEXED,
                video_id UNINDEXED,
                chunk_text
            );
            """
        )
    )

    inspector = sa.inspect(bind)
    if "embedding_records" in inspector.get_table_names():
        bind.execute(
            sa.text(
                """
                INSERT INTO transcript_chunks_fts (embedding_id, video_id, chunk_text)
                SELECT embedding_id, video_id, chunk_text
                FROM embedding_records
                WHERE chunk_text IS NOT NULL AND chunk_text != '';
                """
            )
        )

