"""Tests for the V2 bounded Preview API surface.

Covers:
- Server-bound Preview admission (no fingerprint echo)
- Bounded Preview operator documents
- Preview zero-mutation invariant
- Error/failure states are truthfully projected
- The retired action matrix route is an ordinary not-found route
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mediaflow.domain.library import ResourceLibrary
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.configuration_snapshot import ConfigurationSnapshot
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_scanner import FakeStorage

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)


def _system_status_snapshot(
    resource_libraries: tuple[ResourceLibrary, ...] = (),
) -> ConfigurationSnapshot:
    doc = {
        "system": {"configuration_valid": True},
        "storages": {"total": 0, "truncated": False, "items": []},
        "resource_libraries": {
            "total": len(resource_libraries),
            "truncated": False,
            "items": [
                {
                    "id": rl.library_id,
                    "storage_id": rl.storage_id,
                    "enabled": rl.enabled,
                    "scan_mode": rl.scan_mode.value if hasattr(rl, "scan_mode") else "full",
                    "max_depth": getattr(rl, "max_depth", 1),
                    "extension_count": 0,
                    "recognition_rule_set_id": getattr(rl, "recognition_rule_set_id", None),
                }
                for rl in resource_libraries
            ],
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


def _get(api, path: str, *, token: str = "test-token"):
    statuses: list[str] = []
    if "?" in path:
        path_info, query_string = path.split("?", 1)
    else:
        path_info, query_string = path, ""
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path_info,
        "QUERY_STRING": query_string,
        "CONTENT_LENGTH": "0",
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
        "wsgi.input": io.BytesIO(b""),
    }
    payload = b"".join(api(environ, lambda status, _headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(payload)


def _post(api, path: str, body=None, *, token: str = "test-token"):
    raw = json.dumps(body).encode("utf-8") if body is not None else b""
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": str(len(raw)),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
        "wsgi.input": io.BytesIO(raw),
    }
    payload = b"".join(api(environ, lambda status, _headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(payload)


def _api(
    *,
    permissions: frozenset[ApiPermission] = frozenset(
        {ApiPermission.READ, ApiPermission.SUBMIT_DRY_RUN, ApiPermission.MANAGE_MANUAL_ORGANIZE}
    ),
    library_value: ResourceLibrary | None = None,
    storage: FakeStorage | None = None,
) -> MediaFlowApi:
    from mediaflow.application.manual_organize import ManualOrganizeIntentService
    from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
    from mediaflow.domain.manual_organize import ManualConfigurationSnapshot

    principal = ResolvedApiPrincipal("test-operator", "test-token", permissions)
    storage = storage or FakeStorage("source")
    library_value = library_value or ResourceLibrary(
        "library", "Library", "source", "", exclude_rules=()
    )
    snapshot = _system_status_snapshot((library_value,))
    repository = SQLiteTaskRepository(Path(tempfile.mkdtemp(), "test.sqlite3"))

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
        configuration_resolver=_config_resolver,
    )
    previews = ManualOrganizePreviewService(
        repository,
        intents,
        configuration=manual_snapshot,
        storages={"source": storage},
    )
    return MediaFlowApi(
        repository,
        principals=(principal,),
        system_status=snapshot,
        configuration_snapshot_id="active-snap",
        configuration_snapshot_digest="active-digest",
        manual_intent_service=intents,
        manual_preview_service=previews,
    )


class BoundedDocumentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = FakeStorage("source")
        self.storage.add_file("current.mkv", 10, NOW - timedelta(hours=2))
        self.library_value = ResourceLibrary("library", "Library", "source", "", exclude_rules=())

    def test_preview_operator_document_strips_fingerprint(self) -> None:
        from mediaflow.application.operations_lifecycle import manual_preview_operator_document

        raw = {
            "previewId": "p1",
            "intentId": "i1",
            "actor": "test",
            "intentVersion": 1,
            "configurationSnapshotId": "snap1",
            "configurationSnapshotDigest": "d" * 64,
            "status": "previewed",
            "current": True,
            "createdAt": "2026-09-04T12:00:00Z",
            "updatedAt": "2026-09-04T12:00:00Z",
            "nextAction": "inspect items",
            "error": None,
            "sideEffects": "none",
            "zeroMutation": True,
            "executionState": "ready_for_explicit_authorization",
            "truncated": False,
            "scope": {"kind": "file", "id": "f1", "itemCount": 1},
            "items": [
                {
                    "previewItemId": "pi1",
                    "previewId": "p1",
                    "itemId": "it1",
                    "position": 0,
                    "stage": "planning",
                    "status": "previewed",
                    "createdAt": "2026-09-04T12:00:00Z",
                    "updatedAt": "2026-09-04T12:00:00Z",
                    "current": True,
                    "truncated": False,
                    "nextAction": "ok",
                    "error": None,
                    "source": {
                        "fileId": "f1",
                        "storageId": "source",
                        "resourceLibraryId": "library",
                        "path": "movies/Test.mkv",
                        "filename": "Test.mkv",
                        "extension": "mkv",
                        "size": 1024,
                        "scanStatus": "ready",
                        "occurrenceState": "verified",
                        "occurrenceId": "occ-abc",
                        "fingerprint": "a" * 64,
                    },
                    "choice": {
                        "recognitionTypeId": "type-a",
                        "namingPolicyId": "naming-a",
                        "classificationPolicyId": "class-a",
                        "organizePolicyId": "organize-a",
                    },
                    "configurationSnapshotId": "snap1",
                    "configurationSnapshotDigest": "d" * 64,
                    "plan": {
                        "recognitionType": "type-a",
                        "destination": "/Media/Movies/Test/Test.mkv",
                        "zeroMutation": True,
                        "sourceFingerprint": "a" * 64,
                        "inputFingerprint": "b" * 64,
                    },
                }
            ],
        }
        bounded = manual_preview_operator_document(raw)
        self.assertEqual("p1", bounded["previewId"])
        self.assertEqual("previewed", bounded["status"])
        self.assertIsNone(bounded.get("configurationSnapshotDigest"))
        self.assertIn("configurationSnapshotId", bounded)
        self.assertEqual(1, len(bounded["items"]))
        item = bounded["items"][0]
        self.assertIsNone(item["source"].get("occurrenceId"))
        self.assertIsNone(item["source"].get("fingerprint"))
        self.assertIn("destination", item["plan"])
        self.assertIsNone(item["plan"].get("sourceFingerprint"))
        self.assertIsNone(item["plan"].get("inputFingerprint"))
        self.assertTrue(item["plan"].get("zeroMutation"))


class HostileProjectionTests(unittest.TestCase):
    """The bounded operator documents must survive hostile persisted records."""

    def test_preview_projection_rejects_every_forbidden_nested_shape(self) -> None:
        from mediaflow.application.operations_lifecycle import manual_preview_operator_document

        raw = {
            "previewId": "p1",
            "intentId": "i1",
            "actor": "test",
            "intentVersion": 1,
            "configurationSnapshotId": "snap1",
            "configurationSnapshotDigest": "d" * 64,
            "status": "previewed",
            "current": True,
            "createdAt": "2026-09-04T12:00:00Z",
            "updatedAt": "2026-09-04T12:00:00Z",
            "nextAction": "inspect items",
            "error": None,
            "sideEffects": "none",
            "zeroMutation": True,
            "executionState": "ready_for_explicit_authorization",
            "truncated": False,
            "scope": {"kind": "file", "id": "f1", "itemCount": 1},
            "scopeKind": "file",
            "scopeId": "f1",
            "selection": {"selectedItemIds": ["it1"], "unselectedItemIds": []},
            "items": [
                {
                    "previewItemId": "pi1",
                    "previewId": "p1",
                    "itemId": "it1",
                    "position": 0,
                    "stage": "planning",
                    "status": "previewed",
                    "current": True,
                    "truncated": False,
                    "nextAction": "ok",
                    "error": None,
                    "zeroMutation": True,
                    "executionState": "ready_for_explicit_authorization",
                    "configurationSnapshotId": "snap1",
                    "configurationSnapshotDigest": "d" * 64,
                    "sourceFingerprint": "a" * 64,
                    "source": {
                        "fileId": "f1",
                        "storageId": "source",
                        "resourceLibraryId": "library",
                        "path": "movies/Test.mkv",
                        "filename": "Test.mkv",
                        "extension": "mkv",
                        "size": 1024,
                        "scanStatus": "ready",
                        "occurrenceState": "verified",
                        "occurrenceId": "occ-abc",
                        "fingerprint": "a" * 64,
                    },
                    "choice": {
                        "recognitionTypeId": "type-a",
                        "namingPolicyId": "naming-a",
                        "classificationPolicyId": "class-a",
                        "organizePolicyId": "organize-a",
                    },
                    "plan": {
                        "recognitionType": "type-a",
                        "mediaIdentity": {
                            "provider": "tmdb",
                            "providerId": "129",
                            "title": "One",
                            "year": 2001,
                        },
                        "policies": {
                            "recognitionTypePolicyId": "type-a",
                            "metadataPolicyId": "metadata-a",
                            "namingPolicyId": "naming-a",
                            "classificationPolicyId": "class-a",
                            "organizePolicyId": "organize-a",
                        },
                        "analysis": {
                            "parse": {
                                "titleCandidate": "One",
                                "year": 2001,
                                "evidence": [
                                    {
                                        "field": "fingerprint",
                                        "value": "b" * 64,
                                        "source": "filename",
                                        "confidence": "high",
                                    }
                                ],
                            },
                            "recognition": {"status": "matched", "recognitionTypeId": "type-a"},
                            "metadata": {"available": True, "query": "One"},
                            "naming": {"available": True, "directory": "A", "filename": "One.mkv"},
                            "classification": {"available": True, "relativePath": "A"},
                        },
                        "destination": {
                            "storageId": "target",
                            "mediaLibraryRoot": "/private/media",
                            "relativePath": "A/One (2001)/One (2001).mkv",
                            "path": "/private/media/out.mkv",
                        },
                        "operation": "move",
                        "operationPolicy": "move",
                        "attachments": [
                            {
                                "type": "subtitle",
                                "source": {"storageId": "source", "path": "movies/Test.zh.srt"},
                                "destination": {
                                    "storageId": "target",
                                    "path": "/private/media/out.mkv",
                                },
                                "operation": "link",
                                "suffix": ".zh",
                            },
                            {
                                "type": "subtitle",
                                "source": {"storageId": "source", "path": "movies/Test.en.srt"},
                                "destination": {
                                    "storageId": "target",
                                    "path": "/private/media/Authorization: Bearer hidden.srt",
                                },
                                "operation": "link",
                                "suffix": ".en",
                            },
                        ],
                        "executionPlan": {
                            "planId": "plan-1",
                            "sourceStorageId": "source",
                            "sourcePath": "/private/media/in.mkv",
                            "targetStorageId": "target",
                            "targetPath": "/private/media/out.mkv",
                            "mediaLibraryRoot": "/private/media",
                            "sourceLibraryRoot": "/private/source",
                        },
                        "capabilities": {
                            "required": ["can_copy"],
                            "declared": ["can_copy"],
                            "missing": [],
                            "verdict": "ok",
                        },
                        "conflicts": [
                            {
                                "type": "target_exists",
                                "source": "/private/media/in.mkv",
                                "destination": "/private/media/out.mkv",
                                "details": "an existing target was found",
                            }
                        ],
                        "warnings": ["/private/media is not writable"],
                        "planStatus": "ready",
                        "zeroMutation": True,
                        "executionState": "ready_for_explicit_authorization",
                        "bounded": True,
                        "deterministic": True,
                    },
                }
            ],
        }
        bounded = manual_preview_operator_document(raw)
        serialized = json.dumps(bounded)

        # Forbidden evidence is gone from keys, values and nested structures.
        self.assertNotIn("a" * 64, serialized)
        self.assertNotIn("b" * 64, serialized)
        self.assertNotIn("d" * 64, serialized)
        self.assertNotIn("Bearer hidden", serialized)
        self.assertNotIn("/private", serialized)
        self.assertNotIn("executionPlan", serialized)
        self.assertNotIn("sourceLibraryRoot", serialized)
        self.assertNotIn("mediaLibraryRoot", serialized)
        self.assertNotIn("occurrenceId", serialized)
        self.assertNotIn("fingerprint", serialized)
        self.assertNotIn("digest", serialized)

        # The operator-facing findings survive the redaction.
        item = bounded["items"][0]
        self.assertEqual("A/One (2001)/One (2001).mkv", item["plan"]["destination"]["relativePath"])
        self.assertEqual("target", item["plan"]["destination"]["storageId"])
        self.assertEqual("One", item["plan"]["mediaIdentity"]["title"])
        self.assertEqual("tmdb", item["plan"]["mediaIdentity"]["provider"])
        self.assertEqual("A", item["plan"]["analysis"]["classification"]["relativePath"])
        attachments = item["plan"]["attachments"]
        self.assertEqual(2, len(attachments))
        self.assertEqual("subtitle", attachments[0]["type"])
        self.assertEqual("zh", attachments[0]["language"])
        self.assertEqual("out.mkv", attachments[0]["filename"])
        self.assertIsNotNone(attachments[1]["filename"])
        self.assertNotIn("hidden", attachments[1]["filename"])
        self.assertNotIn("Authorization", attachments[1]["filename"])
        conflicts = item["plan"]["conflicts"]
        self.assertEqual(1, len(conflicts))
        self.assertEqual("target_exists", conflicts[0]["type"])
        self.assertEqual("media/out.mkv", conflicts[0]["destination"])
        self.assertTrue(item["zeroMutation"])
        self.assertEqual("none", item["sideEffects"])


class RetiredManualActionMatrixTests(unittest.TestCase):
    """The old action matrix route has no current product consumer."""

    def test_old_registered_queries_are_ordinary_not_found(self) -> None:
        storage = FakeStorage("source")
        storage.add_file("current.mkv", 10, NOW - timedelta(hours=2))
        library_value = ResourceLibrary("library", "Library", "source", "", exclude_rules=())
        api = _api(library_value=library_value, storage=storage)
        for query in (
            "scopeKind=file&fileId=any-id&resourceLibraryId=library",
            "scopeKind=resourceLibrary",
            "scopeKind=resourceLibrary&resourceLibraryId=library",
            "scopeKind=host_path",
        ):
            with self.subTest(query=query):
                status, body = _get(api, f"/api/operations/manual-actions?{query}")
                self.assertEqual(404, status)
                self.assertEqual("not_found", body["error"]["code"])


class RetiredServerBoundPreviewTests(unittest.TestCase):
    """The standalone current-source Preview product is retired.

    ``/api/operations/previews`` no longer serves an independent product;
    its old inputs get an ordinary not-found answer after normal authentication
    and create no Preview record.
    """

    def setUp(self) -> None:
        self.storage = FakeStorage("source")
        self.storage.add_file("current.mkv", 10, NOW - timedelta(hours=2))
        self.library_value = ResourceLibrary("library", "Library", "source", "", exclude_rules=())

    def _make_api(self, permissions=None):
        if permissions is None:
            permissions = frozenset(
                {
                    ApiPermission.READ,
                    ApiPermission.SUBMIT_DRY_RUN,
                    ApiPermission.MANAGE_MANUAL_ORGANIZE,
                }
            )
        return _api(
            permissions=permissions,
            library_value=self.library_value,
            storage=self.storage,
        )

    def test_old_server_bound_preview_routes_are_ordinary_not_found(self) -> None:
        api = self._make_api()
        for method, path, body in (
            (
                "POST",
                "/api/operations/previews",
                {"scopeKind": "resource_library", "resourceLibraryId": "library"},
            ),
            ("GET", "/api/operations/previews", None),
            (
                "GET",
                "/api/operations/previews?scopeKind=resource_library&scopeId=library",
                None,
            ),
            ("GET", "/api/operations/previews/nonexistent", None),
        ):
            with self.subTest(method=method, path=path):
                if method == "POST":
                    status, _ = _post(api, path, body=body)
                else:
                    status, _ = _get(api, path)
                self.assertEqual(404, status)


class ZeroMutationInvariantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = FakeStorage("source")
        self.storage.add_file("current.mkv", 10, NOW - timedelta(hours=2))
        self.library_value = ResourceLibrary("library", "Library", "source", "", exclude_rules=())

    def test_preview_operator_document_declares_zero_mutation(self) -> None:
        """Verify that bounded preview documents always declare zero mutation."""
        from mediaflow.application.operations_lifecycle import manual_preview_operator_document

        preview_doc = {
            "previewId": "p1",
            "intentId": "i1",
            "actor": "test",
            "intentVersion": 1,
            "configurationSnapshotId": "snap1",
            "configurationSnapshotDigest": "d" * 64,
            "status": "previewed",
            "current": True,
            "createdAt": "2026-09-04T12:00:00Z",
            "updatedAt": "2026-09-04T12:00:00Z",
            "nextAction": "inspect items",
            "error": None,
            "sideEffects": "none",
            "zeroMutation": True,
            "executionState": "ready_for_explicit_authorization",
            "truncated": False,
            "scope": {"kind": "file", "id": "f1", "itemCount": 1},
            "items": [
                {
                    "previewItemId": "pi1",
                    "previewId": "p1",
                    "itemId": "it1",
                    "position": 0,
                    "stage": "planning",
                    "status": "previewed",
                    "createdAt": "2026-09-04T12:00:00Z",
                    "updatedAt": "2026-09-04T12:00:00Z",
                    "current": True,
                    "truncated": False,
                    "nextAction": "ok",
                    "error": None,
                    "source": {
                        "fileId": "f1",
                        "storageId": "source",
                        "resourceLibraryId": "library",
                        "path": "movies/Test.mkv",
                        "filename": "Test.mkv",
                        "extension": "mkv",
                        "size": 1024,
                        "scanStatus": "ready",
                        "occurrenceState": "verified",
                        "occurrenceId": "occ-abc",
                        "fingerprint": "a" * 64,
                    },
                    "choice": {
                        "recognitionTypeId": "type-a",
                        "namingPolicyId": "naming-a",
                        "classificationPolicyId": "class-a",
                        "organizePolicyId": "organize-a",
                    },
                    "configurationSnapshotId": "snap1",
                    "configurationSnapshotDigest": "d" * 64,
                    "plan": {
                        "recognitionType": "type-a",
                        "destination": "/Media/Movies/Test/Test.mkv",
                        "zeroMutation": True,
                        "sourceFingerprint": "a" * 64,
                        "inputFingerprint": "b" * 64,
                    },
                }
            ],
        }
        bounded = manual_preview_operator_document(preview_doc)
        # Zero mutation invariant
        self.assertTrue(bounded["zeroMutation"])
        self.assertIn(
            bounded["executionState"],
            ("not_available_in_this_task", "ready_for_explicit_authorization"),
        )
        for item in bounded.get("items", []):
            self.assertTrue(item.get("zeroMutation"))
            self.assertIn(item.get("executionState"), ("not_available_in_this_task", None))
        # Configuration digest must be stripped
        self.assertNotIn("configurationSnapshotDigest", bounded)
        self.assertIn("configurationSnapshotId", bounded)
        # Item source must not have fingerprint
        item = bounded["items"][0]
        self.assertIsNone(item["source"].get("occurrenceId"))
        self.assertIsNone(item["source"].get("fingerprint"))
        # Plan must not have fingerprint
        self.assertIsNone(item["plan"].get("sourceFingerprint"))
        self.assertIsNone(item["plan"].get("inputFingerprint"))


if __name__ == "__main__":
    unittest.main()
