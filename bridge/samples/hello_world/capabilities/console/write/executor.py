"""Registration-unaware executor for console.write (see contracts/console.write.contract.yaml).

Exposes only execute(operation, input, policy) -> output. Never imports the
Registry, never calls register — this module has no idea it will be reached
through the Bridge.

Neither the operation name nor `text`'s required-ness/type is checked
here: the Bridge already guarantees both before this ever runs --
discovery only calls an executor with an operation it declared, and
`Bridge.handle` validates `input` against the contract's declared shape
(2-RULES.md "No silent defaults on what resolution depends on") before
any executor sees it. Nothing left for this executor to check that isn't
genuine console.write-specific business logic -- and there isn't any.
"""


def execute(operation, input, policy):
    text = input["text"]
    # flush=True: stdout is block-buffered, not line-buffered, when it isn't
    # a real terminal (2-RULES.md "the harness runs headlessly") -- without
    # it, this line could sit in Python's own buffer instead of reaching
    # the terminal as each call actually happens.
    print(text, flush=True)
    return {}
