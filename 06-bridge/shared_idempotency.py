"""دفتر یکتایی مشترک نسخهٔ ۰٫۱ برای هماهنگی اثر میان چند میزبان.

دفتر از جپا، پل و انتخاب‌کننده مستقل است. مدیر فرایند فقط پیاده‌سازی مرجع
محلی قرارداد است و می‌تواند بدون تغییر مصرف‌کننده با پیاده‌سازی دیگری عوض شود.
"""
from __future__ import annotations
import multiprocessing
from multiprocessing.managers import SyncManager
from dataclasses import dataclass
from typing import Any
from .bridge import BridgeError
from .policy import PolicyContext
from .registry import CapabilityImplementation, CapabilityRegistry

SHARED_IDEMPOTENCY_CAPABILITY = "arpaped.execution.idempotency"

@dataclass(slots=True)
class SharedIdempotencyLedger:
    """مالک چرخهٔ عمر ذخیره و عملیات اتمی نتیجهٔ مشترک."""
    manager: Any
    entries: Any
    lock: Any
    implementation_id: str = "arpaped.shared-idempotency.manager-reference"

    @classmethod
    def start(cls) -> "SharedIdempotencyLedger":
        # نشانی شبکه‌ای صریح از سوکت یونیکس موقت مستقل است و همان مرز
        # چندمیزبانی مرجع را در محیط‌های محدود نیز حفظ می‌کند.
        manager = SyncManager(address=("127.0.0.1", 0), authkey=b"dep-v2-shared-idempotency")
        manager.start()
        return cls(manager, manager.dict(), manager.RLock())

    def stop(self) -> None:
        self.manager.shutdown()

    def descriptor(self) -> CapabilityImplementation:
        return CapabilityImplementation(
            self.implementation_id, "2.0.0", SHARED_IDEMPOTENCY_CAPABILITY, "0.1",
            ("inspect",), self.execute, priority=70,
            metadata={"module": "shared_idempotency", "data_contract_version": "0.1"},
        )

    def execute(self, operation: str, input_record: dict[str, Any], policy: PolicyContext) -> dict[str, Any]:
        if operation != "inspect":
            raise BridgeError("BRIDGE_UNSUPPORTED_OPERATION", "execution", "عملیات دفتر پشتیبانی نمی‌شود")
        with self.lock:
            present = self.entries.get(str(input_record.get("idempotency_key", ""))) is not None
        return {"present": present, "status": "completed" if present else "missing"}

def register_shared_idempotency(registry: CapabilityRegistry) -> SharedIdempotencyLedger:
    """چرخهٔ مدیریت، دفتر را مستقل می‌سازد و ثبت می‌کند."""
    ledger = SharedIdempotencyLedger.start()
    registry.register(ledger.descriptor())
    return ledger
