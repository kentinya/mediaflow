"""Bounded, secret-free explanations for durable per-item failures.

The scheduled execution boundary must preserve enough information for an operator to
choose a safe next action without persisting an adapter exception.  This value object is
also used as the wire format stored in the existing TaskItem/Result ``error`` columns;
that keeps the change additive and avoids a schema migration for a projection concern.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

FAILURE_ERROR_PREFIX = "mediaflow-failure-v1:"
MAX_FAILURE_FIELD_LENGTH = 256
MAX_FAILURE_ERROR_LENGTH = 2048


@dataclass(frozen=True)
class FailureExplanation:
    """One bounded explanation with exactly one safe next action."""

    category: str
    message: str
    durable_state: str
    side_effects: str
    retry_safe: bool
    next_action: str

    def __post_init__(self) -> None:
        for name in (
            "category",
            "message",
            "durable_state",
            "side_effects",
            "next_action",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"failure explanation {name} is required")
            if len(value) > MAX_FAILURE_FIELD_LENGTH:
                raise ValueError(f"failure explanation {name} is too long")
            if "\x00" in value or "\n" in value or "\r" in value:
                raise ValueError(f"failure explanation {name} contains control characters")
        if not isinstance(self.retry_safe, bool):
            raise ValueError("failure explanation retry_safe must be boolean")

    def document(self) -> dict[str, object]:
        return {
            "category": self.category,
            "message": self.message,
            "durableState": self.durable_state,
            "sideEffects": self.side_effects,
            "retrySafe": self.retry_safe,
            "nextAction": self.next_action,
        }

    def encode(self) -> str:
        encoded = FAILURE_ERROR_PREFIX + json.dumps(
            self.document(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        if len(encoded) > MAX_FAILURE_ERROR_LENGTH:
            raise ValueError("failure explanation encoding is too long")
        return encoded


def decode_failure_explanation(value: Any) -> FailureExplanation | None:
    """Decode only our bounded envelope; legacy plain errors remain displayable as-is."""

    if not isinstance(value, str) or not value.startswith(FAILURE_ERROR_PREFIX):
        return None
    try:
        payload = json.loads(value[len(FAILURE_ERROR_PREFIX) :])
        if not isinstance(payload, dict):
            return None
        return FailureExplanation(
            category=payload["category"],
            message=payload["message"],
            durable_state=payload["durableState"],
            side_effects=payload["sideEffects"],
            retry_safe=payload["retrySafe"],
            next_action=payload["nextAction"],
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def failure_document(value: str | FailureExplanation | None) -> dict[str, object] | None:
    if isinstance(value, FailureExplanation):
        return value.document()
    explanation = decode_failure_explanation(value)
    return explanation.document() if explanation is not None else None


__all__ = [
    "FAILURE_ERROR_PREFIX",
    "MAX_FAILURE_ERROR_LENGTH",
    "MAX_FAILURE_FIELD_LENGTH",
    "FailureExplanation",
    "decode_failure_explanation",
    "failure_document",
]
