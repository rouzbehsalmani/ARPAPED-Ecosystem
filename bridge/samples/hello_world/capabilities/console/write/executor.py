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
    print(text)
    return {}
