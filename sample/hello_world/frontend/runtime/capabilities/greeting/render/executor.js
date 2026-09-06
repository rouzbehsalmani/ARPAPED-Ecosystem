"use strict";
/**
 * Executor factory for greeting.render (../../../contracts/greeting.render.contract.yaml),
 * Local execution (executor_kind: factory) in the frontend's own Bridge
 * Core -- its OWN capability, not a second implementation of backend's
 * greeting.compose (see the contract's own header for why). makeExecutor
 * is called once, at assembly time, with a Dependencies scoped to
 * dependencies.capabilities (console.write, R4). console.write only
 * exists Remote from this runtime's own registry (../../console/write/manifest.json) --
 * this factory doesn't know or care; `write.call(...)` is a real,
 * fully-traced Bridge request either way (R6/R8).
 */

function makeExecutor(dependencies) {
  const write = dependencies.resolve("console.write", "write");

  return async function execute(operation, input, policy) {
    const message = `Greetings, ${input.name}! (rendered by the frontend)`;
    // console.write is pinned <2.0.0 (this contract's own
    // dependencies.capabilities) -- 1.0.0's `text` field, not 2.0.0's `message`.
    await write.call({ text: message }, policy);
    return { message };
  };
}

export { makeExecutor };
