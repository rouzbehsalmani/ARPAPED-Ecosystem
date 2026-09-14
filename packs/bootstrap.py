"""The executable form of packs/README.md's own "two-agent split" section
-- what Agent 1 (1-CYCLE.md Phase 0) actually runs to offer the pillar
combinations, and what Agent 2 runs to read the handoff.

Three commands:

  python -m packs.bootstrap list-pillars
      Prints every adoptable pillar and every non-empty combination of
      them, generated from packs/*.yaml's own `pillar:`/`description:`
      fields -- never hardcoded prose that could drift from those files
      the moment a pack changes. This is the literal menu Phase 0 step 2
      (1-CYCLE.md, Gate 35) requires offering explicitly for a genuinely
      new ecosystem root, never defaulted to silently.

  python -m packs.bootstrap resolve --ecosystem-root PATH --pillars-file FILE
      [--combine-with-file FILE] [--out PATH] [--resolved-by NAME]
      Writes a new ecosystem-resolution record
      (ecosystem-resolution-record.schema.json,
      blueprint.dep.ecosystem_resolution) from a `pillars-file` -- a JSON
      file matching the schema's own `pillars` object shape directly,
      the same posture blueprint.dep.finish_cycle's own CLI already takes
      toward --cycle-report/--verification-record (a real record as a
      file, never flattened into ad hoc flags -- `pillars.runtime` in
      particular is a variable-length array of multi-field objects, which
      no flag design handles cleanly). Exits 0 with the written path on
      stdout, or 1 with why not on stderr (schema-invalid input).

  python -m packs.bootstrap describe PATH
      Pretty-prints an existing resolution record -- which pillars, what
      each resolved to, which combine_with hooks were applied. What
      Agent 2 runs first, instead of hand-reading raw JSON, to confirm
      what Agent 1 actually settled before building anything.

Nothing here duplicates a pack's own content -- `list-pillars` reads
packs/*.yaml directly every time, so it can never go stale independently
of them.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from blueprint.dep import ecosystem_resolution

_PACKS_DIR = Path(__file__).resolve().parent


def _load_pack_descriptions() -> dict[str, dict[str, str]]:
    """pillar name (lowercase) -> {"pack": ..., "description": ...},
    read fresh from every packs/*.yaml sibling of this file each call --
    never cached, never copied into this module's own source."""

    result: dict[str, dict[str, str]] = {}
    for path in sorted(_PACKS_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        result[data["pillar"].lower()] = {
            "pack": data["pack"],
            "description": data["description"].strip(),
        }
    return result


def list_pillars() -> None:
    pillars = _load_pack_descriptions()
    names = sorted(pillars)

    print("Available pillars (packs/README.md):")
    for name in names:
        first_line = pillars[name]["description"].splitlines()[0]
        print(f"  - {name.capitalize()} ({pillars[name]['pack']}.yaml): {first_line}")
    print()

    print("Combinations you can adopt (choose one):")
    n = 1
    for r in range(1, len(names) + 1):
        for combo in itertools.combinations(names, r):
            label = " + ".join(c.capitalize() for c in combo)
            if r == len(names):
                label += "  (the full, integrated configuration -- see starterkit/)"
            print(f"  {n}. {label}")
            n += 1


def resolve(
    ecosystem_root: Path,
    pillars_file: Path,
    combine_with_file: Optional[Path] = None,
    out: Optional[Path] = None,
    resolved_by: Optional[str] = None,
) -> Path:
    """Builds and saves a new ecosystem-resolution record. `pillars_file`
    is a JSON file holding exactly the schema's own `pillars` object
    (e.g. `{"process": {...}, "evolution": {...}}`) -- whichever pillars
    were chosen after `list_pillars()` presented the options. Raises
    ecosystem_resolution.EcosystemResolutionError if the resulting record
    fails schema validation (an empty `pillars`, a malformed runtime
    entry, an unknown pillar key). Returns the path written to.
    """

    pillars = json.loads(pillars_file.read_text(encoding="utf-8"))
    record: dict[str, Any] = {
        "resolution_id": f"res-{uuid.uuid4().hex[:12]}",
        "ecosystem_root": str(ecosystem_root),
        "pillars": pillars,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
    }
    if combine_with_file is not None:
        record["combine_with_applied"] = json.loads(combine_with_file.read_text(encoding="utf-8"))
    if resolved_by is not None:
        record["resolved_by"] = resolved_by

    out_path = out if out is not None else ecosystem_root / "state" / "ecosystem-resolution.json"
    return ecosystem_resolution.save_resolution_record(record, out_path)


def describe(path: Path) -> None:
    record = ecosystem_resolution.load_resolution_record(path)
    if record is None:
        print(f"No resolution record at {path}", file=sys.stderr)
        raise SystemExit(1)

    print(f"resolution_id:  {record['resolution_id']}")
    print(f"ecosystem_root: {record['ecosystem_root']}")
    print(f"resolved_at:    {record['resolved_at']}")
    if "resolved_by" in record:
        print(f"resolved_by:    {record['resolved_by']}")
    print(f"pillars adopted: {', '.join(sorted(record['pillars']))}")
    for name, detail in record["pillars"].items():
        print(f"  {name}:")
        for key, value in detail.items():
            print(f"    {key}: {value}")

    hooks = record.get("combine_with_applied") or []
    if hooks:
        print("combine_with_applied:")
        for hook in hooks:
            mark = "x" if hook["applied"] else " "
            print(f"  [{mark}] {hook['hook']} ({hook['from_pillar']} -> {hook['to_pillar']}): {hook.get('detail', '')}")


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m packs.bootstrap",
        description="Offer/resolve/describe a project's own pillar combination (1-CYCLE.md Phase 0 Gate 25/35).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-pillars", help="Print the available pillars and every combination of them.")

    p_resolve = sub.add_parser("resolve", help="Write a new ecosystem-resolution record.")
    p_resolve.add_argument("--ecosystem-root", required=True, type=Path)
    p_resolve.add_argument(
        "--pillars-file", required=True, type=Path,
        help="JSON file matching the schema's own 'pillars' object shape directly.",
    )
    p_resolve.add_argument("--combine-with-file", type=Path, default=None)
    p_resolve.add_argument("--out", type=Path, default=None, help="Default: <ecosystem-root>/state/ecosystem-resolution.json")
    p_resolve.add_argument("--resolved-by", default=None)

    p_describe = sub.add_parser("describe", help="Pretty-print an existing ecosystem-resolution record.")
    p_describe.add_argument("path", type=Path)

    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)

    if args.command == "list-pillars":
        list_pillars()
        return 0

    if args.command == "resolve":
        try:
            out_path = resolve(
                args.ecosystem_root, args.pillars_file, args.combine_with_file, args.out, args.resolved_by,
            )
        except ecosystem_resolution.EcosystemResolutionError as exc:
            print(f"bootstrap resolve: refused -- {exc}", file=sys.stderr)
            return 1
        print(out_path)
        return 0

    if args.command == "describe":
        describe(args.path)
        return 0

    return 1  # unreachable -- argparse enforces one of the subcommands above


if __name__ == "__main__":
    raise SystemExit(main())
