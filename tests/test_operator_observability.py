from __future__ import annotations

import base64
import io
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from mediaflow.domain.automation import AutomationCommand, AutomationJob, AutomationJobStatus
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import APP_JS, INDEX_HTML
from mediaflow.interfaces.pagination import decode_cursor, encode_cursor
from mediaflow.interfaces.service_api import MediaFlowApi

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)


def request(api, path: str, *, query: str = ""):
    statuses = []
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": "0",
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": "Bearer viewer-token",
        "wsgi.input": io.BytesIO(),
    }
    body = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(body)


class OperatorObservabilityTests(unittest.TestCase):
    def test_task_and_job_collections_are_bounded_and_validate_queries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                for rank in range(3):
                    repository.create_task(self._task(rank))
                    repository.create_job(self._job(rank))
                api = self._api(repository)
                status, tasks = request(api, "/api/v1/tasks", query="limit=2")
                self.assertEqual(status, 200)
                self.assertEqual(tasks["limit"], 2)
                self.assertTrue(tasks["truncated"])
                self.assertEqual([item["task_id"] for item in tasks["items"]], ["task-2", "task-1"])
                status, jobs = request(api, "/api/v1/jobs", query="limit=2")
                self.assertEqual(status, 200)
                self.assertEqual(jobs["limit"], 2)
                self.assertTrue(jobs["truncated"])
                self.assertEqual([item["job_id"] for item in jobs["items"]], ["job-2", "job-1"])
                status, default = request(api, "/api/v1/tasks")
                self.assertEqual(
                    (status, default["limit"], default["truncated"]), (200, 100, False)
                )
                for path in ("/api/v1/tasks", "/api/v1/jobs"):
                    for query in (
                        "limit=0",
                        "limit=101",
                        "limit=no",
                        "limit=1&limit=2",
                        "path=/private",
                    ):
                        with self.subTest(path=path, query=query):
                            self.assertEqual(request(api, path, query=query)[0], 400)

    def test_task_detail_limits_items_and_results_in_sql_and_reports_truncation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                repository.create_task(self._task(0))
                for rank in range(3):
                    repository.upsert_item(self._item(rank))
                    repository.append_result(self._result(rank))
                api = self._api(repository)
                with (
                    patch.object(repository, "list_items", wraps=repository.list_items) as items,
                    patch.object(
                        repository, "list_results", wraps=repository.list_results
                    ) as results,
                ):
                    status, document = request(
                        api,
                        "/api/v1/tasks/task-0",
                        query="itemLimit=1&resultLimit=2",
                    )
                self.assertEqual(status, 200)
                self.assertEqual([item["item_id"] for item in document["items"]], ["item-0"])
                self.assertEqual(
                    [item["result_id"] for item in document["results"]], ["result-0", "result-1"]
                )
                self.assertTrue(document["items_truncated"])
                self.assertTrue(document["results_truncated"])
                self.assertEqual((document["item_limit"], document["result_limit"]), (1, 2))
                items.assert_called_once_with("task-0", limit=2)
                results.assert_called_once_with("task-0", limit=3)
                for query in (
                    "itemLimit=0",
                    "resultLimit=101",
                    "itemLimit=x",
                    "itemLimit=1&itemLimit=2",
                    "sourcePath=/private",
                ):
                    with self.subTest(query=query):
                        self.assertEqual(request(api, "/api/v1/tasks/task-0", query=query)[0], 400)
                self.assertEqual(request(api, "/api/v1/tasks/missing")[0], 404)

    def test_operator_ui_has_read_only_task_job_and_result_views(self) -> None:
        html = INDEX_HTML.decode()
        script = APP_JS.decode()
        self.assertIn('data-view="tasks"', html)
        self.assertIn('data-view="jobs"', html)
        self.assertIn("/api/v1/${kind}?limit=100", script)
        self.assertIn("?itemLimit=100&resultLimit=100${itemSuffix}${resultSuffix}", script)
        self.assertIn("Items truncated", script)
        self.assertIn("Results truncated", script)
        self.assertIn("Open linked task", script)
        self.assertIn("Next ${noun}", script)
        self.assertIn("Next items", script)
        self.assertIn("Next results", script)
        self.assertIn("textContent", script)
        self.assertNotIn("/api/v1/tasks/${encodeURIComponent(id)}/resume", script)
        self.assertNotIn("/api/v1/jobs/${encodeURIComponent(id)}/cancel", script)
        self.assertNotIn("/api/v1/jobs', {method: 'POST'", script)

    def test_task_and_job_cursor_pages_are_stable_with_identical_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                for rank in range(5):
                    repository.create_task(
                        replace(self._task(rank), created_at=NOW, updated_at=NOW)
                    )
                    repository.create_job(replace(self._job(rank), created_at=NOW, updated_at=NOW))
                api = self._api(repository)
                task_ids, cursor = [], None
                while True:
                    query = "limit=2" + (f"&cursor={cursor}" if cursor else "")
                    status, page = request(api, "/api/v1/tasks", query=query)
                    self.assertEqual(status, 200)
                    task_ids.extend(item["task_id"] for item in page["items"])
                    cursor = page["next_cursor"]
                    if cursor is None:
                        self.assertFalse(page["truncated"])
                        break
                self.assertEqual(task_ids, ["task-4", "task-3", "task-2", "task-1", "task-0"])
                self.assertEqual(len(task_ids), len(set(task_ids)))
                end_cursor = encode_cursor("tasks", NOW, "task-0")
                _, empty = request(api, "/api/v1/tasks", query=f"limit=2&cursor={end_cursor}")
                self.assertEqual(empty["items"], [])
                self.assertFalse(empty["truncated"])
                self.assertIsNone(empty["next_cursor"])
                self.assertNotIn(end_cursor, repr(repository.list_security_audit(limit=100)))

                job_ids, cursor = [], None
                while True:
                    query = "limit=2" + (f"&cursor={cursor}" if cursor else "")
                    status, page = request(api, "/api/v1/jobs", query=query)
                    self.assertEqual(status, 200)
                    job_ids.extend(item["job_id"] for item in page["items"])
                    cursor = page["next_cursor"]
                    if cursor is None:
                        break
                self.assertEqual(job_ids, ["job-4", "job-3", "job-2", "job-1", "job-0"])

    def test_item_and_result_cursors_are_independent_oldest_first(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                repository.create_task(self._task(0))
                for rank in range(4):
                    repository.upsert_item(
                        replace(self._item(rank), created_at=NOW, updated_at=NOW)
                    )
                    repository.append_result(replace(self._result(rank), created_at=NOW))
                api = self._api(repository)
                _, first = request(
                    api,
                    "/api/v1/tasks/task-0",
                    query="itemLimit=2&resultLimit=1",
                )
                self.assertEqual([item["item_id"] for item in first["items"]], ["item-0", "item-1"])
                self.assertEqual([item["result_id"] for item in first["results"]], ["result-0"])
                item_position = decode_cursor(first["next_item_cursor"], "task_items")
                result_position = decode_cursor(first["next_result_cursor"], "task_results")
                with (
                    patch.object(repository, "list_items", wraps=repository.list_items) as items,
                    patch.object(
                        repository, "list_results", wraps=repository.list_results
                    ) as results,
                ):
                    _, second = request(
                        api,
                        "/api/v1/tasks/task-0",
                        query=(
                            "itemLimit=2&resultLimit=1"
                            f"&itemCursor={first['next_item_cursor']}"
                            f"&resultCursor={first['next_result_cursor']}"
                        ),
                    )
                self.assertEqual(
                    [item["item_id"] for item in second["items"]], ["item-2", "item-3"]
                )
                self.assertEqual([item["result_id"] for item in second["results"]], ["result-1"])
                items.assert_called_once_with("task-0", limit=3, after=item_position)
                results.assert_called_once_with("task-0", limit=2, after=result_position)
                self.assertIsNone(second["next_item_cursor"])
                self.assertIsNotNone(second["next_result_cursor"])

    def test_cursor_validation_rejects_malformed_cross_kind_and_injected_values(self) -> None:
        valid = encode_cursor("tasks", NOW, "task-1")
        self.assertEqual(decode_cursor(valid, "tasks"), (NOW, "task-1"))
        invalid_documents = (
            {"at": NOW.isoformat(), "id": "task-1", "kind": "tasks"},
            {"at": "not-a-time", "id": "task-1", "kind": "tasks", "version": 1},
            {
                "at": "2026-08-22T20:00:00+08:00",
                "id": "task-1",
                "kind": "tasks",
                "version": 1,
            },
            {"at": NOW.isoformat(), "id": "../task", "kind": "tasks", "version": 1},
            {"at": NOW.isoformat(), "id": "task-1", "kind": "tasks", "version": True},
        )
        for document in invalid_documents:
            raw = json.dumps(document, separators=(",", ":")).encode()
            cursor = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
            with self.subTest(document=document), self.assertRaises(ValueError):
                decode_cursor(cursor, "tasks")
        for cursor in ("%", "x" * 513, encode_cursor("jobs", NOW, "job-1")):
            with self.subTest(cursor=cursor), self.assertRaises(ValueError):
                decode_cursor(cursor, "tasks")

        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                repository.create_task(self._task(0))
                api = self._api(repository)
                for query in (
                    "limit=1&cursor=%25",
                    f"limit=1&cursor={encode_cursor('jobs', NOW, 'job-1')}",
                    f"limit=1&cursor={valid}&cursor={valid}",
                    "itemLimit=1&itemCursor=%25",
                    f"resultLimit=1&resultCursor={encode_cursor('task_items', NOW, 'item-1')}",
                ):
                    path = (
                        "/api/v1/tasks/task-0"
                        if "item" in query or "result" in query
                        else "/api/v1/tasks"
                    )
                    with self.subTest(query=query):
                        self.assertEqual(request(api, path, query=query)[0], 400)

    def test_newer_concurrent_insert_does_not_shift_existing_task_cursor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                for rank in range(4):
                    repository.create_task(
                        replace(self._task(rank), created_at=NOW, updated_at=NOW)
                    )
                api = self._api(repository)
                _, first = request(api, "/api/v1/tasks", query="limit=2")
                repository.create_task(
                    replace(
                        self._task(9),
                        created_at=NOW + timedelta(minutes=1),
                        updated_at=NOW + timedelta(minutes=1),
                    )
                )
                _, second = request(
                    api,
                    "/api/v1/tasks",
                    query=f"limit=2&cursor={first['next_cursor']}",
                )
                combined = [item["task_id"] for item in first["items"] + second["items"]]
                self.assertEqual(combined, ["task-3", "task-2", "task-1", "task-0"])
                self.assertNotIn("task-9", combined)

    @staticmethod
    def _api(repository) -> MediaFlowApi:
        principal = ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
        return MediaFlowApi(repository, None, principals=(principal,))

    @staticmethod
    def _task(rank: int) -> PersistentTask:
        occurred = NOW + timedelta(minutes=rank)
        return PersistentTask(
            f"task-{rank}",
            "preview",
            PersistentTaskStatus.COMPLETED,
            False,
            occurred,
            occurred,
            total_items=3,
            completed_items=3,
        )

    @staticmethod
    def _job(rank: int) -> AutomationJob:
        occurred = NOW + timedelta(minutes=rank)
        return AutomationJob(
            f"job-{rank}",
            AutomationCommand.PREVIEW,
            AutomationJobStatus.COMPLETED,
            occurred,
            occurred,
            task_id=f"task-{rank}",
        )

    @staticmethod
    def _item(rank: int) -> PersistentTaskItem:
        occurred = NOW + timedelta(seconds=rank)
        return PersistentTaskItem(
            f"item-{rank}",
            "task-0",
            "source",
            "movies",
            f"movie-{rank}.mkv",
            f"source:movie-{rank}.mkv",
            TaskItemStatus.DRY_RUN,
            "completed",
            1,
            occurred,
            occurred,
        )

    @staticmethod
    def _result(rank: int) -> PersistentResultRecord:
        occurred = NOW + timedelta(seconds=rank)
        return PersistentResultRecord(
            f"result-{rank}",
            "task-0",
            f"item-{rank}",
            "source",
            f"movie-{rank}.mkv",
            "target",
            f"Movies/movie-{rank}.mkv",
            "A",
            "tmdb",
            str(rank),
            "A",
            "A",
            "A",
            "A",
            "MOVE",
            "dry_run",
            occurred,
            title=f"Movie {rank}",
        )


if __name__ == "__main__":
    unittest.main()
