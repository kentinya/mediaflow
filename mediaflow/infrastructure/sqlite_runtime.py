from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

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

SCHEMA_VERSION = 3


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

    def get_confirmation(self, confirmation_id: str) -> ConflictConfirmation | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM conflict_confirmations WHERE confirmation_id=?",
                (confirmation_id,),
            ).fetchone()
        return self._confirmation(row) if row else None

    def list_confirmations(
        self, *, status: ConfirmationStatus | None = None
    ) -> tuple[ConflictConfirmation, ...]:
        query = "SELECT * FROM conflict_confirmations"
        parameters: tuple[object, ...] = ()
        if status is not None:
            query += " WHERE status=?"
            parameters = (status.value,)
        query += " ORDER BY created_at, confirmation_id"
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
        return tuple(self._confirmation(row) for row in rows)

    def resolve_confirmation(
        self, confirmation: ConflictConfirmation, audit: ConflictDecisionAudit
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
