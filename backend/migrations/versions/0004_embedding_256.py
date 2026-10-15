"""Grow the local embedding from 64 to 256 dimensions and re-embed every knowledge document.

Revision ID: 0004
Revises: 0003
"""

import json

import sqlalchemy as sa
from alembic import op

from app.services.knowledge import local_embedding

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

_documents = sa.table(
    "knowledge_documents",
    sa.column("id", sa.Integer),
    sa.column("title", sa.String),
    sa.column("content", sa.Text),
    sa.column("tags", sa.JSON),
    sa.column("embedding", sa.JSON),
)


def _resize(dimensions: int) -> None:
    bind = op.get_bind()
    postgres = bind.dialect.name == "postgresql"
    if postgres:
        op.execute("DROP INDEX IF EXISTS ix_knowledge_embedding_vector")
        op.execute(
            f"ALTER TABLE knowledge_documents ALTER COLUMN embedding_vector TYPE vector({dimensions}) "
            f"USING NULL::vector({dimensions})"
        )
    rows = bind.execute(sa.select(_documents.c.id, _documents.c.title, _documents.c.content, _documents.c.tags)).all()
    for row in rows:
        tags = json.loads(row.tags) if isinstance(row.tags, str) else (row.tags or [])
        embedding = local_embedding(f"{row.title} {row.content} {' '.join(tags)}", dimensions=dimensions)
        bind.execute(_documents.update().where(_documents.c.id == row.id).values(embedding=embedding))
        if postgres:
            bind.execute(
                sa.text("UPDATE knowledge_documents SET embedding_vector = :embedding WHERE id = :id"),
                {"embedding": str(embedding), "id": row.id},
            )
    if postgres:
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_knowledge_embedding_vector "
            "ON knowledge_documents USING hnsw (embedding_vector vector_cosine_ops)"
        )


def upgrade() -> None:
    _resize(256)


def downgrade() -> None:
    _resize(64)
