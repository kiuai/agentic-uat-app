from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app import models
from app.schemas import UserCreate, UserOut
from app.auth import hash_password, require_roles, user_role_names
from app.audit import audit

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/users", response_model=UserOut, dependencies=[Depends(require_roles(models.RoleName.admin.value))])
def create_user(payload: UserCreate, db: Session = Depends(get_db), me=Depends(require_roles(models.RoleName.admin.value))):
    if db.query(models.User).filter(models.User.user_id == payload.user_id).first():
        raise HTTPException(status_code=400, detail="user_id already exists")
    user = models.User(user_id=payload.user_id, email=payload.email, password_hash=hash_password(payload.password))
    db.add(user); db.commit(); db.refresh(user)

    # Ensure roles exist
    roles = []
    for rname in payload.roles:
        role = db.query(models.Role).filter(models.Role.name == models.RoleName(rname)).first()
        if not role:
            raise HTTPException(status_code=400, detail=f"Unknown role: {rname}")
        db.add(models.UserRole(user_id=user.id, role_id=role.id))
        roles.append(rname)
    db.commit()
    audit(db, me.id, "admin.user_created", {"new_user_id": user.user_id, "roles": roles})
    return UserOut(id=user.id, user_id=user.user_id, email=user.email, roles=roles)

@router.get("/users", response_model=list[UserOut], dependencies=[Depends(require_roles(models.RoleName.admin.value))])
def list_users(db: Session = Depends(get_db)):
    out = []
    users = db.query(models.User).all()
    for u in users:
        out.append(UserOut(id=u.id, user_id=u.user_id, email=u.email, roles=user_role_names(u)))
    return out
