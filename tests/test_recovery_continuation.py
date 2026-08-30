from __future__ import annotations

import io
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

from mediaflow.application.automation import AutomationJobService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.recovery_admission import RecoveryAdmissionService
from mediaflow.application.recovery_continuation import (
    RecoveryContinuationService,
)
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.automation import AutomationCommand, AutomationJob, AutomationJobStatus
from mediaflow.domain.metadata import (
    MediaCandidate,
    MediaType,
    MetadataError,
    MetadataErrorCode,
)
from mediaflow.domain.recovery_continuation import RecoveryContinuationStatus
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import PersistentResultRecord, TaskItemStatus
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_metadata_correction import CapturingProvider


def api_request(
    api,
    path: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    token: str = "admin-token",
):
    statuses = []
    payload = json.dumps(body).encode("utf-8") if body is not None else b""
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": str(len(payload)),
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(payload),
    }
    if token:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    response = b"".join(api(environ, lambda value, headers: statuses.append(value)))
    return int(statuses[0].split()[0]), json.loads(response)


class DetailCountingProvider(CapturingProvider):
    def __init__(self, candidates):
        super().__init__(candidates)
        self.movie_details = []

    def get_movie(self, provider_id, policy=None, **kwargs):
        self.movie_details.append(provider_id)
        return super().get_movie(provider_id, policy, **kwargs)


class FailingSearchProvider(DetailCountingProvider):
    def __init__(self, candidates=(), *, failure=True):
        super().__init__(candidates)
        self.failure = failure

    def search_movie(self, query, policy=None, **kwargs):
        if self.failure:
            self.movie_queries.append((query.title_candidate, query.year))
            raise MetadataError(MetadataErrorCode.CONNECTION_FAILED, "provider unavailable")
        return super().search_movie(query, policy, **kwargs)


class ExplodingSearchProvider(DetailCountingProvider):
    def __init__(self, candidates=()):
        super().__init__(candidates)

    def search_movie(self, query, policy=None, **kwargs):
        raise RuntimeError("provider exception marker")


class RecoveryContinuationTests(unittest.TestCase):
    def _environment(self, directory: str | Path):
        root = Path(directory)
        source_root = root / "Incoming"
        target_root = root / "Target"
        media_root = source_root / "Media" / "C"
        media_root.mkdir(parents=True)
        target_root.mkdir()
        source_file = media_root / "Correct.2024.mkv"
        source_file.write_bytes(b"unchanged-source")
        database = root / "runtime.sqlite3"
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        document["storages"][0]["rootPath"] = str(source_root)
        document["storages"][1]["rootPath"] = str(target_root)
        document["resourceLibraries"][0]["displayRootPath"] = str(source_root)
        document["persistence"] = {"databasePath": str(database)}
        document["historyPath"] = str(root / "history.jsonl")
        config_path = root / "config.json"
        config_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")

        with SQLiteConfigurationRepository(database) as repository:
            managed = ManagedConfigurationService(repository)
            revision = managed.validate(
                managed.import_draft(document, actor="tester").revision_id, actor="tester"
            )
            managed.activate(revision.revision_id, expected_version=1, actor="tester")
            active = managed.active()
            assert active is not None
            snapshot = (active.revision_id, active.digest)

        return {
            "root": root,
            "source_file": source_file,
            "target_root": target_root,
            "database": database,
            "config": config_path,
            "document": document,
            "snapshot": snapshot,
            "storage_path": "Media/C/Correct.2024.mkv",
            "display_source": str(source_root / "C" / "Correct.2024.mkv"),
        }

    def _seed_failed_item(
        self,
        environment,
        *,
        execute_authorized: bool = False,
        sibling: bool = True,
        source_path: str | None = None,
        certainty: str = "none",
        item_id: str | None = None,
    ):
        snapshot_id, snapshot_digest = environment["snapshot"]
        storage_path = source_path or environment["storage_path"]
        display_source = str(Path(environment["display_source"]).parent / Path(storage_path).name)
        with SQLiteTaskRepository(environment["database"]) as repository:
            coordinator = _coordinator(repository)
            task = coordinator.create(
                "organize",
                execute_authorized=execute_authorized,
                scope_path=display_source,
                item_limit=2,
                configuration_snapshot_id=snapshot_id,
                configuration_snapshot_digest=snapshot_digest,
                require_configuration_snapshot=True,
            )
            item = coordinator.begin_item(
                task.task_id,
                "source-storage",
                "source",
                storage_path,
                display_source,
            )
            if item_id is not None:
                item = replace(item, item_id=item_id)
            item = replace(
                item, status=TaskItemStatus.FAILED, stage="failed", error="original failure"
            )
            repository.upsert_item(item)
            # Production completes a failed item and releases its lock.
            repository.release(item.storage_id, item.source_path, item.task_id)
            result = PersistentResultRecord(
                f"result-{item.item_id}",
                task.task_id,
                item.item_id,
                "source-storage",
                storage_path,
                "target-storage",
                "Movies/movie.mkv",
                "C",
                "tmdb",
                "123",
                "C",
                "A",
                "A",
                "A",
                "MOVE",
                TaskItemStatus.FAILED.value,
                datetime(2026, 8, 30, 12, 0, tzinfo=UTC),
                title="Movie",
                error="result failure",
                completed_operations=() if certainty != "attempted_unverified" else ("MOVE",),
                effect_certainty=certainty,
                uncertain_effects=(
                    ("mutation_outcome",) if certainty == "attempted_unverified" else ()
                ),
            )
            repository.append_result(result)
            if sibling:
                sibling_item = coordinator.begin_item(
                    task.task_id,
                    "source-storage",
                    "source",
                    "Media/C/Sibling.mkv",
                    str(Path(display_source).parent / "Sibling.mkv"),
                )
                repository.upsert_item(
                    replace(
                        sibling_item,
                        status=TaskItemStatus.SUCCESS,
                        stage="completed",
                    )
                )
                repository.release(
                    sibling_item.storage_id,
                    sibling_item.source_path,
                    sibling_item.task_id,
                )
                sibling_result = PersistentResultRecord(
                    "result-sibling",
                    task.task_id,
                    sibling_item.item_id,
                    "source-storage",
                    "Media/C/Sibling.mkv",
                    "target-storage",
                    "Movies/Sibling.mkv",
                    "C",
                    "tmdb",
                    "999",
                    "C",
                    "A",
                    "A",
                    "A",
                    "MOVE",
                    TaskItemStatus.SUCCESS.value,
                    datetime(2026, 8, 30, 12, 0, tzinfo=UTC),
                    title="Sibling",
                    effect_certainty="verified_complete",
                    uncertain_effects=(),
                )
                repository.append_result(sibling_result)
        return task, item

    def _api(self, environment, *, maximum_active_jobs=100):
        file_index = SQLiteFileIndexRepository(environment["database"])
        repository = SQLiteTaskRepository(environment["database"])
        configuration = SQLiteConfigurationRepository(environment["database"])
        catalog = FileCatalogService(
            file_index,
            ("source",),
            ("source-storage",),
            task_repository=repository,
        )
        api = MediaFlowApi(
            repository,
            None,
            principals=(ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),),
            file_catalog=catalog,
            configuration_service=ManagedConfigurationService(
                configuration,
                bootstrap_database_path=str(environment["database"]),
            ),
            configuration_snapshot_id=environment["snapshot"][0],
            configuration_snapshot_digest=environment["snapshot"][1],
            maximum_active_jobs=maximum_active_jobs,
        )
        self.addCleanup(
            lambda: [
                value.close()
                for value in (
                    api._repository,
                    api._file_catalog._repository,
                    api._configuration_service.repository,
                )
                if value is not None
            ]
        )
        return api

    def _admit(self, environment, task, item, api=None):
        with SQLiteTaskRepository(environment["database"]) as repository:
            gate = RecoveryAdmissionService(
                repository,
                snapshot_validator=lambda _id, _digest: None,
            )
            checkpoint = gate.checkpoint_service.get(item.item_id, task_id=task.task_id)
            admitted = gate.admit(
                task.task_id,
                item.item_id,
                action_id="retry",
                expected_checkpoint_version=checkpoint.checkpoint_version,
                actor="operator",
            )
        return admitted, checkpoint

    def _continue(self, environment, task, item, *, expected=None, api=None):
        with SQLiteTaskRepository(environment["database"]) as repository:
            service = RecoveryContinuationService(
                repository,
                snapshot_validator=lambda _id, _digest: None,
            )
            checkpoint = service.checkpoint_service.get(item.item_id, task_id=task.task_id)
            expected = expected or checkpoint.checkpoint_version
            return service.submit(
                task.task_id,
                item.item_id,
                expected_checkpoint_version=expected,
                actor="operator",
                maximum_active_jobs=100,
            )

    def _run_worker(self, environment, provider, *, expected_code=0):
        output, errors = io.StringIO(), io.StringIO()
        storage_construction = Mock()
        original_create_storages = RuntimeConfiguration.create_storages

        def create_storages(configuration, external=None, storage_ids=None):
            storage_construction(configuration, external, storage_ids)
            return original_create_storages(configuration, external, storage_ids)

        with (
            patch.object(RuntimeConfiguration, "create_storages", create_storages),
            patch(
                "mediaflow.final_cli.metadata_provider_registry_from_environment",
                lambda _ids: MetadataProviderRegistry((provider,)),
            ),
        ):
            code = final_main(
                ["--config", str(environment["config"]), "worker", "run-next"],
                stdout=output,
                stderr=errors,
            )
        self.assertEqual(code, expected_code, f"{errors.getvalue()}\n{output.getvalue()}")
        return storage_construction

    def test_continuation_is_single_item_pinned_dryrun_and_durable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            source_task, source_item = self._seed_failed_item(environment)
            admitted, _ = self._admit(environment, source_task, source_item)
            api = self._api(environment)

            status, checkpoint = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}",
            )
            self.assertEqual(status, 200)
            self.assertIn("continue", checkpoint["actions"][0]["action_id"])
            self.assertEqual(checkpoint["recovery_request"]["request_id"], admitted.request_id)

            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            status, accepted = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}/recovery/continue",
                method="POST",
                body={"expectedCheckpointVersion": checkpoint["checkpoint_version"]},
            )
            self.assertEqual(status, 202)
            self.assertEqual(accepted["status"], "queued")
            self.assertEqual(accepted["executionMode"], "dry_run")
            self.assertEqual(accepted["source_task_id"], source_task.task_id)
            self.assertEqual(accepted["source_item_id"], source_item.item_id)
            self.assertIn("no execute", accepted["authority_statement"])

            with SQLiteTaskRepository(environment["database"]) as repository:
                source_before = (
                    repository.get_task(source_task.task_id),
                    repository.get_item(source_item.item_id),
                    repository.list_items(source_task.task_id),
                    repository.list_results(source_task.task_id),
                )
                request_before = repository.get_recovery_request(admitted.request_id)
                self.assertTrue(request_before.active)

            self._run_worker(environment, provider)
            self.assertEqual(provider.movie_queries, [("Correct", 2024)])
            self.assertEqual(provider.movie_details, ["42"])
            self.assertEqual(environment["source_file"].read_bytes(), b"unchanged-source")
            self.assertFalse(any(environment["target_root"].iterdir()))

            with SQLiteTaskRepository(environment["database"]) as repository:
                self.assertEqual(
                    repository.get_task(source_task.task_id),
                    source_before[0],
                )
                self.assertEqual(
                    repository.get_item(source_item.item_id),
                    source_before[1],
                )
                self.assertEqual(
                    repository.list_items(source_task.task_id),
                    source_before[2],
                )
                self.assertEqual(
                    repository.list_results(source_task.task_id),
                    source_before[3],
                )
                continuation = repository.get_recovery_continuation_for_request(admitted.request_id)
                assert continuation is not None
                self.assertEqual(continuation.status, RecoveryContinuationStatus.COMPLETED)
                new_task = repository.get_task(continuation.new_task_id or "")
                self.assertIsNotNone(new_task)
                assert new_task is not None
                new_items = repository.list_items(new_task.task_id)
                self.assertEqual(len(new_items), 1)
                self.assertEqual(new_items[0].status, TaskItemStatus.DRY_RUN)
                self.assertFalse(new_task.execute_authorized)
                self.assertEqual(new_task.item_limit, 1)
                self.assertEqual(
                    new_task.configuration_snapshot_id,
                    environment["snapshot"][0],
                )
                results = repository.list_results(new_task.task_id)
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0].recognition_type, "C")
                self.assertEqual(results[0].metadata_policy_id, "C")
                self.assertEqual(results[0].naming_policy_id, "A")
                self.assertEqual(results[0].classification_policy_id, "A")
                self.assertEqual(results[0].status, "dry_run")
                self.assertEqual(continuation.new_result_id, results[0].result_id)
                request = repository.get_recovery_request(admitted.request_id)
                self.assertEqual(request.status.value, "completed")
                self.assertEqual(
                    repository.get_item(source_item.item_id).error,
                    "original failure",
                )

            status, checkpoint = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}",
            )
            self.assertEqual(checkpoint["recovery_continuation"]["status"], "completed")
            self.assertEqual(
                checkpoint["recovery_continuation"]["new_task_id"],
                continuation.new_task_id,
            )

    def test_uncertain_effects_are_never_continued(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            source_task, source_item = self._seed_failed_item(
                environment,
                source_path="Media/C/Partial.mkv",
                certainty="attempted_unverified",
            )
            api = self._api(environment)
            status, checkpoint = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}",
            )
            self.assertEqual(status, 200)
            self.assertNotIn("continue", [value["action_id"] for value in checkpoint["actions"]])
            self.assertEqual(checkpoint["actions"][0]["action_id"], "investigate")
            status, document = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}/recovery/continue",
                method="POST",
                body={"expectedCheckpointVersion": checkpoint["checkpoint_version"]},
            )
            self.assertEqual(status, 409)
            self.assertEqual(document["error"]["details"]["reason"], "uncertain_effects")

    def test_pending_job_cancellation_cancels_continuation_and_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            source_task, source_item = self._seed_failed_item(environment)
            admitted, _ = self._admit(environment, source_task, source_item)
            submitted = self._continue(environment, source_task, source_item)

            with SQLiteTaskRepository(environment["database"]) as repository:
                cancelled_job = AutomationJobService(repository).cancel(submitted.job.job_id)
                continuation = repository.get_recovery_continuation_for_job(submitted.job.job_id)
                request = repository.get_recovery_request(admitted.request_id)

                self.assertEqual(cancelled_job.status, AutomationJobStatus.CANCELLED)
                self.assertIsNotNone(continuation)
                self.assertEqual(continuation.status, RecoveryContinuationStatus.CANCELLED)
                self.assertEqual(request.status.value, "cancelled")
                self.assertFalse(request.active)
                self.assertEqual(repository.get_item(source_item.item_id).error, "original failure")
                self.assertEqual(len(repository.list_results(source_task.task_id)), 2)

    def test_continuation_admission_rolls_back_job_and_row_together(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            source_task, source_item = self._seed_failed_item(environment)
            admitted, _ = self._admit(environment, source_task, source_item)

            with SQLiteTaskRepository(environment["database"]) as repository:
                service = RecoveryContinuationService(
                    repository,
                    snapshot_validator=lambda _id, _digest: None,
                )
                current_checkpoint = service.checkpoint_service.get(
                    source_item.item_id, task_id=source_task.task_id
                )
                with patch.object(
                    repository,
                    "_insert_job",
                    side_effect=RuntimeError("injected admission failure"),
                ):
                    with self.assertRaises(RuntimeError):
                        service.submit(
                            source_task.task_id,
                            source_item.item_id,
                            expected_checkpoint_version=current_checkpoint.checkpoint_version,
                            actor="operator",
                            maximum_active_jobs=100,
                        )

                self.assertIsNone(
                    repository.get_recovery_continuation_for_request(admitted.request_id)
                )
                self.assertEqual(repository.list_jobs(limit=100), ())
                self.assertEqual(
                    repository.get_recovery_request(admitted.request_id).status.value,
                    "pending",
                )
                self.assertEqual(repository.get_item(source_item.item_id).error, "original failure")

    def test_continuation_terminal_resolution_rolls_back_together(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            source_task, source_item = self._seed_failed_item(environment)
            admitted, _ = self._admit(environment, source_task, source_item)
            submitted = self._continue(environment, source_task, source_item)

            with SQLiteTaskRepository(environment["database"]) as repository:
                repository.mark_recovery_continuation_running(submitted.job.job_id)
                with patch.object(
                    repository,
                    "_resolve_recovery_request_locked",
                    side_effect=RuntimeError("injected terminal failure"),
                ):
                    with self.assertRaises(RuntimeError):
                        repository.complete_recovery_continuation(
                            submitted.job.job_id,
                            new_task_id="child-task",
                            new_result_id="child-result",
                            success=True,
                        )

                continuation = repository.get_recovery_continuation_for_job(submitted.job.job_id)
                request = repository.get_recovery_request(admitted.request_id)
                self.assertEqual(continuation.status, RecoveryContinuationStatus.RUNNING)
                self.assertIsNone(continuation.new_task_id)
                self.assertIsNone(continuation.new_result_id)
                self.assertEqual(request.status.value, "pending")
                self.assertEqual(repository.get_item(source_item.item_id).error, "original failure")
                self.assertEqual(len(repository.list_results(source_task.task_id)), 2)

    def test_stale_duplicate_and_inactive_refusals(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            source_task, source_item = self._seed_failed_item(environment)
            admitted, _ = self._admit(environment, source_task, source_item)
            api = self._api(environment)
            _status, checkpoint = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}",
            )

            # Stale version is refused and the current version is returned.
            stale, document = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}/recovery/continue",
                method="POST",
                body={"expectedCheckpointVersion": "0" * 64},
            )
            self.assertEqual(stale, 409)
            self.assertEqual(document["error"]["details"]["reason"], "stale_checkpoint")
            self.assertEqual(
                document["error"]["details"]["currentCheckpointVersion"],
                checkpoint["checkpoint_version"],
            )

            # First valid continuation.
            status, accepted = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}/recovery/continue",
                method="POST",
                body={"expectedCheckpointVersion": checkpoint["checkpoint_version"]},
            )
            self.assertEqual(status, 202)

            # Duplicate returns the existing continuation.
            status, document = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}/recovery/continue",
                method="POST",
                body={"expectedCheckpointVersion": checkpoint["checkpoint_version"]},
            )
            self.assertEqual(status, 409)
            self.assertEqual(
                document["error"]["details"]["reason"],
                "continuation_exists",
            )
            self.assertEqual(
                document["error"]["details"]["existingContinuation"]["continuation_id"],
                accepted["continuation_id"],
            )

            # A terminal request cannot be continued.
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            self._run_worker(environment, provider)
            _status, after = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}",
            )
            status, document = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}/recovery/continue",
                method="POST",
                body={"expectedCheckpointVersion": after["checkpoint_version"]},
            )
            self.assertEqual(status, 409)
            self.assertEqual(document["error"]["details"]["reason"], "request_not_active")
            with SQLiteTaskRepository(environment["database"]) as repository:
                self.assertEqual(
                    repository.get_recovery_request(admitted.request_id).status.value,
                    "completed",
                )

    def test_concurrent_submissions_produce_one_continuation_and_job(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            source_task, source_item = self._seed_failed_item(environment)
            admitted, _ = self._admit(environment, source_task, source_item)
            api = self._api(environment)
            _status, checkpoint = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}",
            )
            payload = {"expectedCheckpointVersion": checkpoint["checkpoint_version"]}
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = (
                    executor.submit(
                        api_request,
                        api,
                        f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}/recovery/continue",
                        method="POST",
                        body=payload,
                    ),
                    executor.submit(
                        api_request,
                        api,
                        f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}/recovery/continue",
                        method="POST",
                        body=payload,
                    ),
                )
                outcomes = tuple(future.result(timeout=10) for future in futures)
            self.assertEqual(sorted(value[0] for value in outcomes), [202, 409])
            accepted = next(value for value in outcomes if value[0] == 202)[1]
            conflict = next(value for value in outcomes if value[0] == 409)[1]
            self.assertEqual(
                conflict["error"]["details"]["existingContinuation"]["continuation_id"],
                accepted["continuation_id"],
            )
            with SQLiteTaskRepository(environment["database"]) as repository:
                continuations = repository.list_recovery_continuations(source_item.item_id)
                jobs = repository.list_jobs()
                self.assertEqual(len(continuations), 1)
                self.assertEqual(len(jobs), 1)

    def test_queue_full_rejects_without_continuation_or_job(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            source_task, source_item = self._seed_failed_item(environment)
            self._admit(environment, source_task, source_item)
            api = self._api(environment, maximum_active_jobs=1)
            now = datetime.now(UTC)
            with SQLiteTaskRepository(environment["database"]) as repository:
                repository.create_job(
                    AutomationJob(
                        "blocking-job",
                        AutomationCommand.PREVIEW,
                        AutomationJobStatus.PENDING,
                        now,
                        now,
                        limit=1,
                        configuration_snapshot_id=environment["snapshot"][0],
                        configuration_snapshot_digest=environment["snapshot"][1],
                    )
                )
            _status, checkpoint = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}",
            )
            status, document = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}/recovery/continue",
                method="POST",
                body={"expectedCheckpointVersion": checkpoint["checkpoint_version"]},
            )
            self.assertEqual(status, 409)
            self.assertEqual(document["error"]["code"], "queue_full")
            self.assertEqual(document["error"]["details"]["sideEffects"], "none")
            self.assertTrue(document["error"]["details"]["retrySafe"])
            with SQLiteTaskRepository(environment["database"]) as repository:
                self.assertEqual(len(repository.list_jobs()), 1)
                self.assertEqual(
                    repository.list_recovery_continuations(source_item.item_id),
                    (),
                )

    def test_snapshot_unavailable_is_refused_at_submission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            source_task, source_item = self._seed_failed_item(environment)
            self._admit(environment, source_task, source_item)
            with SQLiteTaskRepository(environment["database"]) as repository:
                repository.update_task(
                    replace(
                        source_task,
                        configuration_snapshot_id="missing-snapshot",
                        configuration_snapshot_digest="0" * 64,
                    )
                )
            api = self._api(environment)
            _status, checkpoint = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}",
            )
            status, document = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}/recovery/continue",
                method="POST",
                body={"expectedCheckpointVersion": checkpoint["checkpoint_version"]},
            )
            self.assertEqual(status, 503)
            self.assertEqual(document["error"]["code"], "configuration_unavailable")
            with SQLiteTaskRepository(environment["database"]) as repository:
                self.assertEqual(repository.list_jobs(), ())
                self.assertEqual(
                    repository.list_recovery_continuations(source_item.item_id),
                    (),
                )

    def test_worker_snapshot_mismatch_fails_before_storage_or_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            source_task, source_item = self._seed_failed_item(environment)
            admitted, _ = self._admit(environment, source_task, source_item)
            self._continue(environment, source_task, source_item)
            with SQLiteTaskRepository(environment["database"]) as repository:
                continuation = repository.get_recovery_continuation_for_request(admitted.request_id)
                assert continuation is not None
                job = repository.get_job(continuation.job_id)
                assert job is not None
                repository.update_job(
                    replace(
                        job,
                        configuration_snapshot_id="missing-snapshot",
                        configuration_snapshot_digest="0" * 64,
                    )
                )
            with (
                patch(
                    "mediaflow.final_cli.metadata_provider_registry_from_environment",
                    Mock(side_effect=AssertionError("reached Provider")),
                ) as provider_factory,
                patch.object(
                    RuntimeConfiguration,
                    "create_storages",
                    side_effect=AssertionError("reached Storage"),
                ) as storage_factory,
            ):
                code = final_main(
                    ["--config", str(environment["config"]), "worker", "run-next"],
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )
            self.assertEqual(code, 1)
            self.assertEqual(provider_factory.call_count, 0)
            self.assertEqual(storage_factory.call_count, 0)
            with SQLiteTaskRepository(environment["database"]) as repository:
                continuation = repository.get_recovery_continuation_for_request(admitted.request_id)
                assert continuation is not None
                self.assertEqual(continuation.status.value, "failed")
                self.assertEqual(
                    continuation.error,
                    "saved configuration snapshot is unavailable",
                )
                self.assertIn(
                    "restore the saved published revision",
                    continuation.recovery or "",
                )
                self.assertEqual(
                    repository.get_recovery_request(admitted.request_id).status.value,
                    "failed",
                )

    def test_worker_preflight_rejects_stale_linkage_before_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            source_task, source_item = self._seed_failed_item(environment)
            admitted, _ = self._admit(environment, source_task, source_item)
            self._continue(environment, source_task, source_item)
            # The item is reprocessed elsewhere before the Worker reaches the pipeline.
            with SQLiteTaskRepository(environment["database"]) as repository:
                item = repository.get_item(source_item.item_id)
                assert item is not None
                repository.upsert_item(
                    replace(
                        item,
                        status=TaskItemStatus.WAITING_METADATA,
                        stage="waiting_metadata",
                    )
                )
            provider_factory = Mock(side_effect=AssertionError("worker reached Provider"))
            with (
                patch(
                    "mediaflow.final_cli.metadata_provider_registry_from_environment",
                    provider_factory,
                ),
                patch.object(
                    RuntimeConfiguration,
                    "create_storages",
                    side_effect=AssertionError("worker reached Storage"),
                ) as storage_factory,
            ):
                code = final_main(
                    ["--config", str(environment["config"]), "worker", "run-next"],
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )
            self.assertEqual(code, 1)
            self.assertEqual(provider_factory.call_count, 0)
            self.assertEqual(storage_factory.call_count, 0)
            with SQLiteTaskRepository(environment["database"]) as repository:
                continuation = repository.get_recovery_continuation_for_request(admitted.request_id)
                assert continuation is not None
                self.assertEqual(continuation.status.value, "failed")
                self.assertIn("eligibility", continuation.error or "")
                self.assertEqual(
                    repository.get_recovery_request(admitted.request_id).status.value,
                    "failed",
                )

    def test_provider_failure_is_bounded_secret_free_and_readmissible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            source_task, source_item = self._seed_failed_item(environment)
            admitted, _ = self._admit(environment, source_task, source_item)
            api = self._api(environment)
            _status, checkpoint = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}",
            )
            status, _accepted = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}/recovery/continue",
                method="POST",
                body={"expectedCheckpointVersion": checkpoint["checkpoint_version"]},
            )
            self.assertEqual(status, 202)
            self._run_worker(
                environment,
                ExplodingSearchProvider(),
                expected_code=1,
            )
            with SQLiteTaskRepository(environment["database"]) as repository:
                first = repository.get_recovery_continuation_for_request(admitted.request_id)
                assert first is not None
                self.assertEqual(first.status.value, "failed")
                self.assertIn("single-item DryRun", first.error or "")
                self.assertNotIn("provider exception marker", first.error or "")
                self.assertEqual(
                    repository.get_recovery_request(admitted.request_id).status.value,
                    "failed",
                )
                self.assertEqual(
                    repository.get_item(source_item.item_id).status,
                    TaskItemStatus.PENDING,
                )
            history = Path(environment["root"] / "history.jsonl")
            self.assertNotIn("provider exception marker", history.read_text(encoding="utf-8"))

            # The item can be decided again: a fresh request and continuation.
            with SQLiteTaskRepository(environment["database"]) as repository:
                gate = RecoveryAdmissionService(
                    repository,
                    snapshot_validator=lambda _id, _digest: None,
                )
                after = gate.checkpoint_service.get(source_item.item_id)
                self.assertEqual(after.permitted_action_ids, ("retry",))
                second = gate.admit(
                    source_task.task_id,
                    source_item.item_id,
                    action_id="retry",
                    expected_checkpoint_version=after.checkpoint_version,
                    actor="operator",
                )
                self.assertNotEqual(second.request_id, admitted.request_id)
            self._continue(environment, source_task, source_item)
            self._run_worker(
                environment,
                DetailCountingProvider(
                    (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
                ),
            )
            with SQLiteTaskRepository(environment["database"]) as repository:
                continuations = repository.list_recovery_continuations(source_item.item_id)
                self.assertEqual(len(continuations), 2)
                self.assertEqual(
                    [value.status.value for value in continuations],
                    ["completed", "failed"],
                )
                requests = repository.list_recovery_requests(source_item.item_id)
                self.assertEqual(len(requests), 2)

    def test_zero_mutation_falsified_through_real_seams_and_tree_snapshot(self) -> None:
        def tree_snapshot(root: Path) -> tuple[tuple[str, int, int], ...]:
            if not root.is_dir():
                return ()
            rows: list[tuple[str, int, int]] = []
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    stat = path.stat()
                    rows.append((str(path.relative_to(root)), stat.st_size, stat.st_mtime_ns))
            return tuple(rows)

        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            source_root = Path(environment["display_source"]).parent.parent
            source_before = tree_snapshot(source_root)
            target_before = tree_snapshot(environment["target_root"])
            source_task, source_item = self._seed_failed_item(environment)
            admitted, _ = self._admit(environment, source_task, source_item)
            self._continue(environment, source_task, source_item)
            storage_construction = self._run_worker(
                environment,
                DetailCountingProvider(
                    (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
                ),
            )
            self.assertEqual(storage_construction.call_count, 1)
            self.assertEqual(tree_snapshot(source_root), source_before)
            self.assertEqual(tree_snapshot(environment["target_root"]), target_before)
            with SQLiteTaskRepository(environment["database"]) as repository:
                continuation = repository.get_recovery_continuation_for_request(admitted.request_id)
                assert continuation is not None
                new_task = repository.get_task(continuation.new_task_id or "")
                assert new_task is not None
                self.assertFalse(new_task.execute_authorized)
                job = repository.get_job(continuation.job_id)
                assert job is not None
                self.assertFalse(job.execute_authorized)

    def test_api_fail_closed_permission_and_malformed_body(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            source_task, source_item = self._seed_failed_item(environment)
            self._admit(environment, source_task, source_item)
            viewer = MediaFlowApi(
                SQLiteTaskRepository(environment["database"]),
                None,
                principals=(
                    ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ})),
                ),
            )
            path = (
                f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}/recovery/continue"
            )
            status, document = api_request(
                viewer,
                path,
                method="POST",
                body={"expectedCheckpointVersion": "0" * 64},
                token="viewer-token",
            )
            self.assertEqual(status, 403)
            self.assertEqual(document["error"]["code"], "forbidden")
            status, document = api_request(
                viewer,
                path,
                method="POST",
                body={},
                token="viewer-token",
            )
            self.assertEqual(status, 403)

            api = self._api(environment)
            _status, checkpoint = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}",
            )
            for body in ({}, {"extra": True}, {"expectedCheckpointVersion": 123}):
                with self.subTest(body=body):
                    status, document = api_request(
                        api,
                        path,
                        method="POST",
                        body=body,
                    )
                    self.assertEqual(status, 400)
                    self.assertEqual(document["error"]["code"], "invalid_request")
            status, document = api_request(
                api,
                path,
                method="POST",
                body={"expectedCheckpointVersion": "0" * 64},
                token=None,
            )
            self.assertEqual(status, 401)
            unknown = f"/api/v1/tasks/{source_task.task_id}/items/missing-item/recovery/continue"
            status, document = api_request(
                api,
                unknown,
                method="POST",
                body={"expectedCheckpointVersion": "0" * 64},
            )
            self.assertEqual(status, 404)
            mismatch = f"/api/v1/tasks/wrong-task/items/{source_item.item_id}/recovery/continue"
            status, document = api_request(
                api,
                mismatch,
                method="POST",
                body={"expectedCheckpointVersion": "0" * 64},
            )
            self.assertEqual(status, 404)

    def test_migration_preserves_rows_and_schema_marker_advances(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                coordinator = _coordinator(repository)
                task = coordinator.create(
                    "organize",
                    execute_authorized=False,
                    configuration_snapshot_id="revision-1",
                    configuration_snapshot_digest="a" * 64,
                )
                item = coordinator.begin_item(
                    task.task_id,
                    "source-storage",
                    "source",
                    "Media/C/Keep.mkv",
                    "Media/C/Keep.mkv",
                )
                item = replace(item, status=TaskItemStatus.FAILED, stage="failed", error="keep me")
                repository.upsert_item(item)
                repository._connection.execute("DROP INDEX one_active_recovery_continuation")
                repository._connection.execute("DROP INDEX recovery_continuations_item_created")
                repository._connection.execute("DROP TABLE recovery_continuations")
                repository._connection.execute(
                    "UPDATE schema_version SET version=24 WHERE component='runtime'"
                )
                repository._connection.commit()
                self.assertEqual(repository.get_item(item.item_id).error, "keep me")
            with SQLiteTaskRepository(database) as reopened:
                self.assertEqual(reopened.schema_version, SCHEMA_VERSION)
                tables = reopened._connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name='recovery_continuations'"
                ).fetchall()
                self.assertEqual(len(tables), 1)
                self.assertEqual(reopened.get_item(item.item_id).error, "keep me")
                self.assertEqual(reopened.list_recovery_continuations(item.item_id), ())


def _coordinator(repository):
    return PersistentTaskCoordinator(repository, repository)


if __name__ == "__main__":
    unittest.main()
