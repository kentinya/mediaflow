"""Golden contract proof for the V2 bounded manual Scan/Preview API.

This module drives the *real* ``MediaFlowApi`` over a real runtime
configuration, a real ``LocalStorage`` source, a real scanner-produced
FileIndex record and the real manual Scan/Preview services, and captures the
exact bounded documents the V2 Operations workspace consumes:

``GET  /api/v1/operations/manual-actions``
``POST /api/v1/operations/scans``
``GET  /api/v1/operations/scans/{taskId}``
``POST /api/v1/operations/previews``
``GET  /api/v1/operations/previews``
``GET  /api/v1/operations/previews/{previewId}``

The captured documents are canonicalized (timestamps, generated identifiers and
opaque paging cursors) and compared with the checked-in fixture consumed by the
frontend normalizers, component/router tests and built-artifact browser tests.
Running this module proves the fixture is still exactly what the API returns;
regenerate it with ``MEDIAFLOW_UPDATE_FIXTURES=1`` only when the API contract
itself intentionally changed.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.manual_scan import ManualScanService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.scanner import StorageScanner
from mediaflow.application.strategy_test import SyntheticMetadataProvider
from mediaflow.domain.library import MediaLibrary, ResourceLibrary
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.configuration_snapshot import build_configuration_snapshot
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.memory_file_index import InMemoryFileIndexRepository
from mediaflow.infrastructure.runtime_configuration import (
    RuntimeConfiguration,
    StorageDefinition,
    with_managed_snapshot,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import development_strategy_configuration
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_manual_organize_preview import manual_snapshot
from tests.test_manual_preview import MutationSpyStorage

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = (
    REPOSITORY_ROOT
    / "web"
    / "src"
    / "entities"
    / "operations"
    / "__fixtures__"
    / "manual-operations.json"
)
SNAPSHOT_ID = "active-1"
SNAPSHOT_DIGEST = "a" * 64
CANONICAL_TIMESTAMP = "2026-09-04T12:00:00+00:00"
CANONICAL_CURSOR = "<cursor>"

_TIMESTAMP_SHAPE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:\+00:00|Z)")
_UUID_SHAPE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
_HEX_ID_SHAPE = re.compile(r"\b[0-9a-f]{32}\b")
_DIGEST_SHAPE = re.compile(r"(?<![0-9a-zA-Z])[0-9a-f]{64}(?![0-9a-zA-Z])")
_CURSOR_KEYS = {"nextItemCursor", "previousItemCursor"}
_FORBIDDEN_SUBSTRINGS = (
    "Bearer ",
    "fingerprint",
    "digest",
    "occurrenceId",
    "executionPlan",
    "sourceLibraryRoot",
    'targetPath":',
    "mediaLibraryRoot",
    "/tmp/",
    "/private/",
    "smb://",
    "http://",
    "https://",
)


def _canonical(value: object, *, key: str | None = None) -> object:
    """Replace volatile values so one real API document can be a stable fixture."""

    if isinstance(value, dict):
        return {name: _canonical(item, key=name) for name, item in value.items()}
    if isinstance(value, list):
        return [_canonical(item, key=key) for item in value]
    if isinstance(value, str):
        if key in _CURSOR_KEYS:
            return CANONICAL_CURSOR
        text = _TIMESTAMP_SHAPE.sub(CANONICAL_TIMESTAMP, value)
        text = _UUID_SHAPE.sub("<uuid>", text)
        text = _HEX_ID_SHAPE.sub("<hex-id>", text)
        return text
    return value


def _request(api, path: str, *, method: str = "GET", body=None, query: str = ""):
    statuses: list[str] = []
    raw = json.dumps(body).encode("utf-8") if body is not None else b""
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(raw)),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": "Bearer contract-token",
        "wsgi.input": io.BytesIO(raw),
    }
    payload = b"".join(api(environ, lambda status, _headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(payload)


class ManualOperationsContractTests(unittest.TestCase):
    """The checked-in frontend fixture must be the real API document."""

    maxDiff = None

    @contextmanager
    def fixture(self):
        with (
            tempfile.TemporaryDirectory() as source_directory,
            tempfile.TemporaryDirectory() as target_directory,
            tempfile.TemporaryDirectory() as runtime_directory,
        ):
            source_root = Path(source_directory)
            target_root = Path(target_directory)
            Path(source_root, "One.2001.mkv").write_bytes(b"source-media")
            Path(source_root, "Two.2002.mkv").write_bytes(b"second-media")
            source_storage = LocalStorage("source", source_root)
            target_storage = LocalStorage("target", target_root)
            library = ResourceLibrary("library", "Library", "source", "", exclude_rules=())

            def scan_clock():
                return datetime.now(UTC) + timedelta(hours=2)

            index = InMemoryFileIndexRepository()
            result = StorageScanner({"source": source_storage}, index, clock=scan_clock).scan(
                library
            )
            self.assertEqual("completed", result.status.value)
            record = index.find_by_path("source", "library", "One.2001.mkv")
            self.assertIsNotNone(record)

            configuration = RuntimeConfiguration(
                development_strategy_configuration(),
                (
                    StorageDefinition("source", "local", str(source_root), "Source"),
                    StorageDefinition("target", "local", str(target_root), "Target"),
                ),
                (library,),
                (),
                (
                    MediaLibrary("movies", "Movies", "target", "Movies"),
                    MediaLibrary("tv", "TV", "target", "TV"),
                ),
                str(Path(runtime_directory, "history.jsonl")),
                str(Path(runtime_directory, "runtime.sqlite3")),
            )
            configuration = with_managed_snapshot(
                configuration,
                snapshot_id=SNAPSHOT_ID,
                digest=SNAPSHOT_DIGEST,
            )
            provider = SyntheticMetadataProvider(
                (
                    MediaCandidate(
                        "tmdb",
                        "129",
                        MediaType.MOVIE,
                        "One",
                        year=2001,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                )
            )
            source = MutationSpyStorage(source_storage)
            target = MutationSpyStorage(target_storage)
            repository = SQLiteTaskRepository(Path(runtime_directory, "runtime.sqlite3"))
            try:
                catalog = FileCatalogService(
                    index,
                    ("library",),
                    ("source",),
                    task_repository=repository,
                )
                intents = ManualOrganizeIntentService(
                    repository,
                    catalog,
                    configuration_resolver=manual_snapshot,
                )
                previews = ManualOrganizePreviewService(
                    repository,
                    intents,
                    catalog,
                    configuration=configuration,
                    file_index=index,
                    providers=MetadataProviderRegistry((provider,)),
                    storages={"source": source, "target": target},
                )
                scans = ManualScanService(
                    repository,
                    index,
                    resource_libraries=(library,),
                    storages={"source": source},
                    configuration_snapshot_id=SNAPSHOT_ID,
                    configuration_snapshot_digest=SNAPSHOT_DIGEST,
                    clock=scan_clock,
                    start_async=False,
                )
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal(
                            "contract-operator",
                            "contract-token",
                            frozenset(
                                {
                                    ApiPermission.READ,
                                    ApiPermission.SUBMIT_DRY_RUN,
                                    ApiPermission.MANAGE_MANUAL_ORGANIZE,
                                    ApiPermission.CANCEL_JOB,
                                }
                            ),
                        ),
                    ),
                    system_status=build_configuration_snapshot(configuration),
                    file_index=index,
                    configuration_snapshot_id=SNAPSHOT_ID,
                    configuration_snapshot_digest=SNAPSHOT_DIGEST,
                    manual_intent_service=intents,
                    manual_preview_service=previews,
                    manual_scan_service=scans,
                )
                yield SimpleNamespace(
                    api=api,
                    repository=repository,
                    scans=scans,
                    record=record,
                    source=source,
                    target=target,
                    source_root=source_root,
                    target_root=target_root,
                )
            finally:
                repository.close()

    def _capture(self, value) -> dict[str, object]:
        api = value.api
        file_id = value.record.file_id

        status, action_matrix = _request(
            api,
            "/api/v1/operations/manual-actions",
            query=f"scopeKind=file&fileId={file_id}&resourceLibraryId=library",
        )
        self.assertEqual(200, status)
        status, discovery_matrix = _request(
            api,
            "/api/v1/operations/manual-actions",
            query="scopeKind=resourceLibrary",
        )
        self.assertEqual(200, status)

        status, scan_admission = _request(
            api,
            "/api/v1/operations/scans",
            method="POST",
            body={
                "scopeKind": "file",
                "fileId": file_id,
                "resourceLibraryId": "library",
                "mode": "incremental",
            },
        )
        self.assertEqual(202, status)
        # Drive the admitted discovery deterministically instead of racing a worker thread.
        value.scans.run(scan_admission["taskId"])
        status, scan_detail = _request(
            api,
            f"/api/v1/operations/scans/{scan_admission['taskId']}",
            query="itemLimit=1",
        )
        self.assertEqual(200, status)

        # A ResourceLibrary-scoped Scan of the two indexed sources exercises the
        # deterministic paging window (one item per page with a next cursor).
        status, scan_library_admission = _request(
            api,
            "/api/v1/operations/scans",
            method="POST",
            body={
                "scopeKind": "resourceLibrary",
                "resourceLibraryId": "library",
                "mode": "full",
            },
        )
        self.assertEqual(202, status)
        value.scans.run(scan_library_admission["taskId"])
        status, scan_library_detail = _request(
            api,
            f"/api/v1/operations/scans/{scan_library_admission['taskId']}",
            query="itemLimit=1",
        )
        self.assertEqual(200, status)
        # Which sibling source lands on one page window depends on the durable
        # per-item ordering (created_at, item_id) produced by concurrent
        # discovery, which is not part of the API contract. The fixture keeps
        # the real page-window shape, counts and cursors but replaces the
        # page-window source label with a canonical placeholder so the golden
        # comparison is reproducible; the exact-file document below still
        # carries the real, deterministic operator-facing source identity.
        scan_library_detail["items"] = [
            {**item, "sourcePath": "<page-item-path>"} for item in scan_library_detail["items"]
        ]

        status, preview_admission = _request(
            api,
            "/api/v1/operations/previews",
            method="POST",
            body={
                "scopeKind": "file",
                "fileId": file_id,
                "resourceLibraryId": "library",
            },
        )
        self.assertEqual(201, status)
        preview_id = preview_admission["previewId"]
        status, preview_detail = _request(api, f"/api/v1/operations/previews/{preview_id}")
        self.assertEqual(200, status)
        status, preview_list = _request(
            api,
            "/api/v1/operations/previews",
            query=f"scopeKind=file&scopeId={file_id}",
        )
        self.assertEqual(200, status)

        return {
            "actionMatrix": action_matrix,
            "resourceLibraryDiscovery": discovery_matrix,
            "scanAdmission": scan_admission,
            "scanDetail": scan_detail,
            "scanLibraryDetail": scan_library_detail,
            "previewAdmission": preview_admission,
            "previewDetail": preview_detail,
            "previewList": preview_list,
        }

    def test_real_api_documents_match_the_frontend_fixture(self) -> None:
        with self.fixture() as value:
            captured = _canonical(self._capture(value))
            # Preview is zero-mutation: the adapter raises on any mutating call.
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            self.assertEqual([], list(value.target_root.rglob("*")))
            self.assertTrue(Path(value.source_root, "One.2001.mkv").exists())

        if os.environ.get("MEDIAFLOW_UPDATE_FIXTURES") == "1":
            FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
            FIXTURE_PATH.write_text(
                json.dumps(captured, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            # The fixture is a frontend asset, so keep it in the frontend's own
            # Prettier style; the JSON semantics this module asserts are
            # formatting-independent.
            if shutil.which("npx") is not None:
                subprocess.run(
                    ["npx", "prettier", "--write", str(FIXTURE_PATH)],
                    cwd=REPOSITORY_ROOT / "web",
                    check=False,
                    capture_output=True,
                )
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(fixture, captured)

    def test_real_api_documents_carry_no_forbidden_evidence(self) -> None:
        with self.fixture() as value:
            captured = self._capture(value)
            serialized = json.dumps(captured, sort_keys=True)
        for shape in _FORBIDDEN_SUBSTRINGS:
            self.assertNotIn(shape, serialized)
        self.assertIsNone(_DIGEST_SHAPE.search(serialized))
        # The recognizable operator-facing evidence is preserved.
        self.assertIn("One.2001.mkv", serialized)
        scan_detail = captured["scanDetail"]
        self.assertEqual("completed", scan_detail["status"])
        self.assertTrue(scan_detail["items"])
        self.assertEqual("incremental", scan_detail["mode"])
        self.assertIs(scan_detail["actions"]["cancel"]["available"], False)
        paged = captured["scanLibraryDetail"]
        self.assertEqual("resourceLibrary", paged["scopeKind"])
        self.assertEqual(1, paged["itemLimit"])
        self.assertEqual(1, len(paged["items"]))
        self.assertIs(paged["itemsTruncated"], True)
        self.assertIsInstance(paged["nextItemCursor"], str)
        self.assertIs(paged["actions"]["cancel"]["available"], False)
        preview_detail = captured["previewDetail"]
        self.assertTrue(preview_detail["zeroMutation"])
        self.assertEqual("file", preview_detail["scope"]["scopeKind"])
        plan = preview_detail["items"][0]["plan"]
        self.assertEqual("A", plan["recognitionType"])
        self.assertEqual("Anime/One (2001)/One (2001).mkv", plan["destination"]["relativePath"])
        self.assertEqual("target", plan["destination"]["storageId"])

    def test_resource_library_discovery_offers_no_action_without_a_selection(self) -> None:
        with self.fixture() as value:
            status, matrix = _request(
                value.api,
                "/api/v1/operations/manual-actions",
                query="scopeKind=resourceLibrary",
            )
        self.assertEqual(200, status)
        self.assertTrue(matrix["selectionRequired"])
        self.assertIsNone(matrix["scopeId"])
        self.assertFalse(matrix["actions"]["scan"]["available"])
        self.assertFalse(matrix["actions"]["preview"]["available"])
        self.assertEqual(
            ["library"],
            [item["resourceLibraryId"] for item in matrix["resourceLibraries"]],
        )
        self.assertTrue(matrix["resourceLibraries"][0]["enabled"])
        self.assertEqual(["full", "incremental"], matrix["actions"]["scan"]["modes"])

    def test_unknown_scope_kind_fails_closed(self) -> None:
        with self.fixture() as value:
            status, body = _request(
                value.api,
                "/api/v1/operations/manual-actions",
                query="scopeKind=host_path",
            )
        self.assertEqual(400, status)
        self.assertEqual("invalid_request", body["error"]["code"])


if __name__ == "__main__":
    unittest.main()
