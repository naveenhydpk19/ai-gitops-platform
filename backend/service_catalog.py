"""Service ownership and dependency graph loaded from a versioned catalog."""

import json
import os
from pathlib import Path


class ServiceCatalog:
    def __init__(self, path: str | Path | None = None, source: str | None = None):
        configured_path = path or os.getenv("SERVICE_CATALOG_PATH")
        self.path = (
            Path(configured_path)
            if configured_path
            else Path(__file__).resolve().parent / "config/service-catalog.json"
        )
        self.source = source or os.getenv("SERVICE_CATALOG_SOURCE") or (
            self.path.name if configured_path else "backend/config/service-catalog.json"
        )

    def graph(self) -> dict:
        if not self.path.exists():
            return {"configured": False, "source": self.source, "services": [], "edges": []}
        services = json.loads(self.path.read_text(encoding="utf-8")).get("services", [])
        edges = [
            {"from": service["name"], "to": dependency}
            for service in services
            for dependency in service.get("depends_on", [])
        ]
        return {"configured": True, "source": self.source, "services": services, "edges": edges}

    def impact(self, repository: str, files: list[str]) -> dict:
        graph = self.graph()
        services = graph["services"]
        changed = {
            service["name"]
            for service in services
            if service.get("repository") == repository
            and any(path.startswith(prefix) for path in files for prefix in service.get("paths", []))
        }
        impacted = set(changed)
        while True:
            dependants = {
                service["name"]
                for service in services
                if any(dependency in impacted for dependency in service.get("depends_on", []))
            }
            expanded = impacted | dependants
            if expanded == impacted:
                break
            impacted = expanded
        return {**graph, "changedServices": sorted(changed), "impactedServices": sorted(impacted)}