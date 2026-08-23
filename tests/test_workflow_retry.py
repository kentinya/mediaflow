from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from mediaflow.application.media_organizer import MediaOrganizerService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.application.scanner import StorageScanner
from mediaflow.application.strategy_test import (
    SyntheticMetadataProvider,
    strategy_runner_from_configuration,
)
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.application.workflow_retry import (
    RetryExhausted,
    RetryInterrupted,
    RetrySignal,
    WorkflowRetryController,
    classify_retryable_error,
)
from mediaflow.domain.library import MediaLibrary, ResourceLibrary
from mediaflow.domain.metadata import MediaCandidate, MediaType, MetadataError, MetadataErrorCode
from mediaflow.domain.organizer import ExecutionStatus
from mediaflow.domain.recognition import RecognitionType
from mediaflow.domain.storage import StorageError, StorageErrorCode
from mediaflow.domain.workflow_retry import RetryCategory, WorkflowRetryPolicy
from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.memory_file_index import InMemoryFileIndexRepository
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration


def example_document() -> dict:
    return json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))


class WorkflowRetryTests(unittest.TestCase):
    def test_default_disabled_and_runtime_configuration(self) -> None:
        self.assertFalse(
            load_runtime_configuration(example_document()).workflow_retry_policy.enabled
        )
        document = example_document()
        document["workflowRetry"] = {
            "enabled": True,
            "maxAttempts": 4,
            "baseDelaySeconds": 0.5,
            "maxDelaySeconds": 3,
            "jitterRatio": 0.25,
        }
        policy = load_runtime_configuration(document).workflow_retry_policy
        self.assertTrue(policy.enabled)
        self.assertEqual(policy.max_attempts, 4)
        self.assertEqual(policy.base_delay_seconds, 0.5)

    def test_runtime_configuration_rejects_invalid_values(self) -> None:
        invalid_values = (
            {"unknown": 1},
            {"enabled": 1},
            {"maxAttempts": True},
            {"maxAttempts": 11},
            {"baseDelaySeconds": -1},
            {"baseDelaySeconds": 2, "maxDelaySeconds": 1},
            {"jitterRatio": 1.1},
        )
        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                document = copy.deepcopy(example_document())
                document["workflowRetry"] = value
                load_runtime_configuration(document)

    def test_transient_categories_are_explicit_and_permanent_are_not(self) -> None:
        transient = (
            (MetadataError(MetadataErrorCode.TIMEOUT, "secret"), RetryCategory.TIMEOUT),
            (
                MetadataError(MetadataErrorCode.PROVIDER_UNAVAILABLE, "secret"),
                RetryCategory.PROVIDER_UNAVAILABLE,
            ),
            (
                StorageError(StorageErrorCode.CONNECTION_LOST, "read", "/secret", "secret"),
                RetryCategory.CONNECTION,
            ),
            (
                StorageError(StorageErrorCode.RATE_LIMITED, "read", "/secret", "secret"),
                RetryCategory.RATE_LIMITED,
            ),
        )
        for error, expected in transient:
            self.assertEqual(classify_retryable_error(error), expected)
        for code in (
            MetadataErrorCode.AUTHENTICATION_FAILED,
            MetadataErrorCode.NOT_FOUND,
            MetadataErrorCode.MALFORMED_RESPONSE,
            MetadataErrorCode.UNKNOWN,
        ):
            self.assertIsNone(classify_retryable_error(MetadataError(code, "secret")))
        self.assertIsNone(classify_retryable_error(ValueError("unknown")))

    def test_bounded_exponential_backoff_and_success_evidence(self) -> None:
        sleeps: list[float] = []
        attempts = 0

        def operation() -> str:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise RetrySignal(RetryCategory.TIMEOUT)
            return "ok"

        outcome = WorkflowRetryController(sleeper=sleeps.append).execute(
            operation,
            WorkflowRetryPolicy(True, 4, 1, 10, 0),
            stage="metadata",
        )
        self.assertEqual(outcome.value, "ok")
        self.assertEqual(sleeps, [0.25] * 12)
        self.assertEqual([event.delay_seconds for event in outcome.events], [1, 2])
        self.assertEqual([event.attempt for event in outcome.events], [2, 3])

    def test_jitter_and_maximum_delay_are_deterministic(self) -> None:
        attempts = 0

        def operation() -> str:
            nonlocal attempts
            attempts += 1
            if attempts < 4:
                raise RetrySignal(RetryCategory.CONNECTION)
            return "ok"

        outcome = WorkflowRetryController(sleeper=lambda _: None, random_source=lambda: 1).execute(
            operation,
            WorkflowRetryPolicy(True, 4, 2, 5, 0.5),
            stage="strategy",
        )
        self.assertEqual([event.delay_seconds for event in outcome.events], [3, 5, 5])

    def test_disabled_permanent_and_exhaustion_are_bounded_and_redacted(self) -> None:
        for error in (ValueError("token=super-secret"), RetrySignal(RetryCategory.TIMEOUT)):
            calls = 0

            def once() -> None:
                nonlocal calls
                calls += 1
                raise error

            with self.assertRaises(type(error)):
                WorkflowRetryController(sleeper=lambda _: None).execute(
                    once, WorkflowRetryPolicy(), stage="strategy"
                )
            self.assertEqual(calls, 1)

        with self.assertRaises(RetryExhausted) as raised:
            WorkflowRetryController(sleeper=lambda _: None).execute(
                lambda: (_ for _ in ()).throw(RetrySignal(RetryCategory.RATE_LIMITED)),
                WorkflowRetryPolicy(True, 3, 0, 0, 0),
                stage="metadata",
            )
        self.assertEqual(len(raised.exception.events), 2)
        self.assertNotIn("secret", str(raised.exception))

    def test_cancellation_stops_before_attempt_and_during_wait(self) -> None:
        with self.assertRaises(RetryInterrupted):
            WorkflowRetryController().execute(
                lambda: "unreachable",
                WorkflowRetryPolicy(True),
                stage="strategy",
                cancellation_check=lambda: True,
            )
        checks = 0

        def cancelled() -> bool:
            nonlocal checks
            checks += 1
            return checks >= 3

        with self.assertRaises(RetryInterrupted):
            WorkflowRetryController(sleeper=lambda _: None).execute(
                lambda: (_ for _ in ()).throw(RetrySignal(RetryCategory.TIMEOUT)),
                WorkflowRetryPolicy(True, 3, 1, 1, 0),
                stage="strategy",
                cancellation_check=cancelled,
            )

    def test_retry_controller_preserves_recognition_type_c_identity(self) -> None:
        calls = 0

        def operation() -> RecognitionType:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RetrySignal(RetryCategory.PROVIDER_UNAVAILABLE)
            return RecognitionType("C", "Special")

        outcome = WorkflowRetryController(sleeper=lambda _: None).execute(
            operation,
            WorkflowRetryPolicy(True, 2, 0, 0, 0),
            stage="strategy",
        )
        self.assertEqual(outcome.value.type_id, "C")

    def test_production_read_only_strategy_retries_but_executor_runs_once(self) -> None:
        class FlakyProvider(SyntheticMetadataProvider):
            def search_movie(self, query, policy=None, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise MetadataError(MetadataErrorCode.TIMEOUT, "token=must-not-persist")
                return self._candidates

        class CountingExecutor:
            def __init__(self) -> None:
                self.calls = 0
                self.delegate = OrganizerExecutor()

            def execute(self, *args, **kwargs):
                self.calls += 1
                return self.delegate.execute(*args, **kwargs)

        with (
            tempfile.TemporaryDirectory() as source_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            source = Path(source_root, "Spirited.Away.2001.mkv")
            source.write_bytes(b"media")
            storages = {
                "source": LocalStorage("source", source_root),
                "target": LocalStorage("target", target_root),
            }
            configuration = development_strategy_configuration()
            provider = FlakyProvider(
                (
                    MediaCandidate(
                        "tmdb",
                        "129",
                        MediaType.MOVIE,
                        "Spirited Away",
                        year=2001,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                )
            )
            executor = CountingExecutor()
            repository = SQLiteTaskRepository(Path(source_root, "runtime.sqlite3"))
            coordinator = PersistentTaskCoordinator(repository, repository)
            task = coordinator.create("preview", execute_authorized=False)
            service = MediaOrganizerService(
                strategy_runner_from_configuration(
                    configuration, MetadataProviderRegistry((provider,)), storages=storages
                ),
                StorageScanner(storages, InMemoryFileIndexRepository()),
                storages,
                {"movies": MediaLibrary("movies", "Movies", "target", "Movies")},
                configuration.recognition_type_policies,
                JsonLinesOperationHistoryRepository(Path(source_root, "history.jsonl")),
                executor=executor,
                retry_policy=WorkflowRetryPolicy(True, 2, 0, 0, 0),
                task_coordinator=coordinator,
                task_id=task.task_id,
            )
            result = service.process_file(
                source.as_posix(),
                resource_library=ResourceLibrary("movies", "Movies", "source", ""),
                storage_path=source.name,
            )
            self.assertIsNotNone(result.execution, result)
            self.assertEqual(result.execution.status, ExecutionStatus.DRY_RUN)
            self.assertEqual(len(result.retry_events), 1)
            self.assertEqual(result.retry_events[0].category, RetryCategory.TIMEOUT)
            self.assertEqual(executor.calls, 1)
            self.assertTrue(source.exists())
            persisted = repository.list_results(task.task_id)[0]
            self.assertEqual(persisted.retry_attempts, 1)
            self.assertEqual(persisted.retry_category, "timeout")
            self.assertNotIn("must-not-persist", repr(persisted))
            repository.close()


if __name__ == "__main__":
    unittest.main()
