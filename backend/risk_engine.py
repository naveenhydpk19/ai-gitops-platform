"""Deterministic production change risk scoring and policy evaluation."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class RiskFactor:
    label: str
    points: int
    evidence: str


def analyze_change(change: dict) -> dict:
    files = [path.lower() for path in change.get("files", [])]
    factors: list[RiskFactor] = []
    if any("migration" in path or path.endswith(".sql") for path in files):
        factors.append(RiskFactor("Database migration", 25, "Schema or migration file changed"))
    if any("configmap" in path or "shared" in path for path in files):
        factors.append(RiskFactor("Shared configuration", 18, "Shared runtime configuration changed"))
    if any("ingress" in path or "gateway" in path for path in files):
        factors.append(RiskFactor("Ingress exposure", 15, "External routing configuration changed"))

    downstream = change.get("downstream_services", [])
    if downstream:
        factors.append(RiskFactor("Dependency blast radius", min(20, len(downstream) * 3), f"{len(downstream)} downstream services affected"))
    incidents = int(change.get("recent_related_incidents", 0))
    if incidents:
        factors.append(RiskFactor("Recent incident history", min(15, incidents * 5), f"{incidents} related incidents in the lookback window"))
    if change.get("additions", 0) + change.get("deletions", 0) > 500:
        factors.append(RiskFactor("Large change set", 10, "More than 500 changed lines"))

    score = min(100, sum(factor.points for factor in factors))
    level = "CRITICAL" if score >= 75 else "HIGH" if score >= 50 else "MEDIUM" if score >= 25 else "LOW"
    controls = ["Test suite must pass"]
    if any(factor.label == "Database migration" for factor in factors):
        controls.extend(["Database backup evidence", "Rollback rehearsal"])
    if score >= 50:
        controls.extend(["10% canary rollout", "Platform approval"])
    if downstream:
        controls.append("Error-rate SLO below 1%")

    has_migration = any(factor.label == "Database migration" for factor in factors)
    blocked = (
        not change.get("tests_passed", False)
        or ((score >= 50 or has_migration) and not change.get("has_rollback_plan", False))
    )
    return {
        "changeId": change.get("change_id"),
        "score": score,
        "level": level,
        "decision": "BLOCKED_PENDING_CONTROLS" if blocked else "READY_FOR_CANARY",
        "factors": [asdict(factor) for factor in factors],
        "affectedServices": downstream,
        "requiredControls": list(dict.fromkeys(controls)),
    }