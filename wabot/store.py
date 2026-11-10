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
