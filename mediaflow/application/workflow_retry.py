from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

from mediaflow.domain.metadata import MetadataError, MetadataErrorCode
from mediaflow.domain.storage import StorageError, StorageErrorCode
from mediaflow.domain.workflow_retry import (
    RetryCategory,
    RetryEvent,
    RetryOutcome,
    WorkflowRetryPolicy,
)


class RetryExhausted(RuntimeError):
    def __init__(self, category: RetryCategory, events: tuple[RetryEvent, ...]) -> None:
        super().__init__(f"read-only workflow retry exhausted: {category.value}")
        self.category = category
        self.events = events


class RetryInterrupted(RuntimeError):
    pass


class RetrySignal(RuntimeError):
    def __init__(self, category: RetryCategory) -> None:
        super().__init__(category.value)
        self.category = category


T = TypeVar("T")


class WorkflowRetryController:
    def __init__(
        self,
        *,
        sleeper: Callable[[float], None] = time.sleep,
        random_source: Callable[[], float] = random.random,
        wait_slice_seconds: float = 0.25,
    ) -> None:
        self._sleep = sleeper
        self._random = random_source
        self._wait_slice = wait_slice_seconds

    def execute(
        self,
        operation: Callable[[], T],
        policy: WorkflowRetryPolicy,
        *,
        stage: str,
        cancellation_check: Callable[[], bool] | None = None,
        on_retry: Callable[[RetryEvent], None] | None = None,
    ) -> RetryOutcome[T]:
        events: list[RetryEvent] = []
        for attempt in range(1, policy.max_attempts + 1):
            if cancellation_check and cancellation_check():
                raise RetryInterrupted("workflow retry interrupted")
            try:
                return RetryOutcome(operation(), tuple(events))
            except Exception as error:
                category = classify_retryable_error(error)
                if not policy.enabled or category is None:
                    raise
                if attempt >= policy.max_attempts:
                    raise RetryExhausted(category, tuple(events)) from None
                delay = self._delay(policy, attempt)
                event = RetryEvent(stage, attempt + 1, category, delay)
                events.append(event)
                if on_retry:
                    on_retry(event)
                self._interruptible_wait(delay, cancellation_check)
        raise AssertionError("unreachable")

    def _delay(self, policy: WorkflowRetryPolicy, failed_attempt: int) -> float:
        base = min(
            policy.max_delay_seconds,
            policy.base_delay_seconds * (2 ** (failed_attempt - 1)),
        )
        if not policy.jitter_ratio:
            return base
        factor = 1 + ((self._random() * 2) - 1) * policy.jitter_ratio
        return min(policy.max_delay_seconds, max(0.0, base * factor))

    def _interruptible_wait(
        self, delay: float, cancellation_check: Callable[[], bool] | None
    ) -> None:
        remaining = delay
        while remaining > 0:
            if cancellation_check and cancellation_check():
                raise RetryInterrupted("workflow retry interrupted")
            step = min(remaining, self._wait_slice)
            self._sleep(step)
            remaining -= step
        if cancellation_check and cancellation_check():
            raise RetryInterrupted("workflow retry interrupted")


def classify_retryable_error(error: Exception) -> RetryCategory | None:
    if isinstance(error, RetrySignal):
        return error.category
    if isinstance(error, MetadataError):
        return {
            MetadataErrorCode.TIMEOUT: RetryCategory.TIMEOUT,
            MetadataErrorCode.CONNECTION_FAILED: RetryCategory.CONNECTION,
            MetadataErrorCode.RATE_LIMITED: RetryCategory.RATE_LIMITED,
            MetadataErrorCode.PROVIDER_UNAVAILABLE: RetryCategory.PROVIDER_UNAVAILABLE,
        }.get(error.code)
    if isinstance(error, StorageError):
        return {
            StorageErrorCode.TIMEOUT: RetryCategory.TIMEOUT,
            StorageErrorCode.CONNECTION_FAILED: RetryCategory.CONNECTION,
            StorageErrorCode.CONNECTION_LOST: RetryCategory.CONNECTION,
            StorageErrorCode.RATE_LIMITED: RetryCategory.RATE_LIMITED,
        }.get(error.code)
    return None
