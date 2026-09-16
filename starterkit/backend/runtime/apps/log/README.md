# The `log` app

One app under `runtime/apps/` — this starter kit's own worked example,
proving what every app here needs and nothing more. A second app would
get its own sibling directory here (`runtime/apps/<name>/`), with its own
`dependencies.yaml`/`main.py`, calling the SAME shared
`../requests.py`'s `make_resolver` every app under `apps/` uses —
never a per-app copy of the Bridge-building machinery, and never a
per-app copy of the Bridge engine/catalog either (both live once, at
`runtime/`).

## What this app does

Three real calls through the Bridge: `log.write` (in-process, unpinned —
resolves to the highest-priority policy-allowed candidate), the same
capability again but pinned to an out-of-process C# implementation
(`log.write.process`, proving the process executor protocol is
language-neutral), then starts `web.serve` — a backend API endpoint only,
never static files (the frontend is served separately, its own static
host). See `main.py`'s own docstring for the exact sequence.

## Files

- `dependencies.yaml` — this app's own declared dependencies, keyed by a
  name this app chose, read by `../requests.py`'s `make_resolver` (not
  copied here). Never restated at a call site (`main.py` only ever says
  `resolve("log_write", "write")`, never a
  capability_id/contract_version/implementation_id directly).
- `main.py` — the process entry point (R1): decides nothing, constructs
  no request. Its own top few lines call
  `make_resolver(Path(__file__).resolve().parent)` once, binding the
  shared request-construction point (R6, `../requests.py`) to THIS app's
  own `dependencies.yaml`; everything after that only calls
  `resolve(...)` and the handles it returns.

See `../requests.py`'s own docstring for what it builds and why it lives
one level up, shared, rather than copied into every app.

## Run

From the repository root:
```
python -m starterkit.backend.runtime.apps.log.main
```
See `../../../README.md` ("Run") for the frontend's own half and the two
servers together.
