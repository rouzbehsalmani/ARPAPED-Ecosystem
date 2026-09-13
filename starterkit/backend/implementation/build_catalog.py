"""Generates the RUNTIME capability-catalog.jsonl (Phase 8, Publish) from
THIS (implementation/) tree's own contracts/manifests -- this script itself
is implementation-time tooling, but its OUTPUT is a runtime artifact, so
it's written one level up, into ../runtime/, never here: nothing under
runtime/ should require anything under implementation/ to exist at
actual run time (that's the whole point of the split -- see ../README.md).

Run whenever anything under capabilities/ or contracts/ changes:
    python -m starterkit.backend.implementation.build_catalog

Uses rebuild_catalog (full rewalk, starterkit/backend/runtime/bridge/assembler.py) since this
starter kit's tree predates the catalog. A growing ecosystem should call
append_to_catalog per publish instead -- O(1), never re-walking what's
already there. See ../runtime/app/requests.py, which reads the catalog at startup.
"""

from pathlib import Path

from starterkit.backend.runtime.bridge.assembler import rebuild_catalog

_IMPLEMENTATION_ROOT = Path(__file__).resolve().parent
_BACKEND_ROOT = _IMPLEMENTATION_ROOT.parent
_REPO_ROOT = _BACKEND_ROOT.parent.parent
_CATALOG_PATH = _BACKEND_ROOT / "runtime" / "capability-catalog.jsonl"


def main():
    count = rebuild_catalog(
        capabilities_root=_IMPLEMENTATION_ROOT / "capabilities",
        repo_root=_REPO_ROOT,
        catalog_path=_CATALOG_PATH,
    )
    print(f"wrote {count} implementation record(s) to {_CATALOG_PATH.relative_to(_REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
