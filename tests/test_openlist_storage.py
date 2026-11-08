from __future__ import annotations

import io
import json
import threading
import unittest
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote

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

    def test_empty_v4_directory_null_content_maps_to_empty_page(self) -> None:
        self.client._json = lambda *_args, **_kwargs: {"content": None, "total": 0}
        self.assertEqual(OpenListPage((), 0), self.client.list_page("/empty", 1, 100))

    def test_list_page_rejects_inconsistent_or_malformed_v4_data(self) -> None:
        for data in (
            {"content": None, "total": 1},
            {"content": None, "total": -1},
            {"content": None, "total": True},
            {"content": None},
            {"content": {}, "total": 0},
            {"content": "", "total": 0},
            {"content": [], "total": -1},
            [],
        ):
            with self.subTest(data=data), self.assertRaises(OpenListClientError) as raised:
                self.client._json = lambda *_args, data=data, **_kwargs: data
                self.client.list_page("/empty", 1, 100)
            self.assertEqual(OpenListClientErrorKind.INVALID_RESPONSE, raised.exception.kind)


class _OpenListHttpServer:
    """Bounded OpenList v4 HTTP fixture that records every request."""

    def __init__(self, entries: dict[str, tuple[bool, bytes]], *, get_mode: str) -> None:
        self.entries = dict(entries)
        self.get_mode = get_mode
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []
        self.raw: dict[str, bytes] = {}
        self.list_failures: dict[int, str] = {}
        self._lock = threading.Lock()
        state = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args: object) -> None:
                return

            def _reply(self, status: int, document: dict[str, object] | None = None) -> None:
                body = b"" if document is None else json.dumps(document).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _business(self, code: int, message: str = "failure") -> None:
                self._reply(200, {"code": code, "message": message, "data": None})

            def _envelope(self, data: object) -> None:
                self._reply(200, {"code": 200, "message": "success", "data": data})

            def _record(self, method: str, body: dict[str, object] | None = None) -> None:
                with state._lock:
                    state.calls.append((method, self.path, body))

            def do_GET(self) -> None:  # noqa: N802
                self._record("GET")
                if self.path == "/ping":
                    self._reply(200)
                    return
                payload = state.raw.get(self.path)
                if payload is None:
                    self._reply(404)
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_POST(self) -> None:  # noqa: N802
                raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                body = json.loads(raw or b"{}")
                self._record("POST", body)
                with state._lock:
                    if self.path == "/api/fs/list":
                        self._list(body)
                    elif self.path == "/api/fs/get":
                        self._get(body)
                    elif self.path == "/api/fs/move":
                        state._move(body)
                        self._envelope(None)
                    elif self.path == "/api/fs/rename":
                        state._rename(body)
                        self._envelope(None)
                    elif self.path == "/api/fs/remove":
                        state._remove(body)
                        self._envelope(None)
                    else:
                        self._business(405, "method not allowed")

            def _list(self, body: dict[str, object]) -> None:
                path = str(body.get("path", ""))
                page = body.get("page")
                per_page = body.get("per_page")
                if body.get("refresh") is not False:
                    self._business(400, "refresh must be false")
                    return
                if type(page) is not int or type(per_page) is not int or page < 1 or per_page < 1:
                    self._business(400, "invalid pagination")
                    return
                mode = state.list_failures.get(page)
                if mode == "http_500":
                    self._reply(500)
                    return
                if mode == "business_500":
                    self._business(500)
                    return
                if mode == "business_403":
                    self._business(403, "permission denied")
                    return
                if mode == "invalid":
                    self._envelope({"content": {}, "total": 0})
                    return
                if mode == "empty_total_9":
                    self._envelope({"content": [], "total": 9})
                    return
                value = state.entries.get(path)
                if value is None:
                    self._business(404, "not found")
                    return
                if not value[0]:
                    self._business(400, "not a directory")
                    return
                prefix = path.rstrip("/") + "/"
                children = [
                    key
                    for key in sorted(state.entries)
                    if key.startswith(prefix) and "/" not in key[len(prefix) :]
                ]
                start = (page - 1) * per_page
                selected = children[start : start + per_page]
                self._envelope(
                    {
                        "content": [state._document(key) for key in selected],
                        "total": len(children),
                    }
                )

            def _get(self, body: dict[str, object]) -> None:
                path = str(body.get("path", ""))
                value = state.entries.get(path)
                if value is None:
                    self._business(404, "not found")
                    return
                if state.get_mode == "http_405":
                    self._reply(405)
                    return
                if state.get_mode == "business_405":
                    self._business(405, "method not allowed")
                    return
                document = state._document(path)
                if not value[0]:
                    raw_path = f"/raw/{quote(path)}"
                    state.raw[raw_path] = value[1]
                    document["raw_url"] = f"{state.base_url}{raw_path}"
                self._reply(200, {"code": 200, "message": "success", "data": document})

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}"

    def start(self) -> _OpenListHttpServer:
        self._thread.start()
        return self

    def close(self) -> None:
        self._server.server_close()

    def shutdown(self) -> None:
        self._server.shutdown()

    def _document(self, path: str) -> dict[str, object]:
        directory, payload = self.entries[path]
        return {
            "name": path.rsplit("/", 1)[-1],
            "size": 0 if directory else len(payload),
            "is_dir": directory,
            "modified": "2026-01-01T00:00:00Z",
        }

    def _relocate(self, source: str, target: str) -> None:
        for key in tuple(self.entries):
            if key == source:
                self.entries[target] = self.entries.pop(key)
            elif key.startswith(source + "/"):
                self.entries[target + key[len(source) :]] = self.entries.pop(key)

    def _move(self, body: dict[str, object]) -> None:
        source_dir = str(body["src_dir"]).rstrip("/")
        target_dir = str(body["dst_dir"]).rstrip("/")
        overwrite = bool(body.get("overwrite"))
        names = body["names"]
        if not isinstance(names, list) or len(names) != 1:
            raise AssertionError("fixture expects one moved name")
        source = f"{source_dir}/{names[0]}"
        target = f"{target_dir}/{names[0]}"
        if source not in self.entries:
            raise AssertionError(f"move source missing: {source}")
        if target in self.entries and not overwrite:
            raise AssertionError(f"move conflict: {target}")
        self._relocate(source, target)

    def _rename(self, body: dict[str, object]) -> None:
        source = str(body["path"])
        target = f"{source.rsplit('/', 1)[0]}/{body['name']}"
        overwrite = bool(body.get("overwrite"))
        if source not in self.entries:
            raise AssertionError(f"rename source missing: {source}")
        if target in self.entries and not overwrite:
            raise AssertionError(f"rename conflict: {target}")
        self._relocate(source, target)

    def _remove(self, body: dict[str, object]) -> None:
        directory = str(body["dir"]).rstrip("/")
        names = body["names"]
        if not isinstance(names, list):
            raise AssertionError("fixture expects a name list")
        for name in names:
            path = f"{directory}/{name}"
            if not self.entries.get(path, (False, b""))[0]:
                raise AssertionError(f"remove expects a directory: {path}")
            if any(key.startswith(path + "/") for key in self.entries):
                raise AssertionError(f"remove expects an empty directory: {path}")
            del self.entries[path]


class HttpOpenListStorageTests(unittest.TestCase):
    def _start(self, entries: dict[str, tuple[bool, bytes]], *, get_mode: str = "http_405"):
        server = _OpenListHttpServer(entries, get_mode=get_mode).start()
        self.addCleanup(server._thread.join, 5)
        self.addCleanup(server.shutdown)
        self.addCleanup(server.close)
        return server

    def _storage(
        self,
        server: _OpenListHttpServer,
        *,
        root_path: str = "/Downloads",
        page_size: int = 100,
    ) -> OpenListStorage:
        return OpenListStorage(
            OpenListStorageConfig(
                "openlist",
                "OpenList",
                server.base_url,
                "secret",
                root_path=root_path,
                page_size=page_size,
                max_retries=0,
            )
        )

    def assert_code(self, code: StorageErrorCode, call) -> StorageError:
        with self.assertRaises(StorageError) as raised:
            call()
        self.assertEqual(code, raised.exception.code)
        return raised.exception

    def assert_metadata_only(self, server: _OpenListHttpServer) -> None:
        posts = [call for call in server.calls if call[0] == "POST"]
        self.assertEqual({"/api/fs/list"}, {path for _method, path, _body in posts})
        for _method, _path, body in posts:
            self.assertIs(False, body["refresh"])
        self.assertFalse(any(path == "/api/fs/get" for _method, path, _body in server.calls))

    def test_http_metadata_queries_list_only_without_fs_get(self) -> None:
        server = self._start(
            {
                "/Downloads": (True, b""),
                "/Downloads/a.mkv": (False, b"aaaa"),
                "/Downloads/b.mkv": (False, b"bb"),
                "/Downloads/电影": (True, b""),
                "/Downloads/ 影片 c d.mkv ": (False, b"media"),
                "/Downloads/影片 c d.mkv": (False, b"other"),
            }
        )
        storage = self._storage(server, page_size=2)
        self.addCleanup(storage.close)

        spaced = storage.stat(" 影片 c d.mkv ")
        self.assertEqual(" 影片 c d.mkv ", spaced.path)
        self.assertEqual(5, spaced.size)
        directory = storage.stat("电影")
        self.assertEqual(StorageEntryType.DIRECTORY, directory.entry_type)
        second_page = storage.stat("影片 c d.mkv")
        self.assertEqual(5, second_page.size)
        self.assertTrue(storage.exists("a.mkv"))
        self.assertFalse(storage.exists("missing"))
        root = storage.stat("")
        self.assertEqual(StorageEntryType.DIRECTORY, root.entry_type)
        self.assertEqual(0, root.size)
        self.assertEqual(datetime(1970, 1, 1, tzinfo=UTC), root.modified_at)
        self.assert_code(StorageErrorCode.NOT_FOUND, lambda: storage.stat("missing"))
        self.assert_metadata_only(server)

    def test_virtual_root_verifies_itself_without_listing_a_parent(self) -> None:
        server = self._start({"/": (True, b""), "/one.mkv": (False, b"one")}, get_mode="http_405")
        storage = self._storage(server, root_path="")
        self.addCleanup(storage.close)
        root = storage.stat("")
        self.assertEqual(StorageEntryType.DIRECTORY, root.entry_type)
        self.assertEqual(datetime(1970, 1, 1, tzinfo=UTC), root.modified_at)
        self.assertEqual(3, storage.stat("one.mkv").size)
        metadata = [
            body
            for method, path, body in server.calls
            if method == "POST" and path == "/api/fs/list"
        ]
        self.assertEqual("/", metadata[0]["path"])
        self.assertIs(False, metadata[0]["refresh"])

    def test_root_listing_failures_are_not_hidden_by_synthesis(self) -> None:
        cases = (
            ({"/": (True, b"")}, "/Missing", "http_404", StorageErrorCode.NOT_FOUND),
            ({"/Downloads": (False, b"file")}, "/Downloads", None, StorageErrorCode.INVALID_PATH),
            (
                {"/Downloads": (True, b"")},
                "/Downloads",
                "business_403",
                StorageErrorCode.PERMISSION_DENIED,
            ),
            ({"/Downloads": (True, b"")}, "/Downloads", "invalid", StorageErrorCode.IO_ERROR),
        )
        for entries, root_path, failure, code in cases:
            with self.subTest(root_path=root_path, failure=failure):
                server = self._start(entries)
                if failure is not None:
                    server.list_failures[1] = failure
                storage = self._storage(server, root_path=root_path)
                self.addCleanup(storage.close)
                self.assert_code(code, lambda: storage.stat(""))
                self.assert_metadata_only(server)

    def test_incomplete_or_failed_traversal_is_never_reported_as_absent(self) -> None:
        entries = {
            "/Downloads": (True, b""),
            **{f"/Downloads/item-{index}.mkv": (False, b"x") for index in range(5)},
        }
        cases = (
            ("http_500", StorageErrorCode.CONNECTION_LOST),
            ("business_403", StorageErrorCode.PERMISSION_DENIED),
            ("invalid", StorageErrorCode.IO_ERROR),
            ("empty_total_9", StorageErrorCode.IO_ERROR),
        )
        for mode, code in cases:
            with self.subTest(mode=mode):
                server = self._start(entries)
                server.list_failures[2] = mode
                storage = self._storage(server, page_size=2)
                self.addCleanup(storage.close)
                self.assert_code(code, lambda: storage.stat("missing"))
                self.assert_metadata_only(server)
                self.assertGreaterEqual(
                    len([call for call in server.calls if call[1] == "/api/fs/list"]), 1
                )

    def test_read_still_requests_the_download_link_and_streams_content(self) -> None:
        server = self._start(
            {"/Downloads": (True, b""), "/Downloads/a.mkv": (False, b"abcdef")},
            get_mode="success",
        )
        storage = self._storage(server)
        self.addCleanup(storage.close)
        with storage.read("a.mkv") as stream:
            self.assertEqual(b"abc", stream.read(3))
        self.assertTrue(any(path == "/api/fs/get" for _method, path, _body in server.calls))
        self.assertTrue(
            any(method == "GET" and path.startswith("/raw/") for method, path, _ in server.calls)
        )

    def test_read_fails_when_the_download_link_is_unavailable(self) -> None:
        for mode in ("http_405", "business_405"):
            with self.subTest(mode=mode):
                server = self._start(
                    {"/Downloads": (True, b""), "/Downloads/a.mkv": (False, b"abcdef")},
                    get_mode=mode,
                )
                storage = self._storage(server)
                self.addCleanup(storage.close)
                self.assert_code(StorageErrorCode.UNKNOWN, lambda: storage.read("a.mkv"))
                self.assertTrue(any(path == "/api/fs/get" for _method, path, _body in server.calls))
                self.assertFalse(
                    any(
                        method == "GET" and path.startswith("/raw/")
                        for method, path, _ in server.calls
                    )
                )

    def test_native_move_and_rename_variants_verify_without_fs_get(self) -> None:
        server = self._start(
            {
                "/Downloads": (True, b""),
                "/Downloads/A": (True, b""),
                "/Downloads/B": (True, b""),
                "/Downloads/root.mkv": (False, b"root"),
                "/Downloads/A/rename.mkv": (False, b"rename"),
                "/Downloads/B/combined.mkv": (False, b"combined"),
            }
        )
        storage = self._storage(server)
        self.addCleanup(storage.close)
        storage.move("root.mkv", "A/root.mkv")
        storage.move("A/rename.mkv", "A/renamed.mkv")
        storage.move("B/combined.mkv", "A/combined-final.mkv")
        self.assertFalse(storage.exists("root.mkv"))
        self.assertEqual(4, storage.stat("A/root.mkv").size)
        self.assertEqual(6, storage.stat("A/renamed.mkv").size)
        self.assertEqual(8, storage.stat("A/combined-final.mkv").size)
        mutation_paths = [
            path
            for method, path, _body in server.calls
            if method == "POST" and path != "/api/fs/list"
        ]
        self.assertEqual(
            ["/api/fs/move", "/api/fs/rename", "/api/fs/move", "/api/fs/rename"],
            mutation_paths,
        )
        metadata = [
            call for call in server.calls if call[0] == "POST" and call[1] == "/api/fs/list"
        ]
        for _method, _path, body in metadata:
            self.assertIs(False, body["refresh"])
        self.assertFalse(any(path == "/api/fs/get" for _method, path, _body in server.calls))

    def test_delete_uses_directory_listing_for_its_type_check(self) -> None:
        server = self._start(
            {
                "/Downloads": (True, b""),
                "/Downloads/empty": (True, b""),
                "/Downloads/full": (True, b""),
                "/Downloads/full/a.mkv": (False, b"a"),
            }
        )
        storage = self._storage(server)
        self.addCleanup(storage.close)
        storage.delete("empty")
        self.assert_code(StorageErrorCode.ALREADY_EXISTS, lambda: storage.delete("full"))
        self.assertTrue(storage.exists("full"))
        self.assertFalse(storage.exists("empty"))
        posts = [call for call in server.calls if call[0] == "POST"]
        self.assertEqual(
            {"/api/fs/list", "/api/fs/remove"}, {path for _method, path, _body in posts}
        )
        for _method, path, body in posts:
            if path == "/api/fs/list":
                self.assertIs(False, body["refresh"])
        self.assertFalse(any(path == "/api/fs/get" for _method, path, _body in server.calls))
