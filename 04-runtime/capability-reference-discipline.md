# Capability Reference Discipline

This document makes MANDATORY the separation between a capability contract
and the component that implements it. It exists because a product that
references concrete components is not product-independent and cannot reuse
ecosystem infrastructure without rewriting its own code.

All examples in this document use abstract placeholders only. Embedding a
concrete product, capability, or component identity here would itself be a
violation of the discipline it prescribes.

The repeating failure this prevents:

```python
# FORBIDDEN — the consumer names a concrete component module/class
from <component_module_a> import <TypeA>, register_<component_a>
from <component_module_b> import <RegistryB>, register_<component_b>
register_<component_a>(self.registry)   # change <component_a> -> edit consumer
```

If changing the component that provides a capability requires editing any
consumer, the boundary is wrong.

## Core rule

> A product/consumer MUST reference only capability identity (capability_id),
> contract version, and contract operations. It MUST NOT reference an
> implementation module, package, class, or registration function by name.

## What a consumer may reference

1. Capability contract IDs and their contract versions.
2. Contract operation names.
3. Contract input/output data shaped by the contract (generic data), NOT by
   the implementing component's internal classes.

## What a consumer MUST NOT reference

1. An implementation module or package path (`<component_module_a>.py`).
2. An implementation class or a registration function
   (`register_<component_a>`, `<ExecutorA>`).
3. An implementation-specific type as contract data
   (`<TypeA>`, `<RegistryB>`, `<TypeC>`).

## Where registration lives in the workflow

Registration is NOT a component concern; it is an ecosystem-assembly concern.
It is performed by the agent in the **Publish** phase of the execution cycle
(`02-cycle/agent-execution-protocol.md`, Phase 7) by publishing component
metadata, lineage, and Registry/index information. Concretely:

- the **component** produces ONLY the implementation (an executor) and, at
  most, capability metadata as data;
- the **manifest** carries the capability contract data (id, version,
  operations) and a reference to the component executor;
- a generic **assembler** constructs the implementation record from the
  manifest and registers it into the canonical Registry.

Registration therefore has a clear home (the manifest + assembler during
Publish) and is never embedded inside a component's implementation logic.

## Three indirections that make the rule enforceable

### 1. Capability contract data lives in a manifest, not in code.

The manifest declares the capability contract data (id, version, operations)
and which component executor provides it:

```yaml
capabilities:
  - id: <capability-a>
    implementation_id: <implementation-a>
    version: 1.0.0
    operations: [<operation-1>, <operation-2>]
    executor: <product_sub>.components.<component_a>:execute
```

### 2. Components are pure executors; they do not register.

A component module implements the capability and exposes its `execute`
(operation, input, policy) -> output callable. It does NOT import the
Registry, construct an implementation record, or contain a `register`
function. The component is registration-unaware.

### 3. A generic assembler performs registration from the manifest.

```python
# assembly (Publish-phase) — the ONLY place that builds implementation records
for entry in manifest["capabilities"]:
    module, attr = entry["executor"].split(":")
    executor = getattr(importlib.import_module(module), attr)
    registry.register(CapabilityImplementation(
        implementation_id=entry["implementation_id"],
        package_version=entry["version"],
        capability_id=entry["id"],
        contract_version=entry["version"],
        operations=tuple(entry["operations"]),
        executor=executor,
    ))
```

Swapping a component = editing the manifest, never the code.

### 4. Consumer roles resolve capability IDs from the product manifest.

Consumer logic refers only to logical roles; the product manifest maps each
role to a capability_id:

```yaml
roles:
  - <role_a>: <capability-a>
  - <role_b>: <capability-b>
```

The consumer resolves `<role_a>` → capability_id at startup and then speaks
only in that ID plus contract operations. No component name appears.

## Contract data is generic

Inputs and outputs must be shaped by the capability contract, not by the
implementing component. Entity records are generic, keyed by generic
attribute names defined in the contract:

```python
entity_a = {"id": "x-1", "class": "category-1", "enabled": True}
entity_b = {"id": "y-2", "class": "category-2", "count": 3}
stats   = {"balance": 1000, "level": 0, "step": 1, "era": 1}
```

Returning implementation classes (`<TypeA>`, `<RegistryB>`) across the
Bridge boundary is a violation.

## Enforcement rules for agents

1. Never register a capability from consumer code; registration belongs to
   the manifest + generic assembler during the Publish phase.
2. Never embed a `register` function or Registry reference inside a
   component; a component exposes only its `execute` implementation.
3. A consumer must contain no `from <component_module> import ...` of
   implementation modules/classes or registration functions.
4. Contract inputs/outputs must be generic data (dicts/shapes from the
   contract), not implementation types.
5. Before accepting a design, verify: "If I replace the component that
   provides capability X, does consumer code change?" If yes, the design
   violates this discipline and MUST be corrected.
6. Component modules live behind a boundary (e.g. a `components/` group)
   and expose only their executor; registration is assembled externally.

## Conformance gate

This rule is a hard gate in the agent conformance checklist. A cycle is not
complete while any consumer references a concrete component or any component
contains registration logic.
