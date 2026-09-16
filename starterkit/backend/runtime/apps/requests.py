"""Shared request-construction machinery (R6) for every app under
runtime/apps/ -- one Bridge/registry, built fresh per call to
make_resolver(app_dir), from the SAME capability catalog at runtime/
(this module's own parent), then bound to whichever app_dir's own
dependencies.yaml the caller passes. Lives here, not inside any single
app's own folder, because none of this is specific to one app -- copying
it into every apps/<name>/ folder would just be the same ~90 lines
duplicated verbatim each time; a second app just calls make_resolver too.

Imports everything under runtime/ (the Bridge, below) by RELATIVE
import, on purpose -- `runtime/` is the actual standalone, copyable unit
(not this apps/ folder, not any one app's own folder): drop it anywhere,
under any package name, and these imports still resolve, because they
never hardcode "starterkit.backend" or any other name above runtime/
itself. Only `blueprint.dep.runtime_log` (further below) reaches OUTSIDE
runtime/ -- a real, optional companion (packs/dep.yaml), never assumed
present.

Each app's own main.py calls make_resolver(Path(__file__).resolve().parent)
once, at import time, and gets back resolve(name, operation) -- name and
operation are the only things ever restated at a call site;
capability_id, contract_version, and (if pinned) implementation_id come
from the matching entry in THAT app's own dependencies.yaml, keyed by
name rather than capability_id (unlike a contract's own
dependencies.capabilities, R4) so the same capability can be declared
more than once under different names/pins.

Only discovery is cached per resolve() call -- every .call() still runs
a fresh policy/select/execute cycle through bridge.handle, self-healing
if cached candidates have gone stale. Each app gets its OWN registry/
Bridge instance (make_resolver builds a fresh pair every call, never a
shared module-level singleton) -- apps are separate processes in
practice (each has its own main.py entry point), so there's no reason to
share Bridge state between them even though they share the same
underlying catalog file.
"""

from pathlib import Path

import yaml

from ..bridge.assembler import assemble_from_catalog
from ..bridge.bridge import Bridge, BridgeError
from ..bridge.policy import StaticPolicyEngine
from ..bridge.registry import CapabilityRegistry
from ..bridge.selector import DeterministicSelector

try:
    # Optional, duck-typed, same posture packs/bridge.yaml's own
    # combine_with.dep note already documents for event_sink: "the Bridge
    # runs identically with or without it." Only import that reaches
    # OUTSIDE runtime/ -- absolute, never relative, since blueprint/dep/
    # is a real, separate companion (packs/dep.yaml), not part of this
    # copyable unit. Missing entirely (runtime/ copied standalone, no DEP
    # pillar adopted) is a normal state, not an error.
    from blueprint.dep.runtime_log import RuntimeEventLog
except ImportError:
    RuntimeEventLog = None

# runtime/apps/requests.py -> parent=apps, parent.parent=runtime.
_RUNTIME_ROOT = Path(__file__).resolve().parent.parent


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


def make_resolver(app_dir: Path):
    """Builds a fresh registry+Bridge from runtime/'s shared capability
    catalog, loads `app_dir`'s own dependencies.yaml, and returns
    resolve(name, operation) bound to both. Call once per app, at import
    time (see each app's own main.py) -- never per call.
    """

    registry = CapabilityRegistry()
    # event_sink: every real call through this Bridge -- harness-scripted
    # or genuine traffic alike -- is recorded as its own runtime event
    # (blueprint/dep/MANIFEST.yaml's runtime_log), not just the ones a
    # verification harness happens to capture into a check dict, WHEN
    # blueprint.dep is actually available (see the try/except above) --
    # None otherwise, and Bridge(..., event_sink=None) is itself a
    # normal, supported state (bridge.py stays decoupled, never imports
    # blueprint.dep itself); this is the one place that wires the two
    # together when both happen to be present, the same way it's the one
    # place that wires registry/policy/selector together regardless.
    event_log = RuntimeEventLog(_RUNTIME_ROOT.parent / "state" / "runtime-events.jsonl") if RuntimeEventLog is not None else None
    bridge = Bridge(registry, StaticPolicyEngine(), DeterministicSelector(), event_sink=(event_log.record if event_log is not None else None))
    # The Bridge is built before assembly runs: web.serve declares
    # executor_kind: factory, which needs a live Bridge to build its
    # Dependencies, even though the registry it wraps is still empty at
    # that instant (nothing reads it until real calls happen).
    assemble_from_catalog(_RUNTIME_ROOT / "capability-catalog.jsonl", registry, bridge=bridge)

    declared_raw = yaml.safe_load((app_dir / "dependencies.yaml").read_text(encoding="utf-8"))
    declared = _load_declared_dependencies(declared_raw.get("capabilities"))

    def resolve(name, operation):
        """Resolves the capability+operation declared under `name` in
        this app's own `dependencies.yaml`. Raises
        `BRIDGE_UNDECLARED_DEPENDENCY` if `name` isn't declared there.
        """
        spec = declared.get(name)
        if spec is None:
            raise BridgeError(
                "BRIDGE_UNDECLARED_DEPENDENCY", "validation",
                f"{name!r} is not declared in dependencies.yaml — add it there before depending on it",
            )
        kwargs = {}
        if spec["implementation_id"] is not None:
            kwargs["implementation_id"] = spec["implementation_id"]
        return bridge.resolve(spec["capability_id"], operation, spec["contract_version"], **kwargs)

    return resolve
