from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

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


def _js_function_body(script: str, name: str) -> str:
    """Return one JS function body from the served asset by brace matching."""

    opening = script.index("{", script.index(f"function {name}("))
    depth = 0
    for index in range(opening, len(script)):
        if script[index] == "{":
            depth += 1
        elif script[index] == "}":
            depth -= 1
            if depth == 0:
                return script[opening + 1 : index]
    raise AssertionError("JavaScript block has an unbalanced body")


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
            self.assertEqual(data["consumption"]["runtimeSnapshotId"], active.revision_id)
            self.assertEqual(data["consumption"]["runtimeSnapshotDigest"], active.digest)
            self.assertIn("automation.maximumActiveJobs", data["consumption"]["consumedFields"])

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

    def test_api_edit_response_can_continue_draft_journey(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)
            create_body = json.dumps(
                {"edits": [{"fieldPath": "automation.maximumActiveJobs", "value": 75}]}
            ).encode("utf-8")
            status, created = request(
                api, "/api/v1/system/settings", method="PUT", body=create_body
            )
            self.assertEqual(status, 201)
            draft_id = created["revisionId"]
            status, draft_view = request(api, f"/api/v1/system/settings?revisionId={draft_id}")
            self.assertEqual(status, 200)
            self.assertEqual(draft_view["revisionId"], draft_id)
            self.assertFalse(draft_view["isActive"])
            # The mutable Draft version is exposed separately from the immutable
            # revision sequence and is the token successive edits must send.
            self.assertEqual(draft_view["draftVersion"], created["draftVersion"])
            self.assertEqual(draft_view["revisionVersion"], created["revisionVersion"])
            self.assertNotEqual(draft_view["draftVersion"], None)
            for value in (80, 85, 90):
                update_body = json.dumps(
                    {
                        "revisionId": draft_id,
                        "expectedVersion": draft_view["draftVersion"],
                        "edits": [{"fieldPath": "automation.maximumActiveJobs", "value": value}],
                    }
                ).encode("utf-8")
                status, updated = request(
                    api, "/api/v1/system/settings", method="PUT", body=update_body
                )
                self.assertEqual(status, 200)
                self.assertEqual(updated["revisionId"], draft_id)
                self.assertEqual(updated["settings"]["automation.maximumActiveJobs"], value)
                self.assertEqual(updated["draftVersion"], draft_view["draftVersion"] + 1)
                self.assertEqual(updated["revisionVersion"], draft_view["revisionVersion"])
                draft_view = updated
            edited = service.require(draft_id)
            self.assertEqual(edited.version, 5)
            self.assertEqual(edited.revision_sequence, 2)

    def test_consumption_evidence_fails_closed_on_runtime_snapshot_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)
            stale_binding = replace(
                api._runtime_binding,
                runtime_settings={
                    "snapshotId": "stale-revision",
                    "digest": "stale-digest",
                    "settings": {},
                },
            )
            with (
                patch.object(api, "_refresh_configuration_binding", return_value=stale_binding),
                patch.object(api, "_runtime_binding", stale_binding),
            ):
                status, data = request(api, "/api/v1/system/settings")
            self.assertEqual(status, 200)
            self.assertFalse(data["consumption"]["consumed"])
            self.assertEqual(data["consumption"]["reason"], "runtime_snapshot_mismatch")
            self.assertEqual(data["consumption"]["revisionId"], active.revision_id)

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

    def test_api_missing_active_fails_closed_with_recovery_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)
            connection = sqlite3.connect(str(Path(directory) / "configuration.sqlite3"))
            try:
                connection.execute(
                    "DELETE FROM managed_configuration_revisions WHERE status='active'"
                )
                connection.commit()
            finally:
                connection.close()
            rows_after_delete = len(repo.list_revisions(limit=100))

            # Read fails closed and names the durable last-known Active identity.
            status, body = request(api, "/api/v1/system/settings")
            self.assertEqual(status, 503)
            self.assertEqual(body["error"]["code"], "configuration_unavailable")
            details = body["error"]["details"]
            self.assertEqual(details["reason"], "active_missing")
            self.assertEqual(details["durableState"], "managed_active_unavailable")
            self.assertEqual(details["sideEffects"], "none")
            self.assertTrue(details["retrySafe"])
            self.assertIn("Draft", details["nextAction"])
            self.assertEqual(details["revisionId"], active.revision_id)
            self.assertEqual(details["digest"], active.digest)

            # Edit fails closed as well: no settings Draft is created.
            body = json.dumps({"edits": [{"fieldPath": "locale", "value": "en-US"}]}).encode(
                "utf-8"
            )
            status, _ = request(api, "/api/v1/system/settings", method="PUT", body=body)
            self.assertEqual(status, 503)
            self.assertEqual(len(repo.list_revisions(limit=100)), rows_after_delete)

    def test_api_corrupt_active_fails_closed_without_payload_leak(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)
            revisions_before = len(repo.list_revisions(limit=100))
            tampered = {**example_document(), "historyPath": "tampered-history.jsonl"}
            repo._connection.execute(
                "UPDATE managed_configuration_revisions SET payload=? WHERE revision_id=?",
                (json.dumps(tampered), active.revision_id),
            )
            repo._connection.commit()

            status, body = request(api, "/api/v1/system/settings")
            self.assertEqual(status, 503)
            self.assertEqual(body["error"]["code"], "configuration_unavailable")
            details = body["error"]["details"]
            self.assertEqual(details["reason"], "digest_corrupt")
            self.assertEqual(details["durableState"], "managed_active_unavailable")
            self.assertEqual(details["sideEffects"], "none")
            self.assertTrue(details["retrySafe"])
            self.assertEqual(details["revisionId"], active.revision_id)
            # The corrupt payload contents never leak through the failure projection.
            self.assertNotIn("tampered-history.jsonl", json.dumps(body))

            status, _ = request(
                api,
                "/api/v1/system/settings",
                method="PUT",
                body=json.dumps({"edits": [{"fieldPath": "locale", "value": "en-US"}]}).encode(
                    "utf-8"
                ),
            )
            self.assertEqual(status, 503)
            self.assertEqual(len(repo.list_revisions(limit=100)), revisions_before)
            # The corrupt Active row itself is preserved for diagnosis/recovery.
            self.assertEqual(len(repo.list_revisions(limit=100)), revisions_before)

    def test_api_runtime_invalid_active_fails_closed_and_preserves_active(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)
            revisions_before = len(repo.list_revisions(limit=100))
            changed = json.loads(json.dumps(example_document()))
            changed["persistence"]["databasePath"] = str(Path(directory) / "other.sqlite3")
            payload = json.dumps(
                changed,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            repo._connection.execute(
                "UPDATE managed_configuration_revisions SET payload=?, digest=? "
                "WHERE revision_id=?",
                (payload, digest, active.revision_id),
            )
            repo._connection.commit()

            status, body = request(api, "/api/v1/system/settings")
            self.assertEqual(status, 503)
            self.assertEqual(body["error"]["code"], "configuration_unavailable")
            details = body["error"]["details"]
            self.assertEqual(details["reason"], "runtime_invalid")
            self.assertEqual(details["durableState"], "managed_active_unavailable")
            self.assertEqual(details["sideEffects"], "none")
            self.assertTrue(details["retrySafe"])
            self.assertEqual(details["revisionId"], active.revision_id)

            status, _ = request(
                api,
                "/api/v1/system/settings",
                method="PUT",
                body=json.dumps({"edits": [{"fieldPath": "locale", "value": "en-US"}]}).encode(
                    "utf-8"
                ),
            )
            self.assertEqual(status, 503)
            self.assertEqual(len(repo.list_revisions(limit=100)), revisions_before)
            row = repo._connection.execute(
                "SELECT payload FROM managed_configuration_revisions WHERE revision_id=?",
                (active.revision_id,),
            ).fetchone()
            self.assertEqual(row["payload"], payload)

    def test_api_restart_required_settings_are_not_claimed_consumed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)
            body = json.dumps(
                {
                    "edits": [
                        {"fieldPath": "cachePath", "value": ".mediaflow/cache-2"},
                        {"fieldPath": "locale", "value": "zh-CN"},
                    ]
                }
            ).encode("utf-8")
            status, created = request(api, "/api/v1/system/settings", method="PUT", body=body)
            self.assertEqual(status, 201)
            draft_id = created["revisionId"]

            # The restart-required values move only through the normal exact
            # validate/checked-activate path.
            status, _ = request(
                api,
                f"/api/v1/configuration/revisions/{draft_id}/validate",
                method="POST",
                body=b"{}",
            )
            self.assertEqual(status, 200)
            status, activated = request(
                api,
                f"/api/v1/configuration/revisions/{draft_id}/activate",
                method="POST",
                body=json.dumps({"expectedVersion": created["draftVersion"]}).encode("utf-8"),
            )
            self.assertEqual(status, 200)

            status, view = request(api, "/api/v1/system/settings")
            self.assertEqual(status, 200)
            self.assertEqual(view["revisionId"], draft_id)
            self.assertTrue(view["isActive"])
            self.assertEqual(view["settings"]["cachePath"], ".mediaflow/cache-2")
            self.assertEqual(view["settings"]["locale"], "zh-CN")
            self.assertEqual(
                view["sections"]["Database"]["cachePath"]["boundary"], "restart_required"
            )
            self.assertEqual(
                view["sections"]["Localization"]["locale"]["boundary"], "restart_required"
            )
            # Consumption evidence names the exact new snapshot but never claims
            # the restart-required values as hot-consumed readiness.
            evidence = view["consumption"]
            self.assertTrue(evidence["consumed"])
            self.assertEqual(evidence["revisionId"], draft_id)
            self.assertEqual(evidence["runtimeSnapshotId"], draft_id)
            self.assertNotIn("cachePath", evidence["consumedFields"])
            self.assertNotIn("locale", evidence["consumedFields"])
            self.assertIn("cachePath", evidence["restartRequiredFields"])
            self.assertIn("locale", evidence["restartRequiredFields"])
            self.assertIn("automation.maximumActiveJobs", evidence["consumedFields"])

            # The prior Active remains superseded and intact.
            prior = service.require(active.revision_id)
            self.assertEqual(prior.status.value, "superseded")
            self.assertIsNone(prior.document.get("locale"))
            self.assertEqual(prior.document["automation"]["maximumActiveJobs"], 100)

    def test_web_and_api_settings_parity_success_failure_and_recovery(self) -> None:
        script = APP_JS.decode("utf-8")
        web_view = _js_function_body(script, "renderSettings")
        # The served Web client must pin the same identity contract the API
        # defines: mutable Draft version for Draft edits, exact Active identity
        # for successor creation, and reopening of the returned Draft.
        self.assertIn("/api/v1/system/settings", web_view)
        self.assertIn("expectedVersion: data.draftVersion", web_view)
        self.assertNotIn("expectedVersion: data.revisionVersion", web_view)
        self.assertIn("expectedActiveRevisionId: data.revisionId", web_view)
        self.assertIn("expectedActiveVersion: data.revisionVersion", web_view)
        self.assertIn("expectedActiveDigest: data.revisionDigest", web_view)
        self.assertIn("renderSettings(settingsRevisionId)", web_view)

        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)
            revisions_before = len(repo.list_revisions(limit=100))

            # 1. Web enters Settings and reads the Active view.
            status, active_view = request(api, "/api/v1/system/settings")
            self.assertEqual(status, 200)
            self.assertTrue(active_view["isActive"])

            # 2. Web saves an edit from the Active view using the exact body
            #    construction of the served client.
            web_body = {
                "edits": [{"fieldPath": "automation.maximumActiveJobs", "value": 80}],
                "expectedActiveRevisionId": active_view["revisionId"],
                "expectedActiveVersion": active_view["revisionVersion"],
                "expectedActiveDigest": active_view["revisionDigest"],
            }
            status, created = request(
                api, "/api/v1/system/settings", method="PUT", body=json.dumps(web_body).encode()
            )
            self.assertEqual(status, 201)
            self.assertTrue(created["created"])
            draft_id = created["revisionId"]

            # 3. Web reopens the returned Draft; consumption stays bound to the
            #    Active, never to the Draft being edited.
            status, draft_view = request(api, f"/api/v1/system/settings?revisionId={draft_id}")
            self.assertEqual(status, 200)
            self.assertFalse(draft_view["isActive"])
            self.assertEqual(draft_view["consumption"]["revisionId"], active.revision_id)
            first_token = draft_view["draftVersion"]

            def draft_edit(value: int, token: int) -> bytes:
                return json.dumps(
                    {
                        "revisionId": draft_id,
                        "expectedVersion": token,
                        "edits": [{"fieldPath": "automation.maximumActiveJobs", "value": value}],
                    }
                ).encode("utf-8")

            # 4. First Draft edit with the mutable Draft version succeeds.
            status, updated = request(
                api, "/api/v1/system/settings", method="PUT", body=draft_edit(85, first_token)
            )
            self.assertEqual(status, 200)
            self.assertEqual(updated["settings"]["automation.maximumActiveJobs"], 85)

            # 5. A stale writer (second operator) advances the same Draft with
            #    an independent field edit; the Web replay with its now-stale
            #    token fails closed with bounded durable recovery evidence and
            #    zero side effects.
            status, _ = request(
                api,
                "/api/v1/system/settings",
                method="PUT",
                body=json.dumps(
                    {
                        "revisionId": draft_id,
                        "expectedVersion": updated["draftVersion"],
                        "edits": [{"fieldPath": "automation.staleJobAgeSeconds", "value": 7200}],
                    }
                ).encode("utf-8"),
            )
            self.assertEqual(status, 200)
            status, conflict = request(
                api, "/api/v1/system/settings", method="PUT", body=draft_edit(90, first_token)
            )
            self.assertEqual(status, 409)
            self.assertEqual(conflict["error"]["code"], "configuration_version_conflict")
            details = conflict["error"]["details"]
            self.assertEqual(details["revisionId"], draft_id)
            self.assertEqual(details["durableState"], "draft_preserved")
            self.assertEqual(details["sideEffects"], "none")
            self.assertTrue(details["retrySafe"])
            self.assertIn("refresh", details["nextAction"])

            # 6. Recovery: refresh the Draft and retry with the current token.
            status, refreshed = request(api, f"/api/v1/system/settings?revisionId={draft_id}")
            self.assertEqual(status, 200)
            self.assertNotEqual(refreshed["draftVersion"], first_token)
            status, recovered = request(
                api,
                "/api/v1/system/settings",
                method="PUT",
                body=draft_edit(90, refreshed["draftVersion"]),
            )
            self.assertEqual(status, 200)
            self.assertEqual(recovered["settings"]["automation.maximumActiveJobs"], 90)
            # The stale writer's independent edit is preserved, not overwritten.
            self.assertEqual(recovered["settings"]["automation.staleJobAgeSeconds"], 7200)

            # Prior Active, its values and the revision set remain intact; the
            # whole journey created exactly one settings Draft and started no
            # media work.
            self.assertEqual(service.active().revision_id, active.revision_id)
            self.assertEqual(service.active().document["automation"]["maximumActiveJobs"], 100)
            self.assertEqual(len(repo.list_revisions(limit=100)), revisions_before + 1)

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
        self.assertIn("settingsRevisionId", script)
        self.assertIn("expectedActiveRevisionId", script)
        # Draft edits send the mutable Draft version, never the revision sequence.
        self.assertIn("expectedVersion: data.draftVersion", script)
        self.assertNotIn("expectedVersion: data.revisionVersion", script)
        self.assertIn("['Draft version', data.draftVersion || '-']", script)
        self.assertIn("Validate and activate this Draft", script)
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

    def test_locale_and_timezone_are_explicit_restart_required(self) -> None:
        doc = example_document()
        projection = SystemSettings.from_document(doc).as_projection()
        self.assertEqual(
            projection["sections"]["Localization"]["locale"]["boundary"],
            "restart_required",
        )
        self.assertEqual(
            projection["sections"]["Localization"]["timezone"]["boundary"],
            "restart_required",
        )


if __name__ == "__main__":
    unittest.main()
