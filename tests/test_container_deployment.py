from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from contextlib import ExitStack, closing
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.accounts import AccountService
from mediaflow.application.configuration_snapshot import (
    ManagedConfigurationService,
    build_first_setup_starter_document,
)
from mediaflow.container_entrypoint import (
    CONTAINER_API_PORT,
    container_preflight_errors,
    load_environment_file,
)
from mediaflow.container_entrypoint import main as entrypoint_main
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.runtime_configuration import (
    is_minimal_management_bootstrap,
    load_minimal_management_bootstrap,
)
from mediaflow.infrastructure.runtime_lease import RuntimeDatabaseLease, RuntimeLeaseMode
from mediaflow.infrastructure.sqlite_applicability import DatabaseApplicabilityError
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_configuration_schema import CONFIGURATION_SCHEMA_VERSION
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from mediaflow.resident_entry import main as resident_main
from scripts.make_deployment_config import (
    make_deployment_configuration,
    make_management_bootstrap,
)
from tests.managed_config_fixture import seed_configuration_schema_11_store

ROOT = Path(__file__).resolve().parents[1]


def run_service_entry(
    config: Path,
    data: Path,
    service: str,
    *,
    skip_preflight: bool = False,
    environment: dict[str, str] | None = None,
):
    """Run one fixed service entry against an isolated deployment."""

    output, error = io.StringIO(), io.StringIO()
    values = {
        "MEDIAFLOW_CONFIG": str(config),
        "MEDIAFLOW_DATA_DIR": str(data),
    }
    values.update(environment or {})
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, values, clear=False))
        if skip_preflight:
            stack.enter_context(
                patch("mediaflow.resident_entry.container_preflight_errors", return_value=[])
            )
        code = resident_main([service], stdout=output, stderr=error)
    return code, output.getvalue(), error.getvalue()


def compose_source_bind_mounts() -> dict[str, dict[str, str]]:
    """Read the shared bind declarations without depending on Compose normalization."""

    mounts = []
    current = None
    in_bind = False
    in_volumes = False
    for line in (ROOT / "compose.yaml").read_text(encoding="utf-8").splitlines():
        stripped = line.lstrip()
        indentation = len(line) - len(stripped)
        if indentation == 0:
            if stripped.startswith("x-mediaflow-volumes:"):
                in_volumes = True
                continue
            if in_volumes:
                break
        if not in_volumes or not stripped or stripped.startswith("#"):
            continue
        if indentation == 2 and stripped.startswith("- "):
            if current is not None:
                mounts.append(current)
            current = {}
            in_bind = False
            key, separator, value = stripped[2:].partition(":")
            if separator:
                current[key] = value.split(" #", 1)[0].strip()
            continue
        if current is None:
            continue
        if indentation == 4:
            if stripped == "bind:":
                in_bind = True
                continue
            in_bind = False
            destination = current
        elif indentation == 6 and in_bind:
            destination = current.setdefault("bind", {})
        else:
            continue
        key, separator, value = stripped.partition(":")
        if separator:
            destination[key] = value.split(" #", 1)[0].strip()
    if current is not None:
        mounts.append(current)
    return {
        mount["target"]: mount
        for mount in mounts
        if mount.get("type") == "bind" and "target" in mount
    }


def request(app, method: str, path: str, *, token: str | None = None):
    body = b""
    statuses = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": str(len(body)),
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(body),
    }
    if token is not None:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    response = b"".join(app(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(response)


class ProductionWsgiCliTests(unittest.TestCase):
    def test_service_start_takes_the_shared_lease_before_opening_the_store(self) -> None:
        """An occupied maintenance lease leaves an empty restore target empty.

        Resolving the API's Active opens the configuration repository, which
        creates tables and markers on an empty file.  The lease must therefore
        come first: an offline recovery holding the exclusive lease on an empty
        destination must see that destination stay empty when a service is
        started meanwhile, and the bounded message names the service to start
        again after the recovery finishes.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data"
            data.mkdir()
            database = data / "mediaflow.sqlite3"
            bootstrap = root / "mediaflow.json"
            bootstrap.write_text(
                json.dumps(make_management_bootstrap(database_path=str(database))),
                encoding="utf-8",
            )
            calls: list[tuple[str, int, int]] = []

            def fake_serve(_app, *, host, port, threads):
                calls.append((host, port, threads))

            with (
                RuntimeDatabaseLease(database, RuntimeLeaseMode.EXCLUSIVE),
                patch("mediaflow.production_wsgi.serve", side_effect=fake_serve),
            ):
                status, _, error_text = run_service_entry(bootstrap, data, "api")
            self.assertEqual(status, 2, error_text)
            self.assertIn("runtime database is in use", error_text)
            self.assertIn("start the api service again", error_text)
            self.assertFalse(database.exists())
            self.assertEqual(list(data.glob("mediaflow.sqlite3-*")), [])
            self.assertEqual(calls, [])

            # After the recovery releases the lease the same entry starts the
            # API, and the source listener configuration still applies there.
            with patch("mediaflow.production_wsgi.serve", side_effect=fake_serve):
                status, output, error_text = run_service_entry(
                    bootstrap,
                    data,
                    "api",
                    environment={
                        "MEDIAFLOW_API_HOST": "127.0.0.1",
                        "MEDIAFLOW_API_PORT": "8787",
                        "MEDIAFLOW_API_THREADS": "2",
                    },
                )
            self.assertEqual(status, 0, error_text)
            self.assertIn("listening on 127.0.0.1:8787", output)
            self.assertEqual(calls, [("127.0.0.1", 8787, 2)])
            self.assertTrue(database.exists())

    def test_production_serve_uses_waitress_adapter_and_shared_application(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = json.loads(
                (ROOT / "config" / "strategy.example.json").read_text(encoding="utf-8")
            )
            document["persistence"] = {"databasePath": str(root / "runtime.sqlite3")}
            config = root / "mediaflow.json"
            config.write_text(json.dumps(document), encoding="utf-8")
            calls = []

            def fake_serve(app, *, host, port, threads):
                calls.append((host, port, threads))
                status, health = request(app, "GET", "/health")
                self.assertEqual(status, 200)
                self.assertTrue(health["firstAdministratorRequired"])
                self.assertEqual(request(app, "GET", "/api/tasks")[0], 401)
                # The retired environment token is an explicit Authorization
                # credential and is rejected; it never falls back to an account.
                status, _ = request(
                    app,
                    "GET",
                    "/api/tasks",
                    token="production-secret",
                )
                self.assertEqual(status, 401)

            with (
                patch.dict(os.environ, {"MEDIAFLOW_API_TOKEN": "production-secret"}, clear=True),
                patch("mediaflow.production_wsgi.serve", side_effect=fake_serve),
                patch(
                    "wsgiref.simple_server.make_server",
                    side_effect=AssertionError("production command must not use wsgiref"),
                ),
            ):
                status, _, error_text = run_service_entry(
                    config,
                    root,
                    "api",
                    skip_preflight=True,
                    environment={"MEDIAFLOW_API_PORT": "8080", "MEDIAFLOW_API_THREADS": "8"},
                )
                self.assertIn("WARNING", error_text)
            self.assertEqual(status, 0)
            self.assertEqual(calls, [("0.0.0.0", 8080, 8)])

    def test_production_serve_rejects_invalid_threads_and_port(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = json.loads(
                (ROOT / "config" / "strategy.example.json").read_text(encoding="utf-8")
            )
            document["persistence"] = {"databasePath": str(root / "runtime.sqlite3")}
            config = root / "mediaflow.json"
            config.write_text(json.dumps(document), encoding="utf-8")
            with patch.dict(os.environ, {"MEDIAFLOW_API_TOKEN": "production-secret"}, clear=True):
                for extra in (("MEDIAFLOW_API_THREADS", "0"), ("MEDIAFLOW_API_THREADS", "65")):
                    with self.subTest(extra=extra):
                        name, value = extra
                        status, _, text = run_service_entry(
                            config,
                            root,
                            "api",
                            skip_preflight=True,
                            environment={name: value},
                        )
                        self.assertEqual(status, 2)
                        self.assertIn(name, text)


class ContainerEntrypointTests(unittest.TestCase):
    def test_valid_service_executes_only_the_fixed_resident_entry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, data, _ = ContainerPreflightTests._configuration(self, root)
            with (
                patch.dict(
                    os.environ,
                    {
                        "MEDIAFLOW_CONFIG": str(config),
                        "MEDIAFLOW_DATA_DIR": str(data),
                        "MEDIAFLOW_COMMAND": "/bin/true",
                    },
                    clear=False,
                ),
                patch("mediaflow.container_entrypoint.os.execvpe") as execute,
            ):
                code = entrypoint_main(["worker"])
        self.assertEqual(127, code)
        executable, arguments, _ = execute.call_args.args
        self.assertEqual(executable, os.sys.executable)
        self.assertEqual(arguments, [os.sys.executable, "-m", "mediaflow.resident_entry", "worker"])

    def test_invalid_services_retired_arguments_and_arbitrary_commands_are_rejected(self) -> None:
        cases = (
            [],
            ["api", "serve-production", "--host", "0.0.0.0", "--port", "8080"],
            ["worker", "run"],
            ["scheduler", "tick"],
            ["notification-worker", "run-next"],
            ["host", "not-an-operation"],
            ["python", "-m", "mediaflow.resident_entry", "api"],
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                with patch("mediaflow.container_entrypoint.os.execvpe") as execute:
                    code = entrypoint_main(arguments)
                self.assertEqual(1, code)
                execute.assert_not_called()

    def test_host_mode_executes_only_the_fixed_maintenance_entry(self) -> None:
        with patch("mediaflow.container_entrypoint.os.execvpe") as execute:
            code = entrypoint_main(["host", "verify", "/data/backup.sqlite3"])
        self.assertEqual(127, code)
        executable, arguments, _ = execute.call_args.args
        self.assertEqual(executable, os.sys.executable)
        self.assertEqual(
            arguments,
            [
                os.sys.executable,
                "-m",
                "mediaflow.host_operations",
                "verify",
                "/data/backup.sqlite3",
            ],
        )

    def test_general_cli_modules_are_absent_from_the_runtime(self) -> None:
        """RO-4: the general CLI is retired with its dispatches.

        Service, account and database commands have their own fixed entrances
        (resident entry and host operations), so the old general CLI must not
        even be importable — there is no dispatch layer left to reject a
        command at.
        """

        for module in ("mediaflow.cli", "mediaflow.final_cli"):
            with self.subTest(module=module):
                with self.assertRaises(ModuleNotFoundError):
                    __import__(module)


class ContainerPreflightTests(unittest.TestCase):
    def test_deployment_environment_cannot_move_the_container_listener_port(self) -> None:
        """The listener, Compose mapping and probe share the container port.

        The mounted deployment environment is shared by all four services and
        cannot change where the container API listens: the host port is a
        Compose project decision.  The same three names remain the listener
        configuration of a source installation, which has no Compose mapping.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, data, _ = self._configuration(root)
            for name, value in (
                ("MEDIAFLOW_API_HOST", "127.0.0.1"),
                ("MEDIAFLOW_API_PORT", "9000"),
                ("MEDIAFLOW_API_THREADS", "8"),
            ):
                with self.subTest(name=name):
                    errors = container_preflight_errors(
                        str(config),
                        str(data),
                        environ={name: value},
                        container=True,
                        service="api",
                    )
                    joined = "\n".join(errors)
                    self.assertIn(name, joined)
                    self.assertIn(f"always listens on port {CONTAINER_API_PORT}", joined)
                    self.assertIn("MEDIAFLOW_API_PORT in the Compose project", joined)
                    # The source listener setting is not a container setting.
                    self.assertEqual(
                        container_preflight_errors(
                            str(config), str(data), environ={name: value}, service="api"
                        ),
                        [],
                    )

            environment_file = root / "deployment.env"
            environment_file.write_text("MEDIAFLOW_API_PORT=9000\n", encoding="utf-8")
            error_text = io.StringIO()
            with (
                patch.dict(
                    os.environ,
                    {
                        "MEDIAFLOW_CONFIG": str(config),
                        "MEDIAFLOW_DATA_DIR": str(data),
                        "MEDIAFLOW_ENV_FILE": str(environment_file),
                    },
                    clear=False,
                ),
                patch("mediaflow.container_entrypoint.os.execvpe") as execute,
                patch("sys.stderr", error_text),
            ):
                code = entrypoint_main(["api"])
            self.assertEqual(1, code)
            execute.assert_not_called()
            self.assertIn("MEDIAFLOW_API_PORT", error_text.getvalue())
            self.assertIn(f"always listens on port {CONTAINER_API_PORT}", error_text.getvalue())

    def test_compose_listener_mapping_and_probe_share_the_container_port(self) -> None:
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        api = compose.split("\n  api:\n", 1)[1].split("\n  worker:\n", 1)[0]
        self.assertIn(f"http://127.0.0.1:{CONTAINER_API_PORT}/health", api)
        self.assertIn(
            f'"${{MEDIAFLOW_API_BIND:-127.0.0.1}}:${{MEDIAFLOW_API_PORT:-{CONTAINER_API_PORT}}}'
            f':{CONTAINER_API_PORT}"',
            api,
        )
        self.assertNotIn("MEDIAFLOW_API_HOST", api)
        self.assertNotIn("MEDIAFLOW_API_THREADS", api)

    def _configuration(self, root: Path) -> tuple[Path, Path, Path]:
        data = root / "data"
        incoming = root / "incoming"
        organized = root / "organized"
        data.mkdir()
        incoming.mkdir()
        organized.mkdir()
        config = root / "mediaflow.json"
        document = {
            "version": 1,
            "historyPath": str(data / "history.jsonl"),
            "persistence": {"databasePath": str(data / "mediaflow.sqlite3")},
            "storages": [
                {"id": "source", "type": "local", "rootPath": str(incoming), "readOnly": True},
                {
                    "id": "target",
                    "type": "local",
                    "rootPath": str(organized),
                    "readOnly": False,
                },
            ],
        }
        config.write_text(json.dumps(document), encoding="utf-8")
        return config, data, incoming

    def test_valid_container_paths_pass_and_missing_paths_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, data, incoming = self._configuration(root)
            environment = {"MEDIAFLOW_API_TOKEN": "deployment-secret"}
            self.assertEqual(
                container_preflight_errors(
                    str(config),
                    str(data),
                    environ=environment,
                    service="api",
                ),
                [],
            )
            incoming.rmdir()
            errors = container_preflight_errors(
                str(config),
                str(data),
                environ=environment,
                service="api",
            )
            self.assertTrue(any("media mount is missing" in error for error in errors))

    def test_preflight_rejects_unsafe_data_and_media_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, data, _ = self._configuration(root)
            outside = root / "outside"
            outside.mkdir()
            outside_document = json.loads(config.read_text(encoding="utf-8"))
            outside_document["persistence"] = {"databasePath": str(outside / "runtime.sqlite3")}
            config.write_text(json.dumps(outside_document), encoding="utf-8")
            errors = container_preflight_errors(
                str(config),
                str(data),
                environ={"MEDIAFLOW_API_TOKEN": "deployment-secret"},
            )
            self.assertTrue(any("persistence volume" in error for error in errors))

            unsafe_document = json.loads(config.read_text(encoding="utf-8"))
            unsafe_document["persistence"] = {"databasePath": str(data / "state.sqlite3")}
            unsafe_document["storages"][0]["rootPath"] = "/"
            config.write_text(json.dumps(unsafe_document), encoding="utf-8")
            errors = container_preflight_errors(
                str(config),
                str(data),
                environ={"MEDIAFLOW_API_TOKEN": "deployment-secret"},
            )
            self.assertTrue(any("unsupported" in error for error in errors))

    def test_retired_api_identity_and_unsupported_database_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, data, _ = self._configuration(root)
            document = json.loads(config.read_text(encoding="utf-8"))
            document["api"] = {
                "principals": [
                    {"id": "admin", "tokenEnv": "MEDIAFLOW_API_TOKEN", "roles": ["admin"]}
                ]
            }
            config.write_text(json.dumps(document), encoding="utf-8")
            errors = container_preflight_errors(
                str(config),
                str(data),
                environ={"MEDIAFLOW_API_TOKEN": "deployment-secret"},
                service="api",
            )
            self.assertTrue(any("api.principals is retired" in error for error in errors))
            self.assertTrue(
                any("issue-setup-code" in error for error in errors),
                errors,
            )
            self.assertFalse(any("deployment-secret" in error for error in errors))

            retired_reference = json.loads(config.read_text(encoding="utf-8"))
            retired_reference["api"] = {"tokenEnv": "MEDIAFLOW_API_TOKEN"}
            config.write_text(json.dumps(retired_reference), encoding="utf-8")
            errors = container_preflight_errors(str(config), str(data), environ={})
            self.assertTrue(any("api.tokenEnv is retired" in error for error in errors))

            # A foreign SQLite file is refused before any MediaFlow table is
            # added, and the original bytes remain intact.
            unsupported = Path(data, "mediaflow.sqlite3")
            unsupported.write_bytes(b"not a database")
            original = unsupported.read_bytes()
            clean = json.loads(config.read_text(encoding="utf-8"))
            clean.pop("api", None)
            config.write_text(json.dumps(clean), encoding="utf-8")
            errors = container_preflight_errors(str(config), str(data), environ={})
            self.assertTrue(
                any("not usable by this MediaFlow version" in error for error in errors)
            )
            self.assertEqual(original, unsupported.read_bytes())

    def test_previous_runtime_database_is_refused_before_startup_without_modification(self) -> None:
        """A database created by another MediaFlow version is never opened or upgraded.

        The previous release left a runtime marker, Task/configuration tables
        and no account tables.  Startup and the repository boundary must stop
        before creating or rewriting anything, keep the file byte-for-byte
        unchanged, and name the new-empty-directory recovery path.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, data, _ = self._configuration(root)
            database = data / "mediaflow.sqlite3"
            with SQLiteTaskRepository(database) as repository:
                service = AccountService(repository)
                code, _ = service.issue_first_admin_code()
                service.bootstrap(
                    code=code,
                    username="admin",
                    password="previous-release-password",
                    remember=False,
                )
            with closing(sqlite3.connect(database)) as connection:
                for table in (
                    "account_auth_audit",
                    "account_one_time_codes",
                    "account_sessions",
                    "accounts",
                ):
                    connection.execute(f"DROP TABLE {table}")
                connection.execute(
                    "UPDATE schema_version SET version=? WHERE component='runtime'",
                    (SCHEMA_VERSION - 1,),
                )
                connection.commit()
            before_hash = hashlib.sha256(database.read_bytes()).hexdigest()
            with closing(sqlite3.connect(database)) as connection:
                before_tables = [
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                    ).fetchall()
                ]
                before_marker = connection.execute(
                    "SELECT version FROM schema_version WHERE component='runtime'"
                ).fetchone()[0]
            self.assertEqual(SCHEMA_VERSION - 1, before_marker)

            errors = container_preflight_errors(
                str(config),
                str(data),
                environ={},
                service="api",
            )
            self.assertTrue(any("previous MediaFlow version" in error for error in errors), errors)
            self.assertTrue(any("new empty data directory" in error for error in errors), errors)
            self.assertFalse(any("previous-release-password" in error for error in errors))
            self.assertEqual(before_hash, hashlib.sha256(database.read_bytes()).hexdigest())

            with self.assertRaises(DatabaseApplicabilityError) as refused:
                SQLiteTaskRepository(database)
            self.assertIn("previous MediaFlow version", str(refused.exception))
            self.assertEqual(before_hash, hashlib.sha256(database.read_bytes()).hexdigest())
            with self.assertRaises(DatabaseApplicabilityError) as refused_configuration:
                SQLiteConfigurationRepository(database)
            self.assertIn("previous MediaFlow version", str(refused_configuration.exception))
            self.assertEqual(before_hash, hashlib.sha256(database.read_bytes()).hexdigest())

            status, _, stderr = run_service_entry(config, data, "api")
            self.assertEqual(1, status)
            self.assertIn("previous MediaFlow version", stderr)
            self.assertIn("new empty data directory", stderr)
            self.assertEqual(before_hash, hashlib.sha256(database.read_bytes()).hexdigest())
            with closing(sqlite3.connect(database)) as connection:
                self.assertEqual(
                    before_tables,
                    [
                        row[0]
                        for row in connection.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                        ).fetchall()
                    ],
                )
                self.assertEqual(
                    before_marker,
                    connection.execute(
                        "SELECT version FROM schema_version WHERE component='runtime'"
                    ).fetchone()[0],
                )

    def test_configuration_only_store_from_previous_version_is_refused_before_startup(self) -> None:
        """A previous build's configuration-only store is never adopted or upgraded.

        The configuration layout has not changed, so the previous build's
        ``config initialize`` left the current configuration marker but no
        ``store_origin`` record.  Startup must refuse that file before any
        runtime table or marker is created and keep its bytes unchanged.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data"
            data.mkdir()
            database = data / "mediaflow.sqlite3"
            bootstrap = root / "mediaflow.json"
            bootstrap.write_text(
                json.dumps(make_management_bootstrap(database_path=str(database))),
                encoding="utf-8",
            )
            bootstrap_document = json.loads(bootstrap.read_text(encoding="utf-8"))
            with SQLiteConfigurationRepository(database) as repository:
                service = ManagedConfigurationService(
                    repository,
                    bootstrap_database_path=str(database),
                    bootstrap_document=bootstrap_document,
                )
                service.publish_document(
                    build_first_setup_starter_document(
                        load_minimal_management_bootstrap(bootstrap_document)
                    ),
                    actor="tester",
                )
            # The previous build wrote the same configuration tables and marker
            # but never the current build's creation record.
            with closing(sqlite3.connect(database)) as connection:
                connection.execute("DELETE FROM schema_version WHERE component='store_origin'")
                connection.commit()
            before_hash = hashlib.sha256(database.read_bytes()).hexdigest()
            with closing(sqlite3.connect(database)) as connection:
                before_tables = [
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                    ).fetchall()
                ]
                before_markers = connection.execute(
                    "SELECT component, version FROM schema_version ORDER BY component"
                ).fetchall()

            errors = container_preflight_errors(
                str(bootstrap),
                str(data),
                environ={},
                service="api",
            )
            self.assertTrue(
                any(
                    "configuration-only database created by a previous MediaFlow version" in error
                    for error in errors
                ),
                errors,
            )
            self.assertTrue(any("new empty data directory" in error for error in errors), errors)
            self.assertEqual(before_hash, hashlib.sha256(database.read_bytes()).hexdigest())

            with self.assertRaises(DatabaseApplicabilityError) as refused:
                SQLiteTaskRepository(database)
            self.assertIn("configuration-only database", str(refused.exception))
            self.assertEqual(before_hash, hashlib.sha256(database.read_bytes()).hexdigest())

            status, _, stderr = run_service_entry(bootstrap, data, "api")
            self.assertEqual(1, status)
            self.assertIn("configuration-only database created by a previous", stderr)
            self.assertIn("new empty data directory", stderr)
            self.assertEqual(before_hash, hashlib.sha256(database.read_bytes()).hexdigest())
            with closing(sqlite3.connect(database)) as connection:
                self.assertEqual(
                    before_tables,
                    [
                        row[0]
                        for row in connection.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                        ).fetchall()
                    ],
                )
                self.assertEqual(
                    before_markers,
                    connection.execute(
                        "SELECT component, version FROM schema_version ORDER BY component"
                    ).fetchall(),
                )

    def test_previous_configuration_schema_store_is_refused_before_services_start(self) -> None:
        """A previous build's schema 11 store is not adopted by a service start.

        A previous build left a configuration schema 11 store with unpublished
        rows and no current store origin marker.  The schema 11 switch is
        retired, so the four service commands stop in preflight before the
        runtime repository can add a runtime schema/origin marker; the bounded
        refusal names the versions and the supported next steps.  The original
        bytes stay unchanged.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data"
            data.mkdir()
            database = data / "mediaflow.sqlite3"
            document = json.loads(
                (ROOT / "config" / "strategy.example.json").read_text(encoding="utf-8")
            )
            document["persistence"] = {"databasePath": str(database)}
            seed_configuration_schema_11_store(document)
            bootstrap = root / "mediaflow.json"
            bootstrap.write_text(
                json.dumps(make_management_bootstrap(database_path=str(database))),
                encoding="utf-8",
            )
            before_hash = hashlib.sha256(database.read_bytes()).hexdigest()
            with closing(sqlite3.connect(database)) as connection:
                before_markers = connection.execute(
                    "SELECT component, version FROM schema_version ORDER BY component"
                ).fetchall()
            self.assertEqual(
                [("configuration_management", 11)],
                before_markers,
            )

            for command in (
                "api",
                "worker",
                "scheduler",
                "notification-worker",
            ):
                with self.subTest(command=command):
                    errors = container_preflight_errors(
                        str(bootstrap),
                        str(data),
                        environ={},
                        service=command,
                    )
                    joined = "\n".join(errors)
                    self.assertIn(
                        "configuration schema was created by a previous MediaFlow version", joined
                    )
                    self.assertIn("found 11, expected 12", joined)
                    self.assertIn("new empty data directory", joined)
                    self.assertEqual(
                        before_hash, hashlib.sha256(database.read_bytes()).hexdigest(), command
                    )
                    with closing(sqlite3.connect(database)) as connection:
                        self.assertEqual(
                            before_markers,
                            connection.execute(
                                "SELECT component, version FROM schema_version ORDER BY component"
                            ).fetchall(),
                        )

            # The host maintenance entrances make the same refusal before any
            # write: an offline backup of a store this version cannot use stays
            # impossible, and the operator's file is preserved.
            errors = container_preflight_errors(
                str(bootstrap),
                str(data),
                environ={},
                service=None,
            )
            self.assertEqual(
                1,
                len(errors),
                errors,
            )

    def test_current_configuration_only_store_reads_active_before_accounts_survive_restart(
        self,
    ) -> None:
        """This build's configuration-only store starts, becomes an account store and reopens."""

        class Server:
            app = None

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def serve_forever(self):
                return None

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data"
            data.mkdir()
            database = data / "mediaflow.sqlite3"
            bootstrap = root / "mediaflow.json"
            bootstrap.write_text(
                json.dumps(make_management_bootstrap(database_path=str(database))),
                encoding="utf-8",
            )
            bootstrap_document = json.loads(bootstrap.read_text(encoding="utf-8"))
            with SQLiteConfigurationRepository(database) as repository:
                service = ManagedConfigurationService(
                    repository,
                    bootstrap_database_path=str(database),
                    bootstrap_document=bootstrap_document,
                    management_only=is_minimal_management_bootstrap(bootstrap_document),
                )
                revision = service.publish_document(
                    build_first_setup_starter_document(
                        load_minimal_management_bootstrap(bootstrap_document)
                    ),
                    actor="tester",
                )
                initialized = revision.summary()
            with closing(sqlite3.connect(database)) as connection:
                self.assertEqual(
                    [
                        ("configuration_management", CONFIGURATION_SCHEMA_VERSION),
                        ("store_origin", SCHEMA_VERSION),
                    ],
                    connection.execute(
                        "SELECT component, version FROM schema_version ORDER BY component"
                    ).fetchall(),
                )
            self.assertEqual(
                [],
                container_preflight_errors(
                    str(bootstrap),
                    str(data),
                    environ={},
                    service="api",
                ),
            )

            server = Server()

            def make_server(app, *, host, port, threads):
                server.app = app
                return server

            with patch("mediaflow.production_wsgi.serve", side_effect=make_server):
                code, _, error_text = run_service_entry(bootstrap, data, "api")
            self.assertEqual(0, code, error_text)
            self.assertIsNotNone(server.app)
            system_status = server.app._system_status.as_document()["system"]
            self.assertTrue(system_status["configuration_valid"])

            with SQLiteTaskRepository(database) as repository:
                service = AccountService(repository)
                setup_code, _ = service.issue_first_admin_code()
                service.bootstrap(
                    code=setup_code,
                    username="admin",
                    password="current-release-password",
                    remember=False,
                )

            # Restart: both stores reopen without rewriting the origin or Active.
            with SQLiteTaskRepository(database) as reopened:
                self.assertEqual(SCHEMA_VERSION, reopened.schema_version)
                self.assertEqual(1, reopened.count_accounts())
            with SQLiteConfigurationRepository(database) as reopened:
                stored = reopened.get_active_revision()
                self.assertIsNotNone(stored)
                self.assertEqual(initialized["revisionId"], stored.revision_id)

    def test_empty_and_current_version_stores_pass_startup_and_same_version_restart(self) -> None:
        """A fresh empty store and a current store with an account and Active survive restart."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, data, _ = self._configuration(root)
            database = data / "mediaflow.sqlite3"
            self.assertEqual(
                container_preflight_errors(
                    str(config),
                    str(data),
                    environ={},
                    service="api",
                ),
                [],
            )

            with SQLiteTaskRepository(database) as repository:
                service = AccountService(repository)
                code, _ = service.issue_first_admin_code()
                service.bootstrap(
                    code=code,
                    username="admin",
                    password="current-release-password",
                    remember=False,
                )
            bootstrap = {
                "version": 1,
                "persistence": {"databasePath": str(database)},
            }
            with SQLiteConfigurationRepository(database) as repository:
                service = ManagedConfigurationService(
                    repository,
                    bootstrap_database_path=str(database),
                    bootstrap_document=bootstrap,
                    management_only=True,
                )
                active = service.publish_document(
                    build_first_setup_starter_document(
                        load_minimal_management_bootstrap(bootstrap)
                    ),
                    actor="tester",
                )

            self.assertEqual(
                container_preflight_errors(
                    str(config),
                    str(data),
                    environ={},
                    service="api",
                ),
                [],
            )
            with SQLiteTaskRepository(database) as reopened:
                self.assertEqual(SCHEMA_VERSION, reopened.schema_version)
                self.assertEqual(1, reopened.count_accounts())
                self.assertEqual((), reopened.list_tasks())
            with SQLiteConfigurationRepository(database) as reopened:
                stored = reopened.get_active_revision()
                self.assertIsNotNone(stored)
                self.assertEqual(active.revision_id, stored.revision_id)

    def test_environment_file_parsing_is_bounded_and_never_echoes_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "deployment.env")
            path.write_text(
                "# comment\n"
                "export MEDIAFLOW_API_TOKEN='quoted-secret'\n"
                'MEDIAFLOW_WEBHOOK_SECRET="webhook-secret"\n'
                "EMPTY=\n",
                encoding="utf-8",
            )
            values = load_environment_file(str(path))
            self.assertEqual(values["MEDIAFLOW_API_TOKEN"], "quoted-secret")
            self.assertEqual(values["MEDIAFLOW_WEBHOOK_SECRET"], "webhook-secret")
            self.assertEqual(values["EMPTY"], "")


def _deployment_api(database: str, bootstrap: dict):
    """One real API process shape over the generated deployment bootstrap."""

    from mediaflow.application.configuration_snapshot import ManagedConfigurationService

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


def _api_json(
    api,
    path: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    token: str = "admin-token",
) -> tuple[int, dict]:
    import urllib.parse

    statuses: list[str] = []
    payload = json.dumps(body).encode("utf-8") if body is not None else b""
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": urllib.parse.urlencode({}),
        "CONTENT_LENGTH": str(len(payload)),
        "CONTENT_TYPE": "application/json",
        "wsgi.input": io.BytesIO(payload),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
    }
    raw = b"".join(api(environ, lambda value, headers: statuses.append(value)))
    return int(statuses[0].split()[0]), json.loads(raw)


class ContainerArtifactTests(unittest.TestCase):
    def test_dockerfile_build_context_is_bounded_and_non_root(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("FROM python:3.13-slim", dockerfile)
        self.assertIn('VOLUME ["/data"]', dockerfile)
        self.assertIn('ENTRYPOINT ["python", "-m", "mediaflow.container_entrypoint"]', dockerfile)
        self.assertIn('USER "${MEDIAFLOW_UID}:${MEDIAFLOW_GID}"', dockerfile)
        self.assertNotIn("COPY . .", dockerfile)
        self.assertNotIn("COPY config", dockerfile)
        self.assertNotIn("tests", dockerfile)
        self.assertNotIn("ffmpeg", dockerfile.casefold())

        ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        for required in (
            ".git",
            ".venv",
            "config",
            "config/alist.json",
            "config/strategy.json",
            "config/mediaflow.json",
            ".mediaflow",
            "tests",
            "docs",
            "Task",
            "dist",
        ):
            self.assertIn(required, ignore)

    def test_dockerfile_multi_stage_builds_v2_artifact_into_python_runtime(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        stages = [line.strip() for line in dockerfile.splitlines() if line.startswith("FROM ")]
        self.assertEqual(
            stages,
            ["FROM node:22-bookworm-slim AS web-build", "FROM python:3.13-slim"],
            dockerfile,
        )
        self.assertIn("COPY web/package.json web/package-lock.json ./", dockerfile)
        self.assertIn("RUN npm ci --no-audit --no-fund", dockerfile)
        self.assertIn("RUN npm run build", dockerfile)
        self.assertIn("test -f dist/index.html", dockerfile)
        self.assertIn("COPY --from=web-build /build/web/dist /opt/mediaflow/web/dist", dockerfile)
        self.assertIn(
            "MEDIAFLOW_UI_V2_ASSET_ROOT=/opt/mediaflow/web/dist",
            dockerfile,
            "the runtime image must bind the static-serving root to the built artifact",
        )
        final_stage = dockerfile.split("FROM python:3.13-slim", 1)[1]
        self.assertNotIn("npm", final_stage)
        self.assertNotIn("node_modules", final_stage)
        self.assertNotRegex(final_stage, r"\bnode\b", "the runtime stage must not use Node")
        self.assertNotIn("COPY web", final_stage)

    def test_compose_serves_v2_from_the_image_without_host_web_bind(self) -> None:
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        self.assertNotIn("web/dist", compose)
        self.assertNotIn("MEDIAFLOW_UI_V2_ASSET_ROOT", compose)
        self.assertNotIn("node", compose.casefold())

    def test_deployment_config_helper_is_container_shaped_and_secret_free(self) -> None:
        document = make_deployment_configuration()
        rendered = json.dumps(document, ensure_ascii=False)
        # Deployment startup authority stays with the generated bootstrap; the
        # input is the same portable document the managed export produces, so
        # importing it binds the receiving deployment's own locator/identity.
        self.assertNotIn("persistence", document)
        self.assertNotIn("_examples", document)
        self.assertNotIn("principals", document.get("api", {}))
        self.assertEqual(document["historyPath"], "/data/history.jsonl")
        self.assertEqual(document["storages"][0]["rootPath"], "/media/incoming")
        self.assertEqual(document["storages"][1]["rootPath"], "/media/organized")
        self.assertNotIn("MEDIAFLOW_API_TOKEN=", rendered)
        self.assertNotIn("Bearer", rendered)
        self.assertNotIn("schedules", document["automation"])

    def test_generated_bootstrap_and_configuration_input_import_as_generated(self) -> None:
        """The documented generated pair imports without rewriting identities.

        An operator runs the deployment helper once, starts the management
        bootstrap and imports the second file as produced.  The bootstrap
        carries no API identity, so the rendering may never carry the
        example's unrelated principal identity.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = str(root / "runtime.sqlite3")
            bootstrap_path = root / "mediaflow.json"
            configuration_path = root / "mediaflow.activation.json"
            subprocess.check_output(
                [
                    os.sys.executable,
                    str(ROOT / "scripts" / "make_deployment_config.py"),
                    "--output",
                    str(bootstrap_path),
                    "--configuration-output",
                    str(configuration_path),
                ],
                cwd=ROOT,
                text=True,
            )
            bootstrap = json.loads(bootstrap_path.read_text(encoding="utf-8"))
            self.assertNotIn("api", bootstrap)
            self.assertNotIn("principals", bootstrap)
            # The deployment owns the durable locator, so only the
            # bootstrap is pointed at this isolated database.
            bootstrap["persistence"] = {"databasePath": database}
            bootstrap_path.write_text(json.dumps(bootstrap, ensure_ascii=False), encoding="utf-8")
            # Local publications run the same read-only Storage and
            # destination checks as the Web form; point the generated
            # media input at this test's existing temporary roots.
            configuration = json.loads(configuration_path.read_text(encoding="utf-8"))
            configuration["storages"][0]["rootPath"] = str(root / "incoming")
            configuration["storages"][1]["rootPath"] = str(root / "organized")
            (root / "incoming").mkdir()
            (root / "organized" / "Movies").mkdir(parents=True)
            (root / "organized" / "TV Shows").mkdir()
            configuration_path.write_text(
                json.dumps(configuration, ensure_ascii=False), encoding="utf-8"
            )

            with _deployment_api(database, bootstrap) as api:
                status, published = _api_json(
                    api,
                    "/api/configuration/publish",
                    method="POST",
                    body={"document": configuration},
                )
            self.assertEqual(status, 200, published)
            self.assertEqual(published["status"], "active")
            self.assertTrue(published["published"])

    def test_openlist_example_imports_through_documented_first_setup(self) -> None:
        """The shipped OpenList object can be imported with the generated input.

        An administrator copies ``_examples.storages.openlist`` into
        the generated ``mediaflow.activation.json`` and publishes it with
        ``config publish --file``. The retired top-level connection spelling
        is rejected before publication with a message pointing to
        ``Storage.options``. The same instance then accepts the
        corrected input, keeps the two standard Storages and the example's
        original rootPath/readOnly/token reference, and publishes exactly one
        Active revision.  The OpenList Storage is not referenced by a library,
        so publication does not contact its unresolvable example address.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = str(root / "runtime.sqlite3")
            bootstrap_path = root / "mediaflow.json"
            configuration_path = root / "mediaflow.activation.json"
            subprocess.check_output(
                [
                    os.sys.executable,
                    str(ROOT / "scripts" / "make_deployment_config.py"),
                    "--output",
                    str(bootstrap_path),
                    "--configuration-output",
                    str(configuration_path),
                ],
                cwd=ROOT,
                text=True,
            )
            bootstrap = json.loads(bootstrap_path.read_text(encoding="utf-8"))
            bootstrap["persistence"] = {"databasePath": database}
            bootstrap_path.write_text(json.dumps(bootstrap, ensure_ascii=False), encoding="utf-8")
            example = json.loads(
                (ROOT / "config" / "strategy.example.json").read_text(encoding="utf-8")
            )["_examples"]["storages"]["openlist"]
            deployment = json.loads(configuration_path.read_text(encoding="utf-8"))
            deployment["storages"][0]["rootPath"] = str(root / "incoming")
            deployment["storages"][1]["rootPath"] = str(root / "organized")
            (root / "incoming").mkdir()
            (root / "organized" / "Movies").mkdir(parents=True)
            (root / "organized" / "TV Shows").mkdir()
            configuration_path.write_text(
                json.dumps(deployment, ensure_ascii=False), encoding="utf-8"
            )

            def candidate_with(storage: dict) -> dict:
                document = json.loads(configuration_path.read_text(encoding="utf-8"))
                document["storages"] = [*document["storages"], storage]
                return document

            with _deployment_api(database, bootstrap) as api:
                # The retired spelling must fail closed with the exact correction.
                retired = dict(example)
                retired.update(retired.pop("options"))
                code, error = _api_json(
                    api,
                    "/api/configuration/publish",
                    method="POST",
                    body={"document": candidate_with(retired)},
                )
                self.assertEqual(code, 400, error)
                self.assertIn(
                    "storages[openlist-example].baseUrl is retired",
                    error["error"]["message"],
                )
                self.assertIn("Storage.options", error["error"]["message"])
                code, failed = _api_json(api, "/api/configuration")
                self.assertEqual(code, 200, failed)
                self.assertTrue(failed["setupRequired"])
                self.assertIsNone(failed["active"])
                self.assertEqual(failed["revisions"], [])

                # The corrected shipped shape continues on the same instance.
                code, imported = _api_json(
                    api,
                    "/api/configuration/publish",
                    method="POST",
                    body={"document": candidate_with(example)},
                )
                self.assertEqual(code, 200, imported)
                self.assertEqual(imported["status"], "active")
                code, staged = _api_json(api, "/api/configuration")
                self.assertEqual(code, 200, staged)
                self.assertFalse(staged["setupRequired"])
                self.assertEqual(staged["active"]["revisionId"], imported["revisionId"])
                self.assertEqual(
                    [item["revisionId"] for item in staged["revisions"]],
                    [imported["revisionId"]],
                )
                self.assertEqual(staged["revisions"][0]["status"], "active")

                # The direct publication is the current runtime authority.
                self.assertEqual(staged["active"]["revisionId"], imported["revisionId"])

            # The persisted Draft keeps the example's own values verbatim.
            connection = sqlite3.connect(database)
            try:
                payloads = [
                    json.loads(row[0])
                    for row in connection.execute(
                        "SELECT payload FROM managed_configuration_revisions"
                    )
                ]
            finally:
                connection.close()
            self.assertEqual(len(payloads), 1)
            storages = payloads[0]["storages"]
            self.assertEqual(
                storages,
                [*deployment["storages"], example],
            )
            self.assertEqual(storages[0]["rootPath"], str(root / "incoming"))
            self.assertIs(storages[0]["readOnly"], True)
            self.assertEqual(storages[1]["rootPath"], str(root / "organized"))
            self.assertIs(storages[1]["readOnly"], False)
            self.assertEqual(storages[2]["rootPath"], "/Media")
            self.assertIs(storages[2]["readOnly"], True)
            self.assertEqual(storages[2]["options"]["tokenEnv"], "OPENLIST_TOKEN")

    def test_management_bootstrap_helper_needs_no_media_mount_and_no_secret(self) -> None:
        """The default deployment bootstrap is usable with durable data alone.

        A fresh installation has no media directory.  The rendered bootstrap
        must therefore carry only the database locator and an environment
        reference for the credential, and must be accepted by the strict
        first-setup loader — otherwise the four Compose services cannot start
        before the operator has configured anything.
        """

        document = make_management_bootstrap()
        rendered = json.dumps(document, ensure_ascii=False)
        self.assertTrue(is_minimal_management_bootstrap(document))
        self.assertEqual(document["persistence"]["databasePath"], "/data/mediaflow.sqlite3")
        self.assertNotIn("api", document)
        self.assertNotIn("principals", document)
        # No business object and no media path may be invented here.
        for section in (
            "storages",
            "resourceLibraries",
            "mediaLibraries",
            "webhooks",
            "automationTaskDefinitions",
        ):
            self.assertNotIn(section, document)
        self.assertNotIn("/media/", rendered)
        # A credential value must never be written into the document.
        self.assertNotIn("MEDIAFLOW_API_TOKEN=", rendered)
        self.assertNotIn("Bearer", rendered)
        loaded = load_minimal_management_bootstrap(document)
        self.assertEqual(loaded.database_path, "/data/mediaflow.sqlite3")

    @unittest.skipUnless(shutil.which("docker"), "Docker engine is not available")
    def test_compose_config_exactly_four_services_with_production_boundaries(self) -> None:
        # A default deployment declares no media mount at all: installing
        # MediaFlow and activating an empty baseline must not require a host
        # media directory that a fresh installation does not have.  Adding one
        # is an explicit overlay, verified separately below.
        self.assertEqual(
            compose_source_bind_mounts(),
            {
                "/config/mediaflow.json": {
                    "type": "bind",
                    "source": "${MEDIAFLOW_CONFIG_FILE:-./config/mediaflow.json}",
                    "target": "/config/mediaflow.json",
                    "read_only": "true",
                    "bind": {"create_host_path": "false"},
                },
                "/run/mediaflow/deployment.env": {
                    "type": "bind",
                    "source": "${MEDIAFLOW_ENV_FILE:-./.env.mediaflow}",
                    "target": "/run/mediaflow/deployment.env",
                    "read_only": "true",
                    "bind": {"create_host_path": "false"},
                },
            },
        )
        result = subprocess.run(
            ["docker", "compose", "-f", str(ROOT / "compose.yaml"), "config", "--format", "json"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(result.stdout)
        services = document["services"]
        self.assertEqual(set(services), {"api", "worker", "scheduler", "notification-worker"})
        expected_commands = {
            "api": ["api"],
            "worker": ["worker"],
            "scheduler": ["scheduler"],
            "notification-worker": ["notification-worker"],
        }
        expected_probes = {
            "api": [
                "CMD",
                "python",
                "-m",
                "mediaflow.container_probe",
                "check",
                "--service",
                "api",
                "--url",
                "http://127.0.0.1:8080/health",
            ],
            "worker": [
                "CMD",
                "python",
                "-m",
                "mediaflow.container_probe",
                "check",
                "--service",
                "worker",
            ],
            "scheduler": [
                "CMD",
                "python",
                "-m",
                "mediaflow.container_probe",
                "check",
                "--service",
                "scheduler",
            ],
            "notification-worker": [
                "CMD",
                "python",
                "-m",
                "mediaflow.container_probe",
                "check",
                "--service",
                "notification-worker",
            ],
        }
        for name, definition in services.items():
            with self.subTest(service=name):
                self.assertEqual(definition["command"], expected_commands[name])
                self.assertEqual(definition["restart"], "unless-stopped")
                self.assertEqual(definition["user"], "10001:10001")
                rendered = json.dumps(definition)
                self.assertNotIn("wsgiref", rendered)
                self.assertNotIn("docker.sock", rendered)
                healthcheck = definition.get("healthcheck")
                self.assertIsNotNone(healthcheck, f"{name} must declare a healthcheck")
                self.assertEqual(healthcheck["test"], expected_probes[name])
                self.assertEqual(healthcheck["retries"], 5)
                self.assertEqual(healthcheck["timeout"], "3s")
                self.assertEqual(healthcheck["start_period"], "15s")
                self.assertEqual(healthcheck["interval"], "10s")
                targets = {item["target"] for item in definition["volumes"]}
                self.assertEqual(
                    targets,
                    {
                        "/data",
                        "/config/mediaflow.json",
                        "/run/mediaflow/deployment.env",
                    },
                )
                if name == "api":
                    self.assertIn("ports", definition)
                else:
                    self.assertNotIn("ports", definition)

    @unittest.skipUnless(shutil.which("docker"), "Docker engine is not available")
    def test_optional_media_mount_overlay_is_explicit_confined_and_required(self) -> None:
        """Local Storage gets a real, explicitly opted-in, confined mount.

        The default topology must stay media-free, but an installation that
        does want Local Storage needs both halves proven: the overlay adds
        exactly the two confined mounts when the variables are set, and refuses
        to render at all — with an actionable message rather than a silently
        created empty directory — when they are not.
        """

        environment = os.environ.copy()
        environment.update(
            {
                "MEDIAFLOW_SOURCE_MEDIA_ROOT": "/host/media/incoming",
                "MEDIAFLOW_TARGET_MEDIA_ROOT": "/host/media/organized",
            }
        )
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(ROOT / "compose.yaml"),
                "-f",
                str(ROOT / "compose.media-mounts.yaml"),
                "config",
                "--format",
                "json",
            ],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(result.stdout)
        by_target = {
            volume["target"]: volume for volume in document["services"]["worker"]["volumes"]
        }
        self.assertEqual(by_target["/media/incoming"]["source"], "/host/media/incoming")
        self.assertIs(by_target["/media/incoming"]["read_only"], True)
        self.assertEqual(by_target["/media/organized"]["source"], "/host/media/organized")
        # Compose omits `read_only` when it is the read-write default, so the
        # writable assertion must accept the key being absent.
        self.assertIs(by_target["/media/organized"].get("read_only", False), False)
        # Both must be non-creating, so a typo can never manufacture a media
        # directory on the host.
        for target in ("/media/incoming", "/media/organized"):
            self.assertIs(by_target[target]["bind"]["create_host_path"], False)
        # Every service must receive the same media topology.
        for name, definition in document["services"].items():
            with self.subTest(service=name):
                targets = {item["target"] for item in definition["volumes"]}
                self.assertEqual(
                    targets,
                    {
                        "/data",
                        "/config/mediaflow.json",
                        "/run/mediaflow/deployment.env",
                        "/media/incoming",
                        "/media/organized",
                    },
                )

        missing = os.environ.copy()
        for name in ("MEDIAFLOW_SOURCE_MEDIA_ROOT", "MEDIAFLOW_TARGET_MEDIA_ROOT"):
            missing.pop(name, None)
        refused = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(ROOT / "compose.yaml"),
                "-f",
                str(ROOT / "compose.media-mounts.yaml"),
                "config",
            ],
            cwd=ROOT,
            env=missing,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(refused.returncode, 0)
        # Compose reports the first unresolved variable; the message must name
        # the exact environment variable the operator has to set.
        self.assertIn("MEDIAFLOW_SOURCE_MEDIA_ROOT", refused.stderr)
        # Both variables are genuinely required, not just the first one.
        self.assertIn(
            "MEDIAFLOW_TARGET_MEDIA_ROOT",
            (ROOT / "compose.media-mounts.yaml").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
