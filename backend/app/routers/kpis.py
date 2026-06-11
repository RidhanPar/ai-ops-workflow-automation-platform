from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db import get_db
from app.models import Agent, Ticket, User, WorkflowExecution
from app.schemas import KPIOverview, TrendPoint
from app.services.sla import get_sla_status

router = APIRouter(prefix="/kpis", tags=["kpis"])


@router.get("/overview", response_model=KPIOverview)
def overview(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    tickets = db.query(Ticket).all()
    open_tickets = [t for t in tickets if t.status != "resolved"]
    resolved = [t for t in tickets if t.status == "resolved"]
    breached = [t for t in tickets if get_sla_status(t) in ["breached", "breached_resolved"]]
    at_risk = [t for t in tickets if get_sla_status(t) == "at_risk"]

    resolution_hours = []
    for ticket in resolved:
        if ticket.resolved_at:
            resolution_hours.append((ticket.resolved_at - ticket.created_at).total_seconds() / 3600)

    return KPIOverview(
        total_tickets=len(tickets),
        open_tickets=len(open_tickets),
        escalated_tickets=sum(1 for t in tickets if t.escalated),
        sla_at_risk=len(at_risk),
        sla_breached=len(breached),
        resolved_tickets=len(resolved),
        avg_resolution_hours=round(sum(resolution_hours) / len(resolution_hours), 2) if resolution_hours else 0,
        automation_executions=db.query(WorkflowExecution).count(),
    )


@router.get("/trends", response_model=list[TrendPoint])
def trends(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    since = datetime.utcnow() - timedelta(days=13)
    tickets = db.query(Ticket).filter(Ticket.created_at >= since).all()
    trend_map = defaultdict(lambda: {"created": 0, "resolved": 0})

    for i in range(14):
        day = (since + timedelta(days=i)).date().isoformat()
        trend_map[day]

    for ticket in tickets:
        created_day = ticket.created_at.date().isoformat()
        trend_map[created_day]["created"] += 1
        if ticket.resolved_at:
            resolved_day = ticket.resolved_at.date().isoformat()
            trend_map[resolved_day]["resolved"] += 1

    return [
        TrendPoint(date=day, created=values["created"], resolved=values["resolved"])
        for day, values in sorted(trend_map.items())
    ]


@router.get("/backlog")
def backlog(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    tickets = db.query(Ticket).filter(Ticket.status != "resolved").all()
    by_status = defaultdict(int)
    by_priority = defaultdict(int)
    by_category = defaultdict(int)
    for ticket in tickets:
        by_status[ticket.status] += 1
        by_priority[ticket.priority] += 1
        by_category[ticket.category] += 1
    return {
        "by_status": [{"name": k, "value": v} for k, v in by_status.items()],
        "by_priority": [{"name": k, "value": v} for k, v in by_priority.items()],
        "by_category": [{"name": k, "value": v} for k, v in by_category.items()],
    }


@router.get("/workforce")
def workforce(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    agents = db.query(Agent).order_by(Agent.team, Agent.productivity_score.desc()).all()
    return [
        {
            "agent": agent.name,
            "team": agent.team,
            "skill": agent.skill,
            "active_tickets": agent.active_tickets,
            "avg_resolution_hours": agent.avg_resolution_hours,
            "productivity_score": agent.productivity_score,
        }
        for agent in agents
    ]
