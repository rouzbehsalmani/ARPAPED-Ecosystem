"""Cross-language invariant: Rust Bridge -> Python process capability."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SAMPLE = ROOT / "bridge" / "samples" / "hello_world"
PY_CAP = SAMPLE / "capabilities" / "console" / "write_process" / "executor.py"
CATALOG = SAMPLE / "capability-catalog.jsonl"
RUST_BRIDGE = ROOT / "bridge" / "tests" / "cross_language" / "rust_bridge" / "Cargo.toml"


def make_catalog() -> Path:
    # Production catalog uses `operations`; the small Rust test Bridge models
    # this as `operation`. Normalize only at the test boundary. The production
    # catalog, Contract and Capability are not changed by this adapter.
    entries = [
        json.loads(line)
        for line in CATALOG.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    entry = next(
        e for e in entries if e["implementation_id"] == "console.write.process"
    )
    entry["operation"] = entry.pop("operations")
    entry["executor_path"] = [sys.executable, str(PY_CAP)]

    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", suffix=".jsonl", delete=False
    ) as f:
        json.dump(entry, f)
        f.write("\n")
        return Path(f.name)


def main() -> None:
    catalog = make_catalog()
    try:
        env = os.environ.copy()
        env["ARPAPED_TEST_CATALOG"] = str(catalog)
        request = {
            "capability_id": "console.write",
            "contract_version": "2.0.0",
            "operation": "write",
            "input": {"message": "ARPAPED cross-language", "format": "uppercase"},
        }
        completed = subprocess.run(
            ["cargo", "run", "--quiet", "--manifest-path", str(RUST_BRIDGE)],
            cwd=ROOT,
            input=json.dumps(request) + "\n",
            text=True,
            capture_output=True,
            env=env,
            check=True,
        )
        if completed.stderr:
            print(completed.stderr, end="", file=sys.stderr)
        response = json.loads(completed.stdout.strip().splitlines()[-1])
        assert response["ok"] is True, response
        assert response["implementation_id"] == "console.write.process"
        assert response["output"] == {}
        assert response["trace"] == [
            "validated",
            "discovered",
            "policy_evaluated",
            "selected",
            "executed",
        ]
        print("PASS: Rust Bridge -> Python capability")
    finally:
        catalog.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
