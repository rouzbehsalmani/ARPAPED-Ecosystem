"""Out-of-process executor over loopback TCP, for a capability
implemented in a language other than the Bridge's own. Implements the
Bridge side of `sample/schemas/process-executor-protocol.schema.json`; a
language's own reference client implements the other side.

`ProcessExecutorPool` matches the executor contract exactly --
`__call__(operation, input, policy) -> output` -- so `bridge.handle`
never knows or cares whether an executor is in-process or not.

Wire shape: one newline-delimited JSON object per message. Bridge ->
process: `{"operation", "input", "policy"}`. Process -> Bridge: either
the terminal `{"output"}`/`{"error"}`, or, first, any number of
`{"call": {capability_id, operation, input}}` nested-call requests, each
awaited before the process continues -- safe to reuse the same
`{"output"}`/`{"error"}` shape since a worker connection is exclusively
borrowed for one invocation's whole duration. A nested call resolves
through a `Dependencies` scoped to this implementation's own declared
dependencies (R4), the same enforcement a factory executor gets.

`pool_size` workers are spawned once, at assembly time, concurrently
(not serially -- each spawn is mostly idle wait, and each binds its own
port). A worker that doesn't connect within `startup_timeout` fails
assembly loudly (blueprint/2-RULES.md R5, gate 6).

Loopback TCP, not a Unix domain socket: `socket.AF_UNIX` isn't
available on every platform this reference Bridge runs on.
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
import threading
from pathlib import Path
from typing import Any, Optional, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from .bridge import Bridge


class ProcessExecutorError(Exception):
    """Raised when a worker process cannot be started or never connects."""


class _StreamCapture:
    """Continuously drains a subprocess pipe (a worker's own stdout or
    stderr, entirely separate from the loopback-TCP wire protocol) into a
    growing, lock-protected buffer, from one background daemon thread --
    required because a pipe must be actively read to be capturable at all
    (an unread pipe just blocks the child once its OS buffer fills), and
    because Windows pipes don't support select()/poll() the way a socket
    does, so "drain whatever's available, non-blocking" isn't an option
    here the way it is for the worker's own TCP connection.

    `read_since(offset)` (an `offset()` snapshot taken earlier) returns
    everything captured from that point to now -- how `__call__` isolates
    exactly what THIS invocation's worker wrote during its own span,
    never everything captured since the worker was first spawned.
    """

    def __init__(self, pipe: Any) -> None:
        self._buffer = bytearray()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._drain, args=(pipe,), daemon=True)
        self._thread.start()

    def _drain(self, pipe: Any) -> None:
        # os.read(), not pipe.read(): a BufferedReader's own .read(size)
        # blocks trying to accumulate the FULL requested size before
        # returning (a pipe isn't "interactive" in the sense that
        # exempts a real terminal from this) -- for a short message that
        # never fills the buffer, that means blocking forever waiting for
        # more bytes that are never coming, even though the ones already
        # written are sitting right there. The raw os.read() syscall
        # returns as soon as ANY data is available, which is what
        # "continuously drain whatever's been written so far" actually
        # requires.
        fd = pipe.fileno()
        try:
            while True:
                chunk = os.read(fd, 4096)
                if not chunk:
                    return
                with self._lock:
                    self._buffer.extend(chunk)
        except OSError:
            return

    def offset(self) -> int:
        with self._lock:
            return len(self._buffer)

    def read_since(self, offset: int) -> str:
        with self._lock:
            return bytes(self._buffer[offset:]).decode("utf-8", errors="replace")


@dataclasses.dataclass
class _Worker:
    process: "subprocess.Popen[bytes]"
    connection: socket.socket
    stream: Any
    stdout_capture: _StreamCapture
    stderr_capture: _StreamCapture


def _terminate(worker: _Worker) -> None:
    try:
        worker.connection.close()
    except OSError:
        pass
    try:
        worker.process.terminate()
    except OSError:
        pass
    # Closing these unblocks each _StreamCapture drain thread's os.read()
    # with a clean EOF (or an OSError on an already-broken pipe, caught the
    # same way) instead of leaving it parked on a dead pipe indefinitely,
    # and avoids leaking the OS-level file handles themselves.
    for pipe in (worker.process.stdout, worker.process.stderr):
        try:
            pipe.close()
        except OSError:
            pass


class ProcessExecutorPool:
    """Spawns `pool_size` copies of `command`, each reached over its own
    loopback TCP connection; see the module docstring for the wire shape
    and why this exists.

    `command` is either a single command string (e.g. a compiled binary)
    or an argv list, for when an interpreter and a script are both needed
    (e.g. `["<interpreter>", "path/to/executor"]`, an interpreted
    language's case) -- `sample/schemas/capability-manifest.schema.json` allows
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
        from .bridge import Dependencies  # deferred: see sample/hello_world/backend/runtime/bridge/assembler.py's own Dependencies import

        self._dependencies = Dependencies(bridge, dict(declared))
        self._workers: "queue.Queue[_Worker]" = queue.Queue()
        # Evidence (2-RULES.md glossary) for the call this thread most
        # recently completed through this pool -- thread-local because one
        # thread runs one __call__ to completion (including the `finally:
        # self._workers.put(worker)` below) before its own next line
        # executes, even under Bridge.handle_with_timeout's background
        # thread, so there is never a genuine cross-thread race to guard
        # against here.
        self._evidence_local = threading.local()
        self._shutdown_exit_codes: list[Optional[int]] = []
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
            # stdout/stderr piped (never inherited, as before) so a
            # worker's own prints -- entirely outside the wire protocol on
            # the loopback socket above -- become real, capturable Evidence
            # (2-RULES.md glossary) instead of being silently discarded.
            # Genuinely empty for an implementation whose responsibility
            # never prints (e.g. greeting.compose.process, which only
            # makes a nested Bridge call) and genuinely non-empty for one
            # whose responsibility IS to print (e.g. console.write.process)
            # -- this pool never assumes either.
            process = subprocess.Popen(self._argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
        return _Worker(
            process=process, connection=connection, stream=stream,
            stdout_capture=_StreamCapture(process.stdout),
            stderr_capture=_StreamCapture(process.stderr),
        )

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
        # Snapshot BEFORE sending -- everything captured from here to the
        # terminal "output" message below is this invocation's own span,
        # never anything a PRIOR call already consumed from the same
        # worker (a pool worker is reused across many calls).
        stdout_offset = worker.stdout_capture.offset()
        stderr_offset = worker.stderr_capture.offset()
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
                    # Evidence (2-RULES.md glossary), captured for THIS
                    # invocation's own span only (the offsets snapshotted
                    # above), stashed for bridge.py to pick up via
                    # last_call_evidence() right after this call returns --
                    # never returned as part of the executor contract
                    # itself (output stays exactly {"output": ...} shaped,
                    # unaffected by any of this).
                    self._evidence_local.value = {
                        "executor_kind": "process",
                        "response_output": message["output"],
                        "stdout": worker.stdout_capture.read_since(stdout_offset),
                        "stderr": worker.stderr_capture.read_since(stderr_offset),
                        "worker_alive": worker.connection.fileno() != -1,
                        "process_exit_code": worker.process.poll(),
                    }
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

    def last_call_evidence(self) -> Optional[dict[str, Any]]:
        """Evidence (2-RULES.md glossary) for the most recent call this
        thread completed through this pool -- the duck-typed hook
        `bridge.py`'s `Bridge.handle` looks for via
        `getattr(selected.executor, "last_call_evidence", None)` right
        after execution, the same way it already checks for
        `record_failure`/`record_success` on the selector. None before any
        call has completed on this thread."""
        return getattr(self._evidence_local, "value", None)

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
            # The one genuine, once-only real OS exit code this pool ever
            # produces -- a pool-lifetime fact, deliberately not part of
            # the per-call evidence schema (checks[].evidence.process_exit_code
            # is a live poll() snapshot; a pooled worker outlives any single
            # call, so no single request can honestly claim "the" exit code).
            try:
                code = worker.process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                code = None
            self._shutdown_exit_codes.append(code)

    def shutdown_exit_codes(self) -> list[Optional[int]]:
        """The real OS exit code (or None if it didn't exit within the
        grace period) captured for each worker this pool has shut down so
        far -- a diagnostic, not part of any per-call contract."""
        return list(self._shutdown_exit_codes)
