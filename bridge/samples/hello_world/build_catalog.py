"""Generates this sample's capability-catalog.jsonl (Phase 8, Publish).

Run whenever anything under capabilities/ or its contracts changes:
    python -m bridge.samples.hello_world.build_catalog

Uses rebuild_catalog (full rewalk, bridge/assembler.py) since this
sample's tree predates the catalog. A growing ecosystem should call
append_to_catalog per publish instead -- O(1), never re-walking what's
already there. See app/requests.py, which reads the catalog at startup.
"""

from pathlib import Path

from bridge.assembler import rebuild_catalog

_APP_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _APP_ROOT.parent.parent.parent


def main():
    count = rebuild_catalog(
        capabilities_root=_APP_ROOT / "capabilities",
        repo_root=_REPO_ROOT,
        catalog_path=_APP_ROOT / "capability-catalog.jsonl",
    )
    print(f"wrote {count} implementation record(s) to capability-catalog.jsonl")


if __name__ == "__main__":
    main()
