from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Ticket
from app.schemas import TicketAIRequest, TicketAIResponse
from app.services.ai import analyze_ticket

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/analyze-ticket", response_model=TicketAIResponse)
def analyze_ticket_endpoint(payload: TicketAIRequest, db: Session = Depends(get_db)):
    if payload.ticket_id:
        ticket = db.query(Ticket).filter(Ticket.id == payload.ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        result = analyze_ticket(ticket.title, ticket.description, ticket.customer, ticket.channel)
        ticket.ai_summary = result["summary"]
        ticket.ai_next_action = result["next_action"]
        ticket.category = result.get("category", ticket.category)
        ticket.priority = result.get("recommended_priority", ticket.priority)
        db.commit()
        return result

    if not payload.title or not payload.description:
        raise HTTPException(status_code=400, detail="Provide ticket_id or title and description")

    return analyze_ticket(
        title=payload.title,
        description=payload.description,
        customer=payload.customer or "Unknown",
        channel=payload.channel or "email",
    )
