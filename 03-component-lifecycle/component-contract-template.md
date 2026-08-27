# Component Contract Template

Every reusable component in the ARPAPED ecosystem MUST have a contract that defines its interface, inputs, outputs, and lifecycle.

## Required fields

```yaml
contract:
  identity:
    id: "string"              # unique component identifier
    name: "string"            # human-readable name
    version: "string"         # semantic version
    domain: "string"          # application domain
    family: "string"          # component family
    type: "string"            # capability | connector | service

  responsibility:
    description: "string"     # what this component does
    invariants: ["string"]    # properties that never change

  interface:
    operations:
      - name: "string"
        description: "string"
        input:
          - name: "string"
            type: "string"
            required: true
            description: "string"
        output:
          type: "string"
          description: "string"
        errors:
          - code: "string"
            description: "string"

  dependencies:
    capabilities: []          # required capability contracts
    components: []            # required component contracts
    resources: []             # required external resources

  policy:
    requirements: ["string"]  # policy constraints this component requires
    provides: ["string"]      # policy guarantees this component provides

  runtime:
    threading: "string"       # single | multi | thread-safe
    stateful: false           # whether component maintains state
    lifecycle: "string"       # singleton | transient | scoped

  discoverability:
    tags: ["string"]
    metadata: {}

  versioning:
    compatibility: "string"   # backward | forward | strict
    deprecation_policy: "string"

  lineage:
    created_by: "string"      # cycle or agent that created this
    changed_by: "string"      # cycle or agent that last modified
    history: []               # list of significant changes
```

## Example

```yaml
contract:
  identity:
    id: "<capability-a>"
    name: "<Capability A Display Name>"
    version: "1.0.0"
    domain: "<domain>"
    family: "<family>"
    type: "capability"

  responsibility:
    description: "<one generic responsibility>"
    invariants:
      - "<property that never changes>"
      - "<does not modify its inputs>"

  interface:
    operations:
      - name: "<operation>"
        description: "<what the operation does>"
        input:
          - name: "<input_a>"
            type: "<TypeA>"
            required: true
            description: "<first generic input>"
          - name: "<input_b>"
            type: "<TypeB>"
            required: true
            description: "<second generic input>"
        output:
          type: "<ResultType>"
          description: "<generic result>"
        errors:
          - code: "INVALID_INPUT"
            description: "<input did not satisfy the contract>"

  dependencies:
    capabilities: []
    components: []
    resources: []

  policy:
    requirements: []
    provides: ["deterministic-output"]

  runtime:
    threading: "thread-safe"
    stateful: false
    lifecycle: "singleton"

  discoverability:
    tags: ["<tag-a>", "<tag-b>", "<tag-c>"]
    metadata:
      performance: "<complexity>"

  versioning:
    compatibility: "backward"
    deprecation_policy: "6-month-notice"

  lineage:
    created_by: "cycle-001"
    changed_by: "cycle-001"
    history:
      - version: "1.0.0"
        change: "Initial implementation"
        cycle: "cycle-001"
```

Real capability IDs, types, and domains must be resolved from the ecosystem's
authoritative manifests; the placeholders above are structural shape only.

## Rules

1. The contract MUST be registered in the canonical Registry before the component can be discovered.
2. The contract MUST define all public operations with explicit input/output types.
3. The contract MUST NOT expose implementation details; it defines the WHAT, not the HOW.
4. The contract MUST include error definitions for all failure modes.
5. Version changes MUST follow the declared compatibility policy.
6. Lineage MUST be updated whenever the component is modified.
7. Inputs and outputs MUST be generic contract-shaped data (e.g. typed shapes), never the implementing component's internal classes or module names. A consumer must be able to swap the component without changing its contract data (see `04-runtime/capability-reference-discipline.md`).
8. The contract MUST NOT name or depend on the implementing module, package, or class; the component is bound to the contract through a data-driven capability manifest, not through consumer code.
