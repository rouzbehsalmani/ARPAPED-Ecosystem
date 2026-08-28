# Templates

Two reusable artifact shapes referenced from `CYCLE.md` and `RULES.md`. Rules
governing these shapes (R1–R8) are defined once, in `RULES.md`; this page is
structure only.

## Component contract template

Every reusable component MUST have a contract that defines its interface,
inputs, outputs, and lifecycle. This is that contract's materialized form —
the **contract artifact**, one per capability (existence per R2), generic in
identity (R1) and in data shapes (rule 7 below).

```yaml
contract:
  identity:
    id: "<domain>.<operation>"  # unique, generic capability id (R1)
    name: "string"              # human-readable name
    version: "string"           # semantic version
    domain: "string"            # application domain
    family: "string"            # component family
    type: "string"              # capability | connector | service

  responsibility:
    description: "string"       # what this component does
    invariants: ["string"]      # properties that never change, e.g. "does not modify its inputs"

  interface:
    operations:
      - name: "string"
        description: "string"
        input:
          - name: "string"
            type: "string"
            required: true
            description: "string"
        output:
          type: "string"
          description: "string"
        errors:
          - code: "INVALID_INPUT"
            description: "input did not satisfy the contract"

  dependencies:
    capabilities: []          # required capability contracts (R4: more generic than this one)
    components: []            # required component contracts
    resources: []             # required external resources

  policy:
    requirements: ["string"]  # policy constraints this component requires
    provides: ["string"]      # policy guarantees this component provides, e.g. "deterministic-output"

  runtime:
    threading: "string"       # single | multi | thread-safe
    stateful: false            # whether component maintains state
    lifecycle: "string"       # singleton | transient | scoped

  discoverability:
    tags: ["string"]
    metadata: {}

  versioning:
    compatibility: "string"   # backward | forward | strict
    deprecation_policy: "string"

  lineage:
    created_by: "string"      # cycle or agent that created this
    changed_by: "string"      # cycle or agent that last modified
    history: []               # list of significant changes, e.g. {version, change, cycle}
```

Real capability IDs, types, and domains must be resolved from the
ecosystem's authoritative manifests; the shape above is structural only.

**Rules.**

1. The contract MUST be registered in the canonical Registry before the
   component can be discovered.
2. The contract MUST define all public operations with explicit
   input/output types.
3. The contract MUST NOT expose implementation details; it defines the
   WHAT, not the HOW.
4. The contract MUST include error definitions for all failure modes.
5. Version changes MUST follow the declared compatibility policy.
6. Lineage MUST be updated whenever the component is modified.
7. Inputs and outputs MUST be generic contract-shaped data, never the
   implementing component's internal classes or module names — a consumer
   must be able to swap the component without changing its contract data
   (`RULES.md`, "Capability reference discipline").
8. The contract MUST NOT name or depend on the implementing module,
   package, or class; the component is bound to the contract through a
   data-driven capability manifest, not through consumer code.
9. Contract identity per R1; extraction judgement in `RULES.md`.
10. This file's shape IS the capability's contract artifact: existence and
    uniqueness per R2, locality per R3.
11. `dependencies` per R4.

## Cycle report template

```markdown
# Agent Cycle Report

## Goal
`<goal>`

## Starting State
`<state>`

## Reusable Discovery
`<discovery references>`

## Decisions
For each responsibility: `reuse | compose | split/refactor | create`

## New Components
`<component identities>`

## Reused Components
`<component identities>`

## Split/Refactor Operations
`<lineage references>`

## Registry Changes
`<discoverability/index changes>`

## Bridge Integration
`<canonical path reference>`

## Verification
Report against the checklist in `RULES.md` ("Verification contract"). For
each point — assembly/startup; capability decomposition; every capability
operation with the full ordered trace; every consumer interaction via
scripted stream; operator decision window; reactive same-session;
invariants; record — state PASS/FAIL with evidence.

`<harness path/identity in the resulting state>`

`<trace evaluation>` — the observed Bridge trace for every capability
operation (`validated → discovered → policy_evaluated → selected →
executed`, `check.trace` in the record) and any failure of the ordered
stages.

`<failures observed and fixes applied; regression re-run status>`

`<verification record reference; status: verified | failed>`

## Resulting State
`<state>`

## Next-Cycle Readiness
`<how the resulting state is discoverable without agent memory>`
```
