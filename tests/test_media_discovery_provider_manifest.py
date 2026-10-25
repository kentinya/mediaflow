"""Task 44.7 production-reachability regressions for the bounded manifest.

These cases reproduce the two current production journeys B and A independently
established, without runtime policy injection and without replacing
``Storage.list_page`` on a fake adapter:

* the real managed OpenList HTTP client/adapter (bounded loopback HTTP server)
  returning the same ordinary filename on two non-atomic pages;
* the real OpenList HTTP parser/adapter accepting a basename ``../Outside/...``
  that must never become an intent and must never raise an uncaught exception.

They use validated/activated managed configuration, real SQLite, the production
runtime/Storage construction and the authenticated discovery/finalize APIs.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mediaflow.application.configuration_snapshot import ManagedConfigurationService  # noqa: E402
from mediaflow.application.manual_organize import ManualOrganizeIntentService  # noqa: E402
from mediaflow.application.media_discovery import MediaDiscoveryService  # noqa: E402
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal  # noqa: E402
from mediaflow.infrastructure.sqlite_configuration_management import (  # noqa: E402
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository  # noqa: E402
from mediaflow.interfaces.service_api import MediaFlowApi  # noqa: E402
from tests.test_media_discovery import (  # noqa: E402
    OPERATOR_TOKEN,
    _activate,
    _DiscoveryFixture,
)

TOKEN_ENV = "MEDIAFLOW_TASK44_7_OPENLIST_TOKEN"


class _OpenListServer:
    """A bounded loopback OpenList v4 server with one injected entry."""

    def __init__(self, *, entry_name: str, total: int = 1) -> None:
        self.calls: list[dict[str, object]] = []
        self._entry_name = entry_name
        self._total = total
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:  # noqa: D102
                pass

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length) or b"{}")
                server.calls.append({"endpoint": self.path, "body": body})
                entry = {
                    "name": server._entry_name,
                    "size": 1024,
                    "is_dir": False,
                    "modified": "2020-01-01T00:00:00Z",
                }
                if self.path == "/api/fs/get":
                    # ``stat`` of the selected directory must resolve to a real
                    # directory, exactly like the provider's own metadata.
                    if str(body.get("path", "")).rstrip("/") == "/Movies":
                        entry = {
                            "name": "Movies",
                            "size": 0,
                            "is_dir": True,
                            "modified": "2020-01-01T00:00:00Z",
                        }
                    data: object = entry
                elif self.path == "/api/fs/list":
                    data = {"content": [entry], "total": server._total}
                else:  # pragma: no cover - the discovery stage calls only these
                    self.send_error(404)
                    return
                raw = json.dumps({"code": 200, "message": "success", "data": data}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}"

    def __enter__(self) -> _OpenListServer:
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._server.shutdown()
        self._server.server_close()


class ManagedOpenListDiscoveryTests(_DiscoveryFixture):
    """The production OpenList client/adapter through managed configuration."""

    def _journey(self, server: _OpenListServer):
        document = self.document()
        # Keep the existing Local ``target`` Storage so the configured
        # MediaLibraries stay valid; only the ResourceLibrary source becomes the
        # real OpenList HTTP adapter.
        document["storages"][0] = {
            "id": "source",
            "name": "Source",
            "type": "openlist",
            "rootPath": "/",
            "baseUrl": server.base_url,
            "tokenEnv": TOKEN_ENV,
            "pageSize": 1,
            "maxRetries": 0,
            "enabled": True,
        }
        return document

    def _run(self, server: _OpenListServer):
        """Open the real SQLite/managed runtime and admit one discovery.

        Yields the live services so the caller can drive the Worker and finalize
        while the repositories are still open, exactly like the resident process.
        """

        previous = os.environ.get(TOKEN_ENV)
        os.environ[TOKEN_ENV] = "synthetic-loopback-token"
        try:
            document = self._journey(server)
            with (
                SQLiteConfigurationRepository(self.database) as configuration_repository,
                SQLiteTaskRepository(self.database) as repository,
            ):
                managed = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(self.database),
                )
                revision = _activate(managed, document)
                intents = ManualOrganizeIntentService(repository, managed)
                discovery = MediaDiscoveryService(
                    repository, intents, configuration_service=managed
                )
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(
                        ResolvedApiPrincipal(
                            "operator",
                            OPERATOR_TOKEN,
                            frozenset(
                                {
                                    ApiPermission.READ,
                                    ApiPermission.MANAGE_MANUAL_ORGANIZE,
                                    ApiPermission.EXECUTE_MANUAL_ORGANIZE,
                                }
                            ),
                        ),
                    ),
                    configuration_service=managed,
                    manual_intent_service=intents,
                    media_discovery_service=discovery,
                )
                value = SimpleNamespace(
                    api=api, discovery=discovery, repository=repository, revision=revision
                )
                status, admitted = self.request(
                    value,
                    "/api/v1/resource-libraries/library/files/discoveries",
                    "POST",
                    {"paths": ["Movies"]},
                )
                self.assertEqual(202, status, admitted)
                yield value, admitted
        finally:
            if previous is None:
                os.environ.pop(TOKEN_ENV, None)
            else:
                os.environ[TOKEN_ENV] = previous

    def test_non_atomic_repeated_pages_freeze_one_source_and_one_intent(self) -> None:
        """B's current production reproduction: the same filename on both pages."""

        with _OpenListServer(entry_name="A.2001.mkv", total=2) as server:
            for value, admitted in self._run(server):
                settled = self.run_discovery(value)
                self.assertEqual("completed", settled["status"], settled)
                self.assertEqual(
                    ["Movies/A.2001.mkv"], [item["path"] for item in settled["sources"]], settled
                )
                self.assertEqual(1, settled["progress"]["primarySources"], settled)
                self.assertTrue(settled["actions"]["finalize"]["available"], settled)
                status, frozen = self.request(
                    value,
                    f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                    "POST",
                    {"expectedVersion": settled["version"]},
                )
                self.assertEqual(201, status, frozen)
                self.assertIsNone(frozen["failure"], frozen)
                intent = value.repository.get_manual_intent(frozen["intentId"])
                self.assertEqual(["Movies/A.2001.mkv"], [item.source.path for item in intent.items])
                # The production HTTP client was really exercised.
                endpoints = [call["endpoint"] for call in server.calls]
                self.assertIn("/api/fs/list", endpoints)

    def test_unsafe_basename_publishes_a_durable_refusal(self) -> None:
        """B's current production reproduction: a traversal basename."""

        with _OpenListServer(entry_name="../Outside/B.2002.mkv") as server:
            for value, admitted in self._run(server):
                settled = self.run_discovery(value)
                self.assertEqual("partial_success", settled["status"], settled)
                self.assertEqual("unsafe_entry", settled["progress"]["incompleteReason"], settled)
                self.assertEqual(["unsafe_entry"], settled["progress"]["refusalReasons"], settled)
                self.assertEqual([], settled["sources"], settled)
                self.assertFalse(settled["actions"]["finalize"]["available"], settled)
                self.assertEqual(
                    "discovery_budget_limited", settled["actions"]["finalize"]["refusal"]
                )
                status, refused = self.request(
                    value,
                    f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}/finalize",
                    "POST",
                    {"expectedVersion": settled["version"]},
                )
                self.assertEqual(409, status, refused)
                self.assertEqual("discovery_budget_limited", refused["error"]["code"])
                self.assertIsNone(refused.get("intentId"))
                # RO-2 admits the organizing Task before the walk, so the assertion
                # is that no *item* was ever produced from this budget-refused walk
                # — not that no Task row exists.
                for task in value.repository.list_tasks(limit=20):
                    self.assertEqual((), value.repository.list_items(task.task_id))
                # Only bounded metadata reads reached the provider.
                endpoints = {call["endpoint"] for call in server.calls}
                self.assertTrue(endpoints.issubset({"/api/fs/list", "/api/fs/get"}), endpoints)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
