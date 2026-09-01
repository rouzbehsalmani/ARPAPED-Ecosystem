"""Executor factory for greeting.compose (see contracts/greeting.compose.contract.yaml).

Declares executor_kind: factory in its manifest, so this module's
make_executor is called once, at assembly time, with a Dependencies scoped
to exactly what the contract declared under dependencies.capabilities
(console.write) -- see 2-RULES.md R4 and bridge/bridge.py's Dependencies.
It resolves console.write once and returns the ordinary
execute(operation, input, policy) closure every other executor exposes --
every call on it is a real, fully-traced Bridge request (R6/R8), never a
direct call into console.write's executor.
"""

from bridge.bridge import BridgeError


def make_executor(dependencies):
    write = dependencies.resolve("console.write", "write")

    def execute(operation, input, policy):
        if operation != "compose":
            raise BridgeError("UNSUPPORTED_OPERATION", "execution", f"no such operation: {operation}")
        name = input.get("name")
        if not isinstance(name, str) or not name.strip():
            raise BridgeError("INVALID_INPUT", "execution", "name must be a non-empty string")
        write.call({"text": f"Greetings, {name}!"}, policy_context=policy)
        return {}

    return execute
