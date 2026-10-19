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
from mediaflow.application.evidence_capture import _execution_identity_document
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_execution import ManualOrganizeExecutionService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.manual_recovery_continuation import (
    ManualRecoveryContinuationError,
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
from mediaflow.domain.manual_organize import ManualChoice
from mediaflow.domain.media_evidence import PipelineEvidence
from mediaflow.domain.metadata import (
    CandidateMatchResult,
    CandidateMatchStatus,
    CandidateScore,
    EpisodeIdentity,
    MediaCandidate,
    MediaIdentity,
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
from mediaflow.domain.recognition import RecognitionResult, RecognitionStatus, RecognitionType
from mediaflow.domain.recognition_review import RecognitionReviewStatus
from mediaflow.domain.recovery_continuation import RecoveryContinuationStatus
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.source_evidence import occurrence_id_for, source_fingerprint
from mediaflow.domain.task_persistence import (
    ConfirmationStatus,
    PersistentResultRecord,
    TaskItemStatus,
)
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.source_fixtures import source_identity_from_storage
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
        self.calls += 1
        return self.search_candidates


class EpisodeCountingProvider(DetailCountingProvider):
    """Fake TV provider with a real episode title and observable call count."""

    def __init__(self, candidate):
        super().__init__((candidate,))
        self.season_requests = []

    def get_tv(self, provider_id, policy=None, **kwargs):
        self.calls += 1
        candidate = self._by_id(provider_id)
        return MediaIdentity(
            "tmdb",
            provider_id,
            MediaType.TV,
            candidate.title,
            candidate.original_title,
            candidate.year,
            genres=candidate.genres,
            countries=candidate.countries,
            languages=candidate.languages,
            keywords=candidate.keywords,
            alternative_titles=("Corrected Alternate",),
            translated_titles=("正确",),
            release_date="2024-01-02",
            canonical_release_date="2024-01-02",
            regional_release_date="2024-01-03",
            overview="A complete normalized provider identity.",
            external_ids=(("imdb", "tt1234567"),),
            poster_path="/posters/tv-42.jpg",
            backdrop_path="/backdrops/tv-42.jpg",
            confidence=98.5,
            matched_by="candidate_matcher",
            recognition_type_id="B",
        )

    def get_season(self, provider_id, season, policy=None, **kwargs):
        self.calls += 1
        self.season_requests.append((provider_id, season))
        return MediaIdentity(
            "tmdb",
            provider_id,
            MediaType.TV,
            "Season 1",
            season=season,
            episode_metadata=(EpisodeIdentity(1, "Episode 1", "2024-01-10", "Episode overview"),),
        )


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
        repository = SQLiteTaskRepository(environment["database"])
        configuration = SQLiteConfigurationRepository(environment["database"])
        api = MediaFlowApi(
            repository,
            None,
            principals=(ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),),
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
                for value in (api._repository, api._configuration_service.repository)
                if value is not None
            ]
        )
        return api

    def _manual_services(self, environment, provider, *, executor=None):
        database = environment["database"]
        task_repository = SQLiteTaskRepository(database)
        configuration_repository = SQLiteConfigurationRepository(database)
        configuration_service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=str(database),
        )
        intents = ManualOrganizeIntentService(
            task_repository,
            configuration_service=configuration_service,
            storage_factory=lambda runtime, storage_ids: runtime.create_storages(
                storage_ids=storage_ids
            ),
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
            "configuration_repository": configuration_repository,
            "configuration_service": configuration_service,
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
        storage = LocalStorage("source-storage", source_root)
        StorageScanner({"source-storage": storage}).scan(
            ResourceLibrary("source", "Source", "source-storage", "Media")
        )
        return tuple(
            source_identity_from_storage(
                storage,
                f"Media/{source_subdir}/{name}".strip("/"),
                storage_id="source-storage",
                resource_library_id="source",
            )
            for name in names
        )

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

    def _fail_manual_organize(
        self,
        environment,
        provider,
        *,
        executor=None,
        source_subdir="C",
        choice: ManualChoice | None = None,
    ):
        """Run a real manual organize that fails at the executor for the one source."""
        source_name = Path(environment["source_file"]).name
        records = self._scan_manual_source(
            environment, names=(source_name,), source_subdir=source_subdir
        )
        record = records[0]
        services = self._manual_services(
            environment,
            provider,
            executor=executor or SelectiveManualExecutor(source_name),
        )
        with SQLiteTaskRepository(environment["database"]):
            if choice is None:
                preview = services["previews"].create_current_from_storage(
                    scope_kind="file",
                    actor="operator",
                    resource_library_id=record.resource_library_id,
                    relative_path=record.path.removeprefix("Media/"),
                )
            else:
                intent = services["previews"].admit_storage_paths(
                    resource_library_id=record.resource_library_id,
                    relative_paths=(record.path.removeprefix("Media/"),),
                    actor="operator",
                )
                changed = services["intents"].update_choice(
                    intent.intent_id,
                    intent.items[0].item_id,
                    choice,
                    expected_version=intent.version,
                    expected_item_version=intent.items[0].version,
                    actor="operator",
                )
                preview = services["previews"].create(
                    intent.intent_id,
                    expected_version=changed.version,
                    expected_item_versions={item.item_id: item.version for item in changed.items},
                    snapshot_id=changed.snapshot_id,
                    snapshot_digest=changed.snapshot_digest,
                    actor="operator",
                    source_scope="file",
                    source_scope_id=record.path.removeprefix("Media/"),
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
        for key in ("task_repository", "configuration_repository"):
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

    def _authorize_and_execute_continued(
        self,
        environment,
        services,
        run,
        *,
        expected_destination=None,
        collision=None,
    ):
        """Drive the full continuation journey after a completed linked re-analysis.

        Asserts that ``authorize-organize`` succeeds (the round-4 blocker), that no
        Storage mutation happens before the explicit one-shot execute, that execute
        moves the source to the reviewed destination and consumes the authority, and
        that a repeated execute is refused.
        """

        recovery, api = self._recovery_api(environment, services)
        checkpoint = recovery._checkpoint_service.get(
            run.items[0].task_item_id, task_id=run.task_id
        )
        status, link = self._authorize_continuation(api, run, checkpoint.checkpoint_version)
        self.assertEqual(201, status, f"{link}")
        self.assertEqual("authorized", link["status"])
        # The reviewed decision was persistence-only: nothing moved or was created
        # before the operator's explicit execute.
        self.assertTrue(environment["source_file"].exists())
        if collision is None:
            self.assertEqual((), tuple(Path(environment["target_root"]).rglob("*")))
        else:
            self.assertTrue(collision.exists())
        execute_path = f"/api/v1/manual-recovery-links/{link['link_id']}/execute"
        status, completed = api_request(
            api,
            execute_path,
            method="POST",
            body={"confirmation": True},
            token="operator-token",
        )
        self.assertEqual(200, status, f"{completed}")
        self.assertEqual("consumed", completed["status"])
        self.assertFalse(environment["source_file"].exists())
        if expected_destination is not None:
            moved = next(
                (
                    value
                    for value in Path(environment["target_root"]).rglob("*.mkv")
                    if value.relative_to(environment["target_root"]).as_posix()
                    == expected_destination
                ),
                None,
            )
            self.assertIsNotNone(moved, f"{expected_destination} was not produced")
        if collision is not None:
            self.assertEqual(b"existing-destination", collision.read_bytes())
        status, repeated = api_request(
            api,
            execute_path,
            method="POST",
            body={"confirmation": True},
            token="operator-token",
        )
        self.assertEqual(409, status)
        self.assertEqual("authorization_not_active", repeated["error"]["code"])

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

            # (b) The single re-analysis ended waiting on a human decision. The
            # refusal names that durable linked blocker so the operator can
            # resolve it instead of receiving a generic re-analysis loop.
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
            self.assertEqual("review_pending", refused["error"]["code"])
            self.assertEqual("metadata", refused["error"]["details"]["blockerKind"])
            self.assertEqual(
                "resolve the blocker on the linked TaskItem, continue that item's safe analysis, "
                "then return here",
                refused["error"]["details"]["nextAction"],
            )
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
            # Replace the source so the reviewed occurrence no longer matches
            # the live content at the same path.  The real Worker and local
            # Storage must make their own source-identity decision; no Provider
            # or Storage factory is made to fail to manufacture the refusal.
            environment["source_file"].write_bytes(b"replaced-before-worker")
            with SQLiteTaskRepository(environment["database"]) as repository:
                submission = self._submit_continuation(services, run, repository)
            self._close_manual_services(services)
            provider.movie_queries.clear()
            self._run_worker(environment, provider, expected_code=1)
            # A replaced source is refused at the live re-observation boundary:
            # no Provider request and no new TaskItem/Result is produced.
            self.assertEqual([], provider.movie_queries)
            with SQLiteTaskRepository(environment["database"]) as repository:
                continuation = repository.get_recovery_continuation_for_job(submission.job.job_id)
                assert continuation is not None
                self.assertEqual(RecoveryContinuationStatus.FAILED, continuation.status)
                self.assertIsNone(continuation.new_task_id)
                self.assertIn("source", (continuation.error or "").lower())
                self.assertIn("re-select", continuation.recovery or "")
            self.assertEqual(b"replaced-before-worker", environment["source_file"].read_bytes())
            self.assertEqual((), tuple(Path(environment["target_root"]).rglob("*")))
            self._assert_no_link_authority_or_mutation(environment, run, 1)

    def test_worker_continuation_refuses_missing_source_before_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            services, run, _record, _preview = self._fail_manual_organize(environment, provider)
            with SQLiteTaskRepository(environment["database"]) as repository:
                submission = self._admit_and_continue(services, run, repository)
            self._close_manual_services(services)
            environment["source_file"].unlink()
            provider.movie_queries.clear()
            self._run_worker(environment, provider, expected_code=1)
            self.assertEqual([], provider.movie_queries)
            with SQLiteTaskRepository(environment["database"]) as repository:
                continuation = repository.get_recovery_continuation_for_job(submission.job.job_id)
                assert continuation is not None
                self.assertEqual(RecoveryContinuationStatus.FAILED, continuation.status)
                self.assertIsNone(continuation.new_task_id)
                self.assertIn("source", (continuation.error or "").lower())
                self.assertIn("re-select", continuation.recovery or "")
            self.assertEqual((), tuple(Path(environment["target_root"]).rglob("*")))

    def test_worker_continuation_accepts_unchanged_source_and_superseded_pin(self):
        """A legitimate unchanged source completes; a later Active does not rebind it."""

        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            services, run, _record, _preview = self._fail_manual_organize(environment, provider)
            with SQLiteTaskRepository(environment["database"]) as repository:
                submission = self._admit_and_continue(services, run, repository)
            self._close_manual_services(services)
            # Publish a successor Active revision while the Job stays pinned to
            # the original one: the old pin must remain legitimate.
            successor = self._publish_successor(environment)
            self.assertNotEqual(successor.revision_id, environment["snapshot"][0])
            provider.movie_queries.clear()
            self._run_worker(environment, provider)
            self.assertEqual([("Correct", 2024)], provider.movie_queries)
            self.assertEqual(b"unchanged-source", environment["source_file"].read_bytes())
            with SQLiteTaskRepository(environment["database"]) as repository:
                continuation = repository.get_recovery_continuation_for_job(submission.job.job_id)
                assert continuation is not None
                self.assertEqual(RecoveryContinuationStatus.COMPLETED, continuation.status)
                new_task = repository.get_task(continuation.new_task_id or "")
                assert new_task is not None
                self.assertEqual(environment["snapshot"][0], new_task.configuration_snapshot_id)
                items = repository.list_items(new_task.task_id)
                self.assertEqual(1, len(items))
                self.assertEqual(TaskItemStatus.DRY_RUN, items[0].status)
                live = source_fingerprint(
                    "source-storage",
                    "source",
                    LocalStorage("source-storage", Path(environment["root"]) / "Incoming").stat(
                        environment["storage_path"]
                    ),
                )
                self.assertEqual(items[0].source_fingerprint, live.value)
                self.assertEqual(
                    items[0].source_occurrence_id,
                    occurrence_id_for(
                        "source-storage", "source", environment["storage_path"], live.value
                    ),
                )

    def _publish_successor(self, environment):
        """Publish one successor Active revision over the same database."""

        with SQLiteConfigurationRepository(environment["database"]) as repository:
            managed = ManagedConfigurationService(
                repository, bootstrap_database_path=str(environment["database"])
            )
            document = json.loads(json.dumps(environment["document"]))
            document["historyPath"] = str(Path(environment["root"]) / "history-successor.jsonl")
            draft = managed.import_draft(document, actor="tester")
            validated = managed.validate(draft.revision_id, actor="tester")
            return managed.activate(
                validated.revision_id, expected_version=validated.version, actor="tester"
            )

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

    def test_native_recognition_resolution_continues_exact_item_without_storage_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            with SQLiteTaskRepository(environment["database"]) as repository:
                snapshot_id, snapshot_digest = environment["snapshot"]
                source_task = _coordinator(repository).create(
                    "organize",
                    execute_authorized=False,
                    scope_path="Media/C/Review.2024.mkv",
                    item_limit=10,
                    configuration_snapshot_id=snapshot_id,
                    configuration_snapshot_digest=snapshot_digest,
                    require_configuration_snapshot=True,
                )
                source_item = _coordinator(repository).begin_item(
                    source_task.task_id,
                    "source-storage",
                    "source",
                    "Media/C/Review.2024.mkv",
                    "Media/C/Review.2024.mkv",
                )
                review = RecognitionReviewService(
                    repository,
                    (
                        RecognitionType("A", "Movie"),
                        RecognitionType("B", "TV"),
                        RecognitionType("C", "Special"),
                    ),
                ).create(
                    source_item,
                    RecognitionResult(status=RecognitionStatus.UNRECOGNIZED),
                )
            api = self._api(environment)
            base = f"/api/v1/tasks/{source_task.task_id}/items/{source_item.item_id}"

            status, detail = api_request(api, f"{base}/recovery")
            self.assertEqual(200, status)
            self.assertEqual("none", detail["sideEffects"])
            self.assertEqual("recognition", detail["decision"]["kind"])
            self.assertEqual(review.review_id, detail["decision"]["review_id"])
            self.assertEqual(
                {"A", "B", "C"},
                {choice["recognition_type_id"] for choice in detail["decision"]["choices"]},
            )
            initial_version = detail["checkpoint"]["checkpoint_version"]

            status, saved = api_request(
                api,
                f"{base}/recovery/decision",
                method="POST",
                body={
                    "kind": "recognition",
                    "expectedCheckpointVersion": initial_version,
                    "recognitionTypeId": "C",
                },
            )
            self.assertEqual(200, status)
            self.assertIn("retry", saved["checkpoint"]["permitted_action_ids"])
            self.assertEqual("none", saved["checkpoint"]["effects"]["certainty"])

            # One visible Continue command composes the exact admission and the
            # queued DryRun; the saved choice itself created no execution grant.
            status, accepted = api_request(
                api,
                f"{base}/recovery/continue",
                method="POST",
                body={"expectedCheckpointVersion": saved["checkpoint"]["checkpoint_version"]},
            )
            if status != 202:
                _read_status, current = api_request(api, f"{base}/recovery")
                self.fail(
                    f"native recovery continuation was refused: {accepted}; current={current}"
                )
            self.assertEqual("dry_run", accepted["executionMode"])
            self.assertEqual(source_task.task_id, accepted["source_task_id"])
            self.assertEqual(source_item.item_id, accepted["source_item_id"])

            with SQLiteTaskRepository(environment["database"]) as repository:
                decision = repository.get_recognition_review(review.review_id)
                self.assertEqual("C", decision.selected_recognition_type)
                queued = repository.get_recovery_continuation_for_request(accepted["request_id"])
                self.assertIsNotNone(queued)
                job = repository.get_job(accepted["job_id"])
                self.assertIsNotNone(job)
                self.assertFalse(job.execute_authorized)
                self.assertEqual(b"unchanged-source", environment["source_file"].read_bytes())
                self.assertEqual((), tuple(Path(environment["target_root"]).rglob("*")))

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
                failed_overview = repository.operations_run(source_task.task_id)
                self.assertIsNotNone(failed_overview)
                assert failed_overview is not None
                self.assertTrue(failed_overview.attention)
                self.assertEqual(("failure",), failed_overview.problem_types)
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
                accepted_overview = repository.operations_run(source_task.task_id)
                self.assertIsNotNone(accepted_overview)
                assert accepted_overview is not None
                self.assertTrue(accepted_overview.attention)
                self.assertEqual((), accepted_overview.problem_types)
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
                completed_overview = repository.operations_run(source_task.task_id)
                self.assertIsNotNone(completed_overview)
                assert completed_overview is not None
                self.assertTrue(completed_overview.attention)
                self.assertEqual((), completed_overview.problem_types)

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
                preview = services["previews"].create_current_from_storage(
                    scope_kind="file",
                    actor="operator",
                    resource_library_id=record.resource_library_id,
                    relative_path=record.path.removeprefix("Media/"),
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
                source_overview = repository.operations_run(run.task_id)
                self.assertIsNotNone(source_overview)
                assert source_overview is not None
                self.assertTrue(source_overview.attention)
                self.assertEqual((), source_overview.problem_types)
                self.assertEqual(
                    0,
                    dict(source_overview.problem_file_counts).get("failure"),
                    "a completed analysis continuation remains a generic safe next step, "
                    "not a technical failure",
                )

            # The completed DryRun unlocks one exact continued execution authority.
            continued_services = self._manual_services(environment, provider)
            self.addCleanup(
                lambda: [
                    value.close()
                    for value in (
                        continued_services["task_repository"],
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
            authorized_overview = continued_services["task_repository"].operations_run(run.task_id)
            self.assertIsNotNone(authorized_overview)
            assert authorized_overview is not None
            self.assertTrue(authorized_overview.attention)
            self.assertEqual((), authorized_overview.problem_types)

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
            consumed_overview = continued_services["task_repository"].operations_run(run.task_id)
            self.assertIsNotNone(consumed_overview)
            assert consumed_overview is not None
            self.assertFalse(consumed_overview.attention)
            self.assertEqual((), consumed_overview.problem_types)
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
                failure_window = repository.operations_runs_window(view="failure")
                metadata_window = repository.operations_runs_window(view="metadata")
                self.assertNotIn(run.task_id, {row.task_id for row in failure_window.page})
                self.assertIn(analysis.task_id, {row.task_id for row in metadata_window.page})

            # Persistence-only decision saved on the linked analysis item.
            with SQLiteTaskRepository(environment["database"]) as repository:
                MetadataReviewService(repository).resolve(review.review_id, 1, actor="operator")
                resolved = repository.get_metadata_review_for_item(linked.item_id)
                assert resolved is not None
                self.assertEqual(MetadataReviewStatus.RESOLVED, resolved.status)
                self.assertEqual("42", resolved.selected_provider_id)
                # Immediately after saving the decision the child item waits
                # for the next admission. No new technical failure happened,
                # so the original source must NOT reappear under Failure while
                # its own generic safe-continuation attention stays.
                resolved_item = repository.get_item(linked.item_id)
                assert resolved_item is not None
                self.assertEqual(TaskItemStatus.PENDING, resolved_item.status)
                self.assertEqual("metadata_resolved", resolved_item.stage)
                saved_failure = repository.operations_runs_window(view="failure")
                saved_metadata = repository.operations_runs_window(view="metadata")
                self.assertNotIn(run.task_id, {row.task_id for row in saved_failure.page})
                self.assertNotIn(analysis.task_id, {row.task_id for row in saved_metadata.page})
                saved_attention = repository.operations_runs_window(view="attention")
                self.assertIn(run.task_id, {row.task_id for row in saved_attention.page})

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
            # The saved metadata identity decision must survive into the explicit
            # continuation authority: authorize-organize used to block on a fresh
            # ambiguous live search, so the resolved decision could never execute.
            services = self._manual_services(environment, provider)
            self.addCleanup(self._close_manual_services, services)
            self._authorize_and_execute_continued(
                environment,
                services,
                run,
                expected_destination=results[-1].destination_path,
            )
            with SQLiteTaskRepository(environment["database"]) as repository:
                attention_window = repository.operations_runs_window(view="attention")
                self.assertEqual(0, attention_window.total)

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
            # The resolved RecognitionType decision is honored by the Worker re-analysis
            # and the continuation authority must complete the original manual journey.
            services = self._manual_services(environment, provider)
            self.addCleanup(self._close_manual_services, services)
            self._authorize_and_execute_continued(
                environment,
                services,
                run,
                expected_destination=results[-1].destination_path,
            )

    def test_manual_recovery_refuses_incompatible_linked_recognition_decision(self):
        """A linked RecognitionType change cannot silently execute the old manual plan."""

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
                RecognitionReviewService(
                    repository,
                    (
                        RecognitionType("A", "A"),
                        RecognitionType("B", "B"),
                        RecognitionType("C", "C"),
                    ),
                ).resolve(review.review_id, "C", actor="operator")
                resolved = repository.get_recognition_review_for_item(linked.item_id)
                assert resolved is not None
                self.assertEqual(RecognitionReviewStatus.RESOLVED, resolved.status)
                self.assertEqual("C", resolved.selected_recognition_type)

            services = self._manual_services(environment, provider)
            self.addCleanup(self._close_manual_services, services)
            with SQLiteTaskRepository(environment["database"]) as repository:
                resubmission = self._admit_and_continue(services, run, repository)
            self._close_manual_services(services)
            self._run_worker(environment, provider)
            _retried, retried_analysis = self._completed_continuation_item(
                environment, resubmission.job.job_id, RecoveryContinuationStatus.COMPLETED
            )
            assert retried_analysis is not None
            with SQLiteTaskRepository(environment["database"]) as repository:
                results = repository.list_results(retried_analysis.task_id)
                self.assertEqual("C", results[-1].recognition_type)

            continued_services = self._manual_services(environment, provider)
            self.addCleanup(self._close_manual_services, continued_services)
            recovery, api = self._recovery_api(environment, continued_services)
            checkpoint = recovery._checkpoint_service.get(
                run.items[0].task_item_id, task_id=run.task_id
            )
            status, refused = self._authorize_continuation(api, run, checkpoint.checkpoint_version)
            self.assertEqual(409, status)
            self.assertEqual("recognition_plan_mismatch", refused["error"]["code"])
            self.assertEqual("C", refused["error"]["details"]["reviewedRecognitionType"])
            self.assertEqual("A", refused["error"]["details"]["manualRecognitionType"])
            self.assertTrue(environment["source_file"].exists())
            self.assertEqual(
                (),
                tuple(
                    value
                    for value in Path(environment["target_root"]).rglob("*")
                    if value.is_file()
                ),
            )
            self.assertIsNone(
                continued_services["task_repository"].get_manual_recovery_link_by_source(
                    run.task_id, run.items[0].task_item_id
                )
            )
            self.assertEqual(
                1,
                len(
                    continued_services["task_repository"].list_manual_executions_for_task_item(
                        run.task_id, run.items[0].task_item_id
                    )
                ),
            )

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
            # The saved Metadata Correction identity must survive into the explicit
            # continuation authority and complete the original manual journey.
            services = self._manual_services(environment, provider)
            self.addCleanup(self._close_manual_services, services)
            self._authorize_and_execute_continued(
                environment,
                services,
                run,
                expected_destination=results[-1].destination_path,
            )

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
            # The saved Classification rule decision must survive into the explicit
            # continuation authority and complete the original manual journey.
            services = self._manual_services(environment, provider)
            self.addCleanup(self._close_manual_services, services)
            self._authorize_and_execute_continued(
                environment,
                services,
                run,
                expected_destination=results[-1].destination_path,
            )

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
            # The saved RENAME conflict decision must survive into the explicit
            # continuation authority and complete the original manual journey without
            # touching the colliding destination.
            services = self._manual_services(environment, provider)
            self.addCleanup(self._close_manual_services, services)
            self._authorize_and_execute_continued(
                environment,
                services,
                run,
                expected_destination=results[-1].destination_path,
                collision=collision,
            )

    def _complete_analysis_for_summary(self, environment, provider):
        """Drive one original manual failure to a completed linked re-analysis."""
        services, run, _record, _preview = self._fail_manual_organize(environment, provider)
        with SQLiteTaskRepository(environment["database"]) as repository:
            submission = self._admit_and_continue(services, run, repository)
        self._close_manual_services(services)
        self._run_worker(environment, provider)
        self._completed_continuation_item(
            environment, submission.job.job_id, RecoveryContinuationStatus.COMPLETED
        )
        return run

    def test_recovery_confirmed_execution_clears_attention_after_real_worker(self):
        """A confirmed recovery clears the current problem once the real Worker succeeds.

        The same-page journey's durable preparation -> execution -> TaskItem/Result
        chain is the read authority for the current problem list.  Before the
        Worker runs the run is still in attention; after the real MOVE completes
        with a verified effect the source item leaves the problem list and the
        media is actually moved by OrganizerExecutor.
        """

        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            run = self._complete_analysis_for_summary(environment, provider)
            services = self._manual_services(environment, provider)
            recovery, api = self._recovery_api(environment, services)
            checkpoint = recovery._checkpoint_service.get(
                run.items[0].task_item_id, task_id=run.task_id
            )
            status, preparation = api_request(
                api,
                f"/api/v1/tasks/{run.task_id}/items/{run.items[0].task_item_id}"
                "/recovery/prepare-summary",
                method="POST",
                body={"expectedCheckpointVersion": checkpoint.checkpoint_version},
                token="operator-token",
            )
            self.assertEqual(201, status, f"{preparation}")
            preview = services["previews"].get(preparation["preview_id"])
            ready_item_id = preview.items[0].item_id
            # Before confirmation the run is still an outstanding problem.
            with SQLiteTaskRepository(environment["database"]) as repository:
                before = repository.operations_run(run.task_id)
                assert before is not None
                self.assertTrue(before.attention)
            status, admitted = api_request(
                api,
                f"/api/v1/manual-recovery-preparations/{preparation['preparation_id']}/confirm",
                method="POST",
                body={"itemIds": [ready_item_id], "confirmation": True},
                token="operator-token",
            )
            self.assertEqual(202, status, f"{admitted}")
            # Admission alone is not success: the source is untouched and the
            # problem is still outstanding until the real Worker outcome.
            self.assertTrue(environment["source_file"].exists())
            with SQLiteTaskRepository(environment["database"]) as repository:
                queued = repository.operations_run(run.task_id)
                assert queued is not None
                self.assertTrue(queued.attention)
            # The real resident Worker claims and runs the admitted execution.
            services["execution"].run_admitted(
                admitted["executionId"], worker_id="recovery-e2e-worker"
            )
            self._close_manual_services(services)
            self.assertFalse(environment["source_file"].exists())
            target_files = tuple(Path(environment["target_root"]).rglob("*.mkv"))
            self.assertEqual(1, len(target_files))
            # The confirmed follow-up is a durable success, so the source item
            # no longer occupies the current problem list.
            with SQLiteTaskRepository(environment["database"]) as repository:
                after = repository.operations_run(run.task_id)
                assert after is not None
                self.assertFalse(after.attention)
                self.assertEqual((), after.problem_types)

    def test_recovery_confirmed_execution_re_failure_keeps_both_failures_without_replay(self):
        """A confirmed recovery that fails again keeps both failures and never replays.

        The confirmed subset is admitted and the real Worker runs it.  If the
        execution fails again, the new failure is recorded independently while
        the original failure history is preserved, the admitted execution is
        never automatically retried, and the source item remains an outstanding
        problem with its own next step.
        """

        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            run = self._complete_analysis_for_summary(environment, provider)
            services = self._manual_services(
                environment,
                provider,
                executor=SelectiveManualExecutor("Correct.2024.mkv"),
            )
            recovery, api = self._recovery_api(environment, services)
            checkpoint = recovery._checkpoint_service.get(
                run.items[0].task_item_id, task_id=run.task_id
            )
            status, preparation = api_request(
                api,
                f"/api/v1/tasks/{run.task_id}/items/{run.items[0].task_item_id}"
                "/recovery/prepare-summary",
                method="POST",
                body={"expectedCheckpointVersion": checkpoint.checkpoint_version},
                token="operator-token",
            )
            self.assertEqual(201, status, f"{preparation}")
            preview = services["previews"].get(preparation["preview_id"])
            ready_item_id = preview.items[0].item_id
            status, admitted = api_request(
                api,
                f"/api/v1/manual-recovery-preparations/{preparation['preparation_id']}/confirm",
                method="POST",
                body={"itemIds": [ready_item_id], "confirmation": True},
                token="operator-token",
            )
            self.assertEqual(202, status, f"{admitted}")
            with SQLiteTaskRepository(environment["database"]) as repository:
                continuation_results_before = len(repository.list_results(admitted["taskId"]))
            # The real Worker runs the admitted subset; the failure executor
            # fails this exact source again before any Storage mutation.
            services["execution"].run_admitted(
                admitted["executionId"], worker_id="recovery-refail-worker"
            )
            self._close_manual_services(services)
            self.assertTrue(environment["source_file"].exists())
            self.assertEqual((), tuple(Path(environment["target_root"]).rglob("*")))
            with SQLiteTaskRepository(environment["database"]) as repository:
                continuation_results_after = repository.list_results(admitted["taskId"])
                # The re-failure is recorded on the continuation execution's own
                # Task while the original failure history is retained on the
                # source Task: neither overwrites the other.
                self.assertGreater(len(continuation_results_after), continuation_results_before)
                failures = tuple(
                    value
                    for value in continuation_results_after
                    if value.status.lower() == "failed"
                )
                self.assertGreaterEqual(len(failures), 1)
                original_results = repository.list_results(run.task_id)
                self.assertGreaterEqual(len(original_results), 1)
                # A re-failure is never automatically retried: the confirmed
                # summary stays confirmed with its linked execution and no new
                # authority is minted.
                persisted = repository.get_manual_recovery_preparation(
                    preparation["preparation_id"]
                )
                assert persisted is not None
                self.assertEqual("confirmed", persisted.status.value)
                self.assertEqual(admitted["executionId"], persisted.execution_id)
                active = tuple(
                    value
                    for value in repository.list_manual_execution_authorizations(limit=50)
                    if value.status.value == "active"
                )
                self.assertEqual((), active)

    def test_recovery_prepare_summary_is_read_only_and_durable(self):
        """Prepare publishes a durable, authority-free summary with zero mutation."""
        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            run = self._complete_analysis_for_summary(environment, provider)
            services = self._manual_services(environment, provider)
            recovery, api = self._recovery_api(environment, services)
            self.addCleanup(self._close_manual_services, services)
            checkpoint = recovery._checkpoint_service.get(
                run.items[0].task_item_id, task_id=run.task_id
            )
            with SQLiteTaskRepository(environment["database"]) as repository:
                executions_before = len(
                    repository.list_manual_executions_for_task_item(
                        run.task_id, run.items[0].task_item_id
                    )
                )
            status, preparation = api_request(
                api,
                f"/api/v1/tasks/{run.task_id}/items/{run.items[0].task_item_id}"
                "/recovery/prepare-summary",
                method="POST",
                body={"expectedCheckpointVersion": checkpoint.checkpoint_version},
                token="operator-token",
            )
            self.assertEqual(201, status, f"{preparation}")
            self.assertEqual("prepared", preparation["status"])
            self.assertIsNone(preparation["authorization_id"])
            self.assertIsNone(preparation["execution_id"])
            self.assertFalse(preparation["hasExecutionAuthority"])
            # Zero mutation, zero authority, zero new execution.
            self.assertTrue(environment["source_file"].exists())
            self.assertEqual((), tuple(Path(environment["target_root"]).rglob("*")))
            with SQLiteTaskRepository(environment["database"]) as repository:
                self.assertEqual(
                    executions_before,
                    len(
                        repository.list_manual_executions_for_task_item(
                            run.task_id, run.items[0].task_item_id
                        )
                    ),
                )
                self.assertIsNone(
                    repository.get_manual_recovery_link_by_source(
                        run.task_id, run.items[0].task_item_id
                    )
                )
            # The summary survives a fresh repository handle and a new service.
            reopened = self._manual_services(environment, provider)
            self.addCleanup(self._close_manual_services, reopened)
            rediscovery, _api = self._recovery_api(environment, reopened)
            durable = rediscovery.discovery_for_preparation(run.task_id, run.items[0].task_item_id)
            assert durable is not None
            self.assertEqual(preparation["preparation_id"], durable["preparation_id"])
            self.assertEqual(preparation["preview_id"], durable["preview_id"])

    def test_recovery_prepare_summary_reuses_analysis_without_provider_lookup(self):
        """Preparing the summary adds no Provider search or detail round-trip.

        The completed linked re-analysis already resolved this source's identity
        under the pinned policy.  The summary consumes that durable identity
        instead of re-running the analysis chain inside the HTTP request.
        """

        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            run = self._complete_analysis_for_summary(environment, provider)
            services = self._manual_services(environment, provider)
            recovery, api = self._recovery_api(environment, services)
            self.addCleanup(self._close_manual_services, services)
            checkpoint = recovery._checkpoint_service.get(
                run.items[0].task_item_id, task_id=run.task_id
            )
            searches_before = len(provider.movie_queries)
            details_before = len(provider.movie_details)
            status, preparation = api_request(
                api,
                f"/api/v1/tasks/{run.task_id}/items/{run.items[0].task_item_id}"
                "/recovery/prepare-summary",
                method="POST",
                body={"expectedCheckpointVersion": checkpoint.checkpoint_version},
                token="operator-token",
            )
            self.assertEqual(201, status, f"{preparation}")
            self.assertEqual(searches_before, len(provider.movie_queries))
            self.assertEqual(details_before, len(provider.movie_details))
            preview = services["previews"].get(preparation["preview_id"])
            self.assertEqual("previewed", preview.items[0].status.value)
            self.assertIsNotNone(preview.items[0].plan)

    def test_tv_episode_identity_survives_durable_summary_rebuild(self):
        """The durable analysis identity preserves per-episode naming inputs."""

        for missing_strategy in ("omit_token", "error"):
            with self.subTest(missing_strategy=missing_strategy):
                with tempfile.TemporaryDirectory() as directory:

                    def configure_tv(document):
                        for policy in document["namingPolicies"]:
                            if policy["id"] == "B":
                                policy["missingVariableStrategy"] = missing_strategy

                    environment = self._environment(
                        directory,
                        source_subdir="电视剧",
                        document_patch=configure_tv,
                    )
                    source_file = Path(environment["source_file"])
                    tv_source = source_file.with_name("Correct.S01E01.2024.mkv")
                    source_file.rename(tv_source)
                    environment["source_file"] = tv_source
                    environment["storage_path"] = "Media/电视剧/Correct.S01E01.2024.mkv"
                    environment["display_source"] = str(tv_source)
                    provider = EpisodeCountingProvider(
                        MediaCandidate(
                            "tmdb",
                            "tv-42",
                            MediaType.TV,
                            "Correct",
                            year=2024,
                            genres=("Drama",),
                            countries=("JP",),
                            languages=("ja",),
                            keywords=("mystery",),
                        )
                    )
                    services, run, _record, first_preview = self._fail_manual_organize(
                        environment,
                        provider,
                        executor=SelectiveManualExecutor("Correct.S01E01.2024.mkv"),
                        source_subdir="电视剧",
                        choice=ManualChoice("B", None, "B", "B", "B"),
                    )
                    first_target = first_preview.items[0].plan["destination"]["path"]
                    self.assertIn("Episode 1", first_target)
                    with SQLiteTaskRepository(environment["database"]) as repository:
                        submission = self._admit_and_continue(services, run, repository)
                    self._close_manual_services(services)
                    self._run_worker(environment, provider)
                    continuation, analysis_item = self._completed_continuation_item(
                        environment,
                        submission.job.job_id,
                        RecoveryContinuationStatus.COMPLETED,
                    )
                    self.assertIsNotNone(analysis_item)
                    assert analysis_item is not None
                    self.assertIsNotNone(continuation.new_result_id)
                    with SQLiteTaskRepository(environment["database"]) as repository:
                        analysis_evidence = repository.list_evidence_for_item(
                            analysis_item.item_id, limit=16
                        )
                        metadata_section = analysis_evidence[0].section("metadata")
                        plan_section = analysis_evidence[0].section("plan")
                        self.assertTrue(metadata_section.available)
                        self.assertTrue(plan_section.available)
                        assert metadata_section.value is not None
                        assert plan_section.value is not None
                        self.assertEqual("Episode 1", metadata_section.value.get("episodeTitle"))
                        self.assertEqual(
                            "Episode 1",
                            metadata_section.value["episodeMetadata"][0]["title"],
                        )
                        self.assertEqual(("mystery",), tuple(metadata_section.value["keywords"]))
                        durable_identity = (
                            ManualRecoveryContinuationService._identity_from_document(
                                analysis_evidence[0].execution_identity
                            )
                        )
                        self.assertIsNotNone(durable_identity)
                        assert durable_identity is not None
                        self.assertEqual(("mystery",), durable_identity.keywords)
                        self.assertEqual(
                            ("Corrected Alternate",), durable_identity.alternative_titles
                        )
                        self.assertEqual(("正确",), durable_identity.translated_titles)
                        self.assertEqual(("Drama",), durable_identity.genres)
                        self.assertEqual(("JP",), durable_identity.countries)
                        self.assertEqual(("ja",), durable_identity.languages)
                        self.assertEqual(("imdb", "tt1234567"), durable_identity.external_ids[0])
                        self.assertEqual(
                            "Episode overview", durable_identity.episode_metadata[0].overview
                        )
                        self.assertEqual("Episode 1", durable_identity.episode_title)
                        self.assertEqual("Episode 1", durable_identity.episode_metadata[0].title)
                        self.assertIsNone(
                            ManualRecoveryContinuationService._identity_from_document(
                                metadata_section.value
                            ),
                            "bounded operator evidence is not a plan identity snapshot",
                        )
                        legacy_tv_evidence = dict(metadata_section.value)
                        self.assertIsNone(
                            ManualRecoveryContinuationService._identity_from_document(
                                legacy_tv_evidence
                            ),
                            (
                                "legacy evidence without an exact identity snapshot "
                                "must request a new analysis"
                            ),
                        )
                        self.assertIn("Episode 1", plan_section.value["target"])
                        analysis_target = plan_section.value["target"]

                    provider_calls_before_summary = provider.calls
                    services = self._manual_services(environment, provider)
                    recovery, api = self._recovery_api(environment, services)
                    self.addCleanup(self._close_manual_services, services)
                    checkpoint = recovery._checkpoint_service.get(
                        run.items[0].task_item_id, task_id=run.task_id
                    )
                    status, preparation = api_request(
                        api,
                        f"/api/v1/tasks/{run.task_id}/items/{run.items[0].task_item_id}"
                        "/recovery/prepare-summary",
                        method="POST",
                        body={"expectedCheckpointVersion": checkpoint.checkpoint_version},
                        token="operator-token",
                    )
                    self.assertEqual(201, status, f"{preparation}")
                    self.assertEqual(provider_calls_before_summary, provider.calls)
                    summary = services["previews"].get(preparation["preview_id"])
                    summary_target = summary.items[0].plan["destination"]["path"]
                    self.assertEqual(analysis_target, summary_target)
                    self.assertIn("Episode 1", summary_target)
                    self.assertTrue(tv_source.exists())
                    self.assertEqual(
                        (),
                        tuple(
                            value
                            for value in Path(environment["target_root"]).rglob("*")
                            if value.is_file()
                        ),
                    )

                    status, admitted = api_request(
                        api,
                        f"/api/v1/manual-recovery-preparations/"
                        f"{preparation['preparation_id']}/confirm",
                        method="POST",
                        body={
                            "itemIds": [summary.items[0].item_id],
                            "confirmation": True,
                        },
                        token="operator-token",
                    )
                    self.assertEqual(202, status, f"{admitted}")
                    self.assertTrue(tv_source.exists())
                    self._run_worker(environment, provider)
                    physical_target = Path(environment["target_root"]) / summary_target
                    self.assertTrue(physical_target.is_file(), str(physical_target))
                    self.assertIn("Episode 1", physical_target.name)
                    self.assertFalse(tv_source.exists())

    def test_long_overview_survives_durable_summary_and_classification(self):
        """Long accepted overviews remain complete plan inputs after DB reopen."""

        marker = "tailmarker"
        lengths = (3900, 5200, 4096, 4097)
        for overview_length in lengths:
            with self.subTest(overview_length=overview_length):
                with tempfile.TemporaryDirectory() as directory:

                    def configure_overview_classification(document):
                        for policy in document["classificationPolicies"]:
                            if policy["id"] == "A":
                                policy["rules"].insert(
                                    0,
                                    {
                                        "id": "overview-tail-marker",
                                        "priority": 150,
                                        "conditions": {
                                            "mediaType": ["movie"],
                                            "keywords": [marker],
                                        },
                                        "result": {
                                            "mediaLibraryId": "movies",
                                            "library": "Movies",
                                            "path": ["Overview Tail"],
                                        },
                                    },
                                )

                    overview = "x" * (overview_length - len(marker)) + marker
                    environment = self._environment(
                        directory, document_patch=configure_overview_classification
                    )
                    provider = DetailCountingProvider(
                        (
                            MediaCandidate(
                                "tmdb",
                                "42",
                                MediaType.MOVIE,
                                "Correct",
                                year=2024,
                                overview=overview,
                            ),
                        )
                    )
                    services, run, _record, first_preview = self._fail_manual_organize(
                        environment,
                        provider,
                        executor=SelectiveManualExecutor("Correct.2024.mkv"),
                        choice=ManualChoice("A", None, "A", "A", "A"),
                    )
                    analysis_target = first_preview.items[0].plan["destination"]["path"]
                    self.assertIn("Overview Tail", analysis_target)
                    with SQLiteTaskRepository(environment["database"]) as repository:
                        submission = self._admit_and_continue(services, run, repository)
                    self._close_manual_services(services)
                    self._run_worker(environment, provider)
                    continuation, analysis_item = self._completed_continuation_item(
                        environment,
                        submission.job.job_id,
                        RecoveryContinuationStatus.COMPLETED,
                    )
                    self.assertIsNotNone(analysis_item)
                    assert analysis_item is not None
                    self.assertIsNotNone(continuation.new_result_id)
                    with SQLiteTaskRepository(environment["database"]) as repository:
                        analysis_evidence = repository.list_evidence_for_item(
                            analysis_item.item_id, limit=16
                        )
                        self.assertTrue(analysis_evidence)
                        execution_identity = analysis_evidence[0].execution_identity
                        self.assertIsNotNone(execution_identity)
                        assert execution_identity is not None
                        self.assertEqual(overview, execution_identity["overview"])
                        rebuilt = ManualRecoveryContinuationService._identity_from_document(
                            execution_identity
                        )
                        self.assertIsNotNone(rebuilt)
                        assert rebuilt is not None
                        self.assertEqual(overview, rebuilt.overview)

                    services = self._manual_services(environment, provider)
                    recovery, api = self._recovery_api(environment, services)
                    self.addCleanup(self._close_manual_services, services)
                    checkpoint = recovery._checkpoint_service.get(
                        run.items[0].task_item_id, task_id=run.task_id
                    )
                    provider_calls_before_summary = provider.calls
                    status, preparation = api_request(
                        api,
                        f"/api/v1/tasks/{run.task_id}/items/{run.items[0].task_item_id}"
                        "/recovery/prepare-summary",
                        method="POST",
                        body={"expectedCheckpointVersion": checkpoint.checkpoint_version},
                        token="operator-token",
                    )
                    self.assertEqual(201, status, f"{preparation}")
                    self.assertEqual(provider_calls_before_summary, provider.calls)
                    summary = services["previews"].get(preparation["preview_id"])
                    summary_target = summary.items[0].plan["destination"]["path"]
                    self.assertEqual(analysis_target, summary_target)
                    self.assertIn("Overview Tail", summary_target)
                    self.assertTrue(environment["source_file"].exists())
                    self.assertEqual(
                        (),
                        tuple(
                            value
                            for value in Path(environment["target_root"]).rglob("*")
                            if value.is_file()
                        ),
                    )

                    self._close_manual_services(services)
                    services = self._manual_services(environment, provider)
                    recovery, api = self._recovery_api(environment, services)
                    with SQLiteTaskRepository(environment["database"]) as repository:
                        durable = repository.get_current_manual_recovery_preparation(
                            run.task_id, run.items[0].task_item_id
                        )
                        self.assertIsNotNone(durable)
                        assert durable is not None
                        self.assertEqual(preparation["preparation_id"], durable.preparation_id)
                    preview = services["previews"].get(preparation["preview_id"])
                    status, admitted = api_request(
                        api,
                        f"/api/v1/manual-recovery-preparations/"
                        f"{preparation['preparation_id']}/confirm",
                        method="POST",
                        body={"itemIds": [preview.items[0].item_id], "confirmation": True},
                        token="operator-token",
                    )
                    self.assertEqual(202, status, f"{admitted}")
                    self.assertTrue(environment["source_file"].exists())
                    self._close_manual_services(services)
                    self._run_worker(environment, provider)
                    physical_target = Path(environment["target_root"]) / summary_target
                    self.assertTrue(physical_target.is_file(), str(physical_target))
                    self.assertFalse(environment["source_file"].exists())

    def test_oversized_identity_explains_why_reanalysis_cannot_repair_summary(self):
        """An over-limit identity gives a usable correction instead of a loop."""

        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            task, item = self._seed_failed_item(environment)
            identity, unavailable_reason = _execution_identity_document(
                MediaIdentity(
                    "tmdb",
                    "42",
                    MediaType.MOVIE,
                    "Correct",
                    year=2024,
                    overview="x" * 132_000,
                )
            )
            self.assertIsNone(identity)
            self.assertEqual("identity_exceeds_supported_size", unavailable_reason)
            evidence = PipelineEvidence(
                evidence_id=f"{item.item_id}:size-limit",
                task_id=task.task_id,
                item_id=item.item_id,
                attempts=1,
                source_storage_id=item.storage_id,
                source_path=item.source_path,
                captured_at=datetime.now(UTC),
                configuration_snapshot_id=task.configuration_snapshot_id,
                configuration_snapshot_digest=task.configuration_snapshot_digest,
                outcome="completed",
                sections={},
                execution_identity=identity,
                execution_identity_unavailable_reason=unavailable_reason,
            )
            with SQLiteTaskRepository(environment["database"]) as repository:
                repository.append_evidence(evidence)
                persisted = repository.list_evidence_for_item(item.item_id, limit=1)[0]
                self.assertIsNone(persisted.execution_identity)
                self.assertEqual(
                    unavailable_reason, persisted.execution_identity_unavailable_reason
                )
                service = ManualRecoveryContinuationService(
                    repository,
                    intent_service=None,
                    preview_service=None,
                    execution_service=Mock(),
                    checkpoint_service=Mock(),
                )
                with self.assertRaises(ManualRecoveryContinuationError) as raised:
                    service._reusable_analysis_identity(item.item_id)
            self.assertEqual("analysis_identity_unsupported", raised.exception.code)
            next_action = raised.exception.next_action
            self.assertIn("different Metadata candidate", next_action)
            self.assertIn("repeating the same identity will not", next_action)

    def test_recovery_prepare_summary_reuses_durable_identity_with_saved_metadata_decision(self):
        """A saved Metadata decision must not force a live Provider lookup.

        The operator resolves the ambiguous re-analysis candidate, the next
        re-analysis completes under that exact decision, and the same-page
        summary must consume the durable identity the completed analysis
        resolved instead of running the decision through a fresh Provider
        search/detail inside the HTTP request.
        """

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
                MetadataReviewService(repository).resolve(review.review_id, 1, actor="operator")
                resolved = repository.get_metadata_review_for_item(linked.item_id)
                assert resolved is not None
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

            services = self._manual_services(environment, provider)
            recovery, api = self._recovery_api(environment, services)
            self.addCleanup(self._close_manual_services, services)
            checkpoint = recovery._checkpoint_service.get(
                run.items[0].task_item_id, task_id=run.task_id
            )
            searches_before = len(provider.movie_queries)
            details_before = len(provider.movie_details)
            status, preparation = api_request(
                api,
                f"/api/v1/tasks/{run.task_id}/items/{run.items[0].task_item_id}"
                "/recovery/prepare-summary",
                method="POST",
                body={"expectedCheckpointVersion": checkpoint.checkpoint_version},
                token="operator-token",
            )
            self.assertEqual(201, status, f"{preparation}")
            self.assertEqual(searches_before, len(provider.movie_queries))
            self.assertEqual(details_before, len(provider.movie_details))
            preview = services["previews"].get(preparation["preview_id"])
            self.assertEqual("previewed", preview.items[0].status.value)
            self.assertIsNotNone(preview.items[0].plan)
            self.assertIn("tmdbid-42", preview.items[0].plan["destination"]["path"])
            self.assertTrue(environment["source_file"].exists())
            self.assertEqual((), tuple(Path(environment["target_root"]).rglob("*")))

    def test_recovery_confirm_prepared_admits_exact_subset_and_links_summary(self):
        """Confirmation admits the exact subset and links the summary atomically."""

        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            run = self._complete_analysis_for_summary(environment, provider)
            services = self._manual_services(environment, provider)
            recovery, api = self._recovery_api(environment, services)
            self.addCleanup(self._close_manual_services, services)
            checkpoint = recovery._checkpoint_service.get(
                run.items[0].task_item_id, task_id=run.task_id
            )
            status, preparation = api_request(
                api,
                f"/api/v1/tasks/{run.task_id}/items/{run.items[0].task_item_id}"
                "/recovery/prepare-summary",
                method="POST",
                body={"expectedCheckpointVersion": checkpoint.checkpoint_version},
                token="operator-token",
            )
            self.assertEqual(201, status, f"{preparation}")
            preview = services["previews"].get(preparation["preview_id"])
            ready_item_id = preview.items[0].item_id
            status, admitted = api_request(
                api,
                f"/api/v1/manual-recovery-preparations/{preparation['preparation_id']}/confirm",
                method="POST",
                body={"itemIds": [ready_item_id], "confirmation": True},
                token="operator-token",
            )
            self.assertEqual(202, status, f"{admitted}")
            self.assertEqual([ready_item_id], admitted["selectedItemIds"])
            with SQLiteTaskRepository(environment["database"]) as repository:
                persisted = repository.get_manual_recovery_preparation(
                    preparation["preparation_id"]
                )
                assert persisted is not None
                self.assertEqual("confirmed", persisted.status.value)
                self.assertEqual(admitted["executionId"], persisted.execution_id)
                self.assertIsNotNone(persisted.authorization_id)
            # A repeated confirmation resolves to the same durable execution.
            status, repeated = api_request(
                api,
                f"/api/v1/manual-recovery-preparations/{preparation['preparation_id']}/confirm",
                method="POST",
                body={"itemIds": [ready_item_id], "confirmation": True},
                token="operator-token",
            )
            self.assertEqual(202, status, f"{repeated}")
            self.assertEqual(admitted["executionId"], repeated["executionId"])

    def test_recovery_prepare_summary_supersedes_previous_and_rejects_stale_checkpoint(self):
        """A fresh summary supersedes the old one; a stale checkpoint is refused."""

        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            run = self._complete_analysis_for_summary(environment, provider)
            services = self._manual_services(environment, provider)
            recovery, api = self._recovery_api(environment, services)
            self.addCleanup(self._close_manual_services, services)
            checkpoint = recovery._checkpoint_service.get(
                run.items[0].task_item_id, task_id=run.task_id
            )
            status, first = api_request(
                api,
                f"/api/v1/tasks/{run.task_id}/items/{run.items[0].task_item_id}"
                "/recovery/prepare-summary",
                method="POST",
                body={"expectedCheckpointVersion": checkpoint.checkpoint_version},
                token="operator-token",
            )
            self.assertEqual(201, status)
            status, second = api_request(
                api,
                f"/api/v1/tasks/{run.task_id}/items/{run.items[0].task_item_id}"
                "/recovery/prepare-summary",
                method="POST",
                body={"expectedCheckpointVersion": checkpoint.checkpoint_version},
                token="operator-token",
            )
            self.assertEqual(201, status)
            self.assertNotEqual(first["preparation_id"], second["preparation_id"])
            with SQLiteTaskRepository(environment["database"]) as repository:
                superseded = repository.get_manual_recovery_preparation(first["preparation_id"])
                assert superseded is not None
                self.assertEqual("superseded", superseded.status.value)
                current = repository.get_current_manual_recovery_preparation(
                    run.task_id, run.items[0].task_item_id
                )
                assert current is not None
                self.assertEqual(second["preparation_id"], current.preparation_id)
            # Confirming the superseded summary is refused; the current one is not.
            status, refused = api_request(
                api,
                f"/api/v1/manual-recovery-preparations/{first['preparation_id']}/confirm",
                method="POST",
                body={"itemIds": [run.items[0].task_item_id], "confirmation": True},
                token="operator-token",
            )
            self.assertEqual(409, status, f"{refused}")
            # A stale checkpoint version is refused before any work is created.
            status, stale = api_request(
                api,
                f"/api/v1/tasks/{run.task_id}/items/{run.items[0].task_item_id}"
                "/recovery/prepare-summary",
                method="POST",
                body={"expectedCheckpointVersion": "0" * 64},
                token="operator-token",
            )
            self.assertEqual(409, status, f"{stale}")
            self.assertEqual("stale_checkpoint", stale["error"]["code"])

    def test_recovery_prepare_summary_requires_write_permission(self):
        """A read-only principal cannot prepare a plan summary."""

        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            run = self._complete_analysis_for_summary(environment, provider)
            services = self._manual_services(environment, provider)
            recovery, api = self._recovery_api(environment, services)
            self.addCleanup(self._close_manual_services, services)
            checkpoint = recovery._checkpoint_service.get(
                run.items[0].task_item_id, task_id=run.task_id
            )
            status, denied = api_request(
                api,
                f"/api/v1/tasks/{run.task_id}/items/{run.items[0].task_item_id}"
                "/recovery/prepare-summary",
                method="POST",
                body={"expectedCheckpointVersion": checkpoint.checkpoint_version},
                token="viewer-token",
            )
            self.assertEqual(403, status, f"{denied}")
            self.assertTrue(environment["source_file"].exists())
            self.assertEqual((), tuple(Path(environment["target_root"]).rglob("*")))

    def test_recovery_confirm_rejects_other_actor_and_confirmation_without_flag(self):
        """Only the preparing actor may confirm, and only with confirmation=true."""

        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            run = self._complete_analysis_for_summary(environment, provider)
            services = self._manual_services(environment, provider)
            recovery, api = self._recovery_api(environment, services)
            self.addCleanup(self._close_manual_services, services)
            checkpoint = recovery._checkpoint_service.get(
                run.items[0].task_item_id, task_id=run.task_id
            )
            status, preparation = api_request(
                api,
                f"/api/v1/tasks/{run.task_id}/items/{run.items[0].task_item_id}"
                "/recovery/prepare-summary",
                method="POST",
                body={"expectedCheckpointVersion": checkpoint.checkpoint_version},
                token="operator-token",
            )
            self.assertEqual(201, status)
            confirm_path = (
                f"/api/v1/manual-recovery-preparations/{preparation['preparation_id']}/confirm"
            )
            # confirmation must be exactly true.
            status, refused = api_request(
                api,
                confirm_path,
                method="POST",
                body={"itemIds": [run.items[0].task_item_id], "confirmation": False},
                token="operator-token",
            )
            self.assertEqual(400, status, f"{refused}")
            # A read-only principal cannot confirm at all.
            status, denied = api_request(
                api,
                confirm_path,
                method="POST",
                body={"itemIds": [run.items[0].task_item_id], "confirmation": True},
                token="viewer-token",
            )
            self.assertEqual(403, status, f"{denied}")
            # A different write principal is refused because the summary is not
            # theirs, and no execution is admitted.
            self.assertTrue(environment["source_file"].exists())
            self.assertEqual((), tuple(Path(environment["target_root"]).rglob("*")))

    def test_recovery_confirm_concurrently_admits_one_execution(self):
        """Two concurrent confirmations of the same summary admit at most one."""

        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            run = self._complete_analysis_for_summary(environment, provider)
            services = self._manual_services(environment, provider)
            recovery, api = self._recovery_api(environment, services)
            self.addCleanup(self._close_manual_services, services)
            checkpoint = recovery._checkpoint_service.get(
                run.items[0].task_item_id, task_id=run.task_id
            )
            status, preparation = api_request(
                api,
                f"/api/v1/tasks/{run.task_id}/items/{run.items[0].task_item_id}"
                "/recovery/prepare-summary",
                method="POST",
                body={"expectedCheckpointVersion": checkpoint.checkpoint_version},
                token="operator-token",
            )
            self.assertEqual(201, status)
            preview = services["previews"].get(preparation["preview_id"])
            ready_item_id = preview.items[0].item_id

            def confirm():
                return api_request(
                    api,
                    f"/api/v1/manual-recovery-preparations/{preparation['preparation_id']}/confirm",
                    method="POST",
                    body={"itemIds": [ready_item_id], "confirmation": True},
                    token="operator-token",
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = [
                    future.result() for future in (pool.submit(confirm), pool.submit(confirm))
                ]
            accepted = [value for value in outcomes if value[0] == 202]
            self.assertGreaterEqual(len(accepted), 1, f"{outcomes}")
            execution_ids = {value[1]["executionId"] for value in accepted}
            self.assertEqual(1, len(execution_ids), f"{outcomes}")
            with SQLiteTaskRepository(environment["database"]) as repository:
                self.assertEqual(
                    1,
                    len(
                        repository.list_manual_executions_for_task_item(
                            run.task_id, run.items[0].task_item_id
                        )
                    ),
                )

    def test_recovery_confirm_refuses_different_or_partial_selection(self):
        """A repeat confirmation of a *different* selection is never folded in.

        Only an exactly equivalent repeat may resolve to the already-admitted
        execution; a different, extra, empty, duplicate or malformed selection
        is a different submission and must be refused with its own reason.
        """

        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            run = self._complete_analysis_for_summary(environment, provider)
            services = self._manual_services(environment, provider)
            recovery, api = self._recovery_api(environment, services)
            self.addCleanup(self._close_manual_services, services)
            checkpoint = recovery._checkpoint_service.get(
                run.items[0].task_item_id, task_id=run.task_id
            )
            status, preparation = api_request(
                api,
                f"/api/v1/tasks/{run.task_id}/items/{run.items[0].task_item_id}"
                "/recovery/prepare-summary",
                method="POST",
                body={"expectedCheckpointVersion": checkpoint.checkpoint_version},
                token="operator-token",
            )
            self.assertEqual(201, status, f"{preparation}")
            preview = services["previews"].get(preparation["preview_id"])
            ready_item_id = preview.items[0].item_id
            confirm_path = (
                f"/api/v1/manual-recovery-preparations/{preparation['preparation_id']}/confirm"
            )
            status, admitted = api_request(
                api,
                confirm_path,
                method="POST",
                body={"itemIds": [ready_item_id], "confirmation": True},
                token="operator-token",
            )
            self.assertEqual(202, status, f"{admitted}")
            execution_id = admitted["executionId"]
            # Exactly equivalent repeat still resolves to the same execution.
            status, repeated = api_request(
                api,
                confirm_path,
                method="POST",
                body={"itemIds": [ready_item_id], "confirmation": True},
                token="operator-token",
            )
            self.assertEqual(202, status, f"{repeated}")
            self.assertEqual(execution_id, repeated["executionId"])
            # A different selection is refused and returns no execution.
            status, refused = api_request(
                api,
                confirm_path,
                method="POST",
                body={"itemIds": ["never-reviewed-item"], "confirmation": True},
                token="operator-token",
            )
            self.assertEqual(409, status, f"{refused}")
            self.assertEqual("confirmation_mismatch", refused["error"]["code"])
            # A different destructive permission is also a different submission.
            status, refused_permission = api_request(
                api,
                confirm_path,
                method="POST",
                body={
                    "itemIds": [ready_item_id],
                    "confirmation": True,
                    "allowOverwrite": True,
                },
                token="operator-token",
            )
            self.assertEqual(409, status, f"{refused_permission}")
            self.assertEqual("confirmation_mismatch", refused_permission["error"]["code"])
            # An empty or duplicate selection is refused before any admission.
            for body in (
                {"itemIds": [], "confirmation": True},
                {"itemIds": [ready_item_id, ready_item_id], "confirmation": True},
            ):
                status, malformed = api_request(
                    api, confirm_path, method="POST", body=body, token="operator-token"
                )
                self.assertEqual(400, status, f"{malformed}")
            with SQLiteTaskRepository(environment["database"]) as repository:
                self.assertEqual(
                    1,
                    len(
                        repository.list_manual_executions_for_task_item(
                            run.task_id, run.items[0].task_item_id
                        )
                    ),
                )

    def test_recovery_confirm_reruns_checkpoint_fence_inside_atomic_admission(self):
        """A checkpoint change after preflight is still refused inside the transaction.

        The HTTP preflight reads the item's checkpoint; a concurrent decision
        can then move the item before the atomic admission begins.  The
        admission must re-project the same bounded checkpoint while holding its
        write transaction, so the stale summary can never create an execution.
        """

        with tempfile.TemporaryDirectory() as directory:
            environment = self._environment(directory)
            provider = DetailCountingProvider(
                (MediaCandidate("tmdb", "42", MediaType.MOVIE, "Correct", year=2024),)
            )
            run = self._complete_analysis_for_summary(environment, provider)
            services = self._manual_services(environment, provider)
            recovery, api = self._recovery_api(environment, services)
            self.addCleanup(self._close_manual_services, services)
            checkpoint = recovery._checkpoint_service.get(
                run.items[0].task_item_id, task_id=run.task_id
            )
            status, preparation = api_request(
                api,
                f"/api/v1/tasks/{run.task_id}/items/{run.items[0].task_item_id}"
                "/recovery/prepare-summary",
                method="POST",
                body={"expectedCheckpointVersion": checkpoint.checkpoint_version},
                token="operator-token",
            )
            self.assertEqual(201, status, f"{preparation}")
            preview = services["previews"].get(preparation["preview_id"])
            ready_item_id = preview.items[0].item_id
            with SQLiteTaskRepository(environment["database"]) as repository:
                executions_before = len(
                    repository.list_manual_executions_for_intent(preview.intent_id, limit=100)
                )
            # The preflight has already passed; change the original item's
            # checkpoint before the atomic admission runs.
            with SQLiteTaskRepository(environment["database"]) as mutator:
                item = mutator.get_item(run.items[0].task_item_id)
                assert item is not None
                mutator.upsert_item(
                    replace(item, status=TaskItemStatus.IGNORED, stage="ignored_by_operator")
                )
            status, refused = api_request(
                api,
                f"/api/v1/manual-recovery-preparations/{preparation['preparation_id']}/confirm",
                method="POST",
                body={"itemIds": [ready_item_id], "confirmation": True},
                token="operator-token",
            )
            self.assertEqual(409, status, f"{refused}")
            self.assertIn(
                refused["error"]["code"], {"stale_checkpoint", "item_stale", "preview_stale"}
            )
            with SQLiteTaskRepository(environment["database"]) as repository:
                self.assertEqual(
                    executions_before,
                    len(repository.list_manual_executions_for_intent(preview.intent_id, limit=100)),
                )
                active_authorizations = tuple(
                    value
                    for value in repository.list_manual_execution_authorizations(limit=50)
                    if value.status.value == "active"
                )
                self.assertEqual((), active_authorizations)


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
