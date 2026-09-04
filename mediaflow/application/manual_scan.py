"""Application service for bounded, durable, discovery-only manual Scans."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime

from mediaflow.application.scanner import (
    ScanAlreadyRunningError,
    StorageScanner,
    normalize_resource_root,
)
from mediaflow.domain.file_lifecycle import OccurrenceState
from mediaflow.domain.library import ResourceLibrary, ScanMode
from mediaflow.domain.manual_safety import redact_manual_text
from mediaflow.domain.manual_scan import (
    ManualScanItemOutcome,
    ManualScanRequest,
    ManualScanScopeKind,
    ManualScanTask,
)
from mediaflow.domain.scanner import (
    CancellationToken,
    DiscoveredFile,
    FileChange,
    FileScanStatus,
    ScanResult,
    ScanStatistics,
)
from mediaflow.domain.storage import Storage, StorageEntryType, StorageError
from mediaflow.domain.task_persistence import (
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)


class ManualScanError(ValueError):
    """Fail-closed manual Scan admission or lifecycle error."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int = 409,
        durable_state: str = "unchanged",
        retry_safe: bool = True,
        next_action: str,
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.durable_state = durable_state
        self.retry_safe = retry_safe
        self.next_action = next_action
        self.details = dict(details or {})


class ManualScanService:
    """Admit and run one exact manual discovery scope.

    The service captures immutable runtime configuration at construction.  A new API runtime
    binding constructs a new service, while an already accepted Task continues to use the
    snapshot and library definitions that it persisted at admission.
    """

    MAX_PROGRESS_KEYS = 32
    MAX_ERRORS = 32

    def __init__(
        self,
        repository,
        file_index,
        *,
        resource_libraries: Sequence[ResourceLibrary] = (),
        storages: Mapping[str, Storage] | None = None,
        storage_factory: Callable[..., Mapping[str, Storage]] | None = None,
        runtime_configuration=None,
        configuration_snapshot_id: str | None = None,
        configuration_snapshot_digest: str | None = None,
        clock: Callable[[], datetime] | None = None,
        start_async: bool = True,
    ) -> None:
        if runtime_configuration is not None:
            resource_libraries = runtime_configuration.resource_libraries
            if storage_factory is None:
                storage_factory = runtime_configuration.create_storages
        self._repository = repository
        self._file_index = file_index
        self._resource_libraries = tuple(resource_libraries)
        self._storages = dict(storages or {})
        self._storage_factory = storage_factory
        self._configuration_snapshot_id = configuration_snapshot_id
        self._configuration_snapshot_digest = configuration_snapshot_digest
        self._clock = clock or (lambda: datetime.now(UTC))
        self._start_async = bool(start_async)
        self._lock = threading.RLock()
        self._threads: dict[str, threading.Thread] = {}
        self._tokens: dict[str, CancellationToken] = {}
        self._active_libraries: set[str] = set()

    def admit_document(
        self, document: Mapping[str, object], *, actor: str = "operator", start: bool | None = None
    ) -> ManualScanTask:
        if not isinstance(document, Mapping):
            raise ManualScanError(
                "invalid_request",
                "manual Scan request must be an object",
                status=400,
                next_action="submit one bounded Scan scope and an explicit mode",
            )
        allowed = {
            "scope",
            "scopeKind",
            "resourceLibraryId",
            "fileId",
            "occurrenceId",
            "sourceOccurrenceId",
            "fingerprint",
            "sourceFingerprint",
            "mode",
        }
        if set(document).difference(allowed):
            raise ManualScanError(
                "invalid_request",
                "manual Scan accepts only bounded scope identity and mode",
                status=400,
                next_action="remove path, operation, Provider, and execution fields",
            )
        raw_kind = document.get("scopeKind", document.get("scope"))
        if document.get("scopeKind") is not None and document.get("scope") is not None:
            if document["scopeKind"] != document["scope"]:
                raise ManualScanError(
                    "invalid_scope",
                    "manual Scan scope fields disagree",
                    status=400,
                    next_action="send exactly one scope kind",
                )
        if raw_kind == "resourceLibrary":
            raw_kind = ManualScanScopeKind.RESOURCE_LIBRARY.value
        try:
            kind = ManualScanScopeKind(raw_kind)
            mode = ScanMode(document.get("mode"))
            resource_library_id = document.get("resourceLibraryId")
            file_id = document.get("fileId")
            occurrence_id = self._same_alias(
                document, "occurrenceId", "sourceOccurrenceId", "source occurrence ID"
            )
            fingerprint = self._same_alias(
                document, "fingerprint", "sourceFingerprint", "source fingerprint"
            )
            request = ManualScanRequest(
                kind,
                resource_library_id,
                mode,
                file_id=file_id,
                source_occurrence_id=occurrence_id,
                source_fingerprint=fingerprint,
            )
        except (TypeError, ValueError) as error:
            raise ManualScanError(
                "invalid_request",
                redact_manual_text(error),
                status=400,
                next_action=(
                    "submit one configured ResourceLibrary or exact current FileIndex scope"
                ),
            ) from error
        return self.admit(request, actor=actor, start=start)

    def admit(
        self,
        request: ManualScanRequest,
        *,
        actor: str = "operator",
        start: bool | None = None,
    ) -> ManualScanTask:
        del actor  # The API audit records the actor; the Task stores no secret-bearing identity.
        if not self._configuration_snapshot_id or not self._configuration_snapshot_digest:
            raise ManualScanError(
                "configuration_unavailable",
                "the exact Active runtime binding is unavailable",
                status=503,
                durable_state="no_task_created",
                next_action="restore or activate a valid Active runtime, then retry",
            )
        library = self._require_library(request.resource_library_id)
        storage = self._preflight_storage(library)
        record = None
        if request.scope_kind is ManualScanScopeKind.FILE:
            record = self._require_current_file(request)
            if record.storage_id != storage.storage_id:
                raise ManualScanError(
                    "source_scope_mismatch",
                    "current FileIndex source does not belong to the configured Storage",
                    status=409,
                    durable_state="no_task_created",
                    next_action="refresh FileIndex and select the current source occurrence",
                )
        now = self._clock()
        task_id = uuid.uuid4().hex
        task = PersistentTask(
            task_id=task_id,
            command="scan",
            status=PersistentTaskStatus.RUNNING,
            execute_authorized=False,
            created_at=now,
            updated_at=now,
            started_at=now,
            total_items=1 if record is not None else 0,
            configuration_snapshot_id=self._configuration_snapshot_id,
            configuration_snapshot_digest=self._configuration_snapshot_digest,
        )
        scan = ManualScanTask(
            task_id=task_id,
            scope_kind=request.scope_kind,
            resource_library_id=request.resource_library_id,
            mode=request.mode,
            status=PersistentTaskStatus.RUNNING,
            configuration_snapshot_id=self._configuration_snapshot_id,
            configuration_snapshot_digest=self._configuration_snapshot_digest,
            created_at=now,
            updated_at=now,
            file_id=request.file_id,
            source_occurrence_id=request.source_occurrence_id,
            source_fingerprint=request.source_fingerprint,
            storage_id=storage.storage_id,
            source_path=record.path if record is not None else None,
            progress={"directoriesVisited": 0, "filesVisited": 0, "errors": 0},
            next_action="inspect the persisted Scan Task while discovery is running",
        )
        creator = getattr(self._repository, "create_manual_scan", None)
        if not callable(creator):
            raise ManualScanError(
                "persistence_unavailable",
                "durable manual Scan persistence is unavailable",
                status=503,
                durable_state="no_task_created",
                next_action="restore the runtime Task repository, then retry",
            )
        creator(task, scan)
        if record is not None:
            self._upsert_initial_file_item(scan, record, now)
        should_start = self._start_async if start is None else bool(start)
        if should_start:
            self._start(task_id)
        return scan

    def run(self, task_id: str) -> ManualScanTask:
        scan = self._require_task(task_id)
        task = self._repository.get_task(task_id)
        if task is None:
            raise ManualScanError(
                "task_not_found",
                "manual Scan Task was not found",
                status=404,
                next_action="open the persisted Tasks view and select an existing Scan Task",
            )
        if scan.status not in {PersistentTaskStatus.PENDING, PersistentTaskStatus.RUNNING}:
            return scan
        if (
            scan.configuration_snapshot_id != self._configuration_snapshot_id
            or scan.configuration_snapshot_digest != self._configuration_snapshot_digest
        ):
            return self._finish_error(
                scan,
                task,
                code="configuration_snapshot_mismatch",
                stage="configuration",
                message="manual Scan is pinned to a different Active runtime snapshot",
                next_action=(
                    "restore the pinned Active snapshot or admit a new bounded Scan from the "
                    "current Active runtime"
                ),
            )
        with self._lock:
            token = self._tokens.setdefault(task_id, CancellationToken())
        if scan.cancellation_requested:
            token.cancel()
        library_acquired = False
        try:
            library = self._require_library(scan.resource_library_id)
            self._acquire_library(library.library_id)
            library_acquired = True
            storages = self._storage_map({library.storage_id})
            scanner = StorageScanner(storages, self._file_index, clock=self._clock)
            self._update_progress(task_id, scan.progress, task)

            def on_progress(statistics: ScanStatistics) -> None:
                progress = self._progress_document(statistics)
                self._update_progress(task_id, progress, task)

            def on_discovered(discovered: DiscoveredFile) -> None:
                self._record_discovered(scan, discovered)

            if scan.scope_kind is ManualScanScopeKind.FILE:
                result = scanner.scan_file(
                    library,
                    scan.source_path or "",
                    mode=scan.mode,
                    expected_occurrence_id=scan.source_occurrence_id,
                    expected_fingerprint=scan.source_fingerprint,
                    cancellation=token,
                    on_progress=on_progress,
                    on_discovered=on_discovered,
                )
            else:
                result = scanner.scan(
                    library,
                    mode=scan.mode,
                    cancellation=token,
                    on_progress=on_progress,
                    on_discovered=on_discovered,
                )
            return self._finish(scan, task, result)
        except ScanAlreadyRunningError as error:
            return self._finish_error(
                scan,
                task,
                code="scan_already_running",
                stage="concurrency",
                message=redact_manual_text(error),
                next_action=(
                    "wait for the existing Scan to finish, then repeat the same bounded Scan"
                ),
            )
        except (StorageError, ValueError, OSError) as error:
            return self._finish_error(
                scan,
                task,
                code="scan_unavailable",
                stage="discovery",
                message=redact_manual_text(error),
                next_action=(
                    "inspect the Storage condition and persisted outcomes, then repeat the same "
                    "bounded Scan"
                ),
            )
        except Exception:
            return self._finish_error(
                scan,
                task,
                code="scan_failed",
                stage="discovery",
                message="manual Scan failed (details redacted)",
                next_action=(
                    "inspect the persisted Task and per-item outcomes, then repeat the same "
                    "bounded Scan"
                ),
            )
        finally:
            if library_acquired:
                self._release_library(scan.resource_library_id)
            with self._lock:
                self._tokens.pop(task_id, None)
                self._threads.pop(task_id, None)

    def cancel(self, task_id: str) -> ManualScanTask:
        scan = self._require_task(task_id)
        requester = getattr(self._repository, "request_manual_scan_cancellation", None)
        if not callable(requester):
            raise ManualScanError(
                "persistence_unavailable",
                "manual Scan cancellation persistence is unavailable",
                status=503,
                next_action="restore the runtime Task repository, then retry cancellation",
            )
        try:
            scan = requester(task_id, self._clock())
        except ValueError as error:
            raise ManualScanError(
                "cancellation_unavailable",
                redact_manual_text(error),
                status=409,
                next_action="inspect the terminal Task outcome and repeat only if needed",
            ) from error
        with self._lock:
            token = self._tokens.get(task_id)
            active = task_id in self._threads or token is not None
        if token is not None:
            token.cancel()
        if not active:
            task = self._repository.get_task(task_id)
            if task is not None and task.status in {
                PersistentTaskStatus.PENDING,
                PersistentTaskStatus.RUNNING,
            }:
                now = self._clock()
                scan = replace(
                    scan,
                    status=PersistentTaskStatus.CANCELLED,
                    cancellation_requested=True,
                    updated_at=now,
                    reconciliation_complete=False,
                    known_effects="no_media_mutation",
                    next_action=(
                        "inspect persisted item outcomes, then repeat the same bounded Scan"
                    ),
                )
                task = replace(
                    task,
                    status=PersistentTaskStatus.CANCELLED,
                    updated_at=now,
                    completed_at=now,
                    error="manual Scan cancelled",
                )
                return self._finalize(task, scan)
        scan = replace(
            scan,
            updated_at=self._clock(),
            next_action="wait for bounded cancellation, then inspect persisted item outcomes",
        )
        updater = getattr(self._repository, "update_manual_scan", None)
        if callable(updater):
            updater(scan)
        return self._require_task(task_id)

    def detail(self, task_id: str) -> ManualScanTask:
        return self._require_task(task_id)

    def detail_document(
        self,
        task_id: str,
        *,
        limit: int = 100,
        after=None,
        before=None,
    ) -> dict[str, object]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ManualScanError(
                "invalid_request",
                "manual Scan item limit must be between 1 and 100",
                status=400,
                next_action="request at most 100 per-item discovery outcomes",
            )
        scan = self._require_task(task_id)
        base = self._repository.get_task(task_id)
        if base is None:
            raise ManualScanError(
                "task_not_found",
                "manual Scan Task was not found",
                status=404,
                next_action="open the persisted Tasks view and select an existing Scan Task",
            )
        lister = getattr(self._repository, "list_manual_scan_items", None)
        items = (
            tuple(lister(task_id, limit=limit + 1, after=after, before=before))
            if callable(lister)
            else ()
        )
        page = items[:limit] if before is None else items[-limit:]
        value = scan.document(page)
        value["_has_previous_items"] = (
            bool((after or before) and page) if before is None else len(items) > limit
        )
        value["_has_next_items"] = len(items) > limit if before is None else bool(page)
        value.update(
            {
                "command": base.command,
                "execute_authorized": base.execute_authorized,
                "started_at": base.started_at.isoformat() if base.started_at else None,
                "completed_at": base.completed_at.isoformat() if base.completed_at else None,
                "total_items": base.total_items,
                "completed_items": base.completed_items,
                "failed_items": base.failed_items,
                "error": base.error,
                "item_limit": limit,
                "items_truncated": len(items) > limit,
            }
        )
        return value

    def _start(self, task_id: str) -> None:
        token = CancellationToken()
        with self._lock:
            self._tokens[task_id] = token
            thread = threading.Thread(
                target=self.run,
                args=(task_id,),
                name=f"mediaflow-manual-scan-{task_id[:8]}",
                daemon=True,
            )
            self._threads[task_id] = thread
            thread.start()

    def _finish(
        self, scan: ManualScanTask, task: PersistentTask, result: ScanResult
    ) -> ManualScanTask:
        status = {
            "completed": PersistentTaskStatus.COMPLETED,
            "partial_success": PersistentTaskStatus.PARTIAL_SUCCESS,
            "failed": PersistentTaskStatus.FAILED,
            "cancelled": PersistentTaskStatus.CANCELLED,
        }[result.status.value]
        errors = tuple(
            self._scan_error_document(error) for error in result.errors[: self.MAX_ERRORS]
        )
        now = self._clock()
        total = max(
            result.statistics.files_visited, 1 if scan.scope_kind is ManualScanScopeKind.FILE else 0
        )
        failed = result.statistics.errors
        reconciliation = (
            scan.scope_kind is ManualScanScopeKind.RESOURCE_LIBRARY
            and scan.mode is ScanMode.FULL
            and status is PersistentTaskStatus.COMPLETED
        )
        if status is PersistentTaskStatus.COMPLETED:
            known_effects = "file_index_discovery_refreshed"
            next_action = "inspect refreshed FileIndex state and choose a current item for Preview"
            failure_stage = None
            error = None
        elif status is PersistentTaskStatus.CANCELLED:
            known_effects = "partial_discovery_only"
            next_action = "inspect persisted item outcomes, then repeat the same bounded Scan"
            failure_stage = "cancellation"
            error = "manual Scan cancelled"
        elif status is PersistentTaskStatus.PARTIAL_SUCCESS:
            known_effects = "partial_discovery_only"
            next_action = (
                "inspect per-item outcomes and resolve the Storage condition before repeating "
                "the same bounded Scan"
            )
            failure_stage = "discovery"
            error = "manual Scan completed with discovery errors"
        else:
            known_effects = "observed_items_only"
            next_action = (
                "inspect the persisted Task and Storage condition, then repeat the same bounded "
                "Scan"
            )
            failure_stage = "source" if scan.scope_kind is ManualScanScopeKind.FILE else "discovery"
            error = "manual Scan failed"
        finished = replace(
            scan,
            status=status,
            updated_at=now,
            cancellation_requested=scan.cancellation_requested
            or status is PersistentTaskStatus.CANCELLED,
            progress=self._progress_document(result.statistics),
            errors=errors,
            reconciliation_complete=reconciliation,
            failure_stage=failure_stage,
            known_effects=known_effects,
            retry_safe=True,
            next_action=next_action,
        )
        finished_task = replace(
            task,
            status=status,
            updated_at=now,
            completed_at=now,
            total_items=total,
            completed_items=max(total - failed, 0),
            failed_items=failed,
            error=error,
        )
        if status is PersistentTaskStatus.FAILED and scan.scope_kind is ManualScanScopeKind.FILE:
            self._record_file_failure(finished, result, now)
        return self._finalize(finished_task, finished)

    def _finish_error(
        self,
        scan: ManualScanTask,
        task: PersistentTask,
        *,
        code: str,
        stage: str,
        message: str,
        next_action: str,
    ) -> ManualScanTask:
        now = self._clock()
        error = {
            "code": code,
            "stage": stage,
            "message": redact_manual_text(message, limit=256),
        }
        finished = replace(
            scan,
            status=PersistentTaskStatus.FAILED,
            updated_at=now,
            progress=dict(scan.progress),
            errors=(error,),
            reconciliation_complete=False,
            failure_stage=stage,
            known_effects="observed_items_only",
            retry_safe=True,
            next_action=next_action,
        )
        finished_task = replace(
            task,
            status=PersistentTaskStatus.FAILED,
            updated_at=now,
            completed_at=now,
            total_items=max(
                task.total_items, 1 if scan.scope_kind is ManualScanScopeKind.FILE else 0
            ),
            failed_items=1,
            error="manual Scan failed",
        )
        if scan.scope_kind is ManualScanScopeKind.FILE:
            self._record_file_failure(scan, None, now, error_document=error)
        return self._finalize(finished_task, finished)

    def _finalize(self, task: PersistentTask, scan: ManualScanTask) -> ManualScanTask:
        finalizer = getattr(self._repository, "finalize_manual_scan", None)
        if callable(finalizer):
            return finalizer(task, scan)
        updater = getattr(self._repository, "update_manual_scan", None)
        if callable(updater):
            updater(scan)
        self._repository.update_task(task)
        return scan

    def _update_progress(
        self, task_id: str, progress: Mapping[str, int], task: PersistentTask
    ) -> None:
        scan = self._require_task(task_id)
        now = self._clock()
        bounded = {
            str(key)[:64]: max(0, int(value))
            for key, value in list(progress.items())[: self.MAX_PROGRESS_KEYS]
            if isinstance(value, int) and not isinstance(value, bool)
        }
        updater = getattr(self._repository, "update_manual_scan", None)
        if callable(updater):
            updater(replace(scan, progress=bounded, updated_at=now))
        files = bounded.get("filesVisited", task.total_items)
        errors = bounded.get("errors", task.failed_items)
        self._repository.update_task(
            replace(
                task,
                updated_at=now,
                total_items=max(task.total_items, files),
                completed_items=max(files - errors, 0),
                failed_items=errors,
            )
        )

    def _record_discovered(self, scan: ManualScanTask, discovered: DiscoveredFile) -> None:
        now = self._clock()
        item = self._item_outcome(scan, discovered, now)
        self._repository.upsert_manual_scan_item(item)
        status = {
            FileScanStatus.READY: TaskItemStatus.SUCCESS,
            FileScanStatus.IGNORED: TaskItemStatus.SKIPPED,
            FileScanStatus.UNSTABLE: TaskItemStatus.PARTIAL,
            FileScanStatus.ERROR: TaskItemStatus.FAILED,
        }.get(discovered.status, TaskItemStatus.SUCCESS)
        self._repository.upsert_item(
            PersistentTaskItem(
                item_id=item.item_id,
                task_id=scan.task_id,
                storage_id=discovered.storage_id,
                resource_library_id=discovered.resource_library_id,
                source_path=discovered.path,
                source_display=discovered.path,
                status=status,
                stage="manual_scan_discovery",
                attempts=1,
                created_at=item.created_at,
                updated_at=now,
                error=item.error,
                source_occurrence_id=discovered.occurrence_id,
                source_fingerprint=discovered.fingerprint,
                source_fingerprint_state=discovered.fingerprint_state,
            )
        )

    def _record_file_failure(
        self,
        scan: ManualScanTask,
        result: ScanResult | None,
        now: datetime,
        *,
        error_document: Mapping[str, object] | None = None,
    ) -> None:
        if not scan.source_path or not scan.storage_id:
            return
        error = error_document or (
            self._scan_error_document(result.errors[0])
            if result is not None and result.errors
            else {"code": "scan_failed", "stage": "source"}
        )
        item = ManualScanItemOutcome(
            item_id=self._item_id(scan.task_id, scan.source_path),
            task_id=scan.task_id,
            storage_id=scan.storage_id,
            resource_library_id=scan.resource_library_id,
            source_path=scan.source_path,
            file_id=scan.file_id,
            status=FileScanStatus.ERROR,
            change=None,
            stage="manual_scan_discovery",
            created_at=scan.created_at,
            updated_at=now,
            source_occurrence_id=scan.source_occurrence_id,
            source_fingerprint=scan.source_fingerprint,
            source_fingerprint_state="verified",
            error=redact_manual_text(error, limit=256),
            known_effects="observed_items_only",
            next_action=(
                "refresh FileIndex and select the current source occurrence before repeating "
                "the Scan"
            ),
        )
        self._repository.upsert_manual_scan_item(item)
        self._repository.upsert_item(
            PersistentTaskItem(
                item_id=item.item_id,
                task_id=scan.task_id,
                storage_id=item.storage_id,
                resource_library_id=item.resource_library_id,
                source_path=item.source_path,
                source_display=item.source_path,
                status=TaskItemStatus.FAILED,
                stage=item.stage,
                attempts=1,
                created_at=item.created_at,
                updated_at=now,
                error=item.error,
                source_occurrence_id=item.source_occurrence_id,
                source_fingerprint=item.source_fingerprint,
                source_fingerprint_state=item.source_fingerprint_state,
            )
        )

    def _upsert_initial_file_item(self, scan: ManualScanTask, record, now: datetime) -> None:
        item = ManualScanItemOutcome(
            item_id=self._item_id(scan.task_id, record.path),
            task_id=scan.task_id,
            storage_id=record.storage_id,
            resource_library_id=record.resource_library_id,
            source_path=record.path,
            file_id=record.file_id,
            status=FileScanStatus.DISCOVERED,
            change=FileChange.UNCHANGED,
            stage="manual_scan_admitted",
            created_at=now,
            updated_at=now,
            source_occurrence_id=record.occurrence_id,
            source_fingerprint=record.fingerprint,
            source_fingerprint_state=record.occurrence_state.value,
            next_action="inspect the persisted Scan Task while discovery is running",
        )
        self._repository.upsert_manual_scan_item(item)
        self._repository.upsert_item(
            PersistentTaskItem(
                item_id=item.item_id,
                task_id=scan.task_id,
                storage_id=record.storage_id,
                resource_library_id=record.resource_library_id,
                source_path=record.path,
                source_display=record.path,
                status=TaskItemStatus.PENDING,
                stage="manual_scan_admitted",
                attempts=0,
                created_at=now,
                updated_at=now,
                source_occurrence_id=record.occurrence_id,
                source_fingerprint=record.fingerprint,
                source_fingerprint_state=record.occurrence_state.value,
            )
        )

    def _require_library(self, resource_library_id: str) -> ResourceLibrary:
        values = tuple(
            value for value in self._resource_libraries if value.library_id == resource_library_id
        )
        if not values:
            raise ManualScanError(
                "resource_library_not_found",
                "configured ResourceLibrary was not found",
                status=404,
                durable_state="no_task_created",
                next_action="select one enabled ResourceLibrary from the current Active runtime",
            )
        if len(values) != 1:
            raise ManualScanError(
                "resource_library_ambiguous",
                "ResourceLibrary identity is ambiguous",
                status=409,
                durable_state="no_task_created",
                next_action="repair the duplicate ResourceLibrary configuration before scanning",
            )
        library = values[0]
        if not library.enabled:
            raise ManualScanError(
                "resource_library_unready",
                "ResourceLibrary is disabled",
                status=409,
                durable_state="no_task_created",
                next_action="enable and activate this ResourceLibrary, then retry",
            )
        return library

    def _preflight_storage(self, library: ResourceLibrary) -> Storage:
        try:
            root = normalize_resource_root(library.root_path)
            storage = self._storage_map({library.storage_id}).get(library.storage_id)
            if storage is None:
                raise ValueError("configured Storage is unavailable")
            entry = storage.stat(root)
            if entry.entry_type is not StorageEntryType.DIRECTORY:
                raise ValueError("configured ResourceLibrary root is not a directory")
            return storage
        except (StorageError, ValueError, OSError) as error:
            raise ManualScanError(
                "resource_library_unready",
                "configured ResourceLibrary Storage is unavailable",
                status=503,
                durable_state="no_task_created",
                next_action="restore the configured Storage/root, then retry the same bounded Scan",
                details={"reason": redact_manual_text(error, limit=160)},
            ) from error

    def _require_current_file(self, request: ManualScanRequest):
        lister = getattr(self._file_index, "list_by_resource_library", None)
        if not callable(lister):
            raise ManualScanError(
                "file_index_unavailable",
                "FileIndex current-source lookup is unavailable",
                status=503,
                durable_state="no_task_created",
                next_action="restore FileIndex persistence, then refresh and retry",
            )
        values = tuple(
            record
            for record in lister(request.resource_library_id)
            if record.file_id == request.file_id
        )
        if not values:
            raise ManualScanError(
                "source_not_found",
                "current FileIndex source was not found",
                status=404,
                durable_state="no_task_created",
                next_action="refresh FileIndex and select an existing current source item",
            )
        if len(values) != 1:
            raise ManualScanError(
                "source_ambiguous",
                "FileIndex file ID is ambiguous in this ResourceLibrary",
                status=409,
                durable_state="no_task_created",
                next_action="scope the request to one unambiguous current FileIndex item",
            )
        record = values[0]
        if (
            record.occurrence_state is not OccurrenceState.VERIFIED
            or record.scan_status is not FileScanStatus.READY
            or not record.occurrence_id
            or not record.fingerprint
        ):
            raise ManualScanError(
                "source_not_ready",
                "FileIndex source is not a verified ready current occurrence",
                status=409,
                durable_state="no_task_created",
                next_action=(
                    "complete a ResourceLibrary Scan, then select the refreshed current source"
                ),
            )
        if (
            record.occurrence_id != request.source_occurrence_id
            or record.fingerprint != request.source_fingerprint
        ):
            raise ManualScanError(
                "source_stale",
                "FileIndex source occurrence is stale or replaced",
                status=409,
                durable_state="no_task_created",
                next_action=(
                    "refresh FileIndex and select the current source occurrence before scanning"
                ),
            )
        return record

    def _storage_map(self, storage_ids: set[str] | None = None) -> dict[str, Storage]:
        if self._storage_factory is not None:
            if storage_ids is None:
                return dict(self._storage_factory())
            return dict(self._storage_factory(storage_ids=storage_ids))
        return dict(self._storages)

    def _acquire_library(self, resource_library_id: str) -> None:
        with self._lock:
            if resource_library_id in self._active_libraries:
                raise ScanAlreadyRunningError(
                    f"manual Scan already running for ResourceLibrary {resource_library_id}"
                )
            self._active_libraries.add(resource_library_id)

    def _release_library(self, resource_library_id: str) -> None:
        with self._lock:
            self._active_libraries.discard(resource_library_id)

    def _require_task(self, task_id: str) -> ManualScanTask:
        getter = getattr(self._repository, "get_manual_scan", None)
        value = getter(task_id) if callable(getter) else None
        if value is None:
            raise ManualScanError(
                "task_not_found",
                "manual Scan Task was not found",
                status=404,
                next_action="open the persisted Tasks view and select an existing Scan Task",
            )
        return value

    @staticmethod
    def _same_alias(document: Mapping[str, object], first: str, second: str, label: str) -> object:
        value = document.get(first)
        alternate = document.get(second)
        if value is not None and alternate is not None and value != alternate:
            raise ValueError(f"manual Scan {label} fields disagree")
        return value if value is not None else alternate

    @staticmethod
    def _progress_document(statistics: ScanStatistics) -> dict[str, int]:
        return {
            "directoriesVisited": statistics.directories_visited,
            "filesVisited": statistics.files_visited,
            "mediaCandidates": statistics.media_candidates,
            "ignored": statistics.ignored,
            "unstable": statistics.unstable,
            "errors": statistics.errors,
        }

    @staticmethod
    def _scan_error_document(error) -> dict[str, object]:
        return {
            "code": error.storage_error.value,
            "path": redact_manual_text(error.path, limit=256),
            "operation": redact_manual_text(error.operation, limit=64),
        }

    @staticmethod
    def _item_id(task_id: str, path: str) -> str:
        return uuid.uuid5(uuid.NAMESPACE_URL, f"mediaflow:manual-scan:{task_id}:{path}").hex

    def _item_outcome(
        self, scan: ManualScanTask, discovered: DiscoveredFile, now: datetime
    ) -> ManualScanItemOutcome:
        return ManualScanItemOutcome(
            item_id=self._item_id(scan.task_id, discovered.path),
            task_id=scan.task_id,
            storage_id=discovered.storage_id,
            resource_library_id=discovered.resource_library_id,
            source_path=discovered.path,
            file_id=discovered.file_id,
            status=discovered.status,
            change=discovered.change,
            stage="manual_scan_discovery",
            created_at=scan.created_at,
            updated_at=now,
            source_occurrence_id=discovered.occurrence_id,
            source_fingerprint=discovered.fingerprint,
            source_fingerprint_state=discovered.fingerprint_state,
            known_effects="file_index_discovery_refreshed",
            next_action=(
                "inspect the refreshed FileIndex item"
                if discovered.status is FileScanStatus.READY
                else "inspect the persisted discovery state before continuing"
            ),
        )
