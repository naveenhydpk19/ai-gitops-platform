import unittest

from delivery_orchestrator import DeliveryOrchestrator, DeliveryPolicyError


class FakeGitHub:
    def __init__(self, approved):
        self.approved = approved
        self.dispatched = False

    def approved_change_request(self, _repository, number):
        return {"number": number, "state": "open", "approved": self.approved, "labels": []}

    def dispatch_workflow(self, repository, workflow, ref, inputs):
        self.dispatched = True
        return {"accepted": True, "repository": repository, "workflow": workflow, "ref": ref, "inputs": inputs}


def plan():
    return {
        "planId": "plan-1", "status": "READY_FOR_EXECUTION", "repository": "company/platform",
        "version": "1.2.3", "changeRequest": 42,
        "intent": {"branch": "master", "environments": ["dev", "qa", "prod"]},
    }


class DeliveryOrchestratorTests(unittest.TestCase):
    def test_unapproved_change_request_prevents_dispatch(self):
        github = FakeGitHub(approved=False)
        with self.assertRaises(DeliveryPolicyError):
            DeliveryOrchestrator(github).execute(plan())
        self.assertFalse(github.dispatched)

    def test_approved_change_request_dispatches_guarded_workflow(self):
        github = FakeGitHub(approved=True)
        result = DeliveryOrchestrator(github).execute(plan())
        self.assertTrue(github.dispatched)
        self.assertEqual("release-deploy.yml", result["workflow"])
        self.assertEqual("dev,qa,prod", result["inputs"]["environments"])


if __name__ == "__main__":
    unittest.main()