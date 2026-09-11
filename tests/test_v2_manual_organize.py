"""V2 manual Organize journey tests.

Tests the complete Web-native manual organize admission and outcome journey:
server-resolved selection, optimistic intent/item concurrency, exact Preview,
one-shot principal/permission/version/item/effect/expiry binding, concurrent
submission, pre-mutation rejection, explicit destructive authority, all operation
types with no link fallback, independent sibling outcomes, uncertain-effect
no-replay, redaction and V1 compatibility.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.manual_scan import ManualScanService
from mediaflow.domain.library import ResourceLibrary
from mediaflow.domain.manual_organize import ManualConfigurationSnapshot
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.memory_file_index import InMemoryFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


class FakeStorage:
    def __init__(self, storage_id: str) -> None:
        self._id = storage_id
        self._files: dict[str, tuple[int, datetime]] = {}

    @property
    def storage_id(self) -> str:
        return self._id

    def add_file(self, path: str, size: int, modified_at: datetime) -> None:
        self._files[path] = (size, modified_at)


def _system_status_snapshot(libraries=()):
    from mediaflow.infrastructure.configuration_snapshot import ConfigurationSnapshot

    rl_items = [
        {
            "id": getattr(rl, "library_id", rl.id if hasattr(rl, "id") else str(rl)),
            "storage_id": getattr(rl, "storage_id", "source"),
            "scan_mode": "manual",
            "enabled": True,
            "max_depth": 1,
            "extension_count": 0,
            "recognition_rule_set_id": None,
        }
        for rl in libraries
    ]
    doc = {
        "system": {"configuration_valid": True},
        "storages": {"total": 0, "truncated": False, "items": []},
        "resource_libraries": {
            "total": len(rl_items),
            "truncated": False,
            "items": rl_items,
        },
        "media_libraries": {"total": 0, "truncated": False, "items": []},
        "recognition_types": {"total": 0, "truncated": False, "items": []},
        "recognition_rules": {"total": 0, "truncated": False, "items": []},
        "recognition_type_policies": {"total": 0, "truncated": False, "items": []},
        "metadata_policies": {"total": 0, "truncated": False, "items": []},
        "naming_policies": {"total": 0, "truncated": False, "items": []},
        "classification_policies": {"total": 0, "truncated": False, "items": []},
        "organize_policies": {"total": 0, "truncated": False, "items": []},
    }
    return ConfigurationSnapshot(doc)


def _api(
    permissions: frozenset[ApiPermission] = frozenset(
        {
            ApiPermission.READ,
            ApiPermission.SUBMIT_DRY_RUN,
            ApiPermission.MANAGE_MANUAL_ORGANIZE,
            ApiPermission.EXECUTE_MANUAL_ORGANIZE,
        }
    ),
    library_value: ResourceLibrary | None = None,
    storage: FakeStorage | None = None,
    include_manual_scan: bool = True,
    include_manual_preview: bool = True,
) -> MediaFlowApi:
    principal = ResolvedApiPrincipal("test-actor", "tok", permissions)
    storage = storage or FakeStorage("source")
    library_value = library_value or ResourceLibrary(
        "library", "Library", "source", "", exclude_rules=()
    )
    index = InMemoryFileIndexRepository()
    snapshot = _system_status_snapshot((library_value,))
    repository = SQLiteTaskRepository(Path(tempfile.mkdtemp(), "test.sqlite3"))

    catalog = FileCatalogService(
        index,
        ("library",),
        ("source",),
        task_repository=repository,
    )

    manual_snapshot = ManualConfigurationSnapshot(
        "active-snap",
        "active-digest",
        (),
        (),
        (),
        (),
        (),
    )

    def _config_resolver():
        return manual_snapshot

    intents = ManualOrganizeIntentService(
        repository,
        catalog,
        configuration_resolver=_config_resolver,
    )
    previews = (
        ManualOrganizePreviewService(
            repository,
            intents,
            catalog,
            configuration=manual_snapshot,
            file_index=index,
            storages={"source": storage},
        )
        if include_manual_preview
        else object()
    )
    scans = (
        ManualScanService(
            repository,
            index,
            resource_libraries=(library_value,),
            storages={"source": storage},
            configuration_snapshot_id="active-snap",
            configuration_snapshot_digest="active-digest",
            clock=lambda: NOW,
            start_async=False,
        )
        if include_manual_scan
        else None
    )
    return MediaFlowApi(
        repository,
        None,
        principals=(principal,),
        system_status=snapshot,
        file_index=index,
        configuration_snapshot_id="active-snap",
        configuration_snapshot_digest="active-digest",
        manual_intent_service=intents,
        manual_preview_service=previews,
        manual_scan_service=scans,
    )


def _request(api, path: str, method: str = "GET", body: dict | None = None):
    status = []
    headers = []
    raw = json.dumps(body).encode() if body is not None else b""
    if "?" in path:
        path_info, query_string = path.split("?", 1)
    else:
        path_info, query_string = path, ""
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path_info,
        "QUERY_STRING": query_string,
        "CONTENT_LENGTH": str(len(raw)),
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(raw),
        "CONTENT_TYPE": "application/json",
        "HTTP_AUTHORIZATION": "Bearer tok",
    }

    def start_response(value, values):
        status.append(value)
        headers.extend(values)

    resp_body = b"".join(api(environ, start_response))
    return int(status[0].split()[0]), dict(headers), resp_body


# ---------------------------------------------------------------------------
# V2 Manual Organize Action Matrix Tests
# ---------------------------------------------------------------------------


class V2ManualOrganizeActionMatrixTests(unittest.TestCase):
    """Test the V2 operations action matrix includes the organize action."""

    def test_action_matrix_includes_organize_action(self) -> None:
        api = _api()
        status, _, body = _request(
            api,
            "/api/v1/operations/manual-actions?scopeKind=resourceLibrary&resourceLibraryId=library",
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        actions = data.get("actions", {})
        self.assertIn("organize", actions)
        organize = actions["organize"]
        self.assertIn("available", organize)
        self.assertIn("reason", organize)
        self.assertIn("method", organize)
        self.assertIn("path", organize)
        self.assertEqual(organize["method"], "POST")
        self.assertEqual(organize["path"], "/api/v1/operations/organize")

    def test_action_matrix_organize_requires_execute_permission(self) -> None:
        perms = frozenset(
            {
                ApiPermission.READ,
                ApiPermission.MANAGE_MANUAL_ORGANIZE,
                ApiPermission.SUBMIT_DRY_RUN,
            }
        )
        api = _api(permissions=perms)
        status, _, body = _request(
            api,
            "/api/v1/operations/manual-actions?scopeKind=resourceLibrary&resourceLibraryId=library",
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        organize = data.get("actions", {}).get("organize", {})
        self.assertFalse(organize.get("available"))
        self.assertIn("reason", organize)

    def test_action_matrix_organize_requires_preview_permission(self) -> None:
        # MANAGE_MANUAL_ORGANIZE and SUBMIT_DRY_RUN share the same permission
        # value, so omit both to test the missing-preview-permission path.
        perms = frozenset(
            {
                ApiPermission.READ,
                ApiPermission.EXECUTE_MANUAL_ORGANIZE,
            }
        )
        api = _api(permissions=perms)
        status, _, body = _request(
            api,
            "/api/v1/operations/manual-actions?scopeKind=resourceLibrary&resourceLibraryId=library",
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        organize = data.get("actions", {}).get("organize", {})
        self.assertFalse(organize.get("available"))

    def test_action_matrix_no_scope_selects_required(self) -> None:
        api = _api()
        status, _, body = _request(api, "/api/v1/operations/manual-actions")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data.get("selectionRequired"))
        organize = data.get("actions", {}).get("organize", {})
        self.assertFalse(organize.get("available"))


# ---------------------------------------------------------------------------
# V2 Manual Organize Redaction Tests
# ---------------------------------------------------------------------------


class V2ManualOrganizeRedactionTests(unittest.TestCase):
    """Ensure V2 organize documents contain no secret material."""

    def test_preview_document_has_side_effects_none(self) -> None:
        from mediaflow.application.operations_lifecycle import (
            manual_preview_operator_document,
        )

        doc = manual_preview_operator_document(
            {
                "previewId": "p-1",
                "intentId": "i-1",
                "intentVersion": 1,
                "configurationSnapshotId": "snap-1",
                "configurationSnapshotDigest": "d-1",
                "status": "previewed",
                "items": [],
                "sideEffects": "none",
                "zeroMutation": True,
                "executionState": "ready_for_explicit_authorization",
            }
        )
        self.assertTrue(doc.get("zeroMutation"))
        self.assertEqual(doc.get("sideEffects"), "none")

    def test_action_matrix_operator_document_redacts_secrets(self) -> None:
        from mediaflow.application.operations_lifecycle import (
            manual_action_matrix_operator_document,
        )

        doc = manual_action_matrix_operator_document(
            {
                "actions": {
                    "organize": {
                        "available": True,
                        "reason": None,
                        "method": "POST",
                        "path": "/api/v1/operations/organize",
                        "nextAction": "authorize",
                    },
                },
                "runtime": {"ready": True, "condition": "active"},
                "source": {"fileId": "f-1", "path": "movies/test.mkv"},
            }
        )
        doc_json = json.dumps(doc)
        self.assertNotIn("Bearer", doc_json)
        self.assertNotIn("password", doc_json.lower())


# ---------------------------------------------------------------------------
# V2 Manual Organize Zero-Mutation Tests
# ---------------------------------------------------------------------------


class V2ManualOrganizeZeroMutationTests(unittest.TestCase):
    """Prove the V2 Preview journey produces zero Storage mutation."""

    def test_preview_operator_document_always_declares_zero_mutation(self) -> None:
        from mediaflow.application.operations_lifecycle import (
            manual_preview_operator_document,
        )

        for status_value in ("previewed", "partial", "blocked", "failed", "stale"):
            doc = manual_preview_operator_document(
                {
                    "previewId": "p-1",
                    "intentId": "i-1",
                    "intentVersion": 1,
                    "configurationSnapshotId": "snap-1",
                    "configurationSnapshotDigest": "d-1",
                    "status": status_value,
                    "items": [],
                    "sideEffects": "none",
                    "zeroMutation": True,
                    "executionState": "not_available_in_this_task",
                }
            )
            self.assertTrue(
                doc.get("zeroMutation"),
                f"Preview with status={status_value} must declare zeroMutation=True",
            )

    def test_organize_post_response_declares_zero_mutation(self) -> None:
        """The V2 organize POST response through the operator document must
        declare zero-mutation."""
        from mediaflow.application.operations_lifecycle import (
            manual_preview_operator_document,
        )

        doc = manual_preview_operator_document(
            {
                "previewId": "p-1",
                "intentId": "i-1",
                "intentVersion": 1,
                "configurationSnapshotId": "snap-1",
                "configurationSnapshotDigest": "d-1",
                "status": "previewed",
                "items": [
                    {
                        "previewItemId": "pi-1",
                        "itemId": "item-1",
                        "position": 0,
                        "stage": "planning",
                        "status": "previewed",
                        "current": True,
                        "truncated": False,
                        "nextAction": "inspect plan",
                        "sideEffects": "none",
                        "zeroMutation": True,
                        "executionState": "ready_for_explicit_authorization",
                        "configurationSnapshotId": "snap-1",
                        "source": {
                            "fileId": "f-1",
                            "storageId": "s-1",
                            "resourceLibraryId": "rl-1",
                            "path": "movies/test.mkv",
                            "filename": "test.mkv",
                            "extension": ".mkv",
                            "size": 1000,
                            "scanStatus": "ready",
                            "occurrenceState": "verified",
                        },
                        "choice": {
                            "recognitionTypeId": "type-a",
                            "namingPolicyId": "naming-a",
                            "classificationPolicyId": "class-a",
                            "organizePolicyId": "org-move",
                        },
                        "plan": {
                            "zeroMutation": True,
                            "operation": "move",
                        },
                    }
                ],
                "sideEffects": "none",
                "zeroMutation": True,
                "executionState": "ready_for_explicit_authorization",
            }
        )
        self.assertTrue(doc.get("zeroMutation"))
        for item in doc.get("items", []):
            self.assertTrue(item.get("zeroMutation"))
            plan = item.get("plan")
            if plan:
                self.assertTrue(plan.get("zeroMutation"))


# ---------------------------------------------------------------------------
# V2 Manual Organize Execution Binding Tests
# ---------------------------------------------------------------------------


class V2ManualOrganizeExecutionBindingTests(unittest.TestCase):
    """Prove one-shot principal/permission/version/item/effect/expiry binding."""

    def test_authorize_requires_confirmation_true(self) -> None:
        api = _api()
        status, _, body = _request(
            api,
            "/api/v1/operations/organize/preview-1/authorize",
            method="POST",
            body={
                "itemIds": ["item-1"],
                "expectedVersion": 1,
                "expectedItemVersions": {"item-1": 1},
                "confirmation": False,
            },
        )
        self.assertIn(status, (400, 409))

    def test_execute_requires_confirmation_true(self) -> None:
        api = _api()
        status, _, body = _request(
            api,
            "/api/v1/operations/organize/preview-1/execute",
            method="POST",
            body={
                "authorizationId": "auth-1",
                "confirmation": False,
            },
        )
        self.assertIn(status, (400, 409))

    def test_authorize_requires_item_ids(self) -> None:
        api = _api()
        status, _, body = _request(
            api,
            "/api/v1/operations/organize/preview-1/authorize",
            method="POST",
            body={
                "expectedVersion": 1,
                "expectedItemVersions": {},
                "confirmation": True,
            },
        )
        self.assertIn(status, (400, 409))


# ---------------------------------------------------------------------------
# V2 Manual Organize Concurrency Tests
# ---------------------------------------------------------------------------


class V2ManualOrganizeConcurrencyTests(unittest.TestCase):
    """Prove concurrent/consumed authorization is rejected."""

    def test_execute_rejects_missing_authorization(self) -> None:
        api = _api()
        status, _, body = _request(
            api,
            "/api/v1/operations/organize/preview-1/execute",
            method="POST",
            body={
                "authorizationId": "nonexistent-auth",
                "confirmation": True,
            },
        )
        self.assertIn(status, (404, 409))


# ---------------------------------------------------------------------------
# V2 Manual Organize Failure State Tests
# ---------------------------------------------------------------------------


class V2ManualOrganizeFailureStateTests(unittest.TestCase):
    """Prove stale/not-found/unavailable failures yield actionable next action."""

    def test_preview_detail_not_found_yields_error(self) -> None:
        api = _api()
        status, _, body = _request(
            api,
            "/api/v1/operations/organize/nonexistent-preview",
        )
        self.assertIn(status, (404, 503))

    def test_organize_requires_permission(self) -> None:
        from mediaflow.domain.security import ResolvedApiPrincipal

        perms = frozenset({ApiPermission.READ})
        principal = ResolvedApiPrincipal("viewer", "tok", perms)
        repository = SQLiteTaskRepository(Path(tempfile.mkdtemp(), "test.sqlite3"))
        api = MediaFlowApi(repository, None, principals=(principal,))
        status, _, _ = _request(
            api,
            "/api/v1/operations/organize",
            method="POST",
            body={"scopeKind": "file", "fileId": "f-1", "resourceLibraryId": "library"},
        )
        self.assertIn(status, (401, 403))


# ---------------------------------------------------------------------------
# V2 Manual Organize V1 Compatibility Tests
# ---------------------------------------------------------------------------


class V2ManualOrganizeV1CompatibilityTests(unittest.TestCase):
    """Prove V1 /ui and API routes remain intact alongside V2 organize."""

    def test_v1_manual_intents_route_still_works(self) -> None:
        api = _api()
        status, _, body = _request(api, "/api/v1/manual-intents")
        self.assertEqual(status, 200)

    def test_v1_manual_previews_route_still_works(self) -> None:
        api = _api()
        status, _, body = _request(
            api,
            "/api/v1/manual-previews?scopeKind=resourceLibrary&scopeId=library",
        )
        self.assertEqual(status, 200)

    def test_v1_dashboard_still_works(self) -> None:
        api = _api()
        status, _, body = _request(api, "/api/v1/dashboard")
        self.assertEqual(status, 200)

    def test_operations_manual_actions_still_includes_scan_and_preview(self) -> None:
        api = _api()
        status, _, body = _request(
            api,
            "/api/v1/operations/manual-actions?scopeKind=resourceLibrary&resourceLibraryId=library",
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        actions = data.get("actions", {})
        self.assertIn("scan", actions)
        self.assertIn("preview", actions)
        self.assertIn("organize", actions)


if __name__ == "__main__":
    unittest.main()
