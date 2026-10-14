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
import threading
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from mediaflow.domain.preview_analysis import (
    PreviewAnalysis,
    PreviewAnalysisConflict,
    PreviewAnalysisControlRequested,
    PreviewAnalysisError,
    PreviewAnalysisKind,
    PreviewAnalysisOwnershipLost,
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
        existing = self._reconcile_request(
            actor,
            request_id,
            kind=PreviewAnalysisKind.DEFINITION,
            definition_id=definition_id,
        )
        # A repeated request without a new explicit revision is a retry of the
        # original admitted intent. Return its durable pin even if Active has
        # since advanced or the definition was removed; callers that intend a
        # different revision must use a new request ID (or provide that
        # revision, which is compared below).
        if existing is not None and revision_id is None:
            return existing
        snapshot_id, snapshot_digest, fingerprint = self._definition_pin(definition_id, revision_id)
        if existing is not None:
            return self._reconcile_request(
                actor,
                request_id,
                kind=PreviewAnalysisKind.DEFINITION,
                definition_id=definition_id,
                definition_fingerprint=fingerprint,
                snapshot_id=snapshot_id,
                snapshot_digest=snapshot_digest,
            )
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
            # This new request identity converged on the already durable open
            # work, so it stays readable by its own ID for reconciliation.
            self._bind_request(request_id, open_analysis)
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
        existing = self._reconcile_request(
            actor,
            request_id,
            kind=PreviewAnalysisKind.MANUAL,
            intent_id=intent_id,
            intent_version=expected_version,
        )
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
            intent_version=intent.version,
            snapshot_id=intent.snapshot_id,
            snapshot_digest=intent.snapshot_digest,
        )
        if open_analysis is not None:
            # The open-work match includes the complete manual intent binding:
            # a corrected intent version is a *different* analysis, so it is
            # never silently answered by the earlier version's queued work.
            # This new request identity converged on the durable work, so it
            # stays readable by its own ID for reconciliation.
            self._bind_request(open_analysis)
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
            cancel_requested=False,
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
        parent_heartbeat: Callable[[], bool] | None = None,
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
        return self.run_claimed(
            claimed.analysis_id,
            worker_id=worker_id,
            claim_token=claim_token,
            heartbeat=heartbeat,
            parent_heartbeat=parent_heartbeat,
        )

    def run_claimed(
        self,
        analysis_id: str,
        *,
        worker_id: str,
        claim_token: str,
        heartbeat: Callable[[str], bool] | None = None,
        parent_heartbeat: Callable[[], bool] | None = None,
    ) -> PreviewAnalysis:
        """Advance one claimed analysis to a settled boundary.

        ``parent_heartbeat`` is the *containing* processing-Worker's own
        registration heartbeat.  While this analysis's walk or Provider batch
        blocks in a single long call, the lease keeper below keeps both the
        analysis claim and the parent registration live, so the resident
        Worker's readiness never reports a false stale while it is actually
        working.  A parent-heartbeat fault is tolerated (bounded, retried on
        the next interval) exactly like the Files transfer keeper's; the
        analysis lease renewal itself remains the publication fence.
        """

        analysis = self._read(analysis_id)
        if analysis is None:
            raise PreviewAnalysisUnavailable("the claimed preview analysis is no longer readable")
        if analysis.terminal:
            return analysis
        if not self._owns_unexpired(analysis, worker_id, claim_token):
            return analysis

        heartbeat_call = heartbeat or (
            lambda _analysis_id: self._heartbeat_claim(analysis_id, worker_id, claim_token)
        )
        stopped = threading.Event()
        lease_lost = threading.Event()

        def maintain_lease() -> None:
            interval = max(0.05, min(5.0, self._lease_seconds / 3.0))
            while not stopped.wait(interval):
                try:
                    renewed = heartbeat_call(analysis_id)
                    if parent_heartbeat is not None:
                        # The parent registration is a liveness signal, not the
                        # analysis fence: its fault never settles the analysis,
                        # and the next interval retries it.
                        try:
                            parent_heartbeat()
                        except Exception:
                            pass
                    if not renewed:
                        lease_lost.set()
                        return
                except Exception:  # a heartbeat failure fences publication
                    lease_lost.set()
                    return

        heartbeat_thread = threading.Thread(
            target=maintain_lease,
            name=f"preview-analysis-lease-{analysis_id[:12]}",
            daemon=True,
        )
        heartbeat_thread.start()
        try:
            return self._run_claimed_owned(
                analysis,
                worker_id=worker_id,
                claim_token=claim_token,
                lease_lost=lease_lost,
            )
        finally:
            stopped.set()
            heartbeat_thread.join(timeout=1)

    def _run_claimed_owned(
        self,
        analysis: PreviewAnalysis,
        *,
        worker_id: str,
        claim_token: str,
        lease_lost: threading.Event,
    ) -> PreviewAnalysis:
        if analysis.cancel_requested or analysis.pause_requested:
            return self._settle_control(analysis, worker_id, claim_token)
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
        try:
            running = self._update_claimed(
                running,
                expected_version=analysis.version,
                worker_id=worker_id,
                claim_token=claim_token,
                clear_claim=False,
            )
        except PreviewAnalysisOwnershipLost:
            return self._read(analysis.analysis_id) or analysis

        def checkpoint(phase: str, visited: int, analysed: int, total: int) -> None:
            if lease_lost.is_set():
                raise PreviewAnalysisOwnershipLost(
                    "the analysis Worker lost its lease; no Preview was published"
                )
            current = self._read(analysis.analysis_id)
            if current is None or not self._owns_unexpired(current, worker_id, claim_token):
                raise PreviewAnalysisOwnershipLost(
                    "the analysis Worker no longer owns an unexpired lease"
                )
            if current.cancel_requested:
                raise PreviewAnalysisControlRequested("cancel")
            if current.pause_requested:
                raise PreviewAnalysisControlRequested("pause")
            progress = PreviewAnalysisProgress(
                "running",
                (
                    "checking the bounded source scope"
                    if phase == "discovery"
                    else "analysing the exact zero-mutation Preview"
                ),
                max(current.progress.visited_entries, visited),
                max(current.progress.analysed_items, analysed),
                max(current.progress.total_items, total),
            )
            if progress == current.progress:
                return
            updated = replace(
                current,
                version=current.version + 1,
                progress=progress,
                updated_at=self._clock(),
            )
            self._update_claimed(
                updated,
                expected_version=current.version,
                worker_id=worker_id,
                claim_token=claim_token,
                clear_claim=False,
            )

        try:
            preview = self._analyse(running, checkpoint=checkpoint)
            checkpoint(
                "analysis",
                running.progress.visited_entries,
                running.progress.analysed_items,
                running.progress.total_items,
            )
        except PreviewAnalysisControlRequested:
            current = self._read(analysis.analysis_id) or running
            return self._settle_control(current, worker_id, claim_token)
        except PreviewAnalysisOwnershipLost:
            return self._read(analysis.analysis_id) or running
        except PreviewAnalysisError as error:
            return self._fail_claimed(running, error.code, worker_id, claim_token)
        except Exception:  # noqa: BLE001 - a Worker must never crash the loop
            return self._fail_claimed(running, "preview_analysis_failed", worker_id, claim_token)
        current = self._read(analysis.analysis_id) or running
        if not self._owns_unexpired(current, worker_id, claim_token):
            return current
        if current.cancel_requested or current.pause_requested:
            return self._settle_control(current, worker_id, claim_token)
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
        publisher = getattr(self._repository, "publish_preview_analysis", None)
        if not callable(publisher):
            return self._fail_claimed(
                current, "preview_analysis_publication_unavailable", worker_id, claim_token
            )
        try:
            publisher(
                completed,
                preview,
                expected_version=current.version,
                worker_id=worker_id,
                claim_token=claim_token,
            )
        except PreviewAnalysisOwnershipLost:
            successor = self._read(analysis.analysis_id) or current
            if (
                successor.claim_token == claim_token
                and successor.claim_worker_id == worker_id
                and (successor.cancel_requested or successor.pause_requested)
            ):
                return self._settle_control(successor, worker_id, claim_token)
            return successor
        except PreviewAnalysisError as error:
            return self._fail_claimed(current, error.code, worker_id, claim_token)
        except Exception:  # noqa: BLE001 - preserve the lease and settle a safe failure
            return self._fail_claimed(current, "preview_analysis_failed", worker_id, claim_token)
        return self.get(analysis.analysis_id)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _analyse(
        self,
        analysis: PreviewAnalysis,
        *,
        checkpoint: Callable[[str, int, int, int], None],
    ):
        if analysis.kind is PreviewAnalysisKind.DEFINITION:
            admitted = self._definition_pin(
                analysis.definition_id, analysis.configuration_snapshot_id
            )
            if admitted != (
                analysis.configuration_snapshot_id,
                analysis.configuration_snapshot_digest,
                analysis.definition_fingerprint,
            ):
                raise PreviewAnalysisError(
                    "the admitted definition pin is missing, changed or no longer verifies",
                    code="definition_pin_stale",
                    status=409,
                    next_action=(
                        "reload the published definition and explicitly request a fresh Preview"
                    ),
                )
            return self._definition_previews.create(
                analysis.definition_id,
                revision_id=analysis.configuration_snapshot_id,
                actor=analysis.actor,
                persist=False,
                analysis_checkpoint=checkpoint,
            )
        return self._manual_previews.create(
            analysis.intent_id,
            None,
            expected_version=analysis.intent_version,
            actor=analysis.actor,
            snapshot_id=analysis.configuration_snapshot_id,
            snapshot_digest=analysis.configuration_snapshot_digest,
            skip_current_snapshot_check=True,
            persist=False,
            analysis_checkpoint=checkpoint,
        )

    def find_by_request_id(self, *, actor: str, admission_request_id: str):
        """The durable analysis one exact client request identity created."""

        finder = getattr(self._repository, "find_preview_analysis_by_request_id", None)
        if not callable(finder):
            return None
        return finder(actor=actor, admission_request_id=admission_request_id)

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
                    analysis.actor,
                    analysis.admission_request_id,
                    kind=analysis.kind,
                    definition_id=analysis.definition_id,
                    definition_fingerprint=analysis.definition_fingerprint,
                    intent_id=analysis.intent_id,
                    intent_version=analysis.intent_version,
                    snapshot_id=analysis.configuration_snapshot_id,
                    snapshot_digest=analysis.configuration_snapshot_digest,
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

    def _update_claimed(
        self,
        analysis: PreviewAnalysis,
        *,
        expected_version: int,
        worker_id: str,
        claim_token: str,
        clear_claim: bool,
    ) -> PreviewAnalysis:
        updater = getattr(self._repository, "update_claimed_preview_analysis", None)
        if not callable(updater):
            raise PreviewAnalysisUnavailable("fenced preview analysis update is unavailable")
        return updater(
            analysis,
            expected_version=expected_version,
            worker_id=worker_id,
            claim_token=claim_token,
            now=self._clock(),
            clear_claim=clear_claim,
        )

    def _heartbeat_claim(self, analysis_id: str, worker_id: str, claim_token: str) -> bool:
        heartbeat = getattr(self._repository, "heartbeat_preview_analysis_claim", None)
        if not callable(heartbeat):
            return False
        return heartbeat(
            analysis_id,
            worker_id=worker_id,
            claim_token=claim_token,
            now=self._clock(),
            lease_seconds=self._lease_seconds,
        )

    def _owns_unexpired(
        self,
        analysis: PreviewAnalysis,
        worker_id: str,
        claim_token: str,
    ) -> bool:
        return (
            analysis.claim_worker_id == worker_id
            and analysis.claim_token == claim_token
            and analysis.claim_expires_at is not None
            and analysis.claim_expires_at > self._clock()
        )

    def _settle_control(
        self, current: PreviewAnalysis, worker_id: str, claim_token: str
    ) -> PreviewAnalysis:
        if not self._owns_unexpired(current, worker_id, claim_token):
            return self._read(current.analysis_id) or current
        cancelled = current.cancel_requested
        status = PreviewAnalysisStatus.CANCELLED if cancelled else PreviewAnalysisStatus.PAUSED
        progress = replace(
            current.progress,
            phase="cancelled" if cancelled else "paused",
            message=(
                "cancelled at a safe analysis boundary; no Preview was published"
                if cancelled
                else (
                    "paused at a safe boundary; resume restarts zero-mutation analysis from its "
                    "pinned context"
                )
            ),
        )
        updated = replace(
            current,
            status=status,
            version=current.version + 1,
            cancel_requested=cancelled,
            pause_requested=not cancelled,
            claim_worker_id=None,
            claim_token=None,
            claim_expires_at=None,
            progress=progress,
            updated_at=self._clock(),
        )
        try:
            return self._update_claimed(
                updated,
                expected_version=current.version,
                worker_id=worker_id,
                claim_token=claim_token,
                clear_claim=True,
            )
        except PreviewAnalysisOwnershipLost:
            return self._read(current.analysis_id) or current

    def _fail_claimed(
        self,
        analysis: PreviewAnalysis,
        code: str,
        worker_id: str,
        claim_token: str,
    ) -> PreviewAnalysis:
        current = self._read(analysis.analysis_id) or analysis
        if current.terminal or not self._owns_unexpired(current, worker_id, claim_token):
            return current
        if current.cancel_requested or current.pause_requested:
            return self._settle_control(current, worker_id, claim_token)
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
        try:
            return self._update_claimed(
                updated,
                expected_version=current.version,
                worker_id=worker_id,
                claim_token=claim_token,
                clear_claim=True,
            )
        except PreviewAnalysisOwnershipLost:
            return self._read(current.analysis_id) or current

    def _reconcile_request(
        self,
        actor: str,
        admission_request_id: str,
        *,
        kind: PreviewAnalysisKind,
        definition_id: str | None = None,
        definition_fingerprint: str | None = None,
        intent_id: str | None = None,
        intent_version: int | None = None,
        snapshot_id: str | None = None,
        snapshot_digest: str | None = None,
    ) -> PreviewAnalysis | None:
        finder = getattr(self._repository, "find_preview_analysis_by_request_id", None)
        if not callable(finder):
            return None
        requested = finder(actor=actor, admission_request_id=admission_request_id)
        if requested is None:
            return None
        mismatch = requested.kind is not kind
        mismatch = mismatch or (
            definition_id is not None and requested.definition_id != definition_id
        )
        mismatch = mismatch or (
            definition_fingerprint is not None
            and requested.definition_fingerprint != definition_fingerprint
        )
        mismatch = mismatch or (intent_id is not None and requested.intent_id != intent_id)
        mismatch = mismatch or (
            intent_version is not None and requested.intent_version != intent_version
        )
        mismatch = mismatch or (
            snapshot_id is not None and requested.configuration_snapshot_id != snapshot_id
        )
        mismatch = mismatch or (
            snapshot_digest is not None
            and requested.configuration_snapshot_digest != snapshot_digest
        )
        if mismatch:
            raise PreviewAnalysisError(
                "this analysis request ID is already bound to different analysis context",
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
        intent_version: int | None = None,
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
            intent_version=intent_version,
            configuration_snapshot_id=snapshot_id,
            configuration_snapshot_digest=snapshot_digest,
        )

    def _bind_request(
        self, admission_request_id: str | None, analysis: PreviewAnalysis
    ) -> None:
        """Keep every accepted request identity durably readable.

        When a request *converges* on already-open work (its equivalent
        admission exists), that request's own identity is bound to the same
        durable record, so a lost response for this request reconciles by its
        own ID instead of a bounded absence.  A request that created its own
        row is already readable through the row's own column.  A binding
        failure is never swallowed silently: it means this identity is already
        bound to different work, which is a reconciliation conflict, not a
        success.
        """

        if admission_request_id is None:
            return
        binder = getattr(self._repository, "bind_admission_request", None)
        if not callable(binder):
            return
        binder(
            actor=analysis.actor,
            admission_request_id=admission_request_id,
            kind="preview-analysis",
            target_id=analysis.analysis_id,
            created_at=self._clock(),
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
            if current.status is PreviewAnalysisStatus.PAUSED or current.pause_requested:
                return current
            running = current.status is PreviewAnalysisStatus.RUNNING
            updated = replace(
                current,
                status=(PreviewAnalysisStatus.RUNNING if running else PreviewAnalysisStatus.PAUSED),
                version=current.version + 1,
                pause_requested=True,
                updated_at=self._clock(),
                progress=replace(
                    current.progress,
                    phase="running" if running else "paused",
                    message=(
                        "pause requested; the Worker will acknowledge it at a safe boundary"
                        if running
                        else (
                            "paused before analysis; resume restarts zero-mutation analysis from "
                            "its pinned context"
                        )
                    ),
                ),
            )
        else:
            if current.cancel_requested:
                return current
            running = current.status is PreviewAnalysisStatus.RUNNING
            updated = replace(
                current,
                status=(
                    PreviewAnalysisStatus.RUNNING if running else PreviewAnalysisStatus.CANCELLED
                ),
                version=current.version + 1,
                cancel_requested=True,
                pause_requested=False,
                claim_worker_id=(current.claim_worker_id if running else None),
                claim_token=(current.claim_token if running else None),
                claim_expires_at=(current.claim_expires_at if running else None),
                updated_at=self._clock(),
                progress=replace(
                    current.progress,
                    phase="running" if running else "cancelled",
                    message=(
                        "cancel requested; the Worker will acknowledge it at a safe boundary"
                        if running
                        else "cancelled before analysis; no Preview was published"
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
        # The containing processing-Worker's registration heartbeat, bound by
        # the resident assembly so a long analysis keeps the actual hosting
        # process's liveness evidence fresh.  It is a liveness signal only: it
        # never changes the analysis's own claim or publication fence.
        self._parent_heartbeat: Callable[[], bool] | None = None

    def set_worker_heartbeat(self, heartbeat: Callable[[], bool]) -> None:
        """Bind the containing processing-Worker's registration heartbeat.

        Mirrors the Files transfer runner's seam: the resident assembly wires
        its own wrapped heartbeat (registration row plus resident-presence
        row) so a long discovery/Provider call cannot make the deployment look
        stale while it is actually working.
        """

        if not callable(heartbeat):
            raise ValueError("preview analysis worker heartbeat must be callable")
        self._parent_heartbeat = heartbeat

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def commands(self) -> tuple[str, ...]:
        return ("preview_analysis",)

    def run_next(self) -> PreviewAnalysis | None:
        return self._service.claim_and_run(
            worker_id=self._worker_id,
            claim_token=secrets.token_urlsafe(32),
            parent_heartbeat=self._parent_heartbeat,
        )


__all__ = [
    "DEFAULT_ANALYSIS_LEASE_SECONDS",
    "PreviewAnalysisService",
    "PreviewAnalysisWorker",
]
