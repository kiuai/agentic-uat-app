from datetime import datetime, timedelta
from typing import List
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.settings import settings
from app.db import get_db
from app import models

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def hash_password(pw: str) -> str:
    return pwd_context.hash(pw)

def create_access_token(subject: str, roles: List[str]) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "roles": roles, "exp": expire}
    return jwt.encode(payload, settings.app_secret_key, algorithm="HS256")

def decode_token(token: str):
    try:
        return jwt.decode(token, settings.app_secret_key, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> models.User:
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")
    return user

def user_role_names(user: models.User) -> List[str]:
    return [ur.role.name.value for ur in user.roles]

def require_roles(*allowed: str):
    def dep(user: models.User = Depends(get_current_user)):
        roles = set(user_role_names(user))
        if not roles.intersection(set(allowed)):
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user
    return dep
