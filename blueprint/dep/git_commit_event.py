"""Records the fact that a commit was made, as its own DEP event
(blueprint/dep/MANIFEST.yaml: git_commit_event) -- distinct from and
sharing NO code or schema with runtime_log.py (a deliberate choice: a
commit is an agent/operator action, not a capability's Bridge call, so
it gets its own shape rather than being forced into runtime-event's).

This is the concrete mechanism behind the operator's own instruction:
DEP should reference git commits/branches/tags where relevant, but must
never DEPEND on git as its storage model. Every other blueprint/dep/
tool works with zero git involvement (state_ref.py's own `vcs` probe is
optional and silently omits itself if git isn't present); this module's
entire job, by contrast, IS to record that a real git action happened --
so unlike state_ref's silent-omit posture, a caller invoking this
specifically has nothing meaningful to record if the probe fails, and
that failure is raised loudly rather than swallowed.

Two entry points, for two different callers, the same split
finish_cycle.py already established:

  - `record_git_commit_event(log_path, repo_root, commit="HEAD")` -- the
    importable Python function.
  - `python -m blueprint.dep.git_commit_event --log-path PATH
    --repo-root PATH [--commit SHA]` -- the CLI, for an agent or tool
    that just ran `git commit` itself and cannot (or would rather not)
    import Python to record it -- any shell can invoke this as a
    subprocess after committing.

Generic, same posture as every other blueprint/dep/ tool: no default
`log_path`/`repo_root` here -- always given explicitly by the caller.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import jsonschema

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "git-commit-event.schema.json"
_GIT_COMMIT_EVENT_SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))

_lock = threading.Lock()


class GitCommitEventError(Exception):
    """Raised when there is nothing real to record: `repo_root` isn't a
    git working tree, `commit` doesn't resolve, or git isn't installed.
    Unlike state_ref.py's `_probe_git` (optional supplementary metadata,
    silently omitted on failure), a caller reaching this module has
    asked specifically to record a commit -- a failed probe here means
    the requested event genuinely cannot be produced, so it fails loudly
    rather than writing nothing and returning success."""


def _run_git(repo_root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=str(repo_root), capture_output=True, text=True, timeout=10.0,
        )
    except FileNotFoundError as exc:
        raise GitCommitEventError("git is not installed or not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitCommitEventError(f"git {' '.join(args)} timed out") from exc
    if result.returncode != 0:
        raise GitCommitEventError(
            f"git {' '.join(args)} failed in {repo_root}: {result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout.strip()


def _run_git_optional(repo_root: Path, *args: str) -> Optional[str]:
    try:
        return _run_git(repo_root, *args)
    except GitCommitEventError:
        return None


def record_git_commit_event(log_path: Path, repo_root: Path, commit: str = "HEAD") -> dict[str, Any]:
    """Probes `repo_root` for `commit`'s own real metadata (never
    guessed or reconstructed) and appends one event to `log_path`.
    `commit`'s full sha is REQUIRED and probed loudly
    (`GitCommitEventError` if it doesn't resolve); `branch`/`author`/
    `files_changed` are best-effort and simply omitted if their own
    probe fails, the same required-vs-optional split state_ref.py
    already draws between `content_hash` and `vcs`. Returns the exact
    event written.
    """

    sha = _run_git(repo_root, "rev-parse", commit)
    if not sha:
        raise GitCommitEventError(f"{commit!r} did not resolve to a commit in {repo_root}")

    subject = _run_git_optional(repo_root, "log", "-1", "--format=%s", sha) or ""
    body = _run_git_optional(repo_root, "log", "-1", "--format=%b", sha) or ""
    message = f"{subject}\n\n{body}".strip() if body else subject

    event: dict[str, Any] = {
        "event_id": uuid.uuid4().hex,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "commit": sha,
        "message": message,
    }

    # The repo's CURRENT branch at probe time -- not "which branch(es)
    # contain `commit`" (a commit can be on several, or the repo may
    # have since moved past it), which `--abbrev-ref <sha>` cannot
    # answer anyway (it just echoes the sha back). Meaningful precisely
    # when `commit` is the one just made (the default, "HEAD").
    branch = _run_git_optional(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch and branch != "HEAD":
        event["branch"] = branch

    author = _run_git_optional(repo_root, "log", "-1", "--format=%an <%ae>", sha)
    if author:
        event["author"] = author

    # --root: without it, diff-tree prints nothing for a repo's very
    # first commit (nothing to diff against) -- silently wrong for
    # exactly the commit most likely to be probed in a fresh test repo.
    files_raw = _run_git_optional(repo_root, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", sha)
    if files_raw is not None:
        event["files_changed"] = [line for line in files_raw.splitlines() if line]

    jsonschema.validate(event, _GIT_COMMIT_EVENT_SCHEMA)

    line = json.dumps(event)
    with _lock:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line)
            f.write("\n")

    return event


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m blueprint.dep.git_commit_event",
        description=(
            "Records the fact that a commit was made as its own DEP event. Probes the real "
            "commit (sha/branch/message/author/files_changed) -- never guessed. The subprocess "
            "entry point for any agent/tool that just ran `git commit` and cannot or would "
            "rather not import Python to record it."
        ),
    )
    parser.add_argument("--log-path", required=True, type=Path, dest="log_path")
    parser.add_argument("--repo-root", required=True, type=Path, dest="repo_root")
    parser.add_argument("--commit", required=False, default="HEAD", dest="commit")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    """Exit 0 with the recorded event (JSON) on stdout on success. Exit 1
    with why not on stderr on any anticipated failure (not a git repo,
    commit not found, git not installed). An exception this module never
    anticipated is deliberately left to propagate as a full traceback
    (2-RULES.md "Fail closed")."""
    args = _parse_args(argv)
    try:
        event = record_git_commit_event(args.log_path, args.repo_root, args.commit)
    except (GitCommitEventError, jsonschema.ValidationError) as exc:
        print(f"git_commit_event: NOT recorded -- {exc}", file=sys.stderr)
        return 1
    print(json.dumps(event))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
