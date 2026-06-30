"""Wires the components together and exposes them as one `deps` object."""

from __future__ import annotations

from .agent.orchestrator import Orchestrator
from .db.database import Database
from .llm.client import LlmClient
from .memory.store import MemoryStore
from .tools.registry import ToolRegistry


class Assistant:
    def __init__(self):
        self.db = Database()
        self.llm = LlmClient(self.db)
        self.memory = MemoryStore(self.db, self.llm)
        self.tools = ToolRegistry(self.db, self.memory)
        self.orchestrator = Orchestrator(self.llm, self.memory, self.tools)

    async def reflect(self) -> None:
        """Nightly: summarise recent activity into an observation + light consolidation."""
        msgs = self.memory.recent_messages(limit=40)
        if not msgs:
            return
        convo = "\n".join(f"{m['role']}: {m['content']}" for m in msgs)
        prompt = [
            {"role": "system", "content":
             "Summarise the user's recent activity in 1-2 sentences and note any "
             "recurring pattern worth remembering. Reply with just the observation."},
            {"role": "user", "content": convo[:4000]},
        ]
        try:
            resp = await self.llm.chat(prompt, tools=None)
            text = (resp.get("message", {}).get("content") or "").strip()
            if text:
                await self.memory.remember(text, mtype="observation", confidence=0.4)
        except Exception:
            pass
