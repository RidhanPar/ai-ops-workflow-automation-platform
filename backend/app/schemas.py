from datetime import datetime
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


class TicketAIResponse(BaseModel):
    summary: str
    category: str
    recommended_priority: str
    recommended_team: str
    next_action: str
    confidence: float
    source: str


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
