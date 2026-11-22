from __future__ import annotations

import io
import json
import os
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


class ConfigurationDraftRetirementTests(unittest.TestCase):
    def _seed_store(self, database: Path):
        import sqlite3

        from mediaflow.application.configuration_snapshot import ManagedConfigurationService
        from mediaflow.infrastructure.sqlite_configuration_management import (
            SQLiteConfigurationRepository,
        )

        document = example_document()
        document["persistence"]["databasePath"] = str(database)
        service = ManagedConfigurationService(
            SQLiteConfigurationRepository(database),
            bootstrap_database_path=str(database),
        )
        draft = service.import_draft(document, actor="tester")
        validated = service.validate(draft.revision_id, actor="tester")
        active = service.activate(
            validated.revision_id, expected_version=validated.version, actor="tester"
        )
        unpublished = service.import_draft(document, actor="tester")
        with sqlite3.connect(database) as connection:
            for revision in (active, unpublished):
                connection.execute(
                    "INSERT INTO managed_local_setup_checks "
                    "(revision_id, revision_version, revision_digest, status, checked_at, actor, "
                    "storage_ids, operations, duration_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        revision.revision_id,
                        revision.version,
                        revision.digest,
                        "passed",
                        "2026-11-20T00:00:00+00:00",
                        "tester",
                        "[]",
                        "[]",
                        1,
                    ),
                )
            connection.execute(
                "UPDATE schema_version SET version=11 WHERE component='configuration_management'"
            )
            # The seeded store was written by this build; a real previous build
            # at configuration schema 11 had no store origin marker.
            connection.execute("DELETE FROM schema_version WHERE component='store_origin'")
            connection.commit()
        service.repository.close()
        return active, unpublished

    def _bootstrap(self, root: Path, database: Path) -> Path:
        bootstrap = root / "bootstrap.json"
        bootstrap.write_text(
            json.dumps(
                {
                    "version": 1,
                    "persistence": {"databasePath": str(database)},
                    "api": {"principals": []},
                }
            ),
            encoding="utf-8",
        )
        return bootstrap

    def _run(self, bootstrap: Path, *arguments: str) -> tuple[int, str, str]:
        from mediaflow.final_cli import final_main

        stdout, stderr = io.StringIO(), io.StringIO()
        code = final_main(["--config", str(bootstrap), *arguments], stdout=stdout, stderr=stderr)
        return code, stdout.getvalue(), stderr.getvalue()

    def _schema_version(self, database: Path) -> int:
        import sqlite3

        with sqlite3.connect(database) as connection:
            return int(
                connection.execute(
                    "SELECT version FROM schema_version WHERE component='configuration_management'"
                ).fetchone()[0]
            )

    def test_status_lists_switch_scope_without_modifying_the_previous_store(self) -> None:
        import sqlite3

        from mediaflow.infrastructure.configuration_data_switch import (
            ConfigurationDataSwitchRequired,
        )
        from mediaflow.infrastructure.sqlite_configuration_management import (
            SQLiteConfigurationRepository,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "configuration.sqlite3"
            active, unpublished = self._seed_store(database)
            bootstrap = self._bootstrap(root, database)
            code, output, errors = self._run(bootstrap, "config", "status")
            self.assertEqual(code, 0, errors)
            status = json.loads(output)
            self.assertEqual(status["health"], "DATA_SWITCH_REQUIRED")
            self.assertFalse(status["managementReady"])
            switch = status["dataSwitch"]
            self.assertEqual(switch["state"], "PENDING")
            self.assertEqual(switch["configurationSchemaVersion"], 11)
            self.assertEqual(switch["targetConfigurationSchemaVersion"], 12)
            self.assertEqual(
                [item["revisionId"] for item in switch["affectedRevisions"]],
                [unpublished.revision_id],
            )
            self.assertEqual(switch["affectedRevisions"][0]["status"], "draft")
            self.assertIn(
                {"table": "managed_local_setup_checks", "rows": 1},
                switch["affectedRevisions"][0]["evidence"],
            )
            self.assertGreater(switch["auditRows"], 0)
            self.assertIn("retire-unpublished --confirm", switch["confirmation"])
            # Opening the normal repository must fail closed with the same
            # scope instead of silently switching the file.
            with self.assertRaises(ConfigurationDataSwitchRequired) as raised:
                SQLiteConfigurationRepository(database)
            self.assertIn(unpublished.revision_id, str(raised.exception))
            self.assertIn("was not modified", str(raised.exception))
            self.assertEqual(self._schema_version(database), 11)
            with sqlite3.connect(database) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT status FROM managed_configuration_revisions WHERE revision_id=?",
                        (unpublished.revision_id,),
                    ).fetchone()[0],
                    "draft",
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM managed_local_setup_checks WHERE revision_id=?",
                        (unpublished.revision_id,),
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM configuration_change_audits WHERE object_id=?",
                        (unpublished.revision_id,),
                    ).fetchone()[0],
                    int(switch["auditRows"]),
                )

    def test_confirmed_switch_retires_unpublished_rows_and_preserves_published_history(
        self,
    ) -> None:
        import sqlite3

        from mediaflow.infrastructure.sqlite_configuration_management import (
            SQLiteConfigurationRepository,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "configuration.sqlite3"
            active, unpublished = self._seed_store(database)
            bootstrap = self._bootstrap(root, database)
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "CREATE TABLE tasks (task_id TEXT PRIMARY KEY, status TEXT NOT NULL, "
                    "created_at TEXT NOT NULL, configuration_snapshot_id TEXT)"
                )
                connection.execute(
                    "INSERT INTO tasks VALUES (?, ?, ?, ?)",
                    (
                        "task-published",
                        "running",
                        "2026-11-20T00:00:00+00:00",
                        active.revision_id,
                    ),
                )
                connection.commit()
            code, output, errors = self._run(bootstrap, "config", "retire-unpublished", "--confirm")
            self.assertEqual(code, 0, errors)
            result = json.loads(output)
            self.assertTrue(result["switched"])
            self.assertEqual(result["configurationSchemaVersion"], 12)
            self.assertEqual(
                [item["revisionId"] for item in result["removedRevisions"]],
                [unpublished.revision_id],
            )
            self.assertEqual(result["active"]["revisionId"], active.revision_id)
            self.assertEqual(result["active"]["digest"], active.digest)
            self.assertEqual(self._schema_version(database), 12)
            with sqlite3.connect(database) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT version FROM schema_version WHERE component='store_origin'"
                    ).fetchone()[0],
                    SCHEMA_VERSION,
                )
                self.assertIsNone(
                    connection.execute(
                        "SELECT revision_id FROM managed_configuration_revisions "
                        "WHERE revision_id=?",
                        (unpublished.revision_id,),
                    ).fetchone()
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM managed_local_setup_checks WHERE revision_id=?",
                        (unpublished.revision_id,),
                    ).fetchone()[0],
                    0,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM configuration_change_audits WHERE object_id=?",
                        (unpublished.revision_id,),
                    ).fetchone()[0],
                    0,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM configuration_change_audits WHERE object_id=?",
                        (active.revision_id,),
                    ).fetchone()[0]
                    > 0,
                    True,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM managed_local_setup_checks WHERE revision_id=?",
                        (active.revision_id,),
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT configuration_snapshot_id FROM tasks WHERE task_id=?",
                        ("task-published",),
                    ).fetchone()[0],
                    active.revision_id,
                )
            # The same store now opens normally and reports only published
            # revisions, with the Active identity unchanged.
            with SQLiteConfigurationRepository(database) as repository:
                self.assertEqual(
                    [
                        (revision.revision_id, revision.status.value)
                        for revision in repository.list_revisions(limit=100)
                    ],
                    [(active.revision_id, "active")],
                )
                self.assertEqual(repository.get_active_revision().digest, active.digest)
                self.assertFalse(repository.list_revision_audits(active.revision_id) == ())
            code, output, errors = self._run(bootstrap, "config", "retire-unpublished", "--confirm")
            self.assertEqual(code, 0, errors)
            self.assertFalse(json.loads(output)["switched"])

    def test_switch_is_blocked_and_status_locates_a_pinned_admitted_task(self) -> None:
        import sqlite3

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "configuration.sqlite3"
            active, unpublished = self._seed_store(database)
            bootstrap = self._bootstrap(root, database)
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "CREATE TABLE tasks (task_id TEXT PRIMARY KEY, status TEXT NOT NULL, "
                    "created_at TEXT NOT NULL, configuration_snapshot_id TEXT)"
                )
                connection.execute(
                    "INSERT INTO tasks VALUES (?, ?, ?, ?)",
                    (
                        "task-pinned",
                        "running",
                        "2026-11-20T00:00:00+00:00",
                        unpublished.revision_id,
                    ),
                )
                connection.commit()
            code, output, errors = self._run(bootstrap, "config", "status")
            self.assertEqual(code, 0, errors)
            switch = json.loads(output)["dataSwitch"]
            self.assertEqual(switch["state"], "BLOCKED")
            self.assertEqual(
                [(item["taskId"], item["revisionId"]) for item in switch["pinnedTasks"]],
                [("task-pinned", unpublished.revision_id)],
            )
            code, output, errors = self._run(bootstrap, "config", "retire-unpublished", "--confirm")
            self.assertEqual(code, 2)
            self.assertIn("task-pinned", errors)
            self.assertEqual(json.loads(output)["switched"], False)
            self.assertEqual(self._schema_version(database), 11)
            with sqlite3.connect(database) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT status FROM managed_configuration_revisions WHERE revision_id=?",
                        (unpublished.revision_id,),
                    ).fetchone()[0],
                    "draft",
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT revision_id FROM managed_configuration_revisions "
                        "WHERE status='active'"
                    ).fetchone()[0],
                    active.revision_id,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM managed_local_setup_checks WHERE revision_id=?",
                        (unpublished.revision_id,),
                    ).fetchone()[0],
                    1,
                )

    def test_switch_failure_rolls_back_to_the_previous_store(self) -> None:
        import sqlite3

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "configuration.sqlite3"
            active, unpublished = self._seed_store(database)
            bootstrap = self._bootstrap(root, database)
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "CREATE TRIGGER reject_switch_evidence_delete "
                    "BEFORE DELETE ON managed_local_setup_checks "
                    "BEGIN SELECT RAISE(ABORT, 'simulated evidence delete failure'); END"
                )
                connection.commit()
            code, _, errors = self._run(bootstrap, "config", "retire-unpublished", "--confirm")
            self.assertEqual(code, 2)
            self.assertIn("simulated evidence delete failure", errors)
            self.assertEqual(self._schema_version(database), 11)
            with sqlite3.connect(database) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT status FROM managed_configuration_revisions WHERE revision_id=?",
                        (unpublished.revision_id,),
                    ).fetchone()[0],
                    "draft",
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM managed_local_setup_checks WHERE revision_id=?",
                        (unpublished.revision_id,),
                    ).fetchone()[0],
                    1,
                )
                connection.execute("DROP TRIGGER reject_switch_evidence_delete")
                connection.commit()
            code, output, errors = self._run(bootstrap, "config", "retire-unpublished", "--confirm")
            self.assertEqual(code, 0, errors)
            self.assertTrue(json.loads(output)["switched"])
            self.assertEqual(self._schema_version(database), 12)
            with sqlite3.connect(database) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT status FROM managed_configuration_revisions WHERE revision_id=?",
                        (unpublished.revision_id,),
                    ).fetchone(),
                    None,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT revision_id FROM managed_configuration_revisions "
                        "WHERE status='active'"
                    ).fetchone()[0],
                    active.revision_id,
                )

    def test_cli_initialize_publish_checks_and_explicit_replacement(self) -> None:
        from mediaflow.final_cli import final_main
        from scripts.make_deployment_config import make_deployment_configuration

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "configuration.sqlite3"
            bootstrap = root / "bootstrap.json"
            bootstrap.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "persistence": {"databasePath": str(database)},
                        "api": {"principals": []},
                    }
                ),
                encoding="utf-8",
            )

            def run(*arguments: str) -> tuple[int, str, str]:
                stdout, stderr = io.StringIO(), io.StringIO()
                code = final_main(
                    ["--config", str(bootstrap), *arguments],
                    stdout=stdout,
                    stderr=stderr,
                )
                return code, stdout.getvalue(), stderr.getvalue()

            def status() -> dict:
                code, output, errors = run("config", "status")
                self.assertEqual(code, 0, errors)
                return json.loads(output)

            code, output, errors = run("config", "initialize")
            self.assertEqual(code, 0, errors)
            self.assertTrue(json.loads(output)["initialized"])
            self.assertIsNotNone(status()["active"])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "configuration.sqlite3"
            bootstrap = root / "bootstrap.json"
            bootstrap.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "persistence": {"databasePath": str(database)},
                        "api": {"principals": []},
                    }
                ),
                encoding="utf-8",
            )
            activation = root / "activation.json"
            document = make_deployment_configuration()
            document["storages"][0]["rootPath"] = str(root / "incoming")
            document["storages"][1]["rootPath"] = str(root / "organized")
            activation.write_text(json.dumps(document), encoding="utf-8")

            def run(*arguments: str) -> tuple[int, str, str]:
                stdout, stderr = io.StringIO(), io.StringIO()
                code = final_main(
                    ["--config", str(bootstrap), *arguments],
                    stdout=stdout,
                    stderr=stderr,
                )
                return code, stdout.getvalue(), stderr.getvalue()

            def status() -> dict:
                code, output, errors = run("config", "status")
                self.assertEqual(code, 0, errors)
                return json.loads(output)

            # Missing target roots are a real check failure, not a publication.
            code, _, errors = run("config", "publish", "--file", str(activation))
            self.assertNotEqual(code, 0)
            self.assertIn("read-only Storage check did not pass", errors)
            self.assertIsNone(status()["active"])

            (root / "incoming").mkdir()
            (root / "organized" / "Movies").mkdir(parents=True)
            (root / "organized" / "TV Shows").mkdir()
            code, output, errors = run("config", "publish", "--file", str(activation))
            self.assertEqual(code, 0, errors)
            published = json.loads(output)
            self.assertTrue(published["published"])
            self.assertEqual(status()["active"]["revisionId"], published["revisionId"])
            # The first publication created the file and recorded this build's origin.
            import sqlite3

            with sqlite3.connect(database) as connection:
                self.assertEqual(
                    [
                        ("configuration_management", CONFIGURATION_SCHEMA_VERSION),
                        ("store_origin", SCHEMA_VERSION),
                    ],
                    connection.execute(
                        "SELECT component, version FROM schema_version ORDER BY component"
                    ).fetchall(),
                )

            # A corrupt/missing Active requires the explicit replacement flag.
            import sqlite3

            with sqlite3.connect(database) as connection:
                connection.execute(
                    "DELETE FROM managed_configuration_revisions WHERE status='active'"
                )
            code, _, errors = run("config", "publish", "--file", str(activation))
            self.assertNotEqual(code, 0)
            self.assertIn("explicit replacement", errors)
            self.assertIsNone(status()["active"])
            code, output, errors = run(
                "config", "publish", "--file", str(activation), "--replace-active"
            )
            self.assertEqual(code, 0, errors)
            replacement = json.loads(output)
            self.assertEqual(status()["active"]["revisionId"], replacement["revisionId"])

    def test_cli_retired_draft_commands_are_unknown_and_rejected(self) -> None:
        from mediaflow.final_cli import final_main

        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "bootstrap.json"
            config.write_text(json.dumps(example_document()), encoding="utf-8")
            for command in (
                ["--config", str(config), "config", "draft-import", "--file", str(config)],
                ["--config", str(config), "config", "draft-validate", "revision-1"],
                [
                    "--config",
                    str(config),
                    "config",
                    "activate",
                    "revision-1",
                    "--expected-version",
                    "1",
                ],
            ):
                with self.assertRaises(SystemExit) as raised:
                    final_main(command, stdout=io.StringIO(), stderr=io.StringIO())
                self.assertEqual(raised.exception.code, 2)
