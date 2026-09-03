"""Process entry point (R1): decides nothing, constructs no request --
resolves through app/requests.py and calls the handle it returns.

Six calls, each resolved by a declared name (app/dependencies.yaml),
never a restated contract_version/implementation_id:
  1-2. console_write (>=2.0.0 -> console.write.v2) -- plain, then
       `format: "uppercase"`, a 2.0.0-only option.
  3. greeting_compose (1.0.0) -- its factory executor makes a nested
     Bridge call to console.write (R4), not a shortcut.
  4. console_write_legacy (<2.0.0 -> console.write.default) -- proves
     1.0.0 is still alive alongside 2.0.0 (2-RULES.md R2).
  5. greeting_compose_process -- same nested-call mechanism as #3, from
     an out-of-process implementation (executor_kind: process, written
     in Rust for this example; named for that, not the language).
  6. console_write_process -- console.write 2.0.0 again, from a second
     out-of-process implementation (Python this time), over the same
     protocol #5 uses -- proves the protocol isn't a non-Python escape
     hatch.

Run from the repository root (build the Rust executor first -- see
capabilities/greeting/compose_process/manifest.yaml):
    python -m bridge.samples.hello_world.app.main
"""

from bridge.samples.hello_world.app.requests import resolve


def main():
    writer = resolve("console_write", "write")
    writer.call({"message": "This is a test of the Bridge's console.write capability."})
    writer.call({"message": "Hello, world!", "format": "uppercase"})

    composer = resolve("greeting_compose", "compose")
    composer.call({"name": "ARPAPED"})

    writer_v1 = resolve("console_write_legacy", "write")
    writer_v1.call({"text": "console.write 1.0.0 is real and independently callable."})

    composer_process = resolve("greeting_compose_process", "compose")
    composer_process.call({"name": "ARPAPED (via Rust)"})

    writer_process = resolve("console_write_process", "write")
    writer_process.call({"message": "This line is printed by a second Python process, through the Bridge."})


if __name__ == "__main__":
    main()
