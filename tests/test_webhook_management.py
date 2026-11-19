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
from mediaflow.application.notification import NotificationPublisher
from mediaflow.domain.configuration_integrity import (
    MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION,
    canonical_document_digest,
)
from mediaflow.domain.configuration_management import (
    ConfigurationObjectKind,
    ManagedConfigurationRevision,
    ManagedConfigurationStatus,
)
from mediaflow.domain.notification import (
    NotificationEvent,
    NotificationEventType,
    accepted_webhook_definition,
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

                draft = harness.configuration.create_successor_draft(
                    actor="bootstrap",
                    expected_active_revision_id=active.revision_id,
                    expected_active_digest=active.digest,
                )
                status, draft_detail = request(
                    harness.api,
                    "/api/operations/notifications/webhooks/operations-webhook/draft",
                )
                self.assertEqual(status, 200, draft_detail)
                self.assertEqual(draft_detail["webhook"]["events"], canonical_events)
                self.assertEqual(draft_detail["draft"]["webhook"]["events"], canonical_events)

                # The read projection never rewrites the accepted Active bytes.
                reread = harness.configuration.require(active.revision_id)
                self.assertEqual(reread.digest, accepted.digest)
                self.assertEqual(reread.document, original_document)
                self.assertEqual(
                    reread.document["notifications"]["webhooks"][0]["events"],
                    stored_events,
                )
                self.assertEqual(
                    draft.document["notifications"]["webhooks"][0]["events"], stored_events
                )
                current = harness.configuration.active()
                self.assertIsNotNone(current)
                self.assertEqual(current.revision_id, active.revision_id)
                self.assertEqual(current.digest, active.digest)
            finally:
                harness.close()

    def test_accepted_historical_webhook_copy_and_enable_write_current_events(self) -> None:
        """Server-assembled Draft writes use the current event names.

        Copy and enable/disable read the exact stored definition and assemble
        the write themselves, so an accepted definition must stay actionable
        after the browser is shown the canonical spelling.  Only the selected
        Draft object changes, the accepted bytes and Active identity survive
        until explicit activation, and the current delivery/event reads keep
        working from the same persisted definition.
        """

        with tempfile.TemporaryDirectory() as directory:
            harness = WebhookManagementHarness(directory)
            try:
                accepted, active, stored_events = _accept_historical_webhook(harness)
                canonical_events = ["task.completed", "task.failed", "schedule.emitted"]
                accepted_document = json.loads(json.dumps(accepted.document))
                accepted_webhook = accepted_document["notifications"]["webhooks"][0]

                # One delivery is already recorded under the accepted
                # definition; its event identity uses the Task lifecycle meaning.
                historical_definition = accepted_webhook_definition(accepted_webhook)
                created = NotificationPublisher(
                    harness.repository, (historical_definition,)
                ).publish(
                    NotificationEvent(
                        "event-before-successor",
                        NotificationEventType.TASK_COMPLETED,
                        datetime.now(UTC),
                        {"taskId": "task-before-successor"},
                    )
                )
                self.assertEqual(len(created), 1)

                # The operator opens the exact Active definition and follows
                # the action the detail page offers to open a successor Draft.
                status, detail = request(
                    harness.api,
                    "/api/operations/notifications/webhooks/operations-webhook",
                )
                self.assertEqual(status, 200, detail)
                self.assertEqual(detail["webhook"]["events"], canonical_events)
                self.assertEqual(detail["activeConfiguration"]["revisionId"], active.revision_id)
                create_draft = detail["webhook"]["actions"]["draftCreate"]
                self.assertTrue(create_draft["available"])

                status, draft = request(
                    harness.api,
                    create_draft["path"],
                    method="POST",
                    body=b"{}",
                )
                self.assertEqual(status, 201, draft)
                revision_id = draft["revisionId"]
                version = draft["version"]

                # The detail page now offers copy and enable/disable for the
                # open Draft and still presents the current event names.
                status, detail = request(
                    harness.api,
                    "/api/operations/notifications/webhooks/operations-webhook",
                )
                self.assertEqual(status, 200, detail)
                self.assertEqual(detail["webhook"]["events"], canonical_events)
                self.assertEqual(detail["webhook"]["draftState"]["revisionId"], revision_id)
                actions = detail["webhook"]["actions"]
                for action in ("copy", "enable", "disable"):
                    self.assertTrue(actions[action]["available"], action)
                    self.assertIn(
                        f"/api/configuration/revisions/{revision_id}/objects/webhooks/",
                        actions[action]["path"],
                    )

                # Copy is assembled by the server from the stored definition:
                # it succeeds, writes the current event names, produces one
                # disabled definition with a unique id and leaves the source
                # bytes untouched.
                status, copied = request(
                    harness.api,
                    actions["copy"]["path"],
                    method="POST",
                    body=json.dumps({"expectedVersion": version}).encode(),
                )
                self.assertEqual(status, 200, copied)
                self.assertFalse(copied["object"]["enabled"])
                self.assertEqual(copied["object"]["events"], canonical_events)
                copy_id = copied["object"]["id"]
                self.assertNotEqual(copy_id, "operations-webhook")
                version += 1
                revision = harness.configuration.require(revision_id)
                by_id = {item["id"]: item for item in revision.document["webhooks"]}
                self.assertEqual(set(by_id), {"operations-webhook", copy_id})
                self.assertEqual(by_id["operations-webhook"]["events"], stored_events)
                self.assertEqual(by_id[copy_id]["events"], canonical_events)
                copy_before = json.loads(json.dumps(by_id[copy_id]))

                # Enable/disable changes only the selected definition, writes
                # the current event names and answers with them.
                status, enabled = request(
                    harness.api,
                    actions["enable"]["path"],
                    method="POST",
                    body=json.dumps({"expectedVersion": version}).encode(),
                )
                self.assertEqual(status, 200, enabled)
                self.assertTrue(enabled["object"]["enabled"])
                self.assertEqual(enabled["object"]["events"], canonical_events)
                version += 1
                status, disabled = request(
                    harness.api,
                    actions["disable"]["path"],
                    method="POST",
                    body=json.dumps({"expectedVersion": version}).encode(),
                )
                self.assertEqual(status, 200, disabled)
                self.assertFalse(disabled["object"]["enabled"])
                self.assertEqual(disabled["object"]["events"], canonical_events)
                version += 1
                revision = harness.configuration.require(revision_id)
                by_id = {item["id"]: item for item in revision.document["webhooks"]}
                self.assertFalse(by_id["operations-webhook"]["enabled"])
                self.assertEqual(by_id["operations-webhook"]["events"], canonical_events)
                # The unselected sibling stays byte-identical.
                self.assertEqual(by_id[copy_id], copy_before)

                # A stale version fails closed and leaves the Draft untouched.
                status, stale = request(
                    harness.api,
                    actions["copy"]["path"],
                    method="POST",
                    body=json.dumps({"expectedVersion": version - 1}).encode(),
                )
                self.assertEqual(status, 409)
                self.assertEqual(harness.configuration.require(revision_id).version, version)

                # A read-only principal cannot perform the server-assembled write.
                status, denied = request(
                    harness.api,
                    actions["enable"]["path"],
                    method="POST",
                    body=json.dumps({"expectedVersion": version}).encode(),
                    token="viewer-token",
                )
                self.assertEqual(status, 403)

                # A manually submitted definition still has to use the current
                # spelling; only the server-assembled source read maps it.
                status, rejected = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks/{copy_id}",
                    method="PUT",
                    body=json.dumps(
                        {
                            "object": {**by_id[copy_id], "events": ["job.completed"]},
                            "expectedVersion": version,
                        }
                    ).encode(),
                )
                self.assertEqual(status, 400, rejected)
                self.assertEqual(harness.configuration.require(revision_id).version, version)

                # Re-enable the original definition so the published
                # subscription can record a current delivery after activation.
                status, reenabled = request(
                    harness.api,
                    actions["enable"]["path"],
                    method="POST",
                    body=json.dumps({"expectedVersion": version}).encode(),
                )
                self.assertEqual(status, 200, reenabled)
                self.assertTrue(reenabled["object"]["enabled"])
                version += 1

                # The Active pointer and its bytes do not move before the
                # reviewed Draft is validated and explicitly activated.
                current = harness.configuration.active()
                self.assertEqual(current.revision_id, accepted.revision_id)
                self.assertEqual(current.digest, accepted.digest)
                self.assertEqual(
                    harness.configuration.require(accepted.revision_id).document,
                    accepted_document,
                )

                validated = harness.configuration.validate(revision_id, actor="admin")
                self.assertEqual(validated.validation_errors, ())
                published = harness.configuration.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="admin",
                )
                self.assertEqual(published.revision_id, revision_id)
                published_by_id = {item["id"]: item for item in published.document["webhooks"]}
                self.assertEqual(published_by_id["operations-webhook"]["events"], canonical_events)
                self.assertEqual(published_by_id[copy_id]["events"], canonical_events)

                # The superseded revision keeps its accepted bytes and can
                # still be read with the same subscription meaning.
                superseded = harness.configuration.require(accepted.revision_id)
                self.assertEqual(superseded.status, ManagedConfigurationStatus.SUPERSEDED)
                self.assertEqual(superseded.digest, accepted.digest)
                self.assertEqual(superseded.document, accepted_document)
                self.assertEqual(
                    superseded.document["notifications"]["webhooks"][0]["events"],
                    stored_events,
                )
                still_accepted = accepted_webhook_definition(accepted_webhook)
                self.assertEqual(still_accepted.webhook_id, "operations-webhook")
                self.assertEqual([event.value for event in still_accepted.events], canonical_events)

                # Delivery history stays visible; the subscription read from
                # the persisted definition still records the current event type.
                published_definition = accepted_webhook_definition(
                    published_by_id["operations-webhook"]
                )
                self.assertTrue(published_definition.enabled)
                created = NotificationPublisher(
                    harness.repository, (published_definition,)
                ).publish(
                    NotificationEvent(
                        "event-after-successor",
                        NotificationEventType.TASK_COMPLETED,
                        datetime.now(UTC),
                        {"taskId": "task-after-successor"},
                    )
                )
                self.assertEqual(len(created), 1)
                status, deliveries = request(harness.api, "/api/notifications")
                self.assertEqual(status, 200, deliveries)
                self.assertEqual(
                    sorted(
                        (item["webhookId"], item["eventType"], item["status"])
                        for item in deliveries["items"]
                    ),
                    [
                        ("operations-webhook", "task.completed", "pending"),
                        ("operations-webhook", "task.completed", "pending"),
                    ],
                )
                self.assertEqual(
                    {item["eventId"] for item in deliveries["items"]},
                    {"event-before-successor", "event-after-successor"},
                )
            finally:
                harness.close()

    def test_typed_lifecycle_create_edit_copy_enable_disable_delete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = WebhookManagementHarness(directory)
            revision_id = harness.draft.revision_id
            try:
                # The imported example Draft carries the legacy nested Webhook
                # definition, which the managed graph presents for editing.
                status, before = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects",
                )
                self.assertEqual(status, 200)
                self.assertEqual(
                    [item["id"] for item in before["objects"]["webhooks"]],
                    ["operations-webhook"],
                )

                status, created = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks",
                    method="POST",
                    body=json.dumps({"object": webhook_document(), "expectedVersion": 1}).encode(),
                )
                self.assertEqual(status, 200)
                self.assertEqual(created["webhook"]["id"], "ops-webhook")
                self.assertEqual(created["version"], 2)
                revision = harness.configuration.require(revision_id)
                self.assertIn("webhooks", revision.document)
                self.assertNotIn(
                    "webhooks",
                    revision.document.get("notifications", {}),
                )
                self.assertEqual(
                    [item["id"] for item in revision.document["webhooks"]],
                    ["operations-webhook", "ops-webhook"],
                )

                status, detail = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects",
                )
                self.assertEqual(status, 200)
                webhooks = detail["objects"]["webhooks"]
                self.assertEqual(len(webhooks), 2)
                managed = next(item for item in webhooks if item["id"] == "ops-webhook")
                self.assertEqual(managed["secretReadiness"][0]["env"], "MEDIAFLOW_WEBHOOK_SECRET")
                self.assertEqual(managed["secretReadiness"][0]["state"], "UNSET")
                self.assertTrue(managed["structuralValid"])
                self.assertNotIn("secret", managed)

                # Edit: add an event and reduce the retry window.
                edited = webhook_document(
                    events=["task.completed", "task.failed", "task.cancelled"],
                    maxRetrySeconds=30,
                )
                status, updated = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks/ops-webhook",
                    method="PUT",
                    body=json.dumps({"object": edited, "expectedVersion": 2}).encode(),
                )
                self.assertEqual(status, 200)
                self.assertEqual(updated["webhook"]["maxRetrySeconds"], 30)

                # Copy starts disabled with a unique id.
                status, copied = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks/ops-webhook/copy",
                    method="POST",
                    body=json.dumps({"expectedVersion": 3}).encode(),
                )
                self.assertEqual(status, 200)
                revision = harness.configuration.require(revision_id)
                ids = [item["id"] for item in revision.document["webhooks"]]
                self.assertIn("ops-webhook-copy", ids)
                copy_item = next(
                    item
                    for item in revision.document["webhooks"]
                    if item["id"] == "ops-webhook-copy"
                )
                self.assertFalse(copy_item["enabled"])

                # Enable copy, disable original.
                status, enabled = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks/ops-webhook-copy/enable",
                    method="POST",
                    body=json.dumps({"expectedVersion": 4}).encode(),
                )
                self.assertEqual(status, 200)
                status, disabled = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks/ops-webhook/disable",
                    method="POST",
                    body=json.dumps({"expectedVersion": 5}).encode(),
                )
                self.assertEqual(status, 200)
                revision = harness.configuration.require(revision_id)
                by_id = {item["id"]: item for item in revision.document["webhooks"]}
                self.assertTrue(by_id["ops-webhook-copy"]["enabled"])
                self.assertFalse(by_id["ops-webhook"]["enabled"])

                # Delete the copy; the original remains.
                status, deleted = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks/ops-webhook-copy",
                    method="DELETE",
                    body=json.dumps({"expectedVersion": 6}).encode(),
                )
                self.assertEqual(status, 200)
                revision = harness.configuration.require(revision_id)
                self.assertEqual(
                    [item["id"] for item in revision.document["webhooks"]],
                    ["operations-webhook", "ops-webhook"],
                )

                # Full document validation still passes.
                validated = harness.configuration.validate(revision_id, actor="ops")
                self.assertEqual(validated.validation_errors, ())

                # Viewer cannot mutate but can read.
                status, denied = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks",
                    method="POST",
                    body=json.dumps(
                        {"object": webhook_document(id="second"), "expectedVersion": 7}
                    ).encode(),
                    token="viewer-token",
                )
                self.assertEqual(status, 403)
                status, _ = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects",
                    token="viewer-token",
                )
                self.assertEqual(status, 200)
            finally:
                harness.close()

    def test_revision_authority_stale_writes_and_immutable_active(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = WebhookManagementHarness(directory)
            try:
                revision_id = harness.draft.revision_id
                status, created = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks",
                    method="POST",
                    body=json.dumps({"object": webhook_document(), "expectedVersion": 1}).encode(),
                )
                self.assertEqual(status, 200)

                # Stale write with an old version fails closed.
                status, stale = request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks/ops-webhook",
                    method="PUT",
                    body=json.dumps({"object": webhook_document(), "expectedVersion": 1}).encode(),
                )
                self.assertEqual(status, 409)
                self.assertEqual(stale["error"]["details"]["durableState"], "draft_preserved")

                # Activate and confirm the Active revision is immutable.
                active = _activate(harness)
                status, immutable = request(
                    harness.api,
                    f"/api/configuration/revisions/{active.revision_id}/objects/webhooks",
                    method="POST",
                    body=json.dumps(
                        {"object": webhook_document(id="second"), "expectedVersion": active.version}
                    ).encode(),
                )
                self.assertEqual(status, 409)
                self.assertEqual(harness.configuration.active().revision_id, active.revision_id)
                self.assertEqual(
                    {item["id"] for item in harness.configuration.active().document["webhooks"]},
                    {"operations-webhook", "ops-webhook"},
                )

                # A successor Draft is seeded from the exact Active and remains editable.
                successor = harness.configuration.create_successor_draft(actor="ops")
                self.assertEqual(successor.status, ManagedConfigurationStatus.DRAFT)
                self.assertEqual(
                    {item["id"] for item in successor.document["webhooks"]},
                    {"operations-webhook", "ops-webhook"},
                )

                # Activating the successor supersedes the first Active, which
                # stays immutable.
                validated = harness.configuration.validate(successor.revision_id, actor="ops")
                harness.configuration.activate(
                    successor.revision_id,
                    expected_version=validated.version,
                    actor="ops",
                )
                self.assertEqual(
                    harness.configuration.require(active.revision_id).status,
                    ManagedConfigurationStatus.SUPERSEDED,
                )
                status, superseded = request(
                    harness.api,
                    f"/api/configuration/revisions/{active.revision_id}/objects/webhooks",
                    method="POST",
                    body=json.dumps(
                        {"object": webhook_document(id="third"), "expectedVersion": active.version}
                    ).encode(),
                )
                self.assertEqual(status, 409)
                self.assertNotIn(
                    "third",
                    {item["id"] for item in harness.configuration.active().document["webhooks"]},
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

    def test_test_result_preserves_exact_revision_identity_when_draft_mutates_during_send(
        self,
    ) -> None:
        transport = MutatingTransport()
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
                # The tested identity is the immutable revision 2 snapshot.
                revision = harness.configuration.require(revision_id)
                self.assertEqual(revision.version, 2)
                expected_digest = revision.digest
                transport.configuration = harness.configuration
                transport.revision_id = revision_id

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
                # The Draft was mutated to version 3 while the fake transport sent.
                self.assertEqual(harness.configuration.require(revision_id).version, 3)
                self.assertNotEqual(
                    harness.configuration.require(revision_id).digest,
                    expected_digest,
                )
                # Evidence stays bound to the exact revision that was validated and sent.
                self.assertEqual(
                    result["revision"],
                    {
                        "revisionId": revision_id,
                        "version": 2,
                        "digest": expected_digest,
                        "status": "draft",
                    },
                )
                audits = harness.repository.list_security_audit(limit=50)
                webhook_audit = next(item for item in audits if item.action == "webhook-test")
                self.assertIn(f"version=2&digest={expected_digest}", webhook_audit.route)
                self.assertNotIn("version=3", webhook_audit.route)
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
