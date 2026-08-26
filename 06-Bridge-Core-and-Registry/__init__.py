"""رابط عمومی مرجع پل برای کشف و اجرای قابلیت دپ.

این بسته مسئولیت‌های پل، رجیستری، سیاست و انتخاب را جدا نگه می‌دارد؛ حتی
وقتی همه در یک فرایند محلی اجرا می‌شوند. خود دپ هیچ وابستگی‌ای به این بسته ندارد.
"""

from .bridge import Bridge, BridgeError, BridgeRequest, BridgeResponse
from .dep_adapter import (
    DEP_EVENT_APPEND_CAPABILITY, DEP_EVENT_REPLAY_CAPABILITY,
    DEPJsonlEventAppendImplementation, DEPJsonlEventReplayImplementation, build_dep_bridge,
)
from .jepa_adapter import PROJECT_STATE_VIEW_CAPABILITY, ProjectStateJEPAImplementation, register_project_state_jepa
from .jepa_process import JEPAProcessClient, JEPAProcessError
from .process_jepa_adapter import ProcessProjectStateJEPAImplementation, register_process_project_state_jepa
from .remote_jepa import RemoteJEPABackpressure, RemoteJEPAClient, RemoteJEPAError, RemoteJEPAService
from .remote_jepa_adapter import RemoteProjectStateJEPAImplementation, register_remote_project_state_jepa
from .multihost_jepa import MultiHostProjectStateJEPA, register_multihost_project_state_jepa
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
    "DEP_EVENT_APPEND_CAPABILITY",
    "DEP_EVENT_REPLAY_CAPABILITY",
    "DEPJsonlEventAppendImplementation",
    "DEPJsonlEventReplayImplementation",
    "DeterministicSelector",
    "PolicyContext",
    "PolicyDecision",
    "StaticPolicyEngine",
    "PROJECT_STATE_VIEW_CAPABILITY",
    "ProjectStateJEPAImplementation",
    "JEPAProcessClient",
    "JEPAProcessError",
    "ProcessProjectStateJEPAImplementation",
    "build_dep_bridge",
    "register_project_state_jepa",
    "register_process_project_state_jepa",
    "RemoteJEPABackpressure", "RemoteJEPAClient", "RemoteJEPAError", "RemoteJEPAService",
    "RemoteProjectStateJEPAImplementation", "register_remote_project_state_jepa",
    "CircuitBreakingSelector", "MultiHostProjectStateJEPA", "register_multihost_project_state_jepa",
    "SHARED_IDEMPOTENCY_CAPABILITY", "SharedIdempotencyLedger", "register_shared_idempotency",
]
