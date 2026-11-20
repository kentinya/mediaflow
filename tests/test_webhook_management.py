from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.configuration_integrity import (
    MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION,
    canonical_document_digest,
)
from mediaflow.domain.configuration_management import (
    ConfigurationObjectKind,
    ManagedConfigurationRevision,
    ManagedConfigurationStatus,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
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
):
    statuses = []
    environment = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": str(len(body)),
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(body),
        "HTTP_AUTHORIZATION": f"Bearer {token}" if token else "",
    }
    payload = b"".join(api(environment, lambda status, headers: statuses.append(status)))
    parsed = json.loads(payload) if payload else {}
    return int(statuses[0].split()[0]), parsed


class FakeTransport:
    def __init__(self, *results):
        self.results = list(results or (204,))
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class MutatingTransport:
    """Fake transport that edits the same Draft revision while sending."""

    def __init__(self):
        self.configuration = None
        self.revision_id = None
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        if self.configuration is None or self.revision_id is None:
            return 204
        revision = self.configuration.require(self.revision_id)
        objects = ConfigurationObjectService(self.configuration)
        value = webhook_document()
        value["events"] = ["task.completed", "task.failed", "schedule.emitted"]
        objects.mutate(
            self.revision_id,
            ConfigurationObjectKind.WEBHOOK_DEFINITION,
            object_id=value["id"],
            value=value,
            expected_version=revision.version,
            actor="concurrent-transport",
        )
        return 204


def webhook_document(**changes):
    value = {
        "id": "ops-webhook",
        "url": "https://example.invalid/hooks/mediaflow",
        "secretEnv": "MEDIAFLOW_WEBHOOK_SECRET",
        "events": ["task.completed", "task.failed"],
        "enabled": True,
        "timeoutSeconds": 10,
        "maxAttempts": 5,
        "baseRetrySeconds": 5,
        "maxRetrySeconds": 300,
    }
    value.update(changes)
    return value


class WebhookManagementHarness:
    def __init__(self, directory: str, transport=None):
        self.directory = Path(directory)
        doc = example_document()
        runtime_database = str(self.directory / "runtime.sqlite3")
        doc["persistence"]["databasePath"] = runtime_database
        source_root = self.directory / "source"
        target_root = self.directory / "target"
        (source_root / "incoming").mkdir(parents=True, exist_ok=True)
        (target_root / "Movies").mkdir(parents=True, exist_ok=True)
        for storage in doc.get("storages", []):
            storage["rootPath"] = (
                str(source_root) if storage.get("id") == "source-storage" else str(target_root)
            )
        self.runtime_database = runtime_database
        self.config_repository = SQLiteConfigurationRepository(
            self.directory / "configuration.sqlite3"
        )
        self.configuration = ManagedConfigurationService(
            self.config_repository,
            bootstrap_database_path=runtime_database,
        )
        self.draft = self.configuration.import_draft(doc, actor="bootstrap")
        self.repository = SQLiteTaskRepository(self.directory / "runtime.sqlite3")
        admin = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
        viewer = ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
        self.api = MediaFlowApi(
            self.repository,
            principals=(admin, viewer),
            configuration_service=self.configuration,
            bootstrap_document=doc,
            webhook_transport=transport or FakeTransport(204),
        )

    def close(self):
        self.repository.close()
        self.config_repository.close()


def _activate(harness):
    validated = harness.configuration.validate(harness.draft.revision_id, actor="bootstrap")
    return harness.configuration.activate(
        validated.revision_id,
        expected_version=validated.version,
        actor="bootstrap",
    )


def _accept_historical_webhook(harness):
    """Publish one Webhook definition that still stores the earlier event names.

    This is the Slice Base shape: the exact document was accepted when
    ``job.*`` was the current spelling, so its stored bytes and digest stay
    untouched while every current read presents the Task lifecycle meaning.
    """

    legacy = example_document()
    webhook = legacy.pop("webhooks")[0]
    stored_events = ["job.completed", "job.failed", "schedule.emitted"]
    webhook["events"] = stored_events
    webhook["enabled"] = True
    legacy["notifications"]["webhooks"] = [webhook]
    legacy["persistence"]["databasePath"] = harness.runtime_database
    now = datetime.now(UTC)
    accepted = harness.config_repository.create_revision(
        ManagedConfigurationRevision(
            "previous-version-webhook",
            1,
            ManagedConfigurationStatus.DRAFT,
            MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION,
            canonical_document_digest(legacy),
            legacy,
            now,
            now,
        )
    )
    validated = harness.configuration.validate(accepted.revision_id, actor="bootstrap")
    active = harness.configuration.activate(
        accepted.revision_id,
        expected_version=validated.version,
        actor="bootstrap",
    )
    return accepted, active, stored_events


class WebhookManagementTests(unittest.TestCase):
    def test_accepted_historical_webhook_is_projected_with_current_events(self) -> None:
        """An accepted definition keeps its bytes while reads use current events.

        The previous version stored the Webhook with the then-current event
        names.  Its exact ID, document and digest stay intact, while every
        current read projection presents the same Task lifecycle meaning with
        the current ``task.*`` names.  Only a changed definition has to adopt
        the current names on write.
        """

        with tempfile.TemporaryDirectory() as directory:
            harness = WebhookManagementHarness(directory)
            try:
                accepted, active, stored_events = _accept_historical_webhook(harness)
                self.assertEqual(active.revision_id, accepted.revision_id)
                self.assertEqual(active.digest, accepted.digest)
                original_document = json.loads(json.dumps(active.document))
                canonical_events = ["task.completed", "task.failed", "schedule.emitted"]

                status, detail = request(
                    harness.api,
                    f"/api/configuration/revisions/{active.revision_id}/objects",
                )
                self.assertEqual(status, 200, detail)
                projected = detail["objects"]["webhooks"][0]
                self.assertTrue(projected["structuralValid"])
                self.assertEqual(projected["events"], canonical_events)
                self.assertEqual(projected["secretReadiness"][0]["env"], "MEDIAFLOW_WEBHOOK_SECRET")

                status, page = request(
                    harness.api,
                    "/api/operations/notifications/webhooks",
                )
                self.assertEqual(status, 200, page)
                self.assertEqual([item["id"] for item in page["items"]], ["operations-webhook"])
                self.assertEqual(page["items"][0]["events"], canonical_events)
                self.assertEqual(page["activeConfiguration"]["revisionId"], active.revision_id)

                status, operator_detail = request(
                    harness.api,
                    "/api/operations/notifications/webhooks/operations-webhook",
                )
                self.assertEqual(status, 200, operator_detail)
                self.assertEqual(operator_detail["webhook"]["events"], canonical_events)
                self.assertEqual(
                    operator_detail["activeConfiguration"]["revisionId"],
                    active.revision_id,
                )

                # Direct publication leaves no recoverable Draft to read.
                self.assertFalse(
                    any(
                        revision.status.value in {"draft", "validated"}
                        and revision.revision_id != harness.draft.revision_id
                        for revision in harness.config_repository.list_revisions()
                    )
                )
                # The read projection never rewrites the accepted Active bytes.
                reread = harness.configuration.require(active.revision_id)
                self.assertEqual(reread.digest, accepted.digest)
                self.assertEqual(reread.document, original_document)
                self.assertEqual(
                    reread.document["notifications"]["webhooks"][0]["events"],
                    stored_events,
                )
                current = harness.configuration.active()
                self.assertIsNotNone(current)
                self.assertEqual(current.revision_id, active.revision_id)
                self.assertEqual(current.digest, active.digest)
            finally:
                harness.close()

    def test_accepted_historical_webhook_copy_and_enable_write_current_events(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = WebhookManagementHarness(directory)
            try:
                _accepted, active, _stored = _accept_historical_webhook(harness)
                detail_revision_id = active.revision_id
                status, detail = request(
                    harness.api,
                    "/api/operations/notifications/webhooks/operations-webhook",
                )
                self.assertEqual(status, 200, detail)
                self.assertEqual(
                    detail["webhook"]["events"],
                    ["task.completed", "task.failed", "schedule.emitted"],
                )
                status, copied = request(
                    harness.api,
                    f"/api/configuration/revisions/{detail_revision_id}"
                    "/objects/webhooks/operations-webhook/copy",
                    method="POST",
                    body=json.dumps({"expectedVersion": active.version}).encode(),
                )
                self.assertEqual(status, 200, copied)
                self.assertFalse(copied["object"]["enabled"])
                status, enabled = request(
                    harness.api,
                    f"/api/configuration/revisions/{copied['revisionId']}"
                    f"/objects/webhooks/{copied['object']['id']}/enable",
                    method="POST",
                    body=json.dumps({"expectedVersion": copied["version"]}).encode(),
                )
                self.assertEqual(status, 200, enabled)
                self.assertTrue(enabled["object"]["enabled"])
                current = harness.configuration.active()
                self.assertFalse(
                    any(
                        revision.status.value in {"draft", "validated"}
                        and revision.revision_id != harness.draft.revision_id
                        for revision in harness.config_repository.list_revisions()
                    )
                )
                section = current.document.get("webhooks")
                if not isinstance(section, list):
                    section = current.document["notifications"]["webhooks"]
                self.assertEqual(
                    section[0]["events"],
                    ["job.completed", "job.failed", "schedule.emitted"],
                )
            finally:
                harness.close()

    def test_typed_lifecycle_create_edit_copy_enable_disable_delete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = WebhookManagementHarness(directory)
            try:
                active = _activate(harness)
                revision_id = active.revision_id
                version = active.version
                status, created = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks",
                    method="POST",
                    body=json.dumps(
                        {"object": webhook_document(), "expectedVersion": version}
                    ).encode(),
                )
                self.assertEqual(status, 200, created)
                revision_id, version = created["revisionId"], created["version"]
                status, updated = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks/ops-webhook",
                    method="PUT",
                    body=json.dumps(
                        {
                            "object": webhook_document(
                                events=["task.completed", "task.failed", "task.cancelled"],
                                maxRetrySeconds=30,
                            ),
                            "expectedVersion": version,
                        }
                    ).encode(),
                )
                self.assertEqual(status, 200, updated)
                revision_id, version = updated["revisionId"], updated["version"]
                status, copied = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks/ops-webhook/copy",
                    method="POST",
                    body=json.dumps({"expectedVersion": version}).encode(),
                )
                self.assertEqual(status, 200, copied)
                copied_id = copied["object"]["id"]
                self.assertFalse(copied["object"]["enabled"])
                revision_id, version = copied["revisionId"], copied["version"]
                status, enabled = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks/{copied_id}/enable",
                    method="POST",
                    body=json.dumps({"expectedVersion": version}).encode(),
                )
                self.assertEqual(status, 200, enabled)
                revision_id, version = enabled["revisionId"], enabled["version"]
                status, disabled = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks/ops-webhook/disable",
                    method="POST",
                    body=json.dumps({"expectedVersion": version}).encode(),
                )
                self.assertEqual(status, 200, disabled)
                revision_id, version = disabled["revisionId"], disabled["version"]
                status, deleted = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks/{copied_id}",
                    method="DELETE",
                    body=json.dumps({"expectedVersion": version}).encode(),
                )
                self.assertEqual(status, 200, deleted)
                current = harness.configuration.active()
                ids = [item["id"] for item in current.document["webhooks"]]
                self.assertIn("ops-webhook", ids)
                self.assertNotIn(copied_id, ids)
                self.assertFalse(
                    any(
                        revision.status.value in {"draft", "validated"}
                        for revision in harness.config_repository.list_revisions()
                    )
                )
            finally:
                harness.close()

    def test_revision_authority_stale_writes_and_direct_active_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = WebhookManagementHarness(directory)
            try:
                active = _activate(harness)
                revision_id = active.revision_id
                status, created = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks",
                    method="POST",
                    body=json.dumps(
                        {"object": webhook_document(), "expectedVersion": active.version}
                    ).encode(),
                )
                self.assertEqual(status, 200, created)
                revision_id = created["revisionId"]
                # Stale write with an old version fails closed.
                status, stale = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks/ops-webhook",
                    method="PUT",
                    body=json.dumps(
                        {"object": webhook_document(), "expectedVersion": active.version}
                    ).encode(),
                )
                self.assertEqual(status, 409)
                self.assertEqual(stale["error"]["details"]["durableState"], "active_preserved")
                # The current Active accepts a fresh explicit edit and publishes
                # a new immutable snapshot.
                status, updated = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks",
                    method="POST",
                    body=json.dumps(
                        {
                            "object": webhook_document(id="second"),
                            "expectedVersion": created["version"],
                        }
                    ).encode(),
                )
                self.assertEqual(status, 200, updated)
                self.assertNotEqual(harness.configuration.active().revision_id, revision_id)
                self.assertFalse(
                    any(
                        revision.status.value in {"draft", "validated"}
                        for revision in harness.config_repository.list_revisions()
                    )
                )
            finally:
                harness.close()

    def test_validation_fails_closed_and_responses_are_secret_free(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = WebhookManagementHarness(directory)
            revision_id = harness.draft.revision_id
            try:
                invalid_values = {
                    "http_url": webhook_document(url="http://example.invalid/hook"),
                    "credential_url": webhook_document(
                        url="https://user:pass@example.invalid/hook"
                    ),
                    "fragment_url": webhook_document(url="https://example.invalid/hook#frag"),
                    "bad_env": webhook_document(secretEnv="NOT AN ENV"),
                    "empty_events": webhook_document(events=[]),
                    "duplicate_events": webhook_document(
                        events=["task.completed", "task.completed"]
                    ),
                    "unsupported_event": webhook_document(events=["job.unknown"]),
                    "zero_timeout": webhook_document(timeoutSeconds=0),
                    "oversized_timeout": webhook_document(timeoutSeconds=99999),
                    "zero_attempts": webhook_document(maxAttempts=0),
                    "oversized_attempts": webhook_document(maxAttempts=999),
                    "retry_window": webhook_document(
                        baseRetrySeconds=300,
                        maxRetrySeconds=30,
                    ),
                    "literal_secret": {**webhook_document(), "secret": "super-secret-value"},
                    "literal_token": {**webhook_document(), "token": "super-secret-value"},
                    "arbitrary_field": {**webhook_document(), "execute": "super-secret-value"},
                }
                for label, value in invalid_values.items():
                    with self.subTest(label=label):
                        status, response = request(
                            harness.api,
                            f"/api/configuration/revisions/{revision_id}/objects/webhooks",
                            method="POST",
                            body=json.dumps({"object": value, "expectedVersion": 1}).encode(),
                        )
                        self.assertEqual(status, 400, response)
                        encoded = json.dumps(response)
                        self.assertNotIn("super-secret-value", encoded)

                # Readiness reflects deployment-owned env presence only.
                with patch.dict(os.environ, {"MEDIAFLOW_WEBHOOK_SECRET": "real-secret-value"}):
                    status, created = request(
                        harness.api,
                        f"/api/configuration/revisions/{revision_id}/objects/webhooks",
                        method="POST",
                        body=json.dumps(
                            {"object": webhook_document(), "expectedVersion": 1}
                        ).encode(),
                    )
                    self.assertEqual(status, 200)
                    status, detail = request(
                        harness.api,
                        f"/api/configuration/revisions/{revision_id}/objects",
                    )
                    self.assertEqual(status, 200)
                    webhook = next(
                        item
                        for item in detail["objects"]["webhooks"]
                        if item["id"] == "ops-webhook"
                    )
                    self.assertEqual(webhook["secretReadiness"][0]["state"], "SET")
                    self.assertNotIn("real-secret-value", json.dumps(detail))
            finally:
                harness.close()

    def test_explicit_test_success_sends_one_signed_request_without_side_effects(self) -> None:
        transport = FakeTransport(204)
        with tempfile.TemporaryDirectory() as directory:
            harness = WebhookManagementHarness(directory, transport=transport)
            revision_id = harness.draft.revision_id
            try:
                status, created = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks",
                    method="POST",
                    body=json.dumps({"object": webhook_document(), "expectedVersion": 1}).encode(),
                )
                self.assertEqual(status, 200)
                revision = harness.configuration.require(revision_id)
                jobs_before = ()
                tasks_before = harness.repository.list_tasks()
                deliveries_before = harness.repository.list_deliveries()

                with patch.dict(os.environ, {"MEDIAFLOW_WEBHOOK_SECRET": "top-secret-value"}):
                    status, result = request(
                        harness.api,
                        f"/api/configuration/revisions/{revision_id}/objects/webhooks/ops-webhook/test",
                        method="POST",
                        body=json.dumps(
                            {
                                "expectedVersion": revision.version,
                                "expectedDigest": revision.digest,
                            }
                        ).encode(),
                    )
                self.assertEqual(status, 200)
                self.assertEqual(result["outcome"], "success")
                self.assertEqual(result["category"], "http_204")
                self.assertEqual(result["responseStatus"], 204)
                self.assertEqual(result["sideEffects"], "none")
                self.assertTrue(result["retrySafe"])
                self.assertNotIn("top-secret-value", json.dumps(result))
                self.assertEqual(len(transport.requests), 1)
                sent = transport.requests[0]
                self.assertTrue(sent.headers["X-MediaFlow-Signature"].startswith("sha256="))
                self.assertIn("X-MediaFlow-Test", sent.headers)
                self.assertNotIn("top-secret-value", json.dumps(sent.headers))
                audits = harness.repository.list_security_audit(limit=50)
                self.assertTrue(
                    any(
                        item.action == "webhook-test"
                        and item.outcome in {"allowed", "success"}
                        and "category=http_204" in item.route
                        for item in audits
                    )
                )

                # Exactly one request per explicit action: no automatic retry.
                with patch.dict(os.environ, {"MEDIAFLOW_WEBHOOK_SECRET": "top-secret-value"}):
                    request(
                        harness.api,
                        f"/api/configuration/revisions/{revision_id}/objects/webhooks/ops-webhook/test",
                        method="POST",
                        body=json.dumps(
                            {
                                "expectedVersion": revision.version,
                                "expectedDigest": revision.digest,
                            }
                        ).encode(),
                    )
                self.assertEqual(len(transport.requests), 2)

                self.assertEqual(harness.repository.list_deliveries(), deliveries_before)
                self.assertEqual((), jobs_before)
                self.assertEqual(harness.repository.list_tasks(), tasks_before)
                self.assertEqual(harness.repository.list_automation_definition_due_states(), ())
            finally:
                harness.close()

    def test_explicit_test_failure_categories_and_stale_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = WebhookManagementHarness(
                directory,
                transport=FakeTransport(RuntimeError("transport token=leaked-secret")),
            )
            revision_id = harness.draft.revision_id
            try:
                status, created = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks",
                    method="POST",
                    body=json.dumps({"object": webhook_document(), "expectedVersion": 1}).encode(),
                )
                self.assertEqual(status, 200)
                revision = harness.configuration.require(revision_id)

                # Missing secret reference is deterministic and never sends.
                with patch.dict(os.environ, {}, clear=True):
                    status, missing = request(
                        harness.api,
                        f"/api/configuration/revisions/{revision_id}/objects/webhooks/ops-webhook/test",
                        method="POST",
                        body=json.dumps(
                            {
                                "expectedVersion": revision.version,
                                "expectedDigest": revision.digest,
                            }
                        ).encode(),
                    )
                self.assertEqual(status, 200)
                self.assertEqual(missing["outcome"], "failure")
                self.assertEqual(missing["category"], "missing_secret")
                self.assertTrue(missing["retrySafe"])
                self.assertIn("set the referenced", missing["nextAction"])

                # Stale exact-revision identity fails closed with durable evidence.
                status, stale = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks/ops-webhook/test",
                    method="POST",
                    body=json.dumps(
                        {
                            "expectedVersion": revision.version,
                            "expectedDigest": "stale-digest",
                        }
                    ).encode(),
                )
                self.assertEqual(status, 409)
                self.assertEqual(
                    stale["error"]["details"]["durableState"],
                    "configuration_preserved",
                )

                # Transport failure is reduced to a safe category.
                with patch.dict(os.environ, {"MEDIAFLOW_WEBHOOK_SECRET": "top-secret-value"}):
                    status, transport = request(
                        harness.api,
                        f"/api/configuration/revisions/{revision_id}/objects/webhooks/ops-webhook/test",
                        method="POST",
                        body=json.dumps(
                            {
                                "expectedVersion": revision.version,
                                "expectedDigest": revision.digest,
                            }
                        ).encode(),
                    )
                self.assertEqual(status, 200)
                self.assertEqual(transport["category"], "transport")
                self.assertEqual(transport["outcome"], "failure")
                self.assertNotIn("leaked-secret", json.dumps(transport))
            finally:
                harness.close()

    def test_timeout_and_non_2xx_have_deterministic_failure_semantics(self) -> None:
        cases = (
            (TimeoutError("timeout"), "timeout"),
            (500, "http_500"),
            (429, "http_429"),
            (404, "http_404"),
        )
        for index, (result, category) in enumerate(cases):
            with self.subTest(category=category):
                with tempfile.TemporaryDirectory() as directory:
                    harness = WebhookManagementHarness(directory, transport=FakeTransport(result))
                    revision_id = harness.draft.revision_id
                    try:
                        status, created = request(
                            harness.api,
                            f"/api/configuration/revisions/{revision_id}/objects/webhooks",
                            method="POST",
                            body=json.dumps(
                                {"object": webhook_document(), "expectedVersion": 1}
                            ).encode(),
                        )
                        self.assertEqual(status, 200)
                        revision = harness.configuration.require(revision_id)
                        with patch.dict(
                            os.environ, {"MEDIAFLOW_WEBHOOK_SECRET": "top-secret-value"}
                        ):
                            status, outcome = request(
                                harness.api,
                                f"/api/configuration/revisions/{revision_id}/objects/webhooks/ops-webhook/test",
                                method="POST",
                                body=json.dumps(
                                    {
                                        "expectedVersion": revision.version,
                                        "expectedDigest": revision.digest,
                                    }
                                ).encode(),
                            )
                        self.assertEqual(status, 200)
                        self.assertEqual(outcome["category"], category)
                        if result == 204:
                            self.assertEqual(outcome["outcome"], "success")
                        else:
                            self.assertEqual(outcome["outcome"], "failure")
                        self.assertEqual(outcome["sideEffects"], "none")
                        self.assertIn("nextAction", outcome)
                        self.assertNotIn("top-secret-value", json.dumps(outcome))
                    finally:
                        harness.close()


if __name__ == "__main__":
    unittest.main()
