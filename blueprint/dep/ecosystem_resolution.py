"""Durable record of an ecosystem's own pillar composition (blueprint/dep/MANIFEST.yaml's
ecosystem_resolution) -- what blueprint/1-CYCLE.md Phase 0 Gate 25 requires be
written before a goal is accepted: which of the three pillars (README.md
"Three independently adoptable pillars") this ecosystem adopted, and what
each adopted one resolved to.

Not a capability: like episode_store/checkpoint, this is Evolution-phase
tooling for the cycle itself, not domain logic resolved through the Registry
or reached over the Bridge.

Unlike episode_store (one immutable entry per completed cycle, never
overwritten) and like checkpoint (mutable, current-attempt truth), this
record is current-COMPOSITION truth for the whole ecosystem, not a
historical log entry: it is written once when a genuinely NEW ecosystem
root is first established (1-CYCLE.md Phase 0 step 2/Gate 35 -- a cycle
continuing an EXISTING ecosystem never re-decides this, it just reads the
same file back via checkpoint.ecosystem_resolution_ref), and re-saved only
if the ecosystem's own pillar composition later genuinely changes (e.g. a
Runtime-only project later also adopting the Evolution pillar).

Generic, same posture as every other blueprint/dep/ tool: no default
`path` here -- always given explicitly by the caller, this application's
own path (e.g. state/ecosystem-resolution.json), never a path inside
blueprint/dep/ itself.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import jsonschema

_BLUEPRINT_ROOT = Path(__file__).resolve().parent.parent
_SCHEMAS_DIR = _BLUEPRINT_ROOT / "schemas"

_ECOSYSTEM_RESOLUTION_SCHEMA = json.loads(
    (_SCHEMAS_DIR / "ecosystem-resolution-record.schema.json").read_text(encoding="utf-8")
)


class EcosystemResolutionError(Exception):
    """Raised when a resolution record fails schema validation."""


def save_resolution_record(record: dict[str, Any], path: Path) -> Path:
    """Validates `record` against ecosystem-resolution-record.schema.json,
    then writes it to `path`, creating parent directories as needed.
    Overwrites freely -- this is current ecosystem composition truth, not
    an append-only log (contrast episode_store.save_episode, which refuses
    to overwrite an existing episode_id). Returns `path`.
    """

    try:
        jsonschema.validate(record, _ECOSYSTEM_RESOLUTION_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise EcosystemResolutionError(f"resolution record failed schema validation: {exc.message}") from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


def load_resolution_record(path: Path) -> Optional[dict[str, Any]]:
    """Returns the parsed, schema-validated record at `path`, or None if it
    doesn't exist yet -- a brand-new ecosystem root has no resolution
    record until Phase 0 first writes one, and that absence is a normal
    state, never an error, the same posture episode_store.load_episodes
    takes toward a missing episodes_dir.
    """

    if not path.exists():
        return None

    record = json.loads(path.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(record, _ECOSYSTEM_RESOLUTION_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise EcosystemResolutionError(f"resolution record at {path} failed schema validation: {exc.message}") from exc
    return record
