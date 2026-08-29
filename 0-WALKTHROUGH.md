# Build Walkthrough

**Read this file in full before writing any code in this repository.** Every
past attempt that skipped it produced a plain monolith — a single class with
a pile of methods, no contracts, no manifests, no Bridge, no capabilities.
That is not a hypothetical risk; it has happened multiple times. If you read
nothing else here, read this one rule: **default to capability.** Any
distinct need — including things that look like plain infrastructure
(reading input, tracking time, dispatching a command) — gets a contract,
manifest, and executor, wired through the Bridge already implemented at
`bridge/`. The only two exceptions, anywhere in this document, are the
single request-construction point and the process entry point (both defined
below). A class with several methods that directly mutate application state
is a sign you're about to repeat the mistake — stop and decompose it into
capabilities instead.

`1-CYCLE.md` defines the phases and gates. `2-RULES.md` defines the invariants
they enforce. This file turns both into literal actions for **this specific
repository**, in the order you actually do them, before you write a single
line of feature code.

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

This **is** the canonical execution boundary that `1-CYCLE.md` Phase 0 tells you
to resolve, and the "generic assembler" `2-RULES.md` and `3-TEMPLATES.md` refer
to. Do not write a new Bridge, Registry, Policy, or Selector class, and do not
edit `bridge/*.py` — only import from it. `contracts/` does not exist yet in
this repo; you create it as you add capabilities. There is no product
concept and no per-application copy of the Bridge: one Bridge, built once,
serves every capability you add.

## 1. Bootstrap (1-CYCLE.md Phase 0 — Gates 1, 2, 3, 25)

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

**Default to capability, not local code.** When you need some behavior and
nothing already provides it, create the capability — even when it looks like
plain infrastructure or plumbing: a command dispatcher, a clock/time source,
raw input polling, a step that just sequences a few other capability calls
together. All of those are capability candidates first, local code only as a
last resort. Composing several other capabilities is a reason to give a
responsibility its own contract (a *specific* capability per R4, depending on
the generic ones) — never a reason to leave it as an ad hoc class or module.
Exactly two things in this entire walkthrough are never capabilities: the
single request-construction point (step 4) and the program's entry point
(step 4's caller — whatever starts the application and its top-level loop).
Both are a structural floor, not a judgment call — something has to exist
before the Bridge can route anything. Nothing else gets to skip a contract.

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

This module, plus the process entry point that starts the application (its
top-level loop should do little more than call capabilities in sequence
through this module), are the *only* two kinds of code this walkthrough ever
treats as exempt from capability decomposition (R1). A command dispatcher, a
clock, an input reader, a "business engine" that sequences a few capability
calls — none of those are exemptions; they're capabilities (step 2).

## 5. Assemble every manifest at startup (Phase 8 mechanics, R8's indirections)

Inside the same module that builds `_registry`, register every capability
once, at import time — this is the only place `assemble`/`register` runs:

```python
from pathlib import Path
import yaml

for manifest_path in Path("capabilities").rglob("manifest.yaml"):
    assemble(yaml.safe_load(manifest_path.read_text()), _registry)
```

## 6. Headless verification harness (Phase 7, 2-RULES.md "Verification contract")

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
- Write the cycle report using the template in `3-TEMPLATES.md`.
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

## Worked skeleton 2: composing capabilities, no dispatcher class (R4, R6)

`demo.echo` (step 3) shows the mechanics for *one* capability. It never
shows how a capability composes others, so this closes that gap — the same
gap that, left undocumented, keeps producing a plain orchestration
class/dispatcher instead of capabilities. This is still scaffolding: copy
the shape (contracts, the `dependencies` declaration, calling a dependency
through the request-construction point, the thin entry loop), never the
counter/command domain content.

Three capabilities:

- `command.parse` (generic) — the same shape as `demo.echo`'s `parse`-style
  operations: a verb+args parser over a caller-supplied grammar.
- `counter.adjust` (generic) — given a value, a delta, and bounds, returns
  the clamped new value. A stand-in for any generic state-transition
  capability.
- `session.step` (**specific** — R4) — depends on both of the above. This is
  the interesting one: a responsibility that composes other capabilities is
  itself a capability, with its own contract, not a plain class.

**The two generic contracts**, abbreviated (same full shape as `demo.echo`'s
contract — identity/responsibility/interface/dependencies/discoverability/
versioning/lineage — just the interesting parts shown):

```yaml
# contracts/command.parse.contract.yaml
contract:
  identity: {id: command.parse, name: Command Parse, version: "1.0.0", domain: command, family: command, type: capability}
  interface:
    operations:
      - name: parse
        description: Splits text into verb + args against a caller-supplied grammar.
        input:
          - {name: text, type: string, required: true}
          - {name: grammar, type: object, required: true, description: "verb -> expected arg count"}
        output: {type: object, description: "{ verb, args, valid, error_code }"}
        errors: [{code: INVALID_INPUT, description: text or grammar malformed}]
  dependencies: {capabilities: [], components: [], resources: []}
  # discoverability / versioning / lineage: same shape as demo.echo's contract
```

```yaml
# contracts/counter.adjust.contract.yaml
contract:
  identity: {id: counter.adjust, name: Counter Adjust, version: "1.0.0", domain: counter, family: counter, type: capability}
  interface:
    operations:
      - name: adjust
        description: Returns value + delta, clamped to [min, max].
        input:
          - {name: value, type: integer, required: true}
          - {name: delta, type: integer, required: true}
          - {name: min, type: integer, required: true}
          - {name: max, type: integer, required: true}
        output: {type: object, description: "{ value }"}
        errors: [{code: INVALID_INPUT, description: min > max}]
  dependencies: {capabilities: [], components: [], resources: []}
```

**The specific contract, in full** — note `dependencies.capabilities`
naming the two generic ones (R4: both more generic than `session.step`):

```yaml
# contracts/session.step.contract.yaml
contract:
  identity: {id: session.step, name: Session Step, version: "1.0.0", domain: session, family: session, type: capability}
  responsibility:
    description: >
      Interprets one line of input against the current counter value and
      returns the next value and a message. Composes command.parse and
      counter.adjust — it does not reimplement parsing or clamping itself.
  interface:
    operations:
      - name: run
        description: Advances one interaction.
        input:
          - {name: text, type: string, required: true}
          - {name: count, type: integer, required: true}
        output: {type: object, description: "{ count, message, done }"}
        errors: [{code: UNKNOWN_VERB, description: text did not match the grammar}]
  dependencies:
    capabilities: [command.parse, counter.adjust]
    components: []
    resources: []
  discoverability: {tags: [session], metadata: {}}
  versioning: {compatibility: backward, deprecation_policy: none}
  lineage: {created_by: walkthrough-skeleton, changed_by: walkthrough-skeleton, history: []}
```

Manifests follow the exact shape from step 3 (`capability_id`,
`contract_version`, one `implementations[]` entry each, `executor:
"module.path:execute"`) — omitted here since nothing about their shape
changes. The two generic executors are as plain as their contracts —
neither calls another capability, so neither needs the lazy-import gotcha
below:

```python
# capabilities/command/parse/executor.py
def execute(operation, input, policy):
    text, grammar = input["text"], input["grammar"]
    tokens = text.strip().split()
    if not tokens:
        return {"verb": None, "args": [], "valid": False, "error_code": "EMPTY_TEXT"}
    verb, args = tokens[0], tokens[1:]
    if verb not in grammar or len(args) != grammar[verb]:
        return {"verb": verb, "args": args, "valid": False, "error_code": "UNKNOWN_VERB"}
    return {"verb": verb, "args": args, "valid": True, "error_code": None}
```

```python
# capabilities/counter/adjust/executor.py
def execute(operation, input, policy):
    value, delta = input["value"], input["delta"]
    lo, hi = input["min"], input["max"]
    return {"value": max(lo, min(hi, value + delta))}
```

**The executor that composes its dependencies** — the actual mechanism this
skeleton exists to show,
`capabilities/session/step/executor.py`:

```python
from bridge.bridge import BridgeError

GRAMMAR = {"inc": 0, "dec": 0, "set": 1, "quit": 0}

def execute(operation, input, policy):
    from app.requests import call  # lazy import — see the gotcha below

    if operation != "run":
        raise BridgeError("UNSUPPORTED_OPERATION", "execution", f"no such operation: {operation}")

    text, count = input["text"], input["count"]
    parsed = call("command.parse", "parse", {"text": text, "grammar": GRAMMAR}).output
    if not parsed["valid"]:
        return {"count": count, "message": f"unrecognized: {text}", "done": False}

    verb, args = parsed["verb"], parsed["args"]
    if verb == "quit":
        return {"count": count, "message": "bye", "done": True}
    if verb == "inc":
        delta = 1
    elif verb == "dec":
        delta = -1
    else:  # "set" — grammar guarantees exactly one arg here
        delta = int(args[0]) - count

    adjusted = call("counter.adjust", "adjust", {"value": count, "delta": delta, "min": 0, "max": 100}).output
    new_count = adjusted["value"]
    return {"count": new_count, "message": f"count is now {new_count}", "done": False}
```

**Gotcha: lazy-import the request-construction point.** `app/requests.py`
assembles every manifest — which imports every executor — as part of its
own module body (step 5). If `session.step`'s executor did `from
app.requests import call` at module *top level*, that import would run
while `app.requests` is still mid-initialization (it hasn't finished
defining `call` yet), raising a circular-import error at startup. Importing
`call` *inside* `execute(...)` instead, as shown above, sidesteps this
entirely: by the time `execute` actually runs, `app.requests` has long
since finished loading. Any executor that calls other capabilities needs
this lazy import; one that doesn't (like `demo.echo`'s) doesn't.

**The entry point** — genuinely nothing but a loop that calls one capability
per line, which is the whole point:

```python
from app.requests import call

def main():
    count = 0
    print("Type: inc | dec | set <n> | quit")
    while True:
        text = input("> ")
        response = call("session.step", "run", {"text": text, "count": count})
        count = response.output["count"]
        print(response.output["message"])
        if response.output["done"]:
            break

if __name__ == "__main__":
    main()
```

No dispatcher class. No verb-handler methods. No if/elif ladder of domain
logic outside a contract. The entry point's only job is calling the one
composed capability and printing the result.

**Verifying it**: call `session.step` directly (as in step 6) and assert
its own outer `response.trace` reaches `executed` — you do not need to
"bubble up" the traces of the `command.parse`/`counter.adjust` calls nested
inside its executor; verify those two the same way, directly and
independently, exactly like any other capability operation.
