"""V2 Automation operator journey over the real managed API.

These regressions drive the real ``MediaFlowApi`` against a real managed
configuration runtime, real LocalStorage roots and the real Automation
Preview/unattended-grant/occurrence services. They prove the new
``/api/v1/operations/automation/*`` read projections are bounded operator
documents — no revision digests, definition fingerprints, source fingerprints
or raw organize plans — with backend-authoritative actions and Draft state;
that the Draft → Validate → checked-Activate journey composes the existing
managed-configuration routes atomically and starts no work; that the exact
Preview is zero-mutation, paged and stale-aware; that unattended grants are
confirmed, bound and audited; and that the existing ``/api/v1/automation`` and
configuration surfaces remain untouched for V1 clients.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from mediaflow.application.automation import IntervalScheduler
from mediaflow.application.automation_task_definition_preview import (
    AutomationTaskDefinitionPreviewService,
)
from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.strategy_test import SyntheticMetadataProvider
from mediaflow.domain.automation import (
    AutomationTaskDefinition,
    SchedulerConfigurationSnapshot,
)
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

ADMIN_TOKEN = "automation-admin-token"
VIEWER_TOKEN = "automation-viewer-token"
MANAGER_TOKEN = "automation-manager-token"

OPERATIONS_ROUTE = "/api/v1/operations/automation/task-definitions"

_DEFINITION = {
    "id": "auto-task",
    "name": "Nightly automation",
    "resourceLibraryId": "source",
    "mode": "automatic-organization",
    "intervalSeconds": 3600,
    "itemLimit": 12,
}

_DIGEST_KEYS = (
    "digest",
    "configurationRevisionDigest",
    "configurationSnapshotDigest",
    "definitionFingerprint",
    "definitionCurrentFingerprint",
    "sourceFingerprint",
    "planFingerprint",
)
_FORBIDDEN_DOCUMENT_KEYS = (*_DIGEST_KEYS, "plan")
_FORBIDDEN_SUBSTRINGS = (
    "Bearer ",
    "apiKey",
    "authorization:",
    "executionPlan",
)


def _document(root: Path) -> dict:
    value = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
    value["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
    value["historyPath"] = str(root / "history.jsonl")
    value["storages"][0]["rootPath"] = str(root / "source")
    value["storages"][1]["rootPath"] = str(root / "target")
    # The current-configuration grant permission authority resolves principals
    # from the Active document, so the journey's granting principal must be
    # configured there with the admin role.
    value["api"]["principals"] = [
        {
            "id": "admin",
            "tokenEnv": "MEDIAFLOW_TEST_ADMIN_TOKEN",
            "roles": ["admin"],
            "enabled": True,
        }
    ]
    return value


def _request(
    api,
    path: str,
    *,
    method: str = "GET",
    body: object | None = None,
    token: str = ADMIN_TOKEN,
    query: str = "",
) -> tuple[int, object]:
    payload = b"" if body is None else json.dumps(body).encode("utf-8")
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": str(len(payload)),
        "wsgi.input": io.BytesIO(payload),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
    }
    result = b"".join(api(environ, lambda status, _headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(result)


def _assert_operator_document_clean(document: object) -> None:
    """No digest, fingerprint, raw plan, credential or exception evidence."""

    text = json.dumps(document, ensure_ascii=False)
    lowered = text.lower()
    for key in _FORBIDDEN_DOCUMENT_KEYS:
        assert f'"{key}"' not in text, f"operator document leaked {key}"
    for substring in _FORBIDDEN_SUBSTRINGS:
        assert substring.lower() not in lowered, f"operator document leaked {substring}"
    if isinstance(document, dict):
        for value in document.values():
            _assert_operator_document_clean(value)
    elif isinstance(document, list):
        for value in document:
            _assert_operator_document_clean(value)


class _RecordingStorage(LocalStorage):
    """LocalStorage passthrough that records every mutating call."""

    def __init__(self, storage_id: str, root: Path) -> None:
        super().__init__(storage_id, root)
        self.mutations: list[str] = []

    def write(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.mutations.append("write")
        return super().write(*args, **kwargs)

    def create_directory(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.mutations.append("create_directory")
        return super().create_directory(*args, **kwargs)

    def move(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.mutations.append("move")
        return super().move(*args, **kwargs)

    def copy(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.mutations.append("copy")
        return super().copy(*args, **kwargs)

    def delete(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.mutations.append("delete")
        return super().delete(*args, **kwargs)

    def hard_link(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.mutations.append("hard_link")
        return super().hard_link(*args, **kwargs)

    def soft_link(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.mutations.append("soft_link")
        return super().soft_link(*args, **kwargs)


class AutomationOperatorJourneyTests(unittest.TestCase):
    """Full-journey fixture shared by the V2 Automation operator regressions."""

    @contextlib.contextmanager
    def _journey(self):
        with tempfile.TemporaryDirectory() as directory:
            with tempfile.TemporaryDirectory() as target_directory:
                root = Path(directory)
                target_root = Path(target_directory)
                source_root = root / "source"
                (source_root / "Media" / "电影").mkdir(parents=True)
                (source_root / "Media" / "C").mkdir(parents=True)
                (source_root / "Media" / "电影" / "One.2001.mkv").write_bytes(b"x" * 32)
                (source_root / "Media" / "C" / "One.2001.mkv").write_bytes(b"x" * 32)
                document = _document(root)
                with (
                    SQLiteConfigurationRepository(
                        root / "configuration.sqlite3"
                    ) as configuration_repository,
                    SQLiteTaskRepository(root / "runtime.sqlite3") as runtime,
                ):
                    managed = ManagedConfigurationService(
                        configuration_repository,
                        bootstrap_database_path=str(root / "runtime.sqlite3"),
                    )
                    objects = ConfigurationObjectService(managed)
                    draft = managed.import_draft(document, actor="tester")
                    draft = objects.create_automation_task_definition(
                        draft.revision_id,
                        dict(_DEFINITION),
                        expected_version=draft.version,
                        actor="tester",
                    )
                    draft = objects.enable_automation_task_definition(
                        draft.revision_id,
                        _DEFINITION["id"],
                        expected_version=draft.version,
                        actor="tester",
                    )
                    validated = managed.validate(draft.revision_id, actor="tester")
                    active = managed.activate(
                        validated.revision_id,
                        expected_version=validated.version,
                        actor="tester",
                    )
                    source = _RecordingStorage("source-storage", source_root)
                    target = _RecordingStorage("media-target", target_root)
                    previews = AutomationTaskDefinitionPreviewService(
                        runtime,
                        managed,
                        providers=MetadataProviderRegistry(
                            (
                                SyntheticMetadataProvider(
                                    (
                                        MediaCandidate(
                                            "tmdb",
                                            "129",
                                            MediaType.MOVIE,
                                            "One",
                                            year=2001,
                                        ),
                                    )
                                ),
                            )
                        ),
                        storages={"source-storage": source, "media-target": target},
                    )
                    api = MediaFlowApi(
                        runtime,
                        None,
                        principals=(
                            ResolvedApiPrincipal("admin", ADMIN_TOKEN, frozenset(ApiPermission)),
                            ResolvedApiPrincipal(
                                "viewer", VIEWER_TOKEN, frozenset({ApiPermission.READ})
                            ),
                            ResolvedApiPrincipal(
                                "manager",
                                MANAGER_TOKEN,
                                frozenset(
                                    {
                                        ApiPermission.READ,
                                        ApiPermission.SUBMIT_DRY_RUN,
                                        ApiPermission.MANAGE_CONFIGURATION,
                                    }
                                ),
                            ),
                        ),
                        configuration_service=managed,
                        bootstrap_document=document,
                        automation_preview_service=previews,
                    )
                    yield SimpleNamespace(
                        api=api,
                        managed=managed,
                        objects=objects,
                        runtime=runtime,
                        active=active,
                        previews=previews,
                        source=source,
                        target=target,
                        source_root=source_root,
                        target_root=target_root,
                        root=root,
                    )

    def _snapshot(self, value) -> SchedulerConfigurationSnapshot:
        active = value.managed.active()
        definitions = tuple(
            AutomationTaskDefinition.from_document(item)
            for item in active.document.get("automationTaskDefinitions", [])
        )
        resources = tuple(
            item.get("id")
            for item in active.document.get("resourceLibraries", [])
            if isinstance(item, dict) and item.get("id")
        )
        return SchedulerConfigurationSnapshot(
            active.revision_id,
            active.digest,
            (),
            10,
            definitions,
            active.version,
            resources,
            resources,
        )

    def _action(self, document: dict, name: str) -> dict:
        actions = document["actions"]
        self.assertIn(name, actions)
        return actions[name]

    def test_operator_list_and_detail_are_bounded_and_permission_aware(self) -> None:
        with self._journey() as value:
            status, page = _request(value.api, OPERATIONS_ROUTE)
            self.assertEqual(status, 200)
            _assert_operator_document_clean(page)
            self.assertEqual(page["total"], 1)
            self.assertEqual(page["items"][0]["id"], _DEFINITION["id"])
            active_configuration = page["activeConfiguration"]
            self.assertEqual(active_configuration["status"], "active")
            self.assertEqual(active_configuration["revisionId"], value.active.revision_id)
            self.assertNotIn("digest", active_configuration)
            definition = page["items"][0]
            self.assertTrue(definition["enabled"])
            self.assertEqual(definition["mode"], "automatic-organization")
            self.assertEqual(definition["draftState"]["present"], False)
            detail_action = self._action(definition, "detail")
            self.assertEqual(detail_action["path"], f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}")
            self.assertEqual(detail_action["method"], "GET")
            preview_action = self._action(definition, "preview")
            self.assertEqual(
                preview_action["path"],
                f"/api/v1/automation/task-definitions/{_DEFINITION['id']}/preview",
            )
            grant_action = self._action(definition, "grant")
            self.assertTrue(grant_action["available"])
            self.assertTrue(grant_action["requiresConfirmation"])
            self.assertEqual(
                grant_action["path"],
                f"/api/v1/automation/task-definitions/{_DEFINITION['id']}/grant",
            )
            copy_action = self._action(definition, "copy")
            self.assertFalse(copy_action["available"])
            self.assertIn("successor Draft", copy_action["reason"])
            self.assertEqual(
                self._action(definition, "occurrences")["path"],
                f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}/occurrences",
            )
            self.assertIn("nextRunAt", definition)

            status, viewer_page = _request(value.api, OPERATIONS_ROUTE, token=VIEWER_TOKEN)
            self.assertEqual(status, 200)
            viewer_definition = viewer_page["items"][0]
            self.assertFalse(self._action(viewer_definition, "preview")["available"])
            self.assertIn(
                "required permission",
                self._action(viewer_definition, "preview")["reason"],
            )
            self.assertFalse(self._action(viewer_definition, "grant")["available"])
            self.assertFalse(viewer_page["actions"]["create"]["available"])
            self.assertFalse(viewer_page["actions"]["createDraft"]["available"])

            status, detail = _request(value.api, f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}")
            self.assertEqual(status, 200)
            _assert_operator_document_clean(detail)
            operator = detail["definition"]
            self.assertEqual(operator["id"], _DEFINITION["id"])
            self.assertEqual(
                operator["activeConfiguration"]["revisionId"], value.active.revision_id
            )
            self.assertIn("occurrenceState", operator)
            self.assertIn("unattendedExecutionGrant", operator)
            eligibility = operator["grantEligibility"]
            self.assertEqual(eligibility["eligible"], False)
            self.assertEqual(eligibility["status"], "ineligible")
            self.assertIsNotNone(eligibility["nextAction"])

    def test_draft_journey_composes_existing_routes_atomically(self) -> None:
        with self._journey() as value:
            status, draft = _request(value.api, f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}/draft")
            self.assertEqual(status, 200)
            _assert_operator_document_clean(draft)
            self.assertIsNone(draft["draft"])
            create_action = self._action(draft, "createDraft")
            self.assertTrue(create_action["available"])
            self.assertEqual(
                create_action["path"],
                f"/api/v1/configuration/revisions/{value.active.revision_id}/successor",
            )
            for name in ("save", "validate", "activate"):
                self.assertFalse(self._action(draft, name)["available"])

            status, created = _request(
                value.api,
                create_action["path"],
                method="POST",
                body={"expectedActiveRevisionId": value.active.revision_id},
            )
            self.assertEqual(status, 201)
            revision_id = created["revisionId"]

            status, draft = _request(value.api, f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}/draft")
            self.assertEqual(status, 200)
            self.assertIsNotNone(draft["draft"])
            self.assertEqual(draft["draft"]["revisionId"], revision_id)
            self.assertEqual(draft["draft"]["definition"]["id"], _DEFINITION["id"])
            self.assertIn("resourceLibraryOptions", draft)
            options = {item["id"]: item for item in draft["resourceLibraryOptions"]}
            self.assertTrue(options["source"]["enabled"])
            save_action = self._action(draft, "save")
            self.assertEqual(save_action["method"], "PUT")
            self.assertEqual(
                save_action["path"],
                f"/api/v1/configuration/revisions/{revision_id}/objects/"
                f"automationTaskDefinitions/{_DEFINITION['id']}",
            )
            activate_action = self._action(draft, "activate")
            self.assertTrue(activate_action["requiresConfirmation"])

            edited = dict(draft["draft"]["definition"])
            edited["name"] = "Renamed nightly automation"
            edited["itemLimit"] = 7
            status, saved = _request(
                value.api,
                save_action["path"],
                method="PUT",
                body={"object": edited, "expectedVersion": draft["draft"]["revisionVersion"]},
            )
            self.assertEqual(status, 200)
            new_version = saved["version"]
            self.assertEqual(saved["automationTaskDefinition"]["itemLimit"], 7)

            stale = dict(edited)
            stale["name"] = "Stale write"
            status, _conflict = _request(
                value.api,
                save_action["path"],
                method="PUT",
                body={
                    "object": stale,
                    "expectedVersion": draft["draft"]["revisionVersion"],
                },
            )
            self.assertEqual(status, 409)
            status, reread = _request(value.api, f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}/draft")
            self.assertEqual(reread["draft"]["definition"]["name"], "Renamed nightly automation")

            validate_action = self._action(reread, "validate")
            status, validated = _request(value.api, validate_action["path"], method="POST", body={})
            self.assertEqual(status, 200)
            self.assertEqual(validated["validationErrors"], [])

            status, activated = _request(
                value.api,
                self._action(reread, "activate")["path"],
                method="POST",
                body={"expectedVersion": new_version},
            )
            self.assertEqual(status, 200)
            self.assertNotEqual(activated["revisionId"], value.active.revision_id)

            status, detail = _request(value.api, f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}")
            self.assertEqual(status, 200)
            self.assertEqual(detail["definition"]["name"], "Renamed nightly automation")
            self.assertEqual(detail["definition"]["itemLimit"], 7)
            self.assertEqual(detail["activeConfiguration"]["revisionId"], activated["revisionId"])
            self.assertEqual(detail["definition"]["draftState"]["present"], False)

    def test_definition_mutations_are_permission_bound(self) -> None:
        with self._journey() as value:
            status, draft = _request(value.api, f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}/draft")
            create_action = self._action(draft, "createDraft")
            _status, _created = _request(
                value.api,
                create_action["path"],
                method="POST",
                body={"expectedActiveRevisionId": value.active.revision_id},
            )
            status, draft = _request(value.api, f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}/draft")
            save_action = self._action(draft, "save")
            edited = dict(draft["draft"]["definition"])
            edited["name"] = "Manager rename"
            status, _saved = _request(
                value.api,
                save_action["path"],
                method="PUT",
                token=MANAGER_TOKEN,
                body={
                    "object": edited,
                    "expectedVersion": draft["draft"]["revisionVersion"],
                },
            )
            self.assertEqual(status, 200)
            status, _denied = _request(
                value.api,
                save_action["path"],
                method="PUT",
                token=VIEWER_TOKEN,
                body={"object": edited, "expectedVersion": draft["draft"]["revisionVersion"] + 1},
            )
            self.assertEqual(status, 403)
            status, viewer_draft = _request(
                value.api,
                f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}/draft",
                token=VIEWER_TOKEN,
            )
            self.assertEqual(status, 200)
            self.assertFalse(self._action(viewer_draft, "save")["available"])
            self.assertFalse(self._action(viewer_draft, "activate")["available"])
            self.assertFalse(self._action(viewer_draft, "createDraft")["available"])

    def test_preview_is_exact_zero_mutation_paged_and_bounded(self) -> None:
        with self._journey() as value:
            status, created = _request(
                value.api,
                f"/api/v1/automation/task-definitions/{_DEFINITION['id']}/preview",
                method="POST",
                body={},
            )
            self.assertEqual(status, 201)
            preview_id = created["previewId"]
            self.assertEqual(value.source.mutations, [])
            self.assertEqual(value.target.mutations, [])

            status, preview = _request(
                value.api,
                f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}/previews/{preview_id}",
            )
            self.assertEqual(status, 200)
            _assert_operator_document_clean(preview)
            self.assertEqual(preview["status"], "previewed")
            self.assertTrue(preview["zeroMutation"])
            self.assertEqual(preview["sideEffects"], "none")
            self.assertTrue(preview["current"])
            self.assertEqual(preview["counts"]["discovered"], 2)
            self.assertEqual(preview["itemTotal"], 2)
            self.assertEqual(preview["configurationRevisionId"], value.active.revision_id)
            grant_action = self._action(preview, "grant")
            self.assertTrue(grant_action["available"])
            self.assertTrue(preview["grantEligibility"]["eligible"])
            items_action = self._action(preview, "items")
            self.assertEqual(
                items_action["path"],
                f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}/previews/{preview_id}/items",
            )
            items_by_recognition = {
                item["recognition"]["recognitionTypeId"]: item for item in preview["items"]
            }
            movie_item = items_by_recognition["A"]
            self.assertEqual(movie_item["status"], "previewed")
            self.assertIn("One (2001)", movie_item["naming"]["directory"])
            self.assertIn("One (2001)", movie_item["naming"]["filename"])
            self.assertEqual(movie_item["destination"]["storageId"], "media-target")
            # RecognitionType C stays C even with the A naming/classification
            # policies its RecognitionTypePolicy selects.
            special_item = items_by_recognition["C"]
            self.assertEqual(special_item["status"], "previewed")
            self.assertIn("/C/", special_item["source"]["path"])

            status, page = _request(
                value.api,
                items_action["path"],
                query="limit=1",
            )
            self.assertEqual(status, 200)
            self.assertEqual(len(page["items"]), 1)
            self.assertEqual(page["total"], 2)
            self.assertEqual(page["nextAfter"], 1)
            _assert_operator_document_clean(page)
            status, second_page = _request(
                value.api,
                items_action["path"],
                query="limit=1&after=1",
            )
            self.assertEqual(status, 200)
            self.assertEqual(len(second_page["items"]), 1)
            self.assertIsNone(second_page["nextAfter"])
            self.assertNotEqual(
                page["items"][0]["previewItemId"],
                second_page["items"][0]["previewItemId"],
            )

            status, mismatch = _request(
                value.api,
                f"{OPERATIONS_ROUTE}/other-definition/previews/{preview_id}",
            )
            self.assertEqual(status, 404)

    def test_grant_requires_confirmation_is_bound_and_revocation_is_exact(self) -> None:
        with self._journey() as value:
            _status, preview = _request(
                value.api,
                f"/api/v1/automation/task-definitions/{_DEFINITION['id']}/preview",
                method="POST",
                body={},
            )
            preview_id = preview["previewId"]
            grant_path = f"/api/v1/automation/task-definitions/{_DEFINITION['id']}/grant"

            status, _rejected = _request(
                value.api, grant_path, method="POST", body={"confirmation": False}
            )
            self.assertIn(status, (400, 409))

            status, viewer_denied = _request(
                value.api,
                grant_path,
                method="POST",
                token=VIEWER_TOKEN,
                body={"confirmation": True},
            )
            self.assertEqual(status, 403)

            status, granted = _request(
                value.api,
                grant_path,
                method="POST",
                body={"confirmation": True, "previewId": preview_id},
            )
            self.assertEqual(status, 201)
            grant = granted["grant"]
            self.assertEqual(grant["status"], "active")
            self.assertTrue(grant["active"])
            self.assertEqual(grant["previewId"], preview_id)
            self.assertEqual(grant["definitionId"], _DEFINITION["id"])

            status, state = _request(
                value.api,
                f"/api/v1/automation/task-definitions/{_DEFINITION['id']}/grant-state",
            )
            self.assertEqual(status, 200)
            self.assertEqual(state["grant"]["status"], "active")
            self.assertTrue(state["grantEligibility"]["eligible"])

            status, audit = _request(
                value.api,
                f"/api/v1/automation/task-definitions/{_DEFINITION['id']}/grant/audit",
            )
            self.assertEqual(status, 200)
            self.assertTrue(any(item["action"] == "granted" for item in audit["items"]))

            status, revoked = _request(
                value.api,
                f"/api/v1/automation/task-definitions/{_DEFINITION['id']}/revoke",
                method="POST",
                body={"reason": "bounds no longer wanted"},
            )
            self.assertEqual(status, 200)
            self.assertEqual(revoked["grant"]["status"], "revoked")
            self.assertFalse(revoked["grant"]["active"])

            status, state = _request(
                value.api,
                f"/api/v1/automation/task-definitions/{_DEFINITION['id']}/grant-state",
            )
            self.assertEqual(state["grant"]["status"], "revoked")
            self.assertFalse(state["grant"]["active"])

    def test_preview_staleness_blocks_unattended_authority(self) -> None:
        with self._journey() as value:
            _status, preview = _request(
                value.api,
                f"/api/v1/automation/task-definitions/{_DEFINITION['id']}/preview",
                method="POST",
                body={},
            )
            preview_id = preview["previewId"]

            status, draft = _request(value.api, f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}/draft")
            _status, _created = _request(
                value.api,
                self._action(draft, "createDraft")["path"],
                method="POST",
                body={"expectedActiveRevisionId": value.active.revision_id},
            )
            status, draft = _request(value.api, f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}/draft")
            edited = dict(draft["draft"]["definition"])
            edited["itemLimit"] = 5
            _status, saved = _request(
                value.api,
                self._action(draft, "save")["path"],
                method="PUT",
                body={
                    "object": edited,
                    "expectedVersion": draft["draft"]["revisionVersion"],
                },
            )
            _status, _validated = _request(
                value.api,
                self._action(draft, "validate")["path"],
                method="POST",
                body={},
            )
            _status, _activated = _request(
                value.api,
                self._action(draft, "activate")["path"],
                method="POST",
                body={"expectedVersion": saved["version"]},
            )

            status, reread = _request(
                value.api,
                f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}/previews/{preview_id}",
            )
            self.assertEqual(status, 200)
            self.assertFalse(reread["current"])
            self.assertIsNotNone(reread["staleReason"])
            grant_action = self._action(reread, "grant")
            self.assertFalse(grant_action["available"])
            self.assertIn("fresh exact Preview", grant_action["reason"])
            self.assertEqual(reread["grantEligibility"]["eligible"], False)

            status, denied = _request(
                value.api,
                f"/api/v1/automation/task-definitions/{_DEFINITION['id']}/grant",
                method="POST",
                body={"confirmation": True, "previewId": preview_id},
            )
            self.assertEqual(status, 409)

    def test_checked_activation_starts_no_work_and_occurrences_link_work(self) -> None:
        with self._journey() as value:
            scheduler = IntervalScheduler(
                value.runtime,
                (),
                configuration_snapshot_resolver=lambda: self._snapshot(value),
            )
            emitted = scheduler.tick(datetime.now(UTC) + timedelta(seconds=1))
            self.assertEqual(len(emitted), 1)
            jobs_after_tick = len(value.runtime.list_jobs())

            status, occurrences = _request(
                value.api, f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}/occurrences"
            )
            self.assertEqual(status, 200)
            _assert_operator_document_clean(occurrences)
            self.assertEqual(len(occurrences["items"]), 1)
            occurrence = occurrences["items"][0]
            self.assertEqual(occurrence["definitionId"], _DEFINITION["id"])
            self.assertEqual(occurrence["jobId"], emitted[0].job_id)
            self.assertIsNone(occurrence["taskId"])
            self.assertEqual(occurrence["outcome"], "emitted")
            self.assertIn("job", occurrence["actions"])
            self.assertNotIn("task", occurrence["actions"])
            self.assertEqual(
                occurrence["actions"]["job"]["path"],
                f"/api/v1/operations/jobs/{emitted[0].job_id}",
            )
            self.assertEqual(occurrence["configurationRevisionId"], value.active.revision_id)
            self.assertNotIn("digest", json.dumps(occurrence))

            status, _reread = _request(
                value.api, f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}/occurrences"
            )
            self.assertEqual(status, 200)
            self.assertEqual(len(value.runtime.list_jobs()), jobs_after_tick)

            _status, _preview = _request(
                value.api,
                f"/api/v1/automation/task-definitions/{_DEFINITION['id']}/preview",
                method="POST",
            )
            status, draft = _request(value.api, f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}/draft")
            _status, _created = _request(
                value.api,
                self._action(draft, "createDraft")["path"],
                method="POST",
                body={"expectedActiveRevisionId": value.active.revision_id},
            )
            status, draft = _request(value.api, f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}/draft")
            _status, _validated = _request(
                value.api,
                self._action(draft, "validate")["path"],
                method="POST",
                body={},
            )
            _status, _activated = _request(
                value.api,
                self._action(draft, "activate")["path"],
                method="POST",
                body={"expectedVersion": draft["draft"]["revisionVersion"]},
            )
            self.assertEqual(len(value.runtime.list_jobs()), jobs_after_tick)
            self.assertEqual(value.source.mutations, [])
            self.assertEqual(value.target.mutations, [])

    def test_v1_automation_surfaces_remain_compatible(self) -> None:
        with self._journey() as value:
            status, legacy = _request(value.api, "/api/v1/automation/task-definitions")
            self.assertEqual(status, 200)
            self.assertIn("configuration", legacy)
            self.assertIn("digest", legacy["configuration"])
            self.assertEqual(legacy["items"][0]["id"], _DEFINITION["id"])
            self.assertIn("definitionFingerprint", legacy["items"][0])

            status, legacy_detail = _request(
                value.api, f"/api/v1/automation/task-definitions/{_DEFINITION['id']}"
            )
            self.assertEqual(status, 200)
            self.assertIn("configuration", legacy_detail)
            self.assertIn("definitionFingerprint", legacy_detail["definition"])

            status, jobs = _request(value.api, "/api/v1/jobs")
            self.assertEqual(status, 200)
            self.assertEqual(jobs["items"], [])


if __name__ == "__main__":
    unittest.main()
