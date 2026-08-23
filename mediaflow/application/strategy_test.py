from __future__ import annotations

import posixpath
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import PurePosixPath
from typing import Any, BinaryIO

from mediaflow.application.classification import (
    ClassificationPolicyRegistry,
    ClassificationPreviewService,
)
from mediaflow.application.media_parser import MediaParserService
from mediaflow.application.metadata import (
    CandidateMatcher,
    MetadataIdentificationService,
    MetadataPolicyRegistry,
    MetadataProviderRegistry,
)
from mediaflow.application.naming import NamingPolicyRegistry, NamingPreviewService
from mediaflow.application.nfo_parser import StorageNfoEnricher
from mediaflow.application.organizer import OrganizePlanner, OrganizerExecutor, PlanningError
from mediaflow.application.policies import RecognitionTypePolicyResolver
from mediaflow.application.recognition import RecognitionRuleEngine
from mediaflow.domain.classification import (
    ClassificationContext,
    ClassificationError,
    ClassificationPolicy,
    ClassificationResult,
)
from mediaflow.domain.classification_review import ClassificationSelection
from mediaflow.domain.library import MediaLibrary, ResourceLibrary
from mediaflow.domain.metadata import (
    EpisodeIdentity,
    MediaCandidate,
    MediaIdentity,
    MediaQueryType,
    MediaType,
    MetadataIdentificationResult,
    MetadataPolicy,
    ProviderCapabilities,
)
from mediaflow.domain.metadata_correction import MetadataCorrectionSelection
from mediaflow.domain.metadata_review import MetadataSelection
from mediaflow.domain.naming import NamingContext, NamingError, NamingPolicy, NamingResult
from mediaflow.domain.organizer import ExecutionResult, OrganizePlan, OrganizePolicy
from mediaflow.domain.parser import FileContext, ParseResult
from mediaflow.domain.recognition import (
    RecognitionContext,
    RecognitionReason,
    RecognitionResult,
    RecognitionRule,
    RecognitionStatus,
    RecognitionType,
    RecognitionTypePolicy,
    ResolvedRecognitionPolicy,
)
from mediaflow.domain.recognition_review import RecognitionSelection
from mediaflow.domain.scanner import CancellationToken, FileScanStatus, ScanError, Scanner
from mediaflow.domain.storage import Storage, StorageCapabilities, StorageEntry, WriteSource


class StrategyMutationError(RuntimeError):
    pass


class StrategyConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class StrategyTestConfiguration:
    recognition_types: tuple[RecognitionType, ...]
    recognition_rules: tuple[RecognitionRule, ...]
    recognition_type_policies: tuple[RecognitionTypePolicy, ...]
    metadata_policies: tuple[MetadataPolicy, ...]
    naming_policies: tuple[NamingPolicy, ...] = ()
    classification_policies: tuple[ClassificationPolicy, ...] = ()
    organize_policies: tuple[OrganizePolicy, ...] = ()


class ReadOnlyStrategyStorage:
    """Delegates reads but fails immediately on every Storage mutation."""

    def __init__(self, storage: Storage) -> None:
        self._storage = storage
        self.mutation_calls = {
            name: 0
            for name in (
                "Write",
                "CreateDirectory",
                "Move",
                "Copy",
                "Delete",
                "HardLink",
                "SoftLink",
            )
        }

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
    def capabilities(self) -> StorageCapabilities:
        return StorageCapabilities()

    def list(self, path: str):
        return self._storage.list(path)

    def stat(self, path: str) -> StorageEntry:
        return self._storage.stat(path)

    def exists(self, path: str) -> bool:
        return self._storage.exists(path)

    def read(self, path: str) -> BinaryIO:
        return self._storage.read(path)

    def write(self, path: str, data: WriteSource, *, overwrite: bool = False) -> None:
        self._reject("Write")

    def create_directory(self, path: str) -> None:
        self._reject("CreateDirectory")

    def move(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self._reject("Move")

    def copy(self, source: str, target: str, *, overwrite: bool = False) -> None:
        self._reject("Copy")

    def delete(self, path: str) -> None:
        self._reject("Delete")

    def hard_link(self, source: str, target: str) -> None:
        self._reject("HardLink")

    def soft_link(self, source: str, target: str) -> None:
        self._reject("SoftLink")

    def _reject(self, operation: str) -> None:
        self.mutation_calls[operation] += 1
        raise StrategyMutationError(f"strategy-test forbids Storage mutation: {operation}")


@dataclass(frozen=True)
class StrategyTestResult:
    path: str
    parsed: ParseResult
    recognition: RecognitionResult
    policy: ResolvedRecognitionPolicy | None
    metadata_policy: MetadataPolicy | None = None
    metadata: MetadataIdentificationResult | None = None
    naming: NamingResult | None = None
    naming_error: str | None = None
    naming_requested: bool = False
    classification: ClassificationResult | None = None
    classification_error: str | None = None
    classification_requested: bool = False
    organize_plan: OrganizePlan | None = None
    plan_error: str | None = None
    plan_requested: bool = False
    execution: ExecutionResult | None = None

    @property
    def recognition_type_preserved(self) -> bool:
        if self.recognition.recognition_type_id is None or self.policy is None:
            return False
        if self.policy.recognition_type_id != self.recognition.recognition_type_id:
            return False
        return (
            self.metadata is None
            or self.metadata.recognition_type_id == self.recognition.recognition_type_id
        )


@dataclass(frozen=True)
class CaseResult:
    name: str
    passed: bool
    expected: dict[str, Any]
    actual: dict[str, Any]
    strategy: StrategyTestResult


@dataclass(frozen=True)
class CaseRunSummary:
    total: int
    passed: int
    failed: int
    skipped: int
    cases: tuple[CaseResult, ...]


@dataclass(frozen=True)
class DirectoryStrategyItem:
    path: str
    strategy: StrategyTestResult | None = None
    error: str | None = None


@dataclass(frozen=True)
class DirectoryStrategySummary:
    items: tuple[DirectoryStrategyItem, ...]
    scan_errors: tuple[ScanError, ...]
    total: int
    matched: int
    need_confirm: int
    ambiguous: int
    not_found: int
    unrecognized: int
    errors: int
    mutation_calls: dict[str, int]
    naming_ok: int = 0
    naming_warnings: int = 0
    metadata_need_confirm: int = 0
    metadata_not_found: int = 0
    naming_errors: int = 0
    other_errors: int = 0
    show_naming: bool = False
    show_classification: bool = False
    show_plan: bool = False


class StrategyDirectoryRunner:
    """Feeds Scanner discoveries through the existing single-item strategy pipeline."""

    def __init__(
        self,
        scanner: Scanner,
        library: ResourceLibrary,
        strategy: StrategyTestRunner,
        storage_guard: ReadOnlyStrategyStorage,
    ) -> None:
        self._scanner = scanner
        self._library = library
        self._strategy = strategy
        self._storage_guard = storage_guard

    def run(
        self,
        *,
        live_metadata: bool = False,
        limit: int | None = None,
        show_naming: bool = False,
        show_classification: bool = False,
        show_plan: bool = False,
    ) -> DirectoryStrategySummary:
        if limit is not None and limit < 1:
            raise ValueError("directory limit must be positive")
        self._strategy.validate_configuration(
            live_metadata=live_metadata,
            show_naming=show_naming or show_plan,
            show_classification=show_classification or show_plan,
        )
        cancellation = CancellationToken()
        items: list[DirectoryStrategyItem] = []

        def discovered(file) -> None:
            if file.status is not FileScanStatus.READY:
                return
            path = "/" + file.path.lstrip("/")
            try:
                result = self._strategy.run_path(
                    path,
                    live_metadata=live_metadata,
                    show_naming=show_naming,
                    show_classification=show_classification,
                    show_plan=show_plan,
                    resource_library_id=self._library.library_id,
                    storage_id=self._library.storage_id,
                    storage_path=file.path,
                    source_storage=self._storage_guard,
                )
                items.append(DirectoryStrategyItem(path, strategy=result))
            except Exception as error:  # isolate a bad media item without losing the scan
                items.append(DirectoryStrategyItem(path, error=str(error)))
            if limit is not None and len(items) >= limit:
                cancellation.cancel()

        scan = self._scanner.scan(
            self._library, cancellation=cancellation, on_discovered=discovered
        )
        if any(self._storage_guard.mutation_calls.values()):
            raise StrategyMutationError("strategy-test directory scan detected a Storage mutation")

        matched = need_confirm = ambiguous = not_found = unrecognized = item_errors = 0
        for item in items:
            if item.error or item.strategy is None:
                item_errors += 1
                continue
            strategy = item.strategy
            if strategy.recognition.status.value == "unrecognized":
                unrecognized += 1
            elif strategy.recognition.status.value == "ambiguous":
                ambiguous += 1
            elif strategy.metadata is None or strategy.metadata.status.value == "matched":
                matched += 1
            elif strategy.metadata.status.value == "need_confirm":
                need_confirm += 1
            elif strategy.metadata.status.value == "ambiguous":
                ambiguous += 1
            elif strategy.metadata.status.value == "not_found":
                not_found += 1
            else:
                item_errors += 1
        naming_ok = naming_warnings = metadata_need_confirm = metadata_not_found = 0
        naming_errors = 0
        if show_naming:
            for item in items:
                strategy = item.strategy
                if item.error or strategy is None:
                    continue
                if strategy.metadata and strategy.metadata.status.value == "need_confirm":
                    metadata_need_confirm += 1
                elif strategy.metadata and strategy.metadata.status.value == "not_found":
                    metadata_not_found += 1
                elif strategy.naming_error:
                    naming_errors += 1
                elif strategy.naming and strategy.naming.warnings:
                    naming_warnings += 1
                elif strategy.naming:
                    naming_ok += 1
                elif strategy.metadata is None and strategy.recognition.recognition_type_id:
                    naming_warnings += 1
        other_errors = item_errors + len(scan.errors)
        classification_errors = sum(
            1 for item in items if item.strategy is not None and item.strategy.classification_error
        )
        plan_errors = sum(
            1 for item in items if item.strategy is not None and item.strategy.plan_error
        )
        errors = other_errors + naming_errors + classification_errors + plan_errors
        return DirectoryStrategySummary(
            tuple(items),
            scan.errors,
            len(items),
            matched,
            need_confirm,
            ambiguous,
            not_found,
            unrecognized,
            errors,
            dict(self._storage_guard.mutation_calls),
            naming_ok,
            naming_warnings,
            metadata_need_confirm,
            metadata_not_found,
            naming_errors,
            other_errors,
            show_naming,
            show_classification,
            show_plan,
        )


class StrategyTestRunner:
    def __init__(
        self,
        parser: MediaParserService,
        recognition: RecognitionRuleEngine,
        policy_resolver: RecognitionTypePolicyResolver,
        metadata_policies: MetadataPolicyRegistry,
        naming_policies: NamingPolicyRegistry,
        recognition_type_policies: tuple[RecognitionTypePolicy, ...],
        providers: MetadataProviderRegistry | None = None,
        matcher: CandidateMatcher | None = None,
        storage_guard: ReadOnlyStrategyStorage | None = None,
        classification_policies: ClassificationPolicyRegistry | None = None,
        storages: Mapping[str, Storage] | None = None,
        nfo_enricher: StorageNfoEnricher | None = None,
        recognition_types: tuple[RecognitionType, ...] = (),
    ) -> None:
        self._parser = parser
        self._recognition = recognition
        self._policy_resolver = policy_resolver
        self._metadata_policies = metadata_policies
        self._naming_policies = naming_policies
        self._recognition_type_policies = recognition_type_policies
        self._providers = providers
        self._matcher = matcher or CandidateMatcher()
        self._storage_guard = storage_guard
        self._classification_policies = classification_policies or ClassificationPolicyRegistry(())
        self._storages = dict(storages or {})
        self._nfo_enricher = nfo_enricher or StorageNfoEnricher()
        self._recognition_types = {item.type_id: item for item in recognition_types}

    def validate_configuration(
        self,
        *,
        live_metadata: bool = False,
        show_naming: bool = False,
        show_classification: bool = False,
        show_plan: bool = False,
    ) -> None:
        """Validate global policy/provider links before processing any media item."""
        for type_policy in self._recognition_type_policies:
            try:
                metadata_policy = self._metadata_policies.resolve(type_policy.metadata_policy_id)
            except LookupError as error:
                raise StrategyConfigurationError(
                    f"MetadataPolicy {type_policy.metadata_policy_id!r} referenced by "
                    f"RecognitionTypePolicy {type_policy.policy_id!r} is not configured."
                ) from error
            if live_metadata:
                if self._providers is None:
                    raise StrategyConfigurationError(
                        "live metadata mode requires a configured MetadataProvider registry"
                    )
                try:
                    self._providers.resolve(metadata_policy.provider_id)
                except LookupError as error:
                    raise StrategyConfigurationError(
                        f"MetadataProvider {metadata_policy.provider_id!r} referenced by "
                        f"MetadataPolicy {metadata_policy.policy_id!r} is not configured."
                    ) from error
            if show_naming or show_plan:
                try:
                    self._naming_policies.resolve(type_policy.naming_policy_id)
                except NamingError as error:
                    raise StrategyConfigurationError(
                        f"NamingPolicy {type_policy.naming_policy_id!r} referenced by "
                        f"RecognitionTypePolicy {type_policy.policy_id!r} is not configured."
                    ) from error
            if show_classification or show_plan:
                try:
                    self._classification_policies.resolve(type_policy.classification_policy_id)
                except ClassificationError as error:
                    raise StrategyConfigurationError(
                        f"ClassificationPolicy {type_policy.classification_policy_id!r} "
                        f"referenced by RecognitionTypePolicy {type_policy.policy_id!r} "
                        "is not configured."
                    ) from error

    def run_path(
        self,
        path: str,
        *,
        live_metadata: bool = False,
        show_naming: bool = False,
        show_classification: bool = False,
        show_plan: bool = False,
        resource_library_id: str = "strategy-test",
        storage_id: str = "strategy-test",
        metadata_selection: MetadataSelection | None = None,
        metadata_correction: MetadataCorrectionSelection | None = None,
        classification_selection: ClassificationSelection | None = None,
        recognition_selection: RecognitionSelection | None = None,
        storage_path: str | None = None,
        source_storage: Storage | None = None,
    ) -> StrategyTestResult:
        self.validate_configuration(
            live_metadata=live_metadata,
            show_naming=show_naming or show_plan,
            show_classification=show_classification or show_plan,
            show_plan=show_plan,
        )
        context = file_context_from_path(
            path,
            resource_library_id=resource_library_id,
            storage_id=storage_id,
        )
        parsed = self._parser.parse(context)
        storage = source_storage or self._storages.get(storage_id)
        if storage is not None and storage_path is not None:
            nfo_context = FileContext(
                storage_id,
                resource_library_id,
                storage_path,
                context.filename,
                context.parent_directories,
                context.extension,
                posixpath.dirname(storage_path),
                context.size,
                context.modified_at,
            )
            parsed = self._nfo_enricher.enrich(storage, nfo_context, parsed)
        recognition = self._recognition.recognize(RecognitionContext(context, parsed))
        if recognition_selection is not None:
            if recognition.status is not RecognitionStatus.UNRECOGNIZED:
                raise StrategyConfigurationError(
                    "manual RecognitionType selection requires an Unrecognized result"
                )
            selected = self._recognition_types.get(recognition_selection.recognition_type_id)
            if selected is None or not selected.enabled:
                raise StrategyConfigurationError(
                    "manual RecognitionType is no longer enabled or configured"
                )
            recognition = RecognitionResult(
                selected,
                "manual-review",
                1.0,
                RecognitionStatus.MATCHED,
                score=100,
                reasons=(RecognitionReason("MANUAL_SELECTION", "Selected by manual review"),),
            )
        resolved = (
            self._policy_resolver.resolve(recognition.recognition_type_id)
            if recognition.recognition_type_id
            else None
        )
        metadata_policy = None
        metadata = None
        if resolved:
            try:
                metadata_policy = self._metadata_policies.resolve(resolved.metadata_policy_id)
            except LookupError as error:
                raise StrategyConfigurationError(
                    f"MetadataPolicy {resolved.metadata_policy_id!r} referenced by "
                    f"RecognitionTypePolicy {resolved.type_policy_id!r} is not configured."
                ) from error
        if (
            metadata_selection is not None or metadata_correction is not None
        ) and not live_metadata:
            raise StrategyConfigurationError("metadata selection requires live metadata mode")
        if metadata_selection is not None and metadata_correction is not None:
            raise StrategyConfigurationError("metadata selection and correction cannot be combined")
        if live_metadata and resolved is not None:
            if self._providers is None:
                raise StrategyConfigurationError(
                    "live metadata mode requires a configured MetadataProvider registry"
                )
            identification = MetadataIdentificationService(self._providers, self._matcher)
            if metadata_correction is not None:
                if metadata_correction.recognition_type != recognition.recognition_type_id:
                    raise StrategyConfigurationError(
                        "resolved metadata correction RecognitionType no longer matches"
                    )
                if metadata_correction.metadata_policy_id != resolved.metadata_policy_id:
                    raise StrategyConfigurationError(
                        "resolved metadata correction MetadataPolicy no longer matches"
                    )
                if metadata_correction.provider != metadata_policy.provider_id:
                    raise StrategyConfigurationError(
                        "resolved metadata correction provider no longer matches"
                    )
                try:
                    corrected_type = MediaType(metadata_correction.media_type)
                except ValueError as error:
                    raise StrategyConfigurationError(
                        "resolved metadata correction media type is invalid"
                    ) from error
                if metadata_correction.provider_id:
                    metadata = identification.identify_by_provider_id(
                        recognition,
                        metadata_correction.provider_id,
                        corrected_type,
                        metadata_policy,
                    )
                else:
                    corrected = replace(
                        parsed,
                        title_candidate=metadata_correction.query or parsed.title_candidate,
                        year=metadata_correction.year,
                    )
                    metadata = identification.identify(
                        recognition,
                        corrected,
                        metadata_policy,
                        media_type_override=corrected_type,
                    )
            elif metadata_selection is not None:
                if metadata_selection.recognition_type != recognition.recognition_type_id:
                    raise StrategyConfigurationError(
                        "resolved metadata selection RecognitionType no longer matches"
                    )
                if metadata_selection.metadata_policy_id != resolved.metadata_policy_id:
                    raise StrategyConfigurationError(
                        "resolved metadata selection MetadataPolicy no longer matches"
                    )
                if metadata_selection.provider != metadata_policy.provider_id:
                    raise StrategyConfigurationError(
                        "resolved metadata selection provider no longer matches"
                    )
                try:
                    selected_type = MediaType(metadata_selection.media_type)
                except ValueError as error:
                    raise StrategyConfigurationError(
                        "resolved metadata selection media type is invalid"
                    ) from error
                if metadata_policy.query_type is MediaQueryType.NONE:
                    raise StrategyConfigurationError(
                        "resolved metadata selection MetadataPolicy no longer permits lookup"
                    )
                expected_type = {
                    MediaQueryType.MOVIE: MediaType.MOVIE,
                    MediaQueryType.TV: MediaType.TV,
                }.get(metadata_policy.query_type)
                if expected_type is not None and selected_type is not expected_type:
                    raise StrategyConfigurationError(
                        "resolved metadata selection media type no longer matches"
                    )
                metadata = identification.identify_by_provider_id(
                    recognition,
                    metadata_selection.provider_id,
                    selected_type,
                    metadata_policy,
                )
            else:
                metadata = identification.identify(recognition, parsed, metadata_policy)
        naming = None
        naming_error = None
        if (show_naming or show_plan) and resolved and metadata and metadata.identity:
            try:
                naming = NamingPreviewService(self._naming_policies).preview(
                    NamingContext(
                        recognition.recognition_type_id,
                        metadata.identity,
                        parsed,
                        parsed.original_filename,
                        parsed.extension,
                    ),
                    resolved.naming_policy_id,
                )
            except NamingError as error:
                naming_error = str(error)
        classification = None
        classification_error = None
        if (show_classification or show_plan) and resolved and metadata and metadata.identity:
            try:
                preview = ClassificationPreviewService(self._classification_policies)
                classification_context = ClassificationContext(
                    recognition.recognition_type,
                    metadata.identity,
                    parsed,
                    naming,
                )
                if classification_selection is not None:
                    if classification_selection.recognition_type != recognition.recognition_type_id:
                        raise StrategyConfigurationError(
                            "resolved classification selection RecognitionType no longer matches"
                        )
                    if (
                        classification_selection.classification_policy_id
                        != resolved.classification_policy_id
                    ):
                        raise StrategyConfigurationError(
                            "resolved classification selection policy no longer matches"
                        )
                    policy = self._classification_policies.resolve(
                        resolved.classification_policy_id
                    )
                    rule = next(
                        (
                            value
                            for value in policy.rules
                            if value.enabled and value.rule_id == classification_selection.rule_id
                        ),
                        None,
                    )
                    if (
                        rule is None
                        or rule.media_library_id != classification_selection.media_library_id
                        or rule.relative_category_path != classification_selection.relative_path
                    ):
                        raise StrategyConfigurationError(
                            "resolved classification selection rule no longer matches"
                        )
                    classification = preview.select_configured_rule(
                        classification_context,
                        resolved.classification_policy_id,
                        classification_selection.rule_id,
                    )
                else:
                    classification = preview.preview(
                        classification_context, resolved.classification_policy_id
                    )
            except ClassificationError as error:
                classification_error = str(error)
        organize_plan = None
        plan_error = None
        if show_plan and resolved and metadata and metadata.identity and naming and classification:
            try:
                library_name = classification.library or classification.media_library_id
                organize_plan = OrganizePlanner().plan(
                    source_storage_id=storage_id,
                    source=path,
                    recognition=recognition,
                    type_policy=next(
                        item
                        for item in self._recognition_type_policies
                        if item.policy_id == resolved.type_policy_id
                    ),
                    media_library=MediaLibrary(
                        classification.media_library_id,
                        library_name,
                        "strategy-plan-target",
                        library_name,
                    ),
                    naming=naming,
                    classification=classification,
                    media_identity=metadata.identity,
                )
            except (PlanningError, StopIteration, ValueError) as error:
                plan_error = str(error)
        execution = OrganizerExecutor().execute(organize_plan, {}) if organize_plan else None
        result = StrategyTestResult(
            path,
            parsed,
            recognition,
            resolved,
            metadata_policy,
            metadata,
            naming,
            naming_error,
            show_naming,
            classification,
            classification_error,
            show_classification or show_plan,
            organize_plan,
            plan_error,
            show_plan,
            execution,
        )
        if self._storage_guard and any(self._storage_guard.mutation_calls.values()):
            raise StrategyMutationError("strategy-test detected a Storage mutation")
        return result

    def classification_policy(self, policy_id: str) -> ClassificationPolicy:
        return self._classification_policies.resolve(policy_id)

    def run_cases(self, document: Any, *, show_naming: bool = False) -> CaseRunSummary:
        raw_cases = document.get("cases") if isinstance(document, dict) else document
        if not isinstance(raw_cases, list):
            raise ValueError("strategy case file must contain a list or a 'cases' list")
        results = []
        skipped = 0
        for index, item in enumerate(raw_cases):
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise ValueError(f"strategy case {index} is invalid")
            if item.get("skip"):
                skipped += 1
                continue
            runner = self
            live = bool(item.get("candidates") is not None)
            if live:
                provider = SyntheticMetadataProvider.from_case(item)
                runner = StrategyTestRunner(
                    self._parser,
                    self._recognition,
                    self._policy_resolver,
                    self._metadata_policies,
                    self._naming_policies,
                    self._recognition_type_policies,
                    MetadataProviderRegistry((provider,)),
                    self._matcher,
                    self._storage_guard,
                    self._classification_policies,
                )
            naming_expected = isinstance(item.get("expect"), dict) and "naming" in item["expect"]
            strategy = runner.run_path(
                item["path"],
                live_metadata=live,
                show_naming=show_naming or naming_expected,
                resource_library_id=item.get("resourceLibraryId", "strategy-test"),
            )
            expected = item.get("expect", {})
            if not isinstance(expected, dict):
                raise ValueError(f"strategy case {index} expect must be an object")
            actual = flatten_result(strategy)
            passed = all(actual.get(key) == value for key, value in expected.items())
            results.append(
                CaseResult(
                    item.get("name", f"case-{index + 1}"), passed, expected, actual, strategy
                )
            )
        passed = sum(item.passed for item in results)
        return CaseRunSummary(
            len(raw_cases), passed, len(results) - passed, skipped, tuple(results)
        )


class SyntheticMetadataProvider:
    provider_id = "tmdb"
    capabilities = ProviderCapabilities(True, True, True, True, False, False, True)

    def __init__(
        self,
        candidates: tuple[MediaCandidate, ...],
        episodes: tuple[int, ...] = (),
    ) -> None:
        self._candidates = candidates
        self._episodes = episodes
        self.calls = 0

    @classmethod
    def from_case(cls, case: dict[str, Any]) -> SyntheticMetadataProvider:
        media_type = MediaType(case.get("mediaType", "movie"))
        candidates = tuple(
            MediaCandidate(
                "tmdb",
                str(item["providerId"]),
                media_type,
                item["title"],
                item.get("originalTitle"),
                item.get("year"),
                alternative_titles=tuple(item.get("alternativeTitles", ())),
                translated_titles=tuple(item.get("translatedTitles", ())),
                genres=tuple(item.get("genres", ())),
                countries=tuple(item.get("countries", ())),
                languages=tuple(item.get("languages", ())),
                keywords=tuple(item.get("keywords", ())),
            )
            for item in case.get("candidates", ())
        )
        return cls(candidates, tuple(case.get("availableEpisodes", ())))

    def search_movie(self, query, policy=None, **kwargs):
        self.calls += 1
        return self._candidates

    def search_tv(self, query, policy=None, **kwargs):
        self.calls += 1
        return self._candidates

    def get_movie(self, provider_id, policy=None, **kwargs):
        self.calls += 1
        candidate = self._by_id(provider_id)
        return MediaIdentity(
            "tmdb",
            provider_id,
            MediaType.MOVIE,
            candidate.title,
            candidate.original_title,
            candidate.year,
            alternative_titles=candidate.alternative_titles,
            translated_titles=candidate.translated_titles,
            release_date=candidate.release_date,
            canonical_release_date=candidate.canonical_release_date,
            regional_release_date=candidate.regional_release_date,
            genres=candidate.genres,
            countries=candidate.countries,
            languages=candidate.languages,
            keywords=candidate.keywords,
            overview=candidate.overview,
        )

    def get_tv(self, provider_id, policy=None, **kwargs):
        self.calls += 1
        candidate = self._by_id(provider_id)
        return MediaIdentity(
            "tmdb",
            provider_id,
            MediaType.TV,
            candidate.title,
            candidate.original_title,
            candidate.year,
            alternative_titles=candidate.alternative_titles,
            translated_titles=candidate.translated_titles,
            release_date=candidate.release_date,
            canonical_release_date=candidate.canonical_release_date,
            regional_release_date=candidate.regional_release_date,
            genres=candidate.genres,
            countries=candidate.countries,
            languages=candidate.languages,
            keywords=candidate.keywords,
            overview=candidate.overview,
        )

    def get_season(self, provider_id, season, policy=None, **kwargs):
        self.calls += 1
        episodes = tuple(EpisodeIdentity(number, f"Episode {number}") for number in self._episodes)
        return MediaIdentity(
            "tmdb",
            provider_id,
            MediaType.TV,
            f"Season {season}",
            season=season,
            episode_metadata=episodes,
        )

    def get_episode(self, provider_id, season, episode, policy=None, **kwargs):
        self.calls += 1
        return MediaIdentity(
            "tmdb", provider_id, MediaType.TV, f"Episode {episode}", season=season, episode=episode
        )

    def find_by_external_id(self, source, external_id, policy=None, **kwargs):
        self.calls += 1
        return ()

    def _by_id(self, provider_id: str) -> MediaCandidate:
        return next(item for item in self._candidates if item.provider_id == provider_id)


def strategy_runner_from_configuration(
    configuration: StrategyTestConfiguration,
    providers: MetadataProviderRegistry | None = None,
    storage_guard: ReadOnlyStrategyStorage | None = None,
    storages: Mapping[str, Storage] | None = None,
) -> StrategyTestRunner:
    metadata_policies = MetadataPolicyRegistry(configuration.metadata_policies)
    naming_policies = NamingPolicyRegistry(configuration.naming_policies)
    classification_policies = ClassificationPolicyRegistry(configuration.classification_policies)
    return StrategyTestRunner(
        MediaParserService(),
        RecognitionRuleEngine(configuration.recognition_types, configuration.recognition_rules),
        RecognitionTypePolicyResolver(
            configuration.recognition_type_policies,
            metadata_policies=metadata_policies.references(),
            naming_policies={policy.policy_id: policy for policy in configuration.naming_policies}
            or None,
            classification_policies=classification_policies.references() or None,
        ),
        metadata_policies,
        naming_policies,
        configuration.recognition_type_policies,
        providers,
        storage_guard=storage_guard,
        classification_policies=classification_policies,
        storages=storages,
        recognition_types=configuration.recognition_types,
    )


def default_strategy_runner(
    providers: MetadataProviderRegistry | None = None,
    storage_guard: ReadOnlyStrategyStorage | None = None,
) -> StrategyTestRunner:
    """Compatibility bootstrap; development policy data lives outside application logic."""
    from mediaflow.infrastructure.strategy_configuration import smoke_strategy_configuration

    return strategy_runner_from_configuration(
        smoke_strategy_configuration(), providers, storage_guard
    )


def file_context_from_path(
    path: str,
    *,
    resource_library_id: str = "strategy-test",
    storage_id: str = "strategy-test",
) -> FileContext:
    normalized = path.replace("\\", "/")
    pure = PurePosixPath(normalized)
    filename = pure.name
    directories = tuple(part for part in pure.parent.parts if part not in {"/", "."})
    return FileContext(
        storage_id,
        resource_library_id,
        normalized,
        filename,
        directories,
        pure.suffix.lstrip(".").lower(),
        str(pure.parent),
    )


def flatten_result(result: StrategyTestResult) -> dict[str, Any]:
    policy = result.policy
    metadata = result.metadata
    identity = metadata.identity if metadata else None
    naming = result.naming
    return {
        "recognitionType": result.recognition.recognition_type_id,
        "metadataPolicy": policy.metadata_policy_id if policy else None,
        "namingPolicy": policy.naming_policy_id if policy else None,
        "classificationPolicy": policy.classification_policy_id if policy else None,
        "organizePolicy": policy.organize_policy_id if policy else None,
        "title": identity.title if identity else result.parsed.title_candidate,
        "year": identity.year if identity else result.parsed.year,
        "season": result.parsed.season,
        "episode": result.parsed.episode,
        "episodes": list(result.parsed.episodes),
        "matchStatus": metadata.status.value if metadata else None,
        "selectedProviderId": metadata.identity.provider_id
        if metadata and metadata.identity
        else None,
        "provider": identity.provider if identity else None,
        "providerId": identity.provider_id if identity else None,
        "naming": {
            "directory": naming.directory,
            "directorySegments": list(naming.directory_segments),
            "filename": naming.filename,
        }
        if naming
        else None,
        "recognitionTypePreserved": result.recognition_type_preserved,
    }
