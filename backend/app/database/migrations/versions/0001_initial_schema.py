"""Initial SQLite schema for Arova Creator Intelligence."""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.database.session import Base
    import app.models.entities  # noqa: F401

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from app.database.session import Base
    import app.models.entities  # noqa: F401

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
    _ = sa
