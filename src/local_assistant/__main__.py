"""Entry point.

Phase 0 scaffold: validates config and prints a startup summary. Wiring of the
Telegram loop, orchestrator, memory, scheduler and tools lands in later phases
(see docs/roadmap.md).
"""

from __future__ import annotations

import sys

from .config import settings


def main() -> int:
    if not settings.telegram_bot_token:
        print("⚠  TELEGRAM_BOT_TOKEN is not set. Copy .env.example -> .env first.")
        return 1
    if not settings.owner_ids:
        print("⚠  OWNER_CHAT_IDS is not set — the bot would answer strangers. Refusing to start.")
        return 1

    print("Local Assistant — scaffold OK")
    print(f"  main model : {settings.model_main} (fallback {settings.model_main_fallback})")
    print(f"  router     : {settings.model_router}")
    print(f"  embeddings : {settings.model_embed}")
    print(f"  ctx        : {settings.num_ctx} (working budget {settings.working_context_budget})")
    print(f"  owners     : {settings.owner_ids}")
    print("  TODO: start Telegram loop (phase 2).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
