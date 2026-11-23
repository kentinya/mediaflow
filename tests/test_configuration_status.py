from __future__ import annotations

import io
import json
import os
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.configuration_snapshot import (
    MAX_SECTION_ITEMS,
    build_configuration_snapshot,
)
from mediaflow.infrastructure.runtime_configuration import (
    RuntimeConfiguration,
    StorageDefinition,
    load_runtime_configuration,
)
from mediaflow.infrastructure.sqlite_configuration_schema import CONFIGURATION_SCHEMA_VERSION
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.managed_config_fixture import publish_managed_document
from tests.resident_entry_fixtures import run_api_entry, serve_once


def example_document():
    return json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))


class AuditOnlyRepository:
    def __init__(self) -> None:
        self.audit = []

    def append_security_audit(self, value) -> None:
        self.audit.append(value)

    def __getattr__(self, name):
        raise AssertionError(f"system status must not access repository method {name}")


def request(api, method="GET", query="", token="viewer-token"):
    statuses = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": "/api/system/status",
        "QUERY_STRING": query,
        "CONTENT_LENGTH": "0",
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(),
    }
    if token:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    body = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(body)


class ConfigurationSnapshotTests(unittest.TestCase):
    def test_snapshot_is_bounded_deterministic_and_preserves_c_references(self) -> None:
        runtime = load_runtime_configuration(example_document())
        storages = tuple(
            StorageDefinition(f"storage-{index:03}", "local", f"/secret/{index}", "hidden")
            for index in range(MAX_SECTION_ITEMS + 3, 0, -1)
        )
        snapshot = build_configuration_snapshot(replace(runtime, storage_definitions=storages))
        document = snapshot.as_document()
        self.assertEqual(document["system"]["runtime_schema_version"], SCHEMA_VERSION)
        self.assertTrue(document["system"]["python_supported"])
        self.assertTrue(document["system"]["configuration_valid"])
        self.assertEqual(document["storages"]["total"], MAX_SECTION_ITEMS + 3)
        self.assertTrue(document["storages"]["truncated"])
        self.assertEqual(len(document["storages"]["items"]), MAX_SECTION_ITEMS)
        ids = [item["id"] for item in document["storages"]["items"]]
        self.assertEqual(ids, sorted(ids))
        policies = {
            item["recognition_type_id"]: item
            for item in document["recognition_type_policies"]["items"]
        }
        self.assertEqual(policies["C"]["metadata_policy_id"], "C")
        self.assertEqual(policies["C"]["naming_policy_id"], "A")
        self.assertEqual(policies["C"]["classification_policy_id"], "A")
        self.assertEqual(policies["C"]["organize_policy_id"], "A")
        changed = snapshot.as_document()
        changed["system"]["configuration_valid"] = False
        self.assertTrue(snapshot.as_document()["system"]["configuration_valid"])

    def test_hostile_configuration_content_is_never_exposed(self) -> None:
        source = example_document()
        secret = "DO-NOT-LEAK-9f43"
        source["storages"][0]["rootPath"] = f"/{secret}"
        source["storages"][0]["passwordEnv"] = secret
        source["resourceLibraries"][0]["displayRootPath"] = f"/{secret}/media"
        source["recognitionRules"][0]["condition"]["children"][1]["value"] = secret
        source["namingPolicies"][0]["directoryTemplate"] = "{title}-" + secret
        source["classificationPolicies"][0]["rules"][0]["result"]["path"] = [secret]
        document = build_configuration_snapshot(load_runtime_configuration(source)).as_document()
        rendered = json.dumps(document, ensure_ascii=False)
        # The injected hostile values never appear anywhere in the projection.
        self.assertNotIn(secret, rendered)
        # The forbidden raw configuration fields that could carry those values
        # are never projected. The bounded, intentional `root_path` projection
        # (a safe ResourceLibrary-relative display segment, not the hostile
        # Storage root) remains allowed, so this must not be a broad substring
        # ban on the word "root".
        for forbidden in (
            "rootPath",
            "displayRootPath",
            "passwordEnv",
            "template",
            "condition",
        ):
            self.assertNotIn(forbidden, rendered)
        # The intentional bounded root_path projection stays present and never
        # carries the hostile value.
        libraries = document["resource_libraries"]["items"]
        self.assertTrue(all("root_path" in item for item in libraries))
        self.assertTrue(all(secret not in item["root_path"] for item in libraries))

    def test_system_status_storage_projection_includes_operator_name_but_never_root(
        self,
    ) -> None:
        source = example_document()
        secret_root = "/private/mount/DO-NOT-LEAK-9f43"
        source["storages"][0]["rootPath"] = secret_root
        document = build_configuration_snapshot(load_runtime_configuration(source)).as_document()
        storage = document["storages"]["items"][0]
        self.assertIn("name", storage)
        self.assertIsInstance(storage["name"], str)
        self.assertNotIn(secret_root, json.dumps(document))
        self.assertNotIn("rootPath", json.dumps(document))

    def test_api_rbac_method_query_allowlist_and_no_repository_reads(self) -> None:
        snapshot = build_configuration_snapshot(load_runtime_configuration(example_document()))
        repository = AuditOnlyRepository()
        viewer = ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
        api = MediaFlowApi(repository, principals=(viewer,), system_status=snapshot)
        self.assertEqual(request(api, token=None)[0], 401)
        self.assertEqual(request(api, method="POST")[0], 405)
        self.assertEqual(request(api, query="paths=true")[0], 400)
        status, document = request(api)
        self.assertEqual(status, 200)
        self.assertEqual(
            set(document),
            {
                "system",
                "storages",
                "resource_libraries",
                "media_libraries",
                "recognition_types",
                "recognition_rules",
                "recognition_type_policies",
                "metadata_policies",
                "naming_policies",
                "classification_policies",
                "organize_policies",
            },
        )
        self.assertGreaterEqual(len(repository.audit), 7)

    def test_production_api_bootstrap_injects_snapshot_without_storage(self) -> None:

        class Server:
            app = None

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def serve_forever(self):
                return None

        with tempfile.TemporaryDirectory() as directory:
            source = example_document()
            source["persistence"]["databasePath"] = str(Path(directory, "runtime.sqlite3"))
            source["historyPath"] = str(Path(directory, "history.jsonl"))
            config = Path(directory, "strategy.json")
            config.write_text(json.dumps(source), encoding="utf-8")
            publish_managed_document(source)
            server = Server()

            def make_server(host, port, app):
                server.app = app
                return server

            with (
                patch.dict(os.environ, {"MEDIAFLOW_API_TOKEN": "viewer-token"}, clear=True),
                patch("mediaflow.production_wsgi.serve", side_effect=serve_once(make_server)),
                patch.object(
                    RuntimeConfiguration,
                    "create_storages",
                    side_effect=AssertionError("API status bootstrap constructed Storage"),
                ),
            ):
                status = run_api_entry(
                    config,
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )
            self.assertEqual(status, 0)
            self.assertIsNotNone(server.app)
            self.assertTrue(
                server.app._system_status.as_document()["system"]["configuration_valid"]
            )


if __name__ == "__main__":
    unittest.main()


class RetiredDatabaseStartupTests(unittest.TestCase):
    """A retired V1 runtime database is refused before any write."""

    def test_api_serve_rejects_v1_job_schema_without_modifying_the_file(self) -> None:
        import hashlib
        import sqlite3

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "v1.sqlite3")
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "CREATE TABLE schema_version ("
                    "component TEXT PRIMARY KEY, version INTEGER NOT NULL)"
                )
                connection.execute(
                    "INSERT INTO schema_version VALUES "
                    "('configuration_management', 10), ('runtime', 33)"
                )
                connection.execute("CREATE TABLE jobs (job_id TEXT PRIMARY KEY)")
                connection.commit()
            source = example_document()
            source["persistence"]["databasePath"] = str(database)
            config = Path(directory, "strategy.json")
            config.write_text(json.dumps(source), encoding="utf-8")
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            stderr = io.StringIO()
            code = run_api_entry(
                config,
                stdout=io.StringIO(),
                stderr=stderr,
                skip_preflight=False,
            )
            self.assertEqual(1, code)
            self.assertIn("retired V1 Job schema", stderr.getvalue())
            self.assertIn("file was not modified", stderr.getvalue())
            self.assertEqual(before, hashlib.sha256(database.read_bytes()).hexdigest())
            with sqlite3.connect(database) as connection:
                self.assertEqual(
                    [("configuration_management", 10), ("runtime", 33)],
                    connection.execute(
                        "SELECT component, version FROM schema_version ORDER BY component"
                    ).fetchall(),
                )

    def test_api_serve_rejects_another_application_database_without_modifying_it(
        self,
    ) -> None:
        import hashlib
        import sqlite3

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "notes.sqlite3")
            with sqlite3.connect(database) as connection:
                connection.execute("CREATE TABLE notes (note_id TEXT PRIMARY KEY, body TEXT)")
                connection.execute("INSERT INTO notes VALUES ('n-1', 'keep this note')")
                connection.commit()
            source = example_document()
            source["persistence"]["databasePath"] = str(database)
            config = Path(directory, "strategy.json")
            config.write_text(json.dumps(source), encoding="utf-8")
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            stderr = io.StringIO()
            code = run_api_entry(
                config,
                stdout=io.StringIO(),
                stderr=stderr,
                skip_preflight=False,
            )
            self.assertEqual(1, code)
            self.assertIn("tables but no current MediaFlow schema marker", stderr.getvalue())
            self.assertIn("file was not modified", stderr.getvalue())
            self.assertEqual(before, hashlib.sha256(database.read_bytes()).hexdigest())
            with sqlite3.connect(database) as connection:
                self.assertEqual(
                    [("notes",)],
                    connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                    ).fetchall(),
                )
                self.assertEqual(
                    [("n-1", "keep this note")],
                    connection.execute("SELECT note_id, body FROM notes").fetchall(),
                )

    def test_zero_table_sqlite_file_is_initialized_as_a_current_store(self) -> None:
        import sqlite3

        from mediaflow.infrastructure.sqlite_configuration_management import (
            SQLiteConfigurationRepository,
        )
        from mediaflow.infrastructure.sqlite_configuration_schema import (
            CONFIGURATION_SCHEMA_VERSION,
        )
        from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "empty.sqlite3")
            with sqlite3.connect(database) as connection:
                connection.execute("PRAGMA user_version = 1")
                connection.commit()
            self.assertGreater(database.stat().st_size, 0)
            with SQLiteConfigurationRepository(database):
                pass
            with SQLiteTaskRepository(database) as runtime:
                self.assertEqual(runtime.schema_version, SCHEMA_VERSION)
            with sqlite3.connect(database) as connection:
                self.assertEqual(
                    [
                        ("configuration_management", CONFIGURATION_SCHEMA_VERSION),
                        ("runtime", SCHEMA_VERSION),
                        ("store_origin", SCHEMA_VERSION),
                    ],
                    connection.execute(
                        "SELECT component, version FROM schema_version ORDER BY component"
                    ).fetchall(),
                )


class ConcurrentFirstInitializationTests(unittest.TestCase):
    """Four resident services may start against one empty data directory."""

    def test_empty_database_is_created_once_before_any_service_reads_it(self) -> None:
        import sqlite3
        import threading

        from mediaflow.infrastructure.sqlite_configuration_management import (
            SQLiteConfigurationRepository,
        )
        from mediaflow.infrastructure.sqlite_configuration_schema import (
            CONFIGURATION_SCHEMA_VERSION,
        )
        from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            barrier = threading.Barrier(4)
            failures: list[BaseException] = []

            def boot(index: int) -> None:
                try:
                    barrier.wait(5)
                    if index % 2:
                        with SQLiteConfigurationRepository(database):
                            pass
                        with SQLiteTaskRepository(database):
                            pass
                    else:
                        with SQLiteTaskRepository(database):
                            pass
                        with SQLiteConfigurationRepository(database):
                            pass
                except BaseException as error:  # pragma: no cover - reported below
                    failures.append(error)

            threads = [threading.Thread(target=boot, args=(index,)) for index in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(30)
            self.assertEqual([], failures)
            with sqlite3.connect(database) as connection:
                self.assertEqual(
                    [
                        ("configuration_management", CONFIGURATION_SCHEMA_VERSION),
                        ("runtime", SCHEMA_VERSION),
                        ("store_origin", SCHEMA_VERSION),
                    ],
                    connection.execute(
                        "SELECT component, version FROM schema_version ORDER BY component"
                    ).fetchall(),
                )
            with SQLiteTaskRepository(database) as runtime:
                self.assertEqual(runtime.schema_version, SCHEMA_VERSION)
            with SQLiteConfigurationRepository(database):
                pass


class ConfigurationPublicationTests(unittest.TestCase):
    """The current publication entrance keeps every configuration rule."""

    def _api(self, database: Path, bootstrap: dict):
        """One real API process shape over the deployment bootstrap."""

        from mediaflow.application.configuration_snapshot import ManagedConfigurationService
        from mediaflow.infrastructure.sqlite_configuration_management import (
            SQLiteConfigurationRepository,
        )
        from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository

        configuration_repository = SQLiteConfigurationRepository(database)
        runtime_repository = SQLiteTaskRepository(database)
        service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=str(database),
            bootstrap_document=bootstrap,
        )
        api = MediaFlowApi(
            runtime_repository,
            principals=(ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),),
            configuration_service=service,
            bootstrap_document=bootstrap,
        )

        class _Context:
            def __enter__(self):
                return api

            def __exit__(self, *_):
                configuration_repository.close()
                runtime_repository.close()
                return False

        return _Context()

    def _request(self, api, method: str, path: str, body: dict | None = None):
        raw = b"" if body is None else json.dumps(body).encode("utf-8")
        statuses: list[str] = []
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": "",
            "CONTENT_LENGTH": str(len(raw)),
            "CONTENT_TYPE": "application/json",
            "wsgi.input": io.BytesIO(raw),
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_AUTHORIZATION": "Bearer admin-token",
        }
        payload = b"".join(api(environ, lambda value, headers: statuses.append(value)))
        return int(statuses[0].split()[0]), json.loads(payload)

    def test_initialize_publish_checks_and_explicit_replacement(self) -> None:
        """The current configuration entrance keeps every publication rule.

        The retired CLI ``config initialize/publish`` pair is replaced by the
        System Settings/API publication surface the Web uses: an empty
        initialization, a checked publication that refuses missing Storage
        roots, an explicit replacement of an unavailable Active, and the store
        origin the first publication records.
        """

        from scripts.make_deployment_config import make_deployment_configuration

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "configuration.sqlite3"
            bootstrap = {
                "version": 1,
                "persistence": {"databasePath": str(database)},
            }
            with self._api(database, bootstrap) as api:
                status, initialized = self._request(api, "POST", "/api/configuration/initialize")
                self.assertEqual(201, status, initialized)
                self.assertTrue(initialized["initialized"])
                status, current = self._request(api, "GET", "/api/configuration")
                self.assertEqual(200, status, current)
                self.assertIsNotNone(current["active"])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "configuration.sqlite3"
            bootstrap = {
                "version": 1,
                "persistence": {"databasePath": str(database)},
            }
            document = make_deployment_configuration()
            document["storages"][0]["rootPath"] = str(root / "incoming")
            document["storages"][1]["rootPath"] = str(root / "organized")
            with self._api(database, bootstrap) as api:
                # Missing target roots are a real check failure, not a publication.
                status, failed = self._request(
                    api, "POST", "/api/configuration/publish", {"document": document}
                )
                self.assertGreaterEqual(status, 400, failed)
                status, current = self._request(api, "GET", "/api/configuration")
                self.assertIsNone(current["active"])

                (root / "incoming").mkdir()
                (root / "organized" / "Movies").mkdir(parents=True)
                (root / "organized" / "TV Shows").mkdir()
                status, published = self._request(
                    api, "POST", "/api/configuration/publish", {"document": document}
                )
                self.assertEqual(200, status, published)
                self.assertTrue(published["published"])
                status, current = self._request(api, "GET", "/api/configuration")
                self.assertEqual(current["active"]["revisionId"], published["revisionId"])

                # The first publication created the file and recorded this
                # build's origin; the runtime repository the API process owns
                # also recorded its own current schema marker.
                with sqlite3.connect(database) as connection:
                    markers = dict(
                        connection.execute(
                            "SELECT component, version FROM schema_version"
                        ).fetchall()
                    )
                self.assertEqual(markers["configuration_management"], CONFIGURATION_SCHEMA_VERSION)
                self.assertEqual(markers["store_origin"], SCHEMA_VERSION)
                self.assertEqual(markers.get("runtime"), SCHEMA_VERSION)

                # A corrupt/missing Active requires the explicit replacement flag.
                with sqlite3.connect(database) as connection:
                    connection.execute(
                        "DELETE FROM managed_configuration_revisions WHERE status='active'"
                    )
                status, refused = self._request(
                    api, "POST", "/api/configuration/publish", {"document": document}
                )
                self.assertGreaterEqual(status, 400, refused)
                status, current = self._request(api, "GET", "/api/configuration")
                self.assertIsNone(current["active"])
                status, replacement = self._request(
                    api,
                    "POST",
                    "/api/configuration/publish",
                    {"document": document, "replaceActive": True},
                )
                self.assertEqual(200, status, replacement)
                status, current = self._request(api, "GET", "/api/configuration")
                self.assertEqual(current["active"]["revisionId"], replacement["revisionId"])

    def test_retired_draft_commands_have_no_runtime_surface(self) -> None:
        """The retired Draft lifecycle commands and the CLI that carried them are gone."""

        for module in ("mediaflow.cli", "mediaflow.final_cli"):
            with self.subTest(module=module):
                with self.assertRaises(ModuleNotFoundError):
                    __import__(module)
