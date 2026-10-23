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
import dataclasses
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
from mediaflow.domain.manual_recovery import (
    ManualRecoveryPreparation,
    ManualRecoveryPreparationStatus,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskStatus,
    RunDisplayContext,
    TaskItemStatus,
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


def _run_item(
    task_id: str,
    item_id: str,
    status: TaskItemStatus,
    *,
    created_at: datetime = _NOW,
) -> PersistentTaskItem:
    return PersistentTaskItem(
        item_id=item_id,
        task_id=task_id,
        storage_id="source-storage",
        resource_library_id="source",
        source_path=f"Media/电影/{item_id}.mkv",
        source_display=f"Media/电影/{item_id}.mkv",
        status=status,
        stage="organizing",
        attempts=1,
        created_at=created_at,
        updated_at=created_at,
        destination_storage_id="target-storage" if status is TaskItemStatus.SUCCESS else None,
        destination_path=(f"Movies/{item_id}.mkv" if status is TaskItemStatus.SUCCESS else None),
    )


def _run_result(
    task_id: str,
    item_id: str,
    *,
    created_at: datetime = _NOW,
    effect_certainty: str = "verified_complete",
    status: str = "success",
) -> PersistentResultRecord:
    return PersistentResultRecord(
        f"result-{item_id}",
        task_id,
        item_id,
        "source-storage",
        f"Media/电影/{item_id}.mkv",
        "target-storage" if status == "success" else None,
        f"Movies/{item_id}.mkv" if status == "success" else None,
        "C",
        "tmdb",
        "603",
        None,
        "A",
        "A",
        None,
        "MOVE",
        status,
        created_at,
        title="Example",
        effect_certainty=effect_certainty,
        primary_completed=status == "success",
    )


def _bare_discovery(discovery_id: str, created_at: datetime):
    """A preparation-only bounded discovery with no linked Task and no origin."""

    from mediaflow.domain.media_discovery import (
        DiscoveryBudgets,
        DiscoveryCounters,
        DiscoveryEntryKind,
        DiscoveryIncompleteReason,
        DiscoveryProgress,
        DiscoveryScopeEntry,
        DiscoveryStatus,
        MediaDiscovery,
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
        DiscoveryBudgets(),
        DiscoveryProgress(
            "completed",
            (DiscoveryScopeEntry("Media", DiscoveryEntryKind.DIRECTORY),),
            DiscoveryCounters(),
            DiscoveryIncompleteReason.NONE,
            (),
            (),
        ),
        created_at,
        created_at,
    )


class AutomationWorkspaceReadModelTests(unittest.TestCase):
    """One real managed runtime with real SQLite persistence."""

    def _admitted_automation_run(
        self,
        value,
        identity: str,
        *,
        created_at: datetime = _NOW,
        status: PersistentTaskStatus = PersistentTaskStatus.COMPLETED,
        job_status: AutomationJobStatus = AutomationJobStatus.COMPLETED,
        succeeded_items: int = 0,
        uncertain_items: int = 0,
        definition_id: str = _DEFINITION["id"],
        schedule_id: str = "schedule-1",
    ) -> None:
        """One real original Automation admission: Job + its admitted Task.

        The Job carries the durable ``definition_id``/``schedule_id`` identity a
        Scheduler emission writes, and its Task carries durable ``success``
        items whose Results prove the effect — the exact evidence the cards and
        the record rows must read instead of treating a finished queue row as
        organized work.
        """

        task_id = f"{identity}-task"
        value.runtime.create_task(
            _task(task_id, status=status, created_at=created_at),
            display=RunDisplayContext(
                source_scope="Media/电影",
                labels=("电影库",),
            ),
        )
        value.runtime.create_job(
            _job(
                f"{identity}-job",
                status=job_status,
                created_at=created_at,
                task_id=task_id,
                definition_id=definition_id,
                schedule_id=schedule_id,
            )
        )
        for index in range(succeeded_items):
            item_id = f"{identity}-ok-{index}"
            value.runtime.upsert_item(
                _run_item(task_id, item_id, TaskItemStatus.SUCCESS, created_at=created_at)
            )
            value.runtime.append_result(_run_result(task_id, item_id, created_at=created_at))
        for index in range(uncertain_items):
            item_id = f"{identity}-uncertain-{index}"
            value.runtime.upsert_item(
                _run_item(task_id, item_id, TaskItemStatus.SUCCESS, created_at=created_at)
            )
            value.runtime.append_result(
                _run_result(
                    task_id,
                    item_id,
                    created_at=created_at,
                    effect_certainty="attempted_unverified",
                )
            )

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
            # month; one cancelled run in the previous comparable period.  Each
            # one is a *real original Automation admission* (a Scheduler-style
            # definition-pinned Job with its own admitted Task and durable
            # successful item evidence) rather than an unrelated standalone
            # Task: an ordinary Files/CLI or manual organize Task is not
            # Automation work and must never move these cards.
            current = datetime(2026, 3, 2, 1, 0, tzinfo=zone).astimezone(UTC)
            previous = datetime(2026, 2, 2, 1, 0, tzinfo=zone).astimezone(UTC)
            for index in range(2):
                admitted_at = current + timedelta(hours=index)
                self._admitted_automation_run(
                    value,
                    f"done-{index}",
                    created_at=admitted_at,
                    succeeded_items=2,
                )
            self._admitted_automation_run(
                value,
                "active-1",
                created_at=current + timedelta(hours=3),
                status=PersistentTaskStatus.RUNNING,
                job_status=AutomationJobStatus.RUNNING,
            )
            self._admitted_automation_run(
                value,
                "cancelled-prev",
                created_at=previous,
                status=PersistentTaskStatus.CANCELLED,
                job_status=AutomationJobStatus.CANCELLED,
            )
            # Unrelated non-Automation work that must not contribute at all.
            value.runtime.create_task(_task("files-run", created_at=current + timedelta(hours=4)))
            value.runtime.create_job(_job("plain-job", created_at=current + timedelta(hours=5)))

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
                self._admitted_automation_run(
                    value,
                    f"run-{index}",
                    created_at=_NOW - timedelta(minutes=index),
                    succeeded_items=1,
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

    # -- R1: original Automation admissions only ----------------------------

    def test_records_and_metrics_exclude_non_automation_work(self) -> None:
        """Only original Automation admissions count as Automation runs.

        An ordinary Files/CLI Job, a standalone manual organize Task, a
        preparation-only discovery and a recovery follow-up Task belong to
        other journeys and must never appear in the Automation records page,
        its totals or the four cards.  The same mixed population keeps the one
        genuine scheduled admission fully visible.
        """

        with self._runtime() as value:
            # Genuine original Automation admission.
            self._admitted_automation_run(
                value,
                "scheduled",
                created_at=_NOW - timedelta(hours=5),
                succeeded_items=2,
            )
            # Ordinary Files/CLI Job (no definition/schedule identity).
            value.runtime.create_job(
                _job("plain-files-job", created_at=_NOW - timedelta(minutes=1))
            )
            # Standalone manual organize Task (execute-authorized, no origin).
            value.runtime.create_task(
                _task(
                    "manual-organize-task",
                    created_at=_NOW - timedelta(minutes=2),
                    command="manual_organize",
                )
            )
            # A preparation-only discovery carries no Task and no definition
            # origin of its own shape here: it is a bare discovery admission.
            value.runtime.create_media_discovery(
                _bare_discovery("preparation-discovery", _NOW - timedelta(minutes=3))
            )
            # A Task Center recovery continuation Job (no definition identity).
            value.runtime.create_job(
                _job(
                    "recovery-continuation-job",
                    created_at=_NOW - timedelta(minutes=4),
                )
            )

            status, page = _request(value.api, RECORDS_ROUTE)
            self.assertEqual(status, 200)
            self.assertEqual(page["total"], 1)
            self.assertEqual([item["recordId"] for item in page["items"]], ["scheduled-job"])
            # The status partitions describe the same restricted population.
            self.assertEqual(sum(page["statusCounts"].values()), 1)

            status, metrics = _request(value.api, METRICS_ROUTE)
            self.assertEqual(status, 200)
            self.assertEqual(metrics["monthToDateAdmitted"], 1)
            self.assertEqual(metrics["monthToDateTerminal"], 1)
            self.assertEqual(metrics["completedCount"], 1)
            self.assertEqual(metrics["successRate"], 1.0)

    def test_completed_queue_row_is_not_counted_as_organized_success(self) -> None:
        """A finished admission without proven item success is no success.

        A definition-pinned Job whose linked Task completed with zero durable
        ``success`` items is a *successful no-work completion*, not organized
        work; a Task whose success item still carries an uncertain latest Result
        is terminal-uncertain and never proves success.  Both stay in the
        denominator and are published with their real meaning.
        """

        with self._runtime() as value:
            self._admitted_automation_run(
                value,
                "no-work",
                created_at=_NOW - timedelta(hours=5),
                succeeded_items=0,
            )
            self._admitted_automation_run(
                value,
                "uncertain",
                created_at=_NOW - timedelta(minutes=1),
                succeeded_items=0,
                uncertain_items=1,
            )
            self._admitted_automation_run(
                value,
                "organized",
                created_at=_NOW - timedelta(minutes=2),
                succeeded_items=1,
            )

            status, metrics = _request(value.api, METRICS_ROUTE)
            self.assertEqual(status, 200)
            self.assertEqual(metrics["monthToDateAdmitted"], 3)
            self.assertEqual(metrics["monthToDateTerminal"], 3)
            self.assertEqual(metrics["completedCount"], 1)
            self.assertEqual(metrics["noWorkCount"], 1)
            self.assertEqual(metrics["monthToDateUncertain"], 1)
            self.assertAlmostEqual(metrics["successRate"], 1 / 3)

            status, page = _request(value.api, RECORDS_ROUTE)
            self.assertEqual(status, 200)
            records = {item["recordId"]: item for item in page["items"]}
            no_work = records["no-work-job"]["result"]
            self.assertFalse(no_work["organized"])
            self.assertTrue(no_work["noWork"])
            self.assertIn("没有产生已整理的条目", no_work["statement"])
            organized = records["organized-job"]["result"]
            self.assertTrue(organized["organized"])
            self.assertEqual(organized["successItems"], 1)
            uncertain = records["uncertain-job"]["result"]
            self.assertFalse(uncertain["organized"])
            self.assertEqual(uncertain["uncertainSuccessItems"], 1)

    # -- R3: result/reason and separate handling state ----------------------

    def test_record_reports_real_execution_window_and_reason(self) -> None:
        with self._runtime() as value:
            # A real started/finished execution window on the Job.
            started = _NOW - timedelta(minutes=9)
            finished = _NOW - timedelta(minutes=7)
            value.runtime.create_job(
                dataclasses.replace(
                    _job(
                        "windowed-job",
                        status=AutomationJobStatus.FAILED,
                        created_at=_NOW,
                        definition_id=_DEFINITION["id"],
                        schedule_id="schedule-1",
                    ),
                    started_at=started,
                    completed_at=finished,
                )
            )
            status, page = _request(value.api, RECORDS_ROUTE)
            self.assertEqual(status, 200)
            record = page["items"][0]
            self.assertEqual(record["executionStartedAt"], started.isoformat())
            self.assertEqual(record["executionFinishedAt"], finished.isoformat())
            # The admission timestamps stay distinct from the execution window.
            self.assertNotEqual(record["created_at"], record["executionStartedAt"])

    def test_pending_record_publishes_no_fake_execution_window(self) -> None:
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
            self.assertIsNone(record["executionStartedAt"])
            self.assertIsNone(record["executionFinishedAt"])
            # The row carries a real created_at, but it is never relabelled.
            self.assertTrue(record["created_at"])

    def test_record_handling_is_separate_from_the_original_result(self) -> None:
        with self._runtime() as value:
            self._admitted_automation_run(
                value,
                "failed-then-handled",
                created_at=_NOW,
                status=PersistentTaskStatus.FAILED,
                job_status=AutomationJobStatus.FAILED,
                succeeded_items=1,
            )
            status, page = _request(value.api, RECORDS_ROUTE)
            self.assertEqual(status, 200)
            record = page["items"][0]
            # The original failed outcome stays a historical fact.
            self.assertEqual(record["status"], "failed")
            self.assertFalse(record["result"]["organized"])
            # No linked follow-up exists, so handling is honestly "unhandled"
            # rather than inferred from the current Task status.
            self.assertEqual(record["handling"]["state"], "unhandled")
            self.assertEqual(record["handling"]["attempts"], 0)
            self.assertEqual(record["handoff"]["ownership"], "task_center")
            self.assertIsNotNone(record["nextAction"])
            self.assertEqual(record["nextAction"]["kind"], "task-center-run")

    # -- R2: full-population definition cards -------------------------------

    def test_inventory_cards_use_full_population_aggregates(self) -> None:
        """Published/enabled/Draft counts never come from the current page.

        Twenty-five Active definitions plus two Draft-only corrections and a
        filter that matches nothing still report the same full-population
        aggregates, so a paged or filtered read cannot change the cards.
        """

        with self._runtime() as value:
            active = value.managed.active()
            draft = value.managed.create_successor_draft(actor="tester")
            # The one seeded definition is already Active and enabled; these 24
            # make 25 published definitions in the exact current Active.
            for index in range(24):
                draft = value.objects.create_automation_task_definition(
                    draft.revision_id,
                    {
                        "id": f"auto-{index:02d}",
                        "name": f"Automation {index:02d}",
                        "resourceLibraryId": "source",
                        "mode": "automatic-organization",
                        "intervalSeconds": 3600,
                        "itemLimit": 5,
                    },
                    expected_version=draft.version,
                    actor="tester",
                )
            validated = value.managed.validate(draft.revision_id, actor="tester")
            value.managed.activate(
                validated.revision_id,
                expected_version=validated.version,
                actor="tester",
            )
            # Two further Draft-only correction entries in a fresh successor.
            successor = value.managed.create_successor_draft(actor="tester")
            for identity in ("draft-only-a", "draft-only-b"):
                successor = value.objects.create_automation_task_definition(
                    successor.revision_id,
                    {
                        "id": identity,
                        "name": identity,
                        "resourceLibraryId": "source",
                        "mode": "automatic-organization",
                        "intervalSeconds": 3600,
                        "itemLimit": 5,
                    },
                    expected_version=successor.version,
                    actor="tester",
                )
            self.assertIsNotNone(active)

            status, unfiltered = _request(value.api, DEFINITIONS_ROUTE, query="limit=20")
            self.assertEqual(status, 200)
            counts = unfiltered["inventoryCounts"]
            self.assertEqual(counts["published"], 25)
            self.assertEqual(counts["draftOnly"], 2)
            self.assertEqual(counts["total"], 27)
            self.assertLessEqual(len(unfiltered["items"]), 20)

            # A filter that matches nothing must not zero the cards.
            status, filtered = _request(value.api, DEFINITIONS_ROUTE, query="q=no-such-definition")
            self.assertEqual(status, 200)
            self.assertEqual(filtered["items"], [])
            self.assertEqual(filtered["inventoryCounts"], counts)
            self.assertEqual(filtered["metrics"]["inventory"], counts)

            # Paging to the second page keeps the same aggregates.
            status, second = _request(
                value.api,
                DEFINITIONS_ROUTE,
                query=f"limit=20&cursor={unfiltered['next_cursor']}",
            )
            self.assertEqual(status, 200)
            self.assertEqual(second["inventoryCounts"], counts)

    def test_inventory_latest_run_merges_manual_history(self) -> None:
        """A manual-only definition reports its real latest admitted run."""

        with self._runtime() as value:
            value.runtime.create_task(
                _task("manual-task", created_at=_NOW),
                display=RunDisplayContext(
                    source_scope="Media/电影",
                    labels=("电影库",),
                    origin_definition_id=_DEFINITION["id"],
                    origin_definition_name="Nightly automation",
                    origin_kind="definition-run-once",
                ),
            )
            status, page = _request(value.api, DEFINITIONS_ROUTE)
            self.assertEqual(status, 200)
            latest = page["latestAdmittedRuns"][_DEFINITION["id"]]
            self.assertEqual(latest["runId"], "manual-task")
            self.assertEqual(latest["trigger"], "manual")
            self.assertEqual(latest["admittedAt"], _NOW.isoformat())

    # -- R4: directional cursors through the client ------------------------

    def test_record_paging_uses_the_submitted_direction(self) -> None:
        with self._runtime() as value:
            for index in range(3):
                self._admitted_automation_run(
                    value,
                    f"page-{index}",
                    created_at=_NOW - timedelta(minutes=index),
                    succeeded_items=1,
                )
            status, first = _request(value.api, RECORDS_ROUTE, query="limit=1")
            self.assertEqual(status, 200)
            cursor = first["next_cursor"]
            self.assertIsNotNone(cursor)
            # Forward paging needs the matching direction, exactly as the Web
            # client now submits it.
            status, second = _request(
                value.api, RECORDS_ROUTE, query=f"limit=1&direction=next&cursor={cursor}"
            )
            self.assertEqual(status, 200)
            self.assertNotEqual(
                [item["recordId"] for item in first["items"]],
                [item["recordId"] for item in second["items"]],
            )
            back_cursor = second["previous_cursor"]
            self.assertIsNotNone(back_cursor)
            status, back = _request(
                value.api,
                RECORDS_ROUTE,
                query=f"limit=1&direction=previous&cursor={back_cursor}",
            )
            self.assertEqual(status, 200)
            self.assertEqual(
                [item["recordId"] for item in back["items"]],
                [item["recordId"] for item in first["items"]],
            )

    # -- R1: follow-up executions are not original admissions --------------

    def _recovery_records(self, api) -> dict[str, dict]:
        status, page = _request(api, RECORDS_ROUTE)
        self.assertEqual(status, 200)
        return {item["recordId"]: item for item in page["items"]}

    def test_recovery_follow_up_task_is_not_an_original_admission(self) -> None:
        """A confirmed recovery execution inherits the origin but is not a run.

        The existing supported recovery path writes its follow-up Task with the
        original admission's definition origin (that is how the same execution
        stays reachable from both surfaces).  Origin alone therefore cannot
        decide whether a run is an *original* Automation admission: the durable
        recovery lineage must, and it has to do so before the page window, the
        filtered total, the status partitions, the metric cohorts and the
        per-definition latest outcome, so all of them agree.
        """

        with self._runtime() as value:
            origin = self._admitted_automation_run(
                value,
                "original",
                created_at=_NOW - timedelta(minutes=30),
                status=PersistentTaskStatus.PARTIAL_SUCCESS,
                job_status=AutomationJobStatus.COMPLETED,
                succeeded_items=1,
            )
            self.assertIsNone(origin)
            origin_task_id = "original-task"
            # The confirmed recovery summary of one failed item of that run and
            # the execution it admitted.  Both carry the exact persisted link
            # the real journey writes; the follow-up Task inherits the origin.
            value.runtime.create_task(
                _task(
                    "recovery-prep-task",
                    created_at=_NOW - timedelta(minutes=20),
                    command="preview",
                )
            )
            value.runtime.create_task(
                dataclasses.replace(
                    _task(
                        "follow-up-task",
                        created_at=_NOW - timedelta(minutes=10),
                        command="manual_organize",
                    ),
                    total_items=1,
                    completed_items=1,
                ),
                display=RunDisplayContext(
                    source_scope="Media/电影",
                    labels=("电影库",),
                    origin_definition_id=_DEFINITION["id"],
                    origin_definition_name="Nightly automation",
                    origin_kind="definition-run-once",
                ),
            )
            value.runtime.create_manual_recovery_preparation(
                ManualRecoveryPreparation(
                    "preparation-1",
                    origin_task_id,
                    "original-failed-0",
                    "continuation-1",
                    "recovery-prep-task",
                    "recovery-prep-result",
                    "intent-1",
                    "preview-1",
                    1,
                    "checkpoint-1",
                    "fingerprint-1",
                    "revision-active",
                    "d" * 64,
                    "tester",
                    ManualRecoveryPreparationStatus.PREPARED,
                    _NOW - timedelta(minutes=20),
                    _NOW - timedelta(minutes=10),
                )
            )
            value.runtime._connection.execute(
                "UPDATE manual_recovery_preparations SET status='confirmed', current=0, "
                "execution_id='execution-1' WHERE preparation_id='preparation-1'"
            )
            # The execution row names the follow-up Task; ``manual_executions``
            # refers to a preview/intent, so only the durable execution Task
            # identity is needed here.
            value.runtime._connection.execute(
                """INSERT INTO manual_executions (
                    execution_id, preview_id, intent_id, authorization_id, task_id,
                    actor, intent_version, configuration_snapshot_id,
                    configuration_snapshot_digest, selected_item_ids_json,
                    unselected_item_ids_json, status, next_action, error,
                    allow_overwrite, allow_source_cleanup, created_at, updated_at,
                    completed_at, worker_id, claim_token, claimed_at, claim_expires_at, attempts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          NULL, NULL, NULL, NULL, 0)""",
                (
                    "execution-1",
                    "preview-1",
                    "intent-1",
                    "authorization-1",
                    "follow-up-task",
                    "tester",
                    1,
                    "revision-active",
                    "d" * 64,
                    "[]",
                    "[]",
                    "completed",
                    "inspect the linked execution",
                    None,
                    0,
                    0,
                    (_NOW - timedelta(minutes=10)).isoformat(),
                    (_NOW - timedelta(minutes=10)).isoformat(),
                    (_NOW - timedelta(minutes=10)).isoformat(),
                ),
            )

            records = self._recovery_records(value.api)
            # The follow-up Task is genuinely reachable in Operations but is not
            # another original Automation run.
            self.assertEqual(set(records), {"original-job"})
            self.assertNotIn("follow-up-task", records)
            status, page = _request(value.api, RECORDS_ROUTE)
            self.assertEqual(page["total"], 1)
            self.assertEqual(sum(page["statusCounts"].values()), 1)

            status, metrics = _request(value.api, METRICS_ROUTE)
            self.assertEqual(metrics["monthToDateAdmitted"], 1)
            self.assertEqual(metrics["monthToDateTerminal"], 1)

            # The ordinary Operations population still shows both runs, so the
            # exclusion is confined to the *original Automation* population.
            self.assertTrue(
                any(
                    item.task_id == "follow-up-task"
                    for item in value.runtime.list_operations_runs(limit=50)
                )
            )
            # The original row keeps its historical result and its origin; the
            # exclusion never rewrote the admission evidence.
            record = records["original-job"]
            self.assertEqual(record["trigger"], "scheduled")
            self.assertEqual(record["historyContext"]["definitionId"], _DEFINITION["id"])

    def test_follow_up_exclusion_survives_reopen_and_keeps_latest_original(self) -> None:
        """The same rule holds after a reopen and for the latest-outcome read."""

        with self._runtime() as value:
            self._admitted_automation_run(
                value,
                "original",
                created_at=_NOW - timedelta(hours=1),
                succeeded_items=1,
            )
            value.runtime.create_task(
                dataclasses.replace(
                    _task("follow-up-task", created_at=_NOW),
                    command="manual_organize",
                ),
                display=RunDisplayContext(
                    source_scope="Media/电影",
                    labels=("电影库",),
                    origin_definition_id=_DEFINITION["id"],
                    origin_definition_name="Nightly automation",
                    origin_kind="definition-run-once",
                ),
            )
            value.runtime._connection.execute(
                """INSERT INTO manual_recovery_preparations (
                    preparation_id, source_task_id, source_item_id,
                    analysis_continuation_id, analysis_task_id, analysis_result_id,
                    intent_id, preview_id, intent_version, checkpoint_version,
                    input_fingerprint, configuration_snapshot_id,
                    configuration_snapshot_digest, actor, status, current,
                    authorization_id, execution_id, selected_item_ids_json,
                    allow_overwrite, allow_source_cleanup, created_at, updated_at
                ) VALUES ('preparation-1', 'original-task', 'original-ok-0',
                          'continuation-1', 'analysis-task', 'analysis-result',
                          'intent-1', 'preview-1', 1, 'checkpoint-1', 'fingerprint-1',
                          'revision-active', ?, 'tester', 'prepared', 0, NULL,
                          NULL, '[]', 0, 0, ?, ?)""",
                (
                    "d" * 64,
                    (_NOW - timedelta(minutes=10)).isoformat(),
                    (_NOW - timedelta(minutes=5)).isoformat(),
                ),
            )
            value.runtime._connection.execute(
                """INSERT INTO manual_executions (
                    execution_id, preview_id, intent_id, authorization_id, task_id,
                    actor, intent_version, configuration_snapshot_id,
                    configuration_snapshot_digest, selected_item_ids_json,
                    unselected_item_ids_json, status, next_action, error,
                    allow_overwrite, allow_source_cleanup, created_at, updated_at,
                    completed_at, worker_id, claim_token, claimed_at, claim_expires_at, attempts
                ) VALUES ('execution-1', 'preview-1', 'intent-1', 'authorization-1',
                          'follow-up-task', 'tester', 1, 'revision-active', ?, '[]', '[]',
                          'completed', 'inspect', NULL, 0, 0, ?, ?, ?,
                          NULL, NULL, NULL, NULL, 0)""",
                (
                    "d" * 64,
                    (_NOW - timedelta(minutes=10)).isoformat(),
                    (_NOW - timedelta(minutes=5)).isoformat(),
                    (_NOW - timedelta(minutes=5)).isoformat(),
                ),
            )
            value.runtime._connection.execute(
                "UPDATE manual_recovery_preparations SET status='confirmed', current=0, "
                "execution_id='execution-1' WHERE preparation_id='preparation-1'"
            )
            value.runtime._connection.commit()

            latest = value.runtime.automation_latest_admitted_runs()
            # The newer follow-up never becomes the definition's latest run.
            self.assertEqual(latest[_DEFINITION["id"]]["runId"], "original-job")
            status, page = _request(value.api, RECORDS_ROUTE)
            self.assertEqual(page["total"], 1)
            value.runtime._connection.commit()

    def test_failed_handling_read_is_unavailable_not_unhandled(self) -> None:
        """A follow-up read that failed is never published as "nothing to do"."""

        with self._runtime() as value:
            self._admitted_automation_run(
                value,
                "origin",
                created_at=_NOW,
                status=PersistentTaskStatus.FAILED,
                job_status=AutomationJobStatus.FAILED,
                succeeded_items=0,
            )

            def explode(_task_ids):
                raise RuntimeError("durable handling read is unavailable")

            value.runtime.automation_linked_handling = explode
            status, page = _request(value.api, RECORDS_ROUTE)
            self.assertEqual(status, 200)
            handling = page["items"][0]["handling"]
            self.assertEqual(handling["state"], "unavailable")
            self.assertNotEqual(handling["state"], "unhandled")
            self.assertIn("could not be read", handling["nextAction"])
            # The original outcome is still published unchanged.
            self.assertEqual(page["items"][0]["status"], "failed")

    # -- R3: concrete failure reason and known effects ----------------------

    def test_record_publishes_concrete_item_failure_reason_and_effects(self) -> None:
        """A formal Task failure names its real reason, stage and known effects.

        The exact Task Center item evidence already carries the bounded failure
        envelope, the durable item stage and the effect certainty.  The record
        must reuse it, so the operator sees why an item failed and what is
        known about its effects — without raw exception text and without a
        local recovery control.
        """

        from mediaflow.application.failure_explanation import failure_explanation

        with self._runtime() as value:
            task_id = "mixed-task"
            value.runtime.create_task(
                dataclasses.replace(
                    _task(
                        task_id,
                        status=PersistentTaskStatus.PARTIAL_SUCCESS,
                        command="manual_organize",
                    ),
                    total_items=2,
                    completed_items=1,
                    failed_items=1,
                ),
                display=RunDisplayContext(
                    source_scope="Media/电影",
                    labels=("电影库",),
                    origin_definition_id=_DEFINITION["id"],
                    origin_definition_name="Nightly automation",
                    origin_kind="definition-run-once",
                ),
            )
            value.runtime.upsert_item(_run_item(task_id, "success-item", TaskItemStatus.SUCCESS))
            value.runtime.append_result(_run_result(task_id, "success-item"))
            value.runtime.upsert_item(
                dataclasses.replace(
                    _run_item(task_id, "failed-item", TaskItemStatus.FAILED),
                    stage="organizing",
                    error=failure_explanation(
                        "storage_failure", durable="failed", side_effects="none", retry_safe=True
                    ).encode(),
                )
            )
            value.runtime.append_result(
                dataclasses.replace(
                    _run_result(
                        task_id,
                        "failed-item",
                        status="failed",
                        effect_certainty="none",
                    ),
                    error=failure_explanation(
                        "storage_failure", durable="failed", side_effects="none", retry_safe=True
                    ).encode(),
                )
            )

            status, page = _request(value.api, RECORDS_ROUTE)
            self.assertEqual(status, 200)
            record = page["items"][0]
            self.assertEqual(record["status"], "partial_success")
            stage = record["failureStage"]
            self.assertIsNotNone(stage)
            self.assertFalse(stage["unavailable"])
            self.assertEqual(stage["category"], "storage_failure")
            self.assertIn("Storage operation did not complete", stage["statement"])
            self.assertEqual(stage["effects"]["none"], 1)
            self.assertEqual(stage["effects"]["known"], 0)
            self.assertEqual(len(stage["items"]), 1)
            failed = stage["items"][0]
            self.assertEqual(failed["itemId"], "failed-item")
            self.assertEqual(failed["category"], "storage_failure")
            self.assertEqual(failed["sideEffects"], "none")
            self.assertIn("source/destination state", failed["nextAction"])
            # No raw exception/plan text is exposed anywhere in the document.
            text = json.dumps(page).lower()
            for forbidden in ("traceback", "mediaflow-failure-v1", "storageerror"):
                self.assertNotIn(forbidden, text)
            # The successful sibling's proven effect stays distinct.
            self.assertEqual(record["result"]["successItems"], 1)

    def test_original_failure_reason_survives_later_handling(self) -> None:
        """A historical failure reason is never erased by starting recovery.

        Admitting a recovery continuation moves the source TaskItem off
        ``failed``, so the durable failed Result is what keeps the original
        reason readable.  A per-Task page bound must also keep every Task's own
        evidence: a single global row limit would let one Task hide another.
        """

        from mediaflow.application.failure_explanation import failure_explanation

        with self._runtime() as value:
            encoded = failure_explanation(
                "storage_failure", durable="failed", side_effects="none", retry_safe=True
            ).encode()
            self._admitted_automation_run(
                value,
                "origin",
                created_at=_NOW - timedelta(minutes=30),
                status=PersistentTaskStatus.PARTIAL_SUCCESS,
                job_status=AutomationJobStatus.COMPLETED,
                succeeded_items=1,
            )
            value.runtime.upsert_item(
                dataclasses.replace(
                    _run_item("origin-task", "origin-failed", TaskItemStatus.FAILED),
                    error=encoded,
                )
            )
            value.runtime.append_result(
                dataclasses.replace(
                    _run_result(
                        "origin-task",
                        "origin-failed",
                        created_at=_NOW - timedelta(minutes=40),
                        status="failed",
                        effect_certainty="none",
                    ),
                    error=encoded,
                )
            )
            # This one Task has more failed items than any per-Task sample
            # bound, and two sibling Tasks each have their own single failure.
            # A global row bound would let the big Task's rows consume the whole
            # window and silently drop the siblings' evidence.
            for index in range(14):
                item_id = f"origin-bad-{index}"
                value.runtime.upsert_item(
                    dataclasses.replace(
                        _run_item("origin-task", item_id, TaskItemStatus.FAILED),
                        error=encoded,
                    )
                )
                value.runtime.append_result(
                    dataclasses.replace(
                        _run_result(
                            "origin-task", item_id, status="failed", effect_certainty="none"
                        ),
                        error=encoded,
                    )
                )
            for index in range(2):
                self._admitted_automation_run(
                    value,
                    f"noise-{index}",
                    created_at=_NOW - timedelta(minutes=index + 1),
                    status=PersistentTaskStatus.FAILED,
                    job_status=AutomationJobStatus.FAILED,
                    succeeded_items=0,
                )
                value.runtime.upsert_item(
                    dataclasses.replace(
                        _run_item(
                            f"noise-{index}-task",
                            f"noise-{index}-bad",
                            TaskItemStatus.FAILED,
                            created_at=_NOW,
                        ),
                        error=encoded,
                    )
                )
                value.runtime.append_result(
                    dataclasses.replace(
                        _run_result(
                            f"noise-{index}-task",
                            f"noise-{index}-bad",
                            created_at=_NOW,
                            status="failed",
                            effect_certainty="none",
                        ),
                        error=encoded,
                    )
                )
            # The real recovery admission moves the source item off ``failed``.
            value.runtime.upsert_item(
                _run_item("origin-task", "origin-failed", TaskItemStatus.PENDING)
            )

            status, page = _request(value.api, RECORDS_ROUTE, query="limit=100")
            self.assertEqual(status, 200)
            records = {item["recordId"]: item for item in page["items"]}
            record = records["origin-job"]
            stage = record["failureStage"]
            self.assertFalse(stage["unavailable"])
            self.assertEqual(stage["category"], "storage_failure")
            # The sample is bounded but the counts are honest, and the
            # historical zero-effect reason still names the original item.
            self.assertEqual(stage["effects"]["none"], 15)
            self.assertTrue(stage["itemsTruncated"])
            self.assertEqual(len(stage["items"]), 10)
            self.assertIn("origin-failed", {item["itemId"] for item in stage["items"]})
            self.assertTrue(all(item["sideEffects"] == "none" for item in stage["items"]))
            # The original outcome itself is unchanged by the handling.
            self.assertEqual(record["status"], "partial_success")
            self.assertEqual(record["result"]["successItems"], 1)
            # Every sibling Task kept its own evidence: no global row bound.
            for index in range(2):
                sibling = records[f"noise-{index}-job"]["failureStage"]
                self.assertFalse(sibling["unavailable"])
                self.assertEqual(len(sibling["items"]), 1)
                self.assertEqual(sibling["items"][0]["itemId"], f"noise-{index}-bad")

    def test_record_reports_reached_bound_only_from_admitted_evidence(self) -> None:
        """A reached bound is a durable fact, never an exhaustion claim."""

        with self._runtime() as value:
            # A scheduled occurrence admitted with an item limit of 2 whose Task
            # persisted exactly 2 primary items reached that bound.
            value.runtime.create_task(
                dataclasses.replace(_task("bounded-task"), total_items=2),
            )
            value.runtime.create_job(
                dataclasses.replace(
                    _job(
                        "bounded-job",
                        task_id="bounded-task",
                        definition_id=_DEFINITION["id"],
                        schedule_id="schedule-1",
                    ),
                    limit=2,
                )
            )
            status, page = _request(value.api, RECORDS_ROUTE)
            self.assertEqual(status, 200)
            result = page["items"][0]["result"]
            self.assertEqual(result["admittedItemBound"], 2)
            self.assertTrue(result["reachedItemBound"])

            # A definition Run once persists the *selected* count as its limit,
            # which is not a containment bound: it stays explicitly unavailable.
            value.runtime.create_task(
                dataclasses.replace(
                    _task("manual-bounded", created_at=_NOW - timedelta(minutes=5)),
                    item_limit=2,
                    total_items=2,
                ),
                display=RunDisplayContext(
                    source_scope="Media/电影",
                    labels=("电影库",),
                    origin_definition_id=_DEFINITION["id"],
                    origin_definition_name="Nightly automation",
                    origin_kind="definition-run-once",
                ),
            )
            status, page = _request(value.api, RECORDS_ROUTE)
            records = {item["recordId"]: item for item in page["items"]}
            manual = records["manual-bounded"]["result"]
            self.assertIsNone(manual["admittedItemBound"])
            self.assertFalse(manual["reachedItemBound"])

    def test_handling_progress_is_truthful_across_analysis_plan_and_execution(self) -> None:
        """Analysis completion is not resolution; only a proven effect is.

        The same-page recovery journey writes a recovery continuation (a
        zero-mutation DryRun), then a non-authorizing plan summary, then an
        execution whose items prove the effect.  Each step must publish its own
        truthful handling state so the record never claims resolution before the
        operator confirmed and executed a plan.
        """

        with self._runtime() as value:
            self._admitted_automation_run(
                value,
                "origin",
                created_at=_NOW - timedelta(minutes=30),
                status=PersistentTaskStatus.PARTIAL_SUCCESS,
                job_status=AutomationJobStatus.COMPLETED,
                succeeded_items=1,
            )
            origin = "origin-task"
            value.runtime.upsert_item(
                _run_item(origin, "origin-failed", TaskItemStatus.FAILED, created_at=_NOW)
            )
            # Step 1 — the completed zero-mutation analysis continuation.
            self._write_recovery_continuation(
                value, origin, "origin-failed", "analysis-task", "completed"
            )
            handling = self._recovery_records(value.api)["origin-job"]["handling"]
            self.assertEqual(handling["state"], "investigation")
            self.assertNotEqual(handling["state"], "resolved")

            # Step 2 — a prepared (non-authorizing) plan summary.
            value.runtime.create_task(
                _task("follow-up-task", created_at=_NOW, command="manual_organize")
            )
            value.runtime.upsert_item(
                _run_item("follow-up-task", "follow-up-item", TaskItemStatus.PENDING)
            )
            value.runtime.create_manual_recovery_preparation(
                ManualRecoveryPreparation(
                    "preparation-1",
                    origin,
                    "origin-failed",
                    "continuation-1",
                    "analysis-task",
                    "analysis-result",
                    "intent-1",
                    "preview-1",
                    1,
                    "checkpoint-1",
                    "fingerprint-1",
                    "revision-active",
                    "d" * 64,
                    "tester",
                    ManualRecoveryPreparationStatus.PREPARED,
                    _NOW,
                    _NOW,
                )
            )
            handling = self._recovery_records(value.api)["origin-job"]["handling"]
            self.assertEqual(handling["state"], "investigation")

            # Step 3 — an admitted, still-running execution is progress.
            value.runtime._connection.execute(
                """INSERT INTO manual_executions (
                    execution_id, preview_id, intent_id, authorization_id, task_id,
                    actor, intent_version, configuration_snapshot_id,
                    configuration_snapshot_digest, selected_item_ids_json,
                    unselected_item_ids_json, status, next_action, error,
                    allow_overwrite, allow_source_cleanup, created_at, updated_at,
                    completed_at, worker_id, claim_token, claimed_at, claim_expires_at, attempts
                ) VALUES ('execution-1', 'preview-1', 'intent-1', 'authorization-1',
                          'follow-up-task', 'tester', 1, 'revision-active', ?, '[]', '[]',
                          'admitted', 'wait for the Worker', NULL, 0, 0, ?, ?, NULL,
                          NULL, NULL, NULL, NULL, 0)""",
                ("d" * 64, _NOW.isoformat(), _NOW.isoformat()),
            )
            value.runtime._connection.execute(
                "UPDATE manual_recovery_preparations SET status='confirmed', current=0, "
                "execution_id='execution-1' WHERE preparation_id='preparation-1'"
            )
            value.runtime._connection.commit()
            handling = self._recovery_records(value.api)["origin-job"]["handling"]
            self.assertEqual(handling["state"], "handling")

            # Step 4 — a terminal execution whose item proved the effect is the
            # only state that may read as resolved.
            value.runtime.upsert_item(
                _run_item("follow-up-task", "follow-up-item", TaskItemStatus.SUCCESS)
            )
            value.runtime.append_result(_run_result("follow-up-task", "follow-up-item"))
            value.runtime._connection.execute(
                "UPDATE manual_executions SET status='completed' WHERE execution_id='execution-1'"
            )
            value.runtime._connection.commit()
            handling = self._recovery_records(value.api)["origin-job"]["handling"]
            self.assertEqual(handling["state"], "resolved")

            # Step 5 — a still-failing item in the linked execution is never
            # hidden by an earlier success.
            value.runtime.upsert_item(
                _run_item("follow-up-task", "follow-up-item", TaskItemStatus.FAILED)
            )
            handling = self._recovery_records(value.api)["origin-job"]["handling"]
            self.assertEqual(handling["state"], "recovery_failed")

    @staticmethod
    def _write_recovery_continuation(
        value, source_task_id: str, source_item_id: str, new_task_id: str, status: str
    ) -> None:
        value.runtime.create_task(
            _task(new_task_id, created_at=_NOW, command="recovery-continuation")
        )
        value.runtime._connection.execute(
            """INSERT INTO recovery_requests (
                request_id, task_id, item_id, action_id, checkpoint_version,
                source_storage_id, source_path, actor, requested_at, status,
                authority_statement, next_action
            ) VALUES ('request-1', ?, ?, 'retry', 'checkpoint-1',
                      'source-storage', 'Media/电影/origin-failed.mkv', 'tester', ?,
                      'completed', 'analysis-only', 'inspect the analysis')""",
            (source_task_id, source_item_id, _NOW.isoformat()),
        )
        value.runtime._connection.execute(
            """INSERT INTO recovery_continuations (
                continuation_id, request_id, source_task_id, source_item_id,
                checkpoint_version, configuration_snapshot_id,
                configuration_snapshot_digest, boundary, status, created_at,
                updated_at, actor, job_id, new_task_id, new_result_id, started_at,
                completed_at, error, recovery, authority_statement
            ) VALUES ('continuation-1', 'request-1', ?, ?, 'checkpoint-1',
                      'revision-active', ?, 'analysis', ?, ?, ?, 'tester',
                      'analysis-job', ?, 'analysis-result', ?, ?, NULL, NULL,
                      'analysis-only')""",
            (
                source_task_id,
                source_item_id,
                "d" * 64,
                status,
                _NOW.isoformat(),
                _NOW.isoformat(),
                new_task_id,
                _NOW.isoformat(),
                _NOW.isoformat(),
            ),
        )
        value.runtime._connection.commit()

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
