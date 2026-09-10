"""Headless verification harness for the hello_world sample (Phase 7,
blueprint/2-RULES.md "Verification contract"; blueprint/0-WALKTHROUGH.md step 6).

Lives outside app/ and capabilities/ (blueprint/0-WALKTHROUGH.md step 6: "Lives
outside the application packages"). Confirms every contract and manifest
under this sample validates against its schema, reuses the SAME Bridge
app/requests.py builds (never a second one), drives the same nine calls
app/main.py does through the same request-construction point, and
asserts every observed trace equals validated -> discovered ->
policy_evaluated -> selected -> executed -- copied verbatim from the
response, never hand-written. Each call runs under a bounded per-stage
timeout (`call_with_timeout`, R5) instead of an unbounded wait.

The three counter calls (calls 7-9, hello/hello/world) additionally carry
a deterministic invariant: in ONE fresh process the observed running
counts must be [1, 2, 1] -- proof that counter.count's per-word state
survives repeated invocations within a single runtime, its contract's
entire state_scope.

No operator-decision-window case: that requirement (blueprint/0-WALKTHROUGH.md
step 6) is for a reactive/ongoing system where a scripted action must
land between two automatic ticks -- this sample has no such loop (nine
sequential calls, then done), so there is nothing to interleave. Not
applicable here, not silently skipped either.

On every check passing, writes state/verification-record.json and stops
there -- this harness's own job is done. Recording the completed cycle as
an episode is Phase 8's `blueprint.dep.finish_cycle` task, not this
harness's (blueprint/0-WALKTHROUGH.md step 6): it must run AFTER the
capability catalog is rebuilt, so it can refuse to record on a cyclic
dependency graph (1-CYCLE.md Phase 8 Gate 30/31).

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


def _load_schema(schemas_dir: Path, name: str) -> dict[str, Any]:
    return json.loads((schemas_dir / name).read_text(encoding="utf-8"))


_CONTRACT_SCHEMA = _load_schema(_SAMPLE_SCHEMAS_DIR, "component-contract.schema.json")
_MANIFEST_SCHEMA = _load_schema(_SAMPLE_SCHEMAS_DIR, "capability-manifest.schema.json")
_VERIFICATION_RECORD_SCHEMA = _load_schema(_BLUEPRINT_SCHEMAS_DIR, "verification-record.schema.json")

EXPECTED_TRACE = ("validated", "discovered", "policy_evaluated", "selected", "executed")

# Mirrors app/main.py's nine calls exactly -- the harness drives the same
# consumer-visible interactions the real entry point does, through the
# same dispatcher (app/requests.py's resolve), never a shortcut. The
# counter sequence (7,8,9: hello, hello, world) is deliberate -- in one
# process it must observe running counts [1, 2, 1], the invariant check
# below asserts exactly that.
CALLS = [
    ("console_write", "write", {"message": "This is a test of the Bridge's console.write capability."}),
    ("console_write", "write", {"message": "Hello, world!", "format": "uppercase"}),
    ("greeting_compose", "compose", {"name": "ARPAPED"}),
    ("console_write_legacy", "write", {"text": "console.write 1.0.0 is real and independently callable."}),
    ("greeting_compose_process", "compose", {"name": "ARPAPED (via C#)"}),
    ("console_write_process", "write", {"message": "This line is printed by a second Python process, through the Bridge."}),
    ("hello_counter", "count", {"word": "hello"}),
    ("hello_counter", "count", {"word": "hello"}),
    ("hello_counter", "count", {"word": "world"}),
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
    counter_responses = []
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
            if name == "hello_counter":
                counter_responses.append(response)
        except Exception as exc:
            checks.append({"check_id": check_id, "description": description, "status": "failed", "observed": str(exc)})

    if console_write_response is not None:
        checks.append(_check_console_write_implementation_pinning(console_write_response))
    if len(counter_responses) == 3:
        checks.append(_check_hello_counter_in_process_persistence(counter_responses))

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


def _check_hello_counter_in_process_persistence(responses: list[Any]) -> dict[str, Any]:
    """Invariant check (Gate 37) unique to counter.count: the contract's
    entire state_scope is per-word counts surviving repeated invocations
    within ONE runtime process -- nothing about that persistence is
    observable from any single call's return value, so the harness drives
    the exact word sequence app/main.py uses (hello, hello, world) and
    asserts the three observed running counts are [1, 2, 1]. All three
    calls run in this one fresh harness process, so broken persistence
    (e.g. an executor resetting state per call) fails this check even
    though every individual capability_operation trace still reaches
    executed."""

    observed = [response.output["count"] for response in responses]
    words = [response.output["word"] for response in responses]
    expected = [1, 2, 1]
    status = "passed" if observed == expected else "failed"
    check = {
        "check_id": "call:7-9:hello_counter:in-process-persistence",
        "input": [{"word": word} for word in words],
        "description": "hello, hello, world counted through one process observe running counts [1, 2, 1]",
        "status": status,
        "check_type": "invariant",
        "expected": expected,
        "actual": observed,
    }
    if status == "failed":
        check["observed"] = f"expected {expected}, got {observed}"
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
        print("\nNot publishing an unverified state (R5, Gate 20).")
        raise SystemExit(1)

    # Green record written; this harness's job stops here. The episode for
    # this cycle is recorded by blueprint.dep.finish_cycle (Phase 8), which
    # needs the freshly-rebuilt catalog to refuse on a cyclic graph first.


if __name__ == "__main__":
    main()
