from __future__ import annotations

import hashlib
import io
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_backup import SQLiteBackupService
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.infrastructure.upgrade_preflight import UpgradePreflightService


class UpgradePreflightTests(unittest.TestCase):
    def _databases(self, root: Path) -> tuple[Path, Path, datetime]:
        source = root / "runtime.sqlite3"
        backup = root / "backup.sqlite3"
        with SQLiteTaskRepository(source):
            pass
        SQLiteBackupService(source).backup(backup)
        now = datetime.fromtimestamp(backup.stat().st_mtime, UTC) + timedelta(minutes=1)
        return source, backup, now

    def test_ready_preflight_is_read_only_and_reports_safe_compatibility(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, backup, now = self._databases(root)
            before = {
                path: (
                    path.stat().st_mtime_ns,
                    path.stat().st_size,
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
                for path in (source, backup)
            }
            result = UpgradePreflightService(
                source,
                clock=lambda: now,
                application_version="1.2.3",
                python_version=(3, 13, 5),
            ).check(backup)
            self.assertEqual(result.status, "ready")
            self.assertEqual(result.application_version, "1.2.3")
            self.assertEqual(result.python_version, "3.13.5")
            self.assertEqual(result.runtime_schema, SCHEMA_VERSION)
            self.assertEqual(result.backup_schema, SCHEMA_VERSION)
            self.assertFalse(result.migration_required)
            after = {
                path: (
                    path.stat().st_mtime_ns,
                    path.stat().st_size,
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
                for path in (source, backup)
            }
            self.assertEqual(before, after)
            for path in (source, backup):
                self.assertFalse(Path(f"{path}-wal").exists())
                self.assertFalse(Path(f"{path}-shm").exists())
            self.assertNotIn("secret", repr(result).lower())

    def test_older_matching_schema_is_reported_without_migration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, backup, now = self._databases(root)
            for path in (source, backup):
                with closing(sqlite3.connect(path)) as connection:
                    connection.execute(
                        "UPDATE schema_version SET version=? WHERE component='runtime'",
                        (SCHEMA_VERSION - 1,),
                    )
                    connection.commit()
            before = tuple(path.read_bytes() for path in (source, backup))
            result = UpgradePreflightService(source, clock=lambda: now).check(backup)
            self.assertEqual(result.status, "migration_required")
            self.assertTrue(result.migration_required)
            self.assertEqual(result.runtime_schema, SCHEMA_VERSION - 1)
            self.assertEqual(before, tuple(path.read_bytes() for path in (source, backup)))

    def test_incompatible_paths_versions_and_freshness_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, backup, now = self._databases(root)
            service = UpgradePreflightService(source, clock=lambda: now)
            with self.assertRaisesRegex(ValueError, "different files"):
                service.check(source)
            for invalid in (0, -1, float("inf"), 24 * 366):
                with self.subTest(age=invalid), self.assertRaisesRegex(ValueError, "maximum"):
                    service.check(backup, maximum_backup_age_hours=invalid)
            with self.assertRaisesRegex(ValueError, "not supported"):
                UpgradePreflightService(
                    source, clock=lambda: now, python_version=(3, 10, 14)
                ).check(backup)
            os.utime(backup, (now.timestamp() + 60, now.timestamp() + 60))
            with self.assertRaisesRegex(ValueError, "future"):
                service.check(backup)
            stale = now - timedelta(hours=25)
            os.utime(backup, (stale.timestamp(), stale.timestamp()))
            with self.assertRaisesRegex(ValueError, "stale"):
                service.check(backup)
            os.utime(backup, (now.timestamp(), now.timestamp()))
            with closing(sqlite3.connect(backup)) as connection:
                connection.execute(
                    "UPDATE schema_version SET version=? WHERE component='runtime'",
                    (SCHEMA_VERSION - 1,),
                )
                connection.commit()
            with self.assertRaisesRegex(ValueError, "schema versions differ"):
                service.check(backup)
            with self.assertRaisesRegex(ValueError, "existing regular"):
                service.check(root / "missing.sqlite3")
            malformed = root / "malformed.sqlite3"
            malformed.write_bytes(b"token=should-not-appear")
            with self.assertRaisesRegex(ValueError, "valid MediaFlow"):
                service.check(malformed)

    def test_cli_uses_configured_database_without_storage_construction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, backup, _ = self._databases(root)
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["persistence"] = {"databasePath": str(source)}
            config = root / "config.json"
            config.write_text(json.dumps(document), encoding="utf-8")
            output, error = io.StringIO(), io.StringIO()
            with patch.object(
                RuntimeConfiguration,
                "create_storages",
                side_effect=AssertionError("Storage must not be constructed"),
            ):
                code = final_main(
                    ["--config", str(config), "upgrade", "check", "--backup", str(backup)],
                    stdout=output,
                    stderr=error,
                )
            self.assertEqual(code, 0, error.getvalue())
            self.assertIn("Status: READY", output.getvalue())
            self.assertNotIn("token", output.getvalue().lower())
            error = io.StringIO()
            code = final_main(
                [
                    "--config",
                    str(config),
                    "upgrade",
                    "check",
                    "--backup",
                    str(backup),
                    "--max-backup-age-hours",
                    "0",
                ],
                stdout=io.StringIO(),
                stderr=error,
            )
            self.assertEqual(code, 2)
            self.assertIn("maximum backup age", error.getvalue())


if __name__ == "__main__":
    unittest.main()
