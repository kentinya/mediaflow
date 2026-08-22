from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import BinaryIO, Protocol, TypeVar, cast
from urllib.parse import quote, urlparse

from mediaflow.domain.storage import (
    StorageCapabilities,
    StorageEntry,
    StorageEntryType,
    StorageError,
    StorageErrorCode,
    WriteSource,
)

Result = TypeVar("Result")


@dataclass(frozen=True, repr=False)
class OpenListStorageConfig:
    storage_id: str
    name: str
    base_url: str
    token: str
    root_path: str = "/"
    read_only: bool = False
    connect_timeout: float = 10.0
    request_timeout: float = 60.0
    max_concurrency: int = 4
    max_retries: int = 2
    page_size: int = 100

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if not self.storage_id or not self.name or not self.token:
            raise ValueError("storage ID, name, and authentication token are required")
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base URL must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("base URL must not contain credentials, query, or fragment")
        if self.connect_timeout <= 0 or self.request_timeout <= 0:
            raise ValueError("timeouts must be positive")
        if self.max_concurrency < 1 or self.page_size < 1 or self.max_retries < 0:
            raise ValueError("concurrency/page size must be positive and retries non-negative")

    def __repr__(self) -> str:
        return (
            "OpenListStorageConfig("
            f"storage_id={self.storage_id!r}, name={self.name!r}, "
            f"base_url={self.base_url!r}, token='********', root_path={self.root_path!r}, "
            f"read_only={self.read_only!r}, connect_timeout={self.connect_timeout!r}, "
            f"request_timeout={self.request_timeout!r}, "
            f"max_concurrency={self.max_concurrency!r}, max_retries={self.max_retries!r}, "
            f"page_size={self.page_size!r})"
        )


class OpenListClientErrorKind(StrEnum):
    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"
    ALREADY_EXISTS = "already_exists"
    INVALID_REQUEST = "invalid_request"
    CONNECTION_FAILED = "connection_failed"
    CONNECTION_LOST = "connection_lost"
    AUTHENTICATION_FAILED = "authentication_failed"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    INVALID_RESPONSE = "invalid_response"
    IO_ERROR = "io_error"
    UNKNOWN = "unknown"


class OpenListClientError(Exception):
    def __init__(
        self,
        kind: OpenListClientErrorKind,
        message: str = "OpenList request failed",
        *,
        retry_after: float | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.retry_after = retry_after
        self.cause = cause


@dataclass(frozen=True)
class OpenListClientEntry:
    name: str
    path: str
    is_directory: bool
    size: int
    modified_at: datetime
    raw_url: str | None = None


@dataclass(frozen=True)
class OpenListPage:
    entries: Sequence[OpenListClientEntry]
    total: int


class OpenListClient(Protocol):
    def health(self) -> None: ...
    def list_page(self, path: str, page: int, per_page: int) -> OpenListPage: ...
    def stat(self, path: str) -> OpenListClientEntry: ...
    def open_read(self, path: str) -> BinaryIO: ...
    def upload(self, path: str, data: WriteSource, *, overwrite: bool) -> None: ...
    def create_directory(self, path: str) -> None: ...
    def rename(self, path: str, name: str, *, overwrite: bool) -> None: ...
    def move(self, source: str, target: str, *, overwrite: bool) -> None: ...
    def copy(self, source: str, target: str, *, overwrite: bool) -> None: ...
    def delete(self, path: str) -> None: ...
    def close(self) -> None: ...


class _LeasedStream:
    def __init__(self, stream: BinaryIO, semaphore: threading.BoundedSemaphore) -> None:
        self._stream = stream
        self._semaphore = semaphore
        self._released = False

    def __getattr__(self, name: str) -> object:
        return getattr(self._stream, name)

    def __enter__(self) -> _LeasedStream:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @property
    def closed(self) -> bool:
        return self._stream.closed

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def close(self) -> None:
        try:
            self._stream.close()
        finally:
            if not self._released:
                self._released = True
                self._semaphore.release()


class OpenListStorage:
    def __init__(
        self,
        config: OpenListStorageConfig,
        client: OpenListClient | None = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._config = config
        self._root = self._normalize_root(config.root_path)
        self._client = client or HttpOpenListClient(config)
        self._semaphore = threading.BoundedSemaphore(config.max_concurrency)
        self._sleep = sleep

    @property
    def storage_id(self) -> str:
        return self._config.storage_id

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def read_only(self) -> bool:
        return self._config.read_only

    @property
    def capabilities(self) -> StorageCapabilities:
        writable = not self.read_only
        return StorageCapabilities(writable, writable, writable, False, False)

    def health_check(self) -> None:
        self._execute("health_check", "", self._client.health, retry=True)
        self._execute("health_check", "", lambda: self._client.stat(self._root), retry=True)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OpenListStorage:
        self.health_check()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def list(self, path: str) -> Sequence[StorageEntry]:
        logical, remote = self._paths(path, "list")

        def operation() -> Sequence[StorageEntry]:
            result: list[StorageEntry] = []
            page = 1
            while True:
                response = self._client.list_page(remote, page, self._config.page_size)
                if response.total < 0:
                    raise OpenListClientError(OpenListClientErrorKind.INVALID_RESPONSE)
                result.extend(self._domain_entry(logical, item) for item in response.entries)
                if len(result) >= response.total or not response.entries:
                    return tuple(result)
                page += 1

        return self._execute("list", path, operation, retry=True)

    def stat(self, path: str) -> StorageEntry:
        logical, remote = self._paths(path, "stat")
        return self._execute(
            "stat",
            path,
            lambda: self._domain_entry("", self._client.stat(remote), logical),
            retry=True,
        )

    def exists(self, path: str) -> bool:
        _, remote = self._paths(path, "exists")

        def operation() -> bool:
            try:
                self._client.stat(remote)
            except OpenListClientError as error:
                if error.kind is OpenListClientErrorKind.NOT_FOUND:
                    return False
                raise
            return True

        return self._execute("exists", path, operation, retry=True)

    def read(self, path: str) -> BinaryIO:
        _, remote = self._paths(path, "read")
        self._semaphore.acquire()
        try:
            stream = self._retry(lambda: self._client.open_read(remote))
            return cast(BinaryIO, _LeasedStream(stream, self._semaphore))
        except OpenListClientError as error:
            self._semaphore.release()
            raise self._storage_error("read", path, error) from error
        except BaseException:
            self._semaphore.release()
            raise

    def write(self, path: str, data: WriteSource, *, overwrite: bool = False) -> None:
        self._ensure_writable("write", path)
        _, remote = self._paths(path, "write")
        self._execute("write", path, lambda: self._client.upload(remote, data, overwrite=overwrite))

    def create_directory(self, path: str) -> None:
        self._ensure_writable("create_directory", path)
        _, remote = self._paths(path, "create_directory")
        self._execute("create_directory", path, lambda: self._client.create_directory(remote))

    def move(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self._ensure_writable("move", source)
        _, remote_source = self._paths(source, "move")
        _, remote_target = self._paths(target, "move")

        def operation() -> None:
            source_path = PurePosixPath(remote_source)
            target_path = PurePosixPath(remote_target)
            changes_directory_and_name = (
                source_path.parent != target_path.parent and source_path.name != target_path.name
            )
            if not changes_directory_and_name:
                self._client.move(remote_source, remote_target, overwrite=overwrite)
                return
            intermediate = str(target_path.parent / source_path.name)
            # OpenList's move endpoint preserves the basename, while rename changes
            # only the basename. Chain those native server-side operations so a
            # same-storage MOVE never streams the media through this process.
            # Never overwrite an unrelated intermediate file: overwrite applies
            # only to the requested final target.
            self._client.move(remote_source, intermediate, overwrite=False)
            try:
                self._client.rename(intermediate, target_path.name, overwrite=overwrite)
            except OpenListClientError as rename_error:
                try:
                    self._client.move(intermediate, remote_source, overwrite=False)
                except OpenListClientError as rollback_error:
                    raise OpenListClientError(
                        OpenListClientErrorKind.IO_ERROR, cause=rollback_error
                    ) from rename_error
                raise

        self._execute(
            "move",
            source,
            operation,
        )

    def copy(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self._ensure_writable("copy", source)
        _, remote_source = self._paths(source, "copy")
        _, remote_target = self._paths(target, "copy")
        self._execute(
            "copy",
            source,
            lambda: self._client.copy(remote_source, remote_target, overwrite=overwrite),
        )

    def delete(self, path: str) -> None:
        self._ensure_writable("delete", path)
        logical, remote = self._paths(path, "delete")

        def operation() -> None:
            entry = self._client.stat(remote)
            if entry.is_directory:
                page = self._client.list_page(remote, 1, 1)
                if page.total or page.entries:
                    raise OpenListClientError(OpenListClientErrorKind.ALREADY_EXISTS)
            self._client.delete(remote)

        self._execute("delete", logical, operation)

    def hard_link(self, source: str, target: str) -> None:
        self._unsupported("hard_link", target)

    def soft_link(self, source: str, target: str) -> None:
        self._unsupported("soft_link", target)

    def _execute(
        self, operation: str, path: str, call: Callable[[], Result], *, retry: bool = False
    ) -> Result:
        with self._semaphore:
            try:
                return self._retry(call) if retry else call()
            except OpenListClientError as error:
                raise self._storage_error(operation, path, error) from error

    def _retry(self, call: Callable[[], Result]) -> Result:
        for attempt in range(self._config.max_retries + 1):
            try:
                return call()
            except OpenListClientError as error:
                temporary = error.kind in {
                    OpenListClientErrorKind.CONNECTION_FAILED,
                    OpenListClientErrorKind.CONNECTION_LOST,
                    OpenListClientErrorKind.TIMEOUT,
                    OpenListClientErrorKind.RATE_LIMITED,
                }
                if not temporary or attempt == self._config.max_retries:
                    raise
                delay = error.retry_after if error.retry_after is not None else 0.1 * (2**attempt)
                self._sleep(min(max(delay, 0), 30.0))
        raise AssertionError("unreachable")

    def _paths(self, path: str, operation: str) -> tuple[str, str]:
        try:
            logical = self._normalize_logical(path)
        except ValueError as error:
            code = (
                StorageErrorCode.PATH_TRAVERSAL
                if "traversal" in str(error)
                else StorageErrorCode.INVALID_PATH
            )
            raise StorageError(
                code, operation, path, "invalid storage path", cause=error
            ) from error
        remote = self._root if not logical else f"{self._root.rstrip('/')}/{logical}"
        return logical, remote

    @staticmethod
    def _normalize_logical(path: str) -> str:
        if not isinstance(path, str) or "\x00" in path:
            raise ValueError("invalid path")
        value = path.replace("\\", "/")
        if value.startswith("/") or urlparse(value).scheme or (len(value) > 1 and value[1] == ":"):
            raise ValueError("absolute path")
        parts: list[str] = []
        for part in value.split("/"):
            if part in {"", "."}:
                continue
            if part == "..":
                if not parts:
                    raise ValueError("path traversal")
                parts.pop()
            else:
                parts.append(part)
        return "/".join(parts)

    @staticmethod
    def _normalize_root(path: str) -> str:
        value = path.replace("\\", "/")
        if "\x00" in value or urlparse(value).scheme:
            raise ValueError("invalid root path")
        parts: list[str] = []
        for part in value.split("/"):
            if part in {"", "."}:
                continue
            if part == "..":
                if not parts:
                    raise ValueError("root path escapes OpenList root")
                parts.pop()
            else:
                parts.append(part)
        return "/" + "/".join(parts)

    @staticmethod
    def _domain_entry(
        parent: str, entry: OpenListClientEntry, path: str | None = None
    ) -> StorageEntry:
        logical = path if path is not None else "/".join(filter(None, (parent, entry.name)))
        return StorageEntry(
            name=PurePosixPath(logical).name if logical else "",
            path=logical,
            entry_type=StorageEntryType.DIRECTORY if entry.is_directory else StorageEntryType.FILE,
            size=max(entry.size, 0),
            modified_at=entry.modified_at,
        )

    def _ensure_writable(self, operation: str, path: str) -> None:
        if self.read_only:
            raise StorageError(StorageErrorCode.READ_ONLY, operation, path, "storage is read-only")

    @staticmethod
    def _unsupported(operation: str, path: str) -> None:
        raise StorageError(
            StorageErrorCode.UNSUPPORTED_OPERATION, operation, path, "operation is unsupported"
        )

    @staticmethod
    def _storage_error(operation: str, path: str, error: OpenListClientError) -> StorageError:
        mapping = {
            OpenListClientErrorKind.NOT_FOUND: StorageErrorCode.NOT_FOUND,
            OpenListClientErrorKind.PERMISSION_DENIED: StorageErrorCode.PERMISSION_DENIED,
            OpenListClientErrorKind.ALREADY_EXISTS: StorageErrorCode.ALREADY_EXISTS,
            OpenListClientErrorKind.INVALID_REQUEST: StorageErrorCode.INVALID_PATH,
            OpenListClientErrorKind.CONNECTION_FAILED: StorageErrorCode.CONNECTION_FAILED,
            OpenListClientErrorKind.CONNECTION_LOST: StorageErrorCode.CONNECTION_LOST,
            OpenListClientErrorKind.AUTHENTICATION_FAILED: StorageErrorCode.AUTHENTICATION_FAILED,
            OpenListClientErrorKind.TIMEOUT: StorageErrorCode.TIMEOUT,
            OpenListClientErrorKind.RATE_LIMITED: StorageErrorCode.RATE_LIMITED,
            OpenListClientErrorKind.INVALID_RESPONSE: StorageErrorCode.IO_ERROR,
            OpenListClientErrorKind.IO_ERROR: StorageErrorCode.IO_ERROR,
            OpenListClientErrorKind.UNKNOWN: StorageErrorCode.UNKNOWN,
        }
        code = mapping[error.kind]
        return StorageError(
            code, operation, path, f"OpenList {operation} failed: {code.value}", cause=error
        )


class HttpOpenListClient:
    """OpenList v4 HTTP implementation. HTTP/DTO details remain infrastructure-only."""

    def __init__(self, config: OpenListStorageConfig) -> None:
        try:
            import httpx
        except ImportError as error:
            raise RuntimeError("install mediaflow[openlist] to use OpenListStorage") from error
        self._httpx = httpx
        self._base_url = config.base_url.rstrip("/")
        self._client = httpx.Client(
            headers={"Authorization": config.token},
            timeout=httpx.Timeout(config.request_timeout, connect=config.connect_timeout),
            follow_redirects=True,
        )

    def health(self) -> None:
        response = self._request("GET", "/ping", envelope=False)
        response.close()

    def list_page(self, path: str, page: int, per_page: int) -> OpenListPage:
        data = self._json(
            "POST",
            "/api/fs/list",
            {"path": path, "page": page, "per_page": per_page, "refresh": False},
        )
        if not isinstance(data, dict):
            raise OpenListClientError(OpenListClientErrorKind.INVALID_RESPONSE)
        content = data.get("content")
        total = data.get("total")
        if type(total) is not int or total < 0:
            raise OpenListClientError(OpenListClientErrorKind.INVALID_RESPONSE)
        if content is None:
            if total != 0:
                raise OpenListClientError(OpenListClientErrorKind.INVALID_RESPONSE)
            content = []
        if not isinstance(content, list):
            raise OpenListClientError(OpenListClientErrorKind.INVALID_RESPONSE)
        entries = tuple(self._entry(item, path) for item in content)
        return OpenListPage(entries, total)

    def stat(self, path: str) -> OpenListClientEntry:
        return self._entry(
            self._json("POST", "/api/fs/get", {"path": path}), str(PurePosixPath(path).parent)
        )

    def open_read(self, path: str) -> BinaryIO:
        item = self.stat(path)
        if not item.raw_url:
            raise OpenListClientError(OpenListClientErrorKind.INVALID_RESPONSE)
        try:
            request = self._client.build_request("GET", item.raw_url)
            response = self._client.send(request, stream=True)
            self._check_status(response)
            return cast(BinaryIO, _HttpxStream(response))
        except self._httpx.TimeoutException as error:
            raise OpenListClientError(OpenListClientErrorKind.TIMEOUT, cause=error) from error
        except self._httpx.TransportError as error:
            raise OpenListClientError(
                OpenListClientErrorKind.CONNECTION_LOST, cause=error
            ) from error

    def upload(self, path: str, data: WriteSource, *, overwrite: bool) -> None:
        if not overwrite:
            self._ensure_absent(path)
        headers = {"File-Path": quote(path, safe="/"), "As-Task": "false"}
        response = self._request("PUT", "/api/fs/put", headers=headers, content=self._chunks(data))
        self._envelope(response)

    def create_directory(self, path: str) -> None:
        self._json("POST", "/api/fs/mkdir", {"path": path})

    def rename(self, path: str, name: str, *, overwrite: bool) -> None:
        self._json("POST", "/api/fs/rename", {"path": path, "name": name, "overwrite": overwrite})

    def move(self, source: str, target: str, *, overwrite: bool) -> None:
        self._move_copy("move", source, target, overwrite)

    def copy(self, source: str, target: str, *, overwrite: bool) -> None:
        if PurePosixPath(source).name != PurePosixPath(target).name:
            with self.open_read(source) as stream:
                self.upload(target, stream, overwrite=overwrite)
            return
        self._move_copy("copy", source, target, overwrite)

    def delete(self, path: str) -> None:
        self._json(
            "POST",
            "/api/fs/remove",
            {"dir": str(PurePosixPath(path).parent), "names": [PurePosixPath(path).name]},
        )

    def close(self) -> None:
        self._client.close()

    def _move_copy(self, operation: str, source: str, target: str, overwrite: bool) -> None:
        source_path, target_path = PurePosixPath(source), PurePosixPath(target)
        if source_path.name != target_path.name:
            if operation != "move" or source_path.parent != target_path.parent:
                raise OpenListClientError(OpenListClientErrorKind.INVALID_REQUEST)
            self.rename(source, target_path.name, overwrite=overwrite)
            return
        self._json(
            "POST",
            f"/api/fs/{operation}",
            {
                "src_dir": str(source_path.parent),
                "dst_dir": str(target_path.parent),
                "names": [source_path.name],
                "overwrite": overwrite,
                "skip_existing": False,
            },
        )

    def _ensure_absent(self, path: str) -> None:
        try:
            self.stat(path)
        except OpenListClientError as error:
            if error.kind is OpenListClientErrorKind.NOT_FOUND:
                return
            raise
        raise OpenListClientError(OpenListClientErrorKind.ALREADY_EXISTS)

    @staticmethod
    def _chunks(data: WriteSource) -> Iterator[bytes]:
        if isinstance(data, bytes | bytearray | memoryview):
            yield bytes(data)
            return
        while chunk := data.read(1024 * 1024):
            yield chunk

    def _json(self, method: str, endpoint: str, body: dict[str, object]) -> object:
        return self._envelope(self._request(method, endpoint, json=body))

    def _request(self, method: str, endpoint: str, *, envelope: bool = True, **kwargs: object):
        del envelope
        try:
            response = self._client.request(method, f"{self._base_url}{endpoint}", **kwargs)
            self._check_status(response)
            return response
        except self._httpx.TimeoutException as error:
            raise OpenListClientError(OpenListClientErrorKind.TIMEOUT, cause=error) from error
        except self._httpx.ConnectError as error:
            raise OpenListClientError(
                OpenListClientErrorKind.CONNECTION_FAILED, cause=error
            ) from error
        except self._httpx.TransportError as error:
            raise OpenListClientError(
                OpenListClientErrorKind.CONNECTION_LOST, cause=error
            ) from error

    def _check_status(self, response: object) -> None:
        status = response.status_code
        if 200 <= status < 300:
            return
        retry_after = response.headers.get("Retry-After")
        delay = float(retry_after) if retry_after and retry_after.isdigit() else None
        kind = {
            400: OpenListClientErrorKind.INVALID_REQUEST,
            401: OpenListClientErrorKind.AUTHENTICATION_FAILED,
            403: OpenListClientErrorKind.PERMISSION_DENIED,
            404: OpenListClientErrorKind.NOT_FOUND,
            409: OpenListClientErrorKind.ALREADY_EXISTS,
            429: OpenListClientErrorKind.RATE_LIMITED,
        }.get(
            status,
            OpenListClientErrorKind.CONNECTION_LOST
            if status >= 500
            else OpenListClientErrorKind.UNKNOWN,
        )
        response.close()
        raise OpenListClientError(kind, retry_after=delay)

    def _envelope(self, response: object) -> object:
        try:
            payload = response.json()
        except (ValueError, TypeError) as error:
            raise OpenListClientError(
                OpenListClientErrorKind.INVALID_RESPONSE, cause=error
            ) from error
        finally:
            response.close()
        if not isinstance(payload, dict) or not isinstance(payload.get("code"), int):
            raise OpenListClientError(OpenListClientErrorKind.INVALID_RESPONSE)
        if payload["code"] != 200:
            self._raise_business(payload["code"], payload.get("message"))
        return payload.get("data")

    @staticmethod
    def _raise_business(code: int, message: object) -> None:
        text = message.lower() if isinstance(message, str) else ""
        if "not found" in text:
            kind = OpenListClientErrorKind.NOT_FOUND
        elif "exist" in text:
            kind = OpenListClientErrorKind.ALREADY_EXISTS
        elif code == 401:
            kind = OpenListClientErrorKind.AUTHENTICATION_FAILED
        elif code == 403:
            kind = OpenListClientErrorKind.PERMISSION_DENIED
        elif code == 404:
            kind = OpenListClientErrorKind.NOT_FOUND
        elif code == 409:
            kind = OpenListClientErrorKind.ALREADY_EXISTS
        elif code == 429:
            kind = OpenListClientErrorKind.RATE_LIMITED
        elif code == 400:
            kind = OpenListClientErrorKind.INVALID_REQUEST
        elif code >= 500:
            kind = OpenListClientErrorKind.CONNECTION_LOST
        else:
            kind = OpenListClientErrorKind.UNKNOWN
        raise OpenListClientError(kind)

    @staticmethod
    def _entry(data: object, parent: str) -> OpenListClientEntry:
        if not isinstance(data, dict):
            raise OpenListClientError(OpenListClientErrorKind.INVALID_RESPONSE)
        try:
            name, size, is_directory, modified = (
                data["name"],
                data["size"],
                data["is_dir"],
                data["modified"],
            )
            if (
                not isinstance(name, str)
                or not isinstance(size, int)
                or not isinstance(is_directory, bool)
                or not isinstance(modified, str)
            ):
                raise TypeError
            timestamp = datetime.fromisoformat(modified.replace("Z", "+00:00")).astimezone(UTC)
        except (KeyError, TypeError, ValueError) as error:
            raise OpenListClientError(
                OpenListClientErrorKind.INVALID_RESPONSE, cause=error
            ) from error
        raw_url = data.get("raw_url")
        if raw_url is not None and not isinstance(raw_url, str):
            raise OpenListClientError(OpenListClientErrorKind.INVALID_RESPONSE)
        return OpenListClientEntry(
            name, f"{parent.rstrip('/')}/{name}", is_directory, size, timestamp, raw_url
        )


class _HttpxStream:
    def __init__(self, response: object) -> None:
        self._response = response
        self._iterator = response.iter_bytes()
        self._buffer = bytearray()
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            result = bytes(self._buffer) + b"".join(self._iterator)
            self._buffer.clear()
            return result
        while len(self._buffer) < size:
            try:
                self._buffer.extend(next(self._iterator))
            except StopIteration:
                break
        result = bytes(self._buffer[:size])
        del self._buffer[:size]
        return result

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self._response.close()

    def __enter__(self) -> _HttpxStream:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
