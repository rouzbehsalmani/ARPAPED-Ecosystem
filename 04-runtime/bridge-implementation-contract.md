# Canonical Bridge Implementation Contract

The self-improving agent must resolve and use the ecosystem's existing canonical Bridge.

The Blueprint does not prescribe a replacement implementation.

The agent must verify from authoritative ecosystem artifacts:

- the Bridge identity;
- its canonical request path;
- validation stage;
- discovery stage;
- policy stage;
- selection stage;
- execution handoff;
- tracing/receipt requirements where defined by the ecosystem.

When adding a product, the product becomes a consumer of this path.

The product must not reproduce the Bridge pipeline locally.

## Bridge Trace

The Bridge MUST return a `trace` field in its response. The trace is an ordered tuple of stage identifiers recording which stages the request completed before returning.

### Trace stages

| Stage | Meaning |
|-------|---------|
| `validated` | Request passed structural validation (required fields present, correct types). |
| `discovered` | Registry returned one or more compatible implementations. |
| `policy_evaluated` | Policy engine evaluated all candidates against the policy context. |
| `selected` | Selector chose one or more candidates for execution. |
| `executed` | Selected implementation completed successfully. |

### Trace rules

- Stages appear in the order listed above.
- On success, the trace contains all five stages.
- On failure, the trace contains only the stages reached before the error.
- The trace MUST NOT be empty, even on failure (at minimum `validated`).
- Consumers MAY use the trace for debugging, auditing, and observability.
- The trace MUST NOT be used as a control-flow mechanism; it is informational only.
