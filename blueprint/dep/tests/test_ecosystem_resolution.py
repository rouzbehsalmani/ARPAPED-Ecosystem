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
        "project_kind": "new",
        "app_runtimes": "backend",
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
        "project_kind": "existing",
        "app_runtimes": "backend",
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
        "project_kind": "new",
        "app_runtimes": "both",
        "pillars": {
            "cycles": {
                "cycle_doc": "blueprint/1-CYCLE.md",
                "rules_doc": "blueprint/2-RULES.md",
            }
        },
        "resolved_at": "2026-09-14T00:00:00Z",
        "app_language": {"backend": "C#", "frontend": "TypeScript"},
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

    def test_missing_project_kind_refused(self):
        # Never left implicit, same reasoning as a Bridge runtime's own
        # language -- the wrong guess here (a Builder assuming "new" when
        # a project already existed) is a real, observed failure: it
        # scaffolded a whole fake application instead of recognizing an
        # existing one just needed pillar tooling merged into it.
        record = _cycles_only_record()
        del record["project_kind"]
        with self.assertRaises(ecosystem_resolution.EcosystemResolutionError):
            ecosystem_resolution.save_resolution_record(record, self.path)

    def test_invalid_project_kind_refused(self):
        record = _cycles_only_record()
        record["project_kind"] = "not-a-real-value"
        with self.assertRaises(ecosystem_resolution.EcosystemResolutionError):
            ecosystem_resolution.save_resolution_record(record, self.path)

    def test_existing_project_kind_round_trips(self):
        record = _dep_only_record()
        self.assertEqual(record["project_kind"], "existing")
        ecosystem_resolution.save_resolution_record(record, self.path)
        loaded = ecosystem_resolution.load_resolution_record(self.path)
        self.assertEqual(loaded["project_kind"], "existing")

    def test_missing_app_runtimes_refused(self):
        record = _dep_only_record()
        del record["app_runtimes"]
        with self.assertRaises(ecosystem_resolution.EcosystemResolutionError):
            ecosystem_resolution.save_resolution_record(record, self.path)

    def test_invalid_app_runtimes_refused(self):
        record = _dep_only_record()
        record["app_runtimes"] = "not-a-real-runtime"
        with self.assertRaises(ecosystem_resolution.EcosystemResolutionError):
            ecosystem_resolution.save_resolution_record(record, self.path)

    def test_app_language_absent_for_bridge_only_is_valid(self):
        # A Bridge-adopting ecosystem has nothing to put in app_language --
        # pillars.bridge.runtimes[].language is the single source of truth
        # for that runtime's language instead. Absence here is expected,
        # not a gap this schema should flag.
        record = _bridge_only_record()
        self.assertNotIn("app_language", record)
        ecosystem_resolution.save_resolution_record(record, self.path)

    def test_app_language_round_trips_for_bridge_free_ecosystem(self):
        # The real, observed failure this whole field exists to fix: a
        # Bridge-free ecosystem's app_language answer ("C#") was asked,
        # given, and never stored anywhere the Builder could ever read it.
        record = _cycles_only_record()
        self.assertEqual(record["app_language"], {"backend": "C#", "frontend": "TypeScript"})
        ecosystem_resolution.save_resolution_record(record, self.path)
        loaded = ecosystem_resolution.load_resolution_record(self.path)
        self.assertEqual(loaded["app_language"], {"backend": "C#", "frontend": "TypeScript"})

    def test_app_language_empty_object_refused(self):
        # minProperties: 1 -- an empty app_language is indistinguishable
        # from "nothing was ever recorded," so it's refused outright
        # rather than accepted as a valid-but-useless value.
        record = _cycles_only_record()
        record["app_language"] = {}
        with self.assertRaises(ecosystem_resolution.EcosystemResolutionError):
            ecosystem_resolution.save_resolution_record(record, self.path)

    def test_app_language_unknown_runtime_key_refused(self):
        record = _cycles_only_record()
        record["app_language"] = {"mobile": "Kotlin"}
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


class DetectBridgeLeakageTests(unittest.TestCase):
    """Deliberate, explicit coverage for detect_bridge_leakage() -- the
    real, observed failure this exists to catch: a Builder agent, given a
    DEP+Cycles-only resolution with no Bridge pillar adopted at all, built
    a full contracts/capabilities/manifest.yaml tree anyway, despite
    packs/README.md's own prose already saying not to.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_root_returns_empty(self):
        self.assertEqual(ecosystem_resolution.detect_bridge_leakage(self.root / "nope"), [])

    def test_clean_project_returns_empty(self):
        (self.root / "MyApp.csproj").write_text("real content", encoding="utf-8")
        (self.root / "appsettings.json").write_text('{"key": "value"}', encoding="utf-8")
        self.assertEqual(ecosystem_resolution.detect_bridge_leakage(self.root), [])

    def test_contract_yaml_file_detected(self):
        (self.root / "contracts").mkdir()
        (self.root / "contracts" / "simcity.build.contract.yaml").write_text("identity: {}", encoding="utf-8")
        leaks = ecosystem_resolution.detect_bridge_leakage(self.root)
        self.assertIn("contracts/", leaks)
        self.assertIn(str(Path("contracts") / "simcity.build.contract.yaml"), leaks)

    def test_capability_manifest_content_detected(self):
        (self.root / "capabilities" / "build").mkdir(parents=True)
        (self.root / "capabilities" / "build" / "manifest.yaml").write_text(
            "capability_id: simcity.build\nimplementations: []\n", encoding="utf-8",
        )
        leaks = ecosystem_resolution.detect_bridge_leakage(self.root)
        self.assertIn(str(Path("capabilities") / "build" / "manifest.yaml"), leaks)

    def test_unrelated_manifest_yaml_not_flagged(self):
        # Content-checked, not filename-matched -- "manifest.yaml" alone
        # is too common a name to treat as a violation on its own.
        (self.root / "manifest.yaml").write_text("app_name: MyGame\nversion: 1.0\n", encoding="utf-8")
        self.assertEqual(ecosystem_resolution.detect_bridge_leakage(self.root), [])

    def test_capability_catalog_jsonl_detected(self):
        (self.root / "capability-catalog.jsonl").write_text("{}", encoding="utf-8")
        leaks = ecosystem_resolution.detect_bridge_leakage(self.root)
        self.assertIn("capability-catalog.jsonl", leaks)

    def test_state_directory_never_scanned(self):
        # A stale artifact under state/ (e.g. from a prior, since-reverted
        # Bridge adoption) is a cleanup problem, not evidence of a
        # currently-leaking ecosystem.
        (self.root / "state").mkdir()
        (self.root / "state" / "capability-catalog.jsonl").write_text("{}", encoding="utf-8")
        (self.root / "state" / "contracts").mkdir()
        (self.root / "state" / "contracts" / "x.contract.yaml").write_text("identity: {}", encoding="utf-8")
        self.assertEqual(ecosystem_resolution.detect_bridge_leakage(self.root), [])


if __name__ == "__main__":
    unittest.main()
