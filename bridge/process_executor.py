"""Out-of-process executor over loopback TCP, for a capability implemented
in a language other than the resolved Bridge's own (bridge/MANIFEST.yaml).
This module is the Bridge-side implementation of the process executor
protocol formally defined in `schemas/process-executor-protocol.schema.json`
-- a language's own reference client (resolved from `bridge/MANIFEST.yaml`'s
`clients:`) implements the other side of the same protocol.

A `ProcessExecutorPool` matches the executor contract exactly --
`__call__(operation, input, policy) -> output` -- so it plugs into
`CapabilityImplementation.executor` (registry.py) unchanged; `bridge.handle`
never knows or cares whether the executor it calls is in-process or not.

Wire shape mirrors the same three inputs and one output/error every
executor already has, framed as one newline-delimited JSON object per
message. Bridge -> process starts one invocation: `{"operation", "input",
"policy"}`. Process -> Bridge, while handling it, may be the terminal
reply (`{"output": ...}` or `{"error": {"code", "message", "details"}}`)
-- or, first, any number of nested call requests, `{"call": {"capability_id",
"operation", "input"}}`, each one sent and then immediately awaited before
the process continues. A worker connection is exclusively borrowed for the
whole duration of one invocation (see `ProcessExecutorPool`), so the
Bridge never sends anything else on it while a nested call is outstanding
-- the reply to a nested call can never be confused with a fresh
invocation, and reuses the exact same `{"output"}`/`{"error"}` shape the
terminal reply uses; no separate message-type tag is needed. The external
process never sees `request_id`, `capability_id` (its own),
`contract_version`, or the trace -- those stay the Bridge's job, exactly
as for a direct in-process executor.

A nested call is resolved through a `Dependencies` (bridge/bridge.py)
scoped to this implementation's own declared `dependencies.capabilities`
(R4) -- the identical mechanism and enforcement an `executor_kind: factory`
executor already gets, just reached over the wire instead of a direct
in-process call. This is what lets a capability implemented in another
language compose other capabilities instead of being stuck as a leaf.

A handful of worker processes are spawned once, at assembly time (see
`bridge/assembler.py`), each with its own connection; `__call__` borrows
one per invocation instead of serializing every call onto a single shared
connection. A worker that never connects within `startup_timeout` fails
assembly loudly (`ProcessExecutorError`, wrapped by the assembler into
`AssemblerError`) rather than registering a capability that was never
actually verified to have started (2-RULES.md R5, gate 6).

`pool_size` workers are spawned concurrently, not one at a time -- each
spawn is mostly idle wait (process launch, then a blocking socket
accept), and each binds its own ephemeral port, so nothing about one
spawn depends on another finishing first. With an interpreted language's
real startup cost (an interpreter, not just a compiled binary), spawning
serially would multiply that cost by `pool_size` for every single
process-kind implementation an ecosystem assembles at once; concurrent
spawning keeps one pool's startup cost close to its single slowest
worker instead.

Loopback TCP, not a Unix domain socket: `socket.AF_UNIX` is not available
on every platform this reference Bridge runs on.
"""

from __future__ import annotations

import atexit
import concurrent.futures
import dataclasses
import json
import os
import queue
import socket
import subprocess
from pathlib import Path
from typing import Any, Optional, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from .bridge import Bridge


class ProcessExecutorError(Exception):
    """Raised when a worker process cannot be started or never connects."""


@dataclasses.dataclass
class _Worker:
    process: "subprocess.Popen[bytes]"
    connection: socket.socket
    stream: Any


def _terminate(worker: _Worker) -> None:
    try:
        worker.connection.close()
    except OSError:
        pass
    try:
        worker.process.terminate()
    except OSError:
        pass


class ProcessExecutorPool:
    """Spawns `pool_size` copies of `command`, each reached over its own
    loopback TCP connection; see the module docstring for the wire shape
    and why this exists.

    `command` is either a single command string (e.g. a compiled binary)
    or an argv list, for when an interpreter and a script are both needed
    (e.g. `["<interpreter>", "path/to/executor"]`, an interpreted
    language's case) -- `schemas/capability-manifest.schema.json` allows
    either shape for `executor:` under `executor_kind: process`.

    `declared` is this implementation's contract's `dependencies.capabilities`
    (R4), decoded to `{capability_id: contract_version}` -- the same shape
    `Dependencies` always takes. Required together with `bridge`, even when
    empty: mirrors `executor_kind: factory`'s existing requirement, so a
    nested call attempt fails loudly and consistently rather than being
    silently possible for some process-kind implementations and not others.
    """

    def __init__(
        self, command: str | Sequence[str], *, bridge: "Bridge", declared: dict[str, str],
        pool_size: int = 2, startup_timeout: float = 10.0,
    ) -> None:
        # A manifest's executor: is written with forward slashes, same
        # convention as a contract: path -- normalized to the native
        # separator here since, unlike Path.open, CreateProcess on Windows
        # does not resolve a forward-slash relative path as the program.
        # Every argv part gets this treatment (harmless for a bare
        # interpreter name, which has no slashes to fix).
        parts = [command] if isinstance(command, str) else list(command)
        self._argv = [str(Path(part)) for part in parts]
        from .bridge import Dependencies  # deferred: see bridge/assembler.py's own Dependencies import

        self._dependencies = Dependencies(bridge, dict(declared))
        self._workers: "queue.Queue[_Worker]" = queue.Queue()
        spawned: list[_Worker] = []
        errors: list[Exception] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=pool_size) as pool:
            futures = [pool.submit(self._spawn_worker, startup_timeout) for _ in range(pool_size)]
            for future in futures:
                try:
                    spawned.append(future.result())
                except Exception as exc:
                    errors.append(exc)
        if errors:
            for worker in spawned:
                _terminate(worker)
            raise errors[0]
        for worker in spawned:
            self._workers.put(worker)
        atexit.register(self._shutdown)

    def _spawn_worker(self, startup_timeout: float) -> _Worker:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        env = dict(os.environ)
        env["ARPAPED_BRIDGE_PORT"] = str(port)
        try:
            process = subprocess.Popen(self._argv, env=env)
        except OSError as exc:
            server.close()
            raise ProcessExecutorError(f"cannot start process executor {self._argv!r}: {exc}") from exc
        server.settimeout(startup_timeout)
        try:
            connection, _ = server.accept()
        except socket.timeout:
            process.kill()
            raise ProcessExecutorError(
                f"process executor {self._argv!r} did not connect within {startup_timeout}s"
            ) from None
        finally:
            server.close()
        connection.settimeout(None)
        stream = connection.makefile("rw", encoding="utf-8", newline="\n")
        return _Worker(process=process, connection=connection, stream=stream)

    @staticmethod
    def _send(worker: _Worker, message: dict[str, Any]) -> None:
        worker.stream.write(json.dumps(message))
        worker.stream.write("\n")
        worker.stream.flush()

    @staticmethod
    def _recv(worker: _Worker) -> Optional[dict[str, Any]]:
        line = worker.stream.readline()
        if not line:
            return None
        return json.loads(line)

    def __call__(self, operation: str, input: dict[str, Any], policy: Any) -> dict[str, Any]:
        from .bridge import BridgeError  # deferred: mirrors assembler.py's Dependencies import

        worker = self._workers.get()
        try:
            self._send(worker, {"operation": operation, "input": input, "policy": dataclasses.asdict(policy)})
            while True:
                message = self._recv(worker)
                if message is None:
                    raise BridgeError(
                        "BRIDGE_EXECUTION_FAILED", "execution",
                        f"process executor {self._argv!r} closed its connection",
                        {"cause_type": "ConnectionClosed"},
                    )
                if "call" in message:
                    self._handle_nested_call(worker, message["call"], policy)
                    continue
                if "error" in message:
                    error = message["error"]
                    raise BridgeError(
                        error.get("code", "BRIDGE_EXECUTION_FAILED"), "execution",
                        error.get("message", ""), error.get("details"),
                    )
                if "output" in message:
                    return message["output"]
                raise BridgeError(
                    "BRIDGE_EXECUTION_FAILED", "execution",
                    f"process executor {self._argv!r} sent an unrecognized message {message!r}",
                    {"cause_type": "ProtocolError"},
                )
        except BridgeError:
            raise
        except (OSError, ValueError) as exc:
            raise BridgeError(
                "BRIDGE_EXECUTION_FAILED", "execution",
                f"process executor {self._argv!r} transport failure: {exc}",
                {"cause_type": type(exc).__name__},
            ) from exc
        finally:
            self._workers.put(worker)

    def _handle_nested_call(self, worker: _Worker, call: dict[str, Any], policy: Any) -> None:
        """Resolves one nested call request through this implementation's
        own declared `Dependencies` (R4) and sends back its outcome, in
        the same `{"output"}`/`{"error"}` shape a terminal reply uses --
        the process is synchronously awaiting exactly this one reply
        before it continues, so no separate message-type tag is needed.
        """

        from .bridge import BridgeError

        try:
            bound = self._dependencies.resolve(call.get("capability_id"), call.get("operation"))
            response = bound.call(call.get("input", {}), policy_context=policy)
            self._send(worker, {"output": response.output})
        except BridgeError as exc:
            self._send(worker, {"error": {"code": exc.code, "message": exc.message, "details": exc.details}})

    def _shutdown(self) -> None:
        while not self._workers.empty():
            try:
                worker = self._workers.get_nowait()
            except queue.Empty:
                break
            _terminate(worker)
