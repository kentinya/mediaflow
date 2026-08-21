import hashlib
import io
import os
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

from mediaflow.domain.storage import StorageEntryType, StorageError, StorageErrorCode
from mediaflow.infrastructure.local_storage import InvalidStoragePath, LocalStorage


class LocalStorageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.storage = LocalStorage("local", self.root, name="Local media")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def assert_storage_error(
        self, code: StorageErrorCode, function: Callable[..., object], *args: object
    ) -> StorageError:
        with self.assertRaises(StorageError) as raised:
            function(*args)
        self.assertEqual(code, raised.exception.code)
        return raised.exception

    def test_configuration_and_capabilities(self) -> None:
        self.assertEqual(
            ("local", "Local media", False),
            (self.storage.storage_id, self.storage.name, self.storage.read_only),
        )
        capabilities = self.storage.capabilities
        self.assertTrue(capabilities.can_move and capabilities.can_copy and capabilities.can_delete)
        self.assertEqual(hasattr(os, "link"), capabilities.can_hard_link)
        self.assertEqual(hasattr(os, "symlink"), capabilities.can_soft_link)

    def test_list_empty_and_non_recursive_entries(self) -> None:
        self.storage.create_directory("empty")
        self.assertEqual((), self.storage.list("empty"))
        self.storage.create_directory("items/subdirectory")
        self.storage.write("items/movie.mkv", b"movie")
        entries = self.storage.list("items")
        self.assertEqual(["movie.mkv", "subdirectory"], [entry.name for entry in entries])
        self.assertEqual(
            [StorageEntryType.FILE, StorageEntryType.DIRECTORY],
            [entry.entry_type for entry in entries],
        )
        self.assertEqual(
            ["items/movie.mkv", "items/subdirectory"], [entry.path for entry in entries]
        )
        self.assertEqual(5, entries[0].size)
        self.assertIsNotNone(entries[0].modified_at.tzinfo)

    def test_list_errors_are_unified(self) -> None:
        self.storage.write("file", b"content")
        self.assert_storage_error(StorageErrorCode.NOT_FOUND, self.storage.list, "missing")
        self.assert_storage_error(StorageErrorCode.INVALID_PATH, self.storage.list, "file")

    def test_stat_file_directory_and_missing(self) -> None:
        self.storage.create_directory("directory")
        self.storage.write("file", b"content")
        file_entry = self.storage.stat("file")
        directory_entry = self.storage.stat("directory")
        self.assertEqual((StorageEntryType.FILE, 7), (file_entry.entry_type, file_entry.size))
        self.assertIsNotNone(file_entry.modified_at.tzinfo)
        self.assertEqual(StorageEntryType.DIRECTORY, directory_entry.entry_type)
        self.assertTrue(directory_entry.is_directory)
        self.assert_storage_error(StorageErrorCode.NOT_FOUND, self.storage.stat, "missing")

    def test_exists_true_false_and_invalid_path(self) -> None:
        self.storage.write("file", b"content")
        self.assertTrue(self.storage.exists("file"))
        self.assertFalse(self.storage.exists("missing"))
        with self.assertRaises(InvalidStoragePath):
            self.storage.exists("../outside")

    def test_streaming_write_and_read_consistency(self) -> None:
        self.storage.write("movie.mkv", io.BytesIO(b"streamed-media-content"))
        with self.storage.read("movie.mkv") as stream:
            self.assertEqual(b"streamed-media-content", stream.read())
        self.assert_storage_error(StorageErrorCode.NOT_FOUND, self.storage.read, "missing")
        self.assert_storage_error(StorageErrorCode.INVALID_PATH, self.storage.read, "")

    def test_write_requires_existing_parent_and_conflicts(self) -> None:
        self.assert_storage_error(
            StorageErrorCode.NOT_FOUND, self.storage.write, "missing/file", b"x"
        )
        self.storage.write("file", b"first")
        self.assert_storage_error(
            StorageErrorCode.ALREADY_EXISTS, self.storage.write, "file", b"second"
        )
        with self.storage.read("file") as stream:
            self.assertEqual(b"first", stream.read())

    def test_create_directory_behaviors(self) -> None:
        self.storage.create_directory("one/two")
        self.storage.create_directory("one/two")
        self.assertTrue(self.storage.stat("one/two").is_directory)
        self.storage.write("file", b"content")
        self.assert_storage_error(
            StorageErrorCode.ALREADY_EXISTS, self.storage.create_directory, "file"
        )

    def test_copy_integration_and_errors(self) -> None:
        self.storage.create_directory("source")
        self.storage.create_directory("target")
        self.storage.write("source/movie.mkv", b"test-media-content")
        self.storage.copy("source/movie.mkv", "target/movie.mkv")
        self.assertTrue(self.storage.exists("source/movie.mkv"))
        with self.storage.read("target/movie.mkv") as stream:
            self.assertEqual(b"test-media-content", stream.read())
        self.assert_storage_error(
            StorageErrorCode.ALREADY_EXISTS,
            self.storage.copy,
            "source/movie.mkv",
            "target/movie.mkv",
        )
        self.assert_storage_error(
            StorageErrorCode.NOT_FOUND, self.storage.copy, "missing", "target/new"
        )
        self.assert_storage_error(
            StorageErrorCode.PATH_TRAVERSAL,
            self.storage.copy,
            "source/movie.mkv",
            "../outside",
        )

    def test_large_file_copy_is_stream_safe_and_content_matches(self) -> None:
        self.storage.create_directory("source")
        self.storage.create_directory("target")
        block = b"mediaflow-large-file-test" * 4096
        with tempfile.TemporaryFile() as source_stream:
            for _ in range((16 * 1024 * 1024) // len(block) + 1):
                source_stream.write(block)
            source_stream.truncate(16 * 1024 * 1024)
            source_stream.seek(0)
            self.storage.write("source/movie.mkv", source_stream)
        self.storage.copy("source/movie.mkv", "target/movie.mkv")

        def digest(path: str) -> str:
            result = hashlib.sha256()
            with self.storage.read(path) as stream:
                while chunk := stream.read(1024 * 1024):
                    result.update(chunk)
            return result.hexdigest()

        self.assertEqual(16 * 1024 * 1024, self.storage.stat("target/movie.mkv").size)
        self.assertEqual(digest("source/movie.mkv"), digest("target/movie.mkv"))

    def test_move_integration_and_errors(self) -> None:
        self.storage.create_directory("source")
        self.storage.create_directory("target")
        self.storage.write("source/movie.mkv", b"test-media-content")
        self.storage.move("source/movie.mkv", "target/movie.mkv")
        self.assertFalse(self.storage.exists("source/movie.mkv"))
        with self.storage.read("target/movie.mkv") as stream:
            self.assertEqual(b"test-media-content", stream.read())
        self.assert_storage_error(
            StorageErrorCode.NOT_FOUND, self.storage.move, "missing", "target/new"
        )
        self.storage.write("source/new", b"source")
        self.assert_storage_error(
            StorageErrorCode.ALREADY_EXISTS, self.storage.move, "source/new", "target/movie.mkv"
        )
        self.assert_storage_error(
            StorageErrorCode.PATH_TRAVERSAL, self.storage.move, "source/new", "../outside"
        )

    def test_delete_is_non_recursive_and_errors_are_explicit(self) -> None:
        self.storage.write("file", b"content")
        self.storage.delete("file")
        self.storage.create_directory("empty")
        self.storage.delete("empty")
        self.assertFalse(self.storage.exists("file") or self.storage.exists("empty"))
        self.assert_storage_error(StorageErrorCode.NOT_FOUND, self.storage.delete, "missing")
        self.storage.create_directory("nonempty")
        self.storage.write("nonempty/file", b"content")
        self.assert_storage_error(StorageErrorCode.IO_ERROR, self.storage.delete, "nonempty")
        self.assertTrue(self.storage.exists("nonempty/file"))

    def test_hard_link_or_explicitly_unsupported(self) -> None:
        self.storage.write("source", b"content")
        if self.storage.capabilities.can_hard_link:
            self.storage.hard_link("source", "hard")
            self.assertEqual(
                os.stat(self.root / "source").st_ino, os.stat(self.root / "hard").st_ino
            )
            with self.storage.read("hard") as stream:
                self.assertEqual(b"content", stream.read())
            self.assert_storage_error(
                StorageErrorCode.ALREADY_EXISTS, self.storage.hard_link, "source", "hard"
            )
        with patch.object(LocalStorage, "_can_hard_link", return_value=False):
            self.assert_storage_error(
                StorageErrorCode.UNSUPPORTED_OPERATION,
                self.storage.hard_link,
                "source",
                "unsupported-hard",
            )

    def test_soft_link_stat_or_explicitly_unsupported(self) -> None:
        self.storage.write("source", b"content")
        if self.storage.capabilities.can_soft_link:
            self.storage.soft_link("source", "soft")
            self.assertTrue((self.root / "soft").is_symlink())
            self.assertEqual(StorageEntryType.SYMLINK, self.storage.stat("soft").entry_type)
            self.assert_storage_error(
                StorageErrorCode.ALREADY_EXISTS, self.storage.soft_link, "source", "soft"
            )
        with patch.object(LocalStorage, "_can_soft_link", return_value=False):
            self.assert_storage_error(
                StorageErrorCode.UNSUPPORTED_OPERATION,
                self.storage.soft_link,
                "source",
                "unsupported-soft",
            )
        if self.storage.capabilities.can_soft_link:
            self.assert_storage_error(
                StorageErrorCode.NOT_FOUND, self.storage.soft_link, "missing", "missing-soft"
            )

    def test_read_only_allows_reads_and_rejects_every_mutation(self) -> None:
        self.storage.write("source", b"content")
        readonly = LocalStorage("readonly", self.root, read_only=True)
        with readonly.read("source") as stream:
            self.assertEqual(b"content", stream.read())
        self.assertTrue(readonly.exists("source"))
        self.assertEqual(StorageEntryType.FILE, readonly.stat("source").entry_type)
        self.assertEqual(1, len(readonly.list("")))
        self.assertFalse(any(readonly.capabilities.__dict__.values()))
        mutations = (
            (readonly.write, ("new", b"content")),
            (readonly.create_directory, ("directory",)),
            (readonly.copy, ("source", "copy")),
            (readonly.move, ("source", "move")),
            (readonly.delete, ("source",)),
            (readonly.hard_link, ("source", "hard")),
            (readonly.soft_link, ("source", "soft")),
        )
        for function, arguments in mutations:
            with self.subTest(operation=function.__name__):
                self.assert_storage_error(StorageErrorCode.READ_ONLY, function, *arguments)
        self.assertTrue(readonly.exists("source"))

    def test_path_normalization_and_traversal_protection(self) -> None:
        self.storage.create_directory("folder")
        self.storage.write("folder/file", b"content")
        self.assertTrue(self.storage.exists("./folder//file"))
        self.assertTrue(self.storage.exists("folder/sub/../file"))
        dangerous = (
            "../secret.txt",
            "../../etc/passwd",
            "folder/../../../outside",
            "/etc/passwd",
            "C:/Windows/System32",
        )
        for path in dangerous:
            with self.subTest(path=path), self.assertRaises(InvalidStoragePath) as raised:
                self.storage.exists(path)
            expected = (
                StorageErrorCode.INVALID_PATH
                if path.startswith(("/", "C:"))
                else StorageErrorCode.PATH_TRAVERSAL
            )
            self.assertEqual(expected, raised.exception.code)

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links are unavailable")
    def test_symbolic_link_cannot_escape_storage_root(self) -> None:
        with tempfile.TemporaryDirectory() as outside:
            outside_path = Path(outside)
            (outside_path / "secret").write_bytes(b"secret")
            (self.root / "escape").symlink_to(outside_path, target_is_directory=True)
            for operation in (self.storage.exists, self.storage.stat, self.storage.read):
                with (
                    self.subTest(operation=operation.__name__),
                    self.assertRaises(InvalidStoragePath),
                ):
                    operation("escape/secret")

    def test_storage_errors_retain_cause_without_file_content(self) -> None:
        error = self.assert_storage_error(StorageErrorCode.NOT_FOUND, self.storage.stat, "missing")
        self.assertIsInstance(error.cause, FileNotFoundError)
        self.assertNotIn("test-media-content", str(error))

    def test_permission_denied_is_mapped_to_unified_error(self) -> None:
        self.storage.write("file", b"content")
        with patch.object(Path, "open", side_effect=PermissionError("denied")):
            error = self.assert_storage_error(
                StorageErrorCode.PERMISSION_DENIED, self.storage.read, "file"
            )
        self.assertIsInstance(error.cause, PermissionError)
