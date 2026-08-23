from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar


class RetryCategory(StrEnum):
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    RATE_LIMITED = "rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"


@dataclass(frozen=True)
class WorkflowRetryPolicy:
    enabled: bool = False
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    jitter_ratio: float = 0.0

    def __post_init__(self) -> None:
        if isinstance(self.max_attempts, bool) or not 1 <= self.max_attempts <= 10:
            raise ValueError("workflow retry max attempts must be between 1 and 10")
        if isinstance(self.base_delay_seconds, bool) or not 0 <= self.base_delay_seconds <= 300:
            raise ValueError("workflow retry base delay must be between 0 and 300 seconds")
        if (
            isinstance(self.max_delay_seconds, bool)
            or not self.base_delay_seconds <= self.max_delay_seconds <= 300
        ):
            raise ValueError("workflow retry maximum delay is invalid")
        if isinstance(self.jitter_ratio, bool) or not 0 <= self.jitter_ratio <= 1:
            raise ValueError("workflow retry jitter ratio must be between 0 and 1")


@dataclass(frozen=True)
class RetryEvent:
    stage: str
    attempt: int
    category: RetryCategory
    delay_seconds: float


T = TypeVar("T")


@dataclass(frozen=True)
class RetryOutcome(Generic[T]):
    value: T
    events: tuple[RetryEvent, ...] = ()
