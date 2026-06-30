-- Local Assistant — SQLite schema.
-- Structured memory lives here; semantic vectors mirror into sqlite-vec tables.
-- Apply with: sqlite3 data/assistant.db < schema.sql

PRAGMA journal_mode = WAL;        -- survive sudden power loss better
PRAGMA foreign_keys = ON;

-- ── Schedule ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY,
    title       TEXT NOT NULL,
    start_ts    TEXT NOT NULL,          -- ISO8601
    end_ts      TEXT,
    recur_rule  TEXT,                   -- RFC5545 RRULE, nullable
    notes       TEXT,
    created_ts  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reminders (
    id              INTEGER PRIMARY KEY,
    text            TEXT NOT NULL,
    fire_at         TEXT NOT NULL,       -- ISO8601
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending|sent|snoozed|done
    source_event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
    created_ts      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_reminders_fire ON reminders(fire_at, status);

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY,
    title       TEXT NOT NULL,
    due_ts      TEXT,
    priority    INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'open',          -- open|done|dropped
    created_ts  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── Memory ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY,
    role        TEXT NOT NULL,           -- user|assistant|system|tool
    text        TEXT NOT NULL,
    ts          TEXT NOT NULL DEFAULT (datetime('now')),
    embedded    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(ts);

CREATE TABLE IF NOT EXISTS memories (
    id          INTEGER PRIMARY KEY,
    type        TEXT NOT NULL,           -- user|feedback|project|observation
    content     TEXT NOT NULL,
    confidence  REAL NOT NULL DEFAULT 1.0,
    ts          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS patterns (
    id          INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    evidence    TEXT,
    confidence  REAL NOT NULL DEFAULT 0.3,
    first_seen  TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── Documents (RAG) ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY,
    source      TEXT NOT NULL,           -- filename / origin
    added_ts    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS doc_chunks (
    id          INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_idx   INTEGER NOT NULL,
    text        TEXT NOT NULL
);

-- ── Observability ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS metrics (
    id           INTEGER PRIMARY KEY,
    ts           TEXT NOT NULL DEFAULT (datetime('now')),
    intent       TEXT,
    model        TEXT,
    latency_ms   INTEGER,
    tool_called  TEXT,
    tool_success INTEGER
);

-- ── Vector mirrors (sqlite-vec) ─────────────────────────────
-- Created at runtime after the extension loads, e.g.:
--   CREATE VIRTUAL TABLE vec_memories USING vec0(embedding float[768]);
--   CREATE VIRTUAL TABLE vec_chunks   USING vec0(embedding float[768]);
--   CREATE VIRTUAL TABLE vec_messages USING vec0(embedding float[768]);
-- (embeddinggemma:300m -> 768 dims; adjust if the embed model changes.)
