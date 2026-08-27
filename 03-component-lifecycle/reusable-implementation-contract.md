# Reusable Implementation Contract

A newly created capability/component is reusable only if its implementation boundary does not encode assumptions belonging exclusively to the product that triggered its creation, unless those assumptions are intrinsic to the responsibility itself.

## Required implementation properties

- generic responsibility;
- explicit contract;
- stable identity;
- version;
- declared dependencies;
- no hidden product dependency;
- no hidden renderer/UI dependency unless the responsibility is explicitly UI-specific;
- canonical discoverability metadata;
- runtime resolvability where applicable;
- lineage to the cycle that created or changed it.

## Example decision

Bad (product-specific identity):

`<ProductX><SpecificFeature><Capability>`

when the actual responsibility is generic, e.g.:
`<GenericFeature><Capability>`

Preferred:

`<GenericFeature>Capability`

with the requesting product using it as one consumer among many.

The same rule applies to every domain.

## Implementation structure

Use this structure when a genuinely missing reusable component must be created
(see the glossary and `component-contract-template.md` for field definitions):

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
