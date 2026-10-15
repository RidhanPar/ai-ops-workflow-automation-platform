from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AgentOut(BaseModel):
    id: int
    name: str
    team: str
    skill: str
    active_tickets: int
    avg_resolution_hours: float
    productivity_score: float

    model_config = {"from_attributes": True}


class TicketCreate(BaseModel):
    title: str = Field(min_length=5, max_length=255)
    description: str = Field(min_length=10)
    customer: str
    channel: str = "email"
    category: str = "general"
    priority: str = "medium"
    sla_hours: int = 24
    owner_id: int | None = None


class TicketUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    owner_id: int | None = None
    category: str | None = None
    escalated: bool | None = None
    approval_required: bool | None = None
    version: int | None = None


class TicketOut(BaseModel):
    id: int
    external_id: str
    title: str
    description: str
    customer: str
    channel: str
    category: str
    status: str
    priority: str
    sla_due_at: datetime
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    escalated: bool
    approval_required: bool
    ai_summary: str | None
    ai_next_action: str | None
    version: int
    owner: AgentOut | None = None

    model_config = {"from_attributes": True}


class WorkflowRuleCreate(BaseModel):
    name: str
    description: str
    enabled: bool = True
    trigger: dict
    actions: list[dict]


class WorkflowRuleOut(BaseModel):
    id: int
    name: str
    description: str
    enabled: bool
    trigger: dict
    actions: list[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkflowRunRequest(BaseModel):
    ticket_id: int | None = None
    idempotency_key: str = Field(min_length=8, max_length=160)


class WorkflowRunResult(BaseModel):
    ticket_id: int
    workflow: str
    actions_taken: list[str]


class TicketAIRequest(BaseModel):
    ticket_id: int | None = None
    title: str | None = None
    description: str | None = None
    customer: str | None = None
    channel: str | None = None
    allow_write_tools: bool = False


class TicketAIResponse(BaseModel):
    summary: str
    category: str
    recommended_priority: str
    recommended_team: str
    next_action: str
    confidence: float
    source: str
    trace_id: str
    tools_used: list[str] = Field(default_factory=list)
    knowledge_sources: list[str] = Field(default_factory=list)
    latency_ms: float = 0
    estimated_cost_usd: float = 0
    safety_flags: list[str] = Field(default_factory=list)


class TicketAnalysis(BaseModel):
    summary: str = Field(min_length=10, max_length=500)
    category: Literal["billing", "technical", "policy", "workforce", "general"]
    recommended_priority: Literal["low", "medium", "high", "critical"]
    recommended_team: Literal[
        "Billing Ops", "Technical Support", "Policy Ops", "Workforce Desk", "Escalations Desk", "General Support"
    ]
    next_action: str = Field(min_length=10, max_length=500)
    confidence: float = Field(ge=0, le=1)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class ApprovalDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: str = Field(min_length=3)


class AgentRunRequest(BaseModel):
    ticket_id: int
    allow_write_tools: bool = False


class KPIOverview(BaseModel):
    total_tickets: int
    open_tickets: int
    escalated_tickets: int
    sla_at_risk: int
    sla_breached: int
    resolved_tickets: int
    avg_resolution_hours: float
    automation_executions: int


class TrendPoint(BaseModel):
    date: str
    created: int
    resolved: int


class RiskItemCreate(BaseModel):
    title: str = Field(min_length=5, max_length=255)
    description: str = Field(min_length=10)
    business_unit: str = Field(min_length=1, max_length=120)
    owner: str = Field(min_length=1, max_length=120)
    impact: int = Field(ge=1, le=5)
    likelihood: int = Field(ge=1, le=5)
    proposed_mitigation: str | None = None


class RiskItemOut(BaseModel):
    id: int
    title: str
    description: str
    business_unit: str
    owner: str
    impact: int
    likelihood: int
    proposed_mitigation: str | None
    status: str
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DecisionPackageRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=160)


class ReviewerAssessmentOut(BaseModel):
    id: int
    decision_package_id: int
    reviewer: str
    perspective: str
    vote: str
    comment: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DecisionPackageOut(BaseModel):
    id: int
    risk_item_id: int
    idempotency_key: str
    completeness_gaps: list[str]
    needs_info: bool
    best_practices: list[dict]
    past_decisions: list[dict]
    perspectives: list[dict]
    risk_score: int
    recommended_treatment: str
    safety_flags: list[str]
    generated_by: str
    source: str
    cited_knowledge_ids: list[int]
    cited_decision_ids: list[int]
    trace_id: str
    created_at: datetime
    assessments: list[ReviewerAssessmentOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ReviewerAssessmentCreate(BaseModel):
    perspective: Literal["security", "compliance", "business"]
    vote: Literal["accept", "mitigate", "transfer", "reject"]
    comment: str = Field(min_length=10)


class RiskDecisionCreate(BaseModel):
    decision: Literal["accept", "mitigate", "transfer", "avoid"]
    rationale: str = Field(min_length=20)
    decision_package_id: int
    version: int


class RiskDecisionOut(BaseModel):
    id: int
    risk_item_id: int
    decision_package_id: int
    decided_by: str
    decision: str
    rationale: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PowerBITicketRow(BaseModel):
    ticket_id: int
    external_id: str
    title: str
    customer: str
    channel: str
    category: str
    priority: str
    status: str
    owner: str | None
    team: str | None
    created_at: str
    sla_due_at: str
    resolved_at: str | None
    sla_status: str
    escalated: bool
