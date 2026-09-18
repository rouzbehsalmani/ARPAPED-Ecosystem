"""Generic adapter that lets a Bridge which cannot import a Python
callable in-process (any Bridge not itself Python) still reach an
executor_kind: direct/factory capability, completely unmodified.

Not written per-capability: takes the capability's own manifest-style
executor path (relative/file/path.py:attr, relative to this runtime's own
root -- backend/runtime/bridge/assembler.py's own convention) as a runtime
argument, imports it, and hands it straight to
bridge_client.serve_direct/serve_factory -- the same functions a
native Python executor_kind: process capability would use (this starter
kit's own process-kind implementation, log.write.process, happens to be
written in C#, so it uses that language's own reference client instead;
see ../../../implementation/capabilities/log/write_process/). This is
what lets ../../capabilities/log/write/executor.py and
../../capabilities/web/serve/executor.py stay untouched, forever,
regardless of what language a future Bridge is written in: the
capability author never has to know or care that this adapter exists.

Usage: python direct_adapter.py <direct|factory> <relative/file/path.py:attr>
"""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bridge_client import serve_direct, serve_factory  # noqa: E402 -- import needs sys.path set first

# This runtime's own root, located from THIS file's own disk location
# (clients/python/direct_adapter.py -> clients/python -> clients -> runtime
# root) -- never the caller's cwd or a hardcoded package name, so this
# adapter works regardless of what a foreign-language Bridge sets its
# spawned subprocess's working directory to, and regardless of what the
# runtime/ folder itself is named, or whether it even has a wrapper name
# at all (see backend/README.md "Copying runtime/ elsewhere"). Inserted
# directly (not its parent) so the target executor's own module resolves
# as a bare top-level name, e.g. "capabilities.log.write.executor" --
# the SAME name bridge/assembler.py's own `_runtime_module_name` produces,
# so a capability's executor path never has to know which of the two ways
# it's being loaded.
_RUNTIME_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(_RUNTIME_ROOT))


def _load(executor_path):
    rel_path, attr = executor_path.split(":", 1)
    if rel_path.endswith(".py"):
        rel_path = rel_path[: -len(".py")]
    module_name = rel_path.replace("/", ".")
    module = importlib.import_module(module_name)
    return getattr(module, attr)


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("direct", "factory"):
        print("usage: direct_adapter.py <direct|factory> <relative/file/path.py:attr>", file=sys.stderr)
        raise SystemExit(2)
    kind, executor_path = sys.argv[1], sys.argv[2]
    target = _load(executor_path)
    if kind == "factory":
        serve_factory(target)
    else:
        serve_direct(target)


if __name__ == "__main__":
    main()
