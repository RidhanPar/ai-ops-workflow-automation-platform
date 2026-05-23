import csv
from pathlib import Path
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from app.db import get_db
from app.models import Ticket
from app.services.sla import get_sla_status

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/powerbi/tickets")
def powerbi_tickets(db: Session = Depends(get_db)):
    tickets = db.query(Ticket).options(joinedload(Ticket.owner)).order_by(Ticket.created_at.desc()).all()
    return [
        {
            "ticket_id": ticket.id,
            "external_id": ticket.external_id,
            "title": ticket.title,
            "customer": ticket.customer,
            "channel": ticket.channel,
            "category": ticket.category,
            "priority": ticket.priority,
            "status": ticket.status,
            "owner": ticket.owner.name if ticket.owner else None,
            "team": ticket.owner.team if ticket.owner else None,
            "created_at": ticket.created_at.isoformat(),
            "sla_due_at": ticket.sla_due_at.isoformat(),
            "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
            "sla_status": get_sla_status(ticket),
            "escalated": ticket.escalated,
        }
        for ticket in tickets
    ]


@router.get("/powerbi/tickets.csv")
def powerbi_tickets_csv(db: Session = Depends(get_db)):
    rows = powerbi_tickets(db)
    output_path = Path("/data/powerbi_tickets_export.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if rows:
        with output_path.open("w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    else:
        output_path.write_text("ticket_id,external_id,title\n", encoding="utf-8")

    return FileResponse(output_path, media_type="text/csv", filename="powerbi_tickets_export.csv")
