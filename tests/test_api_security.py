from __future__ import annotations

import copy
import io
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime

from pathlib import Path
from unittest.mock import patch

from mediaflow.application.execution_authorization import ExecutionAuthorizationService
from mediaflow.domain.automation_task_definition_preview import (
    AutomationTaskDefinitionPreviewError,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
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
            ApiPermission.REMOTE_EXECUTE,
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
        loaded_legacy = load_runtime_configuration(legacy)
        with patch.dict(os.environ, {"LEGACY_API_TOKEN": "legacy-secret"}, clear=True):
            self.assertEqual(loaded_legacy.resolve_api_principals()[0].principal_id, "legacy-admin")

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
                    None,
                    principals=principals(),
                    remote_execution_enabled=True,
                )
                self.assertEqual(request(api, "GET", "/api/v1/jobs")[0], 401)
                self.assertEqual(request(api, "GET", "/api/v1/jobs", token="viewer-token")[0], 200)
                self.assertEqual(
                    request(
                        api,
                        "POST",
                        "/api/v1/jobs",
                        token="viewer-token",
                        document={"command": "preview", "limit": 1},
                    )[0],
                    403,
                )
                status, job = request(
                    api,
                    "POST",
                    "/api/v1/jobs",
                    token="operator-token",
                    document={"command": "preview", "limit": 1},
                )
                self.assertEqual(status, 202)
                self.assertEqual(
                    request(
                        api,
                        "POST",
                        f"/api/v1/jobs/{job['job_id']}/cancel",
                        token="viewer-token",
                    )[0],
                    403,
                )
                self.assertEqual(
                    request(
                        api,
                        "POST",
                        f"/api/v1/jobs/{job['job_id']}/cancel",
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

    def test_authentication_compares_against_every_configured_principal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                api = MediaFlowApi(repository, None, principals=principals())
                import hmac

                with patch(
                    "mediaflow.interfaces.service_api.hmac.compare_digest",
                    wraps=hmac.compare_digest,
                ) as compare:
                    self.assertEqual(
                        request(api, "GET", "/api/v1/jobs", token="viewer-token")[0], 200
                    )
                self.assertEqual(compare.call_count, len(principals()))

    def test_executor_role_still_requires_one_time_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=principals(),
                    remote_execution_enabled=True,
                )
                document = {"command": "organize", "execute": True, "limit": 1}
                self.assertEqual(
                    request(api, "POST", "/api/v1/jobs", token="operator-token", document=document)[
                        0
                    ],
                    403,
                )
                self.assertEqual(
                    request(api, "POST", "/api/v1/jobs", token="executor-token", document=document)[
                        0
                    ],
                    400,
                )
                issued = ExecutionAuthorizationService(repository).issue(
                    ttl_seconds=60, max_items=1
                )
                status, job = request(
                    api,
                    "POST",
                    "/api/v1/jobs",
                    token="executor-token",
                    execution_token=issued.token,
                    document=document,
                )
                self.assertEqual(status, 202)
                self.assertTrue(job["execute_authorized"])

    def test_audit_success_denial_redaction_order_limit_and_source_sanitizing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                api = MediaFlowApi(repository, None, principals=principals())
                request(api, "GET", "/api/v1/jobs", token="wrong-secret")
                request(api, "GET", "/api/v1/jobs", token="viewer-token")
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

    def test_audit_failure_blocks_job_creation_before_mutation(self) -> None:
        class BrokenAuditRepository(SQLiteTaskRepository):
            def append_security_audit(self, value):
                raise OSError("database unavailable token=secret")

        with tempfile.TemporaryDirectory() as directory:
            with BrokenAuditRepository(Path(directory, "runtime.sqlite3")) as repository:
                api = MediaFlowApi(repository, None, principals=principals())
                status, response = request(
                    api,
                    "POST",
                    "/api/v1/jobs",
                    token="operator-token",
                    document={"command": "preview", "limit": 1},
                )
                self.assertEqual(status, 500)
                self.assertEqual(repository.list_jobs(), ())
                self.assertNotIn("secret", json.dumps(response))

    def test_local_audit_cli_is_storage_free_and_redacted(self) -> None:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            document["persistence"] = {"databasePath": str(database)}
            document["storages"][0]["rootPath"] = str(Path(directory, "missing-source"))
            document["storages"][1]["rootPath"] = str(Path(directory, "missing-target"))
            config = Path(directory, "config.json")
            config.write_text(json.dumps(document), encoding="utf-8")
            with SQLiteTaskRepository(database) as repository:
                api = MediaFlowApi(repository, None, principals=principals())
                request(api, "GET", "/api/v1/jobs", token="viewer-token")
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

    def test_schema_eight_migrates_security_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            connection = sqlite3.connect(database)
            connection.executescript(
                "CREATE TABLE schema_version "
                "(component TEXT PRIMARY KEY, version INTEGER NOT NULL);"
                "INSERT INTO schema_version VALUES ('runtime', 8);"
            )
            connection.close()
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)
                self.assertEqual(repository.list_security_audit(), ())

class WorkerRouteSecurityTests(unittest.TestCase):
    def test_unauthenticated_requests_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                api = MediaFlowApi(
                    repository,
                    None,
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
                    None,
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
                    runtime_schema_version=33,
                    now=now,
                )
                api = MediaFlowApi(
                    repository,
                    None,
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
                                runtime_schema_version=33,
                                now=datetime.now(UTC),
                            )


class AutomationPreviewSecurityTests(unittest.TestCase):
    def test_viewer_can_inspect_preview_but_cannot_run_and_audit_is_secret_free(self) -> None:
        class FakePreviewService:
            def list_readonly(self, definition_id, *, limit=100):
                return ()

            def get_readonly(self, preview_id):
                raise LookupError("preview not found")

            def create(self, definition_id, *, revision_id=None, actor):
                raise AutomationTaskDefinitionPreviewError(
                    "automation Preview failed before analysis",
                    code="automation_preview_rejected",
                    status=400,
                )

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.sqlite3"
            with SQLiteTaskRepository(database) as repository:
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=principals(),
                    automation_preview_service=FakePreviewService(),
                )
                status, body = request(
                    api,
                    "GET",
                    "/api/v1/automation/task-definitions/task/previews",
                    token="viewer-token",
                )
                self.assertEqual(status, 200)
                self.assertEqual(body["items"], [])
                status, _ = request(
                    api,
                    "POST",
                    "/api/v1/automation/task-definitions/task/preview",
                    token="viewer-token",
                    document={},
                )
                self.assertEqual(status, 403)
                status, body = request(
                    api,
                    "POST",
                    "/api/v1/automation/task-definitions/task/preview",
                    token="operator-token",
                    document={"token": "secret-value"},
                )
                self.assertEqual(status, 400)
                self.assertNotIn("secret-value", json.dumps(body))
                audit = repository.list_security_audit()
                rendered = str([item.__dict__ for item in audit])
                self.assertNotIn("secret-value", rendered)
                self.assertIn(
                    "/api/v1/automation/task-definitions/{id}/preview",
                    rendered,
                )


if __name__ == "__main__":
    unittest.main()
