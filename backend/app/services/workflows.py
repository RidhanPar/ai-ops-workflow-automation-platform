from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Agent, Notification, Ticket, WorkflowExecution, WorkflowRule
from app.services.sla import get_sla_status


def _matches_trigger(ticket: Ticket, trigger: dict) -> bool:
    for key, expected in trigger.items():
        if key == "sla_status":
            actual = get_sla_status(ticket)
        else:
            actual = getattr(ticket, key, None)

        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def _least_loaded_agent(db: Session, team: str | None = None) -> Agent | None:
    query = db.query(Agent)
    if team:
        query = query.filter(Agent.team == team)
    return query.order_by(Agent.active_tickets.asc(), Agent.productivity_score.desc()).first()


def apply_action(db: Session, ticket: Ticket, action: dict) -> str:
    action_type = action.get("type")

    if action_type == "assign_team":
        team = action.get("team")
        agent = _least_loaded_agent(db, team)
        if agent:
            ticket.owner_id = agent.id
            agent.active_tickets += 1
            return f"Assigned to {agent.name} in {agent.team}"
        return "No matching agent found"

    if action_type == "set_priority":
        ticket.priority = action.get("priority", ticket.priority)
        return f"Priority set to {ticket.priority}"

    if action_type == "escalate":
        ticket.escalated = True
        ticket.status = "escalated"
        return "Ticket escalated"

    if action_type == "approval_required":
        ticket.approval_required = True
        return "Approval required flag enabled"

    if action_type == "notify":
        audience = action.get("audience", "operations")
        message = action.get("message", f"Action required for ticket {ticket.external_id}")
        db.add(Notification(ticket_id=ticket.id, audience=audience, message=message))
        return f"Notification sent to {audience}"

    if action_type == "mark_in_progress":
        ticket.status = "in_progress"
        return "Ticket moved to in_progress"

    return f"Unknown action skipped: {action_type}"


def run_workflows(db: Session, ticket_id: int | None = None) -> list[dict]:
    tickets_query = db.query(Ticket)
    if ticket_id:
        tickets_query = tickets_query.filter(Ticket.id == ticket_id)
    else:
        tickets_query = tickets_query.filter(Ticket.status.in_(["open", "in_progress", "waiting_customer", "escalated"]))

    tickets = tickets_query.all()
    rules = db.query(WorkflowRule).filter(WorkflowRule.enabled.is_(True)).all()
    results: list[dict] = []

    for ticket in tickets:
        for rule in rules:
            if not _matches_trigger(ticket, rule.trigger):
                continue

            actions_taken = [apply_action(db, ticket, action) for action in rule.actions]
            ticket.updated_at = datetime.utcnow()
            db.add(WorkflowExecution(
                workflow_id=rule.id,
                ticket_id=ticket.id,
                status="success",
                actions_taken=actions_taken,
            ))
            results.append({
                "ticket_id": ticket.id,
                "workflow": rule.name,
                "actions_taken": actions_taken,
            })

    db.commit()
    return results
