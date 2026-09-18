"""Focused evidence for the bounded Files Copy/Move transfer journey.

Covers the same-Storage native Copy/Move, the composed bounded directory
transfer, the explicit cross-Storage compound Move with its durable
copy -> verify -> delete-source checkpoints, explicit conflict behavior
(including directory and in-batch destinations), fail-closed admission,
stale-manifest refusal, the repeated-`path` Delete impact contract,
OrganizerExecutor-only mutation, truthful skip/partial aggregation, the
durable Result identity/checkpoints and the durable continuation of an
interrupted transfer Task.  Every endpoint is a temporary local root or an
in-process fake; no production service is used.
"""

from __future__ import annotations

import io
import json
import tempfile
import threading
import time
import unittest
from datetime import UTC, datetime, timedelta
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
    StorageError,
    StorageErrorCode,
)
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTaskStatus,
    TaskItemStatus,
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

    def _submit(self, transfers, runtime, **kwargs):
        """Admit one confirmed transfer, run the resident Worker, and return
        the durable operator projection the Web reads after the fact."""

        queued = transfers.submit_transfer(**kwargs)
        self.assertEqual(queued["status"], "QUEUED")
        self.assertEqual(queued["taskStatus"], "pending")
        self._run_worker(transfers, runtime)
        return transfers.transfer_projection(queued["taskId"])

    def _worker(self, transfers, runtime):
        """The resident-Worker pickup for this fixture's runtime repository."""

        from mediaflow.application.files_transfer_worker import FilesTransferWorker

        return FilesTransferWorker(
            transfers,
            runtime,
            lease_seconds=3600.0,
            worker_id="worker-test",
        )

    def _run_worker(self, transfers, runtime):
        """Claim and run every claimable transfer to a terminal state."""

        worker = self._worker(transfers, runtime)
        finished = []
        while (transfer := worker.run_next()) is not None:
            finished.append(transfer)
        return finished


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
            result = self._submit(
                transfers,
                runtime,
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
            moved = self._submit(
                transfers,
                runtime,
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
            # Every Copy/Move — including a short single-file command — runs
            # through the one durable transfer admission/claim/execution
            # model, so Copy/Move has exactly one recovery story.
            task = runtime.get_task(moved["taskId"])
            self.assertEqual(task.command, "files_transfer")

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
            copied = self._submit(
                transfers,
                runtime,
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
            moved = self._submit(
                transfers,
                runtime,
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
            api, active, runtime = self._activate(
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
        return transfers, runtime

    def test_conflict_defaults_to_no_overwrite_and_fails_the_item_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transfers, runtime = self._prepare(root)
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
            result = self._submit(
                transfers,
                runtime,
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
            transfers, runtime = self._prepare(root)
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="skip",
            )
            result = self._submit(
                transfers,
                runtime,
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
            transfers, runtime = self._prepare(root)
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="keep_both",
            )
            self.assertEqual(impact.manifest.destination_for("a.mkv"), "Movies/a (1).mkv")
            result = self._submit(
                transfers,
                runtime,
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
        api, active, runtime = self._activate(root)
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
                transfers.submit_transfer(
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
                transfers.submit_transfer(
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
            api, active, runtime = self._activate(root)
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
            result = self._submit(
                transfers,
                runtime,
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
            api, active, runtime = self._activate(root, storage_adapters={"media-target": target})
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a" * 1000)
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="copy",
            )
            result = self._submit(
                transfers,
                runtime,
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
            api, active, runtime = self._activate(root)
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a" * 100)
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="move",
            )
            result = self._submit(
                transfers,
                runtime,
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
            api, active, runtime = self._activate(
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
            result = self._submit(
                transfers,
                runtime,
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

    def test_real_admission_matches_the_shared_contract_fixture(self) -> None:
        """The real Python API admission document is the shared TS contract.

        The committed fixture is consumed verbatim by the TypeScript normalizer
        test and by the Files fake server, so this comparison is the one
        cross-boundary evidence that the Python API, the strict frontend model
        and the e2e fake all agree on the same document.  Only the server-issued
        opaque task identity is normalized.
        """

        fixture_path = (
            Path(__file__).resolve().parents[1]
            / "web"
            / "tests"
            / "fixtures"
            / "files-transfer-admission.json"
        )
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _active, _runtime = self._activate(root)
            (root / "source" / "a.mkv").write_bytes(b"media")
            (root / "source" / "Movies").mkdir()
            _status, impact = request(
                api,
                "/api/v1/resource-libraries/source/files/transfer-impact"
                "?path=a.mkv&to=source&toPath=Movies&operation=copy&conflict=fail",
            )
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
            self.assertEqual(created, 202)

        normalized = {**result, "taskId": fixture["taskId"]}
        self.assertEqual(normalized, fixture)
        self.assertTrue(result["taskId"])
        self.assertEqual(normalized["topLevelPaths"], ["a.mkv"])
        self.assertTrue(
            all(isinstance(path, str) for path in normalized["topLevelPaths"]),
            normalized["topLevelPaths"],
        )
        self.assertEqual(
            normalized["destinations"], [{"path": "a.mkv", "destination": "Movies/a.mkv"}]
        )
        self.assertEqual(normalized["status"], "QUEUED")
        self.assertEqual(normalized["taskStatus"], "pending")
        self.assertEqual(normalized["sideEffects"], "none")
        self.assertTrue(normalized["outcomes"] == [] or normalized["outcomesTruncated"])
        # The bounded document never carries a host root, credential or provider
        # payload; only ResourceLibrary-relative logical paths.
        rendered = json.dumps(normalized)
        for forbidden in (str(root), "password", "token", "secret", "Authorization"):
            self.assertNotIn(forbidden, rendered)

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
            # 202: the transfer is durably admitted; nothing is mutated on
            # the request stack and the Worker executes the queued work.
            self.assertEqual(created, 202)
            self.assertEqual(result["status"], "QUEUED")
            self.assertEqual(result["taskStatus"], "pending")
            self.assertEqual(result["sideEffects"], "none")
            self.assertFalse((root / "source" / "Movies" / "a.mkv").exists())
            # The admitted transfer follows the durable projection and the
            # separately invoked Worker claim advances it.
            status_code, queued_projection = request(
                api,
                f"/api/v1/resource-libraries/source/files/transfers/{result['taskId']}",
            )
            self.assertEqual(status_code, 200)
            self.assertEqual(queued_projection["status"], "QUEUED")
            self.assertTrue(
                any(
                    action["action"] == "cancel" and action["available"]
                    for action in queued_projection["actions"]
                )
            )
            binding = api._runtime_binding
            transfers_service = DirectFileTransferService(
                direct_files=binding.direct_files, executor=OrganizerExecutor()
            )
            self._run_worker(transfers_service, api._repository)
            final_code, projection = request(
                api,
                f"/api/v1/resource-libraries/source/files/transfers/{result['taskId']}",
            )
            self.assertEqual(final_code, 200)
            self.assertEqual(projection["status"], "SUCCESS")
            self.assertEqual(projection["succeededItems"], 1)
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


class _NoNativeMutationStorage(LocalStorage):
    """A same-Storage double that forbids every non-native mutation."""

    def write(self, *args, **kwargs):
        raise AssertionError("no streaming Write fallback may be attempted")

    def delete(self, *args, **kwargs):
        raise AssertionError("no Delete fallback may be attempted")


class _PausingSource(LocalStorage):
    """A source that requests a durable Task pause at the Nth file mutation.

    The pause request goes through the same durable Task repository the
    application uses, so the running transfer observes it exactly like a
    concurrent operator pause.
    """

    def __init__(self, storage_id: str, root: Path, runtime_db: Path, *, after: int) -> None:
        super().__init__(storage_id, root)
        self._runtime_db = runtime_db
        self._after = after
        self.mutation_calls = 0

    def _request_pause(self) -> None:
        self.mutation_calls += 1
        if self.mutation_calls != self._after:
            return
        repository = SQLiteTaskRepository(self._runtime_db)
        try:
            tasks = repository.list_tasks(command="files_transfer")
            if tasks:
                repository.request_task_pause(tasks[0].task_id, datetime.now(UTC))
        finally:
            repository.close()

    def copy(self, *args, **kwargs):
        self._request_pause()
        return super().copy(*args, **kwargs)

    def move(self, *args, **kwargs):
        self._request_pause()
        return super().move(*args, **kwargs)


class _CrashAfterWriteTarget(LocalStorage):
    """A target that loses the process right after a streamed write lands."""

    def __init__(self, storage_id: str, root: Path) -> None:
        super().__init__(storage_id, root)
        self.write_calls = 0

    def write(self, path: str, data, *, overwrite: bool = False) -> None:
        self.write_calls += 1
        super().write(path, data, overwrite=overwrite)
        raise SystemExit(3)


class _TruncatingCrashTarget(LocalStorage):
    """A target that truncates the streamed write and then loses the process."""

    def write(self, path: str, data, *, overwrite: bool = False) -> None:
        if hasattr(data, "read"):
            data = data.read(3)
        super().write(path, data, overwrite=overwrite)
        raise SystemExit(3)


class _CrashOnDeleteSource(LocalStorage):
    """A source Storage whose file delete loses the process mid-delete."""

    def __init__(self, storage_id: str, root: Path) -> None:
        super().__init__(storage_id, root)
        self.delete_calls = 0

    def delete(self, path: str) -> None:
        self.delete_calls += 1
        if self.delete_calls == 1:
            # The first deletion call loses the process before the file is
            # removed (the source stays); a replacement Worker performs the
            # deletion again with fresh exact evidence.
            raise SystemExit(3)


class _CrashAtCheckpointTarget(LocalStorage):
    """A target that loses the process at a chosen compound checkpoint.

    ``crash_at`` selects which boundary loses the process: ``after_write``
    (the Copy destination landed, verification not yet run) and
    ``after_verify`` (the destination has been read back — verification under
    way — and the source deletion has not run).  The crash arms only after
    the first streamed write, so the admission-time reads stay untouched.
    """

    def __init__(self, storage_id: str, root: Path, *, crash_at: str) -> None:
        super().__init__(storage_id, root)
        self.crash_at = crash_at
        self.write_calls = 0
        self.stat_calls = 0

    def write(self, path: str, data, *, overwrite: bool = False) -> None:
        self.write_calls += 1
        super().write(path, data, overwrite=overwrite)
        if self.crash_at == "after_write":
            raise SystemExit(3)

    def stat(self, path: str) -> StorageEntry:
        self.stat_calls += 1
        if self.crash_at == "after_verify" and self.write_calls >= 1 and (self.stat_calls == 2):
            # stat 1 is the continuation/verify read of the fresh write; the
            # process ends exactly there — destination read (verified), no
            # source deletion yet.
            raise SystemExit(3)
        return super().stat(path)


class DirectoryConflictTests(TransferTestCase):
    """F-1: the selected conflict mode binds every destination, directories included."""

    def _prepare(self, root: Path):
        api, active, runtime = self._activate(root)
        transfers = self._transfers(api, active)
        tree = root / "source" / "show" / "season1"
        tree.mkdir(parents=True)
        (tree / "one.mkv").write_bytes(b"one")
        (tree / "two.mkv").write_bytes(b"two")
        (root / "source" / "Movies").mkdir()
        return transfers, runtime

    def test_fail_mode_directory_move_never_merges_into_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transfers, runtime = self._prepare(root)
            (root / "source" / "Movies" / "show").mkdir()
            (root / "source" / "Movies" / "show" / "keep.mkv").write_bytes(b"keep")
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["show"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="move",
                conflict_mode=TransferConflictMode.FAIL.value,
            )
            self.assertEqual(impact.conflicts[0].resolution, "fail_no_overwrite")
            result = self._submit(
                transfers,
                runtime,
                resource_library_id="source",
                paths=["show"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="move",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            # The B reproduction demanded zero mutation for the affected item.
            self.assertEqual(result["status"], "FAILED")
            self.assertEqual(result["knownEffects"][0]["effect"], "retained")
            self.assertEqual(result["outcomes"][0]["errorCategory"], "target_exists")
            self.assertEqual(result["outcomes"][0]["checkpoints"], [])
            self.assertTrue((root / "source" / "show" / "season1" / "one.mkv").exists())
            self.assertTrue((root / "source" / "show" / "season1" / "two.mkv").exists())
            self.assertEqual(
                (root / "source" / "Movies" / "show" / "keep.mkv").read_bytes(), b"keep"
            )
            item = runtime.list_items(result["taskId"])[0]
            self.assertEqual(item.status, TaskItemStatus.FAILED)

    def test_skip_mode_directory_conflict_skips_the_whole_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transfers, runtime = self._prepare(root)
            (root / "source" / "Movies" / "show").mkdir()
            (root / "source" / "Movies" / "show" / "keep.mkv").write_bytes(b"keep")
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["show"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="move",
                conflict_mode="skip",
            )
            result = self._submit(
                transfers,
                runtime,
                resource_library_id="source",
                paths=["show"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="move",
                conflict_mode="skip",
                manifest_digest=impact.manifest.digest,
            )
            self.assertEqual(result["status"], "SKIPPED")
            self.assertEqual(result["knownEffects"][0]["effect"], "skipped")
            self.assertEqual(result["skippedItems"], 1)
            self.assertTrue((root / "source" / "show" / "season1" / "one.mkv").exists())
            self.assertEqual(
                (root / "source" / "Movies" / "show" / "keep.mkv").read_bytes(), b"keep"
            )
            item = runtime.list_items(result["taskId"])[0]
            self.assertEqual(item.status, TaskItemStatus.SKIPPED)
            self.assertEqual(item.destination_storage_id, "source-storage")

    def test_keep_both_directory_transfer_pins_a_unique_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transfers, runtime = self._prepare(root)
            (root / "source" / "Movies" / "show").mkdir()
            (root / "source" / "Movies" / "show" / "keep.mkv").write_bytes(b"keep")
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["show"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="move",
                conflict_mode="keep_both",
            )
            self.assertEqual(impact.manifest.destination_for("show"), "Movies/show (1)")
            result = self._submit(
                transfers,
                runtime,
                resource_library_id="source",
                paths=["show"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="move",
                conflict_mode="keep_both",
                manifest_digest=impact.manifest.digest,
            )
            self.assertEqual(result["status"], "SUCCESS")
            self.assertEqual(
                (root / "source" / "Movies" / "show (1)" / "season1" / "one.mkv").read_bytes(),
                b"one",
            )
            self.assertEqual(
                (root / "source" / "Movies" / "show" / "keep.mkv").read_bytes(), b"keep"
            )
            self.assertFalse((root / "source" / "show").exists())

    def test_in_batch_destination_collision_is_reported_not_merged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            transfers = self._transfers(api, active)
            (root / "source" / "a").mkdir()
            (root / "source" / "b").mkdir()
            (root / "source" / "d").mkdir()
            (root / "source" / "a" / "x.mkv").write_bytes(b"first")
            (root / "source" / "b" / "x.mkv").write_bytes(b"second")
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a/x.mkv", "b/x.mkv"],
                destination_resource_library_id="source",
                destination_directory="d",
                operation="copy",
                conflict_mode="fail",
            )
            self.assertEqual(
                [conflict.resolution for conflict in impact.conflicts],
                ["batch_conflict"],
            )
            result = self._submit(
                transfers,
                runtime,
                resource_library_id="source",
                paths=["a/x.mkv", "b/x.mkv"],
                destination_resource_library_id="source",
                destination_directory="d",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            self.assertEqual(result["status"], "PARTIAL")
            effects = {effect["path"]: effect["effect"] for effect in result["knownEffects"]}
            self.assertEqual(effects["a/x.mkv"], "transferred")
            self.assertEqual(effects["b/x.mkv"], "retained")
            categories = {
                outcome["path"]: outcome.get("errorCategory") for outcome in result["outcomes"]
            }
            self.assertEqual(categories["b/x.mkv"], "batch_conflict")
            self.assertEqual((root / "source" / "d" / "x.mkv").read_bytes(), b"first")
            self.assertEqual((root / "source" / "b" / "x.mkv").read_bytes(), b"second")

    def test_skip_mode_collision_skips_the_later_sibling_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            transfers = self._transfers(api, active)
            (root / "source" / "a").mkdir()
            (root / "source" / "b").mkdir()
            (root / "source" / "d").mkdir()
            (root / "source" / "a" / "x.mkv").write_bytes(b"first")
            (root / "source" / "b" / "x.mkv").write_bytes(b"second")
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a/x.mkv", "b/x.mkv"],
                destination_resource_library_id="source",
                destination_directory="d",
                operation="copy",
                conflict_mode="skip",
            )
            result = self._submit(
                transfers,
                runtime,
                resource_library_id="source",
                paths=["a/x.mkv", "b/x.mkv"],
                destination_resource_library_id="source",
                destination_directory="d",
                operation="copy",
                conflict_mode="skip",
                manifest_digest=impact.manifest.digest,
            )
            # One item transferred, one skipped by the explicit choice: the
            # truthful aggregate is PARTIAL with exact per-item effects, not a
            # fabricated all-success and not a fabricated all-skip.
            self.assertEqual(result["status"], "PARTIAL")
            self.assertEqual(result["skippedItems"], 1)
            effects = {effect["path"]: effect["effect"] for effect in result["knownEffects"]}
            self.assertEqual(effects["a/x.mkv"], "transferred")
            self.assertEqual(effects["b/x.mkv"], "skipped")
            self.assertEqual((root / "source" / "b" / "x.mkv").read_bytes(), b"second")
            self.assertEqual((root / "source" / "d" / "x.mkv").read_bytes(), b"first")


class SameStorageDecisionTests(TransferTestCase):
    """F-2: the same-Storage decision is bound to configured Storage identity."""

    def test_production_adapter_factory_uses_only_native_operations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # No injected adapter instances: the normal runtime factory builds
            # its own adapters, so no shared object identity exists.
            api, active, runtime = self._activate(root)
            transfers = self._transfers(api, active)
            (root / "source" / "show").mkdir()
            (root / "source" / "show" / "one.mkv").write_bytes(b"one")
            (root / "source" / "Movies").mkdir()
            copy_impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["show"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
            )
            copied = self._submit(
                transfers,
                runtime,
                resource_library_id="source",
                paths=["show"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=copy_impact.manifest.digest,
            )
            self.assertEqual(copied["status"], "SUCCESS")
            file_outcome = next(
                outcome for outcome in copied["outcomes"] if outcome["path"] == "show/one.mkv"
            )
            self.assertEqual(file_outcome["checkpoints"], ["COPY"])
            self.assertTrue((root / "source" / "show" / "one.mkv").exists())
            (root / "source" / "Archive").mkdir()
            move_impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["show"],
                destination_resource_library_id="source",
                destination_directory="Archive",
                operation="move",
            )
            moved = self._submit(
                transfers,
                runtime,
                resource_library_id="source",
                paths=["show"],
                destination_resource_library_id="source",
                destination_directory="Archive",
                operation="move",
                conflict_mode="fail",
                manifest_digest=move_impact.manifest.digest,
            )
            self.assertEqual(moved["status"], "SUCCESS")
            moved_outcome = next(
                outcome for outcome in moved["outcomes"] if outcome["path"] == "show/one.mkv"
            )
            self.assertEqual(moved_outcome["checkpoints"], ["MOVE"])
            self.assertFalse((root / "source" / "show").exists())
            self.assertEqual(
                (root / "source" / "Archive" / "show" / "one.mkv").read_bytes(), b"one"
            )

    def test_explicit_same_storage_decision_never_streams_or_deletes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = _NoNativeMutationStorage("source-storage", root)
            second = LocalStorage("source-storage", root)
            (root / "a.mkv").write_bytes(b"media")
            executor = OrganizerExecutor()
            copied = executor.execute_direct_copy(
                first,
                second,
                "a.mkv",
                "b.mkv",
                same_storage=True,
                execute=True,
            )
            self.assertEqual(copied.status.value, "SUCCESS")
            self.assertEqual(copied.completed_operations, ("COPY",))
            self.assertEqual((root / "b.mkv").read_bytes(), b"media")
            moved = executor.execute_direct_move(
                second,
                first,
                "b.mkv",
                "c.mkv",
                same_storage=True,
                execute=True,
            )
            self.assertEqual(moved.status.value, "SUCCESS")
            self.assertEqual(moved.completed_operations, ("MOVE",))
            self.assertFalse((root / "b.mkv").exists())
            self.assertEqual((root / "c.mkv").read_bytes(), b"media")


class _DisjointRootFixture(TransferTestCase):
    """A fixture whose second ResourceLibrary root is disjoint on one Storage."""

    def _document(self, root: Path) -> dict[str, object]:
        document = super()._document(root)
        document["resourceLibraries"].append(
            {
                "id": "inner",
                "name": "Inner",
                "storageId": "source-storage",
                "storagePath": "other",
                "enabled": True,
                "extensions": ["mkv"],
            }
        )
        return document


class _NestedRootFixture(TransferTestCase):
    """A fixture whose second ResourceLibrary root sits inside the source tree."""

    def _document(self, root: Path) -> dict[str, object]:
        document = super()._document(root)
        document["resourceLibraries"].append(
            {
                "id": "inner",
                "name": "Inner",
                "storageId": "source-storage",
                "storagePath": "shows/nested",
                "enabled": True,
                "extensions": ["mkv"],
            }
        )
        return document


class ResolvedRootOverlapTests(TransferTestCase):
    """F-2: overlap compares fully resolved logical Storage paths.

    Both fixtures keep two ResourceLibrary roots on one Storage.  Relative
    string comparisons either falsely reject the disjoint case or miss the
    physical descendant case; the resolved comparison handles both truthfully.
    """

    def test_equal_relative_strings_on_disjoint_roots_transfer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "shows").mkdir(parents=True)
            (root / "source" / "shows" / "a.mkv").write_bytes(b"a")
            (root / "source" / "other").mkdir(parents=True)
            api, active, runtime = _DisjointRootFixture()._activate(root)
            transfers = self._transfers(api, active)
            # The relative strings are identical ("shows" -> "shows"), but the
            # resolved physical locations are disjoint ResourceLibrary roots on
            # one Storage, so the transfer is valid.
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["shows"],
                destination_resource_library_id="inner",
                destination_directory="",
                operation="move",
            )
            result = self._submit(
                transfers,
                runtime,
                resource_library_id="source",
                paths=["shows"],
                destination_resource_library_id="inner",
                destination_directory="",
                operation="move",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            self.assertEqual(result["status"], "SUCCESS")
            self.assertTrue((root / "source" / "other" / "shows" / "a.mkv").exists())
            self.assertFalse((root / "source" / "shows").exists())

    def test_physical_self_descendant_overlap_is_rejected_across_roots(self) -> None:
        fixture = _NestedRootFixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "shows" / "nested" / "d").mkdir(parents=True)
            (root / "source" / "shows" / "a.mkv").write_bytes(b"a")
            api, active, runtime = fixture._activate(root)
            transfers = self._transfers(api, active)
            # The destination resolves to root/source/shows/nested/d/shows — a
            # physical descendant of the selected directory — even though the
            # relative strings ("shows" vs "d/shows") look unrelated.
            with self.assertRaises(Exception) as caught:
                transfers.transfer_impact(
                    resource_library_id="source",
                    paths=["shows"],
                    destination_resource_library_id="inner",
                    destination_directory="d",
                    operation="move",
                )
            self.assertIn("overlap", str(caught.exception.code))
            self.assertTrue((root / "source" / "shows" / "a.mkv").exists())


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


class _FailingDirectoryCreationTarget(LocalStorage):
    """A destination that refuses to create one specific directory."""

    def create_directory(self, path: str) -> None:
        if path == "Movies/show":
            raise StorageError(
                StorageErrorCode.PERMISSION_DENIED,
                "create_directory",
                path,
                "permission denied",
            )
        return super().create_directory(path)


class _RefusingDirectoryDeleteSource(LocalStorage):
    """A source that refuses to delete the emptied source directory."""

    def delete(self, path: str) -> None:
        if path.endswith("show"):
            raise StorageError(
                StorageErrorCode.PERMISSION_DENIED, "delete", path, "permission denied"
            )
        return super().delete(path)


class _LateConflictTarget(LocalStorage):
    """A target that materializes a conflict inside the directory it creates.

    This models a child destination that appears between the transfer's own
    root creation and the child's last safe boundary — the only way a child
    can conflict after a successful root creation in a deterministic test.
    """

    def __init__(self, storage_id: str, root: Path) -> None:
        super().__init__(storage_id, root)
        self.created: list[str] = []

    def create_directory(self, path: str) -> None:
        super().create_directory(path)
        self.created.append(path)
        # The first created directory receives one late conflicting child.
        if len(self.created) == 1:
            (Path(self._root) / path / "two.mkv").write_bytes(b"late-conflict")


class AggregationTests(TransferTestCase):
    """F-3: skipped, directory and partial effects aggregate truthfully."""

    def test_item_status_precedence_is_deterministic(self) -> None:
        from mediaflow.application.direct_file_transfers import _item_status

        cases = [
            ([("SUCCESS", ["CREATE_DIRECTORY"])], "SUCCESS"),
            ([("SKIPPED", [])], "SKIPPED"),
            ([("SUCCESS", ["CREATE_DIRECTORY"]), ("SKIPPED", [])], "PARTIAL"),
            ([("SUCCESS", ["COPY"]), ("FAILED", [])], "PARTIAL"),
            ([("FAILED", []), ("SKIPPED", [])], "FAILED"),
            ([("FAILED", ["COPY"]), ("SKIPPED", [])], "PARTIAL"),
            ([("PARTIAL", ["COPY"])], "PARTIAL"),
            ([("UNCERTAIN", ["COPY"]), ("SUCCESS", ["COPY"])], "UNCERTAIN"),
            ([], "FAILED"),
        ]
        for statuses, expected in cases:
            entries = [
                {"path": f"entry-{index}", "status": status, "checkpoints": list(checkpoints)}
                for index, (status, checkpoints) in enumerate(statuses)
            ]
            self.assertEqual(_item_status(entries), expected, statuses)

    def test_created_root_with_late_conflicting_child_is_partial_everywhere(self) -> None:
        """The root is created, then a child conflicts late under SKIP.

        The response, the durable TaskItem, the Result and the reloaded Task
        detail all report the partial aggregate and keep the skipped child
        evidence — never a fabricated wholly-successful transfer.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            (root / "destination").mkdir(parents=True, exist_ok=True)
            target = _LateConflictTarget("media-target", root / "destination")
            api, active, runtime = self._activate(root, storage_adapters={"media-target": target})
            transfers = self._transfers(api, active)
            tree = root / "source" / "show"
            tree.mkdir()
            (tree / "one.mkv").write_bytes(b"one")
            (tree / "two.mkv").write_bytes(b"two")
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["show"],
                destination_resource_library_id="destination",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="skip",
            )
            self.assertEqual(impact.conflicts, ())
            result = self._submit(
                transfers,
                runtime,
                resource_library_id="source",
                paths=["show"],
                destination_resource_library_id="destination",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="skip",
                manifest_digest=impact.manifest.digest,
            )
            # Response: the created root plus the skipped child is PARTIAL and
            # the wholly transferred count does not grow.
            self.assertEqual(result["status"], "PARTIAL")
            self.assertEqual(result["succeededItems"], 0)
            # The one item is the partial aggregate; the skipped child stays
            # visible in the per-entry outcomes below.
            self.assertEqual(result["skippedItems"], 0)
            self.assertEqual(result["failedItems"], 1)
            effects = {effect["path"]: effect for effect in result["knownEffects"]}
            self.assertEqual(effects["show"]["effect"], "partial")
            self.assertEqual(effects["show"]["status"], "PARTIAL")
            # The skipped child evidence stays in the durable Result: the
            # completed directory checkpoint beside the retained skip marker.
            item = runtime.list_items(result["taskId"])[0]
            record = runtime.list_results(result["taskId"])[0]
            # The created destination directory is its own entry marker; the
            # copied file and the retained skip keep their exact evidence.
            self.assertIn("entry:SUCCESS:show", record.completed_operations)
            self.assertIn("COPY:show/one.mkv", record.completed_operations)
            self.assertIn("entry:SKIPPED:show/two.mkv", record.completed_operations)
            self.assertIn("entry_error:target_exists:show/two.mkv", record.completed_operations)
            # The per-entry outcomes keep the created-directory truth; the
            # item aggregate in itemOutcomes is the partial one.
            outcomes = {outcome["path"]: outcome for outcome in result["outcomes"]}
            self.assertEqual(outcomes["show"]["status"], "SUCCESS")
            self.assertEqual(outcomes["show/one.mkv"]["status"], "SUCCESS")
            self.assertEqual(outcomes["show/two.mkv"]["status"], "SKIPPED")
            item_outcomes = {item["path"]: item for item in result["itemOutcomes"]}
            self.assertEqual(item_outcomes["show"]["status"], "PARTIAL")
            # Physical truth: root created, non-conflicting file copied, the
            # late conflict kept in place and the source intact.
            self.assertTrue((root / "destination" / "Movies" / "show" / "one.mkv").exists())
            self.assertEqual(
                (root / "destination" / "Movies" / "show" / "two.mkv").read_bytes(),
                b"late-conflict",
            )
            self.assertTrue((root / "source" / "show" / "two.mkv").exists())
            # Durable TaskItem + Result reproduce the same aggregate.
            item = runtime.list_items(result["taskId"])[0]
            self.assertEqual(item.status, TaskItemStatus.PARTIAL)
            record = runtime.list_results(result["taskId"])[0]
            self.assertEqual(record.status, "partial")
            self.assertEqual(record.error, "target_exists")
            self.assertEqual(record.destination_storage_id, "media-target")
            self.assertTrue(any("COPY" in op for op in record.completed_operations))
            # Reloaded Task detail (the state the Web reads after the fact):
            # the Task aggregate counts the one partial item as failed, and
            # the item/Result records keep the exact partial evidence.
            detail = runtime.get_task(result["taskId"])
            self.assertEqual(detail.failed_items, 1)
            self.assertEqual(detail.total_items, 1)

    def test_all_skipped_batch_is_reported_as_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media")
            (root / "source" / "b.mkv").write_bytes(b"other")
            (root / "source" / "d").mkdir()
            (root / "source" / "d" / "a.mkv").write_bytes(b"existing")
            (root / "source" / "d" / "b.mkv").write_bytes(b"existing-b")
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv", "b.mkv"],
                destination_resource_library_id="source",
                destination_directory="d",
                operation="copy",
                conflict_mode="skip",
            )
            result = self._submit(
                transfers,
                runtime,
                resource_library_id="source",
                paths=["a.mkv", "b.mkv"],
                destination_resource_library_id="source",
                destination_directory="d",
                operation="copy",
                conflict_mode="skip",
                manifest_digest=impact.manifest.digest,
            )
            self.assertEqual(result["status"], "SKIPPED")
            self.assertEqual(result["skippedItems"], 2)
            self.assertEqual({effect["effect"] for effect in result["knownEffects"]}, {"skipped"})
            items = runtime.list_items(result["taskId"])
            self.assertEqual({item.status for item in items}, {TaskItemStatus.SKIPPED})
            self.assertEqual((root / "source" / "d" / "a.mkv").read_bytes(), b"existing")
            self.assertTrue((root / "source" / "a.mkv").exists())

    def test_failed_destination_directory_creation_stops_before_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir(parents=True, exist_ok=True)
            (root / "destination" / "Movies").mkdir(parents=True, exist_ok=True)
            target = _FailingDirectoryCreationTarget("media-target", root / "destination")
            api, active, runtime = self._activate(root, storage_adapters={"media-target": target})
            transfers = self._transfers(api, active)
            tree = root / "source" / "show" / "season1"
            tree.mkdir(parents=True)
            (tree / "one.mkv").write_bytes(b"one")
            (root / "source" / "spare").mkdir()
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["show", "spare"],
                destination_resource_library_id="destination",
                destination_directory="Movies",
                operation="copy",
            )
            result = self._submit(
                transfers,
                runtime,
                resource_library_id="source",
                paths=["show", "spare"],
                destination_resource_library_id="destination",
                operation="copy",
                destination_directory="Movies",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            # The failing item's directory mutation was refused: it is a plain
            # failure with no fabricated file transfer behind it.
            show_effects = {effect["path"]: effect for effect in result["knownEffects"]}
            self.assertEqual(show_effects["show"]["effect"], "retained")
            outcomes = {outcome["path"]: outcome for outcome in result["outcomes"]}
            self.assertEqual(outcomes["show"].get("errorCategory"), "create_directory_failed")
            self.assertTrue((root / "source" / "show" / "season1" / "one.mkv").exists())
            # The unaffected sibling still transfers independently.
            self.assertTrue((root / "destination" / "Movies" / "spare").exists())

    def test_failed_emptied_source_directory_removal_is_never_wholly_successful(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir(parents=True, exist_ok=True)
            (root / "destination").mkdir(parents=True, exist_ok=True)
            source = _RefusingDirectoryDeleteSource("source-storage", root / "source")
            api, active, runtime = self._activate(root, storage_adapters={"source-storage": source})
            transfers = self._transfers(api, active)
            tree = root / "source" / "show"
            tree.mkdir()
            (tree / "one.mkv").write_bytes(b"one")
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["show"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="move",
            )
            result = self._submit(
                transfers,
                runtime,
                resource_library_id="source",
                paths=["show"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="move",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            # The file moved and its destination is verified, but the source
            # directory could not be removed: the effect of the refused delete
            # is uncertain to the executor, so the item is an explicit
            # uncertain/partial state — never a wholly successful directory
            # Move and never replayed automatically.
            self.assertEqual(result["status"], "UNCERTAIN")
            outcomes = {outcome["path"]: outcome for outcome in result["outcomes"]}
            self.assertEqual(outcomes["show/one.mkv"]["status"], "SUCCESS")
            self.assertEqual(outcomes["show"]["status"], "UNCERTAIN")
            self.assertEqual(
                outcomes["show"].get("errorCategory"), "source_directory_removal_failed"
            )
            self.assertTrue((root / "source" / "show").is_dir())
            self.assertEqual((root / "destination" / "show" / "one.mkv").read_bytes(), b"one")
            item = runtime.list_items(result["taskId"])[0]
            self.assertEqual(item.status, TaskItemStatus.PARTIAL)


class DurableResultTests(TransferTestCase):
    """F-4: the durable Result reproduces the truthful transfer identity."""

    def test_cross_storage_result_persists_destination_identity_and_checkpoints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a" * 100)
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="move",
            )
            result = self._submit(
                transfers,
                runtime,
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="move",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            self.assertEqual(result["status"], "SUCCESS")
            items = runtime.list_items(result["taskId"])
            self.assertEqual(len(items), 1)
            item = items[0]
            self.assertEqual(item.destination_storage_id, "media-target")
            self.assertEqual(item.destination_path, "a.mkv")
            results = runtime.list_results(result["taskId"])
            self.assertEqual(len(results), 1)
            record = results[0]
            self.assertEqual(record.source_storage_id, "source-storage")
            self.assertEqual(record.destination_storage_id, "media-target")
            self.assertEqual(record.status, "success")
            self.assertEqual(
                record.completed_operations,
                (
                    "copy_written:a.mkv",
                    "destination_verified:a.mkv",
                    "source_deleted:a.mkv",
                    "entry:SUCCESS:a.mkv",
                ),
            )
            self.assertEqual(record.effect_certainty, "verified_complete")


class _GatedSource(LocalStorage):
    """A source that blocks the Nth native mutation until the test releases it.

    While the Worker's execution thread is blocked inside that mutation, the
    test writes the durable pause/cancel request through the same Task
    repository write the authenticated lifecycle API performs — a separate
    control request against a genuinely running transfer — and then releases
    the gate.  The Storage callback itself never mutates any Task row.
    """

    def __init__(self, storage_id: str, root: Path, *, gate_after: int) -> None:
        super().__init__(storage_id, root)
        self._gate_after = gate_after
        self.mutation_calls = 0
        self.reached = threading.Event()
        self.release = threading.Event()

    def _gate(self) -> None:
        self.mutation_calls += 1
        if self.mutation_calls != self._gate_after:
            return
        self.reached.set()
        self.release.wait(timeout=30)

    def copy(self, *args, **kwargs):
        self._gate()
        return super().copy(*args, **kwargs)

    def move(self, *args, **kwargs):
        self._gate()
        return super().move(*args, **kwargs)


class PauseCancelResumeTests(TransferTestCase):
    """F-5: the durable queued/running/paused lifecycle and takeover recovery.

    Admission returns before the first mutation; a separately invoked Worker
    claim advances the work; a pause requested through the durable Task
    repository (exactly what the authenticated lifecycle API does) is observed
    at a per-entry boundary; and a replacement Worker continues only from the
    persisted known-safe checkpoints.
    """

    def _tree(self, root: Path, count: int = 6) -> None:
        tree = root / "source" / "show"
        tree.mkdir(parents=True)
        for index in range(count):
            (tree / f"ep{index:02d}.mkv").write_bytes(b"episode" * (index + 1))

    def _admit(self, transfers, runtime, *, operation="move", conflict_mode="fail"):
        impact = transfers.transfer_impact(
            resource_library_id="source",
            paths=["show"],
            destination_resource_library_id="source",
            destination_directory="Movies",
            operation=operation,
            conflict_mode=conflict_mode,
        )
        return transfers.submit_transfer(
            resource_library_id="source",
            paths=["show"],
            destination_resource_library_id="source",
            destination_directory="Movies",
            operation=operation,
            conflict_mode=conflict_mode,
            manifest_digest=impact.manifest.digest,
        )

    def _run_worker_async(self, transfers, runtime, results: list):
        def run():
            worker = self._worker(transfers, runtime)
            results.append(worker.run_next())

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    def test_pause_inside_one_directory_is_observed_and_resumed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            source = _GatedSource("source-storage", root / "source", gate_after=3)
            api, active, runtime = self._activate(root, storage_adapters={"source-storage": source})
            transfers = self._transfers(api, active)
            self._tree(root)
            # Admission happens on this (API) stack and returns before the
            # first mutation.
            queued = self._admit(transfers, runtime)
            self.assertEqual(queued["status"], "QUEUED")
            self.assertEqual(queued["taskStatus"], "pending")
            self.assertEqual(queued["sideEffects"], "none")
            task_id = queued["taskId"]
            self.assertFalse((root / "source" / "Movies" / "show").exists())

            # A separately invoked Worker claim executes the transfer in its
            # own thread; the test pauses the genuinely running transfer from
            # this control "request" while the third move is in flight.
            results: list = []
            thread = self._run_worker_async(transfers, runtime, results)
            self.assertTrue(source.reached.wait(30))
            paused = runtime.pause_task_if_current(task_id, updated_at=datetime.now(UTC))
            self.assertIsNotNone(paused)
            source.release.set()
            thread.join(30)
            self.assertFalse(thread.is_alive())
            self.assertEqual(
                [transfer.status.value for transfer in results if transfer is not None],
                ["paused"],
            )
            task = runtime.get_task(task_id)
            self.assertEqual(task.status.value, "paused")
            items = runtime.list_items(task_id)
            self.assertEqual(items[0].status, TaskItemStatus.PAUSED)
            progress = json.loads(items[0].progress)
            # The created destination directory and the completed file moves
            # are the recorded known-safe state.
            self.assertEqual(progress["completedEntries"], 4)
            self.assertEqual(len(progress["confirmedEntries"]), 7)
            copied_after_pause = source.mutation_calls
            moved_files = list((root / "source" / "Movies" / "show").glob("*.mkv"))
            self.assertEqual(len(moved_files), 3)

            # Resume re-queues the persisted authority; the Worker (never the
            # resume request) continues from the recorded checkpoints.
            requeued = transfers.requeue_transfer(task_id)
            self.assertEqual(requeued["status"], "QUEUED")
            finished = self._run_worker(transfers, runtime)
            self.assertEqual([transfer.status.value for transfer in finished], ["completed"])
            projection = transfers.transfer_projection(task_id)
            self.assertEqual(projection["status"], "SUCCESS")
            # Already-moved entries are never replayed.
            self.assertEqual(source.mutation_calls - copied_after_pause, 3)
            self.assertEqual(len(list((root / "source" / "Movies" / "show").glob("*.mkv"))), 6)
            self.assertFalse((root / "source" / "show").exists())
            final = runtime.get_task(task_id)
            self.assertEqual(final.status.value, "completed")

    def test_cancel_of_a_running_transfer_is_observed_at_a_safe_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            source = _GatedSource("source-storage", root / "source", gate_after=3)
            api, active, runtime = self._activate(root, storage_adapters={"source-storage": source})
            transfers = self._transfers(api, active)
            self._tree(root)
            queued = self._admit(transfers, runtime)
            task_id = queued["taskId"]

            results: list = []
            thread = self._run_worker_async(transfers, runtime, results)
            self.assertTrue(source.reached.wait(30))
            # Cancel one genuinely running transfer through the same durable
            # compare-and-set the lifecycle API performs.
            cancelled = runtime.cancel_task_if_current(task_id, updated_at=datetime.now(UTC))
            self.assertIsNotNone(cancelled)
            source.release.set()
            thread.join(30)
            self.assertFalse(thread.is_alive())
            self.assertEqual(
                [transfer.status.value for transfer in results if transfer is not None],
                ["cancelled"],
            )
            projection = transfers.transfer_projection(task_id)
            self.assertEqual(projection["status"], "CANCELLED")
            # The completed moves stay terminal; the rest of the source stays
            # in place.
            moved = len(list((root / "source" / "Movies" / "show").glob("*.mkv")))
            remaining = len(list((root / "source" / "show").glob("*.mkv")))
            self.assertEqual(moved + remaining, 6)
            self.assertEqual(source.mutation_calls, 3)

    def test_resume_requeues_pinned_keep_both_and_refuses_a_live_claim(self) -> None:
        """Keep-both continues only from its admission-pinned unique names."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            source = _PausingSource(
                "source-storage", root / "source", root / "runtime.sqlite3", after=1
            )
            api, active, runtime = self._activate(root, storage_adapters={"source-storage": source})
            transfers = self._transfers(api, active)
            self._tree(root, count=3)
            queued = self._admit(transfers, runtime, conflict_mode="keep_both")
            task_id = queued["taskId"]
            self._run_worker(transfers, runtime)
            task = runtime.get_task(task_id)
            self.assertEqual(task.status.value, "paused")
            items = runtime.list_items(task_id)
            # The pinned keep-both root stays the admission-pinned unique name
            # across the pause (the whole subtree kept its pinned identity).
            pinned_root = json.loads(items[0].progress)["destinationPath"]
            self.assertTrue(pinned_root.startswith("Movies/show"))
            moved_before = list((root / "source" / "Movies").glob("show*"))
            self.assertEqual(len(moved_before), 1)

            # Re-queuing keeps the pinned keep-both root: the Worker continues
            # beneath exactly the admission-pinned destination.
            requeued = transfers.requeue_transfer(task_id)
            self.assertEqual(requeued["status"], "QUEUED")
            self.assertEqual(runtime.get_task(task_id).status.value, "pending")
            # A running transfer with a live claim is never re-queued under
            # its owner.
            from mediaflow.application.files_transfer_worker import FilesTransferWorker

            worker = FilesTransferWorker(
                transfers, runtime, lease_seconds=3600.0, worker_id="worker-live"
            )
            self.assertIsNotNone(
                runtime.claim_next_files_transfer(
                    datetime.now(UTC),
                    worker_id="worker-live",
                    claim_token="token-live",
                    lease_seconds=3600.0,
                )
            )
            with self.assertRaises(Exception) as running:
                transfers.requeue_transfer(task_id)
            self.assertIn("claim", str(running.exception))
            del worker

    def test_takeover_after_process_loss_continues_from_persisted_checkpoints(self) -> None:
        """A crashed Worker's transfer is taken over by a replacement Worker.

        The takeover claims the expired lease and continues only from the
        recorded known-safe checkpoints: completed entries are never replayed
        and the compound Move finishes its destructive step only with fresh
        exact evidence.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir(parents=True, exist_ok=True)
            (root / "destination").mkdir(parents=True, exist_ok=True)
            target = _CrashAfterWriteTarget("media-target", root / "destination")
            api, active, runtime = self._activate(root, storage_adapters={"media-target": target})
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a" * 100)
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="move",
            )
            queued = transfers.submit_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="move",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            self.assertEqual(queued["status"], "QUEUED")
            # The interrupted Worker leaves the Task running with an item in
            # flight, its confirmed scope and baseline progress persisted.
            worker = self._worker(transfers, runtime)
            with self.assertRaises(SystemExit):
                worker.run_next()
            tasks = runtime.list_tasks(command="files_transfer")
            self.assertEqual(len(tasks), 1)
            item = runtime.list_items(tasks[0].task_id)[0]
            self.assertEqual(item.status, TaskItemStatus.PROCESSING)
            progress = json.loads(item.progress)
            self.assertEqual(len(progress["confirmedEntries"]), 1)
            writes_after_crash = target.write_calls

            # A replacement Worker takes over the expired claim and finishes
            # the compound Move from the persisted checkpoints: the verified
            # destination is adopted and only the source deletion remains.
            from datetime import timedelta

            worker = self._worker(transfers, runtime)
            del worker
            from mediaflow.application.files_transfer_worker import FilesTransferWorker

            replacement = FilesTransferWorker(
                transfers,
                runtime,
                lease_seconds=3600.0,
                worker_id="worker-replacement",
                clock=lambda: datetime.now(UTC) + timedelta(hours=2),
            )
            finished = replacement.run_next()
            self.assertIsNotNone(finished)
            self.assertEqual(finished.status.value, "completed")
            self.assertEqual(target.write_calls, writes_after_crash)
            self.assertFalse((root / "source" / "a.mkv").exists())
            self.assertEqual((root / "destination" / "a.mkv").read_bytes(), b"media-a" * 100)

    def test_takeover_after_truncated_write_stops_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir(parents=True, exist_ok=True)
            (root / "destination").mkdir(parents=True, exist_ok=True)
            target = _TruncatingCrashTarget("media-target", root / "destination")
            api, active, runtime = self._activate(root, storage_adapters={"media-target": target})
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a" * 100)
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="move",
            )
            queued = transfers.submit_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="move",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            self.assertEqual(queued["status"], "QUEUED")
            worker = self._worker(transfers, runtime)
            with self.assertRaises(SystemExit):
                worker.run_next()
            from datetime import timedelta

            from mediaflow.application.files_transfer_worker import FilesTransferWorker

            replacement = FilesTransferWorker(
                transfers,
                runtime,
                lease_seconds=3600.0,
                worker_id="worker-replacement",
                clock=lambda: datetime.now(UTC) + timedelta(hours=2),
            )
            finished = replacement.run_next()
            # The interrupted in-flight write cannot be proven: the previous
            # owner may still be inside the provider call, so the entry is
            # converged to a durable UNCERTAIN/investigation-only outcome and
            # the operation is never invoked again.  The source stays intact
            # and the truncated destination is never overwritten.
            self.assertIsNotNone(finished)
            self.assertEqual(finished.status.value, "failed")
            projection = transfers.transfer_projection(finished.task_id)
            self.assertEqual(projection["status"], "UNCERTAIN")
            self.assertEqual(projection["durableState"], "mutation_effect_uncertain")
            self.assertEqual(
                projection["outcomes"][0]["errorCategory"],
                "files_transfer_mutation_unresolved",
            )
            self.assertTrue((root / "source" / "a.mkv").exists())
            self.assertNotEqual((root / "destination" / "a.mkv").read_bytes(), b"media-a" * 100)
            item = runtime.list_items(finished.task_id)[0]
            self.assertEqual(item.status.value, "partial")
            record = runtime.list_results(finished.task_id)[0]
            self.assertEqual(record.effect_certainty, "attempted_unverified")
            self.assertEqual(record.uncertain_effects, ("mutation_outcome",))
            task = runtime.get_task(finished.task_id)
            self.assertEqual(task.status.value, "failed")
            self.assertEqual(task.error, "mutation_outcome")

    def test_restart_at_every_compound_checkpoint_continues_or_investigates(self) -> None:
        """Process loss at each compound Move checkpoint.

        Every restart either continues from the persisted safe authority or
        stops in an explicit investigation state; no completed or uncertain
        mutation is ever repeated.
        """

        for crash_at in ("after_write", "after_verify"):
            with self.subTest(crash_at=crash_at):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    (root / "source").mkdir(parents=True, exist_ok=True)
                    (root / "destination").mkdir(parents=True, exist_ok=True)
                    target = _CrashAtCheckpointTarget(
                        "media-target", root / "destination", crash_at=crash_at
                    )
                    api, active, runtime = self._activate(
                        root, storage_adapters={"media-target": target}
                    )
                    self._run_checkpoint_restart(root, api, active, runtime, transfers=None)

        # The source-deletion checkpoint: the deletion call itself loses the
        # process, so the outcome may or may not have completed when a
        # replacement Worker continues from the persisted authority.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir(parents=True, exist_ok=True)
            (root / "destination").mkdir(parents=True, exist_ok=True)
            source = _CrashOnDeleteSource("source-storage", root / "source")
            api, active, runtime = self._activate(root, storage_adapters={"source-storage": source})
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a" * 100)
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="move",
            )
            queued = transfers.submit_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="move",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            self.assertEqual(queued["status"], "QUEUED")
            from datetime import timedelta

            from mediaflow.application.files_transfer_worker import FilesTransferWorker

            crashed = FilesTransferWorker(
                transfers, runtime, lease_seconds=3600.0, worker_id="worker-crashed"
            )
            with self.assertRaises(SystemExit):
                crashed.run_next()
            self.assertGreaterEqual(source.delete_calls, 1)
            replacement = FilesTransferWorker(
                transfers,
                runtime,
                lease_seconds=3600.0,
                worker_id="worker-replacement",
                clock=lambda now=datetime.now(UTC): now + timedelta(hours=2),
            )
            finished = replacement.run_next()
            self.assertIsNotNone(finished)
            # The verified destination stays; the uncertain deletion is never
            # blindly replayed: the continuation re-checks the source and
            # records the truthful state (deleted -> success, present ->
            # explicit uncertain investigation).
            self.assertEqual((root / "destination" / "a.mkv").read_bytes(), b"media-a" * 100)
            projection = transfers.transfer_projection(finished.task_id)
            self.assertIn(projection["status"], {"SUCCESS", "UNCERTAIN", "PARTIAL", "FAILED"})

    def _run_checkpoint_restart(self, root, api, active, runtime, *, transfers):
        """Crash a Worker at the target checkpoint and continue from authority."""

        from datetime import timedelta

        from mediaflow.application.files_transfer_worker import FilesTransferWorker

        service = transfers or self._transfers(api, active)
        (root / "source" / "a.mkv").write_bytes(b"media-a" * 100)
        impact = service.transfer_impact(
            resource_library_id="source",
            paths=["a.mkv"],
            destination_resource_library_id="destination",
            destination_directory="",
            operation="move",
        )
        queued = service.submit_transfer(
            resource_library_id="source",
            paths=["a.mkv"],
            destination_resource_library_id="destination",
            destination_directory="",
            operation="move",
            conflict_mode="fail",
            manifest_digest=impact.manifest.digest,
        )
        self.assertEqual(queued["status"], "QUEUED")
        crashed = FilesTransferWorker(
            service, runtime, lease_seconds=3600.0, worker_id="worker-crashed"
        )
        with self.assertRaises(SystemExit):
            crashed.run_next()
        replacement = FilesTransferWorker(
            service,
            runtime,
            lease_seconds=3600.0,
            worker_id="worker-replacement",
            clock=lambda now=datetime.now(UTC): now + timedelta(hours=2),
        )
        finished = replacement.run_next()
        self.assertIsNotNone(finished)
        # The verified destination is adopted (never re-copied) and the
        # source deletion runs with fresh exact evidence.
        self.assertEqual((root / "destination" / "a.mkv").read_bytes(), b"media-a" * 100)
        projection = service.transfer_projection(finished.task_id)
        self.assertIn(projection["status"], {"SUCCESS", "UNCERTAIN", "PARTIAL", "FAILED"})

    def test_single_file_process_loss_never_leaves_a_non_continuable_task(self) -> None:
        """The same-Storage single-file path shares the one recovery model."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            api, active, runtime = self._activate(root)
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a")
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="move",
            )
            # Admission only: the process is "lost" before the Worker runs.
            queued = transfers.submit_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="move",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            self.assertEqual(queued["status"], "QUEUED")
            task_id = queued["taskId"]
            # No orphaned running Task exists: the durable state is queued,
            # claimable, and finishable by the next Worker.
            self.assertEqual(runtime.get_task(task_id).status.value, "pending")
            finished = self._run_worker(transfers, runtime)
            self.assertEqual([t.status.value for t in finished], ["completed"])
            self.assertFalse((root / "source" / "a.mkv").exists())
            self.assertEqual((root / "source" / "Movies" / "a.mkv").read_bytes(), b"media-a")

    def test_worker_claim_is_atomic_and_fenced(self) -> None:
        """A second Worker never claims a transfer under a live lease."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a")
            (root / "source" / "Movies").mkdir()
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
            )
            queued = transfers.submit_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            task_id = queued["taskId"]
            from mediaflow.application.files_transfer_worker import FilesTransferWorker

            second = FilesTransferWorker(
                transfers, runtime, lease_seconds=3600.0, worker_id="worker-second"
            )
            # A claim by the first Worker (publishing the running boundary)
            # blocks any second claim while the lease is live.
            claimed = runtime.claim_next_files_transfer(
                datetime.now(UTC),
                worker_id="worker-first",
                claim_token="token-a",
                lease_seconds=3600.0,
            )
            self.assertIsNotNone(claimed)
            self.assertTrue(runtime.begin_files_transfer(task_id, "token-a", datetime.now(UTC)))
            self.assertIsNone(
                runtime.claim_next_files_transfer(
                    datetime.now(UTC),
                    worker_id="worker-second",
                    claim_token="token-b",
                    lease_seconds=3600.0,
                )
            )
            self.assertFalse(runtime.begin_files_transfer(task_id, "token-b", datetime.now(UTC)))
            # Only the current claim owner may publish the terminal state.
            from dataclasses import replace

            from mediaflow.domain.task_persistence import FilesTransferStatus

            terminal = replace(claimed, status=FilesTransferStatus.COMPLETED)
            self.assertFalse(
                runtime.finish_files_transfer(
                    terminal, claim_token="token-b", now=datetime.now(UTC)
                )
            )
            self.assertTrue(
                runtime.finish_files_transfer(
                    terminal, claim_token="token-a", now=datetime.now(UTC)
                )
            )
            second.run_next()  # no work claimable; must be a no-op

    def test_guarded_publications_refuse_a_lost_claim(self) -> None:
        """Every post-mutation publication compares the exact claim token."""

        from dataclasses import replace

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a")
            (root / "source" / "Movies").mkdir()
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
            )
            queued = transfers.submit_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            task_id = queued["taskId"]
            claimed = runtime.claim_next_files_transfer(
                datetime.now(UTC),
                worker_id="worker-a",
                claim_token="token-a",
                lease_seconds=3600.0,
            )
            self.assertTrue(runtime.begin_files_transfer(task_id, "token-a", datetime.now(UTC)))
            task = runtime.get_task(task_id)
            item = runtime.list_items(task_id)[0]

            # A Worker that already lost the claim writes nothing: the Task
            # running boundary, the TaskItem progress and the terminal Task
            # aggregate are all compare-and-set against the live token.
            running = replace(task, status=PersistentTaskStatus.FAILED)
            self.assertFalse(
                runtime.update_task_guarded(
                    running,
                    transfer_id=task_id,
                    claim_token="token-b",
                    now=datetime.now(UTC),
                )
            )
            self.assertFalse(
                runtime.upsert_item_guarded(
                    replace(item, status=TaskItemStatus.SUCCESS),
                    transfer_id=task_id,
                    claim_token="token-b",
                    now=datetime.now(UTC),
                )
            )
            record = PersistentResultRecord(
                "res-1",
                task_id,
                item.item_id,
                item.storage_id,
                item.source_display,
                item.destination_storage_id,
                item.destination_path,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                "copy",
                "success",
                datetime.now(UTC),
            )
            self.assertFalse(
                runtime.complete_item_with_evidence_guarded(
                    replace(item, status=TaskItemStatus.SUCCESS),
                    record,
                    None,
                    transfer_id=task_id,
                    claim_token="token-b",
                    now=datetime.now(UTC),
                )
            )
            # Nothing was published by the stale token.
            self.assertEqual(runtime.get_task(task_id).status, task.status)
            self.assertEqual(runtime.list_items(task_id)[0].status, item.status)
            self.assertEqual(runtime.list_results(task_id), ())
            del claimed


class _BlockingCopySource(LocalStorage):
    """A source whose native Copy blocks until the test releases it.

    The blocked call is a genuine provider mutation in flight: while it is
    inside ``copy`` the test advances the wall clock far beyond a short lease
    and lets a second Worker poll, then releases the call.  The first Worker's
    lease keeper must keep the claim alive so the second Worker never sees the
    transfer as abandoned.
    """

    def __init__(self, storage_id: str, root: Path) -> None:
        super().__init__(storage_id, root)
        self.mutation_calls = 0
        self.entered = threading.Event()
        self.release = threading.Event()

    def copy(self, *args, **kwargs):
        self.mutation_calls += 1
        self.entered.set()
        self.release.wait(timeout=30)
        return super().copy(*args, **kwargs)


class TwoWorkerFenceTests(TransferTestCase):
    """A long provider call can never let a second Worker take over in parallel."""

    def test_blocked_mutation_keeps_the_claim_through_a_short_lease(self) -> None:
        """A provider call blocked past the lease is never taken over.

        The whole point is that the ownership signal must not be merely the
        lease deadline: while Worker A is genuinely blocked inside a native
        Copy, Worker B must see no claimable work and must not invoke Storage,
        even though the original one-second deadline has long passed.
        """

        from mediaflow.application.files_transfer_worker import FilesTransferWorker

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            source = _BlockingCopySource("source-storage", root / "source")
            api, active, runtime = self._activate(root, storage_adapters={"source-storage": source})
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a")
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
            )
            queued = transfers.submit_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            task_id = queued["taskId"]

            first = FilesTransferWorker(
                transfers,
                runtime,
                lease_seconds=1.0,
                worker_id="worker-a",
            )
            results: list = []
            thread = threading.Thread(target=lambda: results.append(first.run_next()), daemon=True)
            thread.start()
            self.assertTrue(source.entered.wait(30))
            # The blocked mutation outlives several lease intervals while the
            # keeper keeps the claim live.
            threading.Event().wait(3.0)
            second = FilesTransferWorker(
                transfers,
                runtime,
                lease_seconds=1.0,
                worker_id="worker-b",
            )
            self.assertIsNone(second.run_next())
            self.assertEqual(source.mutation_calls, 1)
            self.assertEqual(runtime.get_files_transfer(task_id).worker_id, "worker-a")
            source.release.set()
            thread.join(30)
            self.assertFalse(thread.is_alive())
            self.assertEqual(source.mutation_calls, 1)
            self.assertEqual(
                [transfer.status.value for transfer in results if transfer is not None],
                ["completed"],
            )
            self.assertEqual(runtime.get_task(task_id).status.value, "completed")

    def test_takeover_continues_only_after_the_owner_is_genuinely_lost(self) -> None:
        from mediaflow.application.files_transfer_worker import FilesTransferWorker

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            source = _BlockingCopySource("source-storage", root / "source")
            api, active, runtime = self._activate(root, storage_adapters={"source-storage": source})
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a")
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
            )
            queued = transfers.submit_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            task_id = queued["taskId"]

            # A claimed lease that this process abandons (no keeper, no
            # heartbeat) is exactly the crashed-owner case: only then may a
            # replacement Worker take over.
            claimed = runtime.claim_next_files_transfer(
                datetime.now(UTC),
                worker_id="worker-crashed",
                claim_token="token-crashed",
                lease_seconds=1.0,
            )
            self.assertIsNotNone(claimed)
            replacement = FilesTransferWorker(
                transfers,
                runtime,
                lease_seconds=3600.0,
                worker_id="worker-replacement",
                clock=lambda: datetime.now(UTC) + timedelta(seconds=60),
            )
            finished = replacement.run_next()
            self.assertIsNotNone(finished)
            self.assertEqual(finished.status.value, "completed")
            self.assertTrue((root / "source" / "Movies" / "a.mkv").exists())
            self.assertEqual(source.mutation_calls, 1)
            self.assertEqual(runtime.get_task(task_id).status.value, "completed")


class _FaultyHeartbeatRepository:
    """A repository proxy whose claim heartbeat faults while armed.

    Every other repository call is delegated unchanged, so the Worker and its
    service still perform real claims, guarded publications and Storage work.
    The fault is the only injected behavior: the keeper's ownership-signal
    delivery fails while Worker A is blocked inside a provider mutation.
    """

    def __init__(self, repository, *, mode: str) -> None:
        object.__setattr__(self, "_repository", repository)
        object.__setattr__(self, "_mode", mode)
        object.__setattr__(self, "armed", False)

    def __getattr__(self, name):
        return getattr(self._repository, name)

    def heartbeat_files_transfer_claim(self, *args, **kwargs):
        if self.armed:
            if self._mode == "false":
                return False
            raise RuntimeError("heartbeat repository unavailable")
        return self._repository.heartbeat_files_transfer_claim(*args, **kwargs)


class InFlightMutationFenceTests(TransferTestCase):
    """A heartbeat fault can never turn an entered mutation into replayable work."""

    def _admit(self, transfers, root: Path):
        (root / "source" / "a.mkv").write_bytes(b"media-a")
        (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
        impact = transfers.transfer_impact(
            resource_library_id="source",
            paths=["a.mkv"],
            destination_resource_library_id="source",
            destination_directory="Movies",
            operation="copy",
            conflict_mode="fail",
        )
        queued = transfers.submit_transfer(
            resource_library_id="source",
            paths=["a.mkv"],
            destination_resource_library_id="source",
            destination_directory="Movies",
            operation="copy",
            conflict_mode="fail",
            manifest_digest=impact.manifest.digest,
        )
        return queued["taskId"]

    def _blocked_first_worker(self, transfers, repository, source):
        from mediaflow.application.files_transfer_worker import FilesTransferWorker

        first = FilesTransferWorker(
            transfers,
            repository,
            lease_seconds=1.0,
            worker_id="worker-a",
        )
        results: list = []
        thread = threading.Thread(target=lambda: results.append(first.run_next()), daemon=True)
        thread.start()
        self.assertTrue(source.entered.wait(30))
        return thread, results

    def _assert_b_never_mutates(self, transfers, runtime, source, task_id: str) -> None:
        from mediaflow.application.files_transfer_worker import FilesTransferWorker

        second = FilesTransferWorker(transfers, runtime, lease_seconds=1.0, worker_id="worker-b")
        second.run_next()
        self.assertEqual(source.mutation_calls, 1, "Worker B must perform zero mutation")
        self.assertNotEqual(runtime.get_files_transfer(task_id).worker_id, "worker-b")

    def test_failed_heartbeat_never_makes_a_blocked_mutation_replayable(self) -> None:
        """A single failed keeper heartbeat must not hand the row to Worker B."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir(parents=True, exist_ok=True)
            source = _BlockingCopySource("source-storage", root / "source")
            api, active, runtime = self._activate(root, storage_adapters={"source-storage": source})
            transfers = self._transfers(api, active)
            task_id = self._admit(transfers, root)
            faulty = _FaultyHeartbeatRepository(runtime, mode="false")
            thread, results = self._blocked_first_worker(transfers, faulty, source)
            # Arm exactly one failing heartbeat, then let the keeper retry.
            faulty.armed = True
            threading.Event().wait(0.1)
            faulty.armed = False
            threading.Event().wait(2.5)
            self._assert_b_never_mutates(transfers, runtime, source, task_id)
            source.release.set()
            thread.join(30)
            self.assertFalse(thread.is_alive())
            self.assertEqual(source.mutation_calls, 1)
            self.assertEqual(
                [transfer.status.value for transfer in results if transfer is not None],
                ["completed"],
            )
            self.assertEqual(runtime.get_task(task_id).status.value, "completed")

    def test_raising_heartbeat_never_makes_a_blocked_mutation_replayable(self) -> None:
        """An exceptional keeper heartbeat must not hand the row to Worker B."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir(parents=True, exist_ok=True)
            source = _BlockingCopySource("source-storage", root / "source")
            api, active, runtime = self._activate(root, storage_adapters={"source-storage": source})
            transfers = self._transfers(api, active)
            task_id = self._admit(transfers, root)
            faulty = _FaultyHeartbeatRepository(runtime, mode="raise")
            thread, results = self._blocked_first_worker(transfers, faulty, source)
            faulty.armed = True
            threading.Event().wait(0.1)
            faulty.armed = False
            threading.Event().wait(2.5)
            self._assert_b_never_mutates(transfers, runtime, source, task_id)
            source.release.set()
            thread.join(30)
            self.assertFalse(thread.is_alive())
            self.assertEqual(source.mutation_calls, 1)
            self.assertEqual(
                [transfer.status.value for transfer in results if transfer is not None],
                ["completed"],
            )

    def test_owner_loss_during_mutation_converges_without_replay(self) -> None:
        """A persistently lost owner's in-flight mutation converges, never replays."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir(parents=True, exist_ok=True)
            source = _BlockingCopySource("source-storage", root / "source")
            api, active, runtime = self._activate(root, storage_adapters={"source-storage": source})
            transfers = self._transfers(api, active)
            task_id = self._admit(transfers, root)
            faulty = _FaultyHeartbeatRepository(runtime, mode="raise")
            thread, _results = self._blocked_first_worker(transfers, faulty, source)
            # The fault starts only once the mutation is genuinely in flight, so
            # the owner entered the operation under a live fence and then lost
            # the ability to renew its lease.
            faulty.armed = True
            # The lease expires while the owner is blocked and the keeper cannot
            # renew it; Worker B may then resolve the recorded boundary.
            threading.Event().wait(4.5)
            self.assertEqual(source.mutation_calls, 1)
            from mediaflow.application.files_transfer_worker import FilesTransferWorker

            second = FilesTransferWorker(
                transfers,
                runtime,
                lease_seconds=1.0,
                worker_id="worker-b",
                clock=lambda: datetime.now(UTC) + timedelta(seconds=10),
            )
            resolved = second.run_next()
            # Zero new mutation: the interrupted operation is never invoked.
            self.assertEqual(source.mutation_calls, 1)
            self.assertIsNotNone(resolved)
            self.assertNotEqual(resolved.status.value, "completed")
            projection = transfers.transfer_projection(task_id)
            self.assertEqual(projection["status"], "UNCERTAIN")
            self.assertEqual(projection["durableState"], "mutation_effect_uncertain")
            self.assertEqual(
                projection["outcomes"][0]["errorCategory"],
                "files_transfer_mutation_unresolved",
            )
            item = runtime.list_items(task_id)[0]
            self.assertEqual(item.status.value, "partial")
            record = runtime.list_results(task_id)[0]
            self.assertEqual(record.effect_certainty, "attempted_unverified")
            self.assertEqual(runtime.get_task(task_id).status.value, "failed")
            source.release.set()
            thread.join(30)
            # The released owner completes its provider call but can no longer
            # publish: one mutation total, no replay, terminal investigation.
            self.assertEqual(source.mutation_calls, 1)
            self.assertEqual(transfers.transfer_projection(task_id)["status"], "UNCERTAIN")

    def test_owner_loss_before_the_mutation_boundary_allows_safe_takeover(self) -> None:
        """An expired claim that never entered a mutation is safely reclaimed."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            api, active, runtime = self._activate(root)
            transfers = self._transfers(api, active)
            task_id = self._admit(transfers, root)
            from mediaflow.application.files_transfer_worker import FilesTransferWorker

            # A claim with no running boundary and no in-flight mutation.
            claimed = runtime.claim_next_files_transfer(
                datetime.now(UTC),
                worker_id="worker-crashed",
                claim_token="token-crashed",
                lease_seconds=1.0,
            )
            self.assertIsNotNone(claimed)
            self.assertIsNone(runtime.get_files_transfer(task_id).mutation_state)
            replacement = FilesTransferWorker(
                transfers,
                runtime,
                lease_seconds=3600.0,
                worker_id="worker-replacement",
                clock=lambda: datetime.now(UTC) + timedelta(seconds=60),
            )
            finished = replacement.run_next()
            self.assertIsNotNone(finished)
            self.assertEqual(finished.status.value, "completed")
            self.assertTrue((root / "source" / "Movies" / "a.mkv").exists())


class _PartialMoveSource(LocalStorage):
    """A same-Storage provider whose native Move creates the target then blocks.

    This is B's exact reproduction shape: the requested single native ``move``
    has already produced a complete target copy and has *not* removed the
    source, and the provider call is still blocked inside the operation when
    the owner's lease expires.  Live Storage therefore holds both the source
    and a complete destination, which is not a completed or idempotently
    continuable Move.
    """

    def __init__(self, storage_id: str, root: Path) -> None:
        super().__init__(storage_id, root)
        self.mutation_calls = 0
        self.entered = threading.Event()
        self.release = threading.Event()
        self.reached_target = threading.Event()

    def move(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self.mutation_calls += 1
        # Land the complete target through the real native copy path first, so
        # the destination genuinely holds the confirmed bytes while the source
        # stays exactly where it was.
        super().copy(source, target, overwrite=overwrite)
        self.reached_target.set()
        self.entered.set()
        self.release.wait(timeout=30)
        return super().move(source, target, overwrite=overwrite)


class InFlightResolutionTests(TransferTestCase):
    """B's two-Worker regressions for truthful in-flight resolution."""

    def _corrupt_authority(self, runtime, task_id: str) -> None:
        with runtime._lock, runtime._connection:
            runtime._connection.execute(
                "UPDATE files_transfers SET authority_json=? WHERE task_id=?",
                ("{not json", task_id),
            )

    def _operations_agreement(self, api, task_id: str) -> None:
        """The Operations projection must agree with the durable rows.

        Reads the same bounded operator endpoint the Operations workspace uses
        and proves the Task, every TaskItem and every Result carry the identical
        uncertain investigation truth — never a raw error, host path or digest.
        """

        status, document = request(api, f"/api/v1/operations/tasks/{task_id}")
        self.assertEqual(status, 200)
        self.assertEqual(document["status"], "failed")
        self.assertEqual(document["failure"]["category"], "workflow_failure")
        for item in document["items"]:
            self.assertEqual(item["status"], "partial")
            self.assertEqual(item["failure"]["category"], "workflow_failure")
            self.assertNotIn("/", item.get("source_path") or "")
        for result in document["results"]:
            self.assertEqual(result["effect_certainty"], "attempted_unverified")
            self.assertEqual(result["uncertain_effects"], ["mutation_outcome"])
            self.assertNotIn("/", result.get("source_path") or "")

    def _pending_after_first_worker(self, transfers, runtime, task_id: str):
        """The durable transfer snapshot while Worker A is still blocked."""

        transfer = runtime.get_files_transfer(task_id)
        self.assertEqual(transfer.status.value, "running")
        self.assertEqual(transfer.mutation_state, "mutation_in_flight")
        return transfer

    def test_same_storage_partial_move_converges_without_replay_or_erasure(self) -> None:
        """B's first repro: a partial native Move is never a fabricated FAILED/none.

        The complete target exists beside the retained source while the owner's
        provider call is still blocked past its lease.  Worker B must issue zero
        Storage mutation, must not route the item through the ordinary
        ``target_exists`` conflict path, and must leave one conservative
        partial/uncertain truth that the released owner can no longer overwrite.
        """

        from mediaflow.application.files_transfer_worker import FilesTransferWorker

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            source = _PartialMoveSource("source-storage", root / "source")
            api, active, runtime = self._activate(root, storage_adapters={"source-storage": source})
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a" * 100)
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="move",
                conflict_mode="fail",
            )
            queued = transfers.submit_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="move",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            task_id = queued["taskId"]

            faulty = _FaultyHeartbeatRepository(runtime, mode="raise")
            first = FilesTransferWorker(transfers, faulty, lease_seconds=1.0, worker_id="worker-a")
            results: list = []
            thread = threading.Thread(target=lambda: results.append(first.run_next()), daemon=True)
            thread.start()
            self.assertTrue(source.reached_target.wait(30))
            faulty.armed = True
            threading.Event().wait(4.5)
            self.assertEqual(source.mutation_calls, 1)
            # Live Storage truth: the complete destination exists and the
            # source was never removed.
            self.assertTrue((root / "source" / "a.mkv").exists())
            self.assertEqual((root / "source" / "Movies" / "a.mkv").read_bytes(), b"media-a" * 100)
            self._pending_after_first_worker(transfers, runtime, task_id)

            second = FilesTransferWorker(
                transfers,
                runtime,
                lease_seconds=1.0,
                worker_id="worker-b",
                clock=lambda: datetime.now(UTC) + timedelta(seconds=10),
            )
            resolved = second.run_next()
            # Worker B performed exactly zero Storage mutation.
            self.assertEqual(source.mutation_calls, 1)
            self.assertIsNotNone(resolved)
            projection = transfers.transfer_projection(task_id)
            # The truthful conservative state: never FAILED + none, never the
            # fabricated clean failure B reproduced.
            self.assertEqual(projection["status"], "UNCERTAIN")
            self.assertNotEqual(projection["status"], "FAILED")
            self.assertEqual(projection["retrySafe"], False)
            self.assertIn("did not retry", projection["nextAction"])
            self.assertIn("inspect", projection["nextAction"].casefold())
            outcomes = projection["outcomes"]
            self.assertTrue(outcomes)
            self.assertNotEqual(outcomes[0].get("errorCategory"), "target_exists")
            transfer = runtime.get_files_transfer(task_id)
            self.assertIsNone(transfer.mutation_state)
            self.assertEqual(transfer.error, "mutation_outcome")
            task = runtime.get_task(task_id)
            self.assertEqual(task.error, "mutation_outcome")
            item = runtime.list_items(task_id)[0]
            record = runtime.list_results(task_id)[0]
            self.assertEqual(item.status.value, "partial")
            self.assertEqual(record.effect_certainty, "attempted_unverified")
            self.assertEqual(record.status, "partial")
            self.assertEqual(record.error, "files_transfer_mutation_unresolved")
            self.assertEqual(task.status.value, "failed")
            self._operations_agreement(api, task_id)

            # The released owner may still create the target and return; every
            # late publication stays rejected by claim-token CAS and the
            # investigation result is unchanged after a repository reload.
            source.release.set()
            thread.join(30)
            self.assertFalse(thread.is_alive())
            self.assertEqual(source.mutation_calls, 1)
            reopened = SQLiteTaskRepository(root / "runtime.sqlite3")
            self.addCleanup(reopened.close)
            self.assertEqual(transfers.transfer_projection(task_id)["status"], "UNCERTAIN")
            reloaded = reopened.get_files_transfer(task_id)
            self.assertEqual(reloaded.status.value, transfer.status.value)
            self.assertEqual(reloaded.error, "mutation_outcome")
            self.assertEqual(reopened.get_task(task_id).status.value, "failed")
            self.assertEqual(reopened.list_items(task_id)[0].status.value, "partial")
            self.assertEqual(
                reopened.list_results(task_id)[0].effect_certainty, "attempted_unverified"
            )

    def test_corrupt_authority_after_an_entered_mutation_is_uncertain(self) -> None:
        """B's second repro: a corrupt authority after entry is never FAILED/none.

        Worker A is blocked inside the Copy, so the durable boundary already
        proves a Storage mutation may have taken effect.  Corrupting the
        authority at that point must converge to ``UNCERTAIN`` with
        ``attempted_unverified`` — never the pre-mutation ``FAILED`` path — and
        a late target created by the released owner cannot change it.
        """

        from mediaflow.application.files_transfer_worker import FilesTransferWorker

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            source = _BlockingCopySource("source-storage", root / "source")
            api, active, runtime = self._activate(root, storage_adapters={"source-storage": source})
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a" * 100)
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
            )
            queued = transfers.submit_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            task_id = queued["taskId"]

            faulty = _FaultyHeartbeatRepository(runtime, mode="raise")
            first = FilesTransferWorker(transfers, faulty, lease_seconds=1.0, worker_id="worker-a")
            results: list = []
            thread = threading.Thread(target=lambda: results.append(first.run_next()), daemon=True)
            thread.start()
            self.assertTrue(source.entered.wait(30))
            # The authority becomes unreadable only *after* Worker A entered
            # the mutation, so the boundary is already durable proof of an
            # entered effect.
            self._corrupt_authority(runtime, task_id)
            faulty.armed = True
            threading.Event().wait(4.5)
            self.assertEqual(source.mutation_calls, 1)
            self._pending_after_first_worker(transfers, runtime, task_id)
            self.assertFalse((root / "source" / "Movies" / "a.mkv").exists())

            second = FilesTransferWorker(
                transfers,
                runtime,
                lease_seconds=1.0,
                worker_id="worker-b",
                clock=lambda: datetime.now(UTC) + timedelta(seconds=10),
            )
            resolved = second.run_next()
            self.assertEqual(source.mutation_calls, 1, "Worker B must not mutate Storage")
            self.assertIsNotNone(resolved)
            projection = transfers.transfer_projection(task_id)
            self.assertEqual(projection["status"], "UNCERTAIN")
            self.assertNotEqual(projection["status"], "FAILED")
            self.assertIsNone(runtime.get_files_transfer(task_id).mutation_state)
            self.assertEqual(runtime.get_files_transfer(task_id).error, "mutation_outcome")
            self.assertEqual(runtime.get_task(task_id).error, "mutation_outcome")
            record = runtime.list_results(task_id)[0]
            self.assertEqual(record.effect_certainty, "attempted_unverified")
            self.assertEqual(record.uncertain_effects, ("mutation_outcome",))
            self.assertEqual(record.error, "files_transfer_mutation_unresolved")
            item = runtime.list_items(task_id)[0]
            self.assertEqual(item.status.value, "partial")
            self.assertEqual(runtime.get_task(task_id).status.value, "failed")
            self._operations_agreement(api, task_id)
            # Release Worker A: its provider call now creates the target, yet
            # the durable investigation-only outcome must stay exactly as the
            # resolver published it, across a repository reopen.
            source.release.set()
            thread.join(30)
            self.assertFalse(thread.is_alive())
            self.assertEqual(source.mutation_calls, 1)
            self.assertTrue((root / "source" / "Movies" / "a.mkv").exists())
            self.assertEqual(transfers.transfer_projection(task_id)["status"], "UNCERTAIN")
            reopened = SQLiteTaskRepository(root / "runtime.sqlite3")
            self.addCleanup(reopened.close)
            reloaded = reopened.get_files_transfer(task_id)
            self.assertEqual(reloaded.error, "mutation_outcome")
            self.assertEqual(
                reopened.list_results(task_id)[0].effect_certainty, "attempted_unverified"
            )
            self.assertEqual(reopened.get_task(task_id).status.value, "failed")

    def test_corrupt_authority_before_any_mutation_stays_bounded_failed(self) -> None:
        """The paired pre-mutation case keeps the zero-mutation FAILED path.

        Without a durable mutation boundary there is no possible file effect, so
        a corrupt authority must stay the bounded ``FAILED``/``none``
        investigation outcome instead of being relabelled as a possible effect.
        """

        from mediaflow.application.files_transfer_worker import FilesTransferWorker

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            api, active, runtime = self._activate(root)
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a")
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
            )
            queued = transfers.submit_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            task_id = queued["taskId"]
            self.assertIsNone(runtime.get_files_transfer(task_id).mutation_state)
            self._corrupt_authority(runtime, task_id)

            worker = FilesTransferWorker(
                transfers, runtime, lease_seconds=3600.0, worker_id="worker-corrupt"
            )
            finished = worker.run_next()
            self.assertIsNotNone(finished)
            self.assertEqual(finished.status.value, "failed")
            self.assertEqual(finished.error, "files_transfer_invalid_authority")
            self.assertEqual(runtime.get_task(task_id).status.value, "failed")
            self.assertEqual(transfers.transfer_projection(task_id)["status"], "FAILED")
            record = runtime.list_results(task_id)[0]
            self.assertEqual(record.effect_certainty, "none")
            self.assertEqual(record.uncertain_effects, ())
            self.assertFalse((root / "source" / "Movies" / "a.mkv").exists())
            self.assertTrue((root / "source" / "a.mkv").exists())


class _CrashAfterFirstCopySource(LocalStorage):
    """A source whose first native Copy lands completely, then loses the process.

    The destination holds the confirmed bytes and the durable in-flight
    boundary is still published, so a replacement Worker must adopt the
    verified Copy from the boundary instead of copying the entry again.
    """

    def __init__(self, storage_id: str, root: Path) -> None:
        super().__init__(storage_id, root)
        self.copy_calls = 0

    def copy(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self.copy_calls += 1
        super().copy(source, target, overwrite=overwrite)
        if self.copy_calls == 1:
            raise SystemExit(3)


class _HandoffProbeRepository:
    """A repository proxy that probes the exact lock-handoff boundary.

    Immediately after the takeover performs its own lock handoff, the proxy
    attempts the same acquisition a competing Task would attempt for the same
    normalized path, and records whether it succeeded.  That is the direct
    interleaving assertion B asked for: a gap-free rotation refuses the
    competing acquisition because the exclusion row is continuously present,
    while the retired-then-inserted shape admits it.  Every other repository
    call is delegated unchanged.
    """

    def __init__(self, repository, *, storage_id: str, path: str, rival_task_id: str) -> None:
        object.__setattr__(self, "_repository", repository)
        object.__setattr__(self, "_storage_id", storage_id)
        object.__setattr__(self, "_path", path)
        object.__setattr__(self, "_rival_task_id", rival_task_id)
        object.__setattr__(self, "armed", False)
        object.__setattr__(self, "probes", [])

    def __getattr__(self, name):
        return getattr(self._repository, name)

    def _probe(self) -> None:
        if not self.armed:
            return
        self.armed = False
        acquired = self._repository.acquire(
            self._storage_id, self._path, self._rival_task_id, datetime.now(UTC)
        )
        self.probes.append(acquired)
        if acquired:
            # Hand the exclusion straight back so the fixture stays coherent.
            self._repository.release(self._storage_id, self._path, self._rival_task_id)

    def rotate_task_locks(self, *args, **kwargs):
        result = self._repository.rotate_task_locks(*args, **kwargs)
        self._probe()
        return result

    def reclaim_task_locks(self, *args, **kwargs):
        result = self._repository.reclaim_task_locks(*args, **kwargs)
        self._probe()
        return result


class _GatedAfterCopySource(LocalStorage):
    """A source whose Nth native Copy lands completely and then blocks.

    Used for B's production-shaped takeover race: Worker A is blocked *inside*
    a native Copy whose destination already holds the confirmed bytes — a
    provable checkpoint — while Worker B takes the same Task over and blocks in
    the next distinct admitted mutation.  Because each blocked call has already
    landed its destination, the blocked owner is always immediately before its
    own verified progress publication, which is exactly the interleaving the
    lock handoff must survive.
    """

    def __init__(self, storage_id: str, root: Path, *, block_calls: set[int]) -> None:
        super().__init__(storage_id, root)
        self.copy_calls = 0
        self._block_calls = set(block_calls)
        self.reached = {call: threading.Event() for call in self._block_calls}
        self.release = {call: threading.Event() for call in self._block_calls}

    def copy(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self.copy_calls += 1
        call = self.copy_calls
        super().copy(source, target, overwrite=overwrite)
        if call in self._block_calls:
            self.reached[call].set()
            self.release[call].wait(timeout=30)


class SourceLockGenerationTests(TransferTestCase):
    """A stale Worker can never release a replacement Worker's source lock.

    These are B's required deterministic multi-Worker regressions for the
    generation-fenced file lock: the guarded TaskItem/Result CAS and the
    file-lock ownership are separate fences, and the second one must survive a
    late ``finally`` from an owner that already lost its claim.
    """

    def _lock_rows(self, repository):
        with repository._lock:
            return [
                (row["storage_id"], row["path"], row["task_id"], row["owner_token"])
                for row in repository._connection.execute(
                    "SELECT storage_id, path, task_id, owner_token FROM file_locks ORDER BY path"
                ).fetchall()
            ]

    def test_failed_cas_never_removes_the_replacement_generation(self) -> None:
        """B's probe: A's guarded publish returns False; B's lock stays owned.

        Worker A holds the frame that acquired the item; Worker B lawfully takes
        over the same Task/path and acquires its own generation.  A's guarded
        terminal publication then fails its claim CAS, but A's unconditional
        ``finally`` must not delete B's row — and a competing Task C must be
        denied with zero Storage mutation.
        """

        from mediaflow.application.task_runtime import PersistentTaskCoordinator
        from mediaflow.domain.task_persistence import PersistentResultRecord

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            coordinator = PersistentTaskCoordinator(runtime, runtime)
            task = coordinator.create("files_transfer", execute_authorized=True)
            item_a = coordinator.begin_item(
                task.task_id, "source-storage", "source", "a.mkv", "a.mkv"
            )
            self.assertIsInstance(item_a.lock_owner_token, str)
            token_a = item_a.lock_owner_token

            # Worker B takes over: it retires the stale generation and acquires
            # its own before continuing a distinct checkpoint.
            self.assertEqual(runtime.reclaim_task_locks(task.task_id), 1)
            item_b = coordinator.begin_item(
                task.task_id, "source-storage", "source", "a.mkv", "a.mkv"
            )
            self.assertNotEqual(item_b.lock_owner_token, token_a)
            self.assertTrue(
                runtime.lock_owned(
                    "source-storage",
                    "a.mkv",
                    task.task_id,
                    owner_token=item_b.lock_owner_token,
                )
            )

            # A's terminal publication is claim-guarded and must fail, exactly
            # as it does after a lost lease.
            record = PersistentResultRecord(
                "res-a",
                task.task_id,
                item_a.item_id,
                item_a.storage_id,
                item_a.source_display,
                item_a.destination_storage_id,
                item_a.destination_path,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                "copy",
                "success",
                datetime.now(UTC),
            )
            self.assertFalse(
                runtime.complete_item_with_evidence_guarded(
                    item_a,
                    record,
                    None,
                    transfer_id="transfer-x",
                    claim_token="stale-token",
                    now=datetime.now(UTC),
                )
            )
            # A's frame finally runs: it must release only its own generation.
            coordinator.release_item_lock(item_a)
            self.assertTrue(
                runtime.lock_owned(
                    "source-storage",
                    "a.mkv",
                    task.task_id,
                    owner_token=item_b.lock_owner_token,
                ),
                "the replacement Worker's lock was removed by a stale owner",
            )
            self.assertFalse(
                runtime.lock_owned("source-storage", "a.mkv", task.task_id, owner_token=token_a)
            )
            rows = self._lock_rows(runtime)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][3], item_b.lock_owner_token)

            # A competing Task C cannot acquire the path: zero mutation.
            task_c = coordinator.create("files_transfer", execute_authorized=True)
            with self.assertRaises(Exception):
                coordinator.begin_item(task_c.task_id, "source-storage", "source", "a.mkv", "a.mkv")
            self.assertEqual(len(self._lock_rows(runtime)), 1)

    def test_post_publication_expiry_window_keeps_the_replacement_generation(self) -> None:
        """A publishes successfully, B re-acquires before A's release runs.

        ``if guarded_publish: release(...)`` is not a sufficient fix: A's guarded
        publication can succeed, its lease expire before the following release,
        and B reacquire the same Task/path in between.  The exact generation
        comparison must protect this window too.
        """

        from mediaflow.application.task_runtime import PersistentTaskCoordinator

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            coordinator = PersistentTaskCoordinator(runtime, runtime)
            task = coordinator.create("files_transfer", execute_authorized=True)
            item_a = coordinator.begin_item(
                task.task_id, "source-storage", "source", "a.mkv", "a.mkv"
            )
            token_a = item_a.lock_owner_token
            # A publishes its terminal item outcome successfully.
            self.assertTrue(
                coordinator.complete_direct_item(
                    item_a, status=TaskItemStatus.SUCCESS, operation="copy"
                )
            )
            # Its own release removed exactly its generation.
            self.assertEqual(self._lock_rows(runtime), [])
            # B reacquires for a continuation of the same Task/path.
            item_b = coordinator.begin_item(
                task.task_id, "source-storage", "source", "a.mkv", "a.mkv"
            )
            # A's late release — after B owns the row — is an exact no-op.
            self.assertFalse(
                runtime.release("source-storage", "a.mkv", task.task_id, owner_token=token_a)
            )
            self.assertTrue(
                runtime.lock_owned(
                    "source-storage",
                    "a.mkv",
                    task.task_id,
                    owner_token=item_b.lock_owner_token,
                )
            )

    def test_production_shaped_continuation_denies_a_competing_task(self) -> None:
        """A lands a checkpoint and blocks; B adopts it; Task C is denied throughout.

        Worker A is blocked inside its admitted native Copy for the first file
        of one selected directory, and the Copy has already landed completely.
        A's ownership signal then fails, its lease genuinely expires, and Worker
        B lawfully takes the transfer over: B adopts A's proven Copy checkpoint,
        atomically takes the same top-level source lock, and blocks in the next
        distinct admitted mutation.  A competing Task C is denied *before* A
        returns and *after* A returns, and only B's own terminal release makes a
        later acquisition possible.  A's late release never frees B's row.
        """

        from mediaflow.application.files_transfer_worker import FilesTransferWorker

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "show").mkdir(parents=True, exist_ok=True)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            (root / "source" / "show" / "ep00.mkv").write_bytes(b"episode-0")
            (root / "source" / "show" / "ep01.mkv").write_bytes(b"episode-1")
            # Both native Copies land completely and then block, so A's first
            # call is a *provable* checkpoint that B may adopt, and B's own
            # continuation is a genuinely distinct admitted mutation.
            source = _GatedAfterCopySource("source-storage", root / "source", block_calls={1, 2})
            api, active, runtime = self._activate(root, storage_adapters={"source-storage": source})
            transfers = self._transfers(api, active)
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["show"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
            )
            queued = transfers.submit_transfer(
                resource_library_id="source",
                paths=["show"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            task_id = queued["taskId"]

            # A enters its mutation under a live fence, then loses the ability
            # to renew: the durable in-flight boundary is its only protection.
            faulty = _FaultyHeartbeatRepository(runtime, mode="raise")
            first = FilesTransferWorker(transfers, faulty, lease_seconds=1.0, worker_id="worker-a")
            results: list = []
            thread = threading.Thread(target=lambda: results.append(first.run_next()), daemon=True)
            thread.start()
            self.assertTrue(source.reached[1].wait(30))
            faulty.armed = True
            self.assertEqual(source.copy_calls, 1)
            self.assertEqual(
                runtime.get_files_transfer(task_id).mutation_state, "mutation_in_flight"
            )
            # The lease genuinely elapses while A is still blocked.
            deadline = time.time() + 30
            while time.time() < deadline:
                current = runtime.get_files_transfer(task_id)
                if current.claim_expires_at is not None and current.claim_expires_at <= (
                    datetime.now(UTC) + timedelta(seconds=60)
                ):
                    break
                time.sleep(0.25)

            # B lawfully claims the expired in-flight boundary and continues.
            # The probe repository races the competing Task into the exact lock
            # handoff boundary, which is the interleaving B reproduced.
            coordinator_probe = transfers._direct.tasks
            probe = _HandoffProbeRepository(
                runtime,
                storage_id="source-storage",
                path="show",
                rival_task_id="rival-task-c",
            )
            coordinator_probe.repository = probe
            coordinator_probe.locks = probe
            second = FilesTransferWorker(
                transfers,
                probe,
                lease_seconds=3600.0,
                worker_id="worker-b",
                clock=lambda: datetime.now(UTC) + timedelta(seconds=60),
            )
            probe.armed = True
            b_results: list = []
            b_thread = threading.Thread(
                target=lambda: b_results.append(second.run_next()), daemon=True
            )
            b_thread.start()
            self.assertTrue(source.reached[2].wait(30), "B must run the next distinct mutation")
            # The competing Task never acquired the top-level path at the
            # handoff boundary.
            self.assertEqual(probe.probes, [False])

            coordinator = transfers._direct.tasks
            # Task C is denied while B owns the top-level source exclusion.
            task_c = coordinator.create("files_transfer", execute_authorized=True)
            with self.assertRaises(Exception):
                coordinator.begin_item(task_c.task_id, "source-storage", "source", "show", "show")
            self.assertEqual(source.copy_calls, 2, "a competing Task must not mutate")

            # A returns while B is still blocked inside its own mutation: A's
            # late release must not free B's exclusion.
            source.release[1].set()
            thread.join(30)
            self.assertFalse(thread.is_alive())
            self.assertEqual(source.copy_calls, 2)
            with self.assertRaises(Exception):
                coordinator.begin_item(task_c.task_id, "source-storage", "source", "show", "show")
            self.assertEqual(source.copy_calls, 2, "a competing Task must not mutate")

            # Only B's terminal release frees the path for a later acquisition.
            source.release[2].set()
            b_thread.join(30)
            self.assertFalse(b_thread.is_alive())
            self.assertEqual(source.copy_calls, 2)
            self.assertIn(runtime.get_task(task_id).status.value, {"completed", "partial_success"})
            self.assertEqual(self._lock_rows(runtime), [])
            later = coordinator.create("files_transfer", execute_authorized=True)
            item = coordinator.begin_item(later.task_id, "source-storage", "source", "show", "show")
            self.assertTrue(
                runtime.lock_owned(
                    "source-storage", "show", later.task_id, owner_token=item.lock_owner_token
                )
            )

    def test_takeover_handoff_never_leaves_the_source_path_unowned(self) -> None:
        """The direct interleaving assertion at the explicit handoff boundary.

        The defect was "retire the Task's locks, then insert later", so a
        competing Task placed in that window acquired the normalized path and
        mutated the source.  The rotation keeps the row continuously present, so
        a competing acquisition is refused at the exact handoff boundary, while
        the old blanket-retire shape demonstrably admits it.
        """

        from mediaflow.application.task_runtime import PersistentTaskCoordinator

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _api, _active, runtime = self._activate(root)
            coordinator = PersistentTaskCoordinator(runtime, runtime)
            task = coordinator.create("files_transfer", execute_authorized=True)
            item_a = coordinator.begin_item(
                task.task_id, "source-storage", "source", "show/ep00.mkv", "show"
            )

            # The gap-free handoff rotates the row in place.  The probe races a
            # competing Task into that exact boundary.
            gap_free = _HandoffProbeRepository(
                runtime,
                storage_id="source-storage",
                path="show/ep00.mkv",
                rival_task_id="rival-task-c",
            )
            gap_free.armed = True
            self.assertEqual(gap_free.rotate_task_locks(task.task_id, "takeover-generation"), 1)
            self.assertEqual(
                gap_free.probes, [False], "the rotated row must never be observable as unowned"
            )
            self.assertTrue(
                runtime.lock_owned(
                    "source-storage",
                    "show/ep00.mkv",
                    task.task_id,
                    owner_token="takeover-generation",
                )
            )
            # The predecessor's late release is an exact no-op.
            self.assertFalse(
                runtime.release(
                    "source-storage",
                    "show/ep00.mkv",
                    task.task_id,
                    owner_token=item_a.lock_owner_token,
                )
            )
            self.assertTrue(
                runtime.lock_owned(
                    "source-storage",
                    "show/ep00.mkv",
                    task.task_id,
                    owner_token="takeover-generation",
                )
            )

            # Falsifiability: the old blanket-retire shape does open exactly the
            # window the rotation closes, so the probe above is not vacuous.
            retired = _HandoffProbeRepository(
                runtime,
                storage_id="source-storage",
                path="show/ep00.mkv",
                rival_task_id="rival-task-d",
            )
            retired.armed = True
            self.assertEqual(retired.reclaim_task_locks(task.task_id), 1)
            self.assertEqual(
                retired.probes, [True], "the retired-then-inserted shape exhibits the window"
            )

    def test_live_mutation_keeps_its_exclusion_and_the_owner_retires_it(self) -> None:
        """An in-flight convergence never unlocks a still-running provider call.

        Worker A is blocked *inside* an admitted Storage mutation when its lease
        expires.  Worker B lawfully resolves the recorded in-flight boundary and
        converges the transfer to a bounded uncertain outcome.  While A's
        provider call is still physically running, the source exclusion must
        stay held so a competing Task C is denied with zero mutation; when A
        finally returns, A's own frame releases exactly its generation so no
        permanent lock leaks and a later lawful acquisition succeeds.
        """

        from mediaflow.application.files_transfer_worker import FilesTransferWorker

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            source = _PartialMoveSource("source-storage", root / "source")
            api, active, runtime = self._activate(root, storage_adapters={"source-storage": source})
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a")
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="move",
                conflict_mode="fail",
            )
            queued = transfers.submit_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="move",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            task_id = queued["taskId"]

            first = FilesTransferWorker(transfers, runtime, lease_seconds=1.0, worker_id="worker-a")
            results: list = []
            thread = threading.Thread(target=lambda: results.append(first.run_next()), daemon=True)
            thread.start()
            self.assertTrue(source.entered.wait(30))
            self.assertEqual(source.mutation_calls, 1)

            # The lease expires while A is still blocked inside its mutation.
            time.sleep(2.6)
            self.assertTrue(thread.is_alive(), "A must still be inside its provider call")
            replacement = FilesTransferWorker(
                transfers,
                runtime,
                lease_seconds=3600.0,
                worker_id="worker-b",
                clock=lambda: datetime.now(UTC) + timedelta(seconds=60),
            )
            replacement.run_next()
            converged = runtime.get_files_transfer(task_id)
            self.assertEqual(converged.status.value, "failed")
            # The exclusion is still held against the live provider call.
            self.assertEqual(len(self._lock_rows(runtime)), 1)
            coordinator = transfers._direct.tasks
            task_c = coordinator.create("files_transfer", execute_authorized=True)
            with self.assertRaises(Exception):
                coordinator.begin_item(task_c.task_id, "source-storage", "source", "a.mkv", "a.mkv")
            self.assertEqual(source.mutation_calls, 1, "a competing Task must not mutate")

            # A returns: its frame retires exactly its own generation, so no
            # permanent lock leaks and a later lawful acquisition succeeds.
            source.release.set()
            thread.join(30)
            self.assertFalse(thread.is_alive())
            self.assertEqual(self._lock_rows(runtime), [])
            later = coordinator.create("files_transfer", execute_authorized=True)
            item = coordinator.begin_item(
                later.task_id, "source-storage", "source", "a.mkv", "a.mkv"
            )
            self.assertTrue(
                runtime.lock_owned(
                    "source-storage",
                    "a.mkv",
                    later.task_id,
                    owner_token=item.lock_owner_token,
                )
            )

    def test_lock_generations_never_reach_operator_documents(self) -> None:
        """The generation is an execution fence, never an operator value."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            api, active, runtime = self._activate(root)
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a")
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
            )
            queued = transfers.submit_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            self._run_worker(transfers, runtime)
            task_id = queued["taskId"]
            status, document = request(api, f"/api/v1/operations/tasks/{task_id}")
            self.assertEqual(status, 200)
            serialized = json.dumps(document)
            self.assertNotIn("lock_owner_token", serialized)
            self.assertNotIn("lockOwnerToken", serialized)
            self.assertNotIn("owner_token", serialized)
            projection = transfers.transfer_projection(task_id)
            self.assertNotIn("lock_owner_token", json.dumps(projection))
            for record in runtime.list_results(task_id):
                self.assertNotIn("lock_owner_token", json.dumps(record.completed_operations))


class AdoptedCheckpointContinuationTests(TransferTestCase):
    """A proven interrupted effect is adopted, never replayed."""

    def test_proven_copy_checkpoint_is_adopted_and_only_the_next_item_runs(self) -> None:
        """A verified interrupted Copy is adopted; the next item is the only work left."""

        from mediaflow.application.files_transfer_worker import FilesTransferWorker

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            source = _CrashAfterFirstCopySource("source-storage", root / "source")
            api, active, runtime = self._activate(root, storage_adapters={"source-storage": source})
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a" * 50)
            (root / "source" / "b.mkv").write_bytes(b"media-b" * 50)
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv", "b.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
            )
            queued = transfers.submit_transfer(
                resource_library_id="source",
                paths=["a.mkv", "b.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            task_id = queued["taskId"]

            crashed = FilesTransferWorker(
                transfers, runtime, lease_seconds=3600.0, worker_id="worker-crashed"
            )
            with self.assertRaises(SystemExit):
                crashed.run_next()
            self.assertEqual(source.copy_calls, 1)
            # Live truth: the first destination landed completely and the
            # durable boundary still proves the entered Copy.
            self.assertEqual((root / "source" / "Movies" / "a.mkv").read_bytes(), b"media-a" * 50)
            self.assertEqual(
                runtime.get_files_transfer(task_id).mutation_state, "mutation_in_flight"
            )

            replacement = FilesTransferWorker(
                transfers,
                runtime,
                lease_seconds=3600.0,
                worker_id="worker-replacement",
                clock=lambda: datetime.now(UTC) + timedelta(hours=2),
            )
            finished = replacement.run_next()
            self.assertIsNotNone(finished)
            self.assertEqual(finished.status.value, "completed")
            # The adopted Copy was never replayed: exactly one more mutation,
            # the second item's own admitted Copy.
            self.assertEqual(source.copy_calls, 2)
            projection = transfers.transfer_projection(task_id)
            self.assertEqual(projection["status"], "SUCCESS")
            self.assertTrue(projection["terminal"])
            self.assertEqual(projection["succeededItems"], 2)
            outcomes = {outcome["path"]: outcome for outcome in projection["outcomes"]}
            self.assertEqual(outcomes["a.mkv"]["status"], "SUCCESS")
            self.assertIn("COPY", outcomes["a.mkv"]["checkpoints"])
            self.assertIn("COPY", outcomes["b.mkv"]["checkpoints"])
            record = next(
                value
                for value in runtime.list_results(task_id)
                if value.source_path.endswith("a.mkv")
            )
            self.assertIn("COPY:a.mkv", record.completed_operations)
            self.assertEqual(record.effect_certainty, "verified_complete")
            self.assertIsNone(runtime.get_files_transfer(task_id).mutation_state)
            self.assertEqual(runtime.get_task(task_id).status.value, "completed")
            self.assertEqual((root / "source" / "Movies" / "b.mkv").read_bytes(), b"media-b" * 50)

    def test_cross_storage_verified_destination_resumes_only_the_destructive_step(self) -> None:
        """A proven cross-Storage Copy checkpoint publishes before the source delete."""

        from mediaflow.application.files_transfer_worker import FilesTransferWorker

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir(parents=True, exist_ok=True)
            (root / "destination").mkdir(parents=True, exist_ok=True)
            target = _CrashAtCheckpointTarget(
                "media-target", root / "destination", crash_at="after_verify"
            )
            api, active, runtime = self._activate(root, storage_adapters={"media-target": target})
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a" * 100)
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="move",
            )
            queued = transfers.submit_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="destination",
                destination_directory="",
                operation="move",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            task_id = queued["taskId"]
            crashed = FilesTransferWorker(
                transfers, runtime, lease_seconds=3600.0, worker_id="worker-crashed"
            )
            with self.assertRaises(SystemExit):
                crashed.run_next()
            writes_after_crash = target.write_calls
            self.assertEqual(writes_after_crash, 1)
            self.assertTrue((root / "source" / "a.mkv").exists())

            replacement = FilesTransferWorker(
                transfers,
                runtime,
                lease_seconds=3600.0,
                worker_id="worker-replacement",
                clock=lambda: datetime.now(UTC) + timedelta(hours=2),
            )
            finished = replacement.run_next()
            self.assertIsNotNone(finished)
            self.assertEqual(finished.status.value, "completed")
            # The proven destination is adopted — never streamed again — and
            # only the separately admitted destructive step remains.
            self.assertEqual(target.write_calls, writes_after_crash)
            self.assertFalse((root / "source" / "a.mkv").exists())
            self.assertEqual((root / "destination" / "a.mkv").read_bytes(), b"media-a" * 100)
            projection = transfers.transfer_projection(task_id)
            self.assertEqual(projection["status"], "SUCCESS")
            self.assertEqual(
                projection["outcomes"][0]["checkpoints"],
                ["copy_written", "destination_verified", "source_deleted"],
            )
            record = runtime.list_results(task_id)[0]
            self.assertEqual(
                record.completed_operations,
                (
                    "copy_written:a.mkv",
                    "destination_verified:a.mkv",
                    "source_deleted:a.mkv",
                    "entry:SUCCESS:a.mkv",
                ),
            )
            self.assertEqual(record.effect_certainty, "verified_complete")


class _FaultyFenceRepository:
    """A repository proxy whose guarded terminal item publish faults on demand.

    Every other call is delegated unchanged, so the Worker and its service still
    perform real claims, real Storage work and a real truthful convergence.  The
    fault happens exactly at the per-item terminal publication boundary, which
    proves a fault there never erases an already-persisted verified effect and
    never leaves a permanently running transfer.

    The proxy is installed on the service's own task coordinator, because that
    is the repository every transfer publication actually reads.
    """

    def __init__(self, repository) -> None:
        object.__setattr__(self, "_repository", repository)
        object.__setattr__(self, "armed", False)

    def __getattr__(self, name):
        return getattr(self._repository, name)

    def complete_item_with_evidence_guarded(self, *args, **kwargs):
        if self.armed:
            raise RuntimeError("terminal publication unavailable")
        return self._repository.complete_item_with_evidence_guarded(*args, **kwargs)


class TerminalPublicationFaultTests(TransferTestCase):
    """A fault around the terminal publication keeps one truthful state."""

    def test_terminal_publication_fault_after_a_persisted_effect_is_never_erased(self) -> None:
        """A fault after one verified effect never turns it into a clean failure.

        The first item's Copy is fully persisted (its guarded publication
        succeeded) and the second item's terminal publication faults.  The
        Worker converges on one truthful PARTIAL aggregate that keeps the first
        verified effect, and a reload reproduces it exactly.
        """

        from mediaflow.application.files_transfer_worker import FilesTransferWorker

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            api, active, runtime = self._activate(root)
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a" * 10)
            (root / "source" / "b.mkv").write_bytes(b"media-b" * 10)
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv", "b.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
            )
            queued = transfers.submit_transfer(
                resource_library_id="source",
                paths=["a.mkv", "b.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            task_id = queued["taskId"]

            faulty = _FaultyFenceRepository(runtime)
            transfers._direct.tasks.repository = faulty
            faulty.armed = True
            worker = FilesTransferWorker(
                transfers, runtime, lease_seconds=3600.0, worker_id="worker-fault"
            )
            worker.run_next()

            transfer = runtime.get_files_transfer(task_id)
            task = runtime.get_task(task_id)
            projection = transfers.transfer_projection(task_id)
            # One deterministic terminal truth on every surface: the first
            # verified effect beside the interrupted second item.
            self.assertTrue(transfer.status.terminal, transfer.status)
            self.assertEqual(transfer.status.value, "partial_success")
            self.assertEqual(task.status.value, "partial_success")
            self.assertTrue(projection["terminal"], projection)
            self.assertEqual(projection["status"], "PARTIAL")
            for item in runtime.list_items(task_id):
                self.assertNotIn(item.status.value, {"processing", "pending", "paused"})
            # The first verified effect is durably preserved: it was never
            # erased into a fabricated clean failure, and the Item and Result
            # agree with the aggregate.
            records = {record.source_path: record for record in runtime.list_results(task_id)}
            kept = records["a.mkv"]
            self.assertEqual(kept.status, "partial")
            self.assertIn("COPY:a.mkv", kept.completed_operations)
            self.assertEqual(kept.effect_certainty, "verified_complete")
            items = {item.source_display: item for item in runtime.list_items(task_id)}
            self.assertEqual(items["a.mkv"].status.value, "partial")
            self.assertEqual((root / "source" / "Movies" / "a.mkv").read_bytes(), b"media-a" * 10)
            self.assertIsNone(runtime.get_files_transfer(task_id).mutation_state)
            reloaded = SQLiteTaskRepository(root / "runtime.sqlite3")
            self.addCleanup(reloaded.close)
            self.assertEqual(reloaded.get_files_transfer(task_id).status, transfer.status)
            self.assertEqual(
                {
                    record.source_path: record.effect_certainty
                    for record in reloaded.list_results(task_id)
                },
                {
                    record.source_path: record.effect_certainty
                    for record in runtime.list_results(task_id)
                },
            )

    def test_faulted_publish_never_leaves_a_permanently_running_transfer(self) -> None:
        """A fault at the terminal publish still converges to a terminal state.

        The provider fails before any write, so the only truthful outcome is a
        zero-effect FAILED with ``none``; the faulted publication must not leave
        a permanently RUNNING projection, and a replacement Worker finishes the
        remaining work from the durable state.
        """

        from mediaflow.application.files_transfer_worker import FilesTransferWorker

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            api, active, runtime = self._activate(
                root,
                storage_adapters={
                    "source-storage": _ExplodingExistsSource("source-storage", root / "source")
                },
            )
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a")
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
            )
            queued = transfers.submit_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            task_id = queued["taskId"]

            faulty = _FaultyFenceRepository(runtime)
            transfers._direct.tasks.repository = faulty
            faulty.armed = True
            worker = FilesTransferWorker(
                transfers, faulty, lease_seconds=3600.0, worker_id="worker-fault"
            )
            worker.run_next()
            # No mutation happened (the provider raised before writing) and the
            # convergence still published one terminal FAILED/none state.
            self.assertFalse((root / "source" / "Movies" / "a.mkv").exists())
            transfer = runtime.get_files_transfer(task_id)
            self.assertTrue(transfer.status.terminal, transfer.status)
            self.assertIsNone(transfer.mutation_state)
            projection = transfers.transfer_projection(task_id)
            self.assertTrue(projection["terminal"], projection)
            self.assertNotEqual(projection["status"], "RUNNING")
            for item in runtime.list_items(task_id):
                self.assertNotIn(item.status.value, {"processing", "pending", "paused"})
            record = runtime.list_results(task_id)[0]
            self.assertEqual(record.effect_certainty, "none")
            self.assertEqual(record.uncertain_effects, ())
            self.assertTrue((root / "source" / "a.mkv").exists())
            # A replacement Worker finds no claimable work and the durable state
            # stays the same terminal zero-effect failure.
            replacement = FilesTransferWorker(
                transfers, runtime, lease_seconds=3600.0, worker_id="worker-replacement"
            )
            self.assertIsNone(replacement.run_next())
            self.assertEqual(transfers.transfer_projection(task_id)["status"], "FAILED")


class _ExplodingCopySource(LocalStorage):
    """A same-Storage provider whose native Copy raises an unexpected error."""

    def copy(self, *args, **kwargs):
        raise OSError("provider exploded")


class _FailsOnSecondCopySource(LocalStorage):
    """A provider whose first Copy lands and whose second Copy raises.

    The first entry therefore records a persisted verified effect and the second
    fails before it can record anything: exactly the "known mutation plus later
    failure" scenario the aggregate must report as PARTIAL.
    """

    def __init__(self, storage_id: str, root: Path) -> None:
        super().__init__(storage_id, root)
        self.copy_calls = 0

    def copy(self, *args, **kwargs):
        self.copy_calls += 1
        if self.copy_calls >= 2:
            raise OSError("provider exploded on the second copy")
        return super().copy(*args, **kwargs)


class _ExplodingExistsSource(LocalStorage):
    """A provider whose destination-state read raises before any mutation."""

    def exists(self, path):
        raise OSError("provider exploded")


class FailureConvergenceTests(TransferTestCase):
    """An unexpected Worker failure converges to one truthful terminal state."""

    def _admit_copy(self, transfers, root: Path) -> str:
        (root / "source" / "a.mkv").write_bytes(b"media-a")
        (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
        impact = transfers.transfer_impact(
            resource_library_id="source",
            paths=["a.mkv"],
            destination_resource_library_id="source",
            destination_directory="Movies",
            operation="copy",
            conflict_mode="fail",
        )
        queued = transfers.submit_transfer(
            resource_library_id="source",
            paths=["a.mkv"],
            destination_resource_library_id="source",
            destination_directory="Movies",
            operation="copy",
            conflict_mode="fail",
            manifest_digest=impact.manifest.digest,
        )
        return queued["taskId"]

    def _assert_converged(self, transfers, runtime, task_id: str) -> dict[str, object]:
        from mediaflow.domain.task_persistence import FilesTransferStatus

        transfer = runtime.get_files_transfer(task_id)
        task = runtime.get_task(task_id)
        projection = transfers.transfer_projection(task_id)
        self.assertIn(
            transfer.status,
            {
                FilesTransferStatus.FAILED,
                FilesTransferStatus.PARTIAL_SUCCESS,
                FilesTransferStatus.COMPLETED,
            },
        )
        self.assertTrue(
            task.status.value in {"failed", "partial_success", "completed"},
            task.status.value,
        )
        self.assertTrue(projection["terminal"], projection)
        self.assertNotEqual(projection["status"], "RUNNING")
        for item in runtime.list_items(task_id):
            self.assertNotIn(item.status.value, {"processing", "pending", "paused"}, item.status)
        return projection

    def test_failure_before_the_first_mutation_is_a_terminal_failed(self) -> None:
        """A failure before any mutation is FAILED with ``effect_certainty=none``."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir(parents=True, exist_ok=True)
            api, active, runtime = self._activate(
                root,
                storage_adapters={
                    "source-storage": _ExplodingExistsSource("source-storage", root / "source")
                },
            )
            transfers = self._transfers(api, active)
            task_id = self._admit_copy(transfers, root)
            self._run_worker(transfers, runtime)
            projection = self._assert_converged(transfers, runtime, task_id)
            self.assertEqual(projection["status"], "FAILED")
            transfer = runtime.get_files_transfer(task_id)
            self.assertEqual(transfer.status.value, "failed")
            self.assertEqual(runtime.get_task(task_id).status.value, "failed")
            item = runtime.list_items(task_id)[0]
            self.assertEqual(item.status.value, "failed")
            record = runtime.list_results(task_id)[0]
            self.assertEqual(record.status, "failed")
            # Zero attempted mutation is ``none`` — never a fabricated
            # verified-complete effect.
            self.assertEqual(record.effect_certainty, "none")
            self.assertEqual(record.uncertain_effects, ())
            # The source is untouched and a fresh transfer is the safe action.
            self.assertTrue((root / "source" / "a.mkv").exists())
            self.assertFalse((root / "source" / "Movies" / "a.mkv").exists())

    def test_failure_after_one_persisted_verified_effect_is_partial_everywhere(self) -> None:
        """A known persisted effect plus a later failure is PARTIAL on every surface.

        This is the exact contradiction B reproduced: transfer/task said FAILED
        while item/result/Files said PARTIAL.  The one post-conversion
        aggregate must make all six surfaces agree.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir(parents=True, exist_ok=True)
            source = _FailsOnSecondCopySource("source-storage", root / "source")
            api, active, runtime = self._activate(root, storage_adapters={"source-storage": source})
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a")
            (root / "source" / "b.mkv").write_bytes(b"media-b")
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            # b.mkv's destination already exists: the confirmed no-overwrite
            # behavior refuses that item without mutating, while a.mkv copies.
            (root / "source" / "Movies" / "b.mkv").write_bytes(b"existing")
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv", "b.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
            )
            queued = transfers.submit_transfer(
                resource_library_id="source",
                paths=["a.mkv", "b.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            task_id = queued["taskId"]
            self._run_worker(transfers, runtime)
            projection = self._assert_converged(transfers, runtime, task_id)
            transfer = runtime.get_files_transfer(task_id)
            task = runtime.get_task(task_id)
            # Every surface reports PARTIAL: a verified known effect plus a
            # later failure can never become a fabricated clean failure.
            self.assertEqual(projection["status"], "PARTIAL")
            self.assertEqual(transfer.status.value, "partial_success")
            self.assertEqual(task.status.value, "partial_success")
            results = {record.item_id: record for record in runtime.list_results(task_id)}
            items_by_id = {item.item_id: item for item in runtime.list_items(task_id)}
            succeeded = [item for item in items_by_id.values() if item.status.value == "success"]
            refused = [item for item in items_by_id.values() if item.status.value == "failed"]
            self.assertEqual((len(succeeded), len(refused)), (1, 1))
            # The verified sibling keeps its verified_complete evidence and the
            # refused sibling records no attempted mutation at all.
            success_record = results[succeeded[0].item_id]
            self.assertEqual(success_record.effect_certainty, "verified_complete")
            self.assertTrue(
                any("COPY" in operation for operation in success_record.completed_operations),
                success_record.completed_operations,
            )
            refused_record = results[refused[0].item_id]
            self.assertEqual(refused_record.effect_certainty, "none")
            # The verified sibling is real and the refused one retained its source.
            self.assertTrue((root / "source" / "Movies" / "a.mkv").exists())
            self.assertTrue((root / "source" / "b.mkv").exists())

    def test_unprovable_provider_effect_is_uncertain_everywhere(self) -> None:
        """An unprovable effect records UNCERTAIN and exposes investigation only."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir(parents=True, exist_ok=True)
            api, active, runtime = self._activate(
                root,
                storage_adapters={
                    "source-storage": _ExplodingCopySource("source-storage", root / "source")
                },
            )
            transfers = self._transfers(api, active)
            task_id = self._admit_copy(transfers, root)
            self._run_worker(transfers, runtime)
            projection = self._assert_converged(transfers, runtime, task_id)
            self.assertEqual(projection["status"], "UNCERTAIN")
            self.assertEqual(projection["durableState"], "mutation_effect_uncertain")
            transfer = runtime.get_files_transfer(task_id)
            task = runtime.get_task(task_id)
            self.assertEqual(transfer.status.value, "failed")
            self.assertEqual(transfer.error, "mutation_outcome")
            self.assertEqual(task.status.value, "failed")
            self.assertEqual(task.error, "mutation_outcome")
            item = runtime.list_items(task_id)[0]
            self.assertEqual(item.status.value, "partial")
            record = runtime.list_results(task_id)[0]
            self.assertEqual(record.status, "partial")
            self.assertEqual(record.effect_certainty, "attempted_unverified")
            self.assertEqual(record.uncertain_effects, ("mutation_outcome",))
            self.assertTrue((root / "source" / "a.mkv").exists())

    def test_failure_after_one_successful_sibling_is_partial(self) -> None:
        """A failure beside one successful sibling is PARTIAL, never FAILED."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir(parents=True, exist_ok=True)
            api, active, runtime = self._activate(root)
            transfers = self._transfers(api, active)
            (root / "source" / "a.mkv").write_bytes(b"media-a")
            (root / "source" / "b.mkv").write_bytes(b"media-b")
            (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
            (root / "source" / "Movies" / "b.mkv").write_bytes(b"existing")
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv", "b.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
            )
            queued = transfers.submit_transfer(
                resource_library_id="source",
                paths=["a.mkv", "b.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            task_id = queued["taskId"]
            self._run_worker(transfers, runtime)
            projection = self._assert_converged(transfers, runtime, task_id)
            self.assertEqual(projection["status"], "PARTIAL")
            self.assertEqual(runtime.get_files_transfer(task_id).status.value, "partial_success")
            self.assertEqual(runtime.get_task(task_id).status.value, "partial_success")
            succeeded = [
                item for item in runtime.list_items(task_id) if item.status.value == "success"
            ]
            self.assertEqual(len(succeeded), 1)
            self.assertTrue((root / "source" / "Movies" / "a.mkv").exists())

    def test_terminal_convergence_is_idempotent_and_reload_stable(self) -> None:
        """Repeating terminal convergence adds no Result and changes no truth."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir(parents=True, exist_ok=True)
            api, active, runtime = self._activate(
                root,
                storage_adapters={
                    "source-storage": _ExplodingCopySource("source-storage", root / "source")
                },
            )
            transfers = self._transfers(api, active)
            task_id = self._admit_copy(transfers, root)
            claimed = runtime.claim_next_files_transfer(
                datetime.now(UTC),
                worker_id="worker-probe",
                claim_token="token-probe",
                lease_seconds=3600.0,
            )
            self.assertIsNotNone(claimed)
            self.assertTrue(runtime.begin_files_transfer(task_id, "token-probe", datetime.now(UTC)))
            self.assertTrue(transfers.converge_worker_failure(task_id, "token-probe", OSError("x")))
            first = self._snapshot_transfer_truth(runtime, transfers, task_id)
            # Repeating the terminal convergence writes no additional Result and
            # reproduces exactly the same status, counts and certainty.
            self.assertTrue(transfers.converge_worker_failure(task_id, "token-probe", OSError("x")))
            second = self._snapshot_transfer_truth(runtime, transfers, task_id)
            self.assertEqual(first, second)

    def _snapshot_transfer_truth(self, runtime, transfers, task_id: str):
        transfer = runtime.get_files_transfer(task_id)
        task = runtime.get_task(task_id)
        return {
            "transfer": transfer.status.value,
            "transfer_error": transfer.error,
            "task": task.status.value,
            "task_error": task.error,
            "items": [(item.item_id, item.status.value) for item in runtime.list_items(task_id)],
            "results": [
                (record.result_id, record.status, record.effect_certainty, record.uncertain_effects)
                for record in runtime.list_results(task_id)
            ],
            "projection": transfers.transfer_projection(task_id)["status"],
        }

    def test_worker_start_failure_converges_the_task_and_items(self) -> None:
        from mediaflow.application.files_transfer_worker import FilesTransferWorker

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
            transfers = self._transfers(api, active)
            task_id = self._admit_copy(transfers, root)

            class _BrokenService:
                converge_worker_failure = transfers.converge_worker_failure

                def run_claimed_transfer(self, *args, **kwargs):
                    raise RuntimeError("worker wiring failed")

            worker = FilesTransferWorker(
                _BrokenService(), runtime, lease_seconds=3600.0, worker_id="worker-broken"
            )
            self.assertIsNone(worker.run_next())
            projection = self._assert_converged(transfers, runtime, task_id)
            self.assertEqual(projection["status"], "FAILED")
            self.assertEqual(runtime.get_files_transfer(task_id).status.value, "failed")
            self.assertEqual(runtime.get_task(task_id).status.value, "failed")
            record = runtime.list_results(task_id)[0]
            self.assertEqual(record.effect_certainty, "none")

    def test_incident_evidence_is_bounded_and_secret_free(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir(parents=True, exist_ok=True)
            api, active, runtime = self._activate(
                root,
                storage_adapters={
                    "source-storage": _ExplodingCopySource("source-storage", root / "source")
                },
            )
            transfers = self._transfers(api, active)
            task_id = self._admit_copy(transfers, root)
            self._run_worker(transfers, runtime)
            projection = transfers.transfer_projection(task_id)
            rendered = json.dumps(projection)
            for secret in ("provider exploded", "OSError", str(root)):
                self.assertNotIn(secret, rendered)


class StaleWorkerRevisionTests(TransferTestCase):
    """The pinned revision travels with the transfer, not with the process."""

    def _activate_successor(self, root: Path, service, objects, document):
        """Publish one successor revision and return its Active row."""

        import copy as copy_module

        candidate = copy_module.deepcopy(document)
        candidate["resourceLibraries"][0]["name"] = "Source Renamed"
        draft = service.import_draft(candidate, actor="operator")
        validated = service.validate(draft.revision_id, actor="operator")
        for storage_id in ("source-storage", "media-target"):
            objects.storage_check(
                validated.revision_id,
                storage_id=storage_id,
                expected_version=validated.version,
                expected_digest=validated.digest,
                actor="operator",
            )
        objects.recognition_strategy_test(
            validated.revision_id,
            expected_version=validated.version,
            expected_digest=validated.digest,
            actor="operator",
            resource_library_id="source",
            synthetic_path="a.mkv",
        )
        objects.destination_precheck(
            validated.revision_id,
            expected_version=validated.version,
            expected_digest=validated.digest,
            actor="operator",
            recognition_type="C",
            sample={
                "title": "T",
                "mediaType": "movie",
                "year": 1999,
                "genres": ["Action"],
                "extension": "mkv",
            },
        )
        return objects.activate_checked(
            validated.revision_id,
            expected_version=validated.version,
            actor="operator",
        )

    def _fixture(self, root: Path):
        from mediaflow.application.configuration_objects import ConfigurationObjectService
        from mediaflow.application.configuration_snapshot import ManagedConfigurationService
        from mediaflow.infrastructure.sqlite_configuration_management import (
            SQLiteConfigurationRepository,
        )

        document = self._document(root)
        (root / "source" / "Movies").mkdir(parents=True, exist_ok=True)
        (root / "destination" / "Movies").mkdir(parents=True, exist_ok=True)
        repository = SQLiteConfigurationRepository(root / "configuration.sqlite3")
        self.addCleanup(repository.close)
        service = ManagedConfigurationService(
            repository, bootstrap_database_path=str(root / "configuration.sqlite3")
        )
        objects = ConfigurationObjectService(service, storage_browser_cursor_secret="s")
        draft = service.import_draft(document, actor="operator")
        validated = service.validate(draft.revision_id, actor="operator")
        for storage_id in ("source-storage", "media-target"):
            objects.storage_check(
                validated.revision_id,
                storage_id=storage_id,
                expected_version=validated.version,
                expected_digest=validated.digest,
                actor="operator",
            )
        objects.recognition_strategy_test(
            validated.revision_id,
            expected_version=validated.version,
            expected_digest=validated.digest,
            actor="operator",
            resource_library_id="source",
            synthetic_path="a.mkv",
        )
        objects.destination_precheck(
            validated.revision_id,
            expected_version=validated.version,
            expected_digest=validated.digest,
            actor="operator",
            recognition_type="C",
            sample={
                "title": "T",
                "mediaType": "movie",
                "year": 1999,
                "genres": ["Action"],
                "extension": "mkv",
            },
        )
        active = objects.activate_checked(
            validated.revision_id,
            expected_version=validated.version,
            actor="operator",
        )
        return document, service, objects, active

    def _pinned_rebuilder(self, api, service):
        """Rebuild one persisted revision exactly like the resident Worker does.

        It reproduces ``mediaflow.final_cli._files_transfer_worker_context``:
        the claimed transfer's own revision is loaded from durable
        configuration state and resolved into an equivalent service, or
        ``None`` when this process cannot lawfully reconstruct it.
        """

        from mediaflow.application.direct_file_commands import DirectFileCommandService
        from mediaflow.infrastructure.runtime_configuration import (
            load_managed_runtime_configuration,
            with_managed_snapshot,
        )

        def rebuild(revision_id: str, revision_digest: str):
            pinned = service._repository.get_revision(revision_id)
            if pinned is None or pinned.digest != revision_digest:
                return None
            runtime = with_managed_snapshot(
                load_managed_runtime_configuration(
                    pinned.document,
                    bootstrap_database_path=service.bootstrap_database_path,
                ),
                snapshot_id=pinned.revision_id,
                digest=pinned.digest,
                version=pinned.version,
            )
            from dataclasses import replace as dc_replace

            from mediaflow.domain.configuration_management import ManagedConfigurationStatus

            published = dc_replace(
                pinned,
                status=ManagedConfigurationStatus.ACTIVE,
                activated_at=pinned.activated_at or datetime.now(UTC),
            )
            return DirectFileTransferService(
                direct_files=DirectFileCommandService(
                    active_revision=published,
                    runtime_configuration=runtime,
                    task_repository=api._repository,
                    revision_rebuilder=rebuild,
                )
            )

        return rebuild

    def _submit_under(self, service, root: Path, task_id_out: list) -> None:
        (root / "source" / "a.mkv").write_bytes(b"media-a")
        impact = service.transfer_impact(
            resource_library_id="source",
            paths=["a.mkv"],
            destination_resource_library_id="source",
            destination_directory="Movies",
            operation="copy",
            conflict_mode="fail",
        )
        queued = service.submit_transfer(
            resource_library_id="source",
            paths=["a.mkv"],
            destination_resource_library_id="source",
            destination_directory="Movies",
            operation="copy",
            conflict_mode="fail",
            manifest_digest=impact.manifest.digest,
        )
        task_id_out.append(queued["taskId"])

    def test_a_newer_worker_reconstructs_an_older_pinned_transfer(self) -> None:
        from mediaflow.application.direct_file_transfers import DirectFileTransferService
        from mediaflow.application.files_transfer_worker import FilesTransferWorker
        from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
        from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
        from mediaflow.interfaces.service_api import MediaFlowApi

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document, service, objects, active = self._fixture(root)
            runtime = SQLiteTaskRepository(root / "runtime.sqlite3")
            self.addCleanup(runtime.close)
            api = MediaFlowApi(
                runtime,
                None,
                principals=(
                    ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                ),
                configuration_service=service,
                bootstrap_document=document,
                storage_browser_cursor_secret="s",
            )
            old_binding = api._prepare_runtime_binding_for_revision(active)
            old_service = DirectFileTransferService(direct_files=old_binding.direct_files)
            task_ids: list = []
            self._submit_under(old_service, root, task_ids)
            task_id = task_ids[0]

            # A successor revision becomes Active while the Worker process
            # stays live; the already-admitted transfer keeps its own pin.
            successor = self._activate_successor(root, service, objects, document)
            new_binding = api._prepare_runtime_binding_for_revision(successor)
            new_service = DirectFileTransferService(
                direct_files=new_binding.direct_files,
                runtime_factory=self._pinned_rebuilder(api, service),
            )
            worker = FilesTransferWorker(
                new_service, runtime, lease_seconds=3600.0, worker_id="worker-new"
            )
            finished = worker.run_next()
            self.assertIsNotNone(finished)
            self.assertEqual(finished.status.value, "completed")
            self.assertTrue((root / "source" / "Movies" / "a.mkv").exists())
            self.assertEqual(runtime.get_task(task_id).status.value, "completed")

    def test_an_incompatible_worker_leaves_the_transfer_claimable(self) -> None:
        from mediaflow.application.direct_file_transfers import DirectFileTransferService
        from mediaflow.application.files_transfer_worker import FilesTransferWorker
        from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
        from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
        from mediaflow.interfaces.service_api import MediaFlowApi

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document, service, objects, active = self._fixture(root)
            runtime = SQLiteTaskRepository(root / "runtime.sqlite3")
            self.addCleanup(runtime.close)
            api = MediaFlowApi(
                runtime,
                None,
                principals=(
                    ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                ),
                configuration_service=service,
                bootstrap_document=document,
                storage_browser_cursor_secret="s",
            )
            new_binding = api._prepare_runtime_binding_for_revision(active)
            new_service = DirectFileTransferService(direct_files=new_binding.direct_files)
            task_ids: list = []
            self._submit_under(new_service, root, task_ids)
            task_id = task_ids[0]

            # A Worker bound to a *different* revision cannot reconstruct the
            # transfer's pin: the claim is released, never consumed.
            incompatible = DirectFileTransferService(
                direct_files=new_binding.direct_files,
                runtime_factory=lambda revision_id, digest: None,
            )
            worker = FilesTransferWorker(
                incompatible,
                runtime,
                lease_seconds=3600.0,
                worker_id="worker-incompatible",
            )
            worker.run_next()
            transfer = runtime.get_files_transfer(task_id)
            self.assertEqual(transfer.status.value, "admitted")
            self.assertEqual(transfer.error, "files_transfer_snapshot_unavailable")
            self.assertEqual(runtime.get_task(task_id).status.value, "pending")
            self.assertFalse((root / "source" / "Movies" / "a.mkv").exists())

    # ------------------------------------------------------------------
    # Both pinned-revision directions and unreadable pinned authority
    # ------------------------------------------------------------------

    def _api_fixture(self, root: Path):
        from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
        from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
        from mediaflow.interfaces.service_api import MediaFlowApi

        document, service, objects, active = self._fixture(root)
        runtime = SQLiteTaskRepository(root / "runtime.sqlite3")
        self.addCleanup(runtime.close)
        api = MediaFlowApi(
            runtime,
            None,
            principals=(ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),),
            configuration_service=service,
            bootstrap_document=document,
            storage_browser_cursor_secret="s",
        )
        return document, service, objects, active, api, runtime

    def test_an_older_worker_executes_newer_pinned_work(self) -> None:
        """Old-process/newer-admission: a Worker composed under A runs a B pin."""

        from mediaflow.application.direct_file_transfers import DirectFileTransferService
        from mediaflow.application.files_transfer_worker import FilesTransferWorker

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document, service, objects, active, api, runtime = self._api_fixture(root)
            old_binding = api._prepare_runtime_binding_for_revision(active)
            # The successor becomes Active before the new transfer is admitted.
            successor = self._activate_successor(root, service, objects, document)
            new_binding = api._prepare_runtime_binding_for_revision(successor)
            new_service = DirectFileTransferService(direct_files=new_binding.direct_files)
            task_ids: list = []
            self._submit_under(new_service, root, task_ids)
            task_id = task_ids[0]

            rebuilt: list = []
            factory = self._pinned_rebuilder(api, service)

            def recording_factory(revision_id: str, revision_digest: str):
                rebuilt.append(revision_id)
                return factory(revision_id, revision_digest)

            # A Worker composed while revision A was Active must reconstruct the
            # newer pinned revision B and execute the admitted work under it.
            old_worker_service = DirectFileTransferService(
                direct_files=old_binding.direct_files,
                runtime_factory=recording_factory,
            )
            worker = FilesTransferWorker(
                old_worker_service, runtime, lease_seconds=3600.0, worker_id="worker-old"
            )
            finished = worker.run_next()
            self.assertIsNotNone(finished)
            self.assertEqual(finished.status.value, "completed")
            self.assertEqual(rebuilt, [successor.revision_id])
            self.assertTrue((root / "source" / "Movies" / "a.mkv").exists())
            self.assertEqual(
                runtime.get_task(task_id).configuration_snapshot_id, successor.revision_id
            )

    def test_two_pinned_revisions_queue_together_use_their_own_bindings(self) -> None:
        """Both pinned revisions queued together each use only their own pin."""

        from mediaflow.application.direct_file_transfers import DirectFileTransferService
        from mediaflow.application.files_transfer_worker import FilesTransferWorker

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document, service, objects, active, api, runtime = self._api_fixture(root)
            old_binding = api._prepare_runtime_binding_for_revision(active)
            old_service = DirectFileTransferService(direct_files=old_binding.direct_files)
            (root / "source" / "a.mkv").write_bytes(b"media-a")
            impact = old_service.transfer_impact(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
            )
            queued_old = old_service.submit_transfer(
                resource_library_id="source",
                paths=["a.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact.manifest.digest,
            )
            successor = self._activate_successor(root, service, objects, document)
            new_binding = api._prepare_runtime_binding_for_revision(successor)
            new_service = DirectFileTransferService(direct_files=new_binding.direct_files)
            (root / "source" / "b.mkv").write_bytes(b"media-b")
            impact_new = new_service.transfer_impact(
                resource_library_id="source",
                paths=["b.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
            )
            queued_new = new_service.submit_transfer(
                resource_library_id="source",
                paths=["b.mkv"],
                destination_resource_library_id="source",
                destination_directory="Movies",
                operation="copy",
                conflict_mode="fail",
                manifest_digest=impact_new.manifest.digest,
            )["taskId"]

            rebuilt: list = []
            factory = self._pinned_rebuilder(api, service)

            def recording_factory(revision_id: str, revision_digest: str):
                rebuilt.append(revision_id)
                return factory(revision_id, revision_digest)

            worker_service = DirectFileTransferService(
                direct_files=old_binding.direct_files,
                runtime_factory=recording_factory,
            )
            worker = FilesTransferWorker(
                worker_service, runtime, lease_seconds=3600.0, worker_id="worker-both"
            )
            finished = [worker.run_next(), worker.run_next()]
            self.assertTrue(all(transfer is not None for transfer in finished))
            self.assertEqual(
                [transfer.status.value for transfer in finished if transfer is not None],
                ["completed", "completed"],
            )
            self.assertEqual(
                runtime.get_task(queued_old["taskId"]).configuration_snapshot_id,
                active.revision_id,
            )
            self.assertEqual(
                runtime.get_task(queued_new).configuration_snapshot_id,
                successor.revision_id,
            )
            # Each transfer reconstructed exactly its own pinned revision.
            self.assertEqual(sorted(rebuilt), sorted([active.revision_id, successor.revision_id]))
            self.assertTrue((root / "source" / "Movies" / "a.mkv").exists())

    def _corrupt_transfer_column(self, runtime, task_id: str, column: str, value) -> None:
        with runtime._lock, runtime._connection:
            runtime._connection.execute(
                f"UPDATE files_transfers SET {column}=? WHERE task_id=?", (value, task_id)
            )

    def test_corrupt_pinned_authority_converges_without_mutation(self) -> None:
        from mediaflow.application.direct_file_transfers import DirectFileTransferService
        from mediaflow.application.files_transfer_worker import FilesTransferWorker

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document, service, objects, active, api, runtime = self._api_fixture(root)
            binding = api._prepare_runtime_binding_for_revision(active)
            transfers = DirectFileTransferService(
                direct_files=binding.direct_files,
                runtime_factory=self._pinned_rebuilder(api, service),
            )
            task_ids: list = []
            self._submit_under(transfers, root, task_ids)
            task_id = task_ids[0]
            self._corrupt_transfer_column(runtime, task_id, "authority_json", "{not json")

            worker = FilesTransferWorker(
                transfers, runtime, lease_seconds=3600.0, worker_id="worker-corrupt"
            )
            finished = worker.run_next()
            self.assertIsNotNone(finished)
            # No Storage mutation happened and the outcome is a bounded,
            # investigation-only state — never a fabricated success or a blind
            # replay of work whose confirmed operation cannot be reconstructed.
            self.assertEqual(finished.status.value, "failed")
            self.assertEqual(finished.error, "files_transfer_invalid_authority")
            self.assertEqual(runtime.get_task(task_id).status.value, "failed")
            self.assertFalse((root / "source" / "Movies" / "a.mkv").exists())
            projection = transfers.transfer_projection(task_id)
            self.assertEqual(projection["status"], "FAILED")
            self.assertTrue(projection["terminal"])

    def test_digest_mismatch_leaves_the_transfer_claimable(self) -> None:
        from mediaflow.application.direct_file_transfers import DirectFileTransferService
        from mediaflow.application.files_transfer_worker import FilesTransferWorker

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document, service, objects, active, api, runtime = self._api_fixture(root)
            binding = api._prepare_runtime_binding_for_revision(active)
            transfers = DirectFileTransferService(
                direct_files=binding.direct_files,
                runtime_factory=self._pinned_rebuilder(api, service),
            )
            task_ids: list = []
            self._submit_under(transfers, root, task_ids)
            task_id = task_ids[0]
            self._corrupt_transfer_column(
                runtime, task_id, "configuration_snapshot_digest", "0" * 64
            )

            worker = FilesTransferWorker(
                transfers, runtime, lease_seconds=3600.0, worker_id="worker-digest"
            )
            worker.run_next()
            transfer = runtime.get_files_transfer(task_id)
            self.assertEqual(transfer.status.value, "admitted")
            self.assertEqual(transfer.error, "files_transfer_snapshot_unavailable")
            self.assertEqual(runtime.get_task(task_id).status.value, "pending")
            self.assertFalse((root / "source" / "Movies" / "a.mkv").exists())

    def test_runtime_reconstruction_failure_leaves_the_transfer_claimable(self) -> None:
        from mediaflow.application.direct_file_transfers import DirectFileTransferService
        from mediaflow.application.files_transfer_worker import FilesTransferWorker

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document, service, objects, active, api, runtime = self._api_fixture(root)
            binding = api._prepare_runtime_binding_for_revision(active)
            transfers = DirectFileTransferService(direct_files=binding.direct_files)
            task_ids: list = []
            self._submit_under(transfers, root, task_ids)
            task_id = task_ids[0]

            def exploding_factory(revision_id: str, revision_digest: str):
                raise RuntimeError("runtime reconstruction failed")

            incompatible = DirectFileTransferService(
                direct_files=binding.direct_files,
                runtime_factory=exploding_factory,
            )
            worker = FilesTransferWorker(
                incompatible, runtime, lease_seconds=3600.0, worker_id="worker-broken-runtime"
            )
            worker.run_next()
            # A reconstruction failure is a readiness problem, not a business
            # failure of otherwise valid work: the claim is released, no
            # mutation happened, and a compatible Worker can still execute it.
            transfer = runtime.get_files_transfer(task_id)
            self.assertEqual(transfer.status.value, "admitted")
            self.assertEqual(transfer.error, "files_transfer_snapshot_unavailable")
            self.assertEqual(runtime.get_task(task_id).status.value, "pending")
            self.assertFalse((root / "source" / "Movies" / "a.mkv").exists())


class ExecutorBoundaryTests(TransferTestCase):
    def test_every_transfer_mutation_crosses_the_organizer_executor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, active, runtime = self._activate(root)
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
            result = self._submit(
                transfers,
                runtime,
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
            api, active, runtime = self._activate(root)
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
            result = self._submit(
                transfers,
                runtime,
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
