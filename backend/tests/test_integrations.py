import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from environment_client import EnvironmentClient
from service_catalog import ServiceCatalog


class IntegrationTests(unittest.TestCase):
    def test_catalog_exposes_logical_source_without_local_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "service-catalog.json"
            path.write_text('{"services": []}', encoding="utf-8")

            graph = ServiceCatalog(path, source="catalog/service-catalog.json").graph()

            self.assertEqual("catalog/service-catalog.json", graph["source"])
            self.assertNotIn(directory, graph["source"])

    def test_catalog_computes_transitive_dependants(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text(json.dumps({"services": [
                {"name": "api", "repository": "acme/shop", "paths": ["api/"], "depends_on": ["database"]},
                {"name": "worker", "repository": "acme/shop", "paths": ["worker/"], "depends_on": ["api"]},
                {"name": "database", "repository": "acme/shop", "paths": ["db/"], "depends_on": []},
            ]}), encoding="utf-8")
            impact = ServiceCatalog(path).impact("acme/shop", ["db/schema.sql"])
            self.assertEqual(["database"], impact["changedServices"])
            self.assertEqual(["api", "database", "worker"], impact["impactedServices"])

    def test_rollout_signals_come_from_prometheus_and_kubernetes(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/api/v1/query"):
                value = "0.4" if "status" in request.url.params["query"] else "125"
                return httpx.Response(200, json={"data": {"result": [{"value": [0, value]}]}})
            return httpx.Response(200, json={"status": {"phase": "Progressing", "replicas": 10, "updatedReplicas": 2, "availableReplicas": 10}})

        environment = {
            "PROMETHEUS_URL": "https://prometheus.example",
            "KUBERNETES_API_URL": "https://kubernetes.example",
            "KUBERNETES_TOKEN": "test-token",
        }
        with patch.dict(os.environ, environment):
            client = httpx.Client(transport=httpx.MockTransport(handler))
            signals = EnvironmentClient(client).rollout_signals("checkout", "prod", "checkout")
        self.assertEqual(0.4, signals["prometheus"]["metrics"]["errorRate"])
        self.assertTrue(signals["prometheus"]["available"])
        self.assertEqual("Progressing", signals["rollout"]["phase"])
        self.assertTrue(signals["rollout"]["available"])

    def test_rollout_signals_preserve_available_source_when_prometheus_fails(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "prometheus.example":
                raise httpx.ConnectError("unreachable", request=request)
            return httpx.Response(200, json={"status": {"phase": "Healthy", "replicas": 2}})

        environment = {
            "PROMETHEUS_URL": "https://prometheus.example",
            "KUBERNETES_API_URL": "https://kubernetes.example",
            "KUBERNETES_TOKEN": "",
        }
        with patch.dict(os.environ, environment):
            client = httpx.Client(transport=httpx.MockTransport(handler))
            signals = EnvironmentClient(client).rollout_signals("checkout", "prod", "checkout")

        self.assertFalse(signals["prometheus"]["available"])
        self.assertEqual("Prometheus query failed", signals["prometheus"]["error"])
        self.assertTrue(signals["rollout"]["available"])
        self.assertEqual("Healthy", signals["rollout"]["phase"])

    def test_rollout_signals_reject_unsafe_identifiers(self):
        with self.assertRaisesRegex(ValueError, "Invalid service identifier"):
            EnvironmentClient().rollout_signals('checkout",job="other', "prod", "checkout")

    def test_rollout_signals_identify_missing_rollout(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/api/v1/query"):
                return httpx.Response(200, json={"data": {"result": []}})
            return httpx.Response(404, json={"message": "not found"})

        environment = {
            "PROMETHEUS_URL": "https://prometheus.example",
            "KUBERNETES_API_URL": "https://kubernetes.example",
            "KUBERNETES_TOKEN": "",
        }
        with patch.dict(os.environ, environment):
            client = httpx.Client(transport=httpx.MockTransport(handler))
            signals = EnvironmentClient(client).rollout_signals("gateway-svc", "dev", "gateway-svc")

        self.assertTrue(signals["prometheus"]["available"])
        self.assertIsNone(signals["prometheus"]["metrics"]["requestRate"])
        self.assertFalse(signals["rollout"]["available"])
        self.assertEqual("Rollout gateway-svc was not found in namespace dev", signals["rollout"]["error"])


if __name__ == "__main__":
    unittest.main()