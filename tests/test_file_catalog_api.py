from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import PersistentResultRecord
from mediaflow.infrastructure.sqlite_file_index import SQLiteFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_file_catalog import file_record

NOW = datetime(2026, 8, 23, 12, tzinfo=UTC)


def api_request(api, path: str, *, token="viewer-token", method="GET", query="", body=None):
    statuses = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": "0",
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(),
    }
    if body is not None:
        raw = json.dumps(body).encode("utf-8")
        environ["CONTENT_LENGTH"] = str(len(raw))
        environ["wsgi.input"] = io.BytesIO(raw)
    if token:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    body = b"".join(api(environ, lambda value, headers: statuses.append(value)))
    return int(statuses[0].split()[0]), json.loads(body)


class FileCatalogApiTests(unittest.TestCase):
    def test_files_endpoints_are_read_only_and_authenticated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteFileIndexRepository(database) as file_index:
                file_index.batch_upsert(
                    (file_record("one", "source-storage", "source", "Movies/A.mkv"),)
                )
            with SQLiteTaskRepository(database) as task_repository:
                task_repository.append_result(
                    PersistentResultRecord(
                        "result-1",
                        "task-1",
                        "item-1",
                        "source-storage",
                        "Movies/A.mkv",
                        "media",
                        "Media/Movies/A.mkv",
                        "C",
                        "tmdb",
                        "101",
                        "C",
                        "A",
                        "A",
                        "A",
                        "move",
                        "dry_run",
                        NOW,
                        title="Movie A",
                    )
                )
            with (
                SQLiteFileIndexRepository(database) as file_index,
                SQLiteTaskRepository(database) as task_repository,
            ):
                catalog = FileCatalogService(
                    file_index,
                    ("source",),
                    ("source-storage",),
                    task_repository=task_repository,
                )
                api = MediaFlowApi(
                    task_repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal(
                            "viewer",
                            "viewer-token",
                            frozenset({ApiPermission.READ, ApiPermission.SUBMIT_DRY_RUN}),
                        ),
                    ),
                    file_catalog=catalog,
                )
                status, document = api_request(api, "/api/v1/files")
                self.assertEqual(status, 200)
                self.assertEqual(document["items"][0]["fileId"], "one")
                status, document = api_request(
                    api,
                    "/api/v1/files",
                    query="scanStatus=ready&recognitionType=C&providerId=101&limit=10",
                )
                self.assertEqual(status, 200)
                self.assertEqual(document["items"][0]["fileId"], "one")
                status, _ = api_request(
                    api,
                    "/api/v1/files",
                    query="limit=10&limit=10",
                )
                self.assertEqual(status, 400)
                status, document = api_request(api, "/api/v1/files/one")
                self.assertEqual(status, 200)
                self.assertEqual(document["latestResult"]["providerId"], "101")
                status, _ = api_request(
                    api,
                    "/api/v1/files/one/re-recognize",
                    method="POST",
                )
                self.assertEqual(status, 400)
                status, _ = api_request(
                    api,
                    "/api/v1/files/one/re-plan",
                    method="POST",
                )
                self.assertEqual(status, 400)
                status, _ = api_request(
                    api,
                    "/api/v1/files/one/re-match",
                    method="POST",
                    body={},
                )
                self.assertEqual(status, 400)
                status, document = api_request(api, "/api/v1/files/stats")
                self.assertEqual(status, 200)
                self.assertEqual(document["total"], 1)
                status, document = api_request(api, "/api/v1/files", token=None)
                self.assertEqual(status, 401)
                status, _ = api_request(api, "/api/v1/files", method="POST")
                self.assertIn(status, {404, 405})


if __name__ == "__main__":
    unittest.main()
