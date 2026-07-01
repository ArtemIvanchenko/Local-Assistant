"""Ollama client wrapper with runtime model selection.

The *active main model* lives in the DB settings table (key `active_main_model`),
so it can be switched at runtime via /model without restarting. Config provides the
default. If the main model errors, we fall back to MODEL_MAIN_FALLBACK once.
"""

from __future__ import annotations

import asyncio
from typing import Any

from ..config import settings

ACTIVE_MODEL_KEY = "active_main_model"


class LlmClient:
    def __init__(self, db=None):
        self.db = db
        self._client = None  # lazy: don't require ollama installed to import

    def _ollama(self):
        if self._client is None:
            import ollama  # noqa: PLC0415

            self._client = ollama.Client(host=settings.ollama_host)
        return self._client

    # ── model selection ──────────────────────────────────────
    @property
    def main_model(self) -> str:
        if self.db is not None:
            return self.db.get_setting(ACTIVE_MODEL_KEY, settings.model_main)
        return settings.model_main

    def set_main_model(self, name: str) -> None:
        if self.db is not None:
            self.db.set_setting(ACTIVE_MODEL_KEY, name)

    def list_installed(self) -> list[str]:
        try:
            data = self._ollama().list()
            return sorted(m.get("model") or m.get("name") for m in data.get("models", []))
        except Exception:
            return []

    def is_installed(self, name: str) -> bool:
        installed = self.list_installed()
        return any(n == name or n.startswith(name + ":") for n in installed)

    def _options(self) -> dict[str, Any]:
        return {"num_ctx": settings.num_ctx, "num_thread": settings.num_threads}

    # ── inference (sync core, async wrappers) ────────────────
    def _chat_sync(self, messages, model=None, tools=None) -> dict:
        model = model or self.main_model
        try:
            return self._ollama().chat(
                model=model, messages=messages, tools=tools, options=self._options()
            )
        except Exception:
            if model != settings.model_main_fallback:
                return self._ollama().chat(
                    model=settings.model_main_fallback,
                    messages=messages,
                    tools=tools,
                    options=self._options(),
                )
            raise

    async def chat(self, messages, model=None, tools=None) -> dict:
        return await asyncio.to_thread(self._chat_sync, messages, model, tools)

    async def route(self, messages) -> dict:
        """Fast path on the small router model (no tools)."""
        return await asyncio.to_thread(self._chat_sync, messages, settings.model_router, None)

    def _embed_sync(self, text: str) -> list[float]:
        resp = self._ollama().embed(model=settings.model_embed, input=text)
        embs = resp.get("embeddings") or [resp.get("embedding")]
        return embs[0]

    async def embed(self, text: str) -> list[float]:
        return await asyncio.to_thread(self._embed_sync, text)

    # ── streaming ────────────────────────────────────────────
    async def stream_chat(self, messages, model=None, tools=None):
        """Async-yield Ollama chunks by draining the blocking iterator in a thread.

        High value on the Pi: at 5-8 tok/s the user sees words appear instead of
        waiting for the whole reply.
        """
        model = model or self.main_model
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        _DONE = object()

        def produce():
            try:
                for chunk in self._ollama().chat(
                    model=model, messages=messages, tools=tools,
                    stream=True, options=self._options(),
                ):
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
            except Exception as e:  # surfaced to the consumer
                loop.call_soon_threadsafe(queue.put_nowait, e)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, _DONE)

        task = loop.run_in_executor(None, produce)
        while True:
            item = await queue.get()
            if item is _DONE:
                break
            if isinstance(item, Exception):
                raise item
            yield item
        await task
