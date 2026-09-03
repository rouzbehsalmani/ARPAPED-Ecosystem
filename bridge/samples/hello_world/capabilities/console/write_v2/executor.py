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

Nothing about `message`/`format` is checked here at all any more --
`Bridge.handle` already validated both against the contract's declared
shape before this ever runs (2-RULES.md "No silent defaults on what
resolution depends on"): `message` required and `type: string`;
`format` absent-or-declared (`default: plain`, so `input["format"]` is
always present), `type: string`, and one of exactly `enum: [plain,
uppercase, prefixed]` (contracts/console.write.contract.yaml) -- so
`_FORMATTERS[input["format"]]` below is a direct, trusting lookup, not a
defensive one: the Bridge already guarantees the key exists.
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
