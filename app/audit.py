import json
from datetime import datetime
from sqlalchemy.orm import Session
from app import models

def audit(db: Session, actor_user_id: int | None, action: str, payload: dict):
    row = models.AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        payload_json=json.dumps(payload, ensure_ascii=False),
        ts=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
