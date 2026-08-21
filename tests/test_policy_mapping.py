import unittest

from mediaflow.application.policies import RecognitionTypePolicyRegistry
from mediaflow.domain.organizer import OrganizeOperationType, OrganizePolicy
from mediaflow.domain.recognition import RecognitionType, RecognitionTypePolicy


class PolicyMappingTest(unittest.TestCase):
    def test_a_b_and_c_policy_matrix_preserves_each_recognition_type(self) -> None:
        type_a = RecognitionType("A", "A")
        type_b = RecognitionType("B", "B")
        type_c = RecognitionType("C", "C")
        registry = RecognitionTypePolicyRegistry(
            [
                self._policy(type_a, "A", "A", "A"),
                self._policy(type_b, "B", "B", "B"),
                self._policy(type_c, "C", "A", "A"),
            ]
        )

        resolved_a = registry.resolve(type_a)
        resolved_b = registry.resolve(type_b)
        resolved = registry.resolve(type_c)

        self.assertEqual(("A", "metadata-A", "naming-A", "classification-A"), self._ids(resolved_a))
        self.assertEqual(("B", "metadata-B", "naming-B", "classification-B"), self._ids(resolved_b))
        self.assertEqual("C", resolved.recognition_type.type_id)
        self.assertEqual("metadata-C", resolved.metadata_policy_id)
        self.assertEqual("naming-A", resolved.naming_policy_id)
        self.assertEqual("classification-A", resolved.classification_policy_id)

    def test_missing_mapping_fails_explicitly(self) -> None:
        with self.assertRaises(LookupError):
            RecognitionTypePolicyRegistry([]).resolve(RecognitionType("C", "C"))

    @staticmethod
    def _policy(
        recognition_type: RecognitionType,
        metadata: str,
        naming: str,
        classification: str,
    ) -> RecognitionTypePolicy:
        return RecognitionTypePolicy(
            f"type-{recognition_type.type_id}",
            recognition_type,
            f"metadata-{metadata}",
            f"naming-{naming}",
            f"classification-{classification}",
            OrganizePolicy("move", OrganizeOperationType.MOVE),
        )

    @staticmethod
    def _ids(policy: RecognitionTypePolicy) -> tuple[str, str, str, str]:
        return (
            policy.recognition_type.type_id,
            policy.metadata_policy_id,
            policy.naming_policy_id,
            policy.classification_policy_id,
        )
