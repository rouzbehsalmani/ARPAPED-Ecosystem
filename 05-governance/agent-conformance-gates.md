# Agent Conformance Gates

Pointer. The 24 gates are part of the cycle: each one lives inside the phase it
enforces in `02-cycle/agent-execution-protocol.md`, and the phase → gate map is
at its top.

| Phase | Gates |
|---|---|
| Bootstrap | 1–3 |
| 1 — Understand | 3 |
| 1.5 — Health check | 12 |
| 2 — Decompose | 13, 21 |
| 3 — Discover | 4, 5 |
| 4 — Decide | 6 |
| 5 — Implement | 7, 15, 16 |
| 6 — Integrate | 10, 13, 24 |
| 7 — Verify | 17–24 |
| 8 — Publish | 8, 9, 14 |
| 9 — Return | 11 |

These are Blueprint conformance gates, not a product test suite. A NO on any
gate means the cycle is not complete.