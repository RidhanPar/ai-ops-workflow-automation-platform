"""Create production-oriented platform schema."""

from alembic import op

from app import models  # noqa: F401
from app.db import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=bind)
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS embedding_vector vector(64)")
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_knowledge_embedding_vector "
            "ON knowledge_documents USING hnsw (embedding_vector vector_cosine_ops)"
        )


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
