from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.core.security import get_current_user, require_roles
from app.db import get_db
from app.models import Ticket, User
from app.schemas import TicketCreate, TicketOut, TicketUpdate
from app.services.audit import record_audit

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("", response_model=list[TicketOut])
def list_tickets(
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = db.query(Ticket).options(joinedload(Ticket.owner)).order_by(Ticket.created_at.desc())
    if status:
        query = query.filter(Ticket.status == status)
    if priority:
        query = query.filter(Ticket.priority == priority)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Ticket.title.ilike(like)) | (Ticket.description.ilike(like)) | (Ticket.customer.ilike(like))
        )
    return query.limit(200).all()


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    ticket = db.query(Ticket).options(joinedload(Ticket.owner)).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.post("", response_model=TicketOut, status_code=201)
def create_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("operator", "manager", "admin")),
):
    next_id = db.query(Ticket).count() + 1
    ticket = Ticket(
        external_id=f"AIOPS-{next_id:05d}",
        title=payload.title,
        description=payload.description,
        customer=payload.customer,
        channel=payload.channel,
        category=payload.category,
        priority=payload.priority,
        sla_due_at=datetime.utcnow() + timedelta(hours=payload.sla_hours),
        owner_id=payload.owner_id,
    )
    db.add(ticket)
    db.flush()
    record_audit(db, user.username, "ticket.created", "ticket", ticket.id, after=payload.model_dump())
    db.commit()
    db.refresh(ticket)
    return ticket


@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("operator", "manager", "admin")),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    data = payload.model_dump(exclude_unset=True)
    expected_version = data.pop("version", None)
    if expected_version is not None and expected_version != ticket.version:
        raise HTTPException(status_code=409, detail=f"Ticket version conflict; current version is {ticket.version}")
    before = {field: getattr(ticket, field) for field in data}
    for field, value in data.items():
        setattr(ticket, field, value)

    if data.get("status") == "resolved" and not ticket.resolved_at:
        ticket.resolved_at = datetime.utcnow()

    ticket.updated_at = datetime.utcnow()
    ticket.version += 1
    record_audit(db, user.username, "ticket.updated", "ticket", ticket.id, before=before, after=data)
    db.commit()
    db.refresh(ticket)
    return ticket
