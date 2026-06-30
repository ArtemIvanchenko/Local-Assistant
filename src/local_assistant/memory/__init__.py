"""Memory subsystem.

Three tiers:
  - structured  -> SQLite (events, reminders, tasks, messages, patterns)
  - semantic    -> sqlite-vec (memories, doc_chunks, messages embeddings; RAG retrieval)
  - profile     -> MEMORY.md (human-readable durable facts, agent-maintained)

Nightly consolidation dedups/merges facts and decays stale ones. (phase 3, 6)
"""
