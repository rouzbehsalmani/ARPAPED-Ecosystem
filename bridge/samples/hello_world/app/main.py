"""Process entry point (R1): ordinary consumer code, not a second exemption.

It decides nothing and constructs no request itself -- it resolves through
the single request-construction point (app/requests.py) and then calls the
handle that comes back. Nothing here prints anything; that's console.write's
job.

The first three `resolve` calls below take no `contract_version` at all --
it comes from this app's own declared dependencies (app/requests.py,
app/dependencies.yaml), the same "declared once, never restated" pattern a
capability's own executor factory uses for ITS dependencies
(bridge/bridge.py's `Dependencies`). The fourth call is different: it's a
deliberate one-off proof, not a normal dependency, so it goes through
`resolve_pinned` and states its version explicitly right there -- there is
no default on that path either (see app/requests.py). A default would mean
"whichever version tie-breaking happens to pick" -- an implicit choice
nobody actually made. Either way, a missing or undeclared version is an
immediate, loud failure, never a quiet wrong answer.

Calling `resolve` once and reusing the handle for both of the first two
calls is the "discover once, call many times" pattern: `console.write`'s
discovery only runs once, while each `call` still gets its own fresh
policy_evaluated / selected / executed trace.

The first call also passes `on_stage`, observing each trace stage live as
the Bridge reaches it (bridge/bridge.py) instead of only seeing the trace
once the call has already returned — the same mechanism a verification
harness uses (bounded per-stage timeout, via `Bridge.handle_with_timeout`)
so a hung capability operation fails fast and diagnosably instead of
blocking an unattended pipeline forever (2-RULES.md R5).

The third call, to `greeting.compose`, proves capability-to-capability
calls (2-RULES.md R4): that capability's executor factory resolved
console.write once (see capabilities/greeting/compose/executor.py) and
calls it through the Bridge, same as this module does — a real, nested,
fully-traced request, never a shortcut. Its own trace reaching `executed`
is only possible if that nested call itself completed the full
validated/discovered/policy_evaluated/selected/executed path.

Both console.write versions are genuinely alive, each with its own real,
callable implementation, not just declared: contracts/console.write.contract.yaml's
`versions` holds 1.0.0 and 2.0.0 as peers (2-RULES.md R2)
(capabilities/console/write/ and capabilities/console/write_v2/). The first
two calls resolve at this app's declared pin (>=2.0.0, console.write.v2,
the contract's default -- identity.version) and use `message`; the fourth
explicitly pins <2.0.0 (console.write.default) through `resolve_pinned` and
uses `text`. The pin alone determines which implementation each call reaches.

2.0.0 is more than a renamed field: the second call also passes
`format: "uppercase"`, an option 1.0.0 has no equivalent for
(capabilities/console/write_v2/executor.py) -- a real, exercised
capability difference between the two versions, not just a cosmetic one.

Run from the repository root:
    python -m bridge.samples.hello_world.app.main
"""

from bridge.samples.hello_world.app.requests import resolve, resolve_pinned


def main():
    writer = resolve("console.write", "write")

    stages_seen = []
    first = writer.call(
        {"message": "This is a test of the Bridge's console.write capability."},
        on_stage=stages_seen.append,
    )
    assert first.trace == ("validated", "discovered", "policy_evaluated", "selected", "executed")
    assert tuple(stages_seen) == first.trace
    assert first.implementation_id == "console.write.v2"

    second = writer.call({"message": "Hello, world!", "format": "uppercase"})
    assert second.trace == ("validated", "discovered", "policy_evaluated", "selected", "executed")
    assert second.implementation_id == "console.write.v2"

    composer = resolve("greeting.compose", "compose")
    third = composer.call({"name": "ARPAPED"})
    assert third.trace == ("validated", "discovered", "policy_evaluated", "selected", "executed")

    writer_v1 = resolve_pinned("console.write", "write", contract_version="<2.0.0")
    fourth = writer_v1.call({"text": "console.write 1.0.0 is real and independently callable."})
    assert fourth.trace == ("validated", "discovered", "policy_evaluated", "selected", "executed")
    assert fourth.implementation_id == "console.write.default"


if __name__ == "__main__":
    main()
