"""Registration-unaware executor for console.write 2.0.0, running as its
own separate out-of-process program (executor_kind: process) instead of
in-process -- proves the process executor protocol
(schemas/process-executor-protocol.schema.json) is genuinely
language-neutral: a Python capability doesn't have to run in-process
just because the Bridge happens to be Python too. Uses
clients/python/bridge_client.py, the same reference client any Python
process-kind capability would use -- exactly mirroring what
clients/rust/ is for a Rust one (see ../../greeting/compose_process/).

Not imported by the Bridge at all: spawned as a genuinely separate
process (`python executor.py`, see ../manifest.yaml's argv-list
`executor:`) and reached over loopback TCP, same as any other
process-kind executor. Same operation and formatting behavior as
../write_v2/executor.py, over a different transport.

Nothing about `message`/`format` is checked here at all any more --
`Bridge.handle` (bridge/bridge.py) already validated both against the
contract's declared shape before this process was ever sent the
invocation (2-RULES.md "No silent defaults on what resolution depends
on") -- true for a process-kind executor exactly as it is for a direct
one: `message` required and `type: string`; `format` absent-or-declared
(`default: plain`, so `input["format"]` is always present), `type:
string`, and one of exactly `enum: [plain, uppercase, prefixed]`
(contracts/console.write.contract.yaml) -- so `_FORMATTERS[input["format"]]`
below is a direct, trusting lookup, not a defensive one.
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
