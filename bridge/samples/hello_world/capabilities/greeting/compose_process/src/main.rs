// Registration-unaware executor for greeting.compose, in Rust instead of
// Python -- proves a process-kind capability can call ANOTHER capability
// through the Bridge (2-RULES.md R4/R5), the same declared-dependency
// mechanism an executor_kind: factory implementation gets
// (../compose/executor.py). Never imported -- the Bridge spawns this as
// a separate process and talks to it over loopback TCP.
//
// All of the Bridge-talking machinery (connect, real JSON parse/serialize,
// read/dispatch invocations, make a nested call) lives in the shared
// reference client, not here -- see clients/rust/src/lib.rs (the
// `bridge_client` crate, depended on via the path dependency in
// Cargo.toml). This file is just this capability's own operation logic.

use bridge_client::Connection;
use serde_json::json;

fn main() {
    let mut conn = Connection::connect();
    conn.serve(|conn, invocation| {
        // Nothing about `name` is checked here at all -- Bridge.handle
        // already validated it against the contract's declared shape
        // before this process was ever sent the invocation (2-RULES.md
        // "No silent defaults on what resolution depends on"): present,
        // a string, and (via the contract's `pattern: "\S"`, not
        // `minLength` -- a whitespace-only string has nonzero length)
        // actually non-blank. All generic, structural constraints, so
        // trusted directly here, the same way a Python executor trusts
        // `input["name"]`. `.expect` turns a genuine violation of that
        // guarantee into a clear panic, not a defensive check for a case
        // that isn't actually reachable.
        let name = invocation.input["name"]
            .as_str()
            .expect("Bridge guarantees `name` is present, a string, and non-blank");

        // A nested call, not the terminal reply: resolved by the Bridge
        // through this implementation's own declared dependencies
        // (dependencies.capabilities in ../../../contracts/greeting.compose.contract.yaml,
        // shared with ../compose/executor.py's Python implementation) --
        // console.write is not imported or spawned by this process itself.
        let text = format!("Greetings, {}!", name);
        match conn.call("console.write", "write", json!({"text": text})) {
            Ok(_) => conn.reply_output(json!({})),
            Err(e) => conn.reply_error(&e.code, &e.message),
        }
    });
}
