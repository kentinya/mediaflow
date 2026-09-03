from __future__ import annotations

import errno
import shutil
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import BinaryIO, Protocol, TypeVar, cast

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


@dataclass(frozen=True, repr=False)
class SMBStorageConfig:
    storage_id: str
    name: str
    host: str
    share_name: str
    username: str
    password: str
    domain: str | None = None
    root_path: str = ""
    port: int = 445
    read_only: bool = False
    connect_timeout: float = 30.0
    operation_timeout: float = 60.0
    max_concurrency: int = 4

    def __post_init__(self) -> None:
        required = (self.storage_id, self.name, self.host, self.share_name)
        if not all(required):
            raise ValueError("storage ID, name, host, and share name are required")
        if not 1 <= self.port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if self.connect_timeout <= 0 or self.operation_timeout <= 0:
            raise ValueError("timeouts must be positive")
        if self.max_concurrency < 1:
            raise ValueError("max_concurrency must be at least one")

    def __repr__(self) -> str:
        return (
            "SMBStorageConfig("
            f"storage_id={self.storage_id!r}, name={self.name!r}, host={self.host!r}, "
            f"share_name={self.share_name!r}, username={self.username!r}, "
            "password='********', "
            f"domain={self.domain!r}, root_path={self.root_path!r}, port={self.port!r}, "
            f"read_only={self.read_only!r}, connect_timeout={self.connect_timeout!r}, "
            f"operation_timeout={self.operation_timeout!r}, "
            f"max_concurrency={self.max_concurrency!r})"
        )


class SMBClientErrorKind(StrEnum):
    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"
    ALREADY_EXISTS = "already_exists"
    CONNECTION_FAILED = "connection_failed"
    CONNECTION_LOST = "connection_lost"
    AUTHENTICATION_FAILED = "authentication_failed"
    TIMEOUT = "timeout"
    IO_ERROR = "io_error"
    UNKNOWN = "unknown"


class SMBClientError(Exception):
    def __init__(
        self, kind: SMBClientErrorKind, message: str, *, cause: BaseException | None = None
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.cause = cause


@dataclass(frozen=True)
class SMBClientEntry:
    name: str
    path: str
    entry_type: StorageEntryType
    size: int
    modified_at: datetime


class SMBClient(Protocol):
    def connect(self, config: SMBStorageConfig) -> None: ...
    def close(self) -> None: ...
    def list(self, path: str) -> Sequence[SMBClientEntry]: ...
    def list_page(
        self, path: str, *, limit: int, cursor: str | None = None
    ) -> Sequence[SMBClientEntry]: ...
    def stat(self, path: str) -> SMBClientEntry: ...
    def open_read(self, path: str) -> BinaryIO: ...
    def open_write(self, path: str, *, overwrite: bool) -> BinaryIO: ...
    def create_directory(self, path: str) -> None: ...
    def move(self, source: str, target: str, *, overwrite: bool) -> None: ...
    def delete(self, path: str, *, directory: bool) -> None: ...


class _LeasedStream:
    def __init__(
        self,
        stream: BinaryIO,
        semaphore: threading.BoundedSemaphore,
        timed: Callable[[Callable[[], Result], float], Result],
        timeout: float,
    ) -> None:
        self._stream = stream
        self._semaphore = semaphore
        self._timed = timed
        self._timeout = timeout
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
        return self._timed(lambda: self._stream.read(size), self._timeout)

    def close(self) -> None:
        try:
            self._timed(self._stream.close, self._timeout)
        finally:
            if not self._released:
                self._released = True
                self._semaphore.release()


class SMBStorage:
    def __init__(self, config: SMBStorageConfig, client: SMBClient | None = None) -> None:
        self._config = config
        self._root_path = self._normalize_root(config.root_path)
        self._client = client or SmbProtocolClient()
        self._semaphore = threading.BoundedSemaphore(config.max_concurrency)
        self._connection_lock = threading.Lock()
        self._connected = False

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

    def connect(self) -> None:
        with self._connection_lock:
            if self._connected:
                return
            try:
                self._timed(
                    lambda: self._client.connect(self._config), self._config.connect_timeout
                )
            except SMBClientError as error:
                raise self._storage_error("connect", "", error) from error
            self._connected = True

    def close(self) -> None:
        with self._connection_lock:
            if self._connected:
                try:
                    self._client.close()
                except SMBClientError as error:
                    raise self._storage_error("close", "", error) from error
                finally:
                    self._connected = False

    def __enter__(self) -> SMBStorage:
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def list(self, path: str) -> Sequence[StorageEntry]:
        logical, remote = self._paths(path, "list")

        def operation() -> Sequence[StorageEntry]:
            return tuple(self._domain_entry(logical, item) for item in self._client.list(remote))

        return self._execute("list", path, operation, reconnect=True)

    def list_page(self, path: str, *, limit: int, cursor: str | None = None) -> StoragePage:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise StorageError(
                StorageErrorCode.INVALID_PATH,
                "list_page",
                path,
                "Storage page limit is invalid",
            )
        logical, remote = self._paths(path, "list_page")

        def operation() -> StoragePage:
            method = getattr(self._client, "list_page", None)
            if callable(method):
                values = tuple(method(remote, limit=limit, cursor=cursor))
            else:
                values = tuple(self._client.list(remote))
                if cursor is not None:
                    values = tuple(item for item in values if item.name > cursor)
                values = values[: limit + 1]
            values = tuple(sorted(values, key=lambda item: item.name))
            has_next = len(values) > limit
            selected = values[:limit]
            entries = tuple(self._domain_entry(logical, item) for item in selected)
            return StoragePage(entries, entries[-1].name if has_next and entries else None)

        return self._execute("list_page", path, operation, reconnect=True)

    def stat(self, path: str) -> StorageEntry:
        logical, remote = self._paths(path, "stat")
        return self._execute(
            "stat",
            path,
            lambda: self._domain_entry("", self._client.stat(remote), logical),
            reconnect=True,
        )

    def exists(self, path: str) -> bool:
        _, remote = self._paths(path, "exists")

        def operation() -> bool:
            try:
                self._client.stat(remote)
            except SMBClientError as error:
                if error.kind is SMBClientErrorKind.NOT_FOUND:
                    return False
                raise
            return True

        return self._execute("exists", path, operation, reconnect=True)

    def read(self, path: str) -> BinaryIO:
        _, remote = self._paths(path, "read")
        self._semaphore.acquire()
        try:
            self.connect()
            try:
                stream = self._timed(
                    lambda: self._client.open_read(remote), self._config.operation_timeout
                )
            except SMBClientError as error:
                if error.kind is SMBClientErrorKind.CONNECTION_LOST:
                    self._reconnect()
                    stream = self._timed(
                        lambda: self._client.open_read(remote), self._config.operation_timeout
                    )
                else:
                    raise
            leased = _LeasedStream(
                stream,
                self._semaphore,
                self._timed,
                self._config.operation_timeout,
            )
            return cast(BinaryIO, leased)
        except SMBClientError as error:
            self._semaphore.release()
            raise self._storage_error("read", path, error) from error
        except BaseException:
            self._semaphore.release()
            raise

    def write(self, path: str, data: WriteSource, *, overwrite: bool = False) -> None:
        self._ensure_writable("write", path)
        _, remote = self._paths(path, "write")

        def operation() -> None:
            with self._client.open_write(remote, overwrite=overwrite) as destination:
                if isinstance(data, bytes | bytearray | memoryview):
                    destination.write(data)
                else:
                    shutil.copyfileobj(data, destination, length=1024 * 1024)

        self._execute("write", path, operation)

    def create_directory(self, path: str) -> None:
        self._ensure_writable("create_directory", path)
        _, remote = self._paths(path, "create_directory")
        self._execute("create_directory", path, lambda: self._client.create_directory(remote))

    def copy(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self._ensure_writable("copy", target)
        _, remote_source = self._paths(source, "copy")
        _, remote_target = self._paths(target, "copy")

        def operation() -> None:
            with self._client.open_read(remote_source) as source_stream:
                with self._client.open_write(remote_target, overwrite=overwrite) as target_stream:
                    shutil.copyfileobj(source_stream, target_stream, length=1024 * 1024)

        self._execute("copy", source, operation)

    def move(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self._ensure_writable("move", source)
        _, remote_source = self._paths(source, "move")
        _, remote_target = self._paths(target, "move")
        self._execute(
            "move",
            source,
            lambda: self._client.move(remote_source, remote_target, overwrite=overwrite),
        )

    def delete(self, path: str) -> None:
        self._ensure_writable("delete", path)
        _, remote = self._paths(path, "delete")

        def operation() -> None:
            entry = self._client.stat(remote)
            self._client.delete(remote, directory=entry.entry_type is StorageEntryType.DIRECTORY)

        self._execute("delete", path, operation)

    def hard_link(self, source: str, target: str) -> None:
        self._ensure_writable("hard_link", target)
        self._unsupported("hard_link", target)

    def soft_link(self, source: str, target: str) -> None:
        self._ensure_writable("soft_link", target)
        self._unsupported("soft_link", target)

    def _execute(
        self,
        operation_name: str,
        path: str,
        operation: Callable[[], Result],
        *,
        reconnect: bool = False,
    ) -> Result:
        with self._semaphore:
            self.connect()
            try:
                return self._timed(operation, self._config.operation_timeout)
            except SMBClientError as error:
                if reconnect and error.kind is SMBClientErrorKind.CONNECTION_LOST:
                    self._reconnect()
                    try:
                        return self._timed(operation, self._config.operation_timeout)
                    except SMBClientError as retry_error:
                        raise self._storage_error(
                            operation_name, path, retry_error
                        ) from retry_error
                raise self._storage_error(operation_name, path, error) from error

    def _reconnect(self) -> None:
        with self._connection_lock:
            try:
                self._client.close()
            except SMBClientError:
                pass
            self._connected = False
        self.connect()

    def _timed(self, operation: Callable[[], Result], timeout: float) -> Result:
        completed = threading.Event()
        results: list[Result] = []
        errors: list[BaseException] = []

        def run() -> None:
            try:
                results.append(operation())
            except BaseException as error:
                errors.append(error)
            finally:
                completed.set()

        threading.Thread(target=run, daemon=True).start()
        if not completed.wait(timeout):
            try:
                self._client.close()
            except SMBClientError:
                pass
            self._connected = False
            raise SMBClientError(SMBClientErrorKind.TIMEOUT, "SMB operation timed out")
        if errors:
            raise errors[0]
        return results[0]

    def _paths(self, path: str, operation: str) -> tuple[str, str]:
        logical = self._normalize_path(path, operation)
        remote = str(PurePosixPath(self._root_path) / logical) if logical else self._root_path
        return logical, remote

    @staticmethod
    def _normalize_path(path: str, operation: str) -> str:
        if not isinstance(path, str) or "\x00" in path:
            raise StorageError(
                StorageErrorCode.INVALID_PATH, operation, str(path), "invalid SMB storage path"
            )
        portable = path.replace("\\", "/")
        if portable.startswith("//") or PurePosixPath(portable).is_absolute():
            raise StorageError(
                StorageErrorCode.INVALID_PATH,
                operation,
                path,
                "absolute and UNC paths are forbidden",
            )
        if len(portable) >= 2 and portable[1] == ":":
            raise StorageError(
                StorageErrorCode.INVALID_PATH, operation, path, "drive paths are forbidden"
            )
        parts: list[str] = []
        for part in PurePosixPath(portable).parts:
            if part in ("", "."):
                continue
            if part == "..":
                if not parts:
                    raise StorageError(
                        StorageErrorCode.PATH_TRAVERSAL,
                        operation,
                        path,
                        "SMB path escapes the configured root",
                    )
                parts.pop()
            else:
                parts.append(part)
        return "/".join(parts)

    @classmethod
    def _normalize_root(cls, root: str) -> str:
        return cls._normalize_path(root, "configure")

    @staticmethod
    def _domain_entry(
        parent: str, entry: SMBClientEntry, explicit_path: str | None = None
    ) -> StorageEntry:
        path = explicit_path
        if path is None:
            path = str(PurePosixPath(parent) / entry.name) if parent else entry.name
        return StorageEntry(entry.name, path, entry.entry_type, entry.size, entry.modified_at)

    def _ensure_writable(self, operation: str, path: str) -> None:
        if self.read_only:
            raise StorageError(
                StorageErrorCode.READ_ONLY,
                operation,
                path,
                f"storage {self.storage_id!r} is read-only",
            )

    @staticmethod
    def _unsupported(operation: str, path: str) -> None:
        raise StorageError(
            StorageErrorCode.UNSUPPORTED_OPERATION,
            operation,
            path,
            f"SMB operation {operation!r} is unsupported",
        )

    @staticmethod
    def _storage_error(operation: str, path: str, error: SMBClientError) -> StorageError:
        mapping = {
            SMBClientErrorKind.NOT_FOUND: StorageErrorCode.NOT_FOUND,
            SMBClientErrorKind.PERMISSION_DENIED: StorageErrorCode.PERMISSION_DENIED,
            SMBClientErrorKind.ALREADY_EXISTS: StorageErrorCode.ALREADY_EXISTS,
            SMBClientErrorKind.CONNECTION_FAILED: StorageErrorCode.CONNECTION_FAILED,
            SMBClientErrorKind.CONNECTION_LOST: StorageErrorCode.CONNECTION_LOST,
            SMBClientErrorKind.AUTHENTICATION_FAILED: StorageErrorCode.AUTHENTICATION_FAILED,
            SMBClientErrorKind.TIMEOUT: StorageErrorCode.TIMEOUT,
            SMBClientErrorKind.IO_ERROR: StorageErrorCode.IO_ERROR,
            SMBClientErrorKind.UNKNOWN: StorageErrorCode.UNKNOWN,
        }
        message = f"SMB {operation} failed ({error.kind.value})"
        return StorageError(mapping[error.kind], operation, path, message, cause=error)


class SmbProtocolClient:
    """Lazy adapter for smbprotocol's high-level smbclient API."""

    def __init__(self) -> None:
        self._module: object | None = None
        self._config: SMBStorageConfig | None = None

    def connect(self, config: SMBStorageConfig) -> None:
        try:
            import smbclient
        except ImportError as error:
            raise SMBClientError(
                SMBClientErrorKind.CONNECTION_FAILED,
                "SMB support is not installed; install the 'smb' project extra",
                cause=error,
            ) from error
        username = f"{config.domain}\\{config.username}" if config.domain else config.username
        try:
            smbclient.register_session(
                config.host,
                username=username or None,
                password=config.password or None,
                port=config.port,
                connection_timeout=config.connect_timeout,
            )
        except Exception as error:
            raise self._convert_error(error, connecting=True) from error
        self._module = smbclient
        self._config = config

    def close(self) -> None:
        if self._module is not None:
            try:
                if self._config is not None:
                    self._module.delete_session(  # type: ignore[attr-defined]
                        self._config.host,
                        port=self._config.port,
                        timeout=self._config.operation_timeout,
                    )
            except Exception as error:
                raise self._convert_error(error) from error
        self._module = None

    def list(self, path: str) -> Sequence[SMBClientEntry]:
        module, unc = self._request(path)
        try:
            with module.scandir(unc, **self._kwargs()) as entries:
                return tuple(self._entry(path, entry) for entry in entries)
        except Exception as error:
            raise self._convert_error(error) from error

    def list_page(
        self, path: str, *, limit: int, cursor: str | None = None
    ) -> Sequence[SMBClientEntry]:
        module, unc = self._request(path)
        try:
            with module.scandir(unc, **self._kwargs()) as entries:
                selected = []
                for entry in entries:
                    if cursor is None or entry.name > cursor:
                        selected.append(entry)
                    if len(selected) >= limit + 1:
                        break
                selected.sort(key=lambda entry: entry.name)
                return tuple(self._entry(path, entry) for entry in selected)
        except Exception as error:
            raise self._convert_error(error) from error

    def stat(self, path: str) -> SMBClientEntry:
        module, unc = self._request(path)
        try:
            result = module.stat(unc, **self._kwargs())
            name = PurePosixPath(path).name
            entry_type = (
                StorageEntryType.DIRECTORY
                if module.path.isdir(unc, **self._kwargs())
                else StorageEntryType.FILE
            )
            return SMBClientEntry(
                name, path, entry_type, result.st_size, datetime.fromtimestamp(result.st_mtime, UTC)
            )
        except Exception as error:
            raise self._convert_error(error) from error

    def open_read(self, path: str) -> BinaryIO:
        module, unc = self._request(path)
        try:
            return module.open_file(unc, mode="rb", **self._kwargs())
        except Exception as error:
            raise self._convert_error(error) from error

    def open_write(self, path: str, *, overwrite: bool) -> BinaryIO:
        module, unc = self._request(path)
        try:
            return module.open_file(unc, mode="wb" if overwrite else "xb", **self._kwargs())
        except Exception as error:
            raise self._convert_error(error) from error

    def create_directory(self, path: str) -> None:
        module, unc = self._request(path)
        try:
            module.makedirs(unc, exist_ok=True, **self._kwargs())
        except Exception as error:
            raise self._convert_error(error) from error

    def move(self, source: str, target: str, *, overwrite: bool) -> None:
        module, source_unc = self._request(source)
        _, target_unc = self._request(target)
        try:
            function = module.replace if overwrite else module.rename
            function(source_unc, target_unc, **self._kwargs())
        except Exception as error:
            raise self._convert_error(error) from error

    def delete(self, path: str, *, directory: bool) -> None:
        module, unc = self._request(path)
        try:
            (module.rmdir if directory else module.remove)(unc, **self._kwargs())
        except Exception as error:
            raise self._convert_error(error) from error

    def _request(self, path: str) -> tuple[object, str]:
        if self._module is None or self._config is None:
            raise SMBClientError(SMBClientErrorKind.CONNECTION_LOST, "SMB session is not connected")
        unc_path = path.replace("/", "\\")
        return self._module, f"\\\\{self._config.host}\\{self._config.share_name}\\{unc_path}"

    def _kwargs(self) -> dict[str, object]:
        if self._config is None:
            return {}
        return {
            "port": self._config.port,
            "connection_timeout": self._config.operation_timeout,
        }

    @staticmethod
    def _entry(parent: str, entry: object) -> SMBClientEntry:
        if entry.is_symlink():  # type: ignore[attr-defined]
            entry_type = StorageEntryType.SYMLINK
        elif entry.is_dir():  # type: ignore[attr-defined]
            entry_type = StorageEntryType.DIRECTORY
        else:
            entry_type = StorageEntryType.FILE
        name = entry.name  # type: ignore[attr-defined]
        path = str(PurePosixPath(parent) / name) if parent else name
        smb_info = getattr(entry, "smb_info", None)
        if smb_info is not None:
            return SMBClientEntry(
                name,
                path,
                entry_type,
                smb_info.end_of_file,
                smb_info.last_write_time.astimezone(UTC),
            )
        stat = entry.stat()  # type: ignore[attr-defined]
        return SMBClientEntry(
            name, path, entry_type, stat.st_size, datetime.fromtimestamp(stat.st_mtime, UTC)
        )

    @staticmethod
    def _convert_error(error: BaseException, *, connecting: bool = False) -> SMBClientError:
        name = type(error).__name__.lower()
        if isinstance(error, FileNotFoundError):
            kind = SMBClientErrorKind.NOT_FOUND
        elif isinstance(error, PermissionError):
            kind = SMBClientErrorKind.PERMISSION_DENIED
        elif isinstance(error, FileExistsError):
            kind = SMBClientErrorKind.ALREADY_EXISTS
        elif isinstance(error, OSError) and error.errno == errno.ENOENT:
            kind = SMBClientErrorKind.NOT_FOUND
        elif isinstance(error, OSError) and error.errno == errno.EEXIST:
            kind = SMBClientErrorKind.ALREADY_EXISTS
        elif isinstance(error, OSError) and error.errno in (errno.EACCES, errno.EPERM):
            kind = SMBClientErrorKind.PERMISSION_DENIED
        elif isinstance(error, OSError) and error.errno == errno.ETIMEDOUT:
            kind = SMBClientErrorKind.TIMEOUT
        elif isinstance(error, OSError) and error.errno in (
            errno.ECONNABORTED,
            errno.ECONNRESET,
            errno.ENOTCONN,
            errno.EPIPE,
        ):
            kind = SMBClientErrorKind.CONNECTION_LOST
        elif isinstance(error, OSError) and error.errno in (
            errno.ECONNREFUSED,
            errno.EHOSTUNREACH,
            errno.ENETUNREACH,
        ):
            kind = SMBClientErrorKind.CONNECTION_FAILED
        elif isinstance(error, TimeoutError) or "timeout" in name:
            kind = SMBClientErrorKind.TIMEOUT
        elif "password" in name or "logon" in name or "authentication" in name:
            kind = SMBClientErrorKind.AUTHENTICATION_FAILED
        elif "connectionclosed" in name or "connectionreset" in name or "transport" in name:
            kind = SMBClientErrorKind.CONNECTION_LOST
        elif connecting or isinstance(error, ConnectionError):
            kind = SMBClientErrorKind.CONNECTION_FAILED
        elif isinstance(error, OSError):
            kind = SMBClientErrorKind.IO_ERROR
        else:
            kind = SMBClientErrorKind.UNKNOWN
        return SMBClientError(kind, f"SMB request failed: {type(error).__name__}", cause=error)
