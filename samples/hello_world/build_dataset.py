"""Builds this sample's dataset.jsonl from its own episode corpus
(dep.dataset_builder, dep/MANIFEST.yaml) -- mirrors build_catalog.py's
relationship to bridge/assembler.py: the generic logic lives in dep/,
this sample calls it against its own state/episodes/.

Run after tests/verify/verify.py has recorded at least one episode:
    python -m samples.hello_world.build_dataset
"""

from pathlib import Path

from dep.dataset_builder import build_dataset

_SAMPLE_ROOT = Path(__file__).resolve().parent
_EPISODES_DIR = _SAMPLE_ROOT / "state" / "episodes"
_OUTPUT_PATH = _SAMPLE_ROOT / "dataset.jsonl"


def main():
    count = build_dataset(episodes_dir=_EPISODES_DIR, output_path=_OUTPUT_PATH)
    print(f"wrote {count} row(s) to {_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
