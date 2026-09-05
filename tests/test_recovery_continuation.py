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

from mediaflow.application.automation import AutomationJobService
from mediaflow.application.classification_review import ClassificationReviewService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.conflict_resolution import ConfirmationService
from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_execution import ManualOrganizeExecutionService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.manual_recovery_continuation import (
    ManualRecoveryContinuationService,
)
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.metadata_correction import MetadataCorrectionService
from mediaflow.application.metadata_review import MetadataReviewService
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.application.recognition_review import RecognitionReviewService
from mediaflow.application.recovery_admission import RecoveryAdmissionService
from mediaflow.application.recovery_continuation import (
    RecoveryContinuationService,
)
from mediaflow.application.scanner import StorageScanner
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.automation import AutomationCommand, AutomationJob, AutomationJobStatus
from mediaflow.domain.classification_review import ClassificationReviewStatus
from mediaflow.domain.library import ResourceLibrary
from mediaflow.domain.metadata import (
    CandidateMatchResult,
    CandidateMatchStatus,
    CandidateScore,
    MediaCandidate,
    MediaType,
    MetadataError,
    MetadataErrorCode,
    MetadataIdentificationResult,
    MetadataIdentificationStatus,
    ScoreComponent,
)
from mediaflow.domain.metadata_review import MetadataReviewStatus
from mediaflow.domain.organizer import (
    ConflictStrategy,
    ExecutionEffectCertainty,
    ExecutionResult,
    ExecutionStatus,
)
from mediaflow.domain.recognition import RecognitionType
from mediaflow.domain.recognition_review import RecognitionReviewStatus
from mediaflow.domain.recovery_continuation import RecoveryContinuationStatus
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import (
    ConfirmationStatus,
    PersistentResultRecord,
    TaskItemStatus,
)
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration
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


class SelectiveManualExecutor:
    """Fail one named source once; later instances may use the real executor."""

    def __init__(self, failed_name: str | None = None, real=None):
        self.failed_name = failed_name
        self.real = real or OrganizerExecutor()
        self.calls: list[str] = []

    def execute(self, plan, storages, **kwargs):
        self.calls.append(plan.source)
        if self.failed_name and plan.source.endswith(self.failed_name):
            return ExecutionResult(
                ExecutionStatus.FAILED,
                plan.operation,
                plan.source,
                plan.target,
                errors=("injected pre-mutation failure",),
                plan_id=plan.plan_id,
                effect_certainty=ExecutionEffectCertainty.NONE,
            )
        return self.real.execute(plan, storages, **kwargs)


class PhaseCandidatesProvider(DetailCountingProvider):
    """Fake provider whose search and detail results tests swap between phases.

    ``replace`` lets a test pin one analysis outcome for the manual journey and a
    different one for the later single-item re-analysis, without changing the
    provider identity pinned in the configuration snapshot.
    """

    def __init__(self, candidates):
        super().__init__(tuple(candidates))
        self.search_candidates = tuple(candidates)

    def replace(self, *, candidates=None, search=None):
        if candidates is not None:
            self._candidates = tuple(candidates)
        if search is not None:
            self.search_candidates = tuple(search)

    def search_movie(self, query, policy=None, **kwargs):
        self.movie_queries.append((query.title_candidate, query.year))
        return self.search_candidates

    def search_tv(self, query, policy=None, **kwargs):
        self.tv_queries.append((query.title_candidate, query.year))
        return self.search_candidates


class RecoveryContinuationTests(unittest.TestCase):
    def _environment(self, directory: str | Path, *, source_subdir: str = "C", document_patch=None):
        root = Path(directory)
        source_root = root / "Incoming"
        target_root = root / "Target"
        media_root = source_root / "Media" / source_subdir
        media_root.mkdir(parents=True)
        target_root.mkdir()
        source_file = media_root / "Correct.2024.mkv"
        source_file.write_bytes(b"unchanged-source")
        database = root / "runtime.sqlite3"
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        document["storages"][0]["rootPath"] = str(source_root)
        document["storages"][1]["rootPath"] = str(target_root)
        document["resourceLibraries"][0]["displayRootPath"] = str(source_root)
        if document_patch is not None:
            document_patch(document)
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
            "storage_path": f"Media/{source_subdir}/Correct.2024.mkv",
            "display_source": str(source_root / source_subdir / "Correct.2024.mkv"),
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

    def _manual_services(self, environment, provider, *, executor=None):
        database = environment["database"]
        task_repository = SQLiteTaskRepository(database)
        file_index = SQLiteFileIndexRepository(database)
        configuration_repository = SQLiteConfigurationRepository(database)
        configuration_service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=str(database),
        )
        catalog = FileCatalogService(
            file_index,
            ("source",),
            ("source-storage",),
            task_repository=task_repository,
        )
        intents = ManualOrganizeIntentService(
            task_repository,
            catalog,
            configuration_service=configuration_service,
        )
        previews = ManualOrganizePreviewService(
            task_repository,
            intents,
            configuration_service=configuration_service,
            providers=MetadataProviderRegistry((provider,)),
        )
        execution = ManualOrganizeExecutionService(
            task_repository,
            previews,
            executor=executor or OrganizerExecutor(),
        )
        return {
            "task_repository": task_repository,
            "file_index": file_index,
            "configuration_repository": configuration_repository,
            "configuration_service": configuration_service,
            "catalog": catalog,
            "intents": intents,
            "previews": previews,
            "execution": execution,
        }

    def _scan_manual_source(
        self, environment, *, names=("Correct.2024.mkv",), source_subdir: str = "C"
    ):
        source_root = Path(environment["root"]) / "Incoming"
        media_root = source_root / "Media" / source_subdir
        media_root.mkdir(parents=True, exist_ok=True)
        for name in names:
            path = Path(media_root, name)
            if not path.exists():
                path.write_bytes((name.encode("utf-8") + b"x" * 200)[:123])
        database = environment["database"]
        with (
            SQLiteFileIndexRepository(database) as file_index,
        ):
            scanner = StorageScanner(
                {"source-storage": LocalStorage("source-storage", source_root)},
                file_index,
            )
            library = ResourceLibrary("source", "Source", "source-storage", "Media")
            scanner.scan(library)
            records = tuple(
                value
                for value in file_index.list_by_resource_library("source")
                if Path(value.path).name in names
            )
        return records

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

    def _fail_manual_organize(self, environment, provider, *, executor=None, source_subdir="C"):
        """Run a real manual organize that fails at the executor for the one source."""
        records = self._scan_manual_source(environment, source_subdir=source_subdir)
        record = records[0]
        services = self._manual_services(
            environment,
            provider,
            executor=executor or SelectiveManualExecutor("Correct.2024.mkv"),
        )
        with SQLiteTaskRepository(environment["database"]):
            preview = services["previews"].create_current(
                scope_kind="file",
                actor="operator",
                file_id=record.file_id,
                resource_library_id=record.resource_library_id,
                occurrence_id=record.occurrence_id,
                fingerprint=record.fingerprint,
            )
            item = preview.items[0]
            authority = services["execution"].authorize(
                preview.preview_id,
                [item.item_id],
                expected_intent_version=preview.intent_version,
                expected_item_versions={item.item_id: item.item_version},
                snapshot_id=preview.configuration_snapshot_id,
                snapshot_digest=preview.configuration_snapshot_digest,
                actor="operator",
                confirmation=True,
            )
            run = services["execution"].execute(
                authority.authorization_id, actor="operator", confirmation=True
            )
            self.assertEqual("failed", run.items[0].status.value)
            self.assertTrue(environment["source_file"].exists())
        return services, run, record, preview

    @staticmethod
    def _close_manual_services(services):
        for key in ("task_repository", "file_index", "configuration_repository"):
            value = services.get(key)
            if value is not None:
                value.close()

    def _submit_continuation(self, services, run, repository):
        """Submit the continuation for the item's already-active recovery request."""
        refreshed = services["execution"]._checkpoint_service.get(
            run.items[0].task_item_id, task_id=run.task_id
        )
        return RecoveryContinuationService(
            repository,
            snapshot_validator=services["execution"]._validate_checkpoint_snapshot,
            checkpoint_service=services["execution"]._checkpoint_service,
        ).submit(
            run.task_id,
            run.items[0].task_item_id,
            expected_checkpoint_version=refreshed.checkpoint_version,
            actor="operator",
            maximum_active_jobs=10,
        )

    def _admit_and_continue(self, services, run, repository):
        """Admit retry for the failed manual item and submit its continuation."""
        checkpoint = services["execution"]._checkpoint_service.get(
            run.items[0].task_item_id, task_id=run.task_id
        )
        RecoveryAdmissionService(
            repository,
            snapshot_validator=services["execution"]._validate_checkpoint_snapshot,
            checkpoint_service=services["execution"]._checkpoint_service,
        ).admit(
            run.task_id,
            run.items[0].task_item_id,
            action_id="retry",
            expected_checkpoint_version=checkpoint.checkpoint_version,
            actor="operator",
        )
        return self._submit_continuation(services, run, repository)

    def _recovery_api(self, environment, services):
        """Expose the manual recovery continuation journey over the real API."""
        recovery = ManualRecoveryContinuationService(
            services["task_repository"],
            intent_service=services["intents"],
            preview_service=services["previews"],
            execution_service=services["execution"],
            checkpoint_service=services["execution"]._checkpoint_service,
        )
        operator = ResolvedApiPrincipal("operator", "operator-token", frozenset(ApiPermission))
        viewer = ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
        api = MediaFlowApi(
            services["task_repository"],
            None,
            principals=(operator, viewer),
            file_catalog=services["catalog"],
            configuration_service=services["configuration_service"],
            configuration_snapshot_id=environment["snapshot"][0],
            configuration_snapshot_digest=environment["snapshot"][1],
            manual_intent_service=services["intents"],
            manual_preview_service=services["previews"],
            manual_execution_service=services["execution"],
            manual_recovery_service=recovery,
        )
        return recovery, api

    def _assert_no_link_authority_or_mutation(self, environment, run, executions_before):
        """Fail-closed evidence: source intact, zero target files, no link, no new run."""
        self.assertTrue(environment["source_file"].exists())
        self.assertEqual(
            (),
            tuple(
                value for value in Path(environment["target_root"]).rglob("*") if value.is_file()
            ),
        )
        with SQLiteTaskRepository(environment["database"]) as repository:
            self.assertIsNone(
                repository.get_manual_recovery_link_by_source(
                    run.task_id, run.items[0].task_item_id
                )
            )
            self.assertEqual(
                executions_before,
                len(
                    repository.list_manual_executions_for_task_item(
                        run.task_id, run.items[0].task_item_id
                    )
                ),
            )

    def _authorize_continuation(self, api, run, checkpoint_version, token="operator-token"):
        return api_request(
            api,
            f"/api/v1/tasks/{run.task_id}/items/{run.items[0].task_item_id}"
            "/recovery/authorize-organize",
            method="POST",
            body={"expectedCheckpointVersion": checkpoint_version, "confirmation": True},
            token=token,
        )

    def _completed_continuation_item(self, environment, job_id, status):
        """Run the worker once and return the linked single-item analysis state."""
        with SQLiteTaskRepository(environment["database"]) as repository:
            continuation = repository.get_recovery_continuation_for_job(job_id)
            assert continuation is not None
            self.assertEqual(status, continuation.status)
            items = (
                repository.list_items(continuation.new_task_id) if continuation.new_task_id else ()
            )
            return continuation, (items[0] if items else None)

    def test_manual_recovery_authority_ttl_expiry_allows_fresh_continuation_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            services, run, _record, _preview = self._fail_manual_organize(environment, provider)
            with SQLiteTaskRepository(environment["database"]) as repository:
                submission = self._admit_and_continue(services, run, repository)
            self._close_manual_services(services)
            self._run_worker(environment, provider)
            continuation, _analysis = self._completed_continuation_item(
                environment, submission.job.job_id, RecoveryContinuationStatus.COMPLETED
            )
            self.assertIsNotNone(continuation.new_result_id)

            services = self._manual_services(environment, provider)
            recovery, api = self._recovery_api(environment, services)
            checkpoint = recovery._checkpoint_service.get(
                run.items[0].task_item_id, task_id=run.task_id
            )
            status, first = self._authorize_continuation(api, run, checkpoint.checkpoint_version)
            self.assertEqual(201, status)
            self.assertEqual("authorized", first["status"])
            first_authorization_id = first["authorization_id"]
            self.assertTrue(environment["source_file"].exists())
            self.assertEqual((), tuple(Path(environment["target_root"]).rglob("*")))

            # The unused one-shot authority expires normally while the operator is
            # away; expiry itself never touches Storage.
            with SQLiteTaskRepository(environment["database"]) as repository:
                self.assertEqual(
                    1,
                    repository.expire_manual_execution_authorizations(
                        datetime.now(UTC) + timedelta(seconds=3600)
                    ),
                )
            status, refused = api_request(
                api,
                f"/api/v1/manual-recovery-links/{first['link_id']}/execute",
                method="POST",
                body={"confirmation": True},
                token="operator-token",
            )
            self.assertEqual(409, status)
            self.assertEqual("authorization_inactive", refused["error"]["code"])
            self.assertTrue(environment["source_file"].exists())
            self.assertEqual((), tuple(Path(environment["target_root"]).rglob("*")))

            # A fresh explicit authorization supersedes the stale link: the original
            # item is not dead-ended by the expired authority.
            checkpoint = recovery._checkpoint_service.get(
                run.items[0].task_item_id, task_id=run.task_id
            )
            status, second = self._authorize_continuation(api, run, checkpoint.checkpoint_version)
            self.assertEqual(201, status)
            self.assertEqual("authorized", second["status"])
            self.assertEqual(first["link_id"], second["link_id"])
            self.assertNotEqual(first_authorization_id, second["authorization_id"])
            self.assertEqual(continuation.continuation_id, second["analysis_continuation_id"])
            self.assertTrue(environment["source_file"].exists())
            self.assertEqual((), tuple(Path(environment["target_root"]).rglob("*")))
            with SQLiteTaskRepository(environment["database"]) as repository:
                persisted = repository.get_manual_recovery_link(first["link_id"])
                assert persisted is not None
                self.assertEqual("authorized", persisted.status.value)
                self.assertEqual(second["authorization_id"], persisted.authorization_id)
                self.assertIsNone(persisted.execution_id)
                by_source = repository.get_manual_recovery_link_by_source(
                    run.task_id, run.items[0].task_item_id
                )
                assert by_source is not None
                self.assertEqual(second["authorization_id"], by_source.authorization_id)
                expired = repository.get_manual_execution_authorization(first_authorization_id)
                self.assertEqual("expired", expired.status.value)

            status, completed = api_request(
                api,
                f"/api/v1/manual-recovery-links/{second['link_id']}/execute",
                method="POST",
                body={"confirmation": True},
                token="operator-token",
            )
            self.assertEqual(200, status)
            self.assertEqual("consumed", completed["status"])
            self.assertFalse(environment["source_file"].exists())
            self.assertEqual(1, len(tuple(Path(environment["target_root"]).rglob("*.mkv"))))
            self._close_manual_services(services)

    def test_manual_recovery_authorize_refuses_fail_closed_before_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            provider = PhaseCandidatesProvider(
                (
                    MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),
                    MediaCandidate("tmdb", "43", MediaType.MOVIE, "Correct", year=2024),
                )
            )
            provider.replace(
                search=(MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            services, run, _record, _preview = self._fail_manual_organize(environment, provider)
            recovery, api = self._recovery_api(environment, services)
            checkpoint = recovery._checkpoint_service.get(
                run.items[0].task_item_id, task_id=run.task_id
            )
            with SQLiteTaskRepository(environment["database"]) as repository:
                RecoveryAdmissionService(
                    repository,
                    snapshot_validator=services["execution"]._validate_checkpoint_snapshot,
                    checkpoint_service=services["execution"]._checkpoint_service,
                ).admit(
                    run.task_id,
                    run.items[0].task_item_id,
                    action_id="retry",
                    expected_checkpoint_version=checkpoint.checkpoint_version,
                    actor="operator",
                )

            # (a) The admitted recovery request is still active: no authority, no link.
            checkpoint = recovery._checkpoint_service.get(
                run.items[0].task_item_id, task_id=run.task_id
            )
            status, refused = self._authorize_continuation(api, run, checkpoint.checkpoint_version)
            self.assertEqual(409, status)
            self.assertEqual("recovery_request_active", refused["error"]["code"])
            self._assert_no_link_authority_or_mutation(environment, run, 1)

            # (b) The single re-analysis ended waiting on a human decision, so no
            # completed linked analysis exists and no authority is issued.
            provider.replace(
                search=(
                    MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),
                    MediaCandidate("tmdb", "43", MediaType.MOVIE, "Correct", year=2024),
                )
            )
            with SQLiteTaskRepository(environment["database"]) as repository:
                submission = self._submit_continuation(services, run, repository)
            self._close_manual_services(services)
            # The waiting re-analysis is a failed continuation run: the worker exits 1.
            self._run_worker(environment, provider, expected_code=1)
            with SQLiteTaskRepository(environment["database"]) as repository:
                continuation = repository.get_recovery_continuation_for_job(submission.job.job_id)
                assert continuation is not None
                self.assertEqual(RecoveryContinuationStatus.FAILED, continuation.status)
                self.assertIn("human decision", continuation.error or "")
            services = self._manual_services(environment, provider)
            recovery, api = self._recovery_api(environment, services)
            checkpoint = recovery._checkpoint_service.get(
                run.items[0].task_item_id, task_id=run.task_id
            )
            status, refused = self._authorize_continuation(api, run, checkpoint.checkpoint_version)
            self.assertEqual(409, status)
            self.assertEqual("analysis_not_completed", refused["error"]["code"])
            self._assert_no_link_authority_or_mutation(environment, run, 1)
            self._close_manual_services(services)

    def test_manual_recovery_authorize_refuses_when_linked_item_still_has_blocker(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            services, run, _record, _preview = self._fail_manual_organize(environment, provider)
            with SQLiteTaskRepository(environment["database"]) as repository:
                submission = self._admit_and_continue(services, run, repository)
            self._close_manual_services(services)
            self._run_worker(environment, provider)
            _continuation, analysis = self._completed_continuation_item(
                environment, submission.job.job_id, RecoveryContinuationStatus.COMPLETED
            )
            assert analysis is not None

            services = self._manual_services(environment, provider)
            recovery, api = self._recovery_api(environment, services)
            with SQLiteTaskRepository(environment["database"]) as repository:
                linked = repository.get_item(analysis.item_id)
                assert linked is not None
                # The linked item re-enters analysis under the same evidence and the
                # real review service records that it requires a metadata decision
                # while the source item still points at the completed continuation.
                processing = replace(linked, status=TaskItemStatus.PROCESSING, stage="processing")
                repository.upsert_item(processing)
                review = MetadataReviewService(repository).create(
                    processing, _ambiguous_identification(), "A"
                )
                self.assertEqual(MetadataReviewStatus.PENDING, review.status)
            checkpoint = recovery._checkpoint_service.get(
                run.items[0].task_item_id, task_id=run.task_id
            )
            status, refused = self._authorize_continuation(api, run, checkpoint.checkpoint_version)
            self.assertEqual(409, status)
            self.assertEqual("review_pending", refused["error"]["code"])
            self.assertEqual("metadata", refused["error"]["details"]["blockerKind"])
            self._assert_no_link_authority_or_mutation(environment, run, 1)
            self._close_manual_services(services)

    def test_manual_recovery_authorize_refuses_replaced_source_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            services, run, _record, _preview = self._fail_manual_organize(environment, provider)
            with SQLiteTaskRepository(environment["database"]) as repository:
                submission = self._admit_and_continue(services, run, repository)
            self._close_manual_services(services)
            self._run_worker(environment, provider)
            self._completed_continuation_item(
                environment, submission.job.job_id, RecoveryContinuationStatus.COMPLETED
            )

            services = self._manual_services(environment, provider)
            recovery, api = self._recovery_api(environment, services)
            checkpoint = recovery._checkpoint_service.get(
                run.items[0].task_item_id, task_id=run.task_id
            )
            # Replace the source without re-scanning: the live file no longer matches
            # the FileIndex occurrence the reviewed plan was built on.
            environment["source_file"].write_bytes(b"replaced-after-analysis")
            status, refused = self._authorize_continuation(api, run, checkpoint.checkpoint_version)
            self.assertEqual(409, status)
            self.assertEqual("source_stale", refused["error"]["code"])
            self._assert_no_link_authority_or_mutation(environment, run, 1)
            self.assertEqual(b"replaced-after-analysis", environment["source_file"].read_bytes())
            self._close_manual_services(services)

    def test_worker_continuation_preflight_rejects_stale_occurrence_before_pipeline(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            services, run, _record, _preview = self._fail_manual_organize(environment, provider)
            checkpoint = services["execution"]._checkpoint_service.get(
                run.items[0].task_item_id, task_id=run.task_id
            )
            with SQLiteTaskRepository(environment["database"]) as repository:
                RecoveryAdmissionService(
                    repository,
                    snapshot_validator=services["execution"]._validate_checkpoint_snapshot,
                    checkpoint_service=services["execution"]._checkpoint_service,
                ).admit(
                    run.task_id,
                    run.items[0].task_item_id,
                    action_id="retry",
                    expected_checkpoint_version=checkpoint.checkpoint_version,
                    actor="operator",
                )
            # Replace the source and rescan so the FileIndex reconciles a new
            # current occurrence for the same path.
            environment["source_file"].write_bytes(b"replaced-before-worker")
            source_root = Path(environment["root"]) / "Incoming"
            with SQLiteFileIndexRepository(environment["database"]) as file_index:
                StorageScanner(
                    {"source-storage": LocalStorage("source-storage", source_root)},
                    file_index,
                ).scan(ResourceLibrary("source", "Source", "source-storage", "Media"))
            with SQLiteTaskRepository(environment["database"]) as repository:
                submission = self._submit_continuation(services, run, repository)
            self._close_manual_services(services)
            provider_factory = Mock(side_effect=AssertionError("worker reached Provider"))
            storage_factory = Mock(side_effect=AssertionError("worker reached Storage"))
            with (
                patch(
                    "mediaflow.final_cli.metadata_provider_registry_from_environment",
                    provider_factory,
                ),
                patch.object(RuntimeConfiguration, "create_storages", storage_factory),
            ):
                code = final_main(
                    ["--config", str(environment["config"]), "worker", "run-next"],
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )
            self.assertEqual(1, code)
            self.assertEqual(0, provider_factory.call_count)
            self.assertEqual(0, storage_factory.call_count)
            with SQLiteTaskRepository(environment["database"]) as repository:
                continuation = repository.get_recovery_continuation_for_job(submission.job.job_id)
                assert continuation is not None
                self.assertEqual(RecoveryContinuationStatus.FAILED, continuation.status)
                self.assertIsNone(continuation.new_task_id)
                self.assertIn("eligibility", continuation.error or "")
            self.assertEqual(b"replaced-before-worker", environment["source_file"].read_bytes())
            self.assertEqual((), tuple(Path(environment["target_root"]).rglob("*")))
            self._assert_no_link_authority_or_mutation(environment, run, 1)

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

    def test_recovery_continue_route_audit_is_templated_without_id_leakage(self) -> None:
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

            status, accepted = api_request(
                api,
                f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}/recovery/continue",
                method="POST",
                body={"expectedCheckpointVersion": checkpoint["checkpoint_version"]},
            )
            self.assertEqual(status, 202)

            with SQLiteTaskRepository(environment["database"]) as repository:
                audit_routes = [item.route for item in repository.list_security_audit()]
                self.assertIn(
                    "/api/v1/tasks/{task_id}/items/{item_id}/recovery/continue",
                    audit_routes,
                )
                self.assertNotIn(source_task.task_id, json.dumps(audit_routes))
                self.assertNotIn(source_item.item_id, json.dumps(audit_routes))

    def test_manual_organize_failure_analysis_continuation_and_exact_execution_link(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            records = self._scan_manual_source(environment)
            record = records[0]

            services = self._manual_services(
                environment,
                provider,
                executor=SelectiveManualExecutor("Correct.2024.mkv"),
            )
            with SQLiteTaskRepository(environment["database"]) as repository:
                preview = services["previews"].create_current(
                    scope_kind="file",
                    actor="operator",
                    file_id=record.file_id,
                    resource_library_id=record.resource_library_id,
                    occurrence_id=record.occurrence_id,
                    fingerprint=record.fingerprint,
                )
                item = preview.items[0]
                authority = services["execution"].authorize(
                    preview.preview_id,
                    [item.item_id],
                    expected_intent_version=preview.intent_version,
                    expected_item_versions={item.item_id: item.item_version},
                    snapshot_id=preview.configuration_snapshot_id,
                    snapshot_digest=preview.configuration_snapshot_digest,
                    actor="operator",
                    confirmation=True,
                )
                run = services["execution"].execute(
                    authority.authorization_id, actor="operator", confirmation=True
                )
                self.assertEqual("failed", run.items[0].status.value)
                self.assertTrue(environment["source_file"].exists())

                # Admit and continue one exact failed manual item as DryRun.
                checkpoint = services["execution"]._checkpoint_service.get(
                    run.items[0].task_item_id, task_id=run.task_id
                )
                admitted = RecoveryAdmissionService(
                    repository,
                    snapshot_validator=services["execution"]._validate_checkpoint_snapshot,
                    checkpoint_service=services["execution"]._checkpoint_service,
                ).admit(
                    run.task_id,
                    run.items[0].task_item_id,
                    action_id="retry",
                    expected_checkpoint_version=checkpoint.checkpoint_version,
                    actor="operator",
                )
                refreshed = services["execution"]._checkpoint_service.get(
                    run.items[0].task_item_id, task_id=run.task_id
                )
                submission = RecoveryContinuationService(
                    repository,
                    snapshot_validator=services["execution"]._validate_checkpoint_snapshot,
                    checkpoint_service=services["execution"]._checkpoint_service,
                ).submit(
                    run.task_id,
                    run.items[0].task_item_id,
                    expected_checkpoint_version=refreshed.checkpoint_version,
                    actor="operator",
                    maximum_active_jobs=10,
                )
                self.assertIsNotNone(admitted.request_id)
                self.assertFalse(submission.job.execute_authorized)

            services["task_repository"].close()
            services["file_index"].close()
            services["configuration_repository"].close()
            self._run_worker(environment, provider)

            with SQLiteTaskRepository(environment["database"]) as repository:
                continuation = repository.get_recovery_continuation_for_job(submission.job.job_id)
                assert continuation is not None
                self.assertEqual(RecoveryContinuationStatus.COMPLETED, continuation.status)
                self.assertIsNotNone(continuation.new_task_id)
                source_before = repository.get_item(run.items[0].task_item_id)
                self.assertIsNotNone(source_before)
                self.assertEqual(TaskItemStatus.PENDING.value, source_before.status.value)

            # The completed DryRun unlocks one exact continued execution authority.
            continued_services = self._manual_services(environment, provider)
            self.addCleanup(
                lambda: [
                    value.close()
                    for value in (
                        continued_services["task_repository"],
                        continued_services["file_index"],
                        continued_services["configuration_repository"],
                    )
                ]
            )
            recovery_service = ManualRecoveryContinuationService(
                continued_services["task_repository"],
                intent_service=continued_services["intents"],
                preview_service=continued_services["previews"],
                execution_service=continued_services["execution"],
                checkpoint_service=continued_services["execution"]._checkpoint_service,
            )
            checkpoint_after = recovery_service._checkpoint_service.get(
                run.items[0].task_item_id, task_id=run.task_id
            )
            operator = ResolvedApiPrincipal(
                "operator",
                "operator-token",
                frozenset(ApiPermission),
            )
            viewer = ResolvedApiPrincipal(
                "viewer",
                "viewer-token",
                frozenset({ApiPermission.READ}),
            )
            api = MediaFlowApi(
                continued_services["task_repository"],
                None,
                principals=(operator, viewer),
                file_catalog=continued_services["catalog"],
                configuration_service=continued_services["configuration_service"],
                configuration_snapshot_id=environment["snapshot"][0],
                configuration_snapshot_digest=environment["snapshot"][1],
                manual_intent_service=continued_services["intents"],
                manual_preview_service=continued_services["previews"],
                manual_execution_service=continued_services["execution"],
                manual_recovery_service=recovery_service,
            )
            authorize_path = (
                f"/api/v1/tasks/{run.task_id}/items/"
                f"{run.items[0].task_item_id}/recovery/authorize-organize"
            )
            status, denied = api_request(
                api,
                authorize_path,
                method="POST",
                body={
                    "expectedCheckpointVersion": checkpoint_after.checkpoint_version,
                    "confirmation": True,
                },
                token="viewer-token",
            )
            self.assertEqual(403, status)
            self.assertEqual("forbidden", denied["error"]["code"])
            status, authorized = api_request(
                api,
                authorize_path,
                method="POST",
                body={
                    "expectedCheckpointVersion": checkpoint_after.checkpoint_version,
                    "confirmation": True,
                },
                token="operator-token",
            )
            self.assertEqual(201, status)
            link = authorized
            self.assertIn("link_id", link)
            self.assertEqual(link["source_task_id"], run.task_id)
            self.assertEqual(link["source_item_id"], run.items[0].task_item_id)
            self.assertEqual(link["analysis_task_id"], continuation.new_task_id)

            self.assertTrue(environment["source_file"].exists())
            status, item_before_execution = api_request(
                api,
                f"/api/v1/tasks/{run.task_id}/items/{run.items[0].task_item_id}",
                token="operator-token",
            )
            self.assertEqual(200, status)
            self.assertEqual("authorized", item_before_execution["manualRecoveryLink"]["status"])
            execute_path = f"/api/v1/manual-recovery-links/{link['link_id']}/execute"
            status, completed = api_request(
                api,
                execute_path,
                method="POST",
                body={"confirmation": True},
                token="operator-token",
            )
            self.assertEqual(200, status)
            self.assertEqual("consumed", completed["status"])
            self.assertIsNotNone(completed["execution_id"])
            self.assertFalse(environment["source_file"].exists())
            target_files = tuple(Path(environment["target_root"]).rglob("*.mkv"))
            self.assertEqual(1, len(target_files))
            status, reloaded = api_request(
                api,
                f"/api/v1/tasks/{run.task_id}/items/{run.items[0].task_item_id}",
                token="operator-token",
            )
            self.assertEqual(200, status)
            self.assertEqual(
                "consumed",
                reloaded["manualRecoveryLink"]["status"],
            )
            self.assertEqual(
                completed["execution_id"],
                reloaded["manualRecoveryLink"]["execution_id"],
            )
            status, repeated = api_request(
                api,
                execute_path,
                method="POST",
                body={"confirmation": True},
                token="operator-token",
            )
            self.assertEqual(409, status)
            self.assertEqual("authorization_not_active", repeated["error"]["code"])
            audit_routes = [
                value.route for value in continued_services["task_repository"].list_security_audit()
            ]
            self.assertIn(
                "/api/v1/tasks/{task_id}/items/{item_id}/recovery/authorize-organize",
                audit_routes,
            )
            self.assertIn("/api/v1/manual-recovery-links/{id}/execute", audit_routes)
            self.assertNotIn(run.task_id, json.dumps(audit_routes))
            self.assertNotIn(run.items[0].task_item_id, json.dumps(audit_routes))

            persisted_link = continued_services["task_repository"].get_manual_recovery_link(
                link["link_id"]
            )
            self.assertIsNotNone(persisted_link)
            self.assertEqual("consumed", persisted_link.status.value)
            self.assertEqual(completed["execution_id"], persisted_link.execution_id)
            with SQLiteTaskRepository(environment["database"]) as repository:
                authorization = repository.get_manual_execution_authorization(
                    link["authorization_id"]
                )
                self.assertEqual("consumed", authorization.status.value)
                self.assertEqual(completed["execution_id"], authorization.execution_id)

    def test_manual_recovery_re_analysis_consumes_metadata_decision_saved_on_linked_item(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            provider = PhaseCandidatesProvider(
                (
                    MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),
                    MediaCandidate("tmdb", "43", MediaType.MOVIE, "Correct", year=2024),
                )
            )
            # The manual journey resolves one candidate; the later search swap makes
            # the production re-analysis ambiguous instead.
            provider.replace(
                search=(MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            services, run, _record, _preview = self._fail_manual_organize(environment, provider)
            # The re-analysis now sees two equal candidates: ambiguous metadata.
            provider.replace(
                search=(
                    MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),
                    MediaCandidate("tmdb", "43", MediaType.MOVIE, "Correct", year=2024),
                )
            )
            with SQLiteTaskRepository(environment["database"]) as repository:
                submission = self._admit_and_continue(services, run, repository)
            self._close_manual_services(services)
            self._run_worker(environment, provider, expected_code=1)
            _continuation, analysis = self._completed_continuation_item(
                environment, submission.job.job_id, RecoveryContinuationStatus.FAILED
            )
            assert analysis is not None
            with SQLiteTaskRepository(environment["database"]) as repository:
                linked = repository.get_item(analysis.item_id)
                assert linked is not None
                self.assertEqual(TaskItemStatus.WAITING_METADATA, linked.status)
                review = repository.get_metadata_review_for_item(linked.item_id)
                assert review is not None
                self.assertEqual(MetadataReviewStatus.PENDING, review.status)

            # Persistence-only decision saved on the linked analysis item.
            with SQLiteTaskRepository(environment["database"]) as repository:
                MetadataReviewService(repository).resolve(review.review_id, 1, actor="operator")
                resolved = repository.get_metadata_review_for_item(linked.item_id)
                assert resolved is not None
                self.assertEqual(MetadataReviewStatus.RESOLVED, resolved.status)
                self.assertEqual("42", resolved.selected_provider_id)

            services = self._manual_services(environment, provider)
            with SQLiteTaskRepository(environment["database"]) as repository:
                resubmission = self._admit_and_continue(services, run, repository)
            self._close_manual_services(services)
            self._run_worker(environment, provider)
            _retried, retried_analysis = self._completed_continuation_item(
                environment, resubmission.job.job_id, RecoveryContinuationStatus.COMPLETED
            )
            assert retried_analysis is not None
            with SQLiteTaskRepository(environment["database"]) as repository:
                retried_item = repository.get_item(retried_analysis.item_id)
                assert retried_item is not None
                self.assertEqual(TaskItemStatus.DRY_RUN, retried_item.status)
                # The resolved review is consumed, not re-created, by the fresh
                # production re-analysis of the original item.
                self.assertIsNone(repository.get_metadata_review_for_item(retried_analysis.item_id))
                results = repository.list_results(retried_analysis.task_id)
                self.assertEqual("42", results[-1].provider_id)
            self.assertTrue(environment["source_file"].exists())
            self.assertEqual((), tuple(Path(environment["target_root"]).rglob("*")))

    def test_manual_recovery_re_analysis_consumes_recognition_decision_saved_on_linked_item(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory, source_subdir="X")
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            services, run, _record, _preview = self._fail_manual_organize(
                environment, provider, source_subdir="X"
            )
            with SQLiteTaskRepository(environment["database"]) as repository:
                submission = self._admit_and_continue(services, run, repository)
            self._close_manual_services(services)
            self._run_worker(environment, provider, expected_code=1)
            _continuation, analysis = self._completed_continuation_item(
                environment, submission.job.job_id, RecoveryContinuationStatus.FAILED
            )
            assert analysis is not None
            with SQLiteTaskRepository(environment["database"]) as repository:
                linked = repository.get_item(analysis.item_id)
                assert linked is not None
                self.assertEqual(TaskItemStatus.WAITING_RECOGNITION, linked.status)
                review = repository.get_recognition_review_for_item(linked.item_id)
                assert review is not None
                self.assertEqual(RecognitionReviewStatus.PENDING, review.status)

            with SQLiteTaskRepository(environment["database"]) as repository:
                RecognitionReviewService(
                    repository,
                    (
                        RecognitionType("A", "A"),
                        RecognitionType("B", "B"),
                        RecognitionType("C", "C"),
                    ),
                ).resolve(review.review_id, "A", actor="operator")
                resolved = repository.get_recognition_review_for_item(linked.item_id)
                assert resolved is not None
                self.assertEqual(RecognitionReviewStatus.RESOLVED, resolved.status)
                self.assertEqual("A", resolved.selected_recognition_type)

            services = self._manual_services(environment, provider)
            with SQLiteTaskRepository(environment["database"]) as repository:
                resubmission = self._admit_and_continue(services, run, repository)
            self._close_manual_services(services)
            self._run_worker(environment, provider)
            _retried, retried_analysis = self._completed_continuation_item(
                environment, resubmission.job.job_id, RecoveryContinuationStatus.COMPLETED
            )
            assert retried_analysis is not None
            with SQLiteTaskRepository(environment["database"]) as repository:
                retried_item = repository.get_item(retried_analysis.item_id)
                assert retried_item is not None
                self.assertEqual(TaskItemStatus.DRY_RUN, retried_item.status)
                self.assertIsNone(
                    repository.get_recognition_review_for_item(retried_analysis.item_id)
                )
                results = repository.list_results(retried_analysis.task_id)
                self.assertEqual("A", results[-1].recognition_type)
            self.assertTrue(environment["source_file"].exists())
            self.assertEqual((), tuple(Path(environment["target_root"]).rglob("*")))

    def test_manual_recovery_re_analysis_consumes_metadata_correction_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            provider = PhaseCandidatesProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            services, run, _record, _preview = self._fail_manual_organize(environment, provider)
            # The re-analysis search now finds nothing, so the production path asks
            # for a metadata correction instead of an identity.
            provider.replace(search=())
            with SQLiteTaskRepository(environment["database"]) as repository:
                submission = self._admit_and_continue(services, run, repository)
            self._close_manual_services(services)
            self._run_worker(environment, provider, expected_code=1)
            _continuation, analysis = self._completed_continuation_item(
                environment, submission.job.job_id, RecoveryContinuationStatus.FAILED
            )
            assert analysis is not None
            with SQLiteTaskRepository(environment["database"]) as repository:
                linked = repository.get_item(analysis.item_id)
                assert linked is not None
                self.assertEqual(TaskItemStatus.WAITING_METADATA_CORRECTION, linked.status)
                review = repository.get_metadata_correction_for_item(linked.item_id)
                assert review is not None

            with SQLiteTaskRepository(environment["database"]) as repository:
                MetadataCorrectionService(
                    repository, development_strategy_configuration().metadata_policies
                ).resolve(
                    review.review_id,
                    query=None,
                    year=None,
                    media_type="movie",
                    provider_id="42",
                    actor="operator",
                )
                resolved = repository.get_metadata_correction_for_item(linked.item_id)
                assert resolved is not None

            services = self._manual_services(environment, provider)
            with SQLiteTaskRepository(environment["database"]) as repository:
                resubmission = self._admit_and_continue(services, run, repository)
            self._close_manual_services(services)
            self._run_worker(environment, provider)
            _retried, retried_analysis = self._completed_continuation_item(
                environment, resubmission.job.job_id, RecoveryContinuationStatus.COMPLETED
            )
            assert retried_analysis is not None
            with SQLiteTaskRepository(environment["database"]) as repository:
                retried_item = repository.get_item(retried_analysis.item_id)
                assert retried_item is not None
                self.assertEqual(TaskItemStatus.DRY_RUN, retried_item.status)
                self.assertIsNone(
                    repository.get_metadata_correction_for_item(retried_analysis.item_id)
                )
                results = repository.list_results(retried_analysis.task_id)
                self.assertEqual("42", results[-1].provider_id)
            self.assertTrue(environment["source_file"].exists())
            self.assertEqual((), tuple(Path(environment["target_root"]).rglob("*")))

    def test_manual_recovery_re_analysis_consumes_classification_decision(self):
        def drop_movie_fallback(document):
            for policy in document["classificationPolicies"]:
                if policy["id"] == "A":
                    policy["rules"] = [
                        rule for rule in policy["rules"] if rule["id"] != "other-movie"
                    ]

        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory, document_patch=drop_movie_fallback)
            provider = PhaseCandidatesProvider(
                (
                    MediaCandidate(
                        "tmdb",
                        "42",
                        MediaType.MOVIE,
                        "Correct",
                        year=2024,
                        genres=("Action",),
                    ),
                )
            )
            services, run, _record, preview = self._fail_manual_organize(environment, provider)
            # The re-analysis identity carries no genre, so no classification rule
            # matches under the pinned snapshot.
            provider.replace(
                candidates=(MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),),
                search=(MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),),
            )
            with SQLiteTaskRepository(environment["database"]) as repository:
                submission = self._admit_and_continue(services, run, repository)
            self._close_manual_services(services)
            self._run_worker(environment, provider, expected_code=1)
            _continuation, analysis = self._completed_continuation_item(
                environment, submission.job.job_id, RecoveryContinuationStatus.FAILED
            )
            assert analysis is not None
            with SQLiteTaskRepository(environment["database"]) as repository:
                linked = repository.get_item(analysis.item_id)
                assert linked is not None
                self.assertEqual(TaskItemStatus.WAITING_CLASSIFICATION, linked.status)
                review = repository.get_classification_review_for_item(linked.item_id)
                assert review is not None
                choices = repository.list_classification_review_choices(review.review_id)
                foreign = next(value for value in choices if value.rule_id == "foreign-movie")

            with SQLiteTaskRepository(environment["database"]) as repository:
                ClassificationReviewService(repository).resolve(
                    review.review_id, foreign.rank, actor="operator"
                )
                resolved = repository.get_classification_review_for_item(linked.item_id)
                assert resolved is not None
                self.assertEqual(ClassificationReviewStatus.RESOLVED, resolved.status)

            services = self._manual_services(environment, provider)
            with SQLiteTaskRepository(environment["database"]) as repository:
                resubmission = self._admit_and_continue(services, run, repository)
            self._close_manual_services(services)
            self._run_worker(environment, provider)
            _retried, retried_analysis = self._completed_continuation_item(
                environment, resubmission.job.job_id, RecoveryContinuationStatus.COMPLETED
            )
            assert retried_analysis is not None
            with SQLiteTaskRepository(environment["database"]) as repository:
                retried_item = repository.get_item(retried_analysis.item_id)
                assert retried_item is not None
                self.assertEqual(TaskItemStatus.DRY_RUN, retried_item.status)
                self.assertIsNone(
                    repository.get_classification_review_for_item(retried_analysis.item_id)
                )
                results = repository.list_results(retried_analysis.task_id)
                self.assertIsNotNone(results[-1].destination_path)
                self.assertIn("外语电影", results[-1].destination_path)
            self.assertTrue(environment["source_file"].exists())
            self.assertEqual((), tuple(Path(environment["target_root"]).rglob("*")))

    def test_manual_recovery_re_analysis_consumes_conflict_decision_saved_on_linked_item(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            services, run, _record, preview = self._fail_manual_organize(environment, provider)
            item_plan = preview.items[0].plan
            assert item_plan is not None
            destination = item_plan["destination"]["path"]
            # A live destination collision exists before the first re-analysis.
            collision = Path(environment["target_root"], destination)
            collision.parent.mkdir(parents=True, exist_ok=True)
            collision.write_bytes(b"existing-destination")
            with SQLiteTaskRepository(environment["database"]) as repository:
                submission = self._admit_and_continue(services, run, repository)
            self._close_manual_services(services)
            self._run_worker(environment, provider, expected_code=1)
            _continuation, analysis = self._completed_continuation_item(
                environment, submission.job.job_id, RecoveryContinuationStatus.FAILED
            )
            assert analysis is not None
            with SQLiteTaskRepository(environment["database"]) as repository:
                linked = repository.get_item(analysis.item_id)
                assert linked is not None
                self.assertEqual(TaskItemStatus.WAITING_CONFIRM, linked.status)
                pending = tuple(
                    value
                    for value in repository.list_confirmations(status=ConfirmationStatus.PENDING)
                    if value.item_id == linked.item_id
                )
                self.assertEqual(1, len(pending))

            # Persistence-only conflict decision: rename, never overwrite.
            with SQLiteTaskRepository(environment["database"]) as repository:
                ConfirmationService(repository).resolve(
                    pending[0].confirmation_id, ConflictStrategy.RENAME, actor="operator"
                )

            services = self._manual_services(environment, provider)
            with SQLiteTaskRepository(environment["database"]) as repository:
                resubmission = self._admit_and_continue(services, run, repository)
            self._close_manual_services(services)
            self._run_worker(environment, provider)
            _retried, retried_analysis = self._completed_continuation_item(
                environment, resubmission.job.job_id, RecoveryContinuationStatus.COMPLETED
            )
            assert retried_analysis is not None
            with SQLiteTaskRepository(environment["database"]) as repository:
                retried_item = repository.get_item(retried_analysis.item_id)
                assert retried_item is not None
                self.assertEqual(TaskItemStatus.DRY_RUN, retried_item.status)
                results = repository.list_results(retried_analysis.task_id)
                self.assertIsNotNone(results[-1].destination_path)
                self.assertNotEqual(destination, results[-1].destination_path)
                self.assertEqual(
                    (),
                    tuple(
                        value
                        for value in repository.list_confirmations(
                            status=ConfirmationStatus.PENDING
                        )
                        if value.item_id == retried_analysis.item_id
                    ),
                )
            # The colliding destination was never overwritten, no renamed target file
            # was created by the DryRun, and the source is intact.
            target_files = [
                value for value in Path(environment["target_root"]).rglob("*") if value.is_file()
            ]
            self.assertEqual([collision], target_files)
            self.assertEqual(b"existing-destination", collision.read_bytes())
            self.assertTrue(environment["source_file"].exists())


def _ambiguous_identification() -> MetadataIdentificationResult:
    candidates = (
        MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),
        MediaCandidate("tmdb", "43", MediaType.MOVIE, "Correct", year=2024),
    )
    scores = tuple(
        CandidateScore(candidate, 80.0 - rank, (ScoreComponent("title", 65.0, "matched"),))
        for rank, candidate in enumerate(candidates)
    )
    match = CandidateMatchResult(
        CandidateMatchStatus.AMBIGUOUS, candidates[0], scores[0].total_score, scores
    )
    return MetadataIdentificationResult(
        MetadataIdentificationStatus.AMBIGUOUS,
        RecognitionType("A", "A"),
        match=match,
        query="Correct",
    )


def _coordinator(repository):
    return PersistentTaskCoordinator(repository, repository)


if __name__ == "__main__":
    unittest.main()
