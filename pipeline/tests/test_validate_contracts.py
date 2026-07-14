import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validate_contracts import decision_ok


class ValidateContractsTests(unittest.TestCase):
    def _decision(self):
        return {
            "schema": "hermes.decision.v1.1",
            "run_id": "plan.001.judge",
            "decision_type": "plan",
            "summary": "next",
            "new_stages": [{
                "id": "X", "title": "x", "depends_on": [], "kind": "implement",
                "contract_version": "1.0", "inputs": ["i"], "outputs": ["o"],
                "in_scope": ["x"], "out_of_scope": ["y"],
                "acceptance": [{"id": "X-AC1", "text": "passes"}],
                "acceptance_to_test_matrix": [{
                    "criterion_id": "X-AC1", "behavior_attack": "x",
                    "exact_test": "tests/test_x.py::test_x", "expected_evidence": "x",
                    "forbidden_side_effects": "none",
                }],
                "required_tests": [], "allowed_files": ["backend/**"], "executor_brief": "do x",
            }],
            "goal_done": False,
            "blocked_reason": None,
            "needs_from_owner": None,
        }

    def test_rejects_one_pytest_command_mixing_uv_project_roots(self):
        d = self._decision()
        d["new_stages"][0]["required_tests"] = [
            "uv run pytest backend/tests/ mcp-server/tests/ -x -q"
        ]
        with self.assertRaisesRegex(ValueError, "cross-project pytest"):
            decision_ok(d)

    def test_accepts_separate_project_aware_pytest_commands(self):
        d = self._decision()
        d["new_stages"][0]["required_tests"] = [
            "uv run --python 3.11 pytest backend/tests/ -x -q",
            "uv run --project mcp-server pytest mcp-server/tests/ -x -q",
        ]
        decision_ok(copy.deepcopy(d))


if __name__ == "__main__":
    unittest.main()
