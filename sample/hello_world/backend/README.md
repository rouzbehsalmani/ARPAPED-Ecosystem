# Sample: hello world web app — backend

The Python half of `sample/hello_world` (see `../README.md` for the
whole sample, what it proves, and how this half composes with
`../frontend/README.md`, the other half). This document covers only
this runtime's own territory: its contracts, capabilities, Bridge, and
how to run it standalone.

This is scaffolding to prove the wiring, not a feature — copy the shape (the
folder layout, the file order, the fields, the request-construction
pattern), never this domain content, into a real capability.

## Layout

Files split into `implementation/` (contracts, manifests, build/verify
tooling — never shipped, never read by anything under `runtime/`) and
`runtime/` (the Bridge, executors, the generated catalog, the entry
point — the only thing a real deployment ever needs). A manifest and its
executor were always related by reference, not physical adjacency (a
manifest's `executor:` field is a path/module string, same as it
references a contract by path) — this split is that same principle
carried one step further, not a new exception to R3's co-location rule
(co-located in the same OWNING PACKAGE, i.e. this one sample, not
necessarily the same directory). `../frontend/` carries the identical
split for the same reason — see `../frontend/README.md`'s own Layout.

```
implementation/                   never read by anything under runtime/ below
  contracts/                      this runtime's OWN contracts — not shared with ../frontend/implementation/contracts/;
                                   two agents can work their own territory without touching the other's files
    console.write.contract.yaml     versions 1.0.0 and 2.0.0, both alive peers
    greeting.compose.contract.yaml  declares console.write as a dependency (<2.0.0)
    web.serve.contract.yaml         also declares console.write as a dependency
  capabilities/                   manifest.yaml per implementation — see "Capability-to-capability calls" etc.
  clients/rust/                   Cargo library crate SOURCE — compiled once, the binary ships in runtime/, not this
  build_catalog.py                generates ../runtime/capability-catalog.jsonl (Phase 8, Publish)
  tests/verify/verify.py          the harness — both runtimes' checks, one verification record
runtime/                          everything a real deployment needs; nothing here reads implementation/
  bridge/                         this runtime's own Bridge (pre-existing)
    bridge.py, registry.py, policy.py, selector.py, assembler.py, process_executor.py
    MANIFEST.yaml                  authoritative descriptor, this runtime's own
  capabilities/                   executor.py per implementation ONLY — no manifest.yaml here
    greeting/compose_process/target/  the COMPILED Rust binary — its source lives in implementation/, not here
  capability-catalog.jsonl        generated — the ONE thing assemble_from_catalog reads at process startup
  app/
    dependencies.yaml, requests.py, main.py
  clients/python/                 bridge_client.py, direct_adapter.py — runtime dependencies of process-kind executors
```

The two process-kind executors below don't hand-write their own
connect/frame/dispatch logic -- they depend on a reference client from
this runtime's own `clients/` directories (not part of `runtime/bridge/`;
see "A capability in another language"): `implementation/clients/rust/`
(a Cargo library crate, SOURCE, depended on via a path dependency -- only
needed to compile the Rust executor, never at runtime) and
`runtime/clients/python/bridge_client.py` (needed at runtime -- the
Python process-kind executor imports it directly), both implementing
`sample/schemas/process-executor-protocol.schema.json`. Each `clients/`
lives inside this runtime's own tree, not at the repo root, because
every consumer of it is a capability inside this one sample — it's
scaffolding to copy the shape of, not shared infrastructure a real
application would depend on.

`runtime/app/main.py` calls `requests.resolve("console_write", "write")` once and
gets back a handle, then calls `.call(...)` on that handle for each request
(discover once, call many times) instead of re-running discovery every
time. Neither `contract_version` nor `implementation_id` is passed at the
call site — `resolve` reads both from the named entry in
`runtime/app/dependencies.yaml`. Unlike a capability contract's own
`dependencies.capabilities` (keyed by capability_id, one entry per
capability), this file is keyed by a name the app chooses, so the same
capability_id (`console.write`) can be declared more than once under
different names, each pinned differently for a different purpose — see
`console_write` vs. `console_write_legacy`, below. A
name that isn't declared raises `BRIDGE_UNDECLARED_DEPENDENCY`; a declared
entry missing `contract_version` fails just as loudly, at load time —
there is no silent default anywhere in this chain (`runtime/app/dependencies.yaml`,
`runtime/app/requests.py`, `Bridge.resolve`). Only the discovery stage is cached —
policy is still evaluated and a candidate is still selected and executed
fresh on every `call`, through the same `bridge.handle` every request goes
through — and the handle re-checks its cached candidates' live state on
each use (self-healing by re-discovering if they've all become unusable),
so it can never return a stale result. `Bridge.resolve`/`BoundCapability`
(`runtime/bridge/bridge.py`) are what actually build the request; `runtime/app/requests.py`
stays the only application module that reaches the Bridge at all.

## What every executor here does NOT check, and why

None of the executors under `runtime/capabilities/` check the operation name —
`if operation != "write": ...` can never actually fire: discovery only
ever calls an executor with an operation it declared in the first place,
so that check would be dead code, not a safeguard.

None of them check their input's required-ness or basic type either
(e.g. `isinstance(message, str)`) — `Bridge.handle` (`runtime/bridge/bridge.py`)
validates a request's `input` against the resolved implementation's
contract-declared shape (`sample/schemas/component-contract.schema.json`'s
`input[].type`/`required`) before any executor runs, uniformly, for
direct, factory, and process-kind implementations alike, in any
language.

Nor do `console.write.v2`/`console.write.process` default
`format` themselves any more — `input.get("format", "plain")` used to
live in each executor separately; now `implementation/contracts/console.write.contract.yaml`
declares `default: plain` once, on the field itself, and `Bridge.handle`
fills it in before either executor runs, so both can just write
`input["format"]`. A default is a static fact about the field, the same
kind of thing `type`/`required` already are, so it belongs in the same
place they do.

Two checks that looked at first like genuine business logic turned out
not to be, and moved too: `console.write.v2`/`console.write.process`'s
`format` must be one of a fixed set of strings, and `greeting.compose`'s
`name` must actually have content, not just be a string. Neither
requires understanding what this capability does — "one of a fixed set
of values" is JSON Schema's `enum`, and "not blank" is JSON Schema's
`pattern` (`minLength` alone isn't enough: a whitespace-only string has
nonzero length, so `implementation/contracts/greeting.compose.contract.yaml` declares
`pattern: "\S"` — at least one non-whitespace character — not
`minLength: 1`). `implementation/contracts/console.write.contract.yaml`'s `format`
declares `enum: [plain, uppercase, prefixed]`. Both are checked by the
Bridge the same way `type`/`required`/`default` already are, so
`runtime/capabilities/console/write_v2/executor.py`, `runtime/capabilities/console/write_process/executor.py`,
`runtime/capabilities/greeting/compose/executor.py`, and
`implementation/capabilities/greeting/compose_process/src/main.rs`
have no validation code left at all — every check any of them used to
have turned out to be generic, not domain-specific.

## Capability-to-capability calls

`greeting.compose` needs *live* access to `console.write` during its own
execution (not just pre-computed input handed to it by its caller), so its
manifest sets `executor_kind: factory` and its `executor:` path names a
factory instead of an executor directly — `runtime/bridge/assembler.py` calls it
once, at assembly time, with a `Dependencies` (`runtime/bridge/bridge.py`) scoped to
exactly what its contract declared under `dependencies.capabilities` (R4).
`runtime/capabilities/greeting/compose/executor.py` resolves `console.write` once
from that `Dependencies` and closes over the handle; the returned
`execute(operation, input, policy)` calls it — a real, fully-traced Bridge
request every time, never a shortcut (R6/R8). Resolving anything the
contract didn't declare would raise `BRIDGE_UNDECLARED_DEPENDENCY`; the
declared dependency graph is also verified acyclic before anything is
registered (R5).

The dependency is pinned, not left open: `console.write` is declared as
`{capability_id: console.write, contract_version: ">=1.0.0,<2.0.0"}`, not a
bare id. `Dependencies.resolve` always resolves at exactly that declared
constraint — never `"*"`, never a value the factory chooses.

`console.write` genuinely has a 2.0.0 (manifest at
`implementation/capabilities/console/write_v2/`, executor at
`runtime/capabilities/console/write_v2/`, real and registered,
see below), and `greeting.compose` is unaffected by
it: its pin keeps it resolving `console.write.default` (1.0.0), never the
newer version -- observable directly in the printed output (see "Run"),
not just declared.

## console.write's two versions

`implementation/contracts/console.write.contract.yaml`'s `versions` holds `"1.0.0"` and
`"2.0.0"` as full, independent peers — neither is "current" with the other
demoted to history; `identity.version` names 2.0.0 as the default for a
consumer that doesn't pin anything (blueprint/2-RULES.md R2). The 2.0.0 version
renamed the operation's `text` input to `message` (a real breaking change)
and adds an optional `format` input (`"plain"`, `"uppercase"`, or
`"prefixed"`) that 1.0.0 has no equivalent for — a real capability
difference between the two versions, recorded in the contract and actually
exercised (see `runtime/app/main.py`'s second call), not just a cosmetic rename.
Both versions have live, callable implementations: `console.write.v2`
(2.0.0, `priority: 200` — manifest at
`implementation/capabilities/console/write_v2/`, executor at
`runtime/capabilities/console/write_v2/`) and `console.write.default`
(1.0.0, `priority: 100` — manifest at
`implementation/capabilities/console/write/`, executor at
`runtime/capabilities/console/write/`) — higher number,
higher precedence (`sample/schemas/capability-manifest.schema.json`). `priority` has
no default: every implementation states its own explicitly (blueprint/2-RULES.md "The
Registry contract"), the same reasoning as `contract_version` having none
on resolve, below. 1.0.0 stays fully alive and callable for anyone who
pins it explicitly.

Priority only breaks ties among candidates that already satisfy a given
version constraint — it is never a substitute for stating that constraint.
`runtime/app/main.py`'s calls all resolve at a stated version, even where it isn't
typed at the call site: `console_write` (`runtime/app/dependencies.yaml` pins
`>=2.0.0,<3.0.0`) lands on `console.write.v2` (`message`);
`greeting.compose`'s own dependency pin (`<2.0.0`) lands on
`console.write.default`; `console_write_legacy`, a deliberate proof rather
than a normal dependency, is declared separately at `<2.0.0` and lands on
the same implementation. 1.0.0's exact interface is right there in
`versions["1.0.0"]`, a full peer of 2.0.0's, and the assembler checks every
manifest's declared operations against whichever version it actually
claims, not merely a version number (blueprint/2-RULES.md R2).

## A capability in another language

`greeting.compose.process` (Cargo source at
`implementation/capabilities/greeting/compose_process/`, compiled
binary at `runtime/capabilities/greeting/compose_process/target/`,
written in Rust for this worked example — its name identifies what it
proves, out-of-process vs. in-process, not the language) is a SECOND,
real implementation of `greeting.compose` — same contract, same
`contract_version`, but its manifest sets `executor_kind: process` and
its `executor:` names a compiled program instead of a `module:attr` path.
`runtime/bridge/assembler.py` spawns it once, at assembly time, into a
`ProcessExecutorPool` (`runtime/bridge/process_executor.py`) instead of importing
anything; the pool becomes the executor and is verified to have actually
connected before being registered (blueprint/2-RULES.md R5, gate 6) — a path that
never resolves fails assembly loudly, not silently.

Crucially, it isn't just a leaf that answers the Bridge's calls — it
composes `console.write` FROM that separate process, through the Bridge,
while handling its own `compose` call, the same declared-dependency
mechanism and enforcement `runtime/capabilities/greeting/compose/executor.py`'s
Python factory already gets (R4), just reached over the wire instead of
a direct Python call. It inherits the contract's existing
`dependencies.capabilities` (`console.write`, `>=1.0.0,<2.0.0`)
automatically — dependencies live on the contract (R2), shared by every
implementation of it, regardless of language. This is what keeps a
capability implemented in another language from being cut off from
every capability that isn't: it can compose exactly like a Python one
can, not just be composed.

The wire protocol has two parts. Bridge → process starts one invocation
(`{"operation", "input", "policy"}`, the same three inputs every executor
gets), and speaks the same `execute(operation, input, policy) -> output`
contract every executor has — the process never sees `request_id`,
`contract_version`, or the trace; that stays the Bridge's job. Process →
Bridge, while handling that invocation, may ALSO send
`{"call": {"capability_id", "operation", "input"}}` back over the same
connection, any number of times, before its terminal reply —
`runtime/bridge/process_executor.py` resolves each one through a `Dependencies`
scoped to that implementation's own declared dependencies
(`BRIDGE_UNDECLARED_DEPENDENCY` if it names anything else), sends the
result back, and the process continues. `greeting.compose.process` never
prints anything itself; whichever `console.write` implementation the
nested call resolves to does — `console.write.default` (1.0.0), the same
one the Python composer already reaches, since both implementations
share the one contract-declared pin.

`implementation/capabilities/greeting/compose_process/` is a real
Cargo crate (`Cargo.toml` + `src/main.rs`), not a single file compiled by
bare `rustc` — it depends on `serde_json` for real JSON parsing (see
"Neither client hand-rolls its own connect/frame/dispatch logic", below)
and on `implementation/clients/rust/` via a path dependency. NOT
built automatically; build it once, from this directory:

```
cargo build --target-dir ../../../../runtime/capabilities/greeting/compose_process/target
```

`--target-dir` is not optional here, unlike a normal Cargo project: this
crate's SOURCE lives in `implementation/` but its compiled OUTPUT is a
runtime artifact (this runtime's own `implementation/`↔`runtime/`
split, "Layout" above) — a bare `cargo build` would place `target/` next
to `Cargo.toml`, in `implementation/`, where the manifest's `executor:`
path (below) would never find it. `target/` is gitignored, `Cargo.lock`
is committed (reproducible builds, standard practice for a binary crate).

Its `priority` (50) is below `greeting.compose.default`'s (100), so it's
reached only by its own declared name, `greeting_compose_process`, which
pins `implementation_id` explicitly (`runtime/app/dependencies.yaml`) — it never
silently becomes the default for `greeting_compose`'s own, separately
declared pin, the same posture `console_write_legacy` already has toward
`console_write`.

### Neither client hand-rolls its own connect/frame/dispatch logic

`src/main.rs` doesn't contain any of the connect/frame/dispatch code
above — it depends on the `bridge_client` crate (`implementation/clients/rust/`, a
Cargo path dependency in its own `Cargo.toml`) and reduces to just its
own operation logic: an `execute(operation, input, conn) ->
Result<Value, CallError>` function, handed to the crate's `serve`, which
owns connecting, reading, dispatching, and sending the reply. A second
Rust capability reuses the same client instead of copying that machinery
again, and can't quietly implement the framing or error handling
differently. `implementation/clients/rust/` uses `serde_json` (a real JSON library, not
hand-written field extraction) — precisely what lets `execute` write
`input["name"].as_str().expect(...)` and actually trust it, the same way
a Python executor trusts `input["name"]`: the Bridge's own guarantee
(required fields present, declared types honored) is only worth
something if the client parsing it is trustworthy too.

Because `serve` owns the loop and `execute` is just a plain function,
this capability's code would be identical if `greeting.compose` were
ever reachable in-process instead — nothing about it depends on
`executor_kind: process` specifically, only on being handed input and a
way to make its one nested call.

`runtime/clients/python/bridge_client.py` is the same idea for Python, and
`runtime/capabilities/console/write_process/executor.py` is what makes it a genuine proof
rather than a hypothetical: a THIRD implementation of `console.write`
2.0.0 that is Python, but runs as its own separate process instead of
in-process, reaching the Bridge through the same protocol any other
language uses — not the in-process `Dependencies` route just because it
happens to share a language with the Bridge. Its own code is
`execute(operation, input, policy) -> output`, handed to
`bridge_client.serve_direct` — the exact same shape and the exact same
function signature `runtime/capabilities/console/write_v2/executor.py` uses in-process; only
the one-line wrapper at the bottom of the file differs. Its `executor:`
is an argv list, not a single command string, because an interpreted
language needs an interpreter AND a script: `["python", "path/to/executor.py"]`
— `ProcessExecutorPool` (`runtime/bridge/process_executor.py`) accepts either
shape. Build nothing for this one; it runs directly. Its `priority`
(150) is below `console.write.v2`'s (200), reached only by its own
declared name, `console_write_process`, the same posture every other
extra implementation here has.

Both clients implement the same formally written-down protocol
(`sample/schemas/process-executor-protocol.schema.json`) — never hand-rolled
per capability.

### `runtime/clients/python/direct_adapter.py` — prepared, not yet needed

`executor_kind: direct`/`factory` (`console.write`'s and
`greeting.compose`'s default implementations —
`runtime/capabilities/console/write/`,
`runtime/capabilities/console/write_v2/`,
`runtime/capabilities/greeting/compose/`) is a literal in-process
Python call — genuinely coupled to the Bridge's own language, unlike
`process`.
If this runtime's Bridge is ever reimplemented in a different language,
those three capabilities' own files must not be edited or deleted to
keep them reachable (blueprint/2-RULES.md R4) — `direct_adapter.py` is the fix:
given a capability's `module:attr` executor path at runtime, it imports
that exact callable and hands it straight to
`bridge_client.serve_direct`/`serve_factory` — the identical functions
`runtime/capabilities/console/write_process/executor.py` calls itself, not a separate
implementation of the same idea — so a non-Python assembler can spawn
this adapter instead of importing the capability directly, invisibly to
discovery, policy, and selection.

Nothing in this sample calls it today — the Bridge is still Python, so
every `direct`/`factory` capability still runs in-process, the fast
path. It's written and tested ahead of that need on purpose: this
coupling is easy to miss until a Bridge rewrite is already underway (it
was), and by then editing or deleting a capability's own files looks
like the only way out unless this already exists.

## Capability catalog

`runtime/app/requests.py` registers capabilities from
`runtime/capability-catalog.jsonl` instead of walking and
re-parsing `implementation/capabilities/` at startup — that
doesn't scale once an ecosystem has more than a handful of capabilities
(see blueprint/2-RULES.md "The Registry contract" and
`runtime/bridge/assembler.py`). The catalog is a generated build
artifact, committed so the sample runs out of the box.

Regenerate it after editing anything under
`implementation/capabilities/` or a contract it references:

```
python -m sample.hello_world.backend.implementation.build_catalog
```

This calls `rebuild_catalog`, which walks the whole tree once — appropriate
here since this runtime's tree predates the catalog. A growing ecosystem
publishing capabilities one at a time should call `append_to_catalog`
per newly published manifest instead: O(1) per publish, never re-walking
what's already in the catalog.

## Run

From the repository root:

```
python -m sample.hello_world.backend.runtime.app.main
```

(Build the Rust executor first — see "A capability in another language" —
or the fifth call below will fail assembly with a clear error naming the
missing program, rather than a confusing one. The sixth call needs no
build step; it runs a Python script directly.)

Expected output — six lines, all printed by a console.write executor,
never by `runtime/app/main.py` (2.0.0 directly for the first two; 1.0.0 via the
nested Bridge call for `greeting.compose`'s; directly again for the
fourth; 1.0.0 again for the fifth, via a nested Bridge call made FROM a
separate out-of-process program; and 2.0.0 directly again for the
sixth, from a separate Python process):

```
This is a test of the Bridge's console.write capability.
HELLO, WORLD!
Greetings, ARPAPED!
console.write 1.0.0 is real and independently callable.
Greetings, ARPAPED (via Rust)!
This line is printed by a second Python process, through the Bridge.
```

The second line is uppercase because that call passes `format: "uppercase"`
— 2.0.0's optional feature 1.0.0 has no equivalent for. The fifth line
looks like the third (both printed by `console.write.default`, via a
nested Bridge call), but that nested call was made from
`greeting.compose.process` — a genuinely separate process (written in
Rust for this worked example), calling back into the Bridge mid-request
— not from `greeting.compose`'s Python factory. The sixth line is
printed by `console.write.process` — a second Python process, not the
interpreter running `runtime/app/main.py`, and not the same mechanism
`console.write.v2`/`console.write.default` use to run in-process.

After printing those six lines, `main.py` starts `web.serve` — an API
endpoint only (`/bridge` and `/health`), never a static file server — and
prints its URL plus the command needed to serve the frontend separately.
See `../README.md` "Two servers, not one" for why, and
`../frontend/README.md` "Run" to bring the frontend up against this API.
