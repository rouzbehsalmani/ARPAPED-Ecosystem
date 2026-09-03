"""Cross-language invariant: Python Bridge -> Rust process capability.

This deliberately leaves the production Bridge, Contract, Manifest and
Capability sources untouched. It builds the existing Rust capability,
clones only the generated catalog into a temporary file, pins the Rust
implementation there, and runs a real Bridge request. The Rust capability
then performs its declared nested call through the same Python Bridge.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SAMPLE = ROOT / "bridge" / "samples" / "hello_world"
RUST_CAP = SAMPLE / "capabilities" / "greeting" / "compose_process"
CATALOG = SAMPLE / "capability-catalog.jsonl"


def rust_binary() -> Path:
    name = "greeting_compose_process.exe" if os.name == "nt" else "greeting_compose_process"
    return RUST_CAP / "target" / "debug" / name


def build_rust_capability() -> None:
    subprocess.run(
        ["cargo", "build", "--manifest-path", str(RUST_CAP / "Cargo.toml")],
        cwd=ROOT,
        check=True,
    )
    binary = rust_binary()
    if not binary.exists():
        raise AssertionError(f"Rust capability binary was not produced: {binary}")


def make_catalog() -> Path:
    entries = [json.loads(line) for line in CATALOG.read_text(encoding="utf-8").splitlines() if line.strip()]
    rust_entry = next(e for e in entries if e["implementation_id"] == "greeting.compose.process")
    rust_entry["executor_path"] = str(rust_binary())
    # Pin the exact implementation under test; all other entries stay as the
    # repository catalog defines them, including console.write for Rust's
    # declared nested dependency.
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".jsonl", delete=False) as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
        return Path(f.name)


def main() -> None:
    if platform.system() == "Windows":
        # Keep stdout/stderr from cargo useful but don't let the test accidentally
        # depend on shell parsing or PATH quoting.
        pass

    build_rust_capability()
    catalog = make_catalog()
    try:
        sys.path.insert(0, str(ROOT))
        from bridge.assembler import assemble_from_catalog
        from bridge.bridge import Bridge
        from bridge.policy import StaticPolicyEngine
        from bridge.registry import CapabilityRegistry
        from bridge.selector import DeterministicSelector

        registry = CapabilityRegistry()
        bridge = Bridge(registry, StaticPolicyEngine(), DeterministicSelector())
        assemble_from_catalog(catalog, registry, bridge=bridge)

        bound = bridge.resolve(
            "greeting.compose",
            "compose",
            "1.0.0",
            implementation_id="greeting.compose.process",
        )
        response = bound.call({"name": "ARPAPED cross-language"})

        assert response.implementation_id == "greeting.compose.process"
        assert response.output == {}
        assert response.trace == ("validated", "discovered", "policy_evaluated", "selected", "executed")
        print("PASS: Python Bridge -> Rust capability -> nested Python capability")
    finally:
        catalog.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
