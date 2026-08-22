from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from threading import Barrier, Thread
from unittest.mock import patch

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
                    ApiPermission.REMOTE_EXECUTE,
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


def create_confirmation(repository: SQLiteTaskRepository, number: int):
    coordinator = PersistentTaskCoordinator(repository, repository)
    task = coordinator.create("preview", execute_authorized=False)
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


class ConfirmationApiTests(unittest.TestCase):
    def test_read_list_show_audit_query_and_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                first, _ = create_confirmation(repository, 1)
                second, _ = create_confirmation(repository, 2)
                ConfirmationService(repository).resolve(
                    first.confirmation_id,
                    ConflictStrategy.SKIP,
                    actor="local",
                    note="credential=super-secret",
                )
                api = MediaFlowApi(repository, None, principals=api_principals())

                self.assertEqual(request(api, "GET", "/api/v1/confirmations")[0], 401)
                for role in ("viewer", "auditor", "operator", "executor", "admin"):
                    with self.subTest(role=role):
                        self.assertEqual(
                            request(
                                api,
                                "GET",
                                "/api/v1/confirmations",
                                token=f"{role}-token",
                            )[0],
                            200,
                        )
                status, pending = request(
                    api,
                    "GET",
                    "/api/v1/confirmations",
                    token="viewer-token",
                    query="status=pending&limit=1",
                )
                self.assertEqual(status, 200)
                self.assertEqual(
                    [item["confirmation_id"] for item in pending["items"]], [second.confirmation_id]
                )
                resolved = request(
                    api,
                    "GET",
                    "/api/v1/confirmations",
                    token="viewer-token",
                    query="status=resolved&limit=10",
                )[1]
                self.assertEqual(resolved["items"][0]["confirmation_id"], first.confirmation_id)
                shown = request(
                    api,
                    "GET",
                    f"/api/v1/confirmations/{first.confirmation_id}",
                    token="viewer-token",
                )[1]
                self.assertEqual(shown["status"], "resolved")
                self.assertNotIn("note", shown)
                audit = request(
                    api,
                    "GET",
                    f"/api/v1/confirmations/{first.confirmation_id}/audit",
                    token="auditor-token",
                )[1]
                self.assertEqual(audit["items"][0]["actor"], "local")
                self.assertNotIn("note", audit["items"][0])
                self.assertNotIn("super-secret", repr(audit))
                for query in ("status=bad", "limit=0", "limit=101", "secret=value"):
                    self.assertEqual(
                        request(
                            api,
                            "GET",
                            "/api/v1/confirmations",
                            token="viewer-token",
                            query=query,
                        )[0],
                        400,
                    )
                self.assertEqual(
                    request(
                        api,
                        "GET",
                        "/api/v1/confirmations/unknown",
                        token="viewer-token",
                    )[0],
                    404,
                )

    def test_remote_skip_rename_permissions_atomic_transition_and_no_job(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                api = MediaFlowApi(repository, None, principals=api_principals())
                for number, role, strategy, expected in (
                    (1, "operator", "skip", TaskItemStatus.SKIPPED),
                    (2, "executor", "rename", TaskItemStatus.PENDING),
                    (3, "admin", "skip", TaskItemStatus.SKIPPED),
                ):
                    confirmation, item = create_confirmation(repository, number)
                    status, resolved = request(
                        api,
                        "POST",
                        f"/api/v1/confirmations/{confirmation.confirmation_id}/resolve",
                        token=f"{role}-token",
                        document={"strategy": strategy},
                    )
                    self.assertEqual(status, 200)
                    self.assertEqual(resolved["actor"], role)
                    self.assertEqual(repository.get_item(item.item_id).status, expected)
                    audit = repository.list_confirmation_audit(confirmation.confirmation_id)
                    self.assertEqual((len(audit), audit[0].actor), (1, role))
                confirmation, _ = create_confirmation(repository, 4)
                for role in ("viewer", "auditor"):
                    self.assertEqual(
                        request(
                            api,
                            "POST",
                            f"/api/v1/confirmations/{confirmation.confirmation_id}/resolve",
                            token=f"{role}-token",
                            document={"strategy": "skip"},
                        )[0],
                        403,
                    )
                self.assertEqual(repository.list_jobs(), ())

    def test_remote_high_risk_and_injected_fields_are_rejected_and_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                api = MediaFlowApi(repository, None, principals=api_principals())
                forbidden_documents = (
                    {"strategy": "manual"},
                    {"strategy": "overwrite"},
                    {"strategy": "skip", "actor": "attacker"},
                    {"strategy": "rename", "proposedDestinationPath": "../escape"},
                    {"strategy": "skip", "execute": True},
                    {"strategy": "skip", "executionToken": "super-secret"},
                )
                for number, document in enumerate(forbidden_documents, 1):
                    confirmation, item = create_confirmation(repository, number)
                    for role in ("operator", "executor", "admin"):
                        with self.subTest(document=document, role=role):
                            self.assertEqual(
                                request(
                                    api,
                                    "POST",
                                    f"/api/v1/confirmations/{confirmation.confirmation_id}/resolve",
                                    token=f"{role}-token",
                                    document=document,
                                )[0],
                                400,
                            )
                    self.assertEqual(
                        repository.get_confirmation(confirmation.confirmation_id).status,
                        ConfirmationStatus.PENDING,
                    )
                    self.assertEqual(
                        repository.get_item(item.item_id).status, TaskItemStatus.WAITING_CONFIRM
                    )
                security_audit = repr(repository.list_security_audit(limit=100))
                self.assertNotIn("super-secret", security_audit)
                self.assertNotIn("escape", security_audit)
                self.assertTrue(
                    any(
                        value.route == "/api/v1/confirmations/{id}/resolve"
                        for value in repository.list_security_audit(limit=100)
                    )
                )

    def test_concurrent_resolution_succeeds_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                confirmation, item = create_confirmation(repository, 1)
            barrier = Barrier(2)
            outcomes = []

            def resolve(actor: str) -> None:
                with SQLiteTaskRepository(database) as repository:
                    barrier.wait()
                    try:
                        ConfirmationService(repository).resolve(
                            confirmation.confirmation_id, ConflictStrategy.SKIP, actor=actor
                        )
                        outcomes.append("resolved")
                    except ValueError:
                        outcomes.append("rejected")

            workers = [Thread(target=resolve, args=(f"operator-{value}",)) for value in range(2)]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join()
            with SQLiteTaskRepository(database) as repository:
                self.assertEqual(sorted(outcomes), ["rejected", "resolved"])
                self.assertEqual(
                    len(repository.list_confirmation_audit(confirmation.confirmation_id)), 1
                )
                self.assertEqual(repository.get_item(item.item_id).status, TaskItemStatus.SKIPPED)

    def test_audit_insert_failure_rolls_back_confirmation_and_item(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, "runtime.sqlite3")
            with SQLiteTaskRepository(database) as repository:
                confirmation, item = create_confirmation(repository, 1)
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
                        confirmation.confirmation_id, ConflictStrategy.SKIP, actor="operator"
                    )
                self.assertEqual(
                    repository.get_confirmation(confirmation.confirmation_id).status,
                    ConfirmationStatus.PENDING,
                )
                self.assertEqual(
                    repository.get_item(item.item_id).status, TaskItemStatus.WAITING_CONFIRM
                )
                self.assertEqual(
                    repository.list_confirmation_audit(confirmation.confirmation_id), ()
                )

    def test_api_does_not_construct_storage_or_execute_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
                confirmation, _ = create_confirmation(repository, 1)
                api = MediaFlowApi(repository, None, principals=api_principals())
                with patch(
                    "mediaflow.application.organizer.OrganizerExecutor.execute",
                    side_effect=AssertionError("confirmation API executed OrganizerExecutor"),
                ):
                    self.assertEqual(
                        request(
                            api,
                            "POST",
                            f"/api/v1/confirmations/{confirmation.confirmation_id}/resolve",
                            token="operator-token",
                            document={"strategy": "skip"},
                        )[0],
                        200,
                    )
                self.assertEqual(repository.list_jobs(), ())
