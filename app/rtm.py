import json
from pathlib import Path
from sqlalchemy.orm import Session
from openpyxl import Workbook
from app import models

def build_rtm_xlsx(db: Session, run_id: int, out_path: str):
    run = db.query(models.Run).get(run_id)
    if not run:
        raise ValueError("run not found")

    wb = Workbook()
    ws = wb.active
    ws.title = "RTM"
    ws.append(["Requirement ID","Test ID","Step","Result","Evidence Path","Evidence SHA256"])

    tests = db.query(models.TestCase).filter(models.TestCase.bundle_id == run.bundle_id).all()
    for t in tests:
        req_ids = json.loads(t.requirement_ids_json or "[]")
        steps = db.query(models.TestStep).filter(models.TestStep.test_case_id == t.id).order_by(models.TestStep.step_index).all()
        for rid in req_ids or [None]:
            for s in steps:
                res = db.query(models.Result).filter(
                    models.Result.run_id == run_id,
                    models.Result.test_case_id == t.id,
                    models.Result.step_id == s.id
                ).first()
                ev = None
                if res:
                    ev = db.query(models.Evidence).filter(models.Evidence.result_id == res.id).first()
                ws.append([
                    rid or "(unmapped)",
                    t.test_id,
                    s.step_index,
                    res.status.value if res else "N/A",
                    ev.path if ev else "",
                    ev.sha256 if ev else "",
                ])

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path
