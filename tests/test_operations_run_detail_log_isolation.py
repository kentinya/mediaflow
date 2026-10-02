"""Task 42.2 regression — per-run isolation of shared-plan operational logs (P1 #2).

``organizer._plan_id`` hashes source Storage/path + target Storage/path.  It is
deterministic but *not* run-unique: two independent Preview passes over the same
source legitimately share one plan ID while being distinct Tasks.  The fix this
file pins down has three cooperating parts, each proven here:

1. REAL PIPELINE ISOLATION (the core regression): two independent
   ``execute=False`` Preview passes run the real
   ``MediaOrganizerService``/``StorageScanner``/``LocalStorage``/
   ``SyntheticMetadataProvider``/``JsonLinesOperationHistoryRepository``/
   ``SQLiteTaskRepository``/``PersistentTaskCoordinator`` assembly, each on its
   own service instance tracked by its own coordinator-created Task and writing
   through its own ``SQLiteOperationalLogger``.  Both passes share one plan ID,
   yet ``list_operational_logs_for_plan(plan_id, task_id=...)`` attributes each
   log row to exactly its own run, refuses attribution with no run linkage, and
   the real ``GET /api/v1/operations/runs/{run}/items/{item}`` read publishes
   exactly the repository's per-run rows — never the other run's.  Each run's
   durable Result survives regardless of log attribution, and both Preview
   passes mutate zero files.  Logs emitted without a run linkage (for example
   the shared executor's ``organizer.execution_result`` rows) are excluded from
   both runs' item evidence while staying visible on the global log list.
2. WRITE-SIDE STAMPING: ``MediaOrganizerService._log`` injects the service's
   own ``task_id`` into every emitted log context, never overwrites an explicit
   caller-supplied ``task_id``, and stamps nothing when the run is untracked.
3. SEEDED API ATTRIBUTION: with hand-seeded rows, each run claims exactly its
   own two plan-linked logs (occurred_at DESC), a plan-ID-only log is claimed by
   neither run, a job-stamped log is claimed through the persisted Job→Task
   linkage from both the Job and Task anchors, a log for a different plan stays
   excluded, and deleting the other run's log linkage cannot erase this run's
   logs or Result.

Everything runs against temporary SQLite/LocalStorage directories; no network,
no Provider service and no production media is touched.
"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
import uuid
from datetime import timedelta
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
from mediaflow.domain.library import MediaLibrary, ResourceLibrary
from mediaflow.domain.logging import LogLevel, OperationalLogRecord
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.organizer import ExecutionStatus
from mediaflow.domain.task_persistence import TaskItemStatus
from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.memory_file_index import InMemoryFileIndexRepository
from mediaflow.infrastructure.operational_logging import SQLiteOperationalLogger
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_operations_run_detail import _item, _result
from tests.test_operations_run_inventory import (
    NOW,
    OPERATOR,
    VIEWER,
    job,
    request,
)

SHARED_PLAN = "shared-plan"

CANDIDATES = (
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


class _RecordingLogger:
    """Minimal ``Logger`` fake that records every emitted context verbatim."""

    def __init__(self) -> None:
        self.calls: list[tuple[LogLevel, str, dict[str, object]]] = []

    def log(self, level, message, **context) -> None:
        self.calls.append((level, message, context))

    def messages(self) -> list[str]:
        return [call[1] for call in self.calls]

    def context_for(self, message: str) -> list[dict[str, object]]:
        return [call[2] for call in self.calls if call[1] == message]


class RealPipelineSharedPlanIsolationTests(unittest.TestCase):
    """The core P1 #2 regression through the complete production assembly."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.source_root = root / "source"
        self.target_root = root / "target"
        self.source_root.mkdir()
        self.target_root.mkdir()
        self.source_path = self.source_root / "Spirited.Away.2001.mkv"
        self.source_path.write_bytes(b"movie")
        self.source_storage = LocalStorage("source", str(self.source_root))
        self.target_storage = LocalStorage("target", str(self.target_root))
        self.storages = {"source": self.source_storage, "target": self.target_storage}
        self.configuration = development_strategy_configuration()
        self.library = ResourceLibrary("movies", "Movies", "source", "")
        self.media_libraries = {"movies": MediaLibrary("movies", "Movies", "target", "Movies")}
        self.repository = SQLiteTaskRepository(root / "runtime.sqlite3")
        self.addCleanup(self.repository.close)
        self.coordinator = PersistentTaskCoordinator(self.repository, self.repository)

    def _preview_pass(self, *, rank: int, executor_logging: bool) -> dict[str, object]:
        """One independent tracked Preview Task over the same single source."""

        task = self.coordinator.create("organize", execute_authorized=False)
        logger = SQLiteOperationalLogger(self.repository, "workflow")
        service = MediaOrganizerService(
            strategy_runner_from_configuration(
                self.configuration,
                MetadataProviderRegistry((SyntheticMetadataProvider(CANDIDATES),)),
            ),
            StorageScanner(self.storages, InMemoryFileIndexRepository()),
            self.storages,
            self.media_libraries,
            self.configuration.recognition_type_policies,
            JsonLinesOperationHistoryRepository(Path(self.temporary.name, f"history-{rank}.jsonl")),
            # final_cli wires the same operational logger into the executor
            # that logs a DryRun; its rows carry the plan ID but no run linkage.
            executor=OrganizerExecutor(logger) if executor_logging else None,
            source_display_roots={"movies": str(self.source_root)},
            task_coordinator=self.coordinator,
            task_id=task.task_id,
            logger=logger,
        )
        batch = service.process_library(self.library, execute=False)
        self.coordinator.finish(task.task_id, batch)
        persisted_items = self.repository.list_items(task.task_id)
        self.assertEqual(1, len(batch.items))
        self.assertEqual(1, len(persisted_items))
        return {
            "task": task,
            "batch": batch,
            "item": persisted_items[0],
        }

    def test_two_preview_passes_share_one_plan_yet_own_disjoint_run_logs(self) -> None:
        first = self._preview_pass(rank=0, executor_logging=False)
        second = self._preview_pass(rank=1, executor_logging=False)

        # Both passes are zero-mutation Previews that reached the executor.
        for pass_ in (first, second):
            item = pass_["batch"].items[0]
            self.assertIsNotNone(item.plan)
            self.assertIsNotNone(item.execution)
            self.assertIs(ExecutionStatus.DRY_RUN, item.execution.status)
            self.assertIs(TaskItemStatus.DRY_RUN, pass_["item"].status)

        # Shared-plan premise: the deterministic plan ID is identical across
        # both passes (live object and persisted TaskItem) while the Tasks,
        # TaskItems and Results are all distinct.
        plan_a = first["batch"].items[0].plan.plan_id
        plan_b = second["batch"].items[0].plan.plan_id
        self.assertEqual(plan_a, plan_b)
        self.assertEqual(first["item"].plan_id, plan_a)
        self.assertEqual(second["item"].plan_id, plan_b)
        task_a = first["task"].task_id
        task_b = second["task"].task_id
        self.assertNotEqual(task_a, task_b)
        self.assertNotEqual(first["item"].item_id, second["item"].item_id)

        # Real repository: each run gets a non-empty, fully own-linked view.
        logs_a = self.repository.list_operational_logs_for_plan(plan_a, task_id=task_a)
        logs_b = self.repository.list_operational_logs_for_plan(plan_b, task_id=task_b)
        self.assertNotEqual(logs_a, ())
        self.assertNotEqual(logs_b, ())
        self.assertTrue(all(record.task_id == task_a for record in logs_a))
        self.assertTrue(all(record.task_id == task_b for record in logs_b))
        self.assertTrue(all(record.plan_id == plan_a for record in logs_a))
        self.assertTrue(all(record.plan_id == plan_b for record in logs_b))
        ids_a = {record.log_id for record in logs_a}
        ids_b = {record.log_id for record in logs_b}
        self.assertTrue(ids_a.isdisjoint(ids_b))
        # The shared plan genuinely holds rows for both runs.
        shared_rows = self.repository.list_operational_logs_for_plan(
            plan_a, task_id=task_a, job_id=None
        ) + self.repository.list_operational_logs_for_plan(plan_b, task_id=task_b)
        self.assertGreaterEqual(len(shared_rows), 2)

        # Plan-ID-only attribution is refused outright.
        self.assertEqual(self.repository.list_operational_logs_for_plan(plan_a), ())

        # Real API: standalone Tasks are their own runs (run_id == task_id).
        api = MediaFlowApi(self.repository, None, principals=(OPERATOR,))
        documents = {}
        for label, pass_ in (("a", first), ("b", second)):
            code, evidence, _ = request(
                api,
                "GET",
                f"/api/v1/operations/runs/{pass_['task'].task_id}/items/{pass_['item'].item_id}",
                token="operator-token",
            )
            self.assertEqual(code, 200, evidence)
            documents[label] = evidence

        for label, pass_, expected in (
            ("a", first, logs_a),
            ("b", second, logs_b),
        ):
            evidence = documents[label]
            self.assertEqual(evidence["run_id"], pass_["task"].task_id)
            self.assertEqual(evidence["task_id"], pass_["task"].task_id)
            self.assertEqual(evidence["item"]["item_id"], pass_["item"].item_id)
            self.assertEqual(evidence["sideEffects"], "none")
            record_ids = [row["record_id"] for row in evidence["logs"]]
            # Exactly the repository's own-run rows, in the same order.
            self.assertEqual(record_ids, [f"log:{row.log_id}" for row in expected])
            self.assertTrue(all(row["kind"] == "log" for row in evidence["logs"]))
        # Cross-run leakage is impossible in either direction.
        a_ids = {row["record_id"] for row in documents["a"]["logs"]}
        b_ids = {row["record_id"] for row in documents["b"]["logs"]}
        self.assertTrue(a_ids.isdisjoint(b_ids))
        self.assertFalse(a_ids & ids_b)
        self.assertFalse(b_ids & ids_a)

        # Result independence: each run's evidence carries its own persisted
        # Result row even though the shared plan's logs are a strict subset.
        for label, pass_ in (("a", first), ("b", second)):
            results = documents[label]["results"]
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["result_id"], f"{pass_['item'].item_id}:1")
            self.assertEqual(results[0]["task_id"], pass_["task"].task_id)
            self.assertEqual(results[0]["status"], TaskItemStatus.DRY_RUN.value)

        # Zero mutation: two Previews changed nothing.
        self.assertTrue(self.source_path.exists())
        self.assertEqual(b"movie", self.source_path.read_bytes())
        self.assertEqual([], sorted(self.target_root.rglob("*")))

    def test_plan_linked_logs_without_run_linkage_are_claimed_by_neither_run(
        self,
    ) -> None:
        # executor_logging=True mirrors final_cli: the shared OrganizerExecutor
        # emits "organize execution result" with the plan ID but no task/job.
        first = self._preview_pass(rank=0, executor_logging=True)
        second = self._preview_pass(rank=1, executor_logging=True)
        plan_a = first["item"].plan_id
        task_a = first["task"].task_id
        task_b = second["task"].task_id

        unlinked = [
            record
            for record in self.repository.list_operational_logs(limit=100)
            if record.plan_id == plan_a and record.task_id is None and record.job_id is None
        ]
        self.assertTrue(
            unlinked,
            "the executor-emitted plan rows must exist to prove they are excluded",
        )
        unlinked_ids = {record.log_id for record in unlinked}

        logs_a = self.repository.list_operational_logs_for_plan(plan_a, task_id=task_a)
        logs_b = self.repository.list_operational_logs_for_plan(plan_a, task_id=task_b)
        claimed = {record.log_id for record in logs_a} | {record.log_id for record in logs_b}
        self.assertFalse(claimed & unlinked_ids)

        api = MediaFlowApi(self.repository, None, principals=(OPERATOR,))
        for pass_, other_task in ((first, task_b), (second, task_a)):
            code, evidence, _ = request(
                api,
                "GET",
                f"/api/v1/operations/runs/{pass_['task'].task_id}/items/{pass_['item'].item_id}",
                token="operator-token",
            )
            self.assertEqual(code, 200, evidence)
            record_ids = {row["record_id"] for row in evidence["logs"]}
            self.assertFalse(record_ids & {f"log:{log_id}" for log_id in unlinked_ids})
            # And neither run leaks the other run's rows.
            other_ids = {
                f"log:{record.log_id}"
                for record in self.repository.list_operational_logs_for_plan(
                    plan_a, task_id=other_task
                )
            }
            self.assertTrue(record_ids)
            self.assertFalse(record_ids & other_ids)
            # Exclusion never erases the durable Result.
            self.assertEqual(len(evidence["results"]), 1)

        # The unlinked history is still globally observable — excluded, not
        # silently destroyed.
        _, page, _ = request(api, "GET", "/api/v1/logs", query="limit=100", token="operator-token")
        global_ids = {item["log_id"] for item in page["items"]}
        self.assertTrue(unlinked_ids <= global_ids)


class OrganizerLogTaskStampingTests(unittest.TestCase):
    """``MediaOrganizerService._log`` stamps its run's task_id at emission."""

    def _service(self, *, task_id: str | None, logger: _RecordingLogger, root: Path):
        (root / "source").mkdir(parents=True, exist_ok=True)
        (root / "target").mkdir(parents=True, exist_ok=True)
        source_storage = LocalStorage("source", str(root / "source"))
        target_storage = LocalStorage("target", str(root / "target"))
        source_path = root / "source" / "Spirited.Away.2001.mkv"
        if not source_path.exists():
            source_path.write_bytes(b"movie")
        storages = {"source": source_storage, "target": target_storage}
        configuration = development_strategy_configuration()
        service = MediaOrganizerService(
            strategy_runner_from_configuration(
                configuration,
                MetadataProviderRegistry((SyntheticMetadataProvider(CANDIDATES),)),
            ),
            StorageScanner(storages, InMemoryFileIndexRepository()),
            storages,
            {"movies": MediaLibrary("movies", "Movies", "target", "Movies")},
            configuration.recognition_type_policies,
            JsonLinesOperationHistoryRepository(root / "history.jsonl"),
            source_display_roots={"movies": str(root / "source")},
            logger=logger,
            task_id=task_id,
        )
        return service, source_path

    def test_tracked_service_stamps_task_id_and_never_overwrites_an_explicit_one(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logger = _RecordingLogger()
            service, source_path = self._service(task_id="task-x", logger=logger, root=root)
            result = service.process_file(
                source_path.as_posix(),
                resource_library=ResourceLibrary("movies", "Movies", "source", ""),
                storage_path=source_path.name,
            )
            self.assertIs(ExecutionStatus.DRY_RUN, result.execution.status)

            # The stage events the SQLite logger persists all carry the run.
            for message in (
                "media parsed and recognized",
                "metadata naming and classification completed",
                "organize plan processed",
            ):
                contexts = logger.context_for(message)
                self.assertTrue(contexts, message)
                self.assertTrue(
                    all(context.get("task_id") == "task-x" for context in contexts),
                    message,
                )
            plan_contexts = logger.context_for("organize plan processed")
            self.assertEqual(plan_contexts[-1]["plan_id"], result.plan.plan_id)
            self.assertEqual(plan_contexts[-1]["task_id"], "task-x")

            # An explicit caller-supplied task_id is never overwritten.
            service._log(
                LogLevel.INFO,
                "library scan started",
                library_id="movies",
                task_id="caller-declared-task",
            )
            scan_contexts = logger.context_for("library scan started")
            self.assertEqual(scan_contexts[-1]["task_id"], "caller-declared-task")
            # Stamping does not mutate the caller's kwargs dictionary.
            self.assertEqual(service._task_id, "task-x")

            # Zero mutation, as every Preview must be.
            self.assertTrue(source_path.exists())
            self.assertEqual([], sorted((root / "target").rglob("*")))

    def test_untracked_service_injects_no_task_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logger = _RecordingLogger()
            service, source_path = self._service(task_id=None, logger=logger, root=root)
            service.process_file(
                source_path.as_posix(),
                resource_library=ResourceLibrary("movies", "Movies", "source", ""),
                storage_path=source_path.name,
            )
            self.assertTrue(logger.calls)
            for _, _, context in logger.calls:
                self.assertNotIn("task_id", context)


class SeededSharedPlanAttributionTests(unittest.TestCase):
    """API-level attribution over hand-seeded rows sharing one plan ID."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name, "runtime.sqlite3")
        self.repository = SQLiteTaskRepository(self.database)
        self.addCleanup(self.repository.close)
        self.api = MediaFlowApi(self.repository, None, principals=(VIEWER, OPERATOR))
        self.coordinator = PersistentTaskCoordinator(self.repository, self.repository)

    def _run_with_item(self, item_id: str) -> str:
        task = self.coordinator.create("preview", execute_authorized=False)
        self.repository.upsert_item(
            _item(task.task_id, item_id, TaskItemStatus.DRY_RUN, plan_id=SHARED_PLAN)
        )
        self.repository.append_result(
            _result(task.task_id, item_id, status="dry_run", effect_certainty="none")
        )
        return task.task_id

    def _seed_log(
        self,
        log_id: str,
        *,
        rank: int,
        task_id: str | None = None,
        job_id: str | None = None,
        plan_id: str = SHARED_PLAN,
    ) -> None:
        self.repository.append_operational_log(
            OperationalLogRecord(
                log_id,
                NOW + timedelta(minutes=rank),
                LogLevel.INFO,
                "workflow",
                "workflow.plan_processed",
                task_id=task_id,
                job_id=job_id,
                plan_id=plan_id,
                status="dry_run",
            )
        )

    def _evidence(self, run_id: str, item_id: str) -> dict:
        code, body, _ = request(
            self.api,
            "GET",
            f"/api/v1/operations/runs/{run_id}/items/{item_id}",
        )
        self.assertEqual(code, 200, body)
        return body

    def _raw(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database))
        self.addCleanup(connection.close)
        return connection

    def test_each_run_claims_exactly_its_own_task_stamped_plan_logs(self) -> None:
        task_a = self._run_with_item("item-a")
        task_b = self._run_with_item("item-b")
        self._seed_log("log-a-1", rank=1, task_id=task_a)
        self._seed_log("log-a-2", rank=2, task_id=task_a)
        self._seed_log("log-b-1", rank=3, task_id=task_b)
        self._seed_log("log-b-2", rank=4, task_id=task_b)
        # Plan-ID-only: shared history that no run is allowed to claim.
        self._seed_log("log-plan-only", rank=5)
        # Same task, different plan: the plan join still excludes it.
        self._seed_log("log-a-other-plan", rank=6, task_id=task_a, plan_id="other-plan")

        # Repository: plan ID alone is refused; each linkage returns exactly
        # its own rows newest-first.
        self.assertEqual(self.repository.list_operational_logs_for_plan(SHARED_PLAN), ())
        self.assertEqual(
            [
                record.log_id
                for record in self.repository.list_operational_logs_for_plan(
                    SHARED_PLAN, task_id=task_a
                )
            ],
            ["log-a-2", "log-a-1"],
        )
        self.assertEqual(
            [
                record.log_id
                for record in self.repository.list_operational_logs_for_plan(
                    SHARED_PLAN, task_id=task_b
                )
            ],
            ["log-b-2", "log-b-1"],
        )

        evidence_a = self._evidence(task_a, "item-a")
        evidence_b = self._evidence(task_b, "item-b")
        self.assertEqual(
            [row["record_id"] for row in evidence_a["logs"]], ["log:log-a-2", "log:log-a-1"]
        )
        self.assertEqual(
            [row["record_id"] for row in evidence_b["logs"]], ["log:log-b-2", "log:log-b-1"]
        )
        for evidence in (evidence_a, evidence_b):
            all_ids = {row["record_id"] for row in evidence["logs"]}
            self.assertNotIn("log:log-plan-only", all_ids)
            self.assertNotIn("log:log-a-other-plan", all_ids)
            self.assertEqual(len(evidence["results"]), 1)

    def test_job_stamped_plan_log_is_claimed_through_the_persisted_job_link(self) -> None:
        task_a = self._run_with_item("item-a")
        task_b = self._run_with_item("item-b")
        job_id = f"job-{uuid.uuid4().hex[:10]}"
        self.repository.create_job(job(job_id, task_id=task_a))
        self._seed_log("log-task-a", rank=1, task_id=task_a)
        self._seed_log("log-job-a", rank=2, job_id=job_id)
        self._seed_log("log-task-b", rank=3, task_id=task_b)

        # Both the Job anchor and the supported Task anchor resolve to the
        # same run and claim both linked rows (occurred_at DESC).
        for run_id in (job_id, task_a):
            evidence = self._evidence(run_id, "item-a")
            self.assertEqual(
                [row["record_id"] for row in evidence["logs"]],
                ["log:log-job-a", "log:log-task-a"],
            )
            self.assertNotIn("log:log-task-b", {row["record_id"] for row in evidence["logs"]})

        # A task-only read does not claim the job-stamped row, and a job-only
        # read does not claim the task-stamped row: linkage is exact, per ID.
        self.assertEqual(
            [
                r.log_id
                for r in self.repository.list_operational_logs_for_plan(SHARED_PLAN, task_id=task_a)
            ],
            ["log-task-a"],
        )
        self.assertEqual(
            [
                r.log_id
                for r in self.repository.list_operational_logs_for_plan(SHARED_PLAN, job_id=job_id)
            ],
            ["log-job-a"],
        )
        evidence_b = self._evidence(task_b, "item-b")
        self.assertEqual([row["record_id"] for row in evidence_b["logs"]], ["log:log-task-b"])

    def test_removing_the_other_runs_log_linkage_erasures_nothing_of_this_run(
        self,
    ) -> None:
        task_a = self._run_with_item("item-a")
        task_b = self._run_with_item("item-b")
        self._seed_log("log-a-1", rank=1, task_id=task_a)
        self._seed_log("log-a-2", rank=2, task_id=task_a)
        self._seed_log("log-b-1", rank=3, task_id=task_b)
        self._seed_log("log-b-2", rank=4, task_id=task_b)

        before_a = self._evidence(task_a, "item-a")
        self.assertEqual(
            [row["record_id"] for row in before_a["logs"]], ["log:log-a-2", "log:log-a-1"]
        )

        connection = self._raw()
        connection.execute("DELETE FROM operational_logs WHERE task_id = ?", (task_b,))
        connection.commit()

        # Run A's evidence is byte-for-byte unaffected by run B's loss.
        after_a = self._evidence(task_a, "item-a")
        self.assertEqual(after_a, before_a)

        # Run B keeps its Result and item checkpoint even with zero logs —
        # absent logs never erase a durable Result.
        after_b = self._evidence(task_b, "item-b")
        self.assertEqual(after_b["logs"], [])
        self.assertEqual(len(after_b["results"]), 1)
        self.assertEqual(after_b["results"][0]["item_id"], "item-b")
        self.assertEqual(after_b["results"][0]["task_id"], task_b)
        self.assertEqual(after_b["item"]["item_id"], "item-b")


if __name__ == "__main__":
    unittest.main()
