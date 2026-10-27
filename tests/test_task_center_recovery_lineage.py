"""Real SQLite/API/Worker regressions for Task45.3 multi-hop recovery."""

from __future__ import annotations

import tempfile
import unittest
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
                # The re-analysis child itself is no longer typed work: its
                # decision completed and no technical failure became a type.
                self.assertFalse(self.state.repository.operations_run(child_task).attention)
                checkpoint = self.detail(seed["taskId"], seed["itemId"])["checkpoint"]
                self.assertNotIn("retry", set(checkpoint["permitted_action_ids"]))
                self.assertEqual(
                    original_results, self.state.repository.list_results(seed["taskId"])
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
        self.assertTrue((self.state.managed.root / "source" / seed["sourcePath"]).exists())

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
