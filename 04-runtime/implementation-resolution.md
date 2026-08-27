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

## Component-reference discipline

A consumer MUST NOT reference a concrete implementation module, class, or
registration function. Consuming the capability contract is the only
supported path:

- resolve capability contract through the Bridge;
- receive generic contract-shaped data;
- never import `<component_module>`, `<ImplementationClass>`, or a
  `register_*` function from consumer code.

Components are pure executors: they expose their `execute` implementation and
do not contain registration logic. Registration is assembled externally from a
capability manifest during the Publish phase.

Component→capability binding must be data-driven (a manifest), and consumer
roles must resolve capability IDs from the product manifest. See
`capability-reference-discipline.md` for the mandatory rules and conformance
gate.
