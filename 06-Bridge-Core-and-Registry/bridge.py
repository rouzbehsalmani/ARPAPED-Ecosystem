"""هماهنگ‌کنندهٔ مسیر کامل درخواست قابلیت در مرجع محلی ارپاپد.

پل نه رجیستری است، نه موتور سیاست، نه انتخاب‌کننده و نه مالک اجرای دپ. فقط
درخواست استاندارد را از این مراحل عبور می‌دهد و ردپای مرحله‌ای برمی‌گرداند.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .policy import PolicyContext, StaticPolicyEngine
from .registry import CapabilityRegistry
from .selector import DeterministicSelector


@dataclass(frozen=True, slots=True)
class BridgeRequest:
    request_id: str
    capability_id: str
    contract_version: str
    operation: str
    input: dict[str, Any]
    policy_context: PolicyContext

    def validate(self) -> None:
        required = (self.request_id, self.capability_id, self.contract_version, self.operation)
        if any(not value.strip() for value in required):
            raise BridgeError("BRIDGE_INVALID_REQUEST", "validation", "فیلد الزامی درخواست خالی است")
        if not isinstance(self.input, dict):
            raise BridgeError("BRIDGE_INVALID_REQUEST", "validation", "ورودی عملیات باید شیء باشد")


@dataclass(frozen=True, slots=True)
class BridgeResponse:
    request_id: str
    capability_id: str
    contract_version: str
    implementation_id: str
    output: dict[str, Any]
    trace: tuple[str, ...]


@dataclass(slots=True)
class BridgeError(Exception):
    code: str
    stage: str
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return f"{self.code}@{self.stage}: {self.message}"


class Bridge:
    """اعتبارسنجی، کشف، سیاست، انتخاب و اجرا را بدون ادغام مسئولیت‌ها هماهنگ می‌کند."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        policy: StaticPolicyEngine,
        selector: DeterministicSelector,
    ) -> None:
        self.registry = registry
        self.policy = policy
        self.selector = selector

    def handle(self, request: BridgeRequest) -> BridgeResponse:
        request.validate()
        trace = ["validated"]
        discovered = self.registry.discover(
            request.capability_id, request.contract_version, request.operation,
        )
        trace.append("discovered")
        if not discovered:
            raise BridgeError("BRIDGE_NO_IMPLEMENTATION", "discovery", "پیاده‌سازی سازگاری کشف نشد")

        allowed = []
        rejections: dict[str, str] = {}
        for implementation in discovered:
            decision = self.policy.evaluate(implementation, request.policy_context)
            if decision.allowed:
                allowed.append(implementation)
            else:
                rejections[implementation.implementation_id] = decision.reason_code
        trace.append("policy_evaluated")
        if not allowed:
            raise BridgeError("BRIDGE_POLICY_DENIED", "policy", "همهٔ گزینه‌های سازگار رد شدند", rejections)

        ranked = self.selector.rank(tuple(allowed)) if hasattr(self.selector, "rank") else (self.selector.select(tuple(allowed)),)
        if not ranked:
            raise BridgeError("BRIDGE_NO_HEALTHY_ROUTE", "selection", "همهٔ گزینه‌های مجاز موقتاً بازمدارند")
        trace.append("selected")
        failures: dict[str, dict[str, Any]] = {}
        for selected in ranked:
            try:
            # زمینهٔ سیاست بخشی از زمینهٔ اجرای همان درخواست است. انتقال آن به
            # پیاده‌سازی اجازه می‌دهد وابستگی‌های تو‌در‌تو همان محدودیت‌ها را
            # حفظ کنند، بدون آنکه پیاده‌سازی داور نهایی سیاست شود.
                output = selected.executor(request.operation, request.input, request.policy_context)
            except BridgeError as exc:
                details = exc.details or {}
                if len(ranked) == 1 or not details.get("failover_allowed", False):
                    raise
                failures[selected.implementation_id] = {"code": exc.code, "stage": exc.stage, **details}
                if hasattr(self.selector, "record_failure"):
                    self.selector.record_failure(selected.implementation_id)
                continue
            except Exception as exc:
            # جزئیات داخلی پیاده‌سازی از این مرز عبور نمی‌کند؛ نوع پایدار پل حفظ می‌شود.
                raise BridgeError(
                    "BRIDGE_EXECUTION_FAILED", "execution", "پیاده‌سازی منتخب درخواست را اجرا نکرد",
                    {"implementation_id": selected.implementation_id, "cause_type": type(exc).__name__},
                ) from exc
            if hasattr(self.selector, "record_success"):
                self.selector.record_success(selected.implementation_id)
            break
        else:
            raise BridgeError(
                "BRIDGE_ALL_IMPLEMENTATIONS_FAILED", "execution",
                "همهٔ پیاده‌سازی‌های مجاز و قابل‌انتخاب شکست خوردند", failures,
            )
        trace.append("executed")
        return BridgeResponse(
            request_id=request.request_id,
            capability_id=request.capability_id,
            contract_version=request.contract_version,
            implementation_id=selected.implementation_id,
            output=output,
            trace=tuple(trace),
        )
