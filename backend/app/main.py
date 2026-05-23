from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.db import Base, SessionLocal, engine
from app.routers import agents, ai, kpis, reports, tickets, workflows
from app.seed import seed_demo_data

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="AI operations platform for SLA monitoring, ticket workflow automation, and operational analytics.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_demo_data(db)
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name, "environment": settings.app_env}


app.include_router(tickets.router)
app.include_router(agents.router)
app.include_router(ai.router)
app.include_router(kpis.router)
app.include_router(workflows.router)
app.include_router(reports.router)
