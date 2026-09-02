"""Shared admission gate for single-item recovery requests.

The gate is the only application entry point that may admit a recovery write.  It reads
the same stage-aware checkpoint exposed to API/Web, validates the pinned snapshot, and
delegates the atomic request/action transition to the repository.  It never executes a
continuation or touches Storage/Provider services.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.domain.configuration_management import RuntimeSnapshotUnavailable
from mediaflow.domain.recovery import (
    RecoveryAdmissionError,
    RecoveryAdmissionReason,
    RecoveryRequest,
)

_SENSITIVE_NOTE = re.compile(
    r"(?ix)"
    r"(?:bearer\s+\S+|"
    r"(?:password|passwd|secret|token|api[_-]?key|authorization|cookie)\s*[:=]\s*\S+)"
)
_PRIVATE_ENDPOINT = re.compile(r"(?i)(?:https?|s3|file)://[^\s]+")
_ABSOLUTE_PATH = re.compile(r"(?<![\w])(?:/[\w.~-]+(?:/[\w. .~+\-]+)*|[A-Za-z]:[\\/][^\s]+)")
_UNSAFE_SOURCE_PREFIX = re.compile(r"(?i)^(?:[a-z][a-z0-9+.-]*://|[a-z]:/|~(?:/|$))")


class RecoveryAdmissionService:
    MAX_IDENTIFIER = 256
    MAX_ACTOR = 200
    MAX_NOTE = 500
    MAX_VERSION = 128

    def __init__(
        self,
        repository,
        *,
        snapshot_validator: Callable[[str, str], None] | None = None,
        checkpoint_service: ProcessingCheckpointService | None = None,
    ) -> None:
        self._repository = repository
        self._snapshot_validator = snapshot_validator
        self._checkpoint_service = checkpoint_service or ProcessingCheckpointService(
            repository, snapshot_validator=snapshot_validator
        )

    @property
    def repository(self):
        return self._repository

    @property
    def checkpoint_service(self) -> ProcessingCheckpointService:
        return self._checkpoint_service

    def admit(
        self,
        task_id: str,
        item_id: str,
        *,
        action_id: str,
        expected_checkpoint_version: str,
        actor: str,
        note: str | None = None,
    ) -> RecoveryRequest:
        task_id = self._required_id(task_id, "Task ID")
        item_id = self._required_id(item_id, "TaskItem ID")
        action_id = self._required_id(action_id, "recovery action")
        expected_checkpoint_version = self._version(expected_checkpoint_version)
        actor = self._redact_note(self._bounded_text(actor, self.MAX_ACTOR, "recovery actor"))
        if actor is None:
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.INSUFFICIENT_AUTHORITY,
                "recovery actor is required",
            )
        note = self._bounded_text(note, self.MAX_NOTE, "recovery note", optional=True)
        note = self._redact_note(note)

        checkpoint = self._checkpoint_service.get(item_id)
        if checkpoint.task_id != task_id:
            # Preserve the existing transport convention (the API maps this to not-found)
            # while retaining a bounded domain reason for direct callers and audit logic.
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.ITEM_TASK_MISMATCH,
                "TaskItem was not found in the specified Task",
            )
        existing = checkpoint.active_recovery_request
        if existing is not None:
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.DUPLICATE_ACTIVE_REQUEST,
                "an active recovery request already exists for this TaskItem",
                current_checkpoint_version=checkpoint.checkpoint_version,
                existing_request=existing,
            )
        if expected_checkpoint_version != checkpoint.checkpoint_version:
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.STALE_CHECKPOINT,
                "checkpoint version is stale; refresh before requesting recovery",
                current_checkpoint_version=checkpoint.checkpoint_version,
            )
        self._validate_source_path(checkpoint.source_path, checkpoint.checkpoint_version)
        if action_id in {"retry", "ignore"} and checkpoint.status not in {
            "success",
            "dry_run",
            "skipped",
            "ignored",
            "cancelled",
        }:
            self._validate_snapshot(checkpoint)
        if action_id == "retry":
            self._validate_retry_checkpoint(checkpoint)
        action = next(
            (value for value in checkpoint.actions if value.action_id == action_id),
            None,
        )
        if action is None:
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.INVALID_ACTION,
                "requested recovery action is unknown",
                current_checkpoint_version=checkpoint.checkpoint_version,
            )
        if not action.admissible:
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.ACTION_NOT_PERMITTED,
                "requested recovery action is not permitted",
                current_checkpoint_version=checkpoint.checkpoint_version,
            )

        snapshot_id = checkpoint.configuration.snapshot_id
        snapshot_digest = checkpoint.configuration.snapshot_digest
        blocker = checkpoint.blocker
        request = RecoveryRequest(
            request_id=str(uuid4()),
            task_id=task_id,
            item_id=item_id,
            action_id=action_id,
            checkpoint_version=checkpoint.checkpoint_version,
            source_storage_id=checkpoint.source_storage_id,
            source_path=checkpoint.source_path,
            configuration_snapshot_id=snapshot_id,
            configuration_snapshot_digest=snapshot_digest,
            actor=actor,
            requested_at=datetime.now(UTC),
            note=note,
            next_action=self._next_action(action_id),
            review_kind=blocker.kind if action_id == "ignore" and blocker else None,
            review_id=blocker.blocker_id if action_id == "ignore" and blocker else None,
        )
        admitted = self._repository.admit_recovery_request(
            request,
            expected_checkpoint_version=expected_checkpoint_version,
            checkpoint_projector=self._checkpoint_service._project,
        )
        if admitted.request_id != request.request_id:
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.DUPLICATE_ACTIVE_REQUEST,
                "an active recovery request already exists for this TaskItem",
                existing_request=admitted,
            )
        return admitted

    @staticmethod
    def _validate_source_path(path: str, checkpoint_version: str) -> None:
        normalized = path.replace("\\", "/") if isinstance(path, str) else ""
        parts = normalized.split("/")
        if (
            not normalized
            or len(normalized) > 4096
            or normalized.startswith("/")
            or _UNSAFE_SOURCE_PREFIX.match(normalized)
            or "\x00" in normalized
            or ":" in normalized
            or any(part == ".." for part in parts)
            or normalized.startswith("[")
        ):
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.INVALID_INPUT,
                "the TaskItem source scope is not a safe Storage-relative path",
                current_checkpoint_version=checkpoint_version,
            )

    def _validate_snapshot(self, checkpoint) -> None:
        snapshot_id = checkpoint.configuration.snapshot_id
        snapshot_digest = checkpoint.configuration.snapshot_digest
        if not snapshot_id or not snapshot_digest:
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.SNAPSHOT_UNAVAILABLE,
                "the parent Task has no pinned configuration snapshot",
                current_checkpoint_version=checkpoint.checkpoint_version,
            )
        if checkpoint.configuration.resolvable is False:
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.SNAPSHOT_UNAVAILABLE,
                "the pinned configuration snapshot is unavailable",
                current_checkpoint_version=checkpoint.checkpoint_version,
            )
        if self._snapshot_validator is None:
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.SNAPSHOT_UNAVAILABLE,
                "the pinned configuration snapshot cannot be validated",
                current_checkpoint_version=checkpoint.checkpoint_version,
            )
        try:
            self._snapshot_validator(snapshot_id, snapshot_digest)
        except RuntimeSnapshotUnavailable as error:
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.SNAPSHOT_UNAVAILABLE,
                "the pinned configuration snapshot is unavailable",
                current_checkpoint_version=checkpoint.checkpoint_version,
            ) from error
        except Exception as error:
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.SNAPSHOT_UNAVAILABLE,
                "the pinned configuration snapshot cannot be validated",
                current_checkpoint_version=checkpoint.checkpoint_version,
            ) from error

    @staticmethod
    def _validate_retry_checkpoint(checkpoint) -> None:
        """Re-check every safety fact that makes an automatic retry admissible.

        The checkpoint is the public recovery contract, but a caller must not be able to
        smuggle a retry through by supplying a stale or forged action list.  These guards
        intentionally remain bounded and secret-free; the repository performs its own
        atomic re-projection before the transition is persisted.
        """

        if checkpoint.blocker is not None:
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.ACTION_NOT_PERMITTED,
                "automatic retry is blocked by a pending operator resolution",
                current_checkpoint_version=checkpoint.checkpoint_version,
            )
        if checkpoint.raw_stage == "admission_interrupted":
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.ACTION_NOT_PERMITTED,
                "automatic retry is refused until the interrupted admission is reconciled",
                current_checkpoint_version=checkpoint.checkpoint_version,
            )
        certainty = getattr(checkpoint.effect_certainty, "value", checkpoint.effect_certainty)
        if certainty in {"attempted_unverified", "unknown"}:
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.ACTION_NOT_PERMITTED,
                "automatic retry is refused because the effect state is not verified",
                current_checkpoint_version=checkpoint.checkpoint_version,
            )
        if checkpoint.configuration.resolvable is not True:
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.SNAPSHOT_UNAVAILABLE,
                "the pinned configuration snapshot is not resolvable",
                current_checkpoint_version=checkpoint.checkpoint_version,
            )

    @staticmethod
    def _next_action(action_id: str) -> str:
        if action_id == "retry":
            return "inspect the admitted request, then continue the supported single-item recovery"
        if action_id == "ignore":
            return "reload the checkpoint and inspect the ignored item; no media mutation occurred"
        return "follow the linked resolution journey and reload the checkpoint"

    @staticmethod
    def _required_id(value: str, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.INVALID_INPUT, f"{label} is required"
            )
        normalized = value.strip()
        if len(normalized) > RecoveryAdmissionService.MAX_IDENTIFIER:
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.INVALID_INPUT, f"{label} is too long"
            )
        return normalized

    @classmethod
    def _version(cls, value: str) -> str:
        normalized = cls._required_id(value, "checkpoint version")
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.INVALID_VERSION,
                "checkpoint version is invalid",
            )
        return normalized

    @staticmethod
    def _bounded_text(
        value: str | None,
        limit: int,
        label: str,
        *,
        optional: bool = False,
    ) -> str | None:
        if value is None:
            return None if optional else ""
        if not isinstance(value, str):
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.INVALID_INPUT, f"{label} is invalid"
            )
        normalized = " ".join(value.split())
        if len(normalized) > limit:
            raise RecoveryAdmissionError(
                RecoveryAdmissionReason.INVALID_INPUT,
                f"{label} exceeds {limit} characters",
            )
        return normalized or None

    @staticmethod
    def _redact_note(value: str | None) -> str | None:
        """Keep operator context while preventing obvious secret/path leakage in audit text."""

        if value is None:
            return None
        redacted = _SENSITIVE_NOTE.sub("[redacted]", value)
        redacted = _PRIVATE_ENDPOINT.sub("[redacted]", redacted)
        redacted = _ABSOLUTE_PATH.sub("[redacted]", redacted)
        return redacted or None
