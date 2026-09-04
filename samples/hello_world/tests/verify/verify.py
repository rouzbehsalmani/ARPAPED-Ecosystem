"""Headless verification harness for the hello_world sample (Phase 7,
2-RULES.md "Verification contract"; 0-WALKTHROUGH.md step 6).

Lives outside app/ and capabilities/ (0-WALKTHROUGH.md step 6: "Lives
outside the application packages"). Confirms every contract and manifest
under this sample validates against its schema, reuses the SAME Bridge
app/requests.py builds (never a second one), drives the same six calls
app/main.py does through the same request-construction point, and
asserts every observed trace equals validated -> discovered ->
policy_evaluated -> selected -> executed -- copied verbatim from the
response, never hand-written. Each call runs under a bounded per-stage
timeout (`call_with_timeout`, R5) instead of an unbounded wait.

No operator-decision-window case: that requirement (0-WALKTHROUGH.md
step 6) is for a reactive/ongoing system where a scripted action must
land between two automatic ticks -- this sample has no such loop (six
sequential calls, then done), so there is nothing to interleave. Not
applicable here, not silently skipped either.

On every check passing, writes state/verification-record.json and
records the completed cycle into the DEP episode store as its own last
act (0-WALKTHROUGH.md step 6/7, 1-CYCLE.md Phase 8 Gate 31) -- so
"verified" and "recorded" are the same event: a harness failure, not a
step a later phase could forget.

Run from anywhere (sys.path is set up below):
    python -m samples.hello_world.tests.verify.verify
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SAMPLE_ROOT = Path(__file__).resolve().parents[2]
_SCHEMAS_DIR = _REPO_ROOT / "schemas"
_STATE_DIR = _SAMPLE_ROOT / "state"

sys.path.insert(0, str(_REPO_ROOT))

import jsonschema  # noqa: E402
import yaml  # noqa: E402

from samples.hello_world.app.requests import resolve  # noqa: E402
from dep.episode_store import save_episode  # noqa: E402


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((_SCHEMAS_DIR / name).read_text(encoding="utf-8"))


_CONTRACT_SCHEMA = _load_schema("component-contract.schema.json")
_MANIFEST_SCHEMA = _load_schema("capability-manifest.schema.json")
_VERIFICATION_RECORD_SCHEMA = _load_schema("verification-record.schema.json")

EXPECTED_TRACE = ("validated", "discovered", "policy_evaluated", "selected", "executed")

# Mirrors app/main.py's six calls exactly -- the harness drives the same
# consumer-visible interactions the real entry point does, through the
# same dispatcher (app/requests.py's resolve), never a shortcut.
CALLS = [
    ("console_write", "write", {"message": "This is a test of the Bridge's console.write capability."}),
    ("console_write", "write", {"message": "Hello, world!", "format": "uppercase"}),
    ("greeting_compose", "compose", {"name": "ARPAPED"}),
    ("console_write_legacy", "write", {"text": "console.write 1.0.0 is real and independently callable."}),
    ("greeting_compose_process", "compose", {"name": "ARPAPED (via Rust)"}),
    ("console_write_process", "write", {"message": "This line is printed by a second Python process, through the Bridge."}),
]


def check_contracts_and_manifests() -> list[dict[str, Any]]:
    """Gate: every contract/manifest under this sample validates against
    its schema -- a prerequisite the harness checks itself, not a final
    afterthought tacked on after the operation checks below."""

    checks = []
    for contract_path in sorted((_SAMPLE_ROOT / "contracts").glob("*.yaml")):
        data = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
        check_id = f"contract-valid:{contract_path.name}"
        description = f"{contract_path.name} validates against component-contract.schema.json"
        try:
            jsonschema.validate(data, _CONTRACT_SCHEMA)
            checks.append({"check_id": check_id, "description": description, "status": "passed"})
        except jsonschema.ValidationError as exc:
            checks.append({"check_id": check_id, "description": description, "status": "failed", "observed": exc.message})

    for manifest_path in sorted((_SAMPLE_ROOT / "capabilities").rglob("manifest.yaml")):
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        rel = manifest_path.relative_to(_SAMPLE_ROOT).as_posix()
        check_id = f"manifest-valid:{rel}"
        description = f"{rel} validates against capability-manifest.schema.json"
        try:
            jsonschema.validate(data, _MANIFEST_SCHEMA)
            checks.append({"check_id": check_id, "description": description, "status": "passed"})
        except jsonschema.ValidationError as exc:
            checks.append({"check_id": check_id, "description": description, "status": "failed", "observed": exc.message})

    return checks


def check_capability_operations() -> list[dict[str, Any]]:
    """Gate: every declared capability operation, called through the SAME
    request-construction point app/main.py uses, under a bounded
    per-stage timeout (R5), with its full observed trace reaching
    executed -- copied from the real response, never hand-written."""

    checks = []
    for i, (name, operation, input_) in enumerate(CALLS, start=1):
        check_id = f"call:{i}:{name}"
        description = f"{name}.{operation} (call {i}) reaches every stage"
        try:
            handle = resolve(name, operation)
            response = handle.call_with_timeout(input_, stage_timeout=10.0)
            trace = tuple(response.trace)
            status = "passed" if trace == EXPECTED_TRACE else "failed"
            check = {
                "check_id": check_id,
                "description": f"{description} through {response.implementation_id}",
                "status": status,
                "check_type": "capability_operation",
                "trace": list(trace),
            }
            if status == "failed":
                check["observed"] = f"expected {list(EXPECTED_TRACE)}, got {list(trace)}"
            checks.append(check)
        except Exception as exc:
            checks.append({"check_id": check_id, "description": description, "status": "failed", "observed": str(exc)})

    return checks


def main() -> None:
    checks = check_contracts_and_manifests() + check_capability_operations()
    passed = sum(1 for c in checks if c["status"] == "passed")
    failed = sum(1 for c in checks if c["status"] == "failed")
    status = "verified" if failed == 0 else "failed"

    verification_record = {
        "verification_id": f"hello-world-{uuid.uuid4().hex[:12]}",
        "state_ref": _SAMPLE_ROOT.relative_to(_REPO_ROOT).as_posix(),
        "harness": Path(__file__).resolve().relative_to(_REPO_ROOT).as_posix(),
        "checks": checks,
        "passed": passed,
        "failed": failed,
        "status": status,
    }
    jsonschema.validate(verification_record, _VERIFICATION_RECORD_SCHEMA)

    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    record_path = _STATE_DIR / "verification-record.json"
    record_path.write_text(json.dumps(verification_record, indent=2), encoding="utf-8")

    for c in checks:
        mark = "PASS" if c["status"] == "passed" else "FAIL"
        print(f"[{mark}] {c['check_id']}: {c['description']}")
    print(f"\n{passed} passed, {failed} failed -- {status}")

    if status != "verified":
        print("\nNot recording an episode for a failed cycle.")
        raise SystemExit(1)

    seen_names: list[str] = []
    for name, _, _ in CALLS:
        if name not in seen_names:
            seen_names.append(name)

    cycle_report = {
        "goal": {
            "description": "Re-verify the hello_world sample's contract -> manifest -> executor -> Bridge wiring end to end (regression, no new capability)."
        },
        "starting_state": _SAMPLE_ROOT.relative_to(_REPO_ROOT).as_posix(),
        "decisions": [
            {
                "responsibility": name,
                "decision": "reuse",
                "reason": f"{name!r} already implemented and registered; this cycle re-verifies it end to end and changes nothing.",
            }
            for name in seen_names
        ],
        "new_capabilities": [],
        "reused_capabilities": seen_names,
        "bridge_integration": (
            "Every call above resolved through app/requests.py's single request-construction "
            "point and the same canonical Bridge app/main.py uses (R6/R8); every observed trace "
            "reached executed."
        ),
        "verification": {
            "harness": verification_record["harness"],
            "verification_record_ref": record_path.relative_to(_REPO_ROOT).as_posix(),
            "status": status,
        },
        "resulting_state": _SAMPLE_ROOT.relative_to(_REPO_ROOT).as_posix(),
        "next_cycle_readiness": (
            "capability-catalog.jsonl, dependencies.yaml, and this verification record are "
            "everything the next cycle needs; no private memory of this run is required."
        ),
    }

    episode_dir = save_episode(cycle_report, verification_record, episodes_dir=_STATE_DIR / "episodes")
    print(f"Recorded episode: {episode_dir.relative_to(_REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
