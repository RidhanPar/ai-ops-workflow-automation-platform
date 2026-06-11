import contextvars
import time
import uuid
from contextlib import contextmanager

from opentelemetry import trace
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models import TraceSpan

trace_id_context: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
tracer = trace.get_tracer("ai-ops-workflow-platform")


def current_trace_id() -> str:
    return trace_id_context.get() or str(uuid.uuid4())


@contextmanager
def traced_span(db: Session, name: str, span_type: str, metadata: dict | None = None):
    trace_id = current_trace_id()
    started = time.perf_counter()
    status = "success"
    error_type = None
    try:
        with tracer.start_as_current_span(name) as span:
            span.set_attribute("aiops.trace_id", trace_id)
            span.set_attribute("aiops.span_type", span_type)
            for key, value in (metadata or {}).items():
                if isinstance(value, (str, int, float, bool)):
                    span.set_attribute(f"aiops.{key}", value)
            yield trace_id
    except Exception as exc:
        status = "error"
        error_type = type(exc).__name__
        raise
    finally:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        db.add(
            TraceSpan(
                trace_id=trace_id,
                name=name,
                span_type=span_type,
                status=status,
                latency_ms=latency_ms,
                error_type=error_type,
                metadata_json=metadata or {},
            )
        )
        logger.info(
            "trace_span",
            trace_id=trace_id,
            name=name,
            span_type=span_type,
            status=status,
            latency_ms=latency_ms,
            error_type=error_type,
        )
        db.flush()
