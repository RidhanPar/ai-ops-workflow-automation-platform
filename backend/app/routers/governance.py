from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.observability import current_trace_id
from app.core.security import get_current_user, require_roles
from app.db import get_db
from app.models import ApprovalRequest, AuditEvent, Ticket, TraceSpan, User
from app.schemas import ApprovalDecision
from app.services.audit import record_audit

router = APIRouter(tags=["governance"])


@router.get("/observability/traces")
def traces(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    spans = db.query(TraceSpan).order_by(TraceSpan.created_at.desc()).limit(100).all()
    return [
        {
            "trace_id": span.trace_id,
            "name": span.name,
            "type": span.span_type,
            "status": span.status,
            "latency_ms": span.latency_ms,
            "cost_usd": span.estimated_cost_usd,
            "error_type": span.error_type,
            "created_at": span.created_at,
        }
        for span in spans
    ]


@router.get("/governance/audits")
def audits(db: Session = Depends(get_db), _: User = Depends(require_roles("manager", "admin"))):
    return db.query(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(100).all()


@router.get("/governance/approvals")
def approvals(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(ApprovalRequest).order_by(ApprovalRequest.created_at.desc()).limit(100).all()


@router.post("/governance/approvals/{approval_id}/decision")
def decide_approval(
    approval_id: int,
    payload: ApprovalDecision,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("manager", "admin")),
):
    approval = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail="Approval request already decided")
    approval.status = payload.decision
    approval.reviewed_by = user.username
    approval.reviewed_at = datetime.utcnow()
    ticket = db.query(Ticket).filter(Ticket.id == approval.ticket_id).first()
    if payload.decision == "approved" and ticket:
        for field, value in approval.proposed_changes.items():
            if hasattr(ticket, field):
                setattr(ticket, field, value)
        ticket.approval_required = False
        ticket.version += 1
    record_audit(
        db,
        user.username,
        f"approval.{payload.decision}",
        "approval",
        approval.id,
        after={"reason": payload.reason, "ticket_id": approval.ticket_id, "trace_id": current_trace_id()},
    )
    db.commit()
    return {"id": approval.id, "status": approval.status}
