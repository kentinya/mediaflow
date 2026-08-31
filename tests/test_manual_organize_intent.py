from __future__ import annotations

import io
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.domain.manual_organize import (
    ManualConfigurationSnapshot,
    ManualIntentError,
    ManualIntentItemStatus,
    ManualPolicyOption,
    ManualRecognitionOption,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import PersistentResultRecord
from mediaflow.infrastructure.memory_file_index import InMemoryFileIndexRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_file_catalog import NOW, file_record


def snapshot() -> ManualConfigurationSnapshot:
    return ManualConfigurationSnapshot(
        "active-1",
        "a" * 64,
        (
            ManualRecognitionOption("A", "Movie", "", "type-A", "A", "A", "A", "A"),
            ManualRecognitionOption("B", "TV", "", "type-B", "B", "B", "B", "B"),
            ManualRecognitionOption("C", "Special", "", "type-C", "C", "A", "A", "A"),
        ),
        (
            ManualPolicyOption("A", "Movie metadata", True, "tmdb", "movie"),
            ManualPolicyOption("B", "TV metadata", True, "tmdb", "tv"),
            ManualPolicyOption("C", "Special metadata", True, "tmdb", "movie"),
        ),
        (
            ManualPolicyOption("A", "Movie naming", True, media_type="movie"),
            ManualPolicyOption("B", "TV naming", True, media_type="tv"),
        ),
        (
            ManualPolicyOption("A", "Movie classification"),
            ManualPolicyOption("B", "TV classification"),
        ),
        (
            ManualPolicyOption("A", "Move", True, operation="move", conflict_strategy="manual"),
            ManualPolicyOption("B", "Copy", True, operation="copy", conflict_strategy="skip"),
        ),
    )


class ManualOrganizeIntentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.index = InMemoryFileIndexRepository()
        self.index.batch_upsert(
            (
                file_record("one", "source", "library", "Movies/one.mkv"),
                file_record("two", "source", "library", "Movies/two.mkv"),
                file_record("three", "source", "library", "Movies/three.mkv"),
            )
        )
        self.catalog = FileCatalogService(self.index, ("library",), ("source",))
        self.snapshot = snapshot()

    def _service(self, repository):
        self.catalog = FileCatalogService(
            self.index, ("library",), ("source",), task_repository=repository
        )
        return ManualOrganizeIntentService(
            repository,
            self.catalog,
            configuration_resolver=lambda: self.snapshot,
        )

    def test_single_and_bounded_batch_are_durable_and_type_c_keeps_a_downstream(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                repository.append_result(
                    PersistentResultRecord(
                        "result-c",
                        "task-c",
                        "item-c",
                        "source",
                        "Movies/one.mkv",
                        None,
                        None,
                        "C",
                        "tmdb",
                        "603",
                        "C",
                        "A",
                        "A",
                        "A",
                        "move",
                        "dry_run",
                        NOW,
                        title="The Matrix",
                    )
                )
                intent = self._service(repository).create(["one", "two"], actor=" operator ")
                self.assertEqual(intent.actor, "operator")
                self.assertEqual(intent.snapshot_id, "active-1")
                self.assertEqual([item.position for item in intent.items], [0, 1])
                self.assertEqual(intent.items[0].choice.recognition_type_id, "C")
                self.assertEqual(intent.items[0].choice.naming_policy_id, "A")
                self.assertEqual(intent.items[0].choice.classification_policy_id, "A")
                self.assertEqual(intent.items[0].choice.organize_policy_id, "A")
                reopened = self._service(repository).get(intent.intent_id)
                self.assertEqual([item.source.file_id for item in reopened.items], ["one", "two"])
                self.assertEqual(len(reopened.audit), 1)

    def test_invalid_selection_is_all_or_nothing_and_source_state_is_exact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = self._service(repository)
                for values, code in (
                    (["one", "missing"], "source_missing"),
                    (["one", "one"], "duplicate_selection"),
                ):
                    with self.subTest(values=values):
                        with self.assertRaises(ManualIntentError) as raised:
                            service.create(values, actor="operator")
                        self.assertEqual(raised.exception.code, code)
                self.assertEqual(repository.list_manual_intents(), ())
                self.index.batch_upsert(
                    (
                        file_record(
                            "bad", "source", "library", "Movies/bad.mkv", scan_status="missing"
                        ),
                    )
                )
                with self.assertRaises(ManualIntentError) as raised:
                    service.create(["bad"], actor="operator")
                self.assertEqual(raised.exception.code, "source_stale")
                with self.assertRaises(ManualIntentError) as raised:
                    service.create([f"file-{index}" for index in range(101)], actor="operator")
                self.assertEqual(raised.exception.code, "selection_over_limit")

    def test_choice_validation_and_concurrency_preserve_prior_and_siblings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = self._service(repository)
                intent = service.create(["one", "two"], actor="operator")
                first, second = intent.items
                with self.assertRaises(ManualIntentError) as raised:
                    service.update_choice(
                        intent.intent_id,
                        first.item_id,
                        {"recognitionTypeId": "B", "namingPolicyId": "A"},
                        expected_version=1,
                        actor="operator",
                    )
                self.assertEqual(raised.exception.code, "incompatible_choice")
                unchanged = service.get(intent.intent_id)
                self.assertEqual(unchanged.version, 1)
                self.assertEqual(unchanged.items[1].version, second.version)
                updated = service.update_choice(
                    intent.intent_id,
                    first.item_id,
                    {
                        "recognitionTypeId": "C",
                        "metadata": {
                            "provider": "tmdb",
                            "providerId": "603",
                            "mediaType": "movie",
                            "title": "The Matrix",
                            "year": 1999,
                        },
                        "namingPolicyId": "A",
                        "classificationPolicyId": "A",
                        "organizePolicyId": "A",
                    },
                    expected_version=1,
                    actor="operator",
                )
                self.assertEqual(updated.version, 2)
                self.assertEqual(updated.items[0].choice.recognition_type_id, "C")
                self.assertEqual(len(updated.audit), 2)
                with self.assertRaises(ManualIntentError) as raised:
                    service.update_choice(
                        intent.intent_id,
                        second.item_id,
                        {"recognitionTypeId": "A"},
                        expected_version=1,
                        actor="operator",
                    )
                self.assertEqual(raised.exception.status, 409)
                current = service.get(intent.intent_id)
                self.assertEqual(current.version, 2)
                self.assertEqual(current.items[1].version, 1)

    def test_snapshot_cross_binding_disabled_and_malformed_choices_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                service = self._service(repository)
                intent = service.create(["one"], actor="operator")
                item = intent.items[0]
                for patch in (
                    {"snapshotId": "later"},
                    {"snapshotDigest": "b" * 64},
                    {"metadata": {"provider": "tmdb", "providerId": "1", "mediaType": "tv"}},
                    {"rawProviderPayload": {"secret": "nope"}},
                    {"organizePolicyId": "not-configured"},
                ):
                    with self.subTest(patch=patch):
                        kwargs = {
                            "snapshot_id": patch.pop("snapshotId", None),
                            "snapshot_digest": patch.pop("snapshotDigest", None),
                        }
                        with self.assertRaises(ManualIntentError):
                            service.update_choice(
                                intent.intent_id,
                                item.item_id,
                                patch,
                                expected_version=1,
                                actor="operator",
                                **kwargs,
                            )
                self.assertEqual(service.get(intent.intent_id).version, 1)

    def test_json_bootstrap_and_disabled_policy_options_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                bootstrap_service = ManualOrganizeIntentService(
                    repository,
                    self.catalog,
                    configuration_resolver=lambda: self.snapshot.document(),
                )
                with self.assertRaises(ManualIntentError) as raised:
                    bootstrap_service.create(["one"], actor="operator")
                self.assertEqual(raised.exception.code, "manual_intent_configuration_unavailable")
                self.assertEqual(repository.list_manual_intents(), ())

                disabled = replace(
                    self.snapshot,
                    metadata_policies=(
                        self.snapshot.metadata_policies[0],
                        replace(self.snapshot.metadata_policies[1], enabled=False),
                        self.snapshot.metadata_policies[2],
                    ),
                )
                service = self._service(repository)
                service._configuration_resolver = lambda: disabled
                intent = service.create(["one"], actor="operator")
                with self.assertRaises(ManualIntentError) as raised:
                    service.update_choice(
                        intent.intent_id,
                        intent.items[0].item_id,
                        {
                            "recognitionTypeId": "B",
                            "namingPolicyId": "B",
                            "classificationPolicyId": "B",
                            "organizePolicyId": "B",
                        },
                        expected_version=1,
                        actor="operator",
                    )
                self.assertIn(raised.exception.code, {"choice_disabled", "incompatible_choice"})
                self.assertEqual(service.get(intent.intent_id).version, 1)

    def test_cancel_and_restart_preserve_independent_status_and_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                intent = self._service(repository).create(["one", "two"], actor="operator")
                cancelled = self._service(repository).cancel(
                    intent.intent_id, expected_version=1, actor="operator"
                )
                self.assertEqual(cancelled.status.value, "cancelled")
                self.assertTrue(
                    all(item.status is ManualIntentItemStatus.CANCELLED for item in cancelled.items)
                )
                self.assertEqual(len(cancelled.audit), 2)
            with SQLiteTaskRepository(database) as reopened:
                value = self._service(reopened).get(intent.intent_id)
                self.assertEqual(value.status.value, "cancelled")
                self.assertEqual([item.position for item in value.items], [0, 1])

    def test_api_rbac_projection_and_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                manual = self._service(repository)
                viewer = ResolvedApiPrincipal(
                    "viewer", "viewer-token", frozenset({ApiPermission.READ})
                )
                operator = ResolvedApiPrincipal(
                    "operator",
                    "operator-token",
                    frozenset({ApiPermission.READ, ApiPermission.SUBMIT_DRY_RUN}),
                )
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(viewer, operator),
                    file_catalog=self.catalog,
                    manual_intent_service=manual,
                )
                status, denied = request(
                    api,
                    "/api/v1/manual-intents",
                    method="POST",
                    body={"fileIds": ["one"]},
                    token="viewer-token",
                )
                self.assertEqual(status, 403)
                status, created = request(
                    api,
                    "/api/v1/manual-intents",
                    method="POST",
                    body={"fileIds": ["one"]},
                    token="operator-token",
                )
                self.assertEqual(status, 201)
                self.assertEqual(created["sideEffects"], "none")
                status, listed = request(
                    api, "/api/v1/manual-intents?limit=10", token="viewer-token"
                )
                self.assertEqual(status, 200)
                self.assertEqual(len(listed["items"]), 1)
                status, conflict = request(
                    api,
                    f"/api/v1/manual-intents/{created['intentId']}/items/{created['items'][0]['itemId']}/choice",
                    method="PUT",
                    body={"expectedVersion": 1, "recognitionTypeId": "missing"},
                    token="operator-token",
                )
                self.assertEqual(status, 400)
                self.assertEqual(conflict["error"]["details"]["sideEffects"], "none")


def request(api, path: str, *, method="GET", body=None, token="operator-token"):
    payload = json.dumps(body).encode("utf-8") if body is not None else b""
    statuses = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path.split("?", 1)[0],
        "QUERY_STRING": path.split("?", 1)[1] if "?" in path else "",
        "CONTENT_LENGTH": str(len(payload)),
        "wsgi.input": io.BytesIO(payload),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}" if token else "",
    }
    value = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(value)


if __name__ == "__main__":
    unittest.main()
