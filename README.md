# Local Assistant

A fully-local, privacy-first AI secretary that runs on a **Raspberry Pi 5 (8GB)** and
talks to you over **Telegram**. It has its own long-term memory, helps with your
schedule and reminders, behaves proactively (daily digests, gentle pattern
observations), and tracks medium/long-term patterns — all **on-device**.

> **Privacy model:** this repository is public — the **code** is open, but the
> **runtime data** (memory, schedule, conversation history) **never leaves the Pi**.
> All personal data is `.gitignore`d. See [`docs/architecture.md`](docs/architecture.md).

---

## Why local

- No cloud API, no per-token cost, works offline.
- Your conversations, schedule, and the assistant's memory stay on your hardware.
- Tunable proactivity instead of a passive chatbot.

The trade-off: a 4B model on the Pi 5 CPU runs at single-digit tokens/sec, so the
design leans on a small router model, speculative decoding, response streaming, and
nightly batch analysis rather than raw throughput.

## Stack

| Layer | Choice |
|---|---|
| Inference | [Ollama](https://ollama.com) (llama.cpp under the hood) |
| Main model | **Qwen3.5-4B** (fallback: Qwen3-4B-Instruct-2507) |
| Router model | **Qwen3-1.7B** |
| Embeddings | **embeddinggemma:300m** |
| Bot | [python-telegram-bot](https://python-telegram-bot.org) |
| Structured memory | SQLite |
| Semantic memory / RAG | [sqlite-vec](https://github.com/asg017/sqlite-vec) |
| Profile memory | `MEMORY.md` (markdown, agent-maintained) |
| Scheduler / proactivity | [APScheduler](https://apscheduler.readthedocs.io) |
| Private web search | [`ddgs`](https://pypi.org/project/ddgs/) (library, no service) |
| Apple integration | iCloud CalDAV (calendar + reminders) / CardDAV (contacts) — optional |
| Tool layer | [MCP](https://modelcontextprotocol.io) |
| Service mgmt | systemd (+ watchdog) — **Docker-free** |

See the full design rationale, model comparison, and inference-speedup notes in
[`docs/architecture.md`](docs/architecture.md).

## Quick start (Raspberry Pi 5)

> Detailed setup lives in [`docs/setup-pi.md`](docs/setup-pi.md). Short version:

```bash
# 1. System deps + Ollama (use the latest — Qwen3.5 needs recent llama.cpp ops)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3.5:4b
ollama pull qwen3:1.7b
ollama pull embeddinggemma:300m

# 2. Project
git clone https://github.com/ArtemIvanchenko/Local-Assistant.git
cd Local-Assistant
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e .

# 3. Config
cp .env.example .env        # fill in TELEGRAM_BOT_TOKEN + OWNER_CHAT_IDS

# 4. Sanity-check config + model availability, then run
python -m local_assistant --check
python -m local_assistant
```

## Choosing a model

Model choice is first-class — nothing is hard-coded and **no weights live in this repo**
(they're pulled by Ollama).

- **At install:** set `MODEL_MAIN` / `MODEL_ROUTER` / `MODEL_EMBED` in `.env`.
- **At runtime, from Telegram:**
  - `/models` — see the curated catalogue (main / router / embed), which are installed
    (✅) vs need `ollama pull` (⬇️), and which is active (⭐).
  - `/model <name>` — switch the active main model instantly (persists across restarts).

The catalogue lives in [`src/local_assistant/llm/models.py`](src/local_assistant/llm/models.py)
(Qwen3.5-4B, Qwen3-4B-Instruct, Phi-4-mini, Gemma 3, Llama 3.2, …). Any model installed
in Ollama can be selected, listed or not.

## Apple integration (optional)

Sync with **Apple Calendar, Reminders and Contacts** via iCloud (works from Linux
using CalDAV/CardDAV + an app-specific password). iCloud becomes the source of truth;
the local DB caches for offline/fast digests. Set `APPLE_ID` + `APPLE_APP_PASSWORD` in
`.env` — or leave blank to stay fully local. Full guide:
[`docs/integrations-apple.md`](docs/integrations-apple.md).

## Roadmap

Implementation is phased — see [`docs/roadmap.md`](docs/roadmap.md). Status: **functional MVP**
(chat, memory, schedule, tools, proactivity, model selection). Hardware tuning is done when
you set up the Pi.

## License

MIT — see [`LICENSE`](LICENSE).
