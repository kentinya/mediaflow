from __future__ import annotations

from datetime import UTC, datetime

from mediaflow.domain.dashboard import DashboardRepository, DashboardSnapshot


class DashboardService:
    """Builds a read-only operational snapshot from normalized persistent state."""

    def __init__(
        self,
        repository: DashboardRepository,
        *,
        resource_library_count: int,
        media_library_count: int,
    ) -> None:
        if resource_library_count < 0 or media_library_count < 0:
            raise ValueError("dashboard library counts must be non-negative")
        self._repository = repository
        self._resource_library_count = resource_library_count
        self._media_library_count = media_library_count

    def snapshot(self, *, recent_limit: int = 10) -> DashboardSnapshot:
        if isinstance(recent_limit, bool) or not isinstance(recent_limit, int):
            raise ValueError("dashboard recent limit must be an integer")
        if recent_limit < 1 or recent_limit > 50:
            raise ValueError("dashboard recent limit must be between 1 and 50")
        state = self._repository.load_dashboard_state(recent_limit=recent_limit)
        return DashboardSnapshot(
            as_of=datetime.now(UTC),
            resource_libraries=self._resource_library_count,
            media_libraries=self._media_library_count,
            files=state.files,
            tasks=state.tasks,
            jobs=state.jobs,
            pending_confirmations=state.pending_confirmations,
            pending_metadata_reviews=state.pending_metadata_reviews,
            pending_classification_reviews=state.pending_classification_reviews,
            dead_letter_notifications=state.dead_letter_notifications,
            recent_failures=state.recent_failures,
        )
