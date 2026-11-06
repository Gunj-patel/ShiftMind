from __future__ import annotations

import os
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Anomaly, HandoverAction, ShiftRecord, UploadedDocument, get_db, init_db
from .services import llm, qa
from .services.anomaly import analyze_all, find_missing_reports
from .services.parser import parse_text, parse_upload
from .services.summary import generate_handover, shift_facts

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="ShiftMind API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(","),
    allow_methods=["*"], allow_headers=["*"],
)


def _store(db: Session, filename: str, res) -> dict:
    doc = UploadedDocument(filename=filename, kind=res.kind, rows_parsed=len(res.rows),
                           rows_rejected=len(res.rejected),
                           parse_notes="\n".join(res.notes + [f"{r['ref']}: {r['reason']}" for r in res.rejected]))
    db.add(doc)
    db.flush()
    ids = set()
    for row in res.rows:
        rec = ShiftRecord(document_id=doc.id, **row)
        db.add(rec)
        db.flush()
        ids.add(rec.id)
    db.commit()
    # history-based rules for neighbours may change too, so re-analyse everything (small data volumes)
    flags = analyze_all(db)
    return {"document_id": doc.id, "filename": filename, "kind": res.kind, "rows_parsed": len(res.rows),
            "rows_rejected": len(res.rejected), "rejected": res.rejected, "notes": res.notes, "anomalies_total": flags}


@app.get("/api/health")
def health():
    return {"status": "ok", "llm_enabled": llm.llm_available()}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (10 MB limit)")
    try:
        res = parse_upload(file.filename or "upload", data)
    except ValueError as e:
        raise HTTPException(415, str(e))
    except Exception as e:  # corrupted file etc.
        raise HTTPException(422, f"Could not read file: {e}")
    return _store(db, file.filename or "upload", res)


class TextIn(BaseModel):
    text: str
    label: str = "pasted-text"


@app.post("/api/upload-text")
def upload_text(body: TextIn, db: Session = Depends(get_db)):
    return _store(db, body.label, parse_text(body.text, body.label))


@app.get("/api/documents")
def documents(db: Session = Depends(get_db)):
    docs = db.scalars(select(UploadedDocument).order_by(UploadedDocument.id.desc())).all()
    return [{"id": d.id, "filename": d.filename, "kind": d.kind, "uploaded_at": d.uploaded_at.isoformat(),
             "rows_parsed": d.rows_parsed, "rows_rejected": d.rows_rejected, "notes": d.parse_notes} for d in docs]


@app.get("/api/shifts")
def shifts(db: Session = Depends(get_db)):
    rows = db.execute(select(ShiftRecord.shift_date, ShiftRecord.shift).distinct()
                      .order_by(ShiftRecord.shift_date.desc())).all()
    order = {"morning": 0, "evening": 1, "night": 2}
    return sorted(({"date": d.isoformat(), "shift": s} for d, s in rows),
                  key=lambda x: (x["date"], order[x["shift"]]), reverse=True)


@app.get("/api/report")
def report(date: date, shift: str, db: Session = Depends(get_db)):
    if shift not in ("morning", "evening", "night"):
        raise HTTPException(400, "shift must be morning, evening or night")
    return generate_handover(db, date, shift)


@app.get("/api/facts")
def facts(date: date, shift: str, db: Session = Depends(get_db)):
    return shift_facts(db, date, shift)


@app.get("/api/anomalies")
def anomalies(severity: str | None = None, db: Session = Depends(get_db)):
    q = select(Anomaly, ShiftRecord).join(ShiftRecord, Anomaly.record_id == ShiftRecord.id)
    if severity:
        q = q.where(Anomaly.severity == severity)
    rows = db.execute(q.order_by(ShiftRecord.shift_date.desc())).all()
    rank = {"critical": 0, "warning": 1, "info": 2}
    out = [{"id": a.id, "record_id": r.id, "date": r.shift_date.isoformat(), "shift": r.shift, "machine": r.machine,
            "rule": a.rule, "severity": a.severity, "message": a.message, "evidence": a.evidence, "source_ref": r.source_ref}
           for a, r in rows]
    return sorted(out, key=lambda x: (rank[x["severity"]], x["date"]), reverse=False)


@app.get("/api/trends")
def trends(machine: str | None = None, db: Session = Depends(get_db)):
    q = select(ShiftRecord).order_by(ShiftRecord.shift_date, ShiftRecord.id)
    if machine:
        q = q.where(ShiftRecord.machine == machine.upper())
    by_day: dict[str, dict] = defaultdict(lambda: {"target": 0.0, "actual": 0.0, "downtime": 0.0, "rejected": 0.0})
    for r in db.scalars(q).all():
        d = by_day[r.shift_date.isoformat()]
        d["target"] += r.target_units or 0
        d["actual"] += r.actual_units or 0
        d["downtime"] += r.downtime_min or 0
        d["rejected"] += r.rejected_units or 0
    return [{"date": k, **v, "achievement": (v["actual"] / v["target"] * 100) if v["target"] else None}
            for k, v in sorted(by_day.items())]


@app.get("/api/machines")
def machines(db: Session = Depends(get_db)):
    return sorted(db.scalars(select(ShiftRecord.machine).distinct()).all())


@app.get("/api/missing")
def missing(date: date, db: Session = Depends(get_db)):
    return find_missing_reports(db, date)


class ActionPatch(BaseModel):
    done: bool


@app.patch("/api/actions/{action_id}")
def patch_action(action_id: int, body: ActionPatch, db: Session = Depends(get_db)):
    a = db.get(HandoverAction, action_id)
    if not a:
        raise HTTPException(404, "Action not found")
    a.done = body.done
    db.commit()
    return {"id": a.id, "done": a.done}


class AskIn(BaseModel):
    question: str


@app.post("/api/ask")
def ask(body: AskIn, db: Session = Depends(get_db)):
    if not body.question.strip():
        raise HTTPException(400, "Question is empty")
    return qa.answer(db, body.question.strip())


@app.delete("/api/data")
def reset(db: Session = Depends(get_db)):
    """Clear all stored data (demo convenience)."""
    for model in (HandoverAction, Anomaly, ShiftRecord, UploadedDocument):
        for obj in db.scalars(select(model)).all():
            db.delete(obj)
    db.commit()
    return {"status": "cleared"}
