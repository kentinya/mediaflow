"""Focused proof for Task 46.4 — the organizing-only Task Center (RO-4).

These tests exercise the real SQLite repository, the shared read projection and
the authenticated ``/api/v1/operations/runs`` API against the current legal
production assemblies:

- AC-1 the eight sibling views are independent, deep-linkable server queries
  with a complete-population summary, and the four recovery views group one
  Task per current *business* problem type;
- AC-2 the summary, the view counts and the page rows share one read basis over
  the whole authorized organizing population, and cursors bind the
  view/problem/filters;
- AC-3 a plain queue admission is not a manual to-do, a real pending problem is,
  resolving it leaves the list and a genuinely new blocker transfers to its own
  type;
- AC-4 a recovery row leads to the exact Task/type file list, server-filtered
  and server-paged on the same durable predicate;
- AC-6 every read is authorized, bounded and side-effect-free.

Task 46.4 removed the former fifth "failure recovery" view: a technical failure
is read-only history in All/Ended, never a problem type, a pending-task count or
a recovery entry.  The tests below assert that positively instead of asserting
the retired five-type shape.

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

    def _task(
        self,
        command: str = "organize",
        *,
        scope: str | None = None,
        execute_authorized: bool = True,
    ):
        # An admitted organizing Task always keeps its real execution intent:
        # a Files admission, a confirmed manual execution, an Automation
        # occurrence or a retry that keeps the original authority.  The Task
        # Center membership rule reads exactly that persisted admission, so a
        # standalone analysis-only DryRun (``execute_authorized=False``) is the
        # negative case the population tests seed explicitly.
        task = self.coordinator.create(
            command,
            execute_authorized=execute_authorized,
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

    def _processing_item_as_waiting_metadata(self, task_id: str, item_id: str) -> None:
        """One item genuinely blocked on a live metadata decision."""

        from dataclasses import replace

        item = self._processing_item(task_id, item_id)
        self.repository.upsert_item(
            replace(
                item,
                status=TaskItemStatus.WAITING_METADATA,
                stage="waiting_metadata",
                attempts=1,
            )
        )

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
        """One *technical* (non-business) failed item.

        A technical failure is real durable history, but it is deliberately not
        one of the four Task Center problem types: it must stay out of Attention
        and out of every type list while remaining readable in All/Ended.
        """

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
    def test_eight_views_are_independent_and_deep_linkable(self) -> None:
        recognition = self._task("organize")
        self._recognition_problem(recognition.task_id, "recog-item")
        metadata = self._task("organize")
        self._metadata_correction_problem(metadata.task_id, "meta-item")
        classification = self._task("organize")
        self._classification_problem(classification.task_id, "class-item")
        conflict = self._task("organize")
        self._conflict_problem(conflict.task_id, "conflict-item")
        # A purely technical failure: durable history, never a fifth type.
        failure = self._task("organize")
        self._failure_problem(failure.task_id, "failure-item")
        # An ordinary (non-organizing) Files command must never enter the center.
        self._task("scan")
        ended = self._task("organize")
        self.repository.update_task(
            __import__("dataclasses").replace(
                ended,
                status=__import__(
                    "mediaflow.domain.task_persistence", fromlist=["PersistentTaskStatus"]
                ).PersistentTaskStatus.COMPLETED,
            )
        )

        all_page = self._page()
        self.assertEqual(6, all_page["total"])
        self.assertNotIn(
            "scan",
            {item["command"] for item in all_page["items"]},
            "an ordinary command family is not Task Center organizing work",
        )
        self.assertEqual(all_page["view"], None)
        # Each view is an independent server query with its own population.
        # The technical failure stays in the running partition (it is unfinished)
        # but is never an Attention problem and never a type list.
        cases = {
            "all": 6,
            "running": 5,
            "attention": 4,
            "ended": 1,
            "recognition": 1,
            "metadata": 1,
            "classification": 1,
            "conflict": 1,
        }
        for view, expected in cases.items():
            with self.subTest(view=view):
                page = self._page(f"view={view}")
                self.assertEqual(view if view != "all" else None, page["view"])
                self.assertEqual(expected, page["total"])
        # The retired fifth view is a rejected filter, never a silently
        # different population and never a resurrected recovery page.
        code, body = request(self.api, "GET", "/api/v1/operations/runs", query="view=failure")
        self.assertEqual(400, code)
        self.assertEqual("invalid_request", body["error"]["code"])
        # The recovery view always applies its own problem predicate even when
        # no explicit problem parameter is submitted.
        recognition_page = self._page("view=recognition")
        self.assertEqual(["recognition"], recognition_page["items"][0]["problem_types"])
        # A standalone problem filter narrows a lifecycle view server-side.
        narrowed = self._page("view=attention&problem=conflict")
        self.assertEqual(1, narrowed["total"])
        self.assertEqual(["conflict"], narrowed["items"][0]["problem_types"])
        # The technical failure is readable in All/Ended and carries no
        # Attention/type/problem claim.
        ended_row = next(item for item in all_page["items"] if item["run_id"] == failure.task_id)
        self.assertFalse(ended_row["attention"])
        self.assertEqual([], list(ended_row["problem_types"]))
        self.assertIsNone(ended_row["attention_reason"])
        # The durable technical failure itself is preserved untouched.
        self.assertEqual(
            TaskItemStatus.FAILED,
            self.repository.get_item("failure-item").status,
        )

    def test_summary_counts_the_complete_population_and_problem_files(self) -> None:
        # Three purely technical failures are real history but produce no
        # Attention and no type/problem count at all.
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
        self.assertEqual(1, summary["attention"])
        self.assertEqual(1, summary["problem_tasks"]["recognition"])
        self.assertEqual(2, summary["problem_files"]["recognition"])
        # A technical failure is not a fifth problem type and cannot be counted
        # as a problem or a file.
        self.assertEqual(
            sorted(["recognition", "metadata", "classification", "conflict"]),
            sorted(summary["problem_tasks"]),
        )
        self.assertEqual(
            sorted(["recognition", "metadata", "classification", "conflict"]),
            sorted(summary["problem_files"]),
        )
        self.assertEqual(4, page["total"])
        self.assertEqual(1, page["attention_count"])

    def test_source_filter_accepts_historical_paths_and_scopes_summary(self) -> None:
        alpha = self._task("organize", scope="Movies/alpha")
        self._recognition_problem(alpha.task_id, "alpha-file")
        beta = self._task("organize", scope="Movies/beta")
        self._classification_problem(beta.task_id, "beta-file")

        page = self._page("view=recognition&source=Movies%2Falpha")
        self.assertEqual(1, page["total"])
        self.assertEqual([alpha.task_id], [item["task_id"] for item in page["items"]])
        self.assertEqual(1, page["summary"]["total"])
        self.assertEqual(1, page["summary"]["problem_tasks"]["recognition"])
        self.assertEqual(1, page["summary"]["problem_files"]["recognition"])
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
        # One task with three metadata problems, one with a single one: the row
        # file count is that exact task's population, never another task's.
        three = self._task("organize", scope="Movies/three")
        self._metadata_correction_problem(three.task_id, "three-a")
        self._metadata_review_problem(three.task_id, "three-b")
        self._processing_item_as_waiting_metadata(three.task_id, "three-c")
        one = self._task("organize", scope="Movies/one")
        self._metadata_review_problem(one.task_id, "one-a")

        page = self._page("view=metadata")
        by_task = {item["task_id"]: item for item in page["items"]}
        self.assertEqual(3, by_task[three.task_id]["problem_file_counts"]["metadata"])
        self.assertEqual(1, by_task[one.task_id]["problem_file_counts"]["metadata"])
        self.assertEqual(4, page["summary"]["problem_files"]["metadata"])

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
            AutomationCommand.ORGANIZE,
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
            self._metadata_correction_problem(task.task_id, f"meta-{index}")
        first = self._page("view=metadata&limit=1")
        cursor = first["next_cursor"]
        self.assertIsNotNone(cursor)
        # The minted scope names the view and problem predicate.
        decoded = decode_directional_cursor(
            cursor,
            "operations_runs",
            expected_scope=(
                "principal=viewer;status=all;attention=false;view=metadata;"
                "problem=metadata;source=all;command=all;q=;from=;to="
            ),
        )
        self.assertIsNotNone(decoded)
        for mismatched in (
            f"view=recognition&limit=1&cursor={cursor}",
            f"view=all&limit=1&cursor={cursor}",
            f"view=metadata&problem=conflict&limit=1&cursor={cursor}",
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
            query=f"view=metadata&limit=1&cursor={cursor}",
        )
        self.assertEqual(400, code)

    def test_initial_manual_confirmation_stays_unfinished_without_attention(self) -> None:
        """An initial manual ``waiting_confirm`` is Running/All, not Attention.

        Task46.4 RO-4: normal manual work that waits for its *initial* execution
        confirmation has no four-type recovery lineage.  It therefore stays
        unfinished in Running/All with its exact summary reachable, contributes
        no pending-task count, no type list and no ended status -- and a plain
        ``waiting_confirm`` item never becomes a Conflict problem on its own.
        """

        from dataclasses import replace

        task = self.coordinator.create(
            "manual_organize", execute_authorized=True, scope_path="Movies/initial"
        )
        item = self._processing_item(task.task_id, "initial-confirm")
        self.repository.upsert_item(
            replace(
                item,
                status=TaskItemStatus.WAITING_CONFIRM,
                stage="waiting_confirm",
            )
        )
        attention = self._page("view=attention")
        self.assertEqual(0, attention["total"])
        self.assertEqual(0, attention["summary"]["attention"])
        for kind in ("recognition", "metadata", "classification", "conflict"):
            self.assertEqual(0, self._page(f"view={kind}")["total"], kind)
        running = self._page("view=running")
        self.assertEqual(1, running["total"])
        self.assertEqual(running["items"][0]["task_id"], task.task_id)
        # The real Task aggregate is an unfinished state (pending/running), so
        # the initial confirmation is genuine Running work.
        self.assertIn(running["items"][0]["status"], {"pending", "running"})
        self.assertFalse(running["items"][0]["attention"])
        self.assertEqual([], list(running["items"][0]["problem_types"]))
        # It is unfinished work, never an ended run.
        self.assertEqual(0, self._page("view=ended")["total"])

    def test_invalid_view_and_problem_values_reject_safely(self) -> None:
        for query in ("view=teleported", "problem=unknown", "view=recognition&view=metadata"):
            with self.subTest(query=query):
                code, body = request(self.api, "GET", "/api/v1/operations/runs", query=query)
                self.assertEqual(400, code)
                self.assertEqual("invalid_request", body["error"]["code"])

    def test_attention_row_exposes_each_current_problem_type_for_location(self) -> None:
        # The overlapping attention view must let the operator open the exact
        # Task/type file list for every current problem, not a dead action.
        # A purely technical failure on the same Task adds neither a type nor a
        # file member.
        mixed = self._task("organize")
        self._metadata_correction_problem(mixed.task_id, "meta-item")
        self._conflict_problem(mixed.task_id, "conflict-item")
        self._failure_problem(mixed.task_id, "failure-item")
        page = self._page("view=attention")
        self.assertEqual(1, page["total"])
        row = page["items"][0]
        self.assertEqual({"metadata", "conflict"}, set(row["problem_types"]))
        # Each type has its own reachable server-filtered file list.
        for problem in ("metadata", "conflict"):
            code, files = request(
                self.api,
                "GET",
                f"/api/v1/operations/runs/{mixed.task_id}/problem-items",
                query=f"problem={problem}",
            )
            self.assertEqual(200, code)
            self.assertEqual(problem, files["problem"])
            self.assertEqual(1, files["matching_total"])

    def test_saved_decision_keeps_its_own_type_until_the_step_completes(self) -> None:
        # Saving a metadata decision leaves the required safe continuation
        # pending.  It is still metadata work of the same recovery lineage, so
        # the row keeps exactly that one type instead of inventing a fifth
        # "safe continuation only" pseudo-type.
        task = self._task("organize")
        review_id = self._metadata_review_problem(task.task_id, "meta-item")
        MetadataReviewService(self.repository).resolve(review_id, 1, actor="operator")
        page = self._page("view=attention")
        self.assertEqual(1, page["total"])
        row = page["items"][0]
        self.assertEqual(["metadata"], list(row["problem_types"]))
        self.assertTrue(row["attention"])
        self.assertEqual("task_problem", row["attention_reason"])
        # The saved decision is reachable in the metadata type list itself, so
        # the required step is locatable after refresh/restart.
        metadata_page = self._page("view=metadata")
        self.assertEqual(1, metadata_page["total"])
        self.assertEqual(["metadata"], list(metadata_page["items"][0]["problem_types"]))

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
        ):
            self._page(f"view={view}")
        self._page()
        # The retired failure view and any other out-of-contract view are
        # rejected reads that still create no work and no media effect.
        for query in ("view=failure", "view=teleported", "problem=failure"):
            code, _body = request(self.api, "GET", "/api/v1/operations/runs", query=query)
            self.assertEqual(400, code)
        self.assertEqual(before_tasks, len(self.repository.list_tasks()))
        self.assertEqual(before_jobs, len(self.repository.list_jobs()))
        # An unauthenticated read is refused, never an empty population.
        code, _body = request(self.api, "GET", "/api/v1/operations/runs", token="denied")
        self.assertEqual(401, code)


class RecoveryListTests(_TaskCenterTestCase):
    def test_one_task_per_type_with_accurate_file_counts(self) -> None:
        # One Task carrying two recognition files and one classification
        # problem appears once in each of its own type lists, with the file
        # count of its own type; a purely technical failure on the same Task
        # adds no type, no file and no count.
        mixed = self._task("organize")
        self._recognition_problem(mixed.task_id, "recog-a")
        self._recognition_problem(mixed.task_id, "recog-b")
        self._classification_problem(mixed.task_id, "class-a")
        self._failure_problem(mixed.task_id, "failure-a")
        # A second Task with only a conflict problem.
        conflict = self._task("organize")
        self._conflict_problem(conflict.task_id, "conflict-a")

        recognition = self._page("view=recognition")
        self.assertEqual(1, recognition["total"])
        self.assertEqual(
            {"recognition", "classification"},
            set(recognition["items"][0]["problem_types"]),
        )
        self.assertEqual(2, recognition["summary"]["problem_files"]["recognition"])
        self.assertEqual(1, recognition["summary"]["problem_tasks"]["recognition"])

        classification = self._page("view=classification")
        self.assertEqual(1, classification["total"])
        self.assertEqual(1, classification["summary"]["problem_files"]["classification"])

        conflict_page = self._page("view=conflict")
        self.assertEqual(1, conflict_page["total"])
        self.assertEqual(conflict.task_id, conflict_page["items"][0]["task_id"])

        # The retired failure view is rejected, and no center read derives a
        # failure statistic from the technical failure.
        code, _body = request(self.api, "GET", "/api/v1/operations/runs", query="view=failure")
        self.assertEqual(400, code)
        summary = self._page()["summary"]
        self.assertNotIn("failure", summary["problem_tasks"])
        self.assertNotIn("failure", summary["problem_files"])

    def test_resolved_problem_keeps_its_type_until_the_human_step_completes(self) -> None:
        task = self._task("organize")
        review_id = self._recognition_problem(task.task_id, "recog-item")
        self.assertEqual(1, self._page("view=recognition")["total"])
        # Saving the decision leaves the item pending at ``recognition_resolved``
        # waiting for the required safe analysis continuation.  The problem is
        # not *resolved* yet: it stays in its own recognition type (and therefore
        # in Attention) instead of being relabelled as a technical failure.
        RecognitionReviewService(
            self.repository,
            (RecognitionType("A", "Movie"), RecognitionType("B", "TV")),
        ).resolve(review_id, "A", actor="operator")
        saved = self._page("view=recognition")
        self.assertEqual(1, saved["total"])
        self.assertIn("recognition", saved["items"][0]["problem_types"])
        self.assertEqual(1, self._page("view=attention")["total"])
        self.assertEqual(0, self._page("view=metadata")["total"])
        self.assertEqual(0, self._page("view=classification")["total"])
        # A genuinely new *classification* blocker on the same Task appears in
        # the classification list, and the task then carries both types once.
        self._classification_problem(task.task_id, "class-item")
        classification = self._page("view=classification")
        self.assertEqual(1, classification["total"])
        self.assertIn("classification", classification["items"][0]["problem_types"])
        self.assertEqual(1, self._page("view=attention")["total"])
        self.assertEqual(
            1, self._page("view=recognition")["summary"]["problem_tasks"]["recognition"]
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
        # A conflict file on the same Task must not appear in the recognition
        # file list.
        self._conflict_problem(task.task_id, "conflict-a")

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
        self.assertNotIn("conflict-a", [item["item_id"] for item in first["items"]])
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
        # The conflict file list contains only the conflict file.
        code, conflicts = request(
            self.api,
            "GET",
            f"/api/v1/operations/runs/{task.task_id}/problem-items",
            query="problem=conflict",
        )
        self.assertEqual(200, code)
        self.assertEqual(1, conflicts["matching_total"])
        self.assertEqual("conflict-a", conflicts["items"][0]["item_id"])
        # A retired technical-failure problem filter is rejected outright.
        code, _body = request(
            self.api,
            "GET",
            f"/api/v1/operations/runs/{task.task_id}/problem-items",
            query="problem=failure",
        )
        self.assertEqual(400, code)

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
            query=f"problem=conflict&limit=1&cursor={cursor}",
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
                AutomationCommand.ORGANIZE,
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
            query="problem=metadata",
        )
        self.assertEqual(200, code)
        self.assertIsNone(body["task_id"])
        self.assertIsNotNone(body["unavailable"])
        self.assertEqual(0, body["matching_total"])

    def test_pre_task_technical_failure_is_read_only_history_not_attention(self) -> None:
        # A Job that failed before any Task existed carries structured, durable
        # failure evidence (a stable category plus an explicit next action).
        # Task46.4 RO-4: that is real read-only history, *not* a fifth problem
        # type and not required human organizing work -- it never enters
        # Attention, pending counts or a type list, while All/Ended keep the
        # real failed status and its factual reason.
        from mediaflow.domain.automation import (
            AutomationCommand,
            AutomationJob,
            AutomationJobStatus,
        )

        self.repository.admit_job(
            AutomationJob(
                "pre-task-repair",
                AutomationCommand.ORGANIZE,
                AutomationJobStatus.PENDING,
                NOW,
                NOW,
            ),
            100,
        )
        finished = self.repository.update_job(
            AutomationJob(
                "pre-task-repair",
                AutomationCommand.ORGANIZE,
                AutomationJobStatus.FAILED,
                NOW,
                NOW,
                completed_at=NOW,
                failure_category="snapshot_digest_mismatch",
                failure_durable_state="the saved revision digest no longer matches",
                failure_side_effects="none",
                failure_retry_safe=False,
                failure_next_action="restore the exact saved published revision",
            )
        )
        self.assertIsNone(finished)
        stored = self.repository.get_job("pre-task-repair")
        self.assertEqual(AutomationJobStatus.FAILED, stored.status)
        # No Attention and no fabricated problem membership.
        self.assertEqual(0, self._page("view=attention")["total"])
        self.assertEqual(0, self._page()["summary"]["attention"])
        for problem in ("recognition", "metadata", "classification", "conflict"):
            self.assertEqual(0, self._page(f"view={problem}")["total"])
        # The factual failed record is still readable in All/Ended.
        all_page = self._page()
        self.assertEqual(1, all_page["total"])
        row = all_page["items"][0]
        self.assertFalse(row["attention"])
        self.assertEqual([], list(row["problem_types"]))
        self.assertIsNone(row["attention_reason"])
        self.assertEqual("failed", row["status"])
        self.assertEqual(1, self._page("view=ended")["total"])
        # Its structured failure evidence stays readable through the Job detail
        # the center already links to -- not a new center failure surface.
        code, job_document = request(self.api, "GET", "/api/v1/operations/jobs/pre-task-repair")
        self.assertEqual(200, code)
        self.assertEqual("snapshot_digest_mismatch", job_document["failure"]["category"])
        self.assertEqual(
            "restore the exact saved published revision",
            job_document["failure"]["nextAction"],
        )
        self.assertEqual(1, self._page("view=ended")["total"])

    def test_plain_queue_and_unstructured_failure_are_not_run_level_repair(self) -> None:
        # A plain queue admission carries no structured repair evidence, and a
        # generic exception failure records no category/next action: neither is
        # a manual to-do, so the attention facet must not invent one.
        from mediaflow.domain.automation import (
            AutomationCommand,
            AutomationJob,
            AutomationJobStatus,
        )

        self.repository.admit_job(
            AutomationJob(
                "queued-plain",
                AutomationCommand.ORGANIZE,
                AutomationJobStatus.PENDING,
                NOW,
                NOW,
            ),
            100,
        )
        self.repository.create_job(
            AutomationJob(
                "generic-failure",
                AutomationCommand.ORGANIZE,
                AutomationJobStatus.FAILED,
                NOW,
                NOW,
                completed_at=NOW,
                error="workflow failed (RuntimeError)",
            )
        )
        page = self._page("view=attention")
        self.assertEqual(0, page["total"])
        self.assertEqual(0, page["summary"]["attention"])
        # Both remain visible in the ordinary lifecycle views.
        self.assertEqual(2, self._page()["total"])
        self.assertEqual(1, self._page("view=ended")["total"])

    def test_cancelled_job_with_evidence_is_not_run_level_repair(self) -> None:
        # A definition-pinned cancellation also records bounded failure evidence
        # (category/next action), but cancellation is the operator's own
        # completed intent, not an outstanding repair to-do.
        from mediaflow.domain.automation import (
            AutomationCommand,
            AutomationJob,
            AutomationJobStatus,
        )

        self.repository.create_job(
            AutomationJob(
                "cancelled-with-evidence",
                AutomationCommand.ORGANIZE,
                AutomationJobStatus.CANCELLED,
                NOW,
                NOW,
                completed_at=NOW,
                cancellation_requested=True,
                error="workflow cancelled",
                failure_category="workflow_cancelled",
                failure_durable_state="no Task was created and no media effect occurred",
                failure_side_effects="none",
                failure_retry_safe=True,
                failure_next_action=("inspect the Automation definition and leave it enabled"),
            )
        )
        page = self._page("view=attention")
        self.assertEqual(0, page["total"])
        self.assertEqual(0, page["summary"]["attention"])
        self.assertEqual(1, self._page("view=ended")["total"])

    def test_run_level_repair_evidence_never_leaks_into_a_linked_task(self) -> None:
        # Once a Job has produced a Task, the Task's item/review evidence owns
        # the current problem; the Job's earlier structured failure must not be
        # re-published as a separate run-level repair.
        from mediaflow.domain.automation import (
            AutomationCommand,
            AutomationJob,
            AutomationJobStatus,
        )

        task = self._task("organize")
        self.repository.create_job(
            AutomationJob(
                "linked-repair",
                AutomationCommand.ORGANIZE,
                AutomationJobStatus.FAILED,
                NOW,
                NOW,
                completed_at=NOW,
                task_id=task.task_id,
                failure_category="definition_scoped_workflow_failed",
                failure_durable_state="linked Task failed before workflow completion",
                failure_side_effects="none",
                failure_retry_safe=True,
                failure_next_action="inspect the linked Task and per-item state",
            )
        )
        page = self._page("view=attention")
        self.assertEqual(0, page["total"])
        # The run is still visible in the ordinary inventory; it just carries no
        # fabricated run-level repair and no attention.
        all_page = self._page()
        self.assertEqual(1, all_page["total"])
        row = all_page["items"][0]
        self.assertFalse(row["attention"])
        self.assertIsNone(row["attention_reason"])
        self.assertIsNone(row["attention_failure_category"])
        self.assertIsNone(row["attention_failure_next_action"])

    def test_attention_view_never_fabricates_zero_for_an_unavailable_read(self) -> None:
        # A read against a runtime without the summary projection still
        # answers the list, but publishes an explicit unavailable summary.
        page = self._page("view=attention")
        self.assertIn("summary", page)
        self.assertTrue(page["summary"]["available"])


class TaskCenterPopulationTests(_TaskCenterTestCase):
    """The center's membership rule, exercised over real durable rows (RO-4).

    Every case here writes the exact durable shape a real producer writes and
    then asks the center's own reads: the same rule must decide the list, the
    counts, the source options, the cursor population and the exact-ID detail.
    """

    def test_ordinary_and_notification_work_never_enters_the_center(self) -> None:
        # Ordinary Files/MediaLibrary commands, a notification command and an
        # unknown legacy command are real durable rows, but never organizing
        # work: no page, count, type list, source option or cursor includes them.
        for command in (
            "files_direct_command",
            "files_delete",
            "files_transfer",
            "media_files_transfer",
            "media_rename",
            "notify-delivery",
            "legacy_historic_work",
        ):
            self.coordinator.create(command, execute_authorized=True, scope_path=command)
        organizing = self._task("organize", scope="Movies/organizing")
        self._recognition_problem(organizing.task_id, "recog-item")

        page = self._page()
        self.assertEqual([organizing.task_id], [item["task_id"] for item in page["items"]])
        self.assertEqual(1, page["total"])
        self.assertEqual({"running": 1}, page["status_counts"])
        self.assertEqual(1, page["summary"]["total"])
        self.assertEqual(1, page["summary"]["problem_tasks"]["recognition"])
        self.assertEqual(
            ["Movies/organizing"],
            [entry["value"] for entry in page["summary"]["sources"]],
        )
        self.assertIsNone(page["next_cursor"])

        # An exact-ID center read of an ordinary row is a 404, never a
        # re-labelled organizing run.
        code, body = request(self.api, "GET", "/api/v1/operations/runs/files_transfer")
        self.assertEqual(404, code)
        self.assertEqual("not_found", body["error"]["code"])
        # A cursor minted over the organizing population cannot be replayed to
        # reach an ordinary row either: the population is decided server-side.
        code, filtered = request(
            self.api, "GET", "/api/v1/operations/runs", query="command=files_transfer"
        )
        self.assertEqual(200, code)
        self.assertEqual(0, filtered["total"])

    def test_analysis_only_preparation_is_not_organizing_work(self) -> None:
        # A definition Run once that has not admitted its own Task is center
        # work; a plain analysis/preview preparation (no definition origin and
        # no admitted Task) is not.
        snapshot = self.repository.list_tasks(limit=1)
        del snapshot  # the fixture's own organizer admission defaults are enough
        self.repository._connection.execute(
            "INSERT INTO media_discoveries (discovery_id, actor, resource_library_id,"
            " storage_id, configuration_snapshot_id, configuration_snapshot_digest,"
            " status, version, budgets_json, progress_json, sources_json,"
            " attempts, pause_requested, cancel_requested, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "plain-analysis",
                "operator",
                "source",
                "source-storage",
                "snap-1",
                "digest-1",
                "completed",
                1,
                "{}",
                "{}",
                "[]",
                0,
                0,
                0,
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
        self.repository._connection.commit()
        page = self._page()
        self.assertEqual(0, page["total"], page)
        code, body = request(self.api, "GET", "/api/v1/operations/runs/plain-analysis")
        self.assertEqual(404, code)

    def test_job_to_task_linkage_keeps_one_identity_and_one_count(self) -> None:
        # A Job acquiring its Task is the same admitted organizing run: the
        # identity, the count and the problem membership never drift, and the
        # linked Task ID still resolves to the one run.
        task = self._task("organize", scope="Movies/linked")
        self._metadata_correction_problem(task.task_id, "meta-a")
        job = AutomationJob(
            "job-linked",
            AutomationCommand.ORGANIZE,
            AutomationJobStatus.PENDING,
            NOW,
            NOW,
            task_id=task.task_id,
            source_scope="Movies/linked",
        )
        self.repository.create_job(job)

        page = self._page()
        self.assertEqual(1, page["total"])
        self.assertEqual("job-linked", page["items"][0]["run_id"])
        self.assertEqual(task.task_id, page["items"][0]["task_id"])
        self.assertEqual({"running": 1}, page["status_counts"])
        # The Job is the admission identity and the pending Task keeps the
        # aggregate in its own unfinished partition without a second row.
        self.assertEqual("running", page["items"][0]["status"])
        self.assertEqual(1, page["summary"]["problem_tasks"]["metadata"])
        # Both durable identities open the same exact run.
        for identity in ("job-linked", task.task_id):
            code, document = request(self.api, "GET", f"/api/v1/operations/runs/{identity}")
            self.assertEqual(200, code)
            self.assertEqual("job-linked", document["run_id"])
            self.assertEqual(task.task_id, document["task_id"])
            self.assertEqual(["metadata"], document["problem_types"])

    def test_mixed_population_beyond_one_page_counts_and_pages_consistently(self) -> None:
        # Ordinary work is newer than every organizing row: the backend decides
        # the population before paging, so the page, the totals and the source
        # options never change because of it.
        organizing_ids = []
        for index in range(3):
            task = self._task("organize", scope=f"Movies/page-{index}")
            self._metadata_correction_problem(task.task_id, f"meta-{index}")
            organizing_ids.append(task.task_id)
        for index in range(5):
            self.coordinator.create(
                "files_direct_command",
                execute_authorized=True,
                scope_path=f"Files/ordinary-{index}",
            )

        first = self._page("view=metadata&limit=2")
        self.assertEqual(3, first["total"])
        self.assertEqual(2, len(first["items"]))
        self.assertEqual(3, first["summary"]["problem_tasks"]["metadata"])
        self.assertEqual(3, first["summary"]["problem_files"]["metadata"])
        self.assertEqual(
            sorted(f"Movies/page-{index}" for index in range(3)),
            sorted(entry["value"] for entry in first["summary"]["sources"]),
        )
        second = self._page(f"view=metadata&limit=2&cursor={first['next_cursor']}")
        self.assertEqual(3, second["total"])
        self.assertEqual(1, len(second["items"]))
        collected = {item["task_id"] for item in first["items"]} | {
            item["task_id"] for item in second["items"]
        }
        self.assertEqual(set(organizing_ids), collected)
        # Every collected row is organizing work with the metadata problem.
        for item in (*first["items"], *second["items"]):
            self.assertEqual(["metadata"], list(item["problem_types"]))

    def test_standalone_analysis_only_dryrun_is_not_organizing_work(self) -> None:
        # B46.4-05: the production CLI ``organize <file>`` without ``--execute``
        # admits a real durable Task whose shape is DRY_RUN / zero movement /
        # ``execute_authorized=False``.  That is analysis-only preparation, so it
        # never enters a center list, count, source option, cursor or exact-ID
        # deep link -- while the Task/Result rows themselves stay intact.
        analysed = self.coordinator.create(
            "organize",
            execute_authorized=False,
            scope_path="Movies/analysis-only",
        )
        self._processing_item(analysed.task_id, "analysis-item")
        self.repository._connection.execute(
            "UPDATE task_items SET status='dry_run', stage='completed' WHERE item_id=?",
            ("analysis-item",),
        )
        self.repository._connection.commit()

        page = self._page()
        self.assertEqual(0, page["total"], page)
        self.assertEqual([], [entry["value"] for entry in page["summary"]["sources"]])
        for view in (
            "all",
            "running",
            "attention",
            "ended",
            "recognition",
            "metadata",
            "classification",
            "conflict",
        ):
            self.assertEqual(0, self._page(f"view={view}")["total"], view)
        code, body = request(self.api, "GET", f"/api/v1/operations/runs/{analysed.task_id}")
        self.assertEqual(404, code)
        self.assertEqual("not_found", body["error"]["code"])
        # Nothing was deleted: the durable analysis Task and its item remain.
        self.assertIsNotNone(self.repository.get_task(analysed.task_id))
        self.assertIsNotNone(self.repository.get_item("analysis-item"))

        # A confirmed execution intent of the *same* scope is organizing work.
        executed = self.coordinator.create(
            "organize",
            execute_authorized=True,
            scope_path="Movies/executed",
        )
        self.assertEqual(1, self._page()["total"])
        self.assertEqual(executed.task_id, self._page()["items"][0]["task_id"])

    def test_analysis_only_successors_never_inherit_center_membership(self) -> None:
        # B46.4-05: an analysis-only Task's own recovery successors are not
        # organizing work either, and they must not become a back door into the
        # center.  The same persisted relation from an *admitted* Task is legal
        # organizing lineage, so the rule is the predecessor's admission — not
        # the continuation command.
        analysed = self.coordinator.create(
            "organize", execute_authorized=False, scope_path="Movies/analysis-only"
        )
        self._processing_item(analysed.task_id, "analysis-item")
        analysis_child = self.coordinator.create(
            "recovery-continuation:analysis-continuation",
            execute_authorized=False,
            scope_path="Movies/analysis-only",
        )
        self._processing_item(analysis_child.task_id, "analysis-child-item")
        self._insert_continuation(
            "analysis-continuation",
            source_task_id=analysed.task_id,
            source_item_id="analysis-item",
            new_task_id=analysis_child.task_id,
        )
        self.assertEqual(0, self._page()["total"])

        admitted = self.coordinator.create(
            "organize", execute_authorized=True, scope_path="Movies/admitted"
        )
        self._processing_item(admitted.task_id, "admitted-item")
        admitted_child = self.coordinator.create(
            "recovery-continuation:admitted-continuation",
            execute_authorized=False,
            scope_path="Movies/admitted",
        )
        self._processing_item(admitted_child.task_id, "admitted-child-item")
        self._insert_continuation(
            "admitted-continuation",
            source_task_id=admitted.task_id,
            source_item_id="admitted-item",
            new_task_id=admitted_child.task_id,
        )
        ids = {item["task_id"] for item in self._page()["items"]}
        self.assertEqual({admitted.task_id, admitted_child.task_id}, ids)

    def _insert_continuation(
        self,
        continuation_id: str,
        *,
        source_task_id: str,
        source_item_id: str,
        new_task_id: str,
    ) -> None:
        """Persist the exact recovery-continuation relation a real Worker writes."""

        with self.repository._connection:
            self.repository._connection.execute(
                """INSERT INTO recovery_continuations (
                    continuation_id, request_id, source_task_id, source_item_id,
                    checkpoint_version, configuration_snapshot_id,
                    configuration_snapshot_digest, boundary, status, created_at,
                    updated_at, actor, job_id, new_task_id, authority_statement
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    continuation_id,
                    f"request-{continuation_id}",
                    source_task_id,
                    source_item_id,
                    "0" * 64,
                    "snap-1",
                    "digest-1",
                    "source_scope_analysis",
                    "completed",
                    NOW.isoformat(),
                    NOW.isoformat(),
                    "operator",
                    f"job-{continuation_id}",
                    new_task_id,
                    "analysis only",
                ),
            )
