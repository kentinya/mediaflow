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
from mediaflow.domain.media_discovery import DiscoveryBudgets, DiscoveryStatus
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
        self.mutations.append(("read", path))
        return self._storage.read(path)

    def write(self, path: str, data, *, overwrite: bool = False) -> None:
        self.mutations.append(("write", path))

    def create_directory(self, path: str) -> None:
        self.mutations.append(("create_directory", path))

    def move(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self.mutations.append(("move", source))

    def copy(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self.mutations.append(("copy", source))

    def delete(self, path: str) -> None:
        self.mutations.append(("delete", path))

    def hard_link(self, source: str, target: str) -> None:
        self.mutations.append(("hard_link", source))

    def soft_link(self, source: str, target: str) -> None:
        self.mutations.append(("soft_link", source))


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
        value["automationTaskDefinitions"] = definitions
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
                runtime_resolver=lambda snapshot_id, digest: runtime,
                storages=dict(storages),
                clock=self.clock,
                budgets=DiscoveryBudgets(),
            )
            run_once = AutomationRunOnceService(discovery, intents, previews, clock=self.clock)
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

    # -- the promised journey --------------------------------------------

    def test_published_disabled_definition_runs_once_without_file_selection(self) -> None:
        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        with self.journey(source_scope="Movies") as value:
            active_before = value.managed.active()
            due_before = value.repository.get_automation_definition_due_state("nightly")
            status, body = self.request(
                value,
                "POST",
                "/api/v1/operations/automation/task-definitions/nightly/run-once",
                {},
            )
            self.assertEqual(202, status)
            self.assertEqual("discovering", body["phase"])
            self.assertEqual("nightly", body["definitionId"])
            self.assertEqual("Movies", body["sourceScope"])
            self.assertEqual(10, body["definitionItemLimit"])
            self.assertEqual(10, body["effectivePrimaryLimit"])
            self.assertEqual("none", body["sideEffects"])
            discovery_id = body["discoveryId"]

            settled = self.drive(value)
            self.assertEqual(DiscoveryStatus.COMPLETED, settled.status)
            self.assertEqual(2, len(settled.sources))
            # The scope came from the definition, never from a submitted path.
            self.assertEqual(
                ("Movies",),
                tuple(entry.path for entry in settled.progress.scope_entries),
            )
            # No schedule or authority state changed.
            self.assertEqual(active_before.revision_id, value.managed.active().revision_id)
            self.assertEqual(
                due_before, value.repository.get_automation_definition_due_state("nightly")
            )
            self.assertIsNone(value.repository.get_active_unattended_execution_grant("nightly"))

            status, detail = self.request(
                value,
                "GET",
                f"/api/v1/operations/automation/run-once/{discovery_id}",
            )
            self.assertEqual(200, status)
            self.assertEqual("ready", detail["phase"])
            self.assertTrue(detail["actions"]["finalize"]["available"])
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_finalize_freezes_manifest_and_returns_exact_preview(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            _status, body = self.request(
                value,
                "POST",
                "/api/v1/operations/automation/task-definitions/nightly/run-once",
                {},
            )
            self.drive(value)
            current = value.run_once.get(body["discoveryId"])
            status, frozen = self.request(
                value,
                "POST",
                f"/api/v1/operations/automation/run-once/{body['discoveryId']}/finalize",
                {"expectedVersion": current.version},
            )
            self.assertEqual(201, status)
            self.assertEqual("frozen", frozen["phase"])
            self.assertTrue(frozen["frozen"])
            self.assertIsNotNone(frozen["intentId"])
            # The expensive exact analysis is deferred to the resident Worker:
            # the response carries a durable analysis identity promptly instead
            # of blocking on the walk and Provider batch.
            analysis_id = frozen["analysisId"]
            self.assertIsNotNone(analysis_id)
            self.assertEqual(
                f"/operations/automation/preview-analyses/{analysis_id}",
                frozen["analysisPath"],
            )
            self.assertEqual("queued", frozen["analysis"]["status"])
            self.assertIsNone(frozen["previewId"])
            # Freezing and the analysis admission are zero mutation.
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_finalize_inline_preview_when_analysis_is_unbound(self) -> None:
        """Without the durable analysis service the inline exact Preview is kept."""

        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            value.run_once.bind_analysis_service(None)
            _status, body = self.request(
                value,
                "POST",
                "/api/v1/operations/automation/task-definitions/nightly/run-once",
                {},
            )
            self.drive(value)
            current = value.run_once.get(body["discoveryId"])
            status, frozen = self.request(
                value,
                "POST",
                f"/api/v1/operations/automation/run-once/{body['discoveryId']}/finalize",
                {"expectedVersion": current.version},
            )
            self.assertEqual(201, status)
            self.assertEqual("frozen", frozen["phase"])
            self.assertIsNotNone(frozen["previewId"])
            self.assertIsNotNone(frozen["intentId"])
            self.assertEqual(frozen["previewId"], frozen["preview"]["previewId"])
            # The frozen manifest's exact zero-mutation Preview is the existing
            # *manual* Organize Preview over the frozen intent, so the operator
            # continues on that surface.  The definition-Preview route reads a
            # different repository and would never show this Preview.
            self.assertEqual(
                f"/operations/organize/preview/{frozen['previewId']}",
                frozen["previewPath"],
            )
            self.assertIsNone(frozen["analysisId"])
            # Freezing and Preview are zero mutation.
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_over_bound_ceiling_with_a_small_scope_runs_once(self) -> None:
        """Ceiling 250 with one eligible file is a legal, complete Run once.

        The effective bound is min(250, 100) = 100 and the actual manifest holds
        one source, so no overflow exists: the definition is admitted, Storage
        is read and the complete manifest can be frozen.
        """

        self.media("Movies/One.2001.mkv")
        with self.journey(item_limit=250, source_scope="Movies") as value:
            status, body = self.request(
                value,
                "POST",
                "/api/v1/operations/automation/task-definitions/nightly/run-once",
                {},
            )
            self.assertEqual(202, status)
            self.assertEqual(250, body["definitionItemLimit"])
            self.assertEqual(100, body["effectivePrimaryLimit"])
            settled = self.drive(value)
            document = value.run_once.document(settled)
            self.assertEqual("ready", document["phase"])
            self.assertEqual(1, document["primarySourceCount"])
            self.assertTrue(document["actions"]["finalize"]["available"])

    def test_actual_overflow_refuses_with_narrowing_guidance(self) -> None:
        """An actual manifest above the effective bound refuses, never truncates."""

        for index in range(101):
            self.media(f"Movies/Movie{index:03d}.2001.mkv")
        with self.journey(item_limit=250, source_scope="Movies") as value:
            status, body = self.request(
                value,
                "POST",
                "/api/v1/operations/automation/task-definitions/nightly/run-once",
                {},
            )
            self.assertEqual(202, status)
            settled = self.drive(value)
            self.assertEqual(100, len(settled.sources))
            current = value.run_once.get(body["discoveryId"])
            status, refused = self.request(
                value,
                "POST",
                f"/api/v1/operations/automation/run-once/{body['discoveryId']}/finalize",
                {"expectedVersion": current.version},
            )
            self.assertEqual(409, status)
            self.assertEqual("discovery_overflow", refused["error"]["code"])
            self.assertIn("narrow", refused["error"]["details"]["nextAction"])

    def test_empty_scope_reports_no_work(self) -> None:
        (self.source_root / "Movies").mkdir()
        with self.journey(source_scope="Movies") as value:
            status, body = self.request(
                value,
                "POST",
                "/api/v1/operations/automation/task-definitions/nightly/run-once",
                {},
            )
            self.assertEqual(202, status)
            settled = self.drive(value)
            document = value.run_once.document(settled)
            self.assertEqual("no_work", document["phase"])
            self.assertFalse(document["actions"]["finalize"]["available"])

    def test_duplicate_admission_reconciles_to_one_durable_run(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            request_id = "11111111-1111-4111-8111-111111111111"
            first_status, first = self.request(
                value,
                "POST",
                "/api/v1/operations/automation/task-definitions/nightly/run-once",
                {"admissionRequestId": request_id},
            )
            second_status, second = self.request(
                value,
                "POST",
                "/api/v1/operations/automation/task-definitions/nightly/run-once",
                {"admissionRequestId": request_id},
            )
            self.assertEqual(202, first_status)
            self.assertEqual(202, second_status)
            self.assertEqual(first["discoveryId"], second["discoveryId"])

    def test_run_once_list_is_principal_scoped(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            self.request(
                value,
                "POST",
                "/api/v1/operations/automation/task-definitions/nightly/run-once",
                {},
            )
            status, body = self.request(value, "GET", "/api/v1/operations/automation/run-once")
            self.assertEqual(200, status)
            self.assertEqual(1, body["total"])
            self.assertEqual("nightly", body["items"][0]["definitionId"])

    def test_definition_history_lists_the_manual_run_once(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            self.request(
                value,
                "POST",
                "/api/v1/operations/automation/task-definitions/nightly/run-once",
                {},
            )
            self.drive(value)
            status, body = self.request(
                value,
                "GET",
                "/api/v1/operations/automation/task-definitions/nightly/occurrences",
            )
            self.assertEqual(200, status)
            manual = [item for item in body["items"] if item.get("trigger") == "manual"]
            self.assertEqual(1, len(manual))
            self.assertEqual("nightly", manual[0]["definitionId"])
            self.assertIsNone(manual[0]["occurrenceId"])
            self.assertIsNone(manual[0]["jobId"])

    # -- refusals and principal isolation --------------------------------

    def test_lost_response_reconciles_by_the_client_request_identity(self) -> None:
        """A lost admission response reads back its own proved original.

        The request identity is generated before the POST, so it proves the
        *actual* admission even after the Active pin changed; a proved absence is
        a bounded 404, never a guessed latest run.
        """

        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            request_id = "33333333-3333-4333-8333-333333333333"
            # No admission exists for this identity yet: an honest absence.
            status, absent = self.request(
                value,
                "GET",
                "/api/v1/operations/automation/task-definitions/nightly/run-once"
                f"?admissionRequestId={request_id}",
            )
            self.assertEqual(404, status)
            self.assertEqual("run_once_request_not_found", absent["error"]["code"])
            self.assertEqual("unknown", absent["error"]["details"]["durableState"])
            # Admit, then reconcile the same identity to the same durable run.
            status, admitted = self.request(
                value,
                "POST",
                "/api/v1/operations/automation/task-definitions/nightly/run-once",
                {"admissionRequestId": request_id},
            )
            self.assertEqual(202, status, admitted)
            status, reconciled = self.request(
                value,
                "GET",
                "/api/v1/operations/automation/task-definitions/nightly/run-once"
                f"?admissionRequestId={request_id}",
            )
            self.assertEqual(200, status, reconciled)
            self.assertEqual(admitted["discoveryId"], reconciled["discoveryId"])
            # The reconciliation never created a second run.
            status, listing = self.request(value, "GET", "/api/v1/operations/automation/run-once")
            self.assertEqual(200, status)
            self.assertEqual(1, listing["total"])
            self.assertEqual([], value.source.mutations)

    def test_observed_definition_fence_refuses_a_stale_request(self) -> None:
        """A stale observed definition/configuration refuses the new admission.

        The same stale action must never silently admit today's published
        definition: the operator reviewed a specific binding, so a changed
        fingerprint or a repinned Active is a 409, not a repin.
        """

        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            definition = next(
                item
                for item in value.runtime.automation_task_definitions
                if item.definition_id == "nightly"
            )
            status, body = self.request(
                value,
                "POST",
                "/api/v1/operations/automation/task-definitions/nightly/run-once",
                {
                    "admissionRequestId": "11111111-1111-4111-8111-111111111111",
                    "expectedDefinitionFingerprint": definition.definition_fingerprint,
                    "expectedRevisionId": value.revision.revision_id,
                    "expectedRevisionVersion": value.revision.version,
                    "expectedRevisionDigest": value.revision.digest,
                },
            )
            self.assertEqual(202, status, body)
            self.assertEqual("nightly", body["definitionId"])
            # A changed observed definition fingerprint is refused.
            status, stale = self.request(
                value,
                "POST",
                "/api/v1/operations/automation/task-definitions/nightly/run-once",
                {"expectedDefinitionFingerprint": "0" * 64},
            )
            self.assertEqual(409, status)
            self.assertEqual("definition_stale", stale["error"]["code"])
            # A repinned Active is refused.
            status, repinned = self.request(
                value,
                "POST",
                "/api/v1/operations/automation/task-definitions/nightly/run-once",
                {
                    "expectedRevisionId": "other-revision",
                    "expectedRevisionVersion": 1,
                    "expectedRevisionDigest": "other-digest",
                },
            )
            self.assertEqual(409, status)
            self.assertEqual("configuration_stale", repinned["error"]["code"])
            # A partial fence is malformed rather than silently weakened.
            status, _partial = self.request(
                value,
                "POST",
                "/api/v1/operations/automation/task-definitions/nightly/run-once",
                {"expectedRevisionId": "other-revision"},
            )
            self.assertEqual(400, status)
            # The refused admissions created no additional work.
            status, listing = self.request(value, "GET", "/api/v1/operations/automation/run-once")
            self.assertEqual(200, status)
            self.assertEqual(1, listing["total"])
            self.assertEqual([], value.source.mutations)

    def test_unreadable_subtree_refuses_the_definition_manifest(self) -> None:
        """An incomplete definition-derived walk cannot finalize over the API."""

        self.media("Movies/One.2001.mkv")
        self.media("Locked/Two.2002.mkv")
        with self.journey(source_scope=None) as value:
            status, body = self.request(
                value,
                "POST",
                "/api/v1/operations/automation/task-definitions/nightly/run-once",
                {},
            )
            self.assertEqual(202, status)
            value.source.fail_listing("Locked")
            settled = self.drive(value)
            status, refused = self.request(
                value,
                "POST",
                f"/api/v1/operations/automation/run-once/{body['discoveryId']}/finalize",
                {"expectedVersion": settled.version},
            )
            self.assertEqual(409, status)
            self.assertEqual("discovery_incomplete_manifest", refused["error"]["code"])
            self.assertEqual("read_failure", refused["error"]["details"]["incompleteReason"])
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_viewer_cannot_start_run_once_and_creates_nothing(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            status, _body = self.request(
                value,
                "POST",
                "/api/v1/operations/automation/task-definitions/nightly/run-once",
                {},
                token=VIEWER_TOKEN,
            )
            self.assertEqual(403, status)
            self.assertEqual((), value.discovery.list(actor="admin"))
            self.assertEqual([], value.source.mutations)

    def test_draft_only_definition_cannot_run_once(self) -> None:
        # A definition that exists only in an unpublished Draft is not a
        # published definition, so Run once refuses instead of running a Draft.
        with self.journey(definitions=[]) as value:
            active = value.managed.active()
            assert active is not None
            draft = value.managed.create_successor_draft(
                actor="tester", expected_active_revision_id=active.revision_id
            )
            from mediaflow.application.configuration_objects import (
                ConfigurationObjectService,
            )
            from mediaflow.domain.configuration_management import (
                ConfigurationObjectKind,
            )

            ConfigurationObjectService(value.managed).mutate(
                draft.revision_id,
                ConfigurationObjectKind.SCHEDULE,
                object_id=None,
                value={
                    "id": "draft-only",
                    "name": "Draft only",
                    "resourceLibraryId": "library",
                    "mode": "automatic-organization",
                    "intervalSeconds": 3600,
                    "itemLimit": 10,
                    "enabled": True,
                },
                expected_version=draft.version,
                actor="tester",
            )
            status, body = self.request(
                value,
                "POST",
                "/api/v1/operations/automation/task-definitions/draft-only/run-once",
                {},
            )
            self.assertEqual(404, status)
            self.assertEqual("definition_not_found", body["error"]["code"])
            self.assertEqual((), value.discovery.list(actor="admin"))

    def test_malformed_run_once_body_is_rejected(self) -> None:
        with self.journey(source_scope="Movies") as value:
            status, _body = self.request(
                value,
                "POST",
                "/api/v1/operations/automation/task-definitions/nightly/run-once",
                {"paths": ["Movies"]},
            )
            self.assertEqual(400, status)

    def test_removed_mode_definition_cannot_be_published_or_run(self) -> None:
        with self.journey(definitions=[]) as value:
            active = value.managed.active()
            assert active is not None
            status, _body = self.request(
                value,
                "POST",
                "/api/v1/operations/automation/definitions",
                {
                    "expectedRevisionId": active.revision_id,
                    "expectedVersion": active.version,
                    "expectedDigest": active.digest,
                    "object": {
                        "id": "legacy",
                        "name": "Legacy",
                        "resourceLibraryId": "library",
                        "mode": "scan-and-plan",
                        "intervalSeconds": 3600,
                        "itemLimit": 10,
                    },
                },
            )
            self.assertGreaterEqual(status, 400)
            self.assertNotEqual(200, status)
            status, body = self.request(
                value,
                "POST",
                "/api/v1/operations/automation/task-definitions/legacy/run-once",
                {},
            )
            self.assertEqual(404, status)
            self.assertEqual("definition_not_found", body["error"]["code"])


if __name__ == "__main__":
    unittest.main()
