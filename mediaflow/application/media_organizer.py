from __future__ import annotations

import posixpath
from collections.abc import Callable
from dataclasses import dataclass

from mediaflow.application.library_pipeline import MediaLibraryResolver, ResourceLibraryScanner
from mediaflow.application.organizer import OrganizePlanner, OrganizerExecutor
from mediaflow.application.strategy_test import StrategyTestResult, StrategyTestRunner
from mediaflow.domain.history import OperationHistoryRecord, OperationHistoryRepository
from mediaflow.domain.library import MediaLibrary, ResourceLibrary
from mediaflow.domain.logging import Logger, LogLevel
from mediaflow.domain.organizer import ExecutionResult, ExecutionStatus, OrganizePlan
from mediaflow.domain.recognition import RecognitionTypePolicy
from mediaflow.domain.scanner import CancellationToken, FileScanStatus, ScanError, Scanner
from mediaflow.domain.storage import Storage


@dataclass(frozen=True)
class MediaOrganizerItemResult:
    source: str
    strategy: StrategyTestResult | None = None
    plan: OrganizePlan | None = None
    execution: ExecutionResult | None = None
    error: str | None = None


@dataclass(frozen=True)
class MediaOrganizerBatchResult:
    items: tuple[MediaOrganizerItemResult, ...]
    scan_errors: tuple[ScanError, ...] = ()

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def matched(self) -> int:
        return sum(
            item.strategy is not None
            and item.strategy.metadata is not None
            and item.strategy.metadata.identity is not None
            for item in self.items
        )

    @property
    def conflicts(self) -> int:
        return sum(bool(item.plan and item.plan.conflicts) for item in self.items)

    @property
    def moved(self) -> int:
        return sum(
            item.execution is not None
            and item.execution.status is ExecutionStatus.SUCCESS
            and item.execution.operation.value == "MOVE"
            for item in self.items
        )

    @property
    def failed(self) -> int:
        return len(self.scan_errors) + sum(
            bool(
                item.error
                or (
                    item.execution
                    and item.execution.status in {ExecutionStatus.FAILED, ExecutionStatus.PARTIAL}
                )
            )
            for item in self.items
        )


ProgressReporter = Callable[[int, int | None, str], None]


class MediaOrganizerService:
    """Thin orchestration over production stages; business decisions stay in their engines."""

    def __init__(
        self,
        strategy: StrategyTestRunner,
        scanner: Scanner,
        storages: dict[str, Storage],
        media_libraries: dict[str, MediaLibrary],
        type_policies: tuple[RecognitionTypePolicy, ...],
        history: OperationHistoryRepository,
        executor: OrganizerExecutor | None = None,
        source_display_roots: dict[str, str] | None = None,
        logger: Logger | None = None,
    ) -> None:
        self._strategy = strategy
        self._scanner = scanner
        self._storages = storages
        self._media_libraries = media_libraries
        self._media_library_resolver = MediaLibraryResolver(
            tuple(media_libraries.values()), storages
        )
        self._type_policies = {item.policy_id: item for item in type_policies}
        self._history = history
        self._executor = executor or OrganizerExecutor()
        self._source_display_roots = source_display_roots or {}
        self._logger = logger

    def process_file(
        self,
        source: str,
        *,
        resource_library: ResourceLibrary,
        storage_path: str,
        execute: bool = False,
    ) -> MediaOrganizerItemResult:
        try:
            strategy = self._strategy.run_path(
                source,
                live_metadata=True,
                show_naming=True,
                show_classification=True,
                resource_library_id=resource_library.library_id,
                storage_id=resource_library.storage_id,
            )
            self._log(
                LogLevel.DEBUG,
                "media parsed and recognized",
                source=source,
                title=strategy.parsed.title_candidate,
                recognition_type=strategy.recognition.recognition_type_id,
            )
            if not strategy.metadata or not strategy.metadata.identity:
                return self._failed(source, strategy, "metadata identity is unavailable")
            if not strategy.naming:
                return self._failed(source, strategy, strategy.naming_error or "naming failed")
            if not strategy.classification or not strategy.classification.media_library_id:
                return self._failed(
                    source, strategy, strategy.classification_error or "classification failed"
                )
            resolved_library = self._media_library_resolver.resolve(strategy.classification)
            media_library = resolved_library.media_library
            self._log(
                LogLevel.DEBUG,
                "metadata naming and classification completed",
                source=source,
                provider_id=strategy.metadata.identity.provider_id,
                naming=strategy.naming.filename,
                classification=strategy.classification.relative_path,
            )
            type_policy = self._type_policies[strategy.policy.type_policy_id]
            plan = OrganizePlanner().plan(
                source_storage_id=resource_library.storage_id,
                source=source,
                source_storage_path=storage_path,
                recognition=strategy.recognition,
                type_policy=type_policy,
                media_library=media_library,
                naming=strategy.naming,
                classification=strategy.classification,
                media_identity=strategy.metadata.identity,
                target_storage=resolved_library.storage,
            )
            execution = self._executor.execute(
                plan,
                self._storages,
                execute=execute,
                resolved_destination=(
                    f"{plan.destination_location.storage_id}:{plan.destination_location.path}"
                    if plan.destination_location
                    else plan.target
                ),
            )
            self._log(
                LogLevel.INFO,
                "organize plan processed",
                source=source,
                plan_id=plan.plan_id,
                destination=plan.target,
                execution_status=execution.status.value,
            )
            item = MediaOrganizerItemResult(source, strategy, plan, execution)
            self._record(item)
            return item
        except Exception as error:
            return self._failed(source, None, str(error))

    def process_library(
        self,
        library: ResourceLibrary,
        *,
        execute: bool = False,
        limit: int | None = None,
        progress: ProgressReporter | None = None,
    ) -> MediaOrganizerBatchResult:
        items: list[MediaOrganizerItemResult] = []
        cancellation = CancellationToken()
        self._log(LogLevel.INFO, "library scan started", library_id=library.library_id)

        def discovered(file) -> None:
            if file.status is not FileScanStatus.READY:
                return
            relative_display_path = file.path
            library_root = library.root_path.strip("/")
            if library_root and file.path.startswith(f"{library_root}/"):
                relative_display_path = file.path[len(library_root) + 1 :]
            source = posixpath.join(
                self._source_display_roots.get(library.library_id, library.root_path),
                relative_display_path,
            )
            items.append(
                self.process_file(
                    source,
                    resource_library=library,
                    storage_path=file.path,
                    execute=execute,
                )
            )
            if progress:
                progress(len(items), limit, source)
            if limit is not None and len(items) >= limit:
                cancellation.cancel()

        scan = self._scanner.scan(library, cancellation=cancellation, on_discovered=discovered)
        self._log(
            LogLevel.INFO,
            "library scan completed",
            library_id=library.library_id,
            files=len(items),
            errors=len(scan.errors),
        )
        return MediaOrganizerBatchResult(tuple(items), scan.errors)

    def process_all_libraries(
        self,
        libraries: tuple[ResourceLibrary, ...],
        *,
        execute: bool = False,
        limit: int | None = None,
        progress: ProgressReporter | None = None,
    ) -> MediaOrganizerBatchResult:
        """Process all enabled configured libraries without local-path assumptions."""
        items: list[MediaOrganizerItemResult] = []

        def discovered(library: ResourceLibrary, file) -> None:
            source = f"{library.storage_id}:{file.path}"
            items.append(
                self.process_file(
                    source,
                    resource_library=library,
                    storage_path=file.path,
                    execute=execute,
                )
            )
            if progress:
                progress(len(items), limit, source)

        batch = ResourceLibraryScanner(self._scanner, libraries, self._storages).scan_all(
            limit=limit,
            on_discovered=discovered,
        )
        errors = tuple(error for result in batch.results for error in result.errors)
        return MediaOrganizerBatchResult(tuple(items), errors)

    def _failed(
        self,
        source: str,
        strategy: StrategyTestResult | None,
        error: str,
    ) -> MediaOrganizerItemResult:
        item = MediaOrganizerItemResult(source, strategy, error=error)
        self._log(LogLevel.ERROR, "media workflow failed", source=source, error=error)
        self._record(item)
        return item

    def _log(self, level: LogLevel, message: str, **context: object) -> None:
        if self._logger:
            self._logger.log(level, message, **context)

    def _record(self, item: MediaOrganizerItemResult) -> None:
        identity = (
            item.strategy.metadata.identity if item.strategy and item.strategy.metadata else None
        )
        execution = item.execution
        self._history.append(
            OperationHistoryRecord.now(
                execution.plan_id if execution else f"failed:{len(self._history.list())}",
                item.source,
                execution.resolved_destination if execution else "",
                execution.operation.value if execution else "SKIP",
                execution.status.value if execution else "FAILED",
                provider_id=identity.provider_id if identity else None,
                title=identity.title if identity else None,
                error=item.error or ("; ".join(execution.errors) if execution else None),
            )
        )
