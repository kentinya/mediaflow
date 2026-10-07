#!/usr/bin/env python3
"""Seed a Base-era Files transfer database and verify candidate readback.

The seed mode imports the project and its existing transfer test fixture from
the supplied Base worktree. The verification mode opens a copy of those
SQLite databases with the current project and compares pinned authority,
Tasks, items, Results and durable projections without running a Worker.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def _seed_base(base_tree: Path, state_root: Path) -> int:
    if state_root.exists():
        raise SystemExit(f"refusing to reuse existing rehearsal state: {state_root}")
    base_tree = base_tree.resolve(strict=True)
    state_root.mkdir(parents=True)
    sys.path.insert(0, str(base_tree))

    from mediaflow.application.files_transfer_worker import FilesTransferWorker
    from mediaflow.domain.storage import StorageEntry
    from mediaflow.infrastructure.local_storage import LocalStorage
    from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION
    from tests.test_direct_file_transfers import TransferTestCase

    imported_project = Path(sys.modules["mediaflow"].__file__).resolve()
    if not imported_project.is_relative_to(base_tree):
        raise SystemExit("seed mode did not load MediaFlow from the supplied Base worktree")

    source_root = state_root / "source"
    destination_root = state_root / "destination"
    source_root.mkdir()
    destination_root.mkdir()

    class SelectiveNoFingerprintSource(LocalStorage):
        @staticmethod
        def _without_identity(entry: StorageEntry) -> StorageEntry:
            if entry.name != "refused.mkv":
                return entry
            return StorageEntry(
                name=entry.name,
                path=entry.path,
                entry_type=entry.entry_type,
                size=entry.size,
                modified_at=entry.modified_at,
                fingerprint=None,
            )

        def stat(self, path: str) -> StorageEntry:
            return self._without_identity(super().stat(path))

        def list(self, path: str):
            return [self._without_identity(entry) for entry in super().list(path)]

    class SwitchingTruncatedTarget(LocalStorage):
        def __init__(self, storage_id: str, path: Path) -> None:
            super().__init__(storage_id, path)
            self.truncate_once = False

        def write(self, path: str, data, *, overwrite: bool = False) -> None:
            if self.truncate_once:
                self.truncate_once = False
                payload = data.read(3) if hasattr(data, "read") else data[:3]
                super().write(path, payload, overwrite=overwrite)
                raise SystemExit(3)
            super().write(path, data, overwrite=overwrite)

    case = TransferTestCase(methodName="runTest")
    source = SelectiveNoFingerprintSource("source-storage", source_root)
    destination = SwitchingTruncatedTarget("media-target", destination_root)
    api, active, repository = case._activate(
        state_root,
        storage_adapters={"source-storage": source, "media-target": destination},
    )
    try:
        transfers = case._transfers(api, active)

        def admit(paths: list[str], *, operation: str = "copy", conflict: str = "fail"):
            impact = transfers.transfer_impact(
                resource_library_id="source",
                paths=paths,
                destination_resource_library_id="destination",
                destination_directory="",
                operation=operation,
                conflict_mode=conflict,
            )
            return transfers.submit_transfer(
                resource_library_id="source",
                paths=paths,
                destination_resource_library_id="destination",
                destination_directory="",
                operation=operation,
                conflict_mode=conflict,
                manifest_digest=impact.manifest.digest,
            )

        (source_root / "complete.mkv").write_bytes(b"complete historical payload")
        completed = admit(["complete.mkv"])
        case._run_worker(transfers, repository)
        assert transfers.transfer_projection(completed["taskId"])["status"] == "SUCCESS"

        (source_root / "partial-a.mkv").write_bytes(b"partial a")
        (source_root / "partial-b.mkv").write_bytes(b"partial b")
        (destination_root / "partial-b.mkv").write_bytes(b"existing target")
        partial = admit(["partial-a.mkv", "partial-b.mkv"], conflict="skip")
        case._run_worker(transfers, repository)
        assert transfers.transfer_projection(partial["taskId"])["status"] == "PARTIAL"

        (source_root / "uncertain.mkv").write_bytes(b"uncertain historical payload")
        uncertain = admit(["uncertain.mkv"], operation="move")
        destination.truncate_once = True
        try:
            case._worker(transfers, repository).run_next()
        except SystemExit:
            pass
        else:
            raise AssertionError("the synthetic Base Worker did not stop at the write boundary")
        recovery = FilesTransferWorker(
            transfers,
            repository,
            lease_seconds=3600.0,
            worker_id="base-rehearsal-recovery",
            clock=lambda: datetime.now(UTC) + timedelta(hours=2),
        )
        assert recovery.run_next() is not None
        assert transfers.transfer_projection(uncertain["taskId"])["status"] == "UNCERTAIN"

        (source_root / "refused.mkv").write_bytes(b"old refused source payload")
        refused = admit(["refused.mkv"], operation="move")
        case._run_worker(transfers, repository)
        assert transfers.transfer_projection(refused["taskId"])["status"] == "PARTIAL"
        assert (source_root / "refused.mkv").read_bytes() == b"old refused source payload"

        (source_root / "pending.mkv").write_bytes(b"pending historical payload")
        pending = admit(["pending.mkv"])
        roles = {
            "completed": completed["taskId"],
            "partial": partial["taskId"],
            "uncertain": uncertain["taskId"],
            "refused_no_fingerprint": refused["taskId"],
            "pending": pending["taskId"],
        }
        manifest: dict[str, object] = {
            "base": "f57715c042ffa22c07d92950cc3de222946ed9b2",
            "baseSchemaVersion": SCHEMA_VERSION,
            "database": str(state_root / "runtime.sqlite3"),
            "configurationDatabase": str(state_root / "configuration.sqlite3"),
            "roles": roles,
            "snapshots": {},
            "records": {},
        }
        snapshots = manifest["snapshots"]
        records = manifest["records"]
        assert isinstance(snapshots, dict) and isinstance(records, dict)
        for role, task_id in roles.items():
            task = repository.get_task(task_id)
            transfer = repository.get_files_transfer(task_id)
            items = repository.list_items(task_id)
            assert task is not None and transfer is not None
            snapshots[role] = {
                "taskStatus": task.status.value,
                "transferStatus": transfer.status.value,
                "snapshotId": transfer.configuration_snapshot_id,
                "snapshotDigest": transfer.configuration_snapshot_digest,
                "authorityJson": transfer.authority_json,
                "authoritySha256": hashlib.sha256(transfer.authority_json.encode()).hexdigest(),
                "taskSnapshotId": task.configuration_snapshot_id,
                "taskSnapshotDigest": task.configuration_snapshot_digest,
            }
            records[role] = {
                "items": [
                    {
                        "itemId": item.item_id,
                        "source": item.source_display,
                        "status": item.status.value,
                        "progress": item.progress,
                    }
                    for item in items
                ],
                "results": [
                    {
                        "itemId": result.item_id,
                        "status": result.status,
                        "effectCertainty": result.effect_certainty,
                        "uncertainEffects": list(result.uncertain_effects),
                    }
                    for result in repository.list_results(task_id)
                ],
            }
        _json(state_root / "base-manifest.json", manifest)
        print(
            json.dumps(
                {
                    "seededFrom": str(base_tree),
                    "base": manifest["base"],
                    "schemaVersion": repository.schema_version,
                    "roles": {
                        role: {
                            "taskId": task_id,
                            "taskStatus": snapshots[role]["taskStatus"],
                            "transferStatus": snapshots[role]["transferStatus"],
                            "snapshotId": snapshots[role]["snapshotId"],
                            "authoritySha256": snapshots[role]["authoritySha256"],
                            "hasStrongFingerprint": any(
                                isinstance(entry, list) and len(entry) > 4 and entry[4]
                                for entry in json.loads(snapshots[role]["authorityJson"]).get(
                                    "entries", []
                                )
                            ),
                        }
                        for role, task_id in roles.items()
                    },
                },
                indent=2,
            )
        )
        return 0
    finally:
        case.doCleanups()


def _verify_candidate(repository_root: Path, state_root: Path) -> int:
    repository_root = repository_root.resolve(strict=True)
    state_root = state_root.resolve(strict=True)
    sys.path.insert(0, str(repository_root))

    from mediaflow.application.direct_file_transfers import durable_transfer_read_service
    from mediaflow.infrastructure.sqlite_configuration_management import (
        SQLiteConfigurationRepository,
    )
    from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository

    imported_project = Path(sys.modules["mediaflow"].__file__).resolve()
    if not imported_project.is_relative_to(repository_root):
        raise SystemExit("verification mode did not load MediaFlow from the candidate checkout")

    manifest = json.loads((state_root / "base-manifest.json").read_text(encoding="utf-8"))
    candidate_dir = state_root / "candidate-restart"
    candidate_dir.mkdir(exist_ok=True)
    candidate_db = candidate_dir / "runtime.sqlite3"
    candidate_configuration_db = candidate_dir / "configuration.sqlite3"
    shutil.copy2(state_root / "runtime.sqlite3", candidate_db)
    shutil.copy2(state_root / "configuration.sqlite3", candidate_configuration_db)
    candidate_hash_before_open = hashlib.sha256(candidate_db.read_bytes()).hexdigest()
    repository = SQLiteTaskRepository(candidate_db)
    configuration = SQLiteConfigurationRepository(candidate_configuration_db)
    try:
        assert repository.schema_version == SCHEMA_VERSION
        assert manifest["baseSchemaVersion"] == SCHEMA_VERSION
        reader = durable_transfer_read_service(repository, media_library=False)
        expected_projection = {
            "completed": "SUCCESS",
            "partial": "PARTIAL",
            "uncertain": "UNCERTAIN",
            "refused_no_fingerprint": "PARTIAL",
            "pending": "QUEUED",
        }
        verified: dict[str, object] = {}
        for role, task_id in manifest["roles"].items():
            original = manifest["snapshots"][role]
            task = repository.get_task(task_id)
            transfer = repository.get_files_transfer(task_id)
            assert task is not None and transfer is not None
            assert task.status.value == original["taskStatus"]
            assert transfer.status.value == original["transferStatus"]
            assert task.configuration_snapshot_id == original["taskSnapshotId"]
            assert task.configuration_snapshot_digest == original["taskSnapshotDigest"]
            assert transfer.configuration_snapshot_id == original["snapshotId"]
            assert transfer.configuration_snapshot_digest == original["snapshotDigest"]
            assert transfer.configuration_snapshot_id == task.configuration_snapshot_id
            assert transfer.configuration_snapshot_digest == task.configuration_snapshot_digest
            assert transfer.authority_json == original["authorityJson"]
            assert (
                hashlib.sha256(transfer.authority_json.encode()).hexdigest()
                == original["authoritySha256"]
            )
            revision = configuration.get_revision(transfer.configuration_snapshot_id)
            assert revision is not None
            assert revision.digest == transfer.configuration_snapshot_digest
            items = repository.list_items(task_id)
            results = repository.list_results(task_id)
            item_facts = [
                {
                    "itemId": item.item_id,
                    "source": item.source_display,
                    "status": item.status.value,
                    "progress": item.progress,
                }
                for item in items
            ]
            result_facts = [
                {
                    "itemId": result.item_id,
                    "status": result.status,
                    "effectCertainty": result.effect_certainty,
                    "uncertainEffects": list(result.uncertain_effects),
                }
                for result in results
            ]
            assert item_facts == manifest["records"][role]["items"]
            assert result_facts == manifest["records"][role]["results"]
            projection = reader.transfer_projection(task_id)
            assert projection["status"] == expected_projection[role]
            if role == "uncertain":
                assert projection["durableState"] == "mutation_effect_uncertain"
                assert result_facts[0]["effectCertainty"] == "attempted_unverified"
                assert result_facts[0]["uncertainEffects"] == ["mutation_outcome"]
            if role == "refused_no_fingerprint":
                assert (
                    state_root / "source" / "refused.mkv"
                ).read_bytes() == b"old refused source payload"
            if role == "pending":
                assert task.status.value == "pending" and transfer.status.value == "admitted"
                assert items[0].status.value == "pending"
            verified[role] = {
                "taskStatus": task.status.value,
                "transferStatus": transfer.status.value,
                "projectionStatus": projection["status"],
                "snapshotId": transfer.configuration_snapshot_id,
                "snapshotDigest": transfer.configuration_snapshot_digest,
                "authoritySha256": hashlib.sha256(transfer.authority_json.encode()).hexdigest(),
                "itemCount": len(items),
                "resultCount": len(results),
            }
        print(
            json.dumps(
                {
                    "candidate": str(repository_root),
                    "schemaVersion": repository.schema_version,
                    "candidateDbSha256BeforeOpen": candidate_hash_before_open,
                    "verified": verified,
                    "refusedSourceRetained": (state_root / "source" / "refused.mkv").exists(),
                },
                indent=2,
            )
        )
        return 0
    finally:
        repository.close()
        configuration.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    seed = subparsers.add_parser("seed-base", help="create historical work under the Base code")
    seed.add_argument("--base-tree", type=Path, required=True)
    seed.add_argument("--state-root", type=Path, required=True)
    verify = subparsers.add_parser("verify-candidate", help="reopen a copy using candidate code")
    verify.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    verify.add_argument("--state-root", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.mode == "seed-base":
        return _seed_base(args.base_tree, args.state_root)
    return _verify_candidate(args.repository_root, args.state_root)


if __name__ == "__main__":
    raise SystemExit(main())
