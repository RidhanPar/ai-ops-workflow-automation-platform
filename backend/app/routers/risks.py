from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.metrics import risk_decisions_total
from app.core.security import get_current_user, require_roles
from app.db import get_db
from app.models import DecisionPackage, ReviewerAssessment, RiskDecision, RiskItem, User
from app.schemas import (
    DecisionPackageOut,
    DecisionPackageRequest,
    ReviewerAssessmentCreate,
    ReviewerAssessmentOut,
    RiskDecisionCreate,
    RiskDecisionOut,
    RiskItemCreate,
    RiskItemOut,
)
from app.services.audit import record_audit
from app.services.decision_package import generate_decision_package

risks_router = APIRouter(prefix="/risks", tags=["risks"])
packages_router = APIRouter(prefix="/decision-packages", tags=["risks"])


@risks_router.post("", response_model=RiskItemOut, status_code=201)
def create_risk(
    payload: RiskItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("operator", "manager", "admin")),
):
    risk = RiskItem(
        title=payload.title,
        description=payload.description,
        business_unit=payload.business_unit,
        owner=payload.owner,
        impact=payload.impact,
        likelihood=payload.likelihood,
        proposed_mitigation=payload.proposed_mitigation,
        status="draft",
        version=1,
    )
    db.add(risk)
    db.flush()
    record_audit(db, user.username, "risk.created", "risk_item", risk.id, {}, {"title": risk.title, "status": "draft"})
    db.commit()
    db.refresh(risk)
    return risk


@risks_router.get("", response_model=list[RiskItemOut])
def list_risks(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return db.query(RiskItem).order_by(RiskItem.created_at.desc()).all()


@risks_router.get("/{risk_id}", response_model=RiskItemOut)
def get_risk(
    risk_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    risk = db.get(RiskItem, risk_id)
    if not risk:
        raise HTTPException(status_code=404, detail="Risk item not found")
    return risk


@risks_router.post("/{risk_id}/decision-package", response_model=DecisionPackageOut, status_code=200)
def create_or_get_decision_package(
    risk_id: int,
    payload: DecisionPackageRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("operator", "manager", "admin")),
):
    risk = db.get(RiskItem, risk_id)
    if not risk:
        raise HTTPException(status_code=404, detail="Risk item not found")
    if risk.status == "decided":
        raise HTTPException(
            status_code=409,
            detail="Risk item is already decided; no new packages can be generated",
        )

    settings = get_settings()
    package = generate_decision_package(db, risk, user.username, payload.idempotency_key, settings)

    if package.needs_info:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Risk item is incomplete; provide the missing fields and use a new idempotency key",
                "gaps": package.completeness_gaps,
                "package_id": package.id,
            },
        )

    return package


@risks_router.post("/{risk_id}/decision", response_model=RiskDecisionOut, status_code=201)
def make_decision(
    risk_id: int,
    payload: RiskDecisionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("manager", "admin")),
):
    risk = db.get(RiskItem, risk_id)
    if not risk:
        raise HTTPException(status_code=404, detail="Risk item not found")

    if risk.version != payload.version:
        raise HTTPException(
            status_code=409,
            detail=f"Version conflict: risk is at version {risk.version}, submitted version {payload.version}",
        )

    package = db.get(DecisionPackage, payload.decision_package_id)
    if not package or package.risk_item_id != risk_id:
        raise HTTPException(
            status_code=404,
            detail="Decision package not found for this risk item",
        )

    latest_pkg = (
        db.query(DecisionPackage)
        .filter(
            DecisionPackage.risk_item_id == risk_id,
            DecisionPackage.needs_info.is_(False),
        )
        .order_by(DecisionPackage.id.desc())
        .first()
    )
    if latest_pkg is None or latest_pkg.id != payload.decision_package_id:
        raise HTTPException(
            status_code=409,
            detail="Decision must reference the latest non-incomplete package for this risk item",
        )

    qualifying_count = (
        db.query(ReviewerAssessment)
        .filter(
            ReviewerAssessment.decision_package_id == payload.decision_package_id,
            ReviewerAssessment.reviewer != user.username,
        )
        .count()
    )
    if qualifying_count < 2:
        raise HTTPException(
            status_code=422,
            detail={
                "message": (
                    f"At least 2 reviewer assessments from users other than the deciding manager are required; "
                    f"{qualifying_count} qualifying assessment(s) found. "
                    f"The deciding manager ({user.username}) cannot count their own assessment toward this requirement."
                ),
                "qualifying_count": qualifying_count,
                "deciding_user": user.username,
            },
        )

    before = {"status": risk.status, "version": risk.version}
    decision = RiskDecision(
        risk_item_id=risk_id,
        decision_package_id=payload.decision_package_id,
        decided_by=user.username,
        decision=payload.decision,
        rationale=payload.rationale,
    )
    db.add(decision)
    risk.status = "decided"
    risk.version += 1
    risk.updated_at = datetime.now(timezone.utc)
    db.flush()

    record_audit(
        db,
        user.username,
        "risk.decision_made",
        "risk_item",
        risk_id,
        before,
        {"status": "decided", "decision": payload.decision, "version": risk.version},
    )
    risk_decisions_total.labels(decision=payload.decision).inc()

    db.commit()
    db.refresh(decision)
    return decision


@risks_router.get("/{risk_id}/latest-package", response_model=DecisionPackageOut)
def get_latest_package(
    risk_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    risk = db.get(RiskItem, risk_id)
    if not risk:
        raise HTTPException(status_code=404, detail="Risk item not found")
    pkg = (
        db.query(DecisionPackage)
        .filter(DecisionPackage.risk_item_id == risk_id)
        .order_by(DecisionPackage.id.desc())
        .first()
    )
    if not pkg:
        raise HTTPException(status_code=404, detail="No package found for this risk item")
    return pkg


@packages_router.get("/{package_id}", response_model=DecisionPackageOut)
def get_decision_package(
    package_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    package = db.get(DecisionPackage, package_id)
    if not package:
        raise HTTPException(status_code=404, detail="Decision package not found")
    return package


@packages_router.post("/{package_id}/assessments", response_model=ReviewerAssessmentOut, status_code=201)
def add_assessment(
    package_id: int,
    payload: ReviewerAssessmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    package = db.get(DecisionPackage, package_id)
    if not package:
        raise HTTPException(status_code=404, detail="Decision package not found")

    if package.needs_info:
        raise HTTPException(
            status_code=422,
            detail="Cannot assess an incomplete package (needs_info=True); fix the risk item and generate a new package",
        )

    risk = db.get(RiskItem, package.risk_item_id)
    if risk and risk.status == "decided":
        raise HTTPException(
            status_code=409,
            detail="Risk item is already decided; no further assessments can be added",
        )

    latest_pkg = (
        db.query(DecisionPackage)
        .filter(
            DecisionPackage.risk_item_id == package.risk_item_id,
            DecisionPackage.needs_info.is_(False),
        )
        .order_by(DecisionPackage.id.desc())
        .first()
    )
    if latest_pkg is None or latest_pkg.id != package_id:
        raise HTTPException(
            status_code=409,
            detail="Assessments can only be added to the latest non-incomplete package for this risk item",
        )

    assessment = ReviewerAssessment(
        decision_package_id=package_id,
        reviewer=user.username,
        perspective=payload.perspective,
        vote=payload.vote,
        comment=payload.comment,
    )
    db.add(assessment)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="You have already submitted an assessment for this package",
        ) from exc

    record_audit(
        db,
        user.username,
        "risk.assessment_added",
        "decision_package",
        package_id,
        {},
        {"vote": payload.vote, "perspective": payload.perspective, "reviewer": user.username},
    )
    db.commit()
    db.refresh(assessment)
    return assessment
