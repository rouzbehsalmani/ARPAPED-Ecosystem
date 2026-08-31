"""Process entry point (R1): ordinary consumer code, not a second exemption.

It decides nothing and constructs no request itself -- it resolves through
the single request-construction point (app/requests.py) and then calls the
handle that comes back. Nothing here prints anything; that's console.write's
job.

Calling `resolve` once and reusing the handle for both calls below is the
"discover once, call many times" pattern: `console.write`'s discovery only
runs once, while each `call` still gets its own fresh policy_evaluated /
selected / executed trace.

Run from the repository root:
    python -m bridge.samples.hello_world.app.main
"""

from bridge.samples.hello_world.app.requests import resolve


def main():
    writer = resolve("console.write", "write")

    first = writer.call({"text": "This is a test of the Bridge's console.write capability."})
    assert first.trace == ("validated", "discovered", "policy_evaluated", "selected", "executed")

    second = writer.call({"text": "Hello, world!"})
    assert second.trace == ("validated", "discovered", "policy_evaluated", "selected", "executed")


if __name__ == "__main__":
    main()
