"""Registration-unaware executor for console.write 2.0.0
(contracts/console.write.contract.yaml). vs. 1.0.0 (../write/executor.py,
kept unchanged, R4): 'text' renamed to 'message', plus an optional
'format' ('plain'/'uppercase'/'prefixed').

`message`/`format` aren't checked here -- Bridge.handle already
validated both against the contract's declared shape (required, type,
default, enum), so `_FORMATTERS[input["format"]]` is a direct, trusting
lookup.
"""

_FORMATTERS = {
    "plain": lambda message: message,
    "uppercase": lambda message: message.upper(),
    "prefixed": lambda message: f"[console.write] {message}",
}


def execute(operation, input, policy):
    formatter = _FORMATTERS[input["format"]]
    print(formatter(input["message"]), flush=True)  # see capabilities/console/write/executor.py's comment on flush=True
    return {}
