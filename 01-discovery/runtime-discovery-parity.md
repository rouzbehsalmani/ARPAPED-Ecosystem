# Build-Time / Runtime Discovery Parity

The agent's discovery result must be representable through the same Registry model used by runtime resolution.

A reusable component is not fully integrated merely because an agent can import or locate its source code.

For an accepted component:

```text
source implementation
      +
canonical contract
      +
discoverability metadata
      +
Registry/index entry
      +
runtime-resolvable implementation
```

must form one coherent identity.

The Bridge must consume the canonical Registry resolution path rather than a product-specific shortcut.
