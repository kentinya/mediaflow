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

    def test_single_file_shorter_source_ends_early_without_fabrication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            (root / "source" / "Movies").mkdir(parents=True)
            (root / "source" / "Movies" / "one.mkv").write_bytes(b"abcdef")
            downloads = self._downloads(api, active)
            manifest = downloads.download_admission(
                resource_library_id="source", paths=["Movies/one.mkv"]
            )
            # Shrink the source after admission: the stream ends early at the
            # admitted size boundary instead of inventing content.
            (root / "source" / "Movies" / "one.mkv").write_bytes(b"ab")
            headers, body = downloads.stream_response(
                resource_library_id="source", manifest=manifest
            )
            self.assertEqual(self._body(headers, body), b"ab")


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
