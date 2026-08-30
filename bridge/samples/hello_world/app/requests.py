"""Single request-construction point for this sample app (Phase 6, R6).

Exactly one module builds requests and calls the Bridge's handle operation:
build a registry; assemble every manifest found under capabilities/ into it
(Phase 8 mechanics, step 5); construct the Bridge from that registry plus
the policy and selector resolved from bridge/MANIFEST.yaml. It then exposes
one `call` operation. Nothing else in this sample constructs a request or
calls the Bridge directly.
"""

import uuid
from pathlib import Path

import yaml

from bridge.assembler import assemble
from bridge.bridge import Bridge, BridgeRequest
from bridge.policy import PolicyContext, StaticPolicyEngine
from bridge.registry import CapabilityRegistry
from bridge.selector import DeterministicSelector

_APP_ROOT = Path(__file__).resolve().parent.parent

_registry = CapabilityRegistry()
for _manifest_path in sorted((_APP_ROOT / "capabilities").rglob("manifest.yaml")):
    assemble(yaml.safe_load(_manifest_path.read_text(encoding="utf-8")), _registry)

_bridge = Bridge(_registry, StaticPolicyEngine(), DeterministicSelector())


def call(capability_id, operation, input, policy_context=None):
    request = BridgeRequest(
        request_id=uuid.uuid4().hex,
        capability_id=capability_id,
        contract_version=">=1.0.0",
        operation=operation,
        input=input,
        policy_context=policy_context
        or PolicyContext(user={}, consumer={}, ecosystem={}, provider={}, module={}),
    )
    return _bridge.handle(request)
