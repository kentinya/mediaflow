"""Real SQLite/API/Worker regressions for Task45.3 multi-hop recovery."""

from __future__ import annotations

import tempfile
import unittest
from collections import Counter
from pathlib import Path

from scripts import operations_inventory_harness as h


class RecoveryLineageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        database = root / "runtime.sqlite3"
        repository, managed, api = h.build_managed_fixture(database, root / "media")
        self.state = h.AppState(database, repository=repository, api=api, managed=managed)
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(lambda: self.state.repository.close())

    def call(self, method, path, body=None, query=""):
        status, value = h.wsgi_request(
            self.state.api, method, path, body=body, query=query, token=h.HARNESS_ADMIN_TOKEN
        )
        self.assertLess(status, 400, (path, status, value))
        return value

    def detail(self, task, item):
        return self.call("GET", f"/api/v1/tasks/{task}/items/{item}/recovery")

    def continue_item(self, task, item):
        return self.call(
            "POST",
            f"/api/v1/tasks/{task}/items/{item}/recovery/continue",
            {
                "expectedCheckpointVersion": self.detail(task, item)["checkpoint"][
                    "checkpoint_version"
                ]
            },
        )

    def seed_metadata_choices(self, task, item_ids):
        """Publish the legal Metadata decisions the batch fixture's items need.

        ``seed_batch_summary_recovery`` really admits two Manual items and fails
        them before any Storage mutation, so neither item carries business
        review rows yet.  The product ``MetadataReviewService`` records one
        NEED_CONFIRM candidate per item for the provider evidence the fixture
        actually seeded, so the operator's following decision is a legal one
        rather than a fabricated identification.
        """

        from dataclasses import replace

        from mediaflow.application.metadata_review import MetadataReviewService
        from mediaflow.domain.metadata import (
            CandidateMatchResult,
            CandidateMatchStatus,
            CandidateScore,
            MetadataIdentificationResult,
            MetadataIdentificationStatus,
            ScoreComponent,
        )
        from mediaflow.domain.recognition import RecognitionType
        from mediaflow.domain.task_persistence import TaskItemStatus

        service = MetadataReviewService(self.state.repository)
        for item_id in item_ids:
            current = self.state.repository.get_item(item_id)
            processing = replace(current, status=TaskItemStatus.PROCESSING, stage="metadata")
            self.state.repository.upsert_item(processing)
            result = next(
                value
                for value in self.state.repository.list_results(task)
                if value.item_id == item_id
            )
            title = result.title or Path(processing.source_path).name.split(".")[0]
            candidate = h.MediaCandidate(
                "tmdb",
                result.provider_id,
                h.MediaType.MOVIE,
                title,
                year=2012,
                genres=("Animation",),
                countries=("JP",),
            )
            service.create(
                processing,
                MetadataIdentificationResult(
                    MetadataIdentificationStatus.NEED_CONFIRM,
                    RecognitionType("C", "Special"),
                    match=CandidateMatchResult(
                        CandidateMatchStatus.NEED_CONFIRM,
                        candidate,
                        72,
                        (CandidateScore(candidate, 72, (ScoreComponent("title", 72, "title"),)),),
                    ),
                    query=title,
                ),
                "C",
            )

    def prepared_metadata_summary(self, task, item):
        """Decide, analyze and prepare one item's exact non-authorizing summary.

        Every step is the product API/Worker: the saved decision, the queued
        analysis continuation, the real resident handler and the bounded plan
        summary.  No execution authority is minted here.
        """

        self.call(
            "POST",
            f"/api/v1/tasks/{task}/items/{item}/recovery/decision",
            {
                "kind": "metadata",
                "candidateRank": 1,
                "expectedCheckpointVersion": self.detail(task, item)["checkpoint"][
                    "checkpoint_version"
                ],
            },
        )
        self.continue_item(task, item)
        self.assertTrue(h.run_task_item_recovery_worker_once(self.state, item_id=item)["ran"])
        summary = self.call(
            "POST",
            f"/api/v1/tasks/{task}/items/{item}/recovery/prepare-summary",
            {
                "expectedCheckpointVersion": self.detail(task, item)["checkpoint"][
                    "checkpoint_version"
                ]
            },
        )
        return summary, self.state.api._manual_recovery._previews.get(summary["preview_id"])

    def confirm_ready_subset(self, summary, preview):
        return self.call(
            "POST",
            f"/api/v1/manual-recovery-preparations/{summary['preparation_id']}/confirm",
            {"confirmation": True, "itemIds": [preview.items[0].item_id]},
        )

    def seed_skipped_conflict(self, task, item, execution_id):
        """Record the real destination conflict a retry observes for one item.

        The product ``ConfirmationService`` writes the pending conflict; the
        operator's following ``skip`` decision is then applied by the product
        recovery API, so both the ``skipped`` disposition and the preserved
        destination come from the native conflict journey.
        """

        from dataclasses import replace

        from mediaflow.application.conflict_resolution import ConfirmationService
        from mediaflow.domain.organizer import (
            Conflict,
            ConflictType,
            OrganizePlan,
            PlanStatus,
            StorageLocation,
        )
        from mediaflow.domain.task_persistence import TaskItemStatus

        execution = self.state.repository.get_manual_execution(execution_id)
        manual_item = next(value for value in execution.items if value.task_item_id == item)
        target_path = str(manual_item.plan["executionPlan"]["targetPath"])
        destination = self.state.managed.root / "destination" / target_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"existing destination must be preserved")
        policy = next(
            value
            for value in self.state.managed.runtime.strategy.organize_policies
            if value.policy_id == "A"
        )
        current = self.state.repository.get_item(item)
        processing = replace(current, status=TaskItemStatus.PROCESSING, stage="metadata")
        self.state.repository.upsert_item(processing)
        ConfirmationService(self.state.repository).create(
            task_id=task,
            item_id=item,
            plan=OrganizePlan(
                source_storage_id="source-storage",
                target_storage_id="media-target",
                source=current.source_path,
                target=target_path,
                recognition_type_id="C",
                naming_policy_id="A",
                classification_policy_id="A",
                organize_policy_id=policy.policy_id,
                conflicts=(
                    Conflict(
                        ConflictType.DESTINATION_EXISTS,
                        current.source_path,
                        target_path,
                        "destination already exists",
                    ),
                ),
                status=PlanStatus.CONFLICT,
                plan_id=str(manual_item.plan["planId"]),
                source_location=StorageLocation("source-storage", current.source_path),
                destination_location=StorageLocation("media-target", target_path),
            ),
            policy=policy,
            item=replace(
                processing, status=TaskItemStatus.WAITING_CONFIRM, stage="waiting_confirm"
            ),
        )
        return destination

    def run_row(self, task, query="limit=100"):
        """One run row exactly as the center list publishes it."""

        page = self.call("GET", "/api/v1/operations/runs", query=query)
        self.assertEqual(page["total"], len(page["items"]))
        matches = [value for value in page["items"] if value["run_id"] == task]
        self.assertEqual(1, len(matches), page["items"])
        return matches[0], page

    def assert_run_projection(self, task, *, status, recovered_completion):
        """The exact aggregate status/recovered-completion truth of one run.

        The detail, the unfiltered list, its status partition and the ended
        view all publish the same facts, so no surface can claim a completion
        the durable items do not prove.
        """

        run = self.call("GET", f"/api/v1/operations/runs/{task}")
        self.assertEqual(status, run["status"])
        self.assertEqual(recovered_completion, run["recovered_completion"])
        row, page = self.run_row(task)
        self.assertEqual(status, row["status"])
        self.assertEqual(recovered_completion, row["recovered_completion"])
        # The same read snapshot's page rows, counts and status partition agree
        # with the row the detail publishes.
        self.assertEqual(
            dict(Counter(value["status"] for value in page["items"])),
            dict(page["status_counts"]),
        )
        self.assertIn(status, page["status_counts"])
        ended, ended_page = self.run_row(task, query="view=ended&limit=100")
        self.assertEqual(status, ended["status"])
        self.assertEqual(recovered_completion, ended["recovered_completion"])
        self.assertGreaterEqual(ended_page["summary"]["ended"], 1)
        # The status partition never publishes a run the detail denies.
        for partition in ("completed", "failed", "partial_success"):
            rows = self.call(
                "GET", "/api/v1/operations/runs", query=f"status={partition}&limit=100"
            )
            present = task in {value["run_id"] for value in rows["items"]}
            self.assertEqual(partition == status, present, (partition, rows["total"]))
        return run

    def prepared_chain(self):
        seed = h.seed_task_item_recovery_journey(self.state, "technical")
        task, item = seed["taskId"], seed["itemId"]
        self.continue_item(task, item)
        h.run_task_item_recovery_worker_once(self.state, item_id=item)
        linked = self.detail(task, item)["checkpoint"]["recovery_continuation"]
        child_task, child_item = linked["new_task_id"], linked["new_item_id"]
        self.call(
            "POST",
            f"/api/v1/tasks/{child_task}/items/{child_item}/recovery/decision",
            {
                "kind": "metadata",
                "candidateRank": 1,
                "expectedCheckpointVersion": self.detail(child_task, child_item)["checkpoint"][
                    "checkpoint_version"
                ],
            },
        )
        self.continue_item(child_task, child_item)
        h.run_task_item_recovery_worker_once(self.state, item_id=child_item)
        summary = self.call(
            "POST",
            f"/api/v1/tasks/{task}/items/{item}/recovery/prepare-summary",
            {
                "expectedCheckpointVersion": self.detail(task, item)["checkpoint"][
                    "checkpoint_version"
                ]
            },
        )
        preview = self.state.api._manual_recovery._previews.get(summary["preview_id"])
        return seed, child_task, child_item, summary, preview

    def problem_items(self, task):
        """Every currently typed business problem of this Task, all four types.

        Task46.4 RO-4 removed the fifth technical "failure" problem type, so the
        current-problem membership is asserted over the four real types and over
        the Attention union the center publishes.
        """

        problems = {}
        for kind in ("recognition", "metadata", "classification", "conflict"):
            problems[kind] = self.call(
                "GET",
                f"/api/v1/operations/runs/{task}/problem-items",
                query=f"problem={kind}&limit=100",
            )
        return problems

    def typed_items(self, task):
        """The distinct items that currently carry any of the four problems."""

        seen: dict[str, set[str]] = {}
        for kind, page in self.problem_items(task).items():
            seen[kind] = {value["item_id"] for value in page["items"]}
        return seen

    def test_verified_multi_hop_success_closes_only_exact_current_problem_after_reopen(self):
        seed, child_task, child_item, summary, preview = self.prepared_chain()
        original_results = self.state.repository.list_results(seed["taskId"])
        self.call(
            "POST",
            f"/api/v1/manual-recovery-preparations/{summary['preparation_id']}/confirm",
            {"confirmation": True, "itemIds": [preview.items[0].item_id]},
        )
        # The exact confirmed follow-up is queued work in Running, not a
        # pending business problem: the child's saved decision already moved on
        # to its explicit continuation, so the child Task carries no four-type
        # attention of its own any more.
        child = self.state.repository.operations_run(child_task)
        self.assertEqual((), child.problem_types)
        self.assertFalse(child.attention)
        completed = h.run_manual_worker_once(self.state)
        self.assertTrue(completed["completed"])
        for reopen in (False, True):
            with self.subTest(reopen=reopen):
                if reopen:
                    self.state.restart()
                # A completed re-analysis and a consumed same-page follow-up
                # prove the exact affected item's problem really closed; the
                # source spends no obsolete four-type attention, while its
                # original attempt Results stay untouched history.
                typed = self.typed_items(seed["taskId"])
                self.assertNotIn(seed["itemId"], typed["metadata"])
                source = self.state.repository.operations_run(seed["taskId"])
                self.assertFalse(source.attention)
                self.assertEqual((), source.problem_types)
                # The one necessary item really carries its own exact verified
                # effect, so the aggregate (detail, list and status partitions)
                # publishes the recovered completion those facts prove.
                # The same source Task keeps an unknown-effect sibling and a
                # success item with no Result evidence, so its aggregate stays
                # honestly partial_success instead of claiming completion.
                self.assert_run_projection(
                    seed["taskId"], status="partial_success", recovered_completion=False
                )
                # The re-analysis child itself is no longer typed work: its
                # decision completed and no technical failure became a type.
                self.assertFalse(self.state.repository.operations_run(child_task).attention)
                checkpoint = self.detail(seed["taskId"], seed["itemId"])["checkpoint"]
                self.assertNotIn("retry", set(checkpoint["permitted_action_ids"]))
                self.assertEqual(
                    original_results, self.state.repository.list_results(seed["taskId"])
                )

    def test_single_item_recovery_projects_completed_from_its_own_effect(self):
        # The clean single-item half of the same rule: the run's only necessary
        # item really is organized by its exact confirmed follow-up, so every
        # read of the aggregate publishes the completion its own effect proves.
        seed = h.seed_task_item_recovery_journey(self.state, "metadata")
        task, item = seed["taskId"], seed["itemId"]
        original_results = self.state.repository.list_results(task)
        summary, preview = self.prepared_metadata_summary(task, item)
        self.confirm_ready_subset(summary, preview)
        self.assertTrue(h.run_manual_worker_once(self.state)["completed"])
        for reopen in (False, True):
            with self.subTest(reopen=reopen):
                if reopen:
                    self.state.restart()
                run = self.assert_run_projection(
                    task, status="completed", recovered_completion=True
                )
                self.assertEqual((), tuple(run["problem_types"]))
                self.assertFalse(run["attention"])
                self.assertEqual(original_results, self.state.repository.list_results(task))

    def test_ignored_sibling_never_projects_recovered_completion(self):
        # B46.4-02: one necessary item is really organized by its exact
        # confirmed follow-up while its sibling is deliberately ignored.  The
        # ignore is a legal disposition that ends that sibling's problem, but it
        # is not organizing success: the run keeps its real failed outcome and
        # never publishes "已完成（恢复成功）".
        seed = h.seed_batch_summary_recovery(self.state)
        task = seed["taskId"]
        recover, ignored = seed["itemIds"]
        self.seed_metadata_choices(task, seed["itemIds"])
        original_results = self.state.repository.list_results(task)
        self.call(
            "POST",
            f"/api/v1/tasks/{task}/items/{ignored}/recovery",
            {
                "actionId": "ignore",
                "expectedCheckpointVersion": self.detail(task, ignored)["checkpoint"][
                    "checkpoint_version"
                ],
            },
        )
        summary, preview = self.prepared_metadata_summary(task, recover)
        self.confirm_ready_subset(summary, preview)
        self.assertTrue(h.run_manual_worker_once(self.state)["completed"])
        # Nothing is replayed once the confirmed work settled.
        self.assertEqual(
            {"completed": False, "reason": "no admitted manual execution"},
            h.run_manual_worker_once(self.state),
        )
        sources = {
            value.item_id: value.source_path for value in self.state.repository.list_items(task)
        }
        root = self.state.managed.root
        for reopen in (False, True):
            with self.subTest(reopen=reopen):
                if reopen:
                    self.state.restart()
                run = self.assert_run_projection(task, status="failed", recovered_completion=False)
                # The real dispositions stay fully readable instead of being
                # flattened into a completion claim.
                self.assertEqual(1, run["progress"]["dispositions"]["ignored"])
                self.assertEqual(0, run["progress"]["dispositions"]["success"])
                self.assertFalse(run["attention"])
                self.assertEqual((), tuple(run["problem_types"]))
                # The page statistics describe the same population: this run is
                # ended history, not a pending business problem.
                _, page = self.run_row(task)
                self.assertEqual(0, page["attention_count"])
                self.assertEqual(0, page["summary"]["problem_tasks"]["metadata"])
                self.assertEqual(0, page["summary"]["problem_files"]["metadata"])
                # The ignored source is exactly where the operator left it; the
                # recovered sibling really moved into the destination scope.
                self.assertTrue((root / "source" / sources[ignored]).is_file())
                self.assertFalse((root / "source" / sources[recover]).exists())
                moved = [
                    value.name for value in (root / "destination").rglob("*") if value.is_file()
                ]
                self.assertTrue(any("BatchSummaryA" in name for name in moved), moved)
                # The original failed attempt stays untouched history.
                self.assertEqual(original_results, self.state.repository.list_results(task))

    def test_recovered_completion_requires_every_necessary_item(self):
        # B46.4-02: only the whole necessary primary population with exact,
        # per-item verified effects may project "已完成（恢复成功）".  One real
        # recovery leaves the run's honest state, the second real recovery
        # completes it, and losing one item's exact lineage evidence drops the
        # projection back instead of keeping a stale completion.
        seed = h.seed_batch_summary_recovery(self.state)
        task = seed["taskId"]
        first, second = seed["itemIds"]
        self.seed_metadata_choices(task, seed["itemIds"])
        original_results = self.state.repository.list_results(task)
        summary, preview = self.prepared_metadata_summary(task, first)
        self.confirm_ready_subset(summary, preview)
        self.assertTrue(h.run_manual_worker_once(self.state)["completed"])
        run = self.assert_run_projection(task, status="failed", recovered_completion=False)
        # Half of the necessary population is still a real Metadata decision, so
        # a partial recovery neither completes nor resets the current problem.
        self.assertEqual(("metadata",), tuple(run["problem_types"]))
        self.assertTrue(run["attention"])
        _, page = self.run_row(task)
        self.assertEqual(1, page["attention_count"])
        self.assertEqual(1, page["summary"]["problem_tasks"]["metadata"])
        self.assertEqual(1, page["summary"]["problem_files"]["metadata"])
        summary, preview = self.prepared_metadata_summary(task, second)
        self.confirm_ready_subset(summary, preview)
        self.assertTrue(h.run_manual_worker_once(self.state)["completed"])
        for reopen in (False, True):
            with self.subTest(reopen=reopen):
                if reopen:
                    self.state.restart()
                run = self.assert_run_projection(
                    task, status="completed", recovered_completion=True
                )
                self.assertFalse(run["attention"])
                self.assertEqual((), tuple(run["problem_types"]))
                self.assertEqual(0, run["progress"]["dispositions"]["ignored"])
                self.assertEqual(original_results, self.state.repository.list_results(task))
        # A verified success that no longer matches the exact persisted source
        # identity is not proof: the aggregate falls back to the run's real
        # outcome instead of keeping a stale completion.
        original = self.state.repository.get_item(second)
        self.assertTrue(self.state.repository.has_verified_recovery_follow_up(second))
        for detached in (True, False):
            with self.subTest(detached=detached):
                with self.state.repository._connection:
                    self.state.repository._connection.execute(
                        "UPDATE task_items SET source_path=? WHERE item_id=?",
                        ("unrelated.mkv" if detached else original.source_path, second),
                    )
                self.assertEqual(
                    not detached,
                    self.state.repository.has_verified_recovery_follow_up(second),
                )
                self.assert_run_projection(
                    task,
                    status="failed" if detached else "completed",
                    recovered_completion=not detached,
                )

    def test_standalone_analysis_continuation_chain_never_enters_the_center(self):
        # B46.4-05: the real CLI ``organize <file>`` DryRun plus the preserved
        # administrative analysis continuation writes the same
        # ``recovery-continuation`` Job command as a four-type recovery.  The
        # Job must prove its admitted organizing source through its persisted
        # relation, not through the command name.  This drives the actual
        # CLI → API continue → queued Job → Worker → child Task chain and every
        # center read before/after the claim and across a database reopen.
        import io
        from unittest.mock import patch

        from mediaflow.domain.metadata import MetadataError, MetadataErrorCode

        output, errors = io.StringIO(), io.StringIO()
        source = self.state.managed.root / "source" / h.PIPELINE_SOURCE_FILE
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"synthetic dryrun source")
        provider = self.state.managed.metadata_registry.resolve("tmdb")
        with (
            patch(
                "mediaflow.final_cli.metadata_provider_registry_from_environment",
                return_value=self.state.managed.metadata_registry,
            ),
            patch.object(
                provider,
                "search_movie",
                side_effect=MetadataError(
                    MetadataErrorCode.CONNECTION_FAILED, "synthetic provider outage"
                ),
            ),
        ):
            code = h.final_main(
                ["organize", str(source)],
                stdout=output,
                stderr=errors,
                _resolved_configuration=self.state.managed.runtime,
            )
        self.assertEqual(1, code)
        task = self.state.repository.list_tasks(limit=10)[0]
        item = self.state.repository.list_items(task.task_id)[0]
        self.assertFalse(task.execute_authorized)
        self.assert_center_excludes(task.task_id, item.item_id)

        continuation = self.continue_item(task.task_id, item.item_id)
        self.assertEqual("queued", continuation["status"])
        job_id = continuation["job_id"]
        self.assert_center_excludes(task.task_id, job_id)

        worker = h.run_task_item_recovery_worker_once(self.state, item_id=item.item_id)
        self.assertTrue(worker["ran"])
        child_task_id = worker["newTaskId"]
        self.assertTrue(child_task_id)
        self.assert_center_excludes(task.task_id, job_id, child_task_id)

        self.state.restart()
        self.assert_center_excludes(task.task_id, job_id, child_task_id)
        # Nothing was deleted: the analysis Task/Result/Job and its
        # continuation remain reachable through the preserved management
        # API/CLI history, only outside the center population.
        self.assertIsNotNone(self.state.repository.get_task(task.task_id))
        self.assertIsNotNone(self.state.repository.get_job(job_id))
        self.assertIsNotNone(self.state.repository.get_task(child_task_id))

    def test_admitted_recovery_continuation_job_joins_before_and_after_claim(self):
        # The positive half of B46.4-05: a recovery continuation of an admitted
        # organizing Task stays center work while its Job is queued (before a
        # Task exists) and after the Worker binds the child Task.  The persisted
        # relation's source Task is the membership proof.
        seed = h.seed_task_item_recovery_journey(self.state, "recognition")
        task_id, item_id = seed["taskId"], seed["itemId"]
        self.call(
            "POST",
            f"/api/v1/tasks/{task_id}/items/{item_id}/recovery/decision",
            {
                "kind": "recognition",
                "recognitionTypeId": "C",
                "expectedCheckpointVersion": self.detail(task_id, item_id)["checkpoint"][
                    "checkpoint_version"
                ],
            },
        )
        continuation = self.continue_item(task_id, item_id)
        job_id = continuation["job_id"]

        page = self.call("GET", "/api/v1/operations/runs", query="limit=100")
        self.assertEqual(2, page["total"])
        ids = {row["run_id"] for row in page["items"]}
        self.assertEqual({task_id, job_id}, ids)
        job_row = next(row for row in page["items"] if row["run_id"] == job_id)
        self.assertEqual("recovery-continuation", job_row["command"])
        self.assertIsNone(job_row["task_id"])
        self.call("GET", f"/api/v1/operations/runs/{job_id}")
        self.assertEqual(job_id, self.state.repository.resolve_operations_run_link(job_id))

        first = self.call("GET", "/api/v1/operations/runs", query="limit=1")
        collected = {row["run_id"] for row in first["items"]}
        cursor = first["next_cursor"]
        while cursor:
            following = self.call(
                "GET", "/api/v1/operations/runs", query=f"limit=1&cursor={cursor}"
            )
            collected.update(row["run_id"] for row in following["items"])
            cursor = following["next_cursor"]
        self.assertEqual({task_id, job_id}, collected)

        worker = h.run_task_item_recovery_worker_once(self.state, item_id=item_id)
        self.assertTrue(worker["ran"])
        child_task_id = worker["newTaskId"]
        for reopen in (False, True):
            with self.subTest(reopen=reopen):
                if reopen:
                    self.state.restart()
                page = self.call("GET", "/api/v1/operations/runs", query="limit=100")
                self.assertEqual(2, page["total"])
                job_row = next(row for row in page["items"] if row["run_id"] == job_id)
                self.assertEqual(child_task_id, job_row["task_id"])
                self.assertEqual(
                    job_id,
                    self.state.repository.resolve_operations_run_link(child_task_id),
                )

    def assert_center_excludes(self, *identifiers: str) -> None:
        """Every center read excludes the supplied identities/source chain."""

        page = self.call("GET", "/api/v1/operations/runs", query="limit=100")
        self.assertEqual(0, page["total"])
        self.assertEqual([], page["items"])
        self.assertEqual(0, page["summary"]["total"])
        self.assertEqual([], page["summary"]["sources"])
        self.assertIsNone(page["previous_cursor"])
        self.assertIsNone(page["next_cursor"])
        for identifier in identifiers:
            with self.subTest(identifier=identifier):
                code, body = h.wsgi_request(
                    self.state.api,
                    "GET",
                    f"/api/v1/operations/runs/{identifier}",
                    token=h.HARNESS_ADMIN_TOKEN,
                )
                self.assertEqual(404, code, body)
                code, _body = h.wsgi_request(
                    self.state.api,
                    "GET",
                    f"/api/v1/operations/runs/{identifier}/export",
                    token=h.HARNESS_ADMIN_TOKEN,
                )
                self.assertEqual(404, code)
                self.assertIsNone(self.state.repository.resolve_operations_run_link(identifier))

    def test_admin_batch_child_publishes_technical_history_kind(self):
        # B46.4-03: the preserved administrative batch still accepts an exact
        # technical item, but its batch document publishes the same
        # ``technical_history`` decision the center uses.  A reopened batch can
        # therefore keep the child's durable row and evidence read-only without
        # re-offering a four-type summary/confirmation action.
        seed = h.seed_task_item_recovery_journey(self.state, "technical")
        task_id, item_id = seed["taskId"], seed["itemId"]
        checkpoint = self.detail(task_id, item_id)["checkpoint"]
        status, batch = h.wsgi_request(
            self.state.api,
            "POST",
            f"/api/v1/tasks/{task_id}/recovery/continue-batch",
            body={
                "items": [
                    {
                        "itemId": item_id,
                        "expectedCheckpointVersion": checkpoint["checkpoint_version"],
                    }
                ]
            },
            token=h.HARNESS_ADMIN_TOKEN,
        )
        self.assertEqual(202, status, batch)
        self.assertEqual("queued", batch["items"][0]["status"])
        self.assertEqual("technical_history", batch["items"][0]["recoveryKind"])
        for reopen in (False, True):
            with self.subTest(reopen=reopen):
                if reopen:
                    self.state.restart()
                code, stored = request_batch = h.wsgi_request(
                    self.state.api,
                    "GET",
                    f"/api/v1/tasks/{task_id}/recovery-batches/{batch['batch_id']}",
                    token=h.HARNESS_ADMIN_TOKEN,
                )
                self.assertEqual(200, code, request_batch)
                self.assertEqual("technical_history", stored["items"][0]["recoveryKind"])
                self.assertEqual("queued", stored["items"][0]["status"])

    def test_repeated_failure_is_not_resolution(self):
        seed, child_task, _, summary, preview = self.prepared_chain()
        self.call(
            "POST",
            f"/api/v1/manual-recovery-preparations/{summary['preparation_id']}/confirm",
            {"confirmation": True, "itemIds": [preview.items[0].item_id]},
        )
        execution = self.state.api._manual_execution
        actual = execution._executor
        execution._executor = h._PreMutationFailureExecutor()
        try:
            completed = h.run_manual_worker_once(self.state)
        finally:
            execution._executor = actual
        self.assertFalse(completed["completed"])
        # A purely technical follow-up failure is not a fifth problem type and
        # does not keep obsolete four-type work alive; it stays true read-only
        # history on the exact failed execution/Result while the source is
        # untouched and is never replayed.
        child = self.state.repository.operations_run(child_task)
        self.assertFalse(child.attention)
        self.assertEqual((), child.problem_types)
        self.assertIn(child.status.value, {"failed", "partial_success"})
        # A technical follow-up failure is no success proof: the source run keeps
        # its real aggregate state and never claims a recovered completion.
        self.assert_run_projection(
            seed["taskId"], status="partial_success", recovered_completion=False
        )
        self.assertTrue((self.state.managed.root / "source" / seed["sourcePath"]).exists())

    def test_skipped_item_never_projects_recovered_completion(self):
        # B46.4-02: ``skip`` is a legal conflict decision that ends that item's
        # problem without organizing the file.  A sibling recovered by its own
        # exact effect therefore does not make the run complete: the skipped file
        # is still at its source, its destination is untouched, and the aggregate
        # keeps its real failed outcome.
        seed = h.seed_batch_summary_recovery(self.state)
        task = seed["taskId"]
        recover, skipped = seed["itemIds"]
        self.seed_metadata_choices(task, [recover])
        destination = self.seed_skipped_conflict(task, skipped, seed["executionId"])
        self.call(
            "POST",
            f"/api/v1/tasks/{task}/items/{skipped}/recovery/decision",
            {
                "kind": "conflict",
                "strategy": "skip",
                "expectedCheckpointVersion": self.detail(task, skipped)["checkpoint"][
                    "checkpoint_version"
                ],
            },
        )
        self.assertEqual("skipped", self.state.repository.get_item(skipped).status.value)
        summary, preview = self.prepared_metadata_summary(task, recover)
        self.confirm_ready_subset(summary, preview)
        self.assertTrue(h.run_manual_worker_once(self.state)["completed"])
        for reopen in (False, True):
            with self.subTest(reopen=reopen):
                if reopen:
                    self.state.restart()
                run = self.assert_run_projection(task, status="failed", recovered_completion=False)
                self.assertFalse(run["attention"])
                self.assertEqual((), tuple(run["problem_types"]))
                self.assertEqual(1, run["progress"]["dispositions"]["skipped"])
                self.assertEqual(0, run["progress"]["dispositions"]["success"])
                # One necessary item carries exact verified success and the other
                # only carries a legal skip, so the aggregate has both facts to
                # weigh instead of silently dropping the unproven item.
                self.assertTrue(self.state.repository.has_verified_recovery_follow_up(recover))
                self.assertFalse(self.state.repository.has_verified_recovery_follow_up(skipped))
                # The skip never mutated either side of the conflict.
                self.assertEqual(
                    b"existing destination must be preserved", destination.read_bytes()
                )
                self.assertTrue(
                    (
                        self.state.managed.root
                        / "source"
                        / self.state.repository.get_item(skipped).source_path
                    ).is_file()
                )

    def test_verified_effect_does_not_resolve_different_source_or_pin(self):
        seed, child_task, child_item, summary, preview = self.prepared_chain()
        self.call(
            "POST",
            f"/api/v1/manual-recovery-preparations/{summary['preparation_id']}/confirm",
            {"confirmation": True, "itemIds": [preview.items[0].item_id]},
        )
        self.assertTrue(h.run_manual_worker_once(self.state)["completed"])
        from dataclasses import replace

        original = self.state.repository.get_item(child_item)
        task = self.state.repository.get_task(child_task)
        self.assertTrue(self.state.repository.has_verified_recovery_follow_up(child_item))
        with self.state.repository._connection:
            self.state.repository._connection.execute(
                "UPDATE task_items SET source_path=? WHERE item_id=?", ("unrelated.mkv", child_item)
            )
        self.assertFalse(self.state.repository.has_verified_recovery_follow_up(child_item))
        with self.state.repository._connection:
            self.state.repository._connection.execute(
                "UPDATE task_items SET source_path=? WHERE item_id=?",
                (original.source_path, child_item),
            )
        self.state.repository.update_task(
            replace(task, configuration_snapshot_digest="different-pin")
        )
        self.assertFalse(self.state.repository.has_verified_recovery_follow_up(child_item))

    def test_batch_seed_survives_unrelated_provider_candidates(self):
        for kind in (
            "recognition",
            "metadata",
            "metadata_correction",
            "classification",
            "conflict",
            "technical",
        ):
            h.seed_task_item_recovery_journey(self.state, kind)
        h.seed_task_item_recovery_batch(self.state)
        seeded = h.seed_batch_summary_recovery(self.state)
        self.assertEqual(2, len(seeded["itemIds"]))

    def test_overwrite_requires_policy_and_separate_exact_effect_consent(self):
        denied = h.seed_task_item_recovery_journey(self.state, "conflict")
        detail = self.detail(denied["taskId"], denied["itemId"])
        status, _ = h.wsgi_request(
            self.state.api,
            "POST",
            f"/api/v1/tasks/{denied['taskId']}/items/{denied['itemId']}/recovery/decision",
            body={
                "kind": "conflict",
                "strategy": "overwrite",
                "confirmOverwrite": True,
                "expectedCheckpointVersion": detail["checkpoint"]["checkpoint_version"],
            },
            token=h.HARNESS_ADMIN_TOKEN,
        )
        self.assertEqual(409, status)
        seed = h.seed_task_item_recovery_journey(self.state, "conflict_overwrite")
        task, item = seed["taskId"], seed["itemId"]
        self.call(
            "POST",
            f"/api/v1/tasks/{task}/items/{item}/recovery/decision",
            {
                "kind": "conflict",
                "strategy": "overwrite",
                "confirmOverwrite": True,
                "expectedCheckpointVersion": self.detail(task, item)["checkpoint"][
                    "checkpoint_version"
                ],
            },
        )
        self.continue_item(task, item)
        h.run_task_item_recovery_worker_once(self.state, item_id=item)
        summary = self.call(
            "POST",
            f"/api/v1/tasks/{task}/items/{item}/recovery/prepare-summary",
            {
                "expectedCheckpointVersion": self.detail(task, item)["checkpoint"][
                    "checkpoint_version"
                ]
            },
        )
        preview = self.state.api._manual_recovery._previews.get(summary["preview_id"])
        target = self.state.managed.root / "destination" / seed["targetPath"]
        self.assertEqual(b"existing destination must be preserved", target.read_bytes())
        body = {"confirmation": True, "itemIds": [preview.items[0].item_id]}
        path = f"/api/v1/manual-recovery-preparations/{summary['preparation_id']}/confirm"
        status, _ = h.wsgi_request(
            self.state.api, "POST", path, body=body, token=h.HARNESS_ADMIN_TOKEN
        )
        self.assertEqual(409, status)
        self.assertEqual(b"existing destination must be preserved", target.read_bytes())
        self.call("POST", path, {**body, "allowOverwrite": True})
        self.assertEqual(b"existing destination must be preserved", target.read_bytes())
        self.assertTrue(h.run_manual_worker_once(self.state)["completed"])
        self.assertEqual(b"synthetic recovery media; no real codec parsing", target.read_bytes())
