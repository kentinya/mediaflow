from __future__ import annotations

from typing import BinaryIO

from mediaflow.domain.storage import Storage, StorageCapabilities, StorageEntry, WriteSource


class ReadOnlyStorageMutationError(RuntimeError):
    """Raised before a guarded Storage mutation can reach its adapter."""


class ReadOnlyStorageGuard:
    """Delegate Storage reads while rejecting and counting every mutation."""

    def __init__(self, storage: Storage) -> None:
        self._storage = storage
        self.mutation_calls = {
            name: 0
            for name in (
                "Write",
                "CreateDirectory",
                "Move",
                "Copy",
                "Delete",
                "HardLink",
                "SoftLink",
            )
        }

    @property
    def storage_id(self) -> str:
        return self._storage.storage_id

    @property
    def name(self) -> str:
        return self._storage.name

    @property
    def read_only(self) -> bool:
        return True

    @property
    def capabilities(self) -> StorageCapabilities:
        return StorageCapabilities()

    def list(self, path: str):
        return self._storage.list(path)

    def stat(self, path: str) -> StorageEntry:
        return self._storage.stat(path)

    def exists(self, path: str) -> bool:
        return self._storage.exists(path)

    def read(self, path: str) -> BinaryIO:
        return self._storage.read(path)

    def write(self, path: str, data: WriteSource, *, overwrite: bool = False) -> None:
        self._reject("Write")

    def create_directory(self, path: str) -> None:
        self._reject("CreateDirectory")

    def move(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self._reject("Move")

    def copy(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self._reject("Copy")

    def delete(self, path: str) -> None:
        self._reject("Delete")

    def hard_link(self, source: str, target: str) -> None:
        self._reject("HardLink")

    def soft_link(self, source: str, target: str) -> None:
        self._reject("SoftLink")

    def _reject(self, operation: str) -> None:
        self.mutation_calls[operation] += 1
        raise self._mutation_error(operation)

    def _mutation_error(self, operation: str) -> ReadOnlyStorageMutationError:
        return ReadOnlyStorageMutationError(
            f"read-only Storage guard forbids mutation: {operation}"
        )
