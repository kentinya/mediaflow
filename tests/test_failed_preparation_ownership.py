"""PATCH-20261109-3 — failed organizing releases its files; entry eligibility is one backend fact.

Every journey in this module drives the real production entrances — the Files
admission API, the resident Task engine, the summary confirmation API and the
run-detail read — and asserts the durable outcome.  No test injects an
eligibility answer into production state or presents a synthetic row as a user
journey.  Two evidence kinds are used, each labeled where it applies:

* ``production failure publication`` — the failure is produced through the Task
  engine's own ``_fail_discovery`` boundary, exactly the way a real unreadable
  analysis pass (``DiscoveryUnavailable``) or a per-item analysis fault surfaces
  to the Worker; nothing about the ownership or eligibility answer is written
  by the test.
* durable-state and read-back assertions afterwards.

Reused fixtures: the real managed runtime, Local Storage, SQLite repository,
fake Provider and Task engine shared by ``tests.test_media_discovery``, plus
the Files hand-off helpers of ``tests.test_organize_source_history``.  No
production state interface is introduced.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from mediaflow.application.media_discovery import DiscoveryUnavailable
from mediaflow.application.strategy_test import SyntheticMetadataProvider
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.task_persistence import PersistentTaskStatus, TaskItemStatus
from tests.test_organize_source_history import (
    _SupersededHandoffFixture,
)


def _provider(*candidates: MediaCandidate) -> SyntheticMetadataProvider:
    return SyntheticMetadataProvider(candidates)


class WholeFlowPassFailureReleasesEveryFileTests(_SupersededHandoffFixture):
    """Failure before any summary: the flow ends and the file is released.

    Production failure publication: the analysis pass becomes unreadable the
    same way a real fault surfaces to the engine — ``run_claimed`` raises and
    the engine's own ``_fail_discovery`` boundary publishes the Task/TaskItem
    failure.  The discovery record itself is never settled (no Worker owns the
    terminal Task any more), which is exactly the durable state whose
    preparation ownership previously wedged the file forever.
    """

    def test_unreadable_pass_fails_the_flow_and_releases_the_file(self):
        self.media("Movies/One.2001.mkv")
        provider = _provider(MediaCandidate("tmdb", "201", MediaType.MOVIE, "One", year=2001))
        with self.journey(provider=provider, task_scheduling=True, attachments=True) as value:
            status, admitted = self._admit(
                value,
                ["Movies/One.2001.mkv"],
                request_id="11111111-1111-4111-8111-111111111111",
            )
            self.assertEqual(202, status, admitted)
            old_id = admitted["organizeTaskId"]
            discovery_id = admitted["discoveryId"]

            with patch.object(
                value.discovery,
                "run_claimed",
                side_effect=DiscoveryUnavailable("the claimed discovery is no longer readable"),
            ):
                self._drive(value, old_id, steps=4)

            # The production failure publication: the Task flow is failed.  The
            # first pass never reached its per-item projection, so the Task
            # honestly holds no item rows at all.
            task = value.repository.get_task(old_id)
            self.assertEqual(PersistentTaskStatus.FAILED, task.status)
            self.assertEqual((), value.repository.list_items(old_id))
            record = value.repository.get_media_discovery(discovery_id)
            self.assertIsNotNone(record)
            self.assertFalse(record.terminal)
            self.assertEqual([], value.target.mutations)

            # The ended flow's run detail keeps the preparation identity but
            # publishes the backend eligibility fact: no execution entry.
            code, body = self.request(value, f"/api/v1/operations/runs/{old_id}")
            self.assertEqual(200, code, body)
            self.assertEqual(
                {
                    "discoveryId": discovery_id,
                    "resourceLibraryId": "library",
                    "continuable": False,
                },
                body["filesPreparation"],
            )

            # The deliberate new Files organize of the same file is admitted
            # without cancelling the terminal Task or clearing any record.
            status, fresh = self._admit(
                value,
                ["Movies/One.2001.mkv"],
                request_id="22222222-2222-4222-8222-222222222222",
            )
            self.assertEqual(202, status, fresh)
            self.assertNotEqual(old_id, fresh["organizeTaskId"])

            # A lost-response retry of the ORIGINAL request identity reconciles
            # to the work it already created instead of minting a second one.
            status, retry = self._admit(
                value,
                ["Movies/One.2001.mkv"],
                request_id="11111111-1111-4111-8111-111111111111",
            )
            self.assertEqual(202, status, retry)
            self.assertEqual(discovery_id, retry["discoveryId"])
            self.assertEqual(old_id, retry["organizeTaskId"])

            # The recorded evidence of the ended flow is untouched, and nothing
            # mutated before any explicit confirmation.
            self.assertEqual(PersistentTaskStatus.FAILED, value.repository.get_task(old_id).status)
            self.assertEqual((), value.repository.list_items(old_id))
            self.assertEqual([], value.target.mutations)


class EndedFlowOldSummaryRefusalTests(_SupersededHandoffFixture):
    """Failure after a summary: the flow ends and the old summary is read-only.

    Production failure publication: the operator explicitly requests a
    re-analysis of the completed preparation through the real API entrance,
    and the re-analysis pass becomes unreadable — the engine's own
    ``_fail_discovery`` boundary fails the flow while the already-published
    waiting items stay exactly what they were.
    """

    def test_reanalysis_failure_ends_the_flow_and_the_old_summary_cannot_confirm(self):
        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        provider = _provider(
            MediaCandidate("tmdb", "201", MediaType.MOVIE, "One", year=2001),
            MediaCandidate("tmdb", "202", MediaType.MOVIE, "Two", year=2002),
        )
        with self.journey(provider=provider, task_scheduling=True, attachments=True) as value:
            old_id, preview = self.summary(
                value,
                ["Movies/One.2001.mkv", "Movies/Two.2002.mkv"],
                "11111111-1111-4111-8111-111111111111",
            )
            items = {item.source_path: item for item in value.repository.list_items(old_id)}
            discovery = value.repository.get_media_discovery_for_task(old_id)
            self.assertIsNotNone(discovery)

            status, _reanalysis = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{discovery.discovery_id}/analyze",
                method="POST",
                body={"expectedVersion": discovery.version},
            )
            self.assertIn(status, (200, 202), _reanalysis)

            with patch.object(
                value.discovery,
                "run_claimed",
                side_effect=DiscoveryUnavailable("the claimed discovery is no longer readable"),
            ):
                self._drive(value, old_id, steps=4)

            task = value.repository.get_task(old_id)
            self.assertEqual(PersistentTaskStatus.FAILED, task.status)
            # The waiting items are frozen evidence of the ended flow, not new
            # failures: their recorded waiting state stays exactly as it was.
            self.assertEqual(
                {
                    "Movies/One.2001.mkv": TaskItemStatus.WAITING_CONFIRM,
                    "Movies/Two.2002.mkv": TaskItemStatus.WAITING_CONFIRM,
                },
                {
                    path: value.repository.get_item(item.item_id).status
                    for path, item in items.items()
                },
            )

            code, body = self.request(value, f"/api/v1/operations/runs/{old_id}")
            self.assertEqual(200, code, body)
            self.assertFalse(body["filesPreparation"]["continuable"])

            # Both waiting files are released to a deliberate new request.
            status, fresh = self._admit(
                value,
                ["Movies/One.2001.mkv", "Movies/Two.2002.mkv"],
                request_id="22222222-2222-4222-8222-222222222222",
            )
            self.assertEqual(202, status, fresh)
            self.assertEqual([], value.target.mutations)

            # The old summary cannot confirm through the real Execute entrance:
            # the flow ended, so a stale page cannot mint a second Task beside
            # the ended one or reopen the work it gave up.
            selected = [item["itemId"] for item in preview["items"]]
            status, refused = self.request(
                value,
                f"/api/v1/operations/organize/previews/{preview['previewId']}/execute",
                method="POST",
                body={
                    "confirmation": True,
                    "itemIds": selected,
                    "expectedIntentVersion": preview["intentVersion"],
                    "allowOverwrite": False,
                    "allowSourceCleanup": False,
                },
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("preparation_flow_ended", refused["error"]["code"])
            self.assertEqual([], value.target.mutations)

            # The ended flow's durable evidence is untouched.
            self.assertEqual(PersistentTaskStatus.FAILED, value.repository.get_task(old_id).status)
            for item in items.values():
                self.assertEqual(
                    TaskItemStatus.WAITING_CONFIRM,
                    value.repository.get_item(item.item_id).status,
                )


class MixedBatchPerFileReleaseTests(_SupersededHandoffFixture):
    """One analysis-failed sibling releases; the waiting siblings keep their summary.

    Production per-item analysis fault: the Provider genuinely fails for one
    selected file only, so the shared plan summary publishes that item as a
    real technical failure while the healthy sibling keeps its exact
    confirmation flow.  The Task flow stays unfinished (waiting for the human)
    and must keep owning the waiting file.
    """

    def test_failed_sibling_releases_and_waiting_siblings_keep_their_summary(self):
        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        provider = _provider(
            MediaCandidate("tmdb", "201", MediaType.MOVIE, "One", year=2001),
            MediaCandidate("tmdb", "202", MediaType.MOVIE, "Two", year=2002),
        )
        original_search = provider.search_movie
        outage = {"active": True}

        def failing_search(query, policy=None, **kwargs):
            if outage["active"] and "One" in str(query):
                raise RuntimeError("provider outage for One")
            return original_search(query, policy=policy, **kwargs)

        provider.search_movie = failing_search
        with self.journey(provider=provider, task_scheduling=True, attachments=True) as value:
            old_id, preview = self.summary(
                value,
                ["Movies/One.2001.mkv", "Movies/Two.2002.mkv"],
                "11111111-1111-4111-8111-111111111111",
            )
            items = {item.source_path: item for item in value.repository.list_items(old_id)}
            # The production per-item publication: One's own analysis fault is
            # a terminal item outcome; Two keeps its exact waiting summary.
            self.assertEqual(TaskItemStatus.FAILED, items["Movies/One.2001.mkv"].status)
            self.assertEqual(TaskItemStatus.WAITING_CONFIRM, items["Movies/Two.2002.mkv"].status)
            self.assertEqual(PersistentTaskStatus.RUNNING, value.repository.get_task(old_id).status)

            code, body = self.request(value, f"/api/v1/operations/runs/{old_id}")
            self.assertEqual(200, code, body)
            # The Task flow is unfinished and still holds a legal continuation,
            # so the Task Center keeps the execution-nature entry for Two.
            self.assertTrue(body["filesPreparation"]["continuable"])

            # One is released to a deliberate new request; Two is still owned
            # by its own waiting summary and cannot start a second work.
            status, fresh = self._admit(
                value,
                ["Movies/One.2001.mkv"],
                request_id="22222222-2222-4222-8222-222222222222",
            )
            self.assertEqual(202, status, fresh)
            status, refused = self._admit(
                value,
                ["Movies/Two.2002.mkv"],
                request_id="33333333-3333-4333-8333-333333333333",
            )
            self.assertEqual(409, status, refused)

            # A stale client that explicitly selects the failed item is
            # refused by name; the healthy sibling stays confirmable.
            one_item = next(
                item for item in preview["items"] if item["source"]["filename"] == "One.2001.mkv"
            )
            two_item = next(
                item for item in preview["items"] if item["source"]["filename"] == "Two.2002.mkv"
            )
            status, refused = self.request(
                value,
                f"/api/v1/operations/organize/previews/{preview['previewId']}/execute",
                method="POST",
                body={
                    "confirmation": True,
                    "itemIds": [one_item["itemId"]],
                    "expectedIntentVersion": preview["intentVersion"],
                    "allowOverwrite": False,
                    "allowSourceCleanup": False,
                },
            )
            self.assertEqual(409, status, refused)
            self.assertEqual([], value.target.mutations)

            # Two's ordinary confirmation adopts its own unfinished Task and
            # executes exactly the reviewed selection.
            self.confirm(value, preview, [two_item["itemId"]])
            for _ in range(8):
                value.task_engine.run_next()
            self.assertEqual(
                PersistentTaskStatus.COMPLETED, value.repository.get_task(old_id).status
            )
            organized = [path.name for path in self.target_root.rglob("*.mkv")]
            self.assertIn("Two (2002).mkv", organized)
            self.assertNotIn("One (2001).mkv", organized)

            # One's deliberate new work runs on its own identity and records
            # its own exact outcome without touching Two's recorded facts.
            # The outage is over, so the fresh analysis plans normally.
            outage["active"] = False
            status, admitted = self._admit(
                value,
                ["Movies/One.2001.mkv"],
                request_id="44444444-4444-4444-8444-444444444444",
            )
            self.assertEqual(202, status, admitted)
            new_id = admitted["organizeTaskId"]
            discovery = self._drive(value, new_id)
            _status, fresh_preview = self.request(
                value, f"/api/v1/operations/organize/previews/{discovery.preview_id}"
            )
            self.assertEqual(200, _status, fresh_preview)
            self.confirm(value, fresh_preview)
            for _ in range(8):
                value.task_engine.run_next()
            organized = [path.name for path in self.target_root.rglob("*.mkv")]
            self.assertIn("One (2001).mkv", organized)
            self.assertEqual(
                PersistentTaskStatus.COMPLETED, value.repository.get_task(new_id).status
            )


class HealthyWaitingSummaryStaysContinuableTests(_SupersededHandoffFixture):
    """A normal unconfirmed summary keeps its entry, its identity and its work.

    Production journey: a healthy Files summary is left unconfirmed — the
    operator closes the page — and later reopens it through the Task Center
    run detail and confirms the same Task.  Closing loses nothing.
    """

    def test_unconfirmed_healthy_summary_stays_continuable_and_confirmable(self):
        self.media("Movies/One.2001.mkv")
        provider = _provider(MediaCandidate("tmdb", "201", MediaType.MOVIE, "One", year=2001))
        with self.journey(provider=provider, task_scheduling=True, attachments=True) as value:
            old_id, preview = self.summary(
                value, ["Movies/One.2001.mkv"], "11111111-1111-4111-8111-111111111111"
            )
            discovery_id = value.repository.get_media_discovery_for_task(old_id).discovery_id

            code, body = self.request(value, f"/api/v1/operations/runs/{old_id}")
            self.assertEqual(200, code, body)
            self.assertEqual(
                {
                    "discoveryId": discovery_id,
                    "resourceLibraryId": "library",
                    "continuable": True,
                },
                body["filesPreparation"],
            )

            # The same summary is reopenable and still the current plan.
            status, reopened = self.request(
                value, f"/api/v1/operations/organize/previews/{preview['previewId']}"
            )
            self.assertEqual(200, status, reopened)
            self.assertTrue(reopened["current"])

            # Confirming later adopts the exact same Task; nothing restarted.
            self.confirm(value, preview)
            for _ in range(8):
                value.task_engine.run_next()
            self.assertEqual(
                PersistentTaskStatus.COMPLETED, value.repository.get_task(old_id).status
            )
            self.assertIn("One (2001).mkv", [path.name for path in self.target_root.rglob("*.mkv")])

            # The completed flow keeps its read-only preparation identity: the
            # work truly ended, so no execution-nature entry remains.
            code, body = self.request(value, f"/api/v1/operations/runs/{old_id}")
            self.assertEqual(200, code, body)
            self.assertFalse(body["filesPreparation"]["continuable"])


if __name__ == "__main__":  # pragma: no cover - direct module execution
    unittest.main()
