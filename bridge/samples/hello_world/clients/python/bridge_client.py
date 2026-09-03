"""Reference client for the process executor protocol
(schemas/process-executor-protocol.schema.json) -- what a process-kind
executor (2-RULES.md R4/R5) exchanges with the Bridge. A Python
capability running as its own separate process uses this instead of
hand-writing connect/frame/dispatch -- the same role clients/rust/
plays for Rust, proving the protocol isn't a non-Python escape hatch
(see ../../capabilities/console/write_process/executor.py).

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
