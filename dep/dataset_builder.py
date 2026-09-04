"""Turns an episode_store corpus into training rows (dep/MANIFEST.yaml's
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

Not a capability, same posture as episode_store.py and build_catalog.py:
Evolution-phase tooling, not something resolved through the Registry or
reached over the Bridge.

Generic, same posture as episode_store.py: no default `episodes_dir`/
`output_path` baked in here -- a sample calls this against its own
episode corpus and writes its own dataset alongside it (see
samples/hello_world/build_dataset.py), the same way it calls
bridge/assembler.py's rebuild_catalog against its own capabilities/.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from dep.episode_store import load_episodes


def build_rows(episodes_dir: Path) -> Iterator[dict[str, Any]]:
    for episode in load_episodes(episodes_dir):
        report = episode["cycle_report"]
        for decision in report["decisions"]:
            yield {
                "episode_id": episode["episode_id"],
                "goal": report["goal"],
                "starting_state": report["starting_state"],
                "responsibility": decision["responsibility"],
                "decision": decision["decision"],
                "reason": decision["reason"],
                "verification_status": report["verification"]["status"],
                "resulting_state": report["resulting_state"],
            }


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
