from __future__ import annotations

import posixpath
import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace

from mediaflow.domain.parser import (
    EvidenceConfidence,
    EvidenceSource,
    FileContext,
    NfoErrorCode,
    NfoMediaType,
    NfoParserError,
    NfoParseResult,
    ParseEvidence,
    ParseResult,
    ParseWarning,
    ParseWarningCode,
)
from mediaflow.domain.storage import Storage, StorageEntryType, StorageError

_UNSAFE_XML = re.compile(rb"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)
_DATE_YEAR = re.compile(r"^(\d{4})(?:[-/.]\d{1,2}[-/.]\d{1,2})?$")
_ID_VALUE = re.compile(r"^[A-Za-z0-9_.:-]{1,200}$")


@dataclass(frozen=True)
class NfoParserOptions:
    maximum_bytes: int = 1_048_576
    maximum_depth: int = 32
    maximum_elements: int = 2_000
    maximum_text_length: int = 4_096
    maximum_ids: int = 32
    maximum_episodes: int = 100
    year_min: int = 1800
    year_max: int = 2200

    def __post_init__(self) -> None:
        if (
            min(
                self.maximum_bytes,
                self.maximum_depth,
                self.maximum_elements,
                self.maximum_text_length,
                self.maximum_ids,
                self.maximum_episodes,
            )
            < 1
        ):
            raise ValueError("NFO parser limits must be positive")
        if self.year_min < 1 or self.year_max < self.year_min:
            raise ValueError("invalid NFO year range")


class NfoParser:
    """Bounded parser for provider-neutral Kodi/Jellyfin-style NFO evidence."""

    def __init__(self, options: NfoParserOptions | None = None) -> None:
        self.options = options or NfoParserOptions()

    def parse(self, payload: bytes | str) -> NfoParseResult:
        raw = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
        if not raw.strip():
            raise NfoParserError(NfoErrorCode.INVALID_INPUT, "NFO is empty")
        if len(raw) > self.options.maximum_bytes:
            raise NfoParserError(NfoErrorCode.INPUT_TOO_LARGE, "NFO exceeds byte limit")
        if _UNSAFE_XML.search(raw):
            raise NfoParserError(
                NfoErrorCode.UNSAFE_XML, "DTD and entity declarations are forbidden"
            )
        try:
            root = ET.fromstring(raw)
        except (ET.ParseError, UnicodeError) as error:
            raise NfoParserError(NfoErrorCode.MALFORMED_XML, "NFO XML is malformed") from error
        root_name = _tag(root.tag)
        try:
            media_type = NfoMediaType(root_name)
        except ValueError as error:
            raise NfoParserError(
                NfoErrorCode.UNSUPPORTED_ROOT, f"unsupported NFO root {root_name!r}"
            ) from error
        self._validate_structure(root)

        title = self._text(root, "title")
        original_title = self._text(root, "originaltitle") or self._text(root, "original_title")
        year = self._year(root)
        season = self._number(root, "season")
        episodes = self._episodes(root)
        provider_ids, external_ids, default_provider_id = self._ids(root)
        return NfoParseResult(
            media_type=media_type,
            title=title,
            original_title=original_title,
            year=year,
            season=season,
            episode=episodes[0] if episodes else None,
            episodes=episodes,
            provider_ids=provider_ids,
            external_ids=external_ids,
            default_provider_id=default_provider_id,
        )

    def _validate_structure(self, root: ET.Element) -> None:
        count = 0
        stack = [(root, 1)]
        while stack:
            element, depth = stack.pop()
            count += 1
            if count > self.options.maximum_elements or depth > self.options.maximum_depth:
                raise NfoParserError(
                    NfoErrorCode.EXCESSIVE_STRUCTURE, "NFO XML structure exceeds limits"
                )
            if element.text and len(element.text) > self.options.maximum_text_length:
                raise NfoParserError(NfoErrorCode.INVALID_VALUE, "NFO text exceeds limit")
            stack.extend((child, depth + 1) for child in element)

    def _text(self, root: ET.Element, name: str) -> str | None:
        element = next((item for item in root.iter() if _tag(item.tag) == name), None)
        if element is None or element.text is None:
            return None
        value = _normalize_text(element.text)
        if len(value) > self.options.maximum_text_length:
            raise NfoParserError(NfoErrorCode.INVALID_VALUE, f"NFO {name} exceeds limit")
        return value or None

    def _number(self, root: ET.Element, name: str) -> int | None:
        value = self._text(root, name)
        if value is None:
            return None
        if not value.isdecimal():
            raise NfoParserError(NfoErrorCode.INVALID_VALUE, f"NFO {name} is invalid")
        number = int(value)
        if number < 0 or number > 100_000:
            raise NfoParserError(NfoErrorCode.INVALID_VALUE, f"NFO {name} is out of range")
        return number

    def _year(self, root: ET.Element) -> int | None:
        value = self._text(root, "year") or self._text(root, "premiered")
        if value is None:
            return None
        match = _DATE_YEAR.fullmatch(value)
        if not match:
            raise NfoParserError(NfoErrorCode.INVALID_VALUE, "NFO year/date is invalid")
        year = int(match.group(1))
        if not self.options.year_min <= year <= self.options.year_max:
            raise NfoParserError(NfoErrorCode.INVALID_VALUE, "NFO year is out of range")
        return year

    def _episodes(self, root: ET.Element) -> tuple[int, ...]:
        values: list[int] = []
        for element in root.iter():
            if _tag(element.tag) != "episode" or element.text is None:
                continue
            text = _normalize_text(element.text)
            if not text.isdecimal():
                raise NfoParserError(NfoErrorCode.INVALID_VALUE, "NFO episode is invalid")
            number = int(text)
            if number < 0 or number > 100_000:
                raise NfoParserError(NfoErrorCode.INVALID_VALUE, "NFO episode is out of range")
            values.append(number)
            if len(values) > self.options.maximum_episodes:
                raise NfoParserError(
                    NfoErrorCode.EXCESSIVE_STRUCTURE, "NFO episode count exceeds limit"
                )
        return tuple(dict.fromkeys(values))

    def _ids(
        self, root: ET.Element
    ) -> tuple[tuple[tuple[str, str], ...], tuple[tuple[str, str], ...], tuple[str, str] | None]:
        values: list[tuple[str, str]] = []
        defaults: list[tuple[str, str]] = []
        for element in root.iter():
            name = _tag(element.tag)
            if name not in {"uniqueid", "tmdbid", "imdbid", "tvdbid", "id"}:
                continue
            value = _normalize_text(element.text or "")
            if not value:
                continue
            provider = {
                "tmdbid": "tmdb",
                "imdbid": "imdb",
                "tvdbid": "tvdb",
                "id": "imdb" if value.startswith("tt") else "legacy",
            }.get(name, _normalize_identifier(element.attrib.get("type", "legacy")))
            if not provider or not _ID_VALUE.fullmatch(value):
                raise NfoParserError(NfoErrorCode.INVALID_VALUE, "NFO provider ID is invalid")
            pair = (provider, value)
            if pair not in values:
                values.append(pair)
            if element.attrib.get("default", "").casefold() in {"true", "1", "yes"}:
                defaults.append(pair)
            if len(values) > self.options.maximum_ids:
                raise NfoParserError(
                    NfoErrorCode.EXCESSIVE_STRUCTURE, "NFO provider ID count exceeds limit"
                )
        provider_ids = tuple(values)
        external_ids = tuple(item for item in values if item[0] not in {"tmdb", "legacy"})
        default = defaults[0] if defaults else (values[0] if values else None)
        return provider_ids, external_ids, default


class StorageNfoEnricher:
    """Discovers and reads one deterministic sidecar through the Storage read port only."""

    def __init__(self, parser: NfoParser | None = None) -> None:
        self.parser = parser or NfoParser()

    def enrich(self, storage: Storage, context: FileContext, parsed: ParseResult) -> ParseResult:
        parent, filename = posixpath.split(context.path)
        stem = posixpath.splitext(filename)[0]
        try:
            entries = storage.list(parent)
        except StorageError as error:
            return _warning(
                parsed, ParseWarningCode.NFO_READ_FAILED, f"NFO list failed: {error.code.value}"
            )
        files = {
            item.name.casefold(): item
            for item in entries
            if item.entry_type is StorageEntryType.FILE
        }
        selected = next(
            (
                files[name.casefold()]
                for name in (f"{stem}.nfo", "movie.nfo", "tvshow.nfo")
                if name.casefold() in files
            ),
            None,
        )
        if selected is None:
            return parsed
        if selected.size > self.parser.options.maximum_bytes:
            return _warning(parsed, ParseWarningCode.INVALID_NFO, "NFO exceeds byte limit")
        try:
            with storage.read(selected.path) as stream:
                payload = stream.read(self.parser.options.maximum_bytes + 1)
        except (StorageError, OSError) as error:
            code = error.code.value if isinstance(error, StorageError) else "io_error"
            return _warning(parsed, ParseWarningCode.NFO_READ_FAILED, f"NFO read failed: {code}")
        try:
            nfo = self.parser.parse(payload)
        except NfoParserError as error:
            return _warning(
                parsed, ParseWarningCode.INVALID_NFO, f"NFO rejected: {error.code.value}"
            )
        return merge_nfo(parsed, nfo, selected.path)


def merge_nfo(parsed: ParseResult, nfo: NfoParseResult, nfo_path: str | None = None) -> ParseResult:
    warnings = list(parsed.warnings)
    alternatives = list(parsed.alternative_title_candidates)
    evidence = list(parsed.evidence)
    title = parsed.title_candidate
    if nfo.title:
        if title and _comparable(title) != _comparable(nfo.title):
            warnings.append(
                ParseWarning(
                    ParseWarningCode.CONFLICTING_NFO_TITLE, "NFO and filename/path titles conflict"
                )
            )
            alternatives.append(title)
        title = nfo.title
        evidence.append(
            ParseEvidence("title_candidate", title, EvidenceSource.NFO, EvidenceConfidence.HIGH)
        )
    if nfo.original_title and _comparable(nfo.original_title) != _comparable(title):
        alternatives.append(nfo.original_title)
        evidence.append(
            ParseEvidence(
                "original_title_candidate",
                nfo.original_title,
                EvidenceSource.NFO,
                EvidenceConfidence.HIGH,
            )
        )
    year = _merge_number(
        parsed.year, nfo.year, ParseWarningCode.CONFLICTING_NFO_YEAR, "year", warnings, evidence
    )
    season = _merge_number(
        parsed.season,
        nfo.season,
        ParseWarningCode.CONFLICTING_NFO_SEASON,
        "season",
        warnings,
        evidence,
    )
    episodes = parsed.episodes
    if nfo.episodes:
        if episodes and episodes != nfo.episodes:
            warnings.append(
                ParseWarning(
                    ParseWarningCode.CONFLICTING_NFO_EPISODE,
                    "NFO and filename/path episodes conflict",
                )
            )
        episodes = nfo.episodes
        evidence.append(
            ParseEvidence(
                "episodes",
                ",".join(map(str, episodes)),
                EvidenceSource.NFO,
                EvidenceConfidence.HIGH,
            )
        )
    return replace(
        parsed,
        title_candidate=title,
        alternative_title_candidates=tuple(
            dict.fromkeys(value for value in alternatives if value and value != title)
        ),
        original_title_candidate=nfo.original_title or parsed.original_title_candidate,
        year=year,
        season=season,
        episode=episodes[0] if episodes else parsed.episode,
        episodes=episodes,
        evidence=tuple(evidence),
        warnings=tuple(dict.fromkeys(warnings)),
        nfo_media_type=nfo.media_type,
        provider_id_candidates=tuple(
            dict.fromkeys((*parsed.provider_id_candidates, *nfo.provider_ids))
        ),
        external_id_candidates=tuple(
            dict.fromkeys((*parsed.external_id_candidates, *nfo.external_ids))
        ),
        nfo_path=nfo_path,
    )


def _merge_number(current, incoming, code, field, warnings, evidence):
    if incoming is None:
        return current
    if current is not None and current != incoming:
        warnings.append(ParseWarning(code, f"NFO and filename/path {field} values conflict"))
    evidence.append(
        ParseEvidence(field, str(incoming), EvidenceSource.NFO, EvidenceConfidence.HIGH)
    )
    return incoming


def _tag(value: str) -> str:
    return value.rsplit("}", 1)[-1].casefold()


def _normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def _normalize_identifier(value: str) -> str:
    normalized = value.strip().casefold()
    return normalized if re.fullmatch(r"[a-z0-9_.-]{1,50}", normalized) else ""


def _comparable(value: str) -> str:
    return re.sub(r"\W+", "", value, flags=re.UNICODE).casefold()


def _warning(parsed: ParseResult, code: ParseWarningCode, message: str) -> ParseResult:
    return replace(parsed, warnings=(*parsed.warnings, ParseWarning(code, message)))
