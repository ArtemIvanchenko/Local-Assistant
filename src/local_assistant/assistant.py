"""Wires the components together and exposes them as one `deps` object."""

from __future__ import annotations

import asyncio

from .agent.orchestrator import Orchestrator
from .config import settings
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

    async def sync_icloud(self) -> None:
        """Pull iCloud events + reminders into the local cache (dedupe by ext_id)."""
        if not settings.icloud_enabled:
            return
        from .integrations.icloud import calendar

        cal = calendar()
        events = await asyncio.to_thread(cal.list_events)
        for ev in events:
            if not ev["uid"]:
                continue
            exists = self.db.query_one("SELECT 1 FROM events WHERE ext_id=?", (ev["uid"],))
            if exists:
                self.db.execute(
                    "UPDATE events SET title=?, start_ts=? WHERE ext_id=?",
                    (ev["title"], ev["start"], ev["uid"]),
                )
            else:
                self.db.execute(
                    "INSERT INTO events(title, start_ts, source, ext_id) VALUES(?,?, 'icloud', ?)",
                    (ev["title"], ev["start"], ev["uid"]),
                )
        reminders = await asyncio.to_thread(cal.list_reminders)
        for rm in reminders:
            if not rm["uid"] or not rm["due"]:
                continue
            exists = self.db.query_one("SELECT 1 FROM reminders WHERE ext_id=?", (rm["uid"],))
            if not exists:
                self.db.execute(
                    "INSERT INTO reminders(text, fire_at, source, ext_id) "
                    "VALUES(?,?, 'icloud', ?)",
                    (rm["text"], rm["due"], rm["uid"]),
                )

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
