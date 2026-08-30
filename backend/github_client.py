"""GitHub REST adapter for production change evidence."""

import os

import httpx


class GitHubClient:
    def __init__(self, token: str | None = None, client: httpx.Client | None = None):
        self.token = token if token is not None else os.getenv("GITHUB_TOKEN", "")
        self.client = client or httpx.Client(base_url="https://api.github.com", timeout=15)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _get_paginated(self, path: str, headers: dict[str, str], key: str | None = None) -> list[dict]:
        items: list[dict] = []
        url: str | None = path
        params: dict[str, int] | None = {"per_page": 100}
        while url:
            response = self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            payload = response.json()
            items.extend(payload.get(key, []) if key else payload)
            url = response.links.get("next", {}).get("url")
            params = None
        return items

    def pull_request_change(self, repository: str, number: int) -> dict:
        headers = self._headers()
        pull_request = self.client.get(f"/repos/{repository}/pulls/{number}", headers=headers)
        pull_request.raise_for_status()
        pull_request_data = pull_request.json()

        files = self._get_paginated(f"/repos/{repository}/pulls/{number}/files", headers)
        checks = self._get_paginated(
            f"/repos/{repository}/commits/{pull_request_data['head']['sha']}/check-runs",
            headers,
            key="check_runs",
        )
        passing_conclusions = {"success", "neutral", "skipped"}
        tests_passed = bool(checks) and all(
            check.get("status") == "completed" and check.get("conclusion") in passing_conclusions
            for check in checks
        )

        labels = {label["name"].lower() for label in pull_request_data.get("labels", [])}
        body = (pull_request_data.get("body") or "").lower()
        has_rollback_plan = "rollback-ready" in labels or "rollback plan" in body

        return {
            "change_id": f"PR-{number}",
            "repository": repository,
            "author": pull_request_data.get("user", {}).get("login", "unknown"),
            "title": pull_request_data.get("title", "Untitled pull request"),
            "url": pull_request_data.get("html_url"),
            "head_sha": pull_request_data["head"]["sha"],
            "files": [file["filename"] for file in files],
            "additions": pull_request_data.get("additions", 0),
            "deletions": pull_request_data.get("deletions", 0),
            "tests_passed": tests_passed,
            "check_runs": [
                {"name": check.get("name"), "status": check.get("status"), "conclusion": check.get("conclusion")}
                for check in checks
            ],
            "has_rollback_plan": has_rollback_plan,
        }

    def approved_change_request(self, repository: str, number: int) -> dict:
        response = self.client.get(f"/repos/{repository}/issues/{number}", headers=self._headers())
        response.raise_for_status()
        issue = response.json()
        labels = {label["name"].lower() for label in issue.get("labels", [])}
        return {
            "number": number,
            "url": issue.get("html_url"),
            "state": issue.get("state"),
            "approved": issue.get("state") == "open" and "change-approved" in labels,
            "labels": sorted(labels),
        }

    def dispatch_workflow(self, repository: str, workflow: str, ref: str, inputs: dict) -> dict:
        response = self.client.post(
            f"/repos/{repository}/actions/workflows/{workflow}/dispatches",
            headers=self._headers(),
            json={"ref": ref, "inputs": inputs},
        )
        response.raise_for_status()
        return {
            "accepted": True,
            "workflow": workflow,
            "actionsUrl": f"https://github.com/{repository}/actions/workflows/{workflow}",
        }