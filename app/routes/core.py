import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app import models
from app.schemas import ProjectCreate, ProjectOut, ApplicationCreate, ApplicationOut, RequirementIn, RequirementOut, BundleOut, RunOut
from app.auth import require_roles
from app.audit import audit
from app.worker.tasks import explore_app, generate_bundle, execute_bundle

router = APIRouter(tags=["core"])

@router.post("/projects", response_model=ProjectOut, dependencies=[Depends(require_roles(models.RoleName.validation_tester.value, models.RoleName.validation_lead.value, models.RoleName.qa.value, models.RoleName.admin.value))])
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), me=Depends(require_roles(models.RoleName.validation_tester.value, models.RoleName.validation_lead.value, models.RoleName.qa.value, models.RoleName.admin.value))):
    p = models.Project(name=payload.name, description=payload.description)
    db.add(p); db.commit(); db.refresh(p)
    audit(db, me.id, "project.created", {"project_id": p.id, "name": p.name})
    return ProjectOut(id=p.id, name=p.name, description=p.description)

@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), me=Depends(require_roles(models.RoleName.validation_tester.value, models.RoleName.validation_lead.value, models.RoleName.qa.value, models.RoleName.admin.value))):
    rows = db.query(models.Project).all()
    return [ProjectOut(id=r.id, name=r.name, description=r.description) for r in rows]

@router.post("/applications", response_model=ApplicationOut, dependencies=[Depends(require_roles(models.RoleName.validation_lead.value, models.RoleName.admin.value))])
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db), me=Depends(require_roles(models.RoleName.validation_lead.value, models.RoleName.admin.value))):
    a = models.Application(project_id=payload.project_id, name=payload.name, base_url=payload.base_url, environment=payload.environment)
    db.add(a); db.commit(); db.refresh(a)
    audit(db, me.id, "application.created", {"application_id": a.id, "base_url": a.base_url})
    return ApplicationOut(id=a.id, project_id=a.project_id, name=a.name, base_url=a.base_url, environment=a.environment)

@router.get("/applications", response_model=list[ApplicationOut])
def list_applications(db: Session = Depends(get_db), me=Depends(require_roles(models.RoleName.validation_tester.value, models.RoleName.validation_lead.value, models.RoleName.qa.value, models.RoleName.admin.value))):
    rows = db.query(models.Application).all()
    return [ApplicationOut(id=r.id, project_id=r.project_id, name=r.name, base_url=r.base_url, environment=r.environment) for r in rows]

@router.post("/projects/{project_id}/requirements", response_model=RequirementOut, dependencies=[Depends(require_roles(models.RoleName.validation_tester.value, models.RoleName.validation_lead.value, models.RoleName.admin.value))])
def add_requirement(project_id: int, payload: RequirementIn, db: Session = Depends(get_db), me=Depends(require_roles(models.RoleName.validation_tester.value, models.RoleName.validation_lead.value, models.RoleName.admin.value))):
    r = models.Requirement(project_id=project_id, req_id=payload.req_id, text=payload.text, priority=payload.priority, risk=payload.risk, source=payload.source)
    db.add(r); db.commit(); db.refresh(r)
    audit(db, me.id, "requirement.added", {"project_id": project_id, "req_id": payload.req_id})
    return RequirementOut(id=r.id, project_id=r.project_id, req_id=r.req_id, text=r.text, priority=r.priority, risk=r.risk, source=r.source, version=r.version, status=r.status)

@router.get("/projects/{project_id}/requirements", response_model=list[RequirementOut])
def list_requirements(project_id: int, db: Session = Depends(get_db), me=Depends(require_roles(models.RoleName.validation_tester.value, models.RoleName.validation_lead.value, models.RoleName.qa.value, models.RoleName.admin.value))):
    rows = db.query(models.Requirement).filter(models.Requirement.project_id == project_id).all()
    return [RequirementOut(id=r.id, project_id=r.project_id, req_id=r.req_id, text=r.text, priority=r.priority, risk=r.risk, source=r.source, version=r.version, status=r.status) for r in rows]

@router.post("/applications/{application_id}/explore")
def start_explore(application_id: int, db: Session = Depends(get_db), me=Depends(require_roles(models.RoleName.validation_tester.value, models.RoleName.validation_lead.value, models.RoleName.admin.value))):
    job = explore_app.delay(application_id=application_id, actor_user_id=me.id)
    return {"job_id": job.id, "state": job.state}

@router.post("/projects/{project_id}/bundles/generate", response_model=BundleOut)
def start_generate(project_id: int, application_id: int, db: Session = Depends(get_db), me=Depends(require_roles(models.RoleName.validation_tester.value, models.RoleName.validation_lead.value, models.RoleName.admin.value))):
    job = generate_bundle.delay(project_id=project_id, application_id=application_id, actor_user_id=me.id)
    return {"id": -1, "project_id": project_id, "version_hash": job.id, "status": "JOB_SUBMITTED"}

@router.get("/bundles", response_model=list[BundleOut])
def list_bundles(db: Session = Depends(get_db), me=Depends(require_roles(models.RoleName.validation_tester.value, models.RoleName.validation_lead.value, models.RoleName.qa.value, models.RoleName.admin.value))):
    rows = db.query(models.TestBundle).order_by(models.TestBundle.created_at.desc()).all()
    return [BundleOut(id=b.id, project_id=b.project_id, version_hash=b.version_hash, status=b.status.value) for b in rows]

@router.post("/bundles/{bundle_id}/approve")
def approve_bundle(bundle_id: int, reason: str | None = None, db: Session = Depends(get_db), me=Depends(require_roles(models.RoleName.validation_lead.value, models.RoleName.qa.value, models.RoleName.admin.value))):
    b = db.query(models.TestBundle).get(bundle_id)
    if not b:
        raise HTTPException(404, "bundle not found")
    if b.created_by == me.id:
        raise HTTPException(403, "cannot approve your own work")
    b.status = models.TestBundleStatus.approved
    db.add(b); db.commit()
    import hashlib
    sig = hashlib.sha256(f"{me.user_id}|approve|bundle|{bundle_id}|{reason or ''}".encode()).hexdigest()
    ap = models.Approval(object_type="bundle", object_id=bundle_id, action="approve", status=models.ApprovalStatus.approved, signed_by=me.id, reason=reason, signature_hash=sig)
    db.add(ap); db.commit()
    audit(db, me.id, "bundle.approved", {"bundle_id": bundle_id, "reason": reason})
    return {"bundle_id": bundle_id, "status": b.status.value}

@router.post("/bundles/{bundle_id}/run", response_model=RunOut)
def run_bundle(bundle_id: int, db: Session = Depends(get_db), me=Depends(require_roles(models.RoleName.validation_tester.value, models.RoleName.validation_lead.value, models.RoleName.admin.value))):
    job = execute_bundle.delay(bundle_id=bundle_id, actor_user_id=me.id)
    return RunOut(id=-1, bundle_id=bundle_id, status=f"JOB_SUBMITTED:{job.id}")

@router.get("/runs", response_model=list[RunOut])
def list_runs(db: Session = Depends(get_db), me=Depends(require_roles(models.RoleName.validation_tester.value, models.RoleName.validation_lead.value, models.RoleName.qa.value, models.RoleName.admin.value))):
    rows = db.query(models.Run).order_by(models.Run.started_at.desc()).all()
    return [RunOut(id=r.id, bundle_id=r.bundle_id, status=r.status.value) for r in rows]
