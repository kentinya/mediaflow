from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import stat
import tempfile
import unittest
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.configuration_management import RuntimeSnapshotUnavailable
from mediaflow.domain.logging import LogLevel, OperationalLogRecord
from mediaflow.domain.security import (
    ApiPermission,
    ResolvedApiPrincipal,
    SecurityAuditRecord,
)
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
from mediaflow.interfaces.service_api import MediaFlowApi
from mediaflow.runtime_support import resolve_configuration
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


class RestoredDeploymentConsumptionTests(unittest.TestCase):
    """The explicit host restore must leave published authority consumable."""

    def _document(self, root: Path, database: Path) -> dict:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        document.pop("_examples", None)
        document["persistence"] = {"databasePath": str(database)}
        document["historyPath"] = str(root / "history.jsonl")
        incoming = root / "incoming"
        organized = root / "organized"
        incoming.mkdir()
        (organized / "Movies").mkdir(parents=True)
        (organized / "TV Shows").mkdir()
        (incoming / "Movie.2001.mkv").write_bytes(b"media")
        document["storages"][0]["rootPath"] = str(incoming)
        document["storages"][0]["readOnly"] = True
        document["storages"][1]["rootPath"] = str(organized)
        document["storages"][1]["readOnly"] = False
        document["resourceLibraries"][0]["storagePath"] = ""
        document["resourceLibraries"][0]["displayRootPath"] = str(incoming)
        return document

    def _activate(self, service, document):
        draft = service.import_draft(document, actor="tester")
        validated = service.validate(draft.revision_id, actor="tester")
        self.assertEqual(validated.status.value, "validated", validated.validation_errors)
        return service.activate(
            validated.revision_id, expected_version=validated.version, actor="tester"
        )

    @staticmethod
    def _write_bootstrap(path: Path, database: Path) -> None:
        path.write_text(
            json.dumps({"version": 1, "persistence": {"databasePath": str(database)}}),
            encoding="utf-8",
        )

    @staticmethod
    def _get(api, path: str):
        statuses: list[str] = []
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": path,
            "QUERY_STRING": "",
            "CONTENT_LENGTH": "0",
            "wsgi.input": io.BytesIO(),
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_AUTHORIZATION": "Bearer viewer-token",
        }
        body = b"".join(api(environ, lambda status, headers: statuses.append(status)))
        return int(statuses[0].split()[0]), json.loads(body)

    @staticmethod
    def _post(api, path: str, document: object):
        payload = json.dumps(document, ensure_ascii=False).encode("utf-8")
        statuses: list[str] = []
        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": path,
            "QUERY_STRING": "",
            "CONTENT_LENGTH": str(len(payload)),
            "CONTENT_TYPE": "application/json",
            "wsgi.input": io.BytesIO(payload),
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_AUTHORIZATION": "Bearer admin-token",
        }
        body = b"".join(api(environ, lambda status, headers: statuses.append(status)))
        return int(statuses[0].split()[0]), json.loads(body)

    @classmethod
    def _complete_flow(cls, api, active):
        return cls._post(
            api,
            "/api/operations/rules/complete-flow",
            {
                "expectedRevisionId": active.revision_id,
                "expectedVersion": active.revision_sequence or active.version,
                "expectedDigest": active.digest,
                "resourceLibraryId": "source",
                "syntheticPath": "电影/Example.Movie.2024.mkv",
                "liveMetadata": False,
                "syntheticIdentity": {
                    "title": "Example Movie",
                    "mediaType": "movie",
                    "year": 2024,
                },
            },
        )

    def test_host_restore_relocates_without_rewriting_published_pins(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "original.sqlite3"
            restored = root / "restored.sqlite3"
            backup = root / "runtime-backup.sqlite3"
            document = self._document(root, source)
            incoming = root / "incoming"
            organized = root / "organized"

            def media_snapshot():
                return tuple(
                    (
                        path.relative_to(root).as_posix(),
                        path.read_bytes() if path.is_file() else None,
                    )
                    for base in (incoming, organized)
                    for path in sorted(base.rglob("*"))
                )

            with (
                SQLiteConfigurationRepository(source) as configuration_repository,
                SQLiteTaskRepository(source) as runtime_repository,
            ):
                service = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(source),
                )
                first = self._activate(service, document)
                second_document = json.loads(json.dumps(document))
                second_document["historyPath"] = str(root / "second-history.jsonl")
                successor = service.stage_successor_draft(actor="tester")
                edited = service.edit_draft(
                    successor.revision_id,
                    second_document,
                    expected_version=successor.version,
                    actor="tester",
                )
                validated = service.validate(edited.revision_id, actor="tester")
                self.assertEqual(validated.status.value, "validated", validated.validation_errors)
                second = service.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
                self.assertEqual(
                    configuration_repository.get_revision(first.revision_id).status.value,
                    "superseded",
                )
                runtime_repository.create_task(
                    PersistentTask(
                        "original-task",
                        "organize",
                        PersistentTaskStatus.COMPLETED,
                        False,
                        NOW,
                        NOW,
                        total_items=1,
                        completed_items=1,
                        configuration_snapshot_id=first.revision_id,
                        configuration_snapshot_digest=first.digest,
                    )
                )
                source_api = MediaFlowApi(
                    runtime_repository,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                    ),
                    configuration_service=service,
                    bootstrap_document={
                        "version": 1,
                        "persistence": {"databasePath": str(source)},
                    },
                    storage_browser_cursor_secret="restore-test-secret",
                )
                before_flow = media_snapshot()
                initial_status, initial_flow = self._complete_flow(source_api, second)
                self.assertEqual(initial_status, 200, initial_flow)
                self.assertEqual(media_snapshot(), before_flow)
            source_config = root / "source-config.json"
            self._write_bootstrap(source_config, source)
            source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
            code, output, error = run_host(source_config, "backup", "--output", str(backup))
            self.assertEqual(code, 0, error)
            self.assertIn("Integrity: OK", output)
            backup_digest = hashlib.sha256(backup.read_bytes()).hexdigest()

            restore_config = root / "restore-config.json"
            self._write_bootstrap(restore_config, restored)
            code, output, error = run_host(
                restore_config, "restore", str(backup), "--confirm-empty-destination"
            )
            self.assertEqual(code, 0, error)
            self.assertIn("Status: RESTORED", output)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), source_digest)
            self.assertEqual(hashlib.sha256(backup.read_bytes()).hexdigest(), backup_digest)

            # Published snapshots and the Task pin keep their exact bytes and
            # identity; only the deployment-internal locator history changes.
            with SQLiteConfigurationRepository(restored) as repository:
                self.assertEqual(
                    repository.get_revision(first.revision_id).document, first.document
                )
                self.assertEqual(repository.get_revision(first.revision_id).digest, first.digest)
                self.assertEqual(
                    repository.get_revision(second.revision_id).document, second.document
                )
                self.assertEqual(
                    repository.deployment_database_locations(), (str(source), str(restored))
                )
            with SQLiteTaskRepository(restored) as repository:
                pinned = repository.get_task("original-task")
                self.assertEqual(pinned.configuration_snapshot_id, first.revision_id)
                self.assertEqual(pinned.configuration_snapshot_digest, first.digest)

            current = resolve_configuration(str(restore_config))
            self.assertEqual(current.database_path, str(restored))
            self.assertEqual(current.configuration_snapshot_id, second.revision_id)
            old_pin = resolve_configuration(
                str(restore_config),
                snapshot_id=first.revision_id,
                snapshot_digest=first.digest,
            )
            self.assertEqual(old_pin.configuration_snapshot_id, first.revision_id)
            self.assertEqual(old_pin.database_path, str(restored))

            restore_bootstrap = json.loads(restore_config.read_text(encoding="utf-8"))
            with (
                SQLiteConfigurationRepository(restored) as configuration_repository,
                SQLiteTaskRepository(restored) as runtime_repository,
            ):
                managed = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(restored),
                    bootstrap_document=restore_bootstrap,
                )
                api = MediaFlowApi(
                    runtime_repository,
                    principals=(
                        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                        ResolvedApiPrincipal(
                            "viewer", "viewer-token", frozenset({ApiPermission.READ})
                        ),
                    ),
                    configuration_service=managed,
                    bootstrap_document=restore_bootstrap,
                    storage_browser_cursor_secret="restore-test-secret",
                )
                status, files = self._get(api, "/api/resource-libraries/source/files")
                self.assertEqual(status, 200, files)
                self.assertEqual(files["configuration"]["revisionId"], second.revision_id)
                self.assertEqual([entry["name"] for entry in files["entries"]], ["Movie.2001.mkv"])

                # The same published Active and offline sample run through the
                # formal Rules API again after the host restore.  The published
                # snapshot keeps its ID/digest and sample while the deployment
                # locator now opens the restored database; the complete plan and
                # the read-only result must stay identical with zero media effect.
                restored_status, restored_flow = self._complete_flow(api, managed.active())
                self.assertEqual(restored_status, 200, restored_flow)
                self.assertEqual(media_snapshot(), before_flow)
                self.assertEqual(
                    {key: value for key, value in initial_flow.items() if key != "testedAt"},
                    {key: value for key, value in restored_flow.items() if key != "testedAt"},
                )
                for flow in (initial_flow, restored_flow):
                    self.assertEqual(flow["entry"], "complete_flow_check")
                    self.assertEqual(flow["readiness"], "complete_plan_ready", flow)
                    self.assertEqual(flow["revisionId"], second.revision_id)
                    self.assertEqual(flow["revisionDigest"], second.digest)
                    self.assertEqual(flow["executionAuthorityGranted"], "none")
                    self.assertEqual(flow["storageReads"], 0)
                    self.assertEqual(flow["sideEffects"], "none")
                    self.assertEqual(flow["providerCalls"], 0)

                # New input carrying the pre-restore locator is still refused.
                wrong = json.loads(json.dumps(managed.active().document))
                wrong["historyPath"] = str(root / "wrong-history.jsonl")
                wrong_draft = managed.import_draft(wrong, actor="tester")
                wrong_validated = managed.validate(wrong_draft.revision_id, actor="tester")
                self.assertEqual(wrong_validated.status.value, "draft")
                self.assertTrue(
                    any("databasePath" in item for item in wrong_validated.validation_errors)
                )

                # A composed successor carries the current locator; a direct
                # publication derived from the old Active is rebound to the
                # same current locator instead of failing the strict input check.
                candidate = managed.stage_successor_draft(actor="tester")
                self.assertEqual(candidate.document["persistence"]["databasePath"], str(restored))
                base = managed.active()
                derived = json.loads(json.dumps(base.document))
                derived["operationalLogging"]["minimumLevel"] = "WARN"
                published = managed.publish_document(
                    derived,
                    actor="tester",
                    expected_active_revision_id=base.revision_id,
                    expected_active_version=base.revision_sequence or base.version,
                    expected_active_digest=base.digest,
                )
                self.assertEqual(published.document["persistence"]["databasePath"], str(restored))
                self.assertEqual(published.document["operationalLogging"]["minimumLevel"], "WARN")

            after_save = resolve_configuration(
                str(restore_config),
                snapshot_id=first.revision_id,
                snapshot_digest=first.digest,
            )
            self.assertEqual(after_save.configuration_snapshot_id, first.revision_id)

            # Copying the restored file without an explicit restore does not
            # silently adopt it at another bootstrap locator.
            copied = root / "copied.sqlite3"
            shutil.copyfile(restored, copied)
            copied_config = root / "copied-config.json"
            self._write_bootstrap(copied_config, copied)
            with self.assertRaises(RuntimeSnapshotUnavailable) as refused:
                resolve_configuration(str(copied_config))
            self.assertEqual(refused.exception.reason, "runtime_invalid")

            self.assertEqual((root / "incoming" / "Movie.2001.mkv").read_bytes(), b"media")
            self.assertEqual(
                sorted(path.name for path in (root / "organized").rglob("*")),
                ["Movies", "TV Shows"],
            )


if __name__ == "__main__":
    unittest.main()
