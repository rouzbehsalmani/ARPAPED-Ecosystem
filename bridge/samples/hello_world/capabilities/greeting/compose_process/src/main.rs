// Registration-unaware executor for greeting.compose, in Rust instead of
// Python -- proves a process-kind capability can call ANOTHER capability
// through the Bridge (R4/R5), the same mechanism a factory executor gets
// (../compose/executor.py). Never imported -- spawned as a separate
// process, reached over loopback TCP.
//
// Connect/parse/dispatch/nested-call machinery lives in clients/rust/src/lib.rs
// (the bridge_client crate, a path dependency) -- `execute` below is
// this capability's ONLY code, a pure function taking `conn` solely to
// make its own nested call through it. Nothing here writes the
// connect/read/reply loop; that's bridge_client::serve's job, so this
// file would be identical if greeting.compose were ever reachable
// in-process (a Rust Bridge, hypothetically) instead of as its own
// process -- see bridge/samples/hello_world/README.md
// "clients/python/direct_adapter.py" for the same property in Python.

use bridge_client::{serve, CallError, Connection};
use serde_json::{json, Value};

fn execute(_operation: &str, input: Value, conn: &mut Connection) -> Result<Value, CallError> {
    // `name` isn't checked here -- Bridge.handle already validated it
    // (present, string, non-blank via `pattern: "\S"`), so this is a
    // trusting lookup, not a defensive one.
    let name = input["name"]
        .as_str()
        .expect("Bridge guarantees `name` is present, a string, and non-blank");

    // A nested call, resolved through this implementation's own
    // declared dependencies.capabilities (R4) -- console.write isn't
    // imported or spawned by this process itself.
    let text = format!("Greetings, {}!", name);
    conn.call("console.write", "write", json!({"text": text}))?;
    Ok(json!({}))
}

fn main() {
    serve(execute);
}
