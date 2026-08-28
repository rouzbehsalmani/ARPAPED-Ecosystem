# Reusable Implementation Contract

A newly created capability/component is reusable only if its implementation
boundary does not encode assumptions belonging exclusively to the product that
triggered its creation, unless those assumptions are intrinsic to the
responsibility itself.

The invariant rules this contract enforces are defined verbatim in
`00-core/capability-rules.md`: **R1** (identity), **R2** (contract artifact),
**R4** (placement), **R5** (dependencies and order). They are not restated
here. This document supplies the extraction judgement, the implementation
shape, and the pre-implementation checkpoint.

## Generic essence vs intrinsic logic (illustrates R1)

Extract the generic essence and leave the product semantics in the consumer or
in composition/configuration:

| Appears product-bound | Generic essence |
|---|---|
| `<product>.board` (grid + cells + balance + counters) | **grid state store** (`grid.store`): create/read/write cells on an MxN grid; balance/counters are plain row values, not built-in types |
| `<product>.input` (command vocabulary) | **CLI parser** (`cli.parse`): parse `verb + args` with a configurable grammar |
| `<product>.render` (ASCII frame) | **ASCII renderer** (`ascii.render`): layout a grid + header + legend generically |
| `<product>.rule` (costs per kind) | **configurable placement/cost check** (`rule.pricing`): bounds-validity, occupancy, funds — costs/kinds are inputs |
| `<product>.simulation` (domain growth engine) | intrinsic to the product — stays product-local, composed over the generic ones above |

If the responsibility is genuinely product-intrinsic, keep it as product-local
logic and do not advertise it as a reusable capability (R1).

## Rules in force (citations only)

- **R1** — see `00-core/capability-rules.md`.
- **R2** — see `00-core/capability-rules.md`.
- **R4** — see `00-core/capability-rules.md`.
- **R5** — see `00-core/capability-rules.md`.

## Implementation structure

Use this structure when a genuinely missing reusable component must be created.
The fields correspond to the contract artifact (see `component-contract-template.md`):

```text
Component
  Identity
  Responsibility
  Contract
  Version
  Classification
    Domain
    Family
    Type
  Inputs
  Outputs
  Dependencies
  Policy requirements
  Runtime requirements
  Discoverability metadata
  Lineage
  Consumers
```

## Product-neutrality checkpoint

Before implementation, ask:

1. What is the responsibility without naming the requesting product?
2. Can another product consume the same contract?
3. Does the implementation contain product-specific assumptions?
4. If yes, are those assumptions intrinsic to the responsibility?
5. If not, move them to composition/configuration/adapter boundaries.

Only after this checkpoint passes should implementation begin.