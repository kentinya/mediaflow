"""Task 41.2 — rules-workspace typed object commands and one-save publication.

These tests prove the vertical the V2 organizing-rules workspace depends on:

* the five independently creatable rule foundations publish one exact Active
  successor per explicit ``保存`` through the existing managed normalization,
  whole-document validation, applicable Slice 40 evidence and checked atomic
  activation boundaries;
* reads and inventory inspection never create a Draft, call a Metadata Provider,
  create work or mutate Storage, and no projection returns a secret value;
* stale or simultaneous writers cannot publish the wrong successor, and a known
  failure keeps the previous Active plus a correctable typed candidate;
* every family reflects real domain fields and references, and the permanent
  RecognitionType-C identity invariant survives reuse of A naming/classification.
"""

from __future__ import annotations

import copy
import io
import json
import os
import tempfile
import threading
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.configuration_objects import ConfigurationObjectService
from mediaflow.application.configuration_snapshot import ManagedConfigurationService
from mediaflow.application.rules_workspace_commands import (
    RULE_FAMILIES,
    RulesWorkspaceCommandService,
)
from mediaflow.domain.configuration_management import (
    ConfigurationVersionConflict,
    RulesWorkspaceSaveError,
)
from mediaflow.domain.recognition import RecognitionType
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.domain.storage import StorageCapabilities, StorageEntry, StorageEntryType
from mediaflow.infrastructure.sqlite_configuration_management import SQLiteConfigurationRepository
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi

BASE = "/api/v1/operations/rules"
INVENTORY = f"{BASE}/inventory"
FORM_AUTHORITY = f"{BASE}/form-authority"

# Deployment-owned credential sentinels. They exist only to prove that no form
# authority, projection, Save response, audit record or error ever carries a
# secret value: the rules workspace exchanges environment-variable names and
# SET/UNSET readiness, never values.
SECRET_SENTINELS = {
    "TMDB_ACCESS_TOKEN": "sentinel-tmdb-access-token-value",
    "OPENLIST_TOKEN": "sentinel-openlist-token-value",
}

RULE_SECTIONS = (
    "recognitionTypes",
    "recognitionRules",
    "recognitionTypePolicies",
    "metadataPolicies",
    "namingPolicies",
    "classificationPolicies",
    "organizePolicies",
)


class RecordingStorage:
    """Provider-neutral fake recording every Storage call the command layer makes."""

    def __init__(self, storage_id: str) -> None:
        self.storage_id = storage_id
        self.name = storage_id
        self.read_only = False
        self.mutations: list[str] = []
        self.reads: list[str] = []

    @property
    def capabilities(self) -> StorageCapabilities:
        return StorageCapabilities()

    def _read(self, operation: str, path: str) -> None:
        self.reads.append(f"{operation}:{path}")

    def stat(self, path: str) -> StorageEntry:
        self._read("stat", path)
        return StorageEntry(path, path, StorageEntryType.DIRECTORY, 0, datetime.now(UTC))

    def list(self, path: str):
        self._read("list", path)
        return ()

    def exists(self, path: str) -> bool:
        self._read("exists", path)
        return True

    def read(self, path: str):
        self._read("read", path)
        raise AssertionError("rules Save must not read file contents")

    def _refuse(self, operation: str):
        self.mutations.append(operation)
        raise AssertionError(f"rules Save must not {operation} Storage")

    def write(self, *args, **kwargs):
        self._refuse("write")

    def create_directory(self, *args, **kwargs):
        self._refuse("create_directory")

    def move(self, *args, **kwargs):
        self._refuse("move")

    def copy(self, *args, **kwargs):
        self._refuse("copy")

    def delete(self, *args, **kwargs):
        self._refuse("delete")

    def hard_link(self, *args, **kwargs):
        self._refuse("hard_link")

    def soft_link(self, *args, **kwargs):
        self._refuse("soft_link")


class MutationAuditRepository(SQLiteConfigurationRepository):
    """Counts activation writes so a test can prove nothing published."""

    def __init__(self, path) -> None:
        super().__init__(path)
        self.activations = 0

    def activate_revision(self, revision_id, expected_version, audit):
        self.activations += 1
        return super().activate_revision(revision_id, expected_version, audit)


def example_document() -> dict:
    return json.loads(Path("config/strategy.example.json").read_text(encoding="utf-8"))


def empty_rule_families(document: dict) -> dict:
    """One legal empty-business Active: the real onboarding starting point."""

    for section in RULE_SECTIONS:
        document[section] = []
    return document


class RulesWorkspaceCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "source" / "incoming").mkdir(parents=True)
        (self.root / "target" / "Movies").mkdir(parents=True)
        self.environment = patch.dict(os.environ, SECRET_SENTINELS, clear=False)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self._activate_baseline(example_document())

    def tearDown(self) -> None:
        for close in (
            getattr(self, "runtime_repository", None),
            getattr(self, "config_repo", None),
        ):
            if close is not None:
                close.close()

    # -- harness ---------------------------------------------------------

    def _activate_baseline(self, document: dict) -> None:
        """Publish one fresh legal Active baseline over the same temporary roots."""

        document = copy.deepcopy(document)
        document["persistence"]["databasePath"] = str(self.root / "runtime.sqlite3")
        document["storages"][0]["rootPath"] = str(self.root / "source")
        document["storages"][1]["rootPath"] = str(self.root / "target")
        document["resourceLibraries"][0]["storagePath"] = "incoming"
        document["mediaLibraries"][0]["rootPath"] = "Movies"

        if getattr(self, "runtime_repository", None) is not None:
            self.runtime_repository.close()
        if getattr(self, "config_repo", None) is not None:
            self.config_repo.close()
        self.baseline_document = document
        self.config_repo = MutationAuditRepository(self.root / "config.sqlite3")
        self.configuration = ManagedConfigurationService(
            self.config_repo,
            bootstrap_database_path=str(self.root / "runtime.sqlite3"),
        )
        self.provider_calls: list[str] = []
        self.objects = ConfigurationObjectService(
            self.configuration,
            metadata_provider_registry_factory=self._forbidden_provider_factory,
            storage_browser_cursor_secret="rules-workspace-test-secret",
        )
        self.adapters = {
            str(item["id"]): RecordingStorage(str(item["id"])) for item in document["storages"]
        }
        self.objects._storage_adapters.update(self.adapters)
        self.commands = RulesWorkspaceCommandService(self.objects)
        draft = self.configuration.import_draft(document, actor="bootstrap")
        validated = self.configuration.validate(draft.revision_id, actor="bootstrap")
        # The baseline records the same shared exact-revision evidence the sibling
        # page-local Save suites use, then publishes through checked activation.
        self.objects._checked_successor_evidence(validated, actor="bootstrap")
        self.objects.activate_checked(
            validated.revision_id, expected_version=validated.version, actor="bootstrap"
        )
        self.activations_at_baseline = self.config_repo.activations
        self.runtime_repository = SQLiteTaskRepository(str(self.root / "runtime.sqlite3"))
        self.admin = ResolvedApiPrincipal("admin", "admin-token", frozenset(ApiPermission))
        self.viewer = ResolvedApiPrincipal(
            "viewer", "viewer-token", frozenset({ApiPermission.READ})
        )
        self.manager_only = ResolvedApiPrincipal(
            "manager",
            "manager-token",
            frozenset({ApiPermission.READ, ApiPermission.MANAGE_CONFIGURATION}),
        )
        self.api = MediaFlowApi(
            self.runtime_repository,
            None,
            principals=(self.admin, self.viewer, self.manager_only),
            configuration_service=self.configuration,
            storage_adapters=self.adapters,
            storage_browser_cursor_secret="rules-workspace-test-secret",
        )

    def _forbidden_provider_factory(self, provider_ids):
        self.provider_calls.extend(provider_ids)
        raise AssertionError("rules Save must never construct or call a Metadata Provider")

    def authority(self) -> dict[str, object]:
        active = self.configuration.active()
        assert active is not None
        return {
            "expected_revision_id": active.revision_id,
            "expected_version": active.revision_sequence or active.version,
            "expected_digest": active.digest,
        }

    def wire_authority(self) -> dict[str, object]:
        values = self.authority()
        return {
            "expectedRevisionId": values["expected_revision_id"],
            "expectedVersion": values["expected_version"],
            "expectedDigest": values["expected_digest"],
        }

    def request(
        self,
        method: str,
        path: str,
        body: object | None = None,
        *,
        token: str = "admin-token",
        query: str = "",
    ):
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
        result = b"".join(self.api(environ, lambda status, _headers: statuses.append(status)))
        return int(statuses[0].split()[0]), (json.loads(result) if result else {})

    def save(self, family: str, value: dict, *, object_id: str | None = None, **overrides):
        kwargs = self.authority()
        kwargs.update(overrides)
        return self.commands.save_object(
            family, value, actor="operator", object_id=object_id, **kwargs
        )

    def active_section(self, section: str) -> list[dict]:
        active = self.configuration.active()
        assert active is not None
        return copy.deepcopy(active.document.get(section, []))

    def assert_active_unchanged(self, before) -> None:
        after = self.configuration.active()
        assert before is not None and after is not None
        self.assertEqual(
            (before.revision_id, before.version, before.digest),
            (after.revision_id, after.version, after.digest),
        )

    def assert_no_secret_value(self, value: object, *, where: str) -> None:
        encoded = json.dumps(value, ensure_ascii=False, default=str).lower()
        for sentinel in SECRET_SENTINELS.values():
            self.assertNotIn(sentinel.lower(), encoded, where)

    def classification_rule(self, library: str = "movies", path=("Feature",)) -> dict:
        return {
            "id": "any",
            "name": "Any media",
            "conditions": {"mediaType": ["movie"]},
            "result": {"mediaLibraryId": library, "library": "Movies", "path": list(path)},
        }

    # -- five-family empty-Active onboarding ----------------------------

    def test_five_family_onboarding_publishes_real_successors_in_legal_order(self) -> None:
        self._activate_baseline(empty_rule_families(example_document()))
        status, inventory = self.request("GET", INVENTORY)
        self.assertEqual(status, 200)
        self.assertTrue(inventory["available"])
        self.assertEqual(inventory["readiness"]["state"], "EMPTY")
        self.assertEqual(self.active_section("recognitionTypes"), [])

        self.save(
            "recognitionTypes",
            {"id": "movie", "name": "Movie", "description": "feature film", "enabled": True},
        )
        self.assertEqual(
            [item["id"] for item in self.active_section("recognitionTypes")], ["movie"]
        )
        second = self.save(
            "metadataPolicies",
            {
                "id": "tmdb-movie",
                "name": "TMDB movie",
                "providerId": "tmdb",
                "mediaType": "movie",
            },
        )
        third = self.save(
            "namingPolicies",
            {
                "id": "movie-standard",
                "name": "Movie standard",
                "mediaTypeMode": "movie",
                "directoryTemplate": "{title} ({year})",
                "filenameTemplate": "{title} ({year}).{ext}",
            },
        )
        fourth = self.save(
            "classificationPolicies",
            {
                "id": "movies-default",
                "name": "Movies default",
                "rules": [self.classification_rule()],
            },
        )
        fifth = self.save(
            "organizePolicies",
            {"id": "move-manual", "operation": "MOVE", "conflictStrategy": "manual"},
        )
        for revision in (second, third, fourth, fifth):
            self.assertEqual(revision.status.value, "active")

        status, refreshed = self.request("GET", INVENTORY)
        self.assertEqual(status, 200)
        counts = refreshed["overview"]["counts"]
        for family in RULE_FAMILIES:
            self.assertEqual(counts[family], 1, family)
        self.assertEqual(
            [item["id"] for item in refreshed["sections"]["recognitionTypes"]], ["movie"]
        )
        self.assertEqual(
            [item["id"] for item in refreshed["sections"]["organizePolicies"]], ["move-manual"]
        )

    def test_type_c_identity_survives_reused_a_naming_and_classification(self) -> None:
        """The permanent AGENTS.md regression, proved on what this Task publishes.

        Type-binding authoring is a frozen boundary for this Task, so the proof here is
        that a rules-workspace edit of an existing RecognitionType keeps its identity
        and leaves the graph that reuses A naming/classification for type C intact:
        the published runtime resolver still answers `RecognitionType == C`.
        """

        edited = self.save(
            "recognitionTypes",
            {"id": "C", "name": "Special", "description": "keeps identity", "enabled": True},
            object_id="C",
        )
        stored = next(item for item in edited.document["recognitionTypes"] if item["id"] == "C")
        self.assertEqual(stored["id"], "C")
        binding = next(
            item for item in edited.document["recognitionTypePolicies"] if item["id"] == "type-C"
        )
        self.assertEqual(binding["recognitionType"], "C")
        self.assertEqual(binding["namingPolicy"], "A")
        self.assertEqual(binding["classificationPolicy"], "A")

        resolver, _catalog = self.objects._policy_resolution_catalog(edited.document)
        resolved = resolver.resolve(RecognitionType("C", "C"))
        self.assertEqual(resolved.recognition_type.type_id, "C")
        self.assertEqual(resolved.naming_policy_id, "A")
        self.assertEqual(resolved.classification_policy_id, "A")

        status, inventory = self.request("GET", INVENTORY)
        self.assertEqual(status, 200)
        row = next(item for item in inventory["sections"]["typeBindings"] if item["id"] == "type-C")
        self.assertEqual(row["recognitionType"], "C")
        self.assertEqual(row["policyReferences"]["namingPolicy"], "A")
        self.assertIn("C", [item["id"] for item in inventory["sections"]["recognitionTypes"]])

    def test_deferred_graph_families_are_not_authored_by_this_surface(self) -> None:
        for family in ("recognitionRules", "typeBindings", "storages", "webhooks"):
            with self.subTest(family=family):
                status, body = self.request(
                    "POST",
                    f"{BASE}/objects/{family}",
                    {"object": {"id": "x", "name": "x"}, **self.wire_authority()},
                )
                self.assertEqual(status, 404, family)
                self.assertEqual(body["error"]["code"], "not_found")
                self.assertIn("recognitionTypes", body["error"]["details"]["nextAction"])

    # -- allowed and rejected operation states ---------------------------

    def test_create_edit_state_change_and_delete_all_publish_active_successors(self) -> None:
        created = self.save(
            "recognitionTypes",
            {"id": "doc", "name": "Documentary", "description": "d", "enabled": True},
        )
        self.assertTrue(any(item["id"] == "doc" for item in created.document["recognitionTypes"]))

        edited = self.save(
            "recognitionTypes", {"id": "doc", "name": "Documentary Feature"}, object_id="doc"
        )
        stored = next(item for item in edited.document["recognitionTypes"] if item["id"] == "doc")
        self.assertEqual(stored["name"], "Documentary Feature")
        # A focused edit preserves fields the typed form did not submit.
        self.assertEqual(stored["description"], "d")
        self.assertIs(stored["enabled"], True)

        disabled = self.commands.set_enabled(
            "recognitionTypes", "doc", enabled=False, actor="operator", **self.authority()
        )
        stored = next(item for item in disabled.document["recognitionTypes"] if item["id"] == "doc")
        self.assertIs(stored["enabled"], False)
        enabled = self.commands.set_enabled(
            "recognitionTypes", "doc", enabled=True, actor="operator", **self.authority()
        )
        stored = next(item for item in enabled.document["recognitionTypes"] if item["id"] == "doc")
        self.assertIs(stored["enabled"], True)

        removed = self.commands.remove_object(
            "recognitionTypes", "doc", actor="operator", **self.authority()
        )
        self.assertFalse(any(item["id"] == "doc" for item in removed.document["recognitionTypes"]))

    def test_edit_cannot_change_id_or_forge_another_object(self) -> None:
        before = self.configuration.active()
        self.save("recognitionTypes", {"id": "keep", "name": "Keep", "enabled": True})
        with self.assertRaises(RulesWorkspaceSaveError) as caught:
            self.save("recognitionTypes", {"id": "other", "name": "Renamed"}, object_id="keep")
        self.assertEqual(caught.exception.code, "rules_id_immutable")
        self.assertEqual(caught.exception.stage, "compose")
        self.assertFalse(
            any(item["id"] == "other" for item in self.active_section("recognitionTypes"))
        )
        self.assertTrue(
            any(item["id"] == "keep" for item in self.active_section("recognitionTypes"))
        )
        self.assertGreaterEqual(self.configuration.active().version, before.version)

    def test_create_over_an_existing_id_is_rejected_and_active_preserved(self) -> None:
        before = self.configuration.active()
        with self.assertRaises(RulesWorkspaceSaveError) as caught:
            self.save("recognitionTypes", {"id": "A", "name": "Hijack"})
        self.assertEqual(caught.exception.code, "rules_duplicate")
        self.assert_active_unchanged(before)
        self.assertEqual(
            [item["name"] for item in self.active_section("recognitionTypes") if item["id"] == "A"],
            ["Normal Movie"],
        )

    def test_missing_object_reads_and_commands_report_not_found(self) -> None:
        before = self.configuration.active()
        for family in RULE_FAMILIES:
            with self.subTest(family=family):
                with self.assertRaises(RulesWorkspaceSaveError) as caught:
                    self.commands.remove_object(
                        family, "ghost", actor="operator", **self.authority()
                    )
                self.assertEqual(caught.exception.code, "rules_object_not_found")
                self.assertEqual(caught.exception.status, 404)
                status, _ = self.request("GET", f"{BASE}/objects/{family}/ghost")
                self.assertEqual(status, 404)
                status, _ = self.request("GET", f"{BASE}/objects/{family}/ghost/copy")
                self.assertEqual(status, 404)
                status, _ = self.request("GET", f"{BASE}/objects/{family}/ghost/impact")
                self.assertEqual(status, 404)
        self.assert_active_unchanged(before)

    def test_unsupported_family_and_operation_are_rejected_explicitly(self) -> None:
        before = self.configuration.active()
        for family in ("recognitionRules", "typeBindings", "storages", "bogus"):
            with self.subTest(family=family):
                with self.assertRaises(RulesWorkspaceSaveError) as caught:
                    self.save(family, {"id": "x", "name": "x"})
                self.assertEqual(caught.exception.code, "rules_family_unsupported")
        # OrganizePolicy has no enable state in the domain, so none is invented.
        with self.assertRaises(RulesWorkspaceSaveError) as caught:
            self.commands.set_enabled(
                "organizePolicies", "A", enabled=False, actor="operator", **self.authority()
            )
        self.assertEqual(caught.exception.code, "rules_operation_unsupported")
        self.assert_active_unchanged(before)

    def test_inventory_reports_only_supported_actions_per_family(self) -> None:
        status, inventory = self.request("GET", INVENTORY)
        self.assertEqual(status, 200)
        self.assertTrue(inventory["canManage"])
        actions = inventory["actions"]
        for family in RULE_FAMILIES:
            with self.subTest(family=family):
                entry = actions[family]
                self.assertTrue(entry["create"])
                self.assertTrue(entry["edit"])
                self.assertTrue(entry["copy"])
                self.assertTrue(entry["remove"])
                self.assertEqual(entry["toggle"], family != "organizePolicies")
                self.assertIsNone(entry["blocker"])
        for family in ("typeBindings", "recognitionRules"):
            entry = actions[family]
            self.assertFalse(entry["edit"])
            self.assertFalse(entry["create"])
            self.assertIn("later in-Slice unit", entry["blocker"])

    # -- form authority from the actual domain ----------------------------

    def test_form_authority_exposes_actual_fields_references_and_secret_readiness(self) -> None:
        status, authority = self.request("GET", FORM_AUTHORITY)
        self.assertEqual(status, 200)
        families = {item["family"]: item for item in authority["families"]}
        self.assertEqual(set(families), set(RULE_FAMILIES))
        self.assertEqual(
            families["recognitionTypes"]["fields"], ["description", "enabled", "id", "name"]
        )
        self.assertIn("providerId", families["metadataPolicies"]["fields"])
        self.assertIn("maxCandidateEnrichments", families["metadataPolicies"]["fields"])
        for template in (
            "directoryTemplate",
            "filenameTemplate",
            "seriesDirectoryTemplate",
            "seasonDirectoryTemplate",
            "episodeFilenameTemplate",
            "multiEpisodeFileTemplate",
        ):
            self.assertIn(template, families["namingPolicies"]["fields"], template)
        self.assertIn("rules", families["classificationPolicies"]["fields"])
        self.assertIn("sourceDirectoryCleanup", families["organizePolicies"]["fields"])
        self.assertNotIn("enabled", families["organizePolicies"]["fields"])
        self.assertIs(families["organizePolicies"]["supportsEnabled"], False)
        self.assertIs(families["recognitionTypes"]["supportsEnabled"], True)

        # Actual configured MediaLibrary authorities, never reference-image examples.
        self.assertEqual({item["id"] for item in authority["mediaLibraries"]}, {"movies", "tv"})
        self.assertEqual([item["providerId"] for item in authority["metadataProviders"]], ["tmdb"])
        readiness = {
            entry["field"]: entry["state"]
            for entry in authority["metadataProviders"][0]["secretReadiness"]
        }
        # Readiness reflects this deployment's actual environment, per name:
        # TMDB_ACCESS_TOKEN is set here, TMDB_TOKEN is not.
        self.assertEqual(readiness, {"TMDB_ACCESS_TOKEN": "SET", "TMDB_TOKEN": "UNSET"})
        self.assert_no_secret_value(authority, where="form authority")

        enums = authority["enums"]
        self.assertEqual(set(enums["mediaTypes"]), {"movie", "tv"})
        # The canonical values the shared normalizer writes for an OrganizePolicy.
        self.assertEqual(
            set(enums["organizeOperations"]), {"move", "copy", "hard_link", "soft_link"}
        )
        self.assertNotIn("delete", enums["organizeOperations"])
        self.assertNotIn("auto", enums["organizeOperations"])
        self.assertIn("title", enums["namingVariables"])
        self.assertNotIn("genre", enums["namingVariables"])
        self.assertIn("mediaType", enums["classificationConditions"])
        self.assertNotIn("actors", enums["classificationConditions"])
        self.assertEqual(
            set(enums["conflictStrategies"]), {"skip", "rename", "manual", "overwrite"}
        )

    def test_edit_projection_round_trips_real_values_and_reference_impact(self) -> None:
        status, projection = self.request("GET", f"{BASE}/objects/recognitionTypes/C")
        self.assertEqual(status, 200)
        self.assertEqual(projection["object"]["id"], "C")
        self.assertEqual(projection["object"]["name"], "Special")
        self.assertIs(projection["object"]["enabled"], True)
        references = projection["references"]
        self.assertGreater(references["total"], 0)
        self.assertTrue(references["removalBlocked"])
        self.assertTrue(
            {item["section"] for item in references["items"]}
            & {"recognitionRules", "recognitionTypePolicies"}
        )
        self.assertTrue(all(item["label"] for item in references["items"]))
        self.assertEqual(projection["sideEffects"], "none")
        self.assert_no_secret_value(projection, where="edit projection")

        status, naming = self.request("GET", f"{BASE}/objects/namingPolicies/A")
        self.assertEqual(status, 200)
        self.assertEqual(naming["object"]["mediaTypeMode"], "movie")
        self.assertIn("provider_id", naming["object"]["directoryTemplate"])

        status, organize = self.request("GET", f"{BASE}/objects/organizePolicies/A")
        self.assertEqual(status, 200)
        self.assertNotIn("enabled", organize["object"])
        self.assertIn("sourceDirectoryCleanup", organize["object"])
        self.assertIn("duplicateDetection", organize["object"])

    def test_reads_have_zero_configuration_provider_task_or_storage_side_effects(self) -> None:
        before = self.configuration.active()
        revisions = len(self.config_repo.list_revisions(limit=200))
        tasks_before = len(self.runtime_repository.list_tasks(limit=50))
        for path in (
            INVENTORY,
            FORM_AUTHORITY,
            f"{BASE}/objects/recognitionTypes/C",
            f"{BASE}/objects/namingPolicies/A/copy",
            f"{BASE}/objects/metadataPolicies/A/impact",
        ):
            self.assertEqual(self.request("GET", path)[0], 200, path)
        self.assert_active_unchanged(before)
        self.assertEqual(len(self.config_repo.list_revisions(limit=200)), revisions)
        self.assertEqual(len(self.runtime_repository.list_tasks(limit=50)), tasks_before)
        self.assertEqual(self.provider_calls, [])
        for adapter in self.adapters.values():
            self.assertEqual(adapter.mutations, [], adapter.storage_id)

    # -- copy -------------------------------------------------------------

    def test_copy_uses_a_new_stable_id_and_defaults_disabled_where_supported(self) -> None:
        status, candidate = self.request("GET", f"{BASE}/objects/metadataPolicies/A/copy")
        self.assertEqual(status, 200)
        self.assertEqual(candidate["object"]["id"], "A-copy")
        self.assertIs(candidate["object"]["enabled"], False)
        self.assertEqual(candidate["object"]["providerId"], "tmdb")
        self.assertEqual(candidate["source"]["id"], "A")
        self.assertEqual(candidate["sideEffects"], "none")
        self.assertFalse(
            any(item["id"] == "A-copy" for item in self.active_section("metadataPolicies"))
        )

        published = self.save("metadataPolicies", candidate["object"])
        stored = next(
            item for item in published.document["metadataPolicies"] if item["id"] == "A-copy"
        )
        self.assertIs(stored["enabled"], False)

    def test_copy_of_organize_policy_invents_no_enabled_field(self) -> None:
        status, candidate = self.request("GET", f"{BASE}/objects/organizePolicies/A/copy")
        self.assertEqual(status, 200)
        self.assertNotIn("enabled", candidate["object"])
        self.assertEqual(candidate["object"]["operation"], "MOVE")
        published = self.save("organizePolicies", candidate["object"])
        stored = next(
            item for item in published.document["organizePolicies"] if item["id"] == "A-copy"
        )
        self.assertNotIn("enabled", stored)

    def test_copy_id_allocation_stays_unique(self) -> None:
        self.save("recognitionTypes", {"id": "E", "name": "Essay", "enabled": True})
        self.save("recognitionTypes", {"id": "E-copy", "name": "Existing", "enabled": True})
        status, candidate = self.request("GET", f"{BASE}/objects/recognitionTypes/E/copy")
        self.assertEqual(status, 200)
        self.assertEqual(candidate["object"]["id"], "E-copy-2")

    # -- reference-protected deletion ------------------------------------

    def test_referenced_deletion_is_blocked_with_actionable_impact(self) -> None:
        before = self.configuration.active()
        with self.assertRaises(RulesWorkspaceSaveError) as caught:
            self.commands.remove_object(
                "recognitionTypes", "C", actor="operator", **self.authority()
            )
        self.assertEqual(caught.exception.code, "rules_object_referenced")
        self.assertEqual(caught.exception.stage, "reference")
        self.assertTrue(caught.exception.details["referenceItems"])
        self.assert_active_unchanged(before)
        self.assertEqual(self.config_repo.activations, self.activations_at_baseline)

        status, impact = self.request("GET", f"{BASE}/objects/metadataPolicies/A/impact")
        self.assertEqual(status, 200)
        self.assertTrue(impact["references"]["removalBlocked"])
        self.assertGreater(impact["references"]["total"], 0)

    def test_unreferenced_deletion_publishes_and_touches_no_media_or_history(self) -> None:
        self.save("namingPolicies", {"id": "temp", "name": "Temp", "enabled": True})
        revisions_before = len(self.config_repo.list_revisions(limit=200))
        removed = self.commands.remove_object(
            "namingPolicies", "temp", actor="operator", **self.authority()
        )
        self.assertFalse(any(item["id"] == "temp" for item in removed.document["namingPolicies"]))
        for adapter in self.adapters.values():
            self.assertEqual(adapter.mutations, [], adapter.storage_id)
        self.assertGreater(len(self.config_repo.list_revisions(limit=200)), revisions_before)

    def test_referenced_deletion_via_api_returns_reference_evidence(self) -> None:
        status, body = self.request(
            "DELETE", f"{BASE}/objects/recognitionTypes/C", self.wire_authority()
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "rules_object_referenced")
        details = body["error"]["details"]
        self.assertEqual(details["objectKind"], "recognitionTypes")
        self.assertEqual(details["objectId"], "C")
        self.assertEqual(details["stage"], "reference")
        self.assertTrue(details["referenceItems"])
        self.assertEqual(details["durableState"], "active_unchanged")

    # -- field, template, path, reference and secret failures ------------

    def test_invalid_fields_templates_paths_and_effects_fail_with_object_identity(self) -> None:
        cases = {
            "unknown field": (
                "recognitionTypes",
                {"id": "x", "name": "x", "bogus": 1},
                "rules_invalid_request",
            ),
            "non-boolean enabled": (
                "recognitionTypes",
                {"id": "x", "name": "x", "enabled": "yes"},
                "rules_invalid_field",
            ),
            "unknown naming variable": (
                "namingPolicies",
                {"id": "x", "name": "x", "directoryTemplate": "{bogus_var}"},
                "rules_invalid_field",
            ),
            "template path separator": (
                "namingPolicies",
                {"id": "x", "name": "x", "directoryTemplate": "movies/{title}"},
                "rules_invalid_field",
            ),
            "absolute template": (
                "namingPolicies",
                {"id": "x", "name": "x", "directoryTemplate": "/media/{title}"},
                "rules_invalid_field",
            ),
            "threshold ordering": (
                "metadataPolicies",
                {
                    "id": "x",
                    "name": "x",
                    "providerId": "tmdb",
                    "automaticThreshold": 10,
                    "confirmationThreshold": 90,
                },
                "rules_invalid_field",
            ),
            "empty classification rules": (
                "classificationPolicies",
                {"id": "x", "name": "x", "rules": []},
                "rules_invalid_field",
            ),
            "unsafe classification path": (
                "classificationPolicies",
                {
                    "id": "x",
                    "name": "x",
                    "rules": [self.classification_rule(path=("..", "escape"))],
                },
                "rules_invalid_field",
            ),
            "overwrite conflict": (
                "organizePolicies",
                {"id": "x", "operation": "MOVE", "conflictStrategy": "skip", "overwrite": True},
                "rules_invalid_field",
            ),
            "unsupported operation": (
                "organizePolicies",
                {"id": "x", "operation": "DELETE", "conflictStrategy": "manual"},
                "rules_invalid_field",
            ),
        }
        for label, (family, value, expected_code) in cases.items():
            with self.subTest(case=label):
                before = self.configuration.active()
                with self.assertRaises(RulesWorkspaceSaveError) as caught:
                    self.save(family, value)
                self.assertEqual(caught.exception.code, expected_code)
                self.assertEqual(caught.exception.stage, "compose")
                self.assertEqual(caught.exception.object_kind, family)
                self.assert_active_unchanged(before)

    def test_unconfigured_provider_and_missing_library_are_visible_blockers(self) -> None:
        before = self.configuration.active()
        with self.assertRaises(RulesWorkspaceSaveError) as caught:
            self.save("metadataPolicies", {"id": "x", "name": "x", "providerId": "imdb"})
        self.assertEqual(caught.exception.code, "rules_reference_unavailable")
        self.assertEqual(caught.exception.stage, "reference")
        self.assertIn("tmdb", str(caught.exception))

        with self.assertRaises(RulesWorkspaceSaveError) as caught:
            self.save(
                "classificationPolicies",
                {
                    "id": "x",
                    "name": "x",
                    "rules": [
                        {
                            "id": "r",
                            "name": "r",
                            "conditions": {"mediaType": ["movie"]},
                            "result": {
                                "mediaLibraryId": "nope",
                                "library": "Nope",
                                "path": ["x"],
                            },
                        }
                    ],
                },
            )
        self.assertEqual(caught.exception.code, "rules_reference_unavailable")
        self.assertIn("MediaLibrary", str(caught.exception))
        self.assert_active_unchanged(before)

    def test_disabled_media_library_reference_is_blocked_not_substituted(self) -> None:
        document = copy.deepcopy(self.baseline_document)
        for item in document["mediaLibraries"]:
            if item["id"] == "tv":
                item["enabled"] = False
        self._activate_baseline(document)
        before = self.configuration.active()
        with self.assertRaises(RulesWorkspaceSaveError) as caught:
            self.save(
                "classificationPolicies",
                {
                    "id": "tv-rules",
                    "name": "TV rules",
                    "rules": [
                        {
                            "id": "tv",
                            "name": "TV",
                            "conditions": {"mediaType": ["tv"]},
                            "result": {
                                "mediaLibraryId": "tv",
                                "library": "TV Shows",
                                "path": ["Series"],
                            },
                        }
                    ],
                },
            )
        self.assertEqual(caught.exception.code, "rules_reference_disabled")
        self.assertIn("disabled", str(caught.exception))
        self.assert_active_unchanged(before)

    def test_api_normalizes_a_field_failure_into_a_bounded_error_document(self) -> None:
        status, body = self.request(
            "POST",
            f"{BASE}/objects/namingPolicies",
            {
                "object": {"id": "bad", "name": "Bad", "directoryTemplate": "{nope_var}"},
                **self.wire_authority(),
            },
        )
        self.assertEqual(status, 400)
        error = body["error"]
        self.assertEqual(error["code"], "rules_invalid_field")
        details = error["details"]
        self.assertEqual(details["objectKind"], "namingPolicies")
        self.assertEqual(details["objectId"], "bad")
        self.assertEqual(details["stage"], "compose")
        # A rejected field never reached persistence: nothing was published and no
        # durable successor exists, while the operator's form input stays correctable.
        self.assertEqual(details["durableState"], "active_unchanged")
        self.assertEqual(details["candidateState"], "not_published")
        self.assertTrue(details["retrySafe"])
        self.assertIn("nextAction", details)
        self.assert_no_secret_value(body, where="field failure document")

    # -- exact-Active stale writers and concurrency ------------------------

    def test_stale_authority_cannot_publish_the_wrong_successor(self) -> None:
        stale = self.authority()
        self.save("recognitionTypes", {"id": "winner", "name": "Winner", "enabled": True})
        before = self.configuration.active()
        with self.assertRaises(ConfigurationVersionConflict) as caught:
            self.save(
                "recognitionTypes",
                {"id": "loser", "name": "Loser", "enabled": True},
                **stale,
            )
        self.assertIn("stale", str(caught.exception))
        self.assertEqual(caught.exception.durable_state, "active_preserved")
        self.assert_active_unchanged(before)
        self.assertFalse(
            any(item["id"] == "loser" for item in self.active_section("recognitionTypes"))
        )

    def test_api_reports_stale_authority_as_an_actionable_conflict(self) -> None:
        authority = self.wire_authority()
        self.save("recognitionTypes", {"id": "first", "name": "First", "enabled": True})
        status, body = self.request(
            "POST",
            f"{BASE}/objects/recognitionTypes",
            {"object": {"id": "second", "name": "Second"}, **authority},
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "configuration_version_conflict")
        details = body["error"]["details"]
        self.assertEqual(details["durableState"], "active_winner_preserved")
        self.assertEqual(details["candidateState"], "not_published")
        self.assertIn("nextAction", details)

    def test_simultaneous_saves_never_publish_a_mixed_or_lost_successor(self) -> None:
        results: list[str] = []
        errors: list[str] = []
        started = threading.Barrier(3)
        release = threading.Barrier(3)

        def writer(object_id: str) -> None:
            # Both writers observe the same Active, then race to publish it.
            shared = self.authority()
            started.wait(timeout=10)
            release.wait(timeout=10)
            try:
                self.commands.save_object(
                    "recognitionTypes",
                    {"id": object_id, "name": object_id, "enabled": True},
                    actor=f"writer-{object_id}",
                    **shared,
                )
                results.append(object_id)
            except Exception as error:  # noqa: BLE001 - recorded and asserted below
                errors.append(getattr(error, "code", type(error).__name__))

        threads = [threading.Thread(target=writer, args=(name,)) for name in ("race-a", "race-b")]
        for thread in threads:
            thread.start()
        started.wait(timeout=10)
        release.wait(timeout=10)
        for thread in threads:
            thread.join(timeout=60)

        ids = {item["id"] for item in self.active_section("recognitionTypes")}
        published = sorted({"race-a", "race-b"} & ids)
        # Publication is linearized by the repository fence: the resulting Active is
        # one immutable successor that never mixes two candidates. Either both wrote
        # onto one serial chain, or the loser was refused with its own durable state.
        self.assertEqual(len(published), len(results), (results, errors))
        self.assertEqual(self.configuration.active().status.value, "active")
        if published != ["race-a", "race-b"]:
            self.assertTrue(errors)
            # A loser is refused by concurrency fencing, a duplicate identity, or the
            # single bounded read-only check slot — all retry-safe, never a silent
            # partial publication.
            self.assertTrue(
                set(errors)
                <= {
                    "rules_invalid_request",
                    "rules_duplicate",
                    "rules_storage_check_failed",
                    "rules_evidence_failed",
                    "ConfigurationVersionConflict",
                    "ConfigurationActivationConflict",
                },
                errors,
            )
        baseline = {item["id"] for item in example_document()["recognitionTypes"]}
        self.assertTrue(baseline <= ids, (baseline, ids))

    def test_missing_or_unreadable_active_fails_closed_without_a_fallback(self) -> None:
        empty_root = self.root / "no-active"
        empty_root.mkdir()
        repository = SQLiteConfigurationRepository(empty_root / "config.sqlite3")
        self.addCleanup(repository.close)
        service = ManagedConfigurationService(
            repository, bootstrap_database_path=str(empty_root / "runtime.sqlite3")
        )
        commands = RulesWorkspaceCommandService(
            ConfigurationObjectService(service, storage_browser_cursor_secret="x" * 32)
        )
        with self.assertRaises(Exception) as caught:
            commands.save_object(
                "recognitionTypes",
                {"id": "x", "name": "x"},
                actor="operator",
                expected_revision_id="r",
                expected_version=1,
                expected_digest="d",
            )
        self.assertNotIsInstance(caught.exception, AssertionError)
        self.assertIsNone(service.active())

    # -- publication integrity --------------------------------------------

    def test_save_publishes_and_is_consumed_as_the_same_immutable_authority(self) -> None:
        published = self.save(
            "recognitionTypes", {"id": "consumed", "name": "Consumed", "enabled": True}
        )
        status, inventory = self.request("GET", INVENTORY)
        self.assertEqual(status, 200)
        self.assertEqual(inventory["active"]["sequence"], published.revision_sequence)
        self.assertIn(
            "consumed", [item["id"] for item in inventory["sections"]["recognitionTypes"]]
        )
        runtime = self.configuration.active()
        assert runtime is not None
        self.assertEqual(runtime.revision_id, published.revision_id)
        self.assertEqual(self.api._runtime_binding.snapshot_id, published.revision_id)
        self.assertEqual(self.api._runtime_binding.snapshot_digest, published.digest)

    def test_save_starts_no_task_job_provider_call_or_storage_mutation(self) -> None:
        tasks_before = len(self.runtime_repository.list_tasks(limit=50))
        self.save("namingPolicies", {"id": "quiet", "name": "Quiet", "enabled": True})
        self.save(
            "organizePolicies", {"id": "quiet", "operation": "COPY", "conflictStrategy": "skip"}
        )
        self.assertEqual(self.provider_calls, [])
        for adapter in self.adapters.values():
            self.assertEqual(adapter.mutations, [], adapter.storage_id)
        self.assertEqual(len(self.runtime_repository.list_tasks(limit=50)), tasks_before)

    def test_unknown_persistence_outcome_reports_not_saved_and_never_replays(self) -> None:
        class Outage(ManagedConfigurationService):
            armed = True

            def validate(self, revision_id, *, actor):
                if Outage.armed:
                    Outage.armed = False
                    raise RuntimeError("simulated persistence outage")
                return super().validate(revision_id, actor=actor)

        broken = Outage(
            SQLiteConfigurationRepository(self.root / "config.sqlite3"),
            bootstrap_database_path=str(self.root / "runtime.sqlite3"),
        )
        self.addCleanup(broken.repository.close)
        commands = RulesWorkspaceCommandService(
            ConfigurationObjectService(
                broken, storage_browser_cursor_secret="rules-workspace-test-secret"
            )
        )
        before = broken.active()
        with self.assertRaises(RulesWorkspaceSaveError) as caught:
            commands.save_object(
                "recognitionTypes",
                {"id": "unknown", "name": "Unknown"},
                actor="operator",
                **self.authority(),
            )
        self.assertEqual(caught.exception.code, "rules_persistence_failed")
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(caught.exception.durable_state, "active_preserved")
        self.assert_active_unchanged(before)
        self.assertFalse(
            any(item["id"] == "unknown" for item in self.active_section("recognitionTypes"))
        )

    def test_api_rejects_a_save_without_observed_active_identity(self) -> None:
        # Without the exact Active identity the backend cannot prove which snapshot
        # the operator reviewed, so it fails closed instead of publishing.
        status, body = self.request(
            "POST",
            f"{BASE}/objects/recognitionTypes",
            {"object": {"id": "no-identity", "name": "x"}},
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_request")
        self.assertFalse(
            any(item["id"] == "no-identity" for item in self.active_section("recognitionTypes"))
        )

    # -- RBAC, audit and redaction ----------------------------------------

    def test_permission_boundaries_are_backend_authoritative(self) -> None:
        authority = self.wire_authority()
        body = {"object": {"id": "rbac", "name": "RBAC"}, **authority}
        self.assertEqual(
            self.request("POST", f"{BASE}/objects/recognitionTypes", body, token="absent")[0], 401
        )
        self.assertEqual(
            self.request("POST", f"{BASE}/objects/recognitionTypes", body, token="viewer-token")[0],
            403,
        )
        # MANAGE_CONFIGURATION alone is not publication authority: activation is required.
        status, denied = self.request(
            "POST", f"{BASE}/objects/recognitionTypes", body, token="manager-token"
        )
        self.assertEqual(status, 403)
        self.assertEqual(denied["error"]["code"], "forbidden")
        self.assertFalse(
            any(item["id"] == "rbac" for item in self.active_section("recognitionTypes"))
        )
        # A read stays available and reports the missing capability truthfully.
        status, inventory = self.request("GET", INVENTORY, token="viewer-token")
        self.assertEqual(status, 200)
        self.assertFalse(inventory["canManage"])
        self.assertEqual(self.request("GET", FORM_AUTHORITY, token="viewer-token")[0], 200)

    def test_every_lifecycle_command_requires_save_authority(self) -> None:
        self.save("recognitionTypes", {"id": "guard", "name": "Guard", "enabled": True})
        authority = self.wire_authority()
        commands = [
            (
                "POST",
                f"{BASE}/objects/recognitionTypes/guard/state/disable",
                {"enabled": False, **authority},
            ),
            ("DELETE", f"{BASE}/objects/recognitionTypes/guard", authority),
            (
                "PUT",
                f"{BASE}/objects/recognitionTypes/guard",
                {"object": {"id": "guard", "name": "changed"}, **authority},
            ),
        ]
        for method, path, body in commands:
            with self.subTest(path=path):
                self.assertEqual(self.request(method, path, body, token="viewer-token")[0], 403)
        stored = next(
            item for item in self.active_section("recognitionTypes") if item["id"] == "guard"
        )
        self.assertEqual(stored["name"], "Guard")
        self.assertIs(stored["enabled"], True)

    def test_request_envelopes_are_bounded_and_method_correct(self) -> None:
        authority = self.wire_authority()
        self.assertEqual(self.request("GET", INVENTORY, query="unknown=1")[0], 400)
        self.assertEqual(self.request("GET", FORM_AUTHORITY, query="x=1")[0], 400)
        self.assertEqual(
            self.request("POST", f"{BASE}/objects/recognitionTypes", {"object": {}})[0], 400
        )
        self.assertEqual(
            self.request(
                "POST",
                f"{BASE}/objects/recognitionTypes",
                {"object": {"id": "x"}, **authority, "extra": 1},
            )[0],
            400,
        )
        self.assertEqual(self.request("PATCH", f"{BASE}/objects/recognitionTypes/A")[0], 405)
        self.assertEqual(self.request("PUT", INVENTORY)[0], 405)
        self.assertEqual(self.request("POST", f"{BASE}/form-authority")[0], 405)
        # A state-change verb must match its body intent.
        self.assertEqual(
            self.request(
                "POST",
                f"{BASE}/objects/recognitionTypes/A/state/disable",
                {"enabled": True, **authority},
            )[0],
            400,
        )

    def test_save_route_accepts_only_the_observed_active_identity(self) -> None:
        self.assertEqual(
            self.request(
                "POST",
                f"{BASE}/objects/recognitionTypes",
                {
                    "object": {"id": "x"},
                    "expectedRevisionId": "r",
                    "expectedVersion": "1",
                    "expectedDigest": "d",
                },
            )[0],
            400,
        )

    def test_audit_records_bounded_secret_free_change_evidence(self) -> None:
        published = self.save(
            "recognitionTypes", {"id": "audited", "name": "Audited", "enabled": True}
        )
        self.configuration.active()
        revisions = {
            revision.revision_id: revision
            for revision in self.config_repo.list_revisions(limit=200)
        }
        self.assertIn(published.revision_id, revisions)
        audits = self.config_repo.list_revision_audits(published.revision_id, limit=200)
        self.assertTrue(audits)
        encoded = json.dumps(
            [
                {
                    "action": audit.action,
                    "actor": audit.actor,
                    "before": audit.safe_before(),
                    "after": audit.safe_after(),
                }
                for audit in audits
            ],
            ensure_ascii=False,
            default=str,
        ).lower()
        for sentinel in SECRET_SENTINELS.values():
            self.assertNotIn(sentinel.lower(), encoded)
        self.assertTrue(any("activate" in audit.action for audit in audits))
        self.assertTrue(any("draft_edit" in audit.action for audit in audits))

    def test_no_read_or_failure_document_ever_carries_a_secret_value(self) -> None:
        for path in (INVENTORY, FORM_AUTHORITY, f"{BASE}/objects/metadataPolicies/A"):
            status, body = self.request("GET", path)
            self.assertEqual(status, 200, path)
            self.assert_no_secret_value(body, where=path)
        status, body = self.request(
            "POST",
            f"{BASE}/objects/metadataPolicies",
            {
                "object": {
                    "id": "secret",
                    "name": "Secret probe",
                    "providerId": "tmdb",
                    "apiKey": SECRET_SENTINELS["TMDB_ACCESS_TOKEN"],
                },
                **self.wire_authority(),
            },
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "rules_invalid_request")
        self.assert_no_secret_value(body, where="rejected metadata save")
        self.assertFalse(
            any(item["id"] == "secret" for item in self.active_section("metadataPolicies"))
        )

    def test_command_family_surface_matches_the_inventory_authority(self) -> None:
        self.assertEqual(
            set(RULE_FAMILIES),
            {
                "recognitionTypes",
                "metadataPolicies",
                "namingPolicies",
                "classificationPolicies",
                "organizePolicies",
            },
        )
        status, inventory = self.request("GET", INVENTORY)
        self.assertEqual(status, 200)
        self.assertEqual(
            sorted(
                family
                for family, entry in inventory["actions"].items()
                if entry["edit"] and entry["blocker"] is None
            ),
            sorted(RULE_FAMILIES),
        )


if __name__ == "__main__":
    unittest.main()
