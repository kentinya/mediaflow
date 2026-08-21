"""Explicit development configuration for the developer-only strategy CLI."""

from mediaflow.application.strategy_test import StrategyTestConfiguration
from mediaflow.domain.classification import ClassificationPolicy, ClassificationRule
from mediaflow.domain.metadata import MediaType, MetadataPolicy
from mediaflow.domain.naming import NamingMediaTypeMode, NamingPolicy
from mediaflow.domain.organizer import OrganizeOperationType, OrganizePolicy
from mediaflow.domain.recognition import (
    AtomicCondition,
    ConditionField,
    ConditionOperator,
    RecognitionRule,
    RecognitionType,
    RecognitionTypePolicy,
)


def smoke_strategy_configuration(
    *,
    language: str | None = None,
    region: str | None = None,
    automatic_threshold: float = 90,
    confirmation_threshold: float = 70,
    minimum_score_gap: float = 5,
) -> StrategyTestConfiguration:
    types = tuple(RecognitionType(value, value) for value in ("A", "B", "C"))
    rules = tuple(
        RecognitionRule(
            f"path-{value}",
            f"Path contains {value}",
            AtomicCondition(ConditionField.PATH, ConditionOperator.CONTAINS, f"/{value}/"),
            value,
            priority=100,
            score=100,
            stop_on_match=True,
        )
        for value in ("A", "B", "C")
    )
    type_policies = tuple(
        RecognitionTypePolicy(
            f"type-{value}",
            types[index],
            value,
            "A" if value == "C" else value,
            "A" if value == "C" else value,
            OrganizePolicy("A" if value == "C" else value, OrganizeOperationType.MOVE),
        )
        for index, value in enumerate(("A", "B", "C"))
    )
    policy_options = {
        "language": language or "en-US",
        "region": region,
        "automatic_threshold": automatic_threshold,
        "confirmation_threshold": confirmation_threshold,
        "minimum_score_gap": minimum_score_gap,
    }
    metadata_policies = (
        MetadataPolicy("A", "tmdb", media_type=MediaType.MOVIE, **policy_options),
        MetadataPolicy("B", "tmdb", media_type=MediaType.TV, **policy_options),
        MetadataPolicy("C", "tmdb", media_type=MediaType.MOVIE, **policy_options),
    )
    naming_policies = (
        NamingPolicy("A", "Standard Movie", media_type_mode=NamingMediaTypeMode.MOVIE),
        NamingPolicy("B", "Standard TV", media_type_mode=NamingMediaTypeMode.TV),
    )
    classification_policies = (
        ClassificationPolicy(
            "A",
            "Movie Classification",
            (
                ClassificationRule(
                    "anime-movie",
                    "Japanese Animation",
                    "movies",
                    "Movies",
                    "Anime",
                    priority=200,
                    media_types=(MediaType.MOVIE,),
                    genres=("Animation",),
                    countries=("Japan", "JP"),
                ),
                ClassificationRule(
                    "animation-movie",
                    "Animation Movie",
                    "movies",
                    "Movies",
                    "Animation",
                    priority=100,
                    media_types=(MediaType.MOVIE,),
                    genres=("Animation",),
                ),
                ClassificationRule(
                    "action-movie",
                    "Action Movie",
                    "movies",
                    "Movies",
                    "Action",
                    priority=90,
                    media_types=(MediaType.MOVIE,),
                    genres=("Action",),
                ),
            ),
        ),
        ClassificationPolicy(
            "B",
            "TV Classification",
            (
                ClassificationRule(
                    "tv-series",
                    "TV Series",
                    "tv",
                    "TV Shows",
                    "Series",
                    priority=100,
                    media_types=(MediaType.TV,),
                ),
            ),
        ),
    )
    return StrategyTestConfiguration(
        types,
        rules,
        type_policies,
        metadata_policies,
        naming_policies,
        classification_policies,
    )


def development_strategy_configuration(
    *,
    language: str | None = None,
    region: str | None = None,
    automatic_threshold: float = 90,
    confirmation_threshold: float = 70,
    minimum_score_gap: float = 5,
) -> StrategyTestConfiguration:
    """Default developer configuration; real libraries should load user JSON configuration."""
    base = smoke_strategy_configuration(
        language=language,
        region=region,
        automatic_threshold=automatic_threshold,
        confirmation_threshold=confirmation_threshold,
        minimum_score_gap=minimum_score_gap,
    )
    outputs = (("movies", "A"), ("tv", "B"), ("special", "C"))
    rules = tuple(
        RecognitionRule(
            f"{library_id}-library",
            f"Resource library {library_id}",
            AtomicCondition(
                ConditionField.RESOURCE_LIBRARY_ID,
                ConditionOperator.EQUALS,
                library_id,
            ),
            recognition_type,
            priority=100,
            score=100,
            stop_on_match=True,
        )
        for library_id, recognition_type in outputs
    )
    return StrategyTestConfiguration(
        base.recognition_types,
        rules,
        base.recognition_type_policies,
        base.metadata_policies,
        base.naming_policies,
        base.classification_policies,
    )
