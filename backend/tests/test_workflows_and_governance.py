from app.db import SessionLocal
from app.models import Agent, ApprovalRequest, WorkflowExecution
from app.services.workflows import _matches_trigger, apply_action


def test_trigger_matching_supports_lists_and_sla(database):
    db = SessionLocal()
    ticket = db.query(__import__("app.models", fromlist=["Ticket"]).Ticket).filter_by(id=1).first()
    assert _matches_trigger(ticket, {"category": "billing", "status": ["open", "in_progress"]})
    assert not _matches_trigger(ticket, {"priority": "low"})
    db.close()


def test_sensitive_action_creates_approval_instead_of_escalating(database):
    db = SessionLocal()
    Ticket = __import__("app.models", fromlist=["Ticket"]).Ticket
    ticket = db.query(Ticket).filter_by(id=1).first()
    ticket.escalated = False
    result = apply_action(db, ticket, {"type": "escalate"}, actor="test")
    db.commit()
    assert "approval" in result.lower()
    assert ticket.escalated is False
    assert db.query(ApprovalRequest).filter_by(ticket_id=ticket.id, status="pending").count() >= 1
    db.close()


def test_assign_team_does_not_inflate_existing_owner_workload(database):
    db = SessionLocal()
    Ticket = __import__("app.models", fromlist=["Ticket"]).Ticket
    ticket = db.query(Ticket).filter_by(id=1).first()
    agent = db.query(Agent).order_by(Agent.active_tickets.asc()).first()
    ticket.owner_id = agent.id
    starting_count = agent.active_tickets

    result = apply_action(db, ticket, {"type": "assign_team", "team": agent.team})

    assert "Already assigned" in result
    assert agent.active_tickets == starting_count
    db.close()


def test_workflow_runs_are_idempotent(client, operator_headers):
    key = "test-idempotency-123"
    first = client.post("/workflows/run", headers=operator_headers, json={"ticket_id": 1, "idempotency_key": key})
    second = client.post("/workflows/run", headers=operator_headers, json={"ticket_id": 1, "idempotency_key": key})
    assert first.status_code == 200
    assert second.status_code == 200
    db = SessionLocal()
    assert db.query(WorkflowExecution).filter(WorkflowExecution.idempotency_key.like(f"{key}:%")).count() >= 1
    count = db.query(WorkflowExecution).filter(WorkflowExecution.idempotency_key.like(f"{key}:%")).count()
    assert count == len(first.json()["executions"])
    db.close()


def test_manager_can_approve_sensitive_action(client, manager_headers):
    approvals = client.get("/governance/approvals", headers=manager_headers).json()
    pending = next(item for item in approvals if item["status"] == "pending")
    response = client.post(
        f"/governance/approvals/{pending['id']}/decision",
        headers=manager_headers,
        json={"decision": "approved", "reason": "Validated operational impact"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
