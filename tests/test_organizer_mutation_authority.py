from __future__ import annotations

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
    ExecutionEffectCertainty,
    ExecutionStatus,
    OrganizeOperationType,
    OrganizePlan,
    PlanOperation,
    PlanStatus,
    RollbackPolicy,
    RollbackStatus,
    StorageLocation,
)
from mediaflow.infrastructure.local_storage import LocalStorage


def _plan(
    *,
    operation: PlanOperation = PlanOperation.MOVE,
    source_storage_id: str = "local",
    target_storage_id: str = "local",
    source: str = "Incoming/Movie.mkv",
    target: str = "Movies/Movie/Movie.mkv",
    attachments: tuple[AttachmentPlan, ...] = (),
    rollback: bool = False,
    cleanup: DirectoryCleanupPolicy | None = None,
) -> OrganizePlan:
    return OrganizePlan(
        source_storage_id,
        target_storage_id,
        source,
        target,
        "C",
        "naming-a",
        "classification-a",
        "organize-authority",
        operation=operation,
        status=PlanStatus.READY,
        plan_id="mutation-authority-plan",
        media_library_root="Movies",
        relative_destination="Movie/Movie.mkv",
        source_location=StorageLocation(source_storage_id, source),
        destination_location=StorageLocation(target_storage_id, target),
        attachment_plans=attachments,
        rollback_policy=RollbackPolicy(enabled=rollback),
        source_library_root=source.split("/", 1)[0],
        source_directory_cleanup=cleanup or DirectoryCleanupPolicy(),
    )


class AuthorityRecorder:
    def __init__(self, *, fail_on: int | None = None, fail_prefix: str | None = None):
        self.fail_on = fail_on
        self.fail_prefix = fail_prefix
        self.calls: list[tuple[str, str]] = []
        self._count = 0

    def __call__(self, plan: OrganizePlan, boundary: str) -> None:
        self.calls.append((plan.source, boundary))
        self._count += 1
        if self.fail_prefix and boundary.startswith(self.fail_prefix):
            raise RuntimeError("live authority refused")
        if self.fail_on is not None and self._count == self.fail_on:
            raise RuntimeError("live authority refused")


def _attachment(
    source: str = "Incoming/Movie.en.srt",
    destination: str = "Movies/Movie/Movie.en.srt",
    attachment_type: AttachmentType = AttachmentType.SUBTITLE,
) -> AttachmentPlan:
    return AttachmentPlan(
        StorageLocation("local", source),
        StorageLocation("local", destination),
        attachment_type,
        PlanOperation.MOVE,
    )


class OrganizerMutationAuthorityTests(unittest.TestCase):
    def test_refusal_before_first_mutation_is_zero_effect_failed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Incoming").mkdir()
            (root / "Incoming" / "Movie.mkv").write_bytes(b"media")
            authority = AuthorityRecorder(fail_on=1)
            result = OrganizerExecutor().execute(
                _plan(),
                {"local": LocalStorage("local", root)},
                execute=True,
                mutation_authority=authority,
            )
            self.assertEqual(ExecutionStatus.FAILED, result.status)
            self.assertEqual((), result.completed_operations)
            self.assertEqual(ExecutionEffectCertainty.NONE, result.effect_certainty)
            self.assertIn("CREATE_DIRECTORY", authority.calls[0][1])
            self.assertIn("unattended authority refused", result.errors[0])
            self.assertTrue((root / "Incoming" / "Movie.mkv").read_bytes() == b"media")
            self.assertFalse((root / "Movies").exists())

    def test_refusal_after_one_attachment_stops_second_attachment_and_primary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Incoming").mkdir()
            (root / "Incoming" / "Movie.mkv").write_bytes(b"media")
            (root / "Incoming" / "Movie.en.srt").write_bytes(b"english")
            (root / "Incoming" / "Movie.zh.srt").write_bytes(b"chinese")
            plan = _plan(
                attachments=(
                    _attachment(),
                    _attachment(
                        source="Incoming/Movie.zh.srt",
                        destination="Movies/Movie/Movie.zh.srt",
                    ),
                )
            )
            authority = AuthorityRecorder(fail_on=3)
            result = OrganizerExecutor().execute(
                plan,
                {"local": LocalStorage("local", root)},
                execute=True,
                mutation_authority=authority,
            )
            self.assertEqual(ExecutionStatus.PARTIAL, result.status)
            self.assertEqual(
                (
                    "CREATE_DIRECTORY",
                    "ATTACHMENT:subtitle:Incoming/Movie.en.srt",
                ),
                result.completed_operations,
            )
            self.assertEqual(ExecutionEffectCertainty.VERIFIED_COMPLETE, result.effect_certainty)
            self.assertEqual(RollbackStatus.DISABLED, result.rollback_status)
            self.assertEqual(
                ["CREATE_DIRECTORY", "ATTACHMENT:MOVE", "ATTACHMENT:MOVE"],
                [boundary for _source, boundary in authority.calls],
            )
            self.assertTrue((root / "Movies" / "Movie" / "Movie.en.srt").read_bytes() == b"english")
            self.assertFalse((root / "Incoming" / "Movie.en.srt").exists())
            self.assertTrue((root / "Incoming" / "Movie.zh.srt").read_bytes() == b"chinese")
            self.assertFalse((root / "Movies" / "Movie" / "Movie.zh.srt").exists())
            self.assertTrue((root / "Incoming" / "Movie.mkv").read_bytes() == b"media")

    def test_refusal_after_attachment_before_primary_records_completed_effect(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Incoming").mkdir()
            (root / "Incoming" / "Movie.mkv").write_bytes(b"media")
            (root / "Incoming" / "Movie.en.srt").write_bytes(b"english")
            authority = AuthorityRecorder(fail_prefix="PRIMARY:")
            result = OrganizerExecutor().execute(
                _plan(attachments=(_attachment(),)),
                {"local": LocalStorage("local", root)},
                execute=True,
                mutation_authority=authority,
            )
            self.assertEqual(ExecutionStatus.PARTIAL, result.status)
            self.assertEqual(
                (
                    "CREATE_DIRECTORY",
                    "ATTACHMENT:subtitle:Incoming/Movie.en.srt",
                ),
                result.completed_operations,
            )
            self.assertTrue((root / "Movies" / "Movie" / "Movie.en.srt").read_bytes() == b"english")
            self.assertTrue((root / "Incoming" / "Movie.mkv").read_bytes() == b"media")
            self.assertIn("PRIMARY:MOVE", authority.calls[-1][1])

    def test_refusal_before_cleanup_delete_preserves_source_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source" / "movie" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")
            plan = replace(
                _plan(
                    source="source/movie/Movie.mkv",
                    source_storage_id="local",
                    target_storage_id="local",
                    cleanup=DirectoryCleanupPolicy(DirectoryCleanupMode.EMPTY),
                ),
                source_library_root="source",
            )
            authority = AuthorityRecorder(fail_prefix="CLEANUP_DELETE_DIRECTORY")
            result = OrganizerExecutor().execute(
                plan,
                {"local": LocalStorage("local", root)},
                execute=True,
                mutation_authority=authority,
            )
            self.assertEqual(ExecutionStatus.PARTIAL, result.status)
            self.assertEqual(DirectoryCleanupStatus.REFUSED, result.cleanup_status)
            self.assertEqual(("CREATE_DIRECTORY", "MOVE"), result.completed_operations)
            self.assertTrue((root / "Movies" / "Movie" / "Movie.mkv").read_bytes() == b"media")
            self.assertTrue(source.parent.exists())
            self.assertTrue(authority.calls[-1][1].startswith("CLEANUP_DELETE_DIRECTORY"))

    def test_refusal_before_ignored_file_delete_preserves_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source" / "movie" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")
            ignored = source.parent / ".DS_Store"
            ignored.write_bytes(b"ignore-me")
            plan = replace(
                _plan(
                    source="source/movie/Movie.mkv",
                    cleanup=DirectoryCleanupPolicy(
                        DirectoryCleanupMode.IGNORABLE,
                        ignore_patterns=(".DS_Store",),
                    ),
                ),
                source_library_root="source",
            )
            authority = AuthorityRecorder(fail_prefix="CLEANUP_DELETE_IGNORED_FILE")
            result = OrganizerExecutor().execute(
                plan,
                {"local": LocalStorage("local", root)},
                execute=True,
                mutation_authority=authority,
            )
            self.assertEqual(ExecutionStatus.PARTIAL, result.status)
            self.assertEqual(DirectoryCleanupStatus.REFUSED, result.cleanup_status)
            self.assertEqual(("CREATE_DIRECTORY", "MOVE"), result.completed_operations)
            self.assertTrue(ignored.read_bytes() == b"ignore-me")
            self.assertTrue(authority.calls[-1][1] == "CLEANUP_DELETE_IGNORED_FILE")

    def test_cross_storage_move_refuses_source_delete_after_verified_copy(self) -> None:
        with (
            tempfile.TemporaryDirectory() as source_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            Path(source_root, "Incoming").mkdir()
            source_path = Path(source_root, "Incoming", "Movie.mkv")
            source_path.write_bytes(b"media")
            source_storage = LocalStorage("source", source_root)
            target_storage = LocalStorage("target", target_root)
            plan = _plan(
                source_storage_id="source",
                target_storage_id="target",
                source="Incoming/Movie.mkv",
                target="Movies/Movie/Movie.mkv",
            )
            authority = AuthorityRecorder(fail_on=3)
            result = OrganizerExecutor().execute(
                plan,
                {"source": source_storage, "target": target_storage},
                execute=True,
                mutation_authority=authority,
            )
            self.assertEqual(ExecutionStatus.PARTIAL, result.status)
            self.assertEqual(("CREATE_DIRECTORY", "COPY"), result.completed_operations)
            self.assertIn("CROSS_STORAGE_DELETE_SOURCE", authority.calls[-1][1])
            self.assertTrue(source_path.exists())
            self.assertEqual(b"media", source_path.read_bytes())
            self.assertEqual(
                b"media",
                Path(target_root, "Movies", "Movie", "Movie.mkv").read_bytes(),
            )

    def test_rollback_never_mutates_when_authority_is_refused(self) -> None:
        class FailingCopyStorage(LocalStorage):
            def copy(self, source, target, *, overwrite=False):
                if source.endswith(".mkv"):
                    raise RuntimeError("injected primary copy failure")
                return super().copy(source, target, overwrite=overwrite)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Incoming").mkdir()
            (root / "Incoming" / "Movie.mkv").write_bytes(b"media")
            (root / "Incoming" / "Movie.en.srt").write_bytes(b"english")
            attachment = replace(
                _attachment(),
                operation=PlanOperation.COPY,
            )
            plan = replace(
                _plan(
                    operation=PlanOperation.COPY,
                    attachments=(attachment,),
                    rollback=True,
                ),
                destination_location=StorageLocation("local", "Movies/Movie/Movie.mkv"),
            )
            authority = AuthorityRecorder(fail_prefix="ROLLBACK:")
            result = OrganizerExecutor().execute(
                plan,
                {"local": FailingCopyStorage("local", root)},
                execute=True,
                mutation_authority=authority,
            )
            self.assertEqual(ExecutionStatus.PARTIAL, result.status)
            self.assertEqual(RollbackStatus.PARTIAL, result.rollback_status)
            self.assertEqual(ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED, result.effect_certainty)
            self.assertTrue((root / "Movies" / "Movie" / "Movie.en.srt").read_bytes() == b"english")
            self.assertTrue((root / "Incoming" / "Movie.en.srt").read_bytes() == b"english")
            self.assertTrue((root / "Movies").exists())
            self.assertTrue(
                any(boundary.startswith("ROLLBACK:") for _, boundary in authority.calls)
            )
            self.assertTrue(any("unattended authority refused" in error for error in result.errors))

    def test_authority_valid_success_path_invokes_hook_before_each_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Incoming").mkdir()
            (root / "Incoming" / "Movie.mkv").write_bytes(b"media")
            (root / "Incoming" / "Movie.en.srt").write_bytes(b"english")
            authority = AuthorityRecorder()
            result = OrganizerExecutor().execute(
                _plan(attachments=(_attachment(),)),
                {"local": LocalStorage("local", root)},
                execute=True,
                mutation_authority=authority,
            )
            self.assertEqual(ExecutionStatus.SUCCESS, result.status, result.errors)
            self.assertEqual(
                [
                    "CREATE_DIRECTORY",
                    "ATTACHMENT:MOVE",
                    "PRIMARY:MOVE",
                ],
                [boundary for _source, boundary in authority.calls],
            )

    def test_hook_boundary_labels_cover_copy_hard_link_and_soft_link(self) -> None:
        cases = (
            (PlanOperation.COPY, None, "PRIMARY:COPY"),
            (PlanOperation.LINK, OrganizeOperationType.HARD_LINK, "PRIMARY:HARD_LINK"),
            (PlanOperation.LINK, OrganizeOperationType.SOFT_LINK, "PRIMARY:SOFT_LINK"),
        )
        for operation, link_operation, expected_boundary in cases:
            with (
                self.subTest(operation=operation, link_operation=link_operation),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                (root / "Incoming").mkdir()
                (root / "Incoming" / "Movie.mkv").write_bytes(b"media")
                plan = _plan(operation=operation)
                if link_operation is not None:
                    plan = replace(plan, link_operation=link_operation)
                authority = AuthorityRecorder(fail_on=2)
                result = OrganizerExecutor().execute(
                    plan,
                    {"local": LocalStorage("local", root)},
                    execute=True,
                    mutation_authority=authority,
                )
                self.assertEqual(ExecutionStatus.PARTIAL, result.status)
                self.assertEqual(("CREATE_DIRECTORY",), result.completed_operations)
                self.assertEqual(expected_boundary, authority.calls[-1][1])
                self.assertEqual(b"media", (root / "Incoming" / "Movie.mkv").read_bytes())

    def test_cross_storage_refusal_before_write_is_zero_effect(self) -> None:
        with (
            tempfile.TemporaryDirectory() as source_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            Path(source_root, "Incoming").mkdir()
            source_path = Path(source_root, "Incoming", "Movie.mkv")
            source_path.write_bytes(b"media")
            plan = _plan(
                source_storage_id="source",
                target_storage_id="target",
                source="Incoming/Movie.mkv",
                target="Movies/Movie/Movie.mkv",
            )
            authority = AuthorityRecorder(fail_on=2)
            result = OrganizerExecutor().execute(
                plan,
                {
                    "source": LocalStorage("source", source_root),
                    "target": LocalStorage("target", target_root),
                },
                execute=True,
                mutation_authority=authority,
            )
            self.assertEqual(ExecutionStatus.PARTIAL, result.status)
            self.assertEqual(("CREATE_DIRECTORY",), result.completed_operations)
            self.assertEqual("PRIMARY:CROSS_STORAGE_WRITE", authority.calls[-1][1])
            self.assertEqual(b"media", source_path.read_bytes())
            self.assertFalse(any("Movie.mkv" in path.name for path in Path(target_root).rglob("*")))
