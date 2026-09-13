# Starter kit: logging web app — frontend

The JavaScript half of `starterkit` (see `../README.md` for the
whole starter kit, what it proves, and how this half composes with
`../backend/README.md`, the other half). This document covers only this
runtime's own territory: its own contract, capability, Bridge, and how
to serve it standalone against a running backend.

This is a real starting point, meant to be copied — copy the shape (the
folder layout, the file order, the fields, the request-construction
pattern) AND the domain (`client.log` reports a real client-side event
to a real backend capability, `log.write` — see `../README.md` "A real
starter kit"); what's still worth replacing is the implementation body
itself, which is intentionally minimal.

## Layout

Files split into `implementation/` (contract, manifests, build/verify
tooling — never shipped, never needed by a real deployment) and
`runtime/` (the Bridge, the executor, the generated catalog, the entry
page, and the host that serves them — everything a real deployment of
this half actually needs). `../backend/` carries the identical split for
the same reason — see `../backend/README.md`'s own Layout.

```
implementation/                   never read by anything under runtime/ below
  contracts/
    client.log.contract.yaml       this runtime's OWN capability, NOT a second implementation of the backend's
                                    log.write (see the contract's own header) — reports a client-side event,
                                    which log.write itself never needed to know about
  capabilities/
    client/log/manifest.json       depends on log.write BY ID (R4), never on the backend's contract file
    log/write/manifest.json        no `contract` field at all — a Remote-kind pointer to a capability this
                                    runtime doesn't own; nothing here to read, the owning runtime's own
                                    contract is authoritative and its Bridge re-validates on arrival regardless
  build_catalog.py                Python build tool (Node has no built-in YAML) — generates
                                   ../runtime/capability-catalog.jsonl from THIS tree's own contracts/manifests;
                                   also validates them against their schemas, this runtime's OWN build step
  tests/verify.js                 this runtime's own headless verification (Node) — run by the backend's harness
runtime/                          everything a real deployment of this half needs — both what a client
                                   fetches AND the host that serves it (see "Run"); separate from the
                                   backend's web.serve (../README.md "Two servers, not one")
  host/
    serve.py                        the process you actually run to deploy this half — NOT itself fetched by a
                                     client, unlike everything else below; see "Run" for why it isn't a bare
                                     `python -m http.server`
  bridge/                         this runtime's own Bridge — a faithful port of the same architecture
    core.js                        Bridge Core: validate -> discover -> policy -> select -> execute, same five-stage trace
    remote_client.js               executor_kind: remote's reference client — speaks bridge-protocol.schema.json directly
    assembler.js                   reads capability-catalog.jsonl, registers each implementation
    MANIFEST.yaml                  authoritative descriptor, mirrors the backend's own style
  capabilities/client/log/executor.js   the ONLY file this capability ships — no manifest.json here
  capability-catalog.jsonl        generated — the ONE thing assembleFromCatalog reads at page load
  app.js                          the Bridge Adapter — this runtime's single request-construction point
  index.html                      the page a real client loads; imports app.js as an ES module
```

`host/serve.py` lives under `runtime/`, not `implementation/`, despite looking like build/dev tooling: `implementation/` is defined as "never shipped, never needed by a real deployment" — and that's exactly wrong for this file, since an actual deployment of this frontend DOES need something serving the rest of `runtime/` over HTTP. It sits in its own `host/` subfolder rather than flat alongside `index.html`/`app.js`/etc. specifically because it plays a different role from those: it's never itself fetched by a browser, it's what makes everything else in `runtime/` fetchable in the first place.

`client.log` runs **Local** in this runtime's own Bridge Core and
declares `log.write` as a dependency, pinned `>=1.0.0,<2.0.0` by ITS OWN
contract — a capability it doesn't own and never copies the contract of.
This runtime's own registry has no local implementation of
`log.write` at all, only a manifest entry with `executor_kind:
remote`, naming `/bridge` — and that entry doesn't even reference a
contract file (nothing to read: the owning runtime, the backend, is the
one authority for its own shape). Resolving it makes a real HTTP POST to
the backend's `web.serve` capability, shaped by
`starterkit/schemas/bridge-protocol.schema.json` (the same shape any
consumer's Bridge call already uses — R4: a Remote call reaches a whole
separate Bridge, which needs the full request shape to run its own
discovery/policy/selection, not just an `execute(operation, input,
policy)` triple). `web.serve` dispatches to `log.write` through the
REAL backend Bridge and returns its real trace — see `../README.md` "The
web app in one paragraph" for the full cross-boundary story.

## Real ES modules, not Node standing in for a browser

Everything under `runtime/` is genuine browser-compatible JavaScript —
`import`/`export`, `fetch()`, and dynamic `import()` — never `require()`
or `fs.readFileSync`, which only Node has. `package.json` sets
`{"type": "module"}` so Node itself also treats these files as ESM (used
only by the headless test harness, `implementation/tests/verify.js`,
never by a real deployment).

`bridge/assembler.js`'s `assembleFromCatalog` takes two separate base
URLs, never one conflated `baseUrl` (backend and frontend are served
separately — `../README.md` "Two servers, not one" — so they are never
the same origin by design):
- `selfBaseUrl` locates THIS runtime's own assets — the catalog itself
  and any Local (factory/direct) executor module. `""` (relative to the
  current page) in a real browser, since wherever this page was loaded
  from also serves its own `capability-catalog.jsonl`; an explicit URL
  only for Node, which has no page origin to be relative to.
- `backendBaseUrl` locates the REMOTE backend's `web.serve` — used ONLY
  for `executor_kind: remote` entries. Always explicit; there is no
  same-origin case for it, since the backend is never this runtime's own
  origin.

Loading a LOCAL executor module is the one place Node and a browser
genuinely differ: a real browser's native `import()` resolves an
http(s) URL directly, but Node's does not (no
`--experimental-network-imports` in general availability) — so
`assembleFromCatalog`'s `importer` parameter exists ONLY to let the
Node-based test harness substitute a local `file://` import for that one
step; its default IS the real browser behavior
(`(specifier) => import(specifier)`), never overridden in production
use.

## Capability catalog

`app.js` assembles this runtime's Bridge Core from
`runtime/capability-catalog.jsonl`, fetched at page load — never by
walking `capabilities/` directly (mirrors the backend's own Registry
discipline, see `../backend/README.md` "Capability catalog"). The
catalog is a generated build artifact, gitignored like every other
generated `state/`-style output (`.gitignore`) — run the command below
once before this starter kit's first use, and again after any capability
change.

Regenerate it after editing anything under `implementation/capabilities/`
or the contract it references:

```
python -m starterkit.frontend.implementation.build_catalog
```

## Run

`../backend/README.md` "Run" must already be running (its API, at
`http://127.0.0.1:8420` by default) before this half is useful — this
runtime's own `log.write` dependency is Remote, reached only by
calling that API.

Serve this runtime's own static files with any static file server. From
the repository root:

```
python -m starterkit.frontend.runtime.host.serve
```

Not a bare `python -m http.server`: Python's `http.server` derives
`Content-Type` from the `mimetypes` module, which on Windows reads the OS
registry first — and many Windows installs map `.js` to `text/plain`
there. A browser refuses to execute a `<script type="module">` served
with a non-JavaScript Content-Type ("Failed to load module script ...
text/plain") — index.html itself loads fine, but every `import` inside it
silently fails, and even index.html's own assembly try/catch never runs,
because the script never started. `runtime/host/serve.py` is a small
wrapper around the same stdlib `SimpleHTTPRequestHandler` that forces the
correct type for the extensions this runtime actually uses, so `python -m
...` "just works" the same way on every platform. (Any other static file
server — nginx, `npx serve`, etc. — already sets correct types itself and
works too; this wrapper exists only so the stdlib one-liner does.)

Note this is exactly the class of bug the harness below (Gate 19) does
NOT catch: the Node-based check never fetches a `.js` file over HTTP at
all (`nodeImporter` imports the local file directly via a `file://` URL),
so it cannot observe a wrong Content-Type header — that failure mode only
exists for a real browser loading real HTTP responses. 10/10 passing
proves the Bridge assembles and executes correctly; it does not prove a
browser can load the page, which is a static-hosting concern (see
`../README.md` "Two servers, not one") the Blueprint deliberately doesn't
model as a capability, and this harness inherits that same boundary.

### Run (agent-driven / automated)

`python -m starterkit.frontend.runtime.host.serve` never returns
on its own either (same as `../backend/README.md` "Run (agent-driven /
automated)" — it's a real server, `serve_forever()`, waiting until
killed). An agent starting it to test against, then continuing other
work, must use `process_supervisor` (`blueprint/dep/MANIFEST.yaml:
process_supervisor`), never wait on the bare command directly — the same
"healthy process mistaken for a hang" trap as the backend, just on port
8421 instead of 8420, and the same built-in protection against a stale,
untracked orphan already squatting that port (see the backend section
and `process_supervisor.py`'s own docstring):

```python
from pathlib import Path
from blueprint.dep import process_supervisor

pidfile = Path("starterkit/frontend/state/frontend.pid")
process_supervisor.start(
    ["python", "-m", "starterkit.frontend.runtime.host.serve"],
    pidfile=pidfile,
    ready_check=process_supervisor.tcp_ready_check("127.0.0.1", 8421),
)
# ... test against it ...
process_supervisor.stop(pidfile)
```

Start the backend the same way first (its own README section) — this
runtime's `log.write` dependency is Remote and needs it up.

Then open `http://127.0.0.1:8421`. The page (`runtime/index.html`) runs
its OWN Bridge Core, entirely in your browser's JavaScript — not a
simulation, the actual `runtime/bridge/core.js` described above. It has
a "Backend API base URL" field, defaulting to `http://127.0.0.1:8420`;
adjust it if you started the API on a different port. Type a message,
pick a level, click **Log**: `client.log` executes **Local**, right
there in the page, and its `log.write` dependency makes a real
cross-origin HTTP POST to the backend's `/bridge` endpoint — watch the
terminal running the backend's `main.py`; that's where the text actually
gets printed, by the backend's own `log.write`, proving the round trip
is real and not two independent halves that happen to sit next to each
other.

Everything the static server above serves to a client (`index.html`,
`app.js`, `bridge/*.js`, `capabilities/client/log/executor.js`,
`capability-catalog.jsonl`) is under `runtime/` — that directory, not
this whole `frontend/` tree, so `implementation/` (the contract,
manifests, `build_catalog.py`) is never reachable over HTTP; open your
browser's Network tab and there is nothing to find there. `runtime/host/`
is the one exception worth naming: it's also under `runtime/` (because a
real deployment needs it to run, unlike `implementation/`), but it's
never itself requested by a browser — nothing in `index.html` or `app.js`
references it, the same way nothing in a served page ever references the
process manager running its own server.

`implementation/tests/verify.js` is this runtime's own headless
verification (Node, not a browser) — it is not run directly; the
backend's own harness (`../backend/implementation/tests/verify/verify.py`)
starts both a real backend API and a separate test-only static server
for `runtime/`, then shells out to it with both URLs and folds its
check into the same verification record (blueprint/1-CYCLE.md Gate 19).

## Runtime events

This runtime's own Bridge Core (`bridge/core.js`) records the same kind
of runtime event the backend's Bridge does (`../backend/README.md`
"Runtime events", `blueprint/dep/MANIFEST.yaml: runtime_log`) — one per
real call, success or failure, including a nested call (`client.log`
composing `log.write` as `executor_kind: remote`) as its own
independent event, not just the top-level one a script happens to make.
`core.js` itself never imports anything Node-specific to do this — a
real browser has no filesystem, so it only ever calls an `eventSink`
callback if one was given; persisting it is entirely the caller's
decision. `index.html` (a real browser) passes none. `implementation/tests/verify.js`
(the Node-based harness) passes a real one, writing
`state/runtime-events.jsonl` — proven for real: running the full harness
produces schema-valid events here (`blueprint/schemas/runtime-event.schema.json`,
the SAME schema the backend's own events validate against) for both the
`client.log` call and its nested `log.write` one, while the
backend's own `state/runtime-events.jsonl` independently records ITS
side of that same distributed call (a real incoming HTTP request) —
two different vantage points of one real interaction, neither guessing
at what the other saw.
