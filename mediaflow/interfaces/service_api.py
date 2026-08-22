from __future__ import annotations

import hmac
import json
from collections.abc import Callable, Iterable
from dataclasses import asdict
from datetime import datetime
from enum import Enum

from mediaflow.application.automation import AutomationJobService
from mediaflow.domain.task_persistence import ConfirmationStatus


class MediaFlowApi:
    """Small WSGI transport over persistence and queue application boundaries."""

    def __init__(self, repository, bearer_token: str, schedules=()) -> None:
        if not bearer_token:
            raise ValueError("API bearer token must be configured")
        self._repository = repository
        self._token = bearer_token
        self._jobs = AutomationJobService(repository)
        self._schedules = tuple(schedules)

    def __call__(self, environ: dict, start_response: Callable) -> Iterable[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))
        try:
            if path == "/health" and method == "GET":
                return self._response(start_response, 200, {"status": "ok"})
            if not path.startswith("/api/v1"):
                return self._error(start_response, 404, "not_found", "route was not found")
            if not self._authorized(environ):
                return self._error(start_response, 401, "unauthorized", "bearer token required")
            return self._dispatch(method, path, environ, start_response)
        except LookupError as error:
            return self._error(start_response, 404, "not_found", str(error))
        except (ValueError, json.JSONDecodeError) as error:
            return self._error(start_response, 400, "invalid_request", str(error))
        except Exception:
            return self._error(
                start_response, 500, "internal_error", "request failed (details redacted)"
            )

    def _dispatch(self, method: str, path: str, environ: dict, start_response: Callable):
        parts = [part for part in path.split("/") if part]
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
        if parts == ["api", "v1", "jobs"]:
            if method == "GET":
                values = self._repository.list_jobs(limit=100)
                return self._response(
                    start_response, 200, {"items": [self._value(item) for item in values]}
                )
            if method == "POST":
                document = self._document(environ)
                forbidden = {"execute", "overwrite", "delete"}.intersection(document)
                if forbidden:
                    raise ValueError(
                        f"unsupported service field {sorted(forbidden)[0]!r}; "
                        "remote execution is disabled"
                    )
                job = self._jobs.submit(document.get("command", ""), limit=document.get("limit"))
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
            return self._response(start_response, 200, self._value(self._jobs.cancel(parts[3])))
        return self._error(start_response, 404, "not_found", "route was not found")

    def _authorized(self, environ: dict) -> bool:
        header = str(environ.get("HTTP_AUTHORIZATION", ""))
        prefix = "Bearer "
        return header.startswith(prefix) and hmac.compare_digest(header[len(prefix) :], self._token)

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
