"""Bounded refusal for retired standalone Scan; no runner or history service."""

from __future__ import annotations

from collections.abc import Mapping


class ManualScanError(ValueError):
    """Fail-closed manual Scan admission or lifecycle error."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int = 409,
        durable_state: str = "unchanged",
        retry_safe: bool = True,
        next_action: str,
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.durable_state = durable_state
        self.retry_safe = retry_safe
        self.next_action = next_action
        self.details = dict(details or {})
