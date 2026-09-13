"""Public interface of the local bridge reference for capability discovery and execution.

This package keeps the responsibilities of the bridge, registry, policy, and
selector separate even when all of them run in a single local process. The
application itself has no dependency on this package.
"""

from .assembler import AssemblerError, ManifestEntry, assemble, from_manifest
from .bridge import Bridge, BridgeError, BridgeRequest, BridgeResponse
from .policy import PolicyContext, PolicyDecision, StaticPolicyEngine
from .registry import CapabilityImplementation, CapabilityRegistry
from .selector import CircuitBreakingSelector, DeterministicSelector

__all__ = [
    "AssemblerError",
    "ManifestEntry",
    "assemble",
    "from_manifest",
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
]