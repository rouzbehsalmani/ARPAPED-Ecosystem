# Packs

Three copy-paste manifests, one per pillar (README.md "Three
independently adoptable pillars"): [`bridge.yaml`](bridge.yaml),
[`dep.yaml`](dep.yaml), [`cycles.yaml`](cycles.yaml).

Each is an INDEX, not a duplicate — a `files:` list of this Blueprint's
own real, canonical paths, never a second copy of their content sitting
in this folder. Adopting a pack means copying the paths it names into
your new project's own tree. No prose to read to figure out what belongs
together; no need to ask an agent — read the one file for the pillar you
want.

## Adopting exactly one pack

Copy every path under that pack's own `files.required`. Copy anything
under `files.optional` only if you need what it's for (each entry says
why). Read the `rules:` pointer for what still applies from
`blueprint/2-RULES.md`, if anything. Done — that pack works standalone,
proven by this repo's own test suite (`packs/dep.yaml`'s
`no_bridge_required` note names the exact test).

## Combining more than one pack

Each pack file has its own `combine_with:` section naming exactly what
changes when another pack joins it — read the pack you're adding, not
just the one you started with, since the note may live on either side
(e.g. Bridge + DEP's wiring is documented once, in
`bridge.yaml`'s `combine_with.dep`, not repeated in
`dep.yaml`'s `combine_with.bridge` — read both, they're short).

For the full picture of Cycles + Bridge combined specifically — which
is the most gate-dense combination — `blueprint/1-CYCLE.md`'s own
"Scope: Bridge-scoped gates vs. always-applicable gates" section (and
`blueprint/2-RULES.md`'s matching "Scope" section) is the authoritative,
gate-by-gate answer; the packs' own `combine_with` notes summarize it,
they don't replace it.

**All three together** is `starterkit/` itself — not a fourth pack to
copy, a worked, runnable proof that the three combine cleanly. Copy
`starterkit/` directly (README.md "A real starter kit") rather than
assembling the three packs by hand if you want the full, integrated
configuration.

## Two-agent split: the Bootstrap agent prepares the ecosystem, the Builder agent builds on it

Two named roles, matching `1-CYCLE.md`'s own phase name for the first
one and the verb this document already used for the second: the
**Bootstrap agent** runs Phase 0 only (choose and resolve a pillar
combination, nothing more); the **Builder agent** starts at Phase 1 and
actually builds the application. Same agent, same session, or two
entirely separate ones — the split is a responsibility boundary, not a
requirement to use two different tools.

**Run it directly: `python -m packs.bootstrap`** — `list-pillars` prints
the menu below (generated live from these three files' own `pillar:`/
`description:` fields, never hardcoded prose that could drift from
them), `resolve` writes the handoff record, `describe` reads it back
human-readably. Proven end to end: `packs/tests/test_bootstrap.py`, and
a real Cycles+DEP run with no Bridge pillar at all — the Bootstrap agent
resolved and wrote the record, the Builder agent read only its path, ran
real verification checks, published a real episode via `finish_cycle`
with `catalog_path=None`, and fed it into `dataset_builder` — zero
re-discovery, zero conversation history required.

If the Cycles pillar is among what you're adopting, `1-CYCLE.md`
Phase 0 is designed to be run by a separate agent (or session) from the
one that builds the actual application: Phase 0's whole job is choosing
and resolving a pillar combination, and its output — the
**ecosystem-resolution record**
(`blueprint/schemas/ecosystem-resolution-record.schema.json`,
`blueprint.dep.ecosystem_resolution`) — is exactly the handoff artifact
the Builder agent needs to start at Phase 1 without re-resolving or
re-deciding anything the Bootstrap agent already settled (the same
bounded-resume discipline `1-CYCLE.md` Gate 33 already requires of a
checkpoint).

Concretely: tell the Bootstrap agent which pillar combination you want
(or have it offer you the options — `1-CYCLE.md` Phase 0 step 2 now
requires this explicitly for a genuinely new ecosystem root, never a
silent default to all three); it copies the relevant pack(s)' files,
wires whatever `combine_with:` hooks you chose, and writes the
resolution record. Hand that record's path to the Builder agent; it
reads `pillars:` to know what exists (and `combine_with_applied:` to
know what's already wired) and proceeds from Phase 1 onward. Neither
agent needs the other's conversation history — the record is the whole
interface, machine-readable and schema-validated, not a prose summary
to reconstruct by re-reading a transcript.

This works even without the Cycles pillar adopted for the actual
application: a Bootstrap agent can still prepare a Bridge+DEP
ecosystem (say) and hand off a resolution record describing it, purely
as a setup step, even if the Builder agent then works without any
further cycle discipline.

### Starting the Bootstrap agent

The ask can be as short as **"start a new project"** — the Bootstrap
agent doesn't need a filled-in template handed to it. If you're acting
as the Bootstrap agent and the user asked you to start (in any
phrasing) without already giving you a pillar combination and a target
location, ask before doing anything else.

**Run `python -m packs.bootstrap questions` in a loop — one call per
question, never reconstruct the flow from memory.** It prints the ONE
next question to ask: `id`, the question text, its `kind`, and its
`options` (if any) already resolved for you. Ask exactly that question,
get a real answer, write `{question_id: answer}` into a JSON file
(adding to it as you go), then run the command again with
`--answers-file` pointing at that file — repeat until it prints "Nothing
left to ask." **Every single time, even if you're confident you already
know what comes next.** This is not optional or a convenience: a real
run skipped both Bridge-language questions entirely, because the agent
ran the command ONCE, saw a few unconditional questions, asked all of
them, and moved on without ever re-running it after `pillars` and
`app_runtimes` were answered — which is exactly when
`bridge_language_backend`/`bridge_language_frontend` first become
visible (both require `pillars` to name "bridge" AND `app_runtimes` to
name a matching runtime). One call, one
question, one answer, repeat — that loop is the only thing that
prevents this. (`--all` prints every remaining question at once instead
— useful for a human previewing the flow, never for actually driving
it.) `QUESTIONS` in `packs/bootstrap.py` is the one place this is
declared — this whole command exists because an agent once free-handed
the flow from prose and invented a redundant "write your own" option
next to a question's own already-automatic free-text fallback; running
it instead of reconstructing the list from memory is what prevents
both failure modes.

**Use your environment's actual selection mechanism for anything with a
`kind` other than `"open"` — this is not conditional, and plain text the
user has to type an answer into is not an acceptable substitute for a
question whose `options` are already known.** In Claude Code, that
mechanism is the AskUserQuestion tool; if you're running as some other
agent, use whatever equivalent choice/menu mechanism you have — do not
fall back to prose-and-free-text just because rendering a real choice
takes one more tool call. `"closed"` (`pillars`, `project_kind`,
`app_runtimes`) has no free-text fallback at all: its `options` are the complete, only
valid answers, offered as clickable choices. `"open_with_default"` /
`"open_with_options"` pair their `options` with whatever free-text/
"Other" fallback your mechanism provides automatically — never add a
redundant extra option yourself that just restates "or type something
else," that's the exact mistake this design already fixed once. Only
`"open"` (`location`) has no options at all: nothing sensible to
suggest, so ask it plainly, in text, and never propose an example.

Once you have an answer to a question, here's what each one means for
what you copy or do next — this reasoning isn't in `QUESTIONS` itself,
only the flow and options are:

- **`project_kind`**: asked right after `pillars`, before anything else,
  because it changes what every later step actually means — "new" vs.
  "existing" (`packs/bootstrap.py`'s own `_QUESTIONS`). For "existing":
  see "Adopting onto an existing project" below before doing anything
  else — the short version is you are NOT building an application, you
  are adding tooling to one that already exists. For "new": the sections
  below (and, if Bridge is adopted, `starterkit/`'s own worked example)
  apply as written.
- **`app_runtimes`**: asked for every pillar combination, Bridge adopted
  or not — this describes the shape of the APPLICATION (does it have a
  backend, a frontend, or both), not of the Bridge. No Bridge doesn't
  mean no backend or no frontend: a DEP+Cycles-only project can have a
  real backend and/or frontend, in some language, with no Bridge
  capability-execution pattern involved at all. It gates which of the two
  question pairs below fires for each runtime: with Bridge among
  `pillars`, read `packs/bridge.yaml`'s own `files.choose_at_least_one`
  directly rather than re-deriving the choice from memory — frontend-only
  is real (e.g. a browser-only app whose capabilities are all Local, no
  backend at all), so is backend-only, so is both wired together as
  `starterkit/` demonstrates — never assume backend just because it's the
  more detailed of the two to resolve. Recorded regardless of Bridge, in
  the record's own top-level `app_runtimes` — with no Bridge adopted,
  there is nowhere else this answer would ever be written down.
- **Per runtime named in `app_runtimes`, exactly one of these two
  question pairs fires, never both, never neither:**
  - **`bridge_language_backend` / `bridge_language_frontend`** — when
    Bridge IS among `pillars`. `starterkit/`'s own Python (backend) /
    JavaScript (frontend) code is a REFERENCE implementation, not the
    only option (`packs/bridge.yaml`'s own header comment explains what
    must carry over unchanged if a different one is named — the
    four-stage pipeline, the observed trace shape, the same schemas). An
    answer matching the reference means copy those files directly; any
    other answer means PORT them into that language yourself, using the
    reference implementation and `2-RULES.md`'s Bridge/Bridge
    Core/Registry/Policy/Selector glossary entries as the specification —
    real work, not a copy-paste, and not something to decline or
    substitute silently. Record whichever language was actually used in
    that runtime's own `pillars.bridge.runtimes[].language` when you
    write the ecosystem-resolution record — never left implicit.
  - **`app_language_backend` / `app_language_frontend`** — when Bridge is
    NOT among `pillars`. No reference language to suggest here (unlike
    `bridge_language_backend`'s "Python") — the only offered option is
    "Not yet / I don't know," though a concrete real language is still a
    perfectly valid free-text answer (this is exactly the failure this
    pair's own existence fixes: a dep+cycles-only run's real "C#" answer
    was once asked, given, and then never asked for again in a form that
    could be recorded at all). Record whichever answer you got in
    `--app-language-backend`/`--app-language-frontend` when you write the
    ecosystem-resolution record (omit either flag entirely if its
    matching question never applied) — see "No Bridge means no
    capability vocabulary" below for what this answer constrains.
- **`location`**: given by the user, never proposed or suggested by
  you. A relative location or plain description ("a folder called
  my-app next to this repo", "in my usual projects folder") is also
  acceptable — resolve it yourself, then always confirm the resolved
  absolute path back before proceeding, never silently guess and
  continue. Either way, a path that isn't already another application's
  own root. `packs.bootstrap resolve` accepts either form for
  `--ecosystem-root` and always normalizes it to absolute before storing
  it (never taking a relative path's meaning from whatever directory
  `resolve` happens to run in later) — but asking for or confirming the
  absolute path up front avoids relying on that safety net silently.

Once you have every answer that applies, **actually copy the files —
this is a real action you take, not a sentence you read past.** If
Bridge is among `pillars`: for each runtime named in `app_runtimes`,
either copy `files.choose_at_least_one`'s matching entry directly (its
own language answer matched the reference) or port it into that
language yourself (it didn't). Either way (Bridge adopted or not), copy
the rest of each adopted pack's own `files.required`. Wire any
`combine_with:` hooks the combination calls for. If `project_kind` is
"existing," see "Adopting onto an existing project" below first — what
"copy the files" means there is narrower than it sounds. Only THEN run
`python -m packs.bootstrap resolve --ecosystem-root <location>
--pillars-file <a JSON file you write, matching the schema's `pillars`
shape -- one `runtimes[]` entry per runtime named in `app_runtimes`,
each with its own `language`, if Bridge was adopted> --project-kind
{new,existing} --app-runtimes {backend,frontend,both}
[--app-language-backend <answer>] [--app-language-frontend <answer>]`.

**Pass `--app-runtimes` even when Bridge was never adopted — there is
nowhere else that answer would ever be written down.** Pass
`--app-language-backend`/`--app-language-frontend` ONLY for a runtime
whose matching `app_language_backend`/`app_language_frontend` question
actually applied (Bridge NOT among `pillars`) — omit the flag entirely
otherwise; never pass a value for a runtime whose language already lives
in `pillars.bridge.runtimes[].language` instead, that would just create
two answers that could disagree. Real, observed failure `app_language_*`
fixes: the question was asked and answered ("C#"), but the answer was
never written into the resolution record at all, so the Builder agent —
which reads ONLY this record, never the Bootstrap conversation — had no
way to know it, and built the application in Python instead.

**`resolve` itself refuses to run if `<location>` shows no real
evidence anything was actually copied or ported into it** (nothing
there at all, or nothing but a `state/` directory) — this is a real,
observed failure, not a hypothetical: a run answered every question
correctly, then called `resolve` directly without ever copying a single
file, producing a fully schema-valid record naming real-looking paths
(`starterkit/backend/runtime/bridge/bridge.py`, copied verbatim from
THIS repo) that didn't exist anywhere in the target project at all. If
`resolve` refuses, that means the copying step above was skipped —
go back and actually do it, don't retry `resolve` expecting a different
result. Report back only the resolution record's path — that's the
whole handoff; nothing else needs explaining to the Builder agent.

## No Bridge means no capability vocabulary

**If Bridge is NOT among `pillars`, never create anything shaped like
the Bridge's own model for the application's own code — no
`*.contract.yaml`, no `manifest.yaml` with a `capability_id` or
`implementations[]`, no `executor.py`/`executor_kind`, no
`capability-catalog.jsonl`, nothing named "capability" as a structural
concept.** That entire vocabulary — contract, manifest, capability,
executor, Registry, catalog — belongs exclusively to the Bridge's own
discovery → policy → selection → execution model
(`packs/bridge.yaml`, `2-RULES.md`'s Bridge/Registry/Policy/Selector
glossary). Without a Bridge, there is no Registry to publish a
capability to and no Bridge to select an implementation through, so
there is nothing for a "capability" to actually be — inventing the
shape anyway produces inert files nothing ever reads.

Without Bridge, **the application is just the application**: plain code
in whatever `app_language_backend`/`app_language_frontend` named,
organized however that language's own conventions call for — a normal
C# app, a normal Python script, whatever
the goal actually calls for. DEP, if adopted, records completed cycles
as episodes (`blueprint/dep/finish_cycle.py` with `catalog_path=None` —
see `packs/dep.yaml`'s own `no_bridge_required` note). Cycles, if
adopted, governs the *development process* — phases, gates like
reuse-before-writing (Gate 6), a headless verification pass (Gate 17),
regression checks (Gate 20), a legible resulting state (Gate 11) — never
the application's own internal architecture
(`packs/cycles.yaml`'s own `bridge_free_use` note has the full,
gate-by-gate list of what's skipped).

**This paragraph, alone, already failed once — twice.** A Builder agent,
given a DEP+Cycles-only resolution with no Bridge at all, built a full
`contracts/*.contract.yaml` + `capabilities/*/manifest.yaml` +
`executor.py` tree anyway, the exact Bridge shape, with none of the
actual Bridge schemas that would validate any of it even copied in — and
did it again on a second, separate run after this section already
existed. Defaulting to this Blueprint's own deeply-habitual pattern is
not a safe fallback, and remembering not to is not reliable enough on its
own. Two mechanical checks exist because of this, and actually running
them is not optional:

- **`python -m packs.bootstrap check-scope --ecosystem-root <location>`**
  — run this anytime during Phase 1-7, the moment you're unsure, or
  routinely while building. Exits 0 clean, or 1 naming every
  Bridge-shaped file/directory found
  (`blueprint.dep.ecosystem_resolution.detect_bridge_leakage`: any
  `contracts/`/`capabilities/` directory, any `*.contract.yaml`, any
  `manifest.yaml`/`manifest.json` whose own text contains both
  `capability_id` and `implementations`, any `capability-catalog.jsonl`).
  Returns `[]` unconditionally once Bridge IS among `pillars` — a real
  `contracts/` directory is exactly what a Bridge-adopting ecosystem is
  supposed to have, never a violation there.
- **`finish_cycle` (`blueprint/dep/finish_cycle.py`) runs the SAME check
  as a hard publish-time gate** when called with `catalog_path=None` and
  a real `ecosystem_root` — Phase 8 Gate 31 now REFUSES to publish a
  cycle while Bridge-shaped leakage exists, the same "fail closed"
  posture it already has toward an unverified verification record.
  Always pass `ecosystem_root` to `finish_cycle` when `catalog_path` is
  `None` — omitting it just means this specific refusal silently doesn't
  run, the same gap this parameter exists to close.

## Adopting onto an existing project

`project_kind: "existing"` means the ecosystem root already has a real
project in it before you touch anything — you are not building an
application, you are adding the adopted pillar(s)' own tooling to one
that already exists. Concretely, this changes "actually copy the files"
above:

- Copy each adopted pack's own `files.required` (and, if Bridge is
  adopted, the runtime(s) named in `app_runtimes`) into the existing
  tree, as a genuinely new addition alongside what's already there —
  never overwrite, restructure, or move anything the existing project
  already had.
- **Never invent placeholder or example application code.** There is no
  blank slate to fill in; the application already exists, in whatever
  shape and language its own author already gave it. If
  `app_language_backend`/`app_language_frontend` names something
  different from what the existing project is actually written in,
  that's real information worth surfacing back to the user before
  proceeding, never a cue to start writing a parallel implementation in
  the answered language.
- If Bridge is among the adopted pillars and the existing project has no
  Bridge yet, follow the normal Bridge file-copying/porting steps, but
  integrate them into the existing project's own structure rather than
  scaffolding a fresh `starterkit/`-shaped tree — `starterkit/`'s own
  Layout is a worked example of the SHAPE, not a template to stamp down
  over an existing project's own layout decisions.
- `resolve`'s own refusal (above) will typically never trigger for
  "existing" — the existing project's own files already satisfy "some
  real content beyond `state/`" before any pillar tooling is even
  copied. That's expected, not a loophole: the check was only ever a
  safety net for "nothing was copied at all," and an existing project
  starts with real content by definition. The actual governance for
  "existing" is everything above, not this check.

## Why an index instead of a copy

A pack file that duplicated its files' content would drift from the
real source the moment either changed, silently. Pointing at the real
paths means a pack is never stale — and matches how every other
authoritative descriptor in this Blueprint already works
(`blueprint/dep/MANIFEST.yaml`: "Docs never name a file directly... If
any piece is ever built, reimplemented, or restructured, update ONLY
this file").
