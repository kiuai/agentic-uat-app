from sqlalchemy.orm import Session
from app import models
from app.auth import hash_password
from app.audit import audit

def ensure_roles(db: Session):
    for rn in models.RoleName:
        existing = db.query(models.Role).filter(models.Role.name == rn).first()
        if not existing:
            db.add(models.Role(name=rn))
    db.commit()

def ensure_admin(db: Session):
    admin_user = db.query(models.User).filter(models.User.user_id == "admin").first()
    if admin_user:
        return
    u = models.User(user_id="admin", email=None, password_hash=hash_password("Admin123!"), is_active=True)
    db.add(u); db.commit(); db.refresh(u)
    role_admin = db.query(models.Role).filter(models.Role.name == models.RoleName.admin).first()
    db.add(models.UserRole(user_id=u.id, role_id=role_admin.id))
    db.commit()
    audit(db, u.id, "seed.admin_created", {"user_id":"admin"})
