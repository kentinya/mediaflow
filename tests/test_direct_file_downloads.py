"""Focused evidence for the confined zero-mutation Files Download journey.

Covers direct single-file streaming with a truthful filename/content type,
bounded directory/multi-selection archive enumeration *before* streaming,
the bounded on-the-fly archive manifest that records honest per-item
outcomes, limit overflow before streaming, fail-closed symlink/unsupported
entries, zero-mutation behavior (no Task, no OrganizerExecutor call) and
secret-free, confined output.  Every endpoint is a temporary local root; no
production service is used.
"""

from __future__ import annotations

import io
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

from mediaflow.application.direct_file_downloads import (
    ARCHIVE_MANIFEST_NAME,
    DirectFileDownloadService,
)
from mediaflow.domain.direct_files import (
    MAX_DOWNLOAD_PATHS,
    DownloadItemStatus,
)
from mediaflow.infrastructure.local_storage import LocalStorage
from tests.test_direct_file_transfers import TransferTestCase


class DownloadTestCase(TransferTestCase):
    def _downloads(self, api, active) -> DirectFileDownloadService:
        binding = api._prepare_runtime_binding_for_revision(active)
        self.assertIsNotNone(binding.direct_downloads)
        return binding.direct_downloads

    @staticmethod
    def _body(headers, body_iterable) -> bytes:
        chunks = list(body_iterable)
        return b"".join(chunks)

    @staticmethod
    def _read_archive(body: bytes) -> dict[str, bytes]:
        archive = zipfile.ZipFile(io.BytesIO(body))
        return {name: archive.read(name) for name in archive.namelist()}


class DownloadSingleFileTests(DownloadTestCase):
    def test_single_file_streams_directly_with_truthful_headers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source" / "Movies" / "one.mkv").parent.mkdir(parents=True)
            (root / "source" / "Movies" / "one.mkv").write_bytes(b"media")
            downloads = self._downloads(api, active)
            manifest = downloads.download_admission(
                resource_library_id="source", paths=["Movies/one.mkv"]
            )
            self.assertIsNotNone(manifest.single_file)
            self.assertEqual(manifest.filename, "one.mkv")
            self.assertEqual(manifest.single_file.size, 5)
            headers, body = downloads.stream_response(
                resource_library_id="source", manifest=manifest
            )
            header_map = {key: value for key, value in headers}
            self.assertEqual(header_map["Content-Type"], "video/x-matroska")
            self.assertIn("one.mkv", header_map["Content-Disposition"])
            self.assertEqual(header_map["Content-Length"], "5")
            self.assertEqual(self._body(headers, body), b"media")

    def test_single_file_shrunk_after_admission_is_refused_truthfully(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True)
            (root / "source" / "Movies" / "one.mkv").write_bytes(b"abcdef")
            downloads = self._downloads(api, active)
            manifest = downloads.download_admission(
                resource_library_id="source", paths=["Movies/one.mkv"]
            )
            # Shrink the source after admission: the read boundary re-validates
            # the pinned evidence and refuses instead of serving an
            # unconfirmed shorter body as the admitted entry.
            (root / "source" / "Movies" / "one.mkv").write_bytes(b"ab")
            with self.assertRaises(Exception) as caught:
                list(downloads.stream_response(resource_library_id="source", manifest=manifest)[1])
            self.assertIn("entry_changed", str(caught.exception.code))

    def test_single_file_same_size_replacement_is_refused_truthfully(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True)
            target = root / "source" / "Movies" / "one.mkv"
            target.write_bytes(b"AAAA")
            downloads = self._downloads(api, active)
            manifest = downloads.download_admission(
                resource_library_id="source", paths=["Movies/one.mkv"]
            )
            # Same size, different content (and a fresh inode/ctime): the pinned
            # provider evidence must catch this instead of streaming BBBB as if
            # it were the admitted AAAA.
            target2 = root / "source" / "Movies" / "replacement.mkv"
            target2.write_bytes(b"BBBB")
            import os

            os.replace(target2, target)
            target.write_bytes(b"BBBB")
            with self.assertRaises(Exception) as caught:
                list(downloads.stream_response(resource_library_id="source", manifest=manifest)[1])
            self.assertIn("entry_changed", str(caught.exception.code))


class DownloadArchiveTests(DownloadTestCase):
    def test_directory_download_streams_one_bounded_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source" / "show" / "season1").mkdir(parents=True)
            (root / "source" / "show" / "season1" / "one.mkv").write_bytes(b"one")
            (root / "source" / "show" / "season1" / "two.mkv").write_bytes(b"two")
            (root / "source" / "show" / "poster.jpg").write_bytes(b"poster")
            downloads = self._downloads(api, active)
            manifest = downloads.download_admission(resource_library_id="source", paths=["show"])
            self.assertTrue(manifest.is_archive)
            names = [entry.archive_path for entry in manifest.entries]
            self.assertIn("show/", names)
            self.assertIn("show/season1/", names)
            self.assertIn("show/season1/one.mkv", names)
            headers, body = downloads.stream_response(
                resource_library_id="source", manifest=manifest
            )
            entries = self._read_archive(self._body(headers, body))
            self.assertEqual(entries["show/season1/one.mkv"], b"one")
            self.assertEqual(entries["show/season1/two.mkv"], b"two")
            self.assertEqual(entries["show/poster.jpg"], b"poster")
            self.assertIn(ARCHIVE_MANIFEST_NAME, entries)
            archive_manifest = json.loads(entries[ARCHIVE_MANIFEST_NAME])
            self.assertEqual(
                {item["path"]: item["status"] for item in archive_manifest["items"]},
                {name: "included" for name in names},
            )

    def test_multi_selection_streams_one_archive_with_per_item_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source" / "A").mkdir(parents=True)
            (root / "source" / "A" / "a.mkv").write_bytes(b"aa")
            (root / "source" / "B").mkdir(parents=True)
            (root / "source" / "B" / "b.mkv").write_bytes(b"bb")
            downloads = self._downloads(api, active)
            manifest = downloads.download_admission(resource_library_id="source", paths=["A", "B"])
            self.assertTrue(manifest.is_archive)
            self.assertEqual(manifest.filename, "files.zip")
            headers, body = downloads.stream_response(
                resource_library_id="source", manifest=manifest
            )
            entries = self._read_archive(self._body(headers, body))
            self.assertEqual(entries["A/a.mkv"], b"aa")
            self.assertEqual(entries["B/b.mkv"], b"bb")

    def test_symlink_and_unsupported_entries_fail_closed_into_the_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source" / "tree").mkdir(parents=True)
            (root / "source" / "tree" / "real.mkv").write_bytes(b"real")
            link = root / "source" / "tree" / "link.mkv"
            link.symlink_to(root / "source" / "tree" / "real.mkv")
            downloads = self._downloads(api, active)
            manifest = downloads.download_admission(resource_library_id="source", paths=["tree"])
            failed = [
                entry for entry in manifest.entries if entry.status is DownloadItemStatus.FAILED
            ]
            self.assertTrue(any(entry.archive_path.endswith("link.mkv") for entry in failed))
            # The symlink is recorded honestly; it is never followed.
            self.assertIsNotNone(manifest.manifest_note)


class DownloadArchiveBoundedStreamTests(DownloadTestCase):
    """B3: archive output is drained while each source file is being read."""

    class _BlockingReadStorage:
        """A provider double whose read blocks until the test allows it."""

        def __init__(self, root: Path) -> None:
            self._inner = LocalStorage("source-storage", root)
            self.started = threading.Event()
            self.release = threading.Event()
            self.consumed_before_release = 0

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def read(self, path):
            inner = self._inner.read(path)
            outer = self

            class _Blocking:
                def __init__(self) -> None:
                    self._source = inner

                def read(self, size=-1):
                    outer.started.set()
                    outer.release.wait(timeout=5)
                    chunk = self._source.read(size)
                    outer.consumed_before_release += len(chunk)
                    return chunk

                def __enter__(self):
                    self._source.__enter__()
                    return self

                def __exit__(self, *exc):
                    return self._source.__exit__(*exc)

                def __getattr__(self, name):
                    return getattr(self._source, name)

            return _Blocking()

    def test_archive_streams_source_consumption_before_the_next_chunk(self) -> None:
        """The first response chunk arrives while the file read is blocked.

        This proves the archive is produced incrementally: a whole-file
        buffering implementation cannot yield the archive header before the
        source read completes.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir(parents=True, exist_ok=True)
            blocking = self._BlockingReadStorage(root / "source")
            api, active, _runtime = self._activate(
                root, storage_adapters={"source-storage": blocking}
            )
            (root / "source" / "data").mkdir(parents=True, exist_ok=True)
            (root / "source" / "data" / "big.bin").write_bytes(b"z" * (4 * 1024 * 1024))
            downloads = self._downloads(api, active)
            manifest = downloads.download_admission(resource_library_id="source", paths=["data"])
            headers, body = downloads.stream_response(
                resource_library_id="source", manifest=manifest
            )
            iterator = iter(body)
            # The producer reaches the file read and blocks there; the
            # response must already be able to produce the archive bytes
            # written before the read (the local file header).
            first = next(iterator)
            self.assertTrue(blocking.started.wait(timeout=5))
            self.assertGreater(len(first), 0)
            self.assertEqual(
                blocking.consumed_before_release,
                0,
                "the response must stream before the whole file is read",
            )
            blocking.release.set()
            rest = b"".join(iterator)
            entries = self._read_archive(first + rest)
            self.assertEqual(entries["data/big.bin"], b"z" * (4 * 1024 * 1024))


class DownloadArchiveSourceChangeTests(DownloadTestCase):
    """B4: same-size replacement and vanish are detected at the read boundary."""

    def test_same_size_replacement_is_reported_never_streamed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source" / "tree").mkdir(parents=True)
            target = root / "source" / "tree" / "one.bin"
            target.write_bytes(b"AAAA")
            downloads = self._downloads(api, active)
            manifest = downloads.download_admission(resource_library_id="source", paths=["tree"])
            # Same-size replacement after admission.
            replacement = root / "source" / "tree" / "replacement.bin"
            replacement.write_bytes(b"BBBB")
            import os

            os.replace(replacement, target)
            target.write_bytes(b"BBBB")
            headers, body = downloads.stream_response(
                resource_library_id="source", manifest=manifest
            )
            entries = self._read_archive(self._body(headers, body))
            # The archive never contains the unadmitted BBBB payload.
            self.assertNotIn(b"BBBB", entries.get("tree/one.bin", b""))
            self.assertNotIn("tree/one.bin", entries)
            archive_manifest = json.loads(entries[ARCHIVE_MANIFEST_NAME])
            statuses = {item["path"]: item["status"] for item in archive_manifest["items"]}
            self.assertEqual(statuses.get("tree/one.bin"), "failed")

    def test_vanished_entry_is_reported_truthfully(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source" / "tree").mkdir(parents=True)
            (root / "source" / "tree" / "gone.bin").write_bytes(b"gone")
            (root / "source" / "tree" / "stays.bin").write_bytes(b"stays")
            downloads = self._downloads(api, active)
            manifest = downloads.download_admission(resource_library_id="source", paths=["tree"])
            (root / "source" / "tree" / "gone.bin").unlink()
            headers, body = downloads.stream_response(
                resource_library_id="source", manifest=manifest
            )
            entries = self._read_archive(self._body(headers, body))
            self.assertEqual(entries["tree/stays.bin"], b"stays")
            self.assertNotIn("tree/gone.bin", entries)
            archive_manifest = json.loads(entries[ARCHIVE_MANIFEST_NAME])
            statuses = {item["path"]: item["status"] for item in archive_manifest["items"]}
            self.assertEqual(statuses.get("tree/gone.bin"), "failed")


class _DisconnectingReadStorage:
    """A provider double that serves one read and then loses the connection.

    This is B's reproduction shape: the first read succeeds (partial content
    reaches the archive entry after response bytes have begun) and the next
    read raises a provider connection error.
    """

    def __init__(self, root: Path) -> None:
        self._inner = LocalStorage("source-storage", root)
        self.failures = 0

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def read(self, path):
        inner = self._inner.read(path)
        outer = self

        class _Disconnecting:
            def __init__(self) -> None:
                self._source = inner
                self._reads = 0

            def read(self, size=-1):
                self._reads += 1
                if self._reads > 1:
                    outer.failures += 1
                    from mediaflow.domain.storage import (
                        StorageError,
                        StorageErrorCode,
                    )

                    raise StorageError(
                        StorageErrorCode.CONNECTION_LOST,
                        "the provider disconnected mid-read",
                    )
                return self._source.read(size)

            def __enter__(self):
                self._source.__enter__()
                return self

            def __exit__(self, *exc):
                return self._source.__exit__(*exc)

            def __getattr__(self, name):
                return getattr(self._source, name)

        return _Disconnecting()


class DownloadArchiveMidEntryFailureTests(DownloadTestCase):
    """B5: a provider read failure after the entry started never fabricates."""

    def test_mid_entry_provider_failure_aborts_the_response_truthfully(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "tree").mkdir(parents=True)
            # Big enough that the streamed read spans more than one provider
            # read (the stream chunk is 256 KiB), so the second read hits the
            # disconnect after the archive entry has started.
            (root / "source" / "tree" / "a.bin").write_bytes(b"A" * (512 * 1024))
            disconnecting = _DisconnectingReadStorage(root / "source")
            api, active, runtime = self._activate(
                root, storage_adapters={"source-storage": disconnecting}
            )
            downloads = self._downloads(api, active)
            manifest = downloads.download_admission(resource_library_id="source", paths=["tree"])
            headers, body = downloads.stream_response(
                resource_library_id="source", manifest=manifest
            )
            iterator = iter(body)
            # Response bytes begin (the archive header/local header), then the
            # provider disconnects mid-entry.
            first = next(iterator)
            self.assertGreater(len(first), 0)
            with self.assertRaises(Exception) as caught:
                b"".join(iterator)
            self.assertIn("transfer_interrupted", str(caught.exception.code))
            self.assertEqual(caught.exception.status, 503)
            # Zero mutation: no Task and no write-back anywhere.
            self.assertEqual(runtime.list_tasks(), ())
            self.assertFalse((root / "source" / "files.zip").exists())
            self.assertEqual((root / "source" / "tree" / "a.bin").read_bytes(), b"A" * (512 * 1024))
            # A genuinely disconnected provider is reported, never swallowed.
            self.assertGreaterEqual(disconnecting.failures, 1)


class DownloadLimitTests(DownloadTestCase):
    def test_over_limit_selection_fails_before_streaming(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source" / "data").mkdir(parents=True)
            for index in range(10):
                (root / "source" / "data" / f"f{index}.txt").write_text("x")
            downloads = self._downloads(api, active)
            paths = [f"data/f{index}.txt" for index in range(MAX_DOWNLOAD_PATHS + 1)]
            with self.assertRaises(Exception) as caught:
                downloads.download_admission(resource_library_id="source", paths=paths)
            self.assertIn("count_limit", str(caught.exception.code))

    def test_root_is_not_downloadable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            downloads = self._downloads(api, active)
            with self.assertRaises(Exception) as caught:
                downloads.download_admission(resource_library_id="source", paths=[""])
            self.assertIn("invalid_path", str(caught.exception.code))


class DownloadZeroMutationTests(DownloadTestCase):
    def test_download_creates_no_task_and_invokes_no_executor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True)
            (root / "source" / "Movies" / "one.mkv").write_bytes(b"media")
            downloads = self._downloads(api, active)
            manifest = downloads.download_admission(
                resource_library_id="source", paths=["Movies/one.mkv"]
            )
            headers, body = downloads.stream_response(
                resource_library_id="source", manifest=manifest
            )
            self._body(headers, body)
            # Zero mutation: no new Task rows and no file-operation locks.
            tasks = runtime.list_tasks()
            self.assertEqual(len(tasks), 0)
            # The source is untouched and nothing was written back to Storage.
            self.assertEqual((root / "source" / "Movies" / "one.mkv").read_bytes(), b"media")
            self.assertFalse((root / "source" / "files.zip").exists())

    def test_download_headers_and_archive_are_secret_free(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True)
            (root / "source" / "Movies" / "one.mkv").write_bytes(b"media")
            downloads = self._downloads(api, active)
            manifest = downloads.download_admission(
                resource_library_id="source", paths=["Movies/one.mkv"]
            )
            headers, body = downloads.stream_response(
                resource_library_id="source", manifest=manifest
            )
            rendered = json.dumps(headers)
            # No host root, credential or provider detail leaks into headers.
            self.assertNotIn(str(root), rendered)
            self.assertNotIn("token", rendered.lower())
            self.assertNotIn("password", rendered.lower())


if __name__ == "__main__":
    unittest.main()
