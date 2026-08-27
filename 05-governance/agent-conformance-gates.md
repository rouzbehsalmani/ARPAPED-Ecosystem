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

A NO means the cycle is not complete.
