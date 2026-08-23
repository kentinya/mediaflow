from __future__ import annotations

import inspect
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from mediaflow.application.configuration_management import StorageConfigurationService
from mediaflow.domain.configuration_management import (
    ConfigurationChangeAudit,
    ConfigurationObjectKind,
    ConfigurationObjectReferenced,
    ConfigurationReference,
    ConfigurationReferencePolicy,
    ConfigurationVersionConflict,
    ManagedStorageConfiguration,
    StorageConfigurationType,
    validate_storage_configuration,
)
from mediaflow.infrastructure.sqlite_configuration_management import (
    CONFIGURATION_SCHEMA_VERSION,
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository


class StorageConfigurationValidationTests(unittest.TestCase):
    def test_validates_every_supported_storage_family(self) -> None:
        cases = {
            StorageConfigurationType.LOCAL: ManagedStorageConfiguration(
                "local-source", "local", "Local source", "/media/incoming"
            ),
            StorageConfigurationType.SMB: ManagedStorageConfiguration(
                "nas",
                "smb",
                "NAS",
                "media/incoming",
                options={
                    "host": "nas.example",
                    "share": "media",
                    "usernameEnv": "SMB_USER",
                    "passwordEnv": "SMB_PASSWORD",
                },
            ),
            StorageConfigurationType.OPENLIST: ManagedStorageConfiguration(
                "openlist",
                "openlist",
                "OpenList",
                "media",
                options={"baseUrl": "https://openlist.example", "tokenEnv": "OPENLIST_TOKEN"},
            ),
            StorageConfigurationType.S3: _s3("aws", "s3", "AWS"),
            StorageConfigurationType.R2: _s3(
                "r2", "r2", "R2", endpoint="https://account.r2.cloudflarestorage.com"
            ),
            StorageConfigurationType.S3_COMPATIBLE: _s3(
                "minio",
                "s3-compatible",
                "MinIO",
                force_path_style=True,
                endpoint="https://minio.example.com",
            ),
        }
        for expected_type, storage in cases.items():
            with self.subTest(expected_type):
                validated = validate_storage_configuration(storage)
                self.assertEqual(validated.storage_type, expected_type)
                self.assertEqual(validated.version, 1)
                self.assertTrue(validated.enabled)

    def test_rejects_invalid_identity_and_root_values(self) -> None:
        cases = [
            ManagedStorageConfiguration("Bad ID", "local", "Local", "/media"),
            ManagedStorageConfiguration("x" * 65, "local", "Local", "/media"),
            ManagedStorageConfiguration("source", "local", "", "/media"),
            ManagedStorageConfiguration("source", "local", "Local", ""),
            ManagedStorageConfiguration("source", "local", "Local", "/media\0"),
            ManagedStorageConfiguration("source", "local", "Local", "/media", enabled=1),
            ManagedStorageConfiguration("source", "unknown", "Local", "/media"),
            ManagedStorageConfiguration("nas", "smb", "NAS", "/absolute", options=_smb_options()),
            ManagedStorageConfiguration("nas", "smb", "NAS", "../escape", options=_smb_options()),
        ]
        for storage in cases:
            with self.subTest((storage.storage_id, storage.storage_type, storage.root_path)):
                with self.assertRaises(ValueError):
                    validate_storage_configuration(storage)

    def test_rejects_missing_environment_names_and_invalid_provider_options(self) -> None:
        cases = [
            ManagedStorageConfiguration(
                "nas", "smb", "NAS", "media", options={"host": "nas", "share": "media"}
            ),
            ManagedStorageConfiguration(
                "nas",
                "smb",
                "NAS",
                "media",
                options=_smb_options() | {"port": 70000},
            ),
            ManagedStorageConfiguration(
                "openlist", "openlist", "OpenList", "media", options={"tokenEnv": "BAD-NAME"}
            ),
            ManagedStorageConfiguration(
                "openlist",
                "openlist",
                "OpenList",
                "media",
                options={"tokenEnv": "TOKEN", "baseUrl": "not-a-url"},
            ),
            ManagedStorageConfiguration(
                "r2",
                "r2",
                "R2",
                "media",
                options=_s3_options(),
            ),
            ManagedStorageConfiguration(
                "aws", "s3", "AWS", "media", options=_s3_options() | {"forcePathStyle": "yes"}
            ),
            ManagedStorageConfiguration(
                "aws", "s3", "AWS", "media", options=_s3_options() | {"connectTimeout": 0}
            ),
            ManagedStorageConfiguration(
                "aws",
                "s3",
                "AWS",
                "media",
                options=_s3_options() | {"bucket": "media/example"},
            ),
            ManagedStorageConfiguration(
                "minio",
                "s3-compatible",
                "MinIO",
                "media",
                options=_s3_options()
                | {
                    "endpoint": "https://user:pass@minio.example.com",
                    "multipartPartSize": 1024,
                },
            ),
        ]
        for storage in cases:
            with self.subTest(storage.storage_type):
                with self.assertRaises(ValueError):
                    validate_storage_configuration(storage)

    def test_rejects_literal_and_nested_secrets_and_non_json_values(self) -> None:
        cases = [
            ManagedStorageConfiguration(
                "openlist", "openlist", "OpenList", "media", options={"token": "raw"}
            ),
            ManagedStorageConfiguration(
                "aws",
                "s3",
                "AWS",
                "media",
                options=_s3_options() | {"nested": {"secretKey": "raw"}},
            ),
            ManagedStorageConfiguration(
                "local", "local", "Local", "/media", options={"value": object()}
            ),
            ManagedStorageConfiguration(
                "local",
                "local",
                "Local",
                "/media",
                options={"number": float("inf")},
            ),
        ]
        for storage in cases:
            with self.subTest(next(iter(storage.options or {}))):
                with self.assertRaises(ValueError):
                    validate_storage_configuration(storage)


class StorageConfigurationServiceTests(unittest.TestCase):
    def test_create_read_update_copy_enable_disable_delete_and_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "configuration.sqlite3"
            with SQLiteConfigurationRepository(database) as repository:
                service = StorageConfigurationService(repository)
                created = service.create(
                    ManagedStorageConfiguration("source", "local", "Source", "/media/incoming"),
                    actor="operator",
                )
                self.assertEqual(created.version, 1)
                self.assertEqual(service.get("source").name, "Source")

                updated = service.update(
                    "source",
                    ManagedStorageConfiguration(
                        "source", "local", "Source Two", "/media/new", version=1
                    ),
                    expected_version=1,
                    actor="operator",
                )
                self.assertEqual(updated.version, 2)
                self.assertEqual(service.get("source").root_path, "/media/new")

                copied = service.copy("source", "target", name="Target", actor="operator")
                self.assertEqual(copied.name, "Target")
                self.assertEqual(copied.version, 1)

                disabled = service.disable("source", actor="operator")
                self.assertFalse(disabled.enabled)
                enabled = service.enable("source", actor="operator")
                self.assertTrue(enabled.enabled)
                self.assertEqual(
                    tuple(item.storage_id for item in service.list(include_disabled=False)),
                    ("source", "target"),
                )

                audits = service.audits("source")
                self.assertEqual(
                    [item.action for item in audits], ["enable", "disable", "update", "create"]
                )
                self.assertEqual(audits[-1].safe_before(), {})
                self.assertEqual(audits[-1].safe_after()["storageId"], "source")

                service.delete("target", actor="operator")
                self.assertIsNone(repository.get_storage("target"))
                self.assertEqual(service.audits("target", limit=10)[0].action, "delete")

                with self.assertRaises(LookupError):
                    service.delete("target", actor="operator")

    def test_invalid_duplicate_conflict_and_referenced_operations_do_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "configuration.sqlite3"
            with SQLiteConfigurationRepository(database) as repository:
                service = StorageConfigurationService(repository)
                storage = ManagedStorageConfiguration(
                    "source", "local", "Source", "/media/incoming"
                )
                service.create(storage, actor="operator")
                before = service.get("source")

                with self.assertRaisesRegex(ValueError, "already exists"):
                    service.create(storage, actor="operator")
                with self.assertRaises(ValueError):
                    service.create(
                        ManagedStorageConfiguration(
                            "bad", "local", "Bad", "/media", options={"password": "raw"}
                        ),
                        actor="operator",
                    )
                with self.assertRaisesRegex(ValueError, "version 1"):
                    service.create(
                        ManagedStorageConfiguration("new", "local", "New", "/media", version=2),
                        actor="operator",
                    )
                with self.assertRaises(ValueError):
                    service.update(
                        "source",
                        ManagedStorageConfiguration("different", "local", "Changed", "/media"),
                        expected_version=before.version,
                        actor="operator",
                    )
                with self.assertRaises(ConfigurationVersionConflict):
                    service.update(
                        "source",
                        ManagedStorageConfiguration(
                            "source", "local", "Changed", "/media", version=99
                        ),
                        expected_version=before.version,
                        actor="operator",
                    )
                self.assertEqual(service.get("source"), before)
                self.assertEqual(service.audits("source", limit=10)[0].action, "create")

                repository.record_storage_reference(
                    ConfigurationReference(
                        ConfigurationObjectKind.RESOURCE_LIBRARY,
                        "incoming",
                        ConfigurationObjectKind.STORAGE,
                        "source",
                    )
                )
                self.assertEqual(
                    repository.list_references(ConfigurationObjectKind.STORAGE, "source"), 1
                )
                with self.assertRaises(ConfigurationObjectReferenced) as context:
                    service.delete("source", actor="operator")
                self.assertEqual(context.exception.reference_count, 1)
                self.assertEqual(service.get("source"), before)
                self.assertEqual(service.audits("source", limit=10)[0].action, "create")

    def test_repository_reference_input_and_schema_marker_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "configuration.sqlite3"
            with SQLiteConfigurationRepository(database) as repository:
                service = StorageConfigurationService(repository)
                service.create(
                    ManagedStorageConfiguration("source", "local", "Source", "/media"),
                    actor="operator",
                )
                invalid_references = [
                    ConfigurationReference(
                        ConfigurationObjectKind.NAMING_POLICY,
                        "naming",
                        ConfigurationObjectKind.STORAGE,
                        "source",
                    ),
                    ConfigurationReference(
                        ConfigurationObjectKind.RESOURCE_LIBRARY,
                        "incoming",
                        ConfigurationObjectKind.NAMING_POLICY,
                        "naming",
                    ),
                    ConfigurationReference(
                        ConfigurationObjectKind.RESOURCE_LIBRARY,
                        "incoming",
                        ConfigurationObjectKind.STORAGE,
                        "missing",
                    ),
                ]
                for reference in invalid_references:
                    with self.subTest(reference):
                        with self.assertRaises((ValueError, LookupError)):
                            repository.record_storage_reference(reference)
                with self.assertRaises(ValueError):
                    repository.list_audits(ConfigurationObjectKind.STORAGE, "source", limit=0)

            with closing(sqlite3.connect(database)) as connection:
                row = connection.execute(
                    "SELECT version FROM schema_version WHERE component='configuration_management'"
                ).fetchone()
                self.assertEqual(row[0], CONFIGURATION_SCHEMA_VERSION)
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                self.assertIn("configuration_objects", tables)
                self.assertIn("configuration_references", tables)
                self.assertIn("configuration_change_audits", tables)

    def test_audit_failure_rolls_back_storage_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteConfigurationRepository(
                Path(directory) / "configuration.sqlite3"
            ) as repository:
                first = validate_storage_configuration(
                    ManagedStorageConfiguration("one", "local", "One", "/media/one")
                )
                second = validate_storage_configuration(
                    ManagedStorageConfiguration("two", "local", "Two", "/media/two")
                )
                audit_id = str(uuid4())
                repository.create_storage(first, _audit(audit_id, "one", "create"))
                with self.assertRaises(sqlite3.IntegrityError):
                    repository.create_storage(second, _audit(audit_id, "two", "create"))
                self.assertEqual(
                    tuple(item.storage_id for item in repository.list_storages()), ("one",)
                )
                self.assertEqual(
                    tuple(
                        item.audit_id
                        for item in repository.list_audits(ConfigurationObjectKind.STORAGE, "one")
                    ),
                    (audit_id,),
                )

    def test_audit_storage_redacts_secret_like_payload_and_never_constructs_storage(self) -> None:
        source = inspect.getsource(StorageConfigurationService)
        repository_source = inspect.getsource(SQLiteConfigurationRepository)
        for forbidden in ("LocalStorage", "SMBStorage", "OpenListStorage", "S3Storage"):
            self.assertNotIn(forbidden, source)
            self.assertNotIn(forbidden, repository_source)

        audit = ConfigurationChangeAudit(
            "audit-redacted",
            ConfigurationObjectKind.STORAGE,
            "source",
            "update",
            {"options": {"password": "raw"}},
            {"options": {"password": "new-raw", "accessKey": "raw-key"}},
            datetime.now(UTC),
            "operator",
        )
        self.assertEqual(audit.safe_before()["options"]["password"], "***REDACTED***")
        self.assertEqual(audit.safe_after()["options"]["password"], "***REDACTED***")
        self.assertEqual(audit.safe_after()["options"]["accessKey"], "***REDACTED***")

    def test_rejects_unbounded_and_invalid_audit_or_reference_inputs(self) -> None:
        policy = ConfigurationReferencePolicy(ConfigurationObjectKind.STORAGE)
        with self.assertRaises(ValueError):
            policy.can_delete(-1)
        with self.assertRaises(ValueError):
            ConfigurationChangeAudit(
                "x" * 129,
                ConfigurationObjectKind.STORAGE,
                "source",
                "create",
                {},
                {},
                datetime.now(UTC),
                "operator",
            )
        with self.assertRaises(ValueError):
            ConfigurationChangeAudit(
                "audit",
                ConfigurationObjectKind.STORAGE,
                "source",
                "create",
                {},
                {},
                datetime.now(),
                "operator",
            )
        with self.assertRaises(ValueError):
            ConfigurationChangeAudit(
                "audit",
                ConfigurationObjectKind.STORAGE,
                "source",
                "create",
                {"value": object()},
                {},
                datetime.now(UTC),
                "operator",
            )

    def test_configuration_schema_can_coexist_with_runtime_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "mediaflow.sqlite3"
            with SQLiteTaskRepository(database):
                with SQLiteConfigurationRepository(database) as repository:
                    repository.create_storage(
                        validate_storage_configuration(
                            ManagedStorageConfiguration("source", "local", "Source", "/media")
                        ),
                        _audit(str(uuid4()), "source", "create"),
                    )
                    self.assertIsNotNone(repository.get_storage("source"))

            with closing(sqlite3.connect(database)) as connection:
                components = {
                    row[0]: row[1]
                    for row in connection.execute("SELECT component, version FROM schema_version")
                }
            self.assertEqual(components["runtime"], SCHEMA_VERSION)
            self.assertEqual(components["configuration_management"], CONFIGURATION_SCHEMA_VERSION)


def _s3(
    storage_id: str,
    storage_type: str,
    name: str,
    *,
    force_path_style: bool = False,
    endpoint: str | None = None,
) -> ManagedStorageConfiguration:
    return ManagedStorageConfiguration(
        storage_id,
        storage_type,
        name,
        "media",
        options=_s3_options()
        | ({"endpoint": endpoint} if endpoint else {})
        | {"forcePathStyle": force_path_style},
    )


def _s3_options() -> dict[str, object]:
    return {
        "bucket": "media",
        "accessKeyEnv": "S3_ACCESS_KEY",
        "secretKeyEnv": "S3_SECRET_KEY",
    }


def _smb_options() -> dict[str, object]:
    return {
        "host": "nas.example",
        "share": "media",
        "usernameEnv": "SMB_USER",
        "passwordEnv": "SMB_PASSWORD",
    }


def _audit(audit_id: str, storage_id: str, action: str) -> ConfigurationChangeAudit:
    return ConfigurationChangeAudit(
        audit_id,
        ConfigurationObjectKind.STORAGE,
        storage_id,
        action,
        {},
        {},
        datetime.now(UTC),
        "operator",
    )


if __name__ == "__main__":
    unittest.main()
