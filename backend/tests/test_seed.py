from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import (
    Agent,
    DecisionPackage,
    KnowledgeDocument,
    ReviewerAssessment,
    RiskDecision,
    RiskItem,
    Ticket,
    User,
    WorkflowRule,
)
from app.seed import RISK_KNOWLEDGE_DOCUMENTS, seed_demo_data

MODELS = (User, KnowledgeDocument, Agent, Ticket, WorkflowRule, RiskItem, DecisionPackage, ReviewerAssessment, RiskDecision)


def _fresh_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False)()


def _counts(db) -> dict[str, int]:
    return {model.__name__: db.query(model).count() for model in MODELS}


def test_seed_is_safe_to_rerun():
    db = _fresh_session()
    seed_demo_data(db)
    first = _counts(db)

    seed_demo_data(db)

    assert _counts(db) == first
    assert first["RiskDecision"] == 3


def test_seed_adds_risk_data_to_a_database_seeded_before_risk_review():
    db = _fresh_session()
    seed_demo_data(db)
    complete = _counts(db)
    for model in (RiskDecision, ReviewerAssessment, DecisionPackage, RiskItem):
        db.query(model).delete()
    risk_titles = [title for title, _, _ in RISK_KNOWLEDGE_DOCUMENTS]
    db.query(KnowledgeDocument).filter(KnowledgeDocument.title.in_(risk_titles)).delete(synchronize_session=False)
    db.add(
        RiskItem(
            title="Risk a user added after upgrading",
            description="A risk created through the API before the demo risks were seeded.",
            business_unit="IT",
            owner="it-lead",
            impact=2,
            likelihood=2,
            status="draft",
            version=1,
        )
    )
    db.commit()

    seed_demo_data(db)

    assert _counts(db) == {**complete, "RiskItem": complete["RiskItem"] + 1}
