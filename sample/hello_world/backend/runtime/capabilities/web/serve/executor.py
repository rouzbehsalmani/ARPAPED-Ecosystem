"""Executor factory for web.serve (../../../../implementation/contracts/web.serve.contract.yaml).

executor_kind: factory -- make_executor is called once, at assembly time,
with a Dependencies scoped to dependencies.capabilities (console.write,
R4). start()/stop() run an in-process HTTP server (ThreadingHTTPServer,
one instance per made executor -- an application only ever composes one)
that answers ONLY POST /bridge, with
sample/schemas/bridge-protocol.schema.json's request/response/error shape
-- the executor_kind: remote wire format (blueprint/2-RULES.md R4) --
dispatching ONLY to console.write (its one declared dependency) via the
same nested-call mechanism greeting.compose's factory executor already
uses (Dependencies never imports the Bridge directly). An API endpoint
only -- no static file serving; the frontend is hosted separately (see
../../../../../README.md "Two servers, not one").

Verified to have actually started before start() returns (R5 gate 6):
binds the socket synchronously, then confirms with a real HTTP request to
its own /health route before replying with the URL.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError
from urllib.request import urlopen

from sample.hello_world.backend.runtime.bridge.bridge import BridgeError
from sample.hello_world.backend.runtime.bridge.policy import PolicyContext


def make_executor(dependencies):
    state: dict[str, object] = {"server": None}

    def _send_json(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # noqa: A002 -- keep test output clean
            pass

        def do_OPTIONS(self) -> None:  # CORS preflight -- backend and frontend are different origins
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self) -> None:
            if self.path == "/health":
                _send_json(self, 200, {"status": "ok"})
                return
            self.send_error(404)

        def do_POST(self) -> None:
            if self.path != "/bridge":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                _send_json(self, 400, {"code": "BRIDGE_INVALID_REQUEST", "stage": "validation", "message": "Malformed JSON body", "details": None})
                return

            capability_id = body.get("capability_id")
            operation = body.get("operation")
            request_id = body.get("request_id", "")
            incoming_policy = body.get("policy_context") or {}

            try:
                handle = dependencies.resolve(capability_id, operation)
                policy_context = PolicyContext(
                    user=incoming_policy.get("user", {}),
                    consumer=incoming_policy.get("consumer", {}),
                    ecosystem=incoming_policy.get("ecosystem", {}),
                    provider=incoming_policy.get("provider", {}),
                    module=incoming_policy.get("module", {}),
                )
                response = handle.call_with_timeout(
                    body.get("input", {}), policy_context=policy_context, stage_timeout=10.0,
                )
                _send_json(self, 200, {
                    "request_id": request_id,
                    "capability_id": capability_id,
                    "contract_version": body.get("contract_version", ""),
                    "implementation_id": response.implementation_id,
                    "output": response.output,
                    "trace": list(response.trace),
                })
            except BridgeError as exc:
                _send_json(self, 200, {"code": exc.code, "stage": exc.stage, "message": exc.message, "details": exc.details})
            except Exception as exc:  # pragma: no cover -- defensive, never a bare 500
                _send_json(self, 200, {"code": "BRIDGE_EXECUTION_FAILED", "stage": "execution", "message": str(exc), "details": None})

    def execute(operation, input, policy):
        if operation == "start":
            if state["server"] is not None:
                raise BridgeError("ALREADY_RUNNING", "execution", "web.serve.start called while a server is already running")
            host = input.get("host", "127.0.0.1")
            port = input.get("port", 0)
            server = ThreadingHTTPServer((host, port), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            actual_port = server.server_address[1]
            url = f"http://{host}:{actual_port}"
            try:
                with urlopen(f"{url}/health", timeout=5.0) as resp:
                    if resp.status != 200:
                        raise RuntimeError(f"web.serve health check returned {resp.status}")
            except URLError as exc:
                server.shutdown()
                server.server_close()
                raise RuntimeError(f"web.serve failed to become reachable: {exc}") from exc
            state["server"] = server
            return {"url": url}

        if operation == "stop":
            server = state["server"]
            if server is not None:
                server.shutdown()
                server.server_close()
                state["server"] = None
            return {}

        raise BridgeError("BRIDGE_UNSUPPORTED_OPERATION", "execution", f"unsupported operation: {operation}")

    return execute
