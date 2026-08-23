from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol
from urllib.parse import urlparse


class ConfigurationObjectKind(StrEnum):
    STORAGE = "storage"
    RESOURCE_LIBRARY = "resource_library"
    MEDIA_LIBRARY = "media_library"
    METADATA_PROVIDER = "metadata_provider"
    METADATA_POLICY = "metadata_policy"
    RECOGNITION_RULE = "recognition_rule"
    RECOGNITION_TYPE = "recognition_type"
    RECOGNITION_TYPE_POLICY = "recognition_type_policy"
    NAMING_POLICY = "naming_policy"
    CLASSIFICATION_POLICY = "classification_policy"
    ORGANIZE_POLICY = "organize_policy"
    SCHEDULE = "schedule"
    SYSTEM_SETTINGS = "system_settings"


class StorageConfigurationType(StrEnum):
    LOCAL = "local"
    SMB = "smb"
    OPENLIST = "openlist"
    S3 = "s3"
    R2 = "r2"
    S3_COMPATIBLE = "s3-compatible"


@dataclass(frozen=True)
class ManagedStorageConfiguration:
    storage_id: str
    storage_type: StorageConfigurationType
    name: str
    root_path: str
    read_only: bool = False
    enabled: bool = True
    options: dict[str, Any] | None = None
    version: int = 1

    def document(self) -> dict[str, object]:
        return {
            "storageId": self.storage_id,
            "type": self.storage_type.value,
            "name": self.name,
            "rootPath": self.root_path,
            "readOnly": self.read_only,
            "enabled": self.enabled,
            "options": copy.deepcopy(self.options or {}),
        }


@dataclass(frozen=True)
class ConfigurationReferencePolicy:
    kind: ConfigurationObjectKind
    block_on_reference: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ConfigurationObjectKind):
            raise ValueError("configuration reference policy kind is required")

    def can_delete(self, reference_count: int) -> bool:
        if isinstance(reference_count, bool) or not isinstance(reference_count, int):
            raise ValueError("reference count must be an integer")
        if reference_count < 0:
            raise ValueError("reference count must not be negative")
        return not self.block_on_reference or reference_count == 0


@dataclass(frozen=True)
class ConfigurationChangeAudit:
    audit_id: str
    object_kind: ConfigurationObjectKind
    object_id: str
    action: str
    before: dict[str, object]
    after: dict[str, object]
    occurred_at: datetime
    actor: str

    def __post_init__(self) -> None:
        if not isinstance(self.object_kind, ConfigurationObjectKind):
            raise ValueError("configuration audit kind is required")
        if not self.audit_id or len(self.audit_id) > 128:
            raise ValueError("configuration audit ID must be a bounded non-empty string")
        if not self.object_id or len(self.object_id) > 128:
            raise ValueError("configuration object ID must be a bounded non-empty string")
        if not self.action or len(self.action) > 32:
            raise ValueError("configuration audit action must be a bounded non-empty string")
        if not isinstance(self.before, dict) or not isinstance(self.after, dict):
            raise ValueError("configuration audit documents must be objects")
        if not isinstance(self.actor, str) or not self.actor.strip() or len(self.actor) > 200:
            raise ValueError("configuration audit actor must be bounded and non-empty")
        if not isinstance(self.occurred_at, datetime):
            raise ValueError("configuration audit time must be a datetime")
        if self.occurred_at.tzinfo is None:
            raise ValueError("configuration audit time must include a timezone")
        for label, document in (("before", self.before), ("after", self.after)):
            try:
                encoded = json.dumps(document, allow_nan=False, sort_keys=True)
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"configuration audit {label} document must be JSON-compatible"
                ) from error
            if len(encoded.encode("utf-8")) > 128 * 1024:
                raise ValueError(f"configuration audit {label} document must be bounded")

    def safe_before(self) -> dict[str, object]:
        return self._safe_document(self.before)

    def safe_after(self) -> dict[str, object]:
        return self._safe_document(self.after)

    @staticmethod
    def _safe_document(value: dict[str, object]) -> dict[str, object]:
        forbidden = {
            "token",
            "password",
            "secret",
            "access_key",
            "secret_key",
            "session_token",
            "authorization",
            "username",
            "accesskey",
            "secretkey",
            "sessiontoken",
            "cookie",
            "api_key",
            "apikey",
        }
        return ManagedDocumentRedactor.redact(value, forbidden)


class ManagedDocumentRedactor:
    @staticmethod
    def redact(
        value: dict[str, object] | list[object] | object,
        forbidden_keys: set[str],
    ) -> dict[str, object] | list[object] | object:
        if isinstance(value, dict):
            result: dict[str, object] = {}
            for key, item in value.items():
                if str(key).lower() in forbidden_keys:
                    result[key] = "***REDACTED***"
                else:
                    result[key] = ManagedDocumentRedactor.redact(item, forbidden_keys)
            return result
        if isinstance(value, list):
            return [ManagedDocumentRedactor.redact(item, forbidden_keys) for item in value]
        return copy.deepcopy(value)


class ConfigurationVersionConflict(RuntimeError):
    """The persisted configuration object changed before an update could commit."""


class ConfigurationObjectReferenced(ValueError):
    def __init__(
        self,
        kind: ConfigurationObjectKind,
        object_id: str,
        reference_count: int,
    ) -> None:
        super().__init__(
            f"Configuration {kind.value} {object_id!r} has {reference_count} references"
        )
        self.kind = kind
        self.object_id = object_id
        self.reference_count = reference_count


@dataclass(frozen=True)
class ConfigurationReference:
    source_kind: ConfigurationObjectKind
    source_id: str
    target_kind: ConfigurationObjectKind
    target_id: str


class StorageConfigurationRepository(Protocol):
    def create_storage(
        self, storage: ManagedStorageConfiguration, audit: ConfigurationChangeAudit
    ) -> ManagedStorageConfiguration: ...

    def get_storage(self, storage_id: str) -> ManagedStorageConfiguration | None: ...

    def list_storages(
        self, *, include_disabled: bool = True
    ) -> tuple[ManagedStorageConfiguration, ...]: ...

    def update_storage(
        self,
        storage: ManagedStorageConfiguration,
        expected_version: int,
        audit: ConfigurationChangeAudit,
    ) -> ManagedStorageConfiguration: ...

    def delete_storage(self, storage_id: str, audit: ConfigurationChangeAudit) -> None: ...

    def list_references(self, kind: ConfigurationObjectKind, object_id: str) -> int: ...

    def record_storage_reference(self, reference: ConfigurationReference) -> None: ...

    def list_audits(
        self,
        kind: ConfigurationObjectKind,
        object_id: str,
        *,
        limit: int = 50,
    ) -> tuple[ConfigurationChangeAudit, ...]: ...


class StorageConfigurationValidator:
    ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
    ENV_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
    SECRET_FIELDS = {
        "token",
        "password",
        "secret",
        "access_key",
        "secret_key",
        "session_token",
        "authorization",
        "username",
        "cookie",
        "api_key",
        "accesskey",
        "secretkey",
        "sessiontoken",
    }
    MAX_NAME = 120
    MAX_ROOT = 4096
    MAX_OPTIONS_BYTES = 64 * 1024

    @classmethod
    def validate(cls, value: ManagedStorageConfiguration) -> ManagedStorageConfiguration:
        storage_id = cls._identifier(value.storage_id, "Storage ID")
        name = cls._text(value.name, "Storage name", cls.MAX_NAME)
        root_path = value.root_path
        if not isinstance(root_path, str) or "\x00" in root_path:
            raise ValueError("Storage rootPath must be a string without NUL")
        if len(root_path) > cls.MAX_ROOT:
            raise ValueError("Storage rootPath must be at most 4096 characters")
        if not isinstance(value.read_only, bool):
            raise ValueError("Storage readOnly must be boolean")
        if not isinstance(value.enabled, bool):
            raise ValueError("Storage enabled must be boolean")
        if (
            isinstance(value.version, bool)
            or not isinstance(value.version, int)
            or value.version < 1
        ):
            raise ValueError("Storage version must be a positive integer")
        storage_type = cls._storage_type(value.storage_type)
        options = cls._options(value.options)
        if storage_type is StorageConfigurationType.LOCAL:
            if not root_path:
                raise ValueError("Local Storage rootPath must be non-empty")
        elif storage_type in {
            StorageConfigurationType.SMB,
            StorageConfigurationType.S3,
            StorageConfigurationType.R2,
            StorageConfigurationType.S3_COMPATIBLE,
        }:
            cls._validate_remote_root(root_path)
        if storage_type is StorageConfigurationType.OPENLIST:
            cls._env(options, "tokenEnv")
            cls._absolute_http_url(options, "baseUrl", required=True)
            cls._positive_number(options, "connectTimeout")
            cls._positive_number(options, "requestTimeout")
            cls._positive_integer(options, "maxConcurrency")
            cls._nonnegative_integer(options, "maxRetries")
            cls._positive_integer(options, "pageSize")
        elif storage_type is StorageConfigurationType.SMB:
            cls._env(options, "usernameEnv")
            cls._env(options, "passwordEnv")
            cls._required_text(options, "host", 255)
            cls._required_text(options, "share", 255)
            cls._optional_text(options, "domain", 255)
            cls._port(options)
            cls._positive_number(options, "connectTimeout")
            cls._positive_number(options, "operationTimeout")
            cls._positive_integer(options, "maxConcurrency")
        elif storage_type in {
            StorageConfigurationType.S3,
            StorageConfigurationType.R2,
            StorageConfigurationType.S3_COMPATIBLE,
        }:
            cls._env(options, "accessKeyEnv")
            cls._env(options, "secretKeyEnv")
            cls._env(options, "sessionTokenEnv", required=False)
            bucket = cls._required_text(options, "bucket", 63)
            if "/" in bucket or bucket.startswith("s3:"):
                raise ValueError("Storage bucket must be a bucket name")
            endpoint = cls._absolute_http_url(options, "endpoint", required=False)
            if storage_type is not StorageConfigurationType.S3 and not endpoint:
                raise ValueError("R2 and S3-compatible Storage require an endpoint")
            cls._optional_text(options, "region", 128)
            cls._boolean(options, "forcePathStyle")
            cls._positive_number(options, "connectTimeout")
            cls._positive_number(options, "requestTimeout")
            cls._positive_integer(options, "maxConcurrency")
            cls._nonnegative_integer(options, "maxRetries")
            cls._positive_integer(options, "pageSize")
            cls._positive_integer(options, "multipartThreshold")
            cls._positive_integer(options, "multipartPartSize", minimum=5 * 1024 * 1024)

        return replace(
            value,
            storage_id=storage_id,
            storage_type=storage_type,
            name=name,
            root_path=root_path,
            options=options,
        )

    @staticmethod
    def _identifier(value: object, label: str) -> str:
        pattern = StorageConfigurationValidator.ID_PATTERN
        if not isinstance(value, str) or not pattern.fullmatch(value):
            raise ValueError(f"{label} must match [a-z0-9][a-z0-9_-] and be at most 64 characters")
        return value

    @staticmethod
    def _text(value: object, label: str, maximum: int) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise ValueError(f"{label} must be a non-empty string of at most {maximum} characters")
        if any(character in value for character in ("\r", "\n", "\x00")):
            raise ValueError(f"{label} must not contain control characters")
        return value

    @staticmethod
    def _storage_type(value: object) -> StorageConfigurationType:
        if isinstance(value, StorageConfigurationType):
            return value
        if not isinstance(value, str):
            raise ValueError("Storage type must be a supported string")
        try:
            return StorageConfigurationType(value.lower())
        except ValueError as error:
            supported = ", ".join(item.value for item in StorageConfigurationType)
            raise ValueError(
                f"unsupported Storage type {value!r}; expected one of {supported}"
            ) from error

    @classmethod
    def _options(cls, value: object) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("Storage options must be an object")
        for key in value:
            if not isinstance(key, str) or not key or len(key) > 128:
                raise ValueError(
                    "Storage option names must be non-empty strings of at most 128 characters"
                )
            if key.lower() in cls.SECRET_FIELDS:
                raise ValueError(
                    f"literal Storage secret field {key!r} is forbidden; use Env fields"
                )
        cls._validate_json_value(value, "Storage options")
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(encoded.encode("utf-8")) > cls.MAX_OPTIONS_BYTES:
            raise ValueError("Storage options must be at most 65536 bytes")
        return copy.deepcopy(value)

    @classmethod
    def _validate_json_value(cls, value: object, label: str) -> None:
        if value is None or isinstance(value, bool | str):
            if isinstance(value, str) and ("\x00" in value or len(value) > 4096):
                raise ValueError(f"{label} strings must be non-NUL and at most 4096 characters")
            return
        if isinstance(value, int):
            return
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError(f"{label} numbers must be finite")
            return
        if isinstance(value, list):
            if len(value) > 256:
                raise ValueError(f"{label} arrays must contain at most 256 values")
            for item in value:
                cls._validate_json_value(item, label)
            return
        if isinstance(value, dict):
            if len(value) > 256:
                raise ValueError(f"{label} objects must contain at most 256 fields")
            for key, item in value.items():
                if not isinstance(key, str) or not key or len(key) > 128:
                    raise ValueError(f"{label} object names must be bounded strings")
                if key.lower() in cls.SECRET_FIELDS:
                    raise ValueError(
                        f"literal Storage secret field {key!r} is forbidden; use Env fields"
                    )
                cls._validate_json_value(item, label)
            return
        raise ValueError(f"{label} must contain only JSON-compatible values")

    @staticmethod
    def _validate_remote_root(value: str) -> None:
        from posixpath import normpath

        normalized = normpath(value or ".")
        if (
            value.startswith(("/", "\\"))
            or "\\" in value
            or normalized == ".."
            or normalized.startswith("../")
        ):
            raise ValueError("remote Storage rootPath must be a safe relative path")

    @staticmethod
    def _absolute_http_url(
        options: dict[str, Any],
        key: str,
        *,
        required: bool,
    ) -> str | None:
        value = options.get(key)
        if value is None:
            if required:
                raise ValueError(f"Storage {key} is required")
            return None
        if not isinstance(value, str) or len(value) > 2048 or "\x00" in value:
            raise ValueError(f"Storage {key} must be a bounded URL string")
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"Storage {key} must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError(f"Storage {key} must not contain credentials, query, or fragment")
        return value

    @classmethod
    def _env(cls, options: dict[str, Any], key: str, *, required: bool = True) -> str | None:
        value = options.get(key)
        if value is None and not required:
            return None
        if not isinstance(value, str) or not cls.ENV_PATTERN.fullmatch(value):
            raise ValueError(f"Storage {key} must be a valid environment variable name")
        return value

    @staticmethod
    def _required_text(options: dict[str, Any], key: str, maximum: int) -> str:
        value = options.get(key)
        if not isinstance(value, str) or not value or len(value) > maximum or "\x00" in value:
            raise ValueError(f"Storage {key} must be a non-empty bounded string")
        return value

    @staticmethod
    def _optional_text(options: dict[str, Any], key: str, maximum: int) -> str | None:
        value = options.get(key)
        if value is None:
            return None
        if not isinstance(value, str) or len(value) > maximum or "\x00" in value:
            raise ValueError(f"Storage {key} must be a bounded string")
        return value

    @staticmethod
    def _boolean(options: dict[str, Any], key: str, *, default: object = None) -> object:
        if key not in options or options[key] is default:
            return default
        if not isinstance(options[key], bool):
            raise ValueError(f"Storage {key} must be boolean")
        return options[key]

    @staticmethod
    def _positive_number(options: dict[str, Any], key: str, *, default: object = None) -> object:
        if key not in options or options[key] is default:
            return default
        value = options[key]
        if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
            raise ValueError(f"Storage {key} must be a positive number")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"Storage {key} must be a positive number")
        return value

    @classmethod
    def _positive_integer(
        cls,
        options: dict[str, Any],
        key: str,
        *,
        default: object = None,
        minimum: int = 1,
    ) -> object:
        if key not in options or options[key] is default:
            return default
        value = options[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"Storage {key} must be an integer of at least {minimum}")
        return value

    @classmethod
    def _nonnegative_integer(cls, options: dict[str, Any], key: str) -> object:
        if key not in options:
            return None
        value = options[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"Storage {key} must be a non-negative integer")
        return value

    @classmethod
    def _port(cls, options: dict[str, Any]) -> object:
        if "port" not in options:
            return None
        value = cls._positive_integer(options, "port")
        assert isinstance(value, int)
        if value > 65535:
            raise ValueError("Storage port must be between 1 and 65535")
        return value


def validate_storage_configuration(
    value: ManagedStorageConfiguration,
) -> ManagedStorageConfiguration:
    return StorageConfigurationValidator.validate(value)


def validate_configuration_object_id(value: str) -> str:
    return StorageConfigurationValidator._identifier(value, "Configuration object ID")


class ConfigurationManagementRepository(Protocol):
    def list_references(self, kind: ConfigurationObjectKind, object_id: str) -> int: ...
    def audit_change(self, audit: ConfigurationChangeAudit) -> None: ...
