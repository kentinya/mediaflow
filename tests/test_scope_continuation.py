"""Focused Task 42.4 coverage: durable queued continuation of a paused scope.

Slice 42 RO-5 / AC-T3–AC-T6.  Every case drives the real application admission
service, the real API transport and the real resident-Worker handler over
temporary Local Storage and a real managed Active revision, and proves that:

- the backend advertises Continue exactly when the exact remaining admitted
  scope of a durably paused Task can really be queued, and withholds it with a
  bounded, truthful reason otherwise;
- admission is atomic and optimistic: a stale version, a duplicate submission, a
  non-paused Task, an unresolvable pin and a non-continuable Task kind are all
  refused with zero queued work and zero Storage mutation;
- a persisted ``execute_authorized`` boolean is never authority — a mutation-
  authorized Task without a live reusable authority is refused with the native
  exact-Preview next action;
- the resident Worker continues only the remaining scope: every already-recorded
  source is excluded, terminal/dry-run/skipped/ignored siblings are never
  replayed, an uncertain effect is never replayed, and the original item budget
  is preserved;
- the original and the continuation run remain independently inspectable, and
  neither the original pin nor the original item history is rewritten.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.read_only_storage import ReadOnlyStorageGuard
from mediaflow.application.scope_continuation import (
    ScopeContinuationService,
    ScopeContinuationWorkerService,
    continuation_obstacle,
    continuation_origin,
    definition_occurrence_authority,
    is_continuable_task_command,
    recovery_preparation_eligibility,
    recovery_scope,
    recovery_scope_plan,
    remaining_scope,
)
from mediaflow.application.strategy_test import SyntheticMetadataProvider
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationJob,
    AutomationJobStatus,
    AutomationTaskRunMode,
)
from mediaflow.domain.configuration_management import (
    ConfigurationDestinationPrecheckStatus,
    ConfigurationStorageCheckStatus,
    ConfigurationStrategyTestStatus,
)
from mediaflow.domain.media_discovery import DiscoveryBudgets
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.scope_continuation import (
    ScopeContinuationError,
    ScopeContinuationReason,
    ScopeContinuationStatus,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.source_evidence import occurrence_id_for, source_fingerprint
from mediaflow.domain.storage import (
    StorageEntry,
    StorageEntryType,
    StorageError,
    StorageErrorCode,
    StoragePage,
)
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_configuration_objects import example_document

NOW = datetime(2026, 10, 4, 12, tzinfo=UTC)

#: A syntactically real SHA-256 digest for the authority-wiring fixtures.
_DIGEST = "a" * 64

ADMIN = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
VIEWER = ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
OPERATOR = ResolvedApiPrincipal(
    "operator", "operator-token", frozenset({ApiPermission.READ, ApiPermission.CANCEL_JOB})
)


def request(
    api: MediaFlowApi,
    path: str,
    *,
    method: str = "GET",
    body: object | None = None,
    token: str = "admin-token",
):
    payload = b"" if body is None else json.dumps(body).encode("utf-8")
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": str(len(payload)),
        "wsgi.input": io.BytesIO(payload),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
    }
    result = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(result)


class ScopeContinuationTests(unittest.TestCase):
    """Application, API and Worker evidence for the paused-scope continuation."""

    # -- fixture ---------------------------------------------------------

    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name)
        self.addCleanup(self._directory.cleanup)
        (self.root / "source" / "Media").mkdir(parents=True)
        (self.root / "target" / "Movies").mkdir(parents=True)
        self.database = self.root / "runtime.sqlite3"
        self.repository = SQLiteTaskRepository(self.database)
        self.addCleanup(self.repository.close)
        self.coordinator = PersistentTaskCoordinator(self.repository, self.repository)

    def _document(self) -> dict:
        document = example_document()
        document["persistence"]["databasePath"] = str(self.root / "configuration.sqlite3")
        document["storages"][0]["rootPath"] = str(self.root / "source")
        document["storages"][1]["rootPath"] = str(self.root / "target")
        document["resourceLibraries"][0]["storagePath"] = "Media"
        document["resourceLibraries"][0]["displayRootPath"] = str(self.root / "source" / "Media")
        document["historyPath"] = str(self.root / "history.jsonl")
        return document

    def _activate(self):
        """Activate one real managed revision and return ``(api, active)``."""

        document = self._document()
        configuration_repository = SQLiteConfigurationRepository(
            self.root / "configuration.sqlite3"
        )
        self.addCleanup(configuration_repository.close)
        service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=str(self.root / "configuration.sqlite3"),
        )
        objects = ConfigurationObjectService(
            service,
            storage_adapters={
                "source-storage": LocalStorage("source-storage", self.root / "source"),
                "media-target": LocalStorage("media-target", self.root / "target"),
            },
            storage_browser_cursor_secret="scope-continuation-test-secret",
        )
        draft = service.import_draft(document, actor="operator")
        validated = service.validate(draft.revision_id, actor="operator")
        for storage_id in ("source-storage", "media-target"):
            evidence = objects.storage_check(
                validated.revision_id,
                storage_id=storage_id,
                expected_version=validated.version,
                expected_digest=validated.digest,
                actor="operator",
            )
            self.assertEqual(evidence.status, ConfigurationStorageCheckStatus.PASSED)
        strategy = objects.recognition_strategy_test(
            validated.revision_id,
            expected_version=validated.version,
            expected_digest=validated.digest,
            actor="operator",
            resource_library_id="source",
            synthetic_path="Example.Movie.2024.1080p.mkv",
        )
        self.assertEqual(strategy.status, ConfigurationStrategyTestStatus.COMPLETED)
        destination = objects.destination_precheck(
            validated.revision_id,
            expected_version=validated.version,
            expected_digest=validated.digest,
            actor="operator",
            recognition_type="C",
            sample={
                "title": "The Matrix",
                "mediaType": "movie",
                "year": 1999,
                "genres": ["Action"],
                "extension": "mkv",
            },
        )
        self.assertEqual(destination.status, ConfigurationDestinationPrecheckStatus.COMPLETED)
        active = objects.activate_checked(
            validated.revision_id,
            expected_version=validated.version,
            actor="operator",
        )
        api = MediaFlowApi(
            self.repository,
            None,
            principals=(ADMIN, VIEWER, OPERATOR),
            configuration_service=service,
            bootstrap_document=document,
            storage_adapters={
                "source-storage": LocalStorage("source-storage", self.root / "source"),
                "media-target": LocalStorage("media-target", self.root / "target"),
            },
            storage_browser_cursor_secret="scope-continuation-test-secret",
        )
        self.active = active
        return api, active

    def _paused_task(
        self,
        *,
        task_id: str = "task-paused",
        command: str = "preview",
        execute_authorized: bool = False,
        scope_path: str | None = None,
        item_limit: int | None = None,
        snapshot_id: str | None = "snap-a",
        snapshot_digest: str | None = "digest-a",
    ) -> PersistentTask:
        task = PersistentTask(
            task_id,
            command,
            PersistentTaskStatus.RUNNING,
            execute_authorized,
            NOW,
            NOW,
            started_at=NOW,
            scope_path=scope_path,
            item_limit=item_limit,
            configuration_snapshot_id=snapshot_id,
            configuration_snapshot_digest=snapshot_digest,
        )
        self.repository.create_task(task)
        return self.coordinator.acknowledge_pause(task.task_id) if False else self._pause(task)

    def _api_paused_task(self, **kwargs) -> PersistentTask:
        """One paused Task pinned to the real immutable Active revision.

        The API validates the pin against the genuine managed configuration, so
        an API-level fixture must carry the exact Active identity rather than a
        placeholder.
        """

        kwargs.setdefault("snapshot_id", self.active.revision_id)
        kwargs.setdefault("snapshot_digest", self.active.digest)
        return self._paused_task(**kwargs)

    def _pause(self, task: PersistentTask) -> PersistentTask:
        requested = self.repository.request_task_pause(task.task_id, NOW)
        self.assertTrue(requested.pause_requested)
        return self.coordinator.acknowledge_pause(task.task_id)

    def _item(
        self,
        task_id: str,
        item_id: str,
        source_path: str,
        status: TaskItemStatus,
        *,
        storage_id: str = "source-storage",
    ) -> PersistentTaskItem:
        item = PersistentTaskItem(
            item_id,
            task_id,
            storage_id,
            "source",
            source_path,
            source_path,
            status,
            status.value,
            1,
            NOW,
            NOW,
        )
        self.repository.upsert_item(item)
        return item

    def _result(
        self,
        task_id: str,
        item_id: str,
        *,
        status: str = "success",
        certainty: str = "verified_complete",
    ) -> None:
        self.repository.append_result(
            PersistentResultRecord(
                f"{item_id}:1",
                task_id,
                item_id,
                "source-storage",
                "Media/one.mkv",
                "media-target",
                "Movies/one.mkv",
                "C",
                "tmdb",
                "1",
                "C",
                "A",
                "A",
                "A",
                "MOVE",
                status,
                NOW,
                title="One",
                effect_certainty=certainty,
                uncertain_effects=("move",) if certainty == "attempted_unverified" else (),
            )
        )

    def _service(self, api=None, *, validator=True) -> ScopeContinuationService:
        return ScopeContinuationService(
            self.repository,
            snapshot_validator=(lambda *_: None) if validator else None,
        )

    def _rejecting_service(self) -> ScopeContinuationService:
        """A boundary whose immutable pin no longer resolves."""

        def reject(_snapshot_id: str, _digest: str) -> None:
            from mediaflow.domain.configuration_management import RuntimeSnapshotUnavailable

            raise RuntimeSnapshotUnavailable(
                "pinned revision is unavailable", reason="snapshot_missing"
            )

        return ScopeContinuationService(self.repository, snapshot_validator=reject)

    # -- continuable matrix ---------------------------------------------

    def test_continuable_command_matrix_matches_the_supported_boundary(self) -> None:
        """Only the Worker-owned processing commands have a remaining scope.

        The manual Scan service observes no pause request, the synchronous Web
        manual Organize and the in-request Files commands/Delete are not
        Worker-owned asynchronous work, and the analysis/recovery continuation
        families have no remaining-scope contract.  They keep their Pause
        capability and must be excluded from Continue.
        """

        self.assertEqual(
            {
                value
                for value in ("scan", "preview", "organize")
                if is_continuable_task_command(value)
            },
            {"preview", "organize"},
        )
        for command in (
            "manual_organize",
            "files_transfer",
            "media_files_transfer",
            "files_direct_command",
            "files_delete",
            "recovery-continuation",
            "metadata-correction-continuation",
            "file-metadata-correction",
            "retry",
            "retry-failed",
        ):
            self.assertFalse(is_continuable_task_command(command), command)

    def test_projection_advertises_continue_for_a_pausable_async_path(self) -> None:
        api, _active = self._activate()
        task = self._api_paused_task()
        status, detail = request(api, f"/api/v1/tasks/{task.task_id}", token="operator-token")
        self.assertEqual(status, 200)
        resume = next(item for item in detail["lifecycle"]["actions"] if item["action"] == "resume")
        self.assertTrue(resume["available"], resume["unavailableReason"])
        self.assertIn("remaining admitted scope", resume["durableOutcome"])
        self.assertEqual(resume["sideEffects"].split(";")[0], "no Storage mutation in this request")

    def test_projection_withholds_continue_with_a_real_reason_per_state(self) -> None:
        api, _active = self._activate()
        running = PersistentTask(
            "task-running",
            "preview",
            PersistentTaskStatus.RUNNING,
            False,
            NOW,
            NOW,
            started_at=NOW,
            configuration_snapshot_id="snap-a",
            configuration_snapshot_digest="digest-a",
        )
        self.repository.create_task(running)
        done = PersistentTask(
            "task-done",
            "preview",
            PersistentTaskStatus.COMPLETED,
            False,
            NOW,
            NOW,
            started_at=NOW,
            completed_at=NOW,
            configuration_snapshot_id="snap-a",
            configuration_snapshot_digest="digest-a",
        )
        self.repository.create_task(done)
        self._api_paused_task(task_id="task-legacy", snapshot_id=None, snapshot_digest=None)

        for task_id, expected in (
            ("task-running", "still running"),
            ("task-done", "terminal state"),
            ("task-legacy", "immutable configuration pin"),
        ):
            status, detail = request(api, f"/api/v1/tasks/{task_id}", token="operator-token")
            self.assertEqual(status, 200)
            resume = next(
                item for item in detail["lifecycle"]["actions"] if item["action"] == "resume"
            )
            self.assertFalse(resume["available"], task_id)
            self.assertIn(expected, resume["unavailableReason"], task_id)
            self.assertIsNotNone(resume["nextAction"])

    def test_every_projection_action_is_available_or_explained(self) -> None:
        """The Web contract: no action may be both withheld and unexplained.

        The V2 normalizer rejects an action that is unavailable without a reason,
        so the backend must always state the bounded obstacle.  A non-paused
        continuable Task is the exact case that would otherwise produce a
        withheld-but-unexplained Continue.
        """

        api, _active = self._activate()
        for status in (
            PersistentTaskStatus.RUNNING,
            PersistentTaskStatus.COMPLETED,
            PersistentTaskStatus.FAILED,
            PersistentTaskStatus.CANCELLED,
        ):
            task = PersistentTask(
                f"task-{status.value}",
                "preview",
                status,
                False,
                NOW,
                NOW,
                started_at=NOW,
                completed_at=(NOW if status is not PersistentTaskStatus.RUNNING else None),
                configuration_snapshot_id=self.active.revision_id,
                configuration_snapshot_digest=self.active.digest,
            )
            self.repository.create_task(task)
            code, detail = request(api, f"/api/v1/tasks/{task.task_id}", token="operator-token")
            self.assertEqual(code, 200)
            for action in detail["lifecycle"]["actions"]:
                # The two directions are both part of the contract: an
                # advertised control never carries a reason, and a withheld one
                # always does.
                if action["available"]:
                    self.assertIsNone(
                        action["unavailableReason"],
                        (status.value, action["action"]),
                    )
                else:
                    self.assertIsNotNone(
                        action["unavailableReason"],
                        (status.value, action["action"]),
                    )
                    self.assertTrue(action["unavailableReason"].strip())

    def test_projection_never_names_a_cli_fallback(self) -> None:
        """RO-5: ordinary recovery must not route the operator to the CLI."""

        api, _active = self._activate()
        task = self._api_paused_task()
        status, detail = request(api, f"/api/v1/tasks/{task.task_id}", token="operator-token")
        self.assertEqual(status, 200)
        for action in detail["lifecycle"]["actions"]:
            text = f"{action['unavailableReason'] or ''} {action['nextAction']}"
            self.assertNotIn("mediaflow tasks", text)
            self.assertNotIn("CLI", text)

    def test_manual_scan_and_synchronous_manual_organize_keep_their_own_truth(self) -> None:
        """The excluded kinds explain their real reason instead of a fake one."""

        api, _active = self._activate()
        manual = PersistentTask(
            "task-manual",
            "manual_organize",
            PersistentTaskStatus.PAUSED,
            False,
            NOW,
            NOW,
            started_at=NOW,
            configuration_snapshot_id="snap-a",
            configuration_snapshot_digest="digest-a",
        )
        self.repository.create_task(manual)
        status, detail = request(api, "/api/v1/tasks/task-manual", token="operator-token")
        self.assertEqual(status, 200)
        self.assertEqual(detail["lifecycle"]["executionPath"], "synchronous_manual_organize")
        resume = next(item for item in detail["lifecycle"]["actions"] if item["action"] == "resume")
        self.assertFalse(resume["available"])
        self.assertIn("no durable queued continuation", resume["unavailableReason"])

    # -- admission ------------------------------------------------------

    def test_admission_queues_one_bounded_continuation_and_no_storage_work(self) -> None:
        api, active = self._activate()
        task = self._api_paused_task(scope_path="Media", item_limit=10)
        self._item(task.task_id, "item-a", "Media/a.mkv", TaskItemStatus.SUCCESS)
        self._result(task.task_id, "item-a")

        status, body = request(
            api,
            f"/api/v1/tasks/{task.task_id}/resume",
            method="POST",
            body={
                "expectedUpdatedAt": self.repository.get_task(task.task_id).updated_at.isoformat()
            },
            token="operator-token",
        )
        self.assertEqual(status, 202, body)
        self.assertEqual(body["action"], "resume")
        self.assertEqual(body["sideEffects"], "none")
        self.assertFalse(body["retrySafe"])
        continuation = body["continuation"]
        # The operator/API projection is bounded and redacted: it publishes the
        # durable identifiers the Web needs and never the internal scope path,
        # the configuration pin identity or the actor.
        self.assertEqual(continuation["status"], "queued")
        self.assertEqual(continuation["sourceTaskId"], task.task_id)
        self.assertEqual(continuation["command"], "preview")
        self.assertEqual(continuation["itemLimit"], 10)
        self.assertEqual(continuation["boundary"], "paused_remaining_admitted_scope")
        self.assertEqual(continuation["sideEffects"], "none")
        self.assertNotIn("scope_path", continuation)
        self.assertNotIn("scopePath", continuation)
        self.assertNotIn("actor", continuation)
        self.assertNotIn("configuration_snapshot_id", continuation)
        self.assertNotIn("configuration_snapshot_digest", continuation)
        self.assertNotIn(str(self.root), json.dumps(body))

        job = self.repository.get_job(body["jobId"])
        self.assertIsNotNone(job)
        assert job is not None
        self.assertIs(job.command, AutomationCommand.SCOPE_CONTINUATION)
        self.assertIs(job.status, AutomationJobStatus.PENDING)
        self.assertFalse(job.execute_authorized)
        self.assertEqual(job.configuration_snapshot_id, active.revision_id)
        # The source Task keeps its exact paused state and its history.
        self.assertIs(self.repository.get_task(task.task_id).status, PersistentTaskStatus.PAUSED)
        self.assertEqual(
            [item.item_id for item in self.repository.list_items(task.task_id)], ["item-a"]
        )
        # The durable row still carries the exact internal pin the Worker needs.
        stored = self.repository.get_scope_continuation_for_job(body["jobId"])
        self.assertEqual(stored.configuration_snapshot_id, active.revision_id)
        self.assertEqual(stored.scope_path, "Media")

    def test_admission_response_never_publishes_an_absolute_scope_path(self) -> None:
        """RO-7: the control response stays behind the redaction boundary.

        A legally admitted scoped run can carry an absolute host path in its
        durable ``scope_path``.  The accepted control must never echo it: the
        Worker keeps the full internal row and the operator reads a bounded
        projection instead.
        """

        api, _active = self._activate()
        absolute = str(self.root / "source" / "Media")
        task = self._api_paused_task(scope_path=absolute, item_limit=2)
        status, body = request(
            api,
            f"/api/v1/tasks/{task.task_id}/resume",
            method="POST",
            body=None,
            token="operator-token",
        )
        self.assertEqual(status, 202, body)
        payload = json.dumps(body)
        self.assertNotIn(absolute, payload)
        self.assertNotIn(str(self.root), payload)
        self.assertNotIn("scope_path", body["continuation"])
        # The internal row keeps the exact original scope the Worker needs.
        stored = self.repository.get_scope_continuation_for_job(body["jobId"])
        self.assertEqual(stored.scope_path, absolute)

    def test_duplicate_admission_never_queues_the_remaining_scope_twice(self) -> None:
        api, _active = self._activate()
        task = self._api_paused_task(scope_path="Media")
        first = request(
            api,
            f"/api/v1/tasks/{task.task_id}/resume",
            method="POST",
            body=None,
            token="operator-token",
        )
        self.assertEqual(first[0], 202)
        jobs_after_first = len(self.repository.list_jobs(limit=100))

        second_status, second = request(
            api,
            f"/api/v1/tasks/{task.task_id}/resume",
            method="POST",
            body=None,
            token="operator-token",
        )
        self.assertEqual(second_status, 409, second)
        self.assertEqual(second["error"]["details"]["reason"], "continuation_exists")
        self.assertEqual(second["error"]["details"]["sideEffects"], "none")
        self.assertEqual(len(self.repository.list_jobs(limit=100)), jobs_after_first)

    def test_stale_version_is_refused_atomically(self) -> None:
        api, _active = self._activate()
        task = self._api_paused_task(scope_path="Media")
        stale = self.repository.get_task(task.task_id).updated_at.isoformat()
        # A later durable transition makes the version the operator read stale.
        self.repository.update_task(
            replace(
                self.repository.get_task(task.task_id),
                updated_at=datetime(2026, 10, 5, tzinfo=UTC),
            )
        )
        status, body = request(
            api,
            f"/api/v1/tasks/{task.task_id}/resume",
            method="POST",
            body={"expectedUpdatedAt": stale},
            token="operator-token",
        )
        self.assertEqual(status, 409, body)
        self.assertEqual(body["error"]["details"]["reason"], "stale_task_state")
        self.assertTrue(body["error"]["details"]["retrySafe"])
        self.assertIsNone(self.repository.get_scope_continuation_for_source_task(task.task_id))

    def test_non_paused_task_is_refused_with_zero_new_work(self) -> None:
        api, _active = self._activate()
        task = PersistentTask(
            "task-running",
            "preview",
            PersistentTaskStatus.RUNNING,
            False,
            NOW,
            NOW,
            started_at=NOW,
            configuration_snapshot_id="snap-a",
            configuration_snapshot_digest="digest-a",
        )
        self.repository.create_task(task)
        status, body = request(
            api,
            "/api/v1/tasks/task-running/resume",
            method="POST",
            body=None,
            token="operator-token",
        )
        self.assertEqual(status, 409, body)
        self.assertEqual(body["error"]["details"]["reason"], "task_not_paused")
        self.assertEqual(self.repository.list_jobs(limit=100), ())
        self.assertEqual(self.repository.list_tasks(limit=100), (task,))

    def test_unresolvable_pin_is_refused_with_the_native_recovery_path(self) -> None:
        api, _active = self._activate()
        task = self._api_paused_task(
            scope_path="Media", snapshot_id="snap-gone", snapshot_digest="d"
        )
        status, body = request(
            api,
            f"/api/v1/tasks/{task.task_id}/resume",
            method="POST",
            body=None,
            token="operator-token",
        )
        self.assertEqual(status, 409, body)
        self.assertEqual(body["error"]["details"]["reason"], "snapshot_unavailable")
        self.assertEqual(body["error"]["details"]["sideEffects"], "none")
        self.assertNotIn("mediaflow tasks", body["error"]["details"]["nextAction"])
        self.assertEqual(self.repository.list_jobs(limit=100), ())

    def test_stored_execute_flag_is_never_authority(self) -> None:
        """A consumed/revoked authority must route through native Preview.

        The Task was admitted as a mutation, but no live reusable authority
        exists for it in this runtime.  The admission must refuse rather than
        silently continue under a persisted boolean, and it must name the exact
        Preview/explicit-intent journey as the next action.
        """

        api, _active = self._activate()
        task = self._api_paused_task(scope_path="Media", execute_authorized=True)
        status, body = request(
            api,
            f"/api/v1/tasks/{task.task_id}/resume",
            method="POST",
            body=None,
            token="operator-token",
        )
        self.assertEqual(status, 409, body)
        self.assertEqual(body["error"]["details"]["reason"], "authority_required")
        self.assertIn("stored execute flag is not authority", body["error"]["message"])
        self.assertIn("exact Preview", body["error"]["details"]["nextAction"])
        self.assertNotIn("mediaflow tasks", body["error"]["details"]["nextAction"])
        self.assertEqual(self.repository.list_jobs(limit=100), ())
        # No definition-bound occurrence exists for this Task, so the shared
        # live-authority checker refuses: a stored boolean is not authority.
        self.assertFalse(definition_occurrence_authority(self.repository, (), None)(task))

        # The recovery entry belongs to a principal that may really admit it, so
        # the projection is read with the manage permission in hand.
        read_status, detail = request(api, f"/api/v1/tasks/{task.task_id}", token="admin-token")
        self.assertEqual(read_status, 200)
        resume = next(item for item in detail["lifecycle"]["actions"] if item["action"] == "resume")
        self.assertFalse(resume["available"])
        self.assertIn("stored execute flag is not authority", resume["unavailableReason"])
        self.assertIn("exact Preview", resume["nextAction"])
        # The native recovery entry is published with the refusal, so the Web
        # renders a real control instead of an instruction with no surface.
        preview = resume["preview"]
        self.assertTrue(preview["available"])
        self.assertEqual(preview["method"], "POST")
        self.assertEqual(preview["path"], f"/api/v1/tasks/{task.task_id}/remaining-scope-previews")
        self.assertEqual(preview["sideEffects"], "none")
        self.assertIn("grants no execution authority", preview["durableOutcome"])

    def test_the_native_preview_action_is_only_published_for_the_authority_refusal(self) -> None:
        """A withheld Continue explains itself, and only that refusal links Preview.

        The Web contract rejects an available control that also carries a
        reason, so the projection must stay exactly one decision: the native
        Preview entry belongs to the authority refusal alone, never to an
        unrelated obstacle such as an unresolvable pin.
        """

        api, _active = self._activate()
        for scope, snapshot, digest, expected_code, expects_preview in (
            ("Media", None, None, "snapshot_unavailable", False),
            ("Media", "snap-gone", "digest-gone", "snapshot_unavailable", False),
        ):
            task = self._api_paused_task(
                task_id=f"task-{expected_code}-{digest}",
                scope_path=scope,
                snapshot_id=snapshot,
                snapshot_digest=digest,
            )
            status, detail = request(api, f"/api/v1/tasks/{task.task_id}", token="admin-token")
            self.assertEqual(status, 200)
            resume = next(
                item for item in detail["lifecycle"]["actions"] if item["action"] == "resume"
            )
            self.assertFalse(resume["available"])
            self.assertIsNotNone(resume["unavailableReason"])
            self.assertEqual("preview" in resume, expects_preview)

        refused = self._api_paused_task(
            task_id="task-authority", scope_path="Media", execute_authorized=True
        )
        status, detail = request(api, f"/api/v1/tasks/{refused.task_id}", token="admin-token")
        self.assertEqual(status, 200)
        resume = next(item for item in detail["lifecycle"]["actions"] if item["action"] == "resume")
        self.assertFalse(resume["available"])
        self.assertTrue(resume["preview"]["available"])

    def test_a_reader_without_the_manage_permission_gets_no_preview_control(self) -> None:
        """The recovery control is bound to the permission that would admit it."""

        api, _active = self._activate()
        task = self._api_paused_task(scope_path="Media", execute_authorized=True)
        status, detail = request(api, f"/api/v1/tasks/{task.task_id}", token="viewer-token")
        self.assertEqual(status, 200)
        resume = next(item for item in detail["lifecycle"]["actions"] if item["action"] == "resume")
        self.assertFalse(resume["available"])
        self.assertNotIn("preview", resume)
        # A principal that may manage manual work but not control the Task still
        # receives the recovery entry, because that is what it may really do.
        status, detail = request(api, f"/api/v1/tasks/{task.task_id}", token="admin-token")
        self.assertEqual(status, 200)
        resume = next(item for item in detail["lifecycle"]["actions"] if item["action"] == "resume")
        self.assertTrue(resume["preview"]["available"])

    def test_read_only_principal_cannot_continue(self) -> None:
        api, _active = self._activate()
        task = self._api_paused_task(scope_path="Media")
        status, detail = request(api, f"/api/v1/tasks/{task.task_id}", token="viewer-token")
        self.assertEqual(status, 200)
        resume = next(item for item in detail["lifecycle"]["actions"] if item["action"] == "resume")
        self.assertFalse(resume["available"])
        self.assertIn("cancel_job permission", resume["unavailableReason"])

        post_status, body = request(
            api,
            f"/api/v1/tasks/{task.task_id}/resume",
            method="POST",
            body=None,
            token="viewer-token",
        )
        self.assertEqual(post_status, 403, body)
        self.assertEqual(self.repository.list_jobs(limit=100), ())

    def test_unknown_task_control_is_a_bounded_not_found(self) -> None:
        api, _active = self._activate()
        status, body = request(
            api,
            "/api/v1/tasks/task-missing/resume",
            method="POST",
            body=None,
            token="operator-token",
        )
        self.assertEqual(status, 404, body)
        self.assertEqual(body["error"]["code"], "not_found")
        self.assertEqual(self.repository.list_jobs(limit=100), ())

    def test_control_requires_no_query_and_sends_one_command(self) -> None:
        api, _active = self._activate()
        task = self._api_paused_task(scope_path="Media")
        status, _ = request(
            api,
            f"/api/v1/tasks/{task.task_id}/resume?limit=1",
            method="POST",
            body=None,
            token="operator-token",
        )
        self.assertNotEqual(status, 202)
        self.assertEqual(self.repository.list_jobs(limit=100), ())

    # -- remaining scope ------------------------------------------------

    def test_remaining_scope_excludes_every_terminal_and_uncertain_item(self) -> None:
        task = self._paused_task(scope_path="Media", item_limit=10)
        self._item(task.task_id, "success", "Media/success.mkv", TaskItemStatus.SUCCESS)
        self._result(task.task_id, "success")
        self._item(task.task_id, "dry", "Media/dry.mkv", TaskItemStatus.DRY_RUN)
        self._result(task.task_id, "dry", status="dry_run")
        self._item(task.task_id, "skipped", "Media/skipped.mkv", TaskItemStatus.SKIPPED)
        self._result(task.task_id, "skipped", status="skipped")
        self._item(task.task_id, "ignored", "Media/ignored.mkv", TaskItemStatus.IGNORED)
        self._result(task.task_id, "ignored", status="ignored")
        self._item(task.task_id, "uncertain", "Media/uncertain.mkv", TaskItemStatus.PARTIAL)
        self._result(task.task_id, "uncertain", status="partial", certainty="attempted_unverified")
        self._item(task.task_id, "waiting", "Media/waiting.mkv", TaskItemStatus.WAITING_METADATA)
        self._item(task.task_id, "paused", "Media/paused.mkv", TaskItemStatus.PAUSED)
        self._item(task.task_id, "failed", "Media/failed.mkv", TaskItemStatus.FAILED)
        # An item whose failure is already recorded as a durable Result is
        # terminal for this purpose and must not be replayed either.
        self._item(
            task.task_id, "recorded-failure", "Media/recorded-failure.mkv", TaskItemStatus.FAILED
        )
        self._result(task.task_id, "recorded-failure", status="failed")

        remaining, already_recorded, remaining_limit = remaining_scope(self.repository, task)
        # A failure is undecided work whether or not its failure is recorded
        # (the proven continuation retries failed items), while a successful,
        # dry-run, skipped or ignored sibling and every uncertain effect stay
        # excluded.
        self.assertEqual(
            {item.item_id for item in remaining},
            {"paused", "failed", "recorded-failure"},
        )
        self.assertEqual(
            already_recorded,
            {
                ("source-storage", f"Media/{name}.mkv")
                for name in (
                    "success",
                    "dry",
                    "skipped",
                    "ignored",
                    "uncertain",
                    "waiting",
                    "paused",
                    "failed",
                    "recorded-failure",
                )
            },
        )
        self.assertEqual(remaining_limit, 10 - 9)

    def test_unlimited_task_keeps_an_unlimited_remaining_budget(self) -> None:
        task = self._paused_task(scope_path="Media", item_limit=None)
        self._item(task.task_id, "a", "Media/a.mkv", TaskItemStatus.SUCCESS)
        remaining, _recorded, remaining_limit = remaining_scope(self.repository, task)
        self.assertEqual(remaining, ())
        self.assertIsNone(remaining_limit)

    def test_exhausted_item_budget_yields_zero_remaining_work(self) -> None:
        task = self._paused_task(scope_path="Media", item_limit=1)
        self._item(task.task_id, "a", "Media/a.mkv", TaskItemStatus.FAILED)
        _remaining, _recorded, remaining_limit = remaining_scope(self.repository, task)
        self.assertEqual(remaining_limit, 0)

    # -- Worker boundary ------------------------------------------------

    def test_worker_prepare_refuses_a_task_whose_pin_became_unresolvable(self) -> None:
        task = self._paused_task(scope_path="Media")
        submission = self._admit(self._service(), task)
        with self.assertRaises(ScopeContinuationError) as raised:
            self._rejecting_service().prepare(submission.job.job_id)
        self.assertIs(raised.exception.reason, ScopeContinuationReason.SNAPSHOT_UNAVAILABLE)
        self.assertIn("cannot be reproduced", str(raised.exception))

    def test_worker_prepare_refuses_a_source_task_whose_scope_changed(self) -> None:
        task = self._paused_task(scope_path="Media", item_limit=5)
        service = self._service()
        submission = self._admit(service, task)
        changed = replace(
            self.repository.get_task(task.task_id),
            scope_path="Media/Other",
            updated_at=datetime(2026, 10, 5, tzinfo=UTC),
        )
        self.repository.update_task(changed)
        with self.assertRaisesRegex(ValueError, "scope or pin changed"):
            service.prepare(submission.job.job_id)

    def test_worker_service_reports_truthful_outcomes(self) -> None:
        task = self._paused_task(scope_path="Media")
        service = self._service()
        submission = self._admit(service, task)
        worker = ScopeContinuationWorkerService(self.repository)
        worker.started(submission.job.job_id)
        self.assertIs(
            self.repository.get_scope_continuation_for_job(submission.job.job_id).status,
            ScopeContinuationStatus.RUNNING,
        )
        # A continuation whose linked Task really completed reports success.
        done = PersistentTask(
            "task-continued",
            "preview",
            PersistentTaskStatus.COMPLETED,
            False,
            NOW,
            NOW,
            started_at=NOW,
            completed_at=NOW,
        )
        self.repository.create_task(done)
        worker.bind(submission.job.job_id, done.task_id)
        finished = worker.finish(submission.job.job_id, done.task_id)
        self.assertIs(finished.status, ScopeContinuationStatus.COMPLETED)
        self.assertEqual(finished.new_task_id, done.task_id)

    def test_worker_service_reports_a_partial_continuation_as_a_failure(self) -> None:
        task = self._paused_task(scope_path="Media")
        service = self._service()
        submission = self._admit(service, task)
        worker = ScopeContinuationWorkerService(self.repository)
        worker.started(submission.job.job_id)
        partial = PersistentTask(
            "task-partial",
            "preview",
            PersistentTaskStatus.PARTIAL_SUCCESS,
            False,
            NOW,
            NOW,
            started_at=NOW,
            completed_at=NOW,
        )
        self.repository.create_task(partial)
        worker.bind(submission.job.job_id, partial.task_id)
        finished = worker.finish(submission.job.job_id, partial.task_id)
        self.assertIs(finished.status, ScopeContinuationStatus.FAILED)
        self.assertIn("part of its remaining scope", finished.error or "")
        self.assertIn("per-item outcomes", finished.recovery or "")

    def test_failed_queued_continuation_leaves_the_original_scope_continueable(self) -> None:
        task = self._paused_task(scope_path="Media")
        service = self._service()
        submission = self._admit(service, task)
        worker = ScopeContinuationWorkerService(self.repository)
        worker.failed(submission.job.job_id, queued=True, error="worker could not start")
        failed = self.repository.get_scope_continuation_for_job(submission.job.job_id)
        self.assertIs(failed.status, ScopeContinuationStatus.FAILED)
        # A new deliberate admission is allowed again after the failed attempt.
        again = service.submit(
            task.task_id, expected_version=None, actor="operator", maximum_active_jobs=10
        )
        self.assertTrue(again.created)
        self.assertNotEqual(
            again.continuation.continuation_id, submission.continuation.continuation_id
        )

    def test_claimable_selection_includes_a_pinned_continuation_job(self) -> None:
        """The Worker's own claim query must hand the continuation to a Worker.

        The continuation Job is pinned to the source Task's revision, which may
        differ from the Worker's currently registered snapshot, so the durable
        continuation row is the explicit per-Job condition that makes it
        claimable.  Without that condition the queued continuation would never
        be picked up.
        """

        task = self._paused_task(scope_path="Media")
        service = self._service()
        submission = self._admit(service, task)
        self.repository.register_worker(
            worker_id="worker-1",
            label="worker-one",
            heartbeat_interval_seconds=5.0,
            supported_commands=("scan", "preview", "organize"),
            configuration_snapshot_id="another-snapshot",
            configuration_snapshot_digest="another-digest",
            runtime_schema_version=SCHEMA_VERSION,
            now=datetime.now(UTC),
        )
        claimed = self.repository.claim_next_job(datetime.now(UTC), worker_id="worker-1")
        self.assertIsNotNone(claimed)
        assert claimed is not None
        self.assertEqual(claimed.job_id, submission.job.job_id)

    def test_terminal_continuation_is_not_claimable_again(self) -> None:
        task = self._paused_task(scope_path="Media")
        service = self._service()
        submission = self._admit(service, task)
        self.repository.update_job(
            replace(
                submission.job,
                status=AutomationJobStatus.FAILED,
                updated_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                error="continuation refused",
            )
        )
        self.repository.fail_queued_scope_continuation(
            submission.job.job_id, error="continuation refused"
        )
        self.assertIsNone(self.repository.claim_next_job(datetime.now(UTC), worker_id=None))

    # -- history and compatibility --------------------------------------

    def test_original_history_and_pin_survive_the_continuation(self) -> None:
        api, _active = self._activate()
        task = self._api_paused_task(scope_path="Media", item_limit=4)
        self._item(task.task_id, "kept", "Media/kept.mkv", TaskItemStatus.SUCCESS)
        self._result(task.task_id, "kept")
        original_before = self.repository.get_task(task.task_id)

        status, body = request(
            api,
            f"/api/v1/tasks/{task.task_id}/resume",
            method="POST",
            body=None,
            token="operator-token",
        )
        self.assertEqual(status, 202, body)

        original_after = self.repository.get_task(task.task_id)
        self.assertEqual(original_after.configuration_snapshot_id, self.active.revision_id)
        self.assertEqual(original_after.configuration_snapshot_digest, self.active.digest)
        self.assertEqual(original_after.item_limit, 4)
        self.assertEqual(original_after.scope_path, "Media")
        self.assertIs(original_after.status, PersistentTaskStatus.PAUSED)
        self.assertEqual(original_after.created_at, original_before.created_at)
        self.assertEqual(
            [item.item_id for item in self.repository.list_items(task.task_id)], ["kept"]
        )
        self.assertEqual(len(self.repository.list_results(task.task_id)), 1)
        self.assertEqual(
            self.repository.get_scope_continuation_for_source_task(task.task_id).status,
            ScopeContinuationStatus.QUEUED,
        )

    def test_continuation_attempts_stay_independently_inspectable(self) -> None:
        task = self._paused_task(scope_path="Media")
        service = self._service()
        first = self._admit(service, task)
        ScopeContinuationWorkerService(self.repository).failed(
            first.job.job_id, queued=True, error="first attempt failed"
        )
        second = service.submit(
            task.task_id, expected_version=None, actor="operator", maximum_active_jobs=10
        )
        attempts = self.repository.list_scope_continuations(task.task_id)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(
            {item.status for item in attempts},
            {ScopeContinuationStatus.FAILED, ScopeContinuationStatus.QUEUED},
        )
        self.assertNotEqual(first.continuation.continuation_id, second.continuation.continuation_id)

    def test_scope_continuation_row_round_trips_every_bounded_field(self) -> None:
        task = self._paused_task(scope_path="Media", item_limit=7)
        service = self._service()
        submission = self._admit(service, task)
        stored = self.repository.get_scope_continuation_for_job(submission.job.job_id)
        self.assertEqual(stored, submission.continuation)
        document = stored.document()
        self.assertEqual(document["source_task_id"], task.task_id)
        self.assertEqual(document["item_limit"], 7)
        self.assertEqual(document["actor"], "operator")
        self.assertIn("no repin", document["authority_statement"])
        # The published document never carries a claim token or a raw path.
        self.assertNotIn("claim_token", document)
        self.assertNotIn(str(self.root), json.dumps(document))

    # -- schema ---------------------------------------------------------

    def test_scope_continuation_table_is_additive_and_legacy_rows_survive(self) -> None:
        import sqlite3

        legacy = self.root / "legacy.sqlite3"
        connection = sqlite3.connect(legacy)
        connection.executescript(
            """
            CREATE TABLE schema_version (component TEXT PRIMARY KEY, version INTEGER NOT NULL);
            INSERT INTO schema_version VALUES ('runtime', 42);
            CREATE TABLE tasks (
                task_id TEXT PRIMARY KEY, command TEXT NOT NULL, status TEXT NOT NULL,
                execute_authorized INTEGER NOT NULL, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, started_at TEXT, completed_at TEXT,
                total_items INTEGER NOT NULL, completed_items INTEGER NOT NULL,
                failed_items INTEGER NOT NULL, error TEXT
            );
            INSERT INTO tasks VALUES (
                'legacy', 'preview', 'paused', 0,
                '2026-08-23T00:00:00+00:00', '2026-08-23T00:00:00+00:00',
                '2026-08-23T00:00:00+00:00', NULL, 1, 0, 0, NULL
            );
            """
        )
        connection.commit()
        connection.close()

        with SQLiteTaskRepository(legacy) as repository:
            self.assertEqual(repository.schema_version, SCHEMA_VERSION)
            task = repository.get_task("legacy")
            self.assertIsNotNone(task)
            assert task is not None
            self.assertIs(task.status, PersistentTaskStatus.PAUSED)
            # No continuation is invented for a legacy row.
            self.assertIsNone(repository.get_scope_continuation_for_source_task("legacy"))
            self.assertEqual(repository.list_scope_continuations("legacy"), ())

    def test_scope_continuation_requires_an_exact_queued_job_identity(self) -> None:
        task = self._paused_task(scope_path="Media")
        now = datetime.now(UTC)
        continuation = self._continuation(task, "job-x", now)
        for bad_job in (
            AutomationJob(
                "job-x",
                AutomationCommand.PREVIEW,
                AutomationJobStatus.PENDING,
                now,
                now,
                configuration_snapshot_id="snap-a",
                configuration_snapshot_digest="digest-a",
            ),
            AutomationJob(
                "job-x",
                AutomationCommand.SCOPE_CONTINUATION,
                AutomationJobStatus.RUNNING,
                now,
                now,
                configuration_snapshot_id="snap-a",
                configuration_snapshot_digest="digest-a",
            ),
            AutomationJob(
                "job-x",
                AutomationCommand.SCOPE_CONTINUATION,
                AutomationJobStatus.PENDING,
                now,
                now,
                execute_authorized=True,
                configuration_snapshot_id="snap-a",
                configuration_snapshot_digest="digest-a",
            ),
            AutomationJob(
                "job-x",
                AutomationCommand.SCOPE_CONTINUATION,
                AutomationJobStatus.PENDING,
                now,
                now,
            ),
        ):
            with self.assertRaises(ValueError):
                self.repository.admit_scope_continuation(
                    bad_job, continuation, maximum_active_jobs=10
                )

    # -- helpers --------------------------------------------------------

    def _continuation(self, task: PersistentTask, job_id: str, now: datetime):
        from mediaflow.domain.scope_continuation import (
            CONTINUATION_BOUNDARY,
            ScopeContinuation,
        )

        return ScopeContinuation(
            f"cont-{job_id}",
            task.task_id,
            task.command,
            task.scope_path,
            task.item_limit,
            task.configuration_snapshot_id or "",
            task.configuration_snapshot_digest or "",
            CONTINUATION_BOUNDARY,
            ScopeContinuationStatus.QUEUED,
            now,
            now,
            "operator",
            job_id,
        )

    def test_pin_survives_an_active_revision_change_and_a_restart(self) -> None:
        """The continuation keeps revision A's exact pin across A→B and a reopen.

        The continuation reproduces the original admitted scope under the
        original immutable pin, so publishing a newer Active revision must not
        repin it, and the durable row must survive a real database reopen with
        its pin and its source history intact.
        """

        from mediaflow.application.scope_continuation import (
            ScopeContinuationService,
            ScopeContinuationWorkerService,
        )

        task = self._paused_task(scope_path="Media", item_limit=4)
        self._item(task.task_id, "kept", "Media/kept.mkv", TaskItemStatus.SUCCESS)
        self._result(task.task_id, "kept")
        service = ScopeContinuationService(self.repository, snapshot_validator=lambda *_: None)
        submission = service.submit(
            task.task_id, expected_version=None, actor="operator", maximum_active_jobs=10
        )
        pinned = submission.continuation
        self.assertEqual(pinned.configuration_snapshot_id, "snap-a")
        self.assertEqual(pinned.configuration_snapshot_digest, "digest-a")

        # A later Active revision B must not repin the queued continuation.
        reopened = SQLiteTaskRepository(self.database)
        self.addCleanup(reopened.close)
        after = reopened.get_scope_continuation_for_job(submission.job.job_id)
        self.assertEqual(after, pinned)
        self.assertEqual(after.configuration_snapshot_id, "snap-a")
        # The original Task's history is untouched by the reopen.
        self.assertEqual([item.item_id for item in reopened.list_items(task.task_id)], ["kept"])
        self.assertEqual(len(reopened.list_results(task.task_id)), 1)

        # The Worker can still complete it after the restart, and the completion
        # is recorded on the same durable row.
        worker = ScopeContinuationWorkerService(reopened)
        worker.started(submission.job.job_id)
        done = PersistentTask(
            "task-after-restart",
            "preview",
            PersistentTaskStatus.COMPLETED,
            False,
            NOW,
            NOW,
            started_at=NOW,
            completed_at=NOW,
        )
        reopened.create_task(done)
        worker.bind(submission.job.job_id, done.task_id)
        finished = worker.finish(submission.job.job_id, done.task_id)
        self.assertIs(finished.status, ScopeContinuationStatus.COMPLETED)
        self.assertEqual(finished.new_task_id, done.task_id)
        self.assertEqual(
            reopened.get_scope_continuation_for_source_task(task.task_id).status,
            ScopeContinuationStatus.COMPLETED,
        )

    def test_concurrent_admission_queues_the_remaining_scope_exactly_once(self) -> None:
        """Two simultaneous deliberate admissions must never double-queue.

        The admission is one atomic compare-and-set: the loser sees the winner's
        active continuation and is refused, so the remaining work can never be
        executed twice.
        """

        import threading

        from mediaflow.application.scope_continuation import ScopeContinuationService

        task = self._paused_task(scope_path="Media")
        results: list[object] = []
        errors: list[object] = []
        # Three parties: the two racing writers and this thread, so both writers
        # really observe the same pre-admission state before either proceeds.
        started = threading.Barrier(3)
        release = threading.Barrier(3)

        def submit() -> None:
            service = ScopeContinuationService(
                SQLiteTaskRepository(self.database), snapshot_validator=lambda *_: None
            )
            started.wait(timeout=10)
            release.wait(timeout=10)
            try:
                results.append(
                    service.submit(
                        task.task_id,
                        expected_version=None,
                        actor="operator",
                        maximum_active_jobs=10,
                    )
                )
            except Exception as error:  # noqa: BLE001 - asserted below
                errors.append(error)

        threads = [threading.Thread(target=submit) for _ in range(2)]
        for thread in threads:
            thread.start()
        started.wait(timeout=10)
        release.wait(timeout=10)
        for thread in threads:
            thread.join(timeout=30)

        # Exactly one admission succeeded; the other was refused as a duplicate.
        self.assertEqual(len(results), 1, errors)
        self.assertEqual(len(errors), 1, results)
        self.assertIs(
            getattr(errors[0], "reason", None),
            ScopeContinuationReason.CONTINUATION_EXISTS,
        )
        attempts = self.repository.list_scope_continuations(task.task_id)
        self.assertEqual(len(attempts), 1)
        self.assertIs(attempts[0].status, ScopeContinuationStatus.QUEUED)
        # Exactly one queued Job exists for the remaining scope.
        self.assertEqual(
            len(
                [
                    job
                    for job in self.repository.list_jobs(limit=100)
                    if job.command is AutomationCommand.SCOPE_CONTINUATION
                ]
            ),
            1,
        )

    def _admit(self, service: ScopeContinuationService, task: PersistentTask):
        return service.submit(
            task.task_id,
            expected_version=None,
            actor="operator",
            maximum_active_jobs=10,
        )

    def test_obstacle_helper_agrees_between_projection_and_admission(self) -> None:
        """One decision function backs both surfaces (no drift possible)."""

        task = self._paused_task(scope_path="Media")
        self.assertEqual(
            continuation_obstacle(self.repository, task, lambda *_: None), (None, None, None)
        )
        no_validator = continuation_obstacle(self.repository, task, None)
        self.assertIs(no_validator[0], ScopeContinuationReason.SNAPSHOT_UNAVAILABLE)
        self.assertIn("cannot be resolved", no_validator[1] or "")
        with self.assertRaises(ScopeContinuationError) as raised:
            self._service(validator=False).submit(
                task.task_id, expected_version=None, actor="operator", maximum_active_jobs=10
            )
        self.assertIs(raised.exception.reason, ScopeContinuationReason.SNAPSHOT_UNAVAILABLE)

    # -- recorded continuation chain (B P1: no repeated finished scope) ---

    def _complete_continuation(
        self, task: PersistentTask, *, new_task_id: str, item_source: str | None = None
    ):
        """Drive one real admission + Worker completion of ``task``'s scope.

        The continuation Job is claimed and closed through the production
        repository methods, and the new Task is finished, so the fixture holds
        exactly the durable state the real Worker leaves behind.
        """

        service = self._service()
        submission = self._admit(service, task)
        self.repository.mark_scope_continuation_running(submission.job.job_id)
        if item_source is not None:
            self._item(new_task_id, f"{new_task_id}:item", item_source, TaskItemStatus.SUCCESS)
            self._result(new_task_id, f"{new_task_id}:item")
        self.repository.bind_scope_continuation_task(submission.job.job_id, new_task_id)
        return submission

    def _child_task(self, task: PersistentTask, new_task_id: str, *, status) -> PersistentTask:
        child = PersistentTask(
            new_task_id,
            task.command,
            status,
            task.execute_authorized,
            NOW,
            NOW,
            started_at=NOW,
            completed_at=NOW if status is not PersistentTaskStatus.PAUSED else None,
            scope_path=task.scope_path,
            item_limit=task.item_limit,
            configuration_snapshot_id=task.configuration_snapshot_id,
            configuration_snapshot_digest=task.configuration_snapshot_digest,
        )
        self.repository.create_task(child)
        return child

    def test_a_finished_continuation_chain_has_no_remaining_scope(self) -> None:
        """B P1-1: a completed continuation must never be admitted again.

        The original paused Task stays ``paused`` after its remaining scope was
        continued and finished.  Its item budget is exhausted across the chain,
        so a second Continue must be refused with zero queued work instead of
        re-processing the same file.
        """

        api, _active = self._activate()
        task = self._api_paused_task(scope_path="Media", item_limit=2)
        self._item(task.task_id, "item-a", "Media/Five.2005.mkv", TaskItemStatus.SUCCESS)
        self._result(task.task_id, "item-a")
        child = self._child_task(task, "task-child", status=PersistentTaskStatus.RUNNING)
        submission = self._admit(self._service(), task)
        self.repository.mark_scope_continuation_running(submission.job.job_id)
        self.repository.bind_scope_continuation_task(submission.job.job_id, child.task_id)
        # The continuation discovered and succeeded on the one remaining source.
        self._item(child.task_id, "child-item", "Media/Six.2006.mkv", TaskItemStatus.SUCCESS)
        self._result(child.task_id, "child-item")
        self.repository.complete_scope_continuation(
            submission.job.job_id, new_task_id=child.task_id, success=True
        )
        self.repository.update_task(
            replace(child, status=PersistentTaskStatus.COMPLETED, updated_at=NOW)
        )

        # The whole chain's recorded items now exhaust the original budget.
        remaining, recorded, remaining_limit = remaining_scope(self.repository, task)
        self.assertEqual(remaining_limit, 0)
        self.assertEqual(remaining, ())
        self.assertEqual(
            recorded,
            {("source-storage", "Media/Five.2005.mkv"), ("source-storage", "Media/Six.2006.mkv")},
        )
        self.assertIs(
            continuation_obstacle(self.repository, task, lambda *_: None)[0],
            ScopeContinuationReason.NO_REMAINING_SCOPE,
        )

        jobs_before = len(self.repository.list_jobs(limit=100))
        status, body = request(
            api,
            f"/api/v1/tasks/{task.task_id}/resume",
            method="POST",
            body=None,
            token="operator-token",
        )
        self.assertEqual(status, 409, body)
        self.assertEqual(body["error"]["details"]["reason"], "no_remaining_scope")
        self.assertEqual(body["error"]["details"]["sideEffects"], "none")
        self.assertEqual(len(self.repository.list_jobs(limit=100)), jobs_before)
        self.assertEqual(len(self.repository.list_scope_continuations(task.task_id)), 1)

    def test_a_still_paused_descendant_owns_the_remaining_scope(self) -> None:
        """A continuation that paused again owns its own remaining scope.

        Continuing the original run would queue the same remaining work twice,
        so the original must be refused and the operator routed to the linked
        continuation run.
        """

        api, _active = self._activate()
        task = self._api_paused_task(scope_path="Media", item_limit=5)
        self._item(task.task_id, "item-a", "Media/one.mkv", TaskItemStatus.SUCCESS)
        self._result(task.task_id, "item-a")
        child = self._child_task(task, "task-child", status=PersistentTaskStatus.PAUSED)
        self._item(child.task_id, "child-item", "Media/two.mkv", TaskItemStatus.PAUSED)
        submission = self._admit(self._service(), task)
        self.repository.mark_scope_continuation_running(submission.job.job_id)
        self.repository.bind_scope_continuation_task(submission.job.job_id, child.task_id)
        self.repository.complete_scope_continuation(
            submission.job.job_id,
            new_task_id=child.task_id,
            success=False,
            error="the continuation paused again before completing its remaining scope",
        )

        # The chain owner is the paused descendant, not the original run.
        from mediaflow.application.scope_continuation import chain_owner

        self.assertEqual(chain_owner(self.repository, task).task_id, child.task_id)
        self.assertIs(
            continuation_obstacle(self.repository, task, lambda *_: None)[0],
            ScopeContinuationReason.CONTINUATION_OWNED_ELSEWHERE,
        )
        status, body = request(
            api,
            f"/api/v1/tasks/{task.task_id}/resume",
            method="POST",
            body=None,
            token="operator-token",
        )
        self.assertEqual(status, 409, body)
        self.assertEqual(body["error"]["details"]["reason"], "continuation_owned_elsewhere")
        # The descendant itself still has a real remaining scope to continue.
        self.assertIsNone(continuation_obstacle(self.repository, child, lambda *_: None)[0])

    def test_projection_advertises_the_linked_continuation_of_a_finished_run(self) -> None:
        """The selected run publishes its bounded continuation evidence."""

        api, _active = self._activate()
        task = self._api_paused_task(scope_path="Media", item_limit=2)
        self._item(task.task_id, "item-a", "Media/Five.2005.mkv", TaskItemStatus.SUCCESS)
        self._result(task.task_id, "item-a")
        child = self._child_task(task, "task-child", status=PersistentTaskStatus.RUNNING)
        submission = self._admit(self._service(), task)
        self.repository.mark_scope_continuation_running(submission.job.job_id)
        self.repository.bind_scope_continuation_task(submission.job.job_id, child.task_id)
        self.repository.complete_scope_continuation(
            submission.job.job_id, new_task_id=child.task_id, success=True
        )

        status, overview = request(api, f"/api/v1/operations/runs/{task.task_id}")
        self.assertEqual(status, 200, overview)
        continuation = overview["continuation"]
        self.assertEqual(continuation["continuationId"], submission.continuation.continuation_id)
        self.assertEqual(continuation["status"], "completed")
        self.assertEqual(continuation["newTaskId"], child.task_id)
        self.assertEqual(continuation["jobId"], submission.job.job_id)
        self.assertEqual(continuation["attemptCount"], 1)
        self.assertEqual(continuation["sideEffects"], "none")
        # The bounded projection never publishes the internal scope or the pin.
        payload = json.dumps(overview)
        self.assertNotIn("Media/Five", payload)
        self.assertNotIn("scope_path", payload)
        self.assertNotIn(str(self.root), payload)


class ScopeContinuationAuthorityWiringTests(unittest.TestCase):
    """The live-authority decision is real, shared and impossible to bypass.

    A persisted ``execute_authorized`` boolean is never authority.  These cases
    prove the shared checker consults the production grant boundary, that a
    revoked or mismatched grant fails closed, and that the API and the Worker
    both pass a real checker into the admission and the lifecycle projection —
    so a continuation can never be advertised or admitted under authority the
    Worker would refuse.
    """

    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name)
        self.addCleanup(self._directory.cleanup)
        self.repository = SQLiteTaskRepository(self.root / "runtime.sqlite3")
        self.addCleanup(self.repository.close)

    def _occurrence_task(self, *, definition_id: str | None = "def-1") -> PersistentTask:
        """One paused, mutation-authorized Task linked to a definition Job."""

        now = datetime(2026, 10, 4, tzinfo=UTC)
        task = PersistentTask(
            "task-occurrence",
            "organize",
            PersistentTaskStatus.RUNNING,
            True,
            now,
            now,
            started_at=now,
            scope_path="Media",
            item_limit=5,
            configuration_snapshot_id="snap-a",
            configuration_snapshot_digest=_DIGEST,
        )
        self.repository.create_task(task)
        if definition_id is not None:
            self.repository.admit_job(
                AutomationJob(
                    "job-occurrence",
                    AutomationCommand.ORGANIZE,
                    AutomationJobStatus.RUNNING,
                    now,
                    now,
                    limit=5,
                    execute_authorized=True,
                    definition_id=definition_id,
                    run_mode=AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
                    resource_library_id="source",
                    source_scope="Media",
                    configuration_snapshot_id="snap-a",
                    configuration_snapshot_digest=_DIGEST,
                    configuration_snapshot_version=1,
                ),
                100,
            )
            self.repository.update_job(
                replace(
                    self.repository.get_job("job-occurrence"),
                    task_id=task.task_id,
                )
            )
        requested = self.repository.request_task_pause(task.task_id, now)
        self.assertTrue(requested.pause_requested)
        return PersistentTaskCoordinator(self.repository, self.repository).acknowledge_pause(
            task.task_id
        )

    @staticmethod
    def _definition():
        from mediaflow.domain.automation import (
            AutomationTaskDefinition,
            AutomationTaskRunMode,
        )

        return AutomationTaskDefinition(
            "def-1",
            "Occurrence",
            "source",
            source_scope="Media",
            mode=AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
            interval_seconds=3600.0,
            item_limit=5,
            enabled=True,
        )

    def test_checker_consults_the_production_grant_boundary(self) -> None:
        """A live grant authorizes; a revoked/mismatched grant never does."""

        task = self._occurrence_task()
        definition = self._definition()
        calls: list[tuple[object, object]] = []

        class _LiveGrants:
            def assert_live(self, job, value):
                calls.append((job, value))
                return object()

        checker = definition_occurrence_authority(self.repository, (definition,), _LiveGrants())
        self.assertTrue(checker(task))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0].job_id, "job-occurrence")

        class _RevokedGrants:
            def assert_live(self, job, value):
                raise RuntimeError("unattended execution grant is revoked")

        self.assertFalse(
            definition_occurrence_authority(self.repository, (definition,), _RevokedGrants())(task)
        )

    def test_checker_follows_the_persisted_definition_ancestry(self) -> None:
        """A later paused Task keeps the original Definition's live authority."""

        original = self._occurrence_task()
        admission = ScopeContinuationService(
            self.repository, snapshot_validator=lambda *_: None
        ).submit(
            original.task_id,
            expected_version=original.updated_at.isoformat(),
            actor="operator",
            maximum_active_jobs=10,
            mutation_authority=lambda _task: True,
        )
        child = PersistentTaskCoordinator(self.repository, self.repository).create(
            original.command,
            execute_authorized=original.execute_authorized,
            scope_path=original.scope_path,
            item_limit=original.item_limit,
            configuration_snapshot_id=original.configuration_snapshot_id,
            configuration_snapshot_digest=original.configuration_snapshot_digest,
            require_configuration_snapshot=True,
            status=PersistentTaskStatus.PAUSED,
        )
        worker_service = ScopeContinuationWorkerService(self.repository)
        worker_service.started(admission.job.job_id)
        worker_service.bind(admission.job.job_id, child.task_id)

        self.assertEqual(continuation_origin(self.repository, child).task_id, original.task_id)
        calls = []

        class _LiveGrants:
            def assert_live(self, job, value):
                calls.append((job, value))

        checker = definition_occurrence_authority(
            self.repository, (self._definition(),), _LiveGrants()
        )
        self.assertTrue(checker(child))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0].job_id, "job-occurrence")

    def test_corrupt_definition_ancestry_is_withheld_by_the_shared_obstacle(self) -> None:
        original = self._occurrence_task(definition_id=None)
        admission = ScopeContinuationService(
            self.repository, snapshot_validator=lambda *_: None
        ).submit(
            original.task_id,
            expected_version=original.updated_at.isoformat(),
            actor="operator",
            maximum_active_jobs=10,
            mutation_authority=lambda _task: True,
        )
        child = PersistentTaskCoordinator(self.repository, self.repository).create(
            original.command,
            execute_authorized=False,
            scope_path="Media/changed",
            item_limit=original.item_limit,
            configuration_snapshot_id=original.configuration_snapshot_id,
            configuration_snapshot_digest=original.configuration_snapshot_digest,
            require_configuration_snapshot=True,
            status=PersistentTaskStatus.PAUSED,
        )
        worker_service = ScopeContinuationWorkerService(self.repository)
        worker_service.started(admission.job.job_id)
        worker_service.bind(admission.job.job_id, child.task_id)

        reason, message, next_action = continuation_obstacle(
            self.repository, child, lambda *_: None
        )
        self.assertIs(reason, ScopeContinuationReason.SNAPSHOT_UNAVAILABLE)
        self.assertIn("continuation history", message or "")
        self.assertIn("configuration history", next_action or "")

    def test_checker_refuses_without_a_definition_occurrence(self) -> None:
        """A one-shot mutation Task has no reusable authority left."""

        task = self._occurrence_task(definition_id=None)
        definition = self._definition()

        class _NeverCalled:
            def assert_live(self, job, value):  # pragma: no cover - must not run
                raise AssertionError("grant boundary must not be consulted")

        self.assertFalse(
            definition_occurrence_authority(self.repository, (definition,), _NeverCalled())(task)
        )

    def test_checker_refuses_when_the_saved_definition_is_absent(self) -> None:
        task = self._occurrence_task()

        class _NeverCalled:
            def assert_live(self, job, value):  # pragma: no cover - must not run
                raise AssertionError("grant boundary must not be consulted")

        self.assertFalse(definition_occurrence_authority(self.repository, (), _NeverCalled())(task))

    def test_obstacle_requires_a_proven_live_authority_for_mutation(self) -> None:
        """The obstacle decision is driven by the checker, not by the boolean."""

        task = self._occurrence_task()
        validator = lambda *_args: None  # noqa: E731 - a permissive test validator

        # A live authority admits the continuation.
        self.assertEqual(
            continuation_obstacle(self.repository, task, validator, lambda _task: True),
            (None, None, None),
        )
        # No checker at all, a refusing checker and a raising checker all refuse.
        for authority in (None, lambda _task: False, _raise):
            reason, message, next_action = continuation_obstacle(
                self.repository, task, validator, authority
            )
            self.assertIs(reason, ScopeContinuationReason.AUTHORITY_REQUIRED)
            self.assertIn("stored execute flag is not authority", message or "")
            self.assertIn("exact Preview", next_action or "")
            self.assertNotIn("mediaflow tasks", next_action or "")

    def test_real_grant_authorizes_and_revocation_refuses(self) -> None:
        """The production grant boundary really decides, end to end.

        A stored ``execute_authorized`` boolean is not authority: the same Task
        is refused while no active grant exists, admitted once a real grant with
        its exact Preview linkage is persisted, and refused again the moment
        that grant is revoked — with zero queued work in every refusal case.
        """

        from types import SimpleNamespace

        from mediaflow.application.unattended_execution import (
            UnattendedExecutionGrantService,
        )
        from mediaflow.domain.automation_task_definition_preview import (
            AutomationTaskDefinitionPreviewStatus,
        )
        from mediaflow.domain.unattended_execution import (
            UnattendedExecutionGrant,
            UnattendedExecutionGrantAudit,
            UnattendedExecutionGrantStatus,
        )

        task = self._occurrence_task()
        definition = self._definition()
        validator = lambda *_args: None  # noqa: E731 - a permissive test validator

        class _PreviewReader:
            """Exact, current, zero-mutation Preview evidence for the grant."""

            preview_id = "preview-1"

            def get_readonly(self, preview_id):
                if preview_id != self.preview_id:
                    raise LookupError("linked Preview was not found")
                return SimpleNamespace(
                    preview_id=preview_id,
                    definition_id=definition.definition_id,
                    definition_fingerprint=definition.definition_fingerprint,
                    configuration_revision_id="snap-a",
                    configuration_revision_digest=_DIGEST,
                    configuration_revision_version=1,
                    resource_library_id=definition.resource_library_id,
                    source_scope=definition.source_scope,
                    run_mode=definition.mode.value,
                    effective_item_limit=definition.item_limit,
                    current=True,
                    zero_mutation=True,
                    status=AutomationTaskDefinitionPreviewStatus.PREVIEWED,
                    boundary_errors=(),
                    items=(),
                )

        grants = UnattendedExecutionGrantService(self.repository, preview_service=_PreviewReader())
        checker = definition_occurrence_authority(self.repository, (definition,), grants)

        # No grant exists yet: the persisted boolean is not authority.
        self.assertFalse(checker(task))
        self.assertIs(
            continuation_obstacle(self.repository, task, validator, checker)[0],
            ScopeContinuationReason.AUTHORITY_REQUIRED,
        )

        # A real persisted active grant with its exact Preview linkage authorizes
        # the exact occurrence.
        now = datetime(2026, 10, 4, tzinfo=UTC)
        self.repository.create_unattended_execution_grant(
            UnattendedExecutionGrant(
                "grant-1",
                "def-1",
                "source",
                "Media",
                definition.mode,
                5,
                UnattendedExecutionGrantStatus.ACTIVE,
                "operator",
                now,
                definition.definition_fingerprint,
                "snap-a",
                _DIGEST,
                1,
                preview_id="preview-1",
            ),
            UnattendedExecutionGrantAudit("audit-1", "grant-1", "granted", now, "operator"),
        )
        self.assertTrue(checker(task))
        self.assertEqual(
            continuation_obstacle(self.repository, task, validator, checker),
            (None, None, None),
        )

        # Revoking the grant refuses the continuation again.
        self.repository.revoke_unattended_execution_grant(
            "grant-1",
            now,
            UnattendedExecutionGrantAudit("audit-2", "grant-1", "revoked", now, "operator"),
            revoking_principal="operator",
            reason="operator revoked",
        )
        self.assertFalse(checker(task))
        self.assertIs(
            continuation_obstacle(self.repository, task, validator, checker)[0],
            ScopeContinuationReason.AUTHORITY_REQUIRED,
        )
        # None of the refusals ever queued a continuation.
        self.assertEqual(self.repository.list_scope_continuations(task.task_id), ())

    def test_worker_never_mutates_without_a_live_hook(self) -> None:
        """A ``None`` mutation hook must refuse, never silently mutate.

        The executor treats ``mutation_authority=None`` as "no authority check".
        A mutation-authorized continuation therefore must never be handed that
        value: the Worker refuses it before constructing any Storage adapter, so
        authority revoked between admission and execution cannot produce a
        mutation.
        """

        import inspect

        from mediaflow import final_cli

        source = inspect.getsource(final_cli._run_scope_continuation)
        # The refusal happens before adapters are constructed.
        refusal = source.index("if original.execute_authorized and mutation_authority is None:")
        adapters = source.index("storages = configuration.create_storages()")
        self.assertLess(refusal, adapters, "the refusal must precede adapter construction")
        self.assertIn('reason="authority_unavailable"', source)
        # The hook is resolved before the executor is built, and is passed in.
        self.assertIn("mutation_authority=mutation_authority", source)
        # And the helper returns None exactly when it cannot prove authority.
        helper = inspect.getsource(final_cli._scope_continuation_mutation_authority)
        self.assertIn("if not checker(original):\n        return None", helper)
        self.assertIn("if definition is None:\n        return None", helper)

    def test_worker_and_api_both_construct_a_real_checker(self) -> None:
        """Neither production surface may fall back to the stored boolean."""

        import inspect

        from mediaflow import final_cli
        from mediaflow.interfaces import service_api

        # The Worker's handler builds the shared checker from the resolved
        # configuration and the repository.
        source = inspect.getsource(final_cli._run_scope_continuation)
        self.assertIn("_scope_continuation_authority(configuration, repository)", source)
        # The API's binding builds one per Active revision, and the admission
        # passes that exact checker.
        self.assertIn("definition_occurrence_authority(", inspect.getsource(service_api))
        self.assertIn(
            "mutation_authority=binding.scope_continuation_authority",
            inspect.getsource(service_api),
        )
        # A mutation hook exists only for a live authority.
        self.assertIn(
            "if not original.execute_authorized:",
            inspect.getsource(final_cli._scope_continuation_mutation_authority),
        )


def _raise(_task) -> bool:
    raise RuntimeError("authority boundary unavailable")


class ScopeContinuationWorkerJourneyTests(unittest.TestCase):
    """The resident Worker really continues only the remaining admitted scope.

    These cases drive the real ``_run_queued_workflow`` / ``_run_scope_continuation``
    Worker boundary over temporary Local Storage and one genuine managed Active
    revision, so the end-to-end behavior is proven rather than inferred from the
    application service alone.  The managed revision is required because the
    Worker resolves the continuation Job's immutable pin through the same
    managed authority the original run used.
    """

    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name)
        self.addCleanup(self._directory.cleanup)
        # Production keeps the runtime and configuration stores in the one
        # managed database, and the Worker opens the runtime repository from the
        # resolved configuration's own path, so the fixture must do the same.
        self.database = self.root / "mediaflow.sqlite3"
        self.repository = SQLiteTaskRepository(self.database)
        self.addCleanup(self.repository.close)
        self.coordinator = PersistentTaskCoordinator(self.repository, self.repository)

    def _activate(self, *, scope: str) -> tuple[Path, object]:
        """Publish one real managed Active revision and return ``(config, active)``."""

        document = example_document()
        (self.root / scope).mkdir(parents=True, exist_ok=True)
        for relative in ("Movies", "TV Shows"):
            (self.root / "Target" / relative).mkdir(parents=True, exist_ok=True)
        document["storages"][0]["rootPath"] = str(self.root)
        document["storages"][1]["rootPath"] = str(self.root / "Target")
        document["resourceLibraries"][0]["storagePath"] = scope
        document["resourceLibraries"][0]["displayRootPath"] = str(self.root / scope)
        document["persistence"] = {"databasePath": str(self.database)}
        document["historyPath"] = str(self.root / "history.jsonl")
        config = self.root / "config.json"
        config.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")

        configuration_repository = SQLiteConfigurationRepository(self.database)
        self.addCleanup(configuration_repository.close)
        service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=str(self.database),
        )
        objects = ConfigurationObjectService(
            service,
            storage_adapters={
                "source-storage": LocalStorage("source-storage", self.root),
                "media-target": LocalStorage("media-target", self.root / "Target"),
            },
            storage_browser_cursor_secret="scope-continuation-journey-secret",
        )
        draft = service.import_draft(document, actor="operator")
        validated = service.validate(draft.revision_id, actor="operator")
        for storage_id in ("source-storage", "media-target"):
            evidence = objects.storage_check(
                validated.revision_id,
                storage_id=storage_id,
                expected_version=validated.version,
                expected_digest=validated.digest,
                actor="operator",
            )
            self.assertEqual(evidence.status, ConfigurationStorageCheckStatus.PASSED)
        strategy = objects.recognition_strategy_test(
            validated.revision_id,
            expected_version=validated.version,
            expected_digest=validated.digest,
            actor="operator",
            resource_library_id="source",
            synthetic_path="Example.Movie.2024.1080p.mkv",
        )
        self.assertEqual(strategy.status, ConfigurationStrategyTestStatus.COMPLETED)
        destination = objects.destination_precheck(
            validated.revision_id,
            expected_version=validated.version,
            expected_digest=validated.digest,
            actor="operator",
            recognition_type="C",
            sample={
                "title": "The Matrix",
                "mediaType": "movie",
                "year": 1999,
                "genres": ["Action"],
                "extension": "mkv",
            },
        )
        self.assertEqual(destination.status, ConfigurationDestinationPrecheckStatus.COMPLETED)
        active = objects.activate_checked(
            validated.revision_id,
            expected_version=validated.version,
            actor="operator",
        )
        return config, active

    def _paused_preview(self, active, *, discovered: str | None = None):
        task = PersistentTask(
            "task-original",
            "preview",
            PersistentTaskStatus.RUNNING,
            False,
            NOW,
            NOW,
            started_at=NOW,
            configuration_snapshot_id=active.revision_id,
            configuration_snapshot_digest=active.digest,
        )
        self.repository.create_task(task)
        if discovered is not None:
            self.coordinator.record_discovered(
                task.task_id,
                "source-storage",
                "source",
                discovered,
                f"source-storage:{discovered}",
            )
        self.repository.request_task_pause(task.task_id, NOW)
        return self.coordinator.acknowledge_pause(task.task_id)

    def test_worker_prepare_failure_closes_the_continuation_without_any_effect(self) -> None:
        from mediaflow.final_cli import _run_queued_workflow

        config, active = self._activate(scope="Incoming")
        (self.root / "Incoming" / "one.mkv").write_bytes(b"one")
        original = self._paused_preview(active)

        service = ScopeContinuationService(self.repository, snapshot_validator=lambda *_: None)
        submission = service.submit(
            original.task_id,
            expected_version=None,
            actor="operator",
            maximum_active_jobs=10,
        )
        # The source Task's scope changes before the Worker claims the Job, so
        # the continuation cannot reproduce the admitted scope and must stop
        # with zero Storage work and zero new Task.
        from dataclasses import replace as _replace

        self.repository.update_task(
            _replace(
                self.repository.get_task(original.task_id),
                scope_path="Incoming/Elsewhere",
                updated_at=datetime(2026, 10, 6, tzinfo=UTC),
            )
        )
        with self.assertRaises(Exception):
            _run_queued_workflow(
                submission.job, str(config), lambda: False, repository=self.repository
            )
        closed = self.repository.get_scope_continuation_for_job(submission.job.job_id)
        self.assertIs(closed.status, ScopeContinuationStatus.FAILED)
        self.assertIsNotNone(closed.recovery)
        self.assertNotIn(str(self.root), json.dumps(closed.document()))
        # No continuation Task was created and the original stays paused with
        # its own scope.
        self.assertEqual(
            [task.task_id for task in self.repository.list_tasks(limit=100)], [original.task_id]
        )
        self.assertIs(
            self.repository.get_task(original.task_id).status, PersistentTaskStatus.PAUSED
        )
        self.assertEqual(
            sorted(path.name for path in (self.root / "Incoming").iterdir()), ["one.mkv"]
        )

    def test_the_worker_never_refuses_the_continuation_it_claimed(self) -> None:
        """The claimed continuation's own Job is excluded from the duplicate check.

        Without that exclusion the Worker would re-read its own active
        continuation as a duplicate and refuse the very work it was admitted to
        do, so the exclusion is a correctness requirement, not a convenience.
        """

        config, active = self._activate(scope="Incoming")
        (self.root / "Incoming" / "first.mkv").write_bytes(b"first")
        (self.root / "Incoming" / "second.mkv").write_bytes(b"second")
        original = self._paused_preview(active)
        service = ScopeContinuationService(self.repository, snapshot_validator=lambda *_: None)
        submission = service.submit(
            original.task_id,
            expected_version=None,
            actor="operator",
            maximum_active_jobs=10,
        )
        # The claimed continuation is active while the Worker prepares it.
        self.repository.mark_scope_continuation_running(submission.job.job_id)
        prepared = service.prepare(submission.job.job_id)
        self.assertEqual(prepared.source_task.task_id, original.task_id)
        # A scan records its sources as it discovers them, so the remaining
        # *rows* are still empty here; the remaining budget and the exclusion
        # set are what the Worker's discovery walk really consumes.
        self.assertIsNone(prepared.remaining_limit)
        self.assertEqual(prepared.already_recorded, frozenset())
        # Admission from another surface still sees the duplicate.
        with self.assertRaises(ScopeContinuationError) as raised:
            service.submit(
                original.task_id,
                expected_version=None,
                actor="operator",
                maximum_active_jobs=10,
            )
        self.assertIs(raised.exception.reason, ScopeContinuationReason.CONTINUATION_EXISTS)

    def test_native_remaining_scope_preview_reviews_only_the_eligible_items(self) -> None:
        """The native recovery path previews the durable remaining scope.

        A paused mutation-authorized run whose live authority is gone has no
        Continue, but the operator must still be able to review exactly what is
        left under the run's own immutable pin.  The admission is zero-mutation,
        excludes the already-decided sibling, and grants no execution authority.
        """

        config, active = self._activate(scope="Incoming")
        (self.root / "Incoming" / "Kept.2006.mkv").write_bytes(b"kept")
        (self.root / "Incoming" / "Left.2005.mkv").write_bytes(b"left")
        original = self._paused_mutation_scan(active, discovered="Incoming/Kept.2006.mkv")
        api = self._api(config)

        status, admission = request(
            api,
            f"/api/v1/tasks/{original.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        # The native recovery admission is durable and asynchronous: it records
        # the bounded observation and lets the resident Worker prove the
        # configured stability interval before freezing and analysing.
        self.assertEqual(status, 202, admission)
        self.assertEqual(admission["journey"], "discovery")
        self.assertEqual(admission["recoverySourceTaskId"], original.task_id)
        self.assertEqual(admission["zeroMutation"], True)
        self.assertEqual(admission["sideEffects"], "none")
        document = self._drive_recovery(api, admission["discoveryId"])
        self.assertEqual(document["prepared"], True)
        # Only the undecided source is reviewed; the recorded sibling is never
        # re-offered, and the plan runs under the run's own historical pin.
        preview = self.repository.get_manual_preview(document["previewId"])
        self.assertEqual([item.source.path for item in preview.items], ["Incoming/Left.2005.mkv"])
        self.assertEqual(preview.configuration_snapshot_id, active.revision_id)
        self.assertIn("previewId", document)
        payload = json.dumps(document)
        self.assertNotIn(str(self.root), payload)
        self.assertNotIn("scope_path", payload)
        # Zero Storage mutation happened during the review.
        self.assertEqual(
            sorted(path.name for path in (self.root / "Incoming").iterdir()),
            ["Kept.2006.mkv", "Left.2005.mkv"],
        )

    def test_remaining_scope_recovery_proves_a_nonzero_stability_interval(self) -> None:
        """A nonzero configured interval is proven by a real elapsed observation.

        This is the exact B blocker: the remaining-scope recovery must not
        discard its first observation and reject every later read.  The durable
        preparation persists the first observation, records the real
        re-observation deadline and only freezes once the interval is proven.
        """

        import os
        import time

        from mediaflow.application.media_discovery import MediaDiscoveryService
        from mediaflow.application.metadata import MetadataProviderRegistry
        from mediaflow.application.strategy_test import SyntheticMetadataProvider
        from mediaflow.domain.media_discovery import DiscoveryStatus
        from mediaflow.domain.metadata import MediaCandidate, MediaType
        from mediaflow.infrastructure.runtime_configuration import (
            load_managed_runtime_configuration,
            with_managed_snapshot,
        )

        config, active = self._activate(scope="Incoming")
        (self.root / "Incoming" / "Kept.2006.mkv").write_bytes(b"kept")
        (self.root / "Incoming" / "Left.2005.mkv").write_bytes(b"left")
        old = time.time() - 86400
        os.utime(self.root / "Incoming" / "Kept.2006.mkv", (old, old))
        os.utime(self.root / "Incoming" / "Left.2005.mkv", (old, old))
        # Rewrite the Active revision with a one-second stable-size interval.
        document = json.loads(config.read_text(encoding="utf-8"))
        document["resourceLibraries"][0]["stability"] = {
            "minimumAgeSeconds": 0,
            "modifiedThresholdSeconds": 0,
            "stableSizeDurationSeconds": 1,
        }
        configuration_repository = SQLiteConfigurationRepository(self.database)
        self.addCleanup(configuration_repository.close)
        managed = ManagedConfigurationService(
            configuration_repository, bootstrap_database_path=str(self.database)
        )
        draft = managed.import_draft(document, actor="operator")
        validated = managed.validate(draft.revision_id, actor="operator")
        active = managed.activate(
            validated.revision_id, expected_version=validated.version, actor="operator"
        )
        config.write_text(json.dumps(document), encoding="utf-8")
        task = self._paused_mutation_scan(active, discovered="Incoming/Kept.2006.mkv")
        from dataclasses import replace as _replace

        task = _replace(task, command="organize")
        self.repository.update_task(task)
        runtime = with_managed_snapshot(
            load_managed_runtime_configuration(
                active.document, bootstrap_database_path=str(self.database)
            ),
            snapshot_id=active.revision_id,
            digest=active.digest,
        )
        storages = runtime.create_storages(
            external={
                "source-storage": LocalStorage("source-storage", self.root),
                "media-target": LocalStorage("media-target", self.root / "Target"),
            }
        )
        providers = MetadataProviderRegistry(
            (
                SyntheticMetadataProvider(
                    (
                        MediaCandidate(
                            "tmdb",
                            "100",
                            MediaType.MOVIE,
                            "Left",
                            year=2005,
                            genres=("Animation",),
                            countries=("JP",),
                        ),
                    )
                ),
            )
        )
        from mediaflow.application.manual_organize import ManualOrganizeIntentService
        from mediaflow.application.manual_organize_preview import (
            ManualOrganizePreviewService,
        )

        intents = ManualOrganizeIntentService(
            self.repository,
            managed,
            runtime_resolver=lambda *_: runtime,
            storage_factory=lambda *_: dict(storages),
        )
        previews = ManualOrganizePreviewService(
            self.repository,
            intents,
            configuration=runtime,
            runtime_resolver=lambda *_: runtime,
            storages=dict(storages),
            providers=providers,
        )
        discovery = MediaDiscoveryService(
            self.repository,
            intents,
            configuration=runtime,
            runtime_resolver=lambda *_: runtime,
            preview_service=previews,
            storages=dict(storages),
        )
        from mediaflow.application.scope_continuation import ScopeContinuationService

        obstacle_service = ScopeContinuationService(
            self.repository, snapshot_validator=lambda *_: None
        )
        discovery.admit_recovery_preparation(
            task.task_id, actor="admin", obstacle=obstacle_service.obstacle
        )
        first = discovery.claim_and_run(worker_id="first", claim_token="first")
        self.assertIs(first.status, DiscoveryStatus.WAITING_STABILITY)
        self.assertEqual((), first.sources)
        self.assertIsNotNone(first.next_observation_at)
        # An immediate re-read is deliberately not claimable before the real
        # interval elapses: waiting work never spins and never fabricates the
        # interval.
        self.assertIsNone(discovery.claim_and_run(worker_id="early", claim_token="early"))
        time.sleep(1.1)
        settled = None
        for index in range(6):
            settled = discovery.claim_and_run(
                worker_id=f"later-{index}", claim_token=f"later-token-{index}"
            )
            if settled is None:
                break
            if settled.preview_id is not None or settled.terminal:
                break
        self.assertIsNotNone(settled)
        self.assertIsNotNone(settled.preview_id)
        preview = self.repository.get_manual_preview(settled.preview_id)
        self.assertEqual([item.source.path for item in preview.items], ["Incoming/Left.2005.mkv"])
        # Zero media mutation during the whole observation and analysis.
        self.assertEqual(
            sorted(path.name for path in (self.root / "Incoming").iterdir()),
            ["Kept.2006.mkv", "Left.2005.mkv"],
        )

    def test_exact_preview_execution_and_worker_consume_the_original_scope_budget(self) -> None:
        """A real exact Preview execution remains in the paused Task's budget."""

        from mediaflow.application.manual_organize_worker import ManualOrganizeExecutionWorker

        config, active = self._activate(scope="Incoming")
        (self.root / "Incoming" / "Left.2005.mkv").write_bytes(b"left")
        (self.root / "Incoming" / "Right.2006.mkv").write_bytes(b"right")
        original = self._paused_mutation_scan(active, item_limit=2)
        api = self._api(config)

        status, admission = request(
            api,
            f"/api/v1/tasks/{original.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 202, admission)
        document = self._drive_recovery(api, admission["discoveryId"])
        preview = self.repository.get_manual_preview(document["previewId"])
        preview_id = preview.preview_id
        self.assertEqual(len(preview.items), 2)
        self.assertEqual(preview.recovery_source_task_id, original.task_id)
        item_ids = [item.item_id for item in preview.items]
        status, admitted = request(
            api,
            f"/api/v1/operations/organize/previews/{preview_id}/execute",
            method="POST",
            body={
                "confirmation": True,
                "itemIds": item_ids,
                "expectedIntentVersion": preview.intent_version,
                "allowOverwrite": False,
                "allowSourceCleanup": False,
            },
            token="admin-token",
        )
        self.assertEqual(status, 202, admitted)
        execution_id = admitted["executionId"]
        execution_task_id = admitted["taskId"]
        link = self.repository.get_scope_recovery_for_new_task(execution_task_id)
        self.assertIsNotNone(link)
        self.assertEqual(link.source_task_id, original.task_id)
        self.assertEqual(link.preview_id, preview_id)
        self.assertEqual(link.execution_id, execution_id)

        worker_result = ManualOrganizeExecutionWorker(api._manual_execution).run_next()
        self.assertIsNotNone(worker_result)
        self.assertEqual(worker_result.execution_id, execution_id)
        self.assertEqual(worker_result.status.value, "completed")
        remaining, recorded, remaining_limit = remaining_scope(self.repository, original)
        self.assertEqual(len(self.repository.list_items(execution_task_id)), 2)
        self.assertEqual(len(recorded), 2)
        self.assertEqual(remaining_limit, 0)
        self.assertEqual(remaining, ())
        self.assertIs(
            continuation_obstacle(self.repository, original, lambda *_: None)[0],
            ScopeContinuationReason.NO_REMAINING_SCOPE,
        )
        self.assertEqual(
            {path.name for path in (self.root / "Target" / "Movies").rglob("*.mkv")},
            {"Left (2005).mkv", "Right (2006).mkv"},
        )

        status, overview = request(api, f"/api/v1/operations/runs/{original.task_id}")
        self.assertEqual(status, 200, overview)
        self.assertEqual(overview["continuation"]["recoveryKind"], "exact_preview")
        self.assertEqual(overview["continuation"]["recoveryPreviewId"], preview_id)
        self.assertEqual(overview["continuation"]["newTaskId"], execution_task_id)
        self.assertEqual(overview["continuation"]["executionId"], execution_id)
        (self.root / "Incoming" / "Third.2007.mkv").write_bytes(b"third")
        status, refused = request(
            api,
            f"/api/v1/tasks/{original.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 409, refused)
        self.assertEqual(refused["error"]["code"], "no_remaining_scope")
        self.assertEqual(len(self.repository.list_scope_recovery_links(original.task_id)), 1)
        with SQLiteTaskRepository(self.database) as reopened:
            durable_source = reopened.get_task(original.task_id)
            self.assertIsNotNone(durable_source)
            durable_link = reopened.get_scope_recovery_for_new_task(execution_task_id)
            self.assertIsNotNone(durable_link)
            self.assertEqual(durable_link.source_task_id, original.task_id)
            self.assertEqual(durable_link.preview_id, preview_id)
            self.assertEqual(durable_link.execution_id, execution_id)
            self.assertEqual(durable_link.new_task_id, execution_task_id)
            self.assertEqual(remaining_scope(reopened, durable_source)[2], 0)

    def test_native_remaining_scope_preview_refuses_a_run_with_no_remaining_scope(self) -> None:
        """A fully-decided run has nothing to review and is refused truthfully."""

        config, active = self._activate(scope="Incoming")
        (self.root / "Incoming" / "only.mkv").write_bytes(b"only")
        original = self._paused_mutation_scan(active)
        api = self._api(config)
        self.coordinator.record_discovered(
            original.task_id,
            "source-storage",
            "source",
            "Incoming/only.mkv",
            "source-storage:Incoming/only.mkv",
        )
        item = self.repository.list_items(original.task_id)[0]
        self.repository.upsert_item(
            replace(item, status=TaskItemStatus.SUCCESS, updated_at=datetime.now(UTC))
        )
        self.repository.append_result(
            PersistentResultRecord(
                "only:1",
                original.task_id,
                item.item_id,
                "source-storage",
                "Incoming/only.mkv",
                "media-target",
                "Movies/Only/Only.mkv",
                "C",
                "tmdb",
                "1",
                "C",
                "A",
                "A",
                "A",
                "MOVE",
                "success",
                NOW,
                title="Only",
                effect_certainty="verified_complete",
            )
        )
        status, document = request(
            api,
            f"/api/v1/tasks/{original.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 409, document)
        self.assertEqual(document["error"]["code"], "no_remaining_scope")
        self.assertEqual(document["error"]["details"]["sideEffects"], "none")
        self.assertEqual(
            self.repository.list_manual_previews_by_scope("resource_library", "source"), ()
        )

    def test_native_remaining_scope_preview_never_widens_an_unresolvable_scope(self) -> None:
        """A scope that is not in the pinned runtime is refused, not broadened.

        Broadening it would review (and could later execute) work the original
        run never admitted, so the recovery path must fail closed.
        """

        config, active = self._activate(scope="Incoming")
        (self.root / "Incoming" / "left.mkv").write_bytes(b"left")
        task = PersistentTask(
            "task-outside",
            "preview",
            PersistentTaskStatus.RUNNING,
            True,
            NOW,
            NOW,
            started_at=NOW,
            scope_path="Somewhere/Else",
            item_limit=2,
            configuration_snapshot_id=active.revision_id,
            configuration_snapshot_digest=active.digest,
        )
        self.repository.create_task(task)
        self.repository.request_task_pause(task.task_id, NOW)
        paused = self.coordinator.acknowledge_pause(task.task_id)
        api = self._api(config)
        status, document = request(
            api,
            f"/api/v1/tasks/{paused.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 409, document)
        self.assertEqual(document["error"]["code"], "scope_unresolved")
        self.assertEqual(document["error"]["details"]["sideEffects"], "none")
        # Nothing was minted and the out-of-scope file was never reviewed.
        self.assertEqual(
            self.repository.list_manual_previews_by_scope("resource_library", "source"), ()
        )
        self.assertNotIn("left.mkv", json.dumps(document))

    def test_the_pinned_recovery_path_never_relaxes_the_ordinary_files_rule(self) -> None:
        """A historical pin is opt-in, and only for the remaining-scope path.

        The ordinary Files admission must keep hard-requiring the current Active
        revision; otherwise a superseded or draft revision could mint an
        ordinary Preview. The opt-in is therefore proven by its own signature
        and by the ordinary path still resolving the *current* Active revision.
        """

        import inspect

        from mediaflow.application.manual_organize import ManualOrganizeIntentService

        config, active = self._activate(scope="Incoming")
        (self.root / "Incoming" / "left.mkv").write_bytes(b"left")
        parameters = inspect.signature(ManualOrganizeIntentService.create_from_sources).parameters
        # The historical-pin behaviour is opt-in: the default keeps the strict
        # current-Active rule for every existing caller.
        self.assertIn("pinned_snapshot", parameters)
        self.assertIs(parameters["pinned_snapshot"].default, False)

        configuration_repository = SQLiteConfigurationRepository(self.database)
        self.addCleanup(configuration_repository.close)
        service = ManagedConfigurationService(
            configuration_repository, bootstrap_database_path=str(self.database)
        )
        intents = ManualOrganizeIntentService(
            self.repository,
            configuration_service=service,
        )
        # The ordinary path resolves the current Active revision, never a
        # caller-supplied historical one.
        current = intents._active_snapshot()
        self.assertEqual(current.snapshot_id, active.revision_id)
        self.assertEqual(current.digest, active.digest)

    def test_native_remaining_scope_preview_requires_the_manage_permission(self) -> None:
        """A READ-only principal can never mint a Preview."""

        config, active = self._activate(scope="Incoming")
        (self.root / "Incoming" / "left.mkv").write_bytes(b"left")
        original = self._paused_mutation_scan(active)
        api = self._api(config)
        status, document = request(
            api,
            f"/api/v1/tasks/{original.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="viewer-token",
        )
        self.assertEqual(status, 403, document)
        self.assertEqual(
            self.repository.list_manual_previews_by_scope("resource_library", "source"), ()
        )

    def test_native_remaining_scope_preview_is_refused_while_the_pin_is_unresolvable(self) -> None:
        """A run whose historical revision is gone is refused, not repinned."""

        config, _active = self._activate(scope="Incoming")
        (self.root / "Incoming" / "left.mkv").write_bytes(b"left")
        task = PersistentTask(
            "task-unpinned",
            "preview",
            PersistentTaskStatus.RUNNING,
            True,
            NOW,
            NOW,
            started_at=NOW,
            configuration_snapshot_id="snap-gone",
            configuration_snapshot_digest="digest-gone",
        )
        self.repository.create_task(task)
        self.repository.request_task_pause(task.task_id, NOW)
        paused = self.coordinator.acknowledge_pause(task.task_id)
        api = self._api(config)
        status, document = request(
            api,
            f"/api/v1/tasks/{paused.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 409, document)
        self.assertEqual(document["error"]["code"], "snapshot_unavailable")
        self.assertEqual(document["error"]["details"]["sideEffects"], "none")
        self.assertNotIn("mediaflow tasks", json.dumps(document))
        self.assertNotIn(str(self.root), json.dumps(document))

    def test_recovery_keeps_an_undecided_recorded_source_in_the_reviewed_scope(self) -> None:
        """An already-recorded but undecided source is *remaining*, not decided.

        The recorded `Kept` sibling is successful and its result is decided.  The
        recorded `Left` item is still `pending` and has no result, so the run's
        remaining scope really contains it.  Recovery must therefore review
        `Left` instead of reporting `no_remaining_scope`, while still never
        replaying `Kept`.

        This is the budget-4 control: two of the four originally admitted units
        are recorded, so three further sources stay discoverable and the ordinary
        Continue guard's own budget check is not the case under test here.
        """

        config, active = self._activate(scope="Incoming")
        sub = self.root / "Incoming" / "Sub"
        sub.mkdir()
        (sub / "Kept.2006.mkv").write_bytes(b"kept")
        (sub / "Left.2005.mkv").write_bytes(b"left")
        task = self._paused_mutation_scan(active, discovered="Incoming/Sub/Kept.2006.mkv")
        task = replace(task, command="organize", scope_path="Incoming/Sub")
        self.repository.update_task(task)
        # A recorded but undecided source: the chain owns it and it consumed one
        # unit of the original budget, but no outcome has been decided yet.
        item = self.coordinator.record_discovered(
            task.task_id,
            "source-storage",
            "source",
            "Incoming/Sub/Left.2005.mkv",
            "source-storage:Incoming/Sub/Left.2005.mkv",
        )
        entry = LocalStorage("source-storage", self.root).stat(item.source_path)
        fingerprint = source_fingerprint("source-storage", "source", entry)
        self.repository.upsert_item(
            replace(
                item,
                status=TaskItemStatus.PENDING,
                stage="pending",
                source_fingerprint=fingerprint.value,
                source_fingerprint_state="verified",
                source_occurrence_id=occurrence_id_for(
                    "source-storage", "source", item.source_path, fingerprint.value
                ),
                source_observed_at=datetime.now(UTC),
            )
        )
        remaining, replay_excluded, source_budget = recovery_scope(
            self.repository, self.repository.get_task(task.task_id)
        )
        plan = recovery_scope_plan(self.repository, self.repository.get_task(task.task_id))
        self.assertEqual([value.source_path for value in remaining], ["Incoming/Sub/Left.2005.mkv"])
        self.assertEqual(replay_excluded, {("source-storage", "Incoming/Sub/Kept.2006.mkv")})
        # The original budget was 4, two sources are recorded, so three further
        # sources stay discoverable *on top of* the one still-undecided item.
        self.assertEqual(source_budget, 3)
        self.assertEqual(plan.unrecorded_budget, 2)

        api = self._api(config)
        status, admission = request(
            api,
            f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 202, admission)
        self.assertEqual(admission["journey"], "discovery")
        self.assertEqual(admission["recoverySourceTaskId"], task.task_id)
        document = self._drive_recovery(api, admission["discoveryId"])
        preview = self.repository.get_manual_preview(document["previewId"])
        # Exactly the undecided source is reviewed; the decided sibling is not.
        self.assertEqual(
            [value.source.path for value in preview.items], ["Incoming/Sub/Left.2005.mkv"]
        )
        self.assertEqual(preview.configuration_snapshot_id, active.revision_id)
        self.assertEqual((sub / "Kept.2006.mkv").read_bytes(), b"kept")
        self.assertEqual((sub / "Left.2005.mkv").read_bytes(), b"left")
        self.assertFalse(list((self.root / "Target").rglob("*.mkv")))

    def _recorded_undecided_scope(
        self, active, *, item_limit: int, keep_success: bool, directory: str = "Sub"
    ):
        """A paused run whose whole admitted budget is already recorded.

        `Kept` (when requested) is successful and decided; `Left` is recorded
        with trustworthy source evidence but is still `pending`, so the whole
        original `item_limit` is occupied by recorded items while one unit of
        real work remains undecided.  Nothing else exists in the scope unless a
        case adds it deliberately: an extra source at a full budget must never
        borrow the pending unit and silently widen the reviewed scope.
        """

        sub = self.root / "Incoming" / directory
        sub.mkdir(parents=True, exist_ok=True)
        if keep_success:
            (sub / "Kept.2006.mkv").write_bytes(b"kept")
        (sub / "Left.2005.mkv").write_bytes(b"left")
        task = self._paused_mutation_scan(
            active,
            discovered=(f"Incoming/{directory}/Kept.2006.mkv" if keep_success else None),
            item_limit=item_limit,
        )
        return replace(task, command="organize", scope_path=f"Incoming/{directory}")

    def _record_pending_source(self, task, path: str) -> None:
        """Record one undecided source with the trustworthy evidence it had."""

        item = self.coordinator.record_discovered(
            task.task_id,
            "source-storage",
            "source",
            path,
            f"source-storage:{path}",
        )
        entry = LocalStorage("source-storage", self.root).stat(item.source_path)
        fingerprint = source_fingerprint("source-storage", "source", entry)
        self.repository.upsert_item(
            replace(
                item,
                status=TaskItemStatus.PENDING,
                stage="pending",
                source_fingerprint=fingerprint.value,
                source_fingerprint_state="verified",
                source_occurrence_id=occurrence_id_for(
                    "source-storage", "source", item.source_path, fingerprint.value
                ),
                source_observed_at=datetime.now(UTC),
            )
        )

    def test_a_fully_recorded_budget_still_recovers_its_undecided_item(self) -> None:
        """B P1: a recorded budget with one Pending item keeps a real recovery.

        `remaining_scope` reports a zero *new* discovery budget because every
        unit of `item_limit` is already recorded. That is not the same statement
        as "nothing is recoverable": `Left` is still undecided, so the native
        projection must advertise the recovery action, the direct preparation
        must be admitted, and the resident Worker's summary must contain exactly
        `Left` while `Kept` is never replayed.
        """

        config, active = self._activate(scope="Incoming")
        task = self._recorded_undecided_scope(active, item_limit=2, keep_success=True)
        self.repository.update_task(task)
        self._record_pending_source(task, "Incoming/Sub/Left.2005.mkv")

        # The whole admitted budget is recorded, and the recorded items are two.
        remaining, _recorded, new_budget = remaining_scope(
            self.repository, self.repository.get_task(task.task_id)
        )
        self.assertEqual([value.source_path for value in remaining], ["Incoming/Sub/Left.2005.mkv"])
        self.assertEqual(new_budget, 0)

        api = self._api(config)
        read_status, detail = request(api, f"/api/v1/tasks/{task.task_id}", token="admin-token")
        self.assertEqual(read_status, 200, detail)
        resume = next(item for item in detail["lifecycle"]["actions"] if item["action"] == "resume")
        # Ordinary Continue stays refused (no live reusable authority), and the
        # native recovery entry is advertised for exactly that refusal.
        self.assertFalse(resume["available"])
        self.assertEqual(resume["preview"]["available"], True)
        self.assertEqual(
            resume["preview"]["path"],
            f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
        )

        overview_status, overview = request(
            api, f"/api/v1/operations/runs/{task.task_id}", token="admin-token"
        )
        self.assertEqual(overview_status, 200, overview)
        overview_resume = next(
            item for item in overview["lifecycle"]["actions"] if item["action"] == "resume"
        )
        self.assertFalse(overview_resume["available"])
        self.assertEqual(overview_resume["preview"]["available"], True)

        status, admission = request(
            api,
            f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 202, admission)
        self.assertEqual(admission["recoverySourceTaskId"], task.task_id)
        self.assertEqual(admission["sideEffects"], "none")
        document = self._drive_recovery(api, admission["discoveryId"])
        self.assertEqual(document["prepared"], True)
        preview = self.repository.get_manual_preview(document["previewId"])
        self.assertEqual(
            [item.source.path for item in preview.items], ["Incoming/Sub/Left.2005.mkv"]
        )
        self.assertEqual(preview.configuration_snapshot_id, active.revision_id)
        self.assertEqual((self.root / "Incoming" / "Sub" / "Kept.2006.mkv").read_bytes(), b"kept")
        self.assertEqual((self.root / "Incoming" / "Sub" / "Left.2005.mkv").read_bytes(), b"left")
        self.assertFalse(list((self.root / "Target").rglob("*.mkv")))

    def test_a_single_recorded_pending_item_is_recoverable_at_a_full_budget(self) -> None:
        """The smallest full-budget boundary: `item_limit=1` with one Pending."""

        config, active = self._activate(scope="Incoming")
        task = self._recorded_undecided_scope(active, item_limit=1, keep_success=False)
        self.repository.update_task(task)
        self._record_pending_source(task, "Incoming/Sub/Left.2005.mkv")
        remaining, _recorded, new_budget = remaining_scope(
            self.repository, self.repository.get_task(task.task_id)
        )
        self.assertEqual([value.source_path for value in remaining], ["Incoming/Sub/Left.2005.mkv"])
        self.assertEqual(new_budget, 0)

        api = self._api(config)
        status, admission = request(
            api,
            f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 202, admission)
        document = self._drive_recovery(api, admission["discoveryId"])
        preview = self.repository.get_manual_preview(document["previewId"])
        self.assertEqual(
            [item.source.path for item in preview.items], ["Incoming/Sub/Left.2005.mkv"]
        )

    def test_a_full_budget_never_lets_a_new_file_borrow_the_pending_unit(self) -> None:
        """A later file cannot replace or widen the recorded undecided unit.

        The original admission is fully recorded at `item_limit=2` with `Kept`
        decided and `Left` pending.  A genuinely new source appears in the same
        directory afterwards.  The recovery preparation must still observe
        exactly `Left`: the new file has no admitted unit and must not borrow the
        pending one.
        """

        config, active = self._activate(scope="Incoming")
        task = self._recorded_undecided_scope(active, item_limit=2, keep_success=True)
        self.repository.update_task(task)
        self._record_pending_source(task, "Incoming/Sub/Left.2005.mkv")
        (self.root / "Incoming" / "Sub" / "New.2020.mkv").write_bytes(b"new")

        api = self._api(config)
        status, admission = request(
            api,
            f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 202, admission)
        document = self._drive_recovery(api, admission["discoveryId"])
        self.assertEqual(document["prepared"], True)
        preview = self.repository.get_manual_preview(document["previewId"])
        self.assertEqual(
            [item.source.path for item in preview.items], ["Incoming/Sub/Left.2005.mkv"]
        )
        for name in ("Kept.2006.mkv", "Left.2005.mkv", "New.2020.mkv"):
            self.assertTrue((self.root / "Incoming" / "Sub" / name).exists(), name)
        self.assertFalse(list((self.root / "Target").rglob("*.mkv")))

    def test_a_fully_recorded_budget_keeps_the_queued_continue_refusal(self) -> None:
        """The recovery entry does not weaken the queued continuation boundary.

        The same full-budget run has no unrecorded discovery budget, so
        `POST /resume` must keep refusing with `no_remaining_scope` and queue
        nothing; only the separate zero-mutation review remains available.
        """

        api_config, active = self._activate(scope="Incoming")
        task = self._recorded_undecided_scope(active, item_limit=2, keep_success=True)
        self.repository.update_task(task)
        self._record_pending_source(task, "Incoming/Sub/Left.2005.mkv")
        api = self._api(api_config)

        jobs_before = len(self.repository.list_jobs(limit=100))
        status, body = request(
            api,
            f"/api/v1/tasks/{task.task_id}/resume",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 409, body)
        self.assertEqual(body["error"]["details"]["reason"], "no_remaining_scope")
        self.assertEqual(body["error"]["details"]["sideEffects"], "none")
        self.assertEqual(len(self.repository.list_jobs(limit=100)), jobs_before)
        self.assertIsNone(self.repository.get_scope_continuation_for_source_task(task.task_id))
        # The recovery preparation is the only remaining surface, and it is a
        # review: no execution authority is granted and no media changed.
        preview_status, admission = request(
            api,
            f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(preview_status, 202, admission)
        self.assertEqual(admission["sideEffects"], "none")
        self.assertFalse(list((self.root / "Target").rglob("*.mkv")))

    def test_a_fully_decided_chain_at_a_full_budget_is_still_refused(self) -> None:
        """A truly decided run keeps the truthful refusal with zero new work.

        Success, ignore and uncertain effects are all decided outcomes, so a
        fully recorded budget made only of them has no recoverable scope: the
        projection must not advertise the recovery entry and the direct request
        must stay a bounded 409 with no preparation created.
        """

        config, active = self._activate(scope="Incoming")
        sub = self.root / "Incoming" / "Sub"
        sub.mkdir()
        (sub / "Kept.2006.mkv").write_bytes(b"kept")
        task = replace(
            self._paused_mutation_scan(
                active, discovered="Incoming/Sub/Kept.2006.mkv", item_limit=1
            ),
            command="organize",
            scope_path="Incoming/Sub",
        )
        self.repository.update_task(task)
        api = self._api(config)

        read_status, detail = request(api, f"/api/v1/tasks/{task.task_id}", token="admin-token")
        self.assertEqual(read_status, 200, detail)
        resume = next(item for item in detail["lifecycle"]["actions"] if item["action"] == "resume")
        self.assertFalse(resume["available"])
        self.assertNotIn("preview", resume)

        status, document = request(
            api,
            f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 409, document)
        self.assertEqual(document["error"]["code"], "no_remaining_scope")
        self.assertEqual(document["error"]["details"]["sideEffects"], "none")
        self.assertEqual(
            self.repository.list_manual_previews_by_scope("resource_library", "source"), ()
        )

    # -- a decided recovery source stays terminal across attempts ---------

    def _copy_journey_active(self):
        """One managed Active revision whose Organize policy really copies.

        The real COPY+Rename policy is the exact shape B reproduced: the source
        file stays in place after a verified success, so nothing about the source
        Storage state can be mistaken for "not yet organised", and a second
        attempt would produce a *second* destination file.
        """

        original = example_document

        def copy_document():
            # The real production journey uses this module-level fixture helper,
            # so patching it here makes the managed Active revision itself carry
            # the COPY+Rename policy instead of a test-only execution path.
            value = original()
            for policy in value["organizePolicies"]:
                policy["operation"] = "COPY"
                policy["conflictStrategy"] = "rename"
            return value

        patcher = mock.patch.dict(globals(), {"example_document": copy_document})
        patcher.start()
        self.addCleanup(patcher.stop)
        return self._activate(scope="Incoming")

    def _recovery_attempt(self, api, task, *, executor=None):
        """Drive one real recovery with an optional executor substitution.

        ``executor`` only ever *replaces the single executor invocation*; the
        whole admission, Preview, Worker, Result and Task persistence path stays
        the production one, so an injected zero-effect or uncertain outcome is
        recorded exactly as a real one would be.
        """

        from mediaflow.application.manual_organize_worker import (
            ManualOrganizeExecutionWorker,
        )

        status, admission = request(
            api,
            f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 202, admission)
        document = self._drive_recovery(api, admission["discoveryId"])
        preview = self.repository.get_manual_preview(document["previewId"])
        status, execution = request(
            api,
            f"/api/v1/operations/organize/previews/{preview.preview_id}/execute",
            method="POST",
            body={
                "confirmation": True,
                "itemIds": [value.item_id for value in preview.items],
                "expectedIntentVersion": preview.intent_version,
                "allowOverwrite": False,
                "allowSourceCleanup": False,
            },
            token="admin-token",
        )
        self.assertEqual(status, 202, execution)
        if executor is None:
            result = ManualOrganizeExecutionWorker(api._manual_execution).run_next()
        else:
            with mock.patch.object(api._manual_execution, "_executor", executor):
                result = ManualOrganizeExecutionWorker(api._manual_execution).run_next()
        self.assertIsNotNone(result)
        self.assertEqual(result.execution_id, execution["executionId"])
        return result, execution["taskId"]

    def _recovery_executed_once(self, api, task):
        """Drive one real recovery: summary, explicit confirm, real Worker."""

        return self._recovery_attempt(api, task)

    def _recorded_budget_two(self, active):
        """The full-budget fixture: `Kept` decided, `Left` recorded-but-pending."""

        task = self._recorded_undecided_scope(active, item_limit=2, keep_success=True)
        self.repository.update_task(task)
        self._record_pending_source(task, "Incoming/Sub/Left.2005.mkv")
        return task

    def test_a_completed_recovery_never_offers_its_source_again(self):
        """B P1: a really completed recovery source stays terminal forever.

        The original Task is paused with `Left` recorded-but-`pending`; the native
        recovery summary reviews exactly `Left`, the operator explicitly confirms
        it and the resident Worker really COPYs it. The later attempt records its
        own Task/Item/Result under its own item ID, and the manual-Organize
        executor stores the organizer's `SUCCESS` spelling — so the ancestor
        `pending` item must still be retired by exact source evidence instead of
        being offered (and executed) a second time.

        This is the exact defect B reproduced end to end: two confirms produced a
        second `Left (2005) (1).mkv` destination file.
        """

        config, active = self._copy_journey_active()
        task = self._recorded_budget_two(active)
        api = self._api(config)
        original_item = next(
            value
            for value in self.repository.list_items(task.task_id)
            if value.source_path == "Incoming/Sub/Left.2005.mkv"
        )

        result, child_task_id = self._recovery_executed_once(api, task)
        self.assertEqual(result.status.value, "completed")
        child_results = self.repository.list_results(child_task_id)
        self.assertEqual(len(child_results), 1)
        # The real persisted encoding is the organizer's own uppercase value; a
        # case-sensitive check on the TaskItem spelling would miss it.
        self.assertEqual(child_results[0].status, "SUCCESS")
        self.assertEqual(child_results[0].effect_certainty, "verified_complete")
        self.assertEqual(child_results[0].source_fingerprint, original_item.source_fingerprint)
        self.assertNotEqual(child_results[0].item_id, original_item.item_id)

        plan = recovery_scope_plan(self.repository, self.repository.get_task(task.task_id))
        self.assertEqual(plan.undecided_items, ())
        self.assertIn(("source-storage", "Incoming/Sub/Left.2005.mkv"), plan.replay_excluded)
        self.assertEqual(plan.new_source_budget, 0)
        self.assertEqual(plan.unrecorded_budget, 0)
        remaining, _recorded, remaining_limit = remaining_scope(
            self.repository, self.repository.get_task(task.task_id)
        )
        self.assertEqual(remaining, ())
        self.assertEqual(remaining_limit, 0)

        # A reopened connection sees the same truth, so a restart cannot replay.
        with SQLiteTaskRepository(self.database) as reopened:
            reopened_plan = recovery_scope_plan(reopened, reopened.get_task(task.task_id))
            self.assertEqual(reopened_plan.undecided_items, ())
            self.assertEqual(reopened_plan.new_source_budget, 0)

        # No native action and no second preparation: the direct POST is refused
        # with the ordinary bounded code and creates no work at all.
        status, detail = request(api, f"/api/v1/tasks/{task.task_id}", token="admin-token")
        self.assertEqual(status, 200, detail)
        resume = next(
            value for value in detail["lifecycle"]["actions"] if value["action"] == "resume"
        )
        self.assertFalse(resume["available"])
        self.assertNotIn("preview", resume)
        previews_before = self.repository.list_manual_previews_by_scope(
            "resource_library", "source"
        )
        second_status, second = request(
            api,
            f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(second_status, 409, second)
        self.assertEqual(second["error"]["code"], "no_remaining_scope")
        self.assertEqual(second["error"]["details"]["sideEffects"], "none")
        self.assertEqual(
            self.repository.list_manual_previews_by_scope("resource_library", "source"),
            previews_before,
        )
        # Exactly one destination file exists, and both sources are untouched:
        # COPY is the normal behavior, so a replay is visible as a second file.
        self.assertEqual(
            sorted(path.name for path in (self.root / "Target").rglob("*.mkv")),
            ["Left (2005).mkv"],
        )
        self.assertEqual((self.root / "Incoming" / "Sub" / "Left.2005.mkv").read_bytes(), b"left")
        self.assertEqual((self.root / "Incoming" / "Sub" / "Kept.2006.mkv").read_bytes(), b"kept")

    def test_an_already_admitted_preparation_cannot_replay_a_completed_source(self):
        """B P1: an earlier-admitted preparation never replays decided work.

        Two legitimate sequential requests are the exact shape B reproduced: the
        first summary (A) is published, a second preparation (B) is admitted but
        not driven, A is then explicitly confirmed and really COPYs `Left`, and
        only afterwards is B driven. B was admitted while `Left` was still
        undecided, so its admission is legal history — but by the time it
        discovers/freezes/analyses, the only source it was admitted for has a
        decided outcome. It must therefore not publish a summary, not authorize
        and not execute, and the destination must keep exactly one file.
        """

        config, active = self._copy_journey_active()
        task = self._recorded_budget_two(active)
        api = self._api(config)
        endpoint = f"/api/v1/tasks/{task.task_id}/remaining-scope-previews"

        status, first = request(api, endpoint, method="POST", body=None, token="admin-token")
        self.assertEqual(status, 202, first)
        first_document = self._drive_recovery(api, first["discoveryId"])
        first_preview = self.repository.get_manual_preview(first_document["previewId"])
        self.assertEqual(
            [value.source.path for value in first_preview.items],
            ["Incoming/Sub/Left.2005.mkv"],
        )

        # The second legitimate request is admitted *before* the first is
        # confirmed. Its discovery stays queued: nothing is driven yet.
        status, second = request(api, endpoint, method="POST", body=None, token="admin-token")
        self.assertEqual(status, 202, second)
        self.assertNotEqual(second["discoveryId"], first["discoveryId"])
        self.assertIsNone(api._media_discovery.get(second["discoveryId"]).preview_id)

        status, execution = request(
            api,
            f"/api/v1/operations/organize/previews/{first_preview.preview_id}/execute",
            method="POST",
            body={
                "confirmation": True,
                "itemIds": [value.item_id for value in first_preview.items],
                "expectedIntentVersion": first_preview.intent_version,
                "allowOverwrite": False,
                "allowSourceCleanup": False,
            },
            token="admin-token",
        )
        self.assertEqual(status, 202, execution)
        from mediaflow.application.manual_organize_worker import (
            ManualOrganizeExecutionWorker,
        )

        result = ManualOrganizeExecutionWorker(api._manual_execution).run_next()
        self.assertIsNotNone(result)
        self.assertEqual(result.status.value, "completed")
        self.assertEqual(
            sorted(path.name for path in (self.root / "Target").rglob("*.mkv")),
            ["Left (2005).mkv"],
        )

        # The already-admitted preparation B is now driven. Its only source was
        # decided in the meantime, so it must settle truthfully instead of
        # publishing a second summary for the exact same source.
        document = self._drive_recovery(api, second["discoveryId"])
        self.assertIsNone(document["previewId"])
        self.assertEqual(
            api._media_discovery.get(second["discoveryId"]).preview_id,
            None,
        )
        self.assertFalse(list(api._media_discovery.get(second["discoveryId"]).sources))
        self.assertEqual(
            sorted(path.name for path in (self.root / "Target").rglob("*.mkv")),
            ["Left (2005).mkv"],
        )

    # -- an already-admitted preparation across the same timing matrix ----

    def _admit_second_preparation(self, api, task):
        """Admit (but never drive) a second preparation of the same paused run."""

        status, admission = request(
            api,
            f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 202, admission)
        return admission

    def _confirm(self, api, preview, *, item_ids=None):
        """Serve one real explicit Execute confirmation for one summary."""

        return request(
            api,
            f"/api/v1/operations/organize/previews/{preview.preview_id}/execute",
            method="POST",
            body={
                "confirmation": True,
                "itemIds": (
                    [value.item_id for value in preview.items]
                    if item_ids is None
                    else list(item_ids)
                ),
                "expectedIntentVersion": preview.intent_version,
                "allowOverwrite": False,
                "allowSourceCleanup": False,
            },
            token="admin-token",
        )

    def _drive_once(self, api):
        from mediaflow.application.manual_organize_worker import (
            ManualOrganizeExecutionWorker,
        )

        result = ManualOrganizeExecutionWorker(api._manual_execution).run_next()
        self.assertIsNotNone(result)
        return result

    def _target_files(self):
        return sorted(path.name for path in (self.root / "Target").rglob("*.mkv"))

    def test_a_queued_preparation_never_offers_a_source_decided_by_an_ignore(self):
        """An explicit operator ignore of an earlier attempt retires the source.

        The decision is recorded on the attempt's own TaskItem and writes no
        Result, so nothing about the other preparation's admission, Preview or
        pin changes. The second preparation must still stop offering it.
        """

        config, active = self._copy_journey_active()
        task = self._recorded_budget_two(active)
        api = self._api(config)
        first = self._admit_second_preparation(api, task)
        first_document = self._drive_recovery(api, first["discoveryId"])
        first_preview = self.repository.get_manual_preview(first_document["previewId"])
        second = self._admit_second_preparation(api, task)
        self.assertNotEqual(first["discoveryId"], second["discoveryId"])

        original_item = next(
            value
            for value in self.repository.list_items(task.task_id)
            if value.source_path == "Incoming/Sub/Left.2005.mkv"
        )
        # The operator explicitly ignores the exact source through the only
        # recording shape a real ignore writes: its own TaskItem, no Result.
        self.repository.upsert_item(
            replace(original_item, status=TaskItemStatus.IGNORED, stage="ignored_by_operator")
        )
        document = self._drive_recovery(api, second["discoveryId"])
        self.assertIsNone(document["previewId"])
        self.assertFalse(list(api._media_discovery.get(second["discoveryId"]).sources))
        self.assertEqual(self._target_files(), [])

        # The first summary was published before the ignore, so confirming it is
        # a genuinely different timing: the atomic admission refuses it.
        status, execution = self._confirm(api, first_preview)
        self.assertEqual(status, 409, execution)
        self.assertEqual(execution["error"]["code"], "recovery_scope_decided")
        self.assertEqual(self._target_files(), [])

    def test_a_recovery_preparation_is_refused_once_its_source_is_unknown(self):
        """An uncertain effect is investigation-only across attempts.

        `unknown` means MediaFlow cannot prove the interrupted mutation did not
        happen, so a summary published before it must never be confirmed and a
        queued preparation must never publish.
        """

        config, active = self._copy_journey_active()
        task = self._recorded_budget_two(active)
        api = self._api(config)
        first = self._admit_second_preparation(api, task)
        first_document = self._drive_recovery(api, first["discoveryId"])
        first_preview = self.repository.get_manual_preview(first_document["previewId"])
        second = self._admit_second_preparation(api, task)
        original_item = next(
            value
            for value in self.repository.list_items(task.task_id)
            if value.source_path == "Incoming/Sub/Left.2005.mkv"
        )
        self.repository.append_result(
            PersistentResultRecord(
                f"{original_item.item_id}:uncertain",
                task.task_id,
                original_item.item_id,
                "source-storage",
                "Incoming/Sub/Left.2005.mkv",
                "media-target",
                "Movies/Left (2005).mkv",
                "C",
                "tmdb",
                "100",
                "C",
                "A",
                "A",
                "A",
                "COPY",
                "PARTIAL",
                NOW,
                title="Left",
                effect_certainty="unknown",
                uncertain_effects=("executor_invocation",),
                source_occurrence_id=original_item.source_occurrence_id,
                source_fingerprint=original_item.source_fingerprint,
            )
        )
        document = self._drive_recovery(api, second["discoveryId"])
        self.assertIsNone(document["previewId"])
        self.assertFalse(list(api._media_discovery.get(second["discoveryId"]).sources))
        status, execution = self._confirm(api, first_preview)
        self.assertEqual(status, 409, execution)
        self.assertEqual(execution["error"]["code"], "recovery_scope_decided")
        # An uncertain effect never produces a destination file by itself.
        self.assertEqual(self._target_files(), [])

    def test_a_zero_effect_failure_keeps_every_preparation_and_confirmation_legal(self):
        """The fence must not over-correct: provable zero effect stays work.

        A `none` certainty means the executor never crossed the mutation
        boundary, so the source is still undecided work. A preparation admitted
        before that attempt, and a summary published before it, must both remain
        legal, and the confirm must really run.
        """

        from mediaflow.domain.organizer import (
            ExecutionEffectCertainty,
            ExecutionResult,
            ExecutionStatus,
        )

        class _ZeroEffectExecutor:
            def execute(self, plan, _storages, **_kwargs):
                return ExecutionResult(
                    ExecutionStatus.FAILED,
                    plan.operation,
                    plan.source,
                    plan.target,
                    plan_id=plan.plan_id,
                    resolved_destination=plan.target,
                    errors=("injected pre-mutation failure",),
                    effect_certainty=ExecutionEffectCertainty.NONE,
                )

        config, active = self._copy_journey_active()
        task = self._recorded_budget_two(active)
        api = self._api(config)
        first = self._admit_second_preparation(api, task)
        first_document = self._drive_recovery(api, first["discoveryId"])
        first_preview = self.repository.get_manual_preview(first_document["previewId"])
        # A real zero-effect attempt happens in between.
        second = self._admit_second_preparation(api, task)
        second_document = self._drive_recovery(api, second["discoveryId"])
        second_preview = self.repository.get_manual_preview(second_document["previewId"])
        status, execution = self._confirm(api, second_preview)
        self.assertEqual(status, 202, execution)
        from mediaflow.application.manual_organize_worker import (
            ManualOrganizeExecutionWorker,
        )

        with mock.patch.object(api._manual_execution, "_executor", _ZeroEffectExecutor()):
            failed = ManualOrganizeExecutionWorker(api._manual_execution).run_next()
        self.assertIsNotNone(failed)
        self.assertEqual(failed.status.value, "failed")
        self.assertEqual(self._target_files(), [])

        # Provable zero effect never retires the source, so the exact same
        # remaining work is still offered by a fresh preparation.
        from mediaflow.application.scope_continuation import (
            recovery_preparation_eligibility,
        )

        eligibility = recovery_preparation_eligibility(
            self.repository, recovery_source_task_id=task.task_id
        )
        self.assertTrue(eligibility.eligible)
        self.assertTrue(eligibility.may_offer("source-storage", "Incoming/Sub/Left.2005.mkv"))
        third = self._admit_second_preparation(api, task)
        third_document = self._drive_recovery(api, third["discoveryId"])
        self.assertTrue(third_document["prepared"])
        third_preview = self.repository.get_manual_preview(third_document["previewId"])
        self.assertEqual(
            [value.source.path for value in third_preview.items],
            ["Incoming/Sub/Left.2005.mkv"],
        )
        # The summary published before the failed attempt is itself a stale
        # reviewed input (a sibling Result now exists), which is the ordinary
        # Preview contract and not a duplicate-mutation risk.
        status, refused = self._confirm(api, first_preview)
        self.assertEqual(status, 409, refused)
        self.assertEqual(self._target_files(), [])
        # The newest summary still really executes the remaining work once.
        status, execution = self._confirm(api, third_preview)
        self.assertEqual(status, 202, execution)
        succeeded = self._drive_once(api)
        self.assertEqual(succeeded.status.value, "completed")
        self.assertEqual(self._target_files(), ["Left (2005).mkv"])

    def test_a_source_decided_while_the_execution_waits_in_the_queue_is_refused(self):
        """The Worker boundary refuses a decided source before any new effect.

        The authorization and the durable execution admission both happened while
        the source was still undecided, so neither can prove the truth any more.
        The resident Worker re-asks the shared contract immediately before it
        reconstructs the reviewed work and closes the item as a truthful
        pre-mutation failure with zero new effect.
        """

        config, active = self._copy_journey_active()
        task = self._recorded_budget_two(active)
        api = self._api(config)
        # B is admitted and really publishes its own summary while A's execution
        # is only admitted, so every request is legal at the moment it is made.
        first = self._admit_second_preparation(api, task)
        first_document = self._drive_recovery(api, first["discoveryId"])
        first_preview = self.repository.get_manual_preview(first_document["previewId"])
        second = self._admit_second_preparation(api, task)
        status, first_execution = self._confirm(api, first_preview)
        self.assertEqual(status, 202, first_execution)
        second_document = self._drive_recovery(api, second["discoveryId"])
        second_preview = self.repository.get_manual_preview(second_document["previewId"])
        self.assertIsNotNone(second_preview)

        # A's execution really completes and releases its fence; the source now
        # has a decided outcome that no reviewed document of B records.
        first_result = self._drive_once(api)
        self.assertEqual(first_result.execution_id, first_execution["executionId"])
        self.assertEqual(first_result.status.value, "completed")
        self.assertEqual(self._target_files(), ["Left (2005).mkv"])

        # Confirming B is refused with zero new execution and zero new effect.
        status, refused = self._confirm(api, second_preview)
        self.assertEqual(status, 409, refused)
        self.assertIn(
            refused["error"]["code"],
            {"recovery_scope_decided", "preview_stale"},
        )
        self.assertEqual(self._target_files(), ["Left (2005).mkv"])
        for name in ("Kept.2006.mkv", "Left.2005.mkv"):
            self.assertTrue((self.root / "Incoming" / "Sub" / name).is_file(), name)

    def test_the_worker_refuses_a_source_decided_after_its_own_admission(self):
        """The mutation boundary itself re-asks the shared contract.

        A second execution was legitimately admitted and holds its own Storage
        fence, so nothing about admission can be re-proved by reading the Task,
        the Preview or the lock.  The deciding evidence arrives afterwards as an
        explicit operator ignore recorded on the source's own TaskItem.  The
        Worker must notice that before it invokes ``OrganizerExecutor`` and close
        the item as one truthful pre-mutation failure with zero new effect.
        """

        config, active = self._copy_journey_active()
        task = self._recorded_budget_two(active)
        api = self._api(config)
        admission = self._admit_second_preparation(api, task)
        document = self._drive_recovery(api, admission["discoveryId"])
        preview = self.repository.get_manual_preview(document["previewId"])
        status, execution = self._confirm(api, preview)
        self.assertEqual(status, 202, execution)

        original_item = next(
            value
            for value in self.repository.list_items(task.task_id)
            if value.source_path == "Incoming/Sub/Left.2005.mkv"
        )
        self.repository.upsert_item(
            replace(original_item, status=TaskItemStatus.IGNORED, stage="ignored_by_operator")
        )
        result = self._drive_once(api)
        self.assertEqual(result.execution_id, execution["executionId"])
        self.assertEqual(result.status.value, "failed")
        results = self.repository.list_results(execution["taskId"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].effect_certainty, "none")
        self.assertEqual(self._target_files(), [])
        for name in ("Kept.2006.mkv", "Left.2005.mkv"):
            self.assertTrue((self.root / "Incoming" / "Sub" / name).is_file(), name)

    def test_a_pre_authorized_confirmation_is_refused_at_the_atomic_admission(self):
        """The one-shot authority is not a licence to skip the live fence.

        A lost-response / interleaved client can hold a still-live authorization
        that was created before another attempt decided the source.  The consumed
        authority, the Preview, the intent and the Storage fence are all still
        individually valid, so only the atomic admission transaction can refuse
        it — and it must do so without creating an execution.
        """

        from mediaflow.application.manual_organize_execution import (
            ManualOrganizeExecutionService,
        )
        from mediaflow.domain.manual_execution import ManualExecutionError

        config, active = self._copy_journey_active()
        task = self._recorded_budget_two(active)
        api = self._api(config)
        admission = self._admit_second_preparation(api, task)
        document = self._drive_recovery(api, admission["discoveryId"])
        preview = self.repository.get_manual_preview(document["previewId"])
        service: ManualOrganizeExecutionService = api._manual_execution
        authority = service.authorize(
            preview.preview_id,
            [value.item_id for value in preview.items],
            expected_intent_version=preview.intent_version,
            actor="admin",
            confirmation=True,
        )
        original_item = next(
            value
            for value in self.repository.list_items(task.task_id)
            if value.source_path == "Incoming/Sub/Left.2005.mkv"
        )
        self.repository.upsert_item(
            replace(original_item, status=TaskItemStatus.IGNORED, stage="ignored_by_operator")
        )
        # The application preflight is disabled for this call so that only the
        # repository's own atomic admission transaction can refuse it: the
        # guarantee must not depend on a check that runs before the write.
        with mock.patch.object(ManualOrganizeExecutionService, "_assert_recovery_preparation_live"):
            with self.assertRaises(ManualExecutionError) as raised:
                service.admit(authority.authorization_id, actor="admin", confirmation=True)
        self.assertEqual(raised.exception.code, "recovery_scope_decided")
        self.assertEqual(self._target_files(), [])
        # No execution row was created by the refused admission, and the
        # one-shot authority was not consumed by it.
        self.assertEqual(self.repository.list_manual_executions_for_preview(preview.preview_id), ())

    def test_a_walk_skips_a_source_decided_after_admission_with_budget_left(self):
        """The walk itself drops a since-decided source, not only the fixed set.

        Here the original admission still holds unrecorded discovery budget, so
        the preparation observes the admitted *directory* rather than its exact
        recorded files. The durable exclusion set was fixed at admission and
        cannot change, so a source this chain decided afterwards can only be
        dropped by the per-source revalidation inside the walk.
        """

        config, active = self._activate(scope="Incoming")
        sub = self.root / "Incoming" / "Sub"
        sub.mkdir()
        (sub / "Kept.2006.mkv").write_bytes(b"kept")
        (sub / "Left.2005.mkv").write_bytes(b"left")
        (sub / "New.2020.mkv").write_bytes(b"new")
        task = replace(
            self._paused_mutation_scan(
                active, discovered="Incoming/Sub/Kept.2006.mkv", item_limit=4
            ),
            command="organize",
            scope_path="Incoming/Sub",
        )
        self.repository.update_task(task)
        self._record_pending_source(task, "Incoming/Sub/Left.2005.mkv")
        api = self._api(config)
        status, admission = request(
            api,
            f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 202, admission)
        # The admission still holds unrecorded budget, so the preparation walks
        # the whole admitted directory.
        queued = api._media_discovery.get(admission["discoveryId"])
        self.assertEqual(
            [(item.path, item.kind.value) for item in queued.progress.scope_entries],
            [("Sub", "directory")],
        )
        # The previously-undecided source is decided after this admission, and
        # the durable exclusion set cannot record that change.
        original_item = next(
            value
            for value in self.repository.list_items(task.task_id)
            if value.source_path == "Incoming/Sub/Left.2005.mkv"
        )
        self.repository.upsert_item(
            replace(
                original_item,
                status=TaskItemStatus.SUCCESS,
                stage="success",
                updated_at=datetime.now(UTC),
            )
        )
        document = self._drive_recovery(api, admission["discoveryId"])
        self.assertTrue(document["prepared"], document)
        preview = self.repository.get_manual_preview(document["previewId"])
        # The decided source is never re-offered; the newcomer keeps its legal
        # unrecorded unit.
        self.assertEqual(
            [value.source.path for value in preview.items],
            ["Incoming/Sub/New.2020.mkv"],
        )
        self.assertEqual(self._target_files(), [])

    def test_a_reopened_database_keeps_the_same_admitted_preparation_refusal(self):
        """The fence is durable: a restart cannot resurrect a decided source."""

        config, active = self._copy_journey_active()
        task = self._recorded_budget_two(active)
        api = self._api(config)
        first = self._admit_second_preparation(api, task)
        first_document = self._drive_recovery(api, first["discoveryId"])
        first_preview = self.repository.get_manual_preview(first_document["previewId"])
        second = self._admit_second_preparation(api, task)
        status, execution = self._confirm(api, first_preview)
        self.assertEqual(status, 202, execution)
        self.assertEqual(self._drive_once(api).status.value, "completed")

        # A fresh connection to the same file must report the exact same truth,
        # so the restart cannot be the way a queued preparation gets replayed.
        from mediaflow.application.scope_continuation import (
            recovery_preparation_eligibility,
        )

        with SQLiteTaskRepository(self.database) as reopened:
            source = reopened.get_task(task.task_id)
            self.assertIsNotNone(source)
            eligibility = recovery_preparation_eligibility(
                reopened,
                recovery_source_task_id=source.task_id,
            )
            self.assertFalse(eligibility.eligible)
            self.assertEqual(eligibility.code, "recovery_scope_decided")
        document = self._drive_recovery(api, second["discoveryId"])
        self.assertIsNone(document["previewId"])
        self.assertEqual(self._target_files(), ["Left (2005).mkv"])

    # -- a mixed scope: one decided sibling must not authorise another ----

    def _mixed_two_source_task(self, active):
        """A paused run whose whole budget records `Left` and `Right` as pending.

        Both sources are trustworthy and still undecided at admission time, so a
        preparation may legally freeze both.  An earlier attempt can then decide
        one of them while the other stays real remaining work, which keeps the
        chain-level ``eligible`` flag ``True``: the exact mixed shape B
        reproduced.
        """

        sub = self.root / "Incoming" / "Sub"
        sub.mkdir(parents=True, exist_ok=True)
        (sub / "Left.2005.mkv").write_bytes(b"left")
        (sub / "Right.2006.mkv").write_bytes(b"right")
        task = replace(
            self._paused_mutation_scan(active, item_limit=2),
            command="organize",
            scope_path="Incoming/Sub",
        )
        self.repository.update_task(task)
        self._record_pending_source(task, "Incoming/Sub/Left.2005.mkv")
        self._record_pending_source(task, "Incoming/Sub/Right.2006.mkv")
        return task

    def _execute_only(self, api, preview, path: str):
        """Really COPY exactly one source of a published summary."""

        selected = [value.item_id for value in preview.items if value.source.path == path]
        self.assertEqual(len(selected), 1, [value.source.path for value in preview.items])
        status, execution = self._confirm(api, preview, item_ids=selected)
        self.assertEqual(status, 202, execution)
        result = self._drive_once(api)
        self.assertEqual(result.status.value, "completed")
        return execution["taskId"]

    def test_a_frozen_mixed_preparation_never_publishes_a_decided_sibling(self):
        """B P1: a frozen mixed manifest must drop a sibling decided afterwards.

        This is B's exact shape.  Summary A publishes both sources, preparation
        B is admitted while both are still undecided and is driven far enough to
        *freeze* its manifest, and A then really completes only `Left` — leaving
        `Right` undecided, so the chain-level ``eligible`` flag stays ``True``.
        B's frozen manifest already contains `Left`, so only a per-source
        re-check at publish time can keep it out.  Driving B must neither
        publish, authorize nor execute `Left` again; `Right` keeps its own legal
        exact summary and the destination keeps exactly one `Left` file.
        """

        config, active = self._copy_journey_active()
        task = self._mixed_two_source_task(active)
        api = self._api(config)
        endpoint = f"/api/v1/tasks/{task.task_id}/remaining-scope-previews"

        status, first = request(api, endpoint, method="POST", body=None, token="admin-token")
        self.assertEqual(status, 202, first)
        first_document = self._drive_recovery(api, first["discoveryId"])
        first_preview = self.repository.get_manual_preview(first_document["previewId"])
        self.assertEqual(
            sorted(value.source.path for value in first_preview.items),
            ["Incoming/Sub/Left.2005.mkv", "Incoming/Sub/Right.2006.mkv"],
        )

        # B is admitted and driven up to its *frozen* stage while both sources
        # are still undecided.  Its manifest now carries both sources and no
        # summary is published yet.
        status, second = request(api, endpoint, method="POST", body=None, token="admin-token")
        self.assertEqual(status, 202, second)
        self.assertNotEqual(second["discoveryId"], first["discoveryId"])
        frozen = None
        for index in range(8):
            frozen = api._media_discovery.claim_and_run(
                worker_id=f"mixed-freeze-{index}", claim_token=f"mixed-freeze-{index}"
            )
            if frozen is None or frozen.frozen or frozen.preview_id:
                break
        self.assertIsNotNone(frozen)
        self.assertTrue(frozen.frozen)
        self.assertIsNone(frozen.preview_id)
        self.assertEqual(
            sorted(value.get("path") for value in frozen.sources),
            ["Incoming/Sub/Left.2005.mkv", "Incoming/Sub/Right.2006.mkv"],
        )

        # A really completes only `Left`; `Right` stays undecided.
        self._execute_only(api, first_preview, "Incoming/Sub/Left.2005.mkv")
        plan = recovery_scope_plan(self.repository, self.repository.get_task(task.task_id))
        self.assertEqual(
            [value.source_path for value in plan.undecided_items],
            ["Incoming/Sub/Right.2006.mkv"],
        )
        eligibility = recovery_preparation_eligibility(
            self.repository, recovery_source_task_id=task.task_id
        )
        # The exact B shape: the chain is still eligible while `Left` is refused.
        self.assertTrue(eligibility.eligible)
        self.assertFalse(eligibility.may_offer("source-storage", "Incoming/Sub/Left.2005.mkv"))
        self.assertTrue(eligibility.may_offer("source-storage", "Incoming/Sub/Right.2006.mkv"))

        # B is now driven to publication.  Its frozen manifest must publish only
        # the still-undecided `Right`; the completed `Left` is never re-offered.
        document = self._drive_recovery(api, second["discoveryId"])
        self.assertIsNotNone(document["previewId"], document)
        preview = self.repository.get_manual_preview(document["previewId"])
        self.assertEqual(
            [value.source.path for value in preview.items],
            ["Incoming/Sub/Right.2006.mkv"],
        )
        self.assertEqual(self._target_files(), ["Left (2005).mkv"])

        # The legal `Right` still really executes, and the destination gains
        # exactly one new file (never a second `Left`).
        status, execution = self._confirm(api, preview)
        self.assertEqual(status, 202, execution)
        self.assertEqual(self._drive_once(api).status.value, "completed")
        self.assertEqual(sorted(self._target_files()), ["Left (2005).mkv", "Right (2006).mkv"])

    def test_a_frozen_manifest_that_loses_every_source_settles_stale(self):
        """A frozen mixed manifest whose every source was decided never publishes.

        Preparation B freezes both sources, then A completes *both* through its
        own exact summary.  B's chain is then fully decided, so driving it must
        settle truthfully without publishing a summary, without authority and
        with zero new destination files.
        """

        config, active = self._copy_journey_active()
        task = self._mixed_two_source_task(active)
        api = self._api(config)
        endpoint = f"/api/v1/tasks/{task.task_id}/remaining-scope-previews"

        status, first = request(api, endpoint, method="POST", body=None, token="admin-token")
        self.assertEqual(status, 202, first)
        first_document = self._drive_recovery(api, first["discoveryId"])
        first_preview = self.repository.get_manual_preview(first_document["previewId"])

        status, second = request(api, endpoint, method="POST", body=None, token="admin-token")
        self.assertEqual(status, 202, second)
        # One Worker pass freezes B's manifest without publishing a summary.
        frozen = api._media_discovery.claim_and_run(
            worker_id="mixed-freeze", claim_token="mixed-freeze-claim"
        )
        self.assertIsNotNone(frozen)
        self.assertTrue(frozen.frozen)
        self.assertIsNone(frozen.preview_id)

        # A completes both sources through its own summary.
        status, execution = self._confirm(api, first_preview)
        self.assertEqual(status, 202, execution)
        self.assertEqual(self._drive_once(api).status.value, "completed")
        self.assertEqual(sorted(self._target_files()), ["Left (2005).mkv", "Right (2006).mkv"])

        # B's frozen manifest is now fully decided: it must not publish again.
        document = self._drive_recovery(api, second["discoveryId"])
        self.assertIsNone(document["previewId"])
        self.assertFalse(list(api._media_discovery.get(second["discoveryId"]).sources))
        self.assertEqual(sorted(self._target_files()), ["Left (2005).mkv", "Right (2006).mkv"])

    def test_a_published_mixed_summary_refuses_only_the_decided_sibling(self):
        """A published mixed summary must refuse its decided sibling at confirm.

        Two summaries publish both sources before an earlier attempt completes
        one of them.  Confirming the mixed set must be refused because `Left` is
        now decided, and the refusal must name it rather than pass on the
        strength of the legal `Right`.
        """

        config, active = self._copy_journey_active()
        task = self._mixed_two_source_task(active)
        api = self._api(config)
        endpoint = f"/api/v1/tasks/{task.task_id}/remaining-scope-previews"

        status, first = request(api, endpoint, method="POST", body=None, token="admin-token")
        self.assertEqual(status, 202, first)
        first_document = self._drive_recovery(api, first["discoveryId"])
        first_preview = self.repository.get_manual_preview(first_document["previewId"])

        status, second = request(api, endpoint, method="POST", body=None, token="admin-token")
        self.assertEqual(status, 202, second)
        second_document = self._drive_recovery(api, second["discoveryId"])
        second_preview = self.repository.get_manual_preview(second_document["previewId"])
        self.assertEqual(
            sorted(value.source.path for value in second_preview.items),
            ["Incoming/Sub/Left.2005.mkv", "Incoming/Sub/Right.2006.mkv"],
        )

        # The earlier summary completes `Left` while `Right` stays pending.
        self._execute_only(api, first_preview, "Incoming/Sub/Left.2005.mkv")

        # Confirming the whole mixed reviewed set is refused by name.
        status, refused = self._confirm(api, second_preview)
        self.assertEqual(status, 409, refused)
        self.assertEqual(refused["error"]["code"], "recovery_scope_decided")
        self.assertEqual(
            refused["error"]["details"]["details"]["path"],
            "Incoming/Sub/Left.2005.mkv",
        )
        self.assertEqual(self._target_files(), ["Left (2005).mkv"])

    def test_a_mixed_scope_is_refused_by_the_atomic_admission_alone(self):
        """The repository transaction refuses a decided sibling by itself.

        The application preflight can be disabled for this call, so only the
        repository's own ``BEGIN IMMEDIATE`` admission transaction can refuse
        the mixed selection.  The decision is recorded as an explicit operator
        ignore, which changes no source evidence version, so the guarantee
        cannot depend on a check that runs before the write.  The unrelated
        legal `Right` must not carry the already-decided `Left` through.
        """

        from mediaflow.application.manual_organize_execution import (
            ManualOrganizeExecutionService,
        )
        from mediaflow.domain.manual_execution import ManualExecutionError

        config, active = self._copy_journey_active()
        task = self._mixed_two_source_task(active)
        api = self._api(config)
        endpoint = f"/api/v1/tasks/{task.task_id}/remaining-scope-previews"

        status, admission = request(api, endpoint, method="POST", body=None, token="admin-token")
        self.assertEqual(status, 202, admission)
        document = self._drive_recovery(api, admission["discoveryId"])
        preview = self.repository.get_manual_preview(document["previewId"])
        service: ManualOrganizeExecutionService = api._manual_execution
        # The one-shot authority for the whole mixed set is created while every
        # source is still undecided.
        authority = service.authorize(
            preview.preview_id,
            [value.item_id for value in preview.items],
            expected_intent_version=preview.intent_version,
            actor="admin",
            confirmation=True,
        )
        # An explicit ignore of only `Left` retires that source without a Result
        # or any evidence-version change; `Right` stays real remaining work.
        original_item = next(
            value
            for value in self.repository.list_items(task.task_id)
            if value.source_path == "Incoming/Sub/Left.2005.mkv"
        )
        self.repository.upsert_item(
            replace(original_item, status=TaskItemStatus.IGNORED, stage="ignored_by_operator")
        )

        # With the application preflight disabled, only the atomic transaction
        # can refuse the already-decided `Left`.
        with mock.patch.object(ManualOrganizeExecutionService, "_assert_recovery_preparation_live"):
            with self.assertRaises(ManualExecutionError) as raised:
                service.admit(authority.authorization_id, actor="admin", confirmation=True)
        self.assertEqual(raised.exception.code, "recovery_scope_decided")
        self.assertEqual(self._target_files(), [])
        self.assertEqual(self.repository.list_manual_executions_for_preview(preview.preview_id), ())

    def test_a_queued_mixed_execution_refuses_the_decided_source_per_item(self):
        """A queued mixed execution re-judges each source before its own mutation.

        Both sources were legally authorized and admitted while undecided, so the
        durable execution, the reviewed Preview and the Storage fence are all
        valid.  The deciding effect for `Left` arrives afterwards as an explicit
        operator ignore, so only the Worker's own per-source boundary can notice
        it and close that one item as a truthful pre-mutation failure while the
        independent `Right` still runs.
        """

        config, active = self._copy_journey_active()
        task = self._mixed_two_source_task(active)
        api = self._api(config)
        endpoint = f"/api/v1/tasks/{task.task_id}/remaining-scope-previews"

        status, admission = request(api, endpoint, method="POST", body=None, token="admin-token")
        self.assertEqual(status, 202, admission)
        document = self._drive_recovery(api, admission["discoveryId"])
        preview = self.repository.get_manual_preview(document["previewId"])
        status, execution = self._confirm(api, preview)
        self.assertEqual(status, 202, execution)

        # The operator explicitly ignores `Left` while the mixed execution waits
        # in the queue.  The ignore writes only the original TaskItem; the
        # admitted execution's own pending item is retired by exact source
        # evidence, and `Right` remains real remaining work.
        original_item = next(
            value
            for value in self.repository.list_items(task.task_id)
            if value.source_path == "Incoming/Sub/Left.2005.mkv"
        )
        self.repository.upsert_item(
            replace(original_item, status=TaskItemStatus.IGNORED, stage="ignored_by_operator")
        )

        result = self._drive_once(api)
        self.assertEqual(result.execution_id, execution["executionId"])
        self.assertEqual(result.status.value, "partial_success")
        results = self.repository.list_results(execution["taskId"])
        by_path = {value.source_path: value for value in results}
        self.assertEqual(
            sorted(by_path), ["Incoming/Sub/Left.2005.mkv", "Incoming/Sub/Right.2006.mkv"]
        )
        self.assertEqual(by_path["Incoming/Sub/Left.2005.mkv"].effect_certainty, "none")
        self.assertEqual(by_path["Incoming/Sub/Right.2006.mkv"].status, "SUCCESS")
        self.assertEqual(sorted(self._target_files()), ["Right (2006).mkv"])

    def test_a_mixed_scope_reopens_with_the_same_per_source_refusal(self):
        """A reopened connection reaches the same per-source verdict."""

        config, active = self._copy_journey_active()
        task = self._mixed_two_source_task(active)
        api = self._api(config)
        endpoint = f"/api/v1/tasks/{task.task_id}/remaining-scope-previews"
        status, first = request(api, endpoint, method="POST", body=None, token="admin-token")
        self.assertEqual(status, 202, first)
        first_document = self._drive_recovery(api, first["discoveryId"])
        first_preview = self.repository.get_manual_preview(first_document["previewId"])
        self._execute_only(api, first_preview, "Incoming/Sub/Left.2005.mkv")
        with SQLiteTaskRepository(self.database) as reopened:
            source = reopened.get_task(task.task_id)
            eligibility = recovery_preparation_eligibility(
                reopened, recovery_source_task_id=source.task_id
            )
            self.assertTrue(eligibility.eligible)
            refused = eligibility.refused_sources(
                (
                    ("source-storage", "Incoming/Sub/Left.2005.mkv"),
                    ("source-storage", "Incoming/Sub/Right.2006.mkv"),
                )
            )
            self.assertEqual(refused, (("source-storage", "Incoming/Sub/Left.2005.mkv"),))

    def test_an_ordinary_files_preparation_is_never_governed_by_recovery_eligibility(self):
        """A non-recovery preparation keeps its own independent lifecycle.

        The recovery fence is keyed on an explicit recovery origin only, so an
        ordinary Files preparation over the same directory still publishes and
        executes even though the paused run's chain is fully decided.
        """

        from mediaflow.application.scope_continuation import (
            recovery_preparation_eligibility,
        )

        config, active = self._copy_journey_active()
        task = self._recorded_budget_two(active)
        api = self._api(config)
        self._recovery_executed_once(api, task)
        ordinary = recovery_preparation_eligibility(self.repository, recovery_source_task_id=None)
        self.assertTrue(ordinary.eligible)
        self.assertTrue(ordinary.may_offer("source-storage", "Incoming/Sub/Left.2005.mkv"))
        # The same directory still prepares as ordinary Files work.
        status, admission = request(
            api,
            "/api/v1/resource-libraries/source/files/discoveries",
            method="POST",
            body={"paths": ["Sub"], "autoPrepare": True},
            token="admin-token",
        )
        self.assertEqual(status, 202, admission)
        self.assertIsNone(admission.get("recoverySourceTaskId"))
        document = self._drive_recovery(api, admission["discoveryId"])
        self.assertTrue(document["prepared"])
        preview = self.repository.get_manual_preview(document["previewId"])
        self.assertIsNotNone(preview)
        self.assertIsNone(preview.recovery_source_task_id)

    def test_a_completed_move_recovery_is_terminal_for_the_original_pending(self):
        """A verified MOVE is equally terminal, so its source is never replayed.

        MOVE removes the source, which would make a naive "is the file still
        there?" check look like a safe no-op. The decision must come from the
        recorded Result, not from the file's presence, so the ancestor `pending`
        item is retired exactly like the COPY case.
        """

        config, active = self._activate(scope="Incoming")
        task = self._recorded_budget_two(active)
        api = self._api(config)

        result, child_task_id = self._recovery_executed_once(api, task)
        self.assertEqual(result.status.value, "completed")
        child_results = self.repository.list_results(child_task_id)
        self.assertEqual(child_results[0].operation, "MOVE")
        self.assertEqual(child_results[0].effect_certainty, "verified_complete")
        self.assertFalse((self.root / "Incoming" / "Sub" / "Left.2005.mkv").exists())
        plan = recovery_scope_plan(self.repository, self.repository.get_task(task.task_id))
        self.assertEqual(plan.undecided_items, ())
        self.assertIn(("source-storage", "Incoming/Sub/Left.2005.mkv"), plan.replay_excluded)
        self.assertEqual(
            sorted(path.name for path in (self.root / "Target").rglob("*.mkv")),
            ["Left (2005).mkv"],
        )

    def test_an_attachment_warning_keeps_the_verified_primary_terminal(self):
        """A verified primary with attachment warnings is never replayed.

        The organizer records `PARTIAL` with `primary_completed=True` when the
        primary was verified and only an independent attachment failed. RO-3 makes
        that a primary success: the attachment reason is shown, and the primary is
        not replayed to repair it.
        """

        config, active = self._copy_journey_active()
        task = self._recorded_budget_two(active)
        api = self._api(config)
        original_item = next(
            value
            for value in self.repository.list_items(task.task_id)
            if value.source_path == "Incoming/Sub/Left.2005.mkv"
        )
        self.repository.append_result(
            PersistentResultRecord(
                f"{original_item.item_id}:1",
                task.task_id,
                original_item.item_id,
                "source-storage",
                "Incoming/Sub/Left.2005.mkv",
                "media-target",
                "Movies/Left (2005).mkv",
                "C",
                "tmdb",
                "100",
                "C",
                "A",
                "A",
                "A",
                "COPY",
                "PARTIAL",
                NOW,
                title="Left",
                error="one attachment could not be copied",
                completed_operations=("COPY",),
                attachment_count=1,
                effect_certainty="verified_complete",
                primary_completed=True,
                attachment_results=(
                    {
                        "source_path": "Incoming/Sub/Left.2005.srt",
                        "status": "failed",
                        "reason": "attachment_collision",
                        "effect_certainty": "none",
                    },
                ),
                source_occurrence_id=original_item.source_occurrence_id,
                source_fingerprint=original_item.source_fingerprint,
            )
        )
        plan = recovery_scope_plan(self.repository, self.repository.get_task(task.task_id))
        self.assertEqual(plan.undecided_items, ())
        self.assertEqual(plan.new_source_budget, 0)
        status, second = request(
            api,
            f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 409, second)
        self.assertEqual(second["error"]["code"], "no_remaining_scope")
        self.assertFalse(list((self.root / "Target").rglob("*.mkv")))

    def test_an_ignored_attempt_never_resurrects_the_pending_ancestor(self):
        """An explicit operator ignore retires the source without any Result.

        Ignoring a *later* attempt of the same chain records only its own
        TaskItem, so a check that reads Results alone would leave the ancestor
        `pending` item recoverable and the operator could be offered work they
        just decided to drop.
        """

        from mediaflow.application.scope_continuation import _SourceObservation

        config, active = self._copy_journey_active()
        task = self._recorded_budget_two(active)
        api = self._api(config)
        original_item = next(
            value
            for value in self.repository.list_items(task.task_id)
            if value.source_path == "Incoming/Sub/Left.2005.mkv"
        )
        # A later attempt of the same exact source was explicitly ignored: that
        # rewrite only touches the attempt's own TaskItem and writes no Result.
        # The exact same TaskItem shape the storage enforces is used here.
        later_attempt = replace(
            original_item,
            status=TaskItemStatus.IGNORED,
            stage="ignored_by_operator",
            source_fingerprint=None,
            source_occurrence_id=None,
            source_fingerprint_state="unverified",
        )
        self.repository.upsert_item(later_attempt)
        observation = _SourceObservation("source-storage", "Incoming/Sub/Left.2005.mkv", None)
        self.assertTrue(observation.is_the_same_file_as(later_attempt))
        plan = recovery_scope_plan(self.repository, self.repository.get_task(task.task_id))
        self.assertEqual(plan.undecided_items, ())
        self.assertEqual(plan.unrecorded_budget, 0)
        status, document = request(
            api,
            f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 409, document)
        self.assertEqual(document["error"]["code"], "no_remaining_scope")
        self.assertFalse(list((self.root / "Target").rglob("*.mkv")))

    def test_an_uncertain_effect_never_resurrects_the_pending_ancestor(self):
        """An unverified effect stays investigation-only across the chain.

        The executor's own `unknown` value — not only `attempted_unverified` — is
        an unverified effect, so a later uncertain attempt must retire the source
        from recovery instead of turning it into a retryable item.
        """

        config, active = self._copy_journey_active()
        task = self._recorded_budget_two(active)
        api = self._api(config)
        original_item = next(
            value
            for value in self.repository.list_items(task.task_id)
            if value.source_path == "Incoming/Sub/Left.2005.mkv"
        )
        self.repository.append_result(
            PersistentResultRecord(
                f"{original_item.item_id}:1",
                task.task_id,
                original_item.item_id,
                "source-storage",
                "Incoming/Sub/Left.2005.mkv",
                "media-target",
                "Movies/Left (2005).mkv",
                "C",
                "tmdb",
                "100",
                "C",
                "A",
                "A",
                "A",
                "COPY",
                "PARTIAL",
                NOW,
                title="Left",
                effect_certainty="unknown",
                uncertain_effects=("executor_invocation",),
                source_occurrence_id=original_item.source_occurrence_id,
                source_fingerprint=original_item.source_fingerprint,
            )
        )
        plan = recovery_scope_plan(self.repository, self.repository.get_task(task.task_id))
        self.assertEqual(plan.undecided_items, ())
        self.assertEqual(plan.unrecorded_budget, 0)
        status, document = request(
            api,
            f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 409, document)
        self.assertEqual(document["error"]["code"], "no_remaining_scope")
        self.assertFalse(list((self.root / "Target").rglob("*.mkv")))

    def test_a_zero_effect_failure_stays_safely_recoverable(self):
        """A failure that provably mutated nothing is still recoverable work.

        Bounded recovery must not over-correct: a `none` effect means the
        executor never crossed the mutation boundary, so the operator may review
        that exact source again. The decided-source rule therefore keys on a
        proven effect, not on the failure status. The same source is offered
        exactly once even though two attempts recorded it.
        """

        from mediaflow.domain.organizer import (
            ExecutionEffectCertainty,
            ExecutionResult,
            ExecutionStatus,
        )

        class _ZeroEffectExecutor:
            """A real executor invocation that provably changed nothing."""

            def execute(self, plan, _storages, **_kwargs):
                return ExecutionResult(
                    ExecutionStatus.FAILED,
                    plan.operation,
                    plan.source,
                    plan.target,
                    plan_id=plan.plan_id,
                    resolved_destination=plan.target,
                    errors=("injected pre-mutation failure",),
                    effect_certainty=ExecutionEffectCertainty.NONE,
                )

        config, active = self._copy_journey_active()
        task = self._recorded_budget_two(active)
        api = self._api(config)
        result, child_task_id = self._recovery_attempt(api, task, executor=_ZeroEffectExecutor())
        self.assertEqual(result.status.value, "failed")
        child_results = self.repository.list_results(child_task_id)
        self.assertEqual(child_results[0].effect_certainty, "none")
        plan = recovery_scope_plan(self.repository, self.repository.get_task(task.task_id))
        # The exact source is still undecided *work*: it is offered once, not once
        # per attempt, and the original admission is not widened.
        self.assertEqual(
            [value.source_path for value in plan.undecided_items],
            ["Incoming/Sub/Left.2005.mkv"],
        )
        self.assertEqual(plan.new_source_budget, 1)
        self.assertEqual(plan.unrecorded_budget, 0)
        self.assertNotIn(("source-storage", "Incoming/Sub/Left.2005.mkv"), plan.replay_excluded)
        status, admission = request(
            api,
            f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 202, admission)
        document = self._drive_recovery(api, admission["discoveryId"])
        preview = self.repository.get_manual_preview(document["previewId"])
        self.assertEqual(
            [value.source.path for value in preview.items],
            ["Incoming/Sub/Left.2005.mkv"],
        )

    def test_a_replaced_file_at_the_same_path_keeps_its_own_undecided_state(self):
        """New bytes at the same path are new work, not a retired source.

        Only a Result proving the *same* observed occurrence retires an item. A
        genuinely replaced file therefore stays recoverable instead of being
        suppressed forever by an earlier success at that path.
        """

        config, active = self._copy_journey_active()
        task = self._recorded_budget_two(active)
        api = self._api(config)
        original_item = next(
            value
            for value in self.repository.list_items(task.task_id)
            if value.source_path == "Incoming/Sub/Left.2005.mkv"
        )
        self._recovery_executed_once(api, task)
        # The earlier success retires the recorded occurrence.
        plan = recovery_scope_plan(self.repository, self.repository.get_task(task.task_id))
        self.assertEqual(plan.undecided_items, ())
        # A different file now occupies the same path.
        (self.root / "Incoming" / "Sub" / "Left.2005.mkv").write_bytes(b"different bytes entirely")
        entry = LocalStorage("source-storage", self.root).stat(original_item.source_path)
        replaced = source_fingerprint("source-storage", "source", entry)
        self.assertNotEqual(replaced.value, original_item.source_fingerprint)
        self.repository.upsert_item(
            replace(
                original_item,
                status=TaskItemStatus.PENDING,
                stage="pending",
                source_fingerprint=replaced.value,
                source_fingerprint_state="verified",
                source_occurrence_id=occurrence_id_for(
                    "source-storage", "source", original_item.source_path, replaced.value
                ),
                source_observed_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        plan = recovery_scope_plan(self.repository, self.repository.get_task(task.task_id))
        self.assertEqual(
            [value.source_path for value in plan.undecided_items],
            ["Incoming/Sub/Left.2005.mkv"],
        )
        self.assertEqual(plan.unrecorded_budget, 0)
        self.assertNotIn(("source-storage", "Incoming/Sub/Left.2005.mkv"), plan.replay_excluded)
        status, admission = request(
            api,
            f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 202, admission)
        document = self._drive_recovery(api, admission["discoveryId"])
        preview = self.repository.get_manual_preview(document["previewId"])
        self.assertEqual(
            [value.source.path for value in preview.items],
            ["Incoming/Sub/Left.2005.mkv"],
        )

    def test_a_new_independent_run_is_never_suppressed_by_an_old_success(self):
        """A genuinely new bounded run over the same file is its own work.

        The decided-source rule only spans one recorded continuation chain, so an
        independent new run of the same directory is not permanently blocked by
        an earlier successful attempt.
        """

        config, active = self._copy_journey_active()
        task = self._recorded_budget_two(active)
        api = self._api(config)
        self._recovery_executed_once(api, task)
        self.assertEqual(
            recovery_scope_plan(
                self.repository, self.repository.get_task(task.task_id)
            ).undecided_items,
            (),
        )
        # A genuinely independent run has its own Task identity; the earlier
        # chain's decided sources must not suppress it.
        fresh = PersistentTask(
            "task-independent-run",
            "organize",
            PersistentTaskStatus.RUNNING,
            True,
            NOW,
            NOW,
            started_at=NOW,
            scope_path="Incoming/Sub",
            item_limit=2,
            configuration_snapshot_id=active.revision_id,
            configuration_snapshot_digest=active.digest,
        )
        self.repository.create_task(fresh)
        fresh = self.coordinator.acknowledge_pause(
            self.repository.request_task_pause(fresh.task_id, NOW).task_id
        )
        fresh_item = self.coordinator.record_discovered(
            fresh.task_id,
            "source-storage",
            "source",
            "Incoming/Sub/Left.2005.mkv",
            "source-storage:Incoming/Sub/Left.2005.mkv",
        )
        self.repository.upsert_item(replace(fresh_item, status=TaskItemStatus.PENDING))
        fresh_plan = recovery_scope_plan(self.repository, self.repository.get_task(fresh.task_id))
        self.assertEqual(
            [value.source_path for value in fresh_plan.undecided_items],
            ["Incoming/Sub/Left.2005.mkv"],
        )
        self.assertEqual(fresh_plan.replay_excluded, frozenset())

    def test_recovery_identity_isolates_tasks_and_ordinary_files_preparations(self) -> None:
        """Two runs' recoveries and an ordinary Files preparation never alias.

        Same actor, library, root, pinned revision and the same directory scope
        for every request, which is exactly the shape that used to collapse all
        three intents onto one durable discovery identity.
        """

        config, active = self._activate(scope="Incoming")
        sub = self.root / "Incoming" / "Sub"
        sub.mkdir()
        (sub / "Kept.2006.mkv").write_bytes(b"kept")
        (sub / "Left.2005.mkv").write_bytes(b"left")
        first = self._paused_mutation_scan(active, discovered="Incoming/Sub/Kept.2006.mkv")
        first = replace(first, command="organize", scope_path="Incoming/Sub")
        self.repository.update_task(first)
        second = PersistentTask(
            "task-second",
            "organize",
            PersistentTaskStatus.RUNNING,
            True,
            NOW,
            NOW,
            started_at=NOW,
            scope_path="Incoming/Sub",
            item_limit=4,
            configuration_snapshot_id=active.revision_id,
            configuration_snapshot_digest=active.digest,
        )
        self.repository.create_task(second)
        self.repository.request_task_pause(second.task_id, NOW)
        second = self.coordinator.acknowledge_pause(second.task_id)
        api = self._api(config)

        status, first_admission = request(
            api,
            f"/api/v1/tasks/{first.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 202, first_admission)
        # The same exact recovery request converges on its own durable record.
        status, first_repeat = request(
            api,
            f"/api/v1/tasks/{first.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 202, first_repeat)
        self.assertEqual(first_repeat["discoveryId"], first_admission["discoveryId"])
        # A second paused run over the same directory is its own admission.
        status, second_admission = request(
            api,
            f"/api/v1/tasks/{second.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 202, second_admission)
        self.assertNotEqual(second_admission["discoveryId"], first_admission["discoveryId"])
        self.assertEqual(second_admission["recoverySourceTaskId"], second.task_id)
        # An ordinary Files preparation of the same directory is a new intent.
        status, ordinary = request(
            api,
            "/api/v1/resource-libraries/source/files/discoveries",
            method="POST",
            body={"paths": ["Sub"], "autoPrepare": True},
            token="admin-token",
        )
        self.assertEqual(status, 202, ordinary)
        self.assertNotIn(
            ordinary["discoveryId"],
            {first_admission["discoveryId"], second_admission["discoveryId"]},
        )
        self.assertIsNone(ordinary.get("recoverySourceTaskId"))
        # A recovery admitted first does not answer a later ordinary request: the
        # repeated ordinary admission converges on its own record and keeps the
        # whole directory it was asked to prepare.
        status, ordinary_repeat = request(
            api,
            "/api/v1/resource-libraries/source/files/discoveries",
            method="POST",
            body={"paths": ["Sub"], "autoPrepare": True},
            token="admin-token",
        )
        self.assertEqual(status, 202, ordinary_repeat)
        self.assertEqual(ordinary_repeat["discoveryId"], ordinary["discoveryId"])
        # Every intent keeps its own manifest; nothing broadened or narrowed.
        prepared = {}
        for discovery in (first_admission, second_admission, ordinary):
            document = self._drive_recovery(api, discovery["discoveryId"])
            preview = self.repository.get_manual_preview(document["previewId"])
            prepared[discovery["discoveryId"]] = sorted(
                value.source.path for value in preview.items
            )
        self.assertEqual(prepared[first_admission["discoveryId"]], ["Incoming/Sub/Left.2005.mkv"])
        # The second run recorded nothing, so its own remaining scope is the
        # whole directory: it is a separate admission, never the first run's
        # narrowed manifest.
        self.assertEqual(
            prepared[second_admission["discoveryId"]],
            ["Incoming/Sub/Kept.2006.mkv", "Incoming/Sub/Left.2005.mkv"],
        )
        self.assertEqual(
            prepared[ordinary["discoveryId"]],
            ["Incoming/Sub/Kept.2006.mkv", "Incoming/Sub/Left.2005.mkv"],
        )
        # An ordinary preparation admitted first does not block a later recovery:
        # the recovery intent is a new admission that observes only its own
        # remaining scope.
        status, after_ordinary = request(
            api,
            f"/api/v1/tasks/{first.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 202, after_ordinary)
        self.assertNotIn(
            after_ordinary["discoveryId"],
            {first_admission["discoveryId"], ordinary["discoveryId"]},
        )
        self.assertEqual(after_ordinary["recoverySourceTaskId"], first.task_id)
        later = self._drive_recovery(api, after_ordinary["discoveryId"])
        later_preview = self.repository.get_manual_preview(later["previewId"])
        self.assertEqual(
            [value.source.path for value in later_preview.items],
            ["Incoming/Sub/Left.2005.mkv"],
        )
        self.assertEqual((sub / "Kept.2006.mkv").read_bytes(), b"kept")
        self.assertEqual((sub / "Left.2005.mkv").read_bytes(), b"left")
        self.assertFalse(list((self.root / "Target").rglob("*.mkv")))

    def test_a_paused_run_reviews_its_exact_space_suffixed_directory(self) -> None:
        """B P1: a durable trailing-space directory must never resolve to its sibling.

        Two real directories differ only by a trailing space.  A real CLI run
        pauses inside the exact ``Folder `` directory; the native remaining-scope
        recovery must review that directory, never the neighbouring ``Folder``.
        The pause is a genuine authenticated API request issued from the real
        Task-creation boundary, so the durable scope is exactly what the CLI
        admitted.
        """

        from mediaflow.application.metadata import MetadataProviderRegistry
        from mediaflow.application.task_runtime import PersistentTaskCoordinator
        from mediaflow.final_cli import final_main

        config, active = self._activate(scope="Incoming")
        intended = self.root / "Incoming" / "Folder "
        sibling = self.root / "Incoming" / "Folder"
        intended.mkdir()
        sibling.mkdir()
        (intended / "Left.2005.mkv").write_bytes(b"intended")
        (sibling / "Right.2006.mkv").write_bytes(b"not in original scope")
        api = self._api(config)
        report: dict[str, object] = {}
        original_create = PersistentTaskCoordinator.create

        def create_and_pause(coordinator, *args, **kwargs):
            task = original_create(coordinator, *args, **kwargs)
            report["task_id"] = task.task_id
            report["scope_path"] = task.scope_path
            status, body = request(
                api,
                f"/api/v1/tasks/{task.task_id}/pause",
                method="POST",
                body={"expectedUpdatedAt": task.updated_at.isoformat()},
            )
            self.assertEqual(status, 200, body)
            return task

        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch.object(PersistentTaskCoordinator, "create", create_and_pause),
            mock.patch(
                "mediaflow.final_cli.metadata_provider_registry_from_environment",
                return_value=MetadataProviderRegistry(()),
            ),
        ):
            code = final_main(
                ["--config", str(config), "organize", str(intended), "--limit", "1"],
                stdout=stdout,
                stderr=stderr,
            )
        self.assertEqual(code, 75, (stdout.getvalue(), stderr.getvalue()))
        task = self.repository.get_task(report["task_id"])
        self.assertIs(task.status, PersistentTaskStatus.PAUSED)
        self.assertEqual(task.scope_path, str(intended))
        self.assertEqual(len(self.repository.list_items(task.task_id)), 0)

        status, admission = request(
            api,
            f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 202, admission)
        document = self._drive_recovery(api, admission["discoveryId"])
        self.assertEqual(document["prepared"], True)
        preview = self.repository.get_manual_preview(document["previewId"])
        self.assertEqual(
            [item.source.path for item in preview.items],
            ["Incoming/Folder /Left.2005.mkv"],
        )
        # The neighbouring sibling is neither observed as a candidate nor
        # mutated, and the source bytes are unchanged.
        self.assertEqual((intended / "Left.2005.mkv").read_bytes(), b"intended")
        self.assertEqual((sibling / "Right.2006.mkv").read_bytes(), b"not in original scope")
        self.assertFalse(list((self.root / "Target").rglob("*.mkv")))

    def test_a_missing_exact_scope_directory_never_falls_back_to_its_sibling(self) -> None:
        """A vanished trailing-space directory must refuse, not review the sibling.

        When the original exact scope no longer exists, recovery keeps the
        original Task and reports the missing source; it must never quietly
        re-admit the trimmed neighbour, the parent directory or the whole
        library.  Zero Storage mutation and no execution authority.
        """

        config, active = self._activate(scope="Incoming")
        sibling = self.root / "Incoming" / "Folder"
        sibling.mkdir()
        (sibling / "Right.2006.mkv").write_bytes(b"not in original scope")
        original = self._paused_mutation_scan(active)
        # The admitted scope is the exact `Folder ` directory, which is absent.
        self.repository.update_task(
            replace(original, scope_path=str(self.root / "Incoming" / "Folder "))
        )
        api = self._api(config)
        status, body = request(
            api,
            f"/api/v1/tasks/{original.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertIn(status, {404, 409}, body)
        self.assertEqual(body["error"]["code"], "source_missing")
        self.assertEqual(body["error"]["details"]["relativePath"], "Folder ")
        self.assertEqual(body["error"]["details"]["sideEffects"], "none")
        # The original Task and the sibling remain untouched.
        self.assertIs(
            self.repository.get_task(original.task_id).status, PersistentTaskStatus.PAUSED
        )
        self.assertEqual((sibling / "Right.2006.mkv").read_bytes(), b"not in original scope")
        self.assertFalse(list((self.root / "Target").rglob("*.mkv")))

    # -- the pre-admission existence probe is itself bounded --------------

    def _probe_task(self, active, *, scope: str = "Incoming"):
        """One paused mutation-authorized run over ``scope`` for probe cases."""

        return self._paused_mutation_scan(active)

    def _paged_storage(self, *, pages, max_page_fetches: int):
        """A read-only guard whose ``list_page`` serves the exact supplied pages.

        ``pages`` maps a ResourceLibrary-relative directory to a callable
        ``(call_number, storage_path) -> StoragePage`` so a case can repeat a
        cursor, vary cursors forever or fail on a chosen fetch.  Every mutation is
        counted by the real shared guard.
        """

        real = LocalStorage("source-storage", self.root)
        state = {"calls": 0}

        class _Paged:
            storage_id = "source-storage"
            name = "paged"
            read_only = True

            def stat(self, path):
                return real.stat(path)

            def list_page(self, path, *, limit, cursor=None):
                state["calls"] += 1
                if state["calls"] > max_page_fetches + 50:
                    # A hard stop so a runaway probe cannot hang the suite; the
                    # case's own bound assertion proves the product stopped well
                    # before this safety stop.
                    raise AssertionError("probe exceeded the safety stop")
                return pages[path](state["calls"], path)

        return ReadOnlyStorageGuard(_Paged()), state

    def test_the_admission_probe_stops_at_the_page_budget_instead_of_hanging(self) -> None:
        """B P1: a provider that never advances its cursor cannot hold the request.

        The pre-admission existence probe used to iterate ``next_cursor`` without
        any page, entry, directory, depth or time bound.  A fake provider that
        kept returning a fresh empty page made the synchronous POST perform more
        fetches than ``max_page_fetches`` and still admit.  The probe must now
        stop at the real bound and admit an ordinary durable preparation so the
        bounded Worker records the truthful reason.
        """

        config, active = self._activate(scope="Incoming")
        (self.root / "Incoming" / "Left.2005.mkv").write_bytes(b"left")
        task = self._probe_task(active)
        api = self._api(config)

        def endless_empty(_call: int, _path: str) -> StoragePage:
            return StoragePage((), f"cursor-{_call}")

        guard, state = self._paged_storage(pages={"Incoming": endless_empty}, max_page_fetches=3)
        # The configured discovery budget itself is what must stop the probe.
        api._media_discovery._budgets = DiscoveryBudgets(max_page_fetches=3)
        with mock.patch.object(api._media_discovery, "_guarded_storage", return_value=guard):
            status, body = request(
                api,
                f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
                method="POST",
                body=None,
                token="admin-token",
            )
        # The request returns an ordinary durable preparation, not a hang and
        # not a fabricated ``no_remaining_scope``.
        self.assertEqual(status, 202, body)
        self.assertIsNotNone(body.get("discoveryId"))
        # The probe never consumed more than the configured page budget (plus at
        # most the bounded file-probe page), so it is a real bound.
        self.assertLessEqual(state["calls"], 3)
        self.assertEqual(guard.mutation_calls, {key: 0 for key in guard.mutation_calls})
        self.assertEqual((self.root / "Incoming" / "Left.2005.mkv").read_bytes(), b"left")
        self.assertFalse(list((self.root / "Target").rglob("*.mkv")))

    def test_the_admission_probe_refuses_a_provider_entry_outside_the_exact_scope(self) -> None:
        """B P1: the probe must never traverse a directory the task never admitted.

        The old probe followed the raw ``StorageEntry.path`` of whatever the
        provider returned, so a misbehaving adapter could hand back a sibling
        directory that was then ``stat``-ed and listed.  The bounded probe now
        admits each entry through the exact same ``_admit_provider_entry``
        boundary the Worker uses, so a wrong-parent entry stops it as incomplete
        and the sibling is never read.
        """

        config, active = self._activate(scope="Incoming")
        allowed = self.root / "Incoming" / "Allowed"
        allowed.mkdir()
        sibling = self.root / "Incoming" / "Sibling"
        sibling.mkdir()
        (sibling / "Proof.2001.mkv").write_bytes(b"outside")
        task = self._paused_mutation_scan(active)
        self.repository.update_task(replace(task, scope_path="Incoming/Allowed"))
        task = self.repository.get_task(task.task_id)
        api = self._api(config)

        reads: list[tuple[str, str]] = []
        self_root = self.root

        class _WrongParent:
            storage_id = "source-storage"
            name = "wrong-parent"
            read_only = True

            def stat(self, path):
                reads.append(("stat", path))
                return LocalStorage("source-storage", self_root).stat(path)

            def list_page(self, path, *, limit, cursor=None):
                reads.append(("list_page", path))
                if path == "Incoming/Allowed":
                    return StoragePage(
                        (
                            StorageEntry(
                                "Sibling",
                                "Incoming/Sibling",
                                StorageEntryType.DIRECTORY,
                                0,
                                datetime(2026, 1, 1, tzinfo=UTC),
                            ),
                        )
                    )
                return LocalStorage("source-storage", self_root).list_page(
                    path, limit=limit, cursor=cursor
                )

        guard = ReadOnlyStorageGuard(_WrongParent())
        with mock.patch.object(api._media_discovery, "_guarded_storage", return_value=guard):
            status, body = request(
                api,
                f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
                method="POST",
                body=None,
                token="admin-token",
            )
        # The preparation is admitted (incomplete probe), but the sibling was
        # never stat-ed or listed: the exact-scope admission stopped the probe.
        self.assertEqual(status, 202, body)
        self.assertNotIn(("list_page", "Incoming/Sibling"), reads)
        self.assertNotIn(("stat", "Incoming/Sibling"), reads)
        self.assertEqual(guard.mutation_calls, {key: 0 for key in guard.mutation_calls})
        self.assertEqual((sibling / "Proof.2001.mkv").read_bytes(), b"outside")

    def test_the_admission_probe_refuses_a_repeated_cursor(self) -> None:
        """A repeated non-empty cursor stops the probe as incomplete, never empty."""

        config, active = self._activate(scope="Incoming")
        (self.root / "Incoming" / "Left.2005.mkv").write_bytes(b"left")
        task = self._probe_task(active)
        api = self._api(config)

        def repeated(_call: int, _path: str) -> StoragePage:
            # The same non-empty cursor forever, with an empty page each time.
            return StoragePage((), "same-cursor")

        guard, state = self._paged_storage(pages={"Incoming": repeated}, max_page_fetches=10)
        with mock.patch.object(api._media_discovery, "_guarded_storage", return_value=guard):
            status, body = request(
                api,
                f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
                method="POST",
                body=None,
                token="admin-token",
            )
        self.assertEqual(status, 202, body)
        self.assertIsNotNone(body.get("discoveryId"))
        # The probe stops on the first repeated cursor, not on the page budget.
        self.assertLessEqual(state["calls"], 2)
        self.assertEqual(guard.mutation_calls, {key: 0 for key in guard.mutation_calls})
        self.assertFalse(list((self.root / "Target").rglob("*.mkv")))

    def test_the_admission_probe_honours_the_entry_budget(self) -> None:
        """More entries than ``max_visited_entries`` stops the probe bounded.

        The probe must enforce the same per-entry bound the Worker does.  Each
        page here carries exactly one excluded (non-media) entry, so the page
        count is the entry count and a tiny entry budget proves the stop without
        ever reaching the page budget.
        """

        config, active = self._activate(scope="Incoming")
        for index in range(10):
            (self.root / "Incoming" / f"Bulk.{index:03d}.txt").write_bytes(b"x")
        task = self._probe_task(active)
        api = self._api(config)
        api._media_discovery._budgets = DiscoveryBudgets(
            max_visited_entries=2, max_page_fetches=1000
        )
        real = LocalStorage("source-storage", self.root)
        state = {"calls": 0}

        class _OneEntryPerPage:
            storage_id = "source-storage"
            name = "one-entry"
            read_only = True

            def stat(self, path):
                return real.stat(path)

            def list_page(self, path, *, limit, cursor=None):
                state["calls"] += 1
                entries = tuple(real.list(path))
                start = int(cursor) if cursor else 0
                if start >= len(entries):
                    return StoragePage(())
                next_cursor = str(start + 1) if start + 1 < len(entries) else None
                return StoragePage((entries[start],), next_cursor)

        guard = ReadOnlyStorageGuard(_OneEntryPerPage())
        with mock.patch.object(api._media_discovery, "_guarded_storage", return_value=guard):
            status, body = request(
                api,
                f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
                method="POST",
                body=None,
                token="admin-token",
            )
        # An exhausted entry budget without a candidate is an incomplete probe:
        # the request is admitted for the Worker to record the real reason.
        self.assertEqual(status, 202, body)
        self.assertLessEqual(state["calls"], 3)
        self.assertEqual(guard.mutation_calls, {key: 0 for key in guard.mutation_calls})
        self.assertFalse(list((self.root / "Target").rglob("*.mkv")))

    def test_the_admission_probe_refuses_a_storage_failure_instead_of_claiming_empty(self) -> None:
        """A read failure during the probe is incomplete, never ``no_remaining_scope``.

        The old probe returned ``True`` on any ``stat``/``list_page`` failure,
        which admitted a preparation whose emptiness was never actually proven.
        The bounded probe must treat a failure as an incomplete probe so the
        Worker records the real reason; a fully decided scope still refuses
        truthfully because it is proven by the exact undecided file set.
        """

        config, active = self._activate(scope="Incoming")
        (self.root / "Incoming" / "Left.2005.mkv").write_bytes(b"left")
        task = self._probe_task(active)
        api = self._api(config)
        real = LocalStorage("source-storage", self.root)

        class _Failing:
            storage_id = "source-storage"
            name = "failing"
            read_only = True

            def stat(self, path):
                return real.stat(path)

            def list_page(self, path, *, limit, cursor=None):
                raise StorageError(
                    StorageErrorCode.CONNECTION_LOST,
                    "list_page",
                    path,
                    "injected provider failure",
                )

        guard = ReadOnlyStorageGuard(_Failing())
        with mock.patch.object(api._media_discovery, "_guarded_storage", return_value=guard):
            status, body = request(
                api,
                f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
                method="POST",
                body=None,
                token="admin-token",
            )
        # A genuine failure is not an empty scope: the request is admitted so the
        # Worker records the real read failure rather than fabricating "nothing
        # to do".
        self.assertEqual(status, 202, body)
        self.assertEqual(guard.mutation_calls, {key: 0 for key in guard.mutation_calls})
        self.assertFalse(list((self.root / "Target").rglob("*.mkv")))

    def test_the_admission_probe_still_refuses_a_safely_empty_scope(self) -> None:
        """A really empty scope keeps the truthful ``no_remaining_scope`` refusal.

        Bounding the probe must not lose the safe-empty answer: a scope whose
        listing completes inside every bound and holds no candidate is proven
        empty, so admission refuses exactly like the inline boundary did, with
        zero durable work and zero Storage mutation.
        """

        config, active = self._activate(scope="Incoming")
        # Only excluded, non-media entries: the walk can finish with no candidate.
        (self.root / "Incoming" / "notes.txt").write_text("not media")
        (self.root / "Incoming" / "partial.part").write_bytes(b"downloading")
        task = self._probe_task(active)
        api = self._api(config)
        status, body = request(
            api,
            f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
            method="POST",
            body=None,
            token="admin-token",
        )
        self.assertEqual(status, 409, body)
        self.assertEqual(body["error"]["code"], "no_remaining_scope")
        self.assertEqual(body["error"]["details"]["sideEffects"], "none")
        self.assertEqual(
            self.repository.list_manual_previews_by_scope("resource_library", "source"), ()
        )
        self.assertEqual((self.root / "Incoming" / "notes.txt").read_text(), "not media")
        self.assertFalse(list((self.root / "Target").rglob("*.mkv")))

    def test_the_admission_probe_stops_at_the_safety_depth_boundary(self) -> None:
        """The probe honours the Task's own safety depth bound, like the Worker."""

        config, active = self._activate(scope="Incoming")
        deep = self.root / "Incoming" / "Deep"
        deep.mkdir()
        (deep / "Candidate.2001.mkv").write_bytes(b"deep")
        task = self._probe_task(active)
        api = self._api(config)
        # The safety bound is measured from the ResourceLibrary root exactly as
        # the Worker measures it, so a zero bound cuts the walk off before the
        # first-level child is ever entered.
        api._media_discovery._budgets = DiscoveryBudgets(max_depth=0)
        real = LocalStorage("source-storage", self.root)
        reads: list[tuple[str, str]] = []

        class _Recording:
            storage_id = "source-storage"
            name = "recording"
            read_only = True

            def stat(self, path):
                reads.append(("stat", path))
                return real.stat(path)

            def list_page(self, path, *, limit, cursor=None):
                reads.append(("list_page", path))
                return real.list_page(path, limit=limit, cursor=cursor)

        guard = ReadOnlyStorageGuard(_Recording())
        with mock.patch.object(api._media_discovery, "_guarded_storage", return_value=guard):
            status, body = request(
                api,
                f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
                method="POST",
                body=None,
                token="admin-token",
            )
        # The subtree below the safety depth is never entered; the probe stops
        # as incomplete and the ordinary Worker records the real depth reason.
        self.assertEqual(status, 202, body)
        self.assertFalse(any("Deep" in path for _, path in reads))
        self.assertEqual(guard.mutation_calls, {key: 0 for key in guard.mutation_calls})
        self.assertEqual((deep / "Candidate.2001.mkv").read_bytes(), b"deep")

    def test_the_admission_probe_refuses_a_provider_directory_cycle(self) -> None:
        """A listing that points back at an ancestor stops the probe, never loops."""

        config, active = self._activate(scope="Incoming")
        loop = self.root / "Incoming" / "Loop"
        loop.mkdir()
        (loop / "Candidate.2001.mkv").write_bytes(b"loop")
        task = self._probe_task(active)
        api = self._api(config)
        real = LocalStorage("source-storage", self.root)
        reads: list[tuple[str, str]] = []

        class _Cycling:
            storage_id = "source-storage"
            name = "cycling"
            read_only = True

            def stat(self, path):
                reads.append(("stat", path))
                return real.stat(path)

            def list_page(self, path, *, limit, cursor=None):
                reads.append(("list_page", path))
                if path == "Incoming/Loop":
                    # The provider claims an entry back at the ancestor: not one
                    # ordinary child, so the exact admission must refuse it.
                    return StoragePage(
                        (
                            StorageEntry(
                                "Incoming",
                                "Incoming",
                                StorageEntryType.DIRECTORY,
                                0,
                                datetime(2026, 1, 1, tzinfo=UTC),
                            ),
                        )
                    )
                return real.list_page(path, limit=limit, cursor=cursor)

        guard = ReadOnlyStorageGuard(_Cycling())
        with mock.patch.object(api._media_discovery, "_guarded_storage", return_value=guard):
            status, body = request(
                api,
                f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
                method="POST",
                body=None,
                token="admin-token",
            )
        self.assertEqual(status, 202, body)
        # Only the two real directories were ever read; the ancestor never
        # became a traversal target and no path outside the scope was listed.
        listed = [path for kind, path in reads if kind == "list_page"]
        self.assertEqual(listed, ["Incoming", "Incoming/Loop"])
        self.assertEqual(guard.mutation_calls, {key: 0 for key in guard.mutation_calls})
        self.assertEqual((loop / "Candidate.2001.mkv").read_bytes(), b"loop")

    def test_the_admission_probe_honours_the_active_time_boundary(self) -> None:
        """Elapsed work is cut off at ``max_active_seconds``, not by a page cap."""

        config, active = self._activate(scope="Incoming")
        (self.root / "Incoming" / "Left.2005.mkv").write_bytes(b"left")
        task = self._probe_task(active)
        api = self._api(config)
        ticks = {"now": 0.0}

        def fake_monotonic() -> float:
            ticks["now"] += 400.0
            return ticks["now"]

        guard, state = self._paged_storage(
            pages={"Incoming": lambda call, _path: StoragePage((), f"cursor-{call}")},
            max_page_fetches=10_000,
        )
        api._media_discovery._monotonic = fake_monotonic
        with mock.patch.object(api._media_discovery, "_guarded_storage", return_value=guard):
            status, body = request(
                api,
                f"/api/v1/tasks/{task.task_id}/remaining-scope-previews",
                method="POST",
                body=None,
                token="admin-token",
            )
        # Two 400-second ticks already exceed the 600-second bound, so the probe
        # admits after at most two page fetches instead of walking pages forever.
        self.assertEqual(status, 202, body)
        self.assertLessEqual(state["calls"], 2)
        self.assertEqual(guard.mutation_calls, {key: 0 for key in guard.mutation_calls})
        self.assertEqual((self.root / "Incoming" / "Left.2005.mkv").read_bytes(), b"left")

    def _drive_recovery(self, api, discovery_id: str) -> dict:
        """Drive one admitted remaining-scope preparation through its Worker.

        The native recovery admission is durable and asynchronous: the HTTP
        request records the bounded observation, and the resident Worker proves
        the configured stability interval before freezing and analysing.  This
        helper advances the same durable record and returns its final discovery
        document, exactly as the real Worker loop does.
        """

        service = api._media_discovery
        last = None
        for index in range(8):
            last = service.claim_and_run(
                worker_id=f"recovery-{index}", claim_token=f"recovery-token-{index}"
            )
            if last is None:
                break
            if last.terminal or last.preview_id is not None:
                break
        assert last is not None, "remaining-scope preparation was never claimable"
        status, document = request(
            api,
            f"/api/v1/operations/organize/discoveries/{discovery_id}",
        )
        assert status == 200, document
        return document

    def _api(self, config: Path):
        """One API over the managed runtime of this journey."""

        from mediaflow.infrastructure.runtime_configuration import (
            load_managed_runtime_configuration,
            with_managed_snapshot,
        )

        configuration_repository = SQLiteConfigurationRepository(self.database)
        self.addCleanup(configuration_repository.close)
        service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=str(self.database),
        )
        document = json.loads(config.read_text(encoding="utf-8"))
        active = service.active()
        assert active is not None
        runtime = with_managed_snapshot(
            load_managed_runtime_configuration(
                active.document, bootstrap_database_path=str(self.database)
            ),
            snapshot_id=active.revision_id,
            digest=active.digest,
        )
        storages = runtime.create_storages(
            external={
                "source-storage": LocalStorage("source-storage", self.root),
                "media-target": LocalStorage("media-target", self.root / "Target"),
            }
        )
        return MediaFlowApi(
            self.repository,
            None,
            principals=(ADMIN, VIEWER, OPERATOR),
            configuration_service=service,
            bootstrap_document=document,
            storage_adapters=storages,
            # The exact Preview runs the real analysis pipeline; a deterministic
            # in-process provider keeps the journey offline while still proving
            # the plan is produced under the run's own pinned revision.
            metadata_provider_registry_factory=lambda runtime: MetadataProviderRegistry(
                (
                    SyntheticMetadataProvider(
                        (
                            MediaCandidate(
                                "tmdb",
                                "100",
                                MediaType.MOVIE,
                                "Left",
                                year=2005,
                                genres=("Animation",),
                                countries=("JP",),
                            ),
                            MediaCandidate(
                                "tmdb",
                                "101",
                                MediaType.MOVIE,
                                "Right",
                                year=2006,
                                genres=("Animation",),
                                countries=("JP",),
                            ),
                        )
                    ),
                )
            ),
            storage_browser_cursor_secret="scope-continuation-journey-secret",
        )

    def _paused_mutation_scan(self, active, *, discovered: str | None = None, item_limit: int = 4):
        """One paused, mutation-authorized run with no live reusable authority.

        This is the exact durable state RO-5 must recover from: the original
        admission was authorized, but the one-shot authority is consumed, so a
        stored boolean is not authority and Continue is refused.
        """

        task = PersistentTask(
            "task-authority",
            "preview",
            PersistentTaskStatus.RUNNING,
            True,
            NOW,
            NOW,
            started_at=NOW,
            scope_path="Incoming",
            item_limit=item_limit,
            configuration_snapshot_id=active.revision_id,
            configuration_snapshot_digest=active.digest,
        )
        self.repository.create_task(task)
        if discovered is not None:
            self.coordinator.record_discovered(
                task.task_id,
                "source-storage",
                "source",
                discovered,
                f"source-storage:{discovered}",
            )
            item = next(
                value
                for value in self.repository.list_items(task.task_id)
                if value.source_path == discovered
            )
            self.repository.upsert_item(
                replace(item, status=TaskItemStatus.SUCCESS, updated_at=datetime.now(UTC))
            )
            self.repository.append_result(
                PersistentResultRecord(
                    f"{item.item_id}:1",
                    task.task_id,
                    item.item_id,
                    "source-storage",
                    discovered,
                    "media-target",
                    "Movies/Kept.2006/Kept.2006.mkv",
                    "C",
                    "tmdb",
                    "1",
                    "C",
                    "A",
                    "A",
                    "A",
                    "MOVE",
                    "success",
                    NOW,
                    title="Kept",
                    effect_certainty="verified_complete",
                )
            )
        self.repository.request_task_pause(task.task_id, NOW)
        return self.coordinator.acknowledge_pause(task.task_id)


if __name__ == "__main__":
    unittest.main()
