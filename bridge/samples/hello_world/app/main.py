"""Process entry point (R1): ordinary consumer code, not a second exemption.

It decides nothing and constructs no request itself -- it just calls through
the single request-construction point (app/requests.py). Nothing here prints
anything; that's console.write's job.

Run from the repository root:
    python -m bridge.samples.hello_world.app.main
"""

from bridge.samples.hello_world.app.requests import call


def main():
    response = call("console.write", "write", {"text": "Hello, world!"})
    assert response.trace == ("validated", "discovered", "policy_evaluated", "selected", "executed")


if __name__ == "__main__":
    main()
