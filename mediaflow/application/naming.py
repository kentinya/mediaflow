from __future__ import annotations

import re
import string
import unicodedata
from dataclasses import dataclass

from mediaflow.domain.metadata import MediaType
from mediaflow.domain.naming import (
    MissingVariableStrategy,
    NamingContext,
    NamingError,
    NamingErrorCode,
    NamingMediaTypeMode,
    NamingPolicy,
    NamingResult,
    NamingTemplate,
)

SUPPORTED_VARIABLES = (
    "title",
    "original_title",
    "year",
    "season",
    "episode",
    "episodes",
    "episode_range",
    "episode_title",
    "provider",
    "provider_id",
    "resolution",
    "source",
    "video_codec",
    "audio",
    "audio_codec",
    "audio_channels",
    "hdr",
    "version",
    "release_group",
    "ext",
)
_NUMERIC_VARIABLES = frozenset(("year", "season", "episode"))
_WINDOWS_RESERVED = frozenset(
    ("CON", "PRN", "AUX", "NUL")
    + tuple(f"COM{number}" for number in range(1, 10))
    + tuple(f"LPT{number}" for number in range(1, 10))
)
_DRIVE_OR_SCHEME = re.compile(r"^(?:[A-Za-z]:|[A-Za-z][A-Za-z0-9+.-]*://)")


class NamingPolicyRegistry:
    def __init__(self, policies: tuple[NamingPolicy, ...]) -> None:
        self._policies: dict[str, NamingPolicy] = {}
        for policy in policies:
            validate_naming_policy(policy)
            if policy.policy_id in self._policies:
                raise NamingError(
                    NamingErrorCode.INVALID_TEMPLATE,
                    f"duplicate NamingPolicy ID {policy.policy_id!r}",
                )
            self._policies[policy.policy_id] = policy

    def resolve(self, policy_id: str) -> NamingPolicy:
        try:
            policy = self._policies[policy_id]
        except KeyError as error:
            raise NamingError(
                NamingErrorCode.POLICY_NOT_FOUND,
                f"NamingPolicy {policy_id!r} is not configured",
            ) from error
        if not policy.enabled:
            raise NamingError(
                NamingErrorCode.POLICY_DISABLED,
                f"NamingPolicy {policy_id!r} is disabled",
            )
        return policy


@dataclass(frozen=True)
class _Rendered:
    value: str
    missing: tuple[str, ...]


class SafeTemplateRenderer:
    """Restricted replacement renderer: named fields and numeric zero-padding only."""

    def validate(self, template: NamingTemplate) -> None:
        value = template.value
        if value.startswith(("/", "\\")) or _DRIVE_OR_SCHEME.match(value):
            raise NamingError(NamingErrorCode.UNSAFE_PATH, "template must be a relative component")
        if "/" in value or "\\" in value:
            raise NamingError(
                NamingErrorCode.UNSAFE_PATH,
                "template literals cannot contain path separators",
            )
        try:
            parsed = tuple(string.Formatter().parse(value))
        except ValueError as error:
            raise NamingError(NamingErrorCode.INVALID_TEMPLATE, str(error)) from error
        for _, field_name, format_spec, conversion in parsed:
            if field_name is None:
                continue
            if field_name not in SUPPORTED_VARIABLES:
                raise NamingError(
                    NamingErrorCode.UNKNOWN_VARIABLE,
                    f"unknown naming variable {field_name!r}",
                )
            if conversion:
                raise NamingError(
                    NamingErrorCode.INVALID_FORMAT_SPECIFIER,
                    "template conversions are not supported",
                )
            if format_spec and (
                field_name not in _NUMERIC_VARIABLES
                or re.fullmatch(r"0[1-9][0-9]*", format_spec) is None
            ):
                raise NamingError(
                    NamingErrorCode.INVALID_FORMAT_SPECIFIER,
                    f"invalid format specifier {format_spec!r} for {field_name!r}",
                )

    def render(
        self,
        template: NamingTemplate,
        variables: dict[str, object | None],
        missing_strategy: MissingVariableStrategy,
    ) -> _Rendered:
        self.validate(template)
        output: list[str] = []
        missing: list[str] = []
        for literal, field_name, format_spec, _ in string.Formatter().parse(template.value):
            output.append(literal)
            if field_name is None:
                continue
            value = variables[field_name]
            if value is None or value == "":
                missing.append(field_name)
                if missing_strategy is MissingVariableStrategy.ERROR:
                    raise NamingError(
                        NamingErrorCode.MISSING_VARIABLE,
                        f"required naming variable {field_name!r} is missing",
                    )
                output.append("")
                continue
            try:
                output.append(format(value, format_spec) if format_spec else str(value))
            except (TypeError, ValueError) as error:
                raise NamingError(
                    NamingErrorCode.INVALID_FORMAT_SPECIFIER,
                    f"cannot format naming variable {field_name!r}",
                ) from error
        rendered = "".join(output)
        if missing and missing_strategy is MissingVariableStrategy.OMIT_TOKEN:
            rendered = _clean_missing_tokens(rendered)
        return _Rendered(rendered, tuple(dict.fromkeys(missing)))


class NameSanitizer:
    def sanitize(
        self, value: str, *, max_length: int, filename: bool = False
    ) -> tuple[str, tuple[str, ...]]:
        original = value
        value = unicodedata.normalize("NFC", value)
        value = "".join(" " if unicodedata.category(char) == "Cc" else char for char in value)
        value = value.replace(":", " -")
        value = re.sub(r"[\\/*?\"<>|]", " ", value)
        value = re.sub(r"\s+", " ", value).strip(" .")
        changes: list[str] = []
        if value != original:
            changes.append("sanitized_character_or_whitespace")
        if value in {"", ".", ".."}:
            raise NamingError(NamingErrorCode.EMPTY_COMPONENT, "naming component is empty")
        stem = value.rsplit(".", 1)[0] if filename and "." in value else value
        if stem.upper() in _WINDOWS_RESERVED:
            value = "_" + value
            changes.append("reserved_name_prefixed")
        if "/" in value or "\\" in value or _DRIVE_OR_SCHEME.match(value):
            raise NamingError(NamingErrorCode.UNSAFE_PATH, "unsafe naming component")
        if len(value) > max_length:
            value = _truncate_component(value, max_length, filename)
            changes.append("component_truncated")
        if not value or value in {".", ".."}:
            raise NamingError(NamingErrorCode.EMPTY_COMPONENT, "naming component is empty")
        return value, tuple(changes)


class NamingEngine:
    def __init__(
        self,
        renderer: SafeTemplateRenderer | None = None,
        sanitizer: NameSanitizer | None = None,
    ) -> None:
        self._renderer = renderer or SafeTemplateRenderer()
        self._sanitizer = sanitizer or NameSanitizer()

    def name(self, context: NamingContext, policy: NamingPolicy) -> NamingResult:
        if not policy.enabled:
            raise NamingError(
                NamingErrorCode.POLICY_DISABLED,
                f"NamingPolicy {policy.policy_id!r} is disabled",
            )
        validate_naming_policy(policy, self._renderer)
        variables, warnings = _variables(context)
        media_type = _media_type(context, policy)
        templates = self._templates(policy, media_type, variables)
        segments: list[str] = []
        changes: list[str] = []
        for template, filename in templates:
            rendered = self._renderer.render(template, variables, policy.missing_variable_strategy)
            warnings.extend(f"missing_variable:{name}" for name in rendered.missing)
            component, component_changes = self._sanitizer.sanitize(
                rendered.value,
                max_length=policy.max_component_length,
                filename=filename,
            )
            segments.append(component)
            changes.extend(component_changes)
            if "component_truncated" in component_changes:
                warnings.append("component_truncated")
        return NamingResult(
            segments[0],
            segments[-1],
            policy.policy_id,
            context.recognition_type_id,
            media_type,
            tuple(segments[:-1]),
            tuple((name, "" if value is None else str(value)) for name, value in variables.items()),
            tuple(dict.fromkeys(warnings)),
            tuple(dict.fromkeys(changes)),
        )

    @staticmethod
    def _templates(
        policy: NamingPolicy, media_type: MediaType, variables: dict[str, object | None]
    ) -> tuple[tuple[NamingTemplate, bool], ...]:
        if media_type is MediaType.MOVIE:
            return (
                (policy.movie_directory_template, False),
                (policy.movie_file_template, True),
            )
        episodes = variables["episode_numbers"]
        episode_template = (
            policy.multi_episode_file_template
            if isinstance(episodes, tuple) and len(episodes) > 1
            else policy.tv_episode_file_template
        )
        return (
            (policy.tv_series_directory_template, False),
            (policy.tv_season_directory_template, False),
            (episode_template, True),
        )


class NamingPreviewService:
    def __init__(self, registry: NamingPolicyRegistry, engine: NamingEngine | None = None) -> None:
        self._registry = registry
        self._engine = engine or NamingEngine()

    def preview(self, context: NamingContext, policy_id: str) -> NamingResult:
        return self._engine.name(context, self._registry.resolve(policy_id))


def validate_naming_policy(
    policy: NamingPolicy, renderer: SafeTemplateRenderer | None = None
) -> None:
    renderer = renderer or SafeTemplateRenderer()
    for template in (
        policy.movie_directory_template,
        policy.movie_file_template,
        policy.tv_series_directory_template,
        policy.tv_season_directory_template,
        policy.tv_episode_file_template,
        policy.multi_episode_file_template,
    ):
        renderer.validate(template)


def _variables(context: NamingContext) -> tuple[dict[str, object | None], list[str]]:
    identity, parsed = context.media_identity, context.parse_result
    warnings: list[str] = []
    year = identity.year
    if year is None and parsed.year is not None:
        year = parsed.year
        warnings.append("missing_year_fallback:parse_result")
    season = identity.season if identity.season is not None else parsed.season
    raw_episodes = identity.episodes or parsed.episodes
    episode = identity.episode if identity.episode is not None else parsed.episode
    if not raw_episodes and episode is not None:
        raw_episodes = (episode,)
    episode_numbers = tuple(sorted(set(raw_episodes)))
    if episode is None and episode_numbers:
        episode = episode_numbers[0]
    extension = context.extension or parsed.extension or _extension(context.original_filename)
    extension = extension.lower().lstrip(".") or None
    audio_parts = tuple(
        value for value in (parsed.audio_codec_tag, parsed.audio_channels_tag) if value
    )
    episodes = _format_episodes(episode_numbers)
    variables: dict[str, object | None] = {
        "title": identity.title,
        "original_title": identity.original_title,
        "year": year,
        "season": season,
        "episode": episode,
        "episodes": episodes,
        "episode_range": episodes,
        "episode_title": identity.episode_title,
        "provider": identity.provider,
        "provider_id": identity.provider_id,
        "resolution": parsed.resolution_tag,
        "source": parsed.source_tag,
        "video_codec": parsed.video_codec_tag,
        "audio": "".join(audio_parts) if audio_parts else None,
        "audio_codec": parsed.audio_codec_tag,
        "audio_channels": parsed.audio_channels_tag,
        "hdr": " ".join(dict.fromkeys(parsed.hdr_tags)) or None,
        "version": " ".join(dict.fromkeys(parsed.version_tags)) or None,
        "release_group": parsed.release_group,
        "ext": extension,
        "episode_numbers": episode_numbers,
    }
    return variables, warnings


def _media_type(context: NamingContext, policy: NamingPolicy) -> MediaType:
    if policy.media_type_mode is NamingMediaTypeMode.MOVIE:
        return MediaType.MOVIE
    if policy.media_type_mode is NamingMediaTypeMode.TV:
        return MediaType.TV
    if context.media_identity.media_type in (MediaType.MOVIE, MediaType.TV):
        return context.media_identity.media_type
    raise NamingError(NamingErrorCode.UNSUPPORTED_MEDIA_TYPE, "unsupported media type")


def _format_episodes(episodes: tuple[int, ...]) -> str | None:
    if not episodes:
        return None
    formatted = [f"E{episode:02d}" for episode in episodes]
    contiguous = all(right == left + 1 for left, right in zip(episodes, episodes[1:]))
    if len(episodes) > 1 and contiguous:
        return f"{formatted[0]}-{formatted[-1]}"
    return "".join(formatted)


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[1] if "." in filename else ""


def _clean_missing_tokens(value: str) -> str:
    value = re.sub(r"\(\s*\)|\[\s*\]", "", value)
    value = re.sub(r"(?:\s+-\s*){2,}", " - ", value)
    value = re.sub(r"\s+-\s*(?=\.)", "", value)
    value = re.sub(r"\s+([.,])", r"\1", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" -._")


def _truncate_component(value: str, max_length: int, filename: bool) -> str:
    extension = ""
    base = value
    if filename and "." in value:
        base, suffix = value.rsplit(".", 1)
        extension = "." + suffix
    available = max_length - len(extension)
    if available < 3:
        raise NamingError(
            NamingErrorCode.COMPONENT_TOO_LONG, "component limit cannot preserve extension"
        )
    tail_length = min(48, max(8, available // 3))
    prefix_length = available - tail_length - 1
    return base[:prefix_length].rstrip() + "…" + base[-tail_length:].lstrip() + extension
