"""اتصال‌دهندهٔ پل به پیاده‌سازی جپای مستقر در فرایند مستقل.

مصرف وابستگی دپ در سمت پل انجام می‌شود تا مسیر اعتبارسنجی، رجیستری، سیاست و
انتخاب حفظ شود. فقط بستهٔ دادهٔ حاصل از قرارداد عمومی به کارگر جپا می‌رسد.
"""

from __future__ import annotations

from typing import Any

from dep import EventEnvelope, VersionedDatasetBuilder

from .bridge import Bridge, BridgeError, BridgeRequest
from .dep_adapter import DEP_EVENT_REPLAY_CAPABILITY
from .jepa_adapter import PROJECT_STATE_VIEW_CAPABILITY
from .jepa_process import JEPAProcessClient, JEPAProcessError
from .policy import PolicyContext
from .registry import CapabilityImplementation, CapabilityRegistry


class ProcessProjectStateJEPAImplementation:
    """قرارداد نمای وضعیت ۰٫۱ را از طریق یک کارگر مستقل اجرا می‌کند."""

    IMPLEMENTATION_ID = "arpaped.project-state-jepa.process-reference"
    PACKAGE_VERSION = "1.7.0"
    CONTRACT_VERSION = "0.1"

    def __init__(self, bridge: Bridge, *, client: JEPAProcessClient | None = None) -> None:
        self.bridge = bridge
        self.client = client or JEPAProcessClient()

    def start(self) -> None:
        self.client.start()

    def stop(self) -> None:
        self.client.stop()

    def crash(self) -> None:
        self.client.crash()

    def execute(
        self, operation: str, input_record: dict[str, Any], policy_context: PolicyContext,
    ) -> dict[str, Any]:
        if operation != "build":
            raise BridgeError("BRIDGE_UNSUPPORTED_OPERATION", "execution", "عملیات پشتیبانی نمی‌شود")
        if not self.client.running:
            raise BridgeError("BRIDGE_IMPLEMENTATION_STOPPED", "execution", "فرایند جپا در دسترس نیست")
        try:
            replay = self.bridge.handle(BridgeRequest(
                request_id=str(input_record.get("dependency_request_id", "process-jepa-dep-replay")),
                capability_id=DEP_EVENT_REPLAY_CAPABILITY,
                contract_version="0.1",
                operation="replay",
                input={},
                policy_context=policy_context,
            ))
        except BridgeError as exc:
            raise BridgeError(
                "BRIDGE_DEPENDENCY_UNAVAILABLE", "execution",
                "قابلیت بازپخش موردنیاز جپا در دسترس نیست",
                {
                    "required_capability_id": DEP_EVENT_REPLAY_CAPABILITY,
                    "dependency_code": exc.code,
                    "dependency_stage": exc.stage,
                },
            ) from exc
        events = tuple(EventEnvelope.from_record(record) for record in replay.output["events"])
        dataset = VersionedDatasetBuilder().build(events)
        try:
            view, worker_request_id = self.client.build_view(dataset)
        except JEPAProcessError as exc:
            raise BridgeError(
                "BRIDGE_REMOTE_EXECUTION_FAILED", "execution",
                "فرایند مستقل جپا درخواست را کامل نکرد",
                {"process_code": exc.code},
            ) from exc
        return {
            "view": view,
            "source_event_count": replay.output["event_count"],
            "dependency": {
                "capability_id": DEP_EVENT_REPLAY_CAPABILITY,
                "contract_version": "0.1",
                "implementation_id": replay.implementation_id,
                "trace": list(replay.trace),
            },
            "execution_boundary": {
                "kind": "separate_process",
                "protocol_version": self.client.PROTOCOL_VERSION,
                "process_id": self.client.process_id,
                "worker_request_id": worker_request_id,
            },
        }

    def descriptor(self, *, priority: int = 90) -> CapabilityImplementation:
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
                "execution_boundary": "separate_process",
                "required_capabilities": [{
                    "capability_id": DEP_EVENT_REPLAY_CAPABILITY,
                    "contract_version": "0.1",
                }],
            },
        )


def register_process_project_state_jepa(
    bridge: Bridge, registry: CapabilityRegistry,
) -> ProcessProjectStateJEPAImplementation:
    """فرایند را راه می‌اندازد و اعلام قابلیت آن را در رجیستری ثبت می‌کند."""

    implementation = ProcessProjectStateJEPAImplementation(bridge)
    implementation.start()
    registry.register(implementation.descriptor())
    return implementation
