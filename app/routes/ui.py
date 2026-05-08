from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from starlette.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import datetime, timedelta
import json

from app.db import get_db
from sqlalchemy import text
import redis as redis_lib
from app import models
from app.auth import verify_password, create_access_token, decode_token, user_role_names, hash_password
from app.settings import settings
from app.worker.tasks import explore_app, generate_bundle, execute_bundle
from app.llm.provider import generate_tests
from celery.result import AsyncResult
from app.worker.celery_app import celery_app
from app.rtm import build_rtm_xlsx
from app.reporting import build_run_report_html, build_run_report_pdf
from app.audit import audit

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/ui", tags=["ui"])

def _session_token(request: Request) -> str | None:
    return request.session.get("token")

def _require_login(request: Request):
    tok = _session_token(request)
    if not tok:
        return None
    try:
        payload = decode_token(tok)
        return payload
    except Exception:
        return None

def _current_user(request: Request, db: Session):
    payload = _require_login(request)
    if not payload:
        return None, []
    user_id = payload.get("sub")
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user or not user.is_active:
        return None, []
    return user, user_role_names(user)

def _require_roles(roles: list[str], allowed: list[str]) -> bool:
    return bool(set(roles).intersection(set(allowed)))

def _active_admin_count(db: Session) -> int:
    return (
        db.query(models.User)
        .join(models.UserRole, models.UserRole.user_id == models.User.id)
        .join(models.Role, models.Role.id == models.UserRole.role_id)
        .filter(models.Role.name == models.RoleName.admin, models.User.is_active == True)
        .count()
    )

def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@router.post("/login")
def login(request: Request, db: Session = Depends(get_db), user_id: str = Form(...), password: str = Form(...)):
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"}, status_code=401)

    roles = user_role_names(user)
    token = create_access_token(subject=user.user_id, roles=roles)
    request.session["token"] = token
    audit(db, user.id, "ui.login", {"user_id": user.user_id, "roles": roles})
    return RedirectResponse("/ui", status_code=303)

@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/ui/login", status_code=303)

@router.get("", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)

    projects = db.query(models.Project).order_by(models.Project.id.desc()).all()
    apps = db.query(models.Application).order_by(models.Application.id.desc()).all()
    bundles = db.query(models.TestBundle).order_by(models.TestBundle.created_at.desc()).limit(10).all()
    runs = db.query(models.Run).order_by(models.Run.started_at.desc()).limit(10).all()

    db_ok = True
    redis_ok = True
    worker_ok = "unknown"
    try:
        db.execute(text("select 1"))
    except Exception:
        db_ok = False
    try:
        r = redis_lib.from_url(settings.redis_url)
        r.ping()
    except Exception:
        redis_ok = False
    try:
        insp = celery_app.control.inspect(timeout=1)
        pings = insp.ping() if insp else None
        worker_ok = "online" if pings else "offline"
    except Exception:
        worker_ok = "unknown"

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "roles": roles,
        "projects": projects,
        "apps": apps,
        "bundles": bundles,
        "runs": runs,
        "status": {
            "db": "online" if db_ok else "offline",
            "redis": "online" if redis_ok else "offline",
            "worker": worker_ok,
        },
    })


@router.get("/settings/llm", response_class=HTMLResponse)
def llm_settings_page(request: Request, project_id: int | None = None, db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    if not _require_roles(roles, [models.RoleName.validation_lead.value, models.RoleName.qa.value, models.RoleName.admin.value]):
        return RedirectResponse("/ui?e=forbidden", status_code=303)

    projects = db.query(models.Project).order_by(models.Project.name.asc()).all()
    selected = project_id or (projects[0].id if projects else None)
    current = None
    if selected:
        current = db.query(models.LLMSettings).filter(models.LLMSettings.project_id == selected).order_by(models.LLMSettings.updated_at.desc()).first()

    return templates.TemplateResponse("llm_settings.html", {
        "request": request,
        "user": user,
        "roles": roles,
        "projects": projects,
        "selected_project_id": selected,
        "current": current,
        "azure_endpoint": settings.azure_openai_endpoint,
        "azure_api_key": settings.azure_openai_api_key,
        "azure_api_version": settings.azure_openai_api_version,
        "azure_deployment": settings.azure_openai_deployment,
    })

@router.post("/settings/llm")
def llm_settings_save(request: Request,
                      project_id: int = Form(...),
                      provider: str = Form("stub"),
                      model: str = Form("gpt-5"),
                      temperature: float = Form(0.2),
                      max_output_tokens: int = Form(2500),
                      strict_json: str = Form("on"),
                      azure_endpoint: str = Form(""),
                      azure_deployment: str = Form(""),
                      azure_api_version: str = Form(""),
                      azure_api_key: str = Form(""),
                      db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    if not _require_roles(roles, [models.RoleName.validation_lead.value, models.RoleName.qa.value, models.RoleName.admin.value]):
        return RedirectResponse("/ui?e=forbidden", status_code=303)

    row = models.LLMSettings(
        project_id=project_id,
        provider=provider,
        model=model,
        temperature=float(temperature),
        max_output_tokens=int(max_output_tokens),
        strict_json=(strict_json == "on"),
        updated_at=datetime.utcnow(),
    )
    db.add(row); db.commit()

    # Update .env for Azure settings (requires restart to take effect)
    if provider == "azure":
        env_path = Path(".env")
        if env_path.exists():
            env_lines = env_path.read_text().splitlines()

            def upsert(key: str, value: str):
                nonlocal env_lines
                found = False
                for i, line in enumerate(env_lines):
                    if line.startswith(f"{key}="):
                        env_lines[i] = f"{key}={value}"
                        found = True
                        break
                if not found:
                    env_lines.append(f"{key}={value}")

            if azure_endpoint:
                upsert("AZURE_OPENAI_ENDPOINT", azure_endpoint.strip())
            if azure_api_key:
                upsert("AZURE_OPENAI_API_KEY", azure_api_key.strip())
            if azure_api_version:
                upsert("AZURE_OPENAI_API_VERSION", azure_api_version.strip())
            if azure_deployment:
                upsert("AZURE_OPENAI_DEPLOYMENT", azure_deployment.strip())
            env_path.write_text("\n".join(env_lines) + "\n")

    audit(db, user.id, "ui.llm_settings.save", {"project_id": project_id, "provider": provider, "model": model})
    return RedirectResponse(f"/ui/settings/llm?project_id={project_id}", status_code=303)

@router.get("/projects", response_class=HTMLResponse)
def projects_page(request: Request, db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    projects = db.query(models.Project).order_by(models.Project.id.desc()).all()
    return templates.TemplateResponse("projects.html", {"request": request, "user": user, "roles": roles, "projects": projects})

@router.post("/projects")
def create_project(request: Request, name: str = Form(...), description: str = Form(""), db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    if not _require_roles(roles, [models.RoleName.validation_tester.value, models.RoleName.validation_lead.value, models.RoleName.qa.value, models.RoleName.admin.value]):
        return RedirectResponse("/ui?e=forbidden", status_code=303)

    p = models.Project(name=name, description=description or None)
    db.add(p); db.commit()
    audit(db, user.id, "ui.project.create", {"name": name})
    return RedirectResponse("/ui/projects", status_code=303)

@router.get("/applications", response_class=HTMLResponse)
def apps_page(request: Request, db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)

    projects = db.query(models.Project).order_by(models.Project.name.asc()).all()
    apps = db.query(models.Application).order_by(models.Application.id.desc()).all()
    return templates.TemplateResponse("applications.html", {"request": request, "user": user, "roles": roles, "projects": projects, "apps": apps})

@router.post("/applications")
def create_app(request: Request, project_id: int = Form(...), name: str = Form(...), base_url: str = Form(...), environment: str = Form("non-prod"), db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    if not _require_roles(roles, [models.RoleName.validation_lead.value, models.RoleName.admin.value]):
        return RedirectResponse("/ui?e=forbidden", status_code=303)

    a = models.Application(project_id=project_id, name=name, base_url=base_url, environment=environment)
    db.add(a); db.commit()
    audit(db, user.id, "ui.application.create", {"application_id": a.id, "base_url": base_url})
    return RedirectResponse("/ui/applications", status_code=303)

@router.post("/applications/{application_id}/explore")
def ui_start_explore(request: Request, application_id: int, db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    if not _require_roles(roles, [models.RoleName.validation_tester.value, models.RoleName.validation_lead.value, models.RoleName.admin.value]):
        return RedirectResponse("/ui?e=forbidden", status_code=303)

    job = explore_app.delay(application_id=application_id, actor_user_id=user.id, max_pages=50)
    audit(db, user.id, "ui.explore.submit", {"job_id": job.id, "application_id": application_id})
    return RedirectResponse(f"/ui/jobs/{job.id}", status_code=303)


@router.get("/requirements/{project_id}", response_class=HTMLResponse)
def reqs_page(request: Request, project_id: int, db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    project = db.query(models.Project).get(project_id)
    reqs = db.query(models.Requirement).filter(models.Requirement.project_id == project_id).order_by(models.Requirement.id.desc()).all()
    return templates.TemplateResponse("requirements.html", {"request": request, "user": user, "roles": roles, "project": project, "reqs": reqs})

@router.post("/requirements/{project_id}")
def add_req(request: Request, project_id: int, req_id: str = Form(...), text: str = Form(...), priority: str = Form(""), risk: str = Form(""), source: str = Form(""), db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    if not _require_roles(roles, [models.RoleName.validation_tester.value, models.RoleName.validation_lead.value, models.RoleName.admin.value]):
        return RedirectResponse("/ui?e=forbidden", status_code=303)

    r = models.Requirement(project_id=project_id, req_id=req_id, text=text, priority=priority or None, risk=risk or None, source=source or None)
    db.add(r); db.commit()
    audit(db, user.id, "ui.requirement.add", {"project_id": project_id, "req_id": req_id})
    return RedirectResponse(f"/ui/requirements/{project_id}", status_code=303)
@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_page(request: Request, job_id: str, db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    res = AsyncResult(job_id, app=celery_app)
    progress_map = {
        "PENDING": 10,
        "RECEIVED": 20,
        "STARTED": 50,
        "RETRY": 60,
        "SUCCESS": 100,
        "FAILURE": 100,
    }
    info = {"id": job_id, "state": res.state, "progress": progress_map.get(res.state, 10)}
    if isinstance(res.info, dict):
        current = res.info.get("current")
        total = res.info.get("total")
        if isinstance(current, int) and isinstance(total, int) and total > 0:
            info["progress"] = int((current / total) * 100)
        stage = res.info.get("stage")
        if stage:
            info["stage"] = stage
        meta_url = res.info.get("url")
        if meta_url:
            info["url"] = meta_url
    if res.successful():
        info["result"] = res.result
    elif res.failed():
        info["error"] = str(res.result)
    return templates.TemplateResponse("job.html", {"request": request, "user": user, "roles": roles, "job": info})

@router.get("/bundles/{bundle_id}", response_class=HTMLResponse)
def bundle_detail(request: Request, bundle_id: int, db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    b = db.query(models.TestBundle).get(bundle_id)
    if not b:
        return RedirectResponse(f"/ui/jobs/{job.id}", status_code=303)
    msg = request.query_params.get("msg")
    tests = db.query(models.TestCase).filter(models.TestCase.bundle_id == bundle_id).order_by(models.TestCase.id.asc()).all()
    steps = {}
    for t in tests:
        steps[t.id] = db.query(models.TestStep).filter(models.TestStep.test_case_id == t.id).order_by(models.TestStep.step_index.asc()).all()
    return templates.TemplateResponse("bundle_detail.html", {"request": request, "user": user, "roles": roles, "bundle": b, "tests": tests, "steps": steps, "msg": msg})

@router.get("/bundles/{bundle_id}/develop", response_class=HTMLResponse)
def develop_test_script_page(request: Request, bundle_id: int, db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    if not _require_roles(roles, [models.RoleName.validation_tester.value, models.RoleName.validation_lead.value, models.RoleName.admin.value]):
        return RedirectResponse("/ui?e=forbidden", status_code=303)

    b = db.query(models.TestBundle).get(bundle_id)
    if not b:
        return RedirectResponse("/ui/bundles", status_code=303)
    apps = db.query(models.Application).order_by(models.Application.id.desc()).all()
    llm_row = db.query(models.LLMSettings).filter(models.LLMSettings.project_id == b.project_id).order_by(models.LLMSettings.updated_at.desc()).first()
    llm_provider = (llm_row.provider if llm_row else None) or (settings.llm_provider or "stub")
    has_llm_key = bool(settings.openai_api_key) or bool(settings.azure_openai_api_key)
    msg = request.query_params.get("msg")
    error = request.query_params.get("e")
    return templates.TemplateResponse("develop_test_script.html", {
        "request": request,
        "user": user,
        "roles": roles,
        "bundle": b,
        "apps": apps,
        "llm_provider": llm_provider,
        "has_llm_key": has_llm_key,
        "msg": msg,
        "error": error,
    })

@router.post("/bundles/{bundle_id}/develop")
def develop_test_script_submit(request: Request,
                               bundle_id: int,
                               application_id: int = Form(...),
                               description: str = Form(...),
                               db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    if not _require_roles(roles, [models.RoleName.validation_tester.value, models.RoleName.validation_lead.value, models.RoleName.admin.value]):
        return RedirectResponse("/ui?e=forbidden", status_code=303)

    b = db.query(models.TestBundle).get(bundle_id)
    if not b:
        return RedirectResponse("/ui/bundles", status_code=303)
    app = db.query(models.Application).get(application_id)
    if not app:
        return RedirectResponse(f"/ui/bundles/{bundle_id}/develop?e=missing", status_code=303)

    pages = db.query(models.Page).filter(models.Page.application_id == application_id).order_by(models.Page.discovered_at.desc()).limit(50).all()
    page_dicts = [{"id": p.id, "url": p.url, "title": p.title, "dom_hash": p.dom_hash} for p in pages]

    elements = []
    if pages:
        top_page_ids = [p.id for p in pages[:5]]
        el_rows = db.query(models.Element).filter(models.Element.page_id.in_(top_page_ids)).order_by(models.Element.id.asc()).limit(300).all()
        for e in el_rows:
            elements.append({"selector": e.selector, "role": e.role, "label": e.label, "type": e.type})

    llm_row = db.query(models.LLMSettings).filter(models.LLMSettings.project_id == b.project_id).order_by(models.LLMSettings.updated_at.desc()).first()
    llm_cfg = {
        "provider": llm_row.provider if llm_row else None,
        "model": llm_row.model if llm_row else None,
        "temperature": llm_row.temperature if llm_row else None,
        "max_output_tokens": llm_row.max_output_tokens if llm_row else None,
        "strict_json": llm_row.strict_json if llm_row else None,
    }

    req_dicts = [{"req_id": "MANUAL-001", "text": description}]
    try:
        tests = generate_tests(req_dicts, app.base_url, page_dicts, elements, llm_cfg)
    except RuntimeError as exc:
        if "OPENAI_API_KEY" in str(exc) or "AZURE_OPENAI" in str(exc):
            return RedirectResponse(f"/ui/bundles/{bundle_id}/develop?e=missing_key", status_code=303)
        raise
    if not tests:
        return RedirectResponse(f"/ui/bundles/{bundle_id}/develop?e=empty", status_code=303)

    for t in tests:
        tc = models.TestCase(
            bundle_id=b.id,
            test_id=t.test_id,
            title=t.title,
            objective=t.objective,
            preconditions=json.dumps(t.preconditions),
            data_json=json.dumps(t.data),
            risk=t.risk,
            requirement_ids_json=json.dumps(t.requirement_ids),
        )
        db.add(tc); db.commit(); db.refresh(tc)

        for s in t.steps:
            selector = s.selector if hasattr(s, "selector") else s.get("selector")
            input_value = s.input if hasattr(s, "input") else s.get("input")
            expected = s.expect if hasattr(s, "expect") else s.get("expect")
            critical = s.critical if hasattr(s, "critical") else bool(s.get("critical", False))
            step = models.TestStep(
                test_case_id=tc.id,
                step_index=s.index if hasattr(s, "index") else s["index"],
                action=s.action if hasattr(s, "action") else s["action"],
                selector_json=json.dumps(selector) if selector else None,
                input=input_value,
                expected=expected,
                critical=bool(critical),
            )
            db.add(step)
        db.commit()

    audit(db, user.id, "ui.bundle.develop_test_script", {"bundle_id": b.id, "application_id": application_id})
    return RedirectResponse(f"/ui/bundles/{bundle_id}?msg=developed", status_code=303)

@router.post("/bundles/{bundle_id}/steps/{step_id}/edit")
def edit_step(request: Request, bundle_id: int, step_id: int,
              action: str = Form(...),
              selector_json: str = Form(""),
              input_value: str = Form(""),
              expected: str = Form(""),
              critical: str = Form("off"),
              db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    # Allow testers/leads/admin to edit steps; QA read-only by default
    if not _require_roles(roles, [models.RoleName.validation_tester.value, models.RoleName.validation_lead.value, models.RoleName.admin.value]):
        return RedirectResponse("/ui?e=forbidden", status_code=303)

    st = db.query(models.TestStep).get(step_id)
    if st:
        st.action = action
        st.selector_json = selector_json.strip() or None
        st.input = input_value.strip() or None
        st.expected = expected.strip() or None
        st.critical = (critical == "on")
        db.add(st); db.commit()
        audit(db, user.id, "ui.step.edit", {"bundle_id": bundle_id, "step_id": step_id})
    return RedirectResponse(f"/ui/bundles/{bundle_id}", status_code=303)

@router.get("/runs/{run_id}/rtm")
def download_rtm(request: Request, run_id: int, db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    out_path = f"/data/evidence/rtm_run{run_id}.xlsx"
    build_rtm_xlsx(db, run_id=run_id, out_path=out_path)
    return FileResponse(out_path, filename=f"rtm_run{run_id}.xlsx")

@router.get("/runs/{run_id}/report")
def download_report_pdf(request: Request, run_id: int, db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    html_path = f"/data/evidence/report_run{run_id}.html"
    pdf_path = f"/data/evidence/report_run{run_id}.pdf"
    build_run_report_html(db, run_id=run_id, out_path=html_path)
    build_run_report_pdf(html_path=html_path, pdf_path=pdf_path)
    return FileResponse(pdf_path, filename=f"report_run{run_id}.pdf")

@router.get("/applications/{application_id}/explore-map", response_class=HTMLResponse)
def explore_map(request: Request, application_id: int, db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    app = db.query(models.Application).get(application_id)
    if not app:
        return RedirectResponse("/ui/applications", status_code=303)
    pages = db.query(models.Page).filter(models.Page.application_id == application_id).order_by(models.Page.discovered_at.desc()).all()
    return templates.TemplateResponse("explore_map.html", {"request": request, "user": user, "roles": roles, "app": app, "pages": pages})



@router.get("/pages/{page_id}", response_class=HTMLResponse)
def page_detail(request: Request, page_id: int, db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    pg = db.query(models.Page).get(page_id)
    if not pg:
        return RedirectResponse("/ui", status_code=303)
    els = db.query(models.Element).filter(models.Element.page_id == page_id).order_by(models.Element.id.asc()).all()
    return templates.TemplateResponse("page_detail.html", {"request": request, "user": user, "roles": roles, "page": pg, "elements": els})

@router.get("/bundles", response_class=HTMLResponse)
def bundles_page(request: Request, db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)

    error = request.query_params.get("e")
    bundles = db.query(models.TestBundle).order_by(models.TestBundle.created_at.desc()).all()
    apps = db.query(models.Application).order_by(models.Application.id.desc()).all()
    projects = db.query(models.Project).order_by(models.Project.id.desc()).all()
    return templates.TemplateResponse("bundles.html", {
        "request": request,
        "user": user,
        "roles": roles,
        "bundles": bundles,
        "apps": apps,
        "projects": projects,
        "error": error,
    })

@router.post("/bundles/generate")
def ui_generate_bundle(request: Request, project_id: int = Form(...), application_id: int = Form(...), db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    if not _require_roles(roles, [models.RoleName.validation_tester.value, models.RoleName.validation_lead.value, models.RoleName.admin.value]):
        return RedirectResponse("/ui?e=forbidden", status_code=303)

    job = generate_bundle.delay(project_id=project_id, application_id=application_id, actor_user_id=user.id)
    audit(db, user.id, "ui.bundle.generate.submit", {"job_id": job.id, "project_id": project_id, "application_id": application_id})
    return RedirectResponse(f"/ui/jobs/{job.id}", status_code=303)

@router.post("/bundles/{bundle_id}/approve")
def ui_approve_bundle(request: Request, bundle_id: int, reason: str = Form(""), db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    if not _require_roles(roles, [models.RoleName.validation_lead.value, models.RoleName.qa.value, models.RoleName.admin.value]):
        return RedirectResponse("/ui?e=forbidden", status_code=303)

    b = db.query(models.TestBundle).get(bundle_id)
    if b and b.created_by == user.id:
        return RedirectResponse("/ui/bundles?e=self_approve", status_code=303)
    if b:
        b.status = models.TestBundleStatus.approved
        db.add(b); db.commit()
    audit(db, user.id, "ui.bundle.approve", {"bundle_id": bundle_id, "reason": reason})
    return RedirectResponse("/ui/bundles", status_code=303)

@router.get("/admin/users", response_class=HTMLResponse)
def admin_users_page(request: Request,
                     audit_q: str | None = None,
                     audit_action: str | None = None,
                     audit_actor: str | None = None,
                     audit_from: str | None = None,
                     audit_to: str | None = None,
                     audit_sort: str | None = None,
                     audit_page: int = 1,
                     db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    if not _require_roles(roles, [models.RoleName.admin.value]):
        return RedirectResponse("/ui?e=forbidden", status_code=303)

    role_options = [
        {"value": models.RoleName.admin.value, "label": "Administrator"},
        {"value": models.RoleName.validation_lead.value, "label": "Validation Lead"},
        {"value": models.RoleName.qa.value, "label": "QA"},
        {"value": models.RoleName.validation_tester.value, "label": "Validation User"},
    ]
    users = db.query(models.User).order_by(models.User.user_id.asc()).all()
    user_rows = []
    for u in users:
        user_rows.append({
            "id": u.id,
            "user_id": u.user_id,
            "email": u.email,
            "roles": user_role_names(u),
            "active": u.is_active,
        })
    page_size = 25
    page = max(1, audit_page or 1)
    audit_query = db.query(models.AuditLog)
    if audit_action:
        audit_query = audit_query.filter(models.AuditLog.action.ilike(f"%{audit_action}%"))
    if audit_q:
        audit_query = audit_query.filter(
            (models.AuditLog.action.ilike(f"%{audit_q}%")) |
            (models.AuditLog.payload_json.ilike(f"%{audit_q}%"))
        )
    if audit_actor:
        if audit_actor.lower() == "system":
            audit_query = audit_query.filter(models.AuditLog.actor_user_id.is_(None))
        else:
            actor_user = db.query(models.User).filter(models.User.user_id == audit_actor).first()
            if actor_user:
                audit_query = audit_query.filter(models.AuditLog.actor_user_id == actor_user.id)
            else:
                audit_query = audit_query.filter(models.AuditLog.id == -1)

    from_dt = _parse_date(audit_from)
    to_dt = _parse_date(audit_to)
    if from_dt:
        audit_query = audit_query.filter(models.AuditLog.ts >= from_dt)
    if to_dt:
        audit_query = audit_query.filter(models.AuditLog.ts <= (to_dt + timedelta(days=1) - timedelta(seconds=1)))

    total = audit_query.count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    if page > total_pages:
        page = total_pages
    sort_key = (audit_sort or "newest").lower()
    if sort_key == "oldest":
        audit_query = audit_query.order_by(models.AuditLog.ts.asc())
    elif sort_key == "action_asc":
        audit_query = audit_query.order_by(models.AuditLog.action.asc(), models.AuditLog.ts.desc())
    elif sort_key == "action_desc":
        audit_query = audit_query.order_by(models.AuditLog.action.desc(), models.AuditLog.ts.desc())
    else:
        audit_query = audit_query.order_by(models.AuditLog.ts.desc())

    audit_rows = audit_query.offset((page - 1) * page_size).limit(page_size).all()

    audits = []
    for a in audit_rows:
        actor = None
        if a.actor_user_id:
            actor_user = db.query(models.User).get(a.actor_user_id)
            actor = actor_user.user_id if actor_user else None
        audits.append({
            "ts": a.ts,
            "actor": actor or "system",
            "action": a.action,
            "payload": a.payload_json,
        })
    msg = request.query_params.get("msg")
    error = request.query_params.get("e")
    return templates.TemplateResponse("admin_users.html", {
        "request": request,
        "user": user,
        "roles": roles,
        "users": user_rows,
        "role_options": role_options,
        "audits": audits,
        "audit_q": audit_q or "",
        "audit_action": audit_action or "",
        "audit_actor": audit_actor or "",
        "audit_page": page,
        "audit_total_pages": total_pages,
        "audit_from": audit_from or "",
        "audit_to": audit_to or "",
        "audit_sort": audit_sort or "newest",
        "msg": msg,
        "error": error,
    })

@router.post("/admin/users")
def admin_users_create(request: Request,
                       user_id: str = Form(...),
                       password: str = Form(...),
                       email: str = Form(""),
                       roles: list[str] = Form([]),
                       db: Session = Depends(get_db)):
    me, role_names = _current_user(request, db)
    if not me:
        return RedirectResponse("/ui/login", status_code=303)
    if not _require_roles(role_names, [models.RoleName.admin.value]):
        return RedirectResponse("/ui?e=forbidden", status_code=303)

    if db.query(models.User).filter(models.User.user_id == user_id).first():
        return RedirectResponse("/ui/admin/users?e=exists", status_code=303)
    if not roles:
        return RedirectResponse("/ui/admin/users?e=roles", status_code=303)

    user = models.User(user_id=user_id, email=email or None, password_hash=hash_password(password), is_active=True)
    db.add(user); db.commit(); db.refresh(user)

    assigned = []
    for rname in roles:
        role = db.query(models.Role).filter(models.Role.name == models.RoleName(rname)).first()
        if not role:
            return RedirectResponse("/ui/admin/users?e=roles", status_code=303)
        db.add(models.UserRole(user_id=user.id, role_id=role.id))
        assigned.append(rname)
    db.commit()
    audit(db, me.id, "ui.admin.user_created", {"new_user_id": user.user_id, "roles": assigned})
    return RedirectResponse("/ui/admin/users?msg=created", status_code=303)

@router.post("/admin/users/{target_user_id}/deactivate")
def admin_users_deactivate(request: Request, target_user_id: int, db: Session = Depends(get_db)):
    me, role_names = _current_user(request, db)
    if not me:
        return RedirectResponse("/ui/login", status_code=303)
    if not _require_roles(role_names, [models.RoleName.admin.value]):
        return RedirectResponse("/ui?e=forbidden", status_code=303)

    target = db.query(models.User).get(target_user_id)
    if not target:
        return RedirectResponse("/ui/admin/users?e=missing", status_code=303)
    if target.id == me.id:
        return RedirectResponse("/ui/admin/users?e=self", status_code=303)
    if models.RoleName.admin.value in user_role_names(target) and _active_admin_count(db) <= 1:
        return RedirectResponse("/ui/admin/users?e=last_admin", status_code=303)

    target.is_active = False
    db.add(target); db.commit()
    audit(db, me.id, "ui.admin.user_deactivated", {"target_user_id": target.user_id})
    return RedirectResponse("/ui/admin/users?msg=deactivated", status_code=303)

@router.post("/admin/users/{target_user_id}/activate")
def admin_users_activate(request: Request, target_user_id: int, db: Session = Depends(get_db)):
    me, role_names = _current_user(request, db)
    if not me:
        return RedirectResponse("/ui/login", status_code=303)
    if not _require_roles(role_names, [models.RoleName.admin.value]):
        return RedirectResponse("/ui?e=forbidden", status_code=303)

    target = db.query(models.User).get(target_user_id)
    if not target:
        return RedirectResponse("/ui/admin/users?e=missing", status_code=303)

    target.is_active = True
    db.add(target); db.commit()
    audit(db, me.id, "ui.admin.user_activated", {"target_user_id": target.user_id})
    return RedirectResponse("/ui/admin/users?msg=activated", status_code=303)

@router.post("/admin/users/{target_user_id}/reset-password")
def admin_users_reset_password(request: Request,
                               target_user_id: int,
                               new_password: str = Form(...),
                               db: Session = Depends(get_db)):
    me, role_names = _current_user(request, db)
    if not me:
        return RedirectResponse("/ui/login", status_code=303)
    if not _require_roles(role_names, [models.RoleName.admin.value]):
        return RedirectResponse("/ui?e=forbidden", status_code=303)

    target = db.query(models.User).get(target_user_id)
    if not target:
        return RedirectResponse("/ui/admin/users?e=missing", status_code=303)

    target.password_hash = hash_password(new_password)
    db.add(target); db.commit()
    audit(db, me.id, "ui.admin.user_password_reset", {"target_user_id": target.user_id})
    return RedirectResponse("/ui/admin/users?msg=password_reset", status_code=303)

@router.post("/admin/users/{target_user_id}/roles")
def admin_users_update_roles(request: Request,
                             target_user_id: int,
                             roles: list[str] = Form([]),
                             db: Session = Depends(get_db)):
    me, role_names = _current_user(request, db)
    if not me:
        return RedirectResponse("/ui/login", status_code=303)
    if not _require_roles(role_names, [models.RoleName.admin.value]):
        return RedirectResponse("/ui?e=forbidden", status_code=303)

    target = db.query(models.User).get(target_user_id)
    if not target:
        return RedirectResponse("/ui/admin/users?e=missing", status_code=303)
    if not roles:
        return RedirectResponse("/ui/admin/users?e=roles", status_code=303)

    existing_roles = user_role_names(target)
    removing_admin = models.RoleName.admin.value in existing_roles and models.RoleName.admin.value not in roles
    if removing_admin and _active_admin_count(db) <= 1:
        return RedirectResponse("/ui/admin/users?e=last_admin", status_code=303)

    db.query(models.UserRole).filter(models.UserRole.user_id == target.id).delete()
    assigned = []
    for rname in roles:
        role = db.query(models.Role).filter(models.Role.name == models.RoleName(rname)).first()
        if not role:
            return RedirectResponse("/ui/admin/users?e=roles", status_code=303)
        db.add(models.UserRole(user_id=target.id, role_id=role.id))
        assigned.append(rname)
    db.commit()
    audit(db, me.id, "ui.admin.user_roles_updated", {"target_user_id": target.user_id, "roles": assigned})
    return RedirectResponse("/ui/admin/users?msg=roles_updated", status_code=303)

@router.post("/bundles/{bundle_id}/run")
def ui_run_bundle(request: Request, bundle_id: int, db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    if not _require_roles(roles, [models.RoleName.validation_tester.value, models.RoleName.validation_lead.value, models.RoleName.admin.value]):
        return RedirectResponse("/ui?e=forbidden", status_code=303)

    job = execute_bundle.delay(bundle_id=bundle_id, actor_user_id=user.id)
    audit(db, user.id, "ui.run.submit", {"job_id": job.id, "bundle_id": bundle_id})
    return RedirectResponse(f"/ui/jobs/{job.id}", status_code=303)

@router.get("/runs", response_class=HTMLResponse)
def runs_page(request: Request, db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)

    runs = db.query(models.Run).order_by(models.Run.started_at.desc()).all()
    return templates.TemplateResponse("runs.html", {"request": request, "user": user, "roles": roles, "runs": runs})

@router.get("/runs/{run_id}/evidence", response_class=HTMLResponse)
def evidence_page(request: Request, run_id: int, db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    # evidence for a run
    results = db.query(models.Result).filter(models.Result.run_id == run_id).all()
    evs = []
    for res in results:
        ev = db.query(models.Evidence).filter(models.Evidence.result_id == res.id).first()
        if ev:
            evs.append(ev)
    return templates.TemplateResponse("evidence.html", {"request": request, "user": user, "roles": roles, "run_id": run_id, "evidence": evs})

@router.get("/evidence/file")
def evidence_file(request: Request, path: str, db: Session = Depends(get_db)):
    user, roles = _current_user(request, db)
    if not user:
        return RedirectResponse("/ui/login", status_code=303)
    # Basic authorization: any logged-in role may view evidence in MVP
    p = Path(path)
    if not p.exists():
        return RedirectResponse("/ui?e=missing", status_code=303)
    return FileResponse(str(p))
