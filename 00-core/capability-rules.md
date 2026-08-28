# Capability Rules (R1–R7)

The complete, numbered set of invariant rules for the ARPAPED ecosystem. Every
other document references these rules by number; nothing else states a rule in
full. Definitions of terms live in `00-core/glossary.md`; the only worked
example is the extraction illustration in
`03-component-lifecycle/reusable-implementation-contract.md`.

## R1 — Hard identity

A capability id names the generic responsibility as `domain.operation` —
precise and concrete (`grid.store`, `ascii.render`, `cli.parse`,
`rule.pricing`), never the originating product (`<product>.board`), never a
vague role name (`grid.manager`). A product-prefixed id means the capability
is bound to exactly one product and cannot be reused by others. If a
responsibility is genuinely product-intrinsic (e.g. a city's growth engine
with zone semantics), it stays product-local logic; it is not a reusable
capability and must not be advertised as one.

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
a product package (`<product>.components.board:execute` is a violation; a
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
   e.g. `<product>.board`) and the responsibility is not genuinely
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
logic. The verification harness is the ONE exception: it constructs requests
directly — that is exactly how it inspects the trace. A component is a
registration-unaware executor reached only by the Bridge.