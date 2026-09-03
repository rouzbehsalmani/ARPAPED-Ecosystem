// Reference client for the process executor protocol
// (schemas/process-executor-protocol.schema.json) -- what a process-kind
// executor (2-RULES.md R4/R5) exchanges with the Bridge. Any Rust
// executor here depends on this crate instead of hand-writing
// connect/frame/dispatch itself (see ../compose_process for the pattern).
//
// Lives inside this sample, not under bridge/ (not part of the Bridge
// implementation) and not at the repo root (not shared, ecosystem-level
// infrastructure -- every consumer is a capability inside this one
// sample; a real application copies the shape, not this copy). See
// clients/python/bridge_client.py for the same role in Python.
//
// Uses a real JSON library (serde_json), not hand-written field
// extraction -- required for `invocation.input["name"].as_str().expect(...)`
// to actually mean something, the same way `input["name"]` does in Python.

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
