"""
Structured logging for AI assistant calls.

Standalone module -- no imports from app.*. Safe to use in CLI scripts,
evaluation runners, and unit tests without loading the full FastAPI stack.

Every function writes a single JSON log line to stdout via Python's logging
module at level INFO. Pipe to a log aggregator (Datadog, Loki, CloudWatch)
or grep locally.
"""

from __future__ import annotations

import json
import logging
import uuid

_logger = logging.getLogger("aiops.observability")

if not _logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


def generate_trace_id() -> str:
    """Return a new UUID4 string to use as the trace ID for one request."""
    return str(uuid.uuid4())


def log_ai_call(
    *,
    ticket_id: int,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: float,
    model_name: str,
    response_summary: str,
    trace_id: str = "",
    error: str | None = None,
) -> None:
    """Log one AI assistant invocation as a JSON line to stdout."""
    record = {
        "event": "ai_call",
        "trace_id": trace_id or generate_trace_id(),
        "ticket_id": ticket_id,
        "model": model_name,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "latency_ms": round(latency_ms, 2),
        "response_summary": response_summary[:100],
        "error": error,
        "status": "error" if error else "success",
    }
    _logger.info(json.dumps(record))


def log_fallback_used(
    *,
    ticket_id: int,
    reason: str,
    trace_id: str = "",
) -> None:
    """Log when the rules-based fallback is used instead of the AI model."""
    record = {
        "event": "fallback_used",
        "trace_id": trace_id or generate_trace_id(),
        "ticket_id": ticket_id,
        "reason": reason,
        "status": "fallback",
    }
    _logger.info(json.dumps(record))
