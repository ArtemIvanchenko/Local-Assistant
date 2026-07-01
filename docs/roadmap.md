# Roadmap

A functional MVP is implemented (clone → install → `.env` → run). Remaining items are
hardware tuning and polish, done when the Pi is set up.

| Phase | Goal | Status |
|---|---|---|
| 0 | Repo scaffold: `.gitignore`, README, structure, packaging, pre-commit | ✅ done |
| 1 | Base: OS, recent Ollama, pull models, cooling/overclock/SSD, verify t/s | ☐ on Pi |
| 2 | Telegram loop: chat with history; chat_id whitelist + `.env` secrets | ✅ done |
| 3 | Memory: SQLite + sqlite-vec + MEMORY.md; semantic search; MCP server | ✅ done |
| 4 | Schedule: events/reminders/tasks CRUD as tools; NL → DB | ✅ done |
| 5 | Scheduler: reminder firing; morning/evening digest | ✅ done |
| 6 | Proactivity/patterns: nightly reflection | ✅ basic |
| 7 | Capabilities: web search (`ddgs`), document ingestion (RAG) | ✅ done |
| 7b | Apple: iCloud Calendar + Reminders (CalDAV) + Contacts (CardDAV) | ✅ done |
| 8 | UX: slash commands, model selection, inline snooze buttons, response streaming | ✅ done |
| 9 | Polish/reliability: speculative decoding (docs), anti-spam cap, backup timer, watchdog, eval+metrics | ✅ done |
| 10 | (Later) Voice (faster-whisper or Gemma 4 E4B audio), AI HAT+ 2, contacts write, iCloud Mail | ☐ later |

Develop on feature branches; commit per phase; `main` protected.
