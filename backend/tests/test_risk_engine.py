import unittest

from risk_engine import analyze_change


class RiskEngineTests(unittest.TestCase):
    def test_high_risk_change_is_blocked_without_rollback(self):
        result = analyze_change({
            "change_id": "PR-1",
            "files": ["db/migrations/1.sql", "infra/ingress.yaml", "deploy/configmap.yaml"],
            "downstream_services": ["a", "b", "c", "d", "e", "f"],
            "recent_related_incidents": 2,
            "tests_passed": True,
            "has_rollback_plan": False,
        })
        self.assertEqual("CRITICAL", result["level"])
        self.assertEqual("BLOCKED_PENDING_CONTROLS", result["decision"])
        self.assertIn("Rollback rehearsal", result["requiredControls"])

    def test_small_tested_change_can_reach_canary(self):
        result = analyze_change({
            "change_id": "PR-2",
            "files": ["src/label.ts"],
            "tests_passed": True,
            "has_rollback_plan": True,
        })
        self.assertEqual(0, result["score"])
        self.assertEqual("READY_FOR_CANARY", result["decision"])

    def test_migration_requires_rollback_even_below_high_risk_threshold(self):
        result = analyze_change({
            "change_id": "PR-3",
            "files": ["db/migrations/3.sql"],
            "tests_passed": True,
            "has_rollback_plan": False,
        })
        self.assertEqual("MEDIUM", result["level"])
        self.assertEqual("BLOCKED_PENDING_CONTROLS", result["decision"])


if __name__ == "__main__":
    unittest.main()