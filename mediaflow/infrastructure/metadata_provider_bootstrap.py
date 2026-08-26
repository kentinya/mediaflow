from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Mapping
from threading import Lock

from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.infrastructure.tmdb import TMDBClient, TMDBConfig, TMDBProvider


class MetadataProviderBootstrapError(RuntimeError):
    """A secret-free, operator-actionable Provider bootstrap failure."""

    def __init__(self, category: str, message: str, next_action: str) -> None:
        super().__init__(message)
        self.category = category
        self.message = message
        self.next_action = next_action


class LazyMetadataProviderRegistryFactory:
    """Lazily publish one complete service-lifetime Provider registry.

    Construction happens only on the first non-empty request.  The lock deliberately
    covers construction: Provider initialization is infrequent, and publishing exactly
    one cache-bearing Provider is more important than duplicate speculative work.
    """

    def __init__(
        self,
        builder: Callable[[Iterable[str]], MetadataProviderRegistry] | None = None,
    ) -> None:
        self._builder = builder or metadata_provider_registry_from_environment
        self._registry: MetadataProviderRegistry | None = None
        self._lock = Lock()

    def __call__(self, provider_ids: Iterable[str]) -> MetadataProviderRegistry:
        requested = _requested_provider_ids(provider_ids)
        _validate_supported_provider_ids(requested)
        if not requested:
            return MetadataProviderRegistry(())
        with self._lock:
            if self._registry is None:
                # Assign only after successful construction. A missing credential or other
                # bootstrap error therefore remains explicitly retryable and cannot publish a
                # partial/broken registry.
                registry = self._builder(requested)
                for provider_id in requested:
                    try:
                        registry.resolve(provider_id)
                    except LookupError as error:
                        raise MetadataProviderBootstrapError(
                            "provider_not_configured",
                            "The referenced Metadata Provider is not configured by this service.",
                            "configure the referenced Provider, then explicitly rerun the live "
                            "Metadata test",
                        ) from error
                self._registry = registry
            return self._registry


def _requested_provider_ids(provider_ids: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(provider_ids))


def _validate_supported_provider_ids(requested: tuple[str, ...]) -> None:
    unsupported = tuple(provider_id for provider_id in requested if provider_id != "tmdb")
    if unsupported:
        raise MetadataProviderBootstrapError(
            "provider_not_configured",
            "The referenced Metadata Provider is not configured by this service.",
            "configure the referenced Provider, then explicitly rerun the live Metadata test",
        )


def metadata_provider_registry_from_environment(
    provider_ids: Iterable[str],
    *,
    environ: Mapping[str, str] | None = None,
) -> MetadataProviderRegistry:
    """Build only requested production Providers; credentials remain environment-only."""

    requested = _requested_provider_ids(provider_ids)
    _validate_supported_provider_ids(requested)
    if not requested:
        return MetadataProviderRegistry(())
    source = os.environ if environ is None else environ
    token = source.get("TMDB_ACCESS_TOKEN") or source.get("TMDB_TOKEN")
    if not token:
        raise MetadataProviderBootstrapError(
            "missing_credential",
            "The TMDB credential required by the effective MetadataPolicy is unavailable.",
            "set TMDB_ACCESS_TOKEN in the service environment, restart the service, and explicitly "
            "rerun the live Metadata test",
        )
    try:
        provider = TMDBProvider(TMDBClient(TMDBConfig(token)))
    except (RuntimeError, ValueError) as error:
        raise MetadataProviderBootstrapError(
            "provider_not_configured",
            "The TMDB Provider could not be constructed by this service.",
            "install/configure the TMDB Provider dependency, restart the service, and explicitly "
            "rerun the live Metadata test",
        ) from error
    return MetadataProviderRegistry((provider,))
