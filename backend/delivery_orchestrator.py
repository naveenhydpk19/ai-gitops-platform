"""Deterministic execution boundary for AI-generated delivery plans."""

from github_client import GitHubClient


class DeliveryPolicyError(ValueError):
    pass


class DeliveryOrchestrator:
    def __init__(self, github: GitHubClient | None = None):
        self.github = github or GitHubClient()

    def execute(self, plan: dict) -> dict:
        if plan.get("status") != "READY_FOR_EXECUTION":
            raise DeliveryPolicyError("Only a ready plan can be dispatched")
        repository = plan["repository"]
        environments = plan["intent"]["environments"]
        change_evidence = None
        if "prod" in environments:
            change_request = plan.get("changeRequest")
            if not change_request:
                raise DeliveryPolicyError("Production requires a change request")
            change_evidence = self.github.approved_change_request(repository, change_request)
            if not change_evidence["approved"]:
                raise DeliveryPolicyError("Change request must be open and labeled change-approved")

        dispatch = self.github.dispatch_workflow(
            repository,
            "release-deploy.yml",
            plan["intent"]["branch"],
            {
                "version": plan["version"],
                "environments": ",".join(environments),
                "change_request": str(plan.get("changeRequest") or ""),
                "plan_id": plan["planId"],
            },
        )
        return {**dispatch, "changeRequestEvidence": change_evidence}