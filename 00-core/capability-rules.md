# Capability Rules (R1–R10)

The complete, numbered set of invariant rules for the ARPAPED ecosystem. Every
other document references these rules by number; nothing else states a rule in
full. Definitions of terms live in `00-core/glossary.md`; the only worked
example is the extraction illustration in
`03-component-lifecycle/reusable-implementation-contract.md`.

## R1 — Hard identity

A capability id names the generic responsibility as `domain.operation` —
precise, concrete, and product-neutral (the shape `domain.operation`, with a
narrow generic domain and a precise operation), never the originating product
(`<product>.<operation>`), never a vague role name (`<domain>.manager`). A
product-prefixed id means the capability is bound to exactly one product and
cannot be reused by others. If a responsibility is genuinely
product-intrinsic (semantics that only that product defines), it stays
product-local logic; it is not a reusable capability and must not be
advertised as one.

## R2 — Contract artifact

Every capability MUST materialize its contract as exactly ONE contract
artifact file — a versioned interface that machine-defines the capability —
and every role→capability mapping resolves to a DISTINCT artifact. The
artifact is never inlined or fused into a product manifest and never lives
implicitly in code only. Each responsibility has exactly one contract; every
operation belongs to exactly one contract. No bundled catch-all capability,
one-file "all capabilities" contract, or one-component-does-everything.

## R3 — One contract, many manifests

A contract is not a manifest. One contract artifact → one capability manifest
→ one executor-reference entry per implementation. Capability manifests live
with the capability's generic footprint and are NEVER hosted, inlined, or
defined inside a product manifest, which references capability contract ids
ONLY (generic ids, never product-scoped ones). Consumer code references roles,
never concrete modules or classes; the product manifest maps each role to a
capability id. One contract therefore serves many consumers across products.

## R4 — Generic placement

Reusable implementations and capability manifests physically live in the
ecosystem's generic capability area (`generic/` at the ecosystem root), never
in a product directory. A capability-manifest executor path NEVER points into
a product package (`<product>.components.<component_a>:execute` is a violation; a
generic module path is required). Discovery and assembly resolve through the
canonical Registry; a product never points directly at another product's
package.

## R5 — Dependencies and order

A capability contract MAY declare multiple required capability contracts in
its `dependencies` (a bigger contract can be composed of several more-generic
ones; do not atomize into micro-capabilities). Every dependency MUST be more
generic than the dependent contract (generics → specifics); a generic
capability NEVER depends on a product-scoped capability; a product-specific
capability is a thin composition over generic contracts, not a
reimplementation of them. Build generics before specifics: the cycle
discovers or creates the generic layer first, then composes the specific
capability.

## R6 — Verification hard-fails

A Verify pass (Phase 7) MUST fail when:

1. a declared capability id is product-scoped (names the originating product,
   e.g. `<product>.<operation>`) and the responsibility is not genuinely
   product-intrinsic product-local logic;
2. a declared capability has no materialized contract artifact;
3. a capability-manifest executor path points into a product package;
4. a contract's `dependencies` reference a product-scoped capability.

## R7 — Request-path discipline

Every consumer-visible request travels one canonical path:

```text
consumer code -> single request-construction point -> Bridge
  -> registry discovery -> policy -> selector -> component executor
```

Consumer code — the product's terminal/CLI input handling included — NEVER
builds a `BridgeRequest`, never calls `bridge.handle`, and never imports a
component module directly. Requests are constructed in exactly ONE place in
the product: the single request-construction point, which resolves
roles→capability ids, speaks only capability ids + contract operations through
the canonical Bridge, and contains no component import and no registration
logic. The verification harness is the ONE exception to the *construction*
rule: it builds `BridgeRequest`s directly — that is exactly how it inspects
the trace — but it MUST still call the same resolved canonical
`bridge.handle(...)` and record only the Bridge's observed `response.trace`
(see **R9**). A component is a registration-unaware executor reached only by
the Bridge.

## R8 — Contract-first creation order

For every capability, construction proceeds in a strict order, and each stage
must be satisfiable before the next begins:

```text
1. contract artifact   (the what: operations, inputs, outputs, errors)
2. capability manifest (the binding: id + contract + operations + executor ref)
3. concrete code       (the how: the registration-unaware executor)
```

Rules: the contract artifact (R2) is written and validated FIRST; the
capability manifest (R3) is written and validated SECOND, declaring the
executor reference (which may name a not-yet-existing module); the concrete
executor code is written THIRD to satisfy the contract. No component code is
written or accepted unless its contract artifact and capability manifest
already exist and validate. Writing concrete code before its contract +
manifest is a violation — the contract is the specification the code is built
against, never a summary of already-written code.

## R9 — The Bridge is the only execution interface

The resolved canonical Bridge is the ONLY way to execute any capability
operation — in the product, in any script, and in the verification harness
alike. The harness may construct `BridgeRequest`s directly (R7), but it must
still call the SAME resolved canonical `bridge.handle(...)` that the product
uses, and it must record only the Bridge's observed `response.trace`. Any
direct invocation of a component executor — or of an orchestrator that calls
executors — outside the canonical Bridge is a violation, in the product and in
the harness. A "verification" that executes capabilities without the Bridge,
or that records a trace it did not observe from the Bridge, is not
verification and the cycle is not complete.

## R10 — Product encapsulation

A product package is a closed boundary. It contains ONLY:

1. consumer logic (per **R3**/**R7**, reached through the product's single
   request-construction point);
2. its product manifest;
3. its declared integration entry point.

It MUST NOT embed non-product concerns:

- ecosystem-assembly / registration code — no `assemble(...)`, no importing or
  touching the canonical Registry, and no hardcoded capability manifest or
  contract artifact paths (registration is an assembly/Publish concern, Phase 8);
- harness / test scaffolding — no injected event-stream or scripted-input
  classes whose only consumer is the verification harness (those live in the
  harness, Phase 7).

Conversely, any code OUTSIDE a product — Publish tooling, scripts, the verify
harness, other products — MUST reach the product only through its declared
public surface: the product manifest and the integration entry point. Importing
a product's internals (private functions, classes, or constants such as grid
dimensions) from Publish or Verify tooling is a violation; the Verify harness
drives the product through that public surface (or reads generic state from the
Bridge), never through product internals (see Gates 29–31).