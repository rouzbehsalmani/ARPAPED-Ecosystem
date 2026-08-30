"""In-process, capability-driven registry of implementations.

The registry only discovers compatible and active candidates. It does not execute
the request, decide whether a candidate is allowed, or make the final selection
among the candidates.

Discovery uses a "selective key -> candidate" index instead of scanning every
registration, keeping the normal path as "selective key -> relevant index ->
bounded candidates".

At scale, one selective key is not enough: `discover_cascade` searches
narrowest-to-widest (Exact -> Scoped -> Family -> Domain -> Cross-domain,
2-RULES.md "Registry contract"), stopping at the first level that returns a
bounded candidate set. Every level is still an indexed lookup, never a scan.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from .policy import PolicyContext

Executor = Callable[[str, dict[str, Any], "PolicyContext"], dict[str, Any]]


def _version_tuple(version: str) -> tuple[int, int, int]:
    """Converts a version string to a comparable 3-tuple; non-numeric segments are ignored."""

    numbers: list[int] = []
    for part in version.split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        numbers.append(int(digits) if digits else 0)
    while len(numbers) < 3:
        numbers.append(0)
    return (numbers[0], numbers[1], numbers[2])


def _matches_version(required: str, actual: str) -> bool:
    """Checks semantic version-range compatibility: exact, <, <=, >, >=, and comma ranges.

    Examples: "1.0.0", ">=1.0.0", ">1.0.0", "<=1.0.0", ">=1.0.0,<2.0.0", and "*".
    These are the same constraints the contract documents use for `contract_version`.
    """

    required = required.strip()
    if not required or required == "*":
        return True

    constraints = [c.strip() for c in required.split(",")]
    actual_tuple = _version_tuple(actual)
    for constraint in constraints:
        if not constraint:
            continue
        if constraint.startswith(">="):
            operator, version = ">=", constraint[2:]
        elif constraint.startswith("<="):
            operator, version = "<=", constraint[2:]
        elif constraint.startswith(">"):
            operator, version = ">", constraint[1:]
        elif constraint.startswith("<"):
            operator, version = "<", constraint[1:]
        else:
            operator, version = "==", constraint
        wanted = _version_tuple(version)
        if operator == "==" and actual_tuple != wanted:
            return False
        if operator == ">=" and not actual_tuple >= wanted:
            return False
        if operator == ">" and not actual_tuple > wanted:
            return False
        if operator == "<=" and not actual_tuple <= wanted:
            return False
        if operator == "<" and not actual_tuple < wanted:
            return False
    return True


@dataclass(frozen=True)
class CapabilityImplementation:
    """A versioned declaration of one way to execute a capability, independent of consumers.

    ``domain``, ``family``, and ``tags`` are read from the capability's own
    contract (identity.domain, identity.family, discoverability.tags) by the
    assembler when it is given a ``root`` to resolve the contract path
    against (see assembler.py). They are optional: an implementation
    registered without them is still fully discoverable at the Exact/Scoped
    levels, just invisible to Family/Domain/Cross-domain discovery.
    """

    implementation_id: str
    package_version: str
    capability_id: str
    contract_version: str
    operations: tuple[str, ...]
    executor: Executor
    priority: int = 100
    enabled: bool = True
    healthy: bool = True
    metadata: Optional[dict[str, Any]] = None
    domain: str = ""
    family: str = ""
    tags: tuple[str, ...] = ()

    def validate(self) -> None:
        required = (
            self.implementation_id,
            self.package_version,
            self.capability_id,
            self.contract_version,
        )
        if any(not value.strip() for value in required) or not self.operations:
            raise ValueError("Incomplete implementation declaration")


class CapabilityRegistry:
    """Keeps administrative registration separate from request-time discovery.

    Every lookup — Exact, Scoped, Family, Domain, or Cross-domain — resolves
    through an index keyed to that level; none of them scan every
    registration.
    """

    def __init__(self) -> None:
        self._items: dict[str, CapabilityImplementation] = {}
        self._by_capability_operation: dict[tuple[str, str], list[str]] = {}
        self._by_family_operation: dict[tuple[str, str, str], list[str]] = {}
        self._by_domain_operation: dict[tuple[str, str], list[str]] = {}
        self._by_tag_operation: dict[tuple[str, str], list[str]] = {}

    def _index(self, implementation: CapabilityImplementation) -> None:
        for operation in implementation.operations:
            self._add(self._by_capability_operation, (implementation.capability_id, operation), implementation)
            # Family names are only meaningful within their domain (a family
            # lives inside a domain, e.g. "presence" inside "spatial") --
            # keying on family alone would merge unrelated domains that
            # happen to reuse the same family name.
            if implementation.family and implementation.domain:
                self._add(
                    self._by_family_operation,
                    (implementation.domain, implementation.family, operation),
                    implementation,
                )
            if implementation.domain:
                self._add(self._by_domain_operation, (implementation.domain, operation), implementation)
            for tag in implementation.tags:
                self._add(self._by_tag_operation, (tag, operation), implementation)

    @staticmethod
    def _add(index: dict[tuple[str, ...], list[str]], key: tuple[str, ...], implementation: CapabilityImplementation) -> None:
        holders = index.setdefault(key, [])
        if implementation.implementation_id not in holders:
            holders.append(implementation.implementation_id)

    def register(self, implementation: CapabilityImplementation) -> None:
        implementation.validate()
        if implementation.implementation_id in self._items:
            raise ValueError("Implementation id is already registered")
        self._items[implementation.implementation_id] = implementation
        self._index(implementation)

    def set_enabled(self, implementation_id: str, enabled: bool) -> None:
        """Changes enablement without removing the registered identity."""

        current = self._items[implementation_id]
        self._items[implementation_id] = CapabilityImplementation(
            implementation_id=current.implementation_id,
            package_version=current.package_version,
            capability_id=current.capability_id,
            contract_version=current.contract_version,
            operations=current.operations,
            executor=current.executor,
            priority=current.priority,
            enabled=enabled,
            healthy=current.healthy,
            metadata=current.metadata,
            domain=current.domain,
            family=current.family,
            tags=current.tags,
        )

    def set_healthy(self, implementation_id: str, healthy: bool) -> None:
        """Updates execution health without removing the registration or changing the contract."""

        current = self._items[implementation_id]
        self._items[implementation_id] = CapabilityImplementation(
            implementation_id=current.implementation_id,
            package_version=current.package_version,
            capability_id=current.capability_id,
            contract_version=current.contract_version,
            operations=current.operations,
            executor=current.executor,
            priority=current.priority,
            enabled=current.enabled,
            healthy=healthy,
            metadata=current.metadata,
            domain=current.domain,
            family=current.family,
            tags=current.tags,
        )

    def _bounded(self, holder_ids: list[str], contract_version: str) -> tuple[CapabilityImplementation, ...]:
        """Filters an index's candidate ids down to the compatible, active ones."""

        return tuple(
            self._items[implementation_id]
            for implementation_id in holder_ids
            if _matches_version(contract_version, self._items[implementation_id].contract_version)
            and self._items[implementation_id].enabled
            and self._items[implementation_id].healthy
        )

    def discover(self, capability_id: str, contract_version: str, operation: str) -> tuple[CapabilityImplementation, ...]:
        """Returns candidates that match the version constraint and are enabled and healthy, from the index.

        This is the Scoped level of the discovery cascade (see
        ``discover_cascade``): exact capability id, any compatible version.
        """

        holders = self._by_capability_operation.get((capability_id, operation), [])
        return self._bounded(holders, contract_version)

    def discover_cascade(
        self,
        capability_id: str,
        operation: str,
        contract_version: str,
        *,
        exact_version: Optional[str] = None,
        implementation_id: Optional[str] = None,
        family: Optional[str] = None,
        domain: Optional[str] = None,
        tags: tuple[str, ...] = (),
    ) -> tuple[str, tuple[CapabilityImplementation, ...]]:
        """Searches narrowest-to-widest, stopping at the first bounded, non-empty level.

        Levels, in order (2-RULES.md "Registry contract"):

        1. Exact       -- capability_id + operation, a pinned version and/or
                          a specific implementation_id.
        2. Scoped      -- capability_id + operation, any compatible version
                          (``discover``, unchanged).
        3. Family      -- identity.domain + identity.family + operation,
                          across capability ids (family names are only
                          meaningful within their domain).
        4. Domain      -- identity.domain + operation, across families.
        5. Cross-domain -- discoverability.tags + operation, across domains.

        Returns ``(level_name, candidates)``; ``("none", ())`` once every
        level is exhausted, at which point creation (R1) is the only
        remaining option.
        """

        if exact_version is not None or implementation_id is not None:
            pinned = self.discover(capability_id, exact_version or contract_version, operation)
            if implementation_id is not None:
                pinned = tuple(c for c in pinned if c.implementation_id == implementation_id)
            if pinned:
                return "exact", pinned

        scoped = self.discover(capability_id, contract_version, operation)
        if scoped:
            return "scoped", scoped

        if family and domain:
            candidates = self._bounded(
                self._by_family_operation.get((domain, family, operation), []), contract_version
            )
            if candidates:
                return "family", candidates

        if domain:
            candidates = self._bounded(self._by_domain_operation.get((domain, operation), []), contract_version)
            if candidates:
                return "domain", candidates

        if tags:
            seen: set[str] = set()
            holders: list[str] = []
            for tag in tags:
                for holder_id in self._by_tag_operation.get((tag, operation), []):
                    if holder_id not in seen:
                        seen.add(holder_id)
                        holders.append(holder_id)
            candidates = self._bounded(holders, contract_version)
            if candidates:
                return "cross_domain", candidates

        return "none", ()
