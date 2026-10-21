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
from mediaflow.domain.task_persistence import ConfirmationStatus
from mediaflow.final_cli import final_main
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
            ).submit("organize", limit=limit)
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
                # Unsupported fields and missing explicit execute are rejected.
                for document in (
                    {"command": "organize", "execute": True, "limit": 1, "path": "/private"},
                    {"command": "organize", "limit": 1},
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
