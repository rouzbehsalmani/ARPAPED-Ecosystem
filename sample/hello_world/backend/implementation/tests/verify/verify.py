"""Headless verification harness for the hello_world sample (Phase 7,
blueprint/2-RULES.md "Verification contract"; blueprint/0-WALKTHROUGH.md step 6).

Lives outside app/ and capabilities/ (blueprint/0-WALKTHROUGH.md step 6: "Lives
outside the application packages"). Confirms every contract and manifest
under this sample validates against its schema, reuses the SAME Bridge
app/requests.py builds (never a second one), drives the same six calls
app/main.py does through the same request-construction point, and
asserts every observed trace equals validated -> discovered ->
policy_evaluated -> selected -> executed -- copied verbatim from the
response, never hand-written. Each call runs under a bounded per-stage
timeout (`call_with_timeout`, R5) instead of an unbounded wait.

No operator-decision-window case: that requirement (blueprint/0-WALKTHROUGH.md
step 6) is for a reactive/ongoing system where a scripted action must
land between two automatic ticks -- this sample has no such loop (six
sequential calls, then done), so there is nothing to interleave. Not
applicable here, not silently skipped either.

On every check passing, writes state/verification-record.json and
records the completed cycle into the DEP episode store as its own last
act (blueprint/0-WALKTHROUGH.md step 6/7, blueprint/1-CYCLE.md Phase 8 Gate 31) -- so
"verified" and "recorded" are the same event: a harness failure, not a
step a later phase could forget.

Run from anywhere (sys.path is set up below):
    python -m sample.hello_world.backend.implementation.tests.verify.verify
"""

from __future__ import annotations

import functools
import json
import platform
import subprocess
import sys
import threading
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[6]
_HELLO_WORLD_ROOT = Path(__file__).resolve().parents[4]
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_IMPLEMENTATION_ROOT = _BACKEND_ROOT / "implementation"
_SAMPLE_SCHEMAS_DIR = _REPO_ROOT / "sample" / "schemas"
_BLUEPRINT_SCHEMAS_DIR = _REPO_ROOT / "blueprint" / "schemas"
_STATE_DIR = _BACKEND_ROOT / "state"

sys.path.insert(0, str(_REPO_ROOT))

import jsonschema  # noqa: E402
import yaml  # noqa: E402

from sample.hello_world.backend.runtime.app.requests import resolve  # noqa: E402
from blueprint.dep.episode_store import save_episode  # noqa: E402
from blueprint.dep.state_ref import capture_state_ref  # noqa: E402


def _load_schema(schemas_dir: Path, name: str) -> dict[str, Any]:
    return json.loads((schemas_dir / name).read_text(encoding="utf-8"))


_CONTRACT_SCHEMA = _load_schema(_SAMPLE_SCHEMAS_DIR, "component-contract.schema.json")
_MANIFEST_SCHEMA = _load_schema(_SAMPLE_SCHEMAS_DIR, "capability-manifest.schema.json")
_VERIFICATION_RECORD_SCHEMA = _load_schema(_BLUEPRINT_SCHEMAS_DIR, "verification-record.schema.json")

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
    """Gate: every BACKEND contract/manifest validates against its schema
    -- a prerequisite the harness checks itself, not a final afterthought
    tacked on after the operation checks below. backend/implementation/contracts/ is
    backend's own -- not shared with frontend/implementation/contracts/, which frontend's
    own build_catalog.py validates as part of its own build step (two
    agents, two territories, no shared file to conflict over). A contract
    that merely resembles a frontend one (e.g. "compose a greeting") is
    never assumed to BE it -- ownership is per-runtime, always."""

    checks = []
    for contract_path in sorted((_BACKEND_IMPLEMENTATION_ROOT / "contracts").glob("*.yaml")):
        data = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
        check_id = f"contract-valid:{contract_path.name}"
        description = f"{contract_path.name} validates against component-contract.schema.json"
        try:
            jsonschema.validate(data, _CONTRACT_SCHEMA)
            checks.append({"check_id": check_id, "description": description, "status": "passed"})
        except jsonschema.ValidationError as exc:
            checks.append({"check_id": check_id, "description": description, "status": "failed", "observed": exc.message})

    for manifest_path in sorted((_BACKEND_IMPLEMENTATION_ROOT / "capabilities").rglob("manifest.yaml")):
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        rel = manifest_path.relative_to(_HELLO_WORLD_ROOT).as_posix()
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
    executed -- copied from the real response, never hand-written.

    Also folds in the Bridge's own observed `selection` (2-RULES.md
    glossary -- Decision Context, distinct from this harness's own
    decisions[] entries in the cycle report) and, for a process-kind
    operation, `evidence` -- both copied verbatim from `response`, the
    same authenticity discipline `trace` already gets (R8, Gate 28/37),
    never invented or reconstructed here."""

    checks = []
    console_write_response = None
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
                "input": input_,
                "description": f"{description} through {response.implementation_id}",
                "status": status,
                "check_type": "capability_operation",
                "trace": list(trace),
                "selection": response.selection,
            }
            if response.evidence is not None:
                check["evidence"] = response.evidence
            if status == "failed":
                check["observed"] = f"expected {list(EXPECTED_TRACE)}, got {list(trace)}"
            checks.append(check)
            if i == 1:
                console_write_response = response
        except Exception as exc:
            checks.append({"check_id": check_id, "description": description, "status": "failed", "observed": str(exc)})

    if console_write_response is not None:
        checks.append(_check_console_write_implementation_pinning(console_write_response))

    return checks


def _check_console_write_implementation_pinning(response: Any) -> dict[str, Any]:
    """Permanent regression check (regression_for
    "console-write-priority-flip-2026-09"): `app/dependencies.yaml`'s
    unpinned `console_write` name (contract_version `>=2.0.0,<3.0.0`, no
    `implementation_id`) must keep resolving to `console.write.v2`, its
    highest-priority (200) implementation -- not `console.write.process`
    (priority 150), a SECOND, equally version-compatible implementation
    the Bridge genuinely discovers and policy-allows for this exact call
    (see `response.selection.candidates`, always 2 entries for this
    call). Nothing else in this harness asserts which `implementation_id`
    an unpinned name resolves to; this is the one check that would have
    caught the real regression observed while this check itself was
    being built: bumping `console.write.process`'s own manifest priority
    above 200 silently flips which of two live, competing implementations
    answers every unpinned `console_write` call, while every trace still
    reaches `executed` and every other check here still passes -- a
    silent default (2-RULES.md "No silent defaults on what resolution
    depends on") this harness had no way to notice before `selection` was
    a real, observed field to assert against."""

    expected_implementation_id = "console.write.v2"
    actual_implementation_id = response.implementation_id
    status = "passed" if actual_implementation_id == expected_implementation_id else "failed"
    check = {
        "check_id": "call:1:console_write:implementation-pinning-regression",
        "input": CALLS[0][2],
        "description": (
            "The unpinned 'console_write' name (app/dependencies.yaml) keeps resolving to "
            "console.write.v2, its highest-priority policy-allowed candidate"
        ),
        "status": status,
        "check_type": "regression",
        "regression_for": "console-write-priority-flip-2026-09",
        "expected": expected_implementation_id,
        "actual": actual_implementation_id,
        "selection": response.selection,
    }
    if status == "failed":
        check["observed"] = (
            f"expected {expected_implementation_id!r}, got {actual_implementation_id!r} -- "
            f"{response.selection['reason']}"
        )
    return check


def check_frontend_bridge() -> list[dict[str, Any]]:
    """Gate 19: the shipped frontend has its own resolved Bridge (Bridge
    Core + Adapter, blueprint/2-RULES.md Bridge glossary) -- this must be
    exercised too, not just the backend capability in isolation. Mirrors
    the REAL deployment topology exactly (../../../../README.md "Two
    servers, not one"): starts web.serve for real (through the SAME resolve()
    everything else here uses) as a pure API, PLUS a separate, test-only
    static server for frontend/runtime/ (not a capability -- serving
    THIS test's own static assets is scaffolding for the test, the same
    posture the harness itself already has toward the application it
    verifies), then runs the frontend's own headless verification (Node)
    against BOTH and folds its check(s) into this record -- one
    verification event covering both runtimes, not two separately-
    rememberable ones."""

    frontend_root = _HELLO_WORLD_ROOT / "frontend"
    backend_server = resolve("web_serve", "start")
    backend_url = backend_server.call({"host": "127.0.0.1", "port": 0}).output["url"]

    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(frontend_root / "runtime"))
    frontend_httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    frontend_thread = threading.Thread(target=frontend_httpd.serve_forever, daemon=True)
    frontend_thread.start()
    frontend_url = f"http://127.0.0.1:{frontend_httpd.server_address[1]}"

    try:
        proc = subprocess.run(
            ["node", str(frontend_root / "implementation" / "tests" / "verify.js"), backend_url, frontend_url],
            capture_output=True, text=True, timeout=15.0,
        )
        if not proc.stdout.strip():
            return [{
                "check_id": "call:1:greeting_render (frontend)",
                "description": "greeting_render.render reaches every stage through the frontend's own Bridge",
                "status": "failed",
                "observed": f"node produced no output (exit {proc.returncode}): {proc.stderr}",
            }]
        return json.loads(proc.stdout)
    finally:
        resolve("web_serve", "stop").call({})
        frontend_httpd.shutdown()
        frontend_httpd.server_close()


def main() -> None:
    checks = check_contracts_and_manifests() + check_capability_operations() + check_frontend_bridge()
    passed = sum(1 for c in checks if c["status"] == "passed")
    failed = sum(1 for c in checks if c["status"] == "failed")
    status = "verified" if failed == 0 else "failed"

    verification_record = {
        "verification_id": f"hello-world-{uuid.uuid4().hex[:12]}",
        "state_ref": _HELLO_WORLD_ROOT.relative_to(_REPO_ROOT).as_posix(),
        "harness": Path(__file__).resolve().relative_to(_REPO_ROOT).as_posix(),
        "environment": {
            "os": platform.system(),
            "os_release": platform.release(),
            "arch": platform.machine(),
            "runtime": f"CPython {platform.python_version()}",
        },
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

    # check_ids per responsibility (dataset_builder.py's own join key --
    # never guessed by matching a responsibility name against a check's
    # description string): every reused capability links to the call(s)
    # that exercised it this cycle, by the same "call:{i}:{name}" ids
    # check_capability_operations() already assigns.
    check_ids_by_name: dict[str, list[str]] = {}
    for i, (name, _, _) in enumerate(CALLS, start=1):
        check_ids_by_name.setdefault(name, []).append(f"call:{i}:{name}")
    check_ids_by_name["console_write"].append("call:1:console_write:implementation-pinning-regression")

    reused_decisions = [
        {
            "responsibility": name,
            "decision": "reuse",
            "reason": f"{name!r} already implemented and registered; unchanged by this cycle.",
            "check_ids": check_ids_by_name[name],
        }
        for name in seen_names
    ]
    # console_write's own decision additionally carries a real, observed
    # failure/correction pair (2-RULES.md glossary), not a narrated
    # after-the-fact summary: while building the permanent regression
    # check above, console.write.process's own manifest priority was
    # actually bumped from 150 to 250, the harness re-run for real (RED),
    # then reverted and re-run again (GREEN) -- these are the two real
    # `selection.reason` strings the Bridge itself produced for those two
    # runs, quoted verbatim, not reconstructed.
    for decision in reused_decisions:
        if decision["responsibility"] == "console_write":
            decision["failure"] = {
                "summary": "console-write-priority-flip-2026-09: unpinned console_write silently resolved to console.write.process instead of console.write.v2",
                "detail": (
                    "console.write.process's own manifest priority was raised from 150 to 250 "
                    "(above console.write.v2's 200) to prove no existing check would notice. It "
                    "didn't: every trace still reached executed and every check but the new "
                    "regression check still passed. Real observed Bridge selection for that run: "
                    "capability_id=console.write, candidates=[console.write.process@250, "
                    "console.write.v2@200], selected=console.write.process, "
                    "reason=\"highest priority (250) among 2 policy-allowed candidates\" -- "
                    "check call:1:console_write:implementation-pinning-regression failed with "
                    "observed=\"expected 'console.write.v2', got 'console.write.process' -- "
                    "highest priority (250) among 2 policy-allowed candidates\"."
                ),
            }
            decision["correction"] = {
                "summary": "Reverted console.write.process's manifest priority to 150",
                "detail": (
                    "Priority reverted 250 -> 150, catalog rebuilt, harness re-run. Real observed "
                    "Bridge selection for the corrected run: candidates=[console.write.process@150, "
                    "console.write.v2@200], selected=console.write.v2, reason=\"highest priority "
                    "(200) among 2 policy-allowed candidates\" -- "
                    "call:1:console_write:implementation-pinning-regression now passes, and stays "
                    "in the harness permanently so this exact regression is caught immediately if "
                    "it ever recurs, rather than staying invisible to every other check the way it "
                    "was before this check existed."
                ),
            }

    cycle_report = {
        "goal": {
            "description": (
                "Turn hello_world into a web app proving the per-runtime Bridge principle "
                "(blueprint/2-RULES.md Bridge/Bridge Core/Bridge Adapter glossary, R4 Local/"
                "Worker/Remote taxonomy): a Python backend (unchanged capabilities) plus a new "
                "web.serve capability exposing it over sample/schemas/bridge-protocol.schema.json, "
                "and a genuine JavaScript frontend Bridge whose OWN greeting.render capability runs "
                "Local and depends on backend's console.write via executor_kind: remote -- two "
                "independently-owned contracts (backend/implementation/contracts/, frontend/implementation/contracts/), never a "
                "shared one, referenced across the boundary only by capability ID (R4)."
            )
        },
        "starting_state": _HELLO_WORLD_ROOT.relative_to(_REPO_ROOT).as_posix(),
        "decisions": reused_decisions + [
            {
                "responsibility": "web.serve",
                "decision": "create",
                "reason": "Nothing exposed the backend Bridge over a network boundary; needed so a different runtime's own Bridge Adapter (the frontend's) can reach it as executor_kind: remote (R4).",
            },
            {
                "responsibility": "greeting.render (frontend)",
                "decision": "create",
                "reason": "Frontend's own capability, not a second implementation of backend's greeting.compose -- a real app's frontend-facing and backend-facing shapes rarely turn out identical, so this one has its own contract (frontend/implementation/contracts/greeting.render.contract.yaml) and its own output shape (returns the composed text for display), while still depending on backend's console.write by ID (R4), proving a specific capability can run Local in one runtime while composing a dependency that only exists Remote from it.",
            },
        ],
        "new_capabilities": ["web.serve", "greeting.render (frontend/runtime/capabilities/greeting/render)"],
        "reused_capabilities": seen_names,
        "bridge_integration": (
            "Backend: every call above resolved through app/requests.py's single "
            "request-construction point and the same canonical Bridge app/main.py uses (R6/R8). "
            "Frontend: greeting_render resolved through frontend/runtime/app.js's own Bridge Adapter and "
            "Bridge Core (frontend/runtime/bridge/core.js), whose console.write dependency (declared by ID, "
            "not by sharing backend's contract) resolved as executor_kind: remote to the SAME "
            "backend Bridge over web.serve's /bridge endpoint -- every observed trace, in both "
            "runtimes, reached executed."
        ),
        "verification": {
            "harness": verification_record["harness"],
            "verification_record_ref": record_path.relative_to(_REPO_ROOT).as_posix(),
            "status": status,
        },
        "resulting_state": _HELLO_WORLD_ROOT.relative_to(_REPO_ROOT).as_posix(),
        "resulting_state_ref": capture_state_ref(
            [
                _BACKEND_IMPLEMENTATION_ROOT / "contracts",
                _BACKEND_IMPLEMENTATION_ROOT / "capabilities",
                _BACKEND_ROOT / "runtime" / "capability-catalog.jsonl",
                _HELLO_WORLD_ROOT / "frontend" / "implementation" / "contracts",
                _HELLO_WORLD_ROOT / "frontend" / "implementation" / "capabilities",
                _HELLO_WORLD_ROOT / "frontend" / "runtime" / "capability-catalog.jsonl",
            ],
            repo_root=_REPO_ROOT,
        ),
        "next_cycle_readiness": (
            "capability-catalog.jsonl, dependencies.yaml, and this verification record are "
            "everything the next cycle needs; no private memory of this run is required."
        ),
    }

    episode_dir = save_episode(cycle_report, verification_record, episodes_dir=_STATE_DIR / "episodes")
    print(f"Recorded episode: {episode_dir.relative_to(_REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
