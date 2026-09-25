"""V2 Storage management operator journey over the real managed API.

These regressions drive the real ``MediaFlowApi`` against a real managed
configuration runtime. They prove the new
``/api/v1/operations/storage-management`` read projections are bounded,
secret-free, exact-Active operator documents — no revision digests, no
credential values, no raw provider exceptions — that distinguish a healthy
empty inventory from missing/unavailable/malformed authority; that the
explicit zero-mutation Connection/Read check binds to the exact Active
revision the operator inspected (stale identity is refused), persists bounded
evidence, and never claims write capability; that RBAC keeps viewers on
inspection only; and that no route scans recursively, calls a Metadata
Provider, creates Jobs/Tasks or mutates Storage content.
"""

from __future__ import annotations

import io
import json
import os
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.storage import (
    StorageCapabilities,
    StorageEntry,
    StorageEntryType,
    StorageError,
    StorageErrorCode,
)
from mediaflow.infrastructure.sqlite_configuration_management import (
    SQLiteConfigurationRepository,
)
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

ADMIN_TOKEN = "storage-admin-token"
VIEWER_TOKEN = "storage-viewer-token"

INVENTORY_ROUTE = "/api/v1/operations/storage-management/inventory"
DETAIL_ROUTE = "/api/v1/operations/storage-management/storage/{storage_id}"
CHECK_ROUTE = DETAIL_ROUTE + "/check"

_FORBIDDEN_SUBSTRINGS = (
    "Bearer ",
    "unit-secret",
    "unit-password",
    "private/root",
)


def _document(root: Path) -> dict:
    value = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
    value["persistence"]["databasePath"] = str(root / "configuration.sqlite3")
    value["storages"] = [
        {
            "id": "local-source",
            "name": "Local source",
            "type": "local",
            "rootPath": str(root / "local"),
            "readOnly": False,
            "enabled": True,
        },
        {
            "id": "nas",
            "name": "NAS",
            "type": "smb",
            "rootPath": "media",
            "readOnly": False,
            "enabled": True,
            "options": {
                "host": "nas.example",
                "share": "media",
                "usernameEnv": "MF_STORAGE_SMB_USER",
                "passwordEnv": "MF_STORAGE_SMB_PASSWORD",
            },
        },
        {
            "id": "r2-media",
            "name": "R2 media",
            "type": "r2",
            "rootPath": "media",
            "readOnly": True,
            "enabled": True,
            "options": {
                "bucket": "media",
                "endpoint": "https://r2.example",
                "accessKeyEnv": "MF_STORAGE_R2_ACCESS",
                "secretKeyEnv": "MF_STORAGE_R2_SECRET",
            },
        },
        {
            "id": "disabled-remote",
            "name": "Disabled remote",
            "type": "openlist",
            "rootPath": "/Media",
            "readOnly": False,
            "enabled": False,
            "options": {
                "baseUrl": "https://openlist.example",
                "tokenEnv": "MF_STORAGE_OPENLIST_TOKEN",
            },
        },
    ]
    value["resourceLibraries"][0]["storageId"] = "local-source"
    for library in value["mediaLibraries"]:
        library["storageId"] = "nas"
    value["automation"]["schedules"] = []
    return value


def _environment() -> dict[str, str]:
    return {
        "MF_STORAGE_SMB_USER": "unit-user",
        "MF_STORAGE_SMB_PASSWORD": "unit-password",
        "MF_STORAGE_R2_ACCESS": "unit-access",
        "MF_STORAGE_R2_SECRET": "unit-secret",
        "MF_STORAGE_OPENLIST_TOKEN": "unit-openlist-token",
    }


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


def _assert_document_clean(document: object) -> None:
    text = json.dumps(document, ensure_ascii=False)
    lowered = text.lower()
    for substring in _FORBIDDEN_SUBSTRINGS:
        assert substring.lower() not in lowered, f"operator document leaked {substring!r}"
    if isinstance(document, dict):
        for value in document.values():
            _assert_document_clean(value)


class FakeStorage:
    """Zero-mutation fake adapter with bounded read/mutation accounting."""

    def __init__(
        self,
        storage_id: str,
        *,
        read_only: bool = False,
        error: BaseException | None = None,
    ) -> None:
        self.storage_id = storage_id
        self.name = storage_id
        self.read_only = read_only
        self.capabilities = StorageCapabilities(
            can_move=not read_only,
            can_copy=not read_only,
            can_delete=not read_only,
            can_hard_link=False,
            can_soft_link=False,
        )
        self.error = error
        self.read_calls: list[tuple[str, str]] = []
        self.mutation_calls = {
            name: 0
            for name in (
                "write",
                "create_directory",
                "move",
                "copy",
                "delete",
                "hard_link",
                "soft_link",
            )
        }

    def _read(self, operation: str, path: str):
        self.read_calls.append((operation, path))
        if self.error is not None:
            raise self.error
        return StorageEntry(
            "",
            "",
            StorageEntryType.DIRECTORY,
            0,
            datetime.now(UTC),
        )

    def stat(self, path: str):
        return self._read("stat", path)

    def list(self, path: str):
        value = self._read("list", path)
        if isinstance(value, StorageEntry):
            return ()
        return value

    def exists(self, path: str) -> bool:
        self._read("exists", path)
        return True

    def read(self, path: str):
        self._read("read", path)
        return io.BytesIO(b"")

    def _mutate(self, operation: str, *_args, **_kwargs):
        self.mutation_calls[operation] += 1
        raise AssertionError(f"unexpected Storage mutation: {operation}")

    def write(self, *args, **kwargs):
        return self._mutate("write", *args, **kwargs)

    def create_directory(self, *args, **kwargs):
        return self._mutate("create_directory", *args, **kwargs)

    def move(self, *args, **kwargs):
        return self._mutate("move", *args, **kwargs)

    def copy(self, *args, **kwargs):
        return self._mutate("copy", *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self._mutate("delete", *args, **kwargs)

    def hard_link(self, *args, **kwargs):
        return self._mutate("hard_link", *args, **kwargs)

    def soft_link(self, *args, **kwargs):
        return self._mutate("soft_link", *args, **kwargs)


class StorageOperationsJourney(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "local").mkdir()
        self.nas = FakeStorage("nas")
        self.adapters = {"nas": self.nas}
        self.environment = patch.dict(os.environ, _environment(), clear=False)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.configuration_repository = SQLiteConfigurationRepository(
            self.root / "configuration.sqlite3"
        )
        self.configuration = ManagedConfigurationService(
            self.configuration_repository,
            bootstrap_database_path=str(self.root / "runtime.sqlite3"),
        )
        document = _document(self.root)
        document["persistence"]["databasePath"] = str(self.root / "runtime.sqlite3")
        self.objects = ConfigurationObjectService(
            self.configuration, storage_adapters=self.adapters
        )
        draft = self.configuration.import_draft(document, actor="bootstrap")
        validated = self.configuration.validate(draft.revision_id, actor="bootstrap")
        self.configuration.activate(
            validated.revision_id,
            expected_version=validated.version,
            actor="bootstrap",
        )
        self.repository = SQLiteTaskRepository(str(self.root / "runtime.sqlite3"))
        principals = (
            ResolvedApiPrincipal(ADMIN_TOKEN, ADMIN_TOKEN, frozenset(ApiPermission)),
            ResolvedApiPrincipal(VIEWER_TOKEN, VIEWER_TOKEN, frozenset({ApiPermission.READ})),
        )
        self.api = MediaFlowApi(
            self.repository,
            None,
            principals=principals,
            configuration_service=self.configuration,
            storage_adapters=self.adapters,
        )

    def tearDown(self) -> None:
        self.objects._setup_check_executor.shutdown(wait=True)
        self.repository.close()
        self.configuration_repository.close()
        self.directory.cleanup()

    # ------------------------------------------------------------------
    # Journey helpers

    def active_identity(self) -> dict:
        _status, inventory = _request(self.api, INVENTORY_ROUTE)
        assert inventory["available"], inventory
        return inventory["active"]

    def check_body(self, active: dict) -> dict:
        return {
            "expectedRevisionId": active["revisionId"],
            "expectedVersion": active["version"],
        }

    # ------------------------------------------------------------------
    # Inventory projection

    def test_inventory_is_exact_active_bounded_and_secret_free(self) -> None:
        status, inventory = _request(self.api, INVENTORY_ROUTE)
        self.assertEqual(status, 200)
        self.assertTrue(inventory["available"])
        self.assertEqual(inventory["authority"], "MANAGED")
        self.assertEqual(inventory["total"], 4)
        self.assertFalse(inventory["truncated"])
        self.assertEqual(
            inventory["families"],
            {"local": 1, "smb": 1, "openlist": 1, "s3": 1},
        )
        self.assertEqual(
            [item["id"] for item in inventory["items"]],
            ["disabled-remote", "local-source", "nas", "r2-media"],
        )
        self.assertEqual(
            [item["family"] for item in inventory["items"]],
            ["openlist", "local", "smb", "s3"],
        )
        by_id = {item["id"]: item for item in inventory["items"]}
        self.assertTrue(by_id["disabled-remote"]["enabled"] is False)
        self.assertTrue(by_id["r2-media"]["readOnly"] is True)
        # Local roots stay execution-environment paths; remote roots stay
        # provider-relative with bounded provider coordinates, and no secret
        # material of any kind crosses the projection.
        self.assertEqual(
            by_id["local-source"]["location"],
            {"kind": "local", "rootPath": str(self.root / "local")},
        )
        self.assertEqual(
            by_id["nas"]["location"],
            {
                "kind": "remote",
                "rootPath": "media",
                "host": "nas.example",
                "share": "media",
            },
        )
        self.assertEqual(
            by_id["r2-media"]["location"],
            {
                "kind": "remote",
                "rootPath": "media",
                "bucket": "media",
                "endpoint": "https://r2.example",
            },
        )
        # Enabled/read-only state, capability declarations and secret
        # readiness are reported truthfully and never conflated.
        self.assertFalse(by_id["r2-media"]["capabilities"]["can_delete"])
        self.assertFalse(by_id["r2-media"]["capabilitiesKnown"])
        self.assertEqual(by_id["nas"]["secretReadiness"][0]["state"], "SET")
        self.assertEqual(
            by_id["nas"]["secretReadiness"][1]["env"],
            "MF_STORAGE_SMB_PASSWORD",
        )
        self.assertNotIn("MF_STORAGE_SMB_PASSWORD", json.dumps(by_id["nas"]["location"]))
        self.assertNotIn("options", by_id["nas"])
        self.assertEqual(by_id["nas"]["writeCapabilityProbe"], "not_run")
        self.assertFalse(by_id["nas"]["capabilitiesKnown"])
        self.assertEqual(by_id["nas"]["writeCapabilitySource"], "unknown")
        # Reference counts include disabled dependents and stay exact.
        self.assertEqual(by_id["local-source"]["references"]["total"], 1)
        self.assertEqual(by_id["local-source"]["references"]["resourceLibraries"], 1)
        self.assertEqual(by_id["local-source"]["references"]["mediaLibraries"], 0)
        self.assertEqual(by_id["nas"]["references"]["mediaLibraries"], 2)
        self.assertEqual(by_id["disabled-remote"]["references"]["total"], 0)
        self.assertEqual(inventory["actions"]["check"]["available"], False)
        self.assertIsNotNone(inventory["actions"]["check"]["reason"])
        _assert_document_clean(inventory)

    def test_inventory_viewer_gets_read_only_actions_and_list_remains_visible(self) -> None:
        status, inventory = _request(self.api, INVENTORY_ROUTE, token=VIEWER_TOKEN)
        self.assertEqual(status, 200)
        self.assertTrue(inventory["available"])
        self.assertEqual(inventory["total"], 4)
        # Disabled Storage visibility follows backend permission: a viewer
        # still sees the disabled configured object because it holds read.
        self.assertIn("disabled-remote", [item["id"] for item in inventory["items"]])
        self.assertFalse(inventory["canManage"])
        _assert_document_clean(inventory)

    def test_inventory_rejects_methods_queries_and_unknown_routes(self) -> None:
        self.assertEqual(_request(self.api, INVENTORY_ROUTE, method="POST")[0], 405)
        status, denied = _request(self.api, INVENTORY_ROUTE, query="limit=10", token=VIEWER_TOKEN)
        self.assertEqual(status, 400)
        self.assertEqual(
            _request(self.api, "/api/v1/operations/storage-management", token=VIEWER_TOKEN)[0],
            404,
        )

    def test_inventory_without_active_and_setup_authority_is_not_an_empty_list(self) -> None:
        self.configuration_repository.close()
        self.repository.close()
        self.objects._setup_check_executor.shutdown(wait=True)
        self.directory.cleanup()
        # A fresh management-only bootstrap has no Active configuration.
        directory = tempfile.TemporaryDirectory()
        try:
            root = Path(directory.name)
            repository = SQLiteConfigurationRepository(root / "configuration.sqlite3")
            task_repository = SQLiteTaskRepository(str(root / "runtime.sqlite3"))
            configuration = ManagedConfigurationService(
                repository,
                bootstrap_database_path=str(root / "runtime.sqlite3"),
                bootstrap_document={"persistence": {"databasePath": str(root / "runtime.sqlite3")}},
                management_only=True,
            )
            admin = ResolvedApiPrincipal(ADMIN_TOKEN, ADMIN_TOKEN, frozenset(ApiPermission))
            api = MediaFlowApi(
                task_repository,
                None,
                principals=(admin,),
                configuration_service=configuration,
                bootstrap_document={"persistence": {"databasePath": str(root / "runtime.sqlite3")}},
                management_only=True,
            )
            try:
                status, inventory = _request(api, INVENTORY_ROUTE)
                self.assertEqual(status, 200)
                self.assertFalse(inventory["available"])
                self.assertEqual(inventory["reason"], "no_active")
                self.assertIsNone(inventory["authority"])
                self.assertEqual(inventory["items"], [])
                self.assertIsNotNone(inventory["actions"]["check"]["reason"])
                _assert_document_clean(inventory)
            finally:
                task_repository.close()
                repository.close()
        finally:
            directory.cleanup()

    # ------------------------------------------------------------------
    # Detail projection

    def test_detail_binds_references_capabilities_and_latest_check(self) -> None:
        detail_route = DETAIL_ROUTE.format(storage_id="nas")
        status, detail = _request(self.api, detail_route)
        self.assertEqual(status, 200)
        storage = detail["storage"]
        self.assertEqual(storage["id"], "nas")
        self.assertEqual(storage["type"], "smb")
        self.assertEqual(storage["family"], "smb")
        self.assertEqual(storage["location"]["host"], "nas.example")
        # The environment variable *name* is bounded configuration display;
        # no secret value, credential or raw option payload is ever returned.
        self.assertNotIn("unit-password", json.dumps(storage))
        self.assertNotIn("options", storage)
        self.assertNotIn("MF_STORAGE_SMB_PASSWORD", json.dumps(storage["location"]))
        summary = storage["references"]
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["resourceLibraries"], 0)
        self.assertEqual(summary["mediaLibraries"], 2)
        references = detail["references"]
        self.assertEqual(references["total"], 2)
        self.assertEqual(references["resourceLibraries"], [])
        self.assertEqual(len(references["mediaLibraries"]), 2)
        media_entries = references["mediaLibraries"]
        self.assertEqual(len(media_entries), 2)
        self.assertEqual(
            {item["id"] for item in media_entries},
            {"movies", "tv"},
        )
        # Latest check is absent before the first explicit check.
        self.assertIsNone(storage["latestCheck"])
        self.assertEqual(detail["activeConfiguration"]["status"], "active")
        self.assertNotIn("digest", json.dumps(detail["activeConfiguration"]))
        self.assertTrue(detail["actions"]["check"]["available"])
        self.assertEqual(detail["actions"]["check"]["method"], "POST")
        self.assertIn("/check", str(detail["actions"]["check"]["path"]))
        self.assertNotIn("expectedDigest", detail["actions"]["check"]["path"])
        _assert_document_clean(detail)

    def test_detail_uses_one_captured_active_identity_for_storage_and_authority(self) -> None:
        active = self.configuration.active()
        assert active is not None
        newer = replace(
            active,
            revision_id="a-different-active-revision",
            version=active.version + 1,
        )
        statuses: list[str] = []
        with patch.object(self.configuration, "active", side_effect=[active, newer]) as read_active:
            response = self.api._storage_detail_operator_document(
                "nas",
                lambda status, _headers: statuses.append(status),
                ResolvedApiPrincipal(ADMIN_TOKEN, ADMIN_TOKEN, frozenset(ApiPermission)),
            )
        self.assertEqual(statuses, ["200 OK"])
        detail = json.loads(b"".join(response))
        self.assertEqual(detail["activeConfiguration"]["revisionId"], active.revision_id)
        self.assertEqual(detail["storage"]["latestCheck"], None)
        self.assertEqual(read_active.call_count, 1)

    def test_reference_summary_counts_every_kind_when_breakdown_is_truncated(self) -> None:
        active = self.configuration.active()
        assert active is not None
        document = json.loads(json.dumps(active.document))
        document["mediaLibraries"].extend(
            {
                "id": f"archived-{index:02d}",
                "name": f"Archived {index:02d}",
                "storageId": "local-source",
                "rootPath": f"Archive/{index:02d}",
                "enabled": index % 2 == 0,
            }
            for index in range(40)
        )
        projected_revision = replace(active, document=document)
        summary = self.objects._storage_reference_document(
            projected_revision,
            "local-source",
        )
        detail = self.objects._storage_reference_detail(
            projected_revision,
            "local-source",
        )
        self.assertEqual(summary["total"], 41)
        self.assertEqual(summary["resourceLibraries"], 1)
        self.assertEqual(summary["mediaLibraries"], 40)
        self.assertTrue(summary["truncated"])
        self.assertEqual(len(detail["resourceLibraries"]), 1)
        self.assertEqual(len(detail["mediaLibraries"]), 32)
        self.assertTrue(detail["truncated"])

    def test_detail_reference_breakdown_includes_disabled_dependents_and_truncation(
        self,
    ) -> None:
        # Add a disabled MediaLibrary referencing the local Storage through the
        # exact Active successor; the breakdown must still count it.
        active_id = self.active_identity()["revisionId"]
        _status, draft = _request(
            self.api,
            f"/api/v1/configuration/revisions/{active_id}/successor",
            method="POST",
            body={},
        )
        revision_id = draft["revisionId"]
        _status, versioned = _request(
            self.api,
            f"/api/v1/configuration/revisions/{revision_id}/objects",
            token=ADMIN_TOKEN,
        )
        version = versioned["version"]
        _status, response = _request(
            self.api,
            f"/api/v1/configuration/revisions/{revision_id}/objects/mediaLibraries",
            method="POST",
            body={
                "object": {
                    "id": "archived-movies",
                    "name": "Archived movies",
                    "storageId": "local-source",
                    "rootPath": "Archive",
                    "enabled": False,
                },
                "expectedVersion": version,
            },
        )
        self.assertIn("version", response, response)
        # Activate the successor so the disabled dependent becomes part of the
        # exact Active configuration the detail projection reads.
        _status, _activated = _request(
            self.api,
            f"/api/v1/configuration/revisions/{revision_id}/validate",
            method="POST",
            body={},
        )
        _status, _activated = _request(
            self.api,
            f"/api/v1/configuration/revisions/{revision_id}/activate",
            method="POST",
            body={"expectedVersion": response["version"]},
        )
        detail_route = DETAIL_ROUTE.format(storage_id="local-source")
        status, detail = _request(self.api, detail_route)
        self.assertEqual(status, 200)
        references = detail["references"]
        self.assertEqual(references["total"], 2)
        self.assertEqual(references["resourceLibraries"][0]["id"], "source")
        self.assertEqual(len(references["mediaLibraries"]), 1)
        disabled_entry = references["mediaLibraries"][0]
        self.assertEqual(disabled_entry["id"], "archived-movies")
        self.assertFalse(disabled_entry["enabled"])

    def test_detail_unknown_storage_is_not_found_and_viewer_cannot_check(self) -> None:
        status, missing = _request(self.api, DETAIL_ROUTE.format(storage_id="missing-storage"))
        self.assertEqual(status, 404)
        self.assertEqual(missing["error"]["code"], "not_found")
        status, detail = _request(
            self.api,
            DETAIL_ROUTE.format(storage_id="nas"),
            token=VIEWER_TOKEN,
        )
        self.assertEqual(status, 200)
        self.assertFalse(detail["actions"]["check"]["available"])
        self.assertIn("manage_configuration", detail["actions"]["check"]["reason"])

    def test_detail_disabled_storage_withholds_check_without_hiding_configuration(
        self,
    ) -> None:
        status, detail = _request(self.api, DETAIL_ROUTE.format(storage_id="disabled-remote"))
        self.assertEqual(status, 200)
        self.assertTrue(detail["storage"]["enabled"] is False)
        self.assertFalse(detail["actions"]["check"]["available"])
        self.assertIn("disabled", detail["actions"]["check"]["reason"])
        _assert_document_clean(detail)

    # ------------------------------------------------------------------
    # Explicit zero-mutation read check

    def test_check_runs_against_exact_active_revision_and_persists_evidence(
        self,
    ) -> None:
        active = self.active_identity()
        check_route = CHECK_ROUTE.format(storage_id="nas")
        status, evidence = _request(
            self.api, check_route, method="POST", body=self.check_body(active)
        )
        self.assertEqual(status, 200)
        self.assertEqual(evidence["storageId"], "nas")
        self.assertEqual(evidence["status"], "passed")
        self.assertTrue(evidence["current"])
        self.assertFalse(evidence["stale"])
        self.assertEqual(evidence["operations"], ["stat:root", "list:root"])
        self.assertEqual(evidence["attemptedOperations"], evidence["operations"])
        self.assertEqual(evidence["sideEffects"], "none")
        self.assertTrue(evidence["retrySafe"])
        self.assertEqual(evidence["capabilityProbe"], "not_run")
        self.assertNotIn("nas.invalid", json.dumps(evidence))
        _assert_document_clean(evidence)
        self.assertEqual(
            self.nas.read_calls,
            [("stat", ""), ("list", "")],
        )
        self.assertEqual(set(self.nas.mutation_calls.values()), {0})
        # The persisted evidence is inspectable through the detail projection.
        status, detail = _request(self.api, DETAIL_ROUTE.format(storage_id="nas"))
        self.assertEqual(status, 200)
        latest = detail["storage"]["latestCheck"]
        self.assertIsNotNone(latest)
        self.assertEqual(latest["status"], "passed")
        self.assertTrue(latest["current"])
        self.assertTrue(detail["storage"]["capabilitiesKnown"])
        self.assertEqual(
            detail["storage"]["writeCapabilitySource"],
            "configured_storage_abstraction",
        )
        self.assertTrue(detail["storage"]["capabilities"]["can_move"])
        # The inventory itself performs no read against Storage.
        _request(self.api, INVENTORY_ROUTE)
        _request(self.api, DETAIL_ROUTE.format(storage_id="local-source"))
        self.assertEqual(
            self.nas.read_calls,
            [("stat", ""), ("list", "")],
        )

    def test_check_normalizes_provider_failures_without_leaking_details(self) -> None:
        failing = FakeStorage(
            "nas",
            error=StorageError(
                StorageErrorCode.AUTHENTICATION_FAILED,
                "list",
                "private/root",
                "raw provider secret unit-secret payload",
            ),
        )
        self.objects._storage_adapters["nas"] = failing
        self.adapters["nas"] = failing
        self.api._storage_adapters["nas"] = failing
        # The API owns its own ConfigurationObjectService built over the
        # adapters dict at init; swap the failing adapter into that instance's
        # adapter copy as well so the check path actually uses it.
        self.api._configuration_objects._storage_adapters["nas"] = failing
        active = self.active_identity()
        status, evidence = _request(
            self.api,
            CHECK_ROUTE.format(storage_id="nas"),
            method="POST",
            body=self.check_body(active),
        )
        self.assertEqual(status, 200)
        self.assertEqual(evidence["status"], "failed")
        self.assertEqual(evidence["failureCategory"], "authentication_failed")
        self.assertTrue(evidence["nextAction"])
        self.assertTrue(evidence["retrySafe"])
        _assert_document_clean(evidence)

    def test_check_stale_active_identity_is_refused_without_running(self) -> None:
        active = self.active_identity()
        stale_body = {
            "expectedRevisionId": "definitely-not-the-active-revision",
            "expectedVersion": active["version"],
        }
        status, conflict = _request(
            self.api,
            CHECK_ROUTE.format(storage_id="nas"),
            method="POST",
            body=stale_body,
        )
        self.assertEqual(status, 409)
        self.assertEqual(conflict["error"]["code"], "configuration_version_conflict")
        self.assertEqual(conflict["error"]["details"]["durableState"], "active_preserved")
        self.assertEqual(conflict["error"]["details"]["candidateState"], "not_run")
        self.assertEqual(self.nas.read_calls, [])

    def test_check_unknown_storage_is_not_found_and_viewers_cannot_start(self) -> None:
        active = self.active_identity()
        status, denied = _request(
            self.api,
            CHECK_ROUTE.format(storage_id="nas"),
            method="POST",
            body=self.check_body(active),
            token=VIEWER_TOKEN,
        )
        self.assertEqual(status, 403)
        self.assertEqual(denied["error"]["code"], "forbidden")
        status, missing = _request(
            self.api,
            CHECK_ROUTE.format(storage_id="missing-storage"),
            method="POST",
            body=self.check_body(active),
        )
        self.assertEqual(status, 404)
        self.assertEqual(self.nas.read_calls, [])
        status, invalid = _request(
            self.api,
            CHECK_ROUTE.format(storage_id="nas"),
            method="POST",
            body={"expectedRevisionId": active["revisionId"]},
        )
        self.assertEqual(status, 400)

    def test_check_disabled_storage_fails_closed_without_adapter_reads(self) -> None:
        active = self.active_identity()
        status, evidence = _request(
            self.api,
            CHECK_ROUTE.format(storage_id="disabled-remote"),
            method="POST",
            body=self.check_body(active),
        )
        self.assertEqual(status, 200)
        self.assertEqual(evidence["status"], "failed")
        self.assertEqual(evidence["failureCategory"], "disabled")
        self.assertTrue(evidence["nextAction"])
        _assert_document_clean(evidence)

    # ------------------------------------------------------------------
    # Regression isolation

    def test_existing_configuration_and_check_surfaces_remain_compatible(self) -> None:
        active = self.active_identity()
        # The V1/managed revision-object routes remain authoritative.
        status, revision = _request(
            self.api,
            f"/api/v1/configuration/revisions/{active['revisionId']}/objects/storages",
        )
        self.assertEqual(status, 200)
        self.assertEqual(revision["total"], 4)
        _status, collection = _request(
            self.api,
            f"/api/v1/configuration/revisions/{active['revisionId']}/storage-checks",
            token=VIEWER_TOKEN,
        )
        self.assertEqual(_status, 200)
        # The explicit check through the new surface persists evidence that the
        # existing revision-scoped read exposes.
        _status, evidence = _request(
            self.api,
            CHECK_ROUTE.format(storage_id="nas"),
            method="POST",
            body=self.check_body(active),
        )
        self.assertEqual(_status, 200)
        _status, document = _request(
            self.api,
            f"/api/v1/configuration/revisions/{active['revisionId']}/storage-checks/nas",
            token=VIEWER_TOKEN,
        )
        self.assertEqual(_status, 200)
        self.assertEqual(document["storageCheck"]["storageId"], "nas")

    def test_no_jobs_or_tasks_are_created_and_audit_routes_are_bounded(self) -> None:
        active = self.active_identity()
        _request(self.api, INVENTORY_ROUTE, token=VIEWER_TOKEN)
        _request(self.api, DETAIL_ROUTE.format(storage_id="nas"), token=VIEWER_TOKEN)
        _request(
            self.api,
            CHECK_ROUTE.format(storage_id="nas"),
            method="POST",
            body=self.check_body(active),
        )
        connection = sqlite3.connect(self.root / "runtime.sqlite3")
        try:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM automation_jobs").fetchone()[0],
                0,
            )
            routes = [
                row[0] for row in connection.execute("SELECT route FROM security_audit").fetchall()
            ]
            self.assertIn("/api/v1/operations/storage-management/inventory", routes)
            self.assertIn("/api/v1/operations/storage-management/storage/{id}", routes)
            self.assertIn("/api/v1/operations/storage-management/storage/{id}/check", routes)
            self.assertFalse(any("nas" in route for route in routes))
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
