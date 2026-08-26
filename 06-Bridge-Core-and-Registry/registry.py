"""رجیستری درون‌فرایندیِ پیاده‌سازی‌های قابلیت.

رجیستری فقط گزینه‌های سازگار و فعال را کشف می‌کند. نه درخواست را اجرا می‌کند،
نه مجازبودن گزینه را می‌سنجد و نه از میان گزینه‌ها انتخاب نهایی انجام می‌دهد.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .policy import PolicyContext

Executor = Callable[[str, dict[str, Any], "PolicyContext"], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class CapabilityImplementation:
    """اعلام نسخه‌دار یک روش اجرای قابلیت، مستقل از مصرف‌کننده."""

    implementation_id: str
    package_version: str
    capability_id: str
    contract_version: str
    operations: tuple[str, ...]
    executor: Executor
    priority: int = 100
    enabled: bool = True
    healthy: bool = True
    metadata: dict[str, Any] | None = None

    def validate(self) -> None:
        required = (
            self.implementation_id,
            self.package_version,
            self.capability_id,
            self.contract_version,
        )
        if any(not value.strip() for value in required) or not self.operations:
            raise ValueError("اعلام پیاده‌سازی ناقص است")


class CapabilityRegistry:
    """ثبت مدیریتی را از کشف زمان اجرای درخواست جدا نگه می‌دارد."""

    def __init__(self) -> None:
        self._items: dict[str, CapabilityImplementation] = {}

    def register(self, implementation: CapabilityImplementation) -> None:
        implementation.validate()
        if implementation.implementation_id in self._items:
            raise ValueError("شناسهٔ پیاده‌سازی قبلاً ثبت شده است")
        self._items[implementation.implementation_id] = implementation

    def set_enabled(self, implementation_id: str, enabled: bool) -> None:
        """فعال‌سازی را بدون حذف هویت ثبت‌شده تغییر می‌دهد."""

        current = self._items[implementation_id]
        self._items[implementation_id] = CapabilityImplementation(
            implementation_id=current.implementation_id,
            package_version=current.package_version,
            capability_id=current.capability_id,
            contract_version=current.contract_version,
            operations=current.operations,
            executor=current.executor,
            priority=current.priority,
            enabled=enabled,
            healthy=current.healthy,
            metadata=current.metadata,
        )

    def set_healthy(self, implementation_id: str, healthy: bool) -> None:
        """سلامت اجرایی را بدون حذف ثبت یا تغییر قرارداد به‌روزرسانی می‌کند."""

        current = self._items[implementation_id]
        self._items[implementation_id] = CapabilityImplementation(
            implementation_id=current.implementation_id,
            package_version=current.package_version,
            capability_id=current.capability_id,
            contract_version=current.contract_version,
            operations=current.operations,
            executor=current.executor,
            priority=current.priority,
            enabled=current.enabled,
            healthy=healthy,
            metadata=current.metadata,
        )

    def discover(self, capability_id: str, contract_version: str, operation: str) -> tuple[CapabilityImplementation, ...]:
        """فقط گزینه‌های دقیقاً سازگار، فعال و سالم را برمی‌گرداند."""

        return tuple(
            item
            for item in self._items.values()
            if item.capability_id == capability_id
            and item.contract_version == contract_version
            and operation in item.operations
            and item.enabled
            and item.healthy
        )
