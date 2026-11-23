"""Shared runtime resolution for resident services and the remaining CLI.

The deployment database locator, managed Active resolution, snapshot identity
and Task-terminal notification observer are consumed by both the fixed service
entry and the remaining business CLI commands.  Keeping them here lets the
service process start without importing the general CLI.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from mediaflow.application.configuration_snapshot import (
    MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION,
)
from mediaflow.application.notification import NotificationPublisher, task_terminal_observer
from mediaflow.domain.configuration_input import reject_retired_configuration_input
from mediaflow.domain.configuration_management import RuntimeSnapshotUnavailable
from mediaflow.infrastructure.runtime_configuration import (
    ManagementBootstrapConfiguration,
    RuntimeConfiguration,
    load_published_runtime_configuration,
    load_runtime_configuration,
    with_managed_snapshot,
)
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository


def configuration_document(path: str | None) -> object:
    configured = path or os.environ.get("MEDIAFLOW_CONFIG")
    if not configured:
        raise ValueError("--config or MEDIAFLOW_CONFIG is required")
    try:
        return json.loads(Path(configured).read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"configuration file could not be read: {error}") from error


def resolve_configuration(
    path: str | None,
    *,
    use_managed: bool = True,
    snapshot_id: str | None = None,
    snapshot_digest: str | None = None,
) -> RuntimeConfiguration:
    raw_document = configuration_document(path)
    # The current startup boundary applies equally to the development
    # listener, production Waitress, residents and `config validate`: a
    # retired deployment identity must not become live authority again.
    reject_retired_configuration_input(raw_document)
    if not use_managed:
        return load_runtime_configuration(raw_document)
    database_path = bootstrap_database_path(raw_document)
    deployment_locations: tuple[str, ...] = ()
    try:
        with SQLiteConfigurationRepository(database_path) as repository:
            active = (
                repository.get_revision(snapshot_id)
                if snapshot_id
                else repository.get_active_revision()
            )
            deployment_locations = repository.deployment_database_locations()
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
        with SQLiteConfigurationRepository(database_path) as repository:
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
        raise RuntimeSnapshotUnavailable(
            "no managed Active configuration exists; create and activate the first setup Draft",
            reason="active_missing",
        )
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
        resolved = load_published_runtime_configuration(
            active.document,
            bootstrap_database_path=database_path,
            deployment_database_locations=deployment_locations,
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
        version=active.version,
    )


def bootstrap_database_path(document: object) -> str:
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


def task_snapshot_identity(path: str | None, task_id: str) -> tuple[str, str] | None:
    """Read a persisted Task's configuration pin before workflow bootstrap.

    A bounded read-only utility: it does not resolve strategy content or
    construct Storage/Provider objects; it only preserves the immutable
    identity already recorded at the Task boundary. Legacy Tasks without a pin
    fail closed once managed authority has been activated; before activation
    they remain bootstrap work.  The standalone retry-failed entrance that
    used to call this was retired (Slice 47 RO-6); a four-type continuation
    resolves its own pinned snapshot inside its admitting service.
    """
    try:
        document = configuration_document(path)
        database_path = bootstrap_database_path(document)
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


def managed_snapshot_identity(path: str | None) -> tuple[str, str] | None:
    """Resolve the current managed identity for long-lived Job producers."""

    document = configuration_document(path)
    database_path = bootstrap_database_path(document)
    with SQLiteConfigurationRepository(database_path) as repository:
        active = repository.get_active_revision()
        deployment_locations = repository.deployment_database_locations()
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
            load_published_runtime_configuration(
                active.document,
                bootstrap_database_path=database_path,
                deployment_database_locations=deployment_locations,
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


def managed_snapshot_reference(path: str | None) -> tuple[str, str] | None:
    """Read the current managed identity without validating its workflow document.

    A Worker must bind its registration to the persisted Active identity, but it
    must still be able to finish an already pinned Job when a newer Active
    document is unhealthy.  The claimed Job remains responsible for loading
    and validating the exact snapshot it consumes.
    """

    document = configuration_document(path)
    database_path = bootstrap_database_path(document)
    with SQLiteConfigurationRepository(database_path) as repository:
        active = repository.get_active_revision()
        if active is None:
            return None
        return active.revision_id, active.digest


class ResidentConfigurationUnavailable(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__("resident configuration is unavailable; restore the named prerequisite")
        self.reason = reason


def resolve_resident_configuration(configured_path: str | None) -> RuntimeConfiguration | None:
    import sqlite3

    try:
        configuration = resolve_configuration(configured_path)
    except sqlite3.Error as error:
        raise ResidentConfigurationUnavailable("database_unavailable") from error
    except RuntimeSnapshotUnavailable as error:
        reason = (
            "schema_unsupported"
            if error.reason == "schema_unsupported"
            else "configuration_unavailable"
        )
        raise ResidentConfigurationUnavailable(reason) from error
    except Exception as error:
        raise ResidentConfigurationUnavailable("configuration_unavailable") from error
    if isinstance(configuration, ManagementBootstrapConfiguration):
        return None
    return configuration


def current_runtime_configuration(configured_path: str | None) -> RuntimeConfiguration | None:
    try:
        return resolve_resident_configuration(configured_path)
    except ResidentConfigurationUnavailable:
        return None


def resident_failure_reason(error: BaseException) -> tuple[str, str]:
    if isinstance(error, ResidentConfigurationUnavailable):
        return error.reason, str(error)
    return (
        "configuration_unavailable",
        "service work is blocked; inspect configuration and durable work",
    )


def notification_publisher(repository, configured_path: str | None) -> NotificationPublisher:
    """Publish settled Task outcomes to the current Active Webhooks.

    The target set is resolved per publication rather than at process start, so
    a Task that settles after a later publication notifies the Webhooks that are
    actually configured then.  Only the durable outbox write happens here; an
    unavailable configuration or a missing secret never fails the Task, and the
    resident Notification Worker remains responsible for signed delivery.
    """

    def webhooks():
        resolved = current_runtime_configuration(configured_path)
        return getattr(resolved, "webhooks", ()) if resolved else ()

    return NotificationPublisher(repository, webhooks)


def attach_task_terminal_notifications(repository, configured_path: str | None) -> None:
    """Publish one terminal Task event at its durable result boundary.

    A Task's terminal outcome is committed by the scheduling kernel, so this
    post-commit observer is the same place for Worker, direct CLI and API
    settlements.  A repository without the seam (a focused unit test double)
    simply publishes nothing.
    """

    attach = getattr(repository, "add_task_terminal_observer", None)
    if not callable(attach):
        return
    attach(task_terminal_observer(notification_publisher(repository, configured_path)))
