"""Focused evidence for the bounded Files Copy/Move transfer journey.

Covers the same-Storage native Copy/Move, the composed bounded directory
transfer, the explicit cross-Storage compound Move with its durable
copy -> verify -> delete-source checkpoints, explicit conflict behavior,
fail-closed admission, stale-manifest refusal, the repeated-`path` Delete
impact contract and OrganizerExecutor-only mutation.  Every endpoint is a
temporary local root or an in-process fake; no production service is used.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.direct_file_transfers import DirectFileTransferService
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.domain.configuration_management import (
    ConfigurationDestinationPrecheckStatus,
    ConfigurationStorageCheckStatus,
    ConfigurationStrategyTestStatus,
)
from mediaflow.domain.direct_files import (
    TransferConflictMode,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.storage import (
    StorageCapabilities,
    StorageEntry,
)
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


class _ReadOnlyProvider(LocalStorage):
    """A provider that advertises no native capability and refuses mutation."""

    @property
    def capabilities(self) -> StorageCapabilities:
        return StorageCapabilities()

    def copy(self, *args, **kwargs):
        raise AssertionError("no native Copy may be attempted")

    def move(self, *args, **kwargs):
        raise AssertionError("no native Move may be attempted")

    def delete(self, *args, **kwargs):
        raise AssertionError("no Delete may be attempted")

    def write(self, *args, **kwargs):
        raise AssertionError("no Write may be attempted")


class _NoIdentityProvider(LocalStorage):
    """A provider whose entries publish no verifiable entry identity.

    This is the provider-neutral stand-in for OpenList/SMB regular entries: a
    cross-Storage Move may stream and verify the Copy, but the exact destructive
    source deletion is unavailable and must end as a verified-copy/source-retained
    partial outcome.
    """

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


class _TruncatingTarget(LocalStorage):
    """A target whose write silently truncates the streamed payload."""

    def write(self, path: str, data, *, overwrite: bool = False) -> None:
        if hasattr(data, "read"):
            data = data.read(3)
        super().write(path, data, overwrite=overwrite)


class _CountingExecutor(OrganizerExecutor):
    """Executor double that records the mutation boundaries actually crossed."""

    def __init__(self) -> None:
        super().__init__()
        self.boundaries: list[str] = []

    def execute_direct_create_directory(self, storage, path, **kwargs):
        self.boundaries.append("CREATE_DIRECTORY")
        return super().execute_direct_create_directory(storage, path, **kwargs)

    def execute_direct_copy(self, *args, **kwargs):
        self.boundaries.append("COPY")
        return super().execute_direct_copy(*args, **kwargs)

    def execute_direct_move(self, *args, **kwargs):
        self.boundaries.append("MOVE")
        return super().execute_direct_move(*args, **kwargs)

    def execute_direct_remove_empty_directory(self, *args, **kwargs):
        self.boundaries.append("DELETE_EMPTY_DIRECTORY")
        return super().execute_direct_remove_empty_directory(*args, **kwargs)


class TransferTestCase(unittest.TestCase):
    """Shared temporary-root fixture with one source and one destination library."""

    def _document(self, root: Path) -> dict[str, object]:
        document = example_document()
        document["persistence"]["databasePath"] = str(root / "configuration.sqlite3")
        document["storages"][0]["rootPath"] = str(root / "source")
        document["storages"][1]["rootPath"] = str(root / "destination")
        document["resourceLibraries"][0]["storagePath"] = ""
        document["mediaLibraries"][0]["rootPath"] = "Movies"
        # A second enabled ResourceLibrary on the other Storage makes the
        # cross-Storage journey explicit without inventing a new provider.
        document["resourceLibraries"].append(
            {
                "id": "destination",
                "name": "Destination",
                "storageId": "media-target",
                "storagePath": "",
                "enabled": True,
                "extensions": ["mkv"],
            }
        )
        return document

    def _activate(self, root: Path, *, storage_adapters=None):
        document = self._document(root)
        (root / "source").mkdir(parents=True, exist_ok=True)
        (root / "destination" / "Movies").mkdir(parents=True, exist_ok=True)
        configuration_repository = SQLiteConfigurationRepository(root / "configuration.sqlite3")
        self.addCleanup(configuration_repository.close)
        service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=str(root / "configuration.sqlite3"),
        )
        objects = ConfigurationObjectService(
            service,
            storage_adapters=storage_adapters,
            storage_browser_cursor_secret="transfer-test-secret",
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
            storage_browser_cursor_secret="transfer-test-secret",
        )
        return api, active, runtime_repository

    def _transfers(self, api, active, *, executor=None) -> DirectFileTransferService:
        binding = api._prepare_runtime_binding_for_revision(active)
        self.assertIsNotNone(binding.direct_files)
        return DirectFileTransferService(
            direct_files=binding.direct_files,
            executor=executor or OrganizerExecutor(),
        )


class SameStorageTransferTests(TransferTestCase):
    def test_same_storage_file_copy_and_move_use_only_the_native_operation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            executor = _CountingExecutor()
            transfers = self._transfers(api, active, executor=executor)
            (root / "source" / "a.mkv").write_bytes(b"media-a")
            (root / "source" / "b.mkv").write_bytes(b"media-b")
            (root / "source" / "Movies").mkdir()

            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
            )
            self.assertEqual(impact.manifest.same_storage, True)
            self.assertEqual(impact.capability, "native_copy")
            result = transfers.execute_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            self.assertEqual(result["status"], "SUCCESS")
            self.assertTrue((root / "source" / "a.mkv").exists())
            self.assertEqual((root / "source" / "Movies" / "a.mkv").read_bytes(), b"media-a")

            move_impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["b.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="move",
            )
            moved = transfers.execute_transfer(
                resource_library_id="source",
                paths=["b.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="move",
                conflict_mode="fail",
                manifest_digest=move_impact.manifest.digest,
            )
            self.assertEqual(moved["status"], "SUCCESS")
            self.assertFalse((root / "source" / "b.mkv").exists())
            self.assertEqual((root / "source" / "Movies" / "b.mkv").read_bytes(), b"media-b")
            self.assertEqual(executor.boundaries, ["COPY", "MOVE"])
            task = runtime.get_task(moved["taskId"])
            self.assertEqual(task.command, "files_direct_command")

    def test_bounded_directory_copy_and_move_plan_every_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            executor = _CountingExecutor()
            transfers = self._transfers(api, active, executor=executor)
            tree = root / "source" / "show" / "season1"
            tree.mkdir(parents=True)
            (tree / "one.mkv").write_bytes(b"one")
            (tree / "two.mkv").write_bytes(b"two")
            (root / "source" / "Movies").mkdir()
            (root / "source" / "Archive").mkdir()

            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["show"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
            )
            self.assertEqual(
                sorted(entry.path for entry in impact.manifest.entries),
                ["show", "show/season1", "show/season1/one.mkv", "show/season1/two.mkv"],
            )
            copied = transfers.execute_transfer(
                resource_library_id="source",
                paths=["show"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            self.assertEqual(copied["status"], "SUCCESS")
            self.assertTrue((root / "source" / "show" / "season1" / "one.mkv").exists())
            self.assertTrue((root / "source" / "Movies" / "show" / "season1" / "one.mkv").exists())
            self.assertIn("CREATE_DIRECTORY", executor.boundaries)
            self.assertEqual(copied["taskStatus"], "completed")

            move_impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["show"],
                destination_resource_library_id="source",
                destination_directory="Archive",
                operation="move",
            )
            moved = transfers.execute_transfer(
                resource_library_id="source",
                paths=["show"],
                destination_resource_library_id="source",
                destination_directory="Archive",
                operation="move",
                conflict_mode="fail",
                manifest_digest=move_impact.manifest.digest,
            )
            self.assertEqual(moved["status"], "SUCCESS")
            self.assertFalse((root / "source" / "show").exists())
            self.assertTrue((root / "source" / "Archive" / "show" / "season1" / "one.mkv").exists())
            self.assertTrue((root / "source" / "Archive" / "show" / "season1" / "two.mkv").exists())
            self.assertEqual(moved["taskStatus"], "completed")

    def test_provider_without_native_capability_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir(parents=True, exist_ok=True)
            (root / "destination").mkdir(parents=True, exist_ok=True)
            read_only = _ReadOnlyProvider("source-storage", root / "source")
            api, active, _runtime = self._activate(
                root, storage_adapters={"source-storage": read_only}
            )
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media")
            (root / "source" / "Movies").mkdir()
            with self.assertRaises(Exception) as caught:
                transfers.transfer_impact(
                    resource_library_id="source",
                    paths=["a.mkv"],
                    destination_resource_library_id="source",
                    destination_directory="Movies",
                    operation="move",
                )
            self.assertIn("unsupported_capability", str(caught.exception.code))
            self.assertTrue((root / "source" / "a.mkv").exists())


class ConflictTests(TransferTestCase):
    def _prepare(self, root: Path):
        api, active, runtime = self._activate(root)
        transfers = self._transfers(api, active)
        (root / "source" / "a.mkv").write_bytes(b"media")
        (root / "source" / "Movies").mkdir()
        (root / "source" / "Movies" / "a.mkv").write_bytes(b"existing")
        return transfers

    def test_conflict_defaults_to_no_overwrite_and_fails_the_item_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transfers = self._prepare(root)
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode=TransferConflictMode.FAIL.value,
            )
            self.assertEqual(len(impact.conflicts), 1)
            self.assertEqual(impact.conflicts[0].resolution, "fail_no_overwrite")
            result = transfers.execute_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            self.assertEqual(result["status"], "FAILED")
            self.assertEqual(result["outcomes"][0]["errorCategory"], "target_exists")
            self.assertEqual((root / "source" / "Movies" / "a.mkv").read_bytes(), b"existing")
            self.assertTrue((root / "source" / "a.mkv").exists())

    def test_skip_leaves_both_sides_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transfers = self._prepare(root)
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="skip",
            )
            result = transfers.execute_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="skip",
                manifest_digest=impact.manifest.digest,
            )
            self.assertEqual(result["outcomes"][0]["status"], "SKIPPED")
            self.assertEqual((root / "source" / "Movies" / "a.mkv").read_bytes(), b"existing")
            self.assertTrue((root / "source" / "a.mkv").exists())

    def test_keep_both_publishes_a_backend_generated_unique_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transfers = self._prepare(root)
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="keep_both",
            )
            self.assertEqual(impact.manifest.destination_for("a.mkv"), "Movies/a (1).mkv")
            result = transfers.execute_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="keep_both",
                manifest_digest=impact.manifest.digest,
            )
            self.assertEqual(result["status"], "SUCCESS")
            self.assertEqual((root / "source" / "Movies" / "a (1).mkv").read_bytes(), b"media")
            self.assertEqual((root / "source" / "Movies" / "a.mkv").read_bytes(), b"existing")


class AdmissionTests(TransferTestCase):
    def _admit(self, root: Path):
        api, active, _runtime = self._activate(root)
        return self._transfers(api, active)

    def test_overlap_root_nested_duplicate_and_symlink_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transfers = self._admit(root)
            (root / "source" / "show").mkdir()
            (root / "source" / "show" / "one.mkv").write_bytes(b"one")
            (root / "source" / "Movies").mkdir()
            (root / "source" / "link.mkv").symlink_to(root / "source" / "show" / "one.mkv")

            cases = (
                (["show"], "show", "overlap"),
                ([""], "", "root_protected"),
                (["show", "show/one.mkv"], "", "invalid_request"),
                (["show", "show"], "", "invalid_request"),
                (["link.mkv"], "", "unsupported_entry"),
            )
            for paths, destination, category in cases:
                with self.subTest(paths=paths, destination=destination):
                    with self.assertRaises(Exception) as caught:
                        transfers.transfer_impact(
                            resource_library_id="source",
                            paths=paths,
                            destination_resource_library_id="source",
                            destination_directory=destination,
                            operation="copy",
                        )
                    self.assertIn(category, str(caught.exception.code))

    def test_stale_manifest_is_refused_with_zero_mutation_and_no_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media")
            (root / "source" / "Movies").mkdir()
            first = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
            )
            # The confirmed entry changes after the impact was issued.
            (root / "source" / "a.mkv").write_bytes(b"media-changed")
            with self.assertRaises(Exception) as caught:
                transfers.execute_transfer(
                    resource_library_id="source",
                    paths=["a.mkv"],
                    destination_resource_library_id="source",
                    destination_directory="Movies",
                    operation="copy",
                    conflict_mode="fail",
                    manifest_digest=first.manifest.digest,
                )
            self.assertEqual(caught.exception.code, "files_transfer_stale_manifest")
            self.assertFalse((root / "source" / "Movies" / "a.mkv").exists())
            self.assertEqual(runtime.list_tasks(command="files_transfer"), ())

    def test_missing_manifest_evidence_is_refused_before_any_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media")
            with self.assertRaises(Exception) as caught:
                transfers.execute_transfer(
                    resource_library_id="source",
                    paths=["a.mkv"],
                    destination_resource_library_id="source",
                    destination_directory="",
                    operation="copy",
                    conflict_mode="fail",
                    manifest_digest="",
                )
            self.assertEqual(caught.exception.code, "files_transfer_invalid_manifest")
            self.assertEqual(runtime.list_tasks(command="files_transfer"), ())

    def test_destination_must_exist_inside_the_destination_library(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transfers = self._admit(root)
            (root / "source" / "a.mkv").write_bytes(b"media")
            with self.assertRaises(Exception) as caught:
                transfers.transfer_impact(
                    resource_library_id="source",
                    paths=["a.mkv"],
                    destination_resource_library_id="source",
                    destination_directory="does-not-exist",
                    operation="copy",
                )
            self.assertEqual(caught.exception.code, "files_transfer_not_a_directory")

    def test_unbounded_selection_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transfers = self._admit(root)
            for index in range(51):
                (root / "source" / f"{index}.mkv").write_bytes(b"x")
            with self.assertRaises(Exception) as caught:
                transfers.transfer_impact(
                    resource_library_id="source",
                    paths=[f"{index}.mkv" for index in range(51)],
                    destination_resource_library_id="source",
                    destination_directory="",
                    operation="copy",
                )
            self.assertEqual(caught.exception.code, "files_transfer_invalid_request")


class CrossStorageTransferTests(TransferTestCase):
    def test_cross_storage_copy_streams_and_verifies_the_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a" * 1000)
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="copy",
            )
            self.assertEqual(impact.manifest.same_storage, False)
            self.assertEqual(impact.capability, "cross_storage_stream")
            result = transfers.execute_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            self.assertEqual(result["status"], "SUCCESS")
            self.assertTrue((root / "source" / "a.mkv").exists())
            self.assertEqual((root / "destination" / "a.mkv").read_bytes(), b"media-a" * 1000)

    def test_truncated_cross_storage_copy_is_never_reported_successful(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir(parents=True, exist_ok=True)
            (root / "destination").mkdir(parents=True, exist_ok=True)
            target = _TruncatingTarget("media-target", root / "destination")
            api, active, _runtime = self._activate(root, storage_adapters={"media-target": target})
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a" * 1000)
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="copy",
            )
            result = transfers.execute_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            self.assertNotEqual(result["status"], "SUCCESS")
            self.assertTrue((root / "source" / "a.mkv").exists())

    def test_cross_storage_move_checkpoints_copy_verify_then_delete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a" * 100)
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="move",
            )
            result = transfers.execute_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="move",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            self.assertEqual(result["status"], "SUCCESS")
            outcome = result["outcomes"][0]
            self.assertEqual(
                outcome["checkpoints"],
                ["copy_written", "destination_verified", "source_deleted"],
            )
            self.assertFalse((root / "source" / "a.mkv").exists())
            self.assertEqual((root / "destination" / "a.mkv").read_bytes(), b"media-a" * 100)

    def test_cross_storage_move_without_exact_identity_retains_the_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            source_root.mkdir(parents=True, exist_ok=True)
            (root / "destination").mkdir(parents=True, exist_ok=True)
            source_provider = _NoIdentityProvider("source-storage", source_root)
            api, active, _runtime = self._activate(
                root, storage_adapters={"source-storage": source_provider}
            )
            transfers = self._transfers(api, active)
            (source_root / "a.mkv").write_bytes(b"media-a" * 100)
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="move",
            )
            result = transfers.execute_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="move",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            # Verified Copy, source retained: a recoverable partial outcome that
            # names the surviving source rather than deleting under weak evidence.
            self.assertEqual(result["status"], "PARTIAL")
            outcome = result["outcomes"][0]
            self.assertEqual(outcome["checkpoints"], ["copy_written", "destination_verified"])
            self.assertEqual(outcome["errorCategory"], "entry_identity_unavailable")
            self.assertTrue((source_root / "a.mkv").exists())
            self.assertEqual((root / "destination" / "a.mkv").read_bytes(), b"media-a" * 100)
            self.assertEqual(result["retrySafe"], False)


class TransferApiTests(TransferTestCase):
    def _activate(self, root: Path, *, storage_adapters=None):
        return super()._activate(root, storage_adapters=storage_adapters)

    def test_transfer_routes_share_application_behavior_and_rbac(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _active, _runtime = self._activate(root)
            (root / "source" / "a.mkv").write_bytes(b"media")
            (root / "source" / "Movies").mkdir()

            status, impact = request(
                api,
                "/api/v1/resource-libraries/source/files/transfer-impact"
                "?path=a.mkv&to=source&toPath=Movies&operation=copy&conflict=fail",
            )
            self.assertEqual(status, 200)
            self.assertEqual(impact["sideEffects"], "none")
            self.assertEqual(impact["retrySafe"], True)
            self.assertEqual(impact["manifestDigest"][:3], "t1.")
            self.assertNotIn("source/", json.dumps(impact))

            viewer_status, _ = request(
                api,
                "/api/v1/resource-libraries/source/files/transfer-impact"
                "?path=a.mkv&to=source&toPath=Movies&operation=copy",
                token="viewer-token",
            )
            self.assertEqual(viewer_status, 200)

            forbidden, _ = request(
                api,
                "/api/v1/resource-libraries/source/files/transfers",
                method="POST",
                token="viewer-token",
                body={
                    "operation": "copy",
                    "paths": ["a.mkv"],
                    "destinationResourceLibraryId": "source",
                    "destinationDirectory": "Movies",
                    "conflictMode": "fail",
                    "manifestDigest": impact["manifestDigest"],
                },
            )
            self.assertEqual(forbidden, 403)

            created, result = request(
                api,
                "/api/v1/resource-libraries/source/files/transfers",
                method="POST",
                body={
                    "operation": "copy",
                    "paths": ["a.mkv"],
                    "destinationResourceLibraryId": "source",
                    "destinationDirectory": "Movies",
                    "conflictMode": "fail",
                    "manifestDigest": impact["manifestDigest"],
                },
            )
            self.assertEqual(created, 200)
            self.assertEqual(result["status"], "SUCCESS")
            self.assertTrue((root / "source" / "Movies" / "a.mkv").exists())

    def test_transfer_routes_reject_unknown_fields_and_stale_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _active, runtime = self._activate(root)
            (root / "source" / "a.mkv").write_bytes(b"media")
            (root / "source" / "Movies").mkdir()

            unknown, _ = request(
                api,
                "/api/v1/resource-libraries/source/files/transfer-impact"
                "?path=a.mkv&to=source&operation=copy&bogus=1",
            )
            self.assertEqual(unknown, 400)

            status, _impact = request(
                api,
                "/api/v1/resource-libraries/source/files/transfer-impact"
                "?path=a.mkv&to=source&toPath=Movies&operation=copy",
            )
            self.assertEqual(status, 200)
            stale, document = request(
                api,
                "/api/v1/resource-libraries/source/files/transfers",
                method="POST",
                body={
                    "operation": "copy",
                    "paths": ["a.mkv"],
                    "destinationResourceLibraryId": "source",
                    "destinationDirectory": "Movies",
                    "conflictMode": "fail",
                    "manifestDigest": "t1.deadbeef",
                },
            )
            self.assertEqual(stale, 409)
            self.assertEqual(document["error"]["code"], "files_transfer_stale_manifest")
            self.assertEqual(runtime.list_tasks(command="files_transfer"), ())


class RepeatedPathDeleteImpactTests(TransferTestCase):
    def test_delete_impact_accepts_two_and_fifty_repeated_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _active, _runtime = self._activate(root)
            for index in range(50):
                (root / "source" / f"f{index:02d}.txt").write_text("x", encoding="utf-8")
            two, first = request(
                api,
                "/api/v1/resource-libraries/source/files/delete-impact?path=f00.txt&path=f01.txt",
            )
            self.assertEqual(two, 200)
            self.assertEqual(sorted(first["topLevelPaths"]), ["f00.txt", "f01.txt"])
            self.assertEqual(first["sideEffects"], "none")
            self.assertEqual(first["retrySafe"], True)

            fifty, many = request(
                api,
                "/api/v1/resource-libraries/source/files/delete-impact?"
                + "&".join(f"path=f{index:02d}.txt" for index in range(50)),
            )
            self.assertEqual(fifty, 200)
            self.assertEqual(many["fileCount"], 50)

    def test_delete_impact_rejects_unknown_blank_and_over_limit_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _active, _runtime = self._activate(root)
            for index in range(51):
                (root / "source" / f"f{index:02d}.txt").write_text("x", encoding="utf-8")
            unknown, unknown_document = request(
                api, "/api/v1/resource-libraries/source/files/delete-impact?path=f00.txt&other=1"
            )
            self.assertEqual(unknown, 400)
            self.assertEqual(unknown_document["error"]["code"], "files_direct_invalid_request")
            blank, _ = request(
                api, "/api/v1/resource-libraries/source/files/delete-impact?path=f00.txt&path="
            )
            self.assertEqual(blank, 400)
            limit, _ = request(
                api,
                "/api/v1/resource-libraries/source/files/delete-impact?"
                + "&".join(f"path=f{index:02d}.txt" for index in range(51)),
            )
            self.assertEqual(limit, 400)


class ExecutorBoundaryTests(TransferTestCase):
    def test_every_transfer_mutation_crosses_the_organizer_executor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            executor = _CountingExecutor()
            transfers = self._transfers(api, active, executor=executor)
            (root / "source" / "one.mkv").write_bytes(b"one")
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["one.mkv"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="move",
            )
            result = transfers.execute_transfer(
                resource_library_id="source",
                paths=["one.mkv"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="move",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            self.assertEqual(result["status"], "SUCCESS")
            self.assertEqual(executor.boundaries, ["MOVE"])
            self.assertFalse((root / "source" / "one.mkv").exists())

    def test_transfer_does_not_invoke_the_media_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, _runtime = self._activate(root)
            transfers = self._transfers(api, active)
            (root / "source" / "Example.Movie.2024.1080p.mkv").write_bytes(b"media")
            (root / "source" / "Movies").mkdir()
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["Example.Movie.2024.1080p.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
            )
            document = json.dumps(impact.document())
            for forbidden in ("recognition", "metadataPolicy", "namingPolicy", "title"):
                self.assertNotIn(forbidden, document)
            result = transfers.execute_transfer(
                resource_library_id="source",
                paths=["Example.Movie.2024.1080p.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            self.assertEqual(result["status"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()
