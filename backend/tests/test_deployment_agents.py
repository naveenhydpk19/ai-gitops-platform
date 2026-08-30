import unittest

from deployment_agents import DeploymentIntent, DeploymentMultiAgent, SpecialistOpinion


class FakeStructuredModel:
    def __init__(self, schema):
        self.schema = schema

    def invoke(self, _messages):
        if self.schema is DeploymentIntent:
            return DeploymentIntent(
                action="release_and_deploy",
                branch="master",
                environments=["dev", "qa", "prod"],
                summary="Release master through production",
            )
        return SpecialistOpinion(agent="specialist", decision="allow", reasons=["Evidence looks valid"])


class FakeModel:
    def with_structured_output(self, schema):
        return FakeStructuredModel(schema)


class DeploymentAgentTests(unittest.TestCase):
    def test_deterministic_policy_blocks_prod_without_change_request(self):
        plan = DeploymentMultiAgent(FakeModel()).plan(
            "I merged master; create a release and deploy dev, qa, and prod",
            repository="company/platform",
            version="1.2.3",
        )
        self.assertEqual("BLOCKED", plan["status"])
        self.assertIn("Production requires a GitHub change-request issue number", plan["blockers"])
        self.assertEqual("gpt-4o-mini", plan["model"])

    def test_approved_plan_retains_human_prod_gate(self):
        plan = DeploymentMultiAgent(FakeModel()).plan(
            "release everything", repository="company/platform", version="1.2.3", change_request=42
        )
        self.assertEqual("READY_FOR_EXECUTION", plan["status"])
        prod = next(step for step in plan["steps"] if step["id"] == "deploy-prod")
        self.assertEqual("change request + human approval", prod["control"])


if __name__ == "__main__":
    unittest.main()