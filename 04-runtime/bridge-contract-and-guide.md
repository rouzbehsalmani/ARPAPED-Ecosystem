# Canonical Bridge — Implementation Contract & Usage Guide

One document, two audiences. **Part A** is for whoever verifies that the
ecosystem's canonical Bridge conforms. **Part B** is for every product that
uses it. All definitions are in `00-core/glossary.md`.

## Part A — Implementation contract

The self-improving agent resolves and uses the ecosystem's existing canonical
Bridge; the Blueprint never prescribes a replacement implementation. The agent
must verify from authoritative ecosystem artifacts:

- the Bridge identity;
- its canonical request path;
- validation stage;
- discovery stage;
- policy stage;
- selection stage;
- execution handoff;
- tracing/receipt requirements where defined by the ecosystem.

A product becomes a consumer of this path and must not reproduce the Bridge
pipeline locally.

### Bridge Trace

The Bridge MUST return a `trace` field in its response: an ordered tuple of
stage identifiers recording which stages the request completed.

| Stage | Meaning |
|-------|---------|
| `validated` | Request passed structural validation (required fields present, correct types). |
| `discovered` | Registry returned one or more compatible implementations. |
| `policy_evaluated` | Policy engine evaluated all candidates against the policy context. |
| `selected` | Selector chose one or more candidates for execution. |
| `executed` | Selected implementation completed successfully. |

Trace rules:

- Stages appear in the order listed above.
- On success, the trace contains all five stages.
- On failure, the trace contains only the stages reached before the error.
- The trace MUST NOT be empty, even on failure (at minimum `validated`).
- Consumers MAY use the trace for debugging, auditing, and verification
  evidence; the trace MUST NOT be used as a control-flow mechanism.

## Part B — Usage guide

### Architecture

```text
Product Code -> BridgeRequest -> Bridge
  ├── Registry (discovery)
  ├── Policy (authorization)
  ├── Selector (routing)
  └── Executor (implementation) -> BridgeResponse -> Product Code
```

### Request format

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

### Response format

```python
@dataclass(frozen=True)
class BridgeResponse:
    request_id: str           # matches the request
    capability_id: str        # capability that was executed
    contract_version: str     # contract version that was used
    implementation_id: str    # specific implementation that ran
    output: dict[str, Any]    # operation output
    trace: tuple[str, ...]    # stage trace — evaluation evidence
```

### Error format

```python
@dataclass
class BridgeError(Exception):
    code: str                 # e.g. "BRIDGE_NO_IMPLEMENTATION"
    stage: str                # stage where the error occurred
    message: str              # human-readable message
    details: dict | None      # additional error context
```

### Usage pattern

**1. Resolve the Bridge** — from the ecosystem root, never from product code:

```python
bridge = Bridge(
    registry=CapabilityRegistry.resolve_from_ecosystem(),
    policy=StaticPolicyEngine.resolve_from_ecosystem(),
    selector=DeterministicSelector.resolve_from_ecosystem(),
)
```

**2. Create a request** — real capability IDs come from the ecosystem's
authoritative manifests (see `00-core/glossary.md` and
`00-core/implementation-map.md`). Abstract placeholders below are shape only:

```python
request = BridgeRequest(
    request_id="req-001",
    capability_id="<capability-a>",
    contract_version=">=1.0.0",
    operation="<operation>",
    input={"<input_a>": "<value-a>", "<input_b>": "<value-b>"},
    policy_context=PolicyContext(user={}, consumer={}, ecosystem={}, provider={}, module={}),
)
```

**3. Handle the response** — and treat the trace as evidence, not control flow:

```python
try:
    response = bridge.handle(request)
    if "executed" not in response.trace:
        # debugging/observability only; verification harnesses evaluate fully
        print(f"Warning: incomplete trace {response.trace}")
    output = response.output
except BridgeError as e:
    print(f"Bridge error: {e.code}@{e.stage}: {e.message}")
```

**4. Failover handling** — the Bridge supports failover for implementations
that declare it:

```python
except BridgeError as e:
    if e.code == "BRIDGE_ALL_IMPLEMENTATIONS_FAILED":
        print("No healthy implementation available")
    elif e.code == "BRIDGE_POLICY_DENIED":
        print("Not authorized")
    elif e.code == "BRIDGE_NO_IMPLEMENTATION":
        print("Capability not available")
    else:
        raise
```

### Rules

All binding consumer rules live in `04-runtime/capability-reference-discipline.md`
(request path, layering, one contract per capability) and
`04-runtime/verification-contract.md` (how the trace is evaluated in a pass).
The only Bridge-specific rules repeated here:

1. Use the canonical Bridge; never create a local copy or second request pipeline.
2. Never bypass the Bridge to call an implementation directly.
3. Include a unique `request_id` in every request.
4. Handle `BridgeError`; do not let it propagate unhandled.
5. Never use the trace for control flow.
6. Request `input` and response `output` are generic contract-shaped data;
   implementation-specific types must not cross the Bridge boundary.