"""Coverage for blueprint/dep/ecosystem_resolution.py -- proves a record
round-trips for each single-pillar composition (the exact three
combinations packs/ offers alone) and that schema-invalid input is
refused, not silently accepted.

Run from the repository root:
    python -m unittest blueprint.dep.tests.test_ecosystem_resolution -v
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from blueprint.dep import ecosystem_resolution


def _bridge_only_record() -> dict:
    return {
        "resolution_id": "res-bridge-0001",
        "ecosystem_root": "test/app",
        "pillars": {
            "bridge": {
                "runtimes": [
                    {
                        "name": "backend",
                        "language": "Python",
                        "bridge": "test/app/runtime/bridge/bridge.py",
                        "registry": "test/app/runtime/bridge/registry.py",
                        "policy": "test/app/runtime/bridge/policy.py",
                        "selector": "test/app/runtime/bridge/selector.py",
                        "contracts_dir": "test/app/implementation/contracts",
                        "implementation_map": {"execution_boundary": "test/app/runtime/bridge/bridge.py"},
                    }
                ]
            }
        },
        "resolved_at": "2026-09-14T00:00:00Z",
    }


def _dep_only_record() -> dict:
    return {
        "resolution_id": "res-dep-0001",
        "ecosystem_root": "test/app",
        "pillars": {
            "dep": {
                "dep_root": "test/app/dep",
                "episodes_dir": "test/app/state/episodes",
            }
        },
        "resolved_at": "2026-09-14T00:00:00Z",
    }


def _cycles_only_record() -> dict:
    return {
        "resolution_id": "res-cycles-0001",
        "ecosystem_root": "test/app",
        "pillars": {
            "cycles": {
                "cycle_doc": "blueprint/1-CYCLE.md",
                "rules_doc": "blueprint/2-RULES.md",
            }
        },
        "resolved_at": "2026-09-14T00:00:00Z",
    }


class EcosystemResolutionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "ecosystem-resolution.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_file_loads_as_none(self):
        self.assertIsNone(ecosystem_resolution.load_resolution_record(self.path))

    def test_bridge_only_round_trips(self):
        ecosystem_resolution.save_resolution_record(_bridge_only_record(), self.path)
        loaded = ecosystem_resolution.load_resolution_record(self.path)
        self.assertEqual(loaded["pillars"].keys(), {"bridge"})
        self.assertEqual(loaded["pillars"]["bridge"]["runtimes"][0]["name"], "backend")

    def test_dep_only_round_trips(self):
        ecosystem_resolution.save_resolution_record(_dep_only_record(), self.path)
        loaded = ecosystem_resolution.load_resolution_record(self.path)
        self.assertEqual(loaded["pillars"].keys(), {"dep"})

    def test_cycles_only_round_trips(self):
        ecosystem_resolution.save_resolution_record(_cycles_only_record(), self.path)
        loaded = ecosystem_resolution.load_resolution_record(self.path)
        self.assertEqual(loaded["pillars"].keys(), {"cycles"})

    def test_multi_pillar_with_combine_with_applied(self):
        record = _bridge_only_record()
        record["pillars"]["dep"] = _dep_only_record()["pillars"]["dep"]
        record["combine_with_applied"] = [
            {
                "hook": "bridge.event_sink",
                "from_pillar": "dep",
                "to_pillar": "bridge",
                "applied": True,
                "detail": "RuntimeEventLog passed as the backend Bridge's own event_sink",
            }
        ]
        ecosystem_resolution.save_resolution_record(record, self.path)
        loaded = ecosystem_resolution.load_resolution_record(self.path)
        self.assertEqual(loaded["pillars"].keys(), {"bridge", "dep"})
        self.assertTrue(loaded["combine_with_applied"][0]["applied"])

    def test_zero_pillars_refused(self):
        record = _cycles_only_record()
        record["pillars"] = {}
        with self.assertRaises(ecosystem_resolution.EcosystemResolutionError):
            ecosystem_resolution.save_resolution_record(record, self.path)
        self.assertFalse(self.path.exists())

    def test_unknown_pillar_key_refused(self):
        record = _cycles_only_record()
        record["pillars"]["not_a_real_pillar"] = {}
        with self.assertRaises(ecosystem_resolution.EcosystemResolutionError):
            ecosystem_resolution.save_resolution_record(record, self.path)

    def test_incomplete_bridge_entry_refused(self):
        record = _bridge_only_record()
        del record["pillars"]["bridge"]["runtimes"][0]["registry"]
        with self.assertRaises(ecosystem_resolution.EcosystemResolutionError):
            ecosystem_resolution.save_resolution_record(record, self.path)

    def test_bridge_entry_without_language_refused(self):
        # language is never inferred from a file extension or left
        # implicit -- a runtime entry with no explicit language is
        # exactly as incomplete as one missing "registry".
        record = _bridge_only_record()
        del record["pillars"]["bridge"]["runtimes"][0]["language"]
        with self.assertRaises(ecosystem_resolution.EcosystemResolutionError):
            ecosystem_resolution.save_resolution_record(record, self.path)

    def test_ported_runtime_language_round_trips(self):
        # The reference implementation is Python (backend) / JavaScript
        # (frontend), but a runtime's own Bridge can genuinely be ported
        # into any language -- proves the schema doesn't special-case or
        # restrict the value to the two reference languages.
        record = _bridge_only_record()
        record["pillars"]["bridge"]["runtimes"][0]["language"] = "Go"
        ecosystem_resolution.save_resolution_record(record, self.path)
        loaded = ecosystem_resolution.load_resolution_record(self.path)
        self.assertEqual(loaded["pillars"]["bridge"]["runtimes"][0]["language"], "Go")

    def test_save_overwrites_freely(self):
        # Unlike episode_store.save_episode, this is current-truth, not an
        # append-only log -- re-saving to the same path must never refuse.
        ecosystem_resolution.save_resolution_record(_cycles_only_record(), self.path)
        ecosystem_resolution.save_resolution_record(_bridge_only_record(), self.path)
        loaded = ecosystem_resolution.load_resolution_record(self.path)
        self.assertEqual(loaded["pillars"].keys(), {"bridge"})

    def test_load_refuses_schema_invalid_file_on_disk(self):
        # A file that was somehow written invalid (hand-edited, a bug
        # elsewhere) must be refused on load too, not silently trusted.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text('{"resolution_id": "bad", "pillars": {}}', encoding="utf-8")
        with self.assertRaises(ecosystem_resolution.EcosystemResolutionError):
            ecosystem_resolution.load_resolution_record(self.path)


if __name__ == "__main__":
    unittest.main()
