from __future__ import annotations

import hmac
import json
from collections.abc import Callable, Iterable
from dataclasses import asdict
from datetime import UTC, datetime
from enum import Enum
from urllib.parse import parse_qs
from uuid import uuid4

from mediaflow.application.automation import AutomationJobService
from mediaflow.application.classification_review import ClassificationReviewService
from mediaflow.application.conflict_resolution import ConfirmationService
from mediaflow.application.dashboard import DashboardService
from mediaflow.application.execution_authorization import ExecutionAuthorizationService
from mediaflow.application.metadata_review import MetadataReviewService
from mediaflow.domain.logging import LogLevel
from mediaflow.domain.notification import NotificationDeliveryStatus
from mediaflow.domain.organizer import ConflictStrategy
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal, SecurityAuditRecord
from mediaflow.domain.task_persistence import ConfirmationStatus
from mediaflow.interfaces.operator_ui import ASSETS as OPERATOR_UI_ASSETS
from mediaflow.interfaces.pagination import (
    CursorDirection,
    DecodedCursor,
    decode_directional_cursor,
    encode_cursor,
)


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
        dashboard_resource_library_count: int = 0,
        dashboard_media_library_count: int = 0,
        remote_execution_enabled: bool = False,
        remote_execution_maximum_ttl_seconds: int = 900,
        system_status=None,
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
        self._system_status = system_status
        self._schedules = tuple(schedules)
        self._dashboard = DashboardService(
            repository,
            resource_library_count=dashboard_resource_library_count,
            media_library_count=dashboard_media_library_count,
        )

    def __call__(self, environ: dict, start_response: Callable) -> Iterable[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))
        request_id = str(uuid4())
        try:
            if path == "/health" and method == "GET":
                return self._response(start_response, 200, {"status": "ok"})
            if path in OPERATOR_UI_ASSETS:
                if method != "GET":
                    return self._error(start_response, 405, "method_not_allowed", "GET required")
                content_type, body = OPERATOR_UI_ASSETS[path]
                return self._static_response(start_response, content_type, body)
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
        if parts == ["api", "v1", "system", "status"]:
            if method != "GET":
                return self._error(start_response, 405, "method_not_allowed", "GET required")
            self._require_empty_query(environ, "system status")
            self._require(principal, ApiPermission.READ)
            if self._system_status is None:
                return self._error(
                    start_response, 503, "service_unavailable", "system status is unavailable"
                )
            return self._response(start_response, 200, self._system_status.as_document())
        if parts == ["api", "v1", "security-audit"] and method == "GET":
            self._require(principal, ApiPermission.READ_SECURITY_AUDIT)
            return self._response(
                start_response,
                200,
                {"items": [self._value(item) for item in self._repository.list_security_audit()]},
            )
        if parts == ["api", "v1", "dashboard"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            return self._response(
                start_response,
                200,
                self._value(self._dashboard.snapshot(recent_limit=self._dashboard_limit(environ))),
            )
        if parts == ["api", "v1", "metadata-reviews"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            limit = self._metadata_review_limit(environ)
            return self._response(
                start_response,
                200,
                {
                    "items": [
                        self._value(item)
                        for item in self._repository.list_metadata_reviews(limit=limit)
                    ]
                },
            )
        if parts == ["api", "v1", "classification-reviews"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            limit = self._classification_review_limit(environ)
            return self._response(
                start_response,
                200,
                {
                    "items": [
                        self._value(item)
                        for item in self._repository.list_classification_reviews(limit=limit)
                    ]
                },
            )
        if len(parts) == 4 and parts[:3] == ["api", "v1", "metadata-reviews"] and method == "GET":
            self._require(principal, ApiPermission.READ)
            review = self._repository.get_metadata_review(parts[3])
            if review is None:
                raise LookupError(f"metadata review {parts[3]!r} was not found")
            return self._response(
                start_response,
                200,
                {
                    **self._value(review),
                    "candidates": [
                        self._value(item)
                        for item in self._repository.list_metadata_review_candidates(parts[3])
                    ],
                    "audit": [
                        self._metadata_review_audit_value(item)
                        for item in self._repository.list_metadata_review_audit(parts[3])
                    ],
                },
            )
        if (
            len(parts) == 4
            and parts[:3] == ["api", "v1", "classification-reviews"]
            and method == "GET"
        ):
            self._require(principal, ApiPermission.READ)
            review = self._repository.get_classification_review(parts[3])
            if review is None:
                raise LookupError(f"classification review {parts[3]!r} was not found")
            return self._response(
                start_response,
                200,
                {
                    **self._value(review),
                    "choices": [
                        self._value(item)
                        for item in self._repository.list_classification_review_choices(parts[3])
                    ],
                    "audit": [
                        self._classification_review_audit_value(item)
                        for item in self._repository.list_classification_review_audit(parts[3])
                    ],
                },
            )
        if method == "GET":
            self._require(principal, ApiPermission.READ)
        if parts == ["api", "v1", "tasks"] and method == "GET":
            limit, cursor = self._collection_page(environ, "tasks")
            values = self._list_page(self._repository.list_tasks, limit, cursor)
            page, has_previous, has_next = self._page_window(values, limit, cursor)
            return self._response(
                start_response,
                200,
                {
                    "items": [self._value(item) for item in page],
                    "limit": limit,
                    "truncated": has_next,
                    "previous_cursor": self._page_cursor(
                        "tasks", page, has_previous, CursorDirection.PREVIOUS
                    ),
                    "next_cursor": self._page_cursor("tasks", page, has_next, CursorDirection.NEXT),
                },
            )
        if len(parts) == 4 and parts[:3] == ["api", "v1", "tasks"] and method == "GET":
            item_limit, result_limit, item_cursor, result_cursor = self._task_detail_page(environ)
            task = self._repository.get_task(parts[3])
            if task is None:
                raise LookupError(f"task {parts[3]!r} was not found")
            items = self._list_page(
                lambda **kwargs: self._repository.list_items(task.task_id, **kwargs),
                item_limit,
                item_cursor,
            )
            results = self._list_page(
                lambda **kwargs: self._repository.list_results(task.task_id, **kwargs),
                result_limit,
                result_cursor,
            )
            item_page, has_previous_items, has_next_items = self._page_window(
                items, item_limit, item_cursor
            )
            result_page, has_previous_results, has_next_results = self._page_window(
                results, result_limit, result_cursor
            )
            return self._response(
                start_response,
                200,
                {
                    **self._value(task),
                    "items": [self._value(item) for item in item_page],
                    "results": [self._value(item) for item in result_page],
                    "item_limit": item_limit,
                    "result_limit": result_limit,
                    "items_truncated": has_next_items,
                    "results_truncated": has_next_results,
                    "previous_item_cursor": self._page_cursor(
                        "task_items", item_page, has_previous_items, CursorDirection.PREVIOUS
                    ),
                    "previous_result_cursor": self._page_cursor(
                        "task_results",
                        result_page,
                        has_previous_results,
                        CursorDirection.PREVIOUS,
                    ),
                    "next_item_cursor": self._page_cursor(
                        "task_items", item_page, has_next_items, CursorDirection.NEXT
                    ),
                    "next_result_cursor": self._page_cursor(
                        "task_results", result_page, has_next_results, CursorDirection.NEXT
                    ),
                },
            )
        if parts == ["api", "v1", "confirmations"] and method == "GET":
            status, limit = self._confirmation_query(environ)
            values = self._repository.list_confirmations(status=status, limit=limit)
            return self._response(
                start_response,
                200,
                {"items": [self._confirmation_value(item) for item in values]},
            )
        if len(parts) == 4 and parts[:3] == ["api", "v1", "confirmations"] and method == "GET":
            value = self._repository.get_confirmation(parts[3])
            if value is None:
                raise LookupError(f"confirmation {parts[3]!r} was not found")
            return self._response(start_response, 200, self._confirmation_value(value))
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "metadata-reviews"]
            and parts[4] == "resolve"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.RESOLVE_METADATA_REVIEW)
            document = self._document(environ)
            if set(document) != {"candidateRank"}:
                raise ValueError("metadata review resolution requires only candidateRank")
            candidate_rank = document["candidateRank"]
            if isinstance(candidate_rank, bool) or not isinstance(candidate_rank, int):
                raise ValueError("candidateRank must be an integer")
            value = MetadataReviewService(self._repository).resolve(
                parts[3], candidate_rank, actor=principal.principal_id
            )
            return self._response(start_response, 200, self._value(value))
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "classification-reviews"]
            and parts[4] == "resolve"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.RESOLVE_CLASSIFICATION_REVIEW)
            document = self._document(environ)
            if set(document) != {"choiceRank"}:
                raise ValueError("classification review resolution requires only choiceRank")
            choice_rank = document["choiceRank"]
            if isinstance(choice_rank, bool) or not isinstance(choice_rank, int):
                raise ValueError("choiceRank must be an integer")
            value = ClassificationReviewService(self._repository).resolve(
                parts[3], choice_rank, actor=principal.principal_id
            )
            return self._response(start_response, 200, self._value(value))
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "confirmations"]
            and parts[4] == "audit"
            and method == "GET"
        ):
            value = self._repository.get_confirmation(parts[3])
            if value is None:
                raise LookupError(f"confirmation {parts[3]!r} was not found")
            return self._response(
                start_response,
                200,
                {
                    "items": [
                        self._confirmation_audit_value(item)
                        for item in self._repository.list_confirmation_audit(parts[3])
                    ]
                },
            )
        if parts == ["api", "v1", "schedules"] and method == "GET":
            self._require_empty_query(environ, "schedule")
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
            limit, delivery_status, cursor = self._notification_query(environ)
            scope = delivery_status.value if delivery_status else "all"
            values = self._list_page(
                lambda **kwargs: self._repository.list_deliveries(status=delivery_status, **kwargs),
                limit,
                cursor,
            )
            page, has_previous, has_next = self._page_window(values, limit, cursor)
            return self._response(
                start_response,
                200,
                {
                    "limit": limit,
                    "status": delivery_status.value if delivery_status else None,
                    "previous_cursor": self._page_cursor(
                        "notification_deliveries",
                        page,
                        has_previous,
                        CursorDirection.PREVIOUS,
                        scope=scope,
                    ),
                    "next_cursor": self._page_cursor(
                        "notification_deliveries",
                        page,
                        has_next,
                        CursorDirection.NEXT,
                        scope=scope,
                    ),
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
                        for item in page
                    ],
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
            limit, cursor = self._scoped_page_query(
                environ, "schedule_audit", parts[3], "schedule audit"
            )
            values = self._list_page(
                lambda **kwargs: self._repository.list_schedule_audit(parts[3], **kwargs),
                limit,
                cursor,
            )
            page, has_previous, has_next = self._page_window(values, limit, cursor)
            return self._response(
                start_response,
                200,
                {
                    "items": [self._value(item) for item in page],
                    "limit": limit,
                    "previous_cursor": self._page_cursor(
                        "schedule_audit",
                        page,
                        has_previous,
                        CursorDirection.PREVIOUS,
                        scope=parts[3],
                    ),
                    "next_cursor": self._page_cursor(
                        "schedule_audit",
                        page,
                        has_next,
                        CursorDirection.NEXT,
                        scope=parts[3],
                    ),
                },
            )
        if parts == ["api", "v1", "logs"] and method == "GET":
            limit, minimum_level, cursor = self._log_query(environ)
            scope = minimum_level.name if minimum_level else "all"
            values = self._list_page(
                lambda **kwargs: self._repository.list_operational_logs(
                    minimum_level=minimum_level, **kwargs
                ),
                limit,
                cursor,
            )
            page, has_previous, has_next = self._page_window(values, limit, cursor)
            return self._response(
                start_response,
                200,
                {
                    "items": [
                        {
                            "log_id": item.log_id,
                            "occurred_at": item.occurred_at.isoformat(),
                            "level": item.level.name,
                            "component": item.component,
                            "event": item.event,
                            "task_id": item.task_id,
                            "job_id": item.job_id,
                            "plan_id": item.plan_id,
                            "status": item.status,
                        }
                        for item in page
                    ],
                    "limit": limit,
                    "level": minimum_level.name if minimum_level else None,
                    "previous_cursor": self._page_cursor(
                        "operational_logs",
                        page,
                        has_previous,
                        CursorDirection.PREVIOUS,
                        scope=scope,
                    ),
                    "next_cursor": self._page_cursor(
                        "operational_logs", page, has_next, CursorDirection.NEXT, scope=scope
                    ),
                },
            )
        if parts == ["api", "v1", "jobs"]:
            if method == "GET":
                limit, cursor = self._collection_page(environ, "jobs")
                values = self._list_page(self._repository.list_jobs, limit, cursor)
                page, has_previous, has_next = self._page_window(values, limit, cursor)
                return self._response(
                    start_response,
                    200,
                    {
                        "items": [self._value(item) for item in page],
                        "limit": limit,
                        "truncated": has_next,
                        "previous_cursor": self._page_cursor(
                            "jobs", page, has_previous, CursorDirection.PREVIOUS
                        ),
                        "next_cursor": self._page_cursor(
                            "jobs", page, has_next, CursorDirection.NEXT
                        ),
                    },
                )
            if method == "POST":
                self._require_empty_query(environ, "job submission")
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
                    unsupported = set(document).difference({"command", "limit"})
                    if unsupported:
                        raise ValueError(f"unsupported DryRun job field {sorted(unsupported)[0]!r}")
                    job = self._jobs.submit(command, limit=document.get("limit"))
                return self._response(start_response, 202, self._value(job))
        if len(parts) == 4 and parts[:3] == ["api", "v1", "jobs"] and method == "GET":
            job = self._repository.get_job(parts[3])
            if job is None:
                raise LookupError(f"automation job {parts[3]!r} was not found")
            return self._response(start_response, 200, self._value(job))
        if len(parts) == 5 and parts[:3] == ["api", "v1", "jobs"] and parts[4] == "cancel":
            if method != "POST":
                return self._error(start_response, 405, "method_not_allowed", "POST required")
            self._require(principal, ApiPermission.CANCEL_JOB)
            self._require_empty_query(environ, "job cancellation")
            self._require_empty_body(environ, "job cancellation")
            return self._response(start_response, 200, self._value(self._jobs.cancel(parts[3])))
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "confirmations"]
            and parts[4] == "resolve"
            and method == "POST"
        ):
            self._require(principal, ApiPermission.RESOLVE_CONFIRMATION)
            document = self._document(environ)
            unsupported = set(document).difference({"strategy"})
            if unsupported:
                raise ValueError(f"unsupported confirmation field {sorted(unsupported)[0]!r}")
            try:
                strategy = ConflictStrategy(document.get("strategy", ""))
            except ValueError as error:
                raise ValueError("remote confirmation strategy must be skip or rename") from error
            if strategy not in {ConflictStrategy.SKIP, ConflictStrategy.RENAME}:
                raise ValueError("remote confirmation strategy must be skip or rename")
            value = ConfirmationService(self._repository).resolve(
                parts[3], strategy, actor=principal.principal_id
            )
            return self._response(start_response, 200, self._confirmation_value(value))
        return self._error(start_response, 404, "not_found", "route was not found")

    def _authenticate(self, environ: dict) -> ResolvedApiPrincipal | None:
        header = str(environ.get("HTTP_AUTHORIZATION", ""))
        prefix = "Bearer "
        candidate = header[len(prefix) :] if header.startswith(prefix) else ""
        valid = (
            len(header) <= 4096
            and 1 <= len(candidate) <= 2048
            and not any(character.isspace() for character in candidate)
        )
        presented = candidate if valid else ""
        matched = None
        for principal in self._principals:
            if hmac.compare_digest(presented, principal.token):
                matched = principal
        return matched

    @staticmethod
    def _static_response(start_response: Callable, content_type: str, body: bytes):
        start_response(
            "200 OK",
            [
                ("Content-Type", content_type),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
                (
                    "Content-Security-Policy",
                    "default-src 'self'; connect-src 'self'; "
                    "script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; "
                    "frame-ancestors 'none'; form-action 'none'",
                ),
                ("X-Content-Type-Options", "nosniff"),
                ("Referrer-Policy", "no-referrer"),
                ("Permissions-Policy", "camera=(), microphone=(), geolocation=()"),
            ],
        )
        return [body]

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
            ("api", "v1", "logs"),
            ("api", "v1", "jobs"),
            ("api", "v1", "security-audit"),
            ("api", "v1", "dashboard"),
            ("api", "v1", "system", "status"),
            ("api", "v1", "metadata-reviews"),
            ("api", "v1", "classification-reviews"),
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
        if len(parts) == 4 and parts[:3] == ["api", "v1", "confirmations"]:
            return "/api/v1/confirmations/{id}"
        if len(parts) == 4 and parts[:3] == ["api", "v1", "metadata-reviews"]:
            return "/api/v1/metadata-reviews/{id}"
        if len(parts) == 4 and parts[:3] == ["api", "v1", "classification-reviews"]:
            return "/api/v1/classification-reviews/{id}"
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "metadata-reviews"]
            and parts[4] == "resolve"
        ):
            return "/api/v1/metadata-reviews/{id}/resolve"
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "classification-reviews"]
            and parts[4] == "resolve"
        ):
            return "/api/v1/classification-reviews/{id}/resolve"
        if (
            len(parts) == 5
            and parts[:3] == ["api", "v1", "confirmations"]
            and parts[4]
            in {
                "audit",
                "resolve",
            }
        ):
            return f"/api/v1/confirmations/{{id}}/{parts[4]}"
        return "/api/v1/<unmatched>"

    @staticmethod
    def _dashboard_limit(environ: dict) -> int:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        unknown = set(values).difference({"recentLimit"})
        if unknown:
            raise ValueError("dashboard query contains an unsupported field")
        raw = values.get("recentLimit", ["10"])
        if len(raw) != 1:
            raise ValueError("dashboard recentLimit must be specified once")
        try:
            return int(raw[0])
        except ValueError as error:
            raise ValueError("dashboard recentLimit must be an integer") from error

    @staticmethod
    def _confirmation_query(
        environ: dict,
    ) -> tuple[ConfirmationStatus | None, int]:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        unknown = set(values).difference({"status", "limit"})
        if unknown:
            raise ValueError("confirmation query contains an unsupported field")
        if any(len(value) != 1 for value in values.values()):
            raise ValueError("confirmation query fields must be specified once")
        raw_status = values.get("status", ["pending"])[0]
        if raw_status == "all":
            status = None
        else:
            try:
                status = ConfirmationStatus(raw_status)
            except ValueError as error:
                raise ValueError("confirmation status must be pending, resolved, or all") from error
        try:
            limit = int(values.get("limit", ["100"])[0])
        except ValueError as error:
            raise ValueError("confirmation limit must be an integer") from error
        if limit < 1 or limit > 100:
            raise ValueError("confirmation limit must be between 1 and 100")
        return status, limit

    @staticmethod
    def _metadata_review_limit(environ: dict) -> int:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"limit"}) or any(len(value) != 1 for value in values.values()):
            raise ValueError("metadata review query accepts one limit field")
        try:
            limit = int(values.get("limit", ["100"])[0])
        except ValueError as error:
            raise ValueError("metadata review limit must be an integer") from error
        if limit < 1 or limit > 100:
            raise ValueError("metadata review limit must be between 1 and 100")
        return limit

    @staticmethod
    def _classification_review_limit(environ: dict) -> int:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"limit"}) or any(len(value) != 1 for value in values.values()):
            raise ValueError("classification review query accepts one limit field")
        try:
            limit = int(values.get("limit", ["100"])[0])
        except ValueError as error:
            raise ValueError("classification review limit must be an integer") from error
        if limit < 1 or limit > 100:
            raise ValueError("classification review limit must be between 1 and 100")
        return limit

    @staticmethod
    def _require_empty_query(environ: dict, resource: str) -> None:
        if str(environ.get("QUERY_STRING", "")):
            raise ValueError(f"{resource} query does not accept fields")

    @staticmethod
    def _require_empty_body(environ: dict, resource: str) -> None:
        raw_length = str(environ.get("CONTENT_LENGTH", "")).strip()
        if not raw_length:
            return
        try:
            length = int(raw_length)
        except ValueError as error:
            raise ValueError("invalid Content-Length") from error
        if length != 0:
            raise ValueError(f"{resource} body must be empty")

    @staticmethod
    def _scoped_page_query(
        environ: dict, kind: str, scope: str, resource: str
    ) -> tuple[int, DecodedCursor | None]:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"limit", "cursor"}) or any(
            len(value) != 1 for value in values.values()
        ):
            raise ValueError(f"{resource} query accepts limit and cursor once")
        limit = MediaFlowApi._parse_bounded_limit(values.get("limit", ["100"])[0], resource)
        raw_cursor = values.get("cursor")
        cursor = (
            decode_directional_cursor(raw_cursor[0], kind, expected_scope=scope)
            if raw_cursor
            else None
        )
        return limit, cursor

    @staticmethod
    def _notification_query(
        environ: dict,
    ) -> tuple[int, NotificationDeliveryStatus | None, DecodedCursor | None]:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"limit", "status", "cursor"}) or any(
            len(value) != 1 for value in values.values()
        ):
            raise ValueError("notification query accepts limit, status, and cursor once")
        limit = MediaFlowApi._parse_bounded_limit(values.get("limit", ["100"])[0], "notification")
        raw_status = values.get("status")
        if raw_status is None or raw_status[0] == "all":
            status = None
        else:
            try:
                status = NotificationDeliveryStatus(raw_status[0])
            except ValueError as error:
                raise ValueError("notification status is invalid") from error
        raw_cursor = values.get("cursor")
        cursor = (
            decode_directional_cursor(
                raw_cursor[0],
                "notification_deliveries",
                expected_scope=status.value if status else "all",
            )
            if raw_cursor
            else None
        )
        return limit, status, cursor

    @staticmethod
    def _log_query(environ: dict) -> tuple[int, LogLevel | None, DecodedCursor | None]:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"limit", "level", "cursor"}) or any(
            len(value) != 1 for value in values.values()
        ):
            raise ValueError("log query accepts limit, level, and cursor once")
        limit = MediaFlowApi._parse_bounded_limit(values.get("limit", ["100"])[0], "log")
        raw_level = values.get("level", ["all"])[0]
        if raw_level == "all":
            level = None
        else:
            try:
                level = LogLevel[raw_level]
            except KeyError as error:
                raise ValueError("log level is invalid") from error
        raw_cursor = values.get("cursor")
        cursor = (
            decode_directional_cursor(
                raw_cursor[0],
                "operational_logs",
                expected_scope=level.name if level else "all",
            )
            if raw_cursor
            else None
        )
        return limit, level, cursor

    @staticmethod
    def _collection_page(environ: dict, resource: str) -> tuple[int, DecodedCursor | None]:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        if set(values).difference({"limit", "cursor"}) or any(
            len(value) != 1 for value in values.values()
        ):
            raise ValueError(f"{resource} query accepts limit and cursor once")
        limit = MediaFlowApi._parse_bounded_limit(
            values.get("limit", ["100"])[0], resource.rstrip("s")
        )
        raw_cursor = values.get("cursor")
        return limit, decode_directional_cursor(raw_cursor[0], resource) if raw_cursor else None

    @staticmethod
    def _task_detail_page(
        environ: dict,
    ) -> tuple[int, int, DecodedCursor | None, DecodedCursor | None]:
        values = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        allowed = {"itemLimit", "resultLimit", "itemCursor", "resultCursor"}
        if set(values).difference(allowed) or any(len(value) != 1 for value in values.values()):
            raise ValueError("task detail query fields must be supported and specified once")
        raw_item_cursor = values.get("itemCursor")
        raw_result_cursor = values.get("resultCursor")
        return (
            MediaFlowApi._parse_bounded_limit(values.get("itemLimit", ["100"])[0], "task item"),
            MediaFlowApi._parse_bounded_limit(values.get("resultLimit", ["100"])[0], "task result"),
            decode_directional_cursor(raw_item_cursor[0], "task_items")
            if raw_item_cursor
            else None,
            decode_directional_cursor(raw_result_cursor[0], "task_results")
            if raw_result_cursor
            else None,
        )

    @staticmethod
    def _list_page(list_values: Callable, limit: int, cursor: DecodedCursor | None):
        if cursor is None:
            return list_values(limit=limit + 1)
        boundary = (
            {"after": cursor.position}
            if cursor.direction is CursorDirection.NEXT
            else {"before": cursor.position}
        )
        return list_values(limit=limit + 1, **boundary)

    @staticmethod
    def _page_window(values, limit: int, cursor: DecodedCursor | None):
        if cursor is not None and cursor.direction is CursorDirection.PREVIOUS:
            page = values[-limit:]
            return page, len(values) > limit, bool(page)
        page = values[:limit]
        return page, bool(cursor and page), len(values) > limit

    @staticmethod
    def _page_cursor(
        kind: str,
        page: tuple | list,
        available: bool,
        direction: CursorDirection,
        *,
        scope: str | None = None,
    ) -> str | None:
        if not available or not page:
            return None
        record = page[0] if direction is CursorDirection.PREVIOUS else page[-1]
        attribute = {
            "tasks": "task_id",
            "jobs": "job_id",
            "task_items": "item_id",
            "task_results": "result_id",
            "notification_deliveries": "delivery_id",
            "schedule_audit": "audit_id",
            "operational_logs": "log_id",
        }[kind]
        identifier = getattr(record, attribute)
        timestamp = (
            record.emitted_at
            if kind == "schedule_audit"
            else record.occurred_at
            if kind == "operational_logs"
            else record.created_at
        )
        return encode_cursor(kind, timestamp, identifier, direction, scope=scope)

    @staticmethod
    def _parse_bounded_limit(raw: str, resource: str) -> int:
        try:
            limit = int(raw)
        except ValueError as error:
            raise ValueError(f"{resource} limit must be an integer") from error
        if limit < 1 or limit > 100:
            raise ValueError(f"{resource} limit must be between 1 and 100")
        return limit

    @classmethod
    def _confirmation_value(cls, value) -> dict:
        document = cls._value(value)
        document.pop("note", None)
        return document

    @classmethod
    def _confirmation_audit_value(cls, value) -> dict:
        document = cls._value(value)
        document.pop("note", None)
        return document

    @classmethod
    def _metadata_review_audit_value(cls, value) -> dict:
        document = cls._value(value)
        document.pop("note", None)
        return document

    @classmethod
    def _classification_review_audit_value(cls, value) -> dict:
        document = cls._value(value)
        document.pop("note", None)
        return document

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
            405: "Method Not Allowed",
            500: "Internal Server Error",
            503: "Service Unavailable",
        }
        headers = [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            ("Referrer-Policy", "no-referrer"),
            ("X-Frame-Options", "DENY"),
        ]
        if status == 401:
            headers.append(("WWW-Authenticate", 'Bearer realm="mediaflow"'))
        start_response(f"{status} {labels[status]}", headers)
        return [body]

    @classmethod
    def _error(cls, start_response: Callable, status: int, code: str, message: str):
        return cls._response(start_response, status, {"error": {"code": code, "message": message}})
