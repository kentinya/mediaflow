from collections.abc import Iterable, Mapping

from mediaflow.domain.recognition import (
    PolicyReference,
    PolicyResolutionError,
    PolicyResolutionErrorCode,
    RecognitionType,
    RecognitionTypePolicy,
    ResolvedRecognitionPolicy,
)


class RecognitionTypePolicyResolver:
    def __init__(
        self,
        policies: Iterable[RecognitionTypePolicy],
        *,
        metadata_policies: Mapping[str, PolicyReference] | None = None,
        naming_policies: Mapping[str, PolicyReference] | None = None,
        classification_policies: Mapping[str, PolicyReference] | None = None,
        organize_policies: Mapping[str, PolicyReference] | None = None,
    ) -> None:
        self._policies: dict[str, RecognitionTypePolicy] = {}
        for policy in policies:
            if not policy.enabled:
                continue
            type_id = policy.recognition_type_id
            if type_id in self._policies:
                raise PolicyResolutionError(
                    PolicyResolutionErrorCode.DUPLICATE_TYPE_POLICY,
                    f"multiple enabled policies for recognition type {type_id!r}",
                )
            self._policies[type_id] = policy
        self._catalogs = {
            "metadata": metadata_policies,
            "naming": naming_policies,
            "classification": classification_policies,
            "organize": organize_policies,
        }

    def resolve(self, recognition_type: RecognitionType | str) -> ResolvedRecognitionPolicy:
        type_id = (
            recognition_type.type_id
            if isinstance(recognition_type, RecognitionType)
            else recognition_type
        )
        try:
            policy = self._policies[type_id]
        except KeyError as error:
            raise PolicyResolutionError(
                PolicyResolutionErrorCode.MISSING_TYPE_POLICY,
                f"no enabled policy for recognition type {type_id!r}",
            ) from error
        if not policy.recognition_type.enabled:
            raise PolicyResolutionError(
                PolicyResolutionErrorCode.RECOGNITION_TYPE_DISABLED,
                f"recognition type {type_id!r} is disabled",
            )
        references = {
            "metadata": policy.metadata_policy_id,
            "naming": policy.naming_policy_id,
            "classification": policy.classification_policy_id,
            "organize": policy.organize_policy_id,
        }
        for kind, reference_id in references.items():
            catalog = self._catalogs[kind]
            if catalog is None:
                continue
            reference = catalog.get(reference_id)
            if reference is None:
                raise PolicyResolutionError(
                    PolicyResolutionErrorCode.INVALID_POLICY_REFERENCE,
                    f"{kind} policy {reference_id!r} does not exist",
                )
            if not reference.enabled:
                raise PolicyResolutionError(
                    PolicyResolutionErrorCode.POLICY_DISABLED,
                    f"{kind} policy {reference_id!r} is disabled",
                )
        return ResolvedRecognitionPolicy(
            recognition_type=policy.recognition_type,
            metadata_policy_id=policy.metadata_policy_id,
            naming_policy_id=policy.naming_policy_id,
            classification_policy_id=policy.classification_policy_id,
            organize_policy_id=policy.organize_policy_id,
            type_policy_id=policy.policy_id,
        )


class RecognitionTypePolicyRegistry(RecognitionTypePolicyResolver):
    """Backward-compatible bootstrap name for the Phase 7 resolver."""

    def resolve(self, recognition_type: RecognitionType) -> RecognitionTypePolicy:
        super().resolve(recognition_type)
        return self._policies[recognition_type.type_id]
