from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db import get_db
from app import models
from app.auth import verify_password, create_access_token, user_role_names
from app.audit import audit
from app.schemas import Token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.user_id == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")
    user.last_login_at = datetime.utcnow()
    db.add(user); db.commit()
    roles = user_role_names(user)
    token = create_access_token(subject=user.user_id, roles=roles)
    audit(db, user.id, "auth.login", {"user_id": user.user_id, "roles": roles})
    return Token(access_token=token)
