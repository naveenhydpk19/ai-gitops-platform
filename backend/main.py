import hashlib
import hmac
import json
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from change_store import ChangeStore
from delivery_orchestrator import DeliveryOrchestrator, DeliveryPolicyError
from delivery_store import DeliveryStore
from deployment_agents import DeploymentMultiAgent
from environment_client import EnvironmentClient
from github_client import GitHubClient
from risk_engine import analyze_change
from service_catalog import ServiceCatalog


app = FastAPI(title="ChangeGuard API", version="0.1.0")
cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
database_path = os.getenv("CHANGEGUARD_DATABASE") or str(Path(__file__).resolve().parent / "data/changeguard.db")
store = ChangeStore(database_path)
delivery_store = DeliveryStore(database_path)
catalog = ServiceCatalog()


def verify_github_signature(body: bytes, signature: str | None) -> None:
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    if not secret:
        return
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid GitHub webhook signature")


def normalize_pull_request(payload: dict) -> dict:
    pull_request = payload.get("pull_request", {})
    repository = payload.get("repository", {})
    files = payload.get("changeguard", {}).get("files", [])
    return {
        "change_id": f"PR-{pull_request.get('number', payload.get('number', 'unknown'))}",
        "repository": repository.get("full_name", "unknown"),
        "author": pull_request.get("user", {}).get("login", "unknown"),
        "files": files,
        "additions": pull_request.get("additions", 0),
        "deletions": pull_request.get("deletions", 0),
        "downstream_services": payload.get("changeguard", {}).get("downstream_services", []),
        "recent_related_incidents": payload.get("changeguard", {}).get("recent_related_incidents", 0),
        "tests_passed": payload.get("changeguard", {}).get("tests_passed", False),
        "has_rollback_plan": payload.get("changeguard", {}).get("has_rollback_plan", False),
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/api/v1/changes/analyze")
def analyze(payload: dict):
    result = analyze_change(payload)
    store.save(result["changeId"], payload, result)
    return result


@app.get("/api/v1/changes")
def list_changes(limit: int = Query(20, ge=1, le=100)):
    return {"items": store.list(limit)}


@app.get("/api/v1/integrations/status")
def integration_status():
    status = EnvironmentClient().status(catalog.graph()["configured"])
    status["openai"] = {
        "configured": DeploymentMultiAgent().configured,
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    }
    return status


@app.post("/api/v1/delivery/plan")
def plan_delivery(payload: dict):
    message = str(payload.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=422, detail="A developer request is required")
    planner = DeploymentMultiAgent()
    if not planner.configured:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured")
    plan = planner.plan(
        message,
        str(payload.get("repository", "")).strip(),
        str(payload.get("version", "")).strip(),
        payload.get("change_request"),
    )
    return delivery_store.save(plan)


@app.get("/api/v1/delivery/plans")
def list_delivery_plans(limit: int = Query(20, ge=1, le=100)):
    return {"items": delivery_store.list(limit)}


@app.post("/api/v1/delivery/plans/{plan_id}/execute")
def execute_delivery_plan(plan_id: str):
    plan = delivery_store.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Delivery plan was not found")
    try:
        execution = DeliveryOrchestrator().execute(plan)
    except DeliveryPolicyError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="GitHub workflow dispatch failed") from error
    return delivery_store.record_execution(plan_id, execution)


@app.get("/api/v1/dependencies")
def dependency_graph():
    return catalog.graph()


@app.post("/api/v1/dependencies/impact")
def dependency_impact(payload: dict):
    return catalog.impact(str(payload.get("repository", "")), payload.get("files", []))


@app.get("/api/v1/rollouts/signals")
def rollout_signals(service: str, namespace: str = "default", rollout: str = ""):
    try:
        return EnvironmentClient().rollout_signals(service, namespace, rollout or service)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="Environment signal source is unavailable") from error


@app.post("/api/v1/integrations/github/import")
def import_github_pull_request(payload: dict):
    repository = str(payload.get("repository", "")).strip()
    number = payload.get("pull_request")
    if repository.count("/") != 1 or not isinstance(number, int) or number < 1:
        raise HTTPException(status_code=422, detail="repository and positive pull_request are required")
    try:
        change = GitHubClient().pull_request_change(repository, number)
    except httpx.HTTPStatusError as error:
        status = error.response.status_code
        detail = "GitHub repository or pull request was not accessible" if status in {401, 403, 404} else "GitHub API request failed"
        raise HTTPException(status_code=502, detail=detail) from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="GitHub API is unavailable") from error
    impact = catalog.impact(change["repository"], change["files"])
    change["downstream_services"] = [
        service for service in impact["impactedServices"] if service not in impact["changedServices"]
    ]
    result = analyze_change(change)
    store.save(result["changeId"], change, result)
    return {"source": change, "impact": impact, "analysis": result}


@app.post("/api/v1/webhooks/github")
async def github_webhook(
    request: Request,
    x_github_event: str | None = Header(default=None),
    x_hub_signature_256: str | None = Header(default=None),
):
    body = await request.body()
    verify_github_signature(body, x_hub_signature_256)
    if x_github_event != "pull_request":
        return {"accepted": False, "reason": "Event type is not analyzed"}
    payload = json.loads(body)
    if payload.get("action") not in {"opened", "reopened", "synchronize", "ready_for_review"}:
        return {"accepted": False, "reason": "Pull request action is not analyzed"}
    change = normalize_pull_request(payload)
    result = analyze_change(change)
    store.save(result["changeId"], change, result)
    return {"accepted": True, "analysis": result}