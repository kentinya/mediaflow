from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from mediaflow.domain.configuration_management import (
    ConfigurationChangeAudit,
    ConfigurationObjectKind,
    ConfigurationObjectReferenced,
    ConfigurationReference,
    ConfigurationReferencePolicy,
    ConfigurationVersionConflict,
    ManagedStorageConfiguration,
    StorageConfigurationType,
    validate_configuration_object_id,
    validate_storage_configuration,
)

CONFIGURATION_SCHEMA_VERSION = 1


class SQLiteConfigurationRepository:
    """Durable configuration CRUD adapter; it never constructs Storage providers."""

    _SOURCE_KINDS = {
        ConfigurationObjectKind.RESOURCE_LIBRARY,
        ConfigurationObjectKind.MEDIA_LIBRARY,
    }

    def __init__(self, database_path: str | Path) -> None:
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self._path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.RLock()
        self._initialize()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> SQLiteConfigurationRepository:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def create_storage(
        self,
        storage: ManagedStorageConfiguration,
        audit: ConfigurationChangeAudit,
    ) -> ManagedStorageConfiguration:
        candidate = validate_storage_configuration(storage)
        if candidate.version != 1:
            raise ValueError("a new Storage configuration must start at version 1")
        if self._get_row(candidate.storage_id) is not None:
            raise ValueError(f"Storage configuration {candidate.storage_id!r} already exists")
        normalized_audit = self._normalize_audit(
            audit,
            ConfigurationObjectKind.STORAGE,
            candidate.storage_id,
            {},
            candidate.document(),
        )
        occurred_at = normalized_audit.occurred_at.isoformat()
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO configuration_objects
                (object_kind, object_id, enabled, payload, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ConfigurationObjectKind.STORAGE.value,
                    candidate.storage_id,
                    int(candidate.enabled),
                    self._json(candidate.document()),
                    candidate.version,
                    occurred_at,
                    occurred_at,
                ),
            )
            self._insert_audit(normalized_audit)
        return candidate

    def get_storage(self, storage_id: str) -> ManagedStorageConfiguration | None:
        row = self._get_row(storage_id)
        return None if row is None else self._storage(row)

    def list_storages(
        self,
        *,
        include_disabled: bool = True,
    ) -> tuple[ManagedStorageConfiguration, ...]:
        sql = "SELECT * FROM configuration_objects WHERE object_kind=?"
        values: tuple[object, ...] = (ConfigurationObjectKind.STORAGE.value,)
        if not include_disabled:
            sql += " AND enabled=1"
        sql += " ORDER BY object_id"
        with self._lock:
            rows = self._connection.execute(sql, values).fetchall()
        return tuple(self._storage(row) for row in rows)

    def update_storage(
        self,
        storage: ManagedStorageConfiguration,
        expected_version: int,
        audit: ConfigurationChangeAudit,
    ) -> ManagedStorageConfiguration:
        candidate = validate_storage_configuration(storage)
        if (
            isinstance(expected_version, bool)
            or not isinstance(expected_version, int)
            or expected_version < 1
        ):
            raise ConfigurationVersionConflict(
                "expected Storage version must be a positive integer"
            )
        if candidate.version != expected_version:
            raise ConfigurationVersionConflict("Storage candidate and expected version must match")
        current_row = self._get_row(candidate.storage_id)
        if current_row is None:
            raise LookupError(f"Storage configuration {candidate.storage_id!r} was not found")
        with self._lock, self._connection:
            # Serialize the read/verify/write cycle so a same-version replacement
            # cannot race an update after the service fetched its optimistic token.
            self._connection.execute("BEGIN IMMEDIATE")
            locked_row = self._get_row(candidate.storage_id)
            if locked_row is None or int(locked_row["version"]) != expected_version:
                self._raise_version_or_missing(candidate.storage_id)
            current = self._storage(locked_row)
            normalized_audit = self._normalize_audit(
                audit,
                ConfigurationObjectKind.STORAGE,
                candidate.storage_id,
                current.document(),
                candidate.document(),
            )
            occurred_at = normalized_audit.occurred_at.isoformat()
            next_version = expected_version + 1
            cursor = self._connection.execute(
                """
                UPDATE configuration_objects
                SET enabled=?, payload=?, version=?, updated_at=?
                WHERE object_kind=? AND object_id=? AND version=?
                """,
                (
                    int(candidate.enabled),
                    self._json(candidate.document()),
                    next_version,
                    occurred_at,
                    ConfigurationObjectKind.STORAGE.value,
                    candidate.storage_id,
                    expected_version,
                ),
            )
            if cursor.rowcount != 1:
                self._raise_version_or_missing(candidate.storage_id)
            self._insert_audit(normalized_audit)
        return replace(candidate, version=next_version)

    def delete_storage(
        self,
        storage_id: str,
        audit: ConfigurationChangeAudit,
    ) -> None:
        with self._lock, self._connection:
            # BEGIN IMMEDIATE serializes the reference check with concurrent writers.
            self._connection.execute("BEGIN IMMEDIATE")
            row = self._get_row(storage_id)
            if row is None:
                raise LookupError(f"Storage configuration {storage_id!r} was not found")
            reference_count = self._reference_count(ConfigurationObjectKind.STORAGE, storage_id)
            policy = ConfigurationReferencePolicy(ConfigurationObjectKind.STORAGE)
            if not policy.can_delete(reference_count):
                raise ConfigurationObjectReferenced(
                    ConfigurationObjectKind.STORAGE,
                    storage_id,
                    reference_count,
                )
            current = self._storage(row)
            normalized_audit = self._normalize_audit(
                audit,
                ConfigurationObjectKind.STORAGE,
                storage_id,
                current.document(),
                {},
            )
            self._connection.execute(
                """
                DELETE FROM configuration_objects
                WHERE object_kind=? AND object_id=?
                """,
                (ConfigurationObjectKind.STORAGE.value, storage_id),
            )
            self._insert_audit(normalized_audit)

    def list_references(
        self,
        kind: ConfigurationObjectKind,
        object_id: str,
    ) -> int:
        if not isinstance(kind, ConfigurationObjectKind):
            raise ValueError("configuration reference kind is required")
        self._object_id(object_id)
        with self._lock:
            return self._reference_count(kind, object_id)

    def record_storage_reference(self, reference: ConfigurationReference) -> None:
        if reference.target_kind is not ConfigurationObjectKind.STORAGE:
            raise ValueError("configuration reference target must be Storage")
        if reference.source_kind not in self._SOURCE_KINDS:
            raise ValueError("Storage references may only come from Resource/Media Libraries")
        source_id = self._object_id(reference.source_id)
        target_id = self._object_id(reference.target_id)
        with self._lock, self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            if self._get_row(target_id) is None:
                raise LookupError(f"Storage configuration {target_id!r} was not found")
            try:
                self._connection.execute(
                    """
                    INSERT INTO configuration_references VALUES (?, ?, ?, ?)
                    """,
                    (
                        reference.source_kind.value,
                        source_id,
                        reference.target_kind.value,
                        target_id,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("configuration reference already exists") from error

    def list_audits(
        self,
        kind: ConfigurationObjectKind,
        object_id: str,
        *,
        limit: int = 50,
    ) -> tuple[ConfigurationChangeAudit, ...]:
        if not isinstance(kind, ConfigurationObjectKind):
            raise ValueError("configuration audit kind is required")
        self._object_id(object_id)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("configuration audit limit must be between 1 and 500")
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM configuration_change_audits
                WHERE object_kind=? AND object_id=?
                ORDER BY occurred_at DESC, sequence DESC LIMIT ?
                """,
                (kind.value, object_id, limit),
            ).fetchall()
        return tuple(self._audit(row) for row in rows)

    def _get_row(self, storage_id: str) -> sqlite3.Row | None:
        self._object_id(storage_id)
        with self._lock:
            return self._connection.execute(
                """
                SELECT * FROM configuration_objects
                WHERE object_kind=? AND object_id=?
                """,
                (ConfigurationObjectKind.STORAGE.value, storage_id),
            ).fetchone()

    @staticmethod
    def _storage(row: sqlite3.Row) -> ManagedStorageConfiguration:
        document = json.loads(row["payload"])
        options = document.get("options", {})
        return ManagedStorageConfiguration(
            document["storageId"],
            StorageConfigurationType(document["type"]),
            document["name"],
            document["rootPath"],
            document["readOnly"],
            document["enabled"],
            options,
            int(row["version"]),
        )

    @staticmethod
    def _audit(row: sqlite3.Row) -> ConfigurationChangeAudit:
        return ConfigurationChangeAudit(
            row["audit_id"],
            ConfigurationObjectKind(row["object_kind"]),
            row["object_id"],
            row["action"],
            json.loads(row["before_json"]),
            json.loads(row["after_json"]),
            datetime.fromisoformat(row["occurred_at"]),
            row["actor"],
        )

    def _reference_count(
        self,
        kind: ConfigurationObjectKind,
        object_id: str,
    ) -> int:
        row = self._connection.execute(
            """
            SELECT COUNT(*) AS value_count FROM configuration_references
            WHERE target_kind=? AND target_id=?
            """,
            (kind.value, object_id),
        ).fetchone()
        return int(row["value_count"])

    def _insert_audit(self, audit: ConfigurationChangeAudit) -> None:
        self._connection.execute(
            """
            INSERT INTO configuration_change_audits
            (audit_id, object_kind, object_id, action, before_json, after_json,
             occurred_at, actor)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit.audit_id,
                audit.object_kind.value,
                audit.object_id,
                audit.action,
                self._json(audit.safe_before()),
                self._json(audit.safe_after()),
                audit.occurred_at.isoformat(),
                audit.actor,
            ),
        )

    def _raise_version_or_missing(self, storage_id: str) -> None:
        if self._get_row(storage_id) is None:
            raise LookupError(f"Storage configuration {storage_id!r} was not found")
        raise ConfigurationVersionConflict(
            f"Storage configuration {storage_id!r} was changed by another update"
        )

    @staticmethod
    def _normalize_audit(
        audit: ConfigurationChangeAudit,
        kind: ConfigurationObjectKind,
        object_id: str,
        before: dict[str, object],
        after: dict[str, object],
    ) -> ConfigurationChangeAudit:
        if not audit.audit_id or not isinstance(audit.actor, str) or not audit.actor.strip():
            raise ValueError("configuration audit ID and actor are required")
        if not audit.action or len(audit.action) > 32:
            raise ValueError("configuration audit action must be a bounded non-empty string")
        return replace(audit, object_kind=kind, object_id=object_id, before=before, after=after)

    @staticmethod
    def _object_id(value: str) -> str:
        return validate_configuration_object_id(value)

    @staticmethod
    def _json(value: object) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)

    def _initialize(self) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_version "
                "(component TEXT PRIMARY KEY, version INTEGER NOT NULL)"
            )
            row = self._connection.execute(
                "SELECT version FROM schema_version WHERE component='configuration_management'"
            ).fetchone()
            if row and int(row["version"]) > CONFIGURATION_SCHEMA_VERSION:
                raise ValueError(
                    "configuration database schema is newer than this MediaFlow version"
                )
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS configuration_objects (
                    object_kind TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(object_kind, object_id)
                );
                CREATE INDEX IF NOT EXISTS configuration_objects_enabled
                    ON configuration_objects(object_kind, enabled, object_id);
                CREATE TABLE IF NOT EXISTS configuration_references (
                    source_kind TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    target_kind TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    PRIMARY KEY(source_kind, source_id, target_kind, target_id)
                );
                CREATE INDEX IF NOT EXISTS configuration_references_target
                    ON configuration_references(target_kind, target_id);
                CREATE TABLE IF NOT EXISTS configuration_change_audits (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    audit_id TEXT NOT NULL UNIQUE,
                    object_kind TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    before_json TEXT NOT NULL,
                    after_json TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    actor TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS configuration_audits_object
                    ON configuration_change_audits(object_kind, object_id, occurred_at, sequence);
                """
            )
            self._connection.execute(
                """
                INSERT INTO schema_version VALUES ('configuration_management', ?)
                ON CONFLICT(component) DO UPDATE SET version=excluded.version
                """,
                (CONFIGURATION_SCHEMA_VERSION,),
            )
