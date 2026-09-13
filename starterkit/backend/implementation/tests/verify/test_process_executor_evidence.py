"""Real (not mocked) proof that process_executor.py's Evidence capture
(2-RULES.md glossary) works: spawns the ACTUAL log.write.process
worker (starterkit/backend/implementation/capabilities/log/write_process/,
a real .NET binary -- built via `dotnet build`, see that directory's own
manifest.yaml) through a real ProcessExecutorPool, over the real
loopback-TCP wire protocol, and asserts what comes back through
`last_call_evidence()` matches what that worker genuinely did -- its own
real stdout, its real response.output, and a real OS exit code captured
once the pool shuts it down.

Run from the repository root (build the C# worker first, same command
its own manifest.yaml documents):
    python -m unittest starterkit.backend.implementation.tests.verify.test_process_executor_evidence -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO_ROOT))

from starterkit.backend.runtime.bridge.bridge import Bridge  # noqa: E402
from starterkit.backend.runtime.bridge.policy import PolicyContext, StaticPolicyEngine  # noqa: E402
from starterkit.backend.runtime.bridge.process_executor import ProcessExecutorPool  # noqa: E402
from starterkit.backend.runtime.bridge.registry import CapabilityRegistry  # noqa: E402
from starterkit.backend.runtime.bridge.selector import DeterministicSelector  # noqa: E402

_WORKER_EXE = _REPO_ROOT / "starterkit/backend/runtime/capabilities/log/write_process/bin/log_write_process.exe"

_EMPTY_POLICY = PolicyContext(user={}, consumer={}, ecosystem={}, provider={}, module={})


class ProcessExecutorEvidenceTests(unittest.TestCase):
    def setUp(self):
        if not _WORKER_EXE.exists():
            self.skipTest(
                f"{_WORKER_EXE} not built -- run `dotnet build` per "
                "starterkit/backend/implementation/capabilities/log/write_process/manifest.yaml first"
            )
        # A throwaway Bridge, unrelated to the real one requests.py builds --
        # this pool only needs `bridge` to construct its (here, empty)
        # Dependencies; nothing in this test resolves through it.
        bridge = Bridge(CapabilityRegistry(), StaticPolicyEngine(), DeterministicSelector())
        self.pool = ProcessExecutorPool(
            [str(_WORKER_EXE)], bridge=bridge, declared={}, pool_size=1,
        )

    def tearDown(self):
        self.pool._shutdown()  # noqa: SLF001 -- exercising real shutdown for the exit-code assertion below

    def test_evidence_captures_real_stdout_and_output(self):
        output = self.pool("write", {"message": "evidence capture works", "level": "info"}, _EMPTY_POLICY)
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
        self.pool("write", {"message": "first call", "level": "info"}, _EMPTY_POLICY)
        first_stdout = self.pool.last_call_evidence()["stdout"]
        self.assertIn("first call", first_stdout)

        self.pool("write", {"message": "second call", "level": "info"}, _EMPTY_POLICY)
        second_stdout = self.pool.last_call_evidence()["stdout"]
        self.assertIn("second call", second_stdout)
        self.assertNotIn("first call", second_stdout)

    def test_level_reflected_in_stdout(self):
        self.pool("write", {"message": "shout this", "level": "error"}, _EMPTY_POLICY)
        evidence = self.pool.last_call_evidence()
        self.assertIn("[ERROR] shout this", evidence["stdout"])

    def test_shutdown_captures_real_exit_code(self):
        self.pool("write", {"message": "before shutdown", "level": "info"}, _EMPTY_POLICY)
        self.pool._shutdown()  # noqa: SLF001 -- idempotent (empty queue on the second, tearDown's, call)
        codes = self.pool.shutdown_exit_codes()
        self.assertEqual(len(codes), 1)
        # terminate() on Windows maps to a non-zero exit; on POSIX, SIGTERM
        # also yields a non-None code once wait() completes -- either way,
        # a REAL captured code, not the live-call None seen mid-session.
        self.assertIsNotNone(codes[0])


if __name__ == "__main__":
    unittest.main()
