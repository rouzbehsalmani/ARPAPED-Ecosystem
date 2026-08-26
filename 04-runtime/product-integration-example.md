# Product Integration Example

This example shows how to create a new product that properly integrates with the ARPAPED ecosystem.

## Scenario

Create a product called "MakCity" that uses the ecosystem's spatial collision, resource exchange, and terrain rendering capabilities.

## Step 1: Create product manifest

Create `manifest.yaml` at the product root:

```yaml
product:
  identity:
    id: "makcity"
    name: "MakCity"
    version: "1.0.0"
    domain: "urban_simulation"

  dependencies:
    bridge: ">=1.0.0"
    registry: ">=1.0.0"
    capabilities:
      - id: "spatial-collision"
        version: ">=1.0.0"
      - id: "resource-exchange"
        version: ">=1.0.0"
      - id: "terrain-rendering"
        version: ">=1.0.0"

  integration:
    entry_point: "makcity:initialize"
    bridge_request_path: "canonical"

  discoverability:
    tags: ["urban", "simulation", "3d"]
    metadata:
      engine: "unity"

  lifecycle:
    state: "development"
    support_contact: "team@makcity.example"
```

## Step 2: Resolve ecosystem root

```python
# makcity/__init__.py

from pathlib import Path

ECOSYSTEM_ROOT = Path(__file__).parent.parent / "arpaped-ecosystem"

def initialize():
    """Initialize MakCity with ecosystem integration."""
    from bridge import Bridge
    from registry import CapabilityRegistry
    from policy import StaticPolicyEngine
    from selector import DeterministicSelector
    
    # Resolve canonical implementations from ecosystem
    registry = CapabilityRegistry.resolve_from(ECOSYSTEM_ROOT)
    policy = StaticPolicyEngine.resolve_from(ECOSYSTEM_ROOT)
    selector = DeterministicSelector.resolve_from(ECOSYSTEM_ROOT)
    
    # Create Bridge instance
    bridge = Bridge(registry=registry, policy=policy, selector=selector)
    
    return bridge
```

## Step 3: Use Bridge for capability execution

```python
# makcity/simulation.py

from bridge import BridgeRequest, BridgeError
from policy import PolicyContext


class Simulation:
    def __init__(self, bridge):
        self.bridge = bridge
        self.policy_context = PolicyContext(
            user_id="makcity",
            permissions=["spatial:read", "resource:read", "terrain:read"],
        )
    
    def check_collision(self, entity_a, entity_b):
        """Check collision using ecosystem capability."""
        request = BridgeRequest(
            request_id=f"collision-{entity_a.id}-{entity_b.id}",
            capability_id="spatial-collision",
            contract_version=">=1.0.0",
            operation="detect_collision",
            input={
                "shape_a": entity_a.shape,
                "shape_b": entity_b.shape,
            },
            policy_context=self.policy_context,
        )
        
        try:
            response = self.bridge.handle(request)
            return response.output["collides"]
        except BridgeError as e:
            print(f"Collision check failed: {e}")
            return False
    
    def transfer_resource(self, from_entity, to_entity, resource_type, amount):
        """Transfer resource using ecosystem capability."""
        request = BridgeRequest(
            request_id=f"transfer-{from_entity.id}-{to_entity.id}",
            capability_id="resource-exchange",
            contract_version=">=1.0.0",
            operation="transfer",
            input={
                "from": from_entity.id,
                "to": to_entity.id,
                "resource": resource_type,
                "amount": amount,
            },
            policy_context=self.policy_context,
        )
        
        try:
            response = self.bridge.handle(request)
            return response.output["success"]
        except BridgeError as e:
            print(f"Resource transfer failed: {e}")
            return False
    
    def render_terrain(self, terrain_data):
        """Render terrain using ecosystem capability."""
        request = BridgeRequest(
            request_id=f"terrain-{id(terrain_data)}",
            capability_id="terrain-rendering",
            contract_version=">=1.0.0",
            operation="render",
            input={
                "data": terrain_data,
                "format": "mesh",
            },
            policy_context=self.policy_context,
        )
        
        try:
            response = self.bridge.handle(request)
            return response.output["mesh"]
        except BridgeError as e:
            print(f"Terrain rendering failed: {e}")
            return None
```

## Step 4: Register product in Registry

The product manifest must be registered so other products can discover it:

```python
# makcity/registration.py

from registry import CapabilityRegistry, ImplementationRecord


def register_makcity(registry: CapabilityRegistry):
    """Register MakCity as a consumer of ecosystem capabilities."""
    
    # The product itself doesn't need registration unless it exposes capabilities
    # But it does need to register its intent to use capabilities
    
    record = ImplementationRecord(
        implementation_id="makcity",
        capability_id="urban-simulation",
        contract_version="1.0.0",
        version="1.0.0",
        dependencies=["spatial-collision", "resource-exchange", "terrain-rendering"],
        discoverability={
            "tags": ["urban", "simulation"],
            "metadata": {"type": "product"},
        },
        lineage={
            "created_by": "cycle-001",
            "history": [],
        },
    )
    
    registry.register(record)
```

## Step 5: Follow the execution cycle

When adding features to MakCity, follow the agent execution protocol:

1. **Understand** — Resolve what ecosystem capabilities are available
2. **Decompose** — Break the feature into responsibilities
3. **Discover** — Find existing capabilities in the Registry
4. **Decide** — Choose: reuse, compose, split, or create
5. **Implement** — Use the Bridge to execute capabilities
6. **Integrate** — All requests go through the canonical Bridge
7. **Publish** — Register any new capabilities in the Registry
8. **Return** — Update state for the next cycle

## What NOT to do

```python
# BAD: Creating a local Bridge
class LocalBridge:
    def handle(self, request):
        # This bypasses the ecosystem!
        pass

# BAD: Calling implementation directly
from spatial_collision import detect_collision  # Direct import!

# BAD: Creating a local Registry
class LocalRegistry:
    def discover(self, capability_id):
        # This duplicates ecosystem functionality!
        pass
```

## What TO do

```python
# GOOD: Using canonical Bridge
bridge = Bridge.resolve_from_ecosystem()
response = bridge.handle(request)

# GOOD: All requests through Bridge
response = bridge.handle(BridgeRequest(
    capability_id="spatial-collision",
    operation="detect_collision",
    ...
))
```
