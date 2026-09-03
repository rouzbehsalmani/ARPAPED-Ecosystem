"""Process entry point (R1): ordinary consumer code, not a second exemption.

It decides nothing and constructs no request itself -- it resolves through
the single request-construction point (app/requests.py) and then calls the
handle that comes back. Nothing here prints anything; that's console.write's
job.

Every `resolve` call below takes just a declared name and an operation --
no `contract_version`, no `implementation_id`. Each name (`console_write`,
`greeting_compose`, `console_write_legacy`, `console_write_rust`) is
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

`console_write_rust` shows a capability can be implemented in a language
other than this Bridge's own (executor_kind: process,
bridge/process_executor.py): `console.write.rust`
(capabilities/console/write_rust/) is a second, real implementation of the
SAME console.write 2.0.0 operation, written in Rust, spawned as a separate
process and reached over loopback TCP -- never imported. Its priority
(150) is below console.write.v2's (200), so it never becomes the default
for `console_write`'s own pin; it's declared under its own name, with its
own implementation_id, precisely so it's reached regardless of priority
ordering -- the same posture `console_write_legacy` already has toward
`console_write`.

Run from the repository root (build the Rust executor first -- see
capabilities/console/write_rust/manifest.yaml):
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

    writer_rust = resolve("console_write_rust", "write")
    writer_rust.call({"message": "This line is printed by a Rust process, through the Bridge."})


if __name__ == "__main__":
    main()
