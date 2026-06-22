from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db import get_db
from app.models import Ticket, User
from app.schemas import TicketAIRequest, TicketAIResponse
from app.services.agent import run_ticket_agent

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/analyze-ticket", response_model=TicketAIResponse)
def analyze_ticket_endpoint(
    payload: TicketAIRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.ticket_id:
        ticket = db.query(Ticket).filter(Ticket.id == payload.ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return run_ticket_agent(db, ticket, user.username, payload.allow_write_tools)

    if not payload.title or not payload.description:
        raise HTTPException(status_code=400, detail="Provide ticket_id or title and description")

    raise HTTPException(
        status_code=400, detail="Ad-hoc analysis is disabled; create a ticket for an auditable agent run"
    )
