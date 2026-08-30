"""LangChain specialists with a deterministic deployment-policy boundary."""

import os
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


Environment = Literal["dev", "qa", "prod"]


class DeploymentIntent(BaseModel):
    action: Literal["release_and_deploy", "deploy", "status", "unknown"]
    branch: str = "master"
    environments: list[Environment] = Field(default_factory=list)
    summary: str


class SpecialistOpinion(BaseModel):
    agent: str
    decision: Literal["allow", "block", "needs_evidence"]
    reasons: list[str]


class DeploymentMultiAgent:
    def __init__(self, model=None):
        self.model = model
        self.model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    @property
    def configured(self) -> bool:
        return self.model is not None or bool(os.getenv("OPENAI_API_KEY"))

    def _model(self):
        return self.model or ChatOpenAI(model=self.model_name, temperature=0)

    def plan(
        self,
        message: str,
        repository: str = "",
        version: str = "",
        change_request: int | None = None,
    ) -> dict:
        model = self._model()
        intent = model.with_structured_output(DeploymentIntent).invoke([
            SystemMessage(content=(
                "You are the Release Intent Agent. Extract only explicit deployment intent. "
                "Use environments in promotion order dev, qa, prod. Never invent a branch or approval."
            )),
            HumanMessage(content=message),
        ])
        release_opinion = model.with_structured_output(SpecialistOpinion).invoke([
            SystemMessage(content=(
                "You are the Release Agent. Review whether this request can create an immutable semantic tag "
                "and GitHub release from the named branch. Identify missing source or CI evidence."
            )),
            HumanMessage(content=f"Intent: {intent.model_dump_json()}"),
        ])
        policy_opinion = model.with_structured_output(SpecialistOpinion).invoke([
            SystemMessage(content=(
                "You are the Production Policy Agent. Production requires an approved change record and a "
                "GitHub Environment reviewer. You advise only; deterministic policy makes the final decision."
            )),
            HumanMessage(content=f"Intent: {intent.model_dump_json()}; change request: {change_request}"),
        ])

        blockers: list[str] = []
        if intent.action not in {"release_and_deploy", "deploy"}:
            blockers.append("No executable release or deployment intent was detected")
        if intent.branch not in {"master", "main"}:
            blockers.append("Only the protected master or main branch can be released")
        if not intent.environments:
            blockers.append("At least one target environment is required")
        if repository.count("/") != 1:
            blockers.append("A GitHub repository in owner/name format is required")
        version_parts = version.removeprefix("v").split(".")
        if len(version_parts) != 3 or not all(part.isdigit() for part in version_parts):
            blockers.append("A semantic release version is required")
        if "prod" in intent.environments and change_request is None:
            blockers.append("Production requires a GitHub change-request issue number")

        return {
            "model": self.model_name,
            "intent": intent.model_dump(),
            "agents": [release_opinion.model_dump(), policy_opinion.model_dump()],
            "changeRequest": change_request,
            "repository": repository,
            "version": version.removeprefix("v"),
            "status": "BLOCKED" if blockers else "READY_FOR_EXECUTION",
            "blockers": blockers,
            "steps": self._steps(intent.environments),
        }

    @staticmethod
    def _steps(environments: list[Environment]) -> list[dict]:
        steps = [
            {"id": "verify", "label": "Verify protected branch and CI", "control": "automatic"},
            {"id": "release", "label": "Create immutable tag and GitHub release", "control": "automatic"},
            {"id": "publish", "label": "Build, scan, and publish ECR images", "control": "automatic"},
        ]
        for environment in environments:
            control = "change request + human approval" if environment == "prod" else "health gate"
            steps.append({"id": f"deploy-{environment}", "label": f"Promote Helm release to {environment}", "control": control})
        return steps