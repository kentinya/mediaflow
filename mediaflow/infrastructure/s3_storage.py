from __future__ import annotations

import io
import json
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import BinaryIO, Protocol, TypeVar, cast
from urllib.parse import urlparse

from mediaflow.domain.storage import (
    StorageCapabilities,
    StorageEntry,
    StorageEntryType,
    StorageError,
    StorageErrorCode,
    StoragePage,
    WriteSource,
)

Result = TypeVar("Result")


class S3Provider(StrEnum):
    AWS_S3 = "aws_s3"
    CLOUDFLARE_R2 = "cloudflare_r2"
    S3_COMPATIBLE = "s3_compatible"


@dataclass(frozen=True, repr=False)
class S3StorageConfig:
    storage_id: str
    name: str
    provider: S3Provider
    bucket: str
    access_key: str
    secret_key: str
    endpoint: str | None = None
    region: str | None = None
    session_token: str | None = None
    root_prefix: str = ""
    read_only: bool = False
    connect_timeout: float = 10.0
    request_timeout: float = 60.0
    max_concurrency: int = 4
    multipart_threshold: int = 64 * 1024 * 1024
    multipart_part_size: int = 16 * 1024 * 1024
    force_path_style: bool = False
    max_retries: int = 2
    page_size: int = 1000
    max_single_copy_size: int = 5 * 1024 * 1024 * 1024

    def __post_init__(self) -> None:
        if not all((self.storage_id, self.name, self.bucket, self.access_key, self.secret_key)):
            raise ValueError("storage ID, name, bucket, access key, and secret key are required")
        if "/" in self.bucket or self.bucket.startswith("s3:"):
            raise ValueError("bucket must be a bucket name")
        if self.provider is not S3Provider.AWS_S3 and not self.endpoint:
            raise ValueError("R2 and generic S3-compatible storage require an endpoint")
        if self.endpoint:
            parsed = urlparse(self.endpoint)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("endpoint must be an absolute HTTP(S) URL")
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("endpoint must not contain credentials, query, or fragment")
        if self.connect_timeout <= 0 or self.request_timeout <= 0:
            raise ValueError("timeouts must be positive")
        if self.max_concurrency < 1 or self.page_size < 1 or self.max_retries < 0:
            raise ValueError("concurrency/page size must be positive and retries non-negative")
        if self.multipart_threshold < 1 or self.multipart_part_size < 5 * 1024 * 1024:
            raise ValueError("multipart threshold must be positive and part size at least 5 MiB")

    @property
    def effective_region(self) -> str:
        if self.region:
            return self.region
        return "auto" if self.provider is S3Provider.CLOUDFLARE_R2 else "us-east-1"

    def __repr__(self) -> str:
        return (
            "S3StorageConfig("
            f"storage_id={self.storage_id!r}, name={self.name!r}, provider={self.provider!r}, "
            f"bucket={self.bucket!r}, endpoint={self.endpoint!r}, region={self.region!r}, "
            "access_key='********', secret_key='********', session_token='********', "
            f"root_prefix={self.root_prefix!r}, read_only={self.read_only!r}, "
            f"connect_timeout={self.connect_timeout!r}, request_timeout={self.request_timeout!r}, "
            f"max_concurrency={self.max_concurrency!r}, "
            f"multipart_threshold={self.multipart_threshold!r}, "
            f"multipart_part_size={self.multipart_part_size!r}, "
            f"force_path_style={self.force_path_style!r}, max_retries={self.max_retries!r})"
        )


class S3ClientErrorKind(StrEnum):
    NOT_FOUND = "not_found"
    BUCKET_NOT_FOUND = "bucket_not_found"
    PERMISSION_DENIED = "permission_denied"
    AUTHENTICATION_FAILED = "authentication_failed"
    ALREADY_EXISTS = "already_exists"
    INVALID_REQUEST = "invalid_request"
    CONNECTION_FAILED = "connection_failed"
    CONNECTION_LOST = "connection_lost"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    INVALID_RESPONSE = "invalid_response"
    IO_ERROR = "io_error"
    UNKNOWN = "unknown"


class S3ClientError(Exception):
    def __init__(
        self,
        kind: S3ClientErrorKind,
        message: str = "S3 request failed",
        *,
        retry_after: float | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.retry_after = retry_after
        self.cause = cause


@dataclass(frozen=True)
class S3ClientObject:
    key: str
    size: int
    modified_at: datetime
    etag: str | None = None


@dataclass(frozen=True)
class S3ListPage:
    objects: Sequence[S3ClientObject]
    common_prefixes: Sequence[str]
    next_token: str | None = None


class S3ClientAdapter(Protocol):
    def head_bucket(self) -> None: ...
    def list_objects(
        self,
        prefix: str,
        *,
        delimiter: str,
        token: str | None,
        max_keys: int,
        start_after: str | None = None,
    ) -> S3ListPage: ...
    def head_object(self, key: str) -> S3ClientObject: ...
    def get_object(self, key: str) -> BinaryIO: ...
    def put_object(
        self, key: str, data: WriteSource, *, content_type: str | None = None
    ) -> None: ...
    def create_multipart_upload(self, key: str) -> str: ...
    def upload_part(self, key: str, upload_id: str, part_number: int, data: bytes) -> str: ...
    def complete_multipart_upload(
        self, key: str, upload_id: str, parts: Sequence[tuple[int, str]]
    ) -> None: ...
    def abort_multipart_upload(self, key: str, upload_id: str) -> None: ...
    def copy_object(self, source_key: str, target_key: str) -> None: ...
    def delete_object(self, key: str) -> None: ...
    def close(self) -> None: ...


class _LeasedStream:
    def __init__(
        self, stream: BinaryIO, semaphore: threading.BoundedSemaphore, logical_path: str
    ) -> None:
        self._stream = stream
        self._semaphore = semaphore
        self._logical_path = logical_path
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
        try:
            return self._stream.read(size)
        except S3ClientError as error:
            raise S3Storage._storage_error("read", self._logical_path, error) from error

    def close(self) -> None:
        try:
            self._stream.close()
        finally:
            if not self._released:
                self._released = True
                self._semaphore.release()


class S3Storage:
    def __init__(
        self,
        config: S3StorageConfig,
        client: S3ClientAdapter | None = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._config = config
        self._root = self._normalize_root(config.root_prefix)
        self._client = client or Boto3S3Client(config)
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
        self._execute("health_check", "", self._client.head_bucket, retry=True)
        self._execute(
            "health_check",
            "",
            lambda: self._client.list_objects(
                self._directory_key(""), delimiter="/", token=None, max_keys=1
            ),
            retry=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> S3Storage:
        self.health_check()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def list(self, path: str) -> Sequence[StorageEntry]:
        logical, _ = self._paths(path, "list")
        prefix = self._directory_key(logical)

        def operation() -> Sequence[StorageEntry]:
            if logical and not self._directory_exists(prefix):
                raise S3ClientError(S3ClientErrorKind.NOT_FOUND)
            entries: dict[str, StorageEntry] = {}
            token: str | None = None
            seen: set[str] = set()
            while True:
                page = self._client.list_objects(
                    prefix, delimiter="/", token=token, max_keys=self._config.page_size
                )
                for common_prefix in page.common_prefixes:
                    name = common_prefix[len(prefix) :].rstrip("/")
                    if name:
                        item_path = "/".join(filter(None, (logical, name)))
                        entries[item_path] = self._directory_entry(item_path)
                for item in page.objects:
                    if item.key == prefix:
                        continue
                    relative = item.key[len(prefix) :]
                    if not relative or "/" in relative:
                        continue
                    item_path = "/".join(filter(None, (logical, relative)))
                    entries[item_path] = self._file_entry(item_path, item)
                if not page.next_token:
                    break
                if page.next_token in seen:
                    raise S3ClientError(S3ClientErrorKind.INVALID_RESPONSE)
                seen.add(page.next_token)
                token = page.next_token
            return tuple(entries[key] for key in sorted(entries))

        return self._execute("list", path, operation, retry=True)

    def list_page(self, path: str, *, limit: int, cursor: str | None = None) -> StoragePage:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise StorageError(
                StorageErrorCode.INVALID_PATH,
                "list_page",
                path,
                "Storage page limit is invalid",
            )
        logical, _ = self._paths(path, "list_page")
        prefix = self._directory_key(logical)
        cursor_kind = "f"
        cursor_name = cursor
        provider_token = None
        if isinstance(cursor, str) and cursor.startswith("{"):
            try:
                marker = json.loads(cursor)
            except json.JSONDecodeError as error:
                raise StorageError(
                    StorageErrorCode.INVALID_PATH,
                    "list_page",
                    path,
                    "Storage page cursor is invalid",
                ) from error
            if not isinstance(marker, dict):
                raise StorageError(
                    StorageErrorCode.INVALID_PATH,
                    "list_page",
                    path,
                    "Storage page cursor is invalid",
                )
            cursor_kind = marker.get("kind", "")
            cursor_name = marker.get("name")
            provider_token = marker.get("token")
        elif isinstance(cursor, str) and cursor[:2] in {"d:", "f:"}:
            cursor_kind, cursor_name = cursor[0], cursor[2:]
        if cursor is not None and (
            not isinstance(cursor, str)
            or not cursor_name
            or "\x00" in cursor
            or "/" in cursor_name
            or cursor_kind not in {"d", "f"}
            or (provider_token is not None and not isinstance(provider_token, str))
        ):
            raise StorageError(
                StorageErrorCode.INVALID_PATH,
                "list_page",
                path,
                "Storage page cursor is invalid",
            )
        start_after = (
            prefix + cursor_name + ("/" if cursor_kind == "d" else "")
            if cursor_name is not None and provider_token is None
            else None
        )

        def operation() -> StoragePage:
            if logical and not self._directory_exists(prefix):
                raise S3ClientError(S3ClientErrorKind.NOT_FOUND)
            arguments = {
                "delimiter": "/",
                "token": provider_token,
                "max_keys": min(limit + 1, self._config.page_size),
            }
            if start_after is not None:
                arguments["start_after"] = start_after
            try:
                page = self._client.list_objects(prefix, **arguments)
            except TypeError:
                # Preserve compatibility with injected pre-pagination fakes.
                if start_after is None:
                    raise
                page = self._client.list_objects(
                    prefix,
                    delimiter="/",
                    token=None,
                    max_keys=min(limit + 1, self._config.page_size),
                )
            entries: dict[str, StorageEntry] = {}
            for common_prefix in page.common_prefixes:
                if not common_prefix.startswith(prefix):
                    raise S3ClientError(S3ClientErrorKind.INVALID_RESPONSE)
                name = common_prefix[len(prefix) :].rstrip("/")
                if name:
                    item_path = "/".join(filter(None, (logical, name)))
                    entries[item_path] = self._directory_entry(item_path)
            for item in page.objects:
                if item.key == prefix:
                    continue
                if not item.key.startswith(prefix):
                    raise S3ClientError(S3ClientErrorKind.INVALID_RESPONSE)
                relative = item.key[len(prefix) :]
                if not relative or "/" in relative:
                    continue
                item_path = "/".join(filter(None, (logical, relative)))
                entries[item_path] = self._file_entry(item_path, item)
            values = tuple(entries[key] for key in sorted(entries))
            if cursor_name is not None:
                values = tuple(entry for entry in values if entry.name > cursor_name)
            selected = values[:limit]
            has_next = len(values) > limit or bool(page.next_token)
            next_adapter_cursor = None
            if has_next and selected:
                kind = "d" if selected[-1].entry_type is StorageEntryType.DIRECTORY else "f"
                if len(values) <= limit and page.next_token is not None:
                    next_adapter_cursor = json.dumps(
                        {
                            "v": 1,
                            "kind": kind,
                            "name": selected[-1].name,
                            "token": page.next_token,
                        },
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                else:
                    next_adapter_cursor = f"{kind}:{selected[-1].name}"
            return StoragePage(selected, next_adapter_cursor)

        return self._execute("list_page", path, operation, retry=True)

    def stat(self, path: str) -> StorageEntry:
        logical, key = self._paths(path, "stat")

        def operation() -> StorageEntry:
            if not logical:
                return self._directory_entry("")
            try:
                return self._file_entry(logical, self._client.head_object(key))
            except S3ClientError as error:
                if error.kind is not S3ClientErrorKind.NOT_FOUND:
                    raise
            marker = self._directory_key(logical)
            if self._directory_exists(marker):
                return self._directory_entry(logical)
            raise S3ClientError(S3ClientErrorKind.NOT_FOUND)

        return self._execute("stat", path, operation, retry=True)

    def exists(self, path: str) -> bool:
        try:
            self.stat(path)
        except StorageError as error:
            if error.code is StorageErrorCode.NOT_FOUND:
                return False
            raise
        return True

    def read(self, path: str) -> BinaryIO:
        _, key = self._paths(path, "read")
        self._semaphore.acquire()
        try:
            stream = self._retry(lambda: self._client.get_object(key))
            return cast(BinaryIO, _LeasedStream(stream, self._semaphore, path))
        except S3ClientError as error:
            self._semaphore.release()
            raise self._storage_error("read", path, error) from error
        except BaseException:
            self._semaphore.release()
            raise

    def write(self, path: str, data: WriteSource, *, overwrite: bool = False) -> None:
        self._ensure_writable("write", path)
        logical, key = self._paths(path, "write")
        if not logical:
            raise StorageError(StorageErrorCode.INVALID_PATH, "write", path, "invalid storage path")

        def operation() -> None:
            self._ensure_target_absent(key, overwrite)
            size = self._source_size(data)
            if size is not None and size < self._config.multipart_threshold:
                self._client.put_object(key, data)
            else:
                self._multipart_upload(key, data)

        self._execute("write", path, operation)

    def create_directory(self, path: str) -> None:
        self._ensure_writable("create_directory", path)
        logical, key = self._paths(path, "create_directory")
        if not logical:
            raise StorageError(
                StorageErrorCode.ALREADY_EXISTS, "create_directory", path, "directory exists"
            )

        def operation() -> None:
            try:
                self._client.head_object(key)
            except S3ClientError as error:
                if error.kind is not S3ClientErrorKind.NOT_FOUND:
                    raise
            else:
                raise S3ClientError(S3ClientErrorKind.ALREADY_EXISTS)
            marker = self._directory_key(logical)
            if self._directory_exists(marker):
                raise S3ClientError(S3ClientErrorKind.ALREADY_EXISTS)
            self._client.put_object(marker, b"", content_type="application/x-directory")

        self._execute("create_directory", path, operation)

    def copy(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self._ensure_writable("copy", source)
        source_logical, source_key = self._paths(source, "copy")
        target_logical, target_key = self._paths(target, "copy")

        def operation() -> None:
            source_entry = self._client.head_object(source_key)
            if not source_logical or not target_logical:
                raise S3ClientError(S3ClientErrorKind.INVALID_REQUEST)
            if source_entry.size > self._config.max_single_copy_size:
                raise StorageError(
                    StorageErrorCode.UNSUPPORTED_OPERATION,
                    "copy",
                    source,
                    "object exceeds configured single-copy limit",
                )
            self._ensure_target_absent(target_key, overwrite)
            self._client.copy_object(source_key, target_key)

        self._execute("copy", source, operation)

    def move(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self._ensure_writable("move", source)
        source_logical, source_key = self._paths(source, "move")
        target_logical, target_key = self._paths(target, "move")

        def operation() -> None:
            source_entry = self._client.head_object(source_key)
            if not source_logical or not target_logical:
                raise S3ClientError(S3ClientErrorKind.INVALID_REQUEST)
            if source_entry.size > self._config.max_single_copy_size:
                raise StorageError(
                    StorageErrorCode.UNSUPPORTED_OPERATION,
                    "move",
                    source,
                    "object exceeds configured single-copy limit",
                )
            self._ensure_target_absent(target_key, overwrite)
            self._client.copy_object(source_key, target_key)
            try:
                target_entry = self._client.head_object(target_key)
            except S3ClientError as error:
                raise S3ClientError(S3ClientErrorKind.IO_ERROR) from error
            if target_entry.size != source_entry.size:
                raise S3ClientError(S3ClientErrorKind.IO_ERROR)
            try:
                self._client.delete_object(source_key)
            except S3ClientError as error:
                raise StorageError(
                    StorageErrorCode.IO_ERROR,
                    "move",
                    source,
                    "S3 move partially completed: target exists and source may remain",
                    cause=error,
                ) from error

        self._execute("move", source, operation)

    def delete(self, path: str) -> None:
        self._ensure_writable("delete", path)
        logical, key = self._paths(path, "delete")
        if not logical:
            raise StorageError(
                StorageErrorCode.PERMISSION_DENIED, "delete", path, "cannot delete root"
            )

        def operation() -> None:
            try:
                self._client.head_object(key)
            except S3ClientError as error:
                if error.kind is not S3ClientErrorKind.NOT_FOUND:
                    raise
            else:
                self._client.delete_object(key)
                return
            marker = self._directory_key(logical)
            if not self._directory_exists(marker):
                raise S3ClientError(S3ClientErrorKind.NOT_FOUND)
            page = self._client.list_objects(marker, delimiter="/", token=None, max_keys=2)
            children = [item for item in page.objects if item.key != marker]
            if children or page.common_prefixes:
                raise S3ClientError(S3ClientErrorKind.ALREADY_EXISTS)
            try:
                self._client.head_object(marker)
            except S3ClientError as error:
                if error.kind is S3ClientErrorKind.NOT_FOUND:
                    raise S3ClientError(S3ClientErrorKind.UNSUPPORTED_OPERATION) from error
                raise
            self._client.delete_object(marker)

        self._execute("delete", path, operation)

    def hard_link(self, source: str, target: str) -> None:
        self._unsupported("hard_link", target)

    def soft_link(self, source: str, target: str) -> None:
        self._unsupported("soft_link", target)

    def _directory_exists(self, marker: str) -> bool:
        try:
            self._client.head_object(marker)
            return True
        except S3ClientError as error:
            if error.kind is not S3ClientErrorKind.NOT_FOUND:
                raise
        page = self._client.list_objects(marker, delimiter="/", token=None, max_keys=1)
        return bool(page.objects or page.common_prefixes)

    def _ensure_target_absent(self, key: str, overwrite: bool) -> None:
        if overwrite:
            return
        try:
            self._client.head_object(key)
        except S3ClientError as error:
            if error.kind is S3ClientErrorKind.NOT_FOUND:
                marker = f"{key.rstrip('/')}/"
                if marker != key and self._directory_exists(marker):
                    raise S3ClientError(S3ClientErrorKind.ALREADY_EXISTS) from error
                return
            raise
        raise S3ClientError(S3ClientErrorKind.ALREADY_EXISTS)

    def _multipart_upload(self, key: str, data: WriteSource) -> None:
        upload_id = self._client.create_multipart_upload(key)
        parts: list[tuple[int, str]] = []
        stream = (
            io.BytesIO(bytes(data)) if isinstance(data, bytes | bytearray | memoryview) else data
        )
        try:
            part_number = 1
            while chunk := stream.read(self._config.multipart_part_size):
                etag = self._client.upload_part(key, upload_id, part_number, chunk)
                parts.append((part_number, etag))
                part_number += 1
            self._client.complete_multipart_upload(key, upload_id, parts)
        except BaseException:
            try:
                self._client.abort_multipart_upload(key, upload_id)
            except S3ClientError:
                pass
            raise

    @staticmethod
    def _source_size(data: WriteSource) -> int | None:
        if isinstance(data, bytes | bytearray | memoryview):
            return len(data)
        try:
            position = data.tell()
            data.seek(0, io.SEEK_END)
            size = data.tell() - position
            data.seek(position)
            return size
        except (AttributeError, OSError, io.UnsupportedOperation):
            return None

    def _execute(
        self, operation: str, path: str, call: Callable[[], Result], *, retry: bool = False
    ) -> Result:
        with self._semaphore:
            try:
                return self._retry(call) if retry else call()
            except S3ClientError as error:
                raise self._storage_error(operation, path, error) from error

    def _retry(self, call: Callable[[], Result]) -> Result:
        temporary = {
            S3ClientErrorKind.CONNECTION_FAILED,
            S3ClientErrorKind.CONNECTION_LOST,
            S3ClientErrorKind.TIMEOUT,
            S3ClientErrorKind.RATE_LIMITED,
        }
        for attempt in range(self._config.max_retries + 1):
            try:
                return call()
            except S3ClientError as error:
                if error.kind not in temporary or attempt == self._config.max_retries:
                    raise
                delay = error.retry_after if error.retry_after is not None else 0.1 * (2**attempt)
                self._sleep(min(max(delay, 0), 30))
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
        return logical, f"{self._root}{logical}"

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
    def _normalize_root(prefix: str) -> str:
        value = prefix.replace("\\", "/")
        if value.startswith("/") or "\x00" in value or urlparse(value).scheme:
            raise ValueError("invalid root prefix")
        parts: list[str] = []
        for part in value.split("/"):
            if part in {"", "."}:
                continue
            if part == "..":
                if not parts:
                    raise ValueError("root prefix traversal")
                parts.pop()
            else:
                parts.append(part)
        return "" if not parts else "/".join(parts) + "/"

    def _directory_key(self, logical: str) -> str:
        key = f"{self._root}{logical}".rstrip("/")
        return f"{key}/" if key else ""

    @staticmethod
    def _file_entry(logical: str, item: S3ClientObject) -> StorageEntry:
        return StorageEntry(
            PurePosixPath(logical).name,
            logical,
            StorageEntryType.FILE,
            max(item.size, 0),
            item.modified_at,
        )

    @staticmethod
    def _directory_entry(logical: str) -> StorageEntry:
        return StorageEntry(
            PurePosixPath(logical).name if logical else "",
            logical,
            StorageEntryType.DIRECTORY,
            0,
            datetime.fromtimestamp(0, UTC),
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
    def _storage_error(operation: str, path: str, error: S3ClientError) -> StorageError:
        mapping = {
            S3ClientErrorKind.NOT_FOUND: StorageErrorCode.NOT_FOUND,
            S3ClientErrorKind.BUCKET_NOT_FOUND: StorageErrorCode.NOT_FOUND,
            S3ClientErrorKind.PERMISSION_DENIED: StorageErrorCode.PERMISSION_DENIED,
            S3ClientErrorKind.AUTHENTICATION_FAILED: StorageErrorCode.AUTHENTICATION_FAILED,
            S3ClientErrorKind.ALREADY_EXISTS: StorageErrorCode.ALREADY_EXISTS,
            S3ClientErrorKind.INVALID_REQUEST: StorageErrorCode.INVALID_PATH,
            S3ClientErrorKind.CONNECTION_FAILED: StorageErrorCode.CONNECTION_FAILED,
            S3ClientErrorKind.CONNECTION_LOST: StorageErrorCode.CONNECTION_LOST,
            S3ClientErrorKind.TIMEOUT: StorageErrorCode.TIMEOUT,
            S3ClientErrorKind.RATE_LIMITED: StorageErrorCode.RATE_LIMITED,
            S3ClientErrorKind.INVALID_RESPONSE: StorageErrorCode.IO_ERROR,
            S3ClientErrorKind.IO_ERROR: StorageErrorCode.IO_ERROR,
            S3ClientErrorKind.UNKNOWN: StorageErrorCode.UNKNOWN,
        }
        code = mapping[error.kind]
        return StorageError(
            code, operation, path, f"S3 {operation} failed: {code.value}", cause=error
        )


class Boto3S3Client:
    def __init__(self, config: S3StorageConfig) -> None:
        try:
            import boto3
            from botocore.config import Config
        except ImportError as error:
            raise RuntimeError("install mediaflow[s3] to use S3Storage") from error
        self._bucket = config.bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=config.endpoint,
            region_name=config.effective_region,
            aws_access_key_id=config.access_key,
            aws_secret_access_key=config.secret_key,
            aws_session_token=config.session_token,
            config=Config(
                connect_timeout=config.connect_timeout,
                read_timeout=config.request_timeout,
                max_pool_connections=config.max_concurrency,
                retries={"total_max_attempts": 1, "mode": "standard"},
                s3={"addressing_style": "path" if config.force_path_style else "auto"},
            ),
        )

    def head_bucket(self) -> None:
        self._call(self._client.head_bucket, Bucket=self._bucket)

    def list_objects(
        self,
        prefix: str,
        *,
        delimiter: str,
        token: str | None,
        max_keys: int,
        start_after: str | None = None,
    ) -> S3ListPage:
        params: dict[str, object] = {
            "Bucket": self._bucket,
            "Prefix": prefix,
            "Delimiter": delimiter,
            "MaxKeys": max_keys,
        }
        if token:
            params["ContinuationToken"] = token
        if start_after:
            params["StartAfter"] = start_after
        response = self._call(self._client.list_objects_v2, **params)
        try:
            objects = tuple(
                S3ClientObject(
                    item["Key"],
                    item["Size"],
                    item["LastModified"].astimezone(UTC),
                    item.get("ETag"),
                )
                for item in response.get("Contents", ())
            )
            prefixes = tuple(item["Prefix"] for item in response.get("CommonPrefixes", ()))
            next_token = response.get("NextContinuationToken")
            if next_token is not None and not isinstance(next_token, str):
                raise TypeError
            return S3ListPage(objects, prefixes, next_token)
        except (KeyError, TypeError, AttributeError) as error:
            raise S3ClientError(S3ClientErrorKind.INVALID_RESPONSE, cause=error) from error

    def head_object(self, key: str) -> S3ClientObject:
        response = self._call(self._client.head_object, Bucket=self._bucket, Key=key)
        try:
            return S3ClientObject(
                key,
                response["ContentLength"],
                response["LastModified"].astimezone(UTC),
                response.get("ETag"),
            )
        except (KeyError, TypeError, AttributeError) as error:
            raise S3ClientError(S3ClientErrorKind.INVALID_RESPONSE, cause=error) from error

    def get_object(self, key: str) -> BinaryIO:
        response = self._call(self._client.get_object, Bucket=self._bucket, Key=key)
        try:
            return cast(BinaryIO, _BotoStreamingBody(response["Body"]))
        except (KeyError, TypeError) as error:
            raise S3ClientError(S3ClientErrorKind.INVALID_RESPONSE, cause=error) from error

    def put_object(self, key: str, data: WriteSource, *, content_type: str | None = None) -> None:
        params: dict[str, object] = {"Bucket": self._bucket, "Key": key, "Body": data}
        if content_type:
            params["ContentType"] = content_type
        self._call(self._client.put_object, **params)

    def create_multipart_upload(self, key: str) -> str:
        response = self._call(self._client.create_multipart_upload, Bucket=self._bucket, Key=key)
        upload_id = response.get("UploadId")
        if not isinstance(upload_id, str):
            raise S3ClientError(S3ClientErrorKind.INVALID_RESPONSE)
        return upload_id

    def upload_part(self, key: str, upload_id: str, part_number: int, data: bytes) -> str:
        response = self._call(
            self._client.upload_part,
            Bucket=self._bucket,
            Key=key,
            UploadId=upload_id,
            PartNumber=part_number,
            Body=data,
        )
        etag = response.get("ETag")
        if not isinstance(etag, str):
            raise S3ClientError(S3ClientErrorKind.INVALID_RESPONSE)
        return etag

    def complete_multipart_upload(
        self, key: str, upload_id: str, parts: Sequence[tuple[int, str]]
    ) -> None:
        body = {"Parts": [{"PartNumber": number, "ETag": etag} for number, etag in parts]}
        self._call(
            self._client.complete_multipart_upload,
            Bucket=self._bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload=body,
        )

    def abort_multipart_upload(self, key: str, upload_id: str) -> None:
        self._call(
            self._client.abort_multipart_upload, Bucket=self._bucket, Key=key, UploadId=upload_id
        )

    def copy_object(self, source_key: str, target_key: str) -> None:
        self._call(
            self._client.copy_object,
            Bucket=self._bucket,
            Key=target_key,
            CopySource={"Bucket": self._bucket, "Key": source_key},
        )

    def delete_object(self, key: str) -> None:
        self._call(self._client.delete_object, Bucket=self._bucket, Key=key)

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _call(method: Callable[..., Result], **kwargs: object) -> Result:
        try:
            return method(**kwargs)
        except BaseException as error:
            raise Boto3S3Client._map_error(error) from error

    @staticmethod
    def _map_error(error: BaseException) -> S3ClientError:
        response = getattr(error, "response", None)
        code = ""
        status = None
        retry_after = None
        if isinstance(response, dict):
            detail = response.get("Error", {})
            if isinstance(detail, dict):
                code = str(detail.get("Code", ""))
            metadata = response.get("ResponseMetadata", {})
            if isinstance(metadata, dict):
                status = metadata.get("HTTPStatusCode")
                headers = metadata.get("HTTPHeaders", {})
                if isinstance(headers, dict):
                    value = headers.get("retry-after")
                    retry_after = (
                        float(value) if isinstance(value, str) and value.isdigit() else None
                    )
        auth = {"InvalidAccessKeyId", "SignatureDoesNotMatch", "ExpiredToken", "InvalidToken"}
        missing = {"NoSuchKey", "NotFound", "NoSuchUpload"}
        if code == "NoSuchBucket":
            kind = S3ClientErrorKind.BUCKET_NOT_FOUND
        elif (
            code in auth
            or status == 401
            or error.__class__.__name__
            in {
                "NoCredentialsError",
                "PartialCredentialsError",
                "CredentialRetrievalError",
            }
        ):
            kind = S3ClientErrorKind.AUTHENTICATION_FAILED
        elif code in missing or status == 404:
            kind = S3ClientErrorKind.NOT_FOUND
        elif code in {"AccessDenied", "Forbidden"} or status == 403:
            kind = S3ClientErrorKind.PERMISSION_DENIED
        elif code in {"PreconditionFailed", "Conflict"} or status in {409, 412}:
            kind = S3ClientErrorKind.ALREADY_EXISTS
        elif code in {"SlowDown", "Throttling", "TooManyRequestsException"} or status == 429:
            kind = S3ClientErrorKind.RATE_LIMITED
        elif code in {"RequestTimeout", "RequestExpired"} or error.__class__.__name__ in {
            "ConnectTimeoutError",
            "ReadTimeoutError",
        }:
            kind = S3ClientErrorKind.TIMEOUT
        elif error.__class__.__name__ in {"EndpointConnectionError", "ProxyConnectionError"}:
            kind = S3ClientErrorKind.CONNECTION_FAILED
        elif code in {"ServiceUnavailable", "InternalError"} or (
            isinstance(status, int) and status >= 500
        ):
            kind = S3ClientErrorKind.CONNECTION_LOST
        elif error.__class__.__name__ in {"ConnectionClosedError", "HTTPClientError"}:
            kind = S3ClientErrorKind.CONNECTION_LOST
        else:
            kind = S3ClientErrorKind.UNKNOWN
        return S3ClientError(kind, retry_after=retry_after, cause=error)


class _BotoStreamingBody:
    def __init__(self, body: object) -> None:
        self._body = body

    @property
    def closed(self) -> bool:
        return bool(getattr(self._body, "closed", False))

    def read(self, size: int = -1) -> bytes:
        try:
            return self._body.read(size)
        except Exception as error:
            raise Boto3S3Client._map_error(error) from error

    def close(self) -> None:
        self._body.close()

    def __enter__(self) -> _BotoStreamingBody:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
