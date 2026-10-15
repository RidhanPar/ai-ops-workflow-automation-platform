"""Add risk review tables (RiskItem, DecisionPackage, ReviewerAssessment, RiskDecision)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    existing = set(sa_inspect(conn).get_table_names())

    if "risk_items" not in existing:
        op.create_table(
            "risk_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("business_unit", sa.String(120), nullable=False),
            sa.Column("owner", sa.String(120), nullable=False),
            sa.Column("impact", sa.Integer(), nullable=False),
            sa.Column("likelihood", sa.Integer(), nullable=False),
            sa.Column("proposed_mitigation", sa.Text(), nullable=True),
            sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_risk_items_id", "risk_items", ["id"])

    if "decision_packages" not in existing:
        op.create_table(
            "decision_packages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("risk_item_id", sa.Integer(), sa.ForeignKey("risk_items.id"), nullable=False),
            sa.Column("idempotency_key", sa.String(160), nullable=False, unique=True),
            sa.Column("completeness_gaps", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("needs_info", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("best_practices", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("past_decisions", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("perspectives", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("risk_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("recommended_treatment", sa.String(40), nullable=False, server_default="mitigate"),
            sa.Column("safety_flags", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("generated_by", sa.String(80), nullable=False),
            sa.Column("trace_id", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_decision_packages_id", "decision_packages", ["id"])
        op.create_index("ix_decision_packages_risk_item_id", "decision_packages", ["risk_item_id"])
        op.create_index(
            "ix_decision_packages_idempotency_key", "decision_packages", ["idempotency_key"], unique=True
        )
        op.create_index("ix_decision_packages_trace_id", "decision_packages", ["trace_id"])

    if "reviewer_assessments" not in existing:
        op.create_table(
            "reviewer_assessments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "decision_package_id",
                sa.Integer(),
                sa.ForeignKey("decision_packages.id"),
                nullable=False,
            ),
            sa.Column("reviewer", sa.String(80), nullable=False),
            sa.Column("vote", sa.String(40), nullable=False),
            sa.Column("comment", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "decision_package_id", "reviewer", name="uq_assessment_package_reviewer"
            ),
        )
        op.create_index("ix_reviewer_assessments_id", "reviewer_assessments", ["id"])
        op.create_index(
            "ix_reviewer_assessments_decision_package_id",
            "reviewer_assessments",
            ["decision_package_id"],
        )

    if "risk_decisions" not in existing:
        op.create_table(
            "risk_decisions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("risk_item_id", sa.Integer(), sa.ForeignKey("risk_items.id"), nullable=False),
            sa.Column(
                "decision_package_id",
                sa.Integer(),
                sa.ForeignKey("decision_packages.id"),
                nullable=False,
            ),
            sa.Column("decided_by", sa.String(80), nullable=False),
            sa.Column("decision", sa.String(40), nullable=False),
            sa.Column("rationale", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_risk_decisions_id", "risk_decisions", ["id"])
        op.create_index("ix_risk_decisions_risk_item_id", "risk_decisions", ["risk_item_id"])


def downgrade() -> None:
    op.drop_table("risk_decisions")
    op.drop_table("reviewer_assessments")
    op.drop_table("decision_packages")
    op.drop_table("risk_items")
