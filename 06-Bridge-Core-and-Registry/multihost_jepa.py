"""چرخهٔ مدیریت چند میزبان مستقل برای یک قابلیت جپا.

این جزء فقط خدمت‌ها را راه‌اندازی و اعلام‌های مستقل را در رجیستری ثبت می‌کند.
کشف با رجیستری، مجازبودن با موتور سیاست، ترتیب و مدار با انتخاب‌کننده و انتقال
میان گزینه‌ها با پل می‌ماند؛ بنابراین خوشه یک پیاده‌سازی پنهان و یکپارچه نیست.
"""

from __future__ import annotations

from dataclasses import dataclass

from .bridge import Bridge
from .registry import CapabilityRegistry
from .remote_jepa import RemoteJEPAClient, RemoteJEPAService
from .remote_jepa_adapter import RemoteProjectStateJEPAImplementation
from .shared_idempotency import SharedIdempotencyLedger, register_shared_idempotency


@dataclass(slots=True)
class MultiHostProjectStateJEPA:
    """مالک چرخهٔ عمر میزبان‌ها؛ فاقد قرارداد اجرای قابلیت مستقل."""

    hosts: tuple[RemoteProjectStateJEPAImplementation, ...]
    shared_ledger: SharedIdempotencyLedger | None = None

    def stop(self) -> None:
        for host in self.hosts:
            host.stop()
        if self.shared_ledger is not None:
            self.shared_ledger.stop()

    def host(self, name: str) -> RemoteProjectStateJEPAImplementation:
        implementation_id = f"arpaped.project-state-jepa.remote-reference.{name}"
        return next(item for item in self.hosts if item.implementation_id == implementation_id)


def register_multihost_project_state_jepa(
    bridge: Bridge,
    registry: CapabilityRegistry,
    *,
    host_names: tuple[str, ...] = ("primary", "secondary"),
    timeout: float = 0.2,
    max_attempts: int = 1,
    shared_idempotency: bool = False,
) -> MultiHostProjectStateJEPA:
    """هر میزبان را با هویت، اتصال و اعلام رجیستری مستقل ثبت می‌کند."""

    hosts: list[RemoteProjectStateJEPAImplementation] = []
    ledger = register_shared_idempotency(registry) if shared_idempotency else None
    try:
        for index, name in enumerate(host_names):
            service = RemoteJEPAService(ledger)
            service.start()
            client = RemoteJEPAClient(service.address, timeout=timeout, max_attempts=max_attempts)
            implementation = RemoteProjectStateJEPAImplementation(
                bridge, service, client,
                implementation_id=f"arpaped.project-state-jepa.remote-reference.{name}",
                priority=80 + index,
                shared_idempotency=shared_idempotency,
            )
            registry.register(implementation.descriptor())
            hosts.append(implementation)
    except Exception:
        for host in hosts:
            host.stop()
        raise
    return MultiHostProjectStateJEPA(tuple(hosts), ledger)
