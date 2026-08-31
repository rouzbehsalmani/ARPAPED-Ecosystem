# Sample: hello world console app

The simplest possible complete, runnable example of the pattern
`0-WALKTHROUGH.md` describes: one capability (`console.write`), a single
request-construction point, and a process entry point that decides nothing —
laid out in the same `contracts/` / `capabilities/<domain>/<operation>/` /
`app/` structure the walkthrough recommends for any real application.

This is scaffolding to prove the wiring, not a feature — copy the shape (the
folder layout, the file order, the fields, the request-construction
pattern), never this domain content, into a real capability.

## Layout

```
contracts/
  console.write.contract.yaml    the capability's contract artifact (schema-valid)
capabilities/
  console/write/
    manifest.yaml                 binds the contract to the executor below
    executor.py                   registration-unaware: given text, writes it to the console
app/
  requests.py                     the single request-construction point (R6) — exposes resolve()
  main.py                         the entry point — decides nothing, resolves once, calls twice
```

`app/main.py` calls `requests.resolve("console.write", "write")` once and
gets back a handle, then calls `.call(...)` on that handle for each request
(discover once, call many times) instead of re-running discovery every time.
Only the discovery stage is cached — policy is still evaluated and a
candidate is still selected and executed fresh on every `call`, through the
same `bridge.handle` every request goes through — and the handle re-checks
its cached candidates' live state on each use (self-healing by
re-discovering if they've all become unusable), so it can never return a
stale result. `Bridge.resolve`/`BoundCapability` (bridge/bridge.py) are what
actually build the request; `app/requests.py` stays the only application
module that reaches the Bridge at all.

## Run

From the repository root:

```
python -m bridge.samples.hello_world.app.main
```

Expected output: `Hello, world!` — printed by the executor, not by `app/main.py`.
