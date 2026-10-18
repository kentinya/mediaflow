"""Focused Task 38.3 coverage: MediaLibrary bounded direct file maintenance.

Slice 38 RO-5/RO-6/RO-7.  Every case here drives the *MediaLibrary* command
journey (Create Folder, Create supported Text File, single-item Rename, bounded
text Open/Edit/Save, Delete) through the real application service and the real
API transport over temporary Local Storage, and proves that:

- the MediaLibrary page resolves its authority only from the exact Active
  MediaLibrary and never from a client-supplied Storage, root or arbitrary path;
- a ResourceLibrary and a MediaLibrary that carry the *same* ID cannot exchange
  command, evidence or confirmation authority;
- every mutation crosses OrganizerExecutor only, and every read, impact,
  evidence, denial and failed admission performs zero Storage mutation and
  creates no durable work;
- durable Task/Result projections name the media library kind, keep per-item
  outcomes independent, and never replay an uncertain mutation;
- the completed ResourceLibrary command journey stays byte-compatible.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.direct_file_commands import DirectFileCommandService
from mediaflow.application.direct_file_transfers import DirectFileTransferService
from mediaflow.application.files_transfer_worker import FilesTransferWorker
from mediaflow.domain.configuration_management import (
    ConfigurationDestinationPrecheckStatus,
    ConfigurationStorageCheckStatus,
    ConfigurationStrategyTestStatus,
)
from mediaflow.domain.direct_files import LibraryKind, entry_version_token
from mediaflow.domain.organizer import ExecutionEffectCertainty, ExecutionStatus
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.runtime_configuration import create_storage_from_definition
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_configuration_objects import example_document

NOW = datetime(2026, 9, 23, 12, tzinfo=UTC)

#: Resource ID and Media ID deliberately collide for the whole module: every
#: cross-authority case below depends on the two kinds sharing an ID.
SHARED_ID = "vault"


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


class _PauseAfterFirstDeleteStorage(MutationAuditStorage):
    """Request a durable Delete Task pause after one MediaLibrary effect."""

    def __init__(self, storage_id: str, root: Path) -> None:
        super().__init__(storage_id, root)
        self.repository: SQLiteTaskRepository | None = None
        self.task_id: str | None = None

    def delete(self, path: str) -> None:
        super().delete(path)
        if self.task_id is not None and self.repository is not None:
            self.repository.request_task_pause(self.task_id, datetime.now(UTC))
            self.task_id = None


class MediaLibraryDirectCommandTests(unittest.TestCase):
    """Application and API evidence for the MediaLibrary command journey."""

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
            }
        ]
        # Same ID as the ResourceLibrary above, a different Storage root: the
        # only difference the two journeys may rely on is the library *kind*.
        document["mediaLibraries"] = [
            # The example classification rules reference these two, so they stay.
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

    def _activate(
        self,
        root: Path,
        *,
        storage_adapters: dict[str, object] | None = None,
    ):
        document = self._document(root)
        (root / "source" / "incoming").mkdir(parents=True, exist_ok=True)
        (root / "target" / "media-vault").mkdir(parents=True, exist_ok=True)
        # The example classification rules target these MediaLibrary roots, so
        # the destination precheck has a real existing directory to resolve.
        (root / "target" / "Movies").mkdir(parents=True, exist_ok=True)
        (root / "target" / "TV Shows").mkdir(parents=True, exist_ok=True)
        configuration_repository = SQLiteConfigurationRepository(root / "configuration.sqlite3")
        self.addCleanup(configuration_repository.close)
        service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=str(root / "configuration.sqlite3"),
        )
        objects = ConfigurationObjectService(
            service,
            storage_adapters=storage_adapters,
            storage_browser_cursor_secret="media-commands-test-secret",
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
            storage_browser_cursor_secret="media-commands-test-secret",
        )
        return api, objects, active, runtime_repository

    @staticmethod
    def _binding(api, active):
        return api._prepare_runtime_binding_for_revision(active)

    def _media_storage(self, root: Path) -> MutationAuditStorage:
        return MutationAuditStorage("media-target", root / "target")

    def _media_service(self, api, active):
        binding = self._binding(api, active)
        service = binding.direct_media_files
        self.assertIsNotNone(service)
        self.assertIs(service.library_kind, LibraryKind.MEDIA)
        return service

    def _run_delete(self, service: DirectFileCommandService, **request) -> dict[str, object]:
        """Drive a confirmed MediaLibrary Delete through the durable Worker."""

        admitted = service.execute_delete(**request)
        return self._run_admitted_delete(service, admitted)

    def _run_admitted_delete(
        self, service: DirectFileCommandService, admitted: dict[str, object]
    ) -> dict[str, object]:
        """Drive an already admitted Delete through the real durable Worker."""

        if admitted.get("taskId") is None or admitted.get("terminal") is True:
            return admitted
        command = str(admitted["taskCommand"])
        transfer_service = DirectFileTransferService(
            direct_files=service, executor=service._executor
        )
        worker = FilesTransferWorker(
            None,
            service._tasks.repository,
            service_factory=lambda selected, _transfer: (
                transfer_service if selected == command else None
            ),
            supported_commands=(command,),
        )
        self.assertIsNotNone(worker.run_next())
        return service.delete_projection(str(admitted["taskId"]))

    def _rename_evidence(self, api, active, library_id: str, path: str, *, media: bool = True):
        service = (
            self._binding(api, active).direct_media_files
            if media
            else self._binding(api, active).direct_files
        )
        document = service.rename_evidence(library_id=library_id, path=path).document()
        return {
            "size": document["size"],
            "modifiedAt": document["modifiedAt"],
            "evidence": document["evidence"],
        }

    def _loaded(self, api, active, library_id: str, path: str, *, media: bool = True):
        service = (
            self._binding(api, active).direct_media_files
            if media
            else self._binding(api, active).direct_files
        )
        return service.read_text(library_id=library_id, path=path).evidence.document()

    # ------------------------------------------------------------------
    # Library authority: the Active MediaLibrary, never a client value
    # ------------------------------------------------------------------

    def test_media_service_resolves_only_active_media_libraries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _runtime = self._activate(root)
            service = self._media_service(api, active)
            # Only enabled MediaLibraries of this kind are resolvable.
            self.assertEqual(sorted(service._libraries), ["movies", "tv", SHARED_ID])
            # A disabled MediaLibrary is not authority.
            with self.assertRaises(Exception) as refused:
                service.create_directory(library_id="off", parent_path="", name="x")
            self.assertEqual(refused.exception.code, "files_direct_media_library_not_found")
            self.assertEqual(refused.exception.status, 404)
            # A ResourceLibrary ID is never resolvable by the media service, even
            # when a MediaLibrary carries the same ID: identity is per kind.
            with self.assertRaises(Exception) as cross:
                service.create_directory(library_id="source", parent_path="", name="x")
            self.assertEqual(cross.exception.code, "files_direct_media_library_not_found")
            # ...and the resource service cannot resolve a media-only ID either.
            resource = self._binding(api, active).direct_files
            self.assertIs(resource.library_kind, LibraryKind.RESOURCE)
            with self.assertRaises(Exception) as other:
                resource.create_directory(library_id="tv", parent_path="", name="x")
            self.assertEqual(other.exception.code, "files_direct_resource_library_not_found")
            # Zero mutation for every refusal above.
            self.assertFalse((root / "target" / "media-vault" / "x").exists())
            self.assertFalse((root / "source" / "incoming" / "x").exists())

    def test_equal_ids_never_exchange_command_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _runtime = self._activate(root)
            media = self._media_service(api, active)
            resource = self._binding(api, active).direct_files
            # Same request ID, same relative path: the two kinds land in their own
            # configured roots and nothing is ever shared.
            media.create_directory(library_id=SHARED_ID, parent_path="", name="Alpha")
            resource.create_directory(library_id=SHARED_ID, parent_path="", name="Alpha")
            self.assertTrue((root / "target" / "media-vault" / "Alpha").is_dir())
            self.assertTrue((root / "source" / "incoming" / "Alpha").is_dir())
            # The media text never appears in the resource library (or vice versa).
            media.create_text(library_id=SHARED_ID, parent_path="", name="media.txt", content="m")
            with self.assertRaises(Exception) as missing:
                resource.read_text(library_id=SHARED_ID, path="media.txt")
            self.assertEqual(missing.exception.code, "files_direct_not_found")

    def test_version_evidence_cannot_cross_library_kind(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            media = self._media_service(api, active)
            (root / "target" / "media-vault" / "notes.txt").write_text("media", encoding="utf-8")
            (root / "source" / "incoming" / "notes.txt").write_text("media", encoding="utf-8")
            # Byte-identical entries at the same relative path in both kinds:
            # only the library kind distinguishes the issued evidence.
            media_evidence = self._rename_evidence(api, active, SHARED_ID, "notes.txt")
            resource_evidence = self._rename_evidence(
                api, active, SHARED_ID, "notes.txt", media=False
            )
            self.assertNotEqual(media_evidence["evidence"], resource_evidence["evidence"])
            tasks_before = len(runtime.list_tasks(limit=100))
            with self.assertRaises(Exception) as refused:
                media.rename(
                    library_id=SHARED_ID,
                    path="notes.txt",
                    name="renamed.txt",
                    expected=resource_evidence,
                )
            self.assertEqual(refused.exception.code, "files_direct_stale_source")
            self.assertEqual(refused.exception.category, "stale_source")
            self.assertFalse((root / "target" / "media-vault" / "renamed.txt").exists())
            self.assertTrue((root / "target" / "media-vault" / "notes.txt").exists())
            with self.assertRaises(Exception) as other:
                self._binding(api, active).direct_files.rename(
                    library_id=SHARED_ID,
                    path="notes.txt",
                    name="renamed.txt",
                    expected=media_evidence,
                )
            self.assertEqual(other.exception.code, "files_direct_stale_source")
            self.assertFalse((root / "source" / "incoming" / "renamed.txt").exists())
            # Every refusal happened at admission: no Task, no mutation.
            self.assertEqual(len(runtime.list_tasks(limit=100)), tasks_before)

    def test_delete_confirmation_cannot_cross_library_kind(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _runtime = self._activate(root)
            media = self._media_service(api, active)
            for base in ("target/media-vault", "source/incoming"):
                (root / base / "same.txt").write_text("identical", encoding="utf-8")
            resource_impact = self._binding(api, active).direct_files.delete_impact(
                library_id=SHARED_ID, paths=["same.txt"]
            )
            media_impact = media.delete_impact(library_id=SHARED_ID, paths=["same.txt"])
            # Identical size, identical path, identical provider shape: the digest
            # still differs because the library kind is part of the confirmed scope.
            self.assertNotEqual(resource_impact.scope_digest, media_impact.scope_digest)
            with self.assertRaises(Exception) as refused:
                self._run_delete(
                    media,
                    library_id=SHARED_ID,
                    paths=["same.txt"],
                    confirmation_digest=resource_impact.scope_digest,
                )
            self.assertEqual(refused.exception.code, "files_direct_stale_confirmation")
            self.assertTrue((root / "target" / "media-vault" / "same.txt").exists())
            self.assertTrue((root / "source" / "incoming" / "same.txt").exists())

    def test_entry_version_token_is_kind_scoped(self) -> None:
        common = {
            "path": "Movie (2020)/Movie.mkv",
            "is_directory": False,
            "size": 10,
            "modified_at": NOW.isoformat(),
            "fingerprint": "inode:1:ctime:2",
        }
        resource = entry_version_token(
            library_kind=LibraryKind.RESOURCE.value, library_id=SHARED_ID, **common
        )
        media = entry_version_token(
            library_kind=LibraryKind.MEDIA.value, library_id=SHARED_ID, **common
        )
        self.assertNotEqual(resource, media)
        self.assertTrue(media.startswith("v1."))

    # ------------------------------------------------------------------
    # The five commands, confined to the MediaLibrary root
    # ------------------------------------------------------------------

    def test_media_commands_complete_confined_to_the_library_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            media = self._media_service(api, active)
            vault = root / "target" / "media-vault"
            created = media.create_directory(library_id=SHARED_ID, parent_path="", name="Movies")
            self.assertEqual(created["status"], "SUCCESS")
            self.assertEqual(created["effectCertainty"], "verified_complete")
            self.assertEqual(created["taskCommand"], "media_files_direct_command")
            self.assertEqual(created["libraryKind"], "media")
            self.assertTrue((vault / "Movies").is_dir())
            text = media.create_text(
                library_id=SHARED_ID,
                parent_path="Movies",
                name="movie.nfo",
                content="<movie/>",
            )
            self.assertEqual(text["status"], "SUCCESS")
            self.assertEqual(text["target"], "Movies/movie.nfo")
            self.assertEqual(
                (vault / "Movies" / "movie.nfo").read_text(encoding="utf-8"), "<movie/>"
            )
            renamed = media.rename(
                library_id=SHARED_ID,
                path="Movies/movie.nfo",
                name="film.nfo",
                expected=self._rename_evidence(api, active, SHARED_ID, "Movies/movie.nfo"),
            )
            self.assertEqual(renamed["status"], "SUCCESS")
            self.assertEqual(renamed["target"], "Movies/film.nfo")
            self.assertFalse((vault / "Movies" / "movie.nfo").exists())
            self.assertTrue((vault / "Movies" / "film.nfo").exists())
            loaded = self._loaded(api, active, SHARED_ID, "Movies/film.nfo")
            saved = media.save_text(
                library_id=SHARED_ID,
                path="Movies/film.nfo",
                content="<film/>",
                expected={"size": loaded["size"], "digest": loaded["digest"]},
            )
            self.assertEqual(saved["status"], "SUCCESS")
            self.assertEqual((vault / "Movies" / "film.nfo").read_text(encoding="utf-8"), "<film/>")
            impact = media.delete_impact(library_id=SHARED_ID, paths=["Movies"])
            deleted = self._run_delete(
                media,
                library_id=SHARED_ID,
                paths=["Movies"],
                confirmation_digest=impact.scope_digest,
            )
            self.assertEqual(deleted["status"], "SUCCESS")
            self.assertEqual(deleted["taskCommand"], "media_files_delete")
            self.assertEqual(
                deleted["knownEffects"],
                [{"path": "Movies", "effect": "deleted", "status": "SUCCESS"}],
            )
            self.assertFalse((vault / "Movies").exists())
            # Durable attribution: media command names and media-namespaced item
            # identity, so no consumer can read this as ResourceLibrary work.
            commands = sorted({task.command for task in runtime.list_tasks(limit=100)})
            self.assertEqual(commands, ["media_files_delete", "media_files_direct_command"])
            items = [
                item
                for task in runtime.list_tasks(limit=100)
                for item in runtime.list_items(task.task_id)
            ]
            self.assertTrue(items)
            self.assertEqual({item.resource_library_id for item in items}, {f"media:{SHARED_ID}"})
            self.assertEqual({item.storage_id for item in items}, {"media-target"})
            # No persisted record carries the configured host root.
            serialized = json.dumps(
                [
                    {
                        "source": item.source_path,
                        "display": item.source_display,
                        "target": item.destination_path,
                    }
                    for item in items
                ]
            )
            self.assertNotIn(str(root), serialized)

    def test_media_delete_readback_pause_and_resume_preserves_completed_items(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target").mkdir()
            storage = _PauseAfterFirstDeleteStorage("media-target", root / "target")
            api, _objects, active, runtime = self._activate(
                root, storage_adapters={"media-target": storage}
            )
            storage.repository = runtime
            media = self._media_service(api, active)
            folder = root / "target" / "media-vault" / "season"
            folder.mkdir()
            for name in ("01.mkv", "02.mkv", "03.mkv"):
                (folder / name).write_text(name, encoding="utf-8")

            impact = media.delete_impact(library_id=SHARED_ID, paths=["season"])
            admitted = media.execute_delete(
                library_id=SHARED_ID,
                paths=["season"],
                confirmation_digest=impact.scope_digest,
            )
            self.assertEqual(admitted["status"], "QUEUED")
            self.assertTrue(folder.exists())
            self.assertEqual(admitted["taskCommand"], "media_files_delete")
            status = request(
                api,
                f"/api/v1/media-libraries/{SHARED_ID}/files/deletes/{admitted['taskId']}",
            )
            self.assertEqual(status[0], 200, status[1])
            self.assertEqual(status[1]["libraryKind"], "media")
            self.assertTrue(status[1]["waitingForWorker"])

            command = str(admitted["taskCommand"])
            transfer_service = DirectFileTransferService(
                direct_files=media, executor=media._executor
            )
            worker = FilesTransferWorker(
                None,
                runtime,
                service_factory=lambda selected, _transfer: (
                    transfer_service if selected == command else None
                ),
                supported_commands=(command,),
            )
            storage.task_id = str(admitted["taskId"])
            self.assertIsNotNone(worker.run_next())
            paused = media.delete_projection(str(admitted["taskId"]))
            self.assertEqual(paused["status"], "PAUSED")
            self.assertEqual(paused["succeededItems"], 1)
            successful_before_resume = {
                item.source_display
                for item in runtime.list_items(str(admitted["taskId"]))
                if item.status.value == "success"
            }
            self.assertEqual(len(successful_before_resume), 1)
            self.assertTrue(folder.exists())

            task = runtime.get_task(str(admitted["taskId"]))
            resumed = request(
                api,
                f"/api/v1/tasks/{task.task_id}/resume",
                method="POST",
                body={"expectedUpdatedAt": task.updated_at.isoformat()},
            )
            self.assertEqual(resumed[0], 202, resumed[1])
            self.assertEqual(resumed[1]["taskStatus"], "pending")
            self.assertIsNotNone(worker.run_next())
            completed = media.delete_projection(str(admitted["taskId"]))
            self.assertEqual(completed["status"], "SUCCESS")
            self.assertFalse(folder.exists())
            successful_after_resume = {
                item.source_display
                for item in runtime.list_items(str(admitted["taskId"]))
                if item.status.value == "success"
            }
            self.assertTrue(successful_before_resume.issubset(successful_after_resume))

    def test_media_mutation_is_executed_only_by_organizer_executor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _runtime = self._activate(root)
            media = self._media_service(api, active)
            storage = self._media_storage(root)
            from mediaflow.application.organizer import OrganizerExecutor

            real_create = OrganizerExecutor.execute_direct_create_directory
            calls: list[str] = []

            def counting_create(executor_self, storage_value, path, **kwargs):
                calls.append(path)
                return real_create(executor_self, storage_value, path, **kwargs)

            with (
                patch.object(DirectFileCommandService, "_open_storage", return_value=storage),
                patch.object(OrganizerExecutor, "execute_direct_create_directory", counting_create),
            ):
                outcome = media.create_directory(
                    library_id=SHARED_ID, parent_path="", name="ViaExecutor"
                )
            self.assertEqual(outcome["status"], "SUCCESS")
            self.assertEqual(calls, ["media-vault/ViaExecutor"])
            # The only recorded provider mutations are the executor's own.
            self.assertEqual(storage.mutations, ["create_directory"])
            self.assertTrue((root / "target" / "media-vault" / "ViaExecutor").is_dir())

    def test_analysis_reads_evidence_and_impact_perform_zero_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            (root / "target" / "media-vault" / "sidecar.srt").write_text("1\n", encoding="utf-8")
            (root / "target" / "media-vault" / "sub").mkdir()
            storage = self._media_storage(root)
            with patch.object(DirectFileCommandService, "_open_storage", return_value=storage):
                media = self._media_service(api, active)
                self.assertEqual(
                    media.read_text(library_id=SHARED_ID, path="sidecar.srt").content, "1\n"
                )
                media.rename_evidence(library_id=SHARED_ID, path="sidecar.srt")
                media.delete_impact(library_id=SHARED_ID, paths=["sub"])
                # Denied and invalid requests are also zero-mutation.
                for attempt in (
                    lambda: media.create_directory(library_id="missing", parent_path="", name="x"),
                    lambda: media.create_directory(
                        library_id=SHARED_ID, parent_path="", name="../out"
                    ),
                    lambda: media.create_text(
                        library_id=SHARED_ID, parent_path="", name="movie.mkv", content="x"
                    ),
                    lambda: media.rename(
                        library_id=SHARED_ID,
                        path="sidecar.srt",
                        name="other.srt",
                        expected={"size": 1, "modifiedAt": NOW.isoformat(), "evidence": "v1.fake"},
                    ),
                    lambda: self._run_delete(
                        media, library_id=SHARED_ID, paths=["sub"], confirmation_digest="stale"
                    ),
                    lambda: media.save_text(
                        library_id=SHARED_ID,
                        path="sidecar.srt",
                        content="2\n",
                        expected={"size": 999, "digest": "0" * 64},
                    ),
                ):
                    with self.assertRaises(Exception):
                        attempt()
            self.assertEqual(storage.mutations, [])
            self.assertTrue(storage.reads)
            self.assertEqual(runtime.list_tasks(limit=100), ())
            self.assertEqual(
                sorted(entry.name for entry in (root / "target" / "media-vault").iterdir()),
                ["sidecar.srt", "sub"],
            )

    # ------------------------------------------------------------------
    # Confinement, capability, type, limit and conflict rules
    # ------------------------------------------------------------------

    def test_paths_and_links_stay_inside_the_media_library_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _runtime = self._activate(root)
            media = self._media_service(api, active)
            for path in ("/etc/passwd", "../outside", "a/../../b", "a\\b"):
                with self.assertRaises(Exception) as refused:
                    media.create_directory(library_id=SHARED_ID, parent_path=path, name="x")
                self.assertIn("invalid_path", refused.exception.category)
                # Pre-existing shared transport behaviour: the same normalization
                # boundary answers both kinds with a bounded 400.
                self.assertEqual(refused.exception.status, 400)
            with self.assertRaises(Exception) as escaped:
                media.delete_impact(library_id=SHARED_ID, paths=["../outside"])
            self.assertEqual(escaped.exception.status, 400)
            self.assertFalse((root / "outside").exists())
            overlap_root = root / "target" / "media-vault" / "overlap"
            (overlap_root / "sub").mkdir(parents=True)
            (overlap_root / "sub" / "file.txt").write_text("keep", encoding="utf-8")
            overlap = media.delete_impact(
                library_id=SHARED_ID,
                paths=["overlap", "overlap/sub", "overlap", "overlap/sub"],
            )
            self.assertEqual(overlap.top_level_paths, ("overlap",))
            self.assertEqual(len(overlap.entries), 3)
            api_overlap = request(
                api,
                f"/api/v1/media-libraries/{SHARED_ID}/files/delete-impact?"
                "path=overlap&path=overlap/sub&path=overlap",
            )
            self.assertEqual(api_overlap[0], 200, api_overlap[1])
            self.assertEqual(api_overlap[1]["topLevelPaths"], ["overlap"])
            admitted_overlap = media.submit_delete(
                library_id=SHARED_ID,
                paths=["overlap", "overlap/sub", "overlap"],
                confirmation_digest=overlap.scope_digest,
            )
            self.assertEqual(admitted_overlap["totalItems"], 3)
            overlap_items = _runtime.list_items(admitted_overlap["taskId"])
            self.assertEqual(len(overlap_items), 3)
            self.assertEqual(
                {item.source_display for item in overlap_items},
                {"overlap", "overlap/sub", "overlap/sub/file.txt"},
            )
            self.assertTrue((overlap_root / "sub" / "file.txt").exists())
            # The library root itself is protected.
            for attempt in (
                lambda: media.delete_impact(library_id=SHARED_ID, paths=[""]),
                lambda: media.rename(
                    library_id=SHARED_ID,
                    path="",
                    name="x",
                    expected={"size": 1, "modifiedAt": NOW.isoformat(), "evidence": "v1.x"},
                ),
            ):
                with self.assertRaises(Exception) as refused:
                    attempt()
                self.assertEqual(refused.exception.category, "root_protected")

    def test_entry_type_text_limits_and_conflicts_are_refused_without_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _runtime = self._activate(root)
            media = self._media_service(api, active)
            vault = root / "target" / "media-vault"
            (vault / "movie.mkv").write_bytes(b"\x1a\x45\xdf\xa3binary")
            (vault / "folder").mkdir()
            (vault / "huge.txt").write_text("x" * 10, encoding="utf-8")
            (vault / "link.txt").symlink_to(vault / "huge.txt")
            for attempt, code in (
                (
                    lambda: media.read_text(library_id=SHARED_ID, path="movie.mkv"),
                    "files_direct_unsupported_text_type",
                ),
                (
                    lambda: media.read_text(library_id=SHARED_ID, path="folder"),
                    "files_direct_is_a_directory",
                ),
                (
                    lambda: media.create_text(
                        library_id=SHARED_ID, parent_path="", name="poster.jpg", content="x"
                    ),
                    "files_direct_unsupported_text_type",
                ),
                (
                    lambda: media.rename(
                        library_id=SHARED_ID,
                        path="huge.txt",
                        name="huge.txt",
                        expected=self._rename_evidence(api, active, SHARED_ID, "huge.txt"),
                    ),
                    "files_direct_invalid_name",
                ),
                (
                    lambda: media.rename(
                        library_id=SHARED_ID,
                        path="missing.txt",
                        name="other.txt",
                        expected={
                            "size": 1,
                            "modifiedAt": NOW.isoformat(),
                            "evidence": "v1." + "0" * 32,
                        },
                    ),
                    "files_direct_not_found",
                ),
            ):
                with self.assertRaises(Exception) as refused:
                    attempt()
                self.assertEqual(refused.exception.code, code)
            # A symlink is excluded from text editing and from Delete.
            with self.assertRaises(Exception) as symlink_read:
                media.read_text(library_id=SHARED_ID, path="link.txt")
            self.assertEqual(
                symlink_read.exception.code,
                "files_direct_symlink_not_supported",
            )
            with self.assertRaises(Exception) as symlink_delete:
                media.delete_impact(library_id=SHARED_ID, paths=["link.txt"])
            self.assertEqual(
                symlink_delete.exception.code,
                "files_direct_symlink_not_supported",
            )
            self.assertTrue((vault / "link.txt").is_symlink())
            self.assertEqual((vault / "huge.txt").read_text(encoding="utf-8"), "x" * 10)
            # Conflict: never a silent overwrite.
            with self.assertRaises(Exception) as conflict:
                media.create_text(
                    library_id=SHARED_ID, parent_path="", name="huge.txt", content="new"
                )
            self.assertEqual(conflict.exception.code, "files_direct_target_exists")
            self.assertEqual(conflict.exception.status, 409)
            self.assertEqual((vault / "huge.txt").read_text(encoding="utf-8"), "x" * 10)
            # Bounded text size.
            big = "y" * (600 * 1024)
            with self.assertRaises(Exception) as oversized:
                media.create_text(library_id=SHARED_ID, parent_path="", name="big.txt", content=big)
            self.assertEqual(oversized.exception.code, "files_direct_text_too_large")
            self.assertEqual(oversized.exception.status, 413)
            self.assertFalse((vault / "big.txt").exists())

    def test_read_only_media_storage_denies_mutation_before_any_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            (root / "target" / "media-vault" / "keep.txt").write_text("k", encoding="utf-8")
            read_only = MutationAuditStorage("media-target", root / "target", read_only=True)
            with patch.object(DirectFileCommandService, "_open_storage", return_value=read_only):
                media = self._media_service(api, active)
                with self.assertRaises(Exception) as denied:
                    media.create_directory(library_id=SHARED_ID, parent_path="", name="blocked")
                self.assertEqual(denied.exception.code, "files_direct_capability_denied")
                self.assertEqual(denied.exception.status, 403)
            self.assertEqual(read_only.mutations, [])
            self.assertEqual(runtime.list_tasks(limit=100), ())
            self.assertFalse((root / "target" / "media-vault" / "blocked").exists())

    def test_media_commands_support_metadata_only_provider_observations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            vault = root / "target" / "media-vault"
            (vault / "a.txt").write_text("x", encoding="utf-8")
            (vault / "folder").mkdir()

            class Fingerprintless(LocalStorage):
                def stat(self, path: str):
                    entry = super().stat(path)
                    return type(entry)(
                        entry.name,
                        entry.path,
                        entry.entry_type,
                        entry.size,
                        entry.modified_at,
                        None,
                    )

                def list(self, path: str):
                    return tuple(
                        type(entry)(
                            entry.name,
                            entry.path,
                            entry.entry_type,
                            entry.size,
                            entry.modified_at,
                            None,
                        )
                        for entry in super().list(path)
                    )

            blind = Fingerprintless("media-target", root / "target")
            with patch.object(DirectFileCommandService, "_open_storage", return_value=blind):
                media = self._media_service(api, active)
                evidence = media.rename_evidence(library_id=SHARED_ID, path="a.txt")
                renamed = media.rename(
                    library_id=SHARED_ID,
                    path="a.txt",
                    name="renamed.txt",
                    expected=evidence.document(),
                )
                self.assertEqual(renamed["status"], "SUCCESS")
                impact = media.delete_impact(library_id=SHARED_ID, paths=["folder"])
                self.assertTrue(all(entry.fingerprint is None for entry in impact.entries))
                deleted = self._run_delete(
                    media,
                    library_id=SHARED_ID,
                    paths=["folder"],
                    confirmation_digest=impact.scope_digest,
                )
                self.assertEqual(deleted["status"], "SUCCESS")
                status, api_evidence = request(
                    api,
                    f"/api/v1/media-libraries/{SHARED_ID}/files/rename-evidence?path=renamed.txt",
                )
                self.assertEqual(status, 200, api_evidence)
                self.assertNotIn("fingerprint", api_evidence)
                status, api_rename = request(
                    api,
                    f"/api/v1/media-libraries/{SHARED_ID}/files/commands",
                    method="POST",
                    body={
                        "operation": "rename",
                        "path": "renamed.txt",
                        "name": "api-renamed.txt",
                        "expected": {
                            "size": api_evidence["size"],
                            "modifiedAt": api_evidence["modifiedAt"],
                            "evidence": api_evidence["evidence"],
                        },
                    },
                )
                self.assertEqual(status, 200, api_rename)
                self.assertEqual(api_rename["status"], "SUCCESS")
            self.assertFalse((vault / "a.txt").exists())
            self.assertTrue((vault / "api-renamed.txt").exists())
            self.assertFalse((vault / "folder").exists())
            self.assertGreaterEqual(len(runtime.list_tasks(limit=100)), 3)

    # ------------------------------------------------------------------
    # Stale evidence and durable per-item outcomes
    # ------------------------------------------------------------------

    def test_stale_version_evidence_is_refused_with_zero_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _runtime = self._activate(root)
            media = self._media_service(api, active)
            vault = root / "target" / "media-vault"
            (vault / "text.txt").write_text("first", encoding="utf-8")
            loaded = self._loaded(api, active, SHARED_ID, "text.txt")
            evidence = self._rename_evidence(api, active, SHARED_ID, "text.txt")
            (vault / "text.txt").write_text("replaced by someone else", encoding="utf-8")
            with self.assertRaises(Exception) as save:
                media.save_text(
                    library_id=SHARED_ID,
                    path="text.txt",
                    content="mine",
                    expected={"size": loaded["size"], "digest": loaded["digest"]},
                )
            self.assertEqual(save.exception.code, "files_direct_stale_content")
            self.assertEqual(
                (vault / "text.txt").read_text(encoding="utf-8"), "replaced by someone else"
            )
            with self.assertRaises(Exception) as rename:
                media.rename(
                    library_id=SHARED_ID, path="text.txt", name="mine.txt", expected=evidence
                )
            self.assertEqual(rename.exception.code, "files_direct_stale_source")
            self.assertFalse((vault / "mine.txt").exists())
            impact = media.delete_impact(library_id=SHARED_ID, paths=["text.txt"])
            (vault / "text.txt").unlink()
            (vault / "text.txt").write_text("brand new", encoding="utf-8")
            with self.assertRaises(Exception) as delete:
                self._run_delete(
                    media,
                    library_id=SHARED_ID,
                    paths=["text.txt"],
                    confirmation_digest=impact.scope_digest,
                )
            self.assertEqual(delete.exception.code, "files_direct_stale_confirmation")
            self.assertEqual((vault / "text.txt").read_text(encoding="utf-8"), "brand new")

    def test_partial_delete_keeps_independent_per_item_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            media = self._media_service(api, active)
            batch = root / "target" / "media-vault" / "batch"
            batch.mkdir()
            (batch / "one.txt").write_text("1", encoding="utf-8")
            (batch / "two.txt").write_text("2", encoding="utf-8")
            impact = media.delete_impact(library_id=SHARED_ID, paths=["batch"])
            real_delete = LocalStorage.delete

            def refuse_one(storage_self, path, *args, **kwargs):
                if path.endswith("one.txt"):
                    raise RuntimeError("provider refused one.txt")
                return real_delete(storage_self, path, *args, **kwargs)

            with patch.object(LocalStorage, "delete", refuse_one):
                outcome = self._run_delete(
                    media,
                    library_id=SHARED_ID,
                    paths=["batch"],
                    confirmation_digest=impact.scope_digest,
                )
            self.assertEqual(outcome["status"], "PARTIAL")
            self.assertEqual(outcome["succeededItems"], 1)
            self.assertEqual(outcome["failedItems"], 2)
            self.assertEqual(
                outcome["knownEffects"],
                [{"path": "batch", "effect": "partial", "status": "PARTIAL"}],
            )
            self.assertFalse((batch / "two.txt").exists())
            self.assertTrue((batch / "one.txt").exists())
            items = runtime.list_items(outcome["taskId"])
            statuses = {item.source_display: item.status.value for item in items}
            self.assertEqual(statuses["batch/two.txt"], "success")
            self.assertEqual(statuses["batch/one.txt"], "failed")
            self.assertTrue(
                any(item.error for item in items if item.source_display == "batch/one.txt")
            )
            # A successful sibling is never replayed by a later retry attempt.
            self.assertEqual(outcome["retrySafe"], False)

    def test_media_delete_persists_source_change_and_unconfirmed_directory_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            media = self._media_service(api, active)
            changed_file = root / "target" / "media-vault" / "changed.txt"
            changed_file.write_text("old", encoding="utf-8")
            file_impact = media.delete_impact(library_id=SHARED_ID, paths=["changed.txt"])
            file_admission = media.submit_delete(
                library_id=SHARED_ID,
                paths=["changed.txt"],
                confirmation_digest=file_impact.scope_digest,
            )
            changed_file.write_text("replacement with a different size", encoding="utf-8")
            file_result = self._run_admitted_delete(media, file_admission)
            self.assertEqual(file_result["outcomes"][0]["errorCategory"], "source_changed")
            file_item = runtime.list_items(file_admission["taskId"])[0]
            file_record = runtime.list_results(file_admission["taskId"])[0]
            self.assertEqual(file_item.error, "source_changed")
            self.assertEqual(file_record.error, "source_changed")
            self.assertTrue(changed_file.exists())

            empty_directory = root / "target" / "media-vault" / "empty-at-confirmation"
            empty_directory.mkdir()
            directory_impact = media.delete_impact(
                library_id=SHARED_ID, paths=["empty-at-confirmation"]
            )
            directory_admission = media.submit_delete(
                library_id=SHARED_ID,
                paths=["empty-at-confirmation"],
                confirmation_digest=directory_impact.scope_digest,
            )
            (empty_directory / "new-child.txt").write_text("keep", encoding="utf-8")
            directory_result = self._run_admitted_delete(media, directory_admission)
            self.assertEqual(directory_result["outcomes"][0]["errorCategory"], "directory_changed")
            directory_item = runtime.list_items(directory_admission["taskId"])[0]
            directory_record = runtime.list_results(directory_admission["taskId"])[0]
            self.assertEqual(directory_item.error, "directory_changed")
            self.assertEqual(directory_record.error, "directory_changed")
            status = request(
                api,
                f"/api/v1/media-libraries/{SHARED_ID}/files/deletes/"
                f"{directory_admission['taskId']}",
            )
            self.assertEqual(status[0], 200, status[1])
            self.assertEqual(status[1]["outcomes"][0]["errorCategory"], "directory_changed")
            self.assertTrue((empty_directory / "new-child.txt").exists())

    def test_uncertain_media_effect_is_recorded_and_never_replayed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            media = self._media_service(api, active)
            (root / "target" / "media-vault" / "u.txt").write_text("x", encoding="utf-8")
            from mediaflow.domain.organizer import ExecutionResult, PlanOperation

            uncertain = ExecutionResult(
                status=ExecutionStatus.PARTIAL,
                operation=PlanOperation.DELETE,
                source="u.txt",
                destination="u.txt",
                errors=("the provider connection was lost during delete",),
                effect_certainty=ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED,
                uncertain_effects=("delete may have been applied",),
            )
            impact = media.delete_impact(library_id=SHARED_ID, paths=["u.txt"])
            with patch(
                "mediaflow.application.direct_file_commands.OrganizerExecutor.execute_direct_delete",
                return_value=uncertain,
            ):
                outcome = self._run_delete(
                    media,
                    library_id=SHARED_ID,
                    paths=["u.txt"],
                    confirmation_digest=impact.scope_digest,
                )
            self.assertEqual(outcome["status"], "UNCERTAIN")
            self.assertEqual(outcome["durableState"], "mutation_effect_uncertain")
            self.assertIn("never replayed automatically", outcome["nextAction"])
            self.assertEqual(
                outcome["knownEffects"],
                [{"path": "u.txt", "effect": "uncertain", "status": "UNCERTAIN"}],
            )
            item = runtime.list_items(outcome["taskId"])[0]
            self.assertEqual(item.status.value, "partial")
            results = runtime.list_results(outcome["taskId"])
            self.assertEqual(results[0].effect_certainty, "attempted_unverified")
            self.assertTrue(results[0].uncertain_effects)
            # The durable record alone is not a resume token: reading the Task back
            # must never re-enter the executor with the uncertain mutation.
            final = runtime.get_task(outcome["taskId"])
            self.assertIn(final.status.value, {"failed", "partial_success"})
            self.assertTrue(final.completed_at is not None)

    # ------------------------------------------------------------------
    # API transport: media namespace, RBAC, compatibility, recovery
    # ------------------------------------------------------------------

    def test_media_api_surface_matches_the_resource_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            vault = root / "target" / "media-vault"
            created = request(
                api,
                f"/api/v1/media-libraries/{SHARED_ID}/files/commands",
                method="POST",
                body={"operation": "create_directory", "parentPath": "", "name": "Show"},
            )
            self.assertEqual(created[0], 200, created[1])
            self.assertEqual(created[1]["taskCommand"], "media_files_direct_command")
            self.assertEqual(created[1]["libraryKind"], "media")
            self.assertEqual(created[1]["sideEffects"], "storage_mutations")
            text = request(
                api,
                f"/api/v1/media-libraries/{SHARED_ID}/files/commands",
                method="POST",
                body={
                    "operation": "create_text",
                    "parentPath": "Show",
                    "name": "ep01.srt",
                    "content": "1\n00:00:00,000 --> 00:00:01,000\nhi\n",
                },
            )
            self.assertEqual(text[0], 200, text[1])
            read = request(
                api,
                f"/api/v1/media-libraries/{SHARED_ID}/files/text?path=Show/ep01.srt",
            )
            self.assertEqual(read[0], 200, read[1])
            self.assertEqual(
                set(read[1]),
                {"mediaLibraryId", "path", "content", "evidence", "sideEffects", "retrySafe"},
            )
            self.assertEqual(read[1]["mediaLibraryId"], SHARED_ID)
            self.assertEqual(read[1]["sideEffects"], "none")
            evidence = request(
                api,
                f"/api/v1/media-libraries/{SHARED_ID}/files/rename-evidence?path=Show/ep01.srt",
            )
            self.assertEqual(evidence[0], 200, evidence[1])
            self.assertEqual(
                set(evidence[1]),
                {
                    "mediaLibraryId",
                    "path",
                    "isDirectory",
                    "size",
                    "modifiedAt",
                    "evidence",
                    "sideEffects",
                    "retrySafe",
                    "nextAction",
                },
            )
            self.assertNotIn("fingerprint", json.dumps(evidence[1]))
            impact = request(
                api,
                f"/api/v1/media-libraries/{SHARED_ID}/files/delete-impact?path=Show",
            )
            self.assertEqual(impact[0], 200, impact[1])
            self.assertEqual(impact[1]["mediaLibraryId"], SHARED_ID)
            self.assertEqual(impact[1]["sideEffects"], "none")
            deleted = request(
                api,
                f"/api/v1/media-libraries/{SHARED_ID}/files/commands",
                method="POST",
                body={
                    "operation": "delete",
                    "paths": ["Show"],
                    "confirmationDigest": impact[1]["scopeDigest"],
                    "requestId": "26dbb770-c8d3-4d0a-9af9-483b12a4e58d",
                },
            )
            self.assertEqual(deleted[0], 202, deleted[1])
            self.assertEqual(deleted[1]["taskId"], "26dbb770-c8d3-4d0a-9af9-483b12a4e58d")
            self.assertEqual(deleted[1]["taskCommand"], "media_files_delete")
            self.assertTrue((vault / "Show").exists())
            media_service = self._media_service(api, active)
            completed = self._run_admitted_delete(media_service, deleted[1])
            self.assertEqual(completed["status"], "SUCCESS")
            self.assertFalse((vault / "Show").exists())
            status = request(
                api,
                f"/api/v1/media-libraries/{SHARED_ID}/files/deletes/{deleted[1]['taskId']}",
            )
            self.assertEqual(status[0], 200, status[1])
            self.assertEqual(status[1]["status"], "SUCCESS")
            # Durable per-item outcome stays independently inspectable after reload.
            task = runtime.get_task(deleted[1]["taskId"])
            self.assertEqual(task.command, "media_files_delete")
            items = runtime.list_items(task.task_id)
            self.assertEqual({item.resource_library_id for item in items}, {f"media:{SHARED_ID}"})
            results = runtime.list_results(task.task_id)
            self.assertTrue(results)
            self.assertTrue(all(result.recognition_type is None for result in results))
            self.assertTrue(all(result.naming_policy_id is None for result in results))
            # RBAC: the media command surface requires the same execute permission.
            denied = request(
                api,
                f"/api/v1/media-libraries/{SHARED_ID}/files/commands",
                method="POST",
                token="viewer-token",
                body={"operation": "create_directory", "parentPath": "", "name": "Nope"},
            )
            self.assertEqual(denied[0], 403, denied[1])
            self.assertEqual(denied[1]["error"]["code"], "forbidden")
            self.assertFalse((vault / "Nope").exists())
            # A media read still requires READ (viewer has it; an unauthenticated
            # request does not).
            anonymous = request(
                api,
                f"/api/v1/media-libraries/{SHARED_ID}/files/text?path=Show/ep01.srt",
                token=None,
            )
            self.assertIn(anonymous[0], {401, 403})
            # Unknown operation and extra fields fail closed before admission.
            bad = request(
                api,
                f"/api/v1/media-libraries/{SHARED_ID}/files/commands",
                method="POST",
                body={"operation": "teleport", "parentPath": "", "name": "x"},
            )
            self.assertEqual(bad[0], 400, bad[1])
            extra = request(
                api,
                f"/api/v1/media-libraries/{SHARED_ID}/files/commands",
                method="POST",
                body={
                    "operation": "create_directory",
                    "parentPath": "",
                    "name": "x",
                    "storageId": "media-target",
                },
            )
            self.assertEqual(extra[0], 400, extra[1])
            self.assertFalse((vault / "x").exists())
            # The resource namespace resolves only the ResourceLibrary with this ID:
            # the media file that was created and deleted above never appears there.
            wrong_namespace = request(
                api,
                f"/api/v1/resource-libraries/{SHARED_ID}/files/text?path=Show/ep01.srt",
            )
            self.assertEqual(wrong_namespace[0], 404, wrong_namespace[1])
            self.assertEqual(wrong_namespace[1]["error"]["code"], "files_direct_not_found")

    def test_media_library_unavailable_bindings_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            # A MediaLibrary whose Storage binding cannot be opened fails closed.
            real_builder = create_storage_from_definition

            def unavailable_builder(definition):
                if definition.storage_id == "media-target":
                    raise RuntimeError("provider endpoint is unreachable")
                return real_builder(definition)

            with patch(
                "mediaflow.infrastructure.runtime_configuration.create_storage_from_definition",
                unavailable_builder,
            ):
                missing_storage = request(
                    api,
                    f"/api/v1/media-libraries/{SHARED_ID}/files/commands",
                    method="POST",
                    body={"operation": "create_directory", "parentPath": "", "name": "x"},
                )
            self.assertEqual(missing_storage[0], 503, missing_storage[1])
            self.assertEqual(
                missing_storage[1]["error"]["code"], "files_direct_storage_unavailable"
            )
            self.assertEqual(missing_storage[1]["error"]["details"]["sideEffects"], "none")
            self.assertFalse((root / "target" / "media-vault" / "x").exists())
            disabled = request(
                api,
                "/api/v1/media-libraries/off/files/commands",
                method="POST",
                body={"operation": "create_directory", "parentPath": "", "name": "x"},
            )
            self.assertEqual(disabled[0], 404, disabled[1])
            self.assertEqual(disabled[1]["error"]["code"], "files_direct_media_library_not_found")
            # The error names only the media identity, never a host root or secret.
            details = disabled[1]["error"]["details"]
            self.assertEqual(details["mediaLibraryId"], "off")
            self.assertIsNone(details["resourceLibraryId"])
            self.assertNotIn(str(root), json.dumps(disabled[1]))
            self.assertEqual(runtime.list_tasks(limit=100), ())

    def test_resource_library_command_journey_remains_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            created = request(
                api,
                f"/api/v1/resource-libraries/{SHARED_ID}/files/commands",
                method="POST",
                body={"operation": "create_directory", "parentPath": "", "name": "legacy"},
            )
            self.assertEqual(created[0], 200, created[1])
            task = runtime.get_task(created[1]["taskId"])
            self.assertEqual(task.command, "files_direct_command")
            # The command names the unchanged ResourceLibrary value and kind.
            self.assertEqual(created[1]["taskCommand"], "files_direct_command")
            self.assertEqual(created[1]["libraryKind"], "resource")
            self.assertEqual(created[1]["resourceLibraryId"], SHARED_ID)
            self.assertNotIn("mediaLibraryId", created[1])
            items = runtime.list_items(task.task_id)
            # Pre-existing durable identity: the bare configured ResourceLibrary ID.
            self.assertEqual(items[0].resource_library_id, SHARED_ID)
            evidence = request(
                api,
                f"/api/v1/resource-libraries/{SHARED_ID}/files/rename-evidence?path=legacy",
            )
            self.assertEqual(evidence[0], 200, evidence[1])
            self.assertEqual(evidence[1]["resourceLibraryId"], SHARED_ID)
            self.assertNotIn("mediaLibraryId", evidence[1])
            impact = request(
                api,
                f"/api/v1/resource-libraries/{SHARED_ID}/files/delete-impact?path=legacy",
            )
            self.assertEqual(impact[1]["resourceLibraryId"], SHARED_ID)
            deleted = request(
                api,
                f"/api/v1/resource-libraries/{SHARED_ID}/files/commands",
                method="POST",
                body={
                    "operation": "delete",
                    "paths": ["legacy"],
                    "confirmationDigest": impact[1]["scopeDigest"],
                },
            )
            self.assertEqual(deleted[0], 202, deleted[1])
            self.assertTrue((root / "source" / "incoming" / "legacy").exists())
            resource_service = self._binding(api, active).direct_files
            completed = self._run_admitted_delete(resource_service, deleted[1])
            self.assertEqual(completed["status"], "SUCCESS")
            self.assertEqual(runtime.get_task(deleted[1]["taskId"]).command, "files_delete")

    def test_media_command_routes_fail_closed_without_an_active_runtime(self) -> None:
        """No Active runtime means no command authority: every surface refuses.

        Mirrors the 38.1 browse guarantee for the new command namespace: the
        refusal carries zero side effects, creates no Task, and touches no file.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.mkdir(exist_ok=True)
            database = root / "configuration.sqlite3"
            document = self._document(root)
            document["persistence"]["databasePath"] = str(database)
            (root / "source" / "incoming").mkdir(parents=True)
            (root / "target" / "media-vault").mkdir(parents=True)
            with (
                SQLiteConfigurationRepository(database) as configuration_repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime,
            ):
                managed = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(database),
                )
                api = MediaFlowApi(
                    runtime,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=managed,
                    bootstrap_document=document,
                    storage_browser_cursor_secret="media-commands-test-secret",
                )
                surfaces = (
                    (
                        f"/api/v1/media-libraries/{SHARED_ID}/files/commands",
                        "POST",
                        {"operation": "create_directory", "parentPath": "", "name": "x"},
                    ),
                    (f"/api/v1/media-libraries/{SHARED_ID}/files/text?path=a.txt", "GET", None),
                    (
                        f"/api/v1/media-libraries/{SHARED_ID}/files/delete-impact?path=a.txt",
                        "GET",
                        None,
                    ),
                    (
                        f"/api/v1/media-libraries/{SHARED_ID}/files/rename-evidence?path=a.txt",
                        "GET",
                        None,
                    ),
                )
                for url, method, body in surfaces:
                    status, error = request(api, url, method=method, body=body)
                    self.assertEqual(status, 503, (url, error))
                    self.assertEqual(error["error"]["code"], "configuration_unavailable")
                    self.assertEqual(error["error"]["details"]["sideEffects"], "none")
                self.assertEqual(runtime.list_tasks(limit=10), ())
            self.assertEqual(list((root / "target" / "media-vault").iterdir()), [])

    def test_media_rows_keep_their_namespaced_identity_and_never_become_source_work(self) -> None:
        """A media Task stays attributable to its own namespaced library identity.

        Both libraries share one Storage and one overlapping root here, so a
        media direct-command row addresses exactly the same
        ``(storage, storage-relative path)`` a ResourceLibrary row would use.
        The persisted identity keeps the media namespace, so no source-scoped
        lookup can present that maintenance as a ResourceLibrary source's work.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            (root / "target" / "media-vault" / "shared.mkv").write_bytes(b"x")
            (root / "source" / "incoming" / "shared.mkv").write_bytes(b"x")
            media = self._media_service(api, active)
            outcome = media.rename(
                library_id=SHARED_ID,
                path="shared.mkv",
                name="renamed.mkv",
                expected=self._rename_evidence(api, active, SHARED_ID, "shared.mkv"),
            )
            self.assertEqual(outcome["status"], "SUCCESS")
            task = runtime.get_task(outcome["taskId"])
            item = runtime.list_items(task.task_id)[0]
            self.assertEqual(item.storage_id, "media-target")
            self.assertEqual(item.resource_library_id, f"media:{SHARED_ID}")
            # The persisted identity is namespaced by library kind, so an equal
            # ResourceLibrary ID never reads this media row as its own work.
            from mediaflow.domain.direct_files import LibraryKind, split_library_identity

            self.assertEqual(
                split_library_identity(item.resource_library_id),
                (LibraryKind.MEDIA, SHARED_ID),
            )
            # The media Task remains durable and attributable on its own, and it
            # persists only bounded library-relative identities.
            self.assertEqual(task.command, "media_files_direct_command")
            result = runtime.list_results(task.task_id)[0]
            self.assertEqual(result.source_path, "shared.mkv")
            self.assertEqual(result.destination_path, "renamed.mkv")
            from dataclasses import asdict

            self.assertNotIn(str(root), json.dumps(asdict(result), default=str))

    def test_media_commands_create_no_media_pipeline_work(self) -> None:
        """Direct maintenance never starts Scan/Recognize/Metadata/Organize work."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            media = self._media_service(api, active)
            media.create_directory(library_id=SHARED_ID, parent_path="", name="Quiet")
            impact = media.delete_impact(library_id=SHARED_ID, paths=["Quiet"])
            self._run_delete(
                media,
                library_id=SHARED_ID,
                paths=["Quiet"],
                confirmation_digest=impact.scope_digest,
            )
            commands = {task.command for task in runtime.list_tasks(limit=100)}
            self.assertTrue(commands.issubset({"media_files_direct_command", "media_files_delete"}))
            for task in runtime.list_tasks(limit=100):
                for item in runtime.list_items(task.task_id):
                    # No plan, no provider identity, no policy evidence.
                    self.assertIsNone(item.plan_id)
                    self.assertIsNone(item.source_occurrence_id)
                    self.assertEqual(item.stage, "completed")
                    results = runtime.list_results(task.task_id)
                    for result in results:
                        self.assertIsNone(result.recognition_type)
                        self.assertIsNone(result.provider)
                        self.assertIsNone(result.naming_policy_id)
                        self.assertIsNone(result.classification_policy_id)
                        self.assertIsNone(result.organize_policy_id)


if __name__ == "__main__":
    unittest.main()
