"""Read-only adapters for Prometheus SLOs and Argo Rollouts resources."""

import os

import httpx


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
            "argoRollouts": {"configured": bool(self.kubernetes_url and self.kubernetes_token)},
        }

    def rollout_signals(self, service: str, namespace: str, rollout: str) -> dict:
        result = {
            "service": service,
            "prometheus": {"configured": bool(self.prometheus_url)},
            "rollout": {"configured": bool(self.kubernetes_url and self.kubernetes_token)},
        }
        if self.prometheus_url:
            queries = {
                "errorRate": f'sum(rate(http_requests_total{{service="{service}",status=~"5.."}}[5m])) / clamp_min(sum(rate(http_requests_total{{service="{service}"}}[5m])), 1) * 100',
                "requestRate": f'sum(rate(http_requests_total{{service="{service}"}}[5m]))',
            }
            metrics = {}
            for name, query in queries.items():
                response = self.client.get(f"{self.prometheus_url}/api/v1/query", params={"query": query})
                response.raise_for_status()
                values = response.json().get("data", {}).get("result", [])
                metrics[name] = float(values[0]["value"][1]) if values else None
            result["prometheus"] = {"configured": True, "metrics": metrics}
        if self.kubernetes_url and self.kubernetes_token:
            response = self.client.get(
                f"{self.kubernetes_url}/apis/argoproj.io/v1alpha1/namespaces/{namespace}/rollouts/{rollout}",
                headers={"Authorization": f"Bearer {self.kubernetes_token}"},
            )
            response.raise_for_status()
            status = response.json().get("status", {})
            result["rollout"] = {
                "configured": True,
                "phase": status.get("phase", "Unknown"),
                "currentStepIndex": status.get("currentStepIndex"),
                "replicas": status.get("replicas", 0),
                "updatedReplicas": status.get("updatedReplicas", 0),
                "availableReplicas": status.get("availableReplicas", 0),
            }
        return result