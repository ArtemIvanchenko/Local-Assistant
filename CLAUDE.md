# Local Assistant — agent context

Fully-local, privacy-first AI secretary on a Raspberry Pi 5 (8GB), over Telegram.
Runtime data never leaves the device; this repo is **public** (code only).

## If you are setting this up on the Pi
Follow **[docs/pi-agent-runbook.md](docs/pi-agent-runbook.md)** step by step. That is
your primary instruction. Do deployment/hardware bring-up, not app rewrites.

## Key commands
```bash
source .venv/bin/activate
python -m local_assistant --check     # preflight: config, models, iCloud, DB
python -m local_assistant             # run the bot (foreground)
python -m pytest -q                   # tests (must pass; no Ollama needed)
ruff check src/ scripts/ tests/       # lint
python scripts/eval_run.py --model <tag>   # tool-selection accuracy for a model
```

## Layout
- `src/local_assistant/` — `config.py`, `assistant.py` (wiring), `agent/orchestrator.py`
  (streaming tool-loop), `llm/` (Ollama client + model catalogue), `memory/` (SQLite +
  sqlite-vec + MEMORY.md), `tools/registry.py` (+ MCP server), `telegram/bot.py`,
  `scheduler/jobs.py`, `integrations/icloud.py` (CalDAV/CardDAV), `observability.py`.
- `docs/` — architecture, setup-pi, integrations-apple, roadmap, this runbook.
- `deploy/systemd/` — service + backup timer templates.

## Conventions & safety
- **Never commit** `.env`, `data/`, `logs/`, `backups/`, `MEMORY.md`, `*.gguf` (gitignored).
- Config is env-driven (`.env`, see `config.py`) — no hard-coded models/paths/secrets.
- Model choice is runtime-switchable (`/model`, DB `settings` table); no weights in repo.
- Keep changes minimal; run `pytest` + `ruff` before committing. Commit per logical unit.
- iCloud/Ollama/Telegram failures must degrade gracefully, never crash the service.
