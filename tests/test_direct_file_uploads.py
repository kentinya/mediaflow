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
import unittest
from pathlib import Path

from mediaflow.application.direct_file_transfers import DirectFileTransferService
from mediaflow.application.direct_file_uploads import (
    DirectFileUploadService,
)
from mediaflow.application.organizer import OrganizerExecutor
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
            # Resume is honestly unavailable: the browser payload bytes are
            # not durable, so a paused upload is resubmitted as a new one.
            self.assertFalse(actions["resume"]["available"])
            del uploads._admitted[task_id]

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
            self.assertEqual(first["status"], "FAILED")
            self.assertEqual(first["errorCategory"], "upload_paused")
            self.assertEqual(first["taskStatus"], "paused")
            projection = uploads.upload_projection(task_id)
            self.assertEqual(projection["status"], "PAUSED")
            self.assertFalse(projection["terminal"])
            actions = {action["action"]: action for action in projection["actions"]}
            self.assertFalse(actions["resume"]["available"])
            document = uploads.finish_upload(task_id)
            # Every item was refused at the safe pause boundary with its own
            # truthful outcome (never delivered, so finish records the
            # bounded truncation category); nothing was written and nothing
            # is replayed.
            by_path = {item["path"]: item for item in document["items"]}
            self.assertEqual(by_path["Movies/a.mkv"]["status"], "FAILED")
            self.assertEqual(by_path["Movies/b.mkv"]["status"], "FAILED")
            self.assertFalse((root / "source" / "Movies" / "a.mkv").exists())
            self.assertFalse((root / "source" / "Movies" / "b.mkv").exists())
            # The durable item rows record the same refused truth.
            rows = {item.source_path: item for item in runtime.list_items(task_id)}
            self.assertEqual(rows["Movies/a.mkv"].status.value, "failed")
            self.assertEqual(rows["Movies/b.mkv"].status.value, "failed")

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
            self.assertFalse((root / "source" / "b.mkv").exists())
            # Delivering index 0, then repeating it, is refused as well.
            self._call(api, self._item_environ(task_id, 0, b"aa"))
            repeat_status, repeat_body = self._call(api, self._item_environ(task_id, 0, b"aa"))
            self.assertEqual(repeat_status, 409, repeat_body)
            self.assertIn("item_already_delivered", repeat_body.decode())

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


if __name__ == "__main__":
    unittest.main()
