# The Self-Improving Cycle

Building something concrete right now? See `0-WALKTHROUGH.md` — it turns the
phases below into literal file paths and commands. This file is the
phase/gate reference it points back to.

The operational spine of the Blueprint. Every capability execution goes through
one canonical Bridge over contract-shaped data, and the cycle always verifies
the result headlessly before publishing it. Definitions and the numbered
invariant rules (R1–R9) it enforces live in `2-RULES.md`; nothing here restates
a rule in full — every phase cites the rule number it enforces.

## Cycle input

```text
current_state
goal
```

## Phase → gate map

| Phase | Gate(s) enforced |
|---|---|
| 0 — Bootstrap | 1, 2, 3, 25, 32, 33, 34, 35 |
| 1 — Understand | 3 |
| 1.5 — Component health check | 12 |
| 2 — Decompose the goal | 13, 21 (by construction) |
| 3 — Discover | 4, 5 |
| 4 — Decide | 6 |
| 5 — Implement | 7, 15, 16, 26 |
| 6 — Integrate | 10, 13, 24, 27 |
| 7 — Verify | 17, 18, 19, 20, 21, 22, 23, 24, 27, 28, 29, 30, 36 |
| 8 — Publish | 8, 9, 14, 31 |
| 9 — Return state | 11 |

A gate answered NO means the cycle is not complete.

## Phase 0 — Bootstrap

**What.** Enter the ecosystem, resolve what is canonical, and accept only then
the goal. Mandatory before any other phase, for any human or AI agent.

**Do.**

1. Before accepting anything as a new goal, check for an existing mid-cycle
   checkpoint via checkpoint's own load operation
   (`blueprint/dep/MANIFEST.yaml: checkpoint`). If it returns an `in_progress` checkpoint, RESUME
   it instead of starting fresh — adopt its `goal` and `starting_state`
   unchanged, skip re-deciding any responsibility already at `integrated`,
   and continue from its `current_phase` and `next_action`. Only proceed
   with a genuinely new goal if nothing is returned, or the
   operator explicitly confirms discarding the in-progress one (then
   clear it via checkpoint's own clear operation before continuing).
   This is what lets a different agent — after the original stopped mid-cycle
   for any reason unrelated to the work itself (tokens, network, crash) —
   pick up exactly where it left off, at the responsibility level, not just
   "somewhere in Phase 5."

   **Resuming is a bounded lookup, not a project-wide re-scan.** Once a
   checkpoint is found, read `ecosystem_resolution_ref` directly instead of
   re-running Bridge/Registry discovery, and open each responsibility's
   recorded `artifacts` (contract/manifest/executor paths) directly instead
   of searching for them. A checkpoint that only carries a status label
   forces a resuming agent back into full-project discovery to trust that
   label — exactly the cost this mechanism exists to remove — so treat a
   `next_action`/`artifacts` field that doesn't name concrete paths as an
   incomplete checkpoint, not something to work around by scanning. Phase
   1/3 discovery still runs, but only for what the checkpoint does not
   already cover (a responsibility not yet in it, or new ground the goal
   adds) — never to re-verify what the checkpoint already resolved. This
   means resume cost is bounded by the number of responsibilities THIS
   checkpoint recorded, never by how many capabilities the wider project
   already has: a project with hundreds of existing capabilities must be
   exactly as cheap to resume as one with a handful, because a resuming
   agent touches only the checkpoint file and the specific paths it names
   — never the project as a whole, regardless of its size. If resuming
   ever costs meaningfully more than what the checkpoint's own contents
   justify, the checkpoint was incomplete (missing `artifacts` or
   `ecosystem_resolution_ref`), not the concept — fix the checkpoint being
   written, not the resuming agent's caution.

   **A stale checkpoint is not an excuse to fall back on a project-wide
   read.** A checkpoint goes stale when work happened but
   `save_checkpoint` wasn't called to record it — observed for real: a
   checkpoint frozen at `current_phase: "0-bootstrap"`, every
   responsibility still `planned`, while the contracts/manifests/executors
   for all of them already existed on disk. Trusting a stale checkpoint
   blindly is wrong, but "read the existing code to reconstruct progress"
   reintroduces the exact O(project) cost checkpoints exist to remove.
   Reconcile instead, still bounded: checkpoint's own catalog-reconciliation
   operation (`blueprint/dep/MANIFEST.yaml: checkpoint`) cross-checks each
   responsibility against the application's own `capability-catalog.jsonl`
   — the same bounded index Phase 3 discovery already uses — filling in
   `artifacts` and advancing `status` to at least `code_written` wherever
   the catalog proves it, in O(this cycle's own capability count), never
   O(project size). It never invents `integrated` from catalog evidence
   alone (that still needs a real, cheap per-responsibility Bridge check),
   and it never regresses a status already further along. Immediately
   `save_checkpoint` the reconciled result — reconciling without re-saving
   pays this same cost again on the very next interruption.

   No catalog exists yet before Phase 8 first runs it, though — observed
   for real, mid-Phase-5: a checkpoint frozen at `current_phase:
   "0-bootstrap"` while 7 contracts and 5 of 7 executors already existed,
   with no `capability-catalog.jsonl` anywhere to reconcile against. For
   this case, checkpoint's own filesystem-reconciliation operation
   (`blueprint/dep/MANIFEST.yaml: checkpoint`) uses the
   ecosystem's own naming convention (R1: `<domain>.<rest>` places a
   contract/manifest at predictable paths, tried as either a `.yaml` or
   `.json` manifest since which one depends on the runtime's own
   language) instead of a catalog — bounded, no file contents read beyond
   a found manifest itself, still O(this checkpoint's own responsibility
   count). A manifest's own `executor:` field is then resolved against
   whichever filesystem roots the caller supplies (there is no one rule
   for this across languages/executor_kinds — a Python `module:attr`
   string and a plain relative path resolve completely differently). It
   also catches what a raw status-bump would hide: a file sitting where a
   manifest would name it, before any manifest exists there, is an R7
   order violation (Gate 26), so it's recorded as a
   `blocker`, not silently advanced past `manifest_written` — reconciling
   must never launder a real rule violation into a clean-looking status.
2. **First decide: does this goal continue an application that already has
   an ecosystem root in this repo, or does it need a genuinely NEW,
   independent one?** (Gate 35) A repo can hold many independent
   worked applications side by side (this one does); "the ecosystem" is
   scoped per APPLICATION, never per repo. Getting this wrong is not a
   style issue -- observed for real: a second, unrelated application
   imported an existing application's Bridge/Registry/
   assembler modules directly instead of resolving its own, because
   nothing distinguished "continue this ecosystem" from "start a new
   one" -- the new application could not run, or be copied into a real
   deployment, without the first application's tree also present.
   - **Continuing an existing application:** establish the root already
     supplied by the operator (or already discoverable, e.g. the one
     goal-relevant application in an otherwise-empty repo); never
     create a second copy of THAT root.
   - **Starting a genuinely new, independent application:** establish a
     NEW root for it (never nested inside, or defaulting to, an
     existing application's root) -- see 0-WALKTHROUGH.md section 0 for
     what this application must resolve/establish for itself (its OWN
     Bridge, Registry, Policy, Selector, assembler -- copied or ported
     from a reference implementation, never imported cross-application).
3. Starting there, discover the authoritative ecosystem profile/manifest,
   canonical Bridge implementation, Registry implementation and records,
   policy implementation, capability/component contracts, implementation
   manifests, and connector contracts. Use the repository's own manifests as
   the authority for exact paths and versions. If two authoritative-looking
   implementations conflict, STOP and report the ambiguity — do not silently
   choose one. If the goal's consumer surface spans more than one runtime —
   the backend plus any other entry point it ships (a browser tab, a
   mobile app, a desktop client, whatever kind it is) — repeat this
   resolution for each runtime that needs its own canonical Bridge; never
   assume a backend Bridge alone covers another entry point's own requests
   (2-RULES.md Bridge glossary, R6).
4. Build an implementation map: every required primitive (execution boundary,
   discovery/Registry, policy, capability model, component model, packaging
   model, implementation model, connector model, resource execution) must
   resolve to an authoritative artifact in the ecosystem (see the resolution
   table in `2-RULES.md`).
5. Write a resolvable **ecosystem-resolution record** — machine-readable
   (e.g. a small JSON artifact or a dedicated report section) — naming at
   minimum the resolved canonical Bridge, Registry, policy stage, selector,
   the `contracts/` area, and the root, plus the implementation map. Without
   it the cycle cannot proceed: a resolved-but-unrecorded Bridge is treated as
   unresolved. The record is referenced in the cycle report
   (`blueprint/schemas/agent-cycle-report.schema.json`) and, if a checkpoint is now
   being started for this cycle attempt, as its `ecosystem_resolution_ref`
   too — this is the single most valuable thing a checkpoint can save a
   resuming agent from redoing.
6. Load the operating rules: this Blueprint, the ecosystem's authoritative
   manifests, canonical Bridge/Registry contracts, immutable architectural
   decisions, capability/component reuse rules, repository-local policies.
   Local instructions may refine implementation details but never contradict
   canonical ecosystem rules.
7. Resolve the current state from the authoritative discoverable state of the
   ecosystem — never from private conversation memory.
8. Only after steps 2–7 are complete (or a checkpoint was resumed at step 1),
   accept the requested goal as the cycle input.
9. Plan the application's package structure before writing any code: contract
   artifacts under `contracts/`; component executors and their capability
   manifests co-located in their owning packages; small generic (single-task,
   reusable) components built and composed before the specific
   responsibilities layered over them (generics → specifics, R4); entry
   points and the single request-construction point at the application level
   (R6); tests and the verification harness outside the application packages.
   Never write an application responsibility as a single monolith file mixing
   independent responsibilities, and never reimplement a small reusable
   component instead of composing it.

**Hard prohibitions.** The agent MUST NOT: create a parallel Bridge (a second
one competing within a runtime that already has its resolved canonical
one — this is distinct from resolving one canonical Bridge per runtime
when the consumer surface genuinely spans more than one, e.g. the backend
plus a browser tab, a mobile app, or any other entry point, 2-RULES.md
Bridge glossary); resolve or import an EXISTING application's Bridge,
Registry, Policy, Selector, or assembler as if it were a genuinely NEW,
independent application's own (Gate 35) — a new application copies or
ports the reference implementation into its own tree, it never imports
another application's module across that boundary; create a private
Registry; copy the entire ecosystem into a package; implement a small
generic responsibility as one-off package-local logic merely for convenience;
globally scan the Registry as the normal discovery mechanism; silently replace
an authoritative implementation; write a monolith file mixing independent
responsibilities; embed registration logic inside an application package
(registration is an assembly/Publish concern, Phase 8); reimplement a
capability's own responsibility directly in a frontend instead of resolving
it through a Bridge (R6/R9) — in any runtime, in any language.

**Non-negotiables.** Gates 1, 2, 3, 25, 32, 33, 34, 35:

1. Did I resolve the canonical Bridge? (From the ecosystem root.)
2. Did I resolve the canonical Registry?
3. Did I avoid creating a parallel Bridge or Registry?
25. Did I emit and reference a written ecosystem-resolution record naming the
    canonical Bridge(s) and Registry (and the implementation map) — one
    Bridge per runtime the goal's consumer surface actually executes in, not
    just the backend's? The canonical Bridge for each such runtime is the
    only execution interface for every capability operation in it — in any
    package, in scripts, in the harness, and in any other entry point
    (browser, mobile, desktop, or otherwise) alike (R8).
32. Did I check for an existing in-progress checkpoint before accepting a
    goal as new, and either resume it or get explicit confirmation to
    discard it?
33. If I resumed a checkpoint, did I go straight to its
    `ecosystem_resolution_ref` and each responsibility's recorded
    `artifacts`, instead of re-discovering already-resolved state via a
    project-wide scan? Resuming from a checkpoint must cost less than
    starting fresh, never the same or more — and that cost must be bounded
    by the number of responsibilities the checkpoint itself recorded, not
    by how many capabilities the wider project has. A resume that scales
    with total project size, in a project with a handful of capabilities
    or hundreds, is a failed resume regardless of whether it eventually
    succeeded.
34. If the checkpoint appeared stale (its recorded status/artifacts didn't
    match what's actually on disk), was it reconciled against a bounded
    source of truth — the capability catalog if one exists (checkpoint's
    own catalog-reconciliation operation), or the ecosystem's own
    naming convention if it doesn't yet (checkpoint's own
    filesystem-reconciliation operation, `blueprint/dep/MANIFEST.yaml: checkpoint`) — never by reading the project to
    reconstruct progress by hand, and immediately re-saved corrected so
    the same staleness is never paid for twice? Did reconciliation record
    any rule violation it exposed (e.g. code written without its manifest,
    R7/Gate 26) as a `blocker` instead of silently advancing the status
    past it?
35. Did I explicitly decide whether this goal continues an EXISTING
    application's ecosystem or requires a genuinely NEW, independent
    one, before resolving any Bridge/Registry — and if new, did the
    resolved Bridge/Registry/Policy/Selector/assembler end up under
    THIS application's own tree (copied or ported from a reference
    implementation), never imported directly from another application's
    module? "The ecosystem" is scoped per application, never per repo;
    a repo holding several independent applications is not itself one
    ecosystem they all share.

**Produces.** Resolved ecosystem root + loaded rules + accepted `goal` + a
written ecosystem-resolution record.

## Phase 1 — Understand

**What.** Resolve the authoritative ecosystem implementation map.

**Do.** Identify the canonical requirements → manifest → implementation →
contract chain for every primitive the goal touches (resolution table in
`2-RULES.md`). Do not infer missing architecture from package code if the
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
catch-all. Identity per R1. Add each responsibility to the checkpoint at
status `planned` (`blueprint.dep.checkpoint.save_checkpoint`, `blueprint/dep/MANIFEST.yaml`) —
this is what lets an agent resuming after an interruption see which
responsibilities this cycle even decomposed into, not just which ones
happen to have code on disk.

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
3. Search the five-level cascade, narrowest first, stopping at the first
   level that returns a bounded, non-empty candidate set (Registry contract,
   `2-RULES.md`): **Exact** (this capability id + operation + a pinned
   version/implementation) → **Scoped** (this capability id + operation, any
   compatible version) → **Family** (`identity.domain` + `identity.family` +
   operation — a family is only meaningful within its domain) →
   **Domain** (`identity.domain` + operation) → **Cross-domain**
   (`discoverability.tags` + operation). Each level is its own index — never
   a scan of the level below it, let alone of every component.
4. Filter the returned candidate set by contract compatibility, then by
   version/lifecycle constraints, then by policy/execution constraints.
5. Prefer direct reusable candidates; a Family/Domain/Cross-domain match may
   need composing (Phase 4) rather than reusing verbatim.
6. Only once all five levels are exhausted with nothing usable does creation
   become the answer (Phase 4) — creation is the last resort of discovery,
   never the default response to a new responsibility.

The normal query path is `selective key -> relevant index -> bounded
candidates`, never `all components -> local filtering` — discovery must not
become `O(total_components)`. Before any code runs, this same search is what
the generated capability catalog makes concrete: grep it by domain, family,
tag, or keyword (2-RULES.md "The Registry contract") instead of reading
every contract in the ecosystem to construct the discovery key by hand.
Every selected candidate must be explainable by
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
generics-first order it imposes (R4). Update each responsibility's
checkpoint entry to status `decided`, with its `decision`/`reason`
(`blueprint.dep.checkpoint.save_checkpoint`) — an agent resuming this cycle later
must never re-decide a responsibility that already reached this status.

**Produces.** A decision table per responsibility.

## Phase 5 — Implement

**What.** Create or adjust components only where the decision requires it.

**Do.** For a new component, follow creation order per R7 — contract artifact
first (validated against `sample/schemas/component-contract.schema.json`), then
capability manifest (validated against `sample/schemas/capability-manifest.schema.json`,
declaring the executor reference, which may name a not-yet-existing module),
then the concrete registration-unaware executor code
(`execute(operation, input, policy) -> output`) — and satisfy R1–R4. Before
writing the contract, apply the product-neutrality checkpoint in `2-RULES.md`
to confirm the responsibility is genuinely generic, not a one-off dressed up
as a capability. Components never register themselves and never import the
Registry (Publish phase owns registration, per R8's indirection rules in
`2-RULES.md`). This contract → manifest → code order is exactly what the
checkpoint's `contract_written` → `manifest_written` → `code_written`
statuses track — update the responsibility's checkpoint entry after each
one completes, not once at the end of the whole capability, so an
interrupted implementation shows precisely which of the three exists on
disk already. Each update MUST also record the file path just written
into that responsibility's `artifacts.contract` / `.manifest` / `.executor`
— a status alone only tells a resuming agent THAT something exists, not
WHERE, which is what forces the expensive fallback of scanning the whole
project to find it.

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
Bridge (`2-RULES.md`). Request path per R6: every consumer request — including
terminal/CLI input handling — funnels through the application's single
request-construction point, in whichever runtime that consumer executes (a
backend process, any other entry point with its own resolved Bridge, or a
thin client calling across to another runtime's — 2-RULES.md R6). Once a responsibility's capability is actually
wired through the Bridge and reachable this way, move its checkpoint entry
to status `integrated` (`blueprint.dep.checkpoint.save_checkpoint`) — the last status
before Phase 7 verification, and the signal a resuming agent uses to skip
re-implementing work that already made it this far.

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
    scripts, in the harness, or in any other entry point (browser, mobile,
    desktop, or otherwise), and no capability's own responsibility
    reimplemented directly in that entry point's own code instead of
    resolved through a Bridge (R6/R8/R9)?

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
written. The full checklist a pass must satisfy lives in `2-RULES.md`
("Verification contract"); this phase runs it.

**Do.** Run the verification harness: assembly/startup, capability
decomposition (R2/R3) incl. its small-reusability hard fails (R5), every
capability operation with its full ordered trace over the SAME resolved
canonical Bridge the application uses (R8), run under a bounded per-stage
timeout rather than an unbounded wait — a stage that never progresses is a
hard failure, not grounds to wait longer (R5) — every consumer control
through a scripted stream, an operator decision window, a reactive loop and
injected input in the same session, regression checks for every previously
reported defect, and a machine-readable verification record written into
the resulting state.

Before treating Gate 27 as satisfied, re-read every entry point's own code
(a process entry point, a browser runtime's bootstrap/rendering script, any
other consumer-facing file) end to end one more time — not to re-run it,
to actually read it — specifically hunting for a numeric or string literal
that isn't pure presentation (a color, a pixel size, a label) (Gate 36).
For each one, check whether some capability's own contract or executor
already defines or computes that same value. Observed for real: an entry
point re-derived a displayed statistic (a resource total contributed per
building type) using hardcoded per-type constants that were already
computed, under the same names, inside a capability's own executor — which
never returned that value in its output, so the entry point silently
duplicated the rule instead of resolving it, and the two copies would have
silently disagreed the moment either one changed. The fix is never in the
entry point: extend the capability's own output to include the value, then
have the entry point read it from there. A gate that only asks "does this
decide anything?" is easy to answer yes-I-checked without ever finding
this; checking literal-by-literal is what actually catches it.

The strongest place to satisfy Phase 8's Gate 31 is
here, as the harness's own last act once every check has passed
(episode_store's own save operation with the cycle report, verification
record, and episodes directory — `blueprint/dep/MANIFEST.yaml: episode_store`,
0-WALKTHROUGH.md step 6) — that makes "verified" and "recorded" the same
event, a harness failure rather than a step a later phase can forget,
instead of two separately-rememberable actions.

**Non-negotiables.** Gates 17–24, 27, 28, 36:

17. Did I run the result through a verification harness — headlessly, no
    real terminal required?
18. Does the harness exercise every declared capability operation over
    contract-shaped data with every trace reaching `executed`?
19. Does it simulate every consumer-visible interaction via a scripted
    command stream and assert its observable effect, running an automatic
    loop and injected input in the SAME session? When a consumer surface is
    another entry point (browser, mobile, desktop, or otherwise) with its
    own resolved Bridge, does this include THAT Bridge's own resolution/
    execution path — not just the backend capability tested in isolation
    while the shipped entry point never actually calls it?
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
29. Does every capability-operation check run under a bounded per-stage
    timeout (never an unbounded wait), with a timeout treated as a hard
    failure rather than grounds to wait longer or retry indefinitely (R5)?
30. For every capability that calls another one, is the declared dependency
    graph acyclic, and does it call only what it declared under
    `dependencies.capabilities` (R4, R5)?
36. Did I re-read every entry point's own code specifically for hardcoded
    literals that duplicate a value some capability already defines or
    computes, rather than trusting a general "does it decide anything?"
    impression? A literal that happens to match a capability's own constant
    is exactly the reimplementation Gate 27 prohibits, just easy to miss
    without checking value-by-value.

**Fail closed.** Any of the above failing stops the cycle: fix (or
split/reuse per Phase 4), re-run the harness, and only then proceed. An
unverified state is never published.

**Produces.** A verification harness, a green (or failed) verification record
in the resulting state (`blueprint/schemas/verification-record.schema.json`).

## Phase 8 — Publish

**What.** Publish the accepted, verified resulting state.

**Do.** Publish component metadata, lineage, and Registry/index information.
Register every capability: the capability manifests (one entry per
implementation) + generic assembler build each implementation record and
register it into the canonical Registry. Publish the decomposition per R3 —
one contract per capability, referenced by its one or more capability-manifest
entries; the Registry records the composition. Then record the cycle itself:
call episode_store's own save operation
(`blueprint/dep/MANIFEST.yaml: episode_store`) with the Phase 7 verification record,
this phase's cycle report, and the episodes directory — `episodes_dir` is this application's own
episode corpus (e.g. `state/episodes/`, alongside its
`state/verification-record.json`; blueprint/dep/ itself has no default), and this
call is what makes the cycle an actual entry in it, not just a record
"written into the resulting state" and never seen again. A cycle that
skips this is not published, regardless of what else it did. Once
the episode is recorded, call checkpoint's own clear operation
(`blueprint/dep/MANIFEST.yaml: checkpoint`) — the episode is now this attempt's permanent record,
so a completed cycle leaves no lingering in-progress checkpoint behind for
a future Phase 0 to mistake for unfinished work.

**Non-negotiables.** Gates 8, 9, 14, 31:

8. If I split a component, did I preserve lineage and update discoverability?
9. Is the resulting component discoverable through the canonical Registry?
14. Is registration performed by the manifest + a generic assembler, so
    components contain no registration logic and swapping an implementation
    requires no consumer code change?
31. Was this cycle recorded into the episode store (`blueprint.dep.episode_store.save_episode`),
    so its decision record and verification record accumulate in this
    application's own episode corpus for `blueprint.dep.dataset_builder` — not left
    unrecorded because nothing in this phase's own output required it?

**Produces.** A discoverable, registered, verified resulting state, recorded
as one episode in the DEP corpus.

## Phase 9 — Return state

**What.** Make the resulting state the input of the next cycle.

**Do.** Ensure no special knowledge of the previous goal is required to reuse
the outputs; the next cycle starts from state + verification record, re-runs
verification, and only then accepts a new goal.

**Non-negotiables.** Gate 11: is the resulting state sufficient for the next
cycle to rediscover the work without private agent memory?

**Produces.** The next cycle's `current_state`.
