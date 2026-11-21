"""V2 Notification operator journey over the real managed API.

These regressions drive the real ``MediaFlowApi`` against a real managed
configuration runtime and the real Webhook/notification services. They prove
the new ``/api/operations/notifications/*`` read projections are bounded
operator documents — no revision digests, no secret values, no delivery bodies,
no signature material — with backend-authoritative actions and Draft state;
that the exact-revision signed test sends exactly one request and never
creates a delivery or mutates configuration; that the Webhook-object-scoped
checked activation publishes only the reviewed Webhook-only change and rejects
sibling and general-configuration changes; that delivery list/detail truthfully
distinguish every durable status and lease state; that recovery is exact,
optimistically fenced, permission-gated and isolated; and that the existing
``/api/notifications`` and configuration surfaces remain untouched for V1
clients.
"""

from __future__ import annotations

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

OPERATIONS_ROUTE = "/api/operations/notifications/webhooks"

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
    # The canonical example stores Webhooks at the root; use the journey's
    # exact identity and deployment-owned secret reference.
    for item in value.get("webhooks", []):
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
        "events": ["task.completed", "task.failed"],
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

    def test_webhook_form(self, document: dict) -> tuple[object, str]:
        """Run one explicit form test against the current Active baseline."""

        active = self.configuration.active()
        webhook_id = str(document.get("id") or WEBHOOK_ID)
        service = self.api._webhook_tests
        original_transport = service._transport
        service._transport = FakeTransport(204)
        try:
            with patch.dict(os.environ, {SECRET_ENV: SECRET_VALUE}):
                status, tested = _request(
                    self.api,
                    f"{OPERATIONS_ROUTE}/{webhook_id}/test",
                    method="POST",
                    body={
                        "webhook": document,
                        "expectedRevisionId": active.revision_id,
                        "expectedVersion": active.version,
                    },
                )
            assert status == 200, tested
            evidence_id = tested.get("testEvidenceId")
            assert isinstance(evidence_id, str) and evidence_id, tested
        finally:
            service._transport = original_transport
        return active, evidence_id

    def open_webhook_draft(self, document: dict | None = None):
        """Publish one Webhook object directly and return the new Active identity.

        The historical helper name is retained by these journey tests; no Draft
        is created. A definition whose id matches the Active definition uses the
        exact-bound edit route (which also migrates a legacy nested spelling to
        the canonical root section); any other id uses the create route.
        """

        stored = document or _webhook_document()
        active, evidence_id = self.test_webhook_form(stored)
        version = active.version
        if stored.get("id") == WEBHOOK_ID:
            route = (
                f"/api/configuration/revisions/{active.revision_id}/objects/webhooks/{WEBHOOK_ID}"
            )
            method = "PUT"
        else:
            route = f"/api/configuration/revisions/{active.revision_id}/objects/webhooks"
            method = "POST"
        status, response = _request(
            self.api,
            route,
            method=method,
            body={
                "object": stored,
                "expectedVersion": version,
                "testEvidenceId": evidence_id,
            },
        )
        assert status == 200, response
        assert response.get("webhook", {}).get("id"), response
        published = self.configuration.active()
        return published.revision_id, published.version

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
            NotificationEventType.TASK_COMPLETED,
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
                self.assertNotIn("draftState", page)
                self.assertEqual(
                    page["supportedEvents"],
                    ["task.completed", "task.failed", "task.cancelled", "schedule.emitted"],
                )
                item = page["items"][0]
                self.assertEqual(
                    item["document"]["id"] if "document" in item else item["id"], WEBHOOK_ID
                )
                self.assertNotIn("definitionState", item)
                self.assertNotIn("draftState", item)
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
                ):
                    action = item["actions"][name]
                    self.assertIn("available", action)
                    self.assertIn("method", action)
                self.assertEqual(
                    item["actions"]["detail"]["path"], f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}"
                )
                self.assertTrue(item["actions"]["edit"]["available"])
                self.assertEqual(
                    item["actions"]["edit"]["path"],
                    f"/api/configuration/revisions/"
                    f"{harness.configuration.active().revision_id}/objects/"
                    f"webhooks/{WEBHOOK_ID}",
                )
                for retired in ("draftCreate", "createDraft", "activate"):
                    self.assertNotIn(retired, item["actions"])
                self.assertNotIn("createDraft", page["actions"])
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
                self.assertFalse(item["actions"]["copy"]["available"])
                self.assertFalse(item["actions"]["test"]["available"])
                for retired in ("draftCreate", "activate"):
                    self.assertNotIn(retired, item["actions"])
                self.assertNotIn("createDraft", page["actions"])
                self.assertTrue(item["actions"]["detail"]["available"])

                status, denied = _request(
                    harness.api, OPERATIONS_ROUTE, method="POST", token=VIEWER_TOKEN
                )
                self.assertEqual(status, 405)
            finally:
                harness.close()

    def test_manager_without_publish_permission_only_reads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                status, page = _request(harness.api, OPERATIONS_ROUTE, token=MANAGER_TOKEN)
                self.assertEqual(status, 200)
                self.assertFalse(page["actions"]["create"]["available"])
                self.assertIn("activate_configuration", page["actions"]["create"]["reason"])
                item = page["items"][0]
                self.assertTrue(item["actions"]["detail"]["available"])
                for name in ("test", "edit", "copy", "enable", "disable"):
                    self.assertFalse(item["actions"][name]["available"], name)
                    self.assertIn("activate_configuration", item["actions"][name]["reason"])

                status, detail = _request(
                    harness.api, f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}", token=MANAGER_TOKEN
                )
                self.assertEqual(status, 200)
                self.assertNotIn("draftState", detail["webhook"])
                self.assertNotIn("definitionState", detail["webhook"])
                self.assertIn("supportedEvents", detail)
                self.assertFalse(detail["webhook"]["actions"]["edit"]["available"])
                self.assertIn(
                    "activate_configuration",
                    detail["webhook"]["actions"]["edit"]["reason"],
                )

                active = harness.configuration.active()
                status, denied = _request(
                    harness.api,
                    f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/test",
                    method="POST",
                    token=MANAGER_TOKEN,
                    body={
                        "expectedRevisionId": active.revision_id,
                        "expectedVersion": active.version,
                    },
                )
                self.assertEqual(status, 403)
                self.assertEqual(len(harness.transport.requests), 0)
            finally:
                harness.close()

    def test_created_definition_is_listed_as_published_active(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                revision_id, _version = harness.open_webhook_draft(
                    _webhook_document(id="copied-webhook", enabled=False)
                )
                status, page = _request(harness.api, OPERATIONS_ROUTE)
                self.assertEqual(status, 200)
                self.assertEqual(page["total"], 2)
                created = next(item for item in page["items"] if item["id"] == "copied-webhook")
                self.assertNotIn("definitionState", created)
                self.assertNotIn("draftState", created)
                self.assertEqual(created["activeConfiguration"]["revisionId"], revision_id)
                # Direct publication leaves no recoverable Draft.
                self.assertNotIn("draftState", page)
                self.assertFalse(
                    any(
                        revision.status.value in {"draft", "validated"}
                        for revision in harness.configuration_repository.list_revisions()
                    )
                )
                _assert_operator_document_clean(page)
            finally:
                harness.close()


class RetiredWebhookEntryTests(unittest.TestCase):
    def test_retired_draft_entries_are_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                active = harness.configuration.active()
                version = active.revision_sequence or active.version
                for path, body in (
                    (f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/draft", {}),
                    (
                        f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/activate-draft",
                        {
                            "expectedRevisionId": active.revision_id,
                            "expectedVersion": version,
                        },
                    ),
                    (
                        f"/api/configuration/revisions/{active.revision_id}/successor",
                        {},
                    ),
                    (
                        f"/api/configuration/revisions/{active.revision_id}/validate",
                        {},
                    ),
                ):
                    status, error = _request(harness.api, path, method="POST", body=body)
                    self.assertEqual(status, 404, (path, error))
                    self.assertEqual(error["error"]["code"], "not_found")
                self.assertEqual(harness.configuration.active().revision_id, active.revision_id)
            finally:
                harness.close()


class WebhookMutationJourneyTests(unittest.TestCase):
    def test_create_edit_enable_disable_and_copy_publish_directly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                active = harness.configuration.active()
                revision_id = active.revision_id
                version = active.version
                route = f"/api/configuration/revisions/{revision_id}/objects/webhooks"

                # The exact-bound edit publishes immediately and migrates a
                # legacy nested spelling to the canonical root section.
                edited_form = _webhook_document(maxAttempts=7)
                _active, evidence_id = harness.test_webhook_form(edited_form)
                status, edited = _request(
                    harness.api,
                    f"{route}/{WEBHOOK_ID}",
                    method="PUT",
                    body={
                        "object": edited_form,
                        "expectedVersion": version,
                        "testEvidenceId": evidence_id,
                    },
                )
                self.assertEqual(status, 200, edited)
                self.assertEqual(edited["webhook"]["maxAttempts"], 7)
                current = harness.configuration.active()
                self.assertNotEqual(current.revision_id, revision_id)
                self.assertEqual(
                    harness.configuration.require(revision_id).status.value, "superseded"
                )
                revision_id = current.revision_id
                version = current.version
                route = f"/api/configuration/revisions/{revision_id}/objects/webhooks"

                # A stale expectedVersion is rejected atomically.
                stale_form = _webhook_document(enabled=False)
                _active, stale_evidence = harness.test_webhook_form(stale_form)
                status, _stale = _request(
                    harness.api,
                    f"{route}/{WEBHOOK_ID}",
                    method="PUT",
                    body={
                        "object": stale_form,
                        "expectedVersion": version - 1,
                        "testEvidenceId": stale_evidence,
                    },
                )
                self.assertEqual(status, 409)
                self.assertEqual(harness.configuration.active().revision_id, revision_id)

                created_form = _webhook_document(id="created-webhook")
                _active, created_evidence = harness.test_webhook_form(created_form)
                status, created = _request(
                    harness.api,
                    route,
                    method="POST",
                    body={
                        "object": created_form,
                        "expectedVersion": version,
                        "testEvidenceId": created_evidence,
                    },
                )
                self.assertEqual(status, 200, created)
                self.assertEqual(created["webhook"]["id"], "created-webhook")
                current = harness.configuration.active()
                revision_id = current.revision_id
                version = current.version
                route = f"/api/configuration/revisions/{revision_id}/objects/webhooks"

                _active, collision_evidence = harness.test_webhook_form(created_form)
                status, _collision = _request(
                    harness.api,
                    route,
                    method="POST",
                    body={
                        "object": created_form,
                        "expectedVersion": version,
                        "testEvidenceId": collision_evidence,
                    },
                )
                self.assertEqual(status, 400)

                for action, expected_flag in (("enable", True), ("disable", False)):
                    current = harness.configuration.active()
                    revision_id = current.revision_id
                    version = current.version
                    status, toggled = _request(
                        harness.api,
                        f"/api/configuration/revisions/{revision_id}/objects/webhooks/"
                        f"{WEBHOOK_ID}/{action}",
                        method="POST",
                        body={"expectedVersion": version},
                    )
                    self.assertEqual(status, 200, toggled)
                    self.assertEqual(toggled["object"]["enabled"], expected_flag)

                current = harness.configuration.active()
                revision_id = current.revision_id
                version = current.version
                status, copied = _request(
                    harness.api,
                    f"/api/configuration/revisions/{revision_id}/objects/webhooks/"
                    f"{WEBHOOK_ID}/copy",
                    method="POST",
                    body={"expectedVersion": version},
                )
                self.assertEqual(status, 200, copied)
                self.assertNotEqual(copied["object"]["id"], WEBHOOK_ID)
                self.assertFalse(copied["object"]["enabled"])
                self.assertFalse(
                    any(
                        revision.status.value in {"draft", "validated"}
                        for revision in harness.configuration_repository.list_revisions()
                    )
                )
            finally:
                harness.close()

    def test_canonical_validator_rejects_hostile_documents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                active = harness.configuration.active()
                revision_id = active.revision_id
                route = f"/api/configuration/revisions/{revision_id}/objects/webhooks"
                valid_form = _webhook_document()
                _active, evidence_id = harness.test_webhook_form(valid_form)
                # The evidence matches this address, so the canonical object
                # validator is the boundary that refuses these structural
                # changes.
                structural = [
                    _webhook_document(unknownField=1),
                    _webhook_document(secret="value"),
                    _webhook_document(events=[]),
                    _webhook_document(events=["task.completed", "task.completed"]),
                    _webhook_document(maxAttempts=0),
                ]
                for value in structural:
                    status, error = _request(
                        harness.api,
                        route,
                        method="POST",
                        body={
                            "object": value,
                            "expectedVersion": active.version,
                            "testEvidenceId": evidence_id,
                        },
                    )
                    self.assertEqual(status, 400, (value, error))
                # Unsafe endpoints never produce successful test evidence and
                # therefore cannot be applied.
                probe_count = len(harness.transport.requests)
                for value in (
                    _webhook_document(url="http://example.invalid/x"),
                    _webhook_document(url="https://user:pw@example.invalid/x"),
                    _webhook_document(url="https://example.invalid/x?token=abc"),
                ):
                    with patch.dict(os.environ, {SECRET_ENV: SECRET_VALUE}):
                        status, tested = _request(
                            harness.api,
                            f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/test",
                            method="POST",
                            body={
                                "webhook": value,
                                "expectedRevisionId": active.revision_id,
                                "expectedVersion": active.version,
                            },
                        )
                    self.assertEqual(status, 200, tested)
                    self.assertEqual(tested["category"], "invalid_definition")
                    self.assertIsNone(tested["testEvidenceId"])
                    status, _rejected = _request(
                        harness.api,
                        route,
                        method="POST",
                        body={
                            "object": value,
                            "expectedVersion": active.version,
                            "testEvidenceId": evidence_id,
                        },
                    )
                    self.assertEqual(status, 400)
                self.assertEqual(len(harness.transport.requests), probe_count)
                self.assertEqual(harness.configuration.active().revision_id, revision_id)
                self.assertFalse(
                    any(
                        revision.status.value in {"draft", "validated"}
                        for revision in harness.configuration_repository.list_revisions()
                    )
                )
            finally:
                harness.close()


class WebhookTestJourneyTests(unittest.TestCase):
    def test_exact_revision_test_sends_one_signed_request_and_no_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                revision_id, version = harness.open_webhook_draft()
                status, retired = _request(harness.api, f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/draft")
                self.assertEqual(status, 404)
                self.assertEqual(retired["error"]["code"], "not_found")

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
                status, deliveries = _request(harness.api, "/api/notifications")
                self.assertEqual(status, 200)
                self.assertEqual(deliveries["items"], [])
                self.assertEqual(
                    harness.configuration.active().revision_id,
                    revision_id,
                )
                self.assertEqual(result["revision"]["status"], "active")
            finally:
                harness.close()

    def test_current_form_test_probes_the_unsaved_values_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                active = harness.configuration.active()
                form = _webhook_document(
                    url="https://example.invalid/hooks/unsaved",
                    maxAttempts=8,
                )
                with patch.dict(os.environ, {SECRET_ENV: SECRET_VALUE}):
                    status, result = _request(
                        harness.api,
                        f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/test",
                        method="POST",
                        body={
                            "webhook": form,
                            "expectedRevisionId": active.revision_id,
                            "expectedVersion": active.version,
                        },
                    )
                self.assertEqual(status, 200, result)
                self.assertEqual(result["outcome"], "success")
                self.assertTrue(result["testEvidenceId"])
                self.assertEqual(result["revision"]["revisionId"], active.revision_id)
                self.assertEqual(len(harness.transport.requests), 1)
                self.assertEqual(
                    harness.transport.requests[0].url,
                    "https://example.invalid/hooks/unsaved",
                )
                # The explicit probe changed neither the Active nor media work.
                self.assertEqual(harness.configuration.active().revision_id, active.revision_id)
                status, deliveries = _request(harness.api, "/api/notifications")
                self.assertEqual(status, 200)
                self.assertEqual(deliveries["items"], [])
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

    def test_superseded_revision_is_rejected_before_any_request(self) -> None:
        """A valid historical revision never tests, even at its exact version."""

        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                first_revision, first_version = harness.open_webhook_draft()
                second_revision, _second_version = harness.open_webhook_draft()
                self.assertNotEqual(first_revision, second_revision)
                self.assertEqual(harness.configuration.active().revision_id, second_revision)

                with patch.dict(os.environ, {SECRET_ENV: SECRET_VALUE}):
                    status, error = _request(
                        harness.api,
                        f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/test",
                        method="POST",
                        body={
                            "expectedRevisionId": first_revision,
                            "expectedVersion": first_version,
                        },
                    )
                self.assertEqual(status, 409)
                self.assertEqual(
                    error["error"]["details"]["durableState"],
                    "no test request was sent",
                )
                self.assertNotIn("digest", json.dumps(error))
                self.assertEqual(len(harness.transport.requests), 0)

                active = harness.configuration.active()
                with patch.dict(os.environ, {SECRET_ENV: SECRET_VALUE}):
                    status, result = _request(
                        harness.api,
                        f"{OPERATIONS_ROUTE}/{WEBHOOK_ID}/test",
                        method="POST",
                        body={
                            "expectedRevisionId": active.revision_id,
                            "expectedVersion": active.version,
                        },
                    )
                self.assertEqual(status, 200)
                _assert_operator_document_clean(result)
                self.assertEqual(result["revision"]["revisionId"], active.revision_id)
                self.assertEqual(len(harness.transport.requests), 1)
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


class WebhookDirectPublicationTests(unittest.TestCase):
    def test_direct_edit_publishes_only_the_reviewed_webhook(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                before = harness.configuration.active()
                tested, evidence_id = harness.test_webhook_form(_webhook_document(maxAttempts=9))
                probes = len(harness.transport.requests)
                status, published = _request(
                    harness.api,
                    f"/api/configuration/revisions/{before.revision_id}/objects/webhooks/{WEBHOOK_ID}",
                    method="PUT",
                    body={
                        "object": _webhook_document(maxAttempts=9),
                        "expectedVersion": before.version,
                        "testEvidenceId": evidence_id,
                    },
                )
                self.assertEqual(status, 200, published)
                self.assertEqual(published["webhook"]["maxAttempts"], 9)
                # Applying the already-tested form never probes again.
                self.assertEqual(len(harness.transport.requests), probes)
                active = harness.configuration.active()
                self.assertNotEqual(active.revision_id, before.revision_id)
                self.assertEqual(
                    harness.configuration.require(before.revision_id).status.value,
                    "superseded",
                )
                section = active.document.get("webhooks")
                if not isinstance(section, list):
                    section = active.document.get("notifications", {}).get("webhooks", [])
                updated = next(item for item in section if item.get("id") == WEBHOOK_ID)
                self.assertEqual(updated["maxAttempts"], 9)
                self.assertFalse(
                    any(
                        revision.status.value in {"draft", "validated"}
                        for revision in harness.configuration_repository.list_revisions()
                    )
                )
            finally:
                harness.close()

    def test_changed_address_after_test_is_refused_without_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                before = harness.configuration.active()
                before_url = harness.active_webhook_definition().url
                tested_address = _webhook_document(url="https://example.invalid/hooks/tested-a")
                _active, evidence_id = harness.test_webhook_form(tested_address)
                audits_before = len(
                    harness.configuration_repository.list_recent_command_audits(
                        ("activate",), limit=50
                    )
                )
                # The exact same test identity cannot publish a different
                # address; the previously published definition stays Active.
                status, rejected = _request(
                    harness.api,
                    f"/api/configuration/revisions/{before.revision_id}/objects/webhooks/{WEBHOOK_ID}",
                    method="PUT",
                    body={
                        "object": _webhook_document(url="https://example.invalid/hooks/tested-b"),
                        "expectedVersion": before.version,
                        "testEvidenceId": evidence_id,
                        "submissionId": "webhook-address-change",
                    },
                )
                self.assertEqual(status, 409, rejected)
                self.assertEqual(harness.configuration.active().revision_id, before.revision_id)
                self.assertEqual(
                    len(
                        harness.configuration_repository.list_recent_command_audits(
                            ("activate",), limit=50
                        )
                    ),
                    audits_before,
                )
                self.assertEqual(harness.active_webhook_definition().url, before_url)

                # A probe of the new address succeeds, then that exact form
                # publishes one new Active configuration.
                tested_address = _webhook_document(url="https://example.invalid/hooks/tested-b")
                _active, evidence_id = harness.test_webhook_form(tested_address)
                status, published = _request(
                    harness.api,
                    f"/api/configuration/revisions/{before.revision_id}/objects/webhooks/{WEBHOOK_ID}",
                    method="PUT",
                    body={
                        "object": tested_address,
                        "expectedVersion": before.version,
                        "testEvidenceId": evidence_id,
                    },
                )
                self.assertEqual(status, 200, published)
                current = harness.configuration.active()
                self.assertNotEqual(current.revision_id, before.revision_id)
                self.assertEqual(
                    harness.active_webhook_definition().url,
                    "https://example.invalid/hooks/tested-b",
                )
            finally:
                harness.close()

    def test_apply_without_successful_test_evidence_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                before = harness.configuration.active()
                status, rejected = _request(
                    harness.api,
                    f"/api/configuration/revisions/{before.revision_id}/objects/webhooks/{WEBHOOK_ID}",
                    method="PUT",
                    body={
                        "object": _webhook_document(maxAttempts=4),
                        "expectedVersion": before.version,
                    },
                )
                self.assertEqual(status, 409, rejected)
                self.assertEqual(harness.configuration.active().revision_id, before.revision_id)
            finally:
                harness.close()

    def test_stale_identity_and_version_are_rejected_without_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                first, evidence_id = harness.test_webhook_form(_webhook_document(maxAttempts=4))
                status, published = _request(
                    harness.api,
                    f"/api/configuration/revisions/{first.revision_id}/objects/webhooks/{WEBHOOK_ID}",
                    method="PUT",
                    body={
                        "object": _webhook_document(maxAttempts=4),
                        "expectedVersion": first.version,
                        "testEvidenceId": evidence_id,
                    },
                )
                self.assertEqual(status, 200, published)
                second = harness.configuration.active()
                # The old Active identity cannot publish again.
                status, stale = _request(
                    harness.api,
                    f"/api/configuration/revisions/{first.revision_id}/objects/webhooks/{WEBHOOK_ID}",
                    method="PUT",
                    body={
                        "object": _webhook_document(maxAttempts=6),
                        "expectedVersion": first.version,
                        "testEvidenceId": evidence_id,
                    },
                )
                self.assertEqual(status, 409, stale)
                self.assertEqual(harness.configuration.active().revision_id, second.revision_id)
                # The current identity with a stale version is also refused.
                _current, fresh_evidence = harness.test_webhook_form(
                    _webhook_document(maxAttempts=6)
                )
                status, stale_version = _request(
                    harness.api,
                    f"/api/configuration/revisions/{second.revision_id}/objects/webhooks/{WEBHOOK_ID}",
                    method="PUT",
                    body={
                        "object": _webhook_document(maxAttempts=6),
                        "expectedVersion": first.version,
                        "testEvidenceId": fresh_evidence,
                    },
                )
                self.assertEqual(status, 409, stale_version)
                self.assertEqual(harness.configuration.active().revision_id, second.revision_id)
            finally:
                harness.close()

    def test_direct_publication_requires_manage_and_activate_permission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                before = harness.configuration.active()
                _active, evidence_id = harness.test_webhook_form(_webhook_document(maxAttempts=9))
                for token in (MANAGER_TOKEN, ACTIVATOR_TOKEN, VIEWER_TOKEN):
                    status, denied = _request(
                        harness.api,
                        f"/api/configuration/revisions/{before.revision_id}/objects/webhooks/{WEBHOOK_ID}",
                        method="PUT",
                        body={
                            "object": _webhook_document(maxAttempts=9),
                            "expectedVersion": before.version,
                            "testEvidenceId": evidence_id,
                        },
                        token=token,
                    )
                    self.assertEqual(status, 403, token)
                self.assertEqual(harness.configuration.active().revision_id, before.revision_id)
            finally:
                harness.close()

    def test_submission_identity_reconciles_publish_and_not_committed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                before = harness.configuration.active()
                form = _webhook_document(maxAttempts=6)
                _active, evidence_id = harness.test_webhook_form(form)
                status, published = _request(
                    harness.api,
                    f"/api/configuration/revisions/{before.revision_id}/objects/webhooks/{WEBHOOK_ID}",
                    method="PUT",
                    body={
                        "object": form,
                        "expectedVersion": before.version,
                        "testEvidenceId": evidence_id,
                        "submissionId": "webhook-committed-submission",
                    },
                )
                self.assertEqual(status, 200, published)
                committed = harness.configuration.active()
                status, reconciled = _request(
                    harness.api,
                    "/api/system/settings/reconcile",
                    query="submissionId=webhook-committed-submission",
                )
                self.assertEqual(status, 200, reconciled)
                self.assertEqual(reconciled["state"], "COMMITTED")
                self.assertTrue(reconciled["committed"])
                self.assertEqual(reconciled["committedRevisionId"], committed.revision_id)
                self.assertEqual(reconciled["sideEffects"], "none")

                # A later publication makes this exact request SUPERSEDED,
                # while the same request still never publishes again.
                _active, evidence_id = harness.test_webhook_form(_webhook_document(maxAttempts=8))
                status, later = _request(
                    harness.api,
                    f"/api/configuration/revisions/{committed.revision_id}/objects/webhooks/{WEBHOOK_ID}",
                    method="PUT",
                    body={
                        "object": _webhook_document(maxAttempts=8),
                        "expectedVersion": committed.version,
                        "testEvidenceId": evidence_id,
                    },
                )
                self.assertEqual(status, 200, later)
                status, superseded = _request(
                    harness.api,
                    "/api/system/settings/reconcile",
                    query="submissionId=webhook-committed-submission",
                )
                self.assertEqual(status, 200, superseded)
                self.assertEqual(superseded["state"], "SUPERSEDED")
                self.assertEqual(harness.configuration.active().revision_id, later["revisionId"])

                # A refused submission with the same identity reports its
                # terminal not-committed evidence without changing the Active.
                status, refused = _request(
                    harness.api,
                    f"/api/configuration/revisions/{later['revisionId']}/objects/webhooks/{WEBHOOK_ID}",
                    method="PUT",
                    body={
                        "object": _webhook_document(maxAttempts=9),
                        "expectedVersion": later["version"],
                        "submissionId": "webhook-not-committed-submission",
                    },
                )
                self.assertEqual(status, 409, refused)
                status, not_committed = _request(
                    harness.api,
                    "/api/system/settings/reconcile",
                    query="submissionId=webhook-not-committed-submission",
                )
                self.assertEqual(status, 200, not_committed)
                self.assertEqual(not_committed["state"], "NOT_COMMITTED")
                self.assertFalse(not_committed["committed"])
                self.assertEqual(harness.configuration.active().revision_id, later["revisionId"])
            finally:
                harness.close()


class DeliveryProjectionTests(unittest.TestCase):
    def prepare_enabled_webhook(self, harness: NotificationHarness) -> None:
        harness.open_webhook_draft()

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
                    "/api/notifications",
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
                    "/api/notifications",
                    query="status=dead-letter",
                )
                self.assertEqual(status, 200)
                self.assertEqual(
                    [item["deliveryId"] for item in filtered["items"]],
                    [dead.delivery_id],
                )
                status, rejected = _request(
                    harness.api,
                    "/api/notifications",
                    query="status=not-a-status",
                )
                self.assertEqual(status, 400)

                # Detail: bounded document, correct lease and recovery evidence.
                status, dead_detail = _request(
                    harness.api,
                    f"/api/operations/notifications/deliveries/{dead.delivery_id}",
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
                    f"/api/operations/notifications/deliveries/{dead.delivery_id}",
                    token=VIEWER_TOKEN,
                )
                self.assertEqual(status, 200)
                self.assertFalse(viewer_detail["actions"]["requeue"]["available"])
                self.assertIn("permission", viewer_detail["actions"]["requeue"]["reason"])

                status, delivering_detail = _request(
                    harness.api,
                    f"/api/operations/notifications/deliveries/{delivering.delivery_id}",
                )
                self.assertEqual(status, 200)
                self.assertEqual(delivering_detail["lease"]["state"], "active")
                self.assertEqual(delivering_detail["recovery"]["availableActions"], [])

                status, pending_detail = _request(
                    harness.api,
                    f"/api/operations/notifications/deliveries/{pending.delivery_id}",
                )
                self.assertEqual(status, 200)
                self.assertEqual(pending_detail["lease"], {"state": "not_leased"})
                self.assertEqual(pending_detail["recovery"]["availableActions"], [])

                status, missing = _request(
                    harness.api,
                    "/api/operations/notifications/deliveries/absent-delivery",
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
                    f"/api/operations/notifications/deliveries/{delivery.delivery_id}",
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
                    "/api/notifications",
                    query="limit=2",
                )
                self.assertEqual(status, 200)
                self.assertEqual(len(first["items"]), 2)
                self.assertIsNotNone(first["next_cursor"])
                self.assertIsNone(first["previous_cursor"])
                status, second = _request(
                    harness.api,
                    "/api/notifications",
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
        harness.open_webhook_draft()

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
                    f"/api/operations/notifications/deliveries/{dead.delivery_id}",
                    token=ADMIN_TOKEN,
                )
                fence = {
                    "expectedStatus": detail["status"],
                    "expectedUpdatedAt": detail["updatedAt"],
                }
                active_before = harness.configuration.active().revision_id
                status, result = _request(
                    harness.api,
                    f"/api/notifications/{dead.delivery_id}/requeue",
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
                status, listing = _request(harness.api, "/api/notifications", query="limit=50")
                self.assertEqual(len(listing["items"]), 2)
                self.assertEqual(harness.configuration.active().revision_id, active_before)
                status, sibling_detail = _request(
                    harness.api,
                    f"/api/operations/notifications/deliveries/{sibling.delivery_id}",
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
                    f"/api/operations/notifications/deliveries/{dead.delivery_id}",
                )
                fence = {
                    "expectedStatus": detail["status"],
                    "expectedUpdatedAt": detail["updatedAt"],
                }
                status, _first = _request(
                    harness.api,
                    f"/api/notifications/{dead.delivery_id}/requeue",
                    method="POST",
                    body=fence,
                )
                self.assertEqual(status, 200)
                # A repeated submission is stale: the state already moved.
                status, second = _request(
                    harness.api,
                    f"/api/notifications/{dead.delivery_id}/requeue",
                    method="POST",
                    body=fence,
                )
                self.assertEqual(status, 409)

                # A wrong fence never mutates.
                status, wrong = _request(
                    harness.api,
                    f"/api/notifications/{dead.delivery_id}/requeue",
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
                    f"/api/operations/notifications/deliveries/{dead.delivery_id}",
                )
                status, wrong_action = _request(
                    harness.api,
                    f"/api/notifications/{dead.delivery_id}/resolve-stale",
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
                    f"/api/notifications/{dead.delivery_id}/requeue",
                    method="POST",
                    body={"expectedStatus": "dead-letter"},
                )
                self.assertEqual(status, 400)

                # The delivery is still exactly once requeued: pending.
                status, final = _request(
                    harness.api,
                    f"/api/operations/notifications/deliveries/{dead.delivery_id}",
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
                    f"/api/operations/notifications/deliveries/{delivery.delivery_id}",
                )
                self.assertEqual(detail["lease"]["state"], "active")
                status, rejected = _request(
                    harness.api,
                    f"/api/notifications/{delivery.delivery_id}/resolve-stale",
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
                    f"/api/operations/notifications/deliveries/{dead.delivery_id}",
                )
                fence = {
                    "expectedStatus": detail["status"],
                    "expectedUpdatedAt": detail["updatedAt"],
                }
                status, denied = _request(
                    harness.api,
                    f"/api/notifications/{dead.delivery_id}/requeue",
                    method="POST",
                    body=fence,
                    token=VIEWER_TOKEN,
                )
                self.assertEqual(status, 403)
                status, still = _request(
                    harness.api,
                    f"/api/operations/notifications/deliveries/{dead.delivery_id}",
                )
                self.assertEqual(still["status"], "dead-letter")
            finally:
                harness.close()


class DeliveryEvidenceTests(unittest.TestCase):
    def test_dead_letter_failure_is_carried_by_the_existing_delivery_reads(self) -> None:
        """Slice 51 Task 51.2: the retired Dashboard aggregation is gone, so the
        dead-letter failure evidence must come from the supported notification
        list/detail reads, keeping the exact delivery identity linkable."""

        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                harness.open_webhook_draft()
                dead = harness.publish_delivery("event-delivery-evidence")
                harness.run_worker(transport=FakeTransport(400), attempts=1)

                # The supported detail read carries the exact dead delivery.
                status, detail = _request(
                    harness.api,
                    f"/api/operations/notifications/deliveries/{dead.delivery_id}",
                )
                self.assertEqual(status, 200)
                self.assertEqual(detail["status"], "dead-letter")
                _assert_operator_document_clean(detail)

                # The supported list read surfaces exactly this dead letter.
                status, listing = _request(
                    harness.api,
                    "/api/notifications",
                    query="limit=50&status=dead-letter",
                )
                self.assertEqual(status, 200)
                identifiers = [item["deliveryId"] for item in listing["items"]]
                self.assertEqual(identifiers, [dead.delivery_id])

                # The identifier is one bounded URI-safe segment: safe to link
                # through the detail route, which stays bounded for unknown ids.
                self.assertNotIn("/", dead.delivery_id)
                self.assertNotIn("\\", dead.delivery_id)
                status, missing = _request(
                    harness.api,
                    "/api/operations/notifications/deliveries/unknown-delivery",
                )
                self.assertEqual(status, 404, missing)
            finally:
                harness.close()


class RestartPersistenceTests(unittest.TestCase):
    def test_delivery_state_survives_a_repository_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            harness = NotificationHarness(directory)
            try:
                harness.open_webhook_draft()
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
                            NotificationEventType.TASK_COMPLETED,
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
                status, listing = _request(harness.api, "/api/notifications")
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
                    f"/api/configuration/revisions/{active.revision_id}/objects/webhooks/{WEBHOOK_ID}/test",
                    method="POST",
                    body={
                        "expectedVersion": revision.version,
                        "expectedDigest": revision.digest,
                    },
                )
                self.assertEqual(status, 200)
                self.assertIn("digest", result["revision"])

                # Unmatched operations notification routes fail closed.
                status, missing = _request(harness.api, "/api/operations/notifications/unknown")
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
                    "/api/operations/notifications/deliveries/whatever",
                    token=None,
                )
                self.assertEqual(status, 401)
            finally:
                harness.close()


if __name__ == "__main__":
    unittest.main()
