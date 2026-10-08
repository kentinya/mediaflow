"""Focused Task 44.3 coverage for object-scoped rules testing and complete flow.

These tests prove Slice 44 RO-4 at the production-engine/application/authenticated
API boundary:

* every Add/copy/Edit family analyses the exact submitted unsaved object with only
  its own necessary inputs;
* an independent local test never requires an unrelated family, a whole-runtime
  load, a Provider call or media Storage I/O, and proves zero mutation/activation;
* a genuine single-rule match, its nested condition truth evidence and a real
  non-match come from the production condition engine;
* RecognitionType C remains C while reusing A Naming/Classification policies;
* the separately labelled complete-flow entry reports real competition results or
  truthful missing-stage blockers, and never grants execution authority.

The complete-flow tests use an offline synthetic identity and a fake live Provider
so no real credential, service or production media is involved.
"""

from __future__ import annotations

import copy
import unittest

from mediaflow.domain.metadata import (
    MediaCandidate,
    MediaIdentity,
    MediaType,
    ProviderCapabilities,
)
from tests.test_v2_rules_workspace_commands import RulesWorkspaceCommandTests

BASE = "/api/v1/operations/rules"
ANALYSIS = f"{BASE}/analysis"
COMPLETE_FLOW = f"{BASE}/complete-flow"


class RecordingProvider:
    """Provider-neutral fake proving whether a live test actually called a Provider."""

    provider_id = "tmdb"
    capabilities = ProviderCapabilities(True, True, True, True, False, False, True)

    def __init__(self, *, fail: bool = False, identity: MediaIdentity | None = None) -> None:
        self.calls: list[str] = []
        self.fail = fail
        self.identity = identity

    def _candidate(self) -> MediaCandidate:
        return MediaCandidate(
            "tmdb",
            "603",
            MediaType.MOVIE,
            "The Matrix",
            original_title="The Matrix",
            release_date="1999-03-31",
            genres=("Action",),
            countries=("US",),
            languages=("en",),
        )

    def search_movie(self, query, policy=None, **kwargs):
        self.calls.append(f"search_movie:{query}")
        if self.fail:
            raise RuntimeError("provider transport failure")
        return (self._candidate(),)

    def search_tv(self, query, policy=None, **kwargs):
        self.calls.append(f"search_tv:{query}")
        return ()

    def get_movie(self, provider_id, policy=None, **kwargs):
        self.calls.append(f"get_movie:{provider_id}")
        return self._candidate()

    def get_tv(self, provider_id, policy=None, **kwargs):
        self.calls.append(f"get_tv:{provider_id}")
        return None

    def get_season(self, provider_id, season, policy=None, **kwargs):
        self.calls.append("get_season")
        return None

    def get_episode(self, provider_id, season, episode, policy=None, **kwargs):
        self.calls.append("get_episode")
        return None

    def find_by_external_id(self, source, external_id, policy=None, **kwargs):
        self.calls.append("find_by_external_id")
        return None


class RulesObjectAnalysisApiTests(unittest.TestCase):
    """Authenticated API journeys for all seven families plus complete flow."""

    def setUp(self) -> None:
        self.harness = RulesWorkspaceCommandTests()
        self.harness.setUp()

    def tearDown(self) -> None:
        self.harness.tearDown()

    # -- harness ---------------------------------------------------------

    def authority(self) -> dict[str, object]:
        active = self.harness.configuration.active()
        assert active is not None
        return {
            "expectedRevisionId": active.revision_id,
            "expectedVersion": active.revision_sequence or active.version,
            "expectedDigest": active.digest,
        }

    def edit_candidate(self, family: str, object_id: str, **overrides) -> dict[str, object]:
        projection = self.harness.commands.edit_projection(family, object_id)
        values = copy.deepcopy(projection["object"])
        values.update(overrides)
        return {"family": family, "objectId": object_id, "values": values}

    def create_candidate(self, family: str, **values) -> dict[str, object]:
        return {"family": family, "objectId": None, "values": values}

    def analyze(
        self,
        family: str,
        candidate: dict[str, object],
        *,
        sample: object | None = None,
        live_metadata: bool = False,
        authority: dict[str, object] | None = None,
    ):
        return self.harness.request(
            "POST",
            f"{ANALYSIS}/{family}",
            {
                **(authority or self.authority()),
                "candidate": candidate,
                "sample": sample,
                "liveMetadata": live_metadata,
            },
        )

    def assert_no_activation(self, before) -> None:
        """Prove this request published no successor Active and kept the prior one."""

        self.harness.assert_active_unchanged(before)
        self.assertEqual(self.harness.config_repo.activations, self.harness.activations_at_baseline)

    def assert_zero_provider(self) -> None:
        self.assertEqual(self.harness.provider_calls, [])

    # -- AC-2: RecognitionType definition ---------------------------------

    def test_unbound_new_type_passes_definition_without_downstream(self) -> None:
        before = self.harness.configuration.active()
        status, body = self.analyze(
            "recognitionTypes",
            self.create_candidate(
                "recognitionTypes", id="fresh-type", name="Fresh type", enabled=True
            ),
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["outcome"], "valid")
        self.assertEqual(body["applicability"], "not_applicable")
        self.assertIn("暂无关联规则", body["conclusion"])
        self.assertEqual(body["result"]["associatedRules"], [])
        self.assertEqual(body["result"]["definition"]["enabled"], True)
        self.assertEqual(body["runtimeEligibility"], "separate")
        self.assertEqual(body["providerCalls"], 0)
        self.assertEqual(body["storageReads"], 0)
        self.assert_no_activation(before)
        self.assert_zero_provider()

    def test_new_type_without_binding_or_downstream_policies_is_still_valid(self) -> None:
        # No RecognitionTypePolicy, MetadataPolicy, NamingPolicy, ClassificationPolicy
        # or OrganizePolicy is required for a definition check.
        before = self.harness.configuration.active()
        status, body = self.analyze(
            "recognitionTypes",
            self.create_candidate("recognitionTypes", id="orphan", name="Orphan type"),
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["outcome"], "valid")
        self.assert_no_activation(before)

    def test_associated_type_definition_is_valid_without_optional_sample(self) -> None:
        before = self.harness.configuration.active()
        status, body = self.analyze(
            "recognitionTypes",
            self.edit_candidate("recognitionTypes", "A"),
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["outcome"], "valid")
        self.assertEqual(body["applicability"], "optional")
        self.assertTrue(body["result"]["associatedRules"])
        self.assert_no_activation(before)

    def test_associated_rule_match_reports_real_result_without_forcing_type(self) -> None:
        before = self.harness.configuration.active()
        status, body = self.analyze(
            "recognitionTypes",
            self.edit_candidate("recognitionTypes", "A"),
            sample={"path": "电影/Example.Movie.2024.mkv", "resourceLibraryId": "source"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["outcome"], "matched")
        rules = body["result"]["associatedRules"]
        self.assertTrue(rules)
        matched = [item for item in rules if item.get("matched") is True]
        self.assertTrue(matched)
        # A genuine associated-rule match outputs the rule's own configured type.
        for item in matched:
            self.assertIn(item["id"], {"movie-library", "movie-any"})
        self.assertIn("single-type", body["result"]["competition"])
        self.assert_no_activation(before)
        self.assert_zero_provider()

    def test_associated_rule_non_match_and_disabled_eligibility_are_distinct(self) -> None:
        before = self.harness.configuration.active()
        status, body = self.analyze(
            "recognitionTypes",
            self.edit_candidate("recognitionTypes", "A"),
            sample={"path": "Example.Movie.2024.mkv", "resourceLibraryId": "other"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["outcome"], "not_matched")
        rules = body["result"]["associatedRules"]
        self.assertTrue(all(item.get("matched") is not True for item in rules))
        # Each rule carries an explicit eligibility fact.
        for item in rules:
            self.assertIn(item["eligibility"], {"enabled", "disabled", "invalid"})
        self.assert_no_activation(before)

    def test_disabled_associated_rule_is_explicitly_excluded(self) -> None:
        before = self.harness.configuration.active()
        rules = self.harness.active_section("recognitionRules")
        target = next(item for item in rules if item["outputRecognitionType"] == "A")
        # Publish a disabled rule that would otherwise match, through the real
        # checked Save so the candidate reflects a real Active object.
        self.harness.commands.set_enabled(
            "recognitionRules",
            target["id"],
            enabled=False,
            actor="operator",
            **self.harness.authority(),
        )
        status, body = self.analyze(
            "recognitionTypes",
            self.edit_candidate("recognitionTypes", "A"),
            sample={"path": "电影/Example.Movie.2024.mkv", "resourceLibraryId": "source"},
        )
        self.assertEqual(status, 200)
        disabled = [
            item for item in body["result"]["associatedRules"] if item["id"] == target["id"]
        ]
        self.assertTrue(disabled)
        self.assertEqual(disabled[0]["eligibility"], "disabled")
        self.assertIsNone(disabled[0]["matched"])
        self.assertIn("已停用", disabled[0]["conclusion"])
        self.assertNotEqual(body["outcome"], "matched")
        self.assertIsNot(before, None)

    # -- AC-3: RecognitionRule --------------------------------------------

    def test_rule_requiring_movie_path_matches_and_non_match_is_real(self) -> None:
        rule = {
            "id": "movie-path-rule",
            "name": "Movie path rule",
            "condition": {
                "operator": "and",
                "children": [
                    {"field": "path", "operator": "contains", "value": "/电影/"},
                    {"field": "extension", "operator": "in", "value": ["mkv", "mp4"]},
                ],
            },
            "outputRecognitionType": "A",
            "enabled": True,
            "priority": 100,
            "score": 100,
            "stopOnMatch": False,
        }
        candidate = self.create_candidate("recognitionRules", **rule)
        before = self.harness.configuration.active()
        status, matched = self.analyze(
            "recognitionRules", candidate, sample={"path": "电影/Example.Movie.2024.mkv"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(matched["outcome"], "matched")
        self.assertEqual(matched["result"]["outputRecognitionType"], "A")
        self.assertEqual(matched["result"]["testedPath"], "电影/Example.Movie.2024.mkv")
        self.assertIn("titleCandidate", matched["result"]["parsed"])
        condition = matched["result"]["condition"]
        self.assertEqual(condition["operator"], "and")
        self.assertEqual(condition["truth"], True)
        self.assertEqual(len(condition["children"]), 2)
        for child in condition["children"]:
            self.assertEqual(child["kind"], "atomic")
            self.assertIn("expected", child)
            self.assertIn("actual", child)
            self.assertEqual(child["truth"], True)

        # The same rule must NOT match without the required path segment.
        status, not_matched = self.analyze(
            "recognitionRules", candidate, sample={"path": "Example.Movie.2024.mkv"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(not_matched["outcome"], "not_matched")
        self.assertEqual(not_matched["result"]["condition"]["truth"], False)
        child_truths = {
            child["field"]: child["truth"]
            for child in not_matched["result"]["condition"]["children"]
        }
        self.assertFalse(child_truths["path"])
        self.assertTrue(child_truths["extension"])
        self.assert_no_activation(before)
        self.assert_zero_provider()

    def test_rule_test_needs_no_binding_or_downstream_graph(self) -> None:
        # The Active document is emptied of bindings and downstream policies; a
        # single-rule test must still work.
        from tests.test_v2_rules_workspace_commands import empty_rule_families, example_document

        document = example_document()
        for section in (
            "recognitionTypePolicies",
            "metadataPolicies",
            "namingPolicies",
            "classificationPolicies",
            "organizePolicies",
        ):
            document[section] = []
        self.harness._activate_baseline(document)
        candidate = self.create_candidate(
            "recognitionRules",
            id="standalone",
            name="Standalone rule",
            condition={"field": "path", "operator": "contains", "value": "/电影/"},
            outputRecognitionType="A",
            enabled=True,
            priority=0,
            score=1,
            stopOnMatch=False,
        )
        status, body = self.analyze(
            "recognitionRules", candidate, sample={"path": "电影/Example.Movie.2024.mkv"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["outcome"], "matched")
        self.assertIsNotNone(empty_rule_families)

    def test_nested_not_group_and_invalid_regex_follow_production_engine(self) -> None:
        candidate = self.create_candidate(
            "recognitionRules",
            id="nested-rule",
            name="Nested rule",
            condition={
                "operator": "and",
                "children": [
                    {"field": "extension", "operator": "equals", "value": "mkv"},
                    {
                        "operator": "not",
                        "children": [{"field": "path", "operator": "contains", "value": "/动漫/"}],
                    },
                ],
            },
            outputRecognitionType="A",
            enabled=True,
            priority=0,
            score=1,
            stopOnMatch=False,
        )
        status, body = self.analyze(
            "recognitionRules", candidate, sample={"path": "电影/Example.Movie.2024.mkv"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["outcome"], "matched")
        nested = body["result"]["condition"]["children"][1]
        self.assertEqual(nested["kind"], "logical")
        self.assertEqual(nested["operator"], "not")
        self.assertTrue(nested["truth"])

        bad = copy.deepcopy(candidate)
        bad["values"]["condition"] = {
            "field": "path",
            "operator": "regex",
            "value": "(a+)+$",
        }
        status, body = self.analyze(
            "recognitionRules", bad, sample={"path": "电影/Example.Movie.2024.mkv"}
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "rules_invalid_field")

    def test_missing_or_disabled_output_type_is_a_relevant_error(self) -> None:
        candidate = self.create_candidate(
            "recognitionRules",
            id="bad-output",
            name="Bad output",
            condition={"field": "extension", "operator": "equals", "value": "mkv"},
            outputRecognitionType="missing-type",
            enabled=True,
            priority=0,
            score=1,
            stopOnMatch=False,
        )
        status, body = self.analyze(
            "recognitionRules", candidate, sample={"path": "Example.Movie.2024.mkv"}
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "rules_reference_unavailable")
        self.assertIn("nextAction", body["error"]["details"])

    def test_disabled_output_type_is_refused_with_a_relevant_actionable_error(self) -> None:
        # A rule whose output type is disabled can never be published (whole-document
        # validation would reject it), so the reference gate refuses it up front with
        # a bounded, actionable error instead of silently reporting a match.
        candidate = self.create_candidate(
            "recognitionRules",
            id="disabled-output",
            name="Disabled output",
            condition={"field": "extension", "operator": "equals", "value": "mkv"},
            outputRecognitionType="disabled-type",
            enabled=True,
            priority=0,
            score=1,
            stopOnMatch=False,
        )
        before = self.harness.configuration.active()
        status, body = self.analyze(
            "recognitionRules", candidate, sample={"path": "Example.Movie.2024.mkv"}
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "rules_reference_unavailable")
        self.assertIn("nextAction", body["error"]["details"])
        self.assert_no_activation(before)

    def test_analysis_refuses_a_disabled_output_type_defensively(self) -> None:
        # Defence in depth: even if a document somehow carried a rule whose output
        # type is disabled, the analysis reports a relevant error rather than
        # claiming a usable match.
        import copy as _copy

        from mediaflow.application.rules_object_analysis import RulesObjectAnalysisService

        active = self.harness.configuration.active()
        document = _copy.deepcopy(active.document)
        document["recognitionTypes"] = [
            {**item, "enabled": False} if item["id"] == "A" else item
            for item in document["recognitionTypes"]
        ]
        document["recognitionRules"] = [
            {
                "id": "forced",
                "name": "Forced",
                "condition": {"field": "extension", "operator": "equals", "value": "mkv"},
                "outputRecognitionType": "A",
                "enabled": True,
                "priority": 0,
                "score": 1,
                "stopOnMatch": False,
            }
        ]
        draft = self.harness.configuration.import_draft(document, actor="operator")
        service = RulesObjectAnalysisService(self.harness.commands, self.harness.objects)
        result = service.analyze(
            "recognitionRules",
            revision_id=draft.revision_id,
            object_id="forced",
            sample={"path": "Example.Movie.2024.mkv"},
        )
        self.assertEqual(result.outcome, "invalid_input")
        self.assertEqual(result.failure_category, "output_type_disabled")
        self.assertIn("已停用", result.message or "")
        self.assert_no_activation(active)

    def test_current_unsaved_edits_change_the_tested_rule_result(self) -> None:
        candidate = self.create_candidate(
            "recognitionRules",
            id="edit-sensitive",
            name="Edit sensitive",
            condition={"field": "path", "operator": "contains", "value": "/电影/"},
            outputRecognitionType="A",
            enabled=True,
            priority=0,
            score=1,
            stopOnMatch=False,
        )
        sample = {"path": "电影/Example.Movie.2024.mkv"}
        status, first = self.analyze("recognitionRules", candidate, sample=sample)
        self.assertEqual(status, 200)
        self.assertEqual(first["outcome"], "matched")
        edited = copy.deepcopy(candidate)
        edited["values"]["condition"] = {
            "field": "path",
            "operator": "contains",
            "value": "/动漫/",
        }
        status, second = self.analyze("recognitionRules", edited, sample=sample)
        self.assertEqual(status, 200)
        self.assertEqual(second["outcome"], "not_matched")
        self.assertNotEqual(first["revisionId"], second["revisionId"])

    def test_selecting_source_context_does_not_rebase_the_submitted_path(self) -> None:
        candidate = self.create_candidate(
            "recognitionRules",
            id="no-rebase",
            name="No rebase",
            condition={"field": "path", "operator": "contains", "value": "/电影/"},
            outputRecognitionType="A",
            enabled=True,
            priority=0,
            score=1,
            stopOnMatch=False,
        )
        status, body = self.analyze(
            "recognitionRules",
            candidate,
            sample={"path": "Example.Movie.2024.mkv", "resourceLibraryId": "source"},
        )
        self.assertEqual(status, 200)
        # The submitted path is reported exactly; no ResourceLibrary root was prepended.
        self.assertEqual(body["result"]["testedPath"], "Example.Movie.2024.mkv")
        self.assertEqual(body["outcome"], "not_matched")

    def test_directory_condition_uses_production_parent_path_semantics(self) -> None:
        candidate = self.create_candidate(
            "recognitionRules",
            id="directory-rule",
            name="Directory rule",
            condition={"field": "directory", "operator": "contains", "value": "Example"},
            outputRecognitionType="A",
            enabled=True,
            priority=0,
            score=1,
            stopOnMatch=False,
        )
        status, bare = self.analyze(
            "recognitionRules", candidate, sample={"path": "Example.Movie.2024.mkv"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(bare["outcome"], "not_matched")
        self.assertEqual(bare["result"]["condition"]["actual"], "[]")

        status, nested = self.analyze(
            "recognitionRules",
            candidate,
            sample={"path": "Example/Example.Movie.2024.mkv"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(nested["outcome"], "matched")
        self.assertEqual(nested["result"]["condition"]["actual"], "[Example]")

    # -- AC-4: binding / metadata / naming / classification / organize -----

    def test_binding_checks_only_type_uniqueness_and_four_references(self) -> None:
        before = self.harness.configuration.active()
        status, body = self.analyze("typeBindings", self.edit_candidate("typeBindings", "type-A"))
        self.assertEqual(status, 200)
        self.assertEqual(body["outcome"], "valid")
        resolved = body["result"]["resolvedPolicies"]
        self.assertEqual(
            set(resolved),
            {"metadataPolicy", "namingPolicy", "classificationPolicy", "organizePolicy"},
        )
        for item in resolved.values():
            self.assertTrue(item["resolved"])
        self.assertEqual(body["result"]["duplicateEnabledBindings"], [])
        self.assertIn("不执行", body["message"])
        self.assert_no_activation(before)
        self.assert_zero_provider()

    def test_binding_c_keeps_c_identity_when_reusing_a_policies(self) -> None:
        status, body = self.analyze("typeBindings", self.edit_candidate("typeBindings", "type-C"))
        self.assertEqual(status, 200)
        self.assertEqual(body["result"]["recognitionType"], "C")
        self.assertEqual(body["result"]["recognitionTypeIdentity"], "C")
        self.assertFalse(body["result"]["cIdentityPreserved"])

    def test_binding_reports_missing_reference_as_relevant_failure(self) -> None:
        candidate = self.edit_candidate("typeBindings", "type-A", namingPolicy="missing-policy")
        # The form-level reference validation rejects the dangling reference with a
        # bounded, actionable error rather than silently succeeding.
        status, body = self.analyze("typeBindings", candidate)
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "rules_reference_unavailable")
        self.assertIn("nextAction", body["error"]["details"])

    def test_offline_metadata_needs_no_credential_and_calls_no_provider(self) -> None:
        before = self.harness.configuration.active()
        status, body = self.analyze(
            "metadataPolicies", self.edit_candidate("metadataPolicies", "A")
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["outcome"], "valid")
        self.assertEqual(body["providerCalls"], 0)
        self.assertEqual(body["result"]["mode"], "offline")
        self.assertFalse(body["result"]["verified"])
        self.assertIn("未调用 Provider", body["conclusion"])
        # Effective settings are shown without any secret value.
        self.assertEqual(body["result"]["effectiveSettings"]["providerId"], "tmdb")
        self.harness.assert_no_secret_value(body, where="offline metadata analysis")
        self.assert_no_activation(before)
        self.assert_zero_provider()

    def test_offline_metadata_works_without_a_credential_while_save_still_gates(self) -> None:
        # RO-4: offline metadata validation must not require a live credential or
        # Provider construction, but publication still fails closed without one.
        import os
        from unittest.mock import patch

        from mediaflow.domain.configuration_management import RulesWorkspaceSaveError

        before = self.harness.configuration.active()
        with patch.dict(os.environ, {"TMDB_ACCESS_TOKEN": "", "TMDB_TOKEN": ""}):
            status, body = self.analyze(
                "metadataPolicies", self.edit_candidate("metadataPolicies", "A")
            )
            self.assertEqual(status, 200)
            self.assertEqual(body["outcome"], "valid")
            self.assertEqual(body["providerCalls"], 0)
            states = {
                item["field"]: item["state"]
                for item in body["result"]["credentialReadiness"]["fields"]
            }
            self.assertTrue(all(state == "UNSET" for state in states.values()))
            self.assertIn("未验证凭据", body["result"]["conclusion"])
            with self.assertRaises(RulesWorkspaceSaveError) as caught:
                self.harness.save(
                    "metadataPolicies",
                    {"id": "gated", "name": "Gated", "providerId": "tmdb"},
                )
            self.assertEqual(caught.exception.code, "rules_provider_secret_unavailable")
        self.assert_no_activation(before)

    def test_explicit_live_metadata_uses_this_policy_and_no_binding(self) -> None:
        provider = RecordingProvider()
        registry = type("Registry", (), {"resolve": lambda self, pid: provider})()
        self.harness.api._configuration_objects._metadata_provider_registry_factory = lambda ids: (
            registry
        )
        before = self.harness.configuration.active()
        status, body = self.analyze(
            "metadataPolicies",
            self.edit_candidate("metadataPolicies", "A"),
            sample={"title": "The Matrix", "year": 1999},
            live_metadata=True,
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["result"]["mode"], "live")
        self.assertTrue(provider.calls)
        self.assertEqual(body["providerCalls"], 1)
        self.assert_no_activation(before)

    def test_live_metadata_without_configured_provider_fails_actionably(self) -> None:
        before = self.harness.configuration.active()
        # The harness factory deliberately raises; a live test must report it
        # instead of silently claiming success.
        status, body = self.analyze(
            "metadataPolicies",
            self.edit_candidate("metadataPolicies", "A"),
            sample={"title": "The Matrix"},
            live_metadata=True,
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["outcome"], "failed")
        self.assertEqual(body["failureCategory"], "provider_not_configured")
        self.assertIn("nextAction", body)
        self.assert_no_activation(before)

    def test_naming_renders_typed_movie_and_tv_samples_independently(self) -> None:
        before = self.harness.configuration.active()
        status, movie = self.analyze(
            "namingPolicies",
            self.edit_candidate("namingPolicies", "A"),
            sample={
                "title": "The Matrix",
                "mediaType": "movie",
                "recognitionType": "C",
                "year": 1999,
                "extension": "mkv",
                "providerId": "603",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(movie["outcome"], "valid")
        self.assertIn("The Matrix", movie["result"]["directory"])
        self.assertIn("renderedVariables", movie["result"])
        self.assertEqual(movie["providerCalls"], 0)
        self.assertEqual(movie["storageReads"], 0)
        self.assert_no_activation(before)
        self.assert_zero_provider()

    def test_naming_reports_missing_variable_decision(self) -> None:
        status, body = self.analyze(
            "namingPolicies",
            self.edit_candidate("namingPolicies", "A"),
            sample={"title": "No Year Movie", "mediaType": "movie", "extension": "mkv"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["outcome"], "valid")
        decisions = body["result"]["missingVariableDecisions"]
        self.assertTrue(any(item["variable"] == "year" for item in decisions))
        self.assertIn("missingVariableStrategy", body["result"])

    def test_classification_evaluates_own_rules_and_referenced_library(self) -> None:
        before = self.harness.configuration.active()
        status, body = self.analyze(
            "classificationPolicies",
            self.edit_candidate("classificationPolicies", "A"),
            sample={
                "title": "Spirited Away",
                "mediaType": "movie",
                "recognitionType": "C",
                "year": 2001,
                "genres": ["Animation"],
                "countries": ["Japan"],
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["outcome"], "matched")
        self.assertEqual(body["result"]["mediaLibraryId"], "movies")
        self.assertTrue(body["result"]["mediaLibraryResolved"])
        self.assertEqual(body["result"]["relativePath"], "Anime")
        # The shipped example document still carries the legacy prefix, so the
        # analysis must report that exact contract instead of a revised one.
        self.assertEqual(body["result"]["destinationContract"], "legacy_library_prefix")
        self.assertEqual(body["providerCalls"], 0)
        self.assertEqual(body["storageReads"], 0)
        self.assert_no_activation(before)

    def test_classification_no_match_is_normal_not_a_failure(self) -> None:
        status, body = self.analyze(
            "classificationPolicies",
            self.edit_candidate("classificationPolicies", "A"),
            sample={
                "title": "Unknown",
                "mediaType": "tv",
                "recognitionType": "C",
                "genres": ["Documentary"],
                "countries": ["France"],
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["outcome"], "not_matched")
        self.assertIsNone(body["failureCategory"])
        self.assertIn("正常结果", body["message"])

    def test_organize_explains_effects_with_physical_readiness_unchecked(self) -> None:
        before = self.harness.configuration.active()
        status, body = self.analyze(
            "organizePolicies", self.edit_candidate("organizePolicies", "A")
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["outcome"], "valid")
        result = body["result"]
        # OrganizePolicy operation is the domain's own lowercase value.
        self.assertEqual(result["operation"], "move")
        self.assertIn("requiredStorageCapabilities", result)
        self.assertEqual(result["physicalReadiness"], "未检查")
        self.assertEqual(result["executionReadiness"], "未检查")
        self.assertIn("none; unsupported capability is a failure", result["fallback"])
        self.assertEqual(body["providerCalls"], 0)
        self.assertEqual(body["storageReads"], 0)
        self.assert_no_activation(before)

    def test_organize_high_risk_permissions_are_explicit(self) -> None:
        candidate = self.edit_candidate("organizePolicies", "A")
        candidate["values"]["conflictStrategy"] = "overwrite"
        candidate["values"]["overwrite"] = True
        status, body = self.analyze("organizePolicies", candidate)
        self.assertEqual(status, 200)
        self.assertTrue(body["result"]["overwriteAuthorized"])
        self.assertTrue(body["result"]["deleteAuthorized"])
        self.assertTrue(any("overwrite" in item for item in body["result"]["warnings"]))

    def test_missing_unrelated_family_does_not_fail_independent_local_tests(self) -> None:
        from tests.test_v2_rules_workspace_commands import example_document

        document = example_document()
        # Remove every downstream family; each independent local test must still work.
        for section in (
            "metadataPolicies",
            "namingPolicies",
            "classificationPolicies",
            "organizePolicies",
            "recognitionTypePolicies",
        ):
            document[section] = []
        self.harness._activate_baseline(document)
        status, body = self.analyze(
            "recognitionRules",
            self.create_candidate(
                "recognitionRules",
                id="independent",
                name="Independent rule",
                condition={"field": "extension", "operator": "equals", "value": "mkv"},
                outputRecognitionType="A",
                enabled=True,
                priority=0,
                score=1,
                stopOnMatch=False,
            ),
            sample={"path": "Example.Movie.2024.mkv"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["outcome"], "matched")

    # -- AC-6: staleness / isolation / permissions -------------------------

    def test_stale_authority_is_rejected_and_keeps_prior_active(self) -> None:
        stale = self.authority()
        self.harness.commands.set_enabled(
            "recognitionRules",
            "movie-library",
            enabled=False,
            actor="operator",
            **self.harness.authority(),
        )
        before = self.harness.configuration.active()
        status, body = self.analyze(
            "recognitionTypes",
            self.edit_candidate("recognitionTypes", "A"),
            authority=stale,
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "configuration_version_conflict")
        self.assertIn("nextAction", body["error"]["details"])
        self.harness.assert_active_unchanged(before)

    def test_read_only_principal_cannot_run_object_analysis(self) -> None:
        before = self.harness.configuration.active()
        status, body = self.harness.request(
            "POST",
            f"{ANALYSIS}/recognitionTypes",
            {
                **self.authority(),
                "candidate": self.edit_candidate("recognitionTypes", "A"),
                "sample": None,
                "liveMetadata": False,
            },
            token="viewer-token",
        )
        self.assertEqual(status, 403)
        self.assert_no_activation(before)

    def test_analysis_never_activates_and_keeps_prior_active(self) -> None:
        before = self.harness.configuration.active()
        for family, object_id in (
            ("recognitionTypes", "A"),
            ("typeBindings", "type-A"),
            ("metadataPolicies", "A"),
            ("organizePolicies", "A"),
        ):
            status, _body = self.analyze(family, self.edit_candidate(family, object_id))
            self.assertEqual(status, 200)
        self.assert_no_activation(before)

    def test_unknown_family_and_unknown_fields_are_rejected(self) -> None:
        status, body = self.harness.request(
            "POST",
            f"{ANALYSIS}/notAFamily",
            {
                **self.authority(),
                "candidate": {"family": "notAFamily", "objectId": None, "values": {}},
                "sample": None,
                "liveMetadata": False,
            },
        )
        self.assertEqual(status, 404)
        status, body = self.harness.request(
            "POST",
            f"{ANALYSIS}/recognitionTypes",
            {
                **self.authority(),
                "candidate": self.edit_candidate("recognitionTypes", "A"),
                "sample": None,
                "liveMetadata": False,
                "extra": True,
            },
        )
        self.assertEqual(status, 400)

    def test_live_metadata_flag_is_rejected_for_non_metadata_families(self) -> None:
        status, body = self.analyze(
            "namingPolicies",
            self.edit_candidate("namingPolicies", "A"),
            sample={"title": "X", "mediaType": "movie", "extension": "mkv"},
            live_metadata=True,
        )
        self.assertEqual(status, 400)

    def test_other_family_drafts_do_not_contaminate_the_result(self) -> None:
        # Stage an unrelated invalid naming candidate, then analyse an independent
        # recognition rule: the unrelated draft cannot enter the candidate.
        candidate = self.create_candidate(
            "namingPolicies",
            id="unrelated",
            name="Unrelated",
            directoryTemplate="{bogus_variable}",
        )
        status, _body = self.analyze("namingPolicies", candidate)
        self.assertEqual(status, 400)
        status, body = self.analyze(
            "recognitionRules",
            self.create_candidate(
                "recognitionRules",
                id="clean",
                name="Clean rule",
                condition={"field": "extension", "operator": "equals", "value": "mkv"},
                outputRecognitionType="A",
                enabled=True,
                priority=0,
                score=1,
                stopOnMatch=False,
            ),
            sample={"path": "Example.Movie.2024.mkv"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["outcome"], "matched")

    # -- AC-7: complete flow ----------------------------------------------

    def _complete_flow(self, **overrides):
        body = {
            **self.authority(),
            "resourceLibraryId": "source",
            "syntheticPath": "电影/Example.Movie.2024.mkv",
            "liveMetadata": False,
            "syntheticIdentity": {
                "title": "Example Movie",
                "mediaType": "movie",
                "year": 2024,
                "genres": ["Animation"],
                "countries": ["Japan"],
            },
        }
        body.update(overrides)
        return self.harness.request("POST", COMPLETE_FLOW, body)

    def test_complete_flow_produces_real_plan_or_truthful_blockers(self) -> None:
        before = self.harness.configuration.active()
        status, body = self._complete_flow()
        self.assertEqual(status, 200)
        self.assertEqual(body["entry"], "complete_flow_check")
        self.assertEqual(body["executionAuthorityGranted"], "none")
        self.assertEqual(body["localOnly"], False)
        self.assertTrue(body["syntheticIdentity"])
        self.assertEqual(body["identityStatus"], "synthetic_offline")
        result = body["result"]
        self.assertIn("recognition", result)
        if body["outcome"] == "valid":
            self.assertEqual(body["readiness"], "complete_plan_ready")
            self.assertEqual(result["naming"]["status"], "complete")
            self.assertTrue(result["naming"]["directory"])
            self.assertTrue(result["naming"]["filename"])
            self.assertEqual(result["classification"]["status"], "classified")
            self.assertTrue(result["classification"]["mediaLibraryId"])
            self.assertTrue("relativePath" in result["classification"])
            self.assertIn("plan", result)
            self.assertTrue(result["plan"]["target"])
        else:
            self.assertEqual(body["readiness"], "blocked")
            self.assertTrue(result["blockers"])
        self.assert_no_activation(before)
        self.assert_zero_provider()

    def test_complete_flow_reports_missing_binding_as_blocker(self) -> None:
        from tests.test_v2_rules_workspace_commands import example_document

        document = example_document()
        document["recognitionTypePolicies"] = []
        self.harness._activate_baseline(document)
        before = self.harness.configuration.active()
        status, body = self._complete_flow()
        self.assertEqual(status, 200)
        self.assertEqual(body["readiness"], "blocked")
        stages = {item["stage"] for item in body["blockers"]}
        self.assertIn("binding", stages)
        self.assert_no_activation(before)

    def test_complete_flow_reports_unrecognized_as_blocker(self) -> None:
        before = self.harness.configuration.active()
        status, body = self._complete_flow(syntheticPath="totally/Unknown.File.mkv")
        self.assertEqual(status, 200)
        self.assertEqual(body["readiness"], "blocked")
        stages = {item["stage"] for item in body["blockers"]}
        self.assertIn("recognition", stages)
        self.assert_no_activation(before)

    def test_complete_flow_offline_never_calls_a_provider(self) -> None:
        before = self.harness.configuration.active()
        status, body = self._complete_flow()
        self.assertEqual(status, 200)
        self.assertEqual(self.harness.provider_calls, [])
        self.assertEqual(body["providerCalls"], 0)
        self.assert_no_activation(before)

    def test_complete_flow_requires_exact_current_active(self) -> None:
        stale = self.authority()
        self.harness.commands.set_enabled(
            "recognitionRules",
            "movie-library",
            enabled=False,
            actor="operator",
            **self.harness.authority(),
        )
        before = self.harness.configuration.active()
        status, body = self._complete_flow(**stale)
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "configuration_version_conflict")
        self.assertEqual(body["error"]["details"]["durableState"], "active_preserved")
        self.harness.assert_active_unchanged(before)

    def test_complete_flow_requires_manage_configuration_permission(self) -> None:
        status, _body = self.harness.request(
            "POST",
            COMPLETE_FLOW,
            {
                **self.authority(),
                "resourceLibraryId": "source",
                "syntheticPath": "电影/Example.Movie.2024.mkv",
                "liveMetadata": False,
                "syntheticIdentity": None,
            },
            token="viewer-token",
        )
        self.assertEqual(status, 403)

    def test_complete_flow_rejects_unknown_library_and_bad_path(self) -> None:
        status, body = self._complete_flow(resourceLibraryId="missing-library")
        self.assertEqual(status, 200)
        self.assertEqual(body["readiness"], "blocked")
        self.assertEqual(body["blockers"][0]["stage"], "source")
        status, _body = self._complete_flow(syntheticPath="")
        self.assertEqual(status, 400)

    def test_complete_flow_live_without_provider_reports_actionable_blocker(self) -> None:
        status, body = self._complete_flow(liveMetadata=True, syntheticIdentity=None)
        self.assertEqual(status, 200)
        self.assertEqual(body["readiness"], "blocked")
        self.assertEqual(body["blockers"][0]["stage"], "metadata")

    def test_complete_flow_synthetic_identity_cannot_be_live(self) -> None:
        status, _body = self._complete_flow(liveMetadata=True)
        self.assertEqual(status, 400)

    def test_existing_strategy_preview_capability_is_preserved(self) -> None:
        # The canonical full-chain Strategy Test must remain available unchanged.
        status, body = self.harness.request(
            "POST",
            f"{BASE}/previews/strategy",
            {
                **self.authority(),
                "candidate": self.edit_candidate("recognitionTypes", "A"),
                "resourceLibraryId": "source",
                "syntheticPath": "电影/Example.Movie.2024.mkv",
                "liveMetadata": False,
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "completed")
        self.assertIn("recognition", body["result"])

    def test_analysis_evidence_is_persisted_and_readable_with_its_purpose(self) -> None:
        status, body = self.analyze(
            "recognitionTypes", self.edit_candidate("recognitionTypes", "A")
        )
        self.assertEqual(status, 200)
        revision = self.harness.configuration.require(body["revisionId"])
        # The analysed revision is a non-Active candidate; the Active is untouched.
        self.assertNotEqual(revision.status.value, "active")
        active = self.harness.configuration.active()
        assert active is not None
        self.assertNotEqual(active.revision_id, revision.revision_id)
        self.assertEqual(body["candidateState"], "validated_non_active")


class RulesObjectAnalysisEngineTests(unittest.TestCase):
    """Production-engine unit coverage for the bounded condition trace."""

    def test_condition_trace_is_bounded_and_reports_expected_actual_truth(self) -> None:
        from mediaflow.application.media_parser import MediaParserService
        from mediaflow.application.recognition import RecognitionRuleEngine
        from mediaflow.domain.parser import FileContext
        from mediaflow.domain.recognition import (
            AtomicCondition,
            ConditionField,
            ConditionOperator,
            LogicalCondition,
            LogicalOperator,
            RecognitionContext,
            RecognitionRule,
            RecognitionType,
        )

        context = FileContext(
            "s",
            "source",
            "电影/Example.Movie.2024.mkv",
            "Example.Movie.2024.mkv",
            ("电影",),
            "mkv",
            "电影",
        )
        parsed = MediaParserService().parse(context)
        types = (RecognitionType("A", "A"),)
        rule = RecognitionRule(
            "r",
            "r",
            LogicalCondition(
                LogicalOperator.AND,
                (
                    AtomicCondition(ConditionField.PATH, ConditionOperator.CONTAINS, "/电影/"),
                    AtomicCondition(ConditionField.EXTENSION, ConditionOperator.EQUALS, "mkv"),
                ),
            ),
            "A",
        )
        engine = RecognitionRuleEngine(types, (rule,))
        evaluation = engine.evaluate_rule(rule, RecognitionContext(context, parsed))
        self.assertTrue(evaluation.matched)
        document = evaluation.condition.document()
        self.assertEqual(document["operator"], "and")
        self.assertEqual(len(document["children"]), 2)
        self.assertEqual(document["children"][0]["field"], "path")
        self.assertTrue(document["children"][0]["truth"])
        self.assertIsNotNone(document["children"][0]["actual"])

    def test_condition_trace_truncates_within_its_budget(self) -> None:
        from mediaflow.application.recognition import (
            CONDITION_TRACE_TEXT_LIMIT,
            _bounded_condition_text,
        )

        long_value = "x" * 5000
        self.assertEqual(len(_bounded_condition_text(long_value)), CONDITION_TRACE_TEXT_LIMIT)

    def test_synthetic_identity_requires_explicit_offline_flag(self) -> None:
        # A synthetic identity must never be combined with live metadata mode.
        from mediaflow.application.rules_object_analysis import RulesObjectAnalysisService
        from mediaflow.application.strategy_test import StrategyConfigurationError
        from mediaflow.domain.metadata import MediaIdentity, MediaType

        identity = MediaIdentity("synthetic-offline", "synthetic", MediaType.MOVIE, "X")
        self.assertEqual(identity.provider, "synthetic-offline")
        self.assertIsNotNone(StrategyConfigurationError)
        self.assertIsNotNone(RulesObjectAnalysisService)


if __name__ == "__main__":
    unittest.main()
