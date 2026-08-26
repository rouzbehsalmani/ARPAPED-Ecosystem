"""پیاده‌سازی قابلیت ثبت رخداد دپ پشت قرارداد عمومی پل.

این فایل تنها محل وابستگی پل مرجع به کلاس‌ها و خطاهای اختصاصی دپ است. تبدیل
ورودی، خروجی و خطا در همین مرز می‌ماند و به رجیستری یا مصرف‌کننده نشت نمی‌کند.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dep import DEPError, EventEnvelope, JsonlEventStore

from .bridge import Bridge, BridgeError
from .policy import PolicyContext, StaticPolicyEngine
from .registry import CapabilityImplementation, CapabilityRegistry
from .selector import DeterministicSelector


DEP_EVENT_APPEND_CAPABILITY = "arpaped.dep.event.append"
DEP_EVENT_REPLAY_CAPABILITY = "arpaped.dep.event.replay"


class DEPJsonlEventAppendImplementation:
    """قرارداد نسخهٔ ۰٫۱ ثبت رخداد را با مخزن پایدار دپ اجرا می‌کند."""

    IMPLEMENTATION_ID = "arpaped.dep.jsonl-event-store"
    PACKAGE_VERSION = "1.6.0"
    CONTRACT_VERSION = "0.1"

    def __init__(self, event_path: Path, *, store: JsonlEventStore | None = None) -> None:
        # اشتراک یک نمونه با قابلیت بازپخش باعث می‌شود خواندن پس از ثبت، همان
        # وضعیت پذیرفته‌شده را ببیند و به زمان بارگذاری اتصال‌دهنده وابسته نشود.
        self.store = store or JsonlEventStore(event_path)

    def execute(
        self, operation: str, input_record: dict[str, Any], policy_context: PolicyContext,
    ) -> dict[str, Any]:
        if operation != "append":
            raise BridgeError("BRIDGE_UNSUPPORTED_OPERATION", "execution", "عملیات پشتیبانی نمی‌شود")
        try:
            event = EventEnvelope.from_record(dict(input_record["event"]))
            accepted = self.store.append(event)
        except DEPError as exc:
            raise BridgeError(
                "BRIDGE_PROVIDER_REJECTED",
                "execution",
                "دپ رخداد را نپذیرفت",
                {"provider_code": exc.code.value, "provider_stage": exc.stage},
            ) from exc
        return {"status": "accepted", "event": accepted.to_record()}

    def descriptor(self, *, priority: int = 100) -> CapabilityImplementation:
        return CapabilityImplementation(
            implementation_id=self.IMPLEMENTATION_ID,
            package_version=self.PACKAGE_VERSION,
            capability_id=DEP_EVENT_APPEND_CAPABILITY,
            contract_version=self.CONTRACT_VERSION,
            operations=("append",),
            executor=self.execute,
            priority=priority,
            metadata={"storage": "jsonl", "module": "dep"},
        )


class DEPJsonlEventReplayImplementation:
    """قرارداد نسخهٔ ۰٫۱ بازپخش تمامیت‌سنجی‌شدهٔ دپ را اجرا می‌کند."""

    IMPLEMENTATION_ID = "arpaped.dep.jsonl-event-replay"
    PACKAGE_VERSION = "1.6.0"
    CONTRACT_VERSION = "0.1"

    def __init__(self, store: JsonlEventStore) -> None:
        self.store = store

    def execute(
        self, operation: str, input_record: dict[str, Any], policy_context: PolicyContext,
    ) -> dict[str, Any]:
        if operation != "replay":
            raise BridgeError("BRIDGE_UNSUPPORTED_OPERATION", "execution", "عملیات پشتیبانی نمی‌شود")
        try:
            events = [event.to_record() for event in self.store.replay()]
        except DEPError as exc:
            raise BridgeError(
                "BRIDGE_PROVIDER_REJECTED", "execution", "دپ تاریخچه را بازپخش نکرد",
                {"provider_code": exc.code.value, "provider_stage": exc.stage},
            ) from exc
        return {"events": events, "event_count": len(events), "integrity": "verified"}

    def descriptor(self, *, priority: int = 100) -> CapabilityImplementation:
        return CapabilityImplementation(
            implementation_id=self.IMPLEMENTATION_ID,
            package_version=self.PACKAGE_VERSION,
            capability_id=DEP_EVENT_REPLAY_CAPABILITY,
            contract_version=self.CONTRACT_VERSION,
            operations=("replay",),
            executor=self.execute,
            priority=priority,
            metadata={"storage": "jsonl", "module": "dep", "access": "read_only"},
        )


def build_dep_bridge(event_path: Path) -> tuple[Bridge, CapabilityRegistry]:
    """چرخهٔ مدیریت ثبت را انجام می‌دهد و پل آمادهٔ اجرای درخواست می‌سازد."""

    registry = CapabilityRegistry()
    store = JsonlEventStore(event_path)
    registry.register(DEPJsonlEventAppendImplementation(event_path, store=store).descriptor())
    registry.register(DEPJsonlEventReplayImplementation(store).descriptor())
    return Bridge(registry, StaticPolicyEngine(), DeterministicSelector()), registry
