# ARPAPED Self-Improving Cycle Blueprint — Agent Executable

**If you are about to write code in this repository, read
`blueprint/0-WALKTHROUGH.md` first — in full, before your first line of code.** This
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

1. **`blueprint/0-WALKTHROUGH.md` — about to build something? Start here.** It turns
   the phases and rules below into literal file paths, imports, and commands
   for this repository, including a small runnable starter kit showing the
   contract → manifest → executor → Bridge wiring end to end.
2. `blueprint/1-CYCLE.md` — the 9-phase spine: bootstrap, then Understand → Decompose →
   Discover → Decide → Implement → Integrate → Verify → Publish → Return
   state, with every conformance gate inlined at the phase that enforces it.
3. `blueprint/2-RULES.md` — every definition (glossary), the numbered invariant rules
   (R1–R9), and the Bridge/Registry/verification contracts that make "go
   through the Bridge" enforceable rather than aspirational.

Contract, manifest, and cycle-report shapes are formally defined in
`blueprint/schemas/` (this cycle's own record shapes) and `starterkit/schemas/`
(bridge/contract/manifest shapes), and demonstrated concretely in
`starterkit/` — which **is** the template: copy it directly rather than
building the wiring from scratch (see "A real starter kit" below).

Manifests and contract artifacts are machine-validated against the schemas in
`starterkit/schemas/` (`capability-manifest`, `component-contract`, and friends), and
registration is performed by the generic assembler resolved via
`starterkit/backend/runtime/bridge/MANIFEST.yaml`.

The cycle is hardened so a result cannot silently bypass the ecosystem: **R7**
mandates contract → manifest → code order, **R8** makes the canonical Bridge
the only execution interface (no direct executor/orchestrator calls, including
in the harness), and conformance gates 25–28 (in `blueprint/1-CYCLE.md`) enforce a written
bootstrap resolution record, contract-first creation, Bridge-only execution,
and trace authenticity (traces must be the Bridge's observed `response.trace`).

## A real starter kit

`starterkit/` is a genuinely endorsed, copy-from-here template — not a
mere illustration to read and reimplement from scratch. It's a small,
real, runnable application (a Python backend, a JavaScript frontend, a
worked C# process-kind capability) that already does everything
`blueprint/0-WALKTHROUGH.md` describes: contract → manifest → executor →
Bridge, one request-construction point, an entry point that decides
nothing, a real verification harness, and real DEP recording. Copy it
into a new project and start replacing its capabilities with real ones.

Its one capability, `log.write` (plus the frontend's `client.log`, which
reports to it remotely), is deliberately real domain content, not a
disposable placeholder — logging is something almost every application
actually needs, so unlike an earlier version of this starter kit (a
"hello world" greeting, deleted by every project that copied it), there
is no equivalent blanket warning here to rip this one out. What IS still
illustrative, and worth expecting to replace: the implementation bodies
themselves are intentionally minimal (a line to stdout) — a real
deployment likely wants file output, rotation, structured JSON, or a
real logging library behind the same contract, not this exact executor
code verbatim.
