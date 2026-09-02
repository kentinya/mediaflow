from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

_CURSOR_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}")
_ENCODED_CURSOR = re.compile(r"[A-Za-z0-9_-]+")
_KINDS = frozenset(
    {
        "tasks",
        "jobs",
        "task_items",
        "task_results",
        "notification_deliveries",
        "schedule_audit",
        "automation_definition_occurrences",
        "operational_logs",
    }
)
_SCOPED_KINDS = frozenset(
    {
        "notification_deliveries",
        "schedule_audit",
        "automation_definition_occurrences",
        "operational_logs",
    }
)
MAX_CURSOR_LENGTH = 512


class CursorDirection(StrEnum):
    NEXT = "next"
    PREVIOUS = "previous"


@dataclass(frozen=True)
class DecodedCursor:
    created_at: datetime
    record_id: str
    direction: CursorDirection
    scope: str | None = None

    @property
    def position(self) -> tuple[datetime, str]:
        return self.created_at, self.record_id


def encode_cursor(
    kind: str,
    created_at: datetime,
    record_id: str,
    direction: CursorDirection | str = CursorDirection.NEXT,
    *,
    scope: str | None = None,
) -> str:
    if kind not in _KINDS:
        raise ValueError("unsupported cursor kind")
    _validate_position(created_at, record_id)
    try:
        resolved_direction = CursorDirection(direction)
    except ValueError as error:
        raise ValueError("unsupported cursor direction") from error
    document = {
        "at": created_at.isoformat(),
        "direction": resolved_direction.value,
        "id": record_id,
        "kind": kind,
        "version": 2,
    }
    if kind in _SCOPED_KINDS:
        if not scope:
            raise ValueError("cursor scope is required")
        document["scope"] = _scope_digest(kind, scope)
    elif scope is not None:
        raise ValueError("cursor scope is unsupported")
    raw = json.dumps(document, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def decode_cursor(
    value: str, expected_kind: str, *, expected_scope: str | None = None
) -> tuple[datetime, str]:
    return decode_directional_cursor(value, expected_kind, expected_scope=expected_scope).position


def decode_directional_cursor(
    value: str, expected_kind: str, *, expected_scope: str | None = None
) -> DecodedCursor:
    if expected_kind not in _KINDS:
        raise ValueError("unsupported cursor kind")
    if (
        not value
        or len(value) > MAX_CURSOR_LENGTH
        or not value.isascii()
        or not _ENCODED_CURSOR.fullmatch(value)
    ):
        raise ValueError("cursor is malformed")
    try:
        padding = "=" * (-len(value) % 4)
        raw = base64.b64decode(value + padding, altchars=b"-_", validate=True)
        document = json.loads(raw.decode("utf-8"))
    except (binascii.Error, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("cursor is malformed") from error
    if not isinstance(document, dict):
        raise ValueError("cursor has an invalid schema")
    version = document.get("version")
    v1_fields = {"at", "id", "kind", "version"}
    v2_fields = v1_fields | {"direction"}
    if expected_kind in _SCOPED_KINDS:
        v2_fields.add("scope")
    if type(version) is not int or version not in {1, 2}:
        raise ValueError("cursor does not match this resource")
    if set(document) != (v1_fields if version == 1 else v2_fields):
        raise ValueError("cursor has an invalid schema")
    if not isinstance(document["kind"], str) or document["kind"] != expected_kind:
        raise ValueError("cursor does not match this resource")
    if not isinstance(document["at"], str) or not isinstance(document["id"], str):
        raise ValueError("cursor has invalid position fields")
    try:
        created_at = datetime.fromisoformat(document["at"])
    except ValueError as error:
        raise ValueError("cursor timestamp is invalid") from error
    _validate_position(created_at, document["id"])
    if expected_kind in _SCOPED_KINDS:
        if version == 1 or not expected_scope:
            raise ValueError("cursor scope is required")
        expected_digest = _scope_digest(expected_kind, expected_scope)
        if not isinstance(document["scope"], str) or not hmac.compare_digest(
            document["scope"], expected_digest
        ):
            raise ValueError("cursor does not match this resource scope")
        scope = document["scope"]
    else:
        if expected_scope is not None:
            raise ValueError("cursor scope is unsupported")
        scope = None
    if version == 1:
        direction = CursorDirection.NEXT
    else:
        try:
            direction = CursorDirection(document["direction"])
        except (TypeError, ValueError) as error:
            raise ValueError("cursor direction is invalid") from error
    return DecodedCursor(created_at, document["id"], direction, scope)


def _scope_digest(kind: str, scope: str) -> str:
    return hashlib.sha256(f"{kind}\0{scope}".encode()).hexdigest()


def _validate_position(created_at: datetime, record_id: str) -> None:
    if created_at.tzinfo is None or created_at.utcoffset() != timedelta(0):
        raise ValueError("cursor timestamp must use UTC")
    if not _CURSOR_ID.fullmatch(record_id):
        raise ValueError("cursor record ID is invalid")
