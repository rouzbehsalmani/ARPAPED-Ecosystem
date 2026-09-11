"""Coverage for process_supervisor.py: real start/stop round trips (no
mocked subprocesses -- a real `python -c ...` process every time), and
the specific regression this session found for real: a `ready_check`
that already passes before `start()` spawns anything (an untracked
orphan already occupying whatever it watches) must refuse loudly,
never report a false "ready" against the wrong process.

Run from the repository root:
    python -m unittest blueprint.dep.tests.test_process_supervisor -v
"""

from __future__ import annotations

import socket
import sys
import tempfile
import time
import unittest
from pathlib import Path

from blueprint.dep import process_supervisor


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ProcessSupervisorTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pidfile = Path(self._tmp.name) / "state" / "proc.pid"

    def tearDown(self):
        process_supervisor.stop(self.pidfile)  # best-effort cleanup
        self._tmp.cleanup()

    def test_start_without_ready_check_then_stop(self):
        process = process_supervisor.start(
            [sys.executable, "-c", "import time; time.sleep(30)"], self.pidfile,
        )
        self.assertTrue(self.pidfile.exists())
        self.assertEqual(int(self.pidfile.read_text(encoding="utf-8")), process.pid)
        self.assertTrue(process_supervisor.stop(self.pidfile))
        self.assertFalse(self.pidfile.exists())

    def test_start_with_real_tcp_ready_check(self):
        port = _free_port()
        process = process_supervisor.start(
            [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
            self.pidfile,
            ready_check=process_supervisor.tcp_ready_check("127.0.0.1", port),
        )
        with socket.create_connection(("127.0.0.1", port), timeout=1.0):
            pass  # genuinely connects -- start() really did wait for readiness
        self.assertTrue(process_supervisor.stop(self.pidfile))
        time.sleep(0.3)
        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=0.5)

    def test_start_refuses_when_pidfile_names_live_process(self):
        process_supervisor.start([sys.executable, "-c", "import time; time.sleep(30)"], self.pidfile)
        with self.assertRaises(process_supervisor.ProcessSupervisorError):
            process_supervisor.start([sys.executable, "-c", "import time; time.sleep(30)"], self.pidfile)

    def test_start_refuses_when_ready_check_already_passes(self):
        # The regression this session found for real: something NOT
        # tracked by this pidfile (a bare socket here, standing in for
        # an untracked orphan) already occupies the port before start()
        # is even called.
        port = _free_port()
        occupier = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        occupier.bind(("127.0.0.1", port))
        occupier.listen(1)
        try:
            with self.assertRaises(process_supervisor.ProcessSupervisorError) as ctx:
                process_supervisor.start(
                    [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
                    self.pidfile,
                    ready_check=process_supervisor.tcp_ready_check("127.0.0.1", port),
                )
            self.assertIn("already passes before starting", str(ctx.exception))
            # Refused BEFORE spawning anything -- no pidfile written, no
            # orphan left behind by this failed attempt.
            self.assertFalse(self.pidfile.exists())
        finally:
            occupier.close()

    def test_stop_is_idempotent_on_missing_pidfile(self):
        self.assertFalse(process_supervisor.stop(self.pidfile))

    def test_start_raises_if_process_exits_before_ready(self):
        with self.assertRaises(process_supervisor.ProcessSupervisorError):
            process_supervisor.start(
                [sys.executable, "-c", "import sys; sys.exit(1)"],
                self.pidfile,
                ready_check=lambda: False,
                ready_timeout=2.0,
                poll_interval=0.05,
            )


if __name__ == "__main__":
    unittest.main()
