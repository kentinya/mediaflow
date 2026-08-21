from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import BinaryIO, Protocol, TypeAlias


class StorageEntryType(StrEnum):
    FILE = "file"
    DIRECTORY = "directory"
    SYMLINK = "symlink"
    OTHER = "other"


class StorageErrorCode(StrEnum):
    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"
    ALREADY_EXISTS = "already_exists"
    INVALID_PATH = "invalid_path"
    PATH_TRAVERSAL = "path_traversal"
    READ_ONLY = "read_only"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    CONNECTION_FAILED = "connection_failed"
    CONNECTION_LOST = "connection_lost"
    AUTHENTICATION_FAILED = "authentication_failed"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    IO_ERROR = "io_error"
    UNKNOWN = "unknown"


class StorageError(Exception):
    def __init__(
        self,
        code: StorageErrorCode,
        operation: str,
        path: str,
        message: str,
        *,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.operation = operation
        self.path = path
        self.cause = cause


@dataclass(frozen=True)
class StorageCapabilities:
    can_move: bool = False
    can_copy: bool = False
    can_delete: bool = False
    can_hard_link: bool = False
    can_soft_link: bool = False


@dataclass(frozen=True)
class StorageEntry:
    name: str
    path: str
    entry_type: StorageEntryType
    size: int
    modified_at: datetime

    @property
    def exists(self) -> bool:
        return True

    @property
    def is_directory(self) -> bool:
        return self.entry_type is StorageEntryType.DIRECTORY


WriteSource: TypeAlias = bytes | bytearray | memoryview | BinaryIO


class Storage(Protocol):
    @property
    def storage_id(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def read_only(self) -> bool: ...

    @property
    def capabilities(self) -> StorageCapabilities: ...

    def list(self, path: str) -> Sequence[StorageEntry]: ...
    def stat(self, path: str) -> StorageEntry: ...
    def exists(self, path: str) -> bool: ...
    def read(self, path: str) -> BinaryIO: ...
    def write(self, path: str, data: WriteSource, *, overwrite: bool = False) -> None: ...
    def create_directory(self, path: str) -> None: ...
    def move(self, source: str, target: str, *, overwrite: bool = False) -> None: ...
    def copy(self, source: str, target: str, *, overwrite: bool = False) -> None: ...
    def delete(self, path: str) -> None: ...
    def hard_link(self, source: str, target: str) -> None: ...
    def soft_link(self, source: str, target: str) -> None: ...
