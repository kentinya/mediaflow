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
from mediaflow.domain.media_discovery import DiscoveryStatus
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.organizer import ExecutionEffectCertainty, ExecutionStatus
from mediaflow.domain.task_persistence import (
    ConfirmationStatus,
    PersistentTaskStatus,
    TaskItemStatus,
)
from mediaflow.domain.task_scheduling import TaskQueueState
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from tests.test_media_discovery import _DiscoveryFixture

REQUEST_ID = "11111111-1111-4111-8111-111111111111"


class ManualTaskDiscoveryTests(_DiscoveryFixture):
    def _admit(self, value, paths, *, auto_prepare=True, request_id=REQUEST_ID):
        return self.request(
            value,
            "/api/v1/resource-libraries/library/files/discoveries",
            "POST",
            {"paths": list(paths), "autoPrepare": auto_prepare, "requestId": request_id},
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
        return decision["checkpoint"]["checkpoint_version"]

    def _resolve_conflict(self, value, task_id, item, strategy="rename"):
        status, checkpoint = self.request(value, f"/api/v1/tasks/{task_id}/items/{item.item_id}")
        self.assertEqual(200, status, checkpoint)
        status, decision = self.request(
            value,
            f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery/decision",
            "POST",
            {
                "kind": "conflict",
                "expectedCheckpointVersion": checkpoint["checkpoint_version"],
                "strategy": strategy,
            },
        )
        self.assertEqual(200, status, decision)
        return decision["checkpoint"]["checkpoint_version"]

    def _analyze(self, value, task_id, discovery):
        """Re-run the task's own bounded analysis and read the fresh summary."""

        current = value.repository.get_media_discovery(discovery.discovery_id)
        status, accepted = self.request(
            value,
            f"/api/v1/operations/organize/discoveries/{discovery.discovery_id}/analyze",
            "POST",
            {"expectedVersion": current.version},
        )
        self.assertEqual(200, status, accepted)
        fresh = self._drive(value, task_id)
        status, preview = self.request(
            value, f"/api/v1/operations/organize/previews/{fresh.preview_id}"
        )
        self.assertEqual(200, status, preview)
        return preview

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
            # settled merely because one confirmed subset finished.  Its published
            # aggregate describes the whole admitted work: two concrete sources,
            # one completed, one still owed — on the Task, the run API and the
            # durable row alike.
            first_result = value.repository.list_results(task_id)[0]
            self.assertEqual(
                (2, 1, 0),
                (
                    first_execution.total_items,
                    first_execution.completed_items,
                    first_execution.failed_items,
                ),
            )
            task_counts, run_counts = self._task_api_counts(value, task_id)
            self.assertEqual((2, 1, 0), task_counts)
            self.assertEqual((2, 1, 0), run_counts)

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
            self.assertEqual(
                (2, 2, 0), (final.total_items, final.completed_items, final.failed_items)
            )
            task_counts, run_counts = self._task_api_counts(value, task_id)
            self.assertEqual((2, 2, 0), task_counts)
            self.assertEqual((2, 2, 0), run_counts)
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
                self.assertEqual(
                    (2, 2, 0),
                    (
                        reopened_task.total_items,
                        reopened_task.completed_items,
                        reopened_task.failed_items,
                    ),
                )

    def test_metadata_decision_continues_in_the_same_task(self) -> None:
        """A resolved Metadata candidate is consumed by the Task's next analysis.

        A repeated analysis of the same admitted Task must apply the operator's
        saved Metadata decision instead of re-publishing the same metadata
        problem (which the review table, keyed on the item, could never store
        twice).  The item reaches its own confirmable summary on the same Task.
        """

        self.media("Movies/One.2001.mkv")
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate(
                    "tmdb", "201", MediaType.MOVIE, "One", year=2001, genres=("Animation",)
                ),
                MediaCandidate(
                    "tmdb", "202", MediaType.MOVIE, "One", year=2001, genres=("Animation",)
                ),
            )
        )
        with self.journey(provider=provider, task_scheduling=True) as value:
            status, admitted = self._admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = self._drive(value, task_id)
            item = value.repository.list_items(task_id)[0]
            self._decide_recognition(value, task_id, item)

            current = value.repository.get_media_discovery(discovery.discovery_id)
            status, accepted = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{discovery.discovery_id}/analyze",
                "POST",
                {"expectedVersion": current.version},
            )
            self.assertEqual(200, status, accepted)
            discovery = self._drive(value, task_id)
            item = value.repository.list_items(task_id)[0]
            self.assertIs(item.status, TaskItemStatus.WAITING_METADATA)
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.WAITING_HUMAN,
            )

            status, checkpoint = self.request(
                value, f"/api/v1/tasks/{task_id}/items/{item.item_id}"
            )
            self.assertEqual(200, status, checkpoint)
            status, decision = self.request(
                value,
                f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery/decision",
                "POST",
                {
                    "kind": "metadata",
                    "expectedCheckpointVersion": checkpoint["checkpoint_version"],
                    "candidateRank": 1,
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
            state = value.repository.get_task_scheduling(task_id)
            self.assertIs(state.queue_state, TaskQueueState.WAITING_HUMAN, state)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            item = value.repository.list_items(task_id)[0]
            self.assertIs(item.status, TaskItemStatus.WAITING_CONFIRM)

            status, preview = self.request(
                value, f"/api/v1/operations/organize/previews/{discovery.preview_id}"
            )
            self.assertEqual(200, status, preview)
            ready = [
                value["itemId"] for value in preview["items"] if value["status"] == "previewed"
            ]
            self.assertEqual(1, len(ready), preview)
            final = self._execute(value, task_id, preview, ready)
            self.assertIs(final.status, PersistentTaskStatus.COMPLETED, final.error)
            self.assertEqual(1, len(value.repository.list_results(task_id)))
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())

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
            # An unproved effect keeps the whole work's source protection: the
            # not-yet-executed sibling cannot be started as separate new work
            # merely because the operator already asked to cancel this Task.
            status, again = self._admit(
                value,
                ["Movies/Two.2002.mkv"],
                request_id="44444444-4444-4444-8444-444444444444",
            )
            self.assertEqual(409, status, again)
            self.assertEqual("source_already_organizing", again["error"]["code"])
            self.assertEqual("none", again["error"]["details"]["sideEffects"])
            self.assertEqual(1, value.repository.count_scheduled_capacity_use())

    # -- Task Center four-type continuation on the same Task ------------------

    def _continue_from_task_center(self, value, task_id, item_id, checkpoint_version):
        """The exact Web path a saved Task Center decision uses to continue."""

        return self.request(
            value,
            f"/api/v1/tasks/{task_id}/items/{item_id}/recovery/continue",
            "POST",
            {"expectedCheckpointVersion": checkpoint_version},
        )

    def _task_api_counts(self, value, task_id):
        status, task = self.request(value, f"/api/v1/tasks/{task_id}")
        self.assertEqual(200, status, task)
        status, run = self.request(value, f"/api/v1/operations/runs/{task_id}")
        self.assertEqual(200, status, run)
        return (
            (task["total_items"], task["completed_items"], task["failed_items"]),
            (run["total_items"], run["completed_items"], run["failed_items"]),
        )

    def test_task_center_continue_runs_the_whole_journey_on_the_same_task(self) -> None:
        """A saved decision continues *this* Task; no recovery Job is minted.

        The exact Web entry (``POST /tasks/{task}/items/{item}/recovery/continue``)
        re-runs the same Task's bounded analysis: the Task identity, its pin and
        its evidence stay, and the operator reaches the confirmable summary and
        the per-item Result on that same Task.
        """

        self.media("Movies/One.2001.mkv")
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate(
                    "tmdb", "201", MediaType.MOVIE, "One", year=2001, genres=("Animation",)
                ),
                MediaCandidate(
                    "tmdb", "202", MediaType.MOVIE, "One", year=2001, genres=("Animation",)
                ),
            )
        )
        with self.journey(provider=provider, task_scheduling=True) as value:
            status, admitted = self._admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = self._drive(value, task_id)
            item = value.repository.list_items(task_id)[0]
            self.assertIs(item.status, TaskItemStatus.WAITING_RECOGNITION)

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
            self.assertIn("retry", decision["checkpoint"]["permitted_action_ids"])

            status, accepted = self._continue_from_task_center(
                value,
                task_id,
                item.item_id,
                decision["checkpoint"]["checkpoint_version"],
            )
            self.assertEqual(202, status, accepted)
            # The answer names the same Task's own preparation; it publishes no
            # Job and no child Task identity at all.
            self.assertEqual(task_id, accepted["taskId"])
            self.assertEqual(discovery.discovery_id, accepted["nativeAnalysis"]["discoveryId"])
            self.assertEqual("none", accepted["sideEffects"])
            self.assertEqual("dry_run", accepted["executionMode"])
            self.assertNotIn("job_id", accepted)
            self.assertNotIn("new_task_id", accepted)
            self.assertEqual((), value.repository.list_jobs(limit=10))
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            # The same Task is re-registered as machine work and advances its
            # own analysis to the next real four-type problem.
            self.assertIn(
                value.repository.get_task_scheduling(task_id).queue_state,
                {TaskQueueState.QUEUED, TaskQueueState.CLAIMED},
            )
            discovery = self._drive(value, task_id)
            self.assertEqual(task_id, value.repository.get_task(task_id).task_id)
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.WAITING_HUMAN,
            )
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            item = value.repository.list_items(task_id)[0]
            self.assertIs(item.status, TaskItemStatus.WAITING_METADATA)
            self.assertEqual((), value.repository.list_jobs(limit=10))

            status, checkpoint = self.request(
                value, f"/api/v1/tasks/{task_id}/items/{item.item_id}"
            )
            self.assertEqual(200, status, checkpoint)
            status, decision = self.request(
                value,
                f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery/decision",
                "POST",
                {
                    "kind": "metadata",
                    "expectedCheckpointVersion": checkpoint["checkpoint_version"],
                    "candidateRank": 1,
                },
            )
            self.assertEqual(200, status, decision)
            status, accepted = self._continue_from_task_center(
                value,
                task_id,
                item.item_id,
                decision["checkpoint"]["checkpoint_version"],
            )
            self.assertEqual(202, status, accepted)
            self.assertEqual(task_id, accepted["taskId"])
            discovery = self._drive(value, task_id)
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.WAITING_HUMAN,
            )
            item = value.repository.list_items(task_id)[0]
            self.assertIs(item.status, TaskItemStatus.WAITING_CONFIRM)

            # The summary and the explicit confirmation remain the existing
            # exact Files preview/execute boundary for this same Task.
            status, preview = self.request(
                value, f"/api/v1/operations/organize/previews/{discovery.preview_id}"
            )
            self.assertEqual(200, status, preview)
            ready = [
                value["itemId"] for value in preview["items"] if value["status"] == "previewed"
            ]
            self.assertEqual(1, len(ready), preview)
            final = self._execute(value, task_id, preview, ready)
            self.assertIs(final.status, PersistentTaskStatus.COMPLETED, final.error)
            self.assertEqual(1, len(value.repository.list_results(task_id)))
            self.assertEqual((), value.repository.list_jobs(limit=10))
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())

    def test_continue_at_full_capacity_keeps_the_saved_decision_and_waits(self) -> None:
        """A full shared queue refuses the continuation without consuming it.

        The Task keeps its waiting state, the saved decision and its summary, and
        the operator's explicit retry succeeds once the competing Task reaches
        its own human boundary.
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
                )
                for index, title in enumerate(("One", "Two"))
            )
        )
        original_document = self.document

        def one_slot(**kwargs):
            document = original_document(**kwargs)
            document["automation"]["maximumActiveJobs"] = 1
            return document

        with (
            mock.patch.object(self, "document", side_effect=one_slot),
            self.journey(provider=provider, task_scheduling=True) as value,
        ):
            status, admitted = self._admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            self._drive(value, task_id)
            item = value.repository.list_items(task_id)[0]
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
            saving = decision["checkpoint"]["checkpoint_version"]

            # A second, deliberate Task holds the single shared slot as real
            # machine work (a distinct request identity, not a repeat).
            status, second = self._admit(
                value,
                ["Movies/Two.2002.mkv"],
                request_id="22222222-2222-4222-8222-222222222222",
            )
            self.assertEqual(202, status, second)
            second_task_id = second["organizeTaskId"]
            self.assertNotEqual(task_id, second_task_id)
            self.assertEqual(1, value.repository.count_scheduled_capacity_use())

            status, refused = self._continue_from_task_center(value, task_id, item.item_id, saving)
            self.assertEqual(409, status, refused)
            self.assertEqual("capacity_full", refused["error"]["code"])
            self.assertEqual("none", refused["error"]["details"]["sideEffects"])
            # Nothing was consumed, cleared or automatically registered: the
            # same Task still waits, its decision and summary stay readable and
            # no Job was created.
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.WAITING_HUMAN,
            )
            self.assertEqual(
                saving,
                self.request(
                    value,
                    f"/api/v1/tasks/{task_id}/items/{item.item_id}",
                )[1]["checkpoint_version"],
            )
            self.assertIsNotNone(value.repository.get_recognition_review_for_item(item.item_id))
            self.assertEqual((), value.repository.list_jobs(limit=10))
            self.assertEqual([], value.source.mutations)

            # The competing Task reaches its own human boundary (zero slots);
            # the operator's explicit retry now re-registers the same Task.
            self._drive(value, second_task_id)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            status, accepted = self._continue_from_task_center(value, task_id, item.item_id, saving)
            self.assertEqual(202, status, accepted)
            self.assertEqual(task_id, accepted["taskId"])
            self.assertEqual((), value.repository.list_jobs(limit=10))
            self._drive(value, task_id)
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.WAITING_HUMAN,
            )
            self.assertEqual([], value.source.mutations)

    def test_cancelled_human_waiting_work_frees_its_source_for_a_new_request(self) -> None:
        """A safe cancel settles the admission too, so a new intent is admitted.

        The Task Center cancel of a work that is only waiting for the operator
        leaves a terminal Task, a terminal item and a cancelled discovery whose
        summary stays readable history.  A new request id for the same unchanged
        file is then a new organizing Task, never a resume or replay of the old
        one.
        """

        self.media("Movies/One.2001.mkv")
        with self.journey(task_scheduling=True) as value:
            status, admitted = self._admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = self._drive(value, task_id)
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.WAITING_HUMAN,
            )
            task = value.repository.get_task(task_id)
            status, cancelled = self.request(
                value,
                f"/api/v1/tasks/{task_id}/cancel",
                "POST",
                {"expectedUpdatedAt": task.updated_at.isoformat()},
            )
            self.assertEqual(200, status, cancelled)
            self.assertIs(value.repository.get_task(task_id).status, PersistentTaskStatus.CANCELLED)
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.SETTLED,
            )
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertEqual(
                {TaskItemStatus.CANCELLED},
                {item.status for item in value.repository.list_items(task_id)},
            )
            # The linked preparation records the same cancellation fact instead
            # of staying a confirmable summary that still owns the source.
            settled = value.repository.get_media_discovery(discovery.discovery_id)
            self.assertIs(settled.status, DiscoveryStatus.CANCELLED)
            self.assertTrue(settled.cancel_requested)
            # Its known findings and plan identity stay readable history.
            self.assertEqual(discovery.preview_id, settled.preview_id)
            self.assertEqual(discovery.sources, settled.sources)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            status, repeated = self._admit(
                value,
                ["Movies/One.2001.mkv"],
                request_id="33333333-3333-4333-8333-333333333333",
            )
            self.assertIn(
                status,
                (202,),
                repeated,
            )
            new_task_id = repeated["organizeTaskId"]
            self.assertNotEqual(task_id, new_task_id)
            self.assertNotEqual(discovery.discovery_id, repeated["discoveryId"])
            # The original work keeps its identity and its final state; the new
            # request is separate, deliberate work with no automatic replay.
            self.assertIs(value.repository.get_task(task_id).status, PersistentTaskStatus.CANCELLED)
            self.assertIsNot(
                value.repository.get_task(new_task_id).status, PersistentTaskStatus.CANCELLED
            )
            self.assertEqual([], value.source.mutations)
            self._drive(value, new_task_id)
            self.assertIs(
                value.repository.get_task_scheduling(new_task_id).queue_state,
                TaskQueueState.WAITING_HUMAN,
            )
            self.assertEqual((), value.repository.list_jobs(limit=10))

            with SQLiteTaskRepository(self.database) as reopened:
                self.assertIs(reopened.get_task(task_id).status, PersistentTaskStatus.CANCELLED)
                self.assertTrue(
                    reopened.get_media_discovery(discovery.discovery_id).cancel_requested
                )

    def test_new_task_reopens_its_own_conflict_not_a_cancelled_tasks_decision(self) -> None:
        """A new request never borrows another Task's resolved conflict decision.

        The first Task resolves a real target collision to Rename and is then
        cancelled without executing.  A deliberate new request for the same
        unchanged source must publish *its own* pending conflict -- not silently
        apply the old Task's rename because the deterministic plan/source/path
        happens to match -- and its own decision then plans and executes on that
        same Task.
        """

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
            first = admitted["organizeTaskId"]
            discovery = self._drive(value, first)
            first_item = value.repository.list_items(first)[0]
            self._decide_recognition(value, first, first_item)
            preview = self._analyze(value, first, discovery)
            # Create a real destination collision for the already planned target.
            destination = (
                self.target_root / preview["items"][0]["plan"]["destination"]["storageRelativePath"]
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"existing target")
            preview = self._analyze(value, first, discovery)
            self.assertEqual(["stale"], [item["status"] for item in preview["items"]], preview)
            self._resolve_conflict(value, first, first_item)

            task = value.repository.get_task(first)
            status, cancelled = self.request(
                value,
                f"/api/v1/tasks/{first}/cancel",
                "POST",
                {"expectedUpdatedAt": task.updated_at.isoformat()},
            )
            self.assertEqual(200, status, cancelled)
            self.assertEqual(0, len(value.repository.list_results(first)))
            self.assertEqual([], value.source.mutations)

            # A deliberate new request for the same unchanged source.
            status, second = self._admit(
                value,
                ["Movies/One.2001.mkv"],
                request_id="22222222-2222-4222-8222-222222222222",
            )
            self.assertEqual(202, status, second)
            second_task = second["organizeTaskId"]
            self.assertNotEqual(first, second_task)
            second_discovery = self._drive(value, second_task)
            second_item = value.repository.list_items(second_task)[0]
            self._decide_recognition(value, second_task, second_item)
            preview = self._analyze(value, second_task, second_discovery)

            # The old Task's resolved Rename is not borrowed: this Task has its
            # own pending conflict and the plan is not silently renamed.
            confirmations = tuple(
                confirmation
                for confirmation in value.repository.list_confirmations()
                if confirmation.task_id == second_task
            )
            self.assertEqual(1, len(confirmations), confirmations)
            self.assertIs(confirmations[0].status, ConfirmationStatus.PENDING)
            self.assertEqual(["stale"], [item["status"] for item in preview["items"]], preview)
            self.assertNotIn("(1)", preview["items"][0]["plan"]["destination"]["filename"])
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            # This Task's own decision is honored on that same Task.
            self._resolve_conflict(value, second_task, second_item)
            preview = self._analyze(value, second_task, second_discovery)
            ready = [item["itemId"] for item in preview["items"] if item["status"] == "previewed"]
            self.assertEqual(1, len(ready), preview)
            self.assertIn("(1)", preview["items"][0]["plan"]["destination"]["filename"])
            final = self._execute(value, second_task, preview, ready)
            self.assertIs(final.status, PersistentTaskStatus.COMPLETED, final.error)
            self.assertEqual(1, len(value.repository.list_results(second_task)))
            self.assertEqual((), value.repository.list_jobs(limit=10))

    def test_failed_subset_keeps_the_undecided_sibling_actionable_on_the_same_task(self) -> None:
        """One failed source never settles the other sources of the same Task.

        Two files are confirmed one at a time.  The first source disappears
        before the Worker runs, so its own Result is failed and no Storage
        mutation is attempted.  The untouched second source must still save its
        decision, continue its analysis and produce its own Result on the same
        Task; the final aggregate honestly shows the failed and the completed
        sibling instead of letting the later success erase the earlier failure.
        """

        provider = self._two_file_recognition_journey()
        with self.journey(provider=provider, task_scheduling=True) as value:
            status, admitted = self._admit(value, ["Movies/One.2001.mkv", "Movies/Two.2002.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = self._drive(value, task_id)
            items = {item.source_path: item for item in value.repository.list_items(task_id)}
            first = items["Movies/One.2001.mkv"]
            second = items["Movies/Two.2002.mkv"]
            self._decide_recognition(value, task_id, first)
            preview = self._analyze(value, task_id, discovery)
            ready = [item["itemId"] for item in preview["items"] if item["status"] == "previewed"]
            self.assertEqual(1, len(ready), preview)
            status, admitted_execution = self.request(
                value,
                f"/api/v1/operations/organize/previews/{preview['previewId']}/execute",
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
            # A normal external event after admission, before the Worker runs.
            (self.source_root / "Movies/One.2001.mkv").unlink()
            for _ in range(4):
                value.task_engine.run_next()

            task = value.repository.get_task(task_id)
            state = value.repository.get_task_scheduling(task_id)
            self.assertIs(task.status, PersistentTaskStatus.RUNNING, task.error)
            self.assertIs(state.queue_state, TaskQueueState.WAITING_HUMAN)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            items = {item.source_path: item for item in value.repository.list_items(task_id)}
            self.assertIs(items["Movies/One.2001.mkv"].status, TaskItemStatus.FAILED)
            self.assertIs(items["Movies/Two.2002.mkv"].status, TaskItemStatus.WAITING_RECOGNITION)
            self.assertEqual(1, len(value.repository.list_results(task_id)))
            self.assertTrue((self.source_root / "Movies/Two.2002.mkv").exists())
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            # The untouched second sibling saves its own decision and continues
            # its safe analysis on this same Task.
            self._decide_recognition(value, task_id, second)
            checkpoint = self.request(value, f"/api/v1/tasks/{task_id}/items/{second.item_id}")[1]
            status, accepted = self._continue_from_task_center(
                value, task_id, second.item_id, checkpoint["checkpoint_version"]
            )
            self.assertEqual(202, status, accepted)
            self.assertEqual(task_id, accepted["taskId"])
            self.assertEqual((), value.repository.list_jobs(limit=10))
            fresh = self._drive(value, task_id)
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.WAITING_HUMAN,
            )
            status, preview = self.request(
                value, f"/api/v1/operations/organize/previews/{fresh.preview_id}"
            )
            self.assertEqual(200, status, preview)
            second_ready = [
                item["itemId"] for item in preview["items"] if item["status"] == "previewed"
            ]
            self.assertEqual(1, len(second_ready), preview)
            final = self._execute(value, task_id, preview, second_ready)
            # The completed second sibling cannot overwrite the recorded first
            # failure: the Task aggregates both independent outcomes.
            self.assertIs(final.status, PersistentTaskStatus.PARTIAL_SUCCESS, final.error)
            self.assertEqual(
                (2, 1, 1),
                (final.total_items, final.completed_items, final.failed_items),
            )
            results = value.repository.list_results(task_id)
            self.assertEqual(2, len(results), results)
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())
            self.assertFalse((self.source_root / "Movies/Two.2002.mkv").exists())

    def test_ready_sources_remain_on_the_task_after_subset_execution(self) -> None:
        """Files needing no decision still own items before any confirmation."""
        provider = self._two_file_recognition_journey()
        with self.journey(provider=provider, task_scheduling=True, attachments=True) as value:
            status, admitted = self._admit(value, ["Movies/One.2001.mkv", "Movies/Two.2002.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = self._drive(value, task_id)
            items = value.repository.list_items(task_id)
            self.assertEqual(2, len(items))
            self.assertTrue(all(item.status is TaskItemStatus.WAITING_CONFIRM for item in items))
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            status, preview = self.request(
                value, f"/api/v1/operations/organize/previews/{discovery.preview_id}"
            )
            self.assertEqual(200, status, preview)
            first = next(
                item["itemId"]
                for item in preview["items"]
                if item["source"]["path"] == "Movies/One.2001.mkv"
            )
            task = self._execute(value, task_id, preview, [first])
            self.assertIs(task.status, PersistentTaskStatus.RUNNING)
            self.assertEqual((2, 1, 0), (task.total_items, task.completed_items, task.failed_items))
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.WAITING_HUMAN,
            )
            first_result = value.repository.list_results(task_id)[0]
            self.assertTrue((self.source_root / "Movies/Two.2002.mkv").exists())
            remaining = self._analyze(value, task_id, discovery)
            self.assertEqual(1, len(remaining["items"]))
            task = self._execute(value, task_id, remaining, [remaining["items"][0]["itemId"]])
            self.assertIs(task.status, PersistentTaskStatus.COMPLETED)
            self.assertEqual((2, 2, 0), (task.total_items, task.completed_items, task.failed_items))
            self.assertIn(first_result, value.repository.list_results(task_id))
            self.assertEqual(2, len(value.repository.list_results(task_id)))
            self.assertEqual((), value.repository.list_jobs(limit=10))
            with SQLiteTaskRepository(self.database) as reopened:
                self.assertEqual(2, reopened.get_task(task_id).completed_items)
                self.assertEqual(2, len(reopened.list_results(task_id)))

    def test_native_summary_is_confirmable_on_the_same_task_from_the_center(self) -> None:
        """The Task Center reads and confirms the Task's own linked summary.

        After a saved four-type decision and its safe re-analysis, the exact
        Files preparation the Task already owns is published as a
        ``business_problem`` summary -- not technical history.  The operator
        confirms a ready subset through the existing execution service and the
        same Task produces its own Result; a reload reads the same durable
        summary back without minting a Job or a second preparation.
        """

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
            item = value.repository.list_items(task_id)[0]
            saved = self._decide_recognition(value, task_id, item)
            status, accepted = self._continue_from_task_center(value, task_id, item.item_id, saved)
            self.assertEqual(202, status, accepted)
            discovery = self._drive(value, task_id)

            status, detail = self.request(
                value, f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery"
            )
            self.assertEqual(200, status, detail)
            self.assertEqual("business_problem", detail["recoveryKind"])
            self.assertTrue(detail["manualRecoveryAvailable"])
            self.assertTrue(detail["manualRecoveryAnalysisReady"])
            preparation = detail["manualRecoveryPreparation"]
            self.assertIsNotNone(preparation)
            self.assertEqual("prepared", preparation["status"])
            self.assertEqual(discovery.preview_id, preparation["preview_id"])
            self.assertEqual(
                "native:" + discovery.discovery_id + ":" + discovery.preview_id,
                preparation["preparation_id"],
            )

            # Preparing the summary is a bounded re-read of that same record.
            status, prepared = self.request(
                value,
                f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery/prepare-summary",
                "POST",
                {"expectedCheckpointVersion": detail["checkpoint"]["checkpoint_version"]},
            )
            self.assertEqual(201, status, prepared)
            self.assertEqual(preparation["preparation_id"], prepared["preparation_id"])
            self.assertFalse(prepared["hasExecutionAuthority"])
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            status, preview = self.request(
                value, f"/api/v1/operations/organize/previews/{preparation['preview_id']}"
            )
            self.assertEqual(200, status, preview)
            ready = [
                entry["itemId"] for entry in preview["items"] if entry["status"] == "previewed"
            ]
            self.assertEqual(1, len(ready), preview)
            status, confirmed = self.request(
                value,
                f"/api/v1/manual-recovery-preparations/{preparation['preparation_id']}/confirm",
                "POST",
                {
                    "itemIds": ready,
                    "confirmation": True,
                    "allowOverwrite": False,
                    "allowSourceCleanup": False,
                },
            )
            self.assertEqual(202, status, confirmed)
            self.assertEqual(task_id, confirmed["taskId"])
            self.assertEqual([], value.source.mutations)
            self.assertEqual((), value.repository.list_jobs(limit=10))

            for _ in range(8):
                value.task_engine.run_next()
            final = value.repository.get_task(task_id)
            self.assertIs(final.status, PersistentTaskStatus.COMPLETED, final.error)
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.SETTLED,
            )
            self.assertEqual(1, len(value.repository.list_results(task_id)))
            self.assertEqual((), value.repository.list_jobs(limit=10))
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())

            # A reload reads the same confirmed step back, read-only.  The
            # execution admission replaces the analysis wrapper with the exact
            # execution item of the same source, so the current item is read.
            current_item = value.repository.list_items(task_id)[0]
            status, reread = self.request(
                value, f"/api/v1/tasks/{task_id}/items/{current_item.item_id}/recovery"
            )
            self.assertEqual(200, status, reread)
            self.assertEqual("confirmed", reread["manualRecoveryPreparation"]["status"])
            self.assertEqual(
                confirmed["executionId"],
                reread["manualRecoveryPreparation"]["execution_id"],
            )
            with SQLiteTaskRepository(self.database) as reopened:
                self.assertIs(reopened.get_task(task_id).status, PersistentTaskStatus.COMPLETED)

    def test_native_metadata_candidate_confirms_on_the_same_task(self) -> None:
        """A Metadata-candidate decision also reaches a confirmable native summary.

        After the Recognition decision, the analysis publishes the Metadata
        candidate problem on the same Task.  Once that candidate is saved and
        re-analyzed, the exact linked summary is published as a
        ``business_problem`` and confirmed through the existing execution
        service on that same Task.
        """

        self.media("Movies/One.2001.mkv")
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate(
                    "tmdb", "201", MediaType.MOVIE, "One", year=2001, genres=("Animation",)
                ),
                MediaCandidate(
                    "tmdb", "202", MediaType.MOVIE, "One", year=2001, genres=("Animation",)
                ),
            )
        )
        with self.journey(provider=provider, task_scheduling=True) as value:
            status, admitted = self._admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            self._drive(value, task_id)
            item = value.repository.list_items(task_id)[0]
            saved = self._decide_recognition(value, task_id, item)
            status, accepted = self._continue_from_task_center(value, task_id, item.item_id, saved)
            self.assertEqual(202, status, accepted)
            self._drive(value, task_id)
            item = value.repository.list_items(task_id)[0]
            self.assertIs(item.status, TaskItemStatus.WAITING_METADATA)

            status, checkpoint = self.request(
                value, f"/api/v1/tasks/{task_id}/items/{item.item_id}"
            )
            self.assertEqual(200, status, checkpoint)
            status, decision = self.request(
                value,
                f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery/decision",
                "POST",
                {
                    "kind": "metadata",
                    "expectedCheckpointVersion": checkpoint["checkpoint_version"],
                    "candidateRank": 1,
                },
            )
            self.assertEqual(200, status, decision)
            status, accepted = self._continue_from_task_center(
                value, task_id, item.item_id, decision["checkpoint"]["checkpoint_version"]
            )
            self.assertEqual(202, status, accepted)
            self._drive(value, task_id)
            item = value.repository.list_items(task_id)[0]
            self.assertIs(item.status, TaskItemStatus.WAITING_CONFIRM)

            status, detail = self.request(
                value, f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery"
            )
            self.assertEqual(200, status, detail)
            self.assertEqual("business_problem", detail["recoveryKind"])
            preparation = detail["manualRecoveryPreparation"]
            self.assertIsNotNone(preparation)
            self.assertEqual("prepared", preparation["status"])

            status, preview = self.request(
                value, f"/api/v1/operations/organize/previews/{preparation['preview_id']}"
            )
            self.assertEqual(200, status, preview)
            ready = [
                entry["itemId"] for entry in preview["items"] if entry["status"] == "previewed"
            ]
            self.assertEqual(1, len(ready), preview)
            status, confirmed = self.request(
                value,
                f"/api/v1/manual-recovery-preparations/{preparation['preparation_id']}/confirm",
                "POST",
                {
                    "itemIds": ready,
                    "confirmation": True,
                    "allowOverwrite": False,
                    "allowSourceCleanup": False,
                },
            )
            self.assertEqual(202, status, confirmed)
            self.assertEqual(task_id, confirmed["taskId"])
            for _ in range(8):
                value.task_engine.run_next()
            final = value.repository.get_task(task_id)
            self.assertIs(final.status, PersistentTaskStatus.COMPLETED, final.error)
            self.assertEqual(1, len(value.repository.list_results(task_id)))
            self.assertEqual((), value.repository.list_jobs(limit=10))
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())

    # -- Exact native confirmation, history and per-item scope ----------------

    def _native_confirm(self, value, preparation, ready, *, expect=202):
        status, reply = self.request(
            value,
            f"/api/v1/manual-recovery-preparations/{preparation['preparation_id']}/confirm",
            "POST",
            {
                "itemIds": list(ready),
                "confirmation": True,
                "allowOverwrite": False,
                "allowSourceCleanup": False,
            },
        )
        self.assertEqual(expect, status, reply)
        return reply

    def test_native_confirmation_is_bound_to_the_reviewed_preview(self) -> None:
        """The old page can never execute a newer, unreviewed plan.

        The operator reads summary A, another explicit analysis publishes
        summary B for the same discovery, and the still-open page A submits its
        confirmation.  A is refused without consuming authority or mutating
        Storage; only confirming the plan that was actually reviewed executes.
        """

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
            item = value.repository.list_items(task_id)[0]
            saved = self._decide_recognition(value, task_id, item)
            status, accepted = self._continue_from_task_center(value, task_id, item.item_id, saved)
            self.assertEqual(202, status, accepted)
            discovery = self._drive(value, task_id)
            status, detail = self.request(
                value, f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery"
            )
            self.assertEqual(200, status, detail)
            old_preparation = detail["manualRecoveryPreparation"]
            old_ready = [
                entry["itemId"]
                for entry in self.request(
                    value,
                    f"/api/v1/operations/organize/previews/{old_preparation['preview_id']}",
                )[1]["items"]
                if entry["status"] == "previewed"
            ]

            # A second explicit analysis supersedes the reviewed Preview while
            # the first page still displays summary A.
            fresh_preview = self._analyze(value, task_id, discovery)
            self.assertNotEqual(old_preparation["preview_id"], fresh_preview["previewId"])

            refused = self._native_confirm(value, old_preparation, old_ready, expect=409)
            self.assertEqual("preparation_stale", refused["error"]["code"])
            self.assertEqual("none", refused["error"]["details"]["sideEffects"])
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            self.assertEqual((), value.repository.list_results(task_id))
            self.assertEqual((), value.repository.list_manual_executions_for_task(task_id))

            # The plan the operator actually reviewed is the only one that runs.
            status, detail = self.request(
                value, f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery"
            )
            self.assertEqual(200, status, detail)
            current = detail["manualRecoveryPreparation"]
            self.assertNotEqual(old_preparation["preparation_id"], current["preparation_id"])
            ready = [
                entry["itemId"]
                for entry in fresh_preview["items"]
                if entry["status"] == "previewed"
            ]
            execution = self._native_confirm(value, current, ready)
            self.assertEqual(task_id, execution["taskId"])
            for _ in range(8):
                value.task_engine.run_next()
            final = value.repository.get_task(task_id)
            self.assertIs(final.status, PersistentTaskStatus.COMPLETED, final.error)
            self.assertEqual(1, len(value.repository.list_results(task_id)))
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())

    def test_confirmed_execution_keeps_the_original_item_link_readable(self) -> None:
        """The exact confirmation preserves the original item URL and history.

        A normal current-summary confirmation reuses the one durable TaskItem
        identity of that source, so the operator's original item link keeps
        reading its decision/history and the admitted execution before, during
        and after the Worker runs, and across a reopen.
        """

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
            self._drive(value, task_id)
            item = value.repository.list_items(task_id)[0]
            saved = self._decide_recognition(value, task_id, item)
            status, accepted = self._continue_from_task_center(value, task_id, item.item_id, saved)
            self.assertEqual(202, status, accepted)
            self._drive(value, task_id)
            status, detail = self.request(
                value, f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery"
            )
            self.assertEqual(200, status, detail)
            preparation = detail["manualRecoveryPreparation"]
            ready = [
                entry["itemId"]
                for entry in self.request(
                    value,
                    f"/api/v1/operations/organize/previews/{preparation['preview_id']}",
                )[1]["items"]
                if entry["status"] == "previewed"
            ]
            execution = self._native_confirm(value, preparation, ready)

            # The original URL is readable immediately after admission, before
            # the Worker has run, and points at the admitted execution.
            status, before = self.request(
                value, f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery"
            )
            self.assertEqual(200, status, before)
            self.assertEqual("confirmed", before["manualRecoveryPreparation"]["status"])
            self.assertEqual(
                execution["executionId"], before["manualRecoveryPreparation"]["execution_id"]
            )

            for _ in range(8):
                value.task_engine.run_next()
            status, after = self.request(
                value, f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery"
            )
            self.assertEqual(200, status, after)
            self.assertEqual("confirmed", after["manualRecoveryPreparation"]["status"])
            self.assertEqual(
                execution["executionId"], after["manualRecoveryPreparation"]["execution_id"]
            )
            self.assertEqual("success", after["checkpoint"]["status"])
            # The one durable source keeps the one durable item identity.
            current_items = value.repository.list_items(task_id)
            self.assertEqual(1, len(current_items))
            self.assertEqual(item.item_id, current_items[0].item_id)
            self.assertEqual(1, len(value.repository.list_results(task_id)))

            with SQLiteTaskRepository(self.database) as reopened:
                reopened_item = reopened.list_items(task_id)[0]
                self.assertEqual(item.item_id, reopened_item.item_id)
                self.assertEqual(1, len(reopened.list_results(task_id)))

    def test_unselected_sibling_keeps_its_own_summary_and_confirms(self) -> None:
        """Only the confirmed subset is bound to the execution.

        Two ready sources are confirmed one at a time through the native
        summary.  The unselected sibling never borrows the first file's
        execution: it keeps its own prepared/pending state, re-analyzes under
        the existing freshness rule, and completes its own Result on the same
        Task without replaying the first.
        """

        provider = self._two_file_recognition_journey()
        with self.journey(provider=provider, task_scheduling=True) as value:
            status, admitted = self._admit(value, ["Movies/One.2001.mkv", "Movies/Two.2002.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = self._drive(value, task_id)
            items = {item.source_path: item for item in value.repository.list_items(task_id)}
            first = items["Movies/One.2001.mkv"]
            second = items["Movies/Two.2002.mkv"]
            self._decide_recognition(value, task_id, first)
            self._decide_recognition(value, task_id, second)
            preview = self._analyze(value, task_id, discovery)
            ready = [
                entry["itemId"] for entry in preview["items"] if entry["status"] == "previewed"
            ]
            self.assertEqual(2, len(ready), preview)
            first_item_id = next(
                entry["itemId"]
                for entry in preview["items"]
                if entry["source"]["path"] == "Movies/One.2001.mkv"
            )
            second_item_id = next(
                entry["itemId"]
                for entry in preview["items"]
                if entry["source"]["path"] == "Movies/Two.2002.mkv"
            )
            status, detail = self.request(
                value, f"/api/v1/tasks/{task_id}/items/{first.item_id}/recovery"
            )
            self.assertEqual(200, status, detail)
            execution = self._native_confirm(
                value, detail["manualRecoveryPreparation"], [first_item_id]
            )
            for _ in range(4):
                value.task_engine.run_next()

            # The unselected sibling keeps its own pending summary and does not
            # borrow the first file's execution.
            status, sibling = self.request(
                value, f"/api/v1/tasks/{task_id}/items/{second.item_id}/recovery"
            )
            self.assertEqual(200, status, sibling)
            sibling_preparation = sibling["manualRecoveryPreparation"]
            self.assertEqual("stale", sibling_preparation["status"])
            self.assertIsNone(sibling_preparation["execution_id"])
            self.assertEqual([], sibling_preparation["selected_item_ids"])
            self.assertEqual("business_problem", sibling["recoveryKind"])
            self.assertEqual(["retry"], sibling["checkpoint"]["permitted_action_ids"])
            self.assertEqual("none", sibling["checkpoint"]["effects"]["certainty"])
            self.assertTrue((self.source_root / "Movies/Two.2002.mkv").exists())

            # Re-analyze the remaining source under the existing freshness rule,
            # then confirm and execute it on the same Task.
            status, continued = self.request(
                value,
                f"/api/v1/tasks/{task_id}/items/{second.item_id}/recovery/continue",
                "POST",
                {"expectedCheckpointVersion": sibling["checkpoint"]["checkpoint_version"]},
            )
            self.assertEqual(202, status, continued)
            fresh = self._drive(value, task_id)
            status, fresh_preview = self.request(
                value, f"/api/v1/operations/organize/previews/{fresh.preview_id}"
            )
            self.assertEqual(200, status, fresh_preview)
            second_ready = [
                entry["itemId"]
                for entry in fresh_preview["items"]
                if entry["status"] == "previewed"
            ]
            self.assertEqual([second_item_id], second_ready)
            status, detail = self.request(
                value, f"/api/v1/tasks/{task_id}/items/{second.item_id}/recovery"
            )
            self.assertEqual(200, status, detail)
            self._native_confirm(value, detail["manualRecoveryPreparation"], second_ready)
            for _ in range(8):
                value.task_engine.run_next()

            final = value.repository.get_task(task_id)
            self.assertIs(final.status, PersistentTaskStatus.COMPLETED, final.error)
            self.assertEqual(
                (2, 2, 0), (final.total_items, final.completed_items, final.failed_items)
            )
            results = value.repository.list_results(task_id)
            self.assertEqual(2, len(results), results)
            # Each confirmed source keeps its own execution; the first result is
            # never replayed or overwritten by the second confirmation.
            first_row = value.repository.manual_execution_item_for_task_item(task_id, first.item_id)
            self.assertIsNotNone(first_row)
            self.assertEqual(execution["executionId"], first_row["execution_id"])
            self.assertEqual(2, len(value.repository.list_manual_executions_for_task(task_id)))
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())
            self.assertFalse((self.source_root / "Movies/Two.2002.mkv").exists())

            with SQLiteTaskRepository(self.database) as reopened:
                reopened_task = reopened.get_task(task_id)
                self.assertIs(reopened_task.status, PersistentTaskStatus.COMPLETED)
                self.assertEqual(2, len(reopened.list_results(task_id)))
                self.assertEqual(
                    (2, 2, 0),
                    (
                        reopened_task.total_items,
                        reopened_task.completed_items,
                        reopened_task.failed_items,
                    ),
                )


if __name__ == "__main__":
    unittest.main()
