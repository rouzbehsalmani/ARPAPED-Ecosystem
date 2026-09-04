const fs = require("fs");
const net = require("net");
const { spawn } = require("child_process");

function fail(message, trace) {
  process.stdout.write(JSON.stringify({ ok: false, error: message, trace }) + "\n");
  process.exitCode = 1;
}

function validate(request, trace) {
  if (!request.capability_id || !request.contract_version || !request.operation) {
    throw new Error("validation failed: required request field is empty");
  }
  if (!request.input || typeof request.input !== "object" || Array.isArray(request.input)) {
    throw new Error("validation failed: input must be an object");
  }
  trace.push("validated");
}

function discover(request, trace) {
  const path = process.env.ARPAPED_TEST_CATALOG;
  if (!path) throw new Error("ARPAPED_TEST_CATALOG is required");
  const entries = fs.readFileSync(path, "utf8")
    .split(/\r?\n/)
    .filter(Boolean)
    .map(line => JSON.parse(line));
  const entry = entries.find(e =>
    e.enabled === true &&
    e.healthy === true &&
    e.capability_id === request.capability_id &&
    e.contract_version === request.contract_version &&
    Array.isArray(e.operation) && e.operation.includes(request.operation) &&
    e.executor_kind === "process"
  );
  if (!entry) throw new Error(`no compatible implementation for ${request.capability_id} ${request.contract_version} ${request.operation}`);
  trace.push("discovered");
  return entry;
}

function execute(request, entry, trace) {
  return new Promise((resolve, reject) => {
    if (!Array.isArray(entry.executor_path) || entry.executor_path.length === 0) {
      reject(new Error("execution failed: process implementation has an empty executor path"));
      return;
    }

    let child = null;
    let socket = null;
    let settled = false;
    const server = net.createServer(client => {
      socket = client;
      const invocation = {
        operation: request.operation,
        input: request.input,
        policy: { user: {}, consumer: {}, ecosystem: {}, provider: {}, module: {} }
      };
      client.write(JSON.stringify(invocation) + "\n");
      let data = "";
      client.on("data", chunk => {
        data += chunk.toString();
        const newline = data.indexOf("\n");
        if (newline === -1 || settled) return;
        try {
          const reply = JSON.parse(data.slice(0, newline).trim());
          settled = true;
          if (reply.error) reject(new Error(JSON.stringify(reply)));
          else resolve(reply.output || {});
        } catch (error) {
          settled = true;
          reject(error);
        } finally {
          client.destroy();
          if (server.listening) server.close();
          if (child && !child.killed) child.kill();
        }
      });
      client.on("error", error => {
        if (settled) return;
        settled = true;
        reject(error);
        if (server.listening) server.close();
        if (child && !child.killed) child.kill();
      });
    });

    const cleanup = () => {
      if (socket && !socket.destroyed) socket.destroy();
      if (server.listening) server.close();
      if (child && !child.killed) child.kill();
    };

    server.listen(0, "127.0.0.1", () => {
      const port = server.address().port;
      child = spawn(entry.executor_path[0], entry.executor_path.slice(1), {
        env: { ...process.env, ARPAPED_BRIDGE_PORT: String(port) },
        stdio: ["ignore", "pipe", "pipe"]
      });
      child.on("error", err => {
        if (settled) return;
        settled = true;
        cleanup();
        reject(new Error(`failed to spawn ${entry.implementation_id}: ${err.message}`));
      });
      child.on("exit", code => {
        if (!settled && code !== null && code !== 0) {
          settled = true;
          cleanup();
          reject(new Error(`executor exited with code ${code}`));
        }
      });
    });
    server.on("error", error => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(error);
    });
  });
}

async function main() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  const request = JSON.parse(Buffer.concat(chunks).toString("utf8").trim());
  const trace = [];
  try {
    validate(request, trace);
    const discovered = discover(request, trace);
    trace.push("policy_evaluated");
    const selected = discovered;
    trace.push("selected");
    const output = await execute(request, selected, trace);
    trace.push("executed");
    process.stdout.write(JSON.stringify({ ok: true, implementation_id: selected.implementation_id, output, trace }) + "\n");
  } catch (error) {
    fail(error.message, trace);
  }
}

main();
