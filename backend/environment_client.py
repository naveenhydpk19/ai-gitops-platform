"""Read-only adapters for Prometheus SLOs and Argo Rollouts resources."""

import os
import re

import httpx


SIGNAL_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,252}$")


class EnvironmentClient:
    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=10)
        self.prometheus_url = os.getenv("PROMETHEUS_URL", "").rstrip("/")
        self.kubernetes_url = os.getenv("KUBERNETES_API_URL", "").rstrip("/")
        self.kubernetes_token = os.getenv("KUBERNETES_TOKEN", "")

    def status(self, catalog_configured: bool) -> dict:
        return {
            "github": {"configured": bool(os.getenv("GITHUB_TOKEN")), "supportsPublicWithoutToken": True},
            "serviceCatalog": {"configured": catalog_configured},
            "prometheus": {"configured": bool(self.prometheus_url)},
            "argoRollouts": {"configured": bool(self.kubernetes_url)},
        }

    def rollout_signals(self, service: str, namespace: str, rollout: str) -> dict:
        for label, value in {"service": service, "namespace": namespace, "rollout": rollout}.items():
            if not SIGNAL_IDENTIFIER.fullmatch(value):
                raise ValueError(f"Invalid {label} identifier")

        result = {
            "service": service,
            "prometheus": {"configured": bool(self.prometheus_url), "available": False},
            "rollout": {"configured": bool(self.kubernetes_url), "available": False},
        }
        if self.prometheus_url:
            queries = {
                "errorRate": f'sum(rate(http_requests_total{{service="{service}",status=~"5.."}}[5m])) / clamp_min(sum(rate(http_requests_total{{service="{service}"}}[5m])), 1) * 100',
                "requestRate": f'sum(rate(http_requests_total{{service="{service}"}}[5m]))',
            }
            try:
                metrics = {}
                for name, query in queries.items():
                    response = self.client.get(f"{self.prometheus_url}/api/v1/query", params={"query": query})
                    response.raise_for_status()
                    values = response.json().get("data", {}).get("result", [])
                    metrics[name] = float(values[0]["value"][1]) if values else None
                result["prometheus"] = {"configured": True, "available": True, "metrics": metrics}
            except (httpx.HTTPError, KeyError, TypeError, ValueError):
                result["prometheus"]["error"] = "Prometheus query failed"
        if self.kubernetes_url:
            headers = {"Authorization": f"Bearer {self.kubernetes_token}"} if self.kubernetes_token else {}
            try:
                response = self.client.get(
                    f"{self.kubernetes_url}/apis/argoproj.io/v1alpha1/namespaces/{namespace}/rollouts/{rollout}",
                    headers=headers,
                )
                response.raise_for_status()
                status = response.json().get("status", {})
                result["rollout"] = {
                    "configured": True,
                    "available": True,
                    "phase": status.get("phase", "Unknown"),
                    "currentStepIndex": status.get("currentStepIndex"),
                    "replicas": status.get("replicas", 0),
                    "updatedReplicas": status.get("updatedReplicas", 0),
                    "availableReplicas": status.get("availableReplicas", 0),
                }
            except httpx.HTTPStatusError as error:
                result["rollout"]["error"] = (
                    f"Rollout {rollout} was not found in namespace {namespace}"
                    if error.response.status_code == 404
                    else "Argo Rollout query failed"
                )
            except (httpx.HTTPError, ValueError):
                result["rollout"]["error"] = "Argo Rollout query failed"
        return result