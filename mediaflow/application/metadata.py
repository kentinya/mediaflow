from __future__ import annotations

import re
import threading
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, replace
from difflib import SequenceMatcher
from typing import Any

from mediaflow.domain.metadata import (
    CandidateMatchResult,
    CandidateMatchStatus,
    CandidateScore,
    MediaCandidate,
    MediaQueryType,
    MediaType,
    MetadataError,
    MetadataErrorCode,
    MetadataIdentificationResult,
    MetadataIdentificationStatus,
    MetadataPolicy,
    MetadataProvider,
    ScoreComponent,
)
from mediaflow.domain.parser import ParseResult
from mediaflow.domain.recognition import RecognitionResult


class MetadataProviderRegistry:
    def __init__(self, providers: tuple[MetadataProvider, ...]) -> None:
        self._providers = {provider.provider_id: provider for provider in providers}
        if len(self._providers) != len(providers):
            raise ValueError("metadata provider ids must be unique")

    def resolve(self, provider_id: str) -> MetadataProvider:
        try:
            return self._providers[provider_id]
        except KeyError as error:
            raise LookupError(f"metadata provider {provider_id!r} is not registered") from error


class MetadataPolicyRegistry:
    """Application catalog for configured metadata policies."""

    def __init__(self, policies: tuple[MetadataPolicy, ...]) -> None:
        self._policies: dict[str, MetadataPolicy] = {}
        for policy in policies:
            if policy.policy_id in self._policies:
                raise ValueError(f"metadata policy id {policy.policy_id!r} is not unique")
            self._policies[policy.policy_id] = policy

    def resolve(self, policy_id: str) -> MetadataPolicy:
        try:
            policy = self._policies[policy_id]
        except KeyError as error:
            raise LookupError(f"metadata policy {policy_id!r} is not configured") from error
        if not policy.enabled:
            raise LookupError(f"metadata policy {policy_id!r} is disabled")
        return policy

    def references(self) -> dict[str, MetadataPolicy]:
        return dict(self._policies)


@dataclass(frozen=True)
class MetadataCacheKey:
    provider: str
    operation: str
    arguments: tuple[tuple[str, str], ...]


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


class MetadataCache:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._entries: dict[MetadataCacheKey, _CacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, key: MetadataCacheKey) -> Any | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= self._clock():
                del self._entries[key]
                return None
            return entry.value

    def put(self, key: MetadataCacheKey, value: Any, ttl: float) -> None:
        if ttl <= 0:
            return
        with self._lock:
            self._entries[key] = _CacheEntry(value, self._clock() + ttl)

    def invalidate(self, key: MetadataCacheKey) -> None:
        with self._lock:
            self._entries.pop(key, None)


class CandidateMatcher:
    def match(
        self,
        parsed: ParseResult,
        candidates: tuple[MediaCandidate, ...],
        policy: MetadataPolicy,
    ) -> CandidateMatchResult:
        expected_type = _expected_media_type(policy)
        filtered = tuple(
            candidate
            for candidate in candidates[: policy.max_candidates]
            if expected_type is None or candidate.media_type is expected_type
        )
        if not filtered or not parsed.title_candidate.strip():
            return CandidateMatchResult(
                CandidateMatchStatus.NOT_FOUND,
                reasons=("No compatible candidates or usable title",),
            )
        scored = tuple(self._score(parsed, candidate) for candidate in filtered)
        ordered = tuple(
            sorted(
                scored,
                key=lambda item: (
                    -item.total_score,
                    -int(item.exact_title),
                    -int(item.exact_year),
                    _provider_id_key(item.candidate.provider_id),
                ),
            )
        )
        best = ordered[0]
        second = ordered[1] if len(ordered) > 1 else None
        gap = best.total_score - second.total_score if second else 100
        if second and gap < policy.minimum_score_gap:
            status = CandidateMatchStatus.AMBIGUOUS
            reason = f"Top candidate score gap {gap:.1f} is below {policy.minimum_score_gap:.1f}"
        elif best.total_score >= policy.automatic_threshold:
            status = CandidateMatchStatus.MATCHED
            reason = "Candidate reached automatic threshold"
        elif best.total_score >= policy.confirmation_threshold:
            status = CandidateMatchStatus.NEED_CONFIRM
            reason = "Candidate requires confirmation"
        else:
            status = CandidateMatchStatus.NOT_FOUND
            reason = "Candidate score is below confirmation threshold"
        return CandidateMatchResult(
            status,
            best.candidate,
            best.total_score,
            ordered,
            (reason,),
            () if status is CandidateMatchStatus.MATCHED else ("automatic selection withheld",),
        )

    @staticmethod
    def _score(parsed: ParseResult, candidate: MediaCandidate) -> CandidateScore:
        query_titles = tuple(
            dict.fromkeys((parsed.title_candidate, *parsed.alternative_title_candidates))
        )
        candidate_titles = tuple(
            (value, source)
            for value, source in (
                (candidate.title, "title"),
                (candidate.original_title, "original_title"),
                *((value, "translation") for value in candidate.translated_titles),
                *((value, "alternative_title") for value in candidate.alternative_titles),
            )
            if value
        )
        similarities = [
            (_similarity(query, title), query, title, source)
            for query in query_titles
            for title, source in candidate_titles
            if query
        ]
        similarity, query_title, matched_title, title_source = max(
            similarities, key=lambda item: item[0], default=(0.0, "", "", None)
        )
        exact_title = _normalize_title(query_title) == _normalize_title(matched_title)
        title_score = 65.0 * similarity
        title_reason = (
            f"exact {title_source} match: {query_title!r} == {matched_title!r}"
            if exact_title
            else (
                f"{query_title!r} vs {matched_title!r} ({title_source}) similarity {similarity:.3f}"
            )
        )
        components = [ScoreComponent("title", title_score, title_reason)]
        year_score = 0.0
        exact_year = False
        if parsed.year is not None and candidate.year is not None:
            difference = abs(parsed.year - candidate.year)
            if difference == 0:
                year_score, exact_year = 20.0, True
            elif difference == 1:
                year_score = 10.0
            elif difference <= 3:
                year_score = 3.0
            else:
                year_score = -15.0
            components.append(
                ScoreComponent("year", year_score, f"canonical year difference is {difference}")
            )
        else:
            components.append(ScoreComponent("year", 0, "canonical year evidence unavailable"))
        if candidate.regional_year is not None:
            components.append(
                ScoreComponent(
                    "regional_year",
                    0,
                    f"regional release year {candidate.regional_year} is informational only",
                )
            )
        components.append(ScoreComponent("media_type", 5, "candidate media type is compatible"))
        directory_score = 0.0
        for evidence in parsed.evidence:
            if evidence.field == "title_candidate" and _normalize_title(
                evidence.value
            ) == _normalize_title(candidate.title):
                directory_score = 10.0
                break
        components.append(
            ScoreComponent("parse_evidence", directory_score, "matching parser title evidence")
        )
        total = max(0.0, min(100.0, title_score + year_score + 5 + directory_score))
        return CandidateScore(
            candidate,
            round(total, 3),
            tuple(components),
            exact_title,
            exact_year,
            query_title or None,
            matched_title or None,
            title_source,
        )


class MetadataIdentificationService:
    def __init__(
        self, providers: MetadataProviderRegistry, matcher: CandidateMatcher | None = None
    ) -> None:
        self._providers = providers
        self._matcher = matcher or CandidateMatcher()

    def identify(
        self,
        recognition: RecognitionResult,
        parsed: ParseResult,
        policy: MetadataPolicy,
        *,
        force_refresh: bool = False,
    ) -> MetadataIdentificationResult:
        if recognition.recognition_type is None:
            raise ValueError("metadata identification requires a resolved recognition type")
        if not policy.enabled or policy.query_type is MediaQueryType.NONE:
            return MetadataIdentificationResult(
                MetadataIdentificationStatus.NOT_FOUND,
                recognition.recognition_type,
                query=parsed.title_candidate,
            )
        provider = self._providers.resolve(policy.provider_id)
        remaining_requests = policy.max_provider_requests

        def consume_request() -> None:
            nonlocal remaining_requests
            if remaining_requests <= 0:
                raise MetadataError(
                    MetadataErrorCode.INVALID_REQUEST,
                    "metadata identification request budget exhausted",
                )
            remaining_requests -= 1

        try:
            media_type = _expected_media_type(policy) or (
                MediaType.TV if parsed.season is not None else MediaType.MOVIE
            )
            if media_type is MediaType.TV:
                consume_request()
                candidates = tuple(provider.search_tv(parsed, policy, force_refresh=force_refresh))
            else:
                consume_request()
                candidates = tuple(
                    provider.search_movie(parsed, policy, force_refresh=force_refresh)
                )
            match = self._matcher.match(parsed, candidates, policy)
            enriched_identities = {}
            if (
                match.status is not CandidateMatchStatus.MATCHED
                and provider.capabilities.can_get_alternative_titles
                and policy.max_candidate_enrichments
            ):
                candidates, enriched_identities = self._enrich_candidates(
                    provider,
                    candidates,
                    parsed,
                    media_type,
                    policy,
                    force_refresh,
                    consume_request,
                    lambda: remaining_requests,
                )
                match = self._matcher.match(parsed, candidates, policy)
            if match.status is not CandidateMatchStatus.MATCHED or match.best_candidate is None:
                status = {
                    CandidateMatchStatus.NEED_CONFIRM: MetadataIdentificationStatus.NEED_CONFIRM,
                    CandidateMatchStatus.AMBIGUOUS: MetadataIdentificationStatus.AMBIGUOUS,
                }.get(match.status, MetadataIdentificationStatus.NOT_FOUND)
                return MetadataIdentificationResult(
                    status, recognition.recognition_type, match=match, query=parsed.title_candidate
                )
            identity = enriched_identities.get(match.best_candidate.provider_id)
            if identity is None and media_type is MediaType.MOVIE:
                consume_request()
                identity = provider.get_movie(
                    match.best_candidate.provider_id, policy, force_refresh=force_refresh
                )
            elif identity is None:
                consume_request()
                identity = provider.get_tv(
                    match.best_candidate.provider_id, policy, force_refresh=force_refresh
                )
            if media_type is MediaType.TV:
                identity = self._verify_episodes(
                    provider, identity, parsed, policy, force_refresh, consume_request
                )
                if identity is None:
                    return MetadataIdentificationResult(
                        MetadataIdentificationStatus.METADATA_MISMATCH,
                        recognition.recognition_type,
                        match=match,
                        query=parsed.title_candidate,
                    )
            identity = replace(
                identity,
                regional_release_date=match.best_candidate.regional_release_date,
                confidence=match.score,
                matched_by="candidate_matcher",
                recognition_type_id=recognition.recognition_type.type_id,
            )
            return MetadataIdentificationResult(
                MetadataIdentificationStatus.MATCHED,
                recognition.recognition_type,
                identity,
                match,
                parsed.title_candidate,
            )
        except MetadataError as error:
            return MetadataIdentificationResult(
                MetadataIdentificationStatus.PROVIDER_ERROR,
                recognition.recognition_type,
                query=parsed.title_candidate,
                error=error,
            )

    @staticmethod
    def _enrich_candidates(
        provider,
        candidates,
        parsed,
        media_type,
        policy,
        force_refresh,
        consume_request,
        remaining_requests,
    ):
        """Enrich only plausible candidates; year is a fetch filter, never match evidence alone."""
        preliminary = CandidateMatcher()
        plausible = []
        for search_rank, candidate in enumerate(candidates[: policy.max_candidates]):
            if candidate.media_type is not media_type:
                continue
            if parsed.year is not None and candidate.year is not None:
                year_distance = abs(parsed.year - candidate.year)
                if year_distance > 1:
                    continue
            else:
                year_distance = 2
            score = preliminary._score(parsed, candidate).total_score
            plausible.append((year_distance, -score, search_rank, candidate))
        plausible.sort(key=lambda item: item[:3])
        reserve = (
            1 if media_type is MediaType.TV and parsed.season is not None and parsed.episodes else 0
        )
        limit = min(policy.max_candidate_enrichments, max(0, remaining_requests() - reserve))
        enriched = {}
        replacements = {}
        for _, _, _, candidate in plausible[:limit]:
            consume_request()
            identity = (
                provider.get_movie(candidate.provider_id, policy, force_refresh=force_refresh)
                if media_type is MediaType.MOVIE
                else provider.get_tv(candidate.provider_id, policy, force_refresh=force_refresh)
            )
            enriched[candidate.provider_id] = identity
            alternatives = tuple(
                dict.fromkeys(
                    value
                    for value in (
                        *candidate.alternative_titles,
                        identity.title,
                        identity.original_title,
                        *identity.alternative_titles,
                    )
                    if value and value not in {candidate.title, candidate.original_title}
                )
            )
            translations = tuple(
                dict.fromkeys(
                    value
                    for value in (*candidate.translated_titles, *identity.translated_titles)
                    if value and value not in {candidate.title, candidate.original_title}
                )
            )
            replacements[candidate.provider_id] = replace(
                candidate,
                year=identity.canonical_year,
                alternative_titles=alternatives,
                translated_titles=translations,
                canonical_release_date=identity.canonical_release_date,
            )
        return (
            tuple(replacements.get(item.provider_id, item) for item in candidates),
            enriched,
        )

    def identify_by_provider_id(
        self,
        recognition: RecognitionResult,
        provider_id: str,
        media_type: MediaType,
        policy: MetadataPolicy,
        *,
        force_refresh: bool = False,
    ) -> MetadataIdentificationResult:
        if recognition.recognition_type is None:
            raise ValueError("metadata identification requires a resolved recognition type")
        provider = self._providers.resolve(policy.provider_id)
        try:
            if media_type is MediaType.MOVIE:
                identity = provider.get_movie(provider_id, policy, force_refresh=force_refresh)
            else:
                identity = provider.get_tv(provider_id, policy, force_refresh=force_refresh)
            identity = replace(
                identity,
                confidence=100,
                matched_by="manual_provider_id",
                recognition_type_id=recognition.recognition_type.type_id,
            )
            return MetadataIdentificationResult(
                MetadataIdentificationStatus.MATCHED,
                recognition.recognition_type,
                identity=identity,
                query=provider_id,
            )
        except MetadataError as error:
            return MetadataIdentificationResult(
                MetadataIdentificationStatus.PROVIDER_ERROR,
                recognition.recognition_type,
                query=provider_id,
                error=error,
            )

    @staticmethod
    def _verify_episodes(provider, identity, parsed, policy, force_refresh, consume_request):
        if parsed.season is None or not parsed.episodes:
            return replace(
                identity, season=parsed.season, episode=parsed.episode, episodes=parsed.episodes
            )
        consume_request()
        season = provider.get_season(
            identity.provider_id, parsed.season, policy, force_refresh=force_refresh
        )
        available = {item.episode: item for item in season.episode_metadata}
        if any(number not in available for number in parsed.episodes):
            return None
        selected = tuple(available[number] for number in parsed.episodes)
        return replace(
            identity,
            season=parsed.season,
            episode=parsed.episodes[0],
            episodes=parsed.episodes,
            episode_title=selected[0].title,
            episode_metadata=selected,
        )


def _expected_media_type(policy: MetadataPolicy) -> MediaType | None:
    if policy.query_type is MediaQueryType.MOVIE:
        return MediaType.MOVIE
    if policy.query_type is MediaQueryType.TV:
        return MediaType.TV
    return None


def _normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"\w+", value, flags=re.UNICODE))


def _similarity(left: str, right: str) -> float:
    left_normalized, right_normalized = _normalize_title(left), _normalize_title(right)
    if not left_normalized or not right_normalized:
        return 0.0
    if left_normalized == right_normalized:
        return 1.0
    sequence = SequenceMatcher(None, left_normalized, right_normalized).ratio()
    left_tokens, right_tokens = set(left_normalized.split()), set(right_normalized.split())
    token = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    return max(sequence, token)


def _provider_id_key(value: str) -> tuple[int, int | str]:
    return (0, int(value)) if value.isdigit() else (1, value)
