from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from mediaflow.domain.automation import (
    AutomationClaimLost,
    AutomationCommand,
    AutomationJob,
    AutomationJobStatus,
    AutomationQueueFull,
    ScheduleAuditRecord,
    ScheduleState,
)
from mediaflow.domain.automation_task_definition_preview import (
    AutomationPreviewSource,
    AutomationTaskDefinitionPreview,
    AutomationTaskDefinitionPreviewItem,
    AutomationTaskDefinitionPreviewItemStatus,
    AutomationTaskDefinitionPreviewStatus,
    AutomationTaskDefinitionPreviewUnavailable,
)
from mediaflow.domain.classification_review import (
    ClassificationReview,
    ClassificationReviewChoice,
    ClassificationReviewDecisionAudit,
    ClassificationReviewStatus,
)
from mediaflow.domain.dashboard import (
    DashboardFileCounts,
    DashboardJobCounts,
    DashboardPersistentState,
    DashboardTaskCounts,
    RecentOperationalFailure,
)
from mediaflow.domain.execution_authorization import (
    ExecutionAuthorization,
    ExecutionAuthorizationAudit,
    ExecutionAuthorizationStatus,
)
from mediaflow.domain.file_catalog import FileReviewLink
from mediaflow.domain.logging import LogLevel, OperationalLogRecord
from mediaflow.domain.manual_execution import (
    ManualExecution,
    ManualExecutionAuthorization,
    ManualExecutionAuthorizationAudit,
    ManualExecutionAuthorizationStatus,
    ManualExecutionEffect,
    ManualExecutionError,
    ManualExecutionItem,
    ManualExecutionItemStatus,
    ManualExecutionScopeItem,
    ManualExecutionStatus,
)
from mediaflow.domain.manual_ignore import (
    ManualIgnoreBatchRequest,
    ManualIgnoreCandidate,
    ManualIgnoreDecision,
    ManualReviewKind,
)
from mediaflow.domain.manual_organize import (
    ManualChoice,
    ManualConfigurationSnapshot,
    ManualIntentAudit,
    ManualIntentConflict,
    ManualIntentItem,
    ManualIntentItemStatus,
    ManualIntentStatus,
    ManualIntentUnavailable,
    ManualOrganizeIntent,
    ManualSourceIdentity,
)
from mediaflow.domain.manual_organize_preview import (
    ManualOrganizePreview,
    ManualPreviewItem,
    ManualPreviewItemStatus,
    ManualPreviewStatus,
    ManualPreviewUnavailable,
)
from mediaflow.domain.manual_safety import (
    redact_evidence_text,
    redact_manual_text,
    redact_manual_value,
)
from mediaflow.domain.media_evidence import (
    PipelineEvidence,
    evidence_from_document,
    redact_pipeline_evidence,
)
from mediaflow.domain.metadata_correction import (
    MetadataCorrectionBatchResolveRequest,
    MetadataCorrectionContinuation,
    MetadataCorrectionContinuationStatus,
    MetadataCorrectionDecisionAudit,
    MetadataCorrectionReview,
    MetadataCorrectionStatus,
)
from mediaflow.domain.metadata_review import (
    MetadataReview,
    MetadataReviewBatchResolveRequest,
    MetadataReviewCandidate,
    MetadataReviewDecisionAudit,
    MetadataReviewScoreComponent,
    MetadataReviewStatus,
)
from mediaflow.domain.notification import (
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationEventType,
)
from mediaflow.domain.processing_checkpoint import (
    CheckpointAudit,
    CheckpointBlocker,
    ProcessingCheckpointContext,
)
from mediaflow.domain.recognition_review import (
    RecognitionBatchResolveRequest,
    RecognitionRetryBatchRequest,
    RecognitionRetryDecision,
    RecognitionReview,
    RecognitionReviewChoice,
    RecognitionReviewDecisionAudit,
    RecognitionReviewStatus,
)
from mediaflow.domain.recovery import (
    RecoveryAdmissionError,
    RecoveryAdmissionReason,
    RecoveryRequest,
    RecoveryRequestStatus,
)
from mediaflow.domain.recovery_batch import (
    RecoveryBatch,
    RecoveryBatchItem,
    RecoveryBatchItemStatus,
)
from mediaflow.domain.recovery_continuation import (
    RecoveryContinuation,
    RecoveryContinuationError,
    RecoveryContinuationReason,
    RecoveryContinuationStatus,
)
from mediaflow.domain.security import SecurityAuditRecord
from mediaflow.domain.task_persistence import (
    ConfirmationStatus,
    ConflictConfirmation,
    ConflictDecisionAudit,
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
    redact_persistent_result,
)
from mediaflow.domain.task_retry import TaskRetryBatchRequest, TaskRetryRequestDecision

# Manual intent, Preview, exact execution, and Automation Task Definition
# Preview tables are additive migrations on the runtime schema.  The table
# creation below is idempotent and upgrades older runtime databases without
# rewriting existing rows.
SCHEMA_VERSION = 28


def _canonical_json(value: object) -> str:
    """Compare persisted JSON values without allowing formatting to affect identity."""

    parsed = json.loads(value) if isinstance(value, str) else value
    return json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint_json(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class SQLiteTaskRepository:
    """Durable task/result/lock adapter sharing the configured runtime SQLite database."""

    def __init__(self, database_path: str | Path) -> None:
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self._path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._initialize()

    @property
    def schema_version(self) -> int:
        with self._lock:
            row = self._connection.execute(
                "SELECT version FROM schema_version WHERE component = 'runtime'"
            ).fetchone()
        return int(row["version"])

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> SQLiteTaskRepository:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def create_task(self, task: PersistentTask) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._task_values(task),
            )

    def update_task(self, task: PersistentTask) -> None:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                UPDATE tasks SET command=?, status=?, execute_authorized=?, created_at=?,
                    updated_at=?, started_at=?, completed_at=?, total_items=?, completed_items=?,
                    failed_items=?, error=?, pause_requested=?, scope_path=?, item_limit=?,
                    configuration_snapshot_id=?, configuration_snapshot_digest=?
                    WHERE task_id=?
                """,
                (*self._task_values(task)[1:], task.task_id),
            )
            if cursor.rowcount != 1:
                raise LookupError(f"task {task.task_id!r} is not configured")

    def request_task_pause(self, task_id: str, updated_at: datetime) -> PersistentTask:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "UPDATE tasks SET pause_requested=1, updated_at=? WHERE task_id=? AND status=?",
                (updated_at.isoformat(), task_id, PersistentTaskStatus.RUNNING.value),
            )
            if cursor.rowcount != 1:
                existing = self.get_task(task_id)
                if existing is None:
                    raise LookupError(f"task {task_id!r} was not found")
                if existing.status is PersistentTaskStatus.RUNNING and existing.pause_requested:
                    return existing
                raise ValueError("only a running task can be paused")
            row = self._connection.execute(
                "SELECT * FROM tasks WHERE task_id=?", (task_id,)
            ).fetchone()
        return self._task(row)

    def task_pause_requested(self, task_id: str) -> bool:
        with self._lock:
            row = self._connection.execute(
                "SELECT pause_requested FROM tasks WHERE task_id=?", (task_id,)
            ).fetchone()
        if row is None:
            raise LookupError(f"task {task_id!r} was not found")
        return bool(row["pause_requested"])

    def get_task(self, task_id: str) -> PersistentTask | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
        return self._task(row) if row else None

    def list_tasks(
        self,
        *,
        limit: int | None = None,
        after: tuple[datetime, str] | None = None,
        before: tuple[datetime, str] | None = None,
    ) -> tuple[PersistentTask, ...]:
        if after is not None and before is not None:
            raise ValueError("after and before are mutually exclusive")
        query = "SELECT * FROM tasks"
        parameters: tuple[object, ...] = ()
        reverse = before is not None
        if after is not None:
            timestamp = after[0].isoformat()
            query += " WHERE (created_at < ? OR (created_at = ? AND task_id < ?))"
            parameters = (timestamp, timestamp, after[1])
        elif before is not None:
            timestamp = before[0].isoformat()
            query += " WHERE (created_at > ? OR (created_at = ? AND task_id > ?))"
            parameters = (timestamp, timestamp, before[1])
        query += (
            " ORDER BY created_at ASC, task_id ASC"
            if reverse
            else " ORDER BY created_at DESC, task_id DESC"
        )
        if limit is not None:
            query += " LIMIT ?"
            parameters += (limit,)
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
        values = tuple(self._task(row) for row in rows)
        return tuple(reversed(values)) if reverse else values

    def load_dashboard_state(self, *, recent_limit: int) -> DashboardPersistentState:
        if isinstance(recent_limit, bool) or not isinstance(recent_limit, int):
            raise ValueError("dashboard recent limit must be an integer")
        if recent_limit < 1 or recent_limit > 50:
            raise ValueError("dashboard recent limit must be between 1 and 50")
        with self._lock:
            has_file_index = self._connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='file_index'"
            ).fetchone()
            file_counts = self._status_counts("file_index", "scan_status") if has_file_index else {}
            task_counts = self._status_counts("tasks", "status")
            job_counts = self._status_counts("automation_jobs", "status")
            pending_confirmations = self._count_where("conflict_confirmations", "status", "pending")
            pending_metadata_reviews = self._count_where("metadata_reviews", "status", "pending")
            pending_classification_reviews = self._count_where(
                "classification_reviews", "status", "pending"
            )
            dead_letters = self._count_where("notification_deliveries", "status", "dead-letter")
            failures = self._recent_operational_failures(recent_limit)
        return DashboardPersistentState(
            files=DashboardFileCounts(
                total=sum(file_counts.values()),
                ready=file_counts.get("ready", 0),
                unstable=file_counts.get("unstable", 0),
                missing=file_counts.get("missing", 0),
                errors=file_counts.get("error", 0),
            ),
            tasks=DashboardTaskCounts(
                total=sum(task_counts.values()),
                pending=task_counts.get("pending", 0),
                running=task_counts.get("running", 0),
                completed=task_counts.get("completed", 0),
                partial_success=task_counts.get("partial_success", 0),
                failed=task_counts.get("failed", 0),
                cancelled=task_counts.get("cancelled", 0),
                paused=task_counts.get("paused", 0),
            ),
            jobs=DashboardJobCounts(
                total=sum(job_counts.values()),
                pending=job_counts.get("pending", 0),
                running=job_counts.get("running", 0),
                completed=job_counts.get("completed", 0),
                failed=job_counts.get("failed", 0),
                cancelled=job_counts.get("cancelled", 0),
            ),
            pending_confirmations=pending_confirmations,
            pending_metadata_reviews=pending_metadata_reviews,
            pending_classification_reviews=pending_classification_reviews,
            dead_letter_notifications=dead_letters,
            recent_failures=failures,
        )

    def _status_counts(self, table: str, column: str) -> dict[str, int]:
        rows = self._connection.execute(
            f"SELECT {column}, COUNT(*) AS value_count FROM {table} GROUP BY {column}"
        ).fetchall()
        return {str(row[column]): int(row["value_count"]) for row in rows}

    def _count_where(self, table: str, column: str, value: str) -> int:
        row = self._connection.execute(
            f"SELECT COUNT(*) AS value_count FROM {table} WHERE {column}=?", (value,)
        ).fetchone()
        return int(row["value_count"])

    def _recent_operational_failures(self, limit: int) -> tuple[RecentOperationalFailure, ...]:
        rows = self._connection.execute(
            """
            SELECT 'task' AS kind, task_id AS identifier, status, updated_at AS occurred_at,
                   'task_failed' AS category
            FROM tasks WHERE status IN ('failed', 'partial_success')
            UNION ALL
            SELECT 'job', job_id, status, updated_at, 'job_failed'
            FROM automation_jobs WHERE status='failed'
            UNION ALL
            SELECT 'notification', delivery_id, status, updated_at, 'delivery_failed'
            FROM notification_deliveries WHERE status='dead-letter'
            ORDER BY occurred_at DESC, kind, identifier
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return tuple(
            RecentOperationalFailure(
                row["kind"],
                row["identifier"],
                row["status"],
                datetime.fromisoformat(row["occurred_at"]),
                row["category"],
            )
            for row in rows
        )

    def upsert_item(self, item: PersistentTaskItem) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO task_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET
                    status=excluded.status, stage=excluded.stage, attempts=excluded.attempts,
                    updated_at=excluded.updated_at, plan_id=excluded.plan_id,
                    destination_storage_id=excluded.destination_storage_id,
                    destination_path=excluded.destination_path,
                    execution_status=excluded.execution_status, error=excluded.error
                """,
                self._item_values(item),
            )

    def get_item(self, item_id: str) -> PersistentTaskItem | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM task_items WHERE item_id = ?", (item_id,)
            ).fetchone()
        return self._item(row) if row else None

    def list_items(
        self,
        task_id: str,
        *,
        limit: int | None = None,
        after: tuple[datetime, str] | None = None,
        before: tuple[datetime, str] | None = None,
    ) -> tuple[PersistentTaskItem, ...]:
        if after is not None and before is not None:
            raise ValueError("after and before are mutually exclusive")
        query = "SELECT * FROM task_items WHERE task_id = ?"
        parameters: tuple[object, ...] = (task_id,)
        reverse = before is not None
        if after is not None:
            timestamp = after[0].isoformat()
            query += " AND (created_at > ? OR (created_at = ? AND item_id > ?))"
            parameters += (timestamp, timestamp, after[1])
        elif before is not None:
            timestamp = before[0].isoformat()
            query += " AND (created_at < ? OR (created_at = ? AND item_id < ?))"
            parameters += (timestamp, timestamp, before[1])
        query += (
            " ORDER BY created_at DESC, item_id DESC"
            if reverse
            else " ORDER BY created_at, item_id"
        )
        if limit is not None:
            query += " LIMIT ?"
            parameters += (limit,)
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
        values = tuple(self._item(row) for row in rows)
        return tuple(reversed(values)) if reverse else values

    def list_failed_items(self, *, limit=100, task_id=None):
        if not 1 <= limit <= 1000:
            raise ValueError("task retry limit must be between 1 and 1000")
        query = """
            SELECT * FROM task_items
            WHERE status IN ('failed', 'partial')
        """
        parameters: tuple[object, ...] = ()
        if task_id is not None:
            query += " AND task_id = ?"
            parameters += (task_id,)
        query += " ORDER BY updated_at, item_id LIMIT ?"
        parameters += (limit,)
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
        return tuple(self._item(row) for row in rows)

    def request_task_retries(self, requests: tuple[TaskRetryBatchRequest, ...]) -> None:
        if not requests:
            raise ValueError("task retry batch must not be empty")
        with self._lock, self._connection:
            for request in requests:
                decision = request.decision
                item = request.item
                cursor = self._connection.execute(
                    """UPDATE task_items SET status=?, stage=?, updated_at=?
                    WHERE item_id=? AND task_id=? AND status='failed'""",
                    (
                        item.status.value,
                        item.stage,
                        item.updated_at.isoformat(),
                        item.item_id,
                        item.task_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValueError("TaskItem is not failed")
                self._connection.execute(
                    "INSERT INTO task_retry_audit VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        decision.decision_id,
                        decision.task_id,
                        decision.item_id,
                        decision.decided_at.isoformat(),
                        decision.actor,
                        decision.note,
                    ),
                )

    def list_task_retry_audit(self, item_id):
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM task_retry_audit WHERE item_id=?
                ORDER BY decided_at, decision_id""",
                (item_id,),
            ).fetchall()
        return tuple(
            TaskRetryRequestDecision(
                row["decision_id"],
                row["task_id"],
                row["item_id"],
                datetime.fromisoformat(row["decided_at"]),
                row["actor"],
                row["note"],
            )
            for row in rows
        )

    def list_recovery_requests(
        self, item_id: str, *, limit: int = 32
    ) -> tuple[RecoveryRequest, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("recovery request limit must be between 1 and 100")
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM recovery_requests WHERE item_id=?
                ORDER BY requested_at, request_id LIMIT ?""",
                (item_id, limit),
            ).fetchall()
        return tuple(self._recovery_request(row) for row in rows)

    def get_recovery_request(self, request_id: str) -> RecoveryRequest | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM recovery_requests WHERE request_id=?", (request_id,)
            ).fetchone()
        return self._recovery_request(row) if row else None

    def get_active_recovery_request(self, item_id: str) -> RecoveryRequest | None:
        with self._lock:
            row = self._connection.execute(
                """SELECT * FROM recovery_requests
                WHERE item_id=? AND status='pending'
                ORDER BY requested_at, request_id LIMIT 1""",
                (item_id,),
            ).fetchone()
        return self._recovery_request(row) if row else None

    def admit_recovery_request(
        self,
        request: RecoveryRequest,
        *,
        expected_checkpoint_version: str,
        checkpoint_projector=None,
    ) -> RecoveryRequest:
        """Atomically record one request and its existing action-specific transition.

        The caller supplies the immutable checkpoint version it presented.  The repository
        re-projects the same bounded context while holding an IMMEDIATE transaction, so a
        concurrent review/result/request cannot be silently overwritten.
        """

        if request.status is not RecoveryRequestStatus.PENDING:
            raise ValueError("recovery request must start pending")
        if not isinstance(expected_checkpoint_version, str) or not expected_checkpoint_version:
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.INVALID_VERSION,
                "checkpoint version is required",
            )
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._connection.execute(
                    """SELECT i.*, t.command AS task_command, t.status AS task_status,
                        t.execute_authorized AS task_execute_authorized,
                        t.created_at AS task_created_at, t.updated_at AS task_updated_at,
                        t.started_at AS task_started_at, t.completed_at AS task_completed_at,
                        t.total_items AS task_total_items,
                        t.completed_items AS task_completed_items,
                        t.failed_items AS task_failed_items, t.error AS task_error,
                        t.pause_requested AS task_pause_requested, t.scope_path AS task_scope_path,
                        t.item_limit AS task_item_limit,
                        t.configuration_snapshot_id AS task_configuration_snapshot_id,
                        t.configuration_snapshot_digest AS task_configuration_snapshot_digest
                    FROM task_items i JOIN tasks t ON t.task_id=i.task_id
                    WHERE i.item_id=?""",
                    (request.item_id,),
                ).fetchone()
                if row is None:
                    raise RecoveryAdmissionError(
                        RecoveryAdmissionReason.UNKNOWN_ITEM,
                        "TaskItem was not found",
                    )
                if row["task_id"] != request.task_id:
                    raise RecoveryAdmissionError(
                        RecoveryAdmissionReason.ITEM_TASK_MISMATCH,
                        "TaskItem was not found in the specified Task",
                    )
                existing_row = self._connection.execute(
                    """SELECT * FROM recovery_requests
                    WHERE item_id=? AND status='pending'
                    ORDER BY requested_at, request_id LIMIT 1""",
                    (request.item_id,),
                ).fetchone()
                if existing_row is not None:
                    existing = self._recovery_request(existing_row)
                    self._connection.commit()
                    return existing

                context = self._get_processing_checkpoint_context_locked(
                    request.item_id, result_limit=32, audit_limit=200
                )
                if checkpoint_projector is None:
                    from mediaflow.application.processing_checkpoint import (
                        ProcessingCheckpointService,
                    )

                    current = ProcessingCheckpointService(self)._project(context)
                else:
                    current = checkpoint_projector(context)
                action = next(
                    (value for value in current.actions if value.action_id == request.action_id),
                    None,
                )
                if action is None:
                    raise RecoveryAdmissionError(
                        RecoveryAdmissionReason.INVALID_ACTION,
                        "requested recovery action is unknown",
                        current_checkpoint_version=current.checkpoint_version,
                    )
                if not action.admissible:
                    raise RecoveryAdmissionError(
                        RecoveryAdmissionReason.ACTION_NOT_PERMITTED,
                        "requested recovery action is not permitted",
                        current_checkpoint_version=current.checkpoint_version,
                    )
                if expected_checkpoint_version != current.checkpoint_version:
                    raise RecoveryAdmissionError(
                        RecoveryAdmissionReason.STALE_CHECKPOINT,
                        "checkpoint version is stale; refresh before requesting recovery",
                        current_checkpoint_version=current.checkpoint_version,
                    )
                if (
                    request.checkpoint_version != current.checkpoint_version
                    or request.task_id != current.task_id
                    or request.item_id != current.item_id
                    or request.source_storage_id != current.source_storage_id
                    or request.source_path != current.source_path
                    or request.configuration_snapshot_id != current.configuration.snapshot_id
                    or request.configuration_snapshot_digest
                    != current.configuration.snapshot_digest
                ):
                    raise RecoveryAdmissionError(
                        RecoveryAdmissionReason.STALE_CHECKPOINT,
                        "checkpoint identity changed; refresh before requesting recovery",
                        current_checkpoint_version=current.checkpoint_version,
                    )
                if request.action_id == "retry":
                    self._admit_retry_locked(request, row)
                elif request.action_id == "ignore":
                    self._admit_ignore_locked(request, row)
                else:
                    raise RecoveryAdmissionError(
                        RecoveryAdmissionReason.ACTION_NOT_PERMITTED,
                        "requested recovery action is not admissible",
                        current_checkpoint_version=current.checkpoint_version,
                    )
                self._connection.execute(
                    """INSERT INTO recovery_requests (
                        request_id, task_id, item_id, action_id, checkpoint_version,
                        source_storage_id, source_path, configuration_snapshot_id,
                        configuration_snapshot_digest, actor, requested_at, status, note,
                        authority_statement, next_action, review_kind, review_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    self._recovery_request_values(request),
                )
            except BaseException:
                self._connection.rollback()
                raise
            self._connection.commit()
            return request

    def _admit_retry_locked(self, request: RecoveryRequest, row: sqlite3.Row) -> None:
        if row["status"] == TaskItemStatus.FAILED.value:
            cursor = self._connection.execute(
                """UPDATE task_items SET status=?, stage=?, updated_at=?
                WHERE item_id=? AND task_id=? AND status='failed'""",
                (
                    TaskItemStatus.PENDING.value,
                    "task_retry_requested",
                    request.requested_at.isoformat(),
                    request.item_id,
                    request.task_id,
                ),
            )
            if cursor.rowcount != 1:
                raise RecoveryAdmissionError(
                    RecoveryAdmissionReason.ACTION_NOT_PERMITTED,
                    "TaskItem is no longer failed or partial",
                )
            self._connection.execute(
                "INSERT INTO task_retry_audit VALUES (?, ?, ?, ?, ?, ?)",
                (
                    request.request_id,
                    request.task_id,
                    request.item_id,
                    request.requested_at.isoformat(),
                    request.actor,
                    request.note,
                ),
            )
            return
        elif (
            row["status"] == TaskItemStatus.PENDING.value and row["stage"] == "task_retry_requested"
        ):
            # Re-admission after a prior request reached a terminal state.  The
            # item stays pending and keeps its original evidence; only the
            # admission timestamp and audit advance.
            cursor = self._connection.execute(
                """UPDATE task_items SET updated_at=?
                WHERE item_id=? AND task_id=? AND status='pending'
                AND stage='task_retry_requested'""",
                (
                    request.requested_at.isoformat(),
                    request.item_id,
                    request.task_id,
                ),
            )
            if cursor.rowcount != 1:
                raise RecoveryAdmissionError(
                    RecoveryAdmissionReason.ACTION_NOT_PERMITTED,
                    "TaskItem is no longer pending",
                )
            # The legacy action audit keeps one row per item (latest decision);
            # the full request history is preserved in recovery_requests.
            existing = self._connection.execute(
                "SELECT decision_id FROM task_retry_audit WHERE item_id=?",
                (request.item_id,),
            ).fetchone()
            if existing is None:
                self._connection.execute(
                    "INSERT INTO task_retry_audit VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        request.request_id,
                        request.task_id,
                        request.item_id,
                        request.requested_at.isoformat(),
                        request.actor,
                        request.note,
                    ),
                )
            else:
                self._connection.execute(
                    """UPDATE task_retry_audit
                    SET decision_id=?, task_id=?, decided_at=?, actor=?, note=?
                    WHERE item_id=?""",
                    (
                        request.request_id,
                        request.task_id,
                        request.requested_at.isoformat(),
                        request.actor,
                        request.note,
                        request.item_id,
                    ),
                )
            return
        else:
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.ACTION_NOT_PERMITTED,
                "retry is not permitted for this TaskItem status",
            )

    def _admit_ignore_locked(self, request: RecoveryRequest, row: sqlite3.Row) -> None:
        review_tables = {
            "recognition": ("recognition_reviews", TaskItemStatus.WAITING_RECOGNITION),
            "metadata": ("metadata_reviews", TaskItemStatus.WAITING_METADATA),
            "metadata_correction": (
                "metadata_corrections",
                TaskItemStatus.WAITING_METADATA_CORRECTION,
            ),
        }
        if request.review_kind not in review_tables or not request.review_id:
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.REVIEW_NOT_PENDING,
                "ignore requires a pending supported review",
            )
        table, waiting_status = review_tables[request.review_kind]
        cursor = self._connection.execute(
            f"""UPDATE {table} SET status='ignored', updated_at=?, decided_at=?, actor=?
            WHERE review_id=? AND item_id=? AND status='pending'""",
            (
                request.requested_at.isoformat(),
                request.requested_at.isoformat(),
                request.actor,
                request.review_id,
                request.item_id,
            ),
        )
        if cursor.rowcount != 1:
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.REVIEW_NOT_PENDING,
                "manual review is not pending",
            )
        cursor = self._connection.execute(
            """UPDATE task_items SET status=?, stage=?, updated_at=?
            WHERE item_id=? AND task_id=? AND status=?""",
            (
                TaskItemStatus.IGNORED.value,
                "ignored_by_operator",
                request.requested_at.isoformat(),
                request.item_id,
                request.task_id,
                waiting_status.value,
            ),
        )
        if cursor.rowcount != 1:
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.ACTION_NOT_PERMITTED,
                "TaskItem is no longer waiting for the matching review",
            )
        self._connection.execute(
            "INSERT INTO manual_ignore_audit VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                request.request_id,
                request.task_id,
                request.item_id,
                request.review_kind,
                request.review_id,
                request.requested_at.isoformat(),
                request.actor,
                request.note,
            ),
        )

    def get_recovery_continuation_for_request(self, request_id: str) -> RecoveryContinuation | None:
        with self._lock:
            row = self._connection.execute(
                """SELECT * FROM recovery_continuations WHERE request_id=?
                ORDER BY created_at DESC, continuation_id DESC LIMIT 1""",
                (request_id,),
            ).fetchone()
        return self._recovery_continuation(row) if row else None

    def get_recovery_continuation_for_job(self, job_id: str) -> RecoveryContinuation | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM recovery_continuations WHERE job_id=?", (job_id,)
            ).fetchone()
        return self._recovery_continuation(row) if row else None

    def list_recovery_continuations(
        self, item_id: str, *, limit: int = 32
    ) -> tuple[RecoveryContinuation, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("recovery continuation limit must be between 1 and 100")
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM recovery_continuations WHERE source_item_id=?
                ORDER BY created_at DESC, continuation_id DESC LIMIT ?""",
                (item_id, limit),
            ).fetchall()
        return tuple(self._recovery_continuation(row) for row in rows)

    def create_recovery_batch(self, batch: RecoveryBatch) -> None:
        if not batch.items or len(batch.items) > 100:
            raise ValueError("recovery batch must contain between 1 and 100 items")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                self._connection.execute(
                    """INSERT INTO recovery_batches
                    (batch_id, source_task_id, actor, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        batch.batch_id,
                        batch.source_task_id,
                        batch.actor,
                        batch.status.value,
                        batch.created_at.isoformat(),
                        batch.updated_at.isoformat(),
                    ),
                )
                for item in batch.items:
                    self._connection.execute(
                        """INSERT INTO recovery_batch_items
                        (batch_item_id, batch_id, source_task_id, source_item_id,
                         checkpoint_version, status, created_at, updated_at, request_id,
                         continuation_id, job_id, reason, error, next_action)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        self._recovery_batch_item_values(item),
                    )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise

    def update_recovery_batch_item(self, item: RecoveryBatchItem) -> None:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """UPDATE recovery_batch_items SET status=?, updated_at=?, request_id=?,
                continuation_id=?, job_id=?, reason=?, error=?, next_action=?
                WHERE batch_item_id=?""",
                (
                    item.status.value,
                    item.updated_at.isoformat(),
                    item.request_id,
                    item.continuation_id,
                    item.job_id,
                    item.reason,
                    item.error,
                    item.next_action,
                    item.batch_item_id,
                ),
            )
            if cursor.rowcount != 1:
                raise LookupError(f"recovery batch item {item.batch_item_id!r} was not found")

    def get_recovery_batch(self, batch_id: str) -> RecoveryBatch:
        with self._lock:
            batch_row = self._connection.execute(
                "SELECT * FROM recovery_batches WHERE batch_id=?", (batch_id,)
            ).fetchone()
            if batch_row is None:
                raise LookupError(f"recovery batch {batch_id!r} was not found")
            rows = self._connection.execute(
                """SELECT b.*, c.status AS continuation_status, c.error AS continuation_error,
                c.recovery AS continuation_recovery,
                c.new_task_id AS continuation_new_task_id,
                c.new_result_id AS continuation_new_result_id
                FROM recovery_batch_items b
                LEFT JOIN recovery_continuations c ON c.continuation_id=b.continuation_id
                WHERE b.batch_id=? ORDER BY b.source_item_id""",
                (batch_id,),
            ).fetchall()
            items = tuple(self._recovery_batch_item(row) for row in rows)
            unchanged = self._connection.execute(
                """SELECT COUNT(*) AS count FROM task_items
                WHERE task_id=? AND status IN ('success', 'skipped', 'dry_run')
                AND item_id NOT IN
                (SELECT source_item_id FROM recovery_batch_items WHERE batch_id=?)""",
                (batch_row["source_task_id"], batch_id),
            ).fetchone()["count"]
            ignored = self._connection.execute(
                """SELECT COUNT(*) AS count FROM task_items
                WHERE task_id=? AND status = 'ignored'
                AND item_id NOT IN
                (SELECT source_item_id FROM recovery_batch_items WHERE batch_id=?)""",
                (batch_row["source_task_id"], batch_id),
            ).fetchone()["count"]
        status = RecoveryBatch.derive_status(items)
        return RecoveryBatch(
            batch_row["batch_id"],
            batch_row["source_task_id"],
            batch_row["actor"],
            datetime.fromisoformat(batch_row["created_at"]),
            max(
                datetime.fromisoformat(batch_row["updated_at"]),
                *(item.updated_at for item in items),
            ),
            status,
            items,
            unchanged,
            ignored_count=ignored,
        )

    def list_recovery_batches(
        self, source_task_id: str, *, limit: int = 20
    ) -> tuple[RecoveryBatch, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("recovery batch limit must be between 1 and 100")
        with self._lock:
            rows = self._connection.execute(
                """SELECT batch_id FROM recovery_batches
                WHERE source_task_id=? ORDER BY created_at DESC, batch_id DESC LIMIT ?""",
                (source_task_id, limit),
            ).fetchall()
        return tuple(self.get_recovery_batch(row["batch_id"]) for row in rows)

    def admit_recovery_continuation(
        self,
        job: AutomationJob,
        continuation: RecoveryContinuation,
        *,
        maximum_active_jobs: int,
        checkpoint_projector=None,
        batch_item_id: str | None = None,
    ) -> tuple[RecoveryContinuation, bool]:
        """Atomically record one continuation and its Job for an active request.

        The caller supplies the immutable checkpoint version it presented.  The
        repository re-projects the same bounded context while holding an
        IMMEDIATE transaction, so a concurrent review/result/request cannot be
        silently overwritten.  The parent request stays active until the
        continuation reaches a terminal state.
        """

        if (
            isinstance(maximum_active_jobs, bool)
            or not isinstance(maximum_active_jobs, int)
            or not 1 <= maximum_active_jobs <= 10_000
        ):
            raise ValueError("maximum active Jobs must be between 1 and 10000")
        if (
            job.command is not AutomationCommand.RECOVERY_CONTINUATION
            or job.status is not AutomationJobStatus.PENDING
            or job.limit != 1
            or job.execute_authorized
            or job.task_id is not None
            or job.schedule_id is not None
            or job.claim_token is not None
            or job.cancellation_requested
            or not job.configuration_snapshot_id
            or not job.configuration_snapshot_digest
        ):
            raise ValueError("recovery continuation Job identity is invalid")
        if (
            continuation.status is not RecoveryContinuationStatus.QUEUED
            or continuation.job_id != job.job_id
            or continuation.configuration_snapshot_id != job.configuration_snapshot_id
            or continuation.configuration_snapshot_digest != job.configuration_snapshot_digest
            or continuation.new_task_id is not None
            or continuation.new_result_id is not None
            or continuation.started_at is not None
            or continuation.completed_at is not None
            or continuation.error is not None
            or continuation.recovery is not None
        ):
            raise ValueError("recovery continuation identity is invalid")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                request = self._connection.execute(
                    """SELECT r.*, i.task_id AS item_task_id, i.status AS item_status,
                    i.stage AS item_stage,
                    t.configuration_snapshot_id AS task_snapshot_id,
                    t.configuration_snapshot_digest AS task_snapshot_digest
                    FROM recovery_requests r
                    JOIN task_items i ON i.item_id=r.item_id
                    JOIN tasks t ON t.task_id=r.task_id
                    WHERE r.request_id=?""",
                    (continuation.request_id,),
                ).fetchone()
                if request is None:
                    raise ValueError("recovery request was not found")
                if request["status"] != RecoveryRequestStatus.PENDING.value:
                    raise ValueError("recovery request is no longer active")
                if (
                    request["task_id"] != continuation.source_task_id
                    or request["item_id"] != continuation.source_item_id
                    or request["item_task_id"] != continuation.source_task_id
                ):
                    raise ValueError("recovery continuation request identity is stale")
                if (
                    request["configuration_snapshot_id"] != continuation.configuration_snapshot_id
                    or request["configuration_snapshot_digest"]
                    != continuation.configuration_snapshot_digest
                    or request["task_snapshot_id"] != continuation.configuration_snapshot_id
                    or request["task_snapshot_digest"] != continuation.configuration_snapshot_digest
                ):
                    raise ValueError("recovery continuation snapshot pin is stale")
                if request["item_status"] != TaskItemStatus.PENDING.value:
                    raise ValueError("recovery continuation source item is no longer pending")
                existing = self._connection.execute(
                    """SELECT * FROM recovery_continuations
                    WHERE request_id=? AND status IN (?, ?)
                    ORDER BY created_at DESC, continuation_id DESC LIMIT 1""",
                    (
                        continuation.request_id,
                        RecoveryContinuationStatus.QUEUED.value,
                        RecoveryContinuationStatus.RUNNING.value,
                    ),
                ).fetchone()
                if existing is not None:
                    self._connection.commit()
                    return self._recovery_continuation(existing), False
                context = self._get_processing_checkpoint_context_locked(
                    continuation.source_item_id, result_limit=32, audit_limit=200
                )
                if checkpoint_projector is None:
                    from mediaflow.application.processing_checkpoint import (
                        ProcessingCheckpointService,
                    )

                    current = ProcessingCheckpointService(self)._project(context)
                else:
                    current = checkpoint_projector(context)
                if current.checkpoint_version != continuation.checkpoint_version:
                    self._connection.rollback()
                    raise RecoveryContinuationError(
                        RecoveryContinuationReason.STALE_CHECKPOINT,
                        "checkpoint version is stale; refresh before continuing recovery",
                        current_checkpoint_version=current.checkpoint_version,
                    )
                if not self._has_job_capacity(maximum_active_jobs):
                    self._connection.rollback()
                    raise AutomationQueueFull(
                        f"automation queue reached configured active Job limit "
                        f"{maximum_active_jobs}"
                    )
                self._insert_job(job)
                self._connection.execute(
                    """INSERT INTO recovery_continuations
                    (continuation_id, request_id, source_task_id, source_item_id,
                     checkpoint_version, configuration_snapshot_id,
                     configuration_snapshot_digest, boundary, status, created_at,
                     updated_at, actor, job_id, new_task_id, new_result_id, started_at,
                     completed_at, error, recovery, authority_statement)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    self._recovery_continuation_values(continuation),
                )
                if batch_item_id is not None:
                    cursor = self._connection.execute(
                        """UPDATE recovery_batch_items
                        SET status=?, updated_at=?, request_id=?, continuation_id=?,
                            job_id=?, reason=NULL, error=NULL, next_action=?
                        WHERE batch_item_id=? AND batch_id IN
                            (SELECT batch_id FROM recovery_batches
                             WHERE source_task_id=?) AND status=?""",
                        (
                            RecoveryBatchItemStatus.QUEUED.value,
                            datetime.now(UTC).isoformat(),
                            continuation.request_id,
                            continuation.continuation_id,
                            continuation.job_id,
                            continuation.next_action(),
                            batch_item_id,
                            continuation.source_task_id,
                            RecoveryBatchItemStatus.SELECTED.value,
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise ValueError("recovery batch child linkage is unavailable")
                self._connection.commit()
                return continuation, True
            except Exception:
                self._connection.rollback()
                raise

    def mark_recovery_continuation_running(
        self, job_id: str, now: datetime | None = None
    ) -> RecoveryContinuation:
        timestamp = now or datetime.now(UTC)
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """UPDATE recovery_continuations
                SET status=?, updated_at=?, started_at=COALESCE(started_at, ?)
                WHERE job_id=? AND status=?""",
                (
                    RecoveryContinuationStatus.RUNNING.value,
                    timestamp.isoformat(),
                    timestamp.isoformat(),
                    job_id,
                    RecoveryContinuationStatus.QUEUED.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("recovery continuation is not queued")
        return self.require_recovery_continuation_by_job(job_id)

    def bind_recovery_continuation_task(self, job_id: str, task_id: str) -> RecoveryContinuation:
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("continuation Task ID is required")
        with self._lock, self._connection:
            task = self._connection.execute(
                "SELECT task_id FROM tasks WHERE task_id=?", (task_id,)
            ).fetchone()
            if task is None:
                raise LookupError(f"continuation Task {task_id!r} was not found")
            cursor = self._connection.execute(
                """UPDATE recovery_continuations
                SET updated_at=?, new_task_id=?
                WHERE job_id=? AND status=? AND new_task_id IS NULL""",
                (
                    datetime.now(UTC).isoformat(),
                    task_id,
                    job_id,
                    RecoveryContinuationStatus.RUNNING.value,
                ),
            )
            if cursor.rowcount != 1:
                continuation = self.get_recovery_continuation_for_job(job_id)
                if continuation is None:
                    raise LookupError(f"recovery continuation for Job {job_id!r} was not found")
                raise ValueError("recovery continuation Task is already bound")
        return self.require_recovery_continuation_by_job(job_id)

    def complete_recovery_continuation(
        self,
        job_id: str,
        *,
        new_task_id: str | None = None,
        new_result_id: str | None = None,
        success: bool,
        error: str | None = None,
        recovery: str | None = None,
        now: datetime | None = None,
    ) -> RecoveryContinuation:
        timestamp = now or datetime.now(UTC)
        status = (
            RecoveryContinuationStatus.COMPLETED if success else RecoveryContinuationStatus.FAILED
        )
        request_status = (
            RecoveryRequestStatus.COMPLETED if success else RecoveryRequestStatus.FAILED
        )
        with self._lock, self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                cursor = self._connection.execute(
                    """UPDATE recovery_continuations
                    SET status=?, updated_at=?, new_task_id=?, new_result_id=?,
                        completed_at=?, error=?, recovery=?
                    WHERE job_id=? AND status=?""",
                    (
                        status.value,
                        timestamp.isoformat(),
                        new_task_id,
                        new_result_id,
                        timestamp.isoformat(),
                        error,
                        recovery,
                        job_id,
                        RecoveryContinuationStatus.RUNNING.value,
                    ),
                )
                if cursor.rowcount != 1:
                    self._connection.rollback()
                    raise ValueError("recovery continuation is not running")
                row = self._connection.execute(
                    "SELECT request_id FROM recovery_continuations WHERE job_id=?",
                    (job_id,),
                ).fetchone()
                if row is not None:
                    self._resolve_recovery_request_locked(
                        row["request_id"], request_status, timestamp
                    )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        return self.require_recovery_continuation_by_job(job_id)

    def fail_queued_recovery_continuation(
        self,
        job_id: str,
        *,
        error: str,
        recovery: str,
        now: datetime | None = None,
    ) -> RecoveryContinuation:
        timestamp = now or datetime.now(UTC)
        with self._lock, self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                cursor = self._connection.execute(
                    """UPDATE recovery_continuations
                    SET status=?, updated_at=?, completed_at=?, error=?, recovery=?
                    WHERE job_id=? AND status=?""",
                    (
                        RecoveryContinuationStatus.FAILED.value,
                        timestamp.isoformat(),
                        timestamp.isoformat(),
                        error,
                        recovery,
                        job_id,
                        RecoveryContinuationStatus.QUEUED.value,
                    ),
                )
                if cursor.rowcount != 1:
                    self._connection.rollback()
                    raise ValueError("recovery continuation is not queued")
                row = self._connection.execute(
                    "SELECT request_id FROM recovery_continuations WHERE job_id=?",
                    (job_id,),
                ).fetchone()
                if row is not None:
                    self._resolve_recovery_request_locked(
                        row["request_id"], RecoveryRequestStatus.FAILED, timestamp
                    )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        return self.require_recovery_continuation_by_job(job_id)

    def cancel_recovery_continuation(
        self, job_id: str, *, now: datetime | None = None
    ) -> RecoveryContinuation:
        timestamp = now or datetime.now(UTC)
        with self._lock, self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                cursor = self._connection.execute(
                    """UPDATE recovery_continuations
                    SET status=?, updated_at=?, completed_at=?, error=?, recovery=?
                    WHERE job_id=? AND status IN (?, ?)""",
                    (
                        RecoveryContinuationStatus.CANCELLED.value,
                        timestamp.isoformat(),
                        timestamp.isoformat(),
                        "recovery continuation Job was cancelled before completion",
                        "refresh the Task item checkpoint and explicitly continue again",
                        job_id,
                        RecoveryContinuationStatus.QUEUED.value,
                        RecoveryContinuationStatus.RUNNING.value,
                    ),
                )
                if cursor.rowcount != 1:
                    continuation = self.get_recovery_continuation_for_job(job_id)
                    if continuation is None:
                        raise LookupError(f"recovery continuation for Job {job_id!r} was not found")
                    if continuation.status is RecoveryContinuationStatus.CANCELLED:
                        return continuation
                    self._connection.rollback()
                    raise ValueError("recovery continuation is not cancellable")
                row = self._connection.execute(
                    "SELECT request_id FROM recovery_continuations WHERE job_id=?",
                    (job_id,),
                ).fetchone()
                if row is not None:
                    self._resolve_recovery_request_locked(
                        row["request_id"], RecoveryRequestStatus.CANCELLED, timestamp
                    )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        return self.require_recovery_continuation_by_job(job_id)

    def require_recovery_continuation_by_job(self, job_id: str) -> RecoveryContinuation:
        continuation = self.get_recovery_continuation_for_job(job_id)
        if continuation is None:
            raise LookupError(f"recovery continuation for Job {job_id!r} was not found")
        return continuation

    def _resolve_recovery_request_locked(
        self,
        request_id: str,
        status: RecoveryRequestStatus,
        timestamp: datetime,
    ) -> None:
        if status not in {
            RecoveryRequestStatus.COMPLETED,
            RecoveryRequestStatus.FAILED,
            RecoveryRequestStatus.CANCELLED,
        }:
            raise ValueError("recovery request terminal status is invalid")
        cursor = self._connection.execute(
            """UPDATE recovery_requests SET status=?, requested_at=requested_at
            WHERE request_id=? AND status='pending'""",
            (status.value, request_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("recovery request is no longer active")

    def list_ignorable_waiting_items(self, *, limit=100, task_id=None):
        if not 1 <= limit <= 1000:
            raise ValueError("manual ignore limit must be between 1 and 1000")
        query = """
            SELECT i.*, 'recognition' AS review_kind, r.review_id AS review_id
            FROM task_items i
            JOIN recognition_reviews r ON r.item_id = i.item_id AND r.status = 'pending'
            WHERE i.status = ?
        """
        parameters: list[object] = [TaskItemStatus.WAITING_RECOGNITION.value]
        if task_id is not None:
            query += " AND i.task_id = ?"
            parameters.append(task_id)
        query += """
            UNION ALL
            SELECT i.*, 'metadata' AS review_kind, r.review_id AS review_id
            FROM task_items i
            JOIN metadata_reviews r ON r.item_id = i.item_id AND r.status = 'pending'
            WHERE i.status = ?
        """
        parameters.append(TaskItemStatus.WAITING_METADATA.value)
        if task_id is not None:
            query += " AND i.task_id = ?"
            parameters.append(task_id)
        query += """
            UNION ALL
            SELECT i.*, 'metadata_correction' AS review_kind, r.review_id AS review_id
            FROM task_items i
            JOIN metadata_corrections r ON r.item_id = i.item_id AND r.status = 'pending'
            WHERE i.status = ?
        """
        parameters.append(TaskItemStatus.WAITING_METADATA_CORRECTION.value)
        if task_id is not None:
            query += " AND i.task_id = ?"
            parameters.append(task_id)
        query += " ORDER BY created_at, item_id LIMIT ?"
        parameters.append(limit)
        with self._lock:
            rows = self._connection.execute(query, tuple(parameters)).fetchall()
        return tuple(
            ManualIgnoreCandidate(
                self._item(row),
                ManualReviewKind(row["review_kind"]),
                row["review_id"],
            )
            for row in rows
        )

    def ignore_waiting_item(self, decision, item) -> None:
        review_tables = {
            ManualReviewKind.RECOGNITION: (
                "recognition_reviews",
                TaskItemStatus.WAITING_RECOGNITION,
            ),
            ManualReviewKind.METADATA: (
                "metadata_reviews",
                TaskItemStatus.WAITING_METADATA,
            ),
            ManualReviewKind.METADATA_CORRECTION: (
                "metadata_corrections",
                TaskItemStatus.WAITING_METADATA_CORRECTION,
            ),
        }
        table, waiting_status = review_tables[decision.review_kind]
        with self._lock, self._connection:
            cursor = self._connection.execute(
                f"""UPDATE {table} SET status='ignored', updated_at=?, decided_at=?, actor=?
                WHERE review_id=? AND item_id=? AND status='pending'""",
                (
                    decision.decided_at.isoformat(),
                    decision.decided_at.isoformat(),
                    decision.actor,
                    decision.review_id,
                    decision.item_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("manual review is not pending")
            cursor = self._connection.execute(
                """UPDATE task_items SET status=?, stage=?, updated_at=?
                WHERE item_id=? AND task_id=? AND status=?""",
                (
                    item.status.value,
                    item.stage,
                    item.updated_at.isoformat(),
                    item.item_id,
                    item.task_id,
                    waiting_status.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("TaskItem is not in the matching waiting state")
            self._connection.execute(
                "INSERT INTO manual_ignore_audit VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    decision.decision_id,
                    decision.task_id,
                    decision.item_id,
                    decision.review_kind.value,
                    decision.review_id,
                    decision.decided_at.isoformat(),
                    decision.actor,
                    decision.note,
                ),
            )

    def ignore_waiting_items(self, requests: tuple[ManualIgnoreBatchRequest, ...]) -> None:
        if not requests:
            raise ValueError("manual ignore batch must not be empty")
        review_tables = {
            ManualReviewKind.RECOGNITION: (
                "recognition_reviews",
                TaskItemStatus.WAITING_RECOGNITION,
            ),
            ManualReviewKind.METADATA: (
                "metadata_reviews",
                TaskItemStatus.WAITING_METADATA,
            ),
            ManualReviewKind.METADATA_CORRECTION: (
                "metadata_corrections",
                TaskItemStatus.WAITING_METADATA_CORRECTION,
            ),
        }
        with self._lock, self._connection:
            for request in requests:
                decision = request.decision
                item = request.item
                table, waiting_status = review_tables[decision.review_kind]
                cursor = self._connection.execute(
                    f"""UPDATE {table} SET status='ignored', updated_at=?, decided_at=?, actor=?
                    WHERE review_id=? AND item_id=? AND status='pending'""",
                    (
                        decision.decided_at.isoformat(),
                        decision.decided_at.isoformat(),
                        decision.actor,
                        decision.review_id,
                        decision.item_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValueError("manual review is not pending")
                cursor = self._connection.execute(
                    """UPDATE task_items SET status=?, stage=?, updated_at=?
                    WHERE item_id=? AND task_id=? AND status=?""",
                    (
                        item.status.value,
                        item.stage,
                        item.updated_at.isoformat(),
                        item.item_id,
                        item.task_id,
                        waiting_status.value,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValueError("TaskItem is not in the matching waiting state")
                self._connection.execute(
                    "INSERT INTO manual_ignore_audit VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        decision.decision_id,
                        decision.task_id,
                        decision.item_id,
                        decision.review_kind.value,
                        decision.review_id,
                        decision.decided_at.isoformat(),
                        decision.actor,
                        decision.note,
                    ),
                )

    def list_manual_ignore_audit(self, item_id):
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM manual_ignore_audit WHERE item_id=?
                ORDER BY decided_at, decision_id""",
                (item_id,),
            ).fetchall()
        return tuple(
            ManualIgnoreDecision(
                row["decision_id"],
                row["task_id"],
                row["item_id"],
                ManualReviewKind(row["review_kind"]),
                row["review_id"],
                datetime.fromisoformat(row["decided_at"]),
                row["actor"],
                row["note"],
            )
            for row in rows
        )

    def append_result(self, result: PersistentResultRecord) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO task_results (
                    result_id, task_id, item_id, source_storage_id, source_path,
                    destination_storage_id, destination_path, recognition_type, provider,
                    provider_id, metadata_policy_id, naming_policy_id, classification_policy_id,
                    organize_policy_id, operation, status, created_at, title, error,
                    completed_operations, attachment_count, retry_attempts, retry_category,
                    cleanup_status, cleanup_step_count, effect_certainty, uncertain_effects
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                self._result_values(result),
            )

    def append_evidence(self, evidence: PipelineEvidence) -> None:
        with self._lock, self._connection:
            self._append_evidence_locked(evidence)

    def _append_evidence_locked(self, evidence: PipelineEvidence) -> None:
        self._connection.execute(
            """
            INSERT OR REPLACE INTO pipeline_evidence (
                evidence_id, task_id, item_id, attempts, source_storage_id, source_path,
                captured_at, configuration_snapshot_id, configuration_snapshot_digest,
                outcome, document
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._evidence_values(evidence),
        )

    def complete_item_with_evidence(
        self,
        item: PersistentTaskItem,
        result: PersistentResultRecord,
        evidence: PipelineEvidence | None,
    ) -> None:
        """Atomically publish item outcome, result, and bounded evidence."""

        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO task_results (
                    result_id, task_id, item_id, source_storage_id, source_path,
                    destination_storage_id, destination_path, recognition_type, provider,
                    provider_id, metadata_policy_id, naming_policy_id, classification_policy_id,
                    organize_policy_id, operation, status, created_at, title, error,
                    completed_operations, attachment_count, retry_attempts, retry_category,
                    cleanup_status, cleanup_step_count, effect_certainty, uncertain_effects
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                self._result_values(result),
            )
            self._connection.execute(
                """
                INSERT INTO task_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET
                    status=excluded.status, stage=excluded.stage, attempts=excluded.attempts,
                    updated_at=excluded.updated_at, plan_id=excluded.plan_id,
                    destination_storage_id=excluded.destination_storage_id,
                    destination_path=excluded.destination_path,
                    execution_status=excluded.execution_status, error=excluded.error
                """,
                self._item_values(item),
            )
            if evidence is not None:
                self._connection.execute(
                    """
                    INSERT OR REPLACE INTO pipeline_evidence (
                        evidence_id, task_id, item_id, attempts, source_storage_id, source_path,
                        captured_at, configuration_snapshot_id, configuration_snapshot_digest,
                        outcome, document
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    self._evidence_values(evidence),
                )

    def list_evidence_for_item(
        self, item_id: str, *, limit: int = 32
    ) -> tuple[PipelineEvidence, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("item evidence limit must be between 1 and 100")
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM pipeline_evidence WHERE item_id=?
                ORDER BY captured_at DESC, evidence_id DESC LIMIT ?""",
                (item_id, limit),
            ).fetchall()
        return tuple(self._evidence(row) for row in rows)

    def list_evidence_for_source(
        self, storage_id: str, path: str, *, limit: int = 32
    ) -> tuple[PipelineEvidence, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("source evidence limit must be between 1 and 100")
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM pipeline_evidence
                WHERE source_storage_id=? AND source_path=?
                ORDER BY captured_at DESC, evidence_id DESC LIMIT ?""",
                (storage_id, path, limit),
            ).fetchall()
        return tuple(self._evidence(row) for row in rows)

    def list_task_items_for_source(
        self, storage_id: str, path: str, *, limit: int = 32
    ) -> tuple[PersistentTaskItem, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("source item limit must be between 1 and 100")
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM task_items WHERE storage_id=? AND source_path=?
                ORDER BY updated_at DESC, item_id DESC LIMIT ?""",
                (storage_id, path, limit),
            ).fetchall()
        return tuple(self._item(row) for row in rows)

    def list_results_for_source(
        self, storage_id: str, path: str, *, limit: int = 32
    ) -> tuple[PersistentResultRecord, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("source result limit must be between 1 and 100")
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM task_results
                WHERE source_storage_id=? AND source_path=?
                ORDER BY created_at DESC, result_id DESC LIMIT ?""",
                (storage_id, path, limit),
            ).fetchall()
        return tuple(self._result(row) for row in rows)

    def list_results_for_item(
        self, item_id: str, *, limit: int = 32
    ) -> tuple[PersistentResultRecord, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("item result limit must be between 1 and 100")
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM task_results WHERE item_id=?
                ORDER BY created_at DESC, result_id DESC LIMIT ?""",
                (item_id, limit),
            ).fetchall()
        return tuple(self._result(row) for row in rows)

    def get_processing_checkpoint_context(
        self, item_id: str, *, result_limit: int = 32, audit_limit: int = 64
    ) -> ProcessingCheckpointContext | None:
        """Read one checkpoint context from a single SQLite snapshot."""
        with self._lock:
            self._connection.execute("BEGIN")
            try:
                context = self._get_processing_checkpoint_context_locked(
                    item_id, result_limit=result_limit, audit_limit=audit_limit
                )
            except BaseException:
                self._connection.rollback()
                raise
            self._connection.commit()
            return context

    def _get_processing_checkpoint_context_locked(
        self, item_id: str, *, result_limit: int = 32, audit_limit: int = 64
    ) -> ProcessingCheckpointContext | None:
        """Read one TaskItem and all bounded recovery evidence under one repository lock."""
        if (
            isinstance(result_limit, bool)
            or not isinstance(result_limit, int)
            or not 1 <= result_limit <= 100
        ):
            raise ValueError("checkpoint result limit must be between 1 and 100")
        if (
            isinstance(audit_limit, bool)
            or not isinstance(audit_limit, int)
            or not 1 <= audit_limit <= 200
        ):
            raise ValueError("checkpoint audit limit must be between 1 and 200")
        with self._lock:
            row = self._connection.execute(
                """SELECT i.*, t.command AS task_command, t.status AS task_status,
                    t.execute_authorized AS task_execute_authorized,
                    t.created_at AS task_created_at,
                    t.updated_at AS task_updated_at, t.started_at AS task_started_at,
                    t.completed_at AS task_completed_at, t.total_items AS task_total_items,
                    t.completed_items AS task_completed_items, t.failed_items AS task_failed_items,
                    t.error AS task_error, t.pause_requested AS task_pause_requested,
                    t.scope_path AS task_scope_path, t.item_limit AS task_item_limit,
                    t.configuration_snapshot_id AS task_configuration_snapshot_id,
                    t.configuration_snapshot_digest AS task_configuration_snapshot_digest
                FROM task_items i JOIN tasks t ON t.task_id=i.task_id WHERE i.item_id=?""",
                (item_id,),
            ).fetchone()
            if row is None:
                return None
            task = PersistentTask(
                row["task_id"],
                row["task_command"],
                PersistentTaskStatus(row["task_status"]),
                bool(row["task_execute_authorized"]),
                datetime.fromisoformat(row["task_created_at"]),
                datetime.fromisoformat(row["task_updated_at"]),
                datetime.fromisoformat(row["task_started_at"]) if row["task_started_at"] else None,
                datetime.fromisoformat(row["task_completed_at"])
                if row["task_completed_at"]
                else None,
                row["task_total_items"],
                row["task_completed_items"],
                row["task_failed_items"],
                row["task_error"],
                bool(row["task_pause_requested"]),
                row["task_scope_path"],
                row["task_item_limit"],
                row["task_configuration_snapshot_id"],
                row["task_configuration_snapshot_digest"],
            )
            item = self._item(row)
            result_rows = self._connection.execute(
                """SELECT * FROM task_results WHERE item_id=?
                ORDER BY created_at DESC, result_id DESC LIMIT ?""",
                (item_id, result_limit),
            ).fetchall()
            results = tuple(self._result(value) for value in result_rows)

            blockers: list[CheckpointBlocker] = []
            blocker_queries = (
                ("recognition", "recognition_reviews", "review_id"),
                ("metadata", "metadata_reviews", "review_id"),
                ("metadata_correction", "metadata_corrections", "review_id"),
                ("classification", "classification_reviews", "review_id"),
                ("conflict", "conflict_confirmations", "confirmation_id"),
            )
            paths = {
                "recognition": "/api/v1/recognition-reviews/",
                "metadata": "/api/v1/metadata-reviews/",
                "metadata_correction": "/api/v1/metadata-corrections/",
                "classification": "/api/v1/classification-reviews/",
                "conflict": "/api/v1/confirmations/",
            }
            for kind, table, identifier_column in blocker_queries:
                blocker_row = self._connection.execute(
                    f"""SELECT {identifier_column} AS blocker_id, task_id, item_id, status
                    FROM {table} WHERE item_id=? ORDER BY updated_at DESC, {identifier_column} DESC
                    LIMIT 32""",
                    (item_id,),
                ).fetchall()
                blockers.extend(
                    CheckpointBlocker(
                        kind,
                        value["blocker_id"],
                        value["status"],
                        value["task_id"],
                        value["item_id"],
                        paths[kind] + value["blocker_id"],
                    )
                    for value in blocker_row
                )

            audits: list[CheckpointAudit] = []
            audit_queries = (
                ("task_retry", "task_retry_audit", "decision_id", "decided_at", "actor"),
                (
                    "recognition_retry",
                    "recognition_retry_audit",
                    "decision_id",
                    "decided_at",
                    "actor",
                ),
                ("manual_ignore", "manual_ignore_audit", "decision_id", "decided_at", "actor"),
            )
            for kind, table, identifier_column, timestamp_column, actor_column in audit_queries:
                audit_rows = self._connection.execute(
                    f"""SELECT {identifier_column} AS audit_id, {timestamp_column} AS occurred_at,
                    {actor_column} AS actor FROM {table} WHERE item_id=?
                    ORDER BY {timestamp_column}, {identifier_column} LIMIT ?""",
                    (item_id, audit_limit),
                ).fetchall()
                audits.extend(
                    CheckpointAudit(
                        value["audit_id"],
                        kind,
                        datetime.fromisoformat(value["occurred_at"]),
                        value["actor"],
                    )
                    for value in audit_rows
                )
            review_audit_queries = (
                (
                    "recognition_review",
                    "recognition_review_decision_audit",
                    "recognition_reviews",
                ),
                ("metadata_review", "metadata_review_decision_audit", "metadata_reviews"),
                (
                    "metadata_correction",
                    "metadata_correction_decision_audit",
                    "metadata_corrections",
                ),
                (
                    "classification_review",
                    "classification_review_decision_audit",
                    "classification_reviews",
                ),
            )
            for kind, audit_table, parent_table in review_audit_queries:
                audit_rows = self._connection.execute(
                    f"""SELECT a.audit_id AS audit_id, a.decided_at AS occurred_at,
                    a.actor AS actor FROM {audit_table} a JOIN {parent_table} p
                    ON p.review_id=a.review_id WHERE p.item_id=?
                    ORDER BY a.decided_at, a.audit_id LIMIT ?""",
                    (item_id, audit_limit),
                ).fetchall()
                audits.extend(
                    CheckpointAudit(
                        value["audit_id"],
                        kind,
                        datetime.fromisoformat(value["occurred_at"]),
                        value["actor"],
                    )
                    for value in audit_rows
                )
            audit_rows = self._connection.execute(
                """SELECT a.audit_id AS audit_id, a.decided_at AS occurred_at,
                a.actor AS actor FROM conflict_decision_audit a
                JOIN conflict_confirmations p ON p.confirmation_id=a.confirmation_id
                WHERE p.item_id=? ORDER BY a.decided_at, a.audit_id LIMIT ?""",
                (item_id, audit_limit),
            ).fetchall()
            audits.extend(
                CheckpointAudit(
                    value["audit_id"],
                    "conflict_decision",
                    datetime.fromisoformat(value["occurred_at"]),
                    value["actor"],
                )
                for value in audit_rows
            )
            recovery_rows = self._connection.execute(
                """SELECT * FROM recovery_requests WHERE item_id=?
                ORDER BY requested_at, request_id LIMIT ?""",
                (item_id, audit_limit),
            ).fetchall()
            recovery_requests = tuple(self._recovery_request(value) for value in recovery_rows)
            continuation_rows = self._connection.execute(
                """SELECT * FROM recovery_continuations WHERE source_item_id=?
                ORDER BY created_at DESC, continuation_id DESC LIMIT ?""",
                (item_id, 32),
            ).fetchall()
            recovery_continuations = tuple(
                self._recovery_continuation(value) for value in continuation_rows
            )
            audits.extend(
                CheckpointAudit(
                    value.request_id,
                    "recovery_request",
                    value.requested_at,
                    value.actor,
                )
                for value in recovery_requests
            )
            audits.sort(key=lambda value: (value.occurred_at, value.audit_id))
            return ProcessingCheckpointContext(
                task=task,
                item=item,
                results=results,
                blockers=tuple(blockers),
                audits=tuple(audits[-audit_limit:]),
                recovery_requests=recovery_requests,
                recovery_continuations=recovery_continuations,
            )

    def list_results(
        self,
        task_id: str,
        *,
        limit: int | None = None,
        after: tuple[datetime, str] | None = None,
        before: tuple[datetime, str] | None = None,
    ) -> tuple[PersistentResultRecord, ...]:
        if after is not None and before is not None:
            raise ValueError("after and before are mutually exclusive")
        query = "SELECT * FROM task_results WHERE task_id = ?"
        parameters: tuple[object, ...] = (task_id,)
        reverse = before is not None
        if after is not None:
            timestamp = after[0].isoformat()
            query += " AND (created_at > ? OR (created_at = ? AND result_id > ?))"
            parameters += (timestamp, timestamp, after[1])
        elif before is not None:
            timestamp = before[0].isoformat()
            query += " AND (created_at < ? OR (created_at = ? AND result_id < ?))"
            parameters += (timestamp, timestamp, before[1])
        query += (
            " ORDER BY created_at DESC, result_id DESC"
            if reverse
            else " ORDER BY created_at, result_id"
        )
        if limit is not None:
            query += " LIMIT ?"
            parameters += (limit,)
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
        values = tuple(self._result(row) for row in rows)
        return tuple(reversed(values)) if reverse else values

    def get_latest_result_for_source(
        self, storage_id: str, path: str
    ) -> PersistentResultRecord | None:
        with self._lock:
            row = self._connection.execute(
                """SELECT * FROM task_results
                WHERE source_storage_id = ? AND source_path = ?
                ORDER BY created_at DESC, result_id DESC LIMIT 1""",
                (storage_id, path),
            ).fetchone()
        return self._result(row) if row else None

    def list_file_review_links(
        self, storage_id: str, path: str, *, limit: int = 100
    ) -> tuple[FileReviewLink, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("file review link limit must be between 1 and 1000")
        query = """
            SELECT 'recognition' AS kind, review_id, status, task_id, item_id
            FROM recognition_reviews
            WHERE source_storage_id=? AND source_path=?
            UNION ALL
            SELECT 'metadata', review_id, status, task_id, item_id
            FROM metadata_reviews
            WHERE source_storage_id=? AND source_path=?
            UNION ALL
            SELECT 'metadata_correction', review_id, status, task_id, item_id
            FROM metadata_corrections
            WHERE source_storage_id=? AND source_path=?
            UNION ALL
            SELECT 'classification', review_id, status, task_id, item_id
            FROM classification_reviews
            WHERE source_storage_id=? AND source_path=?
            UNION ALL
            SELECT 'conflict', confirmation_id, status, task_id, item_id
            FROM conflict_confirmations
            WHERE source_storage_id=? AND source_path=?
            ORDER BY kind, review_id
            LIMIT ?
        """
        with self._lock:
            rows = self._connection.execute(
                query,
                (
                    storage_id,
                    path,
                    storage_id,
                    path,
                    storage_id,
                    path,
                    storage_id,
                    path,
                    storage_id,
                    path,
                    limit,
                ),
            ).fetchall()
        return tuple(
            FileReviewLink(
                row["kind"],
                row["review_id"],
                row["status"],
                row["task_id"],
                row["item_id"],
            )
            for row in rows
        )

    def create_confirmation(self, confirmation: ConflictConfirmation) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """INSERT INTO conflict_confirmations VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                self._confirmation_values(confirmation),
            )

    def create_confirmation_with_evidence(
        self,
        confirmation: ConflictConfirmation,
        item: PersistentTaskItem,
        evidence: PipelineEvidence | None,
    ) -> None:
        """Publish a conflict blocker, waiting item, and evidence atomically."""

        with self._lock, self._connection:
            if evidence is not None:
                self._append_evidence_locked(evidence)
            self._connection.execute(
                """INSERT INTO conflict_confirmations VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                self._confirmation_values(confirmation),
            )
            cursor = self._connection.execute(
                """UPDATE task_items SET status=?, stage=?, updated_at=?, plan_id=?,
                destination_storage_id=?, destination_path=?, execution_status=?, error=?
                WHERE item_id=? AND task_id=? AND status=?""",
                (
                    item.status.value,
                    item.stage,
                    item.updated_at.isoformat(),
                    item.plan_id,
                    item.destination_storage_id,
                    item.destination_path,
                    item.execution_status,
                    item.error,
                    item.item_id,
                    item.task_id,
                    TaskItemStatus.PROCESSING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("conflict TaskItem is not processing")

    def create_metadata_correction(self, review, item) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """INSERT INTO metadata_corrections VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    review.review_id,
                    review.task_id,
                    review.item_id,
                    review.source_storage_id,
                    review.source_path,
                    review.recognition_type,
                    review.metadata_policy_id,
                    review.provider_id,
                    review.original_query,
                    review.original_year,
                    review.original_media_type,
                    review.outcome,
                    review.status.value,
                    review.created_at.isoformat(),
                    review.updated_at.isoformat(),
                    review.corrected_query,
                    review.corrected_year,
                    review.corrected_media_type,
                    review.direct_provider_id,
                    review.decided_at.isoformat() if review.decided_at else None,
                    review.actor,
                ),
            )
            cursor = self._connection.execute(
                """UPDATE task_items SET status=?, stage=?, updated_at=?, error=NULL
                WHERE item_id=? AND status=?""",
                (
                    item.status.value,
                    item.stage,
                    item.updated_at.isoformat(),
                    item.item_id,
                    TaskItemStatus.PROCESSING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("metadata correction TaskItem is not processing")

    def create_metadata_correction_with_evidence(
        self, review, item: PersistentTaskItem, evidence: PipelineEvidence | None
    ) -> None:
        """Publish metadata-correction blocker, waiting item, and evidence atomically."""

        with self._lock, self._connection:
            if evidence is not None:
                self._append_evidence_locked(evidence)
            self._connection.execute(
                """INSERT INTO metadata_corrections VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    review.review_id,
                    review.task_id,
                    review.item_id,
                    review.source_storage_id,
                    review.source_path,
                    review.recognition_type,
                    review.metadata_policy_id,
                    review.provider_id,
                    review.original_query,
                    review.original_year,
                    review.original_media_type,
                    review.outcome,
                    review.status.value,
                    review.created_at.isoformat(),
                    review.updated_at.isoformat(),
                    review.corrected_query,
                    review.corrected_year,
                    review.corrected_media_type,
                    review.direct_provider_id,
                    review.decided_at.isoformat() if review.decided_at else None,
                    review.actor,
                ),
            )
            cursor = self._connection.execute(
                """UPDATE task_items SET status=?, stage=?, updated_at=?, error=NULL
                WHERE item_id=? AND task_id=? AND status=?""",
                (
                    item.status.value,
                    item.stage,
                    item.updated_at.isoformat(),
                    item.item_id,
                    item.task_id,
                    TaskItemStatus.PROCESSING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("metadata correction TaskItem is not processing")

    def get_metadata_correction(self, review_id):
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM metadata_corrections WHERE review_id=?", (review_id,)
            ).fetchone()
        return self._metadata_correction(row) if row else None

    def get_metadata_correction_for_item(self, item_id):
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM metadata_corrections WHERE item_id=?", (item_id,)
            ).fetchone()
        return self._metadata_correction(row) if row else None

    def list_metadata_corrections(self, *, limit=100):
        if not 1 <= limit <= 1000:
            raise ValueError("metadata correction limit must be between 1 and 1000")
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM metadata_corrections
                ORDER BY created_at DESC, review_id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return tuple(self._metadata_correction(row) for row in rows)

    def list_pending_metadata_corrections(self, *, limit=100, task_id=None):
        if not 1 <= limit <= 1000:
            raise ValueError("metadata correction limit must be between 1 and 1000")
        query = """
            SELECT c.* FROM metadata_corrections c
            JOIN task_items i ON i.item_id = c.item_id
            WHERE c.status = ? AND i.status = ?
        """
        parameters: tuple[object, ...] = (
            MetadataCorrectionStatus.PENDING.value,
            TaskItemStatus.WAITING_METADATA_CORRECTION.value,
        )
        if task_id is not None:
            query += " AND c.task_id = ?"
            parameters += (task_id,)
        query += " ORDER BY c.created_at, c.review_id LIMIT ?"
        parameters += (limit,)
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
        return tuple(self._metadata_correction(row) for row in rows)

    def resolve_metadata_correction(self, review, audit, item) -> None:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """UPDATE metadata_corrections SET status=?, updated_at=?, corrected_query=?,
                corrected_year=?, corrected_media_type=?, direct_provider_id=?,
                decided_at=?, actor=?
                WHERE review_id=? AND status=?""",
                (
                    review.status.value,
                    review.updated_at.isoformat(),
                    review.corrected_query,
                    review.corrected_year,
                    review.corrected_media_type,
                    review.direct_provider_id,
                    review.decided_at.isoformat(),
                    review.actor,
                    review.review_id,
                    MetadataCorrectionStatus.PENDING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("metadata correction is not pending")
            cursor = self._connection.execute(
                """UPDATE task_items SET status=?, stage=?, updated_at=?, error=NULL
                WHERE item_id=? AND status=?""",
                (
                    item.status.value,
                    item.stage,
                    item.updated_at.isoformat(),
                    item.item_id,
                    TaskItemStatus.WAITING_METADATA_CORRECTION.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("TaskItem is not waiting for metadata correction")
            self._connection.execute(
                """INSERT INTO metadata_correction_decision_audit
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    audit.audit_id,
                    audit.review_id,
                    audit.corrected_query,
                    audit.corrected_year,
                    audit.corrected_media_type,
                    audit.direct_provider_id,
                    audit.decided_at.isoformat(),
                    audit.actor,
                    audit.note,
                ),
            )

    def resolve_metadata_corrections_batch(
        self, requests: tuple[MetadataCorrectionBatchResolveRequest, ...]
    ) -> None:
        if not requests:
            raise ValueError("metadata correction resolve batch must not be empty")
        with self._lock, self._connection:
            for request in requests:
                review = request.review
                audit = request.audit
                item = request.item
                cursor = self._connection.execute(
                    """UPDATE metadata_corrections SET status=?, updated_at=?, corrected_query=?,
                    corrected_year=?, corrected_media_type=?, direct_provider_id=?,
                    decided_at=?, actor=?
                    WHERE review_id=? AND item_id=? AND status=?""",
                    (
                        review.status.value,
                        review.updated_at.isoformat(),
                        review.corrected_query,
                        review.corrected_year,
                        review.corrected_media_type,
                        review.direct_provider_id,
                        review.decided_at.isoformat(),
                        review.actor,
                        review.review_id,
                        review.item_id,
                        MetadataCorrectionStatus.PENDING.value,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValueError("metadata correction is not pending")
                cursor = self._connection.execute(
                    """UPDATE task_items SET status=?, stage=?, updated_at=?, error=NULL
                    WHERE item_id=? AND task_id=? AND status=?""",
                    (
                        item.status.value,
                        item.stage,
                        item.updated_at.isoformat(),
                        item.item_id,
                        item.task_id,
                        TaskItemStatus.WAITING_METADATA_CORRECTION.value,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValueError("TaskItem is not waiting for metadata correction")
                self._connection.execute(
                    """INSERT INTO metadata_correction_decision_audit
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        audit.audit_id,
                        audit.review_id,
                        audit.corrected_query,
                        audit.corrected_year,
                        audit.corrected_media_type,
                        audit.direct_provider_id,
                        audit.decided_at.isoformat(),
                        audit.actor,
                        audit.note,
                    ),
                )

    def list_metadata_correction_audit(self, review_id):
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM metadata_correction_decision_audit WHERE review_id=?
                ORDER BY decided_at, audit_id""",
                (review_id,),
            ).fetchall()
        return tuple(
            MetadataCorrectionDecisionAudit(
                row["audit_id"],
                row["review_id"],
                row["corrected_query"],
                row["corrected_year"],
                row["corrected_media_type"],
                row["direct_provider_id"],
                datetime.fromisoformat(row["decided_at"]),
                row["actor"],
                row["note"],
            )
            for row in rows
        )

    def get_metadata_correction_continuation_for_review(
        self, review_id: str
    ) -> MetadataCorrectionContinuation | None:
        with self._lock:
            row = self._connection.execute(
                """SELECT * FROM metadata_correction_continuations WHERE review_id=?
                ORDER BY created_at DESC, continuation_id DESC LIMIT 1""",
                (review_id,),
            ).fetchone()
        return self._metadata_correction_continuation(row) if row else None

    def get_metadata_correction_continuation_for_job(
        self, job_id: str
    ) -> MetadataCorrectionContinuation | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM metadata_correction_continuations WHERE job_id=?", (job_id,)
            ).fetchone()
        return self._metadata_correction_continuation(row) if row else None

    def admit_metadata_correction_continuation(
        self,
        job: AutomationJob,
        continuation: MetadataCorrectionContinuation,
        *,
        maximum_active_jobs: int,
    ) -> tuple[MetadataCorrectionContinuation, bool]:
        if (
            isinstance(maximum_active_jobs, bool)
            or not isinstance(maximum_active_jobs, int)
            or not 1 <= maximum_active_jobs <= 10_000
        ):
            raise ValueError("maximum active Jobs must be between 1 and 10000")
        if (
            job.command is not AutomationCommand.FILE_METADATA_CORRECTION
            or job.status is not AutomationJobStatus.PENDING
            or job.limit != 1
            or job.execute_authorized
            or job.task_id is not None
            or job.schedule_id is not None
            or job.claim_token is not None
            or job.cancellation_requested
            or not job.configuration_snapshot_id
            or not job.configuration_snapshot_digest
        ):
            raise ValueError("metadata correction continuation Job identity is invalid")
        if (
            continuation.status is not MetadataCorrectionContinuationStatus.QUEUED
            or continuation.job_id != job.job_id
            or continuation.configuration_snapshot_id != job.configuration_snapshot_id
            or continuation.configuration_snapshot_digest != job.configuration_snapshot_digest
            or continuation.new_task_id is not None
            or continuation.new_result_id is not None
            or continuation.started_at is not None
            or continuation.completed_at is not None
            or continuation.error is not None
            or continuation.recovery is not None
        ):
            raise ValueError("metadata correction continuation identity is invalid")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                source = self._connection.execute(
                    """SELECT m.status AS review_status,
                    m.source_storage_id AS review_storage_id,
                    m.source_path AS review_source_path,
                    i.task_id AS item_task_id, i.storage_id AS item_storage_id,
                    i.source_path AS item_source_path, i.status AS item_status,
                    t.configuration_snapshot_id, t.configuration_snapshot_digest
                    FROM metadata_corrections m
                    JOIN task_items i ON i.item_id=m.item_id
                    JOIN tasks t ON t.task_id=m.task_id
                    WHERE m.review_id=? AND m.task_id=? AND m.item_id=?""",
                    (
                        continuation.review_id,
                        continuation.source_task_id,
                        continuation.source_item_id,
                    ),
                ).fetchone()
                if (
                    source is None
                    or source["review_status"] != MetadataCorrectionStatus.RESOLVED.value
                    or source["item_task_id"] != continuation.source_task_id
                    or source["item_status"] != TaskItemStatus.PENDING.value
                    or source["configuration_snapshot_id"] != continuation.configuration_snapshot_id
                    or source["configuration_snapshot_digest"]
                    != continuation.configuration_snapshot_digest
                    or source["review_storage_id"] != source["item_storage_id"]
                    or source["review_source_path"] != source["item_source_path"]
                ):
                    raise ValueError(
                        "metadata correction continuation source linkage or eligibility changed"
                    )
                row = self._connection.execute(
                    """SELECT * FROM metadata_correction_continuations
                   WHERE review_id=? AND status IN (?, ?)
                   ORDER BY created_at DESC, continuation_id DESC LIMIT 1""",
                    (
                        continuation.review_id,
                        MetadataCorrectionContinuationStatus.QUEUED.value,
                        MetadataCorrectionContinuationStatus.RUNNING.value,
                    ),
                ).fetchone()
                if row is not None:
                    self._connection.commit()
                    return self._metadata_correction_continuation(row), False
                if not self._has_job_capacity(maximum_active_jobs):
                    self._connection.rollback()
                    raise AutomationQueueFull(
                        f"automation queue reached configured active Job limit "
                        f"{maximum_active_jobs}"
                    )
                self._insert_job(job)
                self._connection.execute(
                    """INSERT INTO metadata_correction_continuations
                    (continuation_id, file_id, review_id, source_task_id, source_item_id,
                     configuration_snapshot_id, configuration_snapshot_digest,
                     correction_version, status, created_at, updated_at, actor, job_id,
                     new_task_id, new_result_id, started_at, completed_at, error, recovery)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    self._metadata_correction_continuation_values(continuation),
                )
                self._connection.commit()
                return continuation, True
            except Exception:
                self._connection.rollback()
                raise

    def mark_metadata_correction_continuation_running(
        self, job_id: str, now: datetime | None = None
    ) -> MetadataCorrectionContinuation:
        timestamp = now or datetime.now(UTC)
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """UPDATE metadata_correction_continuations
                SET status=?, updated_at=?, started_at=COALESCE(started_at, ?)
                WHERE job_id=? AND status=?""",
                (
                    MetadataCorrectionContinuationStatus.RUNNING.value,
                    timestamp.isoformat(),
                    timestamp.isoformat(),
                    job_id,
                    MetadataCorrectionContinuationStatus.QUEUED.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("metadata correction continuation is not queued")
        return self.require_metadata_correction_continuation_by_job(job_id)

    def bind_metadata_correction_continuation_task(
        self, job_id: str, task_id: str
    ) -> MetadataCorrectionContinuation:
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("continuation Task ID is required")
        with self._lock, self._connection:
            task = self._connection.execute(
                "SELECT task_id FROM tasks WHERE task_id=?", (task_id,)
            ).fetchone()
            if task is None:
                raise LookupError(f"continuation Task {task_id!r} was not found")
            cursor = self._connection.execute(
                """UPDATE metadata_correction_continuations
                SET updated_at=?, new_task_id=?
                WHERE job_id=? AND status=? AND new_task_id IS NULL""",
                (
                    datetime.now(UTC).isoformat(),
                    task_id,
                    job_id,
                    MetadataCorrectionContinuationStatus.RUNNING.value,
                ),
            )
            if cursor.rowcount != 1:
                continuation = self.get_metadata_correction_continuation_for_job(job_id)
                if continuation is None:
                    raise LookupError(
                        f"metadata correction continuation for Job {job_id!r} was not found"
                    )
                raise ValueError("metadata correction continuation Task is already bound")
        return self.require_metadata_correction_continuation_by_job(job_id)

    def complete_metadata_correction_continuation(
        self,
        job_id: str,
        *,
        new_task_id: str | None = None,
        new_result_id: str | None = None,
        success: bool,
        error: str | None = None,
        recovery: str | None = None,
        now: datetime | None = None,
    ) -> MetadataCorrectionContinuation:
        timestamp = now or datetime.now(UTC)
        status = (
            MetadataCorrectionContinuationStatus.COMPLETED
            if success
            else MetadataCorrectionContinuationStatus.FAILED
        )
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """UPDATE metadata_correction_continuations
                SET status=?, updated_at=?, new_task_id=?, new_result_id=?, completed_at=?,
                    error=?, recovery=?
                WHERE job_id=? AND status=?""",
                (
                    status.value,
                    timestamp.isoformat(),
                    new_task_id,
                    new_result_id,
                    timestamp.isoformat(),
                    error,
                    recovery,
                    job_id,
                    MetadataCorrectionContinuationStatus.RUNNING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("metadata correction continuation is not running")
        return self.require_metadata_correction_continuation_by_job(job_id)

    def fail_queued_metadata_correction_continuation(
        self,
        job_id: str,
        *,
        error: str,
        recovery: str,
        now: datetime | None = None,
    ) -> MetadataCorrectionContinuation:
        timestamp = now or datetime.now(UTC)
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """UPDATE metadata_correction_continuations
                SET status=?, updated_at=?, completed_at=?, error=?, recovery=?
                WHERE job_id=? AND status=?""",
                (
                    MetadataCorrectionContinuationStatus.FAILED.value,
                    timestamp.isoformat(),
                    timestamp.isoformat(),
                    error,
                    recovery,
                    job_id,
                    MetadataCorrectionContinuationStatus.QUEUED.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("metadata correction continuation is not queued")
        return self.require_metadata_correction_continuation_by_job(job_id)

    def cancel_metadata_correction_continuation(
        self, job_id: str, *, now: datetime | None = None
    ) -> MetadataCorrectionContinuation:
        timestamp = now or datetime.now(UTC)
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """UPDATE metadata_correction_continuations
                SET status=?, updated_at=?, completed_at=?, error=?, recovery=?
                WHERE job_id=? AND status IN (?, ?)""",
                (
                    MetadataCorrectionContinuationStatus.CANCELLED.value,
                    timestamp.isoformat(),
                    timestamp.isoformat(),
                    "continuation Job was cancelled before completion",
                    "refresh the File detail and explicitly continue this correction again",
                    job_id,
                    MetadataCorrectionContinuationStatus.QUEUED.value,
                    MetadataCorrectionContinuationStatus.RUNNING.value,
                ),
            )
            if cursor.rowcount != 1:
                continuation = self.get_metadata_correction_continuation_for_job(job_id)
                if continuation is None:
                    raise LookupError(
                        f"metadata correction continuation for Job {job_id!r} was not found"
                    )
                if continuation.status is MetadataCorrectionContinuationStatus.CANCELLED:
                    return continuation
                raise ValueError("metadata correction continuation is not cancellable")
        return self.require_metadata_correction_continuation_by_job(job_id)

    def require_metadata_correction_continuation_by_job(
        self, job_id: str
    ) -> MetadataCorrectionContinuation:
        continuation = self.get_metadata_correction_continuation_for_job(job_id)
        if continuation is None:
            raise LookupError(f"metadata correction continuation for Job {job_id!r} was not found")
        return continuation

    def create_recognition_review(self, review, choices, item) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """INSERT INTO recognition_reviews VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    review.review_id,
                    review.task_id,
                    review.item_id,
                    review.source_storage_id,
                    review.source_path,
                    review.status.value,
                    review.created_at.isoformat(),
                    review.updated_at.isoformat(),
                    review.selected_recognition_type,
                    review.decided_at.isoformat() if review.decided_at else None,
                    review.actor,
                ),
            )
            self._connection.executemany(
                "INSERT INTO recognition_review_choices VALUES (?, ?, ?, ?)",
                tuple(
                    (value.review_id, value.recognition_type_id, value.name, value.description)
                    for value in choices
                ),
            )
            cursor = self._connection.execute(
                """UPDATE task_items SET status=?, stage=?, updated_at=?, error=NULL
                WHERE item_id=? AND status=?""",
                (
                    item.status.value,
                    item.stage,
                    item.updated_at.isoformat(),
                    item.item_id,
                    TaskItemStatus.PROCESSING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("recognition review TaskItem is not processing")

    def create_recognition_review_with_evidence(
        self, review, choices, item: PersistentTaskItem, evidence: PipelineEvidence | None
    ) -> None:
        """Publish recognition blocker, waiting item, and evidence atomically."""

        with self._lock, self._connection:
            if evidence is not None:
                self._append_evidence_locked(evidence)
            self._connection.execute(
                """INSERT INTO recognition_reviews VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    review.review_id,
                    review.task_id,
                    review.item_id,
                    review.source_storage_id,
                    review.source_path,
                    review.status.value,
                    review.created_at.isoformat(),
                    review.updated_at.isoformat(),
                    review.selected_recognition_type,
                    review.decided_at.isoformat() if review.decided_at else None,
                    review.actor,
                ),
            )
            self._connection.executemany(
                "INSERT INTO recognition_review_choices VALUES (?, ?, ?, ?)",
                tuple(
                    (value.review_id, value.recognition_type_id, value.name, value.description)
                    for value in choices
                ),
            )
            cursor = self._connection.execute(
                """UPDATE task_items SET status=?, stage=?, updated_at=?, error=NULL
                WHERE item_id=? AND task_id=? AND status=?""",
                (
                    item.status.value,
                    item.stage,
                    item.updated_at.isoformat(),
                    item.item_id,
                    item.task_id,
                    TaskItemStatus.PROCESSING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("recognition review TaskItem is not processing")

    def get_recognition_review(self, review_id):
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM recognition_reviews WHERE review_id=?", (review_id,)
            ).fetchone()
        return self._recognition_review(row) if row else None

    def get_recognition_review_for_item(self, item_id):
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM recognition_reviews WHERE item_id=?", (item_id,)
            ).fetchone()
        return self._recognition_review(row) if row else None

    def list_recognition_reviews(self, *, limit=100):
        if not 1 <= limit <= 1000:
            raise ValueError("recognition review limit must be between 1 and 1000")
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM recognition_reviews
                ORDER BY created_at DESC, review_id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return tuple(self._recognition_review(row) for row in rows)

    def list_pending_recognition_reviews(self, *, limit=100, task_id=None):
        if not 1 <= limit <= 1000:
            raise ValueError("recognition review limit must be between 1 and 1000")
        query = """
            SELECT r.* FROM recognition_reviews r
            JOIN task_items i ON i.item_id = r.item_id
            WHERE r.status = ? AND i.status = ?
        """
        parameters: tuple[object, ...] = (
            RecognitionReviewStatus.PENDING.value,
            TaskItemStatus.WAITING_RECOGNITION.value,
        )
        if task_id is not None:
            query += " AND r.task_id = ?"
            parameters += (task_id,)
        query += " ORDER BY r.created_at, r.review_id LIMIT ?"
        parameters += (limit,)
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
        return tuple(self._recognition_review(row) for row in rows)

    def list_recognition_review_choices(self, review_id):
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM recognition_review_choices WHERE review_id=?
                ORDER BY recognition_type_id""",
                (review_id,),
            ).fetchall()
        return tuple(
            RecognitionReviewChoice(
                row["review_id"], row["recognition_type_id"], row["name"], row["description"]
            )
            for row in rows
        )

    def resolve_recognition_review(self, review, audit, item) -> None:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """UPDATE recognition_reviews SET status=?, updated_at=?,
                selected_recognition_type=?, decided_at=?, actor=?
                WHERE review_id=? AND status=?""",
                (
                    review.status.value,
                    review.updated_at.isoformat(),
                    review.selected_recognition_type,
                    review.decided_at.isoformat(),
                    review.actor,
                    review.review_id,
                    RecognitionReviewStatus.PENDING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("recognition review is not pending")
            cursor = self._connection.execute(
                """UPDATE task_items SET status=?, stage=?, updated_at=?, error=NULL
                WHERE item_id=? AND status=?""",
                (
                    item.status.value,
                    item.stage,
                    item.updated_at.isoformat(),
                    item.item_id,
                    TaskItemStatus.WAITING_RECOGNITION.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("recognition review TaskItem is not waiting for recognition")
            self._connection.execute(
                "INSERT INTO recognition_review_decision_audit VALUES (?, ?, ?, ?, ?, ?)",
                (
                    audit.audit_id,
                    audit.review_id,
                    audit.recognition_type_id,
                    audit.decided_at.isoformat(),
                    audit.actor,
                    audit.note,
                ),
            )

    def resolve_recognition_reviews_batch(
        self, requests: tuple[RecognitionBatchResolveRequest, ...]
    ) -> None:
        if not requests:
            raise ValueError("recognition resolve batch must not be empty")
        with self._lock, self._connection:
            for request in requests:
                review = request.review
                audit = request.audit
                item = request.item
                cursor = self._connection.execute(
                    """UPDATE recognition_reviews SET status=?, updated_at=?,
                    selected_recognition_type=?, decided_at=?, actor=?
                    WHERE review_id=? AND item_id=? AND status=?""",
                    (
                        review.status.value,
                        review.updated_at.isoformat(),
                        review.selected_recognition_type,
                        review.decided_at.isoformat(),
                        review.actor,
                        review.review_id,
                        review.item_id,
                        RecognitionReviewStatus.PENDING.value,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValueError("recognition review is not pending")
                cursor = self._connection.execute(
                    """UPDATE task_items SET status=?, stage=?, updated_at=?, error=NULL
                    WHERE item_id=? AND task_id=? AND status=?""",
                    (
                        item.status.value,
                        item.stage,
                        item.updated_at.isoformat(),
                        item.item_id,
                        item.task_id,
                        TaskItemStatus.WAITING_RECOGNITION.value,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValueError("recognition review TaskItem is not waiting")
                self._connection.execute(
                    "INSERT INTO recognition_review_decision_audit VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        audit.audit_id,
                        audit.review_id,
                        audit.recognition_type_id,
                        audit.decided_at.isoformat(),
                        audit.actor,
                        audit.note,
                    ),
                )

    def list_recognition_review_audit(self, review_id):
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM recognition_review_decision_audit WHERE review_id=?
                ORDER BY decided_at, audit_id""",
                (review_id,),
            ).fetchall()
        return tuple(
            RecognitionReviewDecisionAudit(
                row["audit_id"],
                row["review_id"],
                row["recognition_type_id"],
                datetime.fromisoformat(row["decided_at"]),
                row["actor"],
                row["note"],
            )
            for row in rows
        )

    def request_recognition_retry(self, review, decision, item) -> None:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """UPDATE recognition_reviews SET status=?, updated_at=?, decided_at=?, actor=?
                WHERE review_id=? AND item_id=? AND status=?""",
                (
                    review.status.value,
                    review.updated_at.isoformat(),
                    review.decided_at.isoformat(),
                    review.actor,
                    review.review_id,
                    review.item_id,
                    RecognitionReviewStatus.PENDING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("recognition review is not pending")
            cursor = self._connection.execute(
                """UPDATE task_items SET status=?, stage=?, updated_at=?, error=NULL
                WHERE item_id=? AND task_id=? AND status=?""",
                (
                    item.status.value,
                    item.stage,
                    item.updated_at.isoformat(),
                    item.item_id,
                    item.task_id,
                    TaskItemStatus.WAITING_RECOGNITION.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("recognition retry TaskItem is not waiting")
            self._connection.execute(
                "INSERT INTO recognition_retry_audit VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    decision.decision_id,
                    decision.review_id,
                    decision.task_id,
                    decision.item_id,
                    decision.decided_at.isoformat(),
                    decision.actor,
                    decision.note,
                ),
            )

    def request_batch_recognition_retry(
        self, requests: tuple[RecognitionRetryBatchRequest, ...]
    ) -> None:
        if not requests:
            raise ValueError("recognition retry batch must not be empty")
        with self._lock, self._connection:
            for request in requests:
                review = request.review
                decision = request.decision
                item = request.item
                cursor = self._connection.execute(
                    """UPDATE recognition_reviews SET status=?, updated_at=?, decided_at=?, actor=?
                    WHERE review_id=? AND item_id=? AND status=?""",
                    (
                        review.status.value,
                        review.updated_at.isoformat(),
                        review.decided_at.isoformat(),
                        review.actor,
                        review.review_id,
                        review.item_id,
                        RecognitionReviewStatus.PENDING.value,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValueError("recognition review is not pending")
                cursor = self._connection.execute(
                    """UPDATE task_items SET status=?, stage=?, updated_at=?, error=NULL
                    WHERE item_id=? AND task_id=? AND status=?""",
                    (
                        item.status.value,
                        item.stage,
                        item.updated_at.isoformat(),
                        item.item_id,
                        item.task_id,
                        TaskItemStatus.WAITING_RECOGNITION.value,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValueError("recognition retry TaskItem is not waiting")
                self._connection.execute(
                    "INSERT INTO recognition_retry_audit VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        decision.decision_id,
                        decision.review_id,
                        decision.task_id,
                        decision.item_id,
                        decision.decided_at.isoformat(),
                        decision.actor,
                        decision.note,
                    ),
                )

    def list_recognition_retry_audit(self, review_id):
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM recognition_retry_audit WHERE review_id=?
                ORDER BY decided_at, decision_id""",
                (review_id,),
            ).fetchall()
        return tuple(
            RecognitionRetryDecision(
                row["decision_id"],
                row["review_id"],
                row["task_id"],
                row["item_id"],
                datetime.fromisoformat(row["decided_at"]),
                row["actor"],
                row["note"],
            )
            for row in rows
        )

    def create_metadata_review(
        self,
        review: MetadataReview,
        candidates: tuple[MetadataReviewCandidate, ...],
        item: PersistentTaskItem,
    ) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """INSERT INTO metadata_reviews
                (review_id, task_id, item_id, source_storage_id, source_path, recognition_type,
                metadata_policy_id, query, outcome, status, created_at, updated_at) VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    review.review_id,
                    review.task_id,
                    review.item_id,
                    review.source_storage_id,
                    review.source_path,
                    review.recognition_type,
                    review.metadata_policy_id,
                    review.query,
                    review.outcome,
                    review.status.value,
                    review.created_at.isoformat(),
                    review.updated_at.isoformat(),
                ),
            )
            self._connection.executemany(
                """INSERT INTO metadata_review_candidates VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    (
                        value.review_id,
                        value.rank,
                        value.provider,
                        value.provider_id,
                        value.media_type,
                        value.title,
                        value.original_title,
                        value.canonical_year,
                        value.regional_year,
                        value.total_score,
                        value.matched_provider_title,
                        value.matched_title_source,
                        json.dumps(
                            [
                                {
                                    "name": component.name,
                                    "score": component.score,
                                    "reason": component.reason,
                                }
                                for component in value.score_components
                            ],
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    )
                    for value in candidates
                ),
            )
            cursor = self._connection.execute(
                """UPDATE task_items SET status=?, stage=?, updated_at=?, error=NULL
                WHERE item_id=? AND status=?""",
                (
                    item.status.value,
                    item.stage,
                    item.updated_at.isoformat(),
                    item.item_id,
                    TaskItemStatus.PROCESSING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("metadata review TaskItem is not processing")

    def create_metadata_review_with_evidence(
        self,
        review: MetadataReview,
        candidates: tuple[MetadataReviewCandidate, ...],
        item: PersistentTaskItem,
        evidence: PipelineEvidence | None,
    ) -> None:
        """Publish metadata blocker, candidates, waiting item, and evidence atomically."""

        with self._lock, self._connection:
            if evidence is not None:
                self._append_evidence_locked(evidence)
            self._connection.execute(
                """INSERT INTO metadata_reviews
                (review_id, task_id, item_id, source_storage_id, source_path, recognition_type,
                metadata_policy_id, query, outcome, status, created_at, updated_at) VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    review.review_id,
                    review.task_id,
                    review.item_id,
                    review.source_storage_id,
                    review.source_path,
                    review.recognition_type,
                    review.metadata_policy_id,
                    review.query,
                    review.outcome,
                    review.status.value,
                    review.created_at.isoformat(),
                    review.updated_at.isoformat(),
                ),
            )
            self._connection.executemany(
                """INSERT INTO metadata_review_candidates VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    (
                        value.review_id,
                        value.rank,
                        value.provider,
                        value.provider_id,
                        value.media_type,
                        value.title,
                        value.original_title,
                        value.canonical_year,
                        value.regional_year,
                        value.total_score,
                        value.matched_provider_title,
                        value.matched_title_source,
                        json.dumps(
                            [
                                {
                                    "name": component.name,
                                    "score": component.score,
                                    "reason": component.reason,
                                }
                                for component in value.score_components
                            ],
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    )
                    for value in candidates
                ),
            )
            cursor = self._connection.execute(
                """UPDATE task_items SET status=?, stage=?, updated_at=?, error=NULL
                WHERE item_id=? AND task_id=? AND status=?""",
                (
                    item.status.value,
                    item.stage,
                    item.updated_at.isoformat(),
                    item.item_id,
                    item.task_id,
                    TaskItemStatus.PROCESSING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("metadata review TaskItem is not processing")

    def get_metadata_review(self, review_id: str) -> MetadataReview | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM metadata_reviews WHERE review_id=?", (review_id,)
            ).fetchone()
        return self._metadata_review(row) if row else None

    def get_metadata_review_for_item(self, item_id: str) -> MetadataReview | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM metadata_reviews WHERE item_id=?", (item_id,)
            ).fetchone()
        return self._metadata_review(row) if row else None

    def list_metadata_reviews(self, *, limit: int = 100) -> tuple[MetadataReview, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 1000:
            raise ValueError("metadata review limit must be between 1 and 1000")
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM metadata_reviews ORDER BY created_at DESC, review_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(self._metadata_review(row) for row in rows)

    def list_pending_metadata_reviews(self, *, limit=100, task_id=None):
        if not 1 <= limit <= 1000:
            raise ValueError("metadata review limit must be between 1 and 1000")
        query = """
            SELECT m.* FROM metadata_reviews m
            JOIN task_items i ON i.item_id = m.item_id
            WHERE m.status = ? AND i.status = ?
        """
        parameters: tuple[object, ...] = (
            MetadataReviewStatus.PENDING.value,
            TaskItemStatus.WAITING_METADATA.value,
        )
        if task_id is not None:
            query += " AND m.task_id = ?"
            parameters += (task_id,)
        query += " ORDER BY m.created_at, m.review_id LIMIT ?"
        parameters += (limit,)
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
        return tuple(self._metadata_review(row) for row in rows)

    def list_metadata_review_candidates(
        self, review_id: str
    ) -> tuple[MetadataReviewCandidate, ...]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM metadata_review_candidates WHERE review_id=? ORDER BY rank",
                (review_id,),
            ).fetchall()
        return tuple(self._metadata_review_candidate(row) for row in rows)

    def resolve_metadata_review(
        self,
        review: MetadataReview,
        audit: MetadataReviewDecisionAudit,
        item: PersistentTaskItem,
    ) -> None:
        if review.status is not MetadataReviewStatus.RESOLVED:
            raise ValueError("resolved metadata review status is required")
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """UPDATE metadata_reviews SET status=?, updated_at=?, selected_rank=?,
                selected_provider=?, selected_provider_id=?, selected_media_type=?, decided_at=?,
                actor=? WHERE review_id=? AND status=?""",
                (
                    review.status.value,
                    review.updated_at.isoformat(),
                    review.selected_rank,
                    review.selected_provider,
                    review.selected_provider_id,
                    review.selected_media_type,
                    review.decided_at.isoformat() if review.decided_at else None,
                    review.actor,
                    review.review_id,
                    MetadataReviewStatus.PENDING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("metadata review is not pending")
            cursor = self._connection.execute(
                """UPDATE task_items SET status=?, stage=?, updated_at=?, error=NULL
                WHERE item_id=? AND status=?""",
                (
                    item.status.value,
                    item.stage,
                    item.updated_at.isoformat(),
                    item.item_id,
                    TaskItemStatus.WAITING_METADATA.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("metadata review TaskItem is not waiting for metadata")
            self._connection.execute(
                "INSERT INTO metadata_review_decision_audit VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    audit.audit_id,
                    audit.review_id,
                    audit.selected_rank,
                    audit.provider,
                    audit.provider_id,
                    audit.media_type,
                    audit.decided_at.isoformat(),
                    audit.actor,
                    audit.note,
                ),
            )

    def resolve_metadata_reviews_batch(
        self, requests: tuple[MetadataReviewBatchResolveRequest, ...]
    ) -> None:
        if not requests:
            raise ValueError("metadata review resolve batch must not be empty")
        with self._lock, self._connection:
            for request in requests:
                review = request.review
                audit = request.audit
                item = request.item
                cursor = self._connection.execute(
                    """UPDATE metadata_reviews SET status=?, updated_at=?, selected_rank=?,
                    selected_provider=?, selected_provider_id=?, selected_media_type=?,
                    decided_at=?, actor=?
                    WHERE review_id=? AND item_id=? AND status=?""",
                    (
                        review.status.value,
                        review.updated_at.isoformat(),
                        review.selected_rank,
                        review.selected_provider,
                        review.selected_provider_id,
                        review.selected_media_type,
                        review.decided_at.isoformat(),
                        review.actor,
                        review.review_id,
                        review.item_id,
                        MetadataReviewStatus.PENDING.value,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValueError("metadata review is not pending")
                cursor = self._connection.execute(
                    """UPDATE task_items SET status=?, stage=?, updated_at=?, error=NULL
                    WHERE item_id=? AND task_id=? AND status=?""",
                    (
                        item.status.value,
                        item.stage,
                        item.updated_at.isoformat(),
                        item.item_id,
                        item.task_id,
                        TaskItemStatus.WAITING_METADATA.value,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValueError("metadata review TaskItem is not waiting for metadata")
                self._connection.execute(
                    "INSERT INTO metadata_review_decision_audit VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        audit.audit_id,
                        audit.review_id,
                        audit.selected_rank,
                        audit.provider,
                        audit.provider_id,
                        audit.media_type,
                        audit.decided_at.isoformat(),
                        audit.actor,
                        audit.note,
                    ),
                )

    def list_metadata_review_audit(self, review_id: str) -> tuple[MetadataReviewDecisionAudit, ...]:
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM metadata_review_decision_audit WHERE review_id=?
                ORDER BY decided_at, audit_id""",
                (review_id,),
            ).fetchall()
        return tuple(
            MetadataReviewDecisionAudit(
                row["audit_id"],
                row["review_id"],
                row["selected_rank"],
                row["provider"],
                row["provider_id"],
                row["media_type"],
                datetime.fromisoformat(row["decided_at"]),
                row["actor"],
                row["note"],
            )
            for row in rows
        )

    def create_classification_review(
        self,
        review: ClassificationReview,
        choices: tuple[ClassificationReviewChoice, ...],
        item: PersistentTaskItem,
    ) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """INSERT INTO classification_reviews
                (review_id, task_id, item_id, source_storage_id, source_path, recognition_type,
                classification_policy_id, provider, provider_id, media_type, title,
                canonical_year, status, created_at, updated_at) VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    review.review_id,
                    review.task_id,
                    review.item_id,
                    review.source_storage_id,
                    review.source_path,
                    review.recognition_type,
                    review.classification_policy_id,
                    review.provider,
                    review.provider_id,
                    review.media_type,
                    review.title,
                    review.canonical_year,
                    review.status.value,
                    review.created_at.isoformat(),
                    review.updated_at.isoformat(),
                ),
            )
            self._connection.executemany(
                "INSERT INTO classification_review_choices VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    (
                        value.review_id,
                        value.rank,
                        value.rule_id,
                        value.rule_name,
                        value.media_library_id,
                        value.relative_path,
                        value.priority,
                        value.description,
                    )
                    for value in choices
                ),
            )
            cursor = self._connection.execute(
                """UPDATE task_items SET status=?, stage=?, updated_at=?, error=NULL
                WHERE item_id=? AND status=?""",
                (
                    item.status.value,
                    item.stage,
                    item.updated_at.isoformat(),
                    item.item_id,
                    TaskItemStatus.PROCESSING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("classification review TaskItem is not processing")

    def create_classification_review_with_evidence(
        self,
        review: ClassificationReview,
        choices: tuple[ClassificationReviewChoice, ...],
        item: PersistentTaskItem,
        evidence: PipelineEvidence | None,
    ) -> None:
        """Publish classification blocker, choices, waiting item, and evidence atomically."""

        with self._lock, self._connection:
            if evidence is not None:
                self._append_evidence_locked(evidence)
            self._connection.execute(
                """INSERT INTO classification_reviews
                (review_id, task_id, item_id, source_storage_id, source_path, recognition_type,
                classification_policy_id, provider, provider_id, media_type, title,
                canonical_year, status, created_at, updated_at) VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    review.review_id,
                    review.task_id,
                    review.item_id,
                    review.source_storage_id,
                    review.source_path,
                    review.recognition_type,
                    review.classification_policy_id,
                    review.provider,
                    review.provider_id,
                    review.media_type,
                    review.title,
                    review.canonical_year,
                    review.status.value,
                    review.created_at.isoformat(),
                    review.updated_at.isoformat(),
                ),
            )
            self._connection.executemany(
                "INSERT INTO classification_review_choices VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    (
                        value.review_id,
                        value.rank,
                        value.rule_id,
                        value.rule_name,
                        value.media_library_id,
                        value.relative_path,
                        value.priority,
                        value.description,
                    )
                    for value in choices
                ),
            )
            cursor = self._connection.execute(
                """UPDATE task_items SET status=?, stage=?, updated_at=?, error=NULL
                WHERE item_id=? AND task_id=? AND status=?""",
                (
                    item.status.value,
                    item.stage,
                    item.updated_at.isoformat(),
                    item.item_id,
                    item.task_id,
                    TaskItemStatus.PROCESSING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("classification review TaskItem is not processing")

    def get_classification_review(self, review_id: str) -> ClassificationReview | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM classification_reviews WHERE review_id=?", (review_id,)
            ).fetchone()
        return self._classification_review(row) if row else None

    def get_classification_review_for_item(self, item_id: str) -> ClassificationReview | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM classification_reviews WHERE item_id=?", (item_id,)
            ).fetchone()
        return self._classification_review(row) if row else None

    def list_classification_reviews(self, *, limit: int = 100) -> tuple[ClassificationReview, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 1000:
            raise ValueError("classification review limit must be between 1 and 1000")
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM classification_reviews
                ORDER BY created_at DESC, review_id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return tuple(self._classification_review(row) for row in rows)

    def list_classification_review_choices(
        self, review_id: str
    ) -> tuple[ClassificationReviewChoice, ...]:
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM classification_review_choices WHERE review_id=?
                ORDER BY rank""",
                (review_id,),
            ).fetchall()
        return tuple(self._classification_review_choice(row) for row in rows)

    def resolve_classification_review(
        self,
        review: ClassificationReview,
        audit: ClassificationReviewDecisionAudit,
        item: PersistentTaskItem,
    ) -> None:
        if review.status is not ClassificationReviewStatus.RESOLVED:
            raise ValueError("resolved classification review status is required")
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """UPDATE classification_reviews SET status=?, updated_at=?, selected_rank=?,
                selected_rule_id=?, selected_media_library_id=?, selected_relative_path=?,
                decided_at=?, actor=? WHERE review_id=? AND status=?""",
                (
                    review.status.value,
                    review.updated_at.isoformat(),
                    review.selected_rank,
                    review.selected_rule_id,
                    review.selected_media_library_id,
                    review.selected_relative_path,
                    review.decided_at.isoformat() if review.decided_at else None,
                    review.actor,
                    review.review_id,
                    ClassificationReviewStatus.PENDING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("classification review is not pending")
            cursor = self._connection.execute(
                """UPDATE task_items SET status=?, stage=?, updated_at=?, error=NULL
                WHERE item_id=? AND status=?""",
                (
                    item.status.value,
                    item.stage,
                    item.updated_at.isoformat(),
                    item.item_id,
                    TaskItemStatus.WAITING_CLASSIFICATION.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("classification review TaskItem is not waiting")
            self._connection.execute(
                """INSERT INTO classification_review_decision_audit VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    audit.audit_id,
                    audit.review_id,
                    audit.selected_rank,
                    audit.rule_id,
                    audit.media_library_id,
                    audit.relative_path,
                    audit.decided_at.isoformat(),
                    audit.actor,
                    audit.note,
                ),
            )

    def list_classification_review_audit(
        self, review_id: str
    ) -> tuple[ClassificationReviewDecisionAudit, ...]:
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM classification_review_decision_audit WHERE review_id=?
                ORDER BY decided_at, audit_id""",
                (review_id,),
            ).fetchall()
        return tuple(
            ClassificationReviewDecisionAudit(
                row["audit_id"],
                row["review_id"],
                row["selected_rank"],
                row["rule_id"],
                row["media_library_id"],
                row["relative_path"],
                datetime.fromisoformat(row["decided_at"]),
                row["actor"],
                row["note"],
            )
            for row in rows
        )

    def get_confirmation(self, confirmation_id: str) -> ConflictConfirmation | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM conflict_confirmations WHERE confirmation_id=?",
                (confirmation_id,),
            ).fetchone()
        return self._confirmation(row) if row else None

    def list_confirmations(
        self, *, status: ConfirmationStatus | None = None, limit: int | None = None
    ) -> tuple[ConflictConfirmation, ...]:
        if limit is not None and (
            isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 1000
        ):
            raise ValueError("confirmation limit must be between 1 and 1000")
        query = "SELECT * FROM conflict_confirmations"
        parameters: tuple[object, ...] = ()
        if status is not None:
            query += " WHERE status=?"
            parameters = (status.value,)
        query += " ORDER BY created_at, confirmation_id"
        if limit is not None:
            query += " LIMIT ?"
            parameters += (limit,)
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
        return tuple(self._confirmation(row) for row in rows)

    def resolve_confirmation(
        self,
        confirmation: ConflictConfirmation,
        audit: ConflictDecisionAudit,
        item: PersistentTaskItem | None = None,
    ) -> None:
        if confirmation.status is not ConfirmationStatus.RESOLVED:
            raise ValueError("resolved confirmation status is required")
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """UPDATE conflict_confirmations SET status=?, updated_at=?,
                selected_strategy=?, proposed_destination_path=?, overwrite_authorized=?,
                actor=?, note=? WHERE confirmation_id=? AND status=?""",
                (
                    confirmation.status.value,
                    confirmation.updated_at.isoformat(),
                    confirmation.selected_strategy,
                    confirmation.proposed_destination_path,
                    int(confirmation.overwrite_authorized),
                    confirmation.actor,
                    confirmation.note,
                    confirmation.confirmation_id,
                    ConfirmationStatus.PENDING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("confirmation is not pending")
            if item is not None:
                cursor = self._connection.execute(
                    """UPDATE task_items SET status=?, stage=?, updated_at=?
                    WHERE item_id=? AND status=?""",
                    (
                        item.status.value,
                        item.stage,
                        item.updated_at.isoformat(),
                        item.item_id,
                        TaskItemStatus.WAITING_CONFIRM.value,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValueError("confirmation TaskItem is not waiting for confirmation")
            self._connection.execute(
                "INSERT INTO conflict_decision_audit VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    audit.audit_id,
                    audit.confirmation_id,
                    audit.strategy,
                    audit.decided_at.isoformat(),
                    int(audit.overwrite_authorized),
                    audit.actor,
                    audit.note,
                ),
            )

    def list_confirmation_audit(self, confirmation_id: str) -> tuple[ConflictDecisionAudit, ...]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM conflict_decision_audit WHERE confirmation_id=? ORDER BY decided_at",
                (confirmation_id,),
            ).fetchall()
        return tuple(
            ConflictDecisionAudit(
                row["audit_id"],
                row["confirmation_id"],
                row["strategy"],
                datetime.fromisoformat(row["decided_at"]),
                bool(row["overwrite_authorized"]),
                row["actor"],
                row["note"],
            )
            for row in rows
        )

    def create_job(self, job: AutomationJob) -> None:
        with self._lock, self._connection:
            self._insert_job(job)

    def admit_job(self, job: AutomationJob, maximum_active_jobs: int) -> bool:
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                if not self._has_job_capacity(maximum_active_jobs):
                    self._connection.rollback()
                    return False
                self._insert_job(job)
                self._connection.commit()
                return True
            except Exception:
                self._connection.rollback()
                raise

    def _has_job_capacity(self, maximum_active_jobs: int) -> bool:
        row = self._connection.execute(
            "SELECT COUNT(*) AS count FROM automation_jobs WHERE status IN (?, ?)",
            (AutomationJobStatus.PENDING.value, AutomationJobStatus.RUNNING.value),
        ).fetchone()
        return int(row["count"]) < maximum_active_jobs

    def get_job(self, job_id: str) -> AutomationJob | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM automation_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
        return self._job(row) if row else None

    def list_jobs(
        self,
        *,
        limit: int | None = None,
        after: tuple[datetime, str] | None = None,
        before: tuple[datetime, str] | None = None,
    ) -> tuple[AutomationJob, ...]:
        if after is not None and before is not None:
            raise ValueError("after and before are mutually exclusive")
        query = "SELECT * FROM automation_jobs"
        parameters: tuple[object, ...] = ()
        reverse = before is not None
        if after is not None:
            timestamp = after[0].isoformat()
            query += " WHERE (created_at < ? OR (created_at = ? AND job_id < ?))"
            parameters = (timestamp, timestamp, after[1])
        elif before is not None:
            timestamp = before[0].isoformat()
            query += " WHERE (created_at > ? OR (created_at = ? AND job_id > ?))"
            parameters = (timestamp, timestamp, before[1])
        query += (
            " ORDER BY created_at ASC, job_id ASC"
            if reverse
            else " ORDER BY created_at DESC, job_id DESC"
        )
        if limit is not None:
            query += " LIMIT ?"
            parameters += (limit,)
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
        values = tuple(self._job(row) for row in rows)
        return tuple(reversed(values)) if reverse else values

    def claim_next_job(self, now: datetime) -> AutomationJob | None:
        claim_token = secrets.token_urlsafe(32)
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT job_id FROM automation_jobs WHERE status=? "
                "ORDER BY created_at, job_id LIMIT 1",
                (AutomationJobStatus.PENDING.value,),
            ).fetchone()
            if row is None:
                return None
            cursor = self._connection.execute(
                "UPDATE automation_jobs SET status=?, updated_at=?, started_at=?, claim_token=? "
                "WHERE job_id=? AND status=?",
                (
                    AutomationJobStatus.RUNNING.value,
                    now.isoformat(),
                    now.isoformat(),
                    claim_token,
                    row["job_id"],
                    AutomationJobStatus.PENDING.value,
                ),
            )
            if cursor.rowcount != 1:
                return None
            claimed = self._connection.execute(
                "SELECT * FROM automation_jobs WHERE job_id=?", (row["job_id"],)
            ).fetchone()
        return self._job(claimed)

    def update_job(self, job: AutomationJob) -> None:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "UPDATE automation_jobs SET command=?, status=?, created_at=?, updated_at=?, "
                "limit_value=?, started_at=?, completed_at=?, task_id=?, error=?, "
                "cancellation_requested=?, schedule_id=?, execute_authorized=?, claim_token=?, "
                "configuration_snapshot_id=?, configuration_snapshot_digest=?, "
                "failure_category=?, failure_durable_state=?, failure_side_effects=?, "
                "failure_retry_safe=?, failure_next_action=? "
                "WHERE job_id=?",
                (*self._job_values(job)[1:], job.job_id),
            )
            if cursor.rowcount != 1:
                raise LookupError(f"automation job {job.job_id!r} was not found")

    def request_job_cancellation(self, job_id: str, now: datetime) -> AutomationJob:
        with self._lock, self._connection:
            existing_row = self._connection.execute(
                "SELECT command, status FROM automation_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if existing_row is None:
                raise LookupError(f"automation job {job_id!r} was not found")
            cursor = self._connection.execute(
                "UPDATE automation_jobs SET status=CASE WHEN status=? THEN ? ELSE status END, "
                "cancellation_requested=1, updated_at=?, "
                "completed_at=CASE WHEN status=? THEN ? ELSE completed_at END "
                "WHERE job_id=? AND status IN (?, ?)",
                (
                    AutomationJobStatus.PENDING.value,
                    AutomationJobStatus.CANCELLED.value,
                    now.isoformat(),
                    AutomationJobStatus.PENDING.value,
                    now.isoformat(),
                    job_id,
                    AutomationJobStatus.PENDING.value,
                    AutomationJobStatus.RUNNING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("only a pending or running automation job can be cancelled")
            if existing_row["command"] == AutomationCommand.FILE_METADATA_CORRECTION.value:
                self._connection.execute(
                    """UPDATE metadata_correction_continuations
                    SET status=?, updated_at=?, completed_at=?, error=?, recovery=?
                    WHERE job_id=? AND status IN (?, ?) AND
                          (status=? OR new_task_id IS NULL)""",
                    (
                        MetadataCorrectionContinuationStatus.CANCELLED.value,
                        now.isoformat(),
                        now.isoformat(),
                        "continuation Job was cancelled before completion",
                        "refresh the File detail and explicitly continue this correction again",
                        job_id,
                        MetadataCorrectionContinuationStatus.QUEUED.value,
                        MetadataCorrectionContinuationStatus.RUNNING.value,
                        MetadataCorrectionContinuationStatus.QUEUED.value,
                    ),
                )
            elif existing_row["command"] == AutomationCommand.RECOVERY_CONTINUATION.value:
                # A pending Job is terminally cancelled here, so its queued
                # continuation cannot remain active after the Worker loses it.
                cursor = self._connection.execute(
                    """UPDATE recovery_continuations
                    SET status=?, updated_at=?, completed_at=?, error=?, recovery=?
                    WHERE job_id=? AND status=?""",
                    (
                        RecoveryContinuationStatus.CANCELLED.value,
                        now.isoformat(),
                        now.isoformat(),
                        "recovery continuation Job was cancelled before completion",
                        "refresh the Task item checkpoint and explicitly continue again",
                        job_id,
                        RecoveryContinuationStatus.QUEUED.value,
                    ),
                )
                if cursor.rowcount == 1:
                    row = self._connection.execute(
                        "SELECT request_id FROM recovery_continuations WHERE job_id=?",
                        (job_id,),
                    ).fetchone()
                    if row is not None:
                        self._resolve_recovery_request_locked(
                            row["request_id"], RecoveryRequestStatus.CANCELLED, now
                        )
            row = self._connection.execute(
                "SELECT * FROM automation_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
        return self._job(row)

    def job_cancellation_requested(self, job_id: str) -> bool:
        with self._lock:
            row = self._connection.execute(
                "SELECT cancellation_requested FROM automation_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
        return bool(row and row["cancellation_requested"])

    def heartbeat_job(self, job_id: str, claim_token: str, now: datetime) -> bool:
        if not claim_token:
            raise AutomationClaimLost("automation Job claim ownership was lost")
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "UPDATE automation_jobs SET updated_at=? WHERE job_id=? AND status=? "
                "AND claim_token=?",
                (
                    now.isoformat(),
                    job_id,
                    AutomationJobStatus.RUNNING.value,
                    claim_token,
                ),
            )
            if cursor.rowcount != 1:
                raise AutomationClaimLost("automation Job claim ownership was lost")
            row = self._connection.execute(
                "SELECT cancellation_requested FROM automation_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
        return bool(row["cancellation_requested"])

    def complete_claimed_job(self, job: AutomationJob) -> bool:
        if not job.claim_token:
            raise AutomationClaimLost("automation Job claim ownership was lost")
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "UPDATE automation_jobs SET command=?, status=?, created_at=?, updated_at=?, "
                "limit_value=?, started_at=?, completed_at=?, task_id=?, error=?, "
                "cancellation_requested=?, schedule_id=?, execute_authorized=?, claim_token=NULL, "
                "configuration_snapshot_id=?, configuration_snapshot_digest=?, "
                "failure_category=?, failure_durable_state=?, failure_side_effects=?, "
                "failure_retry_safe=?, failure_next_action=? "
                "WHERE job_id=? AND status=? AND claim_token=?",
                (
                    *self._job_values(job)[1:13],
                    *self._job_values(job)[14:],
                    job.job_id,
                    AutomationJobStatus.RUNNING.value,
                    job.claim_token,
                ),
            )
        return cursor.rowcount == 1

    def list_stale_running_jobs(
        self, before: datetime, *, limit: int = 100
    ) -> tuple[AutomationJob, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 100:
            raise ValueError("stale job limit must be between 1 and 100")
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM automation_jobs WHERE status=? AND updated_at<? "
                "ORDER BY updated_at, job_id LIMIT ?",
                (AutomationJobStatus.RUNNING.value, before.isoformat(), limit),
            ).fetchall()
        return tuple(self._job(row) for row in rows)

    def requeue_stale_job(self, job_id: str, before: datetime, now: datetime) -> AutomationJob:
        with self._lock, self._connection:
            existing_row = self._connection.execute(
                "SELECT command FROM automation_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if existing_row is None:
                raise LookupError(f"automation job {job_id!r} was not found")
            cursor = self._connection.execute(
                "UPDATE automation_jobs SET status=?, updated_at=?, started_at=NULL, "
                "completed_at=NULL, task_id=NULL, error='explicitly requeued stale job', "
                "cancellation_requested=0, claim_token=NULL, failure_category=NULL, "
                "failure_durable_state=NULL, failure_side_effects=NULL, "
                "failure_retry_safe=NULL, failure_next_action=NULL "
                "WHERE job_id=? AND status=? AND updated_at<?",
                (
                    AutomationJobStatus.PENDING.value,
                    now.isoformat(),
                    job_id,
                    AutomationJobStatus.RUNNING.value,
                    before.isoformat(),
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("automation job is not stale and running")
            if existing_row["command"] == AutomationCommand.FILE_METADATA_CORRECTION.value:
                continuation = self._connection.execute(
                    """SELECT new_task_id FROM metadata_correction_continuations
                    WHERE job_id=? AND status=?""",
                    (job_id, MetadataCorrectionContinuationStatus.RUNNING.value),
                ).fetchone()
                if continuation is not None and continuation["new_task_id"] is None:
                    self._connection.execute(
                        """UPDATE metadata_correction_continuations
                        SET status=?, updated_at=?, started_at=NULL, completed_at=NULL,
                            error=NULL, recovery=NULL
                        WHERE job_id=? AND status=?""",
                        (
                            MetadataCorrectionContinuationStatus.QUEUED.value,
                            now.isoformat(),
                            job_id,
                            MetadataCorrectionContinuationStatus.RUNNING.value,
                        ),
                    )
                elif continuation is not None:
                    self._connection.execute(
                        """UPDATE metadata_correction_continuations
                        SET status=?, updated_at=?, completed_at=?, error=?, recovery=?
                        WHERE job_id=? AND status=?""",
                        (
                            MetadataCorrectionContinuationStatus.FAILED.value,
                            now.isoformat(),
                            now.isoformat(),
                            "stale continuation already has a linked Task",
                            "inspect the linked Task/Result before retrying this correction",
                            job_id,
                            MetadataCorrectionContinuationStatus.RUNNING.value,
                        ),
                    )
            row = self._connection.execute(
                "SELECT * FROM automation_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
        return self._job(row)

    def get_schedule_state(self, schedule_id: str) -> ScheduleState | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM automation_schedules WHERE schedule_id=?", (schedule_id,)
            ).fetchone()
        return self._schedule_state(row) if row else None

    def initialize_schedule_state(
        self, schedule_id: str, next_run_at: datetime, now: datetime
    ) -> ScheduleState:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT OR IGNORE INTO automation_schedules VALUES (?, ?, ?, NULL)",
                (schedule_id, next_run_at.isoformat(), now.isoformat()),
            )
            row = self._connection.execute(
                "SELECT * FROM automation_schedules WHERE schedule_id=?",
                (schedule_id,),
            ).fetchone()
        return self._schedule_state(row)

    def enqueue_due_schedule(
        self,
        schedule_id: str,
        job: AutomationJob,
        occurrence_at: datetime,
        next_run_at: datetime,
        now: datetime,
        maximum_active_jobs: int,
    ) -> bool:
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                if not self._has_job_capacity(maximum_active_jobs):
                    self._connection.rollback()
                    return False
                cursor = self._connection.execute(
                    "UPDATE automation_schedules SET next_run_at=?, updated_at=?, last_job_id=? "
                    "WHERE schedule_id=? AND next_run_at=? AND next_run_at<=?",
                    (
                        next_run_at.isoformat(),
                        now.isoformat(),
                        job.job_id,
                        schedule_id,
                        occurrence_at.isoformat(),
                        now.isoformat(),
                    ),
                )
                if cursor.rowcount != 1:
                    self._connection.rollback()
                    return False
                self._insert_job(job)
                self._connection.execute(
                    "INSERT INTO schedule_audit VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        f"{schedule_id}:{job.job_id}",
                        schedule_id,
                        occurrence_at.isoformat(),
                        now.isoformat(),
                        job.job_id,
                        job.command.value,
                        next_run_at.isoformat(),
                    ),
                )
                self._connection.commit()
                return True
            except Exception:
                self._connection.rollback()
                raise

    def list_schedule_states(self) -> tuple[ScheduleState, ...]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM automation_schedules ORDER BY schedule_id"
            ).fetchall()
        return tuple(self._schedule_state(row) for row in rows)

    def list_schedule_audit(
        self,
        schedule_id: str | None = None,
        *,
        limit: int | None = None,
        after: tuple[datetime, str] | None = None,
        before: tuple[datetime, str] | None = None,
    ) -> tuple[ScheduleAuditRecord, ...]:
        if limit is not None and limit < 1:
            raise ValueError("schedule audit limit must be positive")
        if after is not None and before is not None:
            raise ValueError("after and before are mutually exclusive")
        query = "SELECT * FROM schedule_audit"
        parameters: list[object] = []
        predicates: list[str] = []
        reverse = before is not None
        if schedule_id is not None:
            predicates.append("schedule_id=?")
            parameters.append(schedule_id)
        if after is not None:
            timestamp = after[0].isoformat()
            predicates.append("(emitted_at < ? OR (emitted_at = ? AND audit_id < ?))")
            parameters.extend((timestamp, timestamp, after[1]))
        elif before is not None:
            timestamp = before[0].isoformat()
            predicates.append("(emitted_at > ? OR (emitted_at = ? AND audit_id > ?))")
            parameters.extend((timestamp, timestamp, before[1]))
        if predicates:
            query += " WHERE " + " AND ".join(predicates)
        query += (
            " ORDER BY emitted_at ASC, audit_id ASC"
            if reverse
            else " ORDER BY emitted_at DESC, audit_id DESC"
        )
        if limit is not None:
            query += " LIMIT ?"
            parameters.append(limit)
        with self._lock:
            rows = self._connection.execute(query, tuple(parameters)).fetchall()
        values = tuple(
            ScheduleAuditRecord(
                row["audit_id"],
                row["schedule_id"],
                datetime.fromisoformat(row["occurrence_at"]),
                datetime.fromisoformat(row["emitted_at"]),
                row["job_id"],
                AutomationCommand(row["command"]),
                datetime.fromisoformat(row["next_run_at"]),
            )
            for row in rows
        )
        return tuple(reversed(values)) if reverse else values

    def create_execution_authorization(
        self, value: ExecutionAuthorization, audit: ExecutionAuthorizationAudit
    ) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO execution_authorizations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                self._execution_authorization_values(value),
            )
            self._insert_execution_authorization_audit(audit)

    def get_execution_authorization(self, authorization_id: str) -> ExecutionAuthorization | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM execution_authorizations WHERE authorization_id=?",
                (authorization_id,),
            ).fetchone()
        return self._execution_authorization(row) if row else None

    def list_execution_authorizations(self) -> tuple[ExecutionAuthorization, ...]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM execution_authorizations ORDER BY created_at DESC, authorization_id"
            ).fetchall()
        return tuple(self._execution_authorization(row) for row in rows)

    def expire_execution_authorizations(self, now: datetime) -> int:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "UPDATE execution_authorizations SET status=? WHERE status=? AND expires_at<=?",
                (
                    ExecutionAuthorizationStatus.EXPIRED.value,
                    ExecutionAuthorizationStatus.ACTIVE.value,
                    now.isoformat(),
                ),
            )
        return cursor.rowcount

    def consume_execution_authorization(
        self,
        token_digest: str,
        job: AutomationJob,
        now: datetime,
        audit: ExecutionAuthorizationAudit,
        maximum_active_jobs: int,
    ) -> ExecutionAuthorization:
        expired = False
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._connection.execute(
                    "SELECT * FROM execution_authorizations WHERE token_digest=?", (token_digest,)
                ).fetchone()
                if row is None:
                    raise ValueError("execution authorization is invalid")
                value = self._execution_authorization(row)
                if value.status is not ExecutionAuthorizationStatus.ACTIVE:
                    raise ValueError(f"execution authorization is {value.status.value}")
                if value.expires_at <= now:
                    self._connection.execute(
                        "UPDATE execution_authorizations SET status=? WHERE authorization_id=?",
                        (ExecutionAuthorizationStatus.EXPIRED.value, value.authorization_id),
                    )
                    expired = True
                elif job.limit is None or job.limit > value.max_items:
                    raise ValueError("remote organize limit exceeds execution authorization")
                elif not self._has_job_capacity(maximum_active_jobs):
                    raise AutomationQueueFull(
                        "automation queue reached configured active Job limit "
                        f"{maximum_active_jobs}"
                    )
                else:
                    cursor = self._connection.execute(
                        "UPDATE execution_authorizations SET status=?, consumed_at=?, "
                        "consumed_job_id=? WHERE authorization_id=? AND status=?",
                        (
                            ExecutionAuthorizationStatus.CONSUMED.value,
                            now.isoformat(),
                            job.job_id,
                            value.authorization_id,
                            ExecutionAuthorizationStatus.ACTIVE.value,
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise ValueError("execution authorization was already consumed")
                    self._insert_job(job)
                    self._insert_execution_authorization_audit(
                        replace(audit, authorization_id=value.authorization_id)
                    )
                    updated = self._connection.execute(
                        "SELECT * FROM execution_authorizations WHERE authorization_id=?",
                        (value.authorization_id,),
                    ).fetchone()
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        if expired:
            raise ValueError("execution authorization is expired")
        return self._execution_authorization(updated)

    def revoke_execution_authorization(
        self, authorization_id: str, now: datetime, audit: ExecutionAuthorizationAudit
    ) -> ExecutionAuthorization:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "UPDATE execution_authorizations SET status=?, revoked_at=? "
                "WHERE authorization_id=? AND status=? AND expires_at>?",
                (
                    ExecutionAuthorizationStatus.REVOKED.value,
                    now.isoformat(),
                    authorization_id,
                    ExecutionAuthorizationStatus.ACTIVE.value,
                    now.isoformat(),
                ),
            )
            if cursor.rowcount != 1:
                existing = self.get_execution_authorization(authorization_id)
                if existing is None:
                    raise LookupError(f"execution authorization {authorization_id!r} was not found")
                raise ValueError("only an active unexpired execution authorization can be revoked")
            self._insert_execution_authorization_audit(audit)
            row = self._connection.execute(
                "SELECT * FROM execution_authorizations WHERE authorization_id=?",
                (authorization_id,),
            ).fetchone()
        return self._execution_authorization(row)

    def list_execution_authorization_audit(
        self, authorization_id: str
    ) -> tuple[ExecutionAuthorizationAudit, ...]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM execution_authorization_audit WHERE authorization_id=? "
                "ORDER BY occurred_at, audit_id",
                (authorization_id,),
            ).fetchall()
        return tuple(
            ExecutionAuthorizationAudit(
                row["audit_id"],
                row["authorization_id"],
                row["action"],
                datetime.fromisoformat(row["occurred_at"]),
                row["job_id"],
                row["actor"],
            )
            for row in rows
        )

    def append_security_audit(self, value: SecurityAuditRecord) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO security_audit VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    value.audit_id,
                    value.occurred_at.isoformat(),
                    value.principal_id,
                    value.method,
                    value.route,
                    value.action,
                    value.outcome,
                    value.http_status,
                    value.request_id,
                    value.source_address,
                ),
            )

    def list_security_audit(self, *, limit: int = 100) -> tuple[SecurityAuditRecord, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 1000:
            raise ValueError("security audit limit must be between 1 and 1000")
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM security_audit ORDER BY occurred_at DESC, audit_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(
            SecurityAuditRecord(
                row["audit_id"],
                datetime.fromisoformat(row["occurred_at"]),
                row["principal_id"],
                row["method"],
                row["route"],
                row["action"],
                row["outcome"],
                row["http_status"],
                row["request_id"],
                row["source_address"],
            )
            for row in rows
        )

    def append_operational_log(self, value: OperationalLogRecord) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO operational_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    value.log_id,
                    value.occurred_at.isoformat(),
                    int(value.level),
                    value.component,
                    value.event,
                    value.task_id,
                    value.job_id,
                    value.plan_id,
                    value.status,
                ),
            )

    def list_operational_logs(
        self,
        *,
        limit: int,
        minimum_level: LogLevel | None = None,
        after: tuple[datetime, str] | None = None,
        before: tuple[datetime, str] | None = None,
    ) -> tuple[OperationalLogRecord, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 1000:
            raise ValueError("operational log limit must be between 1 and 1000")
        if after is not None and before is not None:
            raise ValueError("after and before are mutually exclusive")
        query = "SELECT * FROM operational_logs"
        parameters: list[object] = []
        predicates: list[str] = []
        reverse = before is not None
        if minimum_level is not None:
            predicates.append("level >= ?")
            parameters.append(int(minimum_level))
        if after is not None:
            timestamp = after[0].isoformat()
            predicates.append("(occurred_at < ? OR (occurred_at = ? AND log_id < ?))")
            parameters.extend((timestamp, timestamp, after[1]))
        elif before is not None:
            timestamp = before[0].isoformat()
            predicates.append("(occurred_at > ? OR (occurred_at = ? AND log_id > ?))")
            parameters.extend((timestamp, timestamp, before[1]))
        if predicates:
            query += " WHERE " + " AND ".join(predicates)
        query += (
            " ORDER BY occurred_at ASC, log_id ASC"
            if reverse
            else " ORDER BY occurred_at DESC, log_id DESC"
        )
        query += " LIMIT ?"
        parameters.append(limit)
        with self._lock:
            rows = self._connection.execute(query, tuple(parameters)).fetchall()
        values = tuple(
            OperationalLogRecord(
                row["log_id"],
                datetime.fromisoformat(row["occurred_at"]),
                LogLevel(row["level"]),
                row["component"],
                row["event"],
                row["task_id"],
                row["job_id"],
                row["plan_id"],
                row["status"],
            )
            for row in rows
        )
        return tuple(reversed(values)) if reverse else values

    def prune_operational_logs(self, *, before: datetime, maximum_records: int) -> int:
        if maximum_records < 1:
            raise ValueError("operational log maximum records must be positive")
        with self._lock, self._connection:
            aged = self._connection.execute(
                "DELETE FROM operational_logs WHERE occurred_at < ?", (before.isoformat(),)
            ).rowcount
            excess = self._connection.execute(
                "DELETE FROM operational_logs WHERE log_id IN ("
                "SELECT log_id FROM operational_logs ORDER BY occurred_at DESC, log_id DESC "
                "LIMIT -1 OFFSET ?)",
                (maximum_records,),
            ).rowcount
        return aged + excess

    def create_delivery(self, delivery: NotificationDelivery) -> bool:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "INSERT OR IGNORE INTO notification_deliveries VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                self._delivery_values(delivery),
            )
        return cursor.rowcount == 1

    def get_delivery(self, delivery_id: str) -> NotificationDelivery | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM notification_deliveries WHERE delivery_id=?", (delivery_id,)
            ).fetchone()
        return self._delivery(row) if row else None

    def list_deliveries(
        self,
        *,
        status: NotificationDeliveryStatus | None = None,
        limit: int | None = None,
        after: tuple[datetime, str] | None = None,
        before: tuple[datetime, str] | None = None,
    ) -> tuple[NotificationDelivery, ...]:
        if limit is not None and limit < 1:
            raise ValueError("notification limit must be positive")
        if after is not None and before is not None:
            raise ValueError("after and before are mutually exclusive")
        query = "SELECT * FROM notification_deliveries"
        parameters: list[object] = []
        predicates: list[str] = []
        reverse = before is not None
        if status is not None:
            predicates.append("status=?")
            parameters.append(status.value)
        if after is not None:
            timestamp = after[0].isoformat()
            predicates.append("(created_at < ? OR (created_at = ? AND delivery_id < ?))")
            parameters.extend((timestamp, timestamp, after[1]))
        elif before is not None:
            timestamp = before[0].isoformat()
            predicates.append("(created_at > ? OR (created_at = ? AND delivery_id > ?))")
            parameters.extend((timestamp, timestamp, before[1]))
        if predicates:
            query += " WHERE " + " AND ".join(predicates)
        query += (
            " ORDER BY created_at ASC, delivery_id ASC"
            if reverse
            else " ORDER BY created_at DESC, delivery_id DESC"
        )
        if limit is not None:
            query += " LIMIT ?"
            parameters.append(limit)
        with self._lock:
            rows = self._connection.execute(query, tuple(parameters)).fetchall()
        values = tuple(self._delivery(row) for row in rows)
        return tuple(reversed(values)) if reverse else values

    def claim_next_delivery(
        self, now: datetime, stale_before: datetime
    ) -> NotificationDelivery | None:
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT delivery_id FROM notification_deliveries "
                "WHERE (status IN (?, ?) AND next_attempt_at<=?) "
                "OR (status=? AND updated_at<=?) "
                "ORDER BY next_attempt_at, created_at, delivery_id LIMIT 1",
                (
                    NotificationDeliveryStatus.PENDING.value,
                    NotificationDeliveryStatus.RETRY.value,
                    now.isoformat(),
                    NotificationDeliveryStatus.DELIVERING.value,
                    stale_before.isoformat(),
                ),
            ).fetchone()
            if row is None:
                return None
            cursor = self._connection.execute(
                "UPDATE notification_deliveries SET status=?, attempts=attempts+1, updated_at=? "
                "WHERE delivery_id=? AND ((status IN (?, ?) AND next_attempt_at<=?) "
                "OR (status=? AND updated_at<=?))",
                (
                    NotificationDeliveryStatus.DELIVERING.value,
                    now.isoformat(),
                    row["delivery_id"],
                    NotificationDeliveryStatus.PENDING.value,
                    NotificationDeliveryStatus.RETRY.value,
                    now.isoformat(),
                    NotificationDeliveryStatus.DELIVERING.value,
                    stale_before.isoformat(),
                ),
            )
            if cursor.rowcount != 1:
                return None
            claimed = self._connection.execute(
                "SELECT * FROM notification_deliveries WHERE delivery_id=?",
                (row["delivery_id"],),
            ).fetchone()
        return self._delivery(claimed)

    def list_stale_deliveries(
        self, stale_before: datetime, *, limit: int | None = None
    ) -> tuple[NotificationDelivery, ...]:
        if limit is not None and limit < 1:
            raise ValueError("notification limit must be positive")
        query = (
            "SELECT * FROM notification_deliveries WHERE status=? AND updated_at<=? "
            "ORDER BY updated_at, delivery_id"
        )
        parameters: list[object] = [
            NotificationDeliveryStatus.DELIVERING.value,
            stale_before.isoformat(),
        ]
        if limit is not None:
            query += " LIMIT ?"
            parameters.append(limit)
        with self._lock:
            rows = self._connection.execute(query, tuple(parameters)).fetchall()
        return tuple(self._delivery(row) for row in rows)

    def update_delivery(self, delivery: NotificationDelivery) -> None:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "UPDATE notification_deliveries SET webhook_id=?, event_id=?, event_type=?, "
                "body=?, status=?, attempts=?, next_attempt_at=?, created_at=?, updated_at=?, "
                "delivered_at=?, failure_category=?, response_status=? WHERE delivery_id=?",
                (*self._delivery_values(delivery)[1:], delivery.delivery_id),
            )
            if cursor.rowcount != 1:
                raise LookupError(f"notification delivery {delivery.delivery_id!r} was not found")

    def requeue_dead_letter(self, delivery_id: str, now: datetime) -> NotificationDelivery:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "UPDATE notification_deliveries SET status=?, attempts=0, next_attempt_at=?, "
                "updated_at=?, delivered_at=NULL, failure_category=NULL, response_status=NULL "
                "WHERE delivery_id=? AND status=?",
                (
                    NotificationDeliveryStatus.PENDING.value,
                    now.isoformat(),
                    now.isoformat(),
                    delivery_id,
                    NotificationDeliveryStatus.DEAD_LETTER.value,
                ),
            )
            if cursor.rowcount != 1:
                existing = self.get_delivery(delivery_id)
                if existing is None:
                    raise LookupError(f"notification delivery {delivery_id!r} was not found")
                raise ValueError("only a dead-letter notification can be requeued")
            row = self._connection.execute(
                "SELECT * FROM notification_deliveries WHERE delivery_id=?", (delivery_id,)
            ).fetchone()
        return self._delivery(row)

    # Manual-organize intent persistence is intentionally kept on the existing
    # runtime repository.  It shares the same SQLite transaction and audit
    # boundary as Tasks, reviews and Results without creating a parallel
    # database authority.
    def create_manual_intent_with_audit(
        self,
        intent: ManualOrganizeIntent,
        items: tuple[ManualIntentItem, ...] | list[ManualIntentItem],
        audit: ManualIntentAudit,
    ) -> ManualOrganizeIntent:
        if intent.options is None:
            raise ValueError("manual intent configuration option projection is required")
        if intent.intent_id != audit.intent_id or audit.item_id is not None:
            raise ValueError("manual intent creation audit identity is invalid")
        values = tuple(items)
        if values != intent.items:
            raise ValueError("manual intent items do not match the intent projection")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                self._connection.execute(
                    "INSERT INTO manual_intents "
                    "(intent_id, actor, configuration_snapshot_id, configuration_snapshot_digest, "
                    "status, version, created_at, updated_at, next_action, error, options_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        intent.intent_id,
                        intent.actor,
                        intent.snapshot_id,
                        intent.snapshot_digest,
                        intent.status.value,
                        intent.version,
                        intent.created_at.isoformat(),
                        intent.updated_at.isoformat(),
                        intent.next_action,
                        intent.error,
                        json.dumps(intent.options.document(), ensure_ascii=False, sort_keys=True),
                    ),
                )
                for item in values:
                    self._connection.execute(
                        "INSERT INTO manual_intent_items "
                        "(item_id, intent_id, position, file_id, storage_id, resource_library_id, "
                        "source_path, filename, extension, source_size, source_modified_at, "
                        "source_last_seen_at, source_updated_at, source_stable_since, "
                        "source_scan_status, source_last_scan_id, choice_json, status, error, "
                        "version, created_at, updated_at) VALUES "
                        "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        self._manual_item_values(item),
                    )
                self._insert_manual_intent_audit(audit)
                self._connection.commit()
            except BaseException:
                self._connection.rollback()
                raise
        return self.get_manual_intent(intent.intent_id)

    def create_manual_intent(
        self,
        intent: ManualOrganizeIntent,
        items: tuple[ManualIntentItem, ...] | list[ManualIntentItem],
        audit: ManualIntentAudit,
    ) -> ManualOrganizeIntent:
        return self.create_manual_intent_with_audit(intent, items, audit)

    def create_manual_preview(
        self,
        preview: ManualOrganizePreview,
        items: tuple[ManualPreviewItem, ...] | list[ManualPreviewItem] | None = None,
    ) -> ManualOrganizePreview:
        """Publish one complete Preview atomically.

        A new Preview supersedes only the selected item identities.  The old
        aggregate is retained as history and its unselected child rows remain
        independently inspectable, so a bounded batch cannot erase a sibling
        merely because another item was re-previewed.
        """
        if not isinstance(preview, ManualOrganizePreview):
            raise ValueError("manual Preview projection is required")
        values = tuple(preview.items if items is None else items)
        if values != preview.items:
            raise ValueError("manual Preview items do not match the projection")
        if any(
            not isinstance(value, ManualPreviewItem)
            or value.preview_id != preview.preview_id
            or value.intent_id != preview.intent_id
            for value in values
        ):
            raise ValueError("manual Preview item ownership is invalid")
        item_ids = tuple(value.item_id for value in values)
        placeholders = ", ".join("?" for _ in item_ids)
        superseded_error = "superseded by a newer Preview for this item"
        superseded_action = "inspect the newer Preview or request a fresh Preview"
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                intent_row = self._connection.execute(
                    "SELECT status, version, configuration_snapshot_id, "
                    "configuration_snapshot_digest FROM manual_intents WHERE intent_id=?",
                    (preview.intent_id,),
                ).fetchone()
                if intent_row is None:
                    raise LookupError(f"manual intent {preview.intent_id!r} was not found")
                if (
                    intent_row["status"] != ManualIntentStatus.OPEN.value
                    or int(intent_row["version"]) != preview.intent_version
                    or intent_row["configuration_snapshot_id"] != preview.configuration_snapshot_id
                    or intent_row["configuration_snapshot_digest"]
                    != preview.configuration_snapshot_digest
                ):
                    raise ManualIntentConflict(
                        "manual intent changed; no Preview was published",
                        current_version=int(intent_row["version"]),
                    )
                for item in values:
                    current_row = self._connection.execute(
                        "SELECT * FROM manual_intent_items WHERE intent_id=? AND item_id=?",
                        (preview.intent_id, item.item_id),
                    ).fetchone()
                    if current_row is None:
                        raise LookupError(f"manual intent item {item.item_id!r} was not found")
                    current_item = self._manual_item(current_row)
                    if (
                        current_item.version != item.item_version
                        or current_item.status is not ManualIntentItemStatus.READY
                        or current_item.source.document() != item.source.document()
                        or current_item.choice.document() != item.choice.document()
                    ):
                        raise ManualIntentConflict(
                            "manual intent item changed; no Preview was published",
                            current_version=int(intent_row["version"]),
                        )
                old_rows = self._connection.execute(
                    f"SELECT DISTINCT preview_id FROM manual_preview_items "
                    f"WHERE intent_id=? AND current=1 AND item_id IN ({placeholders})",
                    (preview.intent_id, *item_ids),
                ).fetchall()
                if old_rows:
                    old_preview_ids = tuple(row["preview_id"] for row in old_rows)
                    self._connection.execute(
                        f"UPDATE manual_preview_items SET status=?, error=?, next_action=?, "
                        f"current=0, updated_at=? WHERE intent_id=? AND current=1 "
                        f"AND item_id IN ({placeholders})",
                        (
                            ManualPreviewItemStatus.STALE.value,
                            superseded_error,
                            superseded_action,
                            preview.updated_at.isoformat(),
                            preview.intent_id,
                            *item_ids,
                        ),
                    )
                    old_parent_placeholders = ", ".join("?" for _ in old_preview_ids)
                    self._connection.execute(
                        f"UPDATE manual_previews SET status=?, error=?, next_action=?, "
                        f"current=0, updated_at=? WHERE current=1 AND preview_id IN "
                        f"({old_parent_placeholders})",
                        (
                            ManualPreviewStatus.STALE.value,
                            superseded_error,
                            superseded_action,
                            preview.updated_at.isoformat(),
                            *old_preview_ids,
                        ),
                    )
                self._connection.execute(
                    "INSERT INTO manual_previews "
                    "(preview_id, intent_id, actor, configuration_snapshot_id, "
                    "configuration_snapshot_digest, status, intent_version, created_at, "
                    "updated_at, next_action, error, zero_mutation, current, truncated, "
                    "previous_preview_id, unselected_item_ids_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        preview.preview_id,
                        preview.intent_id,
                        preview.actor,
                        preview.configuration_snapshot_id,
                        preview.configuration_snapshot_digest,
                        preview.status.value,
                        preview.intent_version,
                        preview.created_at.isoformat(),
                        preview.updated_at.isoformat(),
                        redact_manual_text(preview.next_action),
                        redact_manual_text(preview.error) if preview.error is not None else None,
                        int(preview.zero_mutation),
                        int(preview.current),
                        int(preview.truncated),
                        preview.previous_preview_id,
                        json.dumps(
                            list(preview.unselected_item_ids),
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    ),
                )
                for item in values:
                    self._connection.execute(
                        "INSERT INTO manual_preview_items "
                        "(preview_item_id, preview_id, intent_id, item_id, position, "
                        "intent_version, item_version, source_json, choice_json, "
                        "configuration_snapshot_id, configuration_snapshot_digest, "
                        "source_fingerprint, source_evidence_versions_json, "
                        "review_versions_json, conflict_versions_json, input_fingerprint, "
                        "plan_fingerprint, status, plan_json, error, next_action, "
                        "zero_mutation, execution_state, truncated, created_at, updated_at, "
                        "current) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                        "?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            item.preview_item_id,
                            item.preview_id,
                            item.intent_id,
                            item.item_id,
                            item.position,
                            item.intent_version,
                            item.item_version,
                            json.dumps(item.source.document(), ensure_ascii=False, sort_keys=True),
                            json.dumps(item.choice.document(), ensure_ascii=False, sort_keys=True),
                            item.configuration_snapshot_id,
                            item.configuration_snapshot_digest,
                            item.source_fingerprint,
                            json.dumps(
                                list(item.source_evidence_versions),
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                            json.dumps(
                                list(item.review_versions),
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                            json.dumps(
                                list(item.conflict_versions),
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                            item.input_fingerprint,
                            item.plan_fingerprint,
                            item.status.value,
                            json.dumps(item.plan, ensure_ascii=False, sort_keys=True)
                            if item.plan is not None
                            else None,
                            redact_manual_text(item.error) if item.error is not None else None,
                            redact_manual_text(item.next_action),
                            int(item.zero_mutation),
                            item.execution_state,
                            int(item.truncated),
                            item.created_at.isoformat(),
                            item.updated_at.isoformat(),
                            int(item.current),
                        ),
                    )
                self._connection.commit()
            except BaseException:
                self._connection.rollback()
                raise
        value = self.get_manual_preview(preview.preview_id)
        if value is None:
            raise ManualPreviewUnavailable(
                "published manual Preview could not be reloaded",
                details={"previewId": preview.preview_id},
            )
        return value

    def get_manual_preview(self, preview_id: str) -> ManualOrganizePreview | None:
        if not isinstance(preview_id, str) or not preview_id.strip():
            raise ValueError("manual Preview ID is required")
        with self._lock:
            return self._load_manual_preview_locked(preview_id)

    def list_manual_previews(
        self, intent_id: str, *, limit: int = 100
    ) -> tuple[ManualOrganizePreview, ...]:
        if not isinstance(intent_id, str) or not intent_id.strip():
            raise ValueError("manual intent ID is required")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("manual Preview limit must be between 1 and 500")
        with self._lock:
            rows = self._connection.execute(
                "SELECT preview_id FROM manual_previews WHERE intent_id=? "
                "ORDER BY created_at DESC, preview_id DESC LIMIT ?",
                (intent_id, limit),
            ).fetchall()
            return tuple(self._load_manual_preview_locked(row["preview_id"]) for row in rows)

    def get_latest_manual_preview(self, intent_id: str) -> ManualOrganizePreview | None:
        values = self.list_manual_previews(intent_id, limit=1)
        return values[0] if values else None

    def mark_manual_preview_items_stale(
        self,
        intent_id: str,
        item_ids: tuple[str, ...] | list[str],
        reason: str,
        now: datetime,
    ) -> int:
        if not isinstance(intent_id, str) or not intent_id.strip():
            raise ValueError("manual intent ID is required")
        values = tuple(item_ids)
        if not values:
            return 0
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 512:
            raise ValueError("manual Preview stale reason is invalid")
        if now.tzinfo is None:
            raise ValueError("manual Preview stale timestamp must include timezone")
        placeholders = ", ".join("?" for _ in values)
        action = "request a fresh Preview for the affected item(s)"
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                rows = self._connection.execute(
                    f"SELECT DISTINCT preview_id FROM manual_preview_items WHERE intent_id=? "
                    f"AND current=1 AND item_id IN ({placeholders})",
                    (intent_id, *values),
                ).fetchall()
                cursor = self._connection.execute(
                    f"UPDATE manual_preview_items SET status=?, error=?, next_action=?, "
                    f"current=0, updated_at=? WHERE intent_id=? AND current=1 "
                    f"AND item_id IN ({placeholders})",
                    (
                        ManualPreviewItemStatus.STALE.value,
                        reason,
                        "request a fresh Preview for this item",
                        now.isoformat(),
                        intent_id,
                        *values,
                    ),
                )
                preview_ids = tuple(row["preview_id"] for row in rows)
                for preview_id in preview_ids:
                    self._connection.execute(
                        "UPDATE manual_previews SET status=?, error=?, next_action=?, "
                        "current=0, updated_at=? WHERE preview_id=? AND current=1",
                        (
                            ManualPreviewStatus.STALE.value,
                            reason,
                            action,
                            now.isoformat(),
                            preview_id,
                        ),
                    )
                self._connection.commit()
            except BaseException:
                self._connection.rollback()
                raise
        return cursor.rowcount

    # Automation Task Definition Preview persistence is a bounded evidence
    # projection only.  It creates no Job, Task, authority, or configuration
    # revision and never mutates Storage.
    def create_automation_task_definition_preview(
        self,
        preview: AutomationTaskDefinitionPreview,
        items: tuple[AutomationTaskDefinitionPreviewItem, ...]
        | list[AutomationTaskDefinitionPreviewItem]
        | None = None,
    ) -> AutomationTaskDefinitionPreview:
        if not isinstance(preview, AutomationTaskDefinitionPreview):
            raise ValueError("automation Preview projection is required")
        values = tuple(preview.items if items is None else items)
        if values != preview.items:
            raise ValueError("automation Preview items do not match the projection")
        if any(
            not isinstance(value, AutomationTaskDefinitionPreviewItem)
            or value.preview_id != preview.preview_id
            or value.definition_id != preview.definition_id
            for value in values
        ):
            raise ValueError("automation Preview item ownership is invalid")
        superseded = "superseded by a newer Preview for this definition"
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                old_rows = self._connection.execute(
                    "SELECT preview_id FROM automation_task_definition_previews "
                    "WHERE definition_id=? AND current=1",
                    (preview.definition_id,),
                ).fetchall()
                old_preview_ids = tuple(row["preview_id"] for row in old_rows)
                if old_preview_ids:
                    placeholders = ", ".join("?" for _ in old_preview_ids)
                    self._connection.execute(
                        f"UPDATE automation_task_definition_preview_items SET current=0, "
                        f"updated_at=? WHERE preview_id IN ({placeholders})",
                        (preview.updated_at.isoformat(), *old_preview_ids),
                    )
                    self._connection.execute(
                        f"UPDATE automation_task_definition_previews SET status=?, current=0, "
                        f"stale_reason=?, error=?, next_action=?, updated_at=? "
                        f"WHERE current=1 AND preview_id IN ({placeholders})",
                        (
                            AutomationTaskDefinitionPreviewStatus.STALE.value,
                            superseded,
                            superseded,
                            "inspect the newer Preview or rerun Preview",
                            preview.updated_at.isoformat(),
                            *old_preview_ids,
                        ),
                    )
                self._connection.execute(
                    "INSERT INTO automation_task_definition_previews "
                    "(preview_id, definition_id, definition_fingerprint, "
                    "configuration_revision_id, configuration_revision_version, "
                    "configuration_revision_digest, configuration_status, "
                    "resource_library_id, storage_id, source_scope, run_mode, "
                    "effective_item_limit, counts_json, status, actor, created_at, "
                    "updated_at, next_action, error, zero_mutation, current, stale_reason, "
                    "truncated, boundary_errors_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                    "?, ?, ?, ?)",
                    (
                        preview.preview_id,
                        preview.definition_id,
                        preview.definition_fingerprint,
                        preview.configuration_revision_id,
                        preview.configuration_revision_version,
                        preview.configuration_revision_digest,
                        preview.configuration_status,
                        preview.resource_library_id,
                        preview.storage_id,
                        preview.source_scope,
                        preview.run_mode,
                        preview.effective_item_limit,
                        json.dumps(preview.counts, ensure_ascii=False, sort_keys=True),
                        preview.status.value,
                        preview.actor,
                        preview.created_at.isoformat(),
                        preview.updated_at.isoformat(),
                        redact_manual_text(preview.next_action),
                        redact_manual_text(preview.error) if preview.error is not None else None,
                        int(preview.zero_mutation),
                        int(preview.current),
                        redact_manual_text(preview.stale_reason)
                        if preview.stale_reason is not None
                        else None,
                        int(preview.truncated),
                        json.dumps(
                            [redact_manual_text(value) for value in preview.boundary_errors[:16]],
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    ),
                )
                for item in values:
                    self._connection.execute(
                        "INSERT INTO automation_task_definition_preview_items "
                        "(preview_item_id, preview_id, definition_id, position, source_json, "
                        "source_fingerprint, status, next_action, recognition_status, "
                        "recognition_rule_id, recognition_type_id, "
                        "recognition_type_policy_id, metadata_policy_id, naming_policy_id, "
                        "classification_policy_id, organize_policy_id, metadata_provider, "
                        "metadata_provider_id, media_type, metadata_status, metadata_title, "
                        "metadata_year, naming_directory, naming_filename, "
                        "classification_media_library_id, classification_relative_path, "
                        "destination_storage_id, destination_path, operation, "
                        "attachments_json, required_capabilities_json, "
                        "declared_capabilities_json, capability_verdict, conflict_strategy, "
                        "conflicts_json, warnings_json, plan_fingerprint, plan_json, blocker, "
                        "zero_mutation, current, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                        "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                        "?, ?, ?)",
                        (
                            item.preview_item_id,
                            item.preview_id,
                            item.definition_id,
                            item.position,
                            json.dumps(item.source.document(), ensure_ascii=False, sort_keys=True),
                            item.source_fingerprint,
                            item.status.value,
                            redact_manual_text(item.next_action),
                            item.recognition_status,
                            item.recognition_rule_id,
                            item.recognition_type_id,
                            item.recognition_type_policy_id,
                            item.metadata_policy_id,
                            item.naming_policy_id,
                            item.classification_policy_id,
                            item.organize_policy_id,
                            item.metadata_provider,
                            item.metadata_provider_id,
                            item.media_type,
                            item.metadata_status,
                            item.metadata_title,
                            item.metadata_year,
                            item.naming_directory,
                            item.naming_filename,
                            item.classification_media_library_id,
                            item.classification_relative_path,
                            item.destination_storage_id,
                            item.destination_path,
                            item.operation,
                            item.attachments_json,
                            item.required_capabilities_json,
                            item.declared_capabilities_json,
                            item.capability_verdict,
                            item.conflict_strategy,
                            item.conflicts_json,
                            item.warnings_json,
                            item.plan_fingerprint,
                            json.dumps(item.plan, ensure_ascii=False, sort_keys=True)
                            if item.plan is not None
                            else None,
                            redact_manual_text(item.blocker) if item.blocker is not None else None,
                            int(item.zero_mutation),
                            int(item.current),
                            item.created_at.isoformat(),
                            item.updated_at.isoformat(),
                        ),
                    )
                self._connection.commit()
            except BaseException:
                self._connection.rollback()
                raise
        value = self.get_automation_task_definition_preview(preview.preview_id)
        if value is None:
            raise AutomationTaskDefinitionPreviewUnavailable(
                "published automation Preview could not be reloaded",
                details={"previewId": preview.preview_id},
            )
        return value

    def get_automation_task_definition_preview(
        self, preview_id: str
    ) -> AutomationTaskDefinitionPreview | None:
        if not isinstance(preview_id, str) or not preview_id.strip():
            raise ValueError("automation Preview ID is required")
        with self._lock:
            return self._load_automation_preview_locked(preview_id)

    def list_automation_task_definition_previews(
        self, definition_id: str, *, limit: int = 100
    ) -> tuple[AutomationTaskDefinitionPreview, ...]:
        if not isinstance(definition_id, str) or not definition_id.strip():
            raise ValueError("automation definition ID is required")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("automation Preview limit must be between 1 and 500")
        with self._lock:
            rows = self._connection.execute(
                "SELECT preview_id FROM automation_task_definition_previews "
                "WHERE definition_id=? ORDER BY created_at DESC, preview_id DESC LIMIT ?",
                (definition_id, limit),
            ).fetchall()
            return tuple(self._load_automation_preview_locked(row["preview_id"]) for row in rows)

    def get_latest_automation_task_definition_preview(
        self, definition_id: str
    ) -> AutomationTaskDefinitionPreview | None:
        values = self.list_automation_task_definition_previews(definition_id, limit=1)
        return values[0] if values else None

    def mark_automation_task_definition_previews_stale(
        self,
        definition_id: str,
        reason: str,
        now: datetime,
    ) -> int:
        if not isinstance(definition_id, str) or not definition_id.strip():
            raise ValueError("automation definition ID is required")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 512:
            raise ValueError("automation Preview stale reason is invalid")
        if now.tzinfo is None:
            raise ValueError("automation Preview stale timestamp must include timezone")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                rows = self._connection.execute(
                    "SELECT preview_id FROM automation_task_definition_previews "
                    "WHERE definition_id=? AND current=1",
                    (definition_id,),
                ).fetchall()
                preview_ids = tuple(row["preview_id"] for row in rows)
                if preview_ids:
                    placeholders = ", ".join("?" for _ in preview_ids)
                    self._connection.execute(
                        f"UPDATE automation_task_definition_preview_items SET current=0, "
                        f"updated_at=? WHERE preview_id IN ({placeholders})",
                        (now.isoformat(), *preview_ids),
                    )
                    cursor = self._connection.execute(
                        f"UPDATE automation_task_definition_previews SET status=?, current=0, "
                        f"stale_reason=?, error=?, next_action=?, updated_at=? "
                        f"WHERE current=1 AND preview_id IN ({placeholders})",
                        (
                            AutomationTaskDefinitionPreviewStatus.STALE.value,
                            reason,
                            reason,
                            "request a fresh Preview after resolving the stated stale reason",
                            now.isoformat(),
                            *preview_ids,
                        ),
                    )
                    affected = cursor.rowcount
                else:
                    affected = 0
                self._connection.commit()
            except BaseException:
                self._connection.rollback()
                raise
        return affected

    # Exact manual execution persistence deliberately reuses the existing
    # tasks/task_items/task_results tables.  These small companion tables hold
    # only the immutable Preview binding and the operation evidence needed to
    # explain that Task after a restart.
    def create_manual_execution_authorization(
        self, authorization: ManualExecutionAuthorization
    ) -> None:
        if authorization.status is not ManualExecutionAuthorizationStatus.ACTIVE:
            raise ValueError("manual execution authorization must start active")
        audit = ManualExecutionAuthorizationAudit(
            str(uuid4()),
            authorization.authorization_id,
            "issued",
            authorization.created_at,
            authorization.actor,
            None,
            {"itemCount": len(authorization.scope)},
        )
        with self._lock, self._connection:
            self._connection.execute(
                """INSERT INTO manual_execution_authorizations (
                    authorization_id, preview_id, intent_id, intent_version,
                    configuration_snapshot_id, configuration_snapshot_digest, actor,
                    permission, confirmation, allow_overwrite, allow_source_cleanup,
                    scope_json, created_at, expires_at, status, consumed_at,
                    execution_id, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                self._manual_execution_authorization_values(authorization),
            )
            self._insert_manual_execution_authorization_audit(audit)

    def get_manual_execution_authorization(
        self, authorization_id: str
    ) -> ManualExecutionAuthorization | None:
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise ValueError("manual execution authorization ID is required")
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM manual_execution_authorizations WHERE authorization_id=?",
                (authorization_id,),
            ).fetchone()
        return self._manual_execution_authorization(row) if row else None

    def list_manual_execution_authorizations(
        self, *, limit: int = 100
    ) -> tuple[ManualExecutionAuthorization, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("manual execution authorization limit must be between 1 and 500")
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM manual_execution_authorizations "
                "ORDER BY created_at DESC, authorization_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(self._manual_execution_authorization(row) for row in rows)

    def list_manual_execution_authorizations_for_preview(
        self, preview_id: str, *, limit: int = 100
    ) -> tuple[ManualExecutionAuthorization, ...]:
        self._validate_manual_discovery_limit(limit, "manual execution authorization")
        self._validate_manual_discovery_id(preview_id, "manual Preview ID")
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM manual_execution_authorizations WHERE preview_id=? "
                "ORDER BY created_at DESC, authorization_id DESC LIMIT ?",
                (preview_id, limit),
            ).fetchall()
        return tuple(self._manual_execution_authorization(row) for row in rows)

    def list_manual_execution_authorizations_for_intent(
        self, intent_id: str, *, limit: int = 100
    ) -> tuple[ManualExecutionAuthorization, ...]:
        self._validate_manual_discovery_limit(limit, "manual execution authorization")
        self._validate_manual_discovery_id(intent_id, "manual intent ID")
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM manual_execution_authorizations WHERE intent_id=? "
                "ORDER BY created_at DESC, authorization_id DESC LIMIT ?",
                (intent_id, limit),
            ).fetchall()
        return tuple(self._manual_execution_authorization(row) for row in rows)

    def list_manual_executions_for_preview(
        self, preview_id: str, *, limit: int = 100
    ) -> tuple[ManualExecution, ...]:
        self._validate_manual_discovery_limit(limit, "manual execution")
        self._validate_manual_discovery_id(preview_id, "manual Preview ID")
        return self._list_manual_executions_by_column("preview_id", preview_id, limit)

    def list_manual_executions_for_intent(
        self, intent_id: str, *, limit: int = 100
    ) -> tuple[ManualExecution, ...]:
        self._validate_manual_discovery_limit(limit, "manual execution")
        self._validate_manual_discovery_id(intent_id, "manual intent ID")
        return self._list_manual_executions_by_column("intent_id", intent_id, limit)

    def list_manual_executions_for_task(
        self, task_id: str, *, limit: int = 100
    ) -> tuple[ManualExecution, ...]:
        self._validate_manual_discovery_limit(limit, "manual execution")
        self._validate_manual_discovery_id(task_id, "Task ID")
        return self._list_manual_executions_by_column("task_id", task_id, limit)

    def list_manual_executions_for_task_item(
        self, task_id: str, task_item_id: str, *, limit: int = 100
    ) -> tuple[ManualExecution, ...]:
        self._validate_manual_discovery_limit(limit, "manual execution")
        self._validate_manual_discovery_id(task_id, "Task ID")
        self._validate_manual_discovery_id(task_item_id, "TaskItem ID")
        with self._lock:
            rows = self._connection.execute(
                "SELECT DISTINCT execution_id FROM manual_execution_items "
                "WHERE task_id=? AND task_item_id=? "
                "ORDER BY updated_at DESC, execution_id DESC LIMIT ?",
                (task_id, task_item_id, limit),
            ).fetchall()
        return self._load_manual_executions_by_id(rows)

    def list_manual_executions_for_source(
        self, storage_id: str, path: str, *, limit: int = 100
    ) -> tuple[ManualExecution, ...]:
        self._validate_manual_discovery_limit(limit, "manual execution")
        self._validate_manual_discovery_id(storage_id, "storage ID")
        if not isinstance(path, str) or not path.strip() or "\x00" in path:
            raise ValueError("source path is required")
        with self._lock:
            rows = self._connection.execute(
                "SELECT DISTINCT e.execution_id FROM manual_executions e "
                "JOIN manual_execution_items i ON i.execution_id=e.execution_id "
                "JOIN task_items t ON t.item_id=i.task_item_id AND t.task_id=i.task_id "
                "WHERE t.storage_id=? AND t.source_path=? "
                "ORDER BY e.updated_at DESC, e.execution_id DESC LIMIT ?",
                (storage_id, path, limit),
            ).fetchall()
        return self._load_manual_executions_by_id(rows)

    def _list_manual_executions_by_column(
        self, column: str, value: str, limit: int
    ) -> tuple[ManualExecution, ...]:
        if column not in {"preview_id", "intent_id", "task_id"}:
            raise ValueError("unsupported manual execution discovery relation")
        with self._lock:
            rows = self._connection.execute(
                f"SELECT execution_id FROM manual_executions WHERE {column}=? "
                "ORDER BY updated_at DESC, execution_id DESC LIMIT ?",
                (value, limit),
            ).fetchall()
        return self._load_manual_executions_by_id(rows)

    def _load_manual_executions_by_id(self, rows) -> tuple[ManualExecution, ...]:
        values = []
        for row in rows:
            value = self.get_manual_execution(row["execution_id"])
            if value is not None:
                values.append(value)
        return tuple(values)

    @staticmethod
    def _validate_manual_discovery_limit(limit: int, resource: str) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError(f"{resource} discovery limit must be between 1 and 500")

    @staticmethod
    def _validate_manual_discovery_id(value: str, label: str) -> None:
        if not isinstance(value, str) or not value.strip() or "\x00" in value:
            raise ValueError(f"{label} is required")

    def list_manual_execution_authorization_audit(
        self, authorization_id: str
    ) -> tuple[ManualExecutionAuthorizationAudit, ...]:
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise ValueError("manual execution authorization ID is required")
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM manual_execution_authorization_audit "
                "WHERE authorization_id=? ORDER BY occurred_at, audit_id",
                (authorization_id,),
            ).fetchall()
        return tuple(self._manual_execution_authorization_audit(row) for row in rows)

    def expire_manual_execution_authorizations(self, now: datetime) -> int:
        if now.tzinfo is None:
            raise ValueError("manual execution authorization expiry timestamp needs timezone")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                rows = self._connection.execute(
                    "SELECT authorization_id, actor FROM manual_execution_authorizations "
                    "WHERE status=? AND expires_at<=?",
                    (ManualExecutionAuthorizationStatus.ACTIVE.value, now.isoformat()),
                ).fetchall()
                for row in rows:
                    cursor = self._connection.execute(
                        "UPDATE manual_execution_authorizations SET status=? "
                        "WHERE authorization_id=? AND status=?",
                        (
                            ManualExecutionAuthorizationStatus.EXPIRED.value,
                            row["authorization_id"],
                            ManualExecutionAuthorizationStatus.ACTIVE.value,
                        ),
                    )
                    if cursor.rowcount == 1:
                        self._insert_manual_execution_authorization_audit(
                            ManualExecutionAuthorizationAudit(
                                str(uuid4()),
                                row["authorization_id"],
                                "expired",
                                now,
                                row["actor"],
                                None,
                                {"reason": "ttl_expired"},
                            )
                        )
                self._connection.commit()
            except BaseException:
                self._connection.rollback()
                raise
        return len(rows)

    def admit_manual_execution(
        self,
        authorization: ManualExecutionAuthorization,
        execution: ManualExecution,
        items: tuple[ManualExecutionItem, ...],
        locks: tuple[tuple[str, str], ...],
        now: datetime,
    ) -> ManualExecution:
        """Atomically consume exact authority, create Task scope, and fence paths."""

        if not items or tuple(item.item_id for item in items) != execution.selected_item_ids:
            raise ValueError("manual execution items do not match selected scope")
        if execution.authorization_id != authorization.authorization_id:
            raise ValueError("manual execution authorization identity does not match")
        if now.tzinfo is None:
            raise ValueError("manual execution admission timestamp needs timezone")
        lock_values = tuple(
            sorted({(storage_id, self._lock_path(path)) for storage_id, path in locks})
        )
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                auth_row = self._connection.execute(
                    "SELECT * FROM manual_execution_authorizations WHERE authorization_id=?",
                    (authorization.authorization_id,),
                ).fetchone()
                if auth_row is None:
                    raise ManualExecutionError(
                        "manual execution authorization was not found",
                        code="authorization_not_found",
                        status=404,
                    )
                stored = self._manual_execution_authorization(auth_row)
                if stored.status is ManualExecutionAuthorizationStatus.CONSUMED:
                    raise ManualExecutionError(
                        f"manual execution authorization is {stored.status.value}",
                        code="authorization_consumed",
                        next_action="inspect the linked execution; this authority cannot be reused",
                    )
                if stored != authorization:
                    raise ManualExecutionError(
                        "manual execution authorization binding changed",
                        code="authorization_changed",
                        next_action="reload the authorization and inspect its durable state",
                    )
                if stored.expires_at <= now:
                    self._connection.execute(
                        "UPDATE manual_execution_authorizations SET status=? "
                        "WHERE authorization_id=? AND status=?",
                        (
                            ManualExecutionAuthorizationStatus.EXPIRED.value,
                            stored.authorization_id,
                            ManualExecutionAuthorizationStatus.ACTIVE.value,
                        ),
                    )
                    self._insert_manual_execution_authorization_audit(
                        ManualExecutionAuthorizationAudit(
                            str(uuid4()),
                            stored.authorization_id,
                            "expired",
                            now,
                            stored.actor,
                            None,
                            {"reason": "ttl_expired"},
                        )
                    )
                    raise ManualExecutionError(
                        "manual execution authorization is expired",
                        code="authorization_expired",
                        next_action="request a fresh exact Preview and authorization",
                    )

                preview = self._connection.execute(
                    "SELECT * FROM manual_previews WHERE preview_id=?",
                    (execution.preview_id,),
                ).fetchone()
                if (
                    preview is None
                    or not bool(preview["current"])
                    or preview["intent_id"] != execution.intent_id
                    or int(preview["intent_version"]) != execution.intent_version
                    or preview["configuration_snapshot_id"] != execution.configuration_snapshot_id
                    or preview["configuration_snapshot_digest"]
                    != execution.configuration_snapshot_digest
                ):
                    raise ManualExecutionError(
                        "the reviewed Preview is no longer current",
                        code="preview_stale",
                        next_action="reload the manual intent and request a fresh Preview",
                    )
                intent = self._connection.execute(
                    "SELECT status, version, configuration_snapshot_id, "
                    "configuration_snapshot_digest FROM manual_intents WHERE intent_id=?",
                    (execution.intent_id,),
                ).fetchone()
                if (
                    intent is None
                    or intent["status"] != ManualIntentStatus.OPEN.value
                    or int(intent["version"]) != execution.intent_version
                    or intent["configuration_snapshot_id"] != execution.configuration_snapshot_id
                    or intent["configuration_snapshot_digest"]
                    != execution.configuration_snapshot_digest
                ):
                    raise ManualExecutionError(
                        "the manual intent is no longer the reviewed open intent",
                        code="intent_stale",
                        next_action="reload the intent and request a fresh Preview",
                    )
                scope_by_id = {value.item_id: value for value in authorization.scope}
                for item in items:
                    scope = scope_by_id.get(item.item_id)
                    if scope is None:
                        raise ManualExecutionError(
                            "execution contains an item outside its authorization scope",
                            code="scope_changed",
                        )
                    preview_item = self._connection.execute(
                        "SELECT * FROM manual_preview_items WHERE preview_id=? AND item_id=?",
                        (execution.preview_id, item.item_id),
                    ).fetchone()
                    current_item = self._connection.execute(
                        "SELECT * FROM manual_intent_items WHERE intent_id=? AND item_id=?",
                        (execution.intent_id, item.item_id),
                    ).fetchone()
                    if (
                        preview_item is None
                        or current_item is None
                        or not bool(preview_item["current"])
                        or preview_item["status"] != "previewed"
                        or int(preview_item["item_version"]) != scope.item_version
                        or preview_item["source_fingerprint"] != scope.source_fingerprint
                        or preview_item["plan_fingerprint"] != scope.plan_fingerprint
                        or _canonical_json(preview_item["source_json"])
                        != _canonical_json(scope.source.document())
                        or _canonical_json(preview_item["choice_json"])
                        != _canonical_json(scope.choice.document())
                        or preview_item["plan_json"] is None
                        or preview_item["plan_fingerprint"]
                        != _fingerprint_json(preview_item["plan_json"])
                        or _canonical_json(preview_item["plan_json"]) != _canonical_json(item.plan)
                        or int(current_item["version"]) != scope.item_version
                        or current_item["status"] != ManualIntentItemStatus.READY.value
                        or current_item["source_path"] != scope.source.path
                        or current_item["storage_id"] != scope.source.storage_id
                        or _canonical_json(current_item["choice_json"])
                        != _canonical_json(scope.choice.document())
                    ):
                        raise ManualExecutionError(
                            "a reviewed Preview item changed before admission",
                            code="item_stale",
                            next_action="request a fresh Preview for the affected item",
                            details={"itemId": item.item_id},
                        )
                    existing = self._connection.execute(
                        "SELECT 1 FROM manual_execution_items WHERE preview_id=? AND item_id=?",
                        (execution.preview_id, item.item_id),
                    ).fetchone()
                    if existing is not None:
                        raise ManualExecutionError(
                            "this Preview item was already admitted",
                            code="duplicate_execution",
                            next_action="inspect the existing durable execution",
                            details={"itemId": item.item_id},
                        )

                for storage_id, path in lock_values:
                    try:
                        self._connection.execute(
                            "INSERT INTO file_locks VALUES (?, ?, ?, ?)",
                            (storage_id, path, execution.task_id, now.isoformat()),
                        )
                    except sqlite3.IntegrityError as error:
                        raise ManualExecutionError(
                            "one or more reviewed paths are already being processed",
                            code="concurrent_execution",
                            next_action=(
                                "wait for the other Task to finish, then request a fresh Preview"
                            ),
                        ) from error

                task = PersistentTask(
                    execution.task_id,
                    "manual_organize",
                    PersistentTaskStatus.RUNNING,
                    True,
                    execution.created_at,
                    now,
                    execution.created_at,
                    None,
                    len(items),
                    0,
                    0,
                    None,
                    False,
                    None,
                    len(items),
                    execution.configuration_snapshot_id,
                    execution.configuration_snapshot_digest,
                )
                self._connection.execute(
                    "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    self._task_values(task),
                )
                self._connection.execute(
                    """INSERT INTO manual_executions (
                        execution_id, preview_id, intent_id, authorization_id, task_id,
                        actor, intent_version, configuration_snapshot_id,
                        configuration_snapshot_digest, selected_item_ids_json,
                        unselected_item_ids_json, status, next_action, error,
                        allow_overwrite, allow_source_cleanup, created_at, updated_at,
                        completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    self._manual_execution_values(execution),
                )
                for item in items:
                    task_item = self._manual_task_item(item, execution, now)
                    self._connection.execute(
                        "INSERT INTO task_items VALUES "
                        "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        self._item_values(task_item),
                    )
                    self._connection.execute(
                        """INSERT INTO manual_execution_items (
                            execution_item_id, execution_id, preview_id, preview_item_id,
                            intent_id, item_id, task_id, task_item_id, item_version,
                            source_fingerprint, plan_fingerprint, source_json, choice_json,
                            plan_json, status, stage, result_id, effect_certainty,
                            completed_operations, uncertain_effects, error, next_action,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                  ?, ?, ?, ?, ?, ?, ?)""",
                        self._manual_execution_item_values(item),
                    )
                consumed = self._connection.execute(
                    "UPDATE manual_execution_authorizations SET status=?, consumed_at=?, "
                    "execution_id=? WHERE authorization_id=? AND status=?",
                    (
                        ManualExecutionAuthorizationStatus.CONSUMED.value,
                        now.isoformat(),
                        execution.execution_id,
                        authorization.authorization_id,
                        ManualExecutionAuthorizationStatus.ACTIVE.value,
                    ),
                )
                if consumed.rowcount != 1:
                    raise ManualExecutionError(
                        "manual execution authorization changed during admission",
                        code="authorization_changed",
                        next_action="reload the authorization and inspect its durable state",
                    )
                self._insert_manual_execution_authorization_audit(
                    ManualExecutionAuthorizationAudit(
                        str(uuid4()),
                        authorization.authorization_id,
                        "consumed",
                        now,
                        authorization.actor,
                        execution.execution_id,
                        {"taskId": execution.task_id},
                    )
                )
                self._connection.commit()
            except BaseException:
                self._connection.rollback()
                raise
        admitted = self.get_manual_execution(execution.execution_id)
        if admitted is None:
            raise ManualExecutionError(
                "admitted execution could not be reloaded",
                code="execution_unavailable",
                status=503,
            )
        return admitted

    def get_manual_execution(self, execution_id: str) -> ManualExecution | None:
        if not isinstance(execution_id, str) or not execution_id.strip():
            raise ValueError("manual execution ID is required")
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM manual_executions WHERE execution_id=?", (execution_id,)
            ).fetchone()
            if row is None:
                return None
            item_rows = self._connection.execute(
                "SELECT * FROM manual_execution_items WHERE execution_id=? "
                "ORDER BY item_id, execution_item_id",
                (execution_id,),
            ).fetchall()
            items = []
            for item_row in item_rows:
                effect_rows = self._connection.execute(
                    "SELECT * FROM manual_execution_effects WHERE execution_item_id=? "
                    "ORDER BY sequence, effect_id",
                    (item_row["execution_item_id"],),
                ).fetchall()
                items.append(
                    self._manual_execution_item(
                        item_row,
                        tuple(self._manual_execution_effect(value) for value in effect_rows),
                    )
                )
            selected_ids = tuple(json.loads(row["selected_item_ids_json"]))
            selected_order = {item_id: index for index, item_id in enumerate(selected_ids)}
            items.sort(key=lambda value: selected_order.get(value.item_id, len(selected_order)))
        return self._manual_execution(row, tuple(items))

    def update_manual_execution(self, execution: ManualExecution) -> None:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "UPDATE manual_executions SET status=?, next_action=?, error=?, "
                "updated_at=?, completed_at=? WHERE execution_id=?",
                (
                    execution.status.value,
                    execution.next_action,
                    execution.error,
                    execution.updated_at.isoformat(),
                    execution.completed_at.isoformat() if execution.completed_at else None,
                    execution.execution_id,
                ),
            )
            if cursor.rowcount != 1:
                raise LookupError(f"manual execution {execution.execution_id!r} was not found")

    def update_manual_execution_item(self, item: ManualExecutionItem) -> None:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "UPDATE manual_execution_items SET status=?, stage=?, result_id=?, "
                "effect_certainty=?, completed_operations=?, uncertain_effects=?, error=?, "
                "next_action=?, updated_at=? WHERE execution_item_id=?",
                (
                    item.status.value,
                    item.stage,
                    item.result_id,
                    item.effect_certainty,
                    json.dumps(item.completed_operations, ensure_ascii=False),
                    json.dumps(item.uncertain_effects, ensure_ascii=False),
                    item.error,
                    item.next_action,
                    item.updated_at.isoformat(),
                    item.execution_item_id,
                ),
            )
            if cursor.rowcount != 1:
                raise LookupError(f"manual execution item {item.execution_item_id!r} was not found")

    def complete_manual_execution_item(
        self,
        execution: ManualExecution,
        item: ManualExecutionItem,
        task_item: PersistentTaskItem,
        task: PersistentTask,
        result: PersistentResultRecord,
        effects: tuple[ManualExecutionEffect, ...],
        locks: tuple[tuple[str, str], ...],
    ) -> None:
        """Publish TaskItem, Result, effect evidence and release its fence together."""

        if len(effects) > 256:
            raise ValueError("manual execution effect count exceeds its bound")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                self._insert_result_locked(result)
                self._connection.execute(
                    """INSERT INTO task_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?)
                    ON CONFLICT(item_id) DO UPDATE SET
                        status=excluded.status, stage=excluded.stage, attempts=excluded.attempts,
                        updated_at=excluded.updated_at, plan_id=excluded.plan_id,
                        destination_storage_id=excluded.destination_storage_id,
                        destination_path=excluded.destination_path,
                        execution_status=excluded.execution_status, error=excluded.error""",
                    self._item_values(task_item),
                )
                self._connection.execute(
                    "UPDATE manual_execution_items SET status=?, stage=?, result_id=?, "
                    "effect_certainty=?, completed_operations=?, uncertain_effects=?, error=?, "
                    "next_action=?, updated_at=? WHERE execution_item_id=?",
                    (
                        item.status.value,
                        item.stage,
                        item.result_id,
                        item.effect_certainty,
                        json.dumps(item.completed_operations, ensure_ascii=False),
                        json.dumps(item.uncertain_effects, ensure_ascii=False),
                        item.error,
                        item.next_action,
                        item.updated_at.isoformat(),
                        item.execution_item_id,
                    ),
                )
                for effect in effects:
                    self._connection.execute(
                        """INSERT OR REPLACE INTO manual_execution_effects (
                            effect_id, execution_item_id, sequence, action,
                            source_storage_id, source_path, destination_storage_id,
                            destination_path, verified, certainty, details_json, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        self._manual_execution_effect_values(effect),
                    )
                self._connection.execute(
                    "UPDATE manual_executions SET status=?, next_action=?, error=?, "
                    "updated_at=?, completed_at=? WHERE execution_id=?",
                    (
                        execution.status.value,
                        execution.next_action,
                        execution.error,
                        execution.updated_at.isoformat(),
                        execution.completed_at.isoformat() if execution.completed_at else None,
                        execution.execution_id,
                    ),
                )
                cursor = self._connection.execute(
                    "UPDATE tasks SET command=?, status=?, execute_authorized=?, created_at=?, "
                    "updated_at=?, started_at=?, completed_at=?, total_items=?, completed_items=?, "
                    "failed_items=?, error=?, pause_requested=?, scope_path=?, item_limit=?, "
                    "configuration_snapshot_id=?, configuration_snapshot_digest=? WHERE task_id=?",
                    (*self._task_values(task)[1:], task.task_id),
                )
                if cursor.rowcount != 1:
                    raise LookupError(f"task {task.task_id!r} was not found")
                for storage_id, path in tuple(
                    sorted({(storage_id, self._lock_path(path)) for storage_id, path in locks})
                ):
                    self._connection.execute(
                        "DELETE FROM file_locks WHERE storage_id=? AND path=? AND task_id=?",
                        (storage_id, path, task.task_id),
                    )
                self._connection.commit()
            except BaseException:
                self._connection.rollback()
                raise

    def reconcile_manual_execution(
        self,
        execution: ManualExecution,
        items: tuple[ManualExecutionItem, ...],
        task_items: tuple[PersistentTaskItem, ...],
        task: PersistentTask,
        results: tuple[PersistentResultRecord, ...],
        effects: tuple[ManualExecutionEffect, ...],
        audit: ManualExecutionAuthorizationAudit,
    ) -> None:
        """Publish an interruption handoff without invoking or replaying Storage work.

        This path is deliberately separate from normal item completion.  It is the durable
        recovery boundary used when the process stopped between admission/execution phases or
        when result publication failed after OrganizerExecutor may have mutated Storage.  The
        supplied evidence is published atomically and the complete task fence is released only
        after that publication succeeds.
        """

        if len(effects) > 256:
            raise ValueError("manual execution effect count exceeds its bound")
        if audit.execution_id != execution.execution_id:
            raise ValueError("manual execution recovery audit identity does not match")
        if audit.authorization_id != execution.authorization_id:
            raise ValueError("manual execution recovery audit authority does not match")
        if any(item.execution_id != execution.execution_id for item in items):
            raise ValueError("manual execution recovery item identity does not match")
        if any(item.task_id != execution.task_id for item in task_items):
            raise ValueError("manual execution recovery TaskItem identity does not match")
        if any(result.task_id != execution.task_id for result in results):
            raise ValueError("manual execution recovery Result identity does not match")
        item_ids = {item.execution_item_id for item in items}
        if any(effect.execution_item_id not in item_ids for effect in effects):
            raise ValueError("manual execution recovery effect identity does not match")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                current = self._connection.execute(
                    "SELECT status FROM manual_executions WHERE execution_id=?",
                    (execution.execution_id,),
                ).fetchone()
                if current is None:
                    raise LookupError(f"manual execution {execution.execution_id!r} was not found")
                if current["status"] not in {
                    ManualExecutionStatus.ADMITTED.value,
                    ManualExecutionStatus.RUNNING.value,
                }:
                    # A late recovery attempt must never downgrade a terminal result that was
                    # committed before an exception became visible to the caller.
                    self._connection.commit()
                    return
                for result in results:
                    self._insert_result_locked(result)
                for task_item in task_items:
                    self._connection.execute(
                        """INSERT INTO task_items VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                        )
                        ON CONFLICT(item_id) DO UPDATE SET
                            status=excluded.status, stage=excluded.stage,
                            attempts=excluded.attempts,
                            updated_at=excluded.updated_at, plan_id=excluded.plan_id,
                            destination_storage_id=excluded.destination_storage_id,
                            destination_path=excluded.destination_path,
                            execution_status=excluded.execution_status, error=excluded.error""",
                        self._item_values(task_item),
                    )
                for item in items:
                    cursor = self._connection.execute(
                        "UPDATE manual_execution_items SET status=?, stage=?, result_id=?, "
                        "effect_certainty=?, completed_operations=?, uncertain_effects=?, error=?, "
                        "next_action=?, updated_at=? WHERE execution_item_id=?",
                        (
                            item.status.value,
                            item.stage,
                            item.result_id,
                            item.effect_certainty,
                            json.dumps(item.completed_operations, ensure_ascii=False),
                            json.dumps(item.uncertain_effects, ensure_ascii=False),
                            item.error,
                            item.next_action,
                            item.updated_at.isoformat(),
                            item.execution_item_id,
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise LookupError(
                            f"manual execution item {item.execution_item_id!r} was not found"
                        )
                for effect in effects:
                    self._connection.execute(
                        """INSERT OR REPLACE INTO manual_execution_effects (
                            effect_id, execution_item_id, sequence, action,
                            source_storage_id, source_path, destination_storage_id,
                            destination_path, verified, certainty, details_json, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        self._manual_execution_effect_values(effect),
                    )
                cursor = self._connection.execute(
                    "UPDATE manual_executions SET status=?, next_action=?, error=?, "
                    "updated_at=?, completed_at=? WHERE execution_id=?",
                    (
                        execution.status.value,
                        execution.next_action,
                        execution.error,
                        execution.updated_at.isoformat(),
                        execution.completed_at.isoformat() if execution.completed_at else None,
                        execution.execution_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise LookupError(f"manual execution {execution.execution_id!r} was not found")
                cursor = self._connection.execute(
                    "UPDATE tasks SET command=?, status=?, execute_authorized=?, created_at=?, "
                    "updated_at=?, started_at=?, completed_at=?, total_items=?, completed_items=?, "
                    "failed_items=?, error=?, pause_requested=?, scope_path=?, item_limit=?, "
                    "configuration_snapshot_id=?, configuration_snapshot_digest=? WHERE task_id=?",
                    (*self._task_values(task)[1:], task.task_id),
                )
                if cursor.rowcount != 1:
                    raise LookupError(f"task {task.task_id!r} was not found")
                self._connection.execute(
                    "DELETE FROM file_locks WHERE task_id=?", (execution.task_id,)
                )
                self._insert_manual_execution_authorization_audit(audit)
                self._connection.commit()
            except BaseException:
                self._connection.rollback()
                raise

    def get_manual_intent(self, intent_id: str) -> ManualOrganizeIntent | None:
        if not isinstance(intent_id, str) or not intent_id.strip():
            raise ValueError("manual intent ID is required")
        with self._lock:
            return self._load_manual_intent_locked(intent_id)

    def list_manual_intents(self, *, limit: int = 100) -> tuple[ManualOrganizeIntent, ...]:
        if isinstance(limit, bool) or not 1 <= limit <= 500:
            raise ValueError("manual intent limit must be between 1 and 500")
        with self._lock:
            rows = self._connection.execute(
                "SELECT intent_id FROM manual_intents "
                "ORDER BY created_at DESC, intent_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return tuple(self._load_manual_intent_locked(row["intent_id"]) for row in rows)

    def list_manual_intent_audit(
        self, intent_id: str, *, limit: int = 256
    ) -> tuple[ManualIntentAudit, ...]:
        if isinstance(limit, bool) or not 1 <= limit <= 1000:
            raise ValueError("manual intent audit limit must be between 1 and 1000")
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM manual_intent_audit WHERE intent_id=? "
                "ORDER BY occurred_at ASC, audit_id ASC LIMIT ?",
                (intent_id, limit),
            ).fetchall()
        return tuple(self._manual_audit(row) for row in rows)

    def update_manual_intent_choice_with_audit(
        self,
        intent: ManualOrganizeIntent,
        item: ManualIntentItem,
        expected_intent_version: int,
        expected_item_version: int,
        audit: ManualIntentAudit,
    ) -> ManualOrganizeIntent:
        if (
            intent.intent_id != item.intent_id
            or audit.intent_id != intent.intent_id
            or audit.item_id != item.item_id
        ):
            raise ValueError("manual intent choice audit identity is invalid")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                current = self._load_manual_intent_locked(intent.intent_id)
                if current is None:
                    raise LookupError(f"manual intent {intent.intent_id!r} was not found")
                if current.version != expected_intent_version:
                    raise ManualIntentConflict(
                        "manual intent version is stale; no choice was changed", intent=current
                    )
                current_item = next(
                    (value for value in current.items if value.item_id == item.item_id), None
                )
                if current_item is None:
                    raise LookupError(f"manual intent item {item.item_id!r} was not found")
                if current_item.version != expected_item_version:
                    raise ManualIntentConflict(
                        "manual intent item version is stale; no choice was changed", intent=current
                    )
                cursor = self._connection.execute(
                    "UPDATE manual_intents SET version=?, updated_at=?, next_action=?, error=? "
                    "WHERE intent_id=? AND version=?",
                    (
                        intent.version,
                        intent.updated_at.isoformat(),
                        intent.next_action,
                        intent.error,
                        intent.intent_id,
                        expected_intent_version,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ManualIntentConflict(
                        "manual intent version is stale; no choice was changed",
                        intent=self._load_manual_intent_locked(intent.intent_id),
                    )
                cursor = self._connection.execute(
                    "UPDATE manual_intent_items SET choice_json=?, status=?, error=?, "
                    "version=?, updated_at=? "
                    "WHERE item_id=? AND intent_id=? AND version=?",
                    (
                        json.dumps(item.choice.document(), ensure_ascii=False, sort_keys=True),
                        item.status.value,
                        item.error,
                        item.version,
                        item.updated_at.isoformat(),
                        item.item_id,
                        item.intent_id,
                        expected_item_version,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ManualIntentConflict(
                        "manual intent item version is stale; no choice was changed",
                        intent=self._load_manual_intent_locked(intent.intent_id),
                    )
                preview_stale_error = "manual choice changed after Preview"
                preview_stale_action = "request a fresh Preview for this item"
                self._connection.execute(
                    "UPDATE manual_preview_items SET status=?, error=?, next_action=?, "
                    "current=0, updated_at=? WHERE intent_id=? AND item_id=? AND current=1",
                    (
                        ManualPreviewItemStatus.STALE.value,
                        preview_stale_error,
                        preview_stale_action,
                        item.updated_at.isoformat(),
                        item.intent_id,
                        item.item_id,
                    ),
                )
                self._connection.execute(
                    "UPDATE manual_previews SET status=?, error=?, next_action=?, "
                    "current=0, updated_at=? WHERE current=1 AND preview_id IN "
                    "(SELECT preview_id FROM manual_preview_items WHERE intent_id=? "
                    "AND item_id=?)",
                    (
                        ManualPreviewStatus.STALE.value,
                        preview_stale_error,
                        preview_stale_action,
                        item.updated_at.isoformat(),
                        item.intent_id,
                        item.item_id,
                    ),
                )
                self._insert_manual_intent_audit(audit)
                self._connection.commit()
            except BaseException:
                self._connection.rollback()
                raise
        return self.get_manual_intent(intent.intent_id)

    def update_manual_intent_status_with_audit(
        self,
        intent: ManualOrganizeIntent,
        expected_version: int,
        audit: ManualIntentAudit,
    ) -> ManualOrganizeIntent:
        if audit.intent_id != intent.intent_id or audit.item_id is not None:
            raise ValueError("manual intent status audit identity is invalid")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                current = self._load_manual_intent_locked(intent.intent_id)
                if current is None:
                    raise LookupError(f"manual intent {intent.intent_id!r} was not found")
                if current.version != expected_version:
                    raise ManualIntentConflict(
                        "manual intent version is stale; no cancellation was recorded",
                        intent=current,
                    )
                cursor = self._connection.execute(
                    "UPDATE manual_intents SET status=?, version=?, updated_at=?, "
                    "next_action=?, error=? "
                    "WHERE intent_id=? AND version=?",
                    (
                        intent.status.value,
                        intent.version,
                        intent.updated_at.isoformat(),
                        intent.next_action,
                        intent.error,
                        intent.intent_id,
                        expected_version,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ManualIntentConflict(
                        "manual intent version is stale; no cancellation was recorded",
                        intent=self._load_manual_intent_locked(intent.intent_id),
                    )
                self._connection.execute(
                    "UPDATE manual_intent_items SET status=?, updated_at=? WHERE intent_id=?",
                    (
                        ManualIntentItemStatus.CANCELLED.value,
                        intent.updated_at.isoformat(),
                        intent.intent_id,
                    ),
                )
                preview_stale_error = "manual intent was cancelled after Preview"
                preview_stale_action = "create a new intent before requesting Preview"
                self._connection.execute(
                    "UPDATE manual_preview_items SET status=?, error=?, next_action=?, "
                    "current=0, updated_at=? WHERE intent_id=? AND current=1",
                    (
                        ManualPreviewItemStatus.STALE.value,
                        preview_stale_error,
                        preview_stale_action,
                        intent.updated_at.isoformat(),
                        intent.intent_id,
                    ),
                )
                self._connection.execute(
                    "UPDATE manual_previews SET status=?, error=?, next_action=?, "
                    "current=0, updated_at=? WHERE intent_id=? AND current=1",
                    (
                        ManualPreviewStatus.STALE.value,
                        preview_stale_error,
                        preview_stale_action,
                        intent.updated_at.isoformat(),
                        intent.intent_id,
                    ),
                )
                self._insert_manual_intent_audit(audit)
                self._connection.commit()
            except BaseException:
                self._connection.rollback()
                raise
        return self.get_manual_intent(intent.intent_id)

    def _load_manual_preview_locked(self, preview_id: str) -> ManualOrganizePreview | None:
        row = self._connection.execute(
            "SELECT * FROM manual_previews WHERE preview_id=?", (preview_id,)
        ).fetchone()
        if row is None:
            return None
        item_rows = self._connection.execute(
            "SELECT * FROM manual_preview_items WHERE preview_id=? "
            "ORDER BY position ASC, item_id ASC",
            (preview_id,),
        ).fetchall()
        try:
            items = tuple(self._manual_preview_item(value) for value in item_rows)
            return ManualOrganizePreview(
                preview_id=row["preview_id"],
                intent_id=row["intent_id"],
                actor=row["actor"],
                intent_version=int(row["intent_version"]),
                configuration_snapshot_id=row["configuration_snapshot_id"],
                configuration_snapshot_digest=row["configuration_snapshot_digest"],
                status=ManualPreviewStatus(row["status"]),
                items=items,
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                next_action=row["next_action"],
                error=row["error"],
                zero_mutation=bool(row["zero_mutation"]),
                current=bool(row["current"]),
                truncated=bool(row["truncated"]),
                previous_preview_id=row["previous_preview_id"],
                unselected_item_ids=tuple(json.loads(row["unselected_item_ids_json"])),
            )
        except Exception as error:
            raise ManualPreviewUnavailable(
                "durable manual Preview state is corrupt or unavailable",
                details={"previewId": preview_id, "reason": type(error).__name__},
            ) from error

    @staticmethod
    def _manual_preview_item(row: sqlite3.Row) -> ManualPreviewItem:
        return ManualPreviewItem(
            preview_item_id=row["preview_item_id"],
            preview_id=row["preview_id"],
            intent_id=row["intent_id"],
            item_id=row["item_id"],
            position=int(row["position"]),
            intent_version=int(row["intent_version"]),
            item_version=int(row["item_version"]),
            source=ManualSourceIdentity.from_document(json.loads(row["source_json"])),
            choice=ManualChoice.from_document(json.loads(row["choice_json"])),
            configuration_snapshot_id=row["configuration_snapshot_id"],
            configuration_snapshot_digest=row["configuration_snapshot_digest"],
            source_fingerprint=row["source_fingerprint"],
            source_evidence_versions=tuple(json.loads(row["source_evidence_versions_json"])),
            review_versions=tuple(json.loads(row["review_versions_json"])),
            conflict_versions=tuple(json.loads(row["conflict_versions_json"])),
            input_fingerprint=row["input_fingerprint"],
            plan_fingerprint=row["plan_fingerprint"],
            status=ManualPreviewItemStatus(row["status"]),
            plan=json.loads(row["plan_json"]) if row["plan_json"] is not None else None,
            error=row["error"],
            next_action=row["next_action"],
            zero_mutation=bool(row["zero_mutation"]),
            execution_state=row["execution_state"],
            truncated=bool(row["truncated"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            current=bool(row["current"]),
        )

    def _load_automation_preview_locked(
        self, preview_id: str
    ) -> AutomationTaskDefinitionPreview | None:
        row = self._connection.execute(
            "SELECT * FROM automation_task_definition_previews WHERE preview_id=?",
            (preview_id,),
        ).fetchone()
        if row is None:
            return None
        item_rows = self._connection.execute(
            "SELECT * FROM automation_task_definition_preview_items WHERE preview_id=? "
            "ORDER BY position ASC, preview_item_id ASC",
            (preview_id,),
        ).fetchall()
        try:
            items = tuple(self._automation_preview_item(value) for value in item_rows)
            return AutomationTaskDefinitionPreview(
                preview_id=row["preview_id"],
                definition_id=row["definition_id"],
                definition_fingerprint=row["definition_fingerprint"],
                configuration_revision_id=row["configuration_revision_id"],
                configuration_revision_version=int(row["configuration_revision_version"]),
                configuration_revision_digest=row["configuration_revision_digest"],
                configuration_status=row["configuration_status"],
                resource_library_id=row["resource_library_id"],
                storage_id=row["storage_id"],
                source_scope=row["source_scope"],
                run_mode=row["run_mode"],
                effective_item_limit=int(row["effective_item_limit"]),
                counts=dict(json.loads(row["counts_json"])),
                status=AutomationTaskDefinitionPreviewStatus(row["status"]),
                items=items,
                actor=row["actor"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                next_action=row["next_action"],
                error=row["error"],
                zero_mutation=bool(row["zero_mutation"]),
                current=bool(row["current"]),
                stale_reason=row["stale_reason"],
                truncated=bool(row["truncated"]),
                boundary_errors=tuple(json.loads(row["boundary_errors_json"])),
            )
        except Exception as error:
            raise AutomationTaskDefinitionPreviewUnavailable(
                "durable automation Preview state is corrupt or unavailable",
                details={"previewId": preview_id, "reason": type(error).__name__},
            ) from error

    @staticmethod
    def _automation_preview_item(
        row: sqlite3.Row,
    ) -> AutomationTaskDefinitionPreviewItem:
        return AutomationTaskDefinitionPreviewItem(
            preview_item_id=row["preview_item_id"],
            preview_id=row["preview_id"],
            definition_id=row["definition_id"],
            position=int(row["position"]),
            source=AutomationPreviewSource.from_document(json.loads(row["source_json"])),
            source_fingerprint=row["source_fingerprint"],
            status=AutomationTaskDefinitionPreviewItemStatus(row["status"]),
            next_action=row["next_action"],
            recognition_status=row["recognition_status"],
            recognition_rule_id=row["recognition_rule_id"],
            recognition_type_id=row["recognition_type_id"],
            recognition_type_policy_id=row["recognition_type_policy_id"],
            metadata_policy_id=row["metadata_policy_id"],
            naming_policy_id=row["naming_policy_id"],
            classification_policy_id=row["classification_policy_id"],
            organize_policy_id=row["organize_policy_id"],
            metadata_provider=row["metadata_provider"],
            metadata_provider_id=row["metadata_provider_id"],
            media_type=row["media_type"],
            metadata_status=row["metadata_status"],
            metadata_title=row["metadata_title"],
            metadata_year=row["metadata_year"],
            naming_directory=row["naming_directory"],
            naming_filename=row["naming_filename"],
            classification_media_library_id=row["classification_media_library_id"],
            classification_relative_path=row["classification_relative_path"],
            destination_storage_id=row["destination_storage_id"],
            destination_path=row["destination_path"],
            operation=row["operation"],
            attachments_json=row["attachments_json"],
            required_capabilities_json=row["required_capabilities_json"],
            declared_capabilities_json=row["declared_capabilities_json"],
            capability_verdict=row["capability_verdict"],
            conflict_strategy=row["conflict_strategy"],
            conflicts_json=row["conflicts_json"],
            warnings_json=row["warnings_json"],
            plan_fingerprint=row["plan_fingerprint"],
            plan=json.loads(row["plan_json"]) if row["plan_json"] is not None else None,
            blocker=row["blocker"],
            zero_mutation=bool(row["zero_mutation"]),
            current=bool(row["current"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _load_manual_intent_locked(self, intent_id: str) -> ManualOrganizeIntent | None:
        row = self._connection.execute(
            "SELECT * FROM manual_intents WHERE intent_id=?", (intent_id,)
        ).fetchone()
        if row is None:
            return None
        item_rows = self._connection.execute(
            "SELECT * FROM manual_intent_items WHERE intent_id=? "
            "ORDER BY position ASC, item_id ASC",
            (intent_id,),
        ).fetchall()
        try:
            options = ManualConfigurationSnapshot.from_document(json.loads(row["options_json"]))
            items = tuple(self._manual_item(value) for value in item_rows)
            return ManualOrganizeIntent(
                row["intent_id"],
                row["actor"],
                row["configuration_snapshot_id"],
                row["configuration_snapshot_digest"],
                ManualIntentStatus(row["status"]),
                int(row["version"]),
                datetime.fromisoformat(row["created_at"]),
                datetime.fromisoformat(row["updated_at"]),
                items,
                options,
                row["next_action"],
                row["error"],
                (),
            )
        except Exception as error:
            raise ManualIntentUnavailable(
                "durable manual intent state is corrupt or unavailable",
                details={"intentId": intent_id, "reason": type(error).__name__},
            ) from error

    def _insert_manual_intent_audit(self, audit: ManualIntentAudit) -> None:
        self._connection.execute(
            "INSERT INTO manual_intent_audit "
            "(audit_id, intent_id, item_id, actor, action, before_json, after_json, occurred_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                audit.audit_id,
                audit.intent_id,
                audit.item_id,
                audit.actor,
                audit.action,
                json.dumps(audit.before, ensure_ascii=False, sort_keys=True),
                json.dumps(audit.after, ensure_ascii=False, sort_keys=True),
                audit.occurred_at.isoformat(),
            ),
        )

    @staticmethod
    def _manual_item_values(item: ManualIntentItem) -> tuple[object, ...]:
        source = item.source
        return (
            item.item_id,
            item.intent_id,
            item.position,
            source.file_id,
            source.storage_id,
            source.resource_library_id,
            source.path,
            source.filename,
            source.extension,
            source.size,
            source.modified_at.isoformat(),
            source.last_seen_at.isoformat(),
            source.updated_at.isoformat(),
            source.stable_since.isoformat() if source.stable_since else None,
            source.scan_status,
            source.last_scan_id,
            json.dumps(item.choice.document(), ensure_ascii=False, sort_keys=True),
            item.status.value,
            item.error,
            item.version,
            item.created_at.isoformat(),
            item.updated_at.isoformat(),
        )

    @staticmethod
    def _manual_item(row: sqlite3.Row) -> ManualIntentItem:
        source = ManualSourceIdentity(
            row["file_id"],
            row["storage_id"],
            row["resource_library_id"],
            row["source_path"],
            row["filename"],
            row["extension"],
            int(row["source_size"]),
            datetime.fromisoformat(row["source_modified_at"]),
            datetime.fromisoformat(row["source_last_seen_at"]),
            datetime.fromisoformat(row["source_updated_at"]),
            datetime.fromisoformat(row["source_stable_since"])
            if row["source_stable_since"]
            else None,
            row["source_scan_status"],
            row["source_last_scan_id"],
        )
        return ManualIntentItem(
            row["item_id"],
            row["intent_id"],
            int(row["position"]),
            source,
            ManualChoice.from_document(json.loads(row["choice_json"])),
            ManualIntentItemStatus(row["status"]),
            row["error"],
            int(row["version"]),
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _manual_audit(row: sqlite3.Row) -> ManualIntentAudit:
        return ManualIntentAudit(
            row["audit_id"],
            row["intent_id"],
            row["item_id"],
            row["actor"],
            row["action"],
            json.loads(row["before_json"]),
            json.loads(row["after_json"]),
            datetime.fromisoformat(row["occurred_at"]),
        )

    def acquire(self, storage_id: str, path: str, task_id: str, acquired_at: datetime) -> bool:
        normalized = self._lock_path(path)
        try:
            with self._lock, self._connection:
                self._connection.execute(
                    "INSERT INTO file_locks VALUES (?, ?, ?, ?)",
                    (storage_id, normalized, task_id, acquired_at.isoformat()),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def lock_owned(self, storage_id: str, path: str, task_id: str) -> bool:
        normalized = self._lock_path(path)
        with self._lock:
            row = self._connection.execute(
                "SELECT 1 FROM file_locks WHERE storage_id=? AND path=? AND task_id=?",
                (storage_id, normalized, task_id),
            ).fetchone()
        return row is not None

    def release(self, storage_id: str, path: str, task_id: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "DELETE FROM file_locks WHERE storage_id=? AND path=? AND task_id=?",
                (storage_id, self._lock_path(path), task_id),
            )

    def reclaim_task_locks(self, task_id: str) -> int:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "DELETE FROM file_locks WHERE task_id = ?", (task_id,)
            )
        return cursor.rowcount

    def _initialize(self) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_version "
                "(component TEXT PRIMARY KEY, version INTEGER NOT NULL)"
            )
            row = self._connection.execute(
                "SELECT version FROM schema_version WHERE component = 'runtime'"
            ).fetchone()
            if row and int(row["version"]) > SCHEMA_VERSION:
                raise ValueError("runtime database schema is newer than this MediaFlow version")
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY, command TEXT NOT NULL, status TEXT NOT NULL,
                    execute_authorized INTEGER NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, started_at TEXT, completed_at TEXT,
                    total_items INTEGER NOT NULL, completed_items INTEGER NOT NULL,
                    failed_items INTEGER NOT NULL, error TEXT,
                    pause_requested INTEGER NOT NULL DEFAULT 0,
                    scope_path TEXT, item_limit INTEGER,
                    configuration_snapshot_id TEXT, configuration_snapshot_digest TEXT
                );
                CREATE TABLE IF NOT EXISTS task_items (
                    item_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, storage_id TEXT NOT NULL,
                    resource_library_id TEXT NOT NULL, source_path TEXT NOT NULL,
                    source_display TEXT NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL,
                    attempts INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    plan_id TEXT, destination_storage_id TEXT, destination_path TEXT,
                    execution_status TEXT, error TEXT,
                    UNIQUE(task_id, storage_id, source_path),
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                );
                CREATE TABLE IF NOT EXISTS manual_ignore_audit (
                    decision_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                    item_id TEXT NOT NULL UNIQUE, review_kind TEXT NOT NULL,
                    review_id TEXT NOT NULL, decided_at TEXT NOT NULL,
                    actor TEXT NOT NULL, note TEXT,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id),
                    FOREIGN KEY(item_id) REFERENCES task_items(item_id)
                );
                CREATE INDEX IF NOT EXISTS manual_ignore_task_decided
                    ON manual_ignore_audit(task_id, decided_at, decision_id);
                CREATE TABLE IF NOT EXISTS task_retry_audit (
                    decision_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                    item_id TEXT NOT NULL UNIQUE, decided_at TEXT NOT NULL,
                    actor TEXT NOT NULL, note TEXT,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id),
                    FOREIGN KEY(item_id) REFERENCES task_items(item_id)
                );
                CREATE INDEX IF NOT EXISTS task_retry_task_decided
                    ON task_retry_audit(task_id, decided_at, decision_id);
                CREATE TABLE IF NOT EXISTS recovery_requests (
                    request_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                    item_id TEXT NOT NULL, action_id TEXT NOT NULL,
                    checkpoint_version TEXT NOT NULL,
                    source_storage_id TEXT NOT NULL, source_path TEXT NOT NULL,
                    configuration_snapshot_id TEXT,
                    configuration_snapshot_digest TEXT,
                    actor TEXT NOT NULL, requested_at TEXT NOT NULL,
                    status TEXT NOT NULL, note TEXT,
                    authority_statement TEXT NOT NULL,
                    next_action TEXT NOT NULL,
                    review_kind TEXT, review_id TEXT,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id),
                    FOREIGN KEY(item_id) REFERENCES task_items(item_id)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_recovery_request
                    ON recovery_requests(item_id) WHERE status = 'pending';
                CREATE INDEX IF NOT EXISTS recovery_requests_item_requested
                    ON recovery_requests(item_id, requested_at, request_id);
                CREATE TABLE IF NOT EXISTS recovery_continuations (
                    continuation_id TEXT PRIMARY KEY, request_id TEXT NOT NULL,
                    source_task_id TEXT NOT NULL, source_item_id TEXT NOT NULL,
                    checkpoint_version TEXT NOT NULL,
                    configuration_snapshot_id TEXT NOT NULL,
                    configuration_snapshot_digest TEXT NOT NULL,
                    boundary TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, actor TEXT NOT NULL,
                    job_id TEXT NOT NULL UNIQUE, new_task_id TEXT, new_result_id TEXT,
                    started_at TEXT, completed_at TEXT, error TEXT, recovery TEXT,
                    authority_statement TEXT NOT NULL,
                    FOREIGN KEY(request_id) REFERENCES recovery_requests(request_id),
                    FOREIGN KEY(source_task_id) REFERENCES tasks(task_id),
                    FOREIGN KEY(source_item_id) REFERENCES task_items(item_id)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_recovery_continuation
                    ON recovery_continuations(request_id)
                    WHERE status IN ('queued', 'running');
                CREATE INDEX IF NOT EXISTS recovery_continuations_item_created
                    ON recovery_continuations(source_item_id, created_at, continuation_id);
                CREATE TABLE IF NOT EXISTS recovery_batches (
                    batch_id TEXT PRIMARY KEY, source_task_id TEXT NOT NULL, actor TEXT NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    FOREIGN KEY(source_task_id) REFERENCES tasks(task_id)
                );
                CREATE TABLE IF NOT EXISTS recovery_batch_items (
                    batch_item_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL,
                    source_task_id TEXT NOT NULL, source_item_id TEXT NOT NULL,
                    checkpoint_version TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    request_id TEXT, continuation_id TEXT, job_id TEXT,
                    reason TEXT, error TEXT, next_action TEXT,
                    FOREIGN KEY(batch_id) REFERENCES recovery_batches(batch_id),
                    FOREIGN KEY(source_task_id) REFERENCES tasks(task_id),
                    FOREIGN KEY(source_item_id) REFERENCES task_items(item_id),
                    FOREIGN KEY(request_id) REFERENCES recovery_requests(request_id),
                    FOREIGN KEY(continuation_id) REFERENCES recovery_continuations(continuation_id),
                    FOREIGN KEY(job_id) REFERENCES automation_jobs(job_id),
                    UNIQUE(batch_id, source_item_id)
                );
                CREATE INDEX IF NOT EXISTS recovery_batch_items_batch
                    ON recovery_batch_items(batch_id, source_item_id);
                CREATE TABLE IF NOT EXISTS task_results (
                    result_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, item_id TEXT NOT NULL,
                    source_storage_id TEXT NOT NULL, source_path TEXT NOT NULL,
                    destination_storage_id TEXT, destination_path TEXT, recognition_type TEXT,
                    provider TEXT, provider_id TEXT, metadata_policy_id TEXT,
                    naming_policy_id TEXT, classification_policy_id TEXT,
                    organize_policy_id TEXT, operation TEXT, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, title TEXT, error TEXT,
                    completed_operations TEXT NOT NULL DEFAULT '[]',
                    attachment_count INTEGER NOT NULL DEFAULT 0,
                    retry_attempts INTEGER NOT NULL DEFAULT 0,
                    retry_category TEXT,
                    cleanup_status TEXT,
                    cleanup_step_count INTEGER NOT NULL DEFAULT 0,
                    effect_certainty TEXT NOT NULL DEFAULT 'unknown',
                    uncertain_effects TEXT NOT NULL DEFAULT '[]',
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id),
                    FOREIGN KEY(item_id) REFERENCES task_items(item_id)
                );
                CREATE TABLE IF NOT EXISTS pipeline_evidence (
                    evidence_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                    item_id TEXT NOT NULL, attempts INTEGER NOT NULL,
                    source_storage_id TEXT NOT NULL, source_path TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    configuration_snapshot_id TEXT,
                    configuration_snapshot_digest TEXT,
                    outcome TEXT NOT NULL,
                    document TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id),
                    FOREIGN KEY(item_id) REFERENCES task_items(item_id)
                );
                CREATE INDEX IF NOT EXISTS pipeline_evidence_item_captured
                    ON pipeline_evidence(item_id, captured_at, evidence_id);
                CREATE INDEX IF NOT EXISTS pipeline_evidence_source_captured
                    ON pipeline_evidence(source_storage_id, source_path, captured_at, evidence_id);
                CREATE TABLE IF NOT EXISTS manual_intents (
                    intent_id TEXT PRIMARY KEY, actor TEXT NOT NULL,
                    configuration_snapshot_id TEXT NOT NULL,
                    configuration_snapshot_digest TEXT NOT NULL,
                    status TEXT NOT NULL, version INTEGER NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    next_action TEXT NOT NULL, error TEXT,
                    options_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS manual_intent_items (
                    item_id TEXT PRIMARY KEY, intent_id TEXT NOT NULL,
                    position INTEGER NOT NULL, file_id TEXT NOT NULL,
                    storage_id TEXT NOT NULL, resource_library_id TEXT NOT NULL,
                    source_path TEXT NOT NULL, filename TEXT NOT NULL,
                    extension TEXT NOT NULL, source_size INTEGER NOT NULL,
                    source_modified_at TEXT NOT NULL, source_last_seen_at TEXT NOT NULL,
                    source_updated_at TEXT NOT NULL, source_stable_since TEXT,
                    source_scan_status TEXT NOT NULL, source_last_scan_id TEXT,
                    choice_json TEXT NOT NULL, status TEXT NOT NULL,
                    error TEXT, version INTEGER NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(intent_id, position), UNIQUE(intent_id, file_id),
                    FOREIGN KEY(intent_id) REFERENCES manual_intents(intent_id)
                );
                CREATE INDEX IF NOT EXISTS manual_intent_items_order
                    ON manual_intent_items(intent_id, position, item_id);
                CREATE TABLE IF NOT EXISTS manual_intent_audit (
                    audit_id TEXT PRIMARY KEY, intent_id TEXT NOT NULL,
                    item_id TEXT, actor TEXT NOT NULL, action TEXT NOT NULL,
                    before_json TEXT NOT NULL, after_json TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    FOREIGN KEY(intent_id) REFERENCES manual_intents(intent_id),
                    FOREIGN KEY(item_id) REFERENCES manual_intent_items(item_id)
                );
                CREATE INDEX IF NOT EXISTS manual_intent_audit_order
                    ON manual_intent_audit(intent_id, occurred_at, audit_id);
                CREATE TABLE IF NOT EXISTS manual_previews (
                    preview_id TEXT PRIMARY KEY, intent_id TEXT NOT NULL,
                    actor TEXT NOT NULL, configuration_snapshot_id TEXT NOT NULL,
                    configuration_snapshot_digest TEXT NOT NULL, status TEXT NOT NULL,
                    intent_version INTEGER NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, next_action TEXT NOT NULL, error TEXT,
                    zero_mutation INTEGER NOT NULL, current INTEGER NOT NULL DEFAULT 1,
                    truncated INTEGER NOT NULL DEFAULT 0, previous_preview_id TEXT,
                    unselected_item_ids_json TEXT NOT NULL,
                    FOREIGN KEY(intent_id) REFERENCES manual_intents(intent_id)
                );
                CREATE INDEX IF NOT EXISTS manual_previews_intent_created
                    ON manual_previews(intent_id, created_at, preview_id);
                CREATE TABLE IF NOT EXISTS manual_preview_items (
                    preview_item_id TEXT PRIMARY KEY, preview_id TEXT NOT NULL,
                    intent_id TEXT NOT NULL, item_id TEXT NOT NULL, position INTEGER NOT NULL,
                    intent_version INTEGER NOT NULL, item_version INTEGER NOT NULL,
                    source_json TEXT NOT NULL, choice_json TEXT NOT NULL,
                    configuration_snapshot_id TEXT NOT NULL,
                    configuration_snapshot_digest TEXT NOT NULL,
                    source_fingerprint TEXT NOT NULL,
                    source_evidence_versions_json TEXT NOT NULL,
                    review_versions_json TEXT NOT NULL,
                    conflict_versions_json TEXT NOT NULL,
                    input_fingerprint TEXT NOT NULL, plan_fingerprint TEXT,
                    status TEXT NOT NULL, plan_json TEXT, error TEXT,
                    next_action TEXT NOT NULL, zero_mutation INTEGER NOT NULL,
                    execution_state TEXT NOT NULL, truncated INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    current INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(preview_id, item_id),
                    FOREIGN KEY(preview_id) REFERENCES manual_previews(preview_id),
                    FOREIGN KEY(intent_id) REFERENCES manual_intents(intent_id)
                );
                CREATE INDEX IF NOT EXISTS manual_preview_items_intent_current
                    ON manual_preview_items(intent_id, item_id, current);
                CREATE INDEX IF NOT EXISTS manual_preview_items_preview_order
                    ON manual_preview_items(preview_id, position, item_id);
                CREATE TABLE IF NOT EXISTS automation_task_definition_previews (
                    preview_id TEXT PRIMARY KEY, definition_id TEXT NOT NULL,
                    definition_fingerprint TEXT NOT NULL,
                    configuration_revision_id TEXT NOT NULL,
                    configuration_revision_version INTEGER NOT NULL,
                    configuration_revision_digest TEXT NOT NULL,
                    configuration_status TEXT NOT NULL,
                    resource_library_id TEXT NOT NULL, storage_id TEXT NOT NULL,
                    source_scope TEXT, run_mode TEXT NOT NULL,
                    effective_item_limit INTEGER NOT NULL, counts_json TEXT NOT NULL,
                    status TEXT NOT NULL, actor TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    next_action TEXT NOT NULL, error TEXT,
                    zero_mutation INTEGER NOT NULL, current INTEGER NOT NULL DEFAULT 1,
                    stale_reason TEXT, truncated INTEGER NOT NULL DEFAULT 0,
                    boundary_errors_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS automation_previews_definition_created
                    ON automation_task_definition_previews(definition_id, created_at, preview_id);
                CREATE TABLE IF NOT EXISTS automation_task_definition_preview_items (
                    preview_item_id TEXT PRIMARY KEY, preview_id TEXT NOT NULL,
                    definition_id TEXT NOT NULL, position INTEGER NOT NULL,
                    source_json TEXT NOT NULL, source_fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL, next_action TEXT NOT NULL,
                    recognition_status TEXT, recognition_rule_id TEXT,
                    recognition_type_id TEXT, recognition_type_policy_id TEXT,
                    metadata_policy_id TEXT, naming_policy_id TEXT,
                    classification_policy_id TEXT, organize_policy_id TEXT,
                    metadata_provider TEXT, metadata_provider_id TEXT, media_type TEXT,
                    metadata_status TEXT, metadata_title TEXT, metadata_year INTEGER,
                    naming_directory TEXT, naming_filename TEXT,
                    classification_media_library_id TEXT, classification_relative_path TEXT,
                    destination_storage_id TEXT, destination_path TEXT, operation TEXT,
                    attachments_json TEXT, required_capabilities_json TEXT,
                    declared_capabilities_json TEXT, capability_verdict TEXT,
                    conflict_strategy TEXT, conflicts_json TEXT, warnings_json TEXT,
                    plan_fingerprint TEXT, plan_json TEXT, blocker TEXT,
                    zero_mutation INTEGER NOT NULL, current INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(preview_id, position),
                    FOREIGN KEY(preview_id)
                        REFERENCES automation_task_definition_previews(preview_id)
                );
                CREATE INDEX IF NOT EXISTS automation_preview_items_preview_order
                    ON automation_task_definition_preview_items(preview_id, position);
                CREATE TABLE IF NOT EXISTS manual_execution_authorizations (
                    authorization_id TEXT PRIMARY KEY, preview_id TEXT NOT NULL,
                    intent_id TEXT NOT NULL, intent_version INTEGER NOT NULL,
                    configuration_snapshot_id TEXT NOT NULL,
                    configuration_snapshot_digest TEXT NOT NULL, actor TEXT NOT NULL,
                    permission TEXT NOT NULL, confirmation INTEGER NOT NULL,
                    allow_overwrite INTEGER NOT NULL DEFAULT 0,
                    allow_source_cleanup INTEGER NOT NULL DEFAULT 0,
                    scope_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL, status TEXT NOT NULL,
                    consumed_at TEXT, execution_id TEXT, note TEXT,
                    FOREIGN KEY(preview_id) REFERENCES manual_previews(preview_id),
                    FOREIGN KEY(intent_id) REFERENCES manual_intents(intent_id)
                );
                CREATE INDEX IF NOT EXISTS manual_execution_authorizations_status
                    ON manual_execution_authorizations(status, expires_at, created_at);
                CREATE TABLE IF NOT EXISTS manual_execution_authorization_audit (
                    audit_id TEXT PRIMARY KEY, authorization_id TEXT NOT NULL,
                    action TEXT NOT NULL, occurred_at TEXT NOT NULL, actor TEXT,
                    execution_id TEXT, details_json TEXT NOT NULL,
                    FOREIGN KEY(authorization_id)
                        REFERENCES manual_execution_authorizations(authorization_id)
                );
                CREATE INDEX IF NOT EXISTS manual_execution_authorization_audit_time
                    ON manual_execution_authorization_audit(
                        authorization_id, occurred_at, audit_id
                    );
                CREATE TABLE IF NOT EXISTS manual_executions (
                    execution_id TEXT PRIMARY KEY, preview_id TEXT NOT NULL,
                    intent_id TEXT NOT NULL, authorization_id TEXT NOT NULL UNIQUE,
                    task_id TEXT NOT NULL UNIQUE, actor TEXT NOT NULL,
                    intent_version INTEGER NOT NULL, configuration_snapshot_id TEXT NOT NULL,
                    configuration_snapshot_digest TEXT NOT NULL,
                    selected_item_ids_json TEXT NOT NULL, unselected_item_ids_json TEXT NOT NULL,
                    status TEXT NOT NULL, next_action TEXT NOT NULL, error TEXT,
                    allow_overwrite INTEGER NOT NULL DEFAULT 0,
                    allow_source_cleanup INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, completed_at TEXT,
                    FOREIGN KEY(preview_id) REFERENCES manual_previews(preview_id),
                    FOREIGN KEY(intent_id) REFERENCES manual_intents(intent_id),
                    FOREIGN KEY(authorization_id)
                        REFERENCES manual_execution_authorizations(authorization_id),
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                );
                CREATE INDEX IF NOT EXISTS manual_executions_preview_created
                    ON manual_executions(preview_id, created_at, execution_id);
                CREATE TABLE IF NOT EXISTS manual_execution_items (
                    execution_item_id TEXT PRIMARY KEY, execution_id TEXT NOT NULL,
                    preview_id TEXT NOT NULL, preview_item_id TEXT NOT NULL,
                    intent_id TEXT NOT NULL, item_id TEXT NOT NULL,
                    task_id TEXT NOT NULL, task_item_id TEXT NOT NULL UNIQUE,
                    item_version INTEGER NOT NULL, source_fingerprint TEXT NOT NULL,
                    plan_fingerprint TEXT NOT NULL, source_json TEXT NOT NULL,
                    choice_json TEXT NOT NULL, plan_json TEXT NOT NULL,
                    status TEXT NOT NULL, stage TEXT NOT NULL, result_id TEXT,
                    effect_certainty TEXT NOT NULL, completed_operations TEXT NOT NULL,
                    uncertain_effects TEXT NOT NULL, error TEXT, next_action TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(preview_id, item_id), UNIQUE(execution_id, item_id),
                    FOREIGN KEY(execution_id) REFERENCES manual_executions(execution_id),
                    FOREIGN KEY(preview_id) REFERENCES manual_previews(preview_id),
                    FOREIGN KEY(preview_item_id) REFERENCES manual_preview_items(preview_item_id),
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id),
                    FOREIGN KEY(task_item_id) REFERENCES task_items(item_id),
                    FOREIGN KEY(result_id) REFERENCES task_results(result_id)
                );
                CREATE INDEX IF NOT EXISTS manual_execution_items_execution_order
                    ON manual_execution_items(execution_id, item_id, execution_item_id);
                CREATE TABLE IF NOT EXISTS manual_execution_effects (
                    effect_id TEXT PRIMARY KEY, execution_item_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL, action TEXT NOT NULL,
                    source_storage_id TEXT, source_path TEXT,
                    destination_storage_id TEXT, destination_path TEXT,
                    verified INTEGER NOT NULL, certainty TEXT NOT NULL,
                    details_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    UNIQUE(execution_item_id, sequence),
                    FOREIGN KEY(execution_item_id)
                        REFERENCES manual_execution_items(execution_item_id)
                );
                CREATE INDEX IF NOT EXISTS manual_execution_effects_item_order
                    ON manual_execution_effects(execution_item_id, sequence, effect_id);
                CREATE TABLE IF NOT EXISTS file_locks (
                    storage_id TEXT NOT NULL, path TEXT NOT NULL, task_id TEXT NOT NULL,
                    acquired_at TEXT NOT NULL, PRIMARY KEY(storage_id, path)
                );
                CREATE INDEX IF NOT EXISTS task_items_task_status
                    ON task_items(task_id, status);
                CREATE TABLE IF NOT EXISTS conflict_confirmations (
                    confirmation_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, item_id TEXT NOT NULL,
                    plan_id TEXT NOT NULL, conflict_type TEXT NOT NULL,
                    source_storage_id TEXT NOT NULL, source_path TEXT NOT NULL,
                    destination_storage_id TEXT NOT NULL, destination_path TEXT NOT NULL,
                    configured_strategy TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    selected_strategy TEXT, proposed_destination_path TEXT,
                    overwrite_authorized INTEGER NOT NULL DEFAULT 0,
                    actor TEXT, note TEXT,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id),
                    FOREIGN KEY(item_id) REFERENCES task_items(item_id)
                );
                CREATE TABLE IF NOT EXISTS conflict_decision_audit (
                    audit_id TEXT PRIMARY KEY, confirmation_id TEXT NOT NULL,
                    strategy TEXT NOT NULL, decided_at TEXT NOT NULL,
                    overwrite_authorized INTEGER NOT NULL, actor TEXT, note TEXT,
                    FOREIGN KEY(confirmation_id) REFERENCES conflict_confirmations(confirmation_id)
                );
                CREATE INDEX IF NOT EXISTS confirmations_status
                    ON conflict_confirmations(status, created_at);
                CREATE TABLE IF NOT EXISTS metadata_corrections (
                    review_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                    item_id TEXT NOT NULL UNIQUE, source_storage_id TEXT NOT NULL,
                    source_path TEXT NOT NULL, recognition_type TEXT NOT NULL,
                    metadata_policy_id TEXT NOT NULL, provider_id TEXT NOT NULL,
                    original_query TEXT NOT NULL, original_year INTEGER,
                    original_media_type TEXT NOT NULL, outcome TEXT NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    corrected_query TEXT, corrected_year INTEGER, corrected_media_type TEXT,
                    direct_provider_id TEXT, decided_at TEXT, actor TEXT,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id),
                    FOREIGN KEY(item_id) REFERENCES task_items(item_id)
                );
                CREATE TABLE IF NOT EXISTS metadata_correction_decision_audit (
                    audit_id TEXT PRIMARY KEY, review_id TEXT NOT NULL,
                    corrected_query TEXT, corrected_year INTEGER,
                    corrected_media_type TEXT NOT NULL, direct_provider_id TEXT,
                    decided_at TEXT NOT NULL, actor TEXT, note TEXT,
                    FOREIGN KEY(review_id) REFERENCES metadata_corrections(review_id)
                );
                CREATE INDEX IF NOT EXISTS metadata_corrections_status_created
                    ON metadata_corrections(status, created_at, review_id);
                CREATE TABLE IF NOT EXISTS metadata_correction_continuations (
                    continuation_id TEXT PRIMARY KEY, file_id TEXT NOT NULL,
                    review_id TEXT NOT NULL, source_task_id TEXT NOT NULL,
                    source_item_id TEXT NOT NULL,
                    configuration_snapshot_id TEXT NOT NULL,
                    configuration_snapshot_digest TEXT NOT NULL,
                    correction_version TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, actor TEXT NOT NULL,
                    job_id TEXT NOT NULL UNIQUE, new_task_id TEXT, new_result_id TEXT,
                    started_at TEXT, completed_at TEXT, error TEXT, recovery TEXT,
                    FOREIGN KEY(review_id) REFERENCES metadata_corrections(review_id),
                    FOREIGN KEY(source_task_id) REFERENCES tasks(task_id),
                    FOREIGN KEY(source_item_id) REFERENCES task_items(item_id)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_metadata_correction_continuation
                    ON metadata_correction_continuations(review_id)
                    WHERE status IN ('queued', 'running');
                CREATE INDEX IF NOT EXISTS metadata_correction_continuations_review_created
                    ON metadata_correction_continuations(review_id, created_at, continuation_id);
                CREATE TABLE IF NOT EXISTS recognition_reviews (
                    review_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                    item_id TEXT NOT NULL UNIQUE, source_storage_id TEXT NOT NULL,
                    source_path TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    selected_recognition_type TEXT, decided_at TEXT, actor TEXT,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id),
                    FOREIGN KEY(item_id) REFERENCES task_items(item_id)
                );
                CREATE TABLE IF NOT EXISTS recognition_review_choices (
                    review_id TEXT NOT NULL, recognition_type_id TEXT NOT NULL,
                    name TEXT NOT NULL, description TEXT NOT NULL,
                    PRIMARY KEY(review_id, recognition_type_id),
                    FOREIGN KEY(review_id) REFERENCES recognition_reviews(review_id)
                );
                CREATE TABLE IF NOT EXISTS recognition_review_decision_audit (
                    audit_id TEXT PRIMARY KEY, review_id TEXT NOT NULL,
                    recognition_type_id TEXT NOT NULL, decided_at TEXT NOT NULL,
                    actor TEXT, note TEXT,
                    FOREIGN KEY(review_id) REFERENCES recognition_reviews(review_id)
                );
                CREATE TABLE IF NOT EXISTS recognition_retry_audit (
                    decision_id TEXT PRIMARY KEY, review_id TEXT NOT NULL UNIQUE,
                    task_id TEXT NOT NULL, item_id TEXT NOT NULL UNIQUE,
                    decided_at TEXT NOT NULL, actor TEXT NOT NULL, note TEXT,
                    FOREIGN KEY(review_id) REFERENCES recognition_reviews(review_id),
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id),
                    FOREIGN KEY(item_id) REFERENCES task_items(item_id)
                );
                CREATE INDEX IF NOT EXISTS recognition_reviews_status_created
                    ON recognition_reviews(status, created_at, review_id);
                CREATE TABLE IF NOT EXISTS metadata_reviews (
                    review_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                    item_id TEXT NOT NULL UNIQUE, source_storage_id TEXT NOT NULL,
                    source_path TEXT NOT NULL, recognition_type TEXT NOT NULL,
                    metadata_policy_id TEXT NOT NULL, query TEXT NOT NULL,
                    outcome TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    selected_rank INTEGER, selected_provider TEXT,
                    selected_provider_id TEXT, selected_media_type TEXT,
                    decided_at TEXT, actor TEXT,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id),
                    FOREIGN KEY(item_id) REFERENCES task_items(item_id)
                );
                CREATE TABLE IF NOT EXISTS metadata_review_candidates (
                    review_id TEXT NOT NULL, rank INTEGER NOT NULL,
                    provider TEXT NOT NULL, provider_id TEXT NOT NULL,
                    media_type TEXT NOT NULL, title TEXT NOT NULL,
                    original_title TEXT, canonical_year INTEGER, regional_year INTEGER,
                    total_score REAL NOT NULL, matched_provider_title TEXT,
                    matched_title_source TEXT, score_components TEXT NOT NULL,
                    PRIMARY KEY(review_id, rank),
                    FOREIGN KEY(review_id) REFERENCES metadata_reviews(review_id)
                );
                CREATE INDEX IF NOT EXISTS metadata_reviews_status_created
                    ON metadata_reviews(status, created_at, review_id);
                CREATE TABLE IF NOT EXISTS metadata_review_decision_audit (
                    audit_id TEXT PRIMARY KEY, review_id TEXT NOT NULL,
                    selected_rank INTEGER NOT NULL, provider TEXT NOT NULL,
                    provider_id TEXT NOT NULL, media_type TEXT NOT NULL,
                    decided_at TEXT NOT NULL, actor TEXT, note TEXT,
                    FOREIGN KEY(review_id) REFERENCES metadata_reviews(review_id)
                );
                CREATE TABLE IF NOT EXISTS classification_reviews (
                    review_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                    item_id TEXT NOT NULL UNIQUE, source_storage_id TEXT NOT NULL,
                    source_path TEXT NOT NULL, recognition_type TEXT NOT NULL,
                    classification_policy_id TEXT NOT NULL, provider TEXT NOT NULL,
                    provider_id TEXT NOT NULL, media_type TEXT NOT NULL, title TEXT NOT NULL,
                    canonical_year INTEGER, status TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, selected_rank INTEGER, selected_rule_id TEXT,
                    selected_media_library_id TEXT, selected_relative_path TEXT,
                    decided_at TEXT, actor TEXT,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id),
                    FOREIGN KEY(item_id) REFERENCES task_items(item_id)
                );
                CREATE TABLE IF NOT EXISTS classification_review_choices (
                    review_id TEXT NOT NULL, rank INTEGER NOT NULL, rule_id TEXT NOT NULL,
                    rule_name TEXT NOT NULL, media_library_id TEXT NOT NULL,
                    relative_path TEXT NOT NULL, priority INTEGER NOT NULL,
                    description TEXT NOT NULL, PRIMARY KEY(review_id, rank),
                    FOREIGN KEY(review_id) REFERENCES classification_reviews(review_id)
                );
                CREATE TABLE IF NOT EXISTS classification_review_decision_audit (
                    audit_id TEXT PRIMARY KEY, review_id TEXT NOT NULL,
                    selected_rank INTEGER NOT NULL, rule_id TEXT NOT NULL,
                    media_library_id TEXT NOT NULL, relative_path TEXT NOT NULL,
                    decided_at TEXT NOT NULL, actor TEXT, note TEXT,
                    FOREIGN KEY(review_id) REFERENCES classification_reviews(review_id)
                );
                CREATE INDEX IF NOT EXISTS classification_reviews_status_created
                    ON classification_reviews(status, created_at, review_id);
                CREATE TABLE IF NOT EXISTS automation_jobs (
                    job_id TEXT PRIMARY KEY, command TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, limit_value INTEGER,
                    started_at TEXT, completed_at TEXT, task_id TEXT, error TEXT,
                    cancellation_requested INTEGER NOT NULL DEFAULT 0, schedule_id TEXT,
                    execute_authorized INTEGER NOT NULL DEFAULT 0, claim_token TEXT,
                    configuration_snapshot_id TEXT, configuration_snapshot_digest TEXT,
                    failure_category TEXT, failure_durable_state TEXT,
                    failure_side_effects TEXT, failure_retry_safe INTEGER,
                    failure_next_action TEXT
                );
                CREATE INDEX IF NOT EXISTS automation_jobs_status_created
                    ON automation_jobs(status, created_at, job_id);
                CREATE TABLE IF NOT EXISTS automation_schedules (
                    schedule_id TEXT PRIMARY KEY, next_run_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, last_job_id TEXT
                );
                CREATE TABLE IF NOT EXISTS schedule_audit (
                    audit_id TEXT PRIMARY KEY, schedule_id TEXT NOT NULL,
                    occurrence_at TEXT NOT NULL, emitted_at TEXT NOT NULL,
                    job_id TEXT NOT NULL UNIQUE, command TEXT NOT NULL,
                    next_run_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS schedule_audit_schedule_time
                    ON schedule_audit(schedule_id, emitted_at, audit_id);
                CREATE TABLE IF NOT EXISTS notification_deliveries (
                    delivery_id TEXT PRIMARY KEY, webhook_id TEXT NOT NULL,
                    event_id TEXT NOT NULL, event_type TEXT NOT NULL, body TEXT NOT NULL,
                    status TEXT NOT NULL, attempts INTEGER NOT NULL,
                    next_attempt_at TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, delivered_at TEXT, failure_category TEXT,
                    response_status INTEGER, UNIQUE(webhook_id, event_id)
                );
                CREATE INDEX IF NOT EXISTS notification_due
                    ON notification_deliveries(status, next_attempt_at, created_at);
                CREATE TABLE IF NOT EXISTS execution_authorizations (
                    authorization_id TEXT PRIMARY KEY, token_digest TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                    max_items INTEGER NOT NULL, actor TEXT, note TEXT, consumed_at TEXT,
                    consumed_job_id TEXT, revoked_at TEXT
                );
                CREATE TABLE IF NOT EXISTS execution_authorization_audit (
                    audit_id TEXT PRIMARY KEY, authorization_id TEXT NOT NULL,
                    action TEXT NOT NULL, occurred_at TEXT NOT NULL, job_id TEXT, actor TEXT,
                    FOREIGN KEY(authorization_id)
                        REFERENCES execution_authorizations(authorization_id)
                );
                CREATE INDEX IF NOT EXISTS execution_authorizations_status_expiry
                    ON execution_authorizations(status, expires_at);
                CREATE TABLE IF NOT EXISTS security_audit (
                    audit_id TEXT PRIMARY KEY, occurred_at TEXT NOT NULL, principal_id TEXT,
                    method TEXT NOT NULL, route TEXT NOT NULL, action TEXT NOT NULL,
                    outcome TEXT NOT NULL, http_status INTEGER NOT NULL,
                    request_id TEXT NOT NULL, source_address TEXT
                );
                CREATE INDEX IF NOT EXISTS security_audit_occurred
                    ON security_audit(occurred_at, audit_id);
                CREATE TABLE IF NOT EXISTS operational_logs (
                    log_id TEXT PRIMARY KEY, occurred_at TEXT NOT NULL, level INTEGER NOT NULL,
                    component TEXT NOT NULL, event TEXT NOT NULL, task_id TEXT, job_id TEXT,
                    plan_id TEXT, status TEXT
                );
                CREATE INDEX IF NOT EXISTS operational_logs_time
                    ON operational_logs(occurred_at, log_id);
                """
            )
            self._connection.execute(
                "INSERT OR REPLACE INTO schema_version VALUES ('runtime', ?)",
                (SCHEMA_VERSION,),
            )
            columns = {
                row["name"]
                for row in self._connection.execute("PRAGMA table_info(task_results)").fetchall()
            }
            task_columns = {
                row["name"]
                for row in self._connection.execute("PRAGMA table_info(tasks)").fetchall()
            }
            if "pause_requested" not in task_columns:
                self._connection.execute(
                    "ALTER TABLE tasks ADD COLUMN pause_requested INTEGER NOT NULL DEFAULT 0"
                )
            if "scope_path" not in task_columns:
                self._connection.execute("ALTER TABLE tasks ADD COLUMN scope_path TEXT")
            if "item_limit" not in task_columns:
                self._connection.execute("ALTER TABLE tasks ADD COLUMN item_limit INTEGER")
            if "configuration_snapshot_id" not in task_columns:
                self._connection.execute(
                    "ALTER TABLE tasks ADD COLUMN configuration_snapshot_id TEXT"
                )
            if "configuration_snapshot_digest" not in task_columns:
                self._connection.execute(
                    "ALTER TABLE tasks ADD COLUMN configuration_snapshot_digest TEXT"
                )
            job_columns = {
                row["name"]
                for row in self._connection.execute("PRAGMA table_info(automation_jobs)").fetchall()
            }
            if "configuration_snapshot_id" not in job_columns:
                self._connection.execute(
                    "ALTER TABLE automation_jobs ADD COLUMN configuration_snapshot_id TEXT"
                )
            if "configuration_snapshot_digest" not in job_columns:
                self._connection.execute(
                    "ALTER TABLE automation_jobs ADD COLUMN configuration_snapshot_digest TEXT"
                )
            for column, definition in (
                ("failure_category", "TEXT"),
                ("failure_durable_state", "TEXT"),
                ("failure_side_effects", "TEXT"),
                ("failure_retry_safe", "INTEGER"),
                ("failure_next_action", "TEXT"),
            ):
                if column not in job_columns:
                    self._connection.execute(
                        f"ALTER TABLE automation_jobs ADD COLUMN {column} {definition}"
                    )
            if "completed_operations" not in columns:
                self._connection.execute(
                    "ALTER TABLE task_results ADD COLUMN "
                    "completed_operations TEXT NOT NULL DEFAULT '[]'"
                )
            if "attachment_count" not in columns:
                self._connection.execute(
                    "ALTER TABLE task_results ADD COLUMN "
                    "attachment_count INTEGER NOT NULL DEFAULT 0"
                )
            if "retry_attempts" not in columns:
                self._connection.execute(
                    "ALTER TABLE task_results ADD COLUMN retry_attempts INTEGER NOT NULL DEFAULT 0"
                )
            if "retry_category" not in columns:
                self._connection.execute("ALTER TABLE task_results ADD COLUMN retry_category TEXT")
            if "cleanup_status" not in columns:
                self._connection.execute("ALTER TABLE task_results ADD COLUMN cleanup_status TEXT")
            if "cleanup_step_count" not in columns:
                self._connection.execute(
                    "ALTER TABLE task_results ADD COLUMN cleanup_step_count "
                    "INTEGER NOT NULL DEFAULT 0"
                )
            if "effect_certainty" not in columns:
                self._connection.execute(
                    "ALTER TABLE task_results ADD COLUMN effect_certainty "
                    "TEXT NOT NULL DEFAULT 'unknown'"
                )
            if "uncertain_effects" not in columns:
                self._connection.execute(
                    "ALTER TABLE task_results ADD COLUMN uncertain_effects "
                    "TEXT NOT NULL DEFAULT '[]'"
                )
            job_columns = {
                row["name"]
                for row in self._connection.execute("PRAGMA table_info(automation_jobs)").fetchall()
            }
            if "cancellation_requested" not in job_columns:
                self._connection.execute(
                    "ALTER TABLE automation_jobs ADD COLUMN "
                    "cancellation_requested INTEGER NOT NULL DEFAULT 0"
                )
            if "schedule_id" not in job_columns:
                self._connection.execute("ALTER TABLE automation_jobs ADD COLUMN schedule_id TEXT")
            if "execute_authorized" not in job_columns:
                self._connection.execute(
                    "ALTER TABLE automation_jobs ADD COLUMN "
                    "execute_authorized INTEGER NOT NULL DEFAULT 0"
                )
            if "claim_token" not in job_columns:
                self._connection.execute("ALTER TABLE automation_jobs ADD COLUMN claim_token TEXT")
            review_columns = {
                row["name"]
                for row in self._connection.execute(
                    "PRAGMA table_info(metadata_reviews)"
                ).fetchall()
            }
            for name, declaration in (
                ("selected_rank", "INTEGER"),
                ("selected_provider", "TEXT"),
                ("selected_provider_id", "TEXT"),
                ("selected_media_type", "TEXT"),
                ("decided_at", "TEXT"),
                ("actor", "TEXT"),
            ):
                if name not in review_columns:
                    self._connection.execute(
                        f"ALTER TABLE metadata_reviews ADD COLUMN {name} {declaration}"
                    )

    @staticmethod
    def _lock_path(path: str) -> str:
        parts = []
        for part in path.replace("\\", "/").split("/"):
            if not part or part == ".":
                continue
            if part == "..":
                raise ValueError("lock path must be Storage-relative and traversal-free")
            parts.append(part)
        if not parts:
            raise ValueError("lock path must be non-empty")
        return "/".join(parts)

    @staticmethod
    def _manual_execution_authorization_values(
        value: ManualExecutionAuthorization,
    ) -> tuple[object, ...]:
        return (
            value.authorization_id,
            value.preview_id,
            value.intent_id,
            value.intent_version,
            value.configuration_snapshot_id,
            value.configuration_snapshot_digest,
            value.actor,
            value.permission,
            int(value.confirmation),
            int(value.allow_overwrite),
            int(value.allow_source_cleanup),
            json.dumps(
                [item.document() for item in value.scope],
                ensure_ascii=False,
                sort_keys=True,
            ),
            value.created_at.isoformat(),
            value.expires_at.isoformat(),
            value.status.value,
            value.consumed_at.isoformat() if value.consumed_at else None,
            value.execution_id,
            redact_manual_text(value.note) if value.note is not None else None,
        )

    @staticmethod
    def _manual_execution_authorization(
        row: sqlite3.Row,
    ) -> ManualExecutionAuthorization:
        scope = tuple(
            ManualExecutionScopeItem(
                item["itemId"],
                item["previewItemId"],
                int(item["itemVersion"]),
                item["sourceFingerprint"],
                item["planFingerprint"],
                ManualSourceIdentity.from_document(item["source"]),
                ManualChoice.from_document(item["choice"]),
            )
            for item in json.loads(row["scope_json"])
        )
        return ManualExecutionAuthorization(
            row["authorization_id"],
            row["preview_id"],
            row["intent_id"],
            int(row["intent_version"]),
            row["configuration_snapshot_id"],
            row["configuration_snapshot_digest"],
            row["actor"],
            row["permission"],
            bool(row["confirmation"]),
            bool(row["allow_overwrite"]),
            bool(row["allow_source_cleanup"]),
            scope,
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["expires_at"]),
            ManualExecutionAuthorizationStatus(row["status"]),
            datetime.fromisoformat(row["consumed_at"]) if row["consumed_at"] else None,
            row["execution_id"],
            row["note"],
        )

    def _insert_manual_execution_authorization_audit(
        self, value: ManualExecutionAuthorizationAudit
    ) -> None:
        self._connection.execute(
            """INSERT INTO manual_execution_authorization_audit (
                audit_id, authorization_id, action, occurred_at, actor,
                execution_id, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                value.audit_id,
                value.authorization_id,
                value.action,
                value.occurred_at.isoformat(),
                value.actor,
                value.execution_id,
                json.dumps(redact_manual_value(value.details), ensure_ascii=False, sort_keys=True),
            ),
        )

    @staticmethod
    def _manual_execution_authorization_audit(
        row: sqlite3.Row,
    ) -> ManualExecutionAuthorizationAudit:
        return ManualExecutionAuthorizationAudit(
            row["audit_id"],
            row["authorization_id"],
            row["action"],
            datetime.fromisoformat(row["occurred_at"]),
            row["actor"],
            row["execution_id"],
            json.loads(row["details_json"] or "{}"),
        )

    @staticmethod
    def _manual_execution_values(value: ManualExecution) -> tuple[object, ...]:
        return (
            value.execution_id,
            value.preview_id,
            value.intent_id,
            value.authorization_id,
            value.task_id,
            value.actor,
            value.intent_version,
            value.configuration_snapshot_id,
            value.configuration_snapshot_digest,
            json.dumps(value.selected_item_ids, ensure_ascii=False),
            json.dumps(value.unselected_item_ids, ensure_ascii=False),
            value.status.value,
            redact_manual_text(value.next_action),
            redact_manual_text(value.error) if value.error is not None else None,
            int(value.allow_overwrite),
            int(value.allow_source_cleanup),
            value.created_at.isoformat(),
            value.updated_at.isoformat(),
            value.completed_at.isoformat() if value.completed_at else None,
        )

    @staticmethod
    def _manual_execution(
        row: sqlite3.Row, items: tuple[ManualExecutionItem, ...]
    ) -> ManualExecution:
        return ManualExecution(
            row["execution_id"],
            row["preview_id"],
            row["intent_id"],
            row["authorization_id"],
            row["task_id"],
            row["actor"],
            int(row["intent_version"]),
            row["configuration_snapshot_id"],
            row["configuration_snapshot_digest"],
            tuple(json.loads(row["selected_item_ids_json"])),
            tuple(json.loads(row["unselected_item_ids_json"])),
            items,
            ManualExecutionStatus(row["status"]),
            row["next_action"],
            row["error"],
            bool(row["allow_overwrite"]),
            bool(row["allow_source_cleanup"]),
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["updated_at"]),
            datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
        )

    @staticmethod
    def _manual_execution_item_values(value: ManualExecutionItem) -> tuple[object, ...]:
        return (
            value.execution_item_id,
            value.execution_id,
            value.preview_id,
            value.preview_item_id,
            value.intent_id,
            value.item_id,
            value.task_id,
            value.task_item_id,
            value.item_version,
            value.source_fingerprint,
            value.plan_fingerprint,
            json.dumps(value.source.document(), ensure_ascii=False, sort_keys=True),
            json.dumps(value.choice.document(), ensure_ascii=False, sort_keys=True),
            json.dumps(value.plan, ensure_ascii=False, sort_keys=True),
            value.status.value,
            value.stage,
            value.result_id,
            value.effect_certainty,
            json.dumps(value.completed_operations, ensure_ascii=False),
            json.dumps(value.uncertain_effects, ensure_ascii=False),
            redact_manual_text(value.error) if value.error is not None else None,
            redact_manual_text(value.next_action),
            value.created_at.isoformat(),
            value.updated_at.isoformat(),
        )

    @staticmethod
    def _manual_execution_item(
        row: sqlite3.Row, effects: tuple[ManualExecutionEffect, ...]
    ) -> ManualExecutionItem:
        return ManualExecutionItem(
            row["execution_item_id"],
            row["execution_id"],
            row["preview_id"],
            row["preview_item_id"],
            row["intent_id"],
            row["item_id"],
            row["task_id"],
            row["task_item_id"],
            int(row["item_version"]),
            row["source_fingerprint"],
            row["plan_fingerprint"],
            ManualSourceIdentity.from_document(json.loads(row["source_json"])),
            ManualChoice.from_document(json.loads(row["choice_json"])),
            json.loads(row["plan_json"]),
            ManualExecutionItemStatus(row["status"]),
            row["stage"],
            row["result_id"],
            row["effect_certainty"],
            tuple(json.loads(row["completed_operations"] or "[]")),
            tuple(json.loads(row["uncertain_effects"] or "[]")),
            row["error"],
            row["next_action"],
            effects,
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _manual_execution_effect_values(value: ManualExecutionEffect) -> tuple[object, ...]:
        return (
            value.effect_id,
            value.execution_item_id,
            value.sequence,
            value.action,
            value.source_storage_id,
            value.source_path,
            value.destination_storage_id,
            value.destination_path,
            int(value.verified),
            value.certainty,
            json.dumps(redact_manual_value(value.details), ensure_ascii=False, sort_keys=True),
            value.created_at.isoformat(),
        )

    @staticmethod
    def _manual_execution_effect(row: sqlite3.Row) -> ManualExecutionEffect:
        return ManualExecutionEffect(
            row["effect_id"],
            row["execution_item_id"],
            int(row["sequence"]),
            row["action"],
            row["source_storage_id"],
            row["source_path"],
            row["destination_storage_id"],
            row["destination_path"],
            bool(row["verified"]),
            row["certainty"],
            json.loads(row["details_json"] or "{}"),
            datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _manual_task_item(
        value: ManualExecutionItem, execution: ManualExecution, now: datetime
    ) -> PersistentTaskItem:
        destination = value.plan.get("executionPlan")
        destination_storage_id = (
            destination.get("targetStorageId") if isinstance(destination, dict) else None
        )
        destination_path = destination.get("targetPath") if isinstance(destination, dict) else None
        plan_id = value.plan.get("planId")
        return PersistentTaskItem(
            value.task_item_id,
            execution.task_id,
            value.source.storage_id,
            value.source.resource_library_id,
            value.source.path,
            f"{value.source.storage_id}:{value.source.path}",
            TaskItemStatus.PENDING,
            "admitted",
            0,
            value.created_at,
            now,
            plan_id if isinstance(plan_id, str) else None,
            destination_storage_id if isinstance(destination_storage_id, str) else None,
            destination_path if isinstance(destination_path, str) else None,
            None,
            None,
        )

    def _insert_result_locked(self, result: PersistentResultRecord) -> None:
        self._connection.execute(
            """INSERT OR REPLACE INTO task_results (
                result_id, task_id, item_id, source_storage_id, source_path,
                destination_storage_id, destination_path, recognition_type, provider,
                provider_id, metadata_policy_id, naming_policy_id, classification_policy_id,
                organize_policy_id, operation, status, created_at, title, error,
                completed_operations, attachment_count, retry_attempts, retry_category,
                cleanup_status, cleanup_step_count, effect_certainty, uncertain_effects
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?)""",
            self._result_values(result),
        )

    @staticmethod
    def _result_values(result: PersistentResultRecord) -> tuple[object, ...]:
        result = redact_persistent_result(result)
        return (
            result.result_id,
            result.task_id,
            result.item_id,
            result.source_storage_id,
            result.source_path,
            result.destination_storage_id,
            result.destination_path,
            result.recognition_type,
            result.provider,
            result.provider_id,
            result.metadata_policy_id,
            result.naming_policy_id,
            result.classification_policy_id,
            result.organize_policy_id,
            result.operation,
            result.status,
            result.created_at.isoformat(),
            result.title,
            result.error,
            json.dumps(result.completed_operations, ensure_ascii=False),
            result.attachment_count,
            result.retry_attempts,
            result.retry_category,
            result.cleanup_status,
            result.cleanup_step_count,
            result.effect_certainty,
            json.dumps(result.uncertain_effects, ensure_ascii=False),
        )

    @staticmethod
    def _task_values(task: PersistentTask) -> tuple[object, ...]:
        return (
            task.task_id,
            task.command,
            task.status.value,
            int(task.execute_authorized),
            task.created_at.isoformat(),
            task.updated_at.isoformat(),
            task.started_at.isoformat() if task.started_at else None,
            task.completed_at.isoformat() if task.completed_at else None,
            task.total_items,
            task.completed_items,
            task.failed_items,
            task.error,
            int(task.pause_requested),
            task.scope_path,
            task.item_limit,
            task.configuration_snapshot_id,
            task.configuration_snapshot_digest,
        )

    @staticmethod
    def _item_values(item: PersistentTaskItem) -> tuple[object, ...]:
        return (
            item.item_id,
            item.task_id,
            item.storage_id,
            item.resource_library_id,
            item.source_path,
            item.source_display,
            item.status.value,
            item.stage,
            item.attempts,
            item.created_at.isoformat(),
            item.updated_at.isoformat(),
            item.plan_id,
            item.destination_storage_id,
            item.destination_path,
            item.execution_status,
            item.error,
        )

    @staticmethod
    def _task(row: sqlite3.Row) -> PersistentTask:
        return PersistentTask(
            row["task_id"],
            row["command"],
            PersistentTaskStatus(row["status"]),
            bool(row["execute_authorized"]),
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["updated_at"]),
            datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            row["total_items"],
            row["completed_items"],
            row["failed_items"],
            row["error"],
            bool(row["pause_requested"]),
            row["scope_path"],
            row["item_limit"],
            row["configuration_snapshot_id"],
            row["configuration_snapshot_digest"],
        )

    @staticmethod
    def _item(row: sqlite3.Row) -> PersistentTaskItem:
        return PersistentTaskItem(
            row["item_id"],
            row["task_id"],
            row["storage_id"],
            row["resource_library_id"],
            row["source_path"],
            row["source_display"],
            TaskItemStatus(row["status"]),
            row["stage"],
            row["attempts"],
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["updated_at"]),
            row["plan_id"],
            row["destination_storage_id"],
            row["destination_path"],
            row["execution_status"],
            row["error"],
        )

    @staticmethod
    def _result(row: sqlite3.Row) -> PersistentResultRecord:
        return redact_persistent_result(
            PersistentResultRecord(
                row["result_id"],
                row["task_id"],
                row["item_id"],
                row["source_storage_id"],
                row["source_path"],
                row["destination_storage_id"],
                row["destination_path"],
                row["recognition_type"],
                row["provider"],
                row["provider_id"],
                row["metadata_policy_id"],
                row["naming_policy_id"],
                row["classification_policy_id"],
                row["organize_policy_id"],
                row["operation"],
                row["status"],
                datetime.fromisoformat(row["created_at"]),
                row["title"],
                row["error"],
                tuple(json.loads(row["completed_operations"])),
                row["attachment_count"],
                row["retry_attempts"],
                row["retry_category"],
                row["cleanup_status"],
                row["cleanup_step_count"],
                row["effect_certainty"],
                tuple(json.loads(row["uncertain_effects"] or "[]")),
            )
        )

    @staticmethod
    def _evidence_values(evidence: PipelineEvidence) -> tuple[object, ...]:
        source_path = redact_evidence_text(evidence.source_path)
        evidence = redact_pipeline_evidence(evidence)
        return (
            evidence.evidence_id,
            evidence.task_id,
            evidence.item_id,
            evidence.attempts,
            evidence.source_storage_id,
            source_path,
            evidence.captured_at.isoformat(),
            evidence.configuration_snapshot_id,
            evidence.configuration_snapshot_digest,
            evidence.outcome,
            json.dumps(evidence.document(), ensure_ascii=False, sort_keys=True),
        )

    @staticmethod
    def _evidence(row: sqlite3.Row) -> PipelineEvidence:
        return evidence_from_document(json.loads(row["document"]))

    @staticmethod
    def _recovery_request_values(request: RecoveryRequest) -> tuple[object, ...]:
        return (
            request.request_id,
            request.task_id,
            request.item_id,
            request.action_id,
            request.checkpoint_version,
            request.source_storage_id,
            request.source_path,
            request.configuration_snapshot_id,
            request.configuration_snapshot_digest,
            request.actor,
            request.requested_at.isoformat(),
            request.status.value,
            request.note,
            request.authority_statement,
            request.next_action,
            request.review_kind,
            request.review_id,
        )

    @staticmethod
    def _recovery_request(row: sqlite3.Row) -> RecoveryRequest:
        try:
            status = RecoveryRequestStatus(row["status"])
        except ValueError:
            status = RecoveryRequestStatus.REJECTED
        return RecoveryRequest(
            row["request_id"],
            row["task_id"],
            row["item_id"],
            row["action_id"],
            row["checkpoint_version"],
            row["source_storage_id"],
            row["source_path"],
            row["configuration_snapshot_id"],
            row["configuration_snapshot_digest"],
            row["actor"],
            datetime.fromisoformat(row["requested_at"]),
            status,
            row["note"],
            row["authority_statement"],
            row["next_action"],
            row["review_kind"],
            row["review_id"],
        )

    @staticmethod
    def _recovery_continuation_values(
        continuation: RecoveryContinuation,
    ) -> tuple[object, ...]:
        return (
            continuation.continuation_id,
            continuation.request_id,
            continuation.source_task_id,
            continuation.source_item_id,
            continuation.checkpoint_version,
            continuation.configuration_snapshot_id,
            continuation.configuration_snapshot_digest,
            continuation.boundary,
            continuation.status.value,
            continuation.created_at.isoformat(),
            continuation.updated_at.isoformat(),
            continuation.actor,
            continuation.job_id,
            continuation.new_task_id,
            continuation.new_result_id,
            continuation.started_at.isoformat() if continuation.started_at else None,
            continuation.completed_at.isoformat() if continuation.completed_at else None,
            continuation.error,
            continuation.recovery,
            continuation.authority_statement,
        )

    @staticmethod
    def _recovery_batch_item_values(item: RecoveryBatchItem) -> tuple[object, ...]:
        return (
            item.batch_item_id,
            item.batch_id,
            item.source_task_id,
            item.source_item_id,
            item.checkpoint_version,
            item.status.value,
            item.created_at.isoformat(),
            item.updated_at.isoformat(),
            item.request_id,
            item.continuation_id,
            item.job_id,
            item.reason,
            item.error,
            item.next_action,
        )

    @staticmethod
    def _recovery_batch_item(row: sqlite3.Row) -> RecoveryBatchItem:
        status = RecoveryBatchItemStatus(row["status"])
        continuation_status = row["continuation_status"]
        if continuation_status:
            status = {
                RecoveryContinuationStatus.QUEUED.value: RecoveryBatchItemStatus.QUEUED,
                RecoveryContinuationStatus.RUNNING.value: RecoveryBatchItemStatus.RUNNING,
                RecoveryContinuationStatus.COMPLETED.value: RecoveryBatchItemStatus.COMPLETED,
                RecoveryContinuationStatus.FAILED.value: RecoveryBatchItemStatus.FAILED,
                RecoveryContinuationStatus.CANCELLED.value: RecoveryBatchItemStatus.CANCELLED,
            }.get(continuation_status, status)
        new_task_id = row["continuation_new_task_id"]
        new_result_id = row["continuation_new_result_id"]
        recovery_status = continuation_status
        recovery_action = row["continuation_recovery"]
        return RecoveryBatchItem(
            row["batch_item_id"],
            row["batch_id"],
            row["source_task_id"],
            row["source_item_id"],
            row["checkpoint_version"],
            status,
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["updated_at"]),
            row["request_id"],
            row["continuation_id"],
            row["job_id"],
            new_task_id,
            new_result_id,
            recovery_status,
            recovery_action,
            row["reason"],
            row["continuation_error"] or row["error"],
            (
                row["continuation_recovery"]
                or {
                    RecoveryContinuationStatus.QUEUED.value: (
                        "wait for the Worker, then inspect the linked DryRun Task/Result"
                    ),
                    RecoveryContinuationStatus.RUNNING.value: (
                        "wait for the Worker, then inspect the linked DryRun Task/Result"
                    ),
                    RecoveryContinuationStatus.COMPLETED.value: (
                        "inspect the linked DryRun Task/Result; the source item remains unchanged"
                    ),
                    RecoveryContinuationStatus.CANCELLED.value: (
                        "refresh the Task item checkpoint and explicitly continue again"
                    ),
                }.get(row["continuation_status"])
                if row["continuation_status"]
                else row["next_action"]
            ),
        )

    @staticmethod
    def _recovery_continuation(row: sqlite3.Row) -> RecoveryContinuation:
        try:
            status = RecoveryContinuationStatus(row["status"])
        except ValueError:
            status = RecoveryContinuationStatus.FAILED
        return RecoveryContinuation(
            row["continuation_id"],
            row["request_id"],
            row["source_task_id"],
            row["source_item_id"],
            row["checkpoint_version"],
            row["configuration_snapshot_id"],
            row["configuration_snapshot_digest"],
            row["boundary"],
            status,
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["updated_at"]),
            row["actor"],
            row["job_id"],
            row["new_task_id"],
            row["new_result_id"],
            datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            row["error"],
            row["recovery"],
            row["authority_statement"],
        )

    @staticmethod
    def _confirmation_values(value: ConflictConfirmation) -> tuple[object, ...]:
        return (
            value.confirmation_id,
            value.task_id,
            value.item_id,
            value.plan_id,
            value.conflict_type,
            value.source_storage_id,
            value.source_path,
            value.destination_storage_id,
            value.destination_path,
            value.configured_strategy,
            value.status.value,
            value.created_at.isoformat(),
            value.updated_at.isoformat(),
            value.selected_strategy,
            value.proposed_destination_path,
            int(value.overwrite_authorized),
            value.actor,
            value.note,
        )

    @staticmethod
    def _confirmation(row: sqlite3.Row) -> ConflictConfirmation:
        return ConflictConfirmation(
            row["confirmation_id"],
            row["task_id"],
            row["item_id"],
            row["plan_id"],
            row["conflict_type"],
            row["source_storage_id"],
            row["source_path"],
            row["destination_storage_id"],
            row["destination_path"],
            row["configured_strategy"],
            ConfirmationStatus(row["status"]),
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["updated_at"]),
            row["selected_strategy"],
            row["proposed_destination_path"],
            bool(row["overwrite_authorized"]),
            row["actor"],
            row["note"],
        )

    @staticmethod
    def _recognition_review(row: sqlite3.Row) -> RecognitionReview:
        return RecognitionReview(
            row["review_id"],
            row["task_id"],
            row["item_id"],
            row["source_storage_id"],
            row["source_path"],
            RecognitionReviewStatus(row["status"]),
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["updated_at"]),
            row["selected_recognition_type"],
            datetime.fromisoformat(row["decided_at"]) if row["decided_at"] else None,
            row["actor"],
        )

    @staticmethod
    def _metadata_correction(row: sqlite3.Row) -> MetadataCorrectionReview:
        return MetadataCorrectionReview(
            row["review_id"],
            row["task_id"],
            row["item_id"],
            row["source_storage_id"],
            row["source_path"],
            row["recognition_type"],
            row["metadata_policy_id"],
            row["provider_id"],
            row["original_query"],
            row["original_year"],
            row["original_media_type"],
            row["outcome"],
            MetadataCorrectionStatus(row["status"]),
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["updated_at"]),
            row["corrected_query"],
            row["corrected_year"],
            row["corrected_media_type"],
            row["direct_provider_id"],
            datetime.fromisoformat(row["decided_at"]) if row["decided_at"] else None,
            row["actor"],
        )

    @staticmethod
    def _metadata_correction_continuation_values(
        value: MetadataCorrectionContinuation,
    ) -> tuple[object, ...]:
        return (
            value.continuation_id,
            value.file_id,
            value.review_id,
            value.source_task_id,
            value.source_item_id,
            value.configuration_snapshot_id,
            value.configuration_snapshot_digest,
            value.correction_version,
            value.status.value,
            value.created_at.isoformat(),
            value.updated_at.isoformat(),
            value.actor,
            value.job_id,
            value.new_task_id,
            value.new_result_id,
            value.started_at.isoformat() if value.started_at else None,
            value.completed_at.isoformat() if value.completed_at else None,
            value.error,
            value.recovery,
        )

    @staticmethod
    def _metadata_correction_continuation(
        row: sqlite3.Row,
    ) -> MetadataCorrectionContinuation:
        return MetadataCorrectionContinuation(
            row["continuation_id"],
            row["file_id"],
            row["review_id"],
            row["source_task_id"],
            row["source_item_id"],
            row["configuration_snapshot_id"],
            row["configuration_snapshot_digest"],
            row["correction_version"],
            MetadataCorrectionContinuationStatus(row["status"]),
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["updated_at"]),
            row["actor"],
            row["job_id"],
            row["new_task_id"],
            row["new_result_id"],
            datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            row["error"],
            row["recovery"],
        )

    @staticmethod
    def _metadata_review(row: sqlite3.Row) -> MetadataReview:
        return MetadataReview(
            row["review_id"],
            row["task_id"],
            row["item_id"],
            row["source_storage_id"],
            row["source_path"],
            row["recognition_type"],
            row["metadata_policy_id"],
            row["query"],
            row["outcome"],
            MetadataReviewStatus(row["status"]),
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["updated_at"]),
            row["selected_rank"],
            row["selected_provider"],
            row["selected_provider_id"],
            row["selected_media_type"],
            datetime.fromisoformat(row["decided_at"]) if row["decided_at"] else None,
            row["actor"],
        )

    @staticmethod
    def _metadata_review_candidate(row: sqlite3.Row) -> MetadataReviewCandidate:
        components = json.loads(row["score_components"])
        return MetadataReviewCandidate(
            row["review_id"],
            row["rank"],
            row["provider"],
            row["provider_id"],
            row["media_type"],
            row["title"],
            row["original_title"],
            row["canonical_year"],
            row["regional_year"],
            row["total_score"],
            row["matched_provider_title"],
            row["matched_title_source"],
            tuple(
                MetadataReviewScoreComponent(
                    str(component["name"]),
                    float(component["score"]),
                    str(component["reason"]),
                )
                for component in components
            ),
        )

    @staticmethod
    def _classification_review(row: sqlite3.Row) -> ClassificationReview:
        return ClassificationReview(
            row["review_id"],
            row["task_id"],
            row["item_id"],
            row["source_storage_id"],
            row["source_path"],
            row["recognition_type"],
            row["classification_policy_id"],
            row["provider"],
            row["provider_id"],
            row["media_type"],
            row["title"],
            row["canonical_year"],
            ClassificationReviewStatus(row["status"]),
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["updated_at"]),
            row["selected_rank"],
            row["selected_rule_id"],
            row["selected_media_library_id"],
            row["selected_relative_path"],
            datetime.fromisoformat(row["decided_at"]) if row["decided_at"] else None,
            row["actor"],
        )

    @staticmethod
    def _classification_review_choice(row: sqlite3.Row) -> ClassificationReviewChoice:
        return ClassificationReviewChoice(
            row["review_id"],
            row["rank"],
            row["rule_id"],
            row["rule_name"],
            row["media_library_id"],
            row["relative_path"],
            row["priority"],
            row["description"],
        )

    @staticmethod
    def _job_values(job: AutomationJob) -> tuple[object, ...]:
        return (
            job.job_id,
            job.command.value,
            job.status.value,
            job.created_at.isoformat(),
            job.updated_at.isoformat(),
            job.limit,
            job.started_at.isoformat() if job.started_at else None,
            job.completed_at.isoformat() if job.completed_at else None,
            job.task_id,
            job.error,
            int(job.cancellation_requested),
            job.schedule_id,
            int(job.execute_authorized),
            job.claim_token,
            job.configuration_snapshot_id,
            job.configuration_snapshot_digest,
            job.failure_category,
            job.failure_durable_state,
            job.failure_side_effects,
            None if job.failure_retry_safe is None else int(job.failure_retry_safe),
            job.failure_next_action,
        )

    def _insert_job(self, job: AutomationJob) -> None:
        """Insert by column name so older migrated databases remain compatible.

        Historical migrations append columns with ALTER TABLE.  Positional
        INSERTs therefore do not have a stable order across schema versions.
        The explicit column list keeps the new snapshot fields additive while
        preserving the legacy job table layout.
        """
        self._connection.execute(
            "INSERT INTO automation_jobs "
            "(job_id, command, status, created_at, updated_at, limit_value, "
            "started_at, completed_at, task_id, error, cancellation_requested, "
            "schedule_id, execute_authorized, claim_token, "
            "configuration_snapshot_id, configuration_snapshot_digest, failure_category, "
            "failure_durable_state, failure_side_effects, failure_retry_safe, "
            "failure_next_action) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            self._job_values(job),
        )

    @staticmethod
    def _job(row: sqlite3.Row) -> AutomationJob:
        return AutomationJob(
            row["job_id"],
            AutomationCommand(row["command"]),
            AutomationJobStatus(row["status"]),
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["updated_at"]),
            row["limit_value"],
            datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            row["task_id"],
            row["error"],
            bool(row["cancellation_requested"]),
            row["schedule_id"],
            bool(row["execute_authorized"]),
            row["claim_token"],
            row["configuration_snapshot_id"],
            row["configuration_snapshot_digest"],
            row["failure_category"],
            row["failure_durable_state"],
            row["failure_side_effects"],
            None if row["failure_retry_safe"] is None else bool(row["failure_retry_safe"]),
            row["failure_next_action"],
        )

    @staticmethod
    def _execution_authorization_values(value: ExecutionAuthorization) -> tuple[object, ...]:
        return (
            value.authorization_id,
            value.token_digest,
            value.status.value,
            value.created_at.isoformat(),
            value.expires_at.isoformat(),
            value.max_items,
            value.actor,
            value.note,
            value.consumed_at.isoformat() if value.consumed_at else None,
            value.consumed_job_id,
            value.revoked_at.isoformat() if value.revoked_at else None,
        )

    @staticmethod
    def _execution_authorization(row: sqlite3.Row) -> ExecutionAuthorization:
        return ExecutionAuthorization(
            row["authorization_id"],
            row["token_digest"],
            ExecutionAuthorizationStatus(row["status"]),
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["expires_at"]),
            row["max_items"],
            row["actor"],
            row["note"],
            datetime.fromisoformat(row["consumed_at"]) if row["consumed_at"] else None,
            row["consumed_job_id"],
            datetime.fromisoformat(row["revoked_at"]) if row["revoked_at"] else None,
        )

    def _insert_execution_authorization_audit(self, value: ExecutionAuthorizationAudit) -> None:
        self._connection.execute(
            "INSERT INTO execution_authorization_audit VALUES (?, ?, ?, ?, ?, ?)",
            (
                value.audit_id,
                value.authorization_id,
                value.action,
                value.occurred_at.isoformat(),
                value.job_id,
                value.actor,
            ),
        )

    @staticmethod
    def _schedule_state(row: sqlite3.Row) -> ScheduleState:
        return ScheduleState(
            row["schedule_id"],
            datetime.fromisoformat(row["next_run_at"]),
            datetime.fromisoformat(row["updated_at"]),
            row["last_job_id"],
        )

    @staticmethod
    def _delivery_values(value: NotificationDelivery) -> tuple[object, ...]:
        return (
            value.delivery_id,
            value.webhook_id,
            value.event_id,
            value.event_type.value,
            value.body,
            value.status.value,
            value.attempts,
            value.next_attempt_at.isoformat(),
            value.created_at.isoformat(),
            value.updated_at.isoformat(),
            value.delivered_at.isoformat() if value.delivered_at else None,
            value.failure_category,
            value.response_status,
        )

    @staticmethod
    def _delivery(row: sqlite3.Row) -> NotificationDelivery:
        return NotificationDelivery(
            row["delivery_id"],
            row["webhook_id"],
            row["event_id"],
            NotificationEventType(row["event_type"]),
            row["body"],
            NotificationDeliveryStatus(row["status"]),
            row["attempts"],
            datetime.fromisoformat(row["next_attempt_at"]),
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["updated_at"]),
            datetime.fromisoformat(row["delivered_at"]) if row["delivered_at"] else None,
            row["failure_category"],
            row["response_status"],
        )
