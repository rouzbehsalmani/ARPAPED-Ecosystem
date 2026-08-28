# Agent Conformance Gates

Pointer. The 31 gates are part of the cycle: each one lives inside the phase it
enforces in `02-cycle/agent-execution-protocol.md`, and the phase → gate map is
at its top.

| Phase | Gates |
|---|---|
| Bootstrap | 1–3, 25 |
| 1 — Understand | 3 |
| 1.5 — Health check | 12 |
| 2 — Decompose | 13, 21 |
| 3 — Discover | 4, 5 |
| 4 — Decide | 6 |
| 5 — Implement | 7, 15, 16, 26 |
| 6 — Integrate | 10, 13, 24, 27, 30, 31 |
| 7 — Verify | 17–24, 27, 28, 31 |
| 8 — Publish | 8, 9, 14, 29 |
| 9 — Return | 11 |

These are Blueprint conformance gates, not a product test suite. A NO on any
gate means the cycle is not complete.

## Gates 25–28 (v1.1)

Gates 25–28 close the gaps that let a capability product bypass the Bridge
ecosystem entirely and write concrete code before any contract or manifest.

25. **Bootstrap resolution record.** Did I emit and reference a written,
    resolvable ecosystem-resolution record naming the canonical Bridge and
    Registry (and the implementation map)?
26. **Contract-first creation order (R8).** For every created component, did I
    write and validate the contract artifact and capability manifest BEFORE
    writing the concrete code?
27. **Bridge is the only execution interface (R9).** Is the canonical Bridge
    the ONLY path that executes any capability operation — no direct
    executor/orchestrator calls in the product OR the harness?
28. **Trace authenticity.** Does every recorded capability trace equal the
    observed Bridge `response.trace` (copied, not invented or bypassed)?

## Gates 29–31 (v1.1)

Gates 29–31 enforce **R10 (product encapsulation)**: a product package is a
closed boundary holding only consumer logic, its product manifest, and its
integration entry point — and it is reached from outside only through that
public surface.

29. **Product encapsulation — no in-package assembly.** Does the product
    package contain no registration/Registry/`assemble` code and no hardcoded
    capability manifest or contract artifact paths (registration lives in the
    manifest + generic assembler, Phase 8)? Publish tooling may not import a
    product's registration module.
30. **Product encapsulation — no in-package harness scaffolding.** Does the
    product package contain no harness/test scaffolding (no injected
    event-stream or scripted-input class whose only consumer is the verify
    harness)? Such scaffolding lives in the harness (Phase 7).
31. **Product encapsulation — inbound/outbound coupling.** Is the product
    reached externally ONLY through its declared public surface (product
    manifest + integration entry point) — no external import of product
    private functions, classes, or constants (e.g. grid dimensions) from
    Publish or Verify tooling?