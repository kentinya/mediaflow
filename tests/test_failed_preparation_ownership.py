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
from mediaflow.domain.manual_execution import ManualExecutionAuthorizationStatus
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

    def test_ended_flow_refuses_reanalysis_and_keeps_the_saved_plan_readable(self):
        """B3-03 backend facts: one eligibility predicate, real history entry.

        After the production failure publication, the same real re-analysis
        entrance is refused from the shared settled-flow fact (before the
        durable record is touched), the run document publishes the ended
        presentation the preparation page renders, and the original summary
        stays reachable through its own two read-only associations — the
        intent's ``latestPlan`` (backend ``get_latest_manual_preview`` read)
        and the Preview detail route.  Read-only: zero Storage effect.
        """

        self.media("Movies/One.2001.mkv")
        provider = _provider(MediaCandidate("tmdb", "201", MediaType.MOVIE, "One", year=2001))
        with self.journey(provider=provider, task_scheduling=True, attachments=True) as value:
            old_id, preview = self.summary(
                value, ["Movies/One.2001.mkv"], "11111111-1111-4111-8111-111111111111"
            )
            discovery = value.repository.get_media_discovery_for_task(old_id)
            self.assertIsNotNone(discovery)

            # Enter the real re-analysis stage, then produce the real failure:
            # the engine's own ``_fail_discovery`` boundary fails the flow.
            status, _body = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{discovery.discovery_id}/analyze",
                method="POST",
                body={"expectedVersion": discovery.version},
            )
            self.assertIn(status, (200, 202), _body)
            with patch.object(
                value.discovery,
                "run_claimed",
                side_effect=DiscoveryUnavailable("the claimed discovery is no longer readable"),
            ):
                self._drive(value, old_id, steps=4)
            # production failure publication
            task = value.repository.get_task(old_id)
            self.assertEqual(PersistentTaskStatus.FAILED, task.status)
            record = value.repository.get_media_discovery(discovery.discovery_id)
            version_before = record.version

            # The same real entrance is now refused by the shared eligibility
            # fact, without touching the durable record.
            status, refused = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{discovery.discovery_id}/analyze",
                method="POST",
                body={"expectedVersion": record.version},
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("organize_flow_ended", refused["error"]["code"])
            self.assertEqual(
                version_before,
                value.repository.get_media_discovery(discovery.discovery_id).version,
            )

            # The run document the preparation page consumes: the ended flow
            # fact, an advertised-but-refused ``prepare`` action with the same
            # predicate's reason, and an ended native next action instead of a
            # promise that a Worker is analysing this record.
            code, document = self.request(
                value, f"/api/v1/operations/organize/discoveries/{discovery.discovery_id}"
            )
            self.assertEqual(200, code, document)
            self.assertEqual(
                {"taskId": old_id, "status": "failed", "continuable": False},
                document["organizeFlow"],
            )
            prepare = document["actions"]["prepare"]
            self.assertFalse(prepare["available"])
            self.assertEqual("organize_flow_ended", prepare["reason"])
            self.assertIn("already ended", document["nextAction"])
            self.assertNotIn("running the complete analysis", document["nextAction"])

            # The original summary is still reachable as read-only history
            # through both existing associations the Web page uses.
            code, intent = self.request(
                value, f"/api/v1/operations/organize/intents/{preview['intentId']}"
            )
            self.assertEqual(200, code, intent)
            self.assertEqual(preview["previewId"], intent["latestPlan"]["previewId"])
            code, reopened = self.request(
                value, f"/api/v1/operations/organize/previews/{preview['previewId']}"
            )
            self.assertEqual(200, code, reopened)
            self.assertTrue(reopened["zeroMutation"])

            # A stale page that still invokes it creates no second work and no
            # media effect; the original waiting item evidence is unchanged.
            self.assertEqual([old_id], [t.task_id for t in value.repository.list_tasks(limit=50)])
            for item in value.repository.list_items(old_id):
                self.assertEqual(
                    TaskItemStatus.WAITING_CONFIRM,
                    value.repository.get_item(item.item_id).status,
                )
            self.assertEqual([], value.target.mutations)


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


class ConfirmationCrossingFlowFailureTests(_SupersededHandoffFixture):
    """B3-02: a confirmation whose flow settles mid-admission admits nothing.

    Both journeys enter through the real HTTP entrances and the exact
    interleaving is production-natural: while the confirmation's own source
    check runs (after the application boundary's healthy pre-read), a
    concurrent re-analysis goes through the existing analyze entrance and the
    resident engine's own ``_fail_discovery`` boundary publishes the Task
    failure — exactly what B's two-window reproduction did without touching
    durable state directly.  The refusal must therefore come from the atomic
    admission transaction itself: no second Task, no admitted execution, no
    consumed authority, zero Storage effect.

    Evidence labels used below:

    * ``production failure publication`` — Task FAILED is only ever written by
      the engine's ``_fail_discovery`` after ``run_claimed`` raised, never by
      test-local state injection.
    * the ``organizeFlow`` assertions pin the exact nested document the Web
      reader consumes (plain ``taskId``/``status``/``continuable`` keys).
    """

    def _publish_flow_failure(self, value, old_id):
        """Re-analysis through the real API, then the engine's own failure."""

        discovery = value.repository.get_media_discovery_for_task(old_id)
        self.assertIsNotNone(discovery)
        status, body = self.request(
            value,
            f"/api/v1/operations/organize/discoveries/{discovery.discovery_id}/analyze",
            method="POST",
            body={"expectedVersion": discovery.version},
        )
        self.assertIn(status, (200, 202), body)
        with patch.object(
            value.discovery,
            "run_claimed",
            side_effect=DiscoveryUnavailable("analysis read failed during old confirmation"),
        ):
            self._drive(value, old_id, steps=4)
        # production failure publication
        self.assertEqual(PersistentTaskStatus.FAILED, value.repository.get_task(old_id).status)

    def _crossing_storage_check(self, value, old_id, *, fire_at):
        """A storage check that lets the production failure land inside it."""

        original = value.executions._validate_current_storage
        calls = {"count": 0}

        def crossing(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == fire_at:
                self._publish_flow_failure(value, old_id)
            return original(*args, **kwargs)

        return crossing

    @staticmethod
    def _selected_ids(preview):
        return [item["itemId"] for item in preview["items"] if item["status"] == "previewed"]

    def _assert_no_second_work(self, value, old_id, preview):
        """The ended flow keeps its evidence; nothing new was admitted."""

        tasks = tuple(value.repository.list_tasks(limit=50))
        self.assertEqual([old_id], [task.task_id for task in tasks])
        self.assertEqual(PersistentTaskStatus.FAILED, value.repository.get_task(old_id).status)
        self.assertEqual(
            [],
            list(value.repository.list_manual_executions_for_preview(preview["previewId"])),
        )
        authorizations = value.repository.list_manual_execution_authorizations_for_preview(
            preview["previewId"]
        )
        self.assertTrue(authorizations)
        for authority in authorizations:
            self.assertIsNot(ManualExecutionAuthorizationStatus.CONSUMED, authority.status)
        self.assertEqual([], value.target.mutations)
        for item in value.repository.list_items(old_id):
            self.assertEqual(TaskItemStatus.WAITING_CONFIRM, item.status)

    def test_confirmation_crossing_the_failure_is_refused_by_the_admission_itself(self):
        self.media("Movies/One.2001.mkv")
        provider = _provider(MediaCandidate("tmdb", "201", MediaType.MOVIE, "One", year=2001))
        with self.journey(provider=provider, task_scheduling=True, attachments=True) as value:
            old_id, preview = self.summary(
                value, ["Movies/One.2001.mkv"], "11111111-1111-4111-8111-111111111111"
            )
            discovery_id = value.repository.get_media_discovery_for_task(old_id).discovery_id

            # The Web's own reader contract: the healthy flow document with the
            # backend's real nested keys.
            code, detail = self.request(
                value, f"/api/v1/operations/organize/discoveries/{discovery_id}"
            )
            self.assertEqual(200, code, detail)
            self.assertEqual(
                {
                    "taskId": old_id,
                    "status": value.repository.get_task(old_id).status.value,
                    "continuable": True,
                },
                detail["organizeFlow"],
            )

            # The web confirmation enters authorize (healthy) and execute.  The
            # failure lands during execute's own source check — strictly after
            # both pre-reads — so only the in-transaction fence can refuse it.
            crossing = self._crossing_storage_check(value, old_id, fire_at=2)
            selected = self._selected_ids(preview)
            with patch.object(value.executions, "_validate_current_storage", side_effect=crossing):
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

            # The ended flow's own document for the Web, with real keys.
            code, detail = self.request(
                value, f"/api/v1/operations/organize/discoveries/{discovery_id}"
            )
            self.assertEqual(200, code, detail)
            self.assertEqual(
                {"taskId": old_id, "status": "failed", "continuable": False},
                detail["organizeFlow"],
            )
            self._assert_no_second_work(value, old_id, preview)

            # The ordinary new Files admission still releases and re-admits the
            # failed file without touching the ended record (AC-1 stays intact).
            status, fresh = self._admit(
                value,
                ["Movies/One.2001.mkv"],
                request_id="22222222-2222-4222-8222-222222222222",
            )
            self.assertEqual(202, status, fresh)
            self.assertNotEqual(old_id, fresh["organizeTaskId"])
            self.assertEqual([], value.target.mutations)

    def test_an_old_authorization_crossing_the_failure_is_never_consumed(self):
        self.media("Movies/One.2001.mkv")
        provider = _provider(MediaCandidate("tmdb", "201", MediaType.MOVIE, "One", year=2001))
        with self.journey(provider=provider, task_scheduling=True, attachments=True) as value:
            old_id, preview = self.summary(
                value, ["Movies/One.2001.mkv"], "11111111-1111-4111-8111-111111111111"
            )
            selected = self._selected_ids(preview)
            # The operator projection carries no version proof, so the exact
            # reviewed item versions are read from the durable Preview itself.
            durable = value.previews.get(preview["previewId"])
            versions = {
                item.item_id: item.item_version
                for item in durable.items
                if item.item_id in set(selected)
            }

            # The exact authority is issued while the flow is still healthy,
            # through the standalone authorization entrance.
            code, authorized = self.request(
                value,
                f"/api/v1/manual-previews/{preview['previewId']}/authorize",
                method="POST",
                body={
                    "expectedVersion": preview["intentVersion"],
                    "expectedItemVersions": versions,
                    "itemIds": selected,
                    "confirmation": True,
                },
            )
            self.assertEqual(201, code, authorized)
            authorization_id = authorized["authorizationId"]

            # The flow settles while this old authority's own consume runs its
            # source check: the admission transaction itself must refuse it.
            crossing = self._crossing_storage_check(value, old_id, fire_at=1)
            with patch.object(value.executions, "_validate_current_storage", side_effect=crossing):
                status, refused = self.request(
                    value,
                    f"/api/v1/manual-execution-authorizations/{authorization_id}/consume",
                    method="POST",
                    body={"confirmation": True},
                )
            self.assertEqual(409, status, refused)
            self.assertEqual("preparation_flow_ended", refused["error"]["code"])

            # With the failure durable, a plain repeat of the same consume is
            # refused by the same bounded fact and still consumes nothing.
            status, refused = self.request(
                value,
                f"/api/v1/manual-execution-authorizations/{authorization_id}/consume",
                method="POST",
                body={"confirmation": True},
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("preparation_flow_ended", refused["error"]["code"])

            authority = value.repository.get_manual_execution_authorization(authorization_id)
            self.assertIsNot(ManualExecutionAuthorizationStatus.CONSUMED, authority.status)
            self._assert_no_second_work(value, old_id, preview)


if __name__ == "__main__":  # pragma: no cover - direct module execution
    unittest.main()
