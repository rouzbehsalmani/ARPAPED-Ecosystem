# Sample: hello world console app

The simplest possible complete, runnable example of the pattern
`0-WALKTHROUGH.md` describes: two capabilities (`console.write`, and
`greeting.compose` which depends on it), a single request-construction
point, and a process entry point that decides nothing — laid out in the same
`contracts/` / `capabilities/<domain>/<operation>/` / `app/` structure the
walkthrough recommends for any real application.

This is scaffolding to prove the wiring, not a feature — copy the shape (the
folder layout, the file order, the fields, the request-construction
pattern), never this domain content, into a real capability.

## Layout

```
contracts/
  console.write.contract.yaml       console.write's contract — versions 1.0.0 and 2.0.0, both alive peers
  greeting.compose.contract.yaml    greeting.compose's — declares console.write as a dependency
capabilities/
  console/write/
    manifest.yaml                 binds contract_version 1.0.0 to the executor below
    executor.py                   registration-unaware: given text, writes it to the console
  console/write_v2/
    manifest.yaml                 a SECOND manifest for console.write, at contract_version 2.0.0
    executor.py                   given message (renamed from text) and an optional format, writes it
  greeting/compose/
    manifest.yaml                 executor_kind: factory — see "Capability-to-capability calls"
    executor.py                   resolves console.write once, calls it through the Bridge
  greeting/compose_process/
    manifest.yaml                 a SECOND manifest for greeting.compose — executor_kind: process
    Cargo.toml, src/main.rs       a real Cargo crate — calls console.write FROM a separate process, see "A capability in another language"
  console/write_process/
    manifest.yaml                 a THIRD manifest for console.write 2.0.0 — executor_kind: process, argv list
    executor.py                   Python, but runs as its own separate process — see "A capability in another language"
build_catalog.py                  generates capability-catalog.jsonl (Phase 8, Publish)
capability-catalog.jsonl          generated — see "Capability catalog" below
app/
  dependencies.yaml              this app's own declared dependencies — keyed by name, not capability_id
  requests.py                     the single request-construction point (R6) — exposes resolve(name, operation)
  main.py                         the entry point — decides nothing, resolves once per declared name
clients/
  rust/                          Cargo library crate, depended on via a path dependency — see "A capability in another language"
  python/bridge_client.py        the same role, for a Python process-kind executor
```

The two process-kind executors above don't hand-write their own
connect/frame/dispatch logic -- they depend on a reference client from
this sample's own `clients/` directory (not part of `bridge/`; see "A
capability in another language"): `clients/rust/` (a Cargo library
crate, depended on via a path dependency) and `clients/python/bridge_client.py`,
both implementing
`schemas/process-executor-protocol.schema.json`. This directory lives
inside the sample, not at the repo root, because every consumer of it is
a capability inside this one sample — it's scaffolding to copy the shape
of, same as `contracts/`, `capabilities/`, and `app/`, not shared
infrastructure a real application would depend on.

`app/main.py` calls `requests.resolve("console_write", "write")` once and
gets back a handle, then calls `.call(...)` on that handle for each request
(discover once, call many times) instead of re-running discovery every
time. Neither `contract_version` nor `implementation_id` is passed at the
call site — `resolve` reads both from the named entry in
`app/dependencies.yaml`. Unlike a capability contract's own
`dependencies.capabilities` (keyed by capability_id, one entry per
capability), this file is keyed by a name the app chooses, so the same
capability_id (`console.write`) can be declared more than once under
different names, each pinned differently for a different purpose — see
`console_write` vs. `console_write_legacy`, below. A
name that isn't declared raises `BRIDGE_UNDECLARED_DEPENDENCY`; a declared
entry missing `contract_version` fails just as loudly, at load time —
there is no silent default anywhere in this chain (`app/dependencies.yaml`,
`app/requests.py`, `Bridge.resolve`). Only the discovery stage is cached —
policy is still evaluated and a candidate is still selected and executed
fresh on every `call`, through the same `bridge.handle` every request goes
through — and the handle re-checks its cached candidates' live state on
each use (self-healing by re-discovering if they've all become unusable),
so it can never return a stale result. `Bridge.resolve`/`BoundCapability`
(bridge/bridge.py) are what actually build the request; `app/requests.py`
stays the only application module that reaches the Bridge at all.

## What every executor here does NOT check, and why

None of the executors under `capabilities/` check the operation name —
`if operation != "write": ...` can never actually fire: discovery only
ever calls an executor with an operation it declared in the first place,
so that check would be dead code, not a safeguard.

None of them check their input's required-ness or basic type either
(e.g. `isinstance(message, str)`) — `Bridge.handle` (bridge/bridge.py)
validates a request's `input` against the resolved implementation's
contract-declared shape (`schemas/component-contract.schema.json`'s
`input[].type`/`required`) before any executor runs, uniformly, for
direct, factory, and process-kind implementations alike, in any
language.

Nor do `console.write.v2`/`console.write.process` default
`format` themselves any more — `input.get("format", "plain")` used to
live in each executor separately; now `contracts/console.write.contract.yaml`
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
nonzero length, so `contracts/greeting.compose.contract.yaml` declares
`pattern: "\S"` — at least one non-whitespace character — not
`minLength: 1`). `contracts/console.write.contract.yaml`'s `format`
declares `enum: [plain, uppercase, prefixed]`. Both are checked by the
Bridge the same way `type`/`required`/`default` already are, so
`console/write_v2/executor.py`, `console/write_process/executor.py`,
`greeting/compose/executor.py`, and `greeting/compose_process/src/main.rs`
have no validation code left at all — every check any of them used to
have turned out to be generic, not domain-specific.

## Capability-to-capability calls

`greeting.compose` needs *live* access to `console.write` during its own
execution (not just pre-computed input handed to it by its caller), so its
manifest sets `executor_kind: factory` and its `executor:` path names a
factory instead of an executor directly — `bridge/assembler.py` calls it
once, at assembly time, with a `Dependencies` (bridge/bridge.py) scoped to
exactly what its contract declared under `dependencies.capabilities` (R4).
`capabilities/greeting/compose/executor.py` resolves `console.write` once
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

`console.write` genuinely has a 2.0.0 (`capabilities/console/write_v2/`,
real and registered, see below), and `greeting.compose` is unaffected by
it: its pin keeps it resolving `console.write.default` (1.0.0), never the
newer version -- observable directly in the printed output (see "Run"),
not just declared.

## console.write's two versions

`contracts/console.write.contract.yaml`'s `versions` holds `"1.0.0"` and
`"2.0.0"` as full, independent peers — neither is "current" with the other
demoted to history; `identity.version` names 2.0.0 as the default for a
consumer that doesn't pin anything (2-RULES.md R2). The 2.0.0 version
renamed the operation's `text` input to `message` (a real breaking change)
and adds an optional `format` input (`"plain"`, `"uppercase"`, or
`"prefixed"`) that 1.0.0 has no equivalent for — a real capability
difference between the two versions, recorded in the contract and actually
exercised (see `app/main.py`'s second call), not just a cosmetic rename.
Both versions have live, callable implementations: `console.write.v2` (2.0.0,
`capabilities/console/write_v2/`, `priority: 200`) and `console.write.default`
(1.0.0, `capabilities/console/write/`, `priority: 100`) — higher number,
higher precedence (schemas/capability-manifest.schema.json). `priority` has
no default: every implementation states its own explicitly (2-RULES.md "The
Registry contract"), the same reasoning as `contract_version` having none
on resolve, below. 1.0.0 stays fully alive and callable for anyone who
pins it explicitly.

Priority only breaks ties among candidates that already satisfy a given
version constraint — it is never a substitute for stating that constraint.
`app/main.py`'s calls all resolve at a stated version, even where it isn't
typed at the call site: `console_write` (`app/dependencies.yaml` pins
`>=2.0.0,<3.0.0`) lands on `console.write.v2` (`message`);
`greeting.compose`'s own dependency pin (`<2.0.0`) lands on
`console.write.default`; `console_write_legacy`, a deliberate proof rather
than a normal dependency, is declared separately at `<2.0.0` and lands on
the same implementation. 1.0.0's exact interface is right there in
`versions["1.0.0"]`, a full peer of 2.0.0's, and the assembler checks every
manifest's declared operations against whichever version it actually
claims, not merely a version number (2-RULES.md R2).

## A capability in another language

`greeting.compose.process` (`capabilities/greeting/compose_process/`,
written in Rust for this worked example — its name identifies what it
proves, out-of-process vs. in-process, not the language) is a SECOND,
real implementation of `greeting.compose` — same contract, same
`contract_version`, but its manifest sets `executor_kind: process` and
its `executor:` names a compiled program instead of a `module:attr` path.
`bridge/assembler.py` spawns it once, at assembly time, into a
`ProcessExecutorPool` (`bridge/process_executor.py`) instead of importing
anything; the pool becomes the executor and is verified to have actually
connected before being registered (2-RULES.md R5, gate 6) — a path that
never resolves fails assembly loudly, not silently.

Crucially, it isn't just a leaf that answers the Bridge's calls — it
composes `console.write` FROM that separate process, through the Bridge,
while handling its own `compose` call, the same declared-dependency
mechanism and enforcement `capabilities/greeting/compose/executor.py`'s
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
`bridge/process_executor.py` resolves each one through a `Dependencies`
scoped to that implementation's own declared dependencies
(`BRIDGE_UNDECLARED_DEPENDENCY` if it names anything else), sends the
result back, and the process continues. `greeting.compose.process` never
prints anything itself; whichever `console.write` implementation the
nested call resolves to does — `console.write.default` (1.0.0), the same
one the Python composer already reaches, since both implementations
share the one contract-declared pin.

`capabilities/greeting/compose_process/` is a real Cargo crate (`Cargo.toml`
+ `src/main.rs`), not a single file compiled by bare `rustc` — it depends
on `serde_json` for real JSON parsing (see "Neither client hand-rolls its
own connect/frame/dispatch logic", below) and on `clients/rust/` via a
path dependency. NOT built automatically; build it once (from this
directory):

```
cargo build
```

which places the binary at `target/debug/greeting_compose_process[.exe]` —
`target/` is gitignored, `Cargo.lock` is committed (reproducible builds,
standard practice for a binary crate).

Its `priority` (50) is below `greeting.compose.default`'s (100), so it's
reached only by its own declared name, `greeting_compose_process`, which
pins `implementation_id` explicitly (`app/dependencies.yaml`) — it never
silently becomes the default for `greeting_compose`'s own, separately
declared pin, the same posture `console_write_legacy` already has toward
`console_write`.

### Neither client hand-rolls its own connect/frame/dispatch logic

`src/main.rs` doesn't contain any of the connect/frame/dispatch code
above — it depends on the `bridge_client` crate (`clients/rust/`, a
Cargo path dependency in its own `Cargo.toml`) and reduces to just its
own operation logic: validate, compose, call, reply. A second Rust
capability reuses the same client instead of copying that machinery
again, and can't quietly implement the framing or error handling
differently. `clients/rust/` uses `serde_json` (a real JSON library, not
hand-written field extraction) — precisely what lets `src/main.rs` write
`invocation.input["name"].as_str().expect(...)` and actually trust it,
the same way a Python executor trusts `input["name"]`: the Bridge's own
guarantee (required fields present, declared types honored) is only
worth something if the client parsing it is trustworthy too.

`clients/python/bridge_client.py` is the same idea for Python, and
`capabilities/console/write_process/` is what makes it a genuine proof
rather than a hypothetical: a THIRD implementation of `console.write`
2.0.0 that is Python, but runs as its own separate process instead of
in-process, reaching the Bridge through the same protocol any other
language uses — not the in-process `Dependencies` route just because it
happens to share a language with the Bridge. Its `executor:` is an argv
list, not a single command string, because an interpreted language
needs an interpreter AND a script: `["python", "path/to/executor.py"]`
— `ProcessExecutorPool` (`bridge/process_executor.py`) accepts either
shape. Build nothing for this one; it runs directly. Its `priority`
(150) is below `console.write.v2`'s (200), reached only by its own
declared name, `console_write_process`, the same posture every other
extra implementation here has.

Both clients implement the same formally written-down protocol
(`schemas/process-executor-protocol.schema.json`) — never hand-rolled
per capability.

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

(Build the Rust executor first — see "A capability in another language" —
or the fifth call below will fail assembly with a clear error naming the
missing program, rather than a confusing one. The sixth call needs no
build step; it runs a Python script directly.)

Expected output — six lines, all printed by a console.write executor,
never by `app/main.py` (2.0.0 directly for the first two; 1.0.0 via the
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
interpreter running `app/main.py`, and not the same mechanism
`console.write.v2`/`console.write.default` use to run in-process.
