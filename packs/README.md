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
location, ask before doing anything else:

1. **Which pillar combination?** Run `python -m packs.bootstrap
   list-pillars` and show the menu — never assume all three, never
   assume Bridge alone (`1-CYCLE.md` Phase 0 Gate 35).
2. **If the Bridge pillar is among them: backend, frontend, or both?**
   (`packs/bridge.yaml`'s own `files.choose_at_least_one` — read it
   directly rather than re-deriving this choice from memory.) All
   three are real, valid choices: frontend-only (e.g. a browser-only
   app whose capabilities are all Local, no backend at all),
   backend-only, or both wired together as `starterkit/` demonstrates.
   Never assume backend just because it's the more detailed of the two
   to resolve. Not applicable at all if Bridge isn't among the chosen
   pillars — skip this question entirely.
3. **Where should the new project live?** Its ecosystem root — an
   absolute path, given by the user, never proposed or suggested by
   you: ask for it plainly ("what's the absolute path?") and do not
   offer an example path as if it were a default or a hint. A relative
   location or plain description ("a folder called my-app next to this
   repo", "in my usual projects folder") is also acceptable — resolve
   it yourself, then always confirm the resolved absolute path back
   before proceeding, never silently guess and continue. Either way, a
   path that isn't already another application's own root.
   `packs.bootstrap resolve` accepts either form for `--ecosystem-root`
   and always normalizes it to absolute before storing it (never taking
   a relative path's meaning from whatever directory `resolve` happens
   to run in later) — but asking for or confirming the absolute path up
   front avoids relying on that safety net silently.

Once you have every answer that applies: copy the chosen pack(s)'
`files.required` (backend/frontend/both from `files.choose_at_least_one`
when Bridge is among them, and whatever `files.optional` the
combination actually needs) into that location, wire any
`combine_with:` hooks the combination calls for, then run `python -m
packs.bootstrap resolve --ecosystem-root <location> --pillars-file <a
JSON file you write, matching the schema's `pillars` shape -- one
`runtimes[]` entry per runtime chosen in question 2, if Bridge was
adopted>`. Report back only the resolution record's path — that's the
whole handoff; nothing else needs explaining to the Builder agent.

## Why an index instead of a copy

A pack file that duplicated its files' content would drift from the
real source the moment either changed, silently. Pointing at the real
paths means a pack is never stale — and matches how every other
authoritative descriptor in this Blueprint already works
(`blueprint/dep/MANIFEST.yaml`: "Docs never name a file directly... If
any piece is ever built, reimplemented, or restructured, update ONLY
this file").
