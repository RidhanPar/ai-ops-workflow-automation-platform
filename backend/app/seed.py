import os
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    Agent,
    DecisionPackage,
    KnowledgeDocument,
    ReviewerAssessment,
    RiskDecision,
    RiskItem,
    Ticket,
    User,
    WorkflowRule,
)
from app.services.knowledge import add_knowledge_document

TICKET_KNOWLEDGE_DOCUMENTS: list[tuple[str, str, list[str]]] = [
    (
        "Billing payment failure runbook",
        "Validate invoice changes, payment status, and account history. Billing Ops owns payment and refund investigations.",
        ["billing", "payment", "refund"],
    ),
    (
        "Critical outage escalation policy",
        "Critical outages require human-approved escalation, Technical Support investigation, and an operations-lead notification.",
        ["technical", "outage", "escalation"],
    ),
    (
        "Policy appeal handling",
        "Policy appeals must be routed to Policy Ops and require approval before a final customer response is sent.",
        ["policy", "appeal", "approval"],
    ),
]

RISK_KNOWLEDGE_DOCUMENTS: list[tuple[str, str, list[str]]] = [
    (
        "Risk scoring and treatment guide",
        "Risk score = impact x likelihood on a 1-5 scale. Scores 1-5: accept with controls. 6-11: transfer or accept. 12-19: mitigate. 20-25: avoid or escalate immediately. Document treatment rationale and residual risk.",
        ["risk", "scoring", "treatment", "accept", "mitigate", "transfer", "avoid"],
    ),
    (
        "GDPR and data protection risk policy",
        "Personal data processing risks require a data protection impact assessment. Vendor data sharing needs a DPA. Retention breaches must be reported within 72 hours. Owners are accountable for DPIA completion.",
        ["gdpr", "data", "compliance", "privacy", "dpia"],
    ),
    (
        "Third-party and supplier risk controls",
        "Vendors with access to production systems require annual security assessment. SLA breaches by critical vendors must be escalated to procurement and IT security. Contracts must include right-to-audit clauses.",
        ["vendor", "supplier", "third-party", "security", "audit"],
    ),
    (
        "Incident response and business continuity",
        "Business continuity plans must be tested annually. RTO for critical systems is 4 hours. Severity-1 incidents require executive notification within 30 minutes. Post-incident review is mandatory within 5 days.",
        ["incident", "continuity", "rto", "recovery", "escalation"],
    ),
    (
        "Access control and privileged access management",
        "Privileged access requires MFA and quarterly review. Shared accounts are prohibited. Service account passwords rotate every 90 days. Terminated employees must be deprovisioned within 24 hours.",
        ["access", "iam", "mfa", "privileged", "deprovisioning"],
    ),
]


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

    _add_missing_documents(db, TICKET_KNOWLEDGE_DOCUMENTS)
    _seed_agents(db)
    _seed_tickets(db)
    _seed_workflows(db)
    _add_missing_documents(db, RISK_KNOWLEDGE_DOCUMENTS)
    _seed_risk_data(db)


def _add_missing_documents(db: Session, documents: list[tuple[str, str, list[str]]]) -> None:
    existing = {title for (title,) in db.query(KnowledgeDocument.title)}
    for title, content, tags in documents:
        if title not in existing:
            add_knowledge_document(db, title, content, tags)
    db.commit()


def _seed_agents(db: Session) -> None:
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


def _seed_tickets(db: Session) -> None:
    if db.query(Ticket).count() > 0:
        return
    now = datetime.now(timezone.utc)
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
    db.commit()


def _seed_workflows(db: Session) -> None:
    if db.query(WorkflowRule).count() > 0:
        return
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


def _seed_risk_data(db: Session) -> None:
    now = datetime.now(timezone.utc)
    risks = [
        RiskItem(
            title="Customer PII stored in unencrypted S3 bucket",
            description="Analytics pipeline writes customer identifiers and behavioural data to an S3 bucket without server-side encryption. Misconfigured bucket policy would expose PII to unauthorised parties.",
            business_unit="Data Platform",
            owner="data-platform-lead",
            impact=5,
            likelihood=3,
            proposed_mitigation="Enable S3 SSE-KMS on the bucket and enforce encryption via bucket policy. Rotate existing objects with an S3 Batch Operations job.",
            status="decided",
            version=2,
            created_at=now - timedelta(days=30),
            updated_at=now - timedelta(days=20),
        ),
        RiskItem(
            title="Payment processor single point of failure",
            description="All payment transactions route through a single gateway integration with no fallback. A provider outage or API deprecation halts all revenue collection until manual intervention.",
            business_unit="Payments",
            owner="payments-lead",
            impact=5,
            likelihood=2,
            proposed_mitigation="Add a secondary payment gateway in active-passive configuration with automatic circuit-breaker failover.",
            status="in_review",
            version=1,
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=10),
        ),
        RiskItem(
            title="GDPR consent gap in marketing email system",
            description="The marketing email platform does not record granular consent timestamps per subscriber. A data subject access request cannot produce a full audit trail of consent, exposing the organisation to GDPR enforcement.",
            business_unit="Marketing",
            owner="privacy-officer",
            impact=4,
            likelihood=4,
            proposed_mitigation="Extend the subscriber schema to record ISO-8601 consent timestamps and opt-in source. Retroactively re-confirm consent for subscribers added before the change.",
            status="in_review",
            version=1,
            created_at=now - timedelta(days=7),
            updated_at=now - timedelta(days=7),
        ),
        RiskItem(
            title="Privileged database credentials hardcoded in CI pipeline",
            description="Database migration scripts in the internal repository contain production credentials in plain text. Any developer with repository access can connect directly to the production database.",
            business_unit="Engineering",
            owner="security-lead",
            impact=5,
            likelihood=4,
            proposed_mitigation="Remove credentials from repository immediately. Rotate all affected passwords. Move secrets to a vault solution and inject via environment at runtime.",
            status="decided",
            version=2,
            created_at=now - timedelta(days=45),
            updated_at=now - timedelta(days=35),
        ),
        RiskItem(
            title="Third-party analytics SDK collecting data without DPA",
            description="A front-end analytics library from a US-based vendor sends page interaction data including IP addresses to servers outside the EU. No data processing agreement is in place with this vendor.",
            business_unit="Product",
            owner="privacy-officer",
            impact=3,
            likelihood=5,
            proposed_mitigation="Suspend the SDK immediately. Evaluate an EU-hosted alternative or negotiate a GDPR-compliant DPA with the current vendor before reactivation.",
            status="draft",
            version=1,
            created_at=now - timedelta(days=3),
            updated_at=now - timedelta(days=3),
        ),
        RiskItem(
            title="No tested disaster recovery plan for core API",
            description="The operations team has never run a full DR test for the main API service. The documented RTO is 4 hours but no evidence exists that this target is achievable.",
            business_unit="Operations",
            owner="ops-manager",
            impact=4,
            likelihood=3,
            proposed_mitigation="Schedule a DR exercise in a staging environment within Q1. Document RTO evidence and create an annual DR test calendar.",
            status="draft",
            version=1,
            created_at=now - timedelta(days=5),
            updated_at=now - timedelta(days=5),
        ),
        RiskItem(
            title="Stale vendor access to production environment",
            description="Three former contractors still have active VPN credentials and service account access to the production Kubernetes cluster. Accounts were not deprovisioned at contract end.",
            business_unit="IT Security",
            owner="it-security-lead",
            impact=5,
            likelihood=2,
            proposed_mitigation="Revoke access immediately. Audit all service accounts created in the last 18 months. Automate deprovisioning via the HR system offboarding workflow.",
            status="decided",
            version=2,
            created_at=now - timedelta(days=60),
            updated_at=now - timedelta(days=50),
        ),
        # Incomplete risks (no proposed_mitigation) - trigger needs_info branch
        RiskItem(
            title="Missing audit logs on database access layer",
            description="Production database queries are not being logged at the application layer. Without query logs, forensic investigation of data breaches or insider threats is not possible.",
            business_unit="Engineering",
            owner="db-admin",
            impact=4,
            likelihood=3,
            proposed_mitigation=None,
            status="draft",
            version=1,
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=2),
        ),
        RiskItem(
            title="Unvalidated redirects in OAuth callback flow",
            description="The OAuth callback handler accepts redirect URIs without validating against an allowlist. An attacker could craft a phishing URL that appears to originate from the trusted domain.",
            business_unit="Engineering",
            owner="security-lead",
            impact=3,
            likelihood=4,
            proposed_mitigation=None,
            status="draft",
            version=1,
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1),
        ),
        # Complete drafts - ready for package generation
        RiskItem(
            title="Legacy SSH key pairs without rotation policy",
            description="SSH key pairs used for server access have not been rotated in over two years. Compromised keys could grant persistent access to production infrastructure without detection.",
            business_unit="IT Security",
            owner="it-security-lead",
            impact=4,
            likelihood=2,
            proposed_mitigation="Implement a key rotation policy with a 12-month maximum lifespan. Automate rotation via the secrets management system and revoke all keys older than 24 months.",
            status="draft",
            version=1,
            created_at=now - timedelta(days=4),
            updated_at=now - timedelta(days=4),
        ),
        RiskItem(
            title="No rate limiting on public API endpoints",
            description="Public-facing API endpoints do not enforce request rate limits. A misconfigured client or attacker could flood the API, causing service degradation or elevated infrastructure costs.",
            business_unit="Platform",
            owner="platform-lead",
            impact=3,
            likelihood=3,
            proposed_mitigation="Implement rate limiting at the API gateway. Set per-IP and per-key limits with graduated backoff. Monitor for abuse patterns using existing observability tooling.",
            status="draft",
            version=1,
            created_at=now - timedelta(days=6),
            updated_at=now - timedelta(days=6),
        ),
        RiskItem(
            title="Unrestricted outbound traffic from application servers",
            description="Application servers can make outbound connections to any internet endpoint. If compromised, malware could exfiltrate data or establish a command-and-control channel without detection.",
            business_unit="Operations",
            owner="ops-manager",
            impact=4,
            likelihood=2,
            proposed_mitigation="Apply egress firewall rules to application servers limiting outbound connections to approved destinations. Log all denied outbound attempts to the SIEM.",
            status="draft",
            version=1,
            created_at=now - timedelta(days=8),
            updated_at=now - timedelta(days=8),
        ),
    ]
    # Check for the demo risks themselves, so risks users created after an upgrade do not block seeding.
    if db.query(RiskItem).filter(RiskItem.title.in_([risk.title for risk in risks])).first() is not None:
        return
    db.add_all(risks)
    db.flush()

    decided = {r.title: r for r in risks if r.status == "decided"}

    pii_risk = decided["Customer PII stored in unencrypted S3 bucket"]
    pii_pkg = DecisionPackage(
        risk_item_id=pii_risk.id,
        idempotency_key="seed-pkg-pii-s3-001",
        completeness_gaps=[],
        needs_info=False,
        best_practices=[],
        past_decisions=[],
        source="seed",
        cited_knowledge_ids=[],
        cited_decision_ids=[],
        perspectives=[
            {
                "area": "security",
                "key_concerns": ["Unencrypted data at rest violates data security standards"],
                "reviewer_questions": ["Is the bucket publicly accessible?"],
                "suggested_treatment": "mitigate",
                "confidence": 0.9,
            },
            {
                "area": "compliance",
                "key_concerns": ["GDPR Article 32 requires appropriate technical security measures"],
                "reviewer_questions": ["Is a DPIA required for this data store?"],
                "suggested_treatment": "mitigate",
                "confidence": 0.9,
            },
            {
                "area": "business",
                "key_concerns": ["Regulatory fine risk up to 4% of annual global turnover"],
                "reviewer_questions": ["What is the volume and sensitivity of data affected?"],
                "suggested_treatment": "mitigate",
                "confidence": 0.8,
            },
        ],
        risk_score=15,
        recommended_treatment="mitigate",
        safety_flags=[],
        generated_by="seed",
        trace_id="seed-trace-pii-001",
        created_at=now - timedelta(days=25),
    )

    creds_risk = decided["Privileged database credentials hardcoded in CI pipeline"]
    creds_pkg = DecisionPackage(
        risk_item_id=creds_risk.id,
        idempotency_key="seed-pkg-creds-ci-001",
        completeness_gaps=[],
        needs_info=False,
        best_practices=[],
        past_decisions=[],
        source="seed",
        cited_knowledge_ids=[],
        cited_decision_ids=[],
        perspectives=[
            {
                "area": "security",
                "key_concerns": ["Exposed credentials allow direct unauthorised production DB access"],
                "reviewer_questions": ["How many developers have repository access?"],
                "suggested_treatment": "avoid",
                "confidence": 0.95,
            },
            {
                "area": "compliance",
                "key_concerns": ["Credential exposure may trigger breach notification obligations"],
                "reviewer_questions": ["Has any unauthorised access occurred?"],
                "suggested_treatment": "avoid",
                "confidence": 0.9,
            },
            {
                "area": "business",
                "key_concerns": ["Immediate reputational and operational risk"],
                "reviewer_questions": ["Is there evidence of data exfiltration?"],
                "suggested_treatment": "avoid",
                "confidence": 0.9,
            },
        ],
        risk_score=20,
        recommended_treatment="avoid",
        safety_flags=[],
        generated_by="seed",
        trace_id="seed-trace-creds-001",
        created_at=now - timedelta(days=40),
    )

    vendor_risk = decided["Stale vendor access to production environment"]
    vendor_pkg = DecisionPackage(
        risk_item_id=vendor_risk.id,
        idempotency_key="seed-pkg-vendor-access-001",
        completeness_gaps=[],
        needs_info=False,
        best_practices=[],
        past_decisions=[],
        source="seed",
        cited_knowledge_ids=[],
        cited_decision_ids=[],
        perspectives=[
            {
                "area": "security",
                "key_concerns": ["Stale privileged access is a critical attack surface"],
                "reviewer_questions": ["Have the stale credentials been used recently?"],
                "suggested_treatment": "mitigate",
                "confidence": 0.9,
            },
            {
                "area": "compliance",
                "key_concerns": ["Access control policy requires quarterly access review"],
                "reviewer_questions": ["When was the last formal access review conducted?"],
                "suggested_treatment": "mitigate",
                "confidence": 0.85,
            },
            {
                "area": "business",
                "key_concerns": ["Production environment compromise risk"],
                "reviewer_questions": ["Which production systems can the stale accounts access?"],
                "suggested_treatment": "mitigate",
                "confidence": 0.85,
            },
        ],
        risk_score=10,
        recommended_treatment="mitigate",
        safety_flags=[],
        generated_by="seed",
        trace_id="seed-trace-vendor-001",
        created_at=now - timedelta(days=55),
    )

    db.add_all([pii_pkg, creds_pkg, vendor_pkg])
    db.flush()

    for pkg in [pii_pkg, creds_pkg, vendor_pkg]:
        db.add(
            ReviewerAssessment(
                decision_package_id=pkg.id,
                reviewer="security-reviewer",
                perspective="security",
                vote="mitigate",
                comment="Risk is confirmed and the mitigation plan is appropriate for the exposure level.",
                created_at=now - timedelta(days=20),
            )
        )
        db.add(
            ReviewerAssessment(
                decision_package_id=pkg.id,
                reviewer="compliance-reviewer",
                perspective="compliance",
                vote="mitigate",
                comment="Compliance risk is material. Mitigation aligns with regulatory and policy requirements.",
                created_at=now - timedelta(days=19),
            )
        )
    db.flush()

    db.add(
        RiskDecision(
            risk_item_id=pii_risk.id,
            decision_package_id=pii_pkg.id,
            decided_by="manager",
            decision="mitigate",
            rationale="Encryption is a standard, low-cost control. Mitigation approved. Implement SSE-KMS within 30 days.",
            created_at=now - timedelta(days=18),
        )
    )
    db.add(
        RiskDecision(
            risk_item_id=creds_risk.id,
            decision_package_id=creds_pkg.id,
            decided_by="manager",
            decision="mitigate",
            rationale="Immediate credential rotation required. Vault adoption approved as long-term control. Zero tolerance for plaintext credentials in source control.",
            created_at=now - timedelta(days=38),
        )
    )
    db.add(
        RiskDecision(
            risk_item_id=vendor_risk.id,
            decision_package_id=vendor_pkg.id,
            decided_by="manager",
            decision="mitigate",
            rationale="Access revoked immediately. Automated deprovisioning via HR integration approved for implementation within 60 days.",
            created_at=now - timedelta(days=52),
        )
    )
    db.commit()
