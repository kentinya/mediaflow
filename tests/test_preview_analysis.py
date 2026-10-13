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
import unittest
from contextlib import contextmanager
from datetime import UTC, datetime
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
from mediaflow.domain.preview_analysis import PreviewAnalysisStatus
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
                runtime_resolver=lambda snapshot_id, digest: runtime,
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
                self.assertEqual("cancelled", cancelled["status"])
            finally:
                release.set()
                value.definition_previews._discover = original
                runner.join(timeout=15)
            # The accepted cancellation wins: no Preview was published.
            final = value.analyses.get(analysis_id)
            self.assertEqual(PreviewAnalysisStatus.CANCELLED, final.status)
            self.assertIsNone(final.preview_id)
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
                f"/operations/organize/preview/{settled.preview_id}",
                detail["previewPath"],
            )
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
