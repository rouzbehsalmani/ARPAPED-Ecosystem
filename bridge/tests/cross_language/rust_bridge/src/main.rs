use serde::Deserialize;
use serde_json::{json, Value};
use std::env;
use std::fs;
use std::io::{BufRead, BufReader, Write};
use std::net::{TcpListener, TcpStream};
use std::process::{Command, Stdio};

#[derive(Debug, Deserialize)]
struct CatalogEntry {
    capability_id: String,
    contract_version: String,
    operation: Vec<String>,
    executor_kind: String,
    executor_path: Vec<String>,
    implementation_id: String,
    enabled: bool,
    healthy: bool,
}

#[derive(Debug, Deserialize)]
struct Request {
    capability_id: String,
    contract_version: String,
    operation: String,
    input: Value,
}

fn catalog_path() -> String {
    env::var("ARPAPED_TEST_CATALOG").expect("ARPAPED_TEST_CATALOG is required")
}

fn validate_request(request: &Request) -> Result<(), String> {
    if request.capability_id.trim().is_empty()
        || request.contract_version.trim().is_empty()
        || request.operation.trim().is_empty()
    {
        return Err("validation failed: required request field is empty".to_string());
    }
    if !request.input.is_object() {
        return Err("validation failed: input must be an object".to_string());
    }
    Ok(())
}

fn discover(request: &Request) -> Result<CatalogEntry, String> {
    let content = fs::read_to_string(catalog_path()).map_err(|e| format!("catalog read failed: {e}"))?;
    for line in content.lines().filter(|line| !line.trim().is_empty()) {
        let entry: CatalogEntry = serde_json::from_str(line)
            .map_err(|e| format!("invalid catalog JSON: {e}"))?;
        if entry.enabled
            && entry.healthy
            && entry.capability_id == request.capability_id
            && entry.contract_version == request.contract_version
            && entry.operation.iter().any(|op| op == &request.operation)
            && entry.executor_kind == "process"
        {
            return Ok(entry);
        }
    }
    Err(format!(
        "no compatible implementation for {} {} {}",
        request.capability_id, request.contract_version, request.operation
    ))
}

fn policy_allows(_entry: &CatalogEntry) -> bool {
    // The test policy is intentionally equivalent to the reference policy's
    // default allow path. The important invariant here is that policy is a
    // separate stage from discovery and execution.
    true
}

fn select(entry: CatalogEntry) -> CatalogEntry {
    // The temporary test catalog contains one eligible implementation. The
    // selector therefore has one deterministic result and introduces no
    // provider-specific decision into the Rust Bridge.
    entry
}

fn serve_one(mut stream: TcpStream, request: &Request) -> Result<Value, String> {
    let policy = json!({"user": {}, "consumer": {}, "ecosystem": {}, "provider": {}, "module": {}});
    let invocation = json!({
        "operation": request.operation,
        "input": request.input,
        "policy": policy
    });
    writeln!(stream, "{}", invocation).map_err(|e| format!("invocation write failed: {e}"))?;
    stream.flush().map_err(|e| format!("flush failed: {e}"))?;

    let mut line = String::new();
    BufReader::new(stream)
        .read_line(&mut line)
        .map_err(|e| format!("reply read failed: {e}"))?;
    if line.trim().is_empty() {
        return Err("executor closed without a reply".to_string());
    }
    let reply: Value = serde_json::from_str(line.trim())
        .map_err(|e| format!("invalid executor reply: {e}"))?;
    if reply.get("error").is_some() {
        return Err(reply.to_string());
    }
    Ok(reply.get("output").cloned().unwrap_or_else(|| json!({})))
}

fn execute(request: &Request, entry: &CatalogEntry) -> Result<Value, String> {
    if entry.executor_path.is_empty() {
        return Err("execution failed: process implementation has an empty executor path".to_string());
    }

    let listener = TcpListener::bind("127.0.0.1:0")
        .map_err(|e| format!("listener bind failed: {e}"))?;
    let port = listener
        .local_addr()
        .map_err(|e| format!("listener address failed: {e}"))?
        .port();

    let mut command = Command::new(&entry.executor_path[0]);
    command.args(&entry.executor_path[1..]);
    command
        .env("ARPAPED_BRIDGE_PORT", port.to_string())
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    let mut child = command
        .spawn()
        .map_err(|e| format!("failed to spawn {}: {e}", entry.implementation_id))?;

    let (stream, _) = listener
        .accept()
        .map_err(|e| format!("executor connection failed: {e}"))?;
    let result = serve_one(stream, request);
    let _ = child.kill();
    let _ = child.wait();
    result
}

fn main() {
    let stdin = std::io::stdin();
    let mut line = String::new();
    stdin.read_line(&mut line).expect("failed to read request");
    let request: Request = serde_json::from_str(line.trim()).expect("invalid request JSON");

    let mut trace: Vec<&str> = Vec::new();
    let result = (|| {
        validate_request(&request)?;
        trace.push("validated");
        let discovered = discover(&request)?;
        trace.push("discovered");
        if !policy_allows(&discovered) {
            return Err("policy denied the selected candidate".to_string());
        }
        trace.push("policy_evaluated");
        let selected = select(discovered);
        trace.push("selected");
        let output = execute(&request, &selected)?;
        trace.push("executed");
        Ok((output, selected.implementation_id))
    })();

    match result {
        Ok((output, implementation_id)) => println!(
            "{}",
            json!({"ok": true, "implementation_id": implementation_id, "output": output, "trace": trace})
        ),
        Err(error) => println!(
            "{}",
            json!({"ok": false, "error": error, "trace": trace})
        ),
    }
}
