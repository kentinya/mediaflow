from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.domain.configuration_management import (
    ConfigurationChangeAudit,
    ConfigurationObjectKind,
    ConfigurationVersionConflict,
    ManagedStorageConfiguration,
    StorageConfigurationRepository,
    validate_storage_configuration,
)


class StorageConfigurationService:
    MAX_ACTOR = 200

    def __init__(self, repository: StorageConfigurationRepository) -> None:
        self._repository = repository

    def create(
        self,
        storage: ManagedStorageConfiguration,
        *,
        actor: str,
    ) -> ManagedStorageConfiguration:
        validated = validate_storage_configuration(storage)
        if validated.version != 1:
            raise ValueError("a new Storage configuration must start at version 1")
        candidate = replace(validated, version=1)
        audit = self._audit(
            object_id=candidate.storage_id,
            action="create",
            before={},
            after=candidate.document(),
            actor=actor,
        )
        return self._repository.create_storage(candidate, audit)

    def get(self, storage_id: str) -> ManagedStorageConfiguration:
        storage = self._repository.get_storage(storage_id)
        if storage is None:
            raise LookupError(f"Storage configuration {storage_id!r} was not found")
        return storage

    def list(self, *, include_disabled: bool = True) -> tuple[ManagedStorageConfiguration, ...]:
        return self._repository.list_storages(include_disabled=include_disabled)

    def update(
        self,
        storage_id: str,
        storage: ManagedStorageConfiguration,
        *,
        expected_version: int,
        actor: str,
    ) -> ManagedStorageConfiguration:
        if isinstance(expected_version, bool) or not isinstance(expected_version, int):
            raise ConfigurationVersionConflict("expected Storage version must be an integer")
        if expected_version < 1:
            raise ConfigurationVersionConflict("expected Storage version must be positive")
        current = self.get(storage_id)
        candidate = validate_storage_configuration(storage)
        if candidate.storage_id != current.storage_id:
            raise ValueError("Storage configuration ID cannot be changed by update")
        if candidate.version != expected_version:
            raise ConfigurationVersionConflict(
                "Storage candidate version does not match the expected version"
            )
        candidate = replace(candidate, version=expected_version)
        audit = self._audit(
            object_id=current.storage_id,
            action="update",
            before=current.document(),
            after=candidate.document(),
            actor=actor,
        )
        return self._repository.update_storage(candidate, expected_version, audit)

    def copy(
        self,
        storage_id: str,
        new_storage_id: str,
        *,
        name: str | None = None,
        actor: str,
    ) -> ManagedStorageConfiguration:
        source = self.get(storage_id)
        candidate = validate_storage_configuration(
            replace(
                source,
                storage_id=new_storage_id,
                name=name if name is not None else source.name,
                version=1,
            )
        )
        audit = self._audit(
            object_id=candidate.storage_id,
            action="copy",
            before={},
            after=candidate.document(),
            actor=actor,
        )
        return self._repository.create_storage(candidate, audit)

    def enable(self, storage_id: str, *, actor: str) -> ManagedStorageConfiguration:
        return self._set_enabled(storage_id, True, actor)

    def disable(self, storage_id: str, *, actor: str) -> ManagedStorageConfiguration:
        return self._set_enabled(storage_id, False, actor)

    def delete(self, storage_id: str, *, actor: str) -> None:
        current = self.get(storage_id)
        audit = self._audit(
            object_id=current.storage_id,
            action="delete",
            before=current.document(),
            after={},
            actor=actor,
        )
        self._repository.delete_storage(storage_id, audit)

    def audits(
        self,
        storage_id: str,
        *,
        limit: int = 50,
    ):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("configuration audit limit must be between 1 and 500")
        return self._repository.list_audits(
            ConfigurationObjectKind.STORAGE,
            storage_id,
            limit=limit,
        )

    def _set_enabled(
        self,
        storage_id: str,
        enabled: bool,
        actor: str,
    ) -> ManagedStorageConfiguration:
        current = self.get(storage_id)
        if current.enabled == enabled:
            return current
        candidate = replace(current, enabled=enabled)
        audit = self._audit(
            object_id=current.storage_id,
            action="enable" if enabled else "disable",
            before=current.document(),
            after=candidate.document(),
            actor=actor,
        )
        return self._repository.update_storage(candidate, current.version, audit)

    def _audit(
        self,
        *,
        object_id: str,
        action: str,
        before: dict[str, object],
        after: dict[str, object],
        actor: str,
    ) -> ConfigurationChangeAudit:
        normalized_actor = actor.strip() if isinstance(actor, str) else ""
        if not normalized_actor or len(normalized_actor) > self.MAX_ACTOR:
            raise ValueError(
                "configuration actor must be a non-empty string of at most 200 characters"
            )
        return ConfigurationChangeAudit(
            str(uuid4()),
            ConfigurationObjectKind.STORAGE,
            object_id,
            action,
            before,
            after,
            datetime.now(UTC),
            normalized_actor,
        )
