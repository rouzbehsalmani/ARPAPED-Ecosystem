"""Generates this sample's capability-catalog.jsonl (Phase 8, Publish).

Run manually whenever anything under capabilities/ or the contracts it
references changes:
    python -m bridge.samples.hello_world.build_catalog

Uses rebuild_catalog (bridge/assembler.py), which walks capabilities/ once
and regenerates the catalog from scratch. That full walk is appropriate here
because this sample's whole tree predates the catalog mechanism. A growing
ecosystem publishing capabilities one at a time should call
append_to_catalog per newly published manifest instead -- O(1) per
publish, never re-walking what's already in the catalog. See
app/requests.py, which reads the generated catalog at startup instead of
walking capabilities/ itself.
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
