"""Coverage for state_ref.py: content_hash determinism/sensitivity, and
the vcs probe's graceful degrade when repo_root isn't a real git working
tree (proving DEP's own storage model never depends on git), plus a real
positive probe against this repository's own actual git history (proving
the git-aware half genuinely works, not just that it fails safely).

Run from the repository root:
    python -m unittest blueprint.dep.tests.test_state_ref -v
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from blueprint.dep import state_ref

_REPO_ROOT = Path(__file__).resolve().parents[3]


class StateRefTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_same_content_same_hash(self):
        f = self.root / "a.txt"
        f.write_text("hello", encoding="utf-8")
        first = state_ref.capture_state_ref([f])
        second = state_ref.capture_state_ref([f])
        self.assertEqual(first["content_hash"], second["content_hash"])

    def test_different_content_different_hash(self):
        f = self.root / "a.txt"
        f.write_text("hello", encoding="utf-8")
        before = state_ref.capture_state_ref([f])
        f.write_text("goodbye", encoding="utf-8")
        after = state_ref.capture_state_ref([f])
        self.assertNotEqual(before["content_hash"], after["content_hash"])

    def test_added_file_changes_hash_even_with_unchanged_bytes_elsewhere(self):
        a = self.root / "a.txt"
        a.write_text("hello", encoding="utf-8")
        before = state_ref.capture_state_ref([self.root])
        (self.root / "b.txt").write_text("hello", encoding="utf-8")  # same bytes, new file
        after = state_ref.capture_state_ref([self.root])
        self.assertNotEqual(before["content_hash"], after["content_hash"])

    def test_no_repo_root_omits_vcs(self):
        f = self.root / "a.txt"
        f.write_text("x", encoding="utf-8")
        result = state_ref.capture_state_ref([f])
        self.assertNotIn("vcs", result)

    def test_non_git_repo_root_omits_vcs_not_raises(self):
        f = self.root / "a.txt"
        f.write_text("x", encoding="utf-8")
        result = state_ref.capture_state_ref([f], repo_root=self.root)
        self.assertNotIn("vcs", result)

    def test_real_git_repo_root_populates_vcs(self):
        f = _REPO_ROOT / "blueprint" / "dep" / "state_ref.py"
        result = state_ref.capture_state_ref([f], repo_root=_REPO_ROOT)
        self.assertIn("vcs", result)
        self.assertEqual(result["vcs"]["system"], "git")
        self.assertRegex(result["vcs"]["commit"], r"^[0-9a-f]{40}$")
        self.assertIn("dirty", result["vcs"])


if __name__ == "__main__":
    unittest.main()
