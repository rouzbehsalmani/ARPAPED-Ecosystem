# The Self-Improving Cycle

Building something concrete right now? See `WALKTHROUGH.md` — it turns the
phases below into literal file paths and commands. This file is the
phase/gate reference it points back to.

The operational spine of the Blueprint. Every capability execution goes through
one canonical Bridge over contract-shaped data, and the cycle always verifies
the result headlessly before publishing it. Definitions and the numbered
invariant rules (R1–R8) it enforces live in `RULES.md`; nothing here restates
a rule in full — every phase cites the rule number it enforces.

## Cycle input

```text
current_state
goal
```

## Phase → gate map

| Phase | Gate(s) enforced |
|---|---|
| 0 — Bootstrap | 1, 2, 3, 25 |
| 1 — Understand | 3 |
| 1.5 — Component health check | 12 |
| 2 — Decompose the goal | 13, 21 (by construction) |
| 3 — Discover | 4, 5 |
| 4 — Decide | 6 |
| 5 — Implement | 7, 15, 16, 26 |
| 6 — Integrate | 10, 13, 24, 27 |
| 7 — Verify | 17, 18, 19, 20, 21, 22, 23, 24, 27, 28 |
| 8 — Publish | 8, 9, 14 |
| 9 — Return state | 11 |

A gate answered NO means the cycle is not complete.

## Phase 0 — Bootstrap

**What.** Enter the ecosystem, resolve what is canonical, and accept only then
the goal. Mandatory before any other phase, for any human or AI agent.

**Do.**

1. Establish the ecosystem root supplied by the operator; never create a
   second copy.
2. Starting there, discover the authoritative ecosystem profile/manifest,
   canonical Bridge implementation, Registry implementation and records,
   policy implementation, capability/component contracts, implementation
   manifests, and connector contracts. Use the repository's own manifests as
   the authority for exact paths and versions. If two authoritative-looking
   implementations conflict, STOP and report the ambiguity — do not silently
   choose one.
3. Build an implementation map: every required primitive (execution boundary,
   discovery/Registry, policy, capability model, component model, packaging
   model, implementation model, connector model, resource execution) must
   resolve to an authoritative artifact in the ecosystem (see the resolution
   table in `RULES.md`).
4. Write a resolvable **ecosystem-resolution record** — machine-readable
   (e.g. a small JSON artifact or a dedicated report section) — naming at
   minimum the resolved canonical Bridge, Registry, policy stage, selector,
   the `contracts/` area, and the root, plus the implementation map. Without
   it the cycle cannot proceed: a resolved-but-unrecorded Bridge is treated as
   unresolved. The record is referenced in the cycle report (`TEMPLATES.md`).
5. Load the operating rules: this Blueprint, the ecosystem's authoritative
   manifests, canonical Bridge/Registry contracts, immutable architectural
   decisions, capability/component reuse rules, repository-local policies.
   Local instructions may refine implementation details but never contradict
   canonical ecosystem rules.
6. Resolve the current state from the authoritative discoverable state of the
   ecosystem — never from private conversation memory.
7. Only after steps 1–6 are complete, accept the requested goal as the cycle
   input.
8. Plan the application's package structure before writing any code: contract
   artifacts under `contracts/`; component executors and their capability
   manifests co-located in their owning packages; small generic (single-task,
   reusable) components built and composed before the specific
   responsibilities layered over them (generics → specifics, R4); entry
   points and the single request-construction point at the application level
   (R6); tests and the verification harness outside the application packages.
   Never write an application responsibility as a single monolith file mixing
   independent responsibilities, and never reimplement a small reusable
   component instead of composing it.

**Hard prohibitions.** The agent MUST NOT: create a parallel Bridge; create a
private Registry; copy the entire ecosystem into a package; implement a small
generic responsibility as one-off package-local logic merely for convenience;
globally scan the Registry as the normal discovery mechanism; silently replace
an authoritative implementation; write a monolith file mixing independent
responsibilities; embed registration logic inside an application package
(registration is an assembly/Publish concern, Phase 8).

**Non-negotiables.** Gates 1, 2, 3, 25:

1. Did I resolve the canonical Bridge? (From the ecosystem root.)
2. Did I resolve the canonical Registry?
3. Did I avoid creating a parallel Bridge or Registry?
25. Did I emit and reference a written ecosystem-resolution record naming the
    canonical Bridge and Registry (and the implementation map)? The canonical
    Bridge is the only execution interface for every capability operation —
    in any package, in scripts, and in the harness (R8).

**Produces.** Resolved ecosystem root + loaded rules + accepted `goal` + a
written ecosystem-resolution record.

## Phase 1 — Understand

**What.** Resolve the authoritative ecosystem implementation map.

**Do.** Identify the canonical requirements → manifest → implementation →
contract chain for every primitive the goal touches (resolution table in
`RULES.md`). Do not infer missing architecture from package code if the
ecosystem already defines it.

**Non-negotiables.** Gate 3: a second ecosystem copy or an invented
arrangement is a violation.

**Produces.** A map of what already exists and what the goal still requires.

## Phase 1.5 — Component health check

**What.** Audit owned components for split opportunities before decomposing —
splitting is a self-improvement operation, not an ordinary coding convenience.

**Do.** For each component the agent owns or modified, check for:

- responsibility count > 1;
- contract complexity beyond a single coherent purpose;
- mixed concerns that should be separate;
- reuse potential of sub-parts that could be discovered independently.

This audit runs proactively every cycle; the same checks apply reactively
whenever an existing component receives a new requirement and boundary
analysis shows a responsibility could independently be contracted, discovered,
reused, versioned, or lifecycled. If any check is true: define child
contracts, create child components, rewire consumers, update the
Registry/index, and preserve lineage before proceeding. Do not split solely
because the source file is large.

**Non-negotiables.** Gate 12: did I audit existing components before
proceeding? Record the split decision and its reason.

**Produces.** A split decision (or a cleared health check).

## Phase 2 — Decompose the goal

**What.** Split the goal into independently meaningful responsibilities.

**Do.** A decomposition unit is a **capability contract** built per R2/R3: one
responsibility = one capability ID = one contract artifact, implemented by one
or more implementations, each bound by its own capability-manifest entry
referencing the same contract. A bigger contract MAY require multiple other
capability contracts in its `dependencies` per R4 — do not split into
arbitrary micro-tasks and do not bundle unrelated responsibilities into a
catch-all. Identity per R1.

**Non-negotiables.** Gates 13 and 21 by construction: this decomposition is
what Verify (Phase 7) later proves survived integration. Creation order is
generics → specifics per R4.

**Produces.** A list of responsibilities, each with a candidate contract
artifact.

## Phase 3 — Discover

**What.** Find reusable candidates for each responsibility, bounded and
index-driven — never a scan of every component.

**Do.**

1. Extract required responsibilities from the goal.
2. For each, construct the most selective valid discovery key.
3. Resolve the relevant Registry index/shard.
4. Retrieve a bounded candidate set.
5. Filter by contract compatibility, then by version/lifecycle constraints,
   then by policy/execution constraints.
6. Prefer direct reusable candidates.
7. If none satisfy the requirement, widen the discovery scope by one level and
   repeat until a bounded candidate set is found or the allowed scope is
   exhausted.
8. Only then consider split/refactor or creation (Phase 4).

The normal query path is `selective key -> relevant index -> bounded
candidates`, never `all components -> local filtering` — discovery must not
become `O(total_components)`. Every selected candidate must be explainable by
identity, contract, version, compatibility, lifecycle, lineage, and discovery
scope. If a required capability cannot be resolved and no valid creation path
exists, fail closed and report the unresolved requirement.

A reusable component is not fully integrated merely because it can be
imported or located: an accepted component's source implementation, canonical
contract, discoverability metadata, Registry/index entry, and
runtime-resolvable implementation must form one coherent identity, resolvable
through the same Registry model the Bridge uses at runtime — never a local
shortcut.

**Non-negotiables.** Gates 4 and 5:

4. Did I discover existing reusable responsibilities before creating new ones?
5. Was discovery bounded and index-driven, never `O(total_components)` and
   never a global scan?

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
for every decision, and for every `create` decision record the
small-reusability verdict (a generic single-task id per R1) and the
generics-first order it imposes (R4).

**Produces.** A decision table per responsibility.

## Phase 5 — Implement

**What.** Create or adjust components only where the decision requires it.

**Do.** For a new component, follow creation order per R7 — contract artifact
first (validated against `schemas/component-contract.schema.json`), then
capability manifest (validated against `schemas/capability-manifest.schema.json`,
declaring the executor reference, which may name a not-yet-existing module),
then the concrete registration-unaware executor code
(`execute(operation, input, policy) -> output`) — and satisfy R1–R4. Before
writing the contract, apply the product-neutrality checkpoint in `RULES.md`
to confirm the responsibility is genuinely generic, not a one-off dressed up
as a capability. Components never register themselves and never import the
Registry (Publish phase owns registration, per R8's indirection rules in
`RULES.md`).

**Non-negotiables.** Gates 7, 15, 16, 26:

7. If I created a component, does it satisfy R1, R2, R3 — a generic
   single-task identity, a contract artifact placed under `contracts/`, and a
   normal executor module path within the application?
15. Are contract inputs/outputs generic contract-shaped data, not
    implementation types?
16. Do my components expose only their executor, without importing the
    Registry or embedding a `register` function?
26. Did I write and validate the contract artifact and capability manifest
    BEFORE writing the concrete code (R7)? No code exists whose contract +
    manifest were not already in place and valid.

**Produces.** Components + contracts + lineage, all registration-unaware, each
built contract → manifest → code.

## Phase 6 — Integrate

**What.** Wire everything through the canonical Bridge and Registry — no
second request pipeline.

**Do.** Consumers speak only capability IDs + contract operations through the
Bridge (`RULES.md`). Request path per R6: every consumer request — including
terminal/CLI input handling — funnels through the application's single
request-construction point.

**Non-negotiables.** Gates 10, 13, 24, 27:

10. Is the resulting implementation compatible with runtime resolution?
13. Do my consumers reference only capability contracts, never concrete
    component modules/classes/registration functions?
24. Does the request path hold per R6 (one canonical consumer → Bridge path
    through a single request-construction point), with application packages
    free of registration code (registration lives in the manifest + generic
    assembler, Gate 14) and free of harness/test scaffolding (tests and the
    verify harness live outside the application packages)?
27. Is the canonical Bridge the ONLY path that executes any capability
    operation — no direct executor/orchestrator calls in any package, in
    scripts, or in the harness (R8)?

Every integration MUST inspect the Bridge trace on every response
(`validated → discovered → policy_evaluated → selected → executed`). A trace
that does not reach `executed` is an integration failure to resolve before
publishing. Traces are the Bridge's observed `response.trace`, never invented
(Gate 28).

**Produces.** An integrated application whose every request traverses the
canonical path.

## Phase 7 — Verify

**What.** Prove the resulting state by executing it headlessly. A cycle is
not complete until the result has been executed and verified, not merely
written. The full checklist a pass must satisfy lives in `RULES.md`
("Verification contract"); this phase runs it.

**Do.** Run the verification harness: assembly/startup, capability
decomposition (R2/R3) incl. its small-reusability hard fails (R5), every
capability operation with its full ordered trace over the SAME resolved
canonical Bridge the application uses (R8), every consumer control through a
scripted stream, an operator decision window, a reactive loop and injected
input in the same session, regression checks for every previously reported
defect, and a machine-readable verification record written into the
resulting state.

**Non-negotiables.** Gates 17–24, 27, 28:

17. Did I run the result through a verification harness — headlessly, no
    real terminal required?
18. Does the harness exercise every declared capability operation over
    contract-shaped data with every trace reaching `executed`?
19. Does it simulate every consumer-visible interaction via a scripted
    command stream and assert its observable effect, running an automatic
    loop and injected input in the SAME session?
20. Does every previously-reported defect have a regression check that now
    PASSES, and is a verification record written into the resulting state
    and referenced in the cycle report?
21. Does the resulting state preserve capability decomposition (R2/R3) AND
    small-reusability (R5)?
22. Is the full ordered Bridge trace captured, asserted, and persisted in the
    record (`check.trace`) for every capability operation?
23. Is the operator decision window guaranteed (action interleaves between
    automatic transitions; auto-advance never exhausts the state)?
24. Request-path discipline (R6) holds in the harness too: its direct
    `BridgeRequest` construction is specifically for trace evaluation, and it
    still calls the same resolved canonical `bridge.handle(...)` — ordinary
    application code never does this.
27. Is the canonical Bridge the ONLY path that executes any capability
    operation in the harness — no direct executor/orchestrator calls (R8)?
28. Does every recorded capability trace equal the observed Bridge
    `response.trace` — copied, never invented or bypassed? A forged or
    self-constructed trace is a hard fail (R8).

**Fail closed.** Any of the above failing stops the cycle: fix (or
split/reuse per Phase 4), re-run the harness, and only then proceed. An
unverified state is never published.

**Produces.** A verification harness, a green (or failed) verification record
in the resulting state (`schemas/verification-record.schema.json`).

## Phase 8 — Publish

**What.** Publish the accepted, verified resulting state.

**Do.** Publish component metadata, lineage, and Registry/index information.
Register every capability: the capability manifests (one entry per
implementation) + generic assembler build each implementation record and
register it into the canonical Registry. Publish the decomposition per R3 —
one contract per capability, referenced by its one or more capability-manifest
entries; the Registry records the composition.

**Non-negotiables.** Gates 8, 9, 14:

8. If I split a component, did I preserve lineage and update discoverability?
9. Is the resulting component discoverable through the canonical Registry?
14. Is registration performed by the manifest + a generic assembler, so
    components contain no registration logic and swapping an implementation
    requires no consumer code change?

**Produces.** A discoverable, registered, verified resulting state.

## Phase 9 — Return state

**What.** Make the resulting state the input of the next cycle.

**Do.** Ensure no special knowledge of the previous goal is required to reuse
the outputs; the next cycle starts from state + verification record, re-runs
verification, and only then accepts a new goal.

**Non-negotiables.** Gate 11: is the resulting state sufficient for the next
cycle to rediscover the work without private agent memory?

**Produces.** The next cycle's `current_state`.
