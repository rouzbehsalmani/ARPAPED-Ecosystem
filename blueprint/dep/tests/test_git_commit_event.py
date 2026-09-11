"""Coverage for git_commit_event.py: a REAL commit in a throwaway
temporary git repo, probed for real (sha/branch/message/files_changed
all actually observed, never asserted against hardcoded strings), the
loud-failure posture for a missing commit / non-git repo_root (the
deliberate contrast to state_ref.py's silent-omit posture), and a real
CLI subprocess round-trip -- mirroring test_finish_cycle.py's own style.

Run from the repository root:
    python -m unittest blueprint.dep.tests.test_git_commit_event -v
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from blueprint.dep import git_commit_event

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(repo_root), check=True, capture_output=True, text=True)


def _init_repo(repo_root: Path) -> None:
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "Test")


class GitCommitEventTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmp.name) / "repo"
        self.repo_root.mkdir()
        self.log_path = Path(self._tmp.name) / "state" / "git-commit-events.jsonl"
        _init_repo(self.repo_root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_records_real_commit_metadata(self):
        (self.repo_root / "a.txt").write_text("hello", encoding="utf-8")
        _git(self.repo_root, "add", "a.txt")
        _git(self.repo_root, "commit", "-q", "-m", "add a.txt")
        real_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(self.repo_root), capture_output=True, text=True, check=True,
        ).stdout.strip()

        event = git_commit_event.record_git_commit_event(self.log_path, self.repo_root)

        self.assertEqual(event["commit"], real_sha)
        self.assertEqual(len(event["commit"]), 40)
        self.assertEqual(event["message"], "add a.txt")
        self.assertEqual(event["files_changed"], ["a.txt"])
        self.assertIn("author", event)

    def test_event_appended_to_log_path(self):
        (self.repo_root / "a.txt").write_text("hello", encoding="utf-8")
        _git(self.repo_root, "add", "a.txt")
        _git(self.repo_root, "commit", "-q", "-m", "add a.txt")

        git_commit_event.record_git_commit_event(self.log_path, self.repo_root)

        lines = self.log_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        json.loads(lines[0])  # must be valid JSON

    def test_explicit_commit_sha_resolves_to_that_commit(self):
        (self.repo_root / "a.txt").write_text("first", encoding="utf-8")
        _git(self.repo_root, "add", "a.txt")
        _git(self.repo_root, "commit", "-q", "-m", "first commit")
        first_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(self.repo_root), capture_output=True, text=True, check=True,
        ).stdout.strip()
        (self.repo_root / "b.txt").write_text("second", encoding="utf-8")
        _git(self.repo_root, "add", "b.txt")
        _git(self.repo_root, "commit", "-q", "-m", "second commit")

        event = git_commit_event.record_git_commit_event(self.log_path, self.repo_root, commit=first_sha)

        self.assertEqual(event["commit"], first_sha)
        self.assertEqual(event["message"], "first commit")
        self.assertEqual(event["files_changed"], ["a.txt"])

    def test_unresolvable_commit_raises_loudly(self):
        (self.repo_root / "a.txt").write_text("hello", encoding="utf-8")
        _git(self.repo_root, "add", "a.txt")
        _git(self.repo_root, "commit", "-q", "-m", "add a.txt")

        with self.assertRaises(git_commit_event.GitCommitEventError):
            git_commit_event.record_git_commit_event(self.log_path, self.repo_root, commit="not-a-real-commit")

    def test_non_git_repo_root_raises_loudly(self):
        non_git_dir = Path(self._tmp.name) / "not-a-repo"
        non_git_dir.mkdir()
        with self.assertRaises(git_commit_event.GitCommitEventError):
            git_commit_event.record_git_commit_event(self.log_path, non_git_dir)

    def test_cli_subprocess_round_trip(self):
        (self.repo_root / "a.txt").write_text("hello", encoding="utf-8")
        _git(self.repo_root, "add", "a.txt")
        _git(self.repo_root, "commit", "-q", "-m", "cli test commit")

        result = subprocess.run(
            [
                sys.executable, "-m", "blueprint.dep.git_commit_event",
                "--log-path", str(self.log_path),
                "--repo-root", str(self.repo_root),
            ],
            cwd=str(_REPO_ROOT), capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        event = json.loads(result.stdout)
        self.assertEqual(event["message"], "cli test commit")
        self.assertTrue(self.log_path.exists())

    def test_cli_subprocess_missing_commit_exits_nonzero(self):
        result = subprocess.run(
            [
                sys.executable, "-m", "blueprint.dep.git_commit_event",
                "--log-path", str(self.log_path),
                "--repo-root", str(self.repo_root),
                "--commit", "not-a-real-commit",
            ],
            cwd=str(_REPO_ROOT), capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("NOT recorded", result.stderr)


if __name__ == "__main__":
    unittest.main()
