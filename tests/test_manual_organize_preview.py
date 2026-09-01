from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.strategy_test import SyntheticMetadataProvider
from mediaflow.domain.file_catalog import FileReviewLink
from mediaflow.domain.library import MediaLibrary, ResourceLibrary
from mediaflow.domain.manual_organize import (
    ManualConfigurationSnapshot,
    ManualPolicyOption,
    ManualRecognitionOption,
)
from mediaflow.domain.manual_organize_preview import (
    MAX_MANUAL_PREVIEW_PLAN_BYTES,
    ManualPreviewConflict,
    ManualPreviewItemStatus,
    ManualPreviewStatus,
)
from mediaflow.domain.metadata import (
    MediaCandidate,
    MediaType,
    MetadataError,
    MetadataErrorCode,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.storage import StorageCapabilities
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

SNAPSHOT_ID = "active-1"
SNAPSHOT_DIGEST = "a" * 64


def manual_snapshot() -> ManualConfigurationSnapshot:
    return ManualConfigurationSnapshot(
        SNAPSHOT_ID,
        SNAPSHOT_DIGEST,
        (
            ManualRecognitionOption("A", "Movie", "", "type-A", "A", "A", "A", "A"),
            ManualRecognitionOption("B", "TV", "", "type-B", "B", "B", "B", "B"),
            ManualRecognitionOption("C", "Special", "", "type-C", "C", "A", "A", "A"),
        ),
        (
            ManualPolicyOption("A", "Movie metadata", True, "tmdb", "movie"),
            ManualPolicyOption("B", "TV metadata", True, "tmdb", "tv"),
            ManualPolicyOption("C", "Special metadata", True, "tmdb", "movie"),
        ),
        (
            ManualPolicyOption("A", "Movie naming", True, media_type="movie"),
            ManualPolicyOption("B", "TV naming", True, media_type="tv"),
        ),
        (
            ManualPolicyOption("A", "Movie classification"),
            ManualPolicyOption("B", "TV classification"),
        ),
        (
            ManualPolicyOption("A", "Move", True, operation="move", conflict_strategy="manual"),
            ManualPolicyOption("B", "Copy", True, operation="copy", conflict_strategy="skip"),
        ),
    )


class MutationSpyStorage:
    def __init__(self, storage) -> None:
        self.storage = storage
        self.calls: list[str] = []

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
        return StorageCapabilities(
            can_move=True,
            can_copy=True,
            can_delete=True,
            can_hard_link=True,
            can_soft_link=True,
        )

    def list(self, path):
        return self.storage.list(path)

    def stat(self, path):
        return self.storage.stat(path)

    def exists(self, path):
        return self.storage.exists(path)

    def read(self, path):
        return self.storage.read(path)

    def _mutate(self, operation, *args, **kwargs):
        self.calls.append(operation)
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


class FailingMetadataProvider(SyntheticMetadataProvider):
    def search_movie(self, query, policy=None, **kwargs):
        raise MetadataError(
            MetadataErrorCode.PROVIDER_UNAVAILABLE,
            "apiKey=preview-secret provider request failed",
        )


class ManualOrganizePreviewTests(unittest.TestCase):
    def _fixture(self, source_names: tuple[str, ...]):
        directory = tempfile.TemporaryDirectory()
        target_directory = tempfile.TemporaryDirectory()
        source_root = Path(directory.name)
        target_root = Path(target_directory.name)
        for name in source_names:
            Path(source_root, name).write_bytes(b"x" * 123)

        database = source_root / "runtime.sqlite3"
        index = InMemoryFileIndexRepository()
        index.batch_upsert(
            tuple(
                file_record(
                    name.split(".", 1)[0].lower(),
                    "source",
                    "library",
                    name,
                )
                for name in source_names
            )
        )
        configuration = RuntimeConfiguration(
            development_strategy_configuration(),
            (
                StorageDefinition("source", "local", str(source_root), "Source"),
                StorageDefinition("target", "local", str(target_root), "Target"),
            ),
            (ResourceLibrary("library", "Library", "source", ""),),
            (),
            (
                MediaLibrary("movies", "Movies", "target", "Movies"),
                MediaLibrary("tv", "TV", "target", "TV"),
            ),
            str(source_root / "history.jsonl"),
            str(database),
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
        return (
            directory,
            target_directory,
            database,
            source_root,
            target_root,
            index,
            configuration,
            provider,
        )

    @staticmethod
    def _services(
        repository,
        index,
        configuration,
        provider,
        source_root,
        target_root,
    ):
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
        source = MutationSpyStorage(LocalStorage("source", source_root))
        target = MutationSpyStorage(LocalStorage("target", target_root))
        previews = ManualOrganizePreviewService(
            repository,
            intents,
            configuration=configuration,
            providers=MetadataProviderRegistry((provider,)),
            storages={"source": source, "target": target},
        )
        return catalog, intents, previews, source, target

    def test_single_preview_persists_exact_type_c_plan_and_reloads_without_mutation(self):
        fixture = self._fixture(("One.2001.mkv",))
        (
            directory,
            target_directory,
            database,
            source_root,
            target_root,
            index,
            configuration,
            provider,
        ) = fixture
        try:
            with SQLiteTaskRepository(database) as repository:
                _, intents, previews, source, target = self._services(
                    repository, index, configuration, provider, source_root, target_root
                )
                intent = intents.create(["one"], actor="operator")
                intent = intents.update_choice(
                    intent.intent_id,
                    intent.items[0].item_id,
                    {
                        "recognitionTypeId": "C",
                        "namingPolicyId": "A",
                        "classificationPolicyId": "A",
                        "organizePolicyId": "A",
                    },
                    expected_version=1,
                    actor="operator",
                )
                preview = previews.create(
                    intent.intent_id,
                    expected_version=intent.version,
                    expected_item_versions={intent.items[0].item_id: intent.items[0].version},
                    snapshot_id=SNAPSHOT_ID,
                    snapshot_digest=SNAPSHOT_DIGEST,
                    actor="operator",
                )
                self.assertEqual(ManualPreviewStatus.PREVIEWED, preview.status)
                item = preview.items[0]
                self.assertEqual(ManualPreviewItemStatus.PREVIEWED, item.status)
                self.assertEqual("C", item.plan["recognitionType"])
                self.assertEqual("C", item.plan["analysis"]["recognition"]["recognitionTypeId"])
                self.assertEqual("A", item.plan["policies"]["namingPolicyId"])
                self.assertEqual("A", item.plan["policies"]["classificationPolicyId"])
                self.assertEqual("A", item.plan["policies"]["organizePolicyId"])
                self.assertTrue(item.plan["destination"]["path"])
                self.assertTrue(item.plan["zeroMutation"])
                self.assertEqual("not_available_in_this_task", item.execution_state)
                self.assertEqual([], source.calls)
                self.assertEqual([], target.calls)
                self.assertTrue(Path(source_root, "One.2001.mkv").exists())
                self.assertEqual([], list(target_root.rglob("*")))

                reopened = previews.get(preview.preview_id)
                self.assertEqual(preview.document(), reopened.document())
                counts = {
                    name: repository._connection.execute(
                        f"SELECT COUNT(*) AS count FROM {name}"
                    ).fetchone()["count"]
                    for name in ("tasks", "automation_jobs", "execution_authorizations")
                }
                self.assertEqual(
                    {"tasks": 0, "automation_jobs": 0, "execution_authorizations": 0}, counts
                )
            with SQLiteTaskRepository(database) as repository:
                _, intents, previews, _, _ = self._services(
                    repository, index, configuration, provider, source_root, target_root
                )
                self.assertEqual(preview.document(), previews.get(preview.preview_id).document())
                self.assertEqual(intent.document(), intents.get(intent.intent_id).document())
        finally:
            directory.cleanup()
            target_directory.cleanup()

    def test_mixed_batch_keeps_blocker_and_unselected_sibling_independent(self):
        fixture = self._fixture(("One.2001.mkv", "Unknown.2024.mkv"))
        (
            directory,
            target_directory,
            database,
            source_root,
            target_root,
            index,
            configuration,
            provider,
        ) = fixture
        try:
            with SQLiteTaskRepository(database) as repository:
                _, intents, previews, _, _ = self._services(
                    repository, index, configuration, provider, source_root, target_root
                )
                intent = intents.create(["one", "unknown"], actor="operator")
                preview = previews.create(
                    intent.intent_id,
                    expected_version=1,
                    expected_item_versions={item.item_id: item.version for item in intent.items},
                    actor="operator",
                )
                self.assertEqual(
                    [ManualPreviewItemStatus.PREVIEWED, ManualPreviewItemStatus.BLOCKED],
                    [item.status for item in preview.items],
                )
                self.assertIn("metadata", preview.items[1].next_action.lower())
                first_id = intent.items[0].item_id
                refreshed = previews.create(
                    intent.intent_id,
                    [first_id],
                    expected_version=1,
                    expected_item_versions={first_id: 1},
                    actor="operator",
                )
                self.assertEqual((intent.items[1].item_id,), refreshed.unselected_item_ids)
                self.assertEqual(preview.preview_id, refreshed.previous_preview_id)
                historical = repository.get_manual_preview(preview.preview_id)
                self.assertEqual(ManualPreviewStatus.STALE, historical.status)
                self.assertFalse(historical.current)
                self.assertEqual(ManualPreviewItemStatus.STALE, historical.items[0].status)
                self.assertFalse(historical.items[0].current)
                self.assertEqual(ManualPreviewItemStatus.BLOCKED, historical.items[1].status)
                self.assertTrue(historical.items[1].current)
        finally:
            directory.cleanup()
            target_directory.cleanup()

    def test_source_and_choice_changes_mark_preview_stale_without_rebuilding(self):
        fixture = self._fixture(("One.2001.mkv", "Unknown.2024.mkv"))
        (
            directory,
            target_directory,
            database,
            source_root,
            target_root,
            index,
            configuration,
            provider,
        ) = fixture
        try:
            with SQLiteTaskRepository(database) as repository:
                _, intents, previews, _, _ = self._services(
                    repository, index, configuration, provider, source_root, target_root
                )
                intent = intents.create(["one", "unknown"], actor="operator")
                preview = previews.create(
                    intent.intent_id,
                    expected_version=1,
                    expected_item_versions={item.item_id: item.version for item in intent.items},
                    actor="operator",
                )
                changed = replace(
                    file_record("one", "source", "library", "One.2001.mkv"),
                    size=124,
                )
                index.batch_upsert((changed,))
                stale = previews.get(preview.preview_id)
                self.assertEqual(ManualPreviewStatus.STALE, stale.status)
                self.assertFalse(stale.current)
                self.assertTrue(stale.items[0].plan)
                self.assertEqual(ManualPreviewItemStatus.STALE, stale.items[0].status)
                self.assertIn("fresh Preview", stale.items[0].next_action)

                index.batch_upsert((file_record("one", "source", "library", "One.2001.mkv"),))
                intent = intents.get(intent.intent_id)
                updated = intents.update_choice(
                    intent.intent_id,
                    intent.items[0].item_id,
                    {"recognitionTypeId": "C"},
                    expected_version=intent.version,
                    actor="operator",
                )
                self.assertEqual(2, updated.version)
                self.assertEqual(
                    ManualPreviewStatus.STALE,
                    repository.get_manual_preview(preview.preview_id).status,
                )
        finally:
            directory.cleanup()
            target_directory.cleanup()

    def test_snapshot_conflict_publishes_no_preview(self):
        fixture = self._fixture(("One.2001.mkv",))
        (
            directory,
            target_directory,
            database,
            source_root,
            target_root,
            index,
            configuration,
            provider,
        ) = fixture
        try:
            with SQLiteTaskRepository(database) as repository:
                _, intents, previews, _, _ = self._services(
                    repository, index, configuration, provider, source_root, target_root
                )
                intent = intents.create(["one"], actor="operator")
                with self.assertRaisesRegex(ManualPreviewConflict, "pinned configuration snapshot"):
                    previews.create(
                        intent.intent_id,
                        expected_version=1,
                        snapshot_id=SNAPSHOT_ID,
                        snapshot_digest="b" * 64,
                        actor="operator",
                    )
                self.assertIsNone(repository.get_latest_manual_preview(intent.intent_id))
        finally:
            directory.cleanup()
            target_directory.cleanup()

    def test_provider_failure_is_unavailable_and_secret_free(self):
        fixture = self._fixture(("One.2001.mkv",))
        directory, target_directory, database, source_root, target_root, index, configuration, _ = (
            fixture
        )
        try:
            with SQLiteTaskRepository(database) as repository:
                catalog = FileCatalogService(
                    index, ("library",), ("source",), task_repository=repository
                )
                intents = ManualOrganizeIntentService(
                    repository, catalog, configuration_resolver=manual_snapshot
                )
                previews = ManualOrganizePreviewService(
                    repository,
                    intents,
                    configuration=configuration,
                    providers=MetadataProviderRegistry(
                        (
                            FailingMetadataProvider(
                                (),
                            ),
                        )
                    ),
                    storages={
                        "source": MutationSpyStorage(LocalStorage("source", source_root)),
                        "target": MutationSpyStorage(LocalStorage("target", target_root)),
                    },
                )
                intent = intents.create(["one"], actor="operator")
                preview = previews.create(intent.intent_id, expected_version=1, actor="operator")
                item = preview.items[0]
                self.assertEqual(ManualPreviewItemStatus.UNAVAILABLE, item.status)
                self.assertNotIn("preview-secret", item.error)
                self.assertIn("[redacted]", item.error)
        finally:
            directory.cleanup()
            target_directory.cleanup()

    def test_review_and_conflict_evidence_changes_invalidate_current_preview(self):
        fixture = self._fixture(("One.2001.mkv",))
        (
            directory,
            target_directory,
            database,
            source_root,
            target_root,
            index,
            configuration,
            provider,
        ) = fixture
        try:
            with SQLiteTaskRepository(database) as repository:
                _, intents, previews, _, _ = self._services(
                    repository, index, configuration, provider, source_root, target_root
                )
                intent = intents.create(["one"], actor="operator")
                preview = previews.create(intent.intent_id, expected_version=1, actor="operator")
                repository.list_file_review_links = lambda storage_id, path, limit=100: (
                    FileReviewLink("metadata", "review-1", "pending", "task-1", "item-1"),
                )
                stale = previews.get(preview.preview_id)
                self.assertEqual(ManualPreviewStatus.STALE, stale.status)
                fresh = previews.create(intent.intent_id, expected_version=1, actor="operator")
                repository.list_confirmations = lambda limit=None: (
                    SimpleNamespace(
                        source_storage_id="source",
                        source_path="One.2001.mkv",
                        confirmation_id="conflict-1",
                        status="pending",
                        configured_strategy="manual",
                        selected_strategy=None,
                        proposed_destination_path=None,
                        updated_at=None,
                        overwrite_authorized=False,
                    ),
                )
                stale_again = previews.get(fresh.preview_id)
                self.assertEqual(ManualPreviewStatus.STALE, stale_again.status)
        finally:
            directory.cleanup()
            target_directory.cleanup()

    def test_large_provider_identity_is_compacted_to_bounded_plan(self):
        fixture = self._fixture(("One.2001.mkv",))
        directory, target_directory, database, source_root, target_root, index, configuration, _ = (
            fixture
        )
        try:
            huge = "x" * 2048
            provider = SyntheticMetadataProvider(
                (
                    MediaCandidate(
                        "tmdb",
                        "129",
                        MediaType.MOVIE,
                        "One",
                        year=2001,
                        genres=("Animation",) + (huge,) * 64,
                        countries=(huge,) * 64,
                        languages=(huge,) * 64,
                    ),
                )
            )
            with SQLiteTaskRepository(database) as repository:
                _, intents, previews, _, _ = self._services(
                    repository, index, configuration, provider, source_root, target_root
                )
                intent = intents.create(["one"], actor="operator")
                preview = previews.create(intent.intent_id, expected_version=1, actor="operator")
                plan = preview.items[0].plan
                self.assertLessEqual(
                    len(json.dumps(plan, ensure_ascii=False).encode("utf-8")),
                    MAX_MANUAL_PREVIEW_PLAN_BYTES,
                )
                self.assertTrue(plan["truncated"])
        finally:
            directory.cleanup()
            target_directory.cleanup()

    def test_preview_publish_is_atomic_on_duplicate_identity_failure(self):
        fixture = self._fixture(("One.2001.mkv",))
        (
            directory,
            target_directory,
            database,
            source_root,
            target_root,
            index,
            configuration,
            provider,
        ) = fixture
        try:
            with SQLiteTaskRepository(database) as repository:
                _, intents, previews, _, _ = self._services(
                    repository, index, configuration, provider, source_root, target_root
                )
                intent = intents.create(["one"], actor="operator")
                preview = previews.create(intent.intent_id, expected_version=1, actor="operator")
                with self.assertRaises(sqlite3.IntegrityError):
                    repository.create_manual_preview(preview)
                self.assertEqual(
                    preview.document(), repository.get_manual_preview(preview.preview_id).document()
                )
                self.assertEqual(
                    [preview.preview_id],
                    [
                        value.preview_id
                        for value in repository.list_manual_previews(intent.intent_id)
                    ],
                )
        finally:
            directory.cleanup()
            target_directory.cleanup()

    def test_api_rbac_uses_same_projection_and_preview_reads_are_not_audit_mutations(self):
        fixture = self._fixture(("One.2001.mkv",))
        (
            directory,
            target_directory,
            database,
            source_root,
            target_root,
            index,
            configuration,
            provider,
        ) = fixture
        try:
            with SQLiteTaskRepository(database) as repository:
                _, intents, previews, _, _ = self._services(
                    repository, index, configuration, provider, source_root, target_root
                )
                intent = intents.create(["one"], actor="operator")
                viewer = ResolvedApiPrincipal(
                    "viewer", "viewer-token", frozenset({ApiPermission.READ})
                )
                operator = ResolvedApiPrincipal(
                    "operator",
                    "operator-token",
                    frozenset({ApiPermission.READ, ApiPermission.SUBMIT_DRY_RUN}),
                )
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(viewer, operator),
                    file_catalog=intents._file_catalog,
                    manual_intent_service=intents,
                    manual_preview_service=previews,
                )
                body = {
                    "expectedVersion": intent.version,
                    "expectedItemVersions": {intent.items[0].item_id: intent.items[0].version},
                    "snapshotId": intent.snapshot_id,
                    "snapshotDigest": intent.snapshot_digest,
                }
                status, denied = request(
                    api,
                    f"/api/v1/manual-intents/{intent.intent_id}/preview",
                    method="POST",
                    body=body,
                    token="viewer-token",
                )
                self.assertEqual(403, status)
                self.assertEqual("forbidden", denied["error"]["code"])
                status, created = request(
                    api,
                    f"/api/v1/manual-intents/{intent.intent_id}/preview",
                    method="POST",
                    body=body,
                    token="operator-token",
                )
                self.assertEqual(201, status)
                status, loaded = request(
                    api,
                    f"/api/v1/manual-previews/{created['previewId']}",
                    token="viewer-token",
                )
                self.assertEqual(200, status)
                self.assertEqual(created, loaded)
                status, listed = request(
                    api,
                    f"/api/v1/manual-intents/{intent.intent_id}/previews?limit=10",
                    token="viewer-token",
                )
                self.assertEqual(200, status)
                self.assertEqual([created], listed["items"])
                audits_after_post = len(repository.list_security_audit())
                request(
                    api,
                    f"/api/v1/manual-previews/{created['previewId']}",
                    token="viewer-token",
                )
                self.assertEqual(audits_after_post, len(repository.list_security_audit()))
        finally:
            directory.cleanup()
            target_directory.cleanup()

    def test_preview_never_calls_executor_or_storage_mutation(self):
        fixture = self._fixture(("One.2001.mkv",))
        (
            directory,
            target_directory,
            database,
            source_root,
            target_root,
            index,
            configuration,
            provider,
        ) = fixture
        try:
            with SQLiteTaskRepository(database) as repository:
                _, intents, previews, source, target = self._services(
                    repository, index, configuration, provider, source_root, target_root
                )
                intent = intents.create(["one"], actor="operator")
                with patch(
                    "mediaflow.application.strategy_test.OrganizerExecutor.execute",
                    side_effect=AssertionError("Preview called OrganizerExecutor"),
                ):
                    previews.create(intent.intent_id, expected_version=1, actor="operator")
                self.assertEqual([], source.calls)
                self.assertEqual([], target.calls)
        finally:
            directory.cleanup()
            target_directory.cleanup()


def request(api, path: str, *, method: str = "GET", body=None, token: str = "operator-token"):
    payload = json.dumps(body).encode("utf-8") if body is not None else b""
    statuses = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path.split("?", 1)[0],
        "QUERY_STRING": path.split("?", 1)[1] if "?" in path else "",
        "CONTENT_LENGTH": str(len(payload)),
        "wsgi.input": io.BytesIO(payload),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}" if token else "",
    }
    value = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(value)


if __name__ == "__main__":
    unittest.main()
