"""Turn messy shift reports (CSV, Excel, PDF, pasted text) into structured rows.

Parsing is deterministic: header aliases for tabular files, "Key: value" block
parsing for PDFs/text. Rows that cannot be understood are rejected with a
reason rather than guessed, so numbers are never invented.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime

import pandas as pd

FIELD_ALIASES: dict[str, list[str]] = {
    "shift_date": ["date", "shift date", "shift_date", "day", "report date"],
    "shift": ["shift", "shift name", "shift_name"],
    "machine": ["machine", "machine id", "machine_id", "equipment", "equipment id", "line", "asset"],
    "product": ["product", "product name", "item", "batch product", "material"],
    "target_units": ["target", "production target", "target units", "planned", "planned qty", "target_units"],
    "actual_units": ["actual", "actual production", "actual units", "produced", "output", "actual_units", "qty produced"],
    "downtime_min": ["downtime", "downtime min", "downtime (min)", "downtime minutes", "downtime_min", "stoppage", "stop time"],
    "rejected_units": ["rejected", "rejects", "rejected units", "scrap", "defects", "rejected_units"],
    "raw_material_kg": ["raw material", "raw material kg", "raw material (kg)", "material used", "consumption", "raw_material_kg"],
    "downtime_reason": ["reason", "downtime reason", "stoppage reason", "downtime_reason", "cause"],
    "quality_issue": ["quality", "quality issue", "quality issues", "quality_issue", "qc remarks"],
    "maintenance_status": ["maintenance", "maintenance status", "maintenance_status", "pm status"],
    "notes": ["notes", "remarks", "comments", "pending", "pending work", "observations"],
    "operator": ["operator", "supervisor", "recorded by", "engineer", "operator name"],
}

NUMERIC_FIELDS = {"target_units", "actual_units", "downtime_min", "rejected_units", "raw_material_kg"}
SHIFT_ALIASES = {
    "morning": "morning", "m": "morning", "a": "morning", "1": "morning", "day": "morning", "first": "morning",
    "evening": "evening", "e": "evening", "b": "evening", "2": "evening", "afternoon": "evening", "second": "evening",
    "night": "night", "n": "night", "c": "night", "3": "night", "third": "night",
}
MAINT_ALIASES = {
    "pending": "pending", "open": "pending", "required": "pending", "due": "pending", "scheduled": "pending",
    "done": "done", "completed": "done", "closed": "done", "resolved": "done",
    "none": "none", "n/a": "none", "na": "none", "nil": "none", "": "",
}


@dataclass
class ParseResult:
    kind: str
    rows: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)  # {"ref":..., "reason":...}
    notes: list[str] = field(default_factory=list)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower().replace("_", " "))


_ALIAS_LOOKUP = {_norm(a): f for f, al in FIELD_ALIASES.items() for a in al}


def canonical_field(header: str) -> str | None:
    return _ALIAS_LOOKUP.get(_norm(header))


def parse_number(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return None if pd.isna(v) else float(v)
    s = str(v).strip().lower().replace(",", "")
    if s in {"", "-", "na", "n/a", "nil", "none", "nan"}:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    num = float(m.group())
    # "1.5 hrs" / "2 h" -> minutes
    if re.search(r"\b(hr|hrs|hour|hours|h)\b", s) and not re.search(r"\bmin", s):
        num *= 60
    return num


def parse_date(v) -> date | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if hasattr(v, "to_pydatetime"):
        return v.to_pydatetime().date()
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def normalize_shift(v) -> str | None:
    if v is None:
        return None
    return SHIFT_ALIASES.get(_norm(v))


def _clean_text(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def build_row(raw: dict, ref: str, default_date: date | None = None) -> tuple[dict | None, str | None]:
    """Normalise one raw field->value dict. Returns (row, rejection_reason)."""
    row: dict = {"source_ref": ref}
    for f in FIELD_ALIASES:
        row[f] = raw.get(f)

    d = parse_date(row["shift_date"]) or default_date
    if d is None:
        return None, "missing or unreadable date"
    row["shift_date"] = d

    sh = normalize_shift(row["shift"])
    if sh is None:
        return None, f"unrecognised shift '{_clean_text(row['shift'])}'"
    row["shift"] = sh

    machine = _clean_text(row["machine"]).upper()
    if not machine:
        return None, "missing machine"
    row["machine"] = machine

    for f in NUMERIC_FIELDS:
        row[f] = parse_number(row[f])
    for f in ("product", "downtime_reason", "quality_issue", "notes", "operator"):
        row[f] = _clean_text(row[f])
    ms = _norm(_clean_text(row["maintenance_status"]))
    row["maintenance_status"] = MAINT_ALIASES.get(ms, "pending" if "pend" in ms else ms)
    return row, None


# ---------------------------------------------------------------- tabular

def _frame_to_rows(df: pd.DataFrame, label: str) -> ParseResult:
    res = ParseResult(kind="table")
    mapping: dict[str, str] = {}
    for col in df.columns:
        f = canonical_field(col)
        if f and f not in mapping.values():
            mapping[col] = f
    unmapped = [str(c) for c in df.columns if c not in mapping]
    if unmapped:
        res.notes.append(f"Ignored unrecognised columns: {', '.join(unmapped)}")
    missing = [f for f in ("shift_date", "shift", "machine") if f not in mapping.values()]
    if missing:
        res.notes.append(f"Missing required columns: {', '.join(missing)}")
    for i, (_, r) in enumerate(df.iterrows(), start=2):  # row 1 is the header
        raw = {mapping[c]: r[c] for c in mapping}
        if all(_clean_text(v) == "" for v in raw.values()):
            continue
        row, err = build_row(raw, f"{label} row {i}")
        if row:
            res.rows.append(row)
        else:
            res.rejected.append({"ref": f"{label} row {i}", "reason": err})
    return res


def parse_csv(data: bytes, label: str) -> ParseResult:
    df = pd.read_csv(io.BytesIO(data), dtype=object, keep_default_na=False)
    res = _frame_to_rows(df, label)
    res.kind = "csv"
    return res


def parse_excel(data: bytes, label: str) -> ParseResult:
    sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, dtype=object)
    out = ParseResult(kind="xlsx")
    for name, df in sheets.items():
        part = _frame_to_rows(df, f"{label}[{name}]")
        out.rows += part.rows
        out.rejected += part.rejected
        out.notes += part.notes
    return out


# ---------------------------------------------------------------- free text / PDF

_KV = re.compile(r"^\s*([A-Za-z][A-Za-z _()/.-]{1,40}?)\s*[:=\-]\s*(.+?)\s*$")


def parse_text(text: str, label: str, kind: str = "text") -> ParseResult:
    """Parse blocks of 'Key: value' lines. A new block starts on a repeated machine line
    or a blank-line gap followed by a Machine/Date line."""
    res = ParseResult(kind=kind)
    blocks: list[dict] = []
    cur: dict = {}
    carry: dict = {}  # date/shift stated once at top of page apply to following machines
    start_line = 1
    for ln, line in enumerate(text.splitlines(), start=1):
        m = _KV.match(line)
        if not m:
            continue
        f = canonical_field(m.group(1))
        if not f:
            continue
        val = m.group(2)
        if f == "machine" and "machine" in cur:
            blocks.append({"raw": cur, "line": start_line})
            cur = {}
            start_line = ln
        if not cur:
            start_line = ln
        if f in ("shift_date", "shift") and f in cur and cur.get("machine") is None:
            pass
        cur[f] = val
        if f in ("shift_date", "shift"):
            carry[f] = val
    if cur:
        blocks.append({"raw": cur, "line": start_line})

    for b in blocks:
        raw = {**{k: v for k, v in carry.items() if k not in b["raw"]}, **b["raw"]}
        row, err = build_row(raw, f"{label} line {b['line']}")
        if row:
            res.rows.append(row)
        else:
            res.rejected.append({"ref": f"{label} line {b['line']}", "reason": err})
    if not blocks:
        res.notes.append("No 'Key: value' report blocks were found in the text")
    return res


def parse_pdf(data: bytes, label: str) -> ParseResult:
    import pymupdf

    doc = pymupdf.open(stream=data, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    if not text.strip():
        r = ParseResult(kind="pdf")
        r.notes.append("PDF has no extractable text (scanned image?). OCR is not enabled in this version.")
        return r
    res = parse_text(text, label, kind="pdf")
    res.kind = "pdf"
    return res


def parse_upload(filename: str, data: bytes) -> ParseResult:
    name = filename.lower()
    if name.endswith(".csv"):
        return parse_csv(data, filename)
    if name.endswith((".xlsx", ".xlsm", ".xls")):
        return parse_excel(data, filename)
    if name.endswith(".pdf"):
        return parse_pdf(data, filename)
    if name.endswith((".txt", ".md", ".log")):
        return parse_text(data.decode("utf-8", errors="replace"), filename)
    raise ValueError(f"Unsupported file type: {filename}")
