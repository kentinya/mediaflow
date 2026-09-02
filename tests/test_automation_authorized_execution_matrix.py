from __future__ import annotations

import io
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from mediaflow.application.automation import IntervalScheduler
from mediaflow.application.automation_definition_occurrence import (
    AutomationDefinitionOccurrenceService,
)
from mediaflow.application.failure_explanation import (
    classify_failure,
    sanitize_execution_errors,
)
from mediaflow.application.media_organizer import MediaOrganizerItemResult
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.automation import (
    AutomationDefinitionOccurrence,
    AutomationTaskDefinition,
    AutomationTaskRunMode,
    SchedulerConfigurationSnapshot,
)
from mediaflow.domain.failure import MAX_FAILURE_ERROR_LENGTH
from mediaflow.domain.organizer import (
    AttachmentPlan,
    AttachmentType,
    ExecutionEffectCertainty,
    ExecutionResult,
    ExecutionStatus,
    OrganizeOperationType,
    OrganizePlan,
    PlanOperation,
    PlanStatus,
    StorageLocation,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.storage import StorageError, StorageErrorCode
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _matrix_plan(
    operation: PlanOperation,
    *,
    source_storage_id: str = "local",
    target_storage_id: str = "local",
    link_operation: OrganizeOperationType | None = None,
    attachment_plans: tuple[AttachmentPlan, ...] = (),
) -> OrganizePlan:
    source = StorageLocation(source_storage_id, "Incoming/Movie.mkv")
    target = StorageLocation(target_storage_id, "Movies/Movie/Movie.mkv")
    return OrganizePlan(
        source_storage_id,
        target_storage_id,
        source.path,
        target.path,
        "C",
        "naming-a",
        "classification-a",
        "organize-matrix",
        operation=operation,
        status=PlanStatus.READY,
        plan_id=f"matrix-{operation.value}-{link_operation or 'primary'}",
        media_library_root="Movies",
        relative_destination="Movie/Movie.mkv",
        source_location=source,
        destination_location=target,
        link_operation=link_operation,
        attachment_plans=attachment_plans,
    )


def _tree(root: Path) -> tuple[str, ...]:
    return tuple(sorted(str(path.relative_to(root)) for path in root.rglob("*")))


class AuthorizedFailureExplanationTests(unittest.TestCase):
    def test_execution_boundary_categories_are_distinguishable_and_bounded(self) -> None:
        cases = (
            ("unsupported_capability", "operation HARD_LINK is not executable"),
            ("denied_capability", StorageErrorCode.PERMISSION_DENIED),
            ("destination_collision", "destination already exists"),
            ("attachment_collision", "attachment destination already exists: private/path.srt"),
            (
                "invalid_destination",
                "plan destination does not match MediaLibrary root and relative path",
            ),
            ("storage_failure", StorageErrorCode.CONNECTION_LOST),
            ("provider_failure", "provider request failed"),
        )
        explanations = []
        for category, value in cases:
            error = (
                StorageError(value, "move", "/private/source.mkv", "private token=secret")
                if isinstance(value, StorageErrorCode)
                else value
            )
            explanation = classify_failure(error)
            explanations.append(explanation)
            self.assertEqual(explanation.category, category)
            self.assertLessEqual(len(explanation.encode()), MAX_FAILURE_ERROR_LENGTH)
            self.assertNotIn("private", explanation.encode())
            self.assertNotIn("secret", explanation.encode())
            self.assertTrue(explanation.durable_state)
            self.assertTrue(explanation.next_action)
        self.assertEqual(len({value.category for value in explanations}), len(cases))

    def test_unattended_authority_execution_evidence_is_stable_and_bounded(self) -> None:
        cases = (
            (
                ExecutionResult(
                    ExecutionStatus.FAILED,
                    PlanOperation.MOVE,
                    "source",
                    "target",
                    errors=("unattended authority refused before CREATE_DIRECTORY",),
                    effect_certainty=ExecutionEffectCertainty.NONE,
                ),
                True,
            ),
            (
                ExecutionResult(
                    ExecutionStatus.PARTIAL,
                    PlanOperation.MOVE,
                    "source",
                    "target",
                    completed_operations=("MOVE",),
                    errors=("unattended authority refused before CLEANUP_DELETE_DIRECTORY",),
                    effect_certainty=ExecutionEffectCertainty.VERIFIED_COMPLETE,
                ),
                False,
            ),
            (
                ExecutionResult(
                    ExecutionStatus.PARTIAL,
                    PlanOperation.MOVE,
                    "source",
                    "target",
                    completed_operations=("COPY",),
                    errors=("unattended authority refused before ROLLBACK:DELETE_TARGET",),
                    effect_certainty=ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED,
                    uncertain_effects=("mutation_outcome",),
                ),
                False,
            ),
        )
        for execution, retry_safe in cases:
            with self.subTest(status=execution.status.value):
                explanation = classify_failure(execution=execution)
                self.assertEqual(explanation.category, "unattended_authority")
                self.assertEqual(explanation.retry_safe, retry_safe)
                self.assertNotIn("CREATE_DIRECTORY", explanation.message)
                self.assertNotIn("private", explanation.encode())
                sanitized = sanitize_execution_errors(execution, explanation)
                self.assertEqual(sanitized.errors, (explanation.message,))
                self.assertLessEqual(len(explanation.encode()), MAX_FAILURE_ERROR_LENGTH)

    def test_partial_and_uncertain_execution_preserve_effect_boundary(self) -> None:
        partial = ExecutionResult(
            ExecutionStatus.PARTIAL,
            PlanOperation.MOVE,
            "source",
            "target",
            completed_operations=("MOVE",),
            errors=("storage adapter leaked private endpoint",),
            effect_certainty=ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED,
            uncertain_effects=("mutation_outcome",),
        )
        explanation = classify_failure(execution=partial)
        self.assertEqual(explanation.category, "uncertain_effect")
        self.assertFalse(explanation.retry_safe)
        sanitized = sanitize_execution_errors(partial, explanation)
        self.assertNotIn("private endpoint", json.dumps(sanitized.errors))
        self.assertNotEqual(sanitized.errors, ("workflow execution failed",))


class AuthorizedOperationMatrixTests(unittest.TestCase):
    def test_each_configured_operation_executes_with_attachments_without_substitution(self) -> None:
        cases = (
            (PlanOperation.MOVE, None, False, False),
            (PlanOperation.COPY, None, True, False),
            (PlanOperation.LINK, OrganizeOperationType.HARD_LINK, True, False),
            (PlanOperation.LINK, OrganizeOperationType.SOFT_LINK, True, True),
        )
        for operation, link_operation, source_remains, is_symlink in cases:
            with (
                self.subTest(operation=operation, link_operation=link_operation),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                (root / "Incoming").mkdir()
                (root / "Incoming/Movie.mkv").write_bytes(b"video")
                (root / "Incoming/Movie.en.srt").write_bytes(b"subtitle")
                storage = LocalStorage("local", root)
                attachment = AttachmentPlan(
                    StorageLocation("local", "Incoming/Movie.en.srt"),
                    StorageLocation("local", "Movies/Movie/Movie.en.srt"),
                    AttachmentType.SUBTITLE,
                    operation,
                    ".en",
                )
                plan = _matrix_plan(
                    operation,
                    link_operation=link_operation,
                    attachment_plans=(attachment,),
                )
                result = OrganizerExecutor().execute(plan, {"local": storage}, execute=True)
                self.assertEqual(result.status, ExecutionStatus.SUCCESS, result.errors)
                self.assertEqual(result.completed_operations[-1], operation.value)
                primary = root / "Movies/Movie/Movie.mkv"
                subtitle = root / "Movies/Movie/Movie.en.srt"
                self.assertEqual(primary.read_bytes(), b"video")
                self.assertEqual(subtitle.read_bytes(), b"subtitle")
                self.assertEqual((root / "Incoming/Movie.mkv").exists(), source_remains)
                self.assertEqual((root / "Incoming/Movie.en.srt").exists(), source_remains)
                self.assertEqual(primary.is_symlink(), is_symlink)
                self.assertEqual(subtitle.is_symlink(), is_symlink)
                if link_operation is OrganizeOperationType.HARD_LINK:
                    self.assertEqual(
                        primary.stat().st_ino,
                        (root / "Incoming/Movie.mkv").stat().st_ino,
                    )
                    self.assertEqual(
                        subtitle.stat().st_ino,
                        (root / "Incoming/Movie.en.srt").stat().st_ino,
                    )
                expected = {
                    "Incoming",
                    "Movies",
                    "Movies/Movie",
                    "Movies/Movie/Movie.mkv",
                    "Movies/Movie/Movie.en.srt",
                }
                if source_remains:
                    expected.update({"Incoming/Movie.mkv", "Incoming/Movie.en.srt"})
                self.assertEqual(set(_tree(root)), expected)

    def test_unsupported_and_denied_capabilities_fail_before_mutation(self) -> None:
        class UnsupportedStorage(LocalStorage):
            @property
            def capabilities(self):
                from mediaflow.domain.storage import StorageCapabilities

                return StorageCapabilities()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Incoming").mkdir()
            (root / "Incoming/Movie.mkv").write_bytes(b"video")
            unsupported = UnsupportedStorage("local", root)
            plan = _matrix_plan(
                PlanOperation.LINK,
                link_operation=OrganizeOperationType.HARD_LINK,
            )
            result = OrganizerExecutor().execute(plan, {"local": unsupported}, execute=True)
            self.assertEqual(result.status, ExecutionStatus.FAILED)
            self.assertEqual(classify_failure(execution=result).category, "unsupported_capability")
            self.assertEqual(_tree(root), ("Incoming", "Incoming/Movie.mkv"))

            denied = LocalStorage("local", root, read_only=True)
            move_result = OrganizerExecutor().execute(
                replace(plan, operation=PlanOperation.MOVE, link_operation=None),
                {"local": denied},
                execute=True,
            )
            self.assertEqual(move_result.status, ExecutionStatus.FAILED)
            self.assertEqual(classify_failure(execution=move_result).category, "denied_capability")
            self.assertEqual(_tree(root), ("Incoming", "Incoming/Movie.mkv"))

    def test_cross_storage_link_and_attachment_collision_are_explicit_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root, target_root = root / "source", root / "target"
            (source_root / "Incoming").mkdir(parents=True)
            target_root.mkdir()
            (source_root / "Incoming/Movie.mkv").write_bytes(b"video")
            source = LocalStorage("source", source_root)
            target = LocalStorage("target", target_root)
            link_plan = _matrix_plan(
                PlanOperation.LINK,
                source_storage_id="source",
                target_storage_id="target",
                link_operation=OrganizeOperationType.HARD_LINK,
            )
            result = OrganizerExecutor().execute(
                link_plan,
                {"source": source, "target": target},
                execute=True,
            )
            self.assertEqual(result.errors, ("cross-storage LINK is not supported",))
            self.assertEqual(classify_failure(execution=result).category, "unsupported_capability")
            self.assertEqual(_tree(source_root), ("Incoming", "Incoming/Movie.mkv"))
            self.assertEqual(_tree(target_root), ())

            (source_root / "Incoming/Movie.en.srt").write_bytes(b"subtitle")
            (target_root / "Movies/Movie").mkdir(parents=True)
            (target_root / "Movies/Movie/Movie.en.srt").write_bytes(b"existing")
            collision_plan = _matrix_plan(
                PlanOperation.MOVE,
                attachment_plans=(
                    AttachmentPlan(
                        StorageLocation("source", "Incoming/Movie.en.srt"),
                        StorageLocation("target", "Movies/Movie/Movie.en.srt"),
                        AttachmentType.SUBTITLE,
                        PlanOperation.MOVE,
                        ".en",
                    ),
                ),
                source_storage_id="source",
                target_storage_id="target",
            )
            collision = OrganizerExecutor().execute(
                collision_plan,
                {"source": source, "target": target},
                execute=True,
            )
            self.assertEqual(collision.status, ExecutionStatus.FAILED)
            self.assertEqual(
                classify_failure(execution=collision).category,
                "attachment_collision",
            )
            self.assertFalse((target_root / "Movies/Movie/Movie.mkv").exists())
            self.assertEqual((target_root / "Movies/Movie/Movie.en.srt").read_bytes(), b"existing")

    def test_partial_failure_is_durable_and_refuses_automatic_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                coordinator = PersistentTaskCoordinator(repository, repository)
                task = coordinator.create("automatic-organization", execute_authorized=True)
                item = PersistentTaskItem(
                    "partial-item",
                    task.task_id,
                    "source",
                    "resource",
                    "Incoming/Movie.mkv",
                    "source:Incoming/Movie.mkv",
                    TaskItemStatus.PROCESSING,
                    "pipeline",
                    1,
                    NOW,
                    NOW,
                )
                repository.upsert_item(item)
                execution = ExecutionResult(
                    ExecutionStatus.PARTIAL,
                    PlanOperation.MOVE,
                    item.source_path,
                    "Movies/Movie/Movie.mkv",
                    completed_operations=("MOVE",),
                    errors=("adapter private endpoint leaked",),
                    effect_certainty=ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED,
                    uncertain_effects=("mutation_outcome",),
                )
                failure = classify_failure(execution=execution)
                coordinator.complete_item(
                    item,
                    MediaOrganizerItemResult(
                        item.source_path,
                        plan=_matrix_plan(PlanOperation.MOVE),
                        execution=execution,
                        error=failure.message,
                        failure=failure,
                    ),
                )
                persisted = repository.get_item(item.item_id)
                self.assertIsNotNone(persisted)
                self.assertEqual(persisted.status, TaskItemStatus.PARTIAL)
                self.assertTrue(persisted.error.startswith("mediaflow-failure-v1:"))
                result = repository.list_results_for_item(item.item_id)[0]
                self.assertTrue(result.error.startswith("mediaflow-failure-v1:"))
                checkpoint = ProcessingCheckpointService(repository).get(item.item_id)
                self.assertEqual(checkpoint.failure.category, "uncertain_effect")
                self.assertEqual(checkpoint.permitted_action_ids, ("investigate",))
                self.assertNotIn("retry", checkpoint.permitted_action_ids)


class AuthorizedOccurrenceProjectionTests(unittest.TestCase):
    @staticmethod
    def _item(task_id: str, item_id: str, status: TaskItemStatus, error: str | None = None):
        return PersistentTaskItem(
            item_id,
            task_id,
            "source",
            "resource",
            f"Media/incoming/{item_id}.mkv",
            f"source:Media/incoming/{item_id}.mkv",
            status,
            "failed" if status in {TaskItemStatus.FAILED, TaskItemStatus.PARTIAL} else "completed",
            1,
            NOW,
            NOW,
            error=error,
        )

    @staticmethod
    def _result(task_id: str, item_id: str, error: str):
        return PersistentResultRecord(
            f"result-{item_id}",
            task_id,
            item_id,
            "source",
            f"Media/incoming/{item_id}.mkv",
            "target",
            f"Movies/{item_id}.mkv",
            "C",
            "tmdb",
            "123",
            "metadata-c",
            "naming-a",
            "classification-a",
            "organize-move",
            "MOVE",
            TaskItemStatus.FAILED.value,
            NOW,
            error=error,
            retry_category="storage_failure",
        )

    def test_occurrence_summary_counts_statuses_caps_attention_and_reloads(self) -> None:
        explanation = classify_failure("storage operation failed")
        encoded = explanation.encode()
        statuses = (
            TaskItemStatus.PENDING,
            TaskItemStatus.PROCESSING,
            TaskItemStatus.DRY_RUN,
            TaskItemStatus.SUCCESS,
            TaskItemStatus.PARTIAL,
            TaskItemStatus.SKIPPED,
            TaskItemStatus.CANCELLED,
            TaskItemStatus.WAITING_CONFIRM,
            TaskItemStatus.WAITING_RECOGNITION,
            TaskItemStatus.WAITING_METADATA,
            TaskItemStatus.WAITING_METADATA_CORRECTION,
            TaskItemStatus.WAITING_CLASSIFICATION,
            TaskItemStatus.PAUSED,
            TaskItemStatus.IGNORED,
        )
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                repository.create_task(
                    PersistentTask(
                        "task-summary",
                        "automatic-organization",
                        PersistentTaskStatus.PARTIAL_SUCCESS,
                        True,
                        NOW,
                        NOW,
                        item_limit=4,
                    )
                )
                for index, status in enumerate(statuses):
                    repository.upsert_item(self._item("task-summary", f"status-{index}", status))
                unchanged = self._item("task-summary", "unchanged", TaskItemStatus.SKIPPED)
                repository.upsert_item(unchanged)
                repository.append_result(
                    PersistentResultRecord(
                        "result-unchanged",
                        "task-summary",
                        "unchanged",
                        "source",
                        "Media/incoming/unchanged.mkv",
                        "target",
                        "Movies/unchanged.mkv",
                        "C",
                        "tmdb",
                        "123",
                        "metadata-c",
                        "naming-a",
                        "classification-a",
                        "organize-move",
                        "NOOP",
                        TaskItemStatus.SKIPPED.value,
                        NOW,
                    )
                )
                for index in range(40):
                    item_id = f"failed-{index}"
                    repository.upsert_item(
                        self._item("task-summary", item_id, TaskItemStatus.FAILED, encoded)
                    )
                    repository.append_result(self._result("task-summary", item_id, encoded))

                occurrence = AutomationDefinitionOccurrence(
                    "occ-summary",
                    "definition-summary",
                    NOW,
                    NOW,
                    "job-summary",
                    "a" * 64,
                    1,
                    "revision-summary",
                    1,
                    "b" * 64,
                    AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
                    "resource",
                    "Media/incoming",
                    4,
                    task_id="task-summary",
                )
                checkpoints = ProcessingCheckpointService(repository)
                projection = AutomationDefinitionOccurrenceService(repository)
                projection.attach_checkpoint_service(checkpoints)
                trace: list[str] = []
                repository._connection.set_trace_callback(trace.append)
                value = projection.project_occurrences((occurrence,))[0]
                repository._connection.set_trace_callback(None)
                summary = value["outcomeSummary"]
                self.assertEqual(summary["counts"]["failed"], 40)
                self.assertEqual(summary["counts"]["waiting_confirm"], 1)
                self.assertEqual(summary["counts"]["unchanged"], 1)
                self.assertTrue(summary["boundReached"])
                self.assertIsNone(summary["scopeExhausted"])
                self.assertEqual(len(summary["attention"]), 32)
                self.assertTrue(summary["moreAttention"])
                failed_attention = next(
                    value for value in summary["attention"] if value["status"] == "failed"
                )
                self.assertEqual(
                    failed_attention["failureExplanation"]["category"], "storage_failure"
                )
                self.assertTrue(failed_attention["nextAction"])
                self.assertLessEqual(
                    sum(statement.lstrip().upper().startswith("SELECT") for statement in trace),
                    20,
                )
                write_prefixes = (
                    "INSERT",
                    "UPDATE",
                    "DELETE",
                    "REPLACE",
                    "CREATE",
                    "DROP",
                    "ALTER",
                )
                self.assertFalse(
                    any(
                        statement.lstrip().upper().startswith(write_prefixes) for statement in trace
                    ),
                    trace,
                )
                self.assertLessEqual(len(json.dumps(value, ensure_ascii=False)), 200_000)
                self.assertNotIn("private", json.dumps(value))

                detail = projection.project_definition(
                    {"id": "definition-summary", "name": "definition-summary", "enabled": True},
                    _state=None,
                    _latest=occurrence,
                )
                self.assertEqual(detail["outcomeSummary"], value["outcomeSummary"])
                self.assertEqual(detail["occurrence"]["outcomeSummary"], value["outcomeSummary"])

    def test_api_definition_detail_and_occurrence_routes_share_summary(self) -> None:
        definition = AutomationTaskDefinition(
            "definition-summary",
            "definition-summary",
            "resource",
            "Media/incoming",
            AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
            interval_seconds=60,
            item_limit=4,
            enabled=True,
        )
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                repository.create_task(
                    PersistentTask(
                        "task-api-summary",
                        "automatic-organization",
                        PersistentTaskStatus.PARTIAL_SUCCESS,
                        True,
                        NOW,
                        NOW,
                        item_limit=4,
                    )
                )
                repository.upsert_item(
                    self._item(
                        "task-api-summary",
                        "api-failed",
                        TaskItemStatus.FAILED,
                        classify_failure("storage operation failed").encode(),
                    )
                )
                snapshot = SchedulerConfigurationSnapshot(
                    "revision-summary",
                    "b" * 64,
                    (),
                    1,
                    (definition,),
                    1,
                    ("resource",),
                    ("resource",),
                )
                emitted = IntervalScheduler(
                    repository,
                    (),
                    configuration_snapshot_resolver=lambda: snapshot,
                    automation_task_definitions=(definition,),
                ).tick(NOW)
                self.assertEqual(len(emitted), 1)
                repository._connection.execute(
                    "UPDATE automation_jobs SET task_id=? WHERE job_id=?",
                    ("task-api-summary", emitted[0].job_id),
                )
                repository._connection.commit()
                active = SimpleNamespace(
                    revision_id="revision-summary",
                    version=1,
                    revision_sequence=1,
                    digest="b" * 64,
                )
                active.summary = lambda: {
                    "revisionId": active.revision_id,
                    "version": active.version,
                    "revisionSequence": active.revision_sequence,
                    "digest": active.digest,
                }
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal(
                            "viewer", "viewer-token", frozenset({ApiPermission.READ})
                        ),
                    ),
                )
                api._configuration_service = SimpleNamespace(active=lambda: active)
                api._configuration_objects = SimpleNamespace(
                    revision_detail=lambda _revision_id: {
                        "objects": {"automationTaskDefinitions": [definition.document()]}
                    }
                )
                before_read_only_state = (
                    tuple(task.task_id for task in repository.list_tasks()),
                    tuple(job.job_id for job in repository.list_jobs()),
                    tuple(
                        grant.grant_id for grant in repository.list_unattended_execution_grants()
                    ),
                )

                def request(
                    path: str,
                    query: str = "",
                    *,
                    api_client=api,
                    token: str = "viewer-token",
                ):
                    statuses: list[str] = []
                    environ = {
                        "REQUEST_METHOD": "GET",
                        "PATH_INFO": path,
                        "QUERY_STRING": query,
                        "CONTENT_LENGTH": "0",
                        "wsgi.input": io.BytesIO(),
                        "HTTP_AUTHORIZATION": f"Bearer {token}",
                    }
                    body = b"".join(
                        api_client(environ, lambda status, _headers: statuses.append(status))
                    )
                    return int(statuses[0].split()[0]), json.loads(body)

                api_trace: list[str] = []
                repository._connection.set_trace_callback(api_trace.append)
                status, listing = request("/api/v1/automation/task-definitions")
                self.assertEqual(status, 200, listing)
                status, detail = request("/api/v1/automation/task-definitions/definition-summary")
                self.assertEqual(status, 200, detail)
                status, occurrences = request(
                    "/api/v1/automation/task-definitions/definition-summary/occurrences",
                    "limit=10",
                )
                self.assertEqual(status, 200, occurrences)
                status, task_history = request(
                    "/api/v1/tasks/task-api-summary",
                    "itemLimit=10&resultLimit=10",
                )
                self.assertEqual(status, 200, task_history)
                status, checkpoint_history = request(
                    "/api/v1/tasks/task-api-summary/items/api-failed"
                )
                self.assertEqual(status, 200, checkpoint_history)
                status, refreshed_detail = request(
                    "/api/v1/automation/task-definitions/definition-summary"
                )
                self.assertEqual(status, 200, refreshed_detail)
                status, refreshed_occurrences = request(
                    "/api/v1/automation/task-definitions/definition-summary/occurrences",
                    "limit=10",
                )
                self.assertEqual(status, 200, refreshed_occurrences)
                status, refreshed_task_history = request(
                    "/api/v1/tasks/task-api-summary",
                    "itemLimit=10&resultLimit=10",
                )
                self.assertEqual(status, 200, refreshed_task_history)
                status, refreshed_checkpoint_history = request(
                    "/api/v1/tasks/task-api-summary/items/api-failed"
                )
                self.assertEqual(status, 200, refreshed_checkpoint_history)
                repository._connection.set_trace_callback(None)
                write_prefixes = (
                    "INSERT",
                    "UPDATE",
                    "DELETE",
                    "REPLACE",
                    "CREATE",
                    "DROP",
                    "ALTER",
                )
                self.assertFalse(
                    any(
                        statement.lstrip().upper().startswith(write_prefixes)
                        for statement in api_trace
                    ),
                    api_trace,
                )
                after_read_only_state = (
                    tuple(task.task_id for task in repository.list_tasks()),
                    tuple(job.job_id for job in repository.list_jobs()),
                    tuple(
                        grant.grant_id for grant in repository.list_unattended_execution_grants()
                    ),
                )
                self.assertEqual(after_read_only_state, before_read_only_state)
                list_summary = listing["items"][0]["outcomeSummary"]
                self.assertEqual(detail["definition"]["outcomeSummary"], list_summary)
                self.assertEqual(occurrences["items"][0]["outcomeSummary"], list_summary)
                self.assertEqual(refreshed_detail["definition"]["outcomeSummary"], list_summary)
                self.assertEqual(refreshed_occurrences["items"][0]["outcomeSummary"], list_summary)
                self.assertEqual(list_summary["counts"]["failed"], 1)
                self.assertEqual(
                    list_summary["attention"][0]["failureExplanation"]["category"],
                    "storage_failure",
                )

                denied_api = MediaFlowApi(
                    repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal(
                            "cancel-only",
                            "cancel-only-token",
                            frozenset({ApiPermission.CANCEL_JOB}),
                        ),
                    ),
                )
                denied_api._configuration_service = api._configuration_service
                denied_api._configuration_objects = api._configuration_objects
                for path, query in (
                    ("/api/v1/automation/task-definitions/definition-summary", ""),
                    (
                        "/api/v1/automation/task-definitions/definition-summary/occurrences",
                        "limit=10",
                    ),
                ):
                    with self.subTest(path=path):
                        status, denied = request(
                            path,
                            query,
                            api_client=denied_api,
                            token="cancel-only-token",
                        )
                        self.assertEqual(status, 403, denied)
                        self.assertEqual(denied["error"]["code"], "forbidden")
                        denied_text = json.dumps(denied, ensure_ascii=False)
                        self.assertNotIn("outcomeSummary", denied_text)
                        self.assertNotIn("failureExplanation", denied_text)


if __name__ == "__main__":
    unittest.main()
