"""Read the deployment-internal key material used to authenticate cursors.

Storage browser continuation cursors are stateless and authenticated with a
key.  A cursor minted by one CLI/API process must be verifiable by a later,
independent process, so that key cannot be a per-process random value.  It is
instead generated create-if-absent inside the managed configuration store
(see :class:`SQLiteConfigurationRepository`) and read back here.

A strictly read-only operator read (``mediaflow files list``) must not create
or upgrade the store, so this module opens it with ``mode=ro`` and only reads
the one internal-metadata table.  A missing table or row means the store has
not completed the supported initialization that owns the key; the caller turns
that into an explicit, actionable refusal instead of silently minting a
one-off key.
"""

from __future__ import annotations

import sqlite3
import urllib.parse
from pathlib import Path


class InternalKeyUnavailable(RuntimeError):
    """The internal key cannot be read from the store."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


def read_internal_key_read_only(database_path: str | Path, name: str) -> bytes | None:
    """Return the persisted internal key, or ``None`` when it is not present.

    ``None`` distinguishes "this store has not been initialized with the key
    yet" from a corrupt/unreadable value, which raises
    :class:`InternalKeyUnavailable`.  Neither case writes to the database.
    """

    path = Path(database_path)
    if not path.exists():
        return None
    uri = f"file:{urllib.parse.quote(str(path), safe='/')}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as error:
        raise InternalKeyUnavailable(
            "the internal key store could not be opened read-only",
            reason="database_unavailable",
        ) from error
    try:
        if not _table_exists(connection, "managed_internal_keys"):
            return None
        row = connection.execute(
            "SELECT key_material FROM managed_internal_keys WHERE key_name=?", (name,)
        ).fetchone()
        if row is None:
            return None
        return _material(row[0])
    except sqlite3.Error as error:
        raise InternalKeyUnavailable(
            "the internal key store is unreadable",
            reason="database_unreadable",
        ) from error
    finally:
        connection.close()


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _material(value: object) -> bytes:
    if not isinstance(value, (bytes, bytearray, memoryview)) or not value:
        raise InternalKeyUnavailable(
            "the persisted internal key material is empty or corrupt",
            reason="key_corrupt",
        )
    return bytes(value)


__all__ = ["InternalKeyUnavailable", "read_internal_key_read_only"]
