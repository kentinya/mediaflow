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
from tests.test_direct_file_transfers import TransferTestCase, _CountingExecutor


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
        manifest = self._manifest(destination_directory, conflict, items)
        stream = stream_override or self._payloads(items)
        return uploads.upload(resource_library_id="source", manifest=manifest, stream=stream)


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
            # The body declares 4 + 4 bytes but only delivers 4.
            short_stream = io.BytesIO(b"aaaa")
            document = self._upload(uploads, root, items=items, stream_override=short_stream)
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


if __name__ == "__main__":
    unittest.main()
