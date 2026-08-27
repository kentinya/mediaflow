from __future__ import annotations

import io
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.metadata_correction import MetadataCorrectionService
from mediaflow.domain.automation import AutomationCommand, AutomationJob, AutomationJobStatus
from mediaflow.domain.metadata import (
    MediaCandidate,
    MediaType,
    MetadataError,
    MetadataErrorCode,
    MetadataIdentificationStatus,
)
from mediaflow.domain.metadata_correction import MetadataCorrectionStatus
from mediaflow.domain.parser import ParseResult
from mediaflow.domain.scanner import FileChange
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import TaskItemStatus
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration
from mediaflow.interfaces.operator_ui import ASSETS
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_file_catalog import file_record
from tests.test_metadata_correction import CapturingProvider
from tests.test_metadata_review import identification


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


class MetadataCorrectionContinuationTests(unittest.TestCase):
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

    def _seed_resolved_correction(
        self,
        environment,
        *,
        execute_authorized: bool = True,
        direct_provider_id: str | None = None,
    ):
        strategy = development_strategy_configuration()
        policy = next(value for value in strategy.metadata_policies if value.policy_id == "C")
        snapshot_id, snapshot_digest = environment["snapshot"]
        with SQLiteFileIndexRepository(environment["database"]) as file_index:
            file_index.batch_upsert(
                (
                    file_record(
                        "file-one",
                        "source-storage",
                        "source",
                        environment["storage_path"],
                        change=FileChange.NEW,
                    ),
                )
            )
        with SQLiteTaskRepository(environment["database"]) as repository:
            coordinator = _coordinator(repository)
            task = coordinator.create(
                "organize",
                execute_authorized=execute_authorized,
                scope_path=environment["display_source"],
                item_limit=2,
                configuration_snapshot_id=snapshot_id,
                configuration_snapshot_digest=snapshot_digest,
                require_configuration_snapshot=True,
            )
            item = coordinator.begin_item(
                task.task_id,
                "source-storage",
                "source",
                environment["storage_path"],
                environment["display_source"],
            )
            review = MetadataCorrectionService(repository, strategy.metadata_policies).create(
                item,
                identification(
                    MetadataIdentificationStatus.NOT_FOUND,
                    count=0,
                    recognition_type="C",
                ),
                policy,
                ParseResult("Correct", year=2024),
            )
            # The production coordinator releases this lock when it creates the
            # waiting correction. Model that durable state before resolving it.
            repository.release(item.storage_id, item.source_path, item.task_id)
            sibling = coordinator.begin_item(
                task.task_id,
                "source-storage",
                "source",
                "Media/C/Sibling.mkv",
                str(Path(environment["display_source"]).parent / "Sibling.mkv"),
            )
            repository.upsert_item(
                replace(
                    sibling,
                    status=TaskItemStatus.SUCCESS,
                    stage="completed",
                )
            )
            repository.release(
                sibling.storage_id,
                sibling.source_path,
                sibling.task_id,
            )
            resolved = MetadataCorrectionService(repository, strategy.metadata_policies).resolve(
                review.review_id,
                query=None if direct_provider_id else "Correct Title",
                year=2024,
                media_type="movie",
                provider_id=direct_provider_id,
                actor="operator",
            )
            return task, item, resolved

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

    @staticmethod
    def _correction_link(api):
        _status, detail = api_request(api, "/api/v1/files/file-one")
        return next(
            value for value in detail["relatedReviews"] if value["kind"] == "metadata_correction"
        )

    def test_query_continuation_is_single_item_pinned_dryrun_and_durable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            source_task, source_item, review = self._seed_resolved_correction(environment)
            api = self._api(environment)
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct Title", year=2024),)
            )

            status, detail = api_request(api, "/api/v1/files/file-one")
            self.assertEqual(status, 200)
            link = next(
                value
                for value in detail["relatedReviews"]
                if value["kind"] == "metadata_correction"
            )
            self.assertTrue(link["canContinue"])
            self.assertEqual(link["configurationSnapshotId"], environment["snapshot"][0])

            payload = {
                "reviewId": review.review_id,
                "expectedCorrectionVersion": link["correctionVersion"],
            }
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = (
                    executor.submit(
                        api_request,
                        api,
                        "/api/v1/files/file-one/continue-dry-run",
                        method="POST",
                        body=payload,
                    ),
                    executor.submit(
                        api_request,
                        api,
                        "/api/v1/files/file-one/continue-dry-run",
                        method="POST",
                        body=payload,
                    ),
                )
                outcomes = tuple(future.result(timeout=10) for future in futures)
            self.assertEqual(sorted(value[0] for value in outcomes), [202, 409])
            accepted = next(value for value in outcomes if value[0] == 202)[1]
            conflict = next(value for value in outcomes if value[0] == 409)[1]
            self.assertEqual(accepted["executionMode"], "dry_run")
            self.assertEqual(
                conflict["error"]["details"]["continuationId"],
                accepted["continuationId"],
            )
            self.assertEqual(provider.movie_queries, [])

            status, detail = api_request(api, "/api/v1/files/file-one")
            self.assertEqual(detail["relatedReviews"][0]["continuation"]["status"], "queued")

            with SQLiteTaskRepository(environment["database"]) as repository:
                source_before = (
                    repository.get_task(source_task.task_id),
                    repository.get_item(source_item.item_id),
                    repository.list_items(source_task.task_id),
                )

            document = json.loads(environment["config"].read_text(encoding="utf-8"))
            document["resourceLibraries"][0]["displayRootPath"] = str(
                environment["root"] / "DisplayB"
            )
            with SQLiteConfigurationRepository(environment["database"]) as repository:
                managed = ManagedConfigurationService(repository)
                revision = managed.validate(
                    managed.import_draft(document, actor="tester").revision_id,
                    actor="tester",
                )
                managed.activate(revision.revision_id, expected_version=1, actor="tester")

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
            self.assertEqual(code, 0, f"{errors.getvalue()}\n{output.getvalue()}")
            self.assertEqual(storage_construction.call_count, 1)
            self.assertEqual(provider.movie_queries, [("Correct Title", 2024)])
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
                continuation = repository.get_metadata_correction_continuation_for_review(
                    review.review_id
                )
                assert continuation is not None
                self.assertEqual(continuation.status.value, "completed")
                new_task = repository.get_task(continuation.new_task_id or "")
                self.assertIsNotNone(new_task)
                assert new_task is not None
                new_items = repository.list_items(new_task.task_id)
                self.assertEqual(len(new_items), 1)
                self.assertEqual(new_items[0].status, TaskItemStatus.DRY_RUN)
                self.assertFalse(new_task.execute_authorized)
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

    def test_direct_id_uses_detail_path_and_preserves_c_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            _source_task, _source_item, review = self._seed_resolved_correction(
                environment, direct_provider_id="42"
            )
            api = self._api(environment)
            _status, detail = api_request(api, "/api/v1/files/file-one")
            link = next(
                value
                for value in detail["relatedReviews"]
                if value["kind"] == "metadata_correction"
            )
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct Title", year=2024),)
            )
            status, accepted = api_request(
                api,
                "/api/v1/files/file-one/continue-dry-run",
                method="POST",
                body={
                    "reviewId": review.review_id,
                    "expectedCorrectionVersion": link["correctionVersion"],
                },
            )
            self.assertEqual(status, 202)
            output, errors = io.StringIO(), io.StringIO()
            with patch(
                "mediaflow.final_cli.metadata_provider_registry_from_environment",
                lambda _ids: MetadataProviderRegistry((provider,)),
            ):
                code = final_main(
                    ["--config", str(environment["config"]), "worker", "run-next"],
                    stdout=output,
                    stderr=errors,
                )
            self.assertEqual(code, 0, errors.getvalue())
            self.assertEqual(provider.movie_queries, [])
            self.assertEqual(provider.movie_details, ["42"])
            with SQLiteTaskRepository(environment["database"]) as repository:
                continuation = repository.get_metadata_correction_continuation_for_review(
                    review.review_id
                )
                assert continuation is not None
                results = repository.list_results(continuation.new_task_id or "")
                self.assertEqual(results[0].recognition_type, "C")
                self.assertEqual(results[0].metadata_policy_id, "C")
                self.assertEqual(results[0].naming_policy_id, "A")
                self.assertEqual(results[0].classification_policy_id, "A")

    def test_invalid_admission_fails_before_snapshot_provider_or_storage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            _source_task, _source_item, review = self._seed_resolved_correction(environment)
            api = self._api(environment)
            cases = (
                {},
                {"reviewId": review.review_id},
                {
                    "reviewId": review.review_id,
                    "expectedCorrectionVersion": "0" * 64,
                    "extra": True,
                },
                {
                    "reviewId": "missing-review",
                    "expectedCorrectionVersion": "0" * 64,
                },
            )
            for body in cases:
                with self.subTest(body=body):
                    status, document = api_request(
                        api,
                        "/api/v1/files/file-one/continue-dry-run",
                        method="POST",
                        body=body,
                    )
                    self.assertEqual(status, 400)
                    self.assertEqual(document["error"]["code"], "invalid_request")
            stale = {
                "reviewId": review.review_id,
                "expectedCorrectionVersion": "0" * 64,
            }
            status, document = api_request(
                api,
                "/api/v1/files/file-one/continue-dry-run",
                method="POST",
                body=stale,
            )
            self.assertEqual(status, 409)
            with SQLiteTaskRepository(environment["database"]) as repository:
                self.assertIsNone(
                    repository.get_metadata_correction_continuation_for_review(review.review_id)
                )
                jobs = repository.list_jobs()
                self.assertEqual(jobs, ())

    def test_queue_full_rejects_without_continuation_or_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            _source_task, _source_item, review = self._seed_resolved_correction(environment)
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
            status, document = api_request(
                api,
                "/api/v1/files/file-one/continue-dry-run",
                method="POST",
                body={
                    "reviewId": review.review_id,
                    "expectedCorrectionVersion": self._correction_link(api)["correctionVersion"],
                },
            )
            self.assertEqual(status, 409)
            self.assertEqual(document["error"]["code"], "queue_full")
            self.assertEqual(document["error"]["details"]["sideEffects"], "none")
            self.assertTrue(document["error"]["details"]["retrySafe"])
            with SQLiteTaskRepository(environment["database"]) as repository:
                self.assertEqual(len(repository.list_jobs()), 1)
                self.assertIsNone(
                    repository.get_metadata_correction_continuation_for_review(review.review_id)
                )

    def test_snapshot_is_validated_at_admission_before_queueing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            source_task, _source_item, review = self._seed_resolved_correction(environment)
            api = self._api(environment)
            link = self._correction_link(api)
            valid_id, valid_digest = environment["snapshot"]
            for snapshot_id, snapshot_digest in (
                ("missing-snapshot", "0" * 64),
                (valid_id, "0" * 64),
            ):
                with self.subTest(snapshot_id=snapshot_id):
                    with SQLiteTaskRepository(environment["database"]) as repository:
                        repository.update_task(
                            replace(
                                source_task,
                                configuration_snapshot_id=snapshot_id,
                                configuration_snapshot_digest=snapshot_digest,
                            )
                        )
                    status, document = api_request(
                        api,
                        "/api/v1/files/file-one/continue-dry-run",
                        method="POST",
                        body={
                            "reviewId": review.review_id,
                            "expectedCorrectionVersion": link["correctionVersion"],
                        },
                    )
                    self.assertEqual(status, 503)
                    self.assertEqual(document["error"]["code"], "configuration_unavailable")
                    with SQLiteTaskRepository(environment["database"]) as repository:
                        self.assertEqual(repository.list_jobs(), ())
            with SQLiteTaskRepository(environment["database"]) as repository:
                self.assertEqual(
                    repository.get_task(source_task.task_id).configuration_snapshot_digest, "0" * 64
                )
                self.assertNotEqual(valid_digest, "0" * 64)

    def test_snapshot_unavailable_is_durable_and_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            _source_task, _source_item, review = self._seed_resolved_correction(environment)
            api = self._api(environment)
            _status, detail = api_request(api, "/api/v1/files/file-one")
            link = next(
                value
                for value in detail["relatedReviews"]
                if value["kind"] == "metadata_correction"
            )
            status, _accepted = api_request(
                api,
                "/api/v1/files/file-one/continue-dry-run",
                method="POST",
                body={
                    "reviewId": review.review_id,
                    "expectedCorrectionVersion": link["correctionVersion"],
                },
            )
            self.assertEqual(status, 202)
            provider = DetailCountingProvider(())
            with SQLiteTaskRepository(environment["database"]) as repository:
                continuation = repository.get_metadata_correction_continuation_for_review(
                    review.review_id
                )
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
            output, errors = io.StringIO(), io.StringIO()
            provider_factory = Mock(side_effect=lambda _ids: MetadataProviderRegistry((provider,)))
            with (
                patch(
                    "mediaflow.final_cli.metadata_provider_registry_from_environment",
                    provider_factory,
                ),
                patch.object(
                    RuntimeConfiguration,
                    "create_storages",
                    side_effect=AssertionError("snapshot failure constructed Storage"),
                ) as storage_construction,
            ):
                code = final_main(
                    ["--config", str(environment["config"]), "worker", "run-next"],
                    stdout=output,
                    stderr=errors,
                )
            self.assertEqual(code, 1, errors.getvalue())
            self.assertEqual(provider_factory.call_count, 0)
            self.assertEqual(storage_construction.call_count, 0)
            self.assertEqual(provider.movie_queries, [])
            with SQLiteTaskRepository(environment["database"]) as repository:
                continuation = repository.get_metadata_correction_continuation_for_review(
                    review.review_id
                )
                assert continuation is not None
                self.assertEqual(continuation.status.value, "failed")
                self.assertEqual(continuation.error, "saved configuration snapshot is unavailable")
                self.assertIn("restore the saved published revision", continuation.recovery)
                self.assertEqual(
                    repository.get_metadata_correction(review.review_id).status,
                    MetadataCorrectionStatus.RESOLVED,
                )
            _status, detail = api_request(api, "/api/v1/files/file-one")
            visible = next(
                value for value in detail["relatedReviews"] if value["reviewId"] == review.review_id
            )
            self.assertEqual(visible["continuation"]["status"], "failed")
            self.assertEqual(visible["continuation"]["failureCategory"], "snapshot_missing")
            self.assertTrue(visible["continuation"]["snapshotUnavailable"])

    def test_provider_failure_is_durable_and_retry_is_one_item(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            source_task, source_item, review = self._seed_resolved_correction(environment)
            api = self._api(environment)
            link = self._correction_link(api)
            payload = {
                "reviewId": review.review_id,
                "expectedCorrectionVersion": link["correctionVersion"],
            }
            status, accepted = api_request(
                api,
                "/api/v1/files/file-one/continue-dry-run",
                method="POST",
                body=payload,
            )
            self.assertEqual(status, 202)
            failing_provider = FailingSearchProvider()
            output, errors = io.StringIO(), io.StringIO()
            with patch(
                "mediaflow.final_cli.metadata_provider_registry_from_environment",
                lambda _ids: MetadataProviderRegistry((failing_provider,)),
            ):
                code = final_main(
                    ["--config", str(environment["config"]), "worker", "run-next"],
                    stdout=output,
                    stderr=errors,
                )
            self.assertEqual(code, 1, errors.getvalue())
            self.assertGreaterEqual(len(failing_provider.movie_queries), 1)
            with SQLiteTaskRepository(environment["database"]) as repository:
                first = repository.get_metadata_correction_continuation_for_review(review.review_id)
                assert first is not None
                self.assertEqual(first.status.value, "failed")
                self.assertIn("single-item DryRun", first.error or "")
                self.assertTrue(first.recovery)
                self.assertEqual(
                    repository.get_item(source_item.item_id).status, TaskItemStatus.PENDING
                )
                self.assertEqual(repository.get_task(source_task.task_id), source_task)
                failed_job = repository.get_job(first.job_id)
                assert failed_job is not None
                self.assertEqual(failed_job.status.value, "failed")

            successful_provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct Title", year=2024),)
            )
            link = self._correction_link(api)
            self.assertTrue(link["canContinue"])
            status, retry = api_request(
                api,
                "/api/v1/files/file-one/continue-dry-run",
                method="POST",
                body={
                    "reviewId": review.review_id,
                    "expectedCorrectionVersion": link["correctionVersion"],
                },
            )
            self.assertEqual(status, 202)
            self.assertNotEqual(retry["continuationId"], accepted["continuationId"])
            with patch(
                "mediaflow.final_cli.metadata_provider_registry_from_environment",
                lambda _ids: MetadataProviderRegistry((successful_provider,)),
            ):
                code = final_main(
                    ["--config", str(environment["config"]), "worker", "run-next"],
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )
            self.assertEqual(code, 0)
            with SQLiteTaskRepository(environment["database"]) as repository:
                latest = repository.get_metadata_correction_continuation_for_review(
                    review.review_id
                )
                assert latest is not None
                self.assertEqual(latest.continuation_id, retry["continuationId"])
                self.assertEqual(latest.status.value, "completed")
                self.assertEqual(
                    repository.get_item(source_item.item_id).status,
                    TaskItemStatus.PENDING,
                )
                jobs = repository.list_jobs()
                self.assertEqual(len(jobs), 2)
                self.assertEqual(
                    {job.status.value for job in jobs},
                    {"failed", "completed"},
                )

    def test_unexpected_provider_exception_is_not_persisted_in_new_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            _source_task, _source_item, review = self._seed_resolved_correction(environment)
            api = self._api(environment)
            link = self._correction_link(api)
            status, _accepted = api_request(
                api,
                "/api/v1/files/file-one/continue-dry-run",
                method="POST",
                body={
                    "reviewId": review.review_id,
                    "expectedCorrectionVersion": link["correctionVersion"],
                },
            )
            self.assertEqual(status, 202)
            provider = ExplodingSearchProvider()
            with patch(
                "mediaflow.final_cli.metadata_provider_registry_from_environment",
                lambda _ids: MetadataProviderRegistry((provider,)),
            ):
                code = final_main(
                    ["--config", str(environment["config"]), "worker", "run-next"],
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )
            self.assertEqual(code, 1)
            with SQLiteTaskRepository(environment["database"]) as repository:
                continuation = repository.get_metadata_correction_continuation_for_review(
                    review.review_id
                )
                assert continuation is not None
                self.assertEqual(continuation.status.value, "failed")
                self.assertEqual(continuation.error, "single-item DryRun analysis failed")
                self.assertIsNotNone(continuation.new_task_id)
                items = repository.list_items(continuation.new_task_id)
                results = repository.list_results(continuation.new_task_id)
                self.assertEqual(len(items), 1)
                self.assertEqual(len(results), 1)
                self.assertEqual(items[0].error, "single-item DryRun analysis failed")
                self.assertNotIn("provider exception marker", items[0].error or "")
                self.assertNotIn("provider exception marker", results[0].error or "")
            history = Path(environment["root"] / "history.jsonl")
            self.assertNotIn("provider exception marker", history.read_text(encoding="utf-8"))

    def test_linkage_eligibility_and_worker_preflight_fail_before_provider_or_storage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            _source_task, source_item, review = self._seed_resolved_correction(environment)
            api = self._api(environment)
            link = self._correction_link(api)
            payload = {
                "reviewId": review.review_id,
                "expectedCorrectionVersion": link["correctionVersion"],
            }
            with SQLiteFileIndexRepository(environment["database"]) as file_index:
                file_index.batch_upsert(
                    (
                        file_record(
                            "file-two",
                            "source-storage",
                            "source",
                            "Media/C/Other.mkv",
                            change=FileChange.NEW,
                        ),
                    )
                )
            status, document = api_request(
                api,
                "/api/v1/files/file-two/continue-dry-run",
                method="POST",
                body=payload,
            )
            self.assertEqual(status, 400)
            self.assertEqual(document["error"]["code"], "invalid_request")
            with SQLiteTaskRepository(environment["database"]) as repository:
                repository.upsert_item(
                    replace(source_item, status=TaskItemStatus.SUCCESS, stage="completed")
                )
            status, document = api_request(
                api,
                "/api/v1/files/file-one/continue-dry-run",
                method="POST",
                body=payload,
            )
            self.assertEqual(status, 400)
            self.assertEqual(document["error"]["code"], "invalid_request")

            # Restore the eligible source item, queue it, then make the durable
            # linkage stale before the Worker reaches Provider/Storage setup.
            with SQLiteTaskRepository(environment["database"]) as repository:
                repository.upsert_item(
                    replace(
                        source_item,
                        status=TaskItemStatus.PENDING,
                        stage="metadata_correction_resolved",
                    )
                )
            status, accepted = api_request(
                api,
                "/api/v1/files/file-one/continue-dry-run",
                method="POST",
                body=payload,
            )
            self.assertEqual(status, 202)
            with SQLiteTaskRepository(environment["database"]) as repository:
                item = repository.get_item(source_item.item_id)
                assert item is not None
                repository.upsert_item(replace(item, status=TaskItemStatus.SUCCESS))
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
                continuation = repository.get_metadata_correction_continuation_for_review(
                    review.review_id
                )
                assert continuation is not None
                self.assertEqual(continuation.status.value, "failed")
                self.assertIn("eligibility", continuation.error or "")
            _status, detail = api_request(api, "/api/v1/files/file-one")
            visible = next(
                value for value in detail["relatedReviews"] if value["reviewId"] == review.review_id
            )
            self.assertEqual(visible["continuation"]["status"], "failed")
            self.assertFalse(visible["canContinue"])
            self.assertIn("repair", visible["continuation"]["nextAction"])

    def test_stale_and_cancelled_continuations_are_visible_and_recoverable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            _source_task, _source_item, review = self._seed_resolved_correction(environment)
            api = self._api(environment)
            link = self._correction_link(api)
            status, accepted = api_request(
                api,
                "/api/v1/files/file-one/continue-dry-run",
                method="POST",
                body={
                    "reviewId": review.review_id,
                    "expectedCorrectionVersion": link["correctionVersion"],
                },
            )
            self.assertEqual(status, 202)
            with SQLiteTaskRepository(environment["database"]) as repository:
                job = repository.claim_next_job(datetime.now(UTC))
                assert job is not None
                continuation = repository.get_metadata_correction_continuation_for_job(job.job_id)
                assert continuation is not None
                from mediaflow.application.metadata_correction_continuation import (
                    MetadataCorrectionContinuationWorkerService,
                )

                worker = MetadataCorrectionContinuationWorkerService(repository)
                with SQLiteFileIndexRepository(environment["database"]) as file_index:
                    worker.prepare(job.job_id, file_index=file_index)
                worker.started(job.job_id)
                repository.update_job(
                    replace(
                        job,
                        status=job.status,
                        updated_at=datetime.now(UTC) - timedelta(hours=2),
                    )
                )
            _status, detail = api_request(api, "/api/v1/files/file-one")
            current = next(
                value
                for value in detail["relatedReviews"]
                if value["kind"] == "metadata_correction"
            )["continuation"]
            self.assertEqual(current["status"], "stale")
            self.assertIn("requeue", current["nextAction"])
            status, requeued = api_request(
                api,
                f"/api/v1/jobs/{accepted['jobId']}/requeue-stale",
                method="POST",
            )
            self.assertEqual(status, 200)
            self.assertEqual(requeued["status"], "pending")
            with SQLiteTaskRepository(environment["database"]) as repository:
                current = repository.get_metadata_correction_continuation_for_review(
                    review.review_id
                )
                assert current is not None
                self.assertEqual(current.status.value, "queued")
            status, cancelled = api_request(
                api,
                f"/api/v1/jobs/{accepted['jobId']}/cancel",
                method="POST",
            )
            self.assertEqual(status, 200)
            self.assertEqual(cancelled["status"], "cancelled")
            with SQLiteTaskRepository(environment["database"]) as repository:
                current = repository.get_metadata_correction_continuation_for_review(
                    review.review_id
                )
                assert current is not None
                self.assertEqual(current.status.value, "cancelled")
            _status, detail = api_request(api, "/api/v1/files/file-one")
            current = next(
                value
                for value in detail["relatedReviews"]
                if value["kind"] == "metadata_correction"
            )["continuation"]
            self.assertEqual(current["status"], "cancelled")
            self.assertIn("continue", current["nextAction"])

            status, claimed_submission = api_request(
                api,
                "/api/v1/files/file-one/continue-dry-run",
                method="POST",
                body={
                    "reviewId": review.review_id,
                    "expectedCorrectionVersion": link["correctionVersion"],
                },
            )
            self.assertEqual(status, 202)
            with SQLiteTaskRepository(environment["database"]) as repository:
                claimed = repository.claim_next_job(datetime.now(UTC))
                assert claimed is not None
                self.assertEqual(claimed.job_id, claimed_submission["jobId"])
            status, _cancelled = api_request(
                api,
                f"/api/v1/jobs/{claimed_submission['jobId']}/cancel",
                method="POST",
            )
            self.assertEqual(status, 200)
            with SQLiteTaskRepository(environment["database"]) as repository:
                current = repository.get_metadata_correction_continuation_for_review(
                    review.review_id
                )
                assert current is not None
                self.assertEqual(current.status.value, "cancelled")

    def test_operator_ui_action_is_explicit_and_stateful(self) -> None:
        script = ASSETS["/ui/app.js"][1].decode("utf-8")
        self.assertIn("Continue as DryRun", script)
        self.assertIn("Confirm Continue as DryRun", script)
        self.assertIn("/api/v1/files/${encodeURIComponent(id)}/continue-dry-run", script)
        self.assertIn("expectedCorrectionVersion", script)
        self.assertIn("Source Task", script)
        self.assertIn("Storage mutation", script)
        self.assertIn("Continuation status:", script)
        self.assertIn("Failure category:", script)
        self.assertIn("stale", script)
        self.assertIn("Requeue stale continuation", script)
        self.assertIn("/api/v1/jobs/${encodeURIComponent(jobId)}/requeue-stale", script)
        self.assertIn("Retry this correction as DryRun", script)
        self.assertIn("Next action:", script)
        self.assertIn("Source Task and siblings are unchanged", script)

    def test_operator_ui_continuation_section_is_attached_to_file_detail(self) -> None:
        script = ASSETS["/ui/app.js"][1].decode("utf-8")
        body = _js_function_body(script, "renderMetadataContinuation")

        # Both branches must reach the page. Building the section and returning it to a
        # caller that discards the node leaves the whole journey invisible.
        self.assertEqual(body.count("detailContent.append(section)"), 2)
        self.assertNotIn("return section", body)
        self.assertIn("renderMetadataContinuation(id, continuationReview);", script)
        self.assertIn(
            "item.status === 'resolved' && (item.canContinue || item.continuation)",
            script,
        )

        # Pre-submission disclosure and the explicit entry point live on the
        # no-continuation branch.
        for expected in (
            "['Source Task', review.taskId]",
            "['Correction identity', review.correctionVersion]",
            "['Configuration snapshot', review.configurationSnapshotId || '-']",
            "['Items selected', '1'], ['Authority', 'DRY_RUN_ONLY'], ['Storage mutation', 'NONE']",
            "actionButton('Continue as DryRun'",
        ):
            self.assertIn(expected, body)

        # Every continuation state renders its own status, recovery and next action.
        for expected in (
            "`Continuation status: ${current.status}. `",
            "if (current.error)",
            "if (current.recovery)",
            "if (current.nextAction)",
            "actionButton('Open continuation job'",
        ):
            self.assertIn(expected, body)

        # Control visibility follows the API state, not the operator's guess.
        self.assertIn("if (current.taskId) {", body)
        self.assertLess(
            body.index("actionButton('Open continuation job'"),
            body.index("if (current.taskId) {"),
        )
        self.assertIn(
            "if ((current.status === 'failed' || current.status === 'cancelled') "
            "&& review.canContinue) {",
            body,
        )
        self.assertIn("if (current.status === 'stale') {", body)

        # Rendering is read-only: no request, submission or requeue happens on view.
        self.assertNotIn("api(", body)
        self.assertNotIn("fetch(", body)

    def test_file_detail_projection_matches_web_continuation_states(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            _source_task, source_item, review = self._seed_resolved_correction(environment)
            api = self._api(environment)

            link = self._correction_link(api)
            self.assertTrue(link["canContinue"])
            self.assertNotIn("continuation", link)

            status, _accepted = api_request(
                api,
                "/api/v1/files/file-one/continue-dry-run",
                method="POST",
                body={
                    "reviewId": review.review_id,
                    "expectedCorrectionVersion": link["correctionVersion"],
                },
            )
            self.assertEqual(status, 202)
            queued = self._correction_link(api)
            self.assertFalse(queued["canContinue"])
            self.assertEqual(queued["continuation"]["status"], "queued")
            self.assertIsNone(queued["continuation"]["taskId"])
            self.assertIn("Worker", queued["continuation"]["nextAction"])

            with patch(
                "mediaflow.final_cli.metadata_provider_registry_from_environment",
                lambda _ids: MetadataProviderRegistry((FailingSearchProvider(),)),
            ):
                code = final_main(
                    ["--config", str(environment["config"]), "worker", "run-next"],
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )
            self.assertEqual(code, 1)
            failed = self._correction_link(api)
            self.assertTrue(failed["canContinue"])
            self.assertEqual(failed["continuation"]["status"], "failed")
            self.assertEqual(failed["continuation"]["executionMode"], "dry_run")
            self.assertTrue(failed["continuation"]["error"])
            self.assertTrue(failed["continuation"]["recovery"])
            self.assertIn("retry", failed["continuation"]["nextAction"])
            self.assertNotIn("provider unavailable", json.dumps(failed))

            status, _retry = api_request(
                api,
                "/api/v1/files/file-one/continue-dry-run",
                method="POST",
                body={
                    "reviewId": review.review_id,
                    "expectedCorrectionVersion": failed["correctionVersion"],
                },
            )
            self.assertEqual(status, 202)
            with patch(
                "mediaflow.final_cli.metadata_provider_registry_from_environment",
                lambda _ids: MetadataProviderRegistry(
                    (
                        DetailCountingProvider(
                            (
                                MediaCandidate(
                                    "tmdb",
                                    "42",
                                    MediaType.MOVIE,
                                    "Correct Title",
                                    year=2024,
                                ),
                            )
                        ),
                    )
                ),
            ):
                code = final_main(
                    ["--config", str(environment["config"]), "worker", "run-next"],
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )
            self.assertEqual(code, 0)
            completed = self._correction_link(api)
            self.assertFalse(completed["canContinue"])
            self.assertEqual(completed["continuation"]["status"], "completed")
            self.assertEqual(completed["continuation"]["executionMode"], "dry_run")
            self.assertTrue(completed["continuation"]["taskId"])
            self.assertTrue(completed["continuation"]["resultId"])
            self.assertIn("source remains unchanged", completed["continuation"]["nextAction"])

            with SQLiteTaskRepository(environment["database"]) as repository:
                self.assertEqual(
                    repository.get_item(source_item.item_id).status,
                    TaskItemStatus.PENDING,
                )
            self.assertEqual(environment["source_file"].read_bytes(), b"unchanged-source")
            self.assertFalse(any(environment["target_root"].iterdir()))


def _js_function_body(script: str, name: str) -> str:
    """Return one JS function body from the served asset by brace matching."""

    opening = script.index("{", script.index(f"function {name}("))
    depth = 0
    for index in range(opening, len(script)):
        if script[index] == "{":
            depth += 1
        elif script[index] == "}":
            depth -= 1
            if depth == 0:
                return script[opening + 1 : index]
    raise AssertionError(f"function {name} has an unbalanced body")


def _coordinator(repository):
    from mediaflow.application.task_runtime import PersistentTaskCoordinator

    return PersistentTaskCoordinator(repository, repository)


if __name__ == "__main__":
    unittest.main()
