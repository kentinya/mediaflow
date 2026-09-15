from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
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
            rename = service.rename(resource_library_id="source", path="movies/2024", name="2025")
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
            service.rename(resource_library_id="source", path="n.txt", name="m.txt")
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
                lambda: service.rename(resource_library_id="source", path="a.txt", name="b.txt"),
            ):
                with self.assertRaises(DirectFileError) as caught:
                    call()
                self.assertEqual(caught.exception.category, "capability_denied")
                self.assertEqual(caught.exception.status, 403)
            self.assertEqual(fake.mutations, [])

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
            status, body = request(
                api,
                "/api/v1/resource-libraries/source",
                method="DELETE",
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
            status, body = request(
                api,
                "/api/v1/resource-libraries/second",
                method="DELETE",
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
            status, body = request(
                api,
                "/api/v1/resource-libraries/source",
                method="DELETE",
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
                status, body = request(
                    api,
                    "/api/v1/resource-libraries/source",
                    method="DELETE",
                )
                self.assertEqual(status, 200, body)
                execute.assert_not_called()
            self.assertEqual(fake.mutations, [])

    def test_removal_requires_configuration_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, _active, _tasks = self._activate(root)
            status, body = request(
                api,
                "/api/v1/resource-libraries/source",
                method="DELETE",
                token="viewer-token",
            )
            self.assertEqual(status, 403, body)
            self.assertEqual(body["error"]["code"], "forbidden")

    def test_missing_library_removal_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, _active, _tasks = self._activate(root)
            status, body = request(
                api,
                "/api/v1/resource-libraries/does-not-exist",
                method="DELETE",
            )
            self.assertEqual(status, 404, body)
            self.assertEqual(body["error"]["code"], "resource_library_not_found")

    @staticmethod
    def _tree_bytes(base: Path) -> dict[str, bytes]:
        snapshot: dict[str, bytes] = {}
        for path in sorted(base.rglob("*")):
            relative = str(path.relative_to(base))
            snapshot[relative] = path.read_bytes() if path.is_file() else b"<dir>"
        return snapshot


if __name__ == "__main__":
    unittest.main()
