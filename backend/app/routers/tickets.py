from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from app.db import get_db
from app.models import Ticket
from app.schemas import TicketCreate, TicketOut, TicketUpdate

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("", response_model=list[TicketOut])
def list_tickets(
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(Ticket).options(joinedload(Ticket.owner)).order_by(Ticket.created_at.desc())
    if status:
        query = query.filter(Ticket.status == status)
    if priority:
        query = query.filter(Ticket.priority == priority)
    if q:
        like = f"%{q}%"
        query = query.filter((Ticket.title.ilike(like)) | (Ticket.description.ilike(like)) | (Ticket.customer.ilike(like)))
    return query.limit(200).all()


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).options(joinedload(Ticket.owner)).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.post("", response_model=TicketOut, status_code=201)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)):
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
    db.commit()
    db.refresh(ticket)
    return ticket


@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket(ticket_id: int, payload: TicketUpdate, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(ticket, field, value)

    if data.get("status") == "resolved" and not ticket.resolved_at:
        ticket.resolved_at = datetime.utcnow()

    ticket.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(ticket)
    return ticket
