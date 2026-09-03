"""Out-of-process executor over loopback TCP, for a capability implemented
in a language other than the resolved Bridge's own (bridge/MANIFEST.yaml).

A `ProcessExecutorPool` matches the executor contract exactly --
`__call__(operation, input, policy) -> output` -- so it plugs into
`CapabilityImplementation.executor` (registry.py) unchanged; `bridge.handle`
never knows or cares whether the executor it calls is in-process or not.

Wire shape mirrors the same three inputs and one output/error every
executor already has, framed as one newline-delimited JSON object per
message: `{"operation", "input", "policy"}` out, `{"output": ...}` or
`{"error": {"code", "message", "details"}}` back. The external process
never sees `request_id`, `capability_id`, `contract_version`, or the trace
-- those stay the Bridge's job, exactly as for a direct Python executor.

A handful of worker processes are spawned once, at assembly time (see
`bridge/assembler.py`), each with its own connection; `__call__` borrows
one per invocation instead of serializing every call onto a single shared
connection. A worker that never connects within `startup_timeout` fails
assembly loudly (`ProcessExecutorError`, wrapped by the assembler into
`AssemblerError`) rather than registering a capability that was never
actually verified to have started (2-RULES.md R5, gate 6).

Loopback TCP, not a Unix domain socket: `socket.AF_UNIX` is not available
on every platform this reference Bridge runs on.
"""

from __future__ import annotations

import atexit
import dataclasses
import json
import os
import queue
import socket
import subprocess
from pathlib import Path
from typing import Any


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
    """

    def __init__(self, command: str, *, pool_size: int = 2, startup_timeout: float = 10.0) -> None:
        # A manifest's executor: is written with forward slashes, same
        # convention as a contract: path -- normalized to the native
        # separator here since, unlike Path.open, CreateProcess on Windows
        # does not resolve a forward-slash relative path as the program.
        self._command = str(Path(command))
        self._workers: "queue.Queue[_Worker]" = queue.Queue()
        spawned: list[_Worker] = []
        try:
            for _ in range(pool_size):
                worker = self._spawn_worker(startup_timeout)
                spawned.append(worker)
                self._workers.put(worker)
        except Exception:
            for worker in spawned:
                _terminate(worker)
            raise
        atexit.register(self._shutdown)

    def _spawn_worker(self, startup_timeout: float) -> _Worker:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        env = dict(os.environ)
        env["ARPAPED_BRIDGE_PORT"] = str(port)
        try:
            process = subprocess.Popen([self._command], env=env)
        except OSError as exc:
            server.close()
            raise ProcessExecutorError(f"cannot start process executor {self._command!r}: {exc}") from exc
        server.settimeout(startup_timeout)
        try:
            connection, _ = server.accept()
        except socket.timeout:
            process.kill()
            raise ProcessExecutorError(
                f"process executor {self._command!r} did not connect within {startup_timeout}s"
            ) from None
        finally:
            server.close()
        connection.settimeout(None)
        stream = connection.makefile("rw", encoding="utf-8", newline="\n")
        return _Worker(process=process, connection=connection, stream=stream)

    def __call__(self, operation: str, input: dict[str, Any], policy: Any) -> dict[str, Any]:
        from .bridge import BridgeError  # deferred: mirrors assembler.py's Dependencies import

        worker = self._workers.get()
        try:
            request = {"operation": operation, "input": input, "policy": dataclasses.asdict(policy)}
            worker.stream.write(json.dumps(request))
            worker.stream.write("\n")
            worker.stream.flush()
            line = worker.stream.readline()
            if not line:
                raise BridgeError(
                    "BRIDGE_EXECUTION_FAILED", "execution",
                    f"process executor {self._command!r} closed its connection",
                    {"cause_type": "ConnectionClosed"},
                )
            reply = json.loads(line)
        except BridgeError:
            raise
        except (OSError, ValueError) as exc:
            raise BridgeError(
                "BRIDGE_EXECUTION_FAILED", "execution",
                f"process executor {self._command!r} transport failure: {exc}",
                {"cause_type": type(exc).__name__},
            ) from exc
        finally:
            self._workers.put(worker)

        if "error" in reply:
            error = reply["error"]
            raise BridgeError(
                error.get("code", "BRIDGE_EXECUTION_FAILED"), "execution",
                error.get("message", ""), error.get("details"),
            )
        return reply.get("output", {})

    def _shutdown(self) -> None:
        while not self._workers.empty():
            try:
                worker = self._workers.get_nowait()
            except queue.Empty:
                break
            _terminate(worker)
