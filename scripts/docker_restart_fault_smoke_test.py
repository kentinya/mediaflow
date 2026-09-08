#!/usr/bin/env python3
"""Isolated Docker Compose restart/fault acceptance for Task 29.4.

The script builds the exact image, starts an isolated four-service stack on
temporary ``/data`` and media mounts, activates a managed runtime containing one
enabled scan-only Automation Task Definition, proves the Scheduler emits one
durable occurrence across restart, lets the Worker produce FileIndex/Task
evidence, and then injects bounded durable fault fixtures through the installed
package repository inside the container.  It restarts API, Worker, Scheduler and
Notification Worker and verifies durable identities, Worker fencing,
uncertain-mutation refusal and notification at-least-once behavior.

It never reads production paths, credentials, Storage or Providers, and never
uses a remote Storage/Provider service.
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
import urllib.parse
from datetime import UTC, datetime, timedelta
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
RESTART_PROJECT_PREFIX = f"{PROJECT_PREFIX}-restart"
IMAGE_TAG = "mediaflow:task29.4-local"
DEFINITION_ID = "fault-scan"
UNCERTAIN_TASK_ID = "fault-uncertain-task"
UNCERTAIN_ITEM_ID = "fault-uncertain-item"
NOTIFICATION_IDS = {
    "pending": "fault-delivery-pending",
    "retry": "fault-delivery-retry",
    "delivered": "fault-delivery-delivered",
    "dead": "fault-delivery-dead",
    "delivering": "fault-delivery-delivering",
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
        timeout=150.0,
        description=f"Compose services {sorted(services)} healthy",
    )


def add_fault_definition(config_file: Path, source_root: Path) -> None:
    """Add one enabled scan-only definition and one stable media file."""

    media_dir = source_root / "电影"
    media_dir.mkdir(parents=True, exist_ok=True)
    media = media_dir / "One.2001.mkv"
    media.write_bytes((b"fault-restart-media" + b"x" * 256)[:4096])
    old = datetime.now(UTC) - timedelta(hours=2)
    os.utime(media, (old.timestamp(), old.timestamp()))
    source_root.chmod(0o755)
    media_dir.chmod(0o755)
    media.chmod(0o644)

    document = json.loads(config_file.read_text(encoding="utf-8"))
    document["automationTaskDefinitions"] = [
        {
            "id": DEFINITION_ID,
            "name": "Restart fault scan",
            "enabled": True,
            "resourceLibraryId": "source",
            "mode": "scan-only",
            "intervalSeconds": 3600,
            "itemLimit": 10,
        }
    ]
    config_file.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    config_file.chmod(0o644)


def exec_python(
    command: list[str],
    environment: dict[str, str],
    code: str,
    *,
    service: str = "api",
) -> str:
    """Run one installed-package Python fixture inside a Compose service."""

    result = subprocess.run(
        [*command, "exec", "-T", service, "python", "-"],
        cwd=ROOT,
        env=environment,
        input=code,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"container fixture failed in {service}: {detail[:4000]}")
    return result.stdout


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


def occurrences(base: str, token: str, definition_id: str) -> list[dict]:
    path = (
        "/api/v1/automation/task-definitions/"
        f"{urllib.parse.quote(definition_id)}/occurrences?limit=10"
    )
    status, document = json_request(base, path, token)
    if status != 200:
        raise RuntimeError(f"occurrence list returned HTTP {status}: {document}")
    return list(document.get("items") or [])


def collection_ids(base: str, token: str, path: str) -> list[dict]:
    status, document = json_request(base, path, token)
    if status != 200:
        raise RuntimeError(f"durable projection {path} returned HTTP {status}")
    return list(document.get("items") or [])


def wait_occurrences(
    base: str,
    token: str,
    *,
    expected: int,
    timeout: float = 120.0,
) -> list[dict]:
    def reached() -> bool:
        return len(occurrences(base, token, DEFINITION_ID)) == expected

    wait_until(reached, timeout=timeout, description=f"{expected} scheduler occurrences")
    return occurrences(base, token, DEFINITION_ID)


def wait_job_linked_task(base: str, token: str, job_id: str) -> dict:
    def reached() -> bool:
        _, document = json_request(
            base,
            f"/api/v1/jobs/{urllib.parse.quote(job_id)}",
            token,
        )
        return bool(document.get("task_id")) or document.get("status") in {
            "completed",
            "failed",
            "cancelled",
        }

    wait_until(reached, timeout=180.0, description=f"Job {job_id} terminal evidence")
    _, document = json_request(base, f"/api/v1/jobs/{urllib.parse.quote(job_id)}", token)
    return document


def wait_file_index(base: str, token: str, *, minimum: int = 1) -> list[dict]:
    def reached() -> bool:
        items = collection_ids(base, token, "/api/v1/file-index?limit=20")
        return len(items) >= minimum

    wait_until(reached, timeout=180.0, description="persistent FileIndex records")
    return collection_ids(base, token, "/api/v1/file-index?limit=20")


def wait_worker_ready(base: str, token: str) -> dict:
    def reached() -> bool:
        _, readiness = json_request(base, "/api/v1/workers/readiness", token)
        return readiness.get("ready") is True

    wait_until(reached, timeout=120.0, description="processing Worker ready")
    _, readiness = json_request(base, "/api/v1/workers/readiness", token)
    return readiness


def seed_state_code() -> str:
    """Create durable notifications, an uncertain organizer result, and audit/log evidence."""

    return r"""
import json
from datetime import UTC, datetime

from mediaflow.domain.logging import LogLevel, OperationalLogRecord
from mediaflow.domain.notification import (
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationEventType,
)
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
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository

DATABASE = "/data/mediaflow.sqlite3"
NOW = datetime.now(UTC)

with (
    SQLiteTaskRepository(DATABASE) as repository,
    SQLiteConfigurationRepository(DATABASE) as configuration,
):
    active = configuration.get_active_revision()
    if active is None:
        raise RuntimeError("no Active managed revision is present")
    snapshot_id = active.revision_id
    snapshot_digest = active.digest

    if repository.get_task("fault-uncertain-task") is None:
        repository.create_task(
            PersistentTask(
                "fault-uncertain-task",
                "organize",
                PersistentTaskStatus.PARTIAL_SUCCESS,
                True,
                NOW,
                NOW,
                NOW,
                NOW,
                total_items=2,
                completed_items=1,
                failed_items=1,
                configuration_snapshot_id=snapshot_id,
                configuration_snapshot_digest=snapshot_digest,
            )
        )
        repository.upsert_item(
            PersistentTaskItem(
                "fault-success-item",
                "fault-uncertain-task",
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
            )
        )
        repository.upsert_item(
            PersistentTaskItem(
                "fault-uncertain-item",
                "fault-uncertain-task",
                "source-storage",
                "source",
                "Uncertain.2001.mkv",
                "Uncertain.2001.mkv",
                TaskItemStatus.PARTIAL,
                "failed",
                1,
                NOW,
                NOW,
                destination_storage_id="media-target",
                destination_path="Movies/Uncertain (2001)/Uncertain (2001).mkv",
                error="uncertain executor response",
            )
        )
        repository.append_result(
            PersistentResultRecord(
                "fault-success-result",
                "fault-uncertain-task",
                "fault-success-item",
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
                "fault-uncertain-result",
                "fault-uncertain-task",
                "fault-uncertain-item",
                "source-storage",
                "Uncertain.2001.mkv",
                "media-target",
                "Movies/Uncertain (2001)/Uncertain (2001).mkv",
                "C",
                "tmdb",
                "2",
                "metadata-c",
                "naming-a",
                "classification-a",
                "organize-move",
                "MOVE",
                "partial",
                NOW,
                title="Uncertain",
                error="unknown effect",
                completed_operations=("MOVE",),
                effect_certainty="attempted_unverified",
                uncertain_effects=("mutation_outcome",),
            )
        )

    definitions = {
        "fault-delivery-pending": (NotificationDeliveryStatus.PENDING, 0, None),
        "fault-delivery-retry": (NotificationDeliveryStatus.RETRY, 1, "http_503"),
        "fault-delivery-delivered": (NotificationDeliveryStatus.DELIVERED, 1, None),
        "fault-delivery-dead": (NotificationDeliveryStatus.DEAD_LETTER, 2, "http_500"),
        "fault-delivery-delivering": (
            NotificationDeliveryStatus.DELIVERING,
            1,
            None,
        ),
    }
    for index, (delivery_id, (status, attempts, category)) in enumerate(definitions.items()):
        if repository.get_delivery(delivery_id) is None:
            if status is NotificationDeliveryStatus.RETRY:
                response_status = 503
            elif status is NotificationDeliveryStatus.DEAD_LETTER:
                response_status = 500
            else:
                response_status = None
            repository.create_delivery(
                NotificationDelivery(
                    delivery_id,
                    "fault-webhook",
                    f"fault-event-{index}",
                    NotificationEventType.JOB_COMPLETED,
                    "{}",
                    status,
                    attempts,
                    NOW,
                    NOW,
                    NOW,
                    NOW if status == NotificationDeliveryStatus.DELIVERED else None,
                    category,
                    response_status,
                )
            )

    if repository.list_operational_logs(limit=1) == ():
        repository.append_operational_log(
            OperationalLogRecord(
                "fault-restart-log",
                NOW,
                LogLevel.WARN,
                "workflow",
                "uncertain mutation retained for investigation",
                task_id="fault-uncertain-task",
                plan_id="fault-plan",
                status="partial",
            )
        )
    if repository.list_security_audit(limit=1) == ():
        repository.append_security_audit(
            SecurityAuditRecord(
                "fault-restart-audit",
                NOW,
                "deployment-admin",
                "GET",
                "/api/v1/tasks",
                "read",
                "success",
                200,
                "fault-request",
                "127.0.0.1",
            )
        )

    print(
        json.dumps(
            {
                "taskId": "fault-uncertain-task",
                "notifications": len(repository.list_deliveries()),
                "logs": len(repository.list_operational_logs(limit=10)),
                "audits": len(repository.list_security_audit(limit=10)),
            }
        )
    )
"""


def seed_fence_code(job_id: str) -> str:
    """Simulate two Worker processes separated by a durable restart boundary."""

    return """
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from mediaflow.domain.automation import (
    AutomationClaimLost,
    AutomationCommand,
    AutomationJob,
    AutomationJobStatus,
)
from mediaflow.domain.logging import LogLevel, OperationalLogRecord
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository

DATABASE = "/data/mediaflow.sqlite3"
NOW = datetime.now(UTC)
OLD = NOW - timedelta(hours=3)
JOB_ID = __JOB_ID__

with (
    SQLiteTaskRepository(DATABASE) as first_process,
    SQLiteConfigurationRepository(DATABASE) as configuration,
):
    active = configuration.get_active_revision()
    if active is None:
        raise RuntimeError("no Active managed revision is present")
    snapshot_id = active.revision_id
    snapshot_digest = active.digest
    existing = first_process.get_job(JOB_ID)
    if existing is None:
        raise RuntimeError(f"pending Job {JOB_ID} is missing")
    first_process.register_worker(
        "fault-worker-a",
        "fault worker a",
        5.0,
        ("scan", "preview"),
        snapshot_id,
        snapshot_digest,
        SCHEMA_VERSION,
        OLD,
    )
    stale_claim = first_process.claim_next_job(OLD, worker_id="fault-worker-a")
    if stale_claim is None:
        raise RuntimeError("fault worker A could not claim the pending Job")
    stale_claim = replace(stale_claim, claim_token=stale_claim.claim_token)

with (
    SQLiteTaskRepository(DATABASE) as second_process,
    SQLiteConfigurationRepository(DATABASE) as configuration,
):
    active = configuration.get_active_revision()
    snapshot_id = active.revision_id
    snapshot_digest = active.digest
    requeued = second_process.requeue_stale_job(
        JOB_ID,
        NOW - timedelta(hours=2),
        NOW,
    )
    second_process.register_worker(
        "fault-worker-b",
        "fault worker b",
        5.0,
        ("scan", "preview"),
        snapshot_id,
        snapshot_digest,
        SCHEMA_VERSION,
        NOW,
    )
    current_claim = second_process.claim_next_job(NOW, worker_id="fault-worker-b")
    if current_claim is None:
        raise RuntimeError("fault worker B could not claim the requeued Job")
    committed = second_process.complete_claimed_job(
        replace(
            current_claim,
            status=AutomationJobStatus.COMPLETED,
            updated_at=NOW,
            completed_at=NOW,
            task_id="fault-worker-b-task",
        )
    )
    if not committed:
        raise RuntimeError("fault worker B terminal commit failed")
    heartbeat_rejected = False
    try:
        second_process.heartbeat_job(JOB_ID, stale_claim.claim_token, NOW)
    except AutomationClaimLost:
        heartbeat_rejected = True
    stale_committed = second_process.complete_claimed_job(
        replace(
            stale_claim,
            status=AutomationJobStatus.COMPLETED,
            updated_at=NOW,
            completed_at=NOW,
            task_id="fault-worker-a-task",
        )
    )
    second_process.append_operational_log(
        OperationalLogRecord(
            "fault-fence-log",
            NOW,
            LogLevel.WARN,
            "worker",
            "stale Worker heartbeat and terminal commit were rejected",
            job_id=JOB_ID,
            status="running",
        )
    )
    print(
        json.dumps(
            {
                "heartbeatRejected": heartbeat_rejected,
                "staleCommitted": bool(stale_committed),
                "owner": second_process.get_job(JOB_ID).worker_id,
            }
        )
    )
""".replace("__JOB_ID__", json.dumps(job_id))


def restart_fault_smoke(project: str, image: str, keep: bool) -> None:
    token = secrets.token_urlsafe(24)
    api_port = free_port()
    with tempfile.TemporaryDirectory(prefix=f"{RESTART_PROJECT_PREFIX}-") as directory:
        root = Path(directory)
        os.chmod(root, 0o755)
        config_file, environment_file, source_root, target_root = prepare_files(root, token)
        add_fault_definition(config_file, source_root)
        environment = compose_environment(
            root,
            image,
            config_file=config_file,
            environment_file=environment_file,
            source_root=source_root,
            target_root=target_root,
            api_port=api_port,
        )
        command = compose(project)
        expected = {"api", "worker", "scheduler", "notification-worker"}
        try:
            print("Building MediaFlow image...")
            run(
                [
                    "docker",
                    "build",
                    "--file",
                    str(ROOT / "Dockerfile"),
                    "--tag",
                    image,
                    str(ROOT),
                ],
                environment=environment,
            )
            rendered = run(
                ["docker", "compose", "-f", str(ROOT / "compose.yaml"), "config"],
                environment=environment,
            )
            if token in rendered.stdout:
                raise RuntimeError("rendered Compose output contains the deployment API token")
            print("Starting isolated Compose stack...")
            run([*command, "up", "-d", "--no-build"], environment=environment)
            wait_for_services_healthy(command, environment, expected=expected)
            base = f"http://127.0.0.1:{api_port}"
            wait_for_api(base, token)

            print("Stopping Worker and Scheduler before managed activation...")
            run([*command, "stop", "worker", "scheduler"], environment=environment)
            wait_for_api(base, token)

            print("Activating the managed runtime with one scan-only definition...")
            activate_runtime(base, token, config_file)
            identity = active_identity(base, token)

            print("Starting the Scheduler and waiting for one occurrence...")
            run([*command, "start", "scheduler"], environment=environment)
            wait_services_healthy(command, environment, services={"api", "scheduler"})
            first_occurrence = wait_occurrences(base, token, expected=1)

            print("Restarting the Scheduler around the same due slot...")
            run([*command, "restart", "scheduler"], environment=environment)
            wait_services_healthy(command, environment, services={"api", "scheduler"})
            wait_occurrences(base, token, expected=1)
            second_occurrence = occurrences(base, token, DEFINITION_ID)
            if [item["occurrenceId"] for item in second_occurrence] != [
                item["occurrenceId"] for item in first_occurrence
            ]:
                raise RuntimeError("Scheduler restart changed a durable occurrence identity")
            if [item["jobId"] for item in second_occurrence] != [
                item["jobId"] for item in first_occurrence
            ]:
                raise RuntimeError("Scheduler restart changed the linked Job identity")

            print("Starting the Worker and waiting for FileIndex/Task evidence...")
            run([*command, "start", "worker"], environment=environment)
            wait_services_healthy(command, environment, services={"api", "scheduler", "worker"})
            wait_worker_ready(base, token)
            file_items = wait_file_index(base, token)
            if not file_items:
                raise RuntimeError("Worker scan produced no FileIndex records")

            print("Stopping Worker and Notification Worker before fault fixtures...")
            run([*command, "stop", "worker", "notification-worker"], environment=environment)
            wait_for_api(base, token)

            status, submitted = json_request(
                base,
                "/api/v1/jobs",
                token,
                method="POST",
                body={"command": "scan", "limit": 1},
            )
            if status != 202:
                raise RuntimeError(f"fault Job submission returned HTTP {status}: {submitted}")
            fence_job_id = submitted["job_id"]

            print("Seeding durable notification/uncertain/audit/log evidence...")
            seed_output = exec_python(command, environment, seed_state_code())
            seed_summary = json.loads(seed_output.strip().splitlines()[-1])
            if seed_summary["taskId"] != UNCERTAIN_TASK_ID:
                raise RuntimeError("durable fault fixture returned an unexpected Task")

            print("Injecting a stale Worker owner race across repository restart...")
            fence_output = exec_python(command, environment, seed_fence_code(fence_job_id))
            fence_summary = json.loads(fence_output.strip().splitlines()[-1])
            if not fence_summary["heartbeatRejected"] or fence_summary["staleCommitted"]:
                raise RuntimeError(f"stale Worker fencing fixture failed: {fence_summary}")
            if fence_summary["owner"] != "fault-worker-b":
                raise RuntimeError(f"newer Worker owner was not preserved: {fence_summary}")

            baseline = {
                "active": identity,
                "files": [item.get("file_id") or item.get("fileId") for item in file_items],
                "jobs": collection_ids(base, token, "/api/v1/jobs?limit=100"),
                "tasks": collection_ids(base, token, "/api/v1/tasks?limit=100"),
                "occurrences": second_occurrence,
                "notifications": collection_ids(base, token, "/api/v1/notifications?limit=100"),
                "logs": collection_ids(base, token, "/api/v1/logs?limit=100"),
                "audits": collection_ids(base, token, "/api/v1/security-audit?limit=100"),
            }
            baseline_task_ids = {item.get("task_id") for item in baseline["tasks"]}
            if UNCERTAIN_TASK_ID not in baseline_task_ids:
                raise RuntimeError("uncertain fault Task is missing from the API projection")
            baseline_delivery_ids = {item["deliveryId"] for item in baseline["notifications"]}
            if set(NOTIFICATION_IDS.values()) - baseline_delivery_ids:
                raise RuntimeError("seeded notification identities are not visible before restart")

            print("Restarting the API service...")
            run([*command, "restart", "api"], environment=environment)
            wait_for_api(base, token)
            after_api = collection_ids(base, token, "/api/v1/jobs?limit=100")
            if [item["job_id"] for item in after_api] != [
                item["job_id"] for item in baseline["jobs"]
            ]:
                raise RuntimeError("API restart changed durable Job identities")

            print("Restarting the Worker service...")
            run([*command, "start", "worker"], environment=environment)
            wait_services_healthy(command, environment, services={"api", "scheduler", "worker"})
            wait_worker_ready(base, token)
            _, fence_job = json_request(
                base,
                f"/api/v1/jobs/{urllib.parse.quote(fence_job_id)}",
                token,
            )
            if fence_job.get("status") != "completed":
                raise RuntimeError(f"fenced Job is not terminal after Worker restart: {fence_job}")

            print("Restarting the Scheduler service...")
            run([*command, "restart", "scheduler"], environment=environment)
            wait_services_healthy(command, environment, services={"api", "scheduler", "worker"})
            wait_occurrences(base, token, expected=1)
            final_occurrence = occurrences(base, token, DEFINITION_ID)
            if [item["jobId"] for item in final_occurrence] != [
                item["jobId"] for item in baseline["occurrences"]
            ]:
                raise RuntimeError("Scheduler restart changed the linked Job identity")

            print("Restarting the Notification Worker and proving at-least-once...")
            run([*command, "start", "notification-worker"], environment=environment)
            wait_for_services_healthy(command, environment, expected=expected)

            def notification_evidence_settled() -> bool:
                _, notifications = json_request(
                    base,
                    "/api/v1/notifications?limit=100",
                    token,
                )
                values = {item["deliveryId"]: item for item in notifications.get("items", [])}
                if set(NOTIFICATION_IDS.values()) - set(values):
                    return False
                pending = values.get(NOTIFICATION_IDS["pending"])
                delivering = values.get(NOTIFICATION_IDS["delivering"])
                return bool(
                    pending
                    and pending["status"] == "dead-letter"
                    and delivering
                    and delivering["status"] in {"delivering", "delivered", "dead-letter"}
                )

            try:
                wait_until(
                    notification_evidence_settled,
                    timeout=45.0,
                    description="Notification Worker durable at-least-once evidence",
                )
            except RuntimeError as error:
                _, notification_state = json_request(
                    base,
                    "/api/v1/notifications?limit=100",
                    token,
                )
                notification_logs = run(
                    [*command, "logs", "--no-color", "--tail", "200", "notification-worker"],
                    environment=environment,
                )
                raise RuntimeError(
                    "Notification Worker did not settle durable evidence; state="
                    f"{notification_state} logs={notification_logs.stdout[-4000:]}"
                ) from error

            _, notifications = json_request(
                base,
                "/api/v1/notifications?limit=100",
                token,
            )
            final_delivery_ids = {item["deliveryId"] for item in notifications.get("items", [])}
            if final_delivery_ids != baseline_delivery_ids:
                raise RuntimeError(
                    "Notification restart deleted or replaced durable delivery identities"
                )

            print("Verifying API/Web per-item recovery evidence and zero-mutation reads...")
            _, uncertain = json_request(
                base,
                f"/api/v1/tasks/{UNCERTAIN_TASK_ID}/items/{UNCERTAIN_ITEM_ID}",
                token,
            )
            if "investigate" not in uncertain.get("permitted_action_ids", []):
                raise RuntimeError("uncertain item lost its investigation recovery evidence")
            if "retry" in uncertain.get("permitted_action_ids", []):
                raise RuntimeError("uncertain item offered automatic replay")
            if "automatic_replay_refused" not in uncertain.get("refusal_reason", ""):
                raise RuntimeError("uncertain item lost its automatic replay refusal")

            status, ui = http_request(f"{base}/ui/")
            if status != 200 or b"MediaFlow Operator" not in ui:
                raise RuntimeError("Operator Web shell is not reachable")
            status, app_js = http_request(f"{base}/ui/app.js")
            if status != 200:
                raise RuntimeError(f"Operator Web app returned HTTP {status}")
            for marker in (b"showTask", b"showTaskItem", b"renderNotifications"):
                if marker not in app_js:
                    raise RuntimeError(f"Operator Web lacks durable recovery view {marker!r}")

            before_reads = {
                "jobs": len(collection_ids(base, token, "/api/v1/jobs?limit=100")),
                "tasks": len(collection_ids(base, token, "/api/v1/tasks?limit=100")),
                "notifications": len(
                    collection_ids(base, token, "/api/v1/notifications?limit=100")
                ),
            }
            for _ in range(2):
                collection_ids(base, token, "/api/v1/jobs?limit=100")
                collection_ids(base, token, "/api/v1/tasks?limit=100")
                collection_ids(base, token, "/api/v1/notifications?limit=100")
                collection_ids(base, token, "/api/v1/logs?limit=100")
            after_reads = {
                "jobs": len(collection_ids(base, token, "/api/v1/jobs?limit=100")),
                "tasks": len(collection_ids(base, token, "/api/v1/tasks?limit=100")),
                "notifications": len(
                    collection_ids(base, token, "/api/v1/notifications?limit=100")
                ),
            }
            if before_reads != after_reads:
                raise RuntimeError(f"read projections mutated durable state: {after_reads}")

            logs_result = run(
                [*command, "logs", "--no-color", "--tail", "800"],
                environment=environment,
            )
            if token in logs_result.stdout or token in logs_result.stderr:
                raise RuntimeError("service logs contain the deployment API token")
            if secrets.token_urlsafe(8) in config_file.read_text(encoding="utf-8"):
                raise RuntimeError("host configuration fixture leaked a generated secret")

            print("Docker restart/fault smoke acceptance passed.")
        finally:
            if not keep:
                run(
                    [*command, "down", "-v", "--remove-orphans"],
                    environment=environment,
                    check=False,
                )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default=IMAGE_TAG)
    parser.add_argument("--keep", action="store_true", help="keep containers for inspection")
    arguments = parser.parse_args()
    if shutil.which("docker") is None:
        print("Docker engine is unavailable; Docker restart/fault acceptance SKIP")
        return 0
    suffix = f"{os.getpid()}-{int(time.time())}"
    restart_fault_smoke(
        f"{RESTART_PROJECT_PREFIX}-{suffix}",
        arguments.image,
        keep=arguments.keep,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
