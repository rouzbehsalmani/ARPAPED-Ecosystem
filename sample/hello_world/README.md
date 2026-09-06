# Sample: hello world web app

The simplest possible complete, runnable example of two things at once:
the pattern `blueprint/0-WALKTHROUGH.md` describes (contract → manifest →
executor → Bridge, one request-construction point, an entry point that
decides nothing), and the per-runtime Bridge principle in
`blueprint/2-RULES.md` (Bridge / Bridge Core / Bridge Adapter glossary, R4
Local/Worker/Remote) — a Python **backend** and a genuine JavaScript
**frontend**, each with its own resolved Bridge, proven by composing a
capability across both.

This is scaffolding to prove the wiring, not a feature — copy the shape (the
folder layout, the file order, the fields, the request-construction
pattern), never this domain content, into a real capability.

This document covers only what spans both runtimes — what neither side
owns alone. Everything backend-specific lives in
[`backend/README.md`](backend/README.md); everything frontend-specific
lives in [`frontend/README.md`](frontend/README.md). Each of those is
self-contained for its own runtime, the same territory split the code
itself keeps (`backend/`, `frontend/`, each further split into
`implementation/`/`runtime/` — see either README's own Layout section).

## The web app in one paragraph

`backend/` and `frontend/` each own their OWN contracts — `greeting.render`
(frontend) is NOT a second implementation of `greeting.compose` (backend);
they look similar ("make a greeting for a name") because this sample keeps
its toy domain small, but they're genuinely different capabilities, with
different owners and different output shapes (`greeting.render` returns
the composed text for display; `greeting.compose` doesn't need to). What
crosses the runtime boundary is a plain reference by capability ID, never a
shared contract file: `greeting.render` runs **Local** in the frontend's
own Bridge Core and declares `console.write` as a dependency, pinned
`<2.0.0` by ITS OWN contract — a capability it doesn't own and never
copies the contract of. The frontend's own registry has no local
implementation of `console.write` at all, only a manifest entry with
`executor_kind: remote`, naming `/bridge` — and that entry doesn't even
reference a contract file (nothing to read: the owning runtime, backend,
is the one authority for its own shape). Resolving it makes a real HTTP
POST to the backend's `web.serve` capability, shaped by
`sample/schemas/bridge-protocol.schema.json` (the same shape any
consumer's Bridge call already uses — R4: a Remote call reaches a whole
separate Bridge, which needs the full request shape to run its own
discovery/policy/selection, not just an `execute(operation, input, policy)`
triple). `web.serve` dispatches to `console.write` through the REAL
backend Bridge and returns its real trace. Two runtimes, two Bridges, two
independently-owned contracts, one call composed across the boundary by ID
— verified end to end by `backend/implementation/tests/verify/verify.py`, which shells
out to `frontend/implementation/tests/verify.js` (Node, headless) and folds its check
into the SAME verification record (Gate 19: the shipped frontend's own
Bridge path must be exercised, not just the backend capability in
isolation).

See [`backend/README.md`](backend/README.md) for `console.write`'s and
`greeting.compose`'s own layout, versions, and out-of-process
implementations, and [`frontend/README.md`](frontend/README.md) for
`greeting.render`'s own layout and why its code is genuine
browser-compatible JavaScript, not Node pseudocode.

## Two servers, not one

Backend and frontend are served SEPARATELY, on two different origins —
not one process wearing two hats:

```
python -m sample.hello_world.backend.runtime.app.main
```

starts the backend's `web.serve` — an **API endpoint only** (`/bridge`
and `/health`), never a static file server. Separately:

```
python -m sample.hello_world.frontend.runtime.host.serve
```

serves the frontend, then open `http://127.0.0.1:8421` in a browser (a
small wrapper around the stdlib static server, not a bare `python -m
http.server` — see `frontend/README.md` "Run" for why: a Windows-only
`mimetypes` quirk otherwise serves `.js` files with the wrong
Content-Type and browsers silently refuse to run them). See
[`backend/README.md`](backend/README.md#run) and
[`frontend/README.md`](frontend/README.md#run) for each command's full
context (build steps, expected output, how to point the page at a
non-default backend port).

`web.serve` never gained a `static_root` option: nothing can resolve a
capability through a Bridge before the hosting page has already loaded,
so "serve this page" can never itself be reached through the Bridge it
exists to bootstrap (the same reason nothing here models the process
manager that runs the backend). Static hosting is a deployment concern
the Blueprint doesn't model as a capability at all — see the header
comment in `backend/implementation/contracts/web.serve.contract.yaml`.

The verification harness (`backend/implementation/tests/verify/verify.py`)
mirrors this exact two-server topology for its own frontend check: it
starts the real `web.serve` (API only) AND a separate, test-only static
server for `frontend/runtime/` (plain `http.server`, not a capability —
serving the test's own static assets is scaffolding for the test, same as
the harness itself is scaffolding for the sample), then runs
`frontend/implementation/tests/verify.js` against both URLs.
