from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class TicketStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    waiting_customer = "waiting_customer"
    escalated = "escalated"
    resolved = "resolved"


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    team: Mapped[str] = mapped_column(String(120), nullable=False)
    skill: Mapped[str] = mapped_column(String(120), nullable=False)
    active_tickets: Mapped[int] = mapped_column(Integer, default=0)
    avg_resolution_hours: Mapped[float] = mapped_column(Float, default=0.0)
    productivity_score: Mapped[float] = mapped_column(Float, default=0.0)

    tickets = relationship("Ticket", back_populates="owner")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_id: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    customer: Mapped[str] = mapped_column(String(120), nullable=False)
    channel: Mapped[str] = mapped_column(String(60), default="email")
    category: Mapped[str] = mapped_column(String(120), default="general")
    status: Mapped[str] = mapped_column(String(50), default=TicketStatus.open.value)
    priority: Mapped[str] = mapped_column(String(50), default=Priority.medium.value)
    sla_due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_next_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    owner = relationship("Agent", back_populates="tickets")


class WorkflowRule(Base):
    __tablename__ = "workflow_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    trigger: Mapped[dict] = mapped_column(JSON, nullable=False)
    actions: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_id: Mapped[int | None] = mapped_column(ForeignKey("workflow_rules.id"), nullable=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="success")
    actions_taken: Mapped[list] = mapped_column(JSON, nullable=False)
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[str] = mapped_column(String(120), default="operations")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(40), default="viewer")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    embedding: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    actor: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(80), nullable=False)
    before_json: Mapped[dict] = mapped_column(JSON, default=dict)
    after_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_changes: Mapped[dict] = mapped_column(JSON, default=dict)
    reviewed_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TraceSpan(Base):
    __tablename__ = "trace_spans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    span_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0)
    error_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
