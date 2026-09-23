from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
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
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)


class _CountingStorage:
    """Fake Storage adapter recording every call; every mutation is forbidden."""

    def __init__(self) -> None:
        self.storage_id = "storage"
        self.name = "Fake storage"
        self.read_only = False
        self.capabilities = StorageCapabilities()
        self.list_page_calls: list[tuple[str, int, str | None]] = []

    def list(self, path: str):
        return ()

    def list_page(self, path: str, *, limit: int, cursor: str | None = None) -> StoragePage:
        self.list_page_calls.append((path, limit, cursor))
        return StoragePage(())

    def stat(self, path: str) -> StorageEntry:
        return StorageEntry("", "", StorageEntryType.DIRECTORY, 0, NOW)

    def exists(self, path: str) -> bool:
        return True

    def read(self, path: str):
        return io.BytesIO(b"")

    def write(self, *args, **kwargs):
        raise AssertionError("media library browse must not write")

    def create_directory(self, path: str) -> None:
        raise AssertionError("media library browse must not create directories")

    def move(self, *args, **kwargs):
        raise AssertionError("media library browse must not move")

    def copy(self, *args, **kwargs):
        raise AssertionError("media library browse must not copy")

    def delete(self, path: str) -> None:
        raise AssertionError("media library browse must not delete")

    def hard_link(self, *args, **kwargs):
        raise AssertionError("media library browse must not link")

    def soft_link(self, *args, **kwargs):
        raise AssertionError("media library browse must not link")


def _document(root: Path, database: Path) -> dict[str, object]:
    document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
    document["persistence"]["databasePath"] = str(database)
    document["storages"] = [
        {
            "id": "storage",
            "name": "Fake Storage",
            "type": "local",
            "rootPath": str(root),
            "readOnly": False,
            "enabled": True,
        }
    ]
    document["resourceLibraries"] = [
        {
            "id": "shared",
            "name": "Shared ResourceLibrary",
            "storageId": "storage",
            "storagePath": "Movies",
            "enabled": True,
        }
    ]
    document["mediaLibraries"] = [
        {
            "id": "movies",
            "name": "Movies",
            "storageId": "storage",
            "rootPath": "Movies",
            "enabled": True,
        },
        {
            "id": "shared",
            "name": "Shared MediaLibrary",
            "storageId": "storage",
            "rootPath": "Movies",
            "enabled": True,
        },
        {
            "id": "tv",
            "name": "TV Library",
            "storageId": "storage",
            "rootPath": "TV",
            "enabled": True,
        },
        {
            "id": "tv shows",
            "name": "TV Shows",
            "storageId": "storage",
            "rootPath": "TV Shows",
            "enabled": True,
        },
        {
            "id": "off",
            "name": "Disabled Library",
            "storageId": "storage",
            "rootPath": "Disabled",
            "enabled": False,
        },
    ]
    return document


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


def _media_library_api(
    task_repository: SQLiteTaskRepository,
    managed: ManagedConfigurationService,
    document: dict[str, object],
    *,
    storage_adapters: dict[str, object] | None = None,
) -> MediaFlowApi:
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
        bootstrap_document=document,
        storage_adapters=storage_adapters,
        storage_browser_cursor_secret="media-library-test-secret",
    )


class MediaLibraryApiTests(unittest.TestCase):
    """Focused Slice 38 RO-3/RO-7 read-only MediaLibrary API coverage."""

    def test_list_and_browse_enabled_media_libraries_are_live_storage_reads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Movies").mkdir()
            (root / "Movies" / "Breaking Bad").mkdir()
            (root / "Movies" / "poster.jpg").write_bytes(b"poster")
            database = root / "runtime.sqlite3"
            document = _document(root, database)
            with (
                SQLiteConfigurationRepository(database) as configuration_repository,
                SQLiteTaskRepository(database) as task_repository,
            ):
                managed = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(database),
                )
                active = _activate(managed, document)
                api = _media_library_api(task_repository, managed, document)

                status, listing = _request(api, "/api/v1/media-libraries")
                self.assertEqual(status, 200)
                self.assertEqual(listing["surface"], "media_libraries")
                self.assertEqual(listing["sideEffects"], "none")
                self.assertEqual(
                    [item["id"] for item in listing["items"]],
                    ["movies", "shared", "tv", "tv shows"],
                )
                self.assertNotIn("off", [item["id"] for item in listing["items"]])
                shared = listing["items"][0]
                self.assertEqual(shared["rootPath"], "Movies")
                self.assertEqual(shared["storage"]["id"], "storage")
                # No card statistics, capacity, FileIndex facts or results.
                self.assertNotIn("fileCount", shared)
                self.assertNotIn("totalSize", shared)
                self.assertNotIn("statistics", shared)
                self.assertEqual(listing["configuration"]["revisionId"], active.revision_id)

                status, files = _request(api, "/api/v1/media-libraries/shared/files")
                self.assertEqual(status, 200)
                self.assertEqual(files["surface"], "media_library_files")
                self.assertEqual(files["mediaLibrary"]["id"], "shared")
                self.assertEqual(files["mediaLibrary"]["rootPath"], "Movies")
                self.assertEqual(files["path"], "")
                self.assertEqual(files["storageId"], "storage")
                self.assertEqual(files["breadcrumbs"][0]["name"], "MediaLibrary root")
                self.assertEqual(
                    [item["name"] for item in files["entries"]], ["Breaking Bad", "poster.jpg"]
                )
                for entry in files["entries"]:
                    self.assertNotIn("fileId", entry)
                    self.assertNotIn("organizeEligible", entry)
                self.assertEqual(files["sideEffects"], "none")

                # Library-relative path stays confined to the configured root.
                status, nested = _request(
                    api, "/api/v1/media-libraries/shared/files?path=Breaking%20Bad"
                )
                self.assertEqual(status, 200)
                self.assertEqual(nested["path"], "Breaking Bad")
                self.assertEqual(nested["breadcrumbs"][-1]["path"], "Breaking Bad")

                # The disabled library cannot be listed or browsed.
                status, error = _request(api, "/api/v1/media-libraries/off/files")
                self.assertEqual(status, 404)
                self.assertEqual(error["error"]["code"], "storage_browser_media_library_not_found")

                status, error = _request(
                    api,
                    "/api/v1/media-libraries/shared/files?path=../outside",
                )
                self.assertEqual(status, 400)
                self.assertEqual(error["error"]["code"], "storage_browser_invalid_path")

                status, error = _request(
                    api,
                    "/api/v1/media-libraries/shared/files",
                    token=None,
                )
                self.assertEqual(status, 401)

                status, error = _request(api, "/api/v1/media-libraries/shared/files", token="wrong")
                self.assertEqual(status, 401)

    def test_cross_kind_cursor_reuse_fails_closed_both_directions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Movies").mkdir()
            for index in range(3):
                (root / "Movies" / f"a{index}.mkv").write_bytes(b"x" * (index + 1))
            database = root / "runtime.sqlite3"
            document = _document(root, database)
            with (
                SQLiteConfigurationRepository(database) as configuration_repository,
                SQLiteTaskRepository(database) as task_repository,
            ):
                managed = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(database),
                )
                _activate(managed, document)
                api = _media_library_api(task_repository, managed, document)

                # The ResourceLibrary "shared" and MediaLibrary "shared" point at
                # the same Storage and root: authority must still not cross.
                status, resource_page = _request(
                    api,
                    "/api/v1/resource-libraries/shared/files?limit=1",
                )
                self.assertEqual(status, 200)
                self.assertTrue(resource_page["nextCursor"])

                status, error = _request(
                    api,
                    "/api/v1/media-libraries/shared/files?limit=1&cursor="
                    + resource_page["nextCursor"],
                )
                self.assertEqual(status, 400)
                self.assertEqual(error["error"]["code"], "storage_browser_cursor_invalid")

                status, media_page = _request(
                    api,
                    "/api/v1/media-libraries/shared/files?limit=1",
                )
                self.assertEqual(status, 200)
                self.assertTrue(media_page["nextCursor"])
                status, error = _request(
                    api,
                    "/api/v1/resource-libraries/shared/files?limit=1&cursor="
                    + media_page["nextCursor"],
                )
                self.assertEqual(status, 400)
                self.assertEqual(error["error"]["code"], "storage_browser_cursor_invalid")

                # A media cursor is bound to its own library, path and limit.
                status, error = _request(
                    api,
                    "/api/v1/media-libraries/tv/files?limit=1&cursor=" + media_page["nextCursor"],
                )
                self.assertEqual(status, 400)
                self.assertEqual(error["error"]["code"], "storage_browser_cursor_invalid")

                # The cursor continues correctly on its own authority scope.
                status, second_page = _request(
                    api,
                    "/api/v1/media-libraries/shared/files?limit=1&cursor="
                    + media_page["nextCursor"],
                )
                self.assertEqual(status, 200)
                self.assertNotEqual(
                    media_page["entries"][0]["name"], second_page["entries"][0]["name"]
                )

    def test_media_reads_perform_zero_storage_mutation_and_start_no_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Movies").mkdir()
            database = root / "runtime.sqlite3"
            document = _document(root, database)
            storage = _CountingStorage()
            with (
                SQLiteConfigurationRepository(database) as configuration_repository,
                SQLiteTaskRepository(database) as task_repository,
            ):
                managed = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(database),
                )
                _activate(managed, document)
                api = _media_library_api(
                    task_repository,
                    managed,
                    document,
                    storage_adapters={"storage": storage},
                )
                status, _ = _request(api, "/api/v1/media-libraries")
                self.assertEqual(status, 200)
                status, files = _request(api, "/api/v1/media-libraries/shared/files?limit=5")
                self.assertEqual(status, 200)
                status, nested = _request(
                    api, "/api/v1/media-libraries/shared/files?path=Movies&limit=5"
                )
                self.assertEqual(status, 200)
                # All Storage access stays read-only and confined; the provider
                # adapter raised on any mutation and none of those calls fired.
                self.assertEqual((), task_repository.list_tasks())
                self.assertEqual((), task_repository.list_jobs())
                self.assertEqual(files["sideEffects"], "none")
                self.assertTrue(files["retrySafe"] if "retrySafe" in files else True)
                # The MediaLibrary root is joined server-side: the provider only
                # ever sees the configured root + relative path.
                for called_path, _, _ in storage.list_page_calls:
                    self.assertTrue(called_path == "Movies" or called_path.startswith("Movies/"))

    def test_media_routes_have_dedicated_fallbacks_and_query_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "runtime.sqlite3"
            document = _document(root, database)
            with (
                SQLiteConfigurationRepository(database) as configuration_repository,
                SQLiteTaskRepository(database) as task_repository,
            ):
                managed = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(database),
                )
                _activate(managed, document)
                api = _media_library_api(task_repository, managed, document)

                status, error = _request(api, "/api/v1/media-libraries/shared/files?bogus=1")
                self.assertEqual(status, 400)

                status, error = _request(api, "/api/v1/media-libraries/shared/files?limit=0")
                self.assertEqual(status, 400)

                status, error = _request(
                    api, "/api/v1/media-libraries/shared/files", token="nonexistent-scope"
                )
                # Unknown token fails closed as unauthorized.
                self.assertEqual(status, 401)

                status, _ = _request(api, "/api/v1/media-libraries", token=None)
                # The list route requires authentication.
                self.assertEqual(status, 401)

    def test_media_browse_fails_closed_without_an_active_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.mkdir(exist_ok=True)
            database = root / "runtime.sqlite3"
            document = _document(root, database)
            with (
                SQLiteConfigurationRepository(database) as configuration_repository,
                SQLiteTaskRepository(database) as task_repository,
            ):
                managed = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(database),
                )
                api = _media_library_api(task_repository, managed, document)
                status, error = _request(api, "/api/v1/media-libraries/shared/files")
                self.assertEqual(status, 503)
                self.assertEqual(error["error"]["code"], "configuration_unavailable")
                self.assertEqual(error["error"]["details"]["sideEffects"], "none")


if __name__ == "__main__":
    unittest.main()
