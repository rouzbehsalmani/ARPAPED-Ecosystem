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
build_catalog.py                  generates capability-catalog.jsonl (Phase 8, Publish)
capability-catalog.jsonl          generated — see "Capability catalog" below
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

The first call also passes `on_stage`, observing each trace stage live as
the Bridge reaches it instead of only seeing the trace once the call has
returned. This is the same mechanism a verification harness relies on for
bounded, per-stage timeouts (`Bridge.handle_with_timeout`) — a capability
operation that never progresses is a hard failure, detected fast, instead of
an unattended pipeline hanging forever with nobody to notice (2-RULES.md R5).

## Capability catalog

`app/requests.py` registers capabilities from `capability-catalog.jsonl`
instead of walking and re-parsing `capabilities/` at startup — that doesn't
scale once an ecosystem has more than a handful of capabilities (see
2-RULES.md "The Registry contract" and `bridge/assembler.py`). The catalog
is a generated build artifact, committed so the sample runs out of the box.

Regenerate it after editing anything under `capabilities/` or a contract it
references:

```
python -m bridge.samples.hello_world.build_catalog
```

This calls `rebuild_catalog`, which walks the whole tree once — appropriate
here since this sample's tree predates the catalog. A growing ecosystem
publishing capabilities one at a time should call `append_to_catalog`
per newly published manifest instead: O(1) per publish, never re-walking
what's already in the catalog.

## Run

From the repository root:

```
python -m bridge.samples.hello_world.app.main
```

Expected output — two lines, both printed by the executor, never by
`app/main.py`:

```
This is a test of the Bridge's console.write capability.
Hello, world!
```
