# Generic Component Implementation Template

Use this structure when a genuinely missing reusable component must be created.

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

Only after this checkpoint should implementation begin.
