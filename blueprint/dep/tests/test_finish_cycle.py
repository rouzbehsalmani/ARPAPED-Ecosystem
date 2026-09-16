"""Synthetic round-trip coverage for blueprint/dep/finish_cycle.py -- the
only regression coverage any blueprint/dep/ tool has today, added here
because no starter kit is touched to prove this one instead (see the
plan this module was built from). Stdlib unittest + tempfile only, matching
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

from blueprint.dep import checkpoint, dataset_builder, episode_store, finish_cycle

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

    def test_no_catalog_publishes_without_acyclic_check(self):
        # catalog_path=None, and no catalog file is ever written -- proves
        # the acyclic-graph check is skipped outright, not just tolerant of
        # an empty/missing file at a path someone actually gave (see
        # test_missing_catalog_file_still_refuses_when_path_given below).
        episode_dir = finish_cycle.finish_cycle(
            _minimal_cycle_report(),
            _minimal_verification_record(verification_id="no-catalog-0001"),
            None,
            self.episodes_dir,
        )

        self.assertTrue(episode_dir.exists())
        self.assertFalse(self.catalog_path.exists())
        episodes = list(episode_store.load_episodes(self.episodes_dir))
        self.assertEqual(len(episodes), 1)

    def test_no_catalog_with_ecosystem_root_but_clean_still_publishes(self):
        # ecosystem_root given AND catalog_path=None -- the leakage check
        # runs, finds nothing, and publishing proceeds exactly as if
        # ecosystem_root had been omitted.
        (self.root / "MyApp.csproj").write_text("real content", encoding="utf-8")
        episode_dir = finish_cycle.finish_cycle(
            _minimal_cycle_report(),
            _minimal_verification_record(verification_id="clean-ecosystem-0001"),
            None,
            self.episodes_dir,
            ecosystem_root=self.root,
        )
        self.assertTrue(episode_dir.exists())

    def test_no_catalog_with_bridge_leakage_refuses(self):
        # The real, observed failure this whole gate exists to close: a
        # Builder agent built a Bridge-shaped contracts/capabilities tree
        # for a project that never adopted the Bridge pillar at all.
        # packs/README.md's own prose telling it not to was not enough --
        # this is the mechanical check that actually stops the cycle from
        # being marked published while it's still true.
        (self.root / "contracts").mkdir()
        (self.root / "contracts" / "simcity.build.contract.yaml").write_text("identity: {}", encoding="utf-8")

        with self.assertRaises(finish_cycle.FinishCycleError) as ctx:
            finish_cycle.finish_cycle(
                _minimal_cycle_report(),
                _minimal_verification_record(verification_id="leaky-ecosystem-0001"),
                None,
                self.episodes_dir,
                ecosystem_root=self.root,
            )

        message = str(ctx.exception)
        self.assertIn("contracts", message)
        self.assertIn("simcity.build.contract.yaml", message)
        self.assertFalse(self.episodes_dir.exists() and any(self.episodes_dir.iterdir()))

    def test_no_catalog_without_ecosystem_root_skips_leakage_check(self):
        # Omitting ecosystem_root (its default) means the leakage check
        # simply doesn't run -- backward compatible with every existing
        # DEP-only caller that has no such concept, never a silent
        # "assume clean." This is what "STRONGLY recommended" (not
        # required) means in practice: leakage in self.root is real here,
        # but nothing refuses because ecosystem_root was never passed.
        (self.root / "contracts").mkdir()
        (self.root / "contracts" / "leaky.contract.yaml").write_text("identity: {}", encoding="utf-8")

        episode_dir = finish_cycle.finish_cycle(
            _minimal_cycle_report(),
            _minimal_verification_record(verification_id="no-root-passed-0001"),
            None,
            self.episodes_dir,
        )
        self.assertTrue(episode_dir.exists())

    def test_bridge_adopted_never_runs_leakage_check_even_if_passed(self):
        # catalog_path is a real Path (Bridge adopted) -- the leakage
        # check is specific to "Bridge vocabulary with no Bridge," so it
        # never runs here even if ecosystem_root is also given; a real
        # contracts/ dir is exactly what a Bridge-adopting ecosystem is
        # supposed to have.
        _write_catalog(self.catalog_path, _ACYCLIC_ENTRIES)
        (self.root / "contracts").mkdir()
        (self.root / "contracts" / "real.contract.yaml").write_text("identity: {}", encoding="utf-8")

        episode_dir = finish_cycle.finish_cycle(
            _minimal_cycle_report(),
            _minimal_verification_record(verification_id="bridge-adopted-0001"),
            self.catalog_path,
            self.episodes_dir,
            ecosystem_root=self.root,
        )
        self.assertTrue(episode_dir.exists())

    def test_cli_ecosystem_root_flag_refuses_on_leakage(self):
        (self.root / "capabilities").mkdir()
        (self.root / "capabilities" / "manifest.yaml").write_text(
            "capability_id: x\nimplementations: []\n", encoding="utf-8",
        )
        cycle_report_path = self.root / "agent-cycle-report.json"
        verification_record_path = self.root / "verification-record.json"
        cycle_report_path.write_text(json.dumps(_minimal_cycle_report()), encoding="utf-8")
        verification_record_path.write_text(
            json.dumps(_minimal_verification_record(verification_id="cli-leaky-0001")), encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable, "-m", "blueprint.dep.finish_cycle",
                "--cycle-report", str(cycle_report_path),
                "--verification-record", str(verification_record_path),
                "--episodes-dir", str(self.episodes_dir),
                "--ecosystem-root", str(self.root),
            ],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("NOT published", result.stderr)
        self.assertIn("capabilities", result.stderr)

    def test_no_catalog_unverified_status_still_refuses(self):
        # Fail-closed (2-RULES.md) holds regardless of whether the Runtime
        # pillar is in play -- catalog_path=None never bypasses the
        # verified-status refusal, only the acyclic-graph check.
        with self.assertRaises(finish_cycle.FinishCycleError) as ctx:
            finish_cycle.finish_cycle(
                _minimal_cycle_report(),
                _minimal_verification_record(status="failed", verification_id="no-catalog-failed-0001"),
                None,
                self.episodes_dir,
            )

        self.assertIn("failed", str(ctx.exception))
        self.assertFalse(self.episodes_dir.exists() and any(self.episodes_dir.iterdir()))

    def test_missing_catalog_file_still_refuses_when_path_given(self):
        # The regression lock: only an EXPLICIT None skips the check. A
        # real Path that happens to not exist is still a hard refusal --
        # never silently treated as "nothing to check", which would
        # quietly weaken Gate 30 for a Runtime-pillar caller who passed the
        # wrong path or forgot to register before calling finish_cycle.
        self.assertFalse(self.catalog_path.exists())

        with self.assertRaises(finish_cycle.FinishCycleError) as ctx:
            finish_cycle.finish_cycle(
                _minimal_cycle_report(),
                _minimal_verification_record(verification_id="missing-catalog-0001"),
                self.catalog_path,
                self.episodes_dir,
            )

        self.assertIn("capability catalog not found", str(ctx.exception))

    def test_cli_no_catalog_round_trip(self):
        # --catalog omitted from argv entirely (not passed as an empty
        # string) -- the CLI's own equivalent of catalog_path=None.
        cycle_report_path = self.root / "agent-cycle-report.json"
        verification_record_path = self.root / "verification-record.json"
        cycle_report_path.write_text(json.dumps(_minimal_cycle_report()), encoding="utf-8")
        verification_record_path.write_text(
            json.dumps(_minimal_verification_record(verification_id="cli-no-catalog-0001")), encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable, "-m", "blueprint.dep.finish_cycle",
                "--cycle-report", str(cycle_report_path),
                "--verification-record", str(verification_record_path),
                "--episodes-dir", str(self.episodes_dir),
            ],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        episode_dir = Path(result.stdout.strip())
        self.assertTrue(episode_dir.exists())

    def test_no_catalog_episode_feeds_dataset_builder(self):
        # The concrete Evolution-pillar-alone proof: a cycle report/
        # verification record carrying zero Bridge/capability vocabulary
        # (empty new_capabilities/reused_capabilities, an explicit "not
        # adopted" bridge_integration note, a check with no check_type/
        # trace/selection/evidence) still round-trips through finish_cycle
        # (catalog_path=None) and dataset_builder -- proving DEP's own
        # recording+training-export path needs nothing Bridge-shaped.
        no_bridge_cycle_report = {
            "goal": {"description": "Add input validation to a CLI argument parser."},
            "starting_state": "test starting state, no Bridge in this project",
            "decisions": [
                {
                    "responsibility": "validate_user_input",
                    "decision": "create",
                    "reason": "no existing validation for this argument shape",
                },
            ],
            "new_capabilities": [],
            "reused_capabilities": [],
            "bridge_integration": "N/A -- this project has not adopted the Bridge pillar",
            "verification": {
                "harness": "plain-unittest",
                "verification_record_ref": "state/verification-record.json",
                "status": "verified",
            },
            "resulting_state": "test resulting state",
            "next_cycle_readiness": "everything needed is in state/",
        }
        no_bridge_verification_record = {
            "verification_id": "no-bridge-0001",
            "state_ref": "test/state",
            "harness": "plain-unittest",
            "checks": [
                {"check_id": "check:1", "description": "validation rejects empty input", "status": "passed"},
            ],
            "passed": 1,
            "failed": 0,
            "status": "verified",
        }

        finish_cycle.finish_cycle(no_bridge_cycle_report, no_bridge_verification_record, None, self.episodes_dir)

        rows = list(dataset_builder.build_rows(self.episodes_dir))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["responsibility"], "validate_user_input")
        self.assertEqual(rows[0]["decision"], "create")
        self.assertEqual(rows[0]["verification_status"], "verified")
        self.assertNotIn("bridge_selection", rows[0])
        self.assertNotIn("bridge_evidence", rows[0])
        self.assertNotIn("bridge_trace", rows[0])


if __name__ == "__main__":
    unittest.main()
