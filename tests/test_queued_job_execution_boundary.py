from __future__ import annotations

import io
import json
import tempfile
import unittest
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.automation import AutomationJobService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.dashboard import DashboardService
from mediaflow.application.execution_authorization import ExecutionAuthorizationService
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.metadata import (
    MediaCandidate,
    MediaIdentity,
    MediaType,
    ProviderCapabilities,
)
from mediaflow.domain.organizer import (
    Conflict,
    ConflictType,
    OrganizeOperationType,
    OrganizePlan,
    OrganizePolicy,
    PlanOperation,
    PlanStatus,
    StorageLocation,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import ConfirmationStatus, TaskItemStatus
from mediaflow.final_cli import _run_queued_workflow, final_main
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi


class FakeTMDBProvider:
    """Local deterministic Movie provider used only inside temporary journeys."""

    provider_id = "tmdb"
    capabilities = ProviderCapabilities(can_search_movie=True)

    def __init__(self, *_args, **_kwargs):
        pass

    def search_movie(self, _query, _policy=None, **_kwargs):
        return (
            MediaCandidate(
                "tmdb",
                "4242",
                MediaType.MOVIE,
                "Example Movie",
                year=2024,
                genres=("Animation",),
                countries=("JP",),
            ),
        )

    def get_movie(self, provider_id, _policy=None, **_kwargs):
        return MediaIdentity(
            "tmdb",
            provider_id,
            MediaType.MOVIE,
            "Example Movie",
            year=2024,
            genres=("Animation",),
            countries=("JP",),
        )


@dataclass(frozen=True)
class JourneyOutcome:
    job_status: str
    job_execute_authorized: bool
    task_command: str
    task_status: str
    item_status: str | None
    item_destination: str | None
    result_status: str | None
    result_operation: str | None
    result_organize_policy_id: str | None
    pending_confirmations: int
    evidence_outcome: str | None
    evidence_conflicts: tuple[tuple[str, str, str], ...]
    evidence_strategy: str | None
    evidence_next_action: str | None


class QueuedJobExecutionBoundaryTests(unittest.TestCase):
    """Vertical evidence for the shared queued Job execution boundary (RO-8)."""

    def _managed_environment(self, root: Path, *, collision_destination=None):
        source_root = root / "source"
        target_root = root / "target"
        (source_root / "电影").mkdir(parents=True)
        target_root.mkdir()
        (source_root / "电影" / "Example.Movie.2024.mkv").write_bytes(b"movie")
        if collision_destination is not None:
            collision = target_root.joinpath(*collision_destination.split("/"))
            collision.parent.mkdir(parents=True, exist_ok=True)
            collision.write_bytes(b"existing-destination")
        database = root / "runtime.sqlite3"
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        document["storages"][0]["rootPath"] = str(source_root)
        document["storages"][1]["rootPath"] = str(target_root)
        document["resourceLibraries"][0]["storagePath"] = ""
        document["resourceLibraries"][0]["displayRootPath"] = str(source_root)
        document["recognitionRules"][0]["condition"] = {
            "field": "resource_library_id",
            "operator": "equals",
            "value": "source",
        }
        document["persistence"]["databasePath"] = str(database)
        config = root / "bootstrap.json"
        config.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        with SQLiteConfigurationRepository(database) as repository:
            service = ManagedConfigurationService(repository, bootstrap_database_path=str(database))
            draft = service.import_draft(document, actor="tester")
            validated = service.validate(draft.revision_id, actor="tester")
            active = service.activate(
                validated.revision_id,
                expected_version=validated.version,
                actor="tester",
            )
        return source_root, target_root, database, config, active

    def _run_worker(self, config: Path) -> int:
        output, error = io.StringIO(), io.StringIO()
        with (
            patch.dict(
                "os.environ",
                {
                    "TMDB_ACCESS_TOKEN": "test-token",
                    "MEDIAFLOW_API_TOKEN": "operator-token",
                },
                clear=True,
            ),
            patch(
                "mediaflow.infrastructure.metadata_provider_bootstrap.TMDBProvider",
                FakeTMDBProvider,
            ),
            patch(
                "mediaflow.infrastructure.metadata_provider_bootstrap.TMDBClient",
                return_value=object(),
            ),
        ):
            code = final_main(
                ["--config", str(config), "worker", "run-next"],
                stdout=output,
                stderr=error,
            )
        self.assertEqual(code, 0, error.getvalue())
        return code

    @staticmethod
    def _pending_count(repository: SQLiteTaskRepository) -> int:
        return (
            DashboardService(repository, resource_library_count=1, media_library_count=1)
            .snapshot()
            .pending_confirmations
        )

    def _read_outcome(self, repository: SQLiteTaskRepository, job_id: str) -> JourneyOutcome:
        job = repository.get_job(job_id)
        self.assertIsNotNone(job)
        task = repository.get_task(job.task_id)
        self.assertIsNotNone(task)
        items = repository.list_items(task.task_id)
        results = repository.list_results(task.task_id)
        item = items[0] if items else None
        result = results[0] if results else None
        task_pending = tuple(
            value
            for value in repository.list_confirmations(status=ConfirmationStatus.PENDING)
            if value.task_id == task.task_id
        )
        evidence_records = (
            repository.list_evidence_for_item(item.item_id) if item is not None else ()
        )
        evidence = evidence_records[0] if evidence_records else None
        evidence_document = evidence.document() if evidence is not None else {}
        plan = evidence_document.get("sections", {}).get("plan", {}).get("value") or {}
        policy = plan.get("configuredPolicy") or {}
        conflicts = tuple(
            (entry.get("type", ""), entry.get("source", ""), entry.get("destination", ""))
            for entry in plan.get("conflicts", [])
        )
        return JourneyOutcome(
            job.status.value,
            job.execute_authorized,
            task.command,
            task.status.value,
            item.status.value if item else None,
            item.destination_path if item else None,
            result.status if result else None,
            result.operation if result else None,
            result.organize_policy_id if result else None,
            len(task_pending),
            evidence.outcome if evidence else None,
            conflicts,
            policy.get("configuredConflictStrategy"),
            plan.get("nextAction"),
        )

    def _queue_preview(self, database: Path, active, *, limit: int | None = None) -> str:
        with SQLiteTaskRepository(database) as repository:
            job = AutomationJobService(
                repository,
                configuration_snapshot_id=active.revision_id,
                configuration_snapshot_digest=active.digest,
            ).submit("preview", limit=limit)
            return job.job_id

    def _seed_pending_conflict(self, repository: SQLiteTaskRepository, label: str) -> str:
        """Create one durable pending ConflictConfirmation so the preview fixture
        starts from a non-zero Dashboard pending-conflict count."""

        coordinator = PersistentTaskCoordinator(repository, repository)
        task = coordinator.create("organize", execute_authorized=True)
        item = coordinator.begin_item(
            task.task_id,
            "source-storage",
            "source",
            f"Incoming/{label}.mkv",
            f"{label}.mkv",
        )
        source = f"Incoming/{label}.mkv"
        target = f"Movies/{label}/{label}.mkv"
        plan = OrganizePlan(
            "source-storage",
            "media-target",
            source,
            target,
            "C",
            "naming-a",
            "classification-a",
            "A",
            operation=PlanOperation.MOVE,
            conflicts=(Conflict(ConflictType.DESTINATION_EXISTS, source, target, "test"),),
            status=PlanStatus.CONFLICT,
            plan_id=f"seed-{label}",
            media_library_root="Movies",
            relative_destination=f"{label}/{label}.mkv",
            source_location=StorageLocation("source-storage", source),
            destination_location=StorageLocation("media-target", target),
        )
        coordinator.wait_for_confirmation(
            item,
            plan,
            OrganizePolicy("A", OrganizeOperationType.MOVE),
        )
        return repository.list_confirmations()[-1].confirmation_id

    @staticmethod
    def _principals():
        return (
            ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ})),
            ResolvedApiPrincipal(
                "operator",
                "operator-token",
                frozenset({ApiPermission.READ, ApiPermission.SUBMIT_DRY_RUN}),
            ),
            ResolvedApiPrincipal(
                "executor",
                "executor-token",
                frozenset(
                    {
                        ApiPermission.READ,
                        ApiPermission.SUBMIT_DRY_RUN,
                        ApiPermission.REMOTE_EXECUTE,
                    }
                ),
            ),
        )

    @staticmethod
    def _job_request(api, document, *, token="executor-token", execution_token=None):
        body = json.dumps(document).encode()
        statuses = []
        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/api/v1/jobs",
            "QUERY_STRING": "",
            "CONTENT_LENGTH": str(len(body)),
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_AUTHORIZATION": f"Bearer {token}",
            "wsgi.input": io.BytesIO(body),
        }
        if execution_token is not None:
            environ["HTTP_X_MEDIAFLOW_EXECUTION_TOKEN"] = execution_token
        response = b"".join(api(environ, lambda status, headers: statuses.append(status)))
        return int(statuses[0].split()[0]), json.loads(response)

    def test_configuration_first_preview_conflict_is_durable_finding(self) -> None:
        """Configuration -> Activate -> Queue first DryRun Preview (a command=preview
        Job) keeps an organize-plan conflict as an inspectable DRY_RUN finding."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # First a clean run discovers the exact planned destination so the
            # second run can install a real current destination collision.
            first_source, first_target, first_db, first_config, first_active = (
                self._managed_environment(root / "clean")
            )
            first_job = self._queue_preview(first_db, first_active)
            self._run_worker(first_config)
            with SQLiteTaskRepository(first_db) as repository:
                first = self._read_outcome(repository, first_job)
            self.assertEqual(first.item_status, TaskItemStatus.DRY_RUN.value)
            self.assertIsNotNone(first.item_destination)
            destination = first.item_destination

            source_root, target_root, database, config, active = self._managed_environment(
                root / "collision", collision_destination=destination
            )
            with SQLiteTaskRepository(database) as repository:
                seeded = self._seed_pending_conflict(repository, "PreExisting")
                pending_before = self._pending_count(repository)
            job_id = self._queue_preview(database, active)
            self._run_worker(config)

            source = source_root / "电影" / "Example.Movie.2024.mkv"
            collision = target_root.joinpath(*destination.split("/"))
            with SQLiteTaskRepository(database) as repository:
                outcome = self._read_outcome(repository, job_id)
                pending_after = self._pending_count(repository)
                job_row = repository.get_job(job_id)
                seeded_row = repository.get_confirmation(seeded)
                waiting = tuple(
                    item
                    for item in repository.list_items(self._task_id(repository, job_id))
                    if item.status is TaskItemStatus.WAITING_CONFIRM
                )
                confirmation_rows = repository.list_confirmations(status=ConfirmationStatus.PENDING)
            self.assertEqual(outcome.job_status, "completed")
            self.assertFalse(outcome.job_execute_authorized)
            self.assertEqual(job_row.configuration_snapshot_id, active.revision_id)
            self.assertEqual(job_row.configuration_snapshot_digest, active.digest)
            self.assertEqual(outcome.task_command, "preview")
            self.assertEqual(outcome.task_status, "completed")
            self.assertEqual(outcome.item_status, TaskItemStatus.DRY_RUN.value)
            self.assertEqual(outcome.item_destination, destination)
            self.assertEqual(outcome.result_status, TaskItemStatus.DRY_RUN.value)
            self.assertEqual(outcome.result_operation, "MOVE")
            self.assertIsNotNone(outcome.result_organize_policy_id)
            self.assertEqual(outcome.evidence_outcome, "dry_run")
            self.assertIn("DESTINATION_EXISTS", {item[0] for item in outcome.evidence_conflicts})
            self.assertEqual(outcome.evidence_conflicts[0][2], destination)
            self.assertEqual(outcome.evidence_strategy, "manual")
            self.assertIn("analysis-only finding", outcome.evidence_next_action)
            # No PENDING ConflictConfirmation, no WAITING_CONFIRM TaskItem and no
            # Dashboard pending-conflict increase.
            self.assertEqual(outcome.pending_confirmations, 0)
            self.assertEqual(pending_before, 1)
            self.assertEqual(pending_after, 1)
            self.assertIsNotNone(seeded_row)
            self.assertEqual(seeded_row.status, ConfirmationStatus.PENDING)
            self.assertEqual(waiting, ())
            self.assertEqual([value.confirmation_id for value in confirmation_rows], [seeded])
            # Zero Storage mutation: source intact and the pre-existing destination
            # collision is byte-for-byte unchanged with no new file written.
            self.assertTrue(source.exists())
            self.assertEqual(source.read_bytes(), b"movie")
            self.assertTrue(collision.exists())
            self.assertEqual(collision.read_bytes(), b"existing-destination")
            target_files = [value for value in target_root.rglob("*") if value.is_file()]
            self.assertEqual(target_files, [collision])

    def _task_id(self, repository: SQLiteTaskRepository, job_id: str) -> str:
        job = repository.get_job(job_id)
        self.assertIsNotNone(job)
        self.assertIsNotNone(job.task_id)
        return job.task_id

    def test_real_organize_conflict_keeps_existing_recovery_path(self) -> None:
        """A real execute-authorized Organize that revalidates into an unresolved
        conflict keeps PENDING ConflictConfirmation / WAITING_CONFIRM and raises the
        Dashboard pending-conflict count without mutating before resolution."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clean_root = root / "clean"
            first_source, first_target, first_db, first_config, first_active = (
                self._managed_environment(clean_root)
            )
            first_job = self._queue_preview(first_db, first_active)
            self._run_worker(first_config)
            with SQLiteTaskRepository(first_db) as repository:
                first = self._read_outcome(repository, first_job)
            destination = first.item_destination
            self.assertIsNotNone(destination)

            source_root, target_root, database, config, active = self._managed_environment(
                root / "collision", collision_destination=destination
            )
            with SQLiteTaskRepository(database) as repository:
                pending_before = self._pending_count(repository)
                service = ExecutionAuthorizationService(
                    repository,
                    configuration_snapshot_id=active.revision_id,
                    configuration_snapshot_digest=active.digest,
                    clock=lambda: datetime.now(UTC),
                )
                issued = service.issue(ttl_seconds=60, max_items=1, actor="tester")
                job = service.submit_organize(issued.token, limit=1)
            self._run_worker(config)

            source = source_root / "电影" / "Example.Movie.2024.mkv"
            collision = target_root.joinpath(*destination.split("/"))
            with SQLiteTaskRepository(database) as repository:
                outcome = self._read_outcome(repository, job.job_id)
                pending_after = self._pending_count(repository)
                job_row = repository.get_job(job.job_id)
                confirmations = repository.list_confirmations(status=ConfirmationStatus.PENDING)
            self.assertEqual(outcome.job_status, "completed")
            self.assertTrue(outcome.job_execute_authorized)
            self.assertEqual(job_row.configuration_snapshot_id, active.revision_id)
            self.assertEqual(job_row.configuration_snapshot_digest, active.digest)
            self.assertEqual(outcome.task_command, "organize")
            self.assertEqual(outcome.task_status, "partial_success")
            self.assertEqual(outcome.item_status, TaskItemStatus.WAITING_CONFIRM.value)
            self.assertEqual(outcome.item_destination, destination)
            self.assertEqual(pending_before, 0)
            self.assertEqual(pending_after, 1)
            self.assertEqual(len(confirmations), 1)
            self.assertEqual(confirmations[0].configured_strategy, "manual")
            # Zero mutation before conflict resolution.
            self.assertTrue(source.exists())
            self.assertEqual(source.read_bytes(), b"movie")
            self.assertTrue(collision.exists())
            self.assertEqual(collision.read_bytes(), b"existing-destination")
            target_files = [value for value in target_root.rglob("*") if value.is_file()]
            self.assertEqual(target_files, [collision])

    def test_preview_finding_is_not_authority_and_stale_source_fails_closed(self) -> None:
        """A Job Preview finding is never execution authority.  If the source
        disappears before a later authorized Organize, the current-state reanalysis
        finds nothing and performs no mutation (no stale plan is blindly executed)."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root, target_root, database, config, active = self._managed_environment(
                root / "preview"
            )
            preview_job = self._queue_preview(database, active)
            self._run_worker(config)
            with SQLiteTaskRepository(database) as repository:
                preview = self._read_outcome(repository, preview_job)
                self.assertEqual(preview.item_status, TaskItemStatus.DRY_RUN.value)
                self.assertEqual(preview.pending_confirmations, 0)
            destination = preview.item_destination
            self.assertIsNotNone(destination)
            source = source_root / "电影" / "Example.Movie.2024.mkv"
            self.assertTrue(source.exists())
            # The source is removed after the Preview: the stale finding must never
            # become execution authority for a later Organize.
            source.unlink()
            with SQLiteTaskRepository(database) as repository:
                service = ExecutionAuthorizationService(
                    repository,
                    configuration_snapshot_id=active.revision_id,
                    configuration_snapshot_digest=active.digest,
                    clock=lambda: datetime.now(UTC),
                )
                issued = service.issue(ttl_seconds=60, max_items=1, actor="tester")
                job = service.submit_organize(issued.token, limit=1)
            self._run_worker(config)
            with SQLiteTaskRepository(database) as repository:
                job_row = repository.get_job(job.job_id)
                self.assertIsNotNone(job_row)
                self.assertEqual(job_row.status.value, "completed")
                self.assertTrue(job_row.execute_authorized)
                task = repository.get_task(job_row.task_id)
                self.assertIsNotNone(task)
                waiting = tuple(
                    item
                    for item in repository.list_items(task.task_id)
                    if item.status is TaskItemStatus.WAITING_CONFIRM
                )
                self.assertEqual(waiting, ())
                self.assertEqual(
                    repository.list_confirmations(status=ConfirmationStatus.PENDING),
                    (),
                )
            self.assertFalse(source.exists())
            self.assertEqual([value for value in target_root.rglob("*") if value.is_file()], [])

    def test_shared_worker_bridge_marks_only_plain_preview_jobs_analysis_only(self) -> None:
        """The shared queued Job Preview bridge (Jobs and Configuration first
        Preview) routes command=preview as analysis-only, while scan and authorized
        organize jobs keep their existing handoff."""

        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = AutomationJobService(repository)
                preview = service.submit("preview", limit=1)
                scan = service.submit("scan", limit=1)
                calls = []

                def fake_main(args, **kwargs):
                    calls.append((args, kwargs))
                    kwargs["stdout"].write("Task ID: task-x\n")
                    return 0

                with patch("mediaflow.final_cli.final_main", side_effect=fake_main):
                    _run_queued_workflow(preview, None, lambda: False)
                    _run_queued_workflow(scan, None, lambda: False)
                self.assertTrue(calls[0][1]["_analysis_only_preview"])
                self.assertNotIn("--execute", calls[0][0])
                self.assertFalse(calls[1][1]["_analysis_only_preview"])
                self.assertNotIn("--execute", calls[1][0])

    def test_api_command_matrix_and_one_shot_organize_authority(self) -> None:
        """Jobs API command matrix: SUBMIT_DRY_RUN cannot organize; real organize
        requires REMOTE_EXECUTE, execute=true and one valid single-use authority."""

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                authorizer = ExecutionAuthorizationService(
                    repository,
                    clock=lambda: datetime.now(UTC),
                    token_factory=lambda: "one-time-secret",
                )
                issued = authorizer.issue(ttl_seconds=60, max_items=1, actor="tester")
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=self._principals(),
                    remote_execution_enabled=True,
                )
                # DryRun-only principal: Organize is denied before any Job.
                status, body = self._job_request(
                    api,
                    {"command": "organize", "execute": True, "limit": 1},
                    token="operator-token",
                    execution_token="one-time-secret",
                )
                self.assertEqual(status, 403)
                self.assertEqual(body["error"]["code"], "forbidden")
                # Missing, wrong and in-body token material fail closed.
                for document, execution_token in (
                    ({"command": "organize", "execute": True, "limit": 1}, None),
                    ({"command": "organize", "execute": True, "limit": 1}, "unknown-token"),
                    (
                        {
                            "command": "organize",
                            "execute": True,
                            "limit": 1,
                            "executionToken": "one-time-secret",
                        },
                        "one-time-secret",
                    ),
                ):
                    status, _ = self._job_request(api, document, execution_token=execution_token)
                    self.assertEqual(status, 400)
                # Unsupported fields and DryRun variants are rejected.
                for document in (
                    {"command": "organize", "execute": True, "limit": 1, "path": "/private"},
                    {"command": "organize", "limit": 1},
                    {"command": "preview", "execute": True, "limit": 1},
                ):
                    status, _ = self._job_request(api, document, execution_token="one-time-secret")
                    self.assertEqual(status, 400)
                self.assertEqual(len(repository.list_jobs()), 0)
                # One valid one-shot authority admits exactly one execute-authorized Job.
                status, created = self._job_request(
                    api,
                    {"command": "organize", "execute": True, "limit": 1},
                    execution_token="one-time-secret",
                )
                self.assertEqual(status, 202)
                self.assertEqual(created["command"], "organize")
                self.assertTrue(created["execute_authorized"])
                self.assertNotIn("one-time-secret", json.dumps(created))
                self.assertEqual(len(repository.list_jobs()), 1)
                # The one-shot authority is consumed and cannot be silently reused.
                status, _ = self._job_request(
                    api,
                    {"command": "organize", "execute": True, "limit": 1},
                    execution_token="one-time-secret",
                )
                self.assertEqual(status, 400)
                self.assertEqual(len(repository.list_jobs()), 1)
                self.assertEqual(
                    repository.get_execution_authorization(
                        issued.authorization.authorization_id
                    ).status.value,
                    "consumed",
                )


if __name__ == "__main__":
    unittest.main()
