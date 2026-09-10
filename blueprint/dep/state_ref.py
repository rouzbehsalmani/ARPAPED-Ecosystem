"""Captures an immutable identifier for `resulting_state` at the moment a
cycle completes (blueprint/dep/MANIFEST.yaml's state_ref) -- the fix for
`resulting_state` (agent-cycle-report.schema.json) being a live path
string that LATER cycles go on to mutate: an old episode's own "what did
the code actually look like then" is not recoverable from the episode
alone once that path's contents have since changed, only from
archaeology entirely outside DEP.

Two independent signals, captured together, never one substituting for
the other:

  - `content_hash`: a sha256 over the given `paths`' own bytes, walked
    and sorted for determinism. ALWAYS computable, no external tool
    required -- this is what makes DEP's own historical-reconstruction
    story never DEPEND on git being present, installed, or even used for
    this application at all. `blueprint/dep/` stays generic here the same
    way every other tool in it does: the caller decides which paths
    actually define "this cycle's resulting state" (contracts, manifests,
    a generated catalog -- never state/episodes/ itself, which would make
    the hash depend on its own prior output) and supplies them explicitly;
    nothing here defaults to walking an entire application tree.
  - `vcs`: OPTIONAL git commit/branch/dirty-state, captured ONLY when a
    real git repository is actually found at `repo_root` (a plain,
    non-fatal `git rev-parse` probe, never assumed). Genuinely useful
    supplementary metadata when present -- a human or a future agent can
    `git show <commit>` to see the literal tree -- but exactly that:
    supplementary. A `repo_root` that isn't a git working tree, or has no
    `git` on PATH at all, silently omits this key rather than failing;
    DEP's own storage model never requires it (confirmed with the
    operator: "should not depend on Git as its storage model").
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any, Optional, Sequence


def _iter_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(p for p in path.rglob("*") if p.is_file())
    return []


def _content_hash(paths: Sequence[Path]) -> str:
    """Deterministic sha256 over every file reachable from `paths`,
    hashing each file's path (relative to nothing in particular -- just
    its own string form, sorted) alongside its bytes, so the digest
    changes if a file is added/removed/renamed, not only if existing
    bytes change."""

    digest = hashlib.sha256()
    files: list[Path] = []
    for path in paths:
        files.extend(_iter_files(path))
    for file_path in sorted(files, key=str):
        digest.update(str(file_path).encode("utf-8"))
        digest.update(file_path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _probe_git(repo_root: Path) -> Optional[dict[str, Any]]:
    def run(*args: str) -> Optional[str]:
        try:
            result = subprocess.run(
                ["git", *args], cwd=str(repo_root), capture_output=True, text=True, timeout=5.0,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    commit = run("rev-parse", "HEAD")
    if commit is None:
        return None
    branch = run("rev-parse", "--abbrev-ref", "HEAD")
    status = run("status", "--porcelain")
    vcs: dict[str, Any] = {"system": "git", "commit": commit}
    if branch:
        vcs["branch"] = branch
    if status is not None:
        vcs["dirty"] = bool(status)
    return vcs


def capture_state_ref(paths: Sequence[Path], repo_root: Optional[Path] = None) -> dict[str, Any]:
    """Returns `{"content_hash": "sha256:...", "vcs": {...}?}` for the
    given `paths` (files and/or directories, walked recursively) --
    matches `agent-cycle-report.schema.json`'s `resulting_state_ref`
    shape exactly. `repo_root`, when given, is probed for a real git
    identity via `git rev-parse HEAD`; the `vcs` key is present only if
    that probe actually succeeds (a real commit found), omitted
    entirely otherwise -- never a placeholder, never a failure.
    """

    result: dict[str, Any] = {"content_hash": _content_hash(paths)}
    if repo_root is not None:
        vcs = _probe_git(repo_root)
        if vcs is not None:
            result["vcs"] = vcs
    return result
