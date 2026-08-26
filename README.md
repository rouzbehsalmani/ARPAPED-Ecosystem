# ARPAPED Self-Improving Cycle Blueprint v1.1.0 — Agent Executable

This is the operational Blueprint for the ARPAPED self-improving cycle.

It is designed so an AI or human agent can enter an existing ARPAPED ecosystem, resolve its canonical implementations, understand how to work, discover reusable components at scale, create reusable implementations when necessary, integrate them through the canonical Bridge, publish the resulting state, and continue the process recursively.

## Important

This package does **not** copy or replace the ecosystem's Bridge, Registry, or other canonical implementations.

Instead, it gives the agent an explicit bootstrap and resolution protocol for finding and using those implementations from the authoritative ecosystem root.

## Start here

1. `00-core/AGENT-BOOTSTRAP.md`
2. `00-core/implementation-map.md`
3. `02-cycle/agent-execution-protocol.md`
4. `01-discovery/agent-discovery-algorithm.md`
5. `03-component-lifecycle/reusable-implementation-contract.md`
6. `04-runtime/bridge-implementation-contract.md`
7. `04-runtime/registry-implementation-contract.md`
8. `05-governance/agent-conformance-gates.md`

## For product creators

1. `03-component-lifecycle/product-manifest-template.md`
2. `03-component-lifecycle/component-contract-template.md`
3. `04-runtime/bridge-usage-guide.md`
4. `04-runtime/product-integration-example.md`

## This is not a product Blueprint

No MakCity-specific implementation is embedded here.
No Task A/B/C evaluation scenario is embedded here.
The Blueprint defines the reusable operating system for the self-improving cycle.
