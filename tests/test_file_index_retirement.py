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
import re
import sqlite3
import subprocess
import sys
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
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

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
            before = database.read_bytes()
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
            self.assertIn("files_list_digest_corrupt", output)
            self.assertIn("no configuration was created", output)
            self.assertNotIn("unpublished.txt", output)
            self.assertNotIn("One.2001.mkv", output)
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
            before = database.read_bytes()
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
            self.assertIn("files_list_schema_unsupported", output)
            self.assertIn("no configuration was created", output)
            self.assertNotIn("One.2001.mkv", output)
            self.assertEqual(before, database.read_bytes())

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


class CrossProcessCliPaginationTests(unittest.TestCase):
    """RO-7 P1 regression: a cursor issued by one CLI process must page in the next.

    The previous implementation built a fresh ``StorageBrowserService`` per CLI
    invocation with a per-process random cursor key, so the ``Next cursor``
    printed by one process was unverifiable by the next.  These tests drive two
    independent ``mediaflow`` processes against one isolated Active store and
    assert that real pages load, never overlap, reach the last page and
    reconstruct the directory, and that scope/tamper/expiry are still refused.
    """

    def _run_cli(self, config: Path, *arguments: str) -> tuple[int, str]:
        """Run ``mediaflow`` in a real, independent interpreter process."""

        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys; from mediaflow.final_cli import final_main; "
                    "sys.exit(final_main(sys.argv[1:], stdout=sys.stdout, stderr=sys.stderr))"
                ),
                "--config",
                str(config),
                "files",
                "list",
                *arguments,
            ],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
        )
        return completed.returncode, completed.stdout

    @staticmethod
    def _names(output: str) -> list[str]:
        names = []
        for line in output.splitlines():
            match = re.match(r"^(.*) \| (file|directory) \| \d+ \| ", line)
            if match is not None and match.group(1) != "NAME":
                names.append(match.group(1))
        return names

    @staticmethod
    def _next_cursor(output: str) -> str | None:
        for line in output.splitlines():
            if line.startswith("Next cursor:"):
                value = line.split(":", 1)[1].strip()
                return value if value and value != "-" else None
        return None

    def _pageable_fixture(self, root: Path) -> tuple[Path, Path]:
        config, document = _bootstrap(root)
        movies = root / "source" / "Media" / "Movies"
        for index in range(7):
            (movies / f"Page-{index:02d}.mkv").write_bytes(b"x")
        database = root / "runtime.sqlite3"
        _activate(database, document)
        return config, database

    def test_two_independent_processes_page_through_every_entry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, _ = self._pageable_fixture(root)
            full_code, full_output = self._run_cli(
                config, "--resource-library", "source", "--path", "Movies", "--limit", "100"
            )
            self.assertEqual(0, full_code)
            expected = self._names(full_output)
            self.assertGreater(len(expected), 3)

            first_code, first_output = self._run_cli(
                config, "--resource-library", "source", "--path", "Movies", "--limit", "3"
            )
            self.assertEqual(0, first_code)
            self.assertIn("More available: yes", first_output)
            first_names = self._names(first_output)
            self.assertEqual(3, len(first_names))

            cursor = self._next_cursor(first_output)
            self.assertIsNotNone(cursor)
            # A second, independent process must accept the first page's cursor.
            second_code, second_output = self._run_cli(
                config,
                "--resource-library",
                "source",
                "--path",
                "Movies",
                "--limit",
                "3",
                "--cursor",
                cursor,
            )
            self.assertEqual(0, second_code)
            self.assertNotIn("storage_browser_cursor_invalid", second_output)
            second_names = self._names(second_output)
            self.assertEqual(3, len(second_names))
            self.assertEqual([], sorted(set(first_names) & set(second_names)))

            collected = first_names + second_names
            cursor = self._next_cursor(second_output)
            while cursor is not None:
                code, output = self._run_cli(
                    config,
                    "--resource-library",
                    "source",
                    "--path",
                    "Movies",
                    "--limit",
                    "3",
                    "--cursor",
                    cursor,
                )
                self.assertEqual(0, code)
                self.assertNotIn("storage_browser_cursor_invalid", output)
                collected.extend(self._names(output))
                cursor = self._next_cursor(output)
            self.assertEqual(sorted(expected), sorted(collected))

    def test_cursor_is_rejected_across_kind_directory_and_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, _ = self._pageable_fixture(root)
            _, first_output = self._run_cli(
                config, "--resource-library", "source", "--path", "Movies", "--limit", "3"
            )
            cursor = self._next_cursor(first_output)
            self.assertIsNotNone(cursor)

            # Same cursor, different library kind: kind/root binding refuses it.
            _, media_output = self._run_cli(
                config,
                "--media-library",
                "movies",
                "--path",
                "Movies",
                "--limit",
                "3",
                "--cursor",
                cursor,
            )
            self.assertIn("storage_browser_cursor_invalid", media_output)

            # Same cursor, different directory: directory binding refuses it.
            _, directory_output = self._run_cli(
                config,
                "--resource-library",
                "source",
                "--path",
                "",
                "--limit",
                "3",
                "--cursor",
                cursor,
            )
            self.assertIn("storage_browser_cursor_invalid", directory_output)

            # A tampered cursor is refused rather than silently re-read.
            tampered = cursor[:-1] + ("A" if cursor[-1] != "A" else "B")
            _, tampered_output = self._run_cli(
                config,
                "--resource-library",
                "source",
                "--path",
                "Movies",
                "--limit",
                "3",
                "--cursor",
                tampered,
            )
            self.assertIn("storage_browser_cursor_invalid", tampered_output)

    def test_paging_is_read_only_and_key_is_created_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, database = self._pageable_fixture(root)
            with sqlite3.connect(database) as connection:
                first_key = connection.execute(
                    "SELECT key_material FROM managed_internal_keys "
                    "WHERE key_name='storage_browser_cursor'"
                ).fetchone()[0]
            before = database.read_bytes()
            _, first_output = self._run_cli(
                config, "--resource-library", "source", "--path", "Movies", "--limit", "3"
            )
            cursor = self._next_cursor(first_output)
            self._run_cli(
                config,
                "--resource-library",
                "source",
                "--path",
                "Movies",
                "--limit",
                "3",
                "--cursor",
                cursor,
            )
            # Listing and paging never rewrite the store; the internal key is
            # created once by the supported initialization, not by a read.
            self.assertEqual(before, database.read_bytes())
            with sqlite3.connect(database) as connection:
                second_key = connection.execute(
                    "SELECT key_material FROM managed_internal_keys "
                    "WHERE key_name='storage_browser_cursor'"
                ).fetchone()[0]
            self.assertEqual(first_key, second_key)
            with SQLiteTaskRepositoryContext(database) as repository:
                self.assertEqual((), repository.list_tasks())
                self.assertEqual((), repository.list_results("does-not-exist"))

    def test_listing_without_initialized_key_is_refused_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, database = self._pageable_fixture(root)
            # Remove the internal key to model a store whose supported
            # initialization never ran the key creation.
            with sqlite3.connect(database) as connection:
                connection.execute("DELETE FROM managed_internal_keys")
            before = database.read_bytes()
            code, output = self._run_cli(config, "--resource-library", "source", "--path", "Movies")
            self.assertEqual(0, code)
            self.assertIn("files_list_internal_key_unavailable", output)
            self.assertIn("no configuration was created", output)
            # A read never mints a one-off key or writes the store.
            self.assertEqual(before, database.read_bytes())

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
