"""Shared idempotency ledger v0.1 for coordinating effects across hosts.

The ledger is independent of the request pipeline, the bridge, and the selector.
The process manager is just the local reference implementation of the contract
and can be swapped for another implementation without changing consumers.
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

@dataclass
class SharedIdempotencyLedger:
    """Owns the storage lifecycle and atomic operations of the shared record."""
    manager: Any
    entries: Any
    lock: Any
    implementation_id: str = "arpaped.shared-idempotency.manager-reference"

    @classmethod
    def start(cls) -> "SharedIdempotencyLedger":
        # An explicit network address is independent of the ephemeral Unix
        # socket and keeps the reference multi-host boundary even in restricted
        # environments.
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
            raise BridgeError("BRIDGE_UNSUPPORTED_OPERATION", "execution", "Ledger operation is not supported")
        with self.lock:
            present = self.entries.get(str(input_record.get("idempotency_key", ""))) is not None
        return {"present": present, "status": "completed" if present else "missing"}

def register_shared_idempotency(registry: CapabilityRegistry) -> SharedIdempotencyLedger:
    """The management cycle starts the ledger and registers it."""
    ledger = SharedIdempotencyLedger.start()
    registry.register(ledger.descriptor())
    return ledger