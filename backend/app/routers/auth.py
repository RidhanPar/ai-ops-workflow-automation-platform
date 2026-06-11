from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_current_user, verify_password
from app.db import get_db
from app.models import User
from app.schemas import Token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username, User.active.is_(True)).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    return Token(access_token=create_access_token(user.username, user.role), role=user.role)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"username": user.username, "role": user.role}
