from __future__ import annotations

import hashlib
import io
import json
import os
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
from mediaflow.infrastructure.sqlite_backup import SQLiteBackupService
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository

NOW = datetime(2026, 8, 22, 12, tzinfo=UTC)


class SQLiteBackupTests(unittest.TestCase):
    def test_online_backup_is_complete_verified_and_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "runtime.sqlite3", root / "backup.sqlite3"
            with SQLiteTaskRepository(source) as repository:
                repository._connection.execute("PRAGMA journal_mode=WAL")
                repository.create_task(
                    PersistentTask(
                        "task-1", "preview", PersistentTaskStatus.COMPLETED, False, NOW, NOW
                    )
                )
                repository.append_operational_log(
                    OperationalLogRecord("log-1", NOW, LogLevel.INFO, "workflow", "scan.completed")
                )
                repository.append_result(
                    PersistentResultRecord(
                        "result-1",
                        "task-1",
                        "item-1",
                        "source",
                        "movie.mkv",
                        "destination",
                        "Movies/movie.mkv",
                        "A",
                        "tmdb",
                        "1",
                        "A",
                        "A",
                        "A",
                        "A",
                        "COPY",
                        "success",
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
                result = SQLiteBackupService(source).backup(target)
                repository.create_task(
                    PersistentTask(
                        "task-after", "preview", PersistentTaskStatus.COMPLETED, False, NOW, NOW
                    )
                )
            self.assertEqual(result.schema_version, SCHEMA_VERSION)
            self.assertEqual(result.size_bytes, target.stat().st_size)
            self.assertEqual(result.sha256, hashlib.sha256(target.read_bytes()).hexdigest())
            with SQLiteTaskRepository(target) as backup:
                self.assertIsNotNone(backup.get_task("task-1"))
                self.assertIsNone(backup.get_task("task-after"))
                self.assertEqual(backup.list_operational_logs(limit=10)[0].log_id, "log-1")
                self.assertEqual(backup.list_results("task-1")[0].result_id, "result-1")
                self.assertEqual(backup.list_security_audit(limit=10)[0].audit_id, "audit-1")
            original = target.read_bytes()
            with self.assertRaisesRegex(ValueError, "already exists"):
                SQLiteBackupService(source).backup(target)
            self.assertEqual(target.read_bytes(), original)
            with self.assertRaisesRegex(ValueError, "differ"):
                SQLiteBackupService(source).backup(source)

    def test_verify_is_read_only_and_rejects_invalid_databases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "runtime.sqlite3", root / "backup.sqlite3"
            with SQLiteTaskRepository(source):
                pass
            SQLiteBackupService(source).backup(target)
            before = (target.stat().st_mtime_ns, hashlib.sha256(target.read_bytes()).hexdigest())
            result = SQLiteBackupService(source).verify(target)
            after = (target.stat().st_mtime_ns, hashlib.sha256(target.read_bytes()).hexdigest())
            self.assertEqual(before, after)
            self.assertEqual(result.schema_version, SCHEMA_VERSION)
            self.assertFalse(Path(str(target) + "-wal").exists())
            for name, content in (("empty", b""), ("bad", b"not sqlite")):
                candidate = root / name
                candidate.write_bytes(content)
                with self.subTest(name=name), self.assertRaises(ValueError):
                    SQLiteBackupService(source).verify(candidate)
            missing_schema = root / "other.sqlite3"
            sqlite3.connect(missing_schema).close()
            with self.assertRaisesRegex(ValueError, "schema marker"):
                SQLiteBackupService(source).verify(missing_schema)
            newer = root / "newer.sqlite3"
            with closing(sqlite3.connect(newer)) as connection:
                connection.execute("CREATE TABLE schema_version (component TEXT, version INTEGER)")
                connection.execute(
                    "INSERT INTO schema_version VALUES ('runtime', ?)", (SCHEMA_VERSION + 1,)
                )
                connection.commit()
            with self.assertRaisesRegex(ValueError, "newer"):
                SQLiteBackupService(source).verify(newer)

    def test_target_validation_and_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "runtime.sqlite3"
            with self.assertRaisesRegex(ValueError, "does not exist"):
                SQLiteBackupService(root / "missing.sqlite3").backup(root / "unused.sqlite3")
            with self.assertRaisesRegex(ValueError, "invalid"):
                SQLiteBackupService("bad\0source")
            with SQLiteTaskRepository(source):
                pass
            service = SQLiteBackupService(source)
            with self.assertRaisesRegex(ValueError, "parent"):
                service.backup(root / "missing" / "backup.sqlite3")
            directory_target = root / "directory"
            directory_target.mkdir()
            with self.assertRaises(ValueError):
                service.backup(directory_target)
            symlink = root / "link.sqlite3"
            symlink.symlink_to(source)
            with self.assertRaises(ValueError):
                service.backup(symlink)

            failed_target = root / "publish-failed.sqlite3"
            with patch(
                "mediaflow.infrastructure.sqlite_backup.os.link", side_effect=PermissionError
            ):
                with self.assertRaises(PermissionError):
                    service.backup(failed_target)
            self.assertFalse(failed_target.exists())
            self.assertEqual(list(root.glob(".mediaflow-backup-*")), [])

            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["persistence"] = {"databasePath": str(source)}
            config = root / "config.json"
            config.write_text(json.dumps(document), encoding="utf-8")
            output, error = io.StringIO(), io.StringIO()
            backup = root / "cli-backup.sqlite3"
            code = final_main(
                ["--config", str(config), "database", "backup", "--output", str(backup)],
                stdout=output,
                stderr=error,
            )
            self.assertEqual(code, 0, error.getvalue())
            self.assertIn("DATABASE BACKUP", output.getvalue())
            output = io.StringIO()
            code = final_main(
                ["--config", str(config), "database", "verify", str(backup)],
                stdout=output,
                stderr=error,
            )
            self.assertEqual(code, 0, error.getvalue())
            self.assertIn("DATABASE VERIFY", output.getvalue())
            self.assertEqual(os.stat(source).st_size > 0, True)


if __name__ == "__main__":
    unittest.main()
