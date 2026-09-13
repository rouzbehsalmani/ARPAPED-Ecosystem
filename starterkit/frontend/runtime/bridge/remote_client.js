"use strict";
/**
 * Reference client for executor_kind: remote (blueprint/2-RULES.md R4).
 * Speaks starterkit/schemas/bridge-protocol.schema.json directly -- the same
 * request/response/error shape any consumer's Bridge call already uses,
 * not a second, simpler protocol the way executor_kind: process has its
 * own (process-executor-protocol.schema.json). A Remote call reaches a
 * whole OTHER Bridge (the backend's), which runs its own full
 * discovery -> policy -> selection using capability_id/operation/
 * contract_version -- so those fields travel on every call, unlike a
 * Worker's bare execute(operation, input, policy).
 *
 * This module owns the fetch/parse/error-mapping entirely -- a capability
 * never hand-rolls this itself, the same "reference client, not
 * hand-rolled per capability" posture starterkit/backend/clients/
 * already established for executor_kind: process.
 */

import { BridgeError } from "./core.js";

/**
 * Returns an `execute(operation, input, policy)` function that POSTs to
 * `address` (relative to `baseUrl`, e.g. "" in a real browser for
 * same-origin, or an explicit http://host:port when run headlessly with
 * no page origin to be relative to) and returns the remote Bridge's own
 * `output`, or raises a BridgeError built from its own observed
 * code/stage/message -- never inventing a trace or assuming success from
 * HTTP status alone.
 */
function makeRemoteExecutor(address, { baseUrl = "", capabilityId, contractVersion } = {}) {
  return async function execute(operation, input, policyContext) {
    const url = baseUrl + address;
    const requestId = Math.random().toString(16).slice(2) + Date.now().toString(16);
    let res;
    try {
      res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request_id: requestId,
          capability_id: capabilityId,
          contract_version: contractVersion,
          operation,
          input,
          policy_context: policyContext || {},
        }),
      });
    } catch (exc) {
      throw new BridgeError("BRIDGE_REMOTE_UNREACHABLE", "execution", `remote Bridge at ${url} was unreachable: ${exc}`);
    }
    const body = await res.json();
    if (body.code) {
      // The remote Bridge's own error, in its own words -- relayed, not reinterpreted.
      throw new BridgeError(body.code, body.stage, body.message, body.details);
    }
    // The remote side already ran its own full validated->executed trace;
    // this runtime's Core still appends its OWN five stages for THIS
    // request (Core.handle wraps this executor call) -- this function's
    // job is only to return the output, the same contract any other
    // executor_kind honors.
    return body.output;
  };
}

export { makeRemoteExecutor };
