from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

ROUTE = "/api/v1/operations/rules/inventory"


def request(api, *, token="viewer", method="GET", query=""):
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": ROUTE,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": "0",
        "wsgi.input": io.BytesIO(),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
    }
    body = b"".join(api(environ, lambda status, _headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(body)


class RulesWorkspaceJourneyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
        document["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
        document["storages"][0]["rootPath"] = str(root / "source")
        document["storages"][1]["rootPath"] = str(root / "target")
        self.configuration_repository = SQLiteConfigurationRepository(root / "config.sqlite3")
        self.configuration = ManagedConfigurationService(
            self.configuration_repository,
            bootstrap_database_path=str(root / "runtime.sqlite3"),
        )
        draft = self.configuration.import_draft(document, actor="bootstrap")
        validated = self.configuration.validate(draft.revision_id, actor="bootstrap")
        self.configuration.activate(
            validated.revision_id, expected_version=validated.version, actor="bootstrap"
        )
        self.runtime_repository = SQLiteTaskRepository(str(root / "runtime.sqlite3"))
        principals = (
            ResolvedApiPrincipal("viewer", "viewer", frozenset({ApiPermission.READ})),
            ResolvedApiPrincipal("none", "none", frozenset()),
        )
        self.api = MediaFlowApi(
            self.runtime_repository,
            None,
            principals=principals,
            configuration_service=self.configuration,
        )

    def tearDown(self) -> None:
        self.runtime_repository.close()
        self.configuration_repository.close()
        self.directory.cleanup()

    def test_exact_active_projection_is_complete_secret_free_and_preserves_identity(self) -> None:
        status, body = request(self.api)
        self.assertEqual(status, 200)
        self.assertTrue(body["available"])
        self.assertEqual(
            set(body["sections"]),
            {
                "typeBindings",
                "recognitionTypes",
                "recognitionRules",
                "metadataPolicies",
                "namingPolicies",
                "classificationPolicies",
                "organizePolicies",
            },
        )
        binding_c = next(
            item for item in body["sections"]["typeBindings"] if item["id"] == "type-C"
        )
        self.assertEqual(binding_c["recognitionType"], "C")
        self.assertEqual(binding_c["policyReferences"]["namingPolicy"], "A")
        self.assertEqual(binding_c["policyReferences"]["classificationPolicy"], "A")
        encoded = json.dumps(body).lower()
        for forbidden in ("digest", "revisionid", "token", "password", "authorization", "audit"):
            self.assertNotIn(forbidden, encoded)

    def test_search_filter_queries_are_allowlisted_and_reads_have_no_configuration_side_effect(
        self,
    ) -> None:
        before = self.configuration.active()
        status, body = request(
            self.api,
            query="family=recognitionTypes&q=Special&enabled=true",
        )
        self.assertEqual(status, 200)
        self.assertEqual([item["id"] for item in body["sections"]["recognitionTypes"]], ["C"])
        self.assertTrue(
            all(not values for key, values in body["sections"].items() if key != "recognitionTypes")
        )
        after = self.configuration.active()
        self.assertEqual(
            (before.revision_id, before.version, before.digest),
            (after.revision_id, after.version, after.digest),
        )
        for query in ("unknown=1", "family=bad", "enabled=yes", "q=a&q=b"):
            self.assertEqual(request(self.api, query=query)[0], 400)
        self.assertEqual(request(self.api, method="POST")[0], 405)

    def test_permission_and_no_active_outcomes_are_bounded(self) -> None:
        self.assertEqual(request(self.api, token="none")[0], 403)
        root = Path(self.directory.name) / "empty"
        root.mkdir()
        repository = SQLiteConfigurationRepository(root / "config.sqlite3")
        service = ManagedConfigurationService(
            repository, bootstrap_database_path=str(root / "runtime.sqlite3")
        )
        runtime = SQLiteTaskRepository(str(root / "runtime.sqlite3"))
        try:
            api = MediaFlowApi(
                runtime,
                None,
                principals=(
                    ResolvedApiPrincipal("viewer", "viewer", frozenset({ApiPermission.READ})),
                ),
                configuration_service=service,
            )
            status, body = request(api)
            self.assertEqual(status, 200)
            self.assertFalse(body["available"])
            self.assertEqual(body["reason"], "no_active")
            self.assertTrue(all(values == [] for values in body["sections"].values()))
        finally:
            runtime.close()
            repository.close()

    def test_projection_rejects_malformed_active_sections(self) -> None:
        active = self.configuration.active()
        malformed = copy.deepcopy(active.document)
        malformed["recognitionRules"] = {"not": "an array"}

        class Managed:
            repository = self.configuration_repository

            def active(self):
                return type("Revision", (), {**active.__dict__, "document": malformed})()

            @staticmethod
            def verify_integrity(_revision):
                return None

        body = ConfigurationObjectService(Managed()).active_rules_workspace()
        self.assertFalse(body["available"])
        self.assertEqual(body["reason"], "malformed")

    def _activate_document(self, mutate) -> None:
        doc = copy.deepcopy(self.configuration.active().document)
        mutate(doc)
        draft = self.configuration.import_draft(doc, actor="test")
        validated = self.configuration.validate(draft.revision_id, actor="test")
        self.assertEqual(validated.status.value, "validated")
        self.configuration.activate(
            validated.revision_id, expected_version=validated.version, actor="test"
        )

    def test_projection_handles_legal_513_recognition_types(self) -> None:
        def add_types(doc):
            types = list(doc["recognitionTypes"])
            for i in range(510):
                types.append({"id": f"x{i:05d}", "name": f"Extra {i}"})
            doc["recognitionTypes"] = types

        self._activate_document(add_types)
        status, body = request(self.api)
        self.assertEqual(status, 200)
        self.assertTrue(body["available"])
        self.assertEqual(len(body["sections"]["recognitionTypes"]), 513)
        self.assertEqual(body["overview"]["counts"]["recognitionTypes"], 513)

    def test_readiness_is_not_ready_when_all_type_bindings_are_disabled(self) -> None:
        def disable_bindings(doc):
            for binding in doc["recognitionTypePolicies"]:
                binding["enabled"] = False

        self._activate_document(disable_bindings)
        status, body = request(self.api)
        self.assertEqual(status, 200)
        self.assertTrue(body["available"])
        self.assertEqual(body["readiness"]["state"], "PARTIAL")
        self.assertEqual(body["overview"]["enabledCounts"]["typeBindings"], 0)
        binding_gaps = [g for g in body["readiness"]["gaps"] if g["family"] == "typeBindings"]
        self.assertTrue(len(binding_gaps) > 0)
        self.assertIn("enabled RecognitionType binding", binding_gaps[0]["message"])

    def test_readiness_reports_disabled_downstream_reference(self) -> None:
        def disable_naming(doc):
            for policy in doc["namingPolicies"]:
                if policy["id"] == "A":
                    policy["enabled"] = False

        self._activate_document(disable_naming)
        status, body = request(self.api)
        self.assertEqual(status, 200)
        self.assertEqual(body["readiness"]["state"], "PARTIAL")
        binding_gaps = [g for g in body["readiness"]["gaps"] if g["family"] == "typeBindings"]
        self.assertEqual(len(binding_gaps), 1)
        self.assertIn("namingPolicy=A", binding_gaps[0]["message"])
        self.assertIn("disabled or missing downstream policies", binding_gaps[0]["message"])

    def test_readiness_gaps_stay_bounded_and_unique_per_family(self) -> None:
        def add_types(doc):
            types = list(doc["recognitionTypes"])
            for i in range(510):
                types.append({"id": f"x{i:05d}", "name": f"Extra {i}"})
            doc["recognitionTypes"] = types

        self._activate_document(add_types)
        body = ConfigurationObjectService(self.configuration).active_rules_workspace()
        self.assertEqual(body["readiness"]["state"], "PARTIAL")
        families = [gap["family"] for gap in body["readiness"]["gaps"]]
        self.assertEqual(len(families), len(set(families)))
        self.assertLessEqual(len(families), 7)
        for gap in body["readiness"]["gaps"]:
            self.assertLessEqual(len(gap["message"]), 320)
            self.assertLessEqual(len(gap["nextAction"]), 320)

    def test_empty_active_families_report_seven_bounded_onboarding_gaps(self) -> None:
        def empty_families(doc):
            for family in (
                "recognitionTypes",
                "recognitionRules",
                "recognitionTypePolicies",
                "metadataPolicies",
                "namingPolicies",
                "classificationPolicies",
                "organizePolicies",
            ):
                doc[family] = []

        self._activate_document(empty_families)
        status, body = request(self.api)
        self.assertEqual(status, 200)
        self.assertTrue(body["available"])
        self.assertEqual(body["readiness"]["state"], "EMPTY")
        self.assertEqual(len(body["readiness"]["gaps"]), 7)
        self.assertTrue(all(values == [] for values in body["sections"].values()))
        self.assertEqual(body["overview"]["counts"]["recognitionTypes"], 0)


if __name__ == "__main__":
    unittest.main()
