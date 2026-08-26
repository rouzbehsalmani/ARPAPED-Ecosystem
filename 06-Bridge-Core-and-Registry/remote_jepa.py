"""انتقال شبکه‌ای نسخه‌دار جپا؛ بدون دسترسی خدمت به پل یا دپ."""
from __future__ import annotations
import hashlib, json, multiprocessing, socket, socketserver, threading, time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4
from dep.canonical import canonical_bytes
from project_jepa import ProjectStateJEPA

class RemoteJEPAError(RuntimeError):
    """خطای پایدار انتقال، مستقل از خطای خام سوکت."""
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message); self.code = code; self.details = details or {}

class RemoteJEPABackpressure(RemoteJEPAError):
    """رد فوری کار تازه هنگام پر بودن ظرفیت محدود."""

@dataclass(frozen=True, slots=True)
class RemoteCallReceipt:
    view: dict[str, Any]; request_id: str; attempts: int; deduplicated: bool; service_process_id: int

class _State:
    def __init__(self, shared_ledger: Any = None) -> None:
        self.lock = threading.Lock(); self.cache: dict[str, tuple[str, dict[str, Any]]] = {}
        self.execution_count = 0; self.disconnect_count = 0; self.delay_seconds = 0.0
        self.shared_ledger = shared_ledger

def _read(stream: Any) -> dict[str, Any]:
    raw = stream.readline()
    if not raw: raise EOFError("ارتباط پیش از دریافت پاسخ بسته شد")
    return dict(json.loads(raw.decode("utf-8")))

class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        state: _State = self.server.state  # type: ignore[attr-defined]
        request: dict[str, Any] = {}
        try:
            request = _read(self.rfile); operation = request.get("operation")
            if operation == "configure_fault":
                with state.lock:
                    state.disconnect_count = int(request.get("disconnect_count", 0)); state.delay_seconds = float(request.get("delay_seconds", 0))
                self._send({"status":"configured","request_id":request.get("request_id")}); return
            if operation == "stats":
                with state.lock: count = state.execution_count
                self._send({"status":"ok","request_id":request.get("request_id"),"execution_count":count}); return
            response, disconnect = self._build(request, state)
            if not disconnect: self._send(response)
        except Exception as exc:
            self._send({"status":"failed","request_id":request.get("request_id"),"error_code":"REMOTE_PROTOCOL_FAILURE","message":str(exc)})

    def _build(self, request: dict[str, Any], state: _State) -> tuple[dict[str, Any], bool]:
        rid = str(request.get("request_id", ""))
        if request.get("protocol_version") != RemoteJEPAClient.PROTOCOL_VERSION:
            return {"status":"failed","request_id":rid,"error_code":"PROTOCOL_VERSION_UNSUPPORTED","supported_protocol_versions":[RemoteJEPAClient.PROTOCOL_VERSION]}, False
        if request.get("capability_id") != RemoteJEPAClient.CAPABILITY_ID or request.get("contract_version") != "0.1":
            return {"status":"failed","request_id":rid,"error_code":"CAPABILITY_CONTRACT_UNSUPPORTED","supported_contract_versions":["0.1"]}, False
        key = str(request.get("idempotency_key", "")); dataset = dict(request.get("dataset", {}))
        fingerprint = hashlib.sha256(canonical_bytes(dataset)).hexdigest()
        # قفل تا ثبت نتیجه حفظ می‌شود تا دو فراخوانی هم‌زمان با یک کلید هرگز
        # هر دو به محاسبه وارد نشوند. این مرجع اجرای موازی مدل را ادعا نمی‌کند.
        shared = state.shared_ledger
        lock = shared.lock if shared is not None and key else state.lock
        cache = shared.entries if shared is not None and key else state.cache
        # قفل مشترک از بررسی تا ثبت نتیجه، شکاف اجرای هم‌زمان دو میزبان را می‌بندد.
        with lock:
            cached = cache.get(key) if key else None; delay = state.delay_seconds
            if cached is not None:
                if cached[0] != fingerprint: return {"status":"failed","request_id":rid,"error_code":"IDEMPOTENCY_CONFLICT"}, False
                response = dict(cached[1]); response.update({"request_id":rid,"deduplicated":True}); return response, False
            if delay: time.sleep(delay)
            view = ProjectStateJEPA().build_live_view(dataset)
            response = {"status":"ok","request_id":rid,"view":view,"deduplicated":False,"service_process_id":multiprocessing.current_process().pid}
            state.execution_count += 1
            if key: cache[key] = (fingerprint, dict(response))
            disconnect = state.disconnect_count > 0
            if disconnect: state.disconnect_count -= 1
        return response, disconnect

    def _send(self, value: dict[str, Any]) -> None:
        self.wfile.write(canonical_bytes(value)+b"\n"); self.wfile.flush()

class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True; daemon_threads = True
    def __init__(self, address: tuple[str,int], shared_ledger: Any = None) -> None:
        super().__init__(address, _Handler); self.state = _State(shared_ledger)

def _serve(ready: Any, shared_ledger: Any = None) -> None:
    with _Server(("127.0.0.1",0), shared_ledger) as server:
        ready.send(server.server_address); ready.close(); server.serve_forever(poll_interval=.05)

class RemoteJEPAService:
    """چرخهٔ عمر خدمت شبکه‌ای، جدا از ثبت رجیستری."""
    def __init__(self, shared_ledger: Any = None) -> None:
        self._process = None; self._address = None; self.shared_ledger = shared_ledger
    @property
    def address(self) -> tuple[str,int]:
        if self._address is None: raise RemoteJEPAError("REMOTE_NOT_RUNNING","خدمت راه‌اندازی نشده است")
        return self._address
    @property
    def process_id(self) -> int|None: return self._process.pid if self._process else None
    @property
    def running(self) -> bool: return self._process is not None and self._process.is_alive()
    def start(self) -> None:
        if self.running: return
        parent, child = multiprocessing.Pipe(duplex=False); process = multiprocessing.Process(target=_serve,args=(child,self.shared_ledger),daemon=True); process.start(); child.close()
        if not parent.poll(5): process.terminate(); process.join(2); raise RemoteJEPAError("REMOTE_START_TIMEOUT","خدمت آماده نشد")
        address=parent.recv(); parent.close(); self._process=process; self._address=(str(address[0]),int(address[1]))
    def crash(self) -> None:
        if self._process and self._process.is_alive(): self._process.terminate(); self._process.join(2)
    def stop(self) -> None: self.crash(); self._process=None; self._address=None

class RemoteJEPAClient:
    """مشتری دارای مهلت، تلاش مجدد محدود و فشار برگشتی کراندار."""
    PROTOCOL_VERSION="0.2"; CAPABILITY_ID="arpaped.project-state.view"
    def __init__(self,address:tuple[str,int],*,timeout:float=2,max_attempts:int=2,max_in_flight:int=2)->None:
        self.address=address; self.timeout=timeout; self.max_attempts=max_attempts; self._capacity=threading.BoundedSemaphore(max_in_flight)
    def build_view(self,dataset:dict[str,Any],*,idempotency_key:str="")->RemoteCallReceipt:
        if not self._capacity.acquire(False): raise RemoteJEPABackpressure("REMOTE_BACKPRESSURE","ظرفیت پر است")
        try:
            last=None
            for attempt in range(1,(self.max_attempts if idempotency_key else 1)+1):
                rid=f"jepa-remote:{uuid4()}"
                try:
                    response=self._exchange({"protocol_version":self.PROTOCOL_VERSION,"capability_id":self.CAPABILITY_ID,"contract_version":"0.1","operation":"build_view","request_id":rid,"idempotency_key":idempotency_key,"dataset":dataset})
                    if response.get("request_id")!=rid: raise RemoteJEPAError("REMOTE_CORRELATION_MISMATCH","پاسخ متعلق به درخواست نیست")
                    if response.get("status")!="ok": raise RemoteJEPAError(str(response.get("error_code","REMOTE_EXECUTION_FAILED")),"خدمت درخواست را رد کرد",response)
                    return RemoteCallReceipt(dict(response["view"]),rid,attempt,bool(response.get("deduplicated")),int(response["service_process_id"]))
                except RemoteJEPAError as exc:
                    last=exc
                    if exc.code not in {"REMOTE_DISCONNECTED","REMOTE_TIMEOUT"}: raise
            assert last is not None; raise last
        finally: self._capacity.release()
    def configure_fault(self,*,disconnect_count:int=0,delay_seconds:float=0)->None:
        """تنظیم شاهد شکست؛ خارج از قرارداد قابلیت عمومی."""
        self._exchange({"operation":"configure_fault","request_id":f"fault:{uuid4()}","disconnect_count":disconnect_count,"delay_seconds":delay_seconds})
    def execution_count(self)->int: return int(self._exchange({"operation":"stats","request_id":f"stats:{uuid4()}"})["execution_count"])
    def raw_exchange(self,request:dict[str,Any])->dict[str,Any]: return self._exchange(request)
    def _exchange(self,request:dict[str,Any])->dict[str,Any]:
        try:
            with socket.create_connection(self.address,timeout=self.timeout) as connection:
                connection.settimeout(self.timeout)
                # جریان پوششی مالک سوکت نیست؛ بستن صریح هر دو از انباشت
                # توصیفگرها در فراخوانی‌های پرتعداد جلوگیری می‌کند.
                with connection.makefile("rwb") as stream:
                    stream.write(canonical_bytes(request)+b"\n"); stream.flush(); return _read(stream)
        except socket.timeout as exc:
            raise RemoteJEPAError("REMOTE_TIMEOUT", "مهلت پایان یافت", {"failure_phase": "ambiguous"}) from exc
        except EOFError as exc:
            raise RemoteJEPAError("REMOTE_DISCONNECTED", "ارتباط پس از ارسال قطع شد", {"failure_phase": "ambiguous"}) from exc
        except (ConnectionError, OSError) as exc:
            # خطای برقراری اتصال پیش از ارسال، برای جابه‌جایی حتی بدون کلید
            # یکتایی امن است؛ هیچ ارائه‌دهنده‌ای درخواست را ندیده است.
            raise RemoteJEPAError("REMOTE_DISCONNECTED", "اتصال برقرار نشد", {"failure_phase": "before_execution"}) from exc
