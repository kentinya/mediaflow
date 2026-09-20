"""Focused evidence for the bounded Files Upload journey.

Covers executor-only streaming writes, per-item independence, explicit
conflict truth (no-overwrite / skip / backend-named keep-both), limit
enforcement before and during streaming, safe pause/cancel item boundaries,
fault-injected partial/uncertain writes that are never auto-replayed,
capability denial and secret-free bounded evidence.  Every endpoint is a
temporary local root or an in-process fake; no production service is used.
"""

from __future__ import annotations

import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from mediaflow.application.direct_file_transfers import DirectFileTransferService
from mediaflow.application.direct_file_uploads import (
    DirectFileUploadService,
)
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.domain.configuration_management import (
    ConfigurationDestinationPrecheckStatus,
    ConfigurationStorageCheckStatus,
    ConfigurationStrategyTestStatus,
)
from mediaflow.domain.direct_files import (
    MAX_UPLOAD_ITEMS,
)
from mediaflow.infrastructure.local_storage import LocalStorage
from tests.test_direct_file_transfers import TransferTestCase, _CountingExecutor, request


class UploadTestCase(TransferTestCase):
    """The bounded Upload fixture: one writable source ResourceLibrary."""

    def _document(self, root: Path) -> dict[str, object]:
        document = super()._document(root)
        # A single writable source library; uploads target its current
        # directory.  The destination library is unused for uploads.
        return document

    def _uploads(
        self, api, active, *, executor=None
    ) -> tuple[DirectFileUploadService, DirectFileTransferService]:
        binding = api._prepare_runtime_binding_for_revision(active)
        self.assertIsNotNone(binding.direct_uploads)
        uploads = DirectFileUploadService(
            direct_files=binding.direct_files,
            executor=executor or OrganizerExecutor(),
        )
        transfers = DirectFileTransferService(
            direct_files=binding.direct_files,
            executor=executor or OrganizerExecutor(),
        )
        return uploads, transfers

    def _stream(self, items: list[tuple[str, bytes]]) -> io.BytesIO:
        """One declared-length body: manifest framing plus item payloads."""

        manifest = {
            "destinationDirectory": "",
            "conflict": "no_overwrite",
            "items": [
                {"relativePath": relative, "size": len(payload)} for relative, payload in items
            ],
        }
        encoded = json.dumps(manifest).encode("utf-8")
        body = io.BytesIO()
        body.write(len(encoded).to_bytes(4, "big"))
        body.write(encoded)
        for _relative, payload in items:
            body.write(payload)
        return body

    @staticmethod
    def _manifest(destination_directory: str, conflict: str, items) -> dict:
        return {
            "destinationDirectory": destination_directory,
            "conflict": conflict,
            "items": [
                {"relativePath": relative, "size": len(payload)} for relative, payload in items
            ],
        }

    @staticmethod
    def _payloads(items) -> io.BytesIO:
        body = io.BytesIO()
        for _relative, payload in items:
            body.write(payload)
        body.seek(0)
        return body

    def _upload(
        self,
        uploads,
        root: Path,
        *,
        items,
        destination_directory: str = "",
        conflict: str = "no_overwrite",
        stream_override: io.BytesIO | None = None,
    ) -> dict[str, object]:
        """Admit one Upload and stream every item's payload, then finish.

        The production journey is request-per-item: the admission returns the
        durable Task identity, each item's exact payload streams in manifest
        order, and the finish call finalizes the durable Task.  The helper
        drives all three halves exactly like the interface layer does.
        """

        manifest = self._manifest(destination_directory, conflict, items)
        admitted = uploads.upload(resource_library_id="source", manifest=manifest)
        self.assertEqual(admitted["status"], "RUNNING")
        self.assertTrue(admitted["taskId"])
        task_id = admitted["taskId"]
        for index, (_relative, payload) in enumerate(items):
            stream = stream_override if stream_override is not None else io.BytesIO(payload)
            uploads.execute_item(task_id, index, stream)
        return uploads.finish_upload(task_id)


class UploadSuccessTests(UploadTestCase):
    def test_single_file_upload_writes_only_through_the_executor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True)
            executor = _CountingExecutor()
            uploads, _transfers = self._uploads(api, active, executor=executor)
            document = self._upload(
                uploads,
                root,
                items=[("Movies/new.mkv", b"media-bytes")],
                destination_directory="",
            )
            self.assertEqual(document["status"], "SUCCESS")
            item = document["items"][0]
            self.assertEqual(item["status"], "SUCCESS")
            self.assertEqual(item["path"], "Movies/new.mkv")
            self.assertTrue((root / "source" / "Movies" / "new.mkv").read_bytes() == b"media-bytes")
            # The write crossed the executor boundary, not the application.
            self.assertIn("WRITE_STREAM", executor.boundaries)

    def test_directory_tree_upload_creates_parents_and_streams_each_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True)
            uploads, _transfers = self._uploads(api, active)
            items = [
                ("Movies/season1/one.mkv", b"one"),
                ("Movies/season1/two.mkv", b"two"),
                ("Movies/season2/three.mkv", b"three"),
            ]
            document = self._upload(uploads, root, items=items)
            self.assertEqual(document["status"], "SUCCESS")
            self.assertEqual(document["succeededItems"], 3)
            self.assertTrue((root / "source" / "Movies" / "season1" / "one.mkv").exists())
            self.assertTrue((root / "source" / "Movies" / "season1" / "two.mkv").exists())
            self.assertTrue((root / "source" / "Movies" / "season2" / "three.mkv").exists())

    def test_upload_records_a_bounded_checksum_on_success(self) -> None:
        import hashlib

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True)
            uploads, _transfers = self._uploads(api, active)
            payload = b"checksummed"
            document = self._upload(uploads, root, items=[("Movies/c.mkv", payload)])
            item = document["items"][0]
            self.assertEqual(item["status"], "SUCCESS")
            self.assertEqual(item["checksum"], "sha256:" + hashlib.sha256(payload).hexdigest())


class UploadConflictTests(UploadTestCase):
    def _seed_existing(self, root: Path, path: str = "Movies/existing.mkv") -> None:
        target = root / "source" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"original")

    def test_default_no_overwrite_fails_the_item_only_and_leaves_the_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            self._seed_existing(root)
            uploads, _transfers = self._uploads(api, active)
            document = self._upload(
                uploads,
                root,
                items=[("Movies/existing.mkv", b"replacement")],
                conflict="no_overwrite",
            )
            self.assertEqual(document["status"], "FAILED")
            item = document["items"][0]
            self.assertEqual(item["status"], "FAILED")
            self.assertEqual(item["errorCategory"], "target_exists")
            # The original is never replaced.
            self.assertEqual(
                (root / "source" / "Movies" / "existing.mkv").read_bytes(), b"original"
            )

    def test_skip_conflict_records_a_skipped_item_and_touches_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            self._seed_existing(root)
            uploads, _transfers = self._uploads(api, active)
            document = self._upload(
                uploads,
                root,
                items=[("Movies/existing.mkv", b"skip-me")],
                conflict="skip",
            )
            item = document["items"][0]
            self.assertEqual(item["status"], "SKIPPED")
            self.assertEqual(item["errorCategory"], "skipped_existing")
            self.assertEqual(
                (root / "source" / "Movies" / "existing.mkv").read_bytes(), b"original"
            )

    def test_keep_both_publishes_a_backend_determined_unique_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            self._seed_existing(root)
            uploads, _transfers = self._uploads(api, active)
            document = self._upload(
                uploads,
                root,
                items=[("Movies/existing.mkv", b"both")],
                conflict="keep_both",
            )
            item = document["items"][0]
            self.assertEqual(item["status"], "SUCCESS")
            self.assertIn("(", item["destination"])
            # Both the original and the backend-named copy survive.
            self.assertEqual(
                (root / "source" / "Movies" / "existing.mkv").read_bytes(),
                b"original",
            )
            self.assertTrue(
                any(
                    path.name.endswith(".mkv") and " (" in path.name
                    for path in (root / "source" / "Movies").iterdir()
                )
            )

    def test_keep_both_suffix_collision_generates_a_genuinely_absent_name(self) -> None:
        """B's repeated-suffix reproduction for files and directory nodes."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            (root / "source" / "Movies" / "existing.mkv").write_bytes(b"original")
            (root / "source" / "Movies" / "existing (1).mkv").write_bytes(b"taken")
            uploads, _transfers = self._uploads(api, active)
            document = self._upload(
                uploads,
                root,
                items=[("Movies/existing.mkv", b"both")],
                conflict="keep_both",
            )
            item = document["items"][0]
            self.assertEqual(item["status"], "SUCCESS", document)
            # The generated destination is the genuinely absent (2), never
            # the occupied (1).
            self.assertEqual(item["destination"], "Movies/existing (2).mkv")
            self.assertEqual(
                (root / "source" / "Movies" / "existing (2).mkv").read_bytes(), b"both"
            )
            self.assertEqual(
                (root / "source" / "Movies" / "existing (1).mkv").read_bytes(), b"taken"
            )
            self.assertEqual(
                (root / "source" / "Movies" / "existing.mkv").read_bytes(), b"original"
            )

    def test_keep_both_directory_suffix_collision_is_honest_for_directory_nodes(self) -> None:
        """A file occupying the directory node slot, with (1) also occupied."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source").mkdir(parents=True, exist_ok=True)
            # "Show" exists as a *file*, occupying the directory node slot; the
            # first generated directory name "Show (1)" is occupied by a file
            # too, so the genuinely absent "Show (2)" must be used.
            (root / "source" / "Show").write_bytes(b"a file occupies the dir slot")
            (root / "source" / "Show (1)").write_bytes(b"taken")
            uploads, _transfers = self._uploads(api, active)
            document = self._upload(
                uploads,
                root,
                items=[("Show/note.txt", b"both")],
                conflict="keep_both",
            )
            item = document["items"][0]
            self.assertEqual(item["status"], "SUCCESS", document)
            # The renamed node is the absent (2) directory; the occupied (1)
            # is never rewritten and the occupying file is never replaced.
            self.assertEqual(item["destination"], "Show (2)/note.txt")
            self.assertEqual((root / "source" / "Show (2)" / "note.txt").read_bytes(), b"both")
            self.assertEqual((root / "source" / "Show (1)").read_bytes(), b"taken")
            self.assertEqual(
                (root / "source" / "Show").read_bytes(), b"a file occupies the dir slot"
            )

    def test_existing_directory_is_merged_into_not_renamed(self) -> None:
        """Directory-merge stays the separate keep-both boundary."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source").mkdir(parents=True, exist_ok=True)
            (root / "source" / "Show").mkdir()
            uploads, _transfers = self._uploads(api, active)
            document = self._upload(
                uploads,
                root,
                items=[("Show/note.txt", b"both")],
                conflict="keep_both",
            )
            item = document["items"][0]
            self.assertEqual(item["status"], "SUCCESS", document)
            # The existing directory is merged into; nothing is renamed.
            self.assertEqual(item["destination"], "Show/note.txt")
            self.assertEqual((root / "source" / "Show" / "note.txt").read_bytes(), b"both")

    def test_one_failed_item_never_blocks_its_siblings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            self._seed_existing(root)
            (root / "source" / "Movies" / "free.mkv").write_bytes(b"free")
            uploads, _transfers = self._uploads(api, active)
            items = [
                ("Movies/existing.mkv", b"blocked"),
                ("Movies/ok.mkv", b"ok"),
            ]
            document = self._upload(uploads, root, items=items, conflict="no_overwrite")
            by_path = {item["path"]: item for item in document["items"]}
            self.assertEqual(by_path["Movies/existing.mkv"]["status"], "FAILED")
            self.assertEqual(by_path["Movies/ok.mkv"]["status"], "SUCCESS")
            self.assertTrue((root / "source" / "Movies" / "ok.mkv").exists())


class UploadPathValidationTests(UploadTestCase):
    def _run(self, root: Path, uploads, relative: str, destination_directory: str = ""):
        return self._upload(
            uploads,
            root,
            items=[(relative, b"x")],
            destination_directory=destination_directory,
        )

    def test_absolute_and_traversal_paths_fail_closed_before_any_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True)
            uploads, _transfers = self._uploads(api, active)
            for unsafe in ("/etc/passwd", "../../etc/passwd", "a/../../b.txt", ""):
                with self.assertRaises(Exception) as caught:
                    self._run(uploads, root, unsafe) if unsafe else uploads.upload(
                        resource_library_id="source",
                        manifest=self._manifest("", "no_overwrite", []),
                        stream=self._payloads([]),
                    )
                self.assertTrue(caught.exception is not None)

    def test_root_overwrite_and_reserved_names_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            uploads, _transfers = self._uploads(api, active)
            # The ResourceLibrary root itself is not a writable destination.
            for unsafe in ("CON.txt", "aux.tmp", "com1.log"):
                with self.assertRaises(Exception):
                    self._run(uploads, root, unsafe)

    def test_separator_in_basename_and_dot_segments_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            uploads, _transfers = self._uploads(api, active)
            for unsafe in ("a/b/../../c.txt", "a/./b.txt"):
                with self.assertRaises(Exception):
                    self._run(uploads, root, unsafe)


class UploadLimitTests(UploadTestCase):
    def test_over_limit_request_is_refused_before_the_first_byte_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True)
            uploads, _transfers = self._uploads(api, active)
            items = [(f"Movies/{index:04d}.mkv", b"z" * 4) for index in range(MAX_UPLOAD_ITEMS + 1)]
            with self.assertRaises(Exception) as caught:
                self._upload(uploads, root, items=items)
            self.assertIn("count_limit", str(caught.exception.code))
            # Zero files were written.
            self.assertEqual(list((root / "source" / "Movies").glob("*.mkv")), [])

    def test_exceeding_depth_is_refused_before_any_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True)
            uploads, _transfers = self._uploads(api, active)
            from mediaflow.domain.direct_files import MAX_UPLOAD_DEPTH

            deep = "/".join(f"d{i}" for i in range(MAX_UPLOAD_DEPTH + 1)) + "/leaf.mkv"
            with self.assertRaises(Exception) as caught:
                self._upload(uploads, root, items=[(deep, b"x")])
            self.assertIn("depth_limit", str(caught.exception.code))

    def test_truncated_stream_marks_remaining_items_without_fabricating(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True)
            uploads, _transfers = self._uploads(api, active)
            items = [
                ("Movies/a.mkv", b"aaaa"),
                ("Movies/b.mkv", b"bbbb"),
            ]
            manifest = self._manifest("", "no_overwrite", items)
            admitted = uploads.upload(resource_library_id="source", manifest=manifest)
            task_id = admitted["taskId"]
            # The first item's body delivers its declared bytes.
            uploads.execute_item(task_id, 0, io.BytesIO(b"aaaa"))
            # The second item's body ends before its declared size: the
            # executor records a truthful truncation, never a complete file.
            uploads.execute_item(task_id, 1, io.BytesIO(b""))
            document = uploads.finish_upload(task_id)
            by_path = {item["path"]: item for item in document["items"]}
            self.assertEqual(by_path["Movies/a.mkv"]["status"], "SUCCESS")
            # The truncated item may have left a partial artifact; it is
            # reported UNCERTAIN (or clean-FAILED when nothing was written),
            # never fabricated complete, and never auto-replayed.
            self.assertIn(
                by_path["Movies/b.mkv"]["status"],
                {"UNCERTAIN", "FAILED"},
            )
            self.assertEqual(by_path["Movies/b.mkv"]["errorCategory"], "upload_stream_truncated")
            self.assertNotEqual(
                by_path["Movies/b.mkv"]["status"],
                "SUCCESS",
                "a truncated stream is never reported as a complete file",
            )


class UploadFaultInjectionTests(UploadTestCase):
    class _TruncatingWriteStorage(LocalStorage):
        """A provider that publishes a partial artifact then fails the write."""

        def __init__(self, storage_id: str, root: Path, *, after: int) -> None:
            super().__init__(storage_id, root)
            self._after = after

        def write(self, path, data, *, overwrite: bool = False):
            target = self._resolve(path, "write")
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as handle:
                written = 0
                while written < self._after:
                    chunk = data.read(1)
                    if not chunk:
                        break
                    handle.write(chunk)
                    written += len(chunk)
            raise self._mapped_error("write", path, OSError("injected mid-stream write failure"))

    class _FailingWriteStorage(LocalStorage):
        """A provider that refuses a streamed write without any artifact."""

        def write(self, path, data, *, overwrite: bool = False):
            raise self._mapped_error("write", path, OSError("injected clean write refusal"))

    def test_uncertain_write_is_recorded_and_never_replayed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True)
            faulted = self._TruncatingWriteStorage("source-storage", root / "source", after=1)
            api, active, _runtime = self._activate(
                root, storage_adapters={"source-storage": faulted}
            )
            uploads, _transfers = self._uploads(api, active)
            document = self._upload(
                uploads,
                root,
                items=[("Movies/uncertain.mkv", b"abcdef")],
            )
            item = document["items"][0]
            self.assertEqual(
                item["status"],
                "UNCERTAIN",
                "an interrupted write is reported uncertain, never SUCCESS",
            )
            self.assertEqual(item["errorCategory"], "upload_partial_artifact")
            # The partial artifact is left behind, not fabricated clean.
            target = root / "source" / "Movies" / "uncertain.mkv"
            self.assertTrue(target.exists())
            self.assertEqual(target.read_bytes(), b"a")

    def test_clean_failed_write_is_retry_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True)
            faulted = self._FailingWriteStorage("source-storage", root / "source")
            api, active, _runtime = self._activate(
                root, storage_adapters={"source-storage": faulted}
            )
            uploads, _transfers = self._uploads(api, active)
            document = self._upload(
                uploads,
                root,
                items=[("Movies/clean-fail.mkv", b"xyz")],
            )
            item = document["items"][0]
            self.assertEqual(item["status"], "FAILED")
            self.assertEqual(item["errorCategory"], "upload_write_failed")
            # No artifact was published, so the item is safe to retry.
            self.assertFalse((root / "source" / "Movies" / "clean-fail.mkv").exists())


class UploadDurableTaskTests(UploadTestCase):
    """B5: the admitted Upload is one observable durable Task lifecycle."""

    def test_admission_persists_pending_items_and_projection_is_pollable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            uploads, _transfers = self._uploads(api, active)
            manifest = self._manifest(
                "", "no_overwrite", [("Movies/a.mkv", b"aa"), ("Movies/b.mkv", b"bb")]
            )
            admitted = uploads.upload(
                resource_library_id="source",
                manifest=manifest,
                stream=io.BytesIO(b""),
            )
            task_id = admitted["taskId"]
            # The projection is readable from persisted state alone (any
            # process can serve it) and shows pending progress truthfully.
            projection = uploads.upload_projection(task_id)
            self.assertEqual(projection["totalItems"], 2)
            self.assertEqual(projection["processedItems"], 0)
            self.assertFalse(projection["terminal"])
            self.assertEqual(projection["status"], "RUNNING")
            self.assertEqual(
                {item["path"]: item["status"] for item in projection["items"]},
                {"Movies/a.mkv": "PENDING", "Movies/b.mkv": "PENDING"},
            )
            actions = {action["action"]: action for action in projection["actions"]}
            self.assertTrue(actions["pause"]["available"])
            self.assertTrue(actions["cancel"]["available"])
            # Resume is unavailable while running: the session streams the
            # items in manifest order and needs no operator resume.
            self.assertFalse(actions["resume"]["available"])
            from mediaflow.application.direct_file_uploads import drop_upload_session

            drop_upload_session(task_id)

    def test_projection_is_terminal_and_truthful_after_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            uploads, _transfers = self._uploads(api, active)
            document = self._upload(uploads, root, items=[("Movies/a.mkv", b"aa")])
            task_id = document["taskId"]
            projection = uploads.upload_projection(task_id)
            self.assertTrue(projection["terminal"])
            self.assertEqual(projection["status"], "SUCCESS")
            self.assertEqual(projection["succeededItems"], 1)
            self.assertEqual(projection["taskStatus"], "completed")
            actions = {action["action"]: action for action in projection["actions"]}
            self.assertFalse(actions["pause"]["available"])
            self.assertFalse(actions["cancel"]["available"])
            # The durable Task row itself reached its terminal aggregate.
            task = runtime.get_task(task_id)
            self.assertEqual(task.status.value, "completed")

    def test_cancel_takes_effect_at_a_safe_item_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            uploads, _transfers = self._uploads(api, active)
            manifest = self._manifest(
                "", "no_overwrite", [("Movies/a.mkv", b"aa"), ("Movies/b.mkv", b"bb")]
            )
            admitted = uploads.upload(resource_library_id="source", manifest=manifest)
            task_id = admitted["taskId"]
            # Cancel before the first item: the accepted cooperative
            # cancellation means no item is ever written.
            uploads._direct.tasks.cancel(task_id)
            first = uploads.execute_item(task_id, 0, io.BytesIO(b"aa"))
            self.assertEqual(first["status"], "FAILED")
            self.assertEqual(first["errorCategory"], "upload_cancelled")
            self.assertFalse((root / "source" / "Movies" / "a.mkv").exists())
            self.assertFalse((root / "source" / "Movies" / "b.mkv").exists())
            document = uploads.finish_upload(task_id)
            self.assertEqual(document["status"], "CANCELLED")
            projection = uploads.upload_projection(task_id)
            self.assertTrue(projection["terminal"])
            self.assertEqual(projection["taskStatus"], "cancelled")

    def test_pause_takes_effect_at_a_safe_item_boundary_without_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            uploads, _transfers = self._uploads(api, active)
            manifest = self._manifest(
                "", "no_overwrite", [("Movies/a.mkv", b"aa"), ("Movies/b.mkv", b"bb")]
            )
            admitted = uploads.upload(resource_library_id="source", manifest=manifest)
            task_id = admitted["taskId"]
            # Request the pause before the first item: the executor records
            # it at this safe item boundary.
            uploads._direct.tasks.request_pause(task_id)
            first = uploads.execute_item(task_id, 0, io.BytesIO(b"aa"))
            # A pause is never an item failure: the boundary response names
            # the pause, the item keeps its own pending row and nothing was
            # read or written.
            self.assertEqual(first["status"], "PAUSED")
            self.assertTrue(first["paused"])
            self.assertEqual(first["nextIndex"], 0)
            self.assertEqual(first["taskStatus"], "paused")
            self.assertFalse((root / "source" / "Movies" / "a.mkv").exists())
            projection = uploads.upload_projection(task_id)
            self.assertEqual(projection["status"], "PAUSED")
            self.assertFalse(projection["terminal"])
            self.assertEqual(projection["processedItems"], 0)
            actions = {action["action"]: action for action in projection["actions"]}
            # The still-live browser session can resume this exact upload.
            self.assertTrue(actions["resume"]["available"])
            # Finish while paused is refused: it would fabricate a terminal
            # aggregate over a journey the operator explicitly paused.
            with self.assertRaises(Exception) as caught:
                uploads.finish_upload(task_id)
            self.assertEqual(caught.exception.category, "finish_unavailable")
            self.assertFalse((root / "source" / "Movies" / "a.mkv").exists())
            self.assertFalse((root / "source" / "Movies" / "b.mkv").exists())
            # The durable item rows keep their pending truth.
            rows = {item.source_path: item for item in runtime.list_items(task_id)}
            self.assertEqual(rows["Movies/a.mkv"].status.value, "paused")
            self.assertEqual(rows["Movies/b.mkv"].status.value, "paused")

    def test_paused_upload_resumes_and_finishes_with_the_live_selection(self) -> None:
        """The complete pause-to-resume-to-finish journey, per B's blocker."""

        from mediaflow.application.direct_file_uploads import resume_upload_session

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            uploads, _transfers = self._uploads(api, active)
            manifest = self._manifest(
                "", "no_overwrite", [("Movies/a.mkv", b"aa"), ("Movies/b.mkv", b"bb")]
            )
            admitted = uploads.upload(resource_library_id="source", manifest=manifest)
            task_id = admitted["taskId"]
            uploads._direct.tasks.request_pause(task_id)
            paused = uploads.execute_item(task_id, 0, io.BytesIO(b"aa"))
            self.assertEqual(paused["status"], "PAUSED")
            # The Task resume action continues the still-live session: the
            # browser selection streams the remaining items in order.
            resumed = resume_upload_session(task_id)
            self.assertEqual(resumed["nextIndex"], 0)
            self.assertEqual(runtime.get_task(task_id).status.value, "running")
            first = uploads.execute_item(task_id, 0, io.BytesIO(b"aa"))
            self.assertEqual(first["status"], "SUCCESS")
            second = uploads.execute_item(task_id, 1, io.BytesIO(b"bb"))
            self.assertEqual(second["status"], "SUCCESS")
            document = uploads.finish_upload(task_id)
            self.assertEqual(document["status"], "SUCCESS")
            self.assertEqual((root / "source" / "Movies" / "a.mkv").read_bytes(), b"aa")
            self.assertEqual((root / "source" / "Movies" / "b.mkv").read_bytes(), b"bb")
            # The terminal projection is reachable and truthful.
            projection = uploads.upload_projection(task_id)
            self.assertTrue(projection["terminal"])
            self.assertEqual(projection["succeededItems"], 2)

    def test_pause_after_a_delivered_item_resumes_at_the_next_manifest_index(self) -> None:
        from mediaflow.application.direct_file_uploads import resume_upload_session

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            uploads, _transfers = self._uploads(api, active)
            manifest = self._manifest(
                "", "no_overwrite", [("Movies/a.mkv", b"aa"), ("Movies/b.mkv", b"bb")]
            )
            admitted = uploads.upload(resource_library_id="source", manifest=manifest)
            task_id = admitted["taskId"]
            first = uploads.execute_item(task_id, 0, io.BytesIO(b"aa"))
            self.assertEqual(first["status"], "SUCCESS")
            uploads._direct.tasks.request_pause(task_id)
            paused = uploads.execute_item(task_id, 1, io.BytesIO(b"bb"))
            self.assertEqual(paused["status"], "PAUSED")
            self.assertEqual(paused["nextIndex"], 1)
            # The acknowledged pause marks exactly the undelivered item.
            rows = {item.source_path: item for item in runtime.list_items(task_id)}
            self.assertEqual(rows["Movies/a.mkv"].status.value, "success")
            self.assertEqual(rows["Movies/b.mkv"].status.value, "paused")
            resume_upload_session(task_id)
            second = uploads.execute_item(task_id, 1, io.BytesIO(b"bb"))
            self.assertEqual(second["status"], "SUCCESS")
            document = uploads.finish_upload(task_id)
            self.assertEqual(document["status"], "SUCCESS")

    def test_paused_upload_cancel_never_treats_pause_as_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            uploads, _transfers = self._uploads(api, active)
            manifest = self._manifest(
                "", "no_overwrite", [("Movies/a.mkv", b"aa"), ("Movies/b.mkv", b"bb")]
            )
            admitted = uploads.upload(resource_library_id="source", manifest=manifest)
            task_id = admitted["taskId"]
            uploads._direct.tasks.request_pause(task_id)
            paused = uploads.execute_item(task_id, 0, io.BytesIO(b"aa"))
            self.assertEqual(paused["status"], "PAUSED")
            # Cancelling a paused upload converges the durable truth without
            # recording any item failure.
            uploads._direct.tasks.cancel(task_id)
            document = uploads.finish_upload(task_id)
            self.assertEqual(document["status"], "CANCELLED")
            projection = uploads.upload_projection(task_id)
            self.assertTrue(projection["terminal"])
            self.assertEqual(projection["taskStatus"], "cancelled")
            self.assertFalse((root / "source" / "Movies" / "a.mkv").exists())
            self.assertFalse((root / "source" / "Movies" / "b.mkv").exists())

    def test_lost_session_is_an_explicit_interrupted_recovery_not_not_found(self) -> None:
        """A genuinely lost in-process session keeps its Task and refuses."""
        from mediaflow.application.direct_file_uploads import (
            drop_upload_session,
            resume_upload_session,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            uploads, _transfers = self._uploads(api, active)
            manifest = self._manifest("", "no_overwrite", [("Movies/a.mkv", b"aa")])
            admitted = uploads.upload(resource_library_id="source", manifest=manifest)
            task_id = admitted["taskId"]
            drop_upload_session(task_id)
            with self.assertRaises(Exception) as caught:
                uploads.execute_item(task_id, 0, io.BytesIO(b"aa"))
            self.assertEqual(caught.exception.category, "session_interrupted")
            self.assertNotIn("not_found", str(caught.exception.code))
            # The refused request itself changed nothing and is safe to retry
            # as a resubmission.
            self.assertEqual(caught.exception.details["sideEffects"], "none")
            self.assertIs(caught.exception.details["retrySafe"], True)
            with self.assertRaises(Exception) as caught:
                uploads.finish_upload(task_id)
            self.assertEqual(caught.exception.category, "session_interrupted")
            # A lost session cannot resume: the browser bytes are not durable.
            with self.assertRaises(Exception) as caught:
                resume_upload_session(task_id)
            self.assertEqual(caught.exception.code, "resume_unavailable")
            # The durable Task row survives for the operator projection.
            self.assertEqual(runtime.get_task(task_id).command, "files_upload")

    def test_unknown_task_projection_is_a_bounded_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            uploads, _transfers = self._uploads(api, active)
            with self.assertRaises(Exception) as caught:
                uploads.upload_projection("task-does-not-exist")
            self.assertEqual(caught.exception.category, "not_found")


class UploadCapabilityTests(UploadTestCase):
    def test_read_only_storage_refuses_the_upload_with_zero_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True)
            read_only = LocalStorage("source-storage", root / "source", read_only=True)
            api, active, _runtime = self._activate(
                root, storage_adapters={"source-storage": read_only}
            )
            uploads, _transfers = self._uploads(api, active)
            with self.assertRaises(Exception) as caught:
                self._upload(uploads, root, items=[("Movies/x.mkv", b"x")])
            self.assertIn("capability_denied", str(caught.exception.code))
            self.assertFalse((root / "source" / "Movies" / "x.mkv").exists())


class UploadFramedApiTests(UploadTestCase):
    """The real request path: browser JSON manifest + per-item payload bodies.

    The transport is browser-native throughout: the admission is one bounded
    JSON POST (the browser computes the exact Content-Length), and each
    item's payload is one raw-bytes POST — no script-set Content-Length, no
    streaming duplex request option, no multipart assembly in script.
    """

    @staticmethod
    def _admission_environ(manifest: dict):
        body = json.dumps(manifest).encode("utf-8")
        return {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/api/v1/resource-libraries/source/files/uploads",
            "QUERY_STRING": "",
            "CONTENT_LENGTH": str(len(body)),
            "CONTENT_TYPE": "application/json",
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_AUTHORIZATION": "Bearer admin-token",
            "wsgi.input": io.BytesIO(body),
        }

    @staticmethod
    def _item_environ(task_id: str, index: int, payload: bytes):
        return {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": (
                f"/api/v1/resource-libraries/source/files/uploads/{task_id}/items/{index}"
            ),
            "QUERY_STRING": "",
            "CONTENT_LENGTH": str(len(payload)),
            "CONTENT_TYPE": "application/octet-stream",
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_AUTHORIZATION": "Bearer admin-token",
            "wsgi.input": io.BytesIO(payload),
        }

    @staticmethod
    def _call(api, environ):
        statuses: list[str] = []

        def start_response(status, headers):
            statuses.append(status)

        body = b"".join(api(environ, start_response))
        return int(statuses[0].split()[0]), body

    def test_full_journey_admits_streams_and_finishes_with_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            manifest = {
                "destinationDirectory": "Movies",
                "conflict": "no_overwrite",
                "items": [
                    {"relativePath": "a.mkv", "size": 7},
                    {"relativePath": "b.mkv", "size": 2},
                ],
            }
            status, body = self._call(api, self._admission_environ(manifest))
            self.assertEqual(status, 202, body)
            admitted = json.loads(body)
            self.assertEqual(admitted["status"], "RUNNING")
            self.assertTrue(admitted["taskId"])
            task_id = admitted["taskId"]
            # The durable projection is pollable between the item requests.
            poll_status, projection_body = self._call(
                api,
                {
                    "REQUEST_METHOD": "GET",
                    "PATH_INFO": (f"/api/v1/resource-libraries/source/files/uploads/{task_id}"),
                    "QUERY_STRING": "",
                    "CONTENT_LENGTH": "0",
                    "REMOTE_ADDR": "127.0.0.1",
                    "HTTP_AUTHORIZATION": "Bearer admin-token",
                    "wsgi.input": io.BytesIO(b""),
                },
            )
            self.assertEqual(poll_status, 200)
            projection = json.loads(projection_body)
            self.assertFalse(projection["terminal"])
            self.assertEqual(projection["totalItems"], 2)
            # Stream the exact payload bytes per item, in manifest order.
            for index, payload in enumerate([b"blocked", b"ok"]):
                item_status, item_body = self._call(
                    api, self._item_environ(task_id, index, payload)
                )
                self.assertEqual(item_status, 200, item_body)
            finish_status, finish_body = self._call(
                api,
                {
                    "REQUEST_METHOD": "POST",
                    "PATH_INFO": (
                        f"/api/v1/resource-libraries/source/files/uploads/{task_id}/finish"
                    ),
                    "QUERY_STRING": "",
                    "CONTENT_LENGTH": "0",
                    "REMOTE_ADDR": "127.0.0.1",
                    "HTTP_AUTHORIZATION": "Bearer admin-token",
                    "wsgi.input": io.BytesIO(b""),
                },
            )
            self.assertEqual(finish_status, 200, finish_body)
            document = json.loads(finish_body)
            self.assertEqual(document["status"], "SUCCESS")
            self.assertEqual((root / "source" / "Movies" / "a.mkv").read_bytes(), b"blocked")
            self.assertEqual((root / "source" / "Movies" / "b.mkv").read_bytes(), b"ok")
            tasks = runtime.list_tasks()
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0].command, "files_upload")
            self.assertEqual(tasks[0].status.value, "completed")

    def test_conflicting_first_item_never_poisons_the_sibling_payload(self) -> None:
        """B's exact reproduction, end to end through the real API path.

        ``existing.mkv=blocked`` conflicts (no-overwrite) and ``ok.mkv=ok``
        must still receive its exact bytes — per-item requests make framing
        misalignment structurally impossible.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source").mkdir(parents=True, exist_ok=True)
            (root / "source" / "existing.mkv").write_bytes(b"original")
            manifest = {
                "destinationDirectory": "",
                "conflict": "no_overwrite",
                "items": [
                    {"relativePath": "existing.mkv", "size": 7},
                    {"relativePath": "ok.mkv", "size": 2},
                ],
            }
            _status, body = self._call(api, self._admission_environ(manifest))
            task_id = json.loads(body)["taskId"]
            first_status, first_body = self._call(api, self._item_environ(task_id, 0, b"blocked"))
            self.assertEqual(first_status, 200, first_body)
            first = json.loads(first_body)
            self.assertEqual(first["status"], "FAILED")
            self.assertEqual(first["errorCategory"], "target_exists")
            second_status, second_body = self._call(api, self._item_environ(task_id, 1, b"ok"))
            self.assertEqual(second_status, 200, second_body)
            self.assertEqual(json.loads(second_body)["status"], "SUCCESS")
            finish_status, finish_body = self._call(
                api,
                {
                    "REQUEST_METHOD": "POST",
                    "PATH_INFO": (
                        f"/api/v1/resource-libraries/source/files/uploads/{task_id}/finish"
                    ),
                    "QUERY_STRING": "",
                    "CONTENT_LENGTH": "0",
                    "REMOTE_ADDR": "127.0.0.1",
                    "HTTP_AUTHORIZATION": "Bearer admin-token",
                    "wsgi.input": io.BytesIO(b""),
                },
            )
            document = json.loads(finish_body)
            self.assertEqual(finish_status, 200)
            by_path = {item["path"]: item for item in document["items"]}
            self.assertEqual(by_path["existing.mkv"]["status"], "FAILED")
            self.assertEqual(by_path["ok.mkv"]["status"], "SUCCESS")
            # The sibling's exact bytes are intact — never the conflict's.
            self.assertEqual((root / "source" / "ok.mkv").read_bytes(), b"ok")
            self.assertEqual((root / "source" / "existing.mkv").read_bytes(), b"original")

    def test_out_of_order_and_repeated_payload_requests_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source").mkdir(parents=True, exist_ok=True)
            manifest = {
                "destinationDirectory": "",
                "conflict": "no_overwrite",
                "items": [
                    {"relativePath": "a.mkv", "size": 2},
                    {"relativePath": "b.mkv", "size": 2},
                ],
            }
            _status, body = self._call(api, self._admission_environ(manifest))
            task_id = json.loads(body)["taskId"]
            # An out-of-order payload (index 1 before 0) is refused before
            # any read, so item bytes can never be consumed as a sibling's.
            order_status, order_body = self._call(api, self._item_environ(task_id, 1, b"bb"))
            self.assertEqual(order_status, 409, order_body)
            self.assertIn("item_out_of_order", order_body.decode())
            order_details = json.loads(order_body)["error"]["details"]
            self.assertEqual(order_details["sideEffects"], "none")
            self.assertIs(order_details["retrySafe"], True)
            self.assertFalse((root / "source" / "b.mkv").exists())
            # Delivering index 0, then repeating it, is refused as well.
            self._call(api, self._item_environ(task_id, 0, b"aa"))
            repeat_status, repeat_body = self._call(api, self._item_environ(task_id, 0, b"aa"))
            self.assertEqual(repeat_status, 409, repeat_body)
            self.assertIn("item_already_delivered", repeat_body.decode())
            repeat_details = json.loads(repeat_body)["error"]["details"]
            self.assertEqual(repeat_details["sideEffects"], "none")
            self.assertIs(repeat_details["retrySafe"], True)

    def test_item_body_length_must_equal_the_admitted_item_size(self) -> None:
        """B's length-mismatch reproduction, end to end through the route.

        A manifest declaring two bytes followed by an item request with
        ``Content-Length: 7`` and body ``abEXTRA`` must be refused before any
        mutation; the missing-header case fails closed as well.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source").mkdir(parents=True, exist_ok=True)
            manifest = {
                "destinationDirectory": "",
                "conflict": "no_overwrite",
                "items": [{"relativePath": "a.mkv", "size": 2}],
            }
            _status, body = self._call(api, self._admission_environ(manifest))
            task_id = json.loads(body)["taskId"]
            environ = self._item_environ(task_id, 0, b"abEXTRA")
            environ["CONTENT_LENGTH"] = "7"
            status, mismatch_body = self._call(api, environ)
            self.assertEqual(status, 400, mismatch_body)
            self.assertFalse((root / "source" / "a.mkv").exists())
            # The declared two bytes still stream exactly after the refusal:
            # the mismatched request never consumed nor wrote anything.
            exact_status, exact_body = self._call(api, self._item_environ(task_id, 0, b"ab"))
            self.assertEqual(exact_status, 200, exact_body)
            self.assertEqual(json.loads(exact_body)["status"], "SUCCESS")
            self.assertEqual((root / "source" / "a.mkv").read_bytes(), b"ab")

    def test_item_shorter_longer_and_missing_lengths_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source").mkdir(parents=True, exist_ok=True)
            manifest = {
                "destinationDirectory": "",
                "conflict": "no_overwrite",
                "items": [{"relativePath": "a.mkv", "size": 2}],
            }
            _status, body = self._call(api, self._admission_environ(manifest))
            task_id = json.loads(body)["taskId"]
            # A shorter declared length than the admitted size is refused.
            short = self._item_environ(task_id, 0, b"a")
            short["CONTENT_LENGTH"] = "1"
            status, short_body = self._call(api, short)
            self.assertEqual(status, 400, short_body)
            self.assertFalse((root / "source" / "a.mkv").exists())
            # A missing Content-Length fails closed instead of trusting the
            # body.
            missing = self._item_environ(task_id, 0, b"ab")
            missing["CONTENT_LENGTH"] = ""
            status, missing_body = self._call(api, missing)
            self.assertEqual(status, 400, missing_body)
            self.assertFalse((root / "source" / "a.mkv").exists())
            # An invalid Content-Length fails closed as well.
            invalid = self._item_environ(task_id, 0, b"ab")
            invalid["CONTENT_LENGTH"] = "two"
            status, invalid_body = self._call(api, invalid)
            self.assertEqual(status, 400, invalid_body)
            self.assertFalse((root / "source" / "a.mkv").exists())
            # Nothing was recorded and the session still accepts the exact
            # journey.
            exact_status, exact_body = self._call(api, self._item_environ(task_id, 0, b"ab"))
            self.assertEqual(exact_status, 200, exact_body)
            self.assertEqual(json.loads(exact_body)["status"], "SUCCESS")
            self.assertEqual((root / "source" / "a.mkv").read_bytes(), b"ab")

    def test_admission_requires_multipart_free_json_and_bounded_size(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source").mkdir(parents=True, exist_ok=True)
            # A non-JSON body is refused before any Task or mutation exists.
            status, body = self._call(
                api,
                {
                    "REQUEST_METHOD": "POST",
                    "PATH_INFO": "/api/v1/resource-libraries/source/files/uploads",
                    "QUERY_STRING": "",
                    "CONTENT_LENGTH": "7",
                    "CONTENT_TYPE": "text/plain",
                    "REMOTE_ADDR": "127.0.0.1",
                    "HTTP_AUTHORIZATION": "Bearer admin-token",
                    "wsgi.input": io.BytesIO(b"notjson"),
                },
            )
            self.assertTrue(400 <= status < 500, body)
            self.assertFalse((root / "source" / "a.mkv").exists())

    def test_upload_projection_route_serves_the_durable_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            manifest = {
                "destinationDirectory": "",
                "conflict": "no_overwrite",
                "items": [{"relativePath": "x.mkv", "size": 2}],
            }
            _status, body = self._call(api, self._admission_environ(manifest))
            task_id = json.loads(body)["taskId"]
            proj_status, projection_body = self._call(
                api,
                {
                    "REQUEST_METHOD": "GET",
                    "PATH_INFO": (f"/api/v1/resource-libraries/source/files/uploads/{task_id}"),
                    "QUERY_STRING": "",
                    "CONTENT_LENGTH": "0",
                    "REMOTE_ADDR": "127.0.0.1",
                    "HTTP_AUTHORIZATION": "Bearer admin-token",
                    "wsgi.input": io.BytesIO(b""),
                },
            )
            self.assertEqual(proj_status, 200)
            projection = json.loads(projection_body)
            self.assertFalse(projection["terminal"])
            self.assertEqual(projection["totalItems"], 1)
            # An unauthenticated request is refused.
            unauth_status, _unauth = self._call(
                api,
                {
                    "REQUEST_METHOD": "GET",
                    "PATH_INFO": (f"/api/v1/resource-libraries/source/files/uploads/{task_id}"),
                    "QUERY_STRING": "",
                    "CONTENT_LENGTH": "0",
                    "REMOTE_ADDR": "127.0.0.1",
                    "wsgi.input": io.BytesIO(b""),
                },
            )
            self.assertEqual(unauth_status, 401)

    def test_upload_task_pause_and_cancel_via_the_operator_lifecycle_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            manifest = {
                "destinationDirectory": "",
                "conflict": "no_overwrite",
                "items": [
                    {"relativePath": "Movies/a.mkv", "size": 2},
                    {"relativePath": "Movies/b.mkv", "size": 2},
                ],
            }
            _status, body = self._call(api, self._admission_environ(manifest))
            admitted = json.loads(body)
            task_id = admitted["taskId"]
            projection_path = f"/api/v1/resource-libraries/source/files/uploads/{task_id}"
            current = json.loads(
                self._call(
                    api,
                    {
                        "REQUEST_METHOD": "GET",
                        "PATH_INFO": projection_path,
                        "QUERY_STRING": "",
                        "CONTENT_LENGTH": "0",
                        "REMOTE_ADDR": "127.0.0.1",
                        "HTTP_AUTHORIZATION": "Bearer admin-token",
                        "wsgi.input": io.BytesIO(b""),
                    },
                )[1]
            )["version"]
            pause_status, pause_document = request(
                api,
                f"/api/v1/tasks/{task_id}/pause",
                method="POST",
                body={"expectedUpdatedAt": current},
            )
            self.assertEqual(pause_status, 200, pause_document)
            # The accepted pause request is durable but cooperative: the
            # Task stays running until the acknowledged item boundary, and
            # the projection honestly stops advertising a second pause.
            _status, projection_body = self._call(
                api,
                {
                    "REQUEST_METHOD": "GET",
                    "PATH_INFO": projection_path,
                    "QUERY_STRING": "",
                    "CONTENT_LENGTH": "0",
                    "REMOTE_ADDR": "127.0.0.1",
                    "HTTP_AUTHORIZATION": "Bearer admin-token",
                    "wsgi.input": io.BytesIO(b""),
                },
            )
            projection = json.loads(projection_body)
            actions = {action["action"]: action for action in projection["actions"]}
            self.assertFalse(actions["pause"]["available"])
            self.assertTrue(actions["cancel"]["available"])
            # Cancel through the same route converges the durable truth.
            cancel_status, cancel_document = request(
                api,
                f"/api/v1/tasks/{task_id}/cancel",
                method="POST",
                body={
                    "expectedUpdatedAt": json.loads(
                        self._call(
                            api,
                            {
                                "REQUEST_METHOD": "GET",
                                "PATH_INFO": projection_path,
                                "QUERY_STRING": "",
                                "CONTENT_LENGTH": "0",
                                "REMOTE_ADDR": "127.0.0.1",
                                "HTTP_AUTHORIZATION": "Bearer admin-token",
                                "wsgi.input": io.BytesIO(b""),
                            },
                        )[1]
                    )["version"]
                },
            )
            self.assertEqual(cancel_status, 200, cancel_document)
            final = json.loads(
                self._call(
                    api,
                    {
                        "REQUEST_METHOD": "GET",
                        "PATH_INFO": projection_path,
                        "QUERY_STRING": "",
                        "CONTENT_LENGTH": "0",
                        "REMOTE_ADDR": "127.0.0.1",
                        "HTTP_AUTHORIZATION": "Bearer admin-token",
                        "wsgi.input": io.BytesIO(b""),
                    },
                )[1]
            )
            self.assertEqual(final["taskStatus"], "cancelled")
            self.assertTrue(final["terminal"])
            # No item was written and the admission state is cleaned up.
            self.assertFalse((root / "source" / "Movies" / "a.mkv").exists())

    def test_upload_pause_resume_and_finish_through_the_production_routes(self) -> None:
        """The complete Web/API pause-to-resume journey per B's blocker.

        The pause is acknowledged at the item boundary (a PAUSED boundary
        response, never an item failure), the browser stops before the next
        payload POST, the resume route continues the still-live selection and
        the finish records the honest terminal aggregate.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            manifest = {
                "destinationDirectory": "",
                "conflict": "no_overwrite",
                "items": [
                    {"relativePath": "Movies/a.mkv", "size": 2},
                    {"relativePath": "Movies/b.mkv", "size": 2},
                ],
            }
            _status, body = self._call(api, self._admission_environ(manifest))
            task_id = json.loads(body)["taskId"]
            projection_path = f"/api/v1/resource-libraries/source/files/uploads/{task_id}"

            def projection():
                status, payload = self._call(
                    api,
                    {
                        "REQUEST_METHOD": "GET",
                        "PATH_INFO": projection_path,
                        "QUERY_STRING": "",
                        "CONTENT_LENGTH": "0",
                        "REMOTE_ADDR": "127.0.0.1",
                        "HTTP_AUTHORIZATION": "Bearer admin-token",
                        "wsgi.input": io.BytesIO(b""),
                    },
                )
                self.assertEqual(status, 200, payload)
                return json.loads(payload)

            current = projection()["version"]
            pause_status, pause_document = request(
                api,
                f"/api/v1/tasks/{task_id}/pause",
                method="POST",
                body={"expectedUpdatedAt": current},
            )
            self.assertEqual(pause_status, 200, pause_document)
            # The first item request acknowledges the pause at the safe item
            # boundary: HTTP 200 with a PAUSED boundary document — the Web
            # stops here and never posts the next Blob.
            paused_status, paused_body = self._call(api, self._item_environ(task_id, 0, b"aa"))
            self.assertEqual(paused_status, 200, paused_body)
            paused = json.loads(paused_body)
            self.assertEqual(paused["status"], "PAUSED")
            self.assertTrue(paused["paused"])
            self.assertEqual(paused["nextIndex"], 0)
            self.assertFalse((root / "source" / "Movies" / "a.mkv").exists())
            # The durable projection shows the paused truth with resume
            # advertised (the session is still live in this process).
            after_pause = projection()
            self.assertEqual(after_pause["taskStatus"], "paused")
            self.assertEqual(after_pause["processedItems"], 0)
            actions = {action["action"]: action for action in after_pause["actions"]}
            self.assertTrue(actions["resume"]["available"])
            self.assertFalse(after_pause["terminal"])
            # Finish while paused is refused with a bounded conflict.
            finish_status, finish_body = self._call(
                api,
                {
                    "REQUEST_METHOD": "POST",
                    "PATH_INFO": f"{projection_path}/finish",
                    "QUERY_STRING": "",
                    "CONTENT_LENGTH": "0",
                    "REMOTE_ADDR": "127.0.0.1",
                    "HTTP_AUTHORIZATION": "Bearer admin-token",
                    "wsgi.input": io.BytesIO(b""),
                },
            )
            self.assertEqual(finish_status, 409, finish_body)
            self.assertIn("finish_unavailable", finish_body.decode())
            # Resume through the upload resume route; the journey continues
            # with the exact same selection in manifest order.
            resume_status, resume_body = self._call(
                api,
                {
                    "REQUEST_METHOD": "POST",
                    "PATH_INFO": f"{projection_path}/resume",
                    "QUERY_STRING": "",
                    "CONTENT_LENGTH": "0",
                    "REMOTE_ADDR": "127.0.0.1",
                    "HTTP_AUTHORIZATION": "Bearer admin-token",
                    "wsgi.input": io.BytesIO(b""),
                },
            )
            self.assertEqual(resume_status, 200, resume_body)
            resumed = json.loads(resume_body)
            self.assertEqual(resumed["nextIndex"], 0)
            self.assertEqual(runtime.get_task(task_id).status.value, "running")
            # The Web re-streams the remaining items from the advertised index.
            for index, payload in enumerate([b"aa", b"bb"]):
                item_status, item_payload = self._call(
                    api, self._item_environ(task_id, index, payload)
                )
                self.assertEqual(item_status, 200, item_payload)
                self.assertEqual(json.loads(item_payload)["status"], "SUCCESS")
            finish_status, finish_payload = self._call(
                api,
                {
                    "REQUEST_METHOD": "POST",
                    "PATH_INFO": f"{projection_path}/finish",
                    "QUERY_STRING": "",
                    "CONTENT_LENGTH": "0",
                    "REMOTE_ADDR": "127.0.0.1",
                    "HTTP_AUTHORIZATION": "Bearer admin-token",
                    "wsgi.input": io.BytesIO(b""),
                },
            )
            self.assertEqual(finish_status, 200, finish_payload)
            document = json.loads(finish_payload)
            self.assertEqual(document["status"], "SUCCESS")
            self.assertEqual((root / "source" / "Movies" / "a.mkv").read_bytes(), b"aa")
            self.assertEqual((root / "source" / "Movies" / "b.mkv").read_bytes(), b"bb")
            # The resume route is unauthenticated-refused like its siblings.
            unauth_status, _unauth = self._call(
                api,
                {
                    "REQUEST_METHOD": "POST",
                    "PATH_INFO": f"{projection_path}/resume",
                    "QUERY_STRING": "",
                    "CONTENT_LENGTH": "0",
                    "REMOTE_ADDR": "127.0.0.1",
                    "wsgi.input": io.BytesIO(b""),
                },
            )
            self.assertEqual(unauth_status, 401)


class UploadOperationLockTests(UploadTestCase):
    """B1 P1 regression: finish_upload must not race an in-flight item.

    The operation lock per live UploadSession prevents finish_upload from
    publishing mutually contradictory durable and user-visible outcomes.
    Two deterministic WSGI-route regressions prove the fix.
    """

    class _BlockingWriteStorage(LocalStorage):
        """A provider that blocks at the start of write until a gate opens.

        The gate blocks before any bytes are written, so the caller knows
        the operation lock is held (``execute_item`` holds it for the
        entire execution) when the gate is open.
        """

        def __init__(
            self,
            storage_id: str,
            root: Path,
            *,
            write_started: threading.Event,
            gate: threading.Event,
        ) -> None:
            super().__init__(storage_id, root)
            self._write_started = write_started
            self._gate = gate

        def write(self, path, data, *, overwrite: bool = False):
            # Signal before any write so the test knows the executor has
            # entered the storage boundary and the operation lock is held.
            self._write_started.set()
            # Block until the test releases the gate.
            self._gate.wait(timeout=5)
            target = self._resolve(path, "write")
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as handle:
                while True:
                    chunk = data.read(4096)
                    if not chunk:
                        break
                    handle.write(chunk)

    @staticmethod
    def _admission_environ(manifest: dict):
        body = json.dumps(manifest).encode("utf-8")
        return {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/api/v1/resource-libraries/source/files/uploads",
            "QUERY_STRING": "",
            "CONTENT_LENGTH": str(len(body)),
            "CONTENT_TYPE": "application/json",
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_AUTHORIZATION": "Bearer admin-token",
            "wsgi.input": io.BytesIO(body),
        }

    @staticmethod
    def _item_environ(task_id: str, index: int, payload: bytes):
        return {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": (
                f"/api/v1/resource-libraries/source/files/uploads/{task_id}/items/{index}"
            ),
            "QUERY_STRING": "",
            "CONTENT_LENGTH": str(len(payload)),
            "CONTENT_TYPE": "application/octet-stream",
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_AUTHORIZATION": "Bearer admin-token",
            "wsgi.input": io.BytesIO(payload),
        }

    @staticmethod
    def _finish_environ(task_id: str):
        return {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": f"/api/v1/resource-libraries/source/files/uploads/{task_id}/finish",
            "QUERY_STRING": "",
            "CONTENT_LENGTH": "0",
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_AUTHORIZATION": "Bearer admin-token",
            "wsgi.input": io.BytesIO(b""),
        }

    @staticmethod
    def _call(api, environ):
        statuses: list[str] = []

        def start_response(status, headers):
            statuses.append(status)

        body = b"".join(api(environ, start_response))
        return int(statuses[0].split()[0]), body

    def test_inflight_item_makes_concurrent_finish_return_409_then_finish_succeeds(
        self,
    ) -> None:
        """(1) An in-flight item makes concurrent finish return 409 with
        zero state change, then the same finish succeeds after that item
        completes.  Both results are internally consistent."""

        write_started = threading.Event()
        gate = threading.Event()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            blocking = self._BlockingWriteStorage(
                "source-storage",
                root / "source",
                write_started=write_started,
                gate=gate,
            )
            api, active, runtime = self._activate(
                root, storage_adapters={"source-storage": blocking}
            )
            manifest = {
                "destinationDirectory": "",
                "conflict": "no_overwrite",
                "items": [{"relativePath": "Movies/a.mkv", "size": 11}],
            }
            status, body = self._call(api, self._admission_environ(manifest))
            self.assertEqual(status, 202, body)
            task_id = json.loads(body)["taskId"]
            # Start item 0 in a background thread — it will block in the
            # storage write while holding the operation lock.
            result_box: list[tuple[int, bytes]] = []

            def item_thread():
                result_box.append(self._call(api, self._item_environ(task_id, 0, b"hello-world")))

            t = threading.Thread(target=item_thread)
            t.start()
            # Wait until the storage write has started — the operation lock
            # is held for the entire execute_item.
            self.assertTrue(write_started.wait(timeout=5))
            # While the item is in-flight (holding the operation lock),
            # concurrent finish must return 409 with zero state change.
            finish_status, finish_body = self._call(api, self._finish_environ(task_id))
            self.assertEqual(finish_status, 409, finish_body)
            document = json.loads(finish_body)
            self.assertEqual(document["error"]["code"], "files_upload_item_in_progress")
            details = document["error"]["details"]
            self.assertEqual(details["category"], "upload_item_in_progress")
            # Truthful zero-effect, retry-safe recovery: the refused finish
            # changed nothing, so it must not claim Storage mutations.
            self.assertEqual(details["sideEffects"], "none")
            self.assertIs(details["retrySafe"], True)
            self.assertIn("changed nothing", details["durableState"])
            # The Task is still running — no terminal aggregate was published.
            task = runtime.get_task(task_id)
            self.assertEqual(task.status.value, "running")
            # Release the gate so the item completes.
            gate.set()
            t.join(timeout=5)
            self.assertEqual(len(result_box), 1)
            item_status, item_body = result_box[0]
            self.assertEqual(item_status, 200, item_body)
            self.assertEqual(json.loads(item_body)["status"], "SUCCESS")
            self.assertTrue((root / "source" / "Movies" / "a.mkv").exists())
            # Now finish succeeds and reaches the honest terminal aggregate.
            finish_status2, finish_body2 = self._call(api, self._finish_environ(task_id))
            self.assertEqual(finish_status2, 200, finish_body2)
            document = json.loads(finish_body2)
            self.assertEqual(document["status"], "SUCCESS")
            task = runtime.get_task(task_id)
            self.assertEqual(task.status.value, "completed")
            # The projection is internally consistent.
            proj_status, proj_body = self._call(
                api,
                {
                    "REQUEST_METHOD": "GET",
                    "PATH_INFO": f"/api/v1/resource-libraries/source/files/uploads/{task_id}",
                    "QUERY_STRING": "",
                    "CONTENT_LENGTH": "0",
                    "REMOTE_ADDR": "127.0.0.1",
                    "HTTP_AUTHORIZATION": "Bearer admin-token",
                    "wsgi.input": io.BytesIO(b""),
                },
            )
            self.assertEqual(proj_status, 200)
            projection = json.loads(proj_body)
            self.assertTrue(projection["terminal"])
            self.assertEqual(projection["status"], "SUCCESS")
            self.assertEqual(projection["taskStatus"], "completed")

    def test_two_concurrent_deliveries_for_one_item_invoke_exactly_one_mutation(
        self,
    ) -> None:
        """(2) Two concurrent deliveries for one item invoke exactly one
        OrganizerExecutor mutation while the other receives a stable 409.
        The 409 is the ordering guard (item_already_delivered) or the
        operation lock (upload_item_in_progress); both are bounded refusals
        with truthful zero-effect recovery.  Both results are internally
        consistent."""

        write_started = threading.Event()
        gate = threading.Event()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            blocking = self._BlockingWriteStorage(
                "source-storage",
                root / "source",
                write_started=write_started,
                gate=gate,
            )
            api, active, runtime = self._activate(
                root, storage_adapters={"source-storage": blocking}
            )
            executor = _CountingExecutor()
            binding = api._prepare_runtime_binding_for_revision(active)
            self.assertIsNotNone(binding.direct_uploads)
            uploads = DirectFileUploadService(
                direct_files=binding.direct_files,
                executor=executor,
            )
            manifest = self._manifest("", "no_overwrite", [("Movies/solo.mkv", b"exact-bytes")])
            admitted = uploads.upload(resource_library_id="source", manifest=manifest)
            task_id = admitted["taskId"]
            # Start the first delivery in a background thread via the
            # uploads service (which uses the _CountingExecutor).  It will
            # block in the storage write while holding the operation lock.
            result_a: list[dict] = []

            def first_delivery():
                try:
                    result_a.append(uploads.execute_item(task_id, 0, io.BytesIO(b"exact-bytes")))
                except Exception as exc:
                    result_a.append({"_error": str(exc)})

            t = threading.Thread(target=first_delivery)
            t.start()
            # Wait until the storage write has started — the operation lock
            # is held for the entire execute_item.
            self.assertTrue(write_started.wait(timeout=5))
            # The second delivery for the same index goes through the WSGI
            # route and is refused with a stable 409 — either the ordering
            # guard or the operation lock.
            result_b_status, result_b_body = self._call(
                api, self._item_environ(task_id, 0, b"exact-bytes")
            )
            self.assertEqual(result_b_status, 409, result_b_body)
            result_b_text = result_b_body.decode()
            self.assertTrue(
                "item_already_delivered" in result_b_text
                or "upload_item_in_progress" in result_b_text,
                f"expected a stable refusal, got: {result_b_text}",
            )
            # Release the gate so the first delivery completes.
            gate.set()
            t.join(timeout=5)
            self.assertEqual(len(result_a), 1)
            self.assertNotIn("_error", result_a[0], result_a[0].get("_error"))
            self.assertEqual(result_a[0]["status"], "SUCCESS")
            # Exactly one write mutation crossed the Executor boundary.
            write_count = sum(1 for b in executor.boundaries if b == "WRITE_STREAM")
            self.assertEqual(write_count, 1)
            # Finish the upload and verify a single internally consistent
            # terminal Task/projection/result.
            finished = uploads.finish_upload(task_id)
            self.assertEqual(finished["status"], "SUCCESS")
            self.assertEqual(finished["succeededItems"], 1)
            task = runtime.get_task(task_id)
            self.assertEqual(task.status.value, "completed")
            projection = uploads.upload_projection(task_id)
            self.assertTrue(projection["terminal"])
            self.assertEqual(projection["status"], "SUCCESS")
            self.assertEqual(projection["succeededItems"], 1)
            self.assertEqual(projection["failedItems"], 0)

    def test_finish_waits_at_the_lock_before_any_decision_then_the_item_is_bounded(
        self,
    ) -> None:
        """B4 P1(a): the operation lock fences *every* decision.

        An item request that has already reached the operation-lock
        acquisition (before any phase/Task/order decision) must not execute
        against a Task the concurrent finish already made terminal.  With the
        lock acquired first, exactly one side proceeds: finish publishes the
        honest terminal aggregate and the item request is refused with a
        bounded 409 — never a generic 500, never a fabricated write, never a
        success document for a PENDING row.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            api, active, runtime = self._activate(root)
            from mediaflow.application import direct_file_uploads as uploads_module

            manifest = {
                "destinationDirectory": "",
                "conflict": "no_overwrite",
                "items": [{"relativePath": "Movies/a.mkv", "size": 11}],
            }
            status, body = self._call(api, self._admission_environ(manifest))
            self.assertEqual(status, 202, body)
            task_id = json.loads(body)["taskId"]
            session = uploads_module._upload_session(task_id)
            self.assertIsNotNone(session)
            # Deterministically hold the session at the operation-lock
            # acquisition: the item request has passed the session lookup and
            # is waiting *before* every phase/Task/order decision.
            gated = self._GatedOperationLock(session._operation_lock)
            session._operation_lock = gated
            item_results: list[tuple[int, bytes]] = []

            def item_thread():
                item_results.append(self._call(api, self._item_environ(task_id, 0, b"hello-world")))

            t = threading.Thread(target=item_thread)
            t.start()
            self.assertTrue(gated.reached.wait(timeout=5), "the item never reached the lock")
            # The waiting item holds nothing yet, so finish wins the session
            # and publishes the one honest terminal aggregate.
            finish_status, finish_body = self._call(api, self._finish_environ(task_id))
            self.assertEqual(finish_status, 200, finish_body)
            self.assertEqual(json.loads(finish_body)["status"], "FAILED")
            task = runtime.get_task(task_id)
            self.assertEqual(task.status.value, "failed")
            # Release the item: it re-reads the terminal truth under the lock
            # and is refused with the bounded interrupted recovery.
            gated.gate.set()
            t.join(timeout=5)
            self.assertEqual(len(item_results), 1)
            item_status, item_body = item_results[0]
            self.assertNotEqual(item_status, 500, item_body)
            self.assertEqual(item_status, 409, item_body)
            document = json.loads(item_body)
            self.assertTrue(document["error"]["code"].startswith("files_upload_"))
            details = document["error"]["details"]
            self.assertEqual(details["category"], "session_interrupted")
            # The refused request itself changed nothing, so its own recovery
            # evidence is truthful: zero effect and retry-safe.
            self.assertEqual(details["sideEffects"], "none")
            self.assertIs(details["retrySafe"], True)
            # No file was written and exactly one terminal aggregate exists.
            self.assertFalse((root / "source" / "Movies" / "a.mkv").exists())
            projection = uploads_module.DirectFileUploadService(
                direct_files=api._prepare_runtime_binding_for_revision(active).direct_files
            ).upload_projection(task_id)
            self.assertTrue(projection["terminal"])
            self.assertEqual(projection["status"], "FAILED")
            self.assertEqual(projection["failedItems"], 1)
            self.assertEqual(projection["succeededItems"], 0)

    def test_item_waits_at_the_lock_before_any_decision_then_finish_is_bounded(
        self,
    ) -> None:
        """B4 P1(a) converse: an item that wins the lock keeps finish bounded.

        The item acquires the operation lock first and blocks inside the real
        executor; the concurrent finish must not return a success document nor
        mutate anything — it is the same bounded 409 with truthful
        zero-effect, retry-safe recovery, and the item still completes once.
        """

        write_started = threading.Event()
        gate = threading.Event()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            blocking = self._BlockingWriteStorage(
                "source-storage",
                root / "source",
                write_started=write_started,
                gate=gate,
            )
            api, active, runtime = self._activate(
                root, storage_adapters={"source-storage": blocking}
            )
            manifest = {
                "destinationDirectory": "",
                "conflict": "no_overwrite",
                "items": [{"relativePath": "Movies/a.mkv", "size": 11}],
            }
            status, body = self._call(api, self._admission_environ(manifest))
            self.assertEqual(status, 202, body)
            task_id = json.loads(body)["taskId"]
            item_results: list[tuple[int, bytes]] = []

            def item_thread():
                item_results.append(self._call(api, self._item_environ(task_id, 0, b"hello-world")))

            t = threading.Thread(target=item_thread)
            t.start()
            self.assertTrue(write_started.wait(timeout=5))
            finish_status, finish_body = self._call(api, self._finish_environ(task_id))
            self.assertEqual(finish_status, 409, finish_body)
            details = json.loads(finish_body)["error"]["details"]
            self.assertEqual(details["category"], "upload_item_in_progress")
            # Truthful zero-effect, retry-safe recovery — never a
            # success-status document and never a "storage_mutations" claim
            # for a request that changed nothing.
            self.assertEqual(details["sideEffects"], "none")
            self.assertIs(details["retrySafe"], True)
            self.assertEqual(runtime.get_task(task_id).status.value, "running")
            gate.set()
            t.join(timeout=5)
            item_status, item_body = item_results[0]
            self.assertEqual(item_status, 200, item_body)
            self.assertEqual(json.loads(item_body)["status"], "SUCCESS")
            # The same finish now succeeds and reaches the honest terminal.
            finish_status2, finish_body2 = self._call(api, self._finish_environ(task_id))
            self.assertEqual(finish_status2, 200, finish_body2)
            self.assertEqual(json.loads(finish_body2)["status"], "SUCCESS")
            self.assertEqual(runtime.get_task(task_id).status.value, "completed")
            self.assertEqual((root / "source" / "Movies" / "a.mkv").read_bytes(), b"hello-world")

    def test_a_different_next_item_reaches_the_lock_busy_branch(self) -> None:
        """B4 P1(b): a *different* next item must hit the lock-busy branch.

        Item 0 holds the operation lock inside the executor; the concurrently
        submitted item 1 is not an ordering violation, so it must reach the
        lock-busy branch and be refused as one bounded 409 with truthful
        zero-effect recovery — not HTTP 200, not a FAILED row, and not a
        fabricated per-item outcome for an item that was never executed.
        """

        write_started = threading.Event()
        gate = threading.Event()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            blocking = self._BlockingWriteStorage(
                "source-storage",
                root / "source",
                write_started=write_started,
                gate=gate,
            )
            api, active, runtime = self._activate(
                root, storage_adapters={"source-storage": blocking}
            )
            manifest = {
                "destinationDirectory": "",
                "conflict": "no_overwrite",
                "items": [
                    {"relativePath": "Movies/first.mkv", "size": 5},
                    {"relativePath": "Movies/second.mkv", "size": 6},
                ],
            }
            status, body = self._call(api, self._admission_environ(manifest))
            self.assertEqual(status, 202, body)
            task_id = json.loads(body)["taskId"]
            first_results: list[tuple[int, bytes]] = []

            def first_thread():
                first_results.append(self._call(api, self._item_environ(task_id, 0, b"first")))

            t = threading.Thread(target=first_thread)
            t.start()
            self.assertTrue(write_started.wait(timeout=5))
            # Item 1 is the genuinely different next item, not an ordering
            # violation: it reaches the operation lock and is refused there.
            second_status, second_body = self._call(api, self._item_environ(task_id, 1, b"second"))
            self.assertNotEqual(second_status, 500, second_body)
            self.assertEqual(second_status, 409, second_body)
            details = json.loads(second_body)["error"]["details"]
            self.assertEqual(details["category"], "upload_item_in_progress")
            self.assertEqual(details["sideEffects"], "none")
            self.assertIs(details["retrySafe"], True)
            # The durable truth is unchanged: item 1 keeps its own PENDING row
            # and no Result was fabricated for it.
            rows = {row.source_path: row.status.value for row in runtime.list_items(task_id)}
            self.assertEqual(rows["Movies/second.mkv"], "pending")
            self.assertEqual(rows["Movies/first.mkv"], "processing")
            self.assertEqual(list(runtime.list_results(task_id)), [])
            gate.set()
            t.join(timeout=5)
            self.assertEqual(first_results[0][0], 200, first_results[0][1])
            # Item 1 streams normally afterwards — the busy refusal was not an
            # outcome and left nothing behind.
            after_status, after_body = self._call(api, self._item_environ(task_id, 1, b"second"))
            self.assertEqual(after_status, 200, after_body)
            self.assertEqual(json.loads(after_body)["status"], "SUCCESS")
            finish_status, finish_body = self._call(api, self._finish_environ(task_id))
            self.assertEqual(finish_status, 200, finish_body)
            self.assertEqual(json.loads(finish_body)["status"], "SUCCESS")
            self.assertEqual((root / "source" / "Movies" / "second.mkv").read_bytes(), b"second")

    def test_two_sessions_same_target_record_bounded_failure_and_continue(self) -> None:
        """A destination lock is a durable item failure, not an HTTP 500.

        Two independently admitted sessions plan the same initially absent
        target.  The first holds the real Storage write; the second must
        receive the already-persisted FAILED item outcome, then continue with
        its own sibling and finish honestly.  Only the first session may write
        the contested target.
        """

        write_started = threading.Event()
        gate = threading.Event()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            blocking = self._BlockingWriteStorage(
                "source-storage",
                root / "source",
                write_started=write_started,
                gate=gate,
            )
            api, active, runtime = self._activate(
                root, storage_adapters={"source-storage": blocking}
            )
            binding = api._prepare_runtime_binding_for_revision(active)
            self.assertIsNotNone(binding.direct_uploads)
            uploads = DirectFileUploadService(
                direct_files=binding.direct_files,
                executor=OrganizerExecutor(),
            )
            write_mock = mock.patch.object(blocking, "write", wraps=blocking.write)
            writes = write_mock.start()
            self.addCleanup(write_mock.stop)
            first_manifest = self._manifest(
                "",
                "no_overwrite",
                [("Movies/same.mkv", b"first")],
            )
            second_manifest = self._manifest(
                "",
                "no_overwrite",
                [
                    ("Movies/same.mkv", b"second"),
                    ("Movies/sibling.mkv", b"sibling"),
                ],
            )
            first_task_id = uploads.upload(resource_library_id="source", manifest=first_manifest)[
                "taskId"
            ]
            second_task_id = uploads.upload(resource_library_id="source", manifest=second_manifest)[
                "taskId"
            ]

            first_results: list[tuple[int, bytes]] = []

            def first_delivery() -> None:
                first_results.append(
                    self._call(api, self._item_environ(first_task_id, 0, b"first"))
                )

            first_thread = threading.Thread(target=first_delivery)
            first_thread.start()
            self.assertTrue(write_started.wait(timeout=5))

            second_status, second_body = self._call(
                api, self._item_environ(second_task_id, 0, b"second")
            )
            self.assertEqual(second_status, 200, second_body)
            second_item = json.loads(second_body)
            self.assertEqual(second_item["status"], "FAILED")
            self.assertEqual(second_item["errorCategory"], "path_locked")
            self.assertEqual(second_item["sideEffects"], "none")
            self.assertIs(second_item["retrySafe"], True)
            self.assertIn("wait", second_item["nextAction"])

            second_rows = {row.source_path: row for row in runtime.list_items(second_task_id)}
            self.assertEqual(second_rows["Movies/same.mkv"].status.value, "failed")
            self.assertEqual(
                second_rows["Movies/same.mkv"].error,
                "source is locked by another active task",
            )
            self.assertEqual(list(runtime.list_results(second_task_id)), [])
            self.assertFalse((root / "source" / "Movies" / "same.mkv").exists())

            gate.set()
            first_thread.join(timeout=5)
            self.assertEqual(len(first_results), 1)
            self.assertEqual(first_results[0][0], 200, first_results[0][1])
            self.assertEqual(json.loads(first_results[0][1])["status"], "SUCCESS")

            sibling_status, sibling_body = self._call(
                api, self._item_environ(second_task_id, 1, b"sibling")
            )
            self.assertEqual(sibling_status, 200, sibling_body)
            self.assertEqual(json.loads(sibling_body)["status"], "SUCCESS")

            second_finish_status, second_finish_body = self._call(
                api, self._finish_environ(second_task_id)
            )
            self.assertEqual(second_finish_status, 200, second_finish_body)
            second_finished = json.loads(second_finish_body)
            self.assertEqual(second_finished["status"], "PARTIAL")
            self.assertEqual(second_finished["failedItems"], 1)
            self.assertEqual(second_finished["succeededItems"], 1)
            self.assertEqual(runtime.get_task(second_task_id).status.value, "partial_success")
            projection = uploads.upload_projection(second_task_id)
            self.assertTrue(projection["terminal"])
            self.assertEqual(projection["status"], "PARTIAL")
            self.assertEqual(projection["failedItems"], 1)
            locked_entry = next(
                entry for entry in projection["items"] if entry["path"] == "Movies/same.mkv"
            )
            self.assertEqual(locked_entry["status"], "FAILED")
            self.assertEqual(
                locked_entry["errorCategory"], "source is locked by another active task"
            )

            first_finished = uploads.finish_upload(first_task_id)
            self.assertEqual(first_finished["status"], "SUCCESS")
            self.assertEqual((root / "source" / "Movies" / "same.mkv").read_bytes(), b"first")
            self.assertEqual(
                (root / "source" / "Movies" / "sibling.mkv").read_bytes(),
                b"sibling",
            )
            self.assertEqual(
                writes.call_count,
                2,
            )
            contested_writes = [
                call for call in writes.call_args_list if str(call.args[0]).endswith("same.mkv")
            ]
            self.assertEqual(len(contested_writes), 1)

    def test_a_concurrent_cancel_at_the_boundary_is_never_a_generic_500(self) -> None:
        """The Task-admission boundary stays bounded under a concurrent cancel.

        A cancel that converges exactly between the item's own checks and the
        durable Task admission must surface as the honest cancelled outcome,
        never as a generic internal error.  The deterministic scheduling point
        is the coordinator's ``begin_item``: the cancel lands while the item
        request is already past every session/Task check.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            api, active, runtime = self._activate(root)
            from mediaflow.application.task_runtime import PersistentTaskCoordinator

            manifest = {
                "destinationDirectory": "",
                "conflict": "no_overwrite",
                "items": [{"relativePath": "Movies/a.mkv", "size": 2}],
            }
            status, body = self._call(api, self._admission_environ(manifest))
            self.assertEqual(status, 202, body)
            task_id = json.loads(body)["taskId"]
            binding = api._prepare_runtime_binding_for_revision(active)
            coordinator = binding.direct_files.tasks
            real_begin = PersistentTaskCoordinator.begin_item
            converged = threading.Event()

            def begin_after_cancel(self, *args, **kwargs):
                # Exactly the window B described: the request already passed
                # its own checks, and the cancellation converges here.
                if not converged.is_set():
                    converged.set()
                    coordinator.cancel(args[0])
                return real_begin(self, *args, **kwargs)

            with mock.patch.object(PersistentTaskCoordinator, "begin_item", begin_after_cancel):
                item_status, item_body = self._call(api, self._item_environ(task_id, 0, b"aa"))
            self.assertTrue(converged.is_set(), "the boundary was never reached")
            self.assertNotEqual(item_status, 500, item_body)
            self.assertEqual(item_status, 200, item_body)
            self.assertEqual(json.loads(item_body)["errorCategory"], "upload_cancelled")
            self.assertFalse((root / "source" / "Movies" / "a.mkv").exists())
            # The session converged to the truthful cancelled truth.
            self.assertEqual(runtime.get_task(task_id).status.value, "cancelled")

    class _GatedOperationLock:
        """Forward to the real lock; the first acquire signals and waits.

        Holding a request at exactly the operation-lock acquisition is the
        deterministic scheduling point B reproduced: the request has already
        resolved the session and the item index but has made no phase, Task,
        order or finalization decision.
        """

        def __init__(self, real: threading.Lock) -> None:
            self._real = real
            self.reached = threading.Event()
            self.gate = threading.Event()
            self._first = True
            self._guard = threading.Lock()

        def acquire(self, blocking: bool = True) -> bool:
            with self._guard:
                first = self._first
                if first:
                    self._first = False
            if first:
                self.reached.set()
                self.gate.wait(timeout=10)
            return self._real.acquire(blocking)

        def release(self) -> None:
            self._real.release()

        def __enter__(self):
            self.acquire()
            return self

        def __exit__(self, *exc: object) -> None:
            self.release()
            return None


class UploadPinnedBindingTests(UploadTestCase):
    """B3: the admitted Upload keeps its pinned Active execution path.

    A session registry above the replaceable runtime binding owns each
    admitted plan and its exact pinned binding, so a normal configuration
    activation between admission, item streaming and finish affects new
    uploads only.
    """

    def _fixture(self, root: Path):
        """One activated revision with its own configuration service/objects."""

        from mediaflow.application.configuration_objects import ConfigurationObjectService
        from mediaflow.application.configuration_snapshot import ManagedConfigurationService
        from mediaflow.infrastructure.sqlite_configuration_management import (
            SQLiteConfigurationRepository,
        )

        document = self._document(root)
        (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
        (root / "destination" / "Movies").mkdir(parents=True, exist_ok=True)
        repository = SQLiteConfigurationRepository(root / "configuration.sqlite3")
        self.addCleanup(repository.close)
        service = ManagedConfigurationService(
            repository, bootstrap_database_path=str(root / "configuration.sqlite3")
        )
        objects = ConfigurationObjectService(
            service,
            storage_browser_cursor_secret="upload-test-secret",
        )
        draft = service.import_draft(document, actor="operator")
        validated = service.validate(draft.revision_id, actor="operator")
        for storage_id in ("source-storage", "media-target"):
            evidence = objects.storage_check(
                validated.revision_id,
                storage_id=storage_id,
                expected_version=validated.version,
                expected_digest=validated.digest,
                actor="operator",
            )
            self.assertEqual(evidence.status, ConfigurationStorageCheckStatus.PASSED)
        strategy = objects.recognition_strategy_test(
            validated.revision_id,
            expected_version=validated.version,
            expected_digest=validated.digest,
            actor="operator",
            resource_library_id="source",
            synthetic_path="Example.Movie.2024.1080p.mkv",
        )
        self.assertEqual(strategy.status, ConfigurationStrategyTestStatus.COMPLETED)
        destination = objects.destination_precheck(
            validated.revision_id,
            expected_version=validated.version,
            expected_digest=validated.digest,
            actor="operator",
            recognition_type="C",
            sample={
                "title": "The Matrix",
                "mediaType": "movie",
                "year": 1999,
                "genres": ["Action"],
                "extension": "mkv",
            },
        )
        self.assertEqual(destination.status, ConfigurationDestinationPrecheckStatus.COMPLETED)
        active = objects.activate_checked(
            validated.revision_id,
            expected_version=validated.version,
            actor="operator",
        )
        return document, service, objects, active

    def _activate_successor(self, root: Path, service, objects, document):
        """Publish one valid successor revision and return its Active row."""
        import copy as copy_module

        candidate = copy_module.deepcopy(document)
        candidate["resourceLibraries"][0]["name"] = "Source Renamed"
        draft = service.import_draft(candidate, actor="operator")
        validated = service.validate(draft.revision_id, actor="operator")
        for storage_id in ("source-storage", "media-target"):
            evidence = objects.storage_check(
                validated.revision_id,
                storage_id=storage_id,
                expected_version=validated.version,
                expected_digest=validated.digest,
                actor="operator",
            )
            self.assertEqual(evidence.status, ConfigurationStorageCheckStatus.PASSED)
        strategy = objects.recognition_strategy_test(
            validated.revision_id,
            expected_version=validated.version,
            expected_digest=validated.digest,
            actor="operator",
            resource_library_id="source",
            synthetic_path="Example.Movie.2024.1080p.mkv",
        )
        self.assertEqual(strategy.status, ConfigurationStrategyTestStatus.COMPLETED)
        destination = objects.destination_precheck(
            validated.revision_id,
            expected_version=validated.version,
            expected_digest=validated.digest,
            actor="operator",
            recognition_type="C",
            sample={
                "title": "The Matrix",
                "mediaType": "movie",
                "year": 1999,
                "genres": ["Action"],
                "extension": "mkv",
            },
        )
        self.assertEqual(destination.status, ConfigurationDestinationPrecheckStatus.COMPLETED)
        return objects.activate_checked(
            validated.revision_id,
            expected_version=validated.version,
            actor="operator",
        )

    def _api(self, root: Path, document, service):
        from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
        from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
        from mediaflow.interfaces.service_api import MediaFlowApi

        runtime = SQLiteTaskRepository(root / "runtime.sqlite3")
        self.addCleanup(runtime.close)
        api = MediaFlowApi(
            runtime,
            None,
            principals=(ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),),
            configuration_service=service,
            bootstrap_document=document,
            storage_browser_cursor_secret="upload-test-secret",
        )
        return api, runtime

    def test_activation_between_admission_items_and_finish_keeps_the_pinned_upload(self) -> None:
        """B's exact reproduction: revision A admitted, revision B activated."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document, service, objects, active = self._fixture(root)
            api, runtime = self._api(root, document, service)
            old_binding = api._prepare_runtime_binding_for_revision(active)
            self.assertIsNotNone(old_binding.direct_uploads)
            uploads = DirectFileUploadService(direct_files=old_binding.direct_files)

            manifest = self._manifest(
                "", "no_overwrite", [("Movies/a.mkv", b"aa"), ("Movies/b.mkv", b"bb")]
            )
            admitted = uploads.upload(resource_library_id="source", manifest=manifest)
            task_id = admitted["taskId"]

            # A valid successor revision becomes Active before the next item
            # request: the admitted Upload keeps its exact revision-A pin.
            successor = self._activate_successor(root, service, objects, document)
            new_binding = api._prepare_runtime_binding_for_revision(successor)
            self.assertIsNotNone(new_binding.direct_uploads)
            self.assertIsNotNone(new_binding.direct_uploads is not uploads)

            # The item request through the NEW binding streams under the
            # OLD pinned session (never files_upload_unknown).
            document_result = uploads.execute_item(task_id, 0, io.BytesIO(b"aa"))
            self.assertEqual(document_result["status"], "SUCCESS", document_result)
            second = uploads.execute_item(task_id, 1, io.BytesIO(b"bb"))
            self.assertEqual(second["status"], "SUCCESS")
            finished = uploads.finish_upload(task_id)
            self.assertEqual(finished["status"], "SUCCESS")
            self.assertEqual((root / "source" / "Movies" / "a.mkv").read_bytes(), b"aa")
            self.assertEqual((root / "source" / "Movies" / "b.mkv").read_bytes(), b"bb")
            self.assertEqual(runtime.get_task(task_id).status.value, "completed")
            # The durable Task names the admission revision, not the new one.
            task = runtime.get_task(task_id)
            self.assertEqual(task.configuration_snapshot_id, active.revision_id)

    def test_a_new_upload_after_activation_uses_the_new_active_revision(self) -> None:
        from mediaflow.application.direct_file_uploads import resume_upload_session

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document, service, objects, active = self._fixture(root)
            api, runtime = self._api(root, document, service)
            old_binding = api._prepare_runtime_binding_for_revision(active)
            old_uploads = DirectFileUploadService(direct_files=old_binding.direct_files)
            # Admit one upload under revision A and pause it (session live).
            admitted = old_uploads.upload(
                resource_library_id="source",
                manifest=self._manifest("", "no_overwrite", [("Movies/a.mkv", b"aa")]),
            )
            task_id = admitted["taskId"]
            old_uploads._direct.tasks.request_pause(task_id)
            paused = old_uploads.execute_item(task_id, 0, io.BytesIO(b"aa"))
            self.assertEqual(paused["status"], "PAUSED")

            # Activate revision B; a new upload goes through the new binding.
            successor = self._activate_successor(root, service, objects, document)
            new_binding = api._prepare_runtime_binding_for_revision(successor)
            new_uploads = DirectFileUploadService(direct_files=new_binding.direct_files)
            new_document = new_uploads.upload(
                resource_library_id="source",
                manifest=self._manifest("", "no_overwrite", [("Movies/c.mkv", b"cc")]),
            )
            new_task_id = new_document["taskId"]
            self.assertNotEqual(new_task_id, task_id)
            item = new_uploads.execute_item(new_task_id, 0, io.BytesIO(b"cc"))
            self.assertEqual(item["status"], "SUCCESS")
            finished = new_uploads.finish_upload(new_task_id)
            self.assertEqual(finished["status"], "SUCCESS")
            self.assertEqual(
                runtime.get_task(new_task_id).configuration_snapshot_id,
                successor.revision_id,
            )
            # The old paused session still resumes and streams under its own pin.
            resume_upload_session(task_id)
            resumed = old_uploads.execute_item(task_id, 0, io.BytesIO(b"aa"))
            self.assertEqual(resumed["status"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()
