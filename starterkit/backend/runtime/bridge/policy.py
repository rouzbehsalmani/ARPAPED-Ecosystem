"""Independent policy evaluation for each discovered candidate.

This small reference receives the five established policy sources in an explicit
context. A single available implementation does not bypass policy automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .registry import CapabilityImplementation


@dataclass(frozen=True)
class PolicyContext:
    """Policy decision sources for the request, kept out of the capability body."""

    user: dict[str, Any]
    consumer: dict[str, Any]
    ecosystem: dict[str, Any]
    provider: dict[str, Any]
    module: dict[str, Any]


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason_code: str


class StaticPolicyEngine:
    """Applies the basic declarative rules deterministically and testably to each candidate."""

    VERSION = "0.1"

    def evaluate(
        self,
        implementation: CapabilityImplementation,
        context: PolicyContext,
    ) -> PolicyDecision:
        sources = (context.user, context.consumer, context.ecosystem, context.provider, context.module)
        if any(source.get("enabled") is False for source in sources):
            return PolicyDecision(False, "POLICY_SOURCE_DISABLED")
        denied = {
            str(value)
            for source in sources
            for value in source.get("denied_implementation_ids", ())
        }
        if implementation.implementation_id in denied:
            return PolicyDecision(False, "IMPLEMENTATION_DENIED")
        return PolicyDecision(True, "ALLOWED")