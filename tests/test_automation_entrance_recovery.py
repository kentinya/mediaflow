"""Task47.3 round 5 — direct CLI and remote-ticket organizing share one recovery.

The two B blockers this round fixes:

* a direct CLI / remote-ticket organize Task (``trigger=manual``, no Files
  discovery) continues its own saved decision through the same kernel re-entry,
  plan summary, explicit confirmation and same-Task execution the Scheduler due
  / Run once journeys already use — the admission trigger never gates the
  proved organizing work context;
* the legacy ``jobs submit organize`` CLI entrance refuses new work bounded and
  effect-free while naming the usable equivalents, and historical Jobs stay
  readable.

Both journeys run the real production composition end to end: one SQLite file
holds the managed configuration revisions *and* the runtime work exactly like a
deployment, the real CLI parser/dispatch and the real API routes admit the Task,
the real ``final_cli._automatic_task_runner`` (the resident Worker's automatic
branch) advances it, and the real ``ManualTaskEngineWorker`` consumer settles
the confirmed execution.  No synthetic route, no second engine, no user media.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.execution_authorization import ExecutionAuthorizationService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.strategy_test import SyntheticMetadataProvider
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.processing_checkpoint import CheckpointConfiguration, EffectCertainty
from mediaflow.domain.security import (
    ROLE_PERMISSIONS,
    ApiPermission,
    ApiRole,
    ResolvedApiPrincipal,
)
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

ADMIN_TOKEN = "entrance-recovery-admin"
OPERATOR_TOKEN = "entrance-recovery-operator"


class _Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now = self.now + timedelta(seconds=seconds)


@contextmanager
def entrance_journey(
    case,
    *,
    media: str = "One.2001.mkv",
    movie_rule: bool = False,
    capacity: int | None = None,
    candidates: tuple | None = None,
    organize_operation: str | None = None,
):
    """One production-shaped managed layout for one entrance recovery journey.

    The managed revision store and the runtime work share one SQLite file and
    the JSON bootstrap names exactly that database, so the real CLI ``--config``
    resolution, the real pinned Worker reconstruction and the real API binding
    refresh all read the same durable authority a deployment uses.
    """

    root = case.root
    source_root = root / "source"
    target_root = root / "target"
    source_root.mkdir(parents=True, exist_ok=True)
    target_root.mkdir(parents=True, exist_ok=True)
    source = LocalStorage("source", source_root)
    target = LocalStorage("target", target_root)
    database = root / "runtime.sqlite3"
    document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
    document["persistence"] = {"databasePath": str(database)}
    document["historyPath"] = str(root / "history.jsonl")
    document["storages"] = [
        {
            "id": "source",
            "name": "Source",
            "type": "local",
            "rootPath": str(source_root),
            "enabled": True,
        },
        {
            "id": "target",
            "name": "Target",
            "type": "local",
            "rootPath": str(target_root),
            "enabled": True,
        },
    ]
    document["resourceLibraries"] = [
        {
            "id": "library",
            "name": "Library",
            "storageId": "source",
            "storagePath": "",
            "enabled": True,
            "extensions": ["mkv", "mp4"],
            # The deployment's source display root: the direct CLI ``organize
            # <path>`` entrance resolves its configured ResourceLibrary from it.
            "displayRootPath": str(source_root),
        }
    ]
    document["mediaLibraries"] = [
        {
            "id": "movies",
            "name": "Movies",
            "storageId": "target",
            "rootPath": "Organized/Movies",
            "enabled": True,
        },
        {
            "id": "tv",
            "name": "TV",
            "storageId": "target",
            "rootPath": "Organized/TV",
            "enabled": True,
        },
    ]
    document["recognitionRules"] = []
    if organize_operation is not None:
        # The policy the movie rule resolves to, when the journey needs a
        # specific real OrganizerExecutor operation (for example COPY to prove
        # an unverified target write).
        document["organizePolicies"][0]["operation"] = organize_operation
    if movie_rule:
        # One legal movie rule over the whole library, so an organized run can
        # reach the real planning/execution boundary instead of stopping at a
        # waiting-recognition problem.
        document["recognitionRules"] = [
            {
                "id": "movies",
                "name": "Movies",
                "priority": 100,
                "score": 100,
                "stopOnMatch": True,
                "condition": {
                    "field": "extension",
                    "operator": "in",
                    "value": ["mkv", "mp4"],
                },
                "outputRecognitionType": "A",
            }
        ]
    if capacity is not None:
        document["automation"]["maximumActiveJobs"] = capacity
    document["automationTaskDefinitions"] = []
    document["api"]["principals"] = [
        {"id": "admin", "tokenEnv": "MEDIAFLOW_API_TOKEN", "roles": ["admin"], "enabled": True}
    ]
    document["api"]["remoteExecution"] = {"enabled": True, "maximumTtlSeconds": 900}
    config = root / "bootstrap.json"
    config.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    provider_registry = MetadataProviderRegistry(
        (
            SyntheticMetadataProvider(
                candidates
                if candidates is not None
                else (
                    MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),
                    MediaCandidate("tmdb", "2", MediaType.MOVIE, "Two", year=2002),
                )
            ),
        )
    )
    with SQLiteConfigurationRepository(database) as configuration_repository:
        managed = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=str(database),
        )
        draft = managed.import_draft(document, actor="admin")
        validated = managed.validate(draft.revision_id, actor="admin")
        if validated.status.value != "validated":
            raise AssertionError(validated.validation_errors)
        revision = managed.activate(
            validated.revision_id, expected_version=validated.version, actor="admin"
        )
        from mediaflow.infrastructure.runtime_configuration import (
            load_managed_runtime_configuration,
            with_managed_snapshot,
        )

        runtime = with_managed_snapshot(
            load_managed_runtime_configuration(
                revision.document,
                bootstrap_database_path=managed.bootstrap_database_path,
            ),
            snapshot_id=revision.revision_id,
            digest=revision.digest,
            version=revision.version,
        )
        with SQLiteTaskRepository(str(database)) as repository:
            intents = ManualOrganizeIntentService(
                repository,
                managed,
                runtime_resolver=lambda snapshot_id, digest: runtime,
                storage_factory=lambda value, ids: {"source": source, "target": target},
            )
            previews = ManualOrganizePreviewService(
                repository,
                intents,
                configuration=runtime,
                storages={"source": source, "target": target},
                providers=provider_registry,
                clock=case.clock,
            )
            api = MediaFlowApi(
                repository,
                None,
                principals=(
                    ResolvedApiPrincipal("admin", ADMIN_TOKEN, frozenset(ApiPermission)),
                    ResolvedApiPrincipal(
                        "operator", OPERATOR_TOKEN, ROLE_PERMISSIONS[ApiRole.OPERATOR]
                    ),
                ),
                configuration_service=managed,
                bootstrap_document=document,
                manual_intent_service=intents,
                manual_preview_service=previews,
                metadata_provider_registry_factory=lambda ids: provider_registry,
            )
            yield SimpleNamespace(
                api=api,
                repository=repository,
                managed=managed,
                runtime=runtime,
                intents=intents,
                previews=previews,
                clock=case.clock,
                source_root=source_root,
                target_root=target_root,
                revision=revision,
                config=config,
                provider_registry=provider_registry,
            )


class EntranceRecoveryJourneyTests(unittest.TestCase):
    """The manual organizing entrances complete their own four-type recovery."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.clock = _Clock()
        self.environment = patch.dict(
            os.environ,
            {"TMDB_ACCESS_TOKEN": "sentinel-tmdb", "MEDIAFLOW_API_TOKEN": ADMIN_TOKEN},
            clear=False,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def media(self, relative: str) -> Path:
        path = self.root / "source" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"m" * 512)
        stamp = (self.clock.now - timedelta(hours=1)).timestamp()
        os.utime(path, (stamp, stamp))
        return path

    def request(self, value, method, path, body=None, *, token=ADMIN_TOKEN, headers=None):
        payload = b"" if body is None else json.dumps(body).encode("utf-8")
        statuses: list[str] = []
        path_info, _, query_string = path.partition("?")
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path_info,
            "QUERY_STRING": query_string,
            "CONTENT_LENGTH": str(len(payload)),
            "wsgi.input": io.BytesIO(payload),
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_AUTHORIZATION": f"Bearer {token}",
        }
        environ.update(headers or {})
        result = b"".join(value.api(environ, lambda status, _h: statuses.append(status)))
        return int(statuses[0].split()[0]), (json.loads(result) if result else {})

    def _run_resident_worker(self, value, *, prefix: str):
        """One real resident Worker pass over the production automatic routing.

        The consumer is the production ``ManualTaskEngineWorker``; its automatic
        branch is the production ``final_cli._automatic_task_runner`` that
        reconstructs the Task's admitted pin and routes remote/direct organize
        admissions and continuation passes through the shared pipeline.
        """

        from mediaflow.application.manual_organize_execution import (
            ManualOrganizeExecutionService,
        )
        from mediaflow.application.manual_task_engine import ManualTaskEngineWorker
        from mediaflow.application.task_scheduling import TaskSchedulingService
        from mediaflow.final_cli import _automatic_task_runner

        scheduling = TaskSchedulingService(value.repository, capacity=100)
        runner = _automatic_task_runner(value.repository, str(value.config), scheduling)
        execution = ManualOrganizeExecutionService(
            value.repository,
            value.previews,
            value.intents,
            configuration=value.runtime,
            storages={
                "source": LocalStorage("source", value.source_root),
                "target": LocalStorage("target", value.target_root),
            },
            clock=value.clock,
        )
        worker_id = f"{prefix}-{len(value.repository.list_tasks())}"
        value.repository.register_worker(
            worker_id,
            worker_id,
            5.0,
            ("organize",),
            None,
            None,
            SCHEMA_VERSION,
            value.clock.now,
        )
        worker = ManualTaskEngineWorker(
            value.repository,
            scheduling,
            None,
            execution,
            worker_id=worker_id,
            clock=value.clock,
            automatic_runner=runner,
        )
        with patch(
            "mediaflow.final_cli.metadata_provider_registry_from_environment",
            return_value=value.provider_registry,
        ):
            settled = worker.run_next()
        value.repository.stop_worker(worker_id, value.clock.now)
        return settled

    def _save_recognition_decision_and_continue(self, value, task_id, item_id):
        """The real Task Center recovery chain over the live API routes."""

        route = f"/api/v1/tasks/{task_id}/items/{item_id}/recovery"
        status, detail = self.request(value, "GET", route)
        self.assertEqual(200, status, detail)
        self.assertEqual("business_problem", detail["recoveryKind"])
        status, decided = self.request(
            value,
            "POST",
            route + "/decision",
            {
                "kind": "recognition",
                "recognitionTypeId": "A",
                "expectedCheckpointVersion": detail["checkpoint"]["checkpoint_version"],
            },
        )
        self.assertEqual(200, status, decided)
        status, continued = self.request(
            value,
            "POST",
            route + "/continue",
            {"expectedCheckpointVersion": decided["checkpoint"]["checkpoint_version"]},
        )
        return status, continued, decided, detail

    def _confirm_ready_subset(self, value, task_id, item_id, *, actor_token=ADMIN_TOKEN):
        status, detail = self.request(
            value, "GET", f"/api/v1/tasks/{task_id}/items/{item_id}/recovery"
        )
        self.assertEqual(200, status, detail)
        preparation = detail["manualRecoveryPreparation"]
        self.assertIsNotNone(preparation, detail)
        self.assertEqual("prepared", preparation["status"])
        status, preview = self.request(
            value, "GET", f"/api/v1/manual-previews/{preparation['preview_id']}"
        )
        self.assertEqual(200, status, preview)
        ready = [entry["itemId"] for entry in preview["items"] if entry["status"] == "previewed"]
        self.assertEqual(1, len(ready), preview)
        status, confirmed = self.request(
            value,
            "POST",
            f"/api/v1/manual-recovery-preparations/{preparation['preparation_id']}/confirm",
            {"itemIds": ready, "confirmation": True},
            token=actor_token,
        )
        return status, confirmed, preparation, ready

    def test_direct_cli_decision_completes_summary_confirm_execution_on_one_task(self):
        """The direct CLI Task's saved decision finishes on the same Task."""

        self.media("One.2001.mkv")
        with entrance_journey(self) as value:
            output, errors = io.StringIO(), io.StringIO()
            with patch(
                "mediaflow.final_cli.metadata_provider_registry_from_environment",
                return_value=value.provider_registry,
            ):
                code = final_main(
                    ["--config", str(value.config), "organize", "--execute", "--limit", "5"],
                    stdout=output,
                    stderr=errors,
                )
            self.assertEqual(0, code, errors.getvalue())
            (task,) = value.repository.list_tasks()
            state = value.repository.get_task_scheduling(task.task_id)
            self.assertEqual("manual", state.admission_trigger.value)
            self.assertEqual("cli", state.admission_principal)
            display = value.repository.get_run_display_context(task.task_id)
            self.assertEqual("direct-organize", display.origin_kind)
            (item,) = value.repository.list_items(task.task_id)
            self.assertEqual("waiting_recognition", item.status.value)
            self.assertEqual((), value.repository.list_jobs())
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertTrue((value.source_root / "One.2001.mkv").exists())

            status, continued, decided, _detail = self._save_recognition_decision_and_continue(
                value, task.task_id, item.item_id
            )
            self.assertEqual(202, status, continued)
            self.assertEqual(task.task_id, continued["nativeAnalysis"]["taskId"])
            self.assertNotIn("discoveryId", continued["nativeAnalysis"])
            state = value.repository.get_task_scheduling(task.task_id)
            self.assertEqual("queued", state.queue_state.value)
            self.assertEqual(1, value.repository.count_scheduled_capacity_use())
            self.assertEqual("admin", state.continuation_actor)
            self.assertEqual((), value.repository.list_jobs())
            self.assertTrue((value.source_root / "One.2001.mkv").exists())
            self.assertFalse(
                any((value.target_root / "Organized").rglob("*.mkv")),
                "the re-analysis must stay zero-mutation",
            )

            # A duplicate continue while the analysis is queued changes nothing.
            status, repeat = self.request(
                value,
                "POST",
                f"/api/v1/tasks/{task.task_id}/items/{item.item_id}/recovery/continue",
                {"expectedCheckpointVersion": decided["checkpoint"]["checkpoint_version"]},
            )
            self.assertEqual(409, status, repeat)
            self.assertEqual(1, value.repository.count_scheduled_capacity_use())

            settled = self._run_resident_worker(value, prefix="cli-continuation")
            self.assertIsNotNone(settled)
            (item,) = value.repository.list_items(task.task_id)
            self.assertEqual("waiting_confirm", item.status.value, item)
            self.assertEqual("continuation_planned", item.stage)
            state = value.repository.get_task_scheduling(task.task_id)
            self.assertEqual("waiting_human", state.queue_state.value)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertTrue((value.source_root / "One.2001.mkv").exists())

            status, detail = self.request(
                value, "GET", f"/api/v1/tasks/{task.task_id}/items/{item.item_id}/recovery"
            )
            self.assertEqual(200, status, detail)
            preparation = detail["manualRecoveryPreparation"]
            self.assertIsNotNone(preparation, detail)
            # The summary belongs to the authenticated operator who continued
            # the analysis; the CLI admission principal stays separate provenance.
            self.assertEqual("admin", preparation["actor"])
            self.assertEqual("cli", state.admission_principal)
            self.assertTrue(detail["manualRecoveryAvailable"])

            status, refused = self.request(
                value,
                "POST",
                f"/api/v1/manual-recovery-preparations/{preparation['preparation_id']}/confirm",
                {"itemIds": ["any"], "confirmation": True},
                token=OPERATOR_TOKEN,
            )
            self.assertEqual(403, status, refused)
            self.assertEqual("preparation_actor_mismatch", refused["error"]["code"])

            status, confirmed, preparation, ready = self._confirm_ready_subset(
                value, task.task_id, item.item_id
            )
            self.assertEqual(202, status, confirmed)
            self.assertEqual(task.task_id, confirmed["taskId"], confirmed)
            self.assertEqual((), value.repository.list_jobs())

            settled = self._run_resident_worker(value, prefix="cli-execution")
            self.assertIsNotNone(settled)
            self.assertEqual("completed", settled.status.value, settled.error)
            self.assertFalse((value.source_root / "One.2001.mkv").exists())
            organized = list((value.target_root / "Organized" / "Movies").rglob("*.mkv"))
            self.assertEqual(1, len(organized), organized)
            results = value.repository.list_results(task.task_id)
            self.assertEqual(1, len(results), results)
            self.assertEqual("SUCCESS", results[0].status)
            state = value.repository.get_task_scheduling(task.task_id)
            self.assertEqual("settled", state.queue_state.value)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertEqual((), value.repository.list_jobs())

            # The original execution facts survive the reload; the confirmed
            # summary reads back with its linked execution.
            status, detail = self.request(
                value, "GET", f"/api/v1/tasks/{task.task_id}/items/{item.item_id}/recovery"
            )
            self.assertEqual(200, status, detail)
            confirmed_summary = detail["manualRecoveryPreparation"]
            self.assertIsNotNone(confirmed_summary, detail)
            self.assertEqual("confirmed", confirmed_summary["status"])
            self.assertEqual(confirmed["executionId"], confirmed_summary["execution_id"])

    def test_remote_ticket_decision_completes_the_same_recovery_on_one_task(self):
        """The remote-ticket Task's saved decision finishes on the same Task."""

        self.media("One.2001.mkv")
        with entrance_journey(self) as value:
            issued = ExecutionAuthorizationService(
                value.repository,
                maximum_ttl_seconds=900,
                token_factory=lambda: "one-time-entrance-ticket",
            ).issue(ttl_seconds=300, max_items=5, actor="admin")
            status, admitted = self.request(
                value,
                "POST",
                "/api/v1/jobs",
                {"command": "organize", "execute": True, "limit": 5},
                headers={"HTTP_X_MEDIAFLOW_EXECUTION_TOKEN": "one-time-entrance-ticket"},
            )
            self.assertEqual(202, status, admitted)
            self.assertEqual("task_engine", admitted["executionMethod"], admitted)
            task_id = admitted["taskId"]
            task = value.repository.get_task(task_id)
            self.assertIsNotNone(task)
            self.assertTrue(task.execute_authorized)
            self.assertEqual(value.revision.revision_id, task.configuration_snapshot_id, task)
            state = value.repository.get_task_scheduling(task_id)
            self.assertEqual("manual", state.admission_trigger.value)
            self.assertEqual("remote-execution", state.admission_principal)
            display = value.repository.get_run_display_context(task_id)
            self.assertEqual("remote-organize", display.origin_kind)
            self.assertEqual((), value.repository.list_jobs())
            self.assertEqual(
                "consumed",
                value.repository.get_execution_authorization(
                    issued.authorization.authorization_id
                ).status.value,
            )

            settled = self._run_resident_worker(value, prefix="remote-initial")
            self.assertIsNotNone(settled)
            (item,) = value.repository.list_items(task_id)
            self.assertEqual("waiting_recognition", item.status.value, item)
            self.assertEqual((), value.repository.list_jobs())
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())

            status, continued, decided, _detail = self._save_recognition_decision_and_continue(
                value, task_id, item.item_id
            )
            self.assertEqual(202, status, continued)
            self.assertEqual(task_id, continued["nativeAnalysis"]["taskId"])
            state = value.repository.get_task_scheduling(task_id)
            self.assertEqual("queued", state.queue_state.value)
            self.assertEqual("admin", state.continuation_actor)
            self.assertEqual((), value.repository.list_jobs())

            settled = self._run_resident_worker(value, prefix="remote-continuation")
            self.assertIsNotNone(settled)
            (item,) = value.repository.list_items(task_id)
            self.assertEqual("waiting_confirm", item.status.value, item)
            state = value.repository.get_task_scheduling(task_id)
            self.assertEqual("waiting_human", state.queue_state.value)

            status, refused = self.request(
                value,
                "POST",
                "/api/v1/jobs",
                {"command": "organize", "execute": True, "limit": 5},
                headers={"HTTP_X_MEDIAFLOW_EXECUTION_TOKEN": "one-time-entrance-ticket"},
            )
            self.assertEqual(400, status, refused)
            self.assertEqual((), value.repository.list_jobs())

            status, confirmed, preparation, ready = self._confirm_ready_subset(
                value, task_id, item.item_id
            )
            self.assertEqual(202, status, confirmed)
            self.assertEqual(task_id, confirmed["taskId"], confirmed)
            self.assertEqual((), value.repository.list_jobs())

            settled = self._run_resident_worker(value, prefix="remote-execution")
            self.assertIsNotNone(settled)
            self.assertEqual("completed", settled.status.value, settled.error)
            self.assertFalse((value.source_root / "One.2001.mkv").exists())
            organized = list((value.target_root / "Organized" / "Movies").rglob("*.mkv"))
            self.assertEqual(1, len(organized), organized)
            results = value.repository.list_results(task_id)
            self.assertEqual(1, len(results), results)
            self.assertEqual("SUCCESS", results[0].status)
            state = value.repository.get_task_scheduling(task_id)
            self.assertEqual("settled", state.queue_state.value)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertEqual((), value.repository.list_jobs())

    def test_retry_failed_execute_shares_the_kernel_queue_and_capacity(self):
        """The CLI failure retry enters the shared queue; a full queue refuses it.

        The real gap this pins: the failure retry used to create its Task with
        the generic coordinator and move files directly, bypassing the shared
        capacity every other entrance honors.  Now the retried execution is
        admitted by the same kernel — refused at full capacity before any new
        Task row, source-lock release or file effect — and a later explicit
        retry with free capacity runs under the live kernel claim and moves the
        file exactly once, while the original work keeps its own failed facts.
        """

        source = self.media("One.2001.mkv")
        with entrance_journey(
            self,
            movie_rule=True,
            capacity=1,
            candidates=(MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),),
        ) as value:
            from mediaflow.application.organizer import OrganizerExecutor

            class _ExplodingExecutor(OrganizerExecutor):
                def execute(self, plan, storages, **kwargs):
                    raise RuntimeError("injected executor failure before any mutation")

            def with_provider():
                return patch(
                    "mediaflow.final_cli.metadata_provider_registry_from_environment",
                    return_value=value.provider_registry,
                )

            def organize_execute():
                output, errors = io.StringIO(), io.StringIO()
                with with_provider():
                    code = final_main(
                        [
                            "--config",
                            str(value.config),
                            "organize",
                            str(source),
                            "--execute",
                            "--limit",
                            "5",
                        ],
                        stdout=output,
                        stderr=errors,
                    )
                return code, output.getvalue(), errors.getvalue()

            def retry_failed(*extra):
                output, errors = io.StringIO(), io.StringIO()
                with with_provider():
                    code = final_main(
                        [
                            "--config",
                            str(value.config),
                            "tasks",
                            "retry-failed",
                            failed_task.task_id,
                            *extra,
                        ],
                        stdout=output,
                        stderr=errors,
                    )
                return code, output.getvalue(), errors.getvalue()

            # 1. A real admitted execution fails before any mutation at the real
            #    OrganizerExecutor boundary; the source stays in place.
            output, errors = io.StringIO(), io.StringIO()
            with (
                with_provider(),
                patch("mediaflow.final_cli.OrganizerExecutor", _ExplodingExecutor),
            ):
                code = final_main(
                    [
                        "--config",
                        str(value.config),
                        "organize",
                        str(source),
                        "--execute",
                        "--limit",
                        "5",
                    ],
                    stdout=output,
                    stderr=errors,
                )
            self.assertEqual(1, code, errors.getvalue())
            (failed_task,) = value.repository.list_tasks()
            (failed_item,) = value.repository.list_items(failed_task.task_id)
            self.assertEqual("failed", failed_item.status.value, failed_item)
            self.assertEqual("failed", failed_task.status.value, failed_task)
            self.assertTrue(source.exists())
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertIsNotNone(value.repository.get_task_scheduling(failed_task.task_id))

            # 2. One legitimately admitted remote organize Task fills the shared
            #    capacity of one; nothing runs it yet, so it keeps its slot.
            issued = ExecutionAuthorizationService(
                value.repository,
                maximum_ttl_seconds=900,
                token_factory=lambda: "one-time-queue-ticket",
            ).issue(ttl_seconds=300, max_items=5, actor="admin")
            status, admitted = self.request(
                value,
                "POST",
                "/api/v1/jobs",
                {"command": "organize", "execute": True, "limit": 5},
                headers={"HTTP_X_MEDIAFLOW_EXECUTION_TOKEN": "one-time-queue-ticket"},
            )
            self.assertEqual(202, status, admitted)
            queued_task_id = admitted["taskId"]
            self.assertEqual(
                "consumed",
                value.repository.get_execution_authorization(
                    issued.authorization.authorization_id
                ).status.value,
            )
            self.assertEqual(1, value.repository.count_scheduled_capacity_use())

            # 3. The contrast the finding named: the ordinary direct organize
            #    already refuses at full capacity.
            code, _output, errors = organize_execute()
            self.assertEqual(2, code)
            self.assertIn("queue is full", errors)
            self.assertEqual(1, value.repository.count_scheduled_capacity_use())

            # 4. The pinned refusal: the failure retry refuses the same way,
            #    before any new Task, lock release or file effect.
            code, _output, errors = retry_failed("--execute")
            self.assertEqual(2, code)
            self.assertIn("queue is full", errors)
            self.assertEqual(
                2,
                len(value.repository.list_tasks()),
                "no retry Task may be admitted at full capacity",
            )
            (item_after_refusal,) = value.repository.list_items(failed_task.task_id)
            self.assertEqual(failed_item, item_after_refusal)
            self.assertTrue(source.exists())
            self.assertEqual(1, value.repository.count_scheduled_capacity_use())

            # 5. Free the capacity the way an operator would: cancel the queued
            #    remote work at its own safe boundary.
            queued = value.repository.get_task(queued_task_id)
            status, cancelled = self.request(
                value,
                "POST",
                f"/api/v1/tasks/{queued_task_id}/cancel",
                {"expectedUpdatedAt": queued.updated_at.isoformat()},
            )
            self.assertEqual(200, status, cancelled)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())

            # 6. The explicit retry now enters the shared engine and completes.
            code, output, errors = retry_failed("--execute")
            self.assertEqual(0, code, errors)
            self.assertIn("Moved: 1", output)
            tasks = value.repository.list_tasks()
            self.assertEqual(3, len(tasks), tasks)
            (retry_task,) = (
                task for task in tasks if task.task_id not in {failed_task.task_id, queued_task_id}
            )
            self.assertEqual(f"retry-failed:{failed_task.task_id}", retry_task.command)
            self.assertEqual("completed", retry_task.status.value, retry_task.error)
            # The original work's exact pin, scope and bound carry over unchanged.
            self.assertEqual(
                failed_task.configuration_snapshot_id, retry_task.configuration_snapshot_id
            )
            self.assertEqual(
                failed_task.configuration_snapshot_digest, retry_task.configuration_snapshot_digest
            )
            self.assertEqual(failed_task.scope_path, retry_task.scope_path)
            self.assertEqual(failed_task.item_limit, retry_task.item_limit)
            self.assertEqual(5, retry_task.item_limit)
            self.assertTrue(retry_task.execute_authorized)
            state = value.repository.get_task_scheduling(retry_task.task_id)
            self.assertIsNotNone(state, "the retry must own kernel scheduling")
            self.assertEqual("settled", state.queue_state.value)
            self.assertEqual("manual", state.admission_trigger.value)
            self.assertEqual("cli", state.admission_principal)
            display = value.repository.get_run_display_context(retry_task.task_id)
            self.assertEqual("cli-retry-failed", display.origin_kind)
            self.assertFalse(source.exists())
            organized = list((value.target_root / "Organized" / "Movies").rglob("*.mkv"))
            self.assertEqual(1, len(organized), organized)
            results = value.repository.list_results(retry_task.task_id)
            self.assertEqual(1, len(results), results)
            self.assertEqual("success", results[0].status)
            # The original work keeps its own failed facts; the retry is its own
            # execution record and the source was moved exactly once.
            original_after = value.repository.get_task(failed_task.task_id)
            self.assertEqual("failed", original_after.status.value)
            original_results = value.repository.list_results(failed_task.task_id)
            self.assertEqual(1, len(original_results), original_results)
            self.assertEqual("failed", original_results[0].status)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertEqual((), value.repository.list_jobs())

    def test_retry_failed_execute_refuses_the_original_unverified_mutation(self):
        """A retry never re-executes a file whose last mutation is unverified.

        Round 1 runs the real COPY pipeline into the real LocalStorage and
        injects the lost write response at the actual ``LocalStorage.write``
        boundary, so the durable partial/attempted-unverified Result and the
        original Task's in-flight mutation marker are persisted by the
        production path — never by a synthetic row.  Round 2 proves the
        explicit ``retry-failed --execute`` refuses that file: no Provider or
        Storage mutation, no executable new Task, no release of the original
        occupation and no cleared mutation marker.
        """

        source = self.media("One.2001.mkv")
        with entrance_journey(
            self,
            movie_rule=True,
            organize_operation="COPY",
            candidates=(MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),),
        ) as value:
            provider = value.provider_registry.resolve("tmdb")

            def with_provider():
                return patch(
                    "mediaflow.final_cli.metadata_provider_registry_from_environment",
                    return_value=value.provider_registry,
                )

            writes: list[str] = []
            real_write = LocalStorage.write

            def lost_write(storage, path, *args, **kwargs):
                writes.append(str(path))
                raise TimeoutError("injected Storage write response lost after dispatch")

            def observed_write(storage, path, *args, **kwargs):
                writes.append(str(path))
                return real_write(storage, path, *args, **kwargs)

            # Round 1: the real OrganizerExecutor dispatches the target write
            # and the response is lost; the production path persists the
            # uncertain-effect evidence itself.
            output, errors = io.StringIO(), io.StringIO()
            with with_provider(), patch.object(LocalStorage, "write", lost_write):
                code = final_main(
                    [
                        "--config",
                        str(value.config),
                        "organize",
                        str(source),
                        "--execute",
                        "--limit",
                        "5",
                    ],
                    stdout=output,
                    stderr=errors,
                )
            self.assertEqual(2, code, errors.getvalue())
            self.assertIn("unverified in-flight mutation", errors.getvalue(), errors.getvalue())
            self.assertTrue(writes, "the real Executor must dispatch one Storage write")
            self.assertTrue(source.exists())
            (original,) = value.repository.list_tasks()
            (item,) = value.repository.list_items(original.task_id)
            self.assertEqual("partial", item.status.value, item)
            (result,) = value.repository.list_results(original.task_id)
            self.assertEqual("attempted_unverified", result.effect_certainty, result)
            self.assertTrue(result.uncertain_effects, result)
            state = value.repository.get_task_scheduling(original.task_id)
            self.assertTrue(state.mutation_in_flight, state)
            self.assertEqual(item.item_id, state.mutation_item_id)
            self.assertFalse(
                any((value.target_root / "Organized").rglob("*.mkv")),
                "the lost write must not have produced a target file",
            )
            provider_calls = provider.calls
            original_result = result
            original_item = item
            writes.clear()

            # Round 2: the explicit retry refuses the file with zero effects.
            output, errors = io.StringIO(), io.StringIO()
            with with_provider(), patch.object(LocalStorage, "write", observed_write):
                code = final_main(
                    [
                        "--config",
                        str(value.config),
                        "tasks",
                        "retry-failed",
                        original.task_id,
                        "--execute",
                    ],
                    stdout=output,
                    stderr=errors,
                )
            self.assertEqual(2, code, errors.getvalue())
            self.assertIn("no retry run was started", errors.getvalue(), errors.getvalue())
            self.assertIn("could not be verified", errors.getvalue(), errors.getvalue())
            self.assertIn("One.2001.mkv", errors.getvalue(), errors.getvalue())
            self.assertEqual(
                [],
                writes,
                "the refused retry must not dispatch any Storage write",
            )
            self.assertEqual(
                provider_calls,
                provider.calls,
                "the refused retry must not query the metadata provider",
            )
            self.assertEqual(
                1,
                len(value.repository.list_tasks()),
                "no executable retry Task may be admitted for the blocked file",
            )
            (item_after,) = value.repository.list_items(original.task_id)
            self.assertEqual(original_item, item_after, "the original record stays as it was")
            (result_after,) = value.repository.list_results(original.task_id)
            self.assertEqual(
                original_result, result_after, "the uncertain Result is never rewritten"
            )
            state_after = value.repository.get_task_scheduling(original.task_id)
            self.assertTrue(
                state_after.mutation_in_flight,
                "the original uncertain boundary is never cleared by a refused retry",
            )
            self.assertEqual(original_item.item_id, state_after.mutation_item_id)
            owner = value.repository.find_owned_source_work(
                storage_id="source",
                source_path="One.2001.mkv",
                storage_path="One.2001.mkv",
                resource_library_id="library",
            )
            self.assertIsNotNone(owner, "the original work keeps its source occupation")
            self.assertEqual(original.task_id, owner["taskId"])
            self.assertTrue(source.exists())
            self.assertFalse(
                any((value.target_root / "Organized").rglob("*.mkv")),
                "the refused retry must not write the target",
            )

    def test_retry_failed_execute_retries_only_the_proven_zero_effect_sibling(self):
        """An executed retry partitions the batch by each file's own evidence.

        One run leaves One with a proven zero-effect failure (the executor
        stopped before any mutation) and Two with an unverified target write.
        The explicit retry then executes exactly the eligible sibling: One is
        admitted into one kernel retry Task and really copied, while Two keeps
        its original record, its source occupation and the Task's in-flight
        mutation marker untouched.
        """

        self.media("One.2001.mkv")
        self.media("Two.2002.mkv")
        with entrance_journey(
            self,
            movie_rule=True,
            organize_operation="COPY",
            candidates=(
                MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),
                MediaCandidate("tmdb", "2", MediaType.MOVIE, "Two", year=2002),
            ),
        ) as value:
            from mediaflow.application.organizer import OrganizerExecutor

            class _OneFailsBeforeMutation(OrganizerExecutor):
                """The real executor, stopped before any mutation for One only."""

                def execute(self, plan, storages, **kwargs):
                    if "One" in plan.source:
                        raise RuntimeError("injected failure before any mutation for One")
                    return super().execute(plan, storages, **kwargs)

            def with_provider():
                return patch(
                    "mediaflow.final_cli.metadata_provider_registry_from_environment",
                    return_value=value.provider_registry,
                )

            writes: list[str] = []
            real_write = LocalStorage.write

            def selective_write(storage, path, *args, **kwargs):
                writes.append(str(path))
                if "Two" in str(path):
                    raise TimeoutError("injected Storage write response lost after dispatch")
                return real_write(storage, path, *args, **kwargs)

            # One is processed first: its pre-mutation failure publishes a
            # proven zero-effect outcome and releases the Task's mutation
            # boundary, then Two's real write loses its response and keeps the
            # durable uncertain-effect boundary for the original Task.
            output, errors = io.StringIO(), io.StringIO()
            with (
                with_provider(),
                patch.object(LocalStorage, "write", selective_write),
                patch("mediaflow.final_cli.OrganizerExecutor", _OneFailsBeforeMutation),
            ):
                code = final_main(
                    [
                        "--config",
                        str(value.config),
                        "organize",
                        str(value.source_root),
                        "--execute",
                        "--limit",
                        "5",
                    ],
                    stdout=output,
                    stderr=errors,
                )
            self.assertEqual(2, code, errors.getvalue())
            (original,) = value.repository.list_tasks()
            items = {
                item.source_path: item for item in value.repository.list_items(original.task_id)
            }
            self.assertEqual({"One.2001.mkv", "Two.2002.mkv"}, set(items), items)
            self.assertEqual("failed", items["One.2001.mkv"].status.value, items)
            self.assertEqual("partial", items["Two.2002.mkv"].status.value, items)
            results = {
                result.source_path: result
                for result in value.repository.list_results(original.task_id)
            }
            self.assertEqual("none", results["One.2001.mkv"].effect_certainty)
            self.assertFalse(results["One.2001.mkv"].completed_operations)
            self.assertFalse(results["One.2001.mkv"].primary_completed)
            self.assertEqual("attempted_unverified", results["Two.2002.mkv"].effect_certainty)
            state = value.repository.get_task_scheduling(original.task_id)
            self.assertTrue(state.mutation_in_flight, state)
            self.assertEqual(items["Two.2002.mkv"].item_id, state.mutation_item_id)
            two_item = items["Two.2002.mkv"]
            two_result = results["Two.2002.mkv"]
            writes.clear()

            output, errors = io.StringIO(), io.StringIO()
            with with_provider(), patch.object(LocalStorage, "write", selective_write):
                code = final_main(
                    [
                        "--config",
                        str(value.config),
                        "tasks",
                        "retry-failed",
                        original.task_id,
                        "--execute",
                    ],
                    stdout=output,
                    stderr=errors,
                )
            self.assertEqual(0, code, errors.getvalue())
            # The refused sibling is reported on the real operator output.
            self.assertIn("NOT RETRIED", output.getvalue(), output.getvalue())
            self.assertIn("Two.2002.mkv", output.getvalue(), output.getvalue())
            retry_tasks = [
                task for task in value.repository.list_tasks() if task.task_id != original.task_id
            ]
            self.assertEqual(1, len(retry_tasks), retry_tasks)
            retry_items = value.repository.list_items(retry_tasks[0].task_id)
            self.assertEqual(
                {"One.2001.mkv"}, {item.source_path for item in retry_items}, retry_items
            )
            # Only the eligible sibling was written; Two's target write never ran.
            self.assertEqual(
                0,
                len([path for path in writes if "Two" in path]),
                writes,
            )
            organized = sorted(
                str(path.relative_to(value.target_root))
                for path in (value.target_root / "Organized" / "Movies").rglob("*.mkv")
            )
            self.assertEqual(1, len(organized), organized)
            self.assertIn("One", organized[0], organized)
            # Two keeps its original record, occupation and uncertain boundary.
            self.assertTrue((value.source_root / "Two.2002.mkv").exists())
            (two_after,) = (
                item
                for item in value.repository.list_items(original.task_id)
                if item.source_path == "Two.2002.mkv"
            )
            self.assertEqual(two_item, two_after)
            (two_result_after,) = (
                result
                for result in value.repository.list_results(original.task_id)
                if result.source_path == "Two.2002.mkv"
            )
            self.assertEqual(two_result, two_result_after)
            state_after = value.repository.get_task_scheduling(original.task_id)
            self.assertTrue(state_after.mutation_in_flight, state_after)
            self.assertEqual(two_item.item_id, state_after.mutation_item_id)
            owner = value.repository.find_owned_source_work(
                storage_id="source",
                source_path="Two.2002.mkv",
                storage_path="Two.2002.mkv",
                resource_library_id="library",
            )
            self.assertIsNotNone(owner, "the blocked file keeps its original source occupation")
            self.assertEqual(original.task_id, owner["taskId"])
            # The retry Task released its own slot; the original Task keeps its
            # documented retained slot while its unverified mutation boundary
            # stays in flight.
            self.assertEqual(1, value.repository.count_scheduled_capacity_use())

    def test_retry_failed_without_execute_stays_zero_mutation_analysis(self):
        """The retry without ``--execute`` keeps its analysis-only semantics."""

        source = self.media("One.2001.mkv")
        with entrance_journey(
            self,
            movie_rule=True,
            candidates=(MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),),
        ) as value:
            from mediaflow.application.organizer import OrganizerExecutor

            class _ExplodingExecutor(OrganizerExecutor):
                def execute(self, plan, storages, **kwargs):
                    raise RuntimeError("injected executor failure before any mutation")

            with (
                patch(
                    "mediaflow.final_cli.metadata_provider_registry_from_environment",
                    return_value=value.provider_registry,
                ),
                patch("mediaflow.final_cli.OrganizerExecutor", _ExplodingExecutor),
            ):
                code = final_main(
                    [
                        "--config",
                        str(value.config),
                        "organize",
                        str(source),
                        "--execute",
                        "--limit",
                        "5",
                    ],
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )
            self.assertEqual(1, code)
            (failed_task,) = value.repository.list_tasks()

            output, errors = io.StringIO(), io.StringIO()
            with patch(
                "mediaflow.final_cli.metadata_provider_registry_from_environment",
                return_value=value.provider_registry,
            ):
                code = final_main(
                    [
                        "--config",
                        str(value.config),
                        "tasks",
                        "retry-failed",
                        failed_task.task_id,
                    ],
                    stdout=output,
                    stderr=errors,
                )
            self.assertEqual(0, code, errors.getvalue())
            self.assertIn("Mode: DRY_RUN", output.getvalue())
            self.assertIn("Moved: 0", output.getvalue())
            self.assertTrue(source.exists())
            self.assertEqual((), tuple((value.target_root / "Organized").rglob("*")))
            # A zero-mutation re-analysis keeps its original analysis record and
            # never enters the organizing execution queue or gains a slot.
            analysis_tasks = [
                task
                for task in value.repository.list_tasks()
                if task.task_id != failed_task.task_id
            ]
            self.assertEqual(1, len(analysis_tasks), analysis_tasks)
            self.assertFalse(analysis_tasks[0].execute_authorized)
            self.assertIsNone(value.repository.get_task_scheduling(analysis_tasks[0].task_id))
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())

    def test_retry_failed_execute_replays_only_the_failed_sibling(self):
        """A retried execution never replays the original work's success sibling.

        Two real sources are organized together; the executor fails for exactly
        one of them and the other really moves.  ``tasks retry-failed --execute``
        then runs one kernel-admitted retry Task for the failed source only: the
        already-organized sibling keeps its own original Result and is never
        moved again.
        """

        self.media("One.2001.mkv")
        self.media("Two.2002.mkv")
        with entrance_journey(
            self,
            movie_rule=True,
            candidates=(
                MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),
                MediaCandidate("tmdb", "2", MediaType.MOVIE, "Two", year=2002),
            ),
        ) as value:
            from mediaflow.application.organizer import OrganizerExecutor

            attempted: list[str] = []
            fail_second = [True]

            class _SelectiveFailureExecutor(OrganizerExecutor):
                def execute(self, plan, storages, **kwargs):
                    attempted.append(plan.source)
                    if fail_second[0] and "Two" in plan.source:
                        raise RuntimeError("injected failure for the second source only")
                    return super().execute(plan, storages, **kwargs)

            with (
                patch(
                    "mediaflow.final_cli.metadata_provider_registry_from_environment",
                    return_value=value.provider_registry,
                ),
                patch("mediaflow.final_cli.OrganizerExecutor", _SelectiveFailureExecutor),
            ):
                code = final_main(
                    [
                        "--config",
                        str(value.config),
                        "organize",
                        str(value.source_root),
                        "--execute",
                        "--limit",
                        "5",
                    ],
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )
            # The first organized source really moved, failing the run overall.
            self.assertEqual(1, code)
            (original,) = value.repository.list_tasks()
            items = {
                item.source_path: item for item in value.repository.list_items(original.task_id)
            }
            self.assertEqual({"One.2001.mkv", "Two.2002.mkv"}, set(items))
            self.assertEqual("success", items["One.2001.mkv"].status.value)
            self.assertEqual("failed", items["Two.2002.mkv"].status.value)
            original_results = value.repository.list_results(original.task_id)
            self.assertEqual(2, len(original_results), original_results)
            sibling_result = next(
                result for result in original_results if result.source_path == "One.2001.mkv"
            )
            self.assertTrue((value.target_root / "Organized" / "Movies").rglob("*.mkv"))
            moved_sibling = sorted(
                str(path.relative_to(value.target_root))
                for path in (value.target_root / "Organized" / "Movies").rglob("*.mkv")
            )
            self.assertEqual(1, len(moved_sibling), moved_sibling)

            attempted.clear()
            fail_second[0] = False
            with (
                patch(
                    "mediaflow.final_cli.metadata_provider_registry_from_environment",
                    return_value=value.provider_registry,
                ),
                patch("mediaflow.final_cli.OrganizerExecutor", _SelectiveFailureExecutor),
            ):
                code = final_main(
                    [
                        "--config",
                        str(value.config),
                        "tasks",
                        "retry-failed",
                        original.task_id,
                        "--execute",
                    ],
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )
            self.assertEqual(0, code)
            # Exactly the failed source was retried; the success sibling was not.
            self.assertEqual(1, len(attempted), attempted)
            self.assertIn("Two", attempted[0])
            retry_tasks = [
                task for task in value.repository.list_tasks() if task.task_id != original.task_id
            ]
            self.assertEqual(1, len(retry_tasks), retry_tasks)
            retry_items = value.repository.list_items(retry_tasks[0].task_id)
            self.assertEqual(
                {"Two.2002.mkv"}, {item.source_path for item in retry_items}, retry_items
            )
            organized = sorted(
                str(path.relative_to(value.target_root))
                for path in (value.target_root / "Organized" / "Movies").rglob("*.mkv")
            )
            self.assertEqual(2, len(organized), organized)
            self.assertEqual(moved_sibling, [path for path in organized if "One" in path])
            # The original sibling keeps its own Result exactly once.
            original_results = value.repository.list_results(original.task_id)
            self.assertEqual(2, len(original_results), original_results)
            self.assertEqual(
                sibling_result,
                next(result for result in original_results if result.source_path == "One.2001.mkv"),
            )
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())

    def test_manual_task_without_organizing_origin_keeps_the_bounded_refusal(self):
        """A manual Task without a proved organizing origin is never continued.

        The kernel continuation is granted to a manual Task only when its durable
        display origin proves a direct CLI or remote-ticket organize admission.
        A missing or foreign origin keeps the bounded ``no_linked_preparation``
        refusal instead of granting every manual Task a continuation.
        """

        from mediaflow.application.manual_task_continuation import (
            ManualTaskContinuationError,
            ManualTaskContinuationService,
        )
        from mediaflow.domain.task_scheduling import TaskTrigger

        class _Repository:
            def __init__(self, origin):
                self._origin = origin

            def get_task_scheduling(self, task_id):
                return SimpleNamespace(admission_trigger=TaskTrigger.MANUAL)

            def get_run_display_context(self, task_id):
                if self._origin is None:
                    return None
                return SimpleNamespace(origin_kind=self._origin)

            def get_media_discovery_for_task(self, task_id):
                return None

        class _Checkpoints:
            def get(self, item_id, task_id=None):
                return SimpleNamespace(
                    task_id="task-1",
                    checkpoint_version="v1",
                    effect_certainty=EffectCertainty.NONE,
                    permitted_action_ids=("retry",),
                    active_recovery_request=None,
                    recovery_continuation=None,
                    configuration=CheckpointConfiguration("snap-1", "digest-1", True, None),
                )

        class _Scheduling:
            def state(self, task_id):
                return SimpleNamespace(admission_trigger=TaskTrigger.MANUAL)

        for origin in (None, "definition-run-once", "legacy-schedule"):
            with self.subTest(origin=origin):
                service = ManualTaskContinuationService(
                    _Repository(origin),
                    discovery_service=None,
                    checkpoint_service=_Checkpoints(),
                    scheduling=lambda: _Scheduling(),
                )
                with self.assertRaises(ManualTaskContinuationError) as raised:
                    service.continue_analysis(
                        "task-1",
                        "item-1",
                        expected_checkpoint_version="v1",
                        actor="admin",
                    )
                self.assertEqual("no_linked_preparation", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
