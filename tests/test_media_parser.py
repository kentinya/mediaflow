from __future__ import annotations

import time
import unittest

from mediaflow.application.media_parser import MediaParserService, ParserOptions
from mediaflow.domain.parser import (
    FileContext,
    ParserError,
    ParseWarningCode,
)


def context(filename: str, *directories: str) -> FileContext:
    path = "/".join((*directories, filename))
    return FileContext("storage", "library", path, filename, tuple(directories))


# More than fifty deliberately varied real-world-style cases. Expected values are
# partial because absence is as meaningful as presence in a best-effort parser.
CASES = (
    (
        "The.Matrix.1999.1080p.BluRay.x264-GRP.mkv",
        (),
        {
            "title_candidate": "The Matrix",
            "year": 1999,
            "resolution_tag": "1080p",
            "source_tag": "BLURAY",
            "video_codec_tag": "H264",
            "release_group": "GRP",
        },
    ),
    (
        "Dune.Part.Two.2024.2160p.WEB-DL.H265.mkv",
        (),
        {
            "title_candidate": "Dune Part Two",
            "year": 2024,
            "resolution_tag": "2160p",
            "source_tag": "WEB-DL",
            "video_codec_tag": "H265",
        },
    ),
    (
        "2001.A.Space.Odyssey.1968.1080p.mkv",
        (),
        {"title_candidate": "2001 A Space Odyssey", "year": 1968},
    ),
    (
        "Title.1999.Remastered.2024.1080p.mkv",
        (),
        {"title_candidate": "Title", "year": 1999, "version_tag": "REMASTERED"},
    ),
    (
        "Blade.Runner.2049.2017.2160p.mkv",
        (),
        {"title_candidate": "Blade Runner 2049", "year": 2017},
    ),
    ("十二怒汉.1957.1080p.mkv", (), {"title_candidate": "十二怒汉", "year": 1957}),
    ("千と千尋の神隠し.2001.BluRay.mkv", (), {"title_candidate": "千と千尋の神隠し", "year": 2001}),
    ("Amélie.2001.1080p.mkv", (), {"title_candidate": "Amélie", "year": 2001}),
    ("Cidade de Deus (2002) [1080p].mkv", (), {"title_candidate": "Cidade de Deus", "year": 2002}),
    ("Wall-E.2008.720p.mkv", (), {"title_candidate": "Wall-E", "year": 2008}),
    (
        "The.Last.of.Us.S01E03.2160p.WEB-DL.DDP5.1.H.265.mkv",
        ("The.Last.of.Us.2023", "Season 01"),
        {
            "title_candidate": "The Last of Us",
            "year": 2023,
            "season": 1,
            "episode": 3,
            "episodes": (3,),
            "audio_codec_tag": "EAC3",
            "audio_channels_tag": "5.1",
            "video_codec_tag": "H265",
        },
    ),
    ("Breaking.Bad.S1E1.720p.mkv", (), {"season": 1, "episode": 1}),
    ("Show.S01E01E02.1080p.mkv", (), {"episodes": (1, 2)}),
    ("Show.S01E01E02E03.mkv", (), {"episodes": (1, 2, 3)}),
    ("Show.S01E01-E03.1080p.mkv", (), {"episodes": (1, 2, 3)}),
    ("Show.S01E01-03.1080p.mkv", (), {"episodes": (1, 2, 3)}),
    ("Show.1x01.HDTV.mkv", (), {"season": 1, "episode": 1, "source_tag": "HDTV"}),
    ("Show.01x01.mkv", (), {"season": 1, "episode": 1}),
    ("Show.EP01.mkv", (), {"episode": 1}),
    ("Show.ep02.mkv", (), {"episode": 2}),
    ("Show.E01.mkv", (), {"episode": 1}),
    ("动画.第01集.1080p.mkv", (), {"episode": 1}),
    ("动画.第1集.mkv", (), {"episode": 1}),
    ("动画.第01话.mkv", (), {"episode": 1}),
    ("动画.第1话.1080p.mkv", (), {"episode": 1}),
    (
        "S01E03.mkv",
        ("The Last of Us 2023", "Season 1"),
        {"title_candidate": "The Last of Us", "year": 2023, "season": 1, "episode": 3},
    ),
    (
        "03.mkv",
        ("Some Show 2020", "S02"),
        {"title_candidate": "Some Show", "year": 2020, "season": 2},
    ),
    ("Show.S02.E05.WEBRip.mkv", (), {"season": 2, "episode": 5, "source_tag": "WEBRIP"}),
    ("Show.S02-E05.mkv", (), {"season": 2, "episode": 5}),
    ("Show.12x123.mkv", (), {"season": 12, "episode": 123}),
    ("Show.E123.mkv", (), {"episode": 123}),
    (
        "Film.2020.4K.UHD.BluRay.REMUX.mkv",
        (),
        {"year": 2020, "resolution_tag": "2160p", "source_tag": "BLURAY"},
    ),
    ("Film.2020.1080i.BDRip.mkv", (), {"resolution_tag": "1080i", "source_tag": "BDRIP"}),
    ("Film.2020.720p.BRRip.mkv", (), {"source_tag": "BRRIP"}),
    ("Film.2020.576p.DVDRip.mkv", (), {"resolution_tag": "576p", "source_tag": "DVD"}),
    ("Film.2020.480p.WEBRip.mkv", (), {"resolution_tag": "480p", "source_tag": "WEBRIP"}),
    ("Film.2020.WEBDL.mkv", (), {"source_tag": "WEB-DL"}),
    ("Film.2020.WEB-Rip.mkv", (), {"source_tag": "WEBRIP"}),
    ("Film.2020.REMUX.mkv", (), {"source_tag": "REMUX"}),
    ("Film.2020.x265.mkv", (), {"video_codec_tag": "H265"}),
    ("Film.2020.HEVC.mkv", (), {"video_codec_tag": "H265"}),
    ("Film.2020.AVC.mkv", (), {"video_codec_tag": "H264"}),
    ("Film.2020.AV1.mkv", (), {"video_codec_tag": "AV1"}),
    ("Film.2020.VP9.mkv", (), {"video_codec_tag": "VP9"}),
    (
        "Film.2020.TrueHD.Atmos.7.1.mkv",
        (),
        {"audio_codec_tag": "TRUEHD", "audio_channels_tag": "7.1"},
    ),
    (
        "Film.2020.DTS-HD.MA.5.1.mkv",
        (),
        {"audio_codec_tag": "DTS-HD MA", "audio_channels_tag": "5.1"},
    ),
    ("Film.2020.AAC.2.0.mkv", (), {"audio_codec_tag": "AAC", "audio_channels_tag": "2.0"}),
    ("Film.2020.AC3.mkv", (), {"audio_codec_tag": "AC3"}),
    ("Film.2020.DD.mkv", (), {"audio_codec_tag": "AC3"}),
    ("Film.2020.E-AC3.mkv", (), {"audio_codec_tag": "EAC3"}),
    ("Film.2020.DTS.mkv", (), {"audio_codec_tag": "DTS"}),
    ("Film.2020.FLAC.mkv", (), {"audio_codec_tag": "FLAC"}),
    ("Film.2020.OPUS.mkv", (), {"audio_codec_tag": "OPUS"}),
    ("Film.2020.PCM.mkv", (), {"audio_codec_tag": "PCM"}),
    ("Film.2020.DV.HDR10Plus.mkv", (), {"hdr_tags": ("DV", "HDR10+")}),
    ("Film.2020.HDR10.mkv", (), {"hdr_tag": "HDR10"}),
    ("Film.2020.HDR.mkv", (), {"hdr_tag": "HDR"}),
    ("Film.2020.Extended.Cut.mkv", (), {"version_tag": "EXTENDED"}),
    ("Film.2020.Directors.Cut.mkv", (), {"version_tag": "DIRECTOR'S CUT"}),
    ("Film.2020.Theatrical.mkv", (), {"version_tag": "THEATRICAL"}),
    ("Film.2020.Unrated.mkv", (), {"version_tag": "UNRATED"}),
    ("Film.2020.IMAX.mkv", (), {"version_tag": "IMAX"}),
    ("Film.2020.Special.Edition.mkv", (), {"version_tag": "SPECIAL EDITION"}),
    ("Film.2020.Anniversary.mkv", (), {"version_tag": "ANNIVERSARY"}),
    ("Film.2020.CHS.ENG.mkv", (), {"language_tags": ("zh-CN", "en")}),
    ("Film.2020.zh-TW.jpn.mkv", (), {"language_tags": ("zh-TW", "ja")}),
    ("Film.2020.kor.mkv", (), {"language_tags": ("ko",)}),
    ("Movie_Name__2023__1080p.mkv", (), {"title_candidate": "Movie Name", "year": 2023}),
    (
        "Movie (2023) [WEB-DL] {H265}.mkv",
        (),
        {"title_candidate": "Movie", "year": 2023, "source_tag": "WEB-DL"},
    ),
    (
        "A.B.C.2022.PROPER.REPACK.1080p-GROUP.mkv",
        (),
        {"title_candidate": "A B C", "year": 2022, "release_group": "GROUP"},
    ),
    ("No.Year.Movie.1080p.mkv", (), {"title_candidate": "No Year Movie", "year": None}),
    ("Future.Movie.2200.1080p.mkv", (), {"year": None}),
    ("Old.Movie.1899.1080p.mkv", (), {"year": None}),
    ("Show.S01E03.mkv", ("Other Show 2021", "Season 02"), {"season": 1, "episode": 3}),
    ("Movie.2020.1080p.mkv", ("Movie 2019",), {"title_candidate": "Movie", "year": 2020}),
    (
        "episode.S03E07.mkv",
        ("Downloads", "TV", "Unicode 剧集 2024", "第03季"),
        {"season": 3, "episode": 7, "year": 2024},
    ),
    (
        "plain-file.mp4",
        ("Movies", "Plain File"),
        {"title_candidate": "plain-file", "extension": "mp4"},
    ),
)


class MediaParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = MediaParserService()

    def test_representative_filename_and_path_corpus(self) -> None:
        self.assertGreaterEqual(len(CASES), 50)
        for filename, directories, expected in CASES:
            with self.subTest(filename=filename, directories=directories):
                result = self.parser.parse(context(filename, *directories))
                for field, value in expected.items():
                    self.assertEqual(getattr(result, field), value, field)

    def test_conflicts_are_preserved_as_warnings_and_alternatives(self) -> None:
        result = self.parser.parse(
            context("Movie.2020.S01E01.mkv", "Other Movie 2019", "Season 02")
        )
        codes = {warning.code for warning in result.warnings}
        self.assertTrue(
            {
                ParseWarningCode.CONFLICTING_TITLE,
                ParseWarningCode.CONFLICTING_YEAR,
                ParseWarningCode.CONFLICTING_SEASON,
            }
            <= codes
        )
        self.assertIn("Other Movie", result.alternative_title_candidates)

    def test_invalid_and_malformed_inputs_are_safe(self) -> None:
        for filename in ("", ".", "..", "....mkv"):
            with self.subTest(filename=filename), self.assertRaises(ParserError):
                self.parser.parse(context(filename))
        result = self.parser.parse(context("Show.S01EXX.1080p.mkv"))
        self.assertIn(ParseWarningCode.MALFORMED_EPISODE, {item.code for item in result.warnings})

    def test_episode_range_is_bounded(self) -> None:
        result = MediaParserService(ParserOptions(episode_range_limit=10)).parse(
            context("Show.S01E01-E999999.mkv")
        )
        self.assertEqual(result.episodes, (1,))
        self.assertIn(
            ParseWarningCode.INVALID_EPISODE_RANGE, {item.code for item in result.warnings}
        )

    def test_parser_is_deterministic_and_handles_long_adversarial_input_quickly(self) -> None:
        value = ("A." * 5000) + "S01E01.2024.1080p.mkv"
        started = time.monotonic()
        first = self.parser.parse(context(value))
        second = self.parser.parse(context(value))
        self.assertEqual(first, second)
        self.assertLess(time.monotonic() - started, 1.0)

    def test_parser_does_not_change_input_or_touch_external_state(self) -> None:
        item = context("Film.2020.1080p.mkv", "Movies")
        before = repr(item)
        self.parser.parse(item)
        self.assertEqual(repr(item), before)


if __name__ == "__main__":
    unittest.main()
