from __future__ import annotations

import hmac
import json
from collections.abc import Callable, Iterable
from dataclasses import asdict
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from mediaflow.application.automation import AutomationJobService
from mediaflow.application.execution_authorization import ExecutionAuthorizationService
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal, SecurityAuditRecord
from mediaflow.domain.task_persistence import ConfirmationStatus


class ApiPermissionDenied(RuntimeError):
    pass


class MediaFlowApi:
    """Small WSGI transport over persistence and queue application boundaries."""

    def __init__(
        self,
        repository,
        bearer_token: str | None,
        schedules=(),
        *,
        principals: tuple[ResolvedApiPrincipal, ...] = (),
        remote_execution_enabled: bool = False,
        remote_execution_maximum_ttl_seconds: int = 900,
    ) -> None:
        if bearer_token and principals:
            raise ValueError("legacy bearer token cannot be combined with API principals")
        if bearer_token:
            principals = (
                ResolvedApiPrincipal("legacy-admin", bearer_token, frozenset(ApiPermission)),
            )
        if not principals:
            raise ValueError("at least one API principal must be configured")
        self._repository = repository
        self._principals = principals
        self._jobs = AutomationJobService(repository)
        self._execution_authorizations = ExecutionAuthorizationService(
            repository, maximum_ttl_seconds=remote_execution_maximum_ttl_seconds
        )
        self._remote_execution_enabled = remote_execution_enabled
        self._schedules = tuple(schedules)

    def __call__(self, environ: dict, start_response: Callable) -> Iterable[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))
        request_id = str(uuid4())
        try:
            if path == "/health" and method == "GET":
                return self._response(start_response, 200, {"status": "ok"})
            if not path.startswith("/api/v1"):
                return self._error(start_response, 404, "not_found", "route was not found")
            principal = self._authenticate(environ)
            if principal is None:
                self._audit(environ, request_id, None, method, path, "authenticate", "denied", 401)
                return self._error(start_response, 401, "unauthorized", "bearer token required")
            self._audit(environ, request_id, principal, method, path, "request", "started", 0)
            statuses = []

            def capture(status, headers):
                statuses.append(int(status.split()[0]))
                return start_response(status, headers)

            result = self._dispatch(method, path, environ, capture, principal)
            status = statuses[0] if statuses else 500
            self._safe_audit(
                environ,
                request_id,
                principal,
                method,
                path,
                "request",
                "allowed" if status < 400 else "denied",
                status,
            )
            return result
        except ApiPermissionDenied as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "permission",
                "denied",
                403,
            )
            return self._error(start_response, 403, "forbidden", str(error))
        except LookupError as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "request",
                "error",
                404,
            )
            return self._error(start_response, 404, "not_found", str(error))
        except (ValueError, json.JSONDecodeError) as error:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "request",
                "denied",
                400,
            )
            return self._error(start_response, 400, "invalid_request", str(error))
        except Exception:
            self._safe_audit(
                environ,
                request_id,
                locals().get("principal"),
                method,
                path,
                "request",
                "error",
                500,
            )
            return self._error(
                start_response, 500, "internal_error", "request failed (details redacted)"
            )

    def _dispatch(
        self,
        method: str,
        path: str,
        environ: dict,
        start_response: Callable,
        principal: ResolvedApiPrincipal,
    ):
        parts = [part for part in path.split("/") if part]
        if parts == ["api", "v1", "security-audit"] and method == "GET":
            self._require(principal, ApiPermission.READ_SECURITY_AUDIT)
            return self._response(
                start_response,
                200,
                {"items": [self._value(item) for item in self._repository.list_security_audit()]},
            )
        if method == "GET":
            self._require(principal, ApiPermission.READ)
        if parts == ["api", "v1", "tasks"] and method == "GET":
            return self._response(
                start_response,
                200,
                {"items": [self._value(item) for item in self._repository.list_tasks(limit=100)]},
            )
        if len(parts) == 4 and parts[:3] == ["api", "v1", "tasks"] and method == "GET":
            task = self._repository.get_task(parts[3])
            if task is None:
                raise LookupError(f"task {parts[3]!r} was not found")
            return self._response(
                start_response,
                200,
                {
                    **self._value(task),
                    "items": [
                        self._value(item) for item in self._repository.list_items(task.task_id)
                    ],
                    "results": [
                        self._value(item) for item in self._repository.list_results(task.task_id)
                    ],
                },
            )
        if parts == ["api", "v1", "confirmations"] and method == "GET":
            values = self._repository.list_confirmations(status=ConfirmationStatus.PENDING)
            return self._response(
                start_response, 200, {"items": [self._value(item) for item in values]}
            )
        if parts == ["api", "v1", "schedules"] and method == "GET":
            states = {item.schedule_id: item for item in self._repository.list_schedule_states()}
            return self._response(
                start_response,
                200,
                {
                    "items": [
                        {
                            **self._value(item),
                            "state": self._value(states.get(item.schedule_id)),
                        }
                        for item in self._schedules
                    ]
                },
            )
        if parts == ["api", "v1", "notifications"] and method == "GET":
            values = self._repository.list_deliveries(limit=100)
            return self._response(
                start_response,
                200,
                {
                    "items": [
                        {
                            "deliveryId": item.delivery_id,
                            "webhookId": item.webhook_id,
                            "eventId": item.event_id,
                            "eventType": item.event_type.value,
                            "status": item.status.value,
                            "attempts": item.attempts,
                            "nextAttemptAt": item.next_attempt_at.isoformat(),
                            "createdAt": item.created_at.isoformat(),
                            "updatedAt": item.updated_at.isoformat(),
                            "deliveredAt": (
                                item.delivered_at.isoformat() if item.delivered_at else None
                            ),
                            "failureCategory": item.failure_category,
                            "responseStatus": item.response_status,
                        }
                        for item in values
                    ]
                },
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "schedules"]
            and parts[4] == "audit"
            and method == "GET"
        ):
            known = {item.schedule_id for item in self._schedules}
            if parts[3] not in known:
                raise LookupError(f"schedule {parts[3]!r} was not found")
            values = self._repository.list_schedule_audit(parts[3], limit=100)
            return self._response(
                start_response, 200, {"items": [self._value(item) for item in values]}
            )
        if parts == ["api", "v1", "jobs"]:
            if method == "GET":
                values = self._repository.list_jobs(limit=100)
                return self._response(
                    start_response, 200, {"items": [self._value(item) for item in values]}
                )
            if method == "POST":
                document = self._document(environ)
                forbidden = {
                    "overwrite",
                    "delete",
                    "executionToken",
                    "authorization",
                }.intersection(document)
                if forbidden:
                    raise ValueError(f"unsupported service field {sorted(forbidden)[0]!r}")
                command = document.get("command", "")
                if command == "organize":
                    self._require(principal, ApiPermission.REMOTE_EXECUTE)
                    if not self._remote_execution_enabled:
                        raise ValueError("remote execution is disabled")
                    if document.get("execute") is not True:
                        raise ValueError("remote organize requires execute=true")
                    token = str(environ.get("HTTP_X_MEDIAFLOW_EXECUTION_TOKEN", ""))
                    job = self._execution_authorizations.submit_organize(
                        token, limit=document.get("limit")
                    )
                else:
                    self._require(principal, ApiPermission.SUBMIT_DRY_RUN)
                    if "execute" in document:
                        raise ValueError("scan/preview cannot request execute authority")
                    job = self._jobs.submit(command, limit=document.get("limit"))
                return self._response(start_response, 202, self._value(job))
        if len(parts) == 4 and parts[:3] == ["api", "v1", "jobs"] and method == "GET":
            job = self._repository.get_job(parts[3])
            if job is None:
                raise LookupError(f"automation job {parts[3]!r} was not found")
            return self._response(start_response, 200, self._value(job))
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "jobs"]
            and parts[4] == "cancel"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.CANCEL_JOB)
            return self._response(start_response, 200, self._value(self._jobs.cancel(parts[3])))
        return self._error(start_response, 404, "not_found", "route was not found")

    def _authenticate(self, environ: dict) -> ResolvedApiPrincipal | None:
        header = str(environ.get("HTTP_AUTHORIZATION", ""))
        prefix = "Bearer "
        presented = header[len(prefix) :] if header.startswith(prefix) else ""
        matched = None
        for principal in self._principals:
            if hmac.compare_digest(presented, principal.token):
                matched = principal
        return matched

    @staticmethod
    def _require(principal: ResolvedApiPrincipal, permission: ApiPermission) -> None:
        if permission not in principal.permissions:
            raise ApiPermissionDenied(f"principal lacks {permission.value} permission")

    def _audit(
        self,
        environ,
        request_id,
        principal,
        method,
        path,
        action,
        outcome,
        status,
    ) -> None:
        source_parts = str(environ.get("REMOTE_ADDR", "")).split()
        source = source_parts[0][:128] if source_parts else None
        self._repository.append_security_audit(
            SecurityAuditRecord(
                str(uuid4()),
                datetime.now(UTC),
                principal.principal_id if principal else None,
                method[:16],
                self._audit_route(path),
                action,
                outcome,
                status,
                request_id,
                source,
            )
        )

    @staticmethod
    def _audit_route(path: str) -> str:
        parts = [part for part in path.split("/") if part]
        exact = {
            ("api", "v1", "tasks"),
            ("api", "v1", "confirmations"),
            ("api", "v1", "schedules"),
            ("api", "v1", "notifications"),
            ("api", "v1", "jobs"),
            ("api", "v1", "security-audit"),
        }
        key = tuple(parts)
        if key in exact:
            return "/" + "/".join(parts)
        if len(parts) == 4 and parts[:3] in (
            ["api", "v1", "tasks"],
            ["api", "v1", "jobs"],
        ):
            return f"/api/v1/{parts[2]}/{{id}}"
        if len(parts) == 5 and parts[:3] == ["api", "v1", "jobs"] and parts[4] == "cancel":
            return "/api/v1/jobs/{id}/cancel"
        if len(parts) == 5 and parts[:3] == ["api", "v1", "schedules"] and parts[4] == "audit":
            return "/api/v1/schedules/{id}/audit"
        return "/api/v1/<unmatched>"

    def _safe_audit(self, *args) -> None:
        try:
            self._audit(*args)
        except Exception:
            pass

    @staticmethod
    def _document(environ: dict) -> dict:
        raw_length = environ.get("CONTENT_LENGTH", "0") or "0"
        try:
            length = int(raw_length)
        except ValueError as error:
            raise ValueError("invalid Content-Length") from error
        if length < 0 or length > 16_384:
            raise ValueError("request body exceeds 16384 bytes")
        raw = environ["wsgi.input"].read(length)
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("request JSON must be an object")
        return value

    @classmethod
    def _value(cls, value):
        if hasattr(value, "__dataclass_fields__"):
            return {key: cls._value(item) for key, item in asdict(value).items()}
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, tuple):
            return [cls._value(item) for item in value]
        if isinstance(value, dict):
            return {str(key): cls._value(item) for key, item in value.items()}
        return value

    @staticmethod
    def _response(start_response: Callable, status: int, document: dict) -> list[bytes]:
        body = json.dumps(document, ensure_ascii=False, sort_keys=True).encode("utf-8")
        labels = {
            200: "OK",
            202: "Accepted",
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            500: "Internal Server Error",
        }
        start_response(
            f"{status} {labels[status]}",
            [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]

    @classmethod
    def _error(cls, start_response: Callable, status: int, code: str, message: str):
        return cls._response(start_response, status, {"error": {"code": code, "message": message}})
