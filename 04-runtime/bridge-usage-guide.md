# Bridge Usage Guide

This guide explains how products MUST use the canonical Bridge to execute capabilities.

## Architecture

```
Product Code
     │
     ▼
  BridgeRequest
     │
     ▼
┌─────────┐
│  Bridge  │
└─────────┘
     │
     ├──▶ Registry (discovery)
     ├──▶ Policy (authorization)
     ├──▶ Selector (routing)
     └──▶ Executor (implementation)
           │
           ▼
       BridgeResponse
           │
           ▼
      Product Code
```

## Request format

Every request to the Bridge MUST follow this structure:

```python
@dataclass(frozen=True)
class BridgeRequest:
    request_id: str           # unique request identifier
    capability_id: str        # ID of the capability to execute
    contract_version: str     # required contract version
    operation: str            # operation name from the contract
    input: dict[str, Any]     # operation input matching the contract
    policy_context: PolicyContext  # authorization context
```

## Response format

The Bridge ALWAYS returns this structure:

```python
@dataclass(frozen=True)
class BridgeResponse:
    request_id: str           # matches the request
    capability_id: str        # capability that was executed
    contract_version: str     # contract version that was used
    implementation_id: str    # specific implementation that ran
    output: dict[str, Any]    # operation output
    trace: tuple[str, ...]    # stage trace for debugging
```

## Error format

On failure, the Bridge raises:

```python
@dataclass
class BridgeError(Exception):
    code: str                 # error code (e.g., "BRIDGE_NO_IMPLEMENTATION")
    stage: str                # stage where error occurred
    message: str              # human-readable message
    details: dict | None      # additional error context
```

## Usage pattern

### 1. Resolve the Bridge

```python
from bridge import Bridge
from registry import CapabilityRegistry
from policy import StaticPolicyEngine
from selector import DeterministicSelector

# Resolve from ecosystem root (NOT from product code)
bridge = Bridge(
    registry=CapabilityRegistry.resolve_from_ecosystem(),
    policy=StaticPolicyEngine.resolve_from_ecosystem(),
    selector=DeterministicSelector.resolve_from_ecosystem(),
)
```

### 2. Create a request

All examples use abstract placeholders; real capability IDs are resolved from
the ecosystem's authoritative manifests, not invented at the Blueprint layer.

```python
from bridge import BridgeRequest
from policy import PolicyContext

request = BridgeRequest(
    request_id="req-001",
    capability_id="<capability-a>",
    contract_version=">=1.0.0",
    operation="<operation>",
    input={
        "<input_a>": "<value-a>",
        "<input_b>": "<value-b>",
    },
    policy_context=PolicyContext(
        user={}, consumer={}, ecosystem={}, provider={}, module={},
    ),
)
```

### 3. Handle the response

```python
from bridge import BridgeError

try:
    response = bridge.handle(request)

    # Check trace for debugging
    if "executed" not in response.trace:
        print(f"Warning: incomplete trace {response.trace}")

    # Use the generic contract-shaped output
    output = response.output
    if output["<flag>"]:
        print(f"Operation succeeded: {output['<value>']}")

except BridgeError as e:
    print(f"Bridge error: {e.code}@{e.stage}: {e.message}")
    if e.details:
        print(f"Details: {e.details}")
```

### 4. Failover handling

The Bridge supports failover for implementations that declare it:

```python
try:
    response = bridge.handle(request)
except BridgeError as e:
    if e.code == "BRIDGE_ALL_IMPLEMENTATIONS_FAILED":
        # All implementations failed
        print("No healthy implementation available")
    elif e.code == "BRIDGE_POLICY_DENIED":
        # Policy rejected all candidates
        print("Not authorized")
    elif e.code == "BRIDGE_NO_IMPLEMENTATION":
        # No compatible implementation found
        print("Capability not available")
    else:
        # Other error
        raise
```

## Rules

1. Products MUST use the canonical Bridge, never create a local copy.
2. Products MUST NOT bypass the Bridge to call implementations directly.
3. Products MUST include a unique `request_id` in every request.
4. Products MUST handle `BridgeError` and not let it propagate unhandled.
5. Products MUST NOT use the trace for control flow; it is for debugging only.
6. Products MUST resolve the Bridge from the ecosystem root, not from product code.
7. Products MUST NOT reference concrete component modules, classes, or registration functions anywhere in consumer code; all capability access is through the Bridge contract (see `capability-reference-discipline.md`).
8. Component→capability registration MUST be data-driven: performed during the Publish phase by the capability manifest + a generic assembler. Components MUST NOT contain registration logic, so swapping an implementation requires no consumer code change.
9. Bridge request `input` and response `output` MUST be generic contract-shaped data; implementation-specific types MUST NOT cross the Bridge boundary.
