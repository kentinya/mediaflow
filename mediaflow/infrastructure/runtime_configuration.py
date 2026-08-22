from __future__ import annotations

import os
import posixpath
import re
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
from mediaflow.infrastructure.s3_storage import S3Provider, S3Storage, S3StorageConfig
from mediaflow.infrastructure.smb_storage import SMBStorage, SMBStorageConfig
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
    api_token_env: str | None = None

    def create_storages(
        self,
        external: dict[str, Storage] | None = None,
        storage_ids: set[str] | None = None,
    ) -> dict[str, Storage]:
        storages = dict(external or {})
        for value in self.storage_definitions:
            if storage_ids is not None and value.storage_id not in storage_ids:
                continue
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
                if value.storage_type == "smb":
                    options = value.options or {}
                    storages[value.storage_id] = SMBStorage(
                        SMBStorageConfig(
                            value.storage_id,
                            value.name,
                            str(options.get("host", "")),
                            str(options.get("share", "")),
                            _secret(value, "usernameEnv"),
                            _secret(value, "passwordEnv"),
                            str(options["domain"]) if options.get("domain") is not None else None,
                            value.root_path,
                            int(options.get("port", 445)),
                            value.read_only,
                            float(options.get("connectTimeout", 30)),
                            float(options.get("operationTimeout", 60)),
                            int(options.get("maxConcurrency", 4)),
                        )
                    )
                    continue
                if value.storage_type in {"s3", "r2", "s3-compatible"}:
                    options = value.options or {}
                    provider = {
                        "s3": S3Provider.AWS_S3,
                        "r2": S3Provider.CLOUDFLARE_R2,
                        "s3-compatible": S3Provider.S3_COMPATIBLE,
                    }[value.storage_type]
                    session_env = options.get("sessionTokenEnv")
                    session_token = (
                        _secret(value, "sessionTokenEnv") if session_env is not None else None
                    )
                    storages[value.storage_id] = S3Storage(
                        S3StorageConfig(
                            value.storage_id,
                            value.name,
                            provider,
                            str(options.get("bucket", "")),
                            _secret(value, "accessKeyEnv"),
                            _secret(value, "secretKeyEnv"),
                            str(options["endpoint"]) if options.get("endpoint") else None,
                            str(options["region"]) if options.get("region") else None,
                            session_token,
                            value.root_path,
                            value.read_only,
                            float(options.get("connectTimeout", 10)),
                            float(options.get("requestTimeout", 60)),
                            int(options.get("maxConcurrency", 4)),
                            int(options.get("multipartThreshold", 64 * 1024 * 1024)),
                            int(options.get("multipartPartSize", 16 * 1024 * 1024)),
                            bool(options.get("forcePathStyle", False)),
                            int(options.get("maxRetries", 2)),
                            int(options.get("pageSize", 1000)),
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
    for definition in storage_definitions:
        _validate_storage_definition(definition)
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
    api = document.get("api", {})
    if not isinstance(api, dict):
        raise ValueError("runtime configuration 'api' must be an object")
    api_token_env = api.get("tokenEnv")
    if api_token_env is not None and (
        not isinstance(api_token_env, str) or not _ENV_NAME.fullmatch(api_token_env)
    ):
        raise ValueError("API tokenEnv must be a valid environment variable name")
    return RuntimeConfiguration(
        loaded.strategy,
        storage_definitions,
        tuple(resources),
        tuple(display_roots),
        media_libraries,
        history_path,
        database_path,
        api_token_env,
    )


def _storage(value: dict) -> StorageDefinition:
    storage_type = _required(value, "type").lower()
    root = value.get("rootPath", "")
    if not isinstance(root, str) or "\x00" in root:
        raise ValueError("Storage rootPath must be a string without NUL")
    if storage_type == "local" and not root.strip():
        raise ValueError("Local Storage rootPath must be non-empty")
    read_only = value.get("readOnly", False)
    if not isinstance(read_only, bool):
        raise ValueError("Storage readOnly must be boolean")
    return StorageDefinition(
        _required(value, "id"),
        storage_type,
        root,
        str(value.get("name") or value["id"]),
        read_only,
        dict(value),
    )


_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _env_name(options: dict[str, Any], key: str, *, required: bool = True) -> str | None:
    value = options.get(key)
    if value is None and not required:
        return None
    if not isinstance(value, str) or not _ENV_NAME.fullmatch(value):
        raise ValueError(f"Storage {key} must be a valid environment variable name")
    return value


def _secret(definition: StorageDefinition, key: str) -> str:
    options = definition.options or {}
    name = _env_name(options, key)
    assert name is not None
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Storage {definition.storage_id!r} requires environment variable {name}")
    return value


def _validate_storage_definition(value: StorageDefinition) -> None:
    options = value.options or {}
    if value.storage_type == "local":
        return
    if value.storage_type == "openlist":
        _reject_literal_secrets(options, {"token"})
        _env_name(options, "tokenEnv")
        OpenListStorageConfig(
            value.storage_id,
            value.name,
            str(options.get("baseUrl", "")),
            "validation-placeholder",
            value.root_path,
            value.read_only,
            float(options.get("connectTimeout", 10)),
            float(options.get("requestTimeout", 60)),
            int(options.get("maxConcurrency", 4)),
            int(options.get("maxRetries", 2)),
            int(options.get("pageSize", 100)),
        )
        return
    if value.storage_type == "smb":
        _reject_literal_secrets(options, {"username", "password"})
        _validate_remote_root(value.root_path)
        _env_name(options, "usernameEnv")
        _env_name(options, "passwordEnv")
        SMBStorageConfig(
            value.storage_id,
            value.name,
            str(options.get("host", "")),
            str(options.get("share", "")),
            "validation-user",
            "validation-password",
            str(options["domain"]) if options.get("domain") is not None else None,
            value.root_path,
            int(options.get("port", 445)),
            value.read_only,
            float(options.get("connectTimeout", 30)),
            float(options.get("operationTimeout", 60)),
            int(options.get("maxConcurrency", 4)),
        )
        return
    if value.storage_type in {"s3", "r2", "s3-compatible"}:
        _reject_literal_secrets(options, {"accessKey", "secretKey", "sessionToken"})
        _validate_remote_root(value.root_path)
        _env_name(options, "accessKeyEnv")
        _env_name(options, "secretKeyEnv")
        _env_name(options, "sessionTokenEnv", required=False)
        provider = {
            "s3": S3Provider.AWS_S3,
            "r2": S3Provider.CLOUDFLARE_R2,
            "s3-compatible": S3Provider.S3_COMPATIBLE,
        }[value.storage_type]
        force_path_style = options.get("forcePathStyle", False)
        if not isinstance(force_path_style, bool):
            raise ValueError("Storage forcePathStyle must be boolean")
        S3StorageConfig(
            value.storage_id,
            value.name,
            provider,
            str(options.get("bucket", "")),
            "validation-access-key",
            "validation-secret-key",
            str(options["endpoint"]) if options.get("endpoint") else None,
            str(options["region"]) if options.get("region") else None,
            "validation-session" if options.get("sessionTokenEnv") else None,
            value.root_path,
            value.read_only,
            float(options.get("connectTimeout", 10)),
            float(options.get("requestTimeout", 60)),
            int(options.get("maxConcurrency", 4)),
            int(options.get("multipartThreshold", 64 * 1024 * 1024)),
            int(options.get("multipartPartSize", 16 * 1024 * 1024)),
            force_path_style,
            int(options.get("maxRetries", 2)),
            int(options.get("pageSize", 1000)),
        )
        return
    raise ValueError(f"unsupported Storage type {value.storage_type!r}")


def _reject_literal_secrets(options: dict[str, Any], fields: set[str]) -> None:
    configured = fields.intersection(options)
    if configured:
        raise ValueError(
            f"literal Storage secret field {sorted(configured)[0]!r} is forbidden; use Env fields"
        )


def _validate_remote_root(value: str) -> None:
    normalized = posixpath.normpath(value or ".")
    if (
        value.startswith(("/", "\\"))
        or "\\" in value
        or "\x00" in value
        or normalized == ".."
        or normalized.startswith("../")
    ):
        raise ValueError("remote Storage rootPath must be a safe relative path")


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
