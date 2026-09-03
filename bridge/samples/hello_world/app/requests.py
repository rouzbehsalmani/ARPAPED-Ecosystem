"""Single request-construction point for this sample app (Phase 6, R6).

Exactly one module builds the Bridge and hands out access to it: build a
registry; construct the Bridge from it plus the policy and selector
resolved from bridge/MANIFEST.yaml; only THEN register every implementation
from the generated capability catalog into the registry (build_catalog.py,
Phase 8 mechanics, step 5) — never by walking and re-parsing capabilities/
itself, which doesn't scale. It then exposes one `resolve` operation
(below). Nothing else in this sample imports the Bridge, constructs a
request, or calls `bridge.handle` directly.

The Bridge is built BEFORE assembly runs, not after: `greeting.compose`
declares `executor_kind: factory` (it needs live access to console.write —
see its manifest and executor), and a factory-kind entry needs a Bridge to
build its `Dependencies` against. This is safe even though the registry is
still empty at that instant — `Bridge` only holds a reference to it, and
nothing reads that reference until real calls happen, well after assembly
finishes.

This module also declares its OWN dependencies, in `dependencies.yaml`:
each entry is named by whatever this app calls it, mapping to exactly the
capability_id, contract_version, and (if needed) implementation_id
`resolve` should use — read once, here, at load time. `resolve(name,
operation)` takes only a name and an operation; the version (and, where
declared, which specific implementation) is never restated at the call
site — upgrading which version the app uses means editing one entry in
`dependencies.yaml`, not hunting down every call site. Unlike a capability
contract's own `dependencies.capabilities` (R4), which is keyed by
capability_id, this is keyed by name — so the SAME capability can be
declared more than once, pinned differently for different purposes (see
`dependencies.yaml`), which a single capability's own dependency on
another never needs.

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

from bridge.assembler import assemble_from_catalog
from bridge.bridge import Bridge, BridgeError
from bridge.policy import StaticPolicyEngine
from bridge.registry import CapabilityRegistry
from bridge.selector import DeterministicSelector

_APP_ROOT = Path(__file__).resolve().parent.parent
_APP_DIR = Path(__file__).resolve().parent

_registry = CapabilityRegistry()
_bridge = Bridge(_registry, StaticPolicyEngine(), DeterministicSelector())
assemble_from_catalog(_APP_ROOT / "capability-catalog.jsonl", _registry, bridge=_bridge)


def _load_declared_dependencies(raw):
    """Decodes `dependencies.yaml`'s `capabilities` mapping into
    `{name: {capability_id, contract_version, implementation_id}}`.
    `implementation_id` is `None` when not declared for that name.

    Deliberately does not reuse `bridge/assembler.py`'s `parse_dependencies`:
    that helper is keyed by capability_id (one entry per capability, the
    shape a capability contract's own dependencies need) and lets a bare
    string mean "*"; this is keyed by name, so the same capability_id can
    appear under more than one name, pinned differently for different
    purposes -- and `contract_version` is required on every entry, never
    defaulted to "*", the same "no silent default" discipline `Bridge.resolve`
    itself enforces (2-RULES.md "No silent defaults on what resolution
    depends on"). A malformed entry fails loudly here, at load time,
    rather than surfacing later as a confusing `BRIDGE_UNDECLARED_DEPENDENCY`
    for a name the caller thought was already declared correctly.
    """

    declared = {}
    for name, spec in (raw or {}).items():
        if not isinstance(spec, dict) or not isinstance(spec.get("capability_id"), str):
            raise ValueError(f"dependencies.yaml: {name!r} must declare a string 'capability_id'")
        if not isinstance(spec.get("contract_version"), str) or not spec["contract_version"].strip():
            raise ValueError(f"dependencies.yaml: {name!r} must declare a non-empty 'contract_version' — no default")
        declared[name] = {
            "capability_id": spec["capability_id"],
            "contract_version": spec["contract_version"],
            "implementation_id": spec.get("implementation_id"),
        }
    return declared


_declared_raw = yaml.safe_load((_APP_DIR / "dependencies.yaml").read_text(encoding="utf-8"))
_declared = _load_declared_dependencies(_declared_raw.get("capabilities"))


def resolve(name, operation):
    """Resolves the capability+operation declared under `name` in
    `dependencies.yaml` -- capability_id, contract_version, and (if given)
    implementation_id all come from that one declared entry, never
    restated at the call site. Raises `BRIDGE_UNDECLARED_DEPENDENCY` if
    `name` isn't declared there; add it before depending on it.
    """
    spec = _declared.get(name)
    if spec is None:
        raise BridgeError(
            "BRIDGE_UNDECLARED_DEPENDENCY", "validation",
            f"{name!r} is not declared in dependencies.yaml — add it there before depending on it",
        )
    kwargs = {}
    if spec["implementation_id"] is not None:
        kwargs["implementation_id"] = spec["implementation_id"]
    return _bridge.resolve(spec["capability_id"], operation, spec["contract_version"], **kwargs)
