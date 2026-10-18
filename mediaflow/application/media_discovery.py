"""Bounded, durable, metadata-only discovery of a selected ResourceLibrary scope.

This is the Slice 44 RO-6 application boundary.  The Web submits only an enabled
ResourceLibrary identity plus exact ResourceLibrary-relative folder/file paths;
this service resolves the real entry types, the pinned immutable Active
configuration, the Storage adapter, the concrete budgets and every eligible
primary source from live Storage observations.

Safety invariants:

* the whole stage is **metadata only** -- ``stat``/``list_page`` through the
  existing read-only Storage guard; no content read, no hash, no Provider call,
  no per-file catalog lookup and no mutation;
* discovery creates **no execution authority**.  Finalizing only freezes an
  ordinary deduplicated ``ManualSourceIdentity`` list and hands it to the
  existing ``create_from_sources`` admission, which still requires a separate
  exact Preview and an explicitly confirmed execution;
* budgets are persisted with the exact admitted scope and are never reset by
  pause, restart or continue; a limit produces an honest incomplete state and
  never a silently executable first-N prefix.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from mediaflow.application.attachments import AttachmentDiscovery
from mediaflow.application.scan_filters import (
    ObservedSource,
    PrunedAncestorReason,
    ScanEntryVerdict,
    StabilityVerdict,
    classify_entry,
    directory_may_match,
    entry_extension,
    excluded_directory,
    pruned_ancestor,
    stability_verdict,
    stability_wait_seconds,
)
from mediaflow.domain.automation import AutomationTaskDefinition
from mediaflow.domain.manual_organize import (
    ManualIntentError,
    ManualSourceIdentity,
)
from mediaflow.domain.media_discovery import (
    BUDGET_LIMITED_REASONS,
    MAX_DISCOVERY_REFUSALS,
    MAX_DISCOVERY_TEXT_LENGTH,
    DefinitionRunOnceOrigin,
    DiscoveryBudgets,
    DiscoveryConflict,
    DiscoveryCounters,
    DiscoveryEntryKind,
    DiscoveryError,
    DiscoveryFinding,
    DiscoveryFindingKind,
    DiscoveryIncompleteReason,
    DiscoveryObservation,
    DiscoveryOwnershipLost,
    DiscoveryProgress,
    DiscoveryReasonCount,
    DiscoveryScopeEntry,
    DiscoveryStatus,
    DiscoveryUnavailable,
    MediaDiscovery,
    bounded_path,
    canonical_scope,
    deduplicate_scope,
    deduplicate_sources,
    discovery_budget_limited,
    discovery_manifest_incomplete,
    discovery_material_refusal,
    discovery_scope_signature,
    effective_primary_limit,
    is_settlement_status,
)
from mediaflow.domain.organizer import StorageLocation
from mediaflow.domain.preview_analysis import PreviewAnalysisConflict
from mediaflow.domain.source_evidence import (
    OccurrenceState,
    occurrence_id_for,
    source_fingerprint,
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

#: How many times one returning owner re-reads and re-applies the reconciliation
#: rule when a concurrent operator control keeps moving the record.  The loop is
#: bounded because the outcome is already safe: every retry either settles the
#: operator's control with the same bounded work or yields the claim so the next
#: pass continues.  It never spins on a live lock and never overwrites a
#: successor's ownership.
_CONTROL_RECONCILE_ATTEMPTS = 4


class MediaDiscoveryService:
    """Admit, run, control and finalize one bounded selected-scope discovery."""

    def __init__(
        self,
        repository,
        intent_service,
        *,
        configuration_service=None,
        preview_service=None,
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
        self._preview_service = preview_service
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
        admission_request_id: str | None = None,
        auto_prepare: bool = False,
    ) -> MediaDiscovery:
        """Validate the whole submitted scope and durably admit one discovery.

        This performs exactly one bounded ``stat`` per submitted path so the
        real entry type (folder vs ordinary file) is backend authority rather
        than a browser claim.  It never recurses, never enumerates a directory
        and never calls a Provider, so admission stays prompt.

        ``admission_request_id`` is the caller's own identity for this exact
        request.  The immutable Active pin is resolved *here*, at admission
        time, so a browser that rendered an older pin cannot prove which
        admission its POST became.  A caller-supplied identifier can: it is
        durable, it is echoed back and it lets a lost response reconcile
        against the actual admission instead of a guessed binding.
        """

        actor = self._actor(actor)
        if not isinstance(auto_prepare, bool):
            raise DiscoveryError(
                "the preparation flag is invalid",
                code="invalid_request",
                next_action="refresh the creation workspace and start the preparation again",
            )
        admission_request_id = self._admission_request_id(admission_request_id)
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
        submitted_paths = tuple(sorted({entry.path for entry in submitted}))
        # A caller-generated request identity proves only this immutable
        # ResourceLibrary selection. Resolve it before consulting the current
        # Active pin or Storage root so a genuine retry can still read back its
        # original admission after configuration changes.
        if admission_request_id is not None:
            requested = self._reconcile_admission_request(
                actor,
                admission_request_id,
                resource_library_id=resource_library_id,
                submitted_paths=submitted_paths,
                auto_prepare=auto_prepare,
            )
            if requested is not None:
                return requested
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
        # The persisted scope is *set-canonical*: submitting the same set of
        # exact paths in a different order is the same admitted selection, so
        # the durable record (and therefore the frozen manifest) is identical
        # whichever equivalent request won.  Names are never trimmed.
        deduplicated = canonical_scope(deduplicated)
        # Actor/scope/pin-bound admission identity: an identical open
        # submission for the same principal, the same enabled
        # ResourceLibrary/Storage binding, the same deduplicated scope and
        # the same immutable Active pin is reconciled to its durable record
        # instead of admitting a second duplicate walk.  A *terminal* record
        # is never reopened by resubmission — deliberate successor work is
        # always a new discovery.
        reconciliation = self._reconcile_admission(
            actor,
            deduplicated,
            snapshot_id,
            snapshot_digest,
            resource_library_id,
            library.storage_id,
            auto_prepare=auto_prepare,
        )
        if reconciliation is not None:
            # This new request identity converged on the already durable open
            # discovery, so it stays readable by its own ID for reconciliation.
            self._bind_request(admission_request_id, reconciliation)
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
            admission_request_id=admission_request_id,
            auto_prepare=auto_prepare,
        )
        creator = getattr(self._repository, "create_media_discovery", None)
        if not callable(creator):
            raise DiscoveryUnavailable("durable media discovery storage is unavailable")
        try:
            return creator(discovery)
        except DiscoveryConflict:
            # A concurrent equivalent admission won the durable identity race.
            # The correct outcome is the one already durable record, not a
            # duplicate walk: re-read the exact admission identity and return
            # it.  When the winner is not readable as this exact open
            # admission, the conflict is reported rather than guessed away.
            if admission_request_id is not None:
                requested = self._reconcile_admission_request(
                    actor,
                    admission_request_id,
                    resource_library_id=resource_library_id,
                    submitted_paths=submitted_paths,
                    auto_prepare=auto_prepare,
                )
                if requested is not None:
                    return requested
            winner = self._reconcile_admission(
                actor,
                deduplicated,
                snapshot_id,
                snapshot_digest,
                resource_library_id,
                library.storage_id,
                auto_prepare=auto_prepare,
            )
            if winner is not None:
                # The winner was admitted by a concurrent equivalent request
                # with its own identity.  This request was accepted onto that
                # same durable record, so its identity must stay readable too;
                # otherwise its lost-response lookup reports a bounded absence
                # for work that was actually accepted (B43.2-R4-2).
                self._bind_request(admission_request_id, winner)
                return winner
            raise

    def admit_definition_run_once(
        self,
        *,
        definition_id: str,
        actor: str,
        admission_request_id: str | None = None,
        expected_definition_fingerprint: str | None = None,
        expected_revision_id: str | None = None,
        expected_revision_version: int | None = None,
        expected_revision_digest: str | None = None,
    ) -> MediaDiscovery:
        """Admit one definition-bound Run once without a file picker.

        The saved published definition already identifies its ResourceLibrary and
        source sub-scope, so the backend derives the complete admitted scope from
        that definition instead of a browser selection.  The immutable Active pin
        is resolved *here*, so a stale rendered definition cannot silently
        re-pin today's Active.

        The whole scope is the ResourceLibrary root or the definition's safe
        relative sub-scope; the manifest bound is the smaller of the definition
        item ceiling and the existing manual primary bound.  A ceiling above
        that bound is a *legal* definition: the effective bound is applied to
        the actual manifest, so a scope holding fewer eligible sources than the
        bound is discovered and frozen completely.  Only a walk that actually
        reaches the bound without proving exhaustion is refused, because a
        first-N prefix is never a complete manifest.

        The caller may also submit the exact published definition/configuration
        it observed.  That is a *fence*, not a hint: a changed definition
        fingerprint or a repinned Active revision refuses the new admission
        instead of silently binding today's Active to a stale operator intent.
        A reconciled original request is unaffected by a later publication,
        because it reads back the admission it actually created.
        """

        actor = self._actor(actor)
        admission_request_id = self._admission_request_id(admission_request_id)
        if not isinstance(definition_id, str) or not definition_id.strip():
            raise DiscoveryError(
                "Run once requires one published Automation definition",
                code="malformed_selection",
                next_action="open an existing published definition and choose Run once",
            )
        expected_fingerprint = self._expected_fingerprint(expected_definition_fingerprint)
        expected_revision = self._expected_revision(
            expected_revision_id,
            expected_revision_version,
            expected_revision_digest,
        )
        if admission_request_id is not None:
            requested = self._reconcile_admission_request(
                actor,
                admission_request_id,
                resource_library_id=None,
                submitted_paths=None,
                definition_id=definition_id,
            )
            if requested is not None:
                # The request identity proves the *original* admission.  A
                # repeated call that submits a different binding is not a
                # reconciliation but a changed intent reusing another request's
                # identity, so it refuses instead of silently returning the
                # original (which would misreport what the caller asked for).
                self._assert_reconciliation_binding(
                    requested,
                    expected_fingerprint=expected_fingerprint,
                    expected_revision=expected_revision,
                    definition_id=definition_id,
                )
                return requested
        snapshot_id, snapshot_digest = self._active_pin()
        if expected_revision is not None:
            self._assert_expected_revision(snapshot_id, snapshot_digest, expected_revision)
        runtime = self._load_runtime(snapshot_id, snapshot_digest)
        definition = self._runtime_definition(runtime, definition_id)
        if not definition.mode.is_runnable:
            raise DiscoveryError(
                "this definition records a removed Automation mode and cannot be run once",
                code="unsupported_definition_mode",
                status=409,
                next_action=(
                    "remove or correct the unsupported definition configuration; recorded "
                    "history and completed outcomes are preserved"
                ),
            )
        if expected_fingerprint is not None and definition.definition_fingerprint != (
            expected_fingerprint
        ):
            raise DiscoveryError(
                "the published definition changed since this Run once was observed, so the "
                "stale request was not admitted",
                code="definition_stale",
                status=409,
                next_action=(
                    "reload the definition, review its current scope and bounds, then start "
                    "Run once again"
                ),
                details={"definitionChanged": True},
            )
        bound = effective_primary_limit(definition.item_limit)
        # ``bound`` is min(definition ceiling, manual bound).  A ceiling above
        # the manual bound is a legal definition whose *effective* manifest
        # bound is the manual bound; that bound is enforced against the actual
        # walked manifest, never by refusing the definition up front.
        library = self._runtime_library(runtime, definition.resource_library_id)
        storage = self._guarded_storage(runtime, library.storage_id)
        scope_entry = DiscoveryScopeEntry(
            definition.source_scope or "", DiscoveryEntryKind.DIRECTORY
        )
        resolved = self._resolve_entry_kind(storage, library, scope_entry)
        deduplicated = canonical_scope((resolved,))
        origin = DefinitionRunOnceOrigin(
            definition.definition_id,
            definition.name,
            definition.definition_fingerprint,
            snapshot_id,
            self._runtime_snapshot_version(runtime, snapshot_id),
            snapshot_digest,
            library.library_id,
            definition.source_scope,
            definition.item_limit,
            bound,
            definition.mode.value,
            admission_request_id,
        )
        reconciliation = self._reconcile_definition_admission(
            actor,
            definition.definition_id,
            definition.definition_fingerprint,
            snapshot_id,
            snapshot_digest,
        )
        if reconciliation is not None:
            # This new request identity converged on the already durable open
            # Run once, so it stays readable by its own ID for reconciliation.
            self._bind_request(admission_request_id, reconciliation)
            return reconciliation
        now = self._clock()
        progress = DiscoveryProgress(
            "queued",
            deduplicated,
            DiscoveryCounters(),
            DiscoveryIncompleteReason.NONE,
            (),
            (),
            (),
            tuple(entry.path for entry in deduplicated),
            None,
            None,
            (),
            "queued for bounded Run-once discovery by the resident Processing Worker",
        )
        discovery = MediaDiscovery(
            str(uuid4()),
            actor,
            library.library_id,
            library.storage_id,
            snapshot_id,
            snapshot_digest,
            DiscoveryStatus.QUEUED,
            1,
            self._definition_budgets(bound),
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
            admission_request_id=admission_request_id,
            definition_origin=origin,
        )
        creator = getattr(self._repository, "create_media_discovery", None)
        if not callable(creator):
            raise DiscoveryUnavailable("durable media discovery storage is unavailable")
        try:
            return creator(discovery)
        except DiscoveryConflict:
            if admission_request_id is not None:
                requested = self._reconcile_admission_request(
                    actor,
                    admission_request_id,
                    resource_library_id=None,
                    submitted_paths=None,
                    definition_id=definition_id,
                )
                if requested is not None:
                    return requested
            winner = self._reconcile_definition_admission(
                actor,
                definition.definition_id,
                definition.definition_fingerprint,
                snapshot_id,
                snapshot_digest,
            )
            if winner is not None:
                # The concurrent equivalent Run once was admitted under its own
                # request identity; this request converged on the same durable
                # run, so its identity is bound too and its own reconciliation
                # read cannot report a bounded absence (B43.2-R4-2).
                self._bind_request(admission_request_id, winner)
                return winner
            raise

    def _definition_budgets(self, primary_bound: int) -> DiscoveryBudgets:
        """The persisted budgets of one definition-bound Run once.

        Only the primary bound differs from the ordinary discovery budgets, and
        it is the exact effective bound so a later read proves what the run was
        allowed to freeze.
        """

        if primary_bound == self._budgets.max_primary_sources:
            return self._budgets
        return replace(self._budgets, max_primary_sources=primary_bound)

    def _assert_reconciliation_binding(
        self,
        requested: MediaDiscovery,
        *,
        expected_fingerprint: str | None,
        expected_revision: tuple[str, int, str] | None,
        definition_id: str,
    ) -> None:
        """Refuse a repeated request identity that submits a *different* binding.

        The request identity is the caller's proof of the admission it actually
        created.  Reusing it with a changed definition fingerprint or a changed
        observed Active revision is a changed intent wearing another request's
        identity, so the honest outcome is a bounded refusal rather than
        returning the original admission as if it matched the new request.
        """

        origin = requested.definition_origin
        if origin is None or origin.definition_id != definition_id:
            raise DiscoveryError(
                "this admission request identity is already bound to a different Run once",
                code="admission_request_conflict",
                status=409,
                next_action=(
                    "keep this request identity for its original Run once, or start a new "
                    "Run once with a new request identity"
                ),
                details={"requestIdReuse": True},
            )
        if (
            expected_fingerprint is not None
            and origin.definition_fingerprint != expected_fingerprint
        ):
            raise DiscoveryError(
                "this admission request identity already proved a different published "
                "definition, so the changed binding was not admitted",
                code="definition_stale",
                status=409,
                next_action=(
                    "start a new Run once with a new request identity for the changed definition"
                ),
                details={"requestIdReuse": True},
            )
        if expected_revision is not None:
            revision_id, _version, revision_digest = expected_revision
            if (
                origin.configuration_revision_id != revision_id
                or origin.configuration_revision_digest != revision_digest
            ):
                raise DiscoveryError(
                    "this admission request identity already proved a different Active "
                    "configuration, so the changed binding was not admitted",
                    code="configuration_stale",
                    status=409,
                    next_action=(
                        "start a new Run once with a new request identity for the current "
                        "Active configuration"
                    ),
                    details={"requestIdReuse": True},
                )

    def _expected_fingerprint(self, value: object) -> str | None:
        """The optional observed definition fingerprint submitted as a fence."""

        if value is None:
            return None
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise DiscoveryError(
                "the observed definition fingerprint is malformed",
                code="malformed_selection",
                next_action="reload the definition and start Run once again",
            )
        return value

    def _expected_revision(
        self,
        revision_id: object,
        revision_version: object,
        revision_digest: object,
    ) -> tuple[str, int, str] | None:
        """The optional observed Active revision submitted as a fence.

        All three parts are required together: a partial binding could not
        prove which published revision the operator observed, so it is refused
        rather than treated as a weaker hint.
        """

        if revision_id is None and revision_version is None and revision_digest is None:
            return None
        if (
            not isinstance(revision_id, str)
            or not revision_id.strip()
            or isinstance(revision_version, bool)
            or not isinstance(revision_version, int)
            or revision_version < 1
            or not isinstance(revision_digest, str)
            or not revision_digest.strip()
        ):
            raise DiscoveryError(
                "the observed Active revision fence is incomplete or malformed",
                code="malformed_selection",
                next_action="reload the definition and start Run once again",
            )
        return revision_id, revision_version, revision_digest

    def _assert_expected_revision(
        self,
        snapshot_id: str,
        snapshot_digest: str,
        expected: tuple[str, int, str],
    ) -> None:
        """Refuse a stale admission whose observed Active is no longer published."""

        revision_id, _version, revision_digest = expected
        if snapshot_id != revision_id or snapshot_digest != revision_digest:
            raise DiscoveryError(
                "the Active configuration changed since this Run once was observed, so the "
                "stale request was not admitted",
                code="configuration_stale",
                status=409,
                next_action=(
                    "reload the definition and the current Active configuration, then start "
                    "Run once again"
                ),
                details={"configurationChanged": True},
            )

    def _runtime_definition(self, runtime, definition_id: str) -> AutomationTaskDefinition:
        matches = tuple(
            value
            for value in getattr(runtime, "automation_task_definitions", ())
            if getattr(value, "definition_id", getattr(value, "id", None)) == definition_id
        )
        if len(matches) != 1:
            raise DiscoveryError(
                "the requested Automation definition is not in the pinned Active configuration",
                code="definition_not_found",
                status=404,
                next_action=(
                    "publish the definition in the current Active configuration, then run once"
                ),
            )
        definition = matches[0]
        if not isinstance(definition, AutomationTaskDefinition):
            try:
                definition = AutomationTaskDefinition.from_document(definition)
            except (TypeError, ValueError) as error:
                raise DiscoveryError(
                    "the pinned Automation definition cannot be consumed safely",
                    code="definition_invalid",
                    status=409,
                    next_action="validate and publish a corrected definition, then run once",
                ) from error
        if not definition.enabled:
            # A *disabled* schedule is explicitly runnable once: only the
            # schedule is off, not the definition.  The check exists so a
            # definition that is not published at all is distinguished from one
            # whose schedule is merely disabled.
            pass
        return definition

    def _runtime_snapshot_version(self, runtime, snapshot_id: str) -> int:
        """The immutable Active revision version of one Run once.

        The normalized runtime carries the version when the resolver supplied
        it; otherwise it is read from the same managed authority that produced
        the pin, so a resident Worker or a harness resolver that only returns
        the runtime never fabricates a version.  A genuinely unprovable version
        still fails closed.
        """

        version = getattr(runtime, "configuration_snapshot_version", None)
        if isinstance(version, int) and not isinstance(version, bool) and version >= 1:
            return version
        service = self._configuration_service
        if service is not None:
            try:
                revision = service.require(snapshot_id)
            except Exception:
                revision = None
            revision_version = getattr(revision, "version", None)
            if (
                isinstance(revision_version, int)
                and not isinstance(revision_version, bool)
                and revision_version >= 1
            ):
                return revision_version
        raise DiscoveryUnavailable(
            "the pinned Active configuration version is unavailable for Run once"
        )

    def _reconcile_definition_admission(
        self,
        actor: str,
        definition_id: str,
        definition_fingerprint: str,
        snapshot_id: str,
        snapshot_digest: str,
    ) -> MediaDiscovery | None:
        """One already durable *open* Run once for this exact definition pin."""

        finder = getattr(self._repository, "find_open_definition_run_once", None)
        if not callable(finder):
            return None
        return finder(
            actor=actor,
            definition_id=definition_id,
            definition_fingerprint=definition_fingerprint,
            snapshot_id=snapshot_id,
            snapshot_digest=snapshot_digest,
        )

    def _bind_request(self, admission_request_id: str | None, discovery: MediaDiscovery) -> None:
        """Keep every accepted request identity durably readable.

        When a request *converges* on already-open work (its equivalent
        admission exists), the request identity is bound to that same durable
        record, so a lost response for this request reconciles to the run it
        actually created instead of a bounded absence that reads as "no work
        exists".  A request that created its own row is already readable
        through the record's own column.

        The binder enforces the complete principal/request invariant
        (B43.2-R5-1): when another writer has already durably claimed this
        identity for different work, the bind refuses and so must this
        admission — the convergence outcome is a bounded, actionable refusal,
        never a second ``accepted`` answer for one request identity.
        """

        if admission_request_id is None:
            return
        binder = getattr(self._repository, "bind_admission_request", None)
        if not callable(binder):
            return
        try:
            binder(
                actor=discovery.actor,
                admission_request_id=admission_request_id,
                kind="media-discovery",
                target_id=discovery.discovery_id,
                created_at=self._clock(),
            )
        except PreviewAnalysisConflict as error:
            raise DiscoveryError(
                "this discovery request identity is already bound to different "
                "durable work, so this admission was not accepted; reconcile the "
                "original request by its ID or start with a new request identity",
                code="admission_request_conflict",
                status=409,
                next_action=(
                    "keep this request ID for its original admission, or start "
                    "this one with a new request ID"
                ),
                details={"requestIdReuse": True},
            ) from error

    def _reconcile_admission_request(
        self,
        actor: str,
        admission_request_id: str,
        *,
        resource_library_id: str | None,
        submitted_paths: tuple[str, ...] | None,
        auto_prepare: bool = False,
        definition_id: str | None = None,
    ) -> MediaDiscovery | None:
        """The durable admission this exact client request identity created.

        This is proof of the *actual* admission rather than of a rendered
        binding, so a retried request reconciles to its own record even when the
        Active pin or Storage root changed while the response was lost.  A
        repository without the durable lookup (an in-memory test double) simply
        has no proof and reports the honest unknown outcome.

        A request identity is bound to exactly one kind of admission: a Files
        folder/mixed selection or a definition-bound Run once.  Reusing it for
        the other kind, another library, another definition or another selection
        is refused rather than guessed away.
        """

        finder = getattr(self._repository, "find_media_discovery_by_request_id", None)
        if not callable(finder):
            return None
        requested = finder(actor=actor, admission_request_id=admission_request_id)
        if requested is None:
            return None
        origin = requested.definition_origin
        if definition_id is not None:
            if origin is None or origin.definition_id != definition_id:
                raise DiscoveryError(
                    "this Run-once request ID is already bound to a different definition",
                    code="admission_request_conflict",
                    status=409,
                    next_action=(
                        "keep this request ID for its original definition, or start this "
                        "Run once with a new request ID"
                    ),
                    details={"requestIdReuse": True},
                )
            return requested
        if origin is not None:
            raise DiscoveryError(
                "this discovery request ID is already bound to a definition Run once",
                code="admission_request_conflict",
                status=409,
                next_action=(
                    "keep this request ID for its original Run once, or start this selection "
                    "with a new request ID"
                ),
                details={"requestIdReuse": True},
            )
        stored_paths = {entry.path for entry in requested.progress.scope_entries}
        selected_paths = set(submitted_paths or ())
        # A selected directory canonically subsumes any explicitly selected
        # descendants. Use the old persisted entry kinds for that comparison:
        # the current root may have changed or disappeared, and is not proof of
        # what the original request selected.
        stored_directories = tuple(
            entry.path
            for entry in requested.progress.scope_entries
            if entry.kind is DiscoveryEntryKind.DIRECTORY
        )
        selected_paths = {
            path
            for path in selected_paths
            if not any(
                path != directory and path.startswith(directory.rstrip("/") + "/")
                for directory in stored_directories
            )
        }
        if requested.resource_library_id != resource_library_id or selected_paths != stored_paths:
            raise DiscoveryError(
                "this discovery request ID is already bound to a different "
                "ResourceLibrary selection",
                code="admission_request_conflict",
                status=409,
                next_action=(
                    "keep this request ID for its original selection, or start this selection "
                    "with a new request ID"
                ),
                details={"requestIdReuse": True},
            )
        if requested.auto_prepare != auto_prepare:
            raise DiscoveryError(
                "this discovery request ID is already bound to a different creation mode",
                code="admission_request_conflict",
                status=409,
                next_action=(
                    "keep this request ID for its original creation mode, or start this "
                    "selection with a new request ID"
                ),
                details={"requestIdReuse": True},
            )
        return requested

    def _reconcile_admission(
        self,
        actor: str,
        scope: tuple[DiscoveryScopeEntry, ...],
        snapshot_id: str,
        snapshot_digest: str,
        resource_library_id: str,
        storage_id: str,
        *,
        auto_prepare: bool = False,
    ) -> MediaDiscovery | None:
        """Find one already durable open discovery for this exact admission.

        The match is bound to the actor, the *exact ResourceLibrary binding*
        (library identity plus its pinned Storage/root context), the canonical
        deduplicated scope signature and the admitted configuration pin.  A
        lost admission response therefore reconciles to the original durable
        record instead of admitting a duplicate walk, while a different scope,
        a different principal, a different library/Storage binding or a
        repinned Active configuration is always a new admission.  Two enabled
        ResourceLibraries with the same relative path can never answer for
        each other: the relative path alone is not the source identity.
        """

        lister = getattr(self._repository, "list_media_discoveries", None)
        signature = discovery_scope_signature(scope)
        # The durable identity lookup is the authority: an equivalent open
        # admission reconciles even after it left every bounded recent-list
        # window, which a window scan can never guarantee.
        finder = getattr(self._repository, "find_open_media_discovery", None)
        if callable(finder):
            return finder(
                actor=actor,
                resource_library_id=resource_library_id,
                storage_id=storage_id,
                snapshot_id=snapshot_id,
                snapshot_digest=snapshot_digest,
                scope_signature=signature,
                auto_prepare=auto_prepare,
            )
        if not callable(lister):
            return None
        # A repository without the durable lookup (an in-memory test double)
        # falls back to the bounded recent window with the same exact match.
        for candidate in lister(actor=actor, limit=50):
            if candidate.terminal or candidate.frozen:
                continue
            if candidate.auto_prepare != auto_prepare:
                continue
            if (
                candidate.resource_library_id != resource_library_id
                or candidate.storage_id != storage_id
            ):
                # A different ResourceLibrary (or a different Storage/root
                # binding for the same relative path) is a different source
                # selection, never the same admitted scope.
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

    def find_by_request_id(self, *, actor: str, admission_request_id: str) -> MediaDiscovery | None:
        """The durable admission one exact client request identity created.

        This is the reconciliation read a lost admission response needs: the
        request identity is generated before the POST, so it proves the *actual*
        admission even when the Active pin or Storage root changed while the
        response was in flight.  A proved absence returns ``None`` (an honest
        unknown outcome), never a guessed binding from a recent-list window.
        """

        finder = getattr(self._repository, "find_media_discovery_by_request_id", None)
        if not callable(finder):
            return None
        return finder(actor=self._actor(actor), admission_request_id=admission_request_id)

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

    def request_analysis(
        self, discovery_id: str, *, actor: str, expected_version: int
    ) -> MediaDiscovery:
        """Re-enter the durable analysis stage after an operator correction.

        A preparation that already linked a read-only plan summary can be
        re-analyzed once the operator has saved a legal correction (for example
        a RecognitionType choice) on its linked intent.  This records one
        versioned request only: the resident Worker re-runs the complete
        production analysis chain under the same pinned configuration and links
        the new exact Preview.  It grants no execution authority and never
        creates a second queue.
        """

        actor = self._actor(actor)
        discovery = self._require_version(discovery_id, expected_version)
        available, code, next_action, pending = self.analysis_availability(discovery)
        if not available and not pending:
            raise DiscoveryError(
                next_action or "this preparation cannot be re-analyzed in its current state",
                code=code or "discovery_not_preparation",
                status=409,
                next_action=next_action or "start a new preparation if the same scope is wanted",
            )
        if pending:
            # A repeated request converges on the analysis already queued: the
            # Worker re-runs the analysis under the same immutable intent.
            return discovery
        now = self._clock()
        updated = replace(
            discovery,
            status=DiscoveryStatus.ANALYZING,
            version=discovery.version + 1,
            # The earlier plan summary is historical once a new analysis is
            # requested: clearing the link keeps the workspace from presenting
            # a superseded plan as the current one.
            preview_id=None,
            updated_at=now,
            error=None,
            progress=replace(
                discovery.progress,
                phase="analyzing",
                message=(
                    "the resident Worker is re-running the complete zero-mutation analysis "
                    "under the same pinned configuration"
                ),
            ),
        )
        return self._persist(updated, expected_version=discovery.version)

    def analysis_availability(
        self, discovery: MediaDiscovery
    ) -> tuple[bool, str | None, str | None, bool]:
        """Whether one preparation may re-run its zero-mutation analysis.

        This is the single predicate the API publishes and ``request_analysis``
        enforces, so an advertised action can never disagree with the real
        admission.  Returns ``(available, refusal_code, next_action, pending)``.
        ``pending`` marks a request that is already queued and simply converges
        on the same work rather than being refused.
        """

        if not discovery.auto_prepare:
            return (
                False,
                "discovery_not_preparation",
                "open the discovery and use its own reviewed finalize action",
                False,
            )
        if discovery.intent_id is None:
            return (
                False,
                "discovery_not_frozen",
                "wait for the bounded discovery to finish, then request the analysis",
                False,
            )
        if discovery.status in {DiscoveryStatus.FAILED, DiscoveryStatus.CANCELLED}:
            return (
                False,
                "discovery_already_finished",
                "start a new preparation if the same scope is still wanted",
                False,
            )
        if discovery.pause_requested or discovery.cancel_requested:
            return (
                False,
                "discovery_control_pending",
                "refresh the preparation until its control is acknowledged, then request the "
                "analysis again",
                False,
            )
        if discovery.status is DiscoveryStatus.ANALYZING:
            return (False, None, None, True)
        return (True, None, None, False)

    def resume(self, discovery_id: str, *, actor: str, expected_version: int) -> MediaDiscovery:
        """Clear an *acknowledged* cooperative pause so the Worker continues.

        A pause stays cooperative: the resident Worker acknowledges it at its
        next safe boundary and releases the claim in the same transaction.  A
        Continue is only meaningful after that acknowledgement, because only
        then has the interrupted pass's bounded work been settled durably.
        Accepting a Continue while the pause is still pending would let the
        operator's action race the acknowledgement and leave the record with no
        truthful continuation, so the pending stage is refused actionably here
        as well as in the advertised action availability.
        """

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
        if discovery.pause_requested and discovery.status is not DiscoveryStatus.PAUSED:
            # The pause request is durable but the resident Worker has not yet
            # acknowledged it at a safe boundary.  The pending stage is a real
            # transient state, not an error the operator must work around: the
            # acknowledgement is what preserves the interrupted pass's bounded
            # work and releases ownership.  Refusing here changes nothing.
            raise DiscoveryError(
                "the cooperative pause has not been acknowledged yet",
                code="discovery_pause_pending",
                status=409,
                next_action=(
                    "wait for the resident Processing Worker to acknowledge the pause at "
                    "its safe boundary, then continue the same discovery"
                ),
                details={"status": discovery.status.value},
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
        # Resume only clears the operator's own pause request: the operator-owned
        # path never touches the claim columns, so a Worker that is still
        # finishing its safe boundary keeps the exact claim it acquired.
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
        material_refusal = discovery_material_refusal(discovery.progress)
        if material_refusal is not None or (
            discovery.progress.incomplete_reason in BUDGET_LIMITED_REASONS
        ):
            # A budget/safety/cursor/unsafe-entry-limited walk recorded a
            # truncated or unconfined prefix, never a complete scope: freezing
            # it would silently admit a first-N subset as ordinary executable
            # work.  The refusal is durable and monotonic, so an ordinary read
            # failure in another subtree can never re-enable Finalize.  It is
            # reported before the empty-source case because the root cause is
            # the exhausted bound or unsafe entry, not a genuinely empty scope.
            # The honest recovery is a narrowed scope and a new bounded
            # discovery; an ordinary read-failure-only subset is unaffected and
            # keeps its own explicit-review path.
            reason = (material_refusal or discovery.progress.incomplete_reason).value
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
        if discovery.definition_origin is not None:
            # A *definition-derived* Run once must prove a complete manifest of
            # the saved definition scope.  An ordinary read failure (an
            # unreadable subtree or an unobservable named file) leaves the
            # recorded sources a partial subset, so freezing it here would
            # advertise a truncated Automation prefix as executable work.  The
            # strict rule lives at this shared authority boundary, so a direct
            # generic finalize of a definition-origin record is refused exactly
            # like the Run-once route.  The accepted standalone Files selection
            # (no definition origin) keeps its explicit-subset review path.
            strict_refusal = discovery_manifest_incomplete(discovery.progress)
            if strict_refusal is not None:
                raise DiscoveryError(
                    "this Run once did not prove a complete manifest of the definition scope, "
                    "so its findings cannot be frozen",
                    code="discovery_incomplete_manifest",
                    status=409,
                    next_action=(
                        "narrow the definition sourceScope or correct the unreadable source, "
                        "publish it, then start a fresh Run once and discover again"
                    ),
                    details={
                        "incompleteReason": strict_refusal.value,
                        "definitionItemLimit": (
                            discovery.definition_origin.definition_item_limit
                            if discovery.definition_origin
                            else None
                        ),
                        "effectivePrimaryLimit": (
                            discovery.definition_origin.effective_primary_limit
                            if discovery.definition_origin
                            else None
                        ),
                    },
                )
        if not discovery.sources:
            raise DiscoveryError(
                "this discovery found no eligible primary source to freeze",
                code="selection_empty",
                status=409,
                next_action="narrow the selected scope or correct the configured filters",
            )
        return self._finalize(discovery, None)

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
    ) -> MediaDiscovery | None:
        """Claim and advance one queued/expired discovery by one bounded step.

        ``parent_heartbeat`` is the containing processing-Worker's registration
        heartbeat.  A blocked Storage/Provider call inside one advance step can
        otherwise outlive the parent's stale threshold and make a *working*
        resident Worker report unavailable, so a lease keeper keeps both the
        discovery claim and the parent registration live for the whole
        invocation.  The parent signal is liveness evidence only: a fault is
        tolerated and retried on the next interval, and the discovery's own
        claim heartbeat remains the ownership boundary.
        """

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

        if beat is None and parent_heartbeat is None:
            return self.run_claimed(
                claimed.discovery_id,
                worker_id=worker_id,
                claim_token=claim_token,
                heartbeat=beat,
            )
        stopped = threading.Event()

        def keep_alive() -> None:
            interval = max(0.05, min(5.0, self._lease_seconds / 3.0))
            while not stopped.wait(interval):
                try:
                    if beat is not None:
                        beat()
                    if parent_heartbeat is not None:
                        try:
                            parent_heartbeat()
                        except Exception:
                            pass
                except Exception:
                    # A claim-renewal fault stops the keeper; the next in-loop
                    # boundary heartbeat still reports true ownership honestly.
                    return

        keeper = threading.Thread(
            target=keep_alive,
            name=f"media-discovery-lease-{claimed.discovery_id[:12]}",
            daemon=True,
        )
        keeper.start()
        try:
            return self.run_claimed(
                claimed.discovery_id,
                worker_id=worker_id,
                claim_token=claim_token,
                heartbeat=beat,
            )
        finally:
            stopped.set()
            keeper.join(timeout=1)

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
        if discovery.terminal:
            # Already settled by an operator control or a successor Worker: there
            # is nothing this claim may still change, so it stops without writing.
            return discovery
        if discovery.claim_token != claim_token:
            raise DiscoveryOwnershipLost(
                "this Worker no longer owns the discovery claim",
                details={"discoveryId": discovery_id},
            )
        if discovery.cancel_requested:
            return self._cancel(discovery, claim_token)
        if discovery.pause_requested:
            return self._publish_paused(discovery, claim_token)
        if discovery.auto_prepare and discovery.status is DiscoveryStatus.ANALYZING:
            # The bounded walk already froze its reviewed sources into a
            # durable intent.  The Worker now runs the complete production
            # analysis chain through the existing zero-mutation Preview
            # authority and links the exact read-only plan summary.  No
            # execution authority is created.
            return self._analyze(discovery, claim_token)
        try:
            runtime = self._load_runtime(discovery.snapshot_id, discovery.snapshot_digest)
            library = self._runtime_library(runtime, discovery.resource_library_id)
            storage = self._guarded_storage(runtime, library.storage_id)
        except DiscoveryError as error:
            return self._fail(discovery, claim_token, error.code)
        try:
            return self._advance(discovery, claim_token, storage, library, runtime, heartbeat)
        except (DiscoveryConflict, DiscoveryOwnershipLost) as error:
            # Either an operator control (pause/cancel/resume) changed the record
            # while this Worker was walking, or its lease was taken over.  React
            # to the *fresh* durable state at this safe boundary instead of
            # stranding the record, discarding the accepted control, or writing
            # over a successor's ownership.
            #
            # A refused publication carries the bounded work this pass already
            # completed.  A same-owner control change (pause/cancel/resume) is
            # reconciled *with* that work, so an accepted control can never
            # discard the observations, counters and material refusals the live
            # owner had already established.  A lost claim keeps nothing: the
            # successor owns every durable field now.
            return self._settle_after_conflict(discovery_id, claim_token, error)

    def _settle_after_conflict(
        self,
        discovery_id: str,
        claim_token: str,
        refusal: DiscoveryConflict | DiscoveryOwnershipLost,
    ) -> MediaDiscovery:
        """React to a refused stale publication at a safe boundary.

        Ownership loss is deliberately distinguished from a lease lapse or an
        operator version change.  A different persisted claim means another
        Worker owns the walk now, so this owner stops without writing anything.
        A record the operator already settled is returned as-is: that terminal
        outcome is the operator's, and this Worker has nothing left to change.
        Otherwise the claim is still this Worker's, so an accepted pause or
        cancellation is acknowledged *together with* this pass's bounded work,
        and a lapsed lease or a cleared pause simply yields the claim so the
        very next Worker pass continues the same durable scope.

        ``refusal`` carries the fenced projection whose version CAS lost the
        race, and the stability observations written with it.  That work is
        reconciled with the fresh operator-owned record under the exact persisted
        claim: the operator's control flags and lifecycle win, while the same
        owner's counters, findings, manifest, pending traversal, stability
        observations and monotonic material refusals are preserved.  Discarding
        them would reset consumed budgets and let a later continuation silently
        re-walk a scope the operator never narrowed.

        A concurrent control may itself race this reconciliation.  Each retry
        re-reads the fresh record and re-applies the same rule; the bounded loop
        ends by yielding the claim, which leaves the operator's control durable
        and lets the next pass continue instead of stranding the record.

        A settlement projection is never replayed as traversal work.  The latest
        accepted control decides the lifecycle: a pause acknowledgement that lost
        its own CAS to a newer control contributes its bounded counters,
        findings, manifest and refusals, but not its superseded ``paused``
        status.
        """

        attempted = refusal.attempted if isinstance(refusal, DiscoveryConflict) else None
        observations = (
            refusal.attempted_observations if isinstance(refusal, DiscoveryConflict) else ()
        )
        fresh: MediaDiscovery | None = None
        for _ in range(_CONTROL_RECONCILE_ATTEMPTS):
            fresh = self._read(discovery_id)
            if fresh is None:
                raise DiscoveryUnavailable("the claimed discovery is no longer readable")
            if fresh.claim_token != claim_token:
                if fresh.terminal or fresh.cancel_requested:
                    return fresh
                raise DiscoveryOwnershipLost(
                    "this Worker no longer owns the discovery claim",
                    details={"discoveryId": discovery_id},
                )
            if fresh.terminal:
                return fresh
            # The operator owns the control flags and the lifecycle transition;
            # this pass only contributes the bounded work it actually completed,
            # and only when that work belongs to the same immutable scope/pin.
            carried = self._merge_attempted_work(fresh, attempted)
            try:
                if fresh.cancel_requested:
                    return self._cancel(carried, claim_token, observations=observations)
                if fresh.pause_requested:
                    return self._publish_paused(carried, claim_token, observations=observations)
                if self._publication_differs(fresh, carried):
                    # The operator's pause was already acknowledged and then
                    # cleared (or our lease lapsed) *and* this pass completed
                    # bounded work that is not durable yet.  Publish it under the
                    # live claim in the same transaction that releases that
                    # claim, so a Continue never re-walks or resets the work this
                    # pass already established.  A pause that is still pending
                    # acknowledgement never reaches here: Continue is refused
                    # until the acknowledgement has settled the bounded work.
                    return self._settle_control(
                        replace(carried, version=fresh.version + 1),
                        expected_version=fresh.version,
                        claim_token=claim_token,
                        observations=observations,
                    )
            except (DiscoveryConflict, DiscoveryOwnershipLost) as retry:
                # The control state moved again while we reconciled.  Re-read and
                # re-apply the same rule; the attempted work stays with us unless
                # the claim itself was taken over.
                attempted = retry.attempted if isinstance(retry, DiscoveryConflict) else None
                if isinstance(retry, DiscoveryConflict) and retry.attempted_observations:
                    observations = retry.attempted_observations
                continue
            # The claim is still ours but there is nothing new to publish: yield
            # it so the next pickup continues the same durable scope immediately.
            self._release_claim(discovery_id, claim_token)
            return self._read(discovery_id) or fresh
        # The control state kept moving; the operator's own request is durable,
        # so yield the claim and let the next pass continue safely.
        self._release_claim(discovery_id, claim_token)
        return self._read(discovery_id) or fresh

    @staticmethod
    def _merge_attempted_work(
        fresh: MediaDiscovery, attempted: MediaDiscovery | None
    ) -> MediaDiscovery:
        """Keep the live owner's bounded work while the operator keeps control.

        Only progress that belongs to the *same* immutable admitted scope and
        pinned configuration is carried across a refused publication.  Anything
        else (a different pin, a different scope, a stale attempt from another
        owner's record) is discarded, so a control can never be reconciled with
        work that was never admitted for this discovery.

        The operator owns the lifecycle.  A refused *walk* publication carries a
        truthful traversal outcome -- completed, partial success or waiting for
        stability -- so that outcome is preserved together with the counters,
        findings, manifest, pending traversal, observations and monotonic
        material refusals of the same pass.  A refused *control settlement*
        (paused, cancelled or failed) is the previous control's own projection:
        it is never replayed as this pass's traversal outcome, so the latest
        accepted control keeps deciding the lifecycle.  Its bounded work is
        still kept.
        """

        if attempted is None or attempted.discovery_id != fresh.discovery_id:
            return fresh
        if attempted.snapshot_id != fresh.snapshot_id:
            return fresh
        if attempted.snapshot_digest != fresh.snapshot_digest:
            return fresh
        if attempted.resource_library_id != fresh.resource_library_id:
            return fresh
        if attempted.storage_id != fresh.storage_id:
            return fresh
        if discovery_scope_signature(attempted.progress.scope_entries) != (
            discovery_scope_signature(fresh.progress.scope_entries)
        ):
            return fresh
        if is_settlement_status(attempted.status):
            # The latest accepted control decides the lifecycle and its own
            # phase/message; this pass only contributes the work it completed.
            return replace(
                fresh,
                progress=replace(
                    attempted.progress,
                    phase=fresh.progress.phase,
                    message=fresh.progress.message,
                ),
                sources=attempted.sources,
            )
        return replace(
            fresh,
            status=attempted.status,
            progress=attempted.progress,
            sources=attempted.sources,
        )

    @staticmethod
    def _publication_differs(fresh: MediaDiscovery, carried: MediaDiscovery) -> bool:
        """Whether the reconciled work adds anything the durable record lacks."""

        return (
            carried.status is not fresh.status
            or carried.progress != fresh.progress
            or carried.sources != fresh.sources
        )

    # ------------------------------------------------------------------
    # Internal execution
    # ------------------------------------------------------------------

    def _advance(
        self,
        discovery: MediaDiscovery,
        claim_token: str,
        storage: Storage,
        library,
        runtime,
        heartbeat: Callable[[], bool] | None,
    ) -> MediaDiscovery:
        progress = discovery.progress
        counters = progress.counters
        pending_files = list(progress.pending_files)
        pending_directories = list(progress.pending_directories)
        active_directory = progress.active_directory
        active_cursor = progress.active_cursor
        seen_cursors = list(progress.active_cursors_seen)
        # The manifest is keyed by the exact ResourceLibrary-relative source
        # path, so a repeated provider page, a repeated observation pass or a
        # resumed Worker can never admit the same ordinary source twice.  The
        # first durable identity/stability evidence wins.
        sources: dict[str, dict[str, object]] = {}
        for item in discovery.sources:
            path = item.get("path")
            if isinstance(path, str) and path and path not in sources:
                sources[path] = dict(item)
        findings = list(progress.findings)
        reasons = {item.reason: item for item in progress.reasons}
        # Material refusals are durable and monotonic: an ordinary read failure
        # in another subtree must never erase an earlier budget/safety/cursor
        # refusal, in either order or across a restart.  They are persisted
        # separately from the *current* incomplete reason and are the single
        # authority that disables Finalize.
        refusals = list(progress.refusal_reasons)
        observations: list[DiscoveryObservation] = []
        previous = self._load_observations(discovery.discovery_id)
        stable_since: dict[str, datetime] = {}
        # The candidate paths this pass actually observed, so a fully completed
        # pass can drop a previously eligible source that disappeared.
        observed_candidates: set[str] = set()
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
        # A file the admitted scope names but that cannot be observed is a real
        # incomplete scope, exactly like an unreadable directory: the operator
        # must explicitly review the known subset instead of being told the
        # whole selection was discovered.  It is deliberately *not* a material
        # refusal, so the reviewed subset keeps its legal Finalize path.
        observation_degraded = False
        # The unstable count describes the *current* observation pass (what is
        # still waiting for stability), not a cumulative tally of every earlier
        # pass; excluded/error counters stay cumulative totals.
        pass_unstable: set[str] = set()
        # The remaining real interval each still-waiting source needs.  The
        # shortest one becomes the durable re-observation deadline.
        wait_seconds: list[float] = []
        # The file entries observed in the directory currently being walked and
        # in the whole pass.  The authoritative attachment association is
        # evaluated over the real same-directory entry set exactly as the exact
        # Preview does, and it is applied as soon as a directory is finished so
        # a matching sidecar can never inflate the primary count mid-walk.
        directory_entries: list[tuple[str, int, StorageEntry]] = []
        # Every exact regular-file observation participating in this pass,
        # including an explicitly selected file that the API stats directly.
        # Keying by ResourceLibrary-relative path makes overlap between direct
        # selection and a later directory page idempotent.
        observed_file_entries: dict[str, tuple[str, int, StorageEntry]] = {}

        def bump(reason_value: str, path: str) -> None:
            existing = reasons.get(reason_value)
            if existing is None:
                reasons[reason_value] = DiscoveryReasonCount(reason_value, 1, path)
            else:
                reasons[reason_value] = replace(existing, count=existing.count + 1)

        def refuse(reason: DiscoveryIncompleteReason) -> None:
            """Record one durable, monotonic material refusal.

            A material refusal survives a later ordinary read failure in another
            subtree, a later pass and a restart.  It is the single authority that
            keeps Finalize disabled, so a truncated prefix can never be frozen.
            """

            if reason not in refusals and len(refusals) < MAX_DISCOVERY_REFUSALS:
                refusals.append(reason)

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

        def observe(relative: str, depth: int, entry: StorageEntry | None) -> StorageEntry | None:
            """Observe one candidate and return its exact file entry for association."""

            nonlocal counters, observation_degraded
            observed_candidates.add(relative)
            if entry is None:
                try:
                    entry = storage.stat(self._join(library.root_path, relative))
                except (StorageError, OSError, ValueError, KeyError):
                    bump(_REASON_UNREADABLE, relative)
                    note(DiscoveryFindingKind.ERROR, relative, _REASON_UNREADABLE, None, depth)
                    counters = replace(counters, error_entries=counters.error_entries + 1)
                    # The path was seen but its current identity is unknown: it
                    # must not survive in the manifest merely because it was
                    # observed before.
                    sources.pop(relative, None)
                    # A source the admitted scope names but that cannot be
                    # observed makes the walk incomplete: the operator must
                    # explicitly review the known subset, never be told the
                    # whole admitted scope was discovered.
                    observation_degraded = True
                    return None
                if self._admit_stat_entry(entry, relative, library) is None:
                    # A provider ``stat`` that answers for a different path than
                    # the one requested is never normalized into authority.
                    bump(_REASON_UNSAFE_ENTRY, relative)
                    note(
                        DiscoveryFindingKind.ERROR,
                        getattr(entry, "path", relative),
                        _REASON_UNSAFE_ENTRY,
                        entry,
                        depth,
                    )
                    counters = replace(counters, error_entries=counters.error_entries + 1)
                    sources.pop(relative, None)
                    return None
            if entry.entry_type is StorageEntryType.SYMLINK:
                bump(_REASON_SYMLINK, relative)
                note(DiscoveryFindingKind.EXCLUDED, relative, _REASON_SYMLINK, entry, depth)
                counters = replace(counters, excluded_entries=counters.excluded_entries + 1)
                sources.pop(relative, None)
                return None
            if entry.entry_type is not StorageEntryType.FILE:
                bump(_REASON_UNSUPPORTED_TYPE, relative)
                note(
                    DiscoveryFindingKind.EXCLUDED, relative, _REASON_UNSUPPORTED_TYPE, entry, depth
                )
                counters = replace(counters, excluded_entries=counters.excluded_entries + 1)
                sources.pop(relative, None)
                return None
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
                sources.pop(relative, None)
                # The real Preview attachment matcher reads the same directory
                # entries even when a file is excluded as an independent
                # source. Keep this exact observed entry available to that
                # matcher; it can never become a source because it is absent
                # from ``sources``.
                return entry
            observed = source_fingerprint(library.storage_id, library.library_id, entry)
            if observed.state is not OccurrenceState.VERIFIED or observed.value is None:
                bump(_REASON_UNREADABLE, relative)
                note(DiscoveryFindingKind.ERROR, relative, _REASON_UNREADABLE, entry, depth)
                counters = replace(counters, error_entries=counters.error_entries + 1)
                sources.pop(relative, None)
                return entry
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
                # One exact source per admitted Storage/ResourceLibrary/path:
                # a repeated page or a repeated observation pass keeps the first
                # durable identity and never appends a second copy.
                sources.setdefault(
                    relative, self._source_identity(library, entry, relative, observed, now)
                )
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
                # The real interval still required before a later observation
                # could prove this source stable.  The shortest one is the
                # durable re-observation deadline, so waiting work is never
                # reclaimed in a busy loop.
                wait_seconds.append(
                    stability_wait_seconds(
                        library,
                        entry,
                        now=now,
                        unchanged_previous=prior is not None
                        and prior.matches(entry, observed.value),
                        observed_since=resolved_since,
                    )
                )
                # A previously eligible source that is no longer proven stable
                # cannot survive merely because its path was seen before.
                sources.pop(relative, None)

            return entry

        def demote_observed_attachment_groups(directories: set[str] | None = None) -> None:
            """Apply the production matcher to each exact observed directory.

            A mixed selection can contain files observed by ``stat`` alongside
            files from a walked directory. Grouping the complete observed set
            before checking the primary bound lets those two entrances share
            the same association, while never listing an unselected directory.
            """

            grouped: dict[str, dict[str, tuple[str, int, StorageEntry]]] = {}
            for relative, item in observed_file_entries.items():
                directory = relative.rsplit("/", 1)[0] if "/" in relative else ""
                if directories is not None and directory not in directories:
                    continue
                grouped.setdefault(directory, {})[relative] = item
            for directory in sorted(grouped):
                entries = [grouped[directory][path] for path in sorted(grouped[directory])]
                self._demote_attachments(
                    runtime,
                    library,
                    entries,
                    sources,
                    snapshot_id=discovery.snapshot_id,
                    snapshot_digest=discovery.snapshot_digest,
                )

        explicit_files_associated = False
        while not stop:
            if heartbeat is not None and not heartbeat():
                # The lease was taken over by another Worker.  The old owner
                # must stop *without writing*: publishing a pause, a failure or
                # a claim release here would rewrite the successor's ownership
                # and could leave the record with no valid native continuation.
                raise DiscoveryOwnershipLost(
                    "this Worker lost the discovery claim before its next publication",
                    details={"discoveryId": discovery.discovery_id},
                )
            elapsed = self._monotonic() - started
            if elapsed >= self._remaining_active(counters):
                counters = replace(counters, active_seconds=counters.active_seconds + elapsed)
                incomplete = DiscoveryIncompleteReason.TIME_LIMIT
                refuse(incomplete)
                status = DiscoveryStatus.PARTIAL_SUCCESS
                break
            if counters.visited_entries >= self._budgets.max_visited_entries:
                incomplete = DiscoveryIncompleteReason.ENTRY_LIMIT
                refuse(incomplete)
                status = DiscoveryStatus.PARTIAL_SUCCESS
                break
            if counters.page_fetches >= self._budgets.max_page_fetches:
                incomplete = DiscoveryIncompleteReason.PAGE_LIMIT
                refuse(incomplete)
                status = DiscoveryStatus.PARTIAL_SUCCESS
                break
            if pending_files:
                relative = pending_files.pop(0)
                observed_entry = observe(relative, 0, None)
                if observed_entry is not None:
                    observed_file_entries.setdefault(relative, (relative, 0, observed_entry))
                continue
            if active_directory is None:
                if not explicit_files_associated:
                    explicit_directories = {
                        relative.rsplit("/", 1)[0] if "/" in relative else ""
                        for relative in observed_file_entries
                    }
                    demote_observed_attachment_groups(explicit_directories)
                    explicit_files_associated = True
                    if self._over_primary_limit(
                        sources, discovery.budgets.max_primary_sources, bump, note
                    ):
                        incomplete = DiscoveryIncompleteReason.PRIMARY_LIMIT
                        refuse(incomplete)
                        status = DiscoveryStatus.PARTIAL_SUCCESS
                        break
                # The previous directory is fully walked (or was abandoned):
                # apply the production attachment association over its real
                # observed entries, so a *proven* sidecar is never counted as an
                # independent primary.  The primary bound is then evaluated
                # against the true primary set, never against candidates that
                # the existing association is about to demote.
                if directory_entries:
                    walked_directories = {
                        relative.rsplit("/", 1)[0] if "/" in relative else ""
                        for relative, _, _ in directory_entries
                    }
                    demote_observed_attachment_groups(walked_directories)
                    directory_entries = []
                    if self._over_primary_limit(
                        sources, discovery.budgets.max_primary_sources, bump, note
                    ):
                        incomplete = DiscoveryIncompleteReason.PRIMARY_LIMIT
                        refuse(incomplete)
                        status = DiscoveryStatus.PARTIAL_SUCCESS
                        stop = True
                        break
                if not pending_directories:
                    if not degraded:
                        status = DiscoveryStatus.COMPLETED
                    break
                if counters.visited_directories >= self._budgets.max_visited_directories:
                    # A *directory* budget counts distinct directories entered,
                    # not provider pages: a directory already being paged
                    # through is one opened directory and never exhausts this
                    # bound.  The bound is evaluated only when the walk is about
                    # to enter a genuinely new directory.
                    incomplete = DiscoveryIncompleteReason.DIRECTORY_LIMIT
                    refuse(incomplete)
                    status = DiscoveryStatus.PARTIAL_SUCCESS
                    break
                # The previous directory is fully walked: apply the production
                # attachment association, so a sidecar matching an admitted main
                # file is never counted as an independent primary.
                active_directory = pending_directories.pop(0)
                active_cursor = None
                seen_cursors = []
                # One *directory* is counted exactly once, when the walk first
                # enters it.  Every further page of that same directory is a
                # page fetch, not a new directory: counting pages here made a
                # single large directory look like a thousand directories and
                # stopped the walk at the directory bound.
                counters = replace(counters, visited_directories=counters.visited_directories + 1)
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
                if cursor_problem is not None:
                    incomplete = DiscoveryIncompleteReason.CURSOR_REPEATED
                    refuse(incomplete)
                elif not any(discovery_budget_limited(item) for item in refusals):
                    # An ordinary read failure is the *current* fact, but it
                    # must never overwrite an already durable material refusal
                    # (budget, safety depth, cyclic cursor or unsafe entry).
                    incomplete = DiscoveryIncompleteReason.READ_FAILURE
                status = DiscoveryStatus.PARTIAL_SUCCESS
                degraded = True
                active_directory = None
                active_cursor = None
                seen_cursors = []
                continue
            depth = directory.count("/") + 1 if directory else 0
            for raw in tuple(getattr(page, "entries", ())):
                counters = replace(counters, visited_entries=counters.visited_entries + 1)
                relative = self._admit_provider_entry(raw, directory, library)
                if relative is None:
                    # A provider entry whose path/name/type is not exactly one
                    # ordinary child of the requested directory is never
                    # normalized into authority, never stat-ed or traversed and
                    # never allowed to enlarge the manifest.  It is a material
                    # safety refusal: the walk is honestly incomplete and cannot
                    # be frozen as if it were a complete scope.
                    bump(_REASON_UNSAFE_ENTRY, directory)
                    unsafe_path = getattr(raw, "path", None)
                    note(
                        DiscoveryFindingKind.ERROR,
                        unsafe_path if isinstance(unsafe_path, str) else directory,
                        _REASON_UNSAFE_ENTRY,
                        raw if isinstance(raw, StorageEntry) else None,
                        depth,
                    )
                    counters = replace(counters, error_entries=counters.error_entries + 1)
                    incomplete = DiscoveryIncompleteReason.UNSAFE_ENTRY
                    refuse(incomplete)
                    status = DiscoveryStatus.PARTIAL_SUCCESS
                    degraded = True
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
                        refuse(incomplete)
                        status = DiscoveryStatus.PARTIAL_SUCCESS
                        stop = True
                        break
                    pending_directories.append(relative)
                    continue
                directory_entries.append((relative, depth, raw))
                observed_file_entries.setdefault(relative, (relative, depth, raw))
                # Every ordinary file is observed first.  A sidecar is only
                # *demoted* afterwards, and only when the production attachment
                # matcher proves it belongs to an admitted main file: a suffix
                # match with no admitted owner (an orphan trailer) or a policy
                # that does not classify it must keep its ordinary primary
                # identity instead of being silently dropped.  The primary bound
                # is therefore evaluated per completed directory, against the
                # true primary set, never against candidates the existing
                # association is about to demote.
                observe(relative, depth, raw)
            if stop:
                break
            next_cursor = getattr(page, "next_cursor", None)
            if next_cursor:
                if next_cursor in seen_cursors:
                    bump(_REASON_CURSOR, directory)
                    note(DiscoveryFindingKind.ERROR, directory, _REASON_CURSOR, None, depth)
                    counters = replace(counters, error_entries=counters.error_entries + 1)
                    incomplete = DiscoveryIncompleteReason.CURSOR_REPEATED
                    refuse(incomplete)
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

        self._demote_attachments(
            runtime,
            library,
            directory_entries,
            sources,
            snapshot_id=discovery.snapshot_id,
            snapshot_digest=discovery.snapshot_digest,
        )
        self._demote_attachments(
            runtime,
            library,
            list(observed_file_entries.values()),
            sources,
            snapshot_id=discovery.snapshot_id,
            snapshot_digest=discovery.snapshot_digest,
        )
        # A directory abandoned mid-page by an unrelated safety break may have
        # left the manifest over the primary bound; the durable manifest is
        # always trimmed to the exact bound and reported as a material refusal,
        # so no code path can freeze an over-limit or first-N prefix.
        if self._over_primary_limit(sources, discovery.budgets.max_primary_sources, bump, note):
            incomplete = DiscoveryIncompleteReason.PRIMARY_LIMIT
            refuse(incomplete)
            status = DiscoveryStatus.PARTIAL_SUCCESS
        counters = replace(counters, primary_sources=len(sources))

        if status is DiscoveryStatus.COMPLETED and not pending_files and not pending_directories:
            # A fully completed walk observed the whole admitted scope, so a
            # source that no longer appears (removed, renamed out of the media
            # extension set or otherwise no longer eligible) cannot survive in
            # the manifest merely because it was seen in an earlier pass.
            for stale in tuple(sources):
                if stale not in observed_candidates:
                    sources.pop(stale, None)
        counters = replace(
            counters,
            active_seconds=counters.active_seconds + (self._monotonic() - started),
            primary_sources=len(sources),
            unstable_entries=len(pass_unstable),
        )
        if status is DiscoveryStatus.COMPLETED:
            if discovery.cancel_requested:
                return self._cancel(discovery, claim_token)
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
        if (
            status is DiscoveryStatus.COMPLETED
            and observation_degraded
            and incomplete is DiscoveryIncompleteReason.NONE
        ):
            # A file the admitted scope named could not be observed.  That is a
            # real incomplete scope even though the traversal itself finished,
            # so the operator is never told the whole selection was discovered;
            # the known sources keep their legal explicit-subset Finalize path.
            incomplete = DiscoveryIncompleteReason.READ_FAILURE
            status = DiscoveryStatus.PARTIAL_SUCCESS
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
        # A waiting discovery becomes claimable again only when a later
        # observation could actually change the verdict.  The deadline is the
        # shortest real interval any still-waiting source needs, so waiting work
        # neither spins nor consumes the traversal budget while idle.
        next_observation_at: datetime | None = None
        if status is DiscoveryStatus.WAITING_STABILITY and wait_seconds:
            next_observation_at = self._clock() + timedelta(seconds=max(0.0, min(wait_seconds)))
        updated = replace(
            discovery,
            status=status,
            version=discovery.version + 1,
            sources=tuple(sources.values()),
            updated_at=self._clock(),
            error=None,
            next_observation_at=next_observation_at,
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
                tuple(refusals),
            ),
        )
        # A finished observation is never frozen automatically.  Completing a
        # walk does not make an executable subset: the operator must explicitly
        # finalize the reviewed findings, and an incomplete walk especially must
        # never silently become an executable first-N prefix.
        persisted = self._persist(
            updated,
            expected_version=discovery.version,
            claim_token=claim_token,
            observations=tuple(observations),
        )
        # A non-terminal step yields its claim so the resident Worker can
        # continue the same durable scope on its next pass.  The stage is zero
        # mutation and every publication is a version CAS fenced by this exact
        # claim, so a yielded claim can never duplicate a finding or a source.
        self._release_claim(persisted.discovery_id, claim_token)
        if (
            discovery.auto_prepare
            and persisted.status in {DiscoveryStatus.COMPLETED, DiscoveryStatus.PARTIAL_SUCCESS}
            and persisted.sources
            and discovery_material_refusal(persisted.progress) is None
        ):
            # A full preparation freezes its reviewed sources internally and
            # moves into the analysis stage.  A budget/safety-refused walk is
            # deliberately not frozen: its recorded sources are a truncated
            # prefix, so the operator must narrow the scope instead.
            return self._begin_preparation_analysis(persisted)
        return persisted

    def _begin_preparation_analysis(self, discovery: MediaDiscovery) -> MediaDiscovery:
        """Freeze a completed preparation's sources and enter analysis.

        This reuses the exact same durable linkage (one discovery, one linked
        intent) as the explicit Finalize path, then advances the record to the
        ``analyzing`` stage.  A repository that cannot offer the atomic linkage
        fails the preparation closed instead of leaving an orphan intent.
        """

        try:
            frozen = self._finalize(discovery, None)
        except DiscoveryError as error:
            return self._fail(discovery, None, error.code)
        except Exception as error:  # noqa: BLE001 - a Worker must not crash the loop
            return self._fail(discovery, None, type(error).__name__)
        if frozen.intent_id is None or not frozen.frozen:
            # ``_finalize`` recorded a bounded failure; leave that truthful
            # outcome instead of inventing an analysis stage.
            return frozen
        now = self._clock()
        analyzing = replace(
            frozen,
            status=DiscoveryStatus.ANALYZING,
            version=frozen.version + 1,
            updated_at=now,
            error=None,
            progress=replace(
                frozen.progress,
                phase="analyzing",
                message=(
                    "the reviewed source list is frozen; the resident Worker is running the "
                    "complete zero-mutation analysis to build the plan summary"
                ),
            ),
        )
        try:
            return self._persist(analyzing, expected_version=frozen.version)
        except DiscoveryError:
            # The linkage is already durable; a refused stage publication is
            # not a preparation failure, so re-read the truthful record.
            return self._read(discovery.discovery_id) or frozen

    def _analyze(self, discovery: MediaDiscovery, claim_token: str) -> MediaDiscovery:
        """Run the complete production analysis for a frozen preparation.

        The analysis is the existing zero-mutation Preview authority: it uses
        the same RecognitionTypePolicy, Metadata Provider, Naming,
        Classification and plan calculation as the ordinary journey.  The
        resulting exact Preview is linked as read-only evidence; it grants no
        execution authority and mutates nothing.
        """

        service = self._preview_service
        creator = getattr(service, "create", None)
        if service is None or not callable(creator):
            return self._fail(discovery, claim_token, "preview_unavailable")
        if discovery.intent_id is None:
            return self._fail(discovery, claim_token, "intent_unavailable")
        try:
            intent = self._intent_service.get(discovery.intent_id)
        except Exception:  # noqa: BLE001 - a missing intent is a truthful failure
            return self._fail(discovery, claim_token, "intent_unavailable")
        remaining = self._remaining_intent_item_ids(intent)
        if not remaining:
            # Every item of this preparation has already been admitted to an
            # execution.  Re-running the analysis would only re-review work the
            # operator already confirmed, so the preparation settles truthfully
            # at "nothing left to prepare" instead of re-creating a summary.
            now = self._clock()
            settled = replace(
                discovery,
                status=DiscoveryStatus.COMPLETED,
                version=discovery.version + 1,
                preview_id=None,
                updated_at=now,
                error=None,
                progress=replace(
                    discovery.progress,
                    phase="prepared",
                    message=(
                        "every source of this preparation has already been admitted to an "
                        "execution; there is no remaining scope to prepare"
                    ),
                ),
            )
            persisted = self._persist(
                settled, expected_version=discovery.version, claim_token=claim_token
            )
            self._release_claim(persisted.discovery_id, claim_token)
            return persisted
        try:
            preview = creator(
                discovery.intent_id,
                list(remaining),
                expected_version=intent.version,
                actor=discovery.actor,
                tolerate_unready_sources=True,
            )
        except Exception as error:  # noqa: BLE001 - report one bounded failure
            code = getattr(error, "code", None)
            return self._fail(
                discovery,
                claim_token,
                code if isinstance(code, str) and code else "preview_unavailable",
            )
        preview_id = getattr(preview, "preview_id", None)
        if not isinstance(preview_id, str) or not preview_id:
            return self._fail(discovery, claim_token, "preview_unavailable")
        now = self._clock()
        complete = (
            discovery.progress.incomplete_reason is DiscoveryIncompleteReason.NONE
            and discovery_material_refusal(discovery.progress) is None
        )
        updated = replace(
            discovery,
            status=(DiscoveryStatus.COMPLETED if complete else DiscoveryStatus.PARTIAL_SUCCESS),
            version=discovery.version + 1,
            preview_id=preview_id,
            updated_at=now,
            error=None,
            progress=replace(
                discovery.progress,
                phase="prepared",
                message=(
                    "the exact zero-mutation plan summary is ready; review it and explicitly "
                    "confirm the ready subset to organize"
                ),
            ),
        )
        persisted = self._persist(
            updated, expected_version=discovery.version, claim_token=claim_token
        )
        self._release_claim(persisted.discovery_id, claim_token)
        return persisted

    def _remaining_intent_item_ids(self, intent) -> tuple[str, ...]:
        """The intent items a fresh preparation analysis may still review.

        An item that any durable execution of this intent already admitted is
        permanently excluded: a completed, failed, ignored or uncertain sibling
        must never be folded back into a new plan summary.  The set comes from
        the persisted ``manual_execution_items`` authority, not from whether a
        source file still exists or from a truncated recent-execution list, so
        the decision is exact and durable across restarts.
        """

        reader = getattr(self._repository, "list_manual_execution_item_ids_for_intent", None)
        admitted: frozenset[str] = frozenset()
        if callable(reader):
            try:
                admitted = frozenset(reader(intent.intent_id))
            except Exception:  # noqa: BLE001 - a missing reader keeps every item eligible
                admitted = frozenset()
        return tuple(item.item_id for item in intent.items if item.item_id not in admitted)

    def preparation_preview_id(self, discovery_id: str) -> str | None:
        """The exact read-only Preview linked by a completed preparation, if any."""

        discovery = self._read(discovery_id)
        return discovery.preview_id if discovery is not None else None

    def _release_claim(self, discovery_id: str, claim_token: str) -> None:
        releaser = getattr(self._repository, "release_media_discovery_claim", None)
        if callable(releaser) and claim_token:
            try:
                releaser(discovery_id, claim_token)
            except Exception:
                # A claim that cannot be released simply expires on its lease;
                # the durable progress already published is unaffected.
                pass

    @staticmethod
    def _over_primary_limit(sources, bound: int, bump, note) -> bool:
        """Trim the manifest to the discovery's own admitted primary bound.

        The bound is the *durable* bound persisted with this exact admission
        (never the service default), so a definition-bound Run once whose
        effective manifest bound is smaller than the manual default can never
        leave an over-limit manifest behind.  It is evaluated against the true
        primary set (after the production attachment association has demoted
        proven sidecars), so a directory that overshoots in one page is trimmed
        back to exactly that bound instead of silently becoming a first-N
        prefix.
        """

        if len(sources) <= bound:
            return False
        while len(sources) > bound:
            path = next(reversed(sources))
            sources.pop(path, None)
            bump(_REASON_UNSAFE_ENTRY, path)
            note(DiscoveryFindingKind.TRUNCATED, path, "primary_source_limit_exceeded", None, 0)
        return True

    def _attachment_policies_by_source(
        self,
        runtime,
        sources: Mapping[str, dict[str, object]],
        *,
        snapshot_id: str,
        snapshot_digest: str,
    ) -> dict[str, object]:
        """Resolve each source's actual default manual choice under its pin.

        Discovery is followed by an editable manual intent. A RecognitionRule
        result alone does not prove the choice that intent or its Preview will
        consume, so only the existing default-choice behavior may authorize
        source demotion here. If that choice cannot be proven, every source is
        kept as an independent primary for later operator review.
        """

        strategy = getattr(runtime, "strategy", None)
        resolver = getattr(self._intent_service, "default_choice_for_runtime_source", None)
        if strategy is None or not callable(resolver):
            return {}
        type_policies = {
            policy.recognition_type_id: policy
            for policy in strategy.recognition_type_policies
            if policy.enabled and policy.recognition_type.enabled
        }
        resolved: dict[str, object] = {}
        for relative in sorted(sources):
            try:
                source = ManualSourceIdentity.from_document(sources[relative])
                choice = resolver(
                    source,
                    runtime,
                    snapshot_id=snapshot_id,
                    snapshot_digest=snapshot_digest,
                )
            except (ManualIntentError, ValueError):
                continue
            type_policy = type_policies.get(choice.recognition_type_id)
            if type_policy is None:
                continue
            attachments = getattr(type_policy.organize_policy, "attachments", None)
            if attachments is None or not getattr(attachments, "enabled", False):
                continue
            resolved[relative] = attachments
        return resolved

    @staticmethod
    def _stem_related(name: str, owner_name: str) -> bool:
        """A *necessary* stem relation of the production attachment matcher.

        ``AttachmentDiscovery._classify`` only relates a sidecar to a primary
        when the sidecar stem equals, or extends, the primary stem across a
        ``.``/``-`` boundary (case-insensitively).  This cheap predicate only
        narrows which entries the real matcher is asked about; it never decides
        the association itself, so it cannot become a second matching language.
        """

        stem, dot, _extension = name.rpartition(".")
        owner_stem, owner_dot, _owner_extension = owner_name.rpartition(".")
        if not dot or not owner_dot:
            return False
        folded = stem.casefold()
        owner_folded = owner_stem.casefold()
        if folded == owner_folded:
            return True
        return (
            folded.startswith(owner_folded)
            and len(stem) > len(owner_stem)
            and stem[len(owner_stem)] in ".-"
        )

    def _attachment_owners(
        self,
        library,
        relative: str,
        entry: StorageEntry,
        entries: list[tuple[str, int, StorageEntry]],
        admitted: dict[str, dict[str, object]],
        attachment_policies: Mapping[str, object],
    ) -> tuple[str, ...]:
        """Every admitted main file this entry attaches to, in stable order.

        The authoritative association is the production ``AttachmentDiscovery``
        itself, invoked with the *same* policy the exact Preview will consume and
        over the real same-directory entry set.  An entry is an attachment
        exactly when that discovery classifies it as one for an already admitted
        primary, so it never becomes an independent primary of its own.  Nothing
        is fabricated: a video with no admitted main file is not an attachment
        and keeps its ordinary primary identity.

        The *whole* association set is returned, not just its first member: the
        demotion below re-evaluates which association still applies as other
        members are demoted, and the relation itself never changes because the
        matcher always sees the real directory.  Computing it once keeps the
        resolution bounded instead of re-running the matcher per round.
        """

        if entry is None or not admitted:
            return ()
        directory = relative.rsplit("/", 1)[0] if "/" in relative else ""
        same_directory = [
            candidate_entry
            for candidate_relative, _depth, candidate_entry in entries
            if (candidate_relative.rsplit("/", 1)[0] if "/" in candidate_relative else "")
            == directory
        ]
        # Candidates are visited in a stable order so the *same* directory
        # content always yields the same association however the provider paged
        # or ordered it.  Without that, a mutual same-stem group could resolve to
        # a different retained primary on a different page order.
        owners: list[str] = []
        for owner_relative in sorted(admitted):
            if (owner_relative.rsplit("/", 1)[0] if "/" in owner_relative else "") != directory:
                continue
            owner_entry = next(
                (
                    candidate_entry
                    for candidate_relative, _depth, candidate_entry in entries
                    if candidate_relative == owner_relative
                ),
                None,
            )
            if owner_entry is None:
                continue
            # Attachment rules belong to the retained primary's RecognitionType.
            # Another type's settings can never absorb this source.
            policy = attachment_policies.get(owner_relative)
            if policy is None:
                continue
            if not self._stem_related(entry.name, owner_entry.name):
                # The production matcher can only relate same-stem sidecars, so
                # this cheap necessary condition skips the expensive real
                # association for every unrelated pair without deciding it.
                continue
            primary = StorageLocation(library.storage_id, owner_entry.path)
            discovered = AttachmentDiscovery().discover(
                _ObservedDirectoryStorage(library.storage_id, tuple(same_directory)),
                primary,
                policy,
            )
            if any(attachment.source.path == entry.path for attachment in discovered.attachments):
                owners.append(owner_relative)
        return tuple(owners)

    def _demote_attachments(
        self,
        runtime,
        library,
        entries: list[tuple[str, int, StorageEntry]],
        sources: dict[str, dict[str, object]],
        *,
        snapshot_id: str,
        snapshot_digest: str,
    ) -> None:
        """Drop every observed video that is an attachment of a *retained* primary.

        This runs after the walk has established the real primary set, so the
        association is evaluated once per distinct policy against the actual
        admitted main files.  It is the folder-discovery equivalent of the exact
        Preview's own attachment step, not a second matcher: a classified
        attachment is not an independent primary and therefore cannot inflate the
        primary count or trip the 100-primary gate.

        An attachment is only demoted while the admitted primary it attaches to
        *remains* admitted.  The production matcher is symmetric for a same-stem
        video group (``otherSameStem`` classifies ``Film.2001.mkv`` and
        ``Film.2001.mp4`` as each other's attachment), so demoting against the
        pre-demotion source set removed every mutual owner and published a
        completed discovery with an empty manifest.

        The resolution therefore iterates to a fixpoint over the *currently*
        admitted set, and is deterministic and page-order independent:

        * a source the matcher cannot attach to any admitted primary is retained
          unconditionally -- it is nobody's sidecar;
        * every other source is demoted only when its association target is
          itself retained, so a mutual group keeps exactly one admitted primary
          and no eligible media silently disappears;
        * a source whose association target is demoted is re-evaluated against
          the reduced set in the next round, so a sidecar of a demoted member
          (for example a Trailer beside a mutual same-stem group, or a longer
          stem chain) is demoted too instead of being promoted to an independent
          primary.

        Each round demotes at least one source or stops, so this terminates in at
        most one round per admitted source, and the expensive association is
        computed only once.
        """

        if not entries or not sources:
            return
        # Resolve each potential owner's policy once from the exact default
        # manual choice under the pinned runtime. The association relation is
        # then a property of the real directory and the same policy Preview
        # consumes when the operator leaves that editable choice unchanged.
        attachment_policies = self._attachment_policies_by_source(
            runtime,
            sources,
            snapshot_id=snapshot_id,
            snapshot_digest=snapshot_digest,
        )
        candidates = {
            relative: self._attachment_owners(
                library, relative, entry, entries, sources, attachment_policies
            )
            for relative, _depth, entry in entries
            if relative in sources
        }
        admitted = set(sources)
        while True:
            # The owner of a source is its first *still admitted* association,
            # in the same stable order the matcher reports.
            owner_of = {
                relative: next(
                    (owner for owner in candidates.get(relative, ()) if owner in admitted),
                    None,
                )
                for relative in admitted
            }
            # A source nobody admits as an attachment is retained unconditionally.
            retained = {relative for relative in admitted if owner_of[relative] is None}
            demoted: list[str] = []
            for relative in sorted(admitted):
                owner = owner_of[relative]
                if owner is None:
                    continue
                if owner in retained:
                    demoted.append(relative)
                    continue
                # The only primary this entry attaches to is itself being
                # demoted, so demoting this entry too would leave the group with
                # no admitted source at all.  Keep it as the group's retained
                # primary; the next round re-evaluates it against the reduced set.
                retained.add(relative)
            if not demoted:
                return
            for relative in demoted:
                admitted.discard(relative)
                sources.pop(relative, None)

    def _admit_provider_entry(self, raw, directory: str, library) -> str | None:
        """The admitted ResourceLibrary-relative path of one provider entry.

        Returns ``None`` when the entry is not exactly one ordinary child of the
        requested directory inside the ResourceLibrary root.  A provider entry
        is never normalized into authority: sibling, ancestor, absolute,
        traversal, path/name-mismatched or non-entry values are refused before
        any source construction, ``stat`` or traversal scheduling.  Legitimate
        adapter conventions (root prefixes and exact whitespace names) are
        preserved because the check compares the *exact* path the adapter
        published for the requested directory.
        """

        if not isinstance(raw, StorageEntry):
            return None
        path = raw.path
        if not isinstance(path, str) or not path or "\x00" in path or "\\" in path:
            return None
        root_value = (library.root_path or "").strip("/")
        directory_value = directory.strip("/")
        expected_parent = f"{root_value}/{directory_value}" if root_value else directory_value
        expected_parent = expected_parent.strip("/")
        if path.startswith("/"):
            return None
        parts = path.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            return None
        parent = "/".join(parts[:-1])
        if parent != expected_parent:
            return None
        relative = self._relative(path, library.root_path)
        if relative is None:
            return None
        if relative != "/".join(filter(None, (directory_value, parts[-1]))):
            return None
        if raw.entry_type not in {
            StorageEntryType.FILE,
            StorageEntryType.DIRECTORY,
            StorageEntryType.SYMLINK,
            StorageEntryType.OTHER,
        }:
            return None
        if raw.name != parts[-1]:
            return None
        return relative

    def _admit_stat_entry(self, entry, relative: str, library) -> str | None:
        """Whether a provider ``stat`` answer is exactly the requested source.

        An explicit file scope is observed directly, so its ``stat`` result must
        still describe the requested ResourceLibrary-relative path.  A provider
        that answers for a sibling, ancestor, absolute or traversal path is
        refused before source construction.
        """

        if not isinstance(entry, StorageEntry):
            return None
        path = entry.path
        if not isinstance(path, str) or not path or "\x00" in path or "\\" in path:
            return None
        root_value = (library.root_path or "").strip("/")
        expected = f"{root_value}/{relative}".strip("/") if root_value else relative
        if path.startswith("/") or path != expected:
            return None
        parts = path.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            return None
        if entry.name != parts[-1]:
            return None
        return relative

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
        identity = ManualSourceIdentity(
            source_id=occurrence,
            storage_id=library.storage_id,
            resource_library_id=library.library_id,
            path=storage_path,
            filename=filename,
            extension=extension,
            size=entry.size,
            modified_at=entry.modified_at,
            observed_at=now,
            stable_since=None,
            occurrence_id=occurrence,
            fingerprint=observed.value,
            fingerprint_algorithm=observed.algorithm,
            fingerprint_evidence=observed.evidence,
            occurrence_state=observed.state.value,
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
            self._refuse_unselectable_directory(library, entry.path, observed)
            return DiscoveryScopeEntry(entry.path, DiscoveryEntryKind.DIRECTORY)
        if observed.entry_type is StorageEntryType.FILE:
            self._refuse_unselectable_file(library, entry.path, observed)
            return DiscoveryScopeEntry(entry.path, DiscoveryEntryKind.FILE)
        raise DiscoveryError(
            "the selected source has an unsupported entry type",
            code="source_unsupported",
            status=409,
            next_action="select a folder or an ordinary file inside the ResourceLibrary",
            details={"relativePath": entry.path},
        )

    def _refuse_pruned_ancestor(self, library, relative: str) -> None:
        """Refuse a directly selected entry no root walk could ever reach.

        A direct selection shares the *root-relative* meaning of the configured
        exclude/include/depth policy: if an ancestor directory would be pruned
        by a walk that starts at the ResourceLibrary root, then the operator
        browsing into that subtree and clicking the descendant cannot make it
        admissible.  This closes the leaf-only gap without introducing a second
        filter language: ``pruned_ancestor`` is the same pure predicate the walk
        applies to every directory it visits.
        """

        pruned = pruned_ancestor(library, relative)
        if pruned is None:
            return
        ancestor, reason = pruned
        code = {
            PrunedAncestorReason.EXCLUDED_RULE: "source_excluded",
            PrunedAncestorReason.NOT_INCLUDED: "source_not_included",
            PrunedAncestorReason.DEPTH: "source_excluded",
        }[reason]
        why = {
            PrunedAncestorReason.EXCLUDED_RULE: _REASON_EXCLUDED_RULE,
            PrunedAncestorReason.NOT_INCLUDED: _REASON_NOT_INCLUDED,
            PrunedAncestorReason.DEPTH: _REASON_DEPTH,
        }[reason]
        raise DiscoveryError(
            "the selected source is inside a folder the pinned ResourceLibrary policy excludes",
            code=code,
            status=409,
            next_action=(
                "select a source the configured policy admits, or update the ResourceLibrary "
                "policy and publish it"
            ),
            details={"relativePath": relative, "reason": why, "prunedAncestor": ancestor},
        )

    def _refuse_unselectable_directory(
        self, library, relative: str, observed: StorageEntry
    ) -> None:
        """Refuse a directly selected folder the pinned policy already excludes.

        Filtering must not depend on *how* a source was selected.  A directory
        the configured exclude rules, include rules or configured depth reject
        is not a legal entry point: selecting it directly must not walk past the
        same policy that prunes it during a parent walk, and it must not
        silently become an empty "complete" discovery either.  The refusal is
        bounded, actionable and creates no durable record.
        """

        self._refuse_pruned_ancestor(library, relative)
        if excluded_directory(library, relative, observed):
            raise DiscoveryError(
                "the selected folder is excluded by the pinned ResourceLibrary policy",
                code="source_excluded",
                status=409,
                next_action=(
                    "select a folder that the configured exclude rules do not exclude, or "
                    "update the ResourceLibrary policy and publish it"
                ),
                details={"relativePath": relative, "reason": _REASON_EXCLUDED_RULE},
            )
        if not directory_may_match(library.include_rules, relative):
            raise DiscoveryError(
                "the selected folder cannot contain an included source under the pinned policy",
                code="source_not_included",
                status=409,
                next_action=(
                    "select a folder that satisfies the configured include rules, or update "
                    "the ResourceLibrary policy and publish it"
                ),
                details={"relativePath": relative, "reason": _REASON_NOT_INCLUDED},
            )
        if not self._within_configured_depth(library, relative, DiscoveryEntryKind.DIRECTORY):
            raise DiscoveryError(
                "the selected folder is deeper than the configured ResourceLibrary depth",
                code="source_excluded",
                status=409,
                next_action=(
                    "select a shallower folder, or raise the configured depth and publish it"
                ),
                details={"relativePath": relative, "reason": _REASON_DEPTH},
            )

    def _refuse_unselectable_file(self, library, relative: str, observed: StorageEntry) -> None:
        """Refuse a directly selected file the pinned policy excludes.

        An explicit file is a legal entry point only when the same
        root-relative extension/include/exclude/depth policy that governs a
        folder walk admits it.  A temporary/download file, an excluded path or
        a file the configured depth never reaches stays excluded instead of
        becoming a primary source merely because the operator clicked it
        directly.
        """

        self._refuse_pruned_ancestor(library, relative)
        verdict = classify_entry(library, relative, observed)
        if verdict is not ScanEntryVerdict.CANDIDATE:
            reason = {
                ScanEntryVerdict.EXCLUDED_EXTENSION: _REASON_UNSUPPORTED_EXTENSION,
                ScanEntryVerdict.EXCLUDED_RULE: _REASON_EXCLUDED_RULE,
                ScanEntryVerdict.NOT_INCLUDED: _REASON_NOT_INCLUDED,
                ScanEntryVerdict.UNSUPPORTED_TYPE: _REASON_UNSUPPORTED_TYPE,
            }[verdict]
            raise DiscoveryError(
                "the selected file is excluded by the pinned ResourceLibrary policy",
                code="source_excluded",
                status=409,
                next_action=(
                    "select a file the configured policy admits, or update the ResourceLibrary "
                    "policy and publish it"
                ),
                details={"relativePath": relative, "reason": reason},
            )
        if not self._within_configured_depth(library, relative, DiscoveryEntryKind.FILE):
            raise DiscoveryError(
                "the selected file is deeper than the configured ResourceLibrary depth",
                code="source_excluded",
                status=409,
                next_action=(
                    "select a file inside the configured depth, or raise the configured depth "
                    "and publish it"
                ),
                details={"relativePath": relative, "reason": _REASON_DEPTH},
            )

    @staticmethod
    def _within_configured_depth(library, relative: str, kind: DiscoveryEntryKind) -> bool:
        """Whether a *directly selected* entry is reachable under configured depth.

        The walk prunes a child directory found in a directory of depth ``d``
        when ``d >= max_depth`` (depth 0 is the ResourceLibrary root).  A direct
        selection must not be a shortcut around that rule, so it is legal only
        when the directory that would have to be listed to reach it is itself
        listable under the same predicate.  This keeps one depth meaning for the
        whole ResourceLibrary regardless of the selection entrance.
        """

        maximum = getattr(library, "max_depth", None)
        if maximum is None:
            return True
        parent = relative.rsplit("/", 1)[0] if "/" in relative else ""
        if kind is DiscoveryEntryKind.FILE:
            # A file is reached by listing its containing directory, which the
            # walk may only enter from that directory's own parent.
            parent = parent.rsplit("/", 1)[0] if "/" in parent else ""
        depth = 0 if not parent else parent.count("/") + 1
        return depth < maximum

    def _finalize(self, discovery: MediaDiscovery, claim_token: str | None) -> MediaDiscovery:
        """Freeze the discovered sources and hand them to the existing admission."""

        # The frozen manifest is exactly one source per admitted
        # Storage/ResourceLibrary/source path, whatever an earlier record or a
        # repeated provider page may have recorded.
        unique_sources = deduplicate_sources(discovery.sources)
        sources = tuple(ManualSourceIdentity.from_document(value) for value in unique_sources)
        now = self._clock()
        if not sources:
            return self._fail(discovery, claim_token, "selection_empty")
        # The intent projection is *built* here but never persisted on its own:
        # it is inserted by the same repository transaction that links it to
        # this discovery.  A concurrent, repeated or lost-response finalize
        # therefore converges on one linked intent instead of committing an
        # orphan intent before the discovery link wins its version CAS.
        preparer = getattr(self._intent_service, "prepare_from_sources", None)
        if not callable(preparer):
            return self._fail(discovery, claim_token, "intent_unavailable")
        try:
            intent, audit = preparer(
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
        return self._persist_frozen(updated, intent, audit, expected_version=discovery.version)

    def _persist_frozen(
        self,
        discovery: MediaDiscovery,
        intent,
        audit,
        *,
        expected_version: int,
    ) -> MediaDiscovery:
        """Publish the discovery link and its intent as one durable outcome.

        The repository commits both in a single transaction with a version-CAS
        plus one-shot ``intent_id IS NULL`` guard, so only the request that
        wins the discovery transition ever creates an intent.  A losing,
        repeated or lost-response concurrent finalize therefore converges on
        the one linked intent instead of leaving orphan work.  A repository
        that cannot offer that atomic linkage fails closed rather than
        committing an orphan intent or a dangling link.
        """

        linker = getattr(self._repository, "create_manual_intent_for_discovery", None)
        if not callable(linker):
            raise DiscoveryUnavailable("durable media discovery intent linkage is unavailable")
        linked, _ = linker(
            discovery,
            expected_version=expected_version,
            intent=intent,
            items=intent.items,
            audit=audit,
        )
        return linked

    def _cancel(
        self,
        discovery: MediaDiscovery,
        claim_token: str,
        *,
        observations: tuple[DiscoveryObservation, ...] = (),
    ) -> MediaDiscovery:
        """Record a cooperative cancellation that preserves every known finding.

        The transition is settled under the exact current claim, so a Worker
        whose lease was already taken over can never cancel the successor's
        work, and the settlement releases the claim in the same transaction.
        A returning owner that already completed bounded observations passes
        them here so the accepted cancellation keeps that work durable instead
        of discarding it.
        """

        now = self._clock()
        updated = replace(
            discovery,
            status=DiscoveryStatus.CANCELLED,
            version=discovery.version + 1,
            cancel_requested=True,
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
        return self._settle_control(
            updated,
            expected_version=discovery.version,
            claim_token=claim_token,
            observations=observations,
        )

    def _publish_paused(
        self,
        discovery: MediaDiscovery,
        claim_token: str,
        message: str = "",
        *,
        observations: tuple[DiscoveryObservation, ...] = (),
    ) -> MediaDiscovery:
        """Acknowledge a cooperative pause at a safe boundary under the live claim.

        A Worker that no longer owns the claim never reaches this method: the
        caller stops with ``DiscoveryOwnershipLost`` instead, so a stale owner
        can never pause the successor's work or leave it without a native
        continuation.  A returning owner that already completed bounded work
        passes its counters, findings, manifest, stability observations and
        monotonic material refusals through the same settlement, so an accepted
        pause acknowledges the pause without resetting consumed budgets.
        """

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
        return self._settle_control(
            updated,
            expected_version=discovery.version,
            claim_token=claim_token,
            observations=observations,
        )

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
        return self._settle_control(
            updated, expected_version=discovery.version, claim_token=claim_token
        )

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
            # A pause stays cooperative: the Worker acknowledges it at its next
            # safe boundary.  The request itself must survive a concurrent
            # Worker publication, so it is written by the operator-owned path
            # that never touches the live claim.
            return self._persist(updated, expected_version=expected_version)
        # Cancellation is settled here, atomically, as one terminal
        # acknowledgement: the record, the request flag and the claim release
        # are a single transaction.  A cancellation can therefore never be left
        # as an open record that no Worker is allowed to claim again, and an
        # in-flight Worker that is still holding the old claim stops on its next
        # fenced write without touching this outcome.  Every finding already
        # durable is preserved; no execution authority is created.
        cancelled = replace(
            discovery,
            status=DiscoveryStatus.CANCELLED,
            version=discovery.version + 1,
            cancel_requested=True,
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
        return self._settle_control(cancelled, expected_version=expected_version)

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
        claim_token: str | None = None,
        observations: tuple[DiscoveryObservation, ...] = (),
    ) -> MediaDiscovery:
        recorder = getattr(self._repository, "record_media_discovery_progress", None)
        if callable(recorder):
            return recorder(
                discovery,
                expected_version=expected_version,
                claim_token=claim_token,
                observations=observations,
            )
        updater = getattr(self._repository, "update_media_discovery", None)
        if callable(updater):
            return updater(discovery, expected_version=expected_version)
        raise DiscoveryUnavailable("durable media discovery storage is unavailable")

    def _settle_control(
        self,
        discovery: MediaDiscovery,
        *,
        expected_version: int,
        claim_token: str | None = None,
        observations: tuple[DiscoveryObservation, ...] = (),
    ) -> MediaDiscovery:
        """Settle one boundary and release the claim as one durable outcome.

        Status, progress, the stability observations that were part of the same
        atomic write and the claim release are one transaction, so an accepted
        cancellation or acknowledged pause can never leave an open record that
        no Worker is allowed to claim again, and can never discard the bounded
        work the returning owner had already completed.  When ``claim_token`` is
        supplied the settlement is fenced by the exact current claim, so a
        Worker that already lost its lease cannot pause, fail or cancel the
        successor's work.
        """

        settler = getattr(self._repository, "settle_media_discovery_control", None)
        if callable(settler):
            return settler(
                discovery,
                expected_version=expected_version,
                claim_token=claim_token,
                observations=observations,
            )
        return self._persist(
            discovery,
            expected_version=expected_version,
            claim_token=claim_token,
            observations=observations,
        )

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
    def _admission_request_id(value: object) -> str | None:
        """Validate one optional caller-generated admission request identity.

        It is a canonical lowercase UUID, exactly like the existing Delete
        request identity: a caller-supplied value is durable reconciliation
        proof, so a malformed one is refused rather than stored.  ``None`` is
        legal and means the caller offered no such proof.
        """

        if value is None:
            return None
        if not isinstance(value, str):
            raise DiscoveryError(
                "the discovery admission request identity is invalid",
                code="invalid_request",
                next_action="refresh the Files page and start the discovery again",
            )
        try:
            parsed = UUID(value)
        except (TypeError, ValueError, AttributeError):
            parsed = None
        if parsed is None or str(parsed) != value:
            raise DiscoveryError(
                "the discovery admission request identity is invalid",
                code="invalid_request",
                next_action="refresh the Files page and start the discovery again",
            )
        return str(parsed)

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


class _ObservedDirectoryStorage:
    """A read-only view of one already-observed directory's entries.

    The authoritative attachment association must be evaluated over the exact
    same-directory entry set the production ``AttachmentDiscovery`` expects.
    This adapter publishes only the entries the walk already observed from live
    Storage and refuses every mutation, so reuse of the production matcher adds
    no new Storage read and no mutation capability.
    """

    def __init__(self, storage_id: str, entries: tuple[StorageEntry, ...]) -> None:
        self.storage_id = storage_id
        self._entries = tuple(entries)

    @property
    def name(self) -> str:
        return "discovery-observed-directory"

    @property
    def read_only(self) -> bool:
        return True

    def list(self, path: str):
        return self._entries

    def list_page(self, path: str, *, limit: int, cursor: str | None = None):
        from mediaflow.domain.storage import StoragePage

        return StoragePage(self._entries[:limit], None)

    def stat(self, path: str):
        for entry in self._entries:
            if entry.path == path:
                return entry
        raise _DiscoveryMutationError("the observed directory has no such entry")

    def exists(self, path: str) -> bool:
        return any(entry.path == path for entry in self._entries)

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
