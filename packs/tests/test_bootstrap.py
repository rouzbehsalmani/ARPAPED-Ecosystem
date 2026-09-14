"""Coverage for packs/bootstrap.py -- proves list_pillars() stays in sync
with the real packs/*.yaml files (never hardcoded), and that resolve()/
describe() round-trip through blueprint.dep.ecosystem_resolution exactly
the way the CLI's own docstring claims.

Run from the repository root:
    python -m unittest packs.tests.test_bootstrap -v
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from blueprint.dep import ecosystem_resolution
from packs import bootstrap

_REPO_ROOT = Path(__file__).resolve().parents[2]


class ListPillarsTests(unittest.TestCase):
    def test_reads_all_three_real_packs(self):
        pillars = bootstrap._load_pack_descriptions()  # noqa: SLF001 -- exercising the real source-of-truth read
        self.assertEqual(set(pillars.keys()), {"bridge", "dep", "cycles"})
        for name, detail in pillars.items():
            self.assertTrue(detail["description"], f"{name} pack has an empty description")

    def test_prints_all_seven_non_empty_combinations(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            bootstrap.list_pillars()
        output = buf.getvalue()
        # 3 singles + 3 pairs + 1 triple = 7 non-empty subsets of 3 pillars,
        # in alphabetical order (names are sorted()) -- Bridge, Cycles, DEP.
        for combo in ["Bridge", "Cycles", "DEP", "Bridge + Cycles", "Bridge + DEP", "Cycles + DEP", "Bridge + Cycles + DEP"]:
            self.assertIn(combo, output)


class ResolveDescribeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.pillars_file = self.root / "pillars.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_resolve_then_describe_round_trip(self):
        self.pillars_file.write_text(json.dumps({
            "cycles": {"cycle_doc": "blueprint/1-CYCLE.md", "rules_doc": "blueprint/2-RULES.md"},
            "dep": {"dep_root": "blueprint/dep", "episodes_dir": "state/episodes"},
        }), encoding="utf-8")

        out_path = bootstrap.resolve(self.root, self.pillars_file, resolved_by="test-agent")
        self.assertTrue(out_path.exists())

        record = ecosystem_resolution.load_resolution_record(out_path)
        self.assertEqual(set(record["pillars"].keys()), {"cycles", "dep"})
        self.assertEqual(record["resolved_by"], "test-agent")
        self.assertTrue(record["resolution_id"].startswith("res-"))

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            bootstrap.describe(out_path)
        output = buf.getvalue()
        self.assertIn("cycles", output)
        self.assertIn("dep", output)
        self.assertIn("test-agent", output)

    def test_default_out_path_is_ecosystem_root_state(self):
        self.pillars_file.write_text(json.dumps({
            "cycles": {"cycle_doc": "x", "rules_doc": "y"},
        }), encoding="utf-8")

        out_path = bootstrap.resolve(self.root, self.pillars_file)
        self.assertEqual(out_path, self.root / "state" / "ecosystem-resolution.json")

    def test_relative_ecosystem_root_stored_as_absolute(self):
        # A relative --ecosystem-root (e.g. "my-app") must never end up
        # stored verbatim -- it would be ambiguous the moment anything
        # reads the record back from a different working directory than
        # whichever one `resolve` happened to run from.
        self.pillars_file.write_text(json.dumps({
            "cycles": {"cycle_doc": "x", "rules_doc": "y"},
        }), encoding="utf-8")
        (self.root / "my-app").mkdir()

        original_cwd = Path.cwd()
        try:
            os.chdir(self.root)
            out_path = bootstrap.resolve(Path("my-app"), self.pillars_file)
        finally:
            os.chdir(original_cwd)

        record = ecosystem_resolution.load_resolution_record(out_path)
        stored_root = Path(record["ecosystem_root"])
        self.assertTrue(stored_root.is_absolute(), f"expected an absolute path, got {stored_root}")
        self.assertEqual(stored_root, (self.root / "my-app").resolve())

    def test_combine_with_file_is_included(self):
        self.pillars_file.write_text(json.dumps({
            "cycles": {"cycle_doc": "x", "rules_doc": "y"},
            "dep": {"dep_root": "d", "episodes_dir": "e"},
        }), encoding="utf-8")
        combine_file = self.root / "combine.json"
        combine_file.write_text(json.dumps([
            {"hook": "dep.finish_cycle_catalog_path", "from_pillar": "dep", "to_pillar": "cycles", "applied": True, "detail": "catalog_path=None"},
        ]), encoding="utf-8")

        out_path = bootstrap.resolve(self.root, self.pillars_file, combine_with_file=combine_file)
        record = ecosystem_resolution.load_resolution_record(out_path)
        self.assertEqual(len(record["combine_with_applied"]), 1)
        self.assertTrue(record["combine_with_applied"][0]["applied"])

    def test_empty_pillars_refused(self):
        self.pillars_file.write_text("{}", encoding="utf-8")
        with self.assertRaises(ecosystem_resolution.EcosystemResolutionError):
            bootstrap.resolve(self.root, self.pillars_file)

    def test_describe_missing_file_exits_1(self):
        with self.assertRaises(SystemExit) as ctx:
            bootstrap.describe(self.root / "nope.json")
        self.assertEqual(ctx.exception.code, 1)

    def test_cli_subprocess_resolve_and_describe(self):
        self.pillars_file.write_text(json.dumps({
            "bridge": {
                "runtimes": [
                    {
                        "name": "backend",
                        "bridge": "x", "registry": "x", "policy": "x", "selector": "x",
                        "contracts_dir": "x", "implementation_map": {},
                    }
                ]
            },
        }), encoding="utf-8")
        out_path = self.root / "state" / "ecosystem-resolution.json"

        resolve_result = subprocess.run(
            [
                sys.executable, "-m", "packs.bootstrap", "resolve",
                "--ecosystem-root", str(self.root),
                "--pillars-file", str(self.pillars_file),
                "--out", str(out_path),
            ],
            cwd=str(_REPO_ROOT), capture_output=True, text=True,
        )
        self.assertEqual(resolve_result.returncode, 0, resolve_result.stderr)
        self.assertEqual(Path(resolve_result.stdout.strip()), out_path)

        describe_result = subprocess.run(
            [sys.executable, "-m", "packs.bootstrap", "describe", str(out_path)],
            cwd=str(_REPO_ROOT), capture_output=True, text=True,
        )
        self.assertEqual(describe_result.returncode, 0, describe_result.stderr)
        self.assertIn("bridge", describe_result.stdout)

    def test_cli_list_pillars_subprocess(self):
        result = subprocess.run(
            [sys.executable, "-m", "packs.bootstrap", "list-pillars"],
            cwd=str(_REPO_ROOT), capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Bridge + Cycles + DEP", result.stdout)


if __name__ == "__main__":
    unittest.main()
