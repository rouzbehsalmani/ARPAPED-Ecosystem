"""Real (not mocked) proof that process_executor.py's Evidence capture
(2-RULES.md glossary) works: spawns the ACTUAL console.write.process
worker (sample/hello_world/backend/runtime/capabilities/console/write_process/executor.py)
through a real ProcessExecutorPool, over the real loopback-TCP wire
protocol, and asserts what comes back through `last_call_evidence()`
matches what that worker genuinely did -- its own real stdout, its
real response.output, and a real OS exit code captured once the pool
shuts it down.

Run from the repository root:
    python -m unittest sample.hello_world.backend.implementation.tests.verify.test_process_executor_evidence -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(_REPO_ROOT))

from sample.hello_world.backend.runtime.bridge.bridge import Bridge  # noqa: E402
from sample.hello_world.backend.runtime.bridge.policy import PolicyContext, StaticPolicyEngine  # noqa: E402
from sample.hello_world.backend.runtime.bridge.process_executor import ProcessExecutorPool  # noqa: E402
from sample.hello_world.backend.runtime.bridge.registry import CapabilityRegistry  # noqa: E402
from sample.hello_world.backend.runtime.bridge.selector import DeterministicSelector  # noqa: E402

_WORKER_SCRIPT = _REPO_ROOT / "sample/hello_world/backend/runtime/capabilities/console/write_process/executor.py"

_EMPTY_POLICY = PolicyContext(user={}, consumer={}, ecosystem={}, provider={}, module={})


class ProcessExecutorEvidenceTests(unittest.TestCase):
    def setUp(self):
        # A throwaway Bridge, unrelated to the real one requests.py builds --
        # this pool only needs `bridge` to construct its (here, empty)
        # Dependencies; nothing in this test resolves through it.
        bridge = Bridge(CapabilityRegistry(), StaticPolicyEngine(), DeterministicSelector())
        self.pool = ProcessExecutorPool(
            [sys.executable, str(_WORKER_SCRIPT)], bridge=bridge, declared={}, pool_size=1,
        )

    def tearDown(self):
        self.pool._shutdown()  # noqa: SLF001 -- exercising real shutdown for the exit-code assertion below

    def test_evidence_captures_real_stdout_and_output(self):
        output = self.pool("write", {"message": "evidence capture works", "format": "plain"}, _EMPTY_POLICY)
        self.assertEqual(output, {})

        evidence = self.pool.last_call_evidence()
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence["executor_kind"], "process")
        self.assertEqual(evidence["response_output"], {})
        self.assertIn("evidence capture works", evidence["stdout"])
        self.assertEqual(evidence["stderr"], "")
        self.assertTrue(evidence["worker_alive"])
        self.assertIsNone(evidence["process_exit_code"])  # still running immediately after a normal call

    def test_evidence_is_per_call_not_cumulative(self):
        self.pool("write", {"message": "first call", "format": "plain"}, _EMPTY_POLICY)
        first_stdout = self.pool.last_call_evidence()["stdout"]
        self.assertIn("first call", first_stdout)

        self.pool("write", {"message": "second call", "format": "plain"}, _EMPTY_POLICY)
        second_stdout = self.pool.last_call_evidence()["stdout"]
        self.assertIn("second call", second_stdout)
        self.assertNotIn("first call", second_stdout)

    def test_uppercase_format_reflected_in_stdout(self):
        self.pool("write", {"message": "shout this", "format": "uppercase"}, _EMPTY_POLICY)
        evidence = self.pool.last_call_evidence()
        self.assertIn("SHOUT THIS", evidence["stdout"])

    def test_shutdown_captures_real_exit_code(self):
        self.pool("write", {"message": "before shutdown", "format": "plain"}, _EMPTY_POLICY)
        self.pool._shutdown()  # noqa: SLF001 -- idempotent (empty queue on the second, tearDown's, call)
        codes = self.pool.shutdown_exit_codes()
        self.assertEqual(len(codes), 1)
        # terminate() on Windows maps to a non-zero exit; on POSIX, SIGTERM
        # also yields a non-None code once wait() completes -- either way,
        # a REAL captured code, not the live-call None seen mid-session.
        self.assertIsNotNone(codes[0])


if __name__ == "__main__":
    unittest.main()
