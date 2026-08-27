# Product Integration Example

This example shows how to create a new product that properly integrates with
the ARPAPED ecosystem. All identifiers are abstract placeholders
(`<product>`, `<capability-a>`, `<component_a>`) — the same discipline applies
to the documentation as to the code: no concrete product, capability, or
component identity is embedded at the Blueprint layer.

## Scenario

Create a new product that consumes three generic ecosystem capabilities
(`<capability-a>`, `<capability-b>`, `<capability-c>`) through the canonical
Bridge. The product exposes no capabilities of its own.

## Step 1: Create product manifest

Create `manifest.yaml` at the top-level directory that holds the product's
source (the directory path is a placeholder — `<top_level_dir>`; no fixed
name is mandated):

```yaml
product:
  identity:
    id: "<product>"
    name: "<Product Display Name>"
    version: "1.0.0"
    domain: "<domain>"

  dependencies:
    bridge: ">=1.0.0"
    registry: ">=1.0.0"

  roles:                       # logical role -> capability_id (consumer speaks in roles)
    - <role_a>: <capability-a>
    - <role_b>: <capability-b>
    - <role_c>: <capability-c>

  integration:
    entry_point: "<product_pkg>:initialize"
    bridge_request_path: "canonical"

  discoverability:
    tags: ["<tag-a>", "<tag-b>"]
    metadata: {}

  lifecycle:
    state: "development"
    support_contact: "<contact>"
```

## Step 2: Resolve ecosystem root

```python
# <product_pkg>/__init__.py

from pathlib import Path

ECOSYSTEM_ROOT = Path(__file__).parent.parent / "arpaped-ecosystem"


def initialize():
    """Initialize the product with ecosystem integration."""
    from bridge import Bridge
    from registry import CapabilityRegistry
    from policy import StaticPolicyEngine
    from selector import DeterministicSelector

    registry = CapabilityRegistry.resolve_from(ECOSYSTEM_ROOT)
    policy = StaticPolicyEngine.resolve_from(ECOSYSTEM_ROOT)
    selector = DeterministicSelector.resolve_from(ECOSYSTEM_ROOT)

    return Bridge(registry=registry, policy=policy, selector=selector)
```

## Step 3: Use the Bridge for capability execution

The consumer references ONLY capability IDs, contract operations, and
contract-shaped generic data. It never names a component.

```python
# <product_pkg>/workflow.py

from bridge import BridgeRequest, BridgeError
from policy import PolicyContext


def invoke(bridge, capability_id, operation, payload, request_id):
    request = BridgeRequest(
        request_id=request_id,
        capability_id=capability_id,
        contract_version="1.0.0",
        operation=operation,
        input=payload,
        policy_context=PolicyContext(user={}, consumer={}, ecosystem={}, provider={}, module={}),
    )
    return bridge.handle(request).output


def run_step(bridge, roles):
    # resolve role -> capability_id at startup; speak only in that ID + operations
    cap = roles["<role_a>"]

    result = invoke(
        bridge,
        cap,
        "transform",
        {"entity": {"id": "x-1", "class": "category-1"}},
        f"step-a",
    )

    try:
        return result["output_value"]
    except BridgeError as e:
        print(f"Capability failed: {e.code}@{e.stage}: {e.message}")
        return None
```

## Step 4: Follow the execution cycle

When adding features to the product, follow the agent execution protocol:

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
        pass  # bypasses the ecosystem

# BAD: Calling implementation directly
from <component_a> import <some_fn>  # direct import of a component

# BAD: Creating a local Registry
class LocalRegistry:
    def discover(self, capability_id):
        pass  # duplicates ecosystem functionality

# BAD: consumer referencing concrete components / registration functions
from <component_a> import <TypeA>, register_<component_a>  # direct component
register_<component_a>(self.registry)                       # binds consumer to component
record = <component_a>.<TypeA>(...)                         # implementation type crosses boundary
```

## What TO do

```python
# GOOD: Using canonical Bridge for every capability request
response = bridge.handle(BridgeRequest(
    capability_id="<capability-a>",
    operation="<operation>",
    ...
))

# GOOD: consumer code references roles only, resolved to capability IDs at runtime
cap = roles["<role_a>"]
output = invoke(bridge, cap, "<operation>", payload, request_id="req-001")
```

## Capability-reference discipline (mandatory)

A product must consume capabilities through their contracts, never through
concrete components. Registration is part of the workflow's **Publish** phase
and is owned by the manifest + a generic assembler, never by components. Three
indirections make this enforceable:

1. **Capability contract data lives in a manifest.** The manifest declares
   the capability's id, version, operations, and the component executor that
   provides it. Components do NOT contain `register` functions:

   ```yaml
   capabilities:
     - id: <capability-a>
       implementation_id: <implementation-a>
       version: 1.0.0
       operations: [<operation>]
       executor: <product_sub>.components.<component_a>:execute
   ```

2. **A generic assembler registers from the manifest.** During Publish, the
   assembler imports each component's executor and builds the implementation
   record. The component is registration-unaware:

   ```python
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

3. **Consumer roles come from the product manifest.** Consumer logic speaks
   only in role names resolved to capability IDs at startup:

   ```yaml
   roles:
     - <role_a>: <capability-a>
   ```

4. **Contract data is generic.** Inputs/outputs are contract-shaped generic
   data, not implementation classes:

   ```python
   entity = {"id": "x-1", "class": "category-1", "enabled": True}
   ```

Do NOT copy a real capability ID or component module path from this document;
look them up in your ecosystem's own authoritative manifests.

See `capability-reference-discipline.md` for the full mandatory rules.
