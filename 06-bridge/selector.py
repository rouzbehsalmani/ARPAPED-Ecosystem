"""انتخاب و وضعیت شکست گزینه‌هایی که قبلاً از سیاست عبور کرده‌اند.

انتخاب‌کننده مجازبودن یا سازگاری را تعیین نمی‌کند. نسخهٔ تاب‌آور فقط سلامت
مشاهده‌شده در زمان اجرا را نگه می‌دارد تا پل بتواند از یک گزینهٔ بازمدار عبور
کند و پس از مهلت، دقیقاً یک درخواست آزمایشی را به آن بسپارد.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from .registry import CapabilityImplementation


class DeterministicSelector:
    """کمترین اولویت عددی و سپس شناسه را برمی‌گزیند تا نتیجه بازتولیدپذیر باشد."""

    VERSION = "0.1"

    def select(self, options: tuple[CapabilityImplementation, ...]) -> CapabilityImplementation:
        if not options:
            raise ValueError("گزینهٔ مجازی برای انتخاب وجود ندارد")
        return sorted(options, key=lambda item: (item.priority, item.implementation_id))[0]

    def rank(self, options: tuple[CapabilityImplementation, ...]) -> tuple[CapabilityImplementation, ...]:
        """رفتار قدیمی را حفظ می‌کند: فقط یک گزینه برای اجرا انتخاب می‌شود."""

        return (self.select(options),)


@dataclass(slots=True)
class _CircuitState:
    failures: int = 0
    opened_at: float | None = None
    probe_in_flight: bool = False


class CircuitBreakingSelector(DeterministicSelector):
    """مدارشکن حافظه‌ای با گذار بسته، باز و نیمه‌آزمایشی.

    این وضعیت یک شاهد مرجع زمان اجراست و جای سلامت اعلامی رجیستری را نمی‌گیرد.
    قفل فقط گذار وضعیت را اتمی می‌کند؛ اجرای ارائه‌دهنده زیر قفل انجام نمی‌شود.
    """

    VERSION = "0.2"

    def __init__(self, *, failure_threshold: int = 1, recovery_timeout: float = 0.2) -> None:
        if failure_threshold < 1 or recovery_timeout < 0:
            raise ValueError("تنظیم مدارشکن نامعتبر است")
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._states: dict[str, _CircuitState] = {}
        self._lock = threading.Lock()

    def rank(self, options: tuple[CapabilityImplementation, ...]) -> tuple[CapabilityImplementation, ...]:
        now = time.monotonic()
        available: list[CapabilityImplementation] = []
        with self._lock:
            for option in sorted(options, key=lambda item: (item.priority, item.implementation_id)):
                state = self._states.setdefault(option.implementation_id, _CircuitState())
                if state.opened_at is None:
                    available.append(option)
                elif now - state.opened_at >= self.recovery_timeout and not state.probe_in_flight:
                    # تنها یک درخواست حق ورود به حالت نیمه‌آزمایشی دارد؛ بقیه
                    # تا تعیین نتیجه از ارائه‌دهندهٔ سالم دیگر استفاده می‌کنند.
                    state.probe_in_flight = True
                    available.append(option)
        return tuple(available)

    def record_success(self, implementation_id: str) -> None:
        with self._lock:
            self._states[implementation_id] = _CircuitState()

    def record_failure(self, implementation_id: str) -> None:
        with self._lock:
            state = self._states.setdefault(implementation_id, _CircuitState())
            state.failures += 1
            state.probe_in_flight = False
            if state.failures >= self.failure_threshold:
                state.opened_at = time.monotonic()

    def state(self, implementation_id: str) -> str:
        """نمای تشخیصی پایدار برای آزمون؛ بخشی از قرارداد قابلیت نیست."""

        with self._lock:
            state = self._states.get(implementation_id, _CircuitState())
            if state.opened_at is None:
                return "closed"
            if state.probe_in_flight:
                return "half_open"
            return "open"
