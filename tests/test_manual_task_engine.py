"""Files manual work actually runs on the Task scheduling kernel (Task 47.2).

Every assertion runs the real authenticated API, the real bounded-discovery
service, the real manual intent/Preview/execution chain and real Local Storage
over temporary roots, with the Task engine as the only Worker that advances
newly admitted Files work.
"""

from __future__ import annotations

import threading
import time
import unittest
from dataclasses import replace
from datetime import UTC, datetime
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

    def _publish_capacity(self, value, capacity: int):
        """Publish one real Active successor with a new shared allowance.

        The exact revision is loaded back through the production managed
        authority and the harness resolves each pin to its own runtime, so the
        already-prepared summary keeps its old pin while the next Files request
        uses the successor.
        """

        from mediaflow.application.configuration_snapshot import ManagedConfigurationService
        from mediaflow.infrastructure.runtime_configuration import (
            load_managed_runtime_configuration,
            with_managed_snapshot,
        )
        from mediaflow.infrastructure.sqlite_configuration_management import (
            SQLiteConfigurationRepository,
        )
        from tests.test_media_discovery import _activate

        document = self.document()
        document["automation"]["maximumActiveJobs"] = capacity
        with SQLiteConfigurationRepository(self.database) as configuration_repository:
            managed = ManagedConfigurationService(
                configuration_repository,
                bootstrap_database_path=str(self.database),
            )
            revision = _activate(managed, document)
        runtime = with_managed_snapshot(
            load_managed_runtime_configuration(
                revision.document, bootstrap_database_path=str(self.database)
            ),
            snapshot_id=revision.revision_id,
            digest=revision.digest,
            version=revision.version,
        )
        initial = value.configuration

        def resolve(snapshot_id, _digest):
            return runtime if snapshot_id == revision.revision_id else initial

        value.discovery._runtime_resolver = resolve
        value.intents._runtime_resolver = resolve
        value.previews._runtime_resolver = resolve
        return revision, runtime

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
            self.assertEqual(1, len(value.repository.list_tasks()))

    def test_long_batch_analysis_keeps_its_task_claim_live_to_the_summary(self) -> None:
        """A batch whose analysis outlives the default lease still publishes.

        RO-1/M5/M6/M8/M9: production metadata calls can comfortably outlive the
        default 300s Task lease across a whole batch.  The Task owner must renew
        its own claim (and keep the linked discovery claim live) at every item
        and Provider phase boundary, so the exact summary, its per-file items and
        its freed slot are published on the same Task instead of a permanently
        claimed, summary-less Task that still occupies a scheduling slot.
        """

        self._assert_slow_batch_reaches_summary(40, exceeds_lease=True)

    def test_short_batch_analysis_stays_the_same_task_within_the_lease(self) -> None:
        """The ordinary short batch is the control for the long-batch case."""

        self._assert_slow_batch_reaches_summary(20, exceeds_lease=False)

    def test_one_blocked_provider_call_keeps_the_task_lease_live(self) -> None:
        """One blocked Provider call must not let the Task lease lapse.

        A single metadata call can block longer than the lease while no phase
        boundary runs.  The lease keeper must renew the linked discovery claim
        and the containing Task claim for the whole blocked call, so the exact
        summary is still linked on the same Task instead of a lapsed,
        permanently claimed Task.  A real clock with a short lease makes the
        lapse materially real rather than a fake-time comparison.
        """

        self.media("Movies/One.2001.mkv")
        self.clock = lambda: datetime.now(UTC)
        entered, release = threading.Event(), threading.Event()

        class BlockedProvider(SyntheticMetadataProvider):
            def search_movie(self, *args, **kwargs):
                entered.set()
                if not release.wait(20):
                    raise AssertionError("the blocked Provider call was never released")
                return super().search_movie(*args, **kwargs)

        provider = BlockedProvider(
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
        with self.journey(
            provider=provider,
            task_scheduling=True,
            attachments=True,
            worker_lease=0.5,
        ) as value:
            status, admitted = self._admit(value, ["Movies"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            # The first pass walks the discovery and yields for analysis.
            self.assertIsNotNone(value.task_engine.run_next())
            # The second pass enters the analysis and blocks inside the Provider.
            thread = threading.Thread(target=value.task_engine.run_next)
            thread.start()
            try:
                self.assertTrue(entered.wait(20), "the analysis never reached the Provider")
                # Hold the call open well past the 0.5s Task/discovery lease.
                time.sleep(1.5)
            finally:
                release.set()
                thread.join(20)
            self.assertFalse(thread.is_alive())
            discovery = value.repository.get_media_discovery_for_task(task_id)
            task = value.repository.get_task(task_id)
            state = value.repository.get_task_scheduling(task_id)
            self.assertIsNotNone(discovery.preview_id, discovery.error)
            self.assertIs(discovery.status, DiscoveryStatus.COMPLETED)
            self.assertIs(task.status, PersistentTaskStatus.RUNNING)
            self.assertIs(state.queue_state, TaskQueueState.WAITING_HUMAN)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertEqual(1, len(value.repository.list_items(task_id)))
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def _assert_slow_batch_reaches_summary(self, count: int, *, exceeds_lease: bool) -> None:
        """Admit and analyze ``count`` legal movies whose metadata calls are slow.

        One ordinary Provider search advances the fixture clock by ten seconds,
        so a batch above thirty items takes the whole analysis past the default
        300s Task lease without any real wall-clock waiting.
        """

        for index in range(count):
            self.media(f"Movies/Film{index:02d}.2001.mkv")
        clock = self.clock

        class SlowProvider(SyntheticMetadataProvider):
            searches = 0

            def search_movie(self, *args, **kwargs):
                self.searches += 1
                clock.advance(10)
                self._candidates = (
                    MediaCandidate(
                        "tmdb",
                        str(200 + self.searches),
                        MediaType.MOVIE,
                        args[0].title_candidate,
                        year=2001,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                )
                return super().search_movie(*args, **kwargs)

        provider = SlowProvider(
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
        with self.journey(provider=provider, task_scheduling=True, attachments=True) as value:
            status, admitted = self._admit(value, ["Movies"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            started = clock()
            discovery = self._drive(value, task_id)
            elapsed = (clock() - started).total_seconds()
            # The batch itself genuinely exceeds the default 300s Task lease.
            if exceeds_lease:
                self.assertGreater(elapsed, 300.0)
            else:
                self.assertLess(elapsed, 300.0)
            self.assertEqual(count, provider.searches)
            # The same admitted Task publishes the exact summary with one durable
            # item per admitted file, then releases its slot to human waiting.
            task = value.repository.get_task(task_id)
            state = value.repository.get_task_scheduling(task_id)
            self.assertIsNotNone(discovery.preview_id)
            self.assertIs(discovery.status, DiscoveryStatus.COMPLETED)
            self.assertEqual(discovery.organize_task_id, task_id)
            self.assertIs(task.status, PersistentTaskStatus.RUNNING)
            self.assertIs(state.queue_state, TaskQueueState.WAITING_HUMAN)
            self.assertFalse(state.holds_capacity)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertEqual(count, len(value.repository.list_items(task_id)))
            self.assertEqual(0, len(value.repository.list_results(task_id)))
            # Analysis is zero-mutation and creates no legacy Job.
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            self.assertEqual(1, len(value.repository.list_tasks()))
            # The operator readback counts every admitted file exactly once.
            status, detail = self.request(value, f"/api/v1/operations/runs/{task_id}")
            self.assertEqual(200, status, detail)
            self.assertEqual(count, detail["total_items"])
            self.assertEqual([], detail["problem_types"])

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

    def _ignore(self, value, task_id, item):
        """Ignore one item through the existing Tasks recovery endpoint."""

        status, detail = self.request(
            value, f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery"
        )
        self.assertEqual(200, status, detail)
        status, ignored = self.request(
            value,
            f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery",
            "POST",
            {
                "actionId": "ignore",
                "expectedCheckpointVersion": detail["checkpoint"]["checkpoint_version"],
            },
        )
        self.assertEqual(200, status, ignored)
        return detail

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

    # -- B48.1-03: an ended Files attempt never holds the shared slot ---------

    def _ready_summary(self, value, task_id, discovery, paths):
        """Drive the real decision→analysis chain and read the fresh summary."""

        items = {item.source_path: item for item in value.repository.list_items(task_id)}
        for path in paths:
            self._decide_recognition(value, task_id, items[path])
        preview = self._analyze(value, task_id, discovery)
        ready = [entry["itemId"] for entry in preview["items"] if entry["status"] == "previewed"]
        return preview, ready

    _PUBLICATION_FAULT = "local review fixture: item result publication unavailable"

    def test_failed_result_publication_settles_the_ended_attempt_and_releases_the_slot(
        self,
    ) -> None:
        """The call returned; a failed publication never parks the whole Task.

        The real Files chain admits one file, the Worker performs the actual
        move, and only the final item/Result publication fails persistently.
        The ended attempt is retired with unknown-effect evidence and no
        fabricated Result, the linked execution closes with the same evidence,
        the flow completes, the shared slot is released, and later passes — and
        a database reopen — keep exactly those facts without any replay.
        """

        provider = self._two_file_recognition_journey()
        with self.journey(task_scheduling=True, provider=provider) as value:
            status, admitted = self._admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = self._drive(value, task_id)
            preview, ready = self._ready_summary(value, task_id, discovery, ["Movies/One.2001.mkv"])
            self.assertEqual(1, len(ready), preview)
            with mock.patch.object(
                value.repository,
                "complete_manual_execution_item",
                side_effect=RuntimeError(self._PUBLICATION_FAULT),
            ) as publication:
                task = self._execute(value, task_id, preview, ready, steps=1)
            self.assertGreaterEqual(publication.call_count, 1)
            # The flow completed although this file's own Result was never saved.
            self.assertIs(PersistentTaskStatus.COMPLETED, task.status, task.error)
            state = value.repository.get_task_scheduling(task_id)
            self.assertIs(TaskQueueState.SETTLED, state.queue_state)
            self.assertFalse(state.mutation_in_flight)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            (stored,) = value.repository.list_items(task_id)
            self.assertIs(TaskItemStatus.FAILED, stored.status)
            self.assertEqual("technical_stop", stored.stage)
            self.assertIn("unknown", stored.error or "")
            self.assertEqual(0, len(value.repository.list_results(task_id)))
            executions = value.repository.list_manual_executions_for_task(task_id)
            self.assertEqual(1, len(executions))
            self.assertIn(
                executions[0].status,
                {ManualExecutionStatus.PARTIAL_SUCCESS, ManualExecutionStatus.FAILED},
            )
            (execution_item,) = executions[0].items
            self.assertIs(ManualExecutionItemStatus.FAILED, execution_item.status)
            self.assertIsNone(execution_item.result_id)
            self.assertEqual("unknown", execution_item.effect_certainty)
            self.assertIn("result_persistence", execution_item.uncertain_effects)
            # The real mutation happened exactly once and is never replayed.
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())
            effects = list(value.source.mutations) + list(value.target.mutations)
            for _ in range(3):
                value.task_engine.run_next()
            self.assertEqual(effects, list(value.source.mutations) + list(value.target.mutations))
            self.assertIs(PersistentTaskStatus.COMPLETED, value.repository.get_task(task_id).status)
            with SQLiteTaskRepository(self.database) as reopened:
                self.assertIs(PersistentTaskStatus.COMPLETED, reopened.get_task(task_id).status)
                self.assertIs(
                    TaskQueueState.SETTLED, reopened.get_task_scheduling(task_id).queue_state
                )
                self.assertEqual(0, len(reopened.list_results(task_id)))
                (reopened_item,) = reopened.list_items(task_id)
                self.assertEqual("technical_stop", reopened_item.stage)

    def test_failed_publication_returns_the_pending_sibling_to_human_waiting(self) -> None:
        """A confirmed subset's ended attempt settles; the sibling stays owed.

        Two decided sources are analyzed but only the first is confirmed.  The
        Worker moves it and the result publication fails.  The ended attempt is
        retired, the sibling returns to human waiting on this same Task, the
        slot is released, and the operator continues the sibling without
        replaying the ended attempt or erasing its evidence.
        """

        provider = self._two_file_recognition_journey()
        with self.journey(task_scheduling=True, provider=provider) as value:
            status, admitted = self._admit(value, ["Movies/One.2001.mkv", "Movies/Two.2002.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = self._drive(value, task_id)
            preview, ready = self._ready_summary(
                value, task_id, discovery, ["Movies/One.2001.mkv", "Movies/Two.2002.mkv"]
            )
            self.assertEqual(2, len(ready), preview)
            with mock.patch.object(
                value.repository,
                "complete_manual_execution_item",
                side_effect=RuntimeError(self._PUBLICATION_FAULT),
            ):
                task = self._execute(value, task_id, preview, ready[:1], steps=1)
            # The ended attempt closed; the sibling's human work keeps the Task.
            self.assertIs(PersistentTaskStatus.RUNNING, task.status)
            state = value.repository.get_task_scheduling(task_id)
            self.assertIs(TaskQueueState.WAITING_HUMAN, state.queue_state)
            self.assertFalse(state.mutation_in_flight)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            items = {item.source_path: item for item in value.repository.list_items(task_id)}
            self.assertIs(TaskItemStatus.FAILED, items["Movies/One.2001.mkv"].status)
            self.assertEqual("technical_stop", items["Movies/One.2001.mkv"].stage)
            self.assertIs(TaskItemStatus.WAITING_CONFIRM, items["Movies/Two.2002.mkv"].status)
            self.assertEqual(0, len(value.repository.list_results(task_id)))
            executions = value.repository.list_manual_executions_for_task(task_id)
            self.assertEqual(1, len(executions))
            (execution_item,) = executions[0].items
            self.assertIs(ManualExecutionItemStatus.FAILED, execution_item.status)
            self.assertEqual("unknown", execution_item.effect_certainty)
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())
            self.assertTrue((self.source_root / "Movies/Two.2002.mkv").exists())

            # The operator continues the sibling on the same Task: the existing
            # re-analysis offers it again, the explicit confirmation runs, and
            # the flow completes with the ended attempt's evidence untouched.
            fresh = self._analyze(value, task_id, discovery)
            second_ready = [
                entry["itemId"] for entry in fresh["items"] if entry["status"] == "previewed"
            ]
            self.assertEqual(1, len(second_ready), fresh)
            final = self._execute(value, task_id, fresh, second_ready)
            self.assertIs(PersistentTaskStatus.COMPLETED, final.status, final.error)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            items = {item.source_path: item for item in value.repository.list_items(task_id)}
            self.assertIs(TaskItemStatus.FAILED, items["Movies/One.2001.mkv"].status)
            self.assertIs(TaskItemStatus.SUCCESS, items["Movies/Two.2002.mkv"].status)
            self.assertEqual(1, len(value.repository.list_results(task_id)))
            self.assertFalse((self.source_root / "Movies/Two.2002.mkv").exists())

    def test_accepted_cancel_settles_over_an_ended_attempt_with_its_evidence(self) -> None:
        """The cancel keeps priority; the ended attempt is never rewritten.

        The operator's cancel arrives while the real Worker is inside the only
        mutation and the result publication then fails.  The accepted cancel
        settles the Task; the ended attempt keeps its technical-stop evidence
        with no fabricated Result, the never-started tail is not executed, and
        the slot is released without any replay.
        """

        provider = self._two_file_recognition_journey()
        with self.journey(task_scheduling=True, provider=provider) as value:
            status, admitted = self._admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = self._drive(value, task_id)
            preview, ready = self._ready_summary(value, task_id, discovery, ["Movies/One.2001.mkv"])
            status, execution = self.request(
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
            self.assertIn(status, (200, 202), execution)

            original = value.executions._execute_plan

            def execute_then_cancel(plan, storages):
                result = original(plan, storages)
                task = value.repository.get_task(task_id)
                code, reply = self.request(
                    value,
                    f"/api/v1/tasks/{task_id}/cancel",
                    "POST",
                    {"expectedUpdatedAt": task.updated_at.isoformat()},
                )
                self.assertEqual(200, code, reply)
                return result

            with (
                mock.patch.object(
                    value.executions, "_execute_plan", side_effect=execute_then_cancel
                ),
                mock.patch.object(
                    value.repository,
                    "complete_manual_execution_item",
                    side_effect=RuntimeError(self._PUBLICATION_FAULT),
                ),
            ):
                value.task_engine.run_next()
            for _ in range(2):
                value.task_engine.run_next()

            task = value.repository.get_task(task_id)
            state = value.repository.get_task_scheduling(task_id)
            self.assertIs(PersistentTaskStatus.CANCELLED, task.status)
            self.assertIs(TaskQueueState.SETTLED, state.queue_state)
            self.assertFalse(state.mutation_in_flight)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            (stored,) = value.repository.list_items(task_id)
            self.assertIs(TaskItemStatus.FAILED, stored.status)
            self.assertEqual("technical_stop", stored.stage)
            self.assertEqual(0, len(value.repository.list_results(task_id)))
            executions = value.repository.list_manual_executions_for_task(task_id)
            self.assertEqual(1, len(executions))
            self.assertIs(ManualExecutionStatus.CANCELLED, executions[0].status)
            (execution_item,) = executions[0].items
            self.assertIs(ManualExecutionItemStatus.FAILED, execution_item.status)
            self.assertEqual("unknown", execution_item.effect_certainty)
            self.assertIn("result_persistence", execution_item.uncertain_effects)
            self.assertIsNone(execution_item.result_id)
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())
            effects = list(value.source.mutations) + list(value.target.mutations)
            for _ in range(2):
                value.task_engine.run_next()
            self.assertEqual(effects, list(value.source.mutations) + list(value.target.mutations))
            self.assertIs(PersistentTaskStatus.CANCELLED, value.repository.get_task(task_id).status)

    def test_a_call_that_never_returns_keeps_its_boundary_for_inspection(self) -> None:
        """A live unreturned call is never settled, rewritten or replayed.

        The real Worker enters the Storage mutation and the call never returns
        (the pass is destroyed mid-flight).  No settlement is written, the
        shared slot stays with the unproved boundary, and later passes keep
        that exact state instead of guessing an outcome.
        """

        class NeverReturned(BaseException):
            """The pass is destroyed while its only call is still executing."""

        provider = self._two_file_recognition_journey()
        with self.journey(task_scheduling=True, provider=provider) as value:
            status, admitted = self._admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = self._drive(value, task_id)
            preview, ready = self._ready_summary(value, task_id, discovery, ["Movies/One.2001.mkv"])
            status, execution = self.request(
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
            self.assertIn(status, (200, 202), execution)

            original = value.executions._execute_plan

            def execute_and_never_return(plan, storages):
                original(plan, storages)
                raise NeverReturned("the local call is still executing")

            with mock.patch.object(
                value.executions, "_execute_plan", side_effect=execute_and_never_return
            ):
                with self.assertRaises(NeverReturned):
                    value.task_engine.run_next()
            state = value.repository.get_task_scheduling(task_id)
            self.assertIs(PersistentTaskStatus.RUNNING, value.repository.get_task(task_id).status)
            self.assertTrue(state.mutation_in_flight)
            self.assertIs(TaskQueueState.CLAIMED, state.queue_state)
            self.assertEqual(1, value.repository.count_scheduled_capacity_use())
            (stored,) = value.repository.list_items(task_id)
            self.assertIs(TaskItemStatus.PROCESSING, stored.status)
            self.assertEqual(0, len(value.repository.list_results(task_id)))
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())
            effects = list(value.source.mutations) + list(value.target.mutations)
            for _ in range(2):
                self.assertIsNone(value.task_engine.run_next())
            self.assertEqual(effects, list(value.source.mutations) + list(value.target.mutations))
            self.assertTrue(value.repository.get_task_scheduling(task_id).mutation_in_flight)
            self.assertEqual(1, value.repository.count_scheduled_capacity_use())

    def test_unavailable_settlement_writes_neither_success_nor_failure(self) -> None:
        """A database that cannot save the settlement preserves the last facts.

        The result publication failed and the settlement boundary is unavailable
        too: the Task keeps its last durable state — running, marker and slot —
        instead of a fabricated terminal outcome, the retired attempt's evidence
        stays recorded, and no pass replays the media operation.
        """

        provider = self._two_file_recognition_journey()
        with self.journey(task_scheduling=True, provider=provider) as value:
            status, admitted = self._admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = self._drive(value, task_id)
            preview, ready = self._ready_summary(value, task_id, discovery, ["Movies/One.2001.mkv"])
            status, execution = self.request(
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
            self.assertIn(status, (200, 202), execution)
            with (
                mock.patch.object(
                    value.repository,
                    "complete_manual_execution_item",
                    side_effect=RuntimeError(self._PUBLICATION_FAULT),
                ),
                mock.patch.object(
                    value.repository,
                    "release_scheduled_claim",
                    side_effect=RuntimeError(
                        "local review fixture: settlement persistence unavailable"
                    ),
                ),
            ):
                value.task_engine.run_next()
            task = value.repository.get_task(task_id)
            state = value.repository.get_task_scheduling(task_id)
            self.assertIs(PersistentTaskStatus.RUNNING, task.status)
            self.assertIsNone(task.completed_at)
            self.assertTrue(state.mutation_in_flight)
            self.assertEqual(1, value.repository.count_scheduled_capacity_use())
            (stored,) = value.repository.list_items(task_id)
            self.assertIs(TaskItemStatus.FAILED, stored.status)
            self.assertEqual("technical_stop", stored.stage)
            self.assertEqual(0, len(value.repository.list_results(task_id)))
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())
            effects = list(value.source.mutations) + list(value.target.mutations)
            for _ in range(2):
                value.task_engine.run_next()
            self.assertEqual(effects, list(value.source.mutations) + list(value.target.mutations))
            self.assertIs(PersistentTaskStatus.RUNNING, value.repository.get_task(task_id).status)
            self.assertEqual(0, len(value.repository.list_results(task_id)))

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
            self.assertEqual(1, len(value.repository.list_tasks()))
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
            self.assertEqual(1, len(value.repository.list_tasks()))

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
            self.assertEqual(2, len(value.repository.list_tasks()))
            self.assertEqual([], value.source.mutations)

            # The competing Task reaches its own human boundary (zero slots);
            # the operator's explicit retry now re-registers the same Task.
            self._drive(value, second_task_id)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            status, accepted = self._continue_from_task_center(value, task_id, item.item_id, saving)
            self.assertEqual(202, status, accepted)
            self.assertEqual(task_id, accepted["taskId"])
            self.assertEqual(2, len(value.repository.list_tasks()))
            self._drive(value, task_id)
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.WAITING_HUMAN,
            )
            self.assertEqual([], value.source.mutations)

    def test_lowered_system_capacity_applies_to_an_already_prepared_summary(self) -> None:
        """B-P1-2: the current allowance applies when an old summary is confirmed.

        The first file's exact summary was prepared while the published
        allowance was 1025 and is now waiting for the operator.  The system
        setting is lowered to 1 and a separate request for the second file takes
        that only slot.  Confirming the old summary must be refused by the
        *current* allowance even though its immutable execution pin still names
        1025.  The summary, Task, source and one-shot authority stay unconsumed;
        after the competing Task reaches its own human boundary the same
        explicit confirmation succeeds and the real Worker performs the effect.
        """

        for name in ("One.2001.mkv", "Two.2002.mkv"):
            self.media(f"Movies/{name}")
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate(
                    "tmdb",
                    "201",
                    MediaType.MOVIE,
                    "One",
                    year=2001,
                    genres=("Animation",),
                ),
                MediaCandidate(
                    "tmdb",
                    "202",
                    MediaType.MOVIE,
                    "Two",
                    year=2002,
                    genres=("Animation",),
                ),
            )
        )
        original_document = self.document

        def high_capacity(**kwargs):
            document = original_document(**kwargs)
            document["automation"]["maximumActiveJobs"] = 1025
            return document

        with (
            mock.patch.object(self, "document", side_effect=high_capacity),
            self.journey(provider=provider, task_scheduling=True, attachments=True) as value,
        ):
            status, admitted = self._admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = self._drive(value, task_id)
            self.assertIsNotNone(discovery.preview_id)
            preview = value.repository.get_manual_preview(discovery.preview_id)
            old_pin = (preview.configuration_snapshot_id, preview.configuration_snapshot_digest)
            status, preview_document = self.request(
                value, f"/api/v1/operations/organize/previews/{preview.preview_id}"
            )
            self.assertEqual(200, status, preview_document)
            ready = [
                item["itemId"]
                for item in preview_document["items"]
                if item["status"] == "previewed"
            ]
            self.assertEqual(1, len(ready), preview_document)
            confirmation = {
                "confirmation": True,
                "itemIds": ready,
                "expectedIntentVersion": preview_document["intentVersion"],
                "allowOverwrite": False,
                "allowSourceCleanup": False,
            }

            # Lower the system allowance and admit a second deliberate Files
            # request under it.  The second Task holds the only shared slot.
            self._publish_capacity(value, 1)
            status, competitor = self._admit(
                value,
                ["Movies/Two.2002.mkv"],
                request_id="22222222-2222-4222-8222-222222222222",
            )
            self.assertEqual(202, status, competitor)
            competitor_task_id = competitor["organizeTaskId"]
            self.assertEqual(1, value.repository.count_scheduled_capacity_use())

            # The old summary is still itself current; only the current shared
            # capacity refuses it.  Nothing is consumed or mutated.
            status, refused = self.request(
                value,
                f"/api/v1/operations/organize/previews/{preview.preview_id}/execute",
                "POST",
                confirmation,
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("capacity_full", refused["error"]["code"])
            self.assertEqual("none", refused["error"]["details"]["sideEffects"])
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.WAITING_HUMAN,
            )
            self.assertEqual(
                (), value.repository.list_manual_executions_for_preview(preview.preview_id)
            )
            self.assertEqual(
                [],
                [
                    authorization
                    for authorization in (
                        value.repository.list_manual_execution_authorizations_for_preview(
                            preview.preview_id
                        )
                    )
                    if authorization.status.value == "consumed"
                ],
            )
            self.assertEqual(
                old_pin,
                (
                    value.repository.get_manual_preview(
                        preview.preview_id
                    ).configuration_snapshot_id,
                    value.repository.get_manual_preview(
                        preview.preview_id
                    ).configuration_snapshot_digest,
                ),
            )
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            # The competing Task reaches its own human boundary and releases the only slot;
            # the operator's explicit retry of the same summary now succeeds.
            self._drive(value, competitor_task_id)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            status, accepted = self.request(
                value,
                f"/api/v1/operations/organize/previews/{preview.preview_id}/execute",
                "POST",
                confirmation,
            )
            self.assertIn(status, (200, 202), accepted)
            self.assertEqual(task_id, accepted["taskId"])
            self.assertEqual(
                old_pin,
                (
                    value.repository.get_manual_preview(
                        preview.preview_id
                    ).configuration_snapshot_id,
                    value.repository.get_manual_preview(
                        preview.preview_id
                    ).configuration_snapshot_digest,
                ),
            )
            for _ in range(8):
                value.task_engine.run_next()
                task = value.repository.get_task(task_id)
                if task.status in {
                    PersistentTaskStatus.COMPLETED,
                    PersistentTaskStatus.PARTIAL_SUCCESS,
                    PersistentTaskStatus.FAILED,
                    PersistentTaskStatus.CANCELLED,
                }:
                    break
            self.assertIs(value.repository.get_task(task_id).status, PersistentTaskStatus.COMPLETED)
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())
            self.assertTrue((self.source_root / "Movies/Two.2002.mkv").exists())

    def test_recovery_summary_confirmation_uses_current_system_capacity(self) -> None:
        """A four-type recovery summary shares the same current-capacity boundary.

        The native Task Center summary was prepared under 1025.  A successor
        allowance of 1 and a competing Files Task then fill the shared queue;
        confirming the prepared recovery summary must refuse without consuming
        it.  Releasing the competitor lets the same explicit confirmation
        re-register the original Task.
        """

        provider = self._two_file_recognition_journey()
        original_document = self.document

        def high_capacity(**kwargs):
            document = original_document(**kwargs)
            document["automation"]["maximumActiveJobs"] = 1025
            return document

        with (
            mock.patch.object(self, "document", side_effect=high_capacity),
            self.journey(provider=provider, task_scheduling=True) as value,
        ):
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
            self.assertEqual("business_problem", detail["recoveryKind"])
            status, prepared = self.request(
                value,
                f"/api/v1/tasks/{task_id}/items/{item.item_id}/recovery/prepare-summary",
                "POST",
                {"expectedCheckpointVersion": detail["checkpoint"]["checkpoint_version"]},
            )
            self.assertEqual(201, status, prepared)
            status, preview = self.request(
                value,
                f"/api/v1/operations/organize/previews/{prepared['preview_id']}",
            )
            self.assertEqual(200, status, preview)
            ready = [
                entry["itemId"] for entry in preview["items"] if entry["status"] == "previewed"
            ]
            self.assertEqual(1, len(ready), preview)

            # Lower the allowance and take the only slot with a different
            # deliberate Files request.
            self._publish_capacity(value, 1)
            status, competitor = self._admit(
                value,
                ["Movies/Two.2002.mkv"],
                request_id="44444444-4444-4444-8444-444444444444",
            )
            self.assertEqual(202, status, competitor)
            competitor_task_id = competitor["organizeTaskId"]
            self.assertEqual(1, value.repository.count_scheduled_capacity_use())

            confirmation = {
                "itemIds": ready,
                "confirmation": True,
                "allowOverwrite": False,
                "allowSourceCleanup": False,
            }
            status, refused = self.request(
                value,
                f"/api/v1/manual-recovery-preparations/{prepared['preparation_id']}/confirm",
                "POST",
                confirmation,
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("capacity_full", refused["error"]["code"])
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.WAITING_HUMAN,
            )
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            # The competing Task reaches its own human boundary and releases
            # the only slot; the same recovery confirmation now succeeds.
            self._drive(value, competitor_task_id)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            status, confirmed = self.request(
                value,
                f"/api/v1/manual-recovery-preparations/{prepared['preparation_id']}/confirm",
                "POST",
                confirmation,
            )
            self.assertIn(status, (200, 202), confirmed)
            self.assertEqual(task_id, confirmed["taskId"])

    def test_raised_system_capacity_applies_to_an_already_prepared_summary(self) -> None:
        """The reverse direction also uses the current allowance, not the old pin."""

        for name in ("One.2001.mkv", "Two.2002.mkv"):
            self.media(f"Movies/{name}")
        provider = SyntheticMetadataProvider(
            (
                MediaCandidate(
                    "tmdb",
                    "201",
                    MediaType.MOVIE,
                    "One",
                    year=2001,
                    genres=("Animation",),
                ),
                MediaCandidate(
                    "tmdb",
                    "202",
                    MediaType.MOVIE,
                    "Two",
                    year=2002,
                    genres=("Animation",),
                ),
            )
        )
        original_document = self.document

        def one_slot(**kwargs):
            document = original_document(**kwargs)
            document["automation"]["maximumActiveJobs"] = 1
            return document

        with (
            mock.patch.object(self, "document", side_effect=one_slot),
            self.journey(provider=provider, task_scheduling=True, attachments=True) as value,
        ):
            status, admitted = self._admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = self._drive(value, task_id)
            status, preview_document = self.request(
                value, f"/api/v1/operations/organize/previews/{discovery.preview_id}"
            )
            self.assertEqual(200, status, preview_document)
            ready = [
                item["itemId"]
                for item in preview_document["items"]
                if item["status"] == "previewed"
            ]
            confirmation = {
                "confirmation": True,
                "itemIds": ready,
                "expectedIntentVersion": preview_document["intentVersion"],
                "allowOverwrite": False,
                "allowSourceCleanup": False,
            }
            # A competing File holds the old one-slot allowance.
            status, six = self._admit(
                value,
                ["Movies/Two.2002.mkv"],
                request_id="33333333-3333-4333-8333-333333333333",
            )
            self.assertEqual(202, status, six)
            self.assertEqual(1, value.repository.count_scheduled_capacity_use())

            # Raising the published allowance to 2 makes room for the same old
            # summary; using the old pin would still refuse it at 1.
            self._publish_capacity(value, 2)
            status, accepted = self.request(
                value,
                f"/api/v1/operations/organize/previews/{discovery.preview_id}/execute",
                "POST",
                confirmation,
            )
            self.assertIn(status, (200, 202), accepted)
            self.assertEqual(task_id, accepted["taskId"])

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
            self.assertEqual(2, len(value.repository.list_tasks()))

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
            self.assertEqual(1, len(value.repository.list_tasks()))
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
            # failure: both file facts stay independent.  Slice 48 RO-1: the
            # flow itself completed — file outcomes are never the flow status.
            self.assertIs(final.status, PersistentTaskStatus.COMPLETED, final.error)
            self.assertEqual(
                (2, 2, 1),
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
            self.assertEqual(1, len(value.repository.list_tasks()))

            for _ in range(8):
                value.task_engine.run_next()
            final = value.repository.get_task(task_id)
            self.assertIs(final.status, PersistentTaskStatus.COMPLETED, final.error)
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.SETTLED,
            )
            self.assertEqual(1, len(value.repository.list_results(task_id)))
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

    # -- Ignored-source scope and settled-outcome task endings ---------------

    def test_ignored_source_is_not_reoffered_by_the_same_tasks_reanalysis(self) -> None:
        """An ignored source never re-enters its own Task's executable scope.

        One source needs a Metadata candidate review and the operator ignores
        it.  A later, normal upstream correction makes that source unambiguous,
        and the operator reruns the existing analysis to continue the untouched
        sibling.  The ignored source must not be offered again, must keep its
        own item/audit, and must never produce a Result even though the sibling
        still completes its own work on the same Task.
        """

        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        first = MediaCandidate(
            "tmdb",
            "201",
            MediaType.MOVIE,
            "One",
            year=2001,
            genres=("Animation",),
            countries=("JP",),
        )
        duplicate = MediaCandidate(
            "tmdb",
            "202",
            MediaType.MOVIE,
            "One",
            year=2001,
            genres=("Animation",),
            countries=("JP",),
        )
        second = MediaCandidate(
            "tmdb",
            "203",
            MediaType.MOVIE,
            "Two",
            year=2002,
            genres=("Animation",),
            countries=("JP",),
        )
        provider = SyntheticMetadataProvider((first, duplicate, second))
        with self.journey(provider=provider, task_scheduling=True, attachments=True) as value:
            status, admitted = self._admit(value, ["Movies/One.2001.mkv", "Movies/Two.2002.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = self._drive(value, task_id)
            items = {item.source_path: item for item in value.repository.list_items(task_id)}
            ignored_item = items["Movies/One.2001.mkv"]
            self.assertIs(ignored_item.status, TaskItemStatus.WAITING_METADATA)
            self.assertIs(items["Movies/Two.2002.mkv"].status, TaskItemStatus.WAITING_CONFIRM)

            self._ignore(value, task_id, ignored_item)
            self.assertIs(
                value.repository.get_item(ignored_item.item_id).status, TaskItemStatus.IGNORED
            )
            self.assertEqual(
                ["ignore"],
                [
                    request.action_id
                    for request in value.repository.list_recovery_requests(ignored_item.item_id)
                ],
            )
            # The sibling is still actionable, so the Task keeps waiting rather
            # than settling early.
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.WAITING_HUMAN,
            )
            self.assertIs(value.repository.get_task(task_id).status, PersistentTaskStatus.RUNNING)

            # A normal upstream correction makes One unambiguous.  The existing
            # re-analysis must not fold the ignored source back into the plan.
            provider._candidates = (first, second)
            fresh = self._analyze(value, task_id, discovery)
            self.assertEqual(
                ["Movies/Two.2002.mkv"],
                [entry["source"]["path"] for entry in fresh["items"]],
            )
            self.assertIs(
                value.repository.get_item(ignored_item.item_id).status, TaskItemStatus.IGNORED
            )
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            status, detail = self.request(
                value, f"/api/v1/tasks/{task_id}/items/{ignored_item.item_id}/recovery"
            )
            self.assertEqual(200, status, detail)
            self.assertEqual("ignored", detail["checkpoint"]["status"])

            ready = [entry["itemId"] for entry in fresh["items"] if entry["status"] == "previewed"]
            final = self._execute(value, task_id, fresh, ready)
            # Slice 48 RO-1: the ignored sibling is a settled file fact; the
            # flow completed with both facts readable.
            self.assertIs(final.status, PersistentTaskStatus.COMPLETED, final.error)
            self.assertEqual(
                (2, 2, 0), (final.total_items, final.completed_items, final.failed_items)
            )
            self.assertIs(
                value.repository.get_item(ignored_item.item_id).status, TaskItemStatus.IGNORED
            )
            self.assertTrue((self.source_root / "Movies/One.2001.mkv").exists())
            self.assertFalse((self.source_root / "Movies/Two.2002.mkv").exists())
            results = value.repository.list_results(task_id)
            self.assertEqual(1, len(results), results)
            self.assertEqual("Movies/Two.2002.mkv", results[0].source_path)
            self.assertEqual(1, len(value.repository.list_tasks()))
            with SQLiteTaskRepository(self.database) as reopened:
                self.assertIs(
                    reopened.get_item(ignored_item.item_id).status, TaskItemStatus.IGNORED
                )
                self.assertIs(reopened.get_task(task_id).status, PersistentTaskStatus.COMPLETED)
                self.assertTrue((self.source_root / "Movies/One.2001.mkv").exists())

    def test_last_ignored_item_settles_the_task(self) -> None:
        """Finishing the only source by ignoring it ends the Task honestly.

        No decision, confirmation or machine stage remains once the last source
        is ignored, so the Task must stop showing Running/waiting_human forever.
        The ignored outcome is preserved as a non-success aggregate without any
        Storage mutation or occupied slot.
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
        with self.journey(provider=provider, task_scheduling=True, attachments=True) as value:
            status, admitted = self._admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            self._drive(value, task_id)
            item = value.repository.list_items(task_id)[0]
            self.assertIs(item.status, TaskItemStatus.WAITING_METADATA)

            self._ignore(value, task_id, item)

            task = value.repository.get_task(task_id)
            # Slice 48 RO-1: an ignored source is a settled file fact; the
            # flow completed and the ignored outcome stays on the item.
            self.assertIs(task.status, PersistentTaskStatus.COMPLETED, task.error)
            state = value.repository.get_task_scheduling(task_id)
            self.assertIs(state.queue_state, TaskQueueState.SETTLED)
            self.assertFalse(state.holds_capacity)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            status, run = self.request(value, f"/api/v1/operations/runs/{task_id}")
            self.assertEqual(200, status, run)
            self.assertTrue(run["lifecycle"]["terminal"])
            self.assertEqual("completed", run["status"])
            # Further Worker passes add nothing: the work is already final.
            for _ in range(5):
                value.task_engine.run_next()
            self.assertIs(value.repository.get_task(task_id).status, PersistentTaskStatus.COMPLETED)
            with SQLiteTaskRepository(self.database) as reopened:
                self.assertIs(reopened.get_task(task_id).status, PersistentTaskStatus.COMPLETED)
                self.assertIs(reopened.get_item(item.item_id).status, TaskItemStatus.IGNORED)
                self.assertIs(
                    reopened.get_task_scheduling(task_id).queue_state, TaskQueueState.SETTLED
                )

    def test_all_technical_analysis_failures_settle_the_task(self) -> None:
        """A solely technical analysis failure ends the Task as a factual failure.

        The Provider timeout is an existing bounded failure, not a business
        decision.  With no waiting item and no machine work left, the Task must
        settle as Failed instead of staying permanently Running, and it must
        remain read-only with no Storage mutation.
        """

        class Unavailable(SyntheticMetadataProvider):
            def search_movie(self, *args, **kwargs):
                raise TimeoutError("synthetic Provider network timeout")

        self.media("Movies/One.2001.mkv")
        with self.journey(
            provider=Unavailable(()), task_scheduling=True, attachments=True
        ) as value:
            status, admitted = self._admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            self._drive(value, task_id)
            item = value.repository.list_items(task_id)[0]
            self.assertIs(item.status, TaskItemStatus.FAILED)

            task = value.repository.get_task(task_id)
            # Slice 48 RO-2: a solely technical analysis failure is file-local
            # evidence; the flow completed without demanding a formal Result.
            self.assertIs(task.status, PersistentTaskStatus.COMPLETED, task.error)
            state = value.repository.get_task_scheduling(task_id)
            self.assertIs(state.queue_state, TaskQueueState.SETTLED)
            self.assertFalse(state.holds_capacity)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            status, run = self.request(value, f"/api/v1/operations/runs/{task_id}")
            self.assertEqual(200, status, run)
            self.assertTrue(run["lifecycle"]["terminal"])
            self.assertEqual("completed", run["status"])
            self.assertEqual((), value.repository.list_results(task_id))
            with SQLiteTaskRepository(self.database) as reopened:
                self.assertIs(reopened.get_task(task_id).status, PersistentTaskStatus.COMPLETED)

    def test_reanalysis_failure_settles_the_reused_items_task(self) -> None:
        """A failed re-analysis of a ready source ends its own Task honestly.

        A source needing no business decision waits for the operator's exact
        initial confirmation.  When the operator re-runs the analysis and the
        upstream Provider fails, that failure belongs to the source's *existing*
        item: the item, the Task, the counters and the run API must record the
        factual failure and settle, instead of leaving the item forever at
        waiting_confirm and the Task forever Running with no problem and no
        machine work.
        """

        class Unavailable(SyntheticMetadataProvider):
            unavailable = False

            def search_movie(self, *args, **kwargs):
                if self.unavailable:
                    raise TimeoutError("synthetic upstream timeout on explicit re-analysis")
                return super().search_movie(*args, **kwargs)

        self.media("Movies/One.2001.mkv")
        provider = Unavailable(
            (
                MediaCandidate(
                    "tmdb", "201", MediaType.MOVIE, "One", year=2001, genres=("Animation",)
                ),
            )
        )
        with self.journey(provider=provider, task_scheduling=True, attachments=True) as value:
            status, admitted = self._admit(value, ["Movies/One.2001.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = self._drive(value, task_id)
            item = value.repository.list_items(task_id)[0]
            self.assertIs(item.status, TaskItemStatus.WAITING_CONFIRM)
            self.assertIs(value.repository.get_task(task_id).status, PersistentTaskStatus.RUNNING)

            provider.unavailable = True
            fresh = self._analyze(value, task_id, discovery)
            self.assertEqual(["failed"], [entry["status"] for entry in fresh["items"]])
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

            stored = value.repository.get_item(item.item_id)
            self.assertIs(stored.status, TaskItemStatus.FAILED)
            self.assertEqual("analysis_failed", stored.stage)
            self.assertIn("synthetic upstream timeout", stored.error or "")
            task = value.repository.get_task(task_id)
            # Slice 48 RO-2/RO-3: the ended technical attempt is ended progress
            # (1 of 1), the file failure stays on the item, and the flow
            # completed without a formal Result.
            self.assertIs(task.status, PersistentTaskStatus.COMPLETED, task.error)
            self.assertEqual((1, 1, 1), (task.total_items, task.completed_items, task.failed_items))
            state = value.repository.get_task_scheduling(task_id)
            self.assertIs(state.queue_state, TaskQueueState.SETTLED)
            self.assertFalse(state.holds_capacity)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            counts, run_counts = self._task_api_counts(value, task_id)
            self.assertEqual((1, 1, 1), counts)
            self.assertEqual((1, 1, 1), run_counts)
            status, run = self.request(value, f"/api/v1/operations/runs/{task_id}")
            self.assertEqual(200, status, run)
            self.assertTrue(run["lifecycle"]["terminal"])
            self.assertEqual("completed", run["status"])
            self.assertEqual((), value.repository.list_results(task_id))
            # Idle Worker passes never change the settled factual end.
            for _ in range(5):
                value.task_engine.run_next()
            self.assertIs(value.repository.get_task(task_id).status, PersistentTaskStatus.COMPLETED)
            with SQLiteTaskRepository(self.database) as reopened:
                self.assertIs(reopened.get_task(task_id).status, PersistentTaskStatus.COMPLETED)
                self.assertIs(reopened.get_item(item.item_id).status, TaskItemStatus.FAILED)
                self.assertIs(
                    reopened.get_task_scheduling(task_id).queue_state, TaskQueueState.SETTLED
                )

    def test_reanalysis_failure_preserves_a_successful_sibling(self) -> None:
        """A source failure never rewrites or replays a finished sibling.

        One of two ready sources is explicitly confirmed and organized, so it
        owns a Result and a settled item.  The remaining source then fails on a
        fresh analysis.  That source must record its own failure on the same
        Task while the successful sibling keeps its item, Result and effect; the
        Task ends PartialSuccess and never replays the finished source.
        """

        class Unavailable(SyntheticMetadataProvider):
            unavailable = False

            def search_movie(self, *args, **kwargs):
                if self.unavailable:
                    raise TimeoutError("synthetic upstream timeout on explicit re-analysis")
                return super().search_movie(*args, **kwargs)

        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        provider = Unavailable(
            (
                MediaCandidate(
                    "tmdb", "201", MediaType.MOVIE, "One", year=2001, genres=("Animation",)
                ),
                MediaCandidate(
                    "tmdb", "202", MediaType.MOVIE, "Two", year=2002, genres=("Animation",)
                ),
            )
        )
        with self.journey(provider=provider, task_scheduling=True, attachments=True) as value:
            status, admitted = self._admit(value, ["Movies/One.2001.mkv", "Movies/Two.2002.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            discovery = self._drive(value, task_id)
            items = {item.source_path: item for item in value.repository.list_items(task_id)}
            self.assertEqual(2, len(items))
            status, preview = self.request(
                value, f"/api/v1/operations/organize/previews/{discovery.preview_id}"
            )
            self.assertEqual(200, status, preview)
            first = next(
                entry["itemId"]
                for entry in preview["items"]
                if entry["source"]["path"] == "Movies/One.2001.mkv"
            )
            task = self._execute(value, task_id, preview, [first])
            self.assertIs(task.status, PersistentTaskStatus.RUNNING, task.error)
            self.assertEqual((2, 1, 0), (task.total_items, task.completed_items, task.failed_items))
            self.assertEqual(1, len(value.repository.list_results(task_id)))
            first_result = value.repository.list_results(task_id)[0]
            self.assertIs(
                value.repository.get_item(items["Movies/One.2001.mkv"].item_id).status,
                TaskItemStatus.SUCCESS,
            )
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())

            provider.unavailable = True
            fresh = self._analyze(value, task_id, discovery)
            self.assertEqual(
                ["Movies/Two.2002.mkv"],
                [entry["source"]["path"] for entry in fresh["items"]],
            )
            self.assertEqual(["failed"], [entry["status"] for entry in fresh["items"]])

            self.assertIs(
                value.repository.get_item(items["Movies/Two.2002.mkv"].item_id).status,
                TaskItemStatus.FAILED,
            )
            self.assertIs(
                value.repository.get_item(items["Movies/One.2001.mkv"].item_id).status,
                TaskItemStatus.SUCCESS,
            )
            task = value.repository.get_task(task_id)
            # Slice 48 RO-1: the flow completed; both file facts stay readable.
            self.assertIs(task.status, PersistentTaskStatus.COMPLETED, task.error)
            self.assertEqual((2, 2, 1), (task.total_items, task.completed_items, task.failed_items))
            self.assertIs(
                value.repository.get_task_scheduling(task_id).queue_state,
                TaskQueueState.SETTLED,
            )
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            counts, run_counts = self._task_api_counts(value, task_id)
            self.assertEqual((2, 2, 1), counts)
            self.assertEqual((2, 2, 1), run_counts)
            results = value.repository.list_results(task_id)
            self.assertEqual(1, len(results), results)
            self.assertEqual(first_result.result_id, results[0].result_id)
            self.assertEqual("Movies/One.2001.mkv", results[0].source_path)
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())
            self.assertTrue((self.source_root / "Movies/Two.2002.mkv").exists())
            self.assertEqual(1, len(value.repository.list_tasks()))
            with SQLiteTaskRepository(self.database) as reopened:
                self.assertIs(reopened.get_task(task_id).status, PersistentTaskStatus.COMPLETED)
                self.assertEqual(1, len(reopened.list_results(task_id)))
                self.assertIs(
                    reopened.get_item(items["Movies/Two.2002.mkv"].item_id).status,
                    TaskItemStatus.FAILED,
                )

    def test_reanalysis_failure_keeps_an_undecided_sibling_waiting(self) -> None:
        """A failed re-analysis never ends another source's pending decision.

        Two sources await their own RecognitionType.  The operator decides only
        the first, and the upstream Provider then fails while re-analyzing it.
        The decided source records its own factual failure on its existing item,
        while the still-undecided sibling keeps its pending review, waiting item
        and untouched source on the same Task instead of being settled
        prematurely.
        """

        class Unavailable(SyntheticMetadataProvider):
            unavailable = False

            def search_movie(self, *args, **kwargs):
                if self.unavailable:
                    raise TimeoutError("synthetic upstream timeout on explicit re-analysis")
                return super().search_movie(*args, **kwargs)

        for name in ("One.2001.mkv", "Two.2002.mkv"):
            self.media(f"Movies/{name}")
        provider = Unavailable(
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
            items = {item.source_path: item for item in value.repository.list_items(task_id)}
            first = items["Movies/One.2001.mkv"]
            second = items["Movies/Two.2002.mkv"]
            self.assertIs(first.status, TaskItemStatus.WAITING_RECOGNITION)
            self.assertIs(second.status, TaskItemStatus.WAITING_RECOGNITION)

            self._decide_recognition(value, task_id, first)
            provider.unavailable = True
            fresh = self._analyze(value, task_id, discovery)

            statuses = {entry["source"]["path"]: entry["status"] for entry in fresh["items"]}
            self.assertEqual("failed", statuses["Movies/One.2001.mkv"])
            self.assertIn(statuses["Movies/Two.2002.mkv"], {"blocked", "unavailable"})
            self.assertIs(value.repository.get_item(first.item_id).status, TaskItemStatus.FAILED)
            self.assertIs(
                value.repository.get_item(second.item_id).status,
                TaskItemStatus.WAITING_RECOGNITION,
            )
            pending = value.repository.get_recognition_review_for_item(second.item_id)
            self.assertIsNotNone(pending)
            self.assertEqual("pending", pending.status.value)
            task = value.repository.get_task(task_id)
            self.assertIs(task.status, PersistentTaskStatus.RUNNING, task.error)
            state = value.repository.get_task_scheduling(task_id)
            self.assertIs(state.queue_state, TaskQueueState.WAITING_HUMAN)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            self.assertEqual((), value.repository.list_results(task_id))

    def test_ignore_keeps_the_task_waiting_while_a_sibling_is_undecided(self) -> None:
        """A still-undecided sibling is never settled prematurely by an ignore.

        Two sources both wait for their own Recognition decision.  Ignoring one
        leaves a real pending decision on the other, so the Task keeps its
        waiting identity and slot release instead of ending as if the whole batch
        were over.
        """

        provider = self._two_file_recognition_journey()
        with self.journey(provider=provider, task_scheduling=True) as value:
            status, admitted = self._admit(value, ["Movies/One.2001.mkv", "Movies/Two.2002.mkv"])
            self.assertEqual(202, status, admitted)
            task_id = admitted["organizeTaskId"]
            self._drive(value, task_id)
            items = {item.source_path: item for item in value.repository.list_items(task_id)}
            first = items["Movies/One.2001.mkv"]
            second = items["Movies/Two.2002.mkv"]
            self.assertIs(first.status, TaskItemStatus.WAITING_RECOGNITION)
            self.assertIs(second.status, TaskItemStatus.WAITING_RECOGNITION)

            self._ignore(value, task_id, first)

            self.assertIs(value.repository.get_item(first.item_id).status, TaskItemStatus.IGNORED)
            self.assertIs(
                value.repository.get_item(second.item_id).status,
                TaskItemStatus.WAITING_RECOGNITION,
            )
            task = value.repository.get_task(task_id)
            self.assertIs(task.status, PersistentTaskStatus.RUNNING, task.error)
            state = value.repository.get_task_scheduling(task_id)
            self.assertIs(state.queue_state, TaskQueueState.WAITING_HUMAN)
            self.assertEqual(0, value.repository.count_scheduled_capacity_use())
            self.assertEqual([], value.source.mutations)


if __name__ == "__main__":
    unittest.main()
