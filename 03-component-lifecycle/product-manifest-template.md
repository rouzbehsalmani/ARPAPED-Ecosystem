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

  roles:                        # logical role -> capability_id mapping
    - <role>: "<capability_id>" # consumer code references ONLY roles

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

The example uses abstract placeholders; real capability IDs must be resolved
from the ecosystem's authoritative manifests, never invented or copied here.

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
    capabilities:
      - id: "<capability-a>"
        version: ">=1.0.0"
      - id: "<capability-b>"
        version: ">=1.0.0"

  roles:                        # logical role -> capability_id (consumer speaks in roles)
    - <role_a>: <capability-a>
    - <role_b>: <capability-b>

  integration:
    entry_point: "<product_pkg>:initialize"
    bridge_request_path: "canonical"

  discoverability:
    tags: ["<tag-a>", "<tag-b>"]
    metadata:
      platform: ["<platform-a>", "<platform-b>"]

  lifecycle:
    state: "development"
    support_contact: "<contact>"

## Rules

1. The manifest MUST be placed at the top-level directory that holds the product's own source. That directory is a placeholder (`<top_level_dir>`); no fixed directory name is mandated.
2. The manifest MUST reference canonical Bridge and Registry, never product-local copies.
3. The manifest MUST NOT contain implementation details; it declares WHAT the product needs, not HOW it works.
4. Capabilities referenced MUST exist in the ecosystem Registry (as contracts).
   The product manifest never references concrete components; implementation
   selection belongs to the Registry/selector.
5. Version requirements MUST use semantic versioning constraints.
6. Consumer code references `roles` per **R7**/**R3** (roles resolve to
   capability IDs through this manifest; never concrete modules/classes).
7. The manifest references capability contract ids ONLY per **R3**/**R4** (see
   `00-core/capability-rules.md`); capability manifests live in the generic
   capability area and are never hosted inside this product manifest.
8. The product package is a closed boundary per **R10** (Gates 29–31): it
   hosts consumer logic + this manifest + the integration entry point only. It
   contains no ecosystem-assembly/registration code (no `assemble`, no Registry
   import, no hardcoded capability manifest/contract paths — Gate 29) and no
   harness/test scaffolding (Gate 30). Outside tooling (Publish, Verify) reaches
   the product only through this manifest and its entry point, never through
   product internals (Gate 31).
