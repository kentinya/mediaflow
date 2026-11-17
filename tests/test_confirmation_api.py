from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from threading import Barrier, Thread
from unittest.mock import patch

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.conflict_resolution import ConfirmationService
from mediaflow.application.task_runtime import PersistentTaskCoordinator
from mediaflow.domain.organizer import (
    Conflict,
    ConflictStrategy,
    ConflictType,
    OrganizeOperationType,
    OrganizePlan,
    OrganizePolicy,
    PlanOperation,
    PlanStatus,
    StorageLocation,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import ConfirmationStatus, TaskItemStatus
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi


def api_principals() -> tuple[ResolvedApiPrincipal, ...]:
    return (
        ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ})),
        ResolvedApiPrincipal(
            "operator",
            "operator-token",
            frozenset(
                {
                    ApiPermission.READ,
                    ApiPermission.SUBMIT_DRY_RUN,
                    ApiPermission.CANCEL_JOB,
                    ApiPermission.RESOLVE_CONFIRMATION,
                }
            ),
        ),
        ResolvedApiPrincipal(
            "executor",
            "executor-token",
            frozenset(
                {
                    ApiPermission.READ,
                    ApiPermission.SUBMIT_DRY_RUN,
                    ApiPermission.CANCEL_JOB,
                    ApiPermission.RESOLVE_CONFIRMATION,
                }
            ),
        ),
        ResolvedApiPrincipal(
            "auditor",
            "auditor-token",
            frozenset({ApiPermission.READ, ApiPermission.READ_SECURITY_AUDIT}),
        ),
        ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission)),
    )


def request(api, method: str, path: str, *, token=None, query="", document=None):
    body = b"" if document is None else json.dumps(document).encode()
    statuses = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(body)),
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(body),
    }
    if token:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    response = b"".join(api(environ, lambda value, headers: statuses.append(value)))
    return int(statuses[0].split()[0]), json.loads(response)


def plan(number: int) -> OrganizePlan:
    source = f"Incoming/Film-{number}.mkv"
    target = f"Movies/Film-{number}/Film-{number}.mkv"
    return OrganizePlan(
        "source",
        "target",
        source,
        target,
        "C",
        "A",
        "A",
        "A",
        operation=PlanOperation.MOVE,
        conflicts=(Conflict(ConflictType.DESTINATION_EXISTS, source, target, "test"),),
        status=PlanStatus.CONFLICT,
        plan_id=f"plan-{number}",
        media_library_root="Movies",
        relative_destination=f"Film-{number}/Film-{number}.mkv",
        source_location=StorageLocation("source", source),
        destination_location=StorageLocation("target", target),
    )


def create_confirmation(repository: SQLiteTaskRepository, revision, number: int):
    coordinator = PersistentTaskCoordinator(repository, repository)
    task = coordinator.create(
        "organize",
        execute_authorized=False,
        configuration_snapshot_id=revision.revision_id,
        configuration_snapshot_digest=revision.digest,
    )
    item = coordinator.begin_item(
        task.task_id,
        "source",
        "movies",
        f"Incoming/Film-{number}.mkv",
        f"Film-{number}.mkv",
    )
    coordinator.wait_for_confirmation(
        item,
        plan(number),
        OrganizePolicy("A", OrganizeOperationType.MOVE, ConflictStrategy.MANUAL),
    )
    return repository.list_confirmations()[-1], item


def managed_authority(directory: str):
    database = Path(directory, "runtime.sqlite3")
    document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
    document["persistence"] = {"databasePath": str(database)}
    configuration_repository = SQLiteConfigurationRepository(database)
    service = ManagedConfigurationService(
        configuration_repository,
        bootstrap_database_path=str(database),
        bootstrap_document=document,
    )
    draft = service.import_draft(document, actor="tester")
    validated = service.validate(draft.revision_id, actor="tester")
    if validated.status.value != "validated":
        raise AssertionError(validated.validation_errors)
    revision = service.activate(
        validated.revision_id,
        expected_version=validated.version,
        actor="tester",
    )
    return configuration_repository, service, revision


class ConfirmationApiTests(unittest.TestCase):
    def test_current_task_recovery_decision_carries_rbac_and_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            configuration_repository, managed, revision = managed_authority(directory)
            try:
                with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                    first, first_item = create_confirmation(repository, revision, 1)
                    second, second_item = create_confirmation(repository, revision, 2)
                    api = MediaFlowApi(
                        repository,
                        principals=api_principals(),
                        configuration_service=managed,
                    )

                    status, detail = request(
                        api,
                        "GET",
                        f"/api/v1/tasks/{second.task_id}/items/{second_item.item_id}/recovery",
                        token="operator-token",
                    )
                    self.assertEqual(status, 200, detail)
                    self.assertEqual("conflict", detail["decision"]["kind"])
                    checkpoint = detail["checkpoint"]["checkpoint_version"]

                    for role in ("viewer", "auditor"):
                        with self.subTest(role=role):
                            status, denied = request(
                                api,
                                "POST",
                                f"/api/v1/tasks/{second.task_id}/items/"
                                f"{second_item.item_id}/recovery/decision",
                                token=f"{role}-token",
                                document={
                                    "kind": "conflict",
                                    "expectedCheckpointVersion": checkpoint,
                                    "strategy": "skip",
                                },
                            )
                            self.assertEqual(403, status, denied)

                    status, resolved = request(
                        api,
                        "POST",
                        f"/api/v1/tasks/{second.task_id}/items/"
                        f"{second_item.item_id}/recovery/decision",
                        token="operator-token",
                        document={
                            "kind": "conflict",
                            "expectedCheckpointVersion": checkpoint,
                            "strategy": "skip",
                            "note": "credential=super-secret",
                        },
                    )
                    self.assertEqual(200, status, resolved)
                    self.assertEqual("operator", resolved["decision_result"]["actor"])
                    self.assertIs(
                        repository.get_item(second_item.item_id).status,
                        TaskItemStatus.SKIPPED,
                    )
                    audit = repository.list_confirmation_audit(second.confirmation_id)
                    self.assertEqual((len(audit), audit[0].actor), (1, "operator"))
                    self.assertNotIn("super-secret", repr(repository.list_security_audit(limit=50)))
                    self.assertEqual(0, repository.count_scheduled_capacity_use())

                    # A different exact reviewed decision keeps its own
                    # optimistic checkpoint and is not borrowed from the sibling.
                    status, reopened = request(
                        api,
                        "GET",
                        f"/api/v1/tasks/{first.task_id}/items/{first_item.item_id}/recovery",
                        token="operator-token",
                    )
                    self.assertEqual(200, status, reopened)
                    self.assertEqual("pending", reopened["decision"]["status"])
                    status, first_resolved = request(
                        api,
                        "POST",
                        f"/api/v1/tasks/{first.task_id}/items/{first_item.item_id}/recovery/decision",
                        token="operator-token",
                        document={
                            "kind": "conflict",
                            "expectedCheckpointVersion": reopened["checkpoint"][
                                "checkpoint_version"
                            ],
                            "strategy": "skip",
                        },
                    )
                    self.assertEqual(200, status, first_resolved)
                    self.assertIs(
                        repository.get_item(first_item.item_id).status,
                        TaskItemStatus.SKIPPED,
                    )
            finally:
                configuration_repository.close()

    def test_retired_global_review_and_manual_routes_are_not_registered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            configuration_repository, managed, revision = managed_authority(directory)
            try:
                with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                    confirmation, _ = create_confirmation(repository, revision, 1)
                    api = MediaFlowApi(
                        repository,
                        principals=api_principals(),
                        configuration_service=managed,
                    )
                    routes = (
                        ("GET", "/api/v1/confirmations", None, ""),
                        (
                            "GET",
                            f"/api/v1/confirmations/{confirmation.confirmation_id}",
                            None,
                            "",
                        ),
                        (
                            "POST",
                            f"/api/v1/confirmations/{confirmation.confirmation_id}/resolve",
                            {"strategy": "skip"},
                            "",
                        ),
                        (
                            "GET",
                            f"/api/v1/confirmations/{confirmation.confirmation_id}/audit",
                            None,
                            "",
                        ),
                        ("GET", "/api/v1/recognition-reviews", None, ""),
                        ("GET", "/api/v1/metadata-reviews", None, ""),
                        ("GET", "/api/v1/metadata-corrections", None, ""),
                        ("GET", "/api/v1/classification-reviews", None, ""),
                        ("GET", "/api/v1/manual-intents", None, ""),
                        ("GET", "/api/v1/manual-previews", None, ""),
                        ("GET", "/api/v1/manual-executions", None, ""),
                        (
                            "POST",
                            "/api/v1/manual-recovery-preparations/preparation/confirm",
                            {"itemIds": ["x"], "confirmation": True},
                            "",
                        ),
                        ("GET", "/api/v1/files/file-1/previews", None, "resourceLibrary=library"),
                        (
                            "POST",
                            "/api/v1/files/file-1/manual-intent",
                            {},
                            "",
                        ),
                        (
                            "GET",
                            "/api/v1/resource-libraries/library/previews",
                            None,
                            "",
                        ),
                    )
                    for method, path, document, query in routes:
                        with self.subTest(path=path):
                            status, response = request(
                                api,
                                method,
                                path,
                                token="admin-token",
                                document=document,
                                query=query,
                            )
                            self.assertEqual(404, status, response)
                            self.assertEqual("not_found", response["error"]["code"])
                    self.assertIs(
                        repository.get_item(repository.list_confirmations()[0].item_id).status,
                        TaskItemStatus.WAITING_CONFIRM,
                    )
            finally:
                configuration_repository.close()

    def test_invalid_current_decision_fields_are_rejected_and_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            configuration_repository, managed, revision = managed_authority(directory)
            try:
                with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                    api = MediaFlowApi(
                        repository,
                        principals=api_principals(),
                        configuration_service=managed,
                    )
                    for number, document in enumerate(
                        (
                            {"kind": "conflict", "strategy": "manual"},
                            {"kind": "conflict", "strategy": "skip", "actor": "attacker"},
                            {"kind": "conflict", "strategy": "skip", "execute": True},
                            {
                                "kind": "conflict",
                                "strategy": "skip",
                                "executionToken": "super-secret",
                            },
                        ),
                        1,
                    ):
                        confirmation, item = create_confirmation(repository, revision, number)
                        status, detail = request(
                            api,
                            "GET",
                            f"/api/v1/tasks/{confirmation.task_id}/items/{item.item_id}/recovery",
                            token="operator-token",
                        )
                        self.assertEqual(200, status, detail)
                        payload = {
                            **document,
                            "expectedCheckpointVersion": detail["checkpoint"]["checkpoint_version"],
                        }
                        status, refused = request(
                            api,
                            "POST",
                            f"/api/v1/tasks/{confirmation.task_id}/items/"
                            f"{item.item_id}/recovery/decision",
                            token="operator-token",
                            document=payload,
                        )
                        self.assertIn(status, (400, 409), refused)
                        self.assertIs(
                            repository.get_confirmation(confirmation.confirmation_id).status,
                            ConfirmationStatus.PENDING,
                        )
                        self.assertIs(
                            repository.get_item(item.item_id).status,
                            TaskItemStatus.WAITING_CONFIRM,
                        )
                    security_audit = repr(repository.list_security_audit(limit=100))
                    self.assertNotIn("super-secret", security_audit)
                    self.assertNotIn("attacker", security_audit)
            finally:
                configuration_repository.close()

    def test_concurrent_resolution_succeeds_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            configuration_repository, _managed, revision = managed_authority(directory)
            try:
                database = Path(directory, "runtime.sqlite3")
                with SQLiteTaskRepository(database) as repository:
                    confirmation, item = create_confirmation(repository, revision, 1)
                barrier = Barrier(2)
                outcomes = []

                def resolve(actor: str) -> None:
                    with SQLiteTaskRepository(database) as repository:
                        barrier.wait()
                        try:
                            ConfirmationService(repository).resolve(
                                confirmation.confirmation_id,
                                ConflictStrategy.SKIP,
                                actor=actor,
                            )
                            outcomes.append("resolved")
                        except ValueError:
                            outcomes.append("rejected")

                workers = [
                    Thread(target=resolve, args=(f"operator-{value}",)) for value in range(2)
                ]
                for worker in workers:
                    worker.start()
                for worker in workers:
                    worker.join()
                with SQLiteTaskRepository(database) as repository:
                    self.assertEqual(sorted(outcomes), ["rejected", "resolved"])
                    self.assertEqual(
                        len(repository.list_confirmation_audit(confirmation.confirmation_id)), 1
                    )
                    self.assertIs(repository.get_item(item.item_id).status, TaskItemStatus.SKIPPED)
            finally:
                configuration_repository.close()

    def test_audit_insert_failure_rolls_back_confirmation_and_item(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            configuration_repository, _managed, revision = managed_authority(directory)
            try:
                database = Path(directory, "runtime.sqlite3")
                with SQLiteTaskRepository(database) as repository:
                    confirmation, item = create_confirmation(repository, revision, 1)
                connection = sqlite3.connect(database)
                connection.execute(
                    """CREATE TRIGGER reject_confirmation_audit BEFORE INSERT
                    ON conflict_decision_audit BEGIN SELECT RAISE(ABORT, 'injected'); END"""
                )
                connection.commit()
                connection.close()
                with SQLiteTaskRepository(database) as repository:
                    with self.assertRaises(sqlite3.IntegrityError):
                        ConfirmationService(repository).resolve(
                            confirmation.confirmation_id,
                            ConflictStrategy.SKIP,
                            actor="operator",
                        )
                    self.assertIs(
                        repository.get_confirmation(confirmation.confirmation_id).status,
                        ConfirmationStatus.PENDING,
                    )
                    self.assertIs(
                        repository.get_item(item.item_id).status,
                        TaskItemStatus.WAITING_CONFIRM,
                    )
                    self.assertEqual(
                        repository.list_confirmation_audit(confirmation.confirmation_id), ()
                    )
            finally:
                configuration_repository.close()

    def test_current_decision_does_not_construct_storage_or_execute_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            configuration_repository, managed, revision = managed_authority(directory)
            try:
                with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                    confirmation, item = create_confirmation(repository, revision, 1)
                    api = MediaFlowApi(
                        repository,
                        principals=api_principals(),
                        configuration_service=managed,
                    )
                    status, detail = request(
                        api,
                        "GET",
                        f"/api/v1/tasks/{confirmation.task_id}/items/{item.item_id}/recovery",
                        token="operator-token",
                    )
                    self.assertEqual(200, status, detail)
                    with patch(
                        "mediaflow.application.organizer.OrganizerExecutor.execute",
                        side_effect=AssertionError("conflict decision executed OrganizerExecutor"),
                    ):
                        status, resolved = request(
                            api,
                            "POST",
                            f"/api/v1/tasks/{confirmation.task_id}/items/"
                            f"{item.item_id}/recovery/decision",
                            token="operator-token",
                            document={
                                "kind": "conflict",
                                "expectedCheckpointVersion": detail["checkpoint"][
                                    "checkpoint_version"
                                ],
                                "strategy": "skip",
                            },
                        )
                    self.assertEqual(200, status, resolved)
                    self.assertEqual(0, repository.count_scheduled_capacity_use())
            finally:
                configuration_repository.close()


if __name__ == "__main__":
    unittest.main()
