"""ترجمهٔ قابلیت نمای وضعیت به خدمت دوردست؛ وابستگی دپ در میزبان می‌ماند."""
from __future__ import annotations
from typing import Any
from dep import EventEnvelope, VersionedDatasetBuilder
from .bridge import Bridge, BridgeError, BridgeRequest
from .dep_adapter import DEP_EVENT_REPLAY_CAPABILITY
from .jepa_adapter import PROJECT_STATE_VIEW_CAPABILITY
from .policy import PolicyContext
from .registry import CapabilityImplementation, CapabilityRegistry
from .remote_jepa import RemoteJEPABackpressure, RemoteJEPAClient, RemoteJEPAError, RemoteJEPAService

class RemoteProjectStateJEPAImplementation:
    """قرارداد قابلیت ۰٫۱ را از راه پروتکل انتقال ۰٫۲ اجرا می‌کند."""
    IMPLEMENTATION_ID="arpaped.project-state-jepa.remote-reference"; PACKAGE_VERSION="1.8.0"; CONTRACT_VERSION="0.1"
    def __init__(self,bridge:Bridge,service:RemoteJEPAService,client:RemoteJEPAClient,*,implementation_id:str|None=None,priority:int=80,shared_idempotency:bool=False)->None:
        self.bridge=bridge; self.service=service; self.client=client
        self.implementation_id=implementation_id or self.IMPLEMENTATION_ID; self.priority=priority; self.shared_idempotency=shared_idempotency
    def stop(self)->None: self.service.stop()
    def crash(self)->None: self.service.crash()
    def restart(self)->None:
        """میزبان را با نشانی تازه و همان تنظیمات مشتری به رجیستری موجود برمی‌گرداند."""
        timeout=self.client.timeout; attempts=self.client.max_attempts
        # ظرفیت BoundedSemaphore قابل خواندن نیست؛ مرجع بازیابی ظرفیت پیش‌فرض
        # را به‌کار می‌گیرد و قرارداد قابلیت یا هویت ثبت‌شده را تغییر نمی‌دهد.
        self.service.stop(); self.service.start()
        self.client=RemoteJEPAClient(self.service.address,timeout=timeout,max_attempts=attempts)
    def execute(self,operation:str,input_record:dict[str,Any],policy_context:PolicyContext)->dict[str,Any]:
        if operation!="build": raise BridgeError("BRIDGE_UNSUPPORTED_OPERATION","execution","عملیات پشتیبانی نمی‌شود")
        try:
            replay=self.bridge.handle(BridgeRequest(str(input_record.get("dependency_request_id","remote-jepa-dep-replay")),DEP_EVENT_REPLAY_CAPABILITY,"0.1","replay",{},policy_context))
        except BridgeError as exc:
            raise BridgeError("BRIDGE_DEPENDENCY_UNAVAILABLE","execution","قابلیت بازپخش موردنیاز جپا در دسترس نیست",{"required_capability_id":DEP_EVENT_REPLAY_CAPABILITY,"dependency_code":exc.code}) from exc
        dataset=VersionedDatasetBuilder().build(tuple(EventEnvelope.from_record(record) for record in replay.output["events"]))
        try: receipt=self.client.build_view(dataset,idempotency_key=str(input_record.get("idempotency_key","")))
        except RemoteJEPABackpressure as exc: raise BridgeError("BRIDGE_BACKPRESSURE","execution","ظرفیت جپای دوردست پر است") from exc
        except RemoteJEPAError as exc:
            phase=str(exc.details.get("failure_phase","ambiguous"))
            # حافظهٔ یکتایی خدمت‌محلی است؛ بنابراین فقط شکستی که قطعاً پیش از
            # ارسال رخ داده می‌تواند بدون خطر اجرای دوم به میزبان دیگر برود.
            # شکست مبهم فقط با کلید ثبت‌شده در دفتر مشترک حق عبور میان میزبان‌ها دارد.
            failover_allowed=phase=="before_execution" or (self.shared_idempotency and bool(input_record.get("idempotency_key")))
            raise BridgeError("BRIDGE_REMOTE_EXECUTION_FAILED","execution","خدمت دوردست جپا درخواست را کامل نکرد",{"remote_code":exc.code,"failure_phase":phase,"failover_allowed":failover_allowed}) from exc
        return {"view":receipt.view,"source_event_count":replay.output["event_count"],"dependency":{"capability_id":DEP_EVENT_REPLAY_CAPABILITY,"contract_version":"0.1","implementation_id":replay.implementation_id,"trace":list(replay.trace)},"execution_boundary":{"kind":"remote_transport","protocol_version":self.client.PROTOCOL_VERSION,"service_process_id":receipt.service_process_id,"remote_request_id":receipt.request_id,"attempts":receipt.attempts,"deduplicated":receipt.deduplicated}}
    def descriptor(self,*,priority:int|None=None)->CapabilityImplementation:
        return CapabilityImplementation(implementation_id=self.implementation_id,package_version=self.PACKAGE_VERSION,capability_id=PROJECT_STATE_VIEW_CAPABILITY,contract_version=self.CONTRACT_VERSION,operations=("build",),executor=self.execute,priority=self.priority if priority is None else priority,metadata={"module":"project_state_jepa","execution_boundary":"remote_transport","transport_protocol_version":self.client.PROTOCOL_VERSION,"required_capabilities":[{"capability_id":DEP_EVENT_REPLAY_CAPABILITY,"contract_version":"0.1"}]})

def register_remote_project_state_jepa(bridge:Bridge,registry:CapabilityRegistry,*,timeout:float=2,max_attempts:int=2,max_in_flight:int=2)->RemoteProjectStateJEPAImplementation:
    """راه‌اندازی خدمت و ثبت اعلام مستقل آن در چرخهٔ مدیریت."""
    service=RemoteJEPAService(); service.start(); client=RemoteJEPAClient(service.address,timeout=timeout,max_attempts=max_attempts,max_in_flight=max_in_flight)
    implementation=RemoteProjectStateJEPAImplementation(bridge,service,client); registry.register(implementation.descriptor()); return implementation
