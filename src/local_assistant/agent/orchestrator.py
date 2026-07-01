"""The agent loop.

Assembles a frugal context (system prompt with current time + profile + retrieved
memory + recent turns), runs the main model with tools, executes any tool calls,
and loops until the model returns a plain answer. Keeps the working context small
(see WORKING_CONTEXT_BUDGET) and relies on retrieval rather than long context.
"""

from __future__ import annotations

import json
import time

from ..config import settings
from ..observability import log_metric
from ..util import now

MAX_TOOL_ITERS = 5

SYSTEM_TEMPLATE = """\
You are a personal assistant secretary running locally on the user's device.
Be concise, warm, and practical. Reply in the user's language (often Russian).

Current time: {now} ({tz}).
When a tool needs a datetime, resolve relative expressions (e.g. "завтра в 9") to
ISO8601 based on the current time above.

Use tools to manage the user's reminders, calendar, tasks, and memory, and to search
the web for current facts. Prefer searching memory before asking the user to repeat
something. Do not invent events or reminders.

What you know about the user (profile):
{profile}

Relevant memories:
{memories}
"""


class Orchestrator:
    def __init__(self, llm, memory, tools):
        self.llm = llm
        self.memory = memory
        self.tools = tools

    async def _system_prompt(self, user_text: str) -> str:
        profile = self.memory.read_profile() or "(empty)"
        hits = await self.memory.search(user_text, k=4)
        memories = "\n".join(f"- {h['content']}" for h in hits) or "(none)"
        return SYSTEM_TEMPLATE.format(
            now=now().strftime("%Y-%m-%d %H:%M"),
            tz=settings.timezone,
            profile=profile[:2000],
            memories=memories,
        )

    async def handle(self, user_text: str) -> str:
        """Non-streaming convenience wrapper (used by MCP / tests)."""
        final = ""
        async for partial in self.handle_stream(user_text):
            final = partial
        return final or "…"

    async def handle_stream(self, user_text: str):
        """Async-generate the growing answer text; the last value is the final reply."""
        self.memory.log_message("user", user_text)
        messages = [
            {"role": "system", "content": await self._system_prompt(user_text)},
            *self.memory.recent_messages(limit=10),
        ]
        specs = self.tools.specs()
        t0 = time.monotonic()
        tools_used: list[str] = []
        all_ok = True
        answer = ""

        for _ in range(MAX_TOOL_ITERS):
            content = ""
            tool_calls: list[dict] = []
            async for chunk in self.llm.stream_chat(messages, tools=specs):
                msg = chunk.get("message", {})
                if msg.get("content"):
                    content += msg["content"]
                    yield content
                if msg.get("tool_calls"):
                    tool_calls.extend(msg["tool_calls"])

            assistant_msg: dict = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            messages.append(assistant_msg)

            if not tool_calls:
                answer = content.strip() or "…"
                break

            for call in tool_calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                result = await self.tools.call(name, args)
                tools_used.append(name)
                all_ok = all_ok and not result.startswith("error")
                messages.append({"role": "tool", "name": name, "content": result})
        else:
            answer = "Не смог завершить действие за разумное число шагов."
            yield answer

        self.memory.log_message("assistant", answer)
        log_metric(
            self.memory.db, model=self.llm.main_model,
            latency_ms=int((time.monotonic() - t0) * 1000),
            tool_called=",".join(tools_used),
            tool_success=(all_ok if tools_used else None),
        )
