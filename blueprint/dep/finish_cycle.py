"""Publish-time gate for closing two confirmed, structural enforcement gaps
in this Blueprint, together, because they were never really separate
problems (blueprint/dep/MANIFEST.yaml: finish_cycle):

1. 1-CYCLE.md Phase 8 Gate 31 ("recorded into the episode store, then the
   checkpoint cleared") had ZERO automated enforcement: no schema field
   connects a verification_record to an episode, so a fully schema-valid
   status: "verified" record could exist with no episode at all.
   episode_store.save_episode was called from exactly ONE file in this
   repo's entire sample/ tree -- and even that one caller never called
   checkpoint.clear_checkpoint either. There is no non-Python port of
   either module, so a frontend's own JS verification harness (which Gate
   19 requires to exist for every shipped frontend) had no first-party way
   to comply even if it remembered to.
2. 2-RULES.md R4's acyclic-dependency-graph claim ("an ecosystem's assembler
   verifies this before anything is registered") had ZERO implementation
   anywhere -- not in blueprint/dep/, not in any sample's own assembler.

Both are decided here, together, as one publish-time act, the same way
episode_store/checkpoint already refuse half-measures elsewhere (an episode
is never partially written; a checkpoint clear is idempotent, never
silently skipped). `finish_cycle` refuses to record anything at all unless
BOTH hold:

  - the verification record's own `status` is "verified" -- an unverified
    state is never published (2-RULES.md "Fail closed"); this is an
    EXISTING invariant, not a new one, just finally enforced at the one
    place a cycle is actually turned into a published episode;
  - the dependency graph declared across catalog_path's own `dependencies`
    edges (the same capability-catalog.jsonl shape
    checkpoint.reconcile_with_catalog already reads: one line per
    implementation, `capability_id` + `dependencies: {capability_id:
    version_constraint}`) is acyclic -- naming the exact cycle found (e.g.
    "a -> b -> a"), never just "a cycle exists somewhere", since Gate 30
    asks an agent to go fix a specific cycle, not learn one exists.

Only past both refusals does it call episode_store.save_episode, then
checkpoint.clear_checkpoint if a checkpoint_path was given -- unchanged,
still the same two underlying operations, just no longer two
separately-callable, separately-forgettable steps.

Must be called from Phase 8 (1-CYCLE.md), AFTER this cycle's own
capabilities are registered and capability-catalog.jsonl is rebuilt to
include them -- never from the Phase 7 harness itself
(0-WALKTHROUGH.md section 6). The acyclic check can only see what's
actually in the catalog at the moment it's called; calling this before
registration would silently check a graph missing this cycle's own new
edges, which is weaker than Gate 30 actually requires.

Generic, same posture as every other blueprint/dep/ tool: no default
`catalog_path`/`episodes_dir`/`checkpoint_path` here -- always given
explicitly by the caller, this application's own paths, never a path
inside blueprint/dep/ itself.

Two entry points, for two different callers:

  - `finish_cycle(cycle_report, verification_record, catalog_path,
    episodes_dir, checkpoint_path=None)` -- the importable Python function,
    for a harness that already holds both records as in-memory dicts (the
    normal shape immediately after Phase 7 builds them) -- a drop-in
    replacement for what used to be two separate calls.
  - `finish_cycle_from_paths(...)` + `python -m blueprint.dep.finish_cycle
    --cycle-report PATH --verification-record PATH --catalog PATH
    --episodes-dir PATH [--checkpoint PATH]` -- for a harness that cannot
    import Python at all (a JS frontend's own verify.js, or any future
    language). A subprocess call works from any language; this CLI is what
    actually makes Gate 31 satisfiable outside Python.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

import jsonschema

from blueprint.dep import checkpoint, episode_store

_BLUEPRINT_ROOT = Path(__file__).resolve().parent.parent
_SCHEMAS_DIR = _BLUEPRINT_ROOT / "schemas"

_CYCLE_REPORT_SCHEMA = json.loads((_SCHEMAS_DIR / "agent-cycle-report.schema.json").read_text(encoding="utf-8"))
_VERIFICATION_RECORD_SCHEMA = json.loads((_SCHEMAS_DIR / "verification-record.schema.json").read_text(encoding="utf-8"))


class FinishCycleError(Exception):
    """Raised when a cycle refuses to be published: the verification record
    isn't status "verified", the catalog named by catalog_path doesn't
    exist or isn't parseable, or the dependency graph it declares contains
    a cycle (R4/R5, Gate 30). Distinct from episode_store.EpisodeStoreError
    and checkpoint.CheckpointError, which this module still lets propagate
    unwrapped for their own failure modes -- this class exists only for the
    two invariants finish_cycle itself introduces."""


def _build_dependency_graph(catalog_path: Path) -> dict[str, list[str]]:
    """Reads catalog_path (this cycle's own freshly-registered
    capability-catalog.jsonl) into an adjacency list: capability_id ->
    the capability_ids it may call, live, per its contract's
    `dependencies` (R4). More than one line can share a capability_id --
    one per registered implementation -- since dependencies live on the
    shared contract, not per-implementation, every line's declared edges
    for a given capability_id are UNIONED, never "last line wins" the way
    checkpoint.reconcile_with_catalog's own by-id lookup does for its
    different purpose; dropping a real edge here would produce a false
    "acyclic", the wrong direction to ever be wrong in.

    Unlike checkpoint.reconcile_with_catalog (which treats a missing
    catalog_path as nothing to reconcile against yet, a normal state
    mid-cycle before Phase 8 first builds one), a missing or empty catalog
    here IS an error: by the time finish_cycle is called, this cycle's own
    Phase 8 registration has already run and rebuilt it. A missing catalog
    at this point is a caller mistake (wrong path, or called before
    registration), never a normal state to tolerate silently.
    """
    if not catalog_path.exists():
        raise FinishCycleError(
            f"capability catalog not found at {catalog_path} -- finish_cycle must be called "
            "AFTER this cycle's own Phase 8 registration has rebuilt it (1-CYCLE.md Phase 8); "
            "a missing catalog here means either the wrong path was given, or this was called "
            "before registration, never that there is genuinely nothing to check yet"
        )

    graph: dict[str, list[str]] = {}
    for lineno, raw_line in enumerate(catalog_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FinishCycleError(f"{catalog_path}:{lineno}: not valid JSON -- {exc}") from exc
        capability_id = entry.get("capability_id")
        if not capability_id:
            raise FinishCycleError(f"{catalog_path}:{lineno}: entry has no capability_id")
        edges = graph.setdefault(capability_id, [])
        for dep_id in (entry.get("dependencies") or {}):
            if dep_id not in edges:
                edges.append(dep_id)

    return graph


_WHITE, _GRAY, _BLACK = 0, 1, 2


def _find_cycle(graph: dict[str, list[str]]) -> Optional[list[str]]:
    """Standard DFS cycle probe over `graph` (capability_id -> declared
    dependency capability_ids), colored WHITE (unvisited) / GRAY (on the
    current DFS path) / BLACK (fully explored, proven acyclic from here).
    Returns the exact cycle found as a list e.g. ["a", "b", "a"] (so the
    caller can render "a -> b -> a"), or None if the graph is acyclic.
    Deterministic given a deterministic `graph` (dict insertion order,
    which _build_dependency_graph derives from the catalog's own line
    order) -- the same catalog always reports the same cycle the same way.

    A dependency naming a capability_id absent from the catalog entirely
    (declared but never registered) is a different problem than a cycle --
    not this function's job to flag; it only walks edges into nodes the
    catalog actually contains.
    """
    color: dict[str, int] = {node: _WHITE for node in graph}
    path: list[str] = []

    def visit(node: str) -> Optional[list[str]]:
        color[node] = _GRAY
        path.append(node)
        for neighbor in graph.get(node, []):
            if neighbor not in color:
                continue
            if color[neighbor] == _GRAY:
                cycle_start = path.index(neighbor)
                return path[cycle_start:] + [neighbor]
            if color[neighbor] == _WHITE:
                found = visit(neighbor)
                if found is not None:
                    return found
        path.pop()
        color[node] = _BLACK
        return None

    for node in graph:
        if color[node] == _WHITE:
            found = visit(node)
            if found is not None:
                return found
    return None


def finish_cycle(
    cycle_report: dict[str, Any],
    verification_record: dict[str, Any],
    catalog_path: Path,
    episodes_dir: Path,
    checkpoint_path: Optional[Path] = None,
) -> Path:
    """The ONE call 1-CYCLE.md Phase 8 Gate 31 now names for turning a
    verified cycle into a published one. Order is fixed, not
    caller-choosable:

    1. schema-validate both records against the same schemas
       episode_store validates against -- done here too, BEFORE trusting
       verification_record["status"], since a schema-invalid record might
       not even have that key;
    2. refuse if verification_record["status"] != "verified";
    3. build the dependency graph from catalog_path and refuse if it
       contains a cycle, naming the exact cycle (Gate 30);
    4. only past both refusals, episode_store.save_episode(cycle_report,
       verification_record, episodes_dir);
    5. if checkpoint_path is given, checkpoint.clear_checkpoint(checkpoint_path)
       -- already idempotent, so no existence pre-check belongs here.

    Returns the episode directory save_episode created -- same value a
    caller doing the two calls itself used to get back from save_episode.
    """

    try:
        jsonschema.validate(cycle_report, _CYCLE_REPORT_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise FinishCycleError(f"cycle_report failed schema validation: {exc.message}") from exc
    try:
        jsonschema.validate(verification_record, _VERIFICATION_RECORD_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise FinishCycleError(f"verification_record failed schema validation: {exc.message}") from exc

    status = verification_record.get("status")
    if status != "verified":
        raise FinishCycleError(
            f"verification record {verification_record.get('verification_id')!r} has status "
            f"{status!r}, not \"verified\" -- an unverified state is never published "
            "(2-RULES.md \"Fail closed\"); fix the defect, re-run the harness until the record "
            "is green, then call finish_cycle again"
        )

    graph = _build_dependency_graph(catalog_path)
    cycle = _find_cycle(graph)
    if cycle is not None:
        raise FinishCycleError(
            f"declared dependency graph in {catalog_path} contains a cycle: "
            + " -> ".join(cycle)
            + " -- R4/R5/Gate 30 requires generics -> specifics, never a loop; fix the "
            "offending contract's dependencies.capabilities, rebuild the catalog, and only "
            "then call finish_cycle again"
        )

    episode_dir = episode_store.save_episode(cycle_report, verification_record, episodes_dir)

    if checkpoint_path is not None:
        checkpoint.clear_checkpoint(checkpoint_path)

    return episode_dir


def finish_cycle_from_paths(
    cycle_report_path: Path,
    verification_record_path: Path,
    catalog_path: Path,
    episodes_dir: Path,
    checkpoint_path: Optional[Path] = None,
) -> Path:
    """Same contract as finish_cycle, for a caller with these two records
    as files on disk rather than already-loaded dicts -- the normal shape
    for a non-Python harness invoking this module's CLI as a subprocess. A
    Python harness that already holds both as dicts should call
    finish_cycle directly instead."""
    cycle_report = json.loads(cycle_report_path.read_text(encoding="utf-8"))
    verification_record = json.loads(verification_record_path.read_text(encoding="utf-8"))
    return finish_cycle(cycle_report, verification_record, catalog_path, episodes_dir, checkpoint_path)


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m blueprint.dep.finish_cycle",
        description=(
            "Publish-time gate for 1-CYCLE.md Phase 8 Gate 31/Gate 30: refuses to record a "
            "cycle unless its verification record is actually \"verified\" and its declared "
            "capability dependency graph is acyclic, then records the episode and clears the "
            "checkpoint in one call. The subprocess entry point for any harness that cannot "
            "import Python directly."
        ),
    )
    parser.add_argument("--cycle-report", required=True, type=Path, dest="cycle_report_path")
    parser.add_argument("--verification-record", required=True, type=Path, dest="verification_record_path")
    parser.add_argument("--catalog", required=True, type=Path, dest="catalog_path")
    parser.add_argument("--episodes-dir", required=True, type=Path, dest="episodes_dir")
    parser.add_argument("--checkpoint", required=False, default=None, type=Path, dest="checkpoint_path")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    """Exit 0 with the new episode directory on stdout on success -- the
    one line a caller in any language needs to capture. Exit 1 with a
    stderr message naming exactly why the cycle wasn't published on any
    anticipated failure. An exception this module never anticipated is
    deliberately left to propagate as a full traceback -- catching
    Exception broadly here would silently swallow a real bug behind a
    clean-looking one-line message, exactly the failure mode this
    Blueprint exists to prevent (2-RULES.md "Fail closed")."""
    args = _parse_args(argv)
    try:
        episode_dir = finish_cycle_from_paths(
            args.cycle_report_path,
            args.verification_record_path,
            args.catalog_path,
            args.episodes_dir,
            args.checkpoint_path,
        )
    except (
        FinishCycleError,
        episode_store.EpisodeStoreError,
        checkpoint.CheckpointError,
        FileNotFoundError,
        json.JSONDecodeError,
    ) as exc:
        print(f"finish_cycle: cycle NOT published -- {exc}", file=sys.stderr)
        return 1
    print(episode_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
