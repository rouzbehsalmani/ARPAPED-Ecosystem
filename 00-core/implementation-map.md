# Implementation Map

The Blueprint is executable by an agent because it defines how to resolve implementation rather than embedding a duplicate implementation.

## Resolution rule

For every required ecosystem primitive:

`Blueprint requirement -> authoritative manifest -> canonical implementation -> contract`

The agent must resolve these at runtime from the supplied ecosystem root.

## Required primitives

| Primitive | Agent must resolve | Agent must not invent |
|---|---|---|
| Bridge | canonical execution boundary | product-local bridge |
| Registry | canonical discovery service/index | product-local registry |
| Policy | canonical policy stage | hidden product policy |
| Capability | canonical capability contract/model | ad-hoc capability format |
| Component | canonical component identity/contract | product-only generic component |
| Product | canonical product model | standalone execution identity |
| Implementation | canonical implementation record | unregistered implementation |
| Connector | canonical connector contract | direct hidden dependency |
| Resource Exchange | canonical resource execution path when required | private resource runtime |
| Capability binding | manifest + generic assembler (Publish phase) binding capability→implementation | registration embedded in components or consumer code |

## Capability-reference discipline

Components are bound to capabilities through a data-driven manifest, and
consumers reference ONLY capability contracts through the Bridge — never a
concrete component module, class, or registration function. Registration is
an assembly concern owned by the manifest + generic assembler during the
Publish phase; components are registration-unaware executors. This is a hard
conformance gate. See `04-runtime/capability-reference-discipline.md`.
Exact filesystem paths are intentionally resolved from authoritative manifests rather than hard-coded by this Blueprint.
