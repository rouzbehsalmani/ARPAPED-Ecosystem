"""In-process, capability-driven registry of implementations.

The registry only discovers compatible and active candidates. It does not execute
the request, decide whether a candidate is allowed, or make the final selection
among the candidates.

Discovery uses a "selective key -> candidate" index instead of scanning every
registration, keeping the normal path as "selective key -> relevant index ->
bounded candidates".
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
    """A versioned declaration of one way to execute a capability, independent of consumers."""

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

    The "capability + operation -> implementation ids" index lets discovery see
    only the candidates for that key instead of scanning every option (bounded
    complexity).
    """

    def __init__(self) -> None:
        self._items: dict[str, CapabilityImplementation] = {}
        self._by_capability_operation: dict[tuple[str, str], list[str]] = {}

    def _index(self, implementation: CapabilityImplementation) -> None:
        for operation in implementation.operations:
            holders = self._by_capability_operation.setdefault(
                (implementation.capability_id, operation), []
            )
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
        )

    def discover(self, capability_id: str, contract_version: str, operation: str) -> tuple[CapabilityImplementation, ...]:
        """Returns candidates that match the version constraint and are enabled and healthy, from the index."""

        holders = self._by_capability_operation.get(
            (capability_id, operation), []
        )
        return tuple(
            self._items[implementation_id]
            for implementation_id in holders
            if _matches_version(contract_version, self._items[implementation_id].contract_version)
            and self._items[implementation_id].enabled
            and self._items[implementation_id].healthy
        )