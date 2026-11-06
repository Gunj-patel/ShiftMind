# Final directive

Build ShiftMind as an industrial software product, not a chatbot that summarises spreadsheets.

## Must demonstrate
- [x] Messy operational documents (CSV, Excel with odd headers/units, PDF, typed notes) become structured records.
- [x] Numerical validation finds inconsistencies (impossible downtime, rejects > output, negatives, missing fields, outliers).
- [x] Actionable handover reports with priorities, reasons and source records.
- [x] Question answering over historical records with visible sources.
- [x] Deterministic rules for numbers, AI only for wording and retrieval-grounded answers.

## Acceptance checks
1. Upload the four files in `sample_data/` → 119 records, 0 rejected.
2. Night shift of 2026-11-02: M-102 maintenance action is the first high-priority handover item.
3. M-103's 900-minute downtime is flagged `impossible_downtime` (critical).
4. Evening 2026-11-02 reports M-105 as missing.
5. "Why was M-102 down in the last week?" returns sources that include the motor-overheating records.
6. With `ANTHROPIC_API_KEY` unset the whole app and test suite work offline.

## Constraints
Stack: React + Tailwind + Recharts, FastAPI, SQLAlchemy (SQLite dev / PostgreSQL in Docker),
pandas/openpyxl/PyMuPDF. LLM access is optional and isolated in `services/llm.py`.
