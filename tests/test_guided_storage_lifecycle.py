from __future__ import annotations

import copy
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.configuration_management import (
    ConfigurationObjectKind,
    ConfigurationVersionConflict,
)
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.runtime_configuration import load_managed_runtime_configuration
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import APP_JS
from mediaflow.interfaces.service_api import MediaFlowApi


def request(
    api,
    path: str,
    *,
    method: str = "GET",
    body: object | None = None,
    token: str = "admin-token",
) -> tuple[int, dict]:
    payload = b"" if body is None else json.dumps(body).encode("utf-8")
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
    result = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(result)


def minimal_bootstrap(root: Path) -> dict[str, object]:
    return {
        "version": 1,
        "persistence": {"databasePath": str(root / "configuration.sqlite3")},
        "api": {"principals": [{"id": "admin", "tokenEnv": "MF_GUIDED_ADMIN", "roles": ["admin"]}]},
    }


def complete_document(root: Path) -> dict[str, object]:
    document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
    document["persistence"]["databasePath"] = str(root / "configuration.sqlite3")
    document["storages"][0]["rootPath"] = str(root / "source")
    document["storages"][1]["rootPath"] = str(root / "target")
    document["resourceLibraries"][0]["storagePath"] = "incoming"
    document["mediaLibraries"][0]["rootPath"] = "Movies"
    return document


class GuidedStorageLifecycleTests(unittest.TestCase):
    def _api(self, repository, runtime_repository, service, bootstrap):
        admin = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
        viewer = ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
        return MediaFlowApi(
            runtime_repository,
            None,
            principals=(admin, viewer),
            configuration_service=service,
            bootstrap_document=bootstrap,
            management_only=True,
        )

    @staticmethod
    def _storage_values(root: Path) -> list[dict[str, object]]:
        return [
            {
                "id": "local-guided",
                "name": "Guided Local",
                "type": "local",
                "rootPath": str(root / "local"),
                "readOnly": True,
            },
            {
                "id": "smb-guided",
                "name": "Guided SMB",
                "type": "smb",
                "rootPath": "media",
                "readOnly": True,
                "options": {
                    "usernameEnv": "MF_GUIDED_SMB_USER",
                    "passwordEnv": "MF_GUIDED_SMB_PASSWORD",
                    "host": "nas.example.invalid",
                    "share": "Media",
                    "domain": "WORKGROUP",
                    "port": 445,
                },
            },
            {
                "id": "openlist-guided",
                "name": "Guided OpenList",
                "type": "openlist",
                "rootPath": "/Media",
                "options": {
                    "tokenEnv": "MF_GUIDED_OPENLIST_TOKEN",
                    "baseUrl": "https://openlist.example.invalid",
                },
            },
            {
                "id": "s3-guided",
                "name": "Guided AWS S3",
                "type": "s3",
                "rootPath": "incoming",
                "options": {
                    "accessKeyEnv": "MF_GUIDED_S3_ACCESS",
                    "secretKeyEnv": "MF_GUIDED_S3_SECRET",
                    "bucket": "media-bucket",
                    "region": "us-east-1",
                },
            },
            {
                "id": "r2-guided",
                "name": "Guided R2",
                "type": "r2",
                "rootPath": "incoming",
                "options": {
                    "accessKeyEnv": "MF_GUIDED_R2_ACCESS",
                    "secretKeyEnv": "MF_GUIDED_R2_SECRET",
                    "bucket": "media-bucket",
                    "endpoint": "https://r2.example.invalid",
                },
            },
            {
                "id": "compatible-guided",
                "name": "Guided S3 Compatible",
                "type": "s3-compatible",
                "rootPath": "incoming",
                "options": {
                    "accessKeyEnv": "MF_GUIDED_COMPAT_ACCESS",
                    "secretKeyEnv": "MF_GUIDED_COMPAT_SECRET",
                    "sessionTokenEnv": "MF_GUIDED_COMPAT_SESSION",
                    "bucket": "media-bucket",
                    "endpoint": "https://s3-compatible.example.invalid",
                    "forcePathStyle": True,
                },
            },
        ]

    def test_all_kinds_api_rbac_readiness_defaults_and_no_external_operation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bootstrap = minimal_bootstrap(root)
            env_values = {
                "MF_GUIDED_OPENLIST_TOKEN": f"value-{uuid4().hex}",
                "MF_GUIDED_SMB_USER": f"value-{uuid4().hex}",
                "MF_GUIDED_S3_ACCESS": f"value-{uuid4().hex}",
                "MF_GUIDED_R2_SECRET": f"value-{uuid4().hex}",
                "MF_GUIDED_COMPAT_ACCESS": f"value-{uuid4().hex}",
            }
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(
                    repository,
                    bootstrap_document=bootstrap,
                    management_only=True,
                )
                api = self._api(repository, runtime_repository, service, bootstrap)
                with (
                    patch.dict(os.environ, env_values) as environment,
                    patch(
                        "mediaflow.infrastructure.local_storage.LocalStorage",
                        side_effect=AssertionError("Storage constructor reached"),
                    ),
                    patch(
                        "mediaflow.infrastructure.smb_storage.SMBStorage",
                        side_effect=AssertionError("Storage constructor reached"),
                    ),
                    patch(
                        "mediaflow.infrastructure.openlist_storage.OpenListStorage",
                        side_effect=AssertionError("Storage constructor reached"),
                    ),
                    patch(
                        "mediaflow.infrastructure.s3_storage.S3Storage",
                        side_effect=AssertionError("Storage constructor reached"),
                    ),
                    patch(
                        "socket.socket",
                        side_effect=AssertionError("network constructor reached"),
                    ),
                ):
                    environment.pop("MF_GUIDED_SMB_PASSWORD", None)
                    status, draft = request(
                        api,
                        "/api/v1/configuration/drafts/first",
                        method="POST",
                        body={},
                    )
                    self.assertEqual(status, 201)
                    revision_id = draft["revisionId"]
                    version = draft["version"]
                    for value in self._storage_values(root):
                        status, result = request(
                            api,
                            f"/api/v1/configuration/revisions/{revision_id}/objects/storages",
                            method="POST",
                            body={"expectedVersion": version, "object": value},
                        )
                        self.assertEqual(status, 200)
                        self.assertEqual(result["storage"]["id"], value["id"])
                        self.assertEqual(result["storage"]["type"], value["type"])
                        self.assertEqual(result["storage"]["editability"], "guided")
                        version = result["version"]

                    status, detail = request(
                        api,
                        f"/api/v1/configuration/revisions/{revision_id}/objects",
                    )
                    self.assertEqual(status, 200)
                    items = detail["objects"]["storages"]
                    self.assertEqual(
                        {item["type"] for item in items},
                        {"local", "smb", "openlist", "s3", "r2", "s3-compatible"},
                    )
                    by_id = {item["id"]: item for item in items}
                    self.assertEqual(by_id["openlist-guided"]["options"]["pageSize"], 100)
                    self.assertEqual(by_id["smb-guided"]["options"]["operationTimeout"], 60)
                    self.assertEqual(by_id["s3-guided"]["options"]["pageSize"], 1000)
                    self.assertFalse(by_id["local-guided"]["secretReadiness"])
                    readiness = {
                        entry["field"]: entry["state"]
                        for entry in by_id["smb-guided"]["secretReadiness"]
                    }
                    self.assertEqual(readiness, {"usernameEnv": "SET", "passwordEnv": "UNSET"})

                    status, inspected = request(
                        api,
                        f"/api/v1/configuration/revisions/{revision_id}/objects/storages/s3-guided",
                    )
                    self.assertEqual(status, 200)
                    self.assertEqual(inspected["storage"], by_id["s3-guided"])
                    status, collection = request(
                        api,
                        f"/api/v1/configuration/revisions/{revision_id}/objects/storages",
                        token="viewer-token",
                    )
                    self.assertEqual(status, 200)
                    self.assertEqual(collection["total"], 6)
                    status, denied = request(
                        api,
                        f"/api/v1/configuration/revisions/{revision_id}/objects/storages",
                        method="POST",
                        body={
                            "expectedVersion": version,
                            "object": {
                                "id": "viewer-storage",
                                "name": "Viewer",
                                "type": "local",
                                "rootPath": str(root / "viewer"),
                            },
                        },
                        token="viewer-token",
                    )
                    self.assertEqual(status, 403)
                    self.assertEqual(denied["error"]["code"], "forbidden")

                    blob = json.dumps(detail, sort_keys=True)
                    for secret in env_values.values():
                        self.assertNotIn(secret, blob)

    def test_storage_lifecycle_copy_edit_enable_disable_and_stale_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bootstrap = minimal_bootstrap(root)
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(
                    repository,
                    bootstrap_document=bootstrap,
                    management_only=True,
                )
                api = self._api(repository, runtime_repository, service, bootstrap)
                _, draft = request(
                    api,
                    "/api/v1/configuration/drafts/first",
                    method="POST",
                    body={},
                )
                value = self._storage_values(root)[-1]
                status, created = request(
                    api,
                    f"/api/v1/configuration/revisions/{draft['revisionId']}/objects/storages",
                    method="POST",
                    body={"expectedVersion": draft["version"], "object": value},
                )
                self.assertEqual(status, 200)
                revision_id = draft["revisionId"]
                status, copied = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/storages/{value['id']}/copy",
                    method="POST",
                    body={"expectedVersion": created["version"]},
                )
                self.assertEqual(status, 200)
                self.assertEqual(copied["storage"]["id"], "compatible-guided-copy")
                self.assertFalse(copied["storage"]["enabled"])
                self.assertEqual(copied["storage"]["type"], value["type"])
                status, copied_again = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/storages/{value['id']}/copy",
                    method="POST",
                    body={"expectedVersion": copied["version"]},
                )
                self.assertEqual(status, 200)
                self.assertEqual(copied_again["storage"]["id"], "compatible-guided-copy-2")

                edited = copy.deepcopy(copied["storage"])
                edited["name"] = "Edited compatible"
                status, changed = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/storages/{edited['id']}",
                    method="PUT",
                    body={"expectedVersion": copied_again["version"], "object": edited},
                )
                self.assertEqual(status, 200)
                self.assertEqual(changed["storage"]["name"], "Edited compatible")
                status, enabled = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/storages/{edited['id']}/enable",
                    method="POST",
                    body={"expectedVersion": changed["version"]},
                )
                self.assertEqual(status, 200)
                self.assertTrue(enabled["storage"]["enabled"])
                status, disabled = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/storages/{edited['id']}/disable",
                    method="POST",
                    body={"expectedVersion": enabled["version"]},
                )
                self.assertEqual(status, 200)
                self.assertFalse(disabled["storage"]["enabled"])
                status, stale = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/storages/{edited['id']}/enable",
                    method="POST",
                    body={"expectedVersion": enabled["version"]},
                )
                self.assertEqual(status, 409)
                self.assertEqual(stale["error"]["code"], "configuration_version_conflict")
                self.assertFalse(service.require(revision_id).document["storages"][1]["enabled"])

    def test_validation_unknown_fields_and_persistence_failure_leave_draft_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bootstrap = minimal_bootstrap(root)
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(
                    repository,
                    bootstrap_document=bootstrap,
                    management_only=True,
                )
                api = self._api(repository, runtime_repository, service, bootstrap)
                _, draft = request(
                    api,
                    "/api/v1/configuration/drafts/first",
                    method="POST",
                    body={},
                )
                bad = self._storage_values(root)[1]
                bad["options"] = dict(bad["options"], unknownField="rejected")
                status, response = request(
                    api,
                    f"/api/v1/configuration/revisions/{draft['revisionId']}/objects/storages",
                    method="POST",
                    body={"expectedVersion": draft["version"], "object": bad},
                )
                self.assertEqual(status, 400)
                self.assertNotIn("rejected", json.dumps(response))
                self.assertEqual(service.require(draft["revisionId"]).version, draft["version"])

                literal = self._storage_values(root)[2]
                literal["options"] = dict(literal["options"], token="literal-value")
                status, response = request(
                    api,
                    f"/api/v1/configuration/revisions/{draft['revisionId']}/objects/storages",
                    method="POST",
                    body={"expectedVersion": draft["version"], "object": literal},
                )
                self.assertEqual(status, 400)
                self.assertNotIn("literal-value", json.dumps(response))
                before = service.require(draft["revisionId"])
                before_audits = repository.list_revision_audits(draft["revisionId"])
                objects = ConfigurationObjectService(service)
                valid = self._storage_values(root)[0]
                with patch.object(
                    repository,
                    "update_revision_with_audit",
                    side_effect=RuntimeError("persistence unavailable"),
                ):
                    with self.assertRaises(RuntimeError):
                        objects.mutate(
                            draft["revisionId"],
                            ConfigurationObjectKind.STORAGE,
                            object_id=None,
                            value=valid,
                            expected_version=before.version,
                            actor="admin",
                        )
                after = service.require(draft["revisionId"])
                self.assertEqual(after.version, before.version)
                self.assertEqual(after.digest, before.digest)
                self.assertEqual(after.document, before.document)
                self.assertEqual(
                    repository.list_revision_audits(draft["revisionId"]),
                    before_audits,
                )

    def test_reference_protection_and_unreferenced_delete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bootstrap = minimal_bootstrap(root)
            with (
                SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository,
                SQLiteTaskRepository(root / "runtime.sqlite3") as runtime_repository,
            ):
                service = ManagedConfigurationService(
                    repository,
                    bootstrap_document=bootstrap,
                    management_only=True,
                )
                api = self._api(repository, runtime_repository, service, bootstrap)
                _, draft = request(
                    api,
                    "/api/v1/configuration/drafts/first",
                    method="POST",
                    body={},
                )
                revision_id = draft["revisionId"]
                referenced = self._storage_values(root)[0]
                referenced["id"] = "referenced"
                status, created = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/storages",
                    method="POST",
                    body={"expectedVersion": draft["version"], "object": referenced},
                )
                self.assertEqual(status, 200)
                resource = {
                    "id": "resource-ref",
                    "name": "Resource",
                    "storageId": "referenced",
                    "storagePath": "incoming",
                }
                status, resource_result = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/resourceLibraries",
                    method="POST",
                    body={"expectedVersion": created["version"], "object": resource},
                )
                self.assertEqual(status, 200)
                media = {
                    "id": "media-ref",
                    "name": "Media",
                    "storageId": "referenced",
                    "rootPath": "Movies",
                }
                status, media_result = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/mediaLibraries",
                    method="POST",
                    body={"expectedVersion": resource_result["version"], "object": media},
                )
                self.assertEqual(status, 200)
                status, blocked = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/storages/referenced",
                    method="DELETE",
                    body={"expectedVersion": media_result["version"]},
                )
                self.assertEqual(status, 409)
                self.assertEqual(blocked["error"]["code"], "configuration_object_referenced")
                details = blocked["error"]["details"]
                self.assertEqual(details["durableState"], "draft_preserved")
                self.assertTrue(details["retrySafe"])
                self.assertIn("resourceLibraries", json.dumps(details))
                self.assertIn("mediaLibraries", json.dumps(details))
                unchanged = service.require(revision_id)
                self.assertTrue(
                    any(item["id"] == "referenced" for item in unchanged.document["storages"])
                )

                unreferenced = copy.deepcopy(referenced)
                unreferenced["id"] = "unreferenced"
                status, extra = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/storages",
                    method="POST",
                    body={"expectedVersion": unchanged.version, "object": unreferenced},
                )
                self.assertEqual(status, 200)
                status, deleted = request(
                    api,
                    f"/api/v1/configuration/revisions/{revision_id}/objects/storages/unreferenced",
                    method="DELETE",
                    body={"expectedVersion": extra["version"]},
                )
                self.assertEqual(status, 200)
                current = service.require(revision_id)
                self.assertFalse(
                    any(item["id"] == "unreferenced" for item in current.document["storages"])
                )

    def test_starter_restart_nested_runtime_and_active_immutability(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bootstrap = minimal_bootstrap(root)
            remote = {
                "id": "remote-restart",
                "name": "Remote restart",
                "type": "openlist",
                "rootPath": "/Media",
                "options": {
                    "tokenEnv": "MF_GUIDED_RESTART_TOKEN",
                    "baseUrl": "https://restart.example.invalid",
                },
            }
            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                service = ManagedConfigurationService(
                    repository,
                    bootstrap_document=bootstrap,
                    management_only=True,
                )
                draft = service.create_first_draft(actor="admin")
                objects = ConfigurationObjectService(service)
                draft = objects.mutate(
                    draft.revision_id,
                    ConfigurationObjectKind.STORAGE,
                    object_id=None,
                    value=remote,
                    expected_version=draft.version,
                    actor="admin",
                )
                detail = objects.revision_detail(draft.revision_id)
                self.assertEqual(detail["objects"]["storages"][0]["id"], "remote-restart")

            with SQLiteConfigurationRepository(root / "configuration.sqlite3") as repository:
                restarted = ManagedConfigurationService(
                    repository,
                    bootstrap_document=bootstrap,
                    management_only=True,
                )
                restarted_detail = ConfigurationObjectService(restarted).revision_detail(
                    draft.revision_id
                )
                self.assertEqual(
                    restarted_detail["objects"]["storages"][0]["options"]["tokenEnv"],
                    "MF_GUIDED_RESTART_TOKEN",
                )

            document = complete_document(root)
            document["storages"].append(remote)
            runtime = load_managed_runtime_configuration(
                document,
                bootstrap_database_path=str(root / "configuration.sqlite3"),
            )
            self.assertEqual(runtime.storage_definitions[-1].storage_id, "remote-restart")

            with SQLiteConfigurationRepository(root / "active.sqlite3") as repository:
                service = ManagedConfigurationService(repository)
                draft = service.import_draft(complete_document(root), actor="admin")
                validated = service.validate(draft.revision_id, actor="admin")
                active = service.activate(
                    validated.revision_id,
                    expected_version=validated.version,
                    actor="admin",
                )
                objects = ConfigurationObjectService(service)
                before = service.require(active.revision_id)
                with self.assertRaises(ConfigurationVersionConflict):
                    objects.copy_storage(
                        active.revision_id,
                        object_id="source-storage",
                        expected_version=active.version,
                        actor="admin",
                    )
                after = service.require(active.revision_id)
                self.assertEqual(after.status, before.status)
                self.assertEqual(after.version, before.version)
                self.assertEqual(after.digest, before.digest)

    def test_operator_web_exposes_the_same_typed_storage_actions(self) -> None:
        script = APP_JS.decode()
        for label in (
            "Local",
            "SMB",
            "OpenList",
            "AWS S3",
            "Cloudflare R2",
            "S3-compatible",
            "tokenEnv",
            "usernameEnv",
            "passwordEnv",
            "accessKeyEnv",
            "secretKeyEnv",
            "sessionTokenEnv",
            "Credential readiness",
        ):
            with self.subTest(label=label):
                self.assertIn(label, script)
        self.assertIn("/objects/storages/${encodeURIComponent(item.id)}/${action}", script)
        self.assertIn("The copy starts disabled", script)
        self.assertIn("Save guided object", script)


if __name__ == "__main__":
    unittest.main()
