# AI usage log

Record every day: the prompt, what the AI suggested, what failed, what you decided and changed.
Day 1 below was written from the actual build session; continue days 2-5 yourself.

## Day 1 — 2026-11-03: scaffold, parsers, rules, API, UI

### Prompt
Project brief for ShiftMind (shift intelligence, five features, stack, repo layout, "you can add more
features"). Asked the AI assistant to build the whole repository.

### What the AI suggested
- Rule engine for anomalies, LLM optional and used only for wording (matches the brief's guidance).
- Parser with header aliases instead of asking an LLM to read every file.
- Q&A as filter + keyword retrieval + Python-computed totals, with numbered sources.
- Extras beyond the brief: missing-report detection, repeat-failure rule, trends charts, tickable
  handover actions, pasted-text upload, numeric grounding guard on LLM output.

### Problems found and fixed during the session
| Issue | How it showed up | Fix |
| --- | --- | --- |
| Shift status logic was convoluted (`worst` variable with mixed `or`/`and`) | Code review while writing | Replaced with one `any(...)` over critical/warning flags |
| Repeat-failure condition was unreadable (`+ 0`, redundant comparisons) | Code review | Reduced to `len(same) + 1 >= repeat_count` |
| Formatting a possibly-`None` number with `:g` would raise | Code review of `_describe` | Guarded each value explicitly |
| `datetime.utcnow()` deprecation warnings in tests | pytest output | Timezone-aware default, naive UTC stored |
| **False positive:** routine "Changeover" stops flagged as a critical repeat failure, ranking above the real M-102 maintenance item | Live smoke test of the night handover (all 25 unit tests had passed) | Repeat rule now ignores routine reasons (changeover, cleaning, setup...) and stops under 30 min; regression test added |
| **Wrong data:** the night report listed M-105 as missing although it had reported (the evening miss leaked into every shift of that day) | Same smoke test | `shift_facts` filters missing reports to the shift being viewed; regression test added |

Lesson: unit tests were green while two user-visible behaviours were wrong. The end-to-end run against
the sample data is what exposed them, so keep the acceptance checks in `Final directive.md` as tests.

### Verification
- `pytest -q`: 28 passed (parsers incl. PDF/Excel, rule thresholds, API end-to-end, offline).
- Live server run: uploaded all four sample files over HTTP, checked night report, handover order and a Q&A call.
- `vite build` succeeds.

### My decisions (edit this)
- ...

## Day 2
## Day 3
## Day 4
## Day 5
