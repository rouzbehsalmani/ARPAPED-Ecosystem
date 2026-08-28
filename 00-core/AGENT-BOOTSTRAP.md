# ARPAPED Agent Bootstrap Protocol

This document is the mandatory entry procedure for any human or AI agent operating on an ARPAPED project.

The agent MUST follow this procedure before creating or modifying implementation.

## 1. Establish the ecosystem root

Locate the authoritative ARPAPED ecosystem root supplied by the operator.

Do not assume a product directory is the ecosystem root.

Do not create a second ecosystem copy.

## 2. Discover authoritative ecosystem metadata

Starting at the ecosystem root, locate the authoritative:

- ecosystem profile / manifest;
- canonical Bridge implementation;
- Registry implementation and registry records;
- policy implementation;
- capability/component contracts;
- product and implementation manifests;
- connector contracts;
- Resource Exchange implementation, where applicable.

Use the repository's own manifests and documentation as the authority for exact paths and versions.

If two authoritative-looking implementations conflict, STOP and report the ambiguity. Do not silently choose one.

## 3. Build an implementation map

Before implementation, create an in-memory or local working map:

```text
ECOSYSTEM
  ├─ Canonical execution boundary
  ├─ Discovery / Registry
  ├─ Policy
  ├─ Capability model
  ├─ Component model
  ├─ Product model
  ├─ Implementation model
  ├─ Connector model
  └─ Resource execution
```

Every node must resolve to an authoritative artifact in the ecosystem.

## 3.5 Write the ecosystem-resolution record

Bootstrap MUST emit a written, resolvable **ecosystem-resolution record** that
captures the resolved canonical identities — at minimum the canonical Bridge
and Registry, and the implementation map — so the resolution is discoverable,
auditable, and reusable by the next cycle (Gate 25). The record is part of the
resulting state and is referenced in the cycle report. Without it, the cycle
cannot proceed; a resolved-but-unrecorded Bridge is treated as unresolved.

Concretely, the record declares (in a machine-readable form, e.g. a small JSON
artifact or a dedicated section of the report):

```text
resolved:
  bridge:   <canonical bridge identity/version>
  registry: <canonical registry identity/version>
  policy:   <canonical policy stage>
  selector: <canonical selector>
  generic_area: <generic/ capability area path at the ecosystem root>
  root:     <the authoritative ecosystem root supplied by the operator>
map:
  - <primitive> -> <authoritative artifact path>
```

The canonical Bridge is the ONLY execution interface for every capability
operation in the product, in scripts, and in the verification harness (R9).

## 4. Load the operating rules

The agent MUST load and obey:

- this Blueprint;
- the ecosystem's authoritative manifests;
- canonical Bridge/Registry contracts;
- immutable architectural decisions;
- capability/component reuse rules;
- repository-local instructions and policies.

Local project instructions may refine implementation details but may not contradict canonical ecosystem rules.

## 5. Resolve the current state

The current state is the authoritative discoverable state of the ecosystem at the time the cycle begins.

The agent must not use its private conversation memory as the source of truth.

## 6. Accept the goal

Only after the foundation is resolved may the agent accept the requested goal as the cycle input.

## 7. Begin the recursive cycle

Proceed to `02-cycle/agent-execution-protocol.md`.

## Hard prohibitions

The agent MUST NOT:

- create a parallel Bridge;
- create a private Registry for a product;
- copy the entire ecosystem to make a product;
- implement a reusable responsibility as product-local merely for convenience;
- globally scan the Registry as the normal discovery mechanism;
- silently replace an authoritative implementation;
- treat a product's local manifest as proof that it is integrated with the ecosystem.
