# ARPAPED Self-Improving Cycle Blueprint — Agent Executable

**If you are about to write code in this repository, read
`0-WALKTHROUGH.md` first — in full, before your first line of code.** This
is not a suggestion: every past attempt that skipped it produced a plain
monolith script with no contracts, no manifests, no Bridge, and no
capabilities — the exact failure this Blueprint exists to prevent. That has
already happened more than once on this exact repository.

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

1. **`0-WALKTHROUGH.md` — about to build something? Start here.** It turns
   the phases and rules below into literal file paths, imports, and commands
   for this repository, including a small runnable sample app showing the
   contract → manifest → executor → Bridge wiring end to end.
2. `1-CYCLE.md` — the 9-phase spine: bootstrap, then Understand → Decompose →
   Discover → Decide → Implement → Integrate → Verify → Publish → Return
   state, with every conformance gate inlined at the phase that enforces it.
3. `2-RULES.md` — every definition (glossary), the numbered invariant rules
   (R1–R9), and the Bridge/Registry/verification contracts that make "go
   through the Bridge" enforceable rather than aspirational.

Contract, manifest, and cycle-report shapes are formally defined in
`schemas/` and demonstrated concretely in `bridge/samples/hello_world/` —
there is no separate template document.

Manifests and contract artifacts are machine-validated against the schemas in
`schemas/` (`capability-manifest`, `component-contract`, and friends), and
registration is performed by the generic assembler in `bridge/assembler.py`.

The cycle is hardened so a result cannot silently bypass the ecosystem: **R7**
mandates contract → manifest → code order, **R8** makes the canonical Bridge
the only execution interface (no direct executor/orchestrator calls, including
in the harness), and conformance gates 25–28 (in `1-CYCLE.md`) enforce a written
bootstrap resolution record, contract-first creation, Bridge-only execution,
and trace authenticity (traces must be the Bridge's observed `response.trace`).

## This is not a worked product

No concrete application is embedded here, and no concrete evaluation
scenario is embedded here — an embedded product would become a second
source of truth and invite literal copying. `0-WALKTHROUGH.md` does contain
small, deliberately trivial wiring skeletons (a single toy capability, and a
handful composed together) — copy their *shape* (contracts, manifests, the
request-construction pattern), never their toy domain content. The
templates and contract formats are the shape; the Blueprint defines the
reusable operating system for the self-improving cycle.
