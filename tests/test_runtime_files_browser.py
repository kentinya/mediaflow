from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.domain.file_index import FileIndexRecord
from mediaflow.domain.scanner import FileChange, FileScanStatus
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.storage import (
    StorageCapabilities,
    StorageEntry,
    StorageEntryType,
    StoragePage,
)
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import APP_JS, INDEX_HTML
from mediaflow.interfaces.service_api import MediaFlowApi

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)


class _PagedStorage:
    """Provider-neutral fake used to exercise the runtime route for each adapter kind."""

    def __init__(self) -> None:
        self.storage_id = "storage"
        self.name = "Runtime fake Storage"
        self.read_only = False
        self.capabilities = StorageCapabilities()
        self._entry = StorageEntry(
            "fake.mkv",
            "fake.mkv",
            StorageEntryType.FILE,
            7,
            NOW,
        )

    def list(self, path: str):
        return (self._entry,) if not path else ()

    def list_page(self, path: str, *, limit: int, cursor: str | None = None) -> StoragePage:
        if path or cursor:
            return StoragePage(())
        return StoragePage((self._entry,))

    def stat(self, path: str) -> StorageEntry:
        if not path:
            return StorageEntry("", "", StorageEntryType.DIRECTORY, 0, NOW)
        if path == self._entry.path:
            return self._entry
        raise FileNotFoundError(path)

    def exists(self, path: str) -> bool:
        return not path or path == self._entry.path

    def read(self, path: str):
        return io.BytesIO(b"")

    def write(self, *args, **kwargs):
        raise AssertionError("runtime Files browser must not write")

    def create_directory(self, path: str) -> None:
        raise AssertionError("runtime Files browser must not create directories")

    def move(self, *args, **kwargs):
        raise AssertionError("runtime Files browser must not move")

    def copy(self, *args, **kwargs):
        raise AssertionError("runtime Files browser must not copy")

    def delete(self, path: str) -> None:
        raise AssertionError("runtime Files browser must not delete")

    def hard_link(self, *args, **kwargs):
        raise AssertionError("runtime Files browser must not link")

    def soft_link(self, *args, **kwargs):
        raise AssertionError("runtime Files browser must not link")


class _PermissionDeniedStorage(_PagedStorage):
    def list_page(self, path: str, *, limit: int, cursor: str | None = None) -> StoragePage:
        raise PermissionError(path)

    def stat(self, path: str) -> StorageEntry:
        raise PermissionError(path)


def _document(root: Path, database: Path) -> dict[str, object]:
    document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
    document["persistence"]["databasePath"] = str(database)
    document["storages"] = [
        {
            "id": "storage",
            "name": "Runtime Storage",
            "type": "local",
            "rootPath": str(root),
            "readOnly": False,
            "enabled": True,
        }
    ]
    document["resourceLibraries"] = [
        {
            "id": "resources",
            "name": "Runtime Resources",
            "storageId": "storage",
            "storagePath": "",
            "enabled": True,
        }
    ]
    document["mediaLibraries"] = [
        {
            "id": "movies",
            "name": "Runtime Movies",
            "storageId": "storage",
            "rootPath": "Movies",
            "enabled": True,
        },
        {
            "id": "tv",
            "name": "Runtime TV",
            "storageId": "storage",
            "rootPath": "TV",
            "enabled": True,
        },
    ]
    return document


def _record(file_id: str, path: str) -> FileIndexRecord:
    return FileIndexRecord(
        file_id=file_id,
        storage_id="storage",
        resource_library_id="resources",
        path=path,
        filename=Path(path).name,
        extension=Path(path).suffix.lstrip("."),
        size=17,
        modified_at=NOW - timedelta(hours=2),
        first_seen_at=NOW - timedelta(days=2),
        last_seen_at=NOW - timedelta(hours=1),
        stable_since=NOW - timedelta(hours=1),
        scan_status=FileScanStatus.READY,
        change=FileChange.UNCHANGED,
        created_at=NOW - timedelta(days=2),
        updated_at=NOW,
    )


def _activate(service: ManagedConfigurationService, document: dict[str, object]):
    draft = service.import_draft(document, actor="tester")
    validated = service.validate(draft.revision_id, actor="tester")
    if validated.status.value != "validated":
        raise AssertionError(validated.validation_errors)
    return service.activate(
        validated.revision_id,
        expected_version=validated.version,
        actor="tester",
    )


def _request(api: MediaFlowApi, url: str, *, token: str | None = "viewer-token"):
    split = urlsplit(url)
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": split.path,
        "QUERY_STRING": split.query,
        "CONTENT_LENGTH": "0",
        "wsgi.input": io.BytesIO(),
        "REMOTE_ADDR": "127.0.0.1",
    }
    if token is not None:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    body = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(body)


def _api(
    task_repository: SQLiteTaskRepository,
    file_index: SQLiteFileIndexRepository,
    managed: ManagedConfigurationService,
    document: dict[str, object],
    *,
    storage_adapters: dict[str, object] | None = None,
) -> MediaFlowApi:
    catalog = FileCatalogService(
        file_index,
        ("resources",),
        ("storage",),
        task_repository=task_repository,
    )
    return MediaFlowApi(
        task_repository,
        None,
        principals=(
            ResolvedApiPrincipal(
                "viewer",
                "viewer-token",
                frozenset({ApiPermission.READ}),
            ),
        ),
        configuration_service=managed,
        file_catalog=catalog,
        file_index=file_index,
        bootstrap_document=document,
        storage_adapters=storage_adapters,
        storage_browser_cursor_secret="runtime-files-test-secret",
    )


class RuntimeFilesBrowserApiTests(unittest.TestCase):
    def test_runtime_files_reuses_the_application_contract_for_supported_storage_kinds(
        self,
    ) -> None:
        kinds = ("local", "smb", "openlist", "s3", "r2", "s3-compatible")
        environment = {
            "RUNTIME_FILES_SMB_USER": "user",
            "RUNTIME_FILES_SMB_PASSWORD": "password",
            "RUNTIME_FILES_OPENLIST_TOKEN": "token",
            "RUNTIME_FILES_S3_ACCESS": "access",
            "RUNTIME_FILES_S3_SECRET": "secret",
            "RUNTIME_FILES_R2_ACCESS": "access",
            "RUNTIME_FILES_R2_SECRET": "secret",
            "RUNTIME_FILES_COMPAT_ACCESS": "access",
            "RUNTIME_FILES_COMPAT_SECRET": "secret",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for kind in kinds:
                with self.subTest(kind=kind):
                    database = root / f"{kind}.sqlite3"
                    document = _document(root, database)
                    storage = document["storages"][0]
                    storage["type"] = kind
                    storage["rootPath"] = str(root) if kind == "local" else "provider-root"
                    if kind == "smb":
                        storage["options"] = {
                            "usernameEnv": "RUNTIME_FILES_SMB_USER",
                            "passwordEnv": "RUNTIME_FILES_SMB_PASSWORD",
                            "host": "nas.example.invalid",
                            "share": "media",
                        }
                    elif kind == "openlist":
                        storage["rootPath"] = "/Media"
                        storage["options"] = {
                            "tokenEnv": "RUNTIME_FILES_OPENLIST_TOKEN",
                            "baseUrl": "https://openlist.example.invalid",
                        }
                    elif kind in {"s3", "r2", "s3-compatible"}:
                        prefix = {
                            "s3": "RUNTIME_FILES_S3",
                            "r2": "RUNTIME_FILES_R2",
                            "s3-compatible": "RUNTIME_FILES_COMPAT",
                        }[kind]
                        storage["options"] = {
                            "accessKeyEnv": f"{prefix}_ACCESS",
                            "secretKeyEnv": f"{prefix}_SECRET",
                            "bucket": "runtime-files",
                        }
                        if kind != "s3":
                            storage["options"]["endpoint"] = "https://storage.example.invalid"
                    with patch.dict(os.environ, environment):
                        with (
                            SQLiteConfigurationRepository(database) as configuration_repository,
                            SQLiteTaskRepository(database) as task_repository,
                            SQLiteFileIndexRepository(database) as file_index,
                        ):
                            managed = ManagedConfigurationService(
                                configuration_repository,
                                bootstrap_database_path=str(database),
                            )
                            _activate(managed, document)
                            api = _api(
                                task_repository,
                                file_index,
                                managed,
                                document,
                                storage_adapters={"storage": _PagedStorage()},
                            )
                            status, result = _request(
                                api,
                                "/api/v1/storage/files?storageId=storage",
                            )
                            self.assertEqual(status, 200)
                            self.assertEqual(result["surface"], "files")
                            self.assertEqual(result["entries"][0]["name"], "fake.mkv")

    def test_files_is_active_storage_and_file_index_is_a_separate_surface(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            (first / "active-only.mkv").write_bytes(b"active")
            (second / "draft-only.mkv").write_bytes(b"draft")
            database = root / "runtime.sqlite3"
            document = _document(first, database)
            with (
                SQLiteConfigurationRepository(database) as configuration_repository,
                SQLiteTaskRepository(database) as task_repository,
                SQLiteFileIndexRepository(database) as file_index,
            ):
                managed = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(database),
                )
                active = _activate(managed, document)
                file_index.batch_upsert((_record("indexed-active", "active-only.mkv"),))
                api = _api(task_repository, file_index, managed, document)

                status, files = _request(api, "/api/v1/storage/files?storageId=storage")
                self.assertEqual(status, 200)
                self.assertEqual(files["surface"], "files")
                self.assertEqual(files["fileIndexSurface"], "/api/v1/file-index")
                self.assertEqual(files["configuration"]["authority"], "MANAGED")
                self.assertEqual(files["configuration"]["revisionId"], active.revision_id)
                self.assertEqual([item["name"] for item in files["entries"]], ["active-only.mkv"])
                self.assertEqual(
                    files["entries"][0]["indexMembership"]["memberships"][0]["fileId"],
                    "indexed-active",
                )
                self.assertNotIn("processingDisposition", files["entries"][0]["indexMembership"])
                self.assertNotIn("currentOccurrence", files["entries"][0]["indexMembership"])
                self.assertNotIn("organizationOutcome", files["entries"][0]["indexMembership"])

                status, file_index_document = _request(api, "/api/v1/file-index")
                self.assertEqual(status, 200)
                self.assertEqual(file_index_document["surface"], "file_index")
                self.assertEqual(file_index_document["filesSurface"], "/api/v1/storage/files")
                self.assertEqual(file_index_document["items"][0]["fileId"], "indexed-active")
                self.assertEqual(task_repository.list_tasks(), ())
                self.assertEqual(task_repository.list_jobs(), ())

                draft_document = json.loads(json.dumps(document))
                draft_document["storages"][0]["rootPath"] = str(second)
                _draft = managed.import_draft(draft_document, actor="tester")
                status, files = _request(api, "/api/v1/storage/files?storageId=storage")
                self.assertEqual(status, 200)
                self.assertEqual([item["name"] for item in files["entries"]], ["active-only.mkv"])

                active_second = _activate(managed, draft_document)
                status, files = _request(api, "/api/v1/storage/files?storageId=storage")
                self.assertEqual(status, 200)
                self.assertEqual(files["configuration"]["revisionId"], active_second.revision_id)
                self.assertEqual([item["name"] for item in files["entries"]], ["draft-only.mkv"])

    def test_files_preserves_read_only_paging_path_and_rbac_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nested").mkdir(parents=True)
            (root / "empty").mkdir()
            (root / "a.mkv").write_bytes(b"a")
            (root / "nested" / "b.mkv").write_bytes(b"b")
            database = root / "runtime.sqlite3"
            document = _document(root, database)
            original = (root / "nested" / "b.mkv").read_bytes()
            with (
                SQLiteConfigurationRepository(database) as configuration_repository,
                SQLiteTaskRepository(database) as task_repository,
                SQLiteFileIndexRepository(database) as file_index,
            ):
                managed = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(database),
                )
                _activate(managed, document)
                api = _api(task_repository, file_index, managed, document)

                status, first_page = _request(
                    api,
                    "/api/v1/storage/files?storageId=storage&limit=1",
                )
                self.assertEqual(status, 200)
                self.assertEqual(first_page["sideEffects"], "none")
                self.assertTrue(first_page["nextCursor"])
                status, second_page = _request(
                    api,
                    "/api/v1/storage/files?storageId=storage&limit=1&cursor="
                    + first_page["nextCursor"],
                )
                self.assertEqual(status, 200)
                self.assertNotEqual(
                    first_page["entries"][0]["name"], second_page["entries"][0]["name"]
                )
                status, error = _request(
                    api,
                    "/api/v1/storage/files?storageId=storage&resourceLibrary=resources"
                    "&limit=1&cursor=" + first_page["nextCursor"],
                )
                self.assertEqual(status, 400)
                self.assertEqual(error["error"]["code"], "storage_browser_cursor_invalid")

                status, nested = _request(
                    api,
                    "/api/v1/storage/files?storageId=storage&path=nested",
                )
                self.assertEqual(status, 200)
                self.assertEqual(nested["breadcrumbs"][-1]["path"], "nested")
                self.assertEqual(nested["entries"][0]["name"], "b.mkv")
                self.assertEqual((root / "nested" / "b.mkv").read_bytes(), original)
                status, empty = _request(
                    api,
                    "/api/v1/storage/files?storageId=storage&path=empty",
                )
                self.assertEqual(status, 200)
                self.assertEqual(empty["entries"], [])
                self.assertTrue(empty["exhausted"])

                status, error = _request(
                    api,
                    "/api/v1/storage/files?storageId=storage&path=../outside",
                )
                self.assertEqual(status, 400)
                self.assertEqual(error["error"]["code"], "storage_browser_invalid_path")
                status, error = _request(api, "/api/v1/storage/files?storageId=storage", token=None)
                self.assertEqual(status, 401)
                self.assertEqual(error["error"]["code"], "unauthorized")

                status, error = _request(
                    api,
                    "/api/v1/storage/files?storageId=storage&resourceLibrary=missing",
                )
                self.assertEqual(status, 404)
                self.assertEqual(
                    error["error"]["code"], "storage_browser_resource_library_not_found"
                )

    def test_provider_read_failures_keep_the_active_runtime_and_storage_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "runtime.sqlite3"
            document = _document(root, database)
            with (
                SQLiteConfigurationRepository(database) as configuration_repository,
                SQLiteTaskRepository(database) as task_repository,
                SQLiteFileIndexRepository(database) as file_index,
            ):
                managed = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(database),
                )
                active = _activate(managed, document)
                api = _api(
                    task_repository,
                    file_index,
                    managed,
                    document,
                    storage_adapters={"storage": _PermissionDeniedStorage()},
                )
                status, error = _request(api, "/api/v1/storage/files?storageId=storage")
                self.assertEqual(status, 403)
                details = error["error"]["details"]
                self.assertEqual(details["category"], "permission_denied")
                self.assertEqual(details["durableState"], "active_runtime_preserved")
                self.assertEqual(details["sideEffects"], "none")
                self.assertEqual(details["storageId"], "storage")
                self.assertEqual(active.revision_id, managed.active().revision_id)

    def test_files_fails_closed_without_an_active_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.mkdir(exist_ok=True)
            database = root / "runtime.sqlite3"
            document = _document(root, database)
            with (
                SQLiteConfigurationRepository(database) as configuration_repository,
                SQLiteTaskRepository(database) as task_repository,
                SQLiteFileIndexRepository(database) as file_index,
            ):
                managed = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(database),
                )
                api = _api(task_repository, file_index, managed, document)
                status, error = _request(api, "/api/v1/storage/files?storageId=storage")
                self.assertEqual(status, 503)
                self.assertEqual(error["error"]["code"], "configuration_unavailable")
                self.assertEqual(error["error"]["details"]["authority"], "MANAGED")
                self.assertEqual(error["error"]["details"]["sideEffects"], "none")


class RuntimeFilesBrowserUiTests(unittest.TestCase):
    def test_files_and_file_index_have_distinct_operator_entry_points(self) -> None:
        html = INDEX_HTML.decode("utf-8")
        script = APP_JS.decode("utf-8")
        self.assertIn('data-view="files"', html)
        self.assertIn('data-view="file-index"', html)
        self.assertIn("/api/v1/storage/files?", script)
        self.assertIn("/api/v1/file-index?", script)
        self.assertIn("indexMembership", script)
        self.assertIn("Storage root", script)
        self.assertIn("Retry page", script)
        self.assertIn("FileIndex is not a configured Storage browser", script)


if __name__ == "__main__":
    unittest.main()
