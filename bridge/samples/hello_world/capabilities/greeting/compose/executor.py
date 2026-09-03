"""Executor factory for greeting.compose (see contracts/greeting.compose.contract.yaml).

Declares executor_kind: factory in its manifest, so this module's
make_executor is called once, at assembly time, with a Dependencies scoped
to exactly what the contract declared under dependencies.capabilities
(console.write) -- see 2-RULES.md R4 and bridge/bridge.py's Dependencies.
It resolves console.write once and returns the ordinary
execute(operation, input, policy) closure every other executor exposes --
every call on it is a real, fully-traced Bridge request (R6/R8), never a
direct call into console.write's executor.

Nothing about `name` is checked here at all any more -- `Bridge.handle`
already validated it against the contract's declared shape before this
ever runs (2-RULES.md "No silent defaults on what resolution depends
on"): required, `type: string`, and (via `pattern: "\S"`, not
`minLength`, since a whitespace-only string has nonzero length) actually
non-blank. All three are generic, structural constraints, not business
logic -- there's nothing left here that needed capability-specific
understanding to check.
"""


def make_executor(dependencies):
    write = dependencies.resolve("console.write", "write")

    def execute(operation, input, policy):
        write.call({"text": f"Greetings, {input['name']}!"}, policy_context=policy)
        return {}

    return execute
