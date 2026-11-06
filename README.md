# ShiftMind — AI-Powered Industrial Shift Intelligence

ShiftMind turns scattered shift records (Excel, CSV, PDF, typed notes) into structured operational
intelligence: what happened, what went wrong, and what the incoming shift must act on.

> **Design rule:** numbers and anomaly flags come from deterministic code. The LLM, if enabled, only
> rephrases narratives and answers over supplied records, and its output is discarded if it contains a
> number that is not in the facts. ShiftMind never decides that a machine is safe to run.

## Features

| Feature | How it works |
| --- | --- |
| Smart log upload | CSV, Excel (multi-sheet), PDF, `.txt`, pasted text. Flexible header matching, unit handling (`1.5 hrs` → 90 min), shift aliases. Unreadable rows are listed as rejected, never guessed. |
| Anomaly detection | 15 per-record rules (shortfall, overproduction, downtime, reject rate, quality issue, impossible/negative values, missing fields, maintenance pending, repeat failures, z-score outliers vs. the machine's own history, raw-material per-unit deviation) plus missing-report detection across machines. Every flag shows its evidence. |
| AI shift summary | Facts are computed in SQL/Python. Narrative is rule-based by default, LLM-written when `ANTHROPIC_API_KEY` is set (with a numeric grounding check). |
| Handover intelligence | Prioritised checklist (high/medium/low) for the incoming shift, each item with its reason and source record. Items can be ticked off. |
| Ask ShiftMind | Parses machine/shift/date/topic from the question, retrieves matching records, computes totals in Python, answers with numbered sources pointing to the original file and row. |
| Extras | Trends charts, missing-report detection, source row for every record, reset endpoint for demos. |

## Quick start (no Docker)

```bash
# 1. Backend (SQLite by default)
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload            # http://localhost:8000/docs

# 2. Frontend
cd frontend
npm install
npm run dev                              # http://localhost:5173

# 3. Load the demo data: open "Upload logs" and drop the four files from sample_data/
```

Optional AI narration: `export ANTHROPIC_API_KEY=...` before starting the backend
(`SHIFTMIND_MODEL` overrides the model name).

## Docker (PostgreSQL)

```bash
docker compose up --build
# app: http://localhost:8080   api docs: http://localhost:8000/docs
```

## Demo script (2 minutes)

1. Upload `history_week.csv`, `daily_report_morning.xlsx`, `evening_notes.txt`, `night_report.pdf`.
2. **Shift report** → pick `2026-11-02 · Night`: M-102 down 240 min, M-104 rejects spiking; the handover
   list puts the M-102 inspection first.
3. **Anomalies** → filter Critical: the M-103 "900 min downtime" is flagged as a data-entry error, and
   M-102 motor overheating as a repeat failure.
4. Pick `2026-11-02 · Evening`: M-105's missing report is detected.
5. **Ask ShiftMind** → "Why was M-102 down in the last week?" and open the sources.

The sample data is synthetic with planted problems (see `sample_data/generate_samples.py`).

## Tests

```bash
cd backend && pytest -q        # 28 tests: parsers, anomaly rules, API end-to-end (offline)
```

## Layout

```
backend/app/models      SQLAlchemy entities (documents, shift records, anomalies, handover actions)
backend/app/services    parser, anomaly, summary (+handover), qa, llm
backend/app/main.py     FastAPI routes
backend/tests           pytest suite
frontend/src            React + Tailwind + Recharts dashboard
sample_data             synthetic logs + generator
docs                    intent, final directive, write-up, AI usage log
```

## Known limits (v0.1)

- No authentication or multi-plant tenancy yet.
- Scanned/handwritten PDFs need OCR (not included); typed PDFs with `Key: value` lines work.
- Q&A retrieval is keyword/filter based, not embeddings; fine for hundreds of thousands of rows,
  but vague questions retrieve less precisely.
- Thresholds are global constants in `services/anomaly.py`; per-machine tuning is future work.
