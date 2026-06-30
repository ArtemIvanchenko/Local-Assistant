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

# 4. Run
python -m local_assistant
```

## Roadmap

Implementation is phased — see [`docs/roadmap.md`](docs/roadmap.md). Current status: **Phase 0 — scaffold**.

## License

MIT — see [`LICENSE`](LICENSE).
