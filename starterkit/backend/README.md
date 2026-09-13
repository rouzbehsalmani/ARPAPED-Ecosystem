# Starter kit: logging web app — backend

The Python half of `starterkit` (see `../README.md` for the
whole starter kit, what it proves, and how this half composes with
`../frontend/README.md`, the other half). This document covers only
this runtime's own territory: its contracts, capabilities, Bridge, and
how to run it standalone.

This is a real starting point, meant to be copied — copy the shape (the
folder layout, the file order, the fields, the request-construction
pattern) AND the domain (`log.write` is real, keepable content, not a
placeholder — see `../README.md` "A real starter kit"); what's still
worth replacing is the implementation bodies themselves, which are
intentionally minimal (a line to stdout), not real logging behavior.

## Layout

Files split into `implementation/` (contracts, manifests, build/verify
tooling — never shipped, never read by anything under `runtime/`) and
`runtime/` (the Bridge, executors, the generated catalog, the entry
point — the only thing a real deployment ever needs). A manifest and its
executor were always related by reference, not physical adjacency (a
manifest's `executor:` field is a path/module string, same as it
references a contract by path) — this split is that same principle
carried one step further, not a new exception to R3's co-location rule
(co-located in the same OWNING PACKAGE, i.e. this one starter kit, not
necessarily the same directory). `../frontend/` carries the identical
split for the same reason — see `../frontend/README.md`'s own Layout.

```
implementation/                   never read by anything under runtime/ below
  contracts/                      this runtime's OWN contracts — not shared with ../frontend/implementation/contracts/;
                                   two agents can work their own territory without touching the other's files
    log.write.contract.yaml         one version (1.0.0), TWO peer implementations (see "log.write's two implementations")
    web.serve.contract.yaml         declares log.write as a dependency (>=1.0.0,<2.0.0)
  capabilities/                   manifest.yaml per implementation — see "log.write's two implementations" etc.
  clients/csharp/                 .NET library project SOURCE — compiled once, the binary ships in runtime/, not this
  build_catalog.py                generates ../runtime/capability-catalog.jsonl (Phase 8, Publish)
  tests/verify/verify.py          the harness — both runtimes' checks, one verification record
runtime/                          everything a real deployment needs; nothing here reads implementation/
  bridge/                         this runtime's own Bridge (pre-existing)
    bridge.py, registry.py, policy.py, selector.py, assembler.py, process_executor.py
    MANIFEST.yaml                  authoritative descriptor, this runtime's own
  capabilities/                   executor.py per implementation ONLY — no manifest.yaml here
    log/write_process/bin/            the COMPILED C# binary — its source lives in implementation/, not here
  capability-catalog.jsonl        generated — the ONE thing assemble_from_catalog reads at process startup
  app/
    dependencies.yaml, requests.py, main.py
  clients/python/                 bridge_client.py, direct_adapter.py — runtime dependencies of process-kind executors
state/                             generated, gitignored — never committed, always reproducible by running the commands above
  verification-record.json         written by verify.py, the harness's own last act on a green run
  episodes/                        one directory per recorded cycle (blueprint.dep.episode_store)
  runtime-events.jsonl             one line per REAL Bridge call (blueprint.dep.runtime_log) — see "Runtime events" below
```

The two process-kind executors below don't hand-write their own
connect/frame/dispatch logic -- they depend on a reference client from
this runtime's own `clients/` directories (not part of `runtime/bridge/`;
see "A capability in another language"): `implementation/clients/csharp/`
(a .NET library project, SOURCE, depended on via a ProjectReference -- only
needed to compile the C# executor, never at runtime) and
`runtime/clients/python/bridge_client.py` (needed at runtime -- the
Python process-kind executor imports it directly), both implementing
`starterkit/schemas/process-executor-protocol.schema.json`. Each `clients/`
lives inside this runtime's own tree, not at the repo root, because
every consumer of it is a capability inside this one starter kit — it's
meant to be copied into a real application's own tree, not depended on
as shared infrastructure.

`runtime/app/main.py` calls `requests.resolve("log_write", "write")` once and
gets back a handle, then calls `.call(...)` on that handle for each request
(discover once, call many times) instead of re-running discovery every
time. Neither `contract_version` nor `implementation_id` is passed at the
call site — `resolve` reads both from the named entry in
`runtime/app/dependencies.yaml`. Unlike a capability contract's own
`dependencies.capabilities` (keyed by capability_id, one entry per
capability), this file is keyed by a name the app chooses, so the same
capability_id (`log.write`) can be declared more than once under
different names, each pinned differently for a different purpose — see
`log_write` vs. `log_write_process`, below. A
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
contract-declared shape (`starterkit/schemas/component-contract.schema.json`'s
`input[].type`/`required`) before any executor runs, uniformly, for
direct, factory, and process-kind implementations alike, in any
language.

Nor does either implementation default `level` itself —
`input.get("level", "info")` would be tempting to write in each executor
separately; instead `implementation/contracts/log.write.contract.yaml`
declares `default: info` once, on the field itself, and `Bridge.handle`
fills it in before either executor runs, so both can just write
`input["level"]`. A default is a static fact about the field, the same
kind of thing `type`/`required` already are, so it belongs in the same
place they do.

One check that looks at first like genuine business logic turns out not
to be: `level` must be one of a fixed set of strings. That doesn't
require understanding what this capability does — "one of a fixed set of
values" is JSON Schema's `enum`, and
`implementation/contracts/log.write.contract.yaml`'s `level` declares
`enum: [info, warn, error]`. It's checked by the Bridge the same way
`type`/`required`/`default` already are, so
`runtime/capabilities/log/write/executor.py` and
`implementation/capabilities/log/write_process/Program.cs` have no
validation code left at all — every check either would otherwise need
turned out to be generic, not domain-specific.

## Capability-to-capability calls

`log.write` itself is a leaf — its contract declares no dependencies at
all (`dependencies.capabilities: []`), so neither of its two
implementations composes anything. The one capability here that DOES
need live access to another during its own execution is `web.serve`: its
manifest sets `executor_kind: factory` and its `executor:` path names a
factory instead of an executor directly — `runtime/bridge/assembler.py` calls it
once, at assembly time, with a `Dependencies` (`runtime/bridge/bridge.py`) scoped to
exactly what its contract declared under `dependencies.capabilities`
(`log.write`, R4). Resolving anything the contract didn't declare would
raise `BRIDGE_UNDECLARED_DEPENDENCY`; the declared dependency graph is
also verified acyclic before anything is registered (R5).

Unlike a factory that closes over one named dependency and calls it the
same way every time, `runtime/capabilities/web/serve/executor.py`'s
factory resolves its dependency freshly per incoming HTTP request,
using whatever `capability_id`/`operation` the request body itself
names (`dependencies.resolve(capability_id, operation)` inside
`do_POST`, not inside `make_executor`) — because `web.serve` is a
generic Remote entry point (any capability_id a consumer's remote pin
resolves to), not a capability that only ever forwards to one fixed
name. It's still scoped exactly the same way: naming anything outside
`dependencies.capabilities` still raises `BRIDGE_UNDECLARED_DEPENDENCY`,
so in practice, today, the only capability_id it can ever actually
dispatch to is `log.write`.

The dependency is pinned, not left open: `log.write` is declared as
`{capability_id: log.write, contract_version: ">=1.0.0,<2.0.0"}`, not a
bare id. `Dependencies.resolve` always resolves at exactly that declared
constraint — never `"*"`, never a value the factory chooses.

## log.write's two implementations

`implementation/contracts/log.write.contract.yaml` has exactly one
version (`"1.0.0"`) with two full, independently live peer
implementations — the split here is about WHERE code runs, not about
different contract shapes: `log.write.default` (`priority: 100` —
manifest at `implementation/capabilities/log/write/`, executor at
`runtime/capabilities/log/write/`, direct/in-process) and
`log.write.process` (`priority: 50` — manifest at
`implementation/capabilities/log/write_process/`, executor at
`runtime/capabilities/log/write_process/bin/`, out-of-process, written
in C# — see "A capability in another language" below). Higher number,
higher precedence (`starterkit/schemas/capability-manifest.schema.json`).
`priority` has no default: every implementation states its own
explicitly (blueprint/2-RULES.md "The Registry contract"), the same
reasoning as `contract_version` having none on resolve.

Priority only breaks ties among candidates that already satisfy a given
version constraint — it is never a substitute for stating that
constraint. `runtime/app/main.py`'s calls resolve by declared name, never a
restated version at the call site: `log_write`
(`runtime/app/dependencies.yaml` pins `>=1.0.0,<2.0.0`, unpinned on
`implementation_id`) lands on the highest-priority policy-allowed
candidate, `log.write.default`; `log_write_process`, a deliberate proof
rather than a normal dependency, pins `implementation_id: log.write.process`
explicitly, so it reaches the lower-priority implementation on purpose.
This exact behavior — an unpinned name must keep landing on the
highest-priority candidate — is what
`backend/implementation/tests/verify/verify.py`'s permanent regression
check (`log-write-priority-flip-2026-09`, see "Run") actually protects.

## A capability in another language

`log.write.process` (.NET project source at
`implementation/capabilities/log/write_process/`, compiled
binary at `runtime/capabilities/log/write_process/bin/`,
written in C# for this worked example — its name identifies what it
proves, out-of-process vs. in-process, not the language) is a SECOND,
real implementation of `log.write` — same contract, same
`contract_version`, but its manifest sets `executor_kind: process` and
its `executor:` names a compiled program instead of a `module:attr` path.
`runtime/bridge/assembler.py` spawns it once, at assembly time, into a
`ProcessExecutorPool` (`runtime/bridge/process_executor.py`) instead of importing
anything; the pool becomes the executor and is verified to have actually
connected before being registered (blueprint/2-RULES.md R5, gate 6) — a path that
never resolves fails assembly loudly, not silently.

Unlike the old worked example this one replaced, `log.write` itself
declares no dependencies (`dependencies.capabilities: []` — it's a leaf,
see "Capability-to-capability calls" above), so `log.write.process`
never makes a nested call back into the Bridge — it just writes its own
line to its own stdout and returns. The wire protocol it speaks
(`starterkit/schemas/process-executor-protocol.schema.json`) still supports
nested calls generically — Process → Bridge may send
`{"call": {"capability_id", "operation", "input"}}` back over the same
connection, any number of times, before its terminal reply, and
`runtime/bridge/process_executor.py` would resolve each one through a
`Dependencies` scoped to that implementation's own declared dependencies
(`BRIDGE_UNDECLARED_DEPENDENCY` if it named anything else) — this
starter kit just has no process-kind implementation left that needs to
exercise that half of the protocol. What every process-kind executor
DOES always get: Bridge → process starts one invocation
(`{"operation", "input", "policy"}`, the same three inputs every executor
gets), and speaks the same `execute(operation, input, policy) -> output`
contract every executor has — the process never sees `request_id`,
`contract_version`, or the trace; that stays the Bridge's job.

`implementation/capabilities/log/write_process/` is a real
.NET console-app project (`LogWriteProcess.csproj` +
`Program.cs`), not a single file compiled by bare `csc` — it depends on
`System.Text.Json` for real JSON parsing (see "Neither client hand-rolls
its own connect/frame/dispatch logic", below), already part of the
SDK/runtime with nothing extra to pin, and on
`implementation/clients/csharp/` via a ProjectReference. NOT
built automatically; build it once, from this directory:

```
dotnet build --output ../../../../runtime/capabilities/log/write_process/bin
```

`--output` is not optional here, unlike a normal .NET project: this
project's SOURCE lives in `implementation/` but its compiled OUTPUT is a
runtime artifact (this runtime's own `implementation/`↔`runtime/`
split, "Layout" above) — a bare `dotnet build` would place `bin/`/`obj/`
next to `.csproj`, in `implementation/`, where the manifest's `executor:`
path (below) would never find it. `bin/`/`obj/` are gitignored; the
`.csproj` itself is committed (reproducible builds, standard practice for
a .NET project — there is no external package dependency here to lock).

Its `priority` (50) is below `log.write.default`'s (100), so it's
reached only by its own declared name, `log_write_process`, which
pins `implementation_id` explicitly (`runtime/app/dependencies.yaml`) — it never
silently becomes the default for `log_write`'s own, separately
declared, unpinned name (see "log.write's two implementations" above,
and the permanent regression check that protects exactly this).

### Neither client hand-rolls its own connect/frame/dispatch logic

`Program.cs` doesn't contain any of the connect/frame/dispatch code
above — it depends on the `BridgeClient` project (`implementation/clients/csharp/`, a
ProjectReference in its own `.csproj`) and reduces to just its
own operation logic: an `Execute(operation, input, conn) -> object`
function, handed to the project's `Connection.Serve`, which owns
connecting, reading, dispatching, and sending the reply (a capability
fails its own call by throwing `CallError`, the idiomatic C# equivalent
of the Rust client's `Result<Value, CallError>` this project replaced).
A second C# capability reuses the same client instead of copying that
machinery again, and can't quietly implement the framing or error
handling differently. `implementation/clients/csharp/` uses
`System.Text.Json` (a real JSON library, not hand-written field
extraction) — precisely what lets `Execute` write
`input.GetProperty("message").GetString()` and actually trust it, the same
way a Python executor trusts `input["message"]`: the Bridge's own guarantee
(required fields present, declared types honored) is only worth
something if the client parsing it is trustworthy too.

Because `Serve` owns the loop and `Execute` is just a plain function,
this capability's code would be identical if `log.write` ever needed a
nested call of its own, or were ever reachable in-process instead —
nothing about it depends on `executor_kind: process` specifically.

Both clients implement the same formally written-down protocol
(`starterkit/schemas/process-executor-protocol.schema.json`) — never hand-rolled
per capability. `runtime/clients/python/bridge_client.py` is the
identical idea for Python — not exercised by a live capability in this
starter kit today, since its one process-kind implementation happens to
be written in C#, but proven correct against the same schema (see that
file's own docstring).

### `runtime/clients/python/direct_adapter.py` and `bridge_client.py` — prepared, not yet needed

`executor_kind: direct`/`factory` (`log.write`'s and `web.serve`'s
default implementations — `runtime/capabilities/log/write/`,
`runtime/capabilities/web/serve/`) is a literal in-process
Python call — genuinely coupled to the Bridge's own language, unlike
`process`.
If this runtime's Bridge is ever reimplemented in a different language,
those capabilities' own files must not be edited or deleted to
keep them reachable (blueprint/2-RULES.md R4) — `direct_adapter.py` is the fix:
given a capability's `module:attr` executor path at runtime, it imports
that exact callable and hands it straight to
`bridge_client.serve_direct`/`serve_factory` — so a non-Python assembler
can spawn this adapter instead of importing the capability directly,
invisibly to discovery, policy, and selection.

Nothing in this starter kit calls either file today — the Bridge is
still Python, so every `direct`/`factory` capability still runs
in-process, the fast path, and the one process-kind capability that
exists (`log.write.process`) is written in C#, using that language's own
reference client instead of `bridge_client.py`. Both Python files are
written and tested ahead of that need on purpose: the direct/factory
coupling to the Bridge's own language is easy to miss until a Bridge
rewrite is already underway (it was, once), and by then editing or
deleting a capability's own files looks like the only way out unless
this already exists.

## Capability catalog

`runtime/app/requests.py` registers capabilities from
`runtime/capability-catalog.jsonl` instead of walking and
re-parsing `implementation/capabilities/` at startup — that
doesn't scale once an ecosystem has more than a handful of capabilities
(see blueprint/2-RULES.md "The Registry contract" and
`runtime/bridge/assembler.py`). The catalog is a generated build
artifact, gitignored like every other generated `state/`-style output
(`.gitignore`) — run the command below once before this starter kit's
first use, and again after any capability change.

Regenerate it after editing anything under
`implementation/capabilities/` or a contract it references:

```
python -m starterkit.backend.implementation.build_catalog
```

This calls `rebuild_catalog`, which walks the whole tree once — appropriate
here since this runtime's tree predates the catalog. A growing ecosystem
publishing capabilities one at a time should call `append_to_catalog`
per newly published manifest instead: O(1) per publish, never re-walking
what's already in the catalog.

## Run

From the repository root:

```
python -m starterkit.backend.runtime.app.main
```

(Build the C# executor first — see "A capability in another language" —
or the whole app fails immediately at assembly, before printing
anything, with a clear error naming the missing program, rather than a
confusing one: `assemble_from_catalog` builds every implementation in
the catalog up front, at import time, not lazily per call.)

Expected terminal output:

```
[INFO] This is a test of the Bridge's log.write capability.
[WARN] Something worth flagging.
[INFO] API running at http://127.0.0.1:8420 (/bridge). Ctrl+C to stop.
Now serve the frontend separately, e.g.:
    python -m starterkit.frontend.runtime.host.serve
then open http://127.0.0.1:8421 in a browser.
```

The first two lines are both printed by `log.write.default` (the
unpinned `log_write` name's highest-priority policy-allowed candidate,
see "log.write's two implementations") — the second passes
`level: "warn"`, the contract's own `enum`, not a domain-specific check
either executor writes itself (see "What every executor here does NOT
check"). The third `log.write`-shaped call, `log_write_process`, reached
only because `app/dependencies.yaml` pins its `implementation_id`
explicitly, runs `log.write.process` — a genuinely separate,
out-of-process C# program (see "A capability in another language") —
but its own `Console.WriteLine` output is captured internally by
`ProcessExecutorPool` as this call's own recorded `evidence.stdout`
(`verification-record.schema.json`), never inherited by this terminal.
That's the exact same property that once made a genuinely healthy run
look like a hang during this starter kit's own development: a
process-kind worker's stdout was never going to reach this terminal, by
design, so its absence here proves nothing is wrong. Inspect
`state/verification-record.json` (after a `verify.py` run) to see that
line for real.

The fourth line IS printed by `log.write.default` too — `main.py` logs
its own startup status through the same `log` handle the first two calls
use, right after `web.serve.start` returns (an API endpoint only,
`/bridge` and `/health`, never a static file server), the same way a
real backend logs its own lifecycle rather than using a bare `print()`.
The two lines after that ARE a plain `print()`, deliberately: CLI
guidance for the human at this terminal (how to bring the frontend up
against this API), not an event this service would ever log on its own
— see `../README.md` "Two servers, not one" for why they're separate
processes at all, and `../frontend/README.md` "Run" to act on them.
Ctrl+C stops the server and logs one more line, `[INFO] server stopped`,
the same way.

### Run (agent-driven / automated)

The command above is for a human at a terminal: it never returns on its
own (that's the point — `main.py` keeps `web.serve` up until Ctrl+C), so
a human watches the three lines print, then Ctrl+C's it when done. An
agent or script starting this backend to test against it, then continue
doing OTHER work, must NOT invoke it the same way: waiting on that
command to finish is waiting on something that runs forever, which reads
as "stuck" no matter how long you wait — an orphaned, healthy process
mistaken for a hang, observed for real. Use `process_supervisor`
(`blueprint/dep/MANIFEST.yaml: process_supervisor`) instead — it returns
as soon as `ready_check` passes, never once the process exits, and
refuses up front (rather than reporting a false "ready") if something
NOT tracked by `pidfile` already occupies whatever `ready_check` watches
— see that module's own docstring for why this specific protection
exists, observed for real in this exact sequence:

```python
from pathlib import Path
from blueprint.dep import process_supervisor

pidfile = Path("starterkit/backend/state/backend.pid")
process_supervisor.start(
    ["python", "-m", "starterkit.backend.runtime.app.main"],
    pidfile=pidfile,
    ready_check=process_supervisor.tcp_ready_check("127.0.0.1", 8420),
)
# start() has already returned -- the backend is confirmed listening on
# 8420. Do whatever testing needed it running, then:
process_supervisor.stop(pidfile)
```

`stop()` is idempotent and safe to call even if you're not sure it's
still running. Never a bare `subprocess.Popen`/`Start-Process -PassThru`
with no corresponding stop step — that's exactly how an orphaned backend
(still holding port 8420) outlives the session that started it.

## Runtime events

Every one of `main.py`'s calls lands in `state/runtime-events.jsonl` too
— not just recorded in `state/verification-record.json` the way
`verify.py`'s scripted calls are: the three calls the harness mirrors,
`web.serve`'s own start, `main.py`'s own startup-status `log.write` call
right after, and, on a clean Ctrl+C, `web.serve`'s stop and one final
shutdown `log.write` call — up to six events from one full run, not
four. `runtime/app/requests.py` passes a `blueprint.dep.runtime_log.RuntimeEventLog`
(`blueprint/dep/MANIFEST.yaml: runtime_log`) as this Bridge's own
`event_sink`; `Bridge.handle` (`runtime/bridge/bridge.py`) calls it once
per real call it ever handles, success or failure, whether that call
came from this file or from `verify.py`'s harness. `log.write` itself
declares no dependencies, so neither of its own implementations makes a
NESTED call while handling any of these — but `web.serve`'s factory
does resolve `log.write` fresh per incoming HTTP request (see
"Capability-to-capability calls"), so once a remote consumer (the
frontend's `client.log`, or any other) starts sending real requests
through `/bridge`, each one lands here as its own independent event too,
on top of whatever `main.py` itself already logged. This is what makes
`state/` genuinely runtime history, not just a development-cycle audit
trail: a verification record is written once per verified cycle, by a
harness; a runtime event is written once per call, by the Bridge itself,
for every call it ever actually handles. `bridge.py` never imports
`blueprint.dep` — `event_sink` is a plain, duck-typed callable, the same
decoupling posture it already has toward `ProcessExecutorPool`.
