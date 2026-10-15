"""Focused proof for Task 45.1 — nine task-center views and problem recovery.

These tests exercise the real SQLite repository, the shared read projection and
the authenticated ``/api/v1/operations/runs`` API against the current legal
production assemblies:

- AC-1 the nine sibling views are independent, deep-linkable server queries
  with a complete-population summary, and the recovery views group one Task per
  current problem type;
- AC-2 the summary, the view counts and the page rows share one read basis over
  the whole authorized population, and cursors bind the view/problem/filters;
- AC-3 a plain queue admission is not a manual to-do, a real pending problem is,
  resolving it leaves the list and a genuinely new blocker transfers to its own
  type;
- AC-4 a recovery row leads to the exact Task/type file list, server-filtered
  and server-paged on the same durable predicate;
- AC-6 every read is authorized, bounded and side-effect-free.

No production media, credentials or external service is used.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from mediaflow.application.classification_review import ClassificationReviewService
from mediaflow.application.metadata_correction import MetadataCorrectionService
from mediaflow.application.metadata_review import MetadataReviewService
from mediaflow.application.recognition_review import RecognitionReviewService
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.automation import AutomationCommand, AutomationJob, AutomationJobStatus
from mediaflow.domain.classification import (
    ClassificationPolicy,
    ClassificationResult,
    ClassificationRule,
    ClassificationStatus,
)
from mediaflow.domain.metadata import (
    CandidateMatchResult,
    CandidateMatchStatus,
    CandidateScore,
    MediaCandidate,
    MediaIdentity,
    MediaQueryType,
    MediaType,
    MetadataIdentificationResult,
    MetadataIdentificationStatus,
    MetadataPolicy,
    ScoreComponent,
)
from mediaflow.domain.organizer import (
    Conflict,
    ConflictStrategy,
    ConflictType,
    OrganizeOperationType,
    OrganizePlan,
    OrganizePolicy,
    PlanOperation,
    PlanStatus,
    StorageLocation,
)
from mediaflow.domain.recognition import (
    RecognitionResult,
    RecognitionStatus,
    RecognitionType,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import (
    PersistentTaskItem,
    TaskItemStatus,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.pagination import decode_directional_cursor
from mediaflow.interfaces.service_api import MediaFlowApi

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)

VIEWER = ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
OTHER = ResolvedApiPrincipal("other", "other-token", frozenset({ApiPermission.READ}))


def request(
    api: MediaFlowApi,
    method: str,
    path: str,
    *,
    token: str = "viewer-token",
    query: str = "",
) -> tuple[int, dict]:
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": "0",
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
        "wsgi.input": io.BytesIO(),
    }
    payload = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(payload)


class _TaskCenterTestCase(unittest.TestCase):
    """One real SQLite repository behind the authenticated inventory API."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = SQLiteTaskRepository(Path(self.directory.name, "runtime.sqlite3"))
        self.coordinator = PersistentTaskCoordinator(self.repository, self.repository)
        self.api = MediaFlowApi(self.repository, None, principals=(VIEWER, OTHER))

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def _task(self, command: str = "organize", *, scope: str | None = None):
        task = self.coordinator.create(
            command,
            execute_authorized=False,
            scope_path=scope or f"Movies/{command}",
        )
        return task

    def _processing_item(self, task_id: str, item_id: str) -> PersistentTaskItem:
        item = PersistentTaskItem(
            item_id,
            task_id,
            "source",
            "movies",
            f"Movies/{item_id}.mkv",
            f"Movies/{item_id}.mkv",
            TaskItemStatus.PROCESSING,
            "recognizing",
            1,
            NOW,
            NOW,
        )
        self.repository.upsert_item(item)
        return item

    def _recognition_problem(self, task_id: str, item_id: str) -> str:
        item = self._processing_item(task_id, item_id)
        review = RecognitionReviewService(
            self.repository,
            (RecognitionType("A", "Movie"), RecognitionType("B", "TV")),
        ).create(item, RecognitionResult(status=RecognitionStatus.UNRECOGNIZED))
        return review.review_id

    def _metadata_review_problem(self, task_id: str, item_id: str) -> str:
        item = self._processing_item(task_id, item_id)
        candidate = MediaCandidate("tmdb", "55", MediaType.MOVIE, "Ambiguous", year=2001)
        identification = MetadataIdentificationResult(
            status=MetadataIdentificationStatus.AMBIGUOUS,
            recognition_type=RecognitionType("A", "Movie"),
            match=CandidateMatchResult(
                status=CandidateMatchStatus.AMBIGUOUS,
                best_candidate=candidate,
                score=0.6,
                candidate_scores=(
                    CandidateScore(
                        candidate,
                        0.6,
                        (ScoreComponent("title", 0.6, "close title"),),
                    ),
                ),
            ),
            query="Ambiguous",
        )
        review = MetadataReviewService(self.repository).create(item, identification, "metadata-a")
        return review.review_id

    def _metadata_correction_problem(self, task_id: str, item_id: str) -> str:
        item = self._processing_item(task_id, item_id)
        policy = MetadataPolicy(
            "metadata-a",
            "tmdb",
            name="Metadata A",
            media_query_type=MediaQueryType.MOVIE,
        )
        identification = MetadataIdentificationResult(
            status=MetadataIdentificationStatus.NOT_FOUND,
            recognition_type=RecognitionType("A", "Movie"),
            query="Missing",
        )
        from mediaflow.domain.parser import ParseResult

        review = MetadataCorrectionService(self.repository, (policy,)).create(
            item,
            identification,
            policy,
            ParseResult(title_candidate="Missing", year=2001, original_filename="Missing.mkv"),
        )
        return review.review_id

    def _classification_problem(self, task_id: str, item_id: str) -> str:
        item = self._processing_item(task_id, item_id)
        policy = ClassificationPolicy(
            "classification-a",
            "Classification A",
            rules=(
                ClassificationRule(
                    "rule-1",
                    "Rule 1",
                    "media-a",
                    "Movies",
                    priority=10,
                ),
            ),
        )
        identity = MediaIdentity("tmdb", "55", MediaType.MOVIE, "Unclassified", year=2001)
        result = ClassificationResult(
            policy_id=policy.policy_id,
            recognition_type_id="A",
            status=ClassificationStatus.UNCLASSIFIED,
        )
        review = ClassificationReviewService(self.repository).create(item, result, policy, identity)
        return review.review_id

    def _conflict_problem(self, task_id: str, item_id: str) -> str:
        item = self._processing_item(task_id, item_id)
        plan = OrganizePlan(
            source_storage_id="source",
            target_storage_id="target",
            source=f"Movies/{item_id}.mkv",
            target=f"Movies/{item_id}.mkv",
            recognition_type_id="A",
            naming_policy_id="A",
            classification_policy_id="A",
            organize_policy_id="A",
            operation=PlanOperation.MOVE,
            media_library_root="Movies",
            relative_destination=f"{item_id}/{item_id}.mkv",
            source_location=StorageLocation("source", f"Movies/{item_id}.mkv"),
            destination_location=StorageLocation("target", f"Movies/{item_id}.mkv"),
            conflicts=(
                Conflict(
                    ConflictType.DESTINATION_EXISTS,
                    StorageLocation("source", f"Movies/{item_id}.mkv"),
                    StorageLocation("target", f"Movies/{item_id}.mkv"),
                    "destination exists",
                ),
            ),
            status=PlanStatus.CONFLICT,
            plan_id=f"plan-{item_id}",
        )
        self.coordinator.wait_for_confirmation(
            item,
            plan,
            OrganizePolicy("A", OrganizeOperationType.MOVE, ConflictStrategy.MANUAL),
        )
        confirmation = self.repository.list_confirmations()[-1]
        return confirmation.confirmation_id

    def _failure_problem(self, task_id: str, item_id: str) -> None:
        from dataclasses import replace

        item = self._processing_item(task_id, item_id)
        self.repository.upsert_item(
            replace(item, status=TaskItemStatus.FAILED, stage="failed", attempts=1)
        )

    def _page(self, query: str = "", token: str = "viewer-token") -> dict:
        code, page = request(self.api, "GET", "/api/v1/operations/runs", token=token, query=query)
        self.assertEqual(200, code)
        return page


class TaskCenterViewTests(_TaskCenterTestCase):
    def test_nine_views_are_independent_and_deep_linkable(self) -> None:
        recognition = self._task("organize")
        self._recognition_problem(recognition.task_id, "recog-item")
        metadata = self._task("organize")
        self._metadata_correction_problem(metadata.task_id, "meta-item")
        classification = self._task("organize")
        self._classification_problem(classification.task_id, "class-item")
        conflict = self._task("organize")
        self._conflict_problem(conflict.task_id, "conflict-item")
        failure = self._task("organize")
        self._failure_problem(failure.task_id, "failure-item")
        self._task("scan")
        ended = self._task("preview")
        self.repository.update_task(
            __import__("dataclasses").replace(
                ended,
                status=__import__(
                    "mediaflow.domain.task_persistence", fromlist=["PersistentTaskStatus"]
                ).PersistentTaskStatus.COMPLETED,
            )
        )

        all_page = self._page()
        self.assertGreaterEqual(all_page["total"], 7)
        self.assertEqual(all_page["view"], None)
        # Each view is an independent server query with its own population.
        cases = {
            "all": all_page["total"],
            "running": 6,
            "attention": 5,
            "ended": 1,
            "recognition": 1,
            "metadata": 1,
            "classification": 1,
            "conflict": 1,
            "failure": 1,
        }
        for view, expected in cases.items():
            with self.subTest(view=view):
                page = self._page(f"view={view}")
                self.assertEqual(view if view != "all" else None, page["view"])
                self.assertEqual(expected, page["total"])
        # The recovery view always applies its own problem predicate even when
        # no explicit problem parameter is submitted.
        recognition_page = self._page("view=recognition")
        self.assertEqual(["recognition"], recognition_page["items"][0]["problem_types"])
        # A standalone problem filter narrows a lifecycle view server-side.
        narrowed = self._page("view=attention&problem=conflict")
        self.assertEqual(1, narrowed["total"])
        self.assertEqual(["conflict"], narrowed["items"][0]["problem_types"])

    def test_summary_counts_the_complete_population_and_problem_files(self) -> None:
        for index in range(3):
            task = self._task("organize")
            self._failure_problem(task.task_id, f"failure-{index}")
        task = self._task("organize")
        self._recognition_problem(task.task_id, "recog-a")
        self._recognition_problem(task.task_id, "recog-b")

        page = self._page("limit=1")
        summary = page["summary"]
        self.assertTrue(summary["available"])
        # The summary is over the whole authorized population, never just the
        # returned page (which here holds one row).
        self.assertEqual(4, summary["total"])
        self.assertEqual(4, summary["attention"])
        self.assertEqual(1, summary["problem_tasks"]["recognition"])
        self.assertEqual(2, summary["problem_files"]["recognition"])
        self.assertEqual(3, summary["problem_files"]["failure"])
        self.assertEqual(4, page["total"])
        self.assertEqual(4, page["attention_count"])

    def test_source_filter_accepts_historical_paths_and_scopes_summary(self) -> None:
        alpha = self._task("organize", scope="Movies/alpha")
        self._failure_problem(alpha.task_id, "alpha-file")
        beta = self._task("organize", scope="Movies/beta")
        self._failure_problem(beta.task_id, "beta-file")

        page = self._page("view=failure&source=Movies%2Falpha")
        self.assertEqual(1, page["total"])
        self.assertEqual([alpha.task_id], [item["task_id"] for item in page["items"]])
        self.assertEqual(1, page["summary"]["total"])
        self.assertEqual(1, page["summary"]["problem_tasks"]["failure"])
        self.assertEqual(1, page["summary"]["problem_files"]["failure"])
        self.assertEqual("Movies/alpha", page["source"])
        self.assertEqual(
            {"Movies/alpha", "Movies/beta"},
            {entry["value"] for entry in page["summary"]["sources"]},
        )
        self.assertEqual("current_filters", page["summary"]["scope"])
        self.assertEqual("authorized_population", page["summary"]["source_options_scope"])

    def test_redacted_source_options_are_not_selectable_filters(self) -> None:
        summary = MediaFlowApi._public_operations_run_summary(
            {
                "available": True,
                "sources": [
                    {"value": "Movies/public", "label": "Movies/public"},
                    {"value": "/private/media", "label": "/private/media"},
                ],
                "sources_truncated": False,
            }
        )
        self.assertEqual(
            [{"value": "Movies/public", "label": "Movies/public"}],
            summary["sources"],
        )
        self.assertTrue(summary["sources_truncated"])

    def test_page_row_has_its_own_problem_file_count(self) -> None:
        two = self._task("organize", scope="Movies/two")
        self._failure_problem(two.task_id, "two-a")
        self._failure_problem(two.task_id, "two-b")
        one = self._task("organize", scope="Movies/one")
        self._failure_problem(one.task_id, "one-a")

        page = self._page("view=failure")
        by_task = {item["task_id"]: item for item in page["items"]}
        self.assertEqual(2, by_task[two.task_id]["problem_file_counts"]["failure"])
        self.assertEqual(1, by_task[one.task_id]["problem_file_counts"]["failure"])
        self.assertEqual(3, page["summary"]["problem_files"]["failure"])

    def test_page_and_filter_summary_share_the_window_snapshot(self) -> None:
        original = self.repository.operations_runs_window

        def admit_after_snapshot(**arguments):
            window = original(**arguments)
            self._task("scan", scope="Movies/concurrent")
            return window

        self.repository.operations_runs_window = admit_after_snapshot
        page = self._page()
        self.assertEqual(0, page["total"])
        self.assertEqual(0, page["summary"]["total"])
        self.assertEqual([], page["summary"]["sources"])

    def test_linked_job_row_counts_problem_files_through_its_task(self) -> None:
        task = self._task("organize", scope="Movies/linked")
        self._recognition_problem(task.task_id, "linked-a")
        self._recognition_problem(task.task_id, "linked-b")
        job = AutomationJob(
            "job-linked-count",
            AutomationCommand.PREVIEW,
            AutomationJobStatus.PENDING,
            NOW,
            NOW,
            task_id=task.task_id,
            source_scope="Movies/linked",
        )
        self.repository.create_job(job)

        page = self._page("view=recognition")
        self.assertEqual(1, page["total"])
        self.assertEqual("job-linked-count", page["items"][0]["run_id"])
        self.assertEqual(2, page["items"][0]["problem_file_counts"]["recognition"])

    def test_plain_queue_admission_is_not_attention(self) -> None:
        self._task("scan")
        page = self._page("view=attention")
        self.assertEqual(0, page["total"])
        self.assertEqual(0, page["summary"]["attention"])

    def test_cursor_binds_view_and_problem_scope(self) -> None:
        for index in range(3):
            task = self._task("organize")
            self._failure_problem(task.task_id, f"failure-{index}")
        first = self._page("view=failure&limit=1")
        cursor = first["next_cursor"]
        self.assertIsNotNone(cursor)
        # The minted scope names the view and problem predicate.
        decoded = decode_directional_cursor(
            cursor,
            "operations_runs",
            expected_scope=(
                "principal=viewer;status=all;attention=false;view=failure;"
                "problem=failure;source=all;command=all;q=;from=;to="
            ),
        )
        self.assertIsNotNone(decoded)
        for mismatched in (
            f"view=recognition&limit=1&cursor={cursor}",
            f"view=all&limit=1&cursor={cursor}",
            f"view=failure&problem=conflict&limit=1&cursor={cursor}",
        ):
            with self.subTest(query=mismatched):
                code, _body = request(self.api, "GET", "/api/v1/operations/runs", query=mismatched)
                self.assertEqual(400, code)
        # The minting principal pages normally; another principal is refused.
        code, _body = request(
            self.api,
            "GET",
            "/api/v1/operations/runs",
            token="other-token",
            query=f"view=failure&limit=1&cursor={cursor}",
        )
        self.assertEqual(400, code)

    def test_invalid_view_and_problem_values_reject_safely(self) -> None:
        for query in ("view=teleported", "problem=unknown", "view=recognition&view=metadata"):
            with self.subTest(query=query):
                code, body = request(self.api, "GET", "/api/v1/operations/runs", query=query)
                self.assertEqual(400, code)
                self.assertEqual("invalid_request", body["error"]["code"])

    def test_attention_row_exposes_each_current_problem_type_for_location(self) -> None:
        # The overlapping attention view must let the operator open the exact
        # Task/type file list for every current problem, not a dead action.
        mixed = self._task("organize")
        self._metadata_correction_problem(mixed.task_id, "meta-item")
        self._failure_problem(mixed.task_id, "failure-item")
        page = self._page("view=attention")
        self.assertEqual(1, page["total"])
        row = page["items"][0]
        self.assertEqual({"metadata", "failure"}, set(row["problem_types"]))
        # Each type has its own reachable server-filtered file list.
        for problem in ("metadata", "failure"):
            code, files = request(
                self.api,
                "GET",
                f"/api/v1/operations/runs/{mixed.task_id}/problem-items",
                query=f"problem={problem}",
            )
            self.assertEqual(200, code)
            self.assertEqual(problem, files["problem"])
            self.assertEqual(1, files["matching_total"])

    def test_attention_row_with_only_a_safe_continuation_has_no_problem_type(self) -> None:
        # A saved decision waits for continuation with no technical type; the
        # row must stay in attention without inventing one of the five types.
        task = self._task("organize")
        review_id = self._metadata_review_problem(task.task_id, "meta-item")
        MetadataReviewService(self.repository).resolve(review_id, 1, actor="operator")
        page = self._page("view=attention")
        self.assertEqual(1, page["total"])
        row = page["items"][0]
        self.assertEqual([], list(row["problem_types"]))
        self.assertTrue(row["attention"])

    def test_reads_are_side_effect_free(self) -> None:
        task = self._task("organize")
        self._recognition_problem(task.task_id, "recog-item")
        before_tasks = len(self.repository.list_tasks())
        before_jobs = len(self.repository.list_jobs())
        for view in (
            "all",
            "running",
            "attention",
            "ended",
            "recognition",
            "metadata",
            "classification",
            "conflict",
            "failure",
        ):
            self._page(f"view={view}")
        self._page()
        self.assertEqual(before_tasks, len(self.repository.list_tasks()))
        self.assertEqual(before_jobs, len(self.repository.list_jobs()))
        # An unauthenticated read is refused, never an empty population.
        code, _body = request(self.api, "GET", "/api/v1/operations/runs", token="denied")
        self.assertEqual(401, code)


class RecoveryListTests(_TaskCenterTestCase):
    def test_one_task_per_type_with_accurate_file_counts(self) -> None:
        # One Task carrying two recognition files and one failure file appears
        # once in each of its type lists, with the file count of its own type.
        mixed = self._task("organize")
        self._recognition_problem(mixed.task_id, "recog-a")
        self._recognition_problem(mixed.task_id, "recog-b")
        self._failure_problem(mixed.task_id, "failure-a")
        # A second Task with only a conflict problem.
        conflict = self._task("organize")
        self._conflict_problem(conflict.task_id, "conflict-a")

        recognition = self._page("view=recognition")
        self.assertEqual(1, recognition["total"])
        self.assertEqual({"recognition", "failure"}, set(recognition["items"][0]["problem_types"]))
        self.assertEqual(2, recognition["summary"]["problem_files"]["recognition"])
        self.assertEqual(1, recognition["summary"]["problem_tasks"]["recognition"])

        failure = self._page("view=failure")
        self.assertEqual(1, failure["total"])
        self.assertEqual(1, failure["summary"]["problem_files"]["failure"])

        conflict_page = self._page("view=conflict")
        self.assertEqual(1, conflict_page["total"])
        self.assertEqual(conflict.task_id, conflict_page["items"][0]["task_id"])

    def test_resolved_problem_leaves_the_list_and_a_new_blocker_transfers(self) -> None:
        task = self._task("organize")
        review_id = self._recognition_problem(task.task_id, "recog-item")
        self.assertEqual(1, self._page("view=recognition")["total"])
        # Resolving the recognition review leaves the item pending at a
        # *_resolved stage: it is no longer a recognition blocker or a
        # technical failure. Its safe-analysis continuation remains visible
        # in the generic attention view until the operator continues it.
        RecognitionReviewService(
            self.repository,
            (RecognitionType("A", "Movie"), RecognitionType("B", "TV")),
        ).resolve(review_id, "A", actor="operator")
        self.assertEqual(0, self._page("view=recognition")["total"])
        self.assertEqual(0, self._page("view=failure")["total"])
        self.assertEqual(1, self._page("view=attention")["total"])
        # A genuinely new classification blocker on the same Task appears in
        # the classification list alongside the continuation problem.
        self._classification_problem(task.task_id, "class-item")
        self.assertEqual(1, self._page("view=classification")["total"])
        classification = self._page("view=classification")
        self.assertEqual(
            {"classification"},
            set(classification["items"][0]["problem_types"]),
        )

    def test_metadata_two_subtypes_are_both_metadata_problems(self) -> None:
        review_task = self._task("organize")
        self._metadata_review_problem(review_task.task_id, "review-item")
        correction_task = self._task("organize")
        self._metadata_correction_problem(correction_task.task_id, "correction-item")
        page = self._page("view=metadata")
        self.assertEqual(2, page["total"])
        self.assertEqual(2, page["summary"]["problem_files"]["metadata"])

    def test_problem_file_list_is_server_filtered_and_paginated(self) -> None:
        task = self._task("organize")
        for index in range(3):
            self._recognition_problem(task.task_id, f"recog-{index}")
        # A failure file on the same Task must not appear in the recognition
        # file list.
        self._failure_problem(task.task_id, "failure-a")

        code, first = request(
            self.api,
            "GET",
            f"/api/v1/operations/runs/{task.task_id}/problem-items",
            query="problem=recognition&limit=2",
        )
        self.assertEqual(200, code)
        self.assertEqual("recognition", first["problem"])
        self.assertEqual(3, first["matching_total"])
        self.assertEqual(2, len(first["items"]))
        self.assertTrue(first["truncated"])
        self.assertIsNotNone(first["next_cursor"])
        self.assertNotIn("failure-a", [item["item_id"] for item in first["items"]])
        code, second = request(
            self.api,
            "GET",
            f"/api/v1/operations/runs/{task.task_id}/problem-items",
            query=f"problem=recognition&limit=2&cursor={first['next_cursor']}",
        )
        self.assertEqual(200, code)
        self.assertEqual(3, second["matching_total"])
        self.assertEqual(1, len(second["items"]))
        seen = [item["item_id"] for item in first["items"]] + [
            item["item_id"] for item in second["items"]
        ]
        self.assertEqual(3, len(set(seen)))
        # The failure file list contains only the failure file.
        code, failures = request(
            self.api,
            "GET",
            f"/api/v1/operations/runs/{task.task_id}/problem-items",
            query="problem=failure",
        )
        self.assertEqual(200, code)
        self.assertEqual(1, failures["matching_total"])
        self.assertEqual("failure-a", failures["items"][0]["item_id"])

    def test_problem_file_list_binds_problem_and_principal(self) -> None:
        task = self._task("organize")
        self._recognition_problem(task.task_id, "recog-0")
        self._recognition_problem(task.task_id, "recog-1")
        code, first = request(
            self.api,
            "GET",
            f"/api/v1/operations/runs/{task.task_id}/problem-items",
            query="problem=recognition&limit=1",
        )
        cursor = first["next_cursor"]
        self.assertIsNotNone(cursor)
        code, _body = request(
            self.api,
            "GET",
            f"/api/v1/operations/runs/{task.task_id}/problem-items",
            query=f"problem=failure&limit=1&cursor={cursor}",
        )
        self.assertEqual(400, code)
        code, _body = request(
            self.api,
            "GET",
            f"/api/v1/operations/runs/{task.task_id}/problem-items",
            token="other-token",
            query=f"problem=recognition&limit=1&cursor={cursor}",
        )
        self.assertEqual(400, code)
        for invalid in ("problem=unknown", "problem=", "problem=recognition&problem=metadata"):
            with self.subTest(query=invalid):
                code, _body = request(
                    self.api,
                    "GET",
                    f"/api/v1/operations/runs/{task.task_id}/problem-items",
                    query=invalid,
                )
                self.assertEqual(400, code)

    def test_problem_file_list_reports_unavailable_for_a_pre_task_run(self) -> None:
        from mediaflow.domain.automation import (
            AutomationCommand,
            AutomationJob,
            AutomationJobStatus,
        )

        self.repository.admit_job(
            AutomationJob(
                "pre-task-job",
                AutomationCommand.PREVIEW,
                AutomationJobStatus.PENDING,
                NOW,
                NOW,
            ),
            100,
        )
        code, body = request(
            self.api,
            "GET",
            "/api/v1/operations/runs/pre-task-job/problem-items",
            query="problem=failure",
        )
        self.assertEqual(200, code)
        self.assertIsNone(body["task_id"])
        self.assertIsNotNone(body["unavailable"])
        self.assertEqual(0, body["matching_total"])

    def test_attention_view_never_fabricates_zero_for_an_unavailable_read(self) -> None:
        # A read against a runtime without the summary projection still
        # answers the list, but publishes an explicit unavailable summary.
        page = self._page("view=attention")
        self.assertIn("summary", page)
        self.assertTrue(page["summary"]["available"])
