"""Coverage for dataset_builder.py's structured failure/correction and
check_ids-joined selection/evidence/trace pull-through -- the exact gap
this module used to have even for the one failure-adjacent field that
already existed before this test was added (verification.failures_and_fixes
was never read into a row at all).

Run from the repository root:
    python -m unittest blueprint.dep.tests.test_dataset_builder -v
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from blueprint.dep import dataset_builder, episode_store


def _cycle_report(
    decisions: list[dict],
    failures_and_fixes: str | None = None,
    resulting_state_ref: dict | None = None,
) -> dict:
    verification: dict = {
        "harness": "test-harness",
        "verification_record_ref": "state/verification-record.json",
        "status": "verified",
    }
    if failures_and_fixes is not None:
        verification["failures_and_fixes"] = failures_and_fixes
    report = {
        "goal": {"description": "test goal"},
        "starting_state": "test starting state",
        "decisions": decisions,
        "new_capabilities": [],
        "reused_capabilities": [],
        "bridge_integration": "test bridge integration note",
        "verification": verification,
        "resulting_state": "test resulting state",
        "next_cycle_readiness": "everything needed is in state/",
    }
    if resulting_state_ref is not None:
        report["resulting_state_ref"] = resulting_state_ref
    return report


def _verification_record(verification_id: str, checks: list[dict], environment: dict | None = None) -> dict:
    record = {
        "verification_id": verification_id,
        "state_ref": "test/state",
        "harness": "test-harness",
        "checks": checks,
        "passed": sum(1 for c in checks if c["status"] == "passed"),
        "failed": sum(1 for c in checks if c["status"] == "failed"),
        "status": "verified",
    }
    if environment is not None:
        record["environment"] = environment
    return record


class DatasetBuilderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.episodes_dir = Path(self._tmp.name) / "episodes"

    def tearDown(self):
        self._tmp.cleanup()

    def test_failure_and_correction_pulled_through(self):
        decision = {
            "responsibility": "grid.cell", "decision": "create", "reason": "needed for the test",
            "failure": {"summary": "catalog parsing failed", "detail": "missing: operation"},
            "correction": {"summary": "catalog schema corrected", "detail": "added the required operation field"},
        }
        report = _cycle_report([decision])
        record = _verification_record("ds-failure-0001", [])
        episode_store.save_episode(report, record, self.episodes_dir)

        rows = list(dataset_builder.build_rows(self.episodes_dir))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["failure"], decision["failure"])
        self.assertEqual(rows[0]["correction"], decision["correction"])

    def test_decision_with_neither_failure_nor_correction_omits_both(self):
        decision = {"responsibility": "grid.cell", "decision": "reuse", "reason": "already exists"}
        report = _cycle_report([decision])
        record = _verification_record("ds-clean-0001", [])
        episode_store.save_episode(report, record, self.episodes_dir)

        rows = list(dataset_builder.build_rows(self.episodes_dir))
        self.assertNotIn("failure", rows[0])
        self.assertNotIn("correction", rows[0])

    def test_failures_and_fixes_pulled_through(self):
        decision = {"responsibility": "grid.cell", "decision": "create", "reason": "x"}
        report = _cycle_report([decision], failures_and_fixes="one thing broke, fixed by Y")
        record = _verification_record("ds-fnf-0001", [])
        episode_store.save_episode(report, record, self.episodes_dir)

        rows = list(dataset_builder.build_rows(self.episodes_dir))
        self.assertEqual(rows[0]["failures_and_fixes"], "one thing broke, fixed by Y")

    def test_check_ids_join_folds_in_selection_evidence_trace(self):
        decision = {
            "responsibility": "console.write", "decision": "reuse", "reason": "x",
            "check_ids": ["call:1:console_write"],
        }
        report = _cycle_report([decision])
        checks = [{
            "check_id": "call:1:console_write", "description": "d", "status": "passed",
            "check_type": "capability_operation",
            "trace": ["validated", "discovered", "policy_evaluated", "selected", "executed"],
            "selection": {
                "capability_id": "console.write", "operation": "write", "contract_version": ">=2.0.0,<3.0.0",
                "candidates": [{"implementation_id": "console.write.v2", "priority": 200}],
                "selected": "console.write.v2", "reason": "highest priority (200) among 1 policy-allowed candidate",
            },
            "evidence": {"executor_kind": "process", "response_output": {}},
        }]
        record = _verification_record("ds-join-0001", checks)
        episode_store.save_episode(report, record, self.episodes_dir)

        rows = list(dataset_builder.build_rows(self.episodes_dir))
        self.assertEqual(rows[0]["bridge_selection"], [checks[0]["selection"]])
        self.assertEqual(rows[0]["bridge_evidence"], [checks[0]["evidence"]])
        self.assertEqual(rows[0]["bridge_trace"], [checks[0]["trace"]])

    def test_absent_check_ids_never_guessed(self):
        # No check_ids on the decision, even though a check with a
        # similarly-named check_id exists -- the join must never guess by
        # string similarity.
        decision = {"responsibility": "console.write", "decision": "reuse", "reason": "x"}
        report = _cycle_report([decision])
        checks = [{
            "check_id": "call:1:console_write", "description": "d", "status": "passed",
            "check_type": "capability_operation",
            "trace": ["validated", "discovered", "policy_evaluated", "selected", "executed"],
        }]
        record = _verification_record("ds-noguess-0001", checks)
        episode_store.save_episode(report, record, self.episodes_dir)

        rows = list(dataset_builder.build_rows(self.episodes_dir))
        self.assertNotIn("bridge_selection", rows[0])
        self.assertNotIn("bridge_evidence", rows[0])
        self.assertNotIn("bridge_trace", rows[0])

    def test_check_ids_join_folds_in_input(self):
        decision = {
            "responsibility": "console.write", "decision": "reuse", "reason": "x",
            "check_ids": ["call:1:console_write"],
        }
        report = _cycle_report([decision])
        checks = [{
            "check_id": "call:1:console_write", "description": "d", "status": "passed",
            "check_type": "capability_operation",
            "trace": ["validated", "discovered", "policy_evaluated", "selected", "executed"],
            "input": {"message": "hi"},
        }]
        record = _verification_record("ds-input-0001", checks)
        episode_store.save_episode(report, record, self.episodes_dir)

        rows = list(dataset_builder.build_rows(self.episodes_dir))
        self.assertEqual(rows[0]["bridge_input"], [{"message": "hi"}])

    def test_environment_and_resulting_state_ref_pulled_through(self):
        decision = {"responsibility": "grid.cell", "decision": "reuse", "reason": "x"}
        state_ref = {"content_hash": "sha256:deadbeef", "vcs": {"system": "git", "commit": "a" * 40}}
        report = _cycle_report([decision], resulting_state_ref=state_ref)
        environment = {"os": "Linux", "arch": "x86_64"}
        record = _verification_record("ds-env-0001", [], environment=environment)
        episode_store.save_episode(report, record, self.episodes_dir)

        rows = list(dataset_builder.build_rows(self.episodes_dir))
        self.assertEqual(rows[0]["environment"], environment)
        self.assertEqual(rows[0]["resulting_state_ref"], state_ref)

    def test_absent_environment_and_resulting_state_ref_omitted(self):
        decision = {"responsibility": "grid.cell", "decision": "reuse", "reason": "x"}
        report = _cycle_report([decision])
        record = _verification_record("ds-noenv-0001", [])
        episode_store.save_episode(report, record, self.episodes_dir)

        rows = list(dataset_builder.build_rows(self.episodes_dir))
        self.assertNotIn("environment", rows[0])
        self.assertNotIn("resulting_state_ref", rows[0])

    def test_build_dataset_writes_jsonl(self):
        decision = {"responsibility": "grid.cell", "decision": "reuse", "reason": "x"}
        report = _cycle_report([decision])
        record = _verification_record("ds-jsonl-0001", [])
        episode_store.save_episode(report, record, self.episodes_dir)

        output_path = Path(self._tmp.name) / "dataset.jsonl"
        count = dataset_builder.build_dataset(self.episodes_dir, output_path)
        self.assertEqual(count, 1)
        lines = output_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        json.loads(lines[0])  # must be valid JSON


if __name__ == "__main__":
    unittest.main()
