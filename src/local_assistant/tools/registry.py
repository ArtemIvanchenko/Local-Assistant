"""Agent tools: calendar / reminders / tasks / memory / web search.

Defined once here with Ollama-compatible JSON schemas and executed by the
orchestrator. The same registry is re-exported as an MCP server (mcp_server.py) so
other clients can use the tools later.
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from ..config import settings
from ..util import now, parse_when


class ToolRegistry:
    def __init__(self, db, memory):
        self.db = db
        self.memory = memory
        self._handlers: dict[str, Callable[..., Awaitable[str]]] = {
            "add_reminder": self.add_reminder,
            "list_reminders": self.list_reminders,
            "add_event": self.add_event,
            "list_events": self.list_events,
            "add_task": self.add_task,
            "complete_task": self.complete_task,
            "list_tasks": self.list_tasks,
            "remember": self.remember,
            "search_memory": self.search_memory,
            "web_search": self.web_search,
        }

    # ── dispatch ─────────────────────────────────────────────
    async def call(self, name: str, args: dict[str, Any]) -> str:
        handler = self._handlers.get(name)
        if handler is None:
            return f"error: unknown tool {name}"
        try:
            return await handler(**args)
        except Exception as e:  # surface to the model rather than crash the turn
            return f"error: {type(e).__name__}: {e}"

    # ── reminders ────────────────────────────────────────────
    async def add_reminder(self, text: str, when: str) -> str:
        fire = parse_when(when)
        self.db.execute(
            "INSERT INTO reminders(text, fire_at) VALUES(?, ?)",
            (text, fire.isoformat()),
        )
        return f"reminder set for {fire.strftime('%Y-%m-%d %H:%M')}: {text}"

    async def list_reminders(self) -> str:
        rows = self.db.query(
            "SELECT text, fire_at FROM reminders WHERE status='pending' ORDER BY fire_at"
        )
        if not rows:
            return "no pending reminders"
        return "\n".join(f"• {r['fire_at']} — {r['text']}" for r in rows)

    # ── events ───────────────────────────────────────────────
    async def add_event(self, title: str, start: str, end: str | None = None,
                        notes: str | None = None) -> str:
        s = parse_when(start)
        e = parse_when(end).isoformat() if end else None
        self.db.execute(
            "INSERT INTO events(title, start_ts, end_ts, notes) VALUES(?,?,?,?)",
            (title, s.isoformat(), e, notes),
        )
        return f"event added: {title} @ {s.strftime('%Y-%m-%d %H:%M')}"

    async def list_events(self, day: str | None = None) -> str:
        if day:
            d = parse_when(day).date().isoformat()
            rows = self.db.query(
                "SELECT title, start_ts FROM events WHERE date(start_ts)=? ORDER BY start_ts",
                (d,),
            )
        else:
            rows = self.db.query(
                "SELECT title, start_ts FROM events WHERE start_ts>=? ORDER BY start_ts LIMIT 20",
                (now().isoformat(),),
            )
        if not rows:
            return "no events"
        return "\n".join(f"• {r['start_ts']} — {r['title']}" for r in rows)

    # ── tasks ────────────────────────────────────────────────
    async def add_task(self, title: str, due: str | None = None, priority: int = 0) -> str:
        due_ts = parse_when(due).isoformat() if due else None
        self.db.execute(
            "INSERT INTO tasks(title, due_ts, priority) VALUES(?,?,?)",
            (title, due_ts, priority),
        )
        return f"task added: {title}"

    async def complete_task(self, title: str) -> str:
        cur = self.db.execute(
            "UPDATE tasks SET status='done' WHERE status='open' AND title LIKE ?",
            (f"%{title}%",),
        )
        return "task completed" if cur.rowcount else "no matching open task"

    async def list_tasks(self) -> str:
        rows = self.db.query(
            "SELECT title, due_ts FROM tasks WHERE status='open' ORDER BY priority DESC, due_ts"
        )
        if not rows:
            return "no open tasks"
        return "\n".join(f"• {r['title']}" + (f" (due {r['due_ts']})" if r["due_ts"] else "")
                         for r in rows)

    # ── memory ───────────────────────────────────────────────
    async def remember(self, content: str) -> str:
        await self.memory.remember(content, mtype="user")
        return "remembered"

    async def search_memory(self, query: str) -> str:
        hits = await self.memory.search(query, k=5)
        if not hits:
            return "nothing relevant in memory"
        return "\n".join(f"• {h['content']}" for h in hits)

    # ── web search (ddgs) ────────────────────────────────────
    async def web_search(self, query: str) -> str:
        def _search() -> str:
            from ddgs import DDGS  # noqa: PLC0415

            with DDGS() as ddgs:
                results = list(ddgs.text(
                    query, region=settings.search_region,
                    max_results=settings.search_max_results,
                ))
            if not results:
                return "no results"
            return "\n".join(
                f"• {r.get('title')}: {r.get('body', '')[:200]} ({r.get('href')})"
                for r in results
            )

        return await asyncio.to_thread(_search)

    # ── schemas for Ollama tool-calling ──────────────────────
    def specs(self) -> list[dict]:
        def fn(name, desc, props, required):
            return {
                "type": "function",
                "function": {
                    "name": name,
                    "description": desc,
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": required,
                    },
                },
            }

        S = {"type": "string"}
        return [
            fn("add_reminder", "Set a reminder at a specific time.",
               {"text": S, "when": {"type": "string", "description": "ISO8601 datetime"}},
               ["text", "when"]),
            fn("list_reminders", "List pending reminders.", {}, []),
            fn("add_event", "Add a calendar event.",
               {"title": S, "start": {"type": "string", "description": "ISO8601"},
                "end": S, "notes": S}, ["title", "start"]),
            fn("list_events", "List upcoming events, or events on a given day.",
               {"day": {"type": "string", "description": "ISO date, optional"}}, []),
            fn("add_task", "Add a to-do task.",
               {"title": S, "due": S, "priority": {"type": "integer"}}, ["title"]),
            fn("complete_task", "Mark a task done by (partial) title.", {"title": S}, ["title"]),
            fn("list_tasks", "List open tasks.", {}, []),
            fn("remember", "Store a durable fact about the user.", {"content": S}, ["content"]),
            fn("search_memory", "Search the user's memory semantically.", {"query": S}, ["query"]),
            fn("web_search", "Search the web for current information.", {"query": S}, ["query"]),
        ]
