# ARPAPED Self-Improving Cycle Blueprint v1.1.0 — Agent Executable

The operational Blueprint for the ARPAPED self-improving cycle.

**The model in one line:** every capability execution goes through one canonical
Bridge over contract-shaped data, and the cycle always verifies the result
headlessly before publishing it. Definitions for every term (capability,
contract, component, Bridge, trace, state, …) live in exactly one place:
`00-core/glossary.md`.

## Important

This package does **not** copy or replace the ecosystem's Bridge, Registry, or
other canonical implementations. It gives an agent an explicit bootstrap and
resolution protocol for finding and using those implementations from the
authoritative ecosystem root.

## Start here

1. `00-core/AGENT-BOOTSTRAP.md`
2. `00-core/glossary.md` — definitions used everywhere
3. `00-core/implementation-map.md`
4. `02-cycle/agent-execution-protocol.md` — the cycle; conformance gates live inside each phase
5. `01-discovery/agent-discovery-algorithm.md`
6. `03-component-lifecycle/reusable-implementation-contract.md`
7. `03-component-lifecycle/split-protocol.md`
8. `04-runtime/bridge-contract-and-guide.md`
9. `04-runtime/registry-implementation-contract.md`
10. `04-runtime/verification-contract.md` — what a Verify pass must prove
11. `05-governance/agent-conformance-gates.md` — phase → gate index
12. `05-governance/agent-report-template.md`

## For product creators

1. `00-core/glossary.md`
2. `03-component-lifecycle/product-manifest-template.md`
3. `03-component-lifecycle/component-contract-template.md`
4. `04-runtime/bridge-contract-and-guide.md` — request/response/error formats
5. `04-runtime/capability-reference-discipline.md` — mandatory: never reference a concrete component
6. `04-runtime/verification-contract.md` — mandatory: prove behavior headlessly before publishing

## This is not a product Blueprint

No product-specific implementation is embedded here.
No Task A/B/C evaluation scenario is embedded here.
No worked product example exists here, by design — an example becomes a second
source of truth and invites literal copying; the templates and contract formats
are the shape.
The Blueprint defines the reusable operating system for the self-improving cycle.