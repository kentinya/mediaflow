from __future__ import annotations

import hashlib
import posixpath
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.domain.organizer import (
    AttachmentType,
    ConflictStrategy,
    ConflictType,
    OrganizePlan,
    OrganizePolicy,
    PlanOperation,
    PlanStatus,
    StorageLocation,
)
from mediaflow.domain.storage import Storage
from mediaflow.domain.task_persistence import (
    ConfirmationStatus,
    ConflictConfirmation,
    ConflictDecisionAudit,
    PersistentTaskRepository,
    TaskItemStatus,
)


class ConflictResolutionError(ValueError):
    pass


class ConflictResolver:
    """Produces replacement plans; it never performs a Storage mutation."""

    def apply_configured(
        self, plan: OrganizePlan, policy: OrganizePolicy, target_storage: Storage
    ) -> OrganizePlan | None:
        if not plan.conflicts:
            return plan
        if any(conflict.type is ConflictType.INVALID_DESTINATION for conflict in plan.conflicts):
            return None
        if policy.conflict_strategy is ConflictStrategy.SKIP:
            return replace(plan, operation=PlanOperation.SKIP, status=PlanStatus.NOOP, conflicts=())
        if policy.conflict_strategy is ConflictStrategy.RENAME:
            return self.rename(plan, target_storage)
        return None

    def rename(self, plan: OrganizePlan, target_storage: Storage) -> OrganizePlan:
        if not plan.target or not plan.relative_destination:
            raise ConflictResolutionError("rename requires a valid relative destination")
        directory, filename = posixpath.split(plan.relative_destination)
        stem, extension = posixpath.splitext(filename)
        if not stem or any(
            part in {"", ".", ".."} for part in plan.relative_destination.split("/")
        ):
            raise ConflictResolutionError("rename destination is unsafe")
        for number in range(1, 1001):
            relative = posixpath.join(directory, f"{stem} ({number}){extension}")
            target = posixpath.join(plan.media_library_root, relative)
            attachments = self._retarget_attachments(plan, target)
            if not target_storage.exists(target) and not any(
                target_storage.exists(item.destination.path) for item in attachments
            ):
                plan_id = hashlib.sha256(
                    "\x00".join(
                        (plan.source_storage_id, plan.source, plan.target_storage_id, target)
                    ).encode()
                ).hexdigest()[:20]
                return replace(
                    plan,
                    target=target,
                    relative_destination=relative,
                    destination_location=StorageLocation(plan.target_storage_id, target),
                    conflicts=(),
                    status=PlanStatus.READY,
                    plan_id=plan_id,
                    attachment_plans=attachments,
                )
        raise ConflictResolutionError("no available rename destination within 1000 attempts")

    @staticmethod
    def _retarget_attachments(plan: OrganizePlan, target: str):
        parent = posixpath.dirname(target)
        named_stem = posixpath.splitext(posixpath.basename(target))[0]
        values = []
        for attachment in plan.attachment_plans:
            extension = posixpath.splitext(attachment.source.path)[1].casefold()
            if attachment.attachment_type is AttachmentType.SUBTITLE:
                filename = f"{named_stem}{attachment.suffix}{extension}"
            elif attachment.attachment_type is AttachmentType.NFO:
                filename = f"{named_stem}.nfo"
            elif attachment.attachment_type is AttachmentType.POSTER:
                filename = f"poster{extension}"
            elif attachment.attachment_type is AttachmentType.FANART:
                filename = f"fanart{extension}"
            elif attachment.attachment_type is AttachmentType.TRAILER:
                filename = f"{named_stem}-trailer{extension}"
            else:
                filename = f"{named_stem}{attachment.suffix}{extension}"
            values.append(
                replace(
                    attachment,
                    destination=StorageLocation(
                        plan.target_storage_id, posixpath.join(parent, filename)
                    ),
                )
            )
        return tuple(values)

    @staticmethod
    def overwrite(plan: OrganizePlan, policy: OrganizePolicy, *, confirmed: bool) -> OrganizePlan:
        if policy.conflict_strategy is not ConflictStrategy.OVERWRITE:
            raise ConflictResolutionError("OrganizePolicy does not allow overwrite")
        if not confirmed:
            raise ConflictResolutionError("overwrite requires explicit high-risk confirmation")
        allowed = {ConflictType.DESTINATION_EXISTS, ConflictType.TARGET_COLLISION}
        if not plan.conflicts or any(conflict.type not in allowed for conflict in plan.conflicts):
            raise ConflictResolutionError("these conflicts cannot be resolved by overwrite")
        return replace(plan, conflicts=(), status=PlanStatus.READY, overwrite_authorized=True)


class ConfirmationService:
    def __init__(self, repository: PersistentTaskRepository) -> None:
        self._repository = repository

    def create(
        self,
        *,
        task_id: str,
        item_id: str,
        plan: OrganizePlan,
        policy: OrganizePolicy,
    ) -> ConflictConfirmation:
        if not plan.conflicts:
            raise ConflictResolutionError("a confirmation requires at least one conflict")
        now = datetime.now(UTC)
        value = ConflictConfirmation(
            str(uuid4()),
            task_id,
            item_id,
            plan.plan_id,
            ",".join(conflict.type.value for conflict in plan.conflicts),
            plan.source_storage_id,
            plan.source_location.path if plan.source_location else plan.source,
            plan.target_storage_id,
            plan.destination_location.path if plan.destination_location else plan.target,
            policy.conflict_strategy.value,
            ConfirmationStatus.PENDING,
            now,
            now,
        )
        self._repository.create_confirmation(value)
        return value

    def resolve(
        self,
        confirmation_id: str,
        strategy: ConflictStrategy,
        *,
        confirm_overwrite: bool = False,
        actor: str | None = None,
        note: str | None = None,
        proposed_destination_path: str | None = None,
    ) -> ConflictConfirmation:
        current = self._repository.get_confirmation(confirmation_id)
        if current is None:
            raise LookupError(f"confirmation {confirmation_id!r} was not found")
        if current.status is not ConfirmationStatus.PENDING:
            raise ConflictResolutionError("confirmation is already resolved")
        if strategy is ConflictStrategy.MANUAL:
            raise ConflictResolutionError(
                "manual keeps the confirmation pending; choose a decision"
            )
        if strategy is ConflictStrategy.OVERWRITE:
            if current.configured_strategy != ConflictStrategy.OVERWRITE.value:
                raise ConflictResolutionError("configured OrganizePolicy does not allow overwrite")
            if not confirm_overwrite:
                raise ConflictResolutionError("overwrite requires --confirm-overwrite")
        now = datetime.now(UTC)
        resolved = replace(
            current,
            status=ConfirmationStatus.RESOLVED,
            selected_strategy=strategy.value,
            proposed_destination_path=proposed_destination_path,
            overwrite_authorized=strategy is ConflictStrategy.OVERWRITE,
            actor=actor,
            note=note,
            updated_at=now,
        )
        audit = ConflictDecisionAudit(
            str(uuid4()),
            confirmation_id,
            strategy.value,
            now,
            resolved.overwrite_authorized,
            actor,
            note,
        )
        item = self._repository.get_item(current.item_id)
        transitioned = (
            replace(
                item,
                status=(
                    TaskItemStatus.SKIPPED
                    if strategy is ConflictStrategy.SKIP
                    else TaskItemStatus.PENDING
                ),
                stage="conflict_resolved",
                updated_at=now,
            )
            if item is not None
            else None
        )
        self._repository.resolve_confirmation(resolved, audit, transitioned)
        return resolved
