"""Generic adapter that lets a Bridge which cannot import a Python
callable in-process (any Bridge not itself Python) still reach an
executor_kind: direct/factory capability, completely unmodified.

Not written per-capability: takes the capability's own module:attr
executor path as a runtime argument, imports it, and hands it straight
to bridge_client.serve_direct/serve_factory -- the exact same functions
a native executor_kind: process capability uses (see
../../capabilities/console/write_process/executor.py). This is what
lets ../../capabilities/console/write/executor.py,
../../capabilities/console/write_v2/executor.py, and
../../capabilities/greeting/compose/executor.py stay untouched, forever,
regardless of what language a future Bridge is written in: the
capability author never has to know or care that this adapter exists.

Usage: python direct_adapter.py <direct|factory> <module:attr>
"""

import importlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bridge_client import serve_direct, serve_factory  # noqa: E402 -- import needs sys.path set first

# The target module:attr is resolved the same way "python -m ..." would
# resolve it from the repository root (this sample's own convention,
# see app/main.py's "Run from the repository root") -- the caller
# (ProcessExecutorPool) spawns this adapter with that as its working
# directory, same as it does for every other process-kind executor.
sys.path.insert(0, os.getcwd())


def _load(executor_path):
    module_name, attr = executor_path.split(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, attr)


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("direct", "factory"):
        print("usage: direct_adapter.py <direct|factory> <module:attr>", file=sys.stderr)
        raise SystemExit(2)
    kind, executor_path = sys.argv[1], sys.argv[2]
    target = _load(executor_path)
    if kind == "factory":
        serve_factory(target)
    else:
        serve_direct(target)


if __name__ == "__main__":
    main()
