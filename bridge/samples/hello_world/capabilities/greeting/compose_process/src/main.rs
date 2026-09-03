// Registration-unaware executor for greeting.compose, in Rust instead of
// Python -- proves a process-kind capability can call ANOTHER capability
// through the Bridge (R4/R5), the same mechanism a factory executor gets
// (../compose/executor.py). Never imported -- spawned as a separate
// process, reached over loopback TCP.
//
// Connect/parse/dispatch/nested-call machinery lives in clients/rust/src/lib.rs
// (the bridge_client crate, a path dependency); this file is just this
// capability's own operation logic.

use bridge_client::Connection;
use serde_json::json;

fn main() {
    let mut conn = Connection::connect();
    conn.serve(|conn, invocation| {
        // `name` isn't checked here -- Bridge.handle already validated it
        // (present, string, non-blank via `pattern: "\S"`), so this is a
        // trusting lookup, not a defensive one.
        let name = invocation.input["name"]
            .as_str()
            .expect("Bridge guarantees `name` is present, a string, and non-blank");

        // A nested call, resolved through this implementation's own
        // declared dependencies.capabilities (R4) -- console.write isn't
        // imported or spawned by this process itself.
        let text = format!("Greetings, {}!", name);
        match conn.call("console.write", "write", json!({"text": text})) {
            Ok(_) => conn.reply_output(json!({})),
            Err(e) => conn.reply_error(&e.code, &e.message),
        }
    });
}
