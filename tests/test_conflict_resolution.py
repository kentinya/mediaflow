from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from mediaflow.application.conflict_resolution import (
    ConfirmationService,
    ConflictResolutionError,
    ConflictResolver,
)
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.organizer import (
    Conflict,
    ConflictStrategy,
    ConflictType,
    DuplicateIdentity,
    OrganizeOperationType,
    OrganizePlan,
    OrganizePolicy,
    PlanOperation,
    PlanStatus,
    StorageLocation,
)
from mediaflow.domain.task_persistence import ConfirmationStatus, TaskItemStatus
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.infrastructure.strategy_user_configuration import load_strategy_configuration


class ReadOnlyExistsStorage:
    def __init__(self, existing: tuple[str, ...] = ()) -> None:
        self.existing = set(existing)
        self.mutations = 0

    def exists(self, path: str) -> bool:
        return path in self.existing

    def __getattr__(self, name: str):
        if name in {
            "write",
            "create_directory",
            "move",
            "copy",
            "delete",
            "hard_link",
            "soft_link",
        }:
            self.mutations += 1
            raise AssertionError(f"unexpected mutation: {name}")
        raise AttributeError(name)


def conflicted_plan(conflict_type: ConflictType = ConflictType.DESTINATION_EXISTS) -> OrganizePlan:
    target = "Movies/Film/Film.mkv"
    return OrganizePlan(
        "source",
        "target",
        "Incoming/Film.mkv",
        target,
        "C",
        "A",
        "A",
        "A",
        operation=PlanOperation.MOVE,
        conflicts=(Conflict(conflict_type, "Incoming/Film.mkv", target, "test"),),
        status=PlanStatus.CONFLICT,
        plan_id="plan-1",
        media_library_root="Movies",
        relative_destination="Film/Film.mkv",
        source_location=StorageLocation("source", "Incoming/Film.mkv"),
        destination_location=StorageLocation("target", target),
    )


class ConflictResolutionTests(unittest.TestCase):
    def test_configuration_controls_all_conflict_strategies(self) -> None:
        base = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        for strategy in ConflictStrategy:
            document = json.loads(json.dumps(base))
            document["organizePolicies"][0]["conflictStrategy"] = strategy.value
            document["organizePolicies"][0]["overwrite"] = strategy is ConflictStrategy.OVERWRITE
            loaded = load_strategy_configuration(document, require_complete=True)
            self.assertEqual(loaded.strategy.organize_policies[0].conflict_strategy, strategy)
        invalid = json.loads(json.dumps(base))
        invalid["organizePolicies"][0].update({"conflictStrategy": "rename", "overwrite": True})
        with self.assertRaisesRegex(ValueError, "conflicts"):
            load_strategy_configuration(invalid, require_complete=True)

    def test_skip_and_deterministic_rename_are_read_only(self) -> None:
        storage = ReadOnlyExistsStorage(("Movies/Film/Film (1).mkv",))
        resolver = ConflictResolver()
        skipped = resolver.apply_configured(
            conflicted_plan(),
            OrganizePolicy("A", OrganizeOperationType.MOVE, ConflictStrategy.SKIP),
            storage,
        )
        self.assertEqual(skipped.operation, PlanOperation.SKIP)
        renamed = resolver.apply_configured(
            conflicted_plan(),
            OrganizePolicy("A", OrganizeOperationType.MOVE, ConflictStrategy.RENAME),
            storage,
        )
        self.assertEqual(renamed.target, "Movies/Film/Film (2).mkv")
        self.assertEqual(renamed.status, PlanStatus.READY)
        self.assertEqual(storage.mutations, 0)

    def test_manual_waits_and_invalid_destination_cannot_be_overridden(self) -> None:
        storage = ReadOnlyExistsStorage()
        resolver = ConflictResolver()
        self.assertIsNone(
            resolver.apply_configured(
                conflicted_plan(),
                OrganizePolicy("A", OrganizeOperationType.MOVE, ConflictStrategy.MANUAL),
                storage,
            )
        )
        self.assertIsNone(
            resolver.apply_configured(
                conflicted_plan(ConflictType.INVALID_DESTINATION),
                OrganizePolicy("A", OrganizeOperationType.MOVE, ConflictStrategy.RENAME),
                storage,
            )
        )

    def test_overwrite_requires_policy_and_fresh_confirmation(self) -> None:
        plan = conflicted_plan()
        resolver = ConflictResolver()
        policy = OrganizePolicy("A", OrganizeOperationType.MOVE, ConflictStrategy.OVERWRITE)
        with self.assertRaisesRegex(ConflictResolutionError, "explicit"):
            resolver.overwrite(plan, policy, confirmed=False)
        resolved = resolver.overwrite(plan, policy, confirmed=True)
        self.assertTrue(resolved.overwrite_authorized)
        self.assertEqual(resolved.conflicts, ())
        with self.assertRaisesRegex(ConflictResolutionError, "does not allow"):
            resolver.overwrite(
                plan,
                OrganizePolicy("A", OrganizeOperationType.MOVE, ConflictStrategy.MANUAL),
                confirmed=True,
            )

    def test_executor_uses_explicit_overwrite_authority_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Incoming").mkdir()
            (root / "Movies" / "Film").mkdir(parents=True)
            (root / "Incoming" / "Film.mkv").write_bytes(b"new")
            (root / "Movies" / "Film" / "Film.mkv").write_bytes(b"old")
            storage = LocalStorage("local", root)
            plan = replace(
                conflicted_plan(),
                source_storage_id="local",
                target_storage_id="local",
                source_location=StorageLocation("local", "Incoming/Film.mkv"),
                destination_location=StorageLocation("local", "Movies/Film/Film.mkv"),
            )
            resolved = ConflictResolver().overwrite(
                plan,
                OrganizePolicy("A", OrganizeOperationType.MOVE, ConflictStrategy.OVERWRITE),
                confirmed=True,
            )
            result = OrganizerExecutor().execute(resolved, {"local": storage}, execute=True)
            self.assertEqual(result.status.value, "SUCCESS")
            self.assertEqual((root / "Movies" / "Film" / "Film.mkv").read_bytes(), b"new")
            self.assertFalse((root / "Incoming" / "Film.mkv").exists())

    def test_confirmation_persists_audit_and_waiting_item_across_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.begin_item(
                    task.task_id, "source", "movies", "Film.mkv", "Film.mkv"
                )
                policy = OrganizePolicy("A", OrganizeOperationType.MOVE, ConflictStrategy.OVERWRITE)
                coordinator.wait_for_confirmation(item, conflicted_plan(), policy)
                waiting = repository.get_item(item.item_id)
                self.assertEqual(waiting.status, TaskItemStatus.WAITING_CONFIRM)
                self.assertEqual(coordinator.retryable_items(task.task_id, failed_only=False), ())
                confirmation = repository.list_confirmations()[0]
                with self.assertRaisesRegex(ConflictResolutionError, "confirm-overwrite"):
                    ConfirmationService(repository).resolve(
                        confirmation.confirmation_id, ConflictStrategy.OVERWRITE
                    )
                ConfirmationService(repository).resolve(
                    confirmation.confirmation_id,
                    ConflictStrategy.OVERWRITE,
                    confirm_overwrite=True,
                    actor="tester",
                    note="reviewed",
                )
            with SQLiteTaskRepository(database) as reopened:
                value = reopened.get_confirmation(confirmation.confirmation_id)
                self.assertEqual(value.status, ConfirmationStatus.RESOLVED)
                self.assertTrue(value.overwrite_authorized)
                audit = reopened.list_confirmation_audit(value.confirmation_id)
                self.assertEqual(audit[0].actor, "tester")
                self.assertEqual(reopened.schema_version, SCHEMA_VERSION)

    def test_schema_one_database_migrates_forward(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            connection = sqlite3.connect(database)
            connection.execute(
                "CREATE TABLE schema_version (component TEXT PRIMARY KEY, version INTEGER NOT NULL)"
            )
            connection.execute("INSERT INTO schema_version VALUES ('runtime', 1)")
            connection.commit()
            connection.close()
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(repository.schema_version, SCHEMA_VERSION)
                self.assertEqual(repository.list_confirmations(), ())

    def test_duplicate_identity_includes_tv_episode_scope(self) -> None:
        from mediaflow.domain.metadata import MediaIdentity, MediaType

        first = MediaIdentity("tmdb", "99", MediaType.TV, "Show", season=1, episodes=(1, 2))
        second = replace(first, episodes=(3,))
        self.assertNotEqual(
            DuplicateIdentity.from_media_identity(first),
            DuplicateIdentity.from_media_identity(second),
        )

    def test_cli_confirmation_commands_are_persistence_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["persistence"] = {"databasePath": str(root / "runtime.sqlite3")}
            config = root / "config.json"
            config.write_text(json.dumps(document), encoding="utf-8")
            with SQLiteTaskRepository(root / "runtime.sqlite3") as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("preview", execute_authorized=False)
                item = coordinator.begin_item(
                    task.task_id, "source", "movies", "Film.mkv", "Film.mkv"
                )
                coordinator.wait_for_confirmation(
                    item,
                    conflicted_plan(),
                    OrganizePolicy("A", OrganizeOperationType.MOVE, ConflictStrategy.MANUAL),
                )
                confirmation_id = repository.list_confirmations()[0].confirmation_id
            output, errors = io.StringIO(), io.StringIO()
            self.assertEqual(
                final_main(
                    ["--config", str(config), "confirmations", "list"],
                    stdout=output,
                    stderr=errors,
                ),
                0,
            )
            self.assertIn(confirmation_id, output.getvalue())
            output, errors = io.StringIO(), io.StringIO()
            self.assertEqual(
                final_main(
                    [
                        "--config",
                        str(config),
                        "confirmations",
                        "resolve",
                        confirmation_id,
                        "--strategy",
                        "skip",
                        "--actor",
                        "tester",
                    ],
                    stdout=output,
                    stderr=errors,
                ),
                0,
                errors.getvalue(),
            )
            with SQLiteTaskRepository(root / "runtime.sqlite3") as repository:
                self.assertEqual(repository.get_item(item.item_id).status, TaskItemStatus.SKIPPED)
