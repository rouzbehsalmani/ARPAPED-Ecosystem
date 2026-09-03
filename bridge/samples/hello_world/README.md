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
  console/write_rust/
    manifest.yaml                 a THIRD manifest for console.write 2.0.0 — executor_kind: process
    executor.rs                   not Python — see "A capability in another language"
  greeting/compose/
    manifest.yaml                 executor_kind: factory — see "Capability-to-capability calls"
    executor.py                   resolves console.write once, calls it through the Bridge
build_catalog.py                  generates capability-catalog.jsonl (Phase 8, Publish)
capability-catalog.jsonl          generated — see "Capability catalog" below
app/
  dependencies.yaml              this app's own declared dependencies — keyed by name, not capability_id
  requests.py                     the single request-construction point (R6) — exposes resolve(name, operation)
  main.py                         the entry point — decides nothing, resolves once per declared name
```

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
`console_write` vs. `console_write_legacy`/`console_write_rust`, below. A
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

`console.write.rust` (`capabilities/console/write_rust/`) is a THIRD
implementation of the same `console.write` 2.0.0 operation — same
contract, same `contract_version`, but its manifest sets
`executor_kind: process` and its `executor:` names a compiled program
instead of a `module:attr` path. `bridge/assembler.py` spawns it once, at
assembly time, into a `ProcessExecutorPool` (`bridge/process_executor.py`)
instead of importing anything; the pool becomes the executor and is
verified to have actually connected before being registered (2-RULES.md
R5, gate 6) — a path that never resolves fails assembly loudly, not
silently.

`executor.rs` is real Rust, not a stand-in: it connects back over loopback
TCP (the port is handed to it in `ARPAPED_BRIDGE_PORT`) and speaks the
same `execute(operation, input, policy) -> output` contract every executor
has, one newline-delimited JSON message per call — it never sees
`request_id`, `contract_version`, or the trace; that stays the Bridge's
job. It is NOT compiled automatically; build it once (from this
directory, on Windows):

```
rustc capabilities/console/write_rust/executor.rs -o capabilities/console/write_rust/console_write_rust.exe
```

(on Linux/Mac, drop `.exe` from both the `-o` name and the manifest's
`executor:`). The compiled binary isn't committed — it's platform-specific,
the same posture the catalog already has toward needing a build step.

Its `priority` (150) is below `console.write.v2`'s (200), so it's reached
only by its own declared name, `console_write_rust`, which pins
`implementation_id` explicitly (`app/dependencies.yaml`) — it never
silently becomes the default for `console_write`'s own, separately
declared pin, the same posture `console_write_legacy` already has.

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
missing program, rather than a confusing one.)

Expected output — five lines, all printed by a console.write executor
(2.0.0 directly for the first two; 1.0.0 via the nested Bridge call for
`greeting.compose`'s; directly again for the fourth; and the Rust process
for the fifth), never by `app/main.py`:

```
This is a test of the Bridge's console.write capability.
HELLO, WORLD!
Greetings, ARPAPED!
console.write 1.0.0 is real and independently callable.
This line is printed by a Rust process, through the Bridge.
```

The second line is uppercase because that call passes `format: "uppercase"`
— 2.0.0's optional feature 1.0.0 has no equivalent for. The fifth line is
printed by a genuinely separate process (`console.write.rust`), not the
Python interpreter running `app/main.py` at all.
