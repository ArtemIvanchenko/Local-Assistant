"""Three-tier memory: structured (SQLite), semantic (sqlite-vec), profile (MEMORY.md).

Semantic search uses sqlite-vec KNN when available, otherwise a LIKE fallback so the
app works on builds without the extension.
"""

from __future__ import annotations

import struct
from pathlib import Path

from ..config import settings


def _serialize(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _extract_text(path: str) -> str:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader  # noqa: PLC0415

        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    if suffix == ".docx":
        import docx  # noqa: PLC0415

        return "\n".join(par.text for par in docx.Document(path).paragraphs)
    return p.read_text(errors="ignore")  # .txt / .md / fallback


def _chunk(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks, step = [], max(1, size - overlap)
    for i in range(0, len(words), step):
        chunks.append(" ".join(words[i : i + size]))
    return chunks


class MemoryStore:
    def __init__(self, db, llm):
        self.db = db
        self.llm = llm

    # ── conversation history ─────────────────────────────────
    def log_message(self, role: str, text: str) -> int:
        cur = self.db.execute(
            "INSERT INTO messages(role, text) VALUES(?, ?)", (role, text)
        )
        return cur.lastrowid

    def recent_messages(self, limit: int = 12) -> list[dict]:
        rows = self.db.query(
            "SELECT role, text FROM messages ORDER BY id DESC LIMIT ?", (limit,)
        )
        return [{"role": r["role"], "content": r["text"]} for r in reversed(rows)]

    # ── durable memories ─────────────────────────────────────
    async def remember(self, content: str, mtype: str = "user", confidence: float = 1.0) -> int:
        cur = self.db.execute(
            "INSERT INTO memories(type, content, confidence) VALUES(?,?,?)",
            (mtype, content, confidence),
        )
        mem_id = cur.lastrowid
        await self._index("vec_memories", mem_id, content)
        return mem_id

    async def search(self, query: str, k: int = 5) -> list[dict]:
        if self.db.vec_enabled:
            try:
                emb = await self.llm.embed(query)
                rows = self.db.query(
                    "SELECT v.id, m.content, v.distance "
                    "FROM vec_memories v JOIN memories m ON m.id = v.id "
                    "WHERE v.embedding MATCH ? AND k = ? ORDER BY v.distance",
                    (_serialize(emb), k),
                )
                return [{"content": r["content"], "score": r["distance"]} for r in rows]
            except Exception:
                pass
        # Fallback: keyword LIKE.
        rows = self.db.query(
            "SELECT content FROM memories WHERE content LIKE ? "
            "ORDER BY id DESC LIMIT ?",
            (f"%{query}%", k),
        )
        return [{"content": r["content"], "score": None} for r in rows]

    async def _index(self, table: str, row_id: int, text: str) -> None:
        if not self.db.vec_enabled:
            return
        try:
            emb = await self.llm.embed(text)
            self.db.execute(
                f"INSERT OR REPLACE INTO {table}(id, embedding) VALUES(?, ?)",
                (row_id, _serialize(emb)),
            )
        except Exception:
            pass  # embedding unavailable (e.g. Ollama down) — keep structured row

    # ── documents (RAG ingest) ───────────────────────────────
    async def ingest_document(self, path: str, source: str) -> int:
        text = _extract_text(path)
        chunks = _chunk(text)
        cur = self.db.execute("INSERT INTO documents(source) VALUES(?)", (source,))
        doc_id = cur.lastrowid
        for i, chunk in enumerate(chunks):
            c = self.db.execute(
                "INSERT INTO doc_chunks(document_id, chunk_idx, text) VALUES(?,?,?)",
                (doc_id, i, chunk),
            )
            await self._index("vec_chunks", c.lastrowid, chunk)
        return len(chunks)

    async def search_documents(self, query: str, k: int = 5) -> list[dict]:
        if self.db.vec_enabled:
            try:
                emb = await self.llm.embed(query)
                rows = self.db.query(
                    "SELECT c.text, v.distance FROM vec_chunks v "
                    "JOIN doc_chunks c ON c.id = v.id "
                    "WHERE v.embedding MATCH ? AND k = ? ORDER BY v.distance",
                    (_serialize(emb), k),
                )
                return [{"content": r["text"], "score": r["distance"]} for r in rows]
            except Exception:
                pass
        rows = self.db.query(
            "SELECT text FROM doc_chunks WHERE text LIKE ? LIMIT ?", (f"%{query}%", k)
        )
        return [{"content": r["text"], "score": None} for r in rows]

    # ── profile (MEMORY.md) ──────────────────────────────────
    def read_profile(self) -> str:
        p = Path(settings.memory_md_path)
        return p.read_text() if p.exists() else ""

    def write_profile(self, text: str) -> None:
        p = Path(settings.memory_md_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
