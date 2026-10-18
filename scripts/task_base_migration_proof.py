#!/usr/bin/env python3
"""Task Base -> candidate additive migration proof for Task 45.3.

The script builds an isolated Git worktree at the exact Task Base commit
(``8f5cf4e284766bcc8894817d7640231e85050fb2``), creates a runtime SQLite
database with the *actual Task Base code* (schema 45, no
``manual_recovery_preparations`` table), seeds representative durable state,
then reopens that database with the current candidate repository and verifies:

* the additive schema bump (45 -> 46), new preparation columns, and bounded
  parent-continuation lookup index exist;
* the seeded **real** published configuration revision, manual intent/item,
  exact Preview/PreviewItem, one-shot authorization (one active, one already
  consumed), recovery continuation/link and Task/Result facts are byte-for-byte
  intact and no old work became executable;
* the new preparation boundary round-trips, references real Task/item/Preview
  rows, and a legacy row (no confirmed selection) still reads back;
* an injected failure in the additive migration leaves the old database
  unchanged (no half state, no schema marker advance), and removing the fault
  allows a safe reopen.

It never reads production paths, user databases, credentials, Storage or
Providers.  Usage (from the repository root, inside the project venv):

    .venv/bin/python scripts/task_base_migration_proof.py
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK_BASE = "8f5cf4e284766bcc8894817d7640231e85050fb2"
BASE_SCHEMA = 45
CANDIDATE_SCHEMA = 46


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _seed_old_database(base_root: Path, database: Path) -> dict[str, object]:
    """Create the old database using the actual Task Base repository code."""

    seed = base_root / "scripts" / "_task_base_seed.py"
    seed.write_text(
        """
import json
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_execution import ManualOrganizeExecutionService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.manual_recovery_continuation import ManualRecoveryContinuationService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.recovery_admission import RecoveryAdmissionService
from mediaflow.application.recovery_continuation import RecoveryContinuationService
from mediaflow.application.scanner import StorageScanner
from mediaflow.application.strategy_test import SyntheticMetadataProvider
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.media_evidence import (
    EVIDENCE_SECTION_NAMES,
    EvidenceSection,
    PipelineEvidence,
)
from mediaflow.domain.manual_organize import ManualChoice
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.organizer import ExecutionEffectCertainty, ExecutionResult, ExecutionStatus
from mediaflow.domain.task_persistence import PersistentResultRecord, TaskItemStatus
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository, SCHEMA_VERSION
from mediaflow.infrastructure.runtime_configuration import load_managed_runtime_configuration

class _PreMutationFailureExecutor:
    def execute(self, plan, _storages, **_kwargs):
        return ExecutionResult(
            ExecutionStatus.FAILED,
            plan.operation,
            plan.source,
            plan.target,
            plan_id=plan.plan_id,
            resolved_destination=plan.target,
            errors=("migration proof stopped before Storage mutation",),
            effect_certainty=ExecutionEffectCertainty.NONE,
        )

database = Path(sys.argv[1])
now = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
root = database.parent
source_root = root / "source"
target_root = root / "target"
source_file = source_root / "Media" / "C" / "Failed.2024.mkv"
source_file.parent.mkdir(parents=True)
target_root.mkdir(parents=True)
source_file.write_bytes(b"synthetic media used only by this migration proof")
document_path = Path(__file__).resolve().parents[1] / "config/strategy.example.json"
document = json.loads(document_path.read_text())
document["storages"][0]["rootPath"] = str(source_root)
document["storages"][1]["rootPath"] = str(target_root)
document["resourceLibraries"][0]["displayRootPath"] = str(source_root / "Media")
document["persistence"] = {"databasePath": str(database)}
document["historyPath"] = str(root / "history.jsonl")

configuration_repository = SQLiteConfigurationRepository(database)
managed = ManagedConfigurationService(
    configuration_repository,
    bootstrap_database_path=str(database),
)
draft = managed.import_draft(document, actor="migration-proof")
validated = managed.validate(draft.revision_id, actor="migration-proof")
active = managed.activate(
    validated.revision_id,
    expected_version=validated.version,
    actor="migration-proof",
)
snapshot_id, snapshot_digest = active.revision_id, active.digest
managed.validate_runtime_snapshot(snapshot_id, snapshot_digest)
runtime = load_managed_runtime_configuration(
    active.document,
    bootstrap_database_path=str(database),
)
file_index = SQLiteFileIndexRepository(database)
repository = SQLiteTaskRepository(database)

class FakeProvider(SyntheticMetadataProvider):
    pass

provider = FakeProvider((MediaCandidate(
    "tmdb", "42", MediaType.MOVIE, "Failed", year=2024,
    genres=("Animation",), countries=("JP",), languages=("ja",),
),))
catalog = FileCatalogService(
    file_index,
    ("source",),
    ("source-storage",),
    task_repository=repository,
)
storage_factory = lambda configuration, storage_ids: configuration.create_storages(
    storage_ids=storage_ids
)
intents = ManualOrganizeIntentService(
    repository,
    catalog,
    configuration_service=managed,
    storage_factory=storage_factory,
)
previews = ManualOrganizePreviewService(
    repository,
    intents,
    configuration_service=managed,
    providers=MetadataProviderRegistry((provider,)),
    storage_factory=storage_factory,
)
execution = ManualOrganizeExecutionService(
    repository,
    previews,
    intents,
    configuration_service=managed,
    storage_factory=storage_factory,
    executor=_PreMutationFailureExecutor(),
)
try:
    scan = StorageScanner(
        runtime.create_storages(),
        file_index,
        clock=lambda: now + timedelta(hours=2),
    ).scan(runtime.resource_libraries[0])
    assert scan.status.value == "completed", scan.status
    records = file_index.list_by_resource_library("source")
    record = next(value for value in records if value.filename == "Failed.2024.mkv")
    intent = intents.create((record.file_id,), actor="operator")
    item = intent.items[0]
    choice = ManualChoice("A", None, "A", "A", "A")
    intent = intents.update_choice(
        intent.intent_id,
        item.item_id,
        choice,
        expected_version=intent.version,
        expected_item_version=item.version,
        actor="operator",
    )
    preview = previews.create(
        intent.intent_id,
        expected_version=intent.version,
        expected_item_versions={value.item_id: value.version for value in intent.items},
        snapshot_id=intent.snapshot_id,
        snapshot_digest=intent.snapshot_digest,
        actor="operator",
        source_scope="file",
        source_scope_id=record.file_id,
    )
    assert preview.status.value == "previewed", preview.status
    preview_item = preview.items[0]
    authorization = execution.authorize(
        preview.preview_id,
        (preview_item.item_id,),
        expected_intent_version=preview.intent_version,
        expected_item_versions={preview_item.item_id: preview_item.item_version},
        snapshot_id=preview.configuration_snapshot_id,
        snapshot_digest=preview.configuration_snapshot_digest,
        actor="operator",
        confirmation=True,
    )
    failed_execution = execution.execute(
        authorization.authorization_id,
        actor="operator",
        confirmation=True,
    )
    assert failed_execution.items[0].status.value == "failed"
    assert source_file.is_file()
    assert not tuple(target_root.rglob("*"))
    source_task_id = failed_execution.task_id
    source_item_id = failed_execution.items[0].task_item_id
    source_result_id = failed_execution.items[0].result_id
    assert source_result_id is not None

    checkpoint_service = execution._checkpoint_service
    checkpoint = checkpoint_service.get(source_item_id, task_id=source_task_id)
    RecoveryAdmissionService(
        repository,
        snapshot_validator=execution._validate_checkpoint_snapshot,
        checkpoint_service=checkpoint_service,
    ).admit(
        source_task_id,
        source_item_id,
        action_id="retry",
        expected_checkpoint_version=checkpoint.checkpoint_version,
        actor="operator",
    )
    checkpoint = checkpoint_service.get(source_item_id, task_id=source_task_id)
    continuation_submission = RecoveryContinuationService(
        repository,
        snapshot_validator=execution._validate_checkpoint_snapshot,
        checkpoint_service=checkpoint_service,
    ).submit(
        source_task_id,
        source_item_id,
        expected_checkpoint_version=checkpoint.checkpoint_version,
        actor="operator",
        maximum_active_jobs=10,
    )
    continuation = continuation_submission.continuation

    coordinator = PersistentTaskCoordinator(repository, repository)
    analysis_task = coordinator.create(
        "organize",
        execute_authorized=False,
        scope_path=record.path,
        item_limit=1,
        configuration_snapshot_id=snapshot_id,
        configuration_snapshot_digest=snapshot_digest,
        require_configuration_snapshot=True,
    )
    analysis_item = coordinator.begin_item(
        analysis_task.task_id,
        record.storage_id,
        record.resource_library_id,
        record.path,
        record.path,
    )
    analysis_item = replace(
        analysis_item,
        status=TaskItemStatus.DRY_RUN,
        stage="dry_run",
        updated_at=now,
    )
    repository.upsert_item(analysis_item)
    repository.release(analysis_item.storage_id, analysis_item.source_path, analysis_item.task_id)
    analysis_result_id = str(uuid4())
    repository.append_result(PersistentResultRecord(
        analysis_result_id,
        analysis_task.task_id,
        analysis_item.item_id,
        record.storage_id,
        record.path,
        "media-target",
        "Movies/Animation/Failed (2024)/Failed (2024).mkv",
        "A",
        "tmdb",
        "42",
        "A",
        "A",
        "A",
        "A",
        "MOVE",
        TaskItemStatus.DRY_RUN.value,
        now,
        title="Failed",
        effect_certainty="none",
        source_occurrence_id=record.occurrence_id,
        source_fingerprint=record.fingerprint,
        source_fingerprint_state="verified",
    ))
    sections = {
        name: EvidenceSection(False, unavailable_reason="not needed by this migration proof")
        for name in EVIDENCE_SECTION_NAMES
    }
    sections["metadata"] = EvidenceSection(True, {
        "status": "matched",
        "recognitionTypeId": "A",
        "provider": "tmdb",
        "providerId": "42",
        "mediaType": "movie",
        "title": "Failed",
        "originalTitle": "Failed",
        "year": 2024,
        "genres": ["Animation"],
        "countries": ["JP"],
        "languages": ["ja"],
        "keywords": [],
        "episodes": [],
    })
    repository.append_evidence(PipelineEvidence(
        f"{analysis_item.item_id}:1",
        analysis_task.task_id,
        analysis_item.item_id,
        1,
        record.storage_id,
        record.path,
        now,
        snapshot_id,
        snapshot_digest,
        "dry_run",
        sections,
    ))
    repository.mark_recovery_continuation_running(continuation.job_id, now)
    repository.bind_recovery_continuation_task(continuation.job_id, analysis_task.task_id)
    continuation = repository.complete_recovery_continuation(
        continuation.job_id,
        new_task_id=analysis_task.task_id,
        new_result_id=analysis_result_id,
        success=True,
        now=now,
    )

    recovery = ManualRecoveryContinuationService(
        repository,
        intent_service=intents,
        preview_service=previews,
        execution_service=execution,
        checkpoint_service=checkpoint_service,
    )
    checkpoint = checkpoint_service.get(source_item_id, task_id=source_task_id)
    link = recovery.authorize_continued(
        source_task_id,
        source_item_id,
        expected_checkpoint_version=checkpoint.checkpoint_version,
        actor="operator",
        confirmation=True,
    )
    assert (
        repository.get_manual_execution_authorization(link.authorization_id).status.value
        == "active"
    )
    managed.validate_runtime_snapshot(snapshot_id, snapshot_digest)
    print(json.dumps({
        "schema": SCHEMA_VERSION,
        "taskId": source_task_id,
        "failedItemId": source_item_id,
        "failedResultId": source_result_id,
        "intentId": intent.intent_id,
        "intentItemId": item.item_id,
        "previewId": preview.preview_id,
        "previewItemId": preview_item.item_id,
        "authorizationId": authorization.authorization_id,
        "executionId": failed_execution.execution_id,
        "linkId": link.link_id,
        "linkAuthorizationId": link.authorization_id,
        "linkPreviewId": link.preview_id,
        "continuationId": continuation.continuation_id,
        "continuationJobId": continuation.job_id,
        "analysisTaskId": analysis_task.task_id,
        "analysisItemId": analysis_item.item_id,
        "analysisResultId": analysis_result_id,
        "snapshotId": snapshot_id,
        "snapshotDigest": snapshot_digest,
        "sourcePath": record.path,
        "sourceRoot": str(source_root),
        "targetRoot": str(target_root),
        "sourceFile": str(source_file),
        "checkpointVersion": checkpoint.checkpoint_version,
        "intentVersion": intent.version,
        "sourceFingerprint": record.fingerprint,
        "pinStatus": "active",
    }))
finally:
    repository.close()
    file_index.close()
    configuration_repository.close()
""",
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(base_root)
    try:
        result = _run(
            [sys.executable, str(seed), str(database)],
            cwd=base_root,
            env=env,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            f"Task Base seed failed:\nSTDOUT:\n{error.stdout}\nSTDERR:\n{error.stderr}"
        ) from error
    return json.loads(result.stdout.strip().splitlines()[-1])


def _read_facts(database: Path) -> dict[str, object]:
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        marker = connection.execute(
            "SELECT version FROM schema_version WHERE component='runtime'"
        ).fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        results = [
            dict(row)
            for row in connection.execute(
                "SELECT result_id, status, provider_id, effect_certainty, destination_path "
                "FROM task_results ORDER BY result_id"
            ).fetchall()
        ]
        link = (
            [
                dict(row)
                for row in connection.execute(
                    "SELECT status, execution_id, authorization_id, preview_id "
                    "FROM manual_recovery_links ORDER BY link_id"
                ).fetchall()
            ]
            if "manual_recovery_links" in tables
            else []
        )
        authorizations = (
            [
                dict(row)
                for row in connection.execute(
                    "SELECT authorization_id, status, consumed_at, execution_id, "
                    "allow_overwrite, allow_source_cleanup FROM "
                    "manual_execution_authorizations ORDER BY authorization_id"
                ).fetchall()
            ]
            if "manual_execution_authorizations" in tables
            else []
        )
        revisions = (
            [
                dict(row)
                for row in connection.execute(
                    "SELECT revision_id, status, digest FROM managed_configuration_revisions "
                    "ORDER BY revision_id"
                ).fetchall()
            ]
            if "managed_configuration_revisions" in tables
            else []
        )
        previews = (
            [
                dict(row)
                for row in connection.execute(
                    "SELECT preview_id, intent_id, status, configuration_snapshot_id "
                    "FROM manual_previews ORDER BY preview_id"
                ).fetchall()
            ]
            if "manual_previews" in tables
            else []
        )
        executions = (
            connection.execute("SELECT COUNT(*) FROM manual_executions").fetchone()[0]
            if "manual_executions" in tables
            else 0
        )
        columns = (
            {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(manual_recovery_preparations)"
                ).fetchall()
            }
            if "manual_recovery_preparations" in tables
            else set()
        )
        continuation_indexes = (
            {
                row[1]
                for row in connection.execute(
                    "PRAGMA index_list(recovery_continuations)"
                ).fetchall()
            }
            if "recovery_continuations" in tables
            else set()
        )
        task_pins = [
            dict(row)
            for row in connection.execute(
                "SELECT task_id, configuration_snapshot_id, configuration_snapshot_digest "
                "FROM tasks WHERE configuration_snapshot_id IS NOT NULL "
                "ORDER BY task_id"
            ).fetchall()
        ]
        intent_pins = [
            dict(row)
            for row in connection.execute(
                "SELECT intent_id, configuration_snapshot_id, configuration_snapshot_digest "
                "FROM manual_intents ORDER BY intent_id"
            ).fetchall()
        ]
    return {
        "schema": marker,
        "hasPreparationTable": "manual_recovery_preparations" in tables,
        "preparationColumns": sorted(columns),
        "recoveryContinuationIndexes": sorted(continuation_indexes),
        "results": results,
        "links": link,
        "authorizations": authorizations,
        "revisions": revisions,
        "previews": previews,
        "taskPins": task_pins,
        "intentPins": intent_pins,
        "manualExecutions": executions,
    }


def _candidate_round_trip(database: Path, seeded: dict[str, object]) -> dict[str, object]:
    """Validate real pins, migrate, and fail closed on incomplete legacy identity."""

    sys.path.insert(0, str(ROOT))
    from mediaflow.application.configuration_snapshot import ManagedConfigurationService
    from mediaflow.application.file_catalog import FileCatalogService
    from mediaflow.application.manual_organize import ManualOrganizeIntentService
    from mediaflow.application.manual_organize_execution import ManualOrganizeExecutionService
    from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
    from mediaflow.application.manual_recovery_continuation import (
        ManualRecoveryContinuationError,
        ManualRecoveryContinuationService,
    )
    from mediaflow.application.metadata import MetadataProviderRegistry
    from mediaflow.application.strategy_test import SyntheticMetadataProvider
    from mediaflow.domain.metadata import MediaCandidate, MediaType
    from mediaflow.domain.organizer import (
        ExecutionEffectCertainty,
        ExecutionResult,
        ExecutionStatus,
    )
    from mediaflow.domain.task_persistence import TaskItemStatus
    from mediaflow.infrastructure.sqlite_configuration_management import (
        SQLiteConfigurationRepository,
    )
    from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository
    from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository

    class _PreMutationFailureExecutor:
        """Exercise admission without changing the disposable source file."""

        def execute(self, plan, _storages, **_kwargs):
            return ExecutionResult(
                ExecutionStatus.FAILED,
                plan.operation,
                plan.source,
                plan.target,
                plan_id=plan.plan_id,
                resolved_destination=plan.target,
                errors=("migration proof stopped before Storage mutation",),
                effect_certainty=ExecutionEffectCertainty.NONE,
            )

    facts_before = _read_facts(database)
    with SQLiteConfigurationRepository(database) as configuration_repository:
        configuration_service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=str(database),
        )
        configuration_service.validate_runtime_snapshot(
            str(seeded["snapshotId"]), str(seeded["snapshotDigest"])
        )
        active_before = configuration_service.active()
        assert active_before is not None
        assert (active_before.revision_id, active_before.digest) == (
            seeded["snapshotId"],
            seeded["snapshotDigest"],
        )
        assert active_before.status.value == "active"

        with (
            SQLiteTaskRepository(database) as repository,
            SQLiteFileIndexRepository(database) as file_index,
        ):
            assert repository.schema_version == CANDIDATE_SCHEMA, repository.schema_version
            after_open = _read_facts(database)
            for key in (
                "links",
                "authorizations",
                "revisions",
                "previews",
                "results",
                "taskPins",
                "intentPins",
            ):
                assert after_open[key] == facts_before[key], (
                    key,
                    after_open[key],
                    facts_before[key],
                )
            assert after_open["manualExecutions"] == facts_before["manualExecutions"] == 1

            source_task = repository.get_task(str(seeded["taskId"]))
            source_item = repository.get_item(str(seeded["failedItemId"]))
            source_execution = repository.get_manual_execution(str(seeded["executionId"]))
            source_result = next(
                value
                for value in repository.list_results(str(seeded["taskId"]))
                if value.result_id == seeded["failedResultId"]
            )
            analysis_task = repository.get_task(str(seeded["analysisTaskId"]))
            analysis_item = repository.get_item(str(seeded["analysisItemId"]))
            analysis_result = next(
                value
                for value in repository.list_results(str(seeded["analysisTaskId"]))
                if value.result_id == seeded["analysisResultId"]
            )
            continuation = repository.get_recovery_continuation_for_job(
                str(seeded["continuationJobId"])
            )
            link = repository.get_manual_recovery_link(str(seeded["linkId"]))
            link_authorization = repository.get_manual_execution_authorization(
                str(seeded["linkAuthorizationId"])
            )
            assert source_task is not None and source_item is not None
            assert source_execution is not None and source_result is not None
            assert analysis_task is not None and analysis_item is not None
            assert analysis_result is not None
            assert continuation is not None and link is not None
            assert source_task.configuration_snapshot_id == seeded["snapshotId"]
            assert source_task.configuration_snapshot_digest == seeded["snapshotDigest"]
            assert source_result.status == "FAILED"
            assert source_result.effect_certainty == "none"
            assert source_execution.authorization_id == seeded["authorizationId"]
            assert source_execution.task_id == source_task.task_id
            assert source_item.task_id == source_task.task_id
            assert analysis_task.configuration_snapshot_id == seeded["snapshotId"]
            assert analysis_task.configuration_snapshot_digest == seeded["snapshotDigest"]
            assert analysis_item.task_id == analysis_task.task_id
            assert analysis_result.status == TaskItemStatus.DRY_RUN.value
            assert continuation.continuation_id == seeded["continuationId"]
            assert continuation.status.value == "completed"
            assert continuation.new_task_id == analysis_task.task_id
            assert continuation.new_result_id == analysis_result.result_id
            assert link.status.value == "authorized"
            assert link.authorization_id == link_authorization.authorization_id
            assert link.preview_id == seeded["linkPreviewId"]
            assert repository.get_manual_intent(str(seeded["intentId"])) is not None
            assert repository.get_manual_preview(str(seeded["linkPreviewId"])) is not None
            assert link_authorization.status.value == "active"
            assert Path(str(seeded["sourceFile"])).is_file()
            assert not tuple(Path(str(seeded["targetRoot"])).rglob("*"))

            configuration_service.require(str(seeded["snapshotId"]))
            catalog = FileCatalogService(
                file_index,
                ("source",),
                ("source-storage",),
                task_repository=repository,
            )

            def storage_factory(value, storage_ids):
                return value.create_storages(storage_ids=storage_ids)

            intents = ManualOrganizeIntentService(
                repository,
                catalog,
                configuration_service=configuration_service,
                storage_factory=storage_factory,
            )
            provider = SyntheticMetadataProvider(
                (
                    MediaCandidate(
                        "tmdb",
                        "42",
                        MediaType.MOVIE,
                        "Failed",
                        year=2024,
                        genres=("Animation",),
                        countries=("JP",),
                        languages=("ja",),
                    ),
                )
            )
            previews = ManualOrganizePreviewService(
                repository,
                intents,
                configuration_service=configuration_service,
                providers=MetadataProviderRegistry((provider,)),
                storage_factory=storage_factory,
            )
            execution = ManualOrganizeExecutionService(
                repository,
                previews,
                intents,
                configuration_service=configuration_service,
                storage_factory=storage_factory,
                executor=_PreMutationFailureExecutor(),
            )
            recovery = ManualRecoveryContinuationService(
                repository,
                intent_service=intents,
                preview_service=previews,
                execution_service=execution,
                checkpoint_service=execution._checkpoint_service,
            )

            # Task Base evidence has only the bounded operator projection, not
            # the candidate's separate normalized execution identity snapshot.
            # It must require a fresh Worker analysis without a synchronous
            # Provider call; the old active link authority must remain unused.
            provider_calls_before = provider.calls
            assert recovery._reusable_analysis_identity(analysis_item.item_id) is None
            assert provider.calls == provider_calls_before
            checkpoint = execution._checkpoint_service.get(
                str(seeded["failedItemId"]), task_id=str(seeded["taskId"])
            )
            try:
                recovery.prepare_summary(
                    str(seeded["taskId"]),
                    str(seeded["failedItemId"]),
                    expected_checkpoint_version=checkpoint.checkpoint_version,
                    actor="operator",
                )
            except ManualRecoveryContinuationError as error:
                assert error.code == "preview_blocked", (error.code, error)
                assert "re-analyze" in error.next_action or "fresh" in error.next_action
            else:
                raise AssertionError("legacy evidence without an exact identity must block")
            assert provider.calls == provider_calls_before
            assert (
                repository.get_current_manual_recovery_preparation(
                    str(seeded["taskId"]), str(seeded["failedItemId"])
                )
                is None
            )
            assert link.status.value == "authorized"
            assert link_authorization.status.value == "active"
            assert (
                repository.get_manual_execution_authorization(
                    str(seeded["authorizationId"])
                ).status.value
                == "consumed"
            )
            assert Path(str(seeded["sourceFile"])).is_file()
            assert not tuple(Path(str(seeded["targetRoot"])).rglob("*"))

            configuration_service.validate_runtime_snapshot(
                str(seeded["snapshotId"]), str(seeded["snapshotDigest"])
            )
            active_after = configuration_service.active()
            assert active_after is not None
            assert (active_after.revision_id, active_after.digest) == (
                seeded["snapshotId"],
                seeded["snapshotDigest"],
            )

            # Reopen the exact candidate DB and verify the old grant/result/pin
            # facts remain intact while no preparation or execution was invented.
            with SQLiteTaskRepository(database) as reopened:
                assert (
                    reopened.get_current_manual_recovery_preparation(
                        str(seeded["taskId"]), str(seeded["failedItemId"])
                    )
                    is None
                )
                assert (
                    reopened.get_manual_execution_authorization(
                        str(seeded["authorizationId"])
                    ).status.value
                    == "consumed"
                )
                assert (
                    reopened.get_manual_execution_authorization(
                        str(seeded["linkAuthorizationId"])
                    ).status.value
                    == "active"
                )

    return {"afterOpen": after_open, "facts": _read_facts(database)}


def _build_intermediate_database(base_database: Path, target: Path, seeded: dict) -> None:
    """Copy the base database and give it a pre-46 preparation table.

    The Task Base schema 45 has no preparation table at all, so the candidate's
    fresh-table path is exercised by the main round trip.  To exercise the
    *additive ALTER* path (and prove it rolls back atomically), this copies the
    real base database and installs the preparation table in its pre-46 shape:
    the three new columns are absent and one legacy row already exists.  The
    schema marker stays 45, so reopening with the candidate code must add the
    columns through the ALTER branch.
    """

    shutil.copyfile(base_database, target)
    with sqlite3.connect(target) as connection:
        connection.execute(
            """CREATE TABLE manual_recovery_preparations (
                preparation_id TEXT PRIMARY KEY, source_task_id TEXT NOT NULL,
                source_item_id TEXT NOT NULL,
                analysis_continuation_id TEXT NOT NULL,
                analysis_task_id TEXT NOT NULL,
                analysis_result_id TEXT NOT NULL,
                intent_id TEXT NOT NULL, preview_id TEXT NOT NULL UNIQUE,
                intent_version INTEGER NOT NULL,
                checkpoint_version TEXT NOT NULL,
                input_fingerprint TEXT NOT NULL,
                configuration_snapshot_id TEXT NOT NULL,
                configuration_snapshot_digest TEXT NOT NULL,
                actor TEXT NOT NULL, status TEXT NOT NULL, current INTEGER NOT NULL,
                authorization_id TEXT UNIQUE, execution_id TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
        )
        connection.execute(
            "INSERT INTO manual_recovery_preparations VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "legacy-prep",
                seeded["taskId"],
                seeded["failedItemId"],
                seeded["continuationId"],
                seeded["analysisTaskId"],
                seeded["analysisResultId"],
                seeded["intentId"],
                seeded["linkPreviewId"],
                seeded["intentVersion"],
                seeded["checkpointVersion"],
                seeded["sourceFingerprint"],
                seeded["snapshotId"],
                seeded["snapshotDigest"],
                "operator",
                "prepared",
                1,
                None,
                None,
                "2026-10-17T12:00:00+00:00",
                "2026-10-17T12:00:00+00:00",
            ),
        )
        connection.execute("UPDATE schema_version SET version=45 WHERE component='runtime'")
        connection.commit()


def _inject_migration_failure(base_database: Path, seeded: dict, work: Path) -> None:
    """Inject a fault into the additive migration and prove atomic rollback.

    The candidate's own migration runs the ``ALTER TABLE
    manual_recovery_preparations ADD COLUMN selected_item_ids_json`` statement;
    the fault makes that statement raise.  Because the whole additive migration
    runs inside the ``_initialize`` transaction, the preceding statements and
    the schema marker must roll back: the old database keeps schema 45, the
    preparation table keeps its pre-46 shape and the legacy row is intact.
    Removing the fault must then let a safe reopen complete the migration.
    """

    sys.path.insert(0, str(ROOT))
    import mediaflow.infrastructure.sqlite_runtime as runtime_module

    target = work / "intermediate.sqlite3"
    _build_intermediate_database(base_database, target, seeded)
    before = _read_facts(target)
    assert before["schema"] == BASE_SCHEMA
    assert before["hasPreparationTable"] is True
    assert "recovery_continuations_task_created" not in before["recoveryContinuationIndexes"]
    assert "selected_item_ids_json" not in before["preparationColumns"]
    assert before["preparationColumns"] == [
        "actor",
        "analysis_continuation_id",
        "analysis_result_id",
        "analysis_task_id",
        "authorization_id",
        "checkpoint_version",
        "configuration_snapshot_digest",
        "configuration_snapshot_id",
        "created_at",
        "current",
        "execution_id",
        "input_fingerprint",
        "intent_id",
        "intent_version",
        "preparation_id",
        "preview_id",
        "source_item_id",
        "source_task_id",
        "status",
        "updated_at",
    ], before["preparationColumns"]

    original_connect = sqlite3.connect
    state = {"raised": False}

    class _FailingConnection(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if (
                not state["raised"]
                and isinstance(sql, str)
                and "ALTER TABLE manual_recovery_preparations ADD COLUMN selected_item_ids_json"
                in sql
            ):
                state["raised"] = True
                raise sqlite3.OperationalError("injected additive migration failure")
            return super().execute(sql, *args, **kwargs)

    def _patched_connect(*args, **kwargs):
        kwargs.setdefault("factory", _FailingConnection)
        return original_connect(*args, **kwargs)

    runtime_module.sqlite3.connect = _patched_connect
    try:
        try:
            with runtime_module.SQLiteTaskRepository(target):
                raise AssertionError("the injected failure must abort initialization")
        except sqlite3.OperationalError:
            pass
    finally:
        runtime_module.sqlite3.connect = original_connect
    assert state["raised"] is True
    after = _read_facts(target)
    # Atomic rollback: no half-migrated columns, no schema marker advance, and
    # every old durable fact is untouched.
    assert after["schema"] == BASE_SCHEMA, after["schema"]
    assert after["preparationColumns"] == before["preparationColumns"]
    assert after["recoveryContinuationIndexes"] == before["recoveryContinuationIndexes"]
    assert after["results"] == before["results"]
    assert after["links"] == before["links"]
    assert after["authorizations"] == before["authorizations"]
    assert after["revisions"] == before["revisions"]
    # Removing the fault lets the same database reopen and migrate cleanly.
    with runtime_module.SQLiteTaskRepository(target) as reopened:
        assert reopened.schema_version == CANDIDATE_SCHEMA
        legacy = reopened.get_manual_recovery_preparation("legacy-prep")
        assert legacy is not None
        assert legacy.selected_item_ids == ()
        assert legacy.allow_overwrite is False
        assert legacy.allow_source_cleanup is False
    recovered = _read_facts(target)
    assert recovered["schema"] == CANDIDATE_SCHEMA
    assert "selected_item_ids_json" in recovered["preparationColumns"]
    assert "recovery_continuations_task_created" in recovered["recoveryContinuationIndexes"]
    assert recovered["links"] == before["links"]
    assert recovered["authorizations"] == before["authorizations"]
    assert recovered["results"] == before["results"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", default=None)
    args = parser.parse_args()
    work = (
        Path(args.work_dir)
        if args.work_dir
        else Path(tempfile.mkdtemp(prefix="mediaflow-task-base-migration-"))
    )
    work.mkdir(parents=True, exist_ok=True)
    base_root = work / "base"
    database = work / "runtime.sqlite3"
    report: dict[str, object] = {"taskBase": TASK_BASE, "workDir": str(work)}
    try:
        _run(
            ["git", "worktree", "add", "--detach", str(base_root), TASK_BASE],
            cwd=ROOT,
            env=dict(os.environ),
        )
        try:
            seeded = _seed_old_database(base_root, database)
            report["seeded"] = seeded
            # Preserve the true schema-45 database before the candidate migrates
            # it, so the additive-ALTER failure injection starts from real base
            # rows rather than from an already-migrated copy.
            old_database = work / "base-old.sqlite3"
            shutil.copyfile(database, old_database)
            old = _read_facts(database)
            report["oldDatabase"] = old
            assert old["schema"] == BASE_SCHEMA, old["schema"]
            assert "recovery_continuations_task_created" not in old["recoveryContinuationIndexes"]
            assert old["hasPreparationTable"] is False
            assert old["manualExecutions"] == 1
            assert {value["status"] for value in old["authorizations"]} == {
                "active",
                "consumed",
            }, old["authorizations"]
            assert len(old["links"]) == 1 and old["links"][0]["status"] == "authorized", old[
                "links"
            ]
            assert any(
                value["revision_id"] == seeded["snapshotId"]
                and value["digest"] == seeded["snapshotDigest"]
                and value["status"] == "active"
                for value in old["revisions"]
            ), old["revisions"]
            migrated = _candidate_round_trip(database, seeded)
            report["migrationAfterOpen"] = migrated["afterOpen"]
            report["migrated"] = migrated["facts"]
            after_open = migrated["afterOpen"]
            final_facts = migrated["facts"]
            assert after_open["schema"] == CANDIDATE_SCHEMA
            assert (
                "recovery_continuations_task_created" in after_open["recoveryContinuationIndexes"]
            )
            assert after_open["hasPreparationTable"] is True
            assert "selected_item_ids_json" in after_open["preparationColumns"]
            assert "allow_overwrite" in after_open["preparationColumns"]
            assert "allow_source_cleanup" in after_open["preparationColumns"]
            for key in (
                "links",
                "authorizations",
                "revisions",
                "previews",
                "results",
                "taskPins",
                "intentPins",
            ):
                assert after_open[key] == old[key], (key, after_open[key], old[key])
            assert after_open["manualExecutions"] == old["manualExecutions"]
            assert final_facts["links"] == old["links"]
            assert final_facts["authorizations"] == old["authorizations"]
            assert final_facts["results"] == old["results"]
            assert final_facts["revisions"] == old["revisions"]
            assert final_facts["taskPins"] == old["taskPins"]
            assert final_facts["intentPins"] == old["intentPins"]
            assert final_facts["manualExecutions"] == old["manualExecutions"]
            assert (
                "recovery_continuations_task_created" in final_facts["recoveryContinuationIndexes"]
            )
            report["legacyIdentityHandling"] = (
                "fresh Worker analysis required; no Provider fallback or old authorization use"
            )
            report["legacyPreparation"] = "actual Task/analysis/intent/Preview references survived"
            # Failure injection runs on a copy of the real base database with an
            # intermediate pre-46 preparation table; it must roll back
            # atomically and then recover on a fault-free reopen.
            _inject_migration_failure(old_database, seeded, work)
            report["failureInjection"] = "rolled back and recovered"
            report["status"] = "PASS"
        finally:
            _run(
                ["git", "worktree", "remove", "--force", str(base_root)],
                cwd=ROOT,
                env=dict(os.environ),
            )
    except Exception as error:  # pragma: no cover - diagnostic path
        report["status"] = "FAIL"
        report["error"] = f"{type(error).__name__}: {error}"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        shutil.rmtree(work, ignore_errors=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
