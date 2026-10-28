"""Publication evidence for scheduled intent; no second grant or execution engine."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from mediaflow.domain.automation import AutomationTaskDefinition
from mediaflow.domain.configuration_management import (
    AutomationDefinitionSaveError,
    ConfigurationObjectKind,
)
from mediaflow.domain.media_discovery import DiscoveryBudgets
from mediaflow.domain.security import ApiPermission


@dataclass(frozen=True)
class ExecutionPrincipal:
    principal_id: str
    trusted_local: bool = False


def definitions(document):
    return {
        v["id"]: AutomationTaskDefinition.from_document(v)
        for v in document.get("automationTaskDefinitions", [])
    }


def context(document, definition):
    # All strategies/destinations can affect dynamic recognition/classification.
    # Polling, notification and other administration fields cannot expand effects.
    resource = next(
        (
            v
            for v in document.get("resourceLibraries", [])
            if v.get("id") == definition.resource_library_id
        ),
        None,
    )
    storage_ids = {v.get("storageId") for v in document.get("mediaLibraries", [])}
    if resource is not None:
        storage_ids.add(resource.get("storageId"))
    value = {
        "definition": definition.document(),
        "resource": resource,
        "strategy": {
            key: document.get(key)
            for key in (
                "metadataPolicies",
                "namingPolicies",
                "classificationPolicies",
                "organizePolicies",
                "recognitionTypes",
                "recognitionRules",
                "recognitionTypePolicies",
            )
        },
        "mediaLibraries": document.get("mediaLibraries"),
        "storages": [v for v in document.get("storages", []) if v.get("id") in storage_ids],
    }
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def activation_evidence(repository, revision):
    audits = repository.list_audits(
        ConfigurationObjectKind.SYSTEM_SETTINGS, revision.revision_id, limit=500
    )
    audit = next((v for v in audits if v.action == "activate"), None)
    if audit is None:
        raise RuntimeError("published activation evidence is unavailable")
    return audit


def publication_intents(
    repository, previous, revision, actor, permission_authority=None, *, explicit_ids=()
):
    old = definitions(previous.document) if previous else {}
    retained = activation_evidence(repository, previous) if previous else None
    retained_intents = retained.after.get("automationExecutionIntents", {}) if retained else {}
    result = {}
    for key, definition in definitions(revision.document).items():
        if not definition.enabled:
            continue
        digest = context(revision.document, definition)
        unchanged = (
            key in old and old[key].enabled and context(previous.document, old[key]) == digest
        )
        if unchanged and key not in explicit_ids:
            evidence = retained_intents.get(key)
            # Legacy publication evidence is a real actor, never a fabricated admin.
            result[key] = evidence or {
                "principalId": retained.actor,
                "trustedLocal": False,
                "context": digest,
            }
            continue
        if permission_authority is not None:
            try:
                allowed = permission_authority.has_permission(
                    actor, ApiPermission.GRANT_UNATTENDED_EXECUTION
                )
            except Exception as error:
                raise AutomationDefinitionSaveError(
                    "automation_execution_permission_unavailable",
                    "current execution permission could not be verified; Active is preserved",
                    status=503,
                    stage="authority",
                    durable_state="active_preserved",
                    next_action="restore the current permission authority and review the candidate",
                ) from error
            if allowed is not True:
                raise AutomationDefinitionSaveError(
                    "automation_execution_permission_required",
                    "publishing an enabled definition or changed execution scope "
                    "requires execution permission",
                    status=403,
                    stage="authority",
                    durable_state="active_preserved",
                    next_action="ask a principal with scheduled execution permission to review "
                    "and publish",
                )
        import os

        result[key] = {
            "principalId": actor if permission_authority is not None else f"local:{os.getuid()}",
            "trustedLocal": permission_authority is None,
            "context": digest,
        }
    return result


def resolve_principal(managed, job, definition):
    revision = managed.require(job.configuration_snapshot_id)
    managed.verify_integrity(revision)
    audit = activation_evidence(managed.repository, revision)
    evidence = audit.after.get("automationExecutionIntents", {}).get(definition.definition_id)
    if evidence is None:
        return ExecutionPrincipal(audit.actor)
    if evidence.get("context") != context(revision.document, definition):
        raise RuntimeError("execution intent does not match the pinned effective scope")
    return ExecutionPrincipal(evidence["principalId"], evidence.get("trustedLocal") is True)


def live_definition(managed, definition_id):
    active = managed.active()
    if active is None:
        raise RuntimeError("current Active is unavailable")
    managed.verify_integrity(active)
    return definitions(active.document).get(definition_id)


class BoundedScopeReader:
    """Complete Run once walk: bounded active reads and immediate-child entries.

    Budgets cover both observations, but an intentional stability wait consumes
    no read budget. Concurrent directory reads share the same counters.
    """

    def __init__(
        self, storage, *, root="", maximum_entries=None, maximum_directories=None, seconds=None
    ):
        import threading

        budgets = DiscoveryBudgets()
        self._budgets = budgets
        self._root = root
        self._pages = 0
        self._storage = storage
        self._entries = 0
        self._directories = 0
        self._seconds_remaining = budgets.max_active_seconds if seconds is None else seconds
        self._maximum_entries = (
            budgets.max_visited_entries if maximum_entries is None else maximum_entries
        )
        self._maximum_directories = (
            budgets.max_visited_directories if maximum_directories is None else maximum_directories
        )
        self._lock = threading.Lock()

    def __getattr__(self, key):
        return getattr(self._storage, key)

    def list(self, path, *args, **kwargs):
        import time
        from pathlib import PurePosixPath

        from mediaflow.domain.storage import StorageError, StorageErrorCode

        started = time.monotonic()

        def refuse(message):
            raise StorageError(StorageErrorCode.IO_ERROR, "list", path, message)

        with self._lock:
            self._directories += 1
            remaining = self._seconds_remaining
            if self._directories > self._maximum_directories or remaining <= 0:
                refuse("complete Run once scope exceeded its read budget")
        seen = set()
        try:
            relative = PurePosixPath(path).relative_to(PurePosixPath(self._root))
        except ValueError:
            refuse("complete Run once scope returned an unsafe directory")
        if len(relative.parts) > self._budgets.max_depth:
            refuse("complete Run once scope exceeded its depth budget")

        def entries():
            cursor = None
            cursors = set()
            while True:
                with self._lock:
                    self._pages += 1
                    if self._pages > self._budgets.max_page_fetches:
                        refuse("complete Run once scope exceeded its page budget")
                page = self._storage.list_page(path, limit=self._budgets.page_limit, cursor=cursor)
                if len(page.entries) > self._budgets.page_limit:
                    refuse("complete Run once scope returned an oversized page")
                yield from page.entries
                cursor = page.next_cursor
                if cursor is None:
                    return
                if (
                    not isinstance(cursor, str)
                    or not cursor
                    or cursor in cursors
                    or len(cursor.encode("utf-8")) > self._budgets.max_cursor_bytes
                ):
                    refuse("complete Run once scope returned an invalid or repeated cursor")
                cursors.add(cursor)

        try:
            for entry in entries():
                candidate = PurePosixPath(entry.path)
                if (
                    candidate.is_absolute()
                    or ".." in candidate.parts
                    or "\\" in entry.path
                    or candidate.parent != PurePosixPath(path)
                    or str(candidate) != entry.path
                    or entry.name != candidate.name
                    or len(entry.path.encode("utf-8")) > self._budgets.max_path_bytes
                    or len(candidate.parts) > self._budgets.max_segments
                    or len(entry.name.encode("utf-8")) > self._budgets.max_entry_name_bytes
                    or entry.path in seen
                ):
                    refuse("complete Run once scope returned an unsafe or duplicate entry")
                seen.add(entry.path)
                with self._lock:
                    self._entries += 1
                    if self._entries > self._maximum_entries:
                        refuse("complete Run once scope exceeded its read budget")
                if time.monotonic() - started > remaining:
                    refuse("complete Run once scope exceeded its read budget")
                yield entry
            if time.monotonic() - started > remaining:
                refuse("complete Run once scope exceeded its read budget")
        finally:
            with self._lock:
                self._seconds_remaining -= time.monotonic() - started


def assert_schedule_continuity(managed, job, definition):
    """An intervening disable/removal permanently stops old scheduled work.

    Enabled successors may preserve a legitimate pin. Re-enabling later never
    resurrects the unperformed effects of an older admitted occurrence.
    """
    current = managed.active()
    seen = set()
    while current is not None and current.revision_id not in seen:
        seen.add(current.revision_id)
        managed.verify_integrity(current)
        live = definitions(current.document).get(definition.definition_id)
        if live is None or not live.enabled:
            raise RuntimeError("the admitted schedule was disabled or removed")
        if current.revision_id == job.configuration_snapshot_id:
            return
        prior_id = activation_evidence(managed.repository, current).before.get("revisionId")
        if not isinstance(prior_id, str) or not prior_id:
            break
        current = managed.require(prior_id)
    raise RuntimeError("the admitted scheduled intent continuity cannot be proved")
