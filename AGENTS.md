# Instructions for any agent working in this repository

**Read `0-WALKTHROUGH.md` in full before writing any code here.** This
applies regardless of which agent or model you are — the rules below are
not tied to any one vendor or tool.

Every past attempt to build something in this repository without first
reading `0-WALKTHROUGH.md` produced a plain monolith script: a single class
with a pile of methods, no contracts, no manifests, no Bridge, no
capabilities. That is exactly the failure this Blueprint exists to prevent,
and it has happened more than once on this exact repository.

The one rule that matters most, if you read nothing else: **default to
capability.** A canonical Bridge/Registry/Policy/Selector/assembler already
exists at `bridge/` (see `0-WALKTHROUGH.md` step 0). Any distinct need —
including things that look like plain infrastructure (reading input,
tracking time, dispatching a command, or composing a few other capabilities
together) — gets its own contract, manifest, and registration-unaware
executor, wired through that Bridge. The only structural exception is the
single request-construction point (`0-WALKTHROUGH.md` step 4); the entry
point itself is ordinary consumer code, per R1. If you are about to write a
class with several methods that directly mutate application state, stop —
that is a capability (or several), not a class.

Read order: `0-WALKTHROUGH.md` → `1-CYCLE.md` → `2-RULES.md` → `3-TEMPLATES.md`.
