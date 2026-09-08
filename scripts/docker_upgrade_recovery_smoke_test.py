#!/usr/bin/env python3
"""Isolated Docker upgrade/backup/migration recovery acceptance for Task 29.5.

The script builds two local image identities: a synthetic old-schema image whose
runtime schema marker is pinned to 32 and the current candidate image (schema
33).  It starts the old image on temporary ``/data`` and media mounts,
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
OLD_SCHEMA = 32
CURRENT_SCHEMA = 33
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


def prepare_old_context() -> tuple[tempfile.TemporaryDirectory, Path]:
    """Create a local old-schema image context without touching repository files."""

    directory = tempfile.TemporaryDirectory(prefix="mediaflow-old-schema-")
    context = Path(directory.name)
    archive = subprocess.run(
        ["git", "archive", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["tar", "-x", "-C", str(context)],
        input=archive.stdout,
        check=True,
    )
    runtime = context / "mediaflow" / "infrastructure" / "sqlite_runtime.py"
    automation = context / "mediaflow" / "application" / "automation.py"
    source = runtime.read_text(encoding="utf-8")
    runtime.write_text(
        source.replace(f"SCHEMA_VERSION = {CURRENT_SCHEMA}", f"SCHEMA_VERSION = {OLD_SCHEMA}"),
        encoding="utf-8",
    )
    source = automation.read_text(encoding="utf-8")
    automation.write_text(
        source.replace(
            f"runtime_schema_version: int = {CURRENT_SCHEMA},",
            f"runtime_schema_version: int = {OLD_SCHEMA},",
        ),
        encoding="utf-8",
    )
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

    print(
        json.dumps(
            {
                "schema": repository.schema_version,
                "taskId": "upgrade-task",
                "fileId": "upgrade-file",
                "notifications": len(repository.list_deliveries()),
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


def upgrade_recovery_smoke(project: str, keep: bool) -> None:
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
            print("Building synthetic old-schema image...")
            old_context_handle, old_context = prepare_old_context()
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
            if summary["schema"] != OLD_SCHEMA:
                raise RuntimeError(
                    f"old deployment schema is {summary['schema']}, expected {OLD_SCHEMA}"
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
            if "Schema: " + str(OLD_SCHEMA) not in verify_output:
                raise RuntimeError(f"verified backup schema is not {OLD_SCHEMA}: {verify_output}")
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
    arguments = parser.parse_args()
    if shutil.which("docker") is None:
        print("Docker engine is unavailable; Docker upgrade/recovery acceptance SKIP")
        return 0
    project = f"{UPGRADE_PROJECT_PREFIX}-{os.getpid()}-{int(time.time())}"
    upgrade_recovery_smoke(project, keep=arguments.keep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
