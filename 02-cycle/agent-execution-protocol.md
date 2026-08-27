# Agent Execution Protocol

## Cycle input

```text
current_state
goal
```

## Phase 1 — Understand

Resolve the authoritative ecosystem implementation map.

Do not infer missing architecture from product code if the canonical ecosystem already defines it.

## Phase 1.5 — Component Health Check

Before decomposing the goal, audit existing components for split opportunities.

For each component the agent owns or modified in previous cycles:

1. Does the component have multiple independent responsibilities?
2. Has the component grown beyond a single coherent contract?
3. Can parts of the component be discovered and reused independently?
4. Does the component mix concerns that should be separate?

If any answer is YES, split the component before proceeding. Record the split decision and its reason.

## Phase 2 — Decompose the goal

Decompose only into independently meaningful responsibilities.

A decomposition unit should have an independent contract and potential lifecycle.

Do not split a requirement into arbitrary micro-tasks.

## Phase 3 — Discover

Run the scalable discovery algorithm for each responsibility.

## Phase 4 — Decide

For every responsibility choose exactly one:

1. reuse;
2. compose;
3. split/refactor;
4. create.

The reason for the decision must be recorded.

## Phase 5 — Implement

If creating a component:

- define its responsibility;
- define its generic contract;
- remove product-specific assumptions where possible;
- define dependencies;
- define discoverability metadata;
- define version and lineage;
- implement through canonical ecosystem boundaries.

## Phase 6 — Integrate

Integrate through the canonical Bridge and Registry contracts.

Do not introduce a second request pipeline.

The agent MUST inspect the Bridge trace on every response. A trace that does not reach `executed` indicates an integration failure that must be resolved before publishing.

## Phase 7 — Publish

Publish the accepted resulting state, component metadata, lineage, and Registry/index information.

## Phase 8 — Return state

The resulting state becomes the input state of the next cycle.

No special knowledge of the previous goal may be required to reuse its outputs.
