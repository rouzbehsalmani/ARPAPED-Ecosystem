"use strict";
/**
 * Single request-construction point (blueprint/2-RULES.md R6) for the
 * frontend runtime -- the Bridge Adapter (Bridge glossary): builds this
 * runtime's Bridge Core (./bridge/, this starter kit's own frontend-runtime
 * Bridge -- lives inside frontend/runtime/bridge/, the same way the
 * backend's own Bridge lives inside backend/runtime/bridge/, so this
 * starter kit stays a self-contained, copy-from-here whole: everything a reader
 * needs to copy the shape of one runtime lives under that runtime's own
 * folder, nothing to go hunting for elsewhere in the repo), assembles
 * every implementation from the generated capability catalog (a build
 * artifact, fetched -- not read from disk, this runtime has no
 * filesystem; how it was generated is an implementation/-side concern
 * this runtime file has no need to know or name) -- never by walking
 * capabilities/ directly -- and exposes resolve(name, operation), the JS
 * mirror of ../backend/runtime/app/requests.py.
 *
 * Backend and frontend are served SEPARATELY (../../README.md "Two
 * servers, not one"), so this runtime's own assets and the backend's API
 * are never the same origin -- two different config values, never one
 * `baseUrl` doing both jobs:
 *   - `selfBaseUrl` locates THIS runtime's own catalog/executor assets --
 *     "" (relative to the current page) in a real browser, since whatever
 *     served this page also serves its own capability-catalog.jsonl; an
 *     explicit URL only for Node, which has no page origin to be
 *     relative to.
 *   - `backendBaseUrl` locates the backend's web.serve /bridge endpoint,
 *     for this runtime's own `remote`-kind implementations
 *     (log.write) -- always explicit; there is no same-origin case.
 *
 * `eventSink`, when given, is forwarded straight to BridgeCore (see
 * ./bridge/core.js) -- this file has no opinion on how/whether a real
 * call gets recorded, only on how the Core itself gets built. A real
 * browser passes none (no filesystem to write to); the Node-based
 * harness (implementation/tests/verify.js) passes a real fs-backed one.
 *
 * createApp is async: assembly fetches the catalog and dynamically
 * imports each Local executor module -- genuinely asynchronous in a
 * browser, never a synchronous filesystem read pretending to be one.
 */

import { BridgeCore } from "./bridge/core.js";
import { assembleFromCatalog } from "./bridge/assembler.js";

const DECLARED = {
  // This runtime's own declared-dependencies list (mirrors
  // ../backend/runtime/app/dependencies.yaml) -- keyed by name, not capability_id,
  // resolved once here rather than restated at every call site.
  client_log: { capabilityId: "client.log", contractVersion: "1.0.0" },
};

async function createApp({ selfBaseUrl = "", backendBaseUrl = "", importer, eventSink = null } = {}) {
  const core = new BridgeCore({ eventSink });
  await assembleFromCatalog("/capability-catalog.jsonl", core, {
    selfBaseUrl,
    backendBaseUrl,
    ...(importer ? { importer } : {}),
  });

  function resolve(name, operation) {
    const spec = DECLARED[name];
    if (!spec) {
      throw new Error(`${name} is not declared in this app's DECLARED list -- add it there before depending on it`);
    }
    return core.resolve(spec.capabilityId, operation, spec.contractVersion);
  }

  return { resolve, core };
}

export { createApp };
