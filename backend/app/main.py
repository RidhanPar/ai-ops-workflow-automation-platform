import time
import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.observability import trace_id_context
from app.core.telemetry import configure_telemetry
from app.routers import agents, ai, auth, governance, kpis, reports, tickets, workflows

settings = get_settings()
configure_logging()
logger = structlog.get_logger()

app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    description="Traceable AI-agent and workflow automation platform with human approval controls.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
configure_telemetry(app)

# Expose /metrics for Prometheus scraping. Excluded handlers are not counted
# in http_requests_total to avoid inflating request rate with scrape traffic.
Instrumentator(
    should_group_status_codes=True,
    excluded_handlers=["/metrics", "/health"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.middleware("http")
async def trace_requests(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    token = trace_id_context.set(trace_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        logger.info(
            "http_request",
            trace_id=trace_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return response
    finally:
        trace_id_context.reset(token)


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name, "environment": settings.app_env}


app.include_router(tickets.router)
app.include_router(agents.router)
app.include_router(ai.router)
app.include_router(auth.router)
app.include_router(governance.router)
app.include_router(kpis.router)
app.include_router(workflows.router)
app.include_router(reports.router)
