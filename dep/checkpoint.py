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
