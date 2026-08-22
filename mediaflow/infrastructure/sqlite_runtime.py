from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationJob,
    AutomationJobStatus,
    ScheduleAuditRecord,
    ScheduleState,
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
from mediaflow.domain.metadata_review import (
    MetadataReview,
    MetadataReviewCandidate,
    MetadataReviewScoreComponent,
    MetadataReviewStatus,
)
from mediaflow.domain.notification import (
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationEventType,
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
)

SCHEMA_VERSION = 10


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
                INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._task_values(task),
            )

    def update_task(self, task: PersistentTask) -> None:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                UPDATE tasks SET command=?, status=?, execute_authorized=?, created_at=?,
                    updated_at=?, started_at=?, completed_at=?, total_items=?, completed_items=?,
                    failed_items=?, error=? WHERE task_id=?
                """,
                (*self._task_values(task)[1:], task.task_id),
            )
            if cursor.rowcount != 1:
                raise LookupError(f"task {task.task_id!r} is not configured")

    def get_task(self, task_id: str) -> PersistentTask | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
        return self._task(row) if row else None

    def list_tasks(self, *, limit: int | None = None) -> tuple[PersistentTask, ...]:
        query = "SELECT * FROM tasks ORDER BY created_at DESC"
        parameters: tuple[object, ...] = ()
        if limit is not None:
            query += " LIMIT ?"
            parameters = (limit,)
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
        return tuple(self._task(row) for row in rows)

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

    def list_items(self, task_id: str) -> tuple[PersistentTaskItem, ...]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM task_items WHERE task_id = ? ORDER BY created_at, item_id",
                (task_id,),
            ).fetchall()
        return tuple(self._item(row) for row in rows)

    def append_result(self, result: PersistentResultRecord) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO task_results (
                    result_id, task_id, item_id, source_storage_id, source_path,
                    destination_storage_id, destination_path, recognition_type, provider,
                    provider_id, metadata_policy_id, naming_policy_id, classification_policy_id,
                    organize_policy_id, operation, status, created_at, title, error,
                    completed_operations, attachment_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
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
                ),
            )

    def list_results(self, task_id: str) -> tuple[PersistentResultRecord, ...]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM task_results WHERE task_id = ? ORDER BY created_at, result_id",
                (task_id,),
            ).fetchall()
        return tuple(self._result(row) for row in rows)

    def create_confirmation(self, confirmation: ConflictConfirmation) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """INSERT INTO conflict_confirmations VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                self._confirmation_values(confirmation),
            )

    def create_metadata_review(
        self,
        review: MetadataReview,
        candidates: tuple[MetadataReviewCandidate, ...],
        item: PersistentTaskItem,
    ) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """INSERT INTO metadata_reviews VALUES
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

    def get_metadata_review(self, review_id: str) -> MetadataReview | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM metadata_reviews WHERE review_id=?", (review_id,)
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

    def list_metadata_review_candidates(
        self, review_id: str
    ) -> tuple[MetadataReviewCandidate, ...]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM metadata_review_candidates WHERE review_id=? ORDER BY rank",
                (review_id,),
            ).fetchall()
        return tuple(self._metadata_review_candidate(row) for row in rows)

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
            self._connection.execute(
                "INSERT INTO automation_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                self._job_values(job),
            )

    def get_job(self, job_id: str) -> AutomationJob | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM automation_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
        return self._job(row) if row else None

    def list_jobs(self, *, limit: int | None = None) -> tuple[AutomationJob, ...]:
        query = "SELECT * FROM automation_jobs ORDER BY created_at DESC, job_id DESC"
        parameters: tuple[object, ...] = ()
        if limit is not None:
            query += " LIMIT ?"
            parameters = (limit,)
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
        return tuple(self._job(row) for row in rows)

    def claim_next_job(self, now: datetime) -> AutomationJob | None:
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT job_id FROM automation_jobs WHERE status=? "
                "ORDER BY created_at, job_id LIMIT 1",
                (AutomationJobStatus.PENDING.value,),
            ).fetchone()
            if row is None:
                return None
            cursor = self._connection.execute(
                "UPDATE automation_jobs SET status=?, updated_at=?, started_at=? "
                "WHERE job_id=? AND status=?",
                (
                    AutomationJobStatus.RUNNING.value,
                    now.isoformat(),
                    now.isoformat(),
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
                "cancellation_requested=?, schedule_id=?, execute_authorized=? WHERE job_id=?",
                (*self._job_values(job)[1:], job.job_id),
            )
            if cursor.rowcount != 1:
                raise LookupError(f"automation job {job.job_id!r} was not found")

    def request_job_cancellation(self, job_id: str, now: datetime) -> AutomationJob:
        with self._lock, self._connection:
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
                existing = self.get_job(job_id)
                if existing is None:
                    raise LookupError(f"automation job {job_id!r} was not found")
                raise ValueError("only a pending or running automation job can be cancelled")
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

    def list_stale_running_jobs(self, before: datetime) -> tuple[AutomationJob, ...]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM automation_jobs WHERE status=? AND updated_at<? "
                "ORDER BY updated_at, job_id",
                (AutomationJobStatus.RUNNING.value, before.isoformat()),
            ).fetchall()
        return tuple(self._job(row) for row in rows)

    def requeue_stale_job(self, job_id: str, before: datetime, now: datetime) -> AutomationJob:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "UPDATE automation_jobs SET status=?, updated_at=?, started_at=NULL, "
                "completed_at=NULL, task_id=NULL, error='explicitly requeued stale job', "
                "cancellation_requested=0 WHERE job_id=? AND status=? AND updated_at<?",
                (
                    AutomationJobStatus.PENDING.value,
                    now.isoformat(),
                    job_id,
                    AutomationJobStatus.RUNNING.value,
                    before.isoformat(),
                ),
            )
            if cursor.rowcount != 1:
                existing = self.get_job(job_id)
                if existing is None:
                    raise LookupError(f"automation job {job_id!r} was not found")
                raise ValueError("automation job is not stale and running")
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
    ) -> bool:
        with self._lock, self._connection:
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
                return False
            self._connection.execute(
                "INSERT INTO automation_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                self._job_values(job),
            )
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
        return True

    def list_schedule_states(self) -> tuple[ScheduleState, ...]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM automation_schedules ORDER BY schedule_id"
            ).fetchall()
        return tuple(self._schedule_state(row) for row in rows)

    def list_schedule_audit(
        self, schedule_id: str | None = None, *, limit: int | None = None
    ) -> tuple[ScheduleAuditRecord, ...]:
        if limit is not None and limit < 1:
            raise ValueError("schedule audit limit must be positive")
        query = "SELECT * FROM schedule_audit"
        parameters: list[object] = []
        if schedule_id is not None:
            query += " WHERE schedule_id=?"
            parameters.append(schedule_id)
        query += " ORDER BY emitted_at DESC, audit_id DESC"
        if limit is not None:
            query += " LIMIT ?"
            parameters.append(limit)
        with self._lock:
            rows = self._connection.execute(query, tuple(parameters)).fetchall()
        return tuple(
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
    ) -> ExecutionAuthorization:
        expired = False
        with self._lock, self._connection:
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
                self._connection.execute(
                    "INSERT INTO automation_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    self._job_values(job),
                )
                self._insert_execution_authorization_audit(
                    replace(audit, authorization_id=value.authorization_id)
                )
                updated = self._connection.execute(
                    "SELECT * FROM execution_authorizations WHERE authorization_id=?",
                    (value.authorization_id,),
                ).fetchone()
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
    ) -> tuple[NotificationDelivery, ...]:
        if limit is not None and limit < 1:
            raise ValueError("notification limit must be positive")
        query = "SELECT * FROM notification_deliveries"
        parameters: list[object] = []
        if status is not None:
            query += " WHERE status=?"
            parameters.append(status.value)
        query += " ORDER BY created_at DESC, delivery_id DESC"
        if limit is not None:
            query += " LIMIT ?"
            parameters.append(limit)
        with self._lock:
            rows = self._connection.execute(query, tuple(parameters)).fetchall()
        return tuple(self._delivery(row) for row in rows)

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
                    failed_items INTEGER NOT NULL, error TEXT
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
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id),
                    FOREIGN KEY(item_id) REFERENCES task_items(item_id)
                );
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
                CREATE TABLE IF NOT EXISTS metadata_reviews (
                    review_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                    item_id TEXT NOT NULL UNIQUE, source_storage_id TEXT NOT NULL,
                    source_path TEXT NOT NULL, recognition_type TEXT NOT NULL,
                    metadata_policy_id TEXT NOT NULL, query TEXT NOT NULL,
                    outcome TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
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
                CREATE TABLE IF NOT EXISTS automation_jobs (
                    job_id TEXT PRIMARY KEY, command TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, limit_value INTEGER,
                    started_at TEXT, completed_at TEXT, task_id TEXT, error TEXT,
                    cancellation_requested INTEGER NOT NULL DEFAULT 0, schedule_id TEXT,
                    execute_authorized INTEGER NOT NULL DEFAULT 0
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
        return PersistentResultRecord(
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
