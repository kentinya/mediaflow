"""Task47.3 — one verified source has at most one unfinished automatic owner.

B review `62ebf673` reproduced the real race on the Run once entrance: two
legitimate admissions, two real resident Workers, both passed the read-only
source-ownership query and both registered the same verified source as their
own waiting work.  These tests hold that exact boundary and prove the decisive
decision is one repository transaction — the live claim check, the shared
source-ownership check and the TaskItem start write together — so the losing
work records its own bounded ``source_already_organizing`` refusal instead of
a second operable item for the same file.

The journeys run the real ``MediaFlowApi`` Run once admission, the real
``ManualTaskEngineWorker`` consumer and the production ``_automatic_task_runner``
over temporary Local Storage; the race is reproduced by holding both Workers at
the real read-only ownership query (a dependency boundary the actual call chain
crosses), never by inventing an endpoint.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from mediaflow.application.manual_task_engine import ManualTaskEngineWorker
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.strategy_test import SyntheticMetadataProvider
from mediaflow.application.task_scheduling import TaskSchedulingService
from mediaflow.domain.task_persistence import PersistentTaskItem, TaskItemStatus
from mediaflow.domain.task_scheduling import (
    TaskItemPublication,
    TaskQueueState,
    TaskSchedulingError,
    TaskTrigger,
)
from mediaflow.final_cli import _automatic_task_runner
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from tests import test_v2_automation_run_once as run_once_tests


class RunOnceSourceOwnershipTests(unittest.TestCase):
    """Cross-Task source ownership through the real automatic entrances."""

    def setUp(self) -> None:
        # Reuse the real Run once API fixture (temporary SQLite/Storage, real
        # managed revision store) without re-running its own test methods.
        self.case = run_once_tests.RunOnceApiTests(methodName="journey")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def _workers(self, value, scheduling):
        """Two real resident Workers over the fixture's repository."""

        workers = []
        for number in range(2):
            worker_id = f"ownership-worker-{number}"
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
            workers.append(
                ManualTaskEngineWorker(
                    value.repository,
                    scheduling,
                    None,
                    None,
                    worker_id=worker_id,
                    clock=value.clock,
                    automatic_runner=_automatic_task_runner(value.repository, None, scheduling),
                )
            )
        return workers

    def _run_both(self, value, service, workers, admitted, intercepted_path):
        """Advance both real Workers with their read checks held together."""

        barrier = Barrier(2)
        real_finder = value.repository.find_owned_source_work
        prechecks: list[tuple[str, bool]] = []

        def interleaved_precheck(**kwargs):
            answer = real_finder(**kwargs)
            if (
                kwargs.get("exclude_task_id") in admitted
                and kwargs.get("source_path") == intercepted_path
            ):
                prechecks.append((kwargs["exclude_task_id"], answer is None))
                if answer is None:
                    # Hold both Workers exactly at the read-only pre-check, so
                    # both really reach the decisive registration while the
                    # source is still unowned.
                    barrier.wait(timeout=10)
            return answer

        with (
            patch("mediaflow.final_cli._configuration", return_value=value.runtime),
            patch("mediaflow.final_cli._definition_scoped_service", return_value=service),
            patch.object(value.repository, "find_owned_source_work", interleaved_precheck),
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                list(executor.map(lambda worker: worker.run_next(), workers))
        return prechecks

    def test_concurrent_run_once_workers_admit_one_owner_per_verified_source(self) -> None:
        """Both Workers pass the read query; only one atomic registration wins."""

        case = self.case
        case.media("One.2001.mkv")
        # No recognition rule keeps the winner's item in its human-waiting
        # state, which is exactly the unfinished ownership under test.
        case.change_document = lambda doc: doc.update(recognitionRules=[])
        with case.journey() as value:
            admitted = []
            for request_id in ("ownership-request-1", "ownership-request-2"):
                status, body = case.admit(value, request_id=request_id)
                self.assertEqual(202, status, body)
                admitted.append(body["taskId"])
            self.assertEqual(2, len(set(admitted)), admitted)

            scheduling = TaskSchedulingService(value.repository, capacity=100)
            service = self.case._run_once_service(
                value, lambda ids: MetadataProviderRegistry((SyntheticMetadataProvider(()),))
            )
            workers = self._workers(value, scheduling)
            prechecks = self._run_both(value, service, workers, admitted, "One.2001.mkv")

            # The race was real: both Tasks observed the source free.
            self.assertEqual(sorted(task_id for task_id, _free in prechecks), sorted(admitted))
            self.assertTrue(all(free for _task_id, free in prechecks), prechecks)

            items = [item for task_id in admitted for item in value.repository.list_items(task_id)]
            waiting = [item for item in items if item.status is TaskItemStatus.WAITING_RECOGNITION]
            failed = [item for item in items if item.status is TaskItemStatus.FAILED]
            self.assertEqual(
                1,
                len(waiting),
                [(item.task_id, item.status.value) for item in items],
            )
            self.assertEqual(
                1,
                len(failed),
                [(item.task_id, item.status.value) for item in items],
            )
            # Both attempts competed for the *same verified source occurrence*.
            self.assertEqual(waiting[0].source_path, failed[0].source_path)
            self.assertEqual(waiting[0].source_storage_path, failed[0].source_storage_path)
            self.assertEqual(waiting[0].source_occurrence_id, failed[0].source_occurrence_id)

            # The loser's own durable outcome is the existing bounded refusal:
            # a real failed item/Result with the closed-set reason and next
            # action, zero effects, and no reference to the winner's work.
            results = value.repository.list_results(failed[0].task_id)
            self.assertEqual(1, len(results))
            self.assertEqual("source_already_organizing", results[0].retry_category)
            self.assertEqual("none", results[0].effect_certainty)
            self.assertEqual((), results[0].uncertain_effects)
            self.assertNotIn(waiting[0].task_id, json.dumps(results[0].error or ""))
            self.assertNotIn(waiting[0].item_id, json.dumps(results[0].error or ""))

            # Exactly one unfinished owner remains for the verified source.
            owner = value.repository.find_owned_source_work(
                storage_id=waiting[0].storage_id,
                source_path=waiting[0].source_path,
                storage_path=waiting[0].source_storage_path,
                resource_library_id=waiting[0].resource_library_id,
            )
            self.assertIsNotNone(owner)
            self.assertEqual(waiting[0].task_id, owner["taskId"])

            # The winner keeps its human-waiting work; the loser settled.
            winner_state = value.repository.get_task_scheduling(waiting[0].task_id)
            self.assertIs(TaskQueueState.WAITING_HUMAN, winner_state.queue_state)

            # Neither attempt reached Provider or Storage.
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_sequential_second_run_once_refuses_only_the_owned_source(self) -> None:
        """A later run refuses the owned file and still processes free files."""

        case = self.case
        case.media("A/One.2001.mkv")
        case.media("B/Two.2002.mkv")

        def scoped_definitions(doc):
            doc.update(recognitionRules=[])
            doc["automationTaskDefinitions"] = [
                {
                    "id": "scope-a",
                    "name": "Scope A",
                    "resourceLibraryId": "library",
                    "mode": "automatic-organization",
                    "intervalSeconds": 3600,
                    "itemLimit": 10,
                    "enabled": False,
                    "sourceScope": "A",
                },
                {
                    "id": "scope-b",
                    "name": "Scope B",
                    "resourceLibraryId": "library",
                    "mode": "automatic-organization",
                    "intervalSeconds": 3600,
                    "itemLimit": 10,
                    "enabled": False,
                    "sourceScope": "B",
                },
            ]

        case.change_document = scoped_definitions
        with case.journey() as value:
            scheduling = TaskSchedulingService(value.repository, capacity=100)
            service = self.case._run_once_service(
                value, lambda ids: MetadataProviderRegistry((SyntheticMetadataProvider(()),))
            )
            workers = self._workers(value, scheduling)

            def admit_and_run(definition_id: str, request_id: str) -> str:
                active = value.managed.active()
                from mediaflow.domain.automation import AutomationTaskDefinition

                definition = next(
                    AutomationTaskDefinition.from_document(item)
                    for item in active.document["automationTaskDefinitions"]
                    if item.get("id") == definition_id
                )
                body = {
                    "admissionRequestId": request_id,
                    "expectedRevisionId": active.revision_id,
                    "expectedRevisionVersion": active.revision_sequence or active.version,
                    "expectedRevisionDigest": active.digest,
                    "expectedDefinitionFingerprint": definition.definition_fingerprint,
                }
                status, reply = case.request(
                    value,
                    "POST",
                    f"/api/v1/operations/automation/task-definitions/{definition_id}/run-once",
                    body,
                )
                self.assertEqual(202, status, reply)
                task_id = reply["taskId"]
                with (
                    patch("mediaflow.final_cli._configuration", return_value=value.runtime),
                    patch("mediaflow.final_cli._definition_scoped_service", return_value=service),
                ):
                    self.assertIsNotNone(workers[0].run_next())
                return task_id

            first = admit_and_run("scope-a", "11111111-1111-4111-8111-111111111111")
            second = admit_and_run("scope-b", "22222222-2222-4222-8222-222222222222")
            self.assertNotEqual(first, second)

            # The free file in the other scope was processed independently.
            second_items = value.repository.list_items(second)
            self.assertEqual(["B/Two.2002.mkv"], [item.source_path for item in second_items])
            self.assertIs(TaskItemStatus.WAITING_RECOGNITION, second_items[0].status)

            # A later run over the already-owned scope is admitted as its own
            # Task (overlapping outer scope is legitimate) but its concrete
            # source is refused bounded, with no second operable item.
            third = admit_and_run("scope-a", "33333333-3333-4333-8333-333333333333")
            third_items = value.repository.list_items(third)
            self.assertEqual(1, len(third_items))
            self.assertIs(TaskItemStatus.FAILED, third_items[0].status)
            results = value.repository.list_results(third)
            self.assertEqual(1, len(results))
            self.assertEqual("source_already_organizing", results[0].retry_category)
            self.assertEqual("none", results[0].effect_certainty)
            self.assertNotIn(first, json.dumps(results[0].error or ""))

            owner = value.repository.find_owned_source_work(
                storage_id=third_items[0].storage_id,
                source_path=third_items[0].source_path,
                storage_path=third_items[0].source_storage_path,
                resource_library_id=third_items[0].resource_library_id,
            )
            self.assertIsNotNone(owner)
            self.assertEqual(first, owner["taskId"])

            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_files_discovery_reservation_blocks_the_automatic_entrance(self) -> None:
        """An existing Files reservation keeps its source from a Run once Task."""

        case = self.case
        case.media("Movies/One.2001.mkv")
        case.change_document = lambda doc: doc.update(recognitionRules=[])
        with case.journey() as value:
            status, discovery = case.request(
                value,
                "POST",
                "/api/v1/resource-libraries/library/files/discoveries",
                {
                    "paths": ["Movies"],
                    "autoPrepare": True,
                    "requestId": "44444444-4444-4444-8444-444444444444",
                },
            )
            self.assertEqual(202, status, discovery)
            result = value.discovery.claim_and_run(
                worker_id="files-worker", claim_token="claim-files"
            )
            self.assertIsNotNone(result)

            # A later automatic run over the same library is a legitimate outer
            # admission, but the concrete source stays with the Files work.
            status, body = case.admit(value, request_id="55555555-5555-4555-8555-555555555555")
            self.assertEqual(202, status, body)
            task_id = body["taskId"]
            scheduling = TaskSchedulingService(value.repository, capacity=100)
            service = self.case._run_once_service(
                value, lambda ids: MetadataProviderRegistry((SyntheticMetadataProvider(()),))
            )
            workers = self._workers(value, scheduling)
            with (
                patch("mediaflow.final_cli._configuration", return_value=value.runtime),
                patch("mediaflow.final_cli._definition_scoped_service", return_value=service),
            ):
                self.assertIsNotNone(workers[0].run_next())

            items = value.repository.list_items(task_id)
            self.assertEqual(1, len(items))
            self.assertIs(TaskItemStatus.FAILED, items[0].status)
            results = value.repository.list_results(task_id)
            self.assertEqual(1, len(results))
            self.assertEqual("source_already_organizing", results[0].retry_category)
            self.assertEqual("none", results[0].effect_certainty)
            owner = value.repository.find_owned_source_work(
                storage_id=items[0].storage_id,
                source_path=items[0].source_path,
                storage_path=items[0].source_storage_path,
                resource_library_id=items[0].resource_library_id,
            )
            self.assertIsNotNone(owner)
            self.assertEqual("discovery", owner["kind"])
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)


class BeginScheduledItemOwnershipBoundaryTests(unittest.TestCase):
    """The decisive scheduled-item start keeps every existing protection.

    These tests hold the repository transaction itself: the claim fence, the
    shared source ownership and the item write resolve together, and every
    pre-existing scheduled-item rule (attempt advance, replay-safe history,
    settled siblings) still applies inside that same transaction.
    """

    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.database = Path(self._directory.name) / "runtime.sqlite3"
        self.repository = SQLiteTaskRepository(self.database)
        self.addCleanup(self._directory.cleanup)
        self.addCleanup(self.repository.close)
        self.now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        for worker in ("worker-1", "worker-2"):
            self.repository.register_worker(
                worker, worker, 5.0, ("organize",), None, None, SCHEMA_VERSION, self.now
            )
        self.scheduling = TaskSchedulingService(self.repository, capacity=5)

    def _admit(self, worker_id: str):
        admission = self.scheduling.admit(
            "organize",
            execute_authorized=True,
            trigger=TaskTrigger.RUN_ONCE,
            principal="automation",
            scope_path=None,
            item_limit=10,
            configuration_snapshot_id="snapshot-1",
            configuration_snapshot_digest="digest-1",
            now=self.now,
        )
        claim = self.scheduling.claim(admission.task.task_id, worker_id=worker_id, now=self.now)
        return admission.task.task_id, claim

    def _admit_and_begin(self, worker_id: str):
        task_id, claim = self._admit(worker_id)
        claim = self.scheduling.begin_work(claim, now=self.now)
        return task_id, claim

    def _item(
        self,
        task_id: str,
        source_path: str,
        *,
        attempts: int = 1,
        status: TaskItemStatus = TaskItemStatus.PROCESSING,
    ) -> PersistentTaskItem:
        item_id = str(uuid5(NAMESPACE_URL, f"{task_id}:local:{source_path}"))
        return PersistentTaskItem(
            item_id,
            task_id,
            "local",
            "library",
            source_path,
            source_path,
            status,
            "pipeline",
            attempts,
            self.now,
            self.now,
            source_storage_path=source_path,
        )

    def test_lost_claim_writes_no_item_or_attempt(self) -> None:
        """A stale fence is answered before any ownership or item write."""

        task_id, claim = self._admit("worker-1")
        # Another Worker takes the expired claim; the first fence is stale.
        later = self.now + timedelta(hours=1)
        self.repository.register_worker(
            "worker-2", "worker two", 5.0, ("organize",), None, None, SCHEMA_VERSION, later
        )
        stolen = self.scheduling.claim(task_id, worker_id="worker-2", now=later)
        self.assertIsNotNone(stolen)
        written, owner = self.repository.begin_scheduled_item_with_ownership(
            claim.fence(self.now),
            self._item(task_id, "A.mkv"),
        )
        self.assertFalse(written)
        self.assertIsNone(owner)
        self.assertEqual((), self.repository.list_items(task_id))

    def test_owned_source_refuses_without_writing_and_reports_the_owner(self) -> None:
        """The second Task writes nothing and learns only the fact of ownership."""

        first_id, first_claim = self._admit_and_begin("worker-1")
        self.scheduling.begin_item(
            first_claim,
            storage_id="local",
            resource_library_id="library",
            source_path="A.mkv",
            source_display="A.mkv",
            source_storage_path="A.mkv",
            now=self.now,
        )
        second_id, second_claim = self._admit_and_begin("worker-2")
        written, owner = self.repository.begin_scheduled_item_with_ownership(
            second_claim.fence(self.now),
            self._item(second_id, "A.mkv"),
        )
        self.assertFalse(written)
        self.assertIsNotNone(owner)
        self.assertEqual(first_id, owner["taskId"])
        self.assertEqual((), self.repository.list_items(second_id))

    def test_same_task_and_legal_lineage_never_refuse_themselves(self) -> None:
        """A legal continuation of the owning work is never its own competitor."""

        first_id, first_claim = self._admit_and_begin("worker-1")
        started = self.scheduling.begin_item(
            first_claim,
            storage_id="local",
            resource_library_id="library",
            source_path="A.mkv",
            source_display="A.mkv",
            source_storage_path="A.mkv",
            now=self.now,
        )
        # The owner's own analysis attempt failed without any effect; its
        # remaining work is the legal continuation of that same source.
        self.repository.upsert_scheduled_item(
            first_claim.fence(self.now),
            replace(
                started,
                status=TaskItemStatus.FAILED,
                stage="failed",
                updated_at=self.now,
            ),
            stage=TaskItemPublication.OUTCOME,
        )
        written, owner = self.repository.begin_scheduled_item_with_ownership(
            first_claim.fence(self.now),
            self._item(first_id, "A.mkv", attempts=2),
        )
        self.assertTrue(written)
        self.assertIsNone(owner)

        # A different Task is only admitted when the lineage is legal: the
        # ancestor's remaining scope is the continuation's own source.
        second_id, second_claim = self._admit_and_begin("worker-2")
        written, owner = self.repository.begin_scheduled_item_with_ownership(
            second_claim.fence(self.now),
            self._item(second_id, "A.mkv"),
            exclude_lineage_task_id=first_id,
        )
        self.assertTrue(written)
        self.assertIsNone(owner)

    def test_settled_sibling_is_never_started_again_inside_the_transaction(self) -> None:
        """The attempt/outcome protections survive the combined boundary."""

        task_id, claim = self._admit_and_begin("worker-1")
        started = self.scheduling.begin_item(
            claim,
            storage_id="local",
            resource_library_id="library",
            source_path="A.mkv",
            source_display="A.mkv",
            source_storage_path="A.mkv",
            now=self.now,
        )
        self.repository.upsert_scheduled_item(
            claim.fence(self.now),
            replace(started, status=TaskItemStatus.SUCCESS, stage="completed", updated_at=self.now),
            stage=TaskItemPublication.OUTCOME,
        )
        with self.assertRaises(TaskSchedulingError):
            self.repository.begin_scheduled_item_with_ownership(
                claim.fence(self.now),
                self._item(task_id, "A.mkv", attempts=2),
            )
        stored = self.repository.get_item(started.item_id)
        self.assertEqual(1, stored.attempts)
        self.assertIs(TaskItemStatus.SUCCESS, stored.status)


if __name__ == "__main__":
    unittest.main()
