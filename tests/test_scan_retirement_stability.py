"""Retirement leaves fresh organization's real observation and exact confirmation intact."""

from __future__ import annotations

import os
from datetime import timedelta

from tests.test_organize_preparation import _PreparationFixture


class ScanRetirementStabilityTests(_PreparationFixture):
    def test_fresh_scopes_wait_without_scan_then_confirm_only_exact_subset(self):
        for paths in (
            ["Movies"],
            ["Movies/One.2001.mkv"],
            ["Movies/One.2001.mkv", "Movies/Two.2002.mkv"],
        ):
            with self.subTest(paths=paths):
                # Use an isolated fixture per case, without any Scanner/FileIndex seed.
                self.media("Movies/One.2001.mkv")
                self.media("Movies/Two.2002.mkv")
                library = self.resource_library(
                    stability={
                        "minimumAgeSeconds": 0,
                        "modifiedThresholdSeconds": 0,
                        "stableSizeDurationSeconds": 60,
                    }
                )
                with self.journey(resource_libraries=[library]) as value:
                    admitted = self.admit(value, paths)
                    first = value.discovery.claim_and_run(worker_id="first", claim_token="first")
                    self.assertEqual("waiting_stability", first.status.value)
                    self.assertEqual((), first.sources)
                    self.assertEqual((), value.repository.list_tasks())
                    self.assertEqual((), value.repository.list_jobs())
                    self.assertEqual([], value.source.mutations)
                    self.assertEqual([], value.target.mutations)
                    self.clock_value += timedelta(seconds=59)
                    self.assertIsNone(
                        value.discovery.claim_and_run(worker_id="early", claim_token="early")
                    )
                    self.clock_value += timedelta(seconds=1)
                    settled = self.run_worker(value)
                    self.assertEqual(
                        admitted["configurationSnapshotId"], settled["configurationSnapshotId"]
                    )
                    self.assertIsNotNone(settled["previewId"])
                    self.assertEqual((), value.repository.list_tasks())
                    preview = value.repository.get_manual_preview(settled["previewId"])
                    chosen = preview.items[0].item_id
                    result = self.execute(value, {"previewId": preview.preview_id}, [chosen])
                    value.execution_worker.run_next()
                    execution = value.repository.get_manual_execution(result["executionId"])
                    self.assertEqual(1, len(execution.items))
                    self.assertEqual(chosen, execution.items[0].item_id)
                    self.assertEqual("completed", execution.status.value)
                # Each subtest has its own database and source trees.
                self.setUp()

    def test_changed_source_resets_interval_without_grant_or_media_mutation(self):
        path = self.media("Movies/One.2001.mkv")
        old = self.clock_value - timedelta(days=30)
        os.utime(path, (old.timestamp(), old.timestamp()))
        library = self.resource_library(
            stability={
                "minimumAgeSeconds": 0,
                "modifiedThresholdSeconds": 0,
                "stableSizeDurationSeconds": 60,
            }
        )
        with self.journey(resource_libraries=[library]) as value:
            self.admit(value, ["Movies"])
            first = value.discovery.claim_and_run(worker_id="first", claim_token="first")
            self.assertEqual("waiting_stability", first.status.value)
            self.clock_value += timedelta(seconds=60)
            path.write_bytes(b"changed-source")
            changed = value.discovery.claim_and_run(worker_id="changed", claim_token="changed")
            self.assertEqual("waiting_stability", changed.status.value)
            self.assertEqual((), changed.sources)
            self.assertIsNone(changed.preview_id)
            self.clock_value += timedelta(seconds=59)
            self.assertIsNone(value.discovery.claim_and_run(worker_id="early", claim_token="early"))
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            self.assertEqual((), value.repository.list_tasks())
            self.clock_value += timedelta(seconds=1)
            settled = self.run_worker(value)
            self.assertIsNotNone(settled["previewId"])
            self.assertEqual((), value.repository.list_tasks())
