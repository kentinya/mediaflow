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

One of those coordinator-created Tasks also carries a rich, fully durable
detail population for the selected-run journey (Task 42.2): six ``TaskItem``
rows across five dispositions, two ``PersistentResultRecord`` rows (one
verified, one whose effects stay unverified), two operational logs and one
captured ``PipelineEvidence`` row, each written through the repository write
path its real producer uses — so 任务详情 progress, the server-filtered item
pages, 操作记录, one item's evidence and the result package export all serve
only durable SQLite rows, never fixture JSON.

Two test-only control routes exist for the browser journey (they are harness
infrastructure, not product endpoints, and never touch product documents):

- ``POST /__harness__/run-worker`` runs one real Worker claim + linkage;
- ``POST /__harness__/restart`` closes and reopens the runtime database and
  API object over the same file, which is exactly what a process restart does
  to durable state.

The run-detail result-package export is served by the shared package-exchange
authority; production wires it through the managed configuration service and
this harness deliberately has none, so it attaches the repository-only
instance (the result export reads durable Task/Result rows and writes one
best-effort audit row, while every configuration-dependent package route
still answers the same 503 it answered before).

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
from mediaflow.application.package_exchange import PackageExchangeService  # noqa: E402
from mediaflow.application.task_runtime import PersistentTaskCoordinator  # noqa: E402
from mediaflow.domain.automation import (  # noqa: E402
    AutomationCommand,
    AutomationJob,
    AutomationJobStatus,
)
from mediaflow.domain.failure import FailureExplanation  # noqa: E402
from mediaflow.domain.logging import LogLevel, OperationalLogRecord  # noqa: E402
from mediaflow.domain.media_evidence import EvidenceSection, PipelineEvidence  # noqa: E402
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal  # noqa: E402
from mediaflow.domain.task_persistence import (  # noqa: E402
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    TaskItemStatus,
)
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


def build_api(repository: SQLiteTaskRepository) -> MediaFlowApi:
    """One API object over the runtime repository, plus the export authority.

    The run-detail result-package export (``GET /api/v1/operations/runs/
    {id}/export``) is served by ``PackageExchangeService``, which production
    wires through the managed configuration service.  This harness runs with
    no Active configuration on purpose, so it attaches the repository-only
    instance: ``export_results`` reads only durable Task/Result rows and
    writes one best-effort audit row, and every configuration-dependent
    package route still refuses with the same 503 it answered before.
    """

    api = MediaFlowApi(repository, None, principals=(PRINCIPAL,))
    api._package_exchange = PackageExchangeService(None, repository)
    return api


class AppState:
    """The swap-able runtime objects; restart replaces both under one lock."""

    def __init__(self, database: Path) -> None:
        self._database = database
        self._lock = threading.Lock()
        self.repository = SQLiteTaskRepository(database)
        self.api = build_api(self.repository)

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
            self.api = build_api(self.repository)
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
    api = build_api(repository)

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
    # The Task ends FAILED after one bounded item failed before the rest, and
    # its admission counters describe the full durable item population the
    # detail journey reads, so the progress facts and the Task facts agree.
    repository.update_task(
        dataclasses.replace(
            failed_task,
            status=PersistentTaskStatus.FAILED,
            completed_at=now + timedelta(seconds=2),
            total_items=len(RICH_ITEMS),
            completed_items=2,
            failed_items=1,
        )
    )
    # 4. The rich selected-run detail population (RO-3) on that same real
    #    Task: items, Results, operational logs and captured evidence, every
    #    row written through its producer's own repository write path.
    seed_run_detail_population(repository, failed_task, now)
    return repository, api


#: One durable primary item of the rich run-detail population.  The six rows
#: together cover the dispositions an operator diagnoses in 任务详情: a
#: verified success, a success whose storage effect stayed unverified, a
#: failure with a bounded explanation, a waiting decision, a skip and the
#: untouched pending work of a Task that already failed.
@dataclasses.dataclass(frozen=True)
class RichItem:
    suffix: str
    status: TaskItemStatus
    stage: str
    attempts: int
    source_path: str
    destination_path: str | None
    plan_id: str | None
    error: str | None = None
    execution_status: str | None = None


#: Source/destination identities of the rich population: Storage-relative
#: only, so the Operations projection publishes them unchanged.
RICH_ITEMS: tuple[RichItem, ...] = (
    RichItem(
        "01",
        TaskItemStatus.SUCCESS,
        "completed",
        2,
        "Movies/Harness/Failed/Arrival 2016/Arrival.2016.2160p.mkv",
        "Movies/Arrival 2016/Arrival 2016.mkv",
        "harness-plan-01",
        execution_status="SUCCESS",
    ),
    RichItem(
        "02",
        TaskItemStatus.SUCCESS,
        "completed",
        1,
        "Movies/Harness/Failed/Blade Runner 1982/Blade.Runner.1982.1080p.mkv",
        "Movies/Blade Runner 1982/Blade Runner 1982.mkv",
        "harness-plan-02",
        execution_status="SUCCESS",
    ),
    RichItem(
        "03",
        TaskItemStatus.FAILED,
        "failed",
        2,
        "Movies/Harness/Failed/Dune 2021/Dune.2021.2160p.mkv",
        None,
        "harness-plan-03",
        error=FailureExplanation(
            category="destination_collision",
            message="the reviewed destination already exists",
            durable_state="no_media_moved",
            side_effects="none",
            retry_safe=True,
            next_action="resolve the destination conflict, then retry this item",
        ).encode(),
    ),
    RichItem(
        "04",
        TaskItemStatus.WAITING_CONFIRM,
        "waiting_confirm",
        1,
        "Movies/Harness/Failed/Heat 1995/Heat.1995.1080p.mkv",
        None,
        "harness-plan-04",
    ),
    RichItem(
        "05",
        TaskItemStatus.SKIPPED,
        "completed",
        1,
        "Movies/Harness/Failed/Sample 2020/Sample.2020.WEB-DL.mkv",
        None,
        None,
    ),
    RichItem(
        "06",
        TaskItemStatus.PENDING,
        "pipeline",
        0,
        "Movies/Harness/Failed/Pending 2021/Pending.2021.1080p.mkv",
        None,
        None,
    ),
)


def seed_run_detail_population(
    repository: SQLiteTaskRepository,
    task: PersistentTask,
    base: datetime,
) -> None:
    """Attach one rich, fully durable detail population to a real Task.

    Every row goes through the write path its real producer uses —
    ``upsert_item``, ``append_result``, ``append_operational_log`` and
    ``append_evidence`` — so the selected-run detail reads (the progress
    partition, the server-filtered item pages, the exactly-linked operation
    records, one item's evidence and the result package export) can only ever
    serve durable SQLite rows.  The timestamps are one deterministic window
    so the record stream keeps one stable newest-first order.
    """

    storage_id = "harness-storage"
    verified = f"{task.task_id}-01"
    uncertain = f"{task.task_id}-02"
    verified_source = "Movies/Harness/Failed/Arrival 2016/Arrival.2016.2160p.mkv"
    verified_target = "Movies/Arrival 2016/Arrival 2016.mkv"

    for index, spec in enumerate(RICH_ITEMS):
        occurred = base + timedelta(seconds=10 + index)
        repository.upsert_item(
            PersistentTaskItem(
                item_id=f"{task.task_id}-{spec.suffix}",
                task_id=task.task_id,
                storage_id=storage_id,
                resource_library_id="movies",
                source_path=spec.source_path,
                source_display=spec.source_path,
                status=spec.status,
                stage=spec.stage,
                attempts=spec.attempts,
                created_at=occurred,
                updated_at=occurred,
                plan_id=spec.plan_id,
                destination_storage_id=(storage_id if spec.destination_path is not None else None),
                destination_path=spec.destination_path,
                execution_status=spec.execution_status,
                error=spec.error,
            )
        )

    # Two Results: one whose move the executor verified end to end, one whose
    # effect stayed unverified — the progress split publishes them as one
    # confirmed success and one uncertain success that is never counted twice.
    repository.append_result(
        PersistentResultRecord(
            result_id=f"{task.task_id}-result-01",
            task_id=task.task_id,
            item_id=verified,
            source_storage_id=storage_id,
            source_path=verified_source,
            destination_storage_id=storage_id,
            destination_path=verified_target,
            recognition_type="C",
            provider="tmdb",
            provider_id="101",
            metadata_policy_id="C",
            naming_policy_id="A",
            classification_policy_id="A",
            organize_policy_id="A",
            operation="MOVE",
            status="SUCCESS",
            created_at=base + timedelta(seconds=20),
            title="Arrival",
            completed_operations=("MOVE",),
            effect_certainty="verified_complete",
        )
    )
    repository.append_result(
        PersistentResultRecord(
            result_id=f"{task.task_id}-result-02",
            task_id=task.task_id,
            item_id=uncertain,
            source_storage_id=storage_id,
            source_path=RICH_ITEMS[1].source_path,
            destination_storage_id=storage_id,
            destination_path=RICH_ITEMS[1].destination_path,
            recognition_type="C",
            provider="tmdb",
            provider_id="101",
            metadata_policy_id="C",
            naming_policy_id="A",
            classification_policy_id="A",
            organize_policy_id="A",
            operation="MOVE",
            status="SUCCESS",
            created_at=base + timedelta(seconds=21),
            title="Blade Runner",
            completed_operations=("MOVE",),
            effect_certainty="attempted_unverified",
            uncertain_effects=("mutation_outcome",),
        )
    )

    # One captured pipeline-evidence row (kind=evidence in 操作记录), plus the
    # plan-linked operational log the item-evidence read joins through its
    # persisted plan ID and a task-linked failure log (kind=log).
    repository.append_evidence(
        PipelineEvidence(
            evidence_id=f"{task.task_id}-evidence-01",
            task_id=task.task_id,
            item_id=verified,
            attempts=1,
            source_storage_id=storage_id,
            source_path=verified_source,
            captured_at=base + timedelta(seconds=22),
            configuration_snapshot_id=None,
            configuration_snapshot_digest=None,
            outcome="planned",
            sections={
                "parse": EvidenceSection(True, value={"titleCandidate": "Arrival", "year": 2016}),
                "recognition": EvidenceSection(True, value={"recognitionType": "C"}),
                "plan": EvidenceSection(True, value={"operation": "MOVE"}),
            },
        )
    )
    repository.append_operational_log(
        OperationalLogRecord(
            log_id=f"{task.task_id}-log-01",
            occurred_at=base + timedelta(seconds=23),
            level=LogLevel.INFO,
            component="organizer",
            event="organizer.execution_result",
            task_id=task.task_id,
            plan_id="harness-plan-01",
            status="SUCCESS",
        )
    )
    repository.append_operational_log(
        OperationalLogRecord(
            log_id=f"{task.task_id}-log-02",
            occurred_at=base + timedelta(seconds=24),
            level=LogLevel.ERROR,
            component="workflow",
            event="workflow.failed",
            task_id=task.task_id,
            status="failed",
        )
    )


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
