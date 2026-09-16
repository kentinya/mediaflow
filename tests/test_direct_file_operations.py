from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.direct_file_commands import DirectFileCommandService, DirectFileError
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.domain.configuration_management import (
    ConfigurationDestinationPrecheckStatus,
    ConfigurationStorageCheckStatus,
    ConfigurationStrategyTestStatus,
)
from mediaflow.domain.direct_files import EntryVersionEvidence
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.storage import StorageCapabilities, StorageEntry, StorageEntryType
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_configuration_objects import example_document


def request(
    api: MediaFlowApi,
    url: str,
    *,
    method: str = "GET",
    body: object | None = None,
    token: str = "admin-token",
):
    """WSGI request helper that routes query strings like the real server."""

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


def _removal_confirmation(preview: dict) -> dict[str, object]:
    """The exact previewed Active revision identity bound to one confirmation."""

    active = preview["active"]
    return {
        "expectedRevisionId": active["revisionId"],
        "expectedVersion": active["version"],
        "expectedDigest": active["digest"],
        "expectedLibraryId": preview["resourceLibrary"]["id"],
    }


def _entry_evidence(api, active, resource_library_id: str, relative: str) -> dict:
    """The server-issued observed evidence for one entry, as the API issues it."""

    binding = api._prepare_runtime_binding_for_revision(active)
    service = binding.direct_files
    library = service._library(resource_library_id)
    storage = service._open_storage(library)
    entry = service._stat_entry(library, storage, relative)
    return {"size": entry.size, "modifiedAt": entry.modified_at.isoformat()}


def _loaded_evidence(service: DirectFileCommandService, resource_library_id: str, path: str):
    """The exact loaded text-version evidence the API issues for a read."""

    return service.read_text(resource_library_id=resource_library_id, path=path).evidence.document()


def _unreference_source(document: dict[str, object]) -> None:
    """Point every recognition rule at a different library ID."""

    for rule in document["recognitionRules"]:
        condition = rule.get("condition", {})
        if not isinstance(condition, dict):
            continue
        for child in condition.get("children", []):
            if (
                isinstance(child, dict)
                and child.get("field") == "resource_library_id"
                and child.get("value") == "source"
            ):
                child["value"] = "another-library"


class MutationFreeStorage:
    """A provider-neutral fake that refuses every mutating Storage call."""

    def __init__(self, storage_id: str, *, read_only: bool = False) -> None:
        self.storage_id = storage_id
        self.name = storage_id
        self.read_only = read_only
        self.mutations: list[str] = []
        self.capabilities = StorageCapabilities()

    def stat(self, path: str) -> StorageEntry:
        return StorageEntry(Path(path).name, path, StorageEntryType.DIRECTORY, 0, datetime.now(UTC))

    def list(self, path: str):
        return ()

    def exists(self, path: str) -> bool:
        return True

    def read(self, path: str):
        return io.BytesIO(b"")

    def write(self, *args, **kwargs):
        self.mutations.append("write")
        raise AssertionError("this journey must not write Storage")

    def create_directory(self, *args, **kwargs):
        self.mutations.append("create_directory")
        raise AssertionError("this journey must not create Storage directories")

    def move(self, *args, **kwargs):
        self.mutations.append("move")
        raise AssertionError("this journey must not move Storage entries")

    def copy(self, *args, **kwargs):
        self.mutations.append("copy")
        raise AssertionError("this journey must not copy Storage entries")

    def delete(self, *args, **kwargs):
        self.mutations.append("delete")
        raise AssertionError("this journey must not delete Storage entries")

    def hard_link(self, *args, **kwargs):
        self.mutations.append("hard_link")
        raise AssertionError("this journey must not hard-link Storage entries")

    def soft_link(self, *args, **kwargs):
        self.mutations.append("soft_link")
        raise AssertionError("this journey must not soft-link Storage entries")


class _CountingExecutor(OrganizerExecutor):
    """Executor double that flags the moments a mutation actually crosses."""

    def __init__(self) -> None:
        super().__init__()
        self.boundaries: list[str] = []
        self.in_mutation = False

    def _execute_direct(
        self,
        storage,
        operation,
        source,
        target,
        *,
        execute,
        mutation_authority,
        preflight,
        mutate,
        verify,
    ):
        def observed_mutate():
            self.boundaries.append(f"DIRECT:{operation.value}")
            self.in_mutation = True
            try:
                return mutate()
            finally:
                self.in_mutation = False

        return super()._execute_direct(
            storage,
            operation,
            source,
            target,
            execute=execute,
            mutation_authority=mutation_authority,
            preflight=preflight,
            mutate=observed_mutate,
            verify=verify,
        )


class _LateSwapExecutor(OrganizerExecutor):
    """Executor double that swaps the source inside its own preflight.

    This simulates a true pre-mutation race: the file still matches the
    admitted evidence when the application admission digest check runs, then a
    concurrent writer replaces it just before the executor's mutating Storage
    call.  Re-running the executor's own preflight (which closes over the
    admitted data/evidence) re-verifies the digest at the last safe boundary
    and refuses the mutation.
    """

    def __init__(self, root: Path, relative: str, content: str) -> None:
        super().__init__()
        self._root = root
        self._relative = relative
        self._content = content

    def _execute_direct(
        self,
        storage,
        operation,
        source,
        target,
        *,
        execute,
        mutation_authority,
        preflight,
        mutate,
        verify,
    ):
        def swap_then_preflight():
            reason = preflight()
            if reason is None:
                # The admitted evidence just passed the regular preflight; a
                # concurrent writer now replaces the file before the mutating
                # Storage call.
                (self._root / "source" / self._relative).write_text(self._content, encoding="utf-8")
                # Re-run the same preflight: the digest/size fence re-checks the
                # swapped content against the admitted evidence and refuses.
                return preflight()
            return reason

        return super()._execute_direct(
            storage,
            operation,
            source,
            target,
            execute=execute,
            mutation_authority=mutation_authority,
            preflight=swap_then_preflight,
            mutate=mutate,
            verify=verify,
        )


class _RecordingStorage(LocalStorage):
    """Local Storage that records whether mutations crossed the executor."""

    def __init__(self, storage_id: str, root: Path, observer: _CountingExecutor) -> None:
        super().__init__(storage_id, root)
        self._observer = observer
        self.mutations: list[tuple[str, bool]] = []

    def write(self, *args, **kwargs):
        self.mutations.append(("write", self._observer.in_mutation))
        return super().write(*args, **kwargs)

    def create_directory(self, *args, **kwargs):
        self.mutations.append(("create_directory", self._observer.in_mutation))
        return super().create_directory(*args, **kwargs)

    def move(self, *args, **kwargs):
        self.mutations.append(("move", self._observer.in_mutation))
        return super().move(*args, **kwargs)

    def copy(self, *args, **kwargs):
        self.mutations.append(("copy", self._observer.in_mutation))
        return super().copy(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.mutations.append(("delete", self._observer.in_mutation))
        return super().delete(*args, **kwargs)

    def hard_link(self, *args, **kwargs):
        self.mutations.append(("hard_link", self._observer.in_mutation))
        return super().hard_link(*args, **kwargs)

    def soft_link(self, *args, **kwargs):
        self.mutations.append(("soft_link", self._observer.in_mutation))
        return super().soft_link(*args, **kwargs)


class _FingerprintlessStorage(LocalStorage):
    """Storage whose entries publish no provider identity token.

    SMB and OpenList entries and S3 directory entries carry no fingerprint, so
    this provider-neutral fake is the stand-in used to prove that a folder
    Delete without a verifiable directory identity fails closed.  Every delete
    that does reach the Storage is recorded.
    """

    def __init__(self, storage_id: str, root: Path) -> None:
        super().__init__(storage_id, root)
        self.deleted: list[str] = []

    @staticmethod
    def _anonymous(entry: StorageEntry) -> StorageEntry:
        return StorageEntry(
            name=entry.name,
            path=entry.path,
            entry_type=entry.entry_type,
            size=entry.size,
            modified_at=entry.modified_at,
            fingerprint=None,
        )

    def stat(self, path: str) -> StorageEntry:
        return self._anonymous(super().stat(path))

    def list(self, path: str):
        return [self._anonymous(entry) for entry in super().list(path)]

    def delete(self, path: str) -> None:
        self.deleted.append(path)
        return super().delete(path)


class DirectFileExecutorTests(unittest.TestCase):
    """Executor-level evidence: the direct boundary is narrow and safe."""

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)
        self.storage = LocalStorage("storage", self.root)

    def test_create_directory_success_dry_run_and_conflict(self) -> None:
        executor = OrganizerExecutor()
        dry = executor.execute_direct_create_directory(self.storage, "movies", execute=False)
        self.assertEqual(dry.status.value, "DRY_RUN")
        self.assertEqual(dry.effect_certainty.value, "none")
        self.assertFalse((self.root / "movies").exists())
        result = executor.execute_direct_create_directory(self.storage, "movies")
        self.assertEqual(result.status.value, "SUCCESS")
        self.assertEqual(result.effect_certainty.value, "verified_complete")
        self.assertTrue((self.root / "movies").is_dir())
        conflict = executor.execute_direct_create_directory(self.storage, "movies")
        self.assertEqual(conflict.status.value, "FAILED")
        self.assertIn("destination already exists", conflict.errors)
        self.assertEqual(conflict.effect_certainty.value, "none")

    def test_write_refuses_unauthorized_overwrite_and_verifies_size(self) -> None:
        executor = OrganizerExecutor()
        (self.root / "notes.txt").write_text("old", encoding="utf-8")
        refused = executor.execute_direct_write(self.storage, "notes.txt", b"new")
        self.assertEqual(refused.status.value, "FAILED")
        self.assertEqual((self.root / "notes.txt").read_text(encoding="utf-8"), "old")
        written = executor.execute_direct_write(
            self.storage, "notes.txt", b"replaced", overwrite=True
        )
        self.assertEqual(written.status.value, "SUCCESS")
        self.assertEqual((self.root / "notes.txt").read_bytes(), b"replaced")

    def test_rename_is_same_storage_only_and_never_replaces(self) -> None:
        executor = OrganizerExecutor()
        (self.root / "a.txt").write_text("x", encoding="utf-8")
        (self.root / "b.txt").write_text("y", encoding="utf-8")
        conflict = executor.execute_direct_rename(self.storage, "a.txt", "b.txt")
        self.assertEqual(conflict.status.value, "FAILED")
        self.assertIn("destination already exists", conflict.errors)
        self.assertTrue((self.root / "a.txt").exists())
        renamed = executor.execute_direct_rename(self.storage, "a.txt", "c.txt")
        self.assertEqual(renamed.status.value, "SUCCESS")
        self.assertFalse((self.root / "a.txt").exists())
        self.assertTrue((self.root / "c.txt").exists())

    def test_delete_requires_existing_entry(self) -> None:
        executor = OrganizerExecutor()
        missing = executor.execute_direct_delete(self.storage, "gone.txt")
        self.assertEqual(missing.status.value, "FAILED")
        (self.root / "item.txt").write_text("x", encoding="utf-8")
        (self.root / "folder").mkdir()
        self.assertEqual(
            executor.execute_direct_delete(self.storage, "item.txt").status.value, "SUCCESS"
        )
        self.assertEqual(
            executor.execute_direct_delete(self.storage, "folder").status.value, "SUCCESS"
        )

    def test_read_only_storage_is_denied_before_mutation(self) -> None:
        readonly = LocalStorage("ro", self.root, read_only=True)
        executor = OrganizerExecutor()
        denied = executor.execute_direct_create_directory(readonly, "blocked")
        self.assertEqual(denied.status.value, "FAILED")
        self.assertIn("capability denied", denied.errors[0])
        self.assertFalse((self.root / "blocked").exists())

    def test_invalid_paths_fail_before_any_storage_call(self) -> None:
        executor = OrganizerExecutor()
        for path in ("/absolute", "../escape", "a\\b", "a/../b"):
            for operation in (
                executor.execute_direct_create_directory,
                executor.execute_direct_delete,
            ):
                result = operation(self.storage, path)
                self.assertEqual(result.status.value, "FAILED")
                self.assertIn("invalid destination", result.errors)
        self.assertEqual(list(self.root.iterdir()), [])


class DirectFileOperationsTests(unittest.TestCase):
    """Application and API evidence for the Files direct command journey."""

    def _document(self, root: Path) -> dict[str, object]:
        document = example_document()
        document["persistence"]["databasePath"] = str(root / "configuration.sqlite3")
        document["storages"][0]["rootPath"] = str(root / "source")
        document["storages"][1]["rootPath"] = str(root / "target")
        document["resourceLibraries"][0]["storagePath"] = ""
        document["mediaLibraries"][0]["rootPath"] = "Movies"
        return document

    def _activate(
        self,
        root: Path,
        *,
        storage_adapters=None,
        document_overrides=None,
    ):
        document = self._document(root)
        if document_overrides is not None:
            document_overrides(document)
        (root / "source").mkdir(parents=True, exist_ok=True)
        (root / "target" / "Movies").mkdir(parents=True, exist_ok=True)
        configuration_repository = SQLiteConfigurationRepository(root / "configuration.sqlite3")
        self.addCleanup(configuration_repository.close)
        service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=str(root / "configuration.sqlite3"),
        )
        objects = ConfigurationObjectService(
            service,
            storage_adapters=storage_adapters,
            storage_browser_cursor_secret="direct-files-test-secret",
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
            resource_library_id="source",
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
            storage_browser_cursor_secret="direct-files-test-secret",
        )
        return api, objects, active, runtime_repository

    def _service(self, api, active) -> DirectFileCommandService:
        binding = api._prepare_runtime_binding_for_revision(active)
        self.assertIsNotNone(binding.direct_files)
        return binding.direct_files

    # ------------------------------------------------------------------
    # Application service journeys
    # ------------------------------------------------------------------

    def test_create_directory_and_rename_flow_updates_live_storage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            service = self._service(api, active)
            service.create_directory(resource_library_id="source", parent_path="", name="movies")
            outcome = service.create_directory(
                resource_library_id="source", parent_path="movies", name="2024"
            )
            self.assertEqual(outcome["status"], "SUCCESS")
            self.assertEqual(outcome["effectCertainty"], "verified_complete")
            self.assertTrue((root / "source" / "movies" / "2024").is_dir())
            rename = service.rename(
                resource_library_id="source",
                path="movies/2024",
                name="2025",
                expected=_entry_evidence(api, active, "source", "movies/2024"),
            )
            self.assertEqual(rename["status"], "SUCCESS")
            self.assertTrue((root / "source" / "movies" / "2025").is_dir())
            self.assertFalse((root / "source" / "movies" / "2024").exists())
            task = runtime.get_task(outcome["taskId"])
            self.assertIsNotNone(task)
            self.assertEqual(task.command, "files_direct_command")
            items = runtime.list_items(outcome["taskId"])
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].status.value, "success")

    def test_create_rejects_unsafe_names_and_existing_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _tasks = self._activate(root)
            service = self._service(api, active)
            for name in ("../escape", "a/b", "con", "name.", "/abs", ""):
                with self.assertRaises(DirectFileError) as caught:
                    service.create_directory(
                        resource_library_id="source", parent_path="", name=name
                    )
                self.assertEqual(caught.exception.category, "invalid_name")
                self.assertEqual(caught.exception.status, 400)
            self.assertEqual(list(root.glob("source/*")), [])
            service.create_directory(resource_library_id="source", parent_path="", name="shows")
            with self.assertRaises(DirectFileError) as conflict:
                service.create_directory(resource_library_id="source", parent_path="", name="shows")
            self.assertEqual(conflict.exception.category, "target_exists")
            self.assertEqual(conflict.exception.details["durableState"], "storage_unchanged")

    def test_create_text_admits_only_allowlisted_bounded_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _tasks = self._activate(root)
            service = self._service(api, active)
            service.create_directory(resource_library_id="source", parent_path="", name="notes")
            outcome = service.create_text(
                resource_library_id="source",
                parent_path="notes",
                name="plan.txt",
                content="hello",
            )
            self.assertEqual(outcome["status"], "SUCCESS")
            self.assertEqual(
                (root / "source" / "notes" / "plan.txt").read_text(encoding="utf-8"), "hello"
            )
            for name in ("movie.mkv", "binary.exe", "data.dat"):
                with self.assertRaises(DirectFileError) as caught:
                    service.create_text(
                        resource_library_id="source", parent_path="", name=name, content=""
                    )
                self.assertEqual(caught.exception.category, "unsupported_text_type")
            with self.assertRaises(DirectFileError) as conflict:
                service.create_text(
                    resource_library_id="source",
                    parent_path="notes",
                    name="plan.txt",
                    content="replacement",
                )
            self.assertEqual(conflict.exception.category, "target_exists")
            self.assertEqual(
                (root / "source" / "notes" / "plan.txt").read_text(encoding="utf-8"), "hello"
            )
            with self.assertRaises(DirectFileError) as oversized:
                service.create_text(
                    resource_library_id="source",
                    parent_path="",
                    name="big.txt",
                    content="x" * (512 * 1024 + 1),
                )
            self.assertEqual(oversized.exception.category, "text_too_large")
            self.assertFalse((root / "source" / "big.txt").exists())

    def test_read_text_is_bounded_zero_mutation_with_version_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _tasks = self._activate(root)
            service = self._service(api, active)
            (root / "source" / "notes").mkdir()
            (root / "source" / "notes" / "a.nfo").write_text("body", encoding="utf-8")
            document = service.read_text(resource_library_id="source", path="notes/a.nfo")
            self.assertEqual(document.content, "body")
            self.assertEqual(document.evidence.size, 4)
            self.assertTrue(document.evidence.digest)
            (root / "source" / "notes" / "a.mkv").write_bytes(b"\x00\x01mkv")
            for path, expected in (
                ("notes", "is_a_directory"),
                ("notes/a.mkv", "unsupported_text_type"),
                ("notes/missing.txt", "not_found"),
            ):
                with self.assertRaises(DirectFileError) as caught:
                    service.read_text(resource_library_id="source", path=path)
                self.assertEqual(caught.exception.category, expected)
            (root / "source" / "notes" / "bin.nfo").write_bytes(b"\xff\xfe\x00binary")
            with self.assertRaises(DirectFileError) as binary:
                service.read_text(resource_library_id="source", path="notes/bin.nfo")
            self.assertEqual(binary.exception.category, "text_not_decodable")
            (root / "source" / "notes" / "big.srt").write_bytes(b"x" * (512 * 1024 + 1))
            with self.assertRaises(DirectFileError) as oversized:
                service.read_text(resource_library_id="source", path="notes/big.srt")
            self.assertEqual(oversized.exception.category, "text_too_large")

    def test_save_text_is_stale_safe_and_never_overwrites_newer_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _tasks = self._activate(root)
            service = self._service(api, active)
            (root / "source" / "a.txt").write_text("v1", encoding="utf-8")
            loaded = service.read_text(resource_library_id="source", path="a.txt")
            (root / "source" / "a.txt").write_text("v2-newer", encoding="utf-8")
            with self.assertRaises(DirectFileError) as stale:
                service.save_text(
                    resource_library_id="source",
                    path="a.txt",
                    content="editor edits",
                    expected=loaded.evidence.document(),
                )
            self.assertEqual(stale.exception.category, "stale_changed")
            self.assertEqual(stale.exception.status, 409)
            self.assertEqual((root / "source" / "a.txt").read_text(encoding="utf-8"), "v2-newer")
            reloaded = service.read_text(resource_library_id="source", path="a.txt")
            outcome = service.save_text(
                resource_library_id="source",
                path="a.txt",
                content="editor edits",
                expected=reloaded.evidence.document(),
            )
            self.assertEqual(outcome["status"], "SUCCESS")
            self.assertEqual(
                (root / "source" / "a.txt").read_text(encoding="utf-8"), "editor edits"
            )

    def test_save_is_refused_at_the_mutation_boundary_after_a_same_size_swap(self) -> None:
        """A same-size replacement between admission and the write must fail.

        The swap happens exactly inside the executor's admission→preflight
        window: the file matches the loaded evidence when the application
        digest check runs, then a concurrent writer replaces it before the
        executor's last safe boundary.  The executor digest fence refuses the
        write, so the admitted editor content never replaces the newer file.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _tasks = self._activate(root)
            service = self._service(api, active)
            (root / "source" / "a.txt").write_text("v1!", encoding="utf-8")
            loaded = service.read_text(resource_library_id="source", path="a.txt")
            evidence = loaded.evidence.document()
            # The file still matches the loaded evidence at admission time; the
            # same-size replacement happens only inside the executor's
            # preflight window.
            swapper = _LateSwapExecutor(root, "a.txt", "vX!")
            with patch.object(service, "_executor", swapper):
                outcome = service.save_text(
                    resource_library_id="source",
                    path="a.txt",
                    content="editor edits",
                    expected=evidence,
                )
            self.assertEqual(outcome["status"], "FAILED")
            self.assertEqual(outcome["errorCategory"], "source_changed")
            self.assertEqual(outcome["effectCertainty"], "none")
            # The pre-mutation replacement content survives; the editor's
            # admitted content was never written.
            self.assertEqual((root / "source" / "a.txt").read_text(encoding="utf-8"), "vX!")

    def test_rename_binds_observed_source_evidence_and_refuses_swaps(self) -> None:
        """Rename requires and re-verifies server-issued source evidence."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            service = self._service(api, active)
            (root / "source" / "rename-me.txt").write_text("v1", encoding="utf-8")
            evidence = _entry_evidence(api, active, "source", "rename-me.txt")
            # Same size, different content after observation: refused stale.
            (root / "source" / "rename-me.txt").write_text("v2", encoding="utf-8")
            with self.assertRaises(DirectFileError) as stale:
                service.rename(
                    resource_library_id="source",
                    path="rename-me.txt",
                    name="renamed.txt",
                    expected=evidence,
                )
            self.assertEqual(stale.exception.category, "stale_source")
            self.assertEqual(stale.exception.status, 409)
            self.assertTrue((root / "source" / "rename-me.txt").exists())
            self.assertFalse((root / "source" / "renamed.txt").exists())
            # Fresh evidence succeeds and the durable record carries the target.
            fresh = _entry_evidence(api, active, "source", "rename-me.txt")
            outcome = service.rename(
                resource_library_id="source",
                path="rename-me.txt",
                name="renamed.txt",
                expected=fresh,
            )
            self.assertEqual(outcome["status"], "SUCCESS")
            self.assertEqual(outcome["target"], "renamed.txt")
            results = runtime.list_results(outcome["taskId"])
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].source_path, "rename-me.txt")
            self.assertEqual(results[0].destination_path, "renamed.txt")
            self.assertNotIn(str(root / "source"), json.dumps(results[0].__dict__, default=str))

    def test_rename_is_refused_at_the_mutation_boundary_after_a_same_size_swap(self) -> None:
        """A rename whose source is swapped inside the preflight window fails.

        The source matches the observed evidence at admission; a concurrent
        writer replaces it inside the executor's preflight window, and the
        executor's own size+mtime fence refuses to rename the replaced entry.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _tasks = self._activate(root)
            service = self._service(api, active)
            (root / "source" / "race.txt").write_text("v1", encoding="utf-8")

            class SwapInPreflight(OrganizerExecutor):
                def __init__(self, base: Path) -> None:
                    super().__init__()
                    self._base = base

                def _execute_direct(
                    self,
                    storage,
                    operation,
                    source,
                    target,
                    *,
                    execute,
                    mutation_authority,
                    preflight,
                    mutate,
                    verify,
                ):
                    def swap_then_preflight():
                        reason = preflight()
                        if reason is None:
                            # Same size, different content: only the executor's
                            # size+mtime fence can still refuse this rename.
                            (self._base / "source" / "race.txt").write_text("v2", encoding="utf-8")
                            return preflight()
                        return reason

                    return super()._execute_direct(
                        storage,
                        operation,
                        source,
                        target,
                        execute=execute,
                        mutation_authority=mutation_authority,
                        preflight=swap_then_preflight,
                        mutate=mutate,
                        verify=verify,
                    )

            swapper = SwapInPreflight(root)
            evidence = _entry_evidence(api, active, "source", "race.txt")
            with patch.object(service, "_executor", swapper):
                outcome = service.rename(
                    resource_library_id="source",
                    path="race.txt",
                    name="raced.txt",
                    expected=evidence,
                )
            self.assertEqual(outcome["status"], "FAILED")
            self.assertEqual(outcome["errorCategory"], "source_changed")
            # The replaced entry keeps its name; no rename happened.
            self.assertTrue((root / "source" / "race.txt").exists())
            self.assertFalse((root / "source" / "raced.txt").exists())
            self.assertEqual((root / "source" / "race.txt").read_text(encoding="utf-8"), "v2")

    def test_confirmed_delete_refuses_a_same_size_scope_swap(self) -> None:
        """A same-size source swap after the impact preview fails stale."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _tasks = self._activate(root)
            service = self._service(api, active)
            (root / "source" / "victim.txt").write_text("v1", encoding="utf-8")
            impact = service.delete_impact(resource_library_id="source", paths=["victim.txt"])
            # Same size, different content and a later mtime: the modifiedAt in
            # the scope digest makes the old confirmation stale instead of
            # deleting the new file.
            (root / "source" / "victim.txt").write_text("v2", encoding="utf-8")
            later = datetime.now(UTC) + timedelta(seconds=120)
            os.utime(root / "source" / "victim.txt", (later.timestamp(), later.timestamp()))
            with self.assertRaises(DirectFileError) as stale:
                service.execute_delete(
                    resource_library_id="source",
                    paths=["victim.txt"],
                    confirmation_digest=impact.scope_digest,
                )
            self.assertEqual(stale.exception.category, "stale_confirmation")
            self.assertEqual(stale.exception.status, 409)
            self.assertEqual((root / "source" / "victim.txt").read_text(encoding="utf-8"), "v2")

    def test_delete_is_refused_at_the_mutation_boundary_after_a_same_size_swap(self) -> None:
        """A scope file swapped inside the executor's preflight survives.

        The scope digest passes at admission (the file still matches the
        enumerated evidence); a concurrent writer then replaces it with
        same-size/different-mtime content before the executor's mutating
        Storage call.  The executor's size+mtime fence refuses the delete.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _tasks = self._activate(root)
            service = self._service(api, active)
            (root / "source" / "race-victim.txt").write_text("v1", encoding="utf-8")

            class SwapInDeletePreflight(OrganizerExecutor):
                def __init__(self, base: Path) -> None:
                    super().__init__()
                    self._base = base

                def _execute_direct(
                    self,
                    storage,
                    operation,
                    source,
                    target,
                    *,
                    execute,
                    mutation_authority,
                    preflight,
                    mutate,
                    verify,
                ):
                    def swap_then_preflight():
                        reason = preflight()
                        if reason is None:
                            # Same size, later mtime: only the executor's
                            # per-entry fence can still refuse this delete.
                            target_file = self._base / "source" / "race-victim.txt"
                            target_file.write_text("v2", encoding="utf-8")
                            later = datetime.now(UTC) + timedelta(seconds=120)
                            os.utime(target_file, (later.timestamp(), later.timestamp()))
                            return preflight()
                        return reason

                    return super()._execute_direct(
                        storage,
                        operation,
                        source,
                        target,
                        execute=execute,
                        mutation_authority=mutation_authority,
                        preflight=swap_then_preflight,
                        mutate=mutate,
                        verify=verify,
                    )

            impact = service.delete_impact(resource_library_id="source", paths=["race-victim.txt"])
            with patch.object(service, "_executor", SwapInDeletePreflight(root)):
                outcome = service.execute_delete(
                    resource_library_id="source",
                    paths=["race-victim.txt"],
                    confirmation_digest=impact.scope_digest,
                )
            self.assertEqual(outcome["status"], "FAILED")
            self.assertEqual(outcome["failedItems"], 1)
            self.assertEqual(outcome["succeededItems"], 0)
            # The pre-mutation replacement survives the refused delete.
            self.assertEqual(
                (root / "source" / "race-victim.txt").read_text(encoding="utf-8"), "v2"
            )

    def test_delete_impact_document_stays_bounded_and_secret_free(self) -> None:
        """The browser-facing impact never discloses provider identity tokens."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _tasks = self._activate(root)
            service = self._service(api, active)
            (root / "source" / "victim").mkdir()
            (root / "source" / "victim" / "a.txt").write_text("a", encoding="utf-8")
            impact = service.delete_impact(resource_library_id="source", paths=["victim"])
            document = impact.document()
            rendered = json.dumps(document)
            self.assertNotIn("inode:", rendered)
            self.assertNotIn(str(root / "source"), rendered)
            self.assertTrue(document["scopeDigest"])
            for entry in document["entries"]:
                self.assertEqual(set(entry), {"path", "isDirectory", "size", "modifiedAt"})

    def test_confirmed_delete_refuses_a_replaced_empty_directory(self) -> None:
        """A same-name directory replacement after the confirmation fails closed.

        The executor fence uses the provider's stable directory identity (the
        inode segment of the Local fingerprint), so the replacement directory
        created after the operator confirmed the original survives.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _tasks = self._activate(root)
            binding = api._prepare_runtime_binding_for_revision(active)
            service = binding.direct_files
            library = service._library("source")
            storage = service._open_storage(library)
            (root / "source" / "victim").mkdir()
            observed = storage.stat("victim")
            evidence = EntryVersionEvidence(
                size=0,
                modified_at=observed.modified_at.isoformat(),
                is_directory=True,
                fingerprint=observed.fingerprint,
            )
            # Same-name replacement: rmdir + mkdir yields a new inode/ctime.
            storage.delete("victim")
            (root / "source" / "victim").mkdir()
            result = OrganizerExecutor().execute_direct_delete(
                storage, "victim", entry_evidence=evidence
            )
            self.assertEqual(result.status.value, "FAILED")
            self.assertTrue(
                any("entry changed since it was confirmed" in error for error in result.errors)
            )
            self.assertTrue((root / "source" / "victim").is_dir())

    def test_confirmed_recursive_delete_tolerates_confirmed_child_removals(self) -> None:
        """Deleting confirmed children must not break the parent directory fence.

        A confirmed recursive scope legitimately removes children first; the
        parent's provider identity (inode) stays stable across those removals
        and the confirmed parent directory is still deleted.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _tasks = self._activate(root)
            service = self._service(api, active)
            (root / "source" / "season").mkdir()
            (root / "source" / "season" / "inner").mkdir()
            (root / "source" / "season" / "inner" / "e1.mkv").write_bytes(b"01")
            (root / "source" / "season" / "e0.mkv").write_bytes(b"0")
            impact = service.delete_impact(resource_library_id="source", paths=["season"])
            outcome = service.execute_delete(
                resource_library_id="source",
                paths=["season"],
                confirmation_digest=impact.scope_digest,
            )
            self.assertEqual(outcome["status"], "SUCCESS")
            self.assertEqual(outcome["failedItems"], 0)
            self.assertFalse((root / "source" / "season").exists())

    def test_confirmed_recursive_delete_refuses_a_replaced_parent_directory(
        self,
    ) -> None:
        """A recursive parent replaced after confirmation keeps its new content.

        The replacement directory has a new provider identity, so the executor's
        directory-identity fence refuses the delete.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _tasks = self._activate(root)
            (root / "source" / "parent").mkdir()
            (root / "source" / "parent" / "old.txt").write_text("old", encoding="utf-8")
            binding = api._prepare_runtime_binding_for_revision(active)
            direct = binding.direct_files
            library = direct._library("source")
            storage = direct._open_storage(library)
            observed = storage.stat("parent")
            evidence = EntryVersionEvidence(
                size=0,
                modified_at=observed.modified_at.isoformat(),
                is_directory=True,
                fingerprint=observed.fingerprint,
            )
            # Replace the whole directory with different unconfirmed content.
            import shutil

            shutil.rmtree(root / "source" / "parent")
            (root / "source" / "parent").mkdir()
            (root / "source" / "parent" / "new.txt").write_text("new", encoding="utf-8")
            result = OrganizerExecutor().execute_direct_delete(
                storage, "parent", entry_evidence=evidence
            )
            self.assertEqual(result.status.value, "FAILED")
            self.assertTrue(
                any("entry changed since it was confirmed" in error for error in result.errors)
            )
            self.assertEqual(
                (root / "source" / "parent" / "new.txt").read_text(encoding="utf-8"), "new"
            )

    def test_confirmed_delete_refuses_a_replaced_directory_without_provider_identity(
        self,
    ) -> None:
        """No verifiable directory identity means no folder Delete.

        The provider-neutral probe strips Local's identity token, standing in for
        SMB/OpenList entries and S3 directory entries.  The operator's confirmed
        evidence of the original empty directory is submitted after that
        directory was replaced by a new empty directory at the same path: "it is
        still a directory" and "it is empty" are not identity, so the executor
        fails closed and the replacement survives.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            storage = _FingerprintlessStorage("storage", root)
            (root / "victim").mkdir()
            observed = storage.stat("victim")
            self.assertIsNone(observed.fingerprint)
            evidence = EntryVersionEvidence(
                size=0,
                modified_at=observed.modified_at.isoformat(),
                is_directory=True,
                fingerprint=observed.fingerprint,
            )
            # Same-name replacement: rmdir + mkdir of a fresh empty directory.
            storage.delete("victim")
            (root / "victim").mkdir()
            result = OrganizerExecutor().execute_direct_delete(
                storage, "victim", entry_evidence=evidence
            )
            self.assertEqual(result.status.value, "FAILED")
            self.assertEqual(tuple(result.uncertain_effects), ())
            self.assertTrue(
                any("verifiable directory identity" in error for error in result.errors)
            )
            # The replacement survives; the only delete ever issued was the
            # probe's own removal of the original directory.
            self.assertTrue((root / "victim").is_dir())
            self.assertEqual(storage.deleted, ["victim"])

    def test_folder_delete_requires_provider_directory_identity(self) -> None:
        """A provider without folder identity refuses Delete before any mutation.

        The same provider-neutral fake refuses the folder journey with an
        actionable reason, keeps the folder and its files untouched, creates no
        Task, and still deletes plain files, so the refusal is bounded to folders
        whose identity cannot be verified.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir(parents=True, exist_ok=True)
            storage = _FingerprintlessStorage("source-storage", root / "source")
            api, _objects, active, runtime = self._activate(
                root, storage_adapters={"source-storage": storage}
            )
            service = self._service(api, active)
            (root / "source" / "folder").mkdir()
            (root / "source" / "folder" / "keep.txt").write_text("keep", encoding="utf-8")
            (root / "source" / "single.txt").write_text("s", encoding="utf-8")

            with self.assertRaises(DirectFileError) as preview:
                service.delete_impact(resource_library_id="source", paths=["folder"])
            self.assertEqual(preview.exception.code, "files_direct_directory_identity_unavailable")
            self.assertEqual(preview.exception.category, "directory_identity_unavailable")
            self.assertEqual(preview.exception.status, 400)
            self.assertTrue(preview.exception.next_action)

            # The confirmed command refuses as well, including for a mixed
            # selection: nothing is deleted and no Task is created.
            with self.assertRaises(DirectFileError):
                service.execute_delete(
                    resource_library_id="source",
                    paths=["folder", "single.txt"],
                    confirmation_digest="0" * 64,
                )
            self.assertEqual(storage.deleted, [])
            self.assertEqual(runtime.list_tasks(), ())
            self.assertTrue((root / "source" / "folder" / "keep.txt").is_file())
            self.assertTrue((root / "source" / "single.txt").is_file())

            # The API shares the exact application refusal.
            status, body = request(
                api,
                "/api/v1/resource-libraries/source/files/delete-impact?path=folder",
            )
            self.assertEqual(status, 400, body)
            self.assertEqual(body["error"]["code"], "files_direct_directory_identity_unavailable")
            self.assertEqual(body["error"]["details"]["category"], "directory_identity_unavailable")
            self.assertEqual(body["error"]["details"]["sideEffects"], "none")

            # Plain file Delete still works on the same provider: the refusal is
            # bounded to folders without a verifiable identity.
            impact = service.delete_impact(resource_library_id="source", paths=["single.txt"])
            outcome = service.execute_delete(
                resource_library_id="source",
                paths=["single.txt"],
                confirmation_digest=impact.scope_digest,
            )
            self.assertEqual(outcome["status"], "SUCCESS")
            self.assertFalse((root / "source" / "single.txt").exists())
            self.assertEqual(storage.deleted, ["single.txt"])

    def test_delete_result_status_names_the_known_durable_effect(self) -> None:
        """Every terminal Delete response carries the strict frontend status."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _tasks = self._activate(root)
            service = self._service(api, active)
            (root / "source" / "one.txt").write_text("1", encoding="utf-8")
            (root / "source" / "two.txt").write_text("2", encoding="utf-8")
            impact = service.delete_impact(
                resource_library_id="source", paths=["one.txt", "two.txt"]
            )
            outcome = service.execute_delete(
                resource_library_id="source",
                paths=["one.txt", "two.txt"],
                confirmation_digest=impact.scope_digest,
            )
            self.assertEqual(outcome["status"], "SUCCESS")
            self.assertTrue(outcome["succeededItems"] >= 1)
            # A frontend normalizer requiring `status` succeeds on the real shape.
            self.assertIsInstance(outcome["status"], str)
            self.assertTrue(outcome["status"])

            real_delete = LocalStorage.delete

            def failing_delete(storage_self, path, *args, **kwargs):
                if path.endswith("four.txt"):
                    raise RuntimeError("provider refused four.txt")
                return real_delete(storage_self, path, *args, **kwargs)

            (root / "source" / "three.txt").write_text("3", encoding="utf-8")
            (root / "source" / "four.txt").write_text("4", encoding="utf-8")
            impact = service.delete_impact(
                resource_library_id="source", paths=["three.txt", "four.txt"]
            )
            with patch.object(LocalStorage, "delete", failing_delete):
                partial = service.execute_delete(
                    resource_library_id="source",
                    paths=["three.txt", "four.txt"],
                    confirmation_digest=impact.scope_digest,
                )
            self.assertEqual(partial["status"], "PARTIAL")
            self.assertEqual(partial["failedItems"], 1)
            self.assertEqual(partial["succeededItems"], 1)
            # One bounded known-effect entry per confirmed top-level target,
            # in the deterministic sorted target order.
            self.assertEqual(
                partial["knownEffects"],
                [
                    {"path": "four.txt", "effect": "retained", "status": "FAILED"},
                    {"path": "three.txt", "effect": "deleted", "status": "SUCCESS"},
                ],
            )

    def test_large_directory_delete_reports_a_never_truncated_known_effect(self) -> None:
        """A >200-entry directory Delete still names its top-level effect.

        The per-item diagnostic outcomes are truncated for very large
        directories, but the bounded known-effect contract (one entry per
        confirmed top-level target) always identifies whether the selected
        directory itself was fully deleted, so the Web can reconcile the
        selection and the directory tree.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _tasks = self._activate(root)
            service = self._service(api, active)
            big = root / "source" / "big-dir"
            big.mkdir()
            for index in range(201):
                (big / f"file-{index:03}.txt").write_text("x", encoding="utf-8")
            impact = service.delete_impact(resource_library_id="source", paths=["big-dir"])
            # 201 files + the directory itself.
            self.assertEqual(len(impact.entries), 202)
            outcome = service.execute_delete(
                resource_library_id="source",
                paths=["big-dir"],
                confirmation_digest=impact.scope_digest,
            )
            self.assertEqual(outcome["status"], "SUCCESS")
            self.assertEqual(outcome["succeededItems"], 202)
            # The diagnostic outcomes are truncated…
            self.assertTrue(outcome["outcomesTruncated"])
            self.assertLessEqual(len(outcome["outcomes"]), 200)
            # …but the known effect still names the confirmed top-level target.
            self.assertEqual(
                outcome["knownEffects"],
                [{"path": "big-dir", "effect": "deleted", "status": "SUCCESS"}],
            )
            self.assertFalse(big.exists())

    def test_delete_impact_enumerates_bounded_scope_and_refuses_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _tasks = self._activate(root)
            service = self._service(api, active)
            (root / "source" / "season").mkdir()
            (root / "source" / "season" / "ep1").mkdir()
            (root / "source" / "season" / "ep1" / "e1.mkv").write_bytes(b"0123456789")
            (root / "source" / "season" / "e0.mkv").write_bytes(b"01")
            impact = service.delete_impact(resource_library_id="source", paths=["season"])
            self.assertEqual(impact.file_count, 2)
            self.assertEqual(impact.directory_count, 2)
            self.assertEqual(impact.total_bytes, 12)
            self.assertTrue(impact.scope_digest)
            self.assertEqual(len(impact.entries), 4)
            with self.assertRaises(DirectFileError) as root_protected:
                service.delete_impact(resource_library_id="source", paths=[""])
            self.assertEqual(root_protected.exception.category, "root_protected")
            with self.assertRaises(DirectFileError) as nested:
                service.delete_impact(resource_library_id="source", paths=["season", "season/ep1"])
            self.assertEqual(nested.exception.category, "invalid_request")
            outside = root / "outside.txt"
            outside.write_text("keep", encoding="utf-8")
            os.symlink(outside, root / "source" / "season" / "link.mkv")
            with self.assertRaises(DirectFileError) as escaped:
                service.delete_impact(resource_library_id="source", paths=["season"])
            self.assertEqual(escaped.exception.category, "symlink_not_supported")
            self.assertTrue(outside.exists())

    def test_impact_limits_stop_unbounded_enumeration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _tasks = self._activate(root)
            service = self._service(api, active)
            (root / "source" / "many").mkdir()
            for index in range(5):
                (root / "source" / "many" / f"file-{index}.txt").write_text("x", encoding="utf-8")
            with patch("mediaflow.application.direct_file_commands.MAX_IMPACT_ENTRIES", 3):
                with self.assertRaises(DirectFileError) as limited:
                    service.delete_impact(resource_library_id="source", paths=["many"])
            self.assertEqual(limited.exception.category, "impact_entry_limit_exceeded")
            self.assertEqual(limited.exception.status, 413)
            self.assertEqual(len(os.listdir(root / "source")), 1)
            self.assertEqual(len(os.listdir(root / "source" / "many")), 5)

    def test_confirmed_delete_removes_files_and_directories_with_durable_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            service = self._service(api, active)
            (root / "source" / "bulk").mkdir()
            (root / "source" / "bulk" / "inner").mkdir()
            (root / "source" / "bulk" / "inner" / "deep.txt").write_text("d", encoding="utf-8")
            (root / "source" / "bulk" / "top.txt").write_text("t", encoding="utf-8")
            (root / "source" / "single.txt").write_text("s", encoding="utf-8")
            impact = service.delete_impact(
                resource_library_id="source", paths=["bulk", "single.txt"]
            )
            self.assertEqual(impact.file_count, 3)
            self.assertEqual(impact.directory_count, 2)
            with self.assertRaises(DirectFileError) as mismatch:
                service.execute_delete(
                    resource_library_id="source",
                    paths=["bulk", "single.txt"],
                    confirmation_digest="0" * 64,
                )
            self.assertEqual(mismatch.exception.category, "stale_confirmation")
            self.assertTrue((root / "source" / "bulk").exists())
            outcome = service.execute_delete(
                resource_library_id="source",
                paths=["bulk", "single.txt"],
                confirmation_digest=impact.scope_digest,
            )
            self.assertEqual(outcome["operation"], "delete")
            self.assertEqual(outcome["failedItems"], 0)
            self.assertFalse((root / "source" / "bulk").exists())
            self.assertFalse((root / "source" / "single.txt").exists())
            task = runtime.get_task(outcome["taskId"])
            self.assertIsNotNone(task)
            self.assertEqual(task.command, "files_delete")
            items = runtime.list_items(outcome["taskId"])
            self.assertEqual(len(items), 5)
            self.assertTrue(all(item.status.value == "success" for item in items))

    def test_single_file_delete_uses_the_direct_command_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            service = self._service(api, active)
            (root / "source" / "one.txt").write_text("1", encoding="utf-8")
            impact = service.delete_impact(resource_library_id="source", paths=["one.txt"])
            outcome = service.execute_delete(
                resource_library_id="source",
                paths=["one.txt"],
                confirmation_digest=impact.scope_digest,
            )
            self.assertEqual(outcome["succeededItems"], 1)
            task = runtime.get_task(outcome["taskId"])
            self.assertEqual(task.command, "files_direct_command")
            self.assertFalse((root / "source" / "one.txt").exists())

    def test_delete_partial_failure_keeps_independent_item_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            service = self._service(api, active)
            (root / "source" / "batch").mkdir()
            (root / "source" / "batch" / "one.txt").write_text("1", encoding="utf-8")
            (root / "source" / "batch" / "two.txt").write_text("2", encoding="utf-8")
            impact = service.delete_impact(resource_library_id="source", paths=["batch"])

            real_delete = LocalStorage.delete

            def selective_delete(storage_self, path, *args, **kwargs):
                if path.endswith("one.txt"):
                    raise RuntimeError("provider refused one.txt")
                return real_delete(storage_self, path, *args, **kwargs)

            with patch.object(LocalStorage, "delete", selective_delete):
                outcome = service.execute_delete(
                    resource_library_id="source",
                    paths=["batch"],
                    confirmation_digest=impact.scope_digest,
                )
            self.assertEqual(outcome["failedItems"], 2)
            self.assertEqual(outcome["succeededItems"], 1)
            self.assertEqual(outcome["taskStatus"], "partial_success")
            self.assertFalse((root / "source" / "batch" / "two.txt").exists())
            self.assertTrue((root / "source" / "batch" / "one.txt").exists())
            self.assertTrue((root / "source" / "batch").is_dir())
            failed = [item for item in runtime.list_items(outcome["taskId"]) if item.error]
            self.assertEqual(len(failed), 2)
            self.assertTrue(all(item.error for item in failed))

    def test_every_mutation_crosses_organizer_executor_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executor = _CountingExecutor()
            (root / "source").mkdir(parents=True, exist_ok=True)
            recording = _RecordingStorage("source-storage", root / "source", executor)
            api, _objects, active, _tasks = self._activate(
                root, storage_adapters={"source-storage": recording}
            )
            with patch(
                "mediaflow.application.direct_file_commands.OrganizerExecutor",
                lambda: executor,
            ):
                binding = api._prepare_runtime_binding_for_revision(active)
            service = binding.direct_files
            self.assertIs(service._executor, executor)
            service.create_directory(resource_library_id="source", parent_path="", name="d1")
            service.create_text(
                resource_library_id="source", parent_path="", name="n.txt", content="x"
            )
            service.rename(
                resource_library_id="source",
                path="n.txt",
                name="m.txt",
                expected=_entry_evidence(api, active, "source", "n.txt"),
            )
            loaded = service.read_text(resource_library_id="source", path="m.txt")
            service.save_text(
                resource_library_id="source",
                path="m.txt",
                content="y",
                expected=loaded.evidence.document(),
            )
            impact = service.delete_impact(resource_library_id="source", paths=["m.txt"])
            service.execute_delete(
                resource_library_id="source",
                paths=["m.txt"],
                confirmation_digest=impact.scope_digest,
            )
            self.assertEqual(
                executor.boundaries,
                [
                    "DIRECT:CREATE_DIRECTORY",
                    "DIRECT:WRITE",
                    "DIRECT:RENAME",
                    "DIRECT:WRITE",
                    "DIRECT:DELETE",
                ],
            )
            self.assertTrue(recording.mutations)
            self.assertTrue(all(via for _method, via in recording.mutations))

    def test_read_only_storage_denies_mutation_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = MutationFreeStorage("source-storage", read_only=True)
            api, _objects, active, _tasks = self._activate(
                root, storage_adapters={"source-storage": fake}
            )
            service = self._service(api, active)
            for call in (
                lambda: service.create_directory(
                    resource_library_id="source", parent_path="", name="blocked"
                ),
                lambda: service.create_text(
                    resource_library_id="source", parent_path="", name="a.txt", content=""
                ),
                lambda: service.rename(
                    resource_library_id="source",
                    path="a.txt",
                    name="b.txt",
                    expected={"size": 1, "modifiedAt": "1970-01-01T00:00:00+00:00"},
                ),
            ):
                with self.assertRaises(DirectFileError) as caught:
                    call()
                self.assertEqual(caught.exception.category, "capability_denied")
                self.assertEqual(caught.exception.status, 403)
            self.assertEqual(fake.mutations, [])

    def test_commands_persist_exact_logical_source_and_target(self) -> None:
        """Every command's durable record names its bounded logical paths."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            service = self._service(api, active)
            created = service.create_directory(
                resource_library_id="source", parent_path="", name="created-dir"
            )
            results = runtime.list_results(created["taskId"])
            self.assertEqual(results[0].source_path, "created-dir")
            self.assertEqual(results[0].destination_path, "created-dir")

            text = service.create_text(
                resource_library_id="source", parent_path="", name="file.txt", content="x"
            )
            results = runtime.list_results(text["taskId"])
            self.assertEqual(results[0].source_path, "file.txt")
            self.assertEqual(results[0].destination_path, "file.txt")

            renamed = service.rename(
                resource_library_id="source",
                path="file.txt",
                name="moved.txt",
                expected=_entry_evidence(api, active, "source", "file.txt"),
            )
            results = runtime.list_results(renamed["taskId"])
            self.assertEqual(results[0].source_path, "file.txt")
            self.assertEqual(results[0].destination_path, "moved.txt")

            saved = service.save_text(
                resource_library_id="source",
                path="moved.txt",
                content="y",
                expected=_loaded_evidence(service, "source", "moved.txt"),
            )
            results = runtime.list_results(saved["taskId"])
            self.assertEqual(results[0].source_path, "moved.txt")
            self.assertEqual(results[0].destination_path, "moved.txt")

            impact = service.delete_impact(resource_library_id="source", paths=["moved.txt"])
            deleted = service.execute_delete(
                resource_library_id="source",
                paths=["moved.txt"],
                confirmation_digest=impact.scope_digest,
            )
            results = runtime.list_results(deleted["taskId"])
            self.assertEqual(results[0].source_path, "moved.txt")
            self.assertEqual(results[0].destination_path, "moved.txt")
            # Host roots never enter the durable identity.
            for record in (
                *runtime.list_results(created["taskId"]),
                *runtime.list_results(text["taskId"]),
                *runtime.list_results(renamed["taskId"]),
                *runtime.list_results(saved["taskId"]),
                *runtime.list_results(deleted["taskId"]),
            ):
                self.assertNotIn(str(root / "source"), json.dumps(record.__dict__, default=str))

    def test_commands_never_persist_text_contents_or_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            service = self._service(api, active)
            secret_text = "SECRET-EDITOR-CONTENT-9f3b1c"
            outcome = service.create_text(
                resource_library_id="source",
                parent_path="",
                name="secret.txt",
                content=secret_text,
            )
            for record in runtime.list_results(outcome["taskId"]):
                self.assertNotIn(secret_text, json.dumps(record.__dict__, default=str))
            for item in runtime.list_items(outcome["taskId"]):
                self.assertNotIn(secret_text, json.dumps(item.__dict__, default=str))

    # ------------------------------------------------------------------
    # API journeys
    # ------------------------------------------------------------------

    def test_api_command_routes_share_application_behavior_and_rbac(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, _active, runtime = self._activate(root)
            status, body = request(
                api,
                "/api/v1/resource-libraries/source/files/commands",
                method="POST",
                body={"operation": "create_directory", "parentPath": "", "name": "via-api"},
                token="admin-token",
            )
            self.assertEqual(status, 200, body)
            self.assertEqual(body["status"], "SUCCESS")
            self.assertTrue((root / "source" / "via-api").is_dir())
            task = runtime.get_task(body["taskId"])
            self.assertIsNotNone(task)
            self.assertEqual(task.command, "files_direct_command")
            forbidden = request(
                api,
                "/api/v1/resource-libraries/source/files/commands",
                method="POST",
                body={"operation": "create_directory", "parentPath": "", "name": "denied"},
                token="viewer-token",
            )
            self.assertEqual(forbidden[0], 403, forbidden[1])
            self.assertEqual(forbidden[1]["error"]["code"], "forbidden")
            self.assertFalse((root / "source" / "denied").exists())
            bad = request(
                api,
                "/api/v1/resource-libraries/source/files/commands",
                method="POST",
                body={"operation": "teleport", "parentPath": "", "name": "x"},
            )
            self.assertEqual(bad[0], 400)
            unknown = request(
                api,
                "/api/v1/resource-libraries/missing/files/commands",
                method="POST",
                body={"operation": "create_directory", "parentPath": "", "name": "x"},
            )
            self.assertEqual(unknown[0], 404)
            self.assertEqual(unknown[1]["error"]["code"], "files_direct_resource_library_not_found")

    def test_api_text_read_and_impact_routes_are_bounded_reads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, _active, _tasks = self._activate(root)
            (root / "source" / "doc.txt").write_text("api text", encoding="utf-8")
            status, body = request(
                api,
                "/api/v1/resource-libraries/source/files/text?path=doc.txt",
            )
            self.assertEqual(status, 200, body)
            self.assertEqual(body["content"], "api text")
            self.assertEqual(body["sideEffects"], "none")
            self.assertIn("digest", body["evidence"])
            status, body = request(
                api,
                "/api/v1/resource-libraries/source/files/delete-impact?path=doc.txt",
            )
            self.assertEqual(status, 200, body)
            self.assertEqual(body["fileCount"], 1)
            self.assertTrue(body["scopeDigest"])
            missing = request(
                api,
                "/api/v1/resource-libraries/source/files/delete-impact",
            )
            self.assertEqual(missing[0], 400)

    def test_api_stale_save_and_conflict_failures_are_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, _active, _tasks = self._activate(root)
            (root / "source" / "doc.txt").write_text("v1", encoding="utf-8")
            _status, loaded = request(
                api,
                "/api/v1/resource-libraries/source/files/text?path=doc.txt",
            )
            (root / "source" / "doc.txt").write_text("v2", encoding="utf-8")
            stale = request(
                api,
                "/api/v1/resource-libraries/source/files/commands",
                method="POST",
                body={
                    "operation": "save_text",
                    "path": "doc.txt",
                    "content": "editor edits",
                    "expected": loaded["evidence"],
                },
            )
            self.assertEqual(stale[0], 409, stale[1])
            self.assertEqual(stale[1]["error"]["code"], "files_direct_stale_content")
            self.assertEqual(stale[1]["error"]["details"]["category"], "stale_changed")
            self.assertIn("nextAction", stale[1]["error"]["details"])
            self.assertEqual((root / "source" / "doc.txt").read_text(encoding="utf-8"), "v2")

    def test_api_rename_requires_and_enforces_observed_evidence(self) -> None:
        """The API rejects Rename without observed evidence and stale swaps."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _tasks = self._activate(root)
            (root / "source" / "before.txt").write_text("v1", encoding="utf-8")
            missing_evidence = request(
                api,
                "/api/v1/resource-libraries/source/files/commands",
                method="POST",
                body={"operation": "rename", "path": "before.txt", "name": "after.txt"},
            )
            self.assertEqual(missing_evidence[0], 400, missing_evidence[1])
            self.assertEqual(missing_evidence[1]["error"]["code"], "invalid_request")
            self.assertTrue((root / "source" / "before.txt").exists())
            status, listing = request(
                api,
                "/api/v1/resource-libraries/source/files?path=",
            )
            self.assertEqual(status, 200, listing)
            entry = next(item for item in listing["entries"] if item["name"] == "before.txt")
            (root / "source" / "before.txt").write_text("v2", encoding="utf-8")
            later = datetime.now(UTC) + timedelta(seconds=120)
            os.utime(root / "source" / "before.txt", (later.timestamp(), later.timestamp()))
            stale = request(
                api,
                "/api/v1/resource-libraries/source/files/commands",
                method="POST",
                body={
                    "operation": "rename",
                    "path": "before.txt",
                    "name": "after.txt",
                    "expected": {
                        "size": entry["size"],
                        "modifiedAt": entry["modifiedAt"],
                    },
                },
            )
            self.assertEqual(stale[0], 409, stale[1])
            self.assertEqual(stale[1]["error"]["code"], "files_direct_stale_source")
            self.assertTrue((root / "source" / "before.txt").exists())
            self.assertFalse((root / "source" / "after.txt").exists())
            fresh = _entry_evidence(api, active, "source", "before.txt")
            ok = request(
                api,
                "/api/v1/resource-libraries/source/files/commands",
                method="POST",
                body={
                    "operation": "rename",
                    "path": "before.txt",
                    "name": "after.txt",
                    "expected": fresh,
                },
            )
            self.assertEqual(ok[0], 200, ok[1])
            self.assertEqual(ok[1]["status"], "SUCCESS")
            self.assertEqual(ok[1]["target"], "after.txt")
            self.assertTrue((root / "source" / "after.txt").exists())

    # ------------------------------------------------------------------
    # ResourceLibrary removal journey
    # ------------------------------------------------------------------

    def _save_library(self, api, library_id: str, *, storage_id: str = "source-storage"):
        status, body = request(
            api,
            "/api/v1/resource-libraries",
            method="POST",
            body={
                "resourceLibraryId": library_id,
                "name": f"Library {library_id}",
                "enabled": True,
                "storageId": storage_id,
                "storagePath": f"incoming/{library_id}",
            },
        )
        self.assertEqual(status, 200, body)
        return body

    def test_removal_preview_reports_references_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, _active, _tasks = self._activate(root)
            status, body = request(
                api,
                "/api/v1/resource-libraries/source/removal-preview",
            )
            self.assertEqual(status, 200, body)
            self.assertEqual(body["resourceLibrary"]["id"], "source")
            self.assertEqual(body["storage"]["id"], "source-storage")
            self.assertGreaterEqual(body["references"]["total"], 1)
            self.assertEqual(body["sideEffects"], "none")

    def test_referenced_library_cannot_be_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, _active, _tasks = self._activate(root)
            (root / "source" / "keep.txt").write_text("keep", encoding="utf-8")
            status, preview = request(
                api,
                "/api/v1/resource-libraries/source/removal-preview",
            )
            self.assertEqual(status, 200, preview)
            status, body = request(
                api,
                "/api/v1/resource-libraries/source",
                method="DELETE",
                body=_removal_confirmation(preview),
            )
            self.assertEqual(status, 409, body)
            self.assertEqual(body["error"]["code"], "configuration_object_referenced")
            self.assertGreaterEqual(body["error"]["details"]["referenceCount"], 1)
            self.assertTrue((root / "source" / "keep.txt").exists())
            status, libraries = request(
                api,
                "/api/v1/resource-libraries/files",
            )
            self.assertEqual(status, 200)
            self.assertEqual(libraries["total"], 1)

    def test_unreferenced_removal_publishes_successor_and_keeps_storage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, _active, _tasks = self._activate(
                root,
                document_overrides=_unreference_source,
            )
            self._save_library(api, "second")
            (root / "source" / "movie.mkv").write_bytes(b"\x00mkv-bytes")
            (root / "source" / "nested").mkdir()
            (root / "source" / "nested" / "deep.txt").write_text("deep", encoding="utf-8")
            before = self._tree_bytes(root / "source")
            status, preview = request(
                api,
                "/api/v1/resource-libraries/second/removal-preview",
            )
            self.assertEqual(status, 200, preview)
            status, body = request(
                api,
                "/api/v1/resource-libraries/second",
                method="DELETE",
                body=_removal_confirmation(preview),
            )
            self.assertEqual(status, 200, body)
            self.assertEqual(body["removed"]["id"], "second")
            self.assertEqual(body["sideEffects"], "configuration_only")
            self.assertEqual(self._tree_bytes(root / "source"), before)
            status, libraries = request(api, "/api/v1/resource-libraries/files")
            self.assertEqual(status, 200)
            self.assertEqual([item["id"] for item in libraries["items"]], ["source"])
            status, browse = request(api, "/api/v1/resource-libraries/source/files?path=")
            self.assertEqual(status, 200, browse)
            self.assertEqual(browse["resourceLibrary"]["id"], "source")

    def test_removing_the_final_library_reaches_the_empty_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, _active, _tasks = self._activate(
                root,
                document_overrides=_unreference_source,
            )
            (root / "source" / "still-here.txt").write_text("data", encoding="utf-8")
            before = self._tree_bytes(root / "source")
            status, preview = request(
                api,
                "/api/v1/resource-libraries/source/removal-preview",
            )
            self.assertEqual(status, 200, preview)
            status, body = request(
                api,
                "/api/v1/resource-libraries/source",
                method="DELETE",
                body=_removal_confirmation(preview),
            )
            self.assertEqual(status, 200, body)
            self.assertEqual(self._tree_bytes(root / "source"), before)
            status, libraries = request(api, "/api/v1/resource-libraries/files")
            self.assertEqual(status, 200)
            self.assertEqual(libraries["items"], [])
            self.assertEqual(libraries["total"], 0)
            status, browse = request(api, "/api/v1/resource-libraries/source/files?path=")
            self.assertEqual(status, 404)

    def test_removal_never_invokes_organizer_executor_or_storage_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = MutationFreeStorage("source-storage")
            api, _objects, _active, _tasks = self._activate(
                root,
                storage_adapters={"source-storage": fake},
                document_overrides=_unreference_source,
            )
            with patch.object(OrganizerExecutor, "execute") as execute:
                status, preview = request(
                    api,
                    "/api/v1/resource-libraries/source/removal-preview",
                )
                self.assertEqual(status, 200, preview)
                status, body = request(
                    api,
                    "/api/v1/resource-libraries/source",
                    method="DELETE",
                    body=_removal_confirmation(preview),
                )
                self.assertEqual(status, 200, body)
                execute.assert_not_called()
            self.assertEqual(fake.mutations, [])

    def test_removal_requires_configuration_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, _active, _tasks = self._activate(root)
            status, preview = request(
                api,
                "/api/v1/resource-libraries/source/removal-preview",
            )
            self.assertEqual(status, 200, preview)
            status, body = request(
                api,
                "/api/v1/resource-libraries/source",
                method="DELETE",
                token="viewer-token",
                body=_removal_confirmation(preview),
            )
            self.assertEqual(status, 403, body)
            self.assertEqual(body["error"]["code"], "forbidden")

    def test_missing_library_removal_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, _active, _tasks = self._activate(root)
            self._save_library(api, "does-not-exist-target")
            status, preview = request(
                api,
                "/api/v1/resource-libraries/source/removal-preview",
            )
            self.assertEqual(status, 200, preview)
            confirmation = _removal_confirmation(preview)
            confirmation["expectedLibraryId"] = "does-not-exist"
            status, body = request(
                api,
                "/api/v1/resource-libraries/does-not-exist",
                method="DELETE",
                body=confirmation,
            )
            self.assertEqual(status, 404, body)
            self.assertEqual(body["error"]["code"], "resource_library_not_found")

    def test_stale_active_revision_refuses_removal(self) -> None:
        """A confirmation previewed against an older Active cannot remove."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, _active, _tasks = self._activate(
                root,
                document_overrides=_unreference_source,
            )
            self._save_library(api, "second")
            self._save_library(api, "third")
            _status, preview = request(
                api,
                "/api/v1/resource-libraries/third/removal-preview",
            )
            stale_confirmation = _removal_confirmation(preview)
            # The Active revision advances after the operator previewed.
            self._save_library(api, "fourth")
            status, body = request(
                api,
                "/api/v1/resource-libraries/third",
                method="DELETE",
                body=stale_confirmation,
            )
            self.assertEqual(status, 409, body)
            self.assertEqual(body["error"]["code"], "resource_library_removal_stale")
            self.assertEqual(body["error"]["details"]["durableState"], "active_preserved")
            status, libraries = request(api, "/api/v1/resource-libraries/files")
            self.assertEqual(status, 200)
            self.assertEqual(
                sorted(item["id"] for item in libraries["items"]),
                ["fourth", "second", "source", "third"],
            )

    def test_mismatched_library_identity_refuses_removal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, _active, _tasks = self._activate(
                root,
                document_overrides=_unreference_source,
            )
            self._save_library(api, "second")
            _status, preview = request(
                api,
                "/api/v1/resource-libraries/second/removal-preview",
            )
            confirmation = _removal_confirmation(preview)
            confirmation["expectedLibraryId"] = "source"
            status, body = request(
                api,
                "/api/v1/resource-libraries/second",
                method="DELETE",
                body=confirmation,
            )
            self.assertEqual(status, 409, body)
            self.assertEqual(body["error"]["code"], "resource_library_removal_stale")
            status, libraries = request(api, "/api/v1/resource-libraries/files")
            self.assertEqual(status, 200)
            self.assertEqual(
                sorted(item["id"] for item in libraries["items"]),
                ["second", "source"],
            )

    def test_disabled_library_cannot_be_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, _active, _tasks = self._activate(
                root,
                document_overrides=lambda doc: (
                    _unreference_source(doc),
                    doc["resourceLibraries"].append(
                        {
                            "id": "disabled-lib",
                            "name": "Disabled library",
                            "enabled": False,
                            "storageId": "source-storage",
                            "storagePath": "incoming/disabled",
                        }
                    ),
                ),
            )
            status, preview = request(
                api,
                "/api/v1/resource-libraries/disabled-lib/removal-preview",
            )
            self.assertEqual(status, 200, preview)
            self.assertEqual(preview["resourceLibrary"]["enabled"], False)
            status, body = request(
                api,
                "/api/v1/resource-libraries/disabled-lib",
                method="DELETE",
                body=_removal_confirmation(preview),
            )
            self.assertEqual(status, 409, body)
            self.assertEqual(body["error"]["code"], "resource_library_disabled")
            self.assertEqual(body["error"]["details"]["durableState"], "active_preserved")
            # The disabled library stays configured: the preview still resolves
            # it and still refuses removal.
            status, preview_again = request(
                api,
                "/api/v1/resource-libraries/disabled-lib/removal-preview",
            )
            self.assertEqual(status, 200, preview_again)
            self.assertEqual(preview_again["resourceLibrary"]["enabled"], False)

    def test_removal_confirmation_requires_the_previewed_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, _active, _tasks = self._activate(
                root,
                document_overrides=_unreference_source,
            )
            self._save_library(api, "second")
            for incomplete in (
                {},
                {"expectedRevisionId": "r"},
                {
                    "expectedRevisionId": "r",
                    "expectedVersion": 1,
                    "expectedDigest": "d",
                },
            ):
                status, body = request(
                    api,
                    "/api/v1/resource-libraries/second",
                    method="DELETE",
                    body=incomplete,
                )
                self.assertEqual(status, 400, body)
            status, libraries = request(api, "/api/v1/resource-libraries/files")
            self.assertEqual(status, 200)
            self.assertEqual(
                sorted(item["id"] for item in libraries["items"]),
                ["second", "source"],
            )

    @staticmethod
    def _tree_bytes(base: Path) -> dict[str, bytes]:
        snapshot: dict[str, bytes] = {}
        for path in sorted(base.rglob("*")):
            relative = str(path.relative_to(base))
            snapshot[relative] = path.read_bytes() if path.is_file() else b"<dir>"
        return snapshot


if __name__ == "__main__":
    unittest.main()
