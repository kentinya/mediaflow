from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import PurePosixPath

from mediaflow.domain.parser import (
    EvidenceConfidence,
    EvidenceSource,
    FileContext,
    ParseEvidence,
    ParserError,
    ParserErrorCode,
    ParseResult,
    ParseWarning,
    ParseWarningCode,
)


@dataclass(frozen=True)
class ParserOptions:
    episode_range_limit: int = 100
    year_min: int = 1900
    year_max: int = 2100
    enable_chinese_episode_patterns: bool = True

    def __post_init__(self) -> None:
        if self.episode_range_limit < 1:
            raise ValueError("episode range limit must be positive")
        if self.year_min < 1 or self.year_max < self.year_min:
            raise ValueError("invalid year range")


RESOLUTION_RULES = (
    (re.compile(r"(?i)(?<!\w)(2160p|4k|uhd)(?!\w)"), "2160p"),
    (re.compile(r"(?i)(?<!\w)(1080[pi]|720p|576p|480p)(?!\w)"), None),
)
SOURCE_RULES = (
    (re.compile(r"(?i)(?<!\w)(?:uhd[ ._-]*)?blu[ ._-]*ray(?!\w)"), "BLURAY"),
    (re.compile(r"(?i)(?<!\w)brrip(?!\w)"), "BRRIP"),
    (re.compile(r"(?i)(?<!\w)b[dr]rip(?!\w)"), "BDRIP"),
    (re.compile(r"(?i)(?<!\w)remux(?!\w)"), "REMUX"),
    (re.compile(r"(?i)(?<!\w)web[ ._-]*dl(?!\w)"), "WEB-DL"),
    (re.compile(r"(?i)(?<!\w)web[ ._-]*rip(?!\w)"), "WEBRIP"),
    (re.compile(r"(?i)(?<!\w)hdtv(?!\w)"), "HDTV"),
    (re.compile(r"(?i)(?<!\w)(?:dvd[ ._-]*rip|dvd)(?!\w)"), "DVD"),
)
VIDEO_RULES = (
    (re.compile(r"(?i)(?<!\w)(?:h[ .]?264|x264|avc)(?!\w)"), "H264"),
    (re.compile(r"(?i)(?<!\w)(?:h[ .]?265|x265|hevc)(?!\w)"), "H265"),
    (re.compile(r"(?i)(?<!\w)av1(?!\w)"), "AV1"),
    (re.compile(r"(?i)(?<!\w)vp9(?!\w)"), "VP9"),
)
AUDIO_RULES = (
    (re.compile(r"(?i)(?<!\w)(?:true[ ._-]*hd)(?:[ ._-]*atmos)?(?!\w)"), "TRUEHD"),
    (re.compile(r"(?i)(?<!\w)dts[ ._-]*hd(?:[ ._-]*ma)?(?!\w)"), "DTS-HD MA"),
    (re.compile(r"(?i)(?<!\w)dts(?!\w)"), "DTS"),
    (re.compile(r"(?i)(?<!\w)(?:e[ ._-]*ac3|ddp|dd\+)(?=\d|\b)"), "EAC3"),
    (re.compile(r"(?i)(?<!\w)(?:ac3|dolby[ ._-]*digital|dd)(?=\d|\b)"), "AC3"),
    (re.compile(r"(?i)(?<!\w)aac(?!\w)"), "AAC"),
    (re.compile(r"(?i)(?<!\w)(?:lpcm|pcm)(?!\w)"), "PCM"),
    (re.compile(r"(?i)(?<!\w)flac(?!\w)"), "FLAC"),
    (re.compile(r"(?i)(?<!\w)opus(?!\w)"), "OPUS"),
)
HDR_RULES = (
    (re.compile(r"(?i)(?<!\w)(?:dolby[ ._-]*vision|dovi|dv)(?!\w)"), "DV"),
    (re.compile(r"(?i)(?<!\w)(?:hdr10\+|hdr10plus)(?!\w)"), "HDR10+"),
    (re.compile(r"(?i)(?<!\w)hdr10(?!\w)"), "HDR10"),
    (re.compile(r"(?i)(?<!\w)hdr(?!\w)"), "HDR"),
)
VERSION_RULES = (
    (re.compile(r"(?i)(?<!\w)extended(?:[ ._-]*cut)?(?!\w)"), "EXTENDED"),
    (re.compile(r"(?i)(?<!\w)director'?s?[ ._-]*cut(?!\w)"), "DIRECTOR'S CUT"),
    (re.compile(r"(?i)(?<!\w)theatrical(?!\w)"), "THEATRICAL"),
    (re.compile(r"(?i)(?<!\w)unrated(?!\w)"), "UNRATED"),
    (re.compile(r"(?i)(?<!\w)imax(?!\w)"), "IMAX"),
    (re.compile(r"(?i)(?<!\w)remastered(?!\w)"), "REMASTERED"),
    (re.compile(r"(?i)(?<!\w)special[ ._-]*edition(?!\w)"), "SPECIAL EDITION"),
    (re.compile(r"(?i)(?<!\w)anniversary(?!\w)"), "ANNIVERSARY"),
)
LANGUAGE_RULES = (
    (re.compile(r"(?i)(?<![\w-])(?:chs|zh-cn)(?![\w-])"), "zh-CN"),
    (re.compile(r"(?i)(?<![\w-])(?:cht|zh-tw)(?![\w-])"), "zh-TW"),
    (re.compile(r"(?i)(?<![\w-])zh(?![\w-])"), "zh"),
    (re.compile(r"(?i)(?<![\w-])(?:eng|en)(?![\w-])"), "en"),
    (re.compile(r"(?i)(?<![\w-])(?:jpn|ja)(?![\w-])"), "ja"),
    (re.compile(r"(?i)(?<![\w-])(?:kor|ko)(?![\w-])"), "ko"),
)
NOISE_PATTERN = re.compile(
    r"(?i)(?<!\w)(?:proper|repack|rerip|internal|multi|dual|10bit|8bit)(?!\w)"
)
CHANNEL_PATTERN = re.compile(r"(?<!\d)(2[ .]0|5[ .]1|7[ .]1)(?!\d)")
STANDARD_EPISODE = re.compile(
    r"(?i)(?<![A-Za-z0-9])S(?P<season>\d{1,2})[ .-]*E(?P<first>\d{1,4})"
    r"(?P<extra>(?:[ .]*E\d{1,4})*)(?:[ ]*-[ ]*E?(?P<end>\d{1,6}))?"
)
X_EPISODE = re.compile(r"(?i)(?<!\w)(?P<season>\d{1,2})x(?P<episode>\d{1,4})(?!\d)")
BARE_EPISODE = re.compile(r"(?i)(?<![A-Za-z0-9])(?:EP|E)[ ._-]?(?P<episode>\d{1,3})(?!\d)")
CHINESE_EPISODE = re.compile(r"第[ ]*0*(?P<episode>\d{1,4})[ ]*(?:集|话)")
SEASON_DIRECTORY = re.compile(r"(?i)^(?:season[ ._-]*|s)0*(\d{1,2})$")
CHINESE_SEASON_DIRECTORY = re.compile(r"^第[ ]*0*(\d{1,2})[ ]*季$")
MALFORMED_EPISODE = re.compile(r"(?i)(?:S\d{1,2}E(?!\d)|SXXE\d|S\d{1,2}EXX)")
GENERIC_DIRECTORIES = {"downloads", "download", "movies", "movie", "tv", "media", "video", "videos"}


class FilenameNormalizer:
    @staticmethod
    def normalize(value: str) -> str:
        value = value.replace("\u00a0", " ").replace("\u3000", " ")
        value = re.sub(r"[._]+", " ", value)
        value = re.sub(r"[\[\]{}()]", " ", value)
        return re.sub(r"\s+", " ", value).strip()


@dataclass(frozen=True)
class _EpisodeInfo:
    season: int | None = None
    episodes: tuple[int, ...] = ()
    span: tuple[int, int] | None = None
    confidence: EvidenceConfidence = EvidenceConfidence.LOW
    warnings: tuple[ParseWarning, ...] = ()


class FilenameParser:
    def __init__(self, options: ParserOptions | None = None) -> None:
        self.options = options or ParserOptions()

    def parse(self, context: FileContext) -> ParseResult:
        filename = context.filename.strip()
        if not filename or filename in {".", ".."}:
            raise ParserError(ParserErrorCode.INVALID_INPUT, "filename is empty or invalid")
        actual_name = PurePosixPath(filename.replace("\\", "/")).name
        extension = context.extension.lower().lstrip(".")
        if not extension and "." in actual_name:
            extension = actual_name.rsplit(".", 1)[1].lower()
        stem = (
            actual_name[: -(len(extension) + 1)]
            if extension and actual_name.lower().endswith("." + extension)
            else actual_name
        )
        if not stem or not re.search(r"\w", stem, re.UNICODE):
            raise ParserError(ParserErrorCode.INVALID_INPUT, "filename has no parseable content")
        normalized = FilenameNormalizer.normalize(stem)
        return self._parse_text(actual_name, normalized, extension)

    def _parse_text(self, original: str, normalized: str, extension: str) -> ParseResult:
        warnings: list[ParseWarning] = []
        evidence: list[ParseEvidence] = []
        episode = self._episode(normalized)
        warnings.extend(episode.warnings)
        if MALFORMED_EPISODE.search(normalized):
            warnings.append(
                ParseWarning(ParseWarningCode.MALFORMED_EPISODE, "malformed episode marker")
            )

        year, year_span, year_candidates = self._year(normalized)
        if len(year_candidates) > 1:
            warnings.append(
                ParseWarning(ParseWarningCode.MULTIPLE_YEAR_CANDIDATES, "multiple filename years")
            )
        resolution, resolution_match = _first_rule(normalized, RESOLUTION_RULES)
        source, source_match = _first_rule(normalized, SOURCE_RULES)
        video, video_match = _first_rule(normalized, VIDEO_RULES)
        audio, audio_match = _first_rule(normalized, AUDIO_RULES)
        hdr_tags, hdr_matches = _all_rules(normalized, HDR_RULES)
        versions, version_matches = _all_rules(normalized, VERSION_RULES)
        languages, language_matches = _all_rules(normalized, LANGUAGE_RULES)
        channel_match = CHANNEL_PATTERN.search(normalized)
        channels = channel_match.group(1).replace(" ", ".") if channel_match else None
        noise_matches = tuple(NOISE_PATTERN.finditer(normalized))

        boundary_spans = [
            span
            for span in (
                episode.span,
                year_span,
                _span(resolution_match),
                _span(source_match),
                _span(video_match),
                _span(audio_match),
                _span(channel_match),
            )
            if span is not None
        ]
        boundary_spans.extend(
            match.span() for match in hdr_matches + version_matches + noise_matches
        )
        boundary = min((span[0] for span in boundary_spans), default=len(normalized))
        title = _clean_title(normalized[:boundary])
        release_group = self._release_group(original, bool(boundary_spans))
        if release_group and title.endswith("-" + release_group):
            title = title[: -(len(release_group) + 1)].rstrip()
        raw_region = normalized[boundary:].strip()
        raw_tags = tuple(dict.fromkeys(token for token in raw_region.split() if token))

        if title:
            evidence.append(
                ParseEvidence(
                    "title_candidate", title, EvidenceSource.FILENAME, EvidenceConfidence.HIGH
                )
            )
        if year is not None:
            evidence.append(
                ParseEvidence("year", str(year), EvidenceSource.FILENAME, EvidenceConfidence.HIGH)
            )
        if episode.season is not None:
            evidence.append(
                ParseEvidence(
                    "season", str(episode.season), EvidenceSource.FILENAME, episode.confidence
                )
            )
        if episode.episodes:
            evidence.append(
                ParseEvidence(
                    "episodes",
                    ",".join(map(str, episode.episodes)),
                    EvidenceSource.FILENAME,
                    episode.confidence,
                )
            )
        for field, value in (
            ("resolution_tag", resolution),
            ("source_tag", source),
            ("video_codec_tag", video),
            ("audio_codec_tag", audio),
        ):
            if value:
                evidence.append(
                    ParseEvidence(field, value, EvidenceSource.FILENAME, EvidenceConfidence.HIGH)
                )

        return ParseResult(
            title_candidate=title,
            year=year,
            season=episode.season,
            episode=episode.episodes[0] if episode.episodes else None,
            episodes=episode.episodes,
            resolution_tag=resolution,
            source_tag=source,
            video_codec_tag=video,
            audio_tag=audio,
            hdr_tag=hdr_tags[0] if hdr_tags else None,
            version_tag=versions[0] if versions else None,
            release_group=release_group,
            original_filename=original,
            normalized_filename=normalized,
            audio_codec_tag=audio,
            audio_channels_tag=channels,
            hdr_tags=hdr_tags,
            version_tags=versions,
            language_tags=languages,
            extension=extension,
            raw_tags=raw_tags,
            evidence=tuple(evidence),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def _year(self, normalized: str) -> tuple[int | None, tuple[int, int] | None, tuple[int, ...]]:
        matches = tuple(re.finditer(r"(?<!\d)(\d{4})(?!\d)", normalized))
        valid = tuple(
            match
            for match in matches
            if self.options.year_min <= int(match.group(1)) <= self.options.year_max
        )
        if not valid:
            return None, None, ()
        selected = valid[0]
        if len(valid) > 1:
            between = normalized[valid[0].end() : valid[-1].start()]
            has_release_version = any(pattern.search(between) for pattern, _ in VERSION_RULES)
            if not has_release_version:
                selected = valid[-1]
        return (
            int(selected.group(1)),
            selected.span(),
            tuple(int(match.group(1)) for match in valid),
        )

    def _episode(self, normalized: str) -> _EpisodeInfo:
        match = STANDARD_EPISODE.search(normalized)
        if match:
            season = int(match.group("season"))
            first = int(match.group("first"))
            extras = tuple(
                int(value) for value in re.findall(r"(?i)E(\d{1,4})", match.group("extra"))
            )
            end_text = match.group("end")
            if end_text:
                end = int(end_text)
                if end < first or end - first + 1 > self.options.episode_range_limit:
                    warning = ParseWarning(
                        ParseWarningCode.INVALID_EPISODE_RANGE,
                        "episode range exceeds safety limit or is reversed",
                    )
                    return _EpisodeInfo(
                        season, (first,), match.span(), EvidenceConfidence.HIGH, (warning,)
                    )
                episodes = tuple(range(first, end + 1))
            else:
                episodes = tuple(dict.fromkeys((first, *extras)))
            return _EpisodeInfo(season, episodes, match.span(), EvidenceConfidence.HIGH)
        match = X_EPISODE.search(normalized)
        if match:
            return _EpisodeInfo(
                int(match.group("season")),
                (int(match.group("episode")),),
                match.span(),
                EvidenceConfidence.HIGH,
            )
        if self.options.enable_chinese_episode_patterns:
            match = CHINESE_EPISODE.search(normalized)
            if match:
                return _EpisodeInfo(
                    None, (int(match.group("episode")),), match.span(), EvidenceConfidence.HIGH
                )
        match = BARE_EPISODE.search(normalized)
        if match:
            return _EpisodeInfo(
                None, (int(match.group("episode")),), match.span(), EvidenceConfidence.LOW
            )
        return _EpisodeInfo()

    @staticmethod
    def _release_group(original: str, has_release_tag: bool) -> str | None:
        if not has_release_tag:
            return None
        stem = original.rsplit(".", 1)[0] if "." in original else original
        match = re.search(r"-([A-Za-z0-9][A-Za-z0-9_.]{1,31})$", stem)
        return match.group(1) if match else None


@dataclass(frozen=True)
class PathParseResult:
    title_candidate: str = ""
    year: int | None = None
    season: int | None = None
    evidence: tuple[ParseEvidence, ...] = ()


class PathParser:
    def __init__(self, options: ParserOptions | None = None) -> None:
        self.options = options or ParserOptions()

    def parse(self, context: FileContext) -> PathParseResult:
        directories = context.parent_directories or self._directories(context)
        directories = tuple(
            value for value in directories[-4:] if value and value not in {"/", "."}
        )
        season = None
        season_index = None
        evidence: list[ParseEvidence] = []
        for index in range(len(directories) - 1, -1, -1):
            directory = FilenameNormalizer.normalize(directories[index])
            match = SEASON_DIRECTORY.fullmatch(directory) or CHINESE_SEASON_DIRECTORY.fullmatch(
                directory
            )
            if match:
                season = int(match.group(1))
                season_index = index
                evidence.append(
                    ParseEvidence(
                        "season",
                        str(season),
                        EvidenceSource.SEASON_DIRECTORY,
                        EvidenceConfidence.HIGH,
                    )
                )
                break
        title_directory = ""
        if season_index is not None and season_index > 0:
            title_directory = directories[season_index - 1]
        elif directories:
            candidate = directories[-1]
            if not (
                SEASON_DIRECTORY.fullmatch(FilenameNormalizer.normalize(candidate))
                or CHINESE_SEASON_DIRECTORY.fullmatch(FilenameNormalizer.normalize(candidate))
            ):
                title_directory = candidate
        normalized = FilenameNormalizer.normalize(title_directory)
        year, span = self._year(normalized)
        title = _clean_title(normalized[: span[0] if span else len(normalized)])
        if title.lower() in GENERIC_DIRECTORIES:
            title = ""
        if title:
            evidence.append(
                ParseEvidence(
                    "title_candidate",
                    title,
                    EvidenceSource.PARENT_DIRECTORY,
                    EvidenceConfidence.MEDIUM,
                )
            )
        if year is not None:
            evidence.append(
                ParseEvidence(
                    "year", str(year), EvidenceSource.PARENT_DIRECTORY, EvidenceConfidence.MEDIUM
                )
            )
        return PathParseResult(title, year, season, tuple(evidence))

    def _year(self, value: str) -> tuple[int | None, tuple[int, int] | None]:
        for match in re.finditer(r"(?<!\d)(\d{4})(?!\d)", value):
            year = int(match.group(1))
            if self.options.year_min <= year <= self.options.year_max:
                return year, match.span()
        return None, None

    @staticmethod
    def _directories(context: FileContext) -> tuple[str, ...]:
        path = context.parent_path or str(PurePosixPath(context.path.replace("\\", "/")).parent)
        return tuple(part for part in PurePosixPath(path).parts if part not in {"/", "."})


class ParseResultMerger:
    @staticmethod
    def merge(filename: ParseResult, path: PathParseResult) -> ParseResult:
        warnings = list(filename.warnings)
        alternatives = list(filename.alternative_title_candidates)
        title = filename.title_candidate
        if path.title_candidate:
            if not title or title.isdigit():
                if title and title != path.title_candidate:
                    alternatives.append(title)
                title = path.title_candidate
            elif _comparable(title) != _comparable(path.title_candidate):
                alternatives.append(path.title_candidate)
                warnings.append(
                    ParseWarning(
                        ParseWarningCode.CONFLICTING_TITLE,
                        "filename and directory title candidates conflict",
                    )
                )
        year = filename.year if filename.year is not None else path.year
        if filename.year is not None and path.year is not None and filename.year != path.year:
            warnings.append(
                ParseWarning(
                    ParseWarningCode.CONFLICTING_YEAR,
                    "filename and directory year candidates conflict",
                )
            )
        season = filename.season if filename.season is not None else path.season
        if (
            filename.season is not None
            and path.season is not None
            and filename.season != path.season
        ):
            warnings.append(
                ParseWarning(
                    ParseWarningCode.CONFLICTING_SEASON,
                    "filename and directory season candidates conflict",
                )
            )
        return replace(
            filename,
            title_candidate=title,
            alternative_title_candidates=tuple(dict.fromkeys(alternatives)),
            year=year,
            season=season,
            evidence=filename.evidence + path.evidence,
            warnings=tuple(dict.fromkeys(warnings)),
        )


class MediaParserService:
    def __init__(self, options: ParserOptions | None = None) -> None:
        self.options = options or ParserOptions()
        self.filename_parser = FilenameParser(self.options)
        self.path_parser = PathParser(self.options)

    def parse(self, context: FileContext) -> ParseResult:
        filename = self.filename_parser.parse(context)
        path = self.path_parser.parse(context)
        return ParseResultMerger.merge(filename, path)


def _first_rule(value: str, rules):
    best = None
    normalized = None
    for pattern, output in rules:
        match = pattern.search(value)
        if match and (best is None or match.start() < best.start()):
            best = match
            normalized = output or match.group(1).lower()
    return normalized, best


def _all_rules(value: str, rules) -> tuple[tuple[str, ...], tuple[re.Match[str], ...]]:
    found: list[tuple[int, str, re.Match[str]]] = []
    for pattern, output in rules:
        if match := pattern.search(value):
            found.append((match.start(), output, match))
    found.sort(key=lambda item: item[0])
    values = tuple(dict.fromkeys(item[1] for item in found))
    return values, tuple(item[2] for item in found)


def _span(match: re.Match[str] | None) -> tuple[int, int] | None:
    return match.span() if match else None


def _clean_title(value: str) -> str:
    value = re.sub(r"^[\s._-]+|[\s._-]+$", "", value)
    return re.sub(r"\s+", " ", value)


def _comparable(value: str) -> str:
    return re.sub(r"\W+", "", value, flags=re.UNICODE).casefold()
