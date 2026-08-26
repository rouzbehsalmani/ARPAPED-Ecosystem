# Canonical Registry Implementation Contract

The agent must resolve the existing Registry implementation from authoritative ecosystem metadata.

The Registry must provide, directly or through its canonical indexing layer:

- component/capability identity lookup;
- selective classification lookup;
- contract/version lookup;
- implementation resolution;
- lifecycle visibility;
- lineage/discoverability metadata;
- bounded candidate retrieval;
- partition/shard-aware access where required by scale.

The Blueprint does not duplicate Registry source code.

If the existing Registry cannot satisfy the Blueprint's scale requirements, that is an ecosystem implementation gap to be reported and addressed—not a reason to create a product-local Registry.
