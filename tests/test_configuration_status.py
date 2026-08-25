from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.configuration_snapshot import (
    MAX_SECTION_ITEMS,
    build_configuration_snapshot,
)
from mediaflow.infrastructure.runtime_configuration import (
    RuntimeConfiguration,
    StorageDefinition,
    load_runtime_configuration,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION
from mediaflow.interfaces.operator_ui import APP_JS, INDEX_HTML
from mediaflow.interfaces.service_api import MediaFlowApi


def example_document():
    return json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))


class AuditOnlyRepository:
    def __init__(self) -> None:
        self.audit = []

    def append_security_audit(self, value) -> None:
        self.audit.append(value)

    def __getattr__(self, name):
        raise AssertionError(f"system status must not access repository method {name}")


def request(api, method="GET", query="", token="viewer-token"):
    statuses = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": "/api/v1/system/status",
        "QUERY_STRING": query,
        "CONTENT_LENGTH": "0",
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(),
    }
    if token:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    body = b"".join(api(environ, lambda status, headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(body)


class ConfigurationSnapshotTests(unittest.TestCase):
    def test_snapshot_is_bounded_deterministic_and_preserves_c_references(self) -> None:
        runtime = load_runtime_configuration(example_document())
        storages = tuple(
            StorageDefinition(f"storage-{index:03}", "local", f"/secret/{index}", "hidden")
            for index in range(MAX_SECTION_ITEMS + 3, 0, -1)
        )
        snapshot = build_configuration_snapshot(replace(runtime, storage_definitions=storages))
        document = snapshot.as_document()
        self.assertEqual(document["system"]["runtime_schema_version"], SCHEMA_VERSION)
        self.assertTrue(document["system"]["python_supported"])
        self.assertTrue(document["system"]["configuration_valid"])
        self.assertEqual(document["storages"]["total"], MAX_SECTION_ITEMS + 3)
        self.assertTrue(document["storages"]["truncated"])
        self.assertEqual(len(document["storages"]["items"]), MAX_SECTION_ITEMS)
        ids = [item["id"] for item in document["storages"]["items"]]
        self.assertEqual(ids, sorted(ids))
        policies = {
            item["recognition_type_id"]: item
            for item in document["recognition_type_policies"]["items"]
        }
        self.assertEqual(policies["C"]["metadata_policy_id"], "C")
        self.assertEqual(policies["C"]["naming_policy_id"], "A")
        self.assertEqual(policies["C"]["classification_policy_id"], "A")
        self.assertEqual(policies["C"]["organize_policy_id"], "A")
        changed = snapshot.as_document()
        changed["system"]["configuration_valid"] = False
        self.assertTrue(snapshot.as_document()["system"]["configuration_valid"])

    def test_hostile_configuration_content_is_never_exposed(self) -> None:
        source = example_document()
        secret = "DO-NOT-LEAK-9f43"
        source["storages"][0]["rootPath"] = f"/{secret}"
        source["storages"][0]["passwordEnv"] = secret
        source["resourceLibraries"][0]["displayRootPath"] = f"/{secret}/media"
        source["recognitionRules"][0]["condition"]["children"][1]["value"] = secret
        source["namingPolicies"][0]["directoryTemplate"] = "{title}-" + secret
        source["classificationPolicies"][0]["rules"][0]["result"]["path"] = [secret]
        document = build_configuration_snapshot(load_runtime_configuration(source)).as_document()
        rendered = json.dumps(document, ensure_ascii=False)
        self.assertNotIn(secret, rendered)
        self.assertNotIn("root", rendered.casefold())
        self.assertNotIn("template", rendered.casefold())
        self.assertNotIn("condition", rendered.casefold())

    def test_api_rbac_method_query_allowlist_and_no_repository_reads(self) -> None:
        snapshot = build_configuration_snapshot(load_runtime_configuration(example_document()))
        repository = AuditOnlyRepository()
        viewer = ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ}))
        api = MediaFlowApi(repository, None, principals=(viewer,), system_status=snapshot)
        self.assertEqual(request(api, token=None)[0], 401)
        self.assertEqual(request(api, method="POST")[0], 405)
        self.assertEqual(request(api, query="paths=true")[0], 400)
        status, document = request(api)
        self.assertEqual(status, 200)
        self.assertEqual(
            set(document),
            {
                "system",
                "storages",
                "resource_libraries",
                "media_libraries",
                "recognition_types",
                "recognition_rules",
                "recognition_type_policies",
                "metadata_policies",
                "naming_policies",
                "classification_policies",
                "organize_policies",
            },
        )
        self.assertGreaterEqual(len(repository.audit), 7)

    def test_ui_has_explicit_read_only_system_refresh(self) -> None:
        html = INDEX_HTML.decode()
        script = APP_JS.decode()
        self.assertIn('data-view="system"', html)
        self.assertIn("/api/v1/system/status", script)
        self.assertIn("Refresh system status", script)
        self.assertIn("secrets are intentionally hidden", script)
        self.assertIn("Retry safe", script)
        self.assertIn("Side effects", script)
        self.assertIn("Next action", script)
        self.assertIn("textContent", script)
        for forbidden in ("Edit configuration", "Apply configuration", "Test storage"):
            self.assertNotIn(forbidden, html + script)

    def test_production_api_bootstrap_injects_snapshot_without_storage(self) -> None:
        from mediaflow.final_cli import final_main

        class Server:
            app = None

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def serve_forever(self):
                return None

        with tempfile.TemporaryDirectory() as directory:
            source = example_document()
            source["persistence"]["databasePath"] = str(Path(directory, "runtime.sqlite3"))
            source["historyPath"] = str(Path(directory, "history.jsonl"))
            config = Path(directory, "strategy.json")
            config.write_text(json.dumps(source), encoding="utf-8")
            server = Server()

            def make_server(host, port, app):
                server.app = app
                return server

            with (
                patch.dict(os.environ, {"MEDIAFLOW_API_TOKEN": "viewer-token"}, clear=True),
                patch("wsgiref.simple_server.make_server", side_effect=make_server),
                patch.object(
                    RuntimeConfiguration,
                    "create_storages",
                    side_effect=AssertionError("API status bootstrap constructed Storage"),
                ),
            ):
                status = final_main(
                    ["--config", str(config), "api", "serve"],
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )
            self.assertEqual(status, 0)
            self.assertIsNotNone(server.app)
            self.assertTrue(
                server.app._system_status.as_document()["system"]["configuration_valid"]
            )


if __name__ == "__main__":
    unittest.main()
