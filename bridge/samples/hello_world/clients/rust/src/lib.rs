// Reference client for the process executor protocol
// (schemas/process-executor-protocol.schema.json) -- the wire shape a
// process-kind executor (executor_kind: process, 2-RULES.md R4/R5)
// exchanges with the resolved Bridge. Any Rust capability's executor
// depends on this crate (see bridge/samples/hello_world/capabilities/greeting/compose_process
// for the pattern) instead of hand-writing the connect/frame/dispatch
// logic itself -- the same "one shared, reusable way to talk to the
// Bridge" role bridge/bridge.py's Dependencies plays for a Python
// capability that runs in-process.
//
// Lives inside this sample, not under bridge/: it's not part of the
// Bridge implementation (bridge/ is that, and only that -- see
// bridge/MANIFEST.yaml) either way, but it's also not shared,
// ecosystem-level infrastructure -- every consumer of it is a capability
// inside this one sample. A real application copies the shape of this
// client into its own structure, the same way it copies the shape of a
// contract or a capability, rather than depending on hello_world's copy
// -- see clients/python/bridge_client.py for the same role in Python,
// proving this isn't a Rust-specific need.
//
// Uses a real JSON library (serde_json) -- deliberately, not the narrow
// hand-written field extraction an earlier version of this file used.
// That mattered for more than style: input validation is the Bridge's
// job now (2-RULES.md "No silent defaults on what resolution depends
// on"), and a capability can only actually trust that guarantee if this
// client's own parsing is trustworthy too. A real parser is what lets a
// Rust executor write `invocation.input["name"].as_str().expect(...)`
// and mean it, the same way a Python executor can write `input["name"]`
// and mean it.

use serde_json::{json, Value};
use std::env;
use std::io::{BufRead, BufReader, Write};
use std::net::TcpStream;

/// One invocation from the Bridge: its operation name and already-parsed
/// input. `input` is exactly what the Bridge sent -- required fields
/// present, declared types honored, declared defaults already filled in
/// (2-RULES.md "No silent defaults on what resolution depends on") --
/// safe to index into directly for anything the contract declares.
pub struct Invocation {
    pub operation: String,
    pub input: Value,
}

/// The outcome of a failed nested call: the Bridge's `code`/`message`.
/// A capability generally just relays this straight through as its own
/// reply (`Connection::reply_error`).
pub struct CallError {
    pub code: String,
    pub message: String,
}

/// One connection to the Bridge -- one worker in a `ProcessExecutorPool`
/// (bridge/process_executor.py). `connect()` reads `ARPAPED_BRIDGE_PORT`
/// and connects; everything else is one invocation's request/reply cycle.
pub struct Connection {
    reader: BufReader<TcpStream>,
    writer: TcpStream,
}

impl Connection {
    pub fn connect() -> Connection {
        let port = env::var("ARPAPED_BRIDGE_PORT").expect("ARPAPED_BRIDGE_PORT must be set by the Bridge");
        let port: u16 = port.parse().expect("ARPAPED_BRIDGE_PORT must be a port number");
        let stream = TcpStream::connect(("127.0.0.1", port)).expect("failed to connect to the Bridge");
        let writer = stream.try_clone().expect("failed to clone the connection");
        Connection { reader: BufReader::new(stream), writer }
    }

    fn write_value(&mut self, value: &Value) {
        self.writer.write_all(value.to_string().as_bytes()).ok();
        self.writer.write_all(b"\n").ok();
        self.writer.flush().ok();
    }

    fn read_value(&mut self) -> Option<Value> {
        let mut line = String::new();
        match self.reader.read_line(&mut line) {
            Ok(0) => None,
            Ok(_) => serde_json::from_str(&line).ok(),
            Err(_) => None,
        }
    }

    /// Makes one nested call to another capability, resolved through
    /// this implementation's own declared dependencies (R4). Blocks for
    /// exactly one reply before returning -- a worker connection is
    /// exclusively borrowed for one invocation's whole duration, so that
    /// reply can never be confused with a fresh invocation.
    pub fn call(&mut self, capability_id: &str, operation: &str, input: Value) -> Result<Value, CallError> {
        self.write_value(&json!({
            "call": {"capability_id": capability_id, "operation": operation, "input": input}
        }));
        let reply = self.read_value().unwrap_or(Value::Null);
        if let Some(error) = reply.get("error") {
            return Err(CallError {
                code: error.get("code").and_then(Value::as_str).unwrap_or_default().to_string(),
                message: error.get("message").and_then(Value::as_str).unwrap_or_default().to_string(),
            });
        }
        Ok(reply.get("output").cloned().unwrap_or(Value::Null))
    }

    pub fn reply_output(&mut self, output: Value) {
        self.write_value(&json!({"output": output}));
    }

    pub fn reply_error(&mut self, code: &str, message: &str) {
        self.write_value(&json!({"error": {"code": code, "message": message}}));
    }

    /// Runs forever, reading one invocation per line and calling
    /// `handler` with it. The handler must call exactly one of
    /// `reply_output`/`reply_error` before returning. Returns when the
    /// Bridge closes the connection.
    pub fn serve<F: FnMut(&mut Connection, Invocation)>(&mut self, mut handler: F) {
        loop {
            let message = match self.read_value() {
                Some(v) => v,
                None => return,
            };
            let operation = message.get("operation").and_then(Value::as_str).unwrap_or_default().to_string();
            let input = message.get("input").cloned().unwrap_or(Value::Null);
            handler(self, Invocation { operation, input });
        }
    }
}
