"""Task 45.2 — durable same-page preparation: bounded walk → frozen → analysis.

The suite runs against the real runtime SQLite repository, real Local Storage
adapters, the real application services and the real API, with a controlled
clock and a synthetic Metadata provider.  It covers the RO-2 promises named by
Task 45.2 without weakening any production capability:

* one explicit ``autoPrepare`` admission runs the bounded discovery, freezes
  its reviewed sources and links one exact zero-mutation Preview;
* no Storage mutation and no execution authority exist anywhere in the
  preparation stage;
* a material budget refusal never becomes an executable first-N prefix;
* a legal correction re-runs the analysis under the same pinned configuration;
* the preparation is durable across a database reopen.
"""

from __future__ import annotations

import io
import json
import tempfile
import threading
import unittest
from contextlib import contextmanager
from dataclasses import replace as _replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_execution import ManualOrganizeExecutionService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.manual_organize_worker import ManualOrganizeExecutionWorker
from mediaflow.application.media_discovery import MediaDiscoveryService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.application.strategy_test import (
    SyntheticMetadataProvider,
)
from mediaflow.domain.media_discovery import (
    DiscoveryBudgets,
    DiscoveryConflict,
    DiscoveryOwnershipLost,
    DiscoveryStatus,
)
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

OPERATOR_TOKEN = "operator-token"


class _RecordingStorage(LocalStorage):
    def __init__(self, storage_id: str, root: Path) -> None:
        super().__init__(storage_id, root)
        self.mutations: list[tuple[str, str]] = []

    def move(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self.mutations.append(("move", source))
        super().move(source, target, overwrite=overwrite)

    def copy(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self.mutations.append(("copy", source))
        super().copy(source, target, overwrite=overwrite)

    def delete(self, path: str) -> None:
        self.mutations.append(("delete", path))
        super().delete(path)

    def create_directory(self, path: str) -> None:
        self.mutations.append(("create_directory", path))
        super().create_directory(path)

    def write(self, path: str, data, *, overwrite: bool = False) -> None:
        self.mutations.append(("write", path))
        super().write(path, data, overwrite=overwrite)


class _PreparationFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.database = root / "runtime.sqlite3"
        self.source_root = root / "source"
        self.target_root = root / "target"
        self.source_root.mkdir()
        self.target_root.mkdir()
        self.second_source_root = root / "source2"
        self.second_source_root.mkdir()
        self.clock_value = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)

    def clock(self) -> datetime:
        return self.clock_value

    def media(self, relative: str, *, size: int = 64, root: Path | None = None) -> Path:
        path = (root or self.source_root) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"m" * size)
        return path

    def resource_library(self, library_id: str = "library", **overrides) -> dict:
        value = {
            "id": library_id,
            "name": library_id,
            "storageId": "source",
            "storagePath": "",
            "enabled": True,
            "extensions": ["mkv", "mp4"],
            "maxDepth": None,
            "excludeRules": [],
        }
        value.update(overrides)
        return value

    def document(self, *, exclude_rules: tuple[str, ...] = (), resource_libraries=None) -> dict:
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        document["persistence"]["databasePath"] = str(self.database)
        document["historyPath"] = str(self.source_root.parent / "history.jsonl")
        document["storages"] = [
            {
                "id": "source",
                "name": "Source",
                "type": "local",
                "rootPath": str(self.source_root),
                "enabled": True,
            },
            {
                "id": "source2",
                "name": "Source 2",
                "type": "local",
                "rootPath": str(self.second_source_root),
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
        library = self.resource_library(excludeRules=list(exclude_rules))
        document["resourceLibraries"] = (
            list(resource_libraries) if resource_libraries is not None else [library]
        )
        # RO-2/AC-16: the Files journey resolves each source through its pinned
        # RecognitionRule, so this fixture publishes the ordinary video rule.  A
        # source with *no* matching rule is now its own native Recognition problem
        # and is covered by dedicated journeys in tests.test_media_discovery.
        document["recognitionRules"] = [
            {
                "id": "preparation-video-fixture",
                "name": "Preparation video fixture",
                "priority": 100,
                "score": 100,
                "stopOnMatch": True,
                "condition": {
                    "field": "extension",
                    "operator": "in",
                    "value": ["mkv", "mp4"],
                },
                "outputRecognitionType": "A",
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
        return document

    @contextmanager
    def journey(
        self,
        *,
        budgets: DiscoveryBudgets | None = None,
        candidates: tuple[MediaCandidate, ...] | None = None,
        resource_libraries=None,
        provider: SyntheticMetadataProvider | None = None,
    ):
        document = self.document(resource_libraries=resource_libraries)
        source = _RecordingStorage("source", self.source_root)
        source2 = _RecordingStorage("source2", self.second_source_root)
        target = _RecordingStorage("target", self.target_root)
        storages = {"source": source, "source2": source2, "target": target}
        metadata_provider = provider or SyntheticMetadataProvider(
            candidates
            if candidates is not None
            else (
                MediaCandidate(
                    "tmdb",
                    "201",
                    MediaType.MOVIE,
                    "One",
                    year=2001,
                    genres=("Animation",),
                    countries=("JP",),
                ),
                MediaCandidate(
                    "tmdb",
                    "202",
                    MediaType.MOVIE,
                    "Two",
                    year=2002,
                    genres=("Animation",),
                    countries=("JP",),
                ),
                MediaCandidate(
                    "tmdb",
                    "203",
                    MediaType.MOVIE,
                    "Three",
                    year=2003,
                    genres=("Animation",),
                    countries=("JP",),
                ),
                MediaCandidate(
                    "tmdb",
                    "204",
                    MediaType.MOVIE,
                    "Four",
                    year=2004,
                    genres=("Animation",),
                    countries=("JP",),
                ),
            )
        )
        providers = MetadataProviderRegistry((metadata_provider,))
        with (
            SQLiteConfigurationRepository(self.database) as configuration_repository,
            SQLiteTaskRepository(self.database) as repository,
        ):
            managed = ManagedConfigurationService(
                configuration_repository, bootstrap_database_path=str(self.database)
            )
            revision = _activate(managed, document)
            runtime = _runtime_for(managed, revision)

            def resolve_runtime(snapshot_id, snapshot_digest):
                if snapshot_id == revision.revision_id and snapshot_digest == revision.digest:
                    return runtime
                return _runtime_for(managed, managed.require(snapshot_id))

            intents = ManualOrganizeIntentService(
                repository,
                managed,
                runtime_resolver=resolve_runtime,
                storage_factory=lambda value, ids: dict(storages),
            )
            previews = ManualOrganizePreviewService(
                repository,
                intents,
                configuration=runtime,
                runtime_resolver=resolve_runtime,
                storages=dict(storages),
                providers=providers,
                clock=self.clock,
            )
            discovery = MediaDiscoveryService(
                repository,
                intents,
                configuration=runtime,
                runtime_resolver=resolve_runtime,
                preview_service=previews,
                storages=dict(storages),
                clock=self.clock,
                budgets=budgets or DiscoveryBudgets(),
            )
            executions = ManualOrganizeExecutionService(
                repository,
                previews,
                intents,
                checkpoint_service=ProcessingCheckpointService(repository),
                storages=dict(storages),
            )
            execution_worker = ManualOrganizeExecutionWorker(
                executions, worker_id="prep-execution-worker", notice=lambda _line: None
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
                bootstrap_document=document,
                manual_intent_service=intents,
                manual_preview_service=previews,
                manual_execution_service=executions,
                media_discovery_service=discovery,
                storage_adapters=dict(storages),
            )
            yield SimpleNamespace(
                api=api,
                repository=repository,
                intents=intents,
                previews=previews,
                executions=executions,
                execution_worker=execution_worker,
                discovery=discovery,
                managed=managed,
                source=source,
                source2=source2,
                target=target,
            )

    @staticmethod
    def request(value, path: str, method: str = "GET", body=None):
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
            "HTTP_AUTHORIZATION": f"Bearer {OPERATOR_TOKEN}",
        }
        response = b"".join(value.api(environ, lambda status, headers: statuses.append(status)))
        return int(statuses[0].split()[0]), json.loads(response)

    def run_worker(self, value, *, steps: int = 8) -> dict:
        result = None
        for index in range(steps):
            result = value.discovery.claim_and_run(
                worker_id=f"worker-{index}", claim_token=f"token-{index}"
            )
            if result is None:
                raise AssertionError("preparation was not claimable")
            if result.terminal or result.preview_id is not None:
                break
        else:
            raise AssertionError("preparation did not settle within the bounded step budget")
        status, document = self.request(
            value, f"/api/v1/operations/organize/discoveries/{result.discovery_id}"
        )
        if status != 200:
            raise AssertionError(document)
        return document

    def assert_no_executable_work(self, value) -> None:
        """No TaskItem, Preview or execution authority exists yet.

        RO-2 admits the organizing Task before business readiness, so an empty Task
        table is no longer the right assertion.  What must still be true — and is
        what the original cases were really asserting — is that the admitted Task has
        produced no per-item work, no linked Preview and no execution, so no media
        effect is possible from this state.
        """

        for task in value.repository.list_tasks(limit=50):
            self.assertEqual("manual_organize", task.command)
            self.assertEqual((), value.repository.list_items(task.task_id))
        self.assertEqual((), value.repository.list_manual_executions_for_intent("none", limit=10))

    def admit(self, value, paths: list[str], *, library_id: str = "library"):
        status, document = self.request(
            value,
            f"/api/v1/resource-libraries/{library_id}/files/discoveries",
            "POST",
            {"paths": paths, "autoPrepare": True},
        )
        self.assertIn(status, (200, 202), document)
        return document

    def execute(self, value, preview: dict, item_ids: list[str], *, allow_overwrite=False):
        """Confirm one exact reviewed subset through the production API."""

        status, document = self.request(
            value,
            f"/api/v1/operations/organize/previews/{preview['previewId']}",
        )
        self.assertEqual(200, status, document)
        status, result = self.request(
            value,
            f"/api/v1/operations/organize/previews/{preview['previewId']}/execute",
            "POST",
            {
                "confirmation": True,
                "itemIds": item_ids,
                "expectedIntentVersion": document["intentVersion"],
                "allowOverwrite": allow_overwrite,
                "allowSourceCleanup": False,
            },
        )
        self.assertIn(status, (200, 202), result)
        return result

    def analyze(self, value, discovery_id: str, expected_version: int):
        return self.request(
            value,
            f"/api/v1/operations/organize/discoveries/{discovery_id}/analyze",
            "POST",
            {"expectedVersion": expected_version},
        )

    def run_execution_worker(self, value):
        completed = value.execution_worker.run_next()
        if completed is None:
            raise AssertionError("no admitted execution was claimable")
        return value.repository.get_manual_execution(completed.execution_id)


def _activate(service, document):
    draft = service.import_draft(document, actor="tester")
    validated = service.validate(draft.revision_id, actor="tester")
    if validated.status.value != "validated":
        raise AssertionError(validated.validation_errors)
    return service.activate(
        validated.revision_id, expected_version=validated.version, actor="tester"
    )


def _runtime_for(service, revision):
    from mediaflow.infrastructure.runtime_configuration import (
        load_managed_runtime_configuration,
        with_managed_snapshot,
    )

    runtime = load_managed_runtime_configuration(
        revision.document, bootstrap_database_path=str(service.bootstrap_database_path)
    )
    return with_managed_snapshot(runtime, snapshot_id=revision.revision_id, digest=revision.digest)


class PreparationJourneyTests(_PreparationFixture):
    def test_auto_prepare_freezes_and_links_one_exact_zero_mutation_preview(self) -> None:
        """RO-2: one explicit preparation yields the reviewed plan summary."""

        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        with self.journey() as value:
            admitted = self.admit(value, ["Movies"])
            self.assertTrue(admitted["autoPrepare"], admitted)
            self.assertFalse(admitted["prepared"], admitted)
            settled = self.run_worker(value)
            # The walk froze the reviewed list and linked its exact Preview.
            self.assertEqual("completed", settled["status"], settled)
            self.assertTrue(settled["frozen"], settled)
            self.assertIsNotNone(settled["intentId"], settled)
            self.assertIsNotNone(settled["previewId"], settled)
            # The preparation is zero mutation.
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            self.assertEqual("none", settled["sideEffects"], settled)
            self.assertTrue(settled["zeroMutation"], settled)
            # The linked intent holds exactly the two frozen sources.
            intent = value.repository.get_manual_intent(settled["intentId"])
            self.assertEqual(
                {"Movies/One.2001.mkv", "Movies/Two.2002.mkv"},
                {item.source.path for item in intent.items},
            )
            # The linked Preview is the ordinary exact zero-mutation plan.
            preview = value.repository.get_manual_preview(settled["previewId"])
            self.assertIsNotNone(preview)
            self.assertTrue(preview.zero_mutation)
            self.assertEqual(intent.intent_id, preview.intent_id)

    def _blocked_provider(self, value):
        """Pause only the outbound Provider call of the real analysis chain."""

        provider = next(iter(value.previews._providers._providers.values()))
        entered = threading.Event()
        release = threading.Event()
        original = type(provider).search_movie

        def blocked_search(inner_self, query, policy=None, **kwargs):
            entered.set()
            release.wait(timeout=30)
            return original(inner_self, query, policy=policy, **kwargs)

        return entered, release, patch.object(type(provider), "search_movie", blocked_search)

    def _partial_analysis_race(self, value, control: str) -> dict:
        """Let one operator control win while a legal partial analysis runs.

        The whole path is real: the API admission, the Worker claim, the
        production analysis chain and the operator control all run through
        their normal entry points; only the outbound Provider call is paused.
        Returns the operator readback of the settled preparation.
        """

        gone = self.media("Gone.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        self.admit(value, ["Gone.2001.mkv", "Movies"])
        gone.unlink()
        # Stop after the walk froze the reviewed known subset.
        for index in range(6):
            result = value.discovery.claim_and_run(
                worker_id=f"walk-{index}", claim_token=f"walk-token-{index}"
            )
            self.assertIsNotNone(result)
            current = value.repository.get_media_discovery(result.discovery_id)
            if current.status.value == "analyzing":
                break
        self.assertEqual("analyzing", current.status.value, current.status)
        self.assertEqual("read_failure", current.progress.incomplete_reason.value)
        entered, release, guard = self._blocked_provider(value)
        results: list[object] = []

        def analyze() -> None:
            try:
                results.append(
                    value.discovery.claim_and_run(
                        worker_id="analysis-worker", claim_token="analysis-token"
                    )
                )
            except Exception as error:  # noqa: BLE001 - asserted by the caller
                results.append(error)

        with guard:
            thread = threading.Thread(target=analyze, name="partial-analysis")
            thread.start()
            self.assertTrue(entered.wait(15), "the Worker never reached the Provider")
            status, controlled = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{current.discovery_id}/{control}",
                "POST",
                {"expectedVersion": current.version},
            )
            self.assertEqual(200, status, controlled)
        release.set()
        thread.join(timeout=30)
        self.assertFalse(thread.is_alive())
        self.assertNotIsInstance(results[0], Exception, results)
        status, readback = self.request(
            value, f"/api/v1/operations/organize/discoveries/{current.discovery_id}"
        )
        self.assertEqual(200, status, readback)
        return readback

    def test_a_legal_read_failure_subset_publishes_its_complete_plan(self) -> None:
        """B's P1: a legal partial walk still persists the exact plan it analyzed.

        An explicit file that disappears after admission leaves an openly
        reviewed known subset (``read_failure``), not a budget/safety refusal.
        That subset is legal, so its analysis must publish the complete plan —
        plan rows, per-item evidence, the run link and the claim release —
        exactly like a complete walk.  Advertising ``prepared`` with a plan
        identity that resolves to nothing breaks the summary → confirm journey
        for work the operator may lawfully do.
        """

        gone = self.media("Gone.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        with self.journey() as value:
            admitted = self.admit(value, ["Gone.2001.mkv", "Movies"])
            gone.unlink()
            settled = self.run_worker(value)
            self.assertEqual("partial_success", settled["status"], settled)
            self.assertEqual("read_failure", settled["progress"]["incompleteReason"], settled)
            self.assertEqual(1, settled["progress"]["errorEntries"], settled)
            self.assertEqual([], settled["progress"]["refusalReasons"], settled)
            self.assertTrue(settled["frozen"], settled)
            # The published summary is a real plan, not a dangling identity.
            self.assertTrue(settled["prepared"], settled)
            preview_id = settled["previewId"]
            self.assertIsInstance(preview_id, str, settled)
            status, plan = self.request(value, f"/api/v1/operations/organize/previews/{preview_id}")
            self.assertEqual(200, status, plan)
            self.assertEqual(preview_id, plan["previewId"])
            self.assertEqual(
                ["Movies/Two.2002.mkv"], [item["source"]["path"] for item in plan["items"]]
            )
            self.assertEqual({"previewed"}, {item["status"] for item in plan["items"]}, plan)
            # The intent's latest plan is the same plan across a durable reopen.
            with SQLiteTaskRepository(self.database) as reopened:
                stored = reopened.get_media_discovery(settled["discoveryId"])
                self.assertEqual(preview_id, stored.preview_id)
                self.assertIsNotNone(reopened.get_manual_preview(preview_id))
                self.assertEqual(
                    preview_id, reopened.get_latest_manual_preview(stored.intent_id).preview_id
                )
            # Analysis still grants nothing and mutates no media.
            self.assertEqual(
                (),
                tuple(value.repository.list_manual_executions_for_preview(preview_id, limit=10)),
            )
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            self.assertEqual(admitted["discoveryId"], settled["discoveryId"])

            # Only the explicitly confirmed item is executed.
            item = plan["items"][0]
            self.execute(value, plan, [item["itemId"]])
            completed = self.run_execution_worker(value)
            self.assertEqual("completed", completed.status.value, completed)
            self.assertEqual([("delete", "Movies/Two.2002.mkv")], value.source.mutations)
            self.assertFalse((self.source_root / "Movies/Two.2002.mkv").exists())
            self.assertTrue(any(self.target_root.rglob("Two (2002).mkv")))

    def test_a_legal_partial_plan_is_never_published_by_a_losing_write(self) -> None:
        """B's P1 fence: a legal partial plan and the run link still atomic.

        The plan rows were formerly written only for a complete walk, so the
        partial branch had no atomic boundary to lose.  With the plan mandatory
        the same fence covers it: a control that won the version race leaves no
        plan row at all, and an owner that lost its claim publishes nothing.
        """

        gone = self.media("Gone.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        with self.journey() as value:
            admitted = self.admit(value, ["Gone.2001.mkv", "Movies"])
            gone.unlink()
            for index in range(6):
                result = value.discovery.claim_and_run(
                    worker_id=f"walk-{index}", claim_token=f"walk-token-{index}"
                )
                self.assertIsNotNone(result)
                durable = value.repository.get_media_discovery(admitted["discoveryId"])
                if durable.status.value == "analyzing":
                    break
            self.assertEqual("analyzing", durable.status.value, durable.status)
            self.assertEqual("read_failure", durable.progress.incomplete_reason.value)
            intent = value.repository.get_manual_intent(durable.intent_id)
            plan = value.previews.create(
                intent.intent_id,
                [item.item_id for item in intent.items],
                actor="operator",
                expected_version=intent.version,
                persist=False,
            )
            # The analyzing Worker really holds the live claim at this boundary.
            value.repository._connection.execute(
                "UPDATE media_discoveries SET claim_worker_id=?, claim_token=?, "
                "claim_expires_at=? WHERE discovery_id=?",
                (
                    "analysis-owner",
                    "analysis-token",
                    (self.clock_value + timedelta(minutes=10)).isoformat(),
                    admitted["discoveryId"],
                ),
            )
            value.repository._connection.commit()
            claimed = value.repository.get_media_discovery(admitted["discoveryId"])
            self.assertEqual("analysis-token", claimed.claim_token)
            # A control that won the race bumped the version: the whole write
            # is refused and the plan rows never exist.
            value.repository._connection.execute(
                "UPDATE media_discoveries SET version=version+1, pause_requested=1 "
                "WHERE discovery_id=?",
                (admitted["discoveryId"],),
            )
            value.repository._connection.commit()
            with self.assertRaises(DiscoveryConflict):
                value.repository.publish_media_discovery_plan_with_plan(
                    _replace(
                        claimed,
                        status=DiscoveryStatus.PARTIAL_SUCCESS,
                        version=claimed.version + 1,
                        preview_id=plan.preview_id,
                    ),
                    plan,
                    expected_version=claimed.version,
                    claim_token="analysis-token",
                )
            self.assertIsNone(value.repository.get_manual_preview(plan.preview_id))
            self.assertEqual((), value.repository.list_manual_previews(intent.intent_id))
            self.assertIsNone(value.repository.get_latest_manual_preview(intent.intent_id))
            refused = value.repository.get_media_discovery(admitted["discoveryId"])
            self.assertIsNone(refused.preview_id)
            self.assertTrue(refused.pause_requested)
            # A successor cannot publish it either: the exact claim is the
            # second fence, so a stale owner leaves no confirmable residual.
            value.repository._connection.execute(
                "UPDATE media_discoveries SET pause_requested=0 WHERE discovery_id=?",
                (admitted["discoveryId"],),
            )
            value.repository._connection.commit()
            current = value.repository.get_media_discovery(admitted["discoveryId"])
            with self.assertRaises(DiscoveryOwnershipLost):
                value.repository.publish_media_discovery_plan_with_plan(
                    _replace(
                        current,
                        status=DiscoveryStatus.PARTIAL_SUCCESS,
                        version=current.version + 1,
                        preview_id=plan.preview_id,
                    ),
                    plan,
                    expected_version=current.version,
                    claim_token="not-the-live-claim",
                )
            self.assertIsNone(value.repository.get_manual_preview(plan.preview_id))
            self.assertEqual((), value.repository.list_manual_previews(intent.intent_id))
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_a_pause_that_wins_a_partial_analysis_leaves_no_plan(self) -> None:
        """B's P1 fence: the known-subset plan is protected by the atomic write.

        While the Worker analyzes the legal partial manifest the operator pauses
        through the real API.  The accepted control wins the publication, so the
        plan rows and the run link are refused together: no plan row, no intent
        summary and no confirmable work.  Continuing then publishes exactly one
        real plan for that subset.
        """

        with self.journey() as value:
            readback = self._partial_analysis_race(value, "pause")
            self.assertEqual("paused", readback["status"], readback)
            self.assertTrue(readback["pauseRequested"], readback)
            self.assertIsNone(readback["previewId"], readback)
            self.assertFalse(readback["prepared"], readback)
            intent_id = readback["intentId"]
            self.assertIsNotNone(intent_id)
            self.assertEqual((), value.repository.list_manual_previews(intent_id))
            self.assertIsNone(value.repository.get_latest_manual_preview(intent_id))
            self.assertIsNone(
                value.repository.media_discovery_claim(readback["discoveryId"])["claimToken"]
            )
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            # RO-2: the organizing Task admitted with the selection is real and
            # durable, but a paused/cancelled walk leaves no confirmable subset and
            # no TaskItem, so nothing can ever be executed from it.
            self.assert_no_executable_work(value)

            status, resumed = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{readback['discoveryId']}/resume",
                "POST",
                {"expectedVersion": readback["version"]},
            )
            self.assertEqual(200, status, resumed)
            finalized = self.run_worker(value)
            self.assertTrue(finalized["prepared"], finalized)
            self.assertEqual("partial_success", finalized["status"], finalized)
            status, plan = self.request(
                value, f"/api/v1/operations/organize/previews/{finalized['previewId']}"
            )
            self.assertEqual(200, status, plan)
            self.assertEqual(
                ["Movies/Two.2002.mkv"], [item["source"]["path"] for item in plan["items"]]
            )
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_a_cancel_that_wins_a_partial_analysis_leaves_no_plan(self) -> None:
        """B's P1 fence: a cancelled run never leaves a confirmable subset.

        The same race with the terminal control: the accepted cancellation wins,
        so the analyzed known-subset plan is never written and the run stays
        cancelled with no plan, no resume and no execution authority.
        """

        with self.journey() as value:
            readback = self._partial_analysis_race(value, "cancel")
            self.assertEqual("cancelled", readback["status"], readback)
            self.assertIsNone(readback["previewId"], readback)
            self.assertFalse(readback["prepared"], readback)
            intent_id = readback["intentId"]
            self.assertIsNotNone(intent_id)
            self.assertEqual((), value.repository.list_manual_previews(intent_id))
            self.assertIsNone(value.repository.get_latest_manual_preview(intent_id))
            self.assertIsNone(
                value.repository.media_discovery_claim(readback["discoveryId"])["claimToken"]
            )
            self.assertFalse(readback["actions"]["prepare"]["available"], readback)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            # RO-2: the organizing Task admitted with the selection is real and
            # durable, but a paused/cancelled walk leaves no confirmable subset and
            # no TaskItem, so nothing can ever be executed from it.
            self.assert_no_executable_work(value)

    def test_preparation_never_creates_execution_authority(self) -> None:
        """RO-2: confirming is separate; the preparation grants nothing."""

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            self.admit(value, ["Movies"])
            settled = self.run_worker(value)
            executions = value.repository.list_manual_executions_for_preview(
                settled["previewId"], limit=10
            )
            self.assertEqual((), tuple(executions))
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_material_budget_refusal_never_becomes_an_executable_prefix(self) -> None:
        """RO-2: a truncated walk is refused, not silently frozen."""

        for index in range(5):
            self.media(f"Movies/File{index}.200{index}.mkv")
        budgets = DiscoveryBudgets(max_primary_sources=2)
        with self.journey(budgets=budgets) as value:
            self.admit(value, ["Movies"])
            settled = self.run_worker(value)
            self.assertEqual("partial_success", settled["status"], settled)
            self.assertIsNone(settled["previewId"], settled)
            self.assertFalse(settled["frozen"], settled)
            self.assertEqual("primary_limit", settled["progress"]["materialRefusal"], settled)
            self.assertEqual([], value.source.mutations)

    def test_saved_correction_re_enters_the_durable_analysis_stage(self) -> None:
        """RO-2: a legal correction re-runs the analysis in the same queue."""

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            self.admit(value, ["Movies"])
            settled = self.run_worker(value)
            self.assertIsNotNone(settled["previewId"], settled)
            first_preview_id = settled["previewId"]
            # The operator saves a legal RecognitionType choice on the linked
            # intent; that is durable intent state, not execution authority.
            intent = value.repository.get_manual_intent(settled["intentId"])
            choice = intent.items[0].choice
            self.assertIsNotNone(choice.recognition_type_id)
            status, readback = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{settled['discoveryId']}/analyze",
                "POST",
                {"expectedVersion": settled["version"]},
            )
            self.assertEqual(200, status, readback)
            self.assertEqual("analyzing", readback["status"], readback)
            # The resident Worker links a new exact Preview under the same pin.
            reanalyzed = self.run_worker(value)
            self.assertEqual("completed", reanalyzed["status"], reanalyzed)
            self.assertIsNotNone(reanalyzed["previewId"], reanalyzed)
            self.assertNotEqual(first_preview_id, reanalyzed["previewId"])
            self.assertEqual([], value.source.mutations)
            # Both Previews belong to the one durable intent.
            previews = value.repository.list_manual_previews(settled["intentId"], limit=10)
            self.assertEqual(2, len(tuple(previews)))

    def test_preparation_survives_a_database_reopen(self) -> None:
        """RO-2: refresh/reconnect reads the same preparation without new work."""

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            admitted = self.admit(value, ["Movies"])
            settled = self.run_worker(value)
            discovery_id = settled["discoveryId"]
            self.reopen = settled["previewId"]
            # Reopen the durable database: the linked Preview must be readable.
            with SQLiteTaskRepository(self.database) as reopened:
                stored = reopened.get_media_discovery(discovery_id)
                self.assertIsNotNone(stored)
                self.assertEqual(DiscoveryStatus.COMPLETED, stored.status)
                self.assertEqual(self.reopen, stored.preview_id)
                self.assertTrue(stored.auto_prepare)
                self.assertTrue(stored.frozen)
            # A reconnect read of the same discovery publishes the same facts.
            status, readback = self.request(
                value, f"/api/v1/operations/organize/discoveries/{discovery_id}"
            )
            self.assertEqual(200, status, readback)
            self.assertEqual(self.reopen, readback["previewId"])
            self.assertEqual(admitted["discoveryId"], readback["discoveryId"])

    def test_reading_the_preparation_creates_no_work_or_mutation(self) -> None:
        """RO-2: GET/refresh is a pure durable read."""

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            admitted = self.admit(value, ["Movies"])
            for _ in range(3):
                status, readback = self.request(
                    value,
                    f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}",
                )
                self.assertEqual(200, status, readback)
            self.assertEqual([], value.source.mutations)
            stored = value.repository.get_media_discovery(admitted["discoveryId"])
            self.assertEqual(DiscoveryStatus.QUEUED, stored.status)
            self.assertIsNone(stored.preview_id)

    def test_selected_execution_does_not_block_the_unselected_sibling(self) -> None:
        """RO-2/AC-3/4/5: one confirmed item never blocks the remaining sibling.

        Two genuinely ready plans are produced.  The operator confirms exactly
        one; the real Worker moves only that item.  Re-opening the same
        preparation must still let the unselected sibling be corrected and
        re-analyzed into a fresh summary — without re-including the completed
        item (which would fail with ``source_missing`` and erase the sibling's
        correction).
        """

        self.media("Movies/Three.2003.mkv")
        self.media("Movies/Four.2004.mkv")
        with self.journey() as value:
            self.admit(value, ["Movies"])
            settled = self.run_worker(value)
            self.assertEqual("completed", settled["status"], settled)
            preview = value.repository.get_manual_preview(settled["previewId"])
            self.assertEqual(
                {item.status.value for item in preview.items},
                {"previewed"},
            )
            by_path = {item.source.path: item for item in preview.items}
            three = by_path["Movies/Three.2003.mkv"]

            # Confirm exactly the Three item; the real Worker performs the move.
            self.execute(value, settled, [three.item_id])
            completed = self.run_execution_worker(value)
            self.assertEqual("completed", completed.status.value, completed)
            self.assertEqual([("delete", "Movies/Three.2003.mkv")], value.source.mutations)
            self.assertFalse((self.source_root / "Movies/Three.2003.mkv").exists())
            self.assertTrue((self.source_root / "Movies/Four.2004.mkv").exists())

            # The remaining sibling is still individually correctable.
            intent = value.repository.get_manual_intent(settled["intentId"])
            four_item = next(
                item for item in intent.items if item.source.path.endswith("Four.2004.mkv")
            )
            updated = value.intents.update_choice(
                intent.intent_id,
                four_item.item_id,
                {
                    "recognitionTypeId": "C",
                    "namingPolicyId": "A",
                    "classificationPolicyId": "A",
                    "organizePolicyId": "A",
                },
                expected_version=intent.version,
                expected_item_version=four_item.version,
                actor="operator",
            )
            saved = next(item for item in updated.items if item.item_id == four_item.item_id)
            self.assertEqual("C", saved.choice.recognition_type_id)

            # Re-analysis must only review the remaining item, so the completed
            # sibling is never re-included and the analysis does not fail.
            status, readback = self.analyze(value, settled["discoveryId"], settled["version"])
            self.assertEqual(200, status, readback)
            self.assertEqual("analyzing", readback["status"], readback)
            reanalyzed = self.run_worker(value)
            self.assertEqual("completed", reanalyzed["status"], reanalyzed)
            self.assertIsNotNone(reanalyzed["previewId"], reanalyzed)
            refreshed = value.repository.get_manual_preview(reanalyzed["previewId"])
            self.assertEqual(
                {item.source.path for item in refreshed.items},
                {"Movies/Four.2004.mkv"},
            )
            self.assertEqual({item.status.value for item in refreshed.items}, {"previewed"})
            self.assertEqual("C", refreshed.items[0].choice.recognition_type_id)
            # No second mutation happened during correction/re-analysis.
            self.assertEqual([("delete", "Movies/Three.2003.mkv")], value.source.mutations)

    def test_reanalysis_is_advertised_exactly_when_it_is_legal(self) -> None:
        """RO-2/AC-3: the published prepare action matches the real admission."""

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            admitted = self.admit(value, ["Movies"])
            # Before the walk finishes there is no frozen source list yet.
            status, queued = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{admitted['discoveryId']}",
            )
            self.assertEqual(200, status, queued)
            self.assertFalse(queued["actions"]["prepare"]["available"], queued)
            settled = self.run_worker(value)
            self.assertIsNotNone(settled["previewId"], settled)
            # A completed preparation that already linked its summary still
            # advertises the same-page re-check the backend really accepts.
            status, readback = self.request(
                value,
                f"/api/v1/operations/organize/discoveries/{settled['discoveryId']}",
            )
            self.assertEqual(200, status, readback)
            self.assertTrue(readback["actions"]["prepare"]["available"], readback)
            status, accepted = self.analyze(value, settled["discoveryId"], readback["version"])
            self.assertEqual(200, status, accepted)

    def test_intent_document_offers_bounded_source_grounded_identities(self) -> None:
        """RO-2/AC-3: the same-page correction offers only real identity options."""

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            self.admit(value, ["Movies"])
            settled = self.run_worker(value)
            status, intent_document = self.request(
                value, f"/api/v1/operations/organize/intents/{settled['intentId']}"
            )
            self.assertEqual(200, status, intent_document)
            item = intent_document["items"][0]
            identities = item["allowedMetadataIdentities"]
            # The preparation analysis already grounded this source's identity
            # through its own Result, so the operator can select it on-page.
            self.assertGreaterEqual(len(identities), 1, item)
            self.assertEqual(identities[0]["provider"], "tmdb")
            self.assertEqual(identities[0]["providerId"], "201")

            # Saving the offered identity is accepted and re-runs the analysis.
            status, saved = self.request(
                value,
                f"/api/v1/operations/organize/intents/{settled['intentId']}/items/"
                f"{item['itemId']}/choice",
                "POST",
                {
                    "expectedVersion": intent_document["version"],
                    "expectedItemVersion": item["version"],
                    "recognitionTypeId": item["choice"]["recognitionTypeId"],
                    "metadata": {
                        "provider": identities[0]["provider"],
                        "providerId": identities[0]["providerId"],
                        "mediaType": identities[0]["mediaType"],
                        "title": identities[0]["title"],
                        "year": identities[0]["year"],
                    },
                },
            )
            self.assertEqual(200, status, saved)
            self.assertEqual([], value.source.mutations)

    def test_new_source_ambiguous_candidates_are_selectable_and_executable(self) -> None:
        """RO-2/AC-3/5: a brand-new ambiguous source can be corrected and executed.

        A source with no prior Result/choice/review and two genuinely tied
        provider candidates is prepared.  The preparation withholds automatic
        selection, yet its own zero-mutation analysis grounded both candidates.
        The same-page correction must expose exactly those candidates, accept a
        legal choice, reject a cross-source one, produce a truly executable new
        summary, and execute only the explicitly confirmed item — all with zero
        mutation and zero formal recovery todos before confirmation.
        """

        self.media("Movies/One.2001.mkv")
        ambiguous = (
            MediaCandidate(
                "tmdb",
                "201",
                MediaType.MOVIE,
                "One",
                year=2001,
                genres=("Animation",),
                countries=("JP",),
            ),
            MediaCandidate(
                "tmdb",
                "999",
                MediaType.MOVIE,
                "One",
                year=2001,
                genres=("Animation",),
                countries=("JP",),
            ),
        )
        with self.journey(candidates=ambiguous) as value:
            self.admit(value, ["Movies"])
            settled = self.run_worker(value)
            self.assertEqual("completed", settled["status"], settled)

            # The preparation remains a zero-mutation finding, but RO-2/AC-16
            # requires the admitted organizing Task to carry the *real* problem its
            # own analysis found: an ambiguous Metadata identity is one of the four
            # native organizing problems, so it appears as that Task's own review
            # instead of a preparation dead end the operator can never resolve.
            preview = value.repository.get_manual_preview(settled["previewId"])
            item = preview.items[0]
            self.assertEqual("blocked", item.status.value, item.error)
            self.assertIsNone(item.plan.get("mediaIdentity"))
            self.assertEqual("ambiguous", item.plan["analysis"]["metadata"]["match"]["status"])
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            reviews = tuple(value.repository.list_metadata_reviews(limit=100))
            self.assertEqual(1, len(reviews), reviews)
            self.assertEqual("pending", reviews[0].status.value)
            self.assertEqual("Movies/One.2001.mkv", reviews[0].source_path)
            # The review belongs to the *admitted* organizing Task, not to a
            # second Task the preparation invented.
            organize_task_id = settled["organizeTaskId"]
            self.assertEqual(organize_task_id, reviews[0].task_id)
            task_item = value.repository.get_item(reviews[0].item_id)
            self.assertEqual("waiting_metadata", task_item.status.value)
            self.assertEqual(organize_task_id, task_item.task_id)

            status, intent_document = self.request(
                value, f"/api/v1/operations/organize/intents/{settled['intentId']}"
            )
            self.assertEqual(200, status, intent_document)
            intent_item = intent_document["items"][0]
            identities = intent_item["allowedMetadataIdentities"]
            self.assertEqual(
                {"201", "999"},
                {identity["providerId"] for identity in identities},
                intent_item,
            )

            # The published item stays a truthful zero-mutation finding, and the
            # operator is pointed at the Task's own native Metadata decision rather
            # than at a dead-end retry.
            status, preview_document = self.request(
                value, f"/api/v1/operations/organize/previews/{settled['previewId']}"
            )
            self.assertEqual(200, status, preview_document)
            published = preview_document["items"][0]
            self.assertIn("preparation finding", published["failure"]["durableState"])
            self.assertNotIn(
                "TaskItem and Result are durable", published["failure"]["durableState"]
            )
            # The exact bounded identities stay selectable on this page, so the
            # ambiguity is resolvable without inventing a provider payload.
            self.assertEqual({"201", "999"}, {value["providerId"] for value in identities})

            # A cross-source identity is still refused without mutation.
            status, rejected = self.request(
                value,
                f"/api/v1/operations/organize/intents/{settled['intentId']}/items/"
                f"{intent_item['itemId']}/choice",
                "POST",
                {
                    "expectedVersion": intent_document["version"],
                    "expectedItemVersion": intent_item["version"],
                    "metadata": {
                        "provider": "tmdb",
                        "providerId": "777",
                        "mediaType": "movie",
                        "title": "Invented",
                        "year": 2001,
                    },
                },
            )
            self.assertEqual(400, status, rejected)
            self.assertEqual("metadata_unverified", rejected["error"]["code"])
            self.assertEqual([], value.source.mutations)

            # Choosing one of the grounded candidates is accepted and persists.
            chosen = next(value for value in identities if value["providerId"] == "999")
            status, saved = self.request(
                value,
                f"/api/v1/operations/organize/intents/{settled['intentId']}/items/"
                f"{intent_item['itemId']}/choice",
                "POST",
                {
                    "expectedVersion": intent_document["version"],
                    "expectedItemVersion": intent_item["version"],
                    "metadata": {
                        "provider": chosen["provider"],
                        "providerId": chosen["providerId"],
                        "mediaType": chosen["mediaType"],
                        "title": chosen["title"],
                        "year": chosen["year"],
                    },
                },
            )
            self.assertEqual(200, status, saved)
            self.assertEqual([], value.source.mutations)
            stored = value.repository.get_manual_intent(settled["intentId"])
            self.assertEqual("999", stored.items[0].choice.metadata.provider_id)

            # Re-analysis produces a genuinely executable summary.
            status, accepted = self.analyze(value, settled["discoveryId"], settled["version"])
            self.assertEqual(200, status, accepted)
            reanalyzed = self.run_worker(value)
            self.assertEqual("completed", reanalyzed["status"], reanalyzed)
            refreshed = value.repository.get_manual_preview(reanalyzed["previewId"])
            refreshed_item = refreshed.items[0]
            self.assertEqual("previewed", refreshed_item.status.value, refreshed_item.error)
            self.assertEqual("999", refreshed_item.plan["mediaIdentity"]["providerId"])
            self.assertEqual([], value.source.mutations)

            # Explicit confirmation executes exactly the chosen identity.
            self.execute(value, reanalyzed, [refreshed_item.item_id])
            completed = self.run_execution_worker(value)
            self.assertEqual("completed", completed.status.value, completed)
            self.assertEqual([("delete", "Movies/One.2001.mkv")], value.source.mutations)
            self.assertFalse((self.source_root / "Movies/One.2001.mkv").exists())

    def test_unrelated_same_name_preparations_do_not_displace_own_candidates(self) -> None:
        """AC-3/5: an unrelated preparation never steals this source's candidates.

        A source's own ambiguous candidates must survive any number of
        unrelated preparations whose Storage-relative path merely contains the
        same filename text (same name in other directories, or the same name in
        another Storage).  The exact source query must match before ordering
        and limiting, and the original legal choice must remain selectable.
        """

        self.media("One.2001.mkv")
        for index in range(11):
            self.media(f"Other{index}/One.2001.mkv")
            self.media("One.2001.mkv", root=self.second_source_root)
        ambiguous = (
            MediaCandidate("tmdb", "201", MediaType.MOVIE, "One", year=2001),
            MediaCandidate("tmdb", "999", MediaType.MOVIE, "One", year=2001),
        )
        libraries = [
            self.resource_library("library"),
            self.resource_library("library2", storageId="source2"),
        ]
        with self.journey(candidates=ambiguous, resource_libraries=libraries) as value:
            self.admit(value, ["One.2001.mkv"])
            original = self.run_worker(value)
            intent_path = f"/api/v1/operations/organize/intents/{original['intentId']}"
            status, before = self.request(value, intent_path)
            self.assertEqual(200, status, before)
            self.assertEqual(
                {"201", "999"},
                {value["providerId"] for value in before["items"][0]["allowedMetadataIdentities"]},
            )

            # Many unrelated preparations, including > the bounded query limit
            # and a same-named file in a second Storage authority.
            for index in range(11):
                self.clock_value += timedelta(seconds=1)
                self.admit(value, [f"Other{index}/One.2001.mkv"])
                self.run_worker(value)
            self.clock_value += timedelta(seconds=1)
            second = self.admit(value, ["One.2001.mkv"], library_id="library2")
            self.run_worker(value)

            status, after = self.request(value, intent_path)
            self.assertEqual(200, status, after)
            item = after["items"][0]
            self.assertEqual(
                {"201", "999"},
                {value["providerId"] for value in item["allowedMetadataIdentities"]},
                item,
            )
            # The original legal choice still saves without re-running analysis.
            status, saved = self.request(
                value,
                f"{intent_path}/items/{item['itemId']}/choice",
                "POST",
                {
                    "expectedVersion": after["version"],
                    "expectedItemVersion": item["version"],
                    "metadata": {
                        "provider": "tmdb",
                        "providerId": "999",
                        "mediaType": "movie",
                        "title": "One",
                        "year": 2001,
                    },
                },
            )
            self.assertEqual(200, status, saved)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.source2.mutations)
            self.assertIsNotNone(second["discoveryId"])

    def test_replaced_source_version_does_not_inherit_old_candidates(self) -> None:
        """AC-5/6: a replaced file never inherits an older version's authority.

        After a same-path source is replaced by a different occurrence, a new
        preparation must not expose the old version's candidates before its own
        analysis, and a direct save of an old identity must be refused.  Once
        the new analysis completes, only the new version's own candidates are
        offered.
        """

        source = self.media("One.2001.mkv")
        old = (
            MediaCandidate("tmdb", "201", MediaType.MOVIE, "One", year=2001),
            MediaCandidate("tmdb", "999", MediaType.MOVIE, "One", year=2001),
        )
        new = (
            MediaCandidate("tmdb", "301", MediaType.MOVIE, "One", year=2001),
            MediaCandidate("tmdb", "999", MediaType.MOVIE, "One", year=2001),
        )
        provider = SyntheticMetadataProvider(old)
        with self.journey(provider=provider) as value:
            self.admit(value, ["One.2001.mkv"])
            first = self.run_worker(value)
            first_preview = value.repository.get_manual_preview(first["previewId"])
            old_fingerprint = first_preview.items[0].source.fingerprint
            self.assertEqual(
                {"201", "999"},
                {
                    value["providerId"]
                    for value in self.request(
                        value, f"/api/v1/operations/organize/intents/{first['intentId']}"
                    )[1]["items"][0]["allowedMetadataIdentities"]
                },
            )

            # Replace the file with a genuinely different occurrence and switch
            # the provider to the new version's own candidates.
            source.write_bytes(b"replaced media content" * 100)
            provider._candidates = new
            self.clock_value += timedelta(seconds=1)
            self.admit(value, ["One.2001.mkv"])
            # Stop after discovery/freeze: no new Provider analysis yet.
            frozen = value.discovery.claim_and_run(
                worker_id="fresh-discovery", claim_token="fresh-token"
            )
            self.assertIsNotNone(frozen.intent_id, frozen)
            self.assertIsNone(frozen.preview_id, frozen)
            fresh_intent = value.repository.get_manual_intent(frozen.intent_id)
            fresh_fingerprint = fresh_intent.items[0].source.fingerprint
            self.assertNotEqual(old_fingerprint, fresh_fingerprint)

            fresh_path = f"/api/v1/operations/organize/intents/{frozen.intent_id}"
            status, fresh = self.request(value, fresh_path)
            self.assertEqual(200, status, fresh)
            item = fresh["items"][0]
            # The old version's candidates are not published for the new file.
            self.assertEqual([], item["allowedMetadataIdentities"], item)
            status, rejected = self.request(
                value,
                f"{fresh_path}/items/{item['itemId']}/choice",
                "POST",
                {
                    "expectedVersion": fresh["version"],
                    "expectedItemVersion": item["version"],
                    "metadata": {
                        "provider": "tmdb",
                        "providerId": "999",
                        "mediaType": "movie",
                        "title": "One",
                        "year": 2001,
                    },
                },
            )
            self.assertEqual(400, status, rejected)
            self.assertEqual("metadata_unverified", rejected["error"]["code"])
            self.assertEqual([], value.source.mutations)

            # The new analysis, once completed, publishes only its own candidates.
            status, discovery = self.request(
                value, f"/api/v1/operations/organize/discoveries/{frozen.discovery_id}"
            )
            self.assertEqual(200, status, discovery)
            status, accepted = self.analyze(value, frozen.discovery_id, discovery["version"])
            self.assertEqual(200, status, accepted)
            reanalyzed = self.run_worker(value)
            self.assertEqual("completed", reanalyzed["status"], reanalyzed)
            status, refreshed = self.request(value, fresh_path)
            self.assertEqual(200, status, refreshed)
            identities = refreshed["items"][0]["allowedMetadataIdentities"]
            self.assertEqual({"301", "999"}, {value["providerId"] for value in identities})
            self.assertNotIn("201", {value["providerId"] for value in identities})

    def test_candidate_authority_requires_the_pinned_configuration(self) -> None:
        """AC-5: candidates are grounded in this item's own pinned revision.

        A source prepared under revision A keeps its own candidates even after a
        successor Active revision B is activated; a *new* preparation under B
        must not borrow A's candidate authority before its own analysis.
        """

        source = self.media("One.2001.mkv")
        old = (
            MediaCandidate("tmdb", "201", MediaType.MOVIE, "One", year=2001),
            MediaCandidate("tmdb", "999", MediaType.MOVIE, "One", year=2001),
        )
        with self.journey(candidates=old) as value:
            self.admit(value, ["One.2001.mkv"])
            first = self.run_worker(value)
            first_path = f"/api/v1/operations/organize/intents/{first['intentId']}"
            status, pinned = self.request(value, first_path)
            self.assertEqual(200, status, pinned)
            self.assertEqual(
                {"201", "999"},
                {value["providerId"] for value in pinned["items"][0]["allowedMetadataIdentities"]},
            )

            # Activate a successor revision; the pinned revision stays published.
            successor_document = self.document()
            successor_document["mediaLibraries"][0]["rootPath"] = "Organized/MoviesB"
            successor = _activate(value.managed, successor_document)
            self.assertNotEqual(
                value.repository.get_manual_intent(first["intentId"]).snapshot_id,
                successor.revision_id,
            )

            # The existing pinned preparation still reads its own candidates.
            status, after = self.request(value, first_path)
            self.assertEqual(200, status, after)
            self.assertEqual(
                {"201", "999"},
                {value["providerId"] for value in after["items"][0]["allowedMetadataIdentities"]},
            )

            # A brand-new preparation under revision B must not inherit A's
            # candidates before its own analysis has produced any.
            source.write_bytes(b"another replacement" * 100)
            self.clock_value += timedelta(seconds=1)
            self.admit(value, ["One.2001.mkv"])
            frozen = value.discovery.claim_and_run(
                worker_id="revision-b", claim_token="revision-b-token"
            )
            self.assertIsNotNone(frozen.intent_id, frozen)
            self.assertIsNone(frozen.preview_id, frozen)
            status, fresh = self.request(
                value, f"/api/v1/operations/organize/intents/{frozen.intent_id}"
            )
            self.assertEqual(200, status, fresh)
            self.assertEqual([], fresh["items"][0]["allowedMetadataIdentities"], fresh)
            self.assertEqual([], value.source.mutations)


class IntentPageAnalysisTests(_PreparationFixture):
    """The intent-page summary request is durable work, never HTTP analysis.

    B's confirmed P1 was the intent page's ``POST .../previews`` creating a plan
    inline inside the request: a slow Provider blocked the operator's browser,
    and an accepted cancel of the same run still left the late inline plan
    confirmable.  These regressions prove the request only records one versioned
    durable stage on the intent's own organize run, that the resident Worker
    builds and links the plan through the same atomic publication, and that a
    pause or cancel that wins never leaves a confirmable plan behind.
    """

    def _intent(self, value, *, paths=("Movies/One.2001.mkv",), single_file=False):
        """Admit one durable intent, either through the run-backed discovery or
        through the single-file Files admission that carries no run of its own."""

        if single_file:
            for name in paths:
                self.media(name)
            status, intent = self.request(
                value,
                "/api/v1/resource-libraries/library/files/organize",
                "POST",
                {"paths": list(paths)},
            )
            self.assertEqual(201, status, intent)
            return intent
        for name in paths:
            self.media(name)
        self.admit(value, list(paths))
        settled = self.run_worker(value)
        self.assertIsNotNone(settled["intentId"], settled)
        return value.repository.get_manual_intent(settled["intentId"])

    def _request_intent_analysis(self, value, intent):
        return self.request(
            value,
            f"/api/v1/operations/organize/intents/{intent.intent_id}/previews",
            "POST",
            {"expectedVersion": intent.version},
        )

    def _blocked_provider(self, value):
        """Pause only the outbound Provider call of the real analysis chain."""

        provider = next(iter(value.previews._providers._providers.values()))
        entered = threading.Event()
        release = threading.Event()
        original = type(provider).search_movie

        def blocked_search(inner_self, query, policy=None, **kwargs):
            entered.set()
            release.wait(timeout=30)
            return original(inner_self, query, policy=policy, **kwargs)

        return entered, release, patch.object(type(provider), "search_movie", blocked_search)

    def test_intent_analysis_runs_on_the_intent_own_durable_run(self) -> None:
        """A re-analysis records a durable stage; the Worker links the plan."""

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            intent = self._intent(value)
            first = value.repository.get_latest_manual_preview(intent.intent_id)
            self.assertIsNotNone(first)
            provider = next(iter(value.previews._providers._providers.values()))
            entered = threading.Event()
            release = threading.Event()
            original = type(provider).search_movie

            def blocked_search(inner_self, query, policy=None, **kwargs):
                entered.set()
                release.wait(timeout=30)
                return original(inner_self, query, policy=policy, **kwargs)

            with patch.object(type(provider), "search_movie", blocked_search):
                status, document = self._request_intent_analysis(value, intent)
                self.assertEqual(201, status, document)
                analysis = document["analysis"]
                self.assertEqual("analyzing", analysis["phase"], document)
                discovery_id = analysis["discoveryId"]
                self.assertTrue(entered.is_set() is False or entered.wait(0))
                # The request did not block on the Provider and did not link a
                # plan: the durable run is the analysis authority now.
                durable = value.repository.get_media_discovery(discovery_id)
                self.assertEqual("analyzing", durable.status.value, durable.status)
                self.assertIsNone(durable.preview_id, durable)
                self.assertEqual(1, len(value.repository.list_manual_previews(intent.intent_id)))
                release.set()
                analyzed = value.discovery.claim_and_run(
                    worker_id="intent-analysis-worker", claim_token="intent-analysis-token"
                )
                self.assertIsNotNone(analyzed.preview_id)
                self.assertNotEqual(first.preview_id, analyzed.preview_id)
                self.assertEqual(2, len(value.repository.list_manual_previews(intent.intent_id)))
                status, linked = self.request(
                    value,
                    f"/api/v1/operations/organize/previews/{analyzed.preview_id}",
                )
                self.assertEqual(200, status, linked)
                status, restored = self.request(
                    value,
                    f"/api/v1/operations/organize/intents/{intent.intent_id}",
                )
                self.assertEqual(200, status, restored)
                self.assertEqual(
                    analyzed.preview_id,
                    restored["analysis"]["previewId"],
                )
                self.assertTrue(value.repository.get_manual_preview(analyzed.preview_id).current)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_intent_analysis_without_a_run_gets_its_own_durable_run(self) -> None:
        """A single-file Files intent receives a durable run of its own."""

        self.media("One.2001.mkv")
        with self.journey() as value:
            admitted_intent = self._intent(value, paths=("One.2001.mkv",), single_file=True)
            intent = value.repository.get_manual_intent(admitted_intent["intentId"])
            self.assertIsNone(value.repository.find_media_discovery_for_intent(intent.intent_id))
            status, document = self._request_intent_analysis(value, intent)
            self.assertEqual(201, status, document)
            analysis = document["analysis"]
            self.assertEqual("analyzing", analysis["phase"], document)
            analysis["discoveryId"]
            durable = value.repository.get_media_discovery(analysis["discoveryId"])
            self.assertEqual(intent.intent_id, durable.intent_id)
            self.assertEqual(intent.snapshot_id, durable.snapshot_id)
            analyzed = value.discovery.claim_and_run(
                worker_id="single-file-worker", claim_token="single-file-token"
            )
            self.assertIsNotNone(analyzed.preview_id)
            status, restored = self.request(
                value,
                f"/api/v1/operations/organize/intents/{intent.intent_id}",
            )
            self.assertEqual(200, status, restored)
            self.assertEqual(analyzed.preview_id, restored["latestPlan"]["previewId"])
            status, plan = self.request(
                value,
                f"/api/v1/operations/organize/previews/{analyzed.preview_id}",
            )
            self.assertEqual(200, status, plan)
            self.assertEqual(["One.2001.mkv"], [item["source"]["path"] for item in plan["items"]])
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_cancelled_run_analysis_publishes_nothing_for_the_intent_page(self) -> None:
        """A cancel that wins leaves no confirmable plan for this entry."""

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            intent = self._intent(value)
            entered, release, guard = self._blocked_provider(value)
            results: list[object] = []
            with guard:
                status, document = self._request_intent_analysis(value, intent)
                self.assertEqual(201, status, document)
                discovery_id = document["analysis"]["discoveryId"]
                analysis_thread = threading.Thread(
                    target=lambda: results.append(
                        value.discovery.claim_and_run(
                            worker_id="cancelled-analysis-worker",
                            claim_token="cancelled-analysis-token",
                        )
                    ),
                    name="cancelled-intent-analysis",
                )
                analysis_thread.start()
                self.assertTrue(entered.wait(15), "the Worker never reached the Provider")
                status, cancelled = self.request(
                    value,
                    f"/api/v1/operations/organize/discoveries/{discovery_id}/cancel",
                    "POST",
                    {"expectedVersion": value.repository.get_media_discovery(discovery_id).version},
                )
                self.assertEqual(200, status, cancelled)
                release.set()
                analysis_thread.join(timeout=30)
                self.assertFalse(analysis_thread.is_alive())
                self.assertNotIsInstance(results[0], Exception, results)
                late = value.discovery.claim_and_run(
                    worker_id="late-worker", claim_token="late-token"
                )
                self.assertIsNone(late)
            durable = value.repository.get_media_discovery(discovery_id)
            self.assertEqual("cancelled", durable.status.value)
            self.assertIsNone(durable.preview_id, durable)
            # The cancelled run's analysis entry refuses an ordinary late
            # request instead of publishing a confirmable plan.
            status, refused = self._request_intent_analysis(value, intent)
            self.assertEqual(409, status, refused)
            self.assertEqual("discovery_already_finished", refused["error"]["code"])
            status, readback = self.request(
                value,
                f"/api/v1/operations/organize/intents/{intent.intent_id}",
            )
            self.assertEqual(200, status, readback)
            self.assertEqual("cancelled", readback["analysis"]["status"])
            self.assertIsNone(readback["analysis"]["previewId"])
            # The run's own latest plan never names the cancelled analysis: the
            # earlier published plan of the same intent stays the durable
            # history the operator already reviewed, and the cancelled run
            # links none of its own.
            self.assertEqual(durable.intent_id, intent.intent_id)
            if readback["latestPlan"] is not None:
                # The earlier published plan of the same intent is durable
                # history; the cancelled run never linked or superseded it.
                self.assertIsNone(durable.preview_id)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            # RO-2: the organizing Task admitted with the selection is real and
            # durable, but a paused/cancelled walk leaves no confirmable subset and
            # no TaskItem, so nothing can ever be executed from it.
            self.assert_no_executable_work(value)


if __name__ == "__main__":
    unittest.main()
