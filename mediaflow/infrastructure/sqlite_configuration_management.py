from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from mediaflow.domain.configuration_management import (
    ClassificationPreviewEvidence,
    ConfigurationActivationConflict,
    ConfigurationChangeAudit,
    ConfigurationClassificationPreviewStatus,
    ConfigurationDestinationPreviewStatus,
    ConfigurationNamingPreviewStatus,
    ConfigurationObjectKind,
    ConfigurationObjectReferenced,
    ConfigurationOrganizeAuthorityStatus,
    ConfigurationReference,
    ConfigurationReferencePolicy,
    ConfigurationSetupCheckStatus,
    ConfigurationStrategyTestStatus,
    ConfigurationVersionConflict,
    DestinationPreviewEvidence,
    LocalSetupCheckEvidence,
    ManagedConfigurationRevision,
    ManagedConfigurationStatus,
    ManagedStorageConfiguration,
    NamingPreviewEvidence,
    OrganizeAuthorityEvidence,
    RecognitionStrategyTestEvidence,
    RuntimeSnapshotUnavailable,
    StorageConfigurationType,
    validate_configuration_object_id,
    validate_storage_configuration,
)

CONFIGURATION_SCHEMA_VERSION = 9


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

    @property
    def database_path(self) -> str:
        """Return the bootstrap locator used by this configuration store."""

        return str(self._path)

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

    def create_revision(
        self, revision: ManagedConfigurationRevision
    ) -> ManagedConfigurationRevision:
        """Persist a new Draft without changing the active workflow authority."""
        self._validate_revision(revision)
        with self._lock, self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            created = self._insert_revision(revision)
        return created

    def create_revision_with_audit(
        self,
        revision: ManagedConfigurationRevision,
        audit: ConfigurationChangeAudit,
    ) -> ManagedConfigurationRevision:
        """Create a Draft and its lifecycle audit in one SQLite transaction."""

        self._validate_revision(revision)
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                created = self._insert_revision(revision)
                self._insert_audit(
                    self._normalize_audit(
                        audit,
                        ConfigurationObjectKind.SYSTEM_SETTINGS,
                        created.revision_id,
                        audit.before,
                        {**audit.after, "revisionSequence": created.revision_sequence},
                    )
                )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        return created

    def _insert_revision(
        self, revision: ManagedConfigurationRevision
    ) -> ManagedConfigurationRevision:
        if self.get_revision(revision.revision_id) is not None:
            raise ValueError(f"configuration revision {revision.revision_id!r} already exists")
        latest = self._connection.execute(
            "SELECT MAX(revision_sequence) AS sequence FROM managed_configuration_revisions"
        ).fetchone()
        sequence = int(latest["sequence"]) + 1 if latest["sequence"] is not None else 1
        created = replace(revision, revision_sequence=sequence)
        self._connection.execute(
            """
            INSERT INTO managed_configuration_revisions
            (revision_id, revision_sequence, version, status, schema_version, digest, payload,
             validation_errors, created_at, updated_at, validated_at, activated_at,
             base_active_revision_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._revision_values(created),
        )
        return created

    def get_revision(self, revision_id: str) -> ManagedConfigurationRevision | None:
        if not isinstance(revision_id, str) or not revision_id.strip():
            raise ValueError("configuration revision ID is required")
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM managed_configuration_revisions WHERE revision_id=?",
                (revision_id,),
            ).fetchone()
        if row is None:
            return None
        try:
            return self._revision(row)
        except Exception as error:
            if row["status"] == ManagedConfigurationStatus.ACTIVE.value:
                marker = self.last_known_active()
                raise RuntimeSnapshotUnavailable(
                    "managed Active configuration is unreadable",
                    revision_id=marker.get("revisionId") if marker else revision_id,
                    version=marker.get("revisionSequence") if marker else None,
                    digest=marker.get("digest") if marker else None,
                    reason="active_unreadable",
                ) from error
            raise

    def list_revisions(self, *, limit: int = 100) -> tuple[ManagedConfigurationRevision, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("configuration revision limit must be between 1 and 500")
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM managed_configuration_revisions "
                "ORDER BY revision_sequence DESC, revision_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(self._revision(row) for row in rows)

    def update_revision(
        self, revision: ManagedConfigurationRevision, expected_version: int
    ) -> ManagedConfigurationRevision:
        self._validate_revision(revision)
        if isinstance(expected_version, bool) or not isinstance(expected_version, int):
            raise ConfigurationVersionConflict(
                "expected configuration revision version must be an integer"
            )
        with self._lock, self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            row = self._connection.execute(
                "SELECT * FROM managed_configuration_revisions WHERE revision_id=?",
                (revision.revision_id,),
            ).fetchone()
            if row is None:
                raise LookupError(f"configuration revision {revision.revision_id!r} was not found")
            if int(row["version"]) != expected_version:
                raise ConfigurationVersionConflict(
                    f"configuration revision {revision.revision_id!r} was changed by "
                    "another update",
                    revision_id=revision.revision_id,
                    current_version=int(row["version"]),
                    current_digest=row["digest"],
                )
            if row["status"] in {
                ManagedConfigurationStatus.ACTIVE.value,
                ManagedConfigurationStatus.SUPERSEDED.value,
            }:
                raise ConfigurationVersionConflict(
                    "published configuration revisions are immutable"
                )
            updated = self._update_revision_row(revision, expected_version, row)
        return updated

    def update_revision_with_audit(
        self,
        revision: ManagedConfigurationRevision,
        expected_version: int,
        audit: ConfigurationChangeAudit,
    ) -> ManagedConfigurationRevision:
        """Update a Draft and its lifecycle audit in one SQLite transaction."""

        self._validate_revision(revision)
        if isinstance(expected_version, bool) or not isinstance(expected_version, int):
            raise ConfigurationVersionConflict(
                "expected configuration revision version must be an integer"
            )
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._connection.execute(
                    "SELECT * FROM managed_configuration_revisions WHERE revision_id=?",
                    (revision.revision_id,),
                ).fetchone()
                if row is None:
                    raise LookupError(
                        f"configuration revision {revision.revision_id!r} was not found"
                    )
                updated = self._update_revision_row(revision, expected_version, row)
                self._insert_audit(
                    self._normalize_audit(
                        audit,
                        ConfigurationObjectKind.SYSTEM_SETTINGS,
                        revision.revision_id,
                        audit.before,
                        {**audit.after, "revisionSequence": updated.revision_sequence},
                    )
                )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        return updated

    def _update_revision_row(
        self,
        revision: ManagedConfigurationRevision,
        expected_version: int,
        row: sqlite3.Row,
    ) -> ManagedConfigurationRevision:
        if int(row["version"]) != expected_version:
            raise ConfigurationVersionConflict(
                f"configuration revision {revision.revision_id!r} was changed by another update",
                revision_id=revision.revision_id,
                current_version=int(row["version"]),
                current_digest=row["digest"],
            )
        if row["status"] in {
            ManagedConfigurationStatus.ACTIVE.value,
            ManagedConfigurationStatus.SUPERSEDED.value,
        }:
            raise ConfigurationVersionConflict("published configuration revisions are immutable")
        stored_sequence = row["revision_sequence"]
        candidate = (
            revision
            if revision.revision_sequence is not None
            else replace(revision, revision_sequence=int(stored_sequence))
        )
        cursor = self._connection.execute(
            """
            UPDATE managed_configuration_revisions
            SET version=?, status=?, schema_version=?, digest=?, payload=?, validation_errors=?,
                created_at=?, updated_at=?, validated_at=?, activated_at=?,
                base_active_revision_id=?, revision_sequence=?
            WHERE revision_id=? AND version=?
            """,
            (
                *self._revision_values(candidate)[2:],
                candidate.revision_sequence,
                candidate.revision_id,
                expected_version,
            ),
        )
        if cursor.rowcount != 1:
            raise ConfigurationVersionConflict(
                f"configuration revision {revision.revision_id!r} was changed by another update"
            )
        return candidate

    def get_active_revision(self) -> ManagedConfigurationRevision | None:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM managed_configuration_revisions WHERE status=? "
                "ORDER BY version DESC",
                (ManagedConfigurationStatus.ACTIVE.value,),
            ).fetchall()
        if len(rows) > 1:
            raise RuntimeError("managed configuration has more than one Active revision")
        if not rows:
            return None
        try:
            return self._revision(rows[0])
        except Exception as error:
            marker = self.last_known_active()
            raise RuntimeSnapshotUnavailable(
                "managed Active configuration is unreadable",
                revision_id=marker.get("revisionId") if marker else None,
                version=marker.get("revisionSequence") if marker else None,
                digest=marker.get("digest") if marker else None,
                reason="active_unreadable",
            ) from error

    def has_managed_activation(self) -> bool:
        """Return whether this store has ever published managed authority."""
        with self._lock:
            row = self._connection.execute(
                "SELECT 1 FROM managed_configuration_authority WHERE singleton=1"
            ).fetchone()
        return row is not None

    def last_known_active(self) -> dict[str, object] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT last_active_revision_id, last_active_version, last_active_digest, "
                "updated_at FROM managed_configuration_authority WHERE singleton=1"
            ).fetchone()
        if row is None:
            return None
        return {
            "revisionId": row["last_active_revision_id"],
            "version": int(row["last_active_version"]),
            "revisionSequence": int(row["last_active_version"]),
            "digest": row["last_active_digest"],
            "updatedAt": row["updated_at"],
        }

    def activate_revision(
        self,
        revision_id: str,
        expected_version: int,
        audit: ConfigurationChangeAudit,
    ) -> ManagedConfigurationRevision:
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._connection.execute(
                    "SELECT * FROM managed_configuration_revisions WHERE revision_id=?",
                    (revision_id,),
                ).fetchone()
                if row is None:
                    raise LookupError(f"configuration revision {revision_id!r} was not found")
                active_rows = self._connection.execute(
                    "SELECT * FROM managed_configuration_revisions WHERE status=? "
                    "ORDER BY version DESC",
                    (ManagedConfigurationStatus.ACTIVE.value,),
                ).fetchall()
                if len(active_rows) > 1:
                    raise RuntimeError("managed configuration has more than one Active revision")
                current_active = active_rows[0] if active_rows else None
                if int(row["version"]) != expected_version:
                    raise ConfigurationActivationConflict(
                        "configuration revision is stale; refresh the Draft before activation",
                        revision_id=revision_id,
                        current_revision_id=current_active["revision_id"]
                        if current_active
                        else None,
                        current_version=int(current_active["version"]) if current_active else None,
                        current_digest=current_active["digest"] if current_active else None,
                    )
                if row["status"] != ManagedConfigurationStatus.VALIDATED.value:
                    raise ConfigurationActivationConflict(
                        "only a freshly Validated configuration revision can be activated",
                        revision_id=revision_id,
                        current_revision_id=current_active["revision_id"]
                        if current_active
                        else None,
                        current_version=int(current_active["version"]) if current_active else None,
                        current_digest=current_active["digest"] if current_active else None,
                    )
                current_active_usable = bool(
                    current_active is None or self._row_integrity_valid(current_active)
                )
                current_active_id = (
                    current_active["revision_id"]
                    if current_active and current_active_usable
                    else None
                )
                if row["base_active_revision_id"] != current_active_id:
                    raise ConfigurationActivationConflict(
                        "configuration Draft was based on a different Active revision; "
                        "refresh and validate it again",
                        revision_id=revision_id,
                        current_revision_id=current_active["revision_id"]
                        if current_active
                        else None,
                        current_version=int(current_active["version"]) if current_active else None,
                        current_digest=current_active["digest"] if current_active else None,
                    )
                if current_active and current_active["revision_id"] == revision_id:
                    raise ConfigurationActivationConflict(
                        "configuration revision is already Active", revision_id=revision_id
                    )
                if current_active:
                    self._connection.execute(
                        "UPDATE managed_configuration_revisions SET status=?, updated_at=? "
                        "WHERE revision_id=? AND status=?",
                        (
                            ManagedConfigurationStatus.SUPERSEDED.value,
                            audit.occurred_at.isoformat(),
                            current_active["revision_id"],
                            ManagedConfigurationStatus.ACTIVE.value,
                        ),
                    )
                self._connection.execute(
                    "UPDATE managed_configuration_revisions "
                    "SET status=?, updated_at=?, activated_at=? "
                    "WHERE revision_id=? AND version=?",
                    (
                        ManagedConfigurationStatus.ACTIVE.value,
                        audit.occurred_at.isoformat(),
                        audit.occurred_at.isoformat(),
                        revision_id,
                        expected_version,
                    ),
                )
                normalized_audit = self._normalize_audit(
                    audit,
                    ConfigurationObjectKind.SYSTEM_SETTINGS,
                    revision_id,
                    audit.before,
                    {
                        **audit.after,
                        "revisionId": revision_id,
                        "status": ManagedConfigurationStatus.ACTIVE.value,
                    },
                )
                self._insert_audit(normalized_audit)
                self._connection.execute(
                    """
                    INSERT INTO managed_configuration_authority
                    (singleton, last_active_revision_id, last_active_version,
                     last_active_digest, updated_at)
                    VALUES (1, ?, ?, ?, ?)
                    ON CONFLICT(singleton) DO UPDATE SET
                        last_active_revision_id=excluded.last_active_revision_id,
                        last_active_version=excluded.last_active_version,
                        last_active_digest=excluded.last_active_digest,
                        updated_at=excluded.updated_at
                    """,
                    (
                        revision_id,
                        int(row["revision_sequence"]),
                        row["digest"],
                        audit.occurred_at.isoformat(),
                    ),
                )
                activated = self._connection.execute(
                    "SELECT * FROM managed_configuration_revisions WHERE revision_id=?",
                    (revision_id,),
                ).fetchone()
                if activated is None:
                    raise RuntimeError("activated configuration revision disappeared")
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        return self._revision(activated)

    def list_revision_audits(
        self, revision_id: str, *, limit: int = 50
    ) -> tuple[ConfigurationChangeAudit, ...]:
        return self.list_audits(ConfigurationObjectKind.SYSTEM_SETTINGS, revision_id, limit=limit)

    def record_configuration_audit(self, audit: ConfigurationChangeAudit) -> None:
        normalized = self._normalize_audit(
            audit,
            ConfigurationObjectKind.SYSTEM_SETTINGS,
            audit.object_id,
            audit.before,
            audit.after,
        )
        with self._lock, self._connection:
            self._insert_audit(normalized)

    def save_local_setup_check(self, evidence: LocalSetupCheckEvidence) -> LocalSetupCheckEvidence:
        if not isinstance(evidence, LocalSetupCheckEvidence):
            raise ValueError("setup check evidence is required")
        payload = evidence.document()
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO managed_local_setup_checks
                (revision_id, revision_version, revision_digest, status, checked_at, actor,
                 storage_ids, resource_library_id, media_library_id, operations, duration_ms,
                 source_path, destination_path, failure_category, message, next_action)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(revision_id) DO UPDATE SET
                    revision_version=excluded.revision_version,
                    revision_digest=excluded.revision_digest,
                    status=excluded.status,
                    checked_at=excluded.checked_at,
                    actor=excluded.actor,
                    storage_ids=excluded.storage_ids,
                    resource_library_id=excluded.resource_library_id,
                    media_library_id=excluded.media_library_id,
                    operations=excluded.operations,
                    source_path=excluded.source_path,
                    destination_path=excluded.destination_path,
                    duration_ms=excluded.duration_ms,
                    failure_category=excluded.failure_category,
                    message=excluded.message,
                    next_action=excluded.next_action
                """,
                (
                    evidence.revision_id,
                    evidence.revision_version,
                    evidence.revision_digest,
                    evidence.status.value,
                    evidence.checked_at.isoformat(),
                    evidence.actor,
                    self._json(payload["storageIds"]),
                    evidence.resource_library_id,
                    evidence.media_library_id,
                    self._json(payload["operations"]),
                    evidence.duration_ms,
                    evidence.source_path,
                    evidence.destination_path,
                    evidence.failure_category,
                    evidence.message,
                    evidence.next_action,
                ),
            )
        return evidence

    def get_local_setup_check(self, revision_id: str) -> LocalSetupCheckEvidence | None:
        self._object_id(revision_id)
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM managed_local_setup_checks WHERE revision_id=?",
                (revision_id,),
            ).fetchone()
        if row is None:
            return None
        return LocalSetupCheckEvidence(
            row["revision_id"],
            int(row["revision_version"]),
            row["revision_digest"],
            ConfigurationSetupCheckStatus(row["status"]),
            datetime.fromisoformat(row["checked_at"]),
            row["actor"],
            tuple(json.loads(row["storage_ids"])),
            row["resource_library_id"],
            row["media_library_id"],
            row["source_path"],
            row["destination_path"],
            tuple(json.loads(row["operations"])),
            int(row["duration_ms"]),
            row["failure_category"],
            row["message"],
            row["next_action"],
        )

    def save_recognition_strategy_test(
        self, evidence: RecognitionStrategyTestEvidence
    ) -> RecognitionStrategyTestEvidence:
        if not isinstance(evidence, RecognitionStrategyTestEvidence):
            raise ValueError("recognition strategy test evidence is required")
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO managed_recognition_strategy_tests
                (revision_id, revision_version, revision_digest, status, tested_at, actor,
                 resource_library_id, synthetic_path, result_json, failure_category, message,
                 next_action)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(revision_id) DO UPDATE SET
                    revision_version=excluded.revision_version,
                    revision_digest=excluded.revision_digest,
                    status=excluded.status,
                    tested_at=excluded.tested_at,
                    actor=excluded.actor,
                    resource_library_id=excluded.resource_library_id,
                    synthetic_path=excluded.synthetic_path,
                    result_json=excluded.result_json,
                    failure_category=excluded.failure_category,
                    message=excluded.message,
                    next_action=excluded.next_action
                """,
                (
                    evidence.revision_id,
                    evidence.revision_version,
                    evidence.revision_digest,
                    evidence.status.value,
                    evidence.tested_at.isoformat(),
                    evidence.actor,
                    evidence.resource_library_id,
                    evidence.synthetic_path,
                    self._json(evidence.result) if evidence.result is not None else None,
                    evidence.failure_category,
                    evidence.message,
                    evidence.next_action,
                ),
            )
        return evidence

    def replace_recognition_strategy_test(
        self,
        evidence: RecognitionStrategyTestEvidence,
        *,
        expected_revision_version: int,
        expected_revision_digest: str,
        expected_tested_at: datetime,
    ) -> RecognitionStrategyTestEvidence:
        if not isinstance(evidence, RecognitionStrategyTestEvidence):
            raise ValueError("recognition strategy test evidence is required")
        if (
            isinstance(expected_revision_version, bool)
            or not isinstance(expected_revision_version, int)
            or expected_revision_version < 1
        ):
            raise ValueError("expected strategy evidence revision version must be positive")
        if not isinstance(expected_revision_digest, str) or not expected_revision_digest:
            raise ValueError("expected strategy evidence revision digest is required")
        if not isinstance(expected_tested_at, datetime) or expected_tested_at.tzinfo is None:
            raise ValueError("expected strategy evidence time must include a timezone")
        if (
            evidence.revision_version != expected_revision_version
            or evidence.revision_digest != expected_revision_digest
        ):
            raise ValueError("replacement evidence must retain the expected revision identity")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                revision = self._connection.execute(
                    """
                    SELECT version, digest, status
                    FROM managed_configuration_revisions
                    WHERE revision_id=?
                    """,
                    (evidence.revision_id,),
                ).fetchone()
                if (
                    revision is None
                    or int(revision["version"]) != expected_revision_version
                    or revision["digest"] != expected_revision_digest
                    or revision["status"] != ManagedConfigurationStatus.VALIDATED.value
                ):
                    raise ConfigurationVersionConflict(
                        "configuration revision changed while confirming a candidate",
                        revision_id=evidence.revision_id,
                        current_version=(
                            int(revision["version"]) if revision is not None else None
                        ),
                        current_digest=revision["digest"] if revision is not None else None,
                        durable_state="current_draft_and_strategy_evidence_preserved",
                        next_action=(
                            "reload the revision, review the current Draft and Strategy Test "
                            "evidence, then validate and explicitly rerun the live test"
                        ),
                    )
                cursor = self._connection.execute(
                    """
                    UPDATE managed_recognition_strategy_tests
                    SET revision_version=?, revision_digest=?, status=?, tested_at=?, actor=?,
                        resource_library_id=?, synthetic_path=?, result_json=?, failure_category=?,
                        message=?, next_action=?
                    WHERE revision_id=? AND revision_version=? AND revision_digest=? AND tested_at=?
                    """,
                    (
                        evidence.revision_version,
                        evidence.revision_digest,
                        evidence.status.value,
                        evidence.tested_at.isoformat(),
                        evidence.actor,
                        evidence.resource_library_id,
                        evidence.synthetic_path,
                        self._json(evidence.result) if evidence.result is not None else None,
                        evidence.failure_category,
                        evidence.message,
                        evidence.next_action,
                        evidence.revision_id,
                        expected_revision_version,
                        expected_revision_digest,
                        expected_tested_at.isoformat(),
                    ),
                )
                if cursor.rowcount != 1:
                    raise ConfigurationVersionConflict(
                        "Strategy Test evidence changed; reload before confirming a candidate",
                        revision_id=evidence.revision_id,
                        current_version=evidence.revision_version,
                        current_digest=evidence.revision_digest,
                        durable_state="current_strategy_evidence_preserved",
                        next_action=(
                            "reload the revision, review the current Strategy Test outcome, and "
                            "explicitly rerun the live test if another candidate must be considered"
                        ),
                    )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        return evidence

    def get_recognition_strategy_test(
        self, revision_id: str
    ) -> RecognitionStrategyTestEvidence | None:
        self._object_id(revision_id)
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM managed_recognition_strategy_tests WHERE revision_id=?",
                (revision_id,),
            ).fetchone()
        if row is None:
            return None
        return RecognitionStrategyTestEvidence(
            row["revision_id"],
            int(row["revision_version"]),
            row["revision_digest"],
            ConfigurationStrategyTestStatus(row["status"]),
            datetime.fromisoformat(row["tested_at"]),
            row["actor"],
            row["resource_library_id"],
            row["synthetic_path"],
            json.loads(row["result_json"]) if row["result_json"] is not None else None,
            row["failure_category"],
            row["message"],
            row["next_action"],
        )

    def save_naming_preview(self, evidence: NamingPreviewEvidence) -> NamingPreviewEvidence:
        if not isinstance(evidence, NamingPreviewEvidence):
            raise ValueError("naming preview evidence is required")
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO managed_naming_previews
                (revision_id, revision_version, revision_digest, status, previewed_at, actor,
                 policy_id, input_json, result_json, failure_category, message, next_action)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(revision_id) DO UPDATE SET
                    revision_version=excluded.revision_version,
                    revision_digest=excluded.revision_digest,
                    status=excluded.status,
                    previewed_at=excluded.previewed_at,
                    actor=excluded.actor,
                    policy_id=excluded.policy_id,
                    input_json=excluded.input_json,
                    result_json=excluded.result_json,
                    failure_category=excluded.failure_category,
                    message=excluded.message,
                    next_action=excluded.next_action
                """,
                (
                    evidence.revision_id,
                    evidence.revision_version,
                    evidence.revision_digest,
                    evidence.status.value,
                    evidence.previewed_at.isoformat(),
                    evidence.actor,
                    evidence.policy_id,
                    self._json(evidence.input),
                    self._json(evidence.result) if evidence.result is not None else None,
                    evidence.failure_category,
                    evidence.message,
                    evidence.next_action,
                ),
            )
        return evidence

    def get_naming_preview(self, revision_id: str) -> NamingPreviewEvidence | None:
        self._object_id(revision_id)
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM managed_naming_previews WHERE revision_id=?", (revision_id,)
            ).fetchone()
        if row is None:
            return None
        return NamingPreviewEvidence(
            row["revision_id"],
            int(row["revision_version"]),
            row["revision_digest"],
            ConfigurationNamingPreviewStatus(row["status"]),
            datetime.fromisoformat(row["previewed_at"]),
            row["actor"],
            row["policy_id"],
            json.loads(row["input_json"]),
            json.loads(row["result_json"]) if row["result_json"] is not None else None,
            row["failure_category"],
            row["message"],
            row["next_action"],
        )

    def save_classification_preview(
        self, evidence: ClassificationPreviewEvidence
    ) -> ClassificationPreviewEvidence:
        if not isinstance(evidence, ClassificationPreviewEvidence):
            raise ValueError("classification preview evidence is required")
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO managed_classification_previews
                (revision_id, revision_version, revision_digest, status, previewed_at, actor,
                 policy_id, input_json, result_json, failure_category, message, next_action)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(revision_id) DO UPDATE SET
                    revision_version=excluded.revision_version,
                    revision_digest=excluded.revision_digest,
                    status=excluded.status,
                    previewed_at=excluded.previewed_at,
                    actor=excluded.actor,
                    policy_id=excluded.policy_id,
                    input_json=excluded.input_json,
                    result_json=excluded.result_json,
                    failure_category=excluded.failure_category,
                    message=excluded.message,
                    next_action=excluded.next_action
                """,
                (
                    evidence.revision_id,
                    evidence.revision_version,
                    evidence.revision_digest,
                    evidence.status.value,
                    evidence.previewed_at.isoformat(),
                    evidence.actor,
                    evidence.policy_id,
                    self._json(evidence.input),
                    self._json(evidence.result) if evidence.result is not None else None,
                    evidence.failure_category,
                    evidence.message,
                    evidence.next_action,
                ),
            )
        return evidence

    def get_classification_preview(self, revision_id: str) -> ClassificationPreviewEvidence | None:
        self._object_id(revision_id)
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM managed_classification_previews WHERE revision_id=?",
                (revision_id,),
            ).fetchone()
        if row is None:
            return None
        return ClassificationPreviewEvidence(
            row["revision_id"],
            int(row["revision_version"]),
            row["revision_digest"],
            ConfigurationClassificationPreviewStatus(row["status"]),
            datetime.fromisoformat(row["previewed_at"]),
            row["actor"],
            row["policy_id"],
            json.loads(row["input_json"]),
            json.loads(row["result_json"]) if row["result_json"] is not None else None,
            row["failure_category"],
            row["message"],
            row["next_action"],
        )

    def save_organize_authority(
        self, evidence: OrganizeAuthorityEvidence
    ) -> OrganizeAuthorityEvidence:
        if not isinstance(evidence, OrganizeAuthorityEvidence):
            raise ValueError("organize authority evidence is required")
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO managed_organize_authority_previews
                (revision_id, revision_version, revision_digest, status, explained_at, actor,
                 recognition_type, result_json, failure_category, message, next_action)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(revision_id) DO UPDATE SET
                    revision_version=excluded.revision_version,
                    revision_digest=excluded.revision_digest,
                    status=excluded.status,
                    explained_at=excluded.explained_at,
                    actor=excluded.actor,
                    recognition_type=excluded.recognition_type,
                    result_json=excluded.result_json,
                    failure_category=excluded.failure_category,
                    message=excluded.message,
                    next_action=excluded.next_action
                """,
                (
                    evidence.revision_id,
                    evidence.revision_version,
                    evidence.revision_digest,
                    evidence.status.value,
                    evidence.explained_at.isoformat(),
                    evidence.actor,
                    evidence.recognition_type,
                    self._json(evidence.result) if evidence.result is not None else None,
                    evidence.failure_category,
                    evidence.message,
                    evidence.next_action,
                ),
            )
        return evidence

    def get_organize_authority(self, revision_id: str) -> OrganizeAuthorityEvidence | None:
        self._object_id(revision_id)
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM managed_organize_authority_previews WHERE revision_id=?",
                (revision_id,),
            ).fetchone()
        if row is None:
            return None
        return OrganizeAuthorityEvidence(
            row["revision_id"],
            int(row["revision_version"]),
            row["revision_digest"],
            ConfigurationOrganizeAuthorityStatus(row["status"]),
            datetime.fromisoformat(row["explained_at"]),
            row["actor"],
            row["recognition_type"],
            json.loads(row["result_json"]) if row["result_json"] is not None else None,
            row["failure_category"],
            row["message"],
            row["next_action"],
        )

    def save_destination_preview(
        self, evidence: DestinationPreviewEvidence
    ) -> DestinationPreviewEvidence:
        if not isinstance(evidence, DestinationPreviewEvidence):
            raise ValueError("destination preview evidence is required")
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO managed_destination_previews
                (revision_id, revision_version, revision_digest, status, previewed_at, actor,
                 recognition_type, input_json, result_json, failure_category, message, next_action)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(revision_id) DO UPDATE SET
                    revision_version=excluded.revision_version,
                    revision_digest=excluded.revision_digest,
                    status=excluded.status,
                    previewed_at=excluded.previewed_at,
                    actor=excluded.actor,
                    recognition_type=excluded.recognition_type,
                    input_json=excluded.input_json,
                    result_json=excluded.result_json,
                    failure_category=excluded.failure_category,
                    message=excluded.message,
                    next_action=excluded.next_action
                """,
                (
                    evidence.revision_id,
                    evidence.revision_version,
                    evidence.revision_digest,
                    evidence.status.value,
                    evidence.previewed_at.isoformat(),
                    evidence.actor,
                    evidence.recognition_type,
                    self._json(evidence.input),
                    self._json(evidence.result) if evidence.result is not None else None,
                    evidence.failure_category,
                    evidence.message,
                    evidence.next_action,
                ),
            )
        return evidence

    def get_destination_preview(self, revision_id: str) -> DestinationPreviewEvidence | None:
        self._object_id(revision_id)
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM managed_destination_previews WHERE revision_id=?",
                (revision_id,),
            ).fetchone()
        if row is None:
            return None
        return DestinationPreviewEvidence(
            row["revision_id"],
            int(row["revision_version"]),
            row["revision_digest"],
            ConfigurationDestinationPreviewStatus(row["status"]),
            datetime.fromisoformat(row["previewed_at"]),
            row["actor"],
            row["recognition_type"],
            json.loads(row["input_json"]),
            json.loads(row["result_json"]) if row["result_json"] is not None else None,
            row["failure_category"],
            row["message"],
            row["next_action"],
        )

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

    @staticmethod
    def _row_integrity_valid(row: sqlite3.Row) -> bool:
        try:
            document = json.loads(row["payload"])
            canonical = json.dumps(
                document,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            return False
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest() == row["digest"]

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
    def _validate_revision(revision: ManagedConfigurationRevision) -> None:
        if not isinstance(revision, ManagedConfigurationRevision):
            raise ValueError("managed configuration revision is required")

    @staticmethod
    def _revision_values(revision: ManagedConfigurationRevision) -> tuple[object, ...]:
        return (
            revision.revision_id,
            revision.revision_sequence,
            revision.version,
            revision.status.value,
            revision.schema_version,
            revision.digest,
            SQLiteConfigurationRepository._json(revision.document),
            SQLiteConfigurationRepository._json(list(revision.validation_errors)),
            revision.created_at.isoformat(),
            revision.updated_at.isoformat(),
            revision.validated_at.isoformat() if revision.validated_at else None,
            revision.activated_at.isoformat() if revision.activated_at else None,
            revision.base_active_revision_id,
        )

    @staticmethod
    def _revision(row: sqlite3.Row) -> ManagedConfigurationRevision:
        return ManagedConfigurationRevision(
            row["revision_id"],
            int(row["version"]),
            ManagedConfigurationStatus(row["status"]),
            int(row["schema_version"]),
            row["digest"],
            json.loads(row["payload"]),
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["updated_at"]),
            tuple(json.loads(row["validation_errors"])),
            datetime.fromisoformat(row["validated_at"]) if row["validated_at"] else None,
            datetime.fromisoformat(row["activated_at"]) if row["activated_at"] else None,
            row["base_active_revision_id"],
            int(row["revision_sequence"]) if row["revision_sequence"] is not None else None,
        )

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
                CREATE TABLE IF NOT EXISTS managed_configuration_revisions (
                    revision_id TEXT PRIMARY KEY,
                    revision_sequence INTEGER,
                    version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    digest TEXT NOT NULL,
                    payload TEXT NOT NULL,
                validation_errors TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                validated_at TEXT,
                activated_at TEXT,
                base_active_revision_id TEXT
                );
                CREATE INDEX IF NOT EXISTS managed_configuration_revisions_status
                    ON managed_configuration_revisions(status, version, revision_id);
                CREATE TABLE IF NOT EXISTS managed_local_setup_checks (
                    revision_id TEXT PRIMARY KEY,
                    revision_version INTEGER NOT NULL,
                    revision_digest TEXT NOT NULL,
                    status TEXT NOT NULL,
                    checked_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    storage_ids TEXT NOT NULL,
                    resource_library_id TEXT,
                    media_library_id TEXT,
                    operations TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL,
                    source_path TEXT,
                    destination_path TEXT,
                    failure_category TEXT,
                    message TEXT,
                    next_action TEXT
                );
                CREATE INDEX IF NOT EXISTS managed_local_setup_checks_status
                    ON managed_local_setup_checks(status, checked_at);
                CREATE TABLE IF NOT EXISTS managed_recognition_strategy_tests (
                    revision_id TEXT PRIMARY KEY,
                    revision_version INTEGER NOT NULL,
                    revision_digest TEXT NOT NULL,
                    status TEXT NOT NULL,
                    tested_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    resource_library_id TEXT NOT NULL,
                    synthetic_path TEXT NOT NULL,
                    result_json TEXT,
                    failure_category TEXT,
                    message TEXT,
                    next_action TEXT
                );
                CREATE INDEX IF NOT EXISTS managed_recognition_strategy_tests_status
                    ON managed_recognition_strategy_tests(status, tested_at);
                CREATE TABLE IF NOT EXISTS managed_naming_previews (
                    revision_id TEXT PRIMARY KEY,
                    revision_version INTEGER NOT NULL,
                    revision_digest TEXT NOT NULL,
                    status TEXT NOT NULL,
                    previewed_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    policy_id TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    result_json TEXT,
                    failure_category TEXT,
                    message TEXT,
                    next_action TEXT,
                    FOREIGN KEY(revision_id) REFERENCES managed_configuration_revisions(revision_id)
                );
                CREATE INDEX IF NOT EXISTS managed_naming_previews_status
                    ON managed_naming_previews(status, previewed_at);
                CREATE TABLE IF NOT EXISTS managed_classification_previews (
                    revision_id TEXT PRIMARY KEY,
                    revision_version INTEGER NOT NULL,
                    revision_digest TEXT NOT NULL,
                    status TEXT NOT NULL,
                    previewed_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    policy_id TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    result_json TEXT,
                    failure_category TEXT,
                    message TEXT,
                    next_action TEXT,
                    FOREIGN KEY(revision_id) REFERENCES managed_configuration_revisions(revision_id)
                );
                CREATE INDEX IF NOT EXISTS managed_classification_previews_status
                    ON managed_classification_previews(status, previewed_at);
                CREATE TABLE IF NOT EXISTS managed_organize_authority_previews (
                    revision_id TEXT PRIMARY KEY,
                    revision_version INTEGER NOT NULL,
                    revision_digest TEXT NOT NULL,
                    status TEXT NOT NULL,
                    explained_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    recognition_type TEXT NOT NULL,
                    result_json TEXT,
                    failure_category TEXT,
                    message TEXT,
                    next_action TEXT,
                    FOREIGN KEY(revision_id) REFERENCES managed_configuration_revisions(revision_id)
                );
                CREATE INDEX IF NOT EXISTS managed_organize_authority_previews_status
                    ON managed_organize_authority_previews(status, explained_at);
                CREATE TABLE IF NOT EXISTS managed_destination_previews (
                    revision_id TEXT PRIMARY KEY,
                    revision_version INTEGER NOT NULL,
                    revision_digest TEXT NOT NULL,
                    status TEXT NOT NULL,
                    previewed_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    recognition_type TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    result_json TEXT,
                    failure_category TEXT,
                    message TEXT,
                    next_action TEXT,
                    FOREIGN KEY(revision_id) REFERENCES managed_configuration_revisions(revision_id)
                );
                CREATE INDEX IF NOT EXISTS managed_destination_previews_status
                    ON managed_destination_previews(status, previewed_at);
                """
            )
            self._connection.execute(
                """
                INSERT INTO schema_version VALUES ('configuration_management', ?)
                ON CONFLICT(component) DO UPDATE SET version=excluded.version
                """,
                (CONFIGURATION_SCHEMA_VERSION,),
            )
            revision_columns = {
                row["name"]
                for row in self._connection.execute(
                    "PRAGMA table_info(managed_configuration_revisions)"
                ).fetchall()
            }
            if "base_active_revision_id" not in revision_columns:
                self._connection.execute(
                    "ALTER TABLE managed_configuration_revisions "
                    "ADD COLUMN base_active_revision_id TEXT"
                )
            setup_check_columns = {
                row["name"]
                for row in self._connection.execute(
                    "PRAGMA table_info(managed_local_setup_checks)"
                ).fetchall()
            }
            for column in ("source_path", "destination_path"):
                if column not in setup_check_columns:
                    self._connection.execute(
                        f"ALTER TABLE managed_local_setup_checks ADD COLUMN {column} TEXT"
                    )
            if "revision_sequence" not in revision_columns:
                self._connection.execute(
                    "ALTER TABLE managed_configuration_revisions "
                    "ADD COLUMN revision_sequence INTEGER"
                )
            self._connection.execute(
                "UPDATE managed_configuration_revisions SET revision_sequence=rowid "
                "WHERE revision_sequence IS NULL"
            )
            self._connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS managed_configuration_revision_sequence "
                "ON managed_configuration_revisions(revision_sequence)"
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS managed_configuration_authority (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    last_active_revision_id TEXT NOT NULL,
                    last_active_version INTEGER NOT NULL,
                    last_active_digest TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            marker = self._connection.execute(
                "SELECT 1 FROM managed_configuration_authority WHERE singleton=1"
            ).fetchone()
            if marker is None:
                active = self._connection.execute(
                    "SELECT revision_id, revision_sequence, digest, activated_at "
                    "FROM managed_configuration_revisions WHERE status=? "
                    "ORDER BY revision_sequence DESC LIMIT 1",
                    (ManagedConfigurationStatus.ACTIVE.value,),
                ).fetchone()
                if active is not None:
                    self._connection.execute(
                        "INSERT INTO managed_configuration_authority "
                        "(singleton, last_active_revision_id, last_active_version, "
                        "last_active_digest, updated_at) VALUES (1, ?, ?, ?, ?)",
                        (
                            active["revision_id"],
                            int(active["revision_sequence"]),
                            active["digest"],
                            active["activated_at"] or datetime.utcnow().isoformat(),
                        ),
                    )
                else:
                    audit = self._connection.execute(
                        "SELECT after_json, occurred_at FROM configuration_change_audits "
                        "WHERE object_kind=? AND action='activate' "
                        "ORDER BY sequence DESC LIMIT 1",
                        (ConfigurationObjectKind.SYSTEM_SETTINGS.value,),
                    ).fetchone()
                    if audit is not None:
                        after = json.loads(audit["after_json"])
                        revision_id = after.get("revisionId")
                        revision = self._connection.execute(
                            "SELECT revision_sequence, digest FROM managed_configuration_revisions "
                            "WHERE revision_id=?",
                            (revision_id,),
                        ).fetchone()
                        if revision_id and revision is not None:
                            self._connection.execute(
                                "INSERT INTO managed_configuration_authority "
                                "(singleton, last_active_revision_id, last_active_version, "
                                "last_active_digest, updated_at) VALUES (1, ?, ?, ?, ?)",
                                (
                                    revision_id,
                                    int(revision["revision_sequence"]),
                                    revision["digest"],
                                    audit["occurred_at"],
                                ),
                            )
