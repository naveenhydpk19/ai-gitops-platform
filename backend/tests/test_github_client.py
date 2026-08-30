import unittest

import httpx

from github_client import GitHubClient


class GitHubClientTests(unittest.TestCase):
    def test_pull_request_change_uses_live_api_evidence(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/pulls/17"):
                return httpx.Response(200, json={
                    "title": "Protect checkout migration",
                    "html_url": "https://github.com/acme/shop/pull/17",
                    "body": "Rollback plan: restore the previous schema snapshot.",
                    "user": {"login": "octocat"},
                    "head": {"sha": "abc123"},
                    "additions": 80,
                    "deletions": 12,
                    "labels": [],
                })
            if request.url.path.endswith("/pulls/17/files"):
                return httpx.Response(200, json=[{"filename": "db/migrations/17.sql"}])
            if request.url.path.endswith("/commits/abc123/check-runs"):
                return httpx.Response(200, json={"check_runs": [
                    {"name": "integration", "status": "completed", "conclusion": "success"}
                ]})
            return httpx.Response(404)

        client = httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="https://api.github.com",
        )
        change = GitHubClient(token="test-token", client=client).pull_request_change("acme/shop", 17)

        self.assertEqual(["db/migrations/17.sql"], change["files"])
        self.assertTrue(change["tests_passed"])
        self.assertTrue(change["has_rollback_plan"])
        self.assertEqual("abc123", change["head_sha"])


if __name__ == "__main__":
    unittest.main()