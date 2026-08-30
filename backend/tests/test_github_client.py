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

    def test_pull_request_change_reads_all_evidence_pages(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/pulls/18"):
                return httpx.Response(200, json={
                    "title": "Paginated evidence",
                    "html_url": "https://github.com/acme/shop/pull/18",
                    "body": "",
                    "user": {"login": "octocat"},
                    "head": {"sha": "def456"},
                    "labels": [],
                })
            page = request.url.params.get("page")
            if request.url.path.endswith("/pulls/18/files"):
                if page == "2":
                    return httpx.Response(200, json=[{"filename": "src/second.py"}])
                return httpx.Response(200, headers={"Link": '<https://api.github.com/repos/acme/shop/pulls/18/files?page=2>; rel="next"'}, json=[{"filename": "src/first.py"}])
            if request.url.path.endswith("/commits/def456/check-runs"):
                if page == "2":
                    return httpx.Response(200, json={"check_runs": [{"name": "integration", "status": "completed", "conclusion": "success"}]})
                return httpx.Response(200, headers={"Link": '<https://api.github.com/repos/acme/shop/commits/def456/check-runs?page=2>; rel="next"'}, json={"check_runs": [{"name": "unit", "status": "completed", "conclusion": "success"}]})
            return httpx.Response(404)

        client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com")
        change = GitHubClient(token="test-token", client=client).pull_request_change("acme/shop", 18)

        self.assertEqual(["src/first.py", "src/second.py"], change["files"])
        self.assertEqual(["unit", "integration"], [check["name"] for check in change["check_runs"]])
        self.assertTrue(change["tests_passed"])


if __name__ == "__main__":
    unittest.main()