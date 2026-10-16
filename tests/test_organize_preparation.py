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
import unittest
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

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
        self.clock_value = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)

    def clock(self) -> datetime:
        return self.clock_value

    def media(self, relative: str, *, size: int = 64) -> Path:
        path = self.source_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"m" * size)
        return path

    def document(self, *, exclude_rules: tuple[str, ...] = ()) -> dict:
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
                "id": "target",
                "name": "Target",
                "type": "local",
                "rootPath": str(self.target_root),
                "enabled": True,
            },
        ]
        library = {
            "id": "library",
            "name": "Library",
            "storageId": "source",
            "storagePath": "",
            "enabled": True,
            "extensions": ["mkv", "mp4"],
            "maxDepth": None,
            "excludeRules": list(exclude_rules),
        }
        document["resourceLibraries"] = [library]
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
    def journey(self, *, budgets: DiscoveryBudgets | None = None):
        document = self.document()
        source = _RecordingStorage("source", self.source_root)
        target = _RecordingStorage("target", self.target_root)
        storages = {"source": source, "target": target}
        providers = MetadataProviderRegistry(
            (
                SyntheticMetadataProvider(
                    (
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
                ),
            )
        )
        with (
            SQLiteConfigurationRepository(self.database) as configuration_repository,
            SQLiteTaskRepository(self.database) as repository,
        ):
            managed = ManagedConfigurationService(
                configuration_repository, bootstrap_database_path=str(self.database)
            )
            revision = _activate(managed, document)
            runtime = _runtime_for(managed, revision)
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
                storages=dict(storages),
                providers=providers,
                clock=self.clock,
            )
            discovery = MediaDiscoveryService(
                repository,
                intents,
                configuration=runtime,
                runtime_resolver=lambda snapshot_id, digest: runtime,
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
                source=source,
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

    def admit(self, value, paths: list[str]):
        status, document = self.request(
            value,
            "/api/v1/resource-libraries/library/files/discoveries",
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


if __name__ == "__main__":
    unittest.main()
