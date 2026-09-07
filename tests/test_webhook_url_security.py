from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import (
    MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION,
    ManagedConfigurationService,
)
from mediaflow.application.notification import NotificationPublisher, NotificationWorker
from mediaflow.domain.configuration_management import (
    ConfigurationObjectKind,
    ManagedConfigurationRevision,
    ManagedConfigurationStatus,
)
from mediaflow.domain.notification import (
    NotificationEvent,
    NotificationEventType,
    WebhookDefinition,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import APP_JS
from mediaflow.interfaces.service_api import MediaFlowApi

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
SENTINEL = "TOP_SECRET_VALUE_92817"
REDACTED = "***REDACTED***"


class FakeTransport:
    def __init__(self, *results) -> None:
        self.results = list(results or (204,))
        self.requests = []

    def send(self, request) -> int:
        self.requests.append(request)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def example_document() -> dict:
    return json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))


def webhook_document(**changes):
    value = {
        "id": "ops-webhook",
        "url": "https://example.invalid/hooks/mediaflow",
        "secretEnv": "MEDIAFLOW_WEBHOOK_SECRET",
        "events": ["job.completed", "job.failed"],
        "enabled": True,
        "timeoutSeconds": 10,
        "maxAttempts": 5,
        "baseRetrySeconds": 5,
        "maxRetrySeconds": 300,
    }
    value.update(changes)
    return value


def request(
    api,
    path,
    *,
    method="GET",
    body=b"",
    token="admin-token",
    query="",
):
    statuses = []
    environment = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(body)),
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(body),
        "HTTP_AUTHORIZATION": f"Bearer {token}" if token else "",
    }
    payload = b"".join(api(environment, lambda status, headers: statuses.append(status)))
    parsed = json.loads(payload) if payload else {}
    return int(statuses[0].split()[0]), parsed


def canonical_digest(document: dict) -> str:
    encoded = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class WebhookSecurityHarness:
    def __init__(self, directory: str, transport=None):
        self.directory = Path(directory)
        document = example_document()
        runtime_database = str(self.directory / "runtime.sqlite3")
        document["persistence"]["databasePath"] = runtime_database
        self.runtime_database = runtime_database
        self.config_repository = SQLiteConfigurationRepository(
            self.directory / "configuration.sqlite3"
        )
        self.configuration = ManagedConfigurationService(
            self.config_repository,
            bootstrap_database_path=runtime_database,
        )
        self.draft = self.configuration.import_draft(document, actor="bootstrap")
        self.repository = SQLiteTaskRepository(self.directory / "runtime.sqlite3")
        admin = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
        viewer = ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
        self.api = MediaFlowApi(
            self.repository,
            None,
            principals=(admin, viewer),
            configuration_service=self.configuration,
            bootstrap_document=document,
            webhook_transport=transport or FakeTransport(204),
        )

    def seed_revision(
        self,
        *,
        webhook_urls=(),
        status=ManagedConfigurationStatus.DRAFT,
        activated_at: datetime | None = None,
    ) -> ManagedConfigurationRevision:
        """Persist one legacy revision directly, bypassing import validation."""

        document = example_document()
        document["persistence"]["databasePath"] = self.runtime_database
        notifications = document.setdefault("notifications", {})
        webhooks = []
        for index, url in enumerate(webhook_urls):
            webhooks.append(
                webhook_document(
                    id=f"legacy-webhook-{index + 1}",
                    url=url,
                    events=["job.completed"],
                )
            )
        if webhooks:
            notifications["webhooks"] = webhooks
        revision = ManagedConfigurationRevision(
            str(uuid4()),
            1,
            status,
            MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION,
            canonical_digest(document),
            document,
            NOW,
            NOW,
            activated_at=activated_at,
        )
        return self.config_repository.create_revision(revision)

    def close(self):
        self.repository.close()
        self.config_repository.close()


class WebhookUrlCanonicalRuleTests(unittest.TestCase):
    def test_domain_validator_rejects_every_credential_query_spelling(self) -> None:
        unsafe_queries = (
            "token",
            "api_key",
            "apikey",
            "API_KEY",
            "api-key",
            "apiKey",
            "access_token",
            "client_secret",
            "secret",
            "password",
            "authorization",
            "credential",
            "signature",
            "sig",
            "access_key",
            "secret_key",
        )
        for name in unsafe_queries:
            with self.subTest(name=name):
                url = f"https://example.invalid/hooks?{name}={SENTINEL}"
                with self.assertRaises(ValueError) as raised:
                    WebhookDefinition(
                        webhook_id="ops",
                        url=url,
                        secret_env="MEDIAFLOW_WEBHOOK_SECRET",
                        events=(NotificationEventType.JOB_COMPLETED,),
                    )
                message = str(raised.exception)
                self.assertIn("query", message)
                self.assertNotIn(SENTINEL, message)
                self.assertNotIn(url, message)
        # Unrestricted/unknown query parameters also fail closed: they cannot be
        # proven secret-free, so the query component is rejected entirely.
        for url in (
            "https://example.invalid/hooks?format=json",
            "https://example.invalid/hooks?x=1&y=2",
            "https://example.invalid/hooks?token=",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    WebhookDefinition(
                        webhook_id="ops",
                        url=url,
                        secret_env="MEDIAFLOW_WEBHOOK_SECRET",
                        events=(NotificationEventType.JOB_COMPLETED,),
                    )

    def test_domain_validator_still_rejects_userinfo_and_fragment(self) -> None:
        for url in (
            "https://user:pass@example.invalid/hooks",
            "https://example.invalid/hooks#fragment",
            "http://example.invalid/hooks",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError) as raised:
                    WebhookDefinition(
                        webhook_id="ops",
                        url=url,
                        secret_env="MEDIAFLOW_WEBHOOK_SECRET",
                        events=(NotificationEventType.JOB_COMPLETED,),
                    )
                self.assertNotIn(SENTINEL, str(raised.exception))
                self.assertNotIn(url, str(raised.exception))

    def test_runtime_loader_fails_closed_without_echoing_the_url(self) -> None:
        document = example_document()
        url = f"https://example.invalid/hooks?api_key={SENTINEL}"
        document["notifications"]["webhooks"][0]["url"] = url
        with self.assertRaises(ValueError) as raised:
            load_runtime_configuration(copy.deepcopy(document))
        self.assertNotIn(SENTINEL, str(raised.exception))
        self.assertNotIn(url, str(raised.exception))

    def test_safe_endpoints_still_construct_and_round_trip(self) -> None:
        definition = WebhookDefinition(
            webhook_id="ops",
            url="https://example.invalid/hooks/mediaflow",
            secret_env="MEDIAFLOW_WEBHOOK_SECRET",
            events=(NotificationEventType.JOB_COMPLETED,),
        )
        self.assertEqual(definition.document()["url"], "https://example.invalid/hooks/mediaflow")
        loaded = load_runtime_configuration(example_document())
        self.assertEqual(loaded.webhooks[0].url, "https://example.invalid/mediaflow/events")


class WebhookUrlManagedApiTests(unittest.TestCase):
    def test_typed_create_rejects_unsafe_url_before_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = WebhookSecurityHarness(directory)
            revision_id = harness.draft.revision_id
            try:
                unsafe = f"https://example.invalid/hooks?token={SENTINEL}"
                status, response = request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/webhooks",
                    method="POST",
                    body=json.dumps(
                        {"object": webhook_document(url=unsafe), "expectedVersion": 1}
                    ).encode(),
                )
                self.assertEqual(status, 400)
                encoded = json.dumps(response)
                self.assertNotIn(SENTINEL, encoded)
                self.assertNotIn(unsafe, encoded)
                revision = harness.configuration.require(revision_id)
                self.assertEqual(revision.version, 1)
                self.assertNotIn("webhooks", revision.document)
                status, detail = request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects",
                )
                self.assertEqual(status, 200)
                self.assertEqual(
                    [item["id"] for item in detail["objects"]["webhooks"]],
                    ["operations-webhook"],
                )
                self.assertNotIn(SENTINEL, json.dumps(detail))
            finally:
                harness.close()

    def test_whole_document_edit_rejects_new_unsafe_url_and_preserves_draft(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = WebhookSecurityHarness(directory)
            revision_id = harness.draft.revision_id
            try:
                document = harness.configuration.require(revision_id).document
                incoming = copy.deepcopy(document)
                incoming["notifications"]["webhooks"][0]["url"] = (
                    f"https://example.invalid/hooks?secret_key={SENTINEL}"
                )
                status, response = request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{revision_id}",
                    method="PUT",
                    body=json.dumps({"document": incoming, "expectedVersion": 1}).encode(),
                )
                self.assertEqual(status, 400)
                encoded = json.dumps(response)
                self.assertNotIn(SENTINEL, encoded)
                revision = harness.configuration.require(revision_id)
                self.assertEqual(revision.version, 1)
                self.assertEqual(
                    revision.document["notifications"]["webhooks"][0]["url"],
                    "https://example.invalid/mediaflow/events",
                )
            finally:
                harness.close()

    def test_copy_and_enable_of_legacy_unsafe_webhook_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = WebhookSecurityHarness(directory)
            try:
                legacy = harness.seed_revision(
                    webhook_urls=(f"https://example.invalid/hooks?token={SENTINEL}",)
                )
                status, copy_result = request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{legacy.revision_id}"
                    "/objects/webhooks/legacy-webhook-1/copy",
                    method="POST",
                    body=json.dumps({"expectedVersion": legacy.version}).encode(),
                )
                self.assertEqual(status, 400)
                self.assertNotIn(SENTINEL, json.dumps(copy_result))
                status, enable_result = request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{legacy.revision_id}"
                    "/objects/webhooks/legacy-webhook-1/enable",
                    method="POST",
                    body=json.dumps({"expectedVersion": legacy.version}).encode(),
                )
                self.assertEqual(status, 400)
                self.assertNotIn(SENTINEL, json.dumps(enable_result))
            finally:
                harness.close()


class WebhookUrlLegacyProjectionTests(unittest.TestCase):
    def test_legacy_unsafe_revision_projections_and_export_are_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = WebhookSecurityHarness(directory)
            unsafe = f"https://example.invalid/hooks?access_token={SENTINEL}"
            try:
                legacy = harness.seed_revision(webhook_urls=(unsafe,))
                revision_id = legacy.revision_id
                status, detail = request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{revision_id}",
                )
                self.assertEqual(status, 200)
                encoded = json.dumps(detail)
                self.assertNotIn(SENTINEL, encoded)
                self.assertNotIn(unsafe, encoded)
                document = detail["document"]
                stored_url = document["notifications"]["webhooks"][0]["url"]
                self.assertEqual(stored_url, REDACTED)

                status, objects = request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects",
                )
                self.assertEqual(status, 200)
                self.assertNotIn(SENTINEL, json.dumps(objects))
                webhook = next(
                    item
                    for item in objects["objects"]["webhooks"]
                    if item["id"] == "legacy-webhook-1"
                )
                self.assertEqual(webhook["url"], REDACTED)
                self.assertIs(webhook["structuralValid"], False)
                self.assertIn("query", webhook["validationError"])
                self.assertNotIn("access_token", json.dumps(webhook["validationError"]))

                status, package = request(
                    harness.api,
                    "/api/v1/configuration/packages/export/configuration",
                    query=f"revisionId={revision_id}",
                )
                self.assertEqual(status, 200)
                package_encoded = json.dumps(package)
                self.assertNotIn(SENTINEL, package_encoded)
                payload_document = package["payload"]["document"]
                self.assertEqual(payload_document["notifications"]["webhooks"][0]["url"], REDACTED)
                self.assertTrue(
                    any(
                        entry.get("kind") == "redacted_webhook_url"
                        for entry in package["redaction"]["entries"]
                    )
                )

                # The persisted legacy revision is not silently rewritten: only
                # projections/export suppress the credential-bearing URL.
                raw = harness.configuration.require(revision_id).document
                self.assertEqual(raw["notifications"]["webhooks"][0]["url"], unsafe)
            finally:
                harness.close()

    def test_legacy_unsafe_revision_is_correctable_without_deadlock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = WebhookSecurityHarness(directory)
            unsafe_a = f"https://example.invalid/hooks?token={SENTINEL}A"
            unsafe_b = f"https://example.invalid/hooks?password={SENTINEL}B"
            try:
                legacy = harness.seed_revision(webhook_urls=(unsafe_a, unsafe_b))
                revision_id = legacy.revision_id

                # Correct only webhook A; the unchanged legacy unsafe webhook B
                # stays untouched (projection redacted) so no deadlock occurs.
                safe_a = webhook_document(
                    id="legacy-webhook-1",
                    url="https://example.invalid/hooks/legacy-a",
                    events=["job.completed"],
                )
                status, corrected = request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/webhooks/"
                    "legacy-webhook-1",
                    method="PUT",
                    body=json.dumps({"object": safe_a, "expectedVersion": legacy.version}).encode(),
                )
                self.assertEqual(status, 200)
                self.assertNotIn(SENTINEL, json.dumps(corrected))
                updated = harness.configuration.require(revision_id)
                self.assertEqual(updated.version, 2)
                root_hooks = updated.document["webhooks"]
                self.assertEqual(root_hooks[0]["url"], "https://example.invalid/hooks/legacy-a")
                # B moved to the canonical root spelling and remains unsafe but
                # unchanged; its URL is never exposed by projections.
                status, objects = request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects",
                )
                self.assertNotIn(SENTINEL, json.dumps(objects))
                projected_b = next(
                    item
                    for item in objects["objects"]["webhooks"]
                    if item["id"] == "legacy-webhook-2"
                )
                self.assertEqual(projected_b["url"], REDACTED)
                projected_a = next(
                    item
                    for item in objects["objects"]["webhooks"]
                    if item["id"] == "legacy-webhook-1"
                )
                self.assertEqual(projected_a["url"], "https://example.invalid/hooks/legacy-a")

                # Audit records for the correction never contain the legacy URL.
                status, detail = request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{revision_id}",
                )
                self.assertNotIn(SENTINEL, json.dumps(detail))
                self.assertNotIn(unsafe_a, json.dumps(detail))

                # Correct webhook B too; the Draft is now fully safe.
                safe_b = webhook_document(
                    id="legacy-webhook-2",
                    url="https://example.invalid/hooks/legacy-b",
                    events=["job.completed"],
                )
                status, _ = request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/webhooks/"
                    "legacy-webhook-2",
                    method="PUT",
                    body=json.dumps(
                        {"object": safe_b, "expectedVersion": updated.version}
                    ).encode(),
                )
                self.assertEqual(status, 200)
                status, objects = request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects",
                )
                self.assertEqual(status, 200)
                self.assertTrue(
                    all(
                        item["structuralValid"] is True and item["url"] != REDACTED
                        for item in objects["objects"]["webhooks"]
                    )
                )
            finally:
                harness.close()

    def test_validate_and_activation_fail_closed_for_legacy_unsafe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = WebhookSecurityHarness(directory)
            unsafe = f"https://example.invalid/hooks?client_secret={SENTINEL}"
            try:
                legacy = harness.seed_revision(webhook_urls=(unsafe,))
                validated = harness.configuration.validate(legacy.revision_id, actor="bootstrap")
                self.assertEqual(validated.status, ManagedConfigurationStatus.DRAFT)
                self.assertTrue(validated.validation_errors)
                for error in validated.validation_errors:
                    self.assertNotIn(SENTINEL, error)
                    self.assertNotIn(unsafe, error)

                harness.seed_revision(
                    webhook_urls=(unsafe,),
                    status=ManagedConfigurationStatus.ACTIVE,
                    activated_at=NOW,
                )
                status_document = harness.configuration.status_document()
                self.assertEqual(status_document["health"], "UNAVAILABLE")
                self.assertIs(status_document["runtimeConfigured"], False)
                self.assertNotIn(SENTINEL, json.dumps(status_document))

                # The legacy unsafe Active remains correctable through the
                # normal successor-Draft recovery path.
                successor = harness.configuration.create_successor_draft(actor="bootstrap")
                self.assertEqual(successor.status, ManagedConfigurationStatus.DRAFT)
                self.assertNotIn(SENTINEL, json.dumps(successor.summary()))
                safe = webhook_document(
                    id="legacy-webhook-1",
                    url="https://example.invalid/hooks/corrected",
                    events=["job.completed"],
                )
                objects_service = ConfigurationObjectService(harness.configuration)
                updated = objects_service.mutate(
                    successor.revision_id,
                    ConfigurationObjectKind.WEBHOOK_DEFINITION,
                    object_id="legacy-webhook-1",
                    value=safe,
                    expected_version=successor.version,
                    actor="bootstrap",
                )
                self.assertEqual(updated.version, successor.version + 1)
                validated_again = harness.configuration.validate(
                    updated.revision_id, actor="bootstrap"
                )
                self.assertEqual(validated_again.validation_errors, ())
            finally:
                harness.close()


class WebhookUrlCompatibilityTests(unittest.TestCase):
    def test_safe_round_trip_secret_env_and_definition_test(self) -> None:
        transport = FakeTransport(204)
        with tempfile.TemporaryDirectory() as directory:
            harness = WebhookSecurityHarness(directory, transport=transport)
            revision_id = harness.draft.revision_id
            try:
                safe_url = "https://example.invalid/hooks/mediaflow/ops"
                status, created = request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/webhooks",
                    method="POST",
                    body=json.dumps(
                        {
                            "object": webhook_document(
                                id="ops-webhook",
                                url=safe_url,
                                events=["job.completed"],
                            ),
                            "expectedVersion": 1,
                        }
                    ).encode(),
                )
                self.assertEqual(status, 200)
                with patch.dict(os.environ, {"MEDIAFLOW_WEBHOOK_SECRET": "env-secret-992"}):
                    status, detail = request(
                        harness.api,
                        f"/api/v1/configuration/revisions/{revision_id}/objects",
                    )
                    self.assertEqual(status, 200)
                    webhook = next(
                        item
                        for item in detail["objects"]["webhooks"]
                        if item["id"] == "ops-webhook"
                    )
                    self.assertEqual(webhook["url"], safe_url)
                    self.assertIs(webhook["structuralValid"], True)
                    self.assertEqual(webhook["secretReadiness"][0]["state"], "SET")
                    self.assertNotIn("env-secret-992", json.dumps(detail))

                    # Export keeps the safe URL but never the environment value.
                    status, package = request(
                        harness.api,
                        "/api/v1/configuration/packages/export/configuration",
                        query=f"revisionId={revision_id}",
                    )
                    self.assertEqual(status, 200)
                    self.assertNotIn("env-secret-992", json.dumps(package))
                    exported = next(
                        item
                        for item in package["payload"]["document"]["webhooks"]
                        if item["id"] == "ops-webhook"
                    )
                    self.assertEqual(exported["url"], safe_url)
                    self.assertEqual(exported["secretEnv"], "MEDIAFLOW_WEBHOOK_SECRET")

                    # Activate the safe Draft and run the explicit definition test.
                    validated = harness.configuration.validate(revision_id, actor="bootstrap")
                    active = harness.configuration.activate(
                        validated.revision_id,
                        expected_version=validated.version,
                        actor="bootstrap",
                    )
                    deliveries_before = harness.repository.list_deliveries()
                    jobs_before = harness.repository.list_jobs()
                    status, test_result = request(
                        harness.api,
                        f"/api/v1/configuration/revisions/{active.revision_id}/objects/"
                        "webhooks/ops-webhook/test",
                        method="POST",
                        body=json.dumps(
                            {
                                "expectedVersion": active.version,
                                "expectedDigest": active.digest,
                            }
                        ).encode(),
                    )
                    self.assertEqual(status, 200)
                    self.assertEqual(test_result["outcome"], "success")
                    self.assertEqual(harness.repository.list_deliveries(), deliveries_before)
                    self.assertEqual(harness.repository.list_jobs(), jobs_before)

                    # Signed delivery through the Worker still works and creates
                    # exactly one durable delivery for a published event.
                    runtime = load_runtime_configuration(active.document)
                    definition = next(
                        item for item in runtime.webhooks if item.webhook_id == "ops-webhook"
                    )
                    event = NotificationEvent(
                        "event-delivery-1",
                        NotificationEventType.JOB_COMPLETED,
                        NOW,
                        {"jobId": "job-1"},
                    )
                    created_deliveries = NotificationPublisher(
                        harness.repository, (definition,)
                    ).publish(event)
                    self.assertEqual(len(created_deliveries), 1)
                    worker = NotificationWorker(
                        harness.repository,
                        runtime.resolve_webhook_targets(),
                        FakeTransport(204),
                        clock=lambda: NOW + timedelta(days=1),
                    )
                    delivered = worker.run_next()
                    self.assertEqual(delivered.status.value, "delivered")
                    self.assertNotIn("env-secret-992", repr(delivered))
            finally:
                harness.close()

    def test_package_import_rejects_unsafe_webhook_url_and_preserves_draft(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = WebhookSecurityHarness(directory)
            revision_id = harness.draft.revision_id
            try:
                document = harness.configuration.require(revision_id).document
                incoming = copy.deepcopy(document)
                incoming["notifications"]["webhooks"][0]["url"] = (
                    f"https://example.invalid/hooks?authorization={SENTINEL}"
                )
                package = {
                    "packageKind": "mediaflow.configuration.v1",
                    "packageSchemaVersion": 1,
                    "packageVersion": 1,
                    "generatedAt": NOW.isoformat(),
                    "producer": {"id": "test", "version": "0"},
                    "source": {
                        "revisionId": revision_id,
                        "revisionSequence": 1,
                        "version": 1,
                        "status": "draft",
                        "digest": canonical_digest(incoming),
                        "baseActiveRevisionId": None,
                        "createdAt": NOW.isoformat(),
                        "updatedAt": NOW.isoformat(),
                    },
                    "currentness": {
                        "currentActiveRevisionId": None,
                        "currentActiveVersion": None,
                        "currentActiveDigest": None,
                        "sourceIsCurrent": False,
                        "authority": "NONE",
                    },
                    "validation": {
                        "status": "draft",
                        "validationErrors": [],
                        "validatedAt": None,
                        "managedDocumentSchemaVersion": 1,
                        "packageSchemaVersion": 1,
                    },
                    "redaction": {"scope": "test", "entries": [], "entryCount": 0},
                    "payload": {
                        "schemaVersion": 1,
                        "revisionDigest": canonical_digest(incoming),
                        "documentDigest": canonical_digest(incoming),
                        "document": incoming,
                    },
                }
                package["packageDigest"] = canonical_digest(package["payload"])
                status, response = request(
                    harness.api,
                    "/api/v1/configuration/packages",
                    method="POST",
                    body=json.dumps({"package": package}).encode(),
                )
                self.assertEqual(status, 422)
                self.assertNotIn(SENTINEL, json.dumps(response))
                revision = harness.configuration.require(revision_id)
                self.assertEqual(revision.version, 1)
                self.assertEqual(
                    revision.document["notifications"]["webhooks"][0]["url"],
                    "https://example.invalid/mediaflow/events",
                )
            finally:
                harness.close()

    def test_web_and_api_share_the_redacted_endpoint_surface(self) -> None:
        script = APP_JS.decode("utf-8")
        # The guided Web/API journey and the Notifications surface both explain
        # that a hidden endpoint URL must be corrected, and neither form nor
        # Advanced JSON can echo a submitted credential value.
        self.assertIn("'***REDACTED***'", script)
        self.assertIn("Endpoint URL is hidden because the stored URL carries credentials", script)
        self.assertIn("enter a clean HTTPS endpoint URL to correct it", script)
        self.assertIn("stored endpoint URL is hidden because it carries credentials", script)
        self.assertIn("Save Webhook Definition", script)
        self.assertNotIn(SENTINEL, script)


if __name__ == "__main__":
    unittest.main()
