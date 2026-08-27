# Adaptive Split Protocol

Splitting is a self-improvement operation, not an ordinary coding convenience.

## Trigger types

### Reactive

An existing component receives a new requirement and boundary analysis shows that one or more responsibilities can independently:

- be contracted;
- be discovered;
- be reused;
- be versioned;
- have independent lifecycle.

### Proactive

At the start of each cycle (Phase 1.5), audit owned components for split opportunities based on:

- responsibility count > 1;
- contract complexity beyond a single coherent purpose;
- mixed concerns that should be separate;
- reuse potential of sub-parts that could be discovered independently.

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
