from __future__ import annotations

import json
from pathlib import Path
from sqlalchemy.orm import Session
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app import models

TEMPL_DIR = Path("app/templates")
env = Environment(
    loader=FileSystemLoader(str(TEMPL_DIR)),
    autoescape=select_autoescape(["html","xml"]),
)

def build_run_report_html(db: Session, run_id: int, out_path: str) -> str:
    run = db.query(models.Run).get(run_id)
    if not run:
        raise ValueError("run not found")
    bundle = db.query(models.TestBundle).get(run.bundle_id)
    tests = db.query(models.TestCase).filter(models.TestCase.bundle_id == run.bundle_id).all()

    # results keyed by (test_case_id, step_id)
    results = db.query(models.Result).filter(models.Result.run_id == run_id).all()
    res_map = {(r.test_case_id, r.step_id): r for r in results}

    evidence = db.query(models.Evidence).join(models.Result, models.Evidence.result_id == models.Result.id).filter(models.Result.run_id == run_id).all()
    ev_by_result = {}
    for ev in evidence:
        ev_by_result.setdefault(ev.result_id, []).append(ev)

    total = len(results)
    fails = sum(1 for r in results if r.status.value == "FAIL")
    passes = total - fails

    tmpl = env.get_template("run_report.html")
    html = tmpl.render(run=run, bundle=bundle, tests=tests, results=results, passes=passes, fails=fails, total=total, ev_by_result=ev_by_result)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(html, encoding="utf-8")
    return out_path

def build_run_report_pdf(html_path: str, pdf_path: str) -> str:
    # WeasyPrint converts HTML -> PDF
    from weasyprint import HTML
    Path(pdf_path).parent.mkdir(parents=True, exist_ok=True)
    HTML(filename=html_path).write_pdf(pdf_path)
    return pdf_path
