from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sqlite3
import stat
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
from mediaflow.host_operations import main as host_main
from mediaflow.infrastructure.runtime_configuration import RuntimeConfiguration
from mediaflow.infrastructure.sqlite_backup import SQLiteBackupService
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_restore import SQLiteRestoreService
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from tests.managed_config_fixture import seed_configuration_schema_11_store


def run_host(config: Path, *arguments: str):
    output, error = io.StringIO(), io.StringIO()
    with patch.dict(os.environ, {"MEDIAFLOW_DATA_DIR": str(config.parent)}, clear=False):
        code = host_main(["--config", str(config), *arguments], stdout=output, stderr=error)
    return code, output.getvalue(), error.getvalue()


NOW = datetime(2026, 8, 22, 14, tzinfo=UTC)


class SQLiteRestoreTests(unittest.TestCase):
    def _backup(self, root: Path) -> Path:
        source, backup = root / "original.sqlite3", root / "backup.sqlite3"
        with SQLiteTaskRepository(source) as repository:
            repository.create_task(
                PersistentTask(
                    "task-1", "organize", PersistentTaskStatus.COMPLETED, False, NOW, NOW
                )
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
                    "/api/jobs",
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

    def test_restore_to_missing_runtime_preserves_records_and_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup = self._backup(root)
            destination = root / "restored.sqlite3"
            before = (backup.stat().st_mtime_ns, hashlib.sha256(backup.read_bytes()).hexdigest())
            result = SQLiteRestoreService(backup, destination).restore(
                confirmed_empty_destination=True
            )
            self.assertEqual(result.schema_version, SCHEMA_VERSION)
            self.assertEqual(result.size_bytes, destination.stat().st_size)
            self.assertEqual(result.sha256, hashlib.sha256(destination.read_bytes()).hexdigest())
            self.assertEqual(
                before, (backup.stat().st_mtime_ns, hashlib.sha256(backup.read_bytes()).hexdigest())
            )
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
            with SQLiteTaskRepository(destination) as restored:
                self.assertIsNotNone(restored.get_task("task-1"))
                self.assertEqual(restored.list_results("task-1")[0].recognition_type, "C")
                self.assertEqual(restored.list_security_audit(limit=10)[0].audit_id, "audit-1")
                self.assertEqual(restored.list_operational_logs(limit=10)[0].log_id, "log-1")

    def test_older_schema_backup_is_refused_without_touching_the_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup = self._backup(root)
            with closing(sqlite3.connect(backup)) as connection:
                connection.execute(
                    "UPDATE schema_version SET version=? WHERE component='runtime'",
                    (SCHEMA_VERSION - 1,),
                )
                connection.commit()
            destination = root / "restored.sqlite3"
            with self.assertRaisesRegex(ValueError, "not usable by this MediaFlow version"):
                SQLiteRestoreService(backup, destination).restore(confirmed_empty_destination=True)
            self.assertFalse(destination.exists())
            self.assertEqual(list(root.glob(".mediaflow-restore-*")), [])

    def test_current_configuration_only_store_restores_with_its_source_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "configuration.sqlite3"
            with SQLiteConfigurationRepository(source):
                pass
            backup = root / "configuration-backup.sqlite3"
            SQLiteBackupService(source).backup(backup)
            backup_hash = hashlib.sha256(backup.read_bytes()).hexdigest()
            destination = root / "restored.sqlite3"
            result = SQLiteRestoreService(backup, destination).restore(
                confirmed_empty_destination=True
            )
            self.assertEqual(result.schema_kind, "configuration")
            self.assertEqual(result.source_sha256, backup_hash)
            self.assertEqual(hashlib.sha256(backup.read_bytes()).hexdigest(), backup_hash)
            with SQLiteConfigurationRepository(destination):
                pass

    def test_previous_schema_backup_is_refused_before_any_destination_appears(self) -> None:
        """A backup this version refuses to start is not published to an empty target."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "mediaflow.sqlite3"
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["persistence"] = {"databasePath": str(source)}
            seed_configuration_schema_11_store(document)
            with self.assertRaisesRegex(ValueError, "not usable by this MediaFlow version"):
                SQLiteBackupService(source).backup(root / "unused.sqlite3")
            backup = root / "previous-build.sqlite3"
            backup.write_bytes(source.read_bytes())
            before = (backup.stat().st_mtime_ns, hashlib.sha256(backup.read_bytes()).hexdigest())
            destination = root / "restored.sqlite3"
            with self.assertRaisesRegex(
                ValueError,
                re.compile(
                    r"not usable by this MediaFlow version.*configuration schema was created by "
                    r"a previous MediaFlow version",
                    re.DOTALL,
                ),
            ) as refused:
                SQLiteRestoreService(backup, destination).restore(confirmed_empty_destination=True)
            self.assertIn("found 11, expected 12", str(refused.exception))
            self.assertFalse(destination.exists())
            self.assertEqual(list(root.glob(".mediaflow-restore-*")), [])
            self.assertEqual(
                before, (backup.stat().st_mtime_ns, hashlib.sha256(backup.read_bytes()).hexdigest())
            )

    def test_changed_source_backup_blocks_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup = self._backup(root)
            destination = root / "restored.sqlite3"
            from mediaflow.infrastructure import sqlite_restore

            original_copy = sqlite_restore._copy_database

            def copy_then_change_source(source: Path, target: Path) -> None:
                original_copy(source, target)
                with source.open("ab") as stream:
                    stream.write(b"concurrent writer")

            with patch(
                "mediaflow.infrastructure.sqlite_restore._copy_database",
                side_effect=copy_then_change_source,
            ):
                with self.assertRaisesRegex(ValueError, "source backup changed"):
                    SQLiteRestoreService(backup, destination).restore(
                        confirmed_empty_destination=True
                    )
            self.assertFalse(destination.exists())
            self.assertEqual(list(root.glob(".mediaflow-restore-*")), [])

    def test_restore_refuses_unsafe_destinations_and_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup = self._backup(root)
            destination = root / "restored.sqlite3"
            with self.assertRaisesRegex(ValueError, "confirm-empty-destination"):
                SQLiteRestoreService(backup, destination).restore()
            self.assertFalse(destination.exists())
            destination.write_bytes(b"preserve")
            with self.assertRaisesRegex(ValueError, "must not exist"):
                SQLiteRestoreService(backup, destination).restore(confirmed_empty_destination=True)
            self.assertEqual(destination.read_bytes(), b"preserve")
            destination.unlink()
            destination.mkdir()
            with self.assertRaisesRegex(ValueError, "must not exist"):
                SQLiteRestoreService(backup, destination).restore(confirmed_empty_destination=True)
            destination.rmdir()
            symlink_target = root / "unrelated.sqlite3"
            symlink_target.write_bytes(b"preserve")
            destination.symlink_to(symlink_target)
            with self.assertRaisesRegex(ValueError, "must not exist"):
                SQLiteRestoreService(backup, destination).restore(confirmed_empty_destination=True)
            destination.unlink()
            for suffix in ("-wal", "-shm", "-journal"):
                sidecar = Path(f"{destination}{suffix}")
                sidecar.write_bytes(b"preserve")
                with self.subTest(suffix=suffix), self.assertRaisesRegex(ValueError, "sidecar"):
                    SQLiteRestoreService(backup, destination).restore(
                        confirmed_empty_destination=True
                    )
                self.assertEqual(sidecar.read_bytes(), b"preserve")
                sidecar.unlink()
            with self.assertRaisesRegex(ValueError, "different files"):
                SQLiteRestoreService(backup, backup).restore(confirmed_empty_destination=True)
            with self.assertRaisesRegex(ValueError, "parent"):
                SQLiteRestoreService(backup, root / "missing" / "runtime.sqlite3").restore(
                    confirmed_empty_destination=True
                )
            symlink_parent = root / "linked"
            symlink_parent.symlink_to(root, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "parent"):
                SQLiteRestoreService(backup, symlink_parent / "runtime.sqlite3").restore(
                    confirmed_empty_destination=True
                )
            with self.assertRaisesRegex(ValueError, "invalid"):
                SQLiteRestoreService(backup, "bad\0destination")
            for name, content in (("empty.sqlite3", b""), ("malformed.sqlite3", b"not sqlite")):
                candidate = root / name
                candidate.write_bytes(content)
                with self.subTest(backup=name), self.assertRaises(ValueError):
                    SQLiteRestoreService(candidate, destination).restore(
                        confirmed_empty_destination=True
                    )
                self.assertFalse(destination.exists())
            with self.assertRaisesRegex(ValueError, "existing regular"):
                SQLiteRestoreService(root / "missing.sqlite3", destination).restore(
                    confirmed_empty_destination=True
                )
            newer = root / "newer.sqlite3"
            newer.write_bytes(backup.read_bytes())
            with closing(sqlite3.connect(newer)) as connection:
                connection.execute(
                    "UPDATE schema_version SET version=? WHERE component='runtime'",
                    (SCHEMA_VERSION + 1,),
                )
                connection.commit()
            with self.assertRaisesRegex(ValueError, "newer"):
                SQLiteRestoreService(newer, destination).restore(confirmed_empty_destination=True)

    def test_failures_and_publish_race_clean_only_owned_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup = self._backup(root)
            backup_hash = hashlib.sha256(backup.read_bytes()).hexdigest()
            for helper in ("_copy_database", "_fsync"):
                destination = root / f"{helper}.sqlite3"
                with patch(
                    f"mediaflow.infrastructure.sqlite_restore.{helper}", side_effect=OSError
                ):
                    with self.subTest(helper=helper), self.assertRaises(OSError):
                        SQLiteRestoreService(backup, destination).restore(
                            confirmed_empty_destination=True
                        )
                self.assertFalse(destination.exists())
                self.assertEqual(list(root.glob(".mediaflow-restore-*")), [])
            destination = root / "race.sqlite3"

            def race(_source: Path, target: Path) -> None:
                target.write_bytes(b"winner")
                raise ValueError("runtime database destination appeared during restore")

            with patch("mediaflow.infrastructure.sqlite_restore._publish", side_effect=race):
                with self.assertRaisesRegex(ValueError, "appeared"):
                    SQLiteRestoreService(backup, destination).restore(
                        confirmed_empty_destination=True
                    )
            self.assertEqual(destination.read_bytes(), b"winner")
            self.assertEqual(hashlib.sha256(backup.read_bytes()).hexdigest(), backup_hash)
            self.assertEqual(list(root.glob(".mediaflow-restore-*")), [])

    def test_cli_uses_configured_missing_destination_and_no_storage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup = self._backup(root)
            destination = root / "configured-runtime.sqlite3"
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["persistence"] = {"databasePath": str(destination)}
            config = root / "config.json"
            config.write_text(json.dumps(document), encoding="utf-8")
            code, output, error = run_host(config, "restore", str(backup))
            self.assertEqual(code, 2)
            self.assertIn("confirm-empty-destination", error)
            self.assertFalse(destination.exists())
            with patch.object(
                RuntimeConfiguration,
                "create_storages",
                side_effect=AssertionError("Storage must not be constructed"),
            ):
                code, output, error = run_host(
                    config, "restore", str(backup), "--confirm-empty-destination"
                )
            self.assertEqual(code, 0, error)
            self.assertTrue(destination.exists())
            self.assertIn("Status: RESTORED", output)
            self.assertNotIn("token", output.lower())


if __name__ == "__main__":
    unittest.main()
