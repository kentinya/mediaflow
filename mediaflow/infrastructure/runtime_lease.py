from __future__ import annotations

import os
import stat
from enum import StrEnum
from pathlib import Path
from types import TracebackType


class RuntimeLeaseMode(StrEnum):
    SHARED = "shared"
    EXCLUSIVE = "exclusive"


class RuntimeLeaseUnavailable(RuntimeError):
    pass


class RuntimeDatabaseLease:
    def __init__(self, database_path: str | Path, mode: RuntimeLeaseMode) -> None:
        raw = os.fspath(database_path)
        if not raw or "\0" in raw:
            raise ValueError("runtime database path is invalid for maintenance locking")
        database = Path(raw).absolute()
        self.path = database.with_name(f"{database.name}.mediaflow.lock")
        self.mode = mode
        self._descriptor: int | None = None

    def acquire(self, *, create_parent: bool = False) -> RuntimeDatabaseLease:
        if self._descriptor is not None:
            raise RuntimeError("runtime database lease is already acquired")
        if os.name != "posix":
            if self.mode is RuntimeLeaseMode.EXCLUSIVE:
                raise RuntimeError(
                    "exclusive runtime maintenance locking is unsupported on this platform"
                )
            return self
        parent = self.path.parent
        if create_parent and not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)
        if not parent.exists() or not parent.is_dir() or parent.is_symlink():
            raise ValueError("runtime lease parent must be an existing non-symlink directory")
        if self.path.is_symlink() or (self.path.exists() and not self.path.is_file()):
            raise ValueError("runtime lease path must be a regular non-symlink file")
        flags = os.O_CREAT | os.O_RDWR
        flags |= getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(self.path, flags, 0o600)
        except OSError as error:
            raise ValueError("runtime lease file cannot be opened safely") from error
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError("runtime lease path must be a regular non-symlink file")
            os.fchmod(descriptor, 0o600)
            import fcntl

            operation = (
                fcntl.LOCK_SH if self.mode is RuntimeLeaseMode.SHARED else fcntl.LOCK_EX
            ) | fcntl.LOCK_NB
            try:
                fcntl.flock(descriptor, operation)
            except BlockingIOError as error:
                raise RuntimeLeaseUnavailable(
                    "runtime database is in use by another MediaFlow process"
                ) from error
        except BaseException:
            os.close(descriptor)
            raise
        self._descriptor = descriptor
        return self

    def close(self) -> None:
        descriptor, self._descriptor = self._descriptor, None
        if descriptor is None:
            return
        if os.name == "posix":
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)

    def __enter__(self) -> RuntimeDatabaseLease:
        return self.acquire()

    def __exit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        self.close()
