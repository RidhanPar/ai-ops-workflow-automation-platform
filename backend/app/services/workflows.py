from datetime import datetime

from sqlalchemy.orm import Session

from app.core.metrics import human_approval_gates_triggered_total
from app.core.observability import current_trace_id, traced_span
from app.models import Agent, ApprovalRequest, Notification, Ticket, WorkflowExecution, WorkflowRule
from app.services.audit import record_audit
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


def apply_action(db: Session, ticket: Ticket, action: dict, actor: str = "workflow-engine") -> str:
    action_type = action.get("type")

    if action_type == "assign_team":
        team = action.get("team")
        agent = _least_loaded_agent(db, team)
        if agent and ticket.owner_id != agent.id:
            previous_agent = db.get(Agent, ticket.owner_id) if ticket.owner_id else None
            if previous_agent:
                previous_agent.active_tickets = max(0, previous_agent.active_tickets - 1)
            ticket.owner_id = agent.id
            agent.active_tickets += 1
            return f"Assigned to {agent.name} in {agent.team}"
        if agent:
            return f"Already assigned to {agent.name} in {agent.team}"
        return "No matching agent found"

    if action_type == "set_priority":
        ticket.priority = action.get("priority", ticket.priority)
        return f"Priority set to {ticket.priority}"

    if action_type == "escalate":
        db.add(
            ApprovalRequest(
                ticket_id=ticket.id,
                action_type="workflow_escalate",
                requested_by=actor,
                reason="Workflow requested a sensitive escalation action.",
                proposed_changes={"escalated": True, "status": "escalated"},
            )
        )
        ticket.approval_required = True
        human_approval_gates_triggered_total.labels(action_type="workflow_escalate").inc()
        return "Escalation queued for human approval"

    if action_type == "approval_required":
        ticket.approval_required = True
        human_approval_gates_triggered_total.labels(action_type="approval_required").inc()
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


def run_workflows(
    db: Session, idempotency_key: str, ticket_id: int | None = None, actor: str = "workflow-engine"
) -> list[dict]:
    existing = (
        db.query(WorkflowExecution).filter(WorkflowExecution.idempotency_key.like(f"{idempotency_key}:%")).first()
    )
    if existing:
        return [
            {"ticket_id": existing.ticket_id, "workflow": "idempotent_replay", "actions_taken": existing.actions_taken}
        ]

    tickets_query = db.query(Ticket)
    if ticket_id:
        tickets_query = tickets_query.filter(Ticket.id == ticket_id)
    else:
        tickets_query = tickets_query.filter(
            Ticket.status.in_(["open", "in_progress", "waiting_customer", "escalated"])
        )

    tickets = tickets_query.all()
    rules = db.query(WorkflowRule).filter(WorkflowRule.enabled.is_(True)).all()
    results: list[dict] = []

    for ticket in tickets:
        for rule in rules:
            if not _matches_trigger(ticket, rule.trigger):
                continue

            execution_key = f"{idempotency_key}:{ticket.id}:{rule.id}"
            if db.query(WorkflowExecution).filter(WorkflowExecution.idempotency_key == execution_key).first():
                continue
            with traced_span(db, rule.name, "workflow", {"ticket_id": ticket.id, "workflow_id": rule.id}):
                before = {"status": ticket.status, "priority": ticket.priority, "owner_id": ticket.owner_id}
                actions_taken = [apply_action(db, ticket, action, actor) for action in rule.actions]
                ticket.updated_at = datetime.utcnow()
                ticket.version += 1
                db.add(
                    WorkflowExecution(
                        workflow_id=rule.id,
                        ticket_id=ticket.id,
                        status="success",
                        actions_taken=actions_taken,
                        trace_id=current_trace_id(),
                        idempotency_key=execution_key,
                    )
                )
                record_audit(
                    db,
                    actor,
                    "workflow.executed",
                    "ticket",
                    ticket.id,
                    before,
                    {"status": ticket.status, "priority": ticket.priority, "owner_id": ticket.owner_id},
                )
            results.append(
                {
                    "ticket_id": ticket.id,
                    "workflow": rule.name,
                    "actions_taken": actions_taken,
                }
            )

    db.commit()
    return results
