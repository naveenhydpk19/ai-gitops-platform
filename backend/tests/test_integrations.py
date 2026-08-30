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
        self.assertEqual("Progressing", signals["rollout"]["phase"])


if __name__ == "__main__":
    unittest.main()