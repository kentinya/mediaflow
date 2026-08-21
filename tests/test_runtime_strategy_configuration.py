from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.classification import ClassificationEngine
from mediaflow.application.naming import NamingEngine
from mediaflow.application.policies import RecognitionTypePolicyResolver
from mediaflow.domain.classification import ClassificationContext
from mediaflow.domain.metadata import MediaIdentity, MediaType
from mediaflow.domain.naming import NamingContext
from mediaflow.domain.organizer import OrganizeOperationType
from mediaflow.domain.parser import ParseResult
from mediaflow.final_cli import final_main
from mediaflow.infrastructure.openlist_storage import OpenListStorage
from mediaflow.infrastructure.runtime_configuration import load_runtime_configuration


class RuntimeStrategyConfigurationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))

    def test_configuration_alone_controls_naming_classification_and_operation(self) -> None:
        naming = next(item for item in self.document["namingPolicies"] if item["id"] == "A")
        naming["directoryTemplate"] = "{title} [{provider}-{provider_id}]"
        classification = next(
            item for item in self.document["classificationPolicies"] if item["id"] == "A"
        )
        classification["rules"][0]["result"]["path"] = ["动漫"]
        organize = next(item for item in self.document["organizePolicies"] if item["id"] == "A")
        organize["operation"] = "COPY"

        runtime = load_runtime_configuration(self.document)
        identity = MediaIdentity(
            "tmdb",
            "129",
            MediaType.MOVIE,
            "千与千寻",
            year=2001,
            genres=("Animation",),
            countries=("JP",),
        )
        parsed = ParseResult("千与千寻", year=2001, extension="mkv")
        type_c = next(item for item in runtime.strategy.recognition_types if item.type_id == "C")
        policy_a = next(item for item in runtime.strategy.naming_policies if item.policy_id == "A")
        named = NamingEngine().name(NamingContext("C", identity, parsed, extension="mkv"), policy_a)
        classification_a = next(
            item for item in runtime.strategy.classification_policies if item.policy_id == "A"
        )
        classified = ClassificationEngine().classify(
            ClassificationContext(type_c, identity, parsed, named), classification_a
        )
        resolved = RecognitionTypePolicyResolver(
            runtime.strategy.recognition_type_policies,
            metadata_policies={item.policy_id: item for item in runtime.strategy.metadata_policies},
            naming_policies={item.policy_id: item for item in runtime.strategy.naming_policies},
            classification_policies={
                item.policy_id: item for item in runtime.strategy.classification_policies
            },
        ).resolve(type_c)

        self.assertEqual(named.directory, "千与千寻 [tmdb-129]")
        self.assertEqual(classified.relative_path, "动漫")
        self.assertEqual(resolved.recognition_type.type_id, "C")
        self.assertEqual(resolved.metadata_policy_id, "C")
        self.assertEqual(resolved.naming_policy_id, "A")
        self.assertEqual(resolved.classification_policy_id, "A")
        type_policy_c = next(
            item
            for item in runtime.strategy.recognition_type_policies
            if item.recognition_type.type_id == "C"
        )
        self.assertEqual(type_policy_c.organize_policy.operation, OrganizeOperationType.COPY)

    def test_validation_fails_fast_for_invalid_catalogs(self) -> None:
        cases = []
        missing = copy.deepcopy(self.document)
        missing["recognitionTypePolicies"][0]["namingPolicy"] = "missing"
        cases.append(missing)
        duplicate = copy.deepcopy(self.document)
        duplicate["organizePolicies"].append(copy.deepcopy(duplicate["organizePolicies"][0]))
        cases.append(duplicate)
        template = copy.deepcopy(self.document)
        template["namingPolicies"][0]["directoryTemplate"] = "{unsupported}"
        cases.append(template)
        unsafe = copy.deepcopy(self.document)
        unsafe["classificationPolicies"][0]["rules"][0]["result"]["path"] = [".."]
        cases.append(unsafe)
        operation = copy.deepcopy(self.document)
        operation["organizePolicies"][0]["operation"] = "TELEPORT"
        cases.append(operation)
        for document in cases:
            with self.subTest(document=document), self.assertRaises((ValueError, LookupError)):
                load_runtime_configuration(document)

    def test_validation_command_performs_no_storage_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "mediaflow.json")
            path.write_text(json.dumps(self.document, ensure_ascii=False), encoding="utf-8")
            before = sorted(item.name for item in Path(directory).iterdir())
            stdout, stderr = io.StringIO(), io.StringIO()
            code = final_main(
                ["--config", str(path), "config", "validate"],
                stdout=stdout,
                stderr=stderr,
            )
            self.assertEqual(code, 0, stderr.getvalue())
            self.assertIn("Configuration valid", stdout.getvalue())
            self.assertEqual(sorted(item.name for item in Path(directory).iterdir()), before)

    def test_malformed_configuration_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "JSON object"):
            load_runtime_configuration([])

    def test_resource_library_display_root_is_optional_with_legacy_alias(self) -> None:
        document = copy.deepcopy(self.document)
        resource = document["resourceLibraries"][0]
        resource.pop("displayRootPath", None)
        resource.pop("rootPath", None)
        runtime = load_runtime_configuration(document)
        self.assertEqual(runtime.resource_display_roots, ())
        self.assertEqual(runtime.resource_libraries[0].root_path, "Media")

        resource["rootPath"] = "/legacy/display/path"
        runtime = load_runtime_configuration(document)
        self.assertEqual(runtime.resource_display_roots, (("source", "/legacy/display/path"),))

    def test_openlist_storage_uses_environment_owned_token(self) -> None:
        document = copy.deepcopy(self.document)
        document["storages"][0] = {
            "id": "source-storage",
            "name": "OpenList",
            "type": "openlist",
            "baseUrl": "https://openlist.example.test",
            "tokenEnv": "TEST_OPENLIST_TOKEN",
            "rootPath": "/Media",
            "readOnly": True,
        }
        runtime = load_runtime_configuration(document)
        with patch.dict("os.environ", {"TEST_OPENLIST_TOKEN": "secret-token"}):
            storages = runtime.create_storages({"media-target": object()})
        try:
            self.assertIsInstance(storages["source-storage"], OpenListStorage)
            self.assertNotIn("secret-token", repr(storages["source-storage"]))
        finally:
            storages["source-storage"].close()


if __name__ == "__main__":
    unittest.main()
