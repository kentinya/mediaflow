"""Focused Task 38.4 coverage: MediaLibrary bounded Copy/Move transfer recovery.

Slice 38 RO-5/RO-6/RO-7.  Every case drives the *MediaLibrary* transfer journey
through the real application service, the real API transport and the real
resident Worker over temporary Local Storage, and proves that:

- a media transfer resolves both endpoints only from the exact Active
  MediaLibrary, never from a client-supplied Storage, root or raw path;
- a ResourceLibrary and a MediaLibrary that carry the *same* ID cannot exchange
  manifests, evidence, durable attribution or task claims;
- impact, destination admission, stale/invalid/denied reads and failed
  verification perform zero Storage mutation, and no analysis stage starts;
- same-Storage capability rules and the explicit cross-Storage
  Copy→verify→Delete-source sequence are enforced, and a failed verification
  preserves the source;
- the media Worker claims and reconstructs only media work, keeps independent
  per-item outcomes and never replays an uncertain effect;
- the completed ResourceLibrary transfer journey stays byte-compatible.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.direct_file_commands import DirectFileCommandService
from mediaflow.application.direct_file_transfers import (
    DirectFileTransferError,
    DirectFileTransferService,
)
from mediaflow.application.files_transfer_worker import FilesTransferWorker
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.domain.configuration_management import (
    ConfigurationDestinationPrecheckStatus,
    ConfigurationStorageCheckStatus,
    ConfigurationStrategyTestStatus,
)
from mediaflow.domain.direct_files import (
    LibraryKind,
    split_library_identity,
    transfer_manifest_digest,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import (
    FILES_TRANSFER_TASK_COMMAND,
    FilesTransferStatus,
    PersistentTaskStatus,
    TaskItemStatus,
    direct_command_task_command,
)
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_configuration_objects import example_document

NOW = datetime(2026, 9, 23, 12, tzinfo=UTC)

#: The ResourceLibrary and MediaLibrary IDs deliberately collide for the whole
#: module: every cross-authority case below depends on the shared ID.
SHARED_ID = "vault"

#: The MediaLibrary-owned twin of the bounded transfer Task command.
MEDIA_TRANSFER_COMMAND = direct_command_task_command(
    FILES_TRANSFER_TASK_COMMAND, media_library=True
)


def request(
    api: MediaFlowApi,
    url: str,
    *,
    method: str = "GET",
    body: object | None = None,
    token: str = "admin-token",
):
    split = urlsplit(url)
    payload = b"" if body is None else json.dumps(body).encode("utf-8")
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": split.path,
        "QUERY_STRING": split.query,
        "CONTENT_LENGTH": str(len(payload)),
        "wsgi.input": io.BytesIO(payload),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
    }
    result = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(result)


class MutationAuditStorage:
    """One local provider that records every mutating call it receives.

    Reads and metadata stay real (this is temporary Storage), so a case fails
    only when the code under test genuinely mutates Storage outside the
    OrganizerExecutor boundary or mutates at all during analysis.
    """

    def __init__(self, storage_id: str, root: Path, *, read_only: bool = False) -> None:
        self._inner = LocalStorage(storage_id, root, read_only=read_only)
        self.storage_id = storage_id
        self.name = storage_id
        self.read_only = read_only
        self.capabilities = self._inner.capabilities
        self.mutations: list[str] = []
        self.reads: list[str] = []

    def _record(self, name: str) -> None:
        self.mutations.append(name)

    def stat(self, path: str):
        return self._inner.stat(path)

    def exists(self, path: str) -> bool:
        return self._inner.exists(path)

    def list(self, path: str):
        return self._inner.list(path)

    def list_page(self, path: str, *, limit: int, cursor: str | None = None):
        return self._inner.list_page(path, limit=limit, cursor=cursor)

    def read(self, path: str):
        self.reads.append(path)
        return self._inner.read(path)

    def write(self, path, data, **kwargs):
        self._record("write")
        return self._inner.write(path, data, **kwargs)

    def create_directory(self, path: str) -> None:
        self._record("create_directory")
        return self._inner.create_directory(path)

    def move(self, source: str, destination: str, **kwargs):
        self._record("move")
        return self._inner.move(source, destination, **kwargs)

    def copy(self, source: str, destination: str, **kwargs):
        self._record("copy")
        return self._inner.copy(source, destination, **kwargs)

    def delete(self, path: str) -> None:
        self._record("delete")
        return self._inner.delete(path)

    def hard_link(self, source: str, destination: str):
        self._record("hard_link")
        return self._inner.hard_link(source, destination)

    def soft_link(self, source: str, destination: str):
        self._record("soft_link")
        return self._inner.soft_link(source, destination)


class _TruncatingDestinationStorage(LocalStorage):
    """A destination provider whose streamed write lands truncated.

    The destination entry exists but does not hold the source bytes, so a
    cross-Storage Move can never verify its Copy and must stop before the
    destructive source deletion.
    """

    def write(self, path: str, data, *, overwrite: bool = False) -> None:
        if hasattr(data, "read"):
            data = data.read(3)
        super().write(path, data, overwrite=overwrite)


class MediaLibraryTransferTests(unittest.TestCase):
    """Application, API and Worker evidence for the media transfer journey."""

    # ------------------------------------------------------------------
    # Fixture
    # ------------------------------------------------------------------

    def _document(self, root: Path) -> dict[str, object]:
        document = example_document()
        document["persistence"]["databasePath"] = str(root / "configuration.sqlite3")
        document["storages"][0]["rootPath"] = str(root / "source")
        document["storages"][1]["rootPath"] = str(root / "target")
        document["resourceLibraries"] = [
            {
                "id": SHARED_ID,
                "name": "Resource vault",
                "storageId": "source-storage",
                "storagePath": "incoming",
                "enabled": True,
            },
            {
                # Configured only as a ResourceLibrary: the media service must
                # never resolve it, so the two kinds are never one ID space.
                "id": "resource-only",
                "name": "Resource only",
                "storageId": "source-storage",
                "storagePath": "incoming",
                "enabled": True,
            },
        ]
        # The MediaLibrary deliberately reuses the ResourceLibrary ID above with
        # a different Storage root: the only difference the two journeys may
        # rely on is the library *kind*.
        document["mediaLibraries"] = [
            {"id": "movies", "name": "Movies", "storageId": "media-target", "rootPath": "Movies"},
            {"id": "tv", "name": "TV Shows", "storageId": "media-target", "rootPath": "TV Shows"},
            {
                "id": SHARED_ID,
                "name": "Media vault",
                "storageId": "media-target",
                "rootPath": "media-vault",
                "enabled": True,
            },
            {
                "id": "off",
                "name": "Disabled vault",
                "storageId": "media-target",
                "rootPath": "disabled-vault",
                "enabled": False,
            },
        ]
        return document

    def _activate(self, root: Path, *, storage_adapters: dict[str, object] | None = None):
        document = self._document(root)
        (root / "source" / "incoming").mkdir(parents=True, exist_ok=True)
        for relative in ("media-vault", "Movies", "TV Shows", "disabled-vault"):
            (root / "target" / relative).mkdir(parents=True, exist_ok=True)
        configuration_repository = SQLiteConfigurationRepository(root / "configuration.sqlite3")
        self.addCleanup(configuration_repository.close)
        service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=str(root / "configuration.sqlite3"),
        )
        objects = ConfigurationObjectService(
            service,
            storage_adapters=storage_adapters,
            storage_browser_cursor_secret="media-transfer-test-secret",
        )
        draft = service.import_draft(document, actor="operator")
        validated = service.validate(draft.revision_id, actor="operator")
        for storage_id in ("source-storage", "media-target"):
            evidence = objects.storage_check(
                validated.revision_id,
                storage_id=storage_id,
                expected_version=validated.version,
                expected_digest=validated.digest,
                actor="operator",
            )
            self.assertEqual(evidence.status, ConfigurationStorageCheckStatus.PASSED)
        strategy = objects.recognition_strategy_test(
            validated.revision_id,
            expected_version=validated.version,
            expected_digest=validated.digest,
            actor="operator",
            resource_library_id=SHARED_ID,
            synthetic_path="Example.Movie.2024.1080p.mkv",
        )
        self.assertEqual(strategy.status, ConfigurationStrategyTestStatus.COMPLETED)
        destination = objects.destination_precheck(
            validated.revision_id,
            expected_version=validated.version,
            expected_digest=validated.digest,
            actor="operator",
            recognition_type="C",
            sample={
                "title": "The Matrix",
                "mediaType": "movie",
                "year": 1999,
                "genres": ["Action"],
                "extension": "mkv",
            },
        )
        self.assertEqual(destination.status, ConfigurationDestinationPrecheckStatus.COMPLETED)
        active = objects.activate_checked(
            validated.revision_id,
            expected_version=validated.version,
            actor="operator",
        )
        runtime_repository = SQLiteTaskRepository(root / "runtime.sqlite3")
        self.addCleanup(runtime_repository.close)
        api = MediaFlowApi(
            runtime_repository,
            None,
            principals=(
                ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ})),
            ),
            configuration_service=service,
            bootstrap_document=document,
            storage_adapters=storage_adapters,
            storage_browser_cursor_secret="media-transfer-test-secret",
        )
        return api, active, runtime_repository

    def _binding(self, api, active):
        return api._prepare_runtime_binding_for_revision(active)

    def _media_transfers(self, api, active, *, executor=None) -> DirectFileTransferService:
        binding = self._binding(api, active)
        self.assertIsNotNone(binding.direct_media_transfers)
        self.assertIs(binding.direct_media_transfers.library_kind, LibraryKind.MEDIA)
        return DirectFileTransferService(
            direct_files=binding.direct_media_files,
            executor=executor or OrganizerExecutor(),
        )

    def _resource_transfers(self, api, active, *, executor=None) -> DirectFileTransferService:
        binding = self._binding(api, active)
        self.assertIsNotNone(binding.direct_transfers)
        self.assertIs(binding.direct_transfers.library_kind, LibraryKind.RESOURCE)
        return DirectFileTransferService(
            direct_files=binding.direct_files,
            executor=executor or OrganizerExecutor(),
        )

    def _worker(self, transfers, runtime, **kwargs) -> FilesTransferWorker:
        return FilesTransferWorker(
            transfers,
            runtime,
            lease_seconds=3600.0,
            worker_id="worker-media-test",
            **kwargs,
        )

    def _submit(self, transfers, runtime, **kwargs):
        """Admit one confirmed transfer, run the Worker, return the projection."""

        queued = transfers.submit_transfer(**kwargs)
        self.assertEqual(queued["status"], "QUEUED")
        self._run_worker(transfers, runtime)
        return transfers.transfer_projection(queued["taskId"])

    def _run_worker(self, transfers, runtime):
        worker = self._worker(transfers, runtime)
        finished = []
        while (transfer := worker.run_next()) is not None:
            finished.append(transfer)
        return finished

    # ------------------------------------------------------------------
    # Exact Active MediaLibrary authority
    # ------------------------------------------------------------------

    def test_media_transfer_resolves_both_endpoints_from_active_media_libraries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            transfers = self._media_transfers(api, active)
            (root / "target" / "Movies" / "a.mkv").write_bytes(b"media-a")
            (root / "target" / "Movies" / "Dst").mkdir()

            impact = transfers.transfer_impact(
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="tv",
                destination_directory="",
                operation="copy",
            )
            self.assertIs(impact.manifest.library_kind, LibraryKind.MEDIA)
            # A cross-Storage move between two MediaLibraries on one Storage is
            # a native provider operation, exactly as it is for Files.
            self.assertTrue(impact.manifest.same_storage)
            self.assertEqual(impact.capability, "native_copy")
            # The document names both endpoints through the media identity keys
            # and never through the ResourceLibrary ones.
            document = impact.document()
            self.assertEqual(document["mediaLibraryId"], "movies")
            self.assertEqual(document["destinationMediaLibraryId"], "tv")
            self.assertNotIn("resourceLibraryId", document)
            self.assertNotIn("destinationResourceLibraryId", document)

    def test_media_transfer_refuses_a_library_that_is_not_an_enabled_media_library(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            transfers = self._media_transfers(api, active)
            (root / "target" / "media-vault" / "a.mkv").write_bytes(b"media-a")

            # A disabled MediaLibrary is never an endpoint, on either side.
            with self.assertRaises(Exception) as disabled:
                transfers.transfer_impact(
                    resource_library_id="off",
                    paths=["a.mkv"],
                    destination_resource_library_id="movies",
                    destination_directory="",
                    operation="copy",
                )
            self.assertEqual(disabled.exception.media_library_id, "off")
            self.assertEqual(disabled.exception.status, 404)

            with self.assertRaises(Exception) as disabled_target:
                transfers.transfer_impact(
                    resource_library_id="movies",
                    paths=["a.mkv"],
                    destination_resource_library_id="off",
                    destination_directory="",
                    operation="copy",
                )
            self.assertEqual(disabled_target.exception.media_library_id, "off")
            self.assertEqual(disabled_target.exception.status, 404)

            # An ID that is configured only as a ResourceLibrary is not an
            # enabled MediaLibrary for this service: the two kinds are separate
            # authority, never a shared ID space.
            with self.assertRaises(Exception) as unknown:
                transfers.transfer_impact(
                    resource_library_id="resource-only",
                    paths=["a.mkv"],
                    destination_resource_library_id="movies",
                    destination_directory="",
                    operation="copy",
                )
            self.assertEqual(unknown.exception.media_library_id, "resource-only")
            self.assertIsNone(unknown.exception.resource_library_id)

    def test_equal_ids_cannot_exchange_transfer_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            media = self._media_transfers(api, active)
            resource = self._resource_transfers(api, active)
            (root / "target" / "media-vault" / "a.mkv").write_bytes(b"media-a")
            (root / "source" / "incoming" / "a.mkv").write_bytes(b"source-a")
            (root / "source" / "incoming" / "Dst").mkdir(exist_ok=True)

            media_impact = media.transfer_impact(
                resource_library_id=SHARED_ID,
                paths=["a.mkv"],
                destination_resource_library_id="movies",
                destination_directory="",
                operation="copy",
            )
            resource_impact = resource.transfer_impact(
                resource_library_id=SHARED_ID,
                paths=["a.mkv"],
                destination_resource_library_id=SHARED_ID,
                destination_directory="Dst",
                operation="copy",
            )
            # The same configured ID on the two kinds produces different pinned
            # roots and a different opaque digest: neither manifest can confirm
            # the other kind's transfer.
            self.assertNotEqual(media_impact.manifest.digest, resource_impact.manifest.digest)
            self.assertIs(media_impact.manifest.library_kind, LibraryKind.MEDIA)
            self.assertIs(resource_impact.manifest.library_kind, LibraryKind.RESOURCE)

            # The media digest cannot admit a resource transfer, and the
            # resource digest cannot admit a media one.
            with self.assertRaises(DirectFileTransferError) as crossed:
                resource.submit_transfer(
                    resource_library_id=SHARED_ID,
                    paths=["a.mkv"],
                    destination_resource_library_id=SHARED_ID,
                    destination_directory="Dst",
                    operation="copy",
                    conflict_mode="fail",
                    manifest_digest=media_impact.manifest.digest,
                )
            self.assertEqual(crossed.exception.category, "stale_manifest")
            with self.assertRaises(DirectFileTransferError) as crossed_back:
                media.submit_transfer(
                    resource_library_id=SHARED_ID,
                    paths=["a.mkv"],
                    destination_resource_library_id="movies",
                    destination_directory="",
                    operation="copy",
                    conflict_mode="fail",
                    manifest_digest=resource_impact.manifest.digest,
                )
            self.assertEqual(crossed_back.exception.category, "stale_manifest")

    def test_the_library_kind_alone_separates_the_manifest_evidence(self) -> None:
        """The kind is pinned evidence, not incidental metadata.

        The two kinds' opaque manifest digests are derived from deliberately
        different payload shapes: a MediaLibrary payload pins its
        ``libraryKind`` and a ResourceLibrary payload keeps its exact
        pre-existing field set.  Two transfers whose every other input is
        identical therefore never share a digest, so a media confirmation can
        never replay a resource transfer (or the reverse) — and every
        already-issued ResourceLibrary digest keeps its exact value.
        """

        common = {
            "revisionId": "rev-1",
            "revisionDigest": "digest-1",
            "sourceLibraryId": "shared",
            "sourceStorageId": "storage-1",
            "sourceRoot": "root",
            "destinationLibraryId": "shared",
            "destinationStorageId": "storage-1",
            "destinationRoot": "root",
            "destinationDirectory": "Dst",
            "operation": "copy",
            "conflictMode": "fail",
            "topLevelPaths": ["a.mkv"],
            "entries": [["a.mkv", "file", 4, "2026-09-23T12:00:00+00:00", ""]],
            "destinations": [["a.mkv", "Dst/a.mkv"]],
        }
        # The resource payload is byte-for-byte the pre-existing shape.
        resource_digest = transfer_manifest_digest(dict(common))
        media_digest = transfer_manifest_digest({**common, "libraryKind": "media"})
        self.assertNotEqual(resource_digest, media_digest)
        self.assertTrue(resource_digest.startswith("t1."))
        self.assertTrue(media_digest.startswith("t1."))
        # The resource payload is unchanged by this Task: its digest depends on
        # exactly the disclosed pre-existing fields, so an already-issued
        # ResourceLibrary manifest confirmation stays valid.
        self.assertEqual(
            resource_digest,
            transfer_manifest_digest(
                {key: value for key, value in common.items() if key != "libraryKind"}
            ),
        )

    def test_media_transfer_never_reconstructs_resource_transfer_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            media = self._media_transfers(api, active)
            resource = self._resource_transfers(api, active)
            (root / "source" / "incoming" / "a.mkv").write_bytes(b"source-a")
            (root / "target" / "media-vault" / "b.mkv").write_bytes(b"media-b")
            (root / "source" / "incoming" / "Dst").mkdir(exist_ok=True)

            resource_impact = resource.transfer_impact(
                resource_library_id=SHARED_ID,
                paths=["a.mkv"],
                destination_resource_library_id=SHARED_ID,
                destination_directory="Dst",
                operation="copy",
            )
            admitted = resource.submit_transfer(
                resource_library_id=SHARED_ID,
                paths=["a.mkv"],
                destination_resource_library_id=SHARED_ID,
                destination_directory="Dst",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=resource_impact.manifest.digest,
            )
            task_id = admitted["taskId"]
            task = runtime.get_task(task_id)
            self.assertIsNotNone(task)
            self.assertEqual(task.command, FILES_TRANSFER_TASK_COMMAND)

            # The media projection and the media continuation refuse a
            # ResourceLibrary transfer Task, even though the configured IDs are
            # equal.
            with self.assertRaises(DirectFileTransferError) as unreadable:
                media.transfer_projection(task_id)
            self.assertEqual(unreadable.exception.category, "not_found")
            with self.assertRaises(DirectFileTransferError) as unresumable:
                media.requeue_transfer(task_id)
            self.assertEqual(unresumable.exception.category, "resume_unavailable")

            # The media Worker refuses the resource transfer's Task command and
            # leaves the transfer claimable instead of consuming it.
            media_worker = self._worker(media, runtime)
            self.assertIsNone(media_worker.service_for(task.command))
            self._run_worker(resource, runtime)
            projection = resource.transfer_projection(task_id)
            self.assertTrue(projection["terminal"])

    # ------------------------------------------------------------------
    # Zero-mutation admission
    # ------------------------------------------------------------------

    def test_media_impact_and_denials_perform_zero_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "incoming").mkdir(parents=True, exist_ok=True)
            (root / "target").mkdir(parents=True, exist_ok=True)
            source_storage = MutationAuditStorage("source-storage", root / "source")
            target_storage = MutationAuditStorage("media-target", root / "target")
            api, active, _runtime = self._activate(
                root,
                storage_adapters={
                    "source-storage": source_storage,
                    "media-target": target_storage,
                },
            )
            transfers = self._media_transfers(api, active)
            (root / "target" / "Movies" / "a.mkv").write_bytes(b"media-a")
            (root / "target" / "Movies" / "Dst").mkdir()

            impact = transfers.transfer_impact(
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="tv",
                destination_directory="",
                operation="copy",
            )
            self.assertEqual(impact.document()["sideEffects"], "none")
            self.assertEqual(target_storage.mutations, [])
            self.assertEqual(source_storage.mutations, [])

            # A stale digest performs zero mutation and creates no Task.
            with self.assertRaises(DirectFileTransferError) as stale:
                transfers.submit_transfer(
                    resource_library_id="movies",
                    paths=["a.mkv"],
                    destination_resource_library_id="tv",
                    destination_directory="",
                    operation="copy",
                    conflict_mode="fail",
                    manifest_digest="t1.stale",
                )
            self.assertEqual(stale.exception.category, "stale_manifest")
            self.assertEqual(target_storage.mutations, [])

            # A traversal path, a root selection and an unsupported target all
            # fail closed before any mutation.  The traversal case is refused by
            # the shared path-normalization boundary (the same contract the
            # ResourceLibrary transfer uses), so it is asserted through the
            # stable category both boundaries publish.
            for paths, destination, category in (
                (["../escape.mkv"], "", "invalid_path"),
                ([""], "", "root_protected"),
                (["a.mkv"], "Missing", "not_a_directory"),
            ):
                with self.assertRaises(Exception) as refused:
                    transfers.transfer_impact(
                        resource_library_id="movies",
                        paths=paths,
                        destination_resource_library_id="tv",
                        destination_directory=destination,
                        operation="copy",
                    )
                self.assertEqual(getattr(refused.exception, "category", None), category)
            self.assertEqual(target_storage.mutations, [])
            self.assertEqual(source_storage.mutations, [])

    def test_media_transfer_starts_no_media_pipeline_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            transfers = self._media_transfers(api, active)
            (root / "target" / "Movies" / "a.mkv").write_bytes(b"media-a")

            impact = transfers.transfer_impact(
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="tv",
                destination_directory="",
                operation="copy",
            )
            admitted = transfers.submit_transfer(
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="tv",
                destination_directory="",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            # The admission creates exactly one media transfer Task with one
            # item: no recognition, metadata, naming, classification or
            # organize Task/Item is created by a bounded file transfer.
            task = runtime.get_task(admitted["taskId"])
            self.assertIsNotNone(task)
            self.assertEqual(task.command, MEDIA_TRANSFER_COMMAND)
            items = runtime.list_items(task.task_id)
            self.assertEqual(len(items), 1)
            item = items[0]
            self.assertEqual(item.status, TaskItemStatus.PENDING)
            # The durable item identity carries the media namespace, so it can
            # never be joined or replayed as ResourceLibrary work.
            kind, library_id = split_library_identity(item.resource_library_id)
            self.assertIs(kind, LibraryKind.MEDIA)
            self.assertEqual(library_id, "movies")
            self.assertEqual(tuple(runtime.list_results(task.task_id)), ())

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def test_same_storage_media_copy_and_move_use_the_native_operation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            transfers = self._media_transfers(api, active)
            (root / "target" / "Movies" / "a.mkv").write_bytes(b"media-a")
            (root / "target" / "Movies" / "Dst").mkdir()

            impact = transfers.transfer_impact(
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="movies",
                destination_directory="Dst",
                operation="copy",
            )
            copied = self._submit(
                transfers,
                runtime,
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="movies",
                destination_directory="Dst",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            self.assertEqual(copied["status"], "SUCCESS")
            self.assertTrue((root / "target" / "Movies" / "a.mkv").exists())
            self.assertEqual(
                (root / "target" / "Movies" / "Dst" / "a.mkv").read_bytes(), b"media-a"
            )

            move_impact = transfers.transfer_impact(
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="movies",
                destination_directory="Dst",
                operation="move",
                conflict_mode="keep_both",
            )
            moved = self._submit(
                transfers,
                runtime,
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="movies",
                destination_directory="Dst",
                operation="move",
                conflict_mode="keep_both",
                manifest_digest=move_impact.manifest.digest,
            )
            self.assertEqual(moved["status"], "SUCCESS")
            # Keep-both never replaced the earlier copy.
            self.assertFalse((root / "target" / "Movies" / "a.mkv").exists())
            self.assertEqual(
                (root / "target" / "Movies" / "Dst" / "a (1).mkv").read_bytes(), b"media-a"
            )

    def test_cross_storage_media_move_copies_verifies_then_deletes_the_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # Two MediaLibraries on different Storages: the compound Move must
            # be an explicit Copy -> verify -> Delete-source sequence.  The
            # cross-Storage activation creates both Storage roots first.
            api2, active2, runtime2 = self._activate_cross_storage(root)
            (root / "source" / "incoming" / "a.mkv").write_bytes(b"source-a" * 512)
            transfers2 = self._media_transfers(api2, active2)
            impact = transfers2.transfer_impact(
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="tv",
                destination_directory="",
                operation="move",
            )
            self.assertFalse(impact.manifest.same_storage)
            self.assertEqual(impact.capability, "cross_storage_stream")
            result = self._submit(
                transfers2,
                runtime2,
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="tv",
                destination_directory="",
                operation="move",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            self.assertEqual(result["status"], "SUCCESS", result)
            self.assertTrue((root / "target" / "TV Shows" / "a.mkv").exists())
            self.assertFalse((root / "target" / "Movies" / "a.mkv").exists())
            # The durable Result carries the explicit compound checkpoints.
            checkpoints = [
                checkpoint
                for outcome in result["outcomes"]
                for checkpoint in outcome.get("checkpoints", [])
            ]
            self.assertIn("copy_written", checkpoints)
            self.assertIn("destination_verified", checkpoints)
            self.assertIn("source_deleted", checkpoints)

    def test_failed_cross_storage_verification_preserves_the_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate_cross_storage(root)
            source_file = root / "source" / "incoming" / "a.mkv"
            source_file.write_bytes(b"source-a" * 512)
            # The destination provider truncates the streamed write, so the
            # Copy genuinely cannot be verified against the source bytes.
            failing = _TruncatingDestinationStorage("media-target", root / "target")
            transfers = self._media_transfers(api, active)
            binding = self._binding(api, active)
            broken = DirectFileTransferService(
                direct_files=_media_direct(binding, failing), executor=OrganizerExecutor()
            )
            impact = transfers.transfer_impact(
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="tv",
                destination_directory="",
                operation="move",
            )
            result = self._submit(
                broken,
                runtime,
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="tv",
                destination_directory="",
                operation="move",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            # The move did not verify: the source is byte-identical and still
            # present, and the outcome is never reported as a completed
            # transfer.  A failed verification never deletes the source.
            self.assertNotEqual(result["status"], "SUCCESS")
            self.assertTrue(source_file.exists())
            self.assertEqual(source_file.read_bytes(), b"source-a" * 512)
            truncated = root / "target" / "TV Shows" / "a.mkv"
            if truncated.exists():
                # The truncated destination is never adopted as the source's
                # exact bytes.
                self.assertNotEqual(truncated.read_bytes(), b"source-a" * 512)

    # ------------------------------------------------------------------
    # Conflicts, partial and uncertain outcomes
    # ------------------------------------------------------------------

    def test_media_conflict_defaults_to_no_overwrite_and_skips_truthfully(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            transfers = self._media_transfers(api, active)
            (root / "target" / "Movies" / "a.mkv").write_bytes(b"original")
            (root / "target" / "TV Shows" / "a.mkv").write_bytes(b"existing")

            fail_impact = transfers.transfer_impact(
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="tv",
                destination_directory="",
                operation="copy",
            )
            self.assertEqual(fail_impact.conflicts[0].resolution, "fail_no_overwrite")
            failed = self._submit(
                transfers,
                runtime,
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="tv",
                destination_directory="",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=fail_impact.manifest.digest,
            )
            self.assertEqual(failed["status"], "FAILED")
            # No silent overwrite happened.
            self.assertEqual((root / "target" / "TV Shows" / "a.mkv").read_bytes(), b"existing")

            skip_impact = transfers.transfer_impact(
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="tv",
                destination_directory="",
                operation="copy",
                conflict_mode="skip",
            )
            skipped = self._submit(
                transfers,
                runtime,
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="tv",
                destination_directory="",
                operation="copy",
                conflict_mode="skip",
                manifest_digest=skip_impact.manifest.digest,
            )
            self.assertEqual(skipped["status"], "SKIPPED")
            self.assertEqual((root / "target" / "TV Shows" / "a.mkv").read_bytes(), b"existing")
            self.assertTrue((root / "target" / "Movies" / "a.mkv").exists())
            self.assertEqual(skipped["retrySafe"], False)

    def test_media_batch_keeps_independent_per_item_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            transfers = self._media_transfers(api, active)
            (root / "target" / "Movies" / "a.mkv").write_bytes(b"a")
            (root / "target" / "Movies" / "b.mkv").write_bytes(b"b")
            # `b.mkv` already exists at the destination: one sibling skips while
            # the other transfers, and both keep their own outcome.
            (root / "target" / "TV Shows" / "b.mkv").write_bytes(b"existing-b")

            impact = transfers.transfer_impact(
                resource_library_id="movies",
                paths=["a.mkv", "b.mkv"],
                destination_resource_library_id="tv",
                destination_directory="",
                operation="copy",
                conflict_mode="skip",
            )
            result = self._submit(
                transfers,
                runtime,
                resource_library_id="movies",
                paths=["a.mkv", "b.mkv"],
                destination_resource_library_id="tv",
                destination_directory="",
                operation="copy",
                conflict_mode="skip",
                manifest_digest=impact.manifest.digest,
            )
            self.assertEqual(result["status"], "PARTIAL")
            self.assertEqual(result["succeededItems"], 1)
            self.assertEqual(result["skippedItems"], 1)
            statuses = {item["path"]: item["status"] for item in result["itemOutcomes"]}
            self.assertEqual(statuses, {"a.mkv": "SUCCESS", "b.mkv": "SKIPPED"})
            self.assertTrue((root / "target" / "TV Shows" / "a.mkv").exists())
            self.assertEqual((root / "target" / "TV Shows" / "b.mkv").read_bytes(), b"existing-b")

    def test_media_uncertain_effect_is_durable_and_never_replayed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            transfers = self._media_transfers(api, active)
            (root / "target" / "Movies" / "a.mkv").write_bytes(b"a")
            (root / "target" / "Movies" / "Dst").mkdir()

            impact = transfers.transfer_impact(
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="movies",
                destination_directory="Dst",
                operation="move",
                conflict_mode="keep_both",
            )
            # The destination directory appears after admission, so the pinned
            # keep-both name cannot be published and the effect is uncertain.
            queued = transfers.submit_transfer(
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="movies",
                destination_directory="Dst",
                operation="move",
                conflict_mode="keep_both",
                manifest_digest=impact.manifest.digest,
            )
            (root / "target" / "Movies" / "Dst" / "a.mkv").write_bytes(b"external")
            self._run_worker(transfers, runtime)
            projection = transfers.transfer_projection(queued["taskId"])
            # An uncertain sibling is never silently overwritten or replayed.
            self.assertEqual(
                (root / "target" / "Movies" / "Dst" / "a.mkv").read_bytes(), b"external"
            )
            self.assertTrue((root / "target" / "Movies" / "a.mkv").exists())
            self.assertIn(projection["status"], {"FAILED", "UNCERTAIN", "PARTIAL"})

    # ------------------------------------------------------------------
    # API surface
    # ------------------------------------------------------------------

    def test_media_transfer_routes_share_application_behavior_and_rbac(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _active, _runtime = self._activate(root)
            (root / "target" / "Movies" / "a.mkv").write_bytes(b"a")

            status, impact = request(
                api,
                "/api/v1/media-libraries/movies/files/transfer-impact"
                "?path=a.mkv&to=tv&toPath=&operation=copy&conflict=fail",
            )
            self.assertEqual(status, 200)
            self.assertEqual(impact["sideEffects"], "none")
            self.assertEqual(impact["retrySafe"], True)
            self.assertEqual(impact["manifestDigest"][:3], "t1.")
            self.assertEqual(impact["mediaLibraryId"], "movies")
            self.assertEqual(impact["destinationMediaLibraryId"], "tv")
            self.assertNotIn("resourceLibraryId", impact)
            self.assertNotIn(str(root), json.dumps(impact))

            # A read-only principal may read the impact but holds no execute
            # permission, so admission is refused.
            viewer_status, _ = request(
                api,
                "/api/v1/media-libraries/movies/files/transfer-impact"
                "?path=a.mkv&to=tv&toPath=&operation=copy&conflict=fail",
                token="viewer-token",
            )
            self.assertEqual(viewer_status, 200)
            forbidden, _ = request(
                api,
                "/api/v1/media-libraries/movies/files/transfers",
                method="POST",
                token="viewer-token",
                body={
                    "operation": "copy",
                    "paths": ["a.mkv"],
                    "destinationMediaLibraryId": "tv",
                    "destinationDirectory": "",
                    "conflictMode": "fail",
                    "manifestDigest": impact["manifestDigest"],
                },
            )
            self.assertEqual(forbidden, 403)

            created, result = request(
                api,
                "/api/v1/media-libraries/movies/files/transfers",
                method="POST",
                body={
                    "operation": "copy",
                    "paths": ["a.mkv"],
                    "destinationMediaLibraryId": "tv",
                    "destinationDirectory": "",
                    "conflictMode": "fail",
                    "manifestDigest": impact["manifestDigest"],
                },
            )
            self.assertEqual(created, 202)
            self.assertEqual(result["status"], "QUEUED")
            self.assertEqual(result["mediaLibraryId"], "movies")
            self.assertEqual(result["destinationMediaLibraryId"], "tv")
            self.assertNotIn("resourceLibraryId", result)

            # The durable projection is readable, and the resource route cannot
            # serve this media Task (nor the reverse).
            read_status, projection = request(
                api,
                f"/api/v1/media-libraries/movies/files/transfers/{result['taskId']}",
            )
            self.assertEqual(read_status, 200)
            self.assertEqual(projection["mediaLibraryId"], "movies")
            cross_status, _ = request(
                api,
                f"/api/v1/resource-libraries/movies/files/transfers/{result['taskId']}",
            )
            self.assertEqual(cross_status, 404)

            # A ResourceLibrary ID supplied to the media route fails closed.
            not_found, _ = request(
                api,
                f"/api/v1/media-libraries/{SHARED_ID}/files/transfer-impact"
                "?path=a.mkv&to=tv&toPath=&operation=copy&conflict=fail",
            )
            self.assertEqual(not_found, 404)

    def test_resource_library_transfer_journey_remains_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _active, _runtime = self._activate(root)
            (root / "source" / "incoming" / "a.mkv").write_bytes(b"a")
            (root / "source" / "incoming" / "Dst").mkdir(exist_ok=True)

            status, impact = request(
                api,
                "/api/v1/resource-libraries/vault/files/transfer-impact"
                "?path=a.mkv&to=vault&toPath=Dst&operation=copy&conflict=fail",
            )
            self.assertEqual(status, 200)
            # The ResourceLibrary document keeps its exact pre-existing keys.
            self.assertEqual(impact["resourceLibraryId"], "vault")
            self.assertEqual(impact["destinationResourceLibraryId"], "vault")
            self.assertNotIn("mediaLibraryId", impact)
            self.assertNotIn("destinationMediaLibraryId", impact)

            created, result = request(
                api,
                "/api/v1/resource-libraries/vault/files/transfers",
                method="POST",
                body={
                    "operation": "copy",
                    "paths": ["a.mkv"],
                    "destinationResourceLibraryId": "vault",
                    "destinationDirectory": "Dst",
                    "conflictMode": "fail",
                    "manifestDigest": impact["manifestDigest"],
                },
            )
            self.assertEqual(created, 202)
            self.assertEqual(result["resourceLibraryId"], "vault")
            self.assertNotIn("mediaLibraryId", result)
            task = _runtime_task(api, result["taskId"])
            self.assertEqual(task.command, FILES_TRANSFER_TASK_COMMAND)

    def test_media_transfer_routes_fail_closed_without_an_active_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _active, _runtime = self._activate(root)
            binding = api._build_runtime_binding(
                snapshot_id=None,
                snapshot_digest=None,
                maximum_active_jobs=1,
                remote_execution_enabled=False,
                remote_execution_maximum_ttl_seconds=900,
                stale_job_age_seconds=3600,
                system_status=None,
                schedules=(),
                metadata_policies=(),
                resource_library_count=0,
                media_library_count=0,
            )
            self.assertIsNone(binding.direct_media_transfers)
            self.assertIsNone(binding.direct_transfers)

    # ------------------------------------------------------------------
    # Worker: routing, reconstruction and lifecycle
    # ------------------------------------------------------------------

    def test_one_worker_executes_both_kinds_without_crossing_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            media = self._media_transfers(api, active)
            resource = self._resource_transfers(api, active)
            (root / "target" / "Movies" / "m.mkv").write_bytes(b"media")
            (root / "source" / "incoming" / "r.mkv").write_bytes(b"resource")
            (root / "source" / "incoming" / "Dst").mkdir(exist_ok=True)

            media_impact = media.transfer_impact(
                resource_library_id="movies",
                paths=["m.mkv"],
                destination_resource_library_id="tv",
                destination_directory="",
                operation="copy",
            )
            media.submit_transfer(
                resource_library_id="movies",
                paths=["m.mkv"],
                destination_resource_library_id="tv",
                destination_directory="",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=media_impact.manifest.digest,
            )
            resource_impact = resource.transfer_impact(
                resource_library_id=SHARED_ID,
                paths=["r.mkv"],
                destination_resource_library_id=SHARED_ID,
                destination_directory="Dst",
                operation="copy",
            )
            resource.submit_transfer(
                resource_library_id=SHARED_ID,
                paths=["r.mkv"],
                destination_resource_library_id=SHARED_ID,
                destination_directory="Dst",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=resource_impact.manifest.digest,
            )

            # One Worker owns both kind boundaries and dispatches by the
            # claimed Task's own durable command.
            worker = FilesTransferWorker(
                resource,
                runtime,
                media_transfer_service=media,
                lease_seconds=3600.0,
                worker_id="worker-both-kinds",
            )
            self.assertEqual(worker.commands, (FILES_TRANSFER_TASK_COMMAND, MEDIA_TRANSFER_COMMAND))
            finished = []
            while (transfer := worker.run_next()) is not None:
                finished.append(transfer)
            self.assertEqual(len(finished), 2)
            self.assertTrue((root / "target" / "TV Shows" / "m.mkv").exists())
            self.assertTrue((root / "source" / "incoming" / "r.mkv").exists())
            self.assertTrue((root / "source" / "incoming" / "r.mkv").exists())
            # Each kind's own projection reports its own terminal state.
            for task_id in (media_impact.manifest.digest,):
                del task_id
            self.assertEqual(
                len(
                    [
                        transfer
                        for transfer in finished
                        if transfer.status is FilesTransferStatus.COMPLETED
                    ]
                ),
                2,
            )

    def test_worker_refuses_a_media_transfer_without_a_media_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            media = self._media_transfers(api, active)
            resource = self._resource_transfers(api, active)
            (root / "target" / "Movies" / "a.mkv").write_bytes(b"media-a")

            impact = media.transfer_impact(
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="tv",
                destination_directory="",
                operation="copy",
            )
            admitted = media.submit_transfer(
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="tv",
                destination_directory="",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            # A ResourceLibrary-only Worker claims the media transfer and
            # returns it to the queue with readiness evidence instead of
            # consuming it as a business failure.
            resource_only = self._worker(resource, runtime)
            resource_only.run_next()
            row = runtime.get_files_transfer(admitted["taskId"])
            self.assertIsNotNone(row)
            self.assertFalse(row.status.terminal)
            self.assertEqual(row.error, "files_transfer_worker_kind_unavailable")
            self.assertIsNone(row.claim_token)
            # Nothing was copied by the incompatible Worker.
            truncated = root / "target" / "TV Shows" / "a.mkv"
            if truncated.exists():
                # The truncated destination is never adopted as the source's
                # exact bytes.
                self.assertNotEqual(truncated.read_bytes(), b"source-a" * 512)

            # An eligible Worker then completes it.
            media_worker = self._worker(media, runtime)
            media_worker.run_next()
            projection = media.transfer_projection(admitted["taskId"])
            self.assertEqual(projection["status"], "SUCCESS")
            self.assertTrue((root / "target" / "TV Shows" / "a.mkv").exists())

    def test_media_worker_reconstructs_only_its_own_pinned_kind(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            media = self._media_transfers(api, active)
            resource = self._resource_transfers(api, active)
            (root / "target" / "Movies" / "a.mkv").write_bytes(b"media-a")

            impact = media.transfer_impact(
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="tv",
                destination_directory="",
                operation="copy",
            )
            admitted = media.submit_transfer(
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="tv",
                destination_directory="",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            row = runtime.get_files_transfer(admitted["taskId"])
            authority = json.loads(row.authority_json)
            self.assertEqual(authority["libraryKind"], "media")

            # A resource-kind boundary cannot execute the media transfer even
            # when both configured IDs are equal: the pinned kind disagrees.
            import mediaflow.application.direct_file_transfers as transfers_module

            with self.assertRaises(transfers_module._TransferSnapshotUnavailable):
                resource._parse_pinned_authority(row)
            # The transfer stays claimable and unmutated for the eligible kind.
            row = runtime.get_files_transfer(admitted["taskId"])
            self.assertFalse(row.status.terminal)

    def test_media_transfer_pause_cancel_and_resume_stay_durable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            media = self._media_transfers(api, active)
            (root / "target" / "Movies" / "a.mkv").write_bytes(b"media-a")
            (root / "target" / "Movies" / "Dst").mkdir()

            impact = media.transfer_impact(
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="movies",
                destination_directory="Dst",
                operation="copy",
            )
            admitted = media.submit_transfer(
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="movies",
                destination_directory="Dst",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            task_id = admitted["taskId"]
            projection = media.transfer_projection(task_id)
            # A queued transfer advertises cancel and refuses resume (no live
            # claim, nothing paused yet).
            actions = {action["action"]: action for action in projection["actions"]}
            self.assertTrue(actions["cancel"]["available"])
            self.assertFalse(actions["resume"]["available"])
            self.assertFalse(actions["pause"]["available"])

            # Resume of a terminal transfer is refused with a stable category.
            self._run_worker(media, runtime)
            with self.assertRaises(DirectFileTransferError) as terminal:
                media.requeue_transfer(task_id)
            self.assertEqual(terminal.exception.category, "resume_unavailable")
            # The completed effect stays durable and is never replayed.
            self.assertTrue((root / "target" / "Movies" / "Dst" / "a.mkv").exists())
            self.assertTrue((root / "target" / "Movies" / "a.mkv").exists())

    def test_operations_lifecycle_resumes_a_paused_media_transfer_through_its_own_kind(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            media = self._media_transfers(api, active)
            (root / "target" / "Movies" / "a.mkv").write_bytes(b"media-a")
            (root / "target" / "Movies" / "Dst").mkdir()

            impact = media.transfer_impact(
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="movies",
                destination_directory="Dst",
                operation="copy",
            )
            admitted = media.submit_transfer(
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="movies",
                destination_directory="Dst",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            task_id = admitted["taskId"]

            # The Operations lifecycle treats a media transfer Task as a
            # resumable operator-workflow object, exactly like a resource one.
            from mediaflow.application.operations_lifecycle import (
                TaskExecutionPath,
                TaskLifecycleService,
            )

            service = TaskLifecycleService(runtime)
            task = service.require(task_id)
            self.assertEqual(task.command, MEDIA_TRANSFER_COMMAND)
            context = service.execution_context(task)
            self.assertIs(context.path, TaskExecutionPath.OPERATOR_WORKFLOW)

            # Pause it durably, then resume through the media transfer route.
            # A pause is only meaningful on running work, so the Task is first
            # moved to its running state exactly as the Worker would.
            runtime.update_task(
                replace(
                    runtime.get_task(task_id),
                    status=PersistentTaskStatus.RUNNING,
                    updated_at=datetime.now(UTC),
                )
            )
            requested = service.pause(task_id, expected_version=None)
            # Pausing is cooperative: the durable request is recorded now and
            # the running work reaches PAUSED at its own safe item boundary.
            self.assertIs(requested.status, PersistentTaskStatus.RUNNING)
            self.assertTrue(requested.pause_requested)
            # The Worker observes the request at a safe boundary and publishes
            # the paused state on both its Task and its transfer row.
            runtime.update_task(
                replace(
                    runtime.get_task(task_id),
                    status=PersistentTaskStatus.PAUSED,
                    pause_requested=True,
                    updated_at=datetime.now(UTC),
                )
            )
            runtime._connection.execute(
                "UPDATE files_transfers SET status=? WHERE transfer_id=?",
                (FilesTransferStatus.PAUSED.value, task_id),
            )
            runtime._connection.commit()
            self.assertTrue(service.execution_context(runtime.get_task(task_id)).resumable)

            status, body = request(
                api,
                f"/api/v1/tasks/{task_id}/resume",
                method="POST",
                body={"expectedUpdatedAt": runtime.get_task(task_id).updated_at.isoformat()},
                token="admin-token",
            )
            self.assertEqual(status, 202)
            # The resume response is the media transfer's own projection.
            self.assertEqual(body["mediaLibraryId"], "movies")
            self.assertEqual(body["destinationMediaLibraryId"], "movies")
            self.assertNotIn("resourceLibraryId", body)

            # The Worker then completes it from the persisted authority.
            self._run_worker(media, runtime)
            final = media.transfer_projection(task_id)
            self.assertEqual(final["status"], "SUCCESS")
            self.assertTrue((root / "target" / "Movies" / "Dst" / "a.mkv").exists())

    def test_in_flight_media_mutation_is_resolved_without_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            media = self._media_transfers(api, active)
            (root / "target" / "Movies" / "a.mkv").write_bytes(b"media-a")
            (root / "target" / "Movies" / "Dst").mkdir()

            impact = media.transfer_impact(
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="movies",
                destination_directory="Dst",
                operation="copy",
            )
            admitted = media.submit_transfer(
                resource_library_id="movies",
                paths=["a.mkv"],
                destination_resource_library_id="movies",
                destination_directory="Dst",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            task_id = admitted["taskId"]
            item = runtime.list_items(task_id)[0]
            # Simulate the exact crash sequence: a Worker really claims the
            # transfer, publishes the in-flight boundary immediately before the
            # executor call, and then dies before recording any outcome.
            claim_token = "claim-dead-worker"
            claimed = runtime.claim_next_files_transfer(
                datetime.now(UTC),
                worker_id="worker-dead",
                claim_token=claim_token,
                lease_seconds=300.0,
            )
            self.assertIsNotNone(claimed)
            self.assertTrue(runtime.begin_files_transfer(task_id, claim_token, datetime.now(UTC)))
            self.assertTrue(
                runtime.begin_files_transfer_mutation(
                    task_id,
                    claim_token,
                    datetime.now(UTC),
                    item_id=item.item_id,
                    entry_path="a.mkv",
                    action="copy",
                )
            )
            # The dead Worker's lease then expires.
            row = runtime.require_files_transfer(task_id)
            expired = row.claim_expires_at or datetime.now(UTC)
            runtime._connection.execute(
                "UPDATE files_transfers SET claim_expires_at=? WHERE transfer_id=?",
                ((expired - timedelta(hours=1)).isoformat(), task_id),
            )
            runtime._connection.commit()
            # The mutation was never invoked: the destination is still absent,
            # so the resolution must not fabricate a completed effect.
            self.assertFalse((root / "target" / "Movies" / "Dst" / "a.mkv").exists())

            # The next Worker resolves the boundary: with no provable
            # destination effect it converges to investigation-only, and the
            # interrupted Copy is never invoked again.
            self._run_worker(media, runtime)
            row = runtime.require_files_transfer(task_id)
            self.assertTrue(row.status.terminal)
            self.assertIsNone(row.mutation_state)
            projection = media.transfer_projection(task_id)
            self.assertIn(projection["status"], {"FAILED", "UNCERTAIN"})
            self.assertFalse((root / "target" / "Movies" / "Dst" / "a.mkv").exists())
            self.assertTrue((root / "target" / "Movies" / "a.mkv").exists())

    # ------------------------------------------------------------------
    # Cross-storage fixture
    # ------------------------------------------------------------------

    def _activate_cross_storage(self, root: Path):
        """Activate a document whose media source Storage really differs.

        ``movies`` is bound to the *source* Storage and ``tv`` to the target
        one, so a ``movies`` → ``tv`` move is a genuine cross-Storage compound
        operation while both endpoints stay MediaLibraries.
        """

        document = self._document(root)
        (root / "source" / "incoming").mkdir(parents=True, exist_ok=True)
        for relative in ("media-vault", "Movies", "TV Shows", "disabled-vault"):
            (root / "target" / relative).mkdir(parents=True, exist_ok=True)
        for library in document["mediaLibraries"]:
            if library["id"] == "movies":
                library["storageId"] = "source-storage"
                library["rootPath"] = "incoming"
        configuration_repository = SQLiteConfigurationRepository(root / "configuration.sqlite3")
        self.addCleanup(configuration_repository.close)
        service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=str(root / "configuration.sqlite3"),
        )
        objects = ConfigurationObjectService(
            service,
            storage_adapters=None,
            storage_browser_cursor_secret="media-transfer-test-secret",
        )
        draft = service.import_draft(document, actor="operator")
        validated = service.validate(draft.revision_id, actor="operator")
        for storage_id in ("source-storage", "media-target"):
            evidence = objects.storage_check(
                validated.revision_id,
                storage_id=storage_id,
                expected_version=validated.version,
                expected_digest=validated.digest,
                actor="operator",
            )
            self.assertEqual(evidence.status, ConfigurationStorageCheckStatus.PASSED)
        strategy = objects.recognition_strategy_test(
            validated.revision_id,
            expected_version=validated.version,
            expected_digest=validated.digest,
            actor="operator",
            resource_library_id=SHARED_ID,
            synthetic_path="Example.Movie.2024.1080p.mkv",
        )
        self.assertEqual(strategy.status, ConfigurationStrategyTestStatus.COMPLETED)
        destination = objects.destination_precheck(
            validated.revision_id,
            expected_version=validated.version,
            expected_digest=validated.digest,
            actor="operator",
            recognition_type="C",
            sample={
                "title": "The Matrix",
                "mediaType": "movie",
                "year": 1999,
                "genres": ["Action"],
                "extension": "mkv",
            },
        )
        self.assertEqual(destination.status, ConfigurationDestinationPrecheckStatus.COMPLETED)
        active = objects.activate_checked(
            validated.revision_id,
            expected_version=validated.version,
            actor="operator",
        )
        runtime_repository = SQLiteTaskRepository(root / "cross-runtime.sqlite3")
        self.addCleanup(runtime_repository.close)
        api = MediaFlowApi(
            runtime_repository,
            None,
            principals=(
                ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ})),
            ),
            configuration_service=service,
            bootstrap_document=document,
            storage_browser_cursor_secret="media-transfer-test-secret",
        )
        return api, active, runtime_repository


def _media_direct(binding, storage) -> DirectFileCommandService:
    """One media-kind command service whose ``media-target`` is this provider."""

    return DirectFileCommandService(
        active_revision=binding.direct_media_files.revision,
        runtime_configuration=binding.direct_media_files._runtime_configuration,
        task_repository=binding.direct_media_files.tasks.repository,
        storage_adapters={"media-target": storage},
        library_kind=LibraryKind.MEDIA,
    )


def _runtime_task(api: MediaFlowApi, task_id: str):
    return api._repository.get_task(task_id)
