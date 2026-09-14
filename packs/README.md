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
run skipped `bridge_runtimes` and both Bridge-language questions
entirely, because the agent ran the command ONCE, saw a few
unconditional questions, asked all of them, and moved on without ever
re-running it after `pillars` was answered — which is exactly when
`bridge_runtimes` (and, behind it, `bridge_language_backend`/
`bridge_language_frontend`) first becomes visible. One call, one
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
takes one more tool call. `"closed"` (`pillars`, `bridge_runtimes`) has
no free-text fallback at all: its `options` are the complete, only
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

- **`bridge_runtimes`** (`packs/bridge.yaml`'s own `files.choose_at_least_one`
  — read it directly rather than re-deriving this choice from memory):
  frontend-only is real (e.g. a browser-only app whose capabilities are
  all Local, no backend at all), so is backend-only, so is both wired
  together as `starterkit/` demonstrates — never assume backend just
  because it's the more detailed of the two to resolve.
- **`bridge_language_backend` / `bridge_language_frontend`**:
  `starterkit/`'s own Python (backend) / JavaScript (frontend) code is a
  REFERENCE implementation, not the only option (`packs/bridge.yaml`'s
  own header comment explains what must carry over unchanged if a
  different one is named — the four-stage pipeline, the observed trace
  shape, the same schemas). An answer matching the reference means copy
  those files directly; any other answer means PORT them into that
  language yourself, using the reference implementation and
  `2-RULES.md`'s Bridge/Bridge Core/Registry/Policy/Selector glossary
  entries as the specification — real work, not a copy-paste, and not
  something to decline or substitute silently. Record whichever
  language was actually used in that runtime's own
  `pillars.bridge.runtimes[].language` when you write the
  ecosystem-resolution record — never left implicit.
- **`capability_language`**: independent of the Bridge's own language
  answer(s) — a capability can run in-process, in whichever language
  its own Bridge uses (needs nothing extra), or out-of-process in any
  language via the wire protocol. Only concretely actionable when
  backend was chosen; "not yet"/"don't know" is a common, expected
  answer either way. Check the answer against `packs/bridge.yaml`'s own
  `files.optional` yourself: Python or C# each have a real reference
  client to copy; anything else has none yet (that section's own
  trailing comment explains what porting one involves — never invent a
  client that doesn't exist).
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
this is a real action you take, not a sentence you read past.** For
each runtime named in `bridge_runtimes`, either copy
`files.choose_at_least_one`'s matching entry directly (its own language
answer matched the reference) or port it into that language yourself
(it didn't); copy whatever `files.optional` entry matches
`capability_language`'s answer, if any; copy the rest of
`files.required` regardless. Wire any `combine_with:` hooks the
combination calls for. Only THEN run `python -m packs.bootstrap resolve
--ecosystem-root <location> --pillars-file <a JSON file you write,
matching the schema's `pillars` shape -- one `runtimes[]` entry per
runtime named in `bridge_runtimes`, each with its own `language`, if
Bridge was adopted>`.

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

## Why an index instead of a copy

A pack file that duplicated its files' content would drift from the
real source the moment either changed, silently. Pointing at the real
paths means a pack is never stale — and matches how every other
authoritative descriptor in this Blueprint already works
(`blueprint/dep/MANIFEST.yaml`: "Docs never name a file directly... If
any piece is ever built, reimplemented, or restructured, update ONLY
this file").
