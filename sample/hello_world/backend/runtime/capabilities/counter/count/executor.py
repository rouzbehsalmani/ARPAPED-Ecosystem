"""Registration-unaware executor for counter.count 1.1.0
(contracts/counter.count.contract.yaml): accepts a word and returns it
together with the running number of times that word has been submitted in
this runtime's lifetime; `reset` clears every per-word count and reports
the cleared state.

State lives at module scope on purpose: this module is imported once by the
assembler when the capability is registered, so `_COUNTS` is shared by every
call the Bridge routes through this executor for the whole lifetime of this
runtime process. No persistence is promised across separate runs -- a fresh
process starts with an empty dict, which is exactly the contract's
state_scope. `reset` clears the same dict, so the very next `count` of any
word is 1 again.

`word` isn't re-validated here -- Bridge.handle already checked it against
the contract's declared shape (required string containing at least one
non-whitespace character), so it can be used as a dict key directly.
"""

_COUNTS = {}


def execute(operation, input, policy):
    if operation == "reset":
        _COUNTS.clear()
        return {"count": 0}
    word = input["word"]
    current = _COUNTS.get(word, 0) + 1
    _COUNTS[word] = current
    return {"word": word, "count": current}