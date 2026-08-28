# ARPAPED Self-Improving Cycle Blueprint v1.0.0 — Agent Executable

The operational Blueprint for the ARPAPED self-improving cycle.

**The model in one line:** every capability execution goes through one canonical
Bridge over contract-shaped data, and the cycle always verifies the result
headlessly before publishing it. The Bridge is the only execution interface for
any capability operation (R9), and every component is built contract → manifest
→ code (R8). Definitions for every term (capability, contract, component,
Bridge, trace, state, …) live in exactly one place: `00-core/glossary.md`.

## Important

This package does **not** copy or replace the ecosystem's Bridge, Registry, or
other canonical implementations. It gives an agent an explicit bootstrap and
resolution protocol for finding and using those implementations from the
authoritative ecosystem root.

## Start here

1. `00-core/AGENT-BOOTSTRAP.md`
2. `00-core/glossary.md` — definitions used everywhere
3. `00-core/capability-rules.md` — the numbered invariant rules (R1–R10)
4. `00-core/implementation-map.md`
5. `02-cycle/agent-execution-protocol.md` — the cycle; conformance gates live inside each phase
6. `01-discovery/agent-discovery-algorithm.md`
7. `03-component-lifecycle/reusable-implementation-contract.md`
8. `03-component-lifecycle/split-protocol.md`
9. `04-runtime/bridge-contract-and-guide.md`
10. `04-runtime/registry-implementation-contract.md`
11. `04-runtime/verification-contract.md` — what a Verify pass must prove
12. `05-governance/agent-conformance-gates.md` — phase → gate index
13. `05-governance/agent-report-template.md`

Manifests and contract artifacts are machine-validated against schemas in
`schemas/` (`capability-manifest`, `product-manifest`, `component-contract`),
and registration is performed by the generic assembler in `bridge/assembler.py`.

The cycle is hardened so a product cannot silently bypass the ecosystem:
**R8** mandates contract → manifest → code order, **R9** makes the canonical
Bridge the only execution interface (no direct executor/orchestrator calls,
including in the harness), and conformance gates **25–28** enforce a written
bootstrap resolution record, contract-first creation, Bridge-only execution,
and trace authenticity (traces must be the Bridge's observed `response.trace`).
**R10** adds product encapsulation (gates **29–31**): a product package holds
only consumer logic + its manifest + its integration entry point — no
assembly/registration code, no harness scaffolding — and is reached from
outside only through that public surface.

## For product creators

1. `00-core/glossary.md`
2. `00-core/capability-rules.md` — the numbered invariant rules
3. `03-component-lifecycle/product-manifest-template.md`
4. `03-component-lifecycle/component-contract-template.md`
5. `04-runtime/bridge-contract-and-guide.md` — request/response/error formats
6. `04-runtime/capability-reference-discipline.md` — mandatory: never reference a concrete component
7. `04-runtime/verification-contract.md` — mandatory: prove behavior headlessly before publishing

## This is not a product Blueprint

No product-specific implementation is embedded here.
No concrete product evaluation scenario is embedded here.
No worked product example exists here, by design — an example becomes a second
source of truth and invites literal copying; the templates and contract formats
are the shape.
The Blueprint defines the reusable operating system for the self-improving cycle.