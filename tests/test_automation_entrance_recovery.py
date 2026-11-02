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

import errno
import io
import json
import os
import tempfile
import unittest
from contextlib import contextmanager, redirect_stderr
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
from mediaflow.domain.task_scheduling import TaskControl
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
    recognition_rules: list[dict] | None = None,
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
    if recognition_rules is not None:
        document["recognitionRules"] = recognition_rules
    elif movie_rule:
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

    def _run_cli(
        self,
        value,
        *arguments: str,
        cancellation_check=None,
    ) -> tuple[int, str, str]:
        """Run the real production CLI with the journey's fake Provider only."""

        output, errors = io.StringIO(), io.StringIO()
        with patch(
            "mediaflow.final_cli.metadata_provider_registry_from_environment",
            return_value=value.provider_registry,
        ):
            code = final_main(
                ["--config", str(value.config), *arguments],
                stdout=output,
                stderr=errors,
                cancellation_check=cancellation_check,
            )
        return code, output.getvalue(), errors.getvalue()

    def _target_disk_full(
        self, target_root: Path, *, contains: str | None = None, on_disk_full=None
    ):
        """Inject one real ENOSPC at a target Storage write, never at business state."""

        original_open = Path.open
        root = target_root.resolve()

        def disk_full(path, mode="r", *args, **kwargs):
            candidate = Path(path)
            if (
                "w" in mode
                and candidate.resolve().is_relative_to(root)
                and (contains is None or contains in str(candidate))
            ):
                if on_disk_full is not None:
                    on_disk_full()
                raise OSError(errno.ENOSPC, "No space left on device", str(candidate))
            return original_open(path, mode, *args, **kwargs)

        return disk_full

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
            self.assertEqual(1, len(value.repository.list_tasks()))
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
            self.assertEqual(1, len(value.repository.list_tasks()))
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
            self.assertEqual(1, len(value.repository.list_tasks()))

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
            self.assertEqual(1, len(value.repository.list_tasks()))

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

    def test_cli_disk_full_settles_partial_and_next_distinct_file_releases_slot(self):
        """A finished CLI pass gives its slot back without rewriting its unknown Result."""

        first = self.media("One.2001.mkv")
        candidates = (
            MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),
            MediaCandidate("tmdb", "2", MediaType.MOVIE, "Two", year=2002),
        )
        with entrance_journey(
            self,
            movie_rule=True,
            organize_operation="COPY",
            capacity=1,
            candidates=candidates,
        ) as value:
            with patch.object(Path, "open", self._target_disk_full(value.target_root)):
                code, output, errors = self._run_cli(
                    value, "organize", str(first), "--execute", "--limit", "1"
                )

            # The real target write failed, but the process finished cleanly:
            # the CLI reports the durable Task and its business failure instead
            # of a settlement exception.
            self.assertEqual(1, code, errors)
            self.assertEqual("", errors, errors)
            self.assertIn("Task ID:", output)
            self.assertIn("SUMMARY", output)
            self.assertIn("PARTIAL", output)
            self.assertIn("Failed: 1", output)
            self.assertIn("No space left on device", output)

            (first_task,) = value.repository.list_tasks()
            (first_item,) = value.repository.list_items(first_task.task_id)
            (first_result,) = value.repository.list_results(first_task.task_id)
            self.assertEqual("failed", first_task.status.value, first_task.error)
            self.assertEqual("partial", first_item.status.value)
            self.assertEqual("failed", first_item.stage)
            self.assertTrue(first_item.error)
            self.assertEqual("partial", first_result.status)
            self.assertEqual("attempted_unverified", first_result.effect_certainty)
            self.assertEqual(("CREATE_DIRECTORY",), first_result.completed_operations)
            self.assertEqual(("mutation_outcome",), first_result.uncertain_effects)
            first_state = value.repository.get_task_scheduling(first_task.task_id)
            self.assertEqual("settled", first_state.queue_state.value)
            self.assertFalse(first_state.mutation_in_flight)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertTrue(first.exists())
            self.assertEqual([], list(value.target_root.rglob("*.mkv")))
            self.assertEqual(
                {"stopped"},
                {worker.status.value for worker in value.repository.list_workers()},
            )

            # Removing the fault lets a genuinely different file through the
            # same CLI and shared capacity; it is a new Task, not a replay of A.
            second = self.media("Two.2002.mkv")
            code, output, errors = self._run_cli(
                value, "organize", str(second), "--execute", "--limit", "1"
            )
            self.assertEqual(0, code, errors)
            self.assertIn("Task ID:", output)
            tasks = value.repository.list_tasks()
            self.assertEqual(2, len(tasks))
            second_task = next(task for task in tasks if task.task_id != first_task.task_id)
            self.assertEqual("completed", second_task.status.value, second_task.error)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertTrue(second.exists())
            self.assertEqual(
                1, len(list((value.target_root / "Organized" / "Movies").rglob("*.mkv")))
            )
            self.assertEqual((first_item,), value.repository.list_items(first_task.task_id))
            self.assertEqual((first_result,), value.repository.list_results(first_task.task_id))

            # Same-version reopen keeps the honest A/B endings and capacity.
            with SQLiteTaskRepository(value.runtime.database_path) as reopened:
                self.assertEqual("failed", reopened.get_task(first_task.task_id).status.value)
                self.assertEqual((first_item,), reopened.list_items(first_task.task_id))
                self.assertEqual((first_result,), reopened.list_results(first_task.task_id))
                self.assertEqual(
                    "settled",
                    reopened.get_task_scheduling(first_task.task_id).queue_state.value,
                )
                self.assertFalse(
                    reopened.get_task_scheduling(first_task.task_id).mutation_in_flight
                )
                self.assertEqual("completed", reopened.get_task(second_task.task_id).status.value)
                self.assertEqual(0, reopened.count_scheduled_capacity_use())

    def test_cli_folder_mixed_terminal_outcomes_settle_one_task(self):
        """One failed and one successful folder sibling settle independently at zero slots."""

        self.media("One.2001.mkv")
        self.media("Two.2002.mkv")
        candidates = (
            MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),
            MediaCandidate("tmdb", "2", MediaType.MOVIE, "Two", year=2002),
        )
        with entrance_journey(
            self, movie_rule=True, organize_operation="COPY", capacity=1, candidates=candidates
        ) as value:
            with patch.object(
                Path,
                "open",
                self._target_disk_full(value.target_root, contains="Two (2002)"),
            ):
                code, output, errors = self._run_cli(
                    value, "organize", str(value.source_root), "--execute", "--limit", "5"
                )

            self.assertEqual(1, code, errors)
            self.assertEqual("", errors, errors)
            self.assertIn("Task ID:", output)
            self.assertIn("PARTIAL", output)
            self.assertIn("SUCCESS", output)
            (task,) = value.repository.list_tasks()
            self.assertEqual("partial_success", task.status.value, task.error)
            items = {
                Path(item.source_path).name: item
                for item in value.repository.list_items(task.task_id)
            }
            self.assertEqual("success", items["One.2001.mkv"].status.value)
            self.assertEqual("partial", items["Two.2002.mkv"].status.value)
            results = {
                Path(result.source_path).name: result
                for result in value.repository.list_results(task.task_id)
            }
            self.assertEqual("verified_complete", results["One.2001.mkv"].effect_certainty)
            self.assertEqual("attempted_unverified", results["Two.2002.mkv"].effect_certainty)
            state = value.repository.get_task_scheduling(task.task_id)
            self.assertEqual("settled", state.queue_state.value)
            self.assertFalse(state.mutation_in_flight)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertTrue((value.source_root / "One.2001.mkv").exists())
            self.assertTrue((value.source_root / "Two.2002.mkv").exists())
            self.assertEqual(
                1, len(list((value.target_root / "Organized" / "Movies").rglob("*.mkv")))
            )
            self.assertEqual(
                {"stopped"},
                {worker.status.value for worker in value.repository.list_workers()},
            )

    def test_batch_root_files_parse_real_names_and_settle_mixed_outcomes(self):
        """The real all-library batch parses Storage-relative names, not display identity."""

        self.media("One.2001.mkv")
        self.media("Two.2002.mkv")
        candidates = (
            MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),
            MediaCandidate("tmdb", "2", MediaType.MOVIE, "Two", year=2002),
        )

        class _RecordingProvider(SyntheticMetadataProvider):
            def __init__(self) -> None:
                super().__init__(candidates)
                self.queries: list[str] = []

            def search_movie(self, query, policy=None, **kwargs):
                self.queries.append(query.title_candidate)
                return super().search_movie(query, policy, **kwargs)

        with entrance_journey(
            self, movie_rule=True, organize_operation="COPY", capacity=1, candidates=candidates
        ) as value:
            provider = _RecordingProvider()
            value.provider_registry = MetadataProviderRegistry((provider,))
            with patch.object(
                Path,
                "open",
                self._target_disk_full(value.target_root, contains="Two (2002)"),
            ):
                code, output, errors = self._run_cli(
                    value, "batch", "organize", "--execute", "--limit", "5"
                )

            self.assertEqual(1, code, errors)
            self.assertEqual("", errors, errors)
            self.assertEqual(["One", "Two"], provider.queries)
            self.assertIn("Task ID:", output)
            self.assertIn("PARTIAL", output)
            self.assertIn("SUCCESS", output)
            (task,) = value.repository.list_tasks()
            self.assertEqual("partial_success", task.status.value, task.error)
            items = {
                Path(item.source_path).name: item
                for item in value.repository.list_items(task.task_id)
            }
            self.assertEqual("success", items["One.2001.mkv"].status.value)
            self.assertEqual("partial", items["Two.2002.mkv"].status.value)
            results = {
                Path(result.source_path).name: result
                for result in value.repository.list_results(task.task_id)
            }
            self.assertEqual("source", results["One.2001.mkv"].source_storage_id)
            self.assertEqual("source", results["Two.2002.mkv"].source_storage_id)
            self.assertEqual("verified_complete", results["One.2001.mkv"].effect_certainty)
            self.assertEqual("attempted_unverified", results["Two.2002.mkv"].effect_certainty)
            state = value.repository.get_task_scheduling(task.task_id)
            self.assertEqual("settled", state.queue_state.value)
            self.assertFalse(state.mutation_in_flight)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertTrue((value.source_root / "One.2001.mkv").exists())
            self.assertTrue((value.source_root / "Two.2002.mkv").exists())
            self.assertEqual(
                1, len(list((value.target_root / "Organized" / "Movies").rglob("*.mkv")))
            )

            with SQLiteTaskRepository(value.runtime.database_path) as reopened:
                self.assertEqual(1, len(reopened.list_tasks()))
                self.assertEqual(2, len(reopened.list_items(task.task_id)))
                self.assertEqual(2, len(reopened.list_results(task.task_id)))
                self.assertEqual(0, reopened.count_scheduled_capacity_use())

    def test_batch_nested_colon_file_keeps_exact_storage_path_for_recognition(self):
        """A subdirectory file is parsed by exact Storage-relative path, not a split display id."""

        self.media("Movies/With: Colon.2003.mkv")
        candidates = (MediaCandidate("tmdb", "3", MediaType.MOVIE, "With: Colon", year=2003),)
        directory_rule = [
            {
                "id": "movies-directory",
                "name": "Movies directory",
                "priority": 100,
                "score": 100,
                "stopOnMatch": True,
                "condition": {"field": "directory", "operator": "contains", "value": "Movies"},
                "outputRecognitionType": "A",
            }
        ]

        class _RecordingProvider(SyntheticMetadataProvider):
            def __init__(self) -> None:
                super().__init__(candidates)
                self.queries: list[str] = []

            def search_movie(self, query, policy=None, **kwargs):
                self.queries.append(query.title_candidate)
                return super().search_movie(query, policy, **kwargs)

        with entrance_journey(
            self,
            organize_operation="COPY",
            capacity=1,
            candidates=candidates,
            recognition_rules=directory_rule,
        ) as value:
            provider = _RecordingProvider()
            value.provider_registry = MetadataProviderRegistry((provider,))
            code, output, errors = self._run_cli(
                value, "batch", "organize", "--execute", "--limit", "5"
            )

            self.assertEqual(0, code, errors)
            self.assertEqual("", errors, errors)
            self.assertEqual(["With: Colon"], provider.queries)
            self.assertIn("SUCCESS", output)
            (task,) = value.repository.list_tasks()
            (item,) = value.repository.list_items(task.task_id)
            self.assertEqual("success", item.status.value, item.error)
            self.assertEqual("Movies/With: Colon.2003.mkv", item.source_path)
            self.assertEqual("Movies/With: Colon.2003.mkv", item.source_storage_path)
            self.assertEqual("source:Movies/With: Colon.2003.mkv", item.source_display)
            (result,) = value.repository.list_results(task.task_id)
            self.assertEqual("source", result.source_storage_id)
            self.assertEqual("Movies/With: Colon.2003.mkv", result.source_path)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertEqual(
                1, len(list((value.target_root / "Organized" / "Movies").rglob("*.mkv")))
            )

    def test_cli_finished_pass_with_human_waiting_sibling_releases_the_slot(self):
        """A completed CLI pass waits for its operator without keeping a queue slot."""

        self.media("One.2001.mkv")
        self.media("Two.2002.mkv")
        with entrance_journey(
            self,
            movie_rule=True,
            organize_operation="COPY",
            capacity=1,
            candidates=(MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),),
        ) as value:
            with patch.object(
                Path,
                "open",
                self._target_disk_full(value.target_root, contains="One (2001)"),
            ):
                code, output, errors = self._run_cli(
                    value, "organize", str(value.source_root), "--execute", "--limit", "5"
                )

            self.assertEqual(1, code, errors)
            self.assertEqual("", errors, errors)
            self.assertIn("Task ID:", output)
            (task,) = value.repository.list_tasks()
            items = {
                Path(item.source_path).name: item
                for item in value.repository.list_items(task.task_id)
            }
            self.assertEqual("partial", items["One.2001.mkv"].status.value)
            self.assertTrue(items["Two.2002.mkv"].status.value.startswith("waiting_"))
            self.assertEqual(
                ("waiting_metadata_correction",),
                tuple(
                    item.status.value
                    for item in items.values()
                    if item.status.value.startswith("waiting_")
                ),
            )
            state = value.repository.get_task_scheduling(task.task_id)
            self.assertEqual("waiting_human", state.queue_state.value)
            self.assertFalse(state.mutation_in_flight)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            (result,) = value.repository.list_results(task.task_id)
            self.assertEqual("attempted_unverified", result.effect_certainty)
            self.assertEqual([], list(value.target_root.rglob("*.mkv")))
            self.assertEqual(
                {"stopped"},
                {worker.status.value for worker in value.repository.list_workers()},
            )

    def test_cli_cancel_after_disk_failure_settles_without_rewriting_partial(self):
        """A cancel at the returned pass boundary keeps the recorded partial Result."""

        source = self.media("One.2001.mkv")
        cancel = {"requested": False}
        with entrance_journey(
            self,
            movie_rule=True,
            organize_operation="COPY",
            capacity=1,
            candidates=(MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),),
        ) as value:
            disk_full = self._target_disk_full(
                value.target_root, on_disk_full=lambda: cancel.update(requested=True)
            )
            with patch.object(Path, "open", disk_full):
                code, output, errors = self._run_cli(
                    value,
                    "organize",
                    str(source),
                    "--execute",
                    "--limit",
                    "1",
                    cancellation_check=lambda: cancel["requested"],
                )

            self.assertEqual(130, code, errors)
            self.assertEqual("", errors, errors)
            self.assertIn("Task ID:", output)
            (task,) = value.repository.list_tasks()
            (item,) = value.repository.list_items(task.task_id)
            (result,) = value.repository.list_results(task.task_id)
            self.assertEqual("cancelled", task.status.value, task.error)
            self.assertEqual("partial", item.status.value)
            self.assertEqual("partial", result.status)
            self.assertEqual("attempted_unverified", result.effect_certainty)
            self.assertEqual(("mutation_outcome",), result.uncertain_effects)
            state = value.repository.get_task_scheduling(task.task_id)
            self.assertEqual("settled", state.queue_state.value)
            self.assertIs(state.control_request, TaskControl.CANCEL)
            self.assertFalse(state.mutation_in_flight)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertTrue(source.exists())
            self.assertEqual([], list(value.target_root.rglob("*.mkv")))
            self.assertEqual(
                {"stopped"},
                {worker.status.value for worker in value.repository.list_workers()},
            )

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
                "/api/v1/tasks",
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
            self.assertEqual(1, len(value.repository.list_tasks()))
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
            self.assertEqual(1, len(value.repository.list_tasks()))
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())

            status, continued, decided, _detail = self._save_recognition_decision_and_continue(
                value, task_id, item.item_id
            )
            self.assertEqual(202, status, continued)
            self.assertEqual(task_id, continued["nativeAnalysis"]["taskId"])
            state = value.repository.get_task_scheduling(task_id)
            self.assertEqual("queued", state.queue_state.value)
            self.assertEqual("admin", state.continuation_actor)
            self.assertEqual(1, len(value.repository.list_tasks()))

            settled = self._run_resident_worker(value, prefix="remote-continuation")
            self.assertIsNotNone(settled)
            (item,) = value.repository.list_items(task_id)
            self.assertEqual("waiting_confirm", item.status.value, item)
            state = value.repository.get_task_scheduling(task_id)
            self.assertEqual("waiting_human", state.queue_state.value)

            status, refused = self.request(
                value,
                "POST",
                "/api/v1/tasks",
                {"command": "organize", "execute": True, "limit": 5},
                headers={"HTTP_X_MEDIAFLOW_EXECUTION_TOKEN": "one-time-entrance-ticket"},
            )
            self.assertEqual(400, status, refused)
            self.assertEqual(1, len(value.repository.list_tasks()))

            status, confirmed, preparation, ready = self._confirm_ready_subset(
                value, task_id, item.item_id
            )
            self.assertEqual(202, status, confirmed)
            self.assertEqual(task_id, confirmed["taskId"], confirmed)
            self.assertEqual(1, len(value.repository.list_tasks()))

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
            self.assertEqual(1, len(value.repository.list_tasks()))

    def test_retired_retry_failed_entrance_is_an_ordinary_parse_error(self):
        """The retired ``tasks retry-failed`` entrance stays retired, zero effects.

        Slice 47 RO-6 removed the independent CLI failure-retry entrance: new
        organizing starts from Files/``organize`` and an existing Task's own
        four-type continuation.  The old command is an ordinary unrecognized
        argument error reached before any runtime construction — no Task, no
        lock release, no Provider, no Storage effect — and the original failed
        work keeps every one of its durable facts.
        """

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

            # One real admitted execution fails before any mutation at the real
            # OrganizerExecutor boundary, so a genuine failed Task exists.
            output, errors = io.StringIO(), io.StringIO()
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
                    stdout=output,
                    stderr=errors,
                )
            self.assertEqual(1, code, errors.getvalue())
            (failed_task,) = value.repository.list_tasks()
            (failed_item,) = value.repository.list_items(failed_task.task_id)
            self.assertEqual("failed", failed_item.status.value, failed_item)
            self.assertEqual("failed", failed_task.status.value, failed_task)
            (failed_result,) = value.repository.list_results(failed_task.task_id)
            self.assertTrue(source.exists())

            for extra in ([], ["--execute"]):
                with self.subTest(extra=extra):
                    out, err = io.StringIO(), io.StringIO()
                    with redirect_stderr(err):
                        with self.assertRaises(SystemExit) as exited:
                            final_main(
                                [
                                    "--config",
                                    str(value.config),
                                    "tasks",
                                    "retry-failed",
                                    failed_task.task_id,
                                    *extra,
                                ],
                                stdout=out,
                                stderr=err,
                            )
                    self.assertEqual(2, exited.exception.code)
                    self.assertIn("invalid choice", err.getvalue())
                    self.assertEqual("", out.getvalue())

            # The refusal happened at the parser: zero new work, zero effects.
            self.assertEqual(1, len(value.repository.list_tasks()))
            self.assertEqual(
                (failed_item,),
                value.repository.list_items(failed_task.task_id),
                "the original failed item keeps its exact recorded state",
            )
            self.assertEqual(
                (failed_result,),
                value.repository.list_results(failed_task.task_id),
                "the original failure record stays exactly once",
            )
            self.assertTrue(source.exists(), "the source file was never touched")
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
