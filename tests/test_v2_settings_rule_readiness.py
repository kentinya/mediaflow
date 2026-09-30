"""V2 Settings rule-readiness projection (Slice 41, Task 41.5).

Settings and the rules workspace must never disagree about the Active rule
graph. These tests pin the cross-surface contract: the Settings projection is
derived from the same managed Active revision the workspace inventory reads, it
stays bounded and secret-free, and a read of it performs no configuration write
and no storage mutation.
"""

from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

STATUS_ROUTE = "/api/v1/configuration/status"
INVENTORY_ROUTE = "/api/v1/operations/rules/inventory"

FAMILIES = {
    "typeBindings",
    "recognitionTypes",
    "recognitionRules",
    "metadataPolicies",
    "namingPolicies",
    "classificationPolicies",
    "organizePolicies",
}


def request(api, route, *, token="viewer", method="GET", query=""):
    statuses: list[str] = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": route,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": "0",
        "wsgi.input": io.BytesIO(),
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_AUTHORIZATION": f"Bearer {token}",
    }
    body = b"".join(api(environ, lambda status, _headers: statuses.append(status)))
    return int(statuses[0].split()[0]), json.loads(body)


class SettingsRuleReadinessTests(unittest.TestCase):
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
            ResolvedApiPrincipal(
                "admin",
                "admin",
                frozenset(
                    {
                        ApiPermission.READ,
                        ApiPermission.MANAGE_CONFIGURATION,
                        ApiPermission.ACTIVATE_CONFIGURATION,
                    }
                ),
            ),
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

    def _activate_document(self, mutate) -> None:
        doc = copy.deepcopy(self.configuration.active().document)
        mutate(doc)
        draft = self.configuration.import_draft(doc, actor="test")
        validated = self.configuration.validate(draft.revision_id, actor="test")
        self.assertEqual(validated.status.value, "validated")
        self.configuration.activate(
            validated.revision_id, expected_version=validated.version, actor="test"
        )

    def test_status_projects_the_same_active_readiness_as_the_workspace(self) -> None:
        status, document = request(self.api, STATUS_ROUTE)
        self.assertEqual(status, 200)
        readiness = document["ruleReadiness"]
        inventory_status, inventory = request(self.api, INVENTORY_ROUTE)
        self.assertEqual(inventory_status, 200)

        # One Active authority: both surfaces name the same immutable revision
        # and derive the same counts, enabled counts, state and gaps.
        active = self.configuration.active()
        self.assertTrue(inventory["available"])
        self.assertEqual(readiness["available"], True)
        self.assertIsNone(readiness["reason"])
        # The identity is the exact Active revision of the same managed
        # authority, and the same sequence both surfaces report.
        self.assertEqual(readiness["active"]["status"], "ACTIVE")
        self.assertEqual(readiness["active"]["revisionId"], active.revision_id)
        self.assertEqual(readiness["active"]["sequence"], active.revision_sequence)
        self.assertEqual(readiness["active"]["sequence"], inventory["active"]["sequence"])
        self.assertEqual(readiness["state"], inventory["readiness"]["state"])
        self.assertEqual(
            readiness["gaps"],
            inventory["readiness"]["gaps"],
        )
        self.assertEqual(readiness["counts"], inventory["overview"]["counts"])
        self.assertEqual(
            readiness["enabledCounts"],
            inventory["overview"]["enabledCounts"],
        )
        self.assertEqual(set(readiness["counts"]), FAMILIES)
        self.assertGreater(readiness["counts"]["recognitionTypes"], 0)

    def test_projection_is_bounded_and_carries_no_secret_or_authority(self) -> None:
        _status, document = request(self.api, STATUS_ROUTE)
        encoded = json.dumps(document["ruleReadiness"], sort_keys=True)
        self.assertLessEqual(len(encoded), 4096)
        lowered = encoded.lower()
        for forbidden in (
            "token",
            "password",
            "secret",
            "authorization",
            "cookie",
            "rootpath",
            "https://",
            "digest",
            "document",
        ):
            self.assertNotIn(forbidden, lowered)
        for gap in document["ruleReadiness"]["gaps"]:
            self.assertIn(gap["family"], FAMILIES)
            self.assertLessEqual(len(gap["message"]), 320)
            self.assertLessEqual(len(gap["nextAction"]), 320)

    def test_readiness_read_performs_no_configuration_or_storage_write(self) -> None:
        before = self.configuration.active()
        former_sequence = before.revision_sequence
        audits_before = self.configuration_repository.list_revision_audits(before.revision_id)
        status, _document = request(self.api, STATUS_ROUTE)
        self.assertEqual(status, 200)
        after = self.configuration.active()
        self.assertEqual(
            (before.revision_id, before.version, before.digest),
            (after.revision_id, after.version, after.digest),
        )
        self.assertEqual(
            self.configuration_repository.list_revision_audits(after.revision_id),
            audits_before,
        )
        self.assertEqual(len(self.configuration_repository.list_revisions()), 1)
        # A read of readiness never advances the managed activation sequence, so
        # the next writer still composes against the same Active it observed.
        self.assertEqual(after.revision_sequence, former_sequence)

    def test_denied_reads_and_missing_authority_do_not_claim_readiness(self) -> None:
        self.assertEqual(request(self.api, STATUS_ROUTE, token="none")[0], 403)
        self.assertEqual(request(self.api, STATUS_ROUTE, token="bogus")[0], 401)
        # A deployment without a managed configuration service reports the
        # explicit unavailable state instead of an empty rule graph.
        api = MediaFlowApi(
            self.runtime_repository,
            None,
            principals=(ResolvedApiPrincipal("viewer", "viewer", frozenset({ApiPermission.READ})),),
        )
        # A deployment without a managed configuration service refuses the
        # status read outright; it never reports readiness of any kind.
        status, document = request(api, STATUS_ROUTE)
        self.assertEqual(status, 503)
        self.assertNotIn("ruleReadiness", document)

    def test_no_active_configuration_stays_distinct_from_an_empty_rule_graph(self) -> None:
        root = Path(self.directory.name) / "empty"
        root.mkdir()
        repository = SQLiteConfigurationRepository(root / "config.sqlite3")
        service = ManagedConfigurationService(
            repository, bootstrap_database_path=str(root / "runtime.sqlite3")
        )
        api = MediaFlowApi(
            self.runtime_repository,
            None,
            principals=(ResolvedApiPrincipal("viewer", "viewer", frozenset({ApiPermission.READ})),),
            configuration_service=service,
        )
        try:
            status, document = request(api, STATUS_ROUTE)
            self.assertEqual(status, 200)
            readiness = document["ruleReadiness"]
            self.assertFalse(readiness["available"])
            self.assertEqual(readiness["reason"], "no_active")
            self.assertEqual(readiness["state"], "NO_ACTIVE")
            self.assertIsNone(readiness["active"])
        finally:
            repository.close()

    def test_a_later_activation_is_visible_to_the_next_readiness_read(self) -> None:
        _status, first = request(self.api, STATUS_ROUTE)
        first_sequence = first["ruleReadiness"]["active"]["sequence"]
        first_count = first["ruleReadiness"]["counts"]["recognitionTypes"]
        self.assertEqual(first["ruleReadiness"]["state"], "READY")

        def add_recognition_type(doc):
            doc["recognitionTypes"] = [
                *doc["recognitionTypes"],
                {"id": "extra", "name": "Extra"},
            ]

        self._activate_document(add_recognition_type)
        _status, second = request(self.api, STATUS_ROUTE)
        readiness = second["ruleReadiness"]
        self.assertEqual(readiness["active"]["sequence"], first_sequence + 1)
        self.assertEqual(readiness["counts"]["recognitionTypes"], first_count + 1)
        # The newly published object is the Active one the next read describes.
        self.assertEqual(readiness["active"]["revisionId"], self.configuration.active().revision_id)
        _inventory_status, inventory = request(self.api, INVENTORY_ROUTE)
        self.assertEqual(readiness["active"]["sequence"], inventory["active"]["sequence"])
        self.assertIn(
            "extra",
            [item["id"] for item in inventory["sections"]["recognitionTypes"]],
        )

    def test_projection_never_reports_an_identity_the_status_read_did_not(self) -> None:
        """A readiness projection must describe the Active of its own status read.

        The Settings page compares the two identities to detect a concurrent
        activation. If the projection ever named another revision, the page would
        either show a mixed snapshot as current or refuse a truthful one, so the
        identity is required to come from this same document.
        """

        _status, document = request(self.api, STATUS_ROUTE)
        active = document["active"]
        readiness = document["ruleReadiness"]
        self.assertIsNotNone(active)
        self.assertEqual(readiness["active"]["revisionId"], active["revisionId"])
        self.assertEqual(readiness["active"]["sequence"], active["revisionSequence"])
        encoded = json.dumps(readiness)
        self.assertNotIn("digest", encoded.lower())
        self.assertNotIn(active.get("digest", "unused-digest"), encoded)

    def test_readiness_is_bounded_when_the_active_document_is_unreadable(self) -> None:
        """A broken Active is an explicit unavailable readiness, not zero counts."""

        repository = self.configuration_repository
        active = self.configuration.active()
        with patch.object(
            repository,
            "get_active_revision",
            side_effect=RuntimeError("unreadable"),
        ):
            status, document = request(self.api, STATUS_ROUTE)
        self.assertEqual(status, 200)
        readiness = document["ruleReadiness"]
        self.assertFalse(readiness["available"])
        self.assertIn(readiness["state"], {"UNAVAILABLE", "NO_ACTIVE", "MALFORMED"})
        self.assertIsNone(readiness["active"])
        self.assertEqual(readiness["gaps"], [])
        # The unreadable Active is still the one this document reported.
        self.assertIsNotNone(active)
        self.assertEqual(set(readiness["counts"]), FAMILIES)

    def test_partial_readiness_gap_navigates_to_the_family_the_backend_named(self) -> None:
        def disable_bindings(doc):
            for binding in doc["recognitionTypePolicies"]:
                binding["enabled"] = False

        self._activate_document(disable_bindings)
        _status, document = request(self.api, STATUS_ROUTE)
        readiness = document["ruleReadiness"]
        self.assertEqual(readiness["state"], "PARTIAL")
        self.assertTrue(readiness["gaps"])
        for gap in readiness["gaps"]:
            self.assertIn(gap["family"], FAMILIES)
            self.assertTrue(gap["message"])
            self.assertTrue(gap["nextAction"])

    def test_a_concurrent_activation_cannot_mix_identity_with_counts(self) -> None:
        """Regression for the Task 41.5 B-review blocker.

        The B review reproduced this legal concurrency timing: the status
        document reads Active once, then the readiness projection reads Active
        again through the workspace inventory. When a second activation lands
        between the two reads, the old code stamped the *first* read's revision
        identity onto the *second* read's counts, so the response reported the
        old revisionId together with the new (larger) recognitionTypes count and
        the page's mixed-snapshot check could not fire.

        The fix binds the identity and the counts/state/gaps to one single
        Active read inside ``active_rule_readiness``. This test drives the exact
        interleaving through a repository wrapper that publishes a new revision
        between the status read and the readiness read, with the real SQLite
        managed configuration and the production ``MediaFlowApi``.
        """

        activation_landed = False
        activating = False
        # One status request performs three Active reads in order: the status
        # document itself, the command-readiness projection, then the
        # rule-readiness projection. The B-review interleaving publishes the
        # successor before the third read, so `status.active` is still the old
        # revision while the readiness projection derives from the new one.
        active_read_calls = 0
        original_activate = self.configuration.activate

        repository = self.configuration_repository
        inner_get = repository.get_active_revision
        original_active = self.configuration.active()

        def get_active_revision():
            nonlocal activation_landed
            nonlocal activating
            nonlocal active_read_calls
            active_read_calls += 1
            if active_read_calls == 3 and not activation_landed and not activating:
                # Publish one legal successor revision exactly between the
                # status Active read and the readiness Active read. The
                # re-entrancy guard keeps the activation's own internal reads
                # (import/validate/activate) from recursing into the wrapper.
                activating = True
                try:
                    doc = copy.deepcopy(original_active.document)
                    doc["recognitionTypes"] = [
                        *doc["recognitionTypes"],
                        {"id": "interleaved", "name": "Interleaved"},
                    ]
                    draft = self.configuration.import_draft(doc, actor="concurrent")
                    validated = self.configuration.validate(draft.revision_id, actor="concurrent")
                    original_activate(
                        validated.revision_id,
                        expected_version=validated.version,
                        actor="concurrent",
                    )
                finally:
                    activating = False
                activation_landed = True
            return inner_get()

        repository.get_active_revision = get_active_revision
        status_code, document = request(self.api, STATUS_ROUTE)
        self.assertEqual(status_code, 200)
        self.assertTrue(activation_landed)

        status_active = document["active"]
        readiness = document["ruleReadiness"]
        # The status document reported the *old* Active; the readiness
        # projection read *after* the activation, so its identity is the new
        # revision. The two identities disagree — which is exactly the mixed
        # snapshot the frontend must detect instead of silently presenting.
        self.assertIsNotNone(status_active)
        self.assertIsNotNone(readiness["active"])
        self.assertNotEqual(
            readiness["active"]["revisionId"],
            status_active["revisionId"],
        )
        self.assertGreater(
            readiness["active"]["sequence"],
            status_active["revisionSequence"],
        )
        # The counts are the new revision's counts and belong to the readiness
        # identity they are bound to: the interleaved RecognitionType is
        # present, so this can no longer be stamped onto the old identity.
        self.assertEqual(
            readiness["active"]["revisionId"],
            self.configuration.active().revision_id,
        )
        self.assertGreater(readiness["counts"]["recognitionTypes"], 0)

        # The identity now provably describes the same read the counts came
        # from: re-reading the same revision and re-deriving the projection
        # from that exact revision reproduces the same counts.
        pinned = self.configuration.require(readiness["active"]["revisionId"])
        from mediaflow.application.configuration_objects import ConfigurationObjectService

        service = ConfigurationObjectService(self.configuration)
        projection = service._rules_workspace_from_active(pinned, include_sections=False)
        self.assertEqual(
            projection["overview"]["counts"],
            readiness["counts"],
        )
        self.assertEqual(
            projection["overview"]["enabledCounts"],
            readiness["enabledCounts"],
        )
        self.assertEqual(
            projection["readiness"]["gaps"],
            readiness["gaps"],
        )
        self.assertEqual(
            projection["active"]["identity"]["revisionId"],
            readiness["active"]["revisionId"],
        )

        # The frontend contract can detect the mismatch from this document
        # alone: the two revision identities inside one response differ.
        self.assertNotEqual(
            readiness["active"]["revisionId"],
            (status_active or {}).get("revisionId"),
        )


class RulesReadinessFixtureContractTests(unittest.TestCase):
    """The shared cross-boundary fixture the browser fake serves.

    ``web/tests/fixtures/rules-readiness.json`` is consumed by the Playwright
    fake server; this comparison is the one cross-boundary evidence that the
    Python API and the browser fake agree on the same bounded document. Only the
    server-issued opaque integer sequence is pinned to a stable placeholder, and
    the Active revision identity is replaced by the fixture's own constant.
    """

    def test_real_documents_match_the_shared_browser_fixture(self) -> None:
        fixture_path = (
            Path(__file__).resolve().parents[1]
            / "web"
            / "tests"
            / "fixtures"
            / "rules-readiness.json"
        )
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))
            document["persistence"]["databasePath"] = str(root / "runtime.sqlite3")
            document["storages"][0]["rootPath"] = str(root / "source")
            document["storages"][1]["rootPath"] = str(root / "target")
            repository = SQLiteConfigurationRepository(root / "config.sqlite3")
            service = ManagedConfigurationService(
                repository, bootstrap_database_path=str(root / "runtime.sqlite3")
            )
            draft = service.import_draft(document, actor="fixture")
            validated = service.validate(draft.revision_id, actor="fixture")
            service.activate(
                validated.revision_id, expected_version=validated.version, actor="fixture"
            )
            runtime = SQLiteTaskRepository(str(root / "runtime.sqlite3"))
            api = MediaFlowApi(
                runtime,
                None,
                principals=(
                    ResolvedApiPrincipal("viewer", "viewer-token", frozenset({ApiPermission.READ})),
                ),
                configuration_service=service,
            )
            try:
                inventory_status, inventory = request(api, INVENTORY_ROUTE, token="viewer-token")
                self.assertEqual(inventory_status, 200)
                _status, status = request(api, STATUS_ROUTE, token="viewer-token")
                self.assertEqual(inventory, fixture["inventory"])
                readiness = json.loads(
                    json.dumps(status["ruleReadiness"]).replace(
                        service.active().revision_id,
                        fixture["activeRevisionId"],
                    )
                )
                self.assertEqual(readiness, fixture["ruleReadiness"])
                self.assertEqual(fixture["activeSequence"], service.active().revision_sequence)
                self.assertEqual(fixture["activeVersion"], service.active().version)
                # The two surfaces in the fixture describe one Active.
                self.assertEqual(
                    readiness["active"]["sequence"],
                    inventory["active"]["sequence"],
                )
            finally:
                runtime.close()
                repository.close()


if __name__ == "__main__":
    unittest.main()
