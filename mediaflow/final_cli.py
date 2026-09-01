from __future__ import annotations

import argparse
import hashlib
import io
import ipaddress
import json
import os
import re
import secrets
import signal
import threading
import time
from collections.abc import Callable
from contextlib import ExitStack, nullcontext
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TextIO
from zoneinfo import ZoneInfo

from mediaflow.application.automation import (
    AutomationCancelled,
    AutomationConfigurationUnavailable,
    AutomationJobService,
    AutomationWorker,
    IntervalScheduler,
)
from mediaflow.application.classification_review import ClassificationReviewService
from mediaflow.application.configuration_snapshot import (
    MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION,
    ManagedConfigurationService,
)
from mediaflow.application.conflict_resolution import ConfirmationService
from mediaflow.application.dashboard import DashboardService
from mediaflow.application.execution_authorization import ExecutionAuthorizationService
from mediaflow.application.file_catalog import FileCatalogFilter, FileCatalogService
from mediaflow.application.file_metadata_correction import FileMetadataCorrectionService
from mediaflow.application.file_recognition_request import FileRecognitionRequestService
from mediaflow.application.file_replan_request import FileReplanRequestService
from mediaflow.application.library_pipeline import ResourceLibraryScanner
from mediaflow.application.manual_ignore import ManualIgnoreService
from mediaflow.application.media_organizer import MediaOrganizerBatchResult, MediaOrganizerService
from mediaflow.application.metadata_correction import MetadataCorrectionService
from mediaflow.application.metadata_correction_continuation import (
    MetadataCorrectionContinuationWorkerService,
)
from mediaflow.application.metadata_review import MetadataReviewService
from mediaflow.application.notification import NotificationPublisher, NotificationWorker
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.application.recognition_batch_retry import RecognitionBatchRetryService
from mediaflow.application.recognition_retry import RecognitionRetryService
from mediaflow.application.recognition_review import RecognitionReviewService
from mediaflow.application.recovery_admission import RecoveryAdmissionService
from mediaflow.application.recovery_continuation import RecoveryContinuationWorkerService
from mediaflow.application.scanner import StorageScanner
from mediaflow.application.strategy_test import strategy_runner_from_configuration
from mediaflow.application.task_retry import TaskRetryRequestService
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.cli import render_strategy_result
from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationFailureEvidence,
    CronSchedule,
    SchedulerConfigurationSnapshot,
)
from mediaflow.domain.classification_review import (
    ClassificationReviewStatus,
    ClassificationSelection,
)
from mediaflow.domain.configuration_management import RuntimeSnapshotUnavailable
from mediaflow.domain.logging import LogLevel
from mediaflow.domain.metadata_correction import (
    MetadataCorrectionSelection,
    MetadataCorrectionStatus,
)
from mediaflow.domain.metadata_review import MetadataReviewStatus, MetadataSelection
from mediaflow.domain.notification import NotificationDeliveryStatus
from mediaflow.domain.organizer import ConflictStrategy
from mediaflow.domain.recognition_review import RecognitionReviewStatus, RecognitionSelection
from mediaflow.domain.scanner import FileScanStatus
from mediaflow.domain.task_persistence import (
    ConfirmationStatus,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)
from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository
from mediaflow.infrastructure.metadata_provider_bootstrap import (
    LazyMetadataProviderRegistryFactory,
    metadata_provider_registry_from_environment,
)
from mediaflow.infrastructure.migration_rehearsal import SQLiteMigrationRehearsalService
from mediaflow.infrastructure.operational_logging import SQLiteOperationalLogger
from mediaflow.infrastructure.runtime_configuration import (
    ManagementBootstrapConfiguration,
    RuntimeConfiguration,
    load_managed_runtime_configuration,
    load_management_bootstrap,
    load_runtime_configuration,
    with_managed_snapshot,
)
from mediaflow.infrastructure.runtime_lease import RuntimeDatabaseLease, RuntimeLeaseMode
from mediaflow.infrastructure.sqlite_backup import SQLiteBackupService
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository
from mediaflow.infrastructure.sqlite_restore import SQLiteRestoreService
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.infrastructure.upgrade_preflight import UpgradePreflightService


def final_main(
    argv: list[str],
    *,
    stdout: TextIO,
    stderr: TextIO,
    cancellation_check: Callable[[], bool] | None = None,
    _resolved_configuration: RuntimeConfiguration | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="mediaflow")
    parser.add_argument("--config", help="runtime JSON configuration")
    parser.add_argument("--configuration-snapshot-id", help=argparse.SUPPRESS)
    parser.add_argument("--configuration-snapshot-digest", help=argparse.SUPPRESS)
    commands = parser.add_subparsers(dest="command", required=True)
    config = commands.add_parser("config", help="configuration operations")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    config_commands.add_parser("validate", help="validate configuration without processing media")
    config_commands.add_parser("status", help="show JSON bootstrap/managed Active authority")
    draft_import = config_commands.add_parser(
        "draft-import", aliases=("import",), help="import a JSON document as a Draft"
    )
    draft_import.add_argument("--file", help="JSON file; defaults to --config")
    draft_validate = config_commands.add_parser(
        "draft-validate", aliases=("validate-draft",), help="validate one Draft revision"
    )
    draft_validate.add_argument("revision_id")
    draft_validate.add_argument("--actor", default="local-cli")
    activate = config_commands.add_parser("activate", help="activate a Validated Draft")
    activate.add_argument("revision_id")
    activate.add_argument("--expected-version", type=int, required=True)
    activate.add_argument("--actor", default="local-cli")
    analyze = commands.add_parser("analyze", help="analyze one file without planning execution")
    analyze.add_argument("path")
    analyze.add_argument("--offline", action="store_true")
    scan = commands.add_parser("scan", help="scan all configured ResourceLibraries read-only")
    scan.add_argument("--limit", type=int)
    preview = commands.add_parser("preview", help="run the complete workflow as DryRun")
    preview.add_argument("path", nargs="?")
    preview.add_argument("--limit", type=int)
    organize = commands.add_parser("organize", help="organize one file or a directory")
    organize.add_argument("path", nargs="?")
    organize.add_argument("--limit", type=int)
    organize.add_argument("--execute", action="store_true")
    batch = commands.add_parser("batch", help="explicit all-ResourceLibrary batch operations")
    batch_commands = batch.add_subparsers(dest="batch_command", required=True)
    batch_preview = batch_commands.add_parser("preview")
    batch_preview.add_argument("--limit", type=int)
    batch_organize = batch_commands.add_parser("organize")
    batch_organize.add_argument("--limit", type=int)
    batch_organize.add_argument("--execute", action="store_true")
    tasks = commands.add_parser("tasks", help="persistent task operations")
    task_commands = tasks.add_subparsers(dest="task_command", required=True)
    task_list = task_commands.add_parser("list")
    task_list.add_argument("--limit", type=int, default=20)
    task_show = task_commands.add_parser("show")
    task_show.add_argument("task_id")
    task_show_item = task_commands.add_parser("show-item")
    task_show_item.add_argument("task_id")
    task_show_item.add_argument("item_id")
    task_pause = task_commands.add_parser("pause")
    task_pause.add_argument("task_id")
    task_ignore = task_commands.add_parser("ignore-item")
    task_ignore.add_argument("task_id")
    task_ignore.add_argument("item_id")
    task_ignore.add_argument("--actor", required=True)
    task_ignore.add_argument("--note")
    task_ignore_pending = task_commands.add_parser("ignore-pending")
    task_ignore_pending.add_argument("--actor", required=True)
    task_ignore_pending.add_argument("--note")
    task_ignore_pending.add_argument("--limit", type=int, default=100)
    task_ignore_pending.add_argument("--task-id")
    task_retry_request = task_commands.add_parser("retry-request")
    task_retry_request.add_argument("--actor", required=True)
    task_retry_request.add_argument("--note")
    task_retry_request.add_argument("--limit", type=int, default=100)
    task_retry_request.add_argument("--task-id")
    for name in ("resume", "retry-failed"):
        task_retry = task_commands.add_parser(name)
        task_retry.add_argument("task_id")
        task_retry.add_argument("--execute", action="store_true")
    confirmations = commands.add_parser("confirmations", help="persistent conflict decisions")
    confirmation_commands = confirmations.add_subparsers(dest="confirmation_command", required=True)
    confirmation_list = confirmation_commands.add_parser("list")
    confirmation_list.add_argument("--all", action="store_true")
    confirmation_show = confirmation_commands.add_parser("show")
    confirmation_show.add_argument("confirmation_id")
    confirmation_resolve = confirmation_commands.add_parser("resolve")
    confirmation_resolve.add_argument("confirmation_id")
    confirmation_resolve.add_argument(
        "--strategy", required=True, choices=[item.value for item in ConflictStrategy]
    )
    confirmation_resolve.add_argument("--confirm-overwrite", action="store_true")
    confirmation_resolve.add_argument("--actor")
    confirmation_resolve.add_argument("--note")
    storage_command = commands.add_parser("storage", help="Storage configuration and preflight")
    storage_commands = storage_command.add_subparsers(dest="storage_command", required=True)
    storage_commands.add_parser("list", help="list configured Storages without connecting")
    storage_check = storage_commands.add_parser("check", help="run read-only Storage preflight")
    storage_check.add_argument("storage_id", nargs="?")
    files = commands.add_parser("files", help="read-only indexed file catalog")
    file_commands = files.add_subparsers(dest="file_command", required=True)
    file_list = file_commands.add_parser("list")
    file_list.add_argument("--resource-library")
    file_list.add_argument("--storage")
    file_list.add_argument("--scan-status", choices=[item.value for item in FileScanStatus])
    file_list.add_argument("--query")
    file_list.add_argument("--limit", type=int, default=100)
    file_list.add_argument("--after")
    file_list.add_argument("--before")
    file_list.add_argument("--cursor-file-id")
    file_list.add_argument("--recognition-type")
    file_list.add_argument("--provider")
    file_list.add_argument("--provider-id")
    file_list.add_argument("--title")
    file_list.add_argument("--task-id")
    file_list.add_argument("--year", type=int)
    file_show = file_commands.add_parser("show")
    file_show.add_argument("file_id")
    file_show.add_argument("--resource-library")
    file_stats = file_commands.add_parser("stats")
    file_stats.add_argument("--resource-library")
    file_stats.add_argument("--storage")
    file_re_recognize = file_commands.add_parser("re-recognize")
    file_re_recognize.add_argument("file_id")
    file_re_recognize.add_argument("--actor", required=True)
    file_re_recognize.add_argument("--note")
    file_re_match = file_commands.add_parser("re-match")
    file_re_match.add_argument("file_id")
    file_re_match.add_argument("--query")
    file_re_match.add_argument("--year", type=int)
    file_re_match.add_argument("--media-type", required=True, choices=("movie", "tv"))
    file_re_match.add_argument("--provider-id")
    file_re_match.add_argument("--actor", required=True)
    file_re_match.add_argument("--note")
    file_re_plan = file_commands.add_parser("re-plan")
    file_re_plan.add_argument("file_id")
    file_re_plan.add_argument("--actor", required=True)
    file_re_plan.add_argument("--note")
    jobs = commands.add_parser("jobs", help="persistent DryRun background jobs")
    job_commands = jobs.add_subparsers(dest="job_command", required=True)
    job_list = job_commands.add_parser("list")
    job_list.add_argument("--limit", type=int, default=20)
    job_show = job_commands.add_parser("show")
    job_show.add_argument("job_id")
    job_submit = job_commands.add_parser("submit")
    job_submit.add_argument("workflow", choices=("scan", "preview"))
    job_submit.add_argument("--limit", type=int)
    job_cancel = job_commands.add_parser("cancel")
    job_cancel.add_argument("job_id")
    job_stale = job_commands.add_parser("stale")
    job_stale.add_argument("--age-seconds", type=float, required=True)
    job_requeue = job_commands.add_parser("requeue")
    job_requeue.add_argument("job_id")
    job_requeue.add_argument("--age-seconds", type=float, required=True)
    worker = commands.add_parser("worker", help="run persistent DryRun jobs")
    worker_commands = worker.add_subparsers(dest="worker_command", required=True)
    worker_commands.add_parser("run-next")
    worker_run = worker_commands.add_parser("run")
    worker_run.add_argument("--poll-seconds", type=float)
    scheduler = commands.add_parser("scheduler", help="persistent interval schedules")
    scheduler_commands = scheduler.add_subparsers(dest="scheduler_command", required=True)
    scheduler_commands.add_parser("list")
    scheduler_commands.add_parser("tick")
    scheduler_audit = scheduler_commands.add_parser("audit")
    scheduler_audit.add_argument("schedule_id", nargs="?")
    scheduler_audit.add_argument("--limit", type=int, default=100)
    scheduler_run = scheduler_commands.add_parser("run")
    scheduler_run.add_argument("--poll-seconds", type=float)
    notifications = commands.add_parser("notifications", help="notification outbox operations")
    notification_commands = notifications.add_subparsers(dest="notification_command", required=True)
    notification_list = notification_commands.add_parser("list")
    notification_list.add_argument(
        "--status", choices=[item.value for item in NotificationDeliveryStatus]
    )
    notification_list.add_argument("--limit", type=int, default=100)
    notification_requeue = notification_commands.add_parser("requeue")
    notification_requeue.add_argument("delivery_id")
    notification_stale = notification_commands.add_parser("stale")
    notification_stale.add_argument("--age-seconds", type=float, required=True)
    notification_stale.add_argument("--limit", type=int, default=100)
    notification_worker = commands.add_parser(
        "notification-worker", help="deliver signed webhook notifications"
    )
    notification_worker_commands = notification_worker.add_subparsers(
        dest="notification_worker_command", required=True
    )
    notification_worker_commands.add_parser("run-next")
    notification_worker_run = notification_worker_commands.add_parser("run")
    notification_worker_run.add_argument("--poll-seconds", type=float)
    execution_authorizations = commands.add_parser(
        "execution-authorizations", help="local one-time remote execution authority"
    )
    execution_authorization_commands = execution_authorizations.add_subparsers(
        dest="execution_authorization_command", required=True
    )
    execution_authorization_issue = execution_authorization_commands.add_parser("issue")
    execution_authorization_issue.add_argument("--ttl-seconds", type=int, required=True)
    execution_authorization_issue.add_argument("--max-items", type=int, required=True)
    execution_authorization_issue.add_argument("--actor")
    execution_authorization_issue.add_argument("--note")
    execution_authorization_commands.add_parser("list")
    execution_authorization_show = execution_authorization_commands.add_parser("show")
    execution_authorization_show.add_argument("authorization_id")
    execution_authorization_revoke = execution_authorization_commands.add_parser("revoke")
    execution_authorization_revoke.add_argument("authorization_id")
    execution_authorization_revoke.add_argument("--actor")
    security_audit = commands.add_parser("security-audit", help="local API security audit")
    security_audit_commands = security_audit.add_subparsers(
        dest="security_audit_command", required=True
    )
    security_audit_list = security_audit_commands.add_parser("list")
    security_audit_list.add_argument("--limit", type=int, default=100)
    logs = commands.add_parser("logs", help="local redacted operational logs")
    log_commands = logs.add_subparsers(dest="log_command", required=True)
    log_list = log_commands.add_parser("list")
    log_list.add_argument("--limit", type=int, default=100)
    log_list.add_argument("--level", choices=[item.name for item in LogLevel])
    log_commands.add_parser("prune")
    database = commands.add_parser("database", help="runtime database protection")
    database_commands = database.add_subparsers(dest="database_command", required=True)
    database_backup = database_commands.add_parser("backup")
    database_backup.add_argument("--output", required=True)
    database_verify = database_commands.add_parser("verify")
    database_verify.add_argument("path")
    database_restore = database_commands.add_parser("restore")
    database_restore.add_argument("backup")
    database_restore.add_argument("--confirm-empty-destination", action="store_true")
    upgrade = commands.add_parser("upgrade", help="read-only upgrade readiness")
    upgrade_commands = upgrade.add_subparsers(dest="upgrade_command", required=True)
    upgrade_check = upgrade_commands.add_parser("check")
    upgrade_check.add_argument("--backup", required=True)
    upgrade_check.add_argument("--max-backup-age-hours", type=float, default=24)
    upgrade_rehearse = upgrade_commands.add_parser("rehearse")
    upgrade_rehearse.add_argument("--backup", required=True)
    dashboard = commands.add_parser("dashboard", help="read-only operational summary")
    dashboard.add_argument("--recent-limit", type=int, default=10)
    metadata_reviews = commands.add_parser(
        "metadata-reviews", help="persistent metadata candidate review queue"
    )
    metadata_review_commands = metadata_reviews.add_subparsers(
        dest="metadata_review_command", required=True
    )
    metadata_review_list = metadata_review_commands.add_parser("list")
    metadata_review_list.add_argument("--limit", type=int, default=100)
    metadata_review_show = metadata_review_commands.add_parser("show")
    metadata_review_show.add_argument("review_id")
    metadata_review_resolve = metadata_review_commands.add_parser("resolve")
    metadata_review_resolve.add_argument("review_id")
    metadata_review_resolve.add_argument("--candidate-rank", required=True, type=int)
    metadata_review_resolve.add_argument("--actor")
    metadata_review_resolve.add_argument("--note")
    metadata_review_batch_resolve = metadata_review_commands.add_parser("resolve-pending")
    metadata_review_batch_resolve.add_argument("--candidate-rank", required=True, type=int)
    metadata_review_batch_resolve.add_argument("--actor", required=True)
    metadata_review_batch_resolve.add_argument("--note")
    metadata_review_batch_resolve.add_argument("--limit", type=int, default=100)
    metadata_review_batch_resolve.add_argument("--task-id")
    metadata_corrections = commands.add_parser(
        "metadata-corrections", help="persistent metadata query correction queue"
    )
    metadata_correction_commands = metadata_corrections.add_subparsers(
        dest="metadata_correction_command", required=True
    )
    metadata_correction_list = metadata_correction_commands.add_parser("list")
    metadata_correction_list.add_argument("--limit", type=int, default=100)
    metadata_correction_show = metadata_correction_commands.add_parser("show")
    metadata_correction_show.add_argument("review_id")
    metadata_correction_resolve = metadata_correction_commands.add_parser("resolve")
    metadata_correction_resolve.add_argument("review_id")
    metadata_correction_resolve.add_argument("--query")
    metadata_correction_resolve.add_argument("--year", type=int)
    metadata_correction_resolve.add_argument("--media-type", required=True, choices=("movie", "tv"))
    metadata_correction_resolve.add_argument("--provider-id")
    metadata_correction_resolve.add_argument("--actor")
    metadata_correction_resolve.add_argument("--note")
    metadata_correction_batch_resolve = metadata_correction_commands.add_parser("resolve-pending")
    metadata_correction_batch_resolve.add_argument("--query")
    metadata_correction_batch_resolve.add_argument("--year", type=int)
    metadata_correction_batch_resolve.add_argument(
        "--media-type", required=True, choices=("movie", "tv")
    )
    metadata_correction_batch_resolve.add_argument("--provider-id")
    metadata_correction_batch_resolve.add_argument("--actor", required=True)
    metadata_correction_batch_resolve.add_argument("--note")
    metadata_correction_batch_resolve.add_argument("--limit", type=int, default=100)
    metadata_correction_batch_resolve.add_argument("--task-id")
    classification_reviews = commands.add_parser(
        "classification-reviews", help="persistent classification review queue"
    )
    classification_review_commands = classification_reviews.add_subparsers(
        dest="classification_review_command", required=True
    )
    classification_review_list = classification_review_commands.add_parser("list")
    classification_review_list.add_argument("--limit", type=int, default=100)
    classification_review_show = classification_review_commands.add_parser("show")
    classification_review_show.add_argument("review_id")
    classification_review_resolve = classification_review_commands.add_parser("resolve")
    classification_review_resolve.add_argument("review_id")
    classification_review_resolve.add_argument("--choice-rank", required=True, type=int)
    classification_review_resolve.add_argument("--actor")
    classification_review_resolve.add_argument("--note")
    recognition_reviews = commands.add_parser(
        "recognition-reviews", help="persistent Unrecognized media review queue"
    )
    recognition_review_commands = recognition_reviews.add_subparsers(
        dest="recognition_review_command", required=True
    )
    recognition_review_list = recognition_review_commands.add_parser("list")
    recognition_review_list.add_argument("--limit", type=int, default=100)
    recognition_review_show = recognition_review_commands.add_parser("show")
    recognition_review_show.add_argument("review_id")
    recognition_review_resolve = recognition_review_commands.add_parser("resolve")
    recognition_review_resolve.add_argument("review_id")
    recognition_review_resolve.add_argument("--recognition-type", required=True)
    recognition_review_resolve.add_argument("--actor")
    recognition_review_resolve.add_argument("--note")
    recognition_review_retry = recognition_review_commands.add_parser("retry")
    recognition_review_retry.add_argument("review_id")
    recognition_review_retry.add_argument("--actor", required=True)
    recognition_review_retry.add_argument("--note")
    recognition_review_batch_retry = recognition_review_commands.add_parser("retry-pending")
    recognition_review_batch_retry.add_argument("--actor", required=True)
    recognition_review_batch_retry.add_argument("--note")
    recognition_review_batch_retry.add_argument("--limit", type=int, default=100)
    recognition_review_batch_retry.add_argument("--task-id")
    recognition_review_batch_resolve = recognition_review_commands.add_parser("resolve-pending")
    recognition_review_batch_resolve.add_argument("--recognition-type", required=True)
    recognition_review_batch_resolve.add_argument("--actor", required=True)
    recognition_review_batch_resolve.add_argument("--note")
    recognition_review_batch_resolve.add_argument("--limit", type=int, default=100)
    recognition_review_batch_resolve.add_argument("--task-id")
    api = commands.add_parser("api", help="development REST API")
    api_commands = api.add_subparsers(dest="api_command", required=True)
    api_token = api_commands.add_parser("token", help="cryptographic bearer token operations")
    api_token_commands = api_token.add_subparsers(dest="api_token_command", required=True)
    api_token_generate = api_token_commands.add_parser("generate")
    api_token_generate.add_argument("--bytes", type=int, default=32, dest="token_bytes")
    api_credentials = api_commands.add_parser("credentials", help="redacted credential status")
    api_credential_commands = api_credentials.add_subparsers(
        dest="api_credential_command", required=True
    )
    api_credential_commands.add_parser("check")
    api_serve = api_commands.add_parser("serve")
    api_serve.add_argument("--host", default="127.0.0.1")
    api_serve.add_argument("--port", type=int, default=8787)
    api_serve.add_argument("--allow-insecure-remote-http", action="store_true")
    arguments = parser.parse_args(argv)
    if arguments.command == "batch":
        arguments.command = arguments.batch_command
        arguments.path = None
    runtime_lease: RuntimeDatabaseLease | None = None
    try:
        if arguments.command == "api" and arguments.api_command == "token":
            if not 32 <= arguments.token_bytes <= 128:
                raise ValueError("API token bytes must be between 32 and 128")
            stdout.write(f"{secrets.token_urlsafe(arguments.token_bytes)}\n")
            return 0
        # A resumed/retried workflow must resolve the snapshot pinned to the
        # original Task before loading the runtime strategy.  Otherwise a
        # process restart after activation could silently run the old Task
        # against the new Active configuration.
        snapshot_id = arguments.configuration_snapshot_id
        snapshot_digest = arguments.configuration_snapshot_digest
        if (
            not snapshot_id
            and arguments.command == "tasks"
            and arguments.task_command in {"resume", "retry-failed"}
        ):
            pinned = _task_snapshot_identity(arguments.config, arguments.task_id)
            if pinned is not None:
                snapshot_id, snapshot_digest = pinned

        # Database backup/restore and upgrade rehearsal/preflight are
        # intentionally bootstrap-only.  Resolving managed workflow
        # configuration for them would open the configured runtime database
        # before the command's own read-only/atomic safety checks run.
        configuration_management_command = (
            arguments.command == "config"
            and arguments.config_command
            in {
                "status",
                "draft-import",
                "import",
                "draft-validate",
                "validate-draft",
                "activate",
            }
        )
        management_bootstrap_database_path = None
        if configuration_management_command:
            # Recovery commands need only the immutable locator.  Do not make
            # status/import/validate depend on the rest of a broken runtime
            # document; the service performs the candidate validation later.
            management_bootstrap_database_path = _bootstrap_database_path(
                _configuration_document(arguments.config)
            )
        managed_command = (
            arguments.command not in {"database", "upgrade"}
            and not configuration_management_command
            and not (arguments.command == "config" and arguments.config_command == "validate")
        )
        if _resolved_configuration is not None:
            configuration = _resolved_configuration
        elif arguments.command == "worker":
            # Queue claiming must not resolve the current Active workflow.  The
            # immutable locator is enough to claim a Job; its saved revision is
            # loaded only inside _run_queued_workflow after the claim boundary.
            configuration = load_management_bootstrap(_configuration_document(arguments.config))
        else:
            try:
                configuration = (
                    None
                    if configuration_management_command
                    else _configuration(
                        arguments.config,
                        use_managed=managed_command,
                        snapshot_id=snapshot_id,
                        snapshot_digest=snapshot_digest,
                    )
                )
            except RuntimeSnapshotUnavailable:
                # API management must remain available without trusting stale
                # workflow JSON.  It uses only the immutable locator and
                # environment-owned management credentials when Active is
                # unavailable; workflow content is not used for recovery.
                if arguments.command == "api":
                    configuration = load_management_bootstrap(
                        _configuration_document(arguments.config)
                    )
                else:
                    raise
        if (
            arguments.command == "database"
            and arguments.database_command == "restore"
            and not arguments.confirm_empty_destination
        ):
            raise ValueError("restore requires --confirm-empty-destination")
        lease_mode = _runtime_lease_mode(arguments)
        if lease_mode is not None:
            runtime_lease = RuntimeDatabaseLease(configuration.database_path, lease_mode).acquire(
                create_parent=lease_mode is RuntimeLeaseMode.SHARED
            )
        if arguments.command == "api" and arguments.api_command == "credentials":
            statuses = configuration.api_credential_statuses()
            stdout.write(render_api_credentials(statuses))
            return (
                0
                if statuses and all(not item.enabled or item.configured for item in statuses)
                else 1
            )
        if arguments.command == "config":
            bootstrap_document = _configuration_document(arguments.config)
            managed_config_command = arguments.config_command in {
                "status",
                "draft-import",
                "import",
                "draft-validate",
                "validate-draft",
                "activate",
            }
            if managed_config_command:
                database_path = management_bootstrap_database_path
                if database_path is None:
                    raise RuntimeError("configuration management bootstrap locator is unavailable")
                with SQLiteConfigurationRepository(database_path) as repository:
                    service = ManagedConfigurationService(
                        repository,
                        bootstrap_database_path=database_path,
                    )
                    if arguments.config_command == "status":
                        stdout.write(
                            json.dumps(service.status_document(), ensure_ascii=False, indent=2)
                            + "\n"
                        )
                        return 0
                    if arguments.config_command in {"draft-import", "import"}:
                        if arguments.file:
                            document = json.loads(Path(arguments.file).read_text(encoding="utf-8"))
                        else:
                            document = service.current_document(bootstrap_document)
                        revision = service.import_draft(
                            document,
                            actor="local-cli",
                            source="file" if arguments.file else "current",
                        )
                        stdout.write(
                            json.dumps(revision.summary(), ensure_ascii=False, indent=2) + "\n"
                        )
                        return 0
                    if arguments.config_command in {"draft-validate", "validate-draft"}:
                        revision = service.validate(arguments.revision_id, actor=arguments.actor)
                        stdout.write(
                            json.dumps(revision.summary(), ensure_ascii=False, indent=2) + "\n"
                        )
                        return 0 if revision.status.value == "validated" else 1
                    if arguments.config_command == "activate":
                        revision = service.activate(
                            arguments.revision_id,
                            expected_version=arguments.expected_version,
                            actor=arguments.actor,
                        )
                        stdout.write(
                            json.dumps(revision.summary(), ensure_ascii=False, indent=2) + "\n"
                        )
                        return 0
            strategy = configuration.strategy
            stdout.write(
                "Configuration valid\n"
                f"Recognition rules: {len(strategy.recognition_rules)}\n"
                f"Recognition type policies: {len(strategy.recognition_type_policies)}\n"
                f"Metadata policies: {len(strategy.metadata_policies)}\n"
                f"Naming policies: {len(strategy.naming_policies)}\n"
                f"Classification policies: {len(strategy.classification_policies)}\n"
                f"Organize policies: {len(strategy.organize_policies)}\n"
                f"Webhooks: {len(configuration.webhooks)}\n"
            )
            return 0
        if arguments.command == "dashboard":
            with SQLiteTaskRepository(configuration.database_path) as repository:
                snapshot = DashboardService(
                    repository,
                    resource_library_count=sum(
                        item.enabled for item in configuration.resource_libraries
                    ),
                    media_library_count=sum(item.enabled for item in configuration.media_libraries),
                ).snapshot(recent_limit=arguments.recent_limit)
                stdout.write(render_dashboard(snapshot))
            return 0
        if arguments.command == "logs":
            with SQLiteTaskRepository(configuration.database_path) as repository:
                if arguments.log_command == "list":
                    values = repository.list_operational_logs(
                        limit=arguments.limit,
                        minimum_level=LogLevel[arguments.level] if arguments.level else None,
                    )
                    stdout.write(render_operational_logs(values))
                else:
                    removed = repository.prune_operational_logs(
                        before=datetime.now(UTC)
                        - timedelta(days=configuration.operational_logging_retention_days),
                        maximum_records=configuration.operational_logging_maximum_records,
                    )
                    stdout.write(f"Operational log rows removed: {removed}\n")
            return 0
        if arguments.command == "database":
            if arguments.database_command == "restore":
                result = SQLiteRestoreService(
                    arguments.backup, configuration.database_path
                ).restore(confirmed_empty_destination=arguments.confirm_empty_destination)
                stdout.write(render_database_restore(result))
            else:
                service = SQLiteBackupService(configuration.database_path)
                result = (
                    service.backup(arguments.output)
                    if arguments.database_command == "backup"
                    else service.verify(arguments.path)
                )
                stdout.write(render_database_backup(result, arguments.database_command))
            return 0
        if arguments.command == "upgrade":
            if arguments.upgrade_command == "rehearse":
                result = SQLiteMigrationRehearsalService(arguments.backup).rehearse()
                stdout.write(render_migration_rehearsal(result))
            else:
                result = UpgradePreflightService(configuration.database_path).check(
                    arguments.backup,
                    maximum_backup_age_hours=arguments.max_backup_age_hours,
                )
                stdout.write(render_upgrade_preflight(result))
            return 0
        if arguments.command == "metadata-reviews":
            with SQLiteTaskRepository(configuration.database_path) as repository:
                if arguments.metadata_review_command == "list":
                    stdout.write(
                        render_metadata_reviews(
                            repository.list_metadata_reviews(limit=arguments.limit)
                        )
                    )
                elif arguments.metadata_review_command == "show":
                    review = repository.get_metadata_review(arguments.review_id)
                    if review is None:
                        raise LookupError(f"metadata review {arguments.review_id!r} was not found")
                    stdout.write(
                        render_metadata_review(
                            review,
                            repository.list_metadata_review_candidates(review.review_id),
                            repository.list_metadata_review_audit(review.review_id),
                        )
                    )
                elif arguments.metadata_review_command == "resolve-pending":
                    reviews = MetadataReviewService(repository).resolve_pending(
                        arguments.candidate_rank,
                        actor=arguments.actor,
                        note=arguments.note,
                        limit=arguments.limit,
                        task_id=arguments.task_id,
                    )
                    stdout.write(render_metadata_review_batch(reviews))
                else:
                    review = MetadataReviewService(repository).resolve(
                        arguments.review_id,
                        arguments.candidate_rank,
                        actor=arguments.actor,
                        note=arguments.note,
                    )
                    stdout.write(
                        render_metadata_review(
                            review,
                            repository.list_metadata_review_candidates(review.review_id),
                            repository.list_metadata_review_audit(review.review_id),
                        )
                    )
            return 0
        if arguments.command == "metadata-corrections":
            with SQLiteTaskRepository(configuration.database_path) as repository:
                service = MetadataCorrectionService(
                    repository, configuration.strategy.metadata_policies
                )
                if arguments.metadata_correction_command == "list":
                    stdout.write(
                        render_metadata_corrections(
                            repository.list_metadata_corrections(limit=arguments.limit)
                        )
                    )
                elif arguments.metadata_correction_command == "resolve-pending":
                    reviews = service.resolve_pending(
                        query=arguments.query,
                        year=arguments.year,
                        media_type=arguments.media_type,
                        provider_id=arguments.provider_id,
                        actor=arguments.actor,
                        note=arguments.note,
                        limit=arguments.limit,
                        task_id=arguments.task_id,
                    )
                    stdout.write(render_metadata_correction_batch(reviews))
                else:
                    if arguments.metadata_correction_command == "resolve":
                        service.resolve(
                            arguments.review_id,
                            query=arguments.query,
                            year=arguments.year,
                            media_type=arguments.media_type,
                            provider_id=arguments.provider_id,
                            actor=arguments.actor,
                            note=arguments.note,
                        )
                    review = repository.get_metadata_correction(arguments.review_id)
                    if review is None:
                        raise LookupError(
                            f"metadata correction {arguments.review_id!r} was not found"
                        )
                    stdout.write(
                        render_metadata_correction(
                            review,
                            repository.list_metadata_correction_audit(review.review_id),
                        )
                    )
            return 0
        if arguments.command == "recognition-reviews":
            with SQLiteTaskRepository(configuration.database_path) as repository:
                service = RecognitionReviewService(
                    repository, configuration.strategy.recognition_types
                )
                if arguments.recognition_review_command == "list":
                    stdout.write(
                        render_recognition_reviews(
                            repository.list_recognition_reviews(limit=arguments.limit)
                        )
                    )
                elif arguments.recognition_review_command == "resolve-pending":
                    reviews = service.resolve_pending(
                        arguments.recognition_type,
                        actor=arguments.actor,
                        note=arguments.note,
                        limit=arguments.limit,
                        task_id=arguments.task_id,
                    )
                    stdout.write(render_recognition_batch_resolve(reviews))
                elif arguments.recognition_review_command == "retry-pending":
                    decisions = RecognitionBatchRetryService(repository).request_pending(
                        actor=arguments.actor,
                        note=arguments.note,
                        limit=arguments.limit,
                        task_id=arguments.task_id,
                    )
                    stdout.write(render_recognition_batch_retry(decisions))
                else:
                    if arguments.recognition_review_command == "resolve":
                        service.resolve(
                            arguments.review_id,
                            arguments.recognition_type,
                            actor=arguments.actor,
                            note=arguments.note,
                        )
                    elif arguments.recognition_review_command == "retry":
                        RecognitionRetryService(repository).request(
                            arguments.review_id,
                            actor=arguments.actor,
                            note=arguments.note,
                        )
                    review = repository.get_recognition_review(arguments.review_id)
                    if review is None:
                        raise LookupError(
                            f"recognition review {arguments.review_id!r} was not found"
                        )
                    stdout.write(
                        render_recognition_review(
                            review,
                            repository.list_recognition_review_choices(review.review_id),
                            repository.list_recognition_review_audit(review.review_id),
                            repository.list_recognition_retry_audit(review.review_id),
                        )
                    )
            return 0
        if arguments.command == "classification-reviews":
            with SQLiteTaskRepository(configuration.database_path) as repository:
                if arguments.classification_review_command == "list":
                    stdout.write(
                        render_classification_reviews(
                            repository.list_classification_reviews(limit=arguments.limit)
                        )
                    )
                elif arguments.classification_review_command == "show":
                    review = repository.get_classification_review(arguments.review_id)
                    if review is None:
                        raise LookupError(
                            f"classification review {arguments.review_id!r} was not found"
                        )
                    stdout.write(
                        render_classification_review(
                            review,
                            repository.list_classification_review_choices(review.review_id),
                            repository.list_classification_review_audit(review.review_id),
                        )
                    )
                else:
                    review = ClassificationReviewService(repository).resolve(
                        arguments.review_id,
                        arguments.choice_rank,
                        actor=arguments.actor,
                        note=arguments.note,
                    )
                    stdout.write(
                        render_classification_review(
                            review,
                            repository.list_classification_review_choices(review.review_id),
                            repository.list_classification_review_audit(review.review_id),
                        )
                    )
            return 0
        if arguments.command == "notifications":
            if arguments.notification_command in {"list", "stale"} and arguments.limit < 1:
                raise ValueError("notification limit must be positive")
            with SQLiteTaskRepository(configuration.database_path) as repository:
                if arguments.notification_command == "list":
                    status = (
                        NotificationDeliveryStatus(arguments.status) if arguments.status else None
                    )
                    stdout.write(
                        render_notifications(
                            repository.list_deliveries(status=status, limit=arguments.limit)
                        )
                    )
                elif arguments.notification_command == "requeue":
                    stdout.write(
                        render_notification(
                            repository.requeue_dead_letter(arguments.delivery_id, datetime.now(UTC))
                        )
                    )
                else:
                    if arguments.age_seconds <= 0:
                        raise ValueError("notification stale age must be positive")
                    cutoff = datetime.now(UTC) - timedelta(seconds=arguments.age_seconds)
                    stdout.write(
                        render_notifications(
                            repository.list_stale_deliveries(cutoff, limit=arguments.limit)
                        )
                    )
            return 0
        if arguments.command == "notification-worker":
            from mediaflow.infrastructure.webhook import UrllibWebhookTransport

            with SQLiteTaskRepository(configuration.database_path) as repository:
                delivery_worker = NotificationWorker(
                    repository,
                    configuration.resolve_webhook_targets(),
                    UrllibWebhookTransport(),
                    delivery_lease_seconds=configuration.notification_delivery_lease_seconds,
                )
                if arguments.notification_worker_command == "run-next":
                    delivery = delivery_worker.run_next()
                    if delivery is None:
                        stdout.write("No due notification deliveries\n")
                        return 0
                    stdout.write(render_notification(delivery))
                    return 0 if delivery.status.value in {"delivered", "retry"} else 1
                poll = arguments.poll_seconds or configuration.notification_poll_seconds
                processed = _run_resident(
                    lambda stop: delivery_worker.run(
                        stop, poll_seconds=poll, sleep=lambda seconds: _wait(stop, seconds)
                    )
                )
                stdout.write(f"Notification worker stopped; processed={processed}\n")
            return 0
        if arguments.command == "execution-authorizations":
            if not configuration.remote_execution_enabled:
                raise ValueError("remote execution authorization is disabled")
            with SQLiteTaskRepository(configuration.database_path) as repository:
                service = ExecutionAuthorizationService(
                    repository,
                    maximum_ttl_seconds=configuration.remote_execution_maximum_ttl_seconds,
                    maximum_active_jobs=configuration.automation_maximum_active_jobs,
                    configuration_snapshot_id=getattr(
                        configuration, "configuration_snapshot_id", None
                    ),
                    configuration_snapshot_digest=getattr(
                        configuration, "configuration_snapshot_digest", None
                    ),
                )
                if arguments.execution_authorization_command == "issue":
                    issued = service.issue(
                        ttl_seconds=arguments.ttl_seconds,
                        max_items=arguments.max_items,
                        actor=arguments.actor,
                        note=arguments.note,
                    )
                    stdout.write(render_issued_execution_authorization(issued))
                elif arguments.execution_authorization_command == "list":
                    stdout.write(render_execution_authorizations(service.list()))
                elif arguments.execution_authorization_command == "show":
                    value = service.get(arguments.authorization_id)
                    if value is None:
                        raise LookupError(
                            f"execution authorization {arguments.authorization_id!r} was not found"
                        )
                    stdout.write(
                        render_execution_authorization(
                            value,
                            repository.list_execution_authorization_audit(value.authorization_id),
                        )
                    )
                else:
                    stdout.write(
                        render_execution_authorization(
                            service.revoke(arguments.authorization_id, actor=arguments.actor),
                            repository.list_execution_authorization_audit(
                                arguments.authorization_id
                            ),
                        )
                    )
            return 0
        if arguments.command == "security-audit":
            if arguments.limit < 1 or arguments.limit > 1000:
                raise ValueError("security audit limit must be between 1 and 1000")
            with SQLiteTaskRepository(configuration.database_path) as repository:
                stdout.write(
                    render_security_audit(repository.list_security_audit(limit=arguments.limit))
                )
            return 0
        if arguments.command == "tasks" and arguments.task_command in {
            "list",
            "show",
            "show-item",
            "pause",
            "ignore-item",
            "ignore-pending",
            "retry-request",
        }:
            with ExitStack() as stack:
                repository = stack.enter_context(SQLiteTaskRepository(configuration.database_path))
                recovery_admission = None
                if arguments.task_command in {"ignore-item", "ignore-pending", "retry-request"}:
                    configuration_repository = stack.enter_context(
                        SQLiteConfigurationRepository(configuration.database_path)
                    )
                    managed_service = ManagedConfigurationService(
                        configuration_repository,
                        bootstrap_database_path=configuration.database_path,
                    )
                    recovery_admission = RecoveryAdmissionService(
                        repository,
                        snapshot_validator=managed_service.validate_runtime_snapshot,
                    )
                if arguments.task_command == "list":
                    stdout.write(render_tasks(repository.list_tasks(limit=arguments.limit)))
                elif arguments.task_command == "show":
                    task = repository.get_task(arguments.task_id)
                    if task is None:
                        raise LookupError(f"task {arguments.task_id!r} was not found")
                    stdout.write(render_task(task, repository.list_items(task.task_id)))
                elif arguments.task_command == "show-item":
                    checkpoint_service = ProcessingCheckpointService(
                        repository, snapshot_validator=None
                    )
                    checkpoint = checkpoint_service.get(
                        arguments.item_id, task_id=arguments.task_id
                    )
                    stdout.write(render_recovery_checkpoint(checkpoint))
                elif arguments.task_command == "pause":
                    coordinator = PersistentTaskCoordinator(repository, repository)
                    task = coordinator.request_pause(arguments.task_id)
                    stdout.write(render_task(task, repository.list_items(task.task_id)))
                elif arguments.task_command == "ignore-pending":
                    decisions = ManualIgnoreService(
                        repository, recovery_admission=recovery_admission
                    ).ignore_pending(
                        actor=arguments.actor,
                        note=arguments.note,
                        limit=arguments.limit,
                        task_id=arguments.task_id,
                    )
                    stdout.write(render_manual_ignore_batch(decisions))
                elif arguments.task_command == "retry-request":
                    decisions = TaskRetryRequestService(
                        repository, recovery_admission=recovery_admission
                    ).request(
                        actor=arguments.actor,
                        note=arguments.note,
                        limit=arguments.limit,
                        task_id=arguments.task_id,
                    )
                    stdout.write(render_task_retry_request(decisions))
                else:
                    decision = ManualIgnoreService(
                        repository, recovery_admission=recovery_admission
                    ).ignore(
                        arguments.task_id,
                        arguments.item_id,
                        actor=arguments.actor,
                        note=arguments.note,
                    )
                    task = repository.get_task(arguments.task_id)
                    stdout.write(
                        render_manual_ignore(
                            decision,
                            task,
                            repository.list_items(arguments.task_id),
                        )
                    )
            return 0
        if arguments.command == "confirmations":
            with SQLiteTaskRepository(configuration.database_path) as repository:
                service = ConfirmationService(repository)
                if arguments.confirmation_command == "list":
                    values = repository.list_confirmations(
                        status=None if arguments.all else ConfirmationStatus.PENDING
                    )
                    stdout.write(render_confirmations(values))
                elif arguments.confirmation_command == "show":
                    value = repository.get_confirmation(arguments.confirmation_id)
                    if value is None:
                        raise LookupError(
                            f"confirmation {arguments.confirmation_id!r} was not found"
                        )
                    stdout.write(
                        render_confirmation(
                            value,
                            repository.list_confirmation_audit(value.confirmation_id),
                        )
                    )
                else:
                    value = service.resolve(
                        arguments.confirmation_id,
                        ConflictStrategy(arguments.strategy),
                        confirm_overwrite=arguments.confirm_overwrite,
                        actor=arguments.actor,
                        note=arguments.note,
                    )
                    stdout.write(render_confirmation(value, ()))
            return 0
        if arguments.command == "files":
            library_ids = tuple(
                item.library_id for item in configuration.resource_libraries if item.enabled
            )
            storage_ids = tuple(item.storage_id for item in configuration.storage_definitions)
            with ExitStack() as stack:
                file_index = stack.enter_context(
                    SQLiteFileIndexRepository(configuration.database_path)
                )
                task_repository = stack.enter_context(
                    SQLiteTaskRepository(configuration.database_path)
                )
                recovery_admission = None
                if arguments.file_command == "re-plan":
                    recovery_configuration_repository = stack.enter_context(
                        SQLiteConfigurationRepository(configuration.database_path)
                    )
                    recovery_configuration_service = ManagedConfigurationService(
                        recovery_configuration_repository,
                        bootstrap_database_path=configuration.database_path,
                    )
                    recovery_admission = RecoveryAdmissionService(
                        task_repository,
                        snapshot_validator=(
                            recovery_configuration_service.validate_runtime_snapshot
                        ),
                    )
                service = FileCatalogService(
                    file_index,
                    library_ids,
                    storage_ids,
                    task_repository=task_repository,
                )
                if arguments.file_command == "list":
                    scan_status = (
                        FileScanStatus(arguments.scan_status)
                        if arguments.scan_status is not None
                        else None
                    )
                    after = _file_catalog_cursor(
                        arguments.after,
                        arguments.cursor_file_id if arguments.after else None,
                    )
                    before = _file_catalog_cursor(
                        arguments.before,
                        arguments.cursor_file_id if arguments.before else None,
                    )
                    records = service.list(
                        FileCatalogFilter(
                            resource_library_id=arguments.resource_library,
                            storage_id=arguments.storage,
                            scan_status=scan_status,
                            query=arguments.query,
                            limit=arguments.limit,
                            after=after,
                            before=before,
                            recognition_type=arguments.recognition_type,
                            provider=arguments.provider,
                            provider_id=arguments.provider_id,
                            title=arguments.title,
                            task_id=arguments.task_id,
                            year=arguments.year,
                        )
                    )
                    stdout.write(render_file_catalog(records))
                elif arguments.file_command == "stats":
                    stats = service.stats(
                        resource_library_id=arguments.resource_library,
                        storage_id=arguments.storage,
                    )
                    stdout.write(render_file_catalog_stats(stats))
                elif arguments.file_command == "re-recognize":
                    decision = FileRecognitionRequestService(
                        service,
                        RecognitionRetryService(task_repository),
                    ).request(
                        arguments.file_id,
                        actor=arguments.actor,
                        note=arguments.note,
                    )
                    stdout.write(render_file_recognition_request(decision))
                elif arguments.file_command == "re-match":
                    review = FileMetadataCorrectionService(
                        service,
                        MetadataCorrectionService(
                            task_repository,
                            configuration.strategy.metadata_policies,
                        ),
                    ).resolve(
                        arguments.file_id,
                        query=arguments.query,
                        year=arguments.year,
                        media_type=arguments.media_type,
                        provider_id=arguments.provider_id,
                        actor=arguments.actor,
                        note=arguments.note,
                    )
                    stdout.write(render_file_metadata_re_match(review))
                elif arguments.file_command == "re-plan":
                    decision = FileReplanRequestService(
                        service,
                        recovery_admission=recovery_admission,
                    ).request(
                        arguments.file_id,
                        actor=arguments.actor,
                        note=arguments.note,
                    )
                    stdout.write(render_file_replan_request(decision))
                else:
                    detail = service.detail(
                        arguments.file_id,
                        resource_library_id=arguments.resource_library,
                    )
                    stdout.write(render_file_catalog_detail(detail))
            return 0
        if arguments.command == "storage":
            if arguments.storage_command == "list":
                stdout.write(render_storage_definitions(configuration.storage_definitions))
                return 0
            selected = (
                [arguments.storage_id]
                if arguments.storage_id
                else [item.storage_id for item in configuration.storage_definitions]
            )
            known = {item.storage_id for item in configuration.storage_definitions}
            unknown = set(selected) - known
            if unknown:
                raise ValueError(f"unknown Storage {sorted(unknown)[0]!r}")
            failures = 0
            lines = ["", "STORAGE CHECK", ""]
            for storage_id in selected:
                storage = None
                try:
                    storage = configuration.create_storages(storage_ids={storage_id})[storage_id]
                    _read_only_storage_check(storage)
                    lines.append(f"PASS | {storage_id} | read-only preflight succeeded")
                except Exception as error:
                    failures += 1
                    lines.append(f"FAIL | {storage_id} | {_safe_preflight_error(error)}")
                finally:
                    close = getattr(storage, "close", None)
                    if callable(close):
                        try:
                            close()
                        except Exception:
                            pass
            lines.extend(("", f"Total: {len(selected)}", f"Failed: {failures}", ""))
            stdout.write("\n".join(lines))
            return 1 if failures else 0
        if arguments.command == "jobs":
            with SQLiteTaskRepository(configuration.database_path) as repository:
                service = AutomationJobService(
                    repository,
                    maximum_active_jobs=configuration.automation_maximum_active_jobs,
                    configuration_snapshot_id=configuration.configuration_snapshot_id,
                    configuration_snapshot_digest=configuration.configuration_snapshot_digest,
                )
                if arguments.job_command == "list":
                    stdout.write(render_jobs(repository.list_jobs(limit=arguments.limit)))
                elif arguments.job_command == "show":
                    job = repository.get_job(arguments.job_id)
                    if job is None:
                        raise LookupError(f"automation job {arguments.job_id!r} was not found")
                    stdout.write(render_job(job))
                elif arguments.job_command == "submit":
                    job = service.submit(arguments.workflow, limit=arguments.limit)
                    stdout.write(render_job(job))
                elif arguments.job_command == "cancel":
                    stdout.write(render_job(service.cancel(arguments.job_id)))
                elif arguments.job_command == "stale":
                    stdout.write(render_jobs(service.stale(age_seconds=arguments.age_seconds)))
                else:
                    stdout.write(
                        render_job(
                            service.requeue_stale(
                                arguments.job_id, age_seconds=arguments.age_seconds
                            )
                        )
                    )
            return 0
        if arguments.command == "worker":
            with SQLiteTaskRepository(configuration.database_path) as repository:
                worker_service = AutomationWorker(
                    repository,
                    lambda job, cancelled: _run_queued_workflow(job, arguments.config, cancelled),
                    NotificationPublisher(
                        repository,
                        configuration.resolve_webhook_targets()
                        if hasattr(configuration, "resolve_webhook_targets")
                        else {},
                    ),
                )
                if arguments.worker_command == "run-next":
                    job = worker_service.run_next()
                    if job is None:
                        stdout.write("No pending automation jobs\n")
                        return 0
                    stdout.write(render_job(job))
                    return 0 if job.status.value in {"completed", "cancelled"} else 1
                poll = arguments.poll_seconds or getattr(configuration, "worker_poll_seconds", 5.0)
                processed = _run_resident(
                    lambda stop: worker_service.run(
                        stop, poll_seconds=poll, sleep=lambda seconds: _wait(stop, seconds)
                    )
                )
                stdout.write(f"Worker stopped; processed={processed}\n")
                return 0
        if arguments.command == "scheduler":
            with SQLiteTaskRepository(configuration.database_path) as repository:
                scheduler_service = IntervalScheduler(
                    repository,
                    configuration.automation_schedules,
                    NotificationPublisher(repository, configuration.webhooks),
                    maximum_active_jobs=configuration.automation_maximum_active_jobs,
                    configuration_snapshot_id=configuration.configuration_snapshot_id,
                    configuration_snapshot_digest=configuration.configuration_snapshot_digest,
                    configuration_snapshot_resolver=lambda: _managed_scheduler_configuration(
                        arguments.config
                    ),
                )
                if arguments.scheduler_command == "list":
                    stdout.write(
                        render_schedules(
                            configuration.automation_schedules,
                            repository.list_schedule_states(),
                        )
                    )
                    return 0
                if arguments.scheduler_command == "tick":
                    queued = scheduler_service.tick()
                    stdout.write(render_jobs(queued))
                    return 0
                if arguments.scheduler_command == "audit":
                    known = {item.schedule_id for item in configuration.automation_schedules}
                    if arguments.schedule_id and arguments.schedule_id not in known:
                        raise LookupError(f"schedule {arguments.schedule_id!r} was not found")
                    if arguments.limit < 1:
                        raise ValueError("schedule audit limit must be positive")
                    stdout.write(
                        render_schedule_audit(
                            repository.list_schedule_audit(
                                arguments.schedule_id, limit=arguments.limit
                            ),
                            configuration.automation_schedules,
                        )
                    )
                    return 0
                poll = arguments.poll_seconds or configuration.scheduler_poll_seconds
                emitted = _run_resident(
                    lambda stop: scheduler_service.run(
                        stop, poll_seconds=poll, sleep=lambda seconds: _wait(stop, seconds)
                    )
                )
                stdout.write(f"Scheduler stopped; emitted={emitted}\n")
                return 0
        if arguments.command == "api":
            loopback = _validate_api_bind_host(arguments.host)
            if not loopback and not arguments.allow_insecure_remote_http:
                raise ValueError(
                    "non-loopback API bind requires --allow-insecure-remote-http; "
                    "the development server does not provide TLS"
                )
            if not loopback:
                stderr.write(
                    "WARNING: serving authenticated traffic over unencrypted non-loopback HTTP; "
                    "use a trusted TLS reverse proxy\n"
                )
            principals = configuration.resolve_api_principals()
            bootstrap_document = _configuration_document(arguments.config)
            if not 1 <= arguments.port <= 65535:
                raise ValueError("API port must be between 1 and 65535")
            from wsgiref.simple_server import make_server

            from mediaflow.infrastructure.configuration_snapshot import (
                build_configuration_snapshot,
            )
            from mediaflow.interfaces.service_api import MediaFlowApi

            file_index_context = (
                nullcontext(None)
                if isinstance(configuration, ManagementBootstrapConfiguration)
                else SQLiteFileIndexRepository(configuration.database_path)
            )
            with (
                SQLiteTaskRepository(configuration.database_path) as repository,
                file_index_context as file_index,
                SQLiteConfigurationRepository(
                    configuration.database_path
                ) as configuration_repository,
            ):
                file_catalog = (
                    FileCatalogService(
                        file_index,
                        tuple(
                            item.library_id
                            for item in configuration.resource_libraries
                            if item.enabled
                        ),
                        tuple(item.storage_id for item in configuration.storage_definitions),
                        task_repository=repository,
                    )
                    if file_index is not None
                    else None
                )
                app = MediaFlowApi(
                    repository,
                    None,
                    getattr(configuration, "automation_schedules", ()),
                    principals=principals,
                    dashboard_resource_library_count=sum(
                        item.enabled for item in getattr(configuration, "resource_libraries", ())
                    ),
                    dashboard_media_library_count=sum(
                        item.enabled for item in getattr(configuration, "media_libraries", ())
                    ),
                    remote_execution_enabled=getattr(
                        configuration, "remote_execution_enabled", False
                    ),
                    remote_execution_maximum_ttl_seconds=(
                        getattr(configuration, "remote_execution_maximum_ttl_seconds", 900)
                    ),
                    maximum_active_jobs=getattr(
                        configuration, "automation_maximum_active_jobs", 100
                    ),
                    stale_job_age_seconds=getattr(
                        configuration, "automation_stale_job_age_seconds", 3600
                    ),
                    system_status=(
                        None
                        if isinstance(configuration, ManagementBootstrapConfiguration)
                        else build_configuration_snapshot(configuration)
                    ),
                    file_catalog=file_catalog,
                    file_index=file_index,
                    metadata_policies=getattr(
                        getattr(configuration, "strategy", None), "metadata_policies", ()
                    ),
                    configuration_service=ManagedConfigurationService(
                        configuration_repository,
                        bootstrap_database_path=configuration.database_path,
                    ),
                    configuration_snapshot_id=getattr(
                        configuration, "configuration_snapshot_id", None
                    ),
                    configuration_snapshot_digest=getattr(
                        configuration, "configuration_snapshot_digest", None
                    ),
                    bootstrap_document=bootstrap_document,
                    metadata_provider_registry_factory=(
                        LazyMetadataProviderRegistryFactory(
                            metadata_provider_registry_from_environment
                        )
                    ),
                )
                stdout.write(f"MediaFlow API listening on {arguments.host}:{arguments.port}\n")
                stdout.flush()
                with make_server(arguments.host, arguments.port, app) as server:
                    server.serve_forever()
            return 0

        storages = configuration.create_storages()
        if arguments.command == "scan":
            with (
                SQLiteTaskRepository(configuration.database_path) as repository,
                SQLiteFileIndexRepository(configuration.database_path) as file_index,
            ):
                operational_logger = (
                    SQLiteOperationalLogger(
                        repository,
                        "workflow",
                        configuration.operational_logging_minimum_level,
                    )
                    if configuration.operational_logging_enabled
                    else None
                )
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create(
                    "scan",
                    execute_authorized=False,
                    item_limit=arguments.limit,
                    configuration_snapshot_id=configuration.configuration_snapshot_id,
                    configuration_snapshot_digest=configuration.configuration_snapshot_digest,
                    require_configuration_snapshot=(
                        configuration.configuration_authority == "MANAGED"
                    ),
                )
                discovered = []

                def on_discovered(library, file) -> None:
                    discovered.append((library.library_id, file.storage_id, file.path))
                    coordinator.record_discovered(
                        task.task_id,
                        file.storage_id,
                        library.library_id,
                        file.path,
                        f"{file.storage_id}:{file.path}",
                    )

                def workflow_stop() -> bool:
                    return bool(
                        (cancellation_check and cancellation_check())
                        or coordinator.pause_requested(task.task_id)
                    )

                batch = ResourceLibraryScanner(
                    StorageScanner(storages, file_index, logger=operational_logger),
                    configuration.resource_libraries,
                    storages,
                ).scan_all(
                    limit=arguments.limit,
                    on_discovered=on_discovered,
                    cancellation_check=workflow_stop,
                )
                errors = tuple(error for result in batch.results for error in result.errors)
                cancelled = bool(cancellation_check and cancellation_check())
                if cancelled:
                    coordinator.cancel(task.task_id)
                elif coordinator.pause_requested(task.task_id):
                    coordinator.acknowledge_pause(task.task_id)
                else:
                    coordinator.finish(task.task_id, MediaOrganizerBatchResult((), errors))
                stdout.write(f"Task ID: {task.task_id}\n")
                stdout.write(render_scan(batch.results, discovered))
                return 130 if cancelled else 1 if errors else 0
        library = display_root = None
        if getattr(arguments, "path", None):
            library, display_root = _resource_library(configuration, arguments.path)
        resumed_scan = False
        if arguments.command == "tasks" and arguments.task_command == "resume":
            with SQLiteTaskRepository(configuration.database_path) as pause_repository:
                pause_original = pause_repository.get_task(arguments.task_id)
                resumed_scan = bool(
                    pause_original
                    and pause_original.status is PersistentTaskStatus.PAUSED
                    and pause_original.command == "scan"
                )
        providers = None
        if not (arguments.command == "analyze" and arguments.offline) and not resumed_scan:
            providers = metadata_provider_registry_from_environment(("tmdb",))
        strategy = strategy_runner_from_configuration(
            configuration.strategy, providers, storages=storages
        )
        if arguments.command == "analyze":
            assert library is not None and display_root is not None
            result = strategy.run_path(
                str(Path(arguments.path).resolve(strict=False)),
                live_metadata=not arguments.offline,
                resource_library_id=library.library_id,
                storage_id=library.storage_id,
                storage_path=_storage_path(
                    library.root_path,
                    str(
                        Path(arguments.path)
                        .resolve(strict=False)
                        .relative_to(Path(display_root).resolve(strict=False))
                    ),
                ),
            )
            stdout.write(render_strategy_result(result))
            return 0
        with (
            SQLiteTaskRepository(configuration.database_path) as repository,
            SQLiteFileIndexRepository(configuration.database_path) as file_index,
        ):
            operational_logger = (
                SQLiteOperationalLogger(
                    repository,
                    "workflow",
                    configuration.operational_logging_minimum_level,
                )
                if configuration.operational_logging_enabled
                else None
            )
            coordinator = PersistentTaskCoordinator(repository, repository)
            retry_items: tuple[PersistentTaskItem, ...] | None = None
            paused_resume = False
            original_items: tuple[PersistentTaskItem, ...] = ()
            if arguments.command == "tasks":
                original = coordinator.require(arguments.task_id)
                paused_resume = (
                    arguments.task_command == "resume"
                    and original.status is PersistentTaskStatus.PAUSED
                )
                if arguments.execute and not original.execute_authorized:
                    raise ValueError(
                        "original task was not execute-authorized; retry cannot enable execute"
                    )
                retry_items = coordinator.retryable_items(
                    original.task_id,
                    failed_only=arguments.task_command == "retry-failed",
                )
                original_items = repository.list_items(original.task_id)
                repository.reclaim_task_locks(original.task_id)
                execute = bool(arguments.execute and original.execute_authorized)
                task = coordinator.create(
                    original.command
                    if paused_resume
                    else f"{arguments.task_command}:{original.task_id}",
                    execute_authorized=execute,
                    scope_path=original.scope_path,
                    item_limit=original.item_limit,
                    configuration_snapshot_id=original.configuration_snapshot_id,
                    configuration_snapshot_digest=original.configuration_snapshot_digest,
                    require_configuration_snapshot=(
                        configuration.configuration_authority == "MANAGED"
                    ),
                )
            else:
                execute = arguments.command == "organize" and arguments.execute
                task = coordinator.create(
                    arguments.command,
                    execute_authorized=execute,
                    scope_path=arguments.path,
                    item_limit=arguments.limit,
                    configuration_snapshot_id=configuration.configuration_snapshot_id,
                    configuration_snapshot_digest=configuration.configuration_snapshot_digest,
                    require_configuration_snapshot=(
                        configuration.configuration_authority == "MANAGED"
                    ),
                )

            def workflow_stop() -> bool:
                return bool(
                    (cancellation_check and cancellation_check())
                    or coordinator.pause_requested(task.task_id)
                )

            service = MediaOrganizerService(
                strategy,
                StorageScanner(storages, file_index, logger=operational_logger),
                storages,
                {item.library_id: item for item in configuration.media_libraries},
                configuration.strategy.recognition_type_policies,
                JsonLinesOperationHistoryRepository(configuration.history_path),
                executor=OrganizerExecutor(operational_logger),
                source_display_roots=dict(configuration.resource_display_roots),
                logger=operational_logger,
                task_coordinator=coordinator,
                task_id=task.task_id,
                conflict_decisions={
                    (value.source_storage_id, value.source_path): value
                    for value in repository.list_confirmations(status=ConfirmationStatus.RESOLVED)
                }
                if retry_items is not None
                else {},
                metadata_selections={
                    (stored.storage_id, stored.source_path): MetadataSelection(
                        review.recognition_type,
                        review.metadata_policy_id,
                        review.selected_provider,
                        review.selected_provider_id,
                        review.selected_media_type,
                    )
                    for stored in (retry_items or ())
                    if (review := repository.get_metadata_review_for_item(stored.item_id))
                    and review.status is MetadataReviewStatus.RESOLVED
                    and review.selected_provider is not None
                    and review.selected_provider_id is not None
                    and review.selected_media_type is not None
                },
                metadata_corrections={
                    (stored.storage_id, stored.source_path): MetadataCorrectionSelection(
                        review.recognition_type,
                        review.metadata_policy_id,
                        review.provider_id,
                        review.corrected_query,
                        review.corrected_year,
                        review.corrected_media_type,
                        review.direct_provider_id,
                    )
                    for stored in (retry_items or ())
                    if (review := repository.get_metadata_correction_for_item(stored.item_id))
                    and review.status is MetadataCorrectionStatus.RESOLVED
                    and review.corrected_media_type is not None
                },
                classification_selections={
                    (stored.storage_id, stored.source_path): ClassificationSelection(
                        review.recognition_type,
                        review.classification_policy_id,
                        review.selected_rule_id,
                        review.selected_media_library_id,
                        review.selected_relative_path,
                    )
                    for stored in (retry_items or ())
                    if (review := repository.get_classification_review_for_item(stored.item_id))
                    and review.status is ClassificationReviewStatus.RESOLVED
                    and review.selected_rule_id is not None
                    and review.selected_media_library_id is not None
                    and review.selected_relative_path is not None
                },
                recognition_selections={
                    (stored.storage_id, stored.source_path): RecognitionSelection(
                        review.selected_recognition_type
                    )
                    for stored in (retry_items or ())
                    if (review := repository.get_recognition_review_for_item(stored.item_id))
                    and review.status is RecognitionReviewStatus.RESOLVED
                    and review.selected_recognition_type is not None
                },
                retry_policy=configuration.workflow_retry_policy,
                retry_cancellation_check=workflow_stop,
            )
            if retry_items is not None:
                libraries = {item.library_id: item for item in configuration.resource_libraries}
                retried = []
                for stored in retry_items:
                    resource = libraries.get(stored.resource_library_id)
                    if resource is None:
                        raise ValueError(
                            f"task item references missing ResourceLibrary "
                            f"{stored.resource_library_id!r}"
                        )
                    retried.append(
                        service.process_file(
                            stored.source_display,
                            resource_library=resource,
                            storage_path=stored.source_path,
                            execute=execute,
                        )
                    )
                summary = MediaOrganizerBatchResult(tuple(retried))
                if paused_resume:
                    already_seen = {
                        (stored.storage_id, stored.source_path) for stored in original_items
                    }
                    remaining_limit = (
                        max(0, original.item_limit - len(original_items))
                        if original.item_limit is not None
                        else None
                    )
                    continued = _continue_paused_scope(
                        service,
                        configuration,
                        original,
                        storages,
                        file_index,
                        coordinator,
                        task.task_id,
                        execute,
                        remaining_limit,
                        already_seen,
                        workflow_stop,
                        stdout,
                    )
                    summary = MediaOrganizerBatchResult(
                        summary.items + continued.items,
                        summary.scan_errors + continued.scan_errors,
                    )
            elif arguments.path is None:
                summary = service.process_all_libraries(
                    configuration.resource_libraries,
                    execute=execute,
                    limit=arguments.limit,
                    progress=lambda done, total, source: stdout.write(
                        f"PROGRESS {done}/{total or '?'} {source}\n"
                    ),
                    cancellation_check=workflow_stop,
                )
            else:
                assert library is not None and display_root is not None
                path = Path(arguments.path).resolve(strict=False)
                if path.is_dir():
                    summary = service.process_library(
                        library,
                        execute=execute,
                        limit=arguments.limit,
                        progress=lambda done, total, source: stdout.write(
                            f"PROGRESS {done}/{total or '?'} {source}\n"
                        ),
                        cancellation_check=workflow_stop,
                    )
                else:
                    storage_path = path.relative_to(
                        Path(display_root).resolve(strict=False)
                    ).as_posix()
                    storage_path = _storage_path(library.root_path, storage_path)
                    item = service.process_file(
                        path.as_posix(),
                        resource_library=library,
                        storage_path=storage_path,
                        execute=execute,
                    )
                    summary = MediaOrganizerBatchResult((item,))
            cancelled = bool(cancellation_check and cancellation_check())
            if cancelled:
                coordinator.cancel(task.task_id)
            elif coordinator.pause_requested(task.task_id):
                coordinator.acknowledge_pause(task.task_id)
            else:
                coordinator.finish(task.task_id, summary)
            stdout.write(f"Task ID: {task.task_id}\n")
            stdout.write(render_summary(summary, execute=execute))
            paused = coordinator.require(task.task_id).status is PersistentTaskStatus.PAUSED
            return 130 if cancelled else 75 if paused else 1 if summary.failed else 0
    except (OSError, ValueError, LookupError, RuntimeError) as error:
        stderr.write(f"mediaflow error: {error}\n")
        return 2
    finally:
        if runtime_lease is not None:
            runtime_lease.close()


def _runtime_lease_mode(arguments: argparse.Namespace) -> RuntimeLeaseMode | None:
    if arguments.command in {"config", "storage"}:
        return None
    if arguments.command == "api" and arguments.api_command in {"token", "credentials"}:
        return None
    if arguments.command == "database" and arguments.database_command == "restore":
        return RuntimeLeaseMode.EXCLUSIVE
    return RuntimeLeaseMode.SHARED


def _continue_paused_scope(
    service: MediaOrganizerService,
    configuration,
    original: PersistentTask,
    storages,
    file_index,
    coordinator: PersistentTaskCoordinator,
    task_id: str,
    execute: bool,
    limit: int | None,
    skip_sources: set[tuple[str, str]],
    cancellation_check: Callable[[], bool],
    stdout: TextIO,
) -> MediaOrganizerBatchResult:
    if limit == 0:
        return MediaOrganizerBatchResult(())
    if original.command == "scan":
        discovered = []

        def on_discovered(library, file) -> None:
            discovered.append(file.path)
            coordinator.record_discovered(
                task_id,
                file.storage_id,
                library.library_id,
                file.path,
                f"{file.storage_id}:{file.path}",
            )

        batch = ResourceLibraryScanner(
            StorageScanner(storages, file_index),
            configuration.resource_libraries,
            storages,
        ).scan_all(
            limit=limit,
            on_discovered=on_discovered,
            include_discovered=lambda library, file: (
                (
                    library.storage_id,
                    file.path,
                )
                not in skip_sources
            ),
            cancellation_check=cancellation_check,
        )
        errors = tuple(error for result in batch.results for error in result.errors)
        return MediaOrganizerBatchResult((), errors)
    if original.command not in {"preview", "organize"}:
        raise ValueError("paused task command cannot be continued")
    if original.scope_path is None:
        return service.process_all_libraries(
            configuration.resource_libraries,
            execute=execute,
            limit=limit,
            progress=lambda done, total, source: stdout.write(
                f"PROGRESS {done}/{total or '?'} {source}\n"
            ),
            cancellation_check=cancellation_check,
            skip_sources=skip_sources,
        )
    library, display_root = _resource_library(configuration, original.scope_path)
    path = Path(original.scope_path).resolve(strict=False)
    if path.is_dir():
        return service.process_library(
            library,
            execute=execute,
            limit=limit,
            progress=lambda done, total, source: stdout.write(
                f"PROGRESS {done}/{total or '?'} {source}\n"
            ),
            cancellation_check=cancellation_check,
            skip_sources=skip_sources,
        )
    relative = path.relative_to(Path(display_root).resolve(strict=False)).as_posix()
    storage_path = _storage_path(library.root_path, relative)
    if (library.storage_id, storage_path) in skip_sources:
        return MediaOrganizerBatchResult(())
    return MediaOrganizerBatchResult(
        (
            service.process_file(
                path.as_posix(),
                resource_library=library,
                storage_path=storage_path,
                execute=execute,
            ),
        )
    )


def render_summary(summary: MediaOrganizerBatchResult, *, execute: bool) -> str:
    lines = ["", "SUMMARY", "", f"Mode: {'EXECUTE' if execute else 'DRY_RUN'}"]
    for item in summary.items:
        status = (
            item.execution.status.value
            if item.execution
            else "FAILED"
            if item.error
            else "NEED_CONFIRM"
            if item.plan and item.plan.conflicts
            else "SKIPPED"
        )
        details = []
        if item.plan and item.plan.attachment_plans:
            details.append(f"attachments={len(item.plan.attachment_plans)}")
        if item.error:
            details.append(item.error)
        elif item.execution and item.execution.errors:
            details.append("; ".join(item.execution.errors))
        detail = " | ".join(details)
        lines.append(f"{status} | {item.source} | {detail}")
    lines.extend(
        (
            "",
            f"Total: {summary.total}",
            f"Matched: {summary.matched}",
            f"Conflicts: {summary.conflicts}",
            f"Moved: {summary.moved}",
            f"Failed: {summary.failed}",
            "",
        )
    )
    return "\n".join(lines)


def render_scan(results, discovered) -> str:
    lines = ["", "SCAN", ""]
    by_library = {result.resource_library_id: result for result in results}
    for library_id, result in by_library.items():
        lines.extend(
            (
                f"ResourceLibrary: {library_id}",
                f"Status: {result.status.value}",
                f"Found: {sum(1 for item in discovered if item[0] == library_id)}",
                f"Errors: {len(result.errors)}",
                "",
            )
        )
    lines.append(f"Total: {len(discovered)}")
    lines.extend(f"{storage_id}:{path}" for _, storage_id, path in discovered)
    lines.append("")
    return "\n".join(lines)


def render_tasks(tasks: tuple[PersistentTask, ...]) -> str:
    lines = ["", "TASKS", ""]
    for task in tasks:
        lines.append(
            f"{task.task_id} | {task.command} | {task.status.value} | "
            f"pause_requested={'yes' if task.pause_requested else 'no'} | "
            f"total={task.total_items} completed={task.completed_items} "
            f"failed={task.failed_items} | "
            f"snapshot={task.configuration_snapshot_id or '-'}"
        )
    lines.extend(("", f"Total: {len(tasks)}", ""))
    return "\n".join(lines)


def render_file_catalog(records) -> str:
    lines = ["", "FILE CATALOG", ""]
    for record in records:
        lines.append(
            f"{record.file_id} | {record.storage_id}:{record.resource_library_id}:{record.path} | "
            f"{record.scan_status.value} | size={record.size} | "
            f"updated={record.updated_at.isoformat()}"
        )
    lines.extend(("", f"Total: {len(records)}", ""))
    return "\n".join(lines)


def render_file_catalog_stats(stats) -> str:
    lines = [
        "",
        "FILE CATALOG STATS",
        "",
        f"Total: {stats.total}",
        "",
        "BY STATUS",
        "",
    ]
    for status in FileScanStatus:
        lines.append(f"{status.value}: {stats.by_status.get(status, 0)}")
    lines.append("")
    return "\n".join(lines)


def render_file_recognition_request(decision) -> str:
    return "\n".join(
        (
            "",
            "FILE RE-RECOGNITION REQUEST",
            "",
            f"Decision: {decision.decision_id}",
            f"Review: {decision.review_id}",
            f"Task: {decision.task_id}",
            f"Item: {decision.item_id}",
            f"Actor: {decision.actor}",
            "Media mutation: 0",
            "",
        )
    )


def render_file_metadata_re_match(review) -> str:
    return "\n".join(
        (
            "",
            "FILE METADATA RE-MATCH",
            "",
            f"Review: {review.review_id}",
            f"Status: {review.status.value}",
            f"Corrected query: {review.corrected_query or '-'}",
            f"Corrected year: {review.corrected_year or '-'}",
            f"Corrected media type: {review.corrected_media_type or '-'}",
            f"Direct provider ID: {review.direct_provider_id or '-'}",
            f"Actor: {review.actor or '-'}",
            "Media mutation: 0",
            "",
        )
    )


def render_file_replan_request(decision) -> str:
    return "\n".join(
        (
            "",
            "FILE RE-PLAN REQUEST",
            "",
            f"Decision: {decision.decision_id}",
            f"Task: {decision.task_id}",
            f"Item: {decision.item_id}",
            f"Actor: {decision.actor}",
            "Media mutation: 0",
            "",
        )
    )


def render_file_catalog_record(record) -> str:
    return "\n".join(
        (
            "",
            "FILE CATALOG RECORD",
            "",
            f"File ID: {record.file_id}",
            f"Storage: {record.storage_id}",
            f"ResourceLibrary: {record.resource_library_id}",
            f"Path: {record.path}",
            f"Filename: {record.filename}",
            f"Extension: {record.extension}",
            f"Size: {record.size}",
            f"Modified: {record.modified_at.isoformat()}",
            f"Stable since: {record.stable_since.isoformat() if record.stable_since else '-'}",
            f"Scan status: {record.scan_status.value}",
            f"Change: {record.change.value}",
            f"First seen: {record.first_seen_at.isoformat()}",
            f"Last seen: {record.last_seen_at.isoformat()}",
            f"Missing since: {record.missing_since.isoformat() if record.missing_since else '-'}",
            f"Last scan ID: {record.last_scan_id or '-'}",
            "",
        )
    )


def render_file_catalog_detail(detail) -> str:
    record = detail.record
    result = detail.latest_result
    lines = [
        "",
        "FILE CATALOG DETAIL",
        "",
        f"File ID: {record.file_id}",
        f"Storage: {record.storage_id}",
        f"ResourceLibrary: {record.resource_library_id}",
        f"Path: {record.path}",
        f"Filename: {record.filename}",
        f"Extension: {record.extension}",
        f"Size: {record.size}",
        f"Modified: {record.modified_at.isoformat()}",
        f"Stable since: {record.stable_since.isoformat() if record.stable_since else '-'}",
        f"Scan status: {record.scan_status.value}",
        f"Change: {record.change.value}",
        f"First seen: {record.first_seen_at.isoformat()}",
        f"Last seen: {record.last_seen_at.isoformat()}",
        f"Missing since: {record.missing_since.isoformat() if record.missing_since else '-'}",
        f"Last scan ID: {record.last_scan_id or '-'}",
        "",
        "LATEST TASK RESULT",
        "",
    ]
    if result is None:
        lines.extend(("None", ""))
    else:
        lines.extend(
            (
                f"Task: {result.task_id}",
                f"Item: {result.item_id}",
                f"Status: {result.status}",
                f"RecognitionType: {result.recognition_type or '-'}",
                f"Provider: {result.provider or '-'}",
                f"Provider ID: {result.provider_id or '-'}",
                f"Title: {result.title or '-'}",
                f"Metadata policy: {result.metadata_policy_id or '-'}",
                f"Naming policy: {result.naming_policy_id or '-'}",
                f"Classification policy: {result.classification_policy_id or '-'}",
                f"Organize policy: {result.organize_policy_id or '-'}",
                f"Operation: {result.operation or '-'}",
                f"Target: {result.destination_storage_id or '-'}:{result.destination_path or '-'}",
                f"Created: {result.created_at.isoformat()}",
                f"Retry attempts: {result.retry_attempts}",
                f"Cleanup status: {result.cleanup_status or '-'}",
                f"Error: {result.error or '-'}",
                "",
            )
        )
    return "\n".join(lines)


def render_task(task: PersistentTask, items: tuple[PersistentTaskItem, ...]) -> str:
    lines = [
        "",
        "TASK",
        "",
        f"ID: {task.task_id}",
        f"Command: {task.command}",
        f"Status: {task.status.value}",
        f"Pause requested: {'YES' if task.pause_requested else 'NO'}",
        f"Execute authorized: {'YES' if task.execute_authorized else 'NO'}",
        f"Configuration snapshot: {task.configuration_snapshot_id or '-'}",
        f"Configuration digest: {task.configuration_snapshot_digest or '-'}",
        f"Created: {task.created_at.isoformat()}",
        f"Ignored items: {sum(item.status is TaskItemStatus.IGNORED for item in items)}",
        "",
        "ITEMS",
        "",
    ]
    for item in items:
        detail = item.error or item.destination_path or ""
        lines.append(
            f"{item.status.value} | {item.storage_id}:{item.source_path} | "
            f"attempts={item.attempts} | {detail}"
        )
    lines.extend(("", f"Total: {len(items)}", ""))
    return "\n".join(lines)


def render_recovery_checkpoint(checkpoint) -> str:
    lines = [
        "",
        "TASK ITEM RECOVERY CHECKPOINT",
        "",
        f"Task: {checkpoint.task_id}",
        f"Item: {checkpoint.item_id}",
        f"Status: {checkpoint.status}",
        f"Stage: {checkpoint.stage.value}",
        f"Effect certainty: {checkpoint.effect_certainty.value}",
        f"Retry safety: {checkpoint.retry_safety.value}",
        f"Checkpoint version: {checkpoint.checkpoint_version}",
        f"Permitted actions: {', '.join(checkpoint.permitted_action_ids) or '-'}",
    ]
    request = checkpoint.active_recovery_request
    if request is not None:
        lines.extend(
            (
                "",
                "ADMITTED RECOVERY REQUEST",
                "",
                f"Request: {request.request_id}",
                f"Action: {request.action_id}",
                f"Actor: {request.actor}",
                f"Requested: {request.requested_at.isoformat()}",
                f"Bound checkpoint: {request.checkpoint_version}",
                f"Source: {request.source_storage_id}:{request.source_path}",
                f"Snapshot: {request.configuration_snapshot_id}",
                f"Next action: {request.next_action}",
            )
        )
    continuation = checkpoint.recovery_continuation
    if continuation is not None:
        lines.extend(
            (
                "",
                "RECOVERY CONTINUATION",
                "",
                f"Continuation: {continuation.continuation_id}",
                f"Request: {continuation.request_id}",
                f"Status: {continuation.status.value}",
                f"Boundary: {continuation.boundary}",
                f"Bound checkpoint: {continuation.checkpoint_version}",
                f"Job: {continuation.job_id}",
                f"New Task: {continuation.new_task_id or '-'}",
                f"New Result: {continuation.new_result_id or '-'}",
                f"Actor: {continuation.actor}",
                f"Created: {continuation.created_at.isoformat()}",
                f"Error: {continuation.error or '-'}",
                f"Recovery: {continuation.recovery or '-'}",
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_manual_ignore(decision, task, items) -> str:
    return "\n".join(
        (
            "",
            "MANUAL IGNORE",
            "",
            f"Decision: {decision.decision_id}",
            f"Task: {decision.task_id}",
            f"Item: {decision.item_id}",
            f"Review kind: {decision.review_kind.value}",
            f"Review: {decision.review_id}",
            f"Actor: {decision.actor}",
            "Media mutation: 0",
            render_task(task, items),
        )
    )


def render_manual_ignore_batch(decisions) -> str:
    lines = [
        "",
        "BATCH MANUAL IGNORE",
        "",
        f"Ignored: {len(decisions)}",
        "Media mutation: 0",
        "",
        "DECISIONS",
        "",
    ]
    lines.extend(
        f"{item.decision_id} | {item.review_kind.value} | {item.task_id} | "
        f"{item.item_id} | {item.review_id} | {item.actor}"
        for item in decisions
    )
    lines.extend(("", f"Total: {len(decisions)}", ""))
    return "\n".join(lines)


def render_task_retry_request(decisions) -> str:
    lines = [
        "",
        "BATCH TASK RETRY REQUEST",
        "",
        f"Requested: {len(decisions)}",
        "Media mutation: 0",
        "",
        "DECISIONS",
        "",
    ]
    lines.extend(
        f"{item.decision_id} | {item.task_id} | {item.item_id} | {item.actor}" for item in decisions
    )
    lines.extend(("", f"Total: {len(decisions)}", ""))
    return "\n".join(lines)


def render_confirmations(values) -> str:
    lines = ["", "CONFIRMATIONS", ""]
    for value in values:
        lines.append(
            f"{value.confirmation_id} | {value.status.value} | {value.conflict_type} | "
            f"{value.source_storage_id}:{value.source_path} -> "
            f"{value.destination_storage_id}:{value.destination_path}"
        )
    lines.extend(("", f"Total: {len(values)}", ""))
    return "\n".join(lines)


def render_confirmation(value, audit) -> str:
    lines = [
        "",
        "CONFIRMATION",
        "",
        f"ID: {value.confirmation_id}",
        f"Status: {value.status.value}",
        f"Conflict: {value.conflict_type}",
        f"Configured strategy: {value.configured_strategy}",
        f"Selected strategy: {value.selected_strategy or '-'}",
        f"Source: {value.source_storage_id}:{value.source_path}",
        f"Destination: {value.destination_storage_id}:{value.destination_path}",
        f"Overwrite authorized: {'YES' if value.overwrite_authorized else 'NO'}",
        "",
        "AUDIT",
        "",
    ]
    lines.extend(
        f"{entry.decided_at.isoformat()} | {entry.strategy} | {entry.actor or '-'}"
        for entry in audit
    )
    lines.append("")
    return "\n".join(lines)


def render_storage_definitions(definitions) -> str:
    lines = ["", "STORAGES", ""]
    for value in definitions:
        capabilities = _declared_capabilities(value.storage_type, value.read_only)
        lines.append(
            f"{value.storage_id} | {value.storage_type} | root={value.root_path or '/'} | "
            f"readOnly={'YES' if value.read_only else 'NO'} | {capabilities}"
        )
    lines.extend(("", f"Total: {len(definitions)}", ""))
    return "\n".join(lines)


def render_jobs(values) -> str:
    lines = ["", "AUTOMATION JOBS", ""]
    for value in values:
        lines.append(
            f"{value.job_id} | {value.command.value} | {value.status.value} | "
            f"limit={value.limit or '-'} | task={value.task_id or '-'} | "
            f"schedule={value.schedule_id or '-'}"
        )
    lines.extend(("", f"Total: {len(values)}", ""))
    return "\n".join(lines)


def render_job(value) -> str:
    retry_safe = (
        "-" if value.failure_retry_safe is None else ("YES" if value.failure_retry_safe else "NO")
    )
    return "\n".join(
        (
            "",
            "AUTOMATION JOB",
            "",
            f"ID: {value.job_id}",
            f"Command: {value.command.value}",
            f"Status: {value.status.value}",
            f"Limit: {value.limit or '-'}",
            f"Task ID: {value.task_id or '-'}",
            f"Error: {value.error or '-'}",
            f"Cancellation requested: {'YES' if value.cancellation_requested else 'NO'}",
            f"Schedule ID: {value.schedule_id or '-'}",
            f"Execute authorized: {'YES' if value.execute_authorized else 'NO'}",
            f"Configuration snapshot: {value.configuration_snapshot_id or '-'}",
            f"Configuration digest: {value.configuration_snapshot_digest or '-'}",
            f"Failure category: {value.failure_category or '-'}",
            f"Durable state: {value.failure_durable_state or '-'}",
            f"Side effects: {value.failure_side_effects or '-'}",
            f"Retry safe: {retry_safe}",
            f"Next action: {value.failure_next_action or '-'}",
            "",
        )
    )


def render_notifications(values) -> str:
    lines = ["", "NOTIFICATION DELIVERIES", ""]
    for value in values:
        lines.append(
            f"{value.delivery_id} | {value.event_type.value} | {value.webhook_id} | "
            f"{value.status.value} | attempts={value.attempts} | "
            f"updated={value.updated_at.isoformat()} | failure={value.failure_category or '-'}"
        )
    lines.extend(("", f"Total: {len(values)}", ""))
    return "\n".join(lines)


def render_operational_logs(values) -> str:
    lines = ["", "OPERATIONAL LOGS", ""]
    for value in values:
        identifiers = ",".join(
            item
            for item in (value.task_id, value.job_id, value.plan_id, value.status)
            if item is not None
        )
        lines.append(
            f"{value.occurred_at.isoformat()} | {value.level.name} | {value.component} | "
            f"{value.event} | {identifiers or '-'}"
        )
    lines.extend(("", f"Total: {len(values)}", ""))
    return "\n".join(lines)


def render_database_backup(value, operation: str) -> str:
    return "\n".join(
        (
            "",
            f"DATABASE {operation.upper()}",
            "",
            f"Path: {value.destination}",
            f"Schema: {value.schema_version}",
            f"Size: {value.size_bytes}",
            f"SHA-256: {value.sha256}",
            f"Checked: {value.created_at.isoformat()}",
            "",
        )
    )


def render_upgrade_preflight(value) -> str:
    return "\n".join(
        (
            "",
            "UPGRADE PREFLIGHT",
            "",
            f"Status: {value.status.upper()}",
            f"Application: {value.application_version}",
            f"Python: {value.python_version} "
            f"(supported: {'YES' if value.python_supported else 'NO'})",
            f"Supported schema: {value.supported_schema}",
            f"Runtime schema: {value.runtime_schema}",
            f"Backup schema: {value.backup_schema}",
            f"Migration required: {'YES' if value.migration_required else 'NO'}",
            f"Backup age hours: {value.backup_age_hours:.3f}",
            f"Maximum backup age hours: {value.maximum_backup_age_hours:g}",
            f"Backup size: {value.backup_size_bytes}",
            f"Backup SHA-256: {value.backup_sha256}",
            f"Checked: {value.checked_at.isoformat()}",
            "",
        )
    )


def render_database_restore(value) -> str:
    return "\n".join(
        (
            "",
            "DATABASE RESTORE",
            "",
            "Status: RESTORED",
            f"Destination: {value.destination}",
            f"Schema: {value.schema_version}",
            f"Migration required: {'YES' if value.migration_required else 'NO'}",
            f"Size: {value.size_bytes}",
            f"SHA-256: {value.sha256}",
            f"Completed: {value.completed_at.isoformat()}",
            "",
        )
    )


def render_migration_rehearsal(value) -> str:
    counts = ", ".join(f"{name}={count}" for name, count in value.record_counts)
    return "\n".join(
        (
            "",
            "MIGRATION REHEARSAL",
            "",
            "Status: PASS",
            f"Application: {value.application_version}",
            f"Source schema: {value.source_schema}",
            f"Target schema: {value.target_schema}",
            f"Migration required: {'YES' if value.migration_required else 'NO'}",
            f"Migration performed on copy: {'YES' if value.migration_performed else 'NO'}",
            f"Record counts: {counts}",
            f"Backup size: {value.backup_size_bytes}",
            f"Backup SHA-256: {value.backup_sha256}",
            f"Temporary cleanup: {'PASS' if value.temporary_cleanup_complete else 'FAIL'}",
            f"Completed: {value.completed_at.isoformat()}",
            "",
        )
    )


def render_notification(value) -> str:
    return render_notifications((value,))


def render_issued_execution_authorization(issued) -> str:
    value = issued.authorization
    return "\n".join(
        (
            "",
            "EXECUTION AUTHORIZATION ISSUED",
            "",
            f"ID: {value.authorization_id}",
            f"Expires: {value.expires_at.isoformat()}",
            f"Max items: {value.max_items}",
            f"Token: {issued.token}",
            "Token shown once: YES",
            "",
        )
    )


def render_execution_authorizations(values) -> str:
    lines = ["", "EXECUTION AUTHORIZATIONS", ""]
    for value in values:
        lines.append(
            f"{value.authorization_id} | {value.status.value} | "
            f"expires={value.expires_at.isoformat()} | maxItems={value.max_items} | "
            f"job={value.consumed_job_id or '-'}"
        )
    lines.extend(("", f"Total: {len(values)}", ""))
    return "\n".join(lines)


def render_execution_authorization(value, audit) -> str:
    lines = [
        "",
        "EXECUTION AUTHORIZATION",
        "",
        f"ID: {value.authorization_id}",
        f"Status: {value.status.value}",
        f"Created: {value.created_at.isoformat()}",
        f"Expires: {value.expires_at.isoformat()}",
        f"Max items: {value.max_items}",
        f"Consumed job: {value.consumed_job_id or '-'}",
        "",
        "AUDIT",
        "",
    ]
    lines.extend(
        f"{item.occurred_at.isoformat()} | {item.action} | job={item.job_id or '-'} | "
        f"actor={item.actor or '-'}"
        for item in audit
    )
    lines.append("")
    return "\n".join(lines)


def render_security_audit(values) -> str:
    lines = ["", "SECURITY AUDIT", ""]
    lines.extend(
        f"{item.occurred_at.isoformat()} | {item.principal_id or '-'} | "
        f"{item.method} {item.route} | {item.action} | {item.outcome} | "
        f"status={item.http_status} | request={item.request_id}"
        for item in values
    )
    lines.extend(("", f"Total: {len(values)}", ""))
    return "\n".join(lines)


def render_dashboard(value) -> str:
    lines = [
        "",
        "DASHBOARD",
        "",
        f"As of: {value.as_of.isoformat()}",
        f"Resource libraries: {value.resource_libraries}",
        f"Media libraries: {value.media_libraries}",
        f"Indexed files: {value.files.total}",
        f"Ready: {value.files.ready}",
        f"Unstable: {value.files.unstable}",
        f"Missing: {value.files.missing}",
        f"File errors: {value.files.errors}",
        f"Tasks: {value.tasks.total} (running={value.tasks.running}, failed={value.tasks.failed})",
        f"Jobs: {value.jobs.total} (pending={value.jobs.pending}, running={value.jobs.running}, "
        f"failed={value.jobs.failed})",
        f"Pending confirmations: {value.pending_confirmations}",
        f"Pending metadata reviews: {value.pending_metadata_reviews}",
        f"Pending classification reviews: {value.pending_classification_reviews}",
        f"Dead-letter notifications: {value.dead_letter_notifications}",
        "",
        "RECENT FAILURES",
        "",
    ]
    lines.extend(
        f"{item.occurred_at.isoformat()} | {item.kind} | {item.identifier} | "
        f"{item.status} | {item.category}"
        for item in value.recent_failures
    )
    if not value.recent_failures:
        lines.append("None")
    lines.append("")
    return "\n".join(lines)


def render_metadata_reviews(values) -> str:
    lines = ["", "METADATA REVIEWS", ""]
    lines.extend(
        f"{item.review_id} | {item.status.value} | {item.outcome} | "
        f"{item.source_storage_id}:{item.source_path} | {item.query}"
        for item in values
    )
    lines.extend(("", f"Total: {len(values)}", ""))
    return "\n".join(lines)


def render_metadata_corrections(values) -> str:
    lines = ["", "METADATA CORRECTIONS", ""]
    lines.extend(
        f"{item.review_id} | {item.status.value} | "
        f"{item.source_storage_id}:{item.source_path} | "
        f"query={item.original_query} | year={item.original_year or '-'} | "
        f"type={item.original_media_type}"
        for item in values
    )
    lines.extend(("", f"Total: {len(values)}", ""))
    return "\n".join(lines)


def render_metadata_correction(review, audit=()) -> str:
    lines = [
        "",
        "METADATA CORRECTION",
        "",
        f"ID: {review.review_id}",
        f"Status: {review.status.value}",
        f"Source: {review.source_storage_id}:{review.source_path}",
        f"RecognitionType: {review.recognition_type}",
        f"MetadataPolicy: {review.metadata_policy_id}",
        f"Provider: {review.provider_id}",
        f"Original query: {review.original_query}",
        f"Original year: {review.original_year or '-'}",
        f"Original media type: {review.original_media_type}",
        f"Corrected query: {review.corrected_query or '-'}",
        f"Corrected year: {review.corrected_year or '-'}",
        f"Corrected media type: {review.corrected_media_type or '-'}",
        f"Direct provider ID: {review.direct_provider_id or '-'}",
        "",
        "AUDIT",
        "",
    ]
    lines.extend(
        f"{item.decided_at.isoformat()} | query={item.corrected_query or '-'} | "
        f"year={item.corrected_year or '-'} | type={item.corrected_media_type} | "
        f"providerId={item.direct_provider_id or '-'} | actor={item.actor or '-'}"
        for item in audit
    )
    if not audit:
        lines.append("None")
    lines.append("")
    return "\n".join(lines)


def render_metadata_correction_batch(reviews) -> str:
    lines = [
        "",
        "BATCH METADATA CORRECTION",
        "",
        f"Resolved: {len(reviews)}",
        "Media mutation: 0",
        "",
        "REVIEWS",
        "",
    ]
    lines.extend(
        f"{item.review_id} | query={item.corrected_query or '-'} | "
        f"year={item.corrected_year or '-'} | type={item.corrected_media_type or '-'} | "
        f"providerId={item.direct_provider_id or '-'} | actor={item.actor or '-'}"
        for item in reviews
    )
    lines.extend(("", f"Total: {len(reviews)}", ""))
    return "\n".join(lines)


def render_recognition_reviews(values) -> str:
    lines = ["", "RECOGNITION REVIEWS", ""]
    lines.extend(
        f"{item.review_id} | {item.status.value} | {item.source_storage_id}:{item.source_path}"
        for item in values
    )
    lines.extend(("", f"Total: {len(values)}", ""))
    return "\n".join(lines)


def render_recognition_batch_retry(decisions) -> str:
    lines = [
        "",
        "BATCH RECOGNITION RETRY",
        "",
        f"Requested: {len(decisions)}",
        "Media mutation: 0",
        "",
        "DECISIONS",
        "",
    ]
    lines.extend(
        f"{item.decision_id} | {item.review_id} | {item.item_id} | {item.actor}"
        for item in decisions
    )
    lines.extend(("", f"Total: {len(decisions)}", ""))
    return "\n".join(lines)


def render_recognition_batch_resolve(reviews) -> str:
    lines = [
        "",
        "BATCH RECOGNITION RESOLVE",
        "",
        f"Resolved: {len(reviews)}",
        "Media mutation: 0",
        "",
        "REVIEWS",
        "",
    ]
    lines.extend(
        f"{item.review_id} | {item.selected_recognition_type} | {item.actor or '-'}"
        for item in reviews
    )
    lines.extend(("", f"Total: {len(reviews)}", ""))
    return "\n".join(lines)


def render_recognition_review(review, choices, audit=(), retry_audit=()) -> str:
    lines = [
        "",
        "RECOGNITION REVIEW",
        "",
        f"ID: {review.review_id}",
        f"Status: {review.status.value}",
        f"Source: {review.source_storage_id}:{review.source_path}",
        f"Selected RecognitionType: {review.selected_recognition_type or '-'}",
        "",
        "CHOICES",
        "",
    ]
    lines.extend(
        f"{item.recognition_type_id} | {item.name} | {item.description}" for item in choices
    )
    lines.extend(("", "DECISION AUDIT", ""))
    lines.extend(
        f"{item.decided_at.isoformat()} | {item.recognition_type_id} | {item.actor or '-'}"
        for item in audit
    )
    if not audit:
        lines.append("None")
    lines.extend(("", "RETRY AUDIT", ""))
    lines.extend(
        f"{item.decided_at.isoformat()} | retry_requested | {item.actor}" for item in retry_audit
    )
    if not retry_audit:
        lines.append("None")
    lines.append("")
    return "\n".join(lines)


def render_metadata_review(review, candidates, audit=()) -> str:
    lines = [
        "",
        "METADATA REVIEW",
        "",
        f"ID: {review.review_id}",
        f"Status: {review.status.value}",
        f"Outcome: {review.outcome}",
        f"Source: {review.source_storage_id}:{review.source_path}",
        f"RecognitionType: {review.recognition_type}",
        f"MetadataPolicy: {review.metadata_policy_id}",
        f"Query: {review.query}",
        f"Selected rank: {review.selected_rank or '-'}",
        f"Selected candidate: {review.selected_provider}:{review.selected_provider_id}"
        if review.selected_provider_id
        else "Selected candidate: -",
        "",
        "CANDIDATES",
        "",
    ]
    lines.extend(
        f"{item.rank} | {item.provider}:{item.provider_id} | {item.title} | "
        f"year={item.canonical_year or '-'} | score={item.total_score}"
        for item in candidates
    )
    lines.extend(("", "DECISION AUDIT", ""))
    lines.extend(
        f"{item.decided_at.isoformat()} | rank={item.selected_rank} | "
        f"{item.provider}:{item.provider_id} | {item.actor or '-'}"
        for item in audit
    )
    if not audit:
        lines.append("None")
    lines.append("")
    return "\n".join(lines)


def render_metadata_review_batch(reviews) -> str:
    lines = [
        "",
        "BATCH METADATA REVIEW",
        "",
        f"Resolved: {len(reviews)}",
        "Media mutation: 0",
        "",
        "REVIEWS",
        "",
    ]
    lines.extend(
        f"{item.review_id} | rank={item.selected_rank or '-'} | "
        f"{item.selected_provider or '-'}:{item.selected_provider_id or '-'} | "
        f"{item.selected_media_type or '-'} | {item.actor or '-'}"
        for item in reviews
    )
    lines.extend(("", f"Total: {len(reviews)}", ""))
    return "\n".join(lines)


def render_classification_reviews(values) -> str:
    lines = ["", "CLASSIFICATION REVIEWS", ""]
    lines.extend(
        f"{item.review_id} | {item.status.value} | {item.source_storage_id}:"
        f"{item.source_path} | {item.title}"
        for item in values
    )
    lines.extend(("", f"Total: {len(values)}", ""))
    return "\n".join(lines)


def render_classification_review(review, choices, audit=()) -> str:
    lines = [
        "",
        "CLASSIFICATION REVIEW",
        "",
        f"ID: {review.review_id}",
        f"Status: {review.status.value}",
        f"Source: {review.source_storage_id}:{review.source_path}",
        f"RecognitionType: {review.recognition_type}",
        f"ClassificationPolicy: {review.classification_policy_id}",
        f"Media: {review.title} ({review.canonical_year or '-'})",
        f"Selected rank: {review.selected_rank or '-'}",
        f"Selected rule: {review.selected_rule_id or '-'}",
        "",
        "CHOICES",
        "",
    ]
    lines.extend(
        f"{item.rank} | {item.rule_id} | {item.media_library_id}:{item.relative_path} | "
        f"priority={item.priority}"
        for item in choices
    )
    lines.extend(("", "DECISION AUDIT", ""))
    lines.extend(
        f"{item.decided_at.isoformat()} | rank={item.selected_rank} | "
        f"{item.rule_id} | {item.actor or '-'}"
        for item in audit
    )
    if not audit:
        lines.append("None")
    lines.append("")
    return "\n".join(lines)


def _run_queued_workflow(
    job, configured_path: str | None, cancellation_check: Callable[[], bool]
) -> str | None:
    try:
        _require_queued_job_snapshot(job, configured_path)
        resolved_configuration = None
        if job.configuration_snapshot_id:
            resolved_configuration = _configuration(
                configured_path,
                snapshot_id=job.configuration_snapshot_id,
                snapshot_digest=job.configuration_snapshot_digest,
            )
    except RuntimeSnapshotUnavailable as error:
        if job.command is AutomationCommand.FILE_METADATA_CORRECTION:
            _fail_metadata_correction_continuation_snapshot(job, configured_path)
        if job.command is AutomationCommand.RECOVERY_CONTINUATION:
            _fail_recovery_continuation_snapshot(job, configured_path)
        raise _automation_configuration_unavailable(error) from error
    if job.command is AutomationCommand.FILE_METADATA_CORRECTION:
        if resolved_configuration is None:
            raise RuntimeError("metadata correction continuation has no resolved configuration")
        return _run_metadata_correction_continuation(
            job, resolved_configuration, cancellation_check
        )
    if job.command is AutomationCommand.RECOVERY_CONTINUATION:
        if resolved_configuration is None:
            raise RuntimeError("recovery continuation has no resolved configuration")
        return _run_recovery_continuation(job, resolved_configuration, cancellation_check)
    args = []
    resolved = configured_path or os.environ.get("MEDIAFLOW_CONFIG")
    if resolved:
        args.extend(("--config", resolved))
    if job.configuration_snapshot_id:
        args.extend(("--configuration-snapshot-id", job.configuration_snapshot_id))
    if job.configuration_snapshot_digest:
        args.extend(("--configuration-snapshot-digest", job.configuration_snapshot_digest))
    args.append(job.command.value)
    if job.limit is not None:
        args.extend(("--limit", str(job.limit)))
    if job.command is AutomationCommand.ORGANIZE:
        if not job.execute_authorized:
            raise RuntimeError("organize job lacks persisted execute authorization")
        args.append("--execute")
    elif job.execute_authorized:
        raise RuntimeError("non-organize job must not carry execute authorization")
    output, errors = io.StringIO(), io.StringIO()
    code = final_main(
        args,
        stdout=output,
        stderr=errors,
        cancellation_check=cancellation_check,
        _resolved_configuration=resolved_configuration,
    )
    task_id = None
    for line in output.getvalue().splitlines():
        if line.startswith("Task ID: "):
            task_id = line.removeprefix("Task ID: ").strip()
            break
    if code == 130:
        raise AutomationCancelled(task_id)
    if code:
        raise RuntimeError("queued workflow returned a failure status")
    return task_id


def _fail_metadata_correction_continuation_snapshot(job, configured_path: str | None) -> None:
    resolved = configured_path or os.environ.get("MEDIAFLOW_CONFIG")
    if not resolved:
        return
    try:
        database_path = _bootstrap_database_path(_configuration_document(resolved))
    except (OSError, ValueError, RuntimeSnapshotUnavailable):
        return
    try:
        with SQLiteTaskRepository(database_path) as repository:
            MetadataCorrectionContinuationWorkerService(repository).failed(
                job.job_id, snapshot_unavailable=True, queued=True
            )
    except (OSError, LookupError, ValueError, RuntimeError):
        return


def _run_metadata_correction_continuation(
    job, configuration: RuntimeConfiguration, cancellation_check: Callable[[], bool]
) -> str | None:
    with (
        SQLiteTaskRepository(configuration.database_path) as repository,
        SQLiteFileIndexRepository(configuration.database_path) as file_index,
    ):
        continuation_service = MetadataCorrectionContinuationWorkerService(repository)
        prepared = None
        started = False
        task_id: str | None = None
        try:
            if cancellation_check():
                raise AutomationCancelled()
            prepared = continuation_service.prepare(job.job_id, file_index=file_index)
            continuation_service.started(job.job_id)
            started = True
            if cancellation_check():
                continuation_service.cancelled(job.job_id)
                raise AutomationCancelled()
            if (
                configuration.configuration_snapshot_id
                != prepared.continuation.configuration_snapshot_id
                or configuration.configuration_snapshot_digest
                != prepared.continuation.configuration_snapshot_digest
            ):
                raise RuntimeError("runtime configuration snapshot does not match continuation")
            resource = next(
                (
                    item
                    for item in configuration.resource_libraries
                    if item.library_id == prepared.source_item.resource_library_id
                ),
                None,
            )
            if resource is None:
                raise ValueError(
                    "task item references missing ResourceLibrary "
                    f"{prepared.source_item.resource_library_id!r}"
                )
            providers = metadata_provider_registry_from_environment((prepared.selection.provider,))
            storages = configuration.create_storages()
            strategy = strategy_runner_from_configuration(
                configuration.strategy, providers, storages=storages
            )
            operational_logger = (
                SQLiteOperationalLogger(
                    repository,
                    "workflow",
                    configuration.operational_logging_minimum_level,
                )
                if configuration.operational_logging_enabled
                else None
            )
            coordinator = PersistentTaskCoordinator(repository, repository)
            task = coordinator.create(
                f"metadata-correction-continuation:{prepared.continuation.continuation_id}",
                execute_authorized=False,
                scope_path=prepared.source_item.source_display,
                item_limit=1,
                configuration_snapshot_id=prepared.continuation.configuration_snapshot_id,
                configuration_snapshot_digest=(prepared.continuation.configuration_snapshot_digest),
                require_configuration_snapshot=True,
            )
            task_id = task.task_id
            repository.bind_metadata_correction_continuation_task(job.job_id, task.task_id)

            def workflow_stop() -> bool:
                return bool(cancellation_check() or coordinator.pause_requested(task_id or ""))

            service = MediaOrganizerService(
                strategy,
                StorageScanner(storages, file_index, logger=operational_logger),
                storages,
                {item.library_id: item for item in configuration.media_libraries},
                configuration.strategy.recognition_type_policies,
                JsonLinesOperationHistoryRepository(configuration.history_path),
                executor=OrganizerExecutor(operational_logger),
                source_display_roots=dict(configuration.resource_display_roots),
                logger=operational_logger,
                task_coordinator=coordinator,
                task_id=task.task_id,
                metadata_corrections={
                    (prepared.source_item.storage_id, prepared.source_item.source_path): (
                        prepared.selection
                    )
                },
                retry_policy=configuration.workflow_retry_policy,
                retry_cancellation_check=workflow_stop,
                secret_free_errors=True,
            )
            item = service.process_file(
                prepared.source_item.source_display,
                resource_library=resource,
                storage_path=prepared.source_item.source_path,
                execute=False,
            )
            if cancellation_check():
                coordinator.cancel(task.task_id)
                continuation_service.cancelled(job.job_id)
                raise AutomationCancelled(task.task_id)
            finished = coordinator.finish(task.task_id, MediaOrganizerBatchResult((item,)))
            task_id = finished.task_id
            continuation = continuation_service.finish(job.job_id, finished.task_id)
            if continuation.status.value == "failed":
                raise RuntimeError("metadata correction continuation failed")
            return continuation.new_task_id
        except AutomationCancelled:
            if task_id is not None:
                active_task = repository.get_task(task_id)
                if active_task is not None and active_task.status is PersistentTaskStatus.RUNNING:
                    coordinator.cancel(task_id)
            if started:
                continuation_service.cancelled(job.job_id)
            elif prepared is not None:
                continuation_service.cancelled(job.job_id)
            raise
        except Exception:
            if task_id is not None:
                failed_task = repository.get_task(task_id)
                if failed_task is not None and failed_task.status is PersistentTaskStatus.RUNNING:
                    now = datetime.now(UTC)
                    repository.update_task(
                        replace(
                            failed_task,
                            status=PersistentTaskStatus.FAILED,
                            updated_at=now,
                            completed_at=now,
                            error="continuation failed before Task completion",
                        )
                    )
            if started:
                continuation_service.failed(job.job_id, task_id=task_id)
            else:
                continuation_service.failed(job.job_id, queued=True, preflight=True)
            raise


def _fail_recovery_continuation_snapshot(job, configured_path: str | None) -> None:
    resolved = configured_path or os.environ.get("MEDIAFLOW_CONFIG")
    if not resolved:
        return
    try:
        database_path = _bootstrap_database_path(_configuration_document(resolved))
    except (OSError, ValueError, RuntimeSnapshotUnavailable):
        return
    try:
        with SQLiteTaskRepository(database_path) as repository:
            RecoveryContinuationWorkerService(repository).failed(
                job.job_id, snapshot_unavailable=True, queued=True
            )
    except (OSError, LookupError, ValueError, RuntimeError):
        return


def _run_recovery_continuation(
    job, configuration: RuntimeConfiguration, cancellation_check: Callable[[], bool]
) -> str | None:
    with (
        SQLiteTaskRepository(configuration.database_path) as repository,
        SQLiteFileIndexRepository(configuration.database_path) as file_index,
    ):
        continuation_service = RecoveryContinuationWorkerService(repository)
        prepared = None
        started = False
        task_id: str | None = None
        try:
            if cancellation_check():
                raise AutomationCancelled()
            prepared = continuation_service.prepare(job.job_id)
            continuation_service.started(job.job_id)
            started = True
            if cancellation_check():
                continuation_service.cancelled(job.job_id)
                raise AutomationCancelled()
            if (
                configuration.configuration_snapshot_id
                != prepared.continuation.configuration_snapshot_id
                or configuration.configuration_snapshot_digest
                != prepared.continuation.configuration_snapshot_digest
            ):
                raise RuntimeError("runtime configuration snapshot does not match continuation")
            resource = next(
                (
                    item
                    for item in configuration.resource_libraries
                    if item.library_id == prepared.source_item.resource_library_id
                ),
                None,
            )
            if resource is None:
                raise ValueError(
                    "task item references missing ResourceLibrary "
                    f"{prepared.source_item.resource_library_id!r}"
                )
            provider_ids = tuple(
                dict.fromkeys(
                    policy.provider_id
                    for policy in configuration.strategy.metadata_policies
                    if policy.enabled and policy.provider_id
                )
            )
            providers = metadata_provider_registry_from_environment(provider_ids or ("tmdb",))
            storages = configuration.create_storages()
            strategy = strategy_runner_from_configuration(
                configuration.strategy, providers, storages=storages
            )
            operational_logger = (
                SQLiteOperationalLogger(
                    repository,
                    "workflow",
                    configuration.operational_logging_minimum_level,
                )
                if configuration.operational_logging_enabled
                else None
            )
            coordinator = PersistentTaskCoordinator(repository, repository)
            task = coordinator.create(
                f"recovery-continuation:{prepared.continuation.continuation_id}",
                execute_authorized=False,
                scope_path=prepared.source_item.source_display,
                item_limit=1,
                configuration_snapshot_id=prepared.continuation.configuration_snapshot_id,
                configuration_snapshot_digest=(prepared.continuation.configuration_snapshot_digest),
                require_configuration_snapshot=True,
            )
            task_id = task.task_id
            repository.bind_recovery_continuation_task(job.job_id, task.task_id)

            def workflow_stop() -> bool:
                return bool(cancellation_check() or coordinator.pause_requested(task_id or ""))

            service = MediaOrganizerService(
                strategy,
                StorageScanner(storages, file_index, logger=operational_logger),
                storages,
                {item.library_id: item for item in configuration.media_libraries},
                configuration.strategy.recognition_type_policies,
                JsonLinesOperationHistoryRepository(configuration.history_path),
                executor=OrganizerExecutor(operational_logger),
                source_display_roots=dict(configuration.resource_display_roots),
                logger=operational_logger,
                task_coordinator=coordinator,
                task_id=task.task_id,
                retry_policy=configuration.workflow_retry_policy,
                retry_cancellation_check=workflow_stop,
                secret_free_errors=True,
            )
            item = service.process_file(
                prepared.source_item.source_display,
                resource_library=resource,
                storage_path=prepared.source_item.source_path,
                execute=False,
            )
            if cancellation_check():
                coordinator.cancel(task.task_id)
                continuation_service.cancelled(job.job_id)
                raise AutomationCancelled(task.task_id)
            finished = coordinator.finish(task.task_id, MediaOrganizerBatchResult((item,)))
            task_id = finished.task_id
            continuation = continuation_service.finish(job.job_id, finished.task_id)
            if continuation.status.value == "failed":
                raise RuntimeError("recovery continuation failed")
            return continuation.new_task_id
        except AutomationCancelled:
            if task_id is not None:
                active_task = repository.get_task(task_id)
                if active_task is not None and active_task.status is PersistentTaskStatus.RUNNING:
                    coordinator.cancel(task_id)
            if started:
                continuation_service.cancelled(job.job_id)
            elif prepared is not None:
                continuation_service.cancelled(job.job_id)
            raise
        except Exception:
            if task_id is not None:
                failed_task = repository.get_task(task_id)
                if failed_task is not None and failed_task.status is PersistentTaskStatus.RUNNING:
                    now = datetime.now(UTC)
                    repository.update_task(
                        replace(
                            failed_task,
                            status=PersistentTaskStatus.FAILED,
                            updated_at=now,
                            completed_at=now,
                            error="continuation failed before Task completion",
                        )
                    )
            if started:
                continuation_service.failed(job.job_id, task_id=task_id)
            else:
                continuation_service.failed(job.job_id, queued=True, preflight=True)
            raise


def _automation_configuration_unavailable(
    error: RuntimeSnapshotUnavailable,
) -> AutomationConfigurationUnavailable:
    allowed_categories = {
        "active_missing",
        "active_unreadable",
        "digest_corrupt",
        "job_snapshot_incomplete",
        "job_snapshot_missing",
        "runtime_invalid",
        "schema_unsupported",
        "snapshot_digest_mismatch",
        "snapshot_missing",
        "snapshot_not_published",
        "snapshot_unreadable",
    }
    category = error.reason if error.reason in allowed_categories else "configuration_unavailable"
    return AutomationConfigurationUnavailable(
        AutomationFailureEvidence(
            category,
            "saved_configuration_unavailable",
            "none",
            False,
            "restore the saved published revision, or explicitly create new work under "
            "the current Active configuration",
        )
    )


def _require_queued_job_snapshot(job, configured_path: str | None) -> None:
    """Reject legacy unpinned work once managed authority exists.

    The worker command intentionally claims jobs before loading workflow
    configuration.  A queued row without the immutable pair must therefore be
    rejected at the handler boundary instead of silently rebinding to the
    current Active revision.  Before managed activation, JSON bootstrap jobs
    remain compatible with the pre-managed runtime.
    """

    snapshot_id = getattr(job, "configuration_snapshot_id", None)
    snapshot_digest = getattr(job, "configuration_snapshot_digest", None)
    if bool(snapshot_id) != bool(snapshot_digest):
        raise RuntimeSnapshotUnavailable(
            "queued automation Job has an incomplete configuration snapshot pin",
            revision_id=snapshot_id,
            digest=snapshot_digest,
            reason="job_snapshot_incomplete",
        )
    if snapshot_id and snapshot_digest:
        return
    if not configured_path and not os.environ.get("MEDIAFLOW_CONFIG"):
        # Direct unit/service invocations may intentionally exercise the
        # handler without a production bootstrap document.  The production
        # worker entry point always loads the management bootstrap first, so
        # this compatibility branch cannot bypass managed authority there.
        return
    document = _configuration_document(configured_path)
    database_path = _bootstrap_database_path(document)
    with SQLiteConfigurationRepository(database_path) as repository:
        if not repository.has_managed_activation():
            return
        marker = repository.last_known_active()
    raise RuntimeSnapshotUnavailable(
        "legacy automation Job has no managed configuration snapshot pin; "
        "recreate the Job under the current Active revision",
        revision_id=marker.get("revisionId") if marker else None,
        version=(marker.get("revisionSequence") if marker else None),
        digest=marker.get("digest") if marker else None,
        reason="job_snapshot_missing",
    )


def render_schedules(definitions, states) -> str:
    state_by_id = {item.schedule_id: item for item in states}
    lines = ["", "INTERVAL SCHEDULES", ""]
    for value in definitions:
        state = state_by_id.get(value.schedule_id)
        timing = (
            f"cron={value.expression} | timezone={value.timezone}"
            if isinstance(value, CronSchedule)
            else f"interval={value.interval_seconds:g}s"
        )
        local_next = (
            state.next_run_at.astimezone(ZoneInfo(value.timezone)).isoformat()
            if state and isinstance(value, CronSchedule)
            else "-"
        )
        lines.append(
            f"{value.schedule_id} | {value.command.value} | "
            f"enabled={'YES' if value.enabled else 'NO'} | {timing} | "
            f"limit={value.limit or '-'} | nextUtc="
            f"{state.next_run_at.isoformat() if state else '-'} | nextLocal={local_next}"
        )
    lines.extend(("", f"Total: {len(definitions)}", ""))
    return "\n".join(lines)


def render_schedule_audit(values, definitions=()) -> str:
    definitions_by_id = {item.schedule_id: item for item in definitions}
    lines = ["", "SCHEDULE AUDIT", ""]
    for value in values:
        definition = definitions_by_id.get(value.schedule_id)
        local = (
            value.occurrence_at.astimezone(ZoneInfo(definition.timezone)).isoformat()
            if isinstance(definition, CronSchedule)
            else "-"
        )
        lines.append(
            f"{value.emitted_at.isoformat()} | {value.schedule_id} | "
            f"occurrenceUtc={value.occurrence_at.isoformat()} | occurrenceLocal={local} | "
            f"job={value.job_id} | "
            f"command={value.command.value} | next={value.next_run_at.isoformat()}"
        )
    lines.extend(("", f"Total: {len(values)}", ""))
    return "\n".join(lines)


def _run_resident(run: Callable[[Callable[[], bool]], int]) -> int:
    stopped = threading.Event()
    previous = {}

    def request_stop(_signum, _frame) -> None:
        stopped.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous[signum] = signal.signal(signum, request_stop)
    try:
        return run(stopped.is_set)
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def _wait(stop: Callable[[], bool], seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while not stop():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        threading.Event().wait(min(remaining, 0.25))


def _declared_capabilities(storage_type: str, read_only: bool) -> str:
    if read_only:
        return "move=NO copy=NO delete=NO hardLink=NO softLink=NO"
    links = storage_type == "local"
    return (
        "move=YES copy=YES delete=YES "
        f"hardLink={'YES' if links else 'NO'} softLink={'YES' if links else 'NO'}"
    )


def _read_only_storage_check(storage) -> None:
    health = getattr(storage, "health_check", None)
    if callable(health):
        health()
    else:
        connect = getattr(storage, "connect", None)
        if callable(connect):
            connect()
        storage.list("")


def _file_catalog_cursor(timestamp: str | None, file_id: str | None):
    if timestamp is None and file_id is None:
        return None
    if timestamp is None or file_id is None:
        raise ValueError("file catalog cursor requires both timestamp and file ID")
    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError as error:
        raise ValueError("file catalog cursor timestamp must be ISO-8601") from error
    return parsed, file_id


def _safe_preflight_error(error: Exception) -> str:
    from mediaflow.domain.storage import StorageError

    if isinstance(error, StorageError):
        return f"{error.code.value}: {error}"
    if isinstance(error, (ValueError, RuntimeError, OSError)):
        return str(error)
    return type(error).__name__


def _configuration_document(path: str | None) -> object:
    configured = path or os.environ.get("MEDIAFLOW_CONFIG")
    if not configured:
        raise ValueError("--config or MEDIAFLOW_CONFIG is required")
    try:
        return json.loads(Path(configured).read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"configuration file could not be read: {error}") from error


def _configuration(
    path: str | None,
    *,
    use_managed: bool = True,
    snapshot_id: str | None = None,
    snapshot_digest: str | None = None,
) -> RuntimeConfiguration:
    raw_document = _configuration_document(path)
    if not use_managed:
        return load_runtime_configuration(raw_document)
    bootstrap_database_path = _bootstrap_database_path(raw_document)
    try:
        with SQLiteConfigurationRepository(bootstrap_database_path) as repository:
            active = (
                repository.get_revision(snapshot_id)
                if snapshot_id
                else repository.get_active_revision()
            )
    except RuntimeSnapshotUnavailable:
        raise
    except Exception as error:
        if not snapshot_id:
            raise
        raise RuntimeSnapshotUnavailable(
            f"managed configuration snapshot {snapshot_id!r} is unreadable",
            revision_id=snapshot_id,
            digest=snapshot_digest,
            reason="snapshot_unreadable",
        ) from error
    if active is None:
        if snapshot_id:
            raise RuntimeSnapshotUnavailable(
                f"managed configuration snapshot {snapshot_id!r} is unavailable",
                revision_id=snapshot_id,
                digest=snapshot_digest,
                reason="snapshot_missing",
            )
        with SQLiteConfigurationRepository(bootstrap_database_path) as repository:
            if repository.has_managed_activation():
                marker = repository.last_known_active()
                raise RuntimeSnapshotUnavailable(
                    "managed Active configuration is unavailable; "
                    "restore the last published snapshot or stage a new Draft",
                    revision_id=marker.get("revisionId") if marker else None,
                    version=marker.get("revisionSequence") if marker else None,
                    digest=marker.get("digest") if marker else None,
                    reason="active_missing",
                )
        return load_runtime_configuration(raw_document)
    if active.schema_version != MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION:
        raise RuntimeSnapshotUnavailable(
            f"managed configuration snapshot {active.revision_id!r} schema is unsupported",
            revision_id=active.revision_id,
            version=active.revision_sequence,
            digest=active.digest,
            reason="schema_unsupported",
        )
    if snapshot_id and active.status.value not in {"active", "superseded"}:
        raise RuntimeSnapshotUnavailable(
            f"managed configuration snapshot {snapshot_id!r} is not a published revision",
            revision_id=active.revision_id,
            version=active.revision_sequence,
            digest=active.digest,
            reason="snapshot_not_published",
        )
    if snapshot_digest and active.digest != snapshot_digest:
        raise RuntimeSnapshotUnavailable(
            f"managed configuration snapshot {active.revision_id!r} digest does not match the Job",
            revision_id=active.revision_id,
            version=active.revision_sequence,
            digest=active.digest,
            reason="snapshot_digest_mismatch",
        )
    canonical = json.dumps(
        active.document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != active.digest:
        raise RuntimeSnapshotUnavailable(
            f"managed configuration snapshot {active.revision_id!r} digest is corrupt",
            revision_id=active.revision_id,
            version=active.revision_sequence,
            digest=active.digest,
            reason="digest_corrupt",
        )
    try:
        resolved = load_managed_runtime_configuration(
            active.document,
            bootstrap_database_path=bootstrap_database_path,
        )
    except Exception as error:
        raise RuntimeSnapshotUnavailable(
            f"managed Active configuration {active.revision_id!r} is unavailable: "
            f"{type(error).__name__}",
            revision_id=active.revision_id,
            version=active.revision_sequence,
            digest=active.digest,
            reason="runtime_invalid",
        ) from error
    return with_managed_snapshot(
        resolved,
        snapshot_id=active.revision_id,
        digest=active.digest,
    )


def _bootstrap_database_path(document: object) -> str:
    """Read only the bootstrap DB locator before managed authority is known.

    Once an Active revision exists, the rest of the JSON document is not trusted
    for workflow resolution. This small bootstrap field is needed solely to find
    the managed revision store and is never treated as active strategy content.
    """
    if not isinstance(document, dict):
        raise RuntimeSnapshotUnavailable("configuration bootstrap is not a JSON object")
    persistence = document.get("persistence")
    if not isinstance(persistence, dict):
        raise RuntimeSnapshotUnavailable("configuration bootstrap persistence is unavailable")
    value = persistence.get("databasePath", ".mediaflow/mediaflow.sqlite3")
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise RuntimeSnapshotUnavailable("configuration bootstrap databasePath is invalid")
    return value


def _task_snapshot_identity(path: str | None, task_id: str) -> tuple[str, str] | None:
    """Read a persisted Task's configuration pin before workflow bootstrap.

    This is deliberately limited to the two commands that continue existing
    work.  It does not resolve strategy content or construct Storage/Provider
    objects; it only preserves the immutable identity already recorded at the
    Task boundary. Legacy Tasks without a pin fail closed once managed authority
    has been activated; before activation they remain bootstrap work.
    """
    try:
        document = _configuration_document(path)
        database_path = _bootstrap_database_path(document)
        with SQLiteTaskRepository(database_path) as repository:
            task = repository.get_task(task_id)
        if task is not None and not task.configuration_snapshot_id:
            with SQLiteConfigurationRepository(database_path) as configuration_repository:
                if configuration_repository.has_managed_activation():
                    raise RuntimeSnapshotUnavailable(
                        "legacy Task has no managed configuration snapshot pin; "
                        "recreate the Task under the current Active configuration"
                    )
    except RuntimeSnapshotUnavailable:
        raise
    except (OSError, ValueError, RuntimeError):
        return None
    if task is None or not task.configuration_snapshot_id:
        return None
    return task.configuration_snapshot_id, task.configuration_snapshot_digest or ""


def _managed_snapshot_identity(path: str | None) -> tuple[str, str] | None:
    """Resolve the current managed identity for long-lived Job producers."""

    document = _configuration_document(path)
    database_path = _bootstrap_database_path(document)
    with SQLiteConfigurationRepository(database_path) as repository:
        active = repository.get_active_revision()
        if active is None:
            if repository.has_managed_activation():
                raise RuntimeSnapshotUnavailable(
                    "managed Active configuration is unavailable; scheduler is fail-closed",
                    reason="active_missing",
                )
            return None
        if active.schema_version != MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION:
            raise RuntimeSnapshotUnavailable(
                f"managed Active configuration {active.revision_id!r} schema is unsupported",
                revision_id=active.revision_id,
                version=active.revision_sequence,
                digest=active.digest,
                reason="schema_unsupported",
            )
        if (
            hashlib.sha256(
                json.dumps(
                    active.document,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            ).hexdigest()
            != active.digest
        ):
            raise RuntimeSnapshotUnavailable(
                f"managed Active configuration {active.revision_id!r} digest is corrupt",
                revision_id=active.revision_id,
                version=active.revision_sequence,
                digest=active.digest,
                reason="digest_corrupt",
            )
        try:
            load_managed_runtime_configuration(
                active.document,
                bootstrap_database_path=database_path,
            )
        except Exception as error:
            raise RuntimeSnapshotUnavailable(
                f"managed Active configuration {active.revision_id!r} is unavailable: "
                f"{type(error).__name__}: {str(error)[:400]}",
                revision_id=active.revision_id,
                version=active.revision_sequence,
                digest=active.digest,
                reason="runtime_invalid",
            ) from error
        return active.revision_id, active.digest


def _managed_scheduler_configuration(
    path: str | None,
) -> SchedulerConfigurationSnapshot | None:
    """Resolve schedule definitions and pin from one current runtime revision."""

    configuration = _configuration(path)
    if not configuration.configuration_snapshot_id:
        return None
    return SchedulerConfigurationSnapshot(
        configuration.configuration_snapshot_id,
        configuration.configuration_snapshot_digest or "",
        configuration.automation_schedules,
        configuration.automation_maximum_active_jobs,
    )


_HOST_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")


def _validate_api_bind_host(host: str) -> bool:
    if (
        not host
        or len(host) > 253
        or host != host.strip()
        or any(value in host for value in "/\\\x00")
    ):
        raise ValueError("API host must be a valid hostname or IP address")
    if host.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        labels = host[:-1].split(".") if host.endswith(".") else host.split(".")
        if not labels or any(not _HOST_LABEL.fullmatch(label) for label in labels):
            raise ValueError("API host must be a valid hostname or IP address") from None
        return False


def render_api_credentials(values) -> str:
    lines = ["API CREDENTIALS", ""]
    if not values:
        return "\n".join(lines + ["No API principals configured", ""])
    for value in values:
        lines.append(
            " | ".join(
                (
                    value.principal_id,
                    ",".join(role.value for role in value.roles),
                    value.token_env,
                    "ENABLED" if value.enabled else "DISABLED",
                    "SET" if value.configured else "UNSET",
                )
            )
        )
    return "\n".join(lines + [""])


def _resource_library(configuration: RuntimeConfiguration, path: str) -> tuple[object, str]:
    candidate = Path(path).resolve(strict=False)
    roots = []
    libraries = {item.library_id: item for item in configuration.resource_libraries}
    for library_id, value in configuration.resource_display_roots:
        root = Path(value).resolve(strict=False)
        if candidate == root or root in candidate.parents:
            roots.append((len(root.parts), library_id, root.as_posix()))
    if not roots:
        raise ValueError("path is not inside a configured ResourceLibrary")
    _, library_id, root = max(roots)
    return libraries[library_id], root


def _storage_path(library_root: str, relative_to_display_root: str) -> str:
    return "/".join(
        value.strip("/") for value in (library_root, relative_to_display_root) if value.strip("/")
    )
