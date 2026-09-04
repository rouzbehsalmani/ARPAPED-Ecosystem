"""Registration-unaware executor for console.write (contracts/console.write.contract.yaml).

Exposes only execute(operation, input, policy) -> output; never imports
the Registry or calls register. Operation and input shape aren't
checked here -- the Bridge already guarantees both before this runs
(2-RULES.md "No silent defaults on what resolution depends on").
"""


def execute(operation, input, policy):
    text = input["text"]
    print(text, flush=True)  # stdout is block-buffered when not a real terminal
    return {}
