"use strict";
/**
 * Headless verification for the frontend's own Bridge (blueprint/1-CYCLE.md
 * Gate 19: "when a consumer surface is another entry point with its own
 * resolved Bridge, this includes THAT Bridge's own resolution/execution
 * path -- not just the backend capability tested in isolation"). Run by
 * ../../../backend/implementation/tests/verify/verify.py as a subprocess;
 * prints ONE JSON array of check objects to stdout (the same shape
 * verify.py's own checks use) and exits non-zero if anything failed --
 * never a separate, un-aggregated verification record for the same cycle.
 *
 * Usage: node verify.js <backend base url> <frontend static base url>
 * (backend and frontend are served SEPARATELY -- ../../../README.md "Two
 * servers, not one" -- so the harness starts both for real and passes
 * both URLs through, exactly mirroring the real two-server topology
 * rather than a single shared one.)
 *
 * The ONE Node-specific accommodation: ../runtime/bridge/assembler.js
 * fetches the catalog over real HTTP (identical to a real browser), but
 * loading a LOCAL (factory) executor module needs Node's own dynamic
 * import() to resolve a real file, since Node has no
 * --experimental-network-imports in general availability the way a
 * browser's native import() resolves an http(s) URL directly. `nodeImporter`
 * below exists ONLY for that; app.js's default behavior (no override) IS
 * the real browser behavior, never touched in production use.
 *
 * The SECOND Node-specific accommodation: `fsEventSink` below, passed as
 * app.js's own `eventSink` option -- a real browser has no filesystem to
 * persist a runtime event to (blueprint/schemas/runtime-event.schema.json,
 * blueprint/dep/MANIFEST.yaml: runtime_log), but this harness runs in
 * Node, which does. Writes ../../state/runtime-events.jsonl, the same
 * JSONL-per-call shape ../../../backend/state/runtime-events.jsonl
 * already uses -- both validate against the same schema, so a reader
 * never needs to know which runtime produced a given line.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { createApp } from "../../runtime/app.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const RUNTIME_ROOT = path.resolve(__dirname, "../../runtime");
const RUNTIME_EVENTS_PATH = path.resolve(__dirname, "../../state/runtime-events.jsonl");

function fsEventSink(event) {
  fs.mkdirSync(path.dirname(RUNTIME_EVENTS_PATH), { recursive: true });
  fs.appendFileSync(RUNTIME_EVENTS_PATH, `${JSON.stringify(event)}\n`, "utf-8");
}

function nodeImporter(specifier) {
  const url = new URL(specifier);
  const localPath = path.join(RUNTIME_ROOT, url.pathname);
  return import(pathToFileURL(localPath).href);
}

const EXPECTED_TRACE = JSON.stringify(["validated", "discovered", "policy_evaluated", "selected", "executed"]);

async function main() {
  const backendBaseUrl = process.argv[2];
  const selfBaseUrl = process.argv[3];
  if (!backendBaseUrl || !selfBaseUrl) {
    process.stderr.write("usage: node verify.js <backend base url> <frontend static base url>\n");
    process.exit(2);
  }

  const checks = [];

  const input = { name: "ARPAPED (via the frontend Bridge)" };
  try {
    const app = await createApp({ backendBaseUrl, selfBaseUrl, importer: nodeImporter, eventSink: fsEventSink });
    const handle = app.resolve("greeting_render", "render");
    const response = await handle.call(input);
    const traceJson = JSON.stringify(response.trace);
    const status = traceJson === EXPECTED_TRACE ? "passed" : "failed";
    const check = {
      check_id: "call:1:greeting_render (frontend)",
      input,
      description: `greeting_render.render reaches every stage through ${response.implementationId}, composing a Remote console.write call`,
      status,
      check_type: "capability_operation",
      trace: response.trace,
      selection: response.selection,
    };
    if (status === "failed") {
      check.observed = `expected ${EXPECTED_TRACE}, got ${traceJson}`;
    }
    checks.push(check);
  } catch (exc) {
    checks.push({
      check_id: "call:1:greeting_render (frontend)",
      description: "greeting_render.render reaches every stage through the frontend's own Bridge",
      status: "failed",
      observed: String(exc && exc.message ? exc.message : exc),
    });
  }

  process.stdout.write(JSON.stringify(checks));
  const failed = checks.some((c) => c.status === "failed");
  process.exit(failed ? 1 : 0);
}

main();
