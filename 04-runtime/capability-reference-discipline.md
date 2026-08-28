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

Consumer reference behavior is enforced by **R3** (references roles, never
modules/classes) and **R7** (request path) in `00-core/capability-rules.md`.

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
(`02-cycle/agent-execution-protocol.md`, Phase 8) by publishing component
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
and which component executor provides it — one entry per implementation:

```yaml
capabilities:
  - id: <capability-a>
    implementation_id: <implementation-a>
    version: 1.0.0
    operations: [<operation-1>, <operation-2>]
    executor: <product_sub>.components.<component_a>:execute
  - id: <capability-a>          # SECOND implementation of the SAME contract
    implementation_id: <implementation-b>
    version: 1.1.0
    operations: [<operation-1>, <operation-2>]
    executor: <product_sub>.components.<component_b>:execute
```

Two entries declaring the same capability id are two implementations of the ONE
contract; the Registry then offers both candidates to policy/selector. The
contract and the consumers never change — only the manifests differ.

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
   implementation modules/classes or registration functions (per R3/R7).
4. Contract inputs/outputs must be generic data (dicts/shapes from the
   contract), not implementation types.
5. Before accepting a design, verify: "If I replace the component that
   provides capability X, does consumer code change?" If yes, the design
   violates this discipline and MUST be corrected.
6. Component modules live behind a boundary (e.g. a `components/` group)
   and expose only their executor; registration is assembled externally.
7. The product's terminal/CLI input handling is ordinary consumer code —
   reached through the product's single request-construction point per R7 (see
   "Request path and layering" below).
8. Decomposition per **R2**/**R3** — see "Capability decomposition" below.

## Request path and layering

Enforced by **R7** in `00-core/capability-rules.md`. Every consumer-visible
capability request follows one canonical path:

```text
consumer code (terminal/CLI input, logic, anything)
        ->  single request-construction point
        ->  Bridge
        ->  registry discovery  ->  policy  ->  selector  ->  component executor
```

R7 defines the single request-construction point, the no-BridgeRequest rule for
all other product code, and the verification harness as the ONE exception
constructing requests directly to evaluate the trace. The Bridge returns the
trace `validated → discovered → policy_evaluated → selected → executed`; a
component is a registration-unaware executor reached only by the Bridge.

## Capability decomposition

Enforced by **R2**, **R3**, **R6** in `00-core/capability-rules.md`. The cycle
splits goals into such units (Phase 1.5/2) and the Verify phase (7) proves the
RESULT still carries them: the harness fails if one capability silently
absorbed a second responsibility (forcing a `split/refactor` decision).

Identity and dependencies are product-neutral per **R1** and **R5**.
Product-specific semantics belong in the consumer, the single
request-construction point, or composition/configuration — not inside the
reusable contract.

A product whose "one capability does everything" only proves decomposition
happened on paper but not in the result.

## Implementation resolution

When a capability is discovered, resolution follows one chain:

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

The agent must never treat a source file path as the runtime identity of a
capability. Runtime identity comes from the canonical Registry/implementation
model. Consumers resolve the capability contract through the Bridge, receive
generic contract-shaped data, and never import `<component_module>`,
`<ImplementationClass>`, or a `register_*` function.

## Conformance gate

This rule is a hard gate in the agent conformance checklist. A cycle is not
complete while any consumer references a concrete component or any component
contains registration logic.
