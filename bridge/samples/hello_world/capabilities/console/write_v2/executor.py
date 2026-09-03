"""Registration-unaware executor for console.write 2.0.0 (see
contracts/console.write.contract.yaml's `versions`).

Two differences from 1.0.0 (../write/executor.py, still registered as
console.write.default, kept unchanged so a dependent pinned to it --
greeting.compose -- keeps working unaffected, 2-RULES.md R4): the input
field was renamed 'text' -> 'message', and this version adds an optional
'format' input ('plain', 'uppercase', or 'prefixed') that 1.0.0 has no
equivalent for. Exposes only execute(operation, input, policy) -> output,
exactly like every other executor; never imports the Registry, never calls
register.
"""

from bridge.bridge import BridgeError

_FORMATTERS = {
    "plain": lambda message: message,
    "uppercase": lambda message: message.upper(),
    "prefixed": lambda message: f"[console.write] {message}",
}


def execute(operation, input, policy):
    if operation != "write":
        raise BridgeError("UNSUPPORTED_OPERATION", "execution", f"no such operation: {operation}")
    message = input.get("message")
    if not isinstance(message, str):
        raise BridgeError("INVALID_INPUT", "execution", "message must be a string")
    format_ = input.get("format", "plain")
    formatter = _FORMATTERS.get(format_)
    if formatter is None:
        raise BridgeError("INVALID_INPUT", "execution", f"format must be one of {sorted(_FORMATTERS)}, got {format_!r}")
    print(formatter(message), flush=True)  # see capabilities/console/write/executor.py's comment on flush=True
    return {}
