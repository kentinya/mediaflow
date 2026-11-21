"""Read-only scope for the one supported managed-configuration data switch.

A previous supported store (configuration schema 11) still contains unpublished
revisions and their dedicated read-only evidence from the retired draft
lifecycle.  This build stores current and historical published snapshots only.
The switch that removes the retired rows is an explicit deployment action:

* reading the scope never writes, so an operator can inspect exactly which
  revisions, evidence and admitted Tasks are affected on the original file;
* applying it reuses the repository's single initialization transaction, which
  either retires every affected row and advances the marker together or leaves
  the file unchanged.

This module holds only the read-only inspection plus the exception the
repository raises while a switch is still pending.  The mutating transaction
remains in :class:`SQLiteConfigurationRepository`.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from mediaflow.domain.configuration_management import (
    ConfigurationObjectKind,
    ManagedConfigurationStatus,
)
from mediaflow.infrastructure.sqlite_applicability import (
    MIN_CONFIGURATION_SCHEMA_VERSION,
    read_database_markers,
)
from mediaflow.infrastructure.sqlite_configuration_schema import (
    CONFIGURATION_SCHEMA_VERSION,
)

#: Unpublished lifecycle states retired by the data switch.  Published Active
#: and Superseded revisions remain immutable history.
RETIRED_CONFIGURATION_STATUSES = (
    ManagedConfigurationStatus.DRAFT.value,
    ManagedConfigurationStatus.VALIDATED.value,
)

#: Evidence tables whose rows are bound to the candidate revision they checked.
#: Rows still referenced by published revisions are never touched.
RETIRED_UNPUBLISHED_EVIDENCE_TABLES = (
    "managed_local_setup_checks",
    "managed_storage_setup_checks",
    "managed_recognition_strategy_tests",
    "managed_naming_previews",
    "managed_classification_previews",
    "managed_organize_authority_previews",
    "managed_destination_previews",
    "managed_destination_prechecks",
)

_SWITCH_CONFIRMATION = "mediaflow config retire-unpublished --confirm"


@dataclass(frozen=True)
class ConfigurationDataSwitchEvidence:
    table: str
    rows: int

    def document(self) -> dict[str, object]:
        return {"table": self.table, "rows": self.rows}


@dataclass(frozen=True)
class ConfigurationDataSwitchRevision:
    revision_id: str
    status: str
    revision_sequence: int
    version: int
    digest: str
    updated_at: str
    evidence: tuple[ConfigurationDataSwitchEvidence, ...]

    def document(self) -> dict[str, object]:
        return {
            "revisionId": self.revision_id,
            "status": self.status,
            "revisionSequence": self.revision_sequence,
            "version": self.version,
            "digest": self.digest,
            "updatedAt": self.updated_at,
            "evidence": [item.document() for item in self.evidence],
        }


@dataclass(frozen=True)
class ConfigurationDataSwitchPinnedTask:
    task_id: str
    status: str
    created_at: str
    revision_id: str

    def document(self) -> dict[str, object]:
        return {
            "taskId": self.task_id,
            "status": self.status,
            "createdAt": self.created_at,
            "revisionId": self.revision_id,
        }


@dataclass(frozen=True)
class ConfigurationDataSwitchScope:
    """The exact unpublished rows a confirmed switch would remove."""

    configuration_schema_version: int
    target_configuration_schema_version: int
    revisions: tuple[ConfigurationDataSwitchRevision, ...]
    audit_rows: int
    pinned_tasks: tuple[ConfigurationDataSwitchPinnedTask, ...]
    managed_activation: bool

    @property
    def blocked(self) -> bool:
        return bool(self.pinned_tasks)

    @property
    def evidence_totals(self) -> tuple[ConfigurationDataSwitchEvidence, ...]:
        totals: dict[str, int] = {}
        for revision in self.revisions:
            for item in revision.evidence:
                totals[item.table] = totals.get(item.table, 0) + item.rows
        return tuple(
            ConfigurationDataSwitchEvidence(table, rows) for table, rows in sorted(totals.items())
        )

    def next_action(self) -> str:
        if self.blocked:
            pinned = ", ".join(f"{item.task_id}->{item.revision_id}" for item in self.pinned_tasks)
            return (
                "admitted Tasks still pin unpublished revisions "
                f"({pinned}); release or migrate those Tasks, then review "
                "`mediaflow config status` again. The file was not modified."
            )
        if not self.revisions:
            return (
                "no unpublished revisions or evidence remain; run "
                f"`{_SWITCH_CONFIRMATION}` to advance the configuration structure"
            )
        return f"review affectedRevisions and evidence, then run `{_SWITCH_CONFIRMATION}`"

    def document(self) -> dict[str, object]:
        return {
            "required": True,
            "state": "BLOCKED" if self.blocked else "PENDING",
            "configurationSchemaVersion": self.configuration_schema_version,
            "targetConfigurationSchemaVersion": self.target_configuration_schema_version,
            "affectedRevisions": [item.document() for item in self.revisions],
            "evidenceTotals": [item.document() for item in self.evidence_totals],
            "auditRows": self.audit_rows,
            "pinnedTasks": [item.document() for item in self.pinned_tasks],
            "managedActivation": self.managed_activation,
            "confirmation": _SWITCH_CONFIRMATION,
            "nextAction": self.next_action(),
        }


class ConfigurationDataSwitchRequired(RuntimeError):
    """This build refuses to serve a store that still needs the data switch."""

    def __init__(self, scope: ConfigurationDataSwitchScope) -> None:
        self.scope = scope
        remaining = (
            f"{len(scope.revisions)} unpublished revision(s) "
            f"({', '.join(item.revision_id for item in scope.revisions)}), "
            f"{sum(item.rows for item in scope.evidence_totals)} evidence row(s) "
            "and their audits remain from the retired draft lifecycle"
            if scope.revisions
            else "no unpublished revisions remain, but the previous configuration "
            "structure still requires the explicit one-time switch"
        )
        super().__init__(
            f"configuration data switch is pending; {remaining}. Review "
            "the exact scope with `mediaflow config status`, then run "
            f"`{_SWITCH_CONFIRMATION}`. The managed configuration was not modified."
            + (
                " Affected admitted Tasks: "
                + ", ".join(f"{item.task_id}->{item.revision_id}" for item in scope.pinned_tasks)
                + "."
                if scope.blocked
                else ""
            )
        )


def _connect_read_only(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        database_path.resolve().as_uri() + "?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    return connection


def _table_names(connection: sqlite3.Connection) -> frozenset[str]:
    return frozenset(
        str(row["name"])
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    )


def read_configuration_data_switch(
    database_path: str | Path,
) -> ConfigurationDataSwitchScope | None:
    """Return the pending switch scope without modifying the store.

    ``None`` means no switch is pending for this file: it is absent, already
    current, or outside the one supported previous layout.  Unsupported files
    are rejected by the normal applicability boundary when the repository opens.
    """

    path = Path(database_path)
    markers = read_database_markers(path)
    version = markers.configuration_version
    if version is None:
        return None
    if not MIN_CONFIGURATION_SCHEMA_VERSION <= version < CONFIGURATION_SCHEMA_VERSION:
        return None
    connection = _connect_read_only(path)
    try:
        tables = _table_names(connection)
        if "managed_configuration_revisions" not in tables:
            raise RuntimeError(
                "configuration database reports a previous configuration schema "
                "without configuration revisions; the file was not modified"
            )
        placeholders = ",".join("?" for _ in RETIRED_CONFIGURATION_STATUSES)
        rows = connection.execute(
            "SELECT revision_id, status, revision_sequence, version, digest, updated_at "
            "FROM managed_configuration_revisions "
            f"WHERE status IN ({placeholders}) "
            "ORDER BY revision_sequence, revision_id",
            RETIRED_CONFIGURATION_STATUSES,
        ).fetchall()
        revision_ids = tuple(str(row["revision_id"]) for row in rows)
        id_placeholders = ",".join("?" for _ in revision_ids)
        evidence_by_revision: dict[str, list[ConfigurationDataSwitchEvidence]] = {
            revision_id: [] for revision_id in revision_ids
        }
        if revision_ids:
            for table in RETIRED_UNPUBLISHED_EVIDENCE_TABLES:
                if table not in tables:
                    continue
                for evidence_row in connection.execute(
                    f"SELECT revision_id, COUNT(*) AS rows FROM {table} "
                    f"WHERE revision_id IN ({id_placeholders}) "
                    "GROUP BY revision_id ORDER BY revision_id",
                    revision_ids,
                ).fetchall():
                    evidence_by_revision[str(evidence_row["revision_id"])].append(
                        ConfigurationDataSwitchEvidence(
                            table=table,
                            rows=int(evidence_row["rows"]),
                        )
                    )
        revisions = tuple(
            ConfigurationDataSwitchRevision(
                revision_id=str(row["revision_id"]),
                status=str(row["status"]),
                revision_sequence=int(row["revision_sequence"]),
                version=int(row["version"]),
                digest=str(row["digest"]),
                updated_at=str(row["updated_at"]),
                evidence=tuple(evidence_by_revision[str(row["revision_id"])]),
            )
            for row in rows
        )
        audit_rows = 0
        if revision_ids and "configuration_change_audits" in tables:
            audit_rows = int(
                connection.execute(
                    "SELECT COUNT(*) FROM configuration_change_audits "
                    "WHERE object_kind=? "
                    f"AND object_id IN ({id_placeholders})",
                    (ConfigurationObjectKind.SYSTEM_SETTINGS.value, *revision_ids),
                ).fetchone()[0]
            )
        pinned_tasks: tuple[ConfigurationDataSwitchPinnedTask, ...] = ()
        if revision_ids and "tasks" in tables:
            columns = {
                str(item["name"])
                for item in connection.execute("PRAGMA table_info(tasks)").fetchall()
            }
            if "configuration_snapshot_id" in columns:
                pinned_tasks = tuple(
                    ConfigurationDataSwitchPinnedTask(
                        task_id=str(row["task_id"]),
                        status=str(row["status"]),
                        created_at=str(row["created_at"]),
                        revision_id=str(row["configuration_snapshot_id"]),
                    )
                    for row in connection.execute(
                        "SELECT task_id, status, created_at, configuration_snapshot_id "
                        "FROM tasks "
                        f"WHERE configuration_snapshot_id IN ({id_placeholders}) "
                        "ORDER BY created_at, task_id",
                        revision_ids,
                    ).fetchall()
                )
        managed_activation = (
            "managed_configuration_authority" in tables
            and connection.execute(
                "SELECT 1 FROM managed_configuration_authority WHERE singleton=1"
            ).fetchone()
            is not None
        )
        return ConfigurationDataSwitchScope(
            configuration_schema_version=version,
            target_configuration_schema_version=CONFIGURATION_SCHEMA_VERSION,
            revisions=revisions,
            audit_rows=audit_rows,
            pinned_tasks=pinned_tasks,
            managed_activation=managed_activation,
        )
    except sqlite3.DatabaseError as error:
        raise RuntimeError(
            "configuration database cannot be read for the data switch "
            f"({type(error).__name__}); the file was not modified"
        ) from error
    finally:
        connection.close()
