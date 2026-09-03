from __future__ import annotations

import io
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.configuration_management import (
    ConfigurationStorageCheckStatus,
    ConfigurationVersionConflict,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.storage import (
    StorageCapabilities,
    StorageEntry,
    StorageEntryType,
    StorageError,
    StorageErrorCode,
)
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import APP_JS
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_configuration_objects import example_document


def request(
    api,
    path: str,
    *,
    method: str = "GET",
    body: object | None = None,
    token: str = "admin-token",
) -> tuple[int, dict]:
    payload = b"" if body is None else json.dumps(body).encode("utf-8")
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": str(len(payload)),
        "wsgi.input": io.BytesIO(payload),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
    }
    result = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(result)


class FakeStorage:
    def __init__(
        self,
        storage_id: str,
        *,
        read_only: bool = False,
        capabilities: StorageCapabilities | None = None,
        error: BaseException | None = None,
        malformed: str | None = None,
    ) -> None:
        self.storage_id = storage_id
        self.name = storage_id
        self.read_only = read_only
        self.capabilities = capabilities or StorageCapabilities(
            can_move=True,
            can_copy=True,
            can_delete=True,
            can_hard_link=True,
            can_soft_link=True,
        )
        self.error = error
        self.malformed = malformed
        self.read_calls: list[tuple[str, str]] = []
        self.mutation_calls = {
            name: 0
            for name in (
                "write",
                "create_directory",
                "move",
                "copy",
                "delete",
                "hard_link",
                "soft_link",
            )
        }

    def _read(self, operation: str, path: str):
        self.read_calls.append((operation, path))
        if self.error is not None:
            raise self.error
        if self.malformed == operation:
            return {"provider": "malformed"}
        return StorageEntry(
            "",
            "",
            StorageEntryType.DIRECTORY,
            0,
            datetime.now(UTC),
        )

    def stat(self, path: str):
        return self._read("stat", path)

    def list(self, path: str):
        value = self._read("list", path)
        if isinstance(value, StorageEntry):
            return ()
        return value

    def exists(self, path: str) -> bool:
        self._read("exists", path)
        return True

    def read(self, path: str):
        self._read("read", path)
        return io.BytesIO(b"")

    def _mutate(self, operation: str, *_args, **_kwargs):
        self.mutation_calls[operation] += 1
        raise AssertionError(f"unexpected Storage mutation: {operation}")

    def write(self, *args, **kwargs):
        return self._mutate("write", *args, **kwargs)

    def create_directory(self, *args, **kwargs):
        return self._mutate("create_directory", *args, **kwargs)

    def move(self, *args, **kwargs):
        return self._mutate("move", *args, **kwargs)

    def copy(self, *args, **kwargs):
        return self._mutate("copy", *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self._mutate("delete", *args, **kwargs)

    def hard_link(self, *args, **kwargs):
        return self._mutate("hard_link", *args, **kwargs)

    def soft_link(self, *args, **kwargs):
        return self._mutate("soft_link", *args, **kwargs)


class StorageSetupCheckTests(unittest.TestCase):
    def _document(self, root: Path) -> dict[str, object]:
        document = example_document()
        document["persistence"]["databasePath"] = str(root / "configuration.sqlite3")
        document["storages"] = [
            {
                "id": "local-check",
                "name": "Local check",
                "type": "local",
                "rootPath": str(root / "local"),
                "readOnly": False,
                "enabled": True,
            },
            {
                "id": "smb-check",
                "name": "SMB check",
                "type": "smb",
                "rootPath": "media",
                "readOnly": False,
                "enabled": True,
                "options": {
                    "host": "nas.invalid",
                    "share": "media",
                    "usernameEnv": "MF_CHECK_SMB_USER",
                    "passwordEnv": "MF_CHECK_SMB_PASSWORD",
                },
            },
            {
                "id": "openlist-check",
                "name": "OpenList check",
                "type": "openlist",
                "rootPath": "/Media",
                "readOnly": False,
                "enabled": True,
                "options": {
                    "baseUrl": "https://openlist.invalid",
                    "tokenEnv": "MF_CHECK_OPENLIST_TOKEN",
                },
            },
            {
                "id": "s3-check",
                "name": "S3 check",
                "type": "s3",
                "rootPath": "media",
                "readOnly": False,
                "enabled": True,
                "options": {
                    "bucket": "media",
                    "region": "us-east-1",
                    "accessKeyEnv": "MF_CHECK_S3_ACCESS",
                    "secretKeyEnv": "MF_CHECK_S3_SECRET",
                },
            },
            {
                "id": "r2-check",
                "name": "R2 check",
                "type": "r2",
                "rootPath": "media",
                "readOnly": True,
                "enabled": True,
                "options": {
                    "bucket": "media",
                    "endpoint": "https://r2.invalid",
                    "accessKeyEnv": "MF_CHECK_R2_ACCESS",
                    "secretKeyEnv": "MF_CHECK_R2_SECRET",
                },
            },
            {
                "id": "compatible-check",
                "name": "S3 compatible check",
                "type": "s3-compatible",
                "rootPath": "media",
                "readOnly": False,
                "enabled": True,
                "options": {
                    "bucket": "media",
                    "endpoint": "https://s3.invalid",
                    "accessKeyEnv": "MF_CHECK_COMPAT_ACCESS",
                    "secretKeyEnv": "MF_CHECK_COMPAT_SECRET",
                },
            },
        ]
        return document

    @staticmethod
    def _environment() -> dict[str, str]:
        return {
            "MF_CHECK_SMB_USER": "unit-user",
            "MF_CHECK_SMB_PASSWORD": "unit-password",
            "MF_CHECK_OPENLIST_TOKEN": "unit-token",
            "MF_CHECK_S3_ACCESS": "unit-access",
            "MF_CHECK_S3_SECRET": "unit-secret",
            "MF_CHECK_R2_ACCESS": "unit-r2-access",
            "MF_CHECK_R2_SECRET": "unit-r2-secret",
            "MF_CHECK_COMPAT_ACCESS": "unit-compat-access",
            "MF_CHECK_COMPAT_SECRET": "unit-compat-secret",
        }

    def _open(self, root: Path, *, adapters=None, document=None):
        repository = SQLiteConfigurationRepository(root / "configuration.sqlite3")
        managed = ManagedConfigurationService(repository)
        revision = managed.import_draft(
            document or self._document(root),
            actor="operator",
        )
        objects = ConfigurationObjectService(managed, storage_adapters=adapters)
        return repository, managed, objects, revision

    @staticmethod
    def _check(objects, revision, storage_id):
        return objects.storage_check(
            revision.revision_id,
            storage_id=storage_id,
            expected_version=revision.version,
            expected_digest=revision.digest,
            actor="operator",
        )

    def test_all_six_kinds_share_success_path_and_persist_bounded_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "local").mkdir()
            adapters = {
                storage_id: FakeStorage(storage_id)
                for storage_id in (
                    "smb-check",
                    "openlist-check",
                    "s3-check",
                    "r2-check",
                    "compatible-check",
                )
            }
            with (
                patch.dict(os.environ, self._environment(), clear=False),
                patch(
                    "mediaflow.application.configuration_objects.load_runtime_configuration",
                    side_effect=AssertionError("full runtime loader reached"),
                ),
            ):
                repository, managed, objects, revision = self._open(root, adapters=adapters)
                try:
                    values = ["local-check", *adapters]
                    for storage_id in values:
                        with self.subTest(storage_id=storage_id):
                            evidence = self._check(objects, revision, storage_id)
                            self.assertIs(
                                evidence.status,
                                ConfigurationStorageCheckStatus.PASSED,
                            )
                            self.assertEqual(evidence.revision_id, revision.revision_id)
                            self.assertEqual(evidence.revision_version, revision.version)
                            self.assertEqual(evidence.revision_digest, revision.digest)
                            self.assertEqual(
                                evidence.operations,
                                ("stat:root", "list:root"),
                            )
                            self.assertEqual(evidence.attempted_operations, evidence.operations)
                            self.assertEqual(evidence.document()["sideEffects"], "none")
                            self.assertTrue(evidence.document()["retrySafe"])
                            self.assertEqual(evidence.document()["capabilityProbe"], "not_run")
                            self.assertNotIn("unit-secret", repr(evidence.document()))

                    detail = objects.revision_detail(revision.revision_id)
                    self.assertEqual(len(detail["storageChecks"]), 6)
                    self.assertTrue(all(item["current"] for item in detail["storageChecks"]))
                    reloaded = SQLiteConfigurationRepository(root / "configuration.sqlite3")
                    try:
                        reloaded_objects = ConfigurationObjectService(
                            ManagedConfigurationService(reloaded)
                        )
                        reloaded_detail = reloaded_objects.revision_detail(revision.revision_id)
                        self.assertEqual(len(reloaded_detail["storageChecks"]), 6)
                        self.assertEqual(
                            reloaded_detail["storageChecks"][0]["completedReadOperations"],
                            ["stat:root", "list:root"],
                        )
                    finally:
                        reloaded.close()
                    for adapter in adapters.values():
                        self.assertEqual(adapter.read_calls, [("stat", ""), ("list", "")])
                        self.assertEqual(set(adapter.mutation_calls.values()), {0})
                finally:
                    repository.close()

    def test_failures_are_normalized_redacted_and_retryable(self) -> None:
        cases = (
            (StorageErrorCode.PERMISSION_DENIED, "permission_denied"),
            (StorageErrorCode.AUTHENTICATION_FAILED, "authentication_failed"),
            (StorageErrorCode.TIMEOUT, "timeout"),
            (StorageErrorCode.CONNECTION_FAILED, "connection_failed"),
            (StorageErrorCode.NOT_FOUND, "not_found"),
            (StorageErrorCode.INVALID_PATH, "invalid_path"),
            (StorageErrorCode.RATE_LIMITED, "rate_limited"),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict(os.environ, self._environment(), clear=False):
                for index, (code, expected_category) in enumerate(cases):
                    storage_id = "smb-check"
                    adapter = FakeStorage(
                        storage_id,
                        error=StorageError(
                            code,
                            "list",
                            "private/root",
                            "raw provider secret unit-secret payload",
                        ),
                    )
                    repository, managed, objects, revision = self._open(
                        root / f"case-{index}",
                        adapters={storage_id: adapter},
                    )
                    try:
                        evidence = self._check(objects, revision, storage_id)
                        self.assertIs(evidence.status, ConfigurationStorageCheckStatus.FAILED)
                        self.assertEqual(evidence.failure_category, expected_category)
                        self.assertLessEqual(len(evidence.message or ""), 500)
                        self.assertNotIn("private/root", evidence.message or "")
                        self.assertNotIn("unit-secret", repr(evidence.document()))
                        self.assertTrue(evidence.document()["retrySafe"])
                        self.assertTrue(evidence.next_action)
                        self.assertEqual(evidence.attempted_operations, ("stat:root",))
                        self.assertEqual(evidence.operations, ())
                        self.assertEqual(set(adapter.mutation_calls.values()), {0})
                    finally:
                        repository.close()

    def test_malformed_response_and_missing_secret_fail_before_external_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict(os.environ, self._environment(), clear=False):
                malformed = FakeStorage("smb-check", malformed="list")
                repository, managed, objects, revision = self._open(
                    root / "malformed",
                    adapters={"smb-check": malformed},
                )
                try:
                    evidence = self._check(objects, revision, "smb-check")
                    self.assertEqual(evidence.failure_category, "unknown")
                    self.assertEqual(evidence.attempted_operations, ("stat:root", "list:root"))
                    self.assertEqual(evidence.operations, ("stat:root", "list:root"))
                finally:
                    repository.close()

                missing_document = self._document(root / "missing")
                missing_document["storages"][1]["options"]["passwordEnv"] = "MF_MISSING_PASSWORD"
                os.environ.pop("MF_MISSING_PASSWORD", None)
                repository, managed, objects, revision = self._open(
                    root / "missing", document=missing_document
                )
                try:
                    with patch(
                        "mediaflow.application.configuration_objects.create_storage_from_definition",
                        side_effect=AssertionError("adapter construction reached"),
                    ):
                        evidence = self._check(objects, revision, "smb-check")
                    self.assertEqual(evidence.failure_category, "missing_secret")
                    self.assertEqual(evidence.operations, ())
                    self.assertEqual(evidence.attempted_operations, ())
                    self.assertNotIn("MF_MISSING_PASSWORD", evidence.message or "")
                    self.assertTrue(evidence.document()["retrySafe"])
                finally:
                    repository.close()

    def test_stale_revision_secret_readiness_disabled_and_active_are_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "local").mkdir()
            with patch.dict(os.environ, self._environment(), clear=False):
                adapter = FakeStorage("smb-check")
                repository, managed, objects, revision = self._open(
                    root / "stale",
                    adapters={"smb-check": adapter},
                )
                try:
                    self._check(objects, revision, "smb-check")
                    edited_document = json.loads(json.dumps(revision.document))
                    edited_document["storages"][1]["name"] = "edited"
                    edited = managed.edit_draft(
                        revision.revision_id,
                        edited_document,
                        expected_version=revision.version,
                        actor="operator",
                    )
                    detail = objects.revision_detail(edited.revision_id)
                    evidence = detail["storageChecks"][0]
                    self.assertTrue(evidence["stale"])
                    self.assertEqual(evidence["staleReason"], "revision_changed")
                    with self.assertRaises(ConfigurationVersionConflict):
                        objects.storage_check(
                            edited.revision_id,
                            storage_id="smb-check",
                            expected_version=revision.version,
                            expected_digest=revision.digest,
                            actor="operator",
                        )

                    self._check(objects, edited, "smb-check")
                    os.environ.pop("MF_CHECK_SMB_PASSWORD", None)
                    readiness_detail = objects.revision_detail(edited.revision_id)
                    stale = next(
                        item
                        for item in readiness_detail["storageChecks"]
                        if item["storageId"] == "smb-check"
                    )
                    self.assertEqual(stale["staleReason"], "secret_readiness_changed")

                    disabled_document = json.loads(json.dumps(edited.document))
                    disabled_document["storages"][1]["enabled"] = False
                    disabled = managed.edit_draft(
                        edited.revision_id,
                        disabled_document,
                        expected_version=edited.version,
                        actor="operator",
                    )
                    disabled_check = self._check(objects, disabled, "smb-check")
                    self.assertEqual(disabled_check.failure_category, "disabled")
                    disabled_projection = objects.storage_check_evidence(
                        disabled.revision_id, "smb-check"
                    )
                    self.assertFalse(disabled_projection["current"])
                    self.assertEqual(disabled_projection["staleReason"], "storage_disabled")
                finally:
                    repository.close()

                os.environ["MF_CHECK_SMB_PASSWORD"] = "unit-password"
                active_document = example_document()
                active_document["persistence"]["databasePath"] = str(
                    root / "active" / "configuration.sqlite3"
                )
                active_document["storages"][0]["rootPath"] = str(root / "active" / "source")
                active_document["storages"][1]["rootPath"] = str(root / "active" / "target")
                active_document["storages"].append(self._document(root)["storages"][1])
                active_repository, active_managed, active_objects, active_draft = self._open(
                    root / "active",
                    document=active_document,
                )
                try:
                    validated = active_managed.validate(active_draft.revision_id, actor="operator")
                    active = active_managed.activate(
                        validated.revision_id,
                        expected_version=validated.version,
                        actor="operator",
                    )
                    replacement = active_managed.import_draft(
                        active.document,
                        actor="operator",
                    )
                    failing = FakeStorage(
                        "smb-check",
                        error=StorageError(
                            StorageErrorCode.PERMISSION_DENIED,
                            "list",
                            "root",
                            "denied",
                        ),
                    )
                    replacement_objects = ConfigurationObjectService(
                        active_managed,
                        storage_adapters={"smb-check": failing},
                    )
                    result = self._check(replacement_objects, replacement, "smb-check")
                    self.assertEqual(result.failure_category, "permission_denied")
                    self.assertEqual(active_managed.active().revision_id, active.revision_id)
                    self.assertEqual(
                        active_managed.require(active.revision_id).status.value, "active"
                    )
                finally:
                    active_repository.close()

    def test_api_web_rbac_parity_audit_and_no_runtime_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "local").mkdir()
            repository, managed, objects, revision = self._open(
                root,
                adapters={"smb-check": FakeStorage("smb-check")},
            )
            runtime_path = root / "runtime.sqlite3"
            with SQLiteTaskRepository(runtime_path) as runtime_repository:
                admin = ResolvedApiPrincipal(
                    "admin",
                    "admin-token",
                    frozenset(ApiPermission),
                )
                viewer = ResolvedApiPrincipal(
                    "viewer",
                    "viewer-token",
                    frozenset({ApiPermission.READ}),
                )
                api = MediaFlowApi(
                    runtime_repository,
                    None,
                    principals=(admin, viewer),
                    configuration_service=managed,
                    storage_adapters={"smb-check": FakeStorage("smb-check")},
                    management_only=True,
                )
                try:
                    status, result = request(
                        api,
                        f"/api/v1/configuration/revisions/{revision.revision_id}/storage-check",
                        method="POST",
                        body={
                            "storageId": "smb-check",
                            "expectedVersion": revision.version,
                            "expectedDigest": revision.digest,
                        },
                    )
                    self.assertEqual(status, 200)
                    self.assertTrue(result["current"])
                    self.assertEqual(result["storageId"], "smb-check")
                    status, collection = request(
                        api,
                        f"/api/v1/configuration/revisions/{revision.revision_id}/storage-checks",
                        token="viewer-token",
                    )
                    self.assertEqual(status, 200)
                    self.assertEqual(collection["total"], 1)
                    status, denied = request(
                        api,
                        f"/api/v1/configuration/revisions/{revision.revision_id}/storage-check",
                        method="POST",
                        body={
                            "storageId": "smb-check",
                            "expectedVersion": revision.version,
                            "expectedDigest": revision.digest,
                        },
                        token="viewer-token",
                    )
                    self.assertEqual(status, 403)
                    self.assertEqual(denied["error"]["code"], "forbidden")
                    status, detail = request(
                        api,
                        f"/api/v1/configuration/revisions/{revision.revision_id}/storage-checks/smb-check",
                        token="viewer-token",
                    )
                    self.assertEqual(status, 200)
                    self.assertEqual(detail["storageCheck"]["storageId"], "smb-check")
                    connection = sqlite3.connect(runtime_path)
                    try:
                        self.assertEqual(
                            connection.execute("SELECT COUNT(*) FROM automation_jobs").fetchone()[
                                0
                            ],
                            0,
                        )
                        self.assertGreater(
                            connection.execute("SELECT COUNT(*) FROM security_audit").fetchone()[0],
                            0,
                        )
                    finally:
                        connection.close()
                finally:
                    objects._setup_check_executor.shutdown(wait=True)
            repository.close()

            self.assertIn("storage-check", APP_JS.decode("utf-8"))
            self.assertIn("Declared capabilities", APP_JS.decode("utf-8"))
            self.assertIn("Run read-only Storage check", APP_JS.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
