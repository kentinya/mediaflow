from __future__ import annotations

import io
import json
import tempfile
import unittest
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
        self.assertIn("?itemLimit=100&resultLimit=100", script)
        self.assertIn("Items truncated", script)
        self.assertIn("Results truncated", script)
        self.assertIn("Open linked task", script)
        self.assertIn("textContent", script)
        self.assertNotIn("/api/v1/tasks/${encodeURIComponent(id)}/resume", script)
        self.assertNotIn("/api/v1/jobs/${encodeURIComponent(id)}/cancel", script)
        self.assertNotIn("/api/v1/jobs', {method: 'POST'", script)

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
