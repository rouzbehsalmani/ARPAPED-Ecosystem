"""مرز فرایندی جپای وضعیت پروژه و پروتکل محلی درخواست/پاسخ آن.

این فایل فقط اجرای محاسبهٔ جپا را از فرایند پل جدا می‌کند. کارگر هیچ مسیر،
مخزن یا کلاس داخلی دپ را دریافت نمی‌کند و تنها بستهٔ داده‌ای را می‌بیند که
اتصال‌دهنده پس از مصرف قابلیت عمومی بازپخش آماده کرده است.
"""

from __future__ import annotations

import multiprocessing
from multiprocessing.connection import Connection
from threading import Lock
from typing import Any
from uuid import uuid4

from project_jepa import ProjectStateJEPA


class JEPAProcessError(RuntimeError):
    """شکست پایدار مرز فرایندی، بدون نشت خطای خام سامانهٔ عامل."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _worker_main(connection: Connection) -> None:
    """پیام‌های نسخهٔ ۰٫۱ را تا توقف کنترل‌شده پردازش می‌کند.

    شناسهٔ هم‌بستگی بدون تغییر بازگردانده می‌شود تا پاسخ یک فراخوانی هم‌زمان
    هرگز به فراخوانی دیگری نسبت داده نشود.
    """

    model = ProjectStateJEPA()
    try:
        while True:
            message = connection.recv()
            if message.get("operation") == "stop":
                connection.send({"request_id": message["request_id"], "status": "stopped"})
                return
            request_id = str(message["request_id"])
            try:
                view = model.build_live_view(dict(message["dataset"]))
                connection.send({"request_id": request_id, "status": "ok", "view": view})
            except Exception as exc:
                # متن خطای اختصاصی برای عیب‌یابی محلی حفظ می‌شود، اما نوع خام
                # استثنا از مرز پروتکل عبور نمی‌کند.
                connection.send({
                    "request_id": request_id,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                })
    except (EOFError, BrokenPipeError, OSError):
        # بسته‌شدن سمت میزبان پایان طبیعی مالکیت این کارگر است.
        return
    finally:
        connection.close()


class JEPAProcessClient:
    """چرخهٔ عمر و فراخوانی هم‌بستهٔ یک کارگر مستقل جپا را مالک است."""

    PROTOCOL_VERSION = "0.1"

    def __init__(self, *, response_timeout: float = 10.0) -> None:
        self.response_timeout = response_timeout
        self._lock = Lock()
        self._process: multiprocessing.Process | None = None
        self._connection: Connection | None = None

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.is_alive()

    @property
    def process_id(self) -> int | None:
        return self._process.pid if self._process is not None else None

    def start(self) -> None:
        """کارگر تازه می‌سازد؛ راه‌اندازی دوباره وضعیت پل را بازنویسی نمی‌کند."""

        with self._lock:
            if self.running:
                return
            self._close_transport()
            parent, child = multiprocessing.Pipe(duplex=True)
            process = multiprocessing.Process(target=_worker_main, args=(child,), daemon=True)
            process.start()
            child.close()
            self._connection = parent
            self._process = process

    def build_view(self, dataset: dict[str, Any]) -> tuple[dict[str, Any], str]:
        """یک درخواست را اتمی ارسال و فقط پاسخ دارای همان شناسه را می‌پذیرد."""

        with self._lock:
            if not self.running or self._connection is None:
                raise JEPAProcessError("PROCESS_NOT_RUNNING", "فرایند جپا در حال اجرا نیست")
            request_id = f"jepa-process:{uuid4()}"
            try:
                self._connection.send({
                    "protocol_version": self.PROTOCOL_VERSION,
                    "request_id": request_id,
                    "operation": "build_view",
                    "dataset": dataset,
                })
                if not self._connection.poll(self.response_timeout):
                    raise JEPAProcessError("PROCESS_TIMEOUT", "پاسخ فرایند جپا در مهلت مقرر نرسید")
                response = self._connection.recv()
            except JEPAProcessError:
                raise
            except (EOFError, BrokenPipeError, OSError) as exc:
                raise JEPAProcessError("PROCESS_DIED", "ارتباط با فرایند جپا از بین رفت") from exc
            if response.get("request_id") != request_id:
                raise JEPAProcessError("CORRELATION_MISMATCH", "پاسخ فرایند به درخواست جاری تعلق ندارد")
            if response.get("status") != "ok":
                raise JEPAProcessError("WORKER_EXECUTION_FAILED", "فرایند جپا محاسبه را کامل نکرد")
            return dict(response["view"]), request_id

    def stop(self) -> None:
        """توقف کنترل‌شده را درخواست و منابع انتقال را جمع می‌کند."""

        with self._lock:
            if self.running and self._connection is not None:
                request_id = f"jepa-stop:{uuid4()}"
                try:
                    self._connection.send({"request_id": request_id, "operation": "stop"})
                    if self._connection.poll(self.response_timeout):
                        self._connection.recv()
                except (EOFError, BrokenPipeError, OSError):
                    pass
                self._process.join(timeout=self.response_timeout)
            if self._process is not None and self._process.is_alive():
                self._process.terminate()
                self._process.join(timeout=self.response_timeout)
            self._close_transport()

    def crash(self) -> None:
        """فقط برای اثبات مرگ ناگهانی، کارگر را بدون پیام توقف می‌کشد."""

        with self._lock:
            if self._process is not None and self._process.is_alive():
                self._process.terminate()
                self._process.join(timeout=self.response_timeout)

    def _close_transport(self) -> None:
        if self._connection is not None:
            self._connection.close()
        self._connection = None
        self._process = None
