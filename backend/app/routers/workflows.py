from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import WorkflowRule
from app.schemas import WorkflowRuleCreate, WorkflowRuleOut, WorkflowRunRequest
from app.services.workflows import run_workflows

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("", response_model=list[WorkflowRuleOut])
def list_workflows(db: Session = Depends(get_db)):
    return db.query(WorkflowRule).order_by(WorkflowRule.created_at.desc()).all()


@router.post("", response_model=WorkflowRuleOut, status_code=201)
def create_workflow(payload: WorkflowRuleCreate, db: Session = Depends(get_db)):
    workflow = WorkflowRule(**payload.model_dump())
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return workflow


@router.post("/run")
def run_workflow_automation(payload: WorkflowRunRequest, db: Session = Depends(get_db)):
    return {"executions": run_workflows(db, payload.ticket_id)}
