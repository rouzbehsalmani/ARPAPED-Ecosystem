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
Bridge-only project later also adopting the DEP pillar).

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


# Structurally shaped like the Bridge pillar's own contract/manifest model
# (packs/bridge.yaml) -- never legitimate anywhere in an ecosystem that
# hasn't adopted the Bridge pillar, since without a Bridge there is no
# Registry to publish a capability to and nothing to select an
# implementation through. Content-based where a filename alone would be
# too weak a signal (a manifest.yaml could coincidentally be something
# else entirely); filename-based where the convention is exclusive enough
# on its own (nothing but this Blueprint's own contracts end in
# ".contract.yaml", or is ever named exactly "capability-catalog.jsonl").
_BRIDGE_LEAKAGE_DIR_NAMES = ("contracts", "capabilities")
_BRIDGE_LEAKAGE_FILE_NAMES = ("capability-catalog.jsonl",)
_MANIFEST_FILE_NAMES = ("manifest.yaml", "manifest.json")
_MANIFEST_MARKERS = ("capability_id", "implementations")


def detect_bridge_leakage(ecosystem_root: Path) -> list[str]:
    """Scans `ecosystem_root` for files/directories structurally shaped
    like the Bridge pillar's own model, and returns every match found as
    paths relative to `ecosystem_root` (sorted, `[]` means clean). Real,
    observed failure this exists to catch: a Builder agent, given a
    DEP+Cycles-only resolution with no Bridge pillar adopted at all, built
    a full `contracts/`/`capabilities/` tree of *.contract.yaml and
    manifest.yaml files anyway -- despite packs/README.md's own "No
    Bridge means no capability vocabulary" section saying not to, in
    plain prose, already. Prose alone did not stop it; this function is
    the mechanical check `finish_cycle` (this module's own sibling) now
    runs instead of just trusting an agent remembered the rule.

    Matches:
      - any directory named exactly "contracts" or "capabilities";
      - any file whose name ends ".contract.yaml" (this Blueprint's own
        contract-file convention, never used for anything else);
      - any file named exactly "capability-catalog.jsonl" (a Bridge
        RUNTIME artifact -- its mere presence on disk means a Bridge
        engine ran, which shouldn't be possible with no Bridge adopted);
      - any file named exactly "manifest.yaml"/"manifest.json" whose own
        text contains BOTH "capability_id" and "implementations" (the
        capability-manifest shape, packs/bridge.yaml's own
        `choose_at_least_one` entries) -- content-checked, not just
        filename-matched, since "manifest.yaml"/"manifest.json" alone are
        common enough names to have a real, unrelated use elsewhere.

    `state/` (this repo's own convention for generated, gitignored
    runtime/cycle output -- see .gitignore's own `**/state/` entry) is
    never scanned: a leftover capability-catalog.jsonl under state/ from
    a PRIOR, since-reverted Bridge adoption is a stale-cleanup problem,
    not evidence of a currently-leaking ecosystem. Never raises on a file
    it can't read as text (binary, wrong encoding) -- skipped silently,
    since this is a heuristic safety net over real application source,
    not a schema validator with a fixed, always-parseable input shape.
    """

    if not ecosystem_root.exists():
        return []

    violations: set[str] = set()
    for path in ecosystem_root.rglob("*"):
        rel = path.relative_to(ecosystem_root)
        if "state" in rel.parts:
            continue

        if path.is_dir():
            if path.name in _BRIDGE_LEAKAGE_DIR_NAMES:
                violations.add(f"{rel}/")
            continue

        if path.name.endswith(".contract.yaml") or path.name in _BRIDGE_LEAKAGE_FILE_NAMES:
            violations.add(str(rel))
            continue

        if path.name in _MANIFEST_FILE_NAMES:
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if all(marker in text for marker in _MANIFEST_MARKERS):
                violations.add(str(rel))

    return sorted(violations)
