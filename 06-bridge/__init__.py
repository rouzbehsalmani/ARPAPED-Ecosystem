"""رابط عمومی مرجع پل برای کشف و اجرای قابلیت دپ.

این بسته مسئولیت‌های پل، رجیستری، سیاست و انتخاب را جدا نگه می‌دارد؛ حتی
وقتی همه در یک فرایند محلی اجرا می‌شوند. خود دپ هیچ وابستگی‌ای به این بسته ندارد.
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
    "PROJECT_STATE_VIEW_CAPABILITY",
    "CircuitBreakingSelector",
    "SHARED_IDEMPOTENCY_CAPABILITY", 
    "SharedIdempotencyLedger", 
    "register_shared_idempotency",
]
