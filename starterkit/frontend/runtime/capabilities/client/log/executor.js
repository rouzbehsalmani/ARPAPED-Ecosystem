"use strict";
/**
 * Executor factory for client.log (../../../contracts/client.log.contract.yaml),
 * Local execution (executor_kind: factory) in the frontend's own Bridge
 * Core -- its OWN capability, not a second implementation of backend's
 * log.write (see the contract's own header for why). makeExecutor is
 * called once, at assembly time, with a Dependencies scoped to
 * dependencies.capabilities (log.write, R4) -- but `dependencies.resolve(...)`
 * itself is called lazily, inside `execute`, once per real call, not
 * once here: assembleFromCatalog registers catalog entries in file order
 * (../../../implementation/build_catalog.py's own sorted glob), and this
 * capability's own manifest sorts alphabetically BEFORE log.write's own
 * remote-pointer manifest -- resolving eagerly here would look up a
 * capability not registered yet. The same lazy-resolve pattern
 * ../../web/serve/executor.py's own factory already uses on the backend
 * (resolve inside the request handler, never at make_executor time),
 * generalized here rather than relying on file-sort order ever landing
 * the way an earlier version of this file happened to.
 */

function makeExecutor(dependencies) {
  return async function execute(operation, input, policy) {
    const write = dependencies.resolve("log.write", "write");
    await write.call({ message: input.message, level: input.level || "info" }, policy);
    return {};
  };
}

export { makeExecutor };
