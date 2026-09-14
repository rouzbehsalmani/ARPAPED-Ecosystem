# Instructions for any agent working in this repository

**Which pillar(s) is this goal adopting?** This Blueprint is three
independently adoptable pillars -- Cycles (the 9-phase cycle,
`1-CYCLE.md`/`2-RULES.md`), Bridge (the Bridge/capability execution
model, `2-RULES.md` R1-R9), and DEP (`blueprint/dep/`, episode
recording for training). See README.md's "Three independently adoptable
pillars" section for what each gives you alone, and `1-CYCLE.md`/
`2-RULES.md`'s own "Scope" sections for exactly which gates/rules apply
to your goal's combination. If you don't know, or the goal touches
capabilities/a Bridge at all, assume the full integrated combination
below -- the default, fully-supported configuration `starterkit/`
demonstrates, and the rest of this file is written for it.

**Asked to start a genuinely new project** (however short the ask --
"start", "bootstrap this", etc.), with no pillar combination or target
location already given? Don't guess either one. See `packs/README.md`'s
"Starting the Bootstrap agent" section for the two questions to ask
before doing anything else.

**Read `blueprint/0-WALKTHROUGH.md` in full before writing any code here.** This
applies regardless of which agent or model you are — the rules below are
not tied to any one vendor or tool.

Every past attempt to build something in this repository without first
reading `blueprint/0-WALKTHROUGH.md` produced a plain monolith script: a single class
with a pile of methods, no contracts, no manifests, no Bridge, no
capabilities. That is exactly the failure this Blueprint exists to prevent,
and it has happened more than once on this exact repository.

The one rule that matters most, if you read nothing else: **default to
capability.** A canonical Bridge/Registry/Policy/Selector/assembler already
exists at `starterkit/backend/runtime/bridge/` (see `blueprint/0-WALKTHROUGH.md` step 0). Any distinct need —
including things that look like plain infrastructure (reading input,
tracking time, dispatching a command, or composing a few other capabilities
together) — gets its own contract, manifest, and registration-unaware
executor, wired through that Bridge. The only structural exception is the
single request-construction point (`blueprint/0-WALKTHROUGH.md` step 4); the entry
point itself is ordinary consumer code, per R9. If you are about to write a
class with several methods that directly mutate application state, stop —
that is a capability (or several), not a class.

Read order: `blueprint/0-WALKTHROUGH.md` → `blueprint/1-CYCLE.md` → `blueprint/2-RULES.md`.
