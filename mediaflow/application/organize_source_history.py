"""The shared per-source organizing-history admission decision.

Slice 47 RO-6: one concrete source's *latest formal organizing outcome* decides
how the shared engine treats it, per entrance:

* a definition due/Run once pass **excludes** the file when that outcome is
  ``failed``/``partial`` — one honest per-item record with zero Provider calls,
  zero execution right and zero Storage mutation;
* a deliberate Files/CLI manual request is **never excluded** by that history:
  the Web summary shows a bounded server-generated warning instead, and the
  ordinary exact confirmation starts genuinely new work under the current pin.

The decision reads the repository's complete matching history (canonical
Storage-relative path plus comparable version evidence); it never derives one
from a display page, an enclosing Task aggregate or the pass's own exclusion
records.  A history read failure is never silently treated as "no history":
the automatic pass records a fail-closed not-processed item and the Preview
refuses the item, so the operator re-reads instead of running on a guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from mediaflow.domain.source_evidence import SourceVersionEvidence
from mediaflow.domain.task_persistence import (
    EXCLUDING_HISTORY_OUTCOME_STATUSES,
    HISTORY_EXCLUDED_ITEM_STAGE,
    HISTORY_UNAVAILABLE_ITEM_STAGE,
)

#: The formal outcome statuses that make an automatic pass exclude the same
#: source version (one canonical definition in the durable Task domain, because
#: the decisive check runs inside the admission transaction).
EXCLUDING_OUTCOME_STATUSES = EXCLUDING_HISTORY_OUTCOME_STATUSES


class OrganizeSourceHistoryRepository(Protocol):
    """The bounded history port the shared decision depends on."""

    def latest_organize_source_outcome(
        self,
        *,
        storage_id: str,
        source_path: str,
        storage_path: str | None = None,
        resource_library_id: str | None = None,
        source_fingerprint: str | None = None,
        source_version: SourceVersionEvidence | None = None,
        exclude_task_id: str | None = None,
    ) -> dict[str, object] | None: ...


@dataclass(frozen=True)
class OrganizeSourceHistory:
    """The bounded, secret-free history answer for one concrete source.

    ``versionApplicable`` records whether the version comparison was
    conclusive: an incomparable/unknown version keeps the history *possibly
    applicable* (never a fabricated "new file"), and the operator-facing text
    says so instead of claiming certainty.
    """

    status: str
    recorded_at: str | None
    destination_storage_id: str | None
    destination_path: str | None
    effect_certainty: str | None
    uncertain_effects: tuple[str, ...]
    completed_operations: tuple[str, ...]
    primary_completed: bool
    error: str | None
    version_applicable: bool
    outcome_id: str | None = None
    outcome_kind: str | None = None

    @property
    def excludes_automatically(self) -> bool:
        return self.status in EXCLUDING_OUTCOME_STATUSES

    def warning(self) -> str:
        """The short operator-facing, secret-free reminder of this history.

        Slice 47 RO-6 keeps the ordinary reminder to the two facts the operator
        must act on: the previous attempt did not finish, and its target may
        already hold files.  Effect uncertainty is named only when the recorded
        Result really carries an unverified effect; the recorded step codes,
        instants, targets and effect identifiers stay in the item's existing
        detail instead of becoming mandatory reading.
        """

        label = (
            "上次整理失败"
            if self.status == "failed"
            else "上次整理部分成功"
            if self.status == "partial"
            else f"上次整理记录为 {self.status}"
        )
        parts = [f"{label}，目标位置可能已有文件"]
        if self.uncertain_effects or self.effect_certainty not in (
            None,
            "none",
            "verified_complete",
        ):
            parts.append("部分存储效果未确认（远端操作可能已发生，无法由本页证明是否完成）")
        if not self.version_applicable:
            parts.append("来源版本与该记录不完全可比，此历史可能适用")
        parts.append("请核对来源、目标与存储实际效果后再确认本次整理")
        return "；".join(parts)


def latest_applicable_outcome(
    repository: object,
    *,
    storage_id: str,
    source_path: str,
    storage_path: str | None = None,
    resource_library_id: str | None = None,
    source_fingerprint: str | None = None,
    source_version: SourceVersionEvidence | None = None,
    exclude_task_id: str | None = None,
) -> OrganizeSourceHistory | None:
    """The latest applicable formal outcome of one concrete source, or ``None``.

    Raises when the repository read fails: callers fail closed and never treat
    an unreadable history as absent.  A repository that does not implement the
    port (an in-memory test double) honestly answers "no history", matching the
    existing optional-boundary convention of the ownership finder.
    """

    finder = getattr(repository, "latest_organize_source_outcome", None)
    if not callable(finder):
        return None
    outcome = finder(
        storage_id=storage_id,
        source_path=source_path,
        storage_path=storage_path,
        resource_library_id=resource_library_id,
        source_fingerprint=source_fingerprint,
        source_version=source_version,
        exclude_task_id=exclude_task_id,
    )
    if outcome is None:
        return None
    status = str(outcome.get("status") or "")
    return OrganizeSourceHistory(
        status=status,
        recorded_at=_bounded_text(outcome.get("outcomeAt")),
        destination_storage_id=_bounded_text(outcome.get("destinationStorageId")),
        destination_path=_bounded_text(outcome.get("destinationPath")),
        effect_certainty=_bounded_text(outcome.get("effectCertainty")),
        uncertain_effects=tuple(
            _bounded_text(value) for value in (outcome.get("uncertainEffects") or ())
        ),
        completed_operations=tuple(
            _bounded_text(value) for value in (outcome.get("completedOperations") or ())
        ),
        primary_completed=bool(outcome.get("primaryCompleted")),
        error=_bounded_text(outcome.get("error")),
        version_applicable=bool(outcome.get("versionComparable", True)),
        outcome_id=_bounded_text(outcome.get("itemId")),
        outcome_kind=_bounded_text(outcome.get("kind")),
    )


def _bounded_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text[:512] if text else None


__all__ = [
    "EXCLUDING_OUTCOME_STATUSES",
    "HISTORY_EXCLUDED_ITEM_STAGE",
    "HISTORY_UNAVAILABLE_ITEM_STAGE",
    "OrganizeSourceHistory",
    "latest_applicable_outcome",
]
