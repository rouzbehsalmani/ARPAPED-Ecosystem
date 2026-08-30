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
ordinary consumer code, per R1. Nothing else gets to skip a contract.

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
   `connector`, or `service`), `responsibility` (`description` required,
   `invariants` optional), `interface.operations[]` (each operation's
   `name`, `description`, and `errors[]` are REQUIRED — `errors` may be an
   empty list but the key must exist; `input`/`output` are optional),
   `dependencies`, `discoverability`, `versioning`, `lineage` (`policy` and
   `runtime` are optional and may be omitted). Validate it before moving on.
2. **Manifest second** — a capability manifest valid against
   `schemas/capability-manifest.schema.json`: top-level
   `capability_id`, `contract_version`, `implementations[]` (each:
   `implementation_id`, `version`, `operations[]`, an `executor` locator
   whose exact notation depends on the language you resolved per
   `bridge/MANIFEST.yaml`). Do this only after the contract validates.
3. **Code third** — the executor: an operation `execute` taking (operation,
   input, policy) and returning output, in whatever shape your resolved
   Bridge's own implementation expects. It never imports the Registry and
   never calls `register`. Write it only after the manifest exists and
   validates.

Writing the executor before its contract and manifest exist is a Gate 26
violation, no matter how small the capability is.

### Worked sample: hello world

The simplest possible complete, **runnable** example: a console "hello
world," where even writing to the console is a capability, not entry-point
plumbing. See `bridge/samples/hello_world/` — a real contract, manifest,
executor, request-construction point, and entry point, built in the exact
order above (its own `README.md` explains how to run it). This is
scaffolding to prove the wiring, not a feature — copy the shape (the file
order, the fields, the request-construction pattern), never the domain
content, into a real capability.

Its executor's behavior: given operation `write` and `input.text`, write
that text to the console and return an empty object. The entry point is
exactly one call: resolve the Bridge per `bridge/MANIFEST.yaml` and call
`console.write`'s `write` operation with `{ text: "Hello, world!" }`. That
call's response trace reaches every stage in order — `validated →
discovered → policy_evaluated → selected → executed` — for a capability
that only exists as a contract + manifest + registration-unaware executor;
nothing calls `execute` directly, and nothing in the entry point prints
anything itself.

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

This module is the only structural exception (R1). The process entry point
that calls it is ordinary consumer code, not a second exemption — its
top-level loop should do little more than call capabilities in sequence
through this module (step 2).

## 5. Assemble every manifest at startup (Phase 8 mechanics, R8's indirections)

As part of building the request-construction point (step 4), register every
capability once, at load time: for every manifest file under `capabilities/`,
assemble it into the registry using the assembler resolved per
`bridge/MANIFEST.yaml`. This is the only place assembly/registration runs.

## 6. Headless verification harness (Phase 7, 2-RULES.md "Verification contract")

Lives outside the application packages, e.g. `tests/verify`. It must:

- Reuse the SAME Bridge the request-construction point builds — never
  assemble a second one.
- For every capability operation, call it (directly, or through the
  request-construction point) and assert the response trace equals
  `validated → discovered → policy_evaluated → selected → executed` — copied
  from the observed response, never hand-written.
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

Fail closed: if any check fails, fix it and re-run before step 7.

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
  real service, that service is a capability (R1) — the entry point only
  calls it.
