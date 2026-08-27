"""Public interface of the local bridge reference for capability discovery and execution.

This package keeps the responsibilities of the bridge, registry, policy, and
selector separate even when all of them run in a single local process. The
application itself has no dependency on this package.
"""

from .bridge import Bridge, BridgeError, BridgeRequest, BridgeResponse
from .shared_idempotency import SHARED_IDEMPOTENCY_CAPABILITY, SharedIdempotencyLedger, register_shared_idempotency
from .policy import PolicyContext, PolicyDecision, StaticPolicyEngine
from .registry import CapabilityImplementation, CapabilityRegistry
from .selector import CircuitBreakingSelector, DeterministicSelector

__all__ = [
    "Bridge",
    "BridgeError",
    "BridgeRequest",
    "BridgeResponse",
    "CapabilityImplementation",
    "CapabilityRegistry",
    "DeterministicSelector",
    "PolicyContext",
    "PolicyDecision",
    "StaticPolicyEngine",
    "CircuitBreakingSelector",
    "SHARED_IDEMPOTENCY_CAPABILITY",
    "SharedIdempotencyLedger",
    "register_shared_idempotency",
]