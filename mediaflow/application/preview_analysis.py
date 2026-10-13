"""Durable admission and Worker execution of exact Preview analysis.

The existing exact Preview services walk a definition scope or a manual intent
and call the metadata/pipeline analysis synchronously inside the HTTP request.
For a large scope that request blocks for the whole walk and Provider batch, and
the operator has no durable identity, progress or safe cancellation while it
runs.

This service admits that expensive work promptly to the existing resident
Processing Worker instead:

* the HTTP request validates the exact pinned context, records one durable
  ``PreviewAnalysis`` and returns its identity immediately;
* the resident Worker claims it, runs the *existing* exact-Preview service
  (which remains the single authority that produces Preview evidence) and links
  the resulting Preview;
* the operator reads bounded progress, pauses, resumes or cancels at the
  existing safe boundaries.

Safety: the whole stage is metadata-only and zero mutation.  It creates no
execution authority, no dummy Job and no second queue, and a cancelled or failed
analysis leaves no Preview behind.  Only ``OrganizerExecutor`` may ever change
media.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from mediaflow.domain.preview_analysis import (
    PreviewAnalysis,
    PreviewAnalysisConflict,
    PreviewAnalysisError,
    PreviewAnalysisKind,
    PreviewAnalysisProgress,
    PreviewAnalysisStatus,
    PreviewAnalysisUnavailable,
)

DEFAULT_ANALYSIS_LEASE_SECONDS = 300.0


def _analysis_id(value: object) -> str:
    """Validate one caller-generated admission request identity (a UUID)."""

    if value is None:
        return str(uuid4())
    if not isinstance(value, str):
        raise PreviewAnalysisError(
            "the analysis admission request identity is invalid",
            code="invalid_request",
            status=400,
            next_action="reload the exact context and request the analysis again",
        )
    try:
        parsed = UUID(value)
    except (TypeError, ValueError, AttributeError):
        parsed = None
    if parsed is None or str(parsed) != value:
        raise PreviewAnalysisError(
            "the analysis admission request identity is invalid",
            code="invalid_request",
            status=400,
            next_action="reload the exact context and request the analysis again",
        )
    return str(parsed)


class PreviewAnalysisService:
    """Admit, read, control and execute one durable exact analysis."""

    def __init__(
        self,
        repository,
        *,
        definition_previews=None,
        manual_previews=None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        lease_seconds: float = DEFAULT_ANALYSIS_LEASE_SECONDS,
    ) -> None:
        if (
            isinstance(lease_seconds, bool)
            or not isinstance(lease_seconds, int | float)
            or not 0 < float(lease_seconds) <= 86_400
        ):
            raise ValueError("preview analysis worker lease must be between 1 second and 1 day")
        self._repository = repository
        self._definition_previews = definition_previews
        self._manual_previews = manual_previews
        self._clock = clock
        self._lease_seconds = float(lease_seconds)

    @property
    def repository(self):
        return self._repository

    # ------------------------------------------------------------------
    # Admission (prompt; no Storage walk or Provider call in the request)
    # ------------------------------------------------------------------

    def admit_definition(
        self,
        definition_id: str,
        *,
        actor: str,
        revision_id: str | None = None,
        admission_request_id: str | None = None,
    ) -> PreviewAnalysis:
        """Admit durable exact analysis of one published definition.

        The exact pinned revision the existing Preview service will consume is
        resolved *here*, at admission time, and persisted with the record, so a
        Worker that later claims the analysis runs it under the pin the operator
        actually admitted rather than today's Active.
        """

        if self._definition_previews is None:
            raise PreviewAnalysisUnavailable("definition Preview analysis is unavailable")
        if not isinstance(definition_id, str) or not definition_id.strip():
            raise PreviewAnalysisError(
                "definition analysis requires one published definition",
                code="malformed_request",
                status=400,
                next_action="open an existing published definition and request its Preview",
            )
        request_id = _analysis_id(admission_request_id)
        actor = self._actor(actor)
        existing = self._reconcile_request(actor, request_id, kind=PreviewAnalysisKind.DEFINITION)
        if existing is not None:
            return existing
        snapshot_id, snapshot_digest, fingerprint = self._definition_pin(definition_id, revision_id)
        open_analysis = self._find_open(
            actor=actor,
            kind=PreviewAnalysisKind.DEFINITION,
            definition_id=definition_id,
            definition_fingerprint=fingerprint,
            intent_id=None,
            snapshot_id=snapshot_id,
            snapshot_digest=snapshot_digest,
        )
        if open_analysis is not None:
            return open_analysis
        now = self._clock()
        analysis = PreviewAnalysis(
            analysis_id=str(uuid4()),
            kind=PreviewAnalysisKind.DEFINITION,
            actor=actor,
            configuration_snapshot_id=snapshot_id,
            configuration_snapshot_digest=snapshot_digest,
            status=PreviewAnalysisStatus.QUEUED,
            version=1,
            progress=PreviewAnalysisProgress(
                "queued",
                "queued for durable exact analysis by the resident Processing Worker",
            ),
            created_at=now,
            updated_at=now,
            definition_id=definition_id,
            definition_fingerprint=fingerprint,
            admission_request_id=request_id,
        )
        return self._create(analysis)

    def admit_manual(
        self,
        intent_id: str,
        *,
        actor: str,
        expected_version: int,
        admission_request_id: str | None = None,
    ) -> PreviewAnalysis:
        """Admit durable exact analysis of one open manual intent."""

        if self._manual_previews is None:
            raise PreviewAnalysisUnavailable("manual Preview analysis is unavailable")
        if not isinstance(intent_id, str) or not intent_id.strip():
            raise PreviewAnalysisError(
                "manual analysis requires one open manual intent",
                code="malformed_request",
                status=400,
                next_action="open the manual intent and request its exact Preview",
            )
        if (
            isinstance(expected_version, bool)
            or not isinstance(expected_version, int)
            or expected_version < 1
        ):
            raise PreviewAnalysisError(
                "manual analysis requires the current intent version",
                code="malformed_request",
                status=400,
                next_action="reload the manual intent and request its exact Preview",
            )
        request_id = _analysis_id(admission_request_id)
        actor = self._actor(actor)
        existing = self._reconcile_request(actor, request_id, kind=PreviewAnalysisKind.MANUAL)
        if existing is not None:
            return existing
        intent = self._manual_intent(intent_id)
        if intent.status.value != "open":
            raise PreviewAnalysisError(
                "cancelled manual intent cannot be analysed",
                code="intent_not_open",
                status=409,
                next_action="create a new intent from the current File detail",
            )
        if intent.version != expected_version:
            raise PreviewAnalysisConflict(
                "manual intent version is stale; no analysis was admitted",
                details={"currentVersion": intent.version},
            )
        open_analysis = self._find_open(
            actor=actor,
            kind=PreviewAnalysisKind.MANUAL,
            definition_id=None,
            definition_fingerprint=None,
            intent_id=intent_id,
            snapshot_id=intent.snapshot_id,
            snapshot_digest=intent.snapshot_digest,
        )
        if open_analysis is not None:
            return open_analysis
        now = self._clock()
        analysis = PreviewAnalysis(
            analysis_id=str(uuid4()),
            kind=PreviewAnalysisKind.MANUAL,
            actor=actor,
            configuration_snapshot_id=intent.snapshot_id,
            configuration_snapshot_digest=intent.snapshot_digest,
            status=PreviewAnalysisStatus.QUEUED,
            version=1,
            progress=PreviewAnalysisProgress(
                "queued",
                "queued for durable exact analysis by the resident Processing Worker",
            ),
            created_at=now,
            updated_at=now,
            intent_id=intent_id,
            intent_version=intent.version,
            admission_request_id=request_id,
        )
        return self._create(analysis)

    # ------------------------------------------------------------------
    # Readback
    # ------------------------------------------------------------------

    def get(self, analysis_id: str) -> PreviewAnalysis:
        value = self._read(analysis_id)
        if value is None:
            raise PreviewAnalysisError(
                "the requested preview analysis was not found",
                code="preview_analysis_not_found",
                status=404,
                next_action="reload the exact context and request the analysis again",
            )
        return value

    def list(
        self,
        *,
        actor: str | None = None,
        definition_id: str | None = None,
        intent_id: str | None = None,
        limit: int = 100,
    ) -> tuple[PreviewAnalysis, ...]:
        lister = getattr(self._repository, "list_preview_analyses", None)
        if not callable(lister):
            return ()
        return tuple(
            lister(actor=actor, definition_id=definition_id, intent_id=intent_id, limit=limit)
        )

    # ------------------------------------------------------------------
    # Cooperative control
    # ------------------------------------------------------------------

    def request_pause(
        self, analysis_id: str, *, actor: str, expected_version: int
    ) -> PreviewAnalysis:
        return self._request_control(
            analysis_id, actor=actor, expected_version=expected_version, pause=True
        )

    def request_cancel(
        self, analysis_id: str, *, actor: str, expected_version: int
    ) -> PreviewAnalysis:
        return self._request_control(
            analysis_id, actor=actor, expected_version=expected_version, pause=False
        )

    def resume(self, analysis_id: str, *, actor: str, expected_version: int) -> PreviewAnalysis:
        current = self._require_version(analysis_id, expected_version)
        if current.status is not PreviewAnalysisStatus.PAUSED:
            raise PreviewAnalysisError(
                "only a paused preview analysis can be resumed",
                code="analysis_not_paused",
                status=409,
                next_action="reload the durable analysis state and decide again",
                details={"status": current.status.value},
            )
        updated = replace(
            current,
            status=PreviewAnalysisStatus.QUEUED,
            version=current.version + 1,
            pause_requested=False,
            claim_worker_id=None,
            claim_token=None,
            claim_expires_at=None,
            updated_at=self._clock(),
            progress=replace(
                current.progress,
                phase="queued",
                message="resumed; queued for the resident Processing Worker",
            ),
        )
        return self._update(updated, expected_version=current.version)

    # ------------------------------------------------------------------
    # Worker execution
    # ------------------------------------------------------------------

    def claim_and_run(
        self,
        *,
        worker_id: str,
        claim_token: str,
        heartbeat: Callable[[str], bool] | None = None,
    ) -> PreviewAnalysis | None:
        claimer = getattr(self._repository, "claim_next_preview_analysis", None)
        if not callable(claimer):
            raise PreviewAnalysisUnavailable("durable preview analysis claim is unavailable")
        claimed = claimer(
            self._clock(),
            worker_id=worker_id,
            claim_token=claim_token,
            lease_seconds=self._lease_seconds,
        )
        if claimed is None:
            return None
        return self.run_claimed(claimed.analysis_id, worker_id=worker_id, claim_token=claim_token)

    def run_claimed(
        self,
        analysis_id: str,
        *,
        worker_id: str,
        claim_token: str,
    ) -> PreviewAnalysis:
        """Advance one claimed analysis to a settled boundary."""

        analysis = self._read(analysis_id)
        if analysis is None:
            raise PreviewAnalysisUnavailable("the claimed preview analysis is no longer readable")
        if analysis.terminal:
            return analysis
        if analysis.claim_token != claim_token:
            raise PreviewAnalysisError(
                "this Worker no longer owns the preview analysis claim",
                code="preview_analysis_ownership_lost",
                status=409,
                next_action="wait for the current owner to settle, then reload the analysis",
            )
        if analysis.cancel_requested:
            return self._cancel(analysis)
        if analysis.pause_requested:
            return self._publish_paused(analysis)
        running = replace(
            analysis,
            status=PreviewAnalysisStatus.RUNNING,
            version=analysis.version + 1,
            updated_at=self._clock(),
            progress=replace(
                analysis.progress,
                phase="running",
                message="running the exact zero-mutation Preview analysis",
            ),
        )
        running = self._update(running, expected_version=analysis.version)
        try:
            preview = self._analyse(running)
        except PreviewAnalysisError as error:
            return self._fail(running, error.code)
        except Exception:  # noqa: BLE001 - a Worker must never crash the loop
            return self._fail(running, "preview_analysis_failed")
        # Re-read: an operator control may have settled the record while the
        # analysis ran, and the accepted control must win.
        current = self._read(analysis_id) or running
        if current.cancel_requested:
            return self._cancel(current)
        if current.pause_requested:
            return self._publish_paused(current)
        completed = replace(
            current,
            status=PreviewAnalysisStatus.COMPLETED,
            version=current.version + 1,
            preview_id=preview.preview_id,
            claim_worker_id=None,
            claim_token=None,
            claim_expires_at=None,
            updated_at=self._clock(),
            progress=replace(
                current.progress,
                phase="completed",
                message=(
                    "the exact zero-mutation Preview is stored; a separate explicit execution "
                    "confirmation is still required"
                ),
            ),
        )
        return self._update(completed, expected_version=current.version)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _analyse(self, analysis: PreviewAnalysis):
        if analysis.kind is PreviewAnalysisKind.DEFINITION:
            return self._definition_previews.create(analysis.definition_id, actor=analysis.actor)
        return self._manual_previews.create(
            analysis.intent_id,
            None,
            expected_version=analysis.intent_version,
            actor=analysis.actor,
        )

    def _definition_pin(self, definition_id: str, revision_id: str | None) -> tuple[str, str, str]:
        """The exact immutable revision and definition identity the analysis consumes."""

        resolver = getattr(self._definition_previews, "resolve_admission_pin", None)
        if callable(resolver):
            return resolver(definition_id, revision_id)
        raise PreviewAnalysisUnavailable(
            "the definition Preview service cannot resolve an exact admission pin"
        )

    def _manual_intent(self, intent_id: str):
        loader = getattr(self._manual_previews, "load_intent_for_admission", None)
        if callable(loader):
            return loader(intent_id)
        raise PreviewAnalysisUnavailable(
            "the manual Preview service cannot load an exact admission intent"
        )

    def _create(self, analysis: PreviewAnalysis) -> PreviewAnalysis:
        creator = getattr(self._repository, "create_preview_analysis", None)
        if not callable(creator):
            raise PreviewAnalysisUnavailable("durable preview analysis storage is unavailable")
        try:
            return creator(analysis)
        except PreviewAnalysisConflict:
            if analysis.admission_request_id is not None:
                requested = self._reconcile_request(
                    analysis.actor, analysis.admission_request_id, kind=analysis.kind
                )
                if requested is not None:
                    return requested
            raise

    def _read(self, analysis_id: str) -> PreviewAnalysis | None:
        getter = getattr(self._repository, "get_preview_analysis", None)
        if not callable(getter):
            return None
        return getter(analysis_id)

    def _update(self, analysis: PreviewAnalysis, *, expected_version: int) -> PreviewAnalysis:
        updater = getattr(self._repository, "update_preview_analysis", None)
        if not callable(updater):
            raise PreviewAnalysisUnavailable("durable preview analysis update is unavailable")
        return updater(analysis, expected_version=expected_version)

    def _reconcile_request(
        self, actor: str, admission_request_id: str, *, kind: PreviewAnalysisKind
    ) -> PreviewAnalysis | None:
        finder = getattr(self._repository, "find_preview_analysis_by_request_id", None)
        if not callable(finder):
            return None
        requested = finder(actor=actor, admission_request_id=admission_request_id)
        if requested is None:
            return None
        if requested.kind is not kind:
            raise PreviewAnalysisError(
                "this analysis request ID is already bound to a different analysis kind",
                code="admission_request_conflict",
                status=409,
                next_action=(
                    "keep this request ID for its original analysis, or start this one with a "
                    "new request ID"
                ),
                details={"requestIdReuse": True},
            )
        return requested

    def _find_open(
        self,
        *,
        actor: str,
        kind: PreviewAnalysisKind,
        definition_id: str | None,
        definition_fingerprint: str | None,
        intent_id: str | None,
        snapshot_id: str,
        snapshot_digest: str,
    ) -> PreviewAnalysis | None:
        finder = getattr(self._repository, "find_open_preview_analysis", None)
        if not callable(finder):
            return None
        return finder(
            actor=actor,
            kind=kind,
            definition_id=definition_id,
            definition_fingerprint=definition_fingerprint,
            intent_id=intent_id,
            configuration_snapshot_id=snapshot_id,
            configuration_snapshot_digest=snapshot_digest,
        )

    def _require_version(self, analysis_id: str, expected_version: int) -> PreviewAnalysis:
        if isinstance(expected_version, bool) or not isinstance(expected_version, int):
            raise PreviewAnalysisError(
                "preview analysis expected version must be an integer",
                code="malformed_request",
                status=400,
                next_action="reload the durable analysis state and decide again",
            )
        current = self._read(analysis_id)
        if current is None:
            raise PreviewAnalysisError(
                "the requested preview analysis was not found",
                code="preview_analysis_not_found",
                status=404,
                next_action="reload the exact context and request the analysis again",
            )
        if current.version != expected_version:
            raise PreviewAnalysisConflict(
                "preview analysis version is stale; no control was published",
                details={"currentVersion": current.version},
            )
        return current

    def _request_control(
        self,
        analysis_id: str,
        *,
        actor: str,
        expected_version: int,
        pause: bool,
    ) -> PreviewAnalysis:
        self._actor(actor)
        current = self._require_version(analysis_id, expected_version)
        if current.terminal:
            raise PreviewAnalysisError(
                "a settled preview analysis cannot be controlled",
                code="analysis_settled",
                status=409,
                next_action="start a fresh analysis from the exact context",
                details={"status": current.status.value},
            )
        if pause:
            if current.status is PreviewAnalysisStatus.PAUSED:
                return current
            updated = replace(
                current,
                status=PreviewAnalysisStatus.PAUSED,
                version=current.version + 1,
                pause_requested=True,
                updated_at=self._clock(),
                progress=replace(
                    current.progress,
                    phase="paused",
                    message="paused cooperatively; resume to continue the same analysis",
                ),
            )
        else:
            if current.cancel_requested:
                return current
            updated = replace(
                current,
                status=PreviewAnalysisStatus.CANCELLED,
                version=current.version + 1,
                cancel_requested=True,
                claim_worker_id=None,
                claim_token=None,
                claim_expires_at=None,
                updated_at=self._clock(),
                progress=replace(
                    current.progress,
                    phase="cancelled",
                    message="cancelled cooperatively; no Preview was published",
                ),
            )
        return self._update(updated, expected_version=current.version)

    def _publish_paused(self, analysis: PreviewAnalysis) -> PreviewAnalysis:
        updated = replace(
            analysis,
            status=PreviewAnalysisStatus.PAUSED,
            version=analysis.version + 1,
            pause_requested=True,
            updated_at=self._clock(),
            progress=replace(
                analysis.progress,
                phase="paused",
                message="paused cooperatively; resume to continue the same analysis",
            ),
        )
        return self._update(updated, expected_version=analysis.version)

    def _cancel(self, analysis: PreviewAnalysis) -> PreviewAnalysis:
        updated = replace(
            analysis,
            status=PreviewAnalysisStatus.CANCELLED,
            version=analysis.version + 1,
            cancel_requested=True,
            claim_worker_id=None,
            claim_token=None,
            claim_expires_at=None,
            updated_at=self._clock(),
            progress=replace(
                analysis.progress,
                phase="cancelled",
                message="cancelled cooperatively; no Preview was published",
            ),
        )
        return self._update(updated, expected_version=analysis.version)

    def _fail(self, analysis: PreviewAnalysis, code: str) -> PreviewAnalysis:
        current = self._read(analysis.analysis_id) or analysis
        if current.terminal:
            return current
        updated = replace(
            current,
            status=PreviewAnalysisStatus.FAILED,
            version=current.version + 1,
            error=code,
            claim_worker_id=None,
            claim_token=None,
            claim_expires_at=None,
            updated_at=self._clock(),
            progress=replace(
                current.progress,
                phase="failed",
                message=(
                    "the exact analysis failed; inspect the stated condition, repair it, then "
                    "request a fresh analysis"
                ),
            ),
        )
        return self._update(updated, expected_version=current.version)

    @staticmethod
    def _actor(value: object) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise PreviewAnalysisError(
                "preview analysis actor is invalid",
                code="malformed_request",
                status=400,
                next_action="reconnect with an authenticated principal and retry",
            )
        return value


class PreviewAnalysisWorker:
    """Claim and advance admitted durable exact analyses for one Worker."""

    def __init__(
        self,
        analysis_service: PreviewAnalysisService,
        *,
        worker_id: str | None = None,
    ) -> None:
        self._service = analysis_service
        self._worker_id = worker_id or f"preview-analysis-{secrets.token_hex(6)}"

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def commands(self) -> tuple[str, ...]:
        return ("preview_analysis",)

    def run_next(self) -> PreviewAnalysis | None:
        return self._service.claim_and_run(
            worker_id=self._worker_id, claim_token=secrets.token_urlsafe(32)
        )


__all__ = [
    "DEFAULT_ANALYSIS_LEASE_SECONDS",
    "PreviewAnalysisService",
    "PreviewAnalysisWorker",
]
