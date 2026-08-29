# Build Walkthrough

`CYCLE.md` defines the phases and gates. `RULES.md` defines the invariants
they enforce. This file turns both into literal actions for **this specific
repository**, in the order you actually do them, before you write a single
line of feature code. If you were asked to build an application "based on
this Blueprint," start here.

## 0. What already exists here — use it, never reinvent it

The canonical Bridge, Registry, Policy engine, Selector, and assembler this
Blueprint tells you to resolve are **already implemented in this repo**, at
`bridge/`:

| Piece | Import | File |
|---|---|---|
| Bridge | `from bridge.bridge import Bridge, BridgeRequest, BridgeResponse, BridgeError` | `bridge/bridge.py` |
| Registry | `from bridge.registry import CapabilityRegistry, CapabilityImplementation` | `bridge/registry.py` |
| Policy | `from bridge.policy import StaticPolicyEngine, PolicyContext, PolicyDecision` | `bridge/policy.py` |
| Selector | `from bridge.selector import DeterministicSelector` (or `CircuitBreakingSelector` for failover) | `bridge/selector.py` |
| Assembler | `from bridge.assembler import assemble` | `bridge/assembler.py` |

This **is** the canonical execution boundary that `CYCLE.md` Phase 0 tells you
to resolve, and the "generic assembler" `RULES.md` and `TEMPLATES.md` refer
to. Do not write a new Bridge, Registry, Policy, or Selector class, and do not
edit `bridge/*.py` — only import from it. `contracts/` does not exist yet in
this repo; you create it as you add capabilities. There is no product
concept and no per-application copy of the Bridge: one Bridge, built once,
serves every capability you add.

## 1. Bootstrap (CYCLE.md Phase 0 — Gates 1, 2, 3, 25)

Before decomposing the goal:

- [ ] Confirm `bridge/bridge.py`, `bridge/registry.py`, `bridge/policy.py`,
      `bridge/selector.py`, `bridge/assembler.py` exist and read them. This
      satisfies "resolve the canonical Bridge/Registry" (Gates 1, 2) without
      inventing anything (Gate 3).
- [ ] Write the ecosystem-resolution record (Gate 25) — e.g.
      `state/ecosystem-resolution.json`:

  ```json
  {
    "bridge": "bridge.bridge:Bridge",
    "registry": "bridge.registry:CapabilityRegistry",
    "policy": "bridge.policy:StaticPolicyEngine",
    "selector": "bridge.selector:DeterministicSelector",
    "contracts_area": "contracts/",
    "root": "<repo root>"
  }
  ```

- [ ] Do not create a second Bridge/Registry anywhere in your code.

## 2. Decompose the goal into capabilities (Phase 1–2, R1)

List the independently meaningful responsibilities the goal requires. Name
each one `<domain>.<operation>` — precise and small-scale (R1) — never a
vague role (`<domain>.manager`) and never one capability that does
everything. A bigger capability may depend on several more-generic ones
(R4); build the generic ones first.

## 3. Per capability: contract → manifest → code, in that order (Phase 5, R7)

For every capability from step 2:

1. **Contract first** — `contracts/<domain>.<operation>.contract.yaml`,
   valid against `schemas/component-contract.schema.json`. That schema sets
   `additionalProperties: false` at every level, so only these keys exist:
   top-level `contract:` wrapping REQUIRED `identity` (`id, name, version,
   domain, family, type` — `type` is exactly `capability`, `connector`, or
   `service`), `responsibility` (`description` required, `invariants`
   optional), `interface.operations[]` (each operation's `name`,
   `description`, and `errors[]` are REQUIRED — `errors` may be an empty
   list but the key must exist; `input`/`output` are optional),
   `dependencies`, `discoverability`, `versioning`, `lineage` (`policy` and
   `runtime` are optional and may be omitted). Validate it before moving on.
2. **Manifest second** — a capability manifest valid against
   `schemas/capability-manifest.schema.json`: top-level `capability_id`,
   `contract_version`, `implementations[]` (each: `implementation_id`,
   `version`, `operations[]`, `executor` as `"module.path:attr"`). Do this
   only after the contract validates.
3. **Code third** — the executor: `def execute(operation, input, policy):
   -> dict`. It never imports the Registry and never calls `register`. Write
   it only after the manifest exists and validates.

Writing the executor before its contract and manifest exist is a Gate 26
violation, no matter how small the capability is.

### Worked skeleton: `demo.echo`

This is scaffolding to prove the wiring, not a feature — delete it once
your own first capability follows the same shape, and never copy its
`echo`/`message` domain content into real capabilities. Only copy the file
order and the wiring pattern. Built in the exact order above:

**Step 1 — the contract**, `contracts/demo.echo.contract.yaml`:

```yaml
contract:
  identity:
    id: demo.echo
    name: Demo Echo
    version: "1.0.0"
    domain: demo
    family: demo
    type: capability
  responsibility:
    description: >
      Returns its input unchanged. Exists only to prove the
      contract -> manifest -> executor -> Bridge wiring end to end.
    invariants:
      - does not modify its input
  interface:
    operations:
      - name: echo
        description: Returns the given message unchanged.
        input:
          - name: message
            type: string
            required: true
            description: Text to echo back.
        output:
          type: object
          description: "An object shaped { message: <the same text> }."
        errors:
          - code: INVALID_INPUT
            description: message was missing or not a string.
  dependencies:
    capabilities: []
    components: []
    resources: []
  discoverability:
    tags: [demo]
    metadata: {}
  versioning:
    compatibility: backward
    deprecation_policy: none
  lineage:
    created_by: walkthrough-skeleton
    changed_by: walkthrough-skeleton
    history: []
```

**Step 2 — the manifest**, `capabilities/demo/echo/manifest.yaml`:

```yaml
capability_id: demo.echo
contract: contracts/demo.echo.contract.yaml
contract_version: "1.0.0"
implementations:
  - implementation_id: demo.echo.default
    version: "1.0.0"
    operations: [echo]
    executor: capabilities.demo.echo.executor:execute
```

**Step 3 — the executor**, `capabilities/demo/echo/executor.py` (add empty
`__init__.py` files to `capabilities/`, `capabilities/demo/`, and
`capabilities/demo/echo/` so the dotted executor path above is importable):

```python
from bridge.bridge import BridgeError

def execute(operation, input, policy):
    if operation != "echo":
        raise BridgeError("UNSUPPORTED_OPERATION", "execution", f"no such operation: {operation}")
    message = input.get("message")
    if not isinstance(message, str):
        raise BridgeError("INVALID_INPUT", "execution", "message must be a string")
    return {"message": message}
```

**Step 4 — the wiring**, shown inline as a minimal standalone proof (not yet
the production shape — see steps 4–5 below for that):

```python
import uuid, yaml
from bridge.assembler import assemble
from bridge.registry import CapabilityRegistry
from bridge.policy import StaticPolicyEngine, PolicyContext
from bridge.selector import DeterministicSelector
from bridge.bridge import Bridge, BridgeRequest

registry = CapabilityRegistry()
manifest = yaml.safe_load(open("capabilities/demo/echo/manifest.yaml"))
assemble(manifest, registry)

bridge = Bridge(registry, StaticPolicyEngine(), DeterministicSelector())
request = BridgeRequest(
    request_id=uuid.uuid4().hex,
    capability_id="demo.echo",
    contract_version=">=1.0.0",
    operation="echo",
    input={"message": "hello"},
    policy_context=PolicyContext(user={}, consumer={}, ecosystem={}, provider={}, module={}),
)
response = bridge.handle(request)
assert response.output == {"message": "hello"}
assert response.trace == ("validated", "discovered", "policy_evaluated", "selected", "executed")
```

That last assertion is the whole point: it's the Bridge's own observed
trace, reaching `executed`, for a capability that only exists as a contract
+ manifest + registration-unaware executor — nothing called `execute`
directly.

## 4. The single request-construction point (Phase 6, R6)

In a real application (not the standalone proof above), exactly ONE module
owns this wiring — e.g. `app/requests.py`:

```python
_registry = CapabilityRegistry()
# ... assemble every manifest into _registry (see step 5) ...
_bridge = Bridge(_registry, StaticPolicyEngine(), DeterministicSelector())

def call(capability_id, operation, input, policy_context=None):
    request = BridgeRequest(
        request_id=uuid.uuid4().hex,
        capability_id=capability_id,
        contract_version=">=1.0.0",
        operation=operation,
        input=input,
        policy_context=policy_context or PolicyContext(user={}, consumer={}, ecosystem={}, provider={}, module={}),
    )
    return _bridge.handle(request)
```

Every other module — CLI parsing, a game loop, a web handler, anything —
calls `requests.call(...)`. Nothing else constructs a `BridgeRequest` or
calls `bridge.handle` directly (the verification harness in step 6 is the
one exception, per R6).

## 5. Assemble every manifest at startup (Phase 8 mechanics, R8's indirections)

Inside the same module that builds `_registry`, register every capability
once, at import time — this is the only place `assemble`/`register` runs:

```python
from pathlib import Path
import yaml

for manifest_path in Path("capabilities").rglob("manifest.yaml"):
    assemble(yaml.safe_load(manifest_path.read_text()), _registry)
```

## 6. Headless verification harness (Phase 7, RULES.md "Verification contract")

Lives outside the application packages, e.g. `tests/verify.py`. It must:

- Reuse the SAME Bridge `app/requests.py` builds — never assemble a second
  one.
- For every capability operation, call it (directly via `BridgeRequest` +
  `bridge.handle`, or through `requests.call`) and assert the response
  `trace` equals `("validated", "discovered", "policy_evaluated",
  "selected", "executed")` — copied from the observed response, never
  hand-written.
- Drive every consumer-visible interaction through a scripted command
  stream using the same dispatcher the real interface uses.
- Include at least one case proving an operator decision window: a scripted
  action lands between two automatic ticks and its effect is observable.
- Write `state/verification-record.json`, valid against
  `schemas/verification-record.schema.json`: `verification_id`, `state_ref`,
  `harness`, `checks[]` (unique `check_id` per check; a check with
  `check_type: capability_operation` MUST carry a `trace` array copied
  verbatim from the observed response), `passed`, `failed`, `status`
  (`"verified"` or `"failed"`).

Fail closed: if any check fails, fix it and re-run before step 7.

## 7. Publish and return state (Phase 8–9)

- Confirm `registry.discover(capability_id, contract_version, operation)`
  returns a candidate for every capability you built.
- Write the cycle report using the template in `TEMPLATES.md`.
- The resulting state — `contracts/`, `capabilities/`, `app/`, `tests/`,
  `state/verification-record.json`, and the report — is everything the next
  cycle needs. No private memory of this session should be required to
  continue the work (Gate 11).

## Failure patterns this file exists to prevent

- Writing the feature straight into one class/file, with a CLI dispatcher
  calling its methods directly — no contract, no manifest, no Bridge
  anywhere. (This is what happened the first time this Blueprint was
  handed to an agent without this file.)
- Treating "based on this Blueprint" as a naming or flavor theme rather than
  an operating procedure.
- Skipping the verification harness because the application "runs fine
  manually."
