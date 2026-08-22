from __future__ import annotations

import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_lease import (
    RuntimeDatabaseLease,
    RuntimeLeaseMode,
    RuntimeLeaseUnavailable,
)
from mediaflow.infrastructure.sqlite_backup import SQLiteBackupService
from mediaflow.infrastructure.sqlite_restore import SQLiteRestoreService
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository


@unittest.skipUnless(os.name == "posix", "POSIX advisory lock regression")
class RuntimeLeaseTests(unittest.TestCase):
    def _configuration(self, root: Path, database: Path) -> Path:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        document["persistence"] = {"databasePath": str(database)}
        config = root / f"config-{database.stem}.json"
        config.write_text(json.dumps(document), encoding="utf-8")
        return config

    def test_shared_exclusive_contention_release_and_file_safety(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            shared_one = RuntimeDatabaseLease(database, RuntimeLeaseMode.SHARED).acquire()
            shared_two = RuntimeDatabaseLease(database, RuntimeLeaseMode.SHARED).acquire()
            lock_path = shared_one.path
            self.assertEqual(lock_path.read_bytes(), b"")
            self.assertEqual(stat.S_IMODE(lock_path.stat().st_mode), 0o600)
            with self.assertRaisesRegex(RuntimeLeaseUnavailable, "another MediaFlow process"):
                RuntimeDatabaseLease(database, RuntimeLeaseMode.EXCLUSIVE).acquire()
            shared_two.close()
            shared_one.close()
            with RuntimeDatabaseLease(database, RuntimeLeaseMode.EXCLUSIVE):
                with self.assertRaises(RuntimeLeaseUnavailable):
                    RuntimeDatabaseLease(database, RuntimeLeaseMode.EXCLUSIVE).acquire()
                with self.assertRaises(RuntimeLeaseUnavailable):
                    RuntimeDatabaseLease(database, RuntimeLeaseMode.SHARED).acquire()
            with RuntimeDatabaseLease(database, RuntimeLeaseMode.SHARED):
                pass
            self.assertTrue(lock_path.exists())
            self.assertEqual(lock_path.read_bytes(), b"")

    def test_exception_subprocess_exit_and_invalid_lock_paths_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "runtime.sqlite3"
            with self.assertRaisesRegex(RuntimeError, "unwind"):
                with RuntimeDatabaseLease(database, RuntimeLeaseMode.EXCLUSIVE):
                    raise RuntimeError("unwind")
            with RuntimeDatabaseLease(database, RuntimeLeaseMode.EXCLUSIVE):
                pass
            script = (
                "import sys; from mediaflow.infrastructure.runtime_lease import "
                "RuntimeDatabaseLease,RuntimeLeaseMode; "
                "lease=RuntimeDatabaseLease(sys.argv[1],RuntimeLeaseMode.SHARED).acquire(); "
                "print('READY',flush=True); input()"
            )
            with subprocess.Popen(
                [sys.executable, "-c", script, str(database)],
                cwd=Path.cwd(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            ) as process:
                assert process.stdout is not None
                self.assertEqual(process.stdout.readline().strip(), "READY")
                with self.assertRaises(RuntimeLeaseUnavailable):
                    RuntimeDatabaseLease(database, RuntimeLeaseMode.EXCLUSIVE).acquire()
                process.kill()
                process.communicate(timeout=5)
            with RuntimeDatabaseLease(database, RuntimeLeaseMode.EXCLUSIVE):
                pass
            lock_path = RuntimeDatabaseLease(database, RuntimeLeaseMode.SHARED).path
            lock_path.unlink()
            lock_path.symlink_to(root / "elsewhere")
            with self.assertRaisesRegex(ValueError, "non-symlink"):
                RuntimeDatabaseLease(database, RuntimeLeaseMode.SHARED).acquire()
            lock_path.unlink()
            lock_path.mkdir()
            with self.assertRaisesRegex(ValueError, "regular"):
                RuntimeDatabaseLease(database, RuntimeLeaseMode.SHARED).acquire()
            with self.assertRaisesRegex(ValueError, "parent"):
                RuntimeDatabaseLease(
                    root / "missing" / "runtime.sqlite3", RuntimeLeaseMode.SHARED
                ).acquire()

    def test_cli_holds_shared_and_restore_exclusive_with_fail_fast_contention(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.sqlite3"
            backup = root / "backup.sqlite3"
            with SQLiteTaskRepository(source):
                pass
            SQLiteBackupService(source).backup(backup)
            config = self._configuration(root, source)
            original_verify = SQLiteBackupService.verify

            def verify_with_observation(service, candidate, **kwargs):
                with self.assertRaises(RuntimeLeaseUnavailable):
                    RuntimeDatabaseLease(source, RuntimeLeaseMode.EXCLUSIVE).acquire()
                return original_verify(service, candidate, **kwargs)

            with patch.object(SQLiteBackupService, "verify", new=verify_with_observation):
                code = final_main(
                    ["--config", str(config), "database", "verify", str(backup)],
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )
            self.assertEqual(code, 0)

            destination = root / "restored.sqlite3"
            restore_config = self._configuration(root, destination)
            with RuntimeDatabaseLease(destination, RuntimeLeaseMode.SHARED):
                error = io.StringIO()
                code = final_main(
                    [
                        "--config",
                        str(restore_config),
                        "database",
                        "restore",
                        str(backup),
                        "--confirm-empty-destination",
                    ],
                    stdout=io.StringIO(),
                    stderr=error,
                )
                self.assertEqual(code, 2)
                self.assertIn("another MediaFlow process", error.getvalue())
                self.assertFalse(destination.exists())
                self.assertEqual(list(root.glob(".mediaflow-restore-*")), [])
            original_restore = SQLiteRestoreService.restore

            def restore_with_observation(service, **kwargs):
                with self.assertRaises(RuntimeLeaseUnavailable):
                    RuntimeDatabaseLease(destination, RuntimeLeaseMode.SHARED).acquire()
                return original_restore(service, **kwargs)

            with patch.object(SQLiteRestoreService, "restore", new=restore_with_observation):
                code = final_main(
                    [
                        "--config",
                        str(restore_config),
                        "database",
                        "restore",
                        str(backup),
                        "--confirm-empty-destination",
                    ],
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )
            self.assertEqual(code, 0)

    def test_exempt_commands_and_missing_confirmation_create_no_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "runtime.sqlite3"
            config = self._configuration(root, database)
            lock_path = RuntimeDatabaseLease(database, RuntimeLeaseMode.SHARED).path
            for arguments in (
                ["--config", str(config), "config", "validate"],
                ["api", "token", "generate"],
                ["--config", str(config), "api", "credentials", "check"],
                ["--config", str(config), "storage", "list"],
            ):
                with self.subTest(arguments=arguments):
                    final_main(arguments, stdout=io.StringIO(), stderr=io.StringIO())
                    self.assertFalse(lock_path.exists())
            error = io.StringIO()
            code = final_main(
                ["--config", str(config), "database", "restore", str(root / "backup.sqlite3")],
                stdout=io.StringIO(),
                stderr=error,
            )
            self.assertEqual(code, 2)
            self.assertFalse(lock_path.exists())


if __name__ == "__main__":
    unittest.main()
