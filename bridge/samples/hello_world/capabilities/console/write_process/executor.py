"""Registration-unaware executor for console.write 2.0.0, running as its
own out-of-process program (executor_kind: process) instead of
in-process -- proves the protocol is language-neutral even for Python
itself. Spawned as `python executor.py` (../manifest.yaml's argv-list
`executor:`), reached over loopback TCP via
clients/python/bridge_client.py. Same behavior as ../write_v2/executor.py,
over a different transport.

`message`/`format` aren't checked here -- Bridge.handle already
validated both against the contract's declared shape before sending the
invocation, so `_FORMATTERS[input["format"]]` is a direct, trusting
lookup.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "clients" / "python"))
from bridge_client import Connection  # noqa: E402 -- import needs sys.path set first

_FORMATTERS = {
    "plain": lambda message: message,
    "uppercase": lambda message: message.upper(),
    "prefixed": lambda message: f"[console.write] {message}",
}


def handle(conn: Connection, operation: str, input: dict) -> None:
    formatter = _FORMATTERS[input["format"]]
    print(formatter(input["message"]), flush=True)
    conn.reply_output({})


if __name__ == "__main__":
    Connection().serve(handle)
