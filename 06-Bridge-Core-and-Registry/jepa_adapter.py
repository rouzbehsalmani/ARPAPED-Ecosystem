"""اتصال‌دهندهٔ جپای وضعیت پروژه به قراردادهای عمومی پل.

این فایل تنها محل آگاهی مسیر پل از پیاده‌سازی آزمایشی جپاست. جپا برای دریافت
رخدادها به مخزن، فایل یا کلاس داخلی دپ دسترسی ندارد و قابلیت بازپخش دپ را از
خود پل درخواست می‌کند. توقف جپا فقط همین پیاده‌سازی را از خدمت خارج می‌کند.
"""

from __future__ import annotations

from typing import Any

from dep import EventEnvelope, VersionedDatasetBuilder
from project_jepa import ProjectStateJEPA

from .bridge import Bridge, BridgeError, BridgeRequest
from .dep_adapter import DEP_EVENT_REPLAY_CAPABILITY
from .policy import PolicyContext
from .registry import CapabilityImplementation, CapabilityRegistry


PROJECT_STATE_VIEW_CAPABILITY = "arpaped.project-state.view"


class ProjectStateJEPAImplementation:
    """نمای وضعیت نسخهٔ ۰٫۱ را با وابستگی قابلیت‌محور به دپ می‌سازد."""

    IMPLEMENTATION_ID = "arpaped.project-state-jepa.reference"
    PACKAGE_VERSION = "1.6.0"
    CONTRACT_VERSION = "0.1"

    def __init__(self, bridge: Bridge) -> None:
        self.bridge = bridge
        self.running = True

    def stop(self) -> None:
        """منابع اجرایی جپا را متوقف می‌کند، بدون تغییر پل یا دپ."""

        self.running = False

    def start(self) -> None:
        self.running = True

    def execute(
        self, operation: str, input_record: dict[str, Any], policy_context: PolicyContext,
    ) -> dict[str, Any]:
        if operation != "build":
            raise BridgeError("BRIDGE_UNSUPPORTED_OPERATION", "execution", "عملیات پشتیبانی نمی‌شود")
        if not self.running:
            raise BridgeError("BRIDGE_IMPLEMENTATION_STOPPED", "execution", "پیاده‌سازی جپا متوقف است")

        try:
            replay = self.bridge.handle(BridgeRequest(
                request_id=str(input_record.get("dependency_request_id", "jepa-dep-replay")),
                capability_id=DEP_EVENT_REPLAY_CAPABILITY,
                contract_version="0.1",
                operation="replay",
                input={},
                # همان پنج منبع سیاست به وابستگی منتقل می‌شوند؛ اتصال‌دهنده
                # حق ندارد برای درخواست داخلی زمینهٔ آزاد تازه بسازد.
                policy_context=policy_context,
            ))
        except BridgeError as exc:
            # خطای درخواست تو‌در‌توی دپ نباید هویت درخواست جپا را بپوشاند. کد
            # عمومی وابستگی بیرون می‌آید و علت اصلی برای حسابرسی حفظ می‌شود.
            raise BridgeError(
                "BRIDGE_DEPENDENCY_UNAVAILABLE",
                "execution",
                "قابلیت بازپخش موردنیاز جپا در دسترس نیست",
                {
                    "required_capability_id": DEP_EVENT_REPLAY_CAPABILITY,
                    "dependency_code": exc.code,
                    "dependency_stage": exc.stage,
                },
            ) from exc
        events = tuple(EventEnvelope.from_record(record) for record in replay.output["events"])
        dataset = VersionedDatasetBuilder().build(events)
        view = ProjectStateJEPA().build_live_view(dataset)
        return {
            "view": view,
            "source_event_count": replay.output["event_count"],
            "dependency": {
                "capability_id": DEP_EVENT_REPLAY_CAPABILITY,
                "contract_version": "0.1",
                "implementation_id": replay.implementation_id,
                "trace": list(replay.trace),
            },
        }

    def descriptor(self, *, priority: int = 100) -> CapabilityImplementation:
        return CapabilityImplementation(
            implementation_id=self.IMPLEMENTATION_ID,
            package_version=self.PACKAGE_VERSION,
            capability_id=PROJECT_STATE_VIEW_CAPABILITY,
            contract_version=self.CONTRACT_VERSION,
            operations=("build",),
            executor=self.execute,
            priority=priority,
            metadata={
                "module": "project_state_jepa",
                "required_capabilities": [{
                    "capability_id": DEP_EVENT_REPLAY_CAPABILITY,
                    "contract_version": "0.1",
                }],
            },
        )


def register_project_state_jepa(
    bridge: Bridge, registry: CapabilityRegistry,
) -> ProjectStateJEPAImplementation:
    """چرخهٔ مدیریتی ثبت جپا را جدا از چرخهٔ اجرای درخواست انجام می‌دهد."""

    implementation = ProjectStateJEPAImplementation(bridge)
    registry.register(implementation.descriptor())
    return implementation
