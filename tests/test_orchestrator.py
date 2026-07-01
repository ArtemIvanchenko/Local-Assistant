"""Offline test of the streaming tool-calling loop with a scripted fake LLM."""

import asyncio

from local_assistant.agent.orchestrator import Orchestrator
from local_assistant.db.database import Database
from local_assistant.memory.store import MemoryStore
from local_assistant.tools.registry import ToolRegistry


class FakeLLM:
    """Yields scripted turns; each turn is a list of chunk dicts."""

    def __init__(self, turns):
        self.turns = list(turns)
        self.main_model = "fake"

    async def embed(self, text):
        return [0.0] * 768

    async def stream_chat(self, messages, model=None, tools=None):
        for chunk in self.turns.pop(0):
            yield chunk


def _content(text):
    return {"message": {"content": text}}


def _tool(name, args):
    return {"message": {"content": "", "tool_calls": [{"function": {"name": name, "arguments": args}}]}}


def _build(tmp_path, turns):
    db = Database(str(tmp_path / "t.db"))
    llm = FakeLLM(turns)
    mem = MemoryStore(db, llm)
    return Orchestrator(llm, mem, ToolRegistry(db, mem)), db


def test_plain_answer_streams_and_concatenates(tmp_path):
    orch, _ = _build(tmp_path, [[_content("При"), _content("вет")]])  # streamed deltas
    out = asyncio.run(orch.handle("hi"))
    assert out == "Привет"


def test_tool_call_then_answer(tmp_path):
    turns = [
        [_tool("add_task", {"title": "купить хлеб"})],
        [_content("Добавил задачу.")],
    ]
    orch, db = _build(tmp_path, turns)
    out = asyncio.run(orch.handle("добавь задачу купить хлеб"))
    assert out == "Добавил задачу."
    row = db.query_one("SELECT title FROM tasks WHERE status='open'")
    assert row and "хлеб" in row["title"]


def test_metric_logged(tmp_path):
    orch, db = _build(tmp_path, [[_content("ok")]])
    asyncio.run(orch.handle("hi"))
    assert db.query_one("SELECT COUNT(*) c FROM metrics")["c"] == 1
