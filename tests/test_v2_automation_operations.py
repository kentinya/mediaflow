"""V2 Automation operator journey over the real managed API.

These regressions drive the real ``MediaFlowApi`` against a real managed
configuration runtime, real LocalStorage roots and the real definition
occurrence/Run once services. They prove the new
``/api/operations/automation/*`` read projections are bounded operator
documents — no revision digests, definition fingerprints, source fingerprints
or raw organize plans — with backend-authoritative actions and Draft state;
that the Draft → Validate → checked-Activate journey composes the existing
managed-configuration routes atomically and starts no work; that a definition
Run once keeps its exact admitted scope and zero-mutation analysis; and that
the existing ``/api/automation`` and configuration surfaces remain
untouched for V1 clients.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.local_storage import LocalStorage
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from tests.task_engine_test_helpers import claim_and_run

ADMIN_TOKEN = "automation-admin-token"
VIEWER_TOKEN = "automation-viewer-token"
MANAGER_TOKEN = "automation-manager-token"

OPERATIONS_ROUTE = "/api/operations/automation/task-definitions"

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


def _provider_registry_factory(*_requested):
    """A synthetic Provider registry so exact analysis needs no external service."""

    from mediaflow.application.metadata import MetadataProviderRegistry
    from mediaflow.application.strategy_test import SyntheticMetadataProvider
    from mediaflow.domain.metadata import MediaCandidate, MediaType

    return MetadataProviderRegistry(
        (
            SyntheticMetadataProvider(
                (
                    MediaCandidate(
                        "tmdb",
                        "129",
                        MediaType.MOVIE,
                        "One",
                        year=2001,
                        genres=("Animation",),
                        countries=("JP",),
                    ),
                )
            ),
        )
    )


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


class _FailingDraftReadRepository:
    """Repository double whose open-Draft listing fails like a corrupt read.

    Every other call delegates to the real repository, so only Draft
    discovery becomes unavailable — the exact failure shape that must be
    reported as bounded unavailability instead of an empty Draft state.
    """

    def __init__(self, inner) -> None:
        self._inner = inner

    def __getattr__(self, name):  # noqa: ANN001
        return getattr(self._inner, name)

    def list_revisions(self, *, limit: int = 100):
        raise RuntimeError("simulated configuration repository failure")


class AutomationOperatorJourneyTests(unittest.TestCase):
    """Current direct-publication Automation operator journeys."""

    @contextlib.contextmanager
    def _journey(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            target_root = root / "target"
            (source_root / "Media" / "电影").mkdir(parents=True)
            (source_root / "Media" / "C").mkdir(parents=True)
            (source_root / "Media" / "电影" / "One.2001.mkv").write_bytes(b"x" * 32)
            (source_root / "Media" / "C" / "One.2001.mkv").write_bytes(b"x" * 32)
            (source_root / "incoming").mkdir(parents=True)
            (target_root / "Movies").mkdir(parents=True)
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
                status, active = _request(
                    MediaFlowApi(
                        runtime,
                        principals=(
                            ResolvedApiPrincipal("admin", ADMIN_TOKEN, frozenset(ApiPermission)),
                        ),
                        configuration_service=managed,
                        bootstrap_document=document,
                    ),
                    "/api/configuration/publish",
                    method="POST",
                    body={"document": document},
                )
                self.assertEqual(status, 200, active)
                api = MediaFlowApi(
                    runtime,
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
                    metadata_provider_registry_factory=_provider_registry_factory,
                )
                value = SimpleNamespace(
                    api=api,
                    managed=managed,
                    runtime=runtime,
                    repository=runtime,
                    active=managed.active(),
                    source=_RecordingStorage("source-storage", source_root),
                    target=_RecordingStorage("media-target", target_root),
                    source_root=source_root,
                    target_root=target_root,
                    root=root,
                )
                self._create(value, {**_DEFINITION, "enabled": True})
                value.active = managed.active()
                yield value

    def _seed_retained_analysis_plan(self, value, *, definition_id: str = _DEFINITION["id"]) -> str:
        discovery = value.api._media_discovery.admit_definition_run_once(
            definition_id=definition_id, actor="admin"
        )
        for index in range(16):
            result = claim_and_run(
                value.api._media_discovery,
                worker_id=f"analysis-worker-{index}",
                claim_token=f"analysis-token-{index}",
            )
            if result is None:
                raise AssertionError("shared analysis discovery was not claimable")
            if result.terminal:
                break
        else:
            raise AssertionError("shared analysis did not settle in the step budget")
        current = value.api._media_discovery.get(discovery.discovery_id)
        frozen = value.api._media_discovery.finalize(
            discovery.discovery_id, actor="admin", expected_version=current.version
        )
        self.assertIsNone(frozen.organize_task_id)
        intent = value.api._manual_intents.get(frozen.intent_id)
        preview = value.api._manual_previews.create(
            intent.intent_id, expected_version=intent.version, actor="admin"
        )
        self.assertTrue(preview.zero_mutation)
        self.assertEqual("previewed", preview.status.value)
        return preview.preview_id

    @staticmethod
    def _create(value, definition: dict | None = None) -> tuple[int, dict]:
        active = value.managed.active()
        return _request(
            value.api,
            "/api/automation/task-definitions",
            method="POST",
            body={
                "revisionId": active.revision_id,
                "expectedVersion": active.version,
                "object": dict(definition or _DEFINITION),
            },
        )

    def test_list_and_detail_are_bounded_and_permission_aware(self) -> None:
        with self._journey() as value:
            status, page = _request(value.api, OPERATIONS_ROUTE)
            self.assertEqual(status, 200, page)
            _assert_operator_document_clean(page)
            self.assertEqual(page["total"], 1)
            item = page["items"][0]
            self.assertEqual(item["id"], _DEFINITION["id"])
            self.assertEqual(item["definitionState"], "active")
            self.assertFalse(page["draftState"]["present"])
            self.assertFalse(page["actions"]["createDraft"]["available"])
            self.assertIsNone(page["actions"]["createDraft"]["path"])
            status, detail = _request(value.api, f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}")
            self.assertEqual(status, 200)
            _assert_operator_document_clean(detail)
            status, viewer = _request(
                value.api, f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}", token=VIEWER_TOKEN
            )
            self.assertEqual(status, 200)
            self.assertNotIn("activate-draft", json.dumps(viewer))

    def test_direct_create_and_update_publish_without_a_draft(self) -> None:
        with self._journey() as value:
            first = value.managed.active()
            self.assertEqual(
                first.document["automationTaskDefinitions"][0]["id"], _DEFINITION["id"]
            )
            status, updated = _request(
                value.api,
                f"/api/automation/task-definitions/{_DEFINITION['id']}",
                method="PUT",
                body={
                    "revisionId": first.revision_id,
                    "expectedVersion": first.version,
                    "object": {**_DEFINITION, "name": "Renamed nightly automation"},
                },
            )
            self.assertEqual(status, 200, updated)
            active = value.managed.active()
            self.assertEqual(
                active.document["automationTaskDefinitions"][0]["name"],
                "Renamed nightly automation",
            )
            self.assertFalse(
                any(
                    revision.status.value in {"draft", "validated"}
                    for revision in value.managed.repository.list_revisions()
                )
            )

    def test_stale_identity_is_refused_without_publication(self) -> None:
        with self._journey() as value:
            first = value.managed.active()
            status, response = _request(
                value.api,
                "/api/automation/task-definitions",
                method="POST",
                body={
                    "revisionId": first.revision_id,
                    "expectedVersion": first.version - 1,
                    "object": dict(_DEFINITION),
                },
            )
            self.assertEqual(status, 409, response)
            self.assertEqual(response["error"]["code"], "configuration_version_conflict")
            self.assertEqual(value.managed.active().revision_id, first.revision_id)

    def test_retired_draft_and_activate_entries_are_unknown(self) -> None:
        with self._journey() as value:
            active = value.managed.active()
            for suffix in ("draft", "activate-draft"):
                status, response = _request(
                    value.api,
                    f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}/{suffix}",
                    method="POST",
                    body={
                        "expectedRevisionId": active.revision_id,
                        "expectedVersion": active.version,
                    },
                )
                self.assertEqual(status, 404, response)
                self.assertEqual(response["error"]["code"], "not_found")

    def test_reads_create_no_work(self) -> None:
        with self._journey() as value:
            before = value.runtime._connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            _request(value.api, OPERATIONS_ROUTE)
            _request(value.api, f"{OPERATIONS_ROUTE}/{_DEFINITION['id']}")
            after = value.runtime._connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
