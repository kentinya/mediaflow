"""Files manual work actually runs on the Task scheduling kernel (Task 47.2).

Every assertion runs the real authenticated API, the real bounded-discovery
service, the real manual intent/Preview/execution chain and real Local Storage
over temporary roots, with the Task engine as the only Worker that advances
newly admitted Files work.
"""

from __future__ import annotations

import unittest
from dataclasses import replace
from unittest import mock

from mediaflow.application.strategy_test import SyntheticMetadataProvider
from mediaflow.domain.manual_execution import (
    ManualExecutionItemStatus,
    ManualExecutionStatus,
)
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.organizer import ExecutionEffectCertainty, ExecutionStatus
from mediaflow.domain.task_persistence import PersistentTaskStatus, TaskItemStatus
from mediaflow.domain.task_scheduling import TaskQueueState
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from tests.test_media_discovery import _DiscoveryFixture

REQUEST_ID = "11111111-1111-4111-8111-111111111111"


class ManualTaskDiscoveryTests(_DiscoveryFixture):
    def _admit(self, value, paths, *, auto_prepare=True):
        return self.request(
            value,
            "/api/v1/resource-libraries/library/files/discoveries",
            "POST",
            {"paths": list(paths), "autoPrepare": auto_prepare, "requestId": REQUEST_ID},
        )

    def _drive(self, value, task_id, *, steps=12):
        for _ in range(steps):
            value.task_engine.run_next()
            discovery = value.repository.get_media_discovery_for_task(task_id)
            state = value.repository.get_task_scheduling(task_id)
            if discovery is None or state is None:
                continue
            if state.queue_state in {
                TaskQueueState.WAITING_HUMAN,
                TaskQueueState.PAUSED,
                TaskQueueState.SETTLED,
            }:
                return discovery
        return value.repository.get_media_discovery_for_task(task_id)

    def test_new_files_discovery_runs_as_one_task_until_human_confirmation(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey(task_scheduling=True) as value:
            status, document = self._admit(value, ["Movies"])
            self.assertEqual(202, status, document)
            task_id = document["organizeTaskId"]
            state = value.repository.get_task_scheduling(task_id)
            self.assertIsNotNone(state)
            self.assertIs(state.queue_state, TaskQueueState.QUEUED)
            self.assertEqual(state.admission_request_id, REQUEST_ID)

            discovery = self._drive(value, task_id)
            task = value.repository.get_task(task_id)
            state = value.repository.get_task_scheduling(task_id)
            self.assertEqual(discovery.organize_task_id, task_id)
            self.assertIsNotNone(discovery.preview_id)
            self.assertEqual(task.status, PersistentTaskStatus.RUNNING)
            self.assertIs(state.queue_state, TaskQueueState.WAITING_HUMAN)
            self.assertFalse(state.holds_capacity)
            self.assertEqual(value.repository.count_scheduled_capacity_use(), 0)
            # Discovery/analysis is metadata-only: nothing was mutated and the
            # admitted Task identity never changed.
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            # No legacy Job was created for this work.
            self.assertEqual((), value.repository.list_jobs(limit=10))

    def test_files_pause_and_resume_are_retired_with_no_effect(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey(task_scheduling=True) as value:
            status, admitted = self._admit(value, ["Movies"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = value.repository.get_media_discovery_for_task(task_id)
            before_status = value.repository.get_task(task_id).status
            before_state = value.repository.get_task_scheduling(task_id).queue_state
            self.assertEqual(1, value.repository.count_scheduled_capacity_use())

            for action in ("pause", "resume"):
                status, refused = self.request(
                    value,
                    f"/api/v1/operations/organize/discoveries/{discovery.discovery_id}/{action}",
                    "POST",
                    {"expectedVersion": discovery.version},
                )
                self.assertEqual(409, status, refused)
                self.assertEqual("pause_retired", refused["error"]["code"])
                self.assertEqual("none", refused["error"]["details"]["sideEffects"])
            # The retirement is a bounded refusal with no durable effect: the
            # Task identity, its slot and the discovery are exactly as admitted.
            self.assertIs(value.repository.get_task(task_id).status, before_status)
            self.assertIs(value.repository.get_task_scheduling(task_id).queue_state, before_state)
            self.assertEqual(1, value.repository.count_scheduled_capacity_use())
            self.assertEqual([], value.source.mutations)
            # The untouched work still advances to its human boundary.
            driven = self._drive(value, task_id)
            self.assertEqual(task_id, driven.organize_task_id)
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.WAITING_HUMAN,
            )

    def test_task_center_pause_and_resume_are_retired_with_no_effect(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey(task_scheduling=True) as value:
            status, admitted = self._admit(value, ["Movies"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            task = value.repository.get_task(task_id)
            # The Task Center projection no longer advertises pause or resume:
            # the retired controls are absent, not merely withheld.
            status, detail = self.request(value, f"/api/v1/tasks/{task_id}")
            self.assertEqual(200, status, detail)
            action_names = {action["action"] for action in detail["lifecycle"]["actions"]}
            self.assertEqual({"cancel"}, action_names)

            for action in ("pause", "resume"):
                status, refused = self.request(
                    value,
                    f"/api/v1/tasks/{task_id}/{action}",
                    "POST",
                    {"expectedUpdatedAt": task.updated_at.isoformat()},
                )
                self.assertEqual(409, status, refused)
                self.assertEqual("pause_retired", refused["error"]["code"])
            # No requested state, no released slot and no new Worker work.
            self.assertIs(
                value.repository.get_task(task_id).status,
                PersistentTaskStatus.PENDING,
            )
            self.assertEqual(1, value.repository.count_scheduled_capacity_use())
            driven = self._drive(value, task_id)
            self.assertEqual(task_id, driven.organize_task_id)

    def test_pausing_human_waiting_work_is_retired_and_keeps_waiting(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey(task_scheduling=True) as value:
            status, admitted = self._admit(value, ["Movies"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            self._drive(value, task_id)
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.WAITING_HUMAN,
            )

            task = value.repository.get_task(task_id)
            status, refused = self.request(
                value,
                f"/api/v1/tasks/{task_id}/pause",
                "POST",
                {"expectedUpdatedAt": task.updated_at.isoformat()},
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("pause_retired", refused["error"]["code"])
            # Human-waiting work keeps its own state and slot (zero machine
            # slots) with no pause recorded and no Storage mutation.
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.WAITING_HUMAN,
            )
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertEqual([], value.source.mutations)

    def test_accepted_cancel_is_final_and_keeps_the_task_settled(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey(task_scheduling=True) as value:
            status, admitted = self._admit(value, ["Movies"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = value.repository.get_media_discovery_for_task(task_id)

            status, cancelled = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{discovery.discovery_id}/cancel",
                "POST",
                {"expectedVersion": discovery.version},
            )
            self.assertEqual(200, status, cancelled)
            state = value.repository.get_task_scheduling(task_id)
            self.assertIs(state.queue_state, TaskQueueState.SETTLED)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertIs(value.repository.get_task(task_id).status, PersistentTaskStatus.CANCELLED)
            # The accepted cancellation is never turned back into runnable work
            # by a later Worker pass.
            self.assertIsNone(value.task_engine.run_next())
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.SETTLED,
            )

    def test_duplicate_admission_converges_even_at_capacity(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey(task_scheduling=True) as value:
            first_status, first = self._admit(value, ["Movies"])
            self.assertEqual(202, first_status, first)
            # The same principal/request identity is an exact repeat: it must
            # read back the original Task instead of minting a second one.
            second_status, second = self._admit(value, ["Movies"])
            self.assertEqual(202, second_status, second)
            self.assertEqual(first["organizeTaskId"], second["organizeTaskId"])
            self.assertEqual(value.repository.count_scheduled_capacity_use(), 1)

    def test_confirmation_adopts_the_same_task_and_executes(self) -> None:
        self.media("Movies/One.2001.mkv")
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate(
                    "tmdb",
                    "201",
                    MediaType.MOVIE,
                    "One",
                    year=2001,
                    genres=("Animation",),
                    countries=("JP",),
                ),
            )
        )
        with self.journey(provider=provider, task_scheduling=True) as value:
            status, admitted = self._admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = self._drive(value, task_id)
            self.assertEqual(
                "waiting_human", value.repository.get_task_scheduling(task_id).queue_state.value
            )
            item = value.repository.list_items(task_id)[0]
            self.assertEqual("waiting_recognition", item.status.value)

            status, checkpoint = self.request(
                value, f"/api/v1/tasks/{task_id}/items/{item.item_id}"
            )
            self.assertEqual(200, status, checkpoint)
            status, decision = self.request(
                value,
                f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery/decision",
                "POST",
                {
                    "kind": "recognition",
                    "expectedCheckpointVersion": checkpoint["checkpoint_version"],
                    "recognitionTypeId": "A",
                },
            )
            self.assertEqual(200, status, decision)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            current = value.repository.get_media_discovery(discovery.discovery_id)
            status, accepted = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{discovery.discovery_id}/analyze",
                "POST",
                {"expectedVersion": current.version},
            )
            self.assertEqual(200, status, accepted)
            discovery = self._drive(value, task_id)
            task = value.repository.get_task(task_id)
            self.assertEqual(task.task_id, task_id)
            self.assertIsNotNone(discovery.preview_id)

            status, preview = self.request(
                value,
                f"/api/v1/operations/organize/previews/{discovery.preview_id}",
            )
            self.assertEqual(200, status, preview)
            ready = [
                value["itemId"] for value in preview["items"] if value["status"] == "previewed"
            ]
            self.assertEqual(1, len(ready), preview)

            status, admitted_execution = self.request(
                value,
                f"/api/v1/operations/organize/previews/{discovery.preview_id}/execute",
                "POST",
                {
                    "confirmation": True,
                    "itemIds": ready,
                    "expectedIntentVersion": preview["intentVersion"],
                    "allowOverwrite": False,
                    "allowSourceCleanup": False,
                },
            )
            self.assertIn(status, (200, 202), admitted_execution)
            # The confirmation re-registered the same Task for execution.
            state = value.repository.get_task_scheduling(task_id)
            self.assertIn(state.queue_state, {TaskQueueState.QUEUED, TaskQueueState.CLAIMED})
            for _ in range(8):
                value.task_engine.run_next()
                task = value.repository.get_task(task_id)
                if task.status in {
                    PersistentTaskStatus.COMPLETED,
                    PersistentTaskStatus.PARTIAL_SUCCESS,
                    PersistentTaskStatus.FAILED,
                }:
                    break
            task = value.repository.get_task(task_id)
            state = value.repository.get_task_scheduling(task_id)
            self.assertEqual(task.status, PersistentTaskStatus.COMPLETED, task.error)
            self.assertIs(state.queue_state, TaskQueueState.SETTLED)
            self.assertEqual(value.repository.count_scheduled_capacity_use(), 0)
            self.assertEqual(
                ["create_directory", "write"],
                [kind for kind, _path in value.target.mutations],
                value.target.mutations,
            )
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())

    def _two_file_recognition_journey(self):
        for name in ("One.2001.mkv", "Two.2002.mkv"):
            self.media(f"Movies/{name}")
        provider = SyntheticMetadataProvider(
            tuple(
                MediaCandidate(
                    "tmdb",
                    str(201 + index),
                    MediaType.MOVIE,
                    title,
                    year=2001 + index,
                    genres=("Animation",),
                    countries=("JP",),
                )
                for index, title in enumerate(("One", "Two"))
            )
        )
        return provider

    def _decide_recognition(self, value, task_id, item, recognition_type_id="A"):
        status, checkpoint = self.request(value, f"/api/v1/tasks/{task_id}/items/{item.item_id}")
        self.assertEqual(200, status, checkpoint)
        status, decision = self.request(
            value,
            f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery/decision",
            "POST",
            {
                "kind": "recognition",
                "expectedCheckpointVersion": checkpoint["checkpoint_version"],
                "recognitionTypeId": recognition_type_id,
            },
        )
        self.assertEqual(200, status, decision)

    def _execute(self, value, task_id, preview, item_ids, *, steps=8):
        status, admitted = self.request(
            value,
            f"/api/v1/operations/organize/previews/{preview['previewId']}/execute",
            "POST",
            {
                "confirmation": True,
                "itemIds": list(item_ids),
                "expectedIntentVersion": preview["intentVersion"],
                "allowOverwrite": False,
                "allowSourceCleanup": False,
            },
        )
        self.assertIn(status, (200, 202), admitted)
        for _ in range(steps):
            value.task_engine.run_next()
            task = value.repository.get_task(task_id)
            if task.status in {
                PersistentTaskStatus.COMPLETED,
                PersistentTaskStatus.PARTIAL_SUCCESS,
                PersistentTaskStatus.FAILED,
                PersistentTaskStatus.CANCELLED,
            }:
                break
        return value.repository.get_task(task_id)

    def test_partial_recognition_decision_keeps_the_undecided_sibling_actionable(self) -> None:
        """Only the decided subset is confirmed; the undecided sibling stays open.

        The operator picks two files whose RecognitionType is unresolved, decides
        only the first, and reruns the analysis.  The ready subset must be
        confirmable while the still-undecided sibling keeps its own pending review
        and waiting item on the same Task.  After the first Result is persisted the
        second source is decided, analyzed and continued on the same Task without
        replaying the first.
        """

        provider = self._two_file_recognition_journey()
        with self.journey(provider=provider, task_scheduling=True) as value:
            status, admitted = self._admit(value, ["Movies/One.2001.mkv", "Movies/Two.2002.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = self._drive(value, task_id)
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.WAITING_HUMAN,
            )
            items = {item.source_path: item for item in value.repository.list_items(task_id)}
            self.assertEqual(2, len(items))
            first = items["Movies/One.2001.mkv"]
            second = items["Movies/Two.2002.mkv"]
            self.assertIs(first.status, TaskItemStatus.WAITING_RECOGNITION)
            self.assertIs(second.status, TaskItemStatus.WAITING_RECOGNITION)

            self._decide_recognition(value, task_id, first)

            current = value.repository.get_media_discovery(discovery.discovery_id)
            status, accepted = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{discovery.discovery_id}/analyze",
                "POST",
                {"expectedVersion": current.version},
            )
            self.assertEqual(200, status, accepted)
            discovery = self._drive(value, task_id)
            state = value.repository.get_task_scheduling(task_id)
            self.assertIs(state.queue_state, TaskQueueState.WAITING_HUMAN, state)
            self.assertFalse(state.holds_capacity)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            # The undecided sibling is never turned into a stuck processing item; it
            # keeps its own pending review and remains actionable on the same Task.
            items = {item.source_path: item for item in value.repository.list_items(task_id)}
            self.assertIs(items["Movies/Two.2002.mkv"].status, TaskItemStatus.WAITING_RECOGNITION)
            pending = value.repository.get_recognition_review_for_item(second.item_id)
            self.assertIsNotNone(pending)
            self.assertEqual("pending", pending.status.value)

            status, preview = self.request(
                value,
                f"/api/v1/operations/organize/previews/{discovery.preview_id}",
            )
            self.assertEqual(200, status, preview)
            ready = [item["itemId"] for item in preview["items"] if item["status"] == "previewed"]
            self.assertEqual(1, len(ready), preview)

            # Confirm and execute only the ready first source.
            first_execution = self._execute(value, task_id, preview, ready)
            self.assertIs(
                first_execution.status, PersistentTaskStatus.RUNNING, first_execution.error
            )
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.WAITING_HUMAN,
            )
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            items = {item.source_path: item for item in value.repository.list_items(task_id)}
            self.assertIs(items["Movies/One.2001.mkv"].status, TaskItemStatus.SUCCESS)
            self.assertIs(items["Movies/Two.2002.mkv"].status, TaskItemStatus.WAITING_RECOGNITION)
            self.assertEqual(1, len(value.repository.list_results(task_id)))
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())
            # The top-level Task never loses the outstanding sibling, so it is not
            # settled merely because one confirmed subset finished.
            first_result = value.repository.list_results(task_id)[0]

            # Decide the second source and continue it on the same Task.
            self._decide_recognition(value, task_id, second)
            current = value.repository.get_media_discovery(discovery.discovery_id)
            status, accepted = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{discovery.discovery_id}/analyze",
                "POST",
                {"expectedVersion": current.version},
            )
            self.assertEqual(200, status, accepted)
            discovery = self._drive(value, task_id)
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.WAITING_HUMAN,
            )
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            status, preview = self.request(
                value,
                f"/api/v1/operations/organize/previews/{discovery.preview_id}",
            )
            self.assertEqual(200, status, preview)
            second_ready = [
                item["itemId"] for item in preview["items"] if item["status"] == "previewed"
            ]
            self.assertEqual(1, len(second_ready), preview)
            self.assertNotEqual(set(ready), set(second_ready))

            final = self._execute(value, task_id, preview, second_ready)
            self.assertIs(final.status, PersistentTaskStatus.COMPLETED, final.error)
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.SETTLED,
            )
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            results = value.repository.list_results(task_id)
            self.assertEqual(2, len(results), results)
            # The first source's Result is neither replayed nor overwritten.
            self.assertIn(first_result.result_id, {value.result_id for value in results})
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())
            self.assertFalse((self.source_root / "Movies/Two.2002.mkv").exists())

            with SQLiteTaskRepository(self.database) as reopened:
                reopened_task = reopened.get_task(task_id)
                self.assertEqual(reopened_task.task_id, task_id)
                self.assertIs(reopened_task.status, PersistentTaskStatus.COMPLETED)
                self.assertEqual(2, len(reopened.list_results(task_id)))
                self.assertIs(
                    reopened.get_task_scheduling(task_id).queue_state, TaskQueueState.SETTLED
                )

    def test_cancel_during_first_execution_settles_the_task_and_execution(self) -> None:
        """A real two-file run observes cancellation at the next item boundary.

        The first OrganizerExecutor call completes and publishes its own Result
        while the operator cancels from the existing Task route.  The in-flight
        call is not interrupted, the successful sibling keeps its effect/Result,
        and the not-yet-started sibling plus the Task/execution settle as a
        normal cancellation instead of a technical failure.
        """

        for name in ("One.2001.mkv", "Two.2002.mkv"):
            self.media(f"Movies/{name}")
        provider = SyntheticMetadataProvider(
            tuple(
                MediaCandidate(
                    "tmdb",
                    str(201 + index),
                    MediaType.MOVIE,
                    title,
                    year=2001 + index,
                    genres=("Animation",),
                    countries=("JP",),
                )
                for index, title in enumerate(("One", "Two"))
            )
        )
        with self.journey(provider=provider, task_scheduling=True) as value:
            status, admitted = self._admit(value, ["Movies/One.2001.mkv", "Movies/Two.2002.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = self._drive(value, task_id)
            for item in value.repository.list_items(task_id):
                status, checkpoint = self.request(
                    value, f"/api/v1/tasks/{task_id}/items/{item.item_id}"
                )
                self.assertEqual(200, status, checkpoint)
                status, decision = self.request(
                    value,
                    f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery/decision",
                    "POST",
                    {
                        "kind": "recognition",
                        "expectedCheckpointVersion": checkpoint["checkpoint_version"],
                        "recognitionTypeId": "A",
                    },
                )
                self.assertEqual(200, status, decision)
            current = value.repository.get_media_discovery(discovery.discovery_id)
            status, accepted = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{discovery.discovery_id}/analyze",
                "POST",
                {"expectedVersion": current.version},
            )
            self.assertEqual(200, status, accepted)
            discovery = self._drive(value, task_id)
            status, preview = self.request(
                value,
                f"/api/v1/operations/organize/previews/{discovery.preview_id}",
            )
            self.assertEqual(200, status, preview)
            ready = [item["itemId"] for item in preview["items"] if item["status"] == "previewed"]
            self.assertEqual(2, len(ready), preview)
            status, execution = self.request(
                value,
                f"/api/v1/operations/organize/previews/{discovery.preview_id}/execute",
                "POST",
                {
                    "confirmation": True,
                    "itemIds": ready,
                    "expectedIntentVersion": preview["intentVersion"],
                    "allowOverwrite": False,
                    "allowSourceCleanup": False,
                },
            )
            self.assertIn(status, (200, 202), execution)

            original = value.executions._execute_plan
            executed = []
            cancellation = []

            def execute_then_cancel(plan, storages):
                result = original(plan, storages)
                executed.append(plan.source)
                if len(executed) == 1:
                    task = value.repository.get_task(task_id)
                    code, reply = self.request(
                        value,
                        f"/api/v1/tasks/{task_id}/cancel",
                        "POST",
                        {"expectedUpdatedAt": task.updated_at.isoformat()},
                    )
                    cancellation.append((code, reply))
                return result

            with mock.patch.object(
                value.executions, "_execute_plan", side_effect=execute_then_cancel
            ):
                value.task_engine.run_next()
            for _ in range(4):
                value.task_engine.run_next()

            self.assertEqual(1, len(cancellation), cancellation)
            self.assertEqual(200, cancellation[0][0], cancellation[0][1])
            self.assertEqual(["Movies/One.2001.mkv"], executed)
            task = value.repository.get_task(task_id)
            state = value.repository.get_task_scheduling(task_id)
            self.assertIs(task.status, PersistentTaskStatus.CANCELLED)
            self.assertIs(state.queue_state, TaskQueueState.SETTLED)
            self.assertFalse(state.holds_capacity)
            self.assertFalse(state.mutation_in_flight)
            self.assertIsNotNone(state.control_acknowledged_at)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            items = value.repository.list_items(task_id)
            self.assertEqual(
                {
                    "Movies/One.2001.mkv": TaskItemStatus.SUCCESS,
                    "Movies/Two.2002.mkv": TaskItemStatus.CANCELLED,
                },
                {item.source_path: item.status for item in items},
            )
            self.assertEqual(1, len(value.repository.list_results(task_id)))
            executions = value.repository.list_manual_executions_for_task(task_id)
            self.assertEqual(1, len(executions))
            self.assertIs(executions[0].status, ManualExecutionStatus.CANCELLED)
            self.assertEqual(
                {
                    "Movies/One.2001.mkv": ManualExecutionItemStatus.SUCCESS,
                    "Movies/Two.2002.mkv": ManualExecutionItemStatus.CANCELLED,
                },
                {item.source.path: item.status for item in executions[0].items},
            )
            unfinished = next(
                item for item in executions[0].items if item.source.path == "Movies/Two.2002.mkv"
            )
            self.assertEqual("none", unfinished.effect_certainty)
            self.assertIsNone(unfinished.result_id)
            self.assertEqual(
                ["create_directory", "write"],
                [kind for kind, _path in value.target.mutations],
                value.target.mutations,
            )
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())
            self.assertTrue((self.source_root / "Movies/Two.2002.mkv").exists())
            # A cancelled Task is never re-queued or replayed by later passes.
            self.assertIsNone(value.task_engine.run_next())
            self.assertEqual(1, len(value.repository.list_results(task_id)))

            with SQLiteTaskRepository(self.database) as reopened:
                reopened_task = reopened.get_task(task_id)
                reopened_state = reopened.get_task_scheduling(task_id)
                self.assertIs(reopened_task.status, PersistentTaskStatus.CANCELLED)
                self.assertIs(reopened_state.queue_state, TaskQueueState.SETTLED)
                self.assertIs(
                    reopened.list_manual_executions_for_task(task_id)[0].status,
                    ManualExecutionStatus.CANCELLED,
                )

    def test_cancel_does_not_clear_an_uncertain_current_effect(self) -> None:
        """An accepted cancel never converts an unknown effect into a settlement.

        The first real Executor call returns an uncertain outcome while the
        operator cancels.  The Task keeps its claim, shared slot and mutation
        marker for inspection; the not-yet-started sibling is not run and the
        accepted cancel is never cleared, downgraded or replayed.
        """

        for name in ("One.2001.mkv", "Two.2002.mkv"):
            self.media(f"Movies/{name}")
        provider = SyntheticMetadataProvider(
            tuple(
                MediaCandidate(
                    "tmdb",
                    str(201 + index),
                    MediaType.MOVIE,
                    title,
                    year=2001 + index,
                    genres=("Animation",),
                    countries=("JP",),
                )
                for index, title in enumerate(("One", "Two"))
            )
        )
        with self.journey(provider=provider, task_scheduling=True) as value:
            status, admitted = self._admit(value, ["Movies/One.2001.mkv", "Movies/Two.2002.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = self._drive(value, task_id)
            for item in value.repository.list_items(task_id):
                status, checkpoint = self.request(
                    value, f"/api/v1/tasks/{task_id}/items/{item.item_id}"
                )
                self.assertEqual(200, status, checkpoint)
                status, decision = self.request(
                    value,
                    f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery/decision",
                    "POST",
                    {
                        "kind": "recognition",
                        "expectedCheckpointVersion": checkpoint["checkpoint_version"],
                        "recognitionTypeId": "A",
                    },
                )
                self.assertEqual(200, status, decision)
            current = value.repository.get_media_discovery(discovery.discovery_id)
            status, accepted = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{discovery.discovery_id}/analyze",
                "POST",
                {"expectedVersion": current.version},
            )
            self.assertEqual(200, status, accepted)
            discovery = self._drive(value, task_id)
            status, preview = self.request(
                value,
                f"/api/v1/operations/organize/previews/{discovery.preview_id}",
            )
            self.assertEqual(200, status, preview)
            ready = [item["itemId"] for item in preview["items"] if item["status"] == "previewed"]
            status, execution = self.request(
                value,
                f"/api/v1/operations/organize/previews/{discovery.preview_id}/execute",
                "POST",
                {
                    "confirmation": True,
                    "itemIds": ready,
                    "expectedIntentVersion": preview["intentVersion"],
                    "allowOverwrite": False,
                    "allowSourceCleanup": False,
                },
            )
            self.assertIn(status, (200, 202), execution)

            original = value.executions._execute_plan
            executed = []
            cancellation = []

            def execute_unknown(plan, storages):
                result = original(plan, storages)
                executed.append(plan.source)
                if len(executed) == 1:
                    task = value.repository.get_task(task_id)
                    code, reply = self.request(
                        value,
                        f"/api/v1/tasks/{task_id}/cancel",
                        "POST",
                        {"expectedUpdatedAt": task.updated_at.isoformat()},
                    )
                    cancellation.append((code, reply))
                    return replace(
                        result,
                        status=ExecutionStatus.PARTIAL,
                        errors=("synthetic uncertain executor outcome",),
                        effect_certainty=ExecutionEffectCertainty.UNKNOWN,
                        uncertain_effects=("synthetic_unknown",),
                    )
                return result

            with mock.patch.object(value.executions, "_execute_plan", side_effect=execute_unknown):
                value.task_engine.run_next()
            for _ in range(3):
                value.task_engine.run_next()

            self.assertEqual(1, len(cancellation), cancellation)
            self.assertEqual(200, cancellation[0][0], cancellation[0][1])
            self.assertEqual(["Movies/One.2001.mkv"], executed)
            task = value.repository.get_task(task_id)
            state = value.repository.get_task_scheduling(task_id)
            self.assertIs(task.status, PersistentTaskStatus.RUNNING)
            self.assertIs(state.queue_state, TaskQueueState.CLAIMED)
            self.assertTrue(state.holds_capacity)
            self.assertTrue(state.mutation_in_flight)
            self.assertEqual(1, value.repository.count_scheduled_capacity_use())
            self.assertEqual(1, len(value.repository.list_results(task_id)))
            items = value.repository.list_items(task_id)
            self.assertEqual(
                {
                    "Movies/One.2001.mkv": TaskItemStatus.PARTIAL,
                    "Movies/Two.2002.mkv": TaskItemStatus.PENDING,
                },
                {item.source_path: item.status for item in items},
            )
            executions = value.repository.list_manual_executions_for_task(task_id)
            self.assertIs(executions[0].status, ManualExecutionStatus.RUNNING)
            self.assertEqual(
                {
                    "Movies/One.2001.mkv": ManualExecutionItemStatus.PARTIAL,
                    "Movies/Two.2002.mkv": ManualExecutionItemStatus.ADMITTED,
                },
                {item.source.path: item.status for item in executions[0].items},
            )
            self.assertEqual(
                ["create_directory", "write"],
                [kind for kind, _path in value.target.mutations],
                value.target.mutations,
            )
            self.assertTrue((self.source_root / "Movies/Two.2002.mkv").exists())


if __name__ == "__main__":
    unittest.main()
