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
    id: "spatial-collision"
    name: "Spatial Collision Detection"
    version: "1.0.0"
    domain: "geometry"
    family: "spatial"
    type: "capability"

  responsibility:
    description: "Detects collision between geometric shapes in 2D/3D space"
    invariants:
      - "Collision result is deterministic for same inputs"
      - "Does not modify input shapes"

  interface:
    operations:
      - name: "detect_collision"
        description: "Check if two shapes collide"
        input:
          - name: "shape_a"
            type: "Shape"
            required: true
            description: "First geometric shape"
          - name: "shape_b"
            type: "Shape"
            required: true
            description: "Second geometric shape"
        output:
          type: "CollisionResult"
          description: "Collision detection result with contact points"
        errors:
          - code: "INVALID_SHAPE"
            description: "One or both shapes are invalid or degenerate"

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
    tags: ["spatial", "collision", "geometry", "physics"]
    metadata:
      performance: "O(n)"
      precision: "floating-point"

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

## Rules

1. The contract MUST be registered in the canonical Registry before the component can be discovered.
2. The contract MUST define all public operations with explicit input/output types.
3. The contract MUST NOT expose implementation details; it defines the WHAT, not the HOW.
4. The contract MUST include error definitions for all failure modes.
5. Version changes MUST follow the declared compatibility policy.
6. Lineage MUST be updated whenever the component is modified.
