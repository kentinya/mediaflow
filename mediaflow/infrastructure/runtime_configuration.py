from __future__ import annotations

import os
import posixpath
from dataclasses import dataclass
from typing import Any

from mediaflow.application.strategy_test import (
    StrategyTestConfiguration,
    strategy_runner_from_configuration,
)
from mediaflow.domain.library import DEFAULT_MEDIA_EXTENSIONS, MediaLibrary, ResourceLibrary
from mediaflow.domain.storage import Storage
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.openlist_storage import OpenListStorage, OpenListStorageConfig
from mediaflow.infrastructure.strategy_user_configuration import load_strategy_configuration


@dataclass(frozen=True)
class StorageDefinition:
    storage_id: str
    storage_type: str
    root_path: str
    name: str
    read_only: bool = False
    options: dict[str, Any] | None = None


@dataclass(frozen=True)
class RuntimeConfiguration:
    strategy: StrategyTestConfiguration
    storage_definitions: tuple[StorageDefinition, ...]
    resource_libraries: tuple[ResourceLibrary, ...]
    resource_display_roots: tuple[tuple[str, str], ...]
    media_libraries: tuple[MediaLibrary, ...]
    history_path: str
    database_path: str

    def create_storages(self, external: dict[str, Storage] | None = None) -> dict[str, Storage]:
        storages = dict(external or {})
        for value in self.storage_definitions:
            if value.storage_id in storages:
                continue
            if value.storage_type != "local":
                if value.storage_type == "openlist":
                    options = value.options or {}
                    token_env = str(options.get("tokenEnv", ""))
                    token = os.environ.get(token_env) if token_env else None
                    if not token:
                        raise ValueError(
                            f"OpenList Storage {value.storage_id!r} requires environment "
                            f"variable {token_env or '<tokenEnv>'}"
                        )
                    storages[value.storage_id] = OpenListStorage(
                        OpenListStorageConfig(
                            value.storage_id,
                            value.name,
                            str(options.get("baseUrl", "")),
                            token,
                            value.root_path,
                            value.read_only,
                            float(options.get("connectTimeout", 10)),
                            float(options.get("requestTimeout", 60)),
                            int(options.get("maxConcurrency", 4)),
                            int(options.get("maxRetries", 2)),
                            int(options.get("pageSize", 100)),
                        )
                    )
                    continue
                raise ValueError(
                    f"Storage {value.storage_id!r} type {value.storage_type!r} requires an "
                    "injected configured adapter"
                )
            else:
                storages[value.storage_id] = LocalStorage(
                    value.storage_id,
                    value.root_path,
                    name=value.name,
                    read_only=value.read_only,
                )
        return storages


def load_runtime_configuration(document: Any) -> RuntimeConfiguration:
    if not isinstance(document, dict):
        raise ValueError("runtime configuration must be a JSON object")
    loaded = load_strategy_configuration(document, require_complete=True)
    storage_definitions = tuple(_storage(item) for item in _objects(document, "storages"))
    storage_ids = {item.storage_id for item in storage_definitions}
    resources = []
    display_roots = []
    for item in _objects(document, "resourceLibraries"):
        storage_id = _required(item, "storageId")
        _reference(storage_id, storage_ids, "ResourceLibrary Storage")
        display_root = item.get("displayRootPath", item.get("rootPath"))
        resources.append(
            ResourceLibrary(
                _required(item, "id"),
                str(item.get("name") or item["id"]),
                storage_id,
                str(item.get("storagePath", "")),
                enabled=bool(item.get("enabled", True)),
                file_extensions=tuple(item.get("extensions", ())) or DEFAULT_MEDIA_EXTENSIONS,
                max_depth=item.get("maxDepth"),
            )
        )
        if display_root is not None:
            if not isinstance(display_root, str) or not display_root.strip():
                raise ValueError(
                    "ResourceLibrary displayRootPath must be a non-empty string when configured"
                )
            display_roots.append((_required(item, "id"), display_root))
    media_libraries = tuple(
        _media_library(item, storage_ids) for item in _objects(document, "mediaLibraries")
    )
    media_ids = {item.library_id for item in media_libraries}
    if len(media_ids) != len(media_libraries):
        raise ValueError("mediaLibraries IDs must be unique")
    for policy in loaded.strategy.classification_policies:
        for rule in policy.rules:
            if rule.media_library_id not in media_ids:
                raise ValueError(
                    f"ClassificationRule {rule.rule_id!r} references unknown "
                    f"MediaLibrary {rule.media_library_id!r}"
                )
    # Constructing the application registries validates templates, duplicate IDs,
    # recognition outputs, and every RecognitionTypePolicy reference up front.
    strategy_runner_from_configuration(loaded.strategy)
    _validate_strategy_references(loaded.strategy)
    history_path = str(document.get("historyPath", ".mediaflow/history.jsonl"))
    persistence = document.get("persistence", {})
    if not isinstance(persistence, dict):
        raise ValueError("runtime configuration 'persistence' must be an object")
    database_path = persistence.get("databasePath", ".mediaflow/mediaflow.sqlite3")
    if not isinstance(database_path, str) or not database_path.strip() or "\x00" in database_path:
        raise ValueError("persistence databasePath must be a non-empty path string")
    return RuntimeConfiguration(
        loaded.strategy,
        storage_definitions,
        tuple(resources),
        tuple(display_roots),
        media_libraries,
        history_path,
        database_path,
    )


def _storage(value: dict) -> StorageDefinition:
    return StorageDefinition(
        _required(value, "id"),
        _required(value, "type").lower(),
        _required(value, "rootPath"),
        str(value.get("name") or value["id"]),
        bool(value.get("readOnly", False)),
        dict(value),
    )


def _media_library(value: dict, storage_ids: set[str]) -> MediaLibrary:
    storage_id = _required(value, "storageId")
    _reference(storage_id, storage_ids, "MediaLibrary Storage")
    root_path = _required(value, "rootPath")
    normalized = posixpath.normpath(root_path)
    if (
        root_path.startswith(("/", "\\"))
        or "\\" in root_path
        or normalized in {".", ".."}
        or normalized.startswith("../")
    ):
        raise ValueError("MediaLibrary rootPath must be a safe Storage-relative path")
    return MediaLibrary(
        _required(value, "id"),
        str(value.get("name") or value["id"]),
        storage_id,
        normalized,
        bool(value.get("enabled", True)),
    )


def _objects(document: dict, key: str) -> list[dict]:
    value = document.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"runtime configuration {key!r} must be an array of objects")
    return value


def _required(document: dict, key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"runtime configuration {key!r} must be a non-empty string")
    return value


def _reference(value: str, available: set[str], label: str) -> None:
    if value not in available:
        raise ValueError(f"{label} references unknown Storage {value!r}")


def _validate_strategy_references(strategy: StrategyTestConfiguration) -> None:
    type_ids = {item.type_id for item in strategy.recognition_types}
    catalogs = {
        "MetadataPolicy": {item.policy_id for item in strategy.metadata_policies},
        "NamingPolicy": {item.policy_id for item in strategy.naming_policies},
        "ClassificationPolicy": {item.policy_id for item in strategy.classification_policies},
        "OrganizePolicy": {item.policy_id for item in strategy.organize_policies},
    }
    policy_ids = [item.policy_id for item in strategy.recognition_type_policies]
    if len(policy_ids) != len(set(policy_ids)):
        raise ValueError("recognitionTypePolicies IDs must be unique")
    for rule in strategy.recognition_rules:
        if rule.output_recognition_type_id not in type_ids:
            raise ValueError(
                f"RecognitionRule {rule.rule_id!r} references unknown RecognitionType "
                f"{rule.output_recognition_type_id!r}"
            )
    for policy in strategy.recognition_type_policies:
        references = (
            ("MetadataPolicy", policy.metadata_policy_id),
            ("NamingPolicy", policy.naming_policy_id),
            ("ClassificationPolicy", policy.classification_policy_id),
            ("OrganizePolicy", policy.organize_policy_id),
        )
        for label, value in references:
            if value not in catalogs[label]:
                raise ValueError(
                    f"RecognitionTypePolicy {policy.policy_id!r} references unknown "
                    f"{label} {value!r}"
                )
