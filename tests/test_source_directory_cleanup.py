from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.domain.organizer import (
    AttachmentPlan,
    AttachmentType,
    DirectoryCleanupMode,
    DirectoryCleanupPolicy,
    DirectoryCleanupStatus,
    ExecutionStatus,
    OrganizePlan,
    PlanOperation,
    PlanStatus,
    StorageLocation,
)
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.openlist_storage import (
    OpenListClientEntry,
    OpenListClientError,
    OpenListClientErrorKind,
    OpenListPage,
    OpenListStorage,
    OpenListStorageConfig,
)
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.s3_storage import (
    S3ClientError,
    S3ClientErrorKind,
    S3ClientObject,
    S3ListPage,
    S3Provider,
    S3Storage,
    S3StorageConfig,
)

NOW = datetime(2026, 9, 1, tzinfo=UTC)


def example_document() -> dict:
    return json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))


def plan(
    source: str = "source/movie/Movie.mkv",
    target: str = "target/Movie/Movie.mkv",
    *,
    operation: PlanOperation = PlanOperation.MOVE,
    cleanup: DirectoryCleanupPolicy = DirectoryCleanupPolicy(),
    root: str = "source",
) -> OrganizePlan:
    return OrganizePlan(
        "local",
        "local",
        source,
        target,
        "A",
        "A",
        "A",
        "A",
        operation=operation,
        status=PlanStatus.READY,
        plan_id="cleanup-plan",
        media_library_root="target",
        relative_destination=target.removeprefix("target/"),
        source_location=StorageLocation("local", source),
        destination_location=StorageLocation("local", target),
        source_library_root=root,
        source_directory_cleanup=cleanup,
    )


class SourceDirectoryCleanupTests(unittest.TestCase):
    def test_configuration_default_external_values_and_validation(self) -> None:
        loaded = load_runtime_configuration(example_document())
        self.assertEqual(
            loaded.strategy.organize_policies[0].source_directory_cleanup.mode,
            DirectoryCleanupMode.NONE,
        )
        document = example_document()
        document["organizePolicies"][0]["sourceDirectoryCleanup"] = {
            "mode": "ignorable",
            "maxParentDirectories": 2,
            "ignorePatterns": [".DS_Store", "Thumbs.db"],
            "maxEntries": 20,
        }
        configured = load_runtime_configuration(document).strategy.organize_policies[0]
        self.assertEqual(configured.source_directory_cleanup.max_parent_directories, 2)
        self.assertEqual(
            configured.source_directory_cleanup.ignore_patterns, (".DS_Store", "Thumbs.db")
        )
        invalid_values = (
            {"mode": "delete-all"},
            {"mode": "empty", "ignorePatterns": [".DS_Store"]},
            {"mode": "ignorable", "ignorePatterns": []},
            {"mode": "ignorable", "ignorePatterns": ["*"]},
            {"mode": "ignorable", "ignorePatterns": ["../x"]},
            {"mode": "empty", "maxParentDirectories": 11},
            {"mode": "empty", "maxEntries": True},
            {"unknown": 1},
        )
        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                invalid = copy.deepcopy(document)
                invalid["organizePolicies"][0]["sourceDirectoryCleanup"] = value
                load_runtime_configuration(invalid)
        for root in ("../outside", "inside/../outside", "/absolute", "inside//nested"):
            with (
                self.subTest(root=root),
                self.assertRaisesRegex(ValueError, "safe Storage-relative"),
            ):
                invalid_root = example_document()
                invalid_root["resourceLibraries"][0]["storagePath"] = root
                load_runtime_configuration(invalid_root)

    def test_empty_cleanup_is_bounded_and_preserves_library_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "source/parent/child/Movie.mkv")
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")
            storage = LocalStorage("local", directory)
            result = OrganizerExecutor().execute(
                plan(
                    "source/parent/child/Movie.mkv",
                    cleanup=DirectoryCleanupPolicy(
                        DirectoryCleanupMode.EMPTY, max_parent_directories=5
                    ),
                ),
                {"local": storage},
                execute=True,
            )
            self.assertEqual(result.status, ExecutionStatus.SUCCESS)
            self.assertEqual(result.cleanup_status, DirectoryCleanupStatus.SUCCESS)
            self.assertFalse(Path(directory, "source/parent/child").exists())
            self.assertFalse(Path(directory, "source/parent").exists())
            self.assertTrue(Path(directory, "source").is_dir())
            self.assertEqual(
                [step.path for step in result.cleanup_steps],
                ["source/parent/child", "source/parent"],
            )

    def test_direct_library_root_file_is_never_cleaned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "source/Movie.mkv")
            source.parent.mkdir()
            source.write_bytes(b"media")
            result = OrganizerExecutor().execute(
                plan(
                    "source/Movie.mkv",
                    cleanup=DirectoryCleanupPolicy(DirectoryCleanupMode.EMPTY),
                ),
                {"local": LocalStorage("local", directory)},
                execute=True,
            )
            self.assertEqual(result.cleanup_status, DirectoryCleanupStatus.NOT_APPLICABLE)
            self.assertTrue(Path(directory, "source").is_dir())

    def test_ignorable_files_are_explicit_and_unknown_content_stops_before_delete(self) -> None:
        for unknown in (False, True):
            with self.subTest(unknown=unknown), tempfile.TemporaryDirectory() as directory:
                source = Path(directory, "source/movie/Movie.mkv")
                source.parent.mkdir(parents=True)
                source.write_bytes(b"media")
                Path(source.parent, ".DS_Store").write_bytes(b"ignored")
                if unknown:
                    Path(source.parent, "keep.txt").write_bytes(b"keep")
                result = OrganizerExecutor().execute(
                    plan(
                        cleanup=DirectoryCleanupPolicy(
                            DirectoryCleanupMode.IGNORABLE,
                            ignore_patterns=(".DS_Store",),
                        )
                    ),
                    {"local": LocalStorage("local", directory)},
                    execute=True,
                )
                self.assertEqual(result.status, ExecutionStatus.SUCCESS)
                expected = (
                    DirectoryCleanupStatus.STOPPED if unknown else DirectoryCleanupStatus.SUCCESS
                )
                self.assertEqual(result.cleanup_status, expected)
                self.assertEqual(Path(source.parent, ".DS_Store").exists(), unknown)
                if unknown:
                    self.assertTrue(Path(source.parent, "keep.txt").exists())
                    self.assertFalse(
                        any(step.action == "DELETE_IGNORED_FILE" for step in result.cleanup_steps)
                    )

    def test_copy_and_dryrun_never_cleanup(self) -> None:
        for operation, execute in ((PlanOperation.COPY, True), (PlanOperation.MOVE, False)):
            with (
                self.subTest(operation=operation, execute=execute),
                tempfile.TemporaryDirectory() as directory,
            ):
                source = Path(directory, "source/movie/Movie.mkv")
                source.parent.mkdir(parents=True)
                source.write_bytes(b"media")
                result = OrganizerExecutor().execute(
                    plan(
                        operation=operation,
                        cleanup=DirectoryCleanupPolicy(DirectoryCleanupMode.EMPTY),
                    ),
                    {"local": LocalStorage("local", directory)},
                    execute=execute,
                )
                self.assertTrue(source.exists())
                self.assertTrue(source.parent.exists())
                self.assertEqual(result.cleanup_steps, ())

    def test_symlink_or_subdirectory_prevents_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "source/movie/Movie.mkv")
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")
            Path(source.parent, "unknown").mkdir()
            result = OrganizerExecutor().execute(
                plan(
                    cleanup=DirectoryCleanupPolicy(
                        DirectoryCleanupMode.IGNORABLE, ignore_patterns=("unknown",)
                    )
                ),
                {"local": LocalStorage("local", directory)},
                execute=True,
            )
            self.assertEqual(result.cleanup_status, DirectoryCleanupStatus.STOPPED)
            self.assertTrue(Path(source.parent, "unknown").is_dir())

    def test_invalid_boundary_fails_closed_after_verified_move(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "outside/movie/Movie.mkv")
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")
            unsafe = replace(
                plan(
                    "outside/movie/Movie.mkv",
                    cleanup=DirectoryCleanupPolicy(DirectoryCleanupMode.EMPTY),
                ),
                source_library_root="source",
            )
            result = OrganizerExecutor().execute(
                unsafe, {"local": LocalStorage("local", directory)}, execute=True
            )
            self.assertEqual(result.status, ExecutionStatus.PARTIAL)
            self.assertEqual(result.cleanup_status, DirectoryCleanupStatus.FAILED)
            self.assertTrue(Path(directory, "outside/movie").is_dir())
            self.assertFalse(source.exists())

    def test_attachment_move_can_leave_source_directory_empty_for_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "source/movie/Movie.mkv")
            subtitle = Path(directory, "source/movie/Movie.zh.srt")
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")
            subtitle.write_bytes(b"subtitle")
            value = replace(
                plan(cleanup=DirectoryCleanupPolicy(DirectoryCleanupMode.EMPTY)),
                attachment_plans=(
                    AttachmentPlan(
                        StorageLocation("local", "source/movie/Movie.zh.srt"),
                        StorageLocation("local", "target/Movie/Movie.zh.srt"),
                        AttachmentType.SUBTITLE,
                        PlanOperation.MOVE,
                    ),
                ),
            )
            result = OrganizerExecutor().execute(
                value, {"local": LocalStorage("local", directory)}, execute=True
            )
            self.assertEqual(result.status, ExecutionStatus.SUCCESS)
            self.assertEqual(result.cleanup_status, DirectoryCleanupStatus.SUCCESS)
            self.assertFalse(source.parent.exists())
            self.assertTrue(Path(directory, "target/Movie/Movie.zh.srt").exists())

    def test_directory_change_between_checks_fails_without_recursive_delete(self) -> None:
        class RacingStorage(LocalStorage):
            def __init__(self, root: str) -> None:
                super().__init__("local", root)
                self.root = Path(root)
                self.cleanup_lists = 0

            def list(self, path: str):
                if path == "source/movie":
                    self.cleanup_lists += 1
                    if self.cleanup_lists == 2:
                        Path(self.root, path, "appeared.txt").write_bytes(b"unknown")
                return super().list(path)

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "source/movie/Movie.mkv")
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")
            result = OrganizerExecutor().execute(
                plan(cleanup=DirectoryCleanupPolicy(DirectoryCleanupMode.EMPTY)),
                {"local": RacingStorage(directory)},
                execute=True,
            )
            self.assertEqual(result.status, ExecutionStatus.PARTIAL)
            self.assertEqual(result.cleanup_status, DirectoryCleanupStatus.FAILED)
            self.assertTrue(Path(source.parent, "appeared.txt").exists())


class _FakeOpenListClient:
    """An OpenList double reproducing the real server-side file semantics.

    Entries are a flat path map.  Delete refuses a non-empty directory, so an
    emptied directory is only removed after the provider itself confirms it is
    empty.  No entry publishes an identity fingerprint, matching the real
    adapter: the cleanup must therefore stay a policy-scoped name predicate and
    must never require or fake exact-entry identity.
    """

    def __init__(self) -> None:
        self.entries: dict[str, OpenListClientEntry] = {}
        self.deleted: list[str] = []

    @staticmethod
    def entry(name: str, *, directory: bool = False, size: int = 0) -> OpenListClientEntry:
        return OpenListClientEntry(name, name, directory, size, NOW)

    def list_page(self, path: str, page: int, per_page: int) -> OpenListPage:
        prefix = path.rstrip("/") + "/"
        children = [
            value
            for key, value in sorted(self.entries.items())
            if key.startswith(prefix) and "/" not in key[len(prefix) :]
        ]
        start = (page - 1) * per_page
        return OpenListPage(children[start : start + per_page], len(children))

    def stat(self, path: str) -> OpenListClientEntry:
        try:
            return self.entries[path]
        except KeyError as error:
            raise OpenListClientError(OpenListClientErrorKind.NOT_FOUND) from error

    def create_directory(self, path: str) -> None:
        if path in self.entries:
            raise OpenListClientError(OpenListClientErrorKind.ALREADY_EXISTS)
        name = path.rstrip("/").rsplit("/", 1)[-1]
        self.entries[path] = self.entry(name, directory=True)

    def move(self, source: str, target: str, *, overwrite: bool) -> None:
        if source not in self.entries:
            raise OpenListClientError(OpenListClientErrorKind.NOT_FOUND)
        if target in self.entries and not overwrite:
            raise OpenListClientError(OpenListClientErrorKind.ALREADY_EXISTS)
        self.entries[target] = self.entries.pop(source)

    def copy(self, source: str, target: str, *, overwrite: bool) -> None:
        if source not in self.entries:
            raise OpenListClientError(OpenListClientErrorKind.NOT_FOUND)
        if target in self.entries and not overwrite:
            raise OpenListClientError(OpenListClientErrorKind.ALREADY_EXISTS)
        self.entries[target] = self.entries[source]

    def delete(self, path: str) -> None:
        if path not in self.entries:
            raise OpenListClientError(OpenListClientErrorKind.NOT_FOUND)
        self.deleted.append(path)
        del self.entries[path]


class _FakeS3Client:
    """A minimal object-store double with real object-validator semantics."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.delete_calls: list[str] = []
        self.uploads: dict[str, list[bytes]] = {}

    def list_objects(self, prefix: str, *, delimiter: str, token, max_keys: int):
        names: list[tuple[str, str]] = []
        for key in sorted(self.objects):
            if not key.startswith(prefix):
                continue
            remainder = key[len(prefix) :]
            if delimiter in remainder:
                names.append(("prefix", prefix + remainder.split(delimiter, 1)[0] + delimiter))
            else:
                names.append(("object", key))
        names = list(dict.fromkeys(names))
        objects = tuple(
            S3ClientObject(key, len(self.objects[key]), NOW, f"etag-{key}")
            for kind, key in names
            if kind == "object"
        )
        prefixes = tuple(key for kind, key in names if kind == "prefix")
        return S3ListPage(objects, prefixes, None)

    def head_object(self, key: str) -> S3ClientObject:
        if key not in self.objects:
            raise S3ClientError(S3ClientErrorKind.NOT_FOUND)
        return S3ClientObject(key, len(self.objects[key]), NOW, f"etag-{key}")

    def get_object(self, key: str):
        if key not in self.objects:
            raise S3ClientError(S3ClientErrorKind.NOT_FOUND)
        return io.BytesIO(self.objects[key])

    def put_object(self, key: str, data, *, content_type=None) -> None:
        if isinstance(data, bytes | bytearray | memoryview):
            self.objects[key] = bytes(data)
        else:
            chunks = []
            while chunk := data.read(1024 * 1024):
                chunks.append(chunk)
            self.objects[key] = b"".join(chunks)

    def create_multipart_upload(self, key: str) -> str:
        self.uploads["upload-1"] = []
        return "upload-1"

    def upload_part(self, key: str, upload_id: str, part_number: int, data: bytes) -> str:
        self.uploads[upload_id].append(data)
        return f"etag-{part_number}"

    def complete_multipart_upload(self, key: str, upload_id: str, parts) -> None:
        self.objects[key] = b"".join(self.uploads.pop(upload_id))

    def abort_multipart_upload(self, key: str, upload_id: str) -> None:
        self.uploads.pop(upload_id, None)

    def copy_object(self, source_key: str, target_key: str) -> None:
        if source_key not in self.objects:
            raise S3ClientError(S3ClientErrorKind.NOT_FOUND)
        self.objects[target_key] = self.objects[source_key]

    def delete_object(self, key: str) -> None:
        if key not in self.objects:
            raise S3ClientError(S3ClientErrorKind.NOT_FOUND)
        self.delete_calls.append(key)
        del self.objects[key]


class ProviderCleanupSemanticsTests(unittest.TestCase):
    """The supported OpenList/S3 Move-plus-ignorable-cleanup journey."""

    @staticmethod
    def _cleanup_plan(
        patterns: tuple[str, ...] = ("*.txt",),
        storage_id: str = "local",
        source: str = "source/movie/Movie.mkv",
        target: str = "target/Movie/Movie.mkv",
    ) -> OrganizePlan:
        return (
            plan(
                source,
                target,
                cleanup=DirectoryCleanupPolicy(
                    DirectoryCleanupMode.IGNORABLE,
                    ignore_patterns=patterns,
                ),
            )
            if storage_id == "local"
            else OrganizePlan(
                storage_id,
                storage_id,
                source,
                target,
                "A",
                "A",
                "A",
                "A",
                operation=PlanOperation.MOVE,
                status=PlanStatus.READY,
                plan_id="cleanup-plan",
                media_library_root="",
                relative_destination="",
                source_location=StorageLocation(storage_id, source),
                destination_location=StorageLocation(storage_id, target),
                source_library_root="",
                source_directory_cleanup=DirectoryCleanupPolicy(
                    DirectoryCleanupMode.IGNORABLE,
                    ignore_patterns=patterns,
                ),
            )
        )

    def test_openlist_ignorable_cleanup_completes_the_motivating_journey(self) -> None:
        client = _FakeOpenListClient()
        storage = OpenListStorage(
            OpenListStorageConfig("ol", "OpenList", "https://openlist.invalid", "token"), client
        )
        client.entries["/src"] = client.entry("src", directory=True)
        client.entries["/src/Movie.mkv"] = client.entry("Movie.mkv", size=11)
        client.entries["/src/ad.txt"] = client.entry("ad.txt", size=3)
        client.entries["/src/thumb.txt"] = client.entry("thumb.txt", size=2)
        result = OrganizerExecutor().execute(
            self._cleanup_plan(storage_id="ol", source="src/Movie.mkv", target="dst/Movie.mkv"),
            {"ol": storage},
            execute=True,
        )
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(result.cleanup_status, DirectoryCleanupStatus.SUCCESS)
        # The media Move completed server-side and every policy-matched file was
        # removed before the provider-confirmed empty directory was deleted.
        self.assertEqual(
            sorted(client.entries),
            ["/dst", "/dst/Movie.mkv"],
        )
        self.assertEqual(
            [step.action for step in result.cleanup_steps],
            ["DELETE_IGNORED_FILE", "DELETE_IGNORED_FILE", "DELETE_EMPTY_DIRECTORY"],
        )
        # No Files-direct-Delete identity evidence is required or faked here.
        self.assertFalse(any("fingerprint" in step.action for step in result.cleanup_steps))

    def test_openlist_unknown_file_stops_cleanup_without_identity_bypass(self) -> None:
        client = _FakeOpenListClient()
        storage = OpenListStorage(
            OpenListStorageConfig("ol", "OpenList", "https://openlist.invalid", "token"), client
        )
        client.entries["/src"] = client.entry("src", directory=True)
        client.entries["/src/Movie.mkv"] = client.entry("Movie.mkv", size=11)
        client.entries["/src/ad.txt"] = client.entry("ad.txt")
        client.entries["/src/keep.mkv"] = client.entry("keep.mkv", size=5)
        result = OrganizerExecutor().execute(
            self._cleanup_plan(storage_id="ol", source="src/Movie.mkv", target="dst/Movie.mkv"),
            {"ol": storage},
            execute=True,
        )
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(result.cleanup_status, DirectoryCleanupStatus.STOPPED)
        self.assertIn("/src/ad.txt", client.entries)
        self.assertIn("/src/keep.mkv", client.entries)
        self.assertFalse(any(step.success for step in result.cleanup_steps))

    def test_s3_ignorable_cleanup_records_the_absent_virtual_prefix(self) -> None:
        client = _FakeS3Client()
        storage = S3Storage(
            S3StorageConfig(
                "s3",
                "S3",
                S3Provider.S3_COMPATIBLE,
                "media",
                "ak",
                "sk",
                endpoint="https://s3.invalid",
                root_prefix="downloads",
            ),
            client,
            sleep=lambda _: None,
        )
        client.objects["downloads/src/Movie.mkv"] = b"media"
        client.objects["downloads/src/ad.txt"] = b"junk"
        client.objects["downloads/src/thumb.txt"] = b"junk2"
        result = OrganizerExecutor().execute(
            self._cleanup_plan(storage_id="s3", source="src/Movie.mkv", target="dst/Movie.mkv"),
            {"s3": storage},
            execute=True,
        )
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(result.cleanup_status, DirectoryCleanupStatus.SUCCESS)
        # Every admitted object is gone and no fictional directory object was
        # deleted: only the two matched files plus the moved media were deleted.
        self.assertEqual(
            sorted(client.delete_calls),
            [
                "downloads/src/Movie.mkv",
                "downloads/src/ad.txt",
                "downloads/src/thumb.txt",
            ],
        )
        # The organized destination is a real created directory marker; the
        # emptied source prefix is gone without any fictional object deletion.
        self.assertEqual(sorted(client.objects), ["downloads/dst/", "downloads/dst/Movie.mkv"])
        self.assertEqual(
            [step.action for step in result.cleanup_steps],
            ["DELETE_IGNORED_FILE", "DELETE_IGNORED_FILE", "DIRECTORY_ALREADY_ABSENT"],
        )

    def test_s3_explicit_empty_marker_is_deleted_after_matched_files(self) -> None:
        client = _FakeS3Client()
        storage = S3Storage(
            S3StorageConfig(
                "s3",
                "S3",
                S3Provider.S3_COMPATIBLE,
                "media",
                "ak",
                "sk",
                endpoint="https://s3.invalid",
                root_prefix="downloads",
            ),
            client,
            sleep=lambda _: None,
        )
        client.objects["downloads/src/Movie.mkv"] = b"media"
        client.objects["downloads/src/ad.txt"] = b"junk"
        client.objects["downloads/src/"] = b""
        result = OrganizerExecutor().execute(
            self._cleanup_plan(storage_id="s3", source="src/Movie.mkv", target="dst/Movie.mkv"),
            {"s3": storage},
            execute=True,
        )
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(result.cleanup_status, DirectoryCleanupStatus.SUCCESS)
        # The explicit empty marker is deleted through the executor; no other
        # object is touched.
        self.assertEqual(
            sorted(client.delete_calls),
            ["downloads/src/", "downloads/src/Movie.mkv", "downloads/src/ad.txt"],
        )
        self.assertEqual(sorted(client.objects), ["downloads/dst/", "downloads/dst/Movie.mkv"])

    def test_s3_cleanup_permission_refusal_keeps_partial_known_effects(self) -> None:
        class RefusingClient(_FakeS3Client):
            def __init__(self) -> None:
                super().__init__()
                self.deletions = 0

            def delete_object(self, key: str) -> None:
                self.deletions += 1
                if key.endswith("thumb.txt"):
                    raise S3ClientError(S3ClientErrorKind.PERMISSION_DENIED)
                super().delete_object(key)

        client = RefusingClient()
        storage = S3Storage(
            S3StorageConfig(
                "s3",
                "S3",
                S3Provider.S3_COMPATIBLE,
                "media",
                "ak",
                "sk",
                endpoint="https://s3.invalid",
                root_prefix="downloads",
            ),
            client,
            sleep=lambda _: None,
        )
        client.objects["downloads/src/Movie.mkv"] = b"media"
        client.objects["downloads/src/ad.txt"] = b"junk"
        client.objects["downloads/src/thumb.txt"] = b"junk2"
        result = OrganizerExecutor().execute(
            self._cleanup_plan(storage_id="s3", source="src/Movie.mkv", target="dst/Movie.mkv"),
            {"s3": storage},
            execute=True,
        )
        # The media Move stays successful; the first deletion is a known partial
        # effect and the refused deletion is never replayed automatically.
        self.assertEqual(result.status, ExecutionStatus.PARTIAL)
        self.assertEqual(result.cleanup_status, DirectoryCleanupStatus.PARTIAL)
        self.assertEqual(
            sorted(client.objects),
            ["downloads/dst/", "downloads/dst/Movie.mkv", "downloads/src/thumb.txt"],
        )
        self.assertEqual(client.deletions, 3)

    def test_same_name_replacement_still_matching_the_pattern_is_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "source/movie/Movie.mkv")
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")
            junk = Path(source.parent, "ad.txt")
            junk.write_bytes(b"first")
            executor = OrganizerExecutor()

            class ReplacementStorage(LocalStorage):
                def stat(self, path: str):
                    observed = super().stat(path)
                    if observed.name == "ad.txt" and observed.size == len(b"first"):
                        # A concurrent writer replaced the junk file with a
                        # different, still pattern-matching regular file.
                        junk.write_bytes(b"replacement-with-different-size")
                    return observed

            result = executor.execute(
                self._cleanup_plan(),
                {"local": ReplacementStorage("local", directory)},
                execute=True,
            )
            self.assertEqual(result.status, ExecutionStatus.SUCCESS)
            self.assertEqual(result.cleanup_status, DirectoryCleanupStatus.SUCCESS)
            self.assertFalse(junk.exists())


if __name__ == "__main__":
    unittest.main()
