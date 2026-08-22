from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import BinaryIO, TypeVar

from mediaflow.domain.storage import (
    StorageCapabilities,
    StorageEntry,
    StorageEntryType,
    StorageError,
    StorageErrorCode,
    WriteSource,
)

Result = TypeVar("Result")


class InvalidStoragePath(StorageError):
    """Compatibility name for callers of the bootstrap path error."""


class LocalStorage:
    def __init__(
        self,
        storage_id: str,
        root: str | Path,
        *,
        name: str | None = None,
        read_only: bool = False,
    ) -> None:
        if not storage_id:
            raise ValueError("storage_id must not be empty")
        try:
            resolved_root = Path(root).resolve(strict=True)
        except OSError as error:
            raise self._mapped_error("configure", str(root), error) from error
        if not resolved_root.is_dir():
            raise StorageError(
                StorageErrorCode.INVALID_PATH,
                "configure",
                str(root),
                "storage root must be a directory",
            )
        self._storage_id = storage_id
        self._name = name or storage_id
        self._root = resolved_root
        self._read_only = read_only

    @property
    def storage_id(self) -> str:
        return self._storage_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def read_only(self) -> bool:
        return self._read_only

    @property
    def capabilities(self) -> StorageCapabilities:
        writable = not self._read_only
        return StorageCapabilities(
            can_move=writable,
            can_copy=writable,
            can_delete=writable,
            can_hard_link=writable and self._can_hard_link(),
            can_soft_link=writable and self._can_soft_link(),
        )

    def _resolve(self, path: str, operation: str) -> Path:
        if not isinstance(path, str) or "\x00" in path:
            raise InvalidStoragePath(
                StorageErrorCode.INVALID_PATH,
                operation,
                str(path),
                "storage path must be a string without null bytes",
            )
        portable_path = path.replace("\\", "/")
        logical = PurePosixPath(portable_path)
        if logical.is_absolute() or (len(portable_path) >= 2 and portable_path[1] == ":"):
            raise InvalidStoragePath(
                StorageErrorCode.INVALID_PATH,
                operation,
                path,
                "absolute storage paths are not allowed",
            )
        parts: list[str] = []
        for part in logical.parts:
            if part in ("", "."):
                continue
            if part == "..":
                if not parts:
                    raise InvalidStoragePath(
                        StorageErrorCode.PATH_TRAVERSAL,
                        operation,
                        path,
                        "storage path escapes its root",
                    )
                parts.pop()
            else:
                parts.append(part)
        candidate = self._root.joinpath(*parts)
        try:
            resolved = candidate.resolve(strict=False)
        except OSError as error:
            raise self._mapped_error(operation, path, error) from error
        if resolved != self._root and self._root not in resolved.parents:
            raise InvalidStoragePath(
                StorageErrorCode.PATH_TRAVERSAL,
                operation,
                path,
                "storage path escapes its root through a symbolic link",
            )
        return candidate

    def _entry(self, logical_path: str, item: Path) -> StorageEntry:
        stat = item.lstat()
        if item.is_symlink():
            entry_type = StorageEntryType.SYMLINK
        elif item.is_file():
            entry_type = StorageEntryType.FILE
        elif item.is_dir():
            entry_type = StorageEntryType.DIRECTORY
        else:
            entry_type = StorageEntryType.OTHER
        return StorageEntry(
            name=item.name,
            path=logical_path,
            entry_type=entry_type,
            size=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime, UTC),
        )

    def list(self, path: str) -> Sequence[StorageEntry]:
        def perform() -> Sequence[StorageEntry]:
            directory = self._resolve(path, "list")
            return tuple(
                self._entry(self._join_logical(path, item.name), item)
                for item in sorted(directory.iterdir(), key=lambda entry: entry.name)
            )

        return self._execute("list", path, perform)

    def stat(self, path: str) -> StorageEntry:
        def perform() -> StorageEntry:
            target = self._resolve(path, "stat")
            return self._entry(self._normalize_logical(path), target)

        return self._execute("stat", path, perform)

    def exists(self, path: str) -> bool:
        target = self._resolve(path, "exists")
        try:
            target.lstat()
        except FileNotFoundError:
            return False
        except OSError as error:
            raise self._mapped_error("exists", path, error) from error
        return True

    def read(self, path: str) -> BinaryIO:
        return self._execute("read", path, lambda: self._resolve(path, "read").open("rb"))

    def write(self, path: str, data: WriteSource, *, overwrite: bool = False) -> None:
        self._ensure_writable("write", path)

        def perform() -> None:
            target = self._resolve(path, "write")

            def stage(destination: Path) -> None:
                with destination.open("wb") as stream:
                    if isinstance(data, bytes | bytearray | memoryview):
                        stream.write(data)
                    else:
                        shutil.copyfileobj(data, stream, length=1024 * 1024)
                    stream.flush()
                    os.fsync(stream.fileno())

            self._atomic_publish(target, stage, overwrite=overwrite)

        self._execute("write", path, perform)

    def create_directory(self, path: str) -> None:
        self._ensure_writable("create_directory", path)
        self._execute(
            "create_directory",
            path,
            lambda: self._resolve(path, "create_directory").mkdir(parents=True, exist_ok=True),
        )

    def move(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self._ensure_writable("move", source)

        def perform() -> None:
            source_path = self._resolve(source, "move")
            target_path = self._resolve(target, "move")
            self._guard_target(target_path, overwrite, "move", target)
            if overwrite:
                os.replace(source_path, target_path)
            else:
                source_path.rename(target_path)

        self._execute("move", source, perform)

    def copy(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self._ensure_writable("copy", target)

        def perform() -> None:
            source_path = self._resolve(source, "copy")
            target_path = self._resolve(target, "copy")
            self._atomic_publish(
                target_path,
                lambda stage: shutil.copy2(source_path, stage),
                overwrite=overwrite,
            )

        self._execute("copy", source, perform)

    def delete(self, path: str) -> None:
        self._ensure_writable("delete", path)

        def perform() -> None:
            target = self._resolve(path, "delete")
            target.rmdir() if target.is_dir() and not target.is_symlink() else target.unlink()

        self._execute("delete", path, perform)

    def hard_link(self, source: str, target: str) -> None:
        self._ensure_writable("hard_link", target)
        if not self._can_hard_link():
            self._unsupported("hard_link", target)

        def perform() -> None:
            source_path = self._resolve(source, "hard_link")
            target_path = self._resolve(target, "hard_link")
            self._guard_target(target_path, False, "hard_link", target)
            os.link(source_path, target_path)

        self._execute("hard_link", source, perform)

    def soft_link(self, source: str, target: str) -> None:
        self._ensure_writable("soft_link", target)
        if not self._can_soft_link():
            self._unsupported("soft_link", target)

        def perform() -> None:
            source_path = self._resolve(source, "soft_link")
            target_path = self._resolve(target, "soft_link")
            if not source_path.exists():
                raise StorageError(
                    StorageErrorCode.NOT_FOUND,
                    "soft_link",
                    source,
                    "soft link source does not exist",
                )
            self._guard_target(target_path, False, "soft_link", target)
            relative_source = os.path.relpath(source_path, target_path.parent)
            target_path.symlink_to(relative_source)

        self._execute("soft_link", source, perform)

    def _ensure_writable(self, operation: str, path: str) -> None:
        if self._read_only:
            raise StorageError(
                StorageErrorCode.READ_ONLY,
                operation,
                path,
                f"storage {self._storage_id!r} is read-only",
            )

    @staticmethod
    def _atomic_publish(
        target: Path,
        writer: Callable[[Path], object],
        *,
        overwrite: bool,
    ) -> None:
        descriptor, stage_name = tempfile.mkstemp(prefix=".mediaflow-stage-", dir=target.parent)
        os.close(descriptor)
        stage = Path(stage_name)
        try:
            writer(stage)
            if overwrite:
                os.replace(stage, target)
            else:
                os.link(stage, target)
                stage.unlink()
        finally:
            try:
                stage.unlink()
            except FileNotFoundError:
                pass

    @staticmethod
    def _can_hard_link() -> bool:
        return hasattr(os, "link")

    @staticmethod
    def _can_soft_link() -> bool:
        return hasattr(os, "symlink")

    @staticmethod
    def _guard_target(target: Path, overwrite: bool, operation: str, path: str) -> None:
        try:
            target.lstat()
        except FileNotFoundError:
            return
        if not overwrite:
            raise StorageError(
                StorageErrorCode.ALREADY_EXISTS,
                operation,
                path,
                "storage target already exists",
            )

    @staticmethod
    def _unsupported(operation: str, path: str) -> None:
        raise StorageError(
            StorageErrorCode.UNSUPPORTED_OPERATION,
            operation,
            path,
            f"operation {operation!r} is not supported on this platform",
        )

    @staticmethod
    def _normalize_logical(path: str) -> str:
        normalized = str(PurePosixPath(path.replace("\\", "/")))
        return "" if normalized == "." else normalized

    @classmethod
    def _join_logical(cls, path: str, name: str) -> str:
        parent = cls._normalize_logical(path)
        return str(PurePosixPath(parent) / name) if parent else name

    @classmethod
    def _execute(cls, operation: str, path: str, function: Callable[[], Result]) -> Result:
        try:
            return function()
        except StorageError:
            raise
        except OSError as error:
            raise cls._mapped_error(operation, path, error) from error

    @staticmethod
    def _mapped_error(operation: str, path: str, error: OSError) -> StorageError:
        if isinstance(error, FileNotFoundError):
            code = StorageErrorCode.NOT_FOUND
        elif isinstance(error, PermissionError):
            code = StorageErrorCode.PERMISSION_DENIED
        elif isinstance(error, FileExistsError):
            code = StorageErrorCode.ALREADY_EXISTS
        elif isinstance(error, (IsADirectoryError, NotADirectoryError)):
            code = StorageErrorCode.INVALID_PATH
        elif error.errno is not None:
            code = StorageErrorCode.IO_ERROR
        else:
            code = StorageErrorCode.UNKNOWN
        return StorageError(code, operation, path, str(error), cause=error)
