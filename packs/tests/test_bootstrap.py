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


class QuestionsTests(unittest.TestCase):
    def _ids(self, answers=None):
        return [q["id"] for q in bootstrap.applicable_questions(answers)]

    def test_start_of_flow_has_no_bridge_questions(self):
        # Nothing answered yet. `project_kind`/`app_runtimes` are
        # unconditional (neither describes the Bridge) so both show up
        # immediately; every language question needs `pillars` AND
        # `app_runtimes` answered first, so none of them appear yet.
        self.assertEqual(self._ids(), ["pillars", "project_kind", "app_runtimes", "location"])

    def test_project_kind_is_closed_with_new_and_existing_options(self):
        questions = {q["id"]: q for q in bootstrap.applicable_questions()}
        self.assertEqual(questions["project_kind"]["kind"], "closed")
        self.assertEqual(questions["project_kind"]["options"], ["new", "existing"])

    def test_bridge_not_chosen_asks_app_language_not_bridge_language(self):
        # Real, observed failure this locks in: a dep+cycles-only run (no
        # Bridge pillar at all) was asked a Bridge-worded question with no
        # Bridge to compare to. The fix: mutually exclusive question
        # pairs per runtime -- bridge_language_* only WITH a Bridge,
        # app_language_* only WITHOUT one, never both, never neither.
        ids = self._ids({"pillars": ["dep", "cycles"], "app_runtimes": "both"})
        self.assertNotIn("bridge_language_backend", ids)
        self.assertNotIn("bridge_language_frontend", ids)
        self.assertIn("app_language_backend", ids)
        self.assertIn("app_language_frontend", ids)

    def test_bridge_chosen_asks_bridge_language_not_app_language(self):
        ids = self._ids({"pillars": ["bridge"], "app_runtimes": "both"})
        self.assertIn("bridge_language_backend", ids)
        self.assertIn("bridge_language_frontend", ids)
        self.assertNotIn("app_language_backend", ids)
        self.assertNotIn("app_language_frontend", ids)

    def test_no_runtime_yet_shows_no_language_question_of_either_kind(self):
        # pillars answered, app_runtimes not yet -- neither language
        # question pair can apply until app_runtimes says which
        # runtime(s) actually exist, with a Bridge or without one.
        ids = self._ids({"pillars": ["bridge"]})
        self.assertIn("app_runtimes", ids)
        for missing in ("bridge_language_backend", "bridge_language_frontend", "app_language_backend", "app_language_frontend"):
            self.assertNotIn(missing, ids)

        ids_no_bridge = self._ids({"pillars": ["dep"]})
        for missing in ("bridge_language_backend", "bridge_language_frontend", "app_language_backend", "app_language_frontend"):
            self.assertNotIn(missing, ids_no_bridge)

    def test_backend_only_asks_backend_language_only(self):
        ids = self._ids({"pillars": ["bridge"], "app_runtimes": "backend"})
        self.assertIn("bridge_language_backend", ids)
        self.assertNotIn("bridge_language_frontend", ids)

        ids_no_bridge = self._ids({"pillars": ["dep"], "app_runtimes": "backend"})
        self.assertIn("app_language_backend", ids_no_bridge)
        self.assertNotIn("app_language_frontend", ids_no_bridge)

    def test_frontend_only_asks_frontend_language_only(self):
        ids = self._ids({"pillars": ["bridge"], "app_runtimes": "frontend"})
        self.assertIn("bridge_language_frontend", ids)
        self.assertNotIn("bridge_language_backend", ids)

        ids_no_bridge = self._ids({"pillars": ["dep"], "app_runtimes": "frontend"})
        self.assertIn("app_language_frontend", ids_no_bridge)
        self.assertNotIn("app_language_backend", ids_no_bridge)

    def test_both_asks_both_languages(self):
        ids = self._ids({"pillars": ["bridge"], "app_runtimes": "both"})
        self.assertIn("bridge_language_backend", ids)
        self.assertIn("bridge_language_frontend", ids)

        ids_no_bridge = self._ids({"pillars": ["dep"], "app_runtimes": "both"})
        self.assertIn("app_language_backend", ids_no_bridge)
        self.assertIn("app_language_frontend", ids_no_bridge)

    def test_already_answered_questions_never_reappear(self):
        # pillars and app_runtimes are both already answered -- neither
        # should show up again even though app_runtimes still
        # technically "applies" (it's unconditional) given these answers.
        ids = self._ids({"pillars": ["bridge"], "app_runtimes": "both"})
        self.assertNotIn("pillars", ids)
        self.assertNotIn("app_runtimes", ids)

    def test_bridge_language_options_are_the_reference_language_only(self):
        # Exactly one real option each -- the reference implementation's
        # own language -- never a second, redundant "write your own"
        # entry duplicating the free-text fallback.
        questions = {q["id"]: q for q in bootstrap.applicable_questions({"pillars": ["bridge"], "app_runtimes": "both"})}
        self.assertEqual(questions["bridge_language_backend"]["options"], ["Python"])
        self.assertEqual(questions["bridge_language_frontend"]["options"], ["JavaScript"])

    def test_app_language_options_are_just_the_fallback(self):
        # No reference language to suggest for a Bridge-free runtime
        # (unlike bridge_language_backend's "Python") -- just the one
        # honest fallback option, same as every other Bridge-free case.
        questions = {q["id"]: q for q in bootstrap.applicable_questions({"pillars": ["dep"], "app_runtimes": "both"})}
        self.assertEqual(questions["app_language_backend"]["options"], ["Not yet / I don't know"])
        self.assertEqual(questions["app_language_backend"]["kind"], "open_with_default")
        self.assertEqual(questions["app_language_frontend"]["options"], ["Not yet / I don't know"])

    def test_location_has_no_options_at_all(self):
        # Genuinely open -- options: None AND no options_source, unlike
        # pillars below. This is the one question with nothing to select.
        questions = {q["id"]: q for q in bootstrap.applicable_questions()}
        self.assertIsNone(questions["location"]["options"])
        self.assertEqual(questions["location"]["kind"], "open")
        self.assertNotIn("options_source", questions["location"])

    def test_pillars_has_no_hardcoded_options_but_is_still_a_selection_question(self):
        # options: None here does NOT mean "ask in plain text" -- it
        # means the real options live in list-pillars' own output.
        # options_source must be present and point at that command, or
        # an agent reading only `options` has no way to tell this apart
        # from a genuinely open question like location.
        questions = {q["id"]: q for q in bootstrap.applicable_questions()}
        self.assertIsNone(questions["pillars"]["options"])
        self.assertEqual(questions["pillars"]["options_source"], "python -m packs.bootstrap list-pillars")

    def test_print_questions_notes_pillars_options_source(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            bootstrap.print_questions()
        output = buf.getvalue()
        self.assertIn("still a selection question", output)
        self.assertIn("list-pillars", output)

    def test_next_question_returns_none_when_nothing_left(self):
        answers = {
            "pillars": ["cycles"], "project_kind": "new", "app_runtimes": "both",
            "app_language_backend": "Python", "app_language_frontend": "TypeScript",
            "location": "/tmp/x",
        }
        self.assertIsNone(bootstrap.next_question(answers))

    def test_print_questions_default_shows_only_the_next_one(self):
        # The regression this whole command exists to prevent: seeing
        # more than one question at once invites asking several without
        # re-checking in between. Default output must be exactly one.
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            bootstrap.print_questions({"pillars": ["bridge"], "project_kind": "new", "app_runtimes": "backend"})
        output = buf.getvalue()
        self.assertIn("[bridge_language_backend]", output)
        self.assertIn("Python", output)
        self.assertNotIn("bridge_language_frontend", output)
        self.assertNotIn("app_language", output)
        self.assertNotIn("location", output)

    def test_print_questions_all_shows_every_remaining_one(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            bootstrap.print_questions({"pillars": ["bridge"], "project_kind": "new", "app_runtimes": "backend"}, show_all=True)
        output = buf.getvalue()
        self.assertIn("[bridge_language_backend]", output)
        self.assertIn("location", output)

    def test_print_questions_all_shows_app_language_when_bridge_free(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            bootstrap.print_questions({"pillars": ["dep"], "project_kind": "new", "app_runtimes": "backend"}, show_all=True)
        output = buf.getvalue()
        self.assertNotIn("bridge_language_backend", output)
        self.assertIn("[app_language_backend]", output)
        self.assertIn("location", output)

    def test_print_questions_nothing_left_message(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            bootstrap.print_questions({
                "pillars": ["cycles"], "project_kind": "new", "app_runtimes": "both",
                "app_language_backend": "x", "app_language_frontend": "y", "location": "y",
            })
        self.assertIn("Nothing left to ask.", buf.getvalue())

    def test_full_loop_never_skips_a_question(self):
        # Simulates exactly what a real Bootstrap agent should do:
        # repeatedly call next_question(), answer it, feed the answer
        # back, until None. Proves the whole Bridge+both-runtimes flow
        # surfaces every single question, in order, none skipped, none
        # repeated -- the exact failure mode a real run hit for real.
        answers: dict = {}
        seen_ids = []
        canned = {
            "pillars": ["bridge", "dep"],
            "project_kind": "new",
            "app_runtimes": "both",
            "bridge_language_backend": "Python",
            "bridge_language_frontend": "JavaScript",
            "location": "/tmp/my-app",
        }
        for _ in range(20):  # hard cap -- a real infinite loop is itself a test failure
            q = bootstrap.next_question(answers)
            if q is None:
                break
            self.assertNotIn(q["id"], seen_ids, f"{q['id']} was asked twice")
            seen_ids.append(q["id"])
            answers[q["id"]] = canned[q["id"]]
        else:
            self.fail("loop never terminated -- next_question() kept returning something")

        self.assertEqual(
            seen_ids,
            ["pillars", "project_kind", "app_runtimes", "bridge_language_backend", "bridge_language_frontend", "location"],
        )

    def test_full_loop_never_skips_a_question_bridge_free(self):
        # Mirror of the above for the app_language_backend/frontend pair
        # -- proves that path surfaces every question too, none skipped.
        answers: dict = {}
        seen_ids = []
        canned = {
            "pillars": ["dep", "cycles"],
            "project_kind": "existing",
            "app_runtimes": "both",
            "app_language_backend": "C#",
            "app_language_frontend": "TypeScript",
            "location": "D:/simcity",
        }
        for _ in range(20):
            q = bootstrap.next_question(answers)
            if q is None:
                break
            self.assertNotIn(q["id"], seen_ids, f"{q['id']} was asked twice")
            seen_ids.append(q["id"])
            answers[q["id"]] = canned[q["id"]]
        else:
            self.fail("loop never terminated -- next_question() kept returning something")

        self.assertEqual(
            seen_ids,
            ["pillars", "project_kind", "app_runtimes", "app_language_backend", "app_language_frontend", "location"],
        )

    def test_cli_questions_subprocess_no_answers(self):
        result = subprocess.run(
            [sys.executable, "-m", "packs.bootstrap", "questions"],
            cwd=str(_REPO_ROOT), capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[pillars]", result.stdout)
        self.assertNotIn("app_runtimes", result.stdout)

    def test_cli_questions_subprocess_with_answers_file_shows_only_next(self):
        with tempfile.TemporaryDirectory() as tmp:
            answers_path = Path(tmp) / "answers.json"
            answers_path.write_text(json.dumps({"pillars": ["bridge"], "project_kind": "new", "app_runtimes": "both"}), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "packs.bootstrap", "questions", "--answers-file", str(answers_path)],
                cwd=str(_REPO_ROOT), capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("bridge_language_backend", result.stdout)
        self.assertNotIn("bridge_language_frontend", result.stdout)
        self.assertNotIn("[pillars]", result.stdout)

    def test_cli_questions_subprocess_all_flag_shows_everything(self):
        with tempfile.TemporaryDirectory() as tmp:
            answers_path = Path(tmp) / "answers.json"
            answers_path.write_text(json.dumps({"pillars": ["bridge"], "project_kind": "new", "app_runtimes": "both"}), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "packs.bootstrap", "questions", "--answers-file", str(answers_path), "--all"],
                cwd=str(_REPO_ROOT), capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("bridge_language_backend", result.stdout)
        self.assertIn("bridge_language_frontend", result.stdout)


class ResolveDescribeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        # NOTE: self.pillars_file lives directly inside self.root, so
        # most tests below that pass ecosystem_root=self.root incidentally
        # satisfy resolve()'s own "real content besides state/" check just
        # by having written this fixture file first -- not because it
        # simulates real copied pack content. RealContentCheckTests below
        # exercises that check deliberately and explicitly instead.
        self.pillars_file = self.root / "pillars.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_resolve_then_describe_round_trip(self):
        self.pillars_file.write_text(json.dumps({
            "cycles": {"cycle_doc": "blueprint/1-CYCLE.md", "rules_doc": "blueprint/2-RULES.md"},
            "dep": {"dep_root": "blueprint/dep", "episodes_dir": "state/episodes"},
        }), encoding="utf-8")

        out_path = bootstrap.resolve(self.root, self.pillars_file, "new", "both", resolved_by="test-agent")
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

        out_path = bootstrap.resolve(self.root, self.pillars_file, "new", "backend")
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
        (self.root / "my-app" / "1-CYCLE.md").write_text("x", encoding="utf-8")  # simulate real copied content

        original_cwd = Path.cwd()
        try:
            os.chdir(self.root)
            out_path = bootstrap.resolve(Path("my-app"), self.pillars_file, "new", "backend")
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

        out_path = bootstrap.resolve(self.root, self.pillars_file, "new", "backend", combine_with_file=combine_file)
        record = ecosystem_resolution.load_resolution_record(out_path)
        self.assertEqual(len(record["combine_with_applied"]), 1)
        self.assertTrue(record["combine_with_applied"][0]["applied"])

    def test_empty_pillars_refused(self):
        self.pillars_file.write_text("{}", encoding="utf-8")
        with self.assertRaises(ecosystem_resolution.EcosystemResolutionError):
            bootstrap.resolve(self.root, self.pillars_file, "new", "backend")

    def test_describe_missing_file_exits_1(self):
        with self.assertRaises(SystemExit) as ctx:
            bootstrap.describe(self.root / "nope.json")
        self.assertEqual(ctx.exception.code, 1)

    def test_cli_subprocess_resolve_and_describe(self):
        self.pillars_file.write_text(json.dumps({
            "bridge": {
                "runtimes": [
                    {
                        "name": "backend", "language": "Python",
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
                "--project-kind", "new",
                "--app-runtimes", "backend",
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
        self.assertIn("project_kind:   new", describe_result.stdout)

    def test_cli_list_pillars_subprocess(self):
        result = subprocess.run(
            [sys.executable, "-m", "packs.bootstrap", "list-pillars"],
            cwd=str(_REPO_ROOT), capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Bridge + Cycles + DEP", result.stdout)


class RealContentCheckTests(unittest.TestCase):
    """Deliberate, explicit coverage for resolve()'s own refusal when
    ecosystem_root shows no real evidence anything was actually copied
    or ported into it -- the exact real-world failure this check exists
    to catch: a Bootstrap agent ran every question, wrote a fully
    schema-valid resolution record naming real-looking file paths, and
    never once copied an actual file. `D:\\simcity` ended up with nothing
    but `state/ecosystem-resolution.json` -- a record describing an
    ecosystem that plainly doesn't exist.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.pillars_file = self.root / ".." / "pillars.json"  # deliberately OUTSIDE self.root
        self.pillars_file = self.pillars_file.resolve()
        self.pillars_file.write_text(json.dumps({"cycles": {"cycle_doc": "x", "rules_doc": "y"}}), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()
        self.pillars_file.unlink(missing_ok=True)

    def test_refuses_when_ecosystem_root_does_not_exist(self):
        missing = self.root / "does-not-exist-yet"
        with self.assertRaises(ecosystem_resolution.EcosystemResolutionError) as ctx:
            bootstrap.resolve(missing, self.pillars_file, "new", "backend")
        self.assertIn("no real content", str(ctx.exception))

    def test_refuses_when_ecosystem_root_is_completely_empty(self):
        with self.assertRaises(ecosystem_resolution.EcosystemResolutionError) as ctx:
            bootstrap.resolve(self.root, self.pillars_file, "new", "backend")
        self.assertIn("no real content", str(ctx.exception))

    def test_refuses_when_ecosystem_root_has_only_a_state_directory(self):
        # The exact D:\simcity shape: state/ already exists (e.g. from a
        # previous failed attempt), but nothing else does.
        (self.root / "state").mkdir()
        (self.root / "state" / "leftover.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(ecosystem_resolution.EcosystemResolutionError) as ctx:
            bootstrap.resolve(self.root, self.pillars_file, "new", "backend")
        self.assertIn("no real content", str(ctx.exception))

    def test_succeeds_once_real_content_exists_alongside_state(self):
        (self.root / "state").mkdir()
        (self.root / "1-CYCLE.md").write_text("real copied content", encoding="utf-8")
        out_path = bootstrap.resolve(self.root, self.pillars_file, "new", "backend")
        self.assertTrue(out_path.exists())

    def test_succeeds_with_real_content_and_no_state_dir_yet(self):
        # state/ doesn't need to already exist -- resolve() creates it
        # itself when writing the record; only "is there real content"
        # matters, not "does state/ already exist".
        (self.root / "1-CYCLE.md").write_text("real copied content", encoding="utf-8")
        out_path = bootstrap.resolve(self.root, self.pillars_file, "new", "backend")
        self.assertTrue(out_path.exists())

    def test_existing_project_kind_trivially_satisfies_real_content_check(self):
        # An "existing" project already has real files before any pillar
        # adoption starts -- resolve() never needs new scaffold content
        # written first for this case, unlike "new".
        (self.root / "MyExistingApp.csproj").write_text("real pre-existing project", encoding="utf-8")
        out_path = bootstrap.resolve(self.root, self.pillars_file, "existing", "backend")
        record = ecosystem_resolution.load_resolution_record(out_path)
        self.assertEqual(record["project_kind"], "existing")

    def test_app_language_recorded_for_bridge_free_ecosystem(self):
        (self.root / "MyExistingApp.csproj").write_text("real pre-existing project", encoding="utf-8")
        out_path = bootstrap.resolve(
            self.root, self.pillars_file, "existing", "both",
            app_language_backend="C#", app_language_frontend="TypeScript",
        )
        record = ecosystem_resolution.load_resolution_record(out_path)
        self.assertEqual(record["app_language"], {"backend": "C#", "frontend": "TypeScript"})

    def test_app_language_absent_when_not_passed(self):
        (self.root / "1-CYCLE.md").write_text("real copied content", encoding="utf-8")
        out_path = bootstrap.resolve(self.root, self.pillars_file, "new", "backend")
        record = ecosystem_resolution.load_resolution_record(out_path)
        self.assertNotIn("app_language", record)

    def test_cli_resolve_refuses_on_empty_ecosystem_root(self):
        result = subprocess.run(
            [
                sys.executable, "-m", "packs.bootstrap", "resolve",
                "--ecosystem-root", str(self.root),
                "--pillars-file", str(self.pillars_file),
                "--project-kind", "new",
                "--app-runtimes", "backend",
            ],
            cwd=str(_REPO_ROOT), capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("no real content", result.stderr)
        self.assertFalse((self.root / "state").exists(), "refused resolve must not write anything at all")


class CheckScopeTests(unittest.TestCase):
    """Coverage for check_scope() -- the proactive, run-anytime-during-
    Phase-1-7 half of the same check blueprint/dep/finish_cycle.py now
    runs as a hard publish-time gate. Real, observed failure both exist
    for: a Builder agent, given a DEP+Cycles-only resolution with no
    Bridge pillar adopted at all, built a full contracts/capabilities
    tree anyway -- packs/README.md's own prose telling it not to was not
    enough on its own.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.pillars_file = self.root / ".." / "pillars.json"
        self.pillars_file = self.pillars_file.resolve()

    def tearDown(self):
        self._tmp.cleanup()
        self.pillars_file.unlink(missing_ok=True)

    def _resolve_no_bridge(self):
        self.pillars_file.write_text(json.dumps({
            "dep": {"dep_root": "d", "episodes_dir": "e"},
            "cycles": {"cycle_doc": "x", "rules_doc": "y"},
        }), encoding="utf-8")
        bootstrap.resolve(self.root, self.pillars_file, "existing", "backend")

    def _resolve_with_bridge(self):
        self.pillars_file.write_text(json.dumps({
            "bridge": {
                "runtimes": [
                    {
                        "name": "backend", "language": "Python",
                        "bridge": "x", "registry": "x", "policy": "x", "selector": "x",
                        "contracts_dir": "x", "implementation_map": {},
                    }
                ]
            },
        }), encoding="utf-8")
        bootstrap.resolve(self.root, self.pillars_file, "new", "backend")

    def test_no_resolution_record_raises(self):
        with self.assertRaises(ecosystem_resolution.EcosystemResolutionError):
            bootstrap.check_scope(self.root)

    def test_clean_no_bridge_ecosystem_returns_empty(self):
        (self.root / "MyApp.csproj").write_text("real content", encoding="utf-8")
        self._resolve_no_bridge()
        self.assertEqual(bootstrap.check_scope(self.root), [])

    def test_leaky_no_bridge_ecosystem_returns_violations(self):
        (self.root / "contracts").mkdir()
        (self.root / "contracts" / "x.contract.yaml").write_text("identity: {}", encoding="utf-8")
        self._resolve_no_bridge()
        leaks = bootstrap.check_scope(self.root)
        self.assertIn("contracts/", leaks)

    def test_bridge_adopted_never_flags_contracts(self):
        # A real contracts/ dir is exactly what a Bridge-adopting
        # ecosystem is SUPPOSED to have -- never a violation.
        (self.root / "contracts").mkdir()
        (self.root / "contracts" / "x.contract.yaml").write_text("identity: {}", encoding="utf-8")
        self._resolve_with_bridge()
        self.assertEqual(bootstrap.check_scope(self.root), [])

    def test_cli_clean_exits_0(self):
        (self.root / "MyApp.csproj").write_text("real content", encoding="utf-8")
        self._resolve_no_bridge()
        result = subprocess.run(
            [sys.executable, "-m", "packs.bootstrap", "check-scope", "--ecosystem-root", str(self.root)],
            cwd=str(_REPO_ROOT), capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No pillar-scope leakage found.", result.stdout)

    def test_cli_leaky_exits_1(self):
        (self.root / "capabilities").mkdir()
        (self.root / "capabilities" / "manifest.yaml").write_text(
            "capability_id: x\nimplementations: []\n", encoding="utf-8",
        )
        self._resolve_no_bridge()
        result = subprocess.run(
            [sys.executable, "-m", "packs.bootstrap", "check-scope", "--ecosystem-root", str(self.root)],
            cwd=str(_REPO_ROOT), capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("capabilities", result.stderr)


if __name__ == "__main__":
    unittest.main()
