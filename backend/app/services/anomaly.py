"""Deterministic anomaly detection. No LLM is involved: every flag carries the
numbers that triggered it so a supervisor can verify it by hand."""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.entities import Anomaly, ShiftRecord

SHIFT_LENGTH_MIN = 480
SHIFTS = ("morning", "evening", "night")

# Thresholds live in one place so they are easy to tune per plant.
THRESHOLDS = {
    "achievement_warn": 0.90,
    "achievement_crit": 0.70,
    "overproduction": 1.25,
    "downtime_warn": 60,
    "downtime_crit": 120,
    "reject_warn": 0.03,
    "reject_crit": 0.08,
    "zscore": 2.5,
    "min_history": 5,
    "consumption_dev": 0.20,
    "repeat_days": 7,
    "repeat_count": 2,
    "repeat_min_downtime": 30,  # short stops are not failures worth a root-cause review
}

# Planned/routine stoppages that are expected to recur and must not be reported as repeat failures.
ROUTINE_REASONS = ("changeover", "cleaning", "setup", "set-up", "planned", "break", "shift change", "calibration")


@dataclass
class Flag:
    rule: str
    severity: str
    message: str
    evidence: str = ""


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def evaluate_record(rec: ShiftRecord, history: list[ShiftRecord]) -> list[Flag]:
    """Evaluate one record against fixed rules and the machine's own history."""
    t = THRESHOLDS
    flags: list[Flag] = []

    # ---- data integrity -------------------------------------------------
    for fname in ("target_units", "actual_units", "downtime_min", "rejected_units", "raw_material_kg"):
        v = getattr(rec, fname)
        if v is not None and v < 0:
            flags.append(Flag("negative_value", "critical", f"{fname} is negative", f"{fname}={v}"))
    if rec.downtime_min is not None and rec.downtime_min > SHIFT_LENGTH_MIN:
        flags.append(Flag("impossible_downtime", "critical",
                          "Downtime exceeds the length of a shift - likely a data entry error",
                          f"downtime={rec.downtime_min:g} min, shift={SHIFT_LENGTH_MIN} min"))
    if rec.actual_units is not None and rec.rejected_units is not None and rec.rejected_units > rec.actual_units:
        flags.append(Flag("rejects_exceed_output", "critical",
                          "Rejected units exceed total units produced",
                          f"rejected={rec.rejected_units:g}, actual={rec.actual_units:g}"))
    if rec.actual_units is None:
        flags.append(Flag("missing_actual", "warning", "Actual production was not recorded"))
    if rec.target_units is None:
        flags.append(Flag("missing_target", "info", "Production target was not recorded"))
    if (rec.downtime_min or 0) > 0 and not rec.downtime_reason:
        flags.append(Flag("missing_downtime_reason", "warning", "Downtime recorded without a reason",
                          f"downtime={rec.downtime_min:g} min"))

    # ---- production vs target -------------------------------------------
    if rec.target_units and rec.actual_units is not None and rec.target_units > 0:
        ach = rec.actual_units / rec.target_units
        ev = f"actual={rec.actual_units:g}, target={rec.target_units:g}, achievement={_pct(ach)}"
        gap = rec.target_units - rec.actual_units
        if ach < t["achievement_crit"]:
            flags.append(Flag("target_shortfall", "critical", f"Production {gap:g} units below target", ev))
        elif ach < t["achievement_warn"]:
            flags.append(Flag("target_shortfall", "warning", f"Production {gap:g} units below target", ev))
        elif ach > t["overproduction"]:
            flags.append(Flag("overproduction", "info",
                              "Output far above target - check that the target or count is correct", ev))

    # ---- downtime --------------------------------------------------------
    if rec.downtime_min is not None and rec.downtime_min <= SHIFT_LENGTH_MIN:
        ev = f"downtime={rec.downtime_min:g} min"
        if rec.downtime_min >= t["downtime_crit"]:
            flags.append(Flag("high_downtime", "critical", "Major downtime during shift", ev))
        elif rec.downtime_min >= t["downtime_warn"]:
            flags.append(Flag("high_downtime", "warning", "Significant downtime during shift", ev))

    # ---- quality ---------------------------------------------------------
    if rec.actual_units and rec.rejected_units is not None and rec.rejected_units <= rec.actual_units:
        rate = rec.rejected_units / rec.actual_units
        ev = f"rejected={rec.rejected_units:g} of {rec.actual_units:g} ({rate * 100:.1f}%)"
        if rate >= t["reject_crit"]:
            flags.append(Flag("high_reject_rate", "critical", "Reject rate is very high", ev))
        elif rate >= t["reject_warn"]:
            flags.append(Flag("high_reject_rate", "warning", "Reject rate above normal", ev))
    if rec.quality_issue:
        flags.append(Flag("quality_issue_reported", "warning", "Quality issue reported by operator",
                          rec.quality_issue[:200]))

    # ---- maintenance -----------------------------------------------------
    if rec.maintenance_status == "pending":
        sev = "critical" if (rec.downtime_min or 0) >= t["downtime_warn"] else "warning"
        flags.append(Flag("maintenance_pending", sev, "Maintenance still pending on this machine",
                          rec.downtime_reason[:200] or "no reason recorded"))

    # ---- history based (machine's own baseline) --------------------------
    prior = [h for h in history if h.id != rec.id and h.machine == rec.machine and (h.shift_date, h.shift) < (rec.shift_date, rec.shift)]
    prior_actual = [h.actual_units for h in prior if h.actual_units is not None]
    if rec.actual_units is not None and len(prior_actual) >= t["min_history"]:
        mean = statistics.fmean(prior_actual)
        sd = statistics.pstdev(prior_actual)
        if sd > 0:
            z = (rec.actual_units - mean) / sd
            if abs(z) >= t["zscore"]:
                flags.append(Flag("production_outlier", "warning",
                                  "Production is unusual compared with this machine's history",
                                  f"actual={rec.actual_units:g}, mean={mean:.0f}, sd={sd:.0f}, z={z:+.1f} over {len(prior_actual)} shifts"))

    if rec.raw_material_kg and rec.actual_units and rec.actual_units > 0:
        per_unit = rec.raw_material_kg / rec.actual_units
        base = [h.raw_material_kg / h.actual_units for h in prior
                if h.raw_material_kg and h.actual_units and h.actual_units > 0
                and (not rec.product or h.product == rec.product)]
        if len(base) >= t["min_history"]:
            med = statistics.median(base)
            if med > 0 and abs(per_unit - med) / med > t["consumption_dev"]:
                flags.append(Flag("consumption_deviation", "warning",
                                  "Raw material use per unit deviates from normal",
                                  f"{per_unit:.3f} kg/unit vs typical {med:.3f} kg/unit ({(per_unit - med) / med * 100:+.0f}%)"))

    routine = any(w in rec.downtime_reason.lower() for w in ROUTINE_REASONS)
    if rec.downtime_reason and not routine and (rec.downtime_min or 0) >= t["repeat_min_downtime"]:
        cutoff = rec.shift_date - timedelta(days=t["repeat_days"])
        key = rec.downtime_reason.strip().lower()
        same = [h for h in prior if h.shift_date >= cutoff and h.downtime_reason.strip().lower() == key]
        if len(same) + 1 >= t["repeat_count"]:
            flags.append(Flag("repeat_failure", "critical" if len(same) >= 2 else "warning",
                              "Same downtime cause has occurred repeatedly on this machine",
                              f"'{rec.downtime_reason}' seen {len(same) + 1} times in the last {t['repeat_days']} days"))
    return flags


def analyze_all(db: Session, only_ids: set[int] | None = None) -> int:
    """(Re)compute anomalies for the given records (or all). Returns number of flags written."""
    records = db.scalars(select(ShiftRecord).order_by(ShiftRecord.shift_date, ShiftRecord.id)).all()
    count = 0
    for rec in records:
        if only_ids is not None and rec.id not in only_ids:
            continue
        for a in list(rec.anomalies):
            db.delete(a)
        db.flush()
        for f in evaluate_record(rec, records):
            db.add(Anomaly(record_id=rec.id, rule=f.rule, severity=f.severity, message=f.message, evidence=f.evidence))
            count += 1
    db.commit()
    return count


def find_missing_reports(db: Session, day: date) -> list[dict]:
    """Machines that normally report (>=3 records in the 7 days before) but have
    no record for a shift that other machines did report on `day`."""
    window_start = day - timedelta(days=7)
    recent = db.scalars(select(ShiftRecord).where(ShiftRecord.shift_date >= window_start, ShiftRecord.shift_date < day)).all()
    counts: dict[str, int] = {}
    for r in recent:
        counts[r.machine] = counts.get(r.machine, 0) + 1
    regular = {m for m, c in counts.items() if c >= 3}
    today = db.scalars(select(ShiftRecord).where(ShiftRecord.shift_date == day)).all()
    reported: dict[str, set[str]] = {}
    for r in today:
        reported.setdefault(r.shift, set()).add(r.machine)
    missing = []
    for shift, machines in reported.items():
        for m in sorted(regular - machines):
            missing.append({"date": day.isoformat(), "shift": shift, "machine": m,
                            "message": f"No report for {m} in the {shift} shift although other machines reported"})
    return missing
