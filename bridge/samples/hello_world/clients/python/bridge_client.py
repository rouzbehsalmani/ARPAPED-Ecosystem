"""Reference client for the process executor protocol
(schemas/process-executor-protocol.schema.json) -- the wire shape a
process-kind executor (executor_kind: process, 2-RULES.md R4/R5)
exchanges with the resolved Bridge. Any Python capability that runs as
its own separate process (instead of in-process, as a direct or factory
executor) uses this instead of hand-writing the connect/frame/dispatch
logic itself -- the same role clients/rust/ plays for a Rust capability.

Proves the protocol is genuinely language-neutral, not just "the
non-Python escape hatch": a Python capability doesn't have to run
in-process just because the Bridge happens to be Python too. It reaches
the Bridge exactly the way any other language does, over this same
protocol -- see bridge/samples/hello_world/capabilities/console/write_process/executor.py.

Lives inside this sample, not under bridge/: it's not part of the Bridge
implementation (bridge/ is that, and only that -- see bridge/MANIFEST.yaml)
either way, but it's also not shared, ecosystem-level infrastructure --
every consumer of it is a capability inside this one sample. A real
application copies the shape of this client into its own structure, the
same way it copies the shape of a contract or a capability, rather than
depending on hello_world's copy.

This does real JSON parsing via the standard library, needing no
external dependency to do it -- clients/rust/ also does real parsing now
(serde_json), a real dependency it depends on directly (Cargo, not bare
rustc); the difference here is Python's own stdlib already includes one.
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
