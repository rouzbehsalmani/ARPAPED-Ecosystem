"""سنجش مستقل سیاست برای هر گزینهٔ کشف‌شده.

این مرجع کوچک پنج منبع سیاست تثبیت‌شده را در یک زمینهٔ صریح دریافت می‌کند.
وجود تنها یک پیاده‌سازی باعث عبور خودکار از سیاست نمی‌شود.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .registry import CapabilityImplementation


@dataclass(frozen=True)
class PolicyContext:
    """منابع تصمیم سیاست برای همان درخواست، بدون قرارگرفتن در بدنهٔ قابلیت."""

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
    """قواعد اعلامی پایه را قطعی و قابل‌آزمون روی هر گزینه اعمال می‌کند."""

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
