"""Bounded, durable, metadata-only discovery of a selected ResourceLibrary scope.

This is the Slice 44 RO-6 application boundary.  The Web submits only an enabled
ResourceLibrary identity plus exact ResourceLibrary-relative folder/file paths;
this service resolves the real entry types, the pinned immutable Active
configuration, the Storage adapter, the concrete budgets and every eligible
primary source from live Storage observations.

Safety invariants:

* the whole stage is **metadata only** -- ``stat``/``list_page`` through the
  existing read-only Storage guard; no content read, no hash, no Provider call,
  no FileIndex lookup and no mutation;
* discovery creates **no execution authority**.  Finalizing only freezes an
  ordinary deduplicated ``ManualSourceIdentity`` list and hands it to the
  existing ``create_from_sources`` admission, which still requires a separate
  exact Preview and an explicitly confirmed execution;
* budgets are persisted with the exact admitted scope and are never reset by
  pause, restart or continue; a limit produces an honest incomplete state and
  never a silently executable first-N prefix.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.application.scan_filters import (
    ObservedSource,
    ScanEntryVerdict,
    StabilityVerdict,
    classify_entry,
    directory_may_match,
    entry_extension,
    excluded_directory,
    stability_verdict,
)
from mediaflow.domain.file_lifecycle import (
    OccurrenceState,
    occurrence_id_for,
    source_fingerprint,
)
from mediaflow.domain.manual_organize import (
    ManualIntentError,
    ManualSourceIdentity,
)
from mediaflow.domain.media_discovery import (
    BUDGET_LIMITED_REASONS,
    MAX_DISCOVERY_TEXT_LENGTH,
    DiscoveryBudgets,
    DiscoveryConflict,
    DiscoveryCounters,
    DiscoveryEntryKind,
    DiscoveryError,
    DiscoveryFinding,
    DiscoveryFindingKind,
    DiscoveryIncompleteReason,
    DiscoveryObservation,
    DiscoveryProgress,
    DiscoveryReasonCount,
    DiscoveryScopeEntry,
    DiscoveryStatus,
    DiscoveryUnavailable,
    MediaDiscovery,
    bounded_path,
    deduplicate_scope,
    discovery_scope_signature,
)
from mediaflow.domain.storage import (
    Storage,
    StorageEntry,
    StorageEntryType,
    StorageError,
)

DEFAULT_DISCOVERY_LEASE_SECONDS = 300.0

#: Bounded, secret-free exclusion explanations.  The reason string is a stable
#: machine value; the operator copy lives in the Web projection.
_REASON_TEMPORARY = "temporary_file"
_REASON_UNSUPPORTED_EXTENSION = "unsupported_extension"
_REASON_EXCLUDED_RULE = "configured_exclude"
_REASON_NOT_INCLUDED = "not_included"
_REASON_UNSUPPORTED_TYPE = "unsupported_entry_type"
_REASON_SYMLINK = "symbolic_link"
_REASON_UNREADABLE = "unreadable_directory"
_REASON_UNSTABLE_AGE = "waiting_minimum_age"
_REASON_UNSTABLE_SIZE = "waiting_stable_size"
_REASON_CHANGED = "source_changed_since_observation"
_REASON_DEPTH = "configured_depth_exceeded"
_REASON_UNSAFE_ENTRY = "unsafe_provider_entry"
_REASON_CURSOR = "repeated_provider_cursor"
#: The reason recorded when the Task's own safety depth bound — measured
#: below each selected folder — truncates the walk.  It is kept separate from
#: the configured library-root depth so an exhausted safety budget is never
#: presented as a configured policy exclusion.
_REASON_SAFETY_DEPTH = "safety_depth_limit"

_TEMPORARY_SUFFIXES = (".part", ".tmp", ".download", ".crdownload", ".!qb")


class MediaDiscoveryService:
    """Admit, run, control and finalize one bounded selected-scope discovery."""

    def __init__(
        self,
        repository,
        intent_service,
        *,
        configuration_service=None,
        runtime_resolver: Callable[..., object] | None = None,
        configuration: object | None = None,
        storages: Mapping[str, Storage] | None = None,
        storage_factory: Callable[..., Mapping[str, Storage]] | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        monotonic: Callable[[], float] = time.monotonic,
        lease_seconds: float = DEFAULT_DISCOVERY_LEASE_SECONDS,
        budgets: DiscoveryBudgets | None = None,
    ) -> None:
        if (
            isinstance(lease_seconds, bool)
            or not isinstance(lease_seconds, int | float)
            or not 0 < float(lease_seconds) <= 86_400
        ):
            raise ValueError("discovery worker lease must be between 1 second and 1 day")
        self._repository = repository
        self._intent_service = intent_service
        self._configuration_service = configuration_service or getattr(
            intent_service, "_configuration_service", None
        )
        self._runtime_resolver = runtime_resolver
        self._configuration = configuration
        self._storages = dict(storages or {})
        self._storage_factory = storage_factory
        self._clock = clock
        self._monotonic = monotonic
        self._lease_seconds = float(lease_seconds)
        self._budgets = budgets or DiscoveryBudgets()

    @property
    def repository(self):
        return self._repository

    @property
    def budgets(self) -> DiscoveryBudgets:
        return self._budgets

    # ------------------------------------------------------------------
    # Admission (prompt, zero Storage enumeration in the HTTP request)
    # ------------------------------------------------------------------

    def admit(
        self,
        *,
        resource_library_id: str,
        relative_paths: Sequence[str] | None,
        actor: str,
    ) -> MediaDiscovery:
        """Validate the whole submitted scope and durably admit one discovery.

        This performs exactly one bounded ``stat`` per submitted path so the
        real entry type (folder vs ordinary file) is backend authority rather
        than a browser claim.  It never recurses, never enumerates a directory
        and never calls a Provider, so admission stays prompt.
        """

        actor = self._actor(actor)
        if not self._valid_scope_id(resource_library_id):
            raise DiscoveryError(
                "folder and mixed-selection discovery requires one enabled ResourceLibrary",
                code="malformed_selection",
                next_action="select one enabled ResourceLibrary and retry",
            )
        if not isinstance(relative_paths, (list, tuple)) or not relative_paths:
            raise DiscoveryError(
                "discovery requires at least one selected folder or file",
                code="selection_empty",
                next_action="select one or more folders or files and retry",
            )
        if len(relative_paths) > self._budgets.max_scope_paths:
            raise DiscoveryError(
                f"discovery accepts at most {self._budgets.max_scope_paths} selected scopes",
                code="selection_over_limit",
                next_action="select a smaller bounded scope and resubmit",
                details={"limit": self._budgets.max_scope_paths},
            )
        # Validate every raw value before deduplication: a partly invalid
        # request must never silently become a different valid scope.
        submitted: list[DiscoveryScopeEntry] = []
        for value in relative_paths:
            path = bounded_path(value, allow_empty=False)
            submitted.append(DiscoveryScopeEntry(path, DiscoveryEntryKind.FILE))
        snapshot_id, snapshot_digest = self._active_pin()
        runtime = self._load_runtime(snapshot_id, snapshot_digest)
        library = self._runtime_library(runtime, resource_library_id)
        storage = self._guarded_storage(runtime, library.storage_id)
        resolved: list[DiscoveryScopeEntry] = []
        for entry in submitted:
            resolved.append(self._resolve_entry_kind(storage, library, entry))
        deduplicated = deduplicate_scope(tuple(resolved))
        if not deduplicated:
            raise DiscoveryError(
                "the selected scope contains no distinct source",
                code="selection_empty",
                next_action="select one or more folders or files and retry",
            )
        # Actor/scope/pin-bound admission identity: an identical open
        # submission for the same principal, the same deduplicated scope and
        # the same immutable Active pin is reconciled to its durable record
        # instead of admitting a second duplicate walk.  A *terminal* record
        # is never reopened by resubmission — deliberate successor work is
        # always a new discovery.
        reconciliation = self._reconcile_admission(
            actor, deduplicated, snapshot_id, snapshot_digest
        )
        if reconciliation is not None:
            return reconciliation
        now = self._clock()
        discovery_id = str(uuid4())
        progress = DiscoveryProgress(
            "queued",
            deduplicated,
            DiscoveryCounters(),
            DiscoveryIncompleteReason.NONE,
            (),
            (),
            # An explicitly selected file is observed directly; an explicitly
            # selected folder is walked recursively.  Both are seeded here so
            # the first Worker pass covers the whole admitted scope.
            tuple(entry.path for entry in deduplicated if entry.kind is DiscoveryEntryKind.FILE),
            tuple(
                entry.path for entry in deduplicated if entry.kind is DiscoveryEntryKind.DIRECTORY
            ),
            None,
            None,
            (),
            "queued for bounded discovery by the resident Processing Worker",
        )
        discovery = MediaDiscovery(
            discovery_id,
            actor,
            library.library_id,
            library.storage_id,
            snapshot_id,
            snapshot_digest,
            DiscoveryStatus.QUEUED,
            1,
            self._budgets,
            progress,
            now,
            now,
            (),
            None,
            None,
            None,
            None,
            None,
            0,
            False,
            False,
            None,
        )
        creator = getattr(self._repository, "create_media_discovery", None)
        if not callable(creator):
            raise DiscoveryUnavailable("durable media discovery storage is unavailable")
        return creator(discovery)

    def _reconcile_admission(
        self,
        actor: str,
        scope: tuple[DiscoveryScopeEntry, ...],
        snapshot_id: str,
        snapshot_digest: str,
    ) -> MediaDiscovery | None:
        """Find one already durable open discovery for this exact admission.

        The match is bound to the actor, the canonical deduplicated scope
        signature and the admitted configuration pin.  A lost admission
        response therefore reconciles to the original durable record instead
        of admitting a duplicate walk, while a different scope, a different
        principal or a repinned Active configuration is always a new
        admission.
        """

        lister = getattr(self._repository, "list_media_discoveries", None)
        if not callable(lister):
            return None
        signature = discovery_scope_signature(scope)
        # The reconciliation window is bounded: it reads only the recent
        # durable records of this actor, so the cost stays bounded even for a
        # principal with a long discovery history.
        for candidate in lister(actor=actor, limit=50):
            if candidate.terminal or candidate.frozen:
                continue
            if candidate.snapshot_id != snapshot_id or candidate.snapshot_digest != snapshot_digest:
                continue
            if candidate.status is DiscoveryStatus.PAUSED:
                # A paused discovery stays open but it is an explicit
                # operator-controlled state: resubmitting its scope is still
                # the same work, so it reconciles rather than duplicating.
                pass
            if discovery_scope_signature(candidate.progress.scope_entries) != signature:
                continue
            return candidate
        return None

    # ------------------------------------------------------------------
    # Readback
    # ------------------------------------------------------------------

    def get(self, discovery_id: str) -> MediaDiscovery:
        discovery = self._read(discovery_id)
        if discovery is None:
            raise DiscoveryError(
                "the requested discovery was not found",
                code="discovery_not_found",
                status=404,
                next_action="reload the Operations task center and start a new bounded discovery",
            )
        return discovery

    def list(self, *, actor: str | None = None, limit: int = 100) -> tuple[MediaDiscovery, ...]:
        lister = getattr(self._repository, "list_media_discoveries", None)
        if not callable(lister):
            return ()
        return tuple(lister(actor=actor, limit=limit))

    def discovery_for_intent(self, intent_id: str) -> MediaDiscovery | None:
        finder = getattr(self._repository, "find_media_discovery_for_intent", None)
        if not callable(finder):
            return None
        return finder(intent_id)

    # ------------------------------------------------------------------
    # Cooperative control
    # ------------------------------------------------------------------

    def request_pause(
        self, discovery_id: str, *, actor: str, expected_version: int
    ) -> MediaDiscovery:
        return self._request_control(
            discovery_id, actor=actor, expected_version=expected_version, pause=True
        )

    def request_cancel(
        self, discovery_id: str, *, actor: str, expected_version: int
    ) -> MediaDiscovery:
        return self._request_control(
            discovery_id, actor=actor, expected_version=expected_version, pause=False
        )

    def resume(self, discovery_id: str, *, actor: str, expected_version: int) -> MediaDiscovery:
        """Clear a cooperative pause so the next Worker pass continues safely."""

        actor = self._actor(actor)
        discovery = self._require_version(discovery_id, expected_version)
        if discovery.terminal:
            raise DiscoveryError(
                "a finished discovery cannot be resumed",
                code="discovery_not_open",
                status=409,
                next_action="start a new bounded discovery from Files",
            )
        if discovery.cancel_requested:
            raise DiscoveryConflict(
                "this discovery already has a cooperative cancellation request",
                details={"discoveryId": discovery_id},
            )
        if not discovery.pause_requested:
            return discovery
        now = self._clock()
        updated = replace(
            discovery,
            status=DiscoveryStatus.QUEUED,
            version=discovery.version + 1,
            pause_requested=False,
            updated_at=now,
            progress=replace(
                discovery.progress,
                phase="queued",
                message="resumed by the operator; the resident Worker continues the same scope",
            ),
        )
        return self._persist(updated, expected_version=expected_version)

    def finalize(self, discovery_id: str, *, actor: str, expected_version: int) -> MediaDiscovery:
        """Freeze the discovered source list under an explicit operator action.

        The operator's own finalize is the deliberate human step that turns a
        completed observation into the immutable reviewed source list.  It
        creates a durable manual intent only; it grants no execution authority
        and mutates nothing.
        """

        actor = self._actor(actor)
        discovery = self._require_version(discovery_id, expected_version)
        if discovery.frozen:
            return discovery
        if discovery.status not in {
            DiscoveryStatus.COMPLETED,
            DiscoveryStatus.PARTIAL_SUCCESS,
        }:
            raise DiscoveryError(
                "only a finished bounded discovery can be finalized",
                code="discovery_not_complete",
                status=409,
                next_action="wait for the resident Worker to finish, then finalize the findings",
                details={"status": discovery.status.value},
            )
        if not discovery.sources:
            raise DiscoveryError(
                "this discovery found no eligible primary source to freeze",
                code="selection_empty",
                status=409,
                next_action="narrow the selected scope or correct the configured filters",
            )
        if discovery.progress.incomplete_reason in BUDGET_LIMITED_REASONS:
            # A budget/safety/cursor-limited walk recorded a truncated prefix,
            # never a complete scope: freezing it would silently admit a
            # first-N subset as ordinary executable work.  The honest
            # recovery is a narrowed scope and a new bounded discovery; an
            # ordinary read-failure subset is unaffected and keeps its own
            # explicit-review path.
            reason = discovery.progress.incomplete_reason.value
            raise DiscoveryError(
                "this discovery stopped at a budget or safety limit, so its findings are "
                "an incomplete subset and cannot be frozen",
                code="discovery_budget_limited",
                status=409,
                next_action=(
                    "narrow the selected scope to fit the limit and start a new bounded "
                    "discovery; the recorded findings are not an executable subset"
                ),
                details={"incompleteReason": reason},
            )
        return self._finalize(discovery, discovery.claim_token or "", cancelled=False)

    # ------------------------------------------------------------------
    # Worker execution
    # ------------------------------------------------------------------

    def claim_and_run(
        self,
        *,
        worker_id: str,
        claim_token: str,
        heartbeat: Callable[[str], bool] | None = None,
    ) -> MediaDiscovery | None:
        """Claim and advance one queued/expired discovery by one bounded step."""

        claimer = getattr(self._repository, "claim_next_media_discovery", None)
        if not callable(claimer):
            raise DiscoveryUnavailable("durable media discovery claim is unavailable")
        claimed = claimer(
            self._clock(),
            worker_id=worker_id,
            claim_token=claim_token,
            lease_seconds=self._lease_seconds,
        )
        if claimed is None:
            return None
        beat = None
        if heartbeat is not None:
            discovery_id = claimed.discovery_id

            def beat() -> bool:  # type: ignore[misc]
                return heartbeat(discovery_id)

        return self.run_claimed(
            claimed.discovery_id,
            worker_id=worker_id,
            claim_token=claim_token,
            heartbeat=beat,
        )

    def run_claimed(
        self,
        discovery_id: str,
        *,
        worker_id: str,
        claim_token: str,
        heartbeat: Callable[[], bool] | None = None,
    ) -> MediaDiscovery:
        """Advance one claimed discovery until a budget, pause or completion boundary."""

        discovery = self._read(discovery_id)
        if discovery is None:
            raise DiscoveryUnavailable("the claimed discovery is no longer readable")
        if discovery.claim_token != claim_token:
            raise DiscoveryConflict(
                "this Worker no longer owns the discovery claim",
                details={"discoveryId": discovery_id},
            )
        if discovery.terminal:
            return discovery
        if discovery.cancel_requested:
            return self._finalize(discovery, claim_token, cancelled=True)
        if discovery.pause_requested:
            return self._publish_paused(discovery, claim_token)
        try:
            runtime = self._load_runtime(discovery.snapshot_id, discovery.snapshot_digest)
            library = self._runtime_library(runtime, discovery.resource_library_id)
            storage = self._guarded_storage(runtime, library.storage_id)
        except DiscoveryError as error:
            return self._fail(discovery, claim_token, error.code)
        return self._advance(discovery, claim_token, storage, library, heartbeat)

    # ------------------------------------------------------------------
    # Internal execution
    # ------------------------------------------------------------------

    def _advance(
        self,
        discovery: MediaDiscovery,
        claim_token: str,
        storage: Storage,
        library,
        heartbeat: Callable[[], bool] | None,
    ) -> MediaDiscovery:
        progress = discovery.progress
        counters = progress.counters
        pending_files = list(progress.pending_files)
        pending_directories = list(progress.pending_directories)
        active_directory = progress.active_directory
        active_cursor = progress.active_cursor
        seen_cursors = list(progress.active_cursors_seen)
        sources = [dict(item) for item in discovery.sources]
        findings = list(progress.findings)
        reasons = {item.reason: item for item in progress.reasons}
        observations: list[DiscoveryObservation] = []
        previous = self._load_observations(discovery.discovery_id)
        stable_since: dict[str, datetime] = {}
        if not pending_files and not pending_directories:
            # A later observation pass re-walks the exact admitted scope so a
            # not-yet-proven stable-size interval can be established.  The walk
            # is idempotent by path and every counter is carried forward.
            pending_files = [
                entry.path
                for entry in progress.scope_entries
                if entry.kind is DiscoveryEntryKind.FILE
            ]
            pending_directories = [
                entry.path
                for entry in progress.scope_entries
                if entry.kind is DiscoveryEntryKind.DIRECTORY
            ]
        started = self._monotonic()
        incomplete = progress.incomplete_reason
        status = DiscoveryStatus.RUNNING
        stop = False
        degraded = False
        # The unstable count describes the *current* observation pass (what is
        # still waiting for stability), not a cumulative tally of every earlier
        # pass; excluded/error counters stay cumulative totals.
        pass_unstable: set[str] = set()

        def bump(reason_value: str, path: str) -> None:
            existing = reasons.get(reason_value)
            if existing is None:
                reasons[reason_value] = DiscoveryReasonCount(reason_value, 1, path)
            else:
                reasons[reason_value] = replace(existing, count=existing.count + 1)

        def note(kind: DiscoveryFindingKind, path: str, why: str, entry, depth: int) -> None:
            if len(findings) >= self._budgets.max_findings:
                return
            findings.append(
                DiscoveryFinding(
                    kind,
                    path,
                    why,
                    entry.size if isinstance(entry, StorageEntry) else None,
                    entry.modified_at if isinstance(entry, StorageEntry) else None,
                    depth,
                )
            )

        def observe(relative: str, depth: int, entry: StorageEntry | None):
            """Classify and observe one candidate; returns the updated counters."""

            nonlocal counters
            if entry is None:
                try:
                    entry = storage.stat(self._join(library.root_path, relative))
                except (StorageError, OSError, ValueError, KeyError):
                    bump(_REASON_UNREADABLE, relative)
                    note(DiscoveryFindingKind.ERROR, relative, _REASON_UNREADABLE, None, depth)
                    counters = replace(counters, error_entries=counters.error_entries + 1)
                    return
            if entry.entry_type is StorageEntryType.SYMLINK:
                bump(_REASON_SYMLINK, relative)
                note(DiscoveryFindingKind.EXCLUDED, relative, _REASON_SYMLINK, entry, depth)
                counters = replace(counters, excluded_entries=counters.excluded_entries + 1)
                return
            if entry.entry_type is not StorageEntryType.FILE:
                bump(_REASON_UNSUPPORTED_TYPE, relative)
                note(
                    DiscoveryFindingKind.EXCLUDED, relative, _REASON_UNSUPPORTED_TYPE, entry, depth
                )
                counters = replace(counters, excluded_entries=counters.excluded_entries + 1)
                return
            verdict = classify_entry(library, relative, entry)
            if verdict is not ScanEntryVerdict.CANDIDATE:
                why = {
                    ScanEntryVerdict.EXCLUDED_EXTENSION: (
                        _REASON_TEMPORARY
                        if entry.name.lower().endswith(_TEMPORARY_SUFFIXES)
                        else _REASON_UNSUPPORTED_EXTENSION
                    ),
                    ScanEntryVerdict.EXCLUDED_RULE: _REASON_EXCLUDED_RULE,
                    ScanEntryVerdict.NOT_INCLUDED: _REASON_NOT_INCLUDED,
                    ScanEntryVerdict.UNSUPPORTED_TYPE: _REASON_UNSUPPORTED_TYPE,
                }[verdict]
                bump(why, relative)
                note(DiscoveryFindingKind.EXCLUDED, relative, why, entry, depth)
                counters = replace(counters, excluded_entries=counters.excluded_entries + 1)
                return
            observed = source_fingerprint(library.storage_id, library.library_id, entry)
            if observed.state is not OccurrenceState.VERIFIED or observed.value is None:
                bump(_REASON_UNREADABLE, relative)
                note(DiscoveryFindingKind.ERROR, relative, _REASON_UNREADABLE, entry, depth)
                counters = replace(counters, error_entries=counters.error_entries + 1)
                return
            now = self._clock()
            prior = previous.get(relative)
            verdict = stability_verdict(
                library,
                entry,
                now=now,
                previous=prior,
                stable_since=stable_since.get(relative),
                observed_value=observed.value,
            )
            prior_since = prior.stable_since if prior is not None else None
            if verdict is StabilityVerdict.STABLE:
                resolved_since = (
                    stable_since.get(relative)
                    or prior_since
                    or (prior.observed_at if prior is not None else now)
                )
            elif (
                verdict is StabilityVerdict.UNSTABLE_SIZE
                and prior is not None
                and prior.matches(entry, observed.value)
            ):
                # The observable identity is unchanged; the interval keeps
                # running from the first unchanged observation.
                resolved_since = stable_since.get(relative) or prior_since or prior.observed_at
            else:
                # A changed source (or a first observation) starts no interval.
                resolved_since = None
            observations.append(
                DiscoveryObservation(
                    relative,
                    entry.size,
                    entry.modified_at,
                    observed.value,
                    now,
                    resolved_since,
                )
            )
            if verdict is StabilityVerdict.STABLE:
                sources.append(self._source_identity(library, entry, relative, observed, now))
                counters = replace(counters, primary_sources=counters.primary_sources + 1)
                note(
                    DiscoveryFindingKind.PRIMARY, relative, "eligible_primary_source", entry, depth
                )
            else:
                why = {
                    StabilityVerdict.UNSTABLE_AGE: _REASON_UNSTABLE_AGE,
                    StabilityVerdict.UNSTABLE_SIZE: _REASON_UNSTABLE_SIZE,
                    StabilityVerdict.UNSTABLE_CHANGED: _REASON_CHANGED,
                }[verdict]
                bump(why, relative)
                note(DiscoveryFindingKind.UNSTABLE, relative, why, entry, depth)
                pass_unstable.add(relative)

        while not stop:
            if heartbeat is not None and not heartbeat():
                return self._publish_paused(discovery, claim_token, "worker claim lost")
            elapsed = self._monotonic() - started
            if elapsed >= self._remaining_active(counters):
                counters = replace(counters, active_seconds=counters.active_seconds + elapsed)
                incomplete = DiscoveryIncompleteReason.TIME_LIMIT
                status = DiscoveryStatus.PARTIAL_SUCCESS
                break
            if counters.visited_entries >= self._budgets.max_visited_entries:
                incomplete = DiscoveryIncompleteReason.ENTRY_LIMIT
                status = DiscoveryStatus.PARTIAL_SUCCESS
                break
            if counters.visited_directories >= self._budgets.max_visited_directories:
                incomplete = DiscoveryIncompleteReason.DIRECTORY_LIMIT
                status = DiscoveryStatus.PARTIAL_SUCCESS
                break
            if counters.page_fetches >= self._budgets.max_page_fetches:
                incomplete = DiscoveryIncompleteReason.PAGE_LIMIT
                status = DiscoveryStatus.PARTIAL_SUCCESS
                break
            if pending_files:
                observe(pending_files.pop(0), 0, None)
                if self._over_primary_limit(sources, bump, note):
                    incomplete = DiscoveryIncompleteReason.PRIMARY_LIMIT
                    status = DiscoveryStatus.PARTIAL_SUCCESS
                    break
                continue
            if active_directory is None:
                if not pending_directories:
                    if not degraded:
                        status = DiscoveryStatus.COMPLETED
                    break
                active_directory = pending_directories.pop(0)
                active_cursor = None
                seen_cursors = []
            directory = active_directory
            page, failure, cursor_problem = self._list_page(
                storage, library, directory, active_cursor
            )
            counters = replace(counters, page_fetches=counters.page_fetches + 1)
            if failure is not None or cursor_problem is not None:
                why = cursor_problem or _REASON_UNREADABLE
                bump(why, directory)
                note(DiscoveryFindingKind.ERROR, directory, why, None, 0)
                counters = replace(counters, error_entries=counters.error_entries + 1)
                incomplete = (
                    DiscoveryIncompleteReason.CURSOR_REPEATED
                    if cursor_problem is not None
                    else DiscoveryIncompleteReason.READ_FAILURE
                )
                status = DiscoveryStatus.PARTIAL_SUCCESS
                degraded = True
                active_directory = None
                active_cursor = None
                seen_cursors = []
                continue
            counters = replace(counters, visited_directories=counters.visited_directories + 1)
            depth = directory.count("/") + 1 if directory else 0
            for raw in tuple(getattr(page, "entries", ())):
                counters = replace(counters, visited_entries=counters.visited_entries + 1)
                if not isinstance(raw, StorageEntry):
                    bump(_REASON_UNSAFE_ENTRY, directory)
                    continue
                relative = self._relative(raw.path, library.root_path)
                if relative is None:
                    bump(_REASON_UNSAFE_ENTRY, raw.path)
                    note(DiscoveryFindingKind.ERROR, raw.path, _REASON_UNSAFE_ENTRY, raw, depth)
                    counters = replace(counters, error_entries=counters.error_entries + 1)
                    continue
                if raw.entry_type is StorageEntryType.DIRECTORY:
                    if excluded_directory(library, relative, raw):
                        bump(_REASON_EXCLUDED_RULE, relative)
                        note(
                            DiscoveryFindingKind.EXCLUDED,
                            relative,
                            _REASON_EXCLUDED_RULE,
                            raw,
                            depth,
                        )
                        counters = replace(counters, excluded_entries=counters.excluded_entries + 1)
                        continue
                    if not directory_may_match(library.include_rules, relative):
                        bump(_REASON_NOT_INCLUDED, relative)
                        note(
                            DiscoveryFindingKind.EXCLUDED,
                            relative,
                            _REASON_NOT_INCLUDED,
                            raw,
                            depth,
                        )
                        counters = replace(counters, excluded_entries=counters.excluded_entries + 1)
                        continue
                    if library.max_depth is not None and depth >= library.max_depth:
                        bump(_REASON_DEPTH, relative)
                        note(DiscoveryFindingKind.EXCLUDED, relative, _REASON_DEPTH, raw, depth)
                        counters = replace(counters, excluded_entries=counters.excluded_entries + 1)
                        continue
                    if depth + 1 > self._budgets.max_depth:
                        # This is the Task's own safety budget, measured below
                        # each selected folder, not the configured library
                        # depth.  A subtree the safety bound cuts off was
                        # never reached, so the walk is honestly incomplete:
                        # it must never be published as a completed scope or
                        # finalize into a truncated prefix.  The configured
                        # library-root depth stays a separate, explainable
                        # exclusion above.
                        bump(_REASON_SAFETY_DEPTH, relative)
                        note(
                            DiscoveryFindingKind.TRUNCATED,
                            relative,
                            _REASON_SAFETY_DEPTH,
                            raw,
                            depth,
                        )
                        counters = replace(counters, excluded_entries=counters.excluded_entries + 1)
                        incomplete = DiscoveryIncompleteReason.SAFETY_DEPTH_LIMIT
                        status = DiscoveryStatus.PARTIAL_SUCCESS
                        stop = True
                        break
                    pending_directories.append(relative)
                    continue
                observe(relative, depth, raw)
                if self._over_primary_limit(sources, bump, note):
                    incomplete = DiscoveryIncompleteReason.PRIMARY_LIMIT
                    status = DiscoveryStatus.PARTIAL_SUCCESS
                    stop = True
                    break
            if stop:
                break
            next_cursor = getattr(page, "next_cursor", None)
            if next_cursor:
                if next_cursor in seen_cursors:
                    bump(_REASON_CURSOR, directory)
                    note(DiscoveryFindingKind.ERROR, directory, _REASON_CURSOR, None, depth)
                    counters = replace(counters, error_entries=counters.error_entries + 1)
                    incomplete = DiscoveryIncompleteReason.CURSOR_REPEATED
                    status = DiscoveryStatus.PARTIAL_SUCCESS
                    degraded = True
                    active_directory = None
                    active_cursor = None
                    seen_cursors = []
                    continue
                seen_cursors.append(next_cursor)
                active_cursor = next_cursor
                continue
            active_directory = None
            active_cursor = None
            seen_cursors = []

        counters = replace(
            counters,
            active_seconds=counters.active_seconds + (self._monotonic() - started),
            primary_sources=len(sources),
            unstable_entries=len(pass_unstable),
        )
        if status is DiscoveryStatus.COMPLETED:
            if discovery.cancel_requested:
                return self._cancel(discovery)
            if discovery.pause_requested:
                return self._publish_paused(discovery, claim_token)
            if counters.unstable_entries:
                # The whole scope was visited, but some candidates are not yet
                # proven stable.  That is a distinct, safely continuable outcome
                # -- never a completed discovery and never a fabricated interval.
                status = DiscoveryStatus.WAITING_STABILITY
        if (
            status is DiscoveryStatus.PARTIAL_SUCCESS
            and incomplete is DiscoveryIncompleteReason.NONE
        ):
            incomplete = DiscoveryIncompleteReason.READ_FAILURE
        if status is DiscoveryStatus.COMPLETED and not sources:
            # An empty and an all-excluded scope are different truthful outcomes;
            # neither is an incomplete traversal.
            phase = "empty_excluded" if counters.excluded_entries else "empty"
        elif status is DiscoveryStatus.WAITING_STABILITY:
            phase = "waiting_stability"
        else:
            phase = {
                DiscoveryStatus.COMPLETED: "completed",
                DiscoveryStatus.PARTIAL_SUCCESS: "partial",
            }.get(status, "running")
        updated = replace(
            discovery,
            status=status,
            version=discovery.version + 1,
            sources=tuple(sources),
            updated_at=self._clock(),
            error=None,
            progress=DiscoveryProgress(
                phase,
                progress.scope_entries,
                counters,
                incomplete,
                tuple(findings),
                tuple(reasons.values()),
                tuple(pending_files),
                tuple(pending_directories),
                active_directory,
                active_cursor,
                tuple(seen_cursors),
                self._phase_message(status, incomplete),
            ),
        )
        # A finished observation is never frozen automatically.  Completing a
        # walk does not make an executable subset: the operator must explicitly
        # finalize the reviewed findings, and an incomplete walk especially must
        # never silently become an executable first-N prefix.
        persisted = self._persist(
            updated, expected_version=discovery.version, observations=tuple(observations)
        )
        # A non-terminal step yields its claim so the resident Worker can
        # continue the same durable scope on its next pass.  The stage is zero
        # mutation and every publication is a version CAS, so a yielded claim
        # can never duplicate a finding or a source.
        self._release_claim(persisted.discovery_id, claim_token)
        return persisted

    def _release_claim(self, discovery_id: str, claim_token: str) -> None:
        releaser = getattr(self._repository, "release_media_discovery_claim", None)
        if callable(releaser) and claim_token:
            try:
                releaser(discovery_id, claim_token)
            except Exception:
                # A claim that cannot be released simply expires on its lease;
                # the durable progress already published is unaffected.
                pass

    def _over_primary_limit(self, sources, bump, note) -> bool:
        if len(sources) <= self._budgets.max_primary_sources:
            return False
        overflow = sources.pop()
        path = str(overflow.get("path", ""))
        bump(_REASON_UNSAFE_ENTRY, path)
        note(DiscoveryFindingKind.TRUNCATED, path, "primary_source_limit_exceeded", None, 0)
        return True

    def _load_observations(self, discovery_id: str) -> dict[str, ObservedSource]:
        reader = getattr(self._repository, "list_media_discovery_observations", None)
        if not callable(reader):
            return {}
        values = reader(discovery_id, limit=500)
        return {
            value.path: ObservedSource(
                value.path,
                value.size,
                value.modified_at,
                value.fingerprint,
                value.observed_at,
                value.stable_since,
            )
            for value in values
        }

    def _list_page(self, storage: Storage, library, directory: str, cursor: str | None):
        path = self._join(library.root_path, directory)
        try:
            page = storage.list_page(path, limit=self._budgets.page_limit, cursor=cursor)
        except StorageError:
            return None, "storage_error", None
        except (OSError, ValueError, KeyError):
            return None, "storage_error", None
        if page is None:
            return None, "storage_error", None
        next_cursor = getattr(page, "next_cursor", None)
        if next_cursor is not None:
            if not isinstance(next_cursor, str) or not next_cursor:
                return None, None, _REASON_CURSOR
            if len(next_cursor.encode("utf-8")) > self._budgets.max_cursor_bytes:
                return None, None, _REASON_CURSOR
        return page, None, None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _remaining_active(self, counters: DiscoveryCounters) -> float:
        return max(0.0, self._budgets.max_active_seconds - counters.active_seconds)

    def _source_identity(self, library, entry: StorageEntry, relative: str, observed, now):
        storage_path = entry.path or self._join(library.root_path, relative)
        filename = entry.name or storage_path.rsplit("/", 1)[-1]
        extension = entry_extension(entry) or "media"
        occurrence = occurrence_id_for(
            library.storage_id, library.library_id, storage_path, observed.value
        )
        file_id = hashlib.sha256(
            json.dumps(
                {
                    "resourceLibraryId": library.library_id,
                    "storageId": library.storage_id,
                    "path": storage_path,
                    "fingerprint": observed.value,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        identity = ManualSourceIdentity(
            file_id,
            library.storage_id,
            library.library_id,
            storage_path,
            filename,
            extension,
            entry.size,
            entry.modified_at,
            now,
            now,
            now,
            "ready",
            None,
            occurrence,
            observed.value,
            observed.algorithm,
            observed.evidence,
            OccurrenceState.VERIFIED.value,
        )
        return identity.document()

    def _active_pin(self) -> tuple[str, str]:
        resolver = getattr(self._intent_service, "_active_snapshot", None)
        if callable(resolver):
            snapshot = resolver()
            return snapshot.snapshot_id, snapshot.digest
        raise DiscoveryUnavailable("the pinned Active configuration is unavailable")

    def _load_runtime(self, snapshot_id: str, snapshot_digest: str):
        if self._runtime_resolver is not None:
            try:
                try:
                    runtime = self._runtime_resolver(snapshot_id, snapshot_digest)
                except TypeError:
                    runtime = self._runtime_resolver()
            except DiscoveryError:
                raise
            except Exception as error:
                raise DiscoveryUnavailable(
                    "the pinned Active configuration snapshot is unavailable or unreadable",
                    details={"reason": type(error).__name__},
                ) from error
        elif self._configuration_service is not None:
            try:
                self._configuration_service.validate_runtime_snapshot(snapshot_id, snapshot_digest)
                revision = self._configuration_service.require(snapshot_id)
                self._configuration_service.verify_integrity(revision)
                from mediaflow.infrastructure.runtime_configuration import (
                    load_managed_runtime_configuration,
                    with_managed_snapshot,
                )

                database_path = self._configuration_service.bootstrap_database_path or str(
                    getattr(self._configuration_service.repository, "database_path", "")
                )
                runtime = with_managed_snapshot(
                    load_managed_runtime_configuration(
                        revision.document, bootstrap_database_path=database_path
                    ),
                    snapshot_id=snapshot_id,
                    digest=snapshot_digest,
                )
            except DiscoveryError:
                raise
            except Exception as error:
                raise DiscoveryUnavailable(
                    "the pinned Active configuration snapshot is unavailable or unreadable",
                    details={"reason": type(error).__name__},
                ) from error
        elif self._configuration is not None:
            runtime = self._configuration
        else:
            raise DiscoveryUnavailable("media discovery runtime configuration is unavailable")
        if isinstance(runtime, Mapping) or not hasattr(runtime, "strategy"):
            raise DiscoveryUnavailable("media discovery requires a normalized managed snapshot")
        authority = getattr(runtime, "configuration_authority", "MANAGED")
        if (
            authority != "MANAGED"
            or getattr(runtime, "configuration_snapshot_id", None) != snapshot_id
            or getattr(runtime, "configuration_snapshot_digest", None) != snapshot_digest
        ):
            raise DiscoveryUnavailable(
                "media discovery cannot use a draft, JSON bootstrap, or later Active configuration",
                details={"authority": authority},
            )
        return runtime

    def _runtime_library(self, runtime, resource_library_id: str):
        matches = tuple(
            value
            for value in getattr(runtime, "resource_libraries", ())
            if getattr(value, "library_id", None) == resource_library_id
        )
        if len(matches) != 1 or not getattr(matches[0], "enabled", False):
            raise DiscoveryError(
                "the selected ResourceLibrary is unavailable in the pinned configuration",
                code="resource_library_not_found",
                status=404,
                next_action="refresh Files and choose an enabled ResourceLibrary",
            )
        library = matches[0]
        storage = next(
            (
                item
                for item in getattr(runtime, "storage_definitions", ())
                if getattr(item, "storage_id", None) == library.storage_id
            ),
            None,
        )
        if storage is None or getattr(storage, "enabled", True) is False:
            raise DiscoveryUnavailable(
                "the selected ResourceLibrary Storage is unavailable",
                details={"storageId": library.storage_id},
            )
        return library

    def _guarded_storage(self, runtime, storage_id: str):
        if self._storage_factory is not None:
            try:
                values = self._storage_factory(runtime, {storage_id})
            except TypeError:
                values = self._storage_factory({storage_id})
            result = dict(values)
        elif callable(getattr(runtime, "create_storages", None)):
            result = dict(
                runtime.create_storages(external=self._storages, storage_ids={storage_id})
            )
        else:
            result = dict(self._storages)
        storage = result.get(storage_id)
        if storage is None:
            raise DiscoveryUnavailable(
                "a configured Storage required by this discovery is unavailable",
                details={"storageId": storage_id},
            )
        if getattr(storage, "storage_id", storage_id) != storage_id:
            raise DiscoveryUnavailable("the selected Storage adapter does not match the pin")
        return _DiscoveryReadOnlyStorage(storage)

    def _resolve_entry_kind(self, storage: Storage, library, entry: DiscoveryScopeEntry):
        path = self._join(library.root_path, entry.path)
        try:
            observed = storage.stat(path)
        except StorageError as error:
            code = getattr(getattr(error, "code", None), "value", "unknown")
            if code == "not_found":
                raise DiscoveryError(
                    "a selected source no longer exists",
                    code="source_missing",
                    status=404,
                    next_action="refresh Files and select the current scope again",
                    details={"relativePath": entry.path},
                ) from error
            raise DiscoveryUnavailable(
                "the selected source Storage is unavailable",
                details={"relativePath": entry.path, "reason": code},
            ) from error
        except (OSError, ValueError, KeyError) as error:
            raise DiscoveryUnavailable(
                "the selected source Storage is unavailable",
                details={"relativePath": entry.path, "reason": type(error).__name__},
            ) from error
        if not isinstance(observed, StorageEntry):
            raise DiscoveryError(
                "the selected source has an unsupported entry type",
                code="source_unsupported",
                status=409,
                next_action="select a folder or an ordinary file inside the ResourceLibrary",
                details={"relativePath": entry.path},
            )
        if observed.entry_type is StorageEntryType.SYMLINK:
            raise DiscoveryError(
                "a symbolic link is never organized",
                code="source_symlink",
                status=409,
                next_action="select the real folder or file inside the ResourceLibrary",
                details={"relativePath": entry.path},
            )
        if observed.entry_type is StorageEntryType.DIRECTORY:
            return DiscoveryScopeEntry(entry.path, DiscoveryEntryKind.DIRECTORY)
        if observed.entry_type is StorageEntryType.FILE:
            return DiscoveryScopeEntry(entry.path, DiscoveryEntryKind.FILE)
        raise DiscoveryError(
            "the selected source has an unsupported entry type",
            code="source_unsupported",
            status=409,
            next_action="select a folder or an ordinary file inside the ResourceLibrary",
            details={"relativePath": entry.path},
        )

    def _finalize(
        self, discovery: MediaDiscovery, claim_token: str, *, cancelled: bool = False
    ) -> MediaDiscovery:
        """Freeze the discovered sources and hand them to the existing admission."""

        sources = tuple(ManualSourceIdentity.from_document(value) for value in discovery.sources)
        now = self._clock()
        if cancelled:
            # A cooperative cancellation is a truthful terminal outcome, not a
            # failure: known findings are preserved and no authority is created.
            return self._cancel(discovery)
        if not sources:
            return self._fail(discovery, claim_token, "selection_empty")
        creator = getattr(self._intent_service, "create_from_sources", None)
        if not callable(creator):
            return self._fail(discovery, claim_token, "intent_unavailable")
        try:
            intent = creator(
                sources,
                actor=discovery.actor,
                snapshot_id=discovery.snapshot_id,
                snapshot_digest=discovery.snapshot_digest,
                pinned_snapshot=True,
            )
        except ManualIntentError as error:
            return self._fail(discovery, claim_token, error.code)
        updated = replace(
            discovery,
            status=(
                DiscoveryStatus.PARTIAL_SUCCESS
                if discovery.progress.incomplete_reason is not DiscoveryIncompleteReason.NONE
                else DiscoveryStatus.COMPLETED
            ),
            version=discovery.version + 1,
            sources=tuple(source.document() for source in sources),
            intent_id=intent.intent_id,
            frozen_at=now,
            claim_worker_id=None,
            claim_token=None,
            claim_expires_at=None,
            updated_at=now,
            error=None,
            progress=replace(
                discovery.progress,
                phase="frozen",
                message=(
                    "the discovered source list is frozen; a separate exact Preview and a "
                    "confirmed execution are still required"
                ),
            ),
        )
        return self._persist(updated, expected_version=discovery.version)

    def _cancel(self, discovery: MediaDiscovery) -> MediaDiscovery:
        """Record a cooperative cancellation that preserves every known finding."""

        now = self._clock()
        updated = replace(
            discovery,
            status=DiscoveryStatus.CANCELLED,
            version=discovery.version + 1,
            claim_worker_id=None,
            claim_token=None,
            claim_expires_at=None,
            updated_at=now,
            progress=replace(
                discovery.progress,
                phase="cancelled",
                incomplete_reason=DiscoveryIncompleteReason.CANCELLED,
                message=(
                    "discovery was cancelled cooperatively; known findings are preserved and "
                    "no execution authority was created"
                ),
            ),
        )
        return self._persist(updated, expected_version=discovery.version)

    def _publish_paused(
        self, discovery: MediaDiscovery, claim_token: str, message: str = ""
    ) -> MediaDiscovery:
        now = self._clock()
        updated = replace(
            discovery,
            status=DiscoveryStatus.PAUSED,
            version=discovery.version + 1,
            claim_worker_id=None,
            claim_token=None,
            claim_expires_at=None,
            updated_at=now,
            progress=replace(
                discovery.progress,
                phase="paused",
                message=message
                or "discovery is paused; findings and counters are durable and safe to continue",
            ),
        )
        return self._persist(updated, expected_version=discovery.version)

    def _fail(self, discovery: MediaDiscovery, claim_token: str, code: str) -> MediaDiscovery:
        now = self._clock()
        updated = replace(
            discovery,
            status=DiscoveryStatus.FAILED,
            version=discovery.version + 1,
            claim_worker_id=None,
            claim_token=None,
            claim_expires_at=None,
            updated_at=now,
            error=code[:MAX_DISCOVERY_TEXT_LENGTH],
            progress=replace(
                discovery.progress,
                phase="failed",
                message="discovery could not continue under its pinned configuration",
            ),
        )
        return self._persist(updated, expected_version=discovery.version)

    def _request_control(
        self,
        discovery_id: str,
        *,
        actor: str,
        expected_version: int,
        pause: bool,
    ) -> MediaDiscovery:
        actor = self._actor(actor)
        discovery = self._require_version(discovery_id, expected_version)
        if discovery.terminal:
            raise DiscoveryError(
                "a finished discovery cannot be controlled",
                code="discovery_not_open",
                status=409,
                next_action="start a new bounded discovery from Files",
            )
        now = self._clock()
        if pause:
            if discovery.pause_requested:
                return discovery
            updated = replace(
                discovery,
                pause_requested=True,
                version=discovery.version + 1,
                updated_at=now,
                progress=replace(
                    discovery.progress,
                    message=(
                        "a cooperative pause was requested; the Worker stops at a safe boundary"
                    ),
                ),
            )
        else:
            if discovery.cancel_requested:
                return discovery
            updated = replace(
                discovery,
                cancel_requested=True,
                version=discovery.version + 1,
                updated_at=now,
                progress=replace(
                    discovery.progress,
                    message=(
                        "a cooperative cancellation was requested; known findings are preserved "
                        "and no execution authority is created"
                    ),
                ),
            )
        return self._persist(updated, expected_version=expected_version)

    def _require_version(self, discovery_id: str, expected_version: int) -> MediaDiscovery:
        if (
            isinstance(expected_version, bool)
            or not isinstance(expected_version, int)
            or expected_version < 1
        ):
            raise DiscoveryError(
                "the expected discovery version is invalid",
                code="malformed_request",
                next_action="reload the discovery and retry",
            )
        discovery = self.get(discovery_id)
        if discovery.version != expected_version:
            raise DiscoveryConflict(
                "the discovery changed before this action was applied",
                details={
                    "discoveryId": discovery_id,
                    "currentVersion": discovery.version,
                },
            )
        return discovery

    def _persist(
        self,
        discovery: MediaDiscovery,
        *,
        expected_version: int,
        observations: tuple[DiscoveryObservation, ...] = (),
    ) -> MediaDiscovery:
        recorder = getattr(self._repository, "record_media_discovery_progress", None)
        if callable(recorder):
            return recorder(discovery, expected_version=expected_version, observations=observations)
        updater = getattr(self._repository, "update_media_discovery", None)
        if callable(updater):
            return updater(discovery, expected_version=expected_version)
        raise DiscoveryUnavailable("durable media discovery storage is unavailable")

    def _read(self, discovery_id: str) -> MediaDiscovery | None:
        reader = getattr(self._repository, "get_media_discovery", None)
        if not callable(reader):
            return None
        return reader(discovery_id)

    @staticmethod
    def _actor(value: object) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise DiscoveryError(
                "the discovery actor is invalid",
                code="invalid_actor",
                next_action="reload the current session and retry",
            )
        return value

    @staticmethod
    def _valid_scope_id(value: object) -> bool:
        import re

        return isinstance(value, str) and bool(
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}", value)
        )

    @staticmethod
    def _join(root: str, relative: str) -> str:
        root_value = (root or "").strip("/")
        if not root_value:
            return relative
        return f"{root_value}/{relative}" if relative else root_value

    @staticmethod
    def _relative(path: str, root: str) -> str | None:
        """The ResourceLibrary-relative path, or None when the entry escaped."""

        value = (path or "").strip("/")
        root_value = (root or "").strip("/")
        if not root_value:
            return value
        if value == root_value:
            return ""
        if value.startswith(root_value + "/"):
            return value[len(root_value) + 1 :]
        return None

    @staticmethod
    def _phase_message(status: DiscoveryStatus, incomplete: DiscoveryIncompleteReason) -> str:
        if status is DiscoveryStatus.COMPLETED:
            return "bounded discovery completed the whole admitted scope"
        if status is DiscoveryStatus.WAITING_STABILITY:
            return (
                "the whole scope was visited, but some sources are not yet proven stable; "
                "continue the same discovery once their size/time has stopped changing"
            )
        if status is DiscoveryStatus.PARTIAL_SUCCESS:
            return f"bounded discovery stopped at a limit: {incomplete.value}"
        return "bounded discovery is running"


class _DiscoveryReadOnlyStorage:
    """Delegate Storage reads and reject every mutation before it can reach an adapter."""

    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    @property
    def storage_id(self) -> str:
        return self._storage.storage_id

    @property
    def name(self) -> str:
        return self._storage.name

    @property
    def read_only(self) -> bool:
        return True

    @property
    def capabilities(self):
        from mediaflow.domain.storage import StorageCapabilities

        return StorageCapabilities()

    def list(self, path: str):
        return self._storage.list(path)

    def list_page(self, path: str, *, limit: int, cursor: str | None = None):
        return self._storage.list_page(path, limit=limit, cursor=cursor)

    def stat(self, path: str):
        return self._storage.stat(path)

    def exists(self, path: str) -> bool:
        return self._storage.exists(path)

    def read(self, path: str):
        raise _DiscoveryMutationError("discovery is metadata-only and never reads content")

    def write(self, path: str, data, *, overwrite: bool = False) -> None:
        raise _DiscoveryMutationError("discovery never mutates Storage")

    def create_directory(self, path: str) -> None:
        raise _DiscoveryMutationError("discovery never mutates Storage")

    def move(self, source: str, target: str, *, overwrite: bool = False) -> None:
        raise _DiscoveryMutationError("discovery never mutates Storage")

    def copy(self, source: str, target: str, *, overwrite: bool = False) -> None:
        raise _DiscoveryMutationError("discovery never mutates Storage")

    def delete(self, path: str) -> None:
        raise _DiscoveryMutationError("discovery never mutates Storage")

    def hard_link(self, source: str, target: str) -> None:
        raise _DiscoveryMutationError("discovery never mutates Storage")

    def soft_link(self, source: str, target: str) -> None:
        raise _DiscoveryMutationError("discovery never mutates Storage")


class _DiscoveryMutationError(RuntimeError):
    """Raised before a discovery-stage Storage mutation can reach an adapter."""
