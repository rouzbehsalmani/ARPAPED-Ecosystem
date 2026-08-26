# Reusable Implementation Contract

A newly created capability/component is reusable only if its implementation boundary does not encode assumptions belonging exclusively to the product that triggered its creation, unless those assumptions are intrinsic to the responsibility itself.

## Required implementation properties

- generic responsibility;
- explicit contract;
- stable identity;
- version;
- declared dependencies;
- no hidden product dependency;
- no hidden renderer/UI dependency unless the responsibility is explicitly UI-specific;
- canonical discoverability metadata;
- runtime resolvability where applicable;
- lineage to the cycle that created or changed it.

## Example decision

Bad:

`MakCityBuildingCollisionCapability`

when the actual responsibility is generic spatial collision.

Preferred:

`SpatialCollisionCapability`

with MakCity using it as one consumer.

The same rule applies to every domain.
