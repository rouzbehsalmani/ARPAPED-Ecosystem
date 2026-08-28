# Glossary

The single source of definitions for the ARPAPED self-improving cycle. Every
other document in this Blueprint uses exactly these words. If a document seems
to redefine one of these terms, the document is wrong, not this page.

Invariant rules are NOT defined here: each is stated verbatim exactly once, in
`00-core/capability-rules.md` (R1–R10), and documents cite rule numbers.

## Core nouns

| Term | Definition |
|---|---|
| **ecosystem root** | The authoritative ARPAPED project root supplied by the operator. The agent resolves every canonical implementation from here; it never assumes a product directory is the root and never creates a second copy. |
| **responsibility** | One independently meaningful thing a product or the cycle must achieve. The unit of decomposition: one responsibility = one capability = one contract. |
| **capability** | A named, versioned responsibility that the ecosystem can execute (`capability_id`). Identity is the generic responsibility (`domain.operation`; never `<product>.<operation>`) per **R1**. Consumers speak only capability IDs + contract operations (per **R7**). One contract artifact defines it; it may have one or more implementations. |
| **contract** | The machine-readable interface of a capability: identity, version, operations (name, input, output, errors), dependencies, policy, invariants, discoverability, lineage. One contract artifact per capability (see **R2**). |
| **contract artifact** | The materialized, versioned interface file that machine-defines a capability (template: `03-component-lifecycle/component-contract-template.md`). Existence, uniqueness, and locality per **R2**. Referenced by its capability manifest; may be implemented by many components. |
| **component** | The thing that *implements* a capability. A registration-unaware executor exposing only `execute(operation, input, policy) -> output`. Components are never named or imported by consumers. |
| **implementation** | A registered, versioned record that binds an executor to a capability contract (id, version, operations) in the Registry. |
| **product** | A consumer application built on the ecosystem. It declares what it needs (capabilities, components, roles) in its manifest and never bundles implementation logic. |
| **product boundary** | The closed encapsulation of a product per **R10**: each product's complete implementation lives in its own scoped territory at the ecosystem root (a products area, a game area, an economy area — whichever the root designates; the folder name is not a Blueprint mandate) — only consumer logic, its product manifest, and its integration entry point — never ecosystem-assembly/registration code and never harness/test scaffolding. It is reached from outside only through that declared public surface; tooling resolves it by the manifest identity `product.id`, never by hard-coding a product name (Gates 29–31). |
| **generic capability area** | The shared home of reusable capabilities at the ecosystem root (e.g. `generic/`). Placement per **R4**: reusable capabilities live here with their contract artifacts and capability manifests, resolved through the canonical Registry; a product directory is never their home. |
| **consumer** | Any code that invokes a capability — a product, its terminal/CLI input layer, or another component. Reference behavior per **R7**: consumers use only capability IDs + contract operations through the Bridge and never name components. |
| **manifest** | A data file that references contracts and binds identity. Two kinds: **product manifest** (identity, dependencies, roles, integration — one per consumer; references capability ids only, never hosts capability manifests) and **capability manifest** (one contract artifact + its operations and one executor-reference entry per implementation; lives with the capability's generic footprint, never fused into a product directory). Structure per **R3**, locality per **R4**. |
| **role** | A logical name in the product manifest that maps to a capability_id. Consumer code references roles; roles resolve to capability IDs at startup. |
| **assembler** | A generic Publish-phase helper that reads the capability manifest, imports each executor, builds each implementation record, and registers it into the canonical Registry. Products and components never contain registration logic. |
| **Bridge** | The canonical execution boundary. Routes every request through registry discovery → policy → selector → executor and returns a trace. There is exactly one canonical Bridge. |
| **Registry** | The canonical discovery/index service: capability+operation → bounded implementation candidates. There is exactly one canonical Registry. |
| **Policy** | The canonical authorization stage that evaluates each candidate against the request's policy context. |
| **Selector** | The canonical routing stage that picks which allowed candidate executes (with failover awareness). |
| **Executor** | A component's `execute` callable; the only code the Bridge executes. |
| **trace** | The ordered stage list a Bridge response carries: `validated → discovered → policy_evaluated → selected → executed`. The designed evidence that a request travelled the canonical path. |
| **resulting state** | The authoritative, discoverable state of the ecosystem after a cycle completes — code, manifests, contracts, verification record, report. The input state of the next cycle. |
| **verification record** | The machine-readable result of the Verify phase (`schemas/verification-record.schema.json`), written into the resulting state. Green only when the harness passes. |
| **lineage** | The discoverable history of a component: which cycle/agent created it, what changed it, and how it evolved through splits. |

## Dependency direction

Capability contracts depend on each other from **generics → specifics**. The
complete rule (multiple required contracts, no product-scoped dependencies,
build generics first) is **R5** in `00-core/capability-rules.md`. Definitions
only; the rule is not repeated here.

## Verbs

| Verb | Definition |
|---|---|
| **resolve** | Obtain a canonical implementation from the ecosystem root via authoritative manifests. Never invent or copy local equivalents. |
| **discover** | Find reusable candidates in the Registry using a selective key → relevant index → bounded candidates (never a global scan). |
| **assemble** | Build implementation records from the capability manifests (one entry per implementation) during the Publish phase and register them. |
| **register** | Insert an implementation into the canonical Registry — an assembly/Publish concern, never done by components or consumers. |
| **execute** | Run a selected executor for a request through the Bridge. |
| **verify** | Run the resulting state headlessly through the verification harness and prove every required check (see `04-runtime/verification-contract.md`). |
| **publish** | Accept a verified resulting state, its metadata, lineage, and Registry/index information as the new authoritative state. |

## Bridge trace stages

| Stage | Meaning |
|---|---|
| `validated` | Request passed structural validation. |
| `discovered` | Registry returned compatible implementations. |
| `policy_evaluated` | Policy evaluated all candidates. |
| `selected` | Selector chose a candidate for execution. |
| `executed` | Selected implementation completed successfully. |

On success all five stages appear in order; on failure only the stages reached
before the error appear (never empty — at minimum `validated`). The trace is
for debugging, auditing, and verification evidence; it is not control flow.