# Roadmap

| Phase | Goal | Status |
|---|---|---|
| 0 | Repo scaffold: `.gitignore`, README, structure, packaging, pre-commit | ✅ done |
| 1 | Base: OS, recent Ollama, pull models, cooling/overclock/SSD, verify t/s + tool-calling | ☐ |
| 2 | Telegram loop: echo → Qwen3.5-4B chat with history; chat_id whitelist + `.env` secrets | ☐ |
| 3 | Memory + MCP: SQLite + sqlite-vec + MEMORY.md; memory tools as MCP; semantic search | ☐ |
| 4 | Schedule: events/reminders/tasks CRUD as MCP tools; NL → DB | ☐ |
| 5 | Scheduler: APScheduler; reminder firing; morning/evening digest | ☐ |
| 6 | Proactivity/patterns: nightly reflection, `patterns`, memory consolidation | ☐ |
| 7 | Capabilities: web search (`ddgs`), document ingestion (RAG) | ☐ |
| 8 | UX: slash commands, inline buttons, snooze, streaming | ☐ |
| 9 | Polish/reliability: router + speculative decoding, anti-spam, backups, encryption, watchdog, eval+logs | ☐ |
| 10 | (Later) Voice (faster-whisper or Gemma 4 E4B audio), AI HAT+ 2 | ☐ |

Develop on feature branches; commit per phase; `main` protected.
