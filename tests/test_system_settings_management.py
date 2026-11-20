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

    def test_validation_rejects_retired_stale_age_field(self) -> None:
        edits = (SystemSettingsEdit("automation.staleJobAgeSeconds", 7200),)
        errors = validate_settings_edit(edits, bootstrap_database_path=None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], "field_retired")
        self.assertEqual(errors[0]["field"], "automation.staleJobAgeSeconds")

    def test_api_retired_field_edit_is_refused_with_zero_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)
            revisions_before = len(repo.list_revisions(limit=100))
            body = json.dumps(
                {
                    "expectedActiveRevisionId": active.revision_id,
                    "expectedActiveVersion": active.version,
                    "expectedActiveDigest": active.digest,
                    "edits": [{"fieldPath": "automation.staleJobAgeSeconds", "value": 7200}],
                }
            ).encode("utf-8")
            status, data = request(api, "/api/system/settings", method="PUT", body=body)
            self.assertEqual(status, 422, data)
            self.assertEqual(data["error"]["code"], "system_settings_invalid")
            errors = data["error"]["details"]["errors"]
            self.assertEqual(errors[0]["code"], "field_retired")
            self.assertEqual(service.active().revision_id, active.revision_id)
            self.assertEqual(len(repo.list_revisions(limit=100)), revisions_before)

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
            status, data = request(api, "/api/system/settings")
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

    def test_api_read_active_and_rejects_retired_draft_routes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)

            status, data = request(api, f"/api/system/settings?revisionId={active.revision_id}")
            self.assertEqual(status, 200)
            self.assertEqual(data["revisionId"], active.revision_id)
            self.assertTrue(data["isActive"])

            status, data = request(
                api, f"/api/configuration/revisions/{active.revision_id}/settings"
            )
            self.assertEqual(status, 200)
            self.assertTrue(data["isActive"])

            status, body = request(
                api, "/api/configuration/drafts/first", method="POST", body=b"{}"
            )
            self.assertEqual(status, 404)
            self.assertEqual(body["error"]["code"], "not_found")
            status, body = request(
                api,
                f"/api/configuration/revisions/{active.revision_id}/activate",
                method="POST",
                body=json.dumps({"expectedVersion": active.version}).encode("utf-8"),
            )
            self.assertEqual(status, 404)
            self.assertEqual(body["error"]["code"], "not_found")

    def test_api_apply_publishes_immediately_and_preserves_published_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)
            body = json.dumps(
                {
                    "settings": {
                        "automation.maximumActiveJobs": 75,
                        "operationalLogging.minimumLevel": "DEBUG",
                        "workflowRetry.maxAttempts": 5,
                    },
                    "expectedActiveRevisionId": active.revision_id,
                    "expectedActiveVersion": active.revision_sequence,
                    "expectedActiveDigest": active.digest,
                }
            ).encode("utf-8")
            status, data = request(api, "/api/system/settings", method="PUT", body=body)
            self.assertEqual(status, 200)
            self.assertTrue(data["published"])
            self.assertNotEqual(data["revisionId"], active.revision_id)
            self.assertTrue(data["isActive"])
            self.assertEqual(data["settings"]["automation.maximumActiveJobs"], 75)
            self.assertEqual(data["settings"]["operationalLogging.minimumLevel"], "DEBUG")
            self.assertEqual(data["settings"]["workflowRetry.maxAttempts"], 5)

            active_after = service.active()
            self.assertEqual(active_after.revision_id, data["revisionId"])
            self.assertEqual(
                active_after.document.get("automation", {}).get("maximumActiveJobs"), 75
            )
            prior = service.require(active.revision_id)
            self.assertEqual(prior.status.value, "superseded")
            self.assertEqual(prior.document.get("automation", {}).get("maximumActiveJobs"), 100)
            statuses = {revision.status.value for revision in repo.list_revisions(limit=100)}
            self.assertEqual(statuses, {"active", "superseded"})

    def test_api_exact_submission_reconciles_without_a_second_publish(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)
            submission_id = "settings-apply-e2e-1"
            body = json.dumps(
                {
                    "submissionId": submission_id,
                    "expectedActiveRevisionId": active.revision_id,
                    "expectedActiveVersion": active.revision_sequence,
                    "expectedActiveDigest": active.digest,
                    "edits": [{"fieldPath": "automation.maximumActiveJobs", "value": 77}],
                }
            ).encode("utf-8")
            status, applied = request(api, "/api/system/settings", method="PUT", body=body)
            self.assertEqual(status, 200, applied)
            published_revision = applied["revisionId"]
            before = len(repo.list_revisions(limit=100))
            status, reconciled = request(
                api,
                f"/api/system/settings/reconcile?submissionId={submission_id}",
            )
            self.assertEqual(status, 200, reconciled)
            self.assertEqual(reconciled["state"], "COMMITTED")
            self.assertTrue(reconciled["committed"])
            self.assertEqual(reconciled["committedRevisionId"], published_revision)
            self.assertEqual(reconciled["sideEffects"], "none")
            self.assertEqual(len(repo.list_revisions(limit=100)), before)
            self.assertEqual(service.active().revision_id, published_revision)

    def test_api_stale_active_apply_returns_conflict_without_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)
            before = len(repo.list_revisions(limit=100))
            body = json.dumps(
                {
                    "expectedActiveVersion": active.revision_sequence + 99,
                    "settings": {"workflowRetry.maxAttempts": 7},
                }
            ).encode("utf-8")
            status, data = request(api, "/api/system/settings", method="PUT", body=body)
            self.assertEqual(status, 409)
            self.assertEqual(data["error"]["code"], "configuration_version_conflict")
            self.assertEqual(data["error"]["details"]["durableState"], "active_preserved")
            self.assertEqual(service.active().revision_id, active.revision_id)
            self.assertEqual(len(repo.list_revisions(limit=100)), before)

    def test_api_repeated_apply_uses_the_new_active_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)
            view = service.active()
            for value in (80, 85, 90):
                body = json.dumps(
                    {
                        "expectedActiveRevisionId": view.revision_id,
                        "expectedActiveVersion": view.revision_sequence,
                        "expectedActiveDigest": view.digest,
                        "edits": [
                            {
                                "fieldPath": "automation.maximumActiveJobs",
                                "value": value,
                            }
                        ],
                    }
                ).encode("utf-8")
                status, updated = request(api, "/api/system/settings", method="PUT", body=body)
                self.assertEqual(status, 200)
                self.assertEqual(updated["settings"]["automation.maximumActiveJobs"], value)
                self.assertTrue(updated["isActive"])
                view = service.active()
                self.assertEqual(view.revision_id, updated["revisionId"])
            self.assertEqual(len(repo.list_revisions(limit=100)), 4)
            self.assertFalse(
                any(
                    revision.status.value in {"draft", "validated"}
                    for revision in repo.list_revisions(limit=100)
                )
            )

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
                status, data = request(api, "/api/system/settings")
            self.assertEqual(status, 200)
            self.assertFalse(data["consumption"]["consumed"])
            self.assertEqual(data["consumption"]["reason"], "runtime_snapshot_mismatch")
            self.assertEqual(data["consumption"]["revisionId"], active.revision_id)

    def test_api_rejects_retired_draft_parameters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)
            before = len(repo.list_revisions(limit=100))
            for field, value in (
                ("revisionId", active.revision_id),
                ("expectedVersion", 1),
                ("fromActive", True),
            ):
                body = json.dumps({field: value, "settings": {"locale": "en-US"}}).encode("utf-8")
                status, data = request(api, "/api/system/settings", method="PUT", body=body)
                self.assertEqual(status, 400)
                self.assertEqual(data["error"]["code"], "invalid_request")
            self.assertEqual(service.active().revision_id, active.revision_id)
            self.assertEqual(len(repo.list_revisions(limit=100)), before)

    def test_api_rbac_enforcement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)

            # Unauthenticated -> 401
            status, _ = request(api, "/api/system/settings", token=None)
            self.assertEqual(status, 401)

            # Viewer (read-only) -> GET 200, PUT 403
            status, _ = request(api, "/api/system/settings", token="viewer-token")
            self.assertEqual(status, 200)

            body = json.dumps({"settings": {"automation.maximumActiveJobs": 50}}).encode("utf-8")
            status, data = request(
                api, "/api/system/settings", method="PUT", body=body, token="viewer-token"
            )
            self.assertEqual(status, 403)
            self.assertEqual(data["error"]["code"], "forbidden")

    def test_api_rejects_immutable_database_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)
            body = json.dumps(
                {"settings": {"persistence.databasePath": "tampered.sqlite3"}}
            ).encode("utf-8")
            status, data = request(api, "/api/system/settings", method="PUT", body=body)
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
            status, data = request(api, "/api/system/settings", method="PUT", body=body)
            self.assertEqual(status, 200)

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
            status, body = request(api, "/api/system/settings")
            self.assertEqual(status, 503)
            self.assertEqual(body["error"]["code"], "configuration_unavailable")
            details = body["error"]["details"]
            self.assertEqual(details["reason"], "active_missing")
            self.assertEqual(details["durableState"], "managed_active_unavailable")
            self.assertEqual(details["sideEffects"], "none")
            self.assertTrue(details["retrySafe"])
            self.assertIn("replacement", details["nextAction"])
            self.assertEqual(details["revisionId"], active.revision_id)
            self.assertEqual(details["digest"], active.digest)

            # Edit fails closed as well: no settings Draft is created.
            body = json.dumps({"edits": [{"fieldPath": "locale", "value": "en-US"}]}).encode(
                "utf-8"
            )
            status, _ = request(api, "/api/system/settings", method="PUT", body=body)
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

            status, body = request(api, "/api/system/settings")
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
                "/api/system/settings",
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

            status, body = request(api, "/api/system/settings")
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
                "/api/system/settings",
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
                    "expectedActiveRevisionId": active.revision_id,
                    "expectedActiveVersion": active.revision_sequence,
                    "expectedActiveDigest": active.digest,
                    "edits": [
                        {"fieldPath": "cachePath", "value": ".mediaflow/cache-2"},
                        {"fieldPath": "locale", "value": "zh-CN"},
                    ],
                }
            ).encode("utf-8")
            status, applied = request(api, "/api/system/settings", method="PUT", body=body)
            self.assertEqual(status, 200)
            self.assertTrue(applied["published"])
            new_id = applied["revisionId"]
            self.assertNotEqual(new_id, active.revision_id)

            status, view = request(api, "/api/system/settings")
            self.assertEqual(status, 200)
            self.assertEqual(view["revisionId"], new_id)
            self.assertTrue(view["isActive"])
            self.assertEqual(view["settings"]["cachePath"], ".mediaflow/cache-2")
            self.assertEqual(view["settings"]["locale"], "zh-CN")
            self.assertEqual(
                view["sections"]["Database"]["cachePath"]["boundary"], "restart_required"
            )
            self.assertEqual(
                view["sections"]["Localization"]["locale"]["boundary"], "restart_required"
            )
            evidence = view["consumption"]
            self.assertEqual(evidence["revisionId"], new_id)
            self.assertEqual(evidence["runtimeSnapshotId"], new_id)
            self.assertNotIn("cachePath", evidence["consumedFields"])
            self.assertNotIn("locale", evidence["consumedFields"])
            self.assertIn("cachePath", evidence["restartRequiredFields"])
            self.assertIn("locale", evidence["restartRequiredFields"])

            prior = service.require(active.revision_id)
            self.assertEqual(prior.status.value, "superseded")
            self.assertIsNone(prior.document.get("locale"))
            self.assertEqual(prior.document["automation"]["maximumActiveJobs"], 100)

    def test_settings_api_success_failure_and_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api, service, active, repo = setup_test_api(directory)
            revisions_before = len(repo.list_revisions(limit=100))

            status, active_view = request(api, "/api/system/settings")
            self.assertEqual(status, 200)
            self.assertTrue(active_view["isActive"])

            base_body = {
                "expectedActiveRevisionId": active_view["revisionId"],
                "expectedActiveVersion": active_view["revisionVersion"],
                "expectedActiveDigest": active_view["revisionDigest"],
            }

            def apply(value: int, authority: dict) -> tuple[int, dict]:
                body = {
                    **authority,
                    "edits": [
                        {
                            "fieldPath": "automation.maximumActiveJobs",
                            "value": value,
                        }
                    ],
                }
                return request(
                    api,
                    "/api/system/settings",
                    method="PUT",
                    body=json.dumps(body).encode("utf-8"),
                )

            status, first = apply(80, base_body)
            self.assertEqual(status, 200)
            self.assertTrue(first["published"])
            self.assertNotEqual(first["revisionId"], active.revision_id)
            self.assertTrue(first["isActive"])
            self.assertEqual(first["settings"]["automation.maximumActiveJobs"], 80)

            # The previous token is stale after the first publication and never
            # silently overwrites the winning Active.
            status, conflict = apply(85, base_body)
            self.assertEqual(status, 409)
            self.assertEqual(conflict["error"]["code"], "configuration_version_conflict")
            self.assertEqual(conflict["error"]["details"]["durableState"], "active_preserved")
            self.assertEqual(service.active().document["automation"]["maximumActiveJobs"], 80)

            # Recovery: read the actual Active identity, then apply again.
            status, refreshed = request(api, "/api/system/settings")
            self.assertEqual(status, 200)
            status, recovered = apply(
                90,
                {
                    "expectedActiveRevisionId": refreshed["revisionId"],
                    "expectedActiveVersion": refreshed["revisionVersion"],
                    "expectedActiveDigest": refreshed["revisionDigest"],
                },
            )
            self.assertEqual(status, 200)
            self.assertEqual(recovered["settings"]["automation.maximumActiveJobs"], 90)
            self.assertEqual(service.active().revision_id, recovered["revisionId"])
            self.assertEqual(len(repo.list_revisions(limit=100)), revisions_before + 2)
            self.assertFalse(
                any(
                    revision.status.value in {"draft", "validated"}
                    for revision in repo.list_revisions(limit=100)
                )
            )

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
