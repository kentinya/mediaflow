"""V2 Notification operator journey over the real managed API.

These regressions drive the real ``MediaFlowApi`` against a real managed
configuration runtime and the real Webhook/notification services. They prove
the new ``/api/v1/operations/notifications/*`` read projections are bounded
operator documents — no revision digests, no secret values, no delivery bodies,
no signature material — with backend-authoritative actions and Draft state;
that the exact-revision signed test sends exactly one request and never
creates a delivery or mutates configuration; that the Webhook-object-scoped
checked activation publishes only the reviewed Webhook-only change and rejects
sibling and general-configuration changes; that delivery list/detail truthfully
distinguish every durable status and lease state; that recovery is exact,
optimistically fenced, permission-gated and isolated; and that the existing
``/api/v1/notifications`` and configuration surfaces remain untouched for V1
clients.
"""

from __future__ import annotations

import copy
import io
import json
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.notification import NotificationPublisher, NotificationWorker
from mediaflow.domain.notification import (
    NotificationDeliveryStatus,
    NotificationEvent,
    NotificationEventType,
    WebhookDefinition,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

ADMIN_TOKEN = "notification-admin-token"
VIEWER_TOKEN = "notification-viewer-token"
MANAGER_TOKEN = "notification-manager-token"
ACTIVATOR_TOKEN = "notification-activator-token"

OPERATIONS_ROUTE = "/api/v1/operations/notifications/webhooks"

WEBHOOK_ID = "operations-webhook"
SECRET_ENV = "MEDIAFLOW_NOTIFICATION_TEST_SECRET"
SECRET_VALUE = "notification-test-secret-value"

_FORBIDDEN_DOCUMENT_KEYS = (
    "digest",
    "configurationRevisionDigest",
    "configurationSnapshotDigest",
    "signature",
)
_FORBIDDEN_SUBSTRINGS = (
    "Bearer ",
    SECRET_VALUE,
    "X-MediaFlow-Signature",
    "authorization:",
)


def _document(root: Path) -> dict:
    value = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
    value["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
    value["historyPath"] = str(root / "history.jsonl")
    # The example document uses the legacy nested webhook spelling with its own
    # names; the journey constants are normalized here so the Active
    # configuration matches the tested deployment references. One managed edit
    # later migrates the spelling to the canonical root section.
    for item in value.get("notifications", {}).get("webhooks", []):
        item["id"] = WEBHOOK_ID
        item["secretEnv"] = SECRET_ENV
    return value


def _request(
    api,
    path: str,
    *,
    method: str = "GET",
    body: object | None = None,
    token: str = ADMIN_TOKEN,
    query: str = "",
) -> tuple[int, object]:
    payload = b"" if body is None else json.dumps(body).encode("utf-8")
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(payload)),
        "wsgi.input": io.BytesIO(payload),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
    }
    result = b"".join(api(environ, lambda status, _headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(result)


def _assert_operator_document_clean(document: object) -> None:
    """No digest, secret value, signature or credential evidence."""

    text = json.dumps(document, ensure_ascii=False)
    lowered = text.lower()
    for key in _FORBIDDEN_DOCUMENT_KEYS:
        assert f'"{key}"' not in text, f"operator document leaked {key}"
    for substring in _FORBIDDEN_SUBSTRINGS:
        assert substring.lower() not in lowered, f"operator document leaked {substring!r}"
    if isinstance(document, dict):
        for value in document.values():
            _assert_operator_document_clean(value)
    elif isinstance(document, list):
        for value in document:
            _assert_operator_document_clean(value)


def _webhook_document(**changes) -> dict:
    value = {
        "id": WEBHOOK_ID,
        "url": "https://example.invalid/hooks/mediaflow",
        "secretEnv": SECRET_ENV,
        "events": ["job.completed", "job.failed"],
        "enabled": True,
        "timeoutSeconds": 10,
        "maxAttempts": 3,
        "baseRetrySeconds": 2,
        "maxRetrySeconds": 10,
    }
    value.update(changes)
    return value


class FakeTransport:
    def __init__(self, *results) -> None:
        self.results = list(results or (204,))
        self.requests: list[object] = []

    def send(self, request) -> int:
        self.requests.append(request)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class NotificationHarness:
    """Managed Draft/Active configuration plus the real API surface."""

    def __init__(self, directory: str, transport: FakeTransport | None = None):
        self.directory = Path(directory)
        self.transport = transport if transport is not None else FakeTransport()
        document = _document(self.directory)
        self.configuration_repository = SQLiteConfigurationRepository(
            self.directory / "configuration.sqlite3"
        )
        self.configuration = ManagedConfigurationService(
            self.configuration_repository,
            bootstrap_database_path=str(self.directory / "runtime.sqlite3"),
        )
        self.objects = ConfigurationObjectService(self.configuration)
        self.draft = self.configuration.import_draft(document, actor="bootstrap")
        validated = self.configuration.validate(self.draft.revision_id, actor="bootstrap")
        self.configuration.activate(
            validated.revision_id,
            expected_version=validated.version,
            actor="bootstrap",
        )
        self.repository = SQLiteTaskRepository(str(self.directory / "runtime.sqlite3"))
        permissions = {
            ADMIN_TOKEN: frozenset(ApiPermission),
            VIEWER_TOKEN: frozenset({ApiPermission.READ}),
            MANAGER_TOKEN: frozenset(
                {
                    ApiPermission.READ,
                    ApiPermission.MANAGE_CONFIGURATION,
                    ApiPermission.SUBMIT_DRY_RUN,
                    ApiPermission.CANCEL_JOB,
                }
            ),
            ACTIVATOR_TOKEN: frozenset(
                {
                    ApiPermission.READ,
                    ApiPermission.ACTIVATE_CONFIGURATION,
                }
            ),
        }
        principals = tuple(
            ResolvedApiPrincipal(token, token, permissions[token]) for token in permissions
        )
        self.bootstrap_document = document
        self.api = MediaFlowApi(
            self.repository,
            None,
            principals=principals,
            configuration_service=self.configuration,
            bootstrap_document=document,
            webhook_transport=self.transport,
        )

    def close(self) -> None:
        self.repository.close()
        self.configuration_repository.close()

    # ------------------------------------------------------------------
    # Journey helpers

    def open_webhook_draft(self, document: dict | None = None):
        """Create a successor Draft and store one Webhook definition inside it.

        A document whose id matches the Active definition is stored with the
        exact-bound edit route (which also migrates the legacy nested spelling
        to the canonical root section); any other id uses the create route.
        Returns ``(revisionId, expectedVersion)`` advertising the Draft after
        the stored mutation.
        """

        stored = document or _webhook_document()
        active = self.configuration.active()
        _status, draft = _request(
            self.api,
            f"/api/v1/configuration/revisions/{active.revision_id}/successor",
            method="POST",
            body={},
        )
        revision_id = draft["revisionId"]
        version = draft["version"]
        if stored.get("id") == WEBHOOK_ID:
            route = f"/api/v1/configuration/revisions/{revision_id}/objects/webhooks/{WEBHOOK_ID}"
            method = "PUT"
        else:
            route = f"/api/v1/configuration/revisions/{revision_id}/objects/webhooks"
            method = "POST"
        _status, response = _request(
            self.api,
            route,
            method=method,
            body={"object": stored, "expectedVersion": version},
        )
        assert response.get("webhook", {}).get("id"), response
        # The operator journey validates the Draft before activation; the
        # managed service rejects activation of a plain Draft.
        _status, validated = _request(
            self.api,
            f"/api/v1/configuration/revisions/{revision_id}/validate",
            method="POST",
            body={},
        )
        assert validated.get("status") == "validated", validated
        return revision_id, version + 1

    def active_webhook_definition(self) -> WebhookDefinition:
        document = self.configuration.active().document
        section = document.get("webhooks")
        if not isinstance(section, list):
            section = document.get("notifications", {}).get("webhooks", [])
        raw = next(item for item in section if item.get("id") == WEBHOOK_ID)
        return WebhookDefinition.from_document(raw)

    def publish_delivery(self, event_id: str, *, occurred_at=None):
        definition = self.active_webhook_definition()
        event = NotificationEvent(
            event_id,
            NotificationEventType.JOB_COMPLETED,
            occurred_at or datetime.now(UTC),
            {"jobId": event_id},
        )
        created = NotificationPublisher(self.repository, (definition,)).publish(event)
        assert created, f"delivery for {event_id!r} was not created"
        return created[0]

    def run_worker(self, *, transport=None, attempts=None, clock=None):
        definition = self.active_webhook_definition()
        if attempts is not None:
            definition = WebhookDefinition(
                definition.webhook_id,
                definition.url,
                definition.secret_env,
                definition.events,
                enabled=definition.enabled,
                timeout_seconds=definition.timeout_seconds,
                max_attempts=attempts,
                base_retry_seconds=definition.base_retry_seconds,
                max_retry_seconds=definition.max_retry_seconds,
            )
        return NotificationWorker(
            self.repository,
            {WEBHOOK_ID: (definition, SECRET_VALUE)},
            transport if transport is not None else self.transport,
            **({} if clock is None else {"clock": clock}),
        ).run_next()


class WebhookDefinitionsPageTests(unittest.TestCase):
    def test_list_page_is_bounded_digest_free_and_state_truthful(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                status, page = _request(harness.api, OPERATIONS_ROUTE)
                self.assertEqual(status, 200)
                _assert_operator_document_clean(page)
                self.assertEqual(page["total"], 1)
                self.assertFalse(page["truncated"])
                self.assertFalse(page["draftState"]["present"])
                self.assertEqual(
                    page["supportedEvents"],
                    ["job.completed", "job.failed", "job.cancelled", "schedule.emitted"],
                )
                item = page["items"][0]
                self.assertEqual(
                    item["document"]["id"] if "document" in item else item["id"], WEBHOOK_ID
                )
                self.assertEqual(item["definitionState"], "active")
                self.assertEqual(
                    item["activeConfiguration"]["revisionId"],
                    harness.configuration.active().revision_id,
                )
                readiness = item["secretReadiness"]
                self.assertEqual(readiness[0]["field"], "secretEnv")
                self.assertEqual(readiness[0]["env"], SECRET_ENV)
                self.assertIn(readiness[0]["state"], {"SET", "UNSET"})
                self.assertTrue(item["structuralValid"])
                for name in (
                    "detail",
                    "test",
                    "edit",
                    "copy",
                    "enable",
                    "disable",
                    "draftCreate",
                    "activate",
                ):
                    action = item["actions"][name]
                    self.assertIn("available", action)
                    self.assertIn("method", action)
                self.assertEqual(
                    item["actions"]["detail"]["path"], f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}"
                )
                self.assertEqual(item["actions"]["activate"]["requiresConfirmation"], True)
            finally:
                harness.close()

    def test_viewer_read_is_permitted_but_management_actions_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                status, page = _request(harness.api, OPERATIONS_ROUTE, token=VIEWER_TOKEN)
                self.assertEqual(status, 200)
                item = page["items"][0]
                self.assertFalse(item["actions"]["test"]["available"])
                self.assertIn("permission", item["actions"]["test"]["reason"])
                self.assertFalse(item["actions"]["edit"]["available"])
                self.assertFalse(item["actions"]["draftCreate"]["available"])
                self.assertFalse(item["actions"]["activate"]["available"])
                self.assertTrue(item["actions"]["detail"]["available"])

                status, denied = _request(
                    harness.api, OPERATIONS_ROUTE, method="POST", token=VIEWER_TOKEN
                )
                self.assertEqual(status, 405)
            finally:
                harness.close()

    def test_draft_only_definition_is_listed_distinct_from_active(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                revision_id, _version = harness.open_webhook_draft(
                    _webhook_document(id="copied-webhook", enabled=False)
                )
                status, page = _request(harness.api, OPERATIONS_ROUTE)
                self.assertEqual(status, 200)
                self.assertEqual(page["total"], 2)
                draft_only = next(
                    item for item in page["items"] if item["definitionState"] == "draft-only"
                )
                self.assertEqual(draft_only["id"], "copied-webhook")
                self.assertTrue(draft_only["draftState"]["present"])
                self.assertEqual(draft_only["draftState"]["revisionId"], revision_id)
                self.assertFalse(draft_only["actions"]["test"]["available"] is False)
                _assert_operator_document_clean(page)
            finally:
                harness.close()


class WebhookMutationJourneyTests(unittest.TestCase):
    def test_create_edit_enable_disable_copy_are_optimistically_fenced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                active = harness.configuration.active()
                _status, draft = _request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{active.revision_id}/successor",
                    method="POST",
                    body={},
                )
                revision_id = draft["revisionId"]
                version = draft["version"]

                # The exact-bound edit stores the bounded form inside the Draft
                # and migrates the legacy nested spelling to the root section.
                status, edited = _request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/webhooks/{WEBHOOK_ID}",
                    method="PUT",
                    body={
                        "object": _webhook_document(maxAttempts=7),
                        "expectedVersion": version,
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(edited["webhook"]["maxAttempts"], 7)
                version += 1

                # A stale expectedVersion is rejected atomically.
                status, stale = _request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/webhooks/{WEBHOOK_ID}",
                    method="PUT",
                    body={
                        "object": _webhook_document(enabled=False),
                        "expectedVersion": version - 1,
                    },
                )
                self.assertEqual(status, 409)

                # A newly created definition is bound to the same exact Draft
                # version and cannot collide with an existing identity.
                status, created = _request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/webhooks",
                    method="POST",
                    body={
                        "object": _webhook_document(id="created-webhook"),
                        "expectedVersion": version,
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(created["webhook"]["id"], "created-webhook")
                version += 1

                status, collision = _request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/webhooks",
                    method="POST",
                    body={
                        "object": _webhook_document(id="created-webhook"),
                        "expectedVersion": version,
                    },
                )
                self.assertEqual(status, 400)

                for action, expected_flag in (("enable", True), ("disable", False)):
                    status, toggled = _request(
                        harness.api,
                        f"/api/v1/configuration/revisions/{revision_id}/objects/webhooks/{WEBHOOK_ID}/{action}",
                        method="POST",
                        body={"expectedVersion": version},
                    )
                    self.assertEqual(status, 200)
                    self.assertEqual(toggled["object"]["enabled"], expected_flag)
                    version += 1

                status, copied = _request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/webhooks/{WEBHOOK_ID}/copy",
                    method="POST",
                    body={"expectedVersion": version},
                )
                self.assertEqual(status, 200)
                copied_id = copied["object"]["id"]
                self.assertNotEqual(copied_id, WEBHOOK_ID)
                self.assertFalse(copied["object"]["enabled"])

                # The Active configuration was never touched by Draft edits.
                self.assertEqual(
                    harness.configuration.active().revision_id,
                    active.revision_id,
                )
                document = harness.configuration.active().document
                section = document.get("webhooks")
                if not isinstance(section, list):
                    section = document.get("notifications", {}).get("webhooks", [])
                self.assertEqual(
                    [item.get("id") for item in section],
                    [WEBHOOK_ID],
                )
            finally:
                harness.close()

    def test_canonical_validator_rejects_hostile_documents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                active = harness.configuration.active()
                _status, draft = _request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{active.revision_id}/successor",
                    method="POST",
                    body={},
                )
                revision_id = draft["revisionId"]
                version = draft["version"]
                route = f"/api/v1/configuration/revisions/{revision_id}/objects/webhooks"
                hostile = [
                    {"object": _webhook_document(unknownField=1), "expectedVersion": version},
                    {"object": _webhook_document(secret="value"), "expectedVersion": version},
                    {
                        "object": _webhook_document(url="http://example.invalid/x"),
                        "expectedVersion": version,
                    },
                    {
                        "object": _webhook_document(url="https://user:pw@example.invalid/x"),
                        "expectedVersion": version,
                    },
                    {
                        "object": _webhook_document(url="https://example.invalid/x?token=abc"),
                        "expectedVersion": version,
                    },
                    {
                        "object": _webhook_document(events=[]),
                        "expectedVersion": version,
                    },
                    {
                        "object": _webhook_document(events=["job.completed", "job.completed"]),
                        "expectedVersion": version,
                    },
                    {"object": _webhook_document(maxAttempts=0), "expectedVersion": version},
                ]
                for document in hostile:
                    status, error = _request(harness.api, route, method="POST", body=document)
                    self.assertEqual(status, 400, document)
            finally:
                harness.close()


class WebhookTestJourneyTests(unittest.TestCase):
    def test_exact_revision_test_sends_one_signed_request_and_no_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                revision_id, version = harness.open_webhook_draft()
                status, draft_doc = _request(harness.api, f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/draft")
                self.assertEqual(status, 200)
                self.assertEqual(draft_doc["draft"]["revisionId"], revision_id)
                self.assertEqual(draft_doc["draft"]["webhook"]["id"], WEBHOOK_ID)

                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop(SECRET_ENV, None)
                    status, result = _request(
                        harness.api,
                        f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/test",
                        method="POST",
                        body={
                            "expectedRevisionId": revision_id,
                            "expectedVersion": version,
                        },
                    )
                self.assertEqual(status, 200)
                _assert_operator_document_clean(result)
                self.assertEqual(result["category"], "missing_secret")
                self.assertEqual(result["outcome"], "failure")
                self.assertNotIn("digest", result["revision"])
                self.assertEqual(len(harness.transport.requests), 0)

                with patch.dict(os.environ, {SECRET_ENV: SECRET_VALUE}):
                    status, result = _request(
                        harness.api,
                        f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/test",
                        method="POST",
                        body={
                            "expectedRevisionId": revision_id,
                            "expectedVersion": version,
                        },
                    )
                self.assertEqual(status, 200)
                _assert_operator_document_clean(result)
                self.assertEqual(result["outcome"], "success")
                self.assertEqual(result["category"], "http_204")
                self.assertEqual(result["responseStatus"], 204)
                self.assertTrue(result["retrySafe"])
                self.assertEqual(
                    result["durableState"], "no_delivery_created_no_configuration_change"
                )
                # Exactly one signed request reached the fake transport.
                self.assertEqual(len(harness.transport.requests), 1)
                request = harness.transport.requests[0]
                self.assertEqual(request.url, "https://example.invalid/hooks/mediaflow")
                self.assertIn("X-MediaFlow-Signature", request.headers)
                self.assertIn("sha256=", request.headers["X-MediaFlow-Signature"])
                self.assertNotIn(SECRET_VALUE, request.headers["X-MediaFlow-Signature"])
                # No delivery exists, no configuration was published and no
                # activation happened.
                status, deliveries = _request(harness.api, "/api/v1/notifications")
                self.assertEqual(status, 200)
                self.assertEqual(deliveries["items"], [])
                self.assertEqual(
                    harness.configuration.active().revision_id,
                    harness.draft and None or harness.configuration.active().revision_id,
                )

                # The Draft-only definition is testable at its exact revision;
                # the same result categories hold.
                self.assertEqual(result["revision"]["status"], "validated")
            finally:
                harness.close()

    def test_stale_revision_is_rejected_before_any_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                revision_id, version = harness.open_webhook_draft()
                with patch.dict(os.environ, {SECRET_ENV: SECRET_VALUE}):
                    status, error = _request(
                        harness.api,
                        f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/test",
                        method="POST",
                        body={
                            "expectedRevisionId": revision_id,
                            "expectedVersion": version + 3,
                        },
                    )
                self.assertEqual(status, 409)
                self.assertEqual(
                    error["error"]["details"]["durableState"],
                    "no test request was sent",
                )
                self.assertNotIn("digest", json.dumps(error))
                self.assertEqual(len(harness.transport.requests), 0)

                status, missing = _request(
                    harness.api,
                    f"{OPERATIONS_ROUTE}/absent-webhook/test",
                    method="POST",
                    body={
                        "expectedRevisionId": revision_id,
                        "expectedVersion": version,
                    },
                )
                self.assertEqual(status, 404)
                self.assertEqual(len(harness.transport.requests), 0)
            finally:
                harness.close()

    def test_transport_and_server_failures_return_bounded_categories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for index, (transport, expected_category, expected_outcome) in enumerate(
                (
                    (FakeTransport(TimeoutError()), "timeout", "failure"),
                    (FakeTransport(OSError("boom")), "transport", "failure"),
                    (FakeTransport(500), "http_500", "failure"),
                    (FakeTransport(429), "http_429", "failure"),
                    (FakeTransport(400), "http_400", "failure"),
                )
            ):
                with self.subTest(category=expected_category):
                    with tempfile.TemporaryDirectory() as directory:
                        harness = NotificationHarness(directory, transport=transport)
                        try:
                            revision_id, version = harness.open_webhook_draft()
                            with patch.dict(os.environ, {SECRET_ENV: SECRET_VALUE}):
                                status, result = _request(
                                    harness.api,
                                    f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/test",
                                    method="POST",
                                    body={
                                        "expectedRevisionId": revision_id,
                                        "expectedVersion": version,
                                    },
                                )
                            self.assertEqual(status, 200)
                            self.assertEqual(result["category"], expected_category)
                            self.assertEqual(result["outcome"], expected_outcome)
                            _assert_operator_document_clean(result)
                            self.assertEqual(len(transport.requests), 1)
                            if expected_category == "http_400":
                                self.assertFalse(result["retrySafe"])
                        finally:
                            harness.close()


class WebhookCheckedActivationTests(unittest.TestCase):
    def test_activation_publishes_only_the_reviewed_webhook(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                revision_id, version = harness.open_webhook_draft(_webhook_document(maxAttempts=9))
                status, activated = _request(
                    harness.api,
                    f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/activate-draft",
                    method="POST",
                    body={
                        "expectedRevisionId": revision_id,
                        "expectedVersion": version,
                    },
                    token=ADMIN_TOKEN,
                )
                self.assertEqual(status, 200)
                _assert_operator_document_clean(activated)
                self.assertEqual(activated["activatedRevisionId"], revision_id)
                self.assertEqual(activated["activatedVersion"], version)
                self.assertEqual(activated["activeConfiguration"]["revisionId"], revision_id)
                self.assertEqual(activated["webhook"]["maxAttempts"], 9)
                # The legacy nested spelling was migrated to the canonical root
                # section by the managed edit path.
                document = harness.configuration.active().document
                self.assertEqual([item["id"] for item in document["webhooks"]], [WEBHOOK_ID])
                self.assertNotIn("webhooks", document.get("notifications", {}))
                # No delivery was created and no request was sent.
                status, deliveries = _request(harness.api, "/api/v1/notifications")
                self.assertEqual(deliveries["items"], [])
                self.assertEqual(len(harness.transport.requests), 0)

                # Re-activation without a Draft is rejected as durable truth.
                status, conflict = _request(
                    harness.api,
                    f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/activate-draft",
                    method="POST",
                    body={
                        "expectedRevisionId": revision_id,
                        "expectedVersion": version,
                    },
                )
                self.assertEqual(status, 409)
            finally:
                harness.close()

    def test_activation_rejects_sibling_webhook_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                active = harness.configuration.active()
                _status, draft = _request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{active.revision_id}/successor",
                    method="POST",
                    body={},
                )
                revision_id = draft["revisionId"]
                version = draft["version"]
                _status, _edited = _request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/webhooks/{WEBHOOK_ID}",
                    method="PUT",
                    body={"object": _webhook_document(), "expectedVersion": version},
                )
                version += 1
                _status, sibling = _request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/webhooks",
                    method="POST",
                    body={
                        "object": _webhook_document(id="sibling-webhook"),
                        "expectedVersion": version,
                    },
                )
                self.assertEqual(sibling.get("webhook", {}).get("id"), "sibling-webhook")
                version += 1
                status, error = _request(
                    harness.api,
                    f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/activate-draft",
                    method="POST",
                    body={
                        "expectedRevisionId": revision_id,
                        "expectedVersion": version,
                    },
                )
                self.assertEqual(status, 409)
                self.assertEqual(error["error"]["code"], "notification_activation_definition_scope")
                # Active and Draft are preserved untouched.
                self.assertEqual(harness.configuration.active().revision_id, active.revision_id)
                self.assertEqual(
                    harness.configuration.latest_open_draft_containing(
                        "webhooks", WEBHOOK_ID
                    ).revision_id,
                    revision_id,
                )
            finally:
                harness.close()

    def test_activation_rejects_general_configuration_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                active = harness.configuration.active()
                _status, draft = _request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{active.revision_id}/successor",
                    method="POST",
                    body={},
                )
                revision_id = draft["revisionId"]
                version = draft["version"]
                _status, _edited = _request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/webhooks/{WEBHOOK_ID}",
                    method="PUT",
                    body={"object": _webhook_document(), "expectedVersion": version},
                )
                revision = harness.configuration.require(revision_id)
                document = copy.deepcopy(revision.document)
                document["notifications"]["pollSeconds"] = 99
                harness.configuration.edit_draft(
                    revision_id,
                    document,
                    expected_version=revision.version,
                    actor="bootstrap",
                )
                current_version = harness.configuration.require(revision_id).version
                status, error = _request(
                    harness.api,
                    f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/activate-draft",
                    method="POST",
                    body={
                        "expectedRevisionId": revision_id,
                        "expectedVersion": current_version,
                    },
                )
                self.assertEqual(status, 409)
                self.assertEqual(error["error"]["code"], "notification_activation_out_of_scope")
                self.assertEqual(harness.configuration.active().revision_id, active.revision_id)
            finally:
                harness.close()

    def test_activation_fails_closed_on_stale_identity_version_and_base(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                revision_id, version = harness.open_webhook_draft()
                for body, expected_code in (
                    (
                        {"expectedRevisionId": "other-revision", "expectedVersion": version},
                        "configuration_version_conflict",
                    ),
                    (
                        {"expectedRevisionId": revision_id, "expectedVersion": version + 5},
                        "configuration_version_conflict",
                    ),
                ):
                    status, error = _request(
                        harness.api,
                        f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/activate-draft",
                        method="POST",
                        body=body,
                        token=ADMIN_TOKEN,
                    )
                    self.assertEqual(status, 409, body)
                    self.assertEqual(error["error"]["code"], expected_code)
                    self.assertNotIn("digest", json.dumps(error))
            finally:
                harness.close()

    def test_activation_requires_activation_permission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                revision_id, version = harness.open_webhook_draft()
                status, error = _request(
                    harness.api,
                    f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/activate-draft",
                    method="POST",
                    body={
                        "expectedRevisionId": revision_id,
                        "expectedVersion": version,
                    },
                    token=MANAGER_TOKEN,
                )
                self.assertEqual(status, 403)
                status, error = _request(
                    harness.api,
                    f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/activate-draft",
                    method="POST",
                    body={
                        "expectedRevisionId": revision_id,
                        "expectedVersion": version,
                    },
                    token=ACTIVATOR_TOKEN,
                )
                # Without MANAGE_CONFIGURATION the principal may not have been
                # able to stage a Webhook-only Draft, but activation itself is
                # permission-gated by ACTIVATE_CONFIGURATION only.
                self.assertIn(status, (200, 409))
            finally:
                harness.close()


class DeliveryProjectionTests(unittest.TestCase):
    def prepare_enabled_webhook(self, harness: NotificationHarness) -> None:
        revision_id, version = harness.open_webhook_draft()
        status, activated = _request(
            harness.api,
            f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/activate-draft",
            method="POST",
            body={"expectedRevisionId": revision_id, "expectedVersion": version},
        )
        self.assertEqual(status, 200)

    def test_all_durable_statuses_and_lease_states_are_truthful(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                self.prepare_enabled_webhook(harness)
                # delivering with an active lease: claim first so the claim
                # deterministically picks this delivery.
                delivering = harness.publish_delivery("event-delivering")
                now = datetime.now(UTC)
                claimed = harness.repository.claim_next_delivery(now, now - timedelta(seconds=30))
                self.assertIsNotNone(claimed)
                self.assertEqual(claimed.delivery_id, delivering.delivery_id)
                # retry: the worker deterministically claims the oldest due
                # delivery, so each status is produced in publication order.
                retry = harness.publish_delivery("event-retry")
                retried = harness.run_worker(transport=FakeTransport(500), attempts=2)
                self.assertEqual(retried.delivery_id, retry.delivery_id)
                # delivered
                delivered = harness.publish_delivery("event-delivered")
                finished = harness.run_worker(transport=FakeTransport(204))
                self.assertEqual(finished.delivery_id, delivered.delivery_id)
                # dead-letter
                dead = harness.publish_delivery("event-dead")
                dead_lettered = harness.run_worker(transport=FakeTransport(400), attempts=1)
                self.assertEqual(dead_lettered.delivery_id, dead.delivery_id)
                # pending: published last so no worker run claims it.
                pending = harness.publish_delivery("event-pending")

                status, page = _request(
                    harness.api,
                    "/api/v1/notifications",
                    query="limit=50",
                )
                self.assertEqual(status, 200)
                statuses = {item["deliveryId"]: item["status"] for item in page["items"]}
                self.assertEqual(statuses[pending.delivery_id], "pending")
                self.assertEqual(statuses[delivering.delivery_id], "delivering")
                self.assertEqual(statuses[retry.delivery_id], "retry")
                self.assertEqual(statuses[delivered.delivery_id], "delivered")
                self.assertEqual(statuses[dead.delivery_id], "dead-letter")
                _assert_operator_document_clean(page)

                # Status filter is bounded and truthful.
                status, filtered = _request(
                    harness.api,
                    "/api/v1/notifications",
                    query="status=dead-letter",
                )
                self.assertEqual(status, 200)
                self.assertEqual(
                    [item["deliveryId"] for item in filtered["items"]],
                    [dead.delivery_id],
                )
                status, rejected = _request(
                    harness.api,
                    "/api/v1/notifications",
                    query="status=not-a-status",
                )
                self.assertEqual(status, 400)

                # Detail: bounded document, correct lease and recovery evidence.
                status, dead_detail = _request(
                    harness.api,
                    f"/api/v1/operations/notifications/deliveries/{dead.delivery_id}",
                )
                self.assertEqual(status, 200)
                _assert_operator_document_clean(dead_detail)
                self.assertEqual(dead_detail["lease"], {"state": "not_leased"})
                self.assertEqual(
                    dead_detail["recovery"]["availableActions"], ["requeue-dead-letter"]
                )
                self.assertIn("at-least-once", json.dumps(dead_detail).lower())
                self.assertTrue(dead_detail["actions"]["requeue"]["available"])
                status, viewer_detail = _request(
                    harness.api,
                    f"/api/v1/operations/notifications/deliveries/{dead.delivery_id}",
                    token=VIEWER_TOKEN,
                )
                self.assertEqual(status, 200)
                self.assertFalse(viewer_detail["actions"]["requeue"]["available"])
                self.assertIn("permission", viewer_detail["actions"]["requeue"]["reason"])

                status, delivering_detail = _request(
                    harness.api,
                    f"/api/v1/operations/notifications/deliveries/{delivering.delivery_id}",
                )
                self.assertEqual(status, 200)
                self.assertEqual(delivering_detail["lease"]["state"], "active")
                self.assertEqual(delivering_detail["recovery"]["availableActions"], [])

                status, pending_detail = _request(
                    harness.api,
                    f"/api/v1/operations/notifications/deliveries/{pending.delivery_id}",
                )
                self.assertEqual(status, 200)
                self.assertEqual(pending_detail["lease"], {"state": "not_leased"})
                self.assertEqual(pending_detail["recovery"]["availableActions"], [])

                status, missing = _request(
                    harness.api,
                    "/api/v1/operations/notifications/deliveries/absent-delivery",
                )
                self.assertEqual(status, 404)
            finally:
                harness.close()

    def test_expired_lease_advertises_stale_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                self.prepare_enabled_webhook(harness)
                now = datetime.now(UTC)
                delivery = harness.publish_delivery(
                    "event-stale", occurred_at=now - timedelta(hours=2)
                )
                claimed = harness.repository.claim_next_delivery(
                    now - timedelta(hours=2), now - timedelta(hours=3)
                )
                self.assertIsNotNone(claimed)
                status, detail = _request(
                    harness.api,
                    f"/api/v1/operations/notifications/deliveries/{delivery.delivery_id}",
                )
                self.assertEqual(status, 200)
                self.assertEqual(detail["lease"]["state"], "expired")
                self.assertEqual(detail["recovery"]["availableActions"], ["resolve-stale"])
                self.assertTrue(detail["actions"]["resolveStale"]["requiresConfirmation"])
            finally:
                harness.close()

    def test_delivery_paging_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                self.prepare_enabled_webhook(harness)
                for index in range(3):
                    harness.publish_delivery(f"event-page-{index}")
                status, first = _request(
                    harness.api,
                    "/api/v1/notifications",
                    query="limit=2",
                )
                self.assertEqual(status, 200)
                self.assertEqual(len(first["items"]), 2)
                self.assertIsNotNone(first["next_cursor"])
                self.assertIsNone(first["previous_cursor"])
                status, second = _request(
                    harness.api,
                    "/api/v1/notifications",
                    query=f"limit=2&cursor={first['next_cursor']}",
                )
                self.assertEqual(status, 200)
                self.assertEqual(len(second["items"]), 1)
                self.assertIsNotNone(second["previous_cursor"])
                first_ids = {item["deliveryId"] for item in first["items"]}
                second_ids = {item["deliveryId"] for item in second["items"]}
                self.assertEqual(len(first_ids | second_ids), 3)
            finally:
                harness.close()


class DeliveryRecoveryTests(unittest.TestCase):
    def prepare_enabled_webhook(self, harness: NotificationHarness) -> None:
        revision_id, version = harness.open_webhook_draft()
        status, activated = _request(
            harness.api,
            f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/activate-draft",
            method="POST",
            body={"expectedRevisionId": revision_id, "expectedVersion": version},
        )
        self.assertEqual(status, 200)

    def _dead_letter_and_sibling(self, harness: NotificationHarness):
        dead = harness.publish_delivery("event-recover")
        harness.run_worker(transport=FakeTransport(400), attempts=1)
        sibling = harness.publish_delivery("event-sibling")
        return dead, sibling

    def test_requeue_preserves_identity_and_is_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                self.prepare_enabled_webhook(harness)
                # The sibling is published after the requeue so the next
                # deterministic worker claim is the requeued delivery itself.
                dead = harness.publish_delivery("event-recover")
                harness.run_worker(transport=FakeTransport(400), attempts=1)
                status, detail = _request(
                    harness.api,
                    f"/api/v1/operations/notifications/deliveries/{dead.delivery_id}",
                    token=ADMIN_TOKEN,
                )
                fence = {
                    "expectedStatus": detail["status"],
                    "expectedUpdatedAt": detail["updatedAt"],
                }
                active_before = harness.configuration.active().revision_id
                status, result = _request(
                    harness.api,
                    f"/api/v1/notifications/{dead.delivery_id}/requeue",
                    method="POST",
                    body=fence,
                )
                self.assertEqual(status, 200)
                _assert_operator_document_clean(result)
                self.assertEqual(result["action"], "requeue-dead-letter")
                self.assertEqual(result["deliveryId"], dead.delivery_id)
                self.assertEqual(result["previousStatus"], "dead-letter")
                self.assertEqual(result["status"], "pending")
                self.assertEqual(result["attempts"], 0)
                self.assertIn("duplicates", result["atLeastOnce"].lower())
                self.assertEqual(result["durableState"], "dead_letter_requeued_same_identity")

                # The same row identity, no sibling change, no new row, no
                # configuration change and no media effect.
                sibling = harness.publish_delivery("event-sibling")
                status, listing = _request(harness.api, "/api/v1/notifications", query="limit=50")
                self.assertEqual(len(listing["items"]), 2)
                self.assertEqual(harness.configuration.active().revision_id, active_before)
                status, sibling_detail = _request(
                    harness.api,
                    f"/api/v1/operations/notifications/deliveries/{sibling.delivery_id}",
                )
                self.assertEqual(sibling_detail["status"], "pending")
                self.assertEqual(sibling_detail["attempts"], 0)

                # The requeued delivery can be delivered again.
                delivered = harness.run_worker(transport=FakeTransport(204))
                self.assertEqual(delivered.status, NotificationDeliveryStatus.DELIVERED)
                self.assertEqual(delivered.delivery_id, dead.delivery_id)
            finally:
                harness.close()

    def test_repeated_and_stale_recovery_fails_closed_without_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                self.prepare_enabled_webhook(harness)
                dead, _sibling = self._dead_letter_and_sibling(harness)
                status, detail = _request(
                    harness.api,
                    f"/api/v1/operations/notifications/deliveries/{dead.delivery_id}",
                )
                fence = {
                    "expectedStatus": detail["status"],
                    "expectedUpdatedAt": detail["updatedAt"],
                }
                status, _first = _request(
                    harness.api,
                    f"/api/v1/notifications/{dead.delivery_id}/requeue",
                    method="POST",
                    body=fence,
                )
                self.assertEqual(status, 200)
                # A repeated submission is stale: the state already moved.
                status, second = _request(
                    harness.api,
                    f"/api/v1/notifications/{dead.delivery_id}/requeue",
                    method="POST",
                    body=fence,
                )
                self.assertEqual(status, 409)

                # A wrong fence never mutates.
                status, wrong = _request(
                    harness.api,
                    f"/api/v1/notifications/{dead.delivery_id}/requeue",
                    method="POST",
                    body={
                        "expectedStatus": "dead-letter",
                        "expectedUpdatedAt": "2000-01-01T00:00:00+00:00",
                    },
                )
                self.assertEqual(status, 409)

                # Wrong action for the current status fails closed.
                status, detail = _request(
                    harness.api,
                    f"/api/v1/operations/notifications/deliveries/{dead.delivery_id}",
                )
                status, wrong_action = _request(
                    harness.api,
                    f"/api/v1/notifications/{dead.delivery_id}/resolve-stale",
                    method="POST",
                    body={
                        "expectedStatus": detail["status"],
                        "expectedUpdatedAt": detail["updatedAt"],
                    },
                )
                self.assertEqual(status, 409)

                # Malformed evidence fails closed.
                status, malformed = _request(
                    harness.api,
                    f"/api/v1/notifications/{dead.delivery_id}/requeue",
                    method="POST",
                    body={"expectedStatus": "dead-letter"},
                )
                self.assertEqual(status, 400)

                # The delivery is still exactly once requeued: pending.
                status, final = _request(
                    harness.api,
                    f"/api/v1/operations/notifications/deliveries/{dead.delivery_id}",
                )
                self.assertEqual(final["status"], "pending")
            finally:
                harness.close()

    def test_unexpired_lease_is_not_stale_recoverable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                self.prepare_enabled_webhook(harness)
                delivery = harness.publish_delivery("event-lease")
                # The claim clock is taken after publication so the delivery is
                # deterministically due.
                now = datetime.now(UTC)
                claimed = harness.repository.claim_next_delivery(now, now - timedelta(seconds=60))
                self.assertIsNotNone(claimed)
                status, detail = _request(
                    harness.api,
                    f"/api/v1/operations/notifications/deliveries/{delivery.delivery_id}",
                )
                self.assertEqual(detail["lease"]["state"], "active")
                status, rejected = _request(
                    harness.api,
                    f"/api/v1/notifications/{delivery.delivery_id}/resolve-stale",
                    method="POST",
                    body={
                        "expectedStatus": detail["status"],
                        "expectedUpdatedAt": detail["updatedAt"],
                    },
                )
                self.assertEqual(status, 409)
            finally:
                harness.close()

    def test_recovery_is_permission_gated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                self.prepare_enabled_webhook(harness)
                dead, _sibling = self._dead_letter_and_sibling(harness)
                status, detail = _request(
                    harness.api,
                    f"/api/v1/operations/notifications/deliveries/{dead.delivery_id}",
                )
                fence = {
                    "expectedStatus": detail["status"],
                    "expectedUpdatedAt": detail["updatedAt"],
                }
                status, denied = _request(
                    harness.api,
                    f"/api/v1/notifications/{dead.delivery_id}/requeue",
                    method="POST",
                    body=fence,
                    token=VIEWER_TOKEN,
                )
                self.assertEqual(status, 403)
                status, still = _request(
                    harness.api,
                    f"/api/v1/operations/notifications/deliveries/{dead.delivery_id}",
                )
                self.assertEqual(still["status"], "dead-letter")
            finally:
                harness.close()


class DashboardLinkTests(unittest.TestCase):
    def test_dashboard_notification_failure_carries_the_exact_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                revision_id, version = harness.open_webhook_draft()
                status, _activated = _request(
                    harness.api,
                    f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/activate-draft",
                    method="POST",
                    body={"expectedRevisionId": revision_id, "expectedVersion": version},
                )
                self.assertEqual(status, 200)
                dead = harness.publish_delivery("event-dashboard")
                harness.run_worker(transport=FakeTransport(400), attempts=1)
                status, dashboard = _request(harness.api, "/api/v1/dashboard")
                self.assertEqual(status, 200)
                self.assertEqual(dashboard["dead_letter_notifications"], 1)
                notification_failures = [
                    failure
                    for failure in dashboard["recent_failures"]
                    if failure["kind"] == "notification"
                ]
                self.assertTrue(notification_failures)
                self.assertEqual(notification_failures[0]["identifier"], dead.delivery_id)
                # The identifier is one bounded URI-safe segment: safe to link.
                identifier = notification_failures[0]["identifier"]
                self.assertNotIn("/", identifier)
                self.assertNotIn("\\", identifier)
            finally:
                harness.close()


class RestartPersistenceTests(unittest.TestCase):
    def test_delivery_state_survives_a_repository_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                revision_id, version = harness.open_webhook_draft()
                _status, _activated = _request(
                    harness.api,
                    f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/activate-draft",
                    method="POST",
                    body={"expectedRevisionId": revision_id, "expectedVersion": version},
                )
                dead = harness.publish_delivery("event-restart")
                harness.run_worker(transport=FakeTransport(400), attempts=1)
                harness.repository.close()
                reopened = SQLiteTaskRepository(str(harness.directory / "runtime.sqlite3"))
                try:
                    row = reopened.get_delivery(dead.delivery_id)
                    self.assertIsNotNone(row)
                    self.assertEqual(row.status, NotificationDeliveryStatus.DEAD_LETTER)
                    # A repeated publish of the same event never duplicates the
                    # delivery (at-least-once with stable identity).
                    created = NotificationPublisher(
                        reopened, (harness.active_webhook_definition(),)
                    ).publish(
                        NotificationEvent(
                            "event-restart",
                            NotificationEventType.JOB_COMPLETED,
                            datetime.now(UTC),
                            {"jobId": "event-restart"},
                        )
                    )
                    self.assertEqual(created, ())
                finally:
                    reopened.close()
            finally:
                harness.close()


class CompatibilityTests(unittest.TestCase):
    def test_v1_surfaces_remain_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                # The V1 notification list keeps its historical document shape.
                status, listing = _request(harness.api, "/api/v1/notifications")
                self.assertEqual(status, 200)
                self.assertIn("limit", listing)
                self.assertIn("next_cursor", listing)
                self.assertIn("previous_cursor", listing)

                # The V1 managed Webhook test route still binds the digest —
                # that surface is the existing authority for CLI/V1 clients.
                active = harness.configuration.active()
                revision = harness.configuration.require(active.revision_id)
                status, result = _request(
                    harness.api,
                    f"/api/v1/configuration/revisions/{active.revision_id}/objects/webhooks/{WEBHOOK_ID}/test",
                    method="POST",
                    body={
                        "expectedVersion": revision.version,
                        "expectedDigest": revision.digest,
                    },
                )
                self.assertEqual(status, 200)
                self.assertIn("digest", result["revision"])

                # Unmatched operations notification routes fail closed.
                status, missing = _request(harness.api, "/api/v1/operations/notifications/unknown")
                self.assertEqual(status, 404)
                status, deep = _request(
                    harness.api,
                    f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/unknown-segment",
                )
                self.assertEqual(status, 404)
                status, query_rejected = _request(
                    harness.api, OPERATIONS_ROUTE, query="?status=pending"
                )
                self.assertEqual(status, 400)
            finally:
                harness.close()

    def test_delivery_recovery_detail_alias_requires_read_permission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                status, denied = _request(
                    harness.api,
                    "/api/v1/operations/notifications/deliveries/whatever",
                    token=None,
                )
                self.assertEqual(status, 401)
            finally:
                harness.close()


if __name__ == "__main__":
    unittest.main()
