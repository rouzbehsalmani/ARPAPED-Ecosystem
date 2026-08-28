# Verification Contract

The self-improving cycle publishes a **verified** state, not a written state.
This contract is the mandatory checklist for the Verify phase
(`02-cycle/agent-execution-protocol.md`, Phase 7). The harness lives alongside
the product and is part of the resulting state.

It exists because assembled products routinely shipped with defects that purely
"look right" on paper: fail to start after a rename, crash on valid contract
data, advertise unreachable controls, or fill themselves up before the operator
can act. Verification closes that gap.

## A pass proves

The harness runs the product **headlessly** (never requiring `isatty()`) and
must answer YES to all of the following:

1. **Assembly and startup.** The product resolves the canonical Bridge from the
   ecosystem root and starts/drives without manual steps.
2. **Capability decomposition and neutrality.** Enforced rules: **R2**, **R3**,
   **R6** (see `00-core/capability-rules.md`). The harness evaluates them
   directly and MUST fail when any is violated.
3. **Every declared capability operation** is invoked over contract-shaped data
   through the SAME canonical Bridge the product resolves (R9), the response is
   contract-shaped, and the FULL ordered trace is asserted from the Bridge's own
   `response.trace`: `validated → discovered → policy_evaluated → selected →
   executed` (missing stage, wrong order, or no `executed` = fail). The trace is
   observed, never constructed by the harness (Gate 28).
4. **Every consumer-visible behavior** is exercised through a scripted command
   stream (`("key", name)`, `("tick", None)`, `("wait", n)` — same handler the
   real console uses) and its observable effect asserted. A dead binding is a
   defect.
5. **Operator decision window.** A scripted operator action can interleave
   between observable automatic transitions, and unstoppered auto-advance can
   never exhaust the product's own action space (a product whose automatic
   transitions fully saturate every reachable state before the operator can act
   fails). Auto-advance is rate-bounded and always leaves a permanent,
   operator-reachable remainder.
6. **Reactive same session.** The automatic loop AND injected input run in the
   same session; assert both state advanced AND the user's actions took effect.
7. **Invariants, not formatting.** Results are decided on observable behavior
   (state, counts, reached states, pause/speed/reset semantics), never on
   rendered layout.
8. **Record.** A machine-readable verification record
   (`schemas/verification-record.schema.json`) is written into the resulting
   state, referenceable from the cycle report, and green. Every capability
   operation's OBSERVED trace is persisted (`check.trace` — the Bridge's own
   `response.trace`, not invented); `check_id`s are unique.

## Determinism, not a wall clock

Interactive/console products MUST expose a scripted-input path and a
controllable clock: ticking is driven by explicit `tick`/`wait` events, never
by wall-clock time, and the scripted path shares the handlers with the real
console path. If the scripted path bypasses real logic, the harness verifies
nothing.

## Request-path discipline

Enforced rules: **R7** and **R9** in `00-core/capability-rules.md` — canonical
path `consumer code → Bridge → registry → policy → selector → executor`, one
single request-construction point in the product, and the verification harness
as the sole exception to the *construction* rule (it builds `BridgeRequest`s
directly — that is exactly how it inspects the trace), but it MUST still call
the same resolved canonical `bridge.handle(...)` and record only the Bridge's
observed `response.trace`. See also
`04-runtime/capability-reference-discipline.md`.

## Trace authenticity

A recorded trace is valid only if it equals the Bridge's own
`response.trace` for that request — copied from the observed response, in
order. A "verification" that:

- does not execute the capability through the canonical Bridge (calls a
  component executor or an orchestrator directly), or
- constructs its own trace (sets the stages itself without observing them from
  the Bridge),

is NOT verification (R9, Gate 27/28). Its record — however green — does not
prove the result, the cycle is not complete, and the state is not published.

## Regression discipline

Every defect reported by a previous cycle — by a human, a consumer, or an
earlier verification run — MUST be reproduced as a failing-check-first test:
write it failing (red), fix the defect, confirm it passes (green), keep it
forever. The record's `failures` and `regression_for` fields track this. At
minimum, one named check per observed defect class: dead-on-arrival assembly /
startup; capability op crash on valid data; unreachable controls; reactive loop
blocking or pre-empting input; automation exhausting the state (no decision
window); collapsed capability decomposition; bypassed request path; trace not
evaluated; forged or bypassed Bridge trace (trace not equal to the observed
`response.trace`, or capability executed without the Bridge) — this is now a
hard Gate 27/28 fail; component written before its contract artifact and
capability manifest (R8, Gate 26).

## Fail closed

Verification failure is the cycle's primary result. The agent fixes the defect
(or splits/reuses per the Decide phase), re-runs the harness, and only then
proceeds to Publish (Phase 8). A state that cannot be assembled, started,
driven, decomposed correctly, or that fails any check is never published.

## Record

The record lives in the resulting state; the next cycle begins by re-running
the harness and accepts no goal until the record is green. A record that omits
traces, omits the observed `check.trace` on a capability-operation check,
reuses check IDs, or was not regenerated by a green run is not a valid
verified state.