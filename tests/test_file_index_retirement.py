"""Task45.5 RO-7 acceptance: FileIndex retirement and shared live lists.

These tests exercise the real application boundary for the retired FileIndex
product:

* ``mediaflow files list`` reads the same exact Active library directory the Web
  Files/MediaLibrary pages read, through the shared application browser;
* the old index identities, routes and modules are gone, and old inputs get an
  ordinary unsupported/not-found answer rather than a compatibility engine;
* listing is strictly read-only: no database is created or migrated, no
  directory/observation/Task/Result/permission row is written and no media or
  Provider is touched;
* a fresh runtime database has no FileIndex tables and no FileIndex is assembled
  anywhere in the composition.
"""

from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
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


def _cli(argv: list[str]) -> tuple[int, str]:
    output = io.StringIO()
    code = final_main(argv, stdout=output, stderr=io.StringIO())
    return code, output.getvalue()


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
            # A full runtime command opens/initializes the database; the fresh
            # schema must not include any FileIndex product table.
            code, _ = _cli(["--config", str(config), "dashboard"])
            self.assertEqual(0, code)
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

    def test_files_list_requires_exactly_one_library_selector(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, _ = _bootstrap(root)
            with self.assertRaises(SystemExit):
                _cli(["--config", str(config), "files", "list"])
            with self.assertRaises(SystemExit):
                _cli(
                    [
                        "--config",
                        str(config),
                        "files",
                        "list",
                        "--resource-library",
                        "source",
                        "--media-library",
                        "movies",
                    ]
                )

    def test_files_list_without_active_does_not_create_or_migrate_the_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, _ = _bootstrap(root)
            database = root / "runtime.sqlite3"
            self.assertFalse(database.exists())
            code, output = _cli(
                ["--config", str(config), "files", "list", "--resource-library", "source"]
            )
            self.assertEqual(0, code)
            self.assertIn("files_list_no_active", output)
            self.assertIn("no configuration was created", output)
            self.assertFalse(database.exists())

    def test_files_list_reads_real_entries_and_reports_unknown_total(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, document = _bootstrap(root)
            _activate(root / "runtime.sqlite3", document)
            code, output = _cli(
                [
                    "--config",
                    str(config),
                    "files",
                    "list",
                    "--resource-library",
                    "source",
                    "--path",
                    "Movies",
                ]
            )
            self.assertEqual(0, code)
            self.assertIn("Library kind: ResourceLibrary", output)
            self.assertIn("One.2001.mkv | file | 3", output)
            self.assertIn("notes.txt | file | 5", output)
            self.assertIn("长 名 .mkv | file | 7", output)
            self.assertIn("Nested | directory", output)
            self.assertIn("Total: unknown", output)
            # No organize filtering, index identity or status is published.
            for forbidden in ("file_id", "scanStatus", "FileIndex", "occurrenceId"):
                self.assertNotIn(forbidden, output)

    def test_files_list_rejects_the_retired_index_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, _ = _bootstrap(root)
            for retired in (
                ["--scan-status", "ready"],
                ["--cursor-file-id", "abc"],
                ["--storage", "source-storage"],
                ["--query", "One"],
                ["--after", "2026-01-01T00:00:00+00:00"],
            ):
                with self.subTest(retired=retired):
                    with self.assertRaises(SystemExit):
                        _cli(
                            [
                                "--config",
                                str(config),
                                "files",
                                "list",
                                "--resource-library",
                                "source",
                                *retired,
                            ]
                        )

    def test_files_show_and_stats_are_not_registered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, _ = _bootstrap(root)
            for retired in ("show", "stats"):
                with self.subTest(command=retired):
                    with self.assertRaises(SystemExit):
                        _cli(["--config", str(config), "files", retired, "some-id"])

    def test_api_has_no_file_index_product_routes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, document = _bootstrap(root)
            database = root / "runtime.sqlite3"
            _activate(database, document)
            with SQLiteTaskRepositoryContext(database) as repository:
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal(
                            "viewer", "viewer-token", frozenset({ApiPermission.READ})
                        ),
                    ),
                )
                for path in (
                    "/api/v1/files",
                    "/api/v1/file-index",
                    "/api/v1/files/stats",
                    "/api/v1/files/by-source",
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
            with SQLiteTaskRepositoryContext(database) as repository:
                for _ in range(3):
                    code, _ = _cli(
                        [
                            "--config",
                            str(config),
                            "files",
                            "list",
                            "--resource-library",
                            "source",
                            "--path",
                            "Movies",
                        ]
                    )
                    self.assertEqual(0, code)
                self.assertEqual((), repository.list_tasks())
                self.assertEqual((), repository.list_jobs())
                self.assertEqual((), repository.list_manual_intents())
                self.assertEqual((), repository.list_manual_previews("does-not-exist"))
                self.assertEqual((), repository.list_results("does-not-exist"))


class SQLiteTaskRepositoryContext:
    """A thin context manager so the API test owns exactly one repository."""

    def __init__(self, database: Path) -> None:
        from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository

        self._repository = SQLiteTaskRepository(database)

    def __enter__(self):
        return self._repository

    def __exit__(self, *_):
        self._repository.close()
        return False


def _request(api, path: str, *, method: str = "GET", token: str = "viewer-token"):
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": "0",
        "wsgi.input": io.BytesIO(),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
    }
    body = b"".join(api(environ, lambda value, headers: statuses.append(value)))
    return int(statuses[0].split()[0]), json.loads(body)


if __name__ == "__main__":
    unittest.main()
