# Agent Discovery Algorithm

This is an operational algorithm, not a conceptual description.

## Input

`goal + current_state`

## Procedure

1. Extract required responsibilities from the goal.
2. For each responsibility, construct the most selective valid discovery key.
3. Resolve the relevant Registry index/shard.
4. Retrieve a bounded candidate set.
5. Filter candidates by contract compatibility.
6. Filter by version and lifecycle constraints.
7. Filter by policy and execution constraints.
8. Prefer direct reusable candidates.
9. If none satisfy the requirement, widen the discovery scope by one level.
10. Repeat until a bounded candidate set is found or the allowed scope is exhausted.
11. Only then consider split/refactor or creation.

## Complexity rule

The algorithm must not become `O(total_components)` for ordinary discovery.

The normal query path is:

`selective key -> relevant index -> bounded candidates`

not:

`all components -> local filtering`

## Candidate evidence

Every selected candidate must be explainable by:

- identity;
- contract;
- version;
- compatibility;
- lifecycle;
- lineage;
- discovery scope.

## Failure

If a required capability cannot be resolved and no valid creation path exists, fail closed and report the unresolved requirement.

## Build-time / runtime discovery parity

The agent's discovery result must be representable through the same Registry model used by runtime resolution.

A reusable component is not fully integrated merely because an agent can import or locate its source code.

For an accepted component:

```text
source implementation
      +
canonical contract
      +
discoverability metadata
      +
Registry/index entry
      +
runtime-resolvable implementation
```

must form one coherent identity.

The Bridge must consume the canonical Registry resolution path rather than a product-specific shortcut.
