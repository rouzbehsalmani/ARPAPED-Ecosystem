"use strict";
/**
 * Bridge Core for the frontend runtime (blueprint/2-RULES.md Bridge Core
 * glossary) -- a faithful port of sample/hello_world/backend/runtime/bridge/bridge.py's own pipeline:
 * validate -> discover -> policy -> select -> execute, returning the same
 * five-stage trace. This is the SAME architecture as the backend's Bridge,
 * running in a different runtime -- not a lighter or informal substitute
 * (2-RULES.md Bridge glossary).
 *
 * Lives here, inside frontend/ -- this sample's own frontend-runtime
 * Bridge, the same way sample/hello_world/backend/runtime/bridge/ lives inside
 * backend/: each runtime's Bridge stays with that runtime, so this
 * sample stays one self-contained worked example to copy the shape of
 * (README.md), never split across a shared location plus a per-sample
 * remainder. See MANIFEST.yaml.
 *
 * Validation stays Core-owned here too, not per-executor (2-RULES.md "An
 * operation's input shape is enforced once, from the contract, never
 * per-executor") -- checked once, against the resolved candidate's own
 * declared input_schema, before any executor runs.
 */

class BridgeError extends Error {
  constructor(code, stage, message, details = null) {
    super(`${code}@${stage}: ${message}`);
    this.code = code;
    this.stage = stage;
    this.bridgeMessage = message;
    this.details = details;
  }
}

function applyInputSchema(operation, input, inputSchema) {
  const effective = { ...input };
  for (const field of inputSchema || []) {
    const present = Object.prototype.hasOwnProperty.call(effective, field.name);
    if (!present) {
      if (field.required) {
        throw new BridgeError(
          "INVALID_INPUT", "execution",
          `'${field.name}' is required for operation '${operation}' but was not provided`,
        );
      }
      if (Object.prototype.hasOwnProperty.call(field, "default")) {
        effective[field.name] = field.default;
      }
      continue;
    }
    if (field.enum && !field.enum.includes(effective[field.name])) {
      throw new BridgeError(
        "INVALID_INPUT", "execution",
        `'${field.name}' must be one of ${JSON.stringify(field.enum)} for operation '${operation}', got ${JSON.stringify(effective[field.name])}`,
      );
    }
  }
  return effective;
}

class BoundCapability {
  constructor(core, resolved) {
    this._core = core;
    this._resolved = resolved;
  }

  /** Same "discover once, call many times" shape as BoundCapability.call
   * in sample/hello_world/backend/runtime/bridge/bridge.py -- policy/selection/execution still run
   * fresh on every call, through the same handle() every request uses. */
  async call(input, policyContext = {}) {
    return this._core.handle({
      requestId: cryptoRandomId(),
      capabilityId: this._resolved.capabilityId,
      contractVersion: this._resolved.contractVersion,
      operation: this._resolved.operation,
      input,
      policyContext,
    });
  }
}

function cryptoRandomId() {
  return Math.random().toString(16).slice(2) + Date.now().toString(16);
}

/** Mirrors sample/hello_world/backend/runtime/bridge/bridge.py's Dependencies: given once, at assembly
 * time, to a factory executor -- scoped to exactly what its own contract
 * declared, resolving anything else raises BRIDGE_UNDECLARED_DEPENDENCY. */
class Dependencies {
  constructor(core, declared) {
    this._core = core;
    this._declared = declared; // {capability_id: contract_version}
  }

  resolve(capabilityId, operation) {
    if (!Object.prototype.hasOwnProperty.call(this._declared, capabilityId)) {
      throw new BridgeError(
        "BRIDGE_UNDECLARED_DEPENDENCY", "validation",
        `${capabilityId} is not declared in this Dependencies' declared list`,
      );
    }
    const contractVersion = this._declared[capabilityId];
    const resolved = this._core.registry.discoverOne(capabilityId, contractVersion, operation);
    return new BoundCapability(this._core, resolved);
  }
}

function parseVersion(v) {
  return v.split(".").map((n) => parseInt(n, 10));
}

function compareVersions(a, b) {
  const pa = parseVersion(a);
  const pb = parseVersion(b);
  for (let i = 0; i < Math.max(pa.length, pb.length); i += 1) {
    const diff = (pa[i] || 0) - (pb[i] || 0);
    if (diff !== 0) return diff;
  }
  return 0;
}

/** Minimal constraint matcher for what this sample's contracts actually
 * declare: "*", an exact version, or comma-joined ">=X.Y.Z"/"<X.Y.Z"
 * clauses (2-RULES.md R4/"No silent defaults on what resolution depends
 * on" -- a version that isn't stated is never implicitly "any version";
 * this only ever matches what a constraint explicitly says). */
function satisfiesConstraint(version, constraint) {
  if (constraint === "*" || constraint === version) return true;
  return constraint.split(",").every((clause) => {
    const m = clause.trim().match(/^(>=|<=|>|<|==)?\s*(.+)$/);
    const op = m[1] || "==";
    const cmp = compareVersions(version, m[2]);
    if (op === ">=") return cmp >= 0;
    if (op === "<=") return cmp <= 0;
    if (op === ">") return cmp > 0;
    if (op === "<") return cmp < 0;
    return cmp === 0;
  });
}

class Registry {
  constructor() {
    this._entries = [];
  }

  register(entry) {
    this._entries.push(entry);
  }

  /** Exact/scoped discovery only (this Core serves two capabilities) --
   * still bounded, never a scan proportional to anything but its own
   * small entry list, consistent with 2-RULES.md's discovery cascade. */
  discover(capabilityId, contractVersion, operation) {
    return this._entries.filter(
      (e) => e.capabilityId === capabilityId
        && e.operations.includes(operation)
        && satisfiesConstraint(e.contractVersion, contractVersion),
    );
  }

  discoverOne(capabilityId, contractVersion, operation) {
    const candidates = this.discover(capabilityId, contractVersion, operation);
    if (candidates.length === 0) {
      throw new BridgeError("BRIDGE_NO_IMPLEMENTATION", "discovery", `No compatible implementation for ${capabilityId}.${operation}`);
    }
    const best = candidates.reduce((a, b) => (b.priority > a.priority ? b : a));
    return { capabilityId, contractVersion: best.contractVersion, operation, entry: best };
  }
}

/** Allow-all, mirrors sample/hello_world/backend/runtime/bridge/policy.py's StaticPolicyEngine -- a
 * placeholder decision stage, not a security boundary this sample needs
 * to demonstrate. */
function evaluatePolicy(_entry, _policyContext) {
  return { allowed: true };
}

/** Highest-priority-wins, mirrors sample/hello_world/backend/runtime/bridge/selector.py's
 * DeterministicSelector. */
function select(candidates) {
  return candidates.reduce((a, b) => (b.priority > a.priority ? b : a));
}

class BridgeCore {
  constructor() {
    this.registry = new Registry();
  }

  resolve(capabilityId, operation, contractVersion) {
    const resolved = this.registry.discoverOne(capabilityId, contractVersion, operation);
    return new BoundCapability(this, resolved);
  }

  /** The Core pipeline itself -- validated -> discovered -> policy_evaluated
   * -> selected -> executed, the same five stages sample/hello_world/backend/runtime/bridge/bridge.py's
   * Bridge.handle produces, asserted identically by any harness that
   * exercises this runtime's own Bridge (blueprint/1-CYCLE.md Gate 19). */
  async handle(request) {
    const trace = [];
    if (!request.requestId || !request.capabilityId || !request.contractVersion || !request.operation) {
      throw new BridgeError("BRIDGE_INVALID_REQUEST", "validation", "Required request field is empty");
    }
    trace.push("validated");

    const discovered = this.registry.discover(request.capabilityId, request.contractVersion, request.operation);
    trace.push("discovered");
    if (discovered.length === 0) {
      throw new BridgeError("BRIDGE_NO_IMPLEMENTATION", "discovery", "No compatible implementation discovered");
    }

    const allowed = discovered.filter((e) => evaluatePolicy(e, request.policyContext).allowed);
    trace.push("policy_evaluated");
    if (allowed.length === 0) {
      throw new BridgeError("BRIDGE_POLICY_DENIED", "policy", "All compatible candidates were rejected");
    }

    const chosen = select(allowed);
    trace.push("selected");

    const effectiveInput = applyInputSchema(request.operation, request.input, chosen.inputSchema && chosen.inputSchema[request.operation]);

    let output;
    try {
      output = await chosen.executor(request.operation, effectiveInput, request.policyContext);
    } catch (exc) {
      if (exc instanceof BridgeError) throw exc;
      throw new BridgeError("BRIDGE_EXECUTION_FAILED", "execution", "The selected implementation did not execute the request", { causeType: exc && exc.name });
    }
    trace.push("executed");

    return {
      requestId: request.requestId,
      capabilityId: request.capabilityId,
      contractVersion: chosen.contractVersion,
      implementationId: chosen.implementationId,
      output,
      trace,
    };
  }
}

export { BridgeCore, BridgeError, Dependencies };
