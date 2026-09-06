"""Generic supervision for a background process an agent starts and must
reliably stop later -- e.g. a dev/test server started during Phase 7
Verify (0-WALKTHROUGH.md section 6: "a server, a long-lived process").

The problem this exists to prevent, found empirically: a background
process started with a fire-and-forget launcher (a detached shell
command, PowerShell's `Start-Process -PassThru`, a bare `subprocess.Popen`
with no corresponding stop step) keeps running after the command that
started it ends -- invisible to whatever started it, still holding its
port, possibly in a stale state from several restarts ago. The next
"restart and test" then talks to whichever orphaned process happens to
still be listening, not the one just started -- confusing, non-
reproducible failures that have nothing to do with the code under test.

Not a capability: like a sample's own catalog-building tooling and
episode_store (blueprint/dep/MANIFEST.yaml), this
is tooling for the cycle itself (Phase 7's own reliability), not domain
logic reached through the Bridge.

Usage, symmetric start/stop, `pidfile` the only state carried between
them -- no in-memory handle required, so `stop` works from a completely
separate process/script/session, which is exactly the case that was
failing:
    supervisor.start(<argv to launch the process under test, any
                       language>, pidfile,
                      ready_check=lambda: _can_connect(8080))
    ...
    supervisor.stop(pidfile)

Existence-checking and termination are platform-branched, not assumed:
`os.kill(pid, 0)`/`os.kill(pid, SIGTERM)` are the standard POSIX
mechanism, but were verified empirically to be unreliable on Windows
here (a real `taskkill` that genuinely terminated a process was still
reported alive by `os.kill(pid, 0)` afterward) -- Windows uses
`tasklist`/`taskkill` instead, the tools actually proven to work.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional

_WINDOWS = os.name == "nt"


class ProcessSupervisorError(Exception):
    """Raised when a process fails to start, or its ready_check never
    passes within ready_timeout."""


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if _WINDOWS:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True,
        )
        return str(pid) in result.stdout
    import signal
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _terminate(pid: int) -> None:
    if _WINDOWS:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True)
        return
    import signal
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return


def start(
    argv: list[str],
    pidfile: Path,
    ready_check: Optional[Callable[[], bool]] = None,
    ready_timeout: float = 10.0,
    poll_interval: float = 0.1,
) -> subprocess.Popen:
    """Starts `argv` as a background process, writes its PID to
    `pidfile`, and -- if `ready_check` is given -- polls it until it
    returns True, never for longer than `ready_timeout`. Refuses to
    start if `pidfile` already names a live process (stop it first,
    never silently replace it -- that's exactly how orphans accumulate).
    Raises ProcessSupervisorError rather than ever returning a "started"
    claim it didn't actually observe (R5: "verify, synchronously and
    promptly, that the work has actually started before returning").
    """

    if pidfile.exists():
        existing = pidfile.read_text(encoding="utf-8").strip()
        existing_pid = int(existing) if existing else 0
        if _pid_is_alive(existing_pid):
            raise ProcessSupervisorError(
                f"pidfile {pidfile} already names a live process ({existing_pid}) -- stop it first"
            )
        pidfile.unlink()

    process = subprocess.Popen(argv)
    pidfile.parent.mkdir(parents=True, exist_ok=True)
    pidfile.write_text(str(process.pid), encoding="utf-8")

    if ready_check is not None:
        deadline = time.monotonic() + ready_timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pidfile.unlink(missing_ok=True)
                raise ProcessSupervisorError(
                    f"{argv} exited (code {process.returncode}) before becoming ready"
                )
            if ready_check():
                return process
            time.sleep(poll_interval)
        stop(pidfile)
        raise ProcessSupervisorError(f"{argv} did not become ready within {ready_timeout}s")

    return process


def stop(pidfile: Path) -> bool:
    """Reads `pidfile`, terminates that PID, and removes the file.
    Idempotent: a missing pidfile or an already-dead PID is a clean
    no-op (returns False), never an error -- "nothing to stop" is not a
    failure. Returns True only if a live process was actually stopped.
    """

    if not pidfile.exists():
        return False
    text = pidfile.read_text(encoding="utf-8").strip()
    pidfile.unlink()
    pid = int(text) if text else 0
    if not _pid_is_alive(pid):
        return False
    _terminate(pid)
    for _ in range(50):  # up to ~5s grace period
        if not _pid_is_alive(pid):
            return True
        time.sleep(0.1)
    return not _pid_is_alive(pid)
