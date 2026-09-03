"""Executor factory for greeting.compose (contracts/greeting.compose.contract.yaml).

executor_kind: factory -- make_executor is called once, at assembly
time, with a Dependencies scoped to dependencies.capabilities
(console.write, R4). Resolves console.write once and returns the
execute(operation, input, policy) closure; every call is a real,
fully-traced Bridge request (R6/R8), never a direct executor call.

`name` isn't checked here -- Bridge.handle already validated it
(required, type: string, non-blank via `pattern: "\S"`, not minLength).
"""


def make_executor(dependencies):
    write = dependencies.resolve("console.write", "write")

    def execute(operation, input, policy):
        write.call({"text": f"Greetings, {input['name']}!"}, policy_context=policy)
        return {}

    return execute
