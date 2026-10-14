"""Task 43.2 — durable exact-analysis admission for Preview work (B43.2-2).

The existing exact Preview services analyse a whole definition scope or manual
intent synchronously inside the HTTP request.  These tests prove the durable
envelope that fixes that, against the real runtime SQLite repository and the
real application/API services:

* an expensive definition or manual analysis is admitted promptly with a
  durable identity, *before* the slow walk/Provider batch completes;
* a controlled slow analysis proves the admission returned while zero Preview
  rows existed, then the resident Worker completes and links the exact Preview;
* the durable record is readable and cooperatively pausable/resumable/
  cancellable at a safe boundary, with zero media mutation throughout;
* the analysis creates no execution authority, no Job and no second queue.
"""

from __future__ import annotations

import io
import json
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from mediaflow.application.automation_task_definition_preview import (
    AutomationTaskDefinitionPreviewService,
)
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.preview_analysis import (
    PreviewAnalysisService,
    PreviewAnalysisWorker,
)
from mediaflow.domain.preview_analysis import PreviewAnalysisError, PreviewAnalysisStatus
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

ADMIN_TOKEN = "preview-analysis-admin"
VIEWER_TOKEN = "preview-analysis-viewer"


class _Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


def _activate(service, document):
    draft = service.import_draft(document, actor="tester")
    validated = service.validate(draft.revision_id, actor="tester")
    if validated.status.value != "validated":
        raise AssertionError(validated.validation_errors)
    return service.activate(
        validated.revision_id, expected_version=validated.version, actor="tester"
    )


class _RecordingStorage:
    """Wrap Local Storage and record every call so mutation can be proven absent."""

    def __init__(self, storage) -> None:
        self._storage = storage
        self.reads: list[tuple[str, str]] = []
        self.mutations: list[tuple[str, str]] = []

    def __getattr__(self, name):
        return getattr(self._storage, name)

    def list(self, path: str):
        self.reads.append(("list", path))
        return self._storage.list(path)

    def list_page(self, path: str, *, limit: int, cursor: str | None = None):
        self.reads.append(("list_page", path))
        return self._storage.list_page(path, limit=limit, cursor=cursor)

    def stat(self, path: str):
        self.reads.append(("stat", path))
        return self._storage.stat(path)

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


class _DurableAnalysisFixture(unittest.TestCase):
    """A real managed runtime with one published definition and one intent."""

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

    def media(self, relative: str, *, size: int = 512) -> Path:
        path = self.source_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"m" * size)
        return path

    def document(self, *, item_limit: int = 5, source_scope: str | None = "Movies") -> dict:
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
        definition: dict[str, object] = {
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
        document["automationTaskDefinitions"] = [definition]
        return document

    @contextmanager
    def journey(self, *, item_limit: int = 5, source_scope: str | None = "Movies"):
        document = self.document(item_limit=item_limit, source_scope=source_scope)
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

            def resolve_definition_runtime(snapshot_id, digest):
                pinned_revision = managed.require(snapshot_id)
                managed.verify_integrity(pinned_revision)
                if pinned_revision.digest != digest:
                    raise ValueError("requested managed configuration digest is stale")
                return with_managed_snapshot(
                    load_managed_runtime_configuration(
                        pinned_revision.document,
                        bootstrap_database_path=managed.bootstrap_database_path,
                    ),
                    snapshot_id=pinned_revision.revision_id,
                    digest=pinned_revision.digest,
                    version=pinned_revision.version,
                )

            intents = ManualOrganizeIntentService(
                repository,
                None,
                managed,
                runtime_resolver=lambda snapshot_id, digest: runtime,
                storage_factory=lambda value, ids: dict(storages),
            )
            manual_previews = ManualOrganizePreviewService(
                repository,
                intents,
                None,
                configuration=runtime,
                storages=dict(storages),
                clock=self.clock,
            )
            definition_previews = AutomationTaskDefinitionPreviewService(
                repository,
                managed,
                runtime_resolver=resolve_definition_runtime,
                storages=dict(storages),
                clock=self.clock,
            )
            analyses = PreviewAnalysisService(
                repository,
                definition_previews=definition_previews,
                manual_previews=manual_previews,
                clock=self.clock,
            )
            worker = PreviewAnalysisWorker(analyses, worker_id="analysis-worker")
            api = MediaFlowApi(
                repository,
                None,
                principals=(
                    ResolvedApiPrincipal(
                        "operator",
                        ADMIN_TOKEN,
                        frozenset(
                            {
                                ApiPermission.READ,
                                ApiPermission.MANAGE_MANUAL_ORGANIZE,
                                ApiPermission.SUBMIT_DRY_RUN,
                            }
                        ),
                    ),
                    ResolvedApiPrincipal("viewer", VIEWER_TOKEN, frozenset({ApiPermission.READ})),
                ),
                configuration_service=managed,
                bootstrap_document=document,
                manual_intent_service=intents,
                manual_preview_service=manual_previews,
                automation_preview_service=definition_previews,
                preview_analysis_service=analyses,
                storage_adapters=dict(storages),
            )
            yield SimpleNamespace(
                api=api,
                repository=repository,
                intents=intents,
                manual_previews=manual_previews,
                definition_previews=definition_previews,
                analyses=analyses,
                worker=worker,
                runtime=runtime,
                revision=revision,
                managed=managed,
                clock=self.clock,
                source=source,
                target=target,
            )

    @staticmethod
    def request(value, path: str, method: str = "GET", body=None, *, token=ADMIN_TOKEN):
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


class DurableAnalysisAdmissionTests(_DurableAnalysisFixture):
    """AC-T3: long analysis is admitted promptly and stays durable."""

    def test_definition_analysis_admission_is_prompt_and_durable(self) -> None:
        self.media("Movies/One.2001.mkv")
        self.media("Movies/Two.2002.mkv")
        with self.journey() as value:
            # The admission itself performs no walk at all: it is durable and
            # prompt by construction, and zero Preview rows exist until a
            # Worker actually runs the analysis.
            status, body = self.request(
                value,
                "/api/v1/automation/task-definitions/nightly/preview-analyses",
                "POST",
                {},
            )
            self.assertEqual(202, status, body)
            self.assertEqual("queued", body["status"])
            self.assertEqual("nightly", body["definitionId"])
            self.assertEqual(value.revision.revision_id, body["configurationSnapshotId"])
            self.assertTrue(body["zeroMutation"])
            self.assertEqual(value.revision.revision_id, body["configurationSnapshotId"])
            analysis_id = body["analysisId"]
            # Durable *before* any analysis work happens, with zero Preview rows
            # and zero Storage reads at admission.
            durable = value.analyses.get(analysis_id)
            self.assertEqual(PreviewAnalysisStatus.QUEUED, durable.status)
            rows = value.repository._connection.execute(
                "SELECT COUNT(*) FROM automation_task_definition_previews"
            ).fetchone()[0]
            self.assertEqual(0, rows)
            self.assertEqual([], value.source.reads)
            # The readback route restores the same durable identity.
            status, detail = self.request(
                value,
                f"/api/v1/operations/automation/preview-analyses/{analysis_id}",
            )
            self.assertEqual(200, status, detail)
            self.assertEqual(analysis_id, detail["analysisId"])
            self.assertTrue(detail["actions"]["cancel"]["available"])
            self.assertFalse(detail["actions"]["preview"]["available"])
            # A Worker-side slow analysis proves the durable record is readable
            # and controllable *while* the walk is still running.
            release = threading.Event()
            entered = threading.Event()
            original = value.definition_previews._discover

            def blocking_discover(*args, **kwargs):
                entered.set()
                release.wait(timeout=15)
                return original(*args, **kwargs)

            value.definition_previews._discover = blocking_discover
            holder: list[object] = []
            runner = threading.Thread(
                target=lambda: holder.append(value.worker.run_next()), daemon=True
            )
            try:
                runner.start()
                self.assertTrue(entered.wait(timeout=10))
                # The walk is blocked, yet the record is running and readable.
                running = value.analyses.get(analysis_id)
                self.assertEqual(PreviewAnalysisStatus.RUNNING, running.status)
                status, detail = self.request(
                    value,
                    f"/api/v1/operations/automation/preview-analyses/{analysis_id}",
                )
                self.assertEqual(200, status, detail)
                self.assertEqual("running", detail["status"])
                self.assertTrue(detail["actions"]["pause"]["available"])
                self.assertEqual(0, len(value.source.mutations))
                self.assertEqual(0, len(value.target.mutations))
                # A cooperative cancel settles it at the safe boundary.
                status, cancelled = self.request(
                    value,
                    f"/api/v1/operations/automation/preview-analyses/{analysis_id}/cancel",
                    "POST",
                    {"expectedVersion": running.version},
                )
                self.assertEqual(200, status, cancelled)
                self.assertEqual("running", cancelled["status"])
                self.assertTrue(cancelled["cancelRequested"])
            finally:
                release.set()
                value.definition_previews._discover = original
                runner.join(timeout=15)
            # The accepted cancellation wins: no Preview was published.
            final = value.analyses.get(analysis_id)
            self.assertEqual(PreviewAnalysisStatus.CANCELLED, final.status)
            self.assertIsNone(final.preview_id)
            self.assertEqual(
                0,
                value.repository._connection.execute(
                    "SELECT COUNT(*) FROM automation_task_definition_previews"
                ).fetchone()[0],
            )
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_worker_completes_the_analysis_and_links_the_exact_preview(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            status, body = self.request(
                value,
                "/api/v1/automation/task-definitions/nightly/preview-analyses",
                "POST",
                {},
            )
            self.assertEqual(202, status, body)
            analysis_id = body["analysisId"]
            # The resident Worker claims and completes the durable analysis.
            settled = value.worker.run_next()
            self.assertIsNotNone(settled)
            self.assertEqual(analysis_id, settled.analysis_id)
            self.assertEqual(PreviewAnalysisStatus.COMPLETED, settled.status)
            self.assertIsNotNone(settled.preview_id)
            status, detail = self.request(
                value,
                f"/api/v1/operations/automation/preview-analyses/{analysis_id}",
            )
            self.assertEqual(200, status, detail)
            self.assertEqual("completed", detail["status"])
            self.assertEqual(settled.preview_id, detail["previewId"])
            self.assertEqual(
                f"/operations/automation/preview/nightly/{settled.preview_id}",
                detail["previewPath"],
            )
            status, definition_preview = self.request(
                value,
                f"/api/v1/automation/task-definitions/nightly/previews/{settled.preview_id}",
            )
            self.assertEqual(200, status, definition_preview)
            status, manual_preview = self.request(
                value,
                f"/api/v1/operations/organize/preview/{settled.preview_id}",
            )
            self.assertEqual(404, status, manual_preview)
            self.assertTrue(detail["actions"]["preview"]["available"])
            self.assertFalse(detail["actions"]["pause"]["available"])
            # The exact Preview evidence the existing service produces is durable.
            preview = value.definition_previews.get_readonly(settled.preview_id)
            self.assertEqual("nightly", preview.definition_id)
            self.assertTrue(preview.zero_mutation)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)
            # No dummy Job and no second queue were created.
            jobs = value.repository._connection.execute(
                "SELECT COUNT(*) FROM automation_jobs"
            ).fetchone()[0]
            self.assertEqual(0, jobs)

    def test_analysis_is_pausable_resumable_and_cancellable(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            status, body = self.request(
                value,
                "/api/v1/automation/task-definitions/nightly/preview-analyses",
                "POST",
                {},
            )
            self.assertEqual(202, status, body)
            analysis_id = body["analysisId"]
            status, paused = self.request(
                value,
                f"/api/v1/operations/automation/preview-analyses/{analysis_id}/pause",
                "POST",
                {"expectedVersion": body["version"]},
            )
            self.assertEqual(200, status, paused)
            self.assertEqual("paused", paused["status"])
            self.assertTrue(paused["actions"]["resume"]["available"])
            status, resumed = self.request(
                value,
                f"/api/v1/operations/automation/preview-analyses/{analysis_id}/resume",
                "POST",
                {"expectedVersion": paused["version"]},
            )
            self.assertEqual(200, status, resumed)
            self.assertEqual("queued", resumed["status"])
            status, cancelled = self.request(
                value,
                f"/api/v1/operations/automation/preview-analyses/{analysis_id}/cancel",
                "POST",
                {"expectedVersion": resumed["version"]},
            )
            self.assertEqual(200, status, cancelled)
            self.assertEqual("cancelled", cancelled["status"])
            # A settled analysis cannot be controlled again.
            status, _rejected = self.request(
                value,
                f"/api/v1/operations/automation/preview-analyses/{analysis_id}/cancel",
                "POST",
                {"expectedVersion": cancelled["version"]},
            )
            self.assertEqual(409, status)
            # Cancellation published no Preview and mutated nothing.
            self.assertIsNone(cancelled["previewId"])
            self.assertIsNone(value.analyses.get(analysis_id).preview_id)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_duplicate_admission_reconciles_to_one_analysis(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            request_id = "22222222-2222-4222-8222-222222222222"
            first = value.analyses.admit_definition(
                "nightly", actor="operator", admission_request_id=request_id
            )
            second = value.analyses.admit_definition(
                "nightly", actor="operator", admission_request_id=request_id
            )
            self.assertEqual(first.analysis_id, second.analysis_id)
            # A different principal never reconciles to another's request.
            third = value.analyses.admit_definition("nightly", actor="someone-else")
            self.assertNotEqual(first.analysis_id, third.analysis_id)

    def test_request_retry_keeps_its_original_pin_and_refuses_a_changed_revision(self) -> None:
        with self.journey() as value:
            request_id = "44444444-4444-4444-8444-444444444444"
            first = value.analyses.admit_definition(
                "nightly", actor="operator", admission_request_id=request_id
            )
            successor = _activate(value.managed, self.document(source_scope="Other"))

            # A lost-response retry with the same identity returns the exact
            # original pin even after Active changed. A deliberate request to
            # reuse that ID for the new revision is a binding conflict.
            retried = value.analyses.admit_definition(
                "nightly", actor="operator", admission_request_id=request_id
            )
            self.assertEqual(first.analysis_id, retried.analysis_id)
            self.assertEqual(first.configuration_snapshot_id, retried.configuration_snapshot_id)
            with self.assertRaises(PreviewAnalysisError):
                value.analyses.admit_definition(
                    "nightly",
                    actor="operator",
                    revision_id=successor.revision_id,
                    admission_request_id=request_id,
                )

    def test_manual_request_retry_survives_intent_change_and_changed_version_is_refused(
        self,
    ) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            intent = value.manual_previews.admit_storage_paths(
                resource_library_id="library",
                relative_paths=["Movies/One.2001.mkv"],
                actor="operator",
            )
            request_id = "55555555-5555-4555-8555-555555555555"
            path = f"/api/v1/operations/organize/intents/{intent.intent_id}/preview-analyses"
            status, first = self.request(
                value,
                path,
                "POST",
                {
                    "expectedVersion": intent.version,
                    "admissionRequestId": request_id,
                },
            )
            self.assertEqual(202, status, first)

            item = intent.items[0]
            changed = value.intents.update_choice(
                intent.intent_id,
                item.item_id,
                item.choice,
                expected_version=intent.version,
                expected_item_version=item.version,
                actor="operator",
            )
            self.assertGreater(changed.version, intent.version)

            # A replay of the original submitted binding converges to the
            # durable record; the same request ID cannot bind the new intent
            # version to a second analysis.
            status, retried = self.request(
                value,
                path,
                "POST",
                {
                    "expectedVersion": intent.version,
                    "admissionRequestId": request_id,
                },
            )
            self.assertEqual(202, status, retried)
            self.assertEqual(first["analysisId"], retried["analysisId"])
            status, refused = self.request(
                value,
                path,
                "POST",
                {
                    "expectedVersion": changed.version,
                    "admissionRequestId": request_id,
                },
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("admission_request_conflict", refused["error"]["code"])

    def test_a_corrected_intent_version_is_not_silently_answered_by_stale_open_work(
        self,
    ) -> None:
        """A new request for a changed intent version never reports old work.

        The operator saved a choice after version 1 was already queued, then
        requested an exact analysis of version 2 with a *new* request ID. The
        open-work reconciliation must include the complete manual intent
        binding (the admitted version), so the version-2 request either admits
        its own version-2 analysis or refuses explicitly; it can never return
        the version-1 analysis as the version-2 admission (B43.2-R3-1).
        """

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            intent = value.manual_previews.admit_storage_paths(
                resource_library_id="library",
                relative_paths=["Movies/One.2001.mkv"],
                actor="operator",
            )
            first = value.analyses.admit_manual(
                intent.intent_id,
                actor="operator",
                expected_version=intent.version,
                admission_request_id="66666666-6666-4666-8666-666666666666",
            )
            self.assertEqual(intent.version, first.intent_version)
            # The operator saves one choice: the intent advances to version 2.
            item = intent.items[0]
            changed = value.intents.update_choice(
                intent.intent_id,
                item.item_id,
                item.choice,
                expected_version=intent.version,
                expected_item_version=item.version,
                actor="operator",
            )
            self.assertGreater(changed.version, intent.version)
            # A corrected exact analysis is requested with a NEW request ID.
            corrected = value.analyses.admit_manual(
                intent.intent_id,
                actor="operator",
                expected_version=changed.version,
                admission_request_id="77777777-7777-4777-8777-777777777777",
            )
            self.assertNotEqual(first.analysis_id, corrected.analysis_id)
            self.assertEqual(changed.version, corrected.intent_version)
            # The corrected analysis settles into an exact Preview of the
            # corrected intent rather than failing on a stale binding. The
            # superseded version-1 analysis honestly fails its stale pinned
            # version: its intent was corrected after it was admitted, so it
            # can never publish a Preview of choices the operator replaced.
            # Both analyses share one admitted created_at, so the Worker may
            # claim either first; the durable per-identity outcome is what the
            # invariant fixes, not the claim order.
            settled: dict[str, object] = {}
            while True:
                result = value.worker.run_next()
                if result is None:
                    break
                settled[result.analysis_id] = result
            self.assertEqual({first.analysis_id, corrected.analysis_id}, set(settled))
            settled_corrected = settled[corrected.analysis_id]
            settled_first = settled[first.analysis_id]
            self.assertEqual(PreviewAnalysisStatus.COMPLETED, settled_corrected.status)
            self.assertIsNotNone(settled_corrected.preview_id)
            self.assertEqual(PreviewAnalysisStatus.FAILED, settled_first.status)
            self.assertIsNone(settled_first.preview_id)
            preview = value.manual_previews.get_readonly(settled_corrected.preview_id)
            self.assertEqual(changed.version, preview.intent_version)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_two_open_version_requests_with_new_ids_keep_their_own_lookups(
        self,
    ) -> None:
        """Each accepted request identity stays readable by its own ID.

        Two requests for two different intent versions of one intent converge
        on two durable analyses; each submitted request ID must reconcile to
        the analysis it actually created, never to the other one.
        """

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            intent = value.manual_previews.admit_storage_paths(
                resource_library_id="library",
                relative_paths=["Movies/One.2001.mkv"],
                actor="operator",
            )
            first_request = "88888888-8888-4888-8888-888888888888"
            first = value.analyses.admit_manual(
                intent.intent_id,
                actor="operator",
                expected_version=intent.version,
                admission_request_id=first_request,
            )
            item = intent.items[0]
            changed = value.intents.update_choice(
                intent.intent_id,
                item.item_id,
                item.choice,
                expected_version=intent.version,
                expected_item_version=item.version,
                actor="operator",
            )
            second_request = "99999999-9999-4999-8999-999999999999"
            second = value.analyses.admit_manual(
                intent.intent_id,
                actor="operator",
                expected_version=changed.version,
                admission_request_id=second_request,
            )
            self.assertNotEqual(first.analysis_id, second.analysis_id)
            self.assertEqual(first_request, first.admission_request_id, first.admission_request_id)
            self.assertEqual(
                second_request,
                second.admission_request_id,
                second.admission_request_id,
            )
            readback_first = value.analyses.find_by_request_id(
                actor="operator", admission_request_id=first_request
            )
            readback_second = value.analyses.find_by_request_id(
                actor="operator", admission_request_id=second_request
            )
            self.assertIsNotNone(readback_first)
            self.assertIsNotNone(readback_second)
            self.assertEqual(first.analysis_id, readback_first.analysis_id)
            self.assertEqual(second.analysis_id, readback_second.analysis_id)

    def test_equivalent_manual_request_with_a_new_id_returns_the_same_analysis(
        self,
    ) -> None:
        """B43.2-R4-1: a repeated/two-tab manual Preview must not fail.

        A second equivalent request for the *same* intent version with a new
        request ID converges on the already durable analysis and must complete
        the request association and return that exact analysis, instead of an
        internal error that leaves the operator unable to reconcile.
        """

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            intent = value.manual_previews.admit_storage_paths(
                resource_library_id="library",
                relative_paths=["Movies/One.2001.mkv"],
                actor="operator",
            )
            first_request = "abababab-abab-4bab-8bab-abababababab"
            second_request = "cdcdcdcd-cdcd-4dcd-8dcd-cdcdcdcdcdcd"
            first = value.analyses.admit_manual(
                intent.intent_id,
                actor="operator",
                expected_version=intent.version,
                admission_request_id=first_request,
            )
            second = value.analyses.admit_manual(
                intent.intent_id,
                actor="operator",
                expected_version=intent.version,
                admission_request_id=second_request,
            )
            self.assertEqual(first.analysis_id, second.analysis_id)
            readback_second = value.analyses.find_by_request_id(
                actor="operator", admission_request_id=second_request
            )
            self.assertIsNotNone(readback_second)
            self.assertEqual(first.analysis_id, readback_second.analysis_id)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_concurrent_same_request_analysis_creates_one_durable_record(
        self,
    ) -> None:
        """B43.2-R4-2: the durable create fences the request identity.

        Two requests for the same definition/request identity synchronize only
        between the real open-work read and the create, so both observe "no open
        work".  The request-identity uniqueness must hold at the durable
        concurrency boundary: exactly one analysis row exists and both callers
        receive it.
        """

        import threading
        from concurrent.futures import ThreadPoolExecutor

        with self.journey() as value:
            barrier = threading.Barrier(2)
            original = value.analyses._find_open

            def synchronized_find(**kwargs):
                result = original(**kwargs)
                barrier.wait(timeout=10)
                return result

            value.analyses._find_open = synchronized_find
            request_id = "efefefef-efef-4fef-8fef-efefefefefef"

            def admit(_index):
                return value.analyses.admit_definition(
                    "nightly", actor="operator", admission_request_id=request_id
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(admit, range(2)))
            identities = {item.analysis_id for item in results}
            self.assertEqual(1, len(identities), identities)
            rows = value.repository._connection.execute(
                "SELECT analysis_id FROM preview_analyses WHERE actor=? AND admission_request_id=?",
                ("operator", request_id),
            ).fetchall()
            self.assertEqual(1, len(rows))
            self.assertEqual(next(iter(identities)), rows[0]["analysis_id"])
            self.assertEqual([], value.source.mutations)

    def test_analysis_admission_survives_sqlite_close_and_reopen(self) -> None:
        with self.journey() as value:
            admitted = value.analyses.admit_definition("nightly", actor="operator")
            analysis_id = admitted.analysis_id
            revision_id = admitted.configuration_snapshot_id
        with SQLiteTaskRepository(self.database) as reopened:
            persisted = reopened.get_preview_analysis(analysis_id)
            self.assertIsNotNone(persisted)
            self.assertEqual(PreviewAnalysisStatus.QUEUED, persisted.status)
            self.assertEqual("nightly", persisted.definition_id)
            self.assertEqual(revision_id, persisted.configuration_snapshot_id)

    def test_request_id_reuse_with_another_definition_is_rejected(self) -> None:
        with self.journey() as value:
            request_id = "33333333-3333-4333-8333-333333333333"
            first = value.analyses.admit_definition(
                "nightly", actor="operator", admission_request_id=request_id
            )
            with self.assertRaises(PreviewAnalysisError):
                value.analyses.admit_definition(
                    "different", actor="operator", admission_request_id=request_id
                )
            self.assertEqual(first.analysis_id, value.analyses.get(first.analysis_id).analysis_id)
            self.assertEqual(1, len(value.analyses.list(actor="operator")))

    def test_worker_uses_the_admitted_definition_pin_after_publication(self) -> None:
        self.media("Movies/One.2001.mkv")
        self.media("Other/Two.2002.mkv")
        with self.journey() as value:
            admitted = value.analyses.admit_definition("nightly", actor="operator")
            published = _activate(value.managed, self.document(source_scope="Other"))
            self.assertNotEqual(admitted.configuration_snapshot_id, published.revision_id)

            settled = value.worker.run_next()
            self.assertIsNotNone(settled)
            self.assertEqual(PreviewAnalysisStatus.COMPLETED, settled.status)
            preview = value.definition_previews.get_readonly(settled.preview_id)
            self.assertEqual(admitted.configuration_snapshot_id, preview.configuration_revision_id)
            self.assertEqual("Movies", preview.source_scope)
            self.assertEqual(
                ["Movies/One.2001.mkv"],
                [item.source.path for item in preview.items],
            )

    def test_running_pause_is_acknowledged_before_any_preview_is_published(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            admitted = value.analyses.admit_definition("nightly", actor="operator")
            entered = threading.Event()
            release = threading.Event()
            original = value.definition_previews._discover

            def blocking_discover(*args, **kwargs):
                entered.set()
                release.wait(timeout=15)
                return original(*args, **kwargs)

            value.definition_previews._discover = blocking_discover
            runner = threading.Thread(target=value.worker.run_next, daemon=True)
            try:
                runner.start()
                self.assertTrue(entered.wait(timeout=10))
                running = value.analyses.get(admitted.analysis_id)
                requested = value.analyses.request_pause(
                    admitted.analysis_id,
                    actor="operator",
                    expected_version=running.version,
                )
                self.assertEqual(PreviewAnalysisStatus.RUNNING, requested.status)
                self.assertTrue(requested.pause_requested)
            finally:
                release.set()
                value.definition_previews._discover = original
                runner.join(timeout=15)

            paused = value.analyses.get(admitted.analysis_id)
            self.assertFalse(runner.is_alive())
            self.assertEqual(PreviewAnalysisStatus.PAUSED, paused.status)
            self.assertIsNone(paused.preview_id)
            self.assertEqual(
                0,
                value.repository._connection.execute(
                    "SELECT COUNT(*) FROM automation_task_definition_previews"
                ).fetchone()[0],
            )

            resumed = value.analyses.resume(
                admitted.analysis_id,
                actor="operator",
                expected_version=paused.version,
            )
            self.assertEqual(PreviewAnalysisStatus.QUEUED, resumed.status)
            completed = value.worker.run_next()
            self.assertEqual(PreviewAnalysisStatus.COMPLETED, completed.status)
            self.assertIsNotNone(completed.preview_id)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_worker_heartbeats_a_long_analysis_lease(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            admitted = value.analyses.admit_definition("nightly", actor="operator")
            value.analyses._clock = lambda: datetime.now(UTC)
            value.analyses._lease_seconds = 0.3
            entered = threading.Event()
            release = threading.Event()
            original = value.definition_previews._discover

            def blocking_discover(*args, **kwargs):
                entered.set()
                release.wait(timeout=15)
                return original(*args, **kwargs)

            value.definition_previews._discover = blocking_discover
            holder: list[object] = []
            runner = threading.Thread(
                target=lambda: holder.append(value.worker.run_next()), daemon=True
            )
            try:
                runner.start()
                self.assertTrue(entered.wait(timeout=10))
                initial = value.analyses.get(admitted.analysis_id)
                first_expiry = initial.claim_expires_at
                self.assertIsNotNone(first_expiry)
                time.sleep(0.2)
                renewed = value.analyses.get(admitted.analysis_id)
                self.assertGreater(renewed.claim_expires_at, first_expiry)
                successor = value.repository.claim_next_preview_analysis(
                    datetime.now(UTC),
                    worker_id="new-owner",
                    claim_token="new-owner-token",
                    lease_seconds=0.3,
                )
                self.assertIsNone(successor)
            finally:
                release.set()
                value.definition_previews._discover = original
                runner.join(timeout=15)

            self.assertFalse(runner.is_alive())
            self.assertEqual(1, len(holder))
            self.assertEqual(PreviewAnalysisStatus.COMPLETED, holder[0].status)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_expired_owner_cannot_publish_after_a_successor_claims(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            admitted = value.analyses.admit_definition("nightly", actor="operator")
            entered = threading.Event()
            release = threading.Event()
            original = value.definition_previews._discover

            def blocking_discover(*args, **kwargs):
                entered.set()
                release.wait(timeout=15)
                return original(*args, **kwargs)

            value.definition_previews._discover = blocking_discover
            errors: list[BaseException] = []

            def run_old_owner():
                try:
                    value.worker.run_next()
                except BaseException as error:  # captured for the test thread
                    errors.append(error)

            runner = threading.Thread(target=run_old_owner, daemon=True)
            try:
                runner.start()
                self.assertTrue(entered.wait(timeout=10))
                value.clock.now += timedelta(seconds=301)
                successor = value.repository.claim_next_preview_analysis(
                    value.clock(),
                    worker_id="new-owner",
                    claim_token="new-owner-token",
                    lease_seconds=300,
                )
                self.assertIsNotNone(successor)
                self.assertEqual("new-owner", successor.claim_worker_id)
            finally:
                release.set()
                value.definition_previews._discover = original
                runner.join(timeout=15)

            self.assertFalse(runner.is_alive())
            self.assertEqual([], errors)
            final = value.analyses.get(admitted.analysis_id)
            self.assertEqual(PreviewAnalysisStatus.RUNNING, final.status)
            self.assertEqual("new-owner", final.claim_worker_id)
            self.assertIsNone(final.preview_id)
            self.assertEqual(
                0,
                value.repository._connection.execute(
                    "SELECT COUNT(*) FROM automation_task_definition_previews"
                ).fetchone()[0],
            )

    def test_resident_registration_stays_live_during_a_long_analysis(self) -> None:
        """A long analysis keeps the containing Worker's registration live.

        While the exact analysis blocks inside one Storage/Provider call, the
        lease keeper refreshes both the analysis claim *and* the parent
        processing-Worker registration, so real readiness never reports the
        working Worker stale (B43.2-R3-3).
        """

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            value.analyses._clock = lambda: datetime.now(UTC)
            value.analyses._lease_seconds = 0.3
            from mediaflow.application.automation import AutomationWorker

            parent = AutomationWorker(
                value.repository,
                lambda *_args: None,
                worker_id="resident-probe",
                heartbeat_interval_seconds=0.1,
                runtime_schema_version=48,
                preview_analysis_worker=value.worker,
            )
            parent.register()
            entered = threading.Event()
            release = threading.Event()
            original = value.definition_previews._discover

            def blocking_discover(*args, **kwargs):
                entered.set()
                release.wait(timeout=15)
                return original(*args, **kwargs)

            value.definition_previews._discover = blocking_discover
            analysis = value.analyses.admit_definition("nightly", actor="operator")
            thread = threading.Thread(target=parent._run_preview_analysis_work, daemon=True)
            try:
                thread.start()
                self.assertTrue(entered.wait(timeout=5))
                before = value.repository.get_worker(parent.worker_id)
                # Well past the parent's stale threshold (max(3x interval,10s)
                # would be 10s; use 0.5s of analysis time and check the
                # heartbeat actually advanced instead of sleeping 10 real
                # seconds — the threshold formula is exercised below).
                time.sleep(0.5)
                after = value.repository.get_worker(parent.worker_id)
                self.assertIsNotNone(before)
                self.assertIsNotNone(after)
                self.assertGreater(after.last_heartbeat_at, before.last_heartbeat_at)
                current = value.analyses.get(analysis.analysis_id)
                self.assertIsNotNone(current.claim_expires_at)
                self.assertGreater(current.claim_expires_at, datetime.now(UTC))
            finally:
                release.set()
                thread.join(timeout=10)
                value.definition_previews._discover = original
            self.assertEqual(
                PreviewAnalysisStatus.COMPLETED,
                value.analyses.get(analysis.analysis_id).status,
            )
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_lost_analysis_response_reconciles_by_the_request_identity(self) -> None:
        """A lost analysis admission response reads back its proved original.

        The request identity is generated before the POST, so a lost or
        malformed response is an *unknown* outcome, not a rejection: the
        operator reconciles it by its own ID, and a proved absence is a
        bounded 404 rather than a guessed latest analysis.
        """

        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            request_id = "22222222-3333-4222-8222-333333333333"
            # A proved absence before anything was admitted.
            status, absent = self.request(
                value,
                f"/api/v1/operations/automation/preview-analyses?admissionRequestId={request_id}",
            )
            self.assertEqual(404, status)
            self.assertEqual("preview_analysis_request_not_found", absent["error"]["code"])
            self.assertEqual("unknown", absent["error"]["details"]["durableState"])
            # Admit a definition analysis with that identity, then reconcile.
            admitted = value.analyses.admit_definition(
                "nightly", actor="operator", admission_request_id=request_id
            )
            status, reconciled = self.request(
                value,
                f"/api/v1/operations/automation/preview-analyses?admissionRequestId={request_id}",
            )
            self.assertEqual(200, status, reconciled)
            self.assertEqual(admitted.analysis_id, reconciled["analysisId"])
            # Another principal never reads this identity's analysis.
            status, _foreign = self.request(
                value,
                f"/api/v1/operations/automation/preview-analyses?admissionRequestId={request_id}",
                token=VIEWER_TOKEN,
            )
            self.assertEqual(404, status)
            # The read created no additional work.
            self.assertEqual(1, len(value.analyses.list(actor="operator")))
            self.assertEqual([], value.source.mutations)

    def test_manual_analysis_admits_promptly_and_completes(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            intent = value.manual_previews.admit_storage_paths(
                resource_library_id="library",
                relative_paths=["Movies/One.2001.mkv"],
                actor="operator",
            )
            status, body = self.request(
                value,
                f"/api/v1/operations/organize/intents/{intent.intent_id}/preview-analyses",
                "POST",
                {"expectedVersion": intent.version},
            )
            self.assertEqual(202, status, body)
            self.assertEqual("manual", body["kind"])
            self.assertEqual(intent.intent_id, body["intentId"])
            settled = value.worker.run_next()
            self.assertIsNotNone(settled)
            self.assertEqual("completed", settled.status.value)
            self.assertIsNotNone(settled.preview_id)
            self.assertEqual([], value.source.mutations)
            self.assertEqual([], value.target.mutations)

    def test_rbac_and_malformed_input_are_refused_without_work(self) -> None:
        self.media("Movies/One.2001.mkv")
        with self.journey() as value:
            status, _ = self.request(
                value,
                "/api/v1/automation/task-definitions/nightly/preview-analyses",
                "POST",
                {},
                token=VIEWER_TOKEN,
            )
            self.assertEqual(403, status)
            # An unsupported extra field is refused rather than ignored.
            status, _ = self.request(
                value,
                "/api/v1/automation/task-definitions/nightly/preview-analyses",
                "POST",
                {"unexpected": True},
            )
            self.assertEqual(400, status)
            # An unknown analysis id is a bounded 404.
            status, _ = self.request(
                value,
                "/api/v1/operations/automation/preview-analyses/absent",
            )
            self.assertEqual(404, status)
            self.assertEqual(
                0,
                value.repository._connection.execute(
                    "SELECT COUNT(*) FROM preview_analyses"
                ).fetchone()[0],
            )
            self.assertEqual([], value.source.mutations)


if __name__ == "__main__":
    unittest.main()
