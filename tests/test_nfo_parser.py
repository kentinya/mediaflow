from __future__ import annotations

import io
import unittest
from datetime import UTC, datetime

from mediaflow.application.media_parser import MediaParserService
from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.nfo_parser import (
    NfoParser,
    NfoParserOptions,
    StorageNfoEnricher,
    merge_nfo,
)
from mediaflow.application.strategy_test import (
    SyntheticMetadataProvider,
    strategy_runner_from_configuration,
)
from mediaflow.domain.metadata import MediaCandidate, MediaType, MetadataIdentificationStatus
from mediaflow.domain.parser import (
    EvidenceSource,
    FileContext,
    NfoErrorCode,
    NfoMediaType,
    NfoParserError,
    ParseWarningCode,
)
from mediaflow.domain.storage import (
    StorageCapabilities,
    StorageEntry,
    StorageEntryType,
    StorageError,
    StorageErrorCode,
)
from mediaflow.infrastructure.strategy_configuration import smoke_strategy_configuration


def file_context(filename: str = "Wrong.Title.1999.mkv") -> FileContext:
    return FileContext("source", "movies", f"incoming/{filename}", filename, ("incoming",))


class ReadOnlyMemoryStorage:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files
        self.calls = {
            name: 0
            for name in (
                "list",
                "read",
                "write",
                "create_directory",
                "move",
                "copy",
                "delete",
                "hard_link",
                "soft_link",
            )
        }
        self.read_sizes: list[int] = []

    storage_id = "source"
    name = "memory"
    read_only = True
    capabilities = StorageCapabilities()

    def list(self, path):
        self.calls["list"] += 1
        prefix = path.rstrip("/") + "/" if path else ""
        return tuple(
            StorageEntry(
                name[len(prefix) :], name, StorageEntryType.FILE, len(value), datetime.now(UTC)
            )
            for name, value in self.files.items()
            if name.startswith(prefix) and "/" not in name[len(prefix) :]
        )

    def read(self, path):
        self.calls["read"] += 1
        owner = self

        class Tracked(io.BytesIO):
            def read(self, size=-1):
                owner.read_sizes.append(size)
                return super().read(size)

        return Tracked(self.files[path])

    def _mutation(self, name):
        self.calls[name] += 1
        raise AssertionError(f"unexpected Storage mutation: {name}")

    def write(self, *args, **kwargs):
        self._mutation("write")

    def create_directory(self, *args, **kwargs):
        self._mutation("create_directory")

    def move(self, *args, **kwargs):
        self._mutation("move")

    def copy(self, *args, **kwargs):
        self._mutation("copy")

    def delete(self, *args, **kwargs):
        self._mutation("delete")

    def hard_link(self, *args, **kwargs):
        self._mutation("hard_link")

    def soft_link(self, *args, **kwargs):
        self._mutation("soft_link")


class NfoParserTests(unittest.TestCase):
    def test_movie_fields_and_ids_are_normalized(self) -> None:
        result = NfoParser().parse("""
            <movie><title>  流浪\u3000地球 </title>
            <originaltitle>The Wandering Earth</originaltitle>
            <premiered>2019-02-05</premiered>
            <uniqueid type="tmdb" default="true">535167</uniqueid><imdbid>tt7605074</imdbid></movie>
        """)
        self.assertEqual(result.media_type, NfoMediaType.MOVIE)
        self.assertEqual(
            (result.title, result.original_title, result.year),
            ("流浪 地球", "The Wandering Earth", 2019),
        )
        self.assertEqual(result.default_provider_id, ("tmdb", "535167"))
        self.assertIn(("imdb", "tt7605074"), result.external_ids)

    def test_tv_and_multi_episode_fields(self) -> None:
        tv = NfoParser().parse(
            "<tvshow><title>Show</title><year>2024</year><tvdbid>42</tvdbid></tvshow>"
        )
        episode = NfoParser().parse(
            "<episodedetails><title>Pair</title><season>0</season><episode>1</episode><episode>3</episode></episodedetails>"
        )
        self.assertEqual(tv.media_type, NfoMediaType.TVSHOW)
        self.assertEqual(episode.media_type, NfoMediaType.EPISODE)
        self.assertEqual((episode.season, episode.episode, episode.episodes), (0, 1, (1, 3)))

    def test_default_and_non_default_unique_ids_are_deterministic(self) -> None:
        result = NfoParser().parse(
            "<movie><uniqueid type='imdb'>tt1</uniqueid>"
            "<uniqueid type='tmdb' default='true'>9</uniqueid>"
            "<id>tt2</id></movie>"
        )
        self.assertEqual(result.default_provider_id, ("tmdb", "9"))
        self.assertEqual(result.provider_ids, (("imdb", "tt1"), ("tmdb", "9"), ("imdb", "tt2")))

    def test_unsafe_malformed_unsupported_and_invalid_values_fail_typed(self) -> None:
        cases = (
            (b"<!DOCTYPE movie><movie/>", NfoErrorCode.UNSAFE_XML),
            (b"<movie>", NfoErrorCode.MALFORMED_XML),
            (b"<musicvideo/>", NfoErrorCode.UNSUPPORTED_ROOT),
            (b"<movie><year>later</year></movie>", NfoErrorCode.INVALID_VALUE),
            (b"<movie><premiered>2025-junk</premiered></movie>", NfoErrorCode.INVALID_VALUE),
            (b"<episodedetails><episode>-1</episode></episodedetails>", NfoErrorCode.INVALID_VALUE),
        )
        for payload, code in cases:
            with self.subTest(code=code), self.assertRaises(NfoParserError) as raised:
                NfoParser().parse(payload)
            self.assertEqual(raised.exception.code, code)

    def test_size_depth_text_id_and_episode_limits(self) -> None:
        cases = (
            (NfoParserOptions(maximum_bytes=7), b"<movie/>", NfoErrorCode.INPUT_TOO_LARGE),
            (
                NfoParserOptions(maximum_depth=2),
                b"<movie><a><b/></a></movie>",
                NfoErrorCode.EXCESSIVE_STRUCTURE,
            ),
            (
                NfoParserOptions(maximum_text_length=3),
                b"<movie><title>long</title></movie>",
                NfoErrorCode.INVALID_VALUE,
            ),
            (
                NfoParserOptions(maximum_ids=1),
                b"<movie><tmdbid>1</tmdbid><imdbid>tt2</imdbid></movie>",
                NfoErrorCode.EXCESSIVE_STRUCTURE,
            ),
            (
                NfoParserOptions(maximum_episodes=1),
                b"<episodedetails><episode>1</episode><episode>2</episode></episodedetails>",
                NfoErrorCode.EXCESSIVE_STRUCTURE,
            ),
        )
        for options, payload, code in cases:
            with self.subTest(code=code), self.assertRaises(NfoParserError) as raised:
                NfoParser(options).parse(payload)
            self.assertEqual(raised.exception.code, code)

    def test_merge_prefers_nfo_semantics_and_preserves_release_tags(self) -> None:
        parsed = MediaParserService().parse(file_context("Wrong.Title.1999.2160p.WEB-DL.mkv"))
        nfo = NfoParser().parse(
            "<movie><title>Correct Title</title><originaltitle>原题</originaltitle>"
            "<year>2025</year><tmdbid>7</tmdbid></movie>"
        )
        merged = merge_nfo(parsed, nfo, "incoming/Wrong.Title.1999.2160p.WEB-DL.nfo")
        self.assertEqual((merged.title_candidate, merged.year), ("Correct Title", 2025))
        self.assertEqual((merged.resolution_tag, merged.source_tag), ("2160p", "WEB-DL"))
        self.assertIn("Wrong Title", merged.alternative_title_candidates)
        self.assertIn("原题", merged.alternative_title_candidates)
        self.assertEqual(merged.provider_id_candidates, (("tmdb", "7"),))
        self.assertTrue(any(item.source is EvidenceSource.NFO for item in merged.evidence))
        codes = {item.code for item in merged.warnings}
        self.assertIn(ParseWarningCode.CONFLICTING_NFO_TITLE, codes)
        self.assertIn(ParseWarningCode.CONFLICTING_NFO_YEAR, codes)

    def test_storage_discovery_prefers_exact_stem_and_is_read_only(self) -> None:
        exact = b"<movie><title>Exact</title><year>2020</year></movie>"
        storage = ReadOnlyMemoryStorage(
            {
                "incoming/movie.nfo": b"<movie><title>Generic</title></movie>",
                "incoming/Film.2020.nfo": exact,
                "incoming/nested/Film.2020.nfo": b"<movie><title>Nested</title></movie>",
            }
        )
        context = file_context("Film.2020.mkv")
        parsed = MediaParserService().parse(context)
        result = StorageNfoEnricher().enrich(storage, context, parsed)
        self.assertEqual(result.title_candidate, "Exact")
        self.assertEqual(result.nfo_path, "incoming/Film.2020.nfo")
        self.assertEqual(storage.calls["list"], 1)
        self.assertEqual(storage.calls["read"], 1)
        self.assertEqual(storage.read_sizes, [1_048_577])
        self.assertEqual(
            sum(storage.calls[name] for name in storage.calls if name not in {"list", "read"}), 0
        )

    def test_missing_nfo_is_noop_and_invalid_nfo_is_warning(self) -> None:
        context = file_context("Film.2020.mkv")
        parsed = MediaParserService().parse(context)
        self.assertIs(
            StorageNfoEnricher().enrich(ReadOnlyMemoryStorage({}), context, parsed), parsed
        )
        invalid = StorageNfoEnricher().enrich(
            ReadOnlyMemoryStorage({"incoming/Film.2020.nfo": b"<!DOCTYPE movie><movie/>"}),
            context,
            parsed,
        )
        self.assertIn(ParseWarningCode.INVALID_NFO, {item.code for item in invalid.warnings})

    def test_conventional_discovery_order_and_storage_failures_are_bounded(self) -> None:
        context = file_context("Film.2020.mkv")
        parsed = MediaParserService().parse(context)
        conventional = ReadOnlyMemoryStorage(
            {
                "incoming/tvshow.nfo": b"<tvshow><title>TV</title></tvshow>",
                "incoming/movie.nfo": b"<movie><title>Movie</title></movie>",
            }
        )
        self.assertEqual(
            StorageNfoEnricher().enrich(conventional, context, parsed).title_candidate,
            "Movie",
        )

        class FailingList(ReadOnlyMemoryStorage):
            def list(self, path):
                raise StorageError(StorageErrorCode.PERMISSION_DENIED, "list", path, "denied")

        failed = StorageNfoEnricher().enrich(FailingList({}), context, parsed)
        self.assertIn(ParseWarningCode.NFO_READ_FAILED, {item.code for item in failed.warnings})

        oversized = ReadOnlyMemoryStorage({"incoming/Film.2020.nfo": b"x" * (1_048_576 + 1)})
        rejected = StorageNfoEnricher().enrich(oversized, context, parsed)
        self.assertIn(ParseWarningCode.INVALID_NFO, {item.code for item in rejected.warnings})
        self.assertEqual(oversized.calls["read"], 0)

    def test_output_is_deterministic(self) -> None:
        parser = NfoParser()
        payload = (
            "<movie><title>Amélie</title><year>2001</year>"
            "<uniqueid type='tmdb'>194</uniqueid></movie>"
        )
        self.assertEqual(parser.parse(payload), parser.parse(payload))

    def test_strategy_pipeline_uses_nfo_and_preserves_recognition_type_c(self) -> None:
        storage = ReadOnlyMemoryStorage(
            {
                "incoming/Wrong.2020.nfo": (
                    b"<movie><title>Correct</title><year>2025</year>"
                    b"<uniqueid type='tmdb'>7</uniqueid></movie>"
                )
            }
        )
        runner = strategy_runner_from_configuration(
            smoke_strategy_configuration(), storages={"source": storage}
        )
        result = runner.run_path(
            "/C/Wrong.2020.mkv",
            resource_library_id="C",
            storage_id="source",
            storage_path="incoming/Wrong.2020.mkv",
        )
        self.assertEqual(result.parsed.title_candidate, "Correct")
        self.assertEqual(result.parsed.provider_id_candidates, (("tmdb", "7"),))
        self.assertEqual(result.recognition.recognition_type_id, "C")
        self.assertEqual(result.policy.naming_policy_id, "A")
        self.assertEqual(
            sum(storage.calls[name] for name in storage.calls if name not in {"list", "read"}), 0
        )

    def test_nfo_evidence_reaches_existing_metadata_matcher(self) -> None:
        storage = ReadOnlyMemoryStorage(
            {
                "incoming/Wrong.1999.nfo": (
                    b"<movie><title>Correct Movie</title><year>2025</year></movie>"
                )
            }
        )
        provider = SyntheticMetadataProvider(
            (MediaCandidate("tmdb", "7", MediaType.MOVIE, "Correct Movie", year=2025),)
        )
        runner = strategy_runner_from_configuration(
            smoke_strategy_configuration(),
            MetadataProviderRegistry((provider,)),
            storages={"source": storage},
        )
        result = runner.run_path(
            "/A/Wrong.1999.mkv",
            live_metadata=True,
            resource_library_id="A",
            storage_id="source",
            storage_path="incoming/Wrong.1999.mkv",
        )
        self.assertEqual(result.metadata.status, MetadataIdentificationStatus.MATCHED)
        self.assertEqual(result.metadata.identity.provider_id, "7")


if __name__ == "__main__":
    unittest.main()
