from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.configuration_management import (
    ManagedConfigurationStatus,
)
from mediaflow.domain.package_exchange import (
    CONFIGURATION_PACKAGE_KIND,
    canonical_digest,
    redact_configuration_document,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import PersistentResultRecord
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import APP_JS
from mediaflow.interfaces.service_api import MediaFlowApi


def example_document(root: Path, history: str = "history.jsonl") -> dict:
    document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
    document["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
    document["storages"][0]["rootPath"] = str(root / "source")
    document["storages"][1]["rootPath"] = str(root / "target")
    document["resourceLibraries"][0]["storagePath"] = "incoming"
    document["mediaLibraries"][0]["rootPath"] = "Movies"
    document["historyPath"] = str(root / history)
    return document


def activate(service: ManagedConfigurationService, document: dict, actor: str = "bootstrap"):
    draft = service.import_draft(document, actor=actor)
    validated = service.validate(draft.revision_id, actor=actor)
    return service.activate(validated.revision_id, expected_version=validated.version, actor=actor)


def request(
    api: MediaFlowApi,
    path: str,
    *,
    method: str = "GET",
    body: object | None = None,
    token: str = "admin-token",
    query: str = "",
) -> tuple[int, object]:
    if "?" in path and not query:
        path, query = path.split("?", 1)
    payload = b"" if body is None else json.dumps(body).encode("utf-8")
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(payload)),
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(payload),
        "HTTP_AUTHORIZATION": f"Bearer {token}",
    }
    result = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(result)


def setup_api(root: Path):
    runtime = root / "runtime.sqlite3"
    config_repository = SQLiteConfigurationRepository(root / "configuration.sqlite3")
    task_repository = SQLiteTaskRepository(runtime)
    config_repository.__enter__()
    task_repository.__enter__()
    try:
        service = ManagedConfigurationService(
            config_repository,
            bootstrap_database_path=str(runtime),
        )
        first = activate(service, example_document(root, "first-history.jsonl"))
        admin = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
        viewer = ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
        api = MediaFlowApi(
            task_repository,
            None,
            principals=(admin, viewer),
            configuration_service=service,
            configuration_snapshot_id=first.revision_id,
            configuration_snapshot_digest=first.digest,
            bootstrap_document=example_document(root, "first-history.jsonl"),
        )
        return api, service, task_repository, first
    except Exception:
        config_repository.__exit__(None, None, None)
        task_repository.__exit__(None, None, None)
        raise


class PackageRedactionTests(unittest.TestCase):
    def test_environment_references_preserved_and_literal_secrets_redacted(self) -> None:
        document = example_document(Path(tempfile.gettempdir()))
        document["storages"][0]["options"] = {
            "tokenEnv": "OPENLIST_TOKEN",
            "baseUrl": "https://example.invalid",
        }
        document["notifications"]["webhooks"][0]["secret"] = "literal-password"
        document["api"]["fallbackToken"] = "literal-token"
        safe, evidence = redact_configuration_document(document)

        references = [entry for entry in evidence if entry["kind"] == "environment_reference"]
        redacted = [entry for entry in evidence if entry["kind"] == "redacted_literal"]
        self.assertIn("OPENLIST_TOKEN", json.dumps(safe))
        self.assertEqual(
            {
                "api.principals[0].tokenEnv",
                "storages[0].options.tokenEnv",
                "notifications.webhooks[0].secretEnv",
            },
            {entry["field"] for entry in references},
        )
        self.assertIn("notifications.webhooks[0].secret", {entry["field"] for entry in redacted})
        self.assertIn("api.fallbackToken", {entry["field"] for entry in redacted})
        self.assertNotIn("literal-password", json.dumps(safe))
        self.assertNotIn("literal-token", json.dumps(safe))


class PackageExchangeApiTests(unittest.TestCase):
    def _bootstrap(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        api, service, task_repository, first = setup_api(root)
        self.addCleanup(task_repository.close)
        self.addCleanup(service.repository.close)
        return api, service, task_repository, first

    def test_status_exposes_schema_version_and_currentness(self) -> None:
        api, service, _, active = self._bootstrap()
        status_code, document = request(api, "/api/v1/configuration/packages")
        self.assertEqual(status_code, 200)
        self.assertEqual(document["configurationPackageSchemaVersion"], 1)
        self.assertEqual(document["packageKinds"]["configuration"], CONFIGURATION_PACKAGE_KIND)
        self.assertEqual(document["currentActive"]["revisionId"], active.revision_id)
        self.assertEqual(document["currentActive"]["digest"], active.digest)
        self.assertIsNone(document["currentDraft"])
        self.assertIn("active", document["supportedRevisionStatuses"])

    def test_export_active_and_explicit_draft_validated_superseded(self) -> None:
        api, service, _, active = self._bootstrap()
        root = Path(self.temporary.name)

        # Active export with no Draft.
        code, active_package = request(api, "/api/v1/configuration/packages/export/configuration")
        self.assertEqual(code, 200)
        self.assertEqual(active_package["source"]["status"], "active")
        self.assertTrue(active_package["currentness"]["sourceIsCurrent"])

        # Draft then Validated package from the same Active base.
        draft = service.import_draft(example_document(root, "draft.jsonl"), actor="tester")
        code, draft_package = request(
            api,
            "/api/v1/configuration/packages/export/configuration",
            query=f"revisionId={draft.revision_id}",
        )
        self.assertEqual(code, 200)
        self.assertEqual(draft_package["source"]["status"], "draft")
        self.assertFalse(draft_package["currentness"]["sourceIsCurrent"])

        validated = service.validate(draft.revision_id, actor="tester")
        code, validated_package = request(
            api,
            "/api/v1/configuration/packages/export/configuration",
            query=f"revisionId={validated.revision_id}",
        )
        self.assertEqual(code, 200)
        self.assertEqual(validated_package["source"]["status"], "validated")
        self.assertEqual(validated_package["source"]["digest"], validated.digest)
        self.assertEqual(
            validated_package["payload"]["documentDigest"],
            canonical_digest(validated_package["payload"]["document"]),
        )

        # Superseded revision after a second checked activation.
        second = activate(service, example_document(root, "second-history.jsonl"))
        superseded = next(
            revision
            for revision in service.repository.list_revisions()
            if revision.status is ManagedConfigurationStatus.SUPERSEDED
        )
        code, superseded_package = request(
            api,
            "/api/v1/configuration/packages/export/configuration",
            query=f"revisionId={superseded.revision_id}",
        )
        self.assertEqual(code, 200)
        self.assertEqual(superseded_package["source"]["status"], "superseded")
        self.assertEqual(
            superseded_package["currentness"]["currentActiveRevisionId"],
            second.revision_id,
        )
        self.assertEqual(
            active_package["currentness"]["currentActiveRevisionId"], active.revision_id
        )

    def test_configuration_export_is_secret_free_and_bounded(self) -> None:
        api, service, _, _ = self._bootstrap()
        draft = service.import_draft(
            {
                **example_document(Path(self.temporary.name), "secret.jsonl"),
                "api": {
                    "principals": [
                        {
                            "id": "admin",
                            "tokenEnv": "MEDIAFLOW_API_TOKEN",
                            "roles": ["admin"],
                            "enabled": True,
                        }
                    ],
                    "storedToken": "top-secret-token",
                },
            },
            actor="tester",
        )
        code, package = request(
            api,
            "/api/v1/configuration/packages/export/configuration",
            query=f"revisionId={draft.revision_id}",
        )
        self.assertEqual(code, 200)
        self.assertEqual(package["source"]["status"], "draft")
        encoded = json.dumps(package, ensure_ascii=False)
        self.assertNotIn("top-secret-token", encoded)
        entries = package["redaction"]["entries"]
        self.assertTrue(entries)
        self.assertIn(
            "MEDIAFLOW_API_TOKEN",
            json.dumps([entry for entry in entries if entry["kind"] == "environment_reference"]),
        )
        self.assertIn(
            "MEDIAFLOW_WEBHOOK_SECRET",
            json.dumps(package["payload"]["document"]),
        )
        self.assertLess(len(encoded.encode("utf-8")), 1_500_000)

    def test_import_creates_draft_and_does_not_activate_or_overwrite(self) -> None:
        api, service, _, active = self._bootstrap()
        code, package = request(api, "/api/v1/configuration/packages/export/configuration")
        self.assertEqual(code, 200)

        code, imported = request(
            api,
            "/api/v1/configuration/packages",
            method="POST",
            body={"package": package},
        )
        self.assertEqual(code, 201)
        self.assertEqual(imported["action"], "created")
        self.assertEqual(imported["revision"]["status"], "draft")
        self.assertEqual(imported["revision"]["revisionId"], imported["currentDraft"]["revisionId"])
        self.assertEqual(service.active().revision_id, active.revision_id)
        self.assertNotEqual(service.active().revision_id, imported["revision"]["revisionId"])

        # A second import must fail closed; it cannot overwrite the current Draft.
        code, conflict = request(
            api,
            "/api/v1/configuration/packages",
            method="POST",
            body={"package": package},
        )
        self.assertEqual(code, 409)
        self.assertEqual(conflict["error"]["code"], "package_import_draft_conflict")
        self.assertEqual(
            conflict["error"]["details"]["currentDraft"]["revisionId"],
            imported["revision"]["revisionId"],
        )
        self.assertEqual(conflict["error"]["details"]["sideEffects"], "none")
        self.assertTrue(conflict["error"]["details"]["retrySafe"])
        revisions = service.repository.list_revisions()
        self.assertEqual(
            [revision.revision_id for revision in revisions].count(
                imported["revision"]["revisionId"]
            ),
            1,
        )

    def test_import_updates_exact_draft_with_explicit_recovery_identity(self) -> None:
        api, service, _, active = self._bootstrap()
        code, package = request(api, "/api/v1/configuration/packages/export/configuration")
        self.assertEqual(code, 200)
        code, imported = request(
            api,
            "/api/v1/configuration/packages",
            method="POST",
            body={"package": package},
        )
        self.assertEqual(code, 201)
        draft = service.repository.get_revision(imported["revision"]["revisionId"])
        self.assertIsNotNone(draft)
        assert draft is not None

        changed = json.loads(json.dumps(package))
        changed["payload"]["document"]["historyPath"] = str(
            Path(self.temporary.name) / "recovery-history.jsonl"
        )
        changed["payload"]["documentDigest"] = canonical_digest(changed["payload"]["document"])
        changed["packageDigest"] = canonical_digest(changed["payload"])
        code, updated = request(
            api,
            "/api/v1/configuration/packages",
            method="POST",
            body={
                "package": changed,
                "recovery": {
                    "replaceDraft": True,
                    "expectedRevisionId": draft.revision_id,
                    "expectedVersion": draft.version,
                    "expectedDigest": draft.digest,
                },
            },
        )
        self.assertEqual(code, 200)
        self.assertEqual(updated["action"], "updated")
        self.assertGreater(updated["revision"]["version"], draft.version)
        self.assertEqual(service.active().revision_id, active.revision_id)
        self.assertEqual(
            service.repository.get_revision(draft.revision_id).version,
            updated["revision"]["version"],
        )

    def test_stale_package_fails_closed_with_current_active_evidence(self) -> None:
        api, service, _, first = self._bootstrap()
        code, package = request(api, "/api/v1/configuration/packages/export/configuration")
        self.assertEqual(code, 200)
        activate(service, example_document(Path(self.temporary.name), "later.jsonl"))

        code, stale = request(
            api,
            "/api/v1/configuration/packages",
            method="POST",
            body={"package": package},
        )
        self.assertEqual(code, 409)
        self.assertEqual(stale["error"]["code"], "package_stale")
        details = stale["error"]["details"]
        self.assertNotEqual(
            details["currentActive"]["revisionId"],
            first.revision_id,
        )
        self.assertIsNone(details["currentDraft"])
        self.assertEqual(details["sideEffects"], "none")
        self.assertEqual(len(service.repository.list_revisions()), 2)

    def test_invalid_unsupported_digest_and_secret_packages_fail_closed(self) -> None:
        api, service, _, active = self._bootstrap()
        code, package = request(api, "/api/v1/configuration/packages/export/configuration")
        self.assertEqual(code, 200)

        def attempt(changed, expected_code: str):
            status, response = request(
                api,
                "/api/v1/configuration/packages",
                method="POST",
                body={"package": changed},
            )
            self.assertEqual(status, 422)
            self.assertEqual(response["error"]["code"], expected_code)
            self.assertEqual(response["error"]["details"]["sideEffects"], "none")
            return response

        unsupported = json.loads(json.dumps(package))
        unsupported["packageSchemaVersion"] = 99
        attempt(unsupported, "unsupported_package_version")

        invalid_schema = {
            "packageKind": CONFIGURATION_PACKAGE_KIND,
            "packageSchemaVersion": 1,
            "packageVersion": 1,
        }
        attempt(invalid_schema, "invalid_schema")

        digest_mismatch = json.loads(json.dumps(package))
        digest_mismatch["payload"]["documentDigest"] = "0" * 64
        attempt(digest_mismatch, "digest_mismatch")

        secret = json.loads(json.dumps(package))
        secret["payload"]["document"]["api"]["storedToken"] = "literal-secret-value"
        secret["payload"]["documentDigest"] = canonical_digest(secret["payload"]["document"])
        secret["packageDigest"] = canonical_digest(secret["payload"])
        response = attempt(secret, "literal_secret_rejected")

        self.assertEqual(service.active().revision_id, active.revision_id)
        self.assertEqual(len(service.repository.list_revisions()), 1)
        self.assertNotIn("literal-secret-value", json.dumps(response))

    def test_result_export_is_bounded_ordered_and_secret_free(self) -> None:
        api, service, repository, active = self._bootstrap()
        coordinator = PersistentTaskCoordinator(repository, repository)
        task = coordinator.create(
            "preview",
            execute_authorized=False,
            configuration_snapshot_id=active.revision_id,
            configuration_snapshot_digest=active.digest,
        )
        base = datetime.now(UTC)
        item = coordinator.record_discovered(
            task.task_id,
            "source",
            "source-library",
            "movie.mkv",
            "movie.mkv",
        )
        for index in range(3):
            repository.append_result(
                PersistentResultRecord(
                    f"result-{index}",
                    task.task_id,
                    item.item_id,
                    "source",
                    "movie.mkv",
                    "target",
                    "Movies/movie.mkv",
                    "C",
                    "tmdb",
                    "101",
                    "C",
                    "A",
                    "A",
                    "A",
                    "MOVE",
                    "dry_run",
                    base + timedelta(seconds=index),
                    title=f"Movie {index}",
                    error=(
                        "Authorization: Bearer secret-token password=hunter2"
                        if index == 0
                        else None
                    ),
                )
            )

        code, package = request(
            api,
            "/api/v1/configuration/packages/export/results",
            query=f"taskId={task.task_id}&limit=2",
        )
        self.assertEqual(code, 200)
        self.assertEqual(package["packageKind"], "mediaflow.results.v1")
        self.assertEqual(len(package["results"]), 2)
        self.assertTrue(package["truncated"])
        self.assertEqual(
            [row["resultId"] for row in package["results"]],
            ["result-0", "result-1"],
        )
        encoded = json.dumps(package, ensure_ascii=False)
        self.assertNotIn("secret-token", encoded)
        self.assertNotIn("hunter2", encoded)
        self.assertIn("[redacted]", encoded)
        self.assertEqual(package["results"][1]["recognitionType"], "C")
        self.assertEqual(package["results"][1]["providerId"], "101")

        code, missing = request(
            api,
            "/api/v1/configuration/packages/export/results",
            query="taskId=missing",
        )
        self.assertEqual(code, 404)
        self.assertEqual(missing["error"]["code"], "task_not_found")

    def test_result_export_digest_covers_secret_redacted_task_command(self) -> None:
        api, service, repository, active = self._bootstrap()
        coordinator = PersistentTaskCoordinator(repository, repository)
        task = coordinator.create(
            "preview password=hunter2",
            execute_authorized=False,
            configuration_snapshot_id=active.revision_id,
            configuration_snapshot_digest=active.digest,
        )
        base = datetime.now(UTC)
        item = coordinator.record_discovered(
            task.task_id,
            "source",
            "source-library",
            "movie.mkv",
            "movie.mkv",
        )
        repository.append_result(
            PersistentResultRecord(
                "result-0",
                task.task_id,
                item.item_id,
                "source",
                "movie.mkv",
                "target",
                "Movies/movie.mkv",
                "C",
                "tmdb",
                "101",
                "C",
                "A",
                "A",
                "A",
                "MOVE",
                "dry_run",
                base,
                title="Movie 0",
            )
        )

        code, package = request(
            api,
            "/api/v1/configuration/packages/export/results",
            query=f"taskId={task.task_id}&limit=10",
        )
        self.assertEqual(code, 200)
        self.assertEqual(
            package["source"]["taskCommand"],
            "preview password=[redacted]",
        )
        self.assertNotIn("hunter2", json.dumps(package, ensure_ascii=False))
        self.assertEqual(
            package["packageDigest"],
            canonical_digest({"results": package["results"], "source": package["source"]}),
        )
        self.assertIn(
            {"field": "source.taskCommand", "kind": "redacted_text"},
            package["redaction"]["entries"],
        )
        self.assertGreaterEqual(package["redaction"]["entryCount"], 1)

    def test_permissions_audit_and_no_workflow_side_effects(self) -> None:
        api, service, repository, active = self._bootstrap()
        code, package = request(api, "/api/v1/configuration/packages/export/configuration")
        self.assertEqual(code, 200)
        before_tasks = len(repository.list_tasks(limit=100))

        # Viewer may read/export but cannot import.
        code, _ = request(
            api,
            "/api/v1/configuration/packages/export/configuration",
            token="viewer-token",
        )
        self.assertEqual(code, 200)
        code, denied = request(
            api,
            "/api/v1/configuration/packages",
            method="POST",
            body={"package": package},
            token="viewer-token",
        )
        self.assertEqual(code, 403)
        self.assertEqual(denied["error"]["code"], "forbidden")

        code, imported = request(
            api,
            "/api/v1/configuration/packages",
            method="POST",
            body={"package": package},
        )
        self.assertEqual(code, 201)
        self.assertEqual(len(repository.list_tasks(limit=100)), before_tasks)
        self.assertEqual(service.active().revision_id, active.revision_id)
        actions = {record.action for record in repository.list_security_audit(limit=100)}
        self.assertIn("configuration_package_export", actions)
        self.assertIn("configuration_package_import", actions)
        for record in repository.list_security_audit(limit=100):
            combined = f"{record.route} {record.action} {record.outcome}"
            self.assertNotIn("secret-token", combined)
            self.assertNotIn("MEDIAFLOW_API_TOKEN", combined)


class PackageExchangeWebParityTests(unittest.TestCase):
    def test_served_web_asset_uses_the_same_package_endpoints(self) -> None:
        script = APP_JS.decode()
        self.assertIn("'Package exchange (Advanced/support)'", script)
        self.assertIn("/api/v1/configuration/packages", script)
        self.assertIn("/api/v1/configuration/packages/export/configuration", script)
        self.assertIn("/api/v1/configuration/packages/export/results?limit=100", script)
        self.assertIn("Export selected configuration package", script)
        self.assertIn("Import package as Draft/recovery candidate", script)
        self.assertIn("Export result package", script)
        self.assertIn("currentDraft", script)
        self.assertIn("Current Draft", script)
        self.assertNotIn("literal-secret-value", script)

    def test_web_endpoint_contract_replays_shared_api_success_and_conflict(self) -> None:
        script = APP_JS.decode()
        self.assertIn(
            "'/api/v1/configuration/packages/export/configuration' + query",
            script,
        )
        self.assertIn("JSON.stringify({package: parsed})", script)
        self.assertIn("/api/v1/configuration/packages/export/results?limit=100", script)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, service, repository, _ = setup_api(root)
            try:
                # The Web reads the same package status/currentness surface.
                code, status_view = request(api, "/api/v1/configuration/packages")
                self.assertEqual(code, 200)
                self.assertIsNotNone(status_view["currentActive"]["revisionId"])

                # Web export request shape used by the served client.
                code, exported = request(
                    api,
                    "/api/v1/configuration/packages/export/configuration",
                )
                self.assertEqual(code, 200)
                self.assertEqual(
                    exported["currentness"]["currentActiveRevisionId"],
                    status_view["currentActive"]["revisionId"],
                )

                # Web import request shape: one supported package object.
                code, imported = request(
                    api,
                    "/api/v1/configuration/packages",
                    method="POST",
                    body={"package": exported},
                )
                self.assertEqual(code, 201)
                self.assertEqual(imported["action"], "created")

                # The same Web control on a stale package fails through the
                # shared API and displays the same durable recovery details via
                # ``errorText``.
                stale = json.loads(json.dumps(exported))
                stale["packageSchemaVersion"] = 99
                code, failed = request(
                    api,
                    "/api/v1/configuration/packages",
                    method="POST",
                    body={"package": stale},
                )
                self.assertEqual(code, 422)
                self.assertEqual(failed["error"]["code"], "unsupported_package_version")
                self.assertEqual(failed["error"]["details"]["sideEffects"], "none")
                self.assertEqual(service.active().status.value, "active")
                self.assertEqual(len(service.repository.list_revisions()), 2)
            finally:
                repository.close()
                service.repository.close()


if __name__ == "__main__":
    unittest.main()
