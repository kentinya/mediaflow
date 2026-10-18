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
        return self.call(
            "GET",
            f"/api/v1/operations/runs/{task}/problem-items",
            query="problem=failure&limit=100",
        )

    def test_verified_multi_hop_success_closes_only_exact_current_problem_after_reopen(self):
        seed, child_task, child_item, summary, preview = self.prepared_chain()
        original_results = self.state.repository.list_results(seed["taskId"])
        self.call(
            "POST",
            f"/api/v1/manual-recovery-preparations/{summary['preparation_id']}/confirm",
            {"confirmation": True, "itemIds": [preview.items[0].item_id]},
        )
        self.assertTrue(self.state.repository.operations_run(child_task).attention)
        completed = h.run_manual_worker_once(self.state)
        self.assertTrue(completed["completed"])
        for reopen in (False, True):
            with self.subTest(reopen=reopen):
                if reopen:
                    self.state.restart()
                problems = self.problem_items(seed["taskId"])
                self.assertEqual(1, problems["matching_total"], problems)
                self.assertNotIn(seed["itemId"], {value["item_id"] for value in problems["items"]})
                self.assertFalse(self.state.repository.operations_run(child_task).attention)
                checkpoint = self.detail(seed["taskId"], seed["itemId"])["checkpoint"]
                self.assertNotIn("retry", set(checkpoint["permitted_action_ids"]))
                self.assertEqual(
                    original_results, self.state.repository.list_results(seed["taskId"])
                )

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
        self.assertTrue(self.state.repository.operations_run(child_task).attention)
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
