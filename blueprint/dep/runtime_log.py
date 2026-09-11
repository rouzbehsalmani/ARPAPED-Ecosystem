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

`record_resolution` records the OTHER half of an error: how a prior
capability_call failure was actually fixed. Recording only failures and
never their fixes was the gap that prompted this -- `runtime-events.jsonl`
could show a call failing, and (assuming the code was later fixed and
re-run) a LATER call to the same capability succeeding, but nothing ever
said those two were related, let alone WHAT changed between them. This
is deliberately NOT auto-inferred from "the next success after a
failure" -- a later success might be a coincidence (different input, a
transient dependency recovering, a retry that happened to work), so
Bridge.handle has no way to know a given success is genuinely the fix
for a given failure. A resolution is instead an EXPLICIT act by whoever
(agent or human) actually diagnosed and fixed it, the same discipline
agent-cycle-report.schema.json's decisions[].failure/correction already
holds for cycle-level failures -- this is that same idea at runtime-event
granularity, linked by the failed event's own `event_id`, never guessed
by matching capability_id/operation or timestamp proximity.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

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

    def record_resolution(
        self,
        resolves_event_id: str,
        summary: str,
        detail: str,
        verified_by_event_id: Optional[str] = None,
        commit: Optional[str] = None,
    ) -> dict[str, Any]:
        """Records an EXPLICIT resolution for a prior capability_call
        failure (see module docstring) -- never auto-inferred. Returns
        the event actually written.

        `resolves_event_id` is that failure's own `event_id`, always
        supplied by the caller, never looked up here by matching
        capability_id/operation or scanning for "the most recent
        failure" -- an unstated link is not implicitly "whichever
        failure seems related" (2-RULES.md "No silent defaults on what
        resolution depends on"). `verified_by_event_id`, when given, is
        a LATER capability_call success event's own `event_id` -- a
        real, observed re-run proving the fix worked, not just a claim.
        `commit`, when given, is a full git commit sha (typically from
        `blueprint.dep.git_commit_event`) -- optional, since not every
        fix is committed immediately and this module never depends on
        git being present.
        """

        event: dict[str, Any] = {
            "event_id": uuid.uuid4().hex,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "resolves_event_id": resolves_event_id,
            "summary": summary,
            "detail": detail,
        }
        if verified_by_event_id is not None:
            event["verified_by_event_id"] = verified_by_event_id
        if commit is not None:
            event["commit"] = commit
        self.record(event)
        return event


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
