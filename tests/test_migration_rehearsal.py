from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from mediaflow.domain.logging import LogLevel, OperationalLogRecord
from mediaflow.domain.security import SecurityAuditRecord
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskStatus,
)
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.migration_rehearsal import SQLiteMigrationRehearsalService
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_backup import SQLiteBackupService
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository

NOW = datetime(2026, 8, 22, 15, tzinfo=UTC)


class MigrationRehearsalTests(unittest.TestCase):
    def _backup(self, root: Path) -> Path:
        source, backup = root / "source.sqlite3", root / "backup.sqlite3"
        with SQLiteTaskRepository(source) as repository:
            repository.create_task(
                PersistentTask("task-1", "preview", PersistentTaskStatus.COMPLETED, False, NOW, NOW)
            )
            repository.append_result(
                PersistentResultRecord(
                    "result-1",
                    "task-1",
                    "item-1",
                    "source",
                    "movie.mkv",
                    None,
                    None,
                    "C",
                    "tmdb",
                    "1",
                    "C",
                    "A",
                    "A",
                    "A",
                    "COPY",
                    "dry_run",
                    NOW,
                )
            )
            repository.append_security_audit(
                SecurityAuditRecord(
                    "audit-1",
                    NOW,
                    "operator",
                    "GET",
                    "/api/v1/jobs",
                    "list",
                    "allowed",
                    200,
                    "request-1",
                )
            )
            repository.append_operational_log(
                OperationalLogRecord("log-1", NOW, LogLevel.INFO, "workflow", "scan.completed")
            )
        SQLiteBackupService(source).backup(backup)
        return backup

    def test_current_and_older_schema_rehearsal_preserve_records_and_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup = self._backup(root)
            original = (backup.stat().st_mtime_ns, hashlib.sha256(backup.read_bytes()).hexdigest())
            current = SQLiteMigrationRehearsalService(backup).rehearse()
            self.assertEqual((current.source_schema, current.target_schema), (SCHEMA_VERSION,) * 2)
            self.assertFalse(current.migration_required)
            self.assertFalse(current.migration_performed)
            self.assertEqual(
                dict(current.record_counts),
                {"tasks": 1, "task_results": 1, "security_audit": 1, "operational_logs": 1},
            )
            with closing(sqlite3.connect(backup)) as connection:
                connection.execute(
                    "UPDATE schema_version SET version=? WHERE component='runtime'",
                    (SCHEMA_VERSION - 1,),
                )
                connection.commit()
            older_hash = hashlib.sha256(backup.read_bytes()).hexdigest()
            older = SQLiteMigrationRehearsalService(backup).rehearse()
            self.assertEqual(older.source_schema, SCHEMA_VERSION - 1)
            self.assertEqual(older.target_schema, SCHEMA_VERSION)
            self.assertTrue(older.migration_required)
            self.assertTrue(older.migration_performed)
            self.assertEqual(hashlib.sha256(backup.read_bytes()).hexdigest(), older_hash)
            self.assertNotEqual(original[1], older_hash)
            self.assertEqual(list(root.glob(".mediaflow-migration-rehearsal-*")), [])

    def test_invalid_backups_fail_without_rehearsal_residue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, content in (("empty.sqlite3", b""), ("bad.sqlite3", b"not sqlite")):
                backup = root / name
                backup.write_bytes(content)
                with self.subTest(name=name), self.assertRaises(ValueError):
                    SQLiteMigrationRehearsalService(backup).rehearse()
            with self.assertRaisesRegex(ValueError, "existing regular"):
                SQLiteMigrationRehearsalService(root / "missing.sqlite3").rehearse()
            with self.assertRaisesRegex(ValueError, "invalid"):
                SQLiteMigrationRehearsalService("bad\0backup")
            target = root / "target.sqlite3"
            target.write_bytes(b"data")
            symlink = root / "link.sqlite3"
            symlink.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "non-symlink"):
                SQLiteMigrationRehearsalService(symlink).rehearse()
            backup = self._backup(root)
            linked_parent = root / "linked-parent"
            linked_parent.symlink_to(root, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "parent"):
                SQLiteMigrationRehearsalService(linked_parent / backup.name).rehearse()
            with closing(sqlite3.connect(backup)) as connection:
                connection.execute(
                    "UPDATE schema_version SET version=? WHERE component='runtime'",
                    (SCHEMA_VERSION + 1,),
                )
                connection.commit()
            with self.assertRaisesRegex(ValueError, "newer"):
                SQLiteMigrationRehearsalService(backup).rehearse()
            self.assertEqual(list(root.glob(".mediaflow-migration-rehearsal-*")), [])

    def test_copy_and_migration_failures_clean_temporary_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup = self._backup(root)
            digest = hashlib.sha256(backup.read_bytes()).hexdigest()
            with patch(
                "mediaflow.infrastructure.migration_rehearsal._copy_database",
                side_effect=OSError("copy failed token=secret"),
            ):
                with self.assertRaisesRegex(OSError, "copy failed"):
                    SQLiteMigrationRehearsalService(backup).rehearse()
            with patch(
                "mediaflow.infrastructure.migration_rehearsal.SQLiteTaskRepository",
                side_effect=RuntimeError("migration failed token=secret"),
            ):
                with self.assertRaisesRegex(RuntimeError, "migration failed"):
                    SQLiteMigrationRehearsalService(backup).rehearse()
            self.assertEqual(hashlib.sha256(backup.read_bytes()).hexdigest(), digest)
            self.assertEqual(list(root.glob(".mediaflow-migration-rehearsal-*")), [])

    def test_cli_uses_copy_only_holds_shared_lease_and_constructs_no_storage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup = self._backup(root)
            runtime = root / "runtime.sqlite3"
            with SQLiteTaskRepository(runtime):
                pass
            runtime_before = (
                runtime.stat().st_mtime_ns,
                runtime.stat().st_size,
                hashlib.sha256(runtime.read_bytes()).hexdigest(),
            )
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["persistence"] = {"databasePath": str(runtime)}
            config = root / "config.json"
            config.write_text(json.dumps(document), encoding="utf-8")
            output, error = io.StringIO(), io.StringIO()
            original_repository = SQLiteTaskRepository

            def copy_repository(path):
                self.assertNotEqual(Path(path).resolve(), runtime.resolve())
                return original_repository(path)

            with (
                patch.object(
                    RuntimeConfiguration,
                    "create_storages",
                    side_effect=AssertionError("Storage must not be constructed"),
                ),
                patch(
                    "mediaflow.infrastructure.migration_rehearsal.SQLiteTaskRepository",
                    side_effect=copy_repository,
                ),
            ):
                code = final_main(
                    ["--config", str(config), "upgrade", "rehearse", "--backup", str(backup)],
                    stdout=output,
                    stderr=error,
                )
            self.assertEqual(code, 0, error.getvalue())
            self.assertIn("Status: PASS", output.getvalue())
            self.assertNotIn("token", output.getvalue().lower())
            self.assertEqual(
                runtime_before,
                (
                    runtime.stat().st_mtime_ns,
                    runtime.stat().st_size,
                    hashlib.sha256(runtime.read_bytes()).hexdigest(),
                ),
            )


if __name__ == "__main__":
    unittest.main()
