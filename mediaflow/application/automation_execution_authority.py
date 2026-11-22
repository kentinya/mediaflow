"""Live execution authority for definition-pinned scheduled and Run once work.

The independent unattended grant product is retired.  Current authority is the
published Enabled definition (scheduled) or one explicit Run once command
(single run), checked against the *actual current* configured principal
permission at admission and again at every unperformed effect boundary.  The
publication evidence, current-configuration permission and Task admission
principal come from ``automation_execution_intent`` and the runtime
repository; no grant row can ever supply them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from mediaflow.application.automation_execution_intent import (
    ExecutionPrincipal,
    ScheduleContinuityStopped,
)
from mediaflow.domain.automation import AutomationTaskDefinition
from mediaflow.domain.manual_safety import redact_evidence_text
from mediaflow.domain.security import ApiPermission
from mediaflow.domain.unattended_execution import CurrentPermissionAuthority


class AutomationExecutionIntentError(ValueError):
    """Bounded, operator-actionable current execution intent error."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "automation_execution_intent_rejected",
        status: int = 409,
        durable_state: str = "no media mutation occurred",
        retry_safe: bool = True,
        next_action: str = "inspect the current publication and permission state, then retry",
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.durable_state = _bounded(durable_state, 256, "durable state")
        self.retry_safe = retry_safe
        self.next_action = _bounded(next_action, 512, "next action")
        self.details = dict(details or {})


class AutomationIntentBoundaryError(RuntimeError):
    """Current intent disappeared or changed at one per-item mutation boundary."""

    def __init__(
        self,
        *,
        category: str,
        reason: str,
        next_action: str,
        retry_safe: bool = True,
    ) -> None:
        self.category = _bounded(category, 96, "intent boundary category")
        self.reason = _bounded(reason, 256, "intent boundary reason")
        self.next_action = _bounded(next_action, 512, "intent boundary next action")
        self.retry_safe = retry_safe
        self.durable_state = "completed sibling effects are preserved; this item was not mutated"
        super().__init__(self.safe_message)

    @property
    def safe_message(self) -> str:
        return redact_evidence_text(
            f"{self.category}: {self.reason}; next action: {self.next_action}",
            limit=1000,
        )


@dataclass(frozen=True)
class AutomationExecutionAuthorityDecision:
    """The live intent admitted for one claimed occurrence."""

    principal_id: str | None
    run_once: bool


class AutomationExecutionAuthority:
    """Current-intent admission and per-boundary checks over live evidence.

    This is the one authority for definition-pinned scheduled and Run once
    work.  It owns no persistence and never issues, reads or revokes a grant:
    the publisher identity comes from real publication evidence, the Run once
    principal comes from the admitted Task's scheduling row, and permission is
    always the current configured permission authority.
    """

    def __init__(
        self,
        repository,
        *,
        permission_authority: CurrentPermissionAuthority | None = None,
        publication_principal_resolver: Callable[[object, AutomationTaskDefinition], str | None]
        | None = None,
        live_definition_resolver: Callable[[str], object | None] | None = None,
        live_intent_checker: Callable[[object, AutomationTaskDefinition], None] | None = None,
    ) -> None:
        self._repository = repository
        self._permission_authority = permission_authority
        # The principal that published the current Enabled definition is real
        # configuration evidence.  It is supplied by the production consumer
        # (the current Active activation), never by a browser or ``--actor``.
        self._publication_principal_resolver = publication_principal_resolver
        # The Worker's current-Active definition read.  A disabled or removed
        # definition stops future scheduled effects at the next safe boundary.
        self._live_definition_resolver = live_definition_resolver
        self._live_intent_checker = live_intent_checker

    def authorize_task(
        self, task, definition, *, run_once: bool
    ) -> AutomationExecutionAuthorityDecision:
        """Admit the current intent for one already-admitted Task.

        A scheduled occurrence must still be an Enabled published definition
        at this boundary and its publishing principal must currently hold the
        scheduled execution capability.  A Run once Task carries its own
        explicit principal and only needs the current manual-execution
        permission; a disabled schedule is deliberately runnable once.
        """

        definition = _definition(definition)
        if not run_once and not definition.enabled:
            raise AutomationExecutionIntentError(
                "the pinned Automation Task Definition is disabled; no scheduled work was started",
                code="definition_disabled",
                durable_state="no Task, adapter, Provider request, or media effect was created",
                next_action=(
                    "enable the definition in a checked published successor, or use Run once "
                    "for one deliberate execution"
                ),
                details={"definitionId": definition.definition_id},
            )
        principal = self._intent_principal(task, definition, run_once=run_once)
        permission = (
            ApiPermission.EXECUTE_MANUAL_ORGANIZE
            if run_once
            else ApiPermission.GRANT_UNATTENDED_EXECUTION
        )
        self._assert_current_permission(principal, permission=permission, boundary=False)
        if not run_once:
            self._assert_live_definition(definition, boundary=False)
            self._assert_intent_continuity(task, definition)
        return AutomationExecutionAuthorityDecision(
            principal_id=principal.principal_id
            if isinstance(principal, ExecutionPrincipal)
            else principal,
            run_once=run_once,
        )

    def authorize(self, task, definition) -> AutomationExecutionAuthorityDecision:
        """Task-shaped wrapper for callers without an explicit trigger."""

        return self.authorize_task(task, definition, run_once=_task_run_once(task))

    def assert_live(self, task, definition) -> None:
        """Task-shaped per-effect boundary wrapper."""

        self.assert_live_task(task, definition, run_once=_task_run_once(task))

    def assert_live_task(self, task, definition, *, run_once: bool) -> None:
        """Re-read current permission and schedule state at one effect boundary."""

        definition = _definition(definition)
        try:
            if not run_once and not definition.enabled:
                raise AutomationExecutionIntentError(
                    "the scheduled definition was disabled; remaining effects were stopped",
                    code="definition_disabled",
                    durable_state="completed sibling effects are preserved",
                    next_action=(
                        "inspect the completed items and use a new Enabled revision if wanted"
                    ),
                )
            principal = self._intent_principal(task, definition, run_once=run_once)
            permission = (
                ApiPermission.EXECUTE_MANUAL_ORGANIZE
                if run_once
                else ApiPermission.GRANT_UNATTENDED_EXECUTION
            )
            self._assert_current_permission(principal, permission=permission, boundary=True)
            if not run_once:
                self._assert_live_definition(definition, boundary=True)
                self._assert_intent_continuity(task, definition)
        except AutomationExecutionIntentError as error:
            raise AutomationIntentBoundaryError(
                category=error.code,
                reason=str(error),
                next_action=error.next_action,
                retry_safe=error.retry_safe,
            ) from error

    def _intent_principal(
        self, task, definition: AutomationTaskDefinition, *, run_once: bool
    ) -> str | ExecutionPrincipal:
        if run_once:
            reader = getattr(self._repository, "get_task_scheduling", None)
            state = reader(task.task_id) if callable(reader) else None
            principal = getattr(state, "admission_principal", None)
            if isinstance(principal, str) and principal.strip():
                return principal.strip()
            raise AutomationExecutionIntentError(
                "the Run once Task has no explicit principal; no work was started",
                code="run_once_principal_missing",
                durable_state="no Task, adapter, Provider request, or media effect was created",
                next_action="start Run once again from an authenticated session",
                details={"definitionId": definition.definition_id},
            )
        resolver = self._publication_principal_resolver
        if resolver is not None:
            try:
                value = resolver(task, definition)
            except Exception as error:
                raise AutomationExecutionIntentError(
                    "the Enabled definition's publication principal could not be read",
                    code="automation_execution_principal_unavailable",
                    status=503,
                    durable_state=(
                        "no Task, adapter, Provider request, Storage probe, or media effect "
                        "was created"
                    ),
                    next_action=(
                        "restore the managed configuration authority, then let the next due "
                        "occurrence execute; no retry is needed"
                    ),
                ) from error
            if isinstance(value, ExecutionPrincipal):
                return value
            if isinstance(value, str) and value.strip():
                return value.strip()
        raise AutomationExecutionIntentError(
            "the Enabled definition has no verifiable publication principal; no scheduled "
            "work was started",
            code="automation_execution_principal_missing",
            durable_state="no Task, adapter, Provider request, or media effect was created",
            next_action=(
                "publish the Enabled definition again through a checked configuration Save so "
                "its real publication authority is recorded"
            ),
            details={"definitionId": definition.definition_id},
        )

    def _assert_intent_continuity(self, task, definition):
        if self._live_intent_checker is None:
            return
        try:
            self._live_intent_checker(task, definition)
        except ScheduleContinuityStopped as error:
            # The published revision chain proves that the plan was disabled
            # after this occurrence was admitted.  Keep that confirmed reason
            # distinct from an unreadable chain so the execution record can
            # explain the stop and the already-admitted Task can stay stopped.
            raise AutomationExecutionIntentError(
                "the admitted schedule was disabled by a published revision; "
                "this occurrence is stopped",
                code="schedule_disabled",
                durable_state="completed effects are retained; no further effect was started",
                next_action=(
                    "wait for the next normal scheduled run; it is admitted as a new Task "
                    "and this stopped Task remains in the execution records"
                ),
            ) from error
        except Exception as error:
            raise AutomationExecutionIntentError(
                "the admitted schedule was stopped or its publication continuity is unavailable",
                code="scheduled_intent_stopped",
                durable_state="completed effects are retained; no further effect was started",
                next_action=(
                    "inspect existing results; use the next normal due run, "
                    "never replay the stopped occurrence"
                ),
            ) from error

    def _assert_live_definition(
        self, definition: AutomationTaskDefinition, *, boundary: bool
    ) -> None:
        if self._live_definition_resolver is None:
            return
        try:
            current = self._live_definition_resolver(definition.definition_id)
        except Exception as error:
            raise AutomationExecutionIntentError(
                "the current published definition state could not be read",
                code="automation_execution_state_unavailable",
                status=503,
                durable_state="no further media effect was started",
                next_action=(
                    "restore the managed configuration authority; completed effects are "
                    "preserved and no retry is automatic"
                ),
            ) from error
        if current is None:
            raise AutomationExecutionIntentError(
                "the scheduled definition was removed; remaining effects were stopped",
                code="definition_removed",
                durable_state="completed sibling effects are preserved",
                next_action="inspect the completed items; a removed definition cannot be replayed",
            )
        enabled = (
            current.get("enabled")
            if isinstance(current, Mapping)
            else getattr(current, "enabled", None)
        )
        if enabled is not True:
            raise AutomationExecutionIntentError(
                "the scheduled definition was disabled; remaining effects were stopped",
                code="definition_disabled",
                durable_state="completed sibling effects are preserved",
                next_action="inspect the completed items and enable a reviewed successor if wanted",
            )

    def _assert_current_permission(
        self,
        principal_id: str,
        *,
        boundary: bool,
        permission: ApiPermission = ApiPermission.GRANT_UNATTENDED_EXECUTION,
    ) -> None:
        if isinstance(principal_id, ExecutionPrincipal):
            if principal_id.trusted_local:
                import os

                if principal_id.principal_id != f"local:{os.getuid()}":
                    raise AutomationExecutionIntentError(
                        "the trusted local publisher identity is no longer available",
                        code="automation_execution_principal_unavailable",
                        next_action=(
                            "publish a reviewed successor from the current trusted local boundary"
                        ),
                    )
                return
            principal_id = principal_id.principal_id
        if self._permission_authority is None:
            # Lightweight direct callers from the pre-managed runtime do not
            # have a configured authority to consult. Production API/Worker
            # composition always injects one and therefore fails closed.
            return
        try:
            allowed = self._permission_authority.has_permission(principal_id, permission)
        except Exception:
            error = AutomationExecutionIntentError(
                "current configured principal permission authority could not be read",
                code="unattended_permission_authority_unavailable",
                status=503,
                durable_state=(
                    "no Task, adapter, Provider request, Storage probe, or media effect was created"
                ),
                next_action=(
                    "restore the current permission authority, then explicitly resume the "
                    "occurrence"
                ),
            )
            if not boundary:
                raise error from error
            raise AutomationIntentBoundaryError(
                category="unattended_permission_authority_unavailable",
                reason="current configured principal permission authority could not be read",
                next_action=(
                    "restore the current permission authority, then explicitly resume the "
                    "occurrence"
                ),
            ) from error
        if allowed is not True:
            label = permission.value
            error = AutomationExecutionIntentError(
                f"the publishing principal no longer has {label} permission",
                code="unattended_permission_invalid",
                durable_state=(
                    "no Task, adapter, Provider request, Storage probe, or media effect was created"
                ),
                next_action=(
                    "restore that principal's current permission, or publish a reviewed Enabled "
                    "successor from a principal that has it"
                ),
            )
            if not boundary:
                raise error
            raise AutomationIntentBoundaryError(
                category="unattended_permission_invalid",
                reason=f"the publishing principal no longer has {label} permission",
                next_action=(
                    "restore that principal's current permission; completed effects are preserved"
                ),
            ) from error


def _definition(value):
    if isinstance(value, AutomationTaskDefinition):
        return value
    if isinstance(value, Mapping):
        return AutomationTaskDefinition.from_document(value)
    raise ValueError("Automation Task Definition is invalid")


def _bounded(value: object, maximum: int, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\x00" in value:
        raise ValueError(f"automation execution {label} is invalid")
    return value.strip()


def _task_run_once(task) -> bool:
    origin = getattr(task, "execution_origin", None)
    if isinstance(origin, str):
        return origin in {"run-once", "run_once"}
    trigger = getattr(getattr(task, "admission_trigger", None), "value", None)
    return trigger == "run_once"


__all__ = [
    "AutomationExecutionAuthority",
    "AutomationExecutionAuthorityDecision",
    "AutomationExecutionIntentError",
    "AutomationIntentBoundaryError",
]
