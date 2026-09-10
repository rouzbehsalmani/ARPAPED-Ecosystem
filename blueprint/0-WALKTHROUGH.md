# Build Walkthrough

**Read this file in full before writing any code in this repository.** Every
past attempt that skipped it produced a plain monolith — a single class with
a pile of methods, no contracts, no manifests, no Bridge, no capabilities.
That is not a hypothetical risk; it has happened multiple times. If you read
nothing else here, read this one rule: **default to capability.** Any
distinct need — including things that look like plain infrastructure
(reading input, tracking time, dispatching a command) — gets a contract,
manifest, and executor, wired through the Bridge already implemented at
`sample/hello_world/backend/runtime/bridge/`. The only structural exception is the single request-construction
point (defined below); the entry point itself is ordinary consumer code, per
R1. A class with several methods that directly mutate application state is a
sign you're about to repeat the mistake — stop and decompose it into
capabilities instead.

`1-CYCLE.md` defines the phases and gates. `2-RULES.md` defines the invariants
they enforce. This file turns both into literal actions for **this specific
repository**, in the order you actually do them, before you write a single
line of feature code.

Nothing here names a class, import, or exact call signature belonging to any
one language. This applies equally to the canonical Bridge (could be
implemented in any language) and to `blueprint/dep/`'s own tooling
(checkpoint, episode_store, process_supervisor, dataset_builder) — its
current reference implementation happens to be Python, but
`blueprint/dep/MANIFEST.yaml` declares itself just as language-agnostic as
the Bridge's own manifest, and nothing in this file should be read as
requiring Python specifically; if DEP is ever reimplemented in a
different language, only that manifest changes. Wherever an exact shape
matters, this file points at `sample/hello_world/backend/runtime/bridge/MANIFEST.yaml`
(which Bridge role lives where), `blueprint/dep/MANIFEST.yaml` (which DEP
role lives where), and `sample/hello_world/` (a real, runnable sample
app) instead of restating any of it in prose.

## 0. What already exists here — use it, never reinvent it

A REFERENCE canonical Bridge, Registry, Policy engine, Selector, and
assembler already exist in this repo, under
`sample/hello_world/backend/runtime/bridge/` (`sample/hello_world/backend/runtime/bridge/MANIFEST.yaml`
names exactly where each one lives and what it does); `sample/schemas/`
holds the schemas that define contract, manifest, trace, and catalog
shapes (this cycle's own record shapes -- cycle input/report,
verification record, checkpoint -- live separately in
`blueprint/schemas/`, alongside this file).

**"Ecosystem" is scoped per APPLICATION, never per repo.** This repo is
not one application; it's a home for however many independent worked
samples/applications end up here (`sample/hello_world/`, and others
alongside it). Two genuinely different situations, never conflated:

- **Adding a capability to an EXISTING application** (e.g. hello_world
  itself): that application's own ecosystem root already exists.
  Resolve ITS ALREADY-ESTABLISHED Bridge from its own MANIFEST.yaml and
  read that implementation's own source for its actual language and
  call signatures — this file never restates them. Do not write a new
  Bridge, Registry, Policy, Selector, or assembler for it, and do not
  edit anything under its own `bridge/` — only resolve and call it.
  `contracts/` already exists for it; you add to it as you add
  capabilities.
- **Building a genuinely NEW, independent application** (a new sample,
  a new product -- anything that does not already have an ecosystem
  root in this repo): this is a DIFFERENT ecosystem. It gets its OWN
  Bridge, Registry, Policy, Selector, and assembler, under THAT
  application's own tree -- copied or ported from the reference
  implementation above (same architecture; proven portable, see
  `2-RULES.md`'s Bridge glossary) -- never a
  cross-application import of another application's module, and never
  edited into the reference implementation's own tree either.
  `contracts/` does not exist yet for a brand-new application; you
  create it, under THAT application's own root, as you add
  capabilities. Observed for real, the failure this causes when
  skipped: a second, unrelated application imported
  `sample.hello_world.backend.runtime.bridge` directly instead of
  resolving its own -- the new application could not run, or even be
  copied into a real deployment, without the first, unrelated
  application's tree also being present. Two independent applications
  sharing one Bridge module is not reuse; it is an undeclared
  dependency between two things that are supposed to be independent
  worked examples, each self-contained enough to copy on its own.

Whichever case applies, the resolved Bridge (existing or newly
established) **is** the canonical execution boundary that `1-CYCLE.md`
Phase 0 tells you to resolve for that application.

## 1. Bootstrap (1-CYCLE.md Phase 0 — Gates 1, 2, 3, 25, 32, 33, 34, 35)

Before decomposing the goal:

- [ ] **First, decide which of section 0's two cases this goal is** (Gate
      35): does the goal continue an application that already has an
      ecosystem root in this repo (e.g. `sample/hello_world/`), or does
      it need a NEW, independent one? Get this wrong and everything below
      resolves against the wrong application's Bridge.
- [ ] **Existing application:** confirm that application's own
      `<its root>/.../bridge/MANIFEST.yaml` exists and read it, then read
      the implementation and schemas it points at. This satisfies
      "resolve the canonical Bridge/Registry" (Gates 1, 2) without
      inventing anything (Gate 3).
- [ ] **New, independent application:** establish its own root under
      `sample/` (never reusing or nesting inside an existing
      application's root), then give it its own Bridge, Registry,
      Policy, Selector, and assembler -- copied or ported from
      `sample/hello_world/backend/runtime/bridge/`'s reference
      implementation into THIS application's own tree, with its own
      MANIFEST.yaml -- before resolving anything else. Never import the
      reference implementation's module directly from the new
      application's code (see section 0's observed-failure example).
- [ ] Write the ecosystem-resolution record (Gate 25) — e.g.
      `<this application's root>/state/ecosystem-resolution.json`,
      naming what you resolved:

  ```json
  {
    "bridge": "<resolved per THIS APPLICATION's OWN bridge MANIFEST.yaml: execution_boundary>",
    "registry": "<resolved per THIS APPLICATION's OWN bridge MANIFEST.yaml: registry>",
    "policy": "<resolved per THIS APPLICATION's OWN bridge MANIFEST.yaml: policy>",
    "selector": "<resolved per THIS APPLICATION's OWN bridge MANIFEST.yaml: selector>",
    "contracts_area": "<this application's root>/contracts/",
    "root": "<this application's own root, never the repo root>"
  }
  ```

- [ ] Do not create a second Bridge/Registry anywhere in your code, and
      do not resolve or import another application's Bridge/Registry as
      if it were this application's own.

**Before accepting the goal as new, check for a resumable checkpoint (Gate
32).** An agent can stop mid-cycle for reasons that have nothing to do with
the work (tokens ran out, network dropped, the process crashed) — the fix
isn't a fresh agent reconstructing progress by guesswork, it's checking
first:

Load the checkpoint at your chosen `checkpoint_path` (e.g.
`state/cycle-checkpoint.json`) through checkpoint's own load operation
(`blueprint/dep/MANIFEST.yaml: checkpoint` — its exact call signature and
language are that file's concern, not this one's, same posture as the
Bridge above):

- **If one exists and its `status` is `in_progress`**: resume CHEAPLY
  (Gate 33) — read its `ecosystem_resolution_ref` directly instead of
  re-discovering the Bridge/Registry, and open each responsibility's own
  `artifacts` (contract/manifest/executor paths) directly instead of
  searching the project for them. Adopt its `goal`/`starting_state`
  unchanged, skip any responsibility already at `integrated`, and
  continue from its `current_phase`/`next_action` — do not re-decide it
  and do not re-verify it by scanning. Only fall back to normal Phase 1/3
  discovery for what the checkpoint doesn't cover. Resume cost tracks
  THIS checkpoint's own responsibility count, never the project's total
  capability count — a project with hundreds of capabilities must resume
  exactly as cheaply as one with a handful.
- **Otherwise**: nothing to resume (or the operator confirmed discarding
  it — clear it first, via checkpoint's own clear operation). Proceed
  with the new goal, then start saving a checkpoint from step 2 onward.

**If the checkpoint looks stale (Gate 34), reconcile — don't fall back to
reading the whole project.** Observed for real: a checkpoint frozen at
`current_phase: "0-bootstrap"`, every responsibility still `planned`,
while all 8 capabilities' contracts/manifests/executors already existed —
the agent had done the work but never called `save_checkpoint` again
after Phase 0. The wrong recovery is "let me read the existing code" —
that reintroduces the full-project cost checkpoints exist to remove. The
bounded recovery uses the same index Phase 3 discovery already reads:

Reconcile it against `capability-catalog.jsonl` (already built, one line
per capability) via checkpoint's own catalog-reconciliation operation,
then save the repaired checkpoint back immediately, before doing
anything else:

This fills in each responsibility's `artifacts` and advances `status` to
at least `code_written` wherever the catalog proves it — O(this cycle's
own capability count), never O(project size) — but never claims
`integrated` from catalog evidence alone (confirm that with a real,
still-cheap per-responsibility Bridge check) and never regresses a status
already further along. Re-saving immediately means this exact repair is
never paid for twice.

**No catalog exists yet before Phase 8 first builds one.** Also observed
for real, mid-Phase-5: a checkpoint frozen at Phase 0 while 7 contracts
and 5 of 7 executors already existed — too early for a
`capability-catalog.jsonl` to reconcile against. Reconcile against the
filesystem convention instead, via checkpoint's own
filesystem-reconciliation operation, then save the repaired checkpoint
back the same way.

A bounded handful of file-existence checks per responsibility against the
paths R1's own naming convention predicts (`contracts/<id>.contract.yaml`,
`capabilities/<domain>/<rest>/{manifest.yaml or manifest.json}`) — a
manifest is tried as either extension since which one applies depends on
the runtime's own language (e.g. Node has no built-in YAML), never
assumed to be Python/YAML specifically. Once a manifest is found, its own
declared `executor:` field is resolved against whatever filesystem roots
the caller supplies — never guessed as a fixed filename/extension either,
since that locator's resolution rule is itself language/executor_kind-
specific (a Python `module:attr` string and a plain relative JS/binary
path resolve completely differently). Still bounded by this checkpoint's
own responsibility count, no file contents read beyond a found manifest
itself. It also catches what a raw status-bump would hide: a file sitting
where a manifest would name it, before any manifest exists there at all,
is an R7 order violation (Gate 26) — recorded as a `blocker`, never
silently advanced past `manifest_written` as if the correct order had
been followed.

Checkpoint's own save operation (`blueprint/dep/MANIFEST.yaml: checkpoint`)
is called again — not once — as each responsibility's status changes through steps
2–4 below (`planned` → `decided`) and step 3 (`contract_written` →
`manifest_written` → `code_written` → `integrated`), so the checkpoint
always reflects what's actually on disk, not just what was true when the
cycle started (`blueprint/dep/MANIFEST.yaml`). A status change alone is not enough:
each Phase 5 update also records the file just written into that
responsibility's `artifacts.contract` / `.manifest` / `.executor`, and
Phase 0 records `ecosystem_resolution_ref` once the resolution record
exists — a checkpoint that only carries labels like "code_written" still
forces a resuming agent to search for the file to trust the label, which
is the exact cost this mechanism exists to remove.

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
  per `sample/hello_world/backend/runtime/bridge/MANIFEST.yaml` and start from there. Everything passes through
  the Bridge.

## 3. Per capability: contract → manifest → code, in that order (Phase 5, R7)

For every capability from step 2:

1. **Contract first** — `contracts/<domain>.<operation>.contract.yaml`,
   valid against `sample/schemas/component-contract.schema.json`. That schema
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
   `sample/schemas/capability-manifest.schema.json`: top-level
   `capability_id`, `contract_version`, `implementations[]` (each:
   `implementation_id`, `version`, `operations[]`, an `executor` locator
   whose exact notation depends on the language you resolved per
   `sample/hello_world/backend/runtime/bridge/MANIFEST.yaml`, and `priority` — an integer with no default;
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
canonical Bridge per `sample/hello_world/backend/runtime/bridge/MANIFEST.yaml`. It may only call what its own
contract declared under `dependencies.capabilities` (R4) — never invent a
different wiring locally, and never reach the Bridge any other way.

A minimal, runnable sample of this exact shape (contract → manifest →
executor → request-construction point → entry point) lives at
`sample/hello_world/` — its own `README.md` explains how to run it and
what it does; this file does not restate that content, and never will,
so this file never goes stale just because the sample's own shape
changes. This Blueprint never constrains what interface an application
presents (console, web, GUI, or otherwise — see step 6 for how any of
them stays verifiable). It is one sample, not the shape every
application must take: copy the wiring pattern, never its own domain
content, into a real capability.

## 4. The single request-construction point (Phase 6, R6)

In a real application, exactly ONE module owns building requests and calling
the Bridge's handle operation — e.g. `app/requests`. It does three things,
in order, at load time: build a registry; assemble every capability manifest
into it (step 5); construct the Bridge from that registry plus the policy
and selector resolved per `sample/hello_world/backend/runtime/bridge/MANIFEST.yaml`. It then exposes one
operation — call it with a capability id, an operation name, and input — that
builds a request (a fresh id each time, plus a default policy context) and
passes it to the Bridge's handle operation.

Every other module — CLI parsing, a game loop, a web handler, anything —
calls through that one operation. Nothing else constructs a request or calls
the Bridge's handle operation directly (the verification harness in step 6
is the one exception, per R6).

This module may also hold its own small declared-dependencies list, each
entry named by whatever this module chooses to call it, and resolve
through that list by name — so callers get a capability+operation handle
without restating a version constraint (or which specific implementation)
at every call site; only genuinely stated once, in that list, upgrading it
is a single edit instead of a hunt across every call site. Unlike a
capability contract's own `dependencies.capabilities`, which is keyed by
capability id, this list may be keyed by name instead, so the same
capability can be declared more than once, pinned differently for
different purposes — useful here in a way it rarely is for a single
capability's own dependency on another. Every declared entry still states
its own version explicitly; there is no default there either, and
resolving a name the list doesn't contain still fails loudly (2-RULES.md
"No silent defaults on what resolution depends on").

This module is the only structural exception (R6). The process entry point
that calls it is ordinary consumer code, not a second exemption (R9) — its
top-level loop should do little more than call capabilities in sequence
through this module (step 2).

An implementation's executor may also run out-of-process instead of being
imported — for a capability implemented in a language other than this
Bridge's own. Whatever launches it is still bound by the same duty as any
other launched service (R5, gate 6): verify, synchronously and promptly,
that it actually started before treating it as available, never assume.

**R6 does not stop at the backend — every entry point is its own runtime,
and every runtime needs its own Bridge.** "Every other module... calls
through that one operation" above is about code sharing THIS Bridge's own
runtime — a web handler included, since it still runs in the backend's own
runtime and language. A goal's consumer surface is rarely just one runtime: a browser
tab, a mobile app, a desktop client, a CLI shipped separately, another
service calling in — each of these is a DIFFERENT runtime from the
backend's, and the kind of frontend it is doesn't change the rule: the
same discipline applies there too, never a weaker version of it just
because it's "only the frontend" or "only a browser." One Bridge for the
backend and one for each other entry point that needs one — same
architecture, same enforcement, every time. Two legitimate shapes, for
whichever entry point you're building:

- **Thin client** — the entry point issues nothing but requests to the
  backend's own single request-construction point (via whatever the
  `web.serve`/`web.server`-style capability exposes as its API), and holds
  no simulation/business state of its own. Every user action becomes a
  network call; the entry point renders whatever the backend's response
  says.
- **A Bridge of its own** — when a round trip per interaction is the wrong
  tradeoff (fast local feedback, offline use, a native mobile/desktop
  client), that entry point resolves its OWN canonical Bridge: a faithful
  port of the same architecture (Registry, Policy, Selector, executor,
  full trace) running in whatever language/runtime that entry point is
  built in — proven portable already in this Blueprint's own history (the
  reference Bridge has been ported to other backend languages with zero
  capability edits; a browser/mobile/desktop-side port is the same
  exercise, one runtime earlier). Its own capabilities that need server
  authority (persistence, multiplayer state, anything requiring a trusted
  resource) declare that need as an ordinary `dependencies.capabilities`
  entry (R4) whose executor reaches across to the backend's single
  request-construction point over the network — never an undeclared
  network call scattered through UI code outside any Bridge-resolved
  capability.

**What neither shape permits:** an entry point that keeps its own copy of
game/business state and advances it directly in a click/tap/input handler,
never resolving that advance through any Bridge — the exact anti-pattern a
real build produced: a fully working-looking browser game with its own
local `state` object and turn logic reimplemented entirely client-side,
sitting next to a schema-valid contract/manifest/executor/catalog that the
game never once called. Every
mechanical check the Blueprint has (schema validation, catalog structure)
passed; the product was still non-compliant, because R6/R9 bind every
runtime the user actually interacts with, not just whichever one happens
to be easiest to wire a Bridge into. Phase 0 resolves a canonical Bridge
for each runtime the goal's consumer surface needs (Gate 25) — the
backend's, and one for each other entry point, whatever kind it is; Phase
7's harness must exercise whichever Bridge each shipped entry point
actually uses, not just the backend capability in isolation (Gate 19).

## 5. Assemble every manifest at startup (Phase 8 mechanics, R8's indirections)

As part of building the request-construction point (step 4), register every
capability once, at load time, using the assembler resolved per
`sample/hello_world/backend/runtime/bridge/MANIFEST.yaml`. This is the only place assembly/registration runs.

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
  `sample/schemas/component-contract.schema.json` and every manifest against
  `sample/schemas/capability-manifest.schema.json` — a prerequisite the harness
  itself checks, not a final afterthought tacked on after the operation
  checks below.
- Reuse the SAME Bridge the request-construction point builds — never
  assemble a second one.
- For every capability operation, call it (directly, or through the
  request-construction point) and assert the response trace equals
  `validated → discovered → policy_evaluated → selected → executed` — copied
  from the observed response, never hand-written.
- Run every capability-operation check under a bounded per-stage timeout
  resolved from the canonical Bridge (`sample/hello_world/backend/runtime/bridge/MANIFEST.yaml`), never an
  unbounded wait. A stage that never progresses is a hard failure (R5) —
  record it with whatever partial trace was actually observed before the
  timeout, never a reason to wait longer or retry silently. This matters
  most for any operation that starts ongoing/background work (a server, a
  long-lived process): its executor must itself verify, synchronously and
  promptly, that the work has actually started before returning — never a
  fabricated or assumed status — and must never block waiting for the
  ongoing work itself to finish. If the harness itself needs to start such
  a process to test it (e.g. an HTTP server it then sends requests to),
  use process_supervisor's own start/stop operations
  (`blueprint/dep/MANIFEST.yaml: process_supervisor`) rather than a bare background
  launch — a detached shell command, PowerShell's `Start-Process -PassThru`,
  a fire-and-forget `subprocess.Popen` all leave the process running after
  the command that launched it ends, invisible and still holding its port,
  so the next run talks to whichever orphaned process happens to still be
  listening, not the one just started. `ready_check` and `argv` are always
  supplied by the caller, never assumed by the tool — it works the same
  way regardless of what language or framework the process under test is.
- Drive every consumer-visible interaction through a scripted command
  stream using the same dispatcher the real interface uses.
- Include at least one case proving an operator decision window: a scripted
  action lands between two automatic ticks and its effect is observable.
- Write `state/verification-record.json`, valid against
  `blueprint/schemas/verification-record.schema.json`: `verification_id`,
  `state_ref`, `harness`, `environment` (the platform this harness run
  actually executed on — `os`/`arch` required, e.g. Python's
  `platform.system()`/`.machine()` or the equivalent for whatever language
  the harness runs in — captured once for the whole run, never per-check,
  never hardcoded), `checks[]` (unique `check_id` per check; a check with
  `check_type: capability_operation` MUST carry a `trace` array copied
  verbatim from the observed response, and its own `input` — the actual
  value that call was made with, never reconstructed after the fact),
  `passed`, `failed`, `status` (`"verified"` or `"failed"`) (Gate 38).
- Once every check has passed, write `state/verification-record.json` as
  green (above) and stop there — this harness's own job is done. Do NOT call
  `episode_store.save_episode` from inside this harness: recording the
  episode is now `blueprint.dep.finish_cycle`'s job (section 7, 1-CYCLE.md
  Phase 8 Gate 31), and it needs this cycle's own new capabilities already
  registered into `capability-catalog.jsonl` before it can check Gate 30's
  acyclic-graph requirement against the real, complete graph — registration
  hasn't happened yet at this point in the harness. Observed for real: the
  one harness in this repo that ever called `save_episode` did so from
  exactly this point, and never called the paired `clear_checkpoint` at all
  — two separately-rememberable steps, one of which was simply forgotten
  every time it mattered. `finish_cycle` exists so that can't happen again:
  one call, from any language via its CLI, does both, with the
  acyclic-graph refusal as a hard prerequisite instead of an unenforced
  claim.

**Before the loop below is considered done, re-read your own entry point
code once more, on purpose (Gate 36).** The harness above proves every
capability trace reaches `executed`; it does NOT catch an entry point that
quietly re-derives a value a capability already owns, because that code
still runs and still renders something plausible — nothing fails, nothing
traces wrong, it's simply not resolving that value through the Bridge.
Read every entry point / consumer-facing file (a process entry point, a
browser runtime's bootstrap/rendering script) end to end and flag every
numeric or string literal that is not pure presentation (a color, a pixel
size, a label). For each one, check whether some capability's own contract
or executor already defines or computes that same value — if so, this is
the R6/R9 violation Gate 27 prohibits, just invisible to any automated
check: fix it by having that capability RETURN the value in its output
(extending its contract/executor if it doesn't yet), then have the entry
point read it from there, never re-derive it locally. Observed for real:
an entry point re-displayed a statistic using hardcoded per-type constants
that a capability's own executor already computed internally under the
same names but never returned — the two copies agreed by coincidence, and
would have silently drifted the moment either one changed.

**This is a loop, not a one-shot:**

1. Run the harness.
2. Any check fails? Fix that specific defect (or split/reuse per Phase 4) —
   then go back to step 1.
3. Only once every check passes on a fresh run does step 7 begin. An
   unverified state is never published (R5, Gate 20).

## 7. Publish and return state (Phase 8–9)

- Confirm the registry discovers a candidate for every capability you built
  (capability id, contract version, operation), then rebuild/append
  `capability-catalog.jsonl` so it reflects this cycle's own new
  capabilities — this must happen BEFORE the bullet below, since
  `finish_cycle`'s acyclic check reads exactly this file.
- Write the cycle report, valid against `blueprint/schemas/agent-cycle-report.schema.json`.
  Optionally attach `resulting_state_ref`
  (`blueprint/dep/MANIFEST.yaml: state_ref`,
  `blueprint.dep.state_ref.capture_state_ref(paths, repo_root=...)`) — an
  immutable content hash over `resulting_state`'s own files (contracts,
  capabilities, the generated catalog — whatever paths this application's
  own harness names, never a default that walks the whole tree) as they
  actually are at THIS cycle's completion, since `resulting_state` itself
  is a live path a LATER cycle goes on to mutate. `repo_root`, when given,
  adds an OPTIONAL supplementary `vcs` (git commit/branch/dirty) via a
  real, non-fatal probe — DEP references git when relevant but never
  depends on it: a `resulting_state` outside any git working tree still
  gets a real `content_hash`, just no `vcs` (Gate 38).
- Finish the cycle: call `blueprint.dep.finish_cycle`
  (`blueprint/dep/MANIFEST.yaml: finish_cycle`, 1-CYCLE.md Phase 8 Gate 31)
  with the cycle report, verification record, this cycle's own
  freshly-rebuilt `capability-catalog.jsonl`, the episodes directory, and
  the checkpoint path if one is in use. `episodes_dir`/`catalog_path`/
  `checkpoint_path` are always given explicitly, never defaulted by
  `blueprint/dep/` itself — an application's own episodes live under its
  own tree (e.g. `state/episodes/`, alongside `state/verification-record.json`),
  the same way its own `capability-catalog.jsonl` already does, not inside
  `sample/hello_world/backend/runtime/bridge/`. This ONE call refuses to
  record anything at all if the verification record's own `status` isn't
  `"verified"`, or if the catalog's declared dependency graph contains a
  cycle (Gate 30) — naming the exact cycle found (e.g. `"a -> b -> a"`)
  rather than a bare pass/fail. Only past both refusals does it record the
  episode (a schema-invalid record or a duplicate `verification_id` still
  fails the cycle, exactly as before) and clear the checkpoint (idempotent
  — already cleared, or never started, is a clean no-op) in the same call.
  A harness written in a language other than Python invokes exactly the
  same guarantee via `python -m blueprint.dep.finish_cycle --cycle-report ...
  --verification-record ... --catalog ... --episodes-dir ... [--checkpoint ...]`
  as a subprocess call — the one thing that makes Gate 31 satisfiable from
  a JS frontend's own `verify.js` (Gate 19) or any other non-Python
  harness, not just a Python one. See `sample/hello_world/backend/README.md`
  for a worked example (this file never restates a sample's own concrete
  files or their language, same posture as section 0 toward the Bridge).
- The resulting state — `contracts/`, `capabilities/`, `app/`, `tests/`,
  `state/verification-record.json`, the report, and the recorded episode
  in `state/episodes/` — is everything the next cycle needs. No private
  memory of this session should be required to continue the work (Gate 11).

## Failure patterns this file exists to prevent

- Writing the feature straight into one class/file, with a CLI dispatcher
  calling its methods directly — no contract, no manifest, no Bridge
  anywhere. (This is what happened the first time this Blueprint was
  handed to an agent without this file.)
- Treating "based on this Blueprint" as a naming or flavor theme rather than
  an operating procedure.
- Skipping the verification harness because the application "runs fine
  manually."
- An agent interrupted mid-cycle (tokens, network, crash) leaving no
  checkpoint — the next agent has nothing but raw filesystem state to
  reverse-engineer which responsibilities were decided, which have a
  contract but no manifest yet, which are fully wired through the Bridge.
  Checkpoint's own save operation (`blueprint/dep/MANIFEST.yaml: checkpoint`),
  called after every responsibility-status
  change (step 1), exists to prevent exactly this. Observed for real: an
  agent resumed successfully but at high cost, by scanning the whole
  project — the checkpoint (or its `artifacts`/`ecosystem_resolution_ref`
  fields) either didn't exist yet or wasn't trusted. A checkpoint that
  only records a status label, without the file path that earned it,
  still forces that same expensive re-scan (Gate 33) — resuming must cost
  less than starting fresh, never the same.
- A checkpoint that exists but went stale — work happened without
  `save_checkpoint` being called to record it (also observed for real:
  frozen at Phase 0 while 8 capabilities already existed on disk). The
  instinct to distrust a stale checkpoint is correct; falling back to
  reading the whole project to reconstruct progress is not — that pays
  the exact O(project) cost checkpoints exist to remove. Reconcile against
  a bounded source of truth instead — `capability-catalog.jsonl` if it
  exists, via checkpoint's own catalog-reconciliation operation, or the naming
  convention if it doesn't yet, e.g. mid-Phase-5 before Phase 8 ever
  builds one, via checkpoint's own filesystem-reconciliation operation
  (`blueprint/dep/MANIFEST.yaml: checkpoint`; Gate 34) — then
  re-save immediately so the repair is never paid for twice.
- Building a real service (a web server, a scheduler) directly inside the
  entry point because "it's just infrastructure." If the entry point needs a
  real service, that service is a capability (R9) — the entry point only
  calls it.
- An entry point quietly re-deriving a value some capability already
  defines or computes, instead of that capability returning it — every
  mechanical check (schema validation, Bridge trace, harness) passes,
  because nothing about this fails or traces wrong; it just isn't resolved
  through the Bridge (R6/R9). Invisible to a "does it decide anything?"
  skim; only checking the entry point's own literals one by one, against
  what each capability already defines, catches it (Gate 36).
- Recording an episode without clearing the paired checkpoint, or having no
  way at all to record one from a non-Python harness — observed for real:
  the one harness that ever called `save_episode` never called
  `clear_checkpoint`, and every harness in any other language had nothing
  to call either function with, since neither was ever ported.
  `finish_cycle`'s own CLI is a subprocess call any language can make; the
  checkpoint clear is no longer a step a harness has to separately
  remember.
