// Registration-unaware executor for console.write 2.0.0, in Rust instead
// of Python -- proves executor_kind: process end to end (2-RULES.md R4/R5,
// bridge/process_executor.py). Same operation, same contract_version,
// same behavior as ../write_v2/executor.py: reads `message` and optional
// `format` ("plain"/"uppercase"/"prefixed") and prints the formatted
// result. Never imported -- the Bridge spawns this as a separate process
// and talks to it over loopback TCP (see ../../../README.md).
//
// No external crates: this hand-writes just enough of the wire protocol
// to pull a couple of flat string fields out of one JSON line. A real
// capability written in Rust should use a real JSON crate (e.g.
// serde_json) instead -- this narrow parser is scaffolding, scoped
// exactly to the fixed request shape the Bridge sends, and does not
// handle escaped characters within a string value.

use std::env;
use std::io::{BufRead, BufReader, Write};
use std::net::TcpStream;

fn find_string_field(json: &str, key: &str) -> Option<String> {
    let pattern = format!("\"{}\"", key);
    let key_pos = json.find(&pattern)?;
    let after_key = &json[key_pos + pattern.len()..];
    let colon_pos = after_key.find(':')?;
    let after_colon = after_key[colon_pos + 1..].trim_start();
    if !after_colon.starts_with('"') {
        return None;
    }
    let value_start = &after_colon[1..];
    let end = value_start.find('"')?;
    Some(value_start[..end].to_string())
}

fn write_line(writer: &mut impl Write, line: &str) {
    writer.write_all(line.as_bytes()).ok();
    writer.write_all(b"\n").ok();
    writer.flush().ok();
}

fn error_reply(code: &str, message: &str) -> String {
    format!("{{\"error\": {{\"code\": \"{}\", \"message\": \"{}\"}}}}", code, message.replace('"', "'"))
}

fn main() {
    let port = env::var("ARPAPED_BRIDGE_PORT").expect("ARPAPED_BRIDGE_PORT must be set by the Bridge");
    let port: u16 = port.parse().expect("ARPAPED_BRIDGE_PORT must be a port number");
    let stream = TcpStream::connect(("127.0.0.1", port)).expect("failed to connect to the Bridge");
    let mut writer = stream.try_clone().expect("failed to clone the connection");
    let reader = BufReader::new(stream);

    for line in reader.lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => break,
        };
        if line.is_empty() {
            continue;
        }

        let operation = find_string_field(&line, "operation").unwrap_or_default();
        if operation != "write" {
            write_line(&mut writer, &error_reply("UNSUPPORTED_OPERATION", &format!("no such operation: {}", operation)));
            continue;
        }

        let message = match find_string_field(&line, "message") {
            Some(m) => m,
            None => {
                write_line(&mut writer, &error_reply("INVALID_INPUT", "message must be a string"));
                continue;
            }
        };

        let format = find_string_field(&line, "format").unwrap_or_else(|| "plain".to_string());
        let formatted = match format.as_str() {
            "plain" => message.clone(),
            "uppercase" => message.to_uppercase(),
            "prefixed" => format!("[console.write] {}", message),
            other => {
                let msg = format!("format must be one of [\"plain\", \"prefixed\", \"uppercase\"], got \"{}\"", other);
                write_line(&mut writer, &error_reply("INVALID_INPUT", &msg));
                continue;
            }
        };

        println!("{}", formatted);
        std::io::stdout().flush().ok();
        write_line(&mut writer, "{\"output\": {}}");
    }
}
