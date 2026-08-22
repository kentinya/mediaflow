from __future__ import annotations

import io
import unittest
from datetime import UTC, datetime

from mediaflow.domain.storage import StorageEntryType, StorageError, StorageErrorCode
from mediaflow.infrastructure.openlist_storage import (
    HttpOpenListClient,
    OpenListClientEntry,
    OpenListClientError,
    OpenListClientErrorKind,
    OpenListPage,
    OpenListStorage,
    OpenListStorageConfig,
)

NOW = datetime(2026, 8, 19, tzinfo=UTC)


class FakeOpenListClient:
    def __init__(self) -> None:
        self.entries: dict[str, OpenListClientEntry] = {
            "/Downloads": self.entry("Downloads", True),
        }
        self.contents: dict[str, bytes] = {}
        self.calls: list[tuple[object, ...]] = []
        self.failure: OpenListClientError | None = None
        self.repeat_failure = False
        self.page_calls: list[int] = []

    @staticmethod
    def entry(name: str, directory: bool = False, size: int = 0) -> OpenListClientEntry:
        return OpenListClientEntry(name, name, directory, size, NOW)

    def _fail(self) -> None:
        if self.failure:
            error = self.failure
            if not self.repeat_failure:
                self.failure = None
            raise error

    def health(self) -> None:
        self.calls.append(("health",))
        self._fail()

    def list_page(self, path: str, page: int, per_page: int) -> OpenListPage:
        self.calls.append(("list", path, page, per_page))
        self.page_calls.append(page)
        self._fail()
        prefix = path.rstrip("/") + "/"
        children = [
            value
            for key, value in sorted(self.entries.items())
            if key.startswith(prefix) and "/" not in key[len(prefix) :]
        ]
        start = (page - 1) * per_page
        return OpenListPage(children[start : start + per_page], len(children))

    def stat(self, path: str) -> OpenListClientEntry:
        self.calls.append(("stat", path))
        self._fail()
        try:
            return self.entries[path]
        except KeyError as error:
            raise OpenListClientError(OpenListClientErrorKind.NOT_FOUND) from error

    def open_read(self, path: str):
        self.calls.append(("read", path))
        self._fail()
        if path not in self.contents:
            raise OpenListClientError(OpenListClientErrorKind.NOT_FOUND)
        return io.BytesIO(self.contents[path])

    def upload(self, path: str, data, *, overwrite: bool) -> None:
        self.calls.append(("write", path, overwrite))
        self._fail()
        if path in self.entries and not overwrite:
            raise OpenListClientError(OpenListClientErrorKind.ALREADY_EXISTS)
        parent = str(path.rsplit("/", 1)[0])
        if parent not in self.entries:
            raise OpenListClientError(OpenListClientErrorKind.NOT_FOUND)
        if isinstance(data, bytes | bytearray | memoryview):
            payload = bytes(data)
        else:
            chunks = []
            while chunk := data.read(1024 * 1024):
                chunks.append(chunk)
            payload = b"".join(chunks)
        self.contents[path] = payload
        self.entries[path] = self.entry(path.rsplit("/", 1)[-1], size=len(payload))

    def create_directory(self, path: str) -> None:
        self.calls.append(("mkdir", path))
        self._fail()
        if path in self.entries:
            raise OpenListClientError(OpenListClientErrorKind.ALREADY_EXISTS)
        self.entries[path] = self.entry(path.rsplit("/", 1)[-1], True)

    def rename(self, path: str, name: str, *, overwrite: bool) -> None:
        self.move(path, f"{path.rsplit('/', 1)[0]}/{name}", overwrite=overwrite)

    def move(self, source: str, target: str, *, overwrite: bool) -> None:
        self.calls.append(("move", source, target, overwrite))
        self._fail()
        if target in self.entries and not overwrite:
            raise OpenListClientError(OpenListClientErrorKind.ALREADY_EXISTS)
        if source not in self.entries:
            raise OpenListClientError(OpenListClientErrorKind.NOT_FOUND)
        self.entries[target] = self.entries.pop(source)
        if source in self.contents:
            self.contents[target] = self.contents.pop(source)

    def copy(self, source: str, target: str, *, overwrite: bool) -> None:
        self.calls.append(("copy", source, target, overwrite))
        self._fail()
        if target in self.entries and not overwrite:
            raise OpenListClientError(OpenListClientErrorKind.ALREADY_EXISTS)
        if source not in self.entries:
            raise OpenListClientError(OpenListClientErrorKind.NOT_FOUND)
        self.entries[target] = self.entries[source]
        if source in self.contents:
            self.contents[target] = self.contents[source]

    def delete(self, path: str) -> None:
        self.calls.append(("delete", path))
        self._fail()
        del self.entries[path]
        self.contents.pop(path, None)

    def close(self) -> None:
        self.calls.append(("close",))


class OpenListStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = FakeOpenListClient()
        self.config = OpenListStorageConfig(
            "openlist", "OpenList", "https://openlist.invalid", "top-secret", root_path="/Downloads"
        )
        self.storage = OpenListStorage(self.config, self.client, sleep=lambda _: None)

    def assert_code(self, code: StorageErrorCode, call) -> StorageError:
        with self.assertRaises(StorageError) as raised:
            call()
        self.assertEqual(code, raised.exception.code)
        return raised.exception

    def test_config_redacts_secret_and_validates(self) -> None:
        self.assertNotIn("top-secret", repr(self.config))
        self.assertIn("********", repr(self.config))
        with self.assertRaises(ValueError):
            OpenListStorageConfig("id", "name", "file:///tmp", "secret")

    def test_health_checks_server_auth_and_root(self) -> None:
        self.storage.health_check()
        self.assertEqual([("health",), ("stat", "/Downloads")], self.client.calls)
        self.client.failure = OpenListClientError(OpenListClientErrorKind.AUTHENTICATION_FAILED)
        self.assert_code(StorageErrorCode.AUTHENTICATION_FAILED, self.storage.health_check)

    def test_paths_normalize_and_preserve_unicode(self) -> None:
        self.client.entries["/Downloads/电影"] = self.client.entry("电影", True)
        self.client.entries["/Downloads/电影/a b.mkv"] = self.client.entry("a b.mkv", size=3)
        entry = self.storage.stat("电影//./a b.mkv")
        self.assertEqual("电影/a b.mkv", entry.path)
        self.assertEqual(("stat", "/Downloads/电影/a b.mkv"), self.client.calls[-1])

    def test_traversal_and_absolute_paths_are_blocked_locally(self) -> None:
        for path in ("../outside", "../../outside", "folder/../../../outside", "/outside", "C:/x"):
            self.assertIn(
                self.assert_code(
                    StorageErrorCode.PATH_TRAVERSAL
                    if ".." in path
                    else StorageErrorCode.INVALID_PATH,
                    lambda path=path: self.storage.stat(path),
                ).code,
                {StorageErrorCode.PATH_TRAVERSAL, StorageErrorCode.INVALID_PATH},
            )
        self.assertEqual([], self.client.calls)

    def test_list_empty_files_directories_and_pagination(self) -> None:
        self.assertEqual((), self.storage.list(""))
        for index in range(225):
            path = f"/Downloads/item-{index:03d}"
            self.client.entries[path] = self.client.entry(f"item-{index:03d}", index == 0, index)
        result = self.storage.list("")
        self.assertEqual(225, len(result))
        self.assertEqual([1, 1, 2, 3], self.client.page_calls)
        self.assertEqual(StorageEntryType.DIRECTORY, result[0].entry_type)

    def test_list_maps_errors(self) -> None:
        for kind, code in (
            (OpenListClientErrorKind.PERMISSION_DENIED, StorageErrorCode.PERMISSION_DENIED),
            (OpenListClientErrorKind.AUTHENTICATION_FAILED, StorageErrorCode.AUTHENTICATION_FAILED),
            (OpenListClientErrorKind.TIMEOUT, StorageErrorCode.TIMEOUT),
        ):
            self.client.failure = OpenListClientError(kind)
            self.client.repeat_failure = True
            self.assert_code(code, lambda: self.storage.list("missing"))
            self.client.repeat_failure = False

    def test_stat_exists_and_invalid_response(self) -> None:
        self.client.entries["/Downloads/a"] = self.client.entry("a", size=5)
        self.assertEqual(5, self.storage.stat("a").size)
        self.assertTrue(self.storage.exists("a"))
        self.assertFalse(self.storage.exists("missing"))
        self.client.failure = OpenListClientError(OpenListClientErrorKind.INVALID_RESPONSE)
        self.assert_code(StorageErrorCode.IO_ERROR, lambda: self.storage.stat("a"))

    def test_exists_does_not_hide_operational_errors(self) -> None:
        for kind, code in (
            (OpenListClientErrorKind.PERMISSION_DENIED, StorageErrorCode.PERMISSION_DENIED),
            (OpenListClientErrorKind.CONNECTION_FAILED, StorageErrorCode.CONNECTION_FAILED),
            (OpenListClientErrorKind.TIMEOUT, StorageErrorCode.TIMEOUT),
        ):
            self.client.failure = OpenListClientError(kind)
            self.client.repeat_failure = True
            self.assert_code(code, lambda: self.storage.exists("a"))
            self.client.repeat_failure = False

    def test_read_is_streamed_and_maps_failure(self) -> None:
        self.client.contents["/Downloads/a"] = b"abcdef"
        with self.storage.read("a") as stream:
            self.assertEqual(b"abc", stream.read(3))
        self.assert_code(StorageErrorCode.NOT_FOUND, lambda: self.storage.read("missing"))
        self.client.failure = OpenListClientError(OpenListClientErrorKind.TIMEOUT)
        self.client.repeat_failure = True
        self.assert_code(StorageErrorCode.TIMEOUT, lambda: self.storage.read("a"))
        self.client.repeat_failure = False

    def test_streaming_write_default_conflict_parent_and_overwrite(self) -> None:
        class Chunked(io.BytesIO):
            def read(self, size: int = -1) -> bytes:
                self.assertion(size != -1)
                return super().read(size)

            assertion = staticmethod(self.assertTrue)

        self.storage.write("large.bin", Chunked(b"x" * (2 * 1024 * 1024)))
        self.assertEqual(2 * 1024 * 1024, len(self.client.contents["/Downloads/large.bin"]))
        self.assert_code(
            StorageErrorCode.ALREADY_EXISTS, lambda: self.storage.write("large.bin", b"y")
        )
        self.storage.write("large.bin", b"y", overwrite=True)
        self.assert_code(StorageErrorCode.NOT_FOUND, lambda: self.storage.write("missing/a", b"x"))

    def test_create_move_copy_and_conflicts(self) -> None:
        self.storage.create_directory("nested")
        self.storage.create_directory("nested/child")
        self.storage.write("a", b"a")
        self.storage.copy("a", "b")
        self.storage.move("b", "c")
        self.assertTrue(self.storage.exists("a"))
        self.assertTrue(self.storage.exists("c"))
        self.assert_code(StorageErrorCode.ALREADY_EXISTS, lambda: self.storage.copy("a", "c"))
        self.assert_code(StorageErrorCode.NOT_FOUND, lambda: self.storage.copy("missing", "d"))
        self.assert_code(StorageErrorCode.NOT_FOUND, lambda: self.storage.move("missing", "d"))

    def test_move_with_directory_and_name_change_moves_then_renames_server_side(self) -> None:
        self.storage.create_directory("target")
        self.storage.write("original.mkv", b"movie")
        before = len(self.client.calls)
        self.storage.move("original.mkv", "target/renamed.mkv")
        mutation_calls = self.client.calls[before:]
        self.assertEqual(
            [
                (
                    "move",
                    "/Downloads/original.mkv",
                    "/Downloads/target/original.mkv",
                    False,
                ),
                (
                    "move",
                    "/Downloads/target/original.mkv",
                    "/Downloads/target/renamed.mkv",
                    False,
                ),
            ],
            mutation_calls,
        )
        self.assertFalse(
            any(call[0] in {"read", "write", "copy", "delete"} for call in mutation_calls)
        )
        self.assertFalse(self.storage.exists("original.mkv"))
        self.assertTrue(self.storage.exists("target/renamed.mkv"))
        with self.storage.read("target/renamed.mkv") as stream:
            self.assertEqual(b"movie", stream.read())

    def test_combined_move_rename_failure_rolls_back_to_source(self) -> None:
        class RenameFailureClient(FakeOpenListClient):
            def rename(self, path: str, name: str, *, overwrite: bool) -> None:
                self.calls.append(("rename", path, name, overwrite))
                raise OpenListClientError(OpenListClientErrorKind.PERMISSION_DENIED)

        client = RenameFailureClient()
        storage = OpenListStorage(
            OpenListStorageConfig(
                "openlist", "OpenList", "https://example.invalid", "secret", "/Downloads"
            ),
            client,
        )
        storage.create_directory("target")
        storage.write("original.mkv", b"movie")
        before = len(client.calls)
        self.assert_code(
            StorageErrorCode.PERMISSION_DENIED,
            lambda: storage.move("original.mkv", "target/renamed.mkv"),
        )
        mutation_calls = client.calls[before:]
        self.assertTrue(storage.exists("original.mkv"))
        self.assertFalse(storage.exists("target/original.mkv"))
        self.assertFalse(storage.exists("target/renamed.mkv"))
        self.assertFalse(
            any(call[0] in {"read", "write", "copy", "delete"} for call in mutation_calls)
        )

    def test_combined_move_rollback_failure_reports_io_and_leaves_intermediate(self) -> None:
        class RenameAndRollbackFailureClient(FakeOpenListClient):
            move_count = 0

            def move(self, source: str, target: str, *, overwrite: bool) -> None:
                self.move_count += 1
                if self.move_count == 2:
                    self.calls.append(("move", source, target, overwrite))
                    raise OpenListClientError(OpenListClientErrorKind.CONNECTION_LOST)
                super().move(source, target, overwrite=overwrite)

            def rename(self, path: str, name: str, *, overwrite: bool) -> None:
                self.calls.append(("rename", path, name, overwrite))
                raise OpenListClientError(OpenListClientErrorKind.PERMISSION_DENIED)

        client = RenameAndRollbackFailureClient()
        storage = OpenListStorage(
            OpenListStorageConfig(
                "openlist", "OpenList", "https://example.invalid", "secret", "/Downloads"
            ),
            client,
        )
        storage.create_directory("target")
        storage.write("original.mkv", b"movie")
        self.assert_code(
            StorageErrorCode.IO_ERROR,
            lambda: storage.move("original.mkv", "target/renamed.mkv"),
        )
        self.assertFalse(storage.exists("original.mkv"))
        self.assertTrue(storage.exists("target/original.mkv"))
        self.assertFalse(storage.exists("target/renamed.mkv"))

    def test_mutation_permission_and_directory_conflicts(self) -> None:
        self.client.failure = OpenListClientError(OpenListClientErrorKind.PERMISSION_DENIED)
        self.assert_code(StorageErrorCode.PERMISSION_DENIED, lambda: self.storage.write("a", b"x"))
        self.client.entries["/Downloads/file"] = self.client.entry("file")
        self.assert_code(
            StorageErrorCode.ALREADY_EXISTS, lambda: self.storage.create_directory("file")
        )

    def test_delete_file_empty_directory_and_protect_nonempty(self) -> None:
        self.storage.write("a", b"a")
        self.storage.delete("a")
        self.storage.create_directory("empty")
        self.storage.delete("empty")
        self.storage.create_directory("full")
        self.client.entries["/Downloads/full/a"] = self.client.entry("a")
        self.assert_code(StorageErrorCode.ALREADY_EXISTS, lambda: self.storage.delete("full"))
        self.assertTrue(self.storage.exists("full"))

    def test_readonly_blocks_every_mutation_without_client_call(self) -> None:
        readonly = OpenListStorage(
            OpenListStorageConfig("id", "ro", "https://example.invalid", "secret", read_only=True),
            self.client,
        )
        before = list(self.client.calls)
        operations = (
            lambda: readonly.write("a", b"x"),
            lambda: readonly.create_directory("a"),
            lambda: readonly.move("a", "b"),
            lambda: readonly.copy("a", "b"),
            lambda: readonly.delete("a"),
        )
        for operation in operations:
            self.assert_code(StorageErrorCode.READ_ONLY, operation)
        self.assertEqual(before, self.client.calls)
        self.assertFalse(readonly.capabilities.can_move)

    def test_capabilities_and_links(self) -> None:
        capabilities = self.storage.capabilities
        self.assertTrue(capabilities.can_move and capabilities.can_copy and capabilities.can_delete)
        self.assertFalse(capabilities.can_hard_link or capabilities.can_soft_link)
        self.assert_code(
            StorageErrorCode.UNSUPPORTED_OPERATION, lambda: self.storage.hard_link("a", "b")
        )
        self.assert_code(
            StorageErrorCode.UNSUPPORTED_OPERATION, lambda: self.storage.soft_link("a", "b")
        )

    def test_retry_only_idempotent_operations_and_rate_limit(self) -> None:
        self.client.failure = OpenListClientError(
            OpenListClientErrorKind.RATE_LIMITED, retry_after=0
        )
        self.assertEqual((), self.storage.list(""))
        self.client.failure = OpenListClientError(OpenListClientErrorKind.TIMEOUT)
        self.assert_code(StorageErrorCode.TIMEOUT, lambda: self.storage.write("a", b"x"))
        writes = [call for call in self.client.calls if call[0] == "write"]
        self.assertEqual(1, len(writes))


class FakeResponse:
    def __init__(self, status: int, payload: object = None, headers: dict[str, str] | None = None):
        self.status_code = status
        self._payload = payload
        self.headers = headers or {}
        self.closed = False

    def json(self) -> object:
        if isinstance(self._payload, BaseException):
            raise self._payload
        return self._payload

    def close(self) -> None:
        self.closed = True


class HttpOpenListClientContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = HttpOpenListClient.__new__(HttpOpenListClient)

    def test_http_status_mapping(self) -> None:
        cases = {
            400: OpenListClientErrorKind.INVALID_REQUEST,
            401: OpenListClientErrorKind.AUTHENTICATION_FAILED,
            403: OpenListClientErrorKind.PERMISSION_DENIED,
            404: OpenListClientErrorKind.NOT_FOUND,
            409: OpenListClientErrorKind.ALREADY_EXISTS,
            429: OpenListClientErrorKind.RATE_LIMITED,
            503: OpenListClientErrorKind.CONNECTION_LOST,
        }
        for status, expected in cases.items():
            with self.subTest(status=status), self.assertRaises(OpenListClientError) as raised:
                self.client._check_status(FakeResponse(status, headers={"Retry-After": "3"}))
            self.assertEqual(expected, raised.exception.kind)
            if status == 429:
                self.assertEqual(3, raised.exception.retry_after)

    def test_business_status_and_invalid_response_mapping(self) -> None:
        for code, expected in (
            (400, OpenListClientErrorKind.INVALID_REQUEST),
            (401, OpenListClientErrorKind.AUTHENTICATION_FAILED),
            (403, OpenListClientErrorKind.PERMISSION_DENIED),
            (404, OpenListClientErrorKind.NOT_FOUND),
            (409, OpenListClientErrorKind.ALREADY_EXISTS),
            (429, OpenListClientErrorKind.RATE_LIMITED),
            (500, OpenListClientErrorKind.CONNECTION_LOST),
        ):
            with self.subTest(code=code), self.assertRaises(OpenListClientError) as raised:
                self.client._envelope(FakeResponse(200, {"code": code, "message": "failure"}))
            self.assertEqual(expected, raised.exception.kind)
        with self.assertRaises(OpenListClientError) as raised:
            self.client._envelope(FakeResponse(200, ValueError("not json")))
        self.assertEqual(OpenListClientErrorKind.INVALID_RESPONSE, raised.exception.kind)

    def test_business_conflict_message_overrides_ambiguous_403(self) -> None:
        with self.assertRaises(OpenListClientError) as raised:
            self.client._envelope(
                FakeResponse(200, {"code": 403, "message": "file [movie.mkv] exists"})
            )
        self.assertEqual(OpenListClientErrorKind.ALREADY_EXISTS, raised.exception.kind)
