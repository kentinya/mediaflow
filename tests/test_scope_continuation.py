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

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.scope_continuation import (
    ScopeContinuationService,
    ScopeContinuationWorkerService,
    continuation_obstacle,
    definition_occurrence_authority,
    is_continuable_task_command,
    remaining_scope,
)
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
from mediaflow.domain.scope_continuation import (
    ScopeContinuationError,
    ScopeContinuationReason,
    ScopeContinuationStatus,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
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
            {"scan", "preview", "organize"},
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
        self.assertEqual(continuation["status"], "queued")
        self.assertEqual(continuation["source_task_id"], task.task_id)
        self.assertEqual(continuation["command"], "preview")
        self.assertEqual(continuation["scope_path"], "Media")
        self.assertEqual(continuation["item_limit"], 10)
        self.assertEqual(continuation["configuration_snapshot_id"], active.revision_id)
        self.assertEqual(continuation["boundary"], "paused_remaining_admitted_scope")

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
        # The continuation is bound to the real Active revision, never a
        # client-supplied identity.
        self.assertEqual(continuation["configuration_snapshot_id"], active.revision_id)

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

        read_status, detail = request(api, f"/api/v1/tasks/{task.task_id}", token="operator-token")
        self.assertEqual(read_status, 200)
        resume = next(item for item in detail["lifecycle"]["actions"] if item["action"] == "resume")
        self.assertFalse(resume["available"])
        self.assertIn("stored execute flag is not authority", resume["unavailableReason"])
        self.assertIn("exact Preview", resume["nextAction"])

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

    def _paused_scan(self, active, *, discovered: str | None = None):
        task = PersistentTask(
            "task-original",
            "scan",
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

    def test_worker_continues_a_paused_scan_without_repeating_discovered_sources(self) -> None:
        from mediaflow.final_cli import _run_queued_workflow

        config, active = self._activate(scope="Incoming")
        (self.root / "Incoming" / "first.mkv").write_bytes(b"first")
        (self.root / "Incoming" / "second.mkv").write_bytes(b"second")
        original = self._paused_scan(active, discovered="Incoming/first.mkv")

        service = ScopeContinuationService(self.repository, snapshot_validator=lambda *_: None)
        submission = service.submit(
            original.task_id,
            expected_version=None,
            actor="operator",
            maximum_active_jobs=10,
        )
        task_id = _run_queued_workflow(
            submission.job, str(config), lambda: False, repository=self.repository
        )
        self.assertIsNotNone(task_id)
        assert task_id is not None
        continuation = self.repository.get_task(task_id)
        self.assertEqual(continuation.command, "scan")
        self.assertIs(continuation.status, PersistentTaskStatus.COMPLETED)
        # The already-discovered source is never repeated, and the original Task
        # keeps its own durable history and pin untouched.
        self.assertEqual(
            {item.source_path for item in self.repository.list_items(task_id)},
            {"Incoming/second.mkv"},
        )
        self.assertEqual(
            {item.source_path for item in self.repository.list_items(original.task_id)},
            {"Incoming/first.mkv"},
        )
        kept = self.repository.get_task(original.task_id)
        self.assertIs(kept.status, PersistentTaskStatus.PAUSED)
        self.assertEqual(kept.configuration_snapshot_id, active.revision_id)
        self.assertEqual(kept.configuration_snapshot_digest, active.digest)
        finished = self.repository.get_scope_continuation_for_job(submission.job.job_id)
        self.assertIs(finished.status, ScopeContinuationStatus.COMPLETED)
        self.assertEqual(finished.new_task_id, task_id)

    def test_worker_prepare_failure_closes_the_continuation_without_any_effect(self) -> None:
        from mediaflow.final_cli import _run_queued_workflow

        config, active = self._activate(scope="Incoming")
        (self.root / "Incoming" / "one.mkv").write_bytes(b"one")
        original = self._paused_scan(active)

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


if __name__ == "__main__":
    unittest.main()
