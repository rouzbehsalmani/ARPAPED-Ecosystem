"""Single request-construction point for this sample app (R6).

Builds a registry and Bridge (policy/selector from bridge/MANIFEST.yaml),
then registers every implementation from the generated capability
catalog (build_catalog.py) -- never by walking capabilities/ directly.
The Bridge is built before assembly runs: greeting.compose declares
executor_kind: factory, which needs a live Bridge to build its
Dependencies, even though the registry it wraps is still empty at that
instant (nothing reads it until real calls happen).

Exposes resolve(name, operation) -- name and operation are the only
things ever restated at a call site; capability_id, contract_version,
and (if pinned) implementation_id come from the matching entry in
dependencies.yaml, keyed by name rather than capability_id (unlike a
contract's own dependencies.capabilities, R4) so the same capability can
be declared more than once under different names/pins.

Only discovery is cached per resolve() call -- every .call() still runs
a fresh policy/select/execute cycle through bridge.handle, self-healing
if cached candidates have gone stale.
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
    `{name: {capability_id, contract_version, implementation_id}}`
    (`implementation_id` is `None` when undeclared). Keyed by name, not
    capability_id (unlike `assembler.py`'s `parse_dependencies`), so the
    same capability_id can appear under more than one name.
    `contract_version` is required, never defaulted to "*" -- a
    malformed entry fails here, at load time, not later as a confusing
    `BRIDGE_UNDECLARED_DEPENDENCY`.
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
    `dependencies.yaml`. Raises `BRIDGE_UNDECLARED_DEPENDENCY` if `name`
    isn't declared there.
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
