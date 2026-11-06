"""Ask ShiftMind: question answering over stored shift records, with sources.

Pipeline: (1) deterministic query parsing (machine, shift, dates, topic),
(2) SQL filter + keyword scoring to retrieve records, (3) numbers computed in
Python, (4) optional LLM phrasing over the retrieved records only. Every answer
returns the records it was built from, so each claim can be traced to a source row.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.entities import ShiftRecord
from . import llm

STOP = {"the", "a", "an", "of", "on", "in", "for", "to", "is", "was", "were", "what", "which", "why", "how",
        "did", "do", "does", "me", "show", "tell", "about", "and", "or", "with", "had", "has", "have", "last",
        "this", "that", "shift", "machine", "any", "all", "total", "many", "much", "happened", "week", "yesterday", "today"}
TOPIC_WORDS = {
    "downtime": {"downtime", "stopped", "stoppage", "breakdown", "down", "idle"},
    "production": {"production", "output", "produced", "units", "target", "shortfall", "achievement"},
    "quality": {"quality", "reject", "rejects", "rejected", "defect", "defects", "scrap"},
    "maintenance": {"maintenance", "repair", "inspect", "pending", "service"},
    "material": {"material", "consumption", "raw", "kg"},
}


def _parse_query(db: Session, q: str) -> dict:
    ql = q.lower()
    machines = sorted({m.upper() for m in re.findall(r"\b([a-z]{1,4}-?\d{1,4})\b", ql)})
    known = set(db.scalars(select(ShiftRecord.machine).distinct()).all())
    machines = [m for m in machines if m in known]
    shifts = [s for s in ("morning", "evening", "night") if s in ql]
    latest = db.scalar(select(ShiftRecord.shift_date).order_by(ShiftRecord.shift_date.desc()).limit(1))
    start = end = None
    if latest:
        if "yesterday" in ql:
            start = end = latest - timedelta(days=1)
        elif "today" in ql or "latest" in ql or "last shift" in ql:
            start = end = latest
        elif "last week" in ql or "this week" in ql or "past week" in ql or "7 days" in ql:
            start, end = latest - timedelta(days=6), latest
    for m in re.finditer(r"\b(\d{4}-\d{2}-\d{2})\b", ql):
        d = date.fromisoformat(m.group(1))
        start = d if start is None else min(start, d)
        end = d if end is None else max(end, d)
    topics = [t for t, ws in TOPIC_WORDS.items() if ws & set(re.findall(r"[a-z]+", ql))]
    keywords = [w for w in re.findall(r"[a-z]{3,}", ql) if w not in STOP]
    return {"machines": machines, "shifts": shifts, "start": start, "end": end, "topics": topics, "keywords": keywords}


def _score(r: ShiftRecord, p: dict) -> float:
    text = " ".join([r.downtime_reason, r.quality_issue, r.notes, r.product, r.maintenance_status]).lower()
    s = 0.0
    for k in p["keywords"]:
        if k in text:
            s += 2
    if "maintenance" in p["topics"] and r.maintenance_status == "pending":
        s += 3
    if "downtime" in p["topics"] and (r.downtime_min or 0) > 0:
        s += 1 + min((r.downtime_min or 0) / 60, 3)
    if "quality" in p["topics"] and ((r.rejected_units or 0) > 0 or r.quality_issue):
        s += 2
    if "production" in p["topics"] and r.target_units and r.actual_units is not None:
        s += 3 * max(0, 1 - r.actual_units / r.target_units)
    return s


def _describe(r: ShiftRecord) -> str:
    bits = [f"{r.shift_date} {r.shift} {r.machine}"]
    if r.target_units is not None or r.actual_units is not None:
        bits.append(f"target {r.target_units:g}" if r.target_units is not None else "target n/a")
        bits.append(f"actual {r.actual_units:g}" if r.actual_units is not None else "actual n/a")
    if r.downtime_min:
        bits.append(f"downtime {r.downtime_min:g} min" + (f" ({r.downtime_reason})" if r.downtime_reason else ""))
    if r.rejected_units:
        bits.append(f"rejected {r.rejected_units:g}")
    if r.maintenance_status:
        bits.append(f"maintenance {r.maintenance_status}")
    if r.quality_issue:
        bits.append(f"quality: {r.quality_issue}")
    if r.notes:
        bits.append(f"note: {r.notes}")
    return "; ".join(bits)


def _stats(recs: list[ShiftRecord], p: dict) -> list[str]:
    out = []
    if not recs:
        return out
    dt = [r.downtime_min for r in recs if r.downtime_min is not None]
    if dt and ("downtime" in p["topics"] or not p["topics"]):
        out.append(f"Total downtime across {len(dt)} matching record(s): {sum(dt):g} minutes.")
        reasons: dict[str, float] = {}
        for r in recs:
            if r.downtime_reason and r.downtime_min:
                reasons[r.downtime_reason] = reasons.get(r.downtime_reason, 0) + r.downtime_min
        if reasons:
            top = max(reasons.items(), key=lambda kv: kv[1])
            out.append(f"Largest downtime cause: {top[0]} ({top[1]:g} min).")
    both = [r for r in recs if r.target_units and r.actual_units is not None]
    if both and ("production" in p["topics"] or not p["topics"]):
        a, t = sum(r.actual_units for r in both), sum(r.target_units for r in both)
        out.append(f"Production {a:g} vs target {t:g} units ({a / t * 100:.0f}% achievement).")
    rej = [r.rejected_units for r in recs if r.rejected_units is not None]
    if rej and "quality" in p["topics"]:
        out.append(f"Total rejected units: {sum(rej):g}.")
    return out


def answer(db: Session, question: str, limit: int = 8) -> dict:
    p = _parse_query(db, question)
    stmt = select(ShiftRecord)
    if p["machines"]:
        stmt = stmt.where(ShiftRecord.machine.in_(p["machines"]))
    if p["shifts"]:
        stmt = stmt.where(ShiftRecord.shift.in_(p["shifts"]))
    if p["start"]:
        stmt = stmt.where(ShiftRecord.shift_date >= p["start"])
    if p["end"]:
        stmt = stmt.where(ShiftRecord.shift_date <= p["end"])
    recs = db.scalars(stmt).all()
    if not recs:
        return {"answer": "I could not find any shift records matching that question. Try a machine ID, shift or date.",
                "sources": [], "answer_source": "rules", "filters": _filters(p)}
    ranked = sorted(recs, key=lambda r: (_score(r, p), r.shift_date), reverse=True)
    if p["topics"] or p["keywords"]:
        relevant = [r for r in ranked if _score(r, p) > 0] or ranked
    else:
        relevant = sorted(recs, key=lambda r: r.shift_date, reverse=True)
    top = relevant[:limit]
    stats = _stats(relevant, p)
    sources = [{"record_id": r.id, "ref": r.source_ref, "label": f"{r.shift_date} {r.shift} {r.machine}",
                "excerpt": _describe(r)} for r in top]

    base = f"Found {len(relevant)} relevant record(s). " + " ".join(stats)
    base += " Most relevant: " + " | ".join(f"[{i + 1}] {s['excerpt']}" for i, s in enumerate(sources[:3]))
    text, src = base.strip(), "rules"
    if llm.llm_available():
        ctx = "\n".join(f"[{i + 1}] {s['excerpt']}" for i, s in enumerate(sources)) + "\n" + "\n".join(stats)
        out = llm.complete(
            "You answer questions about factory shift logs. Use ONLY the numbered records and computed figures below. "
            "Cite records like [1]. If the records do not answer the question, say so. Never invent numbers.",
            f"Question: {question}\n\nRecords:\n{ctx}")
        if out and llm.numbers_grounded(out, ctx + base):
            text, src = out, "llm"
    return {"answer": text, "sources": sources, "answer_source": src, "filters": _filters(p)}


def _filters(p: dict) -> dict:
    return {"machines": p["machines"], "shifts": p["shifts"],
            "start": p["start"].isoformat() if p["start"] else None,
            "end": p["end"].isoformat() if p["end"] else None, "topics": p["topics"]}
