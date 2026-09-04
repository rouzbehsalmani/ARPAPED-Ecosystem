"""Mid-cycle progress record (dep/MANIFEST.yaml's checkpoint), so an agent
interrupted anywhere in 1-CYCLE.md Phase 0-8 -- tokens, network, crash, any
reason unrelated to the work itself -- can be resumed by a DIFFERENT agent
without reverse-engineering filesystem state (which responsibilities were
decided, which have a contract but no manifest yet, which are fully
integrated, what was already tried and ruled out).

Not the same problem episode_store.py solves: an episode is the durable,
immutable record of a COMPLETED cycle, accumulated across cycles. A
checkpoint is the mutable, in-progress record of the CURRENT cycle attempt,
overwritten repeatedly as work proceeds, and cleared once that attempt
reaches Phase 8 and becomes an episode (1-CYCLE.md Gate 31/32).

Generic, same posture as episode_store.py/process_supervisor.py: no
opinion on WHERE a checkpoint lives -- `checkpoint_path` is always given
explicitly by the caller (e.g. state/cycle-checkpoint.json, the same
state/ convention verification-record.json already uses), never defaulted
to a path inside dep/ itself.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import jsonschema

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCHEMAS_DIR = _REPO_ROOT / "schemas"

_CHECKPOINT_SCHEMA = json.loads((_SCHEMAS_DIR / "cycle-checkpoint.schema.json").read_text(encoding="utf-8"))


class CheckpointError(Exception):
    """Raised when a checkpoint fails schema validation."""


def save_checkpoint(checkpoint: dict[str, Any], checkpoint_path: Path) -> Path:
    """Validates `checkpoint` against cycle-checkpoint.schema.json and
    writes it to `checkpoint_path`, overwriting whatever was there --
    unlike an episode, a checkpoint is mutable and is expected to be
    saved again and again as a cycle attempt progresses.
    """

    try:
        jsonschema.validate(checkpoint, _CHECKPOINT_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise CheckpointError(f"checkpoint failed schema validation: {exc.message}") from exc

    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")
    return checkpoint_path


def load_checkpoint(checkpoint_path: Path) -> Optional[dict[str, Any]]:
    """Returns the checkpoint at `checkpoint_path`, or None if it doesn't
    exist -- nothing to resume, the cycle starts fresh. A present-but-
    invalid file raises rather than being silently ignored: an agent
    should never treat corrupt resume state as "no checkpoint".
    """

    if not checkpoint_path.exists():
        return None
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(checkpoint, _CHECKPOINT_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise CheckpointError(f"checkpoint at {checkpoint_path} failed schema validation: {exc.message}") from exc
    return checkpoint


def clear_checkpoint(checkpoint_path: Path) -> bool:
    """Deletes `checkpoint_path`. Idempotent: a missing file is a clean
    no-op (returns False), never an error. Returns True only if a file
    was actually removed.
    """

    if not checkpoint_path.exists():
        return False
    checkpoint_path.unlink()
    return True


_STATUS_ORDER = [
    "planned",
    "decided",
    "contract_written",
    "manifest_written",
    "code_written",
    "integrated",
]


def reconcile_with_catalog(checkpoint: dict[str, Any], catalog_path: Path) -> dict[str, Any]:
    """Repairs a checkpoint that fell behind reality -- observed for real:
    an agent kept working through Phase 4/5/6 (contracts, manifests,
    executors all written) without ever calling `save_checkpoint` again
    after Phase 0, so a resuming agent found `status: planned` for every
    responsibility while 8 capabilities already existed on disk. The
    wrong fix is reading the project to rebuild the checkpoint by hand --
    that is the exact O(project) cost this whole mechanism exists to
    avoid. The right fix: `catalog_path` (a sample/application's own
    `capability-catalog.jsonl`, built by its `build_catalog.py`) is
    already a bounded, one-line-per-capability index -- the same one
    Phase 3 discovery already uses instead of scanning the Registry.
    Reconciling against it costs O(this cycle's own capability count),
    never O(total project size), regardless of catalog size.

    For every responsibility whose name matches a `capability_id` in the
    catalog, fills in `artifacts` (contract/manifest/executor paths) from
    that entry and advances `status` to at least `code_written` -- a
    catalog entry with all three paths resolved is real evidence code
    exists, but never proves Bridge integration (Phase 6) by itself, so
    `integrated` is never set here; a resuming agent still confirms that
    with its own cheap per-responsibility check. Never regresses a status
    already further along (e.g. leaves an already-`integrated` entry
    alone). Responsibilities with no matching catalog entry are left
    untouched -- reconciliation only repairs what the catalog can prove,
    it never invents progress.

    Mutates and returns `checkpoint`; the caller MUST `save_checkpoint`
    the result to actually persist the repair -- reconciling without
    re-saving pays this same cost again on the next interruption.
    """

    if not catalog_path.exists():
        return checkpoint

    by_id: dict[str, dict[str, Any]] = {}
    for line in catalog_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        entry = json.loads(line)
        by_id[entry["capability_id"]] = entry

    for responsibility in checkpoint.get("responsibilities", []):
        entry = by_id.get(responsibility["responsibility"])
        if entry is None:
            continue
        artifacts = responsibility.setdefault("artifacts", {})
        if entry.get("contract_path"):
            artifacts["contract"] = entry["contract_path"]
        if entry.get("manifest_path"):
            artifacts["manifest"] = entry["manifest_path"]
        if entry.get("executor_path"):
            artifacts["executor"] = entry["executor_path"]

        current = responsibility.get("status", "planned")
        current_idx = _STATUS_ORDER.index(current) if current in _STATUS_ORDER else 0
        target_idx = _STATUS_ORDER.index("code_written")
        if target_idx > current_idx:
            responsibility["status"] = "code_written"

    return checkpoint
