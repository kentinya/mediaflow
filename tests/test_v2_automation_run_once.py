"""Task 43.2 — definition-bound Run once over the real V2 Automation API.

These tests drive the real ``MediaFlowApi`` against a real managed configuration
runtime, real Local Storage and the real application services.  They prove the
operator-facing journey the Contract promises:

* ``运行一次`` is an explicit action on a *published* definition and sends no
  file selection: the backend derives the whole scope from the definition;
* a disabled published schedule is runnable once, and the run never enables the
  schedule, grants/revives/consumes unattended authority or advances due state;
* the prompt durable admission is read back by its own identity across reload;
* a removed mode, an over-bound ceiling and a Draft-only definition are refused
  with a bounded next action instead of being converted or truncated;
* reads and denials create no work and no Storage mutation.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mediaflow.application.automation_run_once import AutomationRunOnceService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.media_discovery import MediaDiscoveryService
from mediaflow.domain.media_discovery import DiscoveryBudgets
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.storage import StorageError, StorageErrorCode
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

ADMIN_TOKEN = "automation-run-once-admin"
VIEWER_TOKEN = "automation-run-once-viewer"


class _Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now = self.now + timedelta(seconds=seconds)


class _RecordingStorage:
    def __init__(self, storage) -> None:
        self._storage = storage
        self.reads: list[tuple[str, str]] = []
        self.mutations: list[tuple[str, str]] = []
        self._unreadable: set[str] = set()

    def fail_listing(self, prefix: str) -> None:
        """Make one subtree unreadable after admission."""

        self._unreadable.add(prefix.strip("/"))

    @property
    def storage_id(self) -> str:
        return self._storage.storage_id

    @property
    def name(self) -> str:
        return self._storage.name

    @property
    def read_only(self) -> bool:
        return self._storage.read_only

    @property
    def capabilities(self):
        return self._storage.capabilities

    def list(self, path: str):
        self.reads.append(("list", path))
        if any(path == prefix or path.startswith(prefix + "/") for prefix in self._unreadable):
            raise StorageError(
                StorageErrorCode.PERMISSION_DENIED, "list", path, "unreadable fixture subtree"
            )
        return self._storage.list(path)

    def list_page(self, path: str, *, limit: int, cursor: str | None = None):
        self.reads.append(("list_page", path))
        for prefix in self._unreadable:
            if path == prefix or path.startswith(prefix + "/"):
                raise StorageError(
                    StorageErrorCode.PERMISSION_DENIED,
                    "list",
                    path,
                    "synthetic permission denial for one subtree",
                )
        return self._storage.list_page(path, limit=limit, cursor=cursor)

    def stat(self, path: str):
        self.reads.append(("stat", path))
        return self._storage.stat(path)

    def exists(self, path: str) -> bool:
        self.reads.append(("exists", path))
        return self._storage.exists(path)

    def read(self, path: str):
        return self._storage.read(path)

    def write(self, path: str, data, *, overwrite: bool = False) -> None:
        self.mutations.append(("write", path))
        return self._storage.write(path, data, overwrite=overwrite)

    def create_directory(self, path: str) -> None:
        self.mutations.append(("create_directory", path))
        return self._storage.create_directory(path)

    def move(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self.mutations.append(("move", source))
        return self._storage.move(source, target, overwrite=overwrite)

    def copy(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self.mutations.append(("copy", source))
        return self._storage.copy(source, target, overwrite=overwrite)

    def delete(self, path: str) -> None:
        self.mutations.append(("delete", path))
        return self._storage.delete(path)

    def hard_link(self, source: str, target: str) -> None:
        self.mutations.append(("hard_link", source))
        return self._storage.hard_link(source, target)

    def soft_link(self, source: str, target: str) -> None:
        self.mutations.append(("soft_link", source))
        return self._storage.soft_link(source, target)


class RunOnceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source_root = self.root / "source"
        self.source_root.mkdir(parents=True)
        self.target_root = self.root / "target"
        self.target_root.mkdir(parents=True)
        self.clock = _Clock()
        self.environment = patch.dict(
            os.environ,
            {"TMDB_ACCESS_TOKEN": "sentinel-tmdb", "OPENLIST_TOKEN": "sentinel-openlist"},
            clear=False,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def media(self, relative: str) -> Path:
        path = self.source_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"m" * 512)
        stamp = (self.clock.now - timedelta(hours=1)).timestamp()
        os.utime(path, (stamp, stamp))
        return path

    def document(self, *, definitions=None, item_limit: int = 10, source_scope=None) -> dict:
        value = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        value["persistence"]["databasePath"] = str(self.root / "runtime.sqlite3")
        value["historyPath"] = str(self.root / "history.jsonl")
        value["storages"] = [
            {
                "id": "source",
                "name": "Source",
                "type": "local",
                "rootPath": str(self.source_root),
                "enabled": True,
            },
            {
                "id": "target",
                "name": "Target",
                "type": "local",
                "rootPath": str(self.target_root),
                "enabled": True,
            },
        ]
        value["resourceLibraries"] = [
            {
                "id": "library",
                "name": "Library",
                "storageId": "source",
                "storagePath": "",
                "enabled": True,
                "extensions": ["mkv", "mp4"],
            }
        ]
        value["mediaLibraries"] = [
            {
                "id": "movies",
                "name": "Movies",
                "storageId": "target",
                "rootPath": "Organized/Movies",
                "enabled": True,
            },
            {
                "id": "tv",
                "name": "TV",
                "storageId": "target",
                "rootPath": "Organized/TV",
                "enabled": True,
            },
        ]
        if definitions is None:
            definition = {
                "id": "nightly",
                "name": "Nightly",
                "resourceLibraryId": "library",
                "mode": "automatic-organization",
                "intervalSeconds": 3600,
                "itemLimit": item_limit,
                "enabled": False,
            }
            if source_scope is not None:
                definition["sourceScope"] = source_scope
            definitions = [definition]
        value["api"]["principals"] = [
            {"id": "admin", "tokenEnv": "MEDIAFLOW_API_TOKEN", "roles": ["admin"], "enabled": True}
        ]
        value["recognitionRules"] = [
            {
                "id": "movies",
                "name": "Movies",
                "priority": 100,
                "score": 100,
                "stopOnMatch": True,
                "condition": {"field": "extension", "operator": "in", "value": ["mkv", "mp4"]},
                "outputRecognitionType": "A",
            }
        ]
        value["automationTaskDefinitions"] = definitions
        if hasattr(self, "stability"):
            value["resourceLibraries"][0]["stability"] = self.stability
        if hasattr(self, "change_document"):
            self.change_document(value)
        return value

    @contextmanager
    def journey(self, *, definitions=None, item_limit: int = 10, source_scope=None):
        document = self.document(
            definitions=definitions, item_limit=item_limit, source_scope=source_scope
        )
        source = _RecordingStorage(LocalStorage("source", self.source_root))
        target = _RecordingStorage(LocalStorage("target", self.target_root))
        storages = {"source": source, "target": target}
        with (
            SQLiteConfigurationRepository(self.root / "configuration.sqlite3") as configuration,
            SQLiteTaskRepository(str(self.root / "runtime.sqlite3")) as repository,
        ):
            managed = ManagedConfigurationService(
                configuration,
                bootstrap_database_path=str(self.root / "runtime.sqlite3"),
            )
            draft = managed.import_draft(document, actor="tester")
            validated = managed.validate(draft.revision_id, actor="tester")
            if validated.status.value != "validated":
                raise AssertionError(validated.validation_errors)
            revision = managed.activate(
                validated.revision_id, expected_version=validated.version, actor="tester"
            )
            from mediaflow.infrastructure.runtime_configuration import (
                load_managed_runtime_configuration,
                with_managed_snapshot,
            )

            runtime = with_managed_snapshot(
                load_managed_runtime_configuration(
                    revision.document, bootstrap_database_path=managed.bootstrap_database_path
                ),
                snapshot_id=revision.revision_id,
                digest=revision.digest,
                version=revision.version,
            )
            intents = ManualOrganizeIntentService(
                repository,
                managed,
                runtime_resolver=lambda snapshot_id, digest: runtime,
                storage_factory=lambda value, ids: dict(storages),
            )
            previews = ManualOrganizePreviewService(
                repository,
                intents,
                configuration=runtime,
                storages=dict(storages),
                clock=self.clock,
            )
            discovery = MediaDiscoveryService(
                repository,
                intents,
                configuration=runtime,
                preview_service=previews,
                runtime_resolver=lambda snapshot_id, digest: runtime,
                storages=dict(storages),
                clock=self.clock,
                budgets=DiscoveryBudgets(),
            )
            run_once = AutomationRunOnceService(discovery, previews, clock=self.clock)
            api = MediaFlowApi(
                repository,
                None,
                principals=(
                    ResolvedApiPrincipal("admin", ADMIN_TOKEN, frozenset(ApiPermission)),
                    ResolvedApiPrincipal("viewer", VIEWER_TOKEN, frozenset({ApiPermission.READ})),
                ),
                configuration_service=managed,
                bootstrap_document=document,
                manual_intent_service=intents,
                manual_preview_service=previews,
                media_discovery_service=discovery,
                automation_run_once_service=run_once,
                storage_adapters=dict(storages),
            )
            yield SimpleNamespace(
                api=api,
                repository=repository,
                managed=managed,
                runtime=runtime,
                discovery=discovery,
                run_once=run_once,
                clock=self.clock,
                source=source,
                target=target,
                revision=revision,
            )

    def request(self, value, method, path, body=None, *, token=ADMIN_TOKEN):
        payload = b"" if body is None else json.dumps(body).encode("utf-8")
        statuses: list[str] = []
        path_info, _, query_string = path.partition("?")
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path_info,
            "QUERY_STRING": query_string,
            "CONTENT_LENGTH": str(len(payload)),
            "wsgi.input": io.BytesIO(payload),
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_AUTHORIZATION": f"Bearer {token}",
        }
        result = b"".join(value.api(environ, lambda status, _headers: statuses.append(status)))
        return int(statuses[0].split()[0]), (json.loads(result) if result else {})

    def drive(self, value, *, steps: int = 12):
        result = None
        for index in range(steps):
            result = value.discovery.claim_and_run(
                worker_id=f"worker-{index}", claim_token=f"token-{index}"
            )
            if result is None:
                raise AssertionError("Run-once discovery was not claimable")
            if result.terminal:
                break
        else:
            raise AssertionError("Run-once discovery did not settle")
        return result

    def admit(self, value, request_id="request-1", **overrides):
        active = value.managed.active()
        from mediaflow.domain.automation import AutomationTaskDefinition

        definition = AutomationTaskDefinition.from_document(
            active.document["automationTaskDefinitions"][0]
        )
        body = {
            "admissionRequestId": request_id,
            "expectedRevisionId": active.revision_id,
            "expectedRevisionVersion": active.revision_sequence or active.version,
            "expectedRevisionDigest": active.digest,
            "expectedDefinitionFingerprint": definition.definition_fingerprint,
            **overrides,
        }
        return self.request(
            value, "POST", "/api/v1/operations/automation/task-definitions/nightly/run-once", body
        )

    def execute(self, value):
        from mediaflow.application.automation import AutomationWorker
        from mediaflow.application.automation_definition_execution import (
            DefinitionScopedExecutionService,
        )
        from mediaflow.application.metadata import MetadataProviderRegistry
        from mediaflow.application.strategy_test import (
            SyntheticMetadataProvider,
            strategy_runner_from_configuration,
        )
        from mediaflow.domain.metadata import MediaCandidate, MediaType
        from mediaflow.infrastructure.json_history import JsonLinesOperationHistoryRepository

        provider = SyntheticMetadataProvider(
            (
                MediaCandidate("tmdb", "1", MediaType.MOVIE, "One", year=2001),
                MediaCandidate("tmdb", "2", MediaType.MOVIE, "Two", year=2002),
            )
        )
        service = DefinitionScopedExecutionService(
            value.repository,
            value.runtime,
            storage_factory=lambda **kwargs: {"source": value.source, "target": value.target},
            provider_factory=lambda ids: MetadataProviderRegistry((provider,)),
            strategy_factory=strategy_runner_from_configuration,
            history_factory=JsonLinesOperationHistoryRepository,
            unattended_grant_service=value.api._unattended_grants,
        )
        return AutomationWorker(value.repository, service.run).run_next()

    def test_disabled_definition_admits_task_before_worker_and_executes_without_confirmation(self):
        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            before = value.managed.active()
            status, run = self.admit(value)
            self.assertEqual(202, status, run)
            self.assertEqual("organizing", run["executionKind"])
            self.assertEqual("pending", value.repository.get_task(run["taskId"]).status.value)
            self.assertEqual([], value.source.mutations)
            finished = self.execute(value)
            self.assertEqual("completed", finished.status.value)
            task = value.repository.get_task(run["taskId"])
            self.assertEqual("completed", task.status.value)
            self.assertEqual(1, task.completed_items)
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())
            self.assertEqual(before.revision_id, value.managed.active().revision_id)
            self.assertIsNone(value.repository.get_automation_definition_due_state("nightly"))
            self.assertEqual((), value.repository.list_unattended_execution_grants())
            self.assertEqual((), value.discovery.list())
            self.assertEqual(1, len(value.repository.list_tasks()))
            self.assertEqual(1, len(value.repository.list_jobs()))
            status, runs = self.request(
                value, "GET", "/api/v1/operations/runs?view=all&trigger=manual"
            )
            self.assertEqual(200, status, runs)
            linked = [v for v in runs["items"] if v["task_id"] == task.task_id]
            self.assertEqual(1, len(linked))
            self.assertEqual("manual", linked[0]["trigger"])
            self.assertEqual("nightly", linked[0]["definition_id"])

    def test_duplicate_and_exact_lost_response_reconcile_without_replay(self):
        self.media("One.2001.mkv")
        with self.journey() as value:
            status, first = self.admit(value)
            self.assertEqual(202, status, first)
            status, second = self.admit(value)
            self.assertEqual(first["jobId"], second["jobId"])
            self.execute(value)
            status, read = self.request(
                value,
                "GET",
                "/api/v1/operations/automation/task-definitions/nightly/run-once?admissionRequestId=request-1",
            )
            self.assertEqual(200, status, read)
            self.assertEqual(first["taskId"], read["taskId"])
            self.assertEqual("completed", read["status"])
            self.assertIsNone(self.execute(value))
            self.assertEqual(1, len(value.repository.list_tasks()))

    def test_empty_is_no_work_but_unreadable_and_overflow_never_execute_prefix(self):
        with self.journey() as value:
            status, run = self.admit(value)
            self.assertEqual(202, status, run)
            self.execute(value)
            self.assertEqual(
                "no_work", value.run_once.document(value.run_once.get(run["jobId"]))["phase"]
            )
        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        with self.journey(item_limit=1) as value:
            self.admit(value, "overflow")
            result = self.execute(value)
            self.assertEqual("failed", result.status.value)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
        with self.journey() as value:
            value.source.fail_listing("Movies")
            self.admit(value, "unreadable")
            result = self.execute(value)
            self.assertEqual("failed", result.status.value)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_effective_ceiling_is_one_hundred_and_small_scope_completes(self):
        self.media("One.2001.mkv")
        with self.journey(item_limit=150) as value:
            status, run = self.admit(value)
            self.assertEqual(202, status, run)
            self.assertEqual(100, run["effectivePrimaryLimit"])
            result = self.execute(value)
            self.assertEqual("completed", result.status.value)
            self.assertEqual(1, value.repository.get_task(run["taskId"]).completed_items)

    def test_stale_malformed_missing_and_read_only_commands_create_nothing(self):
        with self.journey() as value:
            for body, token in [
                ({"admissionRequestId": "bad", "paths": ["One.mkv"]}, ADMIN_TOKEN),
                ({"admissionRequestId": "denied"}, VIEWER_TOKEN),
            ]:
                status, _ = self.request(
                    value,
                    "POST",
                    "/api/v1/operations/automation/task-definitions/nightly/run-once",
                    body,
                    token=token,
                )
                self.assertIn(status, (400, 403))
            status, _ = self.admit(value, expectedRevisionId="stale")
            self.assertEqual(409, status)
            status, _ = self.request(
                value,
                "POST",
                "/api/v1/operations/automation/task-definitions/missing/run-once",
                {"admissionRequestId": "missing"},
            )
            self.assertEqual(404, status)
            self.assertEqual((), value.repository.list_tasks())
            self.assertEqual((), value.repository.list_jobs())
            self.assertEqual([], value.source.mutations)

    def test_automatic_folder_filtering_keeps_images_and_sidecars_out_of_primaries(self):
        self.media("One.2001.mkv")
        self.media("advert.jpg")
        self.media("One.2001.en.srt")
        with self.journey() as value:
            self.admit(value)
            result = self.execute(value)
            self.assertEqual("completed", result.status.value)
            self.assertEqual(1, len(value.repository.list_items(result.task_id)))
            self.assertTrue((self.source_root / "advert.jpg").exists())
            self.assertTrue((self.source_root / "One.2001.en.srt").exists())

    def test_business_readiness_is_inside_the_admitted_task(self):
        self.media("Unknown.2024.mkv")
        with self.journey() as value:
            self.admit(value)
            result = self.execute(value)
            self.assertEqual("completed", result.status.value)
            items = value.repository.list_items(result.task_id)
            self.assertEqual(1, len(items))
            self.assertIn(
                items[0].status.value, ("waiting_metadata", "waiting_metadata_correction")
            )
            self.assertEqual([], value.source.mutations)

    def test_old_analysis_records_remain_analysis_only_on_plain_read(self):
        self.media("One.2001.mkv")
        with self.journey() as value:
            legacy = value.run_once.admit(
                "nightly",
                actor="admin",
                admission_request_id="00000000-0000-4000-8000-000000000001",
            )
            status, read = self.request(
                value, "GET", f"/api/v1/operations/automation/run-once/{legacy.discovery_id}"
            )
            self.assertEqual(200, status)
            self.assertTrue(read["zeroMutation"])
            self.assertNotIn("executionKind", read)
            self.assertEqual((), value.repository.list_jobs())
            self.assertEqual((), value.repository.list_tasks())

    def test_real_positive_size_interval_waits_once_and_reobserves(self):
        import time

        self.stability = {
            "minimumAgeSeconds": 0,
            "modifiedThresholdSeconds": 0,
            "stableSizeDurationSeconds": 1,
        }
        self.media("One.2001.mkv")
        with self.journey() as value:
            self.admit(value)
            start = time.monotonic()
            result = self.execute(value)
            self.assertGreaterEqual(time.monotonic() - start, 1)
            self.assertEqual("completed", value.repository.get_task(result.task_id).status.value)
            self.assertEqual(1, value.repository.get_task(result.task_id).completed_items)

    def test_ready_sibling_avoids_wait_and_unstable_sibling_is_failure_not_attention(self):
        import time

        self.stability = {
            "minimumAgeSeconds": 10,
            "modifiedThresholdSeconds": 20,
            "stableSizeDurationSeconds": 0,
        }
        self.media("One.2001.mkv")
        fresh = self.media("Two.2002.mkv")
        os.utime(fresh, (time.time(), time.time()))
        with self.journey() as value:
            self.admit(value)
            with patch(
                "mediaflow.application.media_organizer.time.sleep",
                side_effect=AssertionError("ready sources must avoid wait"),
            ):
                result = self.execute(value)
            task = value.repository.get_task(result.task_id)
            self.assertEqual("partial_success", task.status.value)
            self.assertEqual((1, 1), (task.completed_items, task.failed_items))
            self.assertTrue(fresh.exists())
            status, page = self.request(value, "GET", "/api/v1/operations/runs?view=attention")
            self.assertEqual(200, status, page)
            self.assertEqual(0, page["total"])

    def test_over_sixty_interval_has_no_wait_and_only_instability_is_failed(self):
        import time

        self.stability = {
            "minimumAgeSeconds": 0,
            "modifiedThresholdSeconds": 70,
            "stableSizeDurationSeconds": 0,
        }
        fresh = self.media("One.2001.mkv")
        os.utime(fresh, (time.time(), time.time()))
        with self.journey() as value:
            self.admit(value)
            with patch(
                "mediaflow.application.media_organizer.time.sleep",
                side_effect=AssertionError("over 60 seconds must not wait"),
            ):
                result = self.execute(value)
            self.assertEqual("failed", value.repository.get_task(result.task_id).status.value)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_source_change_during_single_short_wait_does_not_fake_stability(self):
        import time

        actual_sleep = time.sleep
        self.stability = {
            "minimumAgeSeconds": 0,
            "modifiedThresholdSeconds": 0,
            "stableSizeDurationSeconds": 1,
        }
        source = self.media("One.2001.mkv")
        calls = []

        def change_during_wait(seconds):
            calls.append(seconds)
            source.write_bytes(b"changed while being observed")
            actual_sleep(seconds)

        with self.journey() as value:
            self.admit(value)
            with patch(
                "mediaflow.application.media_organizer.time.sleep", side_effect=change_during_wait
            ):
                result = self.execute(value)
            self.assertEqual(1, len(calls))
            self.assertEqual("failed", value.repository.get_task(result.task_id).status.value)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_concurrent_exact_request_has_one_job_and_one_task(self):
        from concurrent.futures import ThreadPoolExecutor

        with self.journey() as value:
            with ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(pool.map(lambda _: self.admit(value), range(2)))
            self.assertTrue(all(status == 202 for status, body in responses), responses)
            self.assertEqual(responses[0][1]["jobId"], responses[1][1]["jobId"])
            self.assertEqual(1, len(value.repository.list_tasks()))
            self.assertEqual(1, len(value.repository.list_jobs()))
            status, listing = self.request(
                value, "GET", "/api/v1/operations/automation/run-once", token=VIEWER_TOKEN
            )
            self.assertEqual(200, status, listing)
            self.assertEqual([], listing["items"])

    def test_queue_capacity_and_failed_insert_do_not_leave_orphan_tasks(self):
        self.change_document = lambda document: document["automation"].update(
            {"maximumActiveJobs": 1}
        )
        with self.journey() as value:
            with patch.object(
                value.repository, "_insert_job", side_effect=RuntimeError("write failed")
            ):
                status, _ = self.admit(value)
                self.assertEqual(500, status)
            self.assertEqual((), value.repository.list_tasks())
            self.assertEqual((), value.repository.list_jobs())
            status, run = self.admit(value)
            self.assertEqual(202, status, run)
            status, _ = self.admit(value, "second")
            self.assertEqual(409, status)
            self.assertEqual(1, len(value.repository.list_tasks()))
            self.assertEqual(1, len(value.repository.list_jobs()))

    def test_recognition_and_classification_block_inside_real_task_and_center(self):
        # Each case uses a fresh fixture database, not a manually invented Task.
        self.media("One.2001.mkv")
        self.change_document = lambda document: document.update({"recognitionRules": []})
        with self.journey() as value:
            status, admitted = self.admit(value)
            self.assertEqual(202, status, admitted)
            result = self.execute(value)
            (item,) = value.repository.list_items(result.task_id)
            self.assertEqual("waiting_recognition", item.status.value)
            status, page = self.request(value, "GET", "/api/v1/operations/runs?view=recognition")
            self.assertEqual(200, status, page)
            self.assertEqual(1, page["total"])
            self.assertEqual([], value.source.mutations)

    def test_classification_block_inside_real_task(self):
        self.media("One.2001.mkv")

        def no_matching_destination(document):
            document["classificationPolicies"][0]["rules"] = [
                {
                    "id": "tv-only",
                    "priority": 1,
                    "conditions": {"mediaType": ["tv"]},
                    "result": {"mediaLibraryId": "movies", "path": ["TV"]},
                }
            ]

        self.change_document = no_matching_destination
        with self.journey() as value:
            self.admit(value)
            result = self.execute(value)
            (item,) = value.repository.list_items(result.task_id)
            self.assertEqual("waiting_classification", item.status.value)
            status, page = self.request(value, "GET", "/api/v1/operations/runs?view=classification")
            self.assertEqual(200, status, page)
            self.assertEqual(1, page["total"])
            self.assertEqual([], value.source.mutations)

    def test_cancel_pending_job_also_settles_its_precreated_task(self):
        with self.journey() as value:
            status, body = self.admit(value)
            self.assertEqual(202, status, body)
            (job,) = value.repository.list_jobs()
            cancelled = value.repository.request_job_cancellation(job.job_id, datetime.now(UTC))
            self.assertEqual("cancelled", cancelled.status.value)
            task = value.repository.get_task(job.task_id)
            self.assertEqual("cancelled", task.status.value)
            self.assertIsNotNone(task.completed_at)
            self.assertIn("admitted Task", cancelled.failure_durable_state)
            self.assertEqual([], value.source.mutations)

    def test_complete_walk_budget_and_unsafe_entries_fail_before_effects(self):
        from dataclasses import replace

        from mediaflow.application.automation_execution_intent import BoundedScopeReader

        self.media("One.2001.mkv")
        self.media("Two.2002.mkv")
        with self.journey() as value:
            self.admit(value)
            with patch(
                "mediaflow.application.automation_execution_intent.BoundedScopeReader",
                side_effect=lambda storage, **kwargs: BoundedScopeReader(
                    storage, maximum_entries=1, **kwargs
                ),
            ):
                result = self.execute(value)
            self.assertEqual("scope_unreadable", result.failure_category)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
        with self.journey() as value:
            self.admit(value, request_id="unsafe-2")
            original = value.source.list_page

            def unsafe(path, **kwargs):
                page = original(path, **kwargs)
                return replace(page, entries=[replace(page.entries[0], path="../outside.mkv")])

            with patch.object(value.source, "list_page", side_effect=unsafe):
                result = self.execute(value)
            self.assertEqual("scope_unreadable", result.failure_category)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_current_permission_loss_after_admission_settles_task_without_effects(self):
        import copy

        self.media("One.2001.mkv")
        with self.journey() as value:
            self.admit(value)
            document = copy.deepcopy(value.managed.active().document)
            document["api"]["principals"][0]["roles"] = ["viewer"]
            draft = value.managed.import_draft(document, actor="admin")
            validated = value.managed.validate(draft.revision_id, actor="admin")
            value.managed.activate(
                validated.revision_id, expected_version=validated.version, actor="admin"
            )
            result = self.execute(value)
            self.assertEqual("failed", result.status.value)
            self.assertEqual("failed", value.repository.get_task(result.task_id).status.value)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_previously_started_run_once_is_not_scanned_or_replayed(self):
        from mediaflow.application.task_runtime import PersistentTaskCoordinator

        self.media("One.2001.mkv")
        with self.journey() as value:
            self.admit(value)
            (job,) = value.repository.list_jobs()
            PersistentTaskCoordinator(value.repository, value.repository).begin_queued(job.task_id)
            result = self.execute(value)
            self.assertEqual("run_once_already_started", result.failure_category)
            self.assertFalse(result.failure_retry_safe)
            self.assertEqual("unknown", result.failure_side_effects)
            self.assertEqual((), value.repository.list_items(job.task_id))
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_repeated_storage_cursor_cannot_be_reported_as_empty_scope(self):
        from mediaflow.domain.storage import StoragePage

        with self.journey() as value:
            self.admit(value)
            with patch.object(value.source, "list_page", return_value=StoragePage((), "repeat")):
                result = self.execute(value)
            self.assertEqual("scope_unreadable", result.failure_category)
            self.assertEqual("failed", value.repository.get_task(result.task_id).status.value)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_scope_beyond_existing_depth_budget_never_executes_a_prefix(self):
        self.media("One.2001.mkv")
        self.media("/".join(["nested"] * 33 + ["Two.2002.mkv"]))
        with self.journey() as value:
            self.admit(value)
            result = self.execute(value)
            self.assertEqual("scope_unreadable", result.failure_category)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_pending_task_cancellation_is_honored_when_job_is_claimed(self):
        self.media("One.2001.mkv")
        with self.journey() as value:
            self.admit(value)
            (job,) = value.repository.list_jobs()
            cancelled = value.repository.cancel_task_if_current(
                job.task_id, updated_at=datetime.now(UTC)
            )
            self.assertEqual("cancelled", cancelled.status.value)
            result = self.execute(value)
            self.assertEqual("cancelled", result.status.value)
            self.assertEqual("cancelled", value.repository.get_task(job.task_id).status.value)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
