"use strict";
/**
 * Publish-phase helper for the frontend runtime -- mirrors
 * ../../../backend/runtime/bridge/assembler.py's role exactly (blueprint/2-RULES.md
 * "assemble"): reads capability-catalog.jsonl (a generated build
 * artifact -- how it was built is an implementation/-side concern this
 * runtime file has no need to know or name), imports each executor,
 * and registers each implementation into this runtime's own Bridge Core
 * -- never by walking capabilities/ directly at load time.
 *
 * Uses fetch() and dynamic import(), never fs/require -- this is the
 * ACTUAL browser runtime, not Node-only pseudocode standing in for one
 * (a real browser has no filesystem access and no CommonJS require).
 *
 * TWO different base URLs, never conflated (backend and frontend are
 * separately served -- ../../../README.md "Two servers, not one"):
 *   - `selfBaseUrl` locates THIS runtime's own assets -- the catalog
 *     itself and any Local (factory/direct) executor module. "" (relative
 *     to the current page) in a real browser, since wherever this page
 *     was loaded from is also where its own catalog/executors live; an
 *     explicit URL only when Node's fetch/import need one (they have no
 *     page origin to be relative to).
 *   - `backendBaseUrl` locates the REMOTE backend's own web.serve -- used
 *     ONLY for executor_kind: remote entries, never for this runtime's
 *     own assets. Always explicit; there is no same-origin case for it,
 *     since the backend is never this runtime's own origin.
 *
 * Loading a LOCAL executor module is the one place Node and a browser
 * genuinely differ: a real browser's native dynamic import() resolves an
 * http(s) URL directly, but Node's does not (no
 * --experimental-network-imports in general availability) -- so
 * `importer` exists ONLY to let the Node-based test harness substitute a
 * local file:// import for that one step; the default IS the real browser
 * behavior, never overridden in production use.
 */

import { Dependencies } from "./core.js";
import { makeRemoteExecutor } from "./remote_client.js";

async function assembleFromCatalog(
  catalogUrl,
  core,
  { selfBaseUrl = "", backendBaseUrl = "", importer = (specifier) => import(specifier) } = {},
) {
  const res = await fetch(selfBaseUrl + catalogUrl);
  const text = await res.text();
  const lines = text.split("\n").filter((l) => l.trim());
  let count = 0;
  for (const line of lines) {
    const entry = JSON.parse(line);
    if (entry.enabled === false) continue;

    let executor;
    if (entry.executor_kind === "remote") {
      executor = makeRemoteExecutor(entry.executor, {
        baseUrl: backendBaseUrl,
        capabilityId: entry.capability_id,
        contractVersion: entry.contract_version,
      });
    } else if (entry.executor_kind === "factory") {
      const mod = await importer(selfBaseUrl + "/" + entry.executor);
      const declared = entry.dependencies || {};
      executor = mod.makeExecutor(new Dependencies(core, declared));
    } else {
      const mod = await importer(selfBaseUrl + "/" + entry.executor);
      executor = mod.execute;
    }

    core.registry.register({
      capabilityId: entry.capability_id,
      contractVersion: entry.contract_version,
      implementationId: entry.implementation_id,
      operations: entry.operations,
      priority: entry.priority,
      inputSchema: entry.input_schema || {},
      executor,
    });
    count += 1;
  }
  return count;
}

export { assembleFromCatalog };
