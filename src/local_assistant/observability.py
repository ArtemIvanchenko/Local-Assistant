"""Lightweight metrics: a row in SQLite + a line in metrics.jsonl per handled turn.

Used to compare models (latency, tool-call success) and spot regressions.
"""

from __future__ import annotations

import json
from pathlib import Path

from .util import now

_JSONL = Path("logs/metrics.jsonl")


def log_metric(db, *, model: str, latency_ms: int, intent: str = "",
               tool_called: str = "", tool_success: bool | None = None) -> None:
    try:
        db.execute(
            "INSERT INTO metrics(intent, model, latency_ms, tool_called, tool_success) "
            "VALUES(?,?,?,?,?)",
            (intent, model, latency_ms, tool_called,
             None if tool_success is None else int(tool_success)),
        )
    except Exception:
        pass
    try:
        _JSONL.parent.mkdir(parents=True, exist_ok=True)
        with _JSONL.open("a") as f:
            f.write(json.dumps({
                "ts": now().isoformat(), "model": model, "latency_ms": latency_ms,
                "intent": intent, "tool_called": tool_called, "tool_success": tool_success,
            }) + "\n")
    except Exception:
        pass
