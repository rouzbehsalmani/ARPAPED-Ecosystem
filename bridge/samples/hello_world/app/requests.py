"""Single request-construction point for this sample app (Phase 6, R6).

Exactly one module builds the Bridge and hands out access to it: build a
registry; construct the Bridge from it plus the policy and selector
resolved from bridge/MANIFEST.yaml; only THEN register every implementation
from the generated capability catalog into the registry (build_catalog.py,
Phase 8 mechanics, step 5) — never by walking and re-parsing capabilities/
itself, which doesn't scale. It then exposes two resolve operations (below).
Nothing else in this sample imports the Bridge, constructs a request, or
calls `bridge.handle` directly.

The Bridge is built BEFORE assembly runs, not after: `greeting.compose`
declares `executor_kind: factory` (it needs live access to console.write —
see its manifest and executor), and a factory-kind entry needs a Bridge to
build its `Dependencies` against. This is safe even though the registry is
still empty at that instant — `Bridge` only holds a reference to it, and
nothing reads that reference until real calls happen, well after assembly
finishes.

This module also declares its OWN dependencies, in `dependencies.yaml`,
the same shape a capability contract's `dependencies.capabilities` uses —
parsed here with the same `parse_dependencies` (bridge/assembler.py) and
handed to a `Dependencies` (bridge/bridge.py), exactly the mechanism a
capability's own executor factory uses to resolve what its contract
declared. `resolve` is a thin pass-through to that `Dependencies.resolve`:
callers get a capability+operation handle without restating a version at
the call site — it's read from `dependencies.yaml` once, here, so
upgrading which version the app uses means editing that one file, not
hunting down every call site. `resolve_pinned` is the lower-level escape
hatch straight to `Bridge.resolve` for a genuine one-off pin outside the
app's normal declared dependencies (see app/main.py's use of it).

Either way, the returned handle's `call(...)` can be invoked as many times
as needed (discover once, call many times): only the discovery stage is
reused — policy is still evaluated and a candidate is still selected and
executed fresh on every call, through the same `bridge.handle` every
request goes through, and the handle re-checks its cached candidates' live
state on each use (self-healing by re-discovering if they've all become
unusable) rather than trusting a stale snapshot. Building the request
itself is Bridge library code, not application code, so this stays
consistent with R6: this module is still the only place in the app that
reaches the Bridge at all.
"""

from pathlib import Path

import yaml

from bridge.assembler import assemble_from_catalog, parse_dependencies
from bridge.bridge import Bridge, Dependencies
from bridge.policy import StaticPolicyEngine
from bridge.registry import CapabilityRegistry
from bridge.selector import DeterministicSelector

_APP_ROOT = Path(__file__).resolve().parent.parent
_APP_DIR = Path(__file__).resolve().parent

_registry = CapabilityRegistry()
_bridge = Bridge(_registry, StaticPolicyEngine(), DeterministicSelector())
assemble_from_catalog(_APP_ROOT / "capability-catalog.jsonl", _registry, bridge=_bridge)

_declared_raw = yaml.safe_load((_APP_DIR / "dependencies.yaml").read_text(encoding="utf-8"))
_dependencies = Dependencies(_bridge, parse_dependencies(_declared_raw.get("capabilities")))


def resolve(capability_id, operation, **kwargs):
    """Resolves `capability_id`+`operation` at the version constraint this
    app declared for it in `dependencies.yaml` — never restated here. Raises
    `BRIDGE_UNDECLARED_DEPENDENCY` if the capability isn't declared there;
    add it to that file before depending on it, the same discipline a
    capability contract's own `dependencies.capabilities` enforces (R4).
    """
    return _dependencies.resolve(capability_id, operation, **kwargs)


def resolve_pinned(capability_id, operation, contract_version, **kwargs):
    """`contract_version` is a version-range constraint (see registry.py's
    `_matches_version`), stated explicitly by the caller right here — no
    default, ever. The deliberate escape hatch for a genuine one-off pin
    that isn't part of this app's normal declared dependencies (see
    `resolve`, above) — e.g. proving a second, non-default version is still
    independently reachable, rather than an ongoing dependency relationship.
    """
    return _bridge.resolve(capability_id, operation, contract_version, **kwargs)
