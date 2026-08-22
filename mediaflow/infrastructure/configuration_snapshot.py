from __future__ import annotations

import os
import platform
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from types import MappingProxyType
from typing import Any

from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION

MAX_SECTION_ITEMS = 100


@dataclass(frozen=True)
class ConfigurationSnapshot:
    """Immutable, deliberately allowlisted runtime configuration summary."""

    _document: Mapping[str, Any]

    def as_document(self) -> dict[str, Any]:
        return _thaw(self._document)


def build_configuration_snapshot(configuration: RuntimeConfiguration) -> ConfigurationSnapshot:
    strategy = configuration.strategy
    document = {
        "system": {
            "application_version": _application_version(),
            "python_version": platform.python_version(),
            "python_supported": (3, 11) <= sys.version_info[:2] < (3, 14),
            "runtime_schema_version": SCHEMA_VERSION,
            "platform": sys.platform,
            "maintenance_lock_support": (
                "posix_shared_exclusive" if os.name == "posix" else "shared_only"
            ),
            "configuration_valid": True,
            "maximum_active_jobs": configuration.automation_maximum_active_jobs,
            "stale_job_age_seconds": configuration.automation_stale_job_age_seconds,
        },
        "storages": _section(
            configuration.storage_definitions,
            key=lambda item: item.storage_id,
            value=lambda item: {
                "id": item.storage_id,
                "type": item.storage_type,
                "read_only": item.read_only,
            },
        ),
        "resource_libraries": _section(
            configuration.resource_libraries,
            key=lambda item: item.library_id,
            value=lambda item: {
                "id": item.library_id,
                "storage_id": item.storage_id,
                "enabled": item.enabled,
                "scan_mode": item.scan_mode.value,
                "max_depth": item.max_depth,
                "extension_count": len(item.file_extensions),
                "recognition_rule_set_id": item.recognition_rule_set_id,
            },
        ),
        "media_libraries": _section(
            configuration.media_libraries,
            key=lambda item: item.library_id,
            value=lambda item: {
                "id": item.library_id,
                "storage_id": item.storage_id,
                "enabled": item.enabled,
            },
        ),
        "recognition_types": _section(
            strategy.recognition_types,
            key=lambda item: item.type_id,
            value=lambda item: {"id": item.type_id, "enabled": item.enabled},
        ),
        "recognition_rules": _section(
            strategy.recognition_rules,
            key=lambda item: item.rule_id,
            value=lambda item: {
                "id": item.rule_id,
                "enabled": item.enabled,
                "priority": item.priority,
                "output_recognition_type_id": item.output_recognition_type_id,
            },
        ),
        "recognition_type_policies": _section(
            strategy.recognition_type_policies,
            key=lambda item: item.policy_id,
            value=lambda item: {
                "id": item.policy_id,
                "recognition_type_id": item.recognition_type_id,
                "metadata_policy_id": item.metadata_policy_id,
                "naming_policy_id": item.naming_policy_id,
                "classification_policy_id": item.classification_policy_id,
                "organize_policy_id": item.organize_policy_id,
                "enabled": item.enabled,
            },
        ),
        "metadata_policies": _section(
            strategy.metadata_policies,
            key=lambda item: item.policy_id,
            value=lambda item: {
                "id": item.policy_id,
                "provider_id": item.provider_id,
                "query_type": item.query_type.value,
                "enabled": item.enabled,
            },
        ),
        "naming_policies": _section(
            strategy.naming_policies,
            key=lambda item: item.policy_id,
            value=lambda item: {
                "id": item.policy_id,
                "enabled": item.enabled,
                "media_type_mode": item.media_type_mode.value,
                "missing_variable_strategy": item.missing_variable_strategy.value,
            },
        ),
        "classification_policies": _section(
            strategy.classification_policies,
            key=lambda item: item.policy_id,
            value=lambda item: {
                "id": item.policy_id,
                "enabled": item.enabled,
                "priority": item.priority,
                "rule_count": len(item.rules),
            },
        ),
        "organize_policies": _section(
            strategy.organize_policies,
            key=lambda item: item.policy_id,
            value=lambda item: {
                "id": item.policy_id,
                "operation": item.operation.value,
                "conflict_strategy": item.conflict_strategy.value,
            },
        ),
    }
    return ConfigurationSnapshot(_freeze(document))


def _section(values, *, key, value) -> dict[str, Any]:
    ordered = sorted(values, key=key)
    return {
        "total": len(ordered),
        "truncated": len(ordered) > MAX_SECTION_ITEMS,
        "items": [value(item) for item in ordered[:MAX_SECTION_ITEMS]],
    }


def _application_version() -> str:
    try:
        return version("mediaflow")
    except PackageNotFoundError:
        return "development"


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value):
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value
