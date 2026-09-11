"""Records real Bridge calls as they actually happen (blueprint/dep/MANIFEST.yaml's
runtime_log) -- the piece missing from every other blueprint/dep/ tool,
all of which are scoped to one AGENT DEVELOPMENT CYCLE
(episode_store/finish_cycle/checkpoint, 1-CYCLE.md Phase 0-9). Confirmed
directly: bridge.py/registry.py/policy.py/selector.py write nothing to
disk -- a real production call computes trace/selection/evidence in
Bridge.handle and simply discards it unless a caller (today, only
verify.py's harness) explicitly captures it. There is no "runtime DEP
artifact": nothing records what an ecosystem's Bridge actually did while
genuinely serving requests, only what a harness scripted it to do.

`RuntimeEventLog(path).record` is meant to be passed as a Bridge's own
`event_sink` (sample/hello_world/backend/runtime/bridge/bridge.py) --
`Bridge.handle` calls it once per real call, success or failure, with a
normalized event matching runtime-event.schema.json. `bridge.py` itself
never imports this module (stays fully decoupled from blueprint.dep, the
same posture it already has toward ProcessExecutorPool via
hasattr/getattr) -- an application's own request-construction point
(e.g. sample/hello_world/backend/runtime/app/requests.py) is what wires
a RuntimeEventLog in, by passing its `.record` method as `event_sink`.

JSONL, not one-directory-per-event (episode_store's shape): a cycle
happens rarely, a Bridge's calls happen continuously, so this needs to
be cheap to append to -- the same append style
sample/hello_world/backend/runtime/bridge/assembler.py's catalog writer
already uses for capability-catalog.jsonl. Generic like every other
blueprint/dep/ tool: `path` is always given by the caller, never
defaulted.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import jsonschema

_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "runtime-event.schema.json"
_RUNTIME_EVENT_SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


class RuntimeEventLog:
    """One append-only JSONL file. `record` is safe under concurrent
    callers (a real Bridge can be called from many threads at once --
    confirmed for real: sample/hello_world/backend/runtime/capabilities/web/serve/executor.py
    runs a ThreadingHTTPServer, one thread per request) -- a single lock
    serializes the validate-then-append, so two concurrent calls can
    never interleave their own JSON onto the same line or corrupt the
    file.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def record(self, event: dict[str, Any]) -> None:
        jsonschema.validate(event, _RUNTIME_EVENT_SCHEMA)
        line = json.dumps(event)
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as f:
                f.write(line)
                f.write("\n")


def read_events(path: Path):
    """Yields every event in `path`, in file order -- the read-side
    counterpart to `RuntimeEventLog.record`, for anything that later
    wants to consume this log (a dataset projection, an audit script).
    Not schema-validated on read: a log a Bridge is still actively
    appending to is legitimately being read mid-write elsewhere, and
    re-validating every line on every read is the writer's job, already
    done once, not the reader's to repeat.
    """

    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)
