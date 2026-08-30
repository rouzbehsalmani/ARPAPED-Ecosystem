"""Generic, product-agnostic assembler for the ARPAPED self-improving cycle.

The assembler is the Publish-phase (Phase 8) helper that reads capability
manifests and builds implementation records into the canonical Registry. It is
the ONLY place that constructs implementation records.

The assembler contains no capability identity, no component name, and no
product reference. Everything it needs arrives as manifest data:

    capability manifest (validated)
              |
              v
        import executor (module:attr)
              |
              v
        CapabilityImplementation
              |
              v
        registry.register(...)

Components remain registration-unaware executors, and swapping a component
requires editing the manifest, never consumer code.

When given a ``root`` (see ``assemble``), the assembler additionally resolves
each manifest's ``contract`` path against it and reads that contract's
``identity.domain``, ``identity.family``, and ``discoverability.tags`` — the
source of truth for those fields is always the contract (R2/R3), never the
manifest. This is what makes Family/Domain/Cross-domain discovery possible
(2-RULES.md "Registry contract"); omitting ``root`` keeps prior behavior
unchanged (Exact/Scoped discovery only).
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

import yaml

from .registry import CapabilityImplementation, CapabilityRegistry

#: Executor reference format, e.g. "package.module:execute".
_EXECUTOR_SPLIT = ":"


class AssemblerError(Exception):
    """Raised when a capability manifest cannot be assembled."""


@dataclass(frozen=True)
class ManifestEntry:
    """One capability-manifest implementation: an executor bound to one contract."""

    capability_id: str
    implementation_id: str
    package_version: str
    contract_version: str
    operations: tuple[str, ...]
    executor_path: str
    priority: int = 100
    enabled: bool = True
    healthy: bool = True
    metadata: Optional[dict[str, Any]] = None
    domain: str = ""
    family: str = ""
    tags: tuple[str, ...] = ()

    @classmethod
    def from_dict(
        cls,
        capability_id: str,
        contract_version: str,
        entry: dict[str, Any],
        *,
        domain: str = "",
        family: str = "",
        tags: tuple[str, ...] = (),
    ) -> "ManifestEntry":
        """Builds a typed entry from a raw capability-manifest ``implementations`` item.

        ``capability_id`` and ``contract_version`` come from the manifest level
        (per ``schemas/capability-manifest.schema.json``); ``entry`` is one item
        of its ``implementations`` list. ``domain``/``family``/``tags`` come
        from the referenced contract, when a ``root`` was given to ``assemble``.
        """

        if not isinstance(capability_id, str) or not capability_id.strip():
            raise AssemblerError("capability manifest must declare a non-empty 'capability_id'")
        if not isinstance(contract_version, str) or not contract_version.strip():
            raise AssemblerError("capability manifest must declare a non-empty 'contract_version'")

        implementation_id = entry.get("implementation_id")
        executor_path = entry.get("executor")
        operations = entry.get("operations")

        if not isinstance(implementation_id, str) or not implementation_id.strip():
            raise AssemblerError("an implementation entry must declare a non-empty 'implementation_id'")
        if not isinstance(executor_path, str) or not executor_path.strip():
            raise AssemblerError(f"an implementation must declare an 'executor' module:attr path, got {executor_path!r}")
        if _EXECUTOR_SPLIT not in executor_path:
            raise AssemblerError(f"executor must be 'module:attr', got {executor_path!r}")
        if not isinstance(operations, list) or not operations or not all(
            isinstance(op, str) and op.strip() for op in operations
        ):
            raise AssemblerError("an implementation entry must declare a non-empty 'operations' list")

        package_version = entry.get("version", contract_version)
        if not isinstance(package_version, str) or not package_version.strip():
            package_version = contract_version

        if "enabled" in entry and not isinstance(entry["enabled"], bool):
            raise AssemblerError("'enabled' must be a boolean")
        if "healthy" in entry and not isinstance(entry["healthy"], bool):
            raise AssemblerError("'healthy' must be a boolean")

        return cls(
            capability_id=capability_id.strip(),
            implementation_id=implementation_id.strip(),
            package_version=package_version.strip(),
            contract_version=contract_version.strip(),
            operations=tuple(op.strip() for op in operations),
            executor_path=executor_path.strip(),
            priority=int(entry.get("priority", 100)),
            enabled=bool(entry.get("enabled", True)),
            healthy=bool(entry.get("healthy", True)),
            metadata=entry.get("metadata"),
            domain=domain,
            family=family,
            tags=tags,
        )


def _read_contract_identity(manifest: dict[str, Any], root: Optional[Path]) -> tuple[str, str, tuple[str, ...]]:
    """Resolves a manifest's ``contract`` path against ``root`` and reads its identity/discoverability.

    Returns ``("", "", ())`` when ``root`` is omitted or the manifest has no
    ``contract`` path — Exact/Scoped discovery still work without this; only
    Family/Domain/Cross-domain need it.
    """

    if root is None:
        return "", "", ()
    contract_path = manifest.get("contract")
    if not isinstance(contract_path, str) or not contract_path.strip():
        return "", "", ()

    resolved = root / contract_path
    try:
        contract_doc = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    except OSError as exc:
        raise AssemblerError(f"cannot read contract {resolved}: {exc}") from exc

    contract = (contract_doc or {}).get("contract", {})
    identity = contract.get("identity", {})
    discoverability = contract.get("discoverability", {})
    domain = identity.get("domain", "") or ""
    family = identity.get("family", "") or ""
    tags = tuple(discoverability.get("tags", []) or ())
    return domain, family, tags


def from_manifest(manifest: dict[str, Any], *, root: Optional[Path] = None) -> list[ManifestEntry]:
    """Decodes one canonical capability manifest into its typed implementation entries.

    The canonical shape matches ``schemas/capability-manifest.schema.json``:
    a ``capability_id`` and ``contract_version`` at the manifest level, plus an
    ``implementations`` list — each item one implementation of that one
    contract. When ``root`` is given, each entry's ``domain``/``family``/
    ``tags`` are read from the manifest's referenced contract.
    """

    capability_id = manifest.get("capability_id")
    contract_version = manifest.get("contract_version", manifest.get("version"))
    implementations = manifest.get("implementations")

    if not isinstance(implementations, list) or not implementations:
        raise AssemblerError("capability manifest must declare a non-empty 'implementations' list")

    domain, family, tags = _read_contract_identity(manifest, root)

    return [
        ManifestEntry.from_dict(capability_id, contract_version, item, domain=domain, family=family, tags=tags)
        for item in implementations
        if isinstance(item, dict)
    ]


def _load_executor(executor_path: str):
    """Returns the callable referenced by a 'module:attr' executor path."""

    try:
        module_name, attribute = executor_path.split(_EXECUTOR_SPLIT, 1)
    except ValueError:
        raise AssemblerError(f"invalid executor path {executor_path!r}") from None
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise AssemblerError(f"cannot import executor module {module_name!r}: {exc}") from exc
    if not hasattr(module, attribute):
        raise AssemblerError(
            f"executor module {module_name!r} has no attribute {attribute!r}"
        )
    executor = getattr(module, attribute)
    if not callable(executor):
        raise AssemblerError(f"executor {executor_path!r} is not callable")
    return executor


def _to_implementation(entry: ManifestEntry) -> CapabilityImplementation:
    """Builds a Registry implementation record from a validated manifest entry."""

    return CapabilityImplementation(
        implementation_id=entry.implementation_id,
        package_version=entry.package_version,
        capability_id=entry.capability_id,
        contract_version=entry.contract_version,
        operations=entry.operations,
        executor=_load_executor(entry.executor_path),
        priority=entry.priority,
        enabled=entry.enabled,
        healthy=entry.healthy,
        metadata=entry.metadata,
        domain=entry.domain,
        family=entry.family,
        tags=entry.tags,
    )


def assemble(
    manifest: dict[str, Any] | Iterable[dict[str, Any]],
    registry: CapabilityRegistry,
    *,
    root: Optional[Path] = None,
) -> list[str]:
    """Assembles every declared implementation into the canonical Registry.

    Accepts a single capability manifest (per
    ``schemas/capability-manifest.schema.json``) or an iterable of capability
    manifests. Returns the registered implementation ids.

    ``root``, when given, is used to resolve each manifest's ``contract``
    path so the assembler can attach that contract's domain/family/tags to
    the registered implementation, enabling Family/Domain/Cross-domain
    discovery (2-RULES.md "Registry contract"). Omitting it keeps prior
    behavior unchanged.

    Fail closed: if any implementation cannot be imported or registered, an
    ``AssemblerError`` is raised and nothing is partially accepted.
    """

    entries = _collect_entries(manifest, root=root)
    if not entries:
        raise AssemblerError("no implementations declared in the manifest(s)")

    registered: list[str] = []
    for entry in entries:
        implementation = _to_implementation(entry)
        registry.register(implementation)
        registered.append(implementation.implementation_id)
    return registered


def _collect_entries(
    manifest: dict[str, Any] | Iterable[dict[str, Any]],
    *,
    root: Optional[Path] = None,
) -> list[ManifestEntry]:
    """Normalizes a manifest (or iterable of manifests) into typed entries.

    Each input element is a canonical capability manifest carrying a
    ``capability_id`` and ``implementations`` list (see
    ``schemas/capability-manifest.schema.json``).
    """

    manifests: list[dict[str, Any]] = []
    if isinstance(manifest, dict):
        manifests = [manifest]
    else:
        for item in manifest:
            if not isinstance(item, dict):
                raise AssemblerError(f"unexpected manifest element {type(item).__name__}")
            manifests.append(item)

    entries: list[ManifestEntry] = []
    for item in manifests:
        entries.extend(from_manifest(item, root=root))
    return entries
