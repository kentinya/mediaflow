from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier, Thread
from unittest.mock import patch

from mediaflow.application.automation import AutomationJobService, AutomationWorker
from mediaflow.domain.automation import AutomationJobStatus
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi


class AutomationPersistenceTests(unittest.TestCase):
    def test_jobs_persist_claim_in_order_and_cancel_only_pending(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                service = AutomationJobService(repository)
                first = service.submit("scan", limit=3)
                second = service.submit("preview")
                claimed = repository.claim_next_job(datetime.now(UTC))
                self.assertEqual(claimed.job_id, first.job_id)
                self.assertEqual(claimed.status, AutomationJobStatus.RUNNING)
                with self.assertRaisesRegex(ValueError, "only a pending"):
                    service.cancel(first.job_id)
                cancelled = service.cancel(second.job_id)
                self.assertEqual(cancelled.status, AutomationJobStatus.CANCELLED)
            with SQLiteTaskRepository(database) as reopened:
                self.assertEqual(reopened.get_job(first.job_id).status, AutomationJobStatus.RUNNING)
                self.assertEqual(
                    reopened.get_job(second.job_id).status, AutomationJobStatus.CANCELLED
                )

    def test_atomic_claim_allows_one_worker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                AutomationJobService(repository).submit("scan")
            barrier = Barrier(2)
            claimed = []

            def claim() -> None:
                with SQLiteTaskRepository(database) as repository:
                    barrier.wait()
                    claimed.append(repository.claim_next_job(datetime.now(UTC)))

            threads = [Thread(target=claim), Thread(target=claim)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(sum(value is not None for value in claimed), 1)

    def test_worker_completes_and_redacts_failure_details(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = AutomationJobService(repository)
                service.submit("preview")
                completed = AutomationWorker(repository, lambda job: "task-1").run_next()
                self.assertEqual(completed.status, AutomationJobStatus.COMPLETED)
                self.assertEqual(completed.task_id, "task-1")
                service.submit("scan")

                def fail(job):
                    raise RuntimeError("Authorization: Bearer top-secret")

                failed = AutomationWorker(repository, fail).run_next()
                self.assertEqual(failed.status, AutomationJobStatus.FAILED)
                self.assertNotIn("top-secret", failed.error)
                self.assertEqual(failed.error, "workflow failed (RuntimeError)")

    def test_invalid_commands_and_limits_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = AutomationJobService(repository)
                for command in ("organize", "execute", "delete"):
                    with self.assertRaisesRegex(ValueError, "scan or preview"):
                        service.submit(command)
                for limit in (0, -1, True, "2"):
                    with self.assertRaisesRegex(ValueError, "positive integer"):
                        service.submit("scan", limit=limit)


class ServiceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = SQLiteTaskRepository(Path(self.directory.name, "runtime.sqlite3"))
        self.api = MediaFlowApi(self.repository, "api-secret")

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def request(self, method: str, path: str, document=None, token: str | None = None):
        body = b"" if document is None else json.dumps(document).encode()
        status = []
        headers = []
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "CONTENT_LENGTH": str(len(body)),
            "wsgi.input": io.BytesIO(body),
        }
        if token is not None:
            environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        def start_response(value, response_headers):
            status.append(value)
            headers.extend(response_headers)

        response = b"".join(self.api(environ, start_response))
        return int(status[0].split()[0]), json.loads(response), dict(headers)

    def test_health_public_and_api_requires_auth(self) -> None:
        self.assertEqual(self.request("GET", "/health")[0], 200)
        status, document, _ = self.request("GET", "/api/v1/jobs")
        self.assertEqual(status, 401)
        self.assertNotIn("api-secret", json.dumps(document))

    def test_submit_list_show_cancel_and_utf8(self) -> None:
        status, created, headers = self.request(
            "POST", "/api/v1/jobs", {"command": "preview", "limit": 20}, "api-secret"
        )
        self.assertEqual(status, 202)
        self.assertIn("charset=utf-8", headers["Content-Type"])
        job_id = created["job_id"]
        self.assertEqual(
            self.request("GET", f"/api/v1/jobs/{job_id}", token="api-secret")[1]["limit"],
            20,
        )
        self.assertEqual(
            self.request("GET", "/api/v1/jobs", token="api-secret")[1]["items"][0]["command"],
            "preview",
        )
        cancelled = self.request("POST", f"/api/v1/jobs/{job_id}/cancel", token="api-secret")[1]
        self.assertEqual(cancelled["status"], "cancelled")

    def test_rejects_execute_and_unsupported_commands(self) -> None:
        for document in (
            {"command": "organize"},
            {"command": "preview", "execute": False},
            {"command": "scan", "overwrite": False},
        ):
            status, response, _ = self.request("POST", "/api/v1/jobs", document, "api-secret")
            self.assertEqual(status, 400)
            self.assertEqual(response["error"]["code"], "invalid_request")
        self.assertEqual(len(self.repository.list_jobs()), 0)

    def test_stable_errors_for_invalid_json_unknown_routes_and_ids(self) -> None:
        status, response, _ = self.request("GET", "/missing")
        self.assertEqual((status, response["error"]["code"]), (404, "not_found"))
        status, response, _ = self.request("GET", "/api/v1/jobs/missing", token="api-secret")
        self.assertEqual((status, response["error"]["code"]), (404, "not_found"))
        status = []
        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/api/v1/jobs",
            "CONTENT_LENGTH": "1",
            "CONTENT_TYPE": "application/json",
            "HTTP_AUTHORIZATION": "Bearer api-secret",
            "wsgi.input": io.BytesIO(b"{"),
        }
        response = b"".join(self.api(environ, lambda value, headers: status.append(value)))
        self.assertEqual(status[0].split()[0], "400")
        self.assertEqual(json.loads(response)["error"]["code"], "invalid_request")

    def test_read_endpoints_do_not_construct_or_mutate_storage(self) -> None:
        for path in ("/api/v1/tasks", "/api/v1/jobs", "/api/v1/confirmations"):
            self.assertEqual(self.request("GET", path, token="api-secret")[0], 200)


class AutomationCliTests(unittest.TestCase):
    def _configuration(self, directory: str) -> Path:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        root = Path(directory)
        source = root / "source"
        target = root / "target"
        source.mkdir()
        target.mkdir()
        document["storages"][0]["rootPath"] = str(source)
        document["storages"][1]["rootPath"] = str(target)
        document["resourceLibraries"][0]["storagePath"] = ""
        document["resourceLibraries"][0]["displayRootPath"] = str(source)
        document["persistence"] = {"databasePath": str(root / "state.sqlite3")}
        document["historyPath"] = str(root / "history.jsonl")
        document["api"] = {"tokenEnv": "MEDIAFLOW_API_TOKEN"}
        config = root / "config.json"
        config.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        return config

    def test_cli_queue_worker_scan_reuses_workflow_with_zero_media_mutations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._configuration(directory)
            source = Path(directory, "source")
            media = source / "Movie.2025.mkv"
            media.write_bytes(b"unchanged")
            output, error = io.StringIO(), io.StringIO()
            self.assertEqual(
                final_main(
                    ["--config", str(config), "jobs", "submit", "scan", "--limit", "1"],
                    stdout=output,
                    stderr=error,
                ),
                0,
                error.getvalue(),
            )
            output = io.StringIO()
            self.assertEqual(
                final_main(
                    ["--config", str(config), "worker", "run-next"],
                    stdout=output,
                    stderr=error,
                ),
                0,
                error.getvalue(),
            )
            self.assertIn("Status: completed", output.getvalue())
            self.assertEqual(media.read_bytes(), b"unchanged")
            self.assertEqual(list(Path(directory, "target").iterdir()), [])

    def test_api_config_validation_does_not_require_secret(self) -> None:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        document["api"] = {"tokenEnv": "MEDIAFLOW_API_TOKEN"}
        loaded = load_runtime_configuration(copy.deepcopy(document))
        self.assertEqual(loaded.api_token_env, "MEDIAFLOW_API_TOKEN")
        document["api"] = {"tokenEnv": "invalid-name"}
        with self.assertRaisesRegex(ValueError, "API tokenEnv"):
            load_runtime_configuration(document)

    def test_api_startup_requires_configured_secret_without_leaking_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._configuration(directory)
            output, error = io.StringIO(), io.StringIO()
            with patch.dict("os.environ", {}, clear=True):
                code = final_main(
                    ["--config", str(config), "api", "serve"], stdout=output, stderr=error
                )
            self.assertEqual(code, 2)
            self.assertIn("MEDIAFLOW_API_TOKEN", error.getvalue())
            self.assertNotIn("Authorization", error.getvalue())


if __name__ == "__main__":
    unittest.main()
