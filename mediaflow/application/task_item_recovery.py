"""Task-scoped review decisions and explicit Metadata search for Operations.

This service composes the persisted review/checkpoint records already owned by
the processing pipeline. Reads never contact a Provider. Provider search is a
separate explicit command and uses the Task's saved configuration pin.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from mediaflow.application.classification_review import ClassificationReviewService
from mediaflow.application.conflict_resolution import ConfirmationService
from mediaflow.application.metadata_correction import MetadataCorrectionService
from mediaflow.application.metadata_review import MetadataReviewService
from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.application.recognition_review import RecognitionReviewService
from mediaflow.domain.metadata import MediaQueryType, MediaType
from mediaflow.domain.organizer import ConflictStrategy
from mediaflow.domain.parser import ParseResult


class TaskItemRecoveryError(ValueError):
    """Bounded, secret-free refusal for one task-item recovery command."""

    def __init__(self, code: str, message: str, *, status: int = 409, next_action: str) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.next_action = next_action


class TaskItemRecoveryService:
    MAX_QUERY = 500
    MAX_CANDIDATES = 100

    def __init__(
        self,
        repository,
        *,
        checkpoint_service: ProcessingCheckpointService,
        configuration_service=None,
        metadata_provider_registry_factory=None,
    ) -> None:
        self._repository = repository
        self._checkpoints = checkpoint_service
        self._configuration_service = configuration_service
        self._provider_factory = metadata_provider_registry_factory

    def detail(self, task_id: str, item_id: str) -> dict[str, object]:
        checkpoint = self._checkpoint(task_id, item_id)
        blocker = checkpoint.blocker
        decision: dict[str, object] | None = None
        if blocker is not None:
            decision = self._linked_decision(task_id, item_id, blocker.kind, blocker.blocker_id)
        return {
            "task_id": task_id,
            "item_id": item_id,
            "checkpoint": checkpoint.document(),
            "decision": decision,
            "sideEffects": "none",
            "next_action": checkpoint.refusal_reason
            or (
                checkpoint.actions[0].label
                if checkpoint.actions
                else "inspect the saved item evidence"
            ),
        }

    def metadata_search(
        self,
        task_id: str,
        item_id: str,
        *,
        expected_checkpoint_version: str,
        query: str,
        media_type: str,
    ) -> dict[str, object]:
        checkpoint = self._require_checkpoint_version(task_id, item_id, expected_checkpoint_version)
        blocker = checkpoint.blocker
        if blocker is None or blocker.kind != "metadata_correction":
            raise TaskItemRecoveryError(
                "decision_changed",
                "this item no longer has a pending Metadata correction",
                next_action="refresh the item and follow its current recovery action",
            )
        review = self._repository.get_metadata_correction(blocker.blocker_id)
        if not self._owns_review(review, task_id, item_id, blocker.blocker_id):
            raise TaskItemRecoveryError(
                "decision_unavailable",
                "the saved Metadata correction is no longer available for this item",
                next_action="refresh the item evidence and inspect its current blocker",
            )
        runtime = self._pinned_runtime(task_id)
        policy = next(
            (
                value
                for value in runtime.strategy.metadata_policies
                if value.policy_id == review.metadata_policy_id
                and value.enabled
                and value.provider_id == review.provider_id
            ),
            None,
        )
        if policy is None:
            raise TaskItemRecoveryError(
                "metadata_policy_unavailable",
                "the MetadataPolicy saved by this Task is unavailable",
                status=503,
                next_action="restore the Task's published configuration pin, then refresh",
            )
        normalized_query = " ".join(query.split()) if isinstance(query, str) else ""
        if not normalized_query or len(normalized_query) > self.MAX_QUERY:
            raise TaskItemRecoveryError(
                "invalid_search",
                "enter a title of at most 500 characters",
                status=400,
                next_action="correct the title and run Metadata search again",
            )
        try:
            selected_type = MediaType(media_type)
        except (TypeError, ValueError):
            raise TaskItemRecoveryError(
                "invalid_media_type",
                "choose Movie or TV for this Metadata search",
                status=400,
                next_action="select a supported media type and search again",
            ) from None
        if policy.media_query_type is MediaQueryType.MOVIE and selected_type is not MediaType.MOVIE:
            raise TaskItemRecoveryError(
                "media_type_not_permitted",
                "the Task's MetadataPolicy supports Movie search only",
                status=409,
                next_action="use Movie search or repair the MetadataPolicy in Settings",
            )
        if policy.media_query_type is MediaQueryType.TV and selected_type is not MediaType.TV:
            raise TaskItemRecoveryError(
                "media_type_not_permitted",
                "the Task's MetadataPolicy supports TV search only",
                status=409,
                next_action="use TV search or repair the MetadataPolicy in Settings",
            )
        if policy.media_query_type is MediaQueryType.NONE:
            raise TaskItemRecoveryError(
                "metadata_lookup_disabled",
                "the Task's MetadataPolicy does not permit Metadata lookup",
                status=409,
                next_action="repair the MetadataPolicy in Rules, then return and refresh",
            )
        if self._provider_factory is None:
            raise TaskItemRecoveryError(
                "provider_unavailable",
                "the configured Metadata Provider is unavailable",
                status=503,
                next_action="check the Provider configuration in Settings, then return and refresh",
            )
        try:
            providers = self._provider_factory((policy.provider_id,))
            provider = providers.resolve(policy.provider_id)
            parsed = ParseResult(
                title_candidate=normalized_query,
                year=review.original_year,
                original_filename=PurePosixPath(review.source_path).name,
                normalized_filename=PurePosixPath(review.source_path).name,
            )
            candidates = (
                provider.search_movie(parsed, policy)
                if selected_type is MediaType.MOVIE
                else provider.search_tv(parsed, policy)
            )
        except Exception as error:
            # Provider exceptions can contain URLs, request details or other
            # deployment data. The operator gets a useful bounded action only.
            raise TaskItemRecoveryError(
                "provider_search_failed",
                "Metadata search did not complete",
                status=503,
                next_action="check the configured Provider, then explicitly search again",
            ) from error
        bounded = tuple(candidates[: min(policy.max_candidates, self.MAX_CANDIDATES)])
        return {
            "task_id": task_id,
            "item_id": item_id,
            "checkpoint_version": checkpoint.checkpoint_version,
            "provider": policy.provider_id,
            "media_type": selected_type.value,
            "query": normalized_query,
            "candidates": [
                {
                    "rank": rank,
                    "provider_id": value.provider_id[:200],
                    "media_type": value.media_type.value,
                    "title": value.title[:500],
                    "original_title": (
                        value.original_title[:500] if value.original_title is not None else None
                    ),
                    "year": value.canonical_year,
                    "release_date": value.canonical_release_date,
                    "original_language": value.original_language,
                }
                for rank, value in enumerate(bounded, 1)
            ],
            "truncated": len(candidates) > len(bounded),
            "sideEffects": "none",
            "next_action": "select a candidate or correct the search text before saving",
        }

    def resolve(
        self,
        task_id: str,
        item_id: str,
        *,
        kind: str,
        expected_checkpoint_version: str,
        actor: str,
        decision: dict[str, object],
    ) -> object:
        checkpoint = self._require_checkpoint_version(task_id, item_id, expected_checkpoint_version)
        blocker = checkpoint.blocker
        action_id = f"resolve_{kind}"
        if (
            blocker is None
            or blocker.kind != kind
            or action_id not in checkpoint.permitted_action_ids
        ):
            raise TaskItemRecoveryError(
                "decision_changed",
                "the selected decision is no longer permitted for this item",
                next_action="refresh the item and submit a decision for its current blocker",
            )
        self._linked_record(task_id, item_id, kind, blocker.blocker_id)
        runtime = self._pinned_runtime(task_id)
        note = decision.get("note")
        if note is not None and (not isinstance(note, str) or len(note) > 500):
            raise TaskItemRecoveryError(
                "invalid_decision",
                "the optional decision note must be at most 500 characters",
                status=400,
                next_action="shorten the note and submit the decision again",
            )
        try:
            if kind == "recognition":
                recognition_type_id = decision.get("recognition_type_id")
                if not isinstance(recognition_type_id, str):
                    raise ValueError("select a RecognitionType from the saved choices")
                result = RecognitionReviewService(
                    self._repository, runtime.strategy.recognition_types
                ).resolve(
                    blocker.blocker_id,
                    recognition_type_id,
                    actor=actor,
                    note=note,
                )
            elif kind == "metadata":
                rank = decision.get("candidate_rank")
                if isinstance(rank, bool) or not isinstance(rank, int):
                    raise ValueError("select a Metadata candidate from the saved choices")
                result = MetadataReviewService(self._repository).resolve(
                    blocker.blocker_id, rank, actor=actor, note=note
                )
            elif kind == "metadata_correction":
                query = decision.get("query")
                year = decision.get("year")
                media_type = decision.get("media_type")
                provider_id = decision.get("provider_id")
                if not isinstance(query, str) or not isinstance(media_type, str):
                    raise ValueError("corrected title and media type are required")
                if year is not None and (isinstance(year, bool) or not isinstance(year, int)):
                    raise ValueError("corrected year must be an integer")
                if provider_id is not None and not isinstance(provider_id, str):
                    raise ValueError("selected provider ID is invalid")
                result = MetadataCorrectionService(
                    self._repository, runtime.strategy.metadata_policies
                ).resolve(
                    blocker.blocker_id,
                    query=query,
                    year=year,
                    media_type=media_type,
                    provider_id=provider_id,
                    actor=actor,
                    note=note,
                )
            elif kind == "classification":
                rank = decision.get("choice_rank")
                if isinstance(rank, bool) or not isinstance(rank, int):
                    raise ValueError("select a Classification choice from the saved choices")
                result = ClassificationReviewService(self._repository).resolve(
                    blocker.blocker_id, rank, actor=actor, note=note
                )
            elif kind == "conflict":
                raw_strategy = decision.get("strategy")
                try:
                    strategy = ConflictStrategy(raw_strategy)
                except (TypeError, ValueError):
                    raise ValueError("choose a supported conflict strategy") from None
                if strategy is ConflictStrategy.MANUAL:
                    raise ValueError("choose Skip, Rename or an explicitly permitted Overwrite")
                confirm_overwrite = decision.get("confirm_overwrite", False)
                if not isinstance(confirm_overwrite, bool):
                    raise ValueError("overwrite confirmation is invalid")
                result = ConfirmationService(self._repository).resolve(
                    blocker.blocker_id,
                    strategy,
                    confirm_overwrite=confirm_overwrite,
                    actor=actor,
                    note=note,
                )
            else:
                raise ValueError("this review type is not supported in Operations")
        except TaskItemRecoveryError:
            raise
        except Exception as error:
            # Application errors are intentionally mapped to bounded operator
            # copy at the API boundary; never echo provider/path internals.
            raise TaskItemRecoveryError(
                "decision_rejected",
                "the decision was not saved",
                status=409,
                next_action="refresh the item, review its current legal choices, and submit again",
            ) from error
        return result

    def _checkpoint(self, task_id: str, item_id: str):
        try:
            return self._checkpoints.get(item_id, task_id=task_id)
        except LookupError:
            raise LookupError("TaskItem was not found in the specified Task") from None

    def _require_checkpoint_version(self, task_id: str, item_id: str, expected: str):
        checkpoint = self._checkpoint(task_id, item_id)
        if not isinstance(expected, str) or expected != checkpoint.checkpoint_version:
            raise TaskItemRecoveryError(
                "stale_checkpoint",
                "the item changed after it was opened",
                status=409,
                next_action=(
                    "refresh the item, review its current evidence, and submit again deliberately"
                ),
            )
        return checkpoint

    def _linked_decision(
        self, task_id: str, item_id: str, kind: str, blocker_id: str
    ) -> dict[str, object] | None:
        value = self._linked_record(task_id, item_id, kind, blocker_id)
        if value is None:
            return None
        document = {
            "kind": kind,
            "review_id": getattr(value, "review_id", getattr(value, "confirmation_id", None)),
            "status": getattr(value, "status", None),
        }
        if kind == "recognition":
            document["choices"] = [
                {
                    "recognition_type_id": choice.recognition_type_id,
                    "name": choice.name,
                    "description": choice.description,
                }
                for choice in self._repository.list_recognition_review_choices(blocker_id)[:100]
            ]
        elif kind == "metadata":
            document["query"] = value.query
            document["outcome"] = value.outcome
            document["candidates"] = [
                {
                    "rank": candidate.rank,
                    "provider": candidate.provider,
                    "provider_id": candidate.provider_id,
                    "media_type": candidate.media_type,
                    "title": candidate.title,
                    "original_title": candidate.original_title,
                    "canonical_year": candidate.canonical_year,
                    "total_score": candidate.total_score,
                    "matched_provider_title": candidate.matched_provider_title,
                    "matched_title_source": candidate.matched_title_source,
                    "score_components": [
                        {"name": item.name, "score": item.score, "reason": item.reason}
                        for item in candidate.score_components[:8]
                    ],
                }
                for candidate in self._repository.list_metadata_review_candidates(blocker_id)[:100]
            ]
        elif kind == "metadata_correction":
            document.update(
                {
                    "provider_id": value.provider_id,
                    "metadata_policy_id": value.metadata_policy_id,
                    "query": value.original_query,
                    "year": value.original_year,
                    "media_type": value.original_media_type,
                    "can_search": True,
                }
            )
        elif kind == "classification":
            document["choices"] = [
                {
                    "rank": choice.rank,
                    "rule_id": choice.rule_id,
                    "name": choice.name,
                    "media_library_id": choice.media_library_id,
                    "relative_path": choice.relative_path,
                    "description": choice.description,
                    "priority": choice.priority,
                }
                for choice in self._repository.list_classification_review_choices(blocker_id)[:100]
            ]
        elif kind == "conflict":
            document.update(
                {
                    "configured_strategy": value.configured_strategy,
                    "conflict_types": value.conflict_types,
                    "source_path": value.source_path,
                    "target_path": value.target_path,
                    "allowed_strategies": ["skip", "rename"]
                    + (["overwrite"] if value.configured_strategy == "overwrite" else []),
                }
            )
        return document

    def _linked_record(self, task_id: str, item_id: str, kind: str, blocker_id: str):
        if kind == "recognition":
            value = self._repository.get_recognition_review(blocker_id)
        elif kind == "metadata":
            value = self._repository.get_metadata_review(blocker_id)
        elif kind == "metadata_correction":
            value = self._repository.get_metadata_correction(blocker_id)
        elif kind == "classification":
            value = self._repository.get_classification_review(blocker_id)
        elif kind == "conflict":
            value = self._repository.get_confirmation(blocker_id)
        else:
            return None
        if not self._owns_review(value, task_id, item_id, blocker_id):
            raise TaskItemRecoveryError(
                "decision_link_mismatch",
                "the saved decision no longer belongs to this item",
                next_action="refresh the item evidence and inspect its current blocker",
            )
        return value

    @staticmethod
    def _owns_review(value, task_id: str, item_id: str, review_id: str) -> bool:
        if value is None:
            return False
        identifier = getattr(value, "review_id", getattr(value, "confirmation_id", None))
        return (
            identifier == review_id
            and getattr(value, "task_id", None) == task_id
            and getattr(value, "item_id", None) == item_id
            and getattr(getattr(value, "status", None), "value", getattr(value, "status", None))
            == "pending"
        )

    def _pinned_runtime(self, task_id: str):
        task = self._repository.get_task(task_id)
        if task is None:
            raise LookupError("Task was not found")
        snapshot_id = task.configuration_snapshot_id
        digest = task.configuration_snapshot_digest
        if not snapshot_id or not digest or self._configuration_service is None:
            raise TaskItemRecoveryError(
                "configuration_unavailable",
                "the Task's published configuration pin is unavailable",
                status=503,
                next_action="restore the Task's published configuration, then refresh this item",
            )
        try:
            self._configuration_service.validate_runtime_snapshot(snapshot_id, digest)
            revision = self._configuration_service.require(snapshot_id)
            if revision.digest != digest:
                raise ValueError("configuration pin mismatch")
            from mediaflow.infrastructure.runtime_configuration import (
                load_managed_runtime_configuration,
                with_managed_snapshot,
            )

            runtime = load_managed_runtime_configuration(
                revision.document,
                bootstrap_database_path=(
                    self._configuration_service.bootstrap_database_path
                    or getattr(
                        getattr(self._configuration_service, "_repository", None),
                        "database_path",
                        "",
                    )
                ),
            )
            return with_managed_snapshot(
                runtime,
                snapshot_id=snapshot_id,
                digest=digest,
                version=revision.version,
            )
        except TaskItemRecoveryError:
            raise
        except Exception as error:
            raise TaskItemRecoveryError(
                "configuration_unavailable",
                "the Task's published configuration pin is unavailable",
                status=503,
                next_action="restore the Task's published configuration, then refresh this item",
            ) from error
