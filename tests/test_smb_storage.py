import errno
import io
import threading
import unittest
from collections.abc import Sequence
from datetime import UTC, datetime

from mediaflow.domain.storage import StorageEntryType, StorageError, StorageErrorCode
from mediaflow.infrastructure.smb_storage import (
    SMBClientEntry,
    SMBClientError,
    SMBClientErrorKind,
    SmbProtocolClient,
    SMBStorage,
    SMBStorageConfig,
)


class CommitBuffer(io.BytesIO):
    def __init__(self, commit: object) -> None:
        super().__init__()
        self._commit = commit

    def close(self) -> None:
        if not self.closed:
            self._commit(self.getvalue())  # type: ignore[operator]
        super().close()


class StreamingBuffer(io.BytesIO):
    def read(self, size: int = -1) -> bytes:
        if size < 0:
            raise AssertionError("whole-file reads are forbidden")
        return super().read(size)


class FakeSMBClient:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.directories = {"", "root"}
        self.failures: dict[str, list[SMBClientErrorKind]] = {}
        self.connect_calls = 0
        self.close_calls = 0
        self.connected = False
        self.received_config: SMBStorageConfig | None = None
        self.max_active = 0
        self._active = 0
        self._lock = threading.Lock()
        self.block_stat: threading.Event | None = None

    def fail(self, operation: str, *kinds: SMBClientErrorKind) -> None:
        self.failures[operation] = list(kinds)

    def _maybe_fail(self, operation: str) -> None:
        failures = self.failures.get(operation, [])
        if failures:
            kind = failures.pop(0)
            raise SMBClientError(kind, f"fake {operation} failed")

    def connect(self, config: SMBStorageConfig) -> None:
        self.connect_calls += 1
        self.received_config = config
        self._maybe_fail("connect")
        self.connected = True

    def close(self) -> None:
        self.close_calls += 1
        self.connected = False

    def list(self, path: str) -> Sequence[SMBClientEntry]:
        self._maybe_fail("list")
        if path not in self.directories:
            raise SMBClientError(SMBClientErrorKind.NOT_FOUND, "missing directory")
        prefix = f"{path}/" if path else ""
        entries: list[SMBClientEntry] = []
        for directory in self.directories:
            remainder = directory.removeprefix(prefix)
            if directory != path and directory.startswith(prefix) and "/" not in remainder:
                entries.append(self._entry(directory, StorageEntryType.DIRECTORY, 0))
        for file_path, content in self.files.items():
            remainder = file_path.removeprefix(prefix)
            if file_path.startswith(prefix) and "/" not in remainder:
                entries.append(self._entry(file_path, StorageEntryType.FILE, len(content)))
        return sorted(entries, key=lambda entry: entry.name)

    def stat(self, path: str) -> SMBClientEntry:
        if self.block_stat is not None:
            self.block_stat.wait()
        self._maybe_fail("stat")
        if path in self.files:
            return self._entry(path, StorageEntryType.FILE, len(self.files[path]))
        if path in self.directories:
            return self._entry(path, StorageEntryType.DIRECTORY, 0)
        raise SMBClientError(SMBClientErrorKind.NOT_FOUND, "missing path")

    def open_read(self, path: str) -> io.BytesIO:
        self._maybe_fail("read")
        if path not in self.files:
            raise SMBClientError(SMBClientErrorKind.NOT_FOUND, "missing file")
        return StreamingBuffer(self.files[path])

    def open_write(self, path: str, *, overwrite: bool) -> CommitBuffer:
        self._maybe_fail("write")
        if path in self.files and not overwrite:
            raise SMBClientError(SMBClientErrorKind.ALREADY_EXISTS, "target exists")
        parent = path.rpartition("/")[0]
        if parent not in self.directories:
            raise SMBClientError(SMBClientErrorKind.NOT_FOUND, "missing parent")
        return CommitBuffer(lambda content: self.files.__setitem__(path, content))

    def create_directory(self, path: str) -> None:
        self._maybe_fail("mkdir")
        if path in self.files:
            raise SMBClientError(SMBClientErrorKind.ALREADY_EXISTS, "file exists")
        parts = path.split("/")
        for index in range(1, len(parts) + 1):
            self.directories.add("/".join(parts[:index]))

    def move(self, source: str, target: str, *, overwrite: bool) -> None:
        self._maybe_fail("move")
        if source not in self.files:
            raise SMBClientError(SMBClientErrorKind.NOT_FOUND, "source missing")
        if target in self.files and not overwrite:
            raise SMBClientError(SMBClientErrorKind.ALREADY_EXISTS, "target exists")
        self.files[target] = self.files.pop(source)

    def delete(self, path: str, *, directory: bool) -> None:
        self._maybe_fail("delete")
        if directory:
            prefix = f"{path}/"
            children = set(self.files) | self.directories
            if any(item.startswith(prefix) for item in children):
                raise SMBClientError(SMBClientErrorKind.IO_ERROR, "directory not empty")
            if path not in self.directories:
                raise SMBClientError(SMBClientErrorKind.NOT_FOUND, "missing directory")
            self.directories.remove(path)
        elif path in self.files:
            del self.files[path]
        else:
            raise SMBClientError(SMBClientErrorKind.NOT_FOUND, "missing file")

    @staticmethod
    def _entry(path: str, entry_type: StorageEntryType, size: int) -> SMBClientEntry:
        return SMBClientEntry(path.rpartition("/")[2], path, entry_type, size, datetime.now(UTC))


class SMBStorageTest(unittest.TestCase):
    password = "never-log-this-password"

    def setUp(self) -> None:
        self.client = FakeSMBClient()
        self.config = SMBStorageConfig(
            "smb",
            "NAS",
            "nas.example.test",
            "Media",
            "user",
            self.password,
            domain="DOMAIN",
            root_path="root",
            connect_timeout=2,
            operation_timeout=3,
            max_concurrency=2,
        )
        self.storage = SMBStorage(self.config, self.client)

    def assert_error(
        self, code: StorageErrorCode, function: object, *arguments: object
    ) -> StorageError:
        with self.assertRaises(StorageError) as raised:
            function(*arguments)  # type: ignore[operator]
        self.assertEqual(code, raised.exception.code)
        self.assertNotIn(self.password, str(raised.exception))
        return raised.exception

    def test_configuration_secret_and_connection_lifecycle(self) -> None:
        self.assertNotIn(self.password, repr(self.config))
        self.assertIn("********", repr(self.config))
        with self.storage:
            self.assertTrue(self.client.connected)
            self.storage.exists("missing")
        self.assertEqual((1, 1), (self.client.connect_calls, self.client.close_calls))
        self.assertEqual((2, 3, 2), (self.config.connect_timeout, self.config.operation_timeout, 2))

    def test_connection_authentication_and_timeout_errors(self) -> None:
        cases = (
            (SMBClientErrorKind.CONNECTION_FAILED, StorageErrorCode.CONNECTION_FAILED),
            (SMBClientErrorKind.AUTHENTICATION_FAILED, StorageErrorCode.AUTHENTICATION_FAILED),
            (SMBClientErrorKind.TIMEOUT, StorageErrorCode.TIMEOUT),
        )
        for client_code, storage_code in cases:
            with self.subTest(code=client_code):
                client = FakeSMBClient()
                client.fail("connect", client_code)
                self.assert_error(storage_code, SMBStorage(self.config, client).connect)

    def test_operation_timeout_is_enforced(self) -> None:
        client = FakeSMBClient()
        client.block_stat = threading.Event()
        config = SMBStorageConfig(
            "timeout",
            "Timeout",
            "host",
            "share",
            "user",
            "secret",
            operation_timeout=0.02,
        )
        storage = SMBStorage(config, client)
        self.assert_error(StorageErrorCode.TIMEOUT, storage.stat, "file")
        self.assertEqual(1, client.close_calls)

    def test_idempotent_operation_reconnects_once(self) -> None:
        self.client.files["root/movie.mkv"] = b"content"
        self.client.fail("stat", SMBClientErrorKind.CONNECTION_LOST)
        self.assertTrue(self.storage.exists("movie.mkv"))
        self.assertEqual((2, 1), (self.client.connect_calls, self.client.close_calls))

    def test_mutating_operation_is_not_retried(self) -> None:
        self.client.fail("write", SMBClientErrorKind.CONNECTION_LOST)
        self.assert_error(StorageErrorCode.CONNECTION_LOST, self.storage.write, "movie.mkv", b"x")
        self.assertEqual(1, self.client.connect_calls)

    def test_list_empty_files_directories_and_errors(self) -> None:
        self.assertEqual((), self.storage.list(""))
        self.client.files["root/movie.mkv"] = b"movie"
        self.client.directories.add("root/folder")
        entries = self.storage.list("")
        self.assertEqual(["folder", "movie.mkv"], [entry.name for entry in entries])
        self.assertEqual(
            [StorageEntryType.DIRECTORY, StorageEntryType.FILE],
            [entry.entry_type for entry in entries],
        )
        self.assertEqual(["folder", "movie.mkv"], [entry.path for entry in entries])
        self.assert_error(StorageErrorCode.NOT_FOUND, self.storage.list, "missing")
        self.client.fail("list", SMBClientErrorKind.PERMISSION_DENIED)
        self.assert_error(StorageErrorCode.PERMISSION_DENIED, self.storage.list, "")

    def test_stat_and_exists(self) -> None:
        self.client.files["root/movie.mkv"] = b"movie"
        entry = self.storage.stat("movie.mkv")
        self.assertEqual(
            ("movie.mkv", 5, StorageEntryType.FILE), (entry.path, entry.size, entry.entry_type)
        )
        self.assertTrue(self.storage.exists("movie.mkv"))
        self.assertFalse(self.storage.exists("missing"))
        self.client.fail("stat", SMBClientErrorKind.CONNECTION_FAILED)
        self.assert_error(StorageErrorCode.CONNECTION_FAILED, self.storage.exists, "movie.mkv")

    def test_read_write_streaming_conflict_and_errors(self) -> None:
        source = StreamingBuffer(b"test-media-content")
        self.storage.write("movie.mkv", source)
        with self.storage.read("movie.mkv") as stream:
            self.assertEqual(b"test-media-content", stream.read(1024))
        self.assert_error(StorageErrorCode.ALREADY_EXISTS, self.storage.write, "movie.mkv", b"new")
        self.assert_error(StorageErrorCode.NOT_FOUND, self.storage.read, "missing")
        self.client.fail("read", SMBClientErrorKind.PERMISSION_DENIED)
        self.assert_error(StorageErrorCode.PERMISSION_DENIED, self.storage.read, "movie.mkv")

    def test_create_directory_recursive_idempotent_and_conflict(self) -> None:
        self.storage.create_directory("a/b")
        self.storage.create_directory("a/b")
        self.assertTrue(self.storage.exists("a/b"))
        self.client.files["root/file"] = b"x"
        self.assert_error(StorageErrorCode.ALREADY_EXISTS, self.storage.create_directory, "file")

    def test_copy_is_streamed_preserves_source_and_conflicts(self) -> None:
        self.client.files["root/source.mkv"] = b"media" * 1000
        self.storage.copy("source.mkv", "copy.mkv")
        self.assertEqual(self.client.files["root/source.mkv"], self.client.files["root/copy.mkv"])
        self.assert_error(
            StorageErrorCode.ALREADY_EXISTS, self.storage.copy, "source.mkv", "copy.mkv"
        )
        self.assert_error(StorageErrorCode.NOT_FOUND, self.storage.copy, "missing", "new.mkv")

    def test_move_is_native_preserves_content_and_conflicts(self) -> None:
        self.client.files["root/source.mkv"] = b"media"
        self.storage.move("source.mkv", "target.mkv")
        self.assertNotIn("root/source.mkv", self.client.files)
        self.assertEqual(b"media", self.client.files["root/target.mkv"])
        self.client.files["root/source.mkv"] = b"again"
        self.assert_error(
            StorageErrorCode.ALREADY_EXISTS, self.storage.move, "source.mkv", "target.mkv"
        )
        self.assert_error(StorageErrorCode.NOT_FOUND, self.storage.move, "missing", "new.mkv")

    def test_delete_file_empty_directory_and_nonempty_safety(self) -> None:
        self.client.files["root/file"] = b"x"
        self.storage.delete("file")
        self.client.directories.add("root/empty")
        self.storage.delete("empty")
        self.client.directories.add("root/nonempty")
        self.client.files["root/nonempty/file"] = b"x"
        self.assert_error(StorageErrorCode.IO_ERROR, self.storage.delete, "nonempty")
        self.assert_error(StorageErrorCode.NOT_FOUND, self.storage.delete, "missing")

    def test_read_only_blocks_before_connect(self) -> None:
        self.client.files["source"] = b"content"
        readonly = SMBStorage(
            SMBStorageConfig("ro", "Read only", "host", "share", "user", "secret", read_only=True),
            self.client,
        )
        self.assertIn("source", [entry.name for entry in readonly.list("")])
        self.assertTrue(readonly.exists("source"))
        self.assertEqual(StorageEntryType.FILE, readonly.stat("source").entry_type)
        with readonly.read("source") as stream:
            self.assertEqual(b"content", stream.read(1024))
        connect_calls_before_mutations = self.client.connect_calls
        mutations = (
            (readonly.write, ("file", b"x")),
            (readonly.create_directory, ("dir",)),
            (readonly.copy, ("a", "b")),
            (readonly.move, ("a", "b")),
            (readonly.delete, ("a",)),
            (readonly.hard_link, ("a", "b")),
            (readonly.soft_link, ("a", "b")),
        )
        for function, arguments in mutations:
            with self.subTest(operation=function.__name__):
                self.assert_error(StorageErrorCode.READ_ONLY, function, *arguments)
        self.assertEqual(connect_calls_before_mutations, self.client.connect_calls)

    def test_capabilities_and_unsupported_links(self) -> None:
        capabilities = self.storage.capabilities
        self.assertEqual((True, True, True, False, False), tuple(capabilities.__dict__.values()))
        self.assert_error(StorageErrorCode.UNSUPPORTED_OPERATION, self.storage.hard_link, "a", "b")
        self.assert_error(StorageErrorCode.UNSUPPORTED_OPERATION, self.storage.soft_link, "a", "b")
        self.assertEqual(0, self.client.connect_calls)

    def test_root_mapping_and_path_security(self) -> None:
        self.client.files["root/folder/movie.mkv"] = b"movie"
        self.assertTrue(self.storage.exists("folder/movie.mkv"))
        dangerous = (
            "../outside",
            "../../outside",
            "folder/../../../outside",
            r"\\server\other-share\file",
            "/absolute/file",
            "C:/absolute/file",
        )
        for path in dangerous:
            with self.subTest(path=path):
                expected = (
                    StorageErrorCode.INVALID_PATH
                    if path.startswith(("/", "\\", "C:"))
                    else StorageErrorCode.PATH_TRAVERSAL
                )
                self.assert_error(expected, self.storage.exists, path)

    def test_all_network_error_codes_map_without_secret_leakage(self) -> None:
        cases = (
            SMBClientErrorKind.PERMISSION_DENIED,
            SMBClientErrorKind.ALREADY_EXISTS,
            SMBClientErrorKind.TIMEOUT,
            SMBClientErrorKind.IO_ERROR,
            SMBClientErrorKind.UNKNOWN,
        )
        for kind in cases:
            with self.subTest(kind=kind):
                client = FakeSMBClient()
                client.fail("stat", kind)
                storage = SMBStorage(self.config, client)
                expected = StorageErrorCode(kind.value)
                self.assert_error(expected, storage.stat, "file")

    def test_smbprotocol_client_maps_structured_errno_values(self) -> None:
        cases = (
            (errno.ENOENT, SMBClientErrorKind.NOT_FOUND),
            (errno.EEXIST, SMBClientErrorKind.ALREADY_EXISTS),
            (errno.EACCES, SMBClientErrorKind.PERMISSION_DENIED),
            (errno.EPERM, SMBClientErrorKind.PERMISSION_DENIED),
            (errno.ETIMEDOUT, SMBClientErrorKind.TIMEOUT),
            (errno.ECONNRESET, SMBClientErrorKind.CONNECTION_LOST),
            (errno.ECONNREFUSED, SMBClientErrorKind.CONNECTION_FAILED),
        )
        for error_number, expected in cases:
            with self.subTest(error_number=error_number):
                converted = SmbProtocolClient._convert_error(OSError(error_number, "synthetic"))
                self.assertEqual(expected, converted.kind)
                self.assertNotIn("synthetic", str(converted))

        unknown = SmbProtocolClient._convert_error(OSError(errno.EINVAL, "synthetic"))
        self.assertEqual(SMBClientErrorKind.IO_ERROR, unknown.kind)

    def test_smbprotocol_list_entry_uses_scandir_metadata_without_stat(self) -> None:
        modified = datetime(2026, 8, 22, 12, 30, tzinfo=UTC)

        class Info:
            end_of_file = 42
            last_write_time = modified

        class Entry:
            name = "movie.mkv"
            smb_info = Info()

            @staticmethod
            def is_symlink() -> bool:
                return False

            @staticmethod
            def is_dir() -> bool:
                return False

            @staticmethod
            def stat() -> object:
                raise AssertionError("scandir metadata must avoid a second SMB stat request")

        converted = SmbProtocolClient._entry("folder", Entry())
        self.assertEqual("folder/movie.mkv", converted.path)
        self.assertEqual(42, converted.size)
        self.assertEqual(modified, converted.modified_at)

    def test_client_error_message_cannot_leak_password(self) -> None:
        self.storage.connect()

        def leaking_stat(_: str) -> SMBClientEntry:
            raise SMBClientError(
                SMBClientErrorKind.AUTHENTICATION_FAILED,
                f"bad credential {self.password}",
            )

        self.client.stat = leaking_stat  # type: ignore[method-assign]
        self.assert_error(StorageErrorCode.AUTHENTICATION_FAILED, self.storage.stat, "file")

    def test_read_stream_holds_concurrency_permit_until_closed(self) -> None:
        for name in ("a", "b", "c"):
            self.client.files[f"root/{name}"] = name.encode()
        first = self.storage.read("a")
        second = self.storage.read("b")
        third_opened = threading.Event()

        def open_third() -> None:
            with self.storage.read("c"):
                third_opened.set()

        thread = threading.Thread(target=open_third)
        thread.start()
        self.assertFalse(third_opened.wait(0.05))
        first.close()
        self.assertTrue(third_opened.wait(1))
        second.close()
        thread.join(timeout=1)
        self.assertFalse(thread.is_alive())
