"""Expose the assistant's tools as an MCP server.

Lets other MCP clients reuse the same calendar/memory/search tools. Optional — the
Telegram bot uses the registry directly and does not need this running.

Run:  python -m local_assistant.tools.mcp_server
"""

from __future__ import annotations


def build_server():
    from mcp.server.fastmcp import FastMCP

    from ..assistant import Assistant

    deps = Assistant()
    reg = deps.tools
    mcp = FastMCP("local-assistant")

    @mcp.tool()
    async def add_reminder(text: str, when: str) -> str:
        """Set a reminder at an ISO8601 datetime."""
        return await reg.add_reminder(text=text, when=when)

    @mcp.tool()
    async def add_event(title: str, start: str, end: str = "", notes: str = "") -> str:
        """Add a calendar event (ISO8601 start)."""
        return await reg.add_event(title=title, start=start, end=end or None, notes=notes or None)

    @mcp.tool()
    async def add_task(title: str, due: str = "", priority: int = 0) -> str:
        """Add a to-do task."""
        return await reg.add_task(title=title, due=due or None, priority=priority)

    @mcp.tool()
    async def search_memory(query: str) -> str:
        """Search the user's memory semantically."""
        return await reg.search_memory(query=query)

    @mcp.tool()
    async def web_search(query: str) -> str:
        """Search the web for current information."""
        return await reg.web_search(query=query)

    return mcp


if __name__ == "__main__":
    build_server().run()
