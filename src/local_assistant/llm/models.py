"""Curated catalogue of models that make sense on a Raspberry Pi 5 (8GB).

Powers the /models chooser and validation. These are *suggestions* — any model
installed in Ollama can be selected; this list just helps you pick.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    name: str           # Ollama tag
    role: str           # main | router | embed
    size: str           # approx Q4 on-disk / RAM
    tool_calling: str   # quality note
    notes: str


# Ordered best-first within each role.
CATALOG: list[ModelInfo] = [
    # ── Main "brain" (reasoning + tool-calling) ──────────────────────────
    ModelInfo("qwen3.5:4b", "main", "~2.5 GB",
              "strong",
              "Default. Gated DeltaNet hybrid → small KV cache, great for long "
              "context. Needs a recent Ollama/llama.cpp build."),
    ModelInfo("qwen3:4b-instruct", "main", "~2.5 GB",
              "very strong",
              "Rock-solid fallback if Qwen3.5 is unstable on your build. Mature "
              "ARM support."),
    ModelInfo("phi-4-mini", "main", "~2.5 GB",
              "good",
              "Microsoft Phi-4-mini 3.8B — strong reasoning/math, leaner knowledge."),
    ModelInfo("gemma3:4b", "main", "~3.3 GB",
              "ok",
              "Multilingual (140+ langs) + vision. Tool-calling weaker than Qwen."),
    ModelInfo("llama3.2:3b", "main", "~2.0 GB",
              "ok",
              "Lighter/faster, lower reasoning. Good on a busy Pi."),

    # ── Router (fast intent classification, short replies) ───────────────
    ModelInfo("qwen3:1.7b", "router", "~1.3 GB",
              "good",
              "Default router. Tens of tok/s — snappy intent routing."),
    ModelInfo("gemma3:1b", "router", "~0.9 GB",
              "n/a",
              "Fastest tested on Pi 5 (~18-22 tok/s). Routing/short answers only."),
    ModelInfo("llama3.2:1b", "router", "~0.8 GB",
              "n/a",
              "Tiny, fast alternative router."),

    # ── Embeddings (semantic memory / RAG) ───────────────────────────────
    ModelInfo("embeddinggemma:300m", "embed", "~0.4 GB",
              "n/a",
              "Default. 768-dim, retrieval-tuned."),
    ModelInfo("nomic-embed-text", "embed", "~0.3 GB",
              "n/a",
              "768-dim alternative, widely used."),
]


def by_role(role: str) -> list[ModelInfo]:
    return [m for m in CATALOG if m.role == role]


def find(name: str) -> ModelInfo | None:
    return next((m for m in CATALOG if m.name == name), None)
