"""Coverage for runtime_log.py: schema validation on record, a failure
event (no selection/evidence, possibly empty trace) round-trips
correctly, and concurrent writers never corrupt the file -- the real
concurrency reality confirmed against sample/hello_world's own
web/serve/executor.py, which runs a ThreadingHTTPServer (one thread per
request), so a Bridge's event_sink genuinely can be called from many
threads at once.

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
        "capability_id": "console.write",
        "operation": "write",
        "contract_version": ">=2.0.0,<3.0.0",
        "input": {"message": "hi"},
        "trace": ["validated", "discovered", "policy_evaluated", "selected", "executed"],
        "implementation_id": "console.write.v2",
        "selection": {
            "capability_id": "console.write", "operation": "write", "contract_version": ">=2.0.0,<3.0.0",
            "candidates": [{"implementation_id": "console.write.v2", "priority": 200}],
            "selected": "console.write.v2", "reason": "highest priority (200) among 1 policy-allowed candidate",
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
            "request_id": uuid.uuid4().hex, "capability_id": "console.write", "operation": "write",
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


if __name__ == "__main__":
    unittest.main()
