"""Task 43.3 — Automation inventory, execution records and truthful statistics.

These regressions drive the real ``MediaFlowApi`` over the real managed
configuration runtime, the real SQLite runtime repository and the real
Automation services. They prove the three read-model obligations the Task
delivers and nothing else:

- **RO-1 inventory/query/statistics**: every authorized Active and Draft-only
  definition is reachable through a bounded server query with search,
  enablement/source/state filters, a stable total ordering and a cursor bound to
  the exact filter state and reading principal. The four cards report the
  *full authorized admitted-run population* in the configured system timezone,
  with the month cohort, the clamped previous-period comparison and a terminal
  denominator that excludes active/waiting runs. No card is derived from the
  browser page, and an unavailable read/unknown denominator is never published
  as zero.
- **RO-5 execution records**: one deduplicated admitted-run population combining
  scheduled occurrences, manual Run once admissions and pre-Task failures. A
  Job that acquires its Task keeps one identity and one count. Every record is
  read-only and publishes its recovery ownership from durable evidence: a formal
  organizing Task (including one that failed during scanning/planning before any
  mutation) owns recovery in Task Center, a proven settled pre-start failure
  guides the existing supported command, and an ambiguous handoff forbids a
  start-again retry.
- **RO-7 read/navigation/failure**: invalid filters and cursors are rejected
  safely, a cursor minted for another principal/filter is refused, and passive
  reads create no Job, Task, Draft, grant, occurrence, Provider call or Storage
  effect.

No production media, credentials or external service is used.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.automation import (
    AutomationCommand,
    AutomationJob,
    AutomationJobStatus,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import (
    PersistentTask,
    PersistentTaskStatus,
)
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.pagination import decode_directional_cursor
from mediaflow.interfaces.service_api import MediaFlowApi

ADMIN_TOKEN = "automation-workspace-admin-token"
VIEWER_TOKEN = "automation-workspace-viewer-token"

DEFINITIONS_ROUTE = "/api/v1/operations/automation/task-definitions"
RECORDS_ROUTE = "/api/v1/operations/automation/records"
METRICS_ROUTE = "/api/v1/operations/automation/metrics"

SYSTEM_TIMEZONE = "Asia/Shanghai"

_DEFINITION = {
    "id": "auto-task",
    "name": "Nightly automation",
    "resourceLibraryId": "source",
    "mode": "automatic-organization",
    "intervalSeconds": 3600,
    "itemLimit": 12,
}

_NOW = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)


def _document(root: Path) -> dict:
    value = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
    value["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
    value["historyPath"] = str(root / "history.jsonl")
    value["storages"][0]["rootPath"] = str(root / "source")
    value["storages"][1]["rootPath"] = str(root / "target")
    value["timezone"] = SYSTEM_TIMEZONE
    value["automation"]["taskDefinitions"] = []
    value["api"]["principals"] = [
        {
            "id": "admin",
            "tokenEnv": "MEDIAFLOW_TEST_ADMIN_TOKEN",
            "roles": ["admin"],
            "enabled": True,
        }
    ]
    return value


def _request(
    api,
    path: str,
    *,
    method: str = "GET",
    body: object | None = None,
    token: str = ADMIN_TOKEN,
    query: str = "",
) -> tuple[int, object]:
    payload = b"" if body is None else json.dumps(body).encode("utf-8")
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(payload)),
        "wsgi.input": io.BytesIO(payload),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
    }
    result = b"".join(api(environ, lambda status, _headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(result)


def _task(
    task_id: str,
    *,
    status: PersistentTaskStatus = PersistentTaskStatus.COMPLETED,
    created_at: datetime = _NOW,
    command: str = AutomationCommand.ORGANIZE.value,
) -> PersistentTask:
    return PersistentTask(
        task_id,
        command,
        status,
        True,
        created_at,
        created_at,
        started_at=created_at,
        completed_at=created_at if status is PersistentTaskStatus.COMPLETED else None,
        total_items=2,
        completed_items=2 if status is PersistentTaskStatus.COMPLETED else 0,
        failed_items=0,
        scope_path="Media/电影",
        configuration_snapshot_id="revision-active",
        configuration_snapshot_digest="d" * 64,
    )


def _job(
    job_id: str,
    *,
    status: AutomationJobStatus = AutomationJobStatus.COMPLETED,
    created_at: datetime = _NOW,
    task_id: str | None = None,
    definition_id: str | None = None,
    schedule_id: str | None = None,
    failure_category: str | None = None,
    failure_next_action: str | None = None,
) -> AutomationJob:
    return AutomationJob(
        job_id,
        AutomationCommand.ORGANIZE,
        status,
        created_at,
        created_at,
        execute_authorized=True,
        task_id=task_id,
        definition_id=definition_id,
        schedule_id=schedule_id,
        failure_category=failure_category,
        failure_durable_state=("no_work_started" if failure_category else None),
        failure_side_effects=("none" if failure_category else None),
        failure_retry_safe=True if failure_category else None,
        failure_next_action=failure_next_action,
        resource_library_id="source",
        source_scope="Media/电影",
    )


class AutomationWorkspaceReadModelTests(unittest.TestCase):
    """One real managed runtime with real SQLite persistence."""

    @contextlib.contextmanager
    def _runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source" / "Media" / "电影").mkdir(parents=True)
            (root / "target").mkdir(parents=True)
            document = _document(root)
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as config_repo,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime,
            ):
                managed = ManagedConfigurationService(
                    config_repo,
                    bootstrap_database_path=str(root / "runtime.sqlite3"),
                )
                objects = ConfigurationObjectService(managed)
                draft = managed.import_draft(document, actor="tester")
                draft = objects.create_automation_task_definition(
                    draft.revision_id,
                    dict(_DEFINITION),
                    expected_version=draft.version,
                    actor="tester",
                )
                draft = objects.enable_automation_task_definition(
                    draft.revision_id,
                    _DEFINITION["id"],
                    expected_version=draft.version,
                    actor="tester",
                )
                validated = managed.validate(draft.revision_id, actor="tester")
                managed.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="tester",
                )
                api = MediaFlowApi(
                    runtime,
                    None,
                    principals=(
                        ResolvedApiPrincipal("admin", ADMIN_TOKEN, frozenset(ApiPermission)),
                        ResolvedApiPrincipal(
                            "viewer", VIEWER_TOKEN, frozenset({ApiPermission.READ})
                        ),
                    ),
                    configuration_service=managed,
                    bootstrap_document=document,
                )
                # One controlled evaluation instant for the metric calendar so
                # the cohort/month-boundary assertions are exact.
                api._automation_now = lambda: _NOW
                yield SimpleNamespace(
                    api=api,
                    managed=managed,
                    objects=objects,
                    runtime=runtime,
                    root=root,
                )

    # -- inventory query/paging/metrics -------------------------------------

    def test_inventory_reaches_every_authorized_definition_across_pages(self) -> None:
        with self._runtime() as value:
            page, cursor, identities = None, None, []
            while True:
                query = "limit=1" if cursor is None else f"limit=1&cursor={cursor}"
                status, page = _request(value.api, DEFINITIONS_ROUTE, query=query)
                self.assertEqual(status, 200)
                identities.extend(item["id"] for item in page["items"])
                self.assertEqual(page["total"], 1)
                self.assertEqual(page["metrics"]["scope"], "full_authorized_population")
                cursor = page["next_cursor"]
                if cursor is None:
                    break
            self.assertEqual(identities, [_DEFINITION["id"]])
            self.assertFalse(page["truncated"])
            self.assertFalse(page["itemsTruncatedByCap"])

    def test_inventory_filters_and_sort_are_server_side(self) -> None:
        with self._runtime() as value:
            # A Draft-only correction entry must stay reachable and labelled.
            status, created = _request(
                value.api,
                f"/api/v1/configuration/revisions/{value.managed.active().revision_id}/successor",
                method="POST",
                body={"expectedActiveRevisionId": value.managed.active().revision_id},
            )
            self.assertEqual(status, 201)
            status, _created_definition = _request(
                value.api,
                "/api/v1/automation/task-definitions",
                method="POST",
                body={
                    "revisionId": created["revisionId"],
                    "expectedVersion": created["version"],
                    "object": {
                        **_DEFINITION,
                        "id": "draft-task",
                        "name": "Draft only automation",
                    },
                },
            )
            self.assertEqual(status, 200)

            status, page = _request(value.api, DEFINITIONS_ROUTE, query="state=draft-only")
            self.assertEqual(status, 200)
            self.assertEqual([item["id"] for item in page["items"]], ["draft-task"])
            self.assertEqual(page["total"], 1)
            self.assertEqual(page["items"][0]["definitionState"], "draft-only")

            status, page = _request(value.api, DEFINITIONS_ROUTE, query="state=active")
            self.assertEqual([item["id"] for item in page["items"]], ["auto-task"])

            status, page = _request(value.api, DEFINITIONS_ROUTE, query="q=draft+only")
            self.assertEqual([item["id"] for item in page["items"]], ["draft-task"])

            status, page = _request(value.api, DEFINITIONS_ROUTE, query="enabled=true")
            self.assertEqual([item["id"] for item in page["items"]], ["auto-task"])

            status, page = _request(value.api, DEFINITIONS_ROUTE, query="library=missing")
            self.assertEqual(status, 200)
            self.assertEqual(page["items"], [])
            self.assertEqual(page["total"], 0)
            # A filtered empty population is distinct from an unavailable read.
            self.assertTrue(page["metrics"]["available"])

    def test_inventory_rejects_invalid_filters_and_foreign_cursors(self) -> None:
        with self._runtime() as value:
            for query in (
                "sort=unknown",
                "direction=sideways",
                "state=published",
                "enabled=maybe",
                "library=../etc",
                "limit=0",
                "limit=101",
                "unknown=1",
            ):
                with self.subTest(query=query):
                    status, body = _request(value.api, DEFINITIONS_ROUTE, query=query)
                    self.assertEqual(status, 400)
                    self.assertEqual(body["error"]["code"], "invalid_request")

            status, page = _request(value.api, DEFINITIONS_ROUTE, query="limit=1")
            self.assertIsNone(page["next_cursor"])

            # A definition cursor is principal- and filter-scoped.
            status, page = _request(value.api, DEFINITIONS_ROUTE, query="limit=1")
            self.assertEqual(status, 200)
            crafted = value.api._automation_inventory_cursor(
                [{"id": "auto-task"}],
                True,
                __import__(
                    "mediaflow.interfaces.pagination", fromlist=["CursorDirection"]
                ).CursorDirection.NEXT,
                "principal=other;kind=automation-definitions",
                "name",
            )
            self.assertIsNotNone(crafted)
            status, body = _request(value.api, DEFINITIONS_ROUTE, query=f"limit=1&cursor={crafted}")
            self.assertEqual(status, 400)
            self.assertEqual(body["error"]["code"], "invalid_request")

    def test_stale_page_boundary_is_a_recoverable_read(self) -> None:
        with self._runtime() as value:
            # A cursor minted for a boundary that has since left the submitted
            # population reports a bounded stale read with a refresh action —
            # never a silently different page and never a generic rejection.
            cursor = value.api._automation_inventory_cursor(
                [{"id": "vanished-task"}],
                True,
                __import__(
                    "mediaflow.interfaces.pagination", fromlist=["CursorDirection"]
                ).CursorDirection.NEXT,
                "principal=admin;kind=automation-definitions;q=;enabled=all;"
                "library=all;state=all;sort=name;direction=asc",
                "name",
            )
            self.assertIsNotNone(cursor)
            status, body = _request(value.api, DEFINITIONS_ROUTE, query=f"limit=1&cursor={cursor}")
            self.assertEqual(status, 409)
            self.assertEqual(body["error"]["code"], "stale_page")
            self.assertEqual(body["error"]["details"]["sideEffects"], "none")
            self.assertTrue(body["error"]["details"]["retrySafe"])

    # -- metrics ------------------------------------------------------------

    def test_metrics_use_the_system_calendar_and_terminal_denominator(self) -> None:
        with self._runtime() as value:
            zone = ZoneInfo(SYSTEM_TIMEZONE)
            # Two completed runs and one active run inside the current local
            # month; one cancelled run in the previous comparable period.
            current = datetime(2026, 3, 2, 1, 0, tzinfo=zone).astimezone(UTC)
            previous = datetime(2026, 2, 2, 1, 0, tzinfo=zone).astimezone(UTC)
            for index in range(2):
                value.runtime.create_task(
                    _task(
                        f"done-{index}",
                        created_at=current + timedelta(hours=index),
                    )
                )
            value.runtime.create_task(
                _task(
                    "active-1",
                    status=PersistentTaskStatus.RUNNING,
                    created_at=current + timedelta(hours=3),
                )
            )
            value.runtime.create_task(
                _task(
                    "cancelled-prev",
                    status=PersistentTaskStatus.CANCELLED,
                    created_at=previous,
                )
            )

            status, metrics = _request(value.api, METRICS_ROUTE)
            self.assertEqual(status, 200)
            self.assertEqual(metrics["scope"], "full_authorized_population")
            self.assertEqual(metrics["timezone"], SYSTEM_TIMEZONE)
            # Every admitted run in the month contributes to the count; active
            # work is reported separately and excluded from the denominator.
            self.assertEqual(metrics["monthToDateAdmitted"], 3)
            self.assertEqual(metrics["monthToDateTerminal"], 2)
            self.assertEqual(metrics["monthToDateActive"], 1)
            self.assertEqual(metrics["completedCount"], 2)
            self.assertEqual(metrics["successRate"], 1.0)
            self.assertEqual(metrics["previousPeriodAdmitted"], 1)
            self.assertTrue(metrics["comparisonAvailable"])
            # The windows are absolute UTC instants with their exact local
            # boundaries, so an operator can verify the calendar basis.
            self.assertIn("+00:00", metrics["windows"]["current"]["start"])
            self.assertIn("+08:00", metrics["windows"]["current"]["startLocal"])
            self.assertEqual(metrics["sideEffects"], "none")

    def test_metrics_never_fabricate_a_comparison_or_rate(self) -> None:
        with self._runtime() as value:
            status, metrics = _request(value.api, METRICS_ROUTE)
            self.assertEqual(status, 200)
            self.assertEqual(metrics["monthToDateAdmitted"], 0)
            self.assertEqual(metrics["monthToDateTerminal"], 0)
            self.assertEqual(metrics["previousPeriodAdmitted"], 0)
            self.assertFalse(metrics["comparisonAvailable"])
            self.assertEqual(
                metrics["comparisonUnavailableReason"],
                "no_comparable_previous_period",
            )
            # No denominator means no rate at all — never 0% or 100%.
            self.assertIsNone(metrics["successRate"])
            self.assertIn("no terminal admitted run", metrics["denominatorStatement"])
            self.assertTrue(metrics["available"])

    def test_metric_windows_clamp_the_previous_period_at_month_end(self) -> None:
        now = datetime(2026, 3, 31, 23, 30, tzinfo=UTC)
        windows = MediaFlowApi._automation_metric_windows(now, SYSTEM_TIMEZONE)
        previous = windows["previous"]
        self.assertLess(previous["end"], windows["current"]["start"])
        # The previous window never runs past the current month's start.
        self.assertLessEqual(previous["end"].astimezone(UTC), windows["current"]["start"])
        # DST and unequal month lengths are handled by the same local calendar.
        leap = MediaFlowApi._automation_metric_windows(
            datetime(2028, 3, 1, 0, 30, tzinfo=UTC), SYSTEM_TIMEZONE
        )
        self.assertEqual(leap["previous"]["start"].astimezone(ZoneInfo(SYSTEM_TIMEZONE)).day, 1)
        self.assertEqual(leap["previous"]["start"].astimezone(ZoneInfo(SYSTEM_TIMEZONE)).month, 2)

    def test_metric_calendar_uses_the_configured_system_zone_not_cron(self) -> None:
        with self._runtime() as value:
            self.assertEqual(value.api._automation_system_timezone(), SYSTEM_TIMEZONE)
            # A Cron definition's own timezone stays independent of the metric
            # calendar; nothing in the metric read consults a definition.
            status, page = _request(value.api, DEFINITIONS_ROUTE)
            self.assertEqual(status, 200)
            self.assertEqual(
                page["metrics"]["cronTimezoneNote"],
                "Cron definition timezones stay separate from this system calendar",
            )

    # -- execution records --------------------------------------------------

    def test_records_combine_scheduled_manual_and_prestart_runs_once(self) -> None:
        with self._runtime() as value:
            scheduled_task = _task("scheduled-task")
            value.runtime.create_task(scheduled_task)
            # The scheduled occurrence's Job acquired the same Task: the pair
            # must stay one identity with one count.
            value.runtime.create_job(
                _job(
                    "scheduled-job",
                    task_id="scheduled-task",
                    definition_id=_DEFINITION["id"],
                    schedule_id="schedule-1",
                )
            )
            # A deliberate Run once admission with its durable manual origin.
            from mediaflow.domain.task_persistence import RunDisplayContext

            value.runtime.create_task(
                _task("manual-task", created_at=_NOW - timedelta(minutes=1)),
                display=RunDisplayContext(
                    source_scope="Media/电影",
                    labels=("电影库",),
                    origin_definition_id=_DEFINITION["id"],
                    origin_definition_name="Nightly automation",
                    origin_kind="definition-run-once",
                ),
            )
            # A proven settled pre-start failure: no Task, a structured repair.
            value.runtime.create_job(
                _job(
                    "prestart-job",
                    status=AutomationJobStatus.FAILED,
                    created_at=_NOW - timedelta(minutes=2),
                    definition_id=_DEFINITION["id"],
                    schedule_id="schedule-1",
                    failure_category="unattended_execution_authority_missing",
                    failure_next_action="review the exact bounds and explicitly grant",
                )
            )

            status, page = _request(value.api, RECORDS_ROUTE)
            self.assertEqual(status, 200)
            self.assertEqual(page["total"], 3)
            self.assertEqual(page["sideEffects"], "none")
            records = {item["recordId"]: item for item in page["items"]}
            # One row per admitted run: the Job is the admission identity and
            # its linked Task appears as the same row's Task link.
            self.assertEqual(
                set(records),
                {"scheduled-job", "manual-task", "prestart-job"},
            )
            scheduled = records["scheduled-job"]
            self.assertEqual(scheduled["job_id"], "scheduled-job")
            self.assertEqual(scheduled["task_id"], "scheduled-task")
            self.assertEqual(scheduled["trigger"], "scheduled")
            self.assertEqual(scheduled["handoff"]["ownership"], "task_center")
            self.assertFalse(scheduled["handoff"]["startAgainAllowed"])

            manual = records["manual-task"]
            self.assertEqual(manual["trigger"], "manual")
            self.assertEqual(manual["historyContext"]["definitionId"], _DEFINITION["id"])
            self.assertEqual(manual["handoff"]["ownership"], "task_center")

            prestart = records["prestart-job"]
            self.assertEqual(prestart["trigger"], "scheduled")
            self.assertIsNone(prestart["task_id"])
            self.assertEqual(prestart["handoff"]["ownership"], "prestart_repair")
            self.assertFalse(prestart["handoff"]["formalExecution"])
            self.assertEqual(prestart["handoff"]["supportedCommand"], "scheduled-evaluation")
            self.assertFalse(prestart["handoff"]["startAgainAllowed"])
            self.assertIsNone(prestart["handoff"]["taskCenter"])

    def test_records_keep_a_formal_task_failure_before_mutation_in_task_center(self) -> None:
        with self._runtime() as value:
            # A Task exists, and it failed during planning: the first media
            # mutation never happened, yet the durable handoff already transferred
            # recovery ownership to Task Center.
            value.runtime.create_task(_task("planning-task", status=PersistentTaskStatus.FAILED))
            value.runtime.create_job(
                _job(
                    "planning-job",
                    task_id="planning-task",
                    definition_id=_DEFINITION["id"],
                    schedule_id="schedule-1",
                )
            )
            status, page = _request(value.api, RECORDS_ROUTE)
            self.assertEqual(status, 200)
            record = page["items"][0]
            self.assertEqual(record["handoff"]["ownership"], "task_center")
            self.assertTrue(record["handoff"]["formalExecution"])
            self.assertIsNotNone(record["handoff"]["taskCenter"])
            self.assertEqual(record["handoff"]["taskCenter"]["runId"], "planning-task")
            self.assertFalse(record["handoff"]["startAgainAllowed"])

    def test_records_do_not_offer_a_retry_for_queued_or_claimed_work(self) -> None:
        with self._runtime() as value:
            value.runtime.create_job(
                _job(
                    "queued-job",
                    status=AutomationJobStatus.PENDING,
                    definition_id=_DEFINITION["id"],
                    schedule_id="schedule-1",
                )
            )
            status, page = _request(value.api, RECORDS_ROUTE)
            self.assertEqual(status, 200)
            record = page["items"][0]
            self.assertEqual(record["handoff"]["ownership"], "reconcile")
            self.assertEqual(record["handoff"]["durableState"], "attempt_in_progress")
            self.assertFalse(record["handoff"]["startAgainAllowed"])
            self.assertIn("wait for this attempt to settle", record["handoff"]["retryExplanation"])

    def test_records_are_filtered_by_definition_trigger_and_outcome(self) -> None:
        with self._runtime() as value:
            value.runtime.create_task(_task("done-run"))
            value.runtime.create_job(
                _job(
                    "sched-run",
                    task_id="done-run",
                    definition_id=_DEFINITION["id"],
                    schedule_id="schedule-1",
                )
            )
            value.runtime.create_job(
                _job(
                    "unrelated-run",
                    task_id=None,
                    definition_id="other-definition",
                    schedule_id="schedule-2",
                )
            )

            status, page = _request(
                value.api,
                RECORDS_ROUTE,
                query=f"definition={_DEFINITION['id']}",
            )
            self.assertEqual(status, 200)
            self.assertEqual([item["recordId"] for item in page["items"]], ["sched-run"])
            self.assertEqual(page["total"], 1)

            status, page = _request(value.api, RECORDS_ROUTE, query="trigger=manual")
            self.assertEqual(status, 200)
            self.assertEqual(page["items"], [])

            status, page = _request(value.api, RECORDS_ROUTE, query="status=failed")
            self.assertEqual(status, 200)
            self.assertEqual(page["items"], [])

            for query in (
                "definition=../etc",
                "trigger=sometimes",
                "status=nope",
                "from=yesterday",
                "limit=101",
                "other=1",
            ):
                with self.subTest(query=query):
                    status, body = _request(value.api, RECORDS_ROUTE, query=query)
                    self.assertEqual(status, 400)
                    self.assertEqual(body["error"]["code"], "invalid_request")

    def test_record_cursors_are_principal_and_filter_scoped(self) -> None:
        with self._runtime() as value:
            for index in range(3):
                value.runtime.create_task(
                    _task(f"run-{index}", created_at=_NOW - timedelta(minutes=index))
                )
            status, first = _request(value.api, RECORDS_ROUTE, query="limit=1")
            self.assertEqual(status, 200)
            cursor = first["next_cursor"]
            self.assertIsNotNone(cursor)
            decoded = decode_directional_cursor(
                cursor,
                "operations_runs",
                expected_scope=(
                    "principal=admin;kind=automation-records;definition=all;"
                    "trigger=all;status=all;from=;to="
                ),
            )
            self.assertIsNotNone(decoded)
            # The identical filter state pages forward normally...
            status, second = _request(value.api, RECORDS_ROUTE, query=f"limit=1&cursor={cursor}")
            self.assertEqual(status, 200)
            self.assertNotEqual(
                [item["recordId"] for item in first["items"]],
                [item["recordId"] for item in second["items"]],
            )
            # ...while any different filter state refuses the replayed cursor.
            for query in (
                f"limit=1&status=failed&cursor={cursor}",
                f"limit=1&definition=auto-task&cursor={cursor}",
                f"limit=1&trigger=manual&cursor={cursor}",
            ):
                with self.subTest(query=query):
                    status, _body = _request(value.api, RECORDS_ROUTE, query=query)
                    self.assertEqual(status, 400)

    # -- passive reads ------------------------------------------------------

    def test_passive_reads_create_no_work_or_authority(self) -> None:
        with self._runtime() as value:
            before = {
                "jobs": value.runtime.active_automation_job_count(),
                "discoveries": value.runtime.list_media_discoveries(limit=100),
                "occurrences": value.runtime.list_automation_definition_occurrences(
                    _DEFINITION["id"], limit=100
                ),
                "tasks": value.runtime.list_tasks(limit=100),
            }
            for path, query in (
                (DEFINITIONS_ROUTE, ""),
                (DEFINITIONS_ROUTE, "q=nightly&enabled=true&sort=nextRun"),
                (METRICS_ROUTE, ""),
                (RECORDS_ROUTE, ""),
                (RECORDS_ROUTE, f"definition={_DEFINITION['id']}&trigger=scheduled"),
            ):
                with self.subTest(path=path, query=query):
                    status, _body = _request(value.api, path, query=query)
                    self.assertEqual(status, 200)
            self.assertEqual(before["jobs"], value.runtime.active_automation_job_count())
            self.assertEqual(before["discoveries"], value.runtime.list_media_discoveries(limit=100))
            self.assertEqual(
                before["occurrences"],
                value.runtime.list_automation_definition_occurrences(_DEFINITION["id"], limit=100),
            )
            self.assertEqual(before["tasks"], value.runtime.list_tasks(limit=100))
            # No Draft was created by any read.
            self.assertEqual(
                [draft.revision_id for draft in value.managed.open_draft_revisions()],
                [],
            )

    def test_records_read_is_authorized_and_never_leaks_secrets(self) -> None:
        with self._runtime() as value:
            value.runtime.create_job(
                _job(
                    "leaky-job",
                    status=AutomationJobStatus.FAILED,
                    definition_id=_DEFINITION["id"],
                    schedule_id="schedule-1",
                    failure_category="unattended_execution_authority_missing",
                    failure_next_action="grant the exact bounds",
                )
            )
            status, page = _request(value.api, RECORDS_ROUTE, token=VIEWER_TOKEN)
            self.assertEqual(status, 200)
            text = json.dumps(page).lower()
            for forbidden in ("bearer ", "api_key", "apikey", "authorization:"):
                self.assertNotIn(forbidden, text)
            # A read principal without a token is refused.
            statuses: list[str] = []
            body = b"".join(
                value.api(
                    {
                        "REQUEST_METHOD": "GET",
                        "PATH_INFO": RECORDS_ROUTE,
                        "QUERY_STRING": "",
                        "CONTENT_LENGTH": "0",
                        "wsgi.input": io.BytesIO(b""),
                        "REMOTE_ADDR": "127.0.0.1",
                    },
                    lambda status, _headers: statuses.append(status),
                )
            )
            self.assertEqual(int(statuses[0].split()[0]), 401)
            self.assertIn("unauthorized", json.loads(body)["error"]["code"])

    def test_run_once_history_filters_before_the_bounded_window(self) -> None:
        """The definition filter is part of the SQL predicate, before LIMIT.

        A definition's older Run once admissions must stay reachable even when
        other definitions have newer admissions: filtering the newest N rows in
        Python silently dropped this definition's history as soon as any other
        definition ran later.
        """

        from dataclasses import replace

        from mediaflow.domain.media_discovery import (
            DefinitionRunOnceOrigin,
            DiscoveryBudgets,
            DiscoveryCounters,
            DiscoveryEntryKind,
            DiscoveryIncompleteReason,
            DiscoveryProgress,
            DiscoveryScopeEntry,
            DiscoveryStatus,
            MediaDiscovery,
        )

        def discovery(discovery_id: str, definition_id: str, at: datetime):
            origin = DefinitionRunOnceOrigin(
                definition_id,
                f"{definition_id} name",
                "f" * 64,
                "revision-active",
                1,
                "d" * 64,
                "source",
                None,
                5,
                5,
            )
            return MediaDiscovery(
                discovery_id,
                "admin",
                "source",
                "source-storage",
                "revision-active",
                "d" * 64,
                DiscoveryStatus.COMPLETED,
                1,
                replace(DiscoveryBudgets(), max_primary_sources=5),
                DiscoveryProgress(
                    "completed",
                    (DiscoveryScopeEntry("Media", DiscoveryEntryKind.DIRECTORY),),
                    DiscoveryCounters(),
                    DiscoveryIncompleteReason.NONE,
                    (),
                    (),
                ),
                at,
                at,
                definition_origin=origin,
            )

        with self._runtime() as value:
            for index in range(5):
                value.runtime.create_media_discovery(
                    discovery(
                        f"other-{index}",
                        "other-definition",
                        _NOW + timedelta(minutes=index),
                    )
                )
            value.runtime.create_media_discovery(discovery("wanted-run", _DEFINITION["id"], _NOW))

            # A one-row window now returns this definition's own newest
            # admission instead of an empty result from other definitions.
            found = value.runtime.list_definition_run_once_discoveries(_DEFINITION["id"], limit=1)
            self.assertEqual([item.discovery_id for item in found], ["wanted-run"])

            # The other definition's history keeps its own bounded window.
            other = value.runtime.list_definition_run_once_discoveries("other-definition", limit=2)
            self.assertEqual([item.discovery_id for item in other], ["other-4", "other-3"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
