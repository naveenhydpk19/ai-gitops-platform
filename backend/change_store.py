"""SQLite persistence for analyzed production changes."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class ChangeStore:
    def __init__(self, path: str | Path = "data/changeguard.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS change_analyses (
                    change_id TEXT PRIMARY KEY,
                    analyzed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    payload_json TEXT NOT NULL,
                    result_json TEXT NOT NULL
                )"""
            )

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save(self, change_id: str, payload: dict, result: dict) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO change_analyses(change_id, payload_json, result_json)
                VALUES (?, ?, ?)
                ON CONFLICT(change_id) DO UPDATE SET
                    analyzed_at=CURRENT_TIMESTAMP,
                    payload_json=excluded.payload_json,
                    result_json=excluded.result_json""",
                (change_id, json.dumps(payload), json.dumps(result)),
            )

    def list(self, limit: int = 20) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT analyzed_at, payload_json, result_json FROM change_analyses ORDER BY analyzed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "analyzedAt": row["analyzed_at"],
                "source": json.loads(row["payload_json"]),
                **json.loads(row["result_json"]),
            }
            for row in rows
        ]