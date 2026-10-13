#!/usr/bin/env python3
"""Isolated Docker upgrade/backup/migration recovery acceptance for Task 29.5.

The script builds two local image identities: a genuine immutable Base image
(default the original Task 40.3 Base, schema 38; ``--base-sha``/``--base-schema``
select the Slice Base schema 44 or Task Base schema 45 instead) and the current
candidate image, whose expected schema is read from the candidate's own runtime
constant. It starts the old image
on temporary ``/data`` and media mounts,
activates a managed runtime, seeds representative durable state, stops the
stack, creates and verifies a local backup, runs candidate preflight and
migration rehearsal against disposable copies, injects a migration failure,
proves fail-closed recovery, then upgrades the Compose project to the candidate
image and verifies authenticated API/Web readiness plus durable identities.

It never reads production paths, credentials, Storage or Providers, and never
contacts a registry or remote service.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from docker_health_smoke_test import (
    activate_runtime,
    compose,
    json_request,
    service_records,
    wait_for_services_healthy,
)
from docker_smoke_test import (
    PROJECT_PREFIX,
    compose_environment,
    free_port,
    http_request,
    prepare_files,
    run,
    wait_for_api,
    wait_until,
)

ROOT = Path(__file__).resolve().parents[1]
UPGRADE_PROJECT_PREFIX = f"{PROJECT_PREFIX}-upgrade"
IMAGE_TAG_PREFIX = "mediaflow:task29.5"
#: Defaults preserved for the original schema-38 profile.  ``--base-sha`` /
#: ``--base-schema`` let the same smoke rehearse any other immutable Base (for
#: example the Slice Base schema-44 and Task Base schema-45 candidates).
DEFAULT_BASE_SHA = "360e59e0791c60635f050a0444b1a2d0b4458ea4"
OLD_SCHEMA = 38


def _candidate_schema_version() -> int:
    """The working tree's own runtime schema, read from the real constant.

    The candidate image is built from this checkout, so the expected upgraded
    schema must track the code that is actually built rather than a literal
    that silently goes stale on the next additive bump.
    """

    import re

    source = (ROOT / "mediaflow" / "infrastructure" / "sqlite_runtime.py").read_text(
        encoding="utf-8"
    )
    match = re.search(r"^SCHEMA_VERSION = (\d+)$", source, re.MULTILINE)
    if match is None:
        raise RuntimeError("could not read SCHEMA_VERSION from the candidate runtime")
    return int(match.group(1))


CURRENT_SCHEMA = _candidate_schema_version()
DEFINITION_ID = "upgrade-definition"
SCHEDULE_ID = "hourly-scan"
TASK_ID = "upgrade-task"
JOB_SCHEDULED_ID = "upgrade-scheduled-job"
JOB_COMPLETED_ID = "upgrade-completed-job"
NOTIFICATION_IDS = {
    "pending": "upgrade-delivery-pending",
    "retry": "upgrade-delivery-retry",
    "delivered": "upgrade-delivery-delivered",
    "dead": "upgrade-delivery-dead",
}


def wait_services_healthy(
    command: list[str],
    environment: dict[str, str],
    *,
    services: set[str],
) -> None:
    """Wait only the named running services to become healthy."""

    def healthy() -> bool:
        records = service_records(command, environment)
        return all(
            records.get(service)
            and records[service].get("State") == "running"
            and records[service].get("Health") == "healthy"
            for service in services
        )

    wait_until(
        healthy,
        timeout=180.0,
        description=f"Compose services {sorted(services)} healthy",
    )


def build_image(image: str, context: Path, environment: dict[str, str]) -> None:
    run(
        [
            "docker",
            "build",
            "--file",
            str(context / "Dockerfile"),
            "--tag",
            image,
            str(context),
        ],
        environment=environment,
    )


def prepare_old_context(
    base_sha: str = DEFAULT_BASE_SHA,
) -> tuple[tempfile.TemporaryDirectory, Path]:
    """Create a local old-schema image context without touching repository files.

    The base revision is a parameter so the identical smoke can rehearse any
    immutable Base (the original schema-38 profile, the Slice Base schema 44 or
    the Task Base schema 45) without editing this script.
    """

    directory = tempfile.TemporaryDirectory(prefix="mediaflow-old-schema-")
    context = Path(directory.name)
    archive = subprocess.run(
        ["git", "archive", base_sha],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    subprocess.run(["tar", "-x", "-C", str(context)], input=archive.stdout, check=True)
    return directory, context


def image_volume(project: str) -> str:
    return f"{project}_mediaflow-data"


def run_image(
    image: str,
    volume: str,
    config_file: Path,
    environment_file: Path,
    source_root: Path,
    target_root: Path,
    args: list[str],
) -> subprocess.CompletedProcess[str]:
    """Run one MediaFlow command in the image with the deployment mounts."""

    return subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--user",
            "10001:10001",
            "-v",
            f"{volume}:/data",
            "-v",
            f"{config_file}:/config/mediaflow.json:ro",
            "-v",
            f"{environment_file}:/run/mediaflow/deployment.env:ro",
            "-v",
            f"{source_root}:/media/incoming:ro",
            "-v",
            f"{target_root}:/media/organized",
            "-e",
            "MEDIAFLOW_CONFIG=/config/mediaflow.json",
            "-e",
            "MEDIAFLOW_DATA_DIR=/data",
            "-e",
            "MEDIAFLOW_ENV_FILE=/run/mediaflow/deployment.env",
            image,
            *args,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def run_image_python(image: str, volume: str, code: str) -> subprocess.CompletedProcess[str]:
    """Run one installed-package Python fixture inside the image."""

    return subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-i",
            "--entrypoint",
            "python",
            "--user",
            "10001:10001",
            "-v",
            f"{volume}:/data",
            image,
            "-",
        ],
        cwd=ROOT,
        input=code,
        text=True,
        capture_output=True,
        check=False,
    )


def require_success(result: subprocess.CompletedProcess[str], label: str) -> str:
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"{label} failed ({result.returncode}): {detail[:4000]}")
    return result.stdout


def image_sha256(image: str, volume: str, path: str) -> str:
    result = run_image_python(
        image,
        volume,
        (
            "import hashlib\n"
            f"path={json.dumps(path)}\n"
            "print(hashlib.sha256(open(path,'rb').read()).hexdigest())\n"
        ),
    )
    if result.returncode != 0:
        raise RuntimeError(f"image hash failed: {(result.stderr or result.stdout)[:1000]}")
    return result.stdout.strip()


def active_identity(base: str, token: str) -> dict[str, str]:
    status, management = json_request(base, "/api/v1/management/readiness", token)
    if status != 200:
        raise RuntimeError(f"management readiness returned HTTP {status}")
    active = management.get("active") or {}
    revision_id = active.get("revisionId")
    digest = active.get("digest")
    if not revision_id or not digest:
        raise RuntimeError(f"management readiness lacks an exact Active identity: {management}")
    return {"revisionId": revision_id, "digest": digest}


def collection_items(base: str, token: str, path: str) -> list[dict]:
    status, document = json_request(base, path, token)
    if status != 200:
        raise RuntimeError(f"durable projection {path} returned HTTP {status}")
    return list(document.get("items") or [])


def seed_state_code() -> str:
    """Create representative durable state in the old deployment."""

    return r"""
import hashlib
import json
from datetime import UTC, datetime, timedelta

from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationJob,
    AutomationJobStatus,
)
from mediaflow.domain.file_index import FileIndexRecord
from mediaflow.domain.file_lifecycle import OccurrenceState, ProcessingDisposition
from mediaflow.domain.logging import LogLevel, OperationalLogRecord
from mediaflow.domain.notification import (
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationEventType,
)
from mediaflow.domain.scanner import FileChange, FileScanStatus
from mediaflow.domain.security import SecurityAuditRecord
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository

DATABASE = "/data/mediaflow.sqlite3"
NOW = datetime.now(UTC)

with SQLiteConfigurationRepository(DATABASE) as configuration:
    active = configuration.get_active_revision()
    if active is None:
        raise RuntimeError("no Active managed revision is present")
    snapshot_id = active.revision_id
    snapshot_digest = active.digest
    active_revision = active

with (
    SQLiteTaskRepository(DATABASE) as repository,
    SQLiteFileIndexRepository(DATABASE) as file_index,
):
    if repository.get_task("upgrade-task") is None:
        repository.create_task(
            PersistentTask(
                "upgrade-task",
                "organize",
                PersistentTaskStatus.PARTIAL_SUCCESS,
                True,
                NOW,
                NOW,
                NOW,
                NOW,
                total_items=3,
                completed_items=1,
                failed_items=1,
                configuration_snapshot_id=snapshot_id,
                configuration_snapshot_digest=snapshot_digest,
            )
        )
        for item in (
            PersistentTaskItem(
                "upgrade-success-item",
                "upgrade-task",
                "source-storage",
                "source",
                "Ok.2001.mkv",
                "Ok.2001.mkv",
                TaskItemStatus.SUCCESS,
                "completed",
                1,
                NOW,
                NOW,
                destination_storage_id="media-target",
                destination_path="Movies/Ok (2001)/Ok (2001).mkv",
            ),
            PersistentTaskItem(
                "upgrade-failed-item",
                "upgrade-task",
                "source-storage",
                "source",
                "Failed.2001.mkv",
                "Failed.2001.mkv",
                TaskItemStatus.FAILED,
                "failed",
                1,
                NOW,
                NOW,
                error="pre-mutation storage failure",
            ),
            PersistentTaskItem(
                "upgrade-skipped-item",
                "upgrade-task",
                "source-storage",
                "source",
                "Skip.2001.mkv",
                "Skip.2001.mkv",
                TaskItemStatus.SKIPPED,
                "scanned",
                0,
                NOW,
                NOW,
            ),
        ):
            repository.upsert_item(item)
        repository.append_result(
            PersistentResultRecord(
                "upgrade-success-result",
                "upgrade-task",
                "upgrade-success-item",
                "source-storage",
                "Ok.2001.mkv",
                "media-target",
                "Movies/Ok (2001)/Ok (2001).mkv",
                "C",
                "tmdb",
                "1",
                "metadata-c",
                "naming-a",
                "classification-a",
                "organize-move",
                "MOVE",
                "success",
                NOW,
                title="Ok",
                completed_operations=("MOVE",),
                effect_certainty="verified_complete",
            )
        )
        repository.append_result(
            PersistentResultRecord(
                "upgrade-failed-result",
                "upgrade-task",
                "upgrade-failed-item",
                "source-storage",
                "Failed.2001.mkv",
                "media-target",
                "Movies/Failed (2001)/Failed (2001).mkv",
                "C",
                "tmdb",
                "2",
                "metadata-c",
                "naming-a",
                "classification-a",
                "organize-move",
                "MOVE",
                "failed",
                NOW,
                title="Failed",
                error="pre-mutation storage failure",
                effect_certainty="none",
            )
        )

    if repository.get_job("upgrade-completed-job") is None:
        repository.create_job(
            AutomationJob(
                "upgrade-completed-job",
                AutomationCommand.SCAN,
                AutomationJobStatus.COMPLETED,
                NOW,
                NOW,
                task_id="upgrade-task",
                completed_at=NOW,
                configuration_snapshot_id=snapshot_id,
                configuration_snapshot_digest=snapshot_digest,
            )
        )

    if repository.get_schedule_state("hourly-scan") is None:
        scheduled = AutomationJob(
            "upgrade-scheduled-job",
            AutomationCommand.SCAN,
            AutomationJobStatus.COMPLETED,
            NOW,
            NOW,
            limit=1,
            schedule_id="hourly-scan",
            completed_at=NOW,
            configuration_snapshot_id=snapshot_id,
            configuration_snapshot_digest=snapshot_digest,
        )
        repository.initialize_schedule_state("hourly-scan", NOW + timedelta(hours=1), NOW)
        repository.enqueue_due_schedule(
            "hourly-scan",
            scheduled,
            NOW,
            NOW + timedelta(hours=1),
            NOW,
            100,
        )

    file_index.batch_upsert(
        (
            FileIndexRecord(
                "upgrade-file",
                "source-storage",
                "source",
                "电影/One.2001.mkv",
                "One.2001.mkv",
                "mkv",
                4096,
                NOW - timedelta(hours=2),
                NOW - timedelta(hours=2),
                NOW - timedelta(hours=1),
                NOW - timedelta(hours=1),
                FileScanStatus.READY,
                FileChange.NEW,
                NOW - timedelta(hours=2),
                NOW - timedelta(hours=1),
                occurrence_id="upgrade-file-occurrence",
                fingerprint="a" * 64,
                fingerprint_algorithm="sha256",
                fingerprint_evidence={"sample": "fixture"},
                occurrence_state=OccurrenceState.VERIFIED,
                processing_disposition=ProcessingDisposition.UNKNOWN,
            ),
        )
    )

    for index, (delivery_id, status) in enumerate(
        (
            ("upgrade-delivery-pending", NotificationDeliveryStatus.PENDING),
            ("upgrade-delivery-retry", NotificationDeliveryStatus.RETRY),
            ("upgrade-delivery-delivered", NotificationDeliveryStatus.DELIVERED),
            ("upgrade-delivery-dead", NotificationDeliveryStatus.DEAD_LETTER),
        )
    ):
        if repository.get_delivery(delivery_id) is None:
            attempts = 0 if status is NotificationDeliveryStatus.PENDING else 1
            repository.create_delivery(
                NotificationDelivery(
                    delivery_id,
                    "upgrade-webhook",
                    f"upgrade-event-{index}",
                    NotificationEventType.JOB_COMPLETED,
                    "{}",
                    status,
                    attempts,
                    NOW,
                    NOW,
                    NOW,
                    NOW if status is NotificationDeliveryStatus.DELIVERED else None,
                    None if status is NotificationDeliveryStatus.DELIVERED else "http_500",
                    None if status is NotificationDeliveryStatus.DELIVERED else 500,
                )
            )

    if repository.list_operational_logs(limit=1) == ():
        repository.append_operational_log(
            OperationalLogRecord(
                "upgrade-log",
                NOW,
                LogLevel.INFO,
                "workflow",
                "representative state created before upgrade",
                task_id="upgrade-task",
                job_id="upgrade-completed-job",
                status="partial_success",
            )
        )
    if repository.list_security_audit(limit=1) == ():
        repository.append_security_audit(
            SecurityAuditRecord(
                "upgrade-audit",
                NOW,
                "deployment-admin",
                "GET",
                "/api/v1/tasks",
                "read",
                "success",
                200,
                "upgrade-request",
                "127.0.0.1",
            )
        )

    # Write the assigned historical manual states through the old code's own
    # paths.  This runs inside the genuine prior committed schema-38 image, so
    # the manual intents, Previews, one-shot authorizations, admitted
    # executions and terminal completed/partial/uncertain outcomes below are
    # produced by the old application's own domain objects and repository write
    # paths.  They are real historical rows, not a hand-written newer-format
    # document.

    from dataclasses import replace
    from datetime import timedelta
    from uuid import uuid4

    from mediaflow.domain.manual_execution import (
        ManualExecution,
        ManualExecutionAuthorization,
        ManualExecutionEffect,
        ManualExecutionItem,
        ManualExecutionItemStatus,
        ManualExecutionScopeItem,
        ManualExecutionStatus,
    )
    from mediaflow.domain.manual_organize import (
        ManualChoice,
        ManualConfigurationSnapshot,
        ManualIntentAudit,
        ManualIntentItem,
        ManualIntentItemStatus,
        ManualIntentStatus,
        ManualOrganizeIntent,
        ManualSourceIdentity,
    )
    from mediaflow.domain.manual_organize_preview import (
        ManualOrganizePreview,
        ManualPreviewItem,
        ManualPreviewItemStatus,
        ManualPreviewStatus,
    )

    def canonical(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def fingerprint(value):
        return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()

    def legacy_source(path, name):
        return ManualSourceIdentity(
            f"legacy-file-{name}",
            "source-storage",
            "source",
            path,
            name,
            "mkv",
            512,
            NOW - timedelta(hours=2),
            NOW,
            NOW,
            NOW,
            "ready",
            None,
            f"legacy-occ-{name}",
            "a" * 64,
            "storage-entry-sha256",
            {"source": "storage_entry"},
            "verified",
        )

    def legacy_snapshot():
        # The pinned option projection must be the real projection of the exact
        # managed Active revision, so a historical intent stays readable under
        # the same configuration authority the candidate API resolves.
        from mediaflow.application.manual_organize import ManualOrganizeIntentService
        from mediaflow.infrastructure.runtime_configuration import (
            load_managed_runtime_configuration,
        )

        runtime = load_managed_runtime_configuration(
            active_revision.document, bootstrap_database_path=DATABASE
        )
        return ManualOrganizeIntentService._snapshot_from_runtime(
            runtime, snapshot_id, snapshot_digest
        )

    def legacy_intent(intent_id, items):
        return ManualOrganizeIntent(
            intent_id,
            "upgrade-operator",
            snapshot_id,
            snapshot_digest,
            ManualIntentStatus.OPEN,
            1,
            NOW,
            NOW,
            items,
            legacy_snapshot(),
            "continue to an exact zero-mutation Preview",
            None,
            (),
        )

    def legacy_item(intent_id, item_id, source):
        return ManualIntentItem(
            item_id,
            intent_id,
            0,
            source,
            ManualChoice("A", None, "A", "A", "A"),
            ManualIntentItemStatus.READY,
            None,
            1,
            NOW,
            NOW,
        )

    def legacy_preview(preview_id, intent_id, item, source, target):
        plan = {
            "planId": f"legacy-plan-{source.filename}",
            "operation": "MOVE",
            "zeroMutation": True,
            "executionPlan": {
                "planId": f"legacy-plan-{source.filename}",
                "operation": "MOVE",
                "sourceStorageId": source.storage_id,
                "sourcePath": source.path,
                "targetStorageId": "media-target",
                "targetPath": target,
            },
            "executionState": "ready_for_explicit_authorization",
        }
        preview_item = ManualPreviewItem(
            f"{preview_id}-item",
            preview_id,
            intent_id,
            item.item_id,
            0,
            1,
            item.version,
            source,
            item.choice,
            snapshot_id,
            snapshot_digest,
            source.fingerprint,
            (),
            (),
            (),
            "b" * 64,
            fingerprint(plan),
            ManualPreviewItemStatus.PREVIEWED,
            plan,
            None,
            "inspect this exact zero-mutation plan",
            True,
            "ready_for_explicit_authorization",
            False,
            NOW,
            NOW,
            True,
        )
        return (
            ManualOrganizePreview(
                preview_id,
                intent_id,
                "upgrade-operator",
                1,
                snapshot_id,
                snapshot_digest,
                ManualPreviewStatus.PREVIEWED,
                (preview_item,),
                NOW,
                NOW,
                "inspect each item",
                None,
                True,
                True,
                False,
                None,
                (),
                "file",
                item.item_id,
            ),
            preview_item,
        )

    def legacy_authorization(auth_id, preview_id, intent_id, item, preview_item, source):
        return ManualExecutionAuthorization(
            auth_id,
            preview_id,
            intent_id,
            1,
            snapshot_id,
            snapshot_digest,
            "upgrade-operator",
            "execute_manual_organize",
            True,
            False,
            False,
            (
                ManualExecutionScopeItem(
                    item.item_id,
                    preview_item.preview_item_id,
                    item.version,
                    source.fingerprint,
                    preview_item.plan_fingerprint,
                    source,
                    item.choice,
                ),
            ),
            NOW,
            NOW + timedelta(minutes=10),
        )

    def legacy_execution(execution_id, preview_id, intent_id, auth_id, task_id, item,
                         preview_item, source):
        execution_item = ManualExecutionItem(
            f"{execution_id}-item",
            execution_id,
            preview_id,
            preview_item.preview_item_id,
            intent_id,
            item.item_id,
            task_id,
            f"{task_id}-task-item",
            item.version,
            source.fingerprint,
            preview_item.plan_fingerprint,
            source,
            item.choice,
            preview_item.plan,
            ManualExecutionItemStatus.ADMITTED,
            "admitted",
            None,
            "unknown",
            (),
            (),
            None,
            "wait for exact execution to finish",
            (),
            NOW,
            NOW,
        )
        return ManualExecution(
            execution_id,
            preview_id,
            intent_id,
            auth_id,
            task_id,
            "upgrade-operator",
            1,
            snapshot_id,
            snapshot_digest,
            (item.item_id,),
            (),
            (execution_item,),
            ManualExecutionStatus.ADMITTED,
            "inspect each exact execution item",
            None,
            False,
            False,
            NOW,
            NOW,
            None,
        )

    def admit(name, source, execution_status, item_status, result_status, certainty,
              operations, uncertain):
        item = legacy_item(f"intent-{name}", f"item-{name}", source)
        repository.create_manual_intent_with_audit(
            legacy_intent(f"intent-{name}", (item,)),
            (item,),
            ManualIntentAudit(
                f"audit-{name}", f"intent-{name}", None, "upgrade-operator",
                "created", {}, {}, NOW,
            ),
        )
        target = f"Movies/Legacy {name} (2002)/Legacy {name} (2002).mkv"
        preview_value, preview_item = legacy_preview(
            f"preview-{name}", f"intent-{name}", item, source, target
        )
        repository.create_manual_preview(preview_value, preview_value.items)
        auth = legacy_authorization(
            f"auth-{name}", f"preview-{name}", f"intent-{name}", item, preview_item, source
        )
        repository.create_manual_execution_authorization(auth)
        execution_value = legacy_execution(
            f"exec-{name}", f"preview-{name}", f"intent-{name}", f"auth-{name}",
            f"task-{name}", item, preview_item, source,
        )
        repository.admit_manual_execution(
            auth,
            execution_value,
            (execution_value.items[0],),
            (("source-storage", source.path), ("media-target", target)),
            NOW,
        )
        if execution_status is ManualExecutionStatus.ADMITTED:
            return
        admitted = repository.get_manual_execution(f"exec-{name}")
        terminal_item = replace(
            admitted.items[0],
            status=item_status,
            stage="completed" if item_status is ManualExecutionItemStatus.SUCCESS else "failed",
            result_id=f"legacy-result-{name}",
            effect_certainty=certainty,
            completed_operations=operations,
            uncertain_effects=uncertain,
            error=None if item_status is ManualExecutionItemStatus.SUCCESS else f"{name} failure",
            next_action="inspect the durable Result",
            updated_at=NOW,
        )
        terminal_execution = replace(
            admitted,
            items=(terminal_item,),
            status=execution_status,
            next_action="inspect each item outcome",
            updated_at=NOW,
            completed_at=NOW,
        )
        task_item = PersistentTaskItem(
            terminal_item.task_item_id,
            f"task-{name}",
            "source-storage",
            "source",
            source.path,
            f"source-storage:{source.path}",
            (
                TaskItemStatus.SUCCESS
                if item_status is ManualExecutionItemStatus.SUCCESS
                else TaskItemStatus.FAILED
            ),
            terminal_item.stage,
            1,
            NOW,
            NOW,
            plan_id=terminal_item.plan.get("planId"),
            destination_storage_id="media-target",
            destination_path=target,
            error=terminal_item.error,
            source_occurrence_id=source.occurrence_id,
            source_fingerprint=source.fingerprint,
            source_fingerprint_state="verified",
        )
        task = PersistentTask(
            f"task-{name}",
            "manual_organize",
            (
                PersistentTaskStatus.COMPLETED
                if execution_status is ManualExecutionStatus.COMPLETED
                else PersistentTaskStatus.PARTIAL_SUCCESS
            ),
            True,
            NOW,
            NOW,
            NOW,
            NOW,
            1,
            1 if item_status is ManualExecutionItemStatus.SUCCESS else 0,
            0 if item_status is ManualExecutionItemStatus.SUCCESS else 1,
            None,
            False,
            None,
            1,
            snapshot_id,
            snapshot_digest,
        )
        result = PersistentResultRecord(
            f"legacy-result-{name}",
            f"task-{name}",
            terminal_item.task_item_id,
            "source-storage",
            source.path,
            "media-target",
            target,
            "A",
            "tmdb",
            "1",
            "A",
            "A",
            "A",
            "A",
            "MOVE",
            result_status,
            NOW,
            title=f"Legacy {name}",
            completed_operations=operations,
            effect_certainty=certainty,
            uncertain_effects=uncertain,
            error=terminal_item.error,
        )
        effect = ManualExecutionEffect(
            f"legacy-effect-{name}",
            terminal_item.execution_item_id,
            0,
            "MOVE",
            "source-storage",
            source.path,
            "media-target",
            target,
            certainty == "verified_complete",
            certainty,
            {},
            NOW,
        )
        repository.complete_manual_execution_item(
            terminal_execution,
            terminal_item,
            task_item,
            task,
            result,
            (effect,),
            (("source-storage", source.path), ("media-target", target)),
        )

    admit(
        "admitted",
        legacy_source("电影/LegacyAdmitted.2001.mkv", "LegacyAdmitted.2001.mkv"),
        ManualExecutionStatus.ADMITTED,
        ManualExecutionItemStatus.ADMITTED,
        "dry_run",
        "unknown",
        (),
        (),
    )
    admit(
        "completed",
        legacy_source("电影/LegacyCompleted.2002.mkv", "LegacyCompleted.2002.mkv"),
        ManualExecutionStatus.COMPLETED,
        ManualExecutionItemStatus.SUCCESS,
        "SUCCESS",
        "verified_complete",
        ("MOVE",),
        (),
    )
    admit(
        "partial",
        legacy_source("电影/LegacyPartial.2003.mkv", "LegacyPartial.2003.mkv"),
        ManualExecutionStatus.PARTIAL_SUCCESS,
        ManualExecutionItemStatus.FAILED,
        "FAILED",
        "none",
        (),
        (),
    )
    admit(
        "uncertain",
        legacy_source("电影/LegacyUncertain.2004.mkv", "LegacyUncertain.2004.mkv"),
        ManualExecutionStatus.PARTIAL_SUCCESS,
        ManualExecutionItemStatus.PARTIAL,
        "PARTIAL",
        "attempted_unverified",
        ("MOVE",),
        ("mutation_outcome",),
    )

    print(
        json.dumps(
            {
                "schema": repository.schema_version,
                "taskId": "upgrade-task",
                "fileId": "upgrade-file",
                "notifications": len(repository.list_deliveries()),
                "manualIntents": len(repository.list_manual_intents(limit=50)),
                "manualExecutions": sorted(
                    value.execution_id for value in repository.list_manual_executions_for_intent(
                        "intent-admitted", limit=10
                    )
                ),
            }
        )
    )
"""


def failure_backup_code() -> str:
    """Create a schema-30 backup that must fail deterministically on rehearsal."""

    return r'''
import sqlite3
from pathlib import Path

path = Path("/data/failure-backup.sqlite3")
if path.exists():
    path.unlink()
connection = sqlite3.connect(path)
connection.execute(
    "CREATE TABLE schema_version (component TEXT PRIMARY KEY, version INTEGER NOT NULL)"
)
connection.execute("INSERT INTO schema_version VALUES ('runtime', 30)")
connection.execute(
    """CREATE TABLE unattended_execution_grants (
        grant_id TEXT PRIMARY KEY, definition_id TEXT NOT NULL,
        resource_library_id TEXT NOT NULL, source_scope TEXT,
        run_mode TEXT NOT NULL, max_items_per_run INTEGER NOT NULL,
        status TEXT NOT NULL, granting_principal TEXT NOT NULL,
        granted_at TEXT NOT NULL, revoking_principal TEXT,
        revoked_at TEXT, reason TEXT, definition_fingerprint TEXT NOT NULL,
        configuration_snapshot_id TEXT NOT NULL,
        configuration_snapshot_digest TEXT NOT NULL,
        configuration_snapshot_version INTEGER NOT NULL
    )"""
)
connection.execute(
    """CREATE TABLE unattended_execution_grant_audit (
        audit_id TEXT PRIMARY KEY, grant_id TEXT NOT NULL,
        action TEXT NOT NULL, occurred_at TEXT NOT NULL,
        actor TEXT, details_json TEXT NOT NULL
    )"""
)
row = (
    "legacy-grant",
    "legacy-definition",
    "resource",
    None,
    "automatic-organization",
    2,
    "active",
    "admin",
    "2026-01-01T00:00:00+00:00",
    None,
    None,
    None,
    "b" * 64,
    "revision-legacy",
    "c" * 64,
    1,
)
connection.execute(
    """INSERT INTO unattended_execution_grants VALUES (
        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
    )""",
    row,
)
connection.execute(
    """INSERT INTO unattended_execution_grants VALUES (
        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
    )""",
    ("legacy-grant-2", *row[1:]),
)
connection.execute(
    """INSERT INTO unattended_execution_grant_audit VALUES (
        ?, ?, ?, ?, ?, ?
    )""",
    ("legacy-audit", "legacy-grant", "granted", "2026-01-01T00:00:00+00:00", "admin", "{}"),
)
connection.commit()
connection.close()
print("failure backup created")
'''


def restore_probe_code() -> str:
    """Probe non-overwriting restore and sidecar rejection inside the image."""

    return r"""
import json
import os
from pathlib import Path

from mediaflow.infrastructure.sqlite_restore import SQLiteRestoreService

occupied = False
sidecar_rejected = False
restored = False
try:
    SQLiteRestoreService(
        "/data/upgrade-backup.sqlite3",
        "/data/mediaflow.sqlite3",
    ).restore(confirmed_empty_destination=True)
except ValueError:
    occupied = True

destination = Path("/data/sidecar-restore.sqlite3")
sidecar = Path("/data/sidecar-restore.sqlite3-wal")
sidecar.write_bytes(b"occupied")
try:
    SQLiteRestoreService(
        "/data/upgrade-backup.sqlite3",
        destination,
    ).restore(confirmed_empty_destination=True)
except ValueError:
    sidecar_rejected = True
sidecar.unlink()
if destination.exists():
    destination.unlink()

result = SQLiteRestoreService(
    "/data/upgrade-backup.sqlite3",
    "/data/restore-ok.sqlite3",
).restore(confirmed_empty_destination=True)
restored = True
print(
    json.dumps(
        {
        "occupiedRejected": occupied,
        "sidecarRejected": sidecar_rejected,
        "restored": restored,
        "schema": result.schema_version,
        }
    )
)
"""


def upgrade_recovery_smoke(
    project: str,
    keep: bool,
    *,
    base_sha: str = DEFAULT_BASE_SHA,
    base_schema: int = OLD_SCHEMA,
) -> None:
    suffix = f"{os.getpid()}-{int(time.time())}"
    old_image = f"{IMAGE_TAG_PREFIX}-old-{suffix}"
    new_image = f"{IMAGE_TAG_PREFIX}-new-{suffix}"
    token = secrets.token_urlsafe(24)
    api_port = free_port()
    old_context_handle: tempfile.TemporaryDirectory | None = None
    with tempfile.TemporaryDirectory(prefix=f"{UPGRADE_PROJECT_PREFIX}-") as directory:
        root = Path(directory)
        os.chmod(root, 0o755)
        config_file, environment_file, source_root, target_root = prepare_files(root, token)
        # A real ResourceLibrary-relative source for the post-upgrade discovery
        # persistence check.  The source mount stays read-only in production, so
        # the file is created on the host before the stack starts.
        (source_root / "电影").mkdir(parents=True, exist_ok=True)
        (source_root / "电影" / "Upgrade.2001.mkv").write_bytes(b"post-upgrade discovery media")
        for child in source_root.rglob("*"):
            child.chmod(0o755 if child.is_dir() else 0o644)
        environment = compose_environment(
            root,
            old_image,
            config_file=config_file,
            environment_file=environment_file,
            source_root=source_root,
            target_root=target_root,
            api_port=api_port,
        )
        environment_new = dict(environment)
        environment_new["MEDIAFLOW_IMAGE"] = new_image
        command = compose(project)
        volume = image_volume(project)
        expected = {"api", "worker", "scheduler", "notification-worker"}
        try:
            print("Building candidate image...")
            build_image(new_image, ROOT, environment)
            print(f"Building genuine Base {base_sha[:12]} schema-{base_schema} image...")
            old_context_handle, old_context = prepare_old_context(base_sha)
            build_image(old_image, old_context, environment)

            print("Starting old-schema Compose deployment...")
            run([*command, "up", "-d", "--no-build"], environment=environment)
            wait_for_services_healthy(command, environment, expected=expected)
            base = f"http://127.0.0.1:{api_port}"
            wait_for_api(base, token)
            run(
                [*command, "stop", "worker", "scheduler", "notification-worker"],
                environment=environment,
            )
            wait_for_api(base, token)

            print("Activating managed runtime and seeding representative state...")
            activate_runtime(base, token, config_file)
            identity = active_identity(base, token)
            seed_result = run_image_python(old_image, volume, seed_state_code())
            seed_output = require_success(seed_result, "seed state")
            summary = json.loads(seed_output.strip().splitlines()[-1])
            if summary["schema"] != base_schema:
                raise RuntimeError(
                    f"old deployment schema is {summary['schema']}, expected {base_schema}"
                )

            baseline = {
                "active": identity,
                "files": collection_items(base, token, "/api/v1/file-index?limit=20"),
                "jobs": collection_items(base, token, "/api/v1/jobs?limit=100"),
                "tasks": collection_items(base, token, "/api/v1/tasks?limit=100"),
                "notifications": collection_items(base, token, "/api/v1/notifications?limit=100"),
                "logs": collection_items(base, token, "/api/v1/logs?limit=100"),
                "audits": collection_items(base, token, "/api/v1/security-audit?limit=100"),
                "schedule_audit": collection_items(
                    base,
                    token,
                    f"/api/v1/schedules/{SCHEDULE_ID}/audit?limit=10",
                ),
            }
            task_ids = {item.get("task_id") for item in baseline["tasks"]}
            if TASK_ID not in task_ids:
                raise RuntimeError("seeded Task is not visible before upgrade")

            print("Stopping old stack and creating a verified backup...")
            run([*command, "stop"], environment=environment)
            backup_result = run_image(
                old_image,
                volume,
                config_file,
                environment_file,
                source_root,
                target_root,
                ["database", "backup", "--output", "/data/upgrade-backup.sqlite3"],
            )
            require_success(backup_result, "database backup")
            verify_result = run_image(
                old_image,
                volume,
                config_file,
                environment_file,
                source_root,
                target_root,
                ["database", "verify", "/data/upgrade-backup.sqlite3"],
            )
            verify_output = require_success(verify_result, "database verify")
            if "Schema: " + str(base_schema) not in verify_output:
                raise RuntimeError(f"verified backup schema is not {base_schema}: {verify_output}")
            live_before = image_sha256(new_image, volume, "/data/mediaflow.sqlite3")
            backup_before = image_sha256(new_image, volume, "/data/upgrade-backup.sqlite3")

            print("Running candidate preflight and migration rehearsal...")
            check_result = run_image(
                new_image,
                volume,
                config_file,
                environment_file,
                source_root,
                target_root,
                ["upgrade", "check", "--backup", "/data/upgrade-backup.sqlite3"],
            )
            check_output = require_success(check_result, "upgrade preflight")
            if "Status: MIGRATION_REQUIRED" not in check_output:
                raise RuntimeError(f"candidate preflight did not require migration: {check_output}")
            rehearsal_result = run_image(
                new_image,
                volume,
                config_file,
                environment_file,
                source_root,
                target_root,
                ["upgrade", "rehearse", "--backup", "/data/upgrade-backup.sqlite3"],
            )
            rehearsal_output = require_success(rehearsal_result, "migration rehearsal")
            if "Status: PASS" not in rehearsal_output:
                raise RuntimeError(f"migration rehearsal did not pass: {rehearsal_output}")
            if live_before != image_sha256(new_image, volume, "/data/mediaflow.sqlite3"):
                raise RuntimeError("preflight/rehearsal mutated the live database")
            if backup_before != image_sha256(new_image, volume, "/data/upgrade-backup.sqlite3"):
                raise RuntimeError("preflight/rehearsal mutated the verified backup")

            print("Injecting a deterministic migration failure...")
            failure_result = run_image_python(new_image, volume, failure_backup_code())
            require_success(failure_result, "failure backup creation")
            failure_before = image_sha256(new_image, volume, "/data/failure-backup.sqlite3")
            failed_rehearsal = run_image(
                new_image,
                volume,
                config_file,
                environment_file,
                source_root,
                target_root,
                ["upgrade", "rehearse", "--backup", "/data/failure-backup.sqlite3"],
            )
            if failed_rehearsal.returncode == 0:
                raise RuntimeError("injected migration failure unexpectedly passed rehearsal")
            if token in failed_rehearsal.stdout or token in failed_rehearsal.stderr:
                raise RuntimeError("migration failure output leaked the deployment token")
            if live_before != image_sha256(new_image, volume, "/data/mediaflow.sqlite3"):
                raise RuntimeError("migration failure mutated the live database")
            if failure_before != image_sha256(new_image, volume, "/data/failure-backup.sqlite3"):
                raise RuntimeError("migration failure mutated its source backup")

            print("Re-running the verified compatibility gate after failure...")
            check_result = run_image(
                new_image,
                volume,
                config_file,
                environment_file,
                source_root,
                target_root,
                ["upgrade", "check", "--backup", "/data/upgrade-backup.sqlite3"],
            )
            require_success(check_result, "post-failure upgrade preflight")
            rehearsal_result = run_image(
                new_image,
                volume,
                config_file,
                environment_file,
                source_root,
                target_root,
                ["upgrade", "rehearse", "--backup", "/data/upgrade-backup.sqlite3"],
            )
            require_success(rehearsal_result, "post-failure migration rehearsal")
            if live_before != image_sha256(new_image, volume, "/data/mediaflow.sqlite3"):
                raise RuntimeError("post-failure gate mutated the live database")

            print("Probing non-overwriting restore and sidecar rejection...")
            restore_probe = run_image_python(new_image, volume, restore_probe_code())
            restore_output = require_success(restore_probe, "restore probe")
            restore_summary = json.loads(restore_output.strip().splitlines()[-1])
            if (
                not restore_summary["occupiedRejected"]
                or not restore_summary["sidecarRejected"]
                or not restore_summary["restored"]
            ):
                raise RuntimeError(f"restore probe did not pass: {restore_summary}")

            print("Upgrading the Compose project to the candidate image...")
            run(
                [*command, "up", "-d", "--no-deps", "--force-recreate", "api"],
                environment=environment_new,
            )
            wait_for_api(base, token)
            wait_services_healthy(
                command,
                environment_new,
                services={"api"},
            )
            run(
                [*command, "up", "-d", "--force-recreate"],
                environment=environment_new,
            )
            wait_for_services_healthy(command, environment_new, expected=expected)

            def worker_ready() -> bool:
                _, readiness = json_request(base, "/api/v1/workers/readiness", token)
                return readiness.get("ready") is True

            wait_until(worker_ready, timeout=180.0, description="candidate Worker ready")

            print("Verifying candidate API/Web durability...")
            status, system = json_request(base, "/api/v1/system/status", token)
            runtime_schema = (system.get("system") or {}).get("runtime_schema_version")
            if status != 200 or runtime_schema != CURRENT_SCHEMA:
                raise RuntimeError(f"candidate runtime schema is not {CURRENT_SCHEMA}: {system}")
            _, management = json_request(base, "/api/v1/management/readiness", token)
            if (management.get("active") or {}).get("revisionId") != identity["revisionId"]:
                raise RuntimeError("candidate Active identity changed after upgrade")

            final_files = collection_items(base, token, "/api/v1/file-index?limit=20")
            if [item.get("file_id") for item in final_files] != [
                item.get("file_id") for item in baseline["files"]
            ]:
                raise RuntimeError("FileIndex identities changed after upgrade")
            final_jobs = collection_items(base, token, "/api/v1/jobs?limit=100")
            baseline_job_ids = {item["job_id"] for item in baseline["jobs"]}
            final_job_ids = {item["job_id"] for item in final_jobs}
            if not baseline_job_ids <= final_job_ids:
                raise RuntimeError("Job identities were lost after upgrade")
            final_tasks = collection_items(base, token, "/api/v1/tasks?limit=100")
            if [item["task_id"] for item in final_tasks] != [
                item["task_id"] for item in baseline["tasks"]
            ]:
                raise RuntimeError("Task identities changed after upgrade")
            final_notifications = collection_items(base, token, "/api/v1/notifications?limit=100")
            if {item["deliveryId"] for item in final_notifications} != {
                item["deliveryId"] for item in baseline["notifications"]
            }:
                raise RuntimeError("notification identities changed after upgrade")
            final_logs = collection_items(base, token, "/api/v1/logs?limit=100")
            if {item["log_id"] for item in final_logs} != {
                item["log_id"] for item in baseline["logs"]
            }:
                raise RuntimeError("operational-log identities changed after upgrade")
            final_audits = collection_items(base, token, "/api/v1/security-audit?limit=100")
            baseline_audit_ids = {item.get("audit_id") for item in baseline["audits"]}
            final_audit_ids = {item.get("audit_id") for item in final_audits}
            if not baseline_audit_ids <= final_audit_ids:
                raise RuntimeError("security-audit identities were lost after upgrade")
            final_schedule = collection_items(
                base,
                token,
                f"/api/v1/schedules/{SCHEDULE_ID}/audit?limit=10",
            )
            if [item["audit_id"] for item in final_schedule] != [
                item["audit_id"] for item in baseline["schedule_audit"]
            ]:
                raise RuntimeError("schedule occurrence identities changed after upgrade")
            _, failed_item = json_request(
                base,
                "/api/v1/tasks/upgrade-task/items/upgrade-failed-item",
                token,
            )
            if failed_item.get("status") != "failed":
                raise RuntimeError("failed per-item disposition changed after upgrade")
            _, success_item = json_request(
                base,
                "/api/v1/tasks/upgrade-task/items/upgrade-success-item",
                token,
            )
            if success_item.get("status") != "success":
                raise RuntimeError("success per-item disposition changed after upgrade")

            # The genuine prior-committed manual work must survive the upgrade
            # with its own intent, Preview, admitted execution and terminal
            # completed/partial/uncertain outcomes intact.
            # The terminal historical states must be preserved exactly.  The
            # one historically *admitted* execution is genuine claimable work:
            # the live candidate Worker may claim it, so it must stay readable
            # and must never fabricate a verified effect it never performed.
            expected_manual = {
                "completed": ("completed", "success", "verified_complete"),
                "partial": ("partial_success", "failed", "none"),
                "uncertain": ("partial_success", "partial", "attempted_unverified"),
            }
            for name in ("admitted", *expected_manual):
                status, intent_document = json_request(
                    base, f"/api/v1/operations/organize/intents/intent-{name}", token
                )
                if status != 200:
                    raise RuntimeError(
                        f"legacy manual intent {name} is unreadable after upgrade: HTTP {status}"
                    )
                status, execution_document = json_request(
                    base,
                    f"/api/v1/operations/organize/executions?intentId=intent-{name}&limit=10",
                    token,
                )
                if status != 200 or len(execution_document.get("items") or []) != 1:
                    raise RuntimeError(
                        f"legacy manual execution {name} is unreadable after upgrade: "
                        f"HTTP {status} {execution_document}"
                    )
                execution_id = execution_document["items"][0]["executionId"]
                status, execution_detail = json_request(
                    base,
                    f"/api/v1/operations/organize/executions/{execution_id}",
                    token,
                )
                if status != 200:
                    raise RuntimeError(
                        f"legacy manual execution detail {name} is unreadable: HTTP {status}"
                    )
                item_document = (execution_detail.get("items") or [{}])[0]
                if name == "admitted":
                    if execution_detail.get("status") not in {
                        "admitted",
                        "running",
                        "partial_success",
                        "failed",
                        "completed",
                    }:
                        raise RuntimeError(
                            "legacy admitted execution lost its durable state: "
                            f"{execution_detail.get('status')}"
                        )
                    if item_document.get("effectCertainty") == "verified_complete":
                        raise RuntimeError(
                            "the upgrade fabricated a verified effect for admitted work"
                        )
                    continue
                execution_status, item_status, certainty = expected_manual[name]
                if (
                    execution_detail.get("status") != execution_status
                    or item_document.get("status") != item_status
                    or item_document.get("effectCertainty") != certainty
                ):
                    raise RuntimeError(
                        f"legacy manual state {name} changed across the upgrade: {execution_detail}"
                    )
            # Historical manual work gains no discovery scope or new authority.
            status, discovery_list = json_request(
                base, "/api/v1/operations/organize/discoveries", token
            )
            if status != 200 or (discovery_list.get("items") or []):
                raise RuntimeError(
                    f"the upgraded database fabricated discovery scope: {discovery_list}"
                )
            # The new discovery boundary persists real work after the upgrade.
            status, admitted_discovery = json_request(
                base,
                "/api/v1/resource-libraries/source/files/discoveries",
                token,
                method="POST",
                body={"paths": ["电影"]},
            )
            if status != 202 or not admitted_discovery.get("discoveryId"):
                raise RuntimeError(
                    f"post-upgrade discovery admission failed: {status} {admitted_discovery}"
                )
            discovery_id = admitted_discovery["discoveryId"]
            settled = None
            for _ in range(60):
                _, settled = json_request(
                    base,
                    f"/api/v1/operations/organize/discoveries/{discovery_id}",
                    token,
                )
                if settled.get("status") not in {"queued", "running"}:
                    break
                time.sleep(0.5)
            if settled is None or settled.get("status") != "completed":
                raise RuntimeError(f"post-upgrade discovery did not complete: {settled}")

            status, ui = http_request(f"{base}/ui/")
            if status != 200 or b"MediaFlow Operator" not in ui:
                raise RuntimeError("Operator Web shell is not reachable after upgrade")
            status, app_js = http_request(f"{base}/ui/app.js")
            if status != 200:
                raise RuntimeError(f"Operator Web app returned HTTP {status}")
            for marker in (b"showTask", b"showTaskItem", b"renderSystem"):
                if marker not in app_js:
                    raise RuntimeError(f"Operator Web lacks durable view marker {marker!r}")

            before_reads = {
                "jobs": len(final_jobs),
                "tasks": len(final_tasks),
                "notifications": len(final_notifications),
            }
            for _ in range(2):
                collection_items(base, token, "/api/v1/jobs?limit=100")
                collection_items(base, token, "/api/v1/tasks?limit=100")
                collection_items(base, token, "/api/v1/notifications?limit=100")
            after_reads = {
                "jobs": len(collection_items(base, token, "/api/v1/jobs?limit=100")),
                "tasks": len(collection_items(base, token, "/api/v1/tasks?limit=100")),
                "notifications": len(
                    collection_items(base, token, "/api/v1/notifications?limit=100")
                ),
            }
            if before_reads != after_reads:
                raise RuntimeError(f"read projections mutated durable state: {after_reads}")
            logs_result = run(
                [*command, "logs", "--no-color", "--tail", "800"],
                environment=environment_new,
            )
            if token in logs_result.stdout or token in logs_result.stderr:
                raise RuntimeError("service logs contain the deployment API token")
            if secrets.token_urlsafe(8) in config_file.read_text(encoding="utf-8"):
                raise RuntimeError("host configuration fixture leaked a generated secret")

            print("Docker upgrade/recovery smoke acceptance passed.")
        finally:
            if old_context_handle is not None:
                old_context_handle.cleanup()
            if not keep:
                run(
                    [*command, "down", "-v", "--remove-orphans"],
                    environment=environment_new,
                    check=False,
                )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true", help="keep containers for inspection")
    parser.add_argument(
        "--base-sha",
        default=DEFAULT_BASE_SHA,
        help=(
            "immutable Base git revision whose own runtime seeds the old-schema volume "
            f"(default: {DEFAULT_BASE_SHA}, schema {OLD_SCHEMA})"
        ),
    )
    parser.add_argument(
        "--base-schema",
        type=int,
        default=OLD_SCHEMA,
        help=f"the runtime schema the Base revision creates (default: {OLD_SCHEMA})",
    )
    arguments = parser.parse_args()
    if shutil.which("docker") is None:
        print("Docker engine is unavailable; Docker upgrade/recovery acceptance SKIP")
        return 0
    project = f"{UPGRADE_PROJECT_PREFIX}-{os.getpid()}-{int(time.time())}"
    upgrade_recovery_smoke(
        project,
        keep=arguments.keep,
        base_sha=arguments.base_sha,
        base_schema=arguments.base_schema,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
