"""Add source, cited_knowledge_ids, cited_decision_ids to decision_packages; perspective to reviewer_assessments.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa_inspect(conn)

    pkg_cols = {c["name"] for c in insp.get_columns("decision_packages")}
    if "source" not in pkg_cols:
        op.add_column(
            "decision_packages",
            sa.Column(
                "source",
                sa.String(80),
                nullable=False,
                server_default="fallback_no_provider",
            ),
        )
    if "cited_knowledge_ids" not in pkg_cols:
        op.add_column(
            "decision_packages",
            sa.Column("cited_knowledge_ids", sa.JSON(), nullable=False, server_default="[]"),
        )
    if "cited_decision_ids" not in pkg_cols:
        op.add_column(
            "decision_packages",
            sa.Column("cited_decision_ids", sa.JSON(), nullable=False, server_default="[]"),
        )

    assessment_cols = {c["name"] for c in insp.get_columns("reviewer_assessments")}
    if "perspective" not in assessment_cols:
        op.add_column(
            "reviewer_assessments",
            sa.Column("perspective", sa.String(40), nullable=False, server_default="security"),
        )


def downgrade() -> None:
    op.drop_column("reviewer_assessments", "perspective")
    op.drop_column("decision_packages", "cited_decision_ids")
    op.drop_column("decision_packages", "cited_knowledge_ids")
    op.drop_column("decision_packages", "source")
