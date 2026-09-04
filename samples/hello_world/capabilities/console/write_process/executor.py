"""Registration-unaware executor for console.write 2.0.0, running as its
own out-of-process program (executor_kind: process) instead of
in-process -- proves the protocol is language-neutral even for Python
itself. Spawned as `python executor.py` (../manifest.yaml's argv-list
`executor:`), served over loopback TCP by
clients/python/bridge_client.py's `serve_direct`. Same behavior as
../write_v2/executor.py -- in fact the identical native shape,
`execute(operation, input, policy) -> output`; only the wrapper at the
bottom of this file differs, because that's the only thing that should
ever depend on executor_kind.

`message`/`format` aren't checked here -- Bridge.handle already
validated both against the contract's declared shape before sending the
invocation, so `_FORMATTERS[input["format"]]` is a direct, trusting
lookup.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "clients" / "python"))
from bridge_client import serve_direct  # noqa: E402 -- import needs sys.path set first

_FORMATTERS = {
    "plain": lambda message: message,
    "uppercase": lambda message: message.upper(),
    "prefixed": lambda message: f"[console.write] {message}",
}


def execute(operation, input, policy):
    formatter = _FORMATTERS[input["format"]]
    print(formatter(input["message"]), flush=True)
    return {}


if __name__ == "__main__":
    serve_direct(execute)
