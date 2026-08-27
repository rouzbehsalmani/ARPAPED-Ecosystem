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

## Phase 7 — Verify

**A cycle is not complete until the resulting state has been executed and verified, not merely written.**

Before publishing, the agent MUST run a verification pass over the accepted resulting state. This phase exists because an assembled product can be dead-on-arrival — it can fail to start, crash on a declared operation, or have consumer controls that are unreachable — while still looking complete on paper.

The verification pass MUST:

- **Run the result, headlessly.** Execute the assembled product with no manual interaction. A product that cannot be driven without a human at a real terminal is itself a defect.
- **Drive every consumer-visible behavior through a deterministic command stream.** Interactive/console consumers must expose a scripted-input path (a queue of keys/lines/labels) and a controllable clock, so user interaction is simulated exactly as a human would perform it. Simulating interaction is mandatory; real TTYs are non-deterministic and cannot be part of automated verification.
- **Exercise every declared capability operation** over contract-shaped data through the canonical Bridge, and assert the response is contract-shaped and its trace reaches `executed`.
- **Keep the product running while it is interactive.** For reactive products, run the automatic advancement loop AND inject user input in the same session, then assert both effects: state advanced AND the user's actions took effect. A loop that blocks all interaction while it "ticks" is a critical failed check (see `04-runtime/verification-contract.md`).
- **Assert invariants, not formatting.** Pass/fail is based on observable behavior (state, coverage, cell contents, pause/speed/reset semantics), not on the visual layout of output.
- **Apply the regression rule.** Every defect reported in a previous cycle MUST have a failing-check-first regression test; the fix is not accepted until that check passes. This prevents defects from shipping unchanged after manual reports.
- **Fail closed.** Any failure to start, to assemble, to execute a declared operation, or to receive a `validated…executed` trace stops the cycle. Do not publish an unverified state.
- **Record the result.** Write a verification record (see `schemas/verification-record.schema.json`) into the resulting state and reference it in the cycle report, so the next cycle can rediscover which behaviors are proven.

The verification harness and its checks are products of this phase, live alongside the product, and are part of the resulting state.

## Phase 8 — Publish

Publish the accepted, verified resulting state, component metadata, lineage, and Registry/index information.

This is where capability registration happens: component→capability binding is
performed by the capability manifest + a generic assembler into the canonical
Registry. Registration is an assembly concern of this phase — it must NOT be
embedded inside components or consumer code (see
`04-runtime/capability-reference-discipline.md`).

## Phase 9 — Return state

The resulting state becomes the input state of the next cycle.

No special knowledge of the previous goal may be required to reuse its outputs.

The next cycle starts with the state plus its verification record; it re-runs the
verification before accepting any new goal.