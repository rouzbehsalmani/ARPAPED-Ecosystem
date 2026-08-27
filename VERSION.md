# Version

ARPAPED Self-Improving Cycle Blueprint v1.1.0

This revision converts the conceptual cycle Blueprint into an Agent-Executable Blueprint.

Added:
- mandatory Agent Bootstrap Protocol;
- authoritative implementation resolution;
- ecosystem implementation map;
- machine-readable agent execution contract;
- operational discovery algorithm;
- build-time/runtime discovery parity;
- canonical Bridge implementation contract;
- canonical Registry implementation contract;
- reusable implementation contract;
- adaptive split protocol;
- implementation templates;
- agent conformance gates;
- machine-readable cycle input, discovery key, and implementation schemas;
- product manifest template;
- component contract template;
- Bridge usage guide;
- product integration example;
- Bridge trace definition and schema.

## Capability Reference Discipline (v1.1.0+)

Adds the mandatory **capability-reference discipline**
(`04-runtime/capability-reference-discipline.md`):

- consumers reference only capability contracts through the Bridge, never concrete
  component modules/classes/registration functions;
- component→capability registration is performed during the **Publish** phase by
  the capability manifest + a generic assembler — components are
  registration-unaware executors and contain no `register` logic
  (swapping a component requires no consumer code change);
- contract inputs/outputs are generic contract-shaped data, not implementation types;
- added conformance gates 13-16 and Manifest roles mapping to enforce the rule.

This closes a recurring failure where changing a capability component forced edits
to every consumer. The Blueprint remains product-independent and keeps product
evaluation outside its scope.

## Concrete-sample removal (v1.1.0+)

All examples across the Blueprint now use abstract placeholders
(`<capability-a>`, `<component_a>`, `<role_a>`) instead of concrete product,
capability, or component identifiers. Embedding a concrete sample would itself
violate the capability-reference discipline the Blueprint prescribes. Real
identifiers must be resolved from the ecosystem's authoritative manifests.
