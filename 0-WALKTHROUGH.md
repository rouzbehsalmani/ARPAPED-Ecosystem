# Build Walkthrough

**Read this file in full before writing any code in this repository.** Every
past attempt that skipped it produced a plain monolith — a single class with
a pile of methods, no contracts, no manifests, no Bridge, no capabilities.
That is not a hypothetical risk; it has happened multiple times. If you read
nothing else here, read this one rule: **default to capability.** Any
distinct need — including things that look like plain infrastructure
(reading input, tracking time, dispatching a command) — gets a contract,
manifest, and executor, wired through the Bridge already implemented at
`bridge/`. The only structural exception is the single request-construction
point (defined below); the entry point itself is ordinary consumer code, per
R1. A class with several methods that directly mutate application state is a
sign you're about to repeat the mistake — stop and decompose it into
capabilities instead.

`1-CYCLE.md` defines the phases and gates. `2-RULES.md` defines the invariants
they enforce. This file turns both into literal actions for **this specific
repository**, in the order you actually do them, before you write a single
line of feature code.

Nothing here names a class, import, or exact call signature belonging to any
one language — the canonical Bridge could be implemented in any language.
Wherever an exact shape matters, this file points at `bridge/MANIFEST.yaml`
(which role lives where) and `bridge/samples/hello_world/` (a real, runnable
sample app) instead of restating it in prose.

## 0. What already exists here — use it, never reinvent it

The canonical Bridge, Registry, Policy engine, Selector, and assembler this
Blueprint tells you to resolve are **already implemented in this repo**,
under `bridge/`. `bridge/MANIFEST.yaml` names exactly where each one lives
and what it does; `schemas/` holds the schemas that define contract,
manifest, trace, and record shapes. Resolve everything from there and read
that implementation's own source for its actual language and call
signatures — this file never restates them.

This **is** the canonical execution boundary that `1-CYCLE.md` Phase 0 tells
you to resolve. Do not write a new Bridge, Registry, Policy, Selector, or
assembler, and do not edit anything under `bridge/` — only resolve and call
it. `contracts/` does not exist yet in this repo; you create it as you add
capabilities. There is no product concept and no per-application copy of the
Bridge: one Bridge, built once, serves every capability you add.

## 1. Bootstrap (1-CYCLE.md Phase 0 — Gates 1, 2, 3, 25)

Before decomposing the goal:

- [ ] Confirm `bridge/MANIFEST.yaml` exists and read it, then read the
      implementation and schemas it points at. This satisfies "resolve the
      canonical Bridge/Registry" (Gates 1, 2) without inventing anything
      (Gate 3).
- [ ] Write the ecosystem-resolution record (Gate 25) — e.g.
      `state/ecosystem-resolution.json`, naming what you resolved:

  ```json
  {
    "bridge": "<resolved per bridge/MANIFEST.yaml: execution_boundary>",
    "registry": "<resolved per bridge/MANIFEST.yaml: registry>",
    "policy": "<resolved per bridge/MANIFEST.yaml: policy>",
    "selector": "<resolved per bridge/MANIFEST.yaml: selector>",
    "contracts_area": "contracts/",
    "root": "<repo root>"
  }
  ```

- [ ] Do not create a second Bridge/Registry anywhere in your code.

## 2. Decompose the goal into capabilities (Phase 1–2, R1)

List the independently meaningful responsibilities the goal requires. Name
each one `<domain>.<operation>` — precise and small-scale (R1) — never a
vague role (`<domain>.manager`) and never one capability that does
everything. A bigger capability may depend on several more-generic ones
(R4); build the generic ones first.

**Default to capability, not local code.** When you need some behavior and
nothing already provides it, create the capability — even when it looks like
plain infrastructure or plumbing: a command dispatcher, a clock/time source,
raw input polling, a step that just sequences a few other capability calls
together. All of those are capability candidates first, local code only as a
last resort. Composing several other capabilities is a reason to give a
responsibility its own contract (a *specific* capability per R4, depending on
the generic ones) — never a reason to leave it as an ad hoc class or module.
The only structural exception in this entire walkthrough is the single
request-construction point (step 4); the entry point that calls it is
ordinary consumer code, per R9. Nothing else gets to skip a contract.

**Run this checklist for every distinct need, including the entry point's
own needs:**

- I need something the ecosystem doesn't have yet — do I import it directly?
  **No.**
- Do I define a contract, manifest, and component for it instead? **Yes.**
- Is this code the entry point / `main` / `run`? [if yes] Does that change
  anything? **No** — should I bypass the Bridge? **No.** Resolve the Bridge
  per `bridge/MANIFEST.yaml` and start from there. Everything passes through
  the Bridge.

## 3. Per capability: contract → manifest → code, in that order (Phase 5, R7)

For every capability from step 2:

1. **Contract first** — `contracts/<domain>.<operation>.contract.yaml`,
   valid against `schemas/component-contract.schema.json`. That schema
   sets `additionalProperties: false` at every level, so only these keys
   exist: top-level `contract:` wrapping REQUIRED `identity` (`id, name,
   version, domain, family, type` — `type` is exactly `capability`,
   `connector`, or `service`; `version` must be a key present in
   `versions`, below), `responsibility` (`description` required,
   `invariants` optional), `versions` (keyed by version string, each entry
   a full peer with its own `operations[]` — each operation's `name`,
   `description`, and `errors[]` are REQUIRED — `errors` may be an empty
   list but the key must exist; `input`/`output` are optional; a version
   that's fully retired moves to `lineage.history` instead — see R2),
   `dependencies`, `discoverability`, `versioning`, `lineage` (`policy` and
   `runtime` are optional and may be omitted). Validate it before moving on.
2. **Manifest second** — a capability manifest valid against
   `schemas/capability-manifest.schema.json`: top-level
   `capability_id`, `contract_version`, `implementations[]` (each:
   `implementation_id`, `version`, `operations[]`, an `executor` locator
   whose exact notation depends on the language you resolved per
   `bridge/MANIFEST.yaml`, and `priority` — an integer with no default;
   higher number means higher precedence). Do this only after the contract
   validates.
3. **Code third** — the executor: an operation `execute` taking (operation,
   input, policy) and returning output, in whatever shape your resolved
   Bridge's own implementation expects. It never imports the Registry and
   never calls `register`. Write it only after the manifest exists and
   validates.

Writing the executor before its contract and manifest exist is a Gate 26
violation, no matter how small the capability is.

**A capability that needs live access to another one** (not just
pre-computed input its caller already resolved) is the one case with a
different manifest shape: set `executor_kind: factory` on that
implementation entry, and point `executor` at a factory — `(dependencies) ->
executor` — instead of the executor itself, resolved from the same
canonical Bridge per `bridge/MANIFEST.yaml`. It may only call what its own
contract declared under `dependencies.capabilities` (R4) — never invent a
different wiring locally, and never reach the Bridge any other way.

A minimal, runnable sample of this exact shape (contract → manifest →
executor → request-construction point → entry point) lives at
`bridge/samples/hello_world/` — its own `README.md` explains how to run it
and what it does. It happens to print to a console purely because that is
the smallest possible interface to demonstrate the wiring with; this
Blueprint never constrains what interface an application presents (console,
web, GUI, or otherwise — see step 6 for how any of them stays verifiable).
It is one sample, not the shape every application must take: copy the
wiring pattern, never its console-specific content, into a real capability.

## 4. The single request-construction point (Phase 6, R6)

In a real application, exactly ONE module owns building requests and calling
the Bridge's handle operation — e.g. `app/requests`. It does three things,
in order, at load time: build a registry; assemble every capability manifest
into it (step 5); construct the Bridge from that registry plus the policy
and selector resolved per `bridge/MANIFEST.yaml`. It then exposes one
operation — call it with a capability id, an operation name, and input — that
builds a request (a fresh id each time, plus a default policy context) and
passes it to the Bridge's handle operation.

Every other module — CLI parsing, a game loop, a web handler, anything —
calls through that one operation. Nothing else constructs a request or calls
the Bridge's handle operation directly (the verification harness in step 6
is the one exception, per R6).

This module is the only structural exception (R6). The process entry point
that calls it is ordinary consumer code, not a second exemption (R9) — its
top-level loop should do little more than call capabilities in sequence
through this module (step 2).

## 5. Assemble every manifest at startup (Phase 8 mechanics, R8's indirections)

As part of building the request-construction point (step 4), register every
capability once, at load time, using the assembler resolved per
`bridge/MANIFEST.yaml`. This is the only place assembly/registration runs.

For a handful of capabilities, walking `capabilities/` directly and
assembling each manifest found is fine. It stops scaling once there are more
than a handful — see the worked sample below, which instead registers from a
generated capability catalog (built once, at Publish time, from the same
`capabilities/` tree) so startup never has to walk and re-parse it; see
2-RULES.md "The Registry contract" for why authoring-time discovery needs
the same catalog.

## 6. Headless verification harness (Phase 7, 2-RULES.md "Verification contract")

Lives outside the application packages, e.g. `tests/verify`. It must:

- Confirm every contract validates against
  `schemas/component-contract.schema.json` and every manifest against
  `schemas/capability-manifest.schema.json` — a prerequisite the harness
  itself checks, not a final afterthought tacked on after the operation
  checks below.
- Reuse the SAME Bridge the request-construction point builds — never
  assemble a second one.
- For every capability operation, call it (directly, or through the
  request-construction point) and assert the response trace equals
  `validated → discovered → policy_evaluated → selected → executed` — copied
  from the observed response, never hand-written.
- Run every capability-operation check under a bounded per-stage timeout
  resolved from the canonical Bridge (`bridge/MANIFEST.yaml`), never an
  unbounded wait. A stage that never progresses is a hard failure (R5) —
  record it with whatever partial trace was actually observed before the
  timeout, never a reason to wait longer or retry silently. This matters
  most for any operation that starts ongoing/background work (a server, a
  long-lived process): its executor must itself verify, synchronously and
  promptly, that the work has actually started before returning — never a
  fabricated or assumed status — and must never block waiting for the
  ongoing work itself to finish.
- Drive every consumer-visible interaction through a scripted command
  stream using the same dispatcher the real interface uses.
- Include at least one case proving an operator decision window: a scripted
  action lands between two automatic ticks and its effect is observable.
- Write `state/verification-record.json`, valid against
  `schemas/verification-record.schema.json`: `verification_id`,
  `state_ref`, `harness`, `checks[]` (unique `check_id` per check; a check
  with `check_type: capability_operation` MUST carry a `trace` array copied
  verbatim from the observed response), `passed`, `failed`, `status`
  (`"verified"` or `"failed"`).

**This is a loop, not a one-shot:**

1. Run the harness.
2. Any check fails? Fix that specific defect (or split/reuse per Phase 4) —
   then go back to step 1.
3. Only once every check passes on a fresh run does step 7 begin. An
   unverified state is never published (R5, Gate 20).

## 7. Publish and return state (Phase 8–9)

- Confirm the registry discovers a candidate for every capability you built
  (capability id, contract version, operation).
- Write the cycle report, valid against `schemas/agent-cycle-report.schema.json`.
- The resulting state — `contracts/`, `capabilities/`, `app/`, `tests/`,
  `state/verification-record.json`, and the report — is everything the next
  cycle needs. No private memory of this session should be required to
  continue the work (Gate 11).

## Failure patterns this file exists to prevent

- Writing the feature straight into one class/file, with a CLI dispatcher
  calling its methods directly — no contract, no manifest, no Bridge
  anywhere. (This is what happened the first time this Blueprint was
  handed to an agent without this file.)
- Treating "based on this Blueprint" as a naming or flavor theme rather than
  an operating procedure.
- Skipping the verification harness because the application "runs fine
  manually."
- Building a real service (a web server, a scheduler) directly inside the
  entry point because "it's just infrastructure." If the entry point needs a
  real service, that service is a capability (R9) — the entry point only
  calls it.
