# Reusable Implementation Contract

A newly created capability/component is reusable only if its implementation
boundary does not encode assumptions belonging exclusively to the product that
triggered its creation, unless those assumptions are intrinsic to the
responsibility itself.

The invariant rules this contract enforces are defined verbatim in
`00-core/capability-rules.md`: **R1** (identity), **R2** (contract artifact),
**R4** (placement), **R5** (dependencies and order), **R8** (contract-first
creation order), **R9** (the Bridge is the only execution interface). They are
not restated here. This document supplies the extraction judgement, the
implementation shape, and the pre-implementation checkpoint.

## Generic essence vs intrinsic logic (illustrates R1)

Extract the generic essence and leave the product semantics in the consumer or
in composition/configuration. When analyzing a responsibility, separate what is
a plain generic operation from what is product-only meaning:

| Appears product-bound | Generic essence |
|---|---|
| `<product>.<operation_a>` (a named capability that happens to first appear inside a product) | **`<domain>.<operation>`** (the same responsibility restated without the product: a generic state store keyed by contract data, not a built-in product type) |
| `<product>.<operation_b>` (a product command vocabulary) | **`<domain>.<operation>`** (a generic parser of `verb + args` with a configurable grammar) |
| `<product>.<operation_c>` (a product-specific rendering/framing) | **`<domain>.<operation>`** (a generic layout/render over plain data) |
| `<product>.<operation_d>` (product-specific validation/costing) | **`<domain>.<operation>`** (a configurable bounds/validity check — the product's costs, kinds, and rules are inputs, not built-ins) |
| `<product>.<operation_e>` (a domain growth engine) | intrinsic to the product — stays product-local, composed over the generic ones above |

If the responsibility is genuinely product-intrinsic, keep it as product-local
logic and do not advertise it as a reusable capability (R1).

## Rules in force (citations only)

- **R1** — see `00-core/capability-rules.md`.
- **R2** — see `00-core/capability-rules.md`.
- **R4** — see `00-core/capability-rules.md`.
- **R5** — see `00-core/capability-rules.md`.
- **R8** — see `00-core/capability-rules.md`.
- **R9** — see `00-core/capability-rules.md`.

## Creation-Order Protocol (R8)

For every new capability, construction proceeds in a strict, gate-able order.
Each stage MUST be complete and validated before the next begins; this is
enforced by conformance gate 26.

```text
1. CONTRACT  -> write the contract artifact (R2), validated against
                schemas/component-contract.schema.json
                    |
2. MANIFEST  -> write the capability manifest (R3), validated against
                schemas/capability-manifest.schema.json, declaring the
                executor reference (module:attr) — the module may not exist yet
                    |
3. CONCRETE  -> implement the registration-unaware executor
                execute(operation, input, policy) so it satisfies the contract
                (R4 placement; never register; never import the Registry)
```

Checklist for each stage:

- **Contract**: one materialized, versioned contract artifact (R2); operations,
  generic inputs/outputs, and errors defined; validated against the contract
  schema (R6 hard-fails if missing).
- **Manifest**: capability id (R1 generic), contract version, one entry per
  implementation, executor reference (validated against the manifest schema).
- **Concrete code**: the executor only; satisfies the contract; no
  registration logic (Gate 16); no product-prefixed id (R1); reachable only
  through the Bridge (R9).

Writing concrete code before its contract artifact and capability manifest
exist and validate is a violation of **R8**. The contract is the specification
the code is built against, never a summary of already-written code.

## Implementation structure

Use this structure when a genuinely missing reusable component must be created
— applied across the R8 stages (contract first, then manifest, then code).
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

Only after this checkpoint passes may the contract artifact be written; per
R8 the contract and manifest come first, and only then is the concrete code
implemented.