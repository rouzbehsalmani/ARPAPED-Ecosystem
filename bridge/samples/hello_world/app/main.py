"""Process entry point (R1): ordinary consumer code, not a second exemption.

It decides nothing and constructs no request itself -- it resolves through
the single request-construction point (app/requests.py) and then calls the
handle that comes back. Nothing here prints anything; that's console.write's
job.

Every `resolve` call below takes just a declared name and an operation --
no `contract_version`, no `implementation_id`. Each name (`console_write`,
`greeting_compose`, `console_write_legacy`, `greeting_compose_process`) is
declared once, in app/dependencies.yaml, with exactly the capability_id,
version, and (where it matters) implementation_id that name means -- the
same "declared once, never restated" pattern a capability's own executor
factory uses for ITS dependencies (bridge/bridge.py's `Dependencies`),
just keyed by name instead of capability_id so the same capability
(console.write) can be declared more than once, pinned differently for
different purposes. There is no default anywhere in this chain: a name
that isn't declared fails loudly (see app/requests.py).

Calling `resolve` once and reusing the handle for both of the first two
calls is the "discover once, call many times" pattern: `console_write`'s
discovery only runs once, while each `call` still gets its own fresh
policy_evaluated / selected / executed trace.

The third call, to `greeting_compose`, exercises capability-to-capability
calls (2-RULES.md R4): that capability's executor factory resolved
console.write once (see capabilities/greeting/compose/executor.py) and
calls it through the Bridge, same as this module does -- a real, nested,
fully-traced request, never a shortcut.

Both console.write versions are genuinely alive, each with its own real,
callable implementation, not just declared: contracts/console.write.contract.yaml's
`versions` holds 1.0.0 and 2.0.0 as peers (2-RULES.md R2)
(capabilities/console/write/ and capabilities/console/write_v2/). `console_write`
resolves at this app's declared pin (>=2.0.0, console.write.v2, the
contract's default -- identity.version) and uses `message`; `console_write_legacy`
is a deliberate proof, not an ongoing dependency, declared separately at
<2.0.0 (console.write.default) and uses `text`. The declared pin alone
determines which implementation each name reaches.

2.0.0 is more than a renamed field: the second call also passes
`format: "uppercase"`, an option 1.0.0 has no equivalent for
(capabilities/console/write_v2/executor.py) -- a real, exercised
capability difference between the two versions, not just a cosmetic one.

`greeting_compose_process` proves a capability can be implemented in a
language other than this Bridge's own (executor_kind: process,
bridge/process_executor.py) AND still compose other capabilities through
it, instead of being cut off from every capability that isn't also in
that language: `greeting.compose.process`
(capabilities/greeting/compose_process/) is a second, real implementation
of `greeting.compose`, written in Rust for this worked example, that
calls `console.write` FROM that out-of-process program, through the
Bridge, mid-request (the nested-call side of the wire protocol) -- the
same declared-dependency mechanism and enforcement
`capabilities/greeting/compose/executor.py`'s Python factory already gets
(2-RULES.md R4), just reached from another language. Its name identifies
what it proves (out-of-process vs. in-process), not which language it
happens to be written in. It never prints anything itself; the nested
call resolves to `console.write.default` (1.0.0, Python) -- the exact
same implementation the Python composer already reaches, since both
share the one contract-declared dependency pin (R2).

`console_write_process` closes the loop: `console.write.process`
(capabilities/console/write_process/) is a THIRD implementation of
`console.write`, and it's Python too -- but it runs as its own separate
process, using `clients/python/bridge_client.py`, the same way
`greeting.compose.process` uses `clients/rust/`. It doesn't reach the
Bridge in-process just because it happens to share a language with it;
it reaches it the exact same protocol-based way any other language does.
That's what makes "capabilities don't know what language the Bridge is
implemented with" actually true, not just true for languages that aren't
Python.

Run from the repository root (build the Rust executor first -- see
capabilities/greeting/compose_process/manifest.yaml):
    python -m bridge.samples.hello_world.app.main
"""

from bridge.samples.hello_world.app.requests import resolve


def main():
    writer = resolve("console_write", "write")
    writer.call({"message": "This is a test of the Bridge's console.write capability."})
    writer.call({"message": "Hello, world!", "format": "uppercase"})

    composer = resolve("greeting_compose", "compose")
    composer.call({"name": "ARPAPED"})

    writer_v1 = resolve("console_write_legacy", "write")
    writer_v1.call({"text": "console.write 1.0.0 is real and independently callable."})

    composer_process = resolve("greeting_compose_process", "compose")
    composer_process.call({"name": "ARPAPED (via Rust)"})

    writer_process = resolve("console_write_process", "write")
    writer_process.call({"message": "This line is printed by a second Python process, through the Bridge."})


if __name__ == "__main__":
    main()
