# Product Manifest Template

Every product in the ARPAPED ecosystem MUST have a manifest that declares its identity, dependencies, and integration points.

## Required fields

```yaml
product:
  identity:
    id: "string"              # unique product identifier
    name: "string"            # human-readable name
    version: "string"         # semantic version
    domain: "string"          # application domain

  dependencies:
    bridge: "string"          # canonical Bridge version requirement
    registry: "string"        # canonical Registry version requirement
    capabilities:             # list of required capability contracts
      - id: "string"
        version: "string"
    components:               # list of required component contracts
      - id: "string"
        version: "string"

  integration:
    entry_point: "string"     # module path for product initialization
    bridge_request_path: "string"  # how the product sends requests to the Bridge

  discoverability:
    tags: ["string"]          # classification tags for Registry
    metadata: {}              # additional discoverability data

  lifecycle:
    state: "string"           # development | staging | production
    support_contact: "string"
```

## Example

```yaml
product:
  identity:
    id: "makcity-core"
    name: "MakCity Core"
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
    components:
      - id: "terrain-renderer"
        version: ">=1.0.0"

  integration:
    entry_point: "makcity.core:initialize"
    bridge_request_path: "canonical"

  discoverability:
    tags: ["urban", "simulation", "3d"]
    metadata:
      engine: "unity"
      platform: ["windows", "linux"]

  lifecycle:
    state: "development"
    support_contact: "team@makcity.example"
```

## Rules

1. The manifest MUST be placed at the product root.
2. The manifest MUST reference canonical Bridge and Registry, never product-local copies.
3. The manifest MUST NOT contain implementation details; it declares WHAT the product needs, not HOW it works.
4. Capabilities and components referenced MUST exist in the ecosystem Registry.
5. Version requirements MUST use semantic versioning constraints.
