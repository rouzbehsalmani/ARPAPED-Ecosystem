# Cross-Language Bridge Test

This branch tests the exact language-independence invariant that must hold at the Bridge boundary.

## Test A — Python Bridge → Rust Capability

`test_python_bridge_rust_capability.py`

- Builds the existing Rust `greeting.compose.process` capability.
- Keeps the production Python Bridge unchanged.
- Rebinds only a temporary copy of the generated catalog to the Rust executable.
- Executes a real `greeting.compose` request through the Python Bridge.
- The Rust capability then performs its declared nested `console.write` call through the same Python Bridge.
- Verifies the normal five-stage Bridge trace and the selected implementation id.

This is the stronger direction because it also crosses the language boundary during a nested dependency call.

## Test B — Rust Bridge → Python Capability

`test_rust_bridge_python_capability.py`

- Uses the small Rust Bridge implementation in `rust_bridge/`.
- Consumes the same catalog information.
- Uses the same process-executor wire protocol defined by `schemas/process-executor-protocol.schema.json`.
- Executes the existing Python `console.write.process` capability.
- The production Python Bridge is not used in this direction.

The Rust Bridge is deliberately a test/reference Bridge, not a replacement for `bridge/bridge.py`. Its purpose is to prove that the execution boundary can be implemented in another language without changing the capability's contract or code.

## Required invariant

The following must remain unchanged across both directions:

`Contract → Manifest/Catalog → Capability Implementation → Process Executor Protocol`

Only the Bridge implementation language changes.

## Run

From repository root:

```text
python bridge/tests/cross_language/test_python_bridge_rust_capability.py
python bridge/tests/cross_language/test_rust_bridge_python_capability.py
```

Rust/Cargo and Python must be available. The Rust capability is compiled before Test A.
