"""Task 43.2 — definition-bound automatic Run once.

These tests prove the remaining RO-4/RO-3 journey against the real runtime
SQLite repository, real Local Storage adapters and the real application/API
services:

* a published ``automatic-organization`` definition runs once *without* a file
  picker: the backend derives the whole scope from the definition itself;
* a disabled published schedule is runnable once and the run neither enables the
  schedule, nor grants/revives/consumes unattended authority, nor advances due
  state;
* the effective manifest bound is ``min(definition ceiling, 100)`` and an
  over-bound or incomplete walk refuses execution instead of freezing a first-N
  prefix;
* the frozen manifest yields an exact zero-mutation Preview whose separate
  one-shot execution intent is the only path to mutation;
* a recorded pre-amendment mode cannot be run once, published or executed.
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

from mediaflow.application.automation_run_once import (
    AutomationRunOnceError,
    AutomationRunOnceService,
    definition_run_once_available,
)
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_execution import ManualOrganizeExecutionService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.manual_organize_worker import ManualOrganizeExecutionWorker
from mediaflow.application.media_discovery import MediaDiscoveryService
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.domain.automation import AutomationTaskDefinition, AutomationTaskRunMode
from mediaflow.domain.media_discovery import (
    DefinitionRunOnceOrigin,
    DiscoveryBudgets,
    DiscoveryError,
    DiscoveryStatus,
    effective_primary_limit,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.storage import StorageError, StorageErrorCode
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

OPERATOR_TOKEN = "operator-token"


class _Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now = self.now + timedelta(seconds=seconds)


class _RecordingStorage:
    """Wrap Local Storage and record every call so mutation can be proven absent."""

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


def _provider_registry():
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


def _activate(service, document):
    draft = service.import_draft(document, actor="tester")
    validated = service.validate(draft.revision_id, actor="tester")
    if validated.status.value != "validated":
        raise AssertionError(validated.validation_errors)
    return service.activate(
        validated.revision_id, expected_version=validated.version, actor="tester"
    )


class _RunOnceFixture(unittest.TestCase):
    """A real managed runtime with one published automatic-organization definition."""

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        self.source_root = self.root / "source"
        self.source_root.mkdir()
        self.target_root = self.root / "target"
        self.target_root.mkdir()
        self.database = self.root / "runtime.sqlite3"
        self.clock = _Clock()

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def media(self, relative: str, *, size: int = 512, modified_at: datetime | None = None):
        path = self.source_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"m" * size)
        if modified_at is not None:
            stamp = modified_at.timestamp()
            os.utime(path, (stamp, stamp))
        return path

    def document(self, *, definitions=None, item_limit: int = 10, source_scope=None) -> dict:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        document["persistence"]["databasePath"] = str(self.database)
        document["historyPath"] = str(self.root / "history.jsonl")
        document["storages"] = [
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
        document["resourceLibraries"] = [
            {
                "id": "library",
                "name": "Library",
                "storageId": "source",
                "storagePath": "",
                "enabled": True,
                "extensions": ["mkv", "mp4"],
            }
        ]
        document["mediaLibraries"] = [
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
            value = {
                "id": "nightly",
                "name": "Nightly",
                "resourceLibraryId": "library",
                "mode": "automatic-organization",
                "intervalSeconds": 3600,
                "itemLimit": item_limit,
                "enabled": False,
            }
            if source_scope is not None:
                value["sourceScope"] = source_scope
            definitions = [value]
        document["automationTaskDefinitions"] = definitions
        return document

    @contextmanager
    def journey(self, *, definitions=None, item_limit: int = 10, source_scope=None, budgets=None):
        document = self.document(
            definitions=definitions, item_limit=item_limit, source_scope=source_scope
        )
        source = _RecordingStorage(LocalStorage("source", self.source_root))
        target = _RecordingStorage(LocalStorage("target", self.target_root))
        storages = {"source": source, "target": target}
        with (
            SQLiteConfigurationRepository(self.database) as configuration_repository,
            SQLiteTaskRepository(self.database) as repository,
        ):
            managed = ManagedConfigurationService(
                configuration_repository,
                bootstrap_database_path=str(self.database),
            )
            revision = _activate(managed, document)
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
                None,
                managed,
                runtime_resolver=lambda snapshot_id, digest: runtime,
                storage_factory=lambda value, ids: dict(storages),
            )
            previews = ManualOrganizePreviewService(
                repository,
                intents,
                None,
                configuration=runtime,
                providers=_provider_registry(),
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
                budgets=budgets or DiscoveryBudgets(),
            )
            from mediaflow.application.automation_task_definition_preview import (
                AutomationTaskDefinitionPreviewService,
            )
            from mediaflow.application.preview_analysis import (
                PreviewAnalysisService,
                PreviewAnalysisWorker,
            )

            definition_previews = AutomationTaskDefinitionPreviewService(
                repository,
                managed,
                runtime_resolver=lambda snapshot_id, digest: runtime,
                storages=dict(storages),
                clock=self.clock,
            )
            analyses = PreviewAnalysisService(
                repository,
                definition_previews=definition_previews,
                manual_previews=previews,
                clock=self.clock,
            )
            analysis_worker = PreviewAnalysisWorker(analyses, worker_id="harness-analysis-worker")
            run_once = AutomationRunOnceService(
                discovery,
                intents,
                previews,
                analysis_service=analyses,
                clock=self.clock,
            )
            execution = ManualOrganizeExecutionService(
                repository,
                previews,
                intents,
                configuration=runtime,
                storages=dict(storages),
                checkpoint_service=ProcessingCheckpointService(repository),
                clock=self.clock,
            )
            execution_worker = ManualOrganizeExecutionWorker(
                execution, clock=self.clock, worker_id="harness-execution-worker"
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
                                ApiPermission.SUBMIT_DRY_RUN,
                            }
                        ),
                    ),
                    ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ})),
                ),
                configuration_service=managed,
                bootstrap_document=document,
                manual_intent_service=intents,
                manual_preview_service=previews,
                manual_execution_service=execution,
                media_discovery_service=discovery,
                automation_run_once_service=run_once,
                storage_adapters=dict(storages),
            )
            yield SimpleNamespace(
                api=api,
                repository=repository,
                intents=intents,
                previews=previews,
                discovery=discovery,
                definition_previews=definition_previews,
                analyses=analyses,
                analysis_worker=analysis_worker,
                execution=execution,
                execution_worker=execution_worker,
                run_once=run_once,
                configuration=runtime,
                clock=self.clock,
                source=source,
                target=target,
                storages=storages,
                revision=revision,
                managed=managed,
            )

    @staticmethod
    def request(value, path: str, method: str = "GET", body=None, *, token=OPERATOR_TOKEN):
        statuses: list[str] = []
        raw = json.dumps(body).encode() if body is not None else b""
        path_info, _, query_string = path.partition("?")
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path_info,
            "QUERY_STRING": query_string,
            "CONTENT_LENGTH": str(len(raw)),
            "REMOTE_ADDR": "127.0.0.1",
            "wsgi.input": io.BytesIO(raw),
            "CONTENT_TYPE": "application/json",
            "HTTP_AUTHORIZATION": f"Bearer {token}",
        }
        response = b"".join(value.api(environ, lambda status, headers: statuses.append(status)))
        return int(statuses[0].split()[0]), json.loads(response)

    def drive(self, value, *, steps: int = 12):
        """Drive the resident Worker until the definition-bound discovery settles."""

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
            raise AssertionError("Run-once discovery did not settle in the bounded step budget")
        return result


class ModeRemovalTests(_RunOnceFixture):
    """AC-T9: only automatic organization is a runnable definition mode."""

    def test_removed_modes_are_not_runnable_and_are_rejected(self) -> None:
        self.assertEqual(
            (AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,),
            AutomationTaskRunMode.runnable_modes(),
        )
        for value in (
            "scan-only",
            "scan_only",
            "scanOnly",
            "scan",
            "scan-and-plan",
            "scan_and_plan",
            "scanAndPlan",
            "preview",
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    AutomationTaskRunMode.parse(value)
                with self.assertRaises(ValueError):
                    AutomationTaskDefinition(
                        "d", "n", "library", None, value, 3600.0, None, None, 10, False
                    )

    def test_recorded_modes_stay_readable_but_are_not_runnable(self) -> None:
        for value in ("scan-only", "scan-and-plan"):
            with self.subTest(value=value):
                recorded = AutomationTaskRunMode.decode_recorded(value)
                self.assertFalse(recorded.is_runnable)
                self.assertEqual(value, recorded.value)

    def test_form_authority_offers_only_the_retained_mode(self) -> None:
        with self.journey() as value:
            status, document = self.request(value, "/api/v1/operations/automation/definitions")
        self.assertEqual(200, status)
        self.assertEqual(["automatic-organization"], document["enums"]["modes"])
        self.assertEqual("automatic-organization", document["defaults"]["mode"])

    def test_removed_mode_definition_is_refused_by_publication(self) -> None:
        with self.journey(definitions=[]) as value:
            active = value.managed.active()
            status, document = self.request(
                value,
                "/api/v1/operations/automation/definitions",
                "POST",
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

    def test_removed_mode_definition_cannot_run_once(self) -> None:
        with self.journey(definitions=[]) as value:
            with self.assertRaises(DiscoveryError) as caught:
                value.run_once.admit("legacy", actor="operator")
            self.assertEqual("definition_not_found", caught.exception.code)


class EffectiveBoundTests(unittest.TestCase):
    """AC-T2: the effective manifest bound is min(definition ceiling, 100)."""

    def test_effective_bound_is_the_smaller_of_ceiling_and_manual_bound(self) -> None:
        self.assertEqual(5, effective_primary_limit(5))
        self.assertEqual(100, effective_primary_limit(100))
        self.assertEqual(100, effective_primary_limit(250))
        self.assertEqual(100, effective_primary_limit(10_000))

    def test_origin_rejects_an_effective_bound_above_the_manual_bound(self) -> None:
        with self.assertRaises(ValueError):
            DefinitionRunOnceOrigin(
                "d", "n", "a" * 64, "r1", 1, "b" * 64, "library", None, 250, 250
            )

    def test_run_once_available_reports_an_over_bound_ceiling_is_legal(self) -> None:
        """A ceiling above the manual bound is a legal, runnable definition.

        The Contract applies ``min(ceiling, 100)`` to the *actual manifest*, so
        the definition must be admitted; only an actual overflow refuses.
        """

        definition = AutomationTaskDefinition(
            "d",
            "n",
            "library",
            None,
            AutomationTaskRunMode.AUTOMATIC_ORGANIZATION,
            3600.0,
            None,
            None,
            250,
            False,
        )
        available, reason = definition_run_once_available(definition)
        self.assertTrue(available, reason)
        self.assertIsNone(reason)


class RunOnceJourneyTests(_RunOnceFixture):
    """AC-T1/T2/T5/T6: automatic discovery, frozen manifest and separate execution."""

    def test_disabled_published_definition_runs_once_without_a_file_picker(self) -> None:
        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        with self.journey(source_scope="Movies") as value:
            before = value.managed.active()
            definition = next(
                item
                for item in value.configuration.automation_task_definitions
                if item.definition_id == "nightly"
            )
            self.assertFalse(definition.enabled)
            # Admission is prompt and creates no Storage mutation.
            discovery = value.run_once.admit("nightly", actor="operator")
            self.assertEqual("library", discovery.resource_library_id)
            self.assertEqual("Movies", discovery.definition_origin.source_scope)
            self.assertEqual([], value.source.mutations)
            settled = self.drive(value)
            self.assertEqual(DiscoveryStatus.COMPLETED, settled.status)
            self.assertEqual(2, len(settled.sources))
            # The scope came from the definition, never from a submitted path.
            self.assertEqual(
                ("Movies",),
                tuple(entry.path for entry in settled.progress.scope_entries),
            )
            # No schedule/authority state changed.
            self.assertEqual(before.revision_id, value.managed.active().revision_id)
            self.assertIsNone(value.repository.get_automation_definition_due_state("nightly"))
            self.assertIsNone(value.repository.get_active_unattended_execution_grant("nightly"))

    def test_finalize_freezes_the_manifest_and_creates_an_exact_preview(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            discovery = value.run_once.admit("nightly", actor="operator")
            self.drive(value)
            current = value.run_once.get(discovery.discovery_id)
            frozen, preview, analysis = value.run_once.finalize(
                discovery.discovery_id,
                actor="operator",
                expected_version=current.version,
            )
            self.assertIsNotNone(frozen.frozen_at)
            self.assertIsNotNone(frozen.intent_id)
            self.assertEqual("automatic-organization", frozen.definition_origin.run_mode)
            # With a durable analysis service bound, the exact Preview work is
            # deferred to the resident Worker instead of running inline.
            self.assertIsNone(preview)
            self.assertIsNotNone(analysis)
            self.assertEqual("queued", analysis.status.value)
            self.assertEqual(frozen.intent_id, analysis.intent_id)
            # Freezing and Preview admission are still zero-mutation: only a
            # separate explicit execution may ever reach OrganizerExecutor.
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            document = value.run_once.document(frozen)
            self.assertEqual("frozen", document["phase"])
            self.assertTrue(document["frozen"])
            self.assertTrue(document["actions"]["preview"])

    def test_finalize_runs_inline_when_no_analysis_service_is_bound(self) -> None:
        """Without a durable analysis service the inline exact Preview is kept."""

        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            value.run_once.bind_analysis_service(None)
            discovery = value.run_once.admit("nightly", actor="operator")
            self.drive(value)
            current = value.run_once.get(discovery.discovery_id)
            frozen, preview, analysis = value.run_once.finalize(
                discovery.discovery_id,
                actor="operator",
                expected_version=current.version,
            )
            self.assertIsNone(analysis)
            self.assertIsNotNone(preview)
            self.assertTrue(preview.zero_mutation)
            self.assertIsNotNone(preview.preview_id)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_frozen_manifest_reaches_linked_execution_and_operations_origin(self) -> None:
        """The complete Run-once journey reaches a real linked execution.

        Freeze → exact manual Preview → one separate explicit execution →
        resident Worker outcome, with the definition origin durable on the
        resulting Operations run.  The analysis is zero mutation throughout and
        only the explicit confirmation reaches ``OrganizerExecutor``.
        """

        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            discovery = value.run_once.admit("nightly", actor="operator")
            self.drive(value)
            current = value.run_once.get(discovery.discovery_id)
            frozen, preview, analysis = value.run_once.finalize(
                discovery.discovery_id,
                actor="operator",
                expected_version=current.version,
            )
            self.assertIsNotNone(analysis)
            # The resident Worker completes the durable exact analysis.
            settled = value.analysis_worker.run_next()
            self.assertIsNotNone(settled)
            self.assertEqual("completed", settled.status.value)
            preview_id = settled.preview_id
            self.assertIsNotNone(preview_id)
            # The exact Preview is the *manual* Preview over the frozen intent.
            preview = value.previews.get(preview_id)
            self.assertEqual(frozen.intent_id, preview.intent_id)
            self.assertTrue(preview.zero_mutation)
            # No mutation happened merely by admitting and analysing.
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            # One separate explicit confirmation executes the exact selection.
            item_ids = [item.item_id for item in preview.items if item.status.value == "previewed"]
            self.assertTrue(item_ids)
            execution = value.execution.begin_web_execution(
                preview_id,
                item_ids,
                expected_intent_version=preview.intent_version,
                actor="operator",
                confirmation=True,
            )
            self.assertIsNotNone(execution.execution_id)
            run = value.execution_worker.run_next()
            self.assertIsNotNone(run)
            self.assertEqual(execution.execution_id, run.execution_id)
            # The executed run carries the durable definition origin on its
            # Operations run projection, so Operations and the definition
            # history reach the same durable run without a dummy Job.
            self.assertIsNotNone(run.task_id)
            overviews = value.repository.list_operations_runs(limit=10)
            manual = [item for item in overviews if item.origin_definition_id == "nightly"]
            self.assertEqual(1, len(manual))
            self.assertEqual("definition-run-once", manual[0].origin_kind)
            self.assertEqual("Nightly", manual[0].origin_definition_name)
            self.assertEqual(run.task_id, manual[0].task_id)
            # The definition history lists the same durable manual run.
            history = value.repository.list_definition_run_once_discoveries("nightly")
            self.assertEqual(1, len(history))
            self.assertEqual(discovery.discovery_id, history[0].discovery_id)
            self.assertEqual(frozen.intent_id, history[0].intent_id)

    def test_over_bound_ceiling_with_one_eligible_file_is_admitted(self) -> None:
        """Ceiling 250 with one eligible file runs once completely.

        The effective manifest bound is min(250, 100) = 100 and the actual
        manifest holds one source, so no overflow exists.  The definition is
        admitted and reads Storage; it is never refused before the walk.
        """

        self.media("Movies/One.2001.mkv")
        with self.journey(item_limit=250, source_scope="Movies") as value:
            discovery = value.run_once.admit("nightly", actor="operator")
            self.assertEqual(250, discovery.definition_origin.definition_item_limit)
            self.assertEqual(100, discovery.definition_origin.effective_primary_limit)
            self.assertEqual(100, discovery.budgets.max_primary_sources)
            settled = self.drive(value)
            self.assertEqual(DiscoveryStatus.COMPLETED, settled.status)
            self.assertEqual(1, len(settled.sources))
            document = value.run_once.document(settled)
            self.assertEqual("ready", document["phase"])
            self.assertTrue(document["actions"]["finalize"]["available"])
            self.assertTrue(value.source.reads)

    def test_ceiling_at_the_manual_bound_is_admitted_with_that_exact_bound(self) -> None:
        """A ceiling exactly equal to the manual bound keeps its own bound."""

        self.media("Movies/One.2001.mkv")
        with self.journey(item_limit=100, source_scope="Movies") as value:
            discovery = value.run_once.admit("nightly", actor="operator")
            self.assertEqual(100, discovery.budgets.max_primary_sources)
            self.assertEqual(100, discovery.definition_origin.effective_primary_limit)
            self.assertEqual(100, discovery.definition_origin.definition_item_limit)
            settled = self.drive(value)
            self.assertEqual(DiscoveryStatus.COMPLETED, settled.status)
            self.assertEqual(1, len(settled.sources))

    def test_ceiling_above_the_manual_bound_uses_the_manual_bound(self) -> None:
        """A ceiling above the bound is admitted with the bound as its limit.

        The bound is applied to the *actual* manifest: a scope holding fewer
        eligible sources than the bound is discovered and frozen completely.
        Only an actual overflow refuses; the definition itself is legal.
        """

        for ceiling in (101, 1000, 10_000):
            with self.subTest(ceiling=ceiling):
                self.media("Movies/One.2001.mkv")
                with self.journey(item_limit=ceiling, source_scope="Movies") as value:
                    discovery = value.run_once.admit("nightly", actor="operator")
                    self.assertEqual(ceiling, discovery.definition_origin.definition_item_limit)
                    self.assertEqual(100, discovery.definition_origin.effective_primary_limit)
                    self.assertEqual(100, discovery.budgets.max_primary_sources)
                    settled = self.drive(value)
                    self.assertEqual(DiscoveryStatus.COMPLETED, settled.status)
                    self.assertEqual(1, len(settled.sources))
                    document = value.run_once.document(settled)
                    self.assertEqual("ready", document["phase"])
                    self.assertTrue(document["actions"]["finalize"]["available"])

    def test_actual_overflow_above_the_effective_bound_is_refused(self) -> None:
        """An actual manifest above min(ceiling, 100) is refused, never truncated."""

        # 101 eligible primaries exceed the effective bound of 100, so the walk
        # records a truncated prefix and freezing must be refused.
        for index in range(101):
            self.media(f"Movies/Movie{index:03d}.2001.mkv")
        with self.journey(item_limit=250, source_scope="Movies") as value:
            discovery = value.run_once.admit("nightly", actor="operator")
            self.assertEqual(100, discovery.budgets.max_primary_sources)
            settled = self.drive(value)
            self.assertEqual(DiscoveryStatus.PARTIAL_SUCCESS, settled.status)
            self.assertEqual(100, len(settled.sources))
            document = value.run_once.document(settled)
            self.assertEqual("refused", document["phase"])
            self.assertFalse(document["actions"]["finalize"]["available"])
            self.assertTrue(document["actions"]["narrowScope"]["available"])
            with self.assertRaises(AutomationRunOnceError) as caught:
                value.run_once.finalize(
                    discovery.discovery_id,
                    actor="operator",
                    expected_version=settled.version,
                )
            self.assertEqual("discovery_overflow", caught.exception.code)

    def test_ceiling_below_the_manual_bound_uses_the_smaller_bound(self) -> None:
        """A small definition ceiling is the effective manifest bound."""

        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        self.media("Movies/Three.2003.mkv")
        with self.journey(item_limit=2, source_scope="Movies") as value:
            discovery = value.run_once.admit("nightly", actor="operator")
            self.assertEqual(2, discovery.budgets.max_primary_sources)
            self.assertEqual(2, discovery.definition_origin.effective_primary_limit)
            settled = self.drive(value)
            # Reaching the definition's own primary bound is a material
            # refusal: the recorded sources are a truncated prefix and must
            # never be frozen or executed as if complete.
            self.assertEqual(DiscoveryStatus.PARTIAL_SUCCESS, settled.status)
            document = value.run_once.document(settled)
            self.assertEqual("refused", document["phase"])
            self.assertFalse(document["actions"]["finalize"]["available"])
            self.assertTrue(document["actions"]["narrowScope"]["available"])
            with self.assertRaises(AutomationRunOnceError) as caught:
                value.run_once.finalize(
                    discovery.discovery_id,
                    actor="operator",
                    expected_version=settled.version,
                )
            self.assertEqual("discovery_overflow", caught.exception.code)

    def test_manifest_below_the_bound_is_not_refused(self) -> None:
        """Fewer sources than the bound freeze normally."""

        self.media("Movies/One.2001.mkv")
        with self.journey(item_limit=3, source_scope="Movies") as value:
            value.run_once.admit("nightly", actor="operator")
            settled = self.drive(value)
            self.assertEqual(DiscoveryStatus.COMPLETED, settled.status)
            self.assertEqual(1, len(settled.sources))
            document = value.run_once.document(settled)
            self.assertEqual("ready", document["phase"])
            self.assertTrue(document["actions"]["finalize"]["available"])

    def test_empty_scope_reports_no_work(self) -> None:
        (self.source_root / "Movies").mkdir()
        with self.journey(source_scope="Movies") as value:
            discovery = value.run_once.admit("nightly", actor="operator")
            settled = self.drive(value)
            self.assertEqual(DiscoveryStatus.COMPLETED, settled.status)
            self.assertEqual(0, len(settled.sources))
            document = value.run_once.document(settled)
            self.assertEqual("no_work", document["phase"])
            self.assertFalse(document["actions"]["finalize"]["available"])
            with self.assertRaises(AutomationRunOnceError) as caught:
                value.run_once.finalize(
                    discovery.discovery_id,
                    actor="operator",
                    expected_version=settled.version,
                )
            self.assertEqual("selection_empty", caught.exception.code)

    def test_run_once_is_prompt_and_durable_for_api_readback(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            status, document = self.request(
                value,
                "/api/v1/operations/automation/task-definitions/nightly/run-once",
                "POST",
                {},
            )
            self.assertEqual(202, status)
            self.assertEqual("discovering", document["phase"])
            self.assertEqual("nightly", document["definitionId"])
            discovery_id = document["discoveryId"]
            self.drive(value)
            status, detail = self.request(
                value, f"/api/v1/operations/automation/run-once/{discovery_id}"
            )
            self.assertEqual(200, status)
            self.assertEqual("ready", detail["phase"])

    def test_duplicate_admission_reconciles_to_one_durable_run(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            first = value.run_once.admit(
                "nightly",
                actor="operator",
                admission_request_id="11111111-1111-1111-1111-111111111111",
            )
            second = value.run_once.admit(
                "nightly",
                actor="operator",
                admission_request_id="11111111-1111-1111-1111-111111111111",
            )
            self.assertEqual(first.discovery_id, second.discovery_id)
            third = value.run_once.admit("nightly", actor="operator")
            self.assertEqual(first.discovery_id, third.discovery_id)

    def test_every_accepted_request_identity_keeps_its_own_durable_lookup(
        self,
    ) -> None:
        """Each accepted request ID reconciles to the work it actually created.

        Two equivalent Run-once requests from the same principal converge on
        one durable discovery — but *both* submitted request identities are
        durably associated with that admission, so a lost response for either
        one reconciles by its own ID instead of a bounded 404 that reads as
        "no work exists" (B43.2-R3-2).
        """

        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            first_request = "12121212-1212-4212-8212-121212121212"
            second_request = "34343434-3434-4343-8434-343434343434"
            first = value.run_once.admit(
                "nightly", actor="operator", admission_request_id=first_request
            )
            second = value.run_once.admit(
                "nightly", actor="operator", admission_request_id=second_request
            )
            # Equivalent open work converges on one durable discovery.
            self.assertEqual(first.discovery_id, second.discovery_id)
            # Each accepted identity stays verifiably associated with it.
            readback_first = value.discovery.find_by_request_id(
                actor="operator", admission_request_id=first_request
            )
            readback_second = value.discovery.find_by_request_id(
                actor="operator", admission_request_id=second_request
            )
            self.assertIsNotNone(readback_first)
            self.assertIsNotNone(readback_second)
            self.assertEqual(first.discovery_id, readback_first.discovery_id)
            self.assertEqual(second.discovery_id, readback_second.discovery_id)
            self.assertEqual([], value.source.mutations)

    def test_definition_analysis_request_alias_keeps_its_own_durable_lookup(
        self,
    ) -> None:
        """A definition-analysis request ID that converged on open work stays readable."""

        with self.journey() as value:
            first_request = "56565656-5656-4565-8565-565656565656"
            second_request = "78787878-7878-4787-8787-787878787878"
            first = value.analyses.admit_definition(
                "nightly", actor="operator", admission_request_id=first_request
            )
            second = value.analyses.admit_definition(
                "nightly", actor="operator", admission_request_id=second_request
            )
            self.assertEqual(first.analysis_id, second.analysis_id)
            readback_second = value.analyses.find_by_request_id(
                actor="operator", admission_request_id=second_request
            )
            self.assertIsNotNone(readback_second)
            self.assertEqual(first.analysis_id, readback_second.analysis_id)

    def test_run_once_requires_the_published_definition(self) -> None:
        with self.journey() as value:
            with self.assertRaises(DiscoveryError) as caught:
                value.run_once.admit("absent", actor="operator")
            self.assertEqual("definition_not_found", caught.exception.code)

    def test_root_scope_runs_once_over_the_whole_resource_library(self) -> None:
        """A definition with no sub-scope derives the ResourceLibrary root."""

        self.media("One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        with self.journey(source_scope=None) as value:
            discovery = value.run_once.admit("nightly", actor="operator")
            self.assertIsNone(discovery.definition_origin.source_scope)
            settled = self.drive(value)
            self.assertEqual(DiscoveryStatus.COMPLETED, settled.status)
            self.assertEqual(
                ("",),
                tuple(entry.path for entry in settled.progress.scope_entries),
            )
            self.assertEqual(
                {"One.2001.mkv", "Movies/Two.2002.mkv"},
                {item["path"] for item in settled.sources},
            )

    def test_scope_narrowing_after_an_overflow_recovers(self) -> None:
        """A refused actual-overflow run recovers by narrowing and republishing."""

        # The overflow must be a *real* manifest overflow: 101 eligible
        # primaries against the effective bound of 100.  A mere ceiling above
        # 100 is legal and is covered by the bound tests above.
        for index in range(101):
            self.media(f"Movies/Movie{index:03d}.2001.mkv")
        self.media("Other/Two.2002.mkv")
        with self.journey(item_limit=250, source_scope="Movies") as value:
            discovery = value.run_once.admit("nightly", actor="operator")
            settled = self.drive(value)
            self.assertEqual(DiscoveryStatus.PARTIAL_SUCCESS, settled.status)
            document = value.run_once.document(settled)
            self.assertEqual("refused", document["phase"])
            with self.assertRaises(AutomationRunOnceError) as caught:
                value.run_once.finalize(
                    discovery.discovery_id,
                    actor="operator",
                    expected_version=settled.version,
                )
            self.assertEqual("discovery_overflow", caught.exception.code)
        # The same definition with a bound inside the manual limit now runs and
        # discovers only its own narrowed scope, proving the recovery path.
        with self.journey(item_limit=5, source_scope="Other") as value:
            discovery = value.run_once.admit("nightly", actor="operator")
            settled = self.drive(value)
            self.assertEqual(DiscoveryStatus.COMPLETED, settled.status)
            self.assertEqual(5, discovery.definition_origin.effective_primary_limit)
            self.assertEqual(
                ("Other/Two.2002.mkv",),
                tuple(item["path"] for item in settled.sources),
            )

    def test_new_arrivals_after_the_freeze_are_not_in_the_manifest(self) -> None:
        """A frozen manifest is immutable: a later arrival is never included."""

        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            discovery = value.run_once.admit("nightly", actor="operator")
            settled = self.drive(value)
            self.assertEqual(1, len(settled.sources))
            frozen, _preview, _analysis = value.run_once.finalize(
                discovery.discovery_id,
                actor="operator",
                expected_version=settled.version,
            )
            self.assertEqual(
                ("Movies/One.2001.mkv",),
                tuple(item["path"] for item in frozen.sources),
            )
            # A new file arriving afterwards cannot rewrite the frozen manifest.
            self.media("Movies/Late.2003.mkv")
            reread = value.run_once.get(discovery.discovery_id)
            self.assertEqual(
                ("Movies/One.2001.mkv",),
                tuple(item["path"] for item in reread.sources),
            )
            self.assertEqual(frozen.frozen_at, reread.frozen_at)

    def test_a_changed_source_is_visible_before_the_freeze(self) -> None:
        """A source that changes before the walk settles is not frozen stale."""

        path = self.media("Movies/One.2001.mkv", size=512)
        with self.journey(source_scope="Movies") as value:
            value.run_once.admit("nightly", actor="operator")
            # Grow the file so its durable observation no longer matches.
            path.write_bytes(b"m" * 4096)
            settled = self.drive(value)
            # The walk either proves the new stable size or honestly reports the
            # still-waiting stability; it never freezes the superseded size as
            # if it were current.
            if settled.status is DiscoveryStatus.COMPLETED:
                self.assertEqual(4096, settled.sources[0]["size"])
            else:
                self.assertEqual(DiscoveryStatus.WAITING_STABILITY, settled.status)
                document = value.run_once.document(settled)
                self.assertFalse(document["actions"]["finalize"]["available"])

    def test_reads_and_denial_create_no_work_and_no_mutation(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            status, document = self.request(
                value,
                "/api/v1/operations/automation/run-once",
                token="viewer-token",
            )
            self.assertEqual(200, status)
            self.assertEqual([], document["items"])
            denied, _ = self.request(
                value,
                "/api/v1/operations/automation/task-definitions/nightly/run-once",
                "POST",
                {},
                token="viewer-token",
            )
            self.assertEqual(403, denied)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            self.assertEqual((), value.discovery.list(actor="operator"))

    def test_durable_analysis_is_pausable_and_cancellable_before_it_settles(self) -> None:
        """AC-T3: long analysis is durable, observable and safely controllable."""

        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            discovery = value.run_once.admit("nightly", actor="operator")
            # The durable record exists and is observable *before* the walk.
            current = value.run_once.get(discovery.discovery_id)
            self.assertEqual(DiscoveryStatus.QUEUED, current.status)
            document = value.run_once.document(current)
            self.assertEqual("discovering", document["phase"])
            self.assertTrue(document["actions"]["cancel"])
            paused = value.discovery.request_pause(
                discovery.discovery_id, actor="operator", expected_version=current.version
            )
            self.assertTrue(paused.pause_requested)
            # The operator's own control settles the walk at a safe boundary.
            settled = value.discovery.claim_and_run(worker_id="worker-0", claim_token="token-0")
            self.assertEqual(DiscoveryStatus.PAUSED, settled.status)
            cancelled = value.discovery.request_cancel(
                discovery.discovery_id,
                actor="operator",
                expected_version=settled.version,
            )
            self.assertEqual(DiscoveryStatus.CANCELLED, cancelled.status)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_an_unreadable_subtree_refuses_the_definition_manifest(self) -> None:
        """A definition-derived manifest must prove completeness.

        An unreadable subtree leaves the recorded sources a partial subset, so
        neither the Run-once route nor a direct generic finalize of the
        definition-origin record may freeze it into an executable manifest.
        """

        self.media("Movies/One.2001.mkv")
        self.media("Locked/Two.2002.mkv")
        with self.journey(source_scope=None) as value:
            discovery = value.run_once.admit("nightly", actor="operator")
            value.source.fail_listing("Locked")
            settled = self.drive(value)
            self.assertEqual(DiscoveryStatus.PARTIAL_SUCCESS, settled.status)
            self.assertEqual("read_failure", settled.progress.incomplete_reason.value)
            # The known subset is preserved for diagnosis ...
            self.assertEqual(1, len(settled.sources))
            document = value.run_once.document(settled)
            self.assertEqual("refused", document["phase"])
            self.assertFalse(document["actions"]["finalize"]["available"])
            self.assertTrue(document["actions"]["narrowScope"]["available"])
            # ... but it can never become an executable Automation manifest.
            with self.assertRaises(AutomationRunOnceError) as caught:
                value.run_once.finalize(
                    discovery.discovery_id,
                    actor="operator",
                    expected_version=settled.version,
                )
            self.assertEqual("discovery_incomplete_manifest", caught.exception.code)
            self.assertEqual("read_failure", caught.exception.details["incompleteReason"])
            # The shared authority boundary refuses it too: a direct generic
            # finalize of the definition-origin record is not a bypass.
            with self.assertRaises(DiscoveryError) as direct:
                value.discovery.finalize(
                    discovery.discovery_id,
                    actor="operator",
                    expected_version=settled.version,
                )
            self.assertEqual("discovery_incomplete_manifest", direct.exception.code)
            self.assertIsNone(value.run_once.get(discovery.discovery_id).intent_id)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_a_standalone_files_read_failure_subset_still_freezes(self) -> None:
        """The accepted standalone Files explicit-subset path is unchanged."""

        self.media("Movies/One.2001.mkv")
        self.media("Locked/Two.2002.mkv")
        with self.journey() as value:
            admitted = value.discovery.admit(
                resource_library_id="library",
                relative_paths=["Movies", "Locked"],
                actor="operator",
            )
            value.source.fail_listing("Locked")
            settled = self.drive(value)
            self.assertEqual(DiscoveryStatus.PARTIAL_SUCCESS, settled.status)
            self.assertIsNone(settled.definition_origin)
            # No definition origin: the reviewed subset keeps its legal Finalize.
            frozen = value.discovery.finalize(
                admitted.discovery_id,
                actor="operator",
                expected_version=settled.version,
            )
            self.assertIsNotNone(frozen.intent_id)
            self.assertEqual([], value.source.mutations)

    def test_definition_fingerprint_fence_refuses_a_changed_definition(self) -> None:
        """A stale observed definition is refused, not silently re-pinned."""

        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            definition = next(
                item
                for item in value.configuration.automation_task_definitions
                if item.definition_id == "nightly"
            )
            # The exact observed fingerprint admits.
            admitted = value.run_once.admit(
                "nightly",
                actor="operator",
                expected_definition_fingerprint=definition.definition_fingerprint,
                expected_revision_id=value.revision.revision_id,
                expected_revision_version=value.revision.version,
                expected_revision_digest=value.revision.digest,
            )
            self.assertEqual("nightly", admitted.definition_origin.definition_id)
            # A different observed fingerprint is a stale binding.
            with self.assertRaises(DiscoveryError) as caught:
                value.run_once.admit(
                    "nightly",
                    actor="operator",
                    expected_definition_fingerprint="0" * 64,
                )
            self.assertEqual("definition_stale", caught.exception.code)
            # A repinned Active is equally stale.
            with self.assertRaises(DiscoveryError) as revision:
                value.run_once.admit(
                    "nightly",
                    actor="operator",
                    expected_revision_id="other-revision",
                    expected_revision_version=1,
                    expected_revision_digest="other-digest",
                )
            self.assertEqual("configuration_stale", revision.exception.code)
            # A malformed or partial fence is refused rather than weakened.
            with self.assertRaises(DiscoveryError) as malformed:
                value.run_once.admit(
                    "nightly", actor="operator", expected_definition_fingerprint="short"
                )
            self.assertEqual("malformed_selection", malformed.exception.code)
            self.assertEqual([], value.source.mutations)


class HistoricalModeTests(_RunOnceFixture):
    """Recorded pre-amendment work stops safely and stays readable."""

    def test_removed_mode_row_stays_readable_and_never_executes(self) -> None:
        from mediaflow.domain.automation import AutomationDefinitionOccurrence

        occurrence = AutomationDefinitionOccurrence(
            "occurrence-legacy",
            "nightly",
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 1, tzinfo=UTC),
            "job-legacy",
            "a" * 64,
            1,
            "revision-legacy",
            1,
            "b" * 64,
            AutomationTaskRunMode.RECORDED_SCAN_ONLY,
            "library",
            None,
            10,
            "emitted",
            "scheduled",
            "no operator action is required",
            "task-legacy",
            None,
        )
        # The recorded value is preserved exactly as historical data.
        self.assertEqual("scan-only", occurrence.document()["runMode"])
        self.assertFalse(occurrence.run_mode.is_runnable)

    def test_unsupported_mode_definition_records_an_unsupported_outcome(self) -> None:
        from mediaflow.application.automation import IntervalScheduler
        from mediaflow.domain.automation import (
            AutomationDefinitionDueState,
            SchedulerConfigurationSnapshot,
        )

        class _Repository:
            def __init__(self) -> None:
                self.failures: list[dict] = []

            def get_automation_definition_due_state(self, definition_id):
                return AutomationDefinitionDueState(
                    definition_id,
                    datetime(2026, 1, 1, 11, 0, tzinfo=UTC),
                    datetime(2026, 1, 1, 11, 0, tzinfo=UTC),
                )

            def record_automation_definition_failure(self, definition_id, **kwargs):
                self.failures.append({"definitionId": definition_id, **kwargs})
                return None

            def list_automation_definition_due_states(self, **kwargs):
                return ()

        repository = _Repository()
        snapshot = SchedulerConfigurationSnapshot(
            "snapshot-1",
            "a" * 64,
            (),
            100,
            (
                # A recorded pre-amendment definition.  It is built as a raw
                # record because the domain now refuses to construct a
                # removed-mode definition at all.
                SimpleNamespace(
                    definition_id="legacy",
                    name="Legacy",
                    enabled=True,
                    resource_library_id="library",
                    source_scope=None,
                    mode="scan-only",
                    interval_seconds=3600.0,
                    cron=None,
                    timezone=None,
                    item_limit=10,
                ),
            ),
            configuration_snapshot_version=1,
            resource_library_ids=("library",),
            enabled_resource_library_ids=("library",),
        )
        scheduler = IntervalScheduler(
            repository,
            (),
            maximum_active_jobs=100,
            automation_task_definitions=snapshot.automation_task_definitions,
            configuration_snapshot_id=snapshot.snapshot_id,
            configuration_snapshot_digest=snapshot.snapshot_digest,
            configuration_snapshot_version=snapshot.configuration_snapshot_version,
        )
        queued = scheduler.tick(datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
        self.assertEqual((), queued)
        self.assertTrue(
            any(item.get("outcome") == "unsupported" for item in repository.failures),
            repository.failures,
        )


class RunOnceApiTests(_RunOnceFixture):
    """AC-T4/T6: bounded API surface, principal isolation and history."""

    def test_viewer_cannot_start_run_once(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            status, _ = self.request(
                value,
                "/api/v1/operations/automation/task-definitions/nightly/run-once",
                "POST",
                {},
                token="viewer-token",
            )
            self.assertEqual(403, status)
            self.assertEqual((), value.discovery.list(actor="operator"))

    def test_definition_history_lists_the_manual_run_once(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            value.run_once.admit("nightly", actor="operator")
            self.drive(value)
            status, document = self.request(
                value,
                "/api/v1/operations/automation/task-definitions/nightly/occurrences",
            )
            self.assertEqual(200, status)
            manual = [item for item in document["items"] if item.get("trigger") == "manual"]
            self.assertEqual(1, len(manual))
            self.assertEqual("nightly", manual[0]["definitionId"])
            self.assertIsNone(manual[0]["occurrenceId"])
            self.assertIsNone(manual[0]["jobId"])

    def test_run_once_list_is_principal_scoped(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            value.run_once.admit("nightly", actor="operator")
            status, document = self.request(value, "/api/v1/operations/automation/run-once")
            self.assertEqual(200, status)
            self.assertEqual(1, document["total"])
            self.assertEqual("nightly", document["items"][0]["definitionId"])

    def test_unicode_principal_isolation_across_reload_and_reconcile(self) -> None:
        """AC-T4: a Unicode principal reconciles only its own request identity.

        The request identity is principal-scoped, so a Unicode principal's
        unknown admission is readable by that exact principal and invisible to
        another; a reconnect never inherits another principal's outcome.
        """

        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            unicode_actor = "操作员-張三-🎬"
            request_id = "44444444-4444-4444-8444-444444444444"
            admitted = value.run_once.admit(
                "nightly", actor=unicode_actor, admission_request_id=request_id
            )
            # The same principal reads back its own proved original.
            reconciled = value.discovery.find_by_request_id(
                actor=unicode_actor, admission_request_id=request_id
            )
            self.assertIsNotNone(reconciled)
            self.assertEqual(admitted.discovery_id, reconciled.discovery_id)
            # Another principal never reconciles to it.
            self.assertIsNone(
                value.discovery.find_by_request_id(
                    actor="operator", admission_request_id=request_id
                )
            )
            # The durable record keeps the Unicode actor unchanged.
            reread = value.run_once.get(admitted.discovery_id)
            self.assertEqual(unicode_actor, reread.actor)
            # The listing is principal-scoped: the other principal sees none.
            self.assertEqual((), value.discovery.list(actor="operator"))
            self.assertEqual(1, len(value.discovery.list(actor=unicode_actor)))
            self.assertEqual([], value.source.mutations)

    def test_concurrent_duplicate_admission_converges_on_one_run(self) -> None:
        """AC-T4: concurrent identical requests converge on one durable run."""

        from concurrent.futures import ThreadPoolExecutor

        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            request_id = "55555555-5555-4555-8555-555555555555"

            def admit_once():
                return value.run_once.admit(
                    "nightly", actor="operator", admission_request_id=request_id
                )

            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda _index: admit_once(), range(4)))
            identities = {item.discovery_id for item in results}
            self.assertEqual(1, len(identities))
            self.assertEqual(1, len(value.discovery.list(actor="operator")))
            self.assertEqual([], value.source.mutations)
            # A changed binding with the *same* request identity refuses rather
            # than silently re-pinning the proved original.
            with self.assertRaises(DiscoveryError) as caught:
                value.run_once.admit(
                    "nightly",
                    actor="operator",
                    admission_request_id=request_id,
                    expected_definition_fingerprint="0" * 64,
                )
            self.assertEqual("definition_stale", caught.exception.code)

    def test_concurrent_equivalent_new_ids_both_stay_reconcilable(self) -> None:
        """B43.2-R4-2: an accepted concurrent alias is never a bounded 404.

        Two equivalent Run-once requests with distinct IDs synchronize only
        between the real open-work read and the durable create, so one wins the
        identity race.  The loser converged on the winner's record, so its own
        request ID must remain a verifiable association: the winner path must
        bind it, not return and leave the lookup reporting "no work exists".
        """

        import threading
        from concurrent.futures import ThreadPoolExecutor

        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            barrier = threading.Barrier(2)
            original = value.discovery._reconcile_definition_admission
            call_lock = threading.Lock()
            calls = 0

            def synchronized_find(*args, **kwargs):
                nonlocal calls
                result = original(*args, **kwargs)
                with call_lock:
                    calls += 1
                    call = calls
                if call <= 2:
                    barrier.wait(timeout=10)
                return result

            value.discovery._reconcile_definition_admission = synchronized_find
            request_ids = [
                "10101010-1010-4010-8010-101010101010",
                "20202020-2020-4020-8020-202020202020",
            ]

            def admit(request_id):
                return value.run_once.admit(
                    "nightly", actor="operator", admission_request_id=request_id
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                admissions = list(pool.map(admit, request_ids))
            identities = {item.discovery_id for item in admissions}
            self.assertEqual(1, len(identities))
            for request_id in request_ids:
                readback = value.discovery.find_by_request_id(
                    actor="operator", admission_request_id=request_id
                )
                self.assertIsNotNone(readback, request_id)
                self.assertEqual(next(iter(identities)), readback.discovery_id)
            self.assertEqual([], value.source.mutations)

    def test_discovery_alias_refuses_an_identity_claimed_by_other_work(
        self,
    ) -> None:
        """B43.2-R5-1: the discovery alias writer validates the identity too.

        A request identity already durably claimed by another admission (a
        direct analysis row) must be refused by a delayed alias writer, so the
        identity never names two durable facts.  The refused writer reports an
        explicit admission-request conflict, never a second acceptance.
        """

        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            request_id = "30303030-3030-4030-8030-303030303030"
            # The identity is claimed by an analysis through its own column.
            value.analyses.admit_definition(
                "nightly", actor="operator", admission_request_id=request_id
            )
            discovery = value.run_once.admit("nightly", actor="operator")
            self.assertIsNone(discovery.admission_request_id)
            with self.assertRaises(DiscoveryError):
                value.discovery._bind_request(request_id, discovery)
            bindings = value.repository._connection.execute(
                "SELECT target_id FROM admission_request_bindings "
                "WHERE actor=? AND admission_request_id=?",
                ("operator", request_id),
            ).fetchall()
            self.assertEqual([], bindings)
            self.assertEqual([], value.source.mutations)

    def test_discovery_admission_refuses_an_identity_claimed_by_other_work(
        self,
    ) -> None:
        """B43.2-R5-1: the discovery direct-create writer validates too.

        A Run-once admission whose client request identity already names a
        durable analysis must refuse instead of recording a second, cross-family
        admission for the same identity.
        """

        self.media("Movies/One.2001.mkv")
        with self.journey(source_scope="Movies") as value:
            request_id = "40404040-4040-4040-8040-404040404040"
            value.analyses.admit_definition(
                "nightly", actor="operator", admission_request_id=request_id
            )
            with self.assertRaises(DiscoveryError) as caught:
                value.run_once.admit("nightly", actor="operator", admission_request_id=request_id)
            self.assertIn("admission request identity", str(caught.exception))
            rows = value.repository._connection.execute(
                "SELECT discovery_id FROM media_discoveries "
                "WHERE actor=? AND admission_request_id=?",
                ("operator", request_id),
            ).fetchall()
            self.assertEqual([], rows)
            self.assertEqual([], value.source.mutations)

    def test_malformed_run_once_body_is_rejected(self) -> None:
        with self.journey(source_scope="Movies") as value:
            status, _ = self.request(
                value,
                "/api/v1/operations/automation/task-definitions/nightly/run-once",
                "POST",
                {"paths": ["Movies"]},
            )
            self.assertEqual(400, status)


if __name__ == "__main__":
    unittest.main()
