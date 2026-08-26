# Adaptive Split Protocol

Splitting is a self-improvement operation, not an ordinary coding convenience.

## Trigger

An existing component receives a new requirement and boundary analysis shows that one or more responsibilities can independently:

- be contracted;
- be discovered;
- be reused;
- be versioned;
- have independent lifecycle.

## Procedure

```text
existing component
      ↓
boundary analysis
      ↓
independent responsibilities?
   no ───────────────> keep component
   yes
      ↓
define child contracts
      ↓
create child components
      ↓
rewire consumers
      ↓
update Registry/index
      ↓
preserve lineage
      ↓
publish resulting state
```

Do not split solely because the source file is large.
