"""Registration-unaware executor for console.write (see contracts/console.write.contract.yaml).

Exposes only execute(operation, input, policy) -> output. Never imports the
Registry, never calls register — this module has no idea it will be reached
through the Bridge.
"""

from bridge.bridge import BridgeError


def execute(operation, input, policy):
    if operation != "write":
        raise BridgeError("UNSUPPORTED_OPERATION", "execution", f"no such operation: {operation}")
    text = input.get("text")
    if not isinstance(text, str):
        raise BridgeError("INVALID_INPUT", "execution", "text must be a string")
    # flush=True: stdout is block-buffered, not line-buffered, when it isn't
    # a real terminal (2-RULES.md "the harness runs headlessly") -- without
    # it, this line could sit in Python's own buffer while a process-kind
    # executor's output (console/write_rust/executor.rs, which flushes
    # explicitly) reaches the terminal first, scrambling the visible order
    # even though the underlying calls ran in the right sequence.
    print(text, flush=True)
    return {}
