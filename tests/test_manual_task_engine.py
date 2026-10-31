"""Files manual work actually runs on the Task scheduling kernel (Task 47.2).

Every assertion runs the real authenticated API, the real bounded-discovery
service, the real manual intent/Preview/execution chain and real Local Storage
over temporary roots, with the Task engine as the only Worker that advances
newly admitted Files work.
"""

from __future__ import annotations

import unittest

from mediaflow.application.strategy_test import SyntheticMetadataProvider
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.task_persistence import PersistentTaskStatus
from mediaflow.domain.task_scheduling import TaskQueueState
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


if __name__ == "__main__":
    unittest.main()
