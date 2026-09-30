"""SQLite-backed persistent memory store for Scout."""

from __future__ import annotations

import sqlite3
import json
from pathlib import Path
from typing import Any

from scout.config import APP_DIR

DB_PATH = APP_DIR / "data" / "scout.db"

# Initial user profile seeded on first run
_INITIAL_PROFILE = {
    "name": "Sanjay Kumar MP",
    "occupation": "Engineering student",
    "course": "Computer Science and Business Systems",
    "interests": "AI, automation, web development, cybersecurity",
    "current_project": "Scout",
    "preferred_development_style": "terminal-first",
    "preferred_ai": "local AI when practical",
}


class MemoryStore:
    """SQLite-backed persistent memory."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    # ── Connection management ──────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                category TEXT NOT NULL,
                key      TEXT NOT NULL,
                value    TEXT NOT NULL,
                updated  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (category, key)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_mem_cat ON memories (category)
        """)
        conn.commit()

        # Seed initial profile if table is empty
        row = conn.execute("SELECT COUNT(*) as cnt FROM memories").fetchone()
        if row["cnt"] == 0:
            self._seed_profile()

    def _seed_profile(self) -> None:
        for key, value in _INITIAL_PROFILE.items():
            self.save("user_profile", key, value)

    # ── CRUD operations ────────────────────────────────────────────────

    def save(self, category: str, key: str, value: str) -> None:
        """Insert or update a memory entry."""
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO memories (category, key, value, updated)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(category, key) DO UPDATE
               SET value = excluded.value, updated = CURRENT_TIMESTAMP""",
            (category, key, value),
        )
        conn.commit()

    def get(self, category: str, key: str) -> str | None:
        """Get a single memory value."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT value FROM memories WHERE category = ? AND key = ?",
            (category, key),
        ).fetchone()
        return row["value"] if row else None

    def delete(self, category: str, key: str) -> bool:
        """Delete a memory entry. Returns True if it existed."""
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM memories WHERE category = ? AND key = ?",
            (category, key),
        )
        conn.commit()
        return cursor.rowcount > 0

    def search(self, query: str) -> list[dict[str, str]]:
        """Search memories by key or value substring (case-insensitive)."""
        conn = self._get_conn()
        pattern = f"%{query}%"
        rows = conn.execute(
            """SELECT category, key, value FROM memories
               WHERE key LIKE ? OR value LIKE ?
               ORDER BY updated DESC LIMIT 20""",
            (pattern, pattern),
        ).fetchall()
        return [{"category": r["category"], "key": r["key"], "value": r["value"]} for r in rows]

    def get_by_category(self, category: str) -> list[dict[str, str]]:
        """Get all memories in a category."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT key, value FROM memories WHERE category = ? ORDER BY key",
            (category,),
        ).fetchall()
        return [{"key": r["key"], "value": r["value"]} for r in rows]

    def get_user_profile(self) -> dict[str, str]:
        """Get the user profile as a dict."""
        items = self.get_by_category("user_profile")
        return {item["key"]: item["value"] for item in items}

    def get_relevant_memories(self, query: str) -> str:
        """Retrieve a compact, relevant memory block for injection into the model context.
        Returns a short formatted string, NOT the raw data.
        """
        lines: list[str] = []

        # Always include key profile facts (compact)
        profile = self.get_user_profile()
        if profile:
            name = profile.get("name", "User")
            lines.append(f"User: {name}")
            if "current_project" in profile:
                lines.append(f"Current project: {profile['current_project']}")
            if "preferred_development_style" in profile:
                lines.append(f"Dev style: {profile['preferred_development_style']}")

        # Search for query-relevant memories (max 5)
        if query:
            results = self.search(query)
            seen = set()
            for r in results[:5]:
                if r["category"] == "user_profile":
                    continue  # Already included above
                entry = f"{r['key']}: {r['value']}"
                if entry not in seen:
                    seen.add(entry)
                    lines.append(entry)

        # Include preferences (max 3)
        prefs = self.get_by_category("preferences")
        for p in prefs[:3]:
            entry = f"Preference: {p['key']} = {p['value']}"
            if entry not in lines:
                lines.append(entry)

        if not lines:
            return ""

        return "<relevant_memory>\n" + "\n".join(lines) + "\n</relevant_memory>"

    def get_summary(self) -> str:
        """Get a compact summary of all stored memories for /memory display."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT category, COUNT(*) as cnt FROM memories GROUP BY category ORDER BY category"
        ).fetchall()

        lines: list[str] = []
        for r in rows:
            lines.append(f"  {r['category']}: {r['cnt']} entries")

        total = sum(r["cnt"] for r in rows)
        header = f"Scout Memory ({total} entries total)"
        return header + "\n" + "\n".join(lines)

    def clear_all(self) -> int:
        """Delete all memories. Returns count of deleted entries."""
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM memories")
        conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


# Singleton instance
_store: MemoryStore | None = None

def get_memory_store() -> MemoryStore:
    """Get the singleton MemoryStore instance."""
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store
