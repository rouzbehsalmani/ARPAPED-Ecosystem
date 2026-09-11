"""Coverage for runtime_log.py: schema validation on record, a failure
event (no selection/evidence, possibly empty trace) round-trips
correctly, concurrent writers never corrupt the file (observed for
real: a Bridge behind a ThreadingHTTPServer, one thread per request,
genuinely calls event_sink from many threads at once), and
record_resolution links a failure to its own fix by event_id.

Run from the repository root:
    python -m unittest blueprint.dep.tests.test_runtime_log -v
"""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import uuid
from pathlib import Path

import jsonschema

from blueprint.dep import runtime_log


def _success_event(**overrides) -> dict:
    event = {
        "event_id": uuid.uuid4().hex,
        "timestamp": "2026-09-11T00:00:00+00:00",
        "request_id": uuid.uuid4().hex,
        "capability_id": "widget.render",
        "operation": "render",
        "contract_version": ">=2.0.0,<3.0.0",
        "input": {"message": "hi"},
        "trace": ["validated", "discovered", "policy_evaluated", "selected", "executed"],
        "implementation_id": "widget.render.v2",
        "selection": {
            "capability_id": "widget.render", "operation": "render", "contract_version": ">=2.0.0,<3.0.0",
            "candidates": [{"implementation_id": "widget.render.v2", "priority": 200}],
            "selected": "widget.render.v2", "reason": "highest priority (200) among 1 policy-allowed candidate",
        },
        "outcome": "success",
    }
    event.update(overrides)
    return event


class RuntimeEventLogTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "state" / "runtime-events.jsonl"

    def tearDown(self):
        self._tmp.cleanup()

    def test_record_writes_valid_jsonl_line(self):
        log = runtime_log.RuntimeEventLog(self.path)
        log.record(_success_event())
        lines = self.path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        json.loads(lines[0])  # must be valid JSON

    def test_record_creates_parent_directory(self):
        log = runtime_log.RuntimeEventLog(self.path)
        self.assertFalse(self.path.parent.exists())
        log.record(_success_event())
        self.assertTrue(self.path.exists())

    def test_record_rejects_schema_invalid_event(self):
        log = runtime_log.RuntimeEventLog(self.path)
        with self.assertRaises(jsonschema.ValidationError):
            log.record({"event_id": "x"})  # missing every other required field

    def test_failure_event_with_empty_trace_round_trips(self):
        # A call that fails BridgeRequest.validate() reaches zero stages --
        # an honest empty trace, not padded to look like more happened.
        log = runtime_log.RuntimeEventLog(self.path)
        event = {
            "event_id": uuid.uuid4().hex, "timestamp": "2026-09-11T00:00:00+00:00",
            "request_id": uuid.uuid4().hex, "capability_id": "widget.render", "operation": "render",
            "contract_version": ">=2.0.0,<3.0.0", "input": {}, "trace": [], "outcome": "failure",
            "error": {"code": "BRIDGE_INVALID_REQUEST", "stage": "validation", "message": "Operation input must be an object"},
        }
        log.record(event)
        (recorded,) = list(runtime_log.read_events(self.path))
        self.assertEqual(recorded, event)

    def test_success_event_requires_selection(self):
        log = runtime_log.RuntimeEventLog(self.path)
        event = _success_event()
        del event["selection"]
        with self.assertRaises(jsonschema.ValidationError):
            log.record(event)

    def test_concurrent_writers_never_corrupt_file(self):
        log = runtime_log.RuntimeEventLog(self.path)
        n = 50
        threads = [
            threading.Thread(target=log.record, args=(_success_event(request_id=f"req-{i}"),))
            for i in range(n)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        recorded = list(runtime_log.read_events(self.path))
        self.assertEqual(len(recorded), n)
        self.assertEqual({e["request_id"] for e in recorded}, {f"req-{i}" for i in range(n)})

    def test_read_events_on_missing_file_yields_nothing(self):
        self.assertEqual(list(runtime_log.read_events(self.path)), [])

    def test_record_resolution_writes_valid_event(self):
        log = runtime_log.RuntimeEventLog(self.path)
        failure = _success_event(outcome="failure", request_id="req-fail")
        del failure["implementation_id"], failure["selection"]
        failure["error"] = {"code": "BRIDGE_EXECUTION_FAILED", "stage": "execution", "message": "boom"}
        log.record(failure)

        event = log.record_resolution(
            resolves_event_id=failure["event_id"],
            summary="widget-render-v2-missing-format-handler",
            detail="Restored the missing lookup-table entry for the affected format value.",
        )
        self.assertEqual(event["resolves_event_id"], failure["event_id"])
        self.assertNotIn("verified_by_event_id", event)
        self.assertNotIn("commit", event)

        recorded = list(runtime_log.read_events(self.path))
        self.assertEqual(len(recorded), 2)
        self.assertEqual(recorded[1], event)

    def test_record_resolution_with_verified_by_and_commit(self):
        log = runtime_log.RuntimeEventLog(self.path)
        event = log.record_resolution(
            resolves_event_id="fail-123",
            summary="s", detail="d",
            verified_by_event_id="success-456",
            commit="a" * 40,
        )
        self.assertEqual(event["verified_by_event_id"], "success-456")
        self.assertEqual(event["commit"], "a" * 40)

    def test_record_resolution_rejects_invalid_commit_shape(self):
        log = runtime_log.RuntimeEventLog(self.path)
        with self.assertRaises(jsonschema.ValidationError):
            log.record_resolution(
                resolves_event_id="fail-123", summary="s", detail="d", commit="not-a-real-sha",
            )

    def test_failure_then_resolution_real_sequence(self):
        # Mirrors a real, observed class of bug: a contract's own enum
        # allows a value some implementation's internal lookup table
        # doesn't handle -- the call fails with BRIDGE_EXECUTION_FAILED/
        # KeyError, the lookup table gets a missing entry restored, and a
        # later call succeeds -- exactly the two-event pair
        # `resolves_event_id`/`verified_by_event_id` exist to link
        # explicitly, never guessed by matching capability_id or
        # timestamp proximity.
        log = runtime_log.RuntimeEventLog(self.path)
        failure = {
            "event_id": uuid.uuid4().hex, "timestamp": "2026-09-11T19:18:25+00:00",
            "request_id": uuid.uuid4().hex, "capability_id": "widget.render", "operation": "render",
            "contract_version": ">=2.0.0,<3.0.0", "input": {"message": "hi", "format": "loud"},
            "trace": ["validated", "discovered", "policy_evaluated", "selected"], "outcome": "failure",
            "error": {"code": "BRIDGE_EXECUTION_FAILED", "stage": "execution",
                      "message": "The selected implementation did not execute the request",
                      "details": {"implementation_id": "widget.render.v2", "cause_type": "KeyError"}},
        }
        log.record(failure)

        retry = _success_event(request_id=uuid.uuid4().hex)
        log.record(retry)

        resolution = log.record_resolution(
            resolves_event_id=failure["event_id"],
            summary="widget-render-v2-missing-format-handler",
            detail="The implementation's own lookup table was missing the entry for a format "
                   "value the contract's enum still allowed; restored it.",
            verified_by_event_id=retry["event_id"],
        )

        recorded = list(runtime_log.read_events(self.path))
        self.assertEqual(len(recorded), 3)
        self.assertEqual(resolution["resolves_event_id"], failure["event_id"])
        self.assertEqual(resolution["verified_by_event_id"], retry["event_id"])


if __name__ == "__main__":
    unittest.main()
