# Agent Cycle Report

## Goal

`<goal>`

## Starting State

`<state>`

## Reusable Discovery

`<discovery references>`

## Decisions

For each responsibility:

`reuse | compose | split/refactor | create`

## New Components

`<component identities>`

## Reused Components

`<component identities>`

## Split/Refactor Operations

`<lineage references>`

## Registry Changes

`<discoverability/index changes>`

## Bridge Integration

`<canonical path reference>`

## Verification

Report against the checklist in `04-runtime/verification-contract.md`. For each
of its points — assembly/startup; capability decomposition; every capability
operation with the full ordered trace; every consumer interaction via scripted
stream; operator decision window; reactive same-session; invariants; record —
state PASS/FAIL with evidence.

`<harness path/identity in the resulting state>`

`<trace evaluation>` — the observed Bridge trace for every capability operation
(`validated → discovered → policy_evaluated → selected → executed`,
`check.trace` in the record) and any failure of the ordered stages.

`<failures observed and fixes applied; regression re-run status>`

`<verification record reference; status: verified | failed>`

## Resulting State

`<state>`

## Next-Cycle Readiness

`<how the resulting state is discoverable without agent memory>`
