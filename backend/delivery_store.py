"""SQLite audit store for AI-generated delivery plans and executions."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path


class DeliveryStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS delivery_plans (
                    plan_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    execution_json TEXT
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

    def save(self, plan: dict) -> dict:
        stored = {**plan, "planId": uuid.uuid4().hex}
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO delivery_plans(plan_id, status, plan_json) VALUES (?, ?, ?)",
                (stored["planId"], stored["status"], json.dumps(stored)),
            )
        return stored

    def get(self, plan_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT created_at, updated_at, plan_json, execution_json FROM delivery_plans WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()
        if not row:
            return None
        plan = json.loads(row["plan_json"])
        return {
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            **plan,
            "execution": json.loads(row["execution_json"]) if row["execution_json"] else None,
        }

    def list(self, limit: int = 20) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT plan_id FROM delivery_plans ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [plan for row in rows if (plan := self.get(row["plan_id"]))]

    def record_execution(self, plan_id: str, execution: dict) -> dict:
        with self._connect() as connection:
            connection.execute(
                """UPDATE delivery_plans SET status = ?, execution_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE plan_id = ?""",
                ("DISPATCHED", json.dumps(execution), plan_id),
            )
        return self.get(plan_id)