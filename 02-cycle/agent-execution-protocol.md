# Agent Execution Protocol

The spine of the Blueprint. Every other document either feeds a phase or is
referenced by one. Aggregated conformance checklist:
`05-governance/agent-conformance-gates.md` (a pointer to this page).

## Cycle input

```text
current_state
goal
```

## Phase → gate map

| Phase | Gate(s) enforced |
|---|---|
| Bootstrap (before Phase 1) | 1, 2, 3, 25 |
| 1 — Understand | 3 |
| 1.5 — Component health check | 12 |
| 2 — Decompose the goal | 13, 21 (by construction) |
| 3 — Discover | 4, 5 |
| 4 — Decide | 6 |
| 5 — Implement | 7, 15, 16, 26 |
| 6 — Integrate | 10, 13, 24, 27, 30, 31 |
| 7 — Verify | 17, 18, 19, 20, 21, 22, 23, 24, 27, 28, 31 |
| 8 — Publish | 8, 9, 14, 29 |
| 9 — Return state | 11 |

A gate answered NO means the cycle is not complete.

## Bootstrap — before Phase 1

**What.** Enter the ecosystem, resolve what is canonical, and accept only then
the goal.

**Do.** Follow `00-core/AGENT-BOOTSTRAP.md`: establish the ecosystem root,
discover authoritative metadata, build the implementation map, load operating
rules, resolve the current state, accept the goal.

**Non-negotiables.** Gates 1, 2, 3, 25:

1. Did I resolve the canonical Bridge? (From the ecosystem root, never a
   product directory.)
2. Did I resolve the canonical Registry?
3. Did I avoid creating a parallel Bridge or Registry?
25. Did I emit and reference a written ecosystem-resolution record naming the
    canonical Bridge and Registry (and the implementation map)? The canonical
    Bridge is the only execution interface for every capability operation —
    in the product, scripts, and harness (R9).

Plus the bootstrap hard prohibitions: no private Bridge/Registry, no copying
the ecosystem into a product, no silently replacing an authoritative
implementation, no global Registry scans, no treating a local manifest as
ecosystem integration proof.

**Produces.** Resolved ecosystem root + loaded rules + accepted `goal` + a
written `ecosystem-resolution` record.

## Phase 1 — Understand

**What.** Resolve the authoritative ecosystem implementation map
(`00-core/implementation-map.md`).

**Do.** Identify the canonical requirements → manifest → implementation →
contract chain for every primitive the goal touches. Do not infer missing
architecture from product code if the ecosystem already defines it.

**Non-negotiables.** Gate 3 (above): a second ecosystem copy or an invented
arrangement is a violation.

**Produces.** A map of what already exists and what the goal still requires.

## Phase 1.5 — Component health check

**What.** Audit owned components for split opportunities before decomposing.

**Do.** For each component the agent owns or modified: (1) multiple independent
responsibilities? (2) grown beyond one coherent contract? (3) parts reusable
independently? (4) mixed concerns that should be separate?

**Non-negotiables.** Gate 12: did I audit existing components before
proceeding? If any answer is YES, split before proceeding (see
`03-component-lifecycle/split-protocol.md`). Record the split decision and its
reason.

**Produces.** A split decision (or a cleared health check).

## Phase 2 — Decompose the goal

**What.** Split the goal into independently meaningful responsibilities.

**Do.** A decomposition unit is a **capability contract** built per R2/R3: one
responsibility = one capability ID = one contract artifact, implemented by one
or more implementations, each bound by its own capability-manifest entry
referencing the same contract. A (bigger) contract MAY require multiple other
capability contracts in its `dependencies` per R5 — do not split into arbitrary
micro-tasks and do not bundle unrelated responsibilities into a catch-all.
Identity per R1.

**Non-negotiables.** Gates 13 and 21 by construction: this decomposition is
what Verify (Phase 7) later proves survived integration. Creation order is
generics → specifics per R5.

**Produces.** A list of responsibilities, each with a candidate contract
artifact.

## Phase 3 — Discover

**What.** Find reusable candidates for each responsibility.

**Do.** Run the scalable discovery algorithm (`01-discovery/agent-discovery-algorithm.md`):
extract responsibilities → selective discovery key → relevant index → bounded
candidates → filter by contract/version/lifecycle/policy → prefer direct
reuse → widen scope only as needed → only then consider split or creation.
Search the generic capability area per R4 BEFORE considering a product-bound
design: for every responsibility, look for the generic essence (R1) that
already exists or must be created generically.

**Non-negotiables.** Gates 4 and 5:

4. Did I discover existing reusable responsibilities before creating new ones?
5. Was discovery bounded and index-driven (`selective key -> relevant index ->
   bounded candidates`), never `O(total_components)` and never a global scan?

**Produces.** A bounded candidate set per responsibility, with evidence
(identity, contract, version, compatibility, lifecycle, lineage, scope).

## Phase 4 — Decide

**What.** Choose exactly one action per responsibility.

**Do.** For every responsibility pick one of:

| Decision | When |
|---|---|
| reuse | Existing candidate satisfies the requirement. |
| compose | Two or more existing capabilities together satisfy it. |
| split/refactor | An existing component holds this responsibility but mixed with others. |
| create | Nothing reusable exists and no valid creation path is blocked. |

**Non-negotiables.** Gate 6: prefer reuse over duplication. Record the reason
for every decision, and for every `create` decision record the product-neutrality
verdict (generic id + a generic home per R1/R4) and the generics-first order it
imposes (R5).

**Produces.** A decision table per responsibility.

## Phase 5 — Implement

**What.** Create or adjust components only where the decision requires it.

**Do.** For a new component, follow creation order per **R8** — contract
artifact first (validated), then capability manifest (validated), then the
concrete code — and satisfy R1, R2, R4, R5 — see `00-core/capability-rules.md`
— and run the product-neutrality checkpoint
(`reusable-implementation-contract.md`). Fill the contract artifact
(`component-contract-template.md`). Executor shape
`execute(operation, input, policy) -> output`; discoverability metadata,
version and lineage. Components never register themselves and never import the
Registry (Publish phase owns registration).

**Non-negotiables.** Gates 7, 15, 16, 26:

7. If I created a component, does it satisfy R1, R2, R4 — generic identity,
   a contract artifact, and a non-product home with a non-product executor
   path?
15. Are contract inputs/outputs generic contract-shaped data, not implementation
    types?
16. Do my components expose only their executor, without importing the Registry
    or embedding a `register` function?
26. Did I write and validate the contract artifact and capability manifest
    BEFORE writing the concrete code (R8)? No code exists whose contract +
    manifest were not already in place and valid.

**Produces.** Components + contracts + lineage, all registration-unaware, each
built contract → manifest → code.

## Phase 6 — Integrate

**What.** Wire everything through the canonical Bridge and Registry — no second
request pipeline.

**Do.** Consumers speak only role→capability IDs + contract operations through
the Bridge (`04-runtime/bridge-contract-and-guide.md`,
`04-runtime/capability-reference-discipline.md`). Request path per R7: every
consumer request — terminal/CLI input handling included — funnels through the
product's single request-construction point.

**Non-negotiables.** Gates 10, 13, 24, 27, 30, 31:

10. Is the resulting implementation compatible with runtime resolution?
13. Do my consumers reference only capability contracts, never concrete
    component modules/classes/registration functions?
24. Does the request path hold per R7 (one canonical consumer → Bridge path
    through a single request-construction point)?
27. Is the canonical Bridge the ONLY path that executes any capability
    operation — no direct executor/orchestrator calls in the product, in
    scripts, or in the harness (R9)?
30. Is the product package free of harness/test scaffolding — no injected
    event-stream or scripted-input class whose only consumer is the verify
    harness (R10)?
31. Is the product reached externally ONLY through its declared public surface
    (product manifest + integration entry point) — no external import of
    product private functions, classes, or constants (R10)?

Every integration MUST inspect the Bridge trace on every response
(`validated → discovered → policy_evaluated → selected → executed`). A trace
that does not reach `executed` is an integration failure to resolve before
publishing. Traces are the Bridge's observed `response.trace`, never invented
(Gate 28).

**Produces.** An integrated product whose every request traverses the canonical
path.

## Phase 7 — Verify

**What.** Prove the resulting state by executing it headlessly. A cycle is not
complete until the result has been executed and verified, not merely written.

**Do.** Run the verification harness (`04-runtime/verification-contract.md`) —
the checklist there is binding: assembly/startup, capability decomposition
(R2/R3) incl. its product-neutrality hard fails (R6), every capability
operation with its full ordered trace over the SAME resolved canonical Bridge
the product uses (R9), every consumer control through a scripted stream, an
operator decision window, a reactive loop and injected input in the same
session, regression checks for every previously reported defect, and a
machine-readable verification record written into the resulting state.

**Non-negotiables.** Gates 17–24, 27, 28, 31:

17. Did I run the result through a verification harness — headlessly, no real
    terminal required?
18. Does the harness exercise every declared capability operation over
    contract-shaped data with every trace reaching `executed`?
19. Does it simulate every consumer-visible interaction via a scripted command
    stream and assert its observable effect, running an automatic loop and
    injected input in the SAME session?
20. Does every previously-reported defect have a regression check that now
    PASSES, and is a verification record written into the resulting state and
    referenced in the cycle report?
21. Does the resulting state preserve capability decomposition (R2/R3) AND
    product neutrality (R6)?
22. Is the full ordered Bridge trace captured, asserted, and persisted in the
    record (`check.trace`) for every capability operation?
23. Is the operator decision window guaranteed (action interleaves between
    automatic transitions; auto-advance never exhausts the state)?
24. Request-path discipline (R7) holds in the harness too: its direct `BridgeRequest`
    construction is specifically for trace evaluation, and it still calls the
    same resolved canonical `bridge.handle(...)` — ordinary product code never
    does this.
27. Is the canonical Bridge the ONLY path that executes any capability
    operation in the harness — no direct executor/orchestrator calls (R9)?
28. Does every recorded capability trace equal the observed Bridge
    `response.trace` — copied, never invented or bypassed? A forged or
    self-constructed trace is a hard fail (R9).
31. Does the harness drive the product only through its declared public surface
    (product manifest + integration entry point) and read generic state from
    the Bridge — never importing product private functions, classes, or
    constants (R10)? Its direct `BridgeRequest` construction (R7 exception) is
    unchanged: it still calls the same resolved canonical `bridge.handle(...)`
    and records only the observed `response.trace`.

**Fail closed.** Any of the above failing stops the cycle: fix (or split/reuse
per Phase 4), re-run the harness, and only then proceed. An unverified state is
never published.

**Produces.** A verification harness, a green (or failed) verification record
in the resulting state (`schemas/verification-record.schema.json`).

## Phase 8 — Publish

**What.** Publish the accepted, verified resulting state.

**Do.** Publish component metadata, lineage, and Registry/index information.
Register every capability: the capability manifests (one entry per
implementation) + generic assembler build each implementation record and
register it into the canonical Registry. Publish the decomposition per R3 — one
contract per capability, referenced by its one or more capability-manifest
entries; the product manifest records only references (roles → capability
IDs).

**Non-negotiables.** Gates 8, 9, 14, 29:

8. If I split a component, did I preserve lineage and update discoverability?
9. Is the resulting component discoverable through the canonical Registry?
14. Is registration performed by the manifest + a generic assembler, so
    components contain no registration logic and swapping an implementation
    requires no consumer code change?
29. Is the product package free of ecosystem-assembly/registration code — no
    `assemble(...)`, no Registry import, no hardcoded capability manifest or
    contract artifact paths (R10)? Registration lives in the manifest + generic
    assembler at the ecosystem level; Publish tooling does not import a
    product's registration module.

**Produces.** A discoverable, registered, verified resulting state.

## Phase 9 — Return state

**What.** Make the resulting state the input of the next cycle.

**Do.** Ensure no special knowledge of the previous goal is required to reuse
the outputs; the next cycle starts from state + verification record, re-runs
verification, and only then accepts a new goal.

**Non-negotiables.** Gate 11: is the resulting state sufficient for the next
cycle to rediscover the work without private agent memory?

**Produces.** The next cycle's `current_state`.