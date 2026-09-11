"""Tests for the V2 bounded manual Scan/Preview API surface.

Covers:
- Server-bound scan admission (no fingerprint echo)
- Server-bound preview admission (no fingerprint echo)
- Bounded action matrix projection
- Bounded scan and preview operator documents
- Preview zero-mutation invariant
- Error/failure states are truthfully projected
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mediaflow.application.manual_scan import ManualScanError, ManualScanService
from mediaflow.domain.file_lifecycle import OccurrenceState
from mediaflow.domain.library import ResourceLibrary
from mediaflow.domain.scanner import FileScanStatus
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import PersistentTaskStatus
from mediaflow.infrastructure.configuration_snapshot import ConfigurationSnapshot
from mediaflow.infrastructure.memory_file_index import InMemoryFileIndexRepository
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
    index: InMemoryFileIndexRepository | None = None,
    library_value: ResourceLibrary | None = None,
    storage: FakeStorage | None = None,
    include_manual_scan: bool = True,
    include_manual_preview: bool = True,
) -> MediaFlowApi:
    from mediaflow.application.file_catalog import FileCatalogService
    from mediaflow.application.manual_organize import ManualOrganizeIntentService
    from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
    from mediaflow.domain.manual_organize import ManualConfigurationSnapshot

    principal = ResolvedApiPrincipal("test-operator", "test-token", permissions)
    storage = storage or FakeStorage("source")
    library_value = library_value or ResourceLibrary(
        "library", "Library", "source", "", exclude_rules=()
    )
    index = index or InMemoryFileIndexRepository()
    snapshot = _system_status_snapshot((library_value,))
    repository = SQLiteTaskRepository(Path(tempfile.mkdtemp(), "test.sqlite3"))

    # Wire up the manual pipeline.
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


class BoundedDocumentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = FakeStorage("source")
        self.storage.add_file("current.mkv", 10, NOW - timedelta(hours=2))
        self.library_value = ResourceLibrary("library", "Library", "source", "", exclude_rules=())
        self.index = InMemoryFileIndexRepository()
        from mediaflow.application.scanner import StorageScanner

        self.scanner = StorageScanner({"source": self.storage}, self.index, clock=lambda: NOW)
        self.scanner.scan(self.library_value)

    def test_scan_operator_document_strips_fingerprint(self) -> None:
        from mediaflow.application.operations_lifecycle import manual_scan_operator_document

        raw = {
            "taskId": "t1",
            "scopeKind": "file",
            "scopeId": "f1",
            "resourceLibraryId": "library",
            "fileId": "f1",
            "storageId": "source",
            "sourcePath": "movies/Test.mkv",
            "sourceOccurrenceId": "occ-abc",
            "sourceFingerprint": "a" * 64,
            "configurationSnapshotId": "snap1",
            "configurationSnapshotDigest": "d" * 64,
            "status": "running",
            "createdAt": "2026-09-04T12:00:00Z",
            "updatedAt": "2026-09-04T12:00:00Z",
            "cancellationRequested": False,
            "progress": {"filesVisited": 1},
            "errors": [],
            "items": [],
        }
        bounded = manual_scan_operator_document(raw)
        self.assertEqual("t1", bounded["taskId"])
        self.assertIsNone(bounded.get("sourceOccurrenceId"))
        self.assertIsNone(bounded.get("sourceFingerprint"))
        self.assertIsNone(bounded.get("configurationSnapshotDigest"))
        self.assertIn("configurationSnapshotId", bounded)
        self.assertEqual("movies/Test.mkv", bounded["sourcePath"])

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

    def test_scan_projection_bounds_errors_and_publishes_paging_and_actions(self) -> None:
        from mediaflow.application.operations_lifecycle import manual_scan_operator_document

        raw = {
            "taskId": "t1",
            "scopeKind": "resource_library",
            "scopeId": "library",
            "resourceLibraryId": "library",
            "fileId": None,
            "storageId": "source",
            "sourcePath": "movies/Test.mkv",
            "sourceOccurrenceId": "occ-abc",
            "sourceFingerprint": "a" * 64,
            "configurationSnapshotId": "snap1",
            "configurationSnapshotDigest": "d" * 64,
            "mode": "full",
            "status": "partial_success",
            "createdAt": "2026-09-04T12:00:00Z",
            "updatedAt": "2026-09-04T12:00:00Z",
            "cancellationRequested": False,
            "progress": {
                "directoriesVisited": 2,
                "filesVisited": 5,
                "mediaCandidates": 3,
                "ignored": 1,
                "unstable": 0,
                "errors": 1,
            },
            "errors": [
                {
                    "code": "read_failed",
                    "path": "/srv/private/media/bad.mkv",
                    "operation": "list",
                }
            ],
            "reconciliationComplete": False,
            "failureStage": "discovery",
            "knownEffects": "partial_discovery_only",
            "retrySafe": True,
            "nextAction": "inspect per-item outcomes",
            "error": "manual Scan completed with discovery errors",
            "itemLimit": 20,
            "itemsTruncated": True,
            "nextItemCursor": "eyJhIjoxfQ==",
            "previousItemCursor": None,
            "items": [
                {
                    "itemId": "i1",
                    "taskId": "t1",
                    "storageId": "source",
                    "resourceLibraryId": "library",
                    "sourcePath": "movies/Test.mkv",
                    "fileId": "f1",
                    "status": "ready",
                    "change": "unchanged",
                    "stage": "manual_scan_discovery",
                    "createdAt": "2026-09-04T12:00:00Z",
                    "updatedAt": "2026-09-04T12:00:00Z",
                    "sourceOccurrenceId": "occ-abc",
                    "sourceFingerprint": "a" * 64,
                    "error": None,
                    "knownEffects": "file_index_discovery_refreshed",
                    "retrySafe": True,
                    "nextAction": "inspect the refreshed FileIndex item",
                }
            ],
        }
        bounded = manual_scan_operator_document(raw)
        serialized = json.dumps(bounded)

        self.assertEqual("resourceLibrary", bounded["scopeKind"])
        self.assertEqual(20, bounded["itemLimit"])
        self.assertTrue(bounded["itemsTruncated"])
        self.assertEqual("eyJhIjoxfQ==", bounded["nextItemCursor"])
        self.assertIsNone(bounded["previousItemCursor"])
        self.assertEqual("partial_success", bounded["status"])
        self.assertEqual(1, len(bounded["errors"]))
        self.assertEqual("media/bad.mkv", bounded["errors"][0]["path"])
        self.assertIsNotNone(bounded["failure"])
        self.assertFalse(bounded["actions"]["cancel"]["available"])
        self.assertEqual("POST", bounded["actions"]["cancel"]["method"])
        self.assertNotIn("a" * 64, serialized)
        self.assertNotIn("d" * 64, serialized)
        self.assertNotIn("/srv/private", serialized)
        self.assertNotIn("sourceFingerprint", serialized)
        self.assertNotIn("configurationSnapshotDigest", serialized)
        self.assertEqual("movies/Test.mkv", bounded["items"][0]["sourcePath"])

    def test_scan_projection_advertises_cancel_only_for_a_cancellable_state(self) -> None:
        from mediaflow.application.operations_lifecycle import manual_scan_operator_document

        base = {
            "taskId": "t1",
            "scopeKind": "file",
            "scopeId": "f1",
            "resourceLibraryId": "library",
            "fileId": "f1",
            "storageId": "source",
            "sourcePath": "movies/Test.mkv",
            "mode": "incremental",
            "status": "running",
            "createdAt": "2026-09-04T12:00:00Z",
            "updatedAt": "2026-09-04T12:00:00Z",
            "cancellationRequested": False,
            "progress": {},
            "errors": [],
            "items": [],
        }
        running = manual_scan_operator_document(base)
        self.assertTrue(running["actions"]["cancel"]["available"])
        self.assertIsNone(running["actions"]["cancel"]["unavailableReason"])
        self.assertIn("/api/v1/operations/scans/t1/cancel", running["actions"]["cancel"]["path"])

        requested = manual_scan_operator_document({**base, "cancellationRequested": True})
        self.assertFalse(requested["actions"]["cancel"]["available"])
        self.assertIn("already been requested", requested["actions"]["cancel"]["unavailableReason"])

        for status in ("completed", "failed", "cancelled", "partial_success"):
            terminal = manual_scan_operator_document({**base, "status": status})
            self.assertFalse(terminal["actions"]["cancel"]["available"])


class ServerBoundScanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = FakeStorage("source")
        self.storage.add_file("current.mkv", 10, NOW - timedelta(hours=2))
        self.library_value = ResourceLibrary("library", "Library", "source", "", exclude_rules=())
        self.index = InMemoryFileIndexRepository()
        from mediaflow.application.scanner import StorageScanner

        self.scanner = StorageScanner({"source": self.storage}, self.index, clock=lambda: NOW)
        self.scanner.scan(self.library_value)

    def _make_service(self, repository) -> ManualScanService:
        return ManualScanService(
            repository,
            self.index,
            resource_libraries=(self.library_value,),
            storages={"source": self.storage},
            configuration_snapshot_id="snap",
            configuration_snapshot_digest="digest",
            clock=lambda: NOW,
            start_async=False,
        )

    def test_file_scope_admission_resolves_current_record(self) -> None:
        record = self.index.find_by_path("source", "library", "current.mkv")
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = self._make_service(repository)
                scan = service.admit_current_document(
                    {
                        "scopeKind": "file",
                        "fileId": record.file_id,
                        "resourceLibraryId": "library",
                        "mode": "incremental",
                    }
                )
                self.assertEqual(PersistentTaskStatus.RUNNING, scan.status)
                self.assertEqual(record.file_id, scan.file_id)
                self.assertEqual(record.occurrence_id, scan.source_occurrence_id)
                self.assertEqual(record.fingerprint, scan.source_fingerprint)

    def test_file_scope_rejects_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = self._make_service(repository)
                with self.assertRaises(ManualScanError) as ctx:
                    service.admit_current_document(
                        {
                            "scopeKind": "file",
                            "fileId": "nonexistent",
                            "resourceLibraryId": "library",
                            "mode": "incremental",
                        }
                    )
                self.assertEqual("source_not_found", ctx.exception.code)

    def test_file_scope_rejects_not_ready(self) -> None:
        record = self.index.find_by_path("source", "library", "current.mkv")
        from mediaflow.domain.file_index import FileIndexRecord

        not_ready = FileIndexRecord(
            record.file_id,
            "source",
            "library",
            "current.mkv",
            "current.mkv",
            "mkv",
            10,
            NOW,
            NOW,
            NOW,
            None,
            FileScanStatus.UNSTABLE,
            None,
            NOW,
            NOW,
            None,
            None,
            None,
            None,
            None,
            OccurrenceState.UNVERIFIED,
        )
        self.index.batch_upsert((not_ready,))
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = self._make_service(repository)
                with self.assertRaises(ManualScanError) as ctx:
                    service.admit_current_document(
                        {
                            "scopeKind": "file",
                            "fileId": record.file_id,
                            "resourceLibraryId": "library",
                            "mode": "incremental",
                        }
                    )
                self.assertEqual("source_not_ready", ctx.exception.code)

    def test_file_scope_rejects_changed_source_live(self) -> None:
        record = self.index.find_by_path("source", "library", "current.mkv")
        self.storage.files["current.mkv"] = (99, NOW - timedelta(hours=1))
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = self._make_service(repository)
                with self.assertRaises(ManualScanError) as ctx:
                    service.admit_current_document(
                        {
                            "scopeKind": "file",
                            "fileId": record.file_id,
                            "resourceLibraryId": "library",
                            "mode": "incremental",
                        }
                    )
                self.assertEqual("source_stale", ctx.exception.code)

    def test_resource_library_scope_admission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = self._make_service(repository)
                scan = service.admit_current_document(
                    {
                        "scopeKind": "resource_library",
                        "resourceLibraryId": "library",
                        "mode": "incremental",
                    }
                )
                self.assertEqual(PersistentTaskStatus.RUNNING, scan.status)
                self.assertIsNone(scan.file_id)

    def test_file_scope_rejects_fingerprint_echo(self) -> None:
        record = self.index.find_by_path("source", "library", "current.mkv")
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = self._make_service(repository)
                with self.assertRaises(ManualScanError) as ctx:
                    service.admit_current_document(
                        {
                            "scopeKind": "file",
                            "fileId": record.file_id,
                            "resourceLibraryId": "library",
                            "occurrenceId": record.occurrence_id,
                            "fingerprint": record.fingerprint,
                            "mode": "incremental",
                        }
                    )
                self.assertEqual("invalid_request", ctx.exception.code)


class ActionMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = FakeStorage("source")
        self.storage.add_file("current.mkv", 10, NOW - timedelta(hours=2))
        self.library_value = ResourceLibrary("library", "Library", "source", "", exclude_rules=())
        self.index = InMemoryFileIndexRepository()
        from mediaflow.application.scanner import StorageScanner

        self.scanner = StorageScanner({"source": self.storage}, self.index, clock=lambda: NOW)
        self.scanner.scan(self.library_value)

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
            index=self.index,
            library_value=self.library_value,
            storage=self.storage,
        )

    def test_file_scope_action_matrix(self) -> None:
        record = self.index.find_by_path("source", "library", "current.mkv")
        api = self._make_api()
        status, body = _get(
            api,
            f"/api/v1/operations/manual-actions?scopeKind=file&fileId={record.file_id}&resourceLibraryId=library",
        )
        self.assertEqual(200, status)
        self.assertEqual("file", body["scopeKind"])
        self.assertIsNotNone(body["source"])
        self.assertTrue(body["actions"]["scan"]["available"])
        self.assertTrue(body["actions"]["preview"]["available"])

    def test_action_matrix_with_unavailable_scan_service_offers_no_submission(self) -> None:
        """An advertised action must have a callable bound application service."""

        api = _api(
            permissions=frozenset(
                {
                    ApiPermission.READ,
                    ApiPermission.SUBMIT_DRY_RUN,
                    ApiPermission.MANAGE_MANUAL_ORGANIZE,
                }
            ),
            index=self.index,
            library_value=self.library_value,
            storage=self.storage,
            include_manual_scan=False,
        )
        status, body = _get(
            api,
            "/api/v1/operations/manual-actions?scopeKind=resourceLibrary&resourceLibraryId=library",
        )
        self.assertEqual(200, status)
        self.assertFalse(body["actions"]["scan"]["available"])
        self.assertIn("Scan service is unavailable", body["actions"]["scan"]["reason"])
        post_status, post_body = _post(
            api,
            "/api/v1/operations/scans",
            {
                "scopeKind": "resourceLibrary",
                "resourceLibraryId": "library",
                "mode": "full",
            },
        )
        self.assertEqual(503, post_status)
        self.assertEqual("service_unavailable", post_body["error"]["code"])

    def test_action_matrix_with_unavailable_preview_service_offers_no_submission(self) -> None:
        """Preview availability also requires its bound application service."""

        api = _api(
            permissions=frozenset(
                {
                    ApiPermission.READ,
                    ApiPermission.SUBMIT_DRY_RUN,
                    ApiPermission.MANAGE_MANUAL_ORGANIZE,
                }
            ),
            index=self.index,
            library_value=self.library_value,
            storage=self.storage,
            include_manual_preview=False,
        )
        status, body = _get(
            api,
            "/api/v1/operations/manual-actions?scopeKind=resourceLibrary&resourceLibraryId=library",
        )
        self.assertEqual(200, status)
        self.assertFalse(body["actions"]["preview"]["available"])
        self.assertIn("Preview service is unavailable", body["actions"]["preview"]["reason"])
        post_status, post_body = _post(
            api,
            "/api/v1/operations/previews",
            {
                "scopeKind": "resourceLibrary",
                "resourceLibraryId": "library",
            },
        )
        self.assertEqual(503, post_status)
        self.assertEqual("service_unavailable", post_body["error"]["code"])

    def test_library_scope_action_matrix(self) -> None:
        api = self._make_api()
        status, body = _get(
            api,
            "/api/v1/operations/manual-actions?scopeKind=resourceLibrary&resourceLibraryId=library",
        )
        self.assertEqual(200, status)
        self.assertEqual("resourceLibrary", body["scopeKind"])
        self.assertEqual("library", body["scopeId"])
        self.assertFalse(body["selectionRequired"])
        self.assertTrue(body["actions"]["scan"]["available"])
        self.assertEqual(["full", "incremental"], body["actions"]["scan"]["modes"])

    def test_library_discovery_matrix_offers_no_action_without_a_selection(self) -> None:
        api = self._make_api()
        status, body = _get(
            api,
            "/api/v1/operations/manual-actions?scopeKind=resourceLibrary",
        )
        self.assertEqual(200, status)
        self.assertEqual("resourceLibrary", body["scopeKind"])
        self.assertIsNone(body["scopeId"])
        self.assertTrue(body["selectionRequired"])
        self.assertIsNone(body["source"])
        self.assertFalse(body["actions"]["scan"]["available"])
        self.assertFalse(body["actions"]["preview"]["available"])
        self.assertIn("select an exact ResourceLibrary", body["actions"]["scan"]["reason"])
        self.assertEqual(
            ["library"], [item["resourceLibraryId"] for item in body["resourceLibraries"]]
        )
        self.assertTrue(body["resourceLibraries"][0]["enabled"])

    def test_viewer_without_scan_permission(self) -> None:
        api = self._make_api(permissions=frozenset({ApiPermission.READ}))
        record = self.index.find_by_path("source", "library", "current.mkv")
        status, body = _get(
            api,
            f"/api/v1/operations/manual-actions?scopeKind=file&fileId={record.file_id}&resourceLibraryId=library",
        )
        self.assertEqual(200, status)
        self.assertFalse(body["actions"]["scan"]["available"])

    def test_file_not_found_returns_unavailable(self) -> None:
        api = self._make_api()
        status, body = _get(
            api,
            "/api/v1/operations/manual-actions?scopeKind=file&fileId=nonexistent&resourceLibraryId=library",
        )
        self.assertEqual(200, status)
        self.assertFalse(body["actions"]["scan"]["available"])
        self.assertFalse(body["actions"]["preview"]["available"])

    def test_unknown_scope_kind_fails_closed(self) -> None:
        api = self._make_api()
        status, body = _get(
            api,
            "/api/v1/operations/manual-actions?scopeKind=host_path",
        )
        self.assertEqual(400, status)
        self.assertEqual("invalid_request", body["error"]["code"])

    def test_file_scope_requires_an_exact_source_identity(self) -> None:
        api = self._make_api()
        status, _ = _get(
            api,
            "/api/v1/operations/manual-actions?scopeKind=file&resourceLibraryId=library",
        )
        self.assertEqual(400, status)

    def test_resource_library_not_enabled(self) -> None:
        disabled = ResourceLibrary(
            "disabled", "Disabled", "source", "", exclude_rules=(), enabled=False
        )
        api = _api(
            permissions=frozenset({ApiPermission.READ, ApiPermission.SUBMIT_DRY_RUN}),
            index=self.index,
            library_value=disabled,
            storage=self.storage,
        )
        status, body = _get(
            api,
            "/api/v1/operations/manual-actions?scopeKind=resourceLibrary&resourceLibraryId=disabled",
        )
        self.assertEqual(200, status)
        self.assertFalse(body["actions"]["scan"]["available"])

    def test_action_matrix_redacts_credential_shaped_file_labels(self) -> None:
        """A FileIndex filename cannot bypass the Operations redaction boundary."""

        self.storage.add_file("Bearer hidden-token.mkv", 10, NOW - timedelta(hours=2))
        from mediaflow.application.scanner import StorageScanner

        StorageScanner({"source": self.storage}, self.index, clock=lambda: NOW).scan(
            self.library_value
        )
        record = self.index.find_by_path("source", "library", "Bearer hidden-token.mkv")
        self.assertIsNotNone(record)
        api = self._make_api()
        status, body = _get(
            api,
            f"/api/v1/operations/manual-actions?scopeKind=file&fileId={record.file_id}&resourceLibraryId=library",
        )
        self.assertEqual(200, status)
        serialized = json.dumps(body)
        self.assertNotIn("hidden-token", serialized)
        self.assertNotIn("Bearer hidden-token", serialized)
        self.assertEqual(
            "[redacted: the recorded evidence contained a credential, private endpoint "
            "or absolute host path]",
            body["source"]["filename"],
        )


class PrincipalBoundScanProjectionTests(unittest.TestCase):
    def test_read_only_scan_detail_does_not_advertise_cancel(self) -> None:
        """Scan lifecycle controls are projected for the authenticated principal."""

        storage = FakeStorage("source")
        storage.add_file("current.mkv", 10, NOW - timedelta(hours=2))
        library = ResourceLibrary("library", "Library", "source", "", exclude_rules=())
        index = InMemoryFileIndexRepository()
        from mediaflow.application.scanner import StorageScanner

        StorageScanner({"source": storage}, index, clock=lambda: NOW).scan(library)
        operator = ResolvedApiPrincipal(
            "operator",
            "operator-token",
            frozenset({ApiPermission.READ, ApiPermission.SUBMIT_DRY_RUN, ApiPermission.CANCEL_JOB}),
        )
        viewer = ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = ManualScanService(
                    repository,
                    index,
                    resource_libraries=(library,),
                    storages={"source": storage},
                    configuration_snapshot_id="active-snap",
                    configuration_snapshot_digest="active-digest",
                    clock=lambda: NOW,
                    start_async=False,
                )
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(operator, viewer),
                    manual_scan_service=service,
                )
                status, admitted = _post(
                    api,
                    "/api/v1/operations/scans",
                    {
                        "scopeKind": "resourceLibrary",
                        "resourceLibraryId": "library",
                        "mode": "full",
                    },
                    token="operator-token",
                )
                self.assertEqual(202, status)
                task_id = admitted["taskId"]
                status, detail = _get(
                    api,
                    f"/api/v1/operations/scans/{task_id}",
                    token="viewer-token",
                )
                self.assertEqual(200, status)
                self.assertFalse(detail["actions"]["cancel"]["available"])
                self.assertIn(
                    "cancel_job permission", detail["actions"]["cancel"]["unavailableReason"]
                )
                cancel_status, cancel_body = _post(
                    api,
                    f"/api/v1/operations/scans/{task_id}/cancel",
                    token="viewer-token",
                )
                self.assertEqual(403, cancel_status)
                self.assertEqual("forbidden", cancel_body["error"]["code"])


class ServerBoundPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = FakeStorage("source")
        self.storage.add_file("current.mkv", 10, NOW - timedelta(hours=2))
        self.library_value = ResourceLibrary("library", "Library", "source", "", exclude_rules=())
        self.index = InMemoryFileIndexRepository()
        from mediaflow.application.scanner import StorageScanner

        self.scanner = StorageScanner({"source": self.storage}, self.index, clock=lambda: NOW)
        self.scanner.scan(self.library_value)

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
            index=self.index,
            library_value=self.library_value,
            storage=self.storage,
        )

    def test_server_bound_preview_requires_permission(self) -> None:
        api = self._make_api(permissions=frozenset({ApiPermission.READ}))
        status, _ = _post(
            api,
            "/api/v1/operations/previews",
            body={
                "scopeKind": "resource_library",
                "resourceLibraryId": "library",
            },
            token="test-token",
        )
        self.assertEqual(403, status)

    def test_server_bound_preview_rejects_unknown_scope(self) -> None:
        api = self._make_api()
        status, body = _post(
            api,
            "/api/v1/operations/previews",
            body={
                "scopeKind": "invalid",
                "resourceLibraryId": "library",
            },
        )
        self.assertEqual(400, status)

    def test_server_bound_preview_rejects_fingerprint_echo(self) -> None:
        api = self._make_api()
        status, body = _post(
            api,
            "/api/v1/operations/previews",
            body={
                "scopeKind": "resource_library",
                "resourceLibraryId": "library",
                "fingerprint": "a" * 64,
            },
        )
        self.assertEqual(400, status)

    def test_server_bound_preview_list_requires_scope(self) -> None:
        api = self._make_api()
        status, _ = _get(
            api,
            "/api/v1/operations/previews",
        )
        self.assertEqual(400, status)

    def test_server_bound_preview_detail_not_found(self) -> None:
        api = self._make_api()
        status, _ = _get(
            api,
            "/api/v1/operations/previews/nonexistent",
        )
        self.assertEqual(404, status)

    def test_server_bound_preview_list_returns_empty(self) -> None:
        api = self._make_api()
        status, _ = _get(
            api,
            "/api/v1/operations/previews?scopeKind=resource_library&scopeId=library",
        )
        # Returns 200 with empty list when no previews exist
        self.assertEqual(200, status)


class ZeroMutationInvariantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = FakeStorage("source")
        self.storage.add_file("current.mkv", 10, NOW - timedelta(hours=2))
        self.library_value = ResourceLibrary("library", "Library", "source", "", exclude_rules=())
        self.index = InMemoryFileIndexRepository()
        from mediaflow.application.scanner import StorageScanner

        self.scanner = StorageScanner({"source": self.storage}, self.index, clock=lambda: NOW)
        self.scanner.scan(self.library_value)

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
