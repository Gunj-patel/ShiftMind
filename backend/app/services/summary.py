"""Shift summary + handover generation.

Facts and action items are computed deterministically. The LLM (if configured)
only rewrites the narrative, and its output is discarded if it contains any
number not present in the facts.
"""
from __future__ import annotations

import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.entities import HandoverAction, ShiftRecord
from . import llm
from .anomaly import find_missing_reports

SEV_RANK = {"critical": 0, "warning": 1, "info": 2}
NEXT_SHIFT = {"morning": "evening", "evening": "night", "night": "morning"}


def _sum(vals):
    v = [x for x in vals if x is not None]
    return sum(v) if v else None


def shift_facts(db: Session, day: date, shift: str) -> dict:
    recs = db.scalars(select(ShiftRecord).where(ShiftRecord.shift_date == day, ShiftRecord.shift == shift)
                      .order_by(ShiftRecord.machine)).all()
    target = _sum(r.target_units for r in recs)
    actual = _sum(r.actual_units for r in recs)
    # achievement only over records that have both numbers, to avoid a misleading ratio
    both = [r for r in recs if r.target_units and r.actual_units is not None]
    ach = (sum(r.actual_units for r in both) / sum(r.target_units for r in both)) if both else None
    machines = []
    for r in recs:
        machines.append({
            "record_id": r.id, "machine": r.machine, "product": r.product,
            "target": r.target_units, "actual": r.actual_units,
            "achievement": (r.actual_units / r.target_units) if r.target_units and r.actual_units is not None else None,
            "downtime_min": r.downtime_min, "rejected": r.rejected_units,
            "downtime_reason": r.downtime_reason, "maintenance": r.maintenance_status,
            "notes": r.notes, "operator": r.operator, "source_ref": r.source_ref,
            "anomalies": sorted(({"rule": a.rule, "severity": a.severity, "message": a.message, "evidence": a.evidence}
                                 for a in r.anomalies), key=lambda a: SEV_RANK[a["severity"]]),
        })
    flagged = any(a["severity"] in ("critical", "warning") for m in machines for a in m["anomalies"])
    return {
        "date": day.isoformat(), "shift": shift, "machine_count": len(recs),
        "total_target": target, "total_actual": actual, "achievement": ach,
        "total_downtime_min": _sum(r.downtime_min for r in recs),
        "total_rejected": _sum(r.rejected_units for r in recs),
        "status": "attention" if flagged else "normal",
        "machines": machines,
        "missing_reports": [m for m in find_missing_reports(db, day) if m["shift"] == shift],
    }


def _fmt(v, suffix=""):
    return "n/a" if v is None else f"{v:g}{suffix}"


def template_narrative(f: dict) -> str:
    if not f["machine_count"]:
        return "No records were found for this shift."
    parts = []
    ach = f["achievement"]
    line = f"{f['shift'].capitalize()} shift on {f['date']}: {f['machine_count']} machine(s) reported."
    if f["total_target"] is not None and f["total_actual"] is not None:
        line += f" Production was {_fmt(f['total_actual'])} units against a target of {_fmt(f['total_target'])}"
        line += f" ({ach * 100:.0f}% achievement)." if ach is not None else "."
    parts.append(line)
    if f["total_downtime_min"]:
        parts.append(f"Total downtime was {_fmt(f['total_downtime_min'])} minutes.")
    for m in f["machines"]:
        crit = [a for a in m["anomalies"] if a["severity"] == "critical"]
        if crit or (m["downtime_min"] or 0) >= 60:
            s = f"{m['machine']}: "
            if m["downtime_min"]:
                s += f"{_fmt(m['downtime_min'])} min downtime"
                s += f" due to {m['downtime_reason']}. " if m["downtime_reason"] else ". "
            s += " ".join(a["message"] + "." for a in crit[:2])
            parts.append(s.strip())
    if f["missing_reports"]:
        parts.append("Missing reports: " + ", ".join(m["machine"] for m in f["missing_reports"]) + ".")
    return " ".join(parts)


def narrative(f: dict) -> tuple[str, str]:
    """Returns (text, source) where source is 'llm' or 'rules'."""
    base = template_narrative(f)
    if not f["machine_count"] or not llm.llm_available():
        return base, "rules"
    facts = json.dumps({k: v for k, v in f.items() if k != "machines"} | {
        "machines": [{k: v for k, v in m.items() if k not in ("record_id", "source_ref")} for m in f["machines"]]},
        default=str)
    out = llm.complete(
        "You write concise shift summaries for factory supervisors. Use ONLY the facts given. "
        "Never invent or compute new numbers. Do not say whether a machine is safe to run. 3-5 sentences.",
        facts)
    if out and llm.numbers_grounded(out, facts + base):
        return out, "llm"
    return base, "rules"


def build_actions(f: dict) -> list[dict]:
    """Deterministic handover checklist derived from flagged records."""
    actions: list[dict] = []
    for m in f["machines"]:
        rules = {a["rule"]: a for a in m["anomalies"]}
        mid, mach = m["record_id"], m["machine"]
        if m["maintenance"] == "pending":
            why = m["downtime_reason"] or "maintenance marked pending"
            actions.append({"machine": mach, "priority": "high", "source_record_id": mid,
                            "action": f"Maintenance to inspect {mach} ({why}).", "reason": "Maintenance pending from previous shift"})
            actions.append({"machine": mach, "priority": "high", "source_record_id": mid,
                            "action": f"Supervisor to verify {mach} condition before restarting production.",
                            "reason": "Open maintenance item - a person must confirm the machine is fit to run"})
        if "repeat_failure" in rules:
            actions.append({"machine": mach, "priority": "high", "source_record_id": mid,
                            "action": f"Raise root-cause review for repeated '{m['downtime_reason']}' on {mach}.",
                            "reason": rules["repeat_failure"]["evidence"]})
        if "target_shortfall" in rules:
            pr = "high" if rules["target_shortfall"]["severity"] == "critical" else "medium"
            actions.append({"machine": mach, "priority": pr, "source_record_id": mid,
                            "action": f"Review production shortfall on {mach} with the shift supervisor.",
                            "reason": rules["target_shortfall"]["evidence"]})
        if "high_reject_rate" in rules or "quality_issue_reported" in rules:
            ev = (rules.get("high_reject_rate") or rules["quality_issue_reported"])["evidence"]
            actions.append({"machine": mach, "priority": "high" if "high_reject_rate" in rules and rules["high_reject_rate"]["severity"] == "critical" else "medium",
                            "source_record_id": mid, "action": f"QA to check output quality on {mach}.", "reason": ev})
        for key in ("impossible_downtime", "rejects_exceed_output", "negative_value", "missing_actual", "missing_downtime_reason"):
            if key in rules:
                actions.append({"machine": mach, "priority": "medium", "source_record_id": mid,
                                "action": f"Correct the log entry for {mach}: {rules[key]['message'].lower()}.",
                                "reason": rules[key]["evidence"] or rules[key]["message"]})
        if m["notes"]:
            actions.append({"machine": mach, "priority": "low", "source_record_id": mid,
                            "action": f"Follow up on operator note for {mach}: {m['notes'][:160]}", "reason": "Operator note in shift log"})
    for mr in f["missing_reports"]:
        actions.append({"machine": mr["machine"], "priority": "medium", "source_record_id": None,
                        "action": f"Obtain the missing {mr['shift']} shift report for {mr['machine']}.", "reason": mr["message"]})
    order = {"high": 0, "medium": 1, "low": 2}
    seen, out = set(), []
    for a in sorted(actions, key=lambda a: order[a["priority"]]):
        k = (a["machine"], a["action"])
        if k not in seen:
            seen.add(k)
            out.append(a)
    return out


def generate_handover(db: Session, day: date, shift: str) -> dict:
    f = shift_facts(db, day, shift)
    text, source = narrative(f)
    actions = build_actions(f)
    # persist, replacing any previous auto-generated list for this shift
    for old in db.scalars(select(HandoverAction).where(HandoverAction.shift_date == day, HandoverAction.from_shift == shift)).all():
        db.delete(old)
    db.flush()
    saved = []
    for a in actions:
        row = HandoverAction(shift_date=day, from_shift=shift, **a)
        db.add(row)
        saved.append(row)
    db.commit()
    return {"facts": f, "summary": text, "summary_source": source, "incoming_shift": NEXT_SHIFT[shift],
            "actions": [{"id": r.id, "machine": r.machine, "priority": r.priority, "action": r.action,
                         "reason": r.reason, "source_record_id": r.source_record_id, "done": r.done} for r in saved]}
