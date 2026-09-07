"""Synthetic round-trip coverage for blueprint/dep/finish_cycle.py -- the
only regression coverage any blueprint/dep/ tool has today, added here
because no sample/ is touched to prove this one instead (see the plan
this module was built from). Stdlib unittest + tempfile only, matching
the fact that nothing in blueprint/dep/ declares a test dependency beyond
jsonschema/yaml.

Run from the repository root:
    python -m unittest blueprint.dep.tests.test_finish_cycle -v
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from blueprint.dep import checkpoint, episode_store, finish_cycle

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _minimal_cycle_report() -> dict:
    return {
        "goal": {"description": "test goal"},
        "starting_state": "test starting state",
        "decisions": [
            {"responsibility": "grid.cell", "decision": "create", "reason": "needed for the test"},
        ],
        "new_capabilities": ["grid.cell"],
        "reused_capabilities": [],
        "bridge_integration": "test bridge integration note",
        "verification": {
            "harness": "test-harness",
            "verification_record_ref": "state/verification-record.json",
            "status": "verified",
        },
        "resulting_state": "test resulting state",
        "next_cycle_readiness": "everything needed is in state/",
    }


def _minimal_verification_record(status: str = "verified", verification_id: str = "test-cycle-0001") -> dict:
    return {
        "verification_id": verification_id,
        "state_ref": "test/state",
        "harness": "test-harness",
        "checks": [
            {"check_id": "check:1", "description": "a test check", "status": "passed"},
        ],
        "passed": 1,
        "failed": 0,
        "status": status,
    }


def _minimal_checkpoint() -> dict:
    return {
        "checkpoint_id": "test-checkpoint-0001",
        "status": "in_progress",
        "goal": {"description": "test goal"},
        "starting_state": "test starting state",
        "current_phase": "8-publish",
        "phase_log": [{"phase": "0-bootstrap", "note": "started"}],
        "responsibilities": [{"responsibility": "grid.cell", "status": "integrated"}],
        "next_action": "call finish_cycle",
    }


def _write_catalog(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


_ACYCLIC_ENTRIES = [
    {"capability_id": "a", "dependencies": {}},
    {"capability_id": "b", "dependencies": {"a": "*"}},
    {"capability_id": "c", "dependencies": {"b": "*"}},
]

_CYCLIC_ENTRIES = [
    {"capability_id": "a", "dependencies": {"b": "*"}},
    {"capability_id": "b", "dependencies": {"a": "*"}},
]


class FinishCycleTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.catalog_path = self.root / "capability-catalog.jsonl"
        self.episodes_dir = self.root / "episodes"
        self.checkpoint_path = self.root / "cycle-checkpoint.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_acyclic_verified_publishes_and_clears_checkpoint(self):
        _write_catalog(self.catalog_path, _ACYCLIC_ENTRIES)
        checkpoint.save_checkpoint(_minimal_checkpoint(), self.checkpoint_path)
        self.assertTrue(self.checkpoint_path.exists())

        episode_dir = finish_cycle.finish_cycle(
            _minimal_cycle_report(),
            _minimal_verification_record(),
            self.catalog_path,
            self.episodes_dir,
            self.checkpoint_path,
        )

        self.assertTrue(episode_dir.exists())
        self.assertTrue((episode_dir / "agent-cycle-report.json").exists())
        self.assertTrue((episode_dir / "verification-record.json").exists())
        self.assertFalse(self.checkpoint_path.exists(), "checkpoint must be cleared after a successful finish_cycle")

        episodes = list(episode_store.load_episodes(self.episodes_dir))
        self.assertEqual(len(episodes), 1)

    def test_cyclic_graph_refuses(self):
        _write_catalog(self.catalog_path, _CYCLIC_ENTRIES)
        checkpoint.save_checkpoint(_minimal_checkpoint(), self.checkpoint_path)

        with self.assertRaises(finish_cycle.FinishCycleError) as ctx:
            finish_cycle.finish_cycle(
                _minimal_cycle_report(),
                _minimal_verification_record(),
                self.catalog_path,
                self.episodes_dir,
                self.checkpoint_path,
            )

        message = str(ctx.exception)
        self.assertIn("a -> b -> a", message)
        self.assertFalse(self.episodes_dir.exists() and any(self.episodes_dir.iterdir()))
        self.assertTrue(
            self.checkpoint_path.exists(),
            "a refused cycle must never clear the checkpoint -- refusal happens before any side effect",
        )

    def test_unverified_status_refuses(self):
        _write_catalog(self.catalog_path, _ACYCLIC_ENTRIES)

        with self.assertRaises(finish_cycle.FinishCycleError) as ctx:
            finish_cycle.finish_cycle(
                _minimal_cycle_report(),
                _minimal_verification_record(status="failed"),
                self.catalog_path,
                self.episodes_dir,
            )

        self.assertIn("failed", str(ctx.exception))
        self.assertFalse(self.episodes_dir.exists() and any(self.episodes_dir.iterdir()))

    def test_duplicate_episode_still_guarded(self):
        _write_catalog(self.catalog_path, _ACYCLIC_ENTRIES)

        finish_cycle.finish_cycle(
            _minimal_cycle_report(),
            _minimal_verification_record(verification_id="dup-0001"),
            self.catalog_path,
            self.episodes_dir,
        )

        with self.assertRaises(episode_store.EpisodeStoreError):
            finish_cycle.finish_cycle(
                _minimal_cycle_report(),
                _minimal_verification_record(verification_id="dup-0001"),
                self.catalog_path,
                self.episodes_dir,
            )

        episodes = list(episode_store.load_episodes(self.episodes_dir))
        self.assertEqual(len(episodes), 1)

    def test_cli_subprocess_round_trip(self):
        _write_catalog(self.catalog_path, _ACYCLIC_ENTRIES)
        cycle_report_path = self.root / "agent-cycle-report.json"
        verification_record_path = self.root / "verification-record.json"
        cycle_report_path.write_text(json.dumps(_minimal_cycle_report()), encoding="utf-8")
        verification_record_path.write_text(
            json.dumps(_minimal_verification_record(verification_id="cli-0001")), encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable, "-m", "blueprint.dep.finish_cycle",
                "--cycle-report", str(cycle_report_path),
                "--verification-record", str(verification_record_path),
                "--catalog", str(self.catalog_path),
                "--episodes-dir", str(self.episodes_dir),
            ],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        episode_dir = Path(result.stdout.strip())
        self.assertTrue(episode_dir.exists())

    def test_cli_subprocess_cyclic_refusal(self):
        _write_catalog(self.catalog_path, _CYCLIC_ENTRIES)
        cycle_report_path = self.root / "agent-cycle-report.json"
        verification_record_path = self.root / "verification-record.json"
        cycle_report_path.write_text(json.dumps(_minimal_cycle_report()), encoding="utf-8")
        verification_record_path.write_text(
            json.dumps(_minimal_verification_record(verification_id="cli-cyclic-0001")), encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable, "-m", "blueprint.dep.finish_cycle",
                "--cycle-report", str(cycle_report_path),
                "--verification-record", str(verification_record_path),
                "--catalog", str(self.catalog_path),
                "--episodes-dir", str(self.episodes_dir),
            ],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("NOT published", result.stderr)
        self.assertIn("a -> b -> a", result.stderr)


if __name__ == "__main__":
    unittest.main()
