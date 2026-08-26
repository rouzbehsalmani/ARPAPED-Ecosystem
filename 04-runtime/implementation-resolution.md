# Implementation Resolution

When a capability is discovered, the agent resolves:

```text
Capability
  ↓
Contract
  ↓
Compatible implementation(s)
  ↓
Policy constraints
  ↓
Canonical selection
  ↓
Bridge execution
```

The agent must never treat a source file path as the runtime identity of a capability.

Runtime identity comes from the canonical Registry/implementation model.
