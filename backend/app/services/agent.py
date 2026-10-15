from __future__ import annotations

import time
from typing import TypedDict

from langgraph.graph import END, StateGraph
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import logger
from app.core.metrics import (
    agentic_requests_total,
    human_approval_gates_triggered_total,
    llm_call_latency_seconds,
    llm_tokens_used_total,
)
from app.core.observability import current_trace_id, traced_span
from app.models import ApprovalRequest, Ticket, TraceSpan
from app.schemas import TicketAnalysis
from app.services.audit import record_audit
from app.services.knowledge import search_knowledge_base
from app.services.llm_provider import LLMProviderError, get_llm_provider

settings = get_settings()


class AgentState(TypedDict, total=False):
    ticket: Ticket
    context: dict
    tools_used: list[str]
    knowledge_sources: list[str]
    analysis: dict
    safety_flags: list[str]
    allow_write_tools: bool


def _fallback_analysis(title: str, description: str, channel: str = "email") -> TicketAnalysis:
    text = f"{title} {description}".lower()
    priority, category, team = "medium", "general", "General Support"
    if any(word in text for word in ["payment", "invoice", "refund", "charge", "billing"]):
        category, team = "billing", "Billing Ops"
    if any(word in text for word in ["login", "bug", "error", "api", "system", "failed", "outage"]):
        category, team = "technical", "Technical Support"
    if any(word in text for word in ["policy", "appeal", "blocked", "restricted", "compliance"]):
        category, team = "policy", "Policy Ops"
    if any(word in text for word in ["urgent", "critical", "blocked", "outage", "cannot work"]):
        priority, team = "critical", "Escalations Desk"
    elif any(word in text for word in ["sla", "delay", "waiting", "escalate"]):
        priority = "high"
    return TicketAnalysis(
        summary=f"Ticket about a {category} issue raised via {channel}.",
        category=category,
        recommended_priority=priority,
        recommended_team=team,
        next_action="Validate context, review relevant guidance, assign an owner, and update the customer.",
        confidence=0.72,
    )


def _prompt_injection_flags(value: str) -> list[str]:
    indicators = ["ignore previous", "system prompt", "reveal secret", "developer message", "bypass"]
    return [f"prompt_injection:{indicator}" for indicator in indicators if indicator in value.lower()]


def get_customer_history(db: Session, customer: str, exclude_ticket_id: int) -> list[dict]:
    tickets = (
        db.query(Ticket)
        .filter(Ticket.customer == customer, Ticket.id != exclude_ticket_id)
        .order_by(Ticket.created_at.desc())
        .limit(5)
        .all()
    )
    return [
        {"external_id": item.external_id, "category": item.category, "priority": item.priority, "status": item.status}
        for item in tickets
    ]


def request_ticket_update(db: Session, ticket: Ticket, analysis: TicketAnalysis, requested_by: str) -> ApprovalRequest:
    request = ApprovalRequest(
        ticket_id=ticket.id,
        action_type="agent_update_ticket",
        requested_by=requested_by,
        reason=f"Set priority={analysis.recommended_priority}, category={analysis.category}",
        proposed_changes={
            "priority": analysis.recommended_priority,
            "category": analysis.category,
            "ai_summary": analysis.summary,
            "ai_next_action": analysis.next_action,
        },
    )
    ticket.approval_required = True
    db.add(request)
    record_audit(db, requested_by, "approval.requested", "ticket", ticket.id, after={"approval_id": request.id})
    human_approval_gates_triggered_total.labels(action_type="agent_update_ticket").inc()
    return request


def _gather_context(db: Session, state: AgentState) -> AgentState:
    ticket = state["ticket"]
    documents = search_knowledge_base(db, f"{ticket.title} {ticket.description}", limit=3)
    history = get_customer_history(db, ticket.customer, ticket.id)
    state["context"] = {"knowledge": documents, "customer_history": history}
    state["tools_used"] = ["search_knowledge_base", "get_customer_history"]
    state["knowledge_sources"] = [item["title"] for item in documents]
    state["safety_flags"] = _prompt_injection_flags(f"{ticket.title} {ticket.description}")
    return state


def _reason(state: AgentState) -> AgentState:
    ticket = state["ticket"]
    prompt = {
        "ticket": {
            "title": ticket.title,
            "description": ticket.description,
            "customer": ticket.customer,
            "channel": ticket.channel,
        },
        "retrieved_context": state["context"],
        "safety_flags": state["safety_flags"],
    }
    state["analysis"] = {"prompt": prompt}
    return state


def run_ticket_agent(db: Session, ticket: Ticket, actor: str, allow_write_tools: bool = False) -> dict:
    trace_id = current_trace_id()
    started = time.perf_counter()
    graph = StateGraph(AgentState)
    graph.add_node("gather_context", lambda state: _gather_context(db, state))
    graph.add_node("reason", _reason)
    graph.set_entry_point("gather_context")
    graph.add_edge("gather_context", "reason")
    graph.add_edge("reason", END)

    with traced_span(db, "ticket_agent", "agent", {"ticket_id": ticket.id}):
        state = graph.compile().invoke({"ticket": ticket, "allow_write_tools": allow_write_tools})
        provider = get_llm_provider(settings)
        input_cost_per_1m = provider.input_cost_per_1m if provider else 0.0
        output_cost_per_1m = provider.output_cost_per_1m if provider else 0.0
        source, usage = "local_fallback_rules", {"input_tokens": 0, "output_tokens": 0}
        llm_started = time.perf_counter()
        try:
            if provider is not None:
                llm_result = provider.complete(state["analysis"]["prompt"])
                analysis = TicketAnalysis.model_validate_json(llm_result.text)
                usage = {
                    "input_tokens": llm_result.input_tokens,
                    "output_tokens": llm_result.output_tokens,
                }
                source = provider.source_label
            else:
                analysis = _fallback_analysis(ticket.title, ticket.description, ticket.channel)
                if ticket.priority == "critical":
                    analysis.recommended_priority = "critical"
        except ValidationError as exc:
            logger.warning("llm_invalid_output", trace_id=trace_id, error_type=type(exc).__name__)
            analysis, source = (
                _fallback_analysis(ticket.title, ticket.description, ticket.channel),
                "fallback_invalid_output",
            )
        except LLMProviderError as exc:
            logger.warning("llm_provider_failure", trace_id=trace_id, error_type=type(exc).__name__)
            analysis, source = (
                _fallback_analysis(ticket.title, ticket.description, ticket.channel),
                "fallback_provider_failure",
            )
        except Exception as exc:
            logger.exception("llm_unexpected_failure", trace_id=trace_id, error_type=type(exc).__name__)
            analysis, source = (
                _fallback_analysis(ticket.title, ticket.description, ticket.channel),
                "fallback_unexpected_failure",
            )
        finally:
            llm_call_latency_seconds.labels(source=source).observe(time.perf_counter() - llm_started)

        agentic_requests_total.labels(source=source).inc()
        llm_tokens_used_total.labels(direction="input").inc(usage["input_tokens"])
        llm_tokens_used_total.labels(direction="output").inc(usage["output_tokens"])

        ticket.ai_summary = analysis.summary
        ticket.ai_next_action = analysis.next_action
        if allow_write_tools:
            request_ticket_update(db, ticket, analysis, actor)
            state["tools_used"].append("update_ticket_approval_request")

        cost = (
            usage["input_tokens"] * input_cost_per_1m
            + usage["output_tokens"] * output_cost_per_1m
        ) / 1_000_000
        db.add(
            TraceSpan(
                trace_id=trace_id,
                name="llm_analysis",
                span_type="llm",
                status="success",
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                estimated_cost_usd=cost,
                metadata_json={"source": source, "tools_used": state["tools_used"]},
            )
        )
        result = {
            **analysis.model_dump(),
            "source": source,
            "trace_id": trace_id,
            "tools_used": state["tools_used"],
            "knowledge_sources": state["knowledge_sources"],
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "estimated_cost_usd": round(cost, 8),
            "safety_flags": state["safety_flags"],
        }
    db.commit()
    return result
