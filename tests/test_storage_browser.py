from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode, urlsplit

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.storage_browser import StorageBrowserError, StorageBrowserService
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.storage import (
    StorageCapabilities,
    StorageEntry,
    StorageEntryType,
    StorageError,
    StorageErrorCode,
    StoragePage,
)
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import APP_JS
from mediaflow.interfaces.service_api import MediaFlowApi


class PagedStorage:
    def __init__(self, storage_id: str = "storage") -> None:
        now = datetime.now(UTC)
        self.storage_id = storage_id
        self.name = "Paged storage"
        self.read_only = False
        self.capabilities = StorageCapabilities()
        self.entries = tuple(
            StorageEntry(
                name,
                name,
                StorageEntryType.DIRECTORY if name.startswith("dir-") else StorageEntryType.FILE,
                index,
                now,
            )
            for index, name in enumerate(("alpha.mkv", "dir-one", "dir-two", "omega.srt"), 1)
        )
        self.list_page_calls: list[tuple[str, int, str | None]] = []
        self.stat_calls: list[str] = []

    def list(self, path: str):
        return self.entries if not path else ()

    def list_page(self, path: str, *, limit: int, cursor: str | None = None) -> StoragePage:
        self.list_page_calls.append((path, limit, cursor))
        values = tuple(item for item in self.entries if cursor is None or item.name > cursor)
        selected = values[:limit]
        return StoragePage(selected, selected[-1].name if len(values) > limit else None)

    def stat(self, path: str) -> StorageEntry:
        self.stat_calls.append(path)
        if not path:
            return StorageEntry("", "", StorageEntryType.DIRECTORY, 0, datetime.now(UTC))
        entry = next((item for item in self.entries if item.path == path), None)
        if entry is None:
            raise FileNotFoundError(path)
        return entry

    def exists(self, path: str) -> bool:
        return not path or any(item.path == path for item in self.entries)

    def read(self, path: str):
        return io.BytesIO(b"")

    def write(self, *args, **kwargs):
        raise AssertionError("browser must not write")

    def create_directory(self, path: str) -> None:
        raise AssertionError("browser must not create directories")

    def move(self, *args, **kwargs):
        raise AssertionError("browser must not move")

    def copy(self, *args, **kwargs):
        raise AssertionError("browser must not copy")

    def delete(self, path: str) -> None:
        raise AssertionError("browser must not delete")

    def hard_link(self, *args, **kwargs):
        raise AssertionError("browser must not link")

    def soft_link(self, *args, **kwargs):
        raise AssertionError("browser must not link")


def _document(root: Path) -> dict[str, object]:
    value = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
    value["persistence"]["databasePath"] = str(root / "configuration.sqlite3")
    value["storages"] = [
        {
            "id": "storage",
            "name": "Setup storage",
            "type": "local",
            "rootPath": str(root / "media"),
            "readOnly": False,
            "enabled": True,
        }
    ]
    value["resourceLibraries"] = [
        {
            "id": "resources",
            "name": "Resources",
            "storageId": "storage",
            "storagePath": "",
            "enabled": True,
        }
    ]
    value["mediaLibraries"] = [
        {
            "id": "movies",
            "name": "Movies",
            "storageId": "storage",
            "rootPath": "",
            "enabled": True,
        }
    ]
    return value


def _request(api, url: str, *, method: str = "GET", body=None, token: str = "admin-token"):
    split = urlsplit(url)
    payload = b"" if body is None else json.dumps(body).encode("utf-8")
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": split.path,
        "QUERY_STRING": split.query,
        "CONTENT_LENGTH": str(len(payload)),
        "wsgi.input": io.BytesIO(payload),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
    }
    result = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(result)


class StorageBrowserApplicationTests(unittest.TestCase):
    def test_all_supported_storage_kinds_use_the_same_application_browser(self) -> None:
        kinds = ("local", "smb", "openlist", "s3", "r2", "s3-compatible")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "media").mkdir()
            env = {
                "BROWSER_SMB_USER": "user",
                "BROWSER_SMB_PASSWORD": "password",
                "BROWSER_OPENLIST_TOKEN": "token",
                "BROWSER_S3_ACCESS": "access",
                "BROWSER_S3_SECRET": "secret",
                "BROWSER_R2_ACCESS": "access",
                "BROWSER_R2_SECRET": "secret",
                "BROWSER_COMPAT_ACCESS": "access",
                "BROWSER_COMPAT_SECRET": "secret",
            }
            with patch.dict(os.environ, env):
                for kind in kinds:
                    with (
                        self.subTest(kind=kind),
                        SQLiteConfigurationRepository(root / f"{kind}.sqlite3") as repository,
                    ):
                        document = _document(root)
                        storage = document["storages"][0]
                        storage["type"] = kind
                        storage["rootPath"] = (
                            str(root / "media") if kind == "local" else "provider-root"
                        )
                        if kind == "smb":
                            storage["options"] = {
                                "usernameEnv": "BROWSER_SMB_USER",
                                "passwordEnv": "BROWSER_SMB_PASSWORD",
                                "host": "nas.example.invalid",
                                "share": "media",
                            }
                        elif kind == "openlist":
                            storage["rootPath"] = "/Media"
                            storage["options"] = {
                                "tokenEnv": "BROWSER_OPENLIST_TOKEN",
                                "baseUrl": "https://openlist.example.invalid",
                            }
                        elif kind in {"s3", "r2", "s3-compatible"}:
                            prefix = {
                                "s3": "BROWSER_S3",
                                "r2": "BROWSER_R2",
                                "s3-compatible": "BROWSER_COMPAT",
                            }[kind]
                            storage["options"] = {
                                "accessKeyEnv": f"{prefix}_ACCESS",
                                "secretKeyEnv": f"{prefix}_SECRET",
                                "bucket": "media-bucket",
                                "endpoint": (
                                    "https://storage.example.invalid" if kind != "s3" else None
                                ),
                            }
                            if kind == "s3":
                                storage["options"].pop("endpoint")
                        managed = ManagedConfigurationService(
                            repository,
                            bootstrap_document={
                                "persistence": {"databasePath": str(root / "configuration.sqlite3")}
                            },
                            management_only=True,
                        )
                        draft = managed.import_draft(document, actor="admin")
                        result = ConfigurationObjectService(
                            managed,
                            storage_adapters={"storage": PagedStorage()},
                            storage_browser_cursor_secret="browser-test-secret",
                        ).browse_storage(draft.revision_id, storage_id="storage", limit=2)
                        self.assertEqual(result["storageType"], kind)
                        self.assertEqual(result["path"], "")

    def test_local_browse_is_bounded_sorted_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / "media"
            media.mkdir()
            (media / "zeta.mkv").write_bytes(b"z")
            (media / "alpha.mkv").write_bytes(b"a")
            (media / "directory").mkdir()
            (media / "directory" / "nested.mkv").write_bytes(b"n")
            document = _document(root)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(
                    repository,
                    bootstrap_document={
                        "persistence": {"databasePath": str(root / "configuration.sqlite3")}
                    },
                    management_only=True,
                )
                draft = managed.import_draft(document, actor="admin")
                adapter = LocalStorage("storage", media)
                objects = ConfigurationObjectService(
                    managed,
                    storage_adapters={"storage": adapter},
                    storage_browser_cursor_secret="browser-test-secret",
                )
                first = objects.browse_storage(
                    draft.revision_id,
                    storage_id="storage",
                    limit=2,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                )
                self.assertEqual(
                    [entry["name"] for entry in first["entries"]], ["alpha.mkv", "directory"]
                )
                self.assertTrue(first["hasNext"])
                self.assertEqual(first["pathScope"], "storage_relative")
                self.assertEqual(first["sideEffects"], "none")
                second = objects.browse_storage(
                    draft.revision_id,
                    storage_id="storage",
                    limit=2,
                    cursor=first["nextCursor"],
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                )
                self.assertEqual([entry["name"] for entry in second["entries"]], ["zeta.mkv"])
                self.assertFalse(second["hasNext"])
                self.assertFalse((media / "zeta.mkv").stat().st_size == 0)

    def test_nested_empty_directory_and_hostile_name_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / "media"
            media.mkdir()
            (media / "empty").mkdir()
            hostile = "<img src=x onerror=1>.mkv"
            (media / hostile).write_bytes(b"safe")
            document = _document(root)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(
                    repository,
                    bootstrap_document={
                        "persistence": {"databasePath": str(root / "configuration.sqlite3")}
                    },
                    management_only=True,
                )
                draft = managed.import_draft(document, actor="admin")
                objects = ConfigurationObjectService(
                    managed,
                    storage_adapters={"storage": LocalStorage("storage", media)},
                    storage_browser_cursor_secret="browser-test-secret",
                )
                page = objects.browse_storage(draft.revision_id, storage_id="storage", limit=100)
                hostile_entry = next(entry for entry in page["entries"] if entry["name"] == hostile)
                self.assertEqual(hostile_entry["path"], hostile)
                empty = objects.browse_storage(
                    draft.revision_id, storage_id="storage", path="empty", limit=100
                )
                self.assertEqual(empty["entries"], [])
                self.assertTrue(empty["exhausted"])
                self.assertFalse(empty["hasNext"])

    def test_cursor_is_opaque_and_bound_to_path_and_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / "media"
            media.mkdir()
            document = _document(root)
            document["storages"].append(
                {
                    "id": "other",
                    "name": "Other storage",
                    "type": "local",
                    "rootPath": str(root / "media"),
                    "readOnly": False,
                    "enabled": True,
                }
            )
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(
                    repository,
                    bootstrap_document={
                        "persistence": {"databasePath": str(root / "configuration.sqlite3")}
                    },
                    management_only=True,
                )
                draft = managed.import_draft(document, actor="admin")
                adapter = PagedStorage()
                other_adapter = PagedStorage("other")
                objects = ConfigurationObjectService(
                    managed,
                    storage_adapters={"storage": adapter, "other": other_adapter},
                    storage_browser_cursor_secret="browser-test-secret",
                )
                first = objects.browse_storage(
                    draft.revision_id,
                    storage_id="storage",
                    limit=1,
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                )
                cursor = first["nextCursor"]
                self.assertNotIn("provider-secret", cursor)
                with self.assertRaisesRegex(StorageBrowserError, "continuation"):
                    objects.browse_storage(
                        draft.revision_id,
                        storage_id="storage",
                        path="dir-one",
                        limit=1,
                        cursor=cursor,
                        expected_version=draft.version,
                        expected_digest=draft.digest,
                    )
                before = len(adapter.list_page_calls)
                with self.assertRaises(StorageBrowserError):
                    objects.browse_storage(
                        draft.revision_id,
                        storage_id="storage",
                        limit=1,
                        cursor="not-a-cursor",
                        expected_version=draft.version,
                        expected_digest=draft.digest,
                    )
                self.assertEqual(len(adapter.list_page_calls), before)
                before_other = len(other_adapter.list_page_calls)
                with self.assertRaisesRegex(StorageBrowserError, "continuation"):
                    objects.browse_storage(
                        draft.revision_id,
                        storage_id="other",
                        limit=1,
                        cursor=cursor,
                    )
                self.assertEqual(len(other_adapter.list_page_calls), before_other)
                current = managed.require(draft.revision_id)
                objects.select_storage_directory(
                    draft.revision_id,
                    storage_id="storage",
                    path="",
                    target="resourceLibrary",
                    library_id="resources",
                    field="storagePath",
                    expected_version=current.version,
                    expected_digest=current.digest,
                    actor="admin",
                )
                before_revision = len(adapter.list_page_calls)
                with self.assertRaisesRegex(StorageBrowserError, "continuation"):
                    objects.browse_storage(
                        draft.revision_id,
                        storage_id="storage",
                        limit=1,
                        cursor=cursor,
                    )
                self.assertEqual(len(adapter.list_page_calls), before_revision)
                with self.assertRaises(ValueError):
                    objects.browse_storage(draft.revision_id, storage_id="storage", limit=101)
                self.assertEqual(len(adapter.list_page_calls), before_revision)

    def test_expired_cursor_is_rejected_before_provider_contact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "media").mkdir()
            document = _document(root)
            now = [1000.0]
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(
                    repository,
                    bootstrap_document={
                        "persistence": {"databasePath": str(root / "configuration.sqlite3")}
                    },
                    management_only=True,
                )
                draft = managed.import_draft(document, actor="admin")
                adapter = PagedStorage()
                browser = StorageBrowserService(
                    managed,
                    storage_adapters={"storage": adapter},
                    cursor_secret="browser-test-secret",
                    clock=lambda: now[0],
                )
                first = browser.browse(draft.revision_id, storage_id="storage", limit=1)
                now[0] += 601
                calls = len(adapter.list_page_calls)
                with self.assertRaisesRegex(StorageBrowserError, "expired"):
                    browser.browse(
                        draft.revision_id,
                        storage_id="storage",
                        limit=1,
                        cursor=first["nextCursor"],
                    )
                self.assertEqual(len(adapter.list_page_calls), calls)

    def test_provider_failures_are_stable_and_secret_free(self) -> None:
        class ErrorStorage(PagedStorage):
            def __init__(self, code: StorageErrorCode) -> None:
                super().__init__()
                self.code = code

            def list_page(self, path: str, *, limit: int, cursor: str | None = None):
                raise StorageError(
                    self.code,
                    "list_page",
                    "/private/provider-secret",
                    "raw provider payload provider-secret",
                )

        cases = {
            StorageErrorCode.PERMISSION_DENIED: "permission_denied",
            StorageErrorCode.AUTHENTICATION_FAILED: "authentication_failed",
            StorageErrorCode.TIMEOUT: "timeout",
            StorageErrorCode.CONNECTION_FAILED: "connection_failed",
            StorageErrorCode.NOT_FOUND: "not_found",
            StorageErrorCode.INVALID_PATH: "invalid_path",
            StorageErrorCode.IO_ERROR: "connection_failed",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "media").mkdir()
            document = _document(root)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(
                    repository,
                    bootstrap_document={
                        "persistence": {"databasePath": str(root / "configuration.sqlite3")}
                    },
                    management_only=True,
                )
                draft = managed.import_draft(document, actor="admin")
                for code, category in cases.items():
                    with self.subTest(code=code):
                        browser = StorageBrowserService(
                            managed,
                            storage_adapters={"storage": ErrorStorage(code)},
                            cursor_secret="browser-test-secret",
                        )
                        with self.assertRaises(StorageBrowserError) as context:
                            browser.browse(draft.revision_id, storage_id="storage")
                        error = context.exception
                        self.assertEqual(error.category, category)
                        self.assertNotIn("provider-secret", str(error))
                        self.assertNotIn("/private", json.dumps(error.details))

                malformed = PagedStorage()
                malformed.entries = (
                    StorageEntry(
                        "bad",
                        "wrong/path",
                        StorageEntryType.FILE,
                        1,
                        datetime.now(UTC),
                    ),
                )
                browser = StorageBrowserService(
                    managed,
                    storage_adapters={"storage": malformed},
                    cursor_secret="browser-test-secret",
                )
                with self.assertRaisesRegex(StorageBrowserError, "invalid bounded"):
                    browser.browse(draft.revision_id, storage_id="storage")

    def test_invalid_paths_and_symlinks_are_rejected_before_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / "media"
            outside = root / "outside"
            media.mkdir()
            outside.mkdir()
            (outside / "secret.mkv").write_bytes(b"secret")
            (media / "real").mkdir()
            try:
                (media / "link").symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symbolic links are unavailable")
            document = _document(root)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(
                    repository,
                    bootstrap_document={
                        "persistence": {"databasePath": str(root / "configuration.sqlite3")}
                    },
                    management_only=True,
                )
                draft = managed.import_draft(document, actor="admin")
                adapter = LocalStorage("storage", media)
                objects = ConfigurationObjectService(
                    managed,
                    storage_adapters={"storage": adapter},
                    storage_browser_cursor_secret="browser-test-secret",
                )
                page = objects.browse_storage(draft.revision_id, storage_id="storage", limit=100)
                link = next(entry for entry in page["entries"] if entry["name"] == "link")
                self.assertEqual(link["type"], "symlink")
                self.assertFalse(link["traversable"])
                self.assertFalse(link["selectable"])
                for path in (
                    "/etc",
                    "../outside",
                    "real/../outside",
                    "C:/host",
                    "real\\child",
                    "real\x00x",
                ):
                    with self.subTest(path=path), self.assertRaises(StorageBrowserError):
                        objects.browse_storage(draft.revision_id, storage_id="storage", path=path)
                with self.assertRaisesRegex(StorageBrowserError, "symbolic-link"):
                    objects.browse_storage(draft.revision_id, storage_id="storage", path="link")
                with self.assertRaisesRegex(StorageBrowserError, "symbolic-link"):
                    objects.select_storage_directory(
                        draft.revision_id,
                        storage_id="storage",
                        path="link",
                        target="resourceLibrary",
                        library_id="resources",
                        field="storagePath",
                        expected_version=draft.version,
                        expected_digest=draft.digest,
                        actor="admin",
                    )

    def test_local_host_root_is_not_a_supported_browser_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "media").mkdir()
            document = _document(root)
            document["storages"][0]["rootPath"] = "/"
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(
                    repository,
                    bootstrap_document={
                        "persistence": {"databasePath": str(root / "configuration.sqlite3")}
                    },
                    management_only=True,
                )
                draft = managed.import_draft(document, actor="admin")
                adapter = PagedStorage()
                browser = StorageBrowserService(
                    managed,
                    storage_adapters={"storage": adapter},
                    cursor_secret="browser-test-secret",
                )
                with self.assertRaisesRegex(StorageBrowserError, "invalid"):
                    browser.browse(draft.revision_id, storage_id="storage")
                self.assertEqual(adapter.list_page_calls, [])

    def test_directory_selection_uses_existing_mutation_service(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / "media"
            media.mkdir()
            (media / "incoming").mkdir()
            document = _document(root)
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                managed = ManagedConfigurationService(
                    repository,
                    bootstrap_document={
                        "persistence": {"databasePath": str(root / "configuration.sqlite3")}
                    },
                    management_only=True,
                )
                draft = managed.import_draft(document, actor="admin")
                objects = ConfigurationObjectService(
                    managed,
                    storage_adapters={"storage": LocalStorage("storage", media)},
                    storage_browser_cursor_secret="browser-test-secret",
                )
                result = objects.select_storage_directory(
                    draft.revision_id,
                    storage_id="storage",
                    path="incoming",
                    target="resourceLibrary",
                    library_id="resources",
                    field="storagePath",
                    expected_version=draft.version,
                    expected_digest=draft.digest,
                    actor="admin",
                )
                self.assertEqual(result["selected"]["path"], "incoming")
                self.assertEqual(result["object"]["storagePath"], "incoming")
                self.assertEqual(result["revision"]["version"], draft.version + 1)
                self.assertEqual(managed.require(draft.revision_id).status.value, "draft")


class StorageBrowserApiTests(unittest.TestCase):
    def test_api_parity_rbac_and_safe_error_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / "media"
            media.mkdir()
            (media / "chosen").mkdir()
            document = _document(root)
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as config_repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as task_repository,
            ):
                managed = ManagedConfigurationService(
                    config_repository,
                    bootstrap_document={
                        "persistence": {"databasePath": str(root / "configuration.sqlite3")}
                    },
                    management_only=True,
                )
                draft = managed.import_draft(document, actor="admin")
                admin = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
                viewer = ResolvedApiPrincipal(
                    "viewer", "viewer-token", frozenset({ApiPermission.READ})
                )
                api = MediaFlowApi(
                    task_repository,
                    None,
                    principals=(admin, viewer),
                    configuration_service=managed,
                    bootstrap_document={
                        "persistence": {"databasePath": str(root / "configuration.sqlite3")}
                    },
                    management_only=True,
                    storage_adapters={"storage": LocalStorage("storage", media)},
                    storage_browser_cursor_secret="browser-test-secret",
                )
                query = urlencode(
                    {
                        "storageId": "storage",
                        "path": "",
                        "limit": 10,
                        "expectedVersion": draft.version,
                        "expectedDigest": draft.digest,
                    }
                )
                status, page = _request(
                    api,
                    f"/api/v1/configuration/revisions/{draft.revision_id}/storage-browser?{query}",
                    token="viewer-token",
                )
                self.assertEqual(status, 200)
                self.assertEqual(page["pathScope"], "storage_relative")
                selection = {
                    "storageId": "storage",
                    "path": "chosen",
                    "target": "resourceLibrary",
                    "libraryId": "resources",
                    "field": "storagePath",
                    "expectedVersion": draft.version,
                    "expectedDigest": draft.digest,
                }
                selection_url = (
                    f"/api/v1/configuration/revisions/{draft.revision_id}/storage-browser/select"
                )
                status, denied = _request(
                    api, selection_url, method="POST", body=selection, token="viewer-token"
                )
                self.assertEqual(status, 403)
                self.assertEqual(denied["error"]["code"], "forbidden")
                status, selected = _request(
                    api, selection_url, method="POST", body=selection, token="admin-token"
                )
                self.assertEqual(status, 200)
                self.assertEqual(selected["object"]["storagePath"], "chosen")
                status, failed = _request(
                    api,
                    f"/api/v1/configuration/revisions/{draft.revision_id}/storage-browser?"
                    + urlencode({"storageId": "storage", "path": "../secret"}),
                    token="viewer-token",
                )
                self.assertEqual(status, 400)
                self.assertEqual(failed["error"]["code"], "storage_browser_invalid_path")
                self.assertEqual(failed["error"]["details"]["sideEffects"], "none")
                self.assertNotIn("../secret", json.dumps(failed))


class StorageBrowserWebTests(unittest.TestCase):
    def test_setup_picker_and_execution_environment_guidance_are_present(self) -> None:
        script = APP_JS.decode("utf-8")
        self.assertIn("storage-browser", script)
        self.assertIn("renderStorageBrowserPicker", script)
        self.assertIn("Next page", script)
        self.assertIn("Retry page", script)
        self.assertIn("Storage-relative breadcrumb", script)
        self.assertIn("not the File Catalog", script)
        self.assertIn("bind-mount", script)
        self.assertIn("Docker socket", script)
        self.assertNotIn("innerHTML", script)


if __name__ == "__main__":
    unittest.main()
