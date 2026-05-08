import json, os, hashlib
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session

from app.worker.celery_app import celery_app
from app.settings import settings
from app.db import SessionLocal
from app import models
from app.audit import audit

from playwright.sync_api import sync_playwright
from tenacity import retry, stop_after_attempt, wait_exponential

EVIDENCE_DIR = Path(settings.evidence_dir)

def _db() -> Session:
    return SessionLocal()

def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

@celery_app.task(bind=True)
def explore_app(self, application_id: int, actor_user_id: int, max_pages: int = 50):
    db = _db()
    try:
        app = db.query(models.Application).get(application_id)
        if not app:
            raise ValueError("application not found")
        audit(db, actor_user_id, "explore.start", {"application_id": application_id, "max_pages": max_pages})

        EXCLUDE = ["/logout", "/signout", "/delete", "?destroy=", "/admin/delete"]

        def should_visit(url: str) -> bool:
            if not url.startswith(app.base_url):
                return False
            return all(p not in url for p in EXCLUDE)

        def norm(url: str) -> str:
            return url.split("#")[0]

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context()
            page = ctx.new_page()

            queue = [app.base_url]
            seen: set[str] = set()

            total = max_pages
            while queue and len(seen) < max_pages:
                url = norm(queue.pop(0))
                if url in seen or not should_visit(url):
                    continue
                seen.add(url)
                self.update_state(state="PROGRESS", meta={
                    "stage": "crawling",
                    "current": len(seen),
                    "total": total,
                    "url": url,
                })

                page.goto(url, wait_until="domcontentloaded")
                title = page.title()
                dom = page.content()
                dom_hash = hashlib.sha256(dom.encode("utf-8")).hexdigest()

                existing = db.query(models.Page).filter(
                    models.Page.application_id == application_id,
                    models.Page.url == url
                ).first()

                if existing:
                    existing.title = title
                    existing.dom_hash = dom_hash
                    existing.discovered_at = datetime.utcnow()
                    pg = existing
                else:
                    pg = models.Page(application_id=application_id, url=url, title=title, dom_hash=dom_hash)
                    db.add(pg)
                db.commit()
                db.refresh(pg)

                audit(db, actor_user_id, "explore.page", {"application_id": application_id, "url": url, "title": title, "dom_hash": dom_hash})

                hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href).slice(0, 250)")
                for h in hrefs or []:
                    h2 = norm(h)
                    if should_visit(h2) and h2 not in seen:
                        queue.append(h2)

                elements = []

                btns = page.eval_on_selector_all(
                    "button, input[type=submit], [role=button]",
                    "els => els.slice(0, 150).map(e => ({tag: e.tagName.toLowerCase(), type: e.getAttribute('type'), testid: e.getAttribute('data-testid'), aria: e.getAttribute('aria-label'), text: (e.innerText||'').trim().slice(0,120)}))"
                )
                for b in btns or []:
                    label = b.get("aria") or b.get("text") or None
                    selector = None
                    if b.get("testid"):
                        selector = f"[data-testid='{b['testid']}']"
                    elif label:
                        selector = f"role=button[name='{label}']"
                    else:
                        continue
                    elements.append({"selector": selector, "role": "button", "label": label, "type": b.get("type") or b.get("tag"), "metadata": b})

                inputs = page.eval_on_selector_all(
                    "input, textarea, select",
                    "els => els.slice(0, 220).map(e => ({tag: e.tagName.toLowerCase(), type: e.getAttribute('type'), name: e.getAttribute('name'), id: e.getAttribute('id'), placeholder: e.getAttribute('placeholder'), testid: e.getAttribute('data-testid'), aria: e.getAttribute('aria-label')}))"
                )
                for i in inputs or []:
                    label = i.get("aria") or i.get("placeholder") or i.get("name") or i.get("id") or None
                    selector = None
                    if i.get("testid"):
                        selector = f"[data-testid='{i['testid']}']"
                    elif i.get("id"):
                        selector = f"#{i['id']}"
                    elif i.get("name"):
                        selector = f"[name='{i['name']}']"
                    else:
                        continue
                    elements.append({"selector": selector, "role": "input", "label": label, "type": i.get("type") or i.get("tag"), "metadata": i})

                # Replace page elements
                db.query(models.Element).filter(models.Element.page_id == pg.id).delete()
                db.commit()
                for e in elements[:400]:
                    db.add(models.Element(
                        page_id=pg.id,
                        selector=e["selector"],
                        role=e.get("role"),
                        label=e.get("label"),
                        type=e.get("type"),
                        metadata_json=json.dumps(e.get("metadata", {}), ensure_ascii=False),
                        discovered_at=datetime.utcnow(),
                    ))
                db.commit()

            browser.close()

        self.update_state(state="PROGRESS", meta={
            "stage": "finalizing",
            "current": len(seen),
            "total": max_pages,
        })
        audit(db, actor_user_id, "explore.done", {"application_id": application_id, "pages": len(seen)})
        return {"status": "ok", "pages": len(seen)}
    finally:
        db.close()

@celery_app.task(bind=True)
def generate_bundle(self, project_id: int, application_id: int, actor_user_id: int):
    db = _db()
    try:
        self.update_state(state="PROGRESS", meta={"stage": "loading_context", "current": 1, "total": 4})
        reqs = db.query(models.Requirement).filter(models.Requirement.project_id == project_id).all()
        app = db.query(models.Application).get(application_id)
        if not app:
            raise ValueError("application not found")
        from app.llm.provider import generate_tests
        req_dicts = [{"req_id": r.req_id, "text": r.text} for r in reqs]
        pages = db.query(models.Page).filter(models.Page.application_id == application_id).order_by(models.Page.discovered_at.desc()).limit(50).all()
        page_dicts = [{"id": p.id, "url": p.url, "title": p.title, "dom_hash": p.dom_hash} for p in pages]

        elements = []
        if pages:
            # Gather elements from the most recently discovered page first
            top_page_ids = [p.id for p in pages[:5]]
            el_rows = db.query(models.Element).filter(models.Element.page_id.in_(top_page_ids)).order_by(models.Element.id.asc()).limit(300).all()
            for e in el_rows:
                elements.append({"selector": e.selector, "role": e.role, "label": e.label, "type": e.type})

        llm_row = db.query(models.LLMSettings).filter(models.LLMSettings.project_id == project_id).order_by(models.LLMSettings.updated_at.desc()).first()
        llm_cfg = {
            "provider": llm_row.provider if llm_row else None,
            "model": llm_row.model if llm_row else None,
            "temperature": llm_row.temperature if llm_row else None,
            "max_output_tokens": llm_row.max_output_tokens if llm_row else None,
            "strict_json": llm_row.strict_json if llm_row else None,
        }
        audit(db, actor_user_id, "bundle.generate.context", {
            "project_id": project_id,
            "application_id": application_id,
            "req_count": len(req_dicts),
            "page_count": len(page_dicts),
            "element_count": len(elements),
            "llm_provider": (settings.llm_provider or "stub"),
            "model": settings.openai_model if (settings.llm_provider or "").lower() == "openai" else "n/a",
        })
        self.update_state(state="PROGRESS", meta={"stage": "generating_tests", "current": 2, "total": 4})
        tests = generate_tests(req_dicts, app.base_url, page_dicts, elements, llm_cfg)
        payload = json.dumps([t.model_dump() for t in tests], ensure_ascii=False, sort_keys=True)
        version_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        self.update_state(state="PROGRESS", meta={"stage": "saving_bundle", "current": 3, "total": 4})
        bundle = models.TestBundle(
            project_id=project_id,
            version_hash=version_hash,
            status=models.TestBundleStatus.draft,
            created_by=actor_user_id,
            llm_provider=llm_cfg.get("provider") if llm_cfg else None,
            llm_model=llm_cfg.get("model") if llm_cfg else None,
        )
        db.add(bundle); db.commit(); db.refresh(bundle)

        for t in tests:
            tc = models.TestCase(
                bundle_id=bundle.id, test_id=t.test_id, title=t.title, objective=t.objective,
                preconditions=json.dumps(t.preconditions), data_json=json.dumps(t.data),
                risk=t.risk, requirement_ids_json=json.dumps(t.requirement_ids),
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

        self.update_state(state="PROGRESS", meta={"stage": "finalizing", "current": 4, "total": 4})
        audit(db, actor_user_id, "bundle.generated", {"bundle_id": bundle.id, "version_hash": version_hash})
        return {"bundle_id": bundle.id, "version_hash": version_hash}
    finally:
        db.close()

@celery_app.task(bind=True)
def execute_bundle(self, bundle_id: int, actor_user_id: int):
    db = _db()
    try:
        bundle = db.query(models.TestBundle).get(bundle_id)
        if not bundle:
            raise ValueError("bundle not found")
        if bundle.status != models.TestBundleStatus.approved:
            raise ValueError("bundle not approved")

        run = models.Run(bundle_id=bundle_id, started_by=actor_user_id, status=models.RunStatus.running)
        db.add(run); db.commit(); db.refresh(run)

        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

        tests = db.query(models.TestCase).filter(models.TestCase.bundle_id == bundle_id).all()
        total_steps = 0
        for t in tests:
            total_steps += db.query(models.TestStep).filter(models.TestStep.test_case_id == t.id).count()
        completed = 0
        steps_by_test = {t.id: db.query(models.TestStep).filter(models.TestStep.test_case_id == t.id).order_by(models.TestStep.step_index).all() for t in tests}

        audit(db, actor_user_id, "run.start", {"run_id": run.id, "bundle_id": bundle_id})

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context()
            page = ctx.new_page()

            any_fail = False
            for t in tests:
                for step in steps_by_test[t.id]:
                    self.update_state(state="PROGRESS", meta={
                        "stage": "executing",
                        "current": completed,
                        "total": total_steps,
                        "test_id": t.id,
                        "step": step.step_index,
                    })
                    status = models.ResultStatus.pass_
                    msg = None
                    try:
                        _exec_step(page, step)
                        # evidence on critical
                        if step.critical:
                            ev_path = EVIDENCE_DIR / f"run{run.id}_test{t.id}_step{step.step_index}.png"
                            page.screenshot(path=str(ev_path), full_page=True)
                            digest = _sha256(ev_path)
                    except Exception as e:
                        status = models.ResultStatus.fail
                        msg = str(e)
                        any_fail = True
                        # evidence on failure
                        ev_path = EVIDENCE_DIR / f"run{run.id}_test{t.id}_step{step.step_index}_FAIL.png"
                        try:
                            page.screenshot(path=str(ev_path), full_page=True)
                            digest = _sha256(ev_path)
                        except Exception:
                            ev_path = None
                            digest = None

                    res = models.Result(run_id=run.id, test_case_id=t.id, step_id=step.id, status=status, message=msg, page_url=page.url)
                    db.add(res); db.commit(); db.refresh(res)
                    completed += 1

                    if ev_path and digest:
                        ev = models.Evidence(result_id=res.id, kind="screenshot", path=str(ev_path), sha256=digest)
                        db.add(ev); db.commit()

            browser.close()

        run.finished_at = datetime.utcnow()
        run.status = models.RunStatus.failed if any_fail else models.RunStatus.passed
        db.add(run); db.commit()

        self.update_state(state="PROGRESS", meta={"stage": "finalizing", "current": total_steps, "total": total_steps})
        audit(db, actor_user_id, "run.done", {"run_id": run.id, "status": run.status.value})
        return {"run_id": run.id, "status": run.status.value}
    finally:
        db.close()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _exec_step(page, step: models.TestStep):
    import json
    selector = json.loads(step.selector_json) if step.selector_json else {}
    if step.action == "goto":
        page.goto(selector["url"], wait_until="domcontentloaded")
    elif step.action == "assert_url_contains":
        contains = selector["contains"]
        if contains not in page.url:
            raise AssertionError(f"URL does not contain '{contains}': {page.url}")
    elif step.action == "click_css":
        page.locator(selector["css"]).click()
    elif step.action == "fill_css":
        page.locator(selector["css"]).fill(step.input or "")
    else:
        raise ValueError(f"Unknown action: {step.action}")
