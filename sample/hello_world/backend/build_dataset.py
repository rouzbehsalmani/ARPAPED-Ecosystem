"""Builds this sample's dataset.jsonl from its own episode corpus
(blueprint.dep.dataset_builder, blueprint/dep/MANIFEST.yaml) -- mirrors build_catalog.py's
relationship to sample/hello_world/backend/runtime/bridge/assembler.py: the generic logic lives in blueprint/dep/,
this sample calls it against its own state/episodes/.

Run after tests/verify/verify.py has recorded at least one episode:
    python -m sample.hello_world.backend.build_dataset
"""

from pathlib import Path

from blueprint.dep.dataset_builder import build_dataset

_SAMPLE_ROOT = Path(__file__).resolve().parent
_EPISODES_DIR = _SAMPLE_ROOT / "state" / "episodes"
_OUTPUT_PATH = _SAMPLE_ROOT / "dataset.jsonl"


def main():
    count = build_dataset(episodes_dir=_EPISODES_DIR, output_path=_OUTPUT_PATH)
    print(f"wrote {count} row(s) to {_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
