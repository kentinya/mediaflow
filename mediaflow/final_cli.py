from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TextIO
from uuid import uuid4

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import (
    ManagedConfigurationService,
)
from mediaflow.application.manual_ignore import ManualIgnoreService
from mediaflow.application.media_organizer import (
    IncompleteOrganizingScope,
    MediaOrganizerBatchResult,
    MediaOrganizerService,
    incomplete_scope_failure,
)
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.application.recovery_admission import RecoveryAdmissionService
from mediaflow.application.scanner import StorageScanner
from mediaflow.application.storage_browser import StorageBrowserError
from mediaflow.application.strategy_test import strategy_runner_from_configuration
from mediaflow.application.task_flow_settlement import (
    TaskFlowSettlementInputs,
    settle_task_flow,
)
from mediaflow.application.task_runtime import KernelTaskCoordinator, PersistentTaskCoordinator
from mediaflow.cli import render_strategy_result
from mediaflow.domain.configuration_management import (
    ManagedConfigurationStatus,
    RuntimeSnapshotUnavailable,
)
from mediaflow.domain.failure import decode_failure_explanation
from mediaflow.domain.logging import LogLevel
from mediaflow.domain.notification import NotificationDeliveryStatus
from mediaflow.domain.task_persistence import (
    SETTLED_ITEM_STATUSES,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
    task_item_counts,
)
from mediaflow.domain.task_scheduling import TaskControl
from mediaflow.infrastructure.configuration_data_switch import (
    ConfigurationDataSwitchScope,
    read_configuration_data_switch,
)
from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository
from mediaflow.infrastructure.metadata_provider_bootstrap import (
    metadata_provider_registry_from_environment,
)
from mediaflow.infrastructure.operational_logging import SQLiteOperationalLogger
from mediaflow.infrastructure.runtime_configuration import (
    RuntimeConfiguration,
    is_minimal_management_bootstrap,
    load_managed_runtime_configuration,
    load_management_bootstrap,
    with_managed_snapshot,
)
from mediaflow.infrastructure.runtime_lease import RuntimeDatabaseLease, RuntimeLeaseMode
from mediaflow.infrastructure.sqlite_applicability import (
    evaluate_database_applicability,
    read_database_markers,
)
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_configuration_schema import (
    CONFIGURATION_SCHEMA_VERSION,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.runtime_support import (
    attach_task_terminal_notifications as _attach_task_terminal_notifications,
)
from mediaflow.runtime_support import (
    bootstrap_database_path as _bootstrap_database_path,
)
from mediaflow.runtime_support import (
    configuration_document as _configuration_document,
)
from mediaflow.runtime_support import (
    resolve_configuration as _configuration,
)


def final_main(
    argv: list[str],
    *,
    stdout: TextIO,
    stderr: TextIO,
    cancellation_check: Callable[[], bool] | None = None,
    _resolved_configuration: RuntimeConfiguration | None = None,
    _task_observer: Callable[[str], None] | None = None,
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
    initialize = config_commands.add_parser(
        "initialize", help="publish an empty managed configuration"
    )
    initialize.add_argument("--actor", default="local-cli")
    publish = config_commands.add_parser(
        "publish", help="check and publish one complete configuration document"
    )
    publish.add_argument("--file", help="JSON file; defaults to the current Active document")
    publish.add_argument("--actor", default="local-cli")
    publish.add_argument(
        "--replace-active",
        action="store_true",
        help="explicitly replace an unavailable managed Active from --file",
    )
    retire_unpublished = config_commands.add_parser(
        "retire-unpublished",
        help="review and switch a previous store to published-history-only structure",
    )
    retire_unpublished.add_argument(
        "--confirm",
        action="store_true",
        help="apply the reviewed data switch in one transaction",
    )
    analyze = commands.add_parser("analyze", help="analyze one file without planning execution")
    analyze.add_argument("path")
    analyze.add_argument("--offline", action="store_true")
    organize = commands.add_parser("organize", help="organize one file or a directory")
    organize.add_argument("path", nargs="?")
    organize.add_argument("--limit", type=int)
    organize.add_argument("--execute", action="store_true")
    batch = commands.add_parser("batch", help="explicit all-ResourceLibrary batch operations")
    batch_commands = batch.add_subparsers(dest="batch_command", required=True)
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
    task_cancel = task_commands.add_parser("cancel")
    task_cancel.add_argument("task_id")
    # ``retry-request`` and the independent ``retry-failed`` entrance are
    # absent from the command surface: new organizing starts from Files/CLI
    # organize and an existing Task's own four-type continuation; there is no
    # separate failure-retry command and no alias that would recreate one.
    storage_command = commands.add_parser("storage", help="Storage configuration and preflight")
    storage_commands = storage_command.add_subparsers(dest="storage_command", required=True)
    storage_commands.add_parser("list", help="list configured Storages without connecting")
    storage_check = storage_commands.add_parser("check", help="run read-only Storage preflight")
    storage_check.add_argument("storage_id", nargs="?")
    files = commands.add_parser(
        "files",
        help="read the live directory of one Active ResourceLibrary or MediaLibrary",
    )
    file_commands = files.add_subparsers(dest="file_command", required=True)
    file_list = file_commands.add_parser(
        "list",
        help="list one live library directory (read-only; nothing is recorded)",
    )
    library_scope = file_list.add_mutually_exclusive_group(required=True)
    library_scope.add_argument(
        "--resource-library",
        metavar="ID",
        help="ResourceLibrary ID to read the current live directory from",
    )
    library_scope.add_argument(
        "--media-library",
        metavar="ID",
        help="MediaLibrary ID to read the current live directory from",
    )
    file_list.add_argument(
        "--path",
        default="",
        help="library-relative directory (default: the library root)",
    )
    file_list.add_argument("--limit", type=int, default=100)
    file_list.add_argument("--cursor")
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
    arguments, unsupported_arguments = parser.parse_known_args(argv)
    if unsupported_arguments:
        parser.error("unrecognized arguments: " + " ".join(unsupported_arguments))
    if arguments.command == "batch":
        arguments.command = arguments.batch_command
        arguments.path = None
    runtime_lease: RuntimeDatabaseLease | None = None
    direct_organize_worker_id: str | None = None
    try:
        # A resumed/retried workflow must resolve the snapshot pinned to the
        # original Task before loading the runtime strategy.  Otherwise a
        # process restart after activation could silently run the old Task
        # against the new Active configuration.  The standalone retry-failed
        # entrance was retired (Slice 47 RO-6); a four-type continuation
        # resolves its own pinned snapshot inside its admitting service.
        snapshot_id = arguments.configuration_snapshot_id
        snapshot_digest = arguments.configuration_snapshot_digest

        # Database backup/restore are intentionally bootstrap-only.  Resolving
        # managed workflow configuration for them would open the configured
        # runtime database before the command's own read-only/atomic safety
        # checks run.
        configuration_management_command = (
            arguments.command == "config"
            and arguments.config_command
            in {
                "status",
                "initialize",
                "publish",
                "retire-unpublished",
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
        managed_command = not configuration_management_command and not (
            arguments.command == "config" and arguments.config_command == "validate"
        )
        if _resolved_configuration is not None:
            configuration = _resolved_configuration
        elif arguments.command == "files":
            # ``files list`` is a strictly read-only library read.  It resolves
            # the exact Active revision itself through a ``mode=ro`` connection
            # and must never create, migrate or write-lock the runtime database,
            # so it bootstraps only the immutable locator here.
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
                raise
        lease_mode = _runtime_lease_mode(arguments)
        if lease_mode is not None:
            runtime_lease = RuntimeDatabaseLease(configuration.database_path, lease_mode).acquire(
                create_parent=lease_mode is RuntimeLeaseMode.SHARED
            )
        if arguments.command == "config":
            bootstrap_document = _configuration_document(arguments.config)
            managed_config_command = arguments.config_command in {
                "status",
                "initialize",
                "publish",
                "retire-unpublished",
            }
            if managed_config_command:
                database_path = management_bootstrap_database_path
                if database_path is None:
                    raise RuntimeError("configuration management bootstrap locator is unavailable")
                if arguments.config_command == "status":
                    # A previous supported store is inspected through a read-only
                    # connection.  Status never applies the data switch; it lists
                    # the exact revisions, evidence and admitted Task pins.
                    evaluate_database_applicability(
                        read_database_markers(database_path),
                        current_runtime_version=SCHEMA_VERSION,
                        current_configuration_version=CONFIGURATION_SCHEMA_VERSION,
                    )
                    pending_switch = read_configuration_data_switch(database_path)
                    if pending_switch is not None:
                        stdout.write(
                            json.dumps(
                                _data_switch_status_document(pending_switch),
                                ensure_ascii=False,
                                indent=2,
                            )
                            + "\n"
                        )
                        return 0
                data_switch_command = arguments.config_command == "retire-unpublished"
                reviewed_switch = None
                if data_switch_command:
                    reviewed_switch = read_configuration_data_switch(database_path)
                    if reviewed_switch is not None and not arguments.confirm:
                        stdout.write(
                            json.dumps(
                                {
                                    "switched": False,
                                    "dataSwitch": reviewed_switch.document(),
                                    "nextAction": reviewed_switch.next_action(),
                                },
                                ensure_ascii=False,
                                indent=2,
                            )
                            + "\n"
                        )
                        raise ValueError(
                            "configuration data switch requires --confirm after "
                            "reviewing the affected revisions"
                        )
                    if reviewed_switch is not None and reviewed_switch.blocked:
                        stdout.write(
                            json.dumps(
                                {
                                    "switched": False,
                                    "dataSwitch": reviewed_switch.document(),
                                    "nextAction": reviewed_switch.next_action(),
                                },
                                ensure_ascii=False,
                                indent=2,
                            )
                            + "\n"
                        )
                        raise ValueError(reviewed_switch.next_action())
                try:
                    repository = SQLiteConfigurationRepository(
                        database_path,
                        apply_data_switch=data_switch_command and arguments.confirm,
                    )
                except sqlite3.Error as error:
                    if not data_switch_command:
                        raise
                    raise RuntimeError(
                        "configuration data switch failed and was rolled back "
                        f"({type(error).__name__}: {error}); the previous store "
                        "was preserved. Correct the reported database fault, then "
                        "run `mediaflow config status` again"
                    ) from error
                with repository:
                    service = ManagedConfigurationService(
                        repository,
                        bootstrap_database_path=database_path,
                        bootstrap_document=bootstrap_document,
                        management_only=is_minimal_management_bootstrap(bootstrap_document),
                    )
                    if arguments.config_command == "status":
                        stdout.write(
                            json.dumps(service.status_document(), ensure_ascii=False, indent=2)
                            + "\n"
                        )
                        return 0
                    if data_switch_command:
                        active = repository.get_active_revision()
                        remaining = [
                            revision
                            for revision in repository.list_revisions(limit=500)
                            if revision.status
                            in {
                                ManagedConfigurationStatus.DRAFT,
                                ManagedConfigurationStatus.VALIDATED,
                            }
                        ]
                        if remaining:
                            raise RuntimeError(
                                "the data switch left unpublished configuration "
                                "revisions behind: "
                                + ", ".join(item.revision_id for item in remaining)
                            )
                        actual_schema_version = read_database_markers(
                            database_path
                        ).configuration_version
                        if actual_schema_version != CONFIGURATION_SCHEMA_VERSION:
                            raise RuntimeError(
                                "the configuration store did not report the current "
                                "schema after the data switch"
                            )
                        stdout.write(
                            json.dumps(
                                {
                                    "switched": reviewed_switch is not None,
                                    "configurationSchemaVersion": actual_schema_version,
                                    "removedRevisions": [
                                        {"revisionId": revision_id, "status": status}
                                        for revision_id, status in (
                                            repository.data_switch_removed_revisions
                                        )
                                    ],
                                    "removedEvidence": [
                                        {"table": table, "rows": rows}
                                        for table, rows in (repository.data_switch_removed_evidence)
                                    ],
                                    "removedAuditRows": (repository.data_switch_removed_audit_rows),
                                    "active": active.summary() if active is not None else None,
                                    "remainingRevisionCount": len(
                                        repository.list_revisions(limit=500)
                                    ),
                                    "nextAction": (
                                        "start or restart MediaFlow services so they "
                                        "open the switched configuration store"
                                        if reviewed_switch is not None
                                        else "no configuration data switch was pending"
                                    ),
                                },
                                ensure_ascii=False,
                                indent=2,
                            )
                            + "\n"
                        )
                        return 0
                    objects = ConfigurationObjectService(service)
                    if arguments.config_command == "initialize":
                        if service.status_document().get("managedActivation") is True:
                            raise ValueError(
                                "managed configuration already exists; initialize is closed"
                            )
                        from mediaflow.application.configuration_snapshot import (
                            build_first_setup_starter_document,
                        )
                        from mediaflow.infrastructure.runtime_configuration import (
                            load_minimal_management_bootstrap,
                        )

                        document = build_first_setup_starter_document(
                            load_minimal_management_bootstrap(bootstrap_document)
                        )
                        revision = objects.publish_document(document, actor=arguments.actor)
                        stdout.write(
                            json.dumps(
                                {**revision.summary(), "initialized": True},
                                ensure_ascii=False,
                                indent=2,
                            )
                            + "\n"
                        )
                        return 0
                    if arguments.config_command == "publish":
                        if arguments.replace_active and not arguments.file:
                            raise ValueError(
                                "--replace-active requires --file with the complete "
                                "replacement document"
                            )
                        try:
                            active = service.active()
                        except RuntimeSnapshotUnavailable:
                            if not arguments.replace_active:
                                raise
                            active = None
                        if arguments.file:
                            document = json.loads(Path(arguments.file).read_text(encoding="utf-8"))
                        else:
                            if active is None:
                                raise ValueError(
                                    "no Active configuration exists; use `config initialize` "
                                    "or supply --file"
                                )
                            document = service.current_document(bootstrap_document)
                        revision = objects.publish_document(
                            document,
                            actor=arguments.actor,
                            expected_active_revision_id=(
                                active.revision_id if active is not None else None
                            ),
                            expected_active_version=(
                                (active.revision_sequence or active.version)
                                if active is not None
                                else None
                            ),
                            expected_active_digest=(active.digest if active is not None else None),
                            replace_active=arguments.replace_active,
                        )
                        stdout.write(
                            json.dumps(
                                {**revision.summary(), "published": True},
                                ensure_ascii=False,
                                indent=2,
                            )
                            + "\n"
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
            "ignore-item",
            "ignore-pending",
            "cancel",
        }:
            with ExitStack() as stack:
                repository = stack.enter_context(SQLiteTaskRepository(configuration.database_path))
                _attach_task_terminal_notifications(repository, arguments.config)
                recovery_admission = None
                if arguments.task_command in {"ignore-item", "ignore-pending"}:
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
                elif arguments.task_command == "cancel":
                    from mediaflow.application.operations_lifecycle import (
                        TaskLifecycleService,
                    )

                    task = repository.get_task(arguments.task_id)
                    if task is None:
                        raise LookupError(f"task {arguments.task_id!r} was not found")
                    cancelled = TaskLifecycleService(repository).cancel(
                        task.task_id,
                        expected_version=task.updated_at.isoformat(),
                    )
                    stdout.write(
                        f"Task ID: {cancelled.task_id}\nStatus: {cancelled.status.value}\n"
                    )
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
        if arguments.command == "files":
            # ``files list`` reads one exact Active library directory through the
            # same application browser the Web Files and MediaLibrary pages use.
            # It is strictly read-only: it opens no Task/Result repository, creates
            # or upgrades no database, records no directory entry and grants no
            # execution authority.
            if arguments.file_command != "list":
                raise ValueError(
                    f"unsupported files command {arguments.file_command!r}; "
                    "use 'files list' to read one live library directory"
                )
            stdout.write(_render_live_library_directory(configuration, arguments))
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
        storages = configuration.create_storages()
        library = display_root = None
        if getattr(arguments, "path", None):
            library, display_root = _resource_library(configuration, arguments.path)
        providers = None
        if not (arguments.command == "analyze" and arguments.offline):
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
        with SQLiteTaskRepository(configuration.database_path) as repository:
            _attach_task_terminal_notifications(repository, arguments.config)
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
            kernel_context = None
            # The independent ``tasks retry-failed`` entrance was retired (Slice
            # 47 RO-6): new organizing starts from Files/``organize`` and an
            # existing Task's own four-type continuation.  What remains here is
            # the ordinary direct organize workflow (analysis by default, an
            # explicitly authorized kernel execution with ``--execute``).
            execute = arguments.command == "organize" and arguments.execute
            if execute:
                # RO-2: a direct CLI organize execution is the same shared
                # Task work every other entrance runs.  The Task is admitted
                # through the scheduling kernel — capacity, pin, claim fence
                # and results included — and this process drives its own
                # execution under the live claim instead of a parallel
                # generic executor.
                task, scheduling = _admit_direct_organize_task(
                    repository,
                    configuration,
                    path=arguments.path,
                    limit=arguments.limit,
                )
                claim, direct_organize_worker_id = _drive_direct_organize_claim(
                    repository, scheduling, task
                )
                kernel_context = (scheduling, claim)
                coordinator = KernelTaskCoordinator(
                    repository,
                    repository,
                    scheduling,
                    claim,
                    heartbeat=lambda: (
                        scheduling.heartbeat(
                            claim,
                            now=datetime.now(UTC),
                            lease_seconds=900.0,
                        )
                        is not None
                    ),
                )
            else:
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
            if _task_observer is not None:
                # The durable Task identity is handed to the application caller
                # structurally.  Rendered CLI text remains the operator output
                # and is never parsed back into an identity.
                _task_observer(task.task_id)

            def workflow_stop() -> bool:
                return bool(
                    (cancellation_check and cancellation_check())
                    or coordinator.cancellation_observed(task.task_id)
                )

            # Not executing is the shared zero-mutation analysis: it records the
            # complete plan, attachments, conflicts and unready findings without
            # creating a formal execution backlog (WAITING_CONFIRM, review or
            # ConflictConfirmation) and without any execution authority.  A real
            # execute/recovery run keeps its original blocker responsibilities.
            analysis_only = not execute
            service = MediaOrganizerService(
                strategy,
                StorageScanner(storages, logger=operational_logger),
                storages,
                {item.library_id: item for item in configuration.media_libraries},
                configuration.strategy.recognition_type_policies,
                JsonLinesOperationHistoryRepository(configuration.history_path),
                executor=OrganizerExecutor(operational_logger),
                source_display_roots=dict(configuration.resource_display_roots),
                logger=operational_logger,
                task_coordinator=coordinator,
                task_id=task.task_id,
                conflict_decisions={},
                metadata_selections={},
                metadata_corrections={},
                classification_selections={},
                recognition_selections={},
                retry_policy=configuration.workflow_retry_policy,
                retry_cancellation_check=workflow_stop,
                analysis_only=analysis_only,
                # B46.3-05: only a run that may really consume a source asks the
                # shared durable ownership boundary.  A zero-mutation analysis
                # (``execute`` false) creates no organizing work, gains no
                # execution authority and mutates nothing, so it must stay
                # readable even while another work owns the file.
                enforce_source_ownership=execute,
            )
            # The CLI's own source scope must be read completely before any
            # file is processed: a root or subtree that cannot be enumerated
            # makes the admitted scope unproved, so the run settles as a Task
            # flow failure instead of executing a readable prefix or reporting
            # a healthy empty completion.  An explicit --limit keeps its
            # existing subset semantics; only unreadable/overflowed discovery
            # is a scope failure here.
            scope_failure = None
            try:
                if arguments.path is None:
                    summary = service.process_all_libraries(
                        configuration.resource_libraries,
                        execute=execute,
                        limit=arguments.limit,
                        progress=lambda done, total, source: stdout.write(
                            f"PROGRESS {done}/{total or '?'} {source}\n"
                        ),
                        cancellation_check=workflow_stop,
                        require_readable_scope=True,
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
                            require_readable_scope=True,
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
            except IncompleteOrganizingScope as error:
                scope_failure = error
                summary = MediaOrganizerBatchResult((), error.errors, False)
            cancelled = bool(cancellation_check and cancellation_check())
            if kernel_context is not None:
                scheduling, claim = kernel_context
                state = scheduling.state(task.task_id)
                if cancelled and (state is None or state.control_request is None):
                    scheduling.request_control(task.task_id, TaskControl.CANCEL)
                    state = scheduling.state(task.task_id)
                if state is not None and state.control_request is not None:
                    # The operator's accepted control owns the outcome at this
                    # safe boundary: finished items keep their recorded results,
                    # the unfinished tail settles with the control.  This CLI
                    # pass has returned, so a recorded unknown outcome is
                    # history rather than a call still in flight; the shared
                    # kernel still refuses a missing Result or machine sibling.
                    scheduling.acknowledge_control(
                        claim,
                        now=datetime.now(UTC),
                        close_recorded_unknown_boundary=True,
                    )
                else:
                    _settle_direct_organize(
                        repository,
                        scheduling,
                        claim,
                        task,
                        batch=summary,
                        scope_failure=scope_failure,
                    )
            elif cancelled:
                coordinator.cancel(task.task_id)
            elif coordinator.cancellation_observed(task.task_id):
                # A durable cooperative cancellation already owns this Task
                # outcome; a late finish must not overwrite it.
                pass
            else:
                coordinator.finish(task.task_id, summary)
            stdout.write(f"Task ID: {task.task_id}\n")
            stdout.write(render_summary(summary, execute=execute, analysis_only=analysis_only))
            return 130 if cancelled else 1 if summary.failed else 0
    except (OSError, ValueError, LookupError, RuntimeError) as error:
        stderr.write(f"mediaflow error: {error}\n")
        return 2
    finally:
        if direct_organize_worker_id is not None:
            # The synchronous CLI only borrowed a transient Worker identity to
            # own its claimed Task.  Settle it with the run so no live temporary
            # Worker record survives a success or a bounded failure.
            try:
                with SQLiteTaskRepository(configuration.database_path) as cleanup_repository:
                    cleanup_repository.stop_worker(direct_organize_worker_id, datetime.now(UTC))
            except Exception:  # noqa: BLE001 - cleanup never masks the run's real result
                pass
        if runtime_lease is not None:
            runtime_lease.close()


def _runtime_lease_mode(arguments: argparse.Namespace) -> RuntimeLeaseMode | None:
    if arguments.command in {"config", "storage"}:
        return None
    return RuntimeLeaseMode.SHARED


def render_summary(
    summary: MediaOrganizerBatchResult, *, execute: bool, analysis_only: bool = False
) -> str:
    lines = ["", "SUMMARY", "", f"Mode: {'EXECUTE' if execute else 'DRY_RUN'}"]
    for item in summary.items:
        if item.execution is not None:
            status = item.execution.status.value
        elif item.error:
            status = "FAILED"
        elif analysis_only:
            # The analysis ran to completion and recorded its finding: no
            # operator confirmation item exists for it, so the summary must not
            # claim NEED_CONFIRM/SKIPPED.
            status = "ANALYSIS"
        elif item.plan and item.plan.conflicts:
            status = "NEED_CONFIRM"
        else:
            status = "SKIPPED"
        details = []
        if item.plan and item.plan.attachment_plans:
            details.append(f"attachments={len(item.plan.attachment_plans)}")
        if item.plan and item.plan.conflicts:
            details.append(
                "findings=" + ",".join(sorted({value.type.value for value in item.plan.conflicts}))
            )
        if analysis_only and item.evidence is not None:
            details.append(f"outcome={item.evidence.outcome}")
            plan_section = item.evidence.section("plan")
            if plan_section.available and isinstance(plan_section.value, dict):
                next_action = plan_section.value.get("nextAction")
                if isinstance(next_action, str) and next_action:
                    details.append(f"next={next_action}")
            elif plan_section.unavailable_reason:
                details.append(f"next={plan_section.unavailable_reason}")
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


def render_tasks(tasks: tuple[PersistentTask, ...]) -> str:
    lines = ["", "TASKS", ""]
    for task in tasks:
        lines.append(
            f"{task.task_id} | {task.command} | {task.status.value} | "
            f"total={task.total_items} completed={task.completed_items} "
            f"failed={task.failed_items} | "
            f"snapshot={task.configuration_snapshot_id or '-'}"
        )
    lines.extend(("", f"Total: {len(tasks)}", ""))
    return "\n".join(lines)


def _active_runtime_for_browsing(active, database_path: str):
    """Resolve the exact Active revision into a runtime configuration for browsing.

    Only configuration is resolved: no Storage adapter is constructed here, and
    the database locator comes from the immutable bootstrap document, so this can
    never upgrade or create the store it just read.
    """

    runtime = load_managed_runtime_configuration(
        active.document, bootstrap_database_path=database_path
    )
    return with_managed_snapshot(
        runtime,
        snapshot_id=active.revision_id,
        digest=active.digest,
        version=active.revision_sequence,
    )


def _live_list_limit(value: object) -> int:
    if value is None:
        return 100
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 100:
        raise ValueError("files list --limit must be between 1 and 100")
    return value


def render_live_library_directory(document) -> str:
    """Render one bounded live library directory listing."""

    library_kind = str(document.get("libraryKind"))
    library_label = "ResourceLibrary" if library_kind == "resourceLibrary" else "MediaLibrary"
    library = document.get(
        "resourceLibrary" if library_kind == "resourceLibrary" else "mediaLibrary"
    )
    library = library if isinstance(library, dict) else {}
    entries = document.get("entries") or ()
    lines = [
        "",
        "LIVE DIRECTORY",
        "",
        f"Library kind: {library_label}",
        f"Library: {library.get('name') or '-'} ({library.get('id') or '-'})",
        f"Storage: {document.get('storageName') or '-'} ({document.get('storageId') or '-'})",
        f"Directory: {document.get('path') or '/'}",
        f"Revision: {document.get('revisionId') or '-'}",
        "",
        "NAME | TYPE | SIZE | MODIFIED",
        "",
    ]
    for entry in entries:
        lines.append(
            f"{entry.get('name')} | {entry.get('type')} | {entry.get('size')} | "
            f"{entry.get('modifiedAt')}"
        )
    if not entries:
        lines.append("None")
    lines.extend(
        (
            "",
            f"Returned: {len(entries)}",
            f"Limit: {document.get('limit')}",
            f"More available: {'yes' if document.get('hasNext') else 'no'}",
            f"Next cursor: {document.get('nextCursor') or '-'}",
            "Total: unknown (only the requested directory is read)",
            f"Side effects: {document.get('sideEffects', 'none')}",
            "",
        )
    )
    return "\n".join(lines)


def _render_live_library_directory(configuration, arguments) -> str:
    """Read one live library directory and render it for the operator.

    This is the CLI twin of the Web Files/MediaLibrary pages: it resolves the
    exact Active revision, binds the requested library and Storage, and lists the
    requested directory through the shared application browser.  It records
    nothing, creates no database, calls no Provider and mutates no media.
    """

    try:
        document = _live_library_directory_document(configuration, arguments)
    except StorageBrowserError as error:
        return "\n".join(
            (
                "",
                "LIVE DIRECTORY",
                "",
                f"Status: {error.code}",
                f"Reason: {error.message}",
                f"Durable state: {error.durable_state}",
                f"Side effects: {error.details['sideEffects']}",
                f"Repeatable: {'yes' if error.retry_safe else 'no'}",
                f"Next action: {error.next_action}",
                "",
            )
        )
    return render_live_library_directory(document)


def _live_library_directory_document(configuration, arguments) -> dict[str, object]:
    from mediaflow.application.storage_browser import RuntimeFilesBrowserService
    from mediaflow.domain.configuration_management import (
        STORAGE_BROWSER_CURSOR_KEY_NAME,
    )
    from mediaflow.infrastructure.internal_key_store import (
        InternalKeyUnavailable,
        read_internal_key_read_only,
    )
    from mediaflow.infrastructure.read_only_active_configuration import (
        ReadOnlyActiveRevisionSource,
        active_revision_failure_document,
        read_active_revision_read_only,
    )

    bootstrap_document = _configuration_document(arguments.config)
    database_path = _bootstrap_database_path(bootstrap_document)
    try:
        active = read_active_revision_read_only(database_path)
    except RuntimeSnapshotUnavailable as error:
        raise StorageBrowserError(
            f"files_list_{getattr(error, 'reason', 'active_unavailable')}",
            getattr(error, "reason", "active_unavailable"),
            str(error),
            status=409,
            next_action=str(
                active_revision_failure_document(error).get(
                    "nextAction",
                    "complete first setup in the Web Settings page and activate a revision",
                )
            ),
            durable_state="no configuration was created, changed or upgraded",
        ) from error
    if active is None:
        raise StorageBrowserError(
            "files_list_no_active",
            "no_active",
            "no Active configuration revision is published yet",
            status=409,
            next_action="complete first setup in the Web Settings page and activate a revision",
            durable_state="no configuration was created, changed or upgraded",
        )
    # Cursor continuation must stay verifiable across CLI/API processes, so the
    # authentication key is the one persisted in the managed store.  Reading it
    # here stays strictly read-only: a store that has not been initialized with
    # the key is refused explicitly instead of minting a one-off process key.
    try:
        cursor_key = read_internal_key_read_only(database_path, STORAGE_BROWSER_CURSOR_KEY_NAME)
    except InternalKeyUnavailable as error:
        raise StorageBrowserError(
            "files_list_internal_key_unavailable",
            getattr(error, "reason", "internal_key_unavailable"),
            str(error),
            status=409,
            next_action=(
                "complete supported initialization (for example the Web Settings or "
                "resident service startup) so the internal cursor key exists, then retry"
            ),
            durable_state="no configuration was created, changed or upgraded",
        ) from error
    if cursor_key is None:
        raise StorageBrowserError(
            "files_list_internal_key_unavailable",
            "internal_key_unavailable",
            "the internal cursor-authentication key has not been initialized in this store",
            status=409,
            next_action=(
                "complete supported initialization (for example the Web Settings or "
                "resident service startup) so the internal cursor key exists, then retry"
            ),
            durable_state="no configuration was created, changed or upgraded",
        )
    browser = RuntimeFilesBrowserService(
        ReadOnlyActiveRevisionSource(active),
        active_revision=active,
        runtime_configuration=_active_runtime_for_browsing(active, database_path),
        cursor_secret=cursor_key,
    )
    limit = _live_list_limit(arguments.limit)
    if arguments.resource_library is not None:
        document = browser.browse_resource_library(
            resource_library_id=arguments.resource_library,
            path=arguments.path,
            limit=limit,
            cursor=arguments.cursor,
        )
        document["libraryKind"] = "resourceLibrary"
    else:
        document = browser.browse_media_library(
            media_library_id=arguments.media_library,
            path=arguments.path,
            limit=limit,
            cursor=arguments.cursor,
        )
        document["libraryKind"] = "mediaLibrary"
    return document


def render_task(task: PersistentTask, items: tuple[PersistentTaskItem, ...]) -> str:
    lines = [
        "",
        "TASK",
        "",
        f"ID: {task.task_id}",
        f"Command: {task.command}",
        f"Status: {task.status.value}",
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
        # A persisted bounded failure is stored as a versioned envelope.  Decode
        # it so the operator reads the category, reason and next action instead
        # of an opaque token.
        explanation = decode_failure_explanation(item.error)
        if explanation is not None:
            detail = (
                f"{explanation.category}: {explanation.message} | Next: {explanation.next_action}"
            )
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
            item for item in (value.task_id, value.plan_id, value.status) if item is not None
        )
        lines.append(
            f"{value.occurred_at.isoformat()} | {value.level.name} | {value.component} | "
            f"{value.event} | {identifiers or '-'}"
        )
    lines.extend(("", f"Total: {len(values)}", ""))
    return "\n".join(lines)


def render_notification(value) -> str:
    return render_notifications((value,))


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


def _admit_direct_organize_task(repository, configuration, *, path, limit):
    """Admit one direct CLI organize execution through the shared Task kernel.

    The admitted Task — not a parallel generic coordinator row — is the durable
    subject of the run: the same shared capacity, pin, claim fence and results
    every other organizing entrance uses.  Admission is atomic and
    capacity-checked; a full queue refuses the run before any work starts
    instead of queueing it invisibly.
    """

    from mediaflow.application.task_scheduling import (
        TaskSchedulingService,
        build_scheduled_task_admission,
    )
    from mediaflow.domain.task_persistence import RunDisplayContext
    from mediaflow.domain.task_scheduling import TaskQueueFull, TaskTrigger

    scheduling = TaskSchedulingService(
        repository,
        capacity=getattr(configuration, "automation_maximum_active_jobs", 100),
        locks=repository,
    )
    task, state = build_scheduled_task_admission(
        "organize",
        execute_authorized=True,
        trigger=TaskTrigger.MANUAL,
        principal="cli",
        scope_path=path,
        item_limit=limit,
        configuration_snapshot_id=configuration.configuration_snapshot_id,
        configuration_snapshot_digest=configuration.configuration_snapshot_digest,
        require_configuration_snapshot=(configuration.configuration_authority == "MANAGED"),
        now=datetime.now(UTC),
    )
    display = RunDisplayContext(
        source_scope=path,
        origin_kind="direct-organize",
    )
    try:
        admitted = repository.admit_scheduled_task(
            task,
            state,
            capacity=scheduling.capacity,
            display=display,
        )
    except TaskQueueFull as error:
        raise ValueError(
            "the shared organizing queue is full; no organize run was started"
        ) from error
    if admitted.duplicate:
        task, state = admitted.task, admitted.state
    return task, scheduling


def _drive_direct_organize_claim(
    repository, scheduling, task, *, lease_seconds=900.0, commands=("organize",)
):
    """Claim the admitted direct organize Task for this process' own execution.

    The claim is the same kernel boundary a resident Worker holds, so the
    synchronous CLI run publishes every item and Result under the live fence
    and can never write over a successor.  A bounded transient Worker
    registration carries the claim eligibility; it is stopped with the Task's
    own settlement.
    """

    from mediaflow.domain.task_scheduling import TaskWorkerRejected
    from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION

    worker_id = f"direct-organize-{uuid4().hex[:12]}"
    repository.register_worker(
        worker_id,
        worker_id,
        lease_seconds,
        commands,
        None,
        None,
        SCHEMA_VERSION,
        datetime.now(UTC),
    )
    try:
        claim = scheduling.claim(
            task.task_id,
            worker_id=worker_id,
            now=datetime.now(UTC),
            lease_seconds=lease_seconds,
        )
    except BaseException:
        _stop_direct_organize_worker(repository, worker_id)
        raise
    if claim is None:
        _stop_direct_organize_worker(repository, worker_id)
        state = scheduling.state(task.task_id)
        owner = getattr(state, "claim_worker_id", None)
        if isinstance(owner, str) and owner and owner != worker_id:
            raise TaskWorkerRejected(
                f"the admitted organize Task {task.task_id} is already owned by Worker "
                f"{owner!r}; this process did not take or duplicate that work — inspect the "
                "Task's shared execution and result instead"
            )
        raise TaskWorkerRejected(
            f"the admitted organize Task {task.task_id} is not claimable in this run; "
            "inspect its queue state and pinned configuration"
        )
    try:
        claim = scheduling.begin_work(claim, now=datetime.now(UTC))
    except BaseException:
        # The claim is ours but the running boundary could not be published
        # (for example an already accepted control).  Settle that existing
        # control, or hand the claim back without changing operator intent;
        # never leave an owner that never runs.
        try:
            state = scheduling.state(task.task_id)
            if state is not None and state.control_request is not None:
                scheduling.acknowledge_control(claim, now=datetime.now(UTC))
            else:
                from mediaflow.domain.task_scheduling import TaskMachineStage

                scheduling.yield_claim(
                    claim,
                    task=claim.task,
                    stage=TaskMachineStage.DISCOVERY,
                    now=datetime.now(UTC),
                )
        except Exception:  # noqa: BLE001 - preserve the original failure
            pass
        _stop_direct_organize_worker(repository, worker_id)
        raise
    return claim, worker_id


def _stop_direct_organize_worker(repository, worker_id: str) -> None:
    """Best-effort cleanup of the CLI's transient Worker registration."""

    try:
        repository.stop_worker(worker_id, datetime.now(UTC))
    except Exception:  # noqa: BLE001 - cleanup never masks the run's real result
        pass


def _settle_direct_organize(repository, scheduling, claim, task, *, batch, scope_failure):
    """Settle one directly driven organize Task under its live claim.

    The flow outcome is the shared settlement rule over the facts this pass
    actually observed: the pass returned, a discovery failure may have left the
    admitted scope unproved, and durable items may still be waiting for the
    operator or real machine work.  File outcomes never become the flow status.
    An unproved source scope is a bounded Task flow failure — never a healthy
    empty completion — while a source still waiting for the operator returns the
    Task to human waiting with zero slots.
    """

    from mediaflow.domain.task_scheduling import TaskMachineStage

    now = datetime.now(UTC)
    items = repository.list_items(task.task_id)
    total, completed, failed = task_item_counts(items)
    waiting_statuses = {
        TaskItemStatus.WAITING_CONFIRM,
        TaskItemStatus.WAITING_RECOGNITION,
        TaskItemStatus.WAITING_METADATA,
        TaskItemStatus.WAITING_METADATA_CORRECTION,
        TaskItemStatus.WAITING_CLASSIFICATION,
    }
    waiting = tuple(item for item in items if item.status in waiting_statuses)
    machine = tuple(
        item
        for item in items
        if item.status not in SETTLED_ITEM_STATUSES and item.status not in waiting_statuses
    )
    failure = scope_failure.explanation() if scope_failure is not None else None
    if failure is None and batch.scan_errors:
        failure = incomplete_scope_failure(errors=batch.scan_errors)
    decision = settle_task_flow(
        TaskFlowSettlementInputs(
            ended_this_round=True,
            machine_work_remaining=bool(machine),
            human_decision_pending=bool(waiting),
            live_local_call=False,
            scope_proven_complete=failure is None,
            orchestration_error=failure,
            acknowledged_cancellation=False,
        )
    )
    updated = replace(
        task,
        updated_at=now,
        total_items=total,
        completed_items=completed,
        failed_items=failed,
        error=failure.encode() if failure is not None else None,
    )
    if decision.status is PersistentTaskStatus.FAILED:
        # The pass never proved the admitted scope; no file was processed and
        # the reason is durable, bounded and secret-free.  Release the slot
        # under the live owner fence like every other terminal settlement.
        failed_task = replace(updated, status=PersistentTaskStatus.FAILED, completed_at=now)
        scheduling.settle(
            claim,
            task=failed_task,
            items=items,
            now=now,
            close_recorded_unknown_boundary=True,
        )
        return
    if machine:
        # A still-processing sibling is genuine machine work; keep the slot and
        # let the next claim finish it instead of settling under a terminal
        # outcome this run does not own.
        running = replace(updated, status=PersistentTaskStatus.RUNNING, completed_at=None)
        scheduling.publish_task(claim, running, now=now)
        scheduling.yield_claim(
            claim,
            task=running,
            stage=TaskMachineStage.EXECUTION,
            now=now,
        )
        return
    if waiting:
        scheduling.publish_task(claim, updated, now=now)
        # Every source of this direct pass already recorded its own outcome or
        # is waiting for the operator; the process is done making calls, so a
        # recorded unknown effect no longer holds the shared slot.
        scheduling.defer_to_human(
            claim,
            task=updated,
            items=(),
            now=now,
            close_recorded_unknown_boundary=True,
        )
        return
    settled = replace(
        updated,
        status=PersistentTaskStatus.COMPLETED,
        completed_at=now,
    )
    # The direct CLI pass has returned and every durable item is terminal.  A
    # recorded unknown effect remains factual history; releasing its slot does
    # not rewrite the Result, its completed steps or the source protection.
    scheduling.settle(
        claim,
        task=settled,
        items=items,
        now=now,
        close_recorded_unknown_boundary=True,
    )


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


def _safe_preflight_error(error: Exception) -> str:
    from mediaflow.domain.storage import StorageError

    if isinstance(error, StorageError):
        return f"{error.code.value}: {error}"
    if isinstance(error, (ValueError, RuntimeError, OSError)):
        return str(error)
    return type(error).__name__


def _data_switch_status_document(scope: ConfigurationDataSwitchScope) -> dict[str, object]:
    """Report a pending data switch without serving business configuration."""

    return {
        "authority": "MANAGEMENT_BOOTSTRAP",
        "health": "DATA_SWITCH_REQUIRED",
        "managementReady": False,
        "managedActivation": scope.managed_activation,
        "setupRequired": False,
        "runtimeConfigured": False,
        "runtimeReady": False,
        "recoveryRequired": scope.managed_activation,
        "active": None,
        "revisions": [],
        "dataSwitch": scope.document(),
        "nextAction": scope.next_action(),
    }


_HOST_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")


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
