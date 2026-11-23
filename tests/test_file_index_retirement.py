"""Task45.5 RO-7 acceptance, continued through Task 58.2: FileIndex retirement.

These tests exercise the real application boundary for the retired FileIndex
product through the two current library-file APIs the Web Files pages use:

* ``GET /api/resource-libraries/{id}/files`` and ``GET
  /api/media-libraries/{id}/files`` read the exact Active library directory
  through the shared application browser;
* the old index identities, routes and modules are gone;
* listing is strictly read-only: no directory/observation/Task/Result row is
  written, no media or Provider is touched and the store is byte-identical;
* a fresh runtime database has no FileIndex tables and no FileIndex is assembled
  anywhere in the composition.
"""

from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
import urllib.parse
from pathlib import Path

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

EXAMPLES = Path("config/strategy.example.json")

#: Every module that made up the retired FileIndex product.  Importing any of
#: them must now fail: there is no repository, no lifecycle service and no
#: dedicated schema left behind under a new name.
RETIRED_MODULES = (
    "mediaflow.domain.file_index",
    "mediaflow.domain.file_catalog",
    "mediaflow.domain.file_lifecycle",
    "mediaflow.application.file_catalog",
    "mediaflow.application.file_index_lifecycle",
    "mediaflow.infrastructure.sqlite_file_index",
    "mediaflow.infrastructure.memory_file_index",
    "mediaflow.infrastructure.file_index_schema",
)


def _bootstrap(root: Path) -> tuple[Path, dict[str, object]]:
    document = json.loads(EXAMPLES.read_text(encoding="utf-8"))
    source = root / "source"
    (source / "Media" / "Movies").mkdir(parents=True)
    (source / "Media" / "Movies" / "One.2001.mkv").write_bytes(b"one")
    (source / "Media" / "Movies" / "notes.txt").write_bytes(b"notes")
    (source / "Media" / "Movies" / "长 名 .mkv").write_bytes(b"unicode")
    (source / "Media" / "Movies" / "Nested").mkdir()
    document["storages"][0]["rootPath"] = str(source)
    document["persistence"] = {"databasePath": str(root / "runtime.sqlite3")}
    config = root / "config.json"
    config.write_text(json.dumps(document), encoding="utf-8")
    return config, document


def _activate(database: Path, document: dict[str, object]):
    with SQLiteConfigurationRepository(str(database)) as repository:
        service = ManagedConfigurationService(repository, bootstrap_database_path=str(database))
        draft = service.import_draft(document, actor="tester")
        validated = service.validate(draft.revision_id, actor="tester")
        return service.activate(
            validated.revision_id, expected_version=validated.version, actor="tester"
        )


class FileIndexRetirementTests(unittest.TestCase):
    def test_retired_file_index_modules_do_not_exist(self) -> None:
        for name in RETIRED_MODULES:
            with self.subTest(module=name):
                with self.assertRaises(ModuleNotFoundError):
                    __import__(name)

    def test_fresh_runtime_database_creates_no_file_index_table(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, document = _bootstrap(root)
            database = root / "runtime.sqlite3"
            _activate(database, document)
            # The supported bounded task read opens/initializes the runtime
            # schema exactly as the API process does at startup; the fresh
            # schema must not include any FileIndex product table.
            with _api(self, database, document) as api:
                status, body = _request(api, "/api/operations/runs")
            self.assertEqual(200, status)
            connection = sqlite3.connect(database)
            try:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
            finally:
                connection.close()
            self.assertNotIn("file_index", tables)
            self.assertNotIn("file_index_occurrences", tables)
            self.assertNotIn("file_index_reprocess_requests", tables)

    def test_files_list_without_active_answers_without_migrating_the_store(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, document = _bootstrap(root)
            database = root / "runtime.sqlite3"
            with _api(self, database, document) as api:
                before = database.read_bytes()
                status, body = _request(api, "/api/resource-libraries/source/files")
                self.assertEqual(503, status)
                self.assertEqual("configuration_unavailable", body["error"]["code"])
                after = database.read_bytes()
                status, body = _request(api, "/api/media-libraries/movies/files")
                self.assertEqual(503, status)
                self.assertEqual("configuration_unavailable", body["error"]["code"])
            self.assertEqual(before, after)
            connection = sqlite3.connect(database)
            try:
                markers = connection.execute(
                    "SELECT component, version FROM schema_version ORDER BY component"
                ).fetchall()
            finally:
                connection.close()
            # The listing never migrates the store's markers.
            self.assertNotIn(("configuration_management", 999), [tuple(row) for row in markers])

    def test_files_list_reads_real_entries_and_reports_unknown_total(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, document = _bootstrap(root)
            database = root / "runtime.sqlite3"
            _activate(database, document)
            with _api(self, database, document) as api:
                status, body = _request(
                    api,
                    "/api/resource-libraries/source/files",
                    query={"path": "Movies"},
                )
            self.assertEqual(200, status)
            entries = {entry["name"]: entry for entry in body["entries"]}
            self.assertEqual("file", entries["One.2001.mkv"]["type"])
            self.assertEqual(3, entries["One.2001.mkv"]["size"])
            self.assertEqual("file", entries["notes.txt"]["type"])
            self.assertEqual(5, entries["notes.txt"]["size"])
            self.assertEqual("file", entries["长 名 .mkv"]["type"])
            self.assertEqual(7, entries["长 名 .mkv"]["size"])
            self.assertEqual("directory", entries["Nested"]["type"])
            self.assertIsNone(body.get("total"))
            self.assertFalse(body["hasNext"])
            # No organize filtering, index identity or status is published.
            serialized = json.dumps(body)
            for forbidden in ("file_id", "scanStatus", "FileIndex", "occurrenceId"):
                self.assertNotIn(forbidden, serialized)

    def test_files_list_rejects_a_tampered_active_payload(self) -> None:
        """A rewritten Active payload is refused before any Storage is followed.

        The canonical managed integrity rule is the same one runtime consumes, so
        a payload whose stored digest no longer matches must be reported with a
        bounded reason and never listed (even from the rewritten root).
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, document = _bootstrap(root)
            database = root / "runtime.sqlite3"
            active = _activate(database, document)
            (root / "unpublished" / "Media" / "Movies").mkdir(parents=True)
            (root / "unpublished" / "Media" / "Movies" / "unpublished.txt").write_bytes(b"x")
            with sqlite3.connect(database) as connection:
                payload = json.loads(
                    connection.execute(
                        "SELECT payload FROM managed_configuration_revisions WHERE revision_id=?",
                        (active.revision_id,),
                    ).fetchone()[0]
                )
                payload["storages"][0]["rootPath"] = str(root / "unpublished")
                connection.execute(
                    "UPDATE managed_configuration_revisions SET payload=? WHERE revision_id=?",
                    (json.dumps(payload), active.revision_id),
                )
            with _api(self, database, document) as api:
                before = database.read_bytes()
                status, body = _request(
                    api,
                    "/api/resource-libraries/source/files",
                    query={"path": "Movies"},
                )
            self.assertEqual(503, status)
            self.assertIn("unavailable", json.dumps(body).lower())
            self.assertNotIn("unpublished.txt", json.dumps(body))
            self.assertNotIn("One.2001.mkv", json.dumps(body))
            self.assertEqual(before, database.read_bytes())

    def test_files_list_rejects_an_unsupported_active_document_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, document = _bootstrap(root)
            database = root / "runtime.sqlite3"
            active = _activate(database, document)
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "UPDATE managed_configuration_revisions SET schema_version=999 "
                    "WHERE revision_id=?",
                    (active.revision_id,),
                )
            with _api(self, database, document) as api:
                before = database.read_bytes()
                status, body = _request(
                    api,
                    "/api/resource-libraries/source/files",
                    query={"path": "Movies"},
                )
            self.assertEqual(503, status)
            self.assertNotIn("One.2001.mkv", json.dumps(body))
            self.assertEqual(before, database.read_bytes())

    def test_api_has_no_file_index_product_routes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, document = _bootstrap(root)
            database = root / "runtime.sqlite3"
            _activate(database, document)
            with _api(self, database, document) as api:
                for path in (
                    "/api/files",
                    "/api/file-index",
                    "/api/files/stats",
                    "/api/files/by-source",
                ):
                    with self.subTest(path=path):
                        status, _ = _request(api, path)
                        self.assertEqual(404, status)

    def test_listing_records_no_directory_observation_task_or_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, document = _bootstrap(root)
            database = root / "runtime.sqlite3"
            _activate(database, document)
            with _api(self, database, document) as api:
                for _ in range(3):
                    status, _ = _request(
                        api,
                        "/api/resource-libraries/source/files",
                        query={"path": "Movies"},
                    )
                    self.assertEqual(200, status)
                repository = api._repository
                self.assertEqual((), repository.list_tasks())
                self.assertEqual((), repository.list_manual_intents())
                self.assertEqual((), repository.list_manual_previews("does-not-exist"))
                self.assertEqual((), repository.list_results("does-not-exist"))


class CrossInstancePaginationTests(unittest.TestCase):
    """RO-7 P1 regression, current surfaces: a cursor issued by one API instance
    must page in the next.

    Each instance owns its own repository connections and browser, exactly like
    two independent API processes; the cursor-authentication key is the one
    persisted in the managed store, so real pages load, never overlap, reach the
    last page and reconstruct the directory, and scope/tamper are refused.
    """

    def _pageable_fixture(self, root: Path) -> tuple[Path, dict, Path]:
        config, document = _bootstrap(root)
        movies = root / "source" / "Media" / "Movies"
        for index in range(7):
            (movies / f"Page-{index:02d}.mkv").write_bytes(b"x")
        database = root / "runtime.sqlite3"
        _activate(database, document)
        return config, document, database

    def _list(self, api, query: dict[str, str]):
        return _request(api, "/api/resource-libraries/source/files", query=query)

    def test_two_independent_instances_page_through_every_entry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, document, database = self._pageable_fixture(root)
            with _api(self, database, document) as first_api:
                status, full = self._list(first_api, {"path": "Movies", "limit": "100"})
                self.assertEqual(200, status)
                expected = [entry["name"] for entry in full["entries"]]
                self.assertGreater(len(expected), 3)

                status, page_one = self._list(first_api, {"path": "Movies", "limit": "3"})
                self.assertEqual(200, status)
                self.assertTrue(page_one["hasNext"])
                first_names = [entry["name"] for entry in page_one["entries"]]
                self.assertEqual(3, len(first_names))
                cursor = page_one["nextCursor"]
                self.assertTrue(cursor)

            # A second, independent instance must accept the first page's cursor.
            with _api(self, database, document) as second_api:
                status, page_two = self._list(
                    second_api, {"path": "Movies", "limit": "3", "cursor": cursor}
                )
                self.assertEqual(200, status)
                second_names = [entry["name"] for entry in page_two["entries"]]
                self.assertEqual(3, len(second_names))
                self.assertEqual([], sorted(set(first_names) & set(second_names)))

                collected = first_names + second_names
                cursor = page_two.get("nextCursor")
                while cursor:
                    status, page = self._list(
                        second_api, {"path": "Movies", "limit": "3", "cursor": cursor}
                    )
                    self.assertEqual(200, status)
                    collected.extend(entry["name"] for entry in page["entries"])
                    cursor = page.get("nextCursor")
                self.assertEqual(sorted(expected), sorted(collected))

    def test_cursor_is_rejected_across_kind_directory_and_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, document, database = self._pageable_fixture(root)
            with _api(self, database, document) as api:
                status, page = self._list(api, {"path": "Movies", "limit": "3"})
                cursor = page["nextCursor"]

                # Same cursor, different library kind: kind/root binding refuses it.
                status, body = _request(
                    api,
                    "/api/media-libraries/movies/files",
                    query={"path": "Movies", "limit": "3", "cursor": cursor},
                )
                self.assertEqual(400, status)
                self.assertEqual("storage_browser_cursor_invalid", body["error"]["code"])

                # Same cursor, different directory: directory binding refuses it.
                status, body = self._list(api, {"path": "", "limit": "3", "cursor": cursor})
                self.assertEqual(400, status)
                self.assertEqual("storage_browser_cursor_invalid", body["error"]["code"])

                # A tampered cursor is refused rather than silently re-read.
                tampered = cursor[:-1] + ("A" if cursor[-1] != "A" else "B")
                status, body = self._list(api, {"path": "Movies", "limit": "3", "cursor": tampered})
                self.assertEqual(400, status)
                self.assertEqual("storage_browser_cursor_invalid", body["error"]["code"])

    def test_paging_is_read_only_and_key_is_created_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, document, database = self._pageable_fixture(root)
            with sqlite3.connect(database) as connection:
                first_key = connection.execute(
                    "SELECT key_material FROM managed_internal_keys "
                    "WHERE key_name='storage_browser_cursor'"
                ).fetchone()[0]
            with _api(self, database, document) as api:
                before = database.read_bytes()
                status, page = self._list(api, {"path": "Movies", "limit": "3"})
                self.assertEqual(200, status)
                cursor = page["nextCursor"]
                status, _ = self._list(api, {"path": "Movies", "limit": "3", "cursor": cursor})
                self.assertEqual(200, status)
                # Listing and paging never rewrite the store; the internal key
                # is created once by the supported initialization, not by a read.
                self.assertEqual(before, database.read_bytes())
            with sqlite3.connect(database) as connection:
                second_key = connection.execute(
                    "SELECT key_material FROM managed_internal_keys "
                    "WHERE key_name='storage_browser_cursor'"
                ).fetchone()[0]
            self.assertEqual(first_key, second_key)
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual((), repository.list_tasks())
                self.assertEqual((), repository.list_results("does-not-exist"))

    def test_internal_key_survives_reopen_and_reuses_persisted_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "configuration.sqlite3"
            from mediaflow.domain.configuration_management import (
                STORAGE_BROWSER_CURSOR_KEY_NAME,
            )

            with SQLiteConfigurationRepository(database) as repository:
                first = repository.internal_key(STORAGE_BROWSER_CURSOR_KEY_NAME)
                self.assertIsNotNone(first)
                self.assertGreaterEqual(len(first), 32)
            with SQLiteConfigurationRepository(database) as reopened:
                # The create-if-absent key is never overwritten, so a cursor
                # issued before a restart stays verifiable afterwards.
                self.assertEqual(first, reopened.internal_key(STORAGE_BROWSER_CURSOR_KEY_NAME))
            # A second store in the same directory never shares key material.
            with SQLiteConfigurationRepository(root / "other.sqlite3") as other:
                self.assertNotEqual(first, other.internal_key(STORAGE_BROWSER_CURSOR_KEY_NAME))


def _api(test: unittest.TestCase, database: Path, document: dict[str, object]):
    """One real API process shape over one isolated combined store.

    The API owns a configuration repository (managed Active authority) and a
    runtime repository over the same deployment database, exactly like the
    resident API process.  The Files browser resolves the persisted internal
    cursor key from the store, never a per-instance random key.
    """

    configuration_repository = SQLiteConfigurationRepository(database)
    test.addCleanup(configuration_repository.close)
    service = ManagedConfigurationService(
        configuration_repository,
        bootstrap_database_path=str(database),
    )
    runtime_repository = SQLiteTaskRepository(database)
    test.addCleanup(runtime_repository.close)
    return _ApiContext(
        MediaFlowApi(
            runtime_repository,
            principals=(
                ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ})),
            ),
            configuration_service=service,
            bootstrap_document=document,
        )
    )


class _ApiContext:
    """Context wrapper so ``with _api(...)`` closes nothing twice."""

    def __init__(self, api: MediaFlowApi) -> None:
        self._api = api

    def __enter__(self) -> MediaFlowApi:
        return self._api

    def __exit__(self, *_):
        return False


def _request(
    api,
    path: str,
    *,
    method: str = "GET",
    token: str = "admin-token",
    query: dict[str, str] | None = None,
):
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": urllib.parse.urlencode(query or {}),
        "CONTENT_LENGTH": "0",
        "wsgi.input": io.BytesIO(),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
    }
    body = b"".join(api(environ, lambda value, headers: statuses.append(value)))
    return int(statuses[0].split()[0]), json.loads(body)


if __name__ == "__main__":
    unittest.main()
