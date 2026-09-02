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
build_catalog.py                  generates capability-catalog.jsonl (Phase 8, Publish)
capability-catalog.jsonl          generated — see "Capability catalog" below
app/
  dependencies.yaml              this app's own declared dependencies — same shape as a contract's
  requests.py                     the single request-construction point (R6) — exposes resolve()/resolve_pinned()
  main.py                         the entry point — decides nothing, resolves once per capability
```

`app/main.py` calls `requests.resolve("console.write", "write")` once and
gets back a handle, then calls `.call(...)` on that handle for each request
(discover once, call many times) instead of re-running discovery every
time. No `contract_version` is passed at the call site — `resolve` reads it
from `app/dependencies.yaml`, this app's own declared dependencies, the
same shape a capability contract's `dependencies.capabilities` uses and
resolved through the same `Dependencies` mechanism (bridge/bridge.py) a
capability's own executor factory relies on. A capability id that isn't
declared there raises `BRIDGE_UNDECLARED_DEPENDENCY`; there is no silent
default anywhere in this chain (`app/dependencies.yaml`, `app/requests.py`,
`Bridge.resolve`) — a caller must always have stated what it needs
somewhere, never silently inherit whatever tie-breaking among registered
versions happens to produce. A genuine one-off need outside the app's
normal declared dependencies still states its version explicitly, through
`requests.resolve_pinned(...)` (see the fourth call, below). Only the
discovery stage is cached — policy is still evaluated and a
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
newer version, and `app/main.py` asserts this directly rather than just
trusting it.

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
typed at the call site: the first two resolve through the app's declared
dependency (`app/dependencies.yaml` pins `>=2.0.0,<3.0.0`) and land on
`console.write.v2` (`message`); `greeting.compose`'s own dependency pin
(`<2.0.0`) lands on `console.write.default`; a fourth call, a deliberate
proof rather than a normal dependency, explicitly pins `<2.0.0` through
`resolve_pinned` and asserts the same. 1.0.0's exact interface is right there in
`versions["1.0.0"]`, a full peer of 2.0.0's, and the assembler checks every
manifest's declared operations against whichever version it actually
claims, not merely a version number (2-RULES.md R2).

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

Expected output — four lines, all printed by a console.write executor
(2.0.0 directly for the first two; 1.0.0 via the nested Bridge call for
`greeting.compose`'s, and directly again for the fourth), never by
`app/main.py`:

```
This is a test of the Bridge's console.write capability.
HELLO, WORLD!
Greetings, ARPAPED!
console.write 1.0.0 is real and independently callable.
```

The second line is uppercase because that call passes `format: "uppercase"`
— 2.0.0's optional feature 1.0.0 has no equivalent for.
