from __future__ import annotations

import copy
import json
import tempfile
import unittest
from dataclasses import replace
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
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration


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


if __name__ == "__main__":
    unittest.main()
