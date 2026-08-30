# Rules: Definitions, Invariants, Bridge Enforcement

Building something concrete right now? See `0-WALKTHROUGH.md` — it turns these
rules into literal file paths and commands. This file is the definitions/
invariants reference it points back to.

The single source of definitions and invariant rules for the ARPAPED
self-improving cycle. Every other document uses exactly these words and cites
these rules by number; nothing else states a rule in full. If a document
seems to redefine a term or restate a rule differently, that document is
wrong, not this page. The cycle that applies these rules phase by phase is
`1-CYCLE.md`; reusable artifact shapes are in `3-TEMPLATES.md`.

## Glossary

| Term | Definition |
|---|---|
| **cycle** | One complete pass through the phases in `1-CYCLE.md` (Phase 0 Bootstrap through Phase 9 Return state): it starts from a `current_state` + `goal` and produces a verified `resulting state`, which becomes the next cycle's `current_state`. This is the unit the Blueprint is named after — the loop is "self-improving" because each cycle's output is the next cycle's input, with no private agent memory required in between (Gate 11). |
| **ecosystem root** | The authoritative ARPAPED project root supplied by the operator. It is a single application. The agent resolves every canonical implementation from here; it never creates a second copy. |
| **responsibility** | One independently meaningful thing the cycle must achieve. The unit of decomposition: one responsibility = one capability = one contract. |
| **capability** | A named, versioned responsibility that the ecosystem can execute (`capability_id`). Identity is the generic responsibility (`domain.operation`) per R1. Consumers speak only capability IDs + contract operations (per R6) through the single request-construction point. One contract artifact defines it; it may have one or more implementations. |
| **contract** | The machine-readable interface of a capability: identity, version, operations (name, input, output, errors), dependencies, policy, invariants, discoverability, lineage. One contract artifact per capability (R2). |
| **contract artifact** | The materialized, versioned interface file that machine-defines a capability (template: `3-TEMPLATES.md`). Existence and uniqueness per R2. Contract artifacts live under `contracts/`. Referenced by its capability manifest; may be implemented by many components. |
| **generic component** | A small, single-task component that is reusable across cycles. "Generic" describes the component's nature (one task, reusable), never a location (R1, R4). |
| **component** | The thing that *implements* a capability. A registration-unaware executor exposing only `execute(operation, input, policy) -> output`. Components are never named or imported by consumer code. |
| **implementation** | A registered, versioned record that binds an executor to a capability contract (id, version, operations) in the Registry. |
| **consumer** | Any application code that invokes a capability. Reference behavior per R6: consumer code uses only capability IDs + contract operations through the single request-construction point and the Bridge, and never names components. |
| **manifest** | A data file that binds a contract artifact to its operations and to one executor-reference entry per implementation (one contract → one capability manifest → executor entries). The contract artifact, its capability manifests, and its executors are co-located in their owning package within the single application (R3). |
| **packaging** | How the single application is structured as normal packages: contract artifacts under `contracts/`; component executors and capability manifests co-located in their owning packages; small generic components built and composed before the specific responsibilities over them (generics → specifics, R4); entry points and the single request-construction point at the application level; tests and the verification harness live outside the application packages. |
| **assembler** | A generic Publish-phase helper that reads the capability manifests, imports each executor, builds each implementation record, and registers it into the canonical Registry. Application packages never contain registration logic. Reference implementation: `bridge/assembler.py`. |
| **Bridge** | The canonical execution boundary. Routes every request through registry discovery → policy → selector → executor and returns a trace. There is exactly one canonical Bridge. |
| **Registry** | The canonical discovery/index service: capability+operation → bounded implementation candidates. There is exactly one canonical Registry. |
| **Policy** | The canonical authorization stage that evaluates each candidate against the request's policy context. |
| **Selector** | The canonical routing stage that picks which allowed candidate executes (with failover awareness). |
| **Executor** | A component's `execute` callable; the only code the Bridge executes. |
| **trace** | The ordered stage list a Bridge response carries: `validated → discovered → policy_evaluated → selected → executed`. The designed evidence that a request travelled the canonical path. |
| **resulting state** | The authoritative, discoverable state of the ecosystem after a cycle completes — code, contracts, manifests, verification record, report. The input state of the next cycle. |
| **verification record** | The machine-readable result of the Verify phase (`schemas/verification-record.schema.json`), written into the resulting state. Green only when the harness passes. |
| **lineage** | The discoverable history of a component: which cycle/agent created it, what changed it, and how it evolved through splits. |

Dependency direction — capability contracts depend on each other from
**generics → specifics**: a generic capability is a small single-task
component reusable in later cycles, and a specific capability is a thin
composition over generic ones. Full rule: R4.

**Verbs.** *resolve* — obtain a canonical implementation from the ecosystem
root via authoritative manifests, never invent or copy a local equivalent.
*discover* — find reusable candidates in the Registry via selective key →
relevant index → bounded candidates, never a global scan. *assemble* — build
implementation records from the capability manifests during Publish and
register them. *register* — insert an implementation into the canonical
Registry, an assembly/Publish concern, never done by components or consumer
code. *execute* — run a selected executor for a request through the Bridge.
*verify* — run the resulting state headlessly through the harness and prove
every required check. *publish* — accept a verified resulting state, its
metadata, lineage, and Registry/index information as the new authoritative
state.

**Bridge trace stages.**

| Stage | Meaning |
|---|---|
| `validated` | Request passed structural validation. |
| `discovered` | Registry returned compatible implementations. |
| `policy_evaluated` | Policy evaluated all candidates. |
| `selected` | Selector chose a candidate for execution. |
| `executed` | Selected implementation completed successfully. |

On success all five stages appear in order; on failure only the stages
reached before the error appear (never empty — at minimum `validated`). The
trace is for debugging, auditing, and verification evidence; it is never
control flow.

## R1 — Hard identity

A capability id names the generic responsibility as `domain.operation` —
precise, concrete, and small-scale, never an app-bound or one-off label,
never a vague role name (`<domain>.manager`). "Generic" here describes the
nature of the responsibility: it is a single task that another cycle's
responsibility can reuse.

**Default to capability.** When a need exists and nothing in the Registry
satisfies it, the response is to create the capability — contract, manifest,
executor (R7) — not to write it as ad hoc local code. This applies even when
the need looks like plain infrastructure or plumbing (reading input,
tracking time, dispatching a command, sequencing a few other calls
together): if it is a distinct thing the application needs done, it is a
capability candidate first, local code only as a last resort. A responsibility
that composes several generic capabilities is itself a **specific**
capability (R4) — it gets its own contract declaring the generic ones as
`dependencies` and is reached through the Bridge like anything else; "it
composes other capabilities" is a reason to give it a contract, never a
reason to leave it local.

Exactly two things are never capabilities, and both are a structural floor,
not a judgment call: the single request-construction point itself (R6 — it
has to exist before any `BridgeRequest` can be built), and the literal
process entry point that starts the application (something has to run
before the Bridge can route anything to it). Nothing else qualifies for
"stays local" — not a business engine, not a clock, not an input reader, not
a dispatcher.

## R2 — Contract artifact

Every capability MUST materialize its contract as exactly ONE contract
artifact file — a versioned interface that machine-defines the capability.
Contract artifacts live under `contracts/` (one versioned file per
capability). The artifact is never inlined or fused into another file and
never lives implicitly in code only. Each responsibility has exactly one
contract; every operation belongs to exactly one contract. No bundled
catch-all capability, one-file "all capabilities" contract, or
one-component-does-everything.

## R3 — One contract, many manifests

A contract is not a manifest. One contract artifact → one capability
manifest → one executor-reference entry per implementation. The contract
artifact, the capability manifests that reference it, and the executors that
implement it are co-located in their owning package within the single
application — there is no separate area and no inside/outside partition.
Consumer code speaks capability ids + contract operations, never concrete
modules or classes; the application's single request-construction point is
where that speech happens.

## R4 — Dependencies and order

A capability contract MAY declare multiple required capability contracts in
its `dependencies` (a bigger contract can be composed of several
more-generic ones; do not atomize into micro-capabilities). A generic
capability is a small single-task component that is reusable across cycles;
it does not depend on a larger, single-purpose responsibility. Every
dependency MUST be more generic than the dependent contract (generics →
specifics). Build generics before specifics: the cycle discovers or creates
the small reusable components first, then composes the more specific
capability over them. A specific capability is a thin composition over
generic contracts — never a reimplementation of them.

## R5 — Verification hard-fails

A Verify pass (Phase 7) MUST fail when:

1. a declared capability has no materialized contract artifact;
2. a contract artifact is not placed under `contracts/`, or a component's
   package placement violates the single-application packaging layout;
3. a component's executor path is not a normal module path within the
   application, or a single file monolithically bundles independent
   responsibilities instead of composing small reusable components;
4. a process entry point (or a local helper it calls) branches on the
   content of an incoming request/event to decide an action, or itself
   calls two or more different capabilities and combines/sequences their
   results — that decision or composition logic is an unextracted
   capability, not entry-point plumbing. This governs the entry point's own
   code, not a capability's implementation: an executor may freely use any
   external library, framework, or network service it needs to do its job
   — the contract defines the WHAT, never the HOW inside the executor.

## R6 — Request-path discipline

Every consumer-visible request travels one canonical path:

```text
consumer code -> single request-construction point -> Bridge
  -> registry discovery -> policy -> selector -> component executor
```

Application code — any package's terminal/CLI input handling included —
NEVER builds a `BridgeRequest`, never calls `bridge.handle`, and never
imports a component module directly. Requests are constructed in exactly ONE
place in the application: the single request-construction point, which
speaks only capability ids + contract operations through the canonical
Bridge, and contains no component import and no registration logic. The
verification harness is the ONE exception to the *construction* rule: it
builds `BridgeRequest`s directly — that is exactly how it inspects the trace
— but it MUST still call the same resolved canonical `bridge.handle(...)`
and record only the Bridge's observed `response.trace` (R8). A component is
a registration-unaware executor reached only by the Bridge.

## R7 — Contract-first creation order

For every capability, construction proceeds in a strict order, and each
stage must be satisfiable before the next begins:

```text
1. contract artifact   (the what: operations, inputs, outputs, errors)
   -> validated against schemas/component-contract.schema.json
2. capability manifest (the binding: id + contract + operations + executor ref)
   -> validated against schemas/capability-manifest.schema.json;
      the executor reference may name a not-yet-existing module
3. concrete code       (the how: the registration-unaware executor)
   -> execute(operation, input, policy) -> output; never registers itself;
      never imports the Registry
```

The contract artifact (R2) is written and validated FIRST; the capability
manifest (R3) is written and validated SECOND; the concrete executor code is
written THIRD to satisfy the contract. No component code is written or
accepted unless its contract artifact and capability manifest already exist
and validate. Writing concrete code before its contract + manifest is a
violation — the contract is the specification the code is built against,
never a summary of already-written code. (Enforced by Gate 26.)

## R8 — The Bridge is the only execution interface

The resolved canonical Bridge is the ONLY way to execute any capability
operation — in any application package, in any script, and in the
verification harness alike. The harness may construct `BridgeRequest`s
directly (R6), but it must still call the SAME resolved canonical
`bridge.handle(...)` that the application uses, and it must record only the
Bridge's observed `response.trace`. Any direct invocation of a component
executor — or of an orchestrator that calls executors — outside the
canonical Bridge is a violation, in packages and in the harness alike. A
"verification" that executes capabilities without the Bridge, or that
records a trace it did not observe from the Bridge, is not verification and
the cycle is not complete.

## Extraction judgement (illustrates R1)

Extract the generic essence and leave only truly one-off values (not logic)
in configuration/composition. When analyzing a responsibility, separate what
is a plain generic operation from what is one-off, consumer-only meaning —
and remember R1's default: when in doubt, it's a capability.

| Appears one-off | Generic essence |
|---|---|
| A named capability that happens to first appear inside one feature | **`<domain>.<operation>`** — the same responsibility restated generically: e.g. a generic state store keyed by contract data, not a built-in feature type |
| A feature's own command vocabulary | **`<domain>.<operation>`** — a generic parser of `verb + args` with a configurable grammar |
| A feature-specific rendering/framing | **`<domain>.<operation>`** — a generic layout/render over plain data |
| Feature-specific validation/costing | **`<domain>.<operation>`** — a configurable bounds/validity check, where the costs, kinds, and rules are inputs, not built-ins |
| A scripted-command dispatcher (deciding what a parsed command does) | **`<domain>.<operation>`** — a capability in its own right; it may depend on other capabilities (R4), it does not stop being one for composing them |
| A clock/time source (so ticking is controllable, not wall-clock) | **`<domain>.<operation>`** — a capability with a swappable implementation (e.g. real vs. manual), exactly like any other; not a hidden application-only class |
| Raw input/device polling (reading a key, a sensor, a socket) | **`<domain>.<operation>`** — the I/O boundary is a capability too; "it's just plumbing" is not an exemption |
| A responsibility that sequences/composes several other capabilities (a "business engine") | **`<domain>.<operation>`** — a *specific* capability (R4): its contract declares the generic capabilities it composes as `dependencies`; composing others is why it has a contract, not why it's exempt from one |

The only two things that are never capabilities are named in R1: the single
request-construction point and the process entry point. Everything else —
however small, however plumbing-like, however specific to one consumer's
composition of other capabilities — gets a contract.

**Product-neutrality checkpoint.** Before writing the contract artifact, ask:

1. What is the responsibility without naming the requesting feature/consumer?
2. Can another consumer use the same contract?
3. Does the implementation contain assumptions specific to one consumer?
4. If yes, are those assumptions intrinsic to the responsibility?
5. If not, move them to composition/configuration/adapter boundaries.

Only after this checkpoint passes may the contract artifact be written; per
R7 the contract and manifest come first, and only then is the concrete code
implemented.

## The Bridge contract

The agent resolves and uses the ecosystem's existing canonical Bridge; the
Blueprint never prescribes a replacement implementation. Verify from
authoritative ecosystem artifacts: Bridge identity, its canonical request
path, validation stage, discovery stage, policy stage, selection stage,
execution handoff, and tracing/receipt requirements. A consumer of this path
must not reproduce the Bridge pipeline locally.

**Architecture.**

```text
consumer code -> BridgeRequest -> Bridge
  ├── Registry (discovery)
  ├── Policy (authorization)
  ├── Selector (routing)
  └── Executor (implementation) -> BridgeResponse -> consumer code
```

**Request / response / error format.**

```python
@dataclass(frozen=True)
class BridgeRequest:
    request_id: str           # unique request identifier
    capability_id: str        # ID of the capability to execute
    contract_version: str     # required contract version
    operation: str            # operation name from the contract
    input: dict[str, Any]     # operation input matching the contract
    policy_context: PolicyContext  # authorization context

@dataclass(frozen=True)
class BridgeResponse:
    request_id: str           # matches the request
    capability_id: str        # capability that was executed
    contract_version: str     # contract version that was used
    implementation_id: str    # specific implementation that ran
    output: dict[str, Any]    # operation output
    trace: tuple[str, ...]    # stage trace — evaluation evidence

@dataclass
class BridgeError(Exception):
    code: str                 # e.g. "BRIDGE_NO_IMPLEMENTATION"
    stage: str                # stage where the error occurred
    message: str              # human-readable message
    details: dict | None      # additional error context
```

**Usage pattern.**

1. Resolve the Bridge from the ecosystem root, never from consumer code:
   `Bridge(registry=..., policy=..., selector=...)`, each `resolve_from_ecosystem()`.
2. Create a request with real capability IDs from the ecosystem's
   authoritative manifests — never invented locally.
3. Handle the response and treat the trace as evidence, not control flow:
   check `"executed" in response.trace` for debugging only; a verification
   harness evaluates the full trace per R5/R8.
4. Handle `BridgeError` explicitly: `BRIDGE_ALL_IMPLEMENTATIONS_FAILED` (no
   healthy implementation), `BRIDGE_POLICY_DENIED` (not authorized),
   `BRIDGE_NO_IMPLEMENTATION` (capability not available) — never let it
   propagate unhandled.

**Bridge-specific rules.**

1. Use the canonical Bridge; never create a local copy or second request
   pipeline.
2. Never bypass the Bridge to call an implementation directly.
3. Include a unique `request_id` in every request.
4. Handle `BridgeError`; do not let it propagate unhandled.
5. Never use the trace for control flow.
6. Request `input` and response `output` are generic contract-shaped data;
   implementation-specific types must not cross the Bridge boundary.

## The Registry contract

The agent must resolve the existing Registry implementation from
authoritative ecosystem metadata; the Blueprint does not duplicate Registry
source code. The Registry must provide, directly or through its canonical
indexing layer: component/capability identity lookup; selective
classification lookup; contract/version lookup; implementation resolution;
lifecycle visibility; lineage/discoverability metadata; bounded candidate
retrieval; partition/shard-aware access where required by scale. If the
existing Registry cannot satisfy the Blueprint's scale requirements, that is
an ecosystem implementation gap to report and address — not a reason to
create a local Registry.

## Capability reference discipline

This makes MANDATORY the separation between a capability contract and the
component that implements it: a consumer that references a concrete
component is not independent of it and cannot reuse ecosystem infrastructure
without rewriting its own code. The repeating failure this prevents:

```python
# FORBIDDEN — the consumer names a concrete component module/class
from <component_module_a> import <TypeA>, register_<component_a>
register_<component_a>(self.registry)   # change <component_a> -> edit consumer
```

If changing the component that provides a capability requires editing any
consumer, the boundary is wrong.

**Core rule (R3, R6).** A consumer MUST reference only capability identity
(`capability_id`), contract version, and contract operations. It MUST NOT
reference an implementation module, package, class, or registration function
by name.

**What a consumer may reference:** capability contract IDs and versions;
contract operation names; contract input/output data shaped by the contract,
never by the implementing component's internal classes.

**What a consumer MUST NOT reference:** an implementation module or package
path; an implementation class or a registration function; an
implementation-specific type as contract data.

**Where registration lives.** Registration is NOT a component concern; it is
an ecosystem-assembly concern performed in the Publish phase (Phase 8, in
`1-CYCLE.md`). Three indirections make the rule enforceable:

1. **Capability contract data lives in a manifest, not in code.** The
   manifest declares the capability contract identity and, one per
   implementation, the component executor that provides it:

   ```yaml
   # valid against schemas/capability-manifest.schema.json
   capability_id: <capability-a>
   contract: <path-to-contract-artifact>
   contract_version: 1.0.0
   implementations:
     - implementation_id: <implementation-a>
       version: 1.0.0
       operations: [<operation-1>, <operation-2>]
       executor: <package>.components.<component_a>:execute
     - implementation_id: <implementation-b>   # SECOND implementation of the SAME contract
       version: 1.1.0
       operations: [<operation-1>, <operation-2>]
       executor: <package>.components.<component_b>:execute
   ```

   Two implementation entries declaring the same capability contract identity
   are two implementations of the ONE contract; the Registry offers both
   candidates to policy/selector. The contract and the consumers never
   change — only the manifests differ.

2. **Components are pure executors; they do not register.** A component
   module implements the capability and exposes only its
   `execute(operation, input, policy) -> output` callable. It does not
   import the Registry, construct an implementation record, or contain a
   `register` function.

3. **A generic assembler performs registration from the manifest.** During
   Publish (Phase 8), the assembler reads each capability manifest
   (validated against `schemas/capability-manifest.schema.json`), imports
   each entry's executor (`module:attr`), builds the implementation record,
   and registers it into the canonical Registry. Reference implementation:
   `bridge/assembler.py`. Swapping a component = editing the manifest, never
   the code or any consumer.

**Contract data is generic.** Inputs and outputs must be shaped by the
capability contract, not by the implementing component:

```python
entity_a = {"<attr_k>": "<value-k>", "class": "category-1", "enabled": True}
```

Keys like `class`, `count`, `status`, `step` are generic attributes declared
by the contract; the values are plain contract-shaped data, never
implementation types. Returning implementation classes across the Bridge
boundary is a violation.

**Implementation resolution chain.**

```text
Capability -> Contract -> Compatible implementation(s) -> Policy constraints
  -> Canonical selection -> Bridge execution
```

The agent must never treat a source file path as the runtime identity of a
capability. Runtime identity comes from the canonical Registry/implementation
model.

**Enforcement checklist for agents.**

1. Never register a capability from consumer code; registration belongs to
   the manifest + generic assembler during Publish.
2. Never embed a `register` function or Registry reference inside a
   component; a component exposes only its `execute` implementation.
3. A consumer must contain no `from <component_module> import ...` of
   implementation modules/classes or registration functions (R3/R6).
4. Contract inputs/outputs must be generic data (dicts/shapes from the
   contract), not implementation types.
5. Before accepting a design, verify: "If I replace the component that
   provides capability X, does consumer code change?" If yes, the design
   violates this discipline and MUST be corrected.
6. Component modules live behind a boundary (e.g. a `components/` group) and
   expose only their executor; registration is assembled externally.

This is a hard gate in the cycle (`1-CYCLE.md`): a cycle is not complete while
any consumer references a concrete component or any component contains
registration logic (Gates 13/16). The canonical Bridge is the only execution
interface (R8, Gates 27/28), and every component is built contract →
manifest → code (R7, Gate 26).

## Verification contract

The self-improving cycle publishes a **verified** state, not a written state.
This is the mandatory checklist for Phase 7 in `1-CYCLE.md`; the harness lives
alongside the result and is part of the resulting state. It exists because
assembled results routinely shipped with defects that purely "look right" on
paper: fail to start after a rename, crash on valid contract data, advertise
unreachable controls, or fill themselves up before the operator can act.

**A pass proves** — the harness runs headlessly (never requiring `isatty()`)
and must answer YES to all of:

1. **Assembly and startup.** The result resolves the canonical Bridge from
   the ecosystem root and starts/drives without manual steps.
2. **Capability decomposition and neutrality** (R2, R3, R6) — the harness
   evaluates them directly and MUST fail when any is violated.
3. **Every declared capability operation** is invoked over contract-shaped
   data through the SAME canonical Bridge the result resolves (R8), the
   response is contract-shaped, and the FULL ordered trace is asserted from
   the Bridge's own `response.trace` (missing stage, wrong order, or no
   `executed` = fail). The trace is observed, never constructed by the
   harness (Gate 28).
4. **Every consumer-visible behavior** is exercised through a scripted
   command stream (`("key", name)`, `("tick", None)`, `("wait", n)` — same
   handler the real console uses) and its observable effect asserted. A dead
   binding is a defect.
5. **Operator decision window.** A scripted operator action can interleave
   between observable automatic transitions, and unstoppered auto-advance can
   never exhaust the result's own action space. Auto-advance is rate-bounded
   and always leaves a permanent, operator-reachable remainder.
6. **Reactive same session.** The automatic loop AND injected input run in
   the same session; assert both state advanced AND the user's actions took
   effect.
7. **Invariants, not formatting.** Results are decided on observable
   behavior (state, counts, reached states, pause/speed/reset semantics),
   never on rendered layout.
8. **Record.** A machine-readable verification record
   (`schemas/verification-record.schema.json`) is written into the
   resulting state, referenceable from the cycle report, and green. Every
   capability operation's OBSERVED trace is persisted (`check.trace` — the
   Bridge's own `response.trace`, not invented); `check_id`s are unique.

**Determinism, not a wall clock.** Interactive/console results MUST expose a
scripted-input path and a controllable clock: ticking is driven by explicit
`tick`/`wait` events, never wall-clock time, and the scripted path shares
handlers with the real console path. If the scripted path bypasses real
logic, the harness verifies nothing. The clock that provides this is itself
a capability like any other (R1) — not a hidden, application-only class —
so a real and a manual/injectable time source are simply two implementations
of the same contract.

**Request-path discipline** (R6, R8) — canonical path `consumer code ->
Bridge -> registry -> policy -> selector -> executor`, one single
request-construction point, and the verification harness as the sole
exception to the *construction* rule (it builds `BridgeRequest`s directly to
inspect the trace, but still calls the same resolved canonical
`bridge.handle(...)` and records only the observed `response.trace`).

**Trace authenticity.** A recorded trace is valid only if it equals the
Bridge's own `response.trace` for that request. A "verification" that does
not execute the capability through the canonical Bridge, or that constructs
its own trace, is NOT verification (R8, Gate 27/28) — its record, however
green, does not prove the result and the state is not published.

**Regression discipline.** Every defect reported by a previous cycle MUST be
reproduced as a failing-check-first test: write it failing (red), fix the
defect, confirm it passes (green), keep it forever. At minimum, one named
check per observed defect class: dead-on-arrival assembly/startup;
capability op crash on valid data; unreachable controls; reactive loop
blocking or pre-empting input; automation exhausting the state; collapsed
capability decomposition; bypassed request path; trace not evaluated; forged
or bypassed Bridge trace (Gate 27/28); component written before its contract
artifact and capability manifest (R7, Gate 26).

**Fail closed.** Verification failure is the cycle's primary result. The
agent fixes the defect (or splits/reuses per Phase 4), re-runs the harness,
and only then proceeds to Publish. A state that cannot be assembled,
started, driven, decomposed correctly, or that fails any check is never
published. The record lives in the resulting state; the next cycle begins by
re-running the harness and accepts no goal until the record is green. A
record that omits traces, omits `check.trace` on a capability-operation
check, reuses check IDs, or was not regenerated by a green run is not a
valid verified state.

## Resolution table

The Blueprint is executable because it defines how to resolve implementation
rather than embedding a duplicate implementation:

`Blueprint requirement -> authoritative manifest -> canonical implementation -> contract`

| Primitive | Agent must resolve | Agent must not invent |
|---|---|---|
| Bridge | canonical execution boundary | local bridge |
| Registry | canonical discovery service/index | local registry |
| Policy | canonical policy stage | hidden local policy |
| Capability | canonical capability contract/model | ad-hoc capability format |
| Component | canonical component identity/contract | duplicate one-off generic component |
| Implementation | canonical implementation record | unregistered implementation |
| Connector | canonical connector contract | direct hidden dependency |
| Resource Exchange | canonical resource execution path when required | private resource runtime |
| Capability binding | manifests (one entry per implementation) + generic assembler (Publish phase) binding capability→implementation(s) | registration embedded in components or consumer code |
| Contract artifact | one materialized, versioned interface file per capability (R2; see `3-TEMPLATES.md`) | contract shapes living only implicitly in code |

Exact filesystem paths are intentionally resolved from authoritative
manifests rather than hard-coded by this Blueprint.
