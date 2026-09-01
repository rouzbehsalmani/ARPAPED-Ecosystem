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

At scale, neither an agent deciding whether to reuse/compose/create (Phase 3
— Discover) nor the runtime bootstrap should have to walk and re-parse every
manifest and contract in the tree. This module also builds and consumes a
generated **capability catalog** (JSON Lines, one implementation per line;
see ``schemas/capability-catalog.schema.json``) for that: ``append_to_catalog``
(Publish-time, O(1) per newly published capability — never re-walks what
already exists), ``rebuild_catalog`` (a maintenance operation: initial
creation from a pre-existing tree, or recovery/compaction), and
``assemble_from_catalog`` (runtime bootstrap, reading the catalog instead of
walking ``capabilities/``). All three reuse ``from_manifest`` and
``_load_executor`` — no parsing logic is duplicated for the catalog path.

A capability's contract may declare ``dependencies.capabilities`` (R4) —
other capabilities it needs *live* access to during its own execution, not
just pre-computed input data from its caller. An implementation entry opts
into that by setting ``executor_kind: factory`` (default ``direct``,
unchanged behavior): its ``executor`` path is then a factory —
``(dependencies: Dependencies) -> Executor`` — called once, here, at
assembly time, instead of being used directly as the executor. The factory
resolves what it needs through the injected ``Dependencies`` (bridge.py),
which is scoped to exactly the capability ids this contract declared and
routes every call through the same canonical Bridge (R6/R8) — never a raw
executor-to-executor call. ``assemble``/``assemble_from_catalog`` verify the
declared dependency graph is acyclic before registering or invoking any
factory (R5).

A manifest's declared ``contract_version`` is never re-derived, only
cross-checked (R2): whenever a manifest is actually parsed from its source
files (every ``assemble`` call; every ``rebuild_catalog``/
``append_to_catalog``), ``from_manifest`` verifies it against the
contract's own current ``identity.version`` and ``versioning.compatibility``
policy — an implementation can never satisfy a contract version that
doesn't exist yet, and a version older than the contract's current one is
tolerated only as far as that policy allows. This is NOT re-checked from
the catalog's snapshotted data at runtime bootstrap (``assemble_from_catalog``
trusts the catalog as-is, same as domain/family/tags/dependencies).
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Iterator, Optional, Sequence

import yaml

from .registry import CapabilityImplementation, CapabilityRegistry, _version_tuple

if TYPE_CHECKING:
    from .bridge import Bridge

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
    executor_kind: str = "direct"
    dependencies: tuple[str, ...] = ()

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
        dependencies: tuple[str, ...] = (),
    ) -> "ManifestEntry":
        """Builds a typed entry from a raw capability-manifest ``implementations`` item.

        ``capability_id`` and ``contract_version`` come from the manifest level
        (per ``schemas/capability-manifest.schema.json``); ``entry`` is one item
        of its ``implementations`` list. ``domain``/``family``/``tags``/
        ``dependencies`` come from the referenced contract, when a ``root`` was
        given to ``assemble``.
        """

        if not isinstance(capability_id, str) or not capability_id.strip():
            raise AssemblerError("capability manifest must declare a non-empty 'capability_id'")
        if not isinstance(contract_version, str) or not contract_version.strip():
            raise AssemblerError("capability manifest must declare a non-empty 'contract_version'")

        implementation_id = entry.get("implementation_id")
        executor_path = entry.get("executor")
        operations = entry.get("operations")
        executor_kind = entry.get("executor_kind", "direct")

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
        if executor_kind not in ("direct", "factory"):
            raise AssemblerError(f"'executor_kind' must be 'direct' or 'factory', got {executor_kind!r}")

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
            executor_kind=executor_kind,
            dependencies=dependencies,
        )


@dataclass(frozen=True)
class ContractMetadata:
    """Everything the assembler reads from a manifest's referenced contract,
    never duplicated into the manifest itself (R2/R3). All fields default to
    empty/unset — the shape returned when ``root`` is omitted, in which case
    only Exact/Scoped discovery, a "direct" executor, and no version
    cross-check are available.
    """

    domain: str = ""
    family: str = ""
    tags: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    version: str = ""
    compatibility: str = ""


def _read_contract_metadata(manifest: dict[str, Any], root: Optional[Path]) -> ContractMetadata:
    """Resolves a manifest's ``contract`` path against ``root`` and reads its
    identity/discoverability/dependencies/versioning.

    Returns an empty ``ContractMetadata`` when ``root`` is omitted or the
    manifest has no ``contract`` path — Exact/Scoped discovery, and a
    "direct" executor, still work without this; only Family/Domain/
    Cross-domain discovery, a "factory" executor's declared dependencies,
    and the contract-version cross-check need it.
    """

    if root is None:
        return ContractMetadata()
    contract_path = manifest.get("contract")
    if not isinstance(contract_path, str) or not contract_path.strip():
        return ContractMetadata()

    resolved = root / contract_path
    try:
        contract_doc = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    except OSError as exc:
        raise AssemblerError(f"cannot read contract {resolved}: {exc}") from exc

    contract = (contract_doc or {}).get("contract", {})
    identity = contract.get("identity", {})
    discoverability = contract.get("discoverability", {})
    dependencies_block = contract.get("dependencies", {})
    versioning = contract.get("versioning", {}) or {}
    return ContractMetadata(
        domain=identity.get("domain", "") or "",
        family=identity.get("family", "") or "",
        tags=tuple(discoverability.get("tags", []) or ()),
        dependencies=tuple(dependencies_block.get("capabilities", []) or ()),
        version=identity.get("version", "") or "",
        compatibility=versioning.get("compatibility", "") or "",
    )


def _check_version_compatible(
    capability_id: str, contract_version: str, current_identity_version: str, compatibility: str
) -> None:
    """Raises ``AssemblerError`` if a manifest's declared ``contract_version``
    is not compatible with what the contract currently declares as its
    ``identity.version`` (R2): an implementation can never satisfy a
    contract version that doesn't exist yet, and a version older than the
    contract's current one is only tolerated when the contract's own
    ``versioning.compatibility`` policy allows it. Missing/unset
    compatibility defaults to ``"strict"`` — fail closed.

    Skipped entirely when ``current_identity_version`` is empty (no ``root``
    was given, or the contract declares no ``identity.version``) — the same
    escape hatch every other contract-dependent check in this module uses.
    """

    if not current_identity_version:
        return

    declared = _version_tuple(contract_version)
    current = _version_tuple(current_identity_version)
    if declared > current:
        raise AssemblerError(
            f"{capability_id!r} manifest declares contract_version {contract_version!r}, "
            f"newer than the contract's current identity.version {current_identity_version!r}"
        )
    if declared < current and (compatibility or "strict") == "strict":
        raise AssemblerError(
            f"{capability_id!r} manifest declares contract_version {contract_version!r}, but "
            f"the contract has moved to {current_identity_version!r} under a 'strict' "
            "versioning.compatibility policy — update the manifest"
        )


def from_manifest(manifest: dict[str, Any], *, root: Optional[Path] = None) -> list[ManifestEntry]:
    """Decodes one canonical capability manifest into its typed implementation entries.

    The canonical shape matches ``schemas/capability-manifest.schema.json``:
    a ``capability_id`` and ``contract_version`` at the manifest level, plus an
    ``implementations`` list — each item one implementation of that one
    contract. When ``root`` is given, each entry's ``domain``/``family``/
    ``tags``/``dependencies`` are read from the manifest's referenced contract.
    """

    capability_id = manifest.get("capability_id")
    contract_version = manifest.get("contract_version", manifest.get("version"))
    implementations = manifest.get("implementations")

    if not isinstance(implementations, list) or not implementations:
        raise AssemblerError("capability manifest must declare a non-empty 'implementations' list")

    metadata = _read_contract_metadata(manifest, root)
    if isinstance(contract_version, str) and contract_version.strip():
        # A missing/malformed contract_version is reported by
        # ManifestEntry.from_dict below, with its own clear message — this
        # check only runs once there is something meaningful to compare.
        _check_version_compatible(capability_id, contract_version, metadata.version, metadata.compatibility)

    return [
        ManifestEntry.from_dict(
            capability_id, contract_version, item,
            domain=metadata.domain, family=metadata.family,
            tags=metadata.tags, dependencies=metadata.dependencies,
        )
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


def _build_implementation(
    *,
    implementation_id: str,
    package_version: str,
    capability_id: str,
    contract_version: str,
    operations: tuple[str, ...],
    executor_path: str,
    priority: int,
    enabled: bool,
    healthy: bool,
    metadata: Optional[dict[str, Any]],
    domain: str,
    family: str,
    tags: tuple[str, ...],
    dependencies: tuple[str, ...],
    executor_kind: str,
    bridge: Optional["Bridge"],
) -> CapabilityImplementation:
    """Builds one Registry implementation record. Shared by the ``assemble``
    and ``assemble_from_catalog`` entry points — the only place either one
    constructs a ``CapabilityImplementation``.

    ``executor_kind: "direct"`` (default): the loaded callable IS the
    executor, unchanged from every implementation before this existed.
    ``executor_kind: "factory"``: the loaded callable is invoked ONCE, here,
    with a ``Dependencies`` scoped to ``dependencies`` (R4) — its return
    value becomes the executor. Requires ``bridge`` (fail closed otherwise):
    a factory with no Bridge to resolve its dependencies through can't do
    its job.
    """

    raw = _load_executor(executor_path)
    if executor_kind == "factory":
        if bridge is None:
            raise AssemblerError(
                f"{implementation_id!r} declares executor_kind='factory' but no Bridge was "
                "given to build its Dependencies — construct the Bridge before assembling "
                "(see app/requests.py's ordering)"
            )
        from .bridge import Dependencies

        executor = raw(Dependencies(bridge, frozenset(dependencies)))
        if not callable(executor):
            raise AssemblerError(
                f"executor factory {executor_path!r} must return a callable executor, "
                f"got {type(executor).__name__}"
            )
    else:
        executor = raw

    return CapabilityImplementation(
        implementation_id=implementation_id,
        package_version=package_version,
        capability_id=capability_id,
        contract_version=contract_version,
        operations=operations,
        executor=executor,
        priority=priority,
        enabled=enabled,
        healthy=healthy,
        metadata=metadata,
        domain=domain,
        family=family,
        tags=tags,
    )


def _to_implementation(entry: ManifestEntry, *, bridge: Optional["Bridge"] = None) -> CapabilityImplementation:
    """Builds a Registry implementation record from a validated manifest entry."""

    return _build_implementation(
        implementation_id=entry.implementation_id,
        package_version=entry.package_version,
        capability_id=entry.capability_id,
        contract_version=entry.contract_version,
        operations=entry.operations,
        executor_path=entry.executor_path,
        priority=entry.priority,
        enabled=entry.enabled,
        healthy=entry.healthy,
        metadata=entry.metadata,
        domain=entry.domain,
        family=entry.family,
        tags=entry.tags,
        dependencies=entry.dependencies,
        executor_kind=entry.executor_kind,
        bridge=bridge,
    )


def _check_no_dependency_cycles(graph: dict[str, tuple[str, ...]]) -> None:
    """Raises ``AssemblerError`` naming the cycle if the declared
    ``capability_id -> dependencies`` graph is not acyclic (R4/R5). Only
    capability ids present as keys are graph nodes; a dependency on a
    capability_id outside this assembly batch is a leaf (nothing further to
    walk) — cross-batch cycles are still caught eventually, since
    ``assemble_from_catalog`` builds this graph from the WHOLE catalog.
    """

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {capability_id: WHITE for capability_id in graph}
    path: list[str] = []

    def visit(capability_id: str) -> None:
        color[capability_id] = GRAY
        path.append(capability_id)
        for dependency in graph.get(capability_id, ()):
            state = color.get(dependency)
            if state == GRAY:
                cycle = path[path.index(dependency):] + [dependency]
                raise AssemblerError("dependency cycle detected: " + " -> ".join(cycle))
            if state == WHITE:
                visit(dependency)
        path.pop()
        color[capability_id] = BLACK

    for capability_id in graph:
        if color[capability_id] == WHITE:
            visit(capability_id)


def assemble(
    manifest: dict[str, Any] | Iterable[dict[str, Any]],
    registry: CapabilityRegistry,
    *,
    root: Optional[Path] = None,
    bridge: Optional["Bridge"] = None,
) -> list[str]:
    """Assembles every declared implementation into the canonical Registry.

    Accepts a single capability manifest (per
    ``schemas/capability-manifest.schema.json``) or an iterable of capability
    manifests. Returns the registered implementation ids.

    ``root``, when given, is used to resolve each manifest's ``contract``
    path so the assembler can attach that contract's domain/family/tags/
    dependencies to the registered implementation, enabling Family/Domain/
    Cross-domain discovery (2-RULES.md "Registry contract") and
    ``executor_kind: factory`` entries. Omitting it keeps prior behavior
    unchanged. ``bridge`` is required only if any entry is factory-kind.

    Fail closed: if any implementation cannot be imported or registered, or
    the declared dependency graph has a cycle, an ``AssemblerError`` is
    raised and nothing is partially accepted.
    """

    entries = _collect_entries(manifest, root=root)
    if not entries:
        raise AssemblerError("no implementations declared in the manifest(s)")

    _check_no_dependency_cycles({entry.capability_id: entry.dependencies for entry in entries})

    registered: list[str] = []
    for entry in entries:
        implementation = _to_implementation(entry, bridge=bridge)
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


def _read_contract_description(manifest: dict[str, Any], root: Path) -> str:
    """Reads a manifest's contract's ``responsibility.description``, for the
    catalog's ``description`` field only (agent keyword-search relevance) —
    never consumed by ``from_manifest`` or registration itself.
    """

    contract_path = manifest.get("contract") if isinstance(manifest, dict) else None
    if not isinstance(contract_path, str) or not contract_path.strip():
        return ""
    try:
        contract_doc = yaml.safe_load((root / contract_path).read_text(encoding="utf-8"))
    except OSError:
        return ""
    contract = (contract_doc or {}).get("contract", {})
    return contract.get("responsibility", {}).get("description", "") or ""


def _manifest_records(manifest_path: Path, repo_root: Path) -> Iterator[dict[str, Any]]:
    """Parses one manifest file (and the contract it references) into catalog
    records. The shared unit ``append_to_catalog`` and ``rebuild_catalog``
    both build on — parsing logic lives once, in ``from_manifest``/
    ``_read_contract_metadata``.
    """

    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    entries = from_manifest(manifest, root=repo_root)
    description = _read_contract_description(manifest, repo_root)
    contract_path = manifest.get("contract", "") if isinstance(manifest, dict) else ""
    try:
        manifest_rel = manifest_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        manifest_rel = manifest_path.as_posix()

    for entry in entries:
        yield {
            "implementation_id": entry.implementation_id,
            "capability_id": entry.capability_id,
            "package_version": entry.package_version,
            "contract_version": entry.contract_version,
            "operations": list(entry.operations),
            "executor_path": entry.executor_path,
            "priority": entry.priority,
            "enabled": entry.enabled,
            "healthy": entry.healthy,
            "metadata": entry.metadata,
            "domain": entry.domain,
            "family": entry.family,
            "tags": list(entry.tags),
            "dependencies": list(entry.dependencies),
            "executor_kind": entry.executor_kind,
            "description": description,
            "manifest_path": manifest_rel,
            "contract_path": contract_path,
        }


def append_to_catalog(catalog_path: Path, manifest_path: Path, repo_root: Path) -> list[str]:
    """Appends one manifest's implementation record(s) to an existing catalog
    (Phase 8, Publish). Cost is independent of how large the catalog already
    is: only ``manifest_path`` (and the one contract it references) is read —
    nothing already in the catalog is re-read or re-walked. This is what a
    growing ecosystem calls once per newly published capability; see
    ``rebuild_catalog`` for full regeneration.
    """

    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    appended: list[str] = []
    with catalog_path.open("a", encoding="utf-8") as f:
        for record in _manifest_records(manifest_path, repo_root):
            f.write(json.dumps(record, sort_keys=True))
            f.write("\n")
            appended.append(record["implementation_id"])
    return appended


def rebuild_catalog(capabilities_root: Path, repo_root: Path, catalog_path: Path) -> int:
    """Regenerates the whole catalog from scratch by walking
    ``capabilities_root`` once. A maintenance operation — initial creation
    from a pre-existing tree, or recovery/compaction — not something a
    per-capability publish should call; see ``append_to_catalog`` for that.

    Fail closed: a duplicate ``implementation_id`` across the tree raises
    ``AssemblerError`` rather than silently overwriting a catalog line.
    """

    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    seen_ids: set[str] = set()
    count = 0
    with catalog_path.open("w", encoding="utf-8") as f:
        for manifest_path in sorted(capabilities_root.rglob("manifest.yaml")):
            for record in _manifest_records(manifest_path, repo_root):
                implementation_id = record["implementation_id"]
                if implementation_id in seen_ids:
                    raise AssemblerError(
                        f"duplicate implementation_id {implementation_id!r} while rebuilding catalog"
                    )
                seen_ids.add(implementation_id)
                f.write(json.dumps(record, sort_keys=True))
                f.write("\n")
                count += 1
    return count


def assemble_from_catalog(
    catalog_path: Path, registry: CapabilityRegistry, *, bridge: Optional["Bridge"] = None
) -> list[str]:
    """Registers every implementation from a generated catalog (see
    ``append_to_catalog``/``rebuild_catalog``) instead of walking and
    re-parsing ``capabilities/`` at every startup. Trusts the catalog as-is —
    it does not re-derive domain/family/tags/dependencies from contracts
    itself. ``bridge`` is required only if any record is factory-kind.

    Fail closed: a missing catalog, a dependency cycle across the whole
    catalog, or a factory-kind record with no ``bridge`` all raise
    ``AssemblerError`` before anything is registered.
    """

    if not catalog_path.exists():
        raise AssemblerError(
            f"capability catalog not found at {catalog_path}; generate it first "
            "(see append_to_catalog/rebuild_catalog in bridge/assembler.py)"
        )

    records: list[dict[str, Any]] = []
    with catalog_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    _check_no_dependency_cycles(
        {record["capability_id"]: tuple(record.get("dependencies", ())) for record in records}
    )

    registered: list[str] = []
    for record in records:
        implementation = _build_implementation(
            implementation_id=record["implementation_id"],
            package_version=record["package_version"],
            capability_id=record["capability_id"],
            contract_version=record["contract_version"],
            operations=tuple(record["operations"]),
            executor_path=record["executor_path"],
            priority=record.get("priority", 100),
            enabled=record.get("enabled", True),
            healthy=record.get("healthy", True),
            metadata=record.get("metadata"),
            domain=record.get("domain", ""),
            family=record.get("family", ""),
            tags=tuple(record.get("tags", ())),
            dependencies=tuple(record.get("dependencies", ())),
            executor_kind=record.get("executor_kind", "direct"),
            bridge=bridge,
        )
        registry.register(implementation)
        registered.append(implementation.implementation_id)
    return registered
