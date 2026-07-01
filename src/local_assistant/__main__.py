"""Entry point: assemble the assistant, register proactive jobs, run the bot.

Run with:  python -m local_assistant
Pre-flight only:  python -m local_assistant --check
"""

from __future__ import annotations

import sys

from .assistant import Assistant
from .config import settings
from .scheduler.jobs import register as register_jobs
from .telegram.bot import build_application


def _preflight() -> int:
    print("Local Assistant — pre-flight")
    deps = Assistant()
    print(f"  db          : {deps.db.path}  (sqlite-vec: {'on' if deps.db.vec_enabled else 'fallback'})")
    print(f"  main model  : {deps.llm.main_model}  (fallback {settings.model_main_fallback})")
    print(f"  router      : {settings.model_router}")
    print(f"  embeddings  : {settings.model_embed}")
    installed = deps.llm.list_installed()
    print(f"  ollama      : {settings.ollama_host}  ->  "
          f"{len(installed)} models installed" if installed else
          f"  ollama      : {settings.ollama_host}  ->  not reachable / no models")
    print(f"  icloud      : {'on (' + settings.apple_id + ')' if settings.icloud_enabled else 'off (local only)'}")
    print(f"  owners      : {settings.owner_ids or '⚠ none set'}")
    return 0


def main() -> int:
    if "--check" in sys.argv:
        return _preflight()

    if not settings.telegram_bot_token:
        print("⚠  TELEGRAM_BOT_TOKEN is not set. Copy .env.example -> .env first.")
        return 1
    if not settings.owner_ids:
        print("⚠  OWNER_CHAT_IDS is not set — refusing to start (the bot would answer strangers).")
        return 1

    deps = Assistant()
    app = build_application(deps)
    register_jobs(app, deps)
    print(f"Local Assistant running. Main model: {deps.llm.main_model}. Owners: {settings.owner_ids}")
    app.run_polling()
    return 0


if __name__ == "__main__":
    sys.exit(main())
