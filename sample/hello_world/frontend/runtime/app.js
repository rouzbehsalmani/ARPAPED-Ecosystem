"use strict";
/**
 * Single request-construction point (blueprint/2-RULES.md R6) for the
 * frontend runtime -- the Bridge Adapter (Bridge glossary): builds this
 * runtime's Bridge Core (./bridge/, this sample's own frontend-runtime
 * Bridge -- lives inside frontend/, the same way the backend's own Bridge
 * lives inside backend/bridge/, so this sample stays a self-contained
 * worked example: everything a reader needs to copy the shape of one
 * runtime lives under that runtime's own folder, nothing to go hunting
 * for elsewhere in the repo), assembles every implementation from the
 * generated capability catalog (build_catalog.py, fetched -- not read
 * from disk, this runtime has no filesystem) -- never by walking
 * capabilities/ directly -- and exposes resolve(name, operation), the JS
 * mirror of ../backend/app/requests.py.
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
 *     (console.write) -- always explicit; there is no same-origin case.
 *
 * createApp is async: assembly fetches the catalog and dynamically
 * imports each Local executor module -- genuinely asynchronous in a
 * browser, never a synchronous filesystem read pretending to be one.
 */

import { BridgeCore } from "./bridge/core.js";
import { assembleFromCatalog } from "./bridge/assembler.js";

const DECLARED = {
  // This runtime's own declared-dependencies list (mirrors
  // ../backend/app/dependencies.yaml) -- keyed by name, not capability_id,
  // resolved once here rather than restated at every call site.
  greeting_render: { capabilityId: "greeting.render", contractVersion: "1.0.0" },
};

async function createApp({ selfBaseUrl = "", backendBaseUrl = "", importer } = {}) {
  const core = new BridgeCore();
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
