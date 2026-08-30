import hashlib
import hmac
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


class WebhookTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = str(Path(self.temp_dir.name) / "test.db")
        self.environment = patch.dict(os.environ, {
            "GITHUB_WEBHOOK_SECRET": "test-secret",
            "CHANGEGUARD_DATABASE": self.database,
        })
        self.environment.start()
        import importlib
        import main
        self.main = importlib.reload(main)
        self.client = TestClient(self.main.app)

    def tearDown(self):
        self.environment.stop()
        self.temp_dir.cleanup()

    def test_rejects_invalid_signature(self):
        response = self.client.post(
            "/api/v1/webhooks/github",
            content=b"{}",
            headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": "sha256=bad"},
        )
        self.assertEqual(401, response.status_code)

    def test_valid_pull_request_is_analyzed_and_persisted(self):
        payload = {
            "action": "opened",
            "number": 42,
            "repository": {"full_name": "acme/payments"},
            "pull_request": {"number": 42, "additions": 12, "deletions": 4, "user": {"login": "dev"}},
            "changeguard": {"files": ["db/migrations/42.sql"], "tests_passed": True, "has_rollback_plan": False},
        }
        body = json.dumps(payload).encode()
        signature = "sha256=" + hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
        response = self.client.post(
            "/api/v1/webhooks/github",
            content=body,
            headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": signature},
        )
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()["accepted"])
        history = self.client.get("/api/v1/changes").json()["items"]
        self.assertEqual("PR-42", history[0]["changeId"])


if __name__ == "__main__":
    unittest.main()