# Verification Contract

The self-improving cycle publishes a **verified** state, not a written state.
This document is the mandatory discipline for creating and running the
verification harness that proves a resulting state behaves correctly.

It exists because assembled products routinely shipped with defects that purely
"look right" on paper: the product fails to start after an ecosystem rename, a
declared capability operation crashes on valid data, or advertised user controls
are unreachable. These defects were discovered only by manual intervention —
which means the automated cycle was not actually testing its own output. This
contract closes that gap.

## Mandatory Verify phase

Verification is a phase of the execution cycle
(`02-cycle/agent-execution-protocol.md`, Phase 7 — Verify). A cycle is complete
only after the resulting state passes verification, and the verification record
is part of the resulting state.

## Scope of a verification pass

The harness MUST prove, headlessly (`isatty()` may never be required):

1. **Assembly and startup.** The product resolves the canonical Bridge from the
   ecosystem root and starts without manual steps. A product that cannot be
   started and driven by machine input is not verified — it is broken.
2. **Every declared capability operation.** Each capability in the product
   manifest is invoked over contract-shaped data through the canonical Bridge,
   and the response is contract-shaped. The Bridge trace on every invocation
   must end in `executed`.
3. **Every consumer-visible behavior.** For interactive products, every
   advertised user control is exercised through a scripted command stream and
   its effect on observable state is asserted. An advertised control that has no
   effect (a dead binding) is a defect.
4. **Reactive behavior.** A reactive/automatic loop is run in the SAME session as
   the injected inputs, and both effects are asserted: the automatic advancement
   progressed AND the user's actions took effect. A loop that resumes only after
   user input, or that consumes the terminal so no input can be applied, is a
   failed check.
5. **Invariants.** Failures and successes are decided on observable behavior
   (state, counts, cell contents, pause/speed/reset semantics), never on the
   aesthetic layout of rendered output.

## Deterministic, headless execution

Interactive/console consumers MUST expose a scripted-input path and a
controllable clock so verification never depends on a real terminal:

- a **command stream**: an ordered list of events such as
  `("key", "<key_name>")`, `("tick", None)`, `("wait", <seconds>)`, where
  `key_name` uses the same labels the console path produces (e.g.
  `up`/`down`/`left`/`right`, `space`, `p`, `d`);
- a **controllable clock**: ticking is driven by explicit `tick`/`wait` events
  rather than wall-clock time, so a reactive cadence is reproducible.

The scripted path must share the same handlers as the real console path. If the
scripted path bypasses real logic, the harness verifies nothing.

## Regression discipline

Every defect reported by a previous cycle — whether reported by a human, by a
consumer, or by an earlier verification run — MUST be reproduced as a
failing-check-first test:

1. write the check so that it FAILS against the current state (red);
2. fix the defect;
3. confirm the check PASSES (green);
4. keep the check in the harness forever.

The verification record's `failures` and `regression_for` fields track this
explicitly, so the next cycle can see which defects are now proven fixed.

## Fail-closed rule

Verification failure is not a report to file — it is the cycle's primary result.
The agent:

- fixes the defect (or splits/reuses per the Decide phase);
- re-runs the harness;
- only then proceeds to Publish (Phase 8).

A state that cannot be assembled, started, driven, or that fails any check is
never published.

## Record

Write a machine-readable verification record (`schemas/verification-record.schema.json`)
into the resulting state and reference it in the cycle report
(`05-governance/agent-report-template.md`) and in the product manifest's
discoverability metadata. The next cycle begins by re-running the harness and
must accept no goal until the record is green.