"""Turns an episode_store corpus into training rows (blueprint/dep/MANIFEST.yaml's
dataset_builder) -- the piece that makes "historical episodes" usable as
data, not just an audit trail.

One row per decision, not per episode: a single cycle can decompose a
goal into several responsibilities (1-CYCLE.md Phase 2), each independently
decided (Phase 4) -- `decision` (reuse/compose/split_refactor/create/
structural_floor) and `reason` are what a future predictor is actually
meant to predict, given a goal/state/responsibility. `verification_status`
and `resulting_state` are the outcome that decision led to -- carried on
every row from that episode, not treated as a separate example, since a
decision is never independently correct or wrong: it's only ever
evaluated by whether the episode it was part of verified.

Also pulls a decision's own structured `failure`/`correction`
(agent-cycle-report.schema.json) when present, and, via `check_ids`, the
`selection`/`evidence`/`trace` objects the matching verification-record.json
checks actually observed (verification-record.schema.json) -- the exact
gap this module used to have even for the ONE failure-adjacent field that
already existed (`verification.failures_and_fixes`, still pulled below,
was never read here before this was added): a schema can carry rich
per-decision signal and it still never reaches a training row unless
something here actually reads it. The join is always by the explicit
`check_ids` a decision names, never guessed by matching `responsibility`
against a check's `description` string -- an unstated link is not
implicitly "the check with a similar name" (2-RULES.md "No silent
defaults on what resolution depends on" applies here too).

Not a capability, same posture as episode_store and a sample's own
catalog-building tooling (blueprint/dep/MANIFEST.yaml): Evolution-phase
tooling, not something resolved through the Registry or reached over the
Bridge.

Generic, same posture as episode_store: no default `episodes_dir`/
`output_path` baked in here -- a sample calls this against its own
episode corpus and writes its own dataset alongside it (see
sample/hello_world/backend/README.md for a worked example), the same way
it calls its own assembler's rebuild_catalog against its own capabilities/.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from blueprint.dep.episode_store import load_episodes


def build_rows(episodes_dir: Path) -> Iterator[dict[str, Any]]:
    for episode in load_episodes(episodes_dir):
        report = episode["cycle_report"]
        checks_by_id = {
            check["check_id"]: check
            for check in episode["verification_record"].get("checks", [])
        }
        for decision in report["decisions"]:
            row: dict[str, Any] = {
                "episode_id": episode["episode_id"],
                "goal": report["goal"],
                "starting_state": report["starting_state"],
                "responsibility": decision["responsibility"],
                "decision": decision["decision"],
                "reason": decision["reason"],
                "verification_status": report["verification"]["status"],
                "resulting_state": report["resulting_state"],
                "failures_and_fixes": report["verification"].get("failures_and_fixes"),
            }
            if "failure" in decision:
                row["failure"] = decision["failure"]
            if "correction" in decision:
                row["correction"] = decision["correction"]

            matched = [
                checks_by_id[check_id]
                for check_id in decision.get("check_ids", [])
                if check_id in checks_by_id
            ]
            selections = [check["selection"] for check in matched if "selection" in check]
            evidences = [check["evidence"] for check in matched if "evidence" in check]
            traces = [check["trace"] for check in matched if "trace" in check]
            if selections:
                row["bridge_selection"] = selections
            if evidences:
                row["bridge_evidence"] = evidences
            if traces:
                row["bridge_trace"] = traces

            yield row


def build_dataset(episodes_dir: Path, output_path: Path) -> int:
    """Writes one JSON object per line to `output_path`. Returns the row
    count. Rebuilds from scratch every time -- the episode corpus is the
    source of truth; this file is a derived, regenerable view of it, the
    same relationship capability-catalog.jsonl has to the manifests it
    was built from.
    """

    count = 0
    with output_path.open("w", encoding="utf-8") as f:
        for row in build_rows(episodes_dir):
            f.write(json.dumps(row))
            f.write("\n")
            count += 1
    return count
