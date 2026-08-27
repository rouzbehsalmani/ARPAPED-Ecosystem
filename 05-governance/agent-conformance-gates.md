# Agent Conformance Gates

These are Blueprint conformance gates, not a product test suite.

Before declaring a cycle complete, the agent must be able to answer YES to:

1. Did I resolve the canonical Bridge?
2. Did I resolve the canonical Registry?
3. Did I avoid creating a parallel Bridge or Registry?
4. Did I discover existing reusable responsibilities before creating new ones?
5. Was discovery bounded and index-driven?
6. Did I prefer reuse over duplication?
7. If I created a component, is its responsibility product-independent where possible?
8. If I split a component, did I preserve lineage and update discoverability?
9. Is the resulting component discoverable through the canonical Registry?
10. Is the resulting implementation compatible with runtime resolution?
11. Is the resulting state sufficient for the next cycle to rediscover the work without private agent memory?
12. Did I audit existing components for split opportunities before proceeding?
13. Do my consumers reference only capability contracts and never concrete component modules, classes, or registration functions? (See `04-runtime/capability-reference-discipline.md`.)
14. Is component registration performed during the Publish phase by the manifest + a generic assembler, so that components contain no registration logic and swapping a component requires no consumer code change?
15. Are contract inputs/outputs generic data shaped by the contract, not implementation-specific types?
16. Do my components expose only their executor and never import the Registry or embed a `register` function?

17. Did I run the resulting state through a verification harness — headlessly, with no real terminal required — before publishing? (See `02-cycle/agent-execution-protocol.md` Phase 7 and `04-runtime/verification-contract.md`.)

18. Does the harness exercise every declared capability operation over contract-shaped data through the canonical Bridge, with every trace reaching `executed`?

19. Did I simulate every consumer-visible interaction via a scripted command stream and assert its observable effect — including running an automatic advancement loop in the SAME session as injected inputs, so a reactive loop cannot block interaction?

20. Does every previously-reported defect have a regression check that now PASSES, and is a machine-readable verification record (`schemas/verification-record.schema.json`) written into the resulting state and referenced in the cycle report?

A NO means the cycle is not complete.
