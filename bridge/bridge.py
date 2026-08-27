"""Coordinates the full capability request path in the local ARPAPED reference.

The bridge is neither a registry, a policy engine, a selector, nor the owner of
component execution. It only routes a standard request through these stages and
returns a stage trace.

Trace stages (in order):
    validated       - Request passed structural validation.
    discovered      - Registry returned compatible implementations.
    policy_evaluated - Policy engine evaluated all candidates.
    selected        - Selector chose one or more candidates for execution.
    executed        - Selected implementation completed successfully.

On failure, the trace contains only the stages reached before the error.
Consumers may use the trace for debugging, auditing, and observability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .policy import PolicyContext, StaticPolicyEngine
from .registry import CapabilityRegistry
from .selector import DeterministicSelector


@dataclass(frozen=True)
class BridgeRequest:
    request_id: str
    capability_id: str
    contract_version: str
    operation: str
    input: dict[str, Any]
    policy_context: PolicyContext

    def validate(self) -> None:
        required = (self.request_id, self.capability_id, self.contract_version, self.operation)
        if any(not value.strip() for value in required):
            raise BridgeError("BRIDGE_INVALID_REQUEST", "validation", "Required request field is empty")
        if not isinstance(self.input, dict):
            raise BridgeError("BRIDGE_INVALID_REQUEST", "validation", "Operation input must be an object")


@dataclass(frozen=True)
class BridgeResponse:
    request_id: str
    capability_id: str
    contract_version: str
    implementation_id: str
    output: dict[str, Any]
    trace: tuple[str, ...]


@dataclass
class BridgeError(Exception):
    code: str
    stage: str
    message: str
    details: Optional[dict[str, Any]] = None

    def __str__(self) -> str:
        return f"{self.code}@{self.stage}: {self.message}"


class Bridge:
    """Coordinates validation, discovery, policy, selection, and execution without merging responsibilities."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        policy: StaticPolicyEngine,
        selector: DeterministicSelector,
    ) -> None:
        self.registry = registry
        self.policy = policy
        self.selector = selector

    def handle(self, request: BridgeRequest) -> BridgeResponse:
        request.validate()
        trace = ["validated"]
        discovered = self.registry.discover(
            request.capability_id, request.contract_version, request.operation,
        )
        trace.append("discovered")
        if not discovered:
            raise BridgeError("BRIDGE_NO_IMPLEMENTATION", "discovery", "No compatible implementation discovered")

        allowed = []
        rejections: dict[str, str] = {}
        for implementation in discovered:
            decision = self.policy.evaluate(implementation, request.policy_context)
            if decision.allowed:
                allowed.append(implementation)
            else:
                rejections[implementation.implementation_id] = decision.reason_code
        trace.append("policy_evaluated")
        if not allowed:
            raise BridgeError("BRIDGE_POLICY_DENIED", "policy", "All compatible candidates were rejected", rejections)

        ranked = self.selector.rank(tuple(allowed)) if hasattr(self.selector, "rank") else (self.selector.select(tuple(allowed)),)
        if not ranked:
            raise BridgeError("BRIDGE_NO_HEALTHY_ROUTE", "selection", "All allowed candidates are temporarily unavailable")
        trace.append("selected")
        failures: dict[str, dict[str, Any]] = {}
        for selected in ranked:
            try:
            # The policy context is part of the execution context of the same
            # request. Passing it to the implementation lets nested dependencies
            # honour the same constraints without making the implementation the
            # final policy arbiter.
                output = selected.executor(request.operation, request.input, request.policy_context)
            except BridgeError as exc:
                details = exc.details or {}
                if len(ranked) == 1 or not details.get("failover_allowed", False):
                    raise
                failures[selected.implementation_id] = {"code": exc.code, "stage": exc.stage, **details}
                if hasattr(self.selector, "record_failure"):
                    self.selector.record_failure(selected.implementation_id)
                continue
            except Exception as exc:
            # Internal implementation details must not cross this boundary; the
            # stable bridge error type is preserved.
                raise BridgeError(
                    "BRIDGE_EXECUTION_FAILED", "execution", "The selected implementation did not execute the request",
                    {"implementation_id": selected.implementation_id, "cause_type": type(exc).__name__},
                ) from exc
            if hasattr(self.selector, "record_success"):
                self.selector.record_success(selected.implementation_id)
            break
        else:
            raise BridgeError(
                "BRIDGE_ALL_IMPLEMENTATIONS_FAILED", "execution",
                "All allowed and selectable implementations failed", failures,
            )
        trace.append("executed")
        return BridgeResponse(
            request_id=request.request_id,
            capability_id=request.capability_id,
            contract_version=request.contract_version,
            implementation_id=selected.implementation_id,
            output=output,
            trace=tuple(trace),
        )