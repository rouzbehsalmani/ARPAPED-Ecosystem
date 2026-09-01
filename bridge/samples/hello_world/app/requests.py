"""Single request-construction point for this sample app (Phase 6, R6).

Exactly one module builds the Bridge and hands out access to it: build a
registry; construct the Bridge from it plus the policy and selector
resolved from bridge/MANIFEST.yaml; only THEN register every implementation
from the generated capability catalog into the registry (build_catalog.py,
Phase 8 mechanics, step 5) — never by walking and re-parsing capabilities/
itself, which doesn't scale. It then exposes one `resolve` operation.
Nothing else in this sample imports the Bridge, constructs a request, or
calls `bridge.handle` directly.

The Bridge is built BEFORE assembly runs, not after: `greeting.compose`
declares `executor_kind: factory` (it needs live access to console.write —
see its manifest and executor), and a factory-kind entry needs a Bridge to
build its `Dependencies` against. This is safe even though the registry is
still empty at that instant — `Bridge` only holds a reference to it, and
nothing reads that reference until real calls happen, well after assembly
finishes.

`resolve` is a thin pass-through to `Bridge.resolve` (bridge/bridge.py):
callers resolve a capability+operation once and get back a handle whose
`call(...)` they invoke as many times as they need (discover once, call many
times). The handle only reuses the discovery stage — policy is still
evaluated and a candidate is still selected and executed fresh on every
call, through the same `bridge.handle` every request goes through, and the
handle re-checks its cached candidates' live state on each use (self-healing
by re-discovering if they've all become unusable) rather than trusting a
stale snapshot. Building the request itself is Bridge library code, not
application code, so this stays consistent with R6: this module is still the
only place in the app that reaches the Bridge at all.
"""

from pathlib import Path

from bridge.assembler import assemble_from_catalog
from bridge.bridge import Bridge
from bridge.policy import StaticPolicyEngine
from bridge.registry import CapabilityRegistry
from bridge.selector import DeterministicSelector

_APP_ROOT = Path(__file__).resolve().parent.parent

_registry = CapabilityRegistry()
_bridge = Bridge(_registry, StaticPolicyEngine(), DeterministicSelector())
assemble_from_catalog(_APP_ROOT / "capability-catalog.jsonl", _registry, bridge=_bridge)


def resolve(capability_id, operation, contract_version="*"):
    """`contract_version` is a version-range constraint (see registry.py's
    `_matches_version`), owned by the caller's own compatibility expectations
    for this capability+operation — not something this module can invent on
    a capability's behalf. It defaults to "*" (any registered version) since
    this sample makes no version claim of its own.
    """
    return _bridge.resolve(capability_id, operation, contract_version)
