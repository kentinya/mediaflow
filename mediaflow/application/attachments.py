from __future__ import annotations

import posixpath
import re
from dataclasses import replace

from mediaflow.domain.manual_safety import redact_evidence_text
from mediaflow.domain.organizer import (
    AttachmentPlan,
    AttachmentPolicy,
    AttachmentType,
    Conflict,
    ConflictType,
    MediaAttachment,
    MediaFileSet,
    OrganizePlan,
    PlanStatus,
    StorageLocation,
)
from mediaflow.domain.storage import Storage, StorageEntry, StorageEntryType, StorageError

_SUBTITLES = {"srt", "ass", "ssa", "vtt", "sub", "sup"}
_IMAGES = {"jpg", "jpeg", "png", "webp"}
_TRAILER_VIDEO = {"mkv", "mp4", "avi", "mov", "webm", "m2ts", "ts"}
_SAFE_SUFFIX = re.compile(r"^[\w.-]*$", re.UNICODE)


class AttachmentDiscovery:
    """Discovers same-directory sidecars through the read-only Storage port."""

    def discover(
        self, storage: Storage, primary: StorageLocation, policy: AttachmentPolicy
    ) -> MediaFileSet:
        if not policy.enabled:
            return MediaFileSet(primary)
        parent, filename = posixpath.split(primary.path)
        primary_stem, _ = posixpath.splitext(filename)
        attachments: list[MediaAttachment] = []
        for entry in storage.list(parent):
            if entry.entry_type is not StorageEntryType.FILE or entry.path == primary.path:
                continue
            attachment = self._classify(entry, primary_stem, policy, primary.storage_id)
            if attachment is not None:
                attachments.append(attachment)
        attachments.sort(
            key=lambda item: (
                item.attachment_type.value,
                item.source.path.casefold(),
                item.source.path,
            )
        )
        return MediaFileSet(primary, tuple(attachments))

    @staticmethod
    def _classify(
        entry: StorageEntry,
        primary_stem: str,
        policy: AttachmentPolicy,
        storage_id: str,
    ) -> MediaAttachment | None:
        name = entry.name
        stem, dot, extension = name.rpartition(".")
        if not dot:
            return None
        extension_lower = extension.casefold()
        stem_folded = stem.casefold()
        primary_folded = primary_stem.casefold()
        same_stem = stem_folded == primary_folded
        suffix = stem[len(primary_stem) :] if stem_folded.startswith(primary_folded) else ""
        related_stem = same_stem or (
            stem_folded.startswith(primary_folded)
            and len(stem) > len(primary_stem)
            and stem[len(primary_stem)] in ".-"
        )
        source = StorageLocation(storage_id, entry.path)
        if policy.subtitles and extension_lower in _SUBTITLES and related_stem:
            if not _SAFE_SUFFIX.fullmatch(suffix):
                return None
            tokens = tuple(token for token in suffix.lstrip(".-").split(".") if token)
            flags = tuple(
                token.casefold() for token in tokens if token.casefold() in {"forced", "sdh", "hi"}
            )
            language = next(
                (token for token in tokens if token.casefold() not in {"forced", "sdh", "hi"}),
                None,
            )
            return MediaAttachment(
                source, AttachmentType.SUBTITLE, suffix, language, flags, entry.size
            )
        if policy.nfo and extension_lower == "nfo" and same_stem:
            return MediaAttachment(source, AttachmentType.NFO, size=entry.size)
        conventional = stem_folded in {"poster", "fanart"}
        same_stem_art = related_stem and suffix.casefold() in {
            ".poster",
            "-poster",
            ".fanart",
            "-fanart",
        }
        if policy.artwork and extension_lower in _IMAGES and (conventional or same_stem_art):
            kind = (
                AttachmentType.FANART
                if "fanart" in stem_folded or "fanart" in suffix.casefold()
                else AttachmentType.POSTER
            )
            return MediaAttachment(source, kind, suffix, size=entry.size)
        if policy.artwork and extension_lower in _IMAGES and related_stem:
            return MediaAttachment(source, AttachmentType.IMAGE, suffix, size=entry.size)
        trailer_suffix = suffix.casefold() in {".trailer", "-trailer"}
        if (
            policy.trailers
            and extension_lower in _TRAILER_VIDEO
            and related_stem
            and trailer_suffix
        ):
            return MediaAttachment(source, AttachmentType.TRAILER, suffix, size=entry.size)
        if policy.other_same_stem and related_stem and _SAFE_SUFFIX.fullmatch(suffix):
            return MediaAttachment(source, AttachmentType.OTHER, suffix, size=entry.size)
        return None


class AttachmentPlanner:
    """Adds safe, read-only observed attachment operations to an existing main-file plan."""

    def plan(
        self,
        plan: OrganizePlan,
        file_set: MediaFileSet,
        target_storage: Storage | None = None,
    ) -> OrganizePlan:
        if not file_set.attachments:
            return plan
        if plan.destination_location is None or plan.source_location is None:
            return self._invalid(plan, "attachment planning requires portable Storage locations")
        destination_parent = posixpath.dirname(plan.destination_location.path)
        named_stem, _ = posixpath.splitext(posixpath.basename(plan.destination_location.path))
        planned: list[AttachmentPlan] = []
        destinations: set[str] = {plan.destination_location.path.casefold()}
        conflicts = list(plan.conflicts)
        warnings = list(plan.warnings)
        for attachment in file_set.attachments:
            blocked_reason = None
            filename = self._target_filename(named_stem, attachment)
            destination_path = posixpath.join(destination_parent, filename)
            try:
                destination = StorageLocation(plan.target_storage_id, destination_path)
            except ValueError:
                return self._invalid(plan, "attachment destination is unsafe")
            folded = destination.path.casefold()
            if folded in destinations:
                blocked_reason = "attachment_collision"
            destinations.add(folded)
            if target_storage is not None:
                try:
                    exists = target_storage.exists(destination.path)
                except StorageError:
                    blocked_reason = "storage_unavailable"
                else:
                    if exists:
                        blocked_reason = "attachment_collision"
            if blocked_reason:
                warnings.append(f"{blocked_reason}: {destination.path}")
            planned.append(
                AttachmentPlan(
                    attachment.source,
                    destination,
                    attachment.attachment_type,
                    plan.operation,
                    attachment.suffix,
                    attachment.language,
                    blocked_reason,
                )
            )
        return replace(
            plan,
            attachment_plans=tuple(planned),
            conflicts=tuple(conflicts),
            warnings=tuple(warnings),
            status=PlanStatus.CONFLICT if conflicts else plan.status,
        )

    @staticmethod
    def _target_filename(named_stem: str, attachment: MediaAttachment) -> str:
        extension = posixpath.splitext(attachment.source.path)[1].casefold()
        if attachment.attachment_type is AttachmentType.SUBTITLE:
            return f"{named_stem}{attachment.suffix}{extension}"
        if attachment.attachment_type is AttachmentType.NFO:
            return f"{named_stem}.nfo"
        if attachment.attachment_type is AttachmentType.POSTER:
            return f"poster{extension}"
        if attachment.attachment_type is AttachmentType.FANART:
            return f"fanart{extension}"
        if attachment.attachment_type is AttachmentType.TRAILER:
            return f"{named_stem}-trailer{extension}"
        return f"{named_stem}{attachment.suffix}{extension}"

    @staticmethod
    def _invalid(plan: OrganizePlan, details: str) -> OrganizePlan:
        conflict = Conflict(ConflictType.INVALID_DESTINATION, plan.source, plan.target, details)
        return replace(plan, conflicts=(*plan.conflicts, conflict), status=PlanStatus.INVALID)


def attachment_result_document(
    plan: OrganizePlan,
    attachment: AttachmentPlan,
    *,
    status: str,
    reason: str | None = None,
    certainty: str = "none",
    completed: tuple[str, ...] = (),
) -> dict[str, object]:
    """Display evidence only; this never grants attachment or primary replay authority."""
    action = {
        "MOVE": "移动",
        "COPY": "复制",
        "LINK": "软链接"
        if plan.link_operation and plan.link_operation.value == "soft_link"
        else "硬链接",
    }.get(plan.operation.value)
    name = redact_evidence_text(posixpath.basename(attachment.destination.path))
    if certainty in {"unknown", "attempted_unverified"}:
        next_action = "效果尚未确认，请核查附件来源、目标及持久步骤；不要重放主文件或附件。"
    elif status == "success":
        next_action = "附件已验证完成，无需重复操作。"
    elif reason in {"primary_not_completed", "execution_stopped", "authority_refused"}:
        next_action = "执行已停止，请核查持久结果、来源和目标；此记录不授权重放主文件或附件。"
    elif not action:
        next_action = "固定策略不允许继续，请核查附件来源、目标与策略。"
    elif reason == "attachment_collision":
        next_action = f"有冲突：{name}，请修正后再进行‘{action}’操作（仅该附件，不重放主文件）。"
    elif reason == "source_missing":
        next_action = (
            f"附件来源不存在，请核查并补正来源后按固定策略进行‘{action}’操作"
            "（仅该附件，不重放主文件）。"
        )
    else:
        next_action = (
            f"附件未执行，请核查来源、目标及存储权限后按固定策略进行‘{action}’操作"
            "（仅该附件，不重放主文件）。"
        )
    return {
        "type": attachment.attachment_type.value,
        "language": attachment.language,
        "operation": plan.operation.value,
        "action_label": action,
        "status": status,
        "source_storage_id": attachment.source.storage_id,
        "source_path": redact_evidence_text(attachment.source.path),
        "destination_storage_id": attachment.destination.storage_id,
        "destination_path": redact_evidence_text(attachment.destination.path),
        "reason": reason,
        "effect_certainty": certainty,
        "completed_operations": list(completed),
        "next_action": next_action,
    }
