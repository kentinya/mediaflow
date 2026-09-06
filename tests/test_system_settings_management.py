from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.configuration_management import (
    ConfigurationObjectKind,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.system_settings import (
    SystemSettings,
    SystemSettingsEdit,
    validate_settings_edit,
)
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.interfaces.operator_ui import APP_JS, INDEX_HTML
from mediaflow.interfaces.service_api import MediaFlowApi


def example_document() -> dict:
    return json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))


def request(
    api,
    path,
    *,
    method="GET",
    body=b"",
    token="admin-token",
    headers=None,
    query="",
):
    if "?" in path and not query:
        path, query = path.split("?", 1)
    statuses = []
    environment = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}" if token else "",
    }
    environment.update(headers or {})
    payload = b"".join(api(environment, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(payload)


class DummyTaskRepository:
    def __init__(self, database_path: str = ":memory:") -> None:
        self.database_path = database_path

    def list_security_audit(self, *, limit: int = 100):
        return ()

    def append_security_audit(self, value):
        pass


def setup_test_api(directory: str):
    doc = example_document()
    db_path = str(Path(directory) / "runtime.sqlite3")
    doc["persistence"]["databasePath"] = db_path
    config_repo = SQLiteConfigurationRepository(Path(directory) / "configuration.sqlite3")
    config_service = ManagedConfigurationService(
        config_repo,
        bootstrap_database_path=db_path,
    )
    draft = config_service.import_draft(doc, actor="bootstrap")
    validated = config_service.validate(draft.revision_id, actor="bootstrap")
    active = config_service.activate(
        validated.revision_id, expected_version=validated.version, actor="bootstrap"
    )

    admin = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
    viewer = ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
    task_repo = DummyTaskRepository(str(Path(directory) / "runtime.sqlite3"))

    api = MediaFlowApi(
        task_repo,
        None,
        principals=(admin, viewer),
        configuration_service=config_service,
        bootstrap_document=doc,
    )
    return api, config_service, active, config_repo


class SystemSettingsManagementTests(unittest.TestCase):
    def test_domain_projection_and_boundaries(self) -> None:
        doc = example_document()
        doc["locale"] = "en-US"
        doc["timezone"] = "UTC"
        doc["cachePath"] = ".mediaflow/cache"
        doc["logPath"] = ".mediaflow/logs"
        doc["exportPath"] = ".mediaflow/exports"
        settings = SystemSettings.from_document(doc, revision_id="rev-1", revision_version=1)
        projection = settings.as_projection()

        self.assertEqual(projection["revisionId"], "rev-1")
        self.assertEqual(projection["revisionVersion"], 1)
        self.assertEqual(projection["settings"]["locale"], "en-US")
        self.assertEqual(projection["settings"]["timezone"], "UTC")
        self.assertEqual(projection["settings"]["cachePath"], ".mediaflow/cache")
        self.assertEqual(
            projection["sections"]["Database"]["persistence.databasePath"]["boundary"],
            "bootstrap_immutable",
        )
        self.assertEqual(
            projection["sections"]["Database"]["historyPath"]["boundary"],
            "restart_required",
        )
        self.assertEqual(
            projection["sections"]["Automation"]["automation.maximumActiveJobs"]["boundary"],
            "hot_consumed",
        )

    def test_validation_rejects_bootstrap_immutable(self) -> None:
        edits = (SystemSettingsEdit("persistence.databasePath", "new/path.sqlite3"),)
        errors = validate_settings_edit(edits, bootstrap_database_path="/orig/path.sqlite3")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], "field_immutable")
        self.assertEqual(errors[0]["boundary"], "bootstrap_immutable")

    def test_validation_rejects_unknown_field(self) -> None:
        edits = (SystemSettingsEdit("unknown.setting", 42),)
        errors = validate_settings_edit(edits, bootstrap_database_path=None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], "unknown_field")

    def test_validation_bounds_and_cross_field(self) -> None:
        # Out of bounds active jobs
        edits = (SystemSettingsEdit("automation.maximumActiveJobs", 99999),)
        errors = validate_settings_edit(edits, bootstrap_database_path=None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], "invalid_range")

        # Invalid jitter ratio
        edits = (SystemSettingsEdit("workflowRetry.jitterRatio", 1.5),)
        errors = validate_settings_edit(edits, bootstrap_database_path=None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], "invalid_range")

        # Cross field: maxDelay < baseDelay
        edits = (
            SystemSettingsEdit("workflowRetry.baseDelaySeconds", 10.0),
            SystemSettingsEdit("workflowRetry.maxDelaySeconds", 5.0),
        )
        errors = validate_settings_edit(edits, bootstrap_database_path=None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], "invalid_range")

        # Invalid enum
        edits = (SystemSettingsEdit("operationalLogging.minimumLevel", "NONEXISTENT"),)
        errors = validate_settings_edit(edits, bootstrap_database_path=None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], "invalid_enum")

        # Invalid locale
        edits = (SystemSettingsEdit("locale", "not a locale!"),)
        errors = validate_settings_edit(edits, bootstrap_database_path=None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], "invalid_locale")

        # Invalid timezone
        edits = (SystemSettingsEdit("timezone", "Moon/Base"),)
        errors = validate_settings_edit(edits, bootstrap_database_path=None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], "invalid_timezone")

        # Unsafe path
        edits = (SystemSettingsEdit("historyPath", "/absolute/path"),)
        errors = validate_settings_edit(edits, bootstrap_database_path=None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], "unsafe_path")

    def test_api_read_active_system_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)
            status, data = request(api, "/api/v1/system/settings")
            self.assertEqual(status, 200)
            self.assertEqual(data["authority"], "MANAGED")
            self.assertEqual(data["revisionId"], active.revision_id)
            self.assertTrue(data["isActive"])
            self.assertTrue(data["consumption"]["consumed"])
            self.assertEqual(data["consumption"]["revisionId"], active.revision_id)
            self.assertIn("persistence.databasePath", data["settings"])
            self.assertIn("automation.maximumActiveJobs", data["settings"])

    def test_api_read_draft_settings_via_query_and_revision_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)
            draft = service.create_successor_draft(actor="tester")

            # Via query param
            status, data1 = request(api, f"/api/v1/system/settings?revisionId={draft.revision_id}")
            self.assertEqual(status, 200)
            self.assertEqual(data1["revisionId"], draft.revision_id)
            self.assertFalse(data1["isActive"])

            # Via revision route
            status, data2 = request(
                api, f"/api/v1/configuration/revisions/{draft.revision_id}/settings"
            )
            self.assertEqual(status, 200)
            self.assertEqual(data2["revisionId"], draft.revision_id)
            self.assertFalse(data2["isActive"])

    def test_api_edit_creates_successor_draft_and_preserves_active(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)
            body = json.dumps(
                {
                    "settings": {
                        "automation.maximumActiveJobs": 75,
                        "operationalLogging.minimumLevel": "DEBUG",
                        "workflowRetry.maxAttempts": 5,
                    }
                }
            ).encode("utf-8")
            status, data = request(api, "/api/v1/system/settings", method="PUT", body=body)
            self.assertEqual(status, 201)
            self.assertTrue(data["created"])
            self.assertNotEqual(data["revisionId"], active.revision_id)
            self.assertEqual(data["settings"]["automation.maximumActiveJobs"], 75)
            self.assertEqual(data["settings"]["operationalLogging.minimumLevel"], "DEBUG")
            self.assertEqual(data["settings"]["workflowRetry.maxAttempts"], 5)

            # Prior Active remains unchanged
            active_after = service.active()
            self.assertEqual(active_after.revision_id, active.revision_id)
            self.assertEqual(
                active_after.document.get("automation", {}).get("maximumActiveJobs"), 100
            )

    def test_api_edit_existing_draft_with_expected_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)
            draft = service.create_successor_draft(actor="tester")
            body = json.dumps(
                {
                    "expectedVersion": draft.version,
                    "settings": {
                        "automation.staleJobAgeSeconds": 7200,
                    },
                }
            ).encode("utf-8")
            status, data = request(
                api,
                f"/api/v1/configuration/revisions/{draft.revision_id}/settings",
                method="PUT",
                body=body,
            )
            self.assertEqual(status, 200)
            self.assertEqual(data["revisionId"], draft.revision_id)
            self.assertEqual(data["settings"]["automation.staleJobAgeSeconds"], 7200)

            # Re-read Draft from repo
            updated_draft = service.require(draft.revision_id)
            self.assertEqual(
                updated_draft.document.get("automation", {}).get("staleJobAgeSeconds"), 7200
            )
            self.assertEqual(updated_draft.version, draft.version + 1)

    def test_api_stale_concurrency_returns_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)
            draft = service.create_successor_draft(actor="tester")
            body = json.dumps(
                {
                    "expectedVersion": draft.version + 99,
                    "settings": {
                        "automation.staleJobAgeSeconds": 7200,
                    },
                }
            ).encode("utf-8")
            status, data = request(
                api,
                f"/api/v1/configuration/revisions/{draft.revision_id}/settings",
                method="PUT",
                body=body,
            )
            self.assertEqual(status, 409)
            self.assertEqual(data["error"]["code"], "configuration_version_conflict")
            self.assertEqual(data["error"]["details"]["durableState"], "draft_preserved")

    def test_api_rbac_enforcement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)

            # Unauthenticated -> 401
            status, _ = request(api, "/api/v1/system/settings", token=None)
            self.assertEqual(status, 401)

            # Viewer (read-only) -> GET 200, PUT 403
            status, _ = request(api, "/api/v1/system/settings", token="viewer-token")
            self.assertEqual(status, 200)

            body = json.dumps({"settings": {"automation.maximumActiveJobs": 50}}).encode("utf-8")
            status, data = request(
                api, "/api/v1/system/settings", method="PUT", body=body, token="viewer-token"
            )
            self.assertEqual(status, 403)
            self.assertEqual(data["error"]["code"], "forbidden")

    def test_api_rejects_immutable_database_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)
            body = json.dumps(
                {"settings": {"persistence.databasePath": "tampered.sqlite3"}}
            ).encode("utf-8")
            status, data = request(api, "/api/v1/system/settings", method="PUT", body=body)
            self.assertEqual(status, 422)
            self.assertEqual(data["error"]["code"], "system_settings_invalid")
            errors = data["error"]["details"]["errors"]
            self.assertTrue(any(e["field"] == "persistence.databasePath" for e in errors))

    def test_api_audit_and_no_secret_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)
            body = json.dumps(
                {
                    "settings": {
                        "operationalLogging.minimumLevel": "WARN",
                    }
                }
            ).encode("utf-8")
            status, data = request(api, "/api/v1/system/settings", method="PUT", body=body)
            self.assertEqual(status, 201)

            audits = repo.list_revision_audits(data["revisionId"])
            self.assertTrue(
                any(a.object_kind == ConfigurationObjectKind.SYSTEM_SETTINGS for a in audits)
            )
            # Verify no secret text in audit
            for a in audits:
                self.assertNotIn("secret", json.dumps(a.safe_after()).lower())

    def test_web_ui_assets_expose_system_settings(self) -> None:
        html = INDEX_HTML.decode("utf-8")
        script = APP_JS.decode("utf-8")

        self.assertIn('data-view="settings"', html)
        self.assertIn("System Settings", script)
        self.assertIn("/api/v1/system/settings", script)
        self.assertIn("renderSettings", script)
        self.assertIn("Bootstrap-owned", script)
        self.assertIn("typedSettingControl", script)
        self.assertIn("input.type = 'checkbox'", script)
        self.assertIn("input.type = 'number'", script)
        self.assertIn("meta.valueType === 'enum'", script)
        self.assertIn("pendingByPath", script)
        self.assertIn("Add at least one setting edit before saving.", script)

    def test_runtime_projection_preserves_extended_settings(self) -> None:
        from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration

        doc = example_document()
        doc["cachePath"] = ".mediaflow/cache"
        doc["logPath"] = ".mediaflow/logs"
        doc["exportPath"] = ".mediaflow/exports"
        doc["locale"] = "zh-CN"
        doc["timezone"] = "Asia/Shanghai"

        runtime = load_runtime_configuration(doc)

        self.assertEqual(runtime.cache_path, ".mediaflow/cache")
        self.assertEqual(runtime.log_path, ".mediaflow/logs")
        self.assertEqual(runtime.export_path, ".mediaflow/exports")
        self.assertEqual(runtime.locale, "zh-CN")
        self.assertEqual(runtime.timezone, "Asia/Shanghai")


if __name__ == "__main__":
    unittest.main()
