import os
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Agent, KnowledgeDocument, Ticket, User, WorkflowRule
from app.services.knowledge import add_knowledge_document


def demo_password(username: str) -> str:
    return os.getenv(f"DEMO_{username.upper()}_PASSWORD", f"{username}-{'demo'}")


def seed_demo_data(db: Session) -> None:
    if db.query(User).count() == 0:
        db.add_all(
            [
                User(username="viewer", password_hash=hash_password(demo_password("viewer")), role="viewer"),
                User(username="operator", password_hash=hash_password(demo_password("operator")), role="operator"),
                User(username="manager", password_hash=hash_password(demo_password("manager")), role="manager"),
                User(username="admin", password_hash=hash_password(demo_password("admin")), role="admin"),
            ]
        )
        db.commit()

    if db.query(KnowledgeDocument).count() == 0:
        add_knowledge_document(
            db,
            "Billing payment failure runbook",
            "Validate invoice changes, payment status, and account history. Billing Ops owns payment and refund investigations.",
            ["billing", "payment", "refund"],
        )
        add_knowledge_document(
            db,
            "Critical outage escalation policy",
            "Critical outages require human-approved escalation, Technical Support investigation, and an operations-lead notification.",
            ["technical", "outage", "escalation"],
        )
        add_knowledge_document(
            db,
            "Policy appeal handling",
            "Policy appeals must be routed to Policy Ops and require approval before a final customer response is sent.",
            ["policy", "appeal", "approval"],
        )
        db.commit()

    if db.query(Agent).count() > 0:
        return

    agents = [
        Agent(
            name="Ridhan P",
            team="Workforce Desk",
            skill="SLA monitoring",
            active_tickets=2,
            avg_resolution_hours=5.5,
            productivity_score=94,
        ),
        Agent(
            name="Anna K",
            team="Billing Ops",
            skill="Billing investigations",
            active_tickets=4,
            avg_resolution_hours=7.2,
            productivity_score=88,
        ),
        Agent(
            name="Markus L",
            team="Technical Support",
            skill="API and platform issues",
            active_tickets=3,
            avg_resolution_hours=6.1,
            productivity_score=91,
        ),
        Agent(
            name="Sofia R",
            team="Policy Ops",
            skill="Policy reviews",
            active_tickets=5,
            avg_resolution_hours=9.4,
            productivity_score=86,
        ),
        Agent(
            name="Emils B",
            team="Escalations Desk",
            skill="Critical escalations",
            active_tickets=1,
            avg_resolution_hours=4.8,
            productivity_score=96,
        ),
    ]
    db.add_all(agents)
    db.commit()

    now = datetime.utcnow()
    tickets = [
        Ticket(
            external_id="AIOPS-00001",
            title="Campaign payment failed after invoice update",
            description="Customer reports that payment failed after invoice details were changed. They need campaign delivery restored quickly.",
            customer="Baltic Retail Group",
            channel="email",
            category="billing",
            priority="high",
            status="open",
            sla_due_at=now + timedelta(hours=3),
            owner_id=2,
        ),
        Ticket(
            external_id="AIOPS-00002",
            title="API sync error blocking daily reporting",
            description="Internal operations dashboard is not receiving ticket status updates from API sync. Reporting team cannot complete daily overview.",
            customer="Internal Reporting",
            channel="slack",
            category="technical",
            priority="critical",
            status="in_progress",
            sla_due_at=now + timedelta(hours=1),
            owner_id=3,
            escalated=True,
        ),
        Ticket(
            external_id="AIOPS-00003",
            title="Policy appeal waiting for review",
            description="Advertiser says account was restricted and appeal is waiting. Need policy review and response template.",
            customer="Nordic Ads Agency",
            channel="portal",
            category="policy",
            priority="medium",
            status="waiting_customer",
            sla_due_at=now + timedelta(hours=18),
            owner_id=4,
        ),
        Ticket(
            external_id="AIOPS-00004",
            title="Backlog spike in billing queue",
            description="Billing queue has increased after weekend. Need workload balancing and escalation check.",
            customer="Operations Lead",
            channel="email",
            category="workforce",
            priority="high",
            status="open",
            sla_due_at=now + timedelta(hours=6),
            owner_id=1,
        ),
        Ticket(
            external_id="AIOPS-00005",
            title="Customer asks for refund confirmation",
            description="Refund was processed but customer has not received confirmation. Need payment verification and customer update.",
            customer="Ecom Store LV",
            channel="chat",
            category="billing",
            priority="medium",
            status="resolved",
            sla_due_at=now - timedelta(days=1),
            created_at=now - timedelta(days=2),
            resolved_at=now - timedelta(days=1, hours=2),
            owner_id=2,
        ),
        Ticket(
            external_id="AIOPS-00006",
            title="Urgent outage affecting case assignment",
            description="Agents cannot receive new cases due to assignment engine failure. Team productivity and SLA are at risk.",
            customer="Support Operations",
            channel="slack",
            category="technical",
            priority="critical",
            status="open",
            sla_due_at=now - timedelta(hours=2),
            owner_id=5,
            escalated=True,
        ),
    ]
    db.add_all(tickets)

    workflows = [
        WorkflowRule(
            name="Critical Ticket Escalation",
            description="Escalates critical tickets and notifies the operations lead.",
            enabled=True,
            trigger={"priority": "critical"},
            actions=[
                {"type": "escalate"},
                {"type": "assign_team", "team": "Escalations Desk"},
                {
                    "type": "notify",
                    "audience": "operations_lead",
                    "message": "Critical ticket requires immediate attention.",
                },
            ],
        ),
        WorkflowRule(
            name="SLA At Risk Notification",
            description="Notifies workforce desk when a ticket is close to SLA breach.",
            enabled=True,
            trigger={"sla_status": "at_risk"},
            actions=[
                {"type": "assign_team", "team": "Workforce Desk"},
                {
                    "type": "notify",
                    "audience": "workforce_desk",
                    "message": "Ticket is at SLA risk. Review ownership and next action.",
                },
            ],
        ),
        WorkflowRule(
            name="Billing Ticket Routing",
            description="Routes billing tickets to the least loaded billing agent.",
            enabled=True,
            trigger={"category": "billing", "status": ["open", "in_progress"]},
            actions=[
                {"type": "assign_team", "team": "Billing Ops"},
                {"type": "mark_in_progress"},
            ],
        ),
        WorkflowRule(
            name="Policy Approval Required",
            description="Marks policy tickets as approval required before customer response.",
            enabled=True,
            trigger={"category": "policy"},
            actions=[
                {"type": "approval_required"},
                {"type": "assign_team", "team": "Policy Ops"},
            ],
        ),
    ]
    db.add_all(workflows)
    db.commit()
