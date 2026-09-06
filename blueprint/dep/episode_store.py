"""Durable store for completed self-improving cycles (blueprint/dep/MANIFEST.yaml's
episode_store) -- the accumulating corpus that was previously missing:
1-CYCLE.md's Phase 7-8 already produce a decision_record
(blueprint/schemas/agent-cycle-report.schema.json) and a verification_record
(blueprint/schemas/verification-record.schema.json), but neither phase names a
durable place for them to accumulate ACROSS cycles. This module is that
place: one directory per completed cycle ("episode"), holding both
records together, machine-validated against the same schemas the rest of
this Blueprint already validates manifests and contracts against.

Not a capability: like a sample's own catalog-building tooling is
Publish-phase tooling for the Bridge, this is Evolution-phase tooling for
DEP -- nothing here is resolved through the Registry or reached over the
Bridge.

Generic, like a sample's own catalog-building tooling and assembler:
this module has no opinion on WHERE an episode corpus lives -- `episodes_dir`
is always given explicitly by the caller, never defaulted to a path
inside blueprint/dep/ itself. A sample's own episodes belong under that sample
(e.g. sample/hello_world/backend/state/episodes/, alongside its
verification-record.json), the same way its own capability-catalog.jsonl
belongs under it, not inside sample/hello_world/backend/runtime/bridge/.

An episode's identity is its verification_record's own `verification_id`
(already required, already unique per verification-record.schema.json) --
no new identifier scheme is invented. Episodes are historical fact, never
silently overwritten: saving over an existing episode_id is a hard error.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import jsonschema

_BLUEPRINT_ROOT = Path(__file__).resolve().parent.parent
_SCHEMAS_DIR = _BLUEPRINT_ROOT / "schemas"

_CYCLE_REPORT_SCHEMA = json.loads((_SCHEMAS_DIR / "agent-cycle-report.schema.json").read_text(encoding="utf-8"))
_VERIFICATION_RECORD_SCHEMA = json.loads((_SCHEMAS_DIR / "verification-record.schema.json").read_text(encoding="utf-8"))


class EpisodeStoreError(Exception):
    """Raised when a record fails schema validation, or an episode_id
    already exists (episodes are never silently overwritten)."""


def save_episode(
    cycle_report: dict[str, Any],
    verification_record: dict[str, Any],
    episodes_dir: Path,
) -> Path:
    """Validates `cycle_report` and `verification_record` against their
    schemas, then writes both into a new `episodes_dir/<verification_id>/`
    directory. Fails loudly -- never partially writes one file and not
    the other, never overwrites an episode_id that already exists.
    """

    try:
        jsonschema.validate(cycle_report, _CYCLE_REPORT_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise EpisodeStoreError(f"cycle_report failed schema validation: {exc.message}") from exc
    try:
        jsonschema.validate(verification_record, _VERIFICATION_RECORD_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise EpisodeStoreError(f"verification_record failed schema validation: {exc.message}") from exc

    episode_id = verification_record["verification_id"]
    episode_dir = episodes_dir / episode_id
    if episode_dir.exists():
        raise EpisodeStoreError(f"episode {episode_id!r} already exists at {episode_dir} -- episodes are never overwritten")

    episode_dir.mkdir(parents=True)
    (episode_dir / "agent-cycle-report.json").write_text(json.dumps(cycle_report, indent=2), encoding="utf-8")
    (episode_dir / "verification-record.json").write_text(json.dumps(verification_record, indent=2), encoding="utf-8")
    return episode_dir


def load_episodes(episodes_dir: Path) -> Iterator[dict[str, Any]]:
    """Yields `{"episode_id", "cycle_report", "verification_record"}` for
    every episode in `episodes_dir`, oldest directory name first. Missing
    `episodes_dir` yields nothing -- an empty corpus is not an error.
    """

    if not episodes_dir.is_dir():
        return
    for episode_dir in sorted(p for p in episodes_dir.iterdir() if p.is_dir()):
        report_path = episode_dir / "agent-cycle-report.json"
        record_path = episode_dir / "verification-record.json"
        if not report_path.exists() or not record_path.exists():
            continue
        yield {
            "episode_id": episode_dir.name,
            "cycle_report": json.loads(report_path.read_text(encoding="utf-8")),
            "verification_record": json.loads(record_path.read_text(encoding="utf-8")),
        }
