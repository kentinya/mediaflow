from __future__ import annotations

import copy
import io
import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

PERMISSIONS = {
    "viewer": frozenset({ApiPermission.READ}),
    "operator": frozenset(
        {
            ApiPermission.READ,
            ApiPermission.SUBMIT_DRY_RUN,
            ApiPermission.CANCEL_JOB,
            ApiPermission.RESOLVE_CONFIRMATION,
        }
    ),
    "executor": frozenset(
        {
            ApiPermission.READ,
            ApiPermission.SUBMIT_DRY_RUN,
            ApiPermission.CANCEL_JOB,
            ApiPermission.RESOLVE_CONFIRMATION,
        }
    ),
    "auditor": frozenset({ApiPermission.READ, ApiPermission.READ_SECURITY_AUDIT}),
    "admin": frozenset(ApiPermission),
}


def principals():
    return tuple(
        ResolvedApiPrincipal(name, f"{name}-token", permissions)
        for name, permissions in PERMISSIONS.items()
    )


def request(api, method, path, *, token=None, document=None, execution_token=None):
    body = b"" if document is None else json.dumps(document).encode()
    status = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(body)),
        "REMOTE_ADDR": "127.0.0.1\nignored",
        "wsgi.input": io.BytesIO(body),
    }
    if token:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    if execution_token:
        environ["HTTP_X_MEDIAFLOW_EXECUTION_TOKEN"] = execution_token
    response = b"".join(api(environ, lambda value, headers: status.append(value)))
    return int(status[0].split()[0]), json.loads(response)


class ApiSecurityTests(unittest.TestCase):
    def test_configuration_principals_roles_legacy_and_invalid_matrix(self) -> None:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        loaded = load_runtime_configuration(copy.deepcopy(document))
        self.assertEqual(loaded.api_principals[0].principal_id, "local-admin")
        self.assertEqual(loaded.api_principals[0].permissions, frozenset(ApiPermission))
        with patch.dict(os.environ, {"MEDIAFLOW_API_TOKEN": "resolved-secret"}, clear=True):
            resolved = loaded.resolve_api_principals()
        self.assertEqual(resolved[0].principal_id, "local-admin")
        self.assertEqual(resolved[0].token, "resolved-secret")

        legacy = copy.deepcopy(document)
        legacy["api"] = {"tokenEnv": "LEGACY_API_TOKEN"}
        with (
            patch.dict(os.environ, {"LEGACY_API_TOKEN": "legacy-secret"}, clear=True),
            self.assertRaisesRegex(ValueError, "api.tokenEnv is retired"),
        ):
            load_runtime_configuration(legacy)

        invalid_values = []
        mixed = copy.deepcopy(document)
        mixed["api"]["tokenEnv"] = "LEGACY_API_TOKEN"
        invalid_values.append(mixed)
        duplicate_id = copy.deepcopy(document)
        duplicate_id["api"]["principals"].append(
            {"id": "local-admin", "tokenEnv": "SECOND", "roles": ["viewer"]}
        )
        invalid_values.append(duplicate_id)
        duplicate_env = copy.deepcopy(document)
        duplicate_env["api"]["principals"].append(
            {"id": "second", "tokenEnv": "MEDIAFLOW_API_TOKEN", "roles": ["viewer"]}
        )
        invalid_values.append(duplicate_env)
        unknown = copy.deepcopy(document)
        unknown["api"]["principals"][0]["roles"] = ["root"]
        invalid_values.append(unknown)
        empty = copy.deepcopy(document)
        empty["api"]["principals"][0]["roles"] = []
        invalid_values.append(empty)
        literal = copy.deepcopy(document)
        literal["api"]["principals"][0]["token"] = "secret"
        invalid_values.append(literal)
        for value in invalid_values:
            with self.subTest(value=value["api"]), self.assertRaises(ValueError):
                load_runtime_configuration(value)

        missing = copy.deepcopy(document)
        missing["api"]["principals"][0]["tokenEnv"] = "MISSING_API_TOKEN"
        with (
            patch.dict(os.environ, {}, clear=True),
            self.assertRaisesRegex(ValueError, "MISSING_API_TOKEN"),
        ):
            load_runtime_configuration(missing).resolve_api_principals()
        disabled = copy.deepcopy(document)
        disabled["api"]["principals"][0]["enabled"] = False
        with self.assertRaisesRegex(ValueError, "enabled configured principal"):
            load_runtime_configuration(disabled).resolve_api_principals()

    def test_role_permission_matrix_and_401_403(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                api = MediaFlowApi(
                    repository,
                    principals=principals(),
                )
                self.assertEqual(request(api, "GET", "/api/v1/tasks")[0], 401)
                self.assertEqual(request(api, "GET", "/api/v1/tasks", token="viewer-token")[0], 200)
                # Task cancellation stays permission-gated on the durable Task
                # the scheduling kernel admitted.
                from mediaflow.application.task_scheduling import TaskSchedulingService

                task = (
                    TaskSchedulingService(repository, capacity=10)
                    .admit(
                        "organize",
                        execute_authorized=True,
                        trigger=__import__(
                            "mediaflow.domain.task_scheduling", fromlist=["TaskTrigger"]
                        ).TaskTrigger.MANUAL,
                        principal="operator",
                        now=datetime.now(UTC),
                    )
                    .task
                )
                self.assertEqual(
                    request(
                        api,
                        "POST",
                        f"/api/v1/tasks/{task.task_id}/cancel",
                        token="viewer-token",
                    )[0],
                    403,
                )
                self.assertEqual(
                    request(
                        api,
                        "POST",
                        f"/api/v1/tasks/{task.task_id}/cancel",
                        token="operator-token",
                    )[0],
                    200,
                )
                self.assertEqual(
                    request(api, "GET", "/api/v1/security-audit", token="viewer-token")[0],
                    403,
                )
                self.assertEqual(
                    request(api, "GET", "/api/v1/security-audit", token="auditor-token")[0],
                    200,
                )
                self.assertEqual(
                    request(api, "GET", "/api/v1/security-audit", token="admin-token")[0],
                    200,
                )

    def test_authenticated_principal_read_returns_only_current_principal_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                api = MediaFlowApi(repository, principals=principals())
                status, document = request(
                    api,
                    "GET",
                    "/api/v1/auth/principal",
                    token="viewer-token",
                )
                self.assertEqual(status, 200)
                self.assertEqual(document, {"principal_id": "viewer"})
                self.assertNotIn("token", json.dumps(document).lower())
                self.assertEqual(
                    request(api, "GET", "/api/v1/auth/principal")[0],
                    401,
                )

    def test_authentication_compares_against_every_configured_principal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                api = MediaFlowApi(repository, principals=principals())
                import hmac

                with patch(
                    "mediaflow.interfaces.service_api.hmac.compare_digest",
                    wraps=hmac.compare_digest,
                ) as compare:
                    self.assertEqual(
                        request(api, "GET", "/api/v1/tasks", token="viewer-token")[0], 200
                    )
                self.assertEqual(compare.call_count, len(principals()))

    def test_audit_success_denial_redaction_order_limit_and_source_sanitizing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                api = MediaFlowApi(repository, principals=principals())
                request(api, "GET", "/api/v1/tasks", token="wrong-secret")
                request(api, "GET", "/api/v1/auth/principal", token="viewer-token")
                request(api, "GET", "/api/v1/path-token-secret", token="viewer-token")
                values = repository.list_security_audit(limit=10)
                self.assertTrue(any(item.outcome == "denied" for item in values))
                self.assertTrue(any(item.outcome == "allowed" for item in values))
                self.assertTrue(any(item.principal_id == "viewer" for item in values))
                serialized = repr(values)
                self.assertNotIn("wrong-secret", serialized)
                self.assertNotIn("viewer-token", serialized)
                self.assertNotIn("path-token-secret", serialized)
                self.assertNotIn("Authorization", serialized)
                self.assertNotIn("ignored", serialized)
                self.assertLessEqual(len(repository.list_security_audit(limit=1)), 1)

    def test_local_audit_cli_is_storage_free_and_redacted(self) -> None:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            document["persistence"] = {"databasePath": str(database)}
            document["storages"][0]["rootPath"] = str(Path(directory, "missing-source"))
            document["storages"][1]["rootPath"] = str(Path(directory, "missing-target"))
            document.pop("api", None)
            config = Path(directory, "config.json")
            config.write_text(json.dumps(document), encoding="utf-8")
            bootstrap = {
                "persistence": {"databasePath": str(database)},
                "api": {
                    "principals": [
                        {
                            "id": "admin",
                            "tokenEnv": "MEDIAFLOW_API_TOKEN",
                            "roles": ["admin"],
                        }
                    ]
                },
            }
            with SQLiteConfigurationRepository(database) as configuration_repository:
                service = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(database),
                    bootstrap_document=bootstrap,
                )
                draft = service.import_draft(document, actor="tester")
                validated = service.validate(draft.revision_id, actor="tester")
                service.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
            with SQLiteTaskRepository(database) as repository:
                api = MediaFlowApi(repository, principals=principals())
                request(api, "GET", "/api/v1/tasks", token="viewer-token")
            output, error = io.StringIO(), io.StringIO()
            self.assertEqual(
                final_main(
                    ["--config", str(config), "security-audit", "list", "--limit", "10"],
                    stdout=output,
                    stderr=error,
                ),
                0,
                error.getvalue(),
            )
            self.assertIn("SECURITY AUDIT", output.getvalue())
            self.assertNotIn("viewer-token", output.getvalue())
            self.assertFalse(Path(directory, "missing-source").exists())


class WorkerRouteSecurityTests(unittest.TestCase):
    def test_unauthenticated_requests_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                api = MediaFlowApi(
                    repository,
                    principals=principals(),
                )
                for path in ("/api/v1/workers", "/api/v1/workers/readiness"):
                    for method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                        with self.subTest(path=path, method=method):
                            status, _ = request(api, method, path, token=None)
                            self.assertEqual(status, 401)

    def test_only_get_is_allowed_and_mutation_methods_return_405(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                api = MediaFlowApi(
                    repository,
                    principals=principals(),
                )
                for path in ("/api/v1/workers", "/api/v1/workers/readiness"):
                    for method in ("POST", "PUT", "PATCH", "DELETE"):
                        with self.subTest(path=path, method=method):
                            status, _ = request(api, method, path, token="viewer-token")
                            self.assertEqual(status, 405)

    def test_worker_routes_redact_secrets_in_projections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                now = datetime.now(UTC)
                repository.register_worker(
                    worker_id="w-1",
                    label="node-1",
                    heartbeat_interval_seconds=5.0,
                    supported_commands=("scan",),
                    configuration_snapshot_id="cfg-1",
                    configuration_snapshot_digest="sha256:test",
                    runtime_schema_version=SCHEMA_VERSION,
                    now=now,
                )
                api = MediaFlowApi(
                    repository,
                    principals=principals(),
                )
                status, doc = request(api, "GET", "/api/v1/workers", token="viewer-token")
                self.assertEqual(status, 200)
                self.assertEqual(doc["count"], 1)
                serialized = json.dumps(doc)
                self.assertIn("cfg-1", serialized)
                self.assertNotIn("token", serialized.lower())
                status, readiness = request(
                    api, "GET", "/api/v1/workers/readiness", token="viewer-token"
                )
                self.assertEqual(status, 200)
                self.assertIn("ready", readiness)
                self.assertIn("condition", readiness)

    def test_label_validation_for_paths_and_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                for bad_label in (
                    "/etc/passwd",
                    "C:\\\\secrets",
                    "https://x/token",
                    "password=hunter2",
                ):
                    with self.subTest(label=bad_label):
                        with self.assertRaises(ValueError):
                            repository.register_worker(
                                worker_id="w-bad",
                                label=bad_label,
                                heartbeat_interval_seconds=5.0,
                                supported_commands=("scan",),
                                configuration_snapshot_id="cfg-1",
                                configuration_snapshot_digest="sha256:test",
                                runtime_schema_version=SCHEMA_VERSION,
                                now=datetime.now(UTC),
                            )


class RetiredAutomationPreviewSecurityTests(unittest.TestCase):
    """The independent Automation Preview product cannot be run or inspected.

    Its old routes answer as ordinary not-found results after normal
    authentication, they leak no submitted secret and they leave no durable
    preview record behind.
    """

    def test_old_preview_routes_are_ordinary_not_found_and_secret_free(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.sqlite3"
            with SQLiteTaskRepository(database) as repository:
                api = MediaFlowApi(repository, principals=principals())
                for method, path, token in (
                    ("GET", "/api/v1/automation/task-definitions/task/previews", "viewer-token"),
                    ("POST", "/api/v1/automation/task-definitions/task/preview", "viewer-token"),
                    ("POST", "/api/v1/automation/task-definitions/task/preview", "operator-token"),
                ):
                    with self.subTest(method=method, path=path, token=token):
                        status, body = request(
                            api, method, path, token=token, document={"token": "secret-value"}
                        )
                        self.assertIn(status, (403, 404), body)
                        self.assertNotIn("secret-value", json.dumps(body))
                audit = repository.list_security_audit()
                rendered = str([item.__dict__ for item in audit])
                self.assertNotIn("secret-value", rendered)


if __name__ == "__main__":
    unittest.main()
