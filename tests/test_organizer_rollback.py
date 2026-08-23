import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from mediaflow.application.organizer import OrganizePlanner, OrganizerExecutor
from mediaflow.domain.classification import ClassificationResult
from mediaflow.domain.library import MediaLibrary
from mediaflow.domain.naming import NamingResult
from mediaflow.domain.organizer import (
    AttachmentPlan,
    AttachmentType,
    ExecutionStatus,
    OrganizeOperationType,
    OrganizePolicy,
    RollbackPolicy,
    RollbackStatus,
    StorageLocation,
)
from mediaflow.domain.recognition import RecognitionResult, RecognitionType, RecognitionTypePolicy
from mediaflow.infrastructure.local_storage import LocalStorage


class _Delegate:
    def __init__(self, delegate):
        self._delegate = delegate
        self.storage_id = delegate.storage_id

    def __getattr__(self, name):
        return getattr(self._delegate, name)


class _FailSecondCopy(_Delegate):
    def __init__(self, delegate):
        super().__init__(delegate)
        self.calls = 0

    def copy(self, source, target, *, overwrite=False):
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("injected copy failure")
        return self._delegate.copy(source, target, overwrite=overwrite)


class _FailSecondLink(_Delegate):
    def __init__(self, delegate):
        super().__init__(delegate)
        self.calls = 0

    def hard_link(self, source, target):
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("injected link failure")
        return self._delegate.hard_link(source, target)


class _SourceReappearsOnce(_Delegate):
    def __init__(self, delegate, source_path):
        super().__init__(delegate)
        self.source_path = source_path
        self.absent_checks = 0

    def exists(self, path):
        actual = self._delegate.exists(path)
        if path == self.source_path and not actual:
            self.absent_checks += 1
            if self.absent_checks == 2:
                return True
        return actual


class _SourceRemainsReappeared(_SourceReappearsOnce):
    def exists(self, path):
        actual = self._delegate.exists(path)
        if path == self.source_path and not actual:
            self.absent_checks += 1
            return self.absent_checks >= 2
        return actual


class OrganizerRollbackTest(unittest.TestCase):
    @staticmethod
    def _plan(operation=OrganizeOperationType.COPY, *, rollback=True):
        recognition_type = RecognitionType("C", "C")
        policy = RecognitionTypePolicy(
            "type-c",
            recognition_type,
            "C",
            "A",
            "A",
            OrganizePolicy(
                "A",
                operation,
                rollback=RollbackPolicy(enabled=rollback),
            ),
        )
        return OrganizePlanner().plan(
            source_storage_id="local",
            source="source.mkv",
            source_storage_path="source.mkv",
            recognition=RecognitionResult(recognition_type, "rule-c"),
            type_policy=policy,
            media_library=MediaLibrary("movies", "Movies", "local", "Movies"),
            naming=NamingResult("Film", "Film.mkv", "A", "C"),
            classification=ClassificationResult("movies", "Animation", "A", "C"),
        )

    @staticmethod
    def _with_attachments(plan):
        parent = "Movies/Animation/Film"
        return replace(
            plan,
            attachment_plans=(
                AttachmentPlan(
                    StorageLocation("local", "first.srt"),
                    StorageLocation("local", f"{parent}/Film.srt"),
                    AttachmentType.SUBTITLE,
                    plan.operation,
                ),
                AttachmentPlan(
                    StorageLocation("local", "second.srt"),
                    StorageLocation("local", f"{parent}/Film.zh.srt"),
                    AttachmentType.SUBTITLE,
                    plan.operation,
                ),
            ),
        )

    def test_default_disabled_and_dry_run_are_zero_mutation(self):
        class Exploding:
            def __getattr__(self, name):
                raise AssertionError(f"Storage.{name} was accessed")

        plan = self._plan(rollback=False)
        self.assertFalse(plan.rollback_policy.enabled)
        result = OrganizerExecutor().execute(plan, {"local": Exploding()})
        self.assertEqual(ExecutionStatus.DRY_RUN, result.status)
        self.assertEqual(RollbackStatus.NOT_NEEDED, result.rollback_status)

    def test_copy_attachment_failure_compensates_in_reverse_and_cleans_directory(self):
        with tempfile.TemporaryDirectory() as root:
            for name in ("source.mkv", "first.srt", "second.srt"):
                Path(root, name).write_bytes(name.encode())
            storage = _FailSecondCopy(LocalStorage("local", root))
            result = OrganizerExecutor().execute(
                self._with_attachments(self._plan()), {"local": storage}, execute=True
            )
            self.assertEqual(ExecutionStatus.FAILED, result.status)
            self.assertEqual(RollbackStatus.SUCCESS, result.rollback_status)
            self.assertEqual(
                [
                    "ROLLBACK:ATTACHMENT:subtitle:first.srt",
                    "DELETE_DIRECTORY",
                    "DELETE_DIRECTORY",
                    "DELETE_DIRECTORY",
                ],
                [step.action for step in result.rollback_steps],
            )
            self.assertFalse(Path(root, "Movies").exists())
            self.assertTrue(Path(root, "first.srt").exists())

    def test_same_storage_move_is_restored_after_post_move_failure(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "source.mkv").write_bytes(b"media")
            storage = _SourceReappearsOnce(LocalStorage("local", root), "source.mkv")
            plan = self._plan(OrganizeOperationType.MOVE)
            result = OrganizerExecutor().execute(plan, {"local": storage}, execute=True)
            self.assertEqual(ExecutionStatus.FAILED, result.status)
            self.assertEqual(RollbackStatus.SUCCESS, result.rollback_status)
            self.assertEqual(b"media", Path(root, "source.mkv").read_bytes())
            self.assertFalse(Path(root, plan.target).exists())

    def test_hard_link_attachment_failure_removes_owned_link(self):
        with tempfile.TemporaryDirectory() as root:
            for name in ("source.mkv", "first.srt", "second.srt"):
                Path(root, name).write_bytes(name.encode())
            storage = _FailSecondLink(LocalStorage("local", root))
            plan = replace(
                self._plan(OrganizeOperationType.HARD_LINK),
                link_operation=OrganizeOperationType.HARD_LINK,
            )
            result = OrganizerExecutor().execute(
                self._with_attachments(plan), {"local": storage}, execute=True
            )
            self.assertEqual(ExecutionStatus.FAILED, result.status)
            self.assertEqual(RollbackStatus.SUCCESS, result.rollback_status)
            self.assertFalse(Path(root, "Movies").exists())
            self.assertTrue(Path(root, "first.srt").exists())

    def test_cross_storage_move_restores_deleted_source(self):
        with (
            tempfile.TemporaryDirectory() as source_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            Path(source_root, "source.mkv").write_bytes(b"media")
            source = _SourceReappearsOnce(LocalStorage("source", source_root), "source.mkv")
            target = LocalStorage("target", target_root)
            plan = replace(
                self._plan(OrganizeOperationType.MOVE),
                source_storage_id="source",
                target_storage_id="target",
                source_location=StorageLocation("source", "source.mkv"),
                destination_location=StorageLocation("target", self._plan().target),
            )
            result = OrganizerExecutor().execute(
                plan, {"source": source, "target": target}, execute=True
            )
            self.assertEqual(RollbackStatus.SUCCESS, result.rollback_status)
            self.assertEqual(b"media", Path(source_root, "source.mkv").read_bytes())
            self.assertFalse(Path(target_root, plan.target).exists())

    def test_reappeared_move_source_fails_closed_and_retains_target(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "source.mkv").write_bytes(b"media")
            storage = _SourceRemainsReappeared(LocalStorage("local", root), "source.mkv")
            plan = self._plan(OrganizeOperationType.MOVE)
            result = OrganizerExecutor().execute(plan, {"local": storage}, execute=True)
            self.assertEqual(ExecutionStatus.PARTIAL, result.status)
            self.assertEqual(RollbackStatus.PARTIAL, result.rollback_status)
            self.assertTrue(Path(root, plan.target).exists())
            self.assertEqual("rollback_safety_error", result.rollback_steps[0].error)

    def test_cross_storage_delete_failure_removes_owned_copy(self):
        class DeleteFails(_Delegate):
            def delete(self, path):
                raise RuntimeError("injected source delete failure")

        with (
            tempfile.TemporaryDirectory() as source_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            Path(source_root, "source.mkv").write_bytes(b"media")
            source = DeleteFails(LocalStorage("source", source_root))
            target = LocalStorage("target", target_root)
            base = self._plan(OrganizeOperationType.MOVE)
            plan = replace(
                base,
                source_storage_id="source",
                target_storage_id="target",
                source_location=StorageLocation("source", "source.mkv"),
                destination_location=StorageLocation("target", base.target),
            )
            result = OrganizerExecutor().execute(
                plan, {"source": source, "target": target}, execute=True
            )
            self.assertEqual(ExecutionStatus.FAILED, result.status)
            self.assertEqual(RollbackStatus.SUCCESS, result.rollback_status)
            self.assertTrue(Path(source_root, "source.mkv").exists())
            self.assertFalse(Path(target_root, plan.target).exists())

    def test_changed_owned_target_is_never_deleted(self):
        class ChangeBeforeRollback(_FailSecondCopy):
            def copy(self, source, target, *, overwrite=False):
                self.calls += 1
                if self.calls == 2:
                    Path(self._delegate._root, "Movies/Animation/Film/Film.srt").write_bytes(
                        b"changed"
                    )
                    raise RuntimeError("injected copy failure")
                return self._delegate.copy(source, target, overwrite=overwrite)

        with tempfile.TemporaryDirectory() as root:
            for name in ("source.mkv", "first.srt", "second.srt"):
                Path(root, name).write_bytes(name.encode())
            storage = ChangeBeforeRollback(LocalStorage("local", root))
            result = OrganizerExecutor().execute(
                self._with_attachments(self._plan()), {"local": storage}, execute=True
            )
            self.assertEqual(ExecutionStatus.PARTIAL, result.status)
            self.assertEqual(RollbackStatus.PARTIAL, result.rollback_status)
            self.assertTrue(Path(root, "Movies/Animation/Film/Film.srt").exists())
            self.assertEqual("rollback_safety_error", result.rollback_steps[0].error)

    def test_compensation_delete_failure_is_partial(self):
        class RollbackDeleteFails(_FailSecondCopy):
            def delete(self, path):
                if path.endswith("Film.srt"):
                    raise RuntimeError("injected rollback delete failure")
                return self._delegate.delete(path)

        with tempfile.TemporaryDirectory() as root:
            for name in ("source.mkv", "first.srt", "second.srt"):
                Path(root, name).write_bytes(name.encode())
            storage = RollbackDeleteFails(LocalStorage("local", root))
            result = OrganizerExecutor().execute(
                self._with_attachments(self._plan()), {"local": storage}, execute=True
            )
            self.assertEqual(ExecutionStatus.PARTIAL, result.status)
            self.assertEqual(RollbackStatus.PARTIAL, result.rollback_status)
            self.assertTrue(Path(root, "Movies/Animation/Film/Film.srt").exists())

    def test_rollback_and_overwrite_is_rejected_before_storage_access(self):
        class Exploding:
            def __getattr__(self, name):
                raise AssertionError(f"Storage.{name} was accessed")

        result = OrganizerExecutor().execute(
            replace(self._plan(), overwrite_authorized=True),
            {"local": Exploding()},
            execute=True,
        )
        self.assertEqual(ExecutionStatus.FAILED, result.status)
        self.assertIn("cannot be combined", result.errors[0])

    def test_failure_before_owned_effect_needs_no_rollback(self):
        with tempfile.TemporaryDirectory() as root:
            result = OrganizerExecutor().execute(
                self._plan(), {"local": LocalStorage("local", root)}, execute=True
            )
            self.assertEqual(ExecutionStatus.FAILED, result.status)
            self.assertEqual(RollbackStatus.NOT_NEEDED, result.rollback_status)
            self.assertEqual((), result.rollback_steps)

    def test_c_identity_and_a_policy_reuse_are_unchanged(self):
        plan = self._plan()
        self.assertEqual("C", plan.recognition_type_id)
        self.assertEqual("A", plan.naming_policy_id)
        self.assertEqual("A", plan.classification_policy_id)
        self.assertEqual("A", plan.organize_policy_id)


if __name__ == "__main__":
    unittest.main()
