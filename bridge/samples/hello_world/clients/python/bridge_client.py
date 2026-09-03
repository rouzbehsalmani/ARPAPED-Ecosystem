"""Reference client for the process executor protocol
(schemas/process-executor-protocol.schema.json) -- what a process-kind
executor (executor_kind: process, 2-RULES.md R4/R5) exchanges with the
Bridge. A Python capability running as its own separate process uses
this instead of hand-writing connect/frame/dispatch -- the same role
clients/rust/ plays for Rust, proving the protocol isn't a non-Python
escape hatch (see ../../capabilities/console/write_process/executor.py).

`serve_direct`/`serve_factory` are the intended entry points, not
`Connection` directly: they take the exact same native shape a
capability's code already has in-process --
`execute(operation, input, policy) -> output` for `executor_kind: direct`,
`make_executor(dependencies) -> execute` for `executor_kind: factory`
(2-RULES.md R4) -- and serve it over the wire. A capability's own file
never writes the read/dispatch/reply loop itself, and its logic is
identical regardless of whether it ends up running in-process or as its
own process: changing `executor_kind` never touches it.
`direct_adapter.py` is built on exactly these two functions, not a
separate implementation of the same idea.

Lives inside this sample, not under bridge/ (not part of the Bridge
implementation) and not at the repo root (not shared, ecosystem-level
infrastructure -- every consumer is a capability inside this one
sample). Uses the standard library's real JSON parser -- clients/rust/
uses a real one too (serde_json), just an external dependency there
since Rust's stdlib doesn't include one.
"""

from __future__ import annotations

import json
import os
import socket
from typing import Any, Callable


class CallError(Exception):
    """Raised by `Connection.call` when the nested call itself failed --
    carries the Bridge's own `code`/`message`, the same as `BridgeError`
    would in-process.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class Connection:
    """One connection to the Bridge -- one worker in a
    `ProcessExecutorPool` (bridge/process_executor.py). Connects
    immediately, reading `ARPAPED_BRIDGE_PORT` from the environment.

    Low-level primitive that `serve_direct`/`serve_factory` are built
    on; a capability's own code should use those instead of this
    directly (see the module docstring).
    """

    def __init__(self) -> None:
        port = int(os.environ["ARPAPED_BRIDGE_PORT"])
        sock = socket.create_connection(("127.0.0.1", port))
        self._stream = sock.makefile("rw", encoding="utf-8", newline="\n")

    def _write(self, message: dict[str, Any]) -> None:
        self._stream.write(json.dumps(message))
        self._stream.write("\n")
        self._stream.flush()

    def _read(self) -> dict[str, Any] | None:
        line = self._stream.readline()
        if not line:
            return None
        return json.loads(line)

    def call(self, capability_id: str, operation: str, input: dict[str, Any]) -> dict[str, Any]:
        """Makes one nested call to another capability, resolved through
        this implementation's own declared dependencies (R4). Blocks for
        exactly one reply before returning -- a worker connection is
        exclusively borrowed for one invocation's whole duration, so
        that reply can never be confused with a fresh invocation.
        """

        self._write({"call": {"capability_id": capability_id, "operation": operation, "input": input}})
        reply = self._read()
        if reply is None:
            raise CallError("BRIDGE_EXECUTION_FAILED", "connection closed while awaiting the nested call's reply")
        if "error" in reply:
            error = reply["error"]
            raise CallError(error.get("code", "BRIDGE_EXECUTION_FAILED"), error.get("message", ""))
        return reply.get("output", {})

    def reply_output(self, output: dict[str, Any]) -> None:
        self._write({"output": output})

    def reply_error(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        error: dict[str, Any] = {"code": code, "message": message}
        if details is not None:
            error["details"] = details
        self._write({"error": error})

    def serve(self, handler: Callable[["Connection", str, dict[str, Any]], None]) -> None:
        """Runs forever, reading one invocation per line and calling
        `handler(connection, operation, input)`. The handler must call
        exactly one of `reply_output`/`reply_error` before returning.
        Returns when the Bridge closes the connection.
        """

        while True:
            message = self._read()
            if message is None:
                return
            handler(self, message.get("operation", ""), message.get("input", {}))


class _Response:
    """The real BoundCapability.call (bridge/bridge.py) returns a
    BridgeResponse with an `.output` attribute -- matched here in case a
    factory closure ever inspects it (none of this sample's do)."""

    def __init__(self, output: dict[str, Any]) -> None:
        self.output = output


class BoundCapability:
    """Returned by `Dependencies.resolve(...)` -- mirrors
    bridge/bridge.py's real `BoundCapability.call(...)` shape closely
    enough that an unmodified factory closure can't tell the difference:
    delegates to a nested call over the wire (`Connection.call`).
    """

    def __init__(self, conn: Connection, capability_id: str, operation: str) -> None:
        self._conn = conn
        self._capability_id = capability_id
        self._operation = operation

    def call(self, input: dict[str, Any], policy_context: Any = None) -> _Response:
        # policy_context is accepted for signature compatibility with the
        # in-process shape and discarded: the nested-call wire message
        # never carried it explicitly either (schemas/process-executor-
        # protocol.schema.json's callRequest has no policy field) -- the
        # Bridge already threads policy through implicitly, from the
        # outer invocation.
        return _Response(self._conn.call(self._capability_id, self._operation, input))


class Dependencies:
    """Mirrors bridge/bridge.py's real `Dependencies` closely enough
    that an unmodified `make_executor(dependencies)` factory runs
    unchanged, whether it's actually in-process or (here) out-of-process.
    R4 enforcement (only a declared capability_id may be resolved) is
    NOT duplicated here -- the nested call still lands on the real
    Bridge's own `Dependencies`, which already enforces it; this is a
    transport shim, not a second enforcement point.
    """

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def resolve(self, capability_id: str, operation: str) -> BoundCapability:
        return BoundCapability(self._conn, capability_id, operation)


def _served_handler(execute: Callable[[str, dict[str, Any], Any], dict[str, Any]]) -> Callable[[Connection, str, dict[str, Any]], None]:
    def handler(conn: Connection, operation: str, input: dict[str, Any]) -> None:
        try:
            output = execute(operation, input, None)
            conn.reply_output(output)
        except Exception as exc:
            conn.reply_error("BRIDGE_EXECUTION_FAILED", str(exc))

    return handler


def serve_direct(execute: Callable[[str, dict[str, Any], Any], dict[str, Any]]) -> None:
    """Serves a pure `execute(operation, input, policy) -> output`
    function over the process executor wire protocol -- the
    `executor_kind: process` equivalent of `direct`'s native shape
    (2-RULES.md R4), so a leaf capability's code is identical either
    way. No real `PolicyContext` is available here (`policy` is always
    `None`) -- the same limitation `Connection.serve` already has,
    since the wire protocol never forwards it to a handler either.
    """

    Connection().serve(_served_handler(execute))


def serve_factory(make_executor: Callable[[Dependencies], Callable[[str, dict[str, Any], Any], dict[str, Any]]]) -> None:
    """Serves a `make_executor(dependencies) -> execute(operation, input,
    policy)` factory over the process executor wire protocol -- the
    `executor_kind: process` equivalent of `factory`'s native shape
    (2-RULES.md R4), so a capability that needs to call another
    capability has identical code either way.
    `dependencies.resolve(capability_id, operation).call(input)` makes a
    real nested call, resolved through this process's own declared
    dependencies.
    """

    conn = Connection()
    execute = make_executor(Dependencies(conn))
    conn.serve(_served_handler(execute))
