from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db import get_db
from app.models import Agent, User
from app.schemas import AgentOut

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentOut])
def list_agents(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Agent).order_by(Agent.team, Agent.name).all()
