#!/usr/bin/env python
"""Run the eval set against the current main model and report tool-selection accuracy.

Requires Ollama running with the models pulled. Usage:
    python scripts/eval_run.py [--model qwen3:4b-instruct]

For each case it feeds the input to the agent, records which tool the model chose,
and compares with `expect_tool`. Prints per-case pass/fail, accuracy, and latency.
Use it to pick between models objectively (e.g. Qwen3.5 vs the fallback).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from local_assistant.assistant import Assistant

EVAL = Path(__file__).resolve().parent.parent / "tests" / "eval" / "eval_set.jsonl"


async def run(model: str | None):
    a = Assistant()
    if model:
        a.llm.set_main_model(model)
    print(f"model: {a.llm.main_model}\n")

    # Wrap tool dispatch to capture the first tool the model calls.
    captured: list[str] = []
    orig_call = a.tools.call

    async def spy(name, args):
        captured.append(name)
        return await orig_call(name, args)

    a.tools.call = spy

    passed, total, latencies = 0, 0, []
    for line in EVAL.read_text().splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        captured.clear()
        t0 = time.monotonic()
        try:
            await a.orchestrator.handle(case["input"])
        except Exception as e:
            print(f"  ERROR {case['id']}: {e}")
            total += 1
            continue
        latencies.append((time.monotonic() - t0) * 1000)
        got = captured[0] if captured else None
        want = case["expect_tool"]
        ok = got == want
        passed += ok
        total += 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {case['id']:16} want={want} got={got}")

    acc = passed / total * 100 if total else 0
    avg = sum(latencies) / len(latencies) if latencies else 0
    print(f"\naccuracy: {passed}/{total} ({acc:.0f}%)   avg latency: {avg:.0f} ms")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None)
    asyncio.run(run(ap.parse_args().model))
