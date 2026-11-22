"""V2 Automation operator journey over the real managed API.

These regressions drive the real ``MediaFlowApi`` against a real managed
configuration runtime, real LocalStorage roots and the real definition
occurrence/Run once services. They prove the new
``/api/operations/automation/*`` read projections are bounded operator
documents — no revision digests, definition fingerprints, source fingerprints
or raw organize plans — with backend-authoritative actions over the exact
published Active configuration; that the direct create/update journey
publishes atomically and starts no work; that a definition Run once keeps its
exact admitted scope and zero-mutation analysis; and that the existing
``/api/automation`` and configuration surfaces remain untouched for V1
clients.
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

from mediaflow.application.automation import IntervalScheduler
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.manual_task_engine import ManualTaskEngineWorker
from mediaflow.application.task_scheduling import TaskSchedulingService
from mediaflow.domain.automation import AutomationTaskDefinition, SchedulerConfigurationSnapshot
from mediaflow.domain.security import ApiRole
from mediaflow.final_cli import _automatic_task_runner
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.account_fixtures import AccountSessions
from tests.task_engine_test_helpers import claim_and_run

ADMIN_TOKEN = "automation-admin-token"
VIEWER_TOKEN = "automation-viewer-token"

OPERATIONS_ROUTE = "/api/operations/automation/task-definitions"

_DEFINITION = {
    "id": "auto-task",
    "name": "Nightly automation",
    "resourceLibraryId": "source",
    "mode": "automatic-organization",
    "intervalSeconds": 3600,
    "itemLimit": 12,
}

_DIGEST_KEYS = (
    "digest",
    "configurationRevisionDigest",
    "configurationSnapshotDigest",
    "definitionFingerprint",
    "definitionCurrentFingerprint",
    "sourceFingerprint",
    "planFingerprint",
)
_FORBIDDEN_DOCUMENT_KEYS = (*_DIGEST_KEYS, "plan")
_FORBIDDEN_SUBSTRINGS = (
    "Bearer ",
    "apiKey",
    "authorization:",
    "executionPlan",
)


def _document(root: Path) -> dict:
    value = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
    value["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
    value["historyPath"] = str(root / "history.jsonl")
    value["storages"][0]["rootPath"] = str(root / "source")
    value["storages"][1]["rootPath"] = str(root / "target")
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
        "HTTP_HOST": "127.0.0.1",
        "HTTP_ORIGIN": "http://127.0.0.1",
    }
    session = getattr(api, "_fixture_session_cookies", {}).get(token)
    if session is not None:
        environ["HTTP_COOKIE"] = session
    else:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    result = b"".join(api(environ, lambda status, _headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(result)


def _assert_operator_document_clean(document: object) -> None:
    """No digest, fingerprint, raw plan, credential or exception evidence."""

    text = json.dumps(document, ensure_ascii=False)
    lowered = text.lower()
    for key in _FORBIDDEN_DOCUMENT_KEYS:
        assert f'"{key}"' not in text, f"operator document leaked {key}"
    for substring in _FORBIDDEN_SUBSTRINGS:
        assert substring.lower() not in lowered, f"operator document leaked {substring}"
    if isinstance(document, dict):
        for value in document.values():
            _assert_operator_document_clean(value)
    elif isinstance(document, list):
        for value in document:
            _assert_operator_document_clean(value)


def _provider_registry_factory(*_requested):
    """A synthetic Provider registry so exact analysis needs no external service."""

    from mediaflow.application.metadata import MetadataProviderRegistry
    from mediaflow.application.strategy_test import SyntheticMetadataProvider
    from mediaflow.domain.metadata import MediaCandidate, MediaType

    return MetadataProviderRegistry(
        (
            SyntheticMetadataProvider(
                (
                    MediaCandidate(
                        "tmdb",
                        "129",
                        MediaType.MOVIE,
                        "One",
                        year=2001,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                )
            ),
        )
    )


class _RecordingStorage(LocalStorage):
    """LocalStorage passthrough that records every mutating call."""

    def __init__(self, storage_id: str, root: Path) -> None:
        super().__init__(storage_id, root)
        self.mutations: list[str] = []

    def write(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.mutations.append("write")
        return super().write(*args, **kwargs)

    def create_directory(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.mutations.append("create_directory")
        return super().create_directory(*args, **kwargs)

    def move(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.mutations.append("move")
        return super().move(*args, **kwargs)

    def copy(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.mutations.append("copy")
        return super().copy(*args, **kwargs)

    def delete(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.mutations.append("delete")
        return super().delete(*args, **kwargs)

    def hard_link(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.mutations.append("hard_link")
        return super().hard_link(*args, **kwargs)

    def soft_link(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.mutations.append("soft_link")
        return super().soft_link(*args, **kwargs)


class AutomationOperatorJourneyTests(unittest.TestCase):
    """Current direct-publication Automation operator journeys."""

    @contextlib.contextmanager
    def _journey(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            target_root = root / "target"
            (source_root / "Media" / "电影").mkdir(parents=True)
            (source_root / "Media" / "C").mkdir(parents=True)
            (source_root / "Media" / "电影" / "One.2001.mkv").write_bytes(b"x" * 32)
            (source_root / "Media" / "C" / "One.2001.mkv").write_bytes(b"x" * 32)
            (source_root / "incoming").mkdir(parents=True)
            (target_root / "Movies").mkdir(parents=True)
            document = _document(root)
            with (
                SQLiteConfigurationRepository(
                    root / "configuration.sqlite3"
                ) as configuration_repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime,
            ):
                accounts = AccountSessions(runtime)
                accounts.add("admin", (ApiRole.ADMIN,))
                accounts.add("viewer", (ApiRole.VIEWER,))
                session_cookies = {
                    ADMIN_TOKEN: accounts.cookie("admin"),
                    VIEWER_TOKEN: accounts.cookie("viewer"),
                }
                managed = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(root / "runtime.sqlite3"),
                )
                publishing_api = MediaFlowApi(
                    runtime,
                    account_service=accounts.service,
                    configuration_service=managed,
                    bootstrap_document=document,
                )
                publishing_api._fixture_session_cookies = session_cookies
                status, active = _request(
                    publishing_api,
                    "/api/configuration/publish",
                    method="POST",
                    body={"document": document},
                )
                self.assertEqual(status, 200, active)
                api = MediaFlowApi(
                    runtime,
                    account_service=accounts.service,
                    configuration_service=managed,
                    bootstrap_document=document,
                    metadata_provider_registry_factory=_provider_registry_factory,
                )
                api._fixture_session_cookies = session_cookies
                value = SimpleNamespace(
                    api=api,
                    managed=managed,
                    runtime=runtime,
                    repository=runtime,
                    active=managed.active(),
                    source=_RecordingStorage("source-storage", source_root),
                    target=_RecordingStorage("media-target", target_root),
                    source_root=source_root,
                    target_root=target_root,
                    root=root,
                )
                self._create(value, {**_DEFINITION, "enabled": True})
                value.active = managed.active()
                yield value

    def _seed_retained_analysis_plan(self, value, *, definition_id: str = _DEFINITION["id"]) -> str:
        discovery = value.api._media_discovery.admit_definition_run_once(
            definition_id=definition_id, actor="admin"
        )
        for index in range(16):
            result = claim_and_run(
                value.api._media_discovery,
                worker_id=f"analysis-worker-{index}",
                claim_token=f"analysis-token-{index}",
            )
            if result is None:
                raise AssertionError("shared analysis discovery was not claimable")
            if result.terminal:
                break
        else:
            raise AssertionError("shared analysis did not settle in the step budget")
        current = value.api._media_discovery.get(discovery.discovery_id)
        frozen = value.api._media_discovery.finalize(
            discovery.discovery_id, actor="admin", expected_version=current.version
        )
        self.assertIsNone(frozen.organize_task_id)
        intent = value.api._manual_intents.get(frozen.intent_id)
        preview = value.api._manual_previews.create(
            intent.intent_id, expected_version=intent.version, actor="admin"
        )
        self.assertTrue(preview.zero_mutation)
        self.assertEqual("previewed", preview.status.value)
        return preview.preview_id

    @staticmethod
    def _create(value, definition: dict | None = None) -> tuple[int, dict]:
        active = value.managed.active()
        return _request(
            value.api,
            "/api/automation/task-definitions",
            method="POST",
            body={
                "revisionId": active.revision_id,
                "expectedVersion": active.version,
                "object": dict(definition or _DEFINITION),
            },
        )

    def test_list_and_detail_are_bounded_and_permission_aware(self) -> None:
        with self._journey() as value:
            status, page = _request(value.api, OPERATIONS_ROUTE)
            self.assertEqual(status, 200, page)
            _assert_operator_document_clean(page)
            self.assertEqual(page["total"], 1)
            item = page["items"][0]
            self.assertEqual(item["id"], _DEFINITION["id"])
            self.assertEqual(item["definitionState"], "active")
            self.assertNotIn("draftState", page)
            self.assertNotIn("createDraft", page["actions"])
            self.assertNotIn("draftOnly", page["inventoryCounts"])
            self.assertEqual(
                page["inventoryCounts"],
                {
                    "published": 1,
                    "enabled": 1,
                    "total": 1,
                    "basis": "exact_current_active",
                    "scope": "full_authorized_population",
                },
            )
            self.assertNotIn("state", page["query"])
            status, enabled = _request(value.api, OPERATIONS_ROUTE, query="enabled=true")
            self.assertEqual(status, 200, enabled)
            self.assertEqual([item["id"] for item in enabled["items"]], [_DEFINITION["id"]])
            status, disabled = _request(value.api, OPERATIONS_ROUTE, query="enabled=false")
            self.assertEqual(status, 200, disabled)
            self.assertEqual(disabled["items"], [])
            status, detail = _request(value.api, f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}")
            self.assertEqual(status, 200)
            _assert_operator_document_clean(detail)
            self.assertNotIn("draftState", detail["definition"])
            self.assertNotIn("draftCreate", detail["definition"]["actions"])
            status, viewer = _request(
                value.api, f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}", token=VIEWER_TOKEN
            )
            self.assertEqual(status, 200)
            self.assertNotIn("activate-draft", json.dumps(viewer))

    def test_retired_state_filter_and_draft_fields_are_invalid(self) -> None:
        with self._journey() as value:
            for query in ("state=draft-only", "state=active", "state=all", "state=bogus"):
                status, response = _request(value.api, OPERATIONS_ROUTE, query=query)
                self.assertEqual(status, 400, (query, response))
                self.assertEqual(response["error"]["code"], "invalid_request", response)
            for suffix in (
                "",
                f"/{_DEFINITION['id']}",
            ):
                status, body = _request(value.api, f"{OPERATIONS_ROUTE}{suffix}")
                self.assertEqual(status, 200, body)
                self.assertNotIn("draftState", json.dumps(body))
                self.assertNotIn("createDraft", json.dumps(body))
                self.assertNotIn("draftOnly", json.dumps(body))

    def test_direct_create_and_update_publish_without_a_draft(self) -> None:
        with self._journey() as value:
            first = value.managed.active()
            self.assertEqual(
                first.document["automationTaskDefinitions"][0]["id"], _DEFINITION["id"]
            )
            status, updated = _request(
                value.api,
                f"/api/automation/task-definitions/{_DEFINITION['id']}",
                method="PUT",
                body={
                    "revisionId": first.revision_id,
                    "expectedVersion": first.version,
                    "object": {**_DEFINITION, "name": "Renamed nightly automation"},
                },
            )
            self.assertEqual(status, 200, updated)
            active = value.managed.active()
            self.assertEqual(
                active.document["automationTaskDefinitions"][0]["name"],
                "Renamed nightly automation",
            )
            self.assertFalse(
                any(
                    revision.status.value in {"draft", "validated"}
                    for revision in value.managed.repository.list_revisions()
                )
            )

    def test_stale_identity_is_refused_without_publication(self) -> None:
        with self._journey() as value:
            first = value.managed.active()
            status, response = _request(
                value.api,
                "/api/automation/task-definitions",
                method="POST",
                body={
                    "revisionId": first.revision_id,
                    "expectedVersion": first.version - 1,
                    "object": dict(_DEFINITION),
                },
            )
            self.assertEqual(status, 409, response)
            self.assertEqual(response["error"]["code"], "configuration_version_conflict")
            self.assertEqual(value.managed.active().revision_id, first.revision_id)

    def test_retired_draft_and_activate_entries_are_unknown(self) -> None:
        with self._journey() as value:
            active = value.managed.active()
            for suffix in ("draft", "activate-draft"):
                status, response = _request(
                    value.api,
                    f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}/{suffix}",
                    method="POST",
                    body={
                        "expectedRevisionId": active.revision_id,
                        "expectedVersion": active.version,
                    },
                )
                self.assertEqual(status, 404, response)
                self.assertEqual(response["error"]["code"], "not_found")

    def test_reads_create_no_work(self) -> None:
        with self._journey() as value:
            before = value.runtime._connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            _request(value.api, OPERATIONS_ROUTE)
            _request(value.api, f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}")
            after = value.runtime._connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()


class AutomationDisabledScheduleJourneyTests(unittest.TestCase):
    """A disabled plan stops Scheduler admission and the already-queued Work.

    The managed configuration store and the runtime work share one SQLite file
    exactly like a deployment, so the real resident Scheduler and the production
    ``_automatic_task_runner`` resolve the same pinned snapshot.  The browser
    journey in ``automation-lifecycle.python.spec.ts`` drives the same durable
    states through the real Web entry.
    """

    @contextlib.contextmanager
    def _journey(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            target_root = root / "target"
            (source_root / "Media").mkdir(parents=True)
            (source_root / "Media" / "One.2001.mkv").write_bytes(b"x" * 32)
            (target_root / "Movies").mkdir(parents=True)
            document = _document(root)
            database = root / "runtime.sqlite3"
            config = root / "bootstrap.json"
            config.write_text(json.dumps(document), encoding="utf-8")
            with (
                SQLiteConfigurationRepository(database) as configuration_repository,
                SQLiteTaskRepository(database) as runtime,
            ):
                accounts = AccountSessions(runtime)
                accounts.add("admin", (ApiRole.ADMIN,))
                managed = ManagedConfigurationService(
                    configuration_repository,
                    bootstrap_database_path=str(database),
                )
                api = MediaFlowApi(
                    runtime,
                    account_service=accounts.service,
                    configuration_service=managed,
                    bootstrap_document=document,
                )
                api._fixture_session_cookies = {ADMIN_TOKEN: accounts.cookie("admin")}
                status, active = _request(
                    api,
                    "/api/configuration/publish",
                    method="POST",
                    body={"document": document},
                )
                self.assertEqual(200, status, active)
                value = SimpleNamespace(
                    api=api,
                    managed=managed,
                    runtime=runtime,
                    source_root=source_root,
                    target_root=target_root,
                    root=root,
                    config=config,
                )
                self._create_enabled(value)
                yield value

    @staticmethod
    def _authority(value) -> dict:
        active = value.managed.active()
        assert active is not None
        return {
            "expectedRevisionId": active.revision_id,
            "expectedVersion": active.revision_sequence or active.version,
            "expectedDigest": active.digest,
        }

    def _create_enabled(self, value) -> None:
        status, created = _request(
            value.api,
            "/api/operations/automation/definitions",
            method="POST",
            body={
                **self._authority(value),
                "object": dict(_DEFINITION),
                "enabled": True,
            },
        )
        self.assertEqual(200, status, created)
        self.assertIs(created["definition"]["enabled"], True)

    def _scheduler(self, value) -> IntervalScheduler:
        active = value.managed.active()
        assert active is not None
        definition = AutomationTaskDefinition.from_document(
            active.document["automationTaskDefinitions"][0]
        )
        return IntervalScheduler(
            value.runtime,
            configuration_snapshot_resolver=lambda: SchedulerConfigurationSnapshot(
                active.revision_id,
                active.digest,
                100,
                (definition,),
                active.version,
                ("source",),
                ("source",),
            ),
            execution_authority=value.api._automation_execution_authority,
        )

    def _disable(self, value) -> None:
        status, disabled = _request(
            value.api,
            f"/api/operations/automation/definitions/{_DEFINITION['id']}/disable",
            method="POST",
            body=self._authority(value),
        )
        self.assertEqual(200, status, disabled)
        self.assertIs(disabled["definition"]["enabled"], False)

    def _enable(self, value) -> None:
        status, enabled = _request(
            value.api,
            f"/api/operations/automation/definitions/{_DEFINITION['id']}/enable",
            method="POST",
            body=self._authority(value),
        )
        self.assertEqual(200, status, enabled)
        self.assertIs(enabled["definition"]["enabled"], True)

    def _run_worker(self, value):
        now = datetime.now(UTC)
        scheduling = TaskSchedulingService(value.runtime, capacity=100)
        runner = _automatic_task_runner(value.runtime, str(value.config), scheduling)
        worker_id = "automation-disabled-worker"
        value.runtime.register_worker(
            worker_id,
            worker_id,
            5.0,
            ("organize",),
            None,
            None,
            SCHEMA_VERSION,
            now,
        )
        worker = ManualTaskEngineWorker(
            value.runtime,
            scheduling,
            None,
            None,
            worker_id=worker_id,
            automatic_runner=runner,
            notice=lambda line: None,
        )
        try:
            return worker.run_next()
        finally:
            value.runtime.stop_worker(worker_id, datetime.now(UTC))

    def test_disabled_before_due_emits_nothing_and_the_list_says_so(self) -> None:
        with self._journey() as value:
            self._disable(value)
            now = datetime.now(UTC)
            self.assertEqual((), self._scheduler(value).tick(now))
            state = value.runtime.get_automation_definition_due_state(_DEFINITION["id"])
            self.assertIsNotNone(state)
            assert state is not None
            self.assertEqual("disabled", state.last_outcome)
            self.assertIn("disabled", state.last_reason or "")
            self.assertTrue(state.last_next_action)
            self.assertEqual((), value.runtime.list_tasks())

            status, page = _request(value.api, OPERATIONS_ROUTE)
            self.assertEqual(200, status, page)
            item = page["items"][0]
            self.assertIs(item["enabled"], False)
            self.assertEqual("disabled", item["executionReadiness"]["state"])
            # A disabled due-state row keeps its saved next run so re-enabling
            # does not lose cadence; the operator Web must not present it as a
            # live next execution.
            self.assertIsNotNone(item["nextRunAt"])

            self._enable(value)
            emitted = self._scheduler(value).tick(now + timedelta(hours=2))
            self.assertEqual(1, len(emitted))
            self.assertEqual(1, len(value.runtime.list_tasks()))

    def test_disable_after_enqueue_stops_the_real_worker_and_the_record_explains_effects(
        self,
    ) -> None:
        with self._journey() as value:
            now = datetime.now(UTC)
            (queued,) = self._scheduler(value).tick(now)
            self._disable(value)
            self.assertEqual((), self._scheduler(value).tick(now + timedelta(minutes=1)))
            self.assertEqual(
                1,
                len(value.runtime.list_automation_definition_occurrences(_DEFINITION["id"])),
            )

            completed = self._run_worker(value)
            self.assertIsNotNone(completed)
            assert completed is not None
            self.assertEqual(queued.task_id, completed.task_id)
            self.assertEqual("failed", completed.status.value)
            task = value.runtime.get_task(queued.task_id)
            self.assertIsNotNone(task)
            assert task is not None
            self.assertIn("definition_disabled", task.error or "")
            self.assertEqual((), value.runtime.list_items(queued.task_id))
            self.assertEqual([], list(value.target_root.rglob("*.*")))
            self.assertTrue((value.source_root / "Media" / "One.2001.mkv").exists())

            status, records = _request(
                value.api,
                "/api/operations/automation/records",
                query=f"definition={_DEFINITION['id']}",
            )
            self.assertEqual(200, status, records)
            self.assertEqual(1, records["total"], records)
            record = records["items"][0]
            self.assertEqual("failed", record["recordOutcome"]["status"])
            self.assertIn("自动化已停用", record["recordOutcome"]["failureReason"])
            self.assertIn("重新启用", record["recordOutcome"]["nextStep"])
            self.assertIn("没有产生文件效果", record["recordOutcome"]["statement"])
            self.assertEqual("definition_disabled", record["failureStage"]["category"])
            self.assertEqual(0, record["recordOutcome"]["successItems"])

            # Re-enabling admits a fresh occurrence only; the stopped original
            # Task keeps its failed flow and is never replayed.
            self._enable(value)
            (fresh,) = self._scheduler(value).tick(now + timedelta(hours=2))
            self.assertNotEqual(queued.task_id, fresh.task_id)
            self.assertEqual("failed", value.runtime.get_task(queued.task_id).status.value)
            self.assertEqual(
                2,
                len(value.runtime.list_automation_definition_occurrences(_DEFINITION["id"])),
            )
