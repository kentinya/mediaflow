from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.scanner import StorageScanner
from mediaflow.application.strategy_test import SyntheticMetadataProvider
from mediaflow.domain.file_lifecycle import OccurrenceState
from mediaflow.domain.library import MediaLibrary, ResourceLibrary
from mediaflow.domain.manual_organize_preview import (
    ManualPreviewConflict,
    ManualPreviewError,
    ManualPreviewItemStatus,
    ManualPreviewStatus,
)
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.scanner import FileScanStatus
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
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
from tests.test_file_catalog import file_record
from tests.test_manual_organize_preview import manual_snapshot

SNAPSHOT_ID = "active-1"
SNAPSHOT_DIGEST = "a" * 64


class MutationSpyStorage:
    def __init__(self, storage) -> None:
        self.storage = storage
        self.mutations: list[str] = []

    @property
    def storage_id(self):
        return self.storage.storage_id

    @property
    def name(self):
        return self.storage.name

    @property
    def read_only(self):
        return self.storage.read_only

    @property
    def capabilities(self):
        return self.storage.capabilities

    def list(self, path):
        return self.storage.list(path)

    def list_page(self, path, *, limit, cursor=None):
        return self.storage.list_page(path, limit=limit, cursor=cursor)

    def stat(self, path):
        return self.storage.stat(path)

    def exists(self, path):
        return self.storage.exists(path)

    def read(self, path):
        return self.storage.read(path)

    def _mutate(self, operation, *args, **kwargs):
        del args, kwargs
        self.mutations.append(operation)
        raise AssertionError(f"Preview attempted Storage mutation: {operation}")

    def write(self, *args, **kwargs):
        return self._mutate("write", *args, **kwargs)

    def create_directory(self, *args, **kwargs):
        return self._mutate("create_directory", *args, **kwargs)

    def move(self, *args, **kwargs):
        return self._mutate("move", *args, **kwargs)

    def copy(self, *args, **kwargs):
        return self._mutate("copy", *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self._mutate("delete", *args, **kwargs)

    def hard_link(self, *args, **kwargs):
        return self._mutate("hard_link", *args, **kwargs)

    def soft_link(self, *args, **kwargs):
        return self._mutate("soft_link", *args, **kwargs)


class FailingProvider(SyntheticMetadataProvider):
    def search_movie(self, query, policy=None, **kwargs):
        del query, policy, kwargs
        from mediaflow.domain.metadata import MetadataError, MetadataErrorCode

        raise MetadataError(
            MetadataErrorCode.PROVIDER_UNAVAILABLE,
            "Authorization: Bearer preview-secret provider unavailable",
        )


def request(api, path: str, *, token: str, method: str = "GET", body=None, query: str = ""):
    statuses: list[str] = []
    raw = json.dumps(body).encode("utf-8") if body is not None else b""
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(raw)),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
        "wsgi.input": io.BytesIO(raw),
    }
    payload = b"".join(api(environ, lambda status, _headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(payload)


class ManualPreviewTests(unittest.TestCase):
    @contextmanager
    def fixture(self, *, target_read_only: bool = False):
        with (
            tempfile.TemporaryDirectory() as source_directory,
            tempfile.TemporaryDirectory() as target_directory,
            tempfile.TemporaryDirectory() as runtime_directory,
        ):
            source_root = Path(source_directory)
            target_root = Path(target_directory)
            Path(source_root, "One.2001.mkv").write_bytes(b"source-media")
            source_storage = LocalStorage("source", source_root)
            target_storage = LocalStorage("target", target_root, read_only=target_read_only)
            source_for_scan = source_storage
            library = ResourceLibrary("library", "Library", "source", "", exclude_rules=())

            def scan_clock():
                return datetime.now(UTC) + timedelta(hours=2)

            index = InMemoryFileIndexRepository()
            result = StorageScanner({"source": source_for_scan}, index, clock=scan_clock).scan(
                library
            )
            self.assertEqual("completed", result.status.value)
            record = index.find_by_path("source", "library", "One.2001.mkv")
            self.assertIsNotNone(record)
            self.assertEqual(OccurrenceState.VERIFIED, record.occurrence_state)
            configuration = RuntimeConfiguration(
                development_strategy_configuration(),
                (
                    StorageDefinition("source", "local", str(source_root), "Source"),
                    StorageDefinition(
                        "target",
                        "local",
                        str(target_root),
                        "Target",
                        target_read_only,
                    ),
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
            yield SimpleNamespace(
                database=Path(runtime_directory, "runtime.sqlite3"),
                source_root=source_root,
                target_root=target_root,
                index=index,
                record=record,
                configuration=configuration,
                provider=provider,
                source=source,
                target=target,
                library=library,
            )

    @staticmethod
    def services(value, repository, *, provider=None, runtime_resolver=None):
        catalog = FileCatalogService(
            value.index,
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
            configuration=value.configuration,
            file_index=value.index,
            runtime_resolver=runtime_resolver,
            providers=MetadataProviderRegistry((provider or value.provider,)),
            storages={"source": value.source, "target": value.target},
        )
        return catalog, intents, previews

    @staticmethod
    def current_request(record, *, scope_kind="file"):
        return {
            "scope_kind": scope_kind,
            "actor": "operator",
            "file_id": record.file_id if scope_kind == "file" else None,
            "resource_library_id": "library",
            "occurrence_id": record.occurrence_id if scope_kind == "file" else None,
            "fingerprint": record.fingerprint if scope_kind == "file" else None,
        }

    @staticmethod
    def work_counts(repository):
        intent_count = repository._connection.execute(
            "SELECT COUNT(*) AS count FROM manual_intents"
        ).fetchone()["count"]
        task_count = len(repository.list_tasks())
        authority_count = repository._connection.execute(
            "SELECT COUNT(*) AS count FROM execution_authorizations"
        ).fetchone()["count"]
        return intent_count, task_count, authority_count

    def test_exact_current_file_preview_is_durable_and_analysis_only(self):
        with self.fixture() as value, SQLiteTaskRepository(value.database) as repository:
            _, intents, previews = self.services(value, repository)
            preview = previews.create_current(**self.current_request(value.record))

            self.assertEqual(ManualPreviewStatus.PREVIEWED, preview.status)
            self.assertEqual("file", preview.source_scope)
            self.assertEqual(value.record.file_id, preview.source_scope_id)
            item = preview.items[0]
            self.assertEqual(ManualPreviewItemStatus.PREVIEWED, item.status)
            self.assertEqual(value.record.occurrence_id, item.source.occurrence_id)
            self.assertEqual(value.record.fingerprint, item.source.fingerprint)
            self.assertEqual(value.record.fingerprint, item.source_fingerprint)
            self.assertEqual("A", item.plan["recognitionType"])
            self.assertEqual("A", item.plan["policies"]["namingPolicyId"])
            self.assertTrue(item.plan["destination"]["path"])
            self.assertTrue(item.plan["zeroMutation"])
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            self.assertTrue(Path(value.source_root, "One.2001.mkv").exists())
            self.assertEqual([], list(value.target_root.rglob("*")))
            self.assertEqual((1, 0, 0), self.work_counts(repository))

            before = preview.document()
            reread = previews.get_readonly(preview.preview_id)
            self.assertEqual(before, reread.document())
            persisted_intent = intents.get(preview.intent_id)
            self.assertEqual(
                value.record.occurrence_id, persisted_intent.items[0].source.occurrence_id
            )

            value.index.batch_upsert((replace(value.record, size=value.record.size + 1),))
            projected = previews.get(preview.preview_id)
            self.assertFalse(projected.current)
            raw = repository._connection.execute(
                "SELECT status, current FROM manual_previews WHERE preview_id=?",
                (preview.preview_id,),
            ).fetchone()
            self.assertEqual("previewed", raw["status"])
            self.assertEqual(1, raw["current"])

    def test_resource_library_selection_is_bounded_and_persists_scope(self):
        with self.fixture() as value, SQLiteTaskRepository(value.database) as repository:
            _, _, previews = self.services(value, repository)
            preview = previews.create_current(
                scope_kind="resource_library",
                actor="operator",
                resource_library_id="library",
            )
            self.assertEqual("resource_library", preview.source_scope)
            self.assertEqual("library", preview.source_scope_id)
            self.assertEqual(1, len(preview.items))
            self.assertEqual("library", preview.document()["scope"]["id"])
            self.assertEqual(
                (preview.preview_id,),
                tuple(
                    item.preview_id for item in previews.list_current("resource_library", "library")
                ),
            )

            extra = tuple(
                replace(
                    file_record(
                        f"extra-{index}",
                        "source",
                        "library",
                        f"extra-{index}.mkv",
                    ),
                    occurrence_id=f"occ-extra-{index}",
                    fingerprint=f"{index + 1:064x}",
                    fingerprint_algorithm="test",
                    fingerprint_evidence={"bounded": True},
                    occurrence_state=OccurrenceState.VERIFIED,
                )
                for index in range(100)
            )
            value.index.batch_upsert(extra)
            with self.assertRaises(ManualPreviewError) as context:
                previews.create_current(
                    scope_kind="resource_library",
                    actor="operator",
                    resource_library_id="library",
                )
            self.assertEqual("selection_over_limit", context.exception.code)
            self.assertEqual(1, len(repository.list_manual_previews(preview.intent_id)))

    def test_resource_library_preview_keeps_unready_sibling_visible(self):
        with self.fixture() as value, SQLiteTaskRepository(value.database) as repository:
            second_path = Path(value.source_root, "Two.2002.mkv")
            second_path.write_bytes(b"second-media")
            StorageScanner(
                {"source": LocalStorage("source", value.source_root)},
                value.index,
                clock=lambda: datetime.now(UTC) + timedelta(hours=2),
            ).scan(value.library)
            second = value.index.find_by_path("source", "library", "Two.2002.mkv")
            self.assertIsNotNone(second)
            value.index.batch_upsert((replace(second, scan_status=FileScanStatus.UNSTABLE),))
            _, _, previews = self.services(value, repository)

            preview = previews.create_current(
                scope_kind="resource_library",
                actor="operator",
                resource_library_id="library",
            )

            self.assertEqual(
                [ManualPreviewItemStatus.PREVIEWED, ManualPreviewItemStatus.STALE],
                [item.status for item in preview.items],
            )
            self.assertEqual(ManualPreviewStatus.PARTIAL, preview.status)
            self.assertEqual("source_admission", preview.items[1].plan["analysis"]["stage"])
            self.assertIn("exact zero-mutation", preview.items[0].next_action.lower())
            self.assertTrue(preview.items[1].next_action)
            self.assertEqual((1, 0, 0), self.work_counts(repository))

    def test_stale_missing_unstable_and_unverified_sources_fail_closed_without_intent(self):
        for mode in ("stale", "missing", "unstable", "unverified"):
            with (
                self.subTest(mode=mode),
                self.fixture() as value,
                SQLiteTaskRepository(value.database) as repository,
            ):
                if mode == "stale":
                    Path(value.source_root, "One.2001.mkv").write_bytes(b"replacement-media")
                elif mode == "missing":
                    Path(value.source_root, "One.2001.mkv").unlink()
                elif mode == "unstable":
                    value.index.batch_upsert(
                        (replace(value.record, scan_status=FileScanStatus.UNSTABLE),)
                    )
                else:
                    value.index.batch_upsert(
                        (
                            replace(
                                value.record,
                                occurrence_id=None,
                                fingerprint=None,
                                fingerprint_algorithm=None,
                                fingerprint_evidence=None,
                                occurrence_state=OccurrenceState.UNVERIFIED,
                            ),
                        )
                    )
                _, _, previews = self.services(value, repository)
                with self.assertRaises(ManualPreviewError) as context:
                    previews.create_current(**self.current_request(value.record))
                self.assertIn(
                    context.exception.code,
                    {"source_stale", "source_missing", "source_not_ready", "source_unverified"},
                )
                self.assertTrue(context.exception.next_action)
                self.assertEqual((0, 0, 0), self.work_counts(repository))

    def test_provider_failure_is_persisted_per_item_redacted_and_creates_no_review_backlog(self):
        with self.fixture() as value, SQLiteTaskRepository(value.database) as repository:
            _, _, previews = self.services(value, repository, provider=FailingProvider(()))
            preview = previews.create_current(**self.current_request(value.record))
            item = preview.items[0]
            self.assertEqual(ManualPreviewItemStatus.UNAVAILABLE, item.status)
            self.assertNotIn("preview-secret", item.error)
            self.assertNotIn("Bearer", item.error)
            self.assertIn("[redacted]", item.error)
            self.assertEqual("metadata", item.document()["stage"])
            self.assertEqual((1, 0, 0), self.work_counts(repository))
            for table in ("metadata_reviews", "recognition_reviews", "classification_reviews"):
                count = repository._connection.execute(
                    f"SELECT COUNT(*) AS count FROM {table}"
                ).fetchone()["count"]
                self.assertEqual(0, count)

    def test_capability_and_conflict_findings_block_independently_without_mutation(self):
        with (
            self.fixture(target_read_only=True) as value,
            SQLiteTaskRepository(value.database) as repository,
        ):
            _, _, previews = self.services(value, repository)
            preview = previews.create_current(**self.current_request(value.record))
            item = preview.items[0]
            self.assertEqual(ManualPreviewItemStatus.BLOCKED, item.status)
            self.assertEqual("capability_gap", item.plan["capabilities"]["verdict"])
            self.assertEqual("capability", item.document()["stage"])
            self.assertTrue(item.next_action)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

        with self.fixture() as value, SQLiteTaskRepository(value.database) as repository:
            target = Path(value.target_root, "Movies/Anime/One (2001)")
            target.mkdir(parents=True)
            (target / "One (2001).mkv").write_bytes(b"existing-target")
            _, _, previews = self.services(value, repository)
            preview = previews.create_current(**self.current_request(value.record))
            item = preview.items[0]
            self.assertEqual(ManualPreviewItemStatus.BLOCKED, item.status)
            self.assertTrue(item.plan["conflicts"])
            self.assertTrue(item.error)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_snapshot_mismatch_and_runtime_failure_publish_nothing(self):
        with self.fixture() as value, SQLiteTaskRepository(value.database) as repository:
            _, _, previews = self.services(value, repository)
            request_value = self.current_request(value.record)
            request_value.update(snapshot_id=SNAPSHOT_ID, snapshot_digest="b" * 64)
            with self.assertRaises(ManualPreviewConflict):
                previews.create_current(**request_value)
            self.assertEqual((0, 0, 0), self.work_counts(repository))

            def unavailable_runtime(*args):
                del args
                raise RuntimeError("private runtime details")

            _, _, broken = self.services(value, repository, runtime_resolver=unavailable_runtime)
            with self.assertRaisesRegex(ManualPreviewError, "unavailable"):
                broken.create_current(**self.current_request(value.record))
            self.assertEqual((0, 0, 0), self.work_counts(repository))

    def test_api_current_preview_routes_are_strict_shared_and_rbac_protected(self):
        operator = ResolvedApiPrincipal(
            "operator",
            "operator-token",
            frozenset({ApiPermission.READ, ApiPermission.MANAGE_MANUAL_ORGANIZE}),
        )
        viewer = ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
        with self.fixture() as value, SQLiteTaskRepository(value.database) as repository:
            catalog, intents, previews = self.services(value, repository)
            api = MediaFlowApi(
                repository,
                None,
                file_index=value.index,
                file_catalog=catalog,
                principals=(operator, viewer),
                manual_intent_service=intents,
                manual_preview_service=previews,
            )
            payload = {
                "scopeKind": "file",
                "fileId": value.record.file_id,
                "resourceLibraryId": "library",
                "occurrenceId": value.record.occurrence_id,
                "fingerprint": value.record.fingerprint,
            }
            status, document = request(
                api,
                "/api/v1/manual-previews",
                token="operator-token",
                method="POST",
                body=payload,
            )
            self.assertEqual(201, status)
            self.assertEqual("file", document["scopeKind"])
            self.assertEqual(
                value.record.occurrence_id, document["items"][0]["source"]["occurrenceId"]
            )
            preview_id = document["previewId"]
            status, reread = request(
                api,
                f"/api/v1/manual-previews/{preview_id}",
                token="viewer-token",
            )
            self.assertEqual(200, status)
            self.assertEqual(document, reread)
            status, listed = request(
                api,
                "/api/v1/manual-previews",
                token="viewer-token",
                query=f"scopeKind=file&scopeId={value.record.file_id}",
            )
            self.assertEqual(200, status)
            self.assertEqual(preview_id, listed["items"][0]["previewId"])
            status, listed = request(
                api,
                f"/api/v1/files/{value.record.file_id}/previews",
                token="viewer-token",
                query="resourceLibraryId=library",
            )
            self.assertEqual(200, status)
            self.assertEqual(preview_id, listed["items"][0]["previewId"])
            status, denied = request(
                api,
                "/api/v1/manual-previews",
                token="viewer-token",
                method="POST",
                body=payload,
            )
            self.assertEqual(403, status)
            self.assertEqual("forbidden", denied["error"]["code"])
            status, invalid = request(
                api,
                "/api/v1/manual-previews",
                token="operator-token",
                method="POST",
                body={**payload, "path": "arbitrary/private/path.mkv"},
            )
            self.assertEqual(400, status)
            self.assertEqual("invalid_request", invalid["error"]["code"])
            status, resource_preview = request(
                api,
                "/api/v1/resource-libraries/library/preview",
                token="operator-token",
                method="POST",
                body={},
            )
            self.assertEqual(201, status)
            self.assertEqual("resource_library", resource_preview["scopeKind"])
            self.assertEqual("library", resource_preview["scopeId"])
