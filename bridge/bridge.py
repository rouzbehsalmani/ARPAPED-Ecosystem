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

import re
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Optional

from .policy import PolicyContext, StaticPolicyEngine
from .registry import INPUT_TYPE_CHECKS, CapabilityRegistry, InputField, ResolvedCapability
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


def _apply_input_schema(
    operation: str, input: dict[str, Any], input_schema: tuple[InputField, ...],
) -> dict[str, Any]:
    """Checks `input` against one operation's contract-declared shape
    (2-RULES.md "No silent defaults on what resolution depends on") --
    required fields present, and a present field's runtime value matching
    its declared type (`INPUT_TYPE_CHECKS`, bridge/registry.py) -- and
    returns the EFFECTIVE input an executor should actually receive: a
    copy of `input` with every declared field that's absent and has a
    declared default filled in. A field the contract doesn't declare is
    never rejected: additive, not strict. `input_schema` empty (e.g.
    registered without a `root`, see assembler.py) means nothing is
    checked or filled in here -- the same "invisible until resolved"
    posture domain/family/tags have.

    This is deliberately everything a hand-written per-executor check
    used to do for required-ness, type, default value, minimum/maximum
    length, a regular expression, and a fixed set of allowed values
    (`InputField.min_length`/`max_length`/`pattern`/`enum_values`,
    bridge/registry.py) — every one of these is generic and structural,
    checkable without any capability-specific understanding, so none of
    it is an executor's job any more. `min_length` alone does not mean
    "not blank" (a whitespace-only string has nonzero length) --
    `pattern` is what actually expresses that kind of constraint. A
    filled-in default is never re-checked against any of these here:
    `bridge/assembler.py` already guarantees a declared default satisfies
    its own field's other constraints, at assembly time, once — the same
    value would just pass again on every request. The caller's own
    `input` (on `BridgeRequest`, and in the trace/response) is never
    touched by this -- only the copy handed to the executor gains the
    filled-in defaults, so what the caller actually sent stays observable.
    """

    effective = dict(input)
    for field_spec in input_schema:
        if field_spec.name not in effective:
            if field_spec.required:
                raise BridgeError(
                    "INVALID_INPUT", "execution",
                    f"{field_spec.name!r} is required for operation {operation!r} but was not provided",
                )
            if field_spec.has_default:
                effective[field_spec.name] = field_spec.default
            continue
        value = effective[field_spec.name]
        check = INPUT_TYPE_CHECKS.get(field_spec.type)
        if check is not None and not check(value):
            raise BridgeError(
                "INVALID_INPUT", "execution",
                f"{field_spec.name!r} must be of type {field_spec.type!r} for operation {operation!r}, "
                f"got {type(value).__name__}",
            )
        if field_spec.type == "string":
            if field_spec.min_length is not None and len(value) < field_spec.min_length:
                raise BridgeError(
                    "INVALID_INPUT", "execution",
                    f"{field_spec.name!r} must be at least {field_spec.min_length} character(s) long "
                    f"for operation {operation!r}, got {len(value)}",
                )
            if field_spec.max_length is not None and len(value) > field_spec.max_length:
                raise BridgeError(
                    "INVALID_INPUT", "execution",
                    f"{field_spec.name!r} must be at most {field_spec.max_length} character(s) long "
                    f"for operation {operation!r}, got {len(value)}",
                )
            if field_spec.pattern is not None and not re.search(field_spec.pattern, value):
                raise BridgeError(
                    "INVALID_INPUT", "execution",
                    f"{field_spec.name!r} must match pattern {field_spec.pattern!r} for operation "
                    f"{operation!r}, got {value!r}",
                )
        if field_spec.enum_values is not None and value not in field_spec.enum_values:
            raise BridgeError(
                "INVALID_INPUT", "execution",
                f"{field_spec.name!r} must be one of {list(field_spec.enum_values)!r} for operation "
                f"{operation!r}, got {value!r}",
            )
    return effective


class BoundCapability:
    """A capability+operation resolved once, callable many times.

    Returned by `Bridge.resolve(...)`. Holds a `ResolvedCapability` (the
    Registry's discovery cache — see registry.py) plus the identity fields
    needed to build a request. Only discovery is reused across calls: policy
    is evaluated and a candidate is selected and executed fresh every time
    `call` runs, through the same `Bridge.handle` every other request goes
    through.
    """

    def __init__(
        self,
        bridge: "Bridge",
        resolved: ResolvedCapability,
        capability_id: str,
        operation: str,
        contract_version: str,
    ) -> None:
        self._bridge = bridge
        self._resolved = resolved
        self._capability_id = capability_id
        self._operation = operation
        self._contract_version = contract_version

    def call(
        self,
        input: dict[str, Any],
        policy_context: Optional[PolicyContext] = None,
        on_stage: Optional[Callable[[str], None]] = None,
    ) -> BridgeResponse:
        request = BridgeRequest(
            request_id=uuid.uuid4().hex,
            capability_id=self._capability_id,
            contract_version=self._contract_version,
            operation=self._operation,
            input=input,
            policy_context=policy_context
            or PolicyContext(user={}, consumer={}, ecosystem={}, provider={}, module={}),
        )
        return self._bridge.handle(request, resolved=self._resolved, on_stage=on_stage)

    def call_with_timeout(
        self,
        input: dict[str, Any],
        policy_context: Optional[PolicyContext] = None,
        stage_timeout: float = 10.0,
    ) -> BridgeResponse:
        """Same as `call`, but bounded (see `Bridge.handle_with_timeout`) —
        a stage that never progresses raises `BRIDGE_STAGE_TIMEOUT` instead
        of blocking indefinitely. Useful on its own, and for a dependency
        handle held by a capability-composing executor factory (see
        `Dependencies`): a hang three levels deep gets caught at the level
        it actually happens, independently of whatever budget an outer
        caller set for itself.
        """
        request = BridgeRequest(
            request_id=uuid.uuid4().hex,
            capability_id=self._capability_id,
            contract_version=self._contract_version,
            operation=self._operation,
            input=input,
            policy_context=policy_context
            or PolicyContext(user={}, consumer={}, ecosystem={}, provider={}, module={}),
        )
        return self._bridge.handle_with_timeout(request, resolved=self._resolved, stage_timeout=stage_timeout)


class Dependencies:
    """Given once, at startup or assembly time, to whatever needs a
    declared, version-pinned view of other capabilities — never to a
    component's ordinary executor. Two callers use it: a capability's
    executor FACTORY (see the manifest's optional `executor_kind: factory`,
    bridge/assembler.py), scoped to what its own contract declared under
    `dependencies.capabilities` (R4); and an application's single
    request-construction point (R6), scoped to its own declared-dependencies
    file, so it can resolve without restating a version at every call site
    — the same mechanism, the same enforcement, just declared in a
    different place. Mirrors `Bridge.resolve` exactly, but scoped to
    exactly the capability ids `declared` names: resolving anything else
    raises `BRIDGE_UNDECLARED_DEPENDENCY`, which is what makes the declared
    list an enforced runtime boundary, not just documentation.

    A caller resolves `(...)` once per operation it needs and closes over
    the returned `BoundCapability`; the executor closure (or application
    code) calls `.call(...)` (or `.call_with_timeout(...)`) on that handle
    per invocation — the same "discover once, call many times" shape used
    everywhere else in this reference Bridge. Every resulting call is a
    real, fully-traced Bridge request (R6/R8) — never a raw executor-to-
    executor call.

    `declared` maps each allowed capability_id to the version constraint
    actually declared for it (bare-string dependencies mean `"*"`, any
    version — see `bridge/assembler.py`'s `parse_dependencies`). `resolve`
    always uses that declared constraint; it is not a parameter the caller
    can choose, so a dependency's interface changing out from under a
    dependent can never silently reach it — the dependent keeps resolving
    to whatever still satisfies the version it was actually built against,
    or fails loudly (`BRIDGE_NO_IMPLEMENTATION`) if nothing does.
    """

    def __init__(self, bridge: "Bridge", declared: dict[str, str]) -> None:
        self._bridge = bridge
        self._declared = declared

    def resolve(self, capability_id: str, operation: str, **kwargs: Any) -> BoundCapability:
        if capability_id not in self._declared:
            raise BridgeError(
                "BRIDGE_UNDECLARED_DEPENDENCY", "validation",
                f"{capability_id!r} is not declared in this Dependencies' declared "
                "capabilities — add it there before depending on it",
            )
        return self._bridge.resolve(capability_id, operation, self._declared[capability_id], **kwargs)


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

    def resolve(self, capability_id: str, operation: str, contract_version: str, **kwargs: Any) -> BoundCapability:
        """Discovers `capability_id`+`operation` once and returns a handle whose
        `call(...)` re-runs policy, selection, and execution on every use but
        reuses that discovery (see `BoundCapability`). `kwargs` forward to
        `CapabilityRegistry.resolve` (`exact_version`, `implementation_id`,
        `family`, `domain`, `tags`) for callers that need a cascade level
        other than Scoped.

        `contract_version` has no default. A default would mean "whichever
        version wins tie-breaking" — an implicit choice the caller never
        actually made, and implicit choices are exactly what silently
        resolve to the wrong candidate. Pass `"*"` explicitly if any
        version genuinely will do; the point is that the caller decides,
        never the Bridge.
        """
        resolved = self.registry.resolve(capability_id, operation, contract_version, **kwargs)
        return BoundCapability(self, resolved, capability_id, operation, contract_version)

    def handle(
        self,
        request: BridgeRequest,
        resolved: Optional[ResolvedCapability] = None,
        on_stage: Optional[Callable[[str], None]] = None,
    ) -> BridgeResponse:
        """Runs the full request path. `resolved` is an optional handle from
        `CapabilityRegistry.resolve(...)`: when given, its cached candidate ids are
        re-checked live instead of re-running the discovery cascade, so a caller that
        expects to invoke the same capability+operation many times can discover once
        and still get a fresh discovered/policy_evaluated/selected/executed trace on
        every call. Policy, selection, and execution are unaffected either way.

        `on_stage`, when given, is called synchronously with each stage name the
        instant it is reached — the same five stages the returned trace carries,
        just observable live instead of only once the whole call returns. This is
        what lets a caller (see `handle_with_timeout`) tell where a call is stuck
        while it is still running, rather than only after it finally returns (or
        never does).
        """
        trace: list[str] = []

        def _reached(stage: str) -> None:
            trace.append(stage)
            if on_stage is not None:
                on_stage(stage)

        request.validate()
        _reached("validated")
        if resolved is not None:
            discovered = resolved.live_candidates()
        else:
            discovered = self.registry.discover(
                request.capability_id, request.contract_version, request.operation,
            )
        _reached("discovered")
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
        _reached("policy_evaluated")
        if not allowed:
            raise BridgeError("BRIDGE_POLICY_DENIED", "policy", "All compatible candidates were rejected", rejections)

        ranked = self.selector.rank(tuple(allowed)) if hasattr(self.selector, "rank") else (self.selector.select(tuple(allowed)),)
        if not ranked:
            raise BridgeError("BRIDGE_NO_HEALTHY_ROUTE", "selection", "All allowed candidates are temporarily unavailable")
        _reached("selected")
        # Every candidate here shares the same capability_id+operation+contract_version,
        # hence the same contract-declared input shape (R2) -- checked once,
        # against any one of them, outside the retry loop below: a schema
        # mismatch is invalid input, not a candidate-specific failure, so
        # failing over to a different candidate could never fix it. The
        # returned effective_input (declared defaults filled in) is what
        # every executor below actually receives; request.input itself,
        # used everywhere else (trace, response), stays exactly what the
        # caller sent.
        effective_input = _apply_input_schema(
            request.operation, request.input, ranked[0].input_schema.get(request.operation, ()),
        )
        failures: dict[str, dict[str, Any]] = {}
        for selected in ranked:
            try:
            # The policy context is part of the execution context of the same
            # request. Passing it to the implementation lets nested dependencies
            # honour the same constraints without making the implementation the
            # final policy arbiter.
                output = selected.executor(request.operation, effective_input, request.policy_context)
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
        _reached("executed")
        return BridgeResponse(
            request_id=request.request_id,
            capability_id=request.capability_id,
            contract_version=request.contract_version,
            implementation_id=selected.implementation_id,
            output=output,
            trace=tuple(trace),
        )

    def handle_with_timeout(
        self,
        request: BridgeRequest,
        resolved: Optional[ResolvedCapability] = None,
        stage_timeout: float = 10.0,
    ) -> BridgeResponse:
        """Runs `handle` under a bounded per-stage timeout instead of an
        unbounded wait (R5): if no new trace stage is reached within
        `stage_timeout` seconds of the last one (or of the call starting),
        raises `BridgeError("BRIDGE_STAGE_TIMEOUT", <last stage reached, or
        "start">, ..., details={"trace": <the partial stages genuinely
        observed so far>})` instead of blocking indefinitely. That partial
        trace is real, observed data — it simply never reaches `executed`,
        which is exactly what makes it a failure, never something to wait
        longer for.

        Runs `handle` on a background thread and watches its `on_stage`
        calls from this thread. That background thread is NOT forcibly
        killed if it never returns — Python cannot safely do that — so this
        is a detection net for an unattended pipeline (surface a stuck call
        fast, with evidence of where it stuck), not a substitute for R5's
        requirement that an operation itself must not block indefinitely.
        """

        result: dict[str, Any] = {}
        done = threading.Event()
        lock = threading.Lock()
        stages: list[str] = []
        last_update = [time.monotonic()]

        def _on_stage(stage: str) -> None:
            with lock:
                stages.append(stage)
                last_update[0] = time.monotonic()

        def _run() -> None:
            try:
                result["response"] = self.handle(request, resolved=resolved, on_stage=_on_stage)
            except BridgeError as exc:
                result["error"] = exc
            except Exception as exc:
                result["error"] = BridgeError(
                    "BRIDGE_EXECUTION_FAILED", "execution", "The selected implementation did not execute the request",
                    {"cause_type": type(exc).__name__},
                )
            finally:
                done.set()

        threading.Thread(target=_run, daemon=True).start()

        while not done.wait(timeout=0.05):
            with lock:
                elapsed = time.monotonic() - last_update[0]
                observed = list(stages)
            if elapsed > stage_timeout:
                last_stage = observed[-1] if observed else "start"
                raise BridgeError(
                    "BRIDGE_STAGE_TIMEOUT", last_stage,
                    f"No trace progress within {stage_timeout}s after {last_stage!r}",
                    {"trace": observed},
                )

        if "error" in result:
            raise result["error"]
        return result["response"]