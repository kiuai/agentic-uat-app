from fastapi import APIRouter, Depends
from celery.result import AsyncResult
from app.worker.celery_app import celery_app
from app.auth import require_roles
from app import models

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.get("/{job_id}", dependencies=[Depends(require_roles(
    models.RoleName.validation_tester.value,
    models.RoleName.validation_lead.value,
    models.RoleName.qa.value,
    models.RoleName.admin.value,
))])
def job_status(job_id: str):
    res = AsyncResult(job_id, app=celery_app)
    payload = {"id": job_id, "state": res.state}
    if res.successful():
        payload["result"] = res.result
    elif res.failed():
        payload["error"] = str(res.result)
    return payload
