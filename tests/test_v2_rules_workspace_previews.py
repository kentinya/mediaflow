"""Focused Task 41.4 API coverage for exact-revision V2 previews."""

from __future__ import annotations

import unittest

from tests.test_v2_rules_workspace_commands import RulesWorkspaceCommandTests


class RulesWorkspacePreviewApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = RulesWorkspaceCommandTests()
        self.harness.setUp()

    def tearDown(self) -> None:
        self.harness.tearDown()

    def authority(self) -> dict[str, object]:
        active = self.harness.configuration.active()
        assert active is not None
        return {
            "expectedRevisionId": active.revision_id,
            "expectedVersion": active.revision_sequence or active.version,
            "expectedDigest": active.digest,
        }

    def candidate(self, family: str, object_id: str) -> dict[str, object]:
        projection = self.harness.commands.edit_projection(family, object_id)
        return {"family": family, "objectId": object_id, "values": projection["object"]}

    def test_naming_preview_is_exact_revision_bound_and_zero_mutation(self) -> None:
        before_active = self.harness.configuration.active()
        assert before_active is not None
        status, body = self.harness.request(
            "POST",
            "/api/v1/operations/rules/previews/naming",
            {
                **self.authority(),
                "candidate": self.candidate("namingPolicies", "A"),
                "policySelection": {"mode": "direct", "policyId": "A"},
                "sample": {
                    "title": "The Matrix",
                    "mediaType": "movie",
                    "recognitionType": "C",
                    "year": 1999,
                    "extension": "mkv",
                },
            },
        )
        self.assertEqual(status, 200)
        self.assertNotEqual(body["revisionId"], before_active.revision_id)
        self.assertEqual(body["status"], "completed")
        after_active = self.harness.configuration.active()
        assert after_active is not None
        self.assertEqual(after_active.revision_id, before_active.revision_id)
        self.assertEqual(self.harness.config_repo.activations, self.harness.activations_at_baseline)

    def test_preview_rejects_stale_identity_and_unknown_fields(self) -> None:
        authority = self.authority()
        candidate = self.candidate("organizePolicies", "A")
        status, body = self.harness.request(
            "POST",
            "/api/v1/operations/rules/previews/organize",
            {
                **authority,
                "candidate": candidate,
                "recognitionType": "A",
                "resourceLibraryId": "source",
                "syntheticPath": "The Matrix (1999).mkv",
                "sample": {
                    "title": "The Matrix",
                    "mediaType": "movie",
                    "recognitionType": "A",
                    "year": 1999,
                    "extension": "mkv",
                },
                "unexpected": True,
            },
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_request")
        stale = {
            **authority,
            "expectedDigest": "0" * 64,
            "candidate": candidate,
            "recognitionType": "A",
            "resourceLibraryId": "source",
            "syntheticPath": "The Matrix (1999).mkv",
            "sample": {
                "title": "The Matrix",
                "mediaType": "movie",
                "recognitionType": "A",
                "year": 1999,
                "extension": "mkv",
            },
        }
        status, body = self.harness.request(
            "POST", "/api/v1/operations/rules/previews/organize", stale
        )
        self.assertEqual(status, 409)
        self.assertIn("stale", body["error"]["message"].lower())

    def test_strategy_uses_distinct_source_library_and_exact_edited_candidate(self) -> None:
        candidate = self.candidate("recognitionTypes", "C")
        candidate["values"] = {**candidate["values"], "name": "Candidate C"}
        status, body = self.harness.request(
            "POST",
            "/api/v1/operations/rules/previews/strategy",
            {
                **self.authority(),
                "candidate": candidate,
                "resourceLibraryId": "source",
                "syntheticPath": "The Matrix (1999).mkv",
                "liveMetadata": False,
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "completed")
        staged = self.harness.configuration.require(body["revisionId"])
        names = {item["id"]: item["name"] for item in staged.document["recognitionTypes"]}
        self.assertEqual(names["C"], "Candidate C")
        self.assertEqual(body["result"]["source"]["resourceLibraryId"], "source")

    def test_invalid_create_candidate_is_actionable_and_does_not_activate(self) -> None:
        before = self.harness.configuration.active()
        assert before is not None
        status, body = self.harness.request(
            "POST",
            "/api/v1/operations/rules/previews/naming",
            {
                **self.authority(),
                "candidate": {
                    "family": "namingPolicies",
                    "objectId": None,
                    "values": {
                        "id": "new-policy",
                        "name": "Invalid candidate",
                        "directoryTemplate": "{unknown_variable}",
                    },
                },
                "policySelection": {"mode": "direct", "policyId": "new-policy"},
                "sample": {"title": "Example", "mediaType": "movie", "extension": "mkv"},
            },
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "rules_invalid_field")
        self.assertIn("nextAction", body["error"]["details"])
        after = self.harness.configuration.active()
        assert after is not None
        self.assertEqual(after.revision_id, before.revision_id)

    def test_valid_create_candidate_can_be_previewed_without_activation(self) -> None:
        values = self.candidate("namingPolicies", "A")["values"]
        candidate_values = {**values, "id": "candidate-name", "name": "Candidate Name"}
        status, body = self.harness.request(
            "POST",
            "/api/v1/operations/rules/previews/naming",
            {
                **self.authority(),
                "candidate": {
                    "family": "namingPolicies",
                    "objectId": None,
                    "values": candidate_values,
                },
                "policySelection": {"mode": "direct", "policyId": "candidate-name"},
                "sample": {
                    "title": "The Matrix",
                    "mediaType": "movie",
                    "year": 1999,
                    "extension": "mkv",
                },
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["candidateState"], "validated_non_active")
        active = self.harness.configuration.active()
        assert active is not None
        self.assertNotEqual(active.revision_id, body["revisionId"])

    def test_matching_metadata_policy_offline_succeeds_and_mismatch_is_rejected(self) -> None:
        request = {
            **self.authority(),
            "candidate": self.candidate("metadataPolicies", "C"),
            "policyId": "C",
            "resourceLibraryId": "source",
            "syntheticPath": "/C/Special.C.2025.mkv",
            "liveMetadata": False,
        }
        status, body = self.harness.request(
            "POST", "/api/v1/operations/rules/previews/metadata", request
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["result"]["effectiveMetadataPolicy"]["id"], "C")
        self.assertEqual(self.harness.provider_calls, [])

        mismatch = {
            **self.authority(),
            "candidate": self.candidate("metadataPolicies", "C"),
            "policyId": "A",
            "resourceLibraryId": "source",
            "syntheticPath": "/C/Special.C.2025.mkv",
            "liveMetadata": False,
        }
        status, body = self.harness.request(
            "POST", "/api/v1/operations/rules/previews/metadata", mismatch
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "configuration_version_conflict")

    def test_type_c_bound_previews_use_policy_a_without_changing_type(self) -> None:
        sample = {
            "title": "Special C",
            "mediaType": "movie",
            "recognitionType": "C",
            "year": 2025,
            "extension": "mkv",
        }
        for kind, result_key in (
            ("naming", "appliedPolicyId"),
            ("classification", "appliedPolicyId"),
        ):
            kind_sample = (
                sample
                if kind == "naming"
                else {key: value for key, value in sample.items() if key != "extension"}
            )
            status, body = self.harness.request(
                "POST",
                f"/api/v1/operations/rules/previews/{kind}",
                {
                    **self.authority(),
                    "candidate": self.candidate("recognitionTypes", "C"),
                    "policySelection": {
                        "mode": "binding",
                        "recognitionType": "C",
                    },
                    "sample": kind_sample,
                },
            )
            self.assertEqual(status, 200, kind)
            self.assertEqual(body["status"], "completed", kind)
            self.assertEqual(body["result"][result_key], "A", kind)
            self.assertEqual(body["result"]["recognitionType"], "C", kind)

    def test_bound_previews_reject_path_and_mismatched_typed_identity(self) -> None:
        for kind in ("naming", "classification"):
            candidate = self.candidate("recognitionTypes", "C")
            base = {
                **self.authority(),
                "candidate": candidate,
                "policySelection": {
                    "mode": "binding",
                    "recognitionType": "C",
                },
            }
            status, body = self.harness.request(
                "POST",
                f"/api/v1/operations/rules/previews/{kind}",
                {**base, "sample": {"path": "/C/Special.C.2025.mkv"}},
            )
            self.assertEqual(status, 400, kind)
            self.assertEqual(body["error"]["code"], "invalid_request", kind)

            sample = {
                "title": "Special C",
                "mediaType": "movie",
                "recognitionType": "B",
                "year": 2025,
            }
            if kind == "naming":
                sample["extension"] = "mkv"
            status, body = self.harness.request(
                "POST",
                f"/api/v1/operations/rules/previews/{kind}",
                {**base, "sample": sample},
            )
            self.assertEqual(status, 400, kind)
            self.assertEqual(body["error"]["code"], "invalid_request", kind)

    def test_organize_explanation_composes_destination_verdict_without_authority(self) -> None:
        status, body = self.harness.request(
            "POST",
            "/api/v1/operations/rules/previews/organize",
            {
                **self.authority(),
                "candidate": self.candidate("organizePolicies", "A"),
                "recognitionType": "C",
                "resourceLibraryId": "source",
                "syntheticPath": "The Matrix (1999).mkv",
                "sample": {
                    "title": "The Matrix",
                    "mediaType": "movie",
                    "recognitionType": "C",
                    "year": 1999,
                    "extension": "mkv",
                },
            },
        )
        self.assertEqual(status, 200)
        result = body["result"]
        self.assertEqual(result["source"]["resourceLibraryId"], "source")
        self.assertIn("destination", result)
        self.assertIn("executionAllowed", result)
        self.assertEqual(result["executionAuthorityGranted"], "none")
        self.assertTrue(result["allowBlockReasons"])


if __name__ == "__main__":
    unittest.main()
