"""Generic, product-agnostic assembler for the ARPAPED self-improving
cycle (Publish phase, Phase 8) -- the only place that constructs
implementation records, from manifest data alone (no capability
identity, component name, or product reference of its own). Swapping a
component means editing the manifest, never consumer code.

With a ``root``, also resolves each manifest's contract path and reads
identity.domain/family and discoverability.tags -- the source of truth
for Family/Domain/Cross-domain discovery (2-RULES.md "Registry
contract"); omitting root limits discovery to Exact/Scoped.

Builds and consumes a generated capability catalog (JSON Lines, one
implementation per line; schemas/capability-catalog.schema.json) so
neither Discover-phase reasoning nor runtime bootstrap has to re-walk
every manifest: ``append_to_catalog`` (O(1) per publish),
``rebuild_catalog`` (full rewalk -- initial creation or recovery),
``assemble_from_catalog`` (runtime bootstrap). All three share
``from_manifest``/``_load_executor``.

``executor_kind: process``: ``executor`` names a program instead of a
``module:attr`` path; spawned once, here, into a ``ProcessExecutorPool``
(bridge/process_executor.py), which becomes the executor -- lets a
capability be implemented in another language, invisibly to the rest of
the Bridge.

``executor_kind: factory``: for a contract declaring
``dependencies.capabilities`` (R4 -- live access during execution, not
just input data), ``executor`` is instead ``(dependencies: Dependencies)
-> Executor``, called once, here, at assembly time, resolving through
the injected ``Dependencies`` (scoped to exactly the declared capability
ids, routing every call through the canonical Bridge, R6/R8). The
declared dependency graph is verified acyclic before registering or
invoking any factory (R5).

``contract_version`` is cross-checked, never re-derived (R2): every
real parse (``assemble``, ``rebuild_catalog``, ``append_to_catalog``)
verifies it names a currently alive version in the contract's
``versions``, and that each declared operation actually belongs to that
version. Not re-checked from the catalog's snapshotted data at runtime
bootstrap.
"""

from __future__ import annotations

import importlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Iterator, Optional, Sequence

import yaml

from .registry import INPUT_TYPE_CHECKS, CapabilityImplementation, CapabilityRegistry, InputField

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
    executor_path: str | tuple[str, ...]
    priority: int
    enabled: bool = True
    healthy: bool = True
    metadata: Optional[dict[str, Any]] = None
    domain: str = ""
    family: str = ""
    tags: tuple[str, ...] = ()
    executor_kind: str = "direct"
    dependencies: dict[str, str] = field(default_factory=dict)
    input_schema: dict[str, tuple[InputField, ...]] = field(default_factory=dict)

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
        dependencies: Optional[dict[str, str]] = None,
        operation_input_fields: Optional[dict[str, tuple[InputField, ...]]] = None,
    ) -> "ManifestEntry":
        """Builds a typed entry from a raw capability-manifest ``implementations`` item.

        ``capability_id`` and ``contract_version`` come from the manifest level
        (per ``schemas/capability-manifest.schema.json``); ``entry`` is one item
        of its ``implementations`` list. ``domain``/``family``/``tags``/
        ``dependencies``/``operation_input_fields`` come from the referenced
        contract, when a ``root`` was given to ``assemble`` —
        ``operation_input_fields`` is every operation this CONTRACT_VERSION
        declares; this entry's own ``input_schema`` is sliced down to just
        the operations it actually declares, below.
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
        if executor_kind not in ("direct", "factory", "process"):
            raise AssemblerError(f"'executor_kind' must be 'direct', 'factory', or 'process', got {executor_kind!r}")
        if executor_kind in ("direct", "factory"):
            if not isinstance(executor_path, str) or not executor_path.strip():
                raise AssemblerError(f"an implementation must declare a non-empty 'executor', got {executor_path!r}")
            if _EXECUTOR_SPLIT not in executor_path:
                raise AssemblerError(f"executor must be 'module:attr' for executor_kind {executor_kind!r}, got {executor_path!r}")
            executor_path = executor_path.strip()
        else:
            # 'process': a single command string (e.g. a compiled binary),
            # or an argv list when an interpreter and a script are both
            # needed (e.g. an interpreted language) -- see
            # bridge/process_executor.py.
            if isinstance(executor_path, str) and executor_path.strip():
                executor_path = executor_path.strip()
            elif (
                isinstance(executor_path, list) and executor_path
                and all(isinstance(part, str) and part.strip() for part in executor_path)
            ):
                executor_path = tuple(part.strip() for part in executor_path)
            else:
                raise AssemblerError(
                    "an implementation must declare a non-empty 'executor' string or list of "
                    f"strings for executor_kind 'process', got {executor_path!r}"
                )
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
        priority = entry.get("priority")
        if not isinstance(priority, int) or isinstance(priority, bool):
            raise AssemblerError(
                "an implementation entry must declare an integer 'priority' — no default; "
                "higher number = higher precedence (schemas/capability-manifest.schema.json)"
            )

        stripped_operations = tuple(op.strip() for op in operations)
        input_schema = {
            op: (operation_input_fields or {}).get(op, ())
            for op in stripped_operations
        }

        return cls(
            capability_id=capability_id.strip(),
            implementation_id=implementation_id.strip(),
            package_version=package_version.strip(),
            contract_version=contract_version.strip(),
            operations=stripped_operations,
            executor_path=executor_path,
            priority=priority,
            enabled=bool(entry.get("enabled", True)),
            healthy=bool(entry.get("healthy", True)),
            metadata=entry.get("metadata"),
            domain=domain,
            family=family,
            tags=tags,
            executor_kind=executor_kind,
            dependencies=dependencies or {},
            input_schema=input_schema,
        )


@dataclass(frozen=True)
class ContractMetadata:
    """Everything the assembler reads from a manifest's referenced contract,
    never duplicated into the manifest itself (R2/R3). All fields default to
    empty/unset — the shape returned when ``root`` is omitted, in which case
    only Exact/Scoped discovery, a "direct" executor, and no version
    cross-check are available.

    ``operation_input_fields``: ``{version: {operation: (InputField, ...)}}``
    — every declared operation's input shape, across every version, so
    ``from_manifest`` can slice out just the operations one implementation
    entry actually declares. Consumed by the resolved Bridge
    (``bridge/bridge.py``) to validate a request's input, and fill in any
    declared default, before any executor runs, in any language — the
    same duty a hand-written per-executor check used to carry alone.
    """

    domain: str = ""
    family: str = ""
    tags: tuple[str, ...] = ()
    dependencies: dict[str, str] = field(default_factory=dict)
    version: str = ""
    versions_operations: dict[str, frozenset[str]] = field(default_factory=dict)
    dead_versions: frozenset[str] = frozenset()
    operation_input_fields: dict[str, dict[str, tuple[InputField, ...]]] = field(default_factory=dict)


def parse_dependencies(raw: Any) -> dict[str, str]:
    """Decodes a ``dependencies.capabilities``-shaped list into
    ``{capability_id: contract_version}``. A bare string is shorthand for
    ``"*"`` (any registered version, today's only form); an object pins the
    version constraint the declaring side actually depends on (see
    ``schemas/component-contract.schema.json``). Malformed entries are
    skipped rather than raising — schema validation is what enforces shape;
    this is a best-effort read, same posture as the rest of this function.

    Shared by two callers: a capability contract's own
    ``dependencies.capabilities`` (read here, by ``_read_contract_metadata``)
    and an application's own declared-dependencies file for its single
    request-construction point (see ``bridge/bridge.py``'s ``Dependencies``)
    — both use the identical shape, so this decoding logic lives once.
    """

    dependencies: dict[str, str] = {}
    for item in raw or ():
        if isinstance(item, str) and item.strip():
            dependencies[item] = "*"
        elif isinstance(item, dict) and isinstance(item.get("capability_id"), str):
            dependencies[item["capability_id"]] = item.get("contract_version", "*") or "*"
    return dependencies


def _build_input_field(capability_id: str, version: str, operation: str, raw: dict[str, Any]) -> InputField:
    """Builds one `InputField` from a contract's raw `input[]` entry
    (schemas/component-contract.schema.json), failing closed on a
    declaration that could never be honored correctly at runtime rather
    than letting it surface later as a confusing bug:

    - `required: true` together with a `default` is contradictory -- a
      required field's absence is already an error, so its default could
      never actually be reached.
    - A declared `default` whose own type doesn't match the field's
      declared `type` (checked via the same `INPUT_TYPE_CHECKS` the
      Bridge uses at request time) would fail Bridge-side validation the
      instant some caller omitted the field -- caught here, at assembly
      time, instead.
    - `minLength`/`maxLength` only make sense for `type: "string"`, and
      `minLength` may not exceed `maxLength`; a declared `default` string
      shorter/longer than either is the same "would immediately fail the
      Bridge's own check" contradiction.
    - Every value in a declared `enum` must itself match the field's
      `type` -- same reasoning as `default`'s type check. A declared
      `default` that isn't itself one of the `enum` values is also
      contradictory: the Bridge would fill it in and then immediately
      fail its own enum check.
    - `pattern` only makes sense for `type: "string"`, must itself
      compile as a regular expression, and a declared `default` must
      match it -- same "would immediately fail the Bridge's own check"
      reasoning as the other constraints.
    """

    name = raw["name"]
    type_ = raw["type"]
    required = bool(raw.get("required", False))
    has_default = "default" in raw
    default = raw.get("default")
    min_length = raw.get("minLength")
    max_length = raw.get("maxLength")
    enum_values = tuple(raw["enum"]) if "enum" in raw else None
    pattern = raw.get("pattern")

    where = f"{capability_id!r} contract_version {version!r} operation {operation!r} field {name!r}"
    if has_default and required:
        raise AssemblerError(f"{where} declares both 'required: true' and a 'default' -- the default could never be reached")
    if has_default:
        check = INPUT_TYPE_CHECKS.get(type_)
        if check is not None and not check(default):
            raise AssemblerError(f"{where} declares a 'default' that does not match its own 'type': {type_!r}, got {default!r}")
    if (min_length is not None or max_length is not None) and type_ != "string":
        raise AssemblerError(f"{where} declares 'minLength'/'maxLength', which only apply to 'type: string', got {type_!r}")
    if min_length is not None and max_length is not None and min_length > max_length:
        raise AssemblerError(f"{where} declares 'minLength' ({min_length}) greater than 'maxLength' ({max_length})")
    if has_default and isinstance(default, str):
        if min_length is not None and len(default) < min_length:
            raise AssemblerError(f"{where} declares a 'default' shorter than its own 'minLength' ({min_length})")
        if max_length is not None and len(default) > max_length:
            raise AssemblerError(f"{where} declares a 'default' longer than its own 'maxLength' ({max_length})")
    if enum_values is not None:
        check = INPUT_TYPE_CHECKS.get(type_)
        if check is not None:
            mismatched = [v for v in enum_values if not check(v)]
            if mismatched:
                raise AssemblerError(f"{where} declares 'enum' value(s) {mismatched!r} that do not match its own 'type': {type_!r}")
        if has_default and default not in enum_values:
            raise AssemblerError(f"{where} declares a 'default' ({default!r}) that is not one of its own 'enum' values {list(enum_values)!r}")
    compiled_pattern = None
    if pattern is not None:
        if type_ != "string":
            raise AssemblerError(f"{where} declares 'pattern', which only applies to 'type: string', got {type_!r}")
        try:
            compiled_pattern = re.compile(pattern)
        except re.error as exc:
            raise AssemblerError(f"{where} declares 'pattern' {pattern!r} that does not compile as a regular expression: {exc}") from exc
        if has_default and isinstance(default, str) and not compiled_pattern.search(default):
            raise AssemblerError(f"{where} declares a 'default' ({default!r}) that does not match its own 'pattern' {pattern!r}")

    return InputField(
        name=name, type=type_, required=required, has_default=has_default, default=default,
        min_length=min_length, max_length=max_length, enum_values=enum_values, pattern=pattern,
    )


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
    versions_block = contract.get("versions", {}) or {}
    history_block = contract.get("lineage", {}).get("history", []) or []

    identity_id = identity.get("id", "<unknown capability>")
    versions_operations: dict[str, frozenset[str]] = {}
    operation_input_fields: dict[str, dict[str, tuple[InputField, ...]]] = {}
    for version, entry in versions_block.items():
        operations = (entry or {}).get("operations", []) or []
        versions_operations[version] = frozenset(
            op["name"] for op in operations if isinstance(op, dict) and isinstance(op.get("name"), str)
        )
        fields_by_operation: dict[str, tuple[InputField, ...]] = {}
        for op in operations:
            if not isinstance(op, dict) or not isinstance(op.get("name"), str):
                continue
            fields_by_operation[op["name"]] = tuple(
                _build_input_field(identity_id, version, op["name"], f)
                for f in (op.get("input", []) or [])
                if isinstance(f, dict) and isinstance(f.get("name"), str) and isinstance(f.get("type"), str)
            )
        operation_input_fields[version] = fields_by_operation
    dead_versions = frozenset(
        item["version"] for item in history_block if isinstance(item, dict) and isinstance(item.get("version"), str)
    )

    current_version = identity.get("version", "") or ""
    if current_version and versions_operations and current_version not in versions_operations:
        raise AssemblerError(
            f"contract identity.version {current_version!r} is not itself a key in this "
            "contract's 'versions' — the default version must structurally exist"
        )

    return ContractMetadata(
        domain=identity.get("domain", "") or "",
        family=identity.get("family", "") or "",
        tags=tuple(discoverability.get("tags", []) or ()),
        dependencies=parse_dependencies(dependencies_block.get("capabilities")),
        version=current_version,
        versions_operations=versions_operations,
        dead_versions=dead_versions,
        operation_input_fields=operation_input_fields,
    )


def _check_declared_version_alive(
    capability_id: str, contract_version: str, versions_operations: dict[str, frozenset[str]], dead_versions: frozenset[str]
) -> None:
    """Raises ``AssemblerError`` if a manifest's declared ``contract_version``
    is not a currently supported (alive) version of its contract (R2): it
    must be a key in the contract's ``versions`` — never merely "older" or
    "newer" than some current one, since every alive version is a peer, not
    a numeric comparison. A version recorded in ``lineage.history`` is dead:
    no implementation may declare it, and the error says so explicitly,
    distinct from a version that was never recognized at all.
    """

    if contract_version in versions_operations:
        return
    if contract_version in dead_versions:
        raise AssemblerError(
            f"{capability_id!r} manifest declares contract_version {contract_version!r}, which "
            "this contract's lineage.history records as retired (dead) — no implementation may use it"
        )
    raise AssemblerError(
        f"{capability_id!r} manifest declares contract_version {contract_version!r}, which is not "
        "a currently supported version of this contract (see its 'versions')"
    )


def _check_operations_declared(
    capability_id: str, contract_version: str, operations: tuple[str, ...], valid_operations: frozenset[str]
) -> None:
    """Raises ``AssemblerError`` if an implementation entry declares an
    operation that was never actually recorded for the contract_version it
    claims — catches a manifest whose declared operations don't match what
    that specific, alive version's interface really contains.
    """

    unknown = [op for op in operations if op not in valid_operations]
    if unknown:
        raise AssemblerError(
            f"{capability_id!r} manifest declares operation(s) {unknown!r} not present in "
            f"contract_version {contract_version!r}'s recorded interface"
        )


def from_manifest(manifest: dict[str, Any], *, root: Optional[Path] = None) -> list[ManifestEntry]:
    """Decodes one canonical capability manifest into its typed implementation entries.

    The canonical shape matches ``schemas/capability-manifest.schema.json``:
    a ``capability_id`` and ``contract_version`` at the manifest level, plus an
    ``implementations`` list — each item one implementation of that one
    contract. When ``root`` is given, each entry's ``domain``/``family``/
    ``tags``/``dependencies``/``input_schema`` are read from the manifest's
    referenced contract.
    """

    capability_id = manifest.get("capability_id")
    contract_version = manifest.get("contract_version", manifest.get("version"))
    implementations = manifest.get("implementations")

    if not isinstance(implementations, list) or not implementations:
        raise AssemblerError("capability manifest must declare a non-empty 'implementations' list")

    metadata = _read_contract_metadata(manifest, root)
    operation_input_fields = metadata.operation_input_fields.get(contract_version, {})

    entries = [
        ManifestEntry.from_dict(
            capability_id, contract_version, item,
            domain=metadata.domain, family=metadata.family,
            tags=metadata.tags, dependencies=metadata.dependencies,
            operation_input_fields=operation_input_fields,
        )
        for item in implementations
        if isinstance(item, dict)
    ]

    # A missing/malformed contract_version is reported by ManifestEntry.from_dict
    # above, with its own clear message — these checks only run once there is
    # something meaningful to compare, and only when a root actually gave us
    # contract data (metadata.version is the same empty-means-no-data signal
    # used throughout this module).
    if isinstance(contract_version, str) and contract_version.strip() and metadata.version:
        _check_declared_version_alive(capability_id, contract_version, metadata.versions_operations, metadata.dead_versions)
        valid_operations = metadata.versions_operations[contract_version]
        for entry in entries:
            _check_operations_declared(capability_id, contract_version, entry.operations, valid_operations)

    return entries


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
    executor_path: str | Sequence[str],
    priority: int,
    enabled: bool,
    healthy: bool,
    metadata: Optional[dict[str, Any]],
    domain: str,
    family: str,
    tags: tuple[str, ...],
    dependencies: dict[str, str],
    executor_kind: str,
    bridge: Optional["Bridge"],
    input_schema: Optional[dict[str, tuple[InputField, ...]]] = None,
) -> CapabilityImplementation:
    """Builds one Registry implementation record. Shared by the ``assemble``
    and ``assemble_from_catalog`` entry points — the only place either one
    constructs a ``CapabilityImplementation``.

    ``executor_kind: "direct"`` (default): the loaded callable IS the
    executor. ``executor_kind: "factory"``: the loaded callable is invoked ONCE, here,
    with a ``Dependencies`` scoped to ``dependencies`` (R4) — its return
    value becomes the executor. Requires ``bridge`` (fail closed otherwise):
    a factory with no Bridge to resolve its dependencies through can't do
    its job. ``executor_kind: "process"``: ``executor`` names a program,
    spawned once, here, into a ``ProcessExecutorPool`` (bridge/process_executor.py)
    that becomes the executor — no import, no Python callable, for a
    capability implemented in another language. Also requires ``bridge``,
    for the same reason a factory does: a ``ProcessExecutorPool`` is given
    a ``Dependencies`` scoped to ``dependencies`` too, so the spawned
    process can call other capabilities through the Bridge, not just
    answer the Bridge's own calls.
    """

    if executor_kind == "process":
        if bridge is None:
            raise AssemblerError(
                f"{implementation_id!r} declares executor_kind='process' but no Bridge was "
                "given to build its Dependencies — construct the Bridge before assembling "
                "(see app/requests.py's ordering)"
            )
        from .process_executor import ProcessExecutorError, ProcessExecutorPool

        try:
            executor = ProcessExecutorPool(executor_path, bridge=bridge, declared=dict(dependencies))
        except ProcessExecutorError as exc:
            raise AssemblerError(f"{implementation_id!r}: {exc}") from exc
    else:
        raw = _load_executor(executor_path)
        if executor_kind == "factory":
            if bridge is None:
                raise AssemblerError(
                    f"{implementation_id!r} declares executor_kind='factory' but no Bridge was "
                    "given to build its Dependencies — construct the Bridge before assembling "
                    "(see app/requests.py's ordering)"
                )
            from .bridge import Dependencies

            executor = raw(Dependencies(bridge, dict(dependencies)))
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
        input_schema=dict(input_schema or {}),
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
        input_schema=entry.input_schema,
    )


def _check_no_dependency_cycles(graph: dict[str, Iterable[str]]) -> None:
    """Raises ``AssemblerError`` naming the cycle if the declared
    ``capability_id -> dependencies`` graph is not acyclic (R4/R5). Only
    capability ids present as keys are graph nodes; a dependency on a
    capability_id outside this assembly batch is a leaf (nothing further to
    walk) — cross-batch cycles are still caught eventually, since
    ``assemble_from_catalog`` builds this graph from the WHOLE catalog.

    Each graph value just needs to iterate to dependency capability ids —
    a ``dict[str, str]`` (capability_id -> pinned version) works exactly
    like a plain iterable of ids, since iterating a dict yields its keys.
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
    ``executor_kind: factory`` entries. Omitting it limits discovery to
    Exact/Scoped only. ``bridge`` is required only if any entry is
    factory-kind.

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


def _read_operation_descriptions(
    manifest: dict[str, Any], root: Path, contract_version: str, operation_names: Iterable[str]
) -> str:
    """Reads the given operations' descriptions from the SPECIFIC
    contract_version an implementation entry declares, for the catalog's
    ``description`` field only (agent keyword-search relevance) — never
    consumed by ``from_manifest``/registration itself.

    Deliberately scoped to one version's own recorded operations, not the
    contract-wide ``responsibility.description``: versions are peers, each
    potentially describing different behavior (R2) — a 1.0.0
    implementation's catalog description must keep describing 1.0.0's
    actual behavior even after a 2.0.0 peer with different operations is
    added, never silently pick up the newer version's wording.
    """

    contract_path = manifest.get("contract") if isinstance(manifest, dict) else None
    if not isinstance(contract_path, str) or not contract_path.strip():
        return ""
    try:
        contract_doc = yaml.safe_load((root / contract_path).read_text(encoding="utf-8"))
    except OSError:
        return ""
    contract = (contract_doc or {}).get("contract", {})
    versions_block = contract.get("versions", {}) or {}
    operations = (versions_block.get(contract_version) or {}).get("operations", []) or []
    wanted = set(operation_names)
    descriptions = [
        op["description"]
        for op in operations
        if isinstance(op, dict) and op.get("name") in wanted and op.get("description")
    ]
    if descriptions:
        return " ".join(descriptions)
    # Nothing matched (e.g. malformed data) -- the contract-wide summary is
    # a better fallback than an empty string, even though it isn't version-scoped.
    return contract.get("responsibility", {}).get("description", "") or ""


def _input_field_to_record(field_spec: InputField) -> dict[str, Any]:
    """`InputField` -> one JSON-safe catalog dict. `default`/`minLength`/
    `maxLength`/`enum` keys are included only when actually declared —
    `default`'s PRESENCE (not its value) is what a reader
    (`_input_field_from_record`) uses to tell "no default declared" apart
    from "declared, and it's null"; the other three are simply absent
    when not declared, `min_length`/`max_length`/`enum_values` on the
    `InputField` side already being `None` in that case.
    """

    record: dict[str, Any] = {"name": field_spec.name, "type": field_spec.type, "required": field_spec.required}
    if field_spec.has_default:
        record["default"] = field_spec.default
    if field_spec.min_length is not None:
        record["minLength"] = field_spec.min_length
    if field_spec.max_length is not None:
        record["maxLength"] = field_spec.max_length
    if field_spec.enum_values is not None:
        record["enum"] = list(field_spec.enum_values)
    if field_spec.pattern is not None:
        record["pattern"] = field_spec.pattern
    return record


def _input_field_from_record(record: dict[str, Any]) -> InputField:
    """The inverse of `_input_field_to_record` — reads a catalog dict back
    into an `InputField`, consumed by `assemble_from_catalog`.
    """

    return InputField(
        name=record["name"], type=record["type"], required=record["required"],
        has_default="default" in record, default=record.get("default"),
        min_length=record.get("minLength"), max_length=record.get("maxLength"),
        enum_values=tuple(record["enum"]) if "enum" in record else None,
        pattern=record.get("pattern"),
    )


def _manifest_records(manifest_path: Path, repo_root: Path) -> Iterator[dict[str, Any]]:
    """Parses one manifest file (and the contract it references) into catalog
    records. The shared unit ``append_to_catalog`` and ``rebuild_catalog``
    both build on — parsing logic lives once, in ``from_manifest``/
    ``_read_contract_metadata``.
    """

    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    entries = from_manifest(manifest, root=repo_root)
    contract_path = manifest.get("contract", "") if isinstance(manifest, dict) else ""
    try:
        manifest_rel = manifest_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        manifest_rel = manifest_path.as_posix()

    for entry in entries:
        description = _read_operation_descriptions(manifest, repo_root, entry.contract_version, entry.operations)
        input_schema = {
            operation: [_input_field_to_record(f) for f in fields]
            for operation, fields in entry.input_schema.items()
        }
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
            "dependencies": dict(entry.dependencies),
            "executor_kind": entry.executor_kind,
            "description": description,
            "input_schema": input_schema,
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
    it does not re-derive domain/family/tags/dependencies/input_schema from
    contracts itself. ``bridge`` is required only if any record is
    factory-kind or process-kind.

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
        {record["capability_id"]: tuple(record.get("dependencies", {})) for record in records}
    )

    registered: list[str] = []
    for record in records:
        input_schema = {
            operation: tuple(_input_field_from_record(f) for f in fields)
            for operation, fields in record.get("input_schema", {}).items()
        }
        implementation = _build_implementation(
            implementation_id=record["implementation_id"],
            package_version=record["package_version"],
            capability_id=record["capability_id"],
            contract_version=record["contract_version"],
            operations=tuple(record["operations"]),
            executor_path=record["executor_path"],
            priority=record["priority"],
            enabled=record.get("enabled", True),
            healthy=record.get("healthy", True),
            metadata=record.get("metadata"),
            domain=record.get("domain", ""),
            family=record.get("family", ""),
            tags=tuple(record.get("tags", ())),
            dependencies=record.get("dependencies", {}),
            executor_kind=record.get("executor_kind", "direct"),
            bridge=bridge,
            input_schema=input_schema,
        )
        registry.register(implementation)
        registered.append(implementation.implementation_id)
    return registered
