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

fn load_entry(request: &Request) -> Result<CatalogEntry, String> {
    let content = fs::read_to_string(catalog_path()).map_err(|e| format!("catalog read failed: {e}"))?;
    for line in content.lines().filter(|line| !line.trim().is_empty()) {
        let entry: CatalogEntry = serde_json::from_str(line)
            .map_err(|e| format!("invalid catalog JSON: {e}"))?;
        if entry.capability_id == request.capability_id
            && entry.contract_version == request.contract_version
            && entry.operation.iter().any(|op| op == &request.operation)
            && entry.executor_kind == "process"
        {
            return Ok(entry);
        }
    }
    Err(format!(
        "no process implementation for {} {} {}",
        request.capability_id, request.contract_version, request.operation
    ))
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
        return Err("process implementation has an empty executor path".to_string());
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

    match load_entry(&request).and_then(|entry| execute(&request, &entry)) {
        Ok(output) => println!("{}", json!({"ok": true, "output": output})),
        Err(error) => println!("{}", json!({"ok": false, "error": error})),
    }
}
