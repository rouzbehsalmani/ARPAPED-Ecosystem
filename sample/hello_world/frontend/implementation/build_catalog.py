"""Generates this frontend's capability-catalog.jsonl (Phase 8, Publish) --
the JS runtime's own equivalent of ../backend/build_catalog.py, same role
toward sample/hello_world/backend/runtime/bridge/assembler.py's discipline, just reading THIS runtime's
own JSON manifests (frontend/capabilities/**/manifest.json) instead of
YAML ones, since Node has no built-in YAML parser and this sample adds no
npm dependency for it. The frontend Bridge Core (bridge/core.js) never
reads YAML at runtime -- only this generated JSONL, exactly mirroring how
the backend's own Registry never walks capabilities/ directly at startup.

Also validates frontend/contracts/ (this runtime's OWN contracts, e.g.
greeting.render.contract.yaml) against component-contract.schema.json --
frontend's own build step, backend's verify.py never touches this file,
same "two agents, no shared touchpoint" boundary the contracts/ split
itself exists for. A manifest entry with no `contract` field (a Remote-
kind pointer to a capability owned entirely by another runtime, e.g.
console.write) has no contract to read here either -- its authoritative
shape lives with whichever runtime actually owns it, and the remote
Bridge re-validates it on arrival regardless (2-RULES.md R4/R8); this
runtime's own local pre-validation is a convenience, not the source of
truth, for anything it does not itself own.

Run whenever anything under implementation/capabilities/ or
implementation/contracts/ changes:
    python -m sample.hello_world.frontend.implementation.build_catalog

This script itself, and everything it reads, is implementation-time only;
its OUTPUT (../runtime/capability-catalog.jsonl) is the one thing the
runtime tree depends on -- nothing under runtime/ should ever need
anything under implementation/ to exist (see ../README.md).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml

_IMPLEMENTATION_ROOT = Path(__file__).resolve().parent
_FRONTEND_ROOT = _IMPLEMENTATION_ROOT.parent
_HELLO_WORLD_ROOT = _FRONTEND_ROOT.parent
_REPO_ROOT = _HELLO_WORLD_ROOT.parent.parent
_CATALOG_PATH = _FRONTEND_ROOT / "runtime" / "capability-catalog.jsonl"
_MANIFEST_SCHEMA = json.loads((_REPO_ROOT / "sample" / "schemas" / "capability-manifest.schema.json").read_text(encoding="utf-8"))
_CONTRACT_SCHEMA = json.loads((_REPO_ROOT / "sample" / "schemas" / "component-contract.schema.json").read_text(encoding="utf-8"))


def _flatten_dependencies(contract_deps: list[dict[str, Any]]) -> dict[str, str]:
    flattened = {}
    for dep in contract_deps or []:
        if isinstance(dep, dict):
            flattened[dep["capability_id"]] = dep.get("contract_version", "*")
        else:
            flattened[dep] = "*"
    return flattened


def main() -> int:
    rows: list[dict[str, Any]] = []
    for manifest_path in sorted(_IMPLEMENTATION_ROOT.glob("capabilities/**/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        jsonschema.validate(manifest, _MANIFEST_SCHEMA)

        if "contract" in manifest:
            contract_path = _REPO_ROOT / manifest["contract"]
            contract_data = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
            jsonschema.validate(contract_data, _CONTRACT_SCHEMA)
            contract = contract_data["contract"]
            version_block = contract["versions"][manifest["contract_version"]]
            input_schema = {
                op["name"]: op.get("input", [])
                for op in version_block["operations"]
            }
            dependencies = _flatten_dependencies(contract.get("dependencies", {}).get("capabilities", []))
            domain = contract["identity"]["domain"]
            family = contract["identity"]["family"]
            tags = contract.get("discoverability", {}).get("tags", [])
        else:
            # Remote-kind pointer to a capability this runtime doesn't own
            # (e.g. console.write) -- nothing here to read; the owning
            # runtime's own contract is authoritative, and its Bridge
            # re-validates on arrival regardless.
            input_schema = {}
            dependencies = {}
            domain = manifest["capability_id"].split(".")[0]
            family = domain
            tags = []

        for impl in manifest["implementations"]:
            rows.append({
                "capability_id": manifest["capability_id"],
                "contract_version": manifest["contract_version"],
                "implementation_id": impl["implementation_id"],
                "operations": impl["operations"],
                "executor": impl["executor"],
                "executor_kind": impl.get("executor_kind", "direct"),
                "priority": impl["priority"],
                "enabled": impl.get("enabled", True),
                "input_schema": input_schema,
                "dependencies": dependencies,
                "domain": domain,
                "family": family,
                "tags": tags,
            })

    _CATALOG_PATH.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} implementation record(s) to {_CATALOG_PATH.relative_to(_REPO_ROOT).as_posix()}")
    return len(rows)


if __name__ == "__main__":
    main()
