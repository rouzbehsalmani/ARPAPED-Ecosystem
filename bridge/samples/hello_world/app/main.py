"""Process entry point (R1): ordinary consumer code, not a second exemption.

It decides nothing and constructs no request itself -- it resolves through
the single request-construction point (app/requests.py) and then calls the
handle that comes back. Nothing here prints anything; that's console.write's
job.

Calling `resolve` once and reusing the handle for both calls below is the
"discover once, call many times" pattern: `console.write`'s discovery only
runs once, while each `call` still gets its own fresh policy_evaluated /
selected / executed trace.

The first call also passes `on_stage`, observing each trace stage live as
the Bridge reaches it (bridge/bridge.py) instead of only seeing the trace
once the call has already returned — the same mechanism a verification
harness uses (bounded per-stage timeout, via `Bridge.handle_with_timeout`)
so a hung capability operation fails fast and diagnosably instead of
blocking an unattended pipeline forever (2-RULES.md R5).

Run from the repository root:
    python -m bridge.samples.hello_world.app.main
"""

from bridge.samples.hello_world.app.requests import resolve


def main():
    writer = resolve("console.write", "write")

    stages_seen = []
    first = writer.call(
        {"text": "This is a test of the Bridge's console.write capability."},
        on_stage=stages_seen.append,
    )
    assert first.trace == ("validated", "discovered", "policy_evaluated", "selected", "executed")
    assert tuple(stages_seen) == first.trace

    second = writer.call({"text": "Hello, world!"})
    assert second.trace == ("validated", "discovered", "policy_evaluated", "selected", "executed")


if __name__ == "__main__":
    main()
