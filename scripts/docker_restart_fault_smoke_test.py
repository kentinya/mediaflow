#!/usr/bin/env python3
"""Isolated Docker Compose restart/fault acceptance for Task 29.4.

The script builds the exact image, starts an isolated four-service stack on
temporary ``/data`` and media mounts, activates a managed runtime containing one
enabled automatic-organization definition, proves the Scheduler emits one
durable definition-bound Job across restart, lets the Worker produce Task
and Result evidence, and then injects bounded durable fault fixtures through the installed
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
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from docker_health_smoke_test import (
    activate_runtime,
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
DEFINITION_ID = "fault-automatic"
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


def add_fault_schedule(config_file: Path, source_root: Path) -> None:
    """Add one enabled definition and one stable media file."""

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
    document.setdefault("api", {})["remoteExecution"] = {
        "enabled": True,
        "maximumTtlSeconds": 900,
    }
    # The standard media overlay mounts the source read-only. Exercise the
    # supported COPY operation rather than granting an impossible MOVE.
    for policy in document.get("organizePolicies", []):
        policy["operation"] = "COPY"
    automation = document.setdefault("automation", {})
    automation["schedules"] = []
    document["automationTaskDefinitions"] = [
        {
            "id": DEFINITION_ID,
            "name": "Fault restart automatic organization",
            "resourceLibraryId": "source",
            "mode": "automatic-organization",
            "enabled": True,
            "intervalSeconds": 3600,
            "itemLimit": 10,
        }
    ]
    config_file.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    config_file.chmod(0o644)


def prepare_offline_provider(root: Path) -> tuple[Path, Path]:
    provider_root = root / "offline_provider"
    provider_root.mkdir()
    (provider_root / "sitecustomize.py").write_text(
        "import mediaflow.infrastructure.metadata_provider_bootstrap as bootstrap\n"
        "from mediaflow.application.metadata import MetadataProviderRegistry\n"
        "from mediaflow.domain.metadata import (MediaCandidate, MediaIdentity, "
        "MediaType, ProviderCapabilities)\n"
        "\n"
        "class OfflineProvider:\n"
        "    provider_id = 'tmdb'\n"
        "    capabilities = ProviderCapabilities(True, True, True, True, True, True, True)\n"
        "    def search_movie(self, query, policy=None, *, force_refresh=False):\n"
        "        return (MediaCandidate('tmdb', '1', MediaType.MOVIE, 'One'),)\n"
        "    def search_tv(self, query, policy=None, *, force_refresh=False):\n"
        "        return ()\n"
        "    def get_movie(self, provider_id, policy=None, *, force_refresh=False):\n"
        "        return MediaIdentity(provider='tmdb', provider_id=provider_id, "
        "media_type=MediaType.MOVIE, title='One', year=2001)\n"
        "    def get_tv(self, provider_id, policy=None, *, force_refresh=False):\n"
        "        return self.get_movie(provider_id, policy, force_refresh=force_refresh)\n"
        "    def get_season(self, provider_id, season, policy=None, *, force_refresh=False):\n"
        "        return self.get_movie(provider_id, policy, force_refresh=force_refresh)\n"
        "    def get_episode(self, provider_id, season, episode, **kwargs):\n"
        "        return self.get_movie(provider_id, **kwargs)\n"
        "    def find_by_external_id(self, external_id, media_type, **kwargs):\n"
        "        return self.get_movie(external_id, **kwargs)\n"
        "def _offline_registry(provider_ids, **kwargs):\n"
        "    return MetadataProviderRegistry((OfflineProvider(),))\n"
        "bootstrap.metadata_provider_registry_from_environment = _offline_registry\n",
        encoding="utf-8",
    )
    (provider_root / "sitecustomize.py").chmod(0o644)
    override = root / "compose.restart-fault.yaml"
    provider_volume = (
        "      - type: bind\n"
        "        source: ${MEDIAFLOW_OFFLINE_PROVIDER_DIR:?set MEDIAFLOW_OFFLINE_PROVIDER_DIR}\n"
        "        target: /offline-provider\n"
        "        read_only: true\n"
        "        bind:\n"
        "          create_host_path: false\n"
    )
    override.write_text(
        "services:\n"
        + "".join(
            f"  {service}:\n    volumes:\n{provider_volume}    environment:\n"
            "      PYTHONPATH: /offline-provider\n"
            for service in ("api", "worker", "scheduler", "notification-worker")
        ),
        encoding="utf-8",
    )
    override.chmod(0o644)
    return provider_root, override


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


def active_identity(base: str, token: str) -> dict[str, object]:
    status, management = json_request(base, "/api/v1/management/readiness", token)
    if status != 200:
        raise RuntimeError(f"management readiness returned HTTP {status}")
    active = management.get("active") or {}
    revision_id = active.get("revisionId")
    digest = active.get("digest")
    version = active.get("version") or active.get("revisionSequence")
    if not revision_id or not digest or not isinstance(version, int):
        raise RuntimeError(f"management readiness lacks an exact Active identity: {management}")
    return {"revisionId": revision_id, "digest": digest, "version": version}


def definition_projection(base: str, token: str) -> dict:
    status, document = json_request(base, "/api/v1/automation/task-definitions", token)
    if status != 200:
        raise RuntimeError(f"Automation Task Definition list returned HTTP {status}: {document}")
    definition = next(
        (item for item in document.get("items", []) if item.get("id") == DEFINITION_ID),
        None,
    )
    if definition is None:
        raise RuntimeError(f"Active Automation Task Definition {DEFINITION_ID!r} is missing")
    return definition


def prepare_definition_grant(base: str, token: str, identity: dict[str, object]) -> dict:
    """Create the exact analysis evidence and explicit grant used by scheduling."""

    definition = definition_projection(base, token)
    request_id = str(uuid4())
    status, admitted = json_request(
        base,
        f"/api/v1/operations/automation/definitions/{urllib.parse.quote(DEFINITION_ID)}/run-once",
        token,
        method="POST",
        body={
            "admissionRequestId": request_id,
            "expectedDefinitionFingerprint": definition["definitionFingerprint"],
            "expectedRevisionId": identity["revisionId"],
            "expectedRevisionVersion": identity["version"],
            "expectedRevisionDigest": identity["digest"],
        },
    )
    if status != 202:
        raise RuntimeError(f"definition Run once admission returned HTTP {status}: {admitted}")
    discovery_id = admitted.get("discoveryId")
    if not discovery_id:
        raise RuntimeError(f"definition Run once admission lacks discovery identity: {admitted}")

    def discovery_complete() -> dict | None:
        current_status, current = json_request(
            base,
            f"/api/v1/operations/automation/run-once/{urllib.parse.quote(discovery_id)}",
            token,
        )
        if current_status != 200:
            return None
        if current.get("status") in {"completed", "partial_success"}:
            return current
        return None

    completed = wait_until(
        discovery_complete,
        timeout=180.0,
        description="definition Run once discovery completion",
    )
    status, finalized = json_request(
        base,
        f"/api/v1/operations/automation/run-once/{urllib.parse.quote(discovery_id)}/finalize",
        token,
        method="POST",
        body={"expectedVersion": completed["version"]},
    )
    if status != 201:
        raise RuntimeError(f"definition Run once finalize returned HTTP {status}: {finalized}")

    def analysis_complete() -> dict | None:
        current_status, current = json_request(
            base,
            f"/api/v1/operations/automation/run-once/{urllib.parse.quote(discovery_id)}",
            token,
        )
        if current_status != 200:
            return None
        if current.get("previewId"):
            return current
        return None

    analyzed = wait_until(
        analysis_complete,
        timeout=180.0,
        description="definition Run once analysis completion",
    )
    status, grant = json_request(
        base,
        f"/api/v1/automation/task-definitions/{urllib.parse.quote(DEFINITION_ID)}/grant",
        token,
        method="POST",
        body={
            "revisionId": identity["revisionId"],
            "expectedVersion": identity["version"],
            "confirmation": True,
            "maxItemsPerRun": definition["itemLimit"],
            "reason": "isolated restart/fault acceptance",
            "previewId": analyzed["previewId"],
        },
    )
    if status != 201 or (grant.get("grant") or {}).get("status") != "active":
        _, preview = json_request(
            base,
            f"/api/v1/operations/organize/previews/{urllib.parse.quote(analyzed['previewId'])}",
            token,
        )
        _, eligibility = json_request(
            base,
            f"/api/v1/automation/task-definitions/{urllib.parse.quote(DEFINITION_ID)}/grant-state",
            token,
        )
        raise RuntimeError(
            "definition unattended grant returned "
            f"HTTP {status}: grant={grant}; preview={preview}; eligibility={eligibility}"
        )
    return {
        "discoveryId": discovery_id,
        "previewId": analyzed["previewId"],
        "grantId": (grant.get("grant") or {}).get("grantId"),
    }


def scheduled_jobs(base: str, token: str) -> list[dict]:
    status, document = json_request(base, "/api/v1/jobs?limit=100", token)
    if status != 200:
        raise RuntimeError(f"Job list returned HTTP {status}: {document}")
    return [
        item for item in document.get("items", []) if item.get("definition_id") == DEFINITION_ID
    ]


def collection_ids(base: str, token: str, path: str) -> list[dict]:
    status, document = json_request(base, path, token)
    if status != 200:
        raise RuntimeError(f"durable projection {path} returned HTTP {status}")
    return list(document.get("items") or [])


def wait_scheduled_jobs(
    base: str,
    token: str,
    *,
    expected: int,
    timeout: float = 120.0,
) -> list[dict]:
    def reached() -> bool:
        return len(scheduled_jobs(base, token)) == expected

    wait_until(reached, timeout=timeout, description=f"{expected} definition-bound Jobs")
    return scheduled_jobs(base, token)


def wait_job_linked_task(base: str, token: str, job_id: str) -> dict:
    def reached() -> bool:
        _, document = json_request(
            base,
            f"/api/v1/jobs/{urllib.parse.quote(job_id)}",
            token,
        )
        return document.get("status") in {
            "completed",
            "failed",
            "cancelled",
        }

    wait_until(reached, timeout=180.0, description=f"Job {job_id} terminal evidence")
    _, document = json_request(base, f"/api/v1/jobs/{urllib.parse.quote(job_id)}", token)
    return document


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
        ("organize",),
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
        ("organize",),
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
    temp_parent = os.environ.get("MEDIAFLOW_SMOKE_TEMP_DIR")
    if temp_parent:
        Path(temp_parent).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f"{RESTART_PROJECT_PREFIX}-",
        dir=temp_parent,
    ) as directory:
        root = Path(directory)
        os.chmod(root, 0o755)
        config_file, environment_file, source_root, target_root = prepare_files(root, token)
        add_fault_schedule(config_file, source_root)
        provider_root, override_file = prepare_offline_provider(root)
        environment = compose_environment(
            root,
            image,
            config_file=config_file,
            environment_file=environment_file,
            source_root=source_root,
            target_root=target_root,
            api_port=api_port,
        )
        environment["MEDIAFLOW_OFFLINE_PROVIDER_DIR"] = str(provider_root)
        command = [
            "docker",
            "compose",
            "-f",
            str(ROOT / "compose.yaml"),
            "-f",
            str(ROOT / "compose.media-mounts.yaml"),
            "-f",
            str(override_file),
            "--project-name",
            project,
        ]
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
                [
                    "docker",
                    "compose",
                    "-f",
                    str(ROOT / "compose.yaml"),
                    "-f",
                    str(ROOT / "compose.media-mounts.yaml"),
                    "config",
                ],
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

            print("Activating the managed runtime with one automatic-organization definition...")
            add_fault_schedule(config_file, source_root)
            activate_runtime(base, token, config_file)
            identity = active_identity(base, token)

            print("Starting the Worker and establishing explicit definition authority...")
            run([*command, "start", "worker"], environment=environment)
            wait_services_healthy(command, environment, services={"api", "worker"})
            wait_worker_ready(base, token)
            source_file = source_root / "电影" / "One.2001.mkv"
            source_bytes = source_file.read_bytes()
            grant_evidence = prepare_definition_grant(base, token, identity)
            if source_file.read_bytes() != source_bytes or any(target_root.rglob("*")):
                raise RuntimeError("definition analysis or grant mutated source/destination media")
            run([*command, "stop", "worker"], environment=environment)

            print("Starting the Scheduler and waiting for one definition-bound Job...")
            run([*command, "start", "scheduler"], environment=environment)
            wait_services_healthy(command, environment, services={"api", "scheduler"})
            first_occurrence = wait_scheduled_jobs(base, token, expected=1)

            print("Restarting the Scheduler around the same due slot...")
            run([*command, "restart", "scheduler"], environment=environment)
            wait_services_healthy(command, environment, services={"api", "scheduler"})
            wait_scheduled_jobs(base, token, expected=1)
            second_occurrence = scheduled_jobs(base, token)
            if [item["job_id"] for item in second_occurrence] != [
                item["job_id"] for item in first_occurrence
            ]:
                raise RuntimeError("Scheduler restart changed the scheduled Job identity")

            print("Starting the Worker and waiting for definition-bound Task evidence...")
            run([*command, "start", "worker"], environment=environment)
            wait_services_healthy(command, environment, services={"api", "scheduler", "worker"})
            wait_worker_ready(base, token)
            scheduled_job = wait_job_linked_task(
                base,
                token,
                first_occurrence[0]["job_id"],
            )
            scheduled_task_id = scheduled_job.get("task_id")
            if scheduled_job.get("status") != "completed" or not scheduled_task_id:
                raise RuntimeError(
                    f"definition-bound Job did not produce durable Task evidence: {scheduled_job}"
                )
            outputs = list(target_root.rglob("*.mkv"))
            if (
                len(outputs) != 1
                or outputs[0].read_bytes() != source_bytes
                or source_file.read_bytes() != source_bytes
            ):
                raise RuntimeError("scheduled COPY did not preserve exact source/destination bytes")
            occurrence = definition_projection(base, token).get("lastOccurrence") or {}
            if (
                not occurrence.get("occurrenceId")
                or occurrence.get("jobId") != scheduled_job["job_id"]
                or occurrence.get("taskId") != scheduled_task_id
            ):
                raise RuntimeError(f"scheduled occurrence lost its Job/Task linkage: {occurrence}")

            print("Stopping Worker and Notification Worker before fault fixtures...")
            run([*command, "stop", "worker", "notification-worker"], environment=environment)
            wait_for_api(base, token)

            # Use the supported, explicitly authorized remote Organize entry.
            # The stopped Worker cannot execute this fencing-only Job.
            issued = run(
                [
                    *command,
                    "exec",
                    "-T",
                    "api",
                    "mediaflow",
                    "--config",
                    "/config/mediaflow.json",
                    "execution-authorizations",
                    "issue",
                    "--ttl-seconds",
                    "300",
                    "--max-items",
                    "1",
                    "--actor",
                    "isolated-restart-acceptance",
                ],
                environment=environment,
            )
            execution_token = next(
                line.removeprefix("Token: ")
                for line in issued.stdout.splitlines()
                if line.startswith("Token: ")
            )
            request = urllib.request.Request(
                f"{base}/api/v1/jobs",
                data=json.dumps({"command": "organize", "execute": True, "limit": 1}).encode(),
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-MediaFlow-Execution-Token": execution_token,
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status != 202:
                    raise RuntimeError(f"fault Job submission returned HTTP {response.status}")
                submitted = json.load(response)
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
                "jobs": collection_ids(base, token, "/api/v1/jobs?limit=100"),
                "tasks": collection_ids(base, token, "/api/v1/tasks?limit=100"),
                "scheduledJobs": second_occurrence,
                "scheduledTaskId": scheduled_task_id,
                "occurrence": occurrence,
                "grantEvidence": grant_evidence,
                "notifications": collection_ids(base, token, "/api/v1/notifications?limit=100"),
                "logs": collection_ids(base, token, "/api/v1/logs?limit=100"),
                "audits": collection_ids(base, token, "/api/v1/security-audit?limit=100"),
            }
            baseline_task_ids = {item.get("task_id") for item in baseline["tasks"]}
            if UNCERTAIN_TASK_ID not in baseline_task_ids:
                raise RuntimeError("uncertain fault Task is missing from the API projection")
            if scheduled_task_id not in baseline_task_ids:
                raise RuntimeError("definition-bound Task is missing from the API projection")
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
            wait_scheduled_jobs(base, token, expected=1)
            final_occurrence = scheduled_jobs(base, token)
            if [item["job_id"] for item in final_occurrence] != [
                item["job_id"] for item in baseline["scheduledJobs"]
            ]:
                raise RuntimeError("Scheduler restart changed the scheduled Job identity")
            if final_occurrence[0].get("task_id") != scheduled_task_id:
                raise RuntimeError("Scheduler restart changed the definition-bound Task link")
            final_task_ids = {
                item.get("task_id")
                for item in collection_ids(base, token, "/api/v1/tasks?limit=100")
            }
            if scheduled_task_id not in final_task_ids:
                raise RuntimeError("definition-bound Task disappeared after service restarts")
            final_definition = definition_projection(base, token)
            if final_definition.get("lastOccurrence") != baseline["occurrence"]:
                raise RuntimeError("service restarts changed the durable occurrence evidence")
            if (final_definition.get("grant") or {}).get("grantId") != grant_evidence["grantId"]:
                raise RuntimeError("service restarts changed the explicit unattended grant")
            if list(target_root.rglob("*.mkv")) != outputs or (
                outputs[0].read_bytes() != source_bytes or source_file.read_bytes() != source_bytes
            ):
                raise RuntimeError(
                    "service restarts replayed or changed the scheduled media effect"
                )

            print("Restarting Notification Worker and preserving targetless durable evidence...")
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
                # This fixture has no published target authority. The new
                # boundary must preserve every state/attempt, not burn an
                # attempt and dead-letter a delivery merely on restart.
                expected = {
                    "pending": ("pending", 0),
                    "retry": ("retry", 1),
                    "delivered": ("delivered", 1),
                    "dead": ("dead-letter", 2),
                    "delivering": ("delivering", 1),
                }
                return all(
                    (
                        values[NOTIFICATION_IDS[key]]["status"],
                        values[NOTIFICATION_IDS[key]]["attempts"],
                    )
                    == state
                    for key, state in expected.items()
                )

            time.sleep(12)

            try:
                wait_until(
                    notification_evidence_settled,
                    timeout=45.0,
                    description="Notification Worker targetless state and attempt preservation",
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
            for secret in (token, execution_token):
                if secret in logs_result.stdout or secret in logs_result.stderr:
                    raise RuntimeError("service logs contain an API or execution token")
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
