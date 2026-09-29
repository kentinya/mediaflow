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

    def test_naming_preview_is_exact_revision_bound_and_zero_mutation(self) -> None:
        draft = self.harness.configuration.import_draft(
            self.harness.baseline_document, actor="operator"
        )
        validated = self.harness.configuration.validate(draft.revision_id, actor="operator")
        before = (validated.revision_id, validated.version, validated.digest)
        authority = {
            "expectedRevisionId": validated.revision_id,
            "expectedVersion": validated.version,
            "expectedDigest": validated.digest,
        }
        status, body = self.harness.request(
            "POST",
            "/api/v1/operations/rules/previews/naming",
            {
                **authority,
                "policyId": "A",
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
        self.assertEqual(body["revisionId"], validated.revision_id)
        self.assertEqual(body["revisionVersion"], validated.version)
        self.assertEqual(body["status"], "completed")
        self.assertEqual(
            (
                self.harness.configuration.require(validated.revision_id).revision_id,
                self.harness.configuration.require(validated.revision_id).version,
                self.harness.configuration.require(validated.revision_id).digest,
            ),
            before,
        )

    def test_preview_rejects_stale_identity_and_unknown_fields(self) -> None:
        draft = self.harness.configuration.import_draft(
            self.harness.baseline_document, actor="operator"
        )
        validated = self.harness.configuration.validate(draft.revision_id, actor="operator")
        authority = {
            "expectedRevisionId": validated.revision_id,
            "expectedVersion": validated.version,
            "expectedDigest": validated.digest,
        }
        status, body = self.harness.request(
            "POST",
            "/api/v1/operations/rules/previews/organize",
            {**authority, "recognitionType": "A", "unexpected": True},
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_request")
        stale = {**authority, "expectedDigest": "0" * 64, "recognitionType": "A"}
        status, body = self.harness.request(
            "POST", "/api/v1/operations/rules/previews/organize", stale
        )
        self.assertEqual(status, 409)
        self.assertIn("exact current revision", body["error"]["message"].lower())


if __name__ == "__main__":
    unittest.main()
