#!/usr/bin/env python3
"""Isolated real-Python browser harness for the V2 run inventory (Task 42.1).

One process serves both the built V2 artifact (``/ui-v2/*`` through the
production static-serving boundary) and the real ``MediaFlowApi`` over one
temporary SQLite runtime database, so Playwright drives the exact packaged
Python stack instead of a Node fake. Every seeded run is created through a
real supported producer or the real Worker claim/linkage path:

- ``POST /api/v1/jobs`` admits a durable pending Job (pre-Task admission);
- ``PersistentTaskCoordinator.create`` creates standalone durable Tasks, the
  same coordinator every production task producer uses;
- ``repository.admit_job`` admits one definition-pinned Job the way the
  scheduler does, giving the scheduled trigger real evidence;
- ``AutomationWorker.run_next`` claims the pending Job and links its Task
  through the real ``complete_claimed_job`` write path.

Two test-only control routes exist for the browser journey (they are harness
infrastructure, not product endpoints, and never touch product documents):

- ``POST /__harness__/run-worker`` runs one real Worker claim + linkage;
- ``POST /__harness__/restart`` closes and reopens the runtime database and
  API object over the same file, which is exactly what a process restart does
  to durable state.

No production media, credential, Storage adapter, Provider or external service
is involved. The script fails fast when the built artifact is missing.
"""

from __future__ import annotations

import argparse
import dataclasses
import io
import json
import socketserver
import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mediaflow.application.automation import AutomationWorker  # noqa: E402
from mediaflow.application.task_runtime import PersistentTaskCoordinator  # noqa: E402
from mediaflow.domain.automation import (  # noqa: E402
    AutomationCommand,
    AutomationJob,
    AutomationJobStatus,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal  # noqa: E402
from mediaflow.domain.task_persistence import PersistentTaskStatus  # noqa: E402
from mediaflow.infrastructure.sqlite_runtime import (  # noqa: E402
    SCHEMA_VERSION,
    SQLiteTaskRepository,
)
from mediaflow.interfaces.service_api import MediaFlowApi  # noqa: E402
from mediaflow.interfaces.v2_ui import asset_root  # noqa: E402

HARNESS_TOKEN = "harness-viewer-token"
WORKER_ID = "harness-inventory-worker"

PRINCIPAL = ResolvedApiPrincipal(
    "harness",
    HARNESS_TOKEN,
    frozenset(
        {
            ApiPermission.READ,
            ApiPermission.SUBMIT_DRY_RUN,
            ApiPermission.CANCEL_JOB,
        }
    ),
)


class AppState:
    """The swap-able runtime objects; restart replaces both under one lock."""

    def __init__(self, database: Path) -> None:
        self._database = database
        self._lock = threading.Lock()
        self.repository = SQLiteTaskRepository(database)
        self.api = MediaFlowApi(self.repository, None, principals=(PRINCIPAL,))

    @property
    def database(self) -> Path:
        return self._database

    def restart(self) -> None:
        """Close and reopen the runtime database + API over the same file.

        Durable rows, pins, links and Worker registration survive exactly as
        they do across a process restart of the resident services.
        """

        with self._lock:
            self.repository.close()
            self.repository = SQLiteTaskRepository(self._database)
            self.api = MediaFlowApi(self.repository, None, principals=(PRINCIPAL,))
            # The registered Worker's heartbeat must stay claimable across a
            # harness restart; a real resident worker heartbeats continuously.
            worker = (
                self.repository.get_worker(WORKER_ID)
                if hasattr(self.repository, "get_worker")
                else None
            )
            if worker is not None:
                self.repository.heartbeat_worker(WORKER_ID, datetime.now(UTC))


STATE: AppState | None = None


def wsgi_request(
    app,
    method: str,
    path: str,
    *,
    query: str = "",
    body: dict | None = None,
    token: str = HARNESS_TOKEN,
) -> tuple[int, dict]:
    payload = json.dumps(body).encode("utf-8") if body is not None else b""
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(payload)),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
        "wsgi.input": io.BytesIO(payload),
    }
    raw = b"".join(app(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(raw)


def seed(database: Path) -> tuple[SQLiteTaskRepository, MediaFlowApi]:
    """Create one deterministic run population through real producers."""

    repository = SQLiteTaskRepository(database)
    api = MediaFlowApi(repository, None, principals=(PRINCIPAL,))

    # 1. A real durable Job admission: pending, pre-Task, no Worker yet.
    status, job_document = wsgi_request(api, "POST", "/api/v1/jobs", body={"command": "preview"})
    if status != 202:
        raise SystemExit(f"harness: job admission failed with {status}: {job_document}")

    # 2. A second Job, definition-pinned the way the scheduler admits one, so
    #    the scheduled trigger carries real admission evidence.
    now = datetime.now(UTC)
    scheduled = AutomationJob(
        "harness-scheduled-job",
        AutomationCommand.SCAN,
        AutomationJobStatus.PENDING,
        now + timedelta(seconds=1),
        now + timedelta(seconds=1),
        definition_id="harness-definition",
        resource_library_id="harness-library",
        source_scope="Movies",
    )
    repository.admit_job(scheduled, 100)

    # 3. Standalone durable Tasks through the production coordinator.
    coordinator = PersistentTaskCoordinator(repository, repository)
    coordinator.create(
        "scan",
        execute_authorized=False,
        scope_path="Movies/Harness",
    )
    failed_task = coordinator.create(
        "manual_organize",
        execute_authorized=True,
        scope_path="Movies/Harness/Failed",
    )
    # One bounded item failed before any success, so the progress pair stays
    # internally consistent exactly as a real failure publishes it.
    repository.update_task(
        dataclasses.replace(
            failed_task,
            status=PersistentTaskStatus.FAILED,
            completed_at=now + timedelta(seconds=2),
            total_items=1,
            completed_items=0,
            failed_items=1,
        )
    )
    return repository, api


def run_worker_once(state: AppState) -> dict:
    """One real Worker claim + Task linkage over the durable pending Job."""

    def handler(job, cancelled):
        coordinator = PersistentTaskCoordinator(state.repository, state.repository)
        task = coordinator.create(
            job.command.value,
            execute_authorized=False,
            scope_path="Movies/Harness/Linked",
        )
        if cancelled():
            return None
        return task.task_id

    worker = AutomationWorker(
        state.repository,
        handler,
        worker_id=WORKER_ID,
        label="harness-inventory-worker",
        runtime_schema_version=SCHEMA_VERSION,
    )
    claimed = worker.run_next()
    if claimed is None:
        return {"linked": False, "reason": "no claimable Job"}
    return {
        "linked": claimed.task_id is not None,
        "jobId": claimed.job_id,
        "taskId": claimed.task_id,
        "jobStatus": claimed.status.value,
    }


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - wsgiref API
        return


class ThreadingWSGIServer(socketserver.ThreadingMixIn, WSGIServer):
    daemon_threads = True


def application(environ, start_response):
    path = str(environ.get("PATH_INFO", ""))
    if path.startswith("/__harness__/") and STATE is not None:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        if path == "/__harness__/run-worker" and method == "POST":
            document = run_worker_once(STATE)
        elif path == "/__harness__/restart" and method == "POST":
            STATE.restart()
            document = {"restarted": True}
        elif path == "/__harness__/health" and method == "GET":
            document = {"status": "ok"}
        else:
            document = {"error": "harness route not found"}
        body = json.dumps(document).encode("utf-8")
        start_response(
            "200 OK" if "error" not in document else "404 Not Found",
            [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
            ],
        )
        return [body]
    return STATE.api(environ, start_response)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4183)
    parser.add_argument("--database", type=Path, default=None)
    args = parser.parse_args(argv)

    if not (asset_root() / "index.html").is_file():
        print(
            "harness: built V2 artifact is missing; run `npm --prefix web run build` first",
            file=sys.stderr,
        )
        return 2

    database = args.database or Path(tempfile_dir()) / "operations-inventory.sqlite3"
    global STATE
    STATE = AppState(database)
    seed(database)

    with make_server(
        args.host,
        args.port,
        application,
        server_class=ThreadingWSGIServer,
        handler_class=QuietHandler,
    ) as server:
        print(
            f"operations inventory harness: http://{args.host}:{args.port}/ui-v2/ "
            f"(database {database})",
            flush=True,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


def tempfile_dir() -> str:
    import tempfile

    return tempfile.mkdtemp(prefix="mediaflow-inventory-harness-")


if __name__ == "__main__":
    raise SystemExit(main())
