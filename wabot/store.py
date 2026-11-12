import os
import sqlite3
import threading


class MessageStore:
    def __init__(self, path: str):
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS processed_messages ("
                "message_id TEXT PRIMARY KEY, "
                "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS turns ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "wa_id TEXT NOT NULL, "
                "role TEXT NOT NULL, "
                "text TEXT NOT NULL, "
                "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_turns_wa ON turns (wa_id, id)")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS inbox ("
                "seq INTEGER PRIMARY KEY AUTOINCREMENT, "
                "message_id TEXT NOT NULL UNIQUE, "
                "wa_id TEXT NOT NULL, "
                "text TEXT NOT NULL, "
                "status TEXT NOT NULL DEFAULT 'pending', "
                "attempts INTEGER NOT NULL DEFAULT 0, "
                "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            self._conn.commit()

    def add_turn(self, wa_id: str, role: str, text: str) -> None:
        with self._lock:
            self._conn.execute("INSERT INTO turns (wa_id, role, text) VALUES (?, ?, ?)", (wa_id, role, text))
            self._conn.commit()

    def recent(self, wa_id: str, n: int) -> list[tuple[str, str]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT role, text FROM turns WHERE wa_id = ? ORDER BY id DESC LIMIT ?", (wa_id, n)
            ).fetchall()
        return [(role, text) for role, text in reversed(rows)]

    def claim(self, message_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO processed_messages (message_id) VALUES (?)",
                (message_id,),
            )
            self._conn.commit()
            return cur.rowcount == 1

    def release(self, message_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM processed_messages WHERE message_id = ?", (message_id,))
            self._conn.commit()

    def enqueue(self, message_id: str, wa_id: str, text: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO inbox (message_id, wa_id, text) VALUES (?, ?, ?)",
                (message_id, wa_id, text),
            )
            self._conn.commit()
            return cur.rowcount == 1

    def pending(self, max_age_hours: int = 24) -> list[tuple[str, str, str]]:
        with self._lock:
            self._conn.execute(
                "UPDATE inbox SET status = 'dead' "
                "WHERE status = 'pending' AND created_at < datetime('now', ?)",
                (f"-{max_age_hours} hours",),
            )
            self._conn.commit()
            rows = self._conn.execute(
                "SELECT message_id, wa_id, text FROM inbox WHERE status = 'pending' ORDER BY seq"
            ).fetchall()
        return [(m, w, t) for m, w, t in rows]

    def is_done(self, message_id: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM inbox WHERE message_id = ? AND status = 'done'", (message_id,)
            ).fetchone()
        return row is not None

    def complete(self, message_id: str, wa_id: str, user_text: str, reply: str) -> None:
        with self._lock:
            self._conn.execute("UPDATE inbox SET status = 'done' WHERE message_id = ?", (message_id,))
            self._conn.execute(
                "INSERT INTO turns (wa_id, role, text) VALUES (?, 'user', ?)", (wa_id, user_text)
            )
            self._conn.execute(
                "INSERT INTO turns (wa_id, role, text) VALUES (?, 'assistant', ?)", (wa_id, reply)
            )
            self._conn.commit()

    def record_failure(self, message_id: str, max_attempts: int) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE inbox SET attempts = attempts + 1, "
                "status = CASE WHEN attempts + 1 >= ? THEN 'dead' ELSE status END "
                "WHERE message_id = ?",
                (max_attempts, message_id),
            )
            self._conn.commit()

    def prune(self, retention_days: int, max_turns_per_sender: int) -> None:
        cutoff = f"-{retention_days} days"
        with self._lock:
            self._conn.execute("DELETE FROM turns WHERE created_at < datetime('now', ?)", (cutoff,))
            self._conn.execute("DELETE FROM inbox WHERE created_at < datetime('now', ?)", (cutoff,))
            self._conn.execute(
                "DELETE FROM processed_messages WHERE created_at < datetime('now', ?)", (cutoff,)
            )
            self._conn.execute(
                "DELETE FROM turns WHERE id IN ("
                "SELECT id FROM ("
                "SELECT id, ROW_NUMBER() OVER (PARTITION BY wa_id ORDER BY id DESC) AS rn FROM turns"
                ") WHERE rn > ?)",
                (max_turns_per_sender,),
            )
            self._conn.commit()
