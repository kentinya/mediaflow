from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from mediaflow.application.attachments import AttachmentDiscovery, AttachmentPlanner
from mediaflow.application.conflict_resolution import ConflictResolver
from mediaflow.application.media_organizer import MediaOrganizerItemResult
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.organizer import (
    AttachmentPlan,
    AttachmentPolicy,
    AttachmentType,
    Conflict,
    ConflictType,
    ExecutionStatus,
    MediaAttachment,
    MediaFileSet,
    OrganizePlan,
    PlanOperation,
    PlanStatus,
    StorageLocation,
)
from mediaflow.domain.storage import StorageCapabilities, StorageEntry, StorageEntryType
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.infrastructure.strategy_user_configuration import load_strategy_configuration


def entry(path: str, size: int = 1) -> StorageEntry:
    return StorageEntry(
        path.rsplit("/", 1)[-1], path, StorageEntryType.FILE, size, datetime.now(UTC)
    )


class DiscoveryStorage:
    storage_id = "source"
    name = "source"
    read_only = True
    capabilities = StorageCapabilities()

    def __init__(self, entries: tuple[StorageEntry, ...]) -> None:
        self.entries = entries
        self.list_calls = 0
        self.other_calls = 0

    def list(self, path: str):
        self.list_calls += 1
        return self.entries

    def __getattr__(self, name: str):
        self.other_calls += 1
        raise AssertionError(f"discovery called Storage.{name}")


def primary_plan(operation: PlanOperation = PlanOperation.MOVE) -> OrganizePlan:
    return OrganizePlan(
        "source",
        "target",
        "Incoming/Movie.mkv",
        "Movies/Movie/Movie.mkv",
        "C",
        "A",
        "A",
        "A",
        operation=operation,
        status=PlanStatus.READY,
        plan_id="attachments-plan",
        media_library_root="Movies",
        relative_destination="Movie/Movie.mkv",
        source_location=StorageLocation("source", "Incoming/Movie.mkv"),
        destination_location=StorageLocation("target", "Movies/Movie/Movie.mkv"),
    )


class AttachmentTests(unittest.TestCase):
    def test_discovery_preserves_subtitle_language_flags_and_is_read_only(self) -> None:
        storage = DiscoveryStorage(
            (
                entry("Incoming/Movie.mkv", 100),
                entry("Incoming/Movie.zh-CN.forced.ASS"),
                entry("Incoming/Movie.en.sdh.srt"),
                entry("Incoming/Movie.hi.VTT"),
                entry("Incoming/Other.en.srt"),
            )
        )
        result = AttachmentDiscovery().discover(
            storage,
            StorageLocation("source", "Incoming/Movie.mkv"),
            AttachmentPolicy(enabled=True),
        )
        self.assertEqual(len(result.attachments), 3)
        by_path = {item.source.path: item for item in result.attachments}
        self.assertEqual(by_path["Incoming/Movie.zh-CN.forced.ASS"].language, "zh-CN")
        self.assertEqual(by_path["Incoming/Movie.zh-CN.forced.ASS"].flags, ("forced",))
        self.assertEqual(by_path["Incoming/Movie.en.sdh.srt"].flags, ("sdh",))
        self.assertEqual(by_path["Incoming/Movie.hi.VTT"].flags, ("hi",))
        self.assertEqual(storage.list_calls, 1)
        self.assertEqual(storage.other_calls, 0)

    def test_nfo_artwork_trailer_unicode_unknown_and_disabled_kinds(self) -> None:
        entries = (
            entry("电影/流浪地球.mkv"),
            entry("电影/流浪地球.nfo"),
            entry("电影/poster.JPG"),
            entry("电影/fanart.png"),
            entry("电影/流浪地球-trailer.MP4"),
            entry("电影/流浪地球.logo.webp"),
            entry("电影/流浪地球.txt"),
            entry("电影/unrelated.nfo"),
        )
        storage = DiscoveryStorage(entries)
        result = AttachmentDiscovery().discover(
            storage,
            StorageLocation("source", "电影/流浪地球.mkv"),
            AttachmentPolicy(enabled=True),
        )
        self.assertEqual(
            {item.attachment_type for item in result.attachments},
            {
                AttachmentType.NFO,
                AttachmentType.POSTER,
                AttachmentType.FANART,
                AttachmentType.TRAILER,
                AttachmentType.IMAGE,
            },
        )
        disabled = AttachmentDiscovery().discover(
            storage,
            StorageLocation("source", "电影/流浪地球.mkv"),
            AttachmentPolicy(enabled=True, nfo=False, artwork=False, trailers=False),
        )
        self.assertEqual(disabled.attachments, ())
        off = AttachmentDiscovery().discover(
            DiscoveryStorage(()),
            StorageLocation("source", "电影/流浪地球.mkv"),
            AttachmentPolicy(),
        )
        self.assertEqual(off.attachments, ())

    def test_planning_uses_named_stem_and_detects_existing_target(self) -> None:
        file_set = MediaFileSet(
            StorageLocation("source", "Incoming/Movie.mkv"),
            (
                MediaAttachment(
                    StorageLocation("source", "Incoming/Movie.zh-CN.forced.ass"),
                    AttachmentType.SUBTITLE,
                    ".zh-CN.forced",
                ),
                MediaAttachment(
                    StorageLocation("source", "Incoming/Movie.nfo"), AttachmentType.NFO
                ),
                MediaAttachment(
                    StorageLocation("source", "Incoming/poster.jpg"), AttachmentType.POSTER
                ),
            ),
        )
        target = DiscoveryStorage(())
        target.exists = lambda path: path.endswith("Movie.nfo")
        plan = AttachmentPlanner().plan(primary_plan(), file_set, target)
        self.assertEqual(
            tuple(item.destination.path for item in plan.attachment_plans),
            (
                "Movies/Movie/Movie.zh-CN.forced.ass",
                "Movies/Movie/Movie.nfo",
                "Movies/Movie/poster.jpg",
            ),
        )
        self.assertEqual(plan.status, PlanStatus.CONFLICT)
        self.assertEqual(len(plan.conflicts), 1)

    def test_rename_retargets_the_complete_file_set(self) -> None:
        attachment = AttachmentPlan(
            StorageLocation("source", "Incoming/Movie.en.srt"),
            StorageLocation("target", "Movies/Movie/Movie.en.srt"),
            AttachmentType.SUBTITLE,
            PlanOperation.MOVE,
            ".en",
        )
        plan = replace(
            primary_plan(),
            attachment_plans=(attachment,),
            conflicts=(
                Conflict(
                    ConflictType.DESTINATION_EXISTS,
                    "Incoming/Movie.mkv",
                    "Movies/Movie/Movie.mkv",
                    "target exists",
                ),
            ),
            status=PlanStatus.CONFLICT,
        )
        target = DiscoveryStorage(())
        target.exists = lambda path: False
        renamed = ConflictResolver().rename(plan, target)
        self.assertEqual(renamed.target, "Movies/Movie/Movie (1).mkv")
        self.assertEqual(
            renamed.attachment_plans[0].destination.path,
            "Movies/Movie/Movie (1).en.srt",
        )

    def test_deterministic_discovery_order(self) -> None:
        values = (
            entry("Incoming/Movie.en.srt"),
            entry("Incoming/Movie.nfo"),
            entry("Incoming/Movie.zh.ass"),
        )
        policy = AttachmentPolicy(enabled=True)
        forward = AttachmentDiscovery().discover(
            DiscoveryStorage(values), StorageLocation("source", "Incoming/Movie.mkv"), policy
        )
        reverse = AttachmentDiscovery().discover(
            DiscoveryStorage(tuple(reversed(values))),
            StorageLocation("source", "Incoming/Movie.mkv"),
            policy,
        )
        self.assertEqual(forward.attachments, reverse.attachments)

    def test_configuration_is_opt_in_and_validated(self) -> None:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        loaded = load_strategy_configuration(document, require_complete=True)
        self.assertFalse(loaded.strategy.organize_policies[0].attachments.enabled)
        document["organizePolicies"][0]["attachments"] = {
            "enabled": True,
            "subtitles": True,
            "nfo": False,
            "artwork": True,
            "trailers": True,
            "otherSameStem": False,
        }
        loaded = load_strategy_configuration(document, require_complete=True)
        self.assertTrue(loaded.strategy.organize_policies[0].attachments.enabled)
        self.assertFalse(loaded.strategy.organize_policies[0].attachments.nfo)
        document["organizePolicies"][0]["attachments"] = {"enabled": "yes"}
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            load_strategy_configuration(document, require_complete=True)

    def test_dry_run_file_set_has_zero_storage_calls(self) -> None:
        class Exploding:
            def __getattr__(self, name: str):
                raise AssertionError(f"dry-run called Storage.{name}")

        attachment = AttachmentPlan(
            StorageLocation("source", "Incoming/Movie.en.srt"),
            StorageLocation("target", "Movies/Movie/Movie.en.srt"),
            AttachmentType.SUBTITLE,
            PlanOperation.MOVE,
            ".en",
        )
        plan = replace(primary_plan(), attachment_plans=(attachment,))
        result = OrganizerExecutor().execute(plan, {"source": Exploding(), "target": Exploding()})
        self.assertEqual(result.status, ExecutionStatus.DRY_RUN)

    def test_local_move_copy_and_hardlink_execute_attachments(self) -> None:
        for operation in (PlanOperation.MOVE, PlanOperation.COPY, PlanOperation.LINK):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "Incoming").mkdir()
                (root / "Incoming" / "Movie.mkv").write_bytes(b"video")
                (root / "Incoming" / "Movie.en.srt").write_bytes(b"subtitle")
                storage = LocalStorage("local", root)
                plan = replace(
                    primary_plan(operation),
                    source_storage_id="local",
                    target_storage_id="local",
                    source_location=StorageLocation("local", "Incoming/Movie.mkv"),
                    destination_location=StorageLocation("local", "Movies/Movie/Movie.mkv"),
                    attachment_plans=(
                        AttachmentPlan(
                            StorageLocation("local", "Incoming/Movie.en.srt"),
                            StorageLocation("local", "Movies/Movie/Movie.en.srt"),
                            AttachmentType.SUBTITLE,
                            operation,
                            ".en",
                        ),
                    ),
                )
                result = OrganizerExecutor().execute(plan, {"local": storage}, execute=True)
                self.assertEqual(result.status, ExecutionStatus.SUCCESS, result.errors)
                self.assertEqual((root / "Movies/Movie/Movie.en.srt").read_bytes(), b"subtitle")
                if operation is PlanOperation.MOVE:
                    self.assertFalse((root / "Incoming/Movie.en.srt").exists())
                else:
                    self.assertTrue((root / "Incoming/Movie.en.srt").exists())

    def test_cross_storage_move_and_copy_include_attachments(self) -> None:
        for operation in (PlanOperation.MOVE, PlanOperation.COPY):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source_root, target_root = root / "source", root / "target"
                (source_root / "Incoming").mkdir(parents=True)
                target_root.mkdir()
                (source_root / "Incoming/Movie.mkv").write_bytes(b"video")
                (source_root / "Incoming/Movie.nfo").write_bytes(b"nfo")
                source = LocalStorage("source", source_root)
                target = LocalStorage("target", target_root)
                attachment = AttachmentPlan(
                    StorageLocation("source", "Incoming/Movie.nfo"),
                    StorageLocation("target", "Movies/Movie/Movie.nfo"),
                    AttachmentType.NFO,
                    operation,
                )
                plan = replace(primary_plan(operation), attachment_plans=(attachment,))
                result = OrganizerExecutor().execute(
                    plan, {"source": source, "target": target}, execute=True
                )
                self.assertEqual(result.status, ExecutionStatus.SUCCESS, result.errors)
                self.assertTrue((target_root / "Movies/Movie/Movie.nfo").exists())
                self.assertEqual(
                    (source_root / "Incoming/Movie.nfo").exists(),
                    operation is PlanOperation.COPY,
                )

    def test_partial_failure_records_attachment_and_preserves_unknown(self) -> None:
        class FailSecondMoveStorage(LocalStorage):
            def __init__(self, storage_id: str, root: Path) -> None:
                super().__init__(storage_id, root)
                self.moves = 0

            def move(self, source: str, target: str, *, overwrite: bool = False) -> None:
                self.moves += 1
                if self.moves == 2:
                    raise OSError("simulated primary failure")
                super().move(source, target, overwrite=overwrite)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Incoming").mkdir()
            (root / "Incoming/Movie.mkv").write_bytes(b"video")
            (root / "Incoming/Movie.en.srt").write_bytes(b"subtitle")
            (root / "Incoming/unknown.bin").write_bytes(b"keep")
            storage = FailSecondMoveStorage("local", root)
            attachment = AttachmentPlan(
                StorageLocation("local", "Incoming/Movie.en.srt"),
                StorageLocation("local", "Movies/Movie/Movie.en.srt"),
                AttachmentType.SUBTITLE,
                PlanOperation.MOVE,
            )
            plan = replace(
                primary_plan(),
                source_storage_id="local",
                target_storage_id="local",
                source_location=StorageLocation("local", "Incoming/Movie.mkv"),
                destination_location=StorageLocation("local", "Movies/Movie/Movie.mkv"),
                attachment_plans=(attachment,),
            )
            result = OrganizerExecutor().execute(plan, {"local": storage}, execute=True)
            self.assertEqual(result.status, ExecutionStatus.PARTIAL)
            self.assertTrue(
                any(
                    value.startswith("ATTACHMENT:subtitle") for value in result.completed_operations
                )
            )
            self.assertTrue((root / "Incoming/Movie.mkv").exists())
            self.assertTrue((root / "Incoming/unknown.bin").exists())

            database = root / "runtime.sqlite3"
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("organize", execute_authorized=True)
                item = coordinator.begin_item(
                    task.task_id, "local", "source", "Incoming/Movie.mkv", "Movie.mkv"
                )
                coordinator.complete_item(
                    item,
                    MediaOrganizerItemResult("Movie.mkv", plan=plan, execution=result),
                )
            with SQLiteTaskRepository(database) as reopened:
                persisted = reopened.list_results(task.task_id)[0]
                self.assertEqual(persisted.attachment_count, 1)
                self.assertTrue(
                    any(
                        value.startswith("ATTACHMENT:subtitle")
                        for value in persisted.completed_operations
                    )
                )
