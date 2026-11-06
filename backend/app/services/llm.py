"""Thin, optional LLM wrapper.

ShiftMind works without any API key: every caller must handle `None` and fall
back to deterministic text. When ANTHROPIC_API_KEY is set the model is only
used to phrase narratives and answer questions over *supplied* records.
"""
from __future__ import annotations

import json
import os
import re

MODEL = os.getenv("SHIFTMIND_MODEL", "claude-sonnet-5-5")


def llm_available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def complete(system: str, user: str, max_tokens: int = 700) -> str | None:
    if not llm_available():
        return None
    try:
        import anthropic

        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=MODEL, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip() or None
    except Exception:  # network, quota, bad key: degrade gracefully
        return None


def complete_json(system: str, user: str, max_tokens: int = 900) -> dict | None:
    out = complete(system + "\nRespond with a single JSON object and nothing else.", user, max_tokens)
    if not out:
        return None
    m = re.search(r"\{.*\}", out, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


_NUM = re.compile(r"\d+(?:\.\d+)?")


def numbers_grounded(text: str, allowed_text: str) -> bool:
    """Guardrail: every number in the LLM output must appear in the facts we supplied."""
    allowed = set(_NUM.findall(allowed_text))
    return all(n in allowed for n in _NUM.findall(text))
