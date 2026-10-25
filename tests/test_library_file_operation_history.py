"""Durable ordinary-file-operation history of one library page (Task 46.2).

The read is exercised through the real application/API boundary over a
temporary SQLite runtime: work is admitted through the supported direct/
transfer/Delete commands, never seeded by inventing a production entry.
Covered: both library kinds, mixed populations and paging, kind/library/principal
isolation, invalid input, read failure, immutable origin after an Active change,
pre-change rows without display evidence, zero-mutation reads and reopening the
same durable database from a fresh repository/API.
"""

from __future__ import annotations

import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.direct_file_transfers import DirectFileTransferService
from mediaflow.application.files_transfer_worker import FilesTransferWorker
from mediaflow.domain.configuration_management import (
    ConfigurationDestinationPrecheckStatus,
    ConfigurationStorageCheckStatus,
    ConfigurationStrategyTestStatus,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_configuration_objects import example_document
from tests.test_direct_file_operations import MutationFreeStorage, request


class LibraryFileOperationHistoryTests(unittest.TestCase):
    """The library-owned ordinary work index on both page kinds."""

    # ------------------------------------------------------------------
    # Fixture
    # ------------------------------------------------------------------

    def _document(self, root: Path) -> dict[str, object]:
        document = example_document()
        document["persistence"]["databasePath"] = str(root / "configuration.sqlite3")
        document["storages"][0]["rootPath"] = str(root / "source")
        document["storages"][1]["rootPath"] = str(root / "target")
        document["resourceLibraries"][0]["storagePath"] = ""
        document["mediaLibraries"][0]["rootPath"] = "Movies"
        return document

    def _activate(self, root: Path, *, storage_adapters=None):
        document = self._document(root)
        (root / "source").mkdir(parents=True, exist_ok=True)
        (root / "target" / "Movies").mkdir(parents=True, exist_ok=True)
        configuration_repository = SQLiteConfigurationRepository(root / "configuration.sqlite3")
        self.addCleanup(configuration_repository.close)
        service = ManagedConfigurationService(
            configuration_repository,
            bootstrap_database_path=str(root / "configuration.sqlite3"),
        )
        objects = ConfigurationObjectService(
            service,
            storage_adapters=storage_adapters,
            storage_browser_cursor_secret="direct-files-test-secret",
        )
        draft = service.import_draft(document, actor="operator")
        validated = service.validate(draft.revision_id, actor="operator")
        for storage_id in ("source-storage", "media-target"):
            evidence = objects.storage_check(
                validated.revision_id,
                storage_id=storage_id,
                expected_version=validated.version,
                expected_digest=validated.digest,
                actor="operator",
            )
            self.assertEqual(evidence.status, ConfigurationStorageCheckStatus.PASSED)
        strategy = objects.recognition_strategy_test(
            validated.revision_id,
            expected_version=validated.version,
            expected_digest=validated.digest,
            actor="operator",
            resource_library_id="source",
            synthetic_path="Example.Movie.2024.1080p.mkv",
        )
        self.assertEqual(strategy.status, ConfigurationStrategyTestStatus.COMPLETED)
        destination = objects.destination_precheck(
            validated.revision_id,
            expected_version=validated.version,
            expected_digest=validated.digest,
            actor="operator",
            recognition_type="C",
            sample={
                "title": "The Matrix",
                "mediaType": "movie",
                "year": 1999,
                "genres": ["Action"],
                "extension": "mkv",
            },
        )
        self.assertEqual(destination.status, ConfigurationDestinationPrecheckStatus.COMPLETED)
        active = objects.activate_checked(
            validated.revision_id,
            expected_version=validated.version,
            actor="operator",
        )
        runtime_repository = SQLiteTaskRepository(root / "runtime.sqlite3")
        self.addCleanup(runtime_repository.close)
        api = MediaFlowApi(
            runtime_repository,
            None,
            principals=(
                ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ})),
            ),
            configuration_service=service,
            bootstrap_document=document,
            storage_adapters=storage_adapters,
            storage_browser_cursor_secret="direct-files-test-secret",
        )
        return api, objects, active, runtime_repository

    @staticmethod
    def _service(api, active):
        binding = api._prepare_runtime_binding_for_revision(active)
        return binding.direct_files

    # ------------------------------------------------------------------
    # Request helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _list(api, kind: str, library_id: str, *, query: str = "", token="admin-token"):
        base = "resource-libraries" if kind == "resource" else "media-libraries"
        suffix = f"?{query}" if query else ""
        return request(
            api,
            f"/api/v1/{base}/{library_id}/file-operations{suffix}",
            token=token,
        )

    @staticmethod
    def _detail(api, kind: str, library_id: str, task_id: str, *, token="admin-token"):
        base = "resource-libraries" if kind == "resource" else "media-libraries"
        return request(
            api,
            f"/api/v1/{base}/{library_id}/files/operations/{task_id}",
            token=token,
        )

    @staticmethod
    def _origin(api, task_id: str, *, token="admin-token"):
        return request(api, f"/api/v1/files/operation-origin/{task_id}", token=token)

    def _run_delete(self, case_service, **request_document):
        """Drive one confirmed Delete through the real durable Worker boundary."""

        admitted = case_service.execute_delete(**request_document)
        command = str(admitted["taskCommand"])
        transfer_service = DirectFileTransferService(
            direct_files=case_service, executor=case_service._executor
        )
        worker = FilesTransferWorker(
            None,
            case_service._tasks.repository,
            service_factory=lambda selected, _transfer: (
                transfer_service if selected == command else None
            ),
            supported_commands=(command,),
        )
        self.assertIsNotNone(worker.run_next())
        return case_service.delete_projection(str(admitted["taskId"]))

    # ------------------------------------------------------------------
    # Both kinds: real operations become readable history
    # ------------------------------------------------------------------

    def test_resource_and_media_histories_keep_their_own_operations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _runtime = self._activate(root)
            resource = self._service(api, active)
            media = api._prepare_runtime_binding_for_revision(active).direct_media_files
            self.assertIsNotNone(media)

            created = resource.create_directory(library_id="source", parent_path="", name="shows")
            text = resource.create_text(
                library_id="source", parent_path="", name="note.txt", content="hello"
            )
            media_created = media.create_directory(
                library_id="movies", parent_path="", name="shows"
            )
            self.assertNotEqual(created["taskId"], media_created["taskId"])

            code, page = self._list(api, "resource", "source")
            self.assertEqual(200, code, page)
            self.assertEqual(2, page["total"], page)
            self.assertEqual("resource", page["libraryKind"])
            self.assertEqual("resourceLibraryId", page["libraryIdField"])
            self.assertEqual("source", page["resourceLibraryId"])
            self.assertNotIn("mediaLibraryId", page)
            self.assertEqual("none", page["sideEffects"])
            self.assertEqual(
                {created["taskId"], text["taskId"]},
                {item["taskId"] for item in page["items"]},
            )
            by_id = {item["taskId"]: item for item in page["items"]}
            self.assertEqual("create_directory", by_id[created["taskId"]]["operation"])
            self.assertEqual("新建文件夹", by_id[created["taskId"]]["operationLabel"])
            # A bounded text creation is distinct from an in-place edit: the
            # durable display scope (directory → created entry) proves which.
            self.assertEqual("create_text", by_id[text["taskId"]]["operation"])
            self.assertEqual("新建文本文件", by_id[text["taskId"]]["operationLabel"])
            self.assertTrue(by_id[text["taskId"]]["allSucceeded"])
            self.assertTrue(by_id[text["taskId"]]["terminal"])
            self.assertIsNotNone(by_id[created["taskId"]]["sourceScope"])

            code, media_page = self._list(api, "media", "movies")
            self.assertEqual(200, code, media_page)
            self.assertEqual(1, media_page["total"], media_page)
            self.assertEqual("media", media_page["libraryKind"])
            self.assertEqual("movies", media_page["mediaLibraryId"])
            self.assertNotIn("resourceLibraryId", media_page)
            self.assertEqual(media_created["taskId"], media_page["items"][0]["taskId"])

    def test_same_ids_on_both_kinds_never_exchange_history_or_detail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _runtime = self._activate(root)
            resource = self._service(api, active)
            media = api._prepare_runtime_binding_for_revision(active).direct_media_files
            media_created = media.create_directory(
                library_id="movies", parent_path="", name="only-media"
            )
            resource_created = resource.create_directory(
                library_id="source", parent_path="", name="only-resource"
            )

            # A media Task never appears in a resource library's history, even
            # when asked for through the other kind's route.
            code, page = self._list(api, "resource", "movies")
            self.assertEqual(200, code, page)
            self.assertEqual(0, page["total"], page)
            code, page = self._list(api, "media", "source")
            self.assertEqual(200, code, page)
            self.assertEqual(0, page["total"], page)

            code, denied = self._detail(api, "resource", "source", media_created["taskId"])
            self.assertEqual(404, code, denied)
            code, denied = self._detail(api, "media", "movies", resource_created["taskId"])
            self.assertEqual(404, code, denied)
            code, found = self._detail(api, "media", "movies", media_created["taskId"])
            self.assertEqual(200, code, found)
            self.assertEqual(media_created["taskId"], found["taskId"])
            self.assertEqual("movies", found["mediaLibraryId"])

    def test_unknown_library_reads_as_empty_and_never_rebinds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _runtime = self._activate(root)
            resource = self._service(api, active)
            resource.create_directory(library_id="source", parent_path="", name="mine")
            code, page = self._list(api, "resource", "another-library")
            self.assertEqual(200, code, page)
            self.assertEqual(0, page["total"], page)
            self.assertEqual([], page["items"])
            self.assertEqual("none", page["sideEffects"])

    # ------------------------------------------------------------------
    # Mixed populations, paging and the exact scope
    # ------------------------------------------------------------------

    def test_mixed_populations_page_over_ordinary_work_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            resource = self._service(api, active)
            submissions = [
                resource.create_directory(library_id="source", parent_path="", name=name)
                for name in ("one", "two", "three")
            ]
            (root / "source" / "gone.txt").write_text("x", encoding="utf-8")
            digest = resource.delete_impact(library_id="source", paths=["gone.txt"]).scope_digest
            deleted = self._run_delete(
                resource,
                library_id="source",
                paths=["gone.txt"],
                confirmation_digest=digest,
            )
            self.assertEqual("SUCCESS", deleted["status"])

            # The unified run inventory of the same runtime also carries the
            # non-ordinary work (here a real admitted Organize Job).  It must
            # never leak into this library's ordinary population, and the
            # ordinary read must never narrow the shared inventory itself.
            from tests.test_configuration_objects import admit_organize_job

            organize_job_id, _organize_document = admit_organize_job(api)
            self.assertIsNotNone(organize_job_id)
            code, runs = request(api, "/api/v1/operations/runs?limit=100")
            self.assertEqual(200, code, runs)
            self.assertGreater(runs["total"], 4, runs)
            ordinary_commands = {
                "files_direct_command",
                "files_transfer",
                "files_delete",
            }

            code, page = self._list(api, "resource", "source", query="limit=2")
            self.assertEqual(200, code, page)
            self.assertEqual(4, page["total"], page)
            self.assertEqual(2, len(page["items"]))
            self.assertTrue(page["hasNext"])
            self.assertIsNotNone(page["nextCursor"])
            self.assertIsNone(page["previousCursor"])
            for item in page["items"]:
                self.assertIn(item["command"], ordinary_commands)

            collected = list(page["items"])
            cursor = page["nextCursor"]
            while cursor is not None:
                code, following = self._list(
                    api, "resource", "source", query=f"limit=2&cursor={cursor}"
                )
                self.assertEqual(200, code, following)
                self.assertEqual(4, following["total"], following)
                collected.extend(following["items"])
                cursor = following["nextCursor"]
            self.assertEqual(4, len(collected), collected)
            self.assertEqual(
                {submission["taskId"] for submission in submissions} | {deleted["taskId"]},
                {item["taskId"] for item in collected},
            )
            # A previous page can be read back from the second page's cursor.
            code, back = self._list(api, "resource", "source", query="limit=2")
            code, older = self._list(
                api, "resource", "source", query=f"limit=2&cursor={back['nextCursor']}"
            )
            self.assertTrue(older["hasPrevious"])
            code, first = self._list(
                api,
                "resource",
                "source",
                query=f"limit=2&cursor={older['previousCursor']}",
            )
            self.assertEqual(200, code, first)
            self.assertEqual(
                [item["taskId"] for item in back["items"]],
                [item["taskId"] for item in first["items"]],
            )

    def test_cursor_is_bound_to_kind_library_and_principal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _runtime = self._activate(root)
            resource = self._service(api, active)
            media = api._prepare_runtime_binding_for_revision(active).direct_media_files
            for name in ("a", "b", "c"):
                resource.create_directory(library_id="source", parent_path="", name=name)
            media.create_directory(library_id="movies", parent_path="", name="m")

            code, page = self._list(api, "resource", "source", query="limit=1")
            self.assertEqual(200, code, page)
            cursor = page["nextCursor"]
            self.assertIsNotNone(cursor)

            # The same cursor submitted to another kind, another library or by
            # another principal is refused as an invalid cursor, never rendered
            # as an empty or rebound page.
            for kind, library in (("media", "movies"), ("resource", "another-library")):
                code, refused = self._list(api, kind, library, query=f"limit=1&cursor={cursor}")
                self.assertEqual(400, code, refused)
            code, refused = self._list(
                api,
                "resource",
                "source",
                query=f"limit=1&cursor={cursor}",
                token="viewer-token",
            )
            self.assertEqual(400, code, refused)
            code, accepted = self._list(api, "resource", "source", query=f"limit=1&cursor={cursor}")
            self.assertEqual(200, code, accepted)
            self.assertNotEqual(
                [item["taskId"] for item in page["items"]],
                [item["taskId"] for item in accepted["items"]],
            )

    # ------------------------------------------------------------------
    # Invalid input and read failure
    # ------------------------------------------------------------------

    def test_invalid_query_fields_and_limits_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, _active, _runtime = self._activate(root)
            for query in (
                "limit=0",
                "limit=101",
                "limit=abc",
                "unknown=1",
                "limit=1&limit=2",
            ):
                code, refused = self._list(api, "resource", "source", query=query)
                self.assertEqual(400, code, (query, refused))
            code, refused = self._detail(api, "resource", "source", "  ")
            self.assertEqual(400, code, refused)
            code, refused = self._detail(api, "resource", "source", "missing-task")
            self.assertEqual(404, code, refused)
            self.assertEqual("library_file_operation_not_found", refused["error"]["code"])
            code, refused = self._origin(api, "missing-task")
            self.assertEqual(404, code, refused)

    def test_read_without_a_durable_history_reader_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, _active, runtime = self._activate(root)
            # A repository without the history window (an older or foreign
            # reader) answers with one bounded, actionable refusal instead of a
            # raw exception or a fabricated empty page.
            with unittest.mock.patch.object(
                runtime, "library_file_operations_window", None, create=True
            ):
                code, refused = self._list(api, "resource", "source")
            self.assertEqual(503, code, refused)
            self.assertEqual("library_file_operations_unavailable", refused["error"]["code"])
            self.assertEqual("none", refused["error"]["details"]["sideEffects"])
            self.assertTrue(refused["error"]["details"]["retrySafe"])

    def test_viewer_reads_history_and_a_read_mutates_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            resource = self._service(api, active)
            created = resource.create_directory(library_id="source", parent_path="", name="shared")
            code, page = self._list(api, "resource", "source", token="viewer-token")
            self.assertEqual(200, code, page)
            self.assertEqual(1, page["total"])
            code, found = self._detail(
                api, "resource", "source", created["taskId"], token="viewer-token"
            )
            self.assertEqual(200, code, found)
            # Reading history never mutates a Task, item or Result.
            before = runtime.get_task(created["taskId"])
            before_items = runtime.list_items(created["taskId"])
            before_results = runtime.list_results(created["taskId"])
            self._list(api, "resource", "source", token="viewer-token")
            self._detail(api, "resource", "source", created["taskId"], token="viewer-token")
            self._origin(api, created["taskId"], token="viewer-token")
            self.assertEqual(before, runtime.get_task(created["taskId"]))
            self.assertEqual(before_items, runtime.list_items(created["taskId"]))
            self.assertEqual(before_results, runtime.list_results(created["taskId"]))

    # ------------------------------------------------------------------
    # Immutable origin and pre-change rows
    # ------------------------------------------------------------------

    def test_history_survives_an_active_library_removal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _runtime = self._activate(root)
            resource = self._service(api, active)
            created = resource.create_directory(library_id="source", parent_path="", name="keep")
            code, before = self._list(api, "resource", "source")
            self.assertEqual(200, code, before)

            # A real successor Active that removes the library entirely: the
            # historical read keeps its durable origin, scope and result.
            configuration = api._configuration_service
            document = self._document(root)
            document["resourceLibraries"] = []
            draft = configuration.import_draft(document, actor="operator")
            validated = configuration.validate(draft.revision_id, actor="operator")
            configuration.activate(
                validated.revision_id, expected_version=validated.version, actor="operator"
            )
            code, after = self._list(api, "resource", "source")
            self.assertEqual(200, code, after)
            self.assertEqual(before["items"], after["items"])
            self.assertEqual(before["total"], after["total"])
            code, found = self._detail(api, "resource", "source", created["taskId"])
            self.assertEqual(200, code, found)
            code, resolved = self._origin(api, created["taskId"])
            self.assertEqual(200, code, resolved)
            self.assertTrue(resolved["matched"])
            self.assertEqual("source", resolved["resourceLibraryId"])

    def test_pre_change_rows_without_display_evidence_stay_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            resource = self._service(api, active)
            created = resource.create_directory(library_id="source", parent_path="", name="legacy")
            # A row admitted before the display evidence existed: the read must
            # present it truthfully (no scope invented) rather than hide it or
            # backfill from today's Active configuration.
            with runtime._lock, runtime._connection:
                runtime._connection.execute(
                    "DELETE FROM operations_run_display WHERE task_id = ?",
                    (created["taskId"],),
                )
            code, page = self._list(api, "resource", "source")
            self.assertEqual(200, code, page)
            self.assertEqual(1, page["total"], page)
            entry = page["items"][0]
            self.assertEqual(created["taskId"], entry["taskId"])
            self.assertIsNone(entry["sourceScope"])
            self.assertIsNone(entry["targetScope"])
            # The Task's own admitted operation Result still names the command.
            self.assertEqual("create_directory", entry["operation"])

    def test_history_reopens_from_a_fresh_repository_and_api(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, runtime = self._activate(root)
            resource = self._service(api, active)
            first = resource.create_directory(library_id="source", parent_path="", name="one")
            second = resource.create_text(
                library_id="source", parent_path="", name="two.txt", content="x"
            )
            code, before = self._list(api, "resource", "source")
            self.assertEqual(200, code, before)

            runtime.close()
            reopened = SQLiteTaskRepository(root / "runtime.sqlite3")
            self.addCleanup(reopened.close)
            # A process with no Active runtime binding at all: the durable read
            # still answers truthfully and mutates nothing.
            restarted = MediaFlowApi(
                reopened,
                None,
                principals=(
                    ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ})),
                    ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
                ),
            )
            code, after = self._list(restarted, "resource", "source")
            self.assertEqual(200, code, after)
            self.assertEqual(before["items"], after["items"])
            self.assertEqual(before["total"], after["total"])
            self.assertEqual(
                {first["taskId"], second["taskId"]},
                {item["taskId"] for item in after["items"]},
            )
            rendered = json.dumps(after)
            for forbidden in (str(root / "source"), "admin-token", "secret"):
                self.assertNotIn(forbidden, rendered)

    # ------------------------------------------------------------------
    # Deep-link resolution
    # ------------------------------------------------------------------

    def test_deep_link_resolves_to_the_exact_library_or_a_bounded_non_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api, _objects, active, _runtime = self._activate(root)
            resource = self._service(api, active)
            created = resource.create_directory(library_id="source", parent_path="", name="linked")

            code, resolved = self._origin(api, created["taskId"])
            self.assertEqual(200, code, resolved)
            self.assertTrue(resolved["matched"], resolved)
            self.assertEqual("source", resolved["resourceLibraryId"])
            self.assertEqual("resource", resolved["libraryKind"])
            self.assertEqual("none", resolved["sideEffects"])

            # The other kind's resolver refuses the resource Task instead of
            # guessing a MediaLibrary.
            history = api._library_file_operation_history(media_library=True)
            self.assertFalse(history.resolve(task_id=created["taskId"])["matched"])

    # ------------------------------------------------------------------
    # Zero mutation
    # ------------------------------------------------------------------

    def test_history_reads_never_touch_storage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapters = {
                "source-storage": MutationFreeStorage("source-storage"),
                "media-target": MutationFreeStorage("media-target"),
            }
            api, _objects, _active, _runtime = self._activate(root, storage_adapters=adapters)
            code, page = self._list(api, "resource", "source")
            self.assertEqual(200, code, page)
            self.assertEqual(0, page["total"])
            self.assertEqual("none", page["sideEffects"])
            for adapter in adapters.values():
                self.assertEqual([], adapter.mutations)
