from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediaflow.domain.storage import StorageCapabilities, StorageError, StorageErrorCode
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.runtime_configuration import (
    RuntimeConfiguration,
    load_runtime_configuration,
)
from mediaflow.infrastructure.s3_storage import S3Provider


class ReadOnlyPreflightStorage:
    def __init__(self, storage_id: str, *, fail: bool = False) -> None:
        self.storage_id = storage_id
        self.name = storage_id
        self.read_only = False
        self.capabilities = StorageCapabilities(True, True, True, False, False)
        self.fail = fail
        self.lists = 0
        self.mutations = 0

    def list(self, path: str):
        self.lists += 1
        if self.fail:
            raise StorageError(
                StorageErrorCode.AUTHENTICATION_FAILED,
                "list",
                path,
                "authentication failed",
            )
        return ()

    def __getattr__(self, name: str):
        if name in {
            "write",
            "create_directory",
            "move",
            "copy",
            "delete",
            "hard_link",
            "soft_link",
        }:
            self.mutations += 1
            raise AssertionError(f"preflight called mutation {name}")
        raise AttributeError(name)


class RuntimeStorageConfigurationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))

    def _replace_source(self, value: dict) -> RuntimeConfiguration:
        document = copy.deepcopy(self.document)
        document["storages"][0] = value
        return load_runtime_configuration(document)

    def test_smb_runtime_uses_environment_credentials_and_redacts(self) -> None:
        runtime = self._replace_source(
            {
                "id": "source-storage",
                "name": "NAS",
                "type": "smb",
                "host": "nas.example.test",
                "share": "Media",
                "rootPath": "Incoming",
                "usernameEnv": "TEST_SMB_USER",
                "passwordEnv": "TEST_SMB_PASSWORD",
                "domain": "WORKGROUP",
                "port": 445,
                "readOnly": True,
            }
        )
        captured = []

        def build(config):
            captured.append(config)
            return object()

        with (
            patch.dict(
                "os.environ",
                {"TEST_SMB_USER": "operator", "TEST_SMB_PASSWORD": "top-secret"},
            ),
            patch("mediaflow.infrastructure.runtime_configuration.SMBStorage", side_effect=build),
        ):
            runtime.create_storages({"media-target": object()}, storage_ids={"source-storage"})
        self.assertEqual(captured[0].username, "operator")
        self.assertEqual(captured[0].password, "top-secret")
        self.assertNotIn("top-secret", repr(captured[0]))

    def test_s3_r2_and_compatible_runtime_mapping(self) -> None:
        cases = (
            ("s3", None, S3Provider.AWS_S3),
            ("r2", "https://account.r2.cloudflarestorage.com", S3Provider.CLOUDFLARE_R2),
            ("s3-compatible", "https://minio.example.test", S3Provider.S3_COMPATIBLE),
        )
        for storage_type, endpoint, expected in cases:
            with self.subTest(storage_type=storage_type):
                value = {
                    "id": "source-storage",
                    "type": storage_type,
                    "bucket": "media-bucket",
                    "rootPath": "incoming",
                    "accessKeyEnv": "TEST_S3_ACCESS",
                    "secretKeyEnv": "TEST_S3_SECRET",
                    "sessionTokenEnv": "TEST_S3_SESSION",
                    "readOnly": True,
                }
                if endpoint:
                    value["endpoint"] = endpoint
                runtime = self._replace_source(value)
                captured = []
                with (
                    patch.dict(
                        "os.environ",
                        {
                            "TEST_S3_ACCESS": "access-secret",
                            "TEST_S3_SECRET": "private-secret",
                            "TEST_S3_SESSION": "session-secret",
                        },
                    ),
                    patch(
                        "mediaflow.infrastructure.runtime_configuration.S3Storage",
                        side_effect=lambda config: captured.append(config) or object(),
                    ),
                ):
                    runtime.create_storages(storage_ids={"source-storage"})
                config = captured[0]
                self.assertEqual(config.provider, expected)
                self.assertEqual(config.root_prefix, "incoming")
                self.assertNotIn("private-secret", repr(config))
                self.assertNotIn("session-secret", repr(config))

    def test_validation_needs_env_names_but_not_secret_values(self) -> None:
        value = {
            "id": "source-storage",
            "type": "smb",
            "host": "nas",
            "share": "Media",
            "rootPath": "",
            "usernameEnv": "MISSING_USER",
            "passwordEnv": "MISSING_PASSWORD",
        }
        runtime = self._replace_source(value)
        with self.assertRaisesRegex(ValueError, "MISSING_USER"):
            runtime.create_storages(storage_ids={"source-storage"})
        value["usernameEnv"] = "bad-name"
        with self.assertRaisesRegex(ValueError, "environment variable"):
            self._replace_source(value)
        value.update({"usernameEnv": "U", "passwordEnv": "P", "password": "literal-secret"})
        with self.assertRaisesRegex(ValueError, "literal Storage secret"):
            self._replace_source(value)

    def test_config_validate_remote_needs_no_secret_or_network(self) -> None:
        document = copy.deepcopy(self.document)
        document["storages"][0] = {
            "id": "source-storage",
            "type": "smb",
            "host": "nas.example.test",
            "share": "Media",
            "rootPath": "Incoming",
            "usernameEnv": "ABSENT_SMB_USER",
            "passwordEnv": "ABSENT_SMB_PASSWORD",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "config.json")
            path.write_text(json.dumps(document), encoding="utf-8")
            output, errors = io.StringIO(), io.StringIO()
            with patch.object(
                RuntimeConfiguration,
                "create_storages",
                side_effect=AssertionError("validation must not construct adapters"),
            ):
                code = final_main(
                    ["--config", str(path), "config", "validate"],
                    stdout=output,
                    stderr=errors,
                )
            self.assertEqual(code, 0, errors.getvalue())
            self.assertIn("Configuration valid", output.getvalue())

    def test_invalid_remote_storage_configuration_fails_fast(self) -> None:
        cases = [
            {"type": "unknown", "rootPath": ""},
            {
                "type": "smb",
                "rootPath": "",
                "host": "",
                "share": "Media",
                "usernameEnv": "U",
                "passwordEnv": "P",
            },
            {
                "type": "smb",
                "rootPath": "",
                "host": "nas",
                "share": "Media",
                "usernameEnv": "U",
                "passwordEnv": "P",
                "port": 70000,
            },
            {
                "type": "r2",
                "rootPath": "",
                "bucket": "bucket",
                "endpoint": "relative",
                "accessKeyEnv": "A",
                "secretKeyEnv": "S",
            },
            {
                "type": "s3-compatible",
                "rootPath": "",
                "bucket": "bad/bucket",
                "endpoint": "https://minio.example.test",
                "accessKeyEnv": "A",
                "secretKeyEnv": "S",
            },
        ]
        for case in cases:
            value = {"id": "source-storage", **case}
            with self.subTest(case=case), self.assertRaises(ValueError):
                self._replace_source(value)

    def test_storage_list_does_not_construct_or_connect(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "config.json")
            path.write_text(json.dumps(self.document), encoding="utf-8")
            output, errors = io.StringIO(), io.StringIO()
            with patch.object(
                RuntimeConfiguration,
                "create_storages",
                side_effect=AssertionError("must not construct"),
            ):
                code = final_main(
                    ["--config", str(path), "storage", "list"],
                    stdout=output,
                    stderr=errors,
                )
            self.assertEqual(code, 0, errors.getvalue())
            self.assertIn("source-storage | local", output.getvalue())

    def test_storage_check_is_read_only_and_isolates_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "config.json")
            path.write_text(json.dumps(self.document), encoding="utf-8")
            healthy = ReadOnlyPreflightStorage("source-storage")
            failed = ReadOnlyPreflightStorage("media-target", fail=True)

            def create(_self, external=None, storage_ids=None):
                values = {"source-storage": healthy, "media-target": failed}
                return {key: values[key] for key in storage_ids or values}

            output, errors = io.StringIO(), io.StringIO()
            with patch.object(RuntimeConfiguration, "create_storages", create):
                code = final_main(
                    ["--config", str(path), "storage", "check"],
                    stdout=output,
                    stderr=errors,
                )
            self.assertEqual(code, 1)
            self.assertIn("PASS | source-storage", output.getvalue())
            self.assertIn("FAIL | media-target | authentication_failed", output.getvalue())
            self.assertEqual(healthy.mutations + failed.mutations, 0)
            self.assertEqual(healthy.lists, 1)
            self.assertEqual(failed.lists, 1)

    def test_storage_check_rejects_unknown_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "config.json")
            path.write_text(json.dumps(self.document), encoding="utf-8")
            output, errors = io.StringIO(), io.StringIO()
            code = final_main(
                ["--config", str(path), "storage", "check", "missing"],
                stdout=output,
                stderr=errors,
            )
            self.assertEqual(code, 2)
            self.assertIn("unknown Storage", errors.getvalue())
