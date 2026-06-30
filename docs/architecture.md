# Architecture

Fully-local AI secretary on Raspberry Pi 5 (8GB), over Telegram. Privacy-first:
the code is public, the **runtime data never leaves the Pi**.

## Components

```
Telegram ──► [I/O: python-telegram-bot]  (owner chat_id whitelist)
                       │
                       ▼
            [Orchestrator / agent loop]
              ├─ Router (Qwen3-1.7B): classify intent
              └─ Reasoner (Qwen3.5-4B): tool-calling
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
 [Tools — MCP server]           [Memory]
  - calendar/reminder/task CRUD  - SQLite (structured)
  - memory read/write            - sqlite-vec (semantic + RAG)
  - web_search (ddgs)            - MEMORY.md (profile)
  - ingest_document (RAG)
        ▲
[APScheduler] ── reminders · morning/evening digest · nightly reflection+consolidation
```

## Models

| Role | Model | Notes |
|---|---|---|
| Main | **Qwen3.5-4B** | Gated DeltaNet hybrid (3:1 linear:full attention) → small KV cache, good for memory-heavy long context. Needs recent llama.cpp/Ollama. |
| Main fallback | **Qwen3-4B-Instruct-2507** | If Gated DeltaNet is unstable on the local ARM build. Same tool-calling family. |
| Router | **Qwen3-1.7B** | Fast intent classification / short replies. |
| Embeddings | **embeddinggemma:300m** | 768-dim, retrieval-tuned. |
| Draft (spec. decode) | **Qwen3-0.6B** | Speculative decoding for the main model. |

Gemma 4 E4B is **not** the brain (weak/buggy tool-calling) but is reserved for the
voice phase thanks to native audio input.

## Context window — capacity ≠ working point

Qwen3.5-4B supports 262K tokens, but on the Pi two limits bind:

- **RAM (KV cache):** linear attention keeps KV small (only ~1/4 of layers grow) →
  32–64K feasible, ×2–4 more with `KV_CACHE_TYPE=q8_0/q4_0`.
- **Prefill speed (the real bottleneck):** ~30–50 tok/s on CPU. Cold-ingesting 8K ≈
  3–4 min, 32K ≈ 10–18 min. llama.cpp reuses KV across turns, so only a large
  *first* input is slow.

**Therefore:** operate at a **2–8K working context** (`WORKING_CONTEXT_BUDGET`)
assembled via RAG retrieval, keep 32–64K as occasional document-Q&A headroom, and
don't use 100K+ in practice.

## Inference speedups (combine)

Active cooling (mandatory — throttling halves t/s), 2.8–3.0 GHz overclock, NVMe SSD,
NEON+dotprod+fp16 build, `num_threads=4`, THP, KV-cache quantization, speculative
decoding, router for short turns, response streaming, nightly batch for heavy
analysis. Realistic ceiling: 4B ≈ 5–8 tok/s generation.

## Privacy & reliability

chat_id whitelist · LUKS/disk encryption · secrets in `.env` (gitignored) ·
encrypted rotating backups of SQLite + MEMORY.md · systemd `Restart=always` +
heartbeat · WAL mode for power-loss resilience.

> **Telegram caveat:** bot messages are **not** end-to-end encrypted — they pass
> through Telegram's servers. Accepted as a known trade-off for convenience; a
> Matrix/Signal bridge is a possible future swap.
