"""Selection and failure state of candidates that already passed policy.

The selector does not determine permission or compatibility. The resilient
variant only keeps observed runtime health so the bridge can bypass an
unavailable candidate and, after the timeout, hand it exactly one probe request.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Optional

from .registry import CapabilityImplementation


class DeterministicSelector:
    """Chooses the highest numeric priority, then the lowest id, for a
    reproducible result. Higher priority number = higher precedence = picked
    first — a new, preferred implementation states a higher number; nothing
    about any existing implementation that doesn't set one (default 100)
    needs to change for it to lose that comparison.
    """

    VERSION = "0.1"

    def select(self, options: tuple[CapabilityImplementation, ...]) -> CapabilityImplementation:
        if not options:
            raise ValueError("No candidate available for selection")
        return sorted(options, key=lambda item: (-item.priority, item.implementation_id))[0]

    def rank(self, options: tuple[CapabilityImplementation, ...]) -> tuple[CapabilityImplementation, ...]:
        """The base ranking strategy: only the single highest-precedence candidate is chosen for execution."""

        return (self.select(options),)


@dataclass
class _CircuitState:
    failures: int = 0
    opened_at: Optional[float] = None
    probe_in_flight: bool = False


class CircuitBreakingSelector(DeterministicSelector):
    """In-memory circuit breaker with closed, open, and half-open transitions.

    This state is a runtime reference witness and does not replace the registry's
    declared health. The lock only makes state transitions atomic; provider
    execution never happens under the lock.
    """

    VERSION = "0.2"

    def __init__(self, *, failure_threshold: int = 1, recovery_timeout: float = 0.2) -> None:
        if failure_threshold < 1 or recovery_timeout < 0:
            raise ValueError("Invalid circuit breaker configuration")
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._states: dict[str, _CircuitState] = {}
        self._lock = threading.Lock()

    def rank(self, options: tuple[CapabilityImplementation, ...]) -> tuple[CapabilityImplementation, ...]:
        now = time.monotonic()
        available: list[CapabilityImplementation] = []
        with self._lock:
            for option in sorted(options, key=lambda item: (-item.priority, item.implementation_id)):
                state = self._states.setdefault(option.implementation_id, _CircuitState())
                if state.opened_at is None:
                    available.append(option)
                elif now - state.opened_at >= self.recovery_timeout and not state.probe_in_flight:
                    # Only one request may enter the half-open probe; the rest
                    # use the other healthy provider until the outcome is known.
                    state.probe_in_flight = True
                    available.append(option)
        return tuple(available)

    def record_success(self, implementation_id: str) -> None:
        with self._lock:
            self._states[implementation_id] = _CircuitState()

    def record_failure(self, implementation_id: str) -> None:
        with self._lock:
            state = self._states.setdefault(implementation_id, _CircuitState())
            state.failures += 1
            state.probe_in_flight = False
            if state.failures >= self.failure_threshold:
                state.opened_at = time.monotonic()

    def state(self, implementation_id: str) -> str:
        """Stable diagnostic view for tests; not part of the capability contract."""

        with self._lock:
            state = self._states.get(implementation_id, _CircuitState())
            if state.opened_at is None:
                return "closed"
            if state.probe_in_flight:
                return "half_open"
            return "open"