from __future__ import annotations

import unittest
from datetime import UTC, datetime

from mediaflow.domain.configuration_management import (
    ConfigurationChangeAudit,
    ConfigurationObjectKind,
    ConfigurationReferencePolicy,
)


class ConfigurationManagementTests(unittest.TestCase):
    def test_required_object_kinds_are_present(self) -> None:
        expected = {
            "storage",
            "resource_library",
            "media_library",
            "metadata_provider",
            "metadata_policy",
            "recognition_rule",
            "recognition_type",
            "recognition_type_policy",
            "naming_policy",
            "classification_policy",
            "organize_policy",
            "schedule",
            "system_settings",
        }
        self.assertEqual({item.value for item in ConfigurationObjectKind}, expected)

    def test_reference_policy_rejects_destructive_delete(self) -> None:
        policy = ConfigurationReferencePolicy(ConfigurationObjectKind.NAMING_POLICY)
        self.assertTrue(policy.can_delete(0))
        self.assertFalse(policy.can_delete(1))
        blocking = ConfigurationReferencePolicy(
            ConfigurationObjectKind.NAMING_POLICY,
            block_on_reference=False,
        )
        self.assertTrue(blocking.can_delete(1))

    def test_audit_redacts_secret_like_fields(self) -> None:
        audit = ConfigurationChangeAudit(
            "audit-1",
            ConfigurationObjectKind.STORAGE,
            "source",
            "update",
            {"type": "smb", "password": "secret"},
            {"type": "smb", "password": "secret"},
            datetime.now(UTC),
            "operator",
        )
        self.assertEqual(audit.safe_before()["password"], "***REDACTED***")
        self.assertEqual(audit.safe_after()["password"], "***REDACTED***")


if __name__ == "__main__":
    unittest.main()
