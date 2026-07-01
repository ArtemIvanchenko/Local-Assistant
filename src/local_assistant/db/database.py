"""SQLite access layer.

One connection guarded by a lock (single-user, low concurrency). Applies schema.sql
on first run and loads sqlite-vec if available — if it can't load (some Python
builds disable extensions), semantic search degrades to LIKE text matching so the
app still runs everywhere.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from ..config import settings

_SCHEMA = Path(__file__).with_name("schema.sql")


class Database:
    def __init__(self, path: str | None = None):
        self.path = path or settings.db_path
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.vec_enabled = self._try_load_vec()
        self._apply_schema()

    # ── setup ────────────────────────────────────────────────
    def _try_load_vec(self) -> bool:
        try:
            import sqlite_vec  # noqa: PLC0415

            self._conn.enable_load_extension(True)
            sqlite_vec.load(self._conn)
            self._conn.enable_load_extension(False)
            return True
        except Exception:
            return False

    def _apply_schema(self) -> None:
        with self._lock:
            self._conn.executescript(_SCHEMA.read_text())
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)"
            )
            if self.vec_enabled:
                for tbl in ("vec_memories", "vec_chunks", "vec_messages"):
                    self._conn.execute(
                        f"CREATE VIRTUAL TABLE IF NOT EXISTS {tbl} "
                        "USING vec0(id INTEGER PRIMARY KEY, embedding float[768])"
                    )
            self._migrate()
            self._conn.commit()

    def _migrate(self) -> None:
        """Idempotent column adds (sync provenance with external backends like iCloud)."""
        for table in ("events", "reminders"):
            cols = {r["name"] for r in self._conn.execute(f"PRAGMA table_info({table})")}
            if "source" not in cols:
                self._conn.execute(f"ALTER TABLE {table} ADD COLUMN source TEXT DEFAULT 'local'")
            if "ext_id" not in cols:
                self._conn.execute(f"ALTER TABLE {table} ADD COLUMN ext_id TEXT")

    # ── generic helpers ──────────────────────────────────────
    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    # ── settings kv (runtime state, e.g. active model) ───────
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.query_one("SELECT value FROM settings WHERE key=?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def close(self) -> None:
        self._conn.close()
