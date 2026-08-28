# ARPAPED Self-Improving Cycle Blueprint — Agent Executable

The operational Blueprint for the ARPAPED self-improving cycle.

**The model in one line:** every capability execution goes through one
canonical Bridge over contract-shaped data, and the cycle always verifies the
result headlessly before publishing it. The Bridge is the only execution
interface for any capability operation (R8), and every component is built
contract → manifest → code (R7).

## Important

This package does **not** copy or replace the ecosystem's Bridge, Registry, or
other canonical implementations. It gives an agent an explicit bootstrap and
resolution protocol for finding and using those implementations from the
authoritative ecosystem root.

## Start here

1. `CYCLE.md` — the 9-phase spine: bootstrap, then Understand → Decompose →
   Discover → Decide → Implement → Integrate → Verify → Publish → Return
   state, with every conformance gate inlined at the phase that enforces it.
2. `RULES.md` — every definition (glossary), the numbered invariant rules
   (R1–R8), and the Bridge/Registry/verification contracts that make "go
   through the Bridge" enforceable rather than aspirational.
3. `TEMPLATES.md` — the component contract template and the cycle report
   template.

Manifests and contract artifacts are machine-validated against the schemas in
`schemas/` (`capability-manifest`, `component-contract`, and friends), and
registration is performed by the generic assembler in `bridge/assembler.py`.

The cycle is hardened so a result cannot silently bypass the ecosystem: **R7**
mandates contract → manifest → code order, **R8** makes the canonical Bridge
the only execution interface (no direct executor/orchestrator calls, including
in the harness), and conformance gates 25–28 (in `CYCLE.md`) enforce a written
bootstrap resolution record, contract-first creation, Bridge-only execution,
and trace authenticity (traces must be the Bridge's observed `response.trace`).

## This is not a worked example

No concrete implementation is embedded here. No concrete evaluation scenario
is embedded here. No worked example exists here, by design — an example
becomes a second source of truth and invites literal copying; the templates
and contract formats are the shape. The Blueprint defines the reusable
operating system for the self-improving cycle.
