"""رابط خط فرمان مرجع برای اجرای یک درخواست واقعی از مسیر پل محلی."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dep.canonical import canonical_bytes

from .bridge import BridgeRequest
from .dep_adapter import build_dep_bridge
from .policy import PolicyContext


def _write(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(canonical_bytes(record) + b"\n")
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="arpaped-bridge", description="اجرای درخواست قابلیت از مسیر پل")
    parser.add_argument("request", type=Path)
    parser.add_argument("--event-store", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    loaded = json.loads(args.request.read_text(encoding="utf-8"))
    context = loaded["policy_context"]
    request = BridgeRequest(
        request_id=str(loaded["request_id"]),
        capability_id=str(loaded["capability_id"]),
        contract_version=str(loaded["contract_version"]),
        operation=str(loaded["operation"]),
        input=dict(loaded["input"]),
        policy_context=PolicyContext(
            user=dict(context["user"]), consumer=dict(context["consumer"]),
            ecosystem=dict(context["ecosystem"]), provider=dict(context["provider"]),
            module=dict(context["module"]),
        ),
    )
    response = build_dep_bridge(args.event_store)[0].handle(request)
    record = {
        "request_id": response.request_id,
        "capability_id": response.capability_id,
        "contract_version": response.contract_version,
        "implementation_id": response.implementation_id,
        "output": response.output,
        "trace": list(response.trace),
    }
    _write(args.output, record)
    print(canonical_bytes(record).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
