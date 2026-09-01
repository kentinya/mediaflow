from __future__ import annotations

import io
import json
import tempfile
import unittest
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Event, Lock, Thread
from unittest.mock import patch
from uuid import uuid4

from mediaflow.application.file_catalog import FileCatalogService
from mediaflow.application.manual_organize import ManualOrganizeIntentService
from mediaflow.application.manual_organize_execution import (
    ManualOrganizeExecutionService,
)
from mediaflow.application.manual_organize_preview import ManualOrganizePreviewService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.organizer import OrganizerExecutor
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.application.strategy_test import SyntheticMetadataProvider
from mediaflow.domain.library import MediaLibrary, ResourceLibrary
from mediaflow.domain.manual_execution import ManualExecutionError
from mediaflow.domain.manual_organize_preview import (
    ManualPreviewItemStatus,
)
from mediaflow.domain.manual_safety import redact_manual_text
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.organizer import (
    AttachmentPolicy,
    ConflictStrategy,
    DirectoryCleanupMode,
    DirectoryCleanupPolicy,
    ExecutionEffectCertainty,
    ExecutionResult,
    ExecutionStatus,
    OrganizeOperationType,
    RollbackPolicy,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.task_persistence import (
    ConfirmationStatus,
    ConflictConfirmation,
)
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.memory_file_index import InMemoryFileIndexRepository
from mediaflow.infrastructure.runtime_configuration import (
    RuntimeConfiguration,
    StorageDefinition,
    with_managed_snapshot,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.infrastructure.strategy_configuration import (
    development_strategy_configuration,
)
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.test_file_catalog import file_record
from tests.test_manual_organize_preview import manual_snapshot

SNAPSHOT_ID = "active-1"
SNAPSHOT_DIGEST = "a" * 64
NOW = datetime(2026, 8, 30, 12, tzinfo=UTC)


@dataclass
class Fixture:
    source_directory: tempfile.TemporaryDirectory
    target_directory: tempfile.TemporaryDirectory
    database: Path
    source_root: Path
    target_root: Path
    index: InMemoryFileIndexRepository
    configuration: RuntimeConfiguration
    provider: SyntheticMetadataProvider

    def cleanup(self) -> None:
        self.source_directory.cleanup()
        self.target_directory.cleanup()


def request(api, path: str, *, method: str = "GET", body=None, token: str = "operator-token"):
    payload = json.dumps(body).encode("utf-8") if body is not None else b""
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": str(len(payload)),
        "wsgi.input": io.BytesIO(payload),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
    }
    value = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(value)


class _SelectiveExecutor:
    def __init__(self, failed_suffix: str | None = None, uncertain: bool = False) -> None:
        self.failed_suffix = failed_suffix
        self.uncertain = uncertain
        self.calls: list[str] = []
        self.real = OrganizerExecutor()

    def execute(self, plan, storages, **kwargs):
        self.calls.append(plan.source)
        if self.failed_suffix and plan.source.endswith(self.failed_suffix):
            if self.uncertain:
                return ExecutionResult(
                    ExecutionStatus.PARTIAL,
                    plan.operation,
                    plan.source,
                    plan.target,
                    completed_operations=(plan.operation.value,),
                    errors=("injected response uncertainty",),
                    plan_id=plan.plan_id,
                    effect_certainty=ExecutionEffectCertainty.ATTEMPTED_UNVERIFIED,
                    uncertain_effects=("mutation_outcome",),
                )
            return ExecutionResult(
                ExecutionStatus.FAILED,
                plan.operation,
                plan.source,
                plan.target,
                errors=("injected pre-mutation failure",),
                plan_id=plan.plan_id,
                effect_certainty=ExecutionEffectCertainty.NONE,
            )
        return self.real.execute(plan, storages, **kwargs)


class ManualOrganizeExecutionTests(unittest.TestCase):
    def _fixture(
        self,
        names: tuple[str, ...] = ("One.2001.mkv",),
        *,
        operation: OrganizeOperationType = OrganizeOperationType.MOVE,
        same_storage: bool = False,
        read_only_target: bool = False,
        attachments: AttachmentPolicy | None = None,
        cleanup: DirectoryCleanupPolicy | None = None,
    ) -> Fixture:
        source_directory = tempfile.TemporaryDirectory()
        target_directory = tempfile.TemporaryDirectory()
        source_root = Path(source_directory.name)
        target_root = source_root if same_storage else Path(target_directory.name)
        records = []
        candidates = []
        for index, name in enumerate(names, start=1):
            path = Path(name)
            Path(source_root, path).parent.mkdir(parents=True, exist_ok=True)
            Path(source_root, path).write_bytes((name.encode("utf-8") + b"x" * 200)[:123])
            file_id = path.stem.split(".", 1)[0].casefold()
            records.append(file_record(file_id, "source", "library", name))
            title = path.stem.split(".", 1)[0]
            candidates.append(
                MediaCandidate(
                    "tmdb",
                    str(100 + index),
                    MediaType.MOVIE,
                    title,
                    year=2001,
                    genres=("Animation",),
                    countries=("JP",),
                )
            )
        index = InMemoryFileIndexRepository()
        index.batch_upsert(tuple(records))

        strategy = development_strategy_configuration()
        type_policies = list(strategy.recognition_type_policies)
        c_index = next(
            index for index, value in enumerate(type_policies) if value.recognition_type_id == "C"
        )
        c_policy = type_policies[c_index]
        organize_policy = replace(
            c_policy.organize_policy,
            operation=operation,
            attachments=attachments or c_policy.organize_policy.attachments,
            source_directory_cleanup=cleanup or c_policy.organize_policy.source_directory_cleanup,
            rollback=RollbackPolicy(False, True),
            conflict_strategy=(
                ConflictStrategy.OVERWRITE
                if operation is OrganizeOperationType.MOVE and read_only_target is False
                else c_policy.organize_policy.conflict_strategy
            ),
        )
        type_policies[c_index] = replace(c_policy, organize_policy=organize_policy)
        strategy = replace(strategy, recognition_type_policies=tuple(type_policies))
        definitions = [
            StorageDefinition("source", "local", str(source_root), "Source"),
        ]
        storage_ids = "source"
        if not same_storage:
            definitions.append(
                StorageDefinition(
                    "target", "local", str(target_root), "Target", read_only=read_only_target
                )
            )
            storage_ids = "target"
        configuration = RuntimeConfiguration(
            strategy,
            tuple(definitions),
            # An empty ResourceLibrary root keeps cleanup bounded to the source
            # Storage root in the same way as the production configuration.
            (ResourceLibrary("library", "Library", "source", ""),),
            (),
            (MediaLibrary("movies", "Movies", storage_ids, "Movies"),),
            str(source_root / "history.jsonl"),
            str(source_root / "runtime.sqlite3"),
        )
        configuration = with_managed_snapshot(
            configuration, snapshot_id=SNAPSHOT_ID, digest=SNAPSHOT_DIGEST
        )
        provider = SyntheticMetadataProvider(tuple(candidates))
        return Fixture(
            source_directory,
            target_directory,
            Path(configuration.database_path),
            source_root,
            target_root,
            index,
            configuration,
            provider,
        )

    @staticmethod
    def _services(repository, fixture: Fixture):
        catalog = FileCatalogService(
            fixture.index,
            ("library",),
            ("source",),
            task_repository=repository,
        )
        intents = ManualOrganizeIntentService(
            repository, catalog, configuration_resolver=manual_snapshot
        )
        source = LocalStorage("source", fixture.source_root)
        storages = {"source": source}
        if fixture.target_root != fixture.source_root:
            target_definition = next(
                value
                for value in fixture.configuration.storage_definitions
                if value.storage_id == "target"
            )
            storages["target"] = LocalStorage(
                "target", fixture.target_root, read_only=target_definition.read_only
            )
        previews = ManualOrganizePreviewService(
            repository,
            intents,
            configuration=fixture.configuration,
            providers=MetadataProviderRegistry((fixture.provider,)),
            storages=storages,
        )
        execution = ManualOrganizeExecutionService(repository, previews, executor=None)
        return catalog, intents, previews, execution, storages

    @staticmethod
    def _intent_and_preview(intents, previews, *, item_ids=None, recognition_type="C"):
        file_ids = item_ids or ["one"]
        intent = intents.create(file_ids, actor="operator")
        if recognition_type == "C":
            for item in intent.items:
                intent = intents.update_choice(
                    intent.intent_id,
                    item.item_id,
                    {
                        "recognitionTypeId": "C",
                        "namingPolicyId": "A",
                        "classificationPolicyId": "A",
                        "organizePolicyId": "A",
                    },
                    expected_version=intent.version,
                    expected_item_version=item.version,
                    actor="operator",
                )
        selected_item_ids = None if item_ids is None else [item.item_id for item in intent.items]
        preview = previews.create(
            intent.intent_id,
            selected_item_ids,
            expected_version=intent.version,
            expected_item_versions={item.item_id: item.version for item in intent.items},
            snapshot_id=SNAPSHOT_ID,
            snapshot_digest=SNAPSHOT_DIGEST,
            actor="operator",
        )
        return intent, preview

    @staticmethod
    def _authorize(execution, preview, *, allow_overwrite=False, allow_source_cleanup=False):
        item_ids = [
            item.item_id
            for item in preview.items
            if item.status is ManualPreviewItemStatus.PREVIEWED
        ]
        selected = set(item_ids)
        return execution.authorize(
            preview.preview_id,
            item_ids,
            expected_intent_version=preview.intent_version,
            expected_item_versions={
                item.item_id: item.item_version
                for item in preview.items
                if item.item_id in selected
            },
            snapshot_id=preview.configuration_snapshot_id,
            snapshot_digest=preview.configuration_snapshot_digest,
            actor="operator",
            confirmation=True,
            allow_overwrite=allow_overwrite,
            allow_source_cleanup=allow_source_cleanup,
        )

    def test_type_c_exact_move_persists_result_effect_and_checkpoint(self):
        fixture = self._fixture()
        try:
            with SQLiteTaskRepository(fixture.database) as repository:
                _, intents, previews, execution, _ = self._services(repository, fixture)
                intent, preview = self._intent_and_preview(intents, previews)
                item = preview.items[0]
                authority = self._authorize(execution, preview)
                run = execution.execute(
                    authority.authorization_id, actor="operator", confirmation=True
                )

                self.assertEqual("completed", run.status.value)
                self.assertEqual("success", run.items[0].status.value)
                self.assertEqual("C", run.items[0].plan["recognitionType"])
                self.assertTrue(run.items[0].effects)
                self.assertFalse(Path(fixture.source_root, "One.2001.mkv").exists())
                self.assertTrue(
                    Path(fixture.target_root, "Movies/Anime/One (2001)/One (2001).mkv").exists()
                )
                result = repository.list_results(run.task_id)[0]
                self.assertEqual("C", result.recognition_type)
                self.assertEqual("A", result.naming_policy_id)
                self.assertEqual("A", result.classification_policy_id)
                self.assertEqual("A", result.organize_policy_id)
                self.assertEqual("verified_complete", result.effect_certainty)
                self.assertEqual(
                    run.task_id, repository.get_item(run.items[0].task_item_id).task_id
                )
                self.assertEqual(
                    "consumed",
                    repository.get_manual_execution_authorization(
                        authority.authorization_id
                    ).status.value,
                )
                checkpoint = ProcessingCheckpointService(repository).get(
                    run.items[0].task_item_id, task_id=run.task_id
                )
                self.assertEqual("verified_complete", checkpoint.effect_certainty.value)
                self.assertIn("completed", checkpoint.stage.value)
                persisted = execution.document(run.execution_id)
                self.assertEqual(run.execution_id, persisted["executionId"])
                self.assertEqual(run.items[0].task_item_id, persisted["items"][0]["taskItemId"])
                self.assertIsNotNone(persisted["items"][0]["checkpoint"])
                self.assertEqual(item.item_id, run.selected_item_ids[0])
        finally:
            fixture.cleanup()

    def test_exact_execution_plan_preserves_long_storage_paths(self):
        source_path = "/".join(("a" * 200, "b" * 200, "c" * 120, "One.2001.mkv"))
        fixture = self._fixture(names=(source_path,))
        try:
            with SQLiteTaskRepository(fixture.database) as repository:
                _, intents, previews, execution, _ = self._services(repository, fixture)
                _, preview = self._intent_and_preview(intents, previews)
                item = preview.items[0]
                self.assertGreater(len(item.source.path), 512)
                self.assertEqual(item.source.path, item.plan["executionPlan"]["sourcePath"])
                authority = self._authorize(execution, preview)
                run = execution.execute(
                    authority.authorization_id, actor="operator", confirmation=True
                )
                self.assertEqual("success", run.items[0].status.value)
                task_item = repository.get_item(run.items[0].task_item_id)
                self.assertEqual(
                    item.plan["executionPlan"]["targetPath"], task_item.destination_path
                )
        finally:
            fixture.cleanup()

    def test_authority_requires_confirmation_and_rejects_stale_or_blocked_work_before_task(self):
        fixture = self._fixture(names=("One.2001.mkv", "Unknown.2024.mkv"))
        try:
            with SQLiteTaskRepository(fixture.database) as repository:
                _, intents, previews, execution, _ = self._services(repository, fixture)
                intent = intents.create(["one", "unknown"], actor="operator")
                preview = previews.create(intent.intent_id, expected_version=1, actor="operator")
                first = preview.items[0]
                with self.assertRaisesRegex(Exception, "confirmation"):
                    execution.authorize(
                        preview.preview_id,
                        [first.item_id],
                        actor="operator",
                        confirmation=False,
                    )
                with self.assertRaisesRegex(Exception, "duplicates"):
                    execution.authorize(
                        preview.preview_id,
                        [first.item_id, first.item_id],
                        actor="operator",
                        confirmation=True,
                    )
                with self.assertRaisesRegex(Exception, "not executable"):
                    execution.authorize(
                        preview.preview_id,
                        [preview.items[1].item_id],
                        actor="operator",
                        confirmation=True,
                    )
                with self.assertRaisesRegex(Exception, "snapshot|digest"):
                    execution.authorize(
                        preview.preview_id,
                        [first.item_id],
                        snapshot_digest="b" * 64,
                        actor="operator",
                        confirmation=True,
                    )
                self.assertEqual(0, len(repository.list_tasks()))
                self.assertEqual(0, len(repository.list_manual_execution_authorizations()))
        finally:
            fixture.cleanup()

    def test_execution_requires_the_dedicated_permission(self):
        fixture = self._fixture()
        try:
            with SQLiteTaskRepository(fixture.database) as repository:
                _, intents, previews, execution, _ = self._services(repository, fixture)
                _, preview = self._intent_and_preview(intents, previews)
                item = preview.items[0]
                with self.assertRaisesRegex(Exception, "permission"):
                    execution.authorize(
                        preview.preview_id,
                        [item.item_id],
                        expected_intent_version=preview.intent_version,
                        expected_item_versions={item.item_id: item.item_version},
                        snapshot_id=preview.configuration_snapshot_id,
                        snapshot_digest=preview.configuration_snapshot_digest,
                        actor="operator",
                        permission=ApiPermission.SUBMIT_DRY_RUN.value,
                        confirmation=True,
                    )
                self.assertEqual(0, len(repository.list_manual_execution_authorizations()))
        finally:
            fixture.cleanup()

    def test_one_shot_authority_and_unselected_sibling_are_not_replayed(self):
        fixture = self._fixture(names=("One.2001.mkv", "Two.2001.mkv"))
        try:
            with SQLiteTaskRepository(fixture.database) as repository:
                _, intents, previews, execution, _ = self._services(repository, fixture)
                intent = intents.create(["one", "two"], actor="operator")
                preview = previews.create(
                    intent.intent_id,
                    [intent.items[0].item_id],
                    expected_version=1,
                    expected_item_versions={intent.items[0].item_id: 1},
                    actor="operator",
                )
                authority = self._authorize(execution, preview)
                run = execution.execute(
                    authority.authorization_id, actor="operator", confirmation=True
                )
                self.assertEqual((intent.items[1].item_id,), run.unselected_item_ids)
                self.assertEqual(1, len(repository.list_tasks()))
                with self.assertRaisesRegex(Exception, "cannot be reused|consumed|changed"):
                    execution.execute(
                        authority.authorization_id, actor="operator", confirmation=True
                    )
                self.assertEqual(1, len(repository.list_tasks()))
                self.assertTrue(Path(fixture.source_root, "Two.2001.mkv").exists())
                self.assertTrue(
                    Path(fixture.target_root, "Movies/Anime/One (2001)/One (2001).mkv").exists()
                )
                self.assertEqual(
                    run.execution_id, repository.get_manual_execution(run.execution_id).execution_id
                )
        finally:
            fixture.cleanup()

    def test_authorized_subset_keeps_all_other_intent_items_visible_unselected(self):
        fixture = self._fixture(names=("One.2001.mkv", "Two.2001.mkv"))
        try:
            with SQLiteTaskRepository(fixture.database) as repository:
                catalog, intents, previews, service, _ = self._services(repository, fixture)
                intent, preview = self._intent_and_preview(
                    intents, previews, item_ids=["one", "two"]
                )
                selected = preview.items[0]
                authority = service.authorize(
                    preview.preview_id,
                    [selected.item_id],
                    expected_intent_version=preview.intent_version,
                    expected_item_versions={selected.item_id: selected.item_version},
                    snapshot_id=preview.configuration_snapshot_id,
                    snapshot_digest=preview.configuration_snapshot_digest,
                    actor="operator",
                    confirmation=True,
                )
                run = service.execute(
                    authority.authorization_id, actor="operator", confirmation=True
                )
                self.assertEqual((selected.item_id,), run.selected_item_ids)
                self.assertEqual((intent.items[1].item_id,), run.unselected_item_ids)
                self.assertEqual(1, len(run.items))
                self.assertEqual(1, len(repository.list_items(run.task_id)))
                self.assertEqual(1, len(repository.list_results(run.task_id)))

                operator = ResolvedApiPrincipal(
                    "operator",
                    "operator-token",
                    frozenset({ApiPermission.READ}),
                )
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(operator,),
                    file_catalog=catalog,
                    manual_intent_service=intents,
                    manual_preview_service=previews,
                    manual_execution_service=service,
                )
                status, intent_document = request(api, f"/api/v1/manual-intents/{intent.intent_id}")
                self.assertEqual(200, status)
                discovered = intent_document["manualExecutionDiscovery"]
                self.assertEqual(
                    [run.execution_id], [item["executionId"] for item in discovered["executions"]]
                )
                self.assertEqual(
                    [intent.items[1].item_id],
                    discovered["executions"][0]["unselectedItemIds"],
                )
                self.assertIn("execution", discovered["executions"][0]["links"])

                status, preview_document = request(
                    api, f"/api/v1/manual-previews/{preview.preview_id}"
                )
                self.assertEqual(200, status)
                self.assertEqual(
                    [intent.items[1].item_id],
                    preview_document["manualExecutionDiscovery"]["executions"][0][
                        "unselectedItemIds"
                    ],
                )
        finally:
            fixture.cleanup()

    def test_restart_discovers_terminal_execution_from_normal_parent_surfaces(self):
        fixture = self._fixture()
        try:
            with SQLiteTaskRepository(fixture.database) as repository:
                catalog, intents, previews, service, _ = self._services(repository, fixture)
                intent, preview = self._intent_and_preview(intents, previews)
                run = service.execute(
                    self._authorize(service, preview).authorization_id,
                    actor="operator",
                    confirmation=True,
                )
                task_item_id = run.items[0].task_item_id
                intent_id = intent.intent_id
                preview_id = preview.preview_id
                task_id = run.task_id

            with SQLiteTaskRepository(fixture.database) as repository:
                catalog, intents, previews, service, _ = self._services(repository, fixture)
                operator = ResolvedApiPrincipal(
                    "operator",
                    "operator-token",
                    frozenset({ApiPermission.READ}),
                )
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(operator,),
                    file_catalog=catalog,
                    manual_intent_service=intents,
                    manual_preview_service=previews,
                    manual_execution_service=service,
                )
                audit_count = len(repository.list_security_audit())
                status, intent_document = request(api, f"/api/v1/manual-intents/{intent_id}")
                self.assertEqual(200, status)
                discovery = intent_document["manualExecutionDiscovery"]
                self.assertEqual("completed", discovery["executions"][0]["status"])
                self.assertEqual(task_id, discovery["executions"][0]["taskId"])
                self.assertIn("execution", discovery["executions"][0]["links"])

                status, preview_document = request(api, f"/api/v1/manual-previews/{preview_id}")
                self.assertEqual(200, status)
                self.assertEqual(
                    "completed",
                    preview_document["manualExecutionDiscovery"]["executions"][0]["status"],
                )
                status, task_document = request(api, f"/api/v1/tasks/{task_id}")
                self.assertEqual(200, status)
                self.assertEqual(
                    task_id,
                    task_document["manualExecutionDiscovery"]["executions"][0]["taskId"],
                )
                status, item_document = request(
                    api, f"/api/v1/tasks/{task_id}/items/{task_item_id}"
                )
                self.assertEqual(200, status)
                self.assertEqual(
                    "completed",
                    item_document["manualExecutionDiscovery"]["executions"][0]["status"],
                )
                self.assertEqual(audit_count, len(repository.list_security_audit()))
        finally:
            fixture.cleanup()

    def test_restart_discovers_interrupted_execution_and_reconciliation_link(self):
        fixture = self._fixture()
        try:

            class ProcessInterrupted(BaseException):
                pass

            with SQLiteTaskRepository(fixture.database) as repository:
                catalog, intents, previews, service, _ = self._services(repository, fixture)
                intent, preview = self._intent_and_preview(intents, previews)
                authority = self._authorize(service, preview)
                with patch.object(
                    repository,
                    "update_manual_execution",
                    side_effect=ProcessInterrupted(),
                ):
                    with self.assertRaises(ProcessInterrupted):
                        service.execute(
                            authority.authorization_id,
                            actor="operator",
                            confirmation=True,
                        )
                intent_id = intent.intent_id

            with SQLiteTaskRepository(fixture.database) as repository:
                catalog, intents, previews, service, _ = self._services(repository, fixture)
                operator = ResolvedApiPrincipal(
                    "operator",
                    "operator-token",
                    frozenset({ApiPermission.READ, ApiPermission.EXECUTE_MANUAL_ORGANIZE}),
                )
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(operator,),
                    file_catalog=catalog,
                    manual_intent_service=intents,
                    manual_preview_service=previews,
                    manual_execution_service=service,
                )
                status, intent_document = request(api, f"/api/v1/manual-intents/{intent_id}")
                self.assertEqual(200, status)
                execution = intent_document["manualExecutionDiscovery"]["executions"][0]
                self.assertEqual("admitted", execution["status"])
                self.assertIn("reconcile", execution["links"])
                task_id = execution["taskId"]
                execution_id = execution["executionId"]
                status, task_document = request(api, f"/api/v1/tasks/{task_id}")
                self.assertEqual(200, status)
                self.assertEqual(
                    "admitted", task_document["manualExecutionDiscovery"]["executions"][0]["status"]
                )
                status, reconciled = request(
                    api,
                    f"/api/v1/manual-executions/{execution_id}/reconcile",
                    method="POST",
                    body={"confirmation": True},
                )
                self.assertEqual(200, status)
                self.assertEqual("failed", reconciled["status"])
                self.assertNotIn("reconcile", reconciled["links"])
                self.assertTrue(Path(fixture.source_root, "One.2001.mkv").exists())
        finally:
            fixture.cleanup()

    def test_manual_credentials_are_rejected_and_fully_redacted(self):
        fixture = self._fixture()
        secret = "closure-review-secret"
        try:
            with SQLiteTaskRepository(fixture.database) as repository:
                catalog, intents, previews, service, _ = self._services(repository, fixture)
                _, preview = self._intent_and_preview(intents, previews)
                item = preview.items[0]
                with self.assertRaisesRegex(Exception, "note"):
                    service.authorize(
                        preview.preview_id,
                        [item.item_id],
                        expected_intent_version=preview.intent_version,
                        expected_item_versions={item.item_id: item.item_version},
                        snapshot_id=preview.configuration_snapshot_id,
                        snapshot_digest=preview.configuration_snapshot_digest,
                        actor="operator",
                        confirmation=True,
                        note=f"api_key={secret}",
                    )
                self.assertEqual((), repository.list_manual_execution_authorizations())
                self.assertNotIn(secret.encode(), fixture.database.read_bytes())

                redacted = redact_manual_text(
                    f"Authorization: Bearer {secret} token={secret} Cookie: session={secret}"
                )
                self.assertNotIn(secret, redacted)
                self.assertNotIn(f"Bearer {secret}", redacted)
                self.assertIn("Authorization: [redacted]", redacted)

                operator = ResolvedApiPrincipal(
                    "operator",
                    "operator-token",
                    frozenset({ApiPermission.READ, ApiPermission.EXECUTE_MANUAL_ORGANIZE}),
                )
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(operator,),
                    file_catalog=catalog,
                    manual_intent_service=intents,
                    manual_preview_service=previews,
                    manual_execution_service=service,
                )
                body = {
                    "expectedVersion": preview.intent_version,
                    "expectedItemVersions": {item.item_id: item.item_version},
                    "itemIds": [item.item_id],
                    "snapshotId": preview.configuration_snapshot_id,
                    "snapshotDigest": preview.configuration_snapshot_digest,
                    "confirmation": True,
                    "note": f"api_key={secret}",
                }
                status, error = request(
                    api,
                    f"/api/v1/manual-previews/{preview.preview_id}/authorize",
                    method="POST",
                    body=body,
                )
                self.assertEqual(409, status)
                self.assertNotIn(secret, json.dumps(error))
                self.assertNotIn(secret.encode(), fixture.database.read_bytes())
                self.assertNotIn(secret, json.dumps(repository.list_security_audit(), default=str))
        finally:
            fixture.cleanup()

    def test_reading_authorization_does_not_expire_active_authority(self):
        fixture = self._fixture()
        try:
            with SQLiteTaskRepository(fixture.database) as repository:
                catalog, intents, previews, _, _ = self._services(repository, fixture)
                _, preview = self._intent_and_preview(intents, previews)
                now = [NOW]
                service = ManualOrganizeExecutionService(repository, previews, clock=lambda: now[0])
                item = preview.items[0]
                authority = service.authorize(
                    preview.preview_id,
                    [item.item_id],
                    expected_intent_version=preview.intent_version,
                    expected_item_versions={item.item_id: item.item_version},
                    snapshot_id=preview.configuration_snapshot_id,
                    snapshot_digest=preview.configuration_snapshot_digest,
                    actor="operator",
                    confirmation=True,
                    ttl_seconds=1,
                )
                now[0] = NOW + timedelta(seconds=2)
                operator = ResolvedApiPrincipal(
                    "operator", "operator-token", frozenset({ApiPermission.READ})
                )
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(operator,),
                    file_catalog=catalog,
                    manual_intent_service=intents,
                    manual_preview_service=previews,
                    manual_execution_service=service,
                )
                status, document = request(
                    api,
                    f"/api/v1/manual-execution-authorizations/{authority.authorization_id}",
                )
                self.assertEqual(200, status)
                self.assertEqual("active", document["status"])
                self.assertEqual(
                    "active",
                    repository.get_manual_execution_authorization(
                        authority.authorization_id
                    ).status.value,
                )
                self.assertEqual(
                    (),
                    repository.list_manual_execution_authorization_audit(
                        authority.authorization_id
                    )[1:],
                )
        finally:
            fixture.cleanup()

    def test_authorization_expiry_is_audited_and_cannot_admit_a_task(self):
        fixture = self._fixture()
        try:
            with SQLiteTaskRepository(fixture.database) as repository:
                _, intents, previews, _, _ = self._services(repository, fixture)
                _, preview = self._intent_and_preview(intents, previews)
                now = [NOW]
                service = ManualOrganizeExecutionService(repository, previews, clock=lambda: now[0])
                item = preview.items[0]
                authority = service.authorize(
                    preview.preview_id,
                    [item.item_id],
                    expected_intent_version=preview.intent_version,
                    expected_item_versions={item.item_id: item.item_version},
                    snapshot_id=preview.configuration_snapshot_id,
                    snapshot_digest=preview.configuration_snapshot_digest,
                    actor="operator",
                    confirmation=True,
                    ttl_seconds=1,
                )
                now[0] = NOW + timedelta(seconds=2)
                expired = service.get_authorization(authority.authorization_id)
                self.assertEqual("expired", expired.status.value)
                self.assertEqual(
                    ["issued", "expired"],
                    [
                        value.action
                        for value in repository.list_manual_execution_authorization_audit(
                            authority.authorization_id
                        )
                    ],
                )
                with self.assertRaisesRegex(Exception, "expired"):
                    service.execute(authority.authorization_id, actor="operator", confirmation=True)
                self.assertEqual(0, len(repository.list_tasks()))
        finally:
            fixture.cleanup()

    def test_move_copy_hard_link_and_soft_link_use_explicit_reviewed_operation(self):
        cases = (
            (OrganizeOperationType.MOVE, False),
            (OrganizeOperationType.COPY, False),
            (OrganizeOperationType.HARD_LINK, True),
            (OrganizeOperationType.SOFT_LINK, True),
        )
        for operation, same_storage in cases:
            with self.subTest(operation=operation):
                fixture = self._fixture(operation=operation, same_storage=same_storage)
                try:
                    with SQLiteTaskRepository(fixture.database) as repository:
                        _, intents, previews, execution, _ = self._services(repository, fixture)
                        _, preview = self._intent_and_preview(intents, previews)
                        self.assertEqual(ManualPreviewItemStatus.PREVIEWED, preview.items[0].status)
                        authority = self._authorize(execution, preview)
                        run = execution.execute(
                            authority.authorization_id, actor="operator", confirmation=True
                        )
                        self.assertEqual("success", run.items[0].status.value)
                        target = Path(fixture.target_root, "Movies/Anime/One (2001)/One (2001).mkv")
                        self.assertTrue(target.exists())
                        source = Path(fixture.source_root, "One.2001.mkv")
                        if operation is OrganizeOperationType.MOVE:
                            self.assertFalse(source.exists())
                        else:
                            self.assertTrue(source.exists())
                        if operation is OrganizeOperationType.HARD_LINK:
                            self.assertEqual(source.stat().st_ino, target.stat().st_ino)
                        if operation is OrganizeOperationType.SOFT_LINK:
                            self.assertTrue(target.is_symlink())
                finally:
                    fixture.cleanup()

    def test_attachments_and_source_cleanup_are_persisted_only_when_explicitly_authorized(self):
        attachment_policy = AttachmentPolicy(enabled=True)
        attachment_fixture = self._fixture(attachments=attachment_policy)
        try:
            Path(attachment_fixture.source_root, "One.2001.en.srt").write_text(
                "sub", encoding="utf-8"
            )
            with SQLiteTaskRepository(attachment_fixture.database) as repository:
                _, intents, previews, execution, _ = self._services(repository, attachment_fixture)
                _, preview = self._intent_and_preview(intents, previews)
                self.assertEqual(1, len(preview.items[0].plan["attachments"]))
                run = execution.execute(
                    self._authorize(execution, preview).authorization_id,
                    actor="operator",
                    confirmation=True,
                )
                result = repository.list_results(run.task_id)[0]
                self.assertEqual(1, result.attachment_count)
                self.assertTrue(
                    any(value.startswith("ATTACHMENT:") for value in result.completed_operations)
                )
                self.assertTrue(
                    Path(
                        attachment_fixture.target_root, "Movies/Anime/One (2001)/One (2001).en.srt"
                    ).exists()
                )
                self.assertFalse(Path(attachment_fixture.source_root, "One.2001.en.srt").exists())
        finally:
            attachment_fixture.cleanup()

        cleanup_policy = DirectoryCleanupPolicy(DirectoryCleanupMode.EMPTY, 1, (), 100)
        cleanup_fixture = self._fixture(names=("folder/One.2001.mkv",), cleanup=cleanup_policy)
        try:
            with SQLiteTaskRepository(cleanup_fixture.database) as repository:
                _, intents, previews, execution, _ = self._services(repository, cleanup_fixture)
                _, preview = self._intent_and_preview(intents, previews)
                with self.assertRaisesRegex(Exception, "source-cleanup"):
                    self._authorize(execution, preview)
                authority = self._authorize(execution, preview, allow_source_cleanup=True)
                run = execution.execute(
                    authority.authorization_id, actor="operator", confirmation=True
                )
                self.assertEqual("success", run.items[0].status.value)
                self.assertFalse(Path(cleanup_fixture.source_root, "folder").exists())
                self.assertIn("DELETE_EMPTY_DIRECTORY", run.items[0].completed_operations)
        finally:
            cleanup_fixture.cleanup()

    def test_capability_gap_and_unsupported_cross_storage_link_fail_without_fallback(self):
        read_only = self._fixture(read_only_target=True)
        try:
            with SQLiteTaskRepository(read_only.database) as repository:
                _, intents, previews, execution, _ = self._services(repository, read_only)
                _, preview = self._intent_and_preview(intents, previews)
                self.assertEqual(ManualPreviewItemStatus.BLOCKED, preview.items[0].status)
                with self.assertRaisesRegex(Exception, "not executable|capability"):
                    execution.authorize(
                        preview.preview_id,
                        [preview.items[0].item_id],
                        expected_intent_version=preview.intent_version,
                        expected_item_versions={
                            preview.items[0].item_id: preview.items[0].item_version
                        },
                        snapshot_id=preview.configuration_snapshot_id,
                        snapshot_digest=preview.configuration_snapshot_digest,
                        actor="operator",
                        confirmation=True,
                    )
                self.assertTrue(Path(read_only.source_root, "One.2001.mkv").exists())
                self.assertEqual([], list(read_only.target_root.rglob("*")))
        finally:
            read_only.cleanup()

        unsupported = self._fixture(operation=OrganizeOperationType.HARD_LINK)
        try:
            with SQLiteTaskRepository(unsupported.database) as repository:
                _, intents, previews, execution, _ = self._services(repository, unsupported)
                _, preview = self._intent_and_preview(intents, previews)
                self.assertEqual(ManualPreviewItemStatus.BLOCKED, preview.items[0].status)
                self.assertIn("same_storage_link", preview.items[0].plan["capabilities"]["missing"])
                self.assertEqual(0, len(repository.list_tasks()))
        finally:
            unsupported.cleanup()

    def test_collision_requires_recorded_overwrite_decision_and_explicit_authority(self):
        fixture = self._fixture()
        try:
            with SQLiteTaskRepository(fixture.database) as repository:
                _, intents, previews, execution, _ = self._services(repository, fixture)
                intent, blocked = self._intent_and_preview(intents, previews)
                item = blocked.items[0]
                self.assertEqual(ManualPreviewItemStatus.PREVIEWED, item.status)
                destination = item.plan["destination"]["path"]
                Path(fixture.target_root, destination).parent.mkdir(parents=True, exist_ok=True)
                Path(fixture.target_root, destination).write_bytes(b"old")
                blocked = previews.create(
                    intent.intent_id,
                    expected_version=intent.version,
                    expected_item_versions={intent.items[0].item_id: intent.items[0].version},
                    actor="operator",
                )
                item = blocked.items[0]
                self.assertEqual(ManualPreviewItemStatus.BLOCKED, item.status)
                plan = item.plan
                confirmation = ConflictConfirmation(
                    str(uuid4()),
                    "conflict-task",
                    "conflict-item",
                    plan["planId"],
                    "DESTINATION_EXISTS",
                    "source",
                    plan["source"]["path"],
                    "target",
                    destination,
                    "overwrite",
                    ConfirmationStatus.RESOLVED,
                    NOW,
                    NOW,
                    selected_strategy="overwrite",
                    overwrite_authorized=True,
                    actor="operator",
                )
                repository.create_confirmation(confirmation)
                fresh = previews.create(
                    intent.intent_id,
                    expected_version=intent.version,
                    expected_item_versions={intent.items[0].item_id: intent.items[0].version},
                    actor="operator",
                )
                self.assertEqual(ManualPreviewItemStatus.PREVIEWED, fresh.items[0].status)
                self.assertTrue(fresh.items[0].plan["executionPlan"]["overwriteAuthorized"])
                with self.assertRaisesRegex(Exception, "overwrite"):
                    self._authorize(execution, fresh)
                authority = self._authorize(execution, fresh, allow_overwrite=True)
                run = execution.execute(
                    authority.authorization_id, actor="operator", confirmation=True
                )
                self.assertEqual("success", run.items[0].status.value)
                self.assertFalse(Path(fixture.source_root, "One.2001.mkv").exists())
                self.assertEqual(123, Path(fixture.target_root, destination).stat().st_size)
        finally:
            fixture.cleanup()

    def test_mixed_batch_and_pre_mutation_failure_keep_independent_recovery(self):
        fixture = self._fixture(names=("One.2001.mkv", "Two.2001.mkv"))
        try:
            with SQLiteTaskRepository(fixture.database) as repository:
                _, intents, previews, _, storages = self._services(repository, fixture)
                intent, preview = self._intent_and_preview(
                    intents, previews, item_ids=["one", "two"]
                )
                executor = _SelectiveExecutor(failed_suffix="Two.2001.mkv")
                service = ManualOrganizeExecutionService(repository, previews, executor=executor)
                authority = self._authorize(service, preview)
                run = service.execute(
                    authority.authorization_id, actor="operator", confirmation=True
                )
                self.assertEqual("partial_success", run.status.value)
                statuses = {item.item_id: item.status.value for item in run.items}
                self.assertEqual("success", statuses[intent.items[0].item_id])
                self.assertEqual("failed", statuses[intent.items[1].item_id])
                self.assertFalse(Path(fixture.source_root, "One.2001.mkv").exists())
                self.assertTrue(Path(fixture.source_root, "Two.2001.mkv").exists())
                self.assertEqual(2, len(repository.list_results(run.task_id)))
                failed = next(item for item in run.items if item.status.value == "failed")
                checkpoint = service._checkpoint_service.get(
                    failed.task_item_id, task_id=run.task_id
                )
                self.assertIn("retry", checkpoint.permitted_action_ids)
                self.assertNotIn("investigate", checkpoint.permitted_action_ids)
                self.assertEqual(2, len(executor.calls))
                self.assertIn("target", storages)
        finally:
            fixture.cleanup()

    def test_uncertain_failure_records_effects_and_refuses_replay(self):
        fixture = self._fixture()
        try:
            with SQLiteTaskRepository(fixture.database) as repository:
                _, intents, previews, _, _ = self._services(repository, fixture)
                _, preview = self._intent_and_preview(intents, previews)
                executor = _SelectiveExecutor(failed_suffix="One.2001.mkv", uncertain=True)
                service = ManualOrganizeExecutionService(repository, previews, executor=executor)
                run = service.execute(
                    self._authorize(service, preview).authorization_id,
                    actor="operator",
                    confirmation=True,
                )
                self.assertEqual("partial_success", run.status.value)
                item = run.items[0]
                self.assertEqual("partial", item.status.value)
                self.assertEqual("attempted_unverified", item.effect_certainty)
                self.assertTrue(item.effects)
                self.assertIn("automatic replay", item.next_action)
                checkpoint = service._checkpoint_service.get(item.task_item_id, task_id=run.task_id)
                self.assertEqual(("investigate",), checkpoint.permitted_action_ids)
                self.assertNotIn("retry", checkpoint.permitted_action_ids)
                self.assertTrue(Path(fixture.source_root, "One.2001.mkv").exists())
        finally:
            fixture.cleanup()

    def test_admission_interruption_is_reconciled_and_releases_fence(self):
        fixture = self._fixture()
        try:
            with SQLiteTaskRepository(fixture.database) as repository:
                _, intents, previews, service, _ = self._services(repository, fixture)
                _, preview = self._intent_and_preview(intents, previews)
                authority = self._authorize(service, preview)
                with patch.object(
                    repository,
                    "update_manual_execution",
                    side_effect=RuntimeError("injected admission persistence failure"),
                ):
                    with self.assertRaisesRegex(
                        RuntimeError, "injected admission persistence failure"
                    ):
                        service.execute(
                            authority.authorization_id,
                            actor="operator",
                            confirmation=True,
                        )
                stored_authority = repository.get_manual_execution_authorization(
                    authority.authorization_id
                )
                run = repository.get_manual_execution(stored_authority.execution_id)
                self.assertEqual("failed", run.status.value)
                self.assertEqual("failed", run.items[0].status.value)
                self.assertEqual("admission_interrupted", run.items[0].stage)
                self.assertIn("fresh Preview", run.items[0].next_action)
                result = repository.list_results(run.task_id)[0]
                self.assertEqual("FAILED", result.status)
                self.assertEqual("none", result.effect_certainty)
                self.assertFalse(repository.lock_owned("source", "One.2001.mkv", run.task_id))
                checkpoint = ProcessingCheckpointService(repository).get(
                    run.items[0].task_item_id, task_id=run.task_id
                )
                self.assertEqual(("investigate",), checkpoint.permitted_action_ids)
                self.assertNotIn("retry", checkpoint.permitted_action_ids)
        finally:
            fixture.cleanup()

    def test_interrupted_admission_has_explicit_api_reconciliation(self):
        fixture = self._fixture()
        try:
            with SQLiteTaskRepository(fixture.database) as repository:
                catalog, intents, previews, service, _ = self._services(repository, fixture)
                _, preview = self._intent_and_preview(intents, previews)
                authority = self._authorize(service, preview)

                class ProcessInterrupted(BaseException):
                    pass

                with patch.object(
                    repository,
                    "update_manual_execution",
                    side_effect=ProcessInterrupted(),
                ):
                    with self.assertRaises(ProcessInterrupted):
                        service.execute(
                            authority.authorization_id,
                            actor="operator",
                            confirmation=True,
                        )
                stored_authority = repository.get_manual_execution_authorization(
                    authority.authorization_id
                )
                raw = repository.get_manual_execution(stored_authority.execution_id)
                self.assertEqual("admitted", raw.status.value)
                self.assertIn("reconcile", raw.items[0].next_action)
                self.assertTrue(repository.lock_owned("source", "One.2001.mkv", raw.task_id))
                operator = ResolvedApiPrincipal(
                    "operator",
                    "operator-token",
                    frozenset({ApiPermission.READ, ApiPermission.EXECUTE_MANUAL_ORGANIZE}),
                )
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(operator,),
                    file_catalog=catalog,
                    manual_intent_service=intents,
                    manual_preview_service=previews,
                    manual_execution_service=service,
                )
                status, document = request(
                    api,
                    f"/api/v1/manual-executions/{raw.execution_id}/reconcile",
                    method="POST",
                    body={"confirmation": True},
                )
                self.assertEqual(200, status)
                self.assertEqual("failed", document["status"])
                self.assertEqual("admission_interrupted", document["items"][0]["stage"])
                self.assertFalse(repository.lock_owned("source", "One.2001.mkv", raw.task_id))
                audit = repository.list_manual_execution_authorization_audit(
                    authority.authorization_id
                )
                self.assertIn("manual_execution_reconciled", [value.action for value in audit])
        finally:
            fixture.cleanup()

    def test_result_publication_failure_persists_uncertain_effects_without_replay(self):
        fixture = self._fixture()
        try:
            with SQLiteTaskRepository(fixture.database) as repository:
                _, intents, previews, service, _ = self._services(repository, fixture)
                _, preview = self._intent_and_preview(intents, previews)
                authority = self._authorize(service, preview)
                with patch.object(
                    repository,
                    "complete_manual_execution_item",
                    side_effect=RuntimeError("injected result publication failure"),
                ):
                    with self.assertRaisesRegex(
                        RuntimeError, "injected result publication failure"
                    ):
                        service.execute(
                            authority.authorization_id,
                            actor="operator",
                            confirmation=True,
                        )
                stored_authority = repository.get_manual_execution_authorization(
                    authority.authorization_id
                )
                run = repository.get_manual_execution(stored_authority.execution_id)
                item = run.items[0]
                result = repository.list_results(run.task_id)[0]
                self.assertEqual("partial_success", run.status.value)
                self.assertEqual("partial", item.status.value)
                self.assertEqual("unknown", item.effect_certainty)
                self.assertIn("MOVE", item.completed_operations)
                self.assertIn("result_persistence", item.uncertain_effects)
                self.assertTrue(item.effects)
                self.assertFalse(item.effects[0].verified)
                self.assertEqual("PARTIAL", result.status)
                self.assertEqual("unknown", result.effect_certainty)
                self.assertIn("result_persistence", result.uncertain_effects)
                self.assertFalse(Path(fixture.source_root, "One.2001.mkv").exists())
                self.assertTrue(
                    Path(fixture.target_root, "Movies/Anime/One (2001)/One (2001).mkv").exists()
                )
                self.assertFalse(repository.lock_owned("source", "One.2001.mkv", run.task_id))
                checkpoint = ProcessingCheckpointService(repository).get(
                    item.task_item_id, task_id=run.task_id
                )
                self.assertEqual(("investigate",), checkpoint.permitted_action_ids)
                self.assertNotIn("retry", checkpoint.permitted_action_ids)
        finally:
            fixture.cleanup()

    def test_process_interruption_after_mutation_is_reconciled_from_observed_effect(self):
        fixture = self._fixture()
        try:
            with SQLiteTaskRepository(fixture.database) as repository:
                _, intents, previews, service, _ = self._services(repository, fixture)
                _, preview = self._intent_and_preview(intents, previews)
                authority = self._authorize(service, preview)

                class ProcessInterrupted(BaseException):
                    pass

                with patch.object(
                    repository,
                    "complete_manual_execution_item",
                    side_effect=ProcessInterrupted(),
                ):
                    with self.assertRaises(ProcessInterrupted):
                        service.execute(
                            authority.authorization_id,
                            actor="operator",
                            confirmation=True,
                        )
                stored_authority = repository.get_manual_execution_authorization(
                    authority.authorization_id
                )
                raw = repository.get_manual_execution(stored_authority.execution_id)
                self.assertEqual("running", raw.status.value)
                self.assertEqual("running", raw.items[0].status.value)
                self.assertEqual(0, len(repository.list_results(raw.task_id)))
                self.assertFalse(Path(fixture.source_root, "One.2001.mkv").exists())
                self.assertTrue(
                    Path(fixture.target_root, "Movies/Anime/One (2001)/One (2001).mkv").exists()
                )
                recovered = service.reconcile(
                    raw.execution_id,
                    actor="operator",
                    confirmation=True,
                )
                item = recovered.items[0]
                self.assertEqual("partial_success", recovered.status.value)
                self.assertEqual("partial", item.status.value)
                self.assertEqual("unknown", item.effect_certainty)
                self.assertIn("MOVE", item.completed_operations)
                self.assertIn("process_interruption", item.uncertain_effects)
                self.assertTrue(item.effects)
                self.assertFalse(item.effects[0].verified)
                self.assertEqual(1, len(repository.list_results(recovered.task_id)))
                checkpoint = ProcessingCheckpointService(repository).get(
                    item.task_item_id, task_id=recovered.task_id
                )
                self.assertEqual(("investigate",), checkpoint.permitted_action_ids)
                self.assertNotIn("retry", checkpoint.permitted_action_ids)
                self.assertFalse(repository.lock_owned("source", "One.2001.mkv", recovered.task_id))
        finally:
            fixture.cleanup()

    def test_concurrent_execute_consumes_authority_once(self):
        fixture = self._fixture()
        try:
            with SQLiteTaskRepository(fixture.database) as repository:
                _, intents, previews, execution, _ = self._services(repository, fixture)
                _, preview = self._intent_and_preview(intents, previews)
                authority = self._authorize(execution, preview)
            active_reads = Barrier(2)
            winner_done = Event()
            outcome_lock = Lock()
            outcomes = {}
            executor = _SelectiveExecutor()

            def worker(role: str) -> None:
                try:
                    with SQLiteTaskRepository(fixture.database) as repository:
                        _, _, previews, execution, _ = self._services(repository, fixture)
                        execution._executor = executor
                        get_authorization = execution.get_authorization

                        def read_active(authorization_id, *, expire=True):
                            value = get_authorization(authorization_id, expire=expire)
                            active_reads.wait(timeout=5)
                            return value

                        validate_storage = execution._validate_current_storage

                        def validate_after_winner(*args, **kwargs):
                            if not winner_done.wait(timeout=5):
                                raise AssertionError(
                                    "winner did not complete before loser preflight"
                                )
                            return validate_storage(*args, **kwargs)

                        with patch.object(execution, "get_authorization", side_effect=read_active):
                            if role == "loser":
                                with patch.object(
                                    execution,
                                    "_validate_current_storage",
                                    side_effect=validate_after_winner,
                                ):
                                    result = execution.execute(
                                        authority.authorization_id,
                                        actor="operator",
                                        confirmation=True,
                                    )
                            else:
                                result = execution.execute(
                                    authority.authorization_id,
                                    actor="operator",
                                    confirmation=True,
                                )
                                winner_done.set()
                except Exception as error:  # one loser is the expected durable rejection
                    result = error
                finally:
                    with outcome_lock:
                        outcomes[role] = result

            threads = [
                Thread(target=worker, args=("winner",)),
                Thread(target=worker, args=("loser",)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)
            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual(2, len(outcomes))
            self.assertEqual(
                1,
                sum(hasattr(value, "execution_id") for value in outcomes.values()),
            )
            self.assertTrue(hasattr(outcomes["winner"], "execution_id"))
            self.assertIsInstance(outcomes["loser"], ManualExecutionError)
            self.assertEqual("authorization_consumed", outcomes["loser"].code)
            self.assertEqual(["One.2001.mkv"], executor.calls)
            target = Path(
                fixture.target_root,
                "Movies/Anime/One (2001)/One (2001).mkv",
            )
            self.assertFalse(Path(fixture.source_root, "One.2001.mkv").exists())
            self.assertTrue(target.exists())
            with SQLiteTaskRepository(fixture.database) as repository:
                stored = repository.get_manual_execution_authorization(authority.authorization_id)
                self.assertEqual("consumed", stored.status.value)
                self.assertEqual(
                    1,
                    sum(
                        audit.action == "consumed"
                        for audit in repository.list_manual_execution_authorization_audit(
                            authority.authorization_id
                        )
                    ),
                )
                executions = repository.list_manual_executions_for_preview(preview.preview_id)
                self.assertEqual(1, len(executions))
                tasks = repository.list_tasks()
                self.assertEqual(1, len(tasks))
                self.assertEqual(1, len(repository.list_items(tasks[0].task_id)))
                self.assertEqual(1, len(repository.list_results(tasks[0].task_id)))
                self.assertEqual(
                    0,
                    repository._connection.execute("SELECT COUNT(*) FROM file_locks").fetchone()[0],
                )
        finally:
            fixture.cleanup()

    def test_active_authorization_preserves_external_source_missing(self):
        fixture = self._fixture()
        try:
            with SQLiteTaskRepository(fixture.database) as repository:
                _, intents, previews, execution, _ = self._services(repository, fixture)
                _, preview = self._intent_and_preview(intents, previews)
                authority = self._authorize(execution, preview)
                Path(fixture.source_root, "One.2001.mkv").unlink()

                with self.assertRaises(ManualExecutionError) as raised:
                    execution.execute(
                        authority.authorization_id,
                        actor="operator",
                        confirmation=True,
                    )

                self.assertEqual("source_missing", raised.exception.code)
                self.assertEqual(
                    "active",
                    repository.get_manual_execution_authorization(
                        authority.authorization_id
                    ).status.value,
                )
                self.assertEqual(0, len(repository.list_tasks()))
                self.assertEqual(
                    0,
                    len(repository.list_manual_executions_for_preview(preview.preview_id)),
                )
                self.assertEqual(
                    0,
                    repository._connection.execute("SELECT COUNT(*) FROM file_locks").fetchone()[0],
                )
                self.assertFalse(
                    Path(
                        fixture.target_root,
                        "Movies/Anime/One (2001)/One (2001).mkv",
                    ).exists()
                )
        finally:
            fixture.cleanup()

    def test_api_requires_execution_permission_and_projects_same_durable_execution(self):
        fixture = self._fixture()
        try:
            with SQLiteTaskRepository(fixture.database) as repository:
                catalog, intents, previews, execution, _ = self._services(repository, fixture)
                _, preview = self._intent_and_preview(intents, previews)
                viewer = ResolvedApiPrincipal(
                    "viewer", "viewer-token", frozenset({ApiPermission.READ})
                )
                operator = ResolvedApiPrincipal(
                    "operator",
                    "operator-token",
                    frozenset(
                        {
                            ApiPermission.READ,
                            ApiPermission.SUBMIT_DRY_RUN,
                            ApiPermission.EXECUTE_MANUAL_ORGANIZE,
                        }
                    ),
                )
                api = MediaFlowApi(
                    repository,
                    None,
                    principals=(viewer, operator),
                    file_catalog=catalog,
                    manual_intent_service=intents,
                    manual_preview_service=previews,
                    manual_execution_service=execution,
                )
                item = preview.items[0]
                body = {
                    "expectedVersion": preview.intent_version,
                    "expectedItemVersions": {item.item_id: item.item_version},
                    "itemIds": [item.item_id],
                    "snapshotId": preview.configuration_snapshot_id,
                    "snapshotDigest": preview.configuration_snapshot_digest,
                    "confirmation": True,
                }
                status, denied = request(
                    api,
                    f"/api/v1/manual-previews/{preview.preview_id}/authorize",
                    method="POST",
                    body=body,
                    token="viewer-token",
                )
                self.assertEqual(403, status)
                self.assertEqual("forbidden", denied["error"]["code"])
                status, authority = request(
                    api,
                    f"/api/v1/manual-previews/{preview.preview_id}/authorize",
                    method="POST",
                    body=body,
                )
                self.assertEqual(201, status)
                status, execution_document = request(
                    api,
                    f"/api/v1/manual-execution-authorizations/{authority['authorizationId']}/execute",
                    method="POST",
                    body={"confirmation": True},
                )
                self.assertEqual(200, status)
                self.assertEqual("completed", execution_document["status"])
                status, reloaded = request(
                    api,
                    f"/api/v1/manual-executions/{execution_document['executionId']}",
                    token="viewer-token",
                )
                self.assertEqual(200, status)
                self.assertEqual(execution_document, reloaded)
                status, repeated = request(
                    api,
                    f"/api/v1/manual-execution-authorizations/{authority['authorizationId']}/execute",
                    method="POST",
                    body={"confirmation": True},
                )
                self.assertEqual(409, status)
                self.assertEqual("authorization_consumed", repeated["error"]["code"])
        finally:
            fixture.cleanup()


if __name__ == "__main__":
    unittest.main()
