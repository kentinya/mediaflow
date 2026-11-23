"""PATCH-20261111-1 — the Metadata correction search forwards the current year.

The per-item Metadata correction search must submit the operator's current
year input to the MetadataProvider: an edited year as that exact integer, an
explicitly cleared year as ``None``, and a legacy body without the field with
the historical original-year semantics. Invalid parameters are refused before
any Provider call, a search stays a read-only Provider query, and a saved
correction later analyzes with the same query conditions.

Every journey here runs the real managed layout, the real CLI organize
admission, the real resident Worker analysis, the real ``MediaFlowApi`` and
the real ``TaskItemRecoveryService`` over one temporary SQLite database with a
local year-sensitive recording Provider. No external service is contacted.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from datetime import timedelta
from os import utime
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.metadata import MetadataProviderRegistry
from mediaflow.application.strategy_test import SyntheticMetadataProvider
from mediaflow.domain.metadata import (
    EpisodeIdentity,
    MediaCandidate,
    MediaIdentity,
    MediaType,
    MetadataError,
    MetadataErrorCode,
)
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION
from tests.test_automation_entrance_recovery import (
    ADMIN_TOKEN,
    _Clock,
    entrance_journey,
)

VIEWER_TOKEN = "metadata-search-viewer"

#: The exact filename the TV journeys parse to ``title "Probe"``,
#: ``year 2025`` and one season/episode, so the saved correction review
#: starts with original year 2025 and media type ``tv``.
TV_MEDIA = "Probe.2025.S01E01.mkv"
MOVIE_MEDIA = "Probe.2025.mkv"

TV_RULE = {
    "id": "probe-tv",
    "name": "Probe TV",
    "priority": 100,
    "score": 100,
    "stopOnMatch": True,
    "condition": {"field": "extension", "operator": "in", "value": ["mkv", "mp4"]},
    "outputRecognitionType": "B",
}


class RecordingYearProvider(SyntheticMetadataProvider):
    """Local Provider whose candidates depend on the queried year.

    Every search input is recorded so the assertions observe the exact
    ``(media type, title, year)`` tuple the recovery service forwarded. The
    corrected year 2024 resolves to candidate ``901``, an explicitly cleared
    year to candidate ``902`` and the original year 2025 to no candidate at
    all — the same shape the reported zero-result journey produced.
    """

    def __init__(self) -> None:
        super().__init__(
            (
                MediaCandidate("tmdb", "901", MediaType.MOVIE, "Probe", year=2024),
                MediaCandidate("tmdb", "902", MediaType.MOVIE, "Probe", year=None),
            ),
            # The TV journeys parse one season/episode, so the Provider must
            # ground that season or the analysis reports a metadata mismatch.
            episodes=(1, 2),
        )
        self.searches: list[tuple[str, str, int | None]] = []
        self.identity_lookups: list[str] = []

    def _for_year(self, media_type: MediaType, year: int | None):
        if year == 2024:
            return (MediaCandidate("tmdb", "901", media_type, "Probe", year=2024),)
        if year is None:
            return (MediaCandidate("tmdb", "902", media_type, "Probe", year=None),)
        return ()

    def _record(self, media_type: str, query: object) -> int | None:
        year = getattr(query, "year", None)
        self.searches.append((media_type, str(getattr(query, "title_candidate", query)), year))
        self.calls += 1
        return year

    def search_movie(self, query, policy=None, **kwargs):
        return self._for_year(MediaType.MOVIE, self._record("movie", query))

    def search_tv(self, query, policy=None, **kwargs):
        return self._for_year(MediaType.TV, self._record("tv", query))

    def get_movie(self, provider_id, policy=None, **kwargs):
        self.identity_lookups.append(provider_id)
        return super().get_movie(provider_id, policy, **kwargs)

    def get_tv(self, provider_id, policy=None, **kwargs):
        self.identity_lookups.append(provider_id)
        return super().get_tv(provider_id, policy, **kwargs)


class ReopeningProvider(RecordingYearProvider):
    """The same year-sensitive provider, with a real unknown TV identity."""

    def get_tv(self, provider_id, policy=None, **kwargs):
        self.identity_lookups.append(provider_id)
        if provider_id == "bad":
            raise MetadataError(MetadataErrorCode.NOT_FOUND, "identity not found")
        return super().get_tv(provider_id, policy, **kwargs)


class CandidateMismatchProvider(SyntheticMetadataProvider):
    """Two same-title/year candidates whose seasons only one can satisfy."""

    def __init__(self) -> None:
        super().__init__(
            (
                MediaCandidate("tmdb", "2019", MediaType.TV, "Probe", year=2025),
                MediaCandidate("tmdb", "wrong", MediaType.TV, "Probe", year=2025),
            ),
            episodes=(1, 2),
        )
        self.season_calls = []

    def get_season(self, provider_id, season, policy=None, **kwargs):
        self.calls += 1
        self.season_calls.append((provider_id, season))
        if provider_id == "wrong":
            raise MetadataError(MetadataErrorCode.NOT_FOUND, "season not found")
        return super().get_season(provider_id, season, policy, **kwargs)


class SeasonAwareTheBoysProvider(SyntheticMetadataProvider):
    """Two same-title works: only the 2019 identity owns S04E01-E08."""

    def __init__(self) -> None:
        super().__init__(
            (
                MediaCandidate("tmdb", "2024", MediaType.TV, "黑袍纠察队", year=2024),
                MediaCandidate("tmdb", "2019", MediaType.TV, "黑袍纠察队", year=2019),
            )
        )
        self.search_years = []
        self.season_calls = []

    def search_tv(self, query, policy=None, **kwargs):
        self.calls += 1
        self.search_years.append(query.year)
        if query.title_candidate != "黑袍纠察队":
            return ()
        return self._candidates

    def get_season(self, provider_id, season, policy=None, **kwargs):
        self.calls += 1
        self.season_calls.append((provider_id, season))
        if provider_id == "2024":
            raise MetadataError(MetadataErrorCode.NOT_FOUND, "season not found")
        if provider_id == "2019" and season == 4:
            return MediaIdentity(
                "tmdb",
                provider_id,
                MediaType.TV,
                "黑袍纠察队",
                season=season,
                episode_metadata=tuple(
                    EpisodeIdentity(number, f"Episode {number}") for number in range(1, 9)
                ),
            )
        return super().get_season(provider_id, season, policy, **kwargs)


class MetadataSearchYearTests(unittest.TestCase):
    """The real recovery search journey over one temporary managed runtime."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.clock = _Clock()
        self.environment = patch.dict(
            os.environ,
            {"TMDB_ACCESS_TOKEN": "sentinel-tmdb"},
            clear=False,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def _write_media(self, value, filename: str) -> Path:
        path = value.source_root / filename
        path.write_bytes(b"m" * 512)
        stamp = (self.clock.now - timedelta(hours=1)).timestamp()
        utime(path, (stamp, stamp))
        return path

    def _admit(self, value, *, limit: int) -> None:
        """Admit one organizing Task through the current scheduling kernel.

        The general CLI that used to admit and drive a direct organize run is
        retired; the same admitted Task is now driven by the resident Worker
        passes below, which is the production path every organizing entrance
        (Files, Automation, Run once) shares.
        """

        from tests.task_engine_test_helpers import admit_organize_task

        admit_organize_task(
            value.repository,
            snapshot_id=value.revision.revision_id,
            snapshot_digest=value.revision.digest,
            limit=limit,
        )

    def _resident_pass(self, value, *, prefix: str):
        from mediaflow.application.manual_organize_execution import (
            ManualOrganizeExecutionService,
        )
        from mediaflow.application.manual_task_engine import ManualTaskEngineWorker
        from mediaflow.application.task_scheduling import TaskSchedulingService
        from mediaflow.infrastructure.local_storage import LocalStorage
        from mediaflow.resident_entry import _automatic_task_runner

        scheduling = TaskSchedulingService(value.repository, capacity=100)
        runner = _automatic_task_runner(value.repository, str(value.config), scheduling)
        execution = ManualOrganizeExecutionService(
            value.repository,
            value.previews,
            value.intents,
            configuration=value.runtime,
            storages={
                "source": LocalStorage("source", value.source_root),
                "target": LocalStorage("target", value.target_root),
            },
            clock=value.clock,
        )
        worker_id = f"{prefix}-{len(value.repository.list_tasks())}"
        value.repository.register_worker(
            worker_id,
            worker_id,
            5.0,
            ("organize",),
            None,
            None,
            SCHEMA_VERSION,
            value.clock.now,
        )
        worker = ManualTaskEngineWorker(
            value.repository,
            scheduling,
            None,
            execution,
            worker_id=worker_id,
            clock=value.clock,
            automatic_runner=runner,
        )
        with patch(
            "mediaflow.resident_entry.metadata_provider_registry_from_environment",
            return_value=value.provider_registry,
        ):
            settled = worker.run_next()
        value.repository.stop_worker(worker_id, value.clock.now)
        return settled

    @contextmanager
    def correction_journey(self, provider: RecordingYearProvider, *, tv: bool):
        media = TV_MEDIA if tv else MOVIE_MEDIA
        with entrance_journey(
            self,
            recognition_rules=[TV_RULE] if tv else None,
            movie_rule=not tv,
            provider_registry=MetadataProviderRegistry((provider,)),
            viewer_token=VIEWER_TOKEN,
        ) as value:
            self._write_media(value, media)
            self._admit(value, limit=5)
            (task,) = value.repository.list_tasks()
            # The first Worker pass runs the admitted analysis and publishes
            # the Task's items; a settled item is then read back durably.
            self._resident_pass(value, prefix="metadata-search")
            (item,) = value.repository.list_items(task.task_id)
            for _ in range(8):
                if item.status.value == "waiting_metadata_correction":
                    break
                self._resident_pass(value, prefix="metadata-search")
                item = value.repository.get_item(item.item_id) or item
            self.assertEqual(
                "waiting_metadata_correction",
                item.status.value,
                "the journey must reach the real Metadata correction blocker",
            )
            review = value.repository.get_metadata_correction_for_item(item.item_id)
            self.assertIsNotNone(review)
            self.assertEqual(2025, review.original_year)
            yield value

    def request(
        self,
        value,
        method: str,
        path: str,
        body: object | None = None,
        *,
        token: str = ADMIN_TOKEN,
    ):
        payload = b"" if body is None else json.dumps(body).encode("utf-8")
        statuses: list[str] = []
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": "",
            "CONTENT_LENGTH": str(len(payload)),
            "wsgi.input": io.BytesIO(payload),
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_HOST": "127.0.0.1",
            "HTTP_ORIGIN": "http://127.0.0.1",
        }
        session = getattr(value.api, "_fixture_session_cookies", {}).get(token)
        if session is not None:
            environ["HTTP_COOKIE"] = session
        else:
            environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        result = b"".join(value.api(environ, lambda status, _h: statuses.append(status)))
        return int(statuses[0].split()[0]), (json.loads(result) if result else {})

    def _checkpoint_version(self, value, task_id: str, item_id: str) -> str:
        status, detail = self.request(
            value, "GET", f"/api/tasks/{task_id}/items/{item_id}/recovery"
        )
        self.assertEqual(200, status, detail)
        self.assertEqual("metadata_correction", detail["decision"]["kind"], detail)
        return detail["checkpoint"]["checkpoint_version"]

    def _search(self, value, task_id: str, item_id: str, body: dict, *, token: str = ADMIN_TOKEN):
        return self.request(
            value,
            "POST",
            f"/api/tasks/{task_id}/items/{item_id}/recovery/metadata-search",
            body,
            token=token,
        )

    def _durable_counts(self, value, task_id: str, item_id: str):
        item = value.repository.get_item(item_id)
        review = value.repository.get_metadata_correction_for_item(item_id)
        return (
            item.status.value,
            review.status.value if review else None,
            len(value.repository.list_results(task_id)),
        )

    def test_changed_year_search_sends_that_exact_year_to_the_provider(self):
        provider = RecordingYearProvider()
        with self.correction_journey(provider, tv=True) as value:
            task_id, item_id, review_id = self._ids(value)
            version = self._checkpoint_version(value, task_id, item_id)
            before = self._durable_counts(value, task_id, item_id)

            status, document = self._search(
                value,
                task_id,
                item_id,
                {
                    "expectedCheckpointVersion": version,
                    "query": "Probe",
                    "mediaType": "tv",
                    "year": 2024,
                },
            )

            self.assertEqual(200, status, document)
            # The first call is the journey's own real analysis (original year
            # 2025); the explicit search forwarded the edited year 2024.
            self.assertEqual(
                [("tv", "Probe", 2025), ("tv", "Probe", 2024)],
                provider.searches,
            )
            self.assertEqual(
                [
                    {
                        "rank": 1,
                        "provider_id": "901",
                        "media_type": "tv",
                        "title": "Probe",
                        "year": 2024,
                    }
                ],
                [
                    {
                        key: value[key]
                        for key in ("rank", "provider_id", "media_type", "title", "year")
                    }
                    for value in document["candidates"]
                ],
            )
            self.assertEqual("none", document["sideEffects"])
            # A search saves no decision and creates no durable work.
            self.assertEqual(before, self._durable_counts(value, task_id, item_id))
            review_after = value.repository.get_metadata_correction(review_id)
            self.assertEqual("pending", review_after.status.value)

    def test_cleared_year_searches_without_a_year_and_never_falls_back(self):
        provider = RecordingYearProvider()
        with self.correction_journey(provider, tv=False) as value:
            task_id, item_id, _review_id = self._ids(value)
            version = self._checkpoint_version(value, task_id, item_id)

            status, document = self._search(
                value,
                task_id,
                item_id,
                {
                    "expectedCheckpointVersion": version,
                    "query": "Probe",
                    "mediaType": "movie",
                    "year": None,
                },
            )

            self.assertEqual(200, status, document)
            # The explicit null reaches the Provider as None: the original
            # year 2025 would have returned zero candidates instead.
            self.assertEqual(
                [("movie", "Probe", 2025), ("movie", "Probe", None)],
                provider.searches,
            )
            self.assertEqual(["902"], [value["provider_id"] for value in document["candidates"]])
            self.assertIsNone(document["candidates"][0]["year"])

    def test_legacy_body_without_year_keeps_the_original_year_semantics(self):
        provider = RecordingYearProvider()
        with self.correction_journey(provider, tv=True) as value:
            task_id, item_id, _review_id = self._ids(value)
            version = self._checkpoint_version(value, task_id, item_id)

            status, document = self._search(
                value,
                task_id,
                item_id,
                {
                    "expectedCheckpointVersion": version,
                    "query": "Probe",
                    "mediaType": "tv",
                },
            )

            self.assertEqual(200, status, document)
            # The legacy omission keeps the historical behavior: the parsed
            # original year 2025 governs both the initial analysis and the
            # explicit search.
            self.assertEqual(
                [("tv", "Probe", 2025), ("tv", "Probe", 2025)],
                provider.searches,
            )
            self.assertEqual([], document["candidates"])

    def test_invalid_year_parameters_are_refused_before_any_provider_call(self):
        provider = RecordingYearProvider()
        with self.correction_journey(provider, tv=True) as value:
            task_id, item_id, review_id = self._ids(value)
            version = self._checkpoint_version(value, task_id, item_id)
            before = self._durable_counts(value, task_id, item_id)
            calls_before = len(provider.searches)
            invalid_years = ["2024", True, False, 2024.5, 1869, 2101]

            for invalid in invalid_years:
                status, error = self._search(
                    value,
                    task_id,
                    item_id,
                    {
                        "expectedCheckpointVersion": version,
                        "query": "Probe",
                        "mediaType": "tv",
                        "year": invalid,
                    },
                )
                self.assertEqual(400, status, (invalid, error))
                self.assertEqual("invalid_year", error["error"]["code"], (invalid, error))
                self.assertIn("nextAction", error["error"]["details"], error)

            status, error = self._search(
                value,
                task_id,
                item_id,
                {
                    "expectedCheckpointVersion": version,
                    "query": "Probe",
                    "mediaType": "tv",
                    "year": 2024,
                    "unexpected": True,
                },
            )
            self.assertEqual(400, status, error)
            self.assertEqual("invalid_request", error["error"]["code"], error)

            # No refusal reached the Provider or changed durable state.
            self.assertEqual(calls_before, len(provider.searches))
            self.assertEqual(before, self._durable_counts(value, task_id, item_id))
            self.assertEqual(
                "pending", value.repository.get_metadata_correction(review_id).status.value
            )

    def test_search_is_side_effect_free_and_bound_to_the_current_checkpoint(self):
        provider = RecordingYearProvider()
        with self.correction_journey(provider, tv=True) as value:
            task_id, item_id, review_id = self._ids(value)
            version = self._checkpoint_version(value, task_id, item_id)
            before = self._durable_counts(value, task_id, item_id)
            calls_before = len(provider.searches)

            for _ in range(2):
                status, _document = self._search(
                    value,
                    task_id,
                    item_id,
                    {
                        "expectedCheckpointVersion": version,
                        "query": "Probe",
                        "mediaType": "tv",
                        "year": 2024,
                    },
                )
                self.assertEqual(200, status)

            status, stale = self._search(
                value,
                task_id,
                item_id,
                {
                    "expectedCheckpointVersion": "f" * 64,
                    "query": "Probe",
                    "mediaType": "tv",
                    "year": 2024,
                },
            )
            self.assertEqual(409, status, stale)
            self.assertEqual("stale_checkpoint", stale["error"]["code"], stale)

            status, refused = self._search(
                value,
                task_id,
                item_id,
                {
                    "expectedCheckpointVersion": version,
                    "query": "Probe",
                    "mediaType": "movie",
                    "year": 2024,
                },
            )
            self.assertEqual(409, status, refused)
            self.assertEqual("media_type_not_permitted", refused["error"]["code"], refused)

            status, denied = self._search(
                value,
                task_id,
                item_id,
                {
                    "expectedCheckpointVersion": version,
                    "query": "Probe",
                    "mediaType": "tv",
                    "year": 2024,
                },
                token=VIEWER_TOKEN,
            )
            self.assertEqual(403, status, denied)
            # Only the two successful searches reached the Provider; the stale,
            # refused-type and permission-denied requests never did.
            self.assertEqual(calls_before + 2, len(provider.searches))
            self.assertEqual(before, self._durable_counts(value, task_id, item_id))
            self.assertEqual(
                "pending", value.repository.get_metadata_correction(review_id).status.value
            )

    def test_saved_candidate_analyzes_with_the_same_search_conditions(self):
        provider = RecordingYearProvider()
        with self.correction_journey(provider, tv=True) as value:
            task_id, item_id, _review_id = self._ids(value)
            version = self._checkpoint_version(value, task_id, item_id)
            status, document = self._search(
                value,
                task_id,
                item_id,
                {
                    "expectedCheckpointVersion": version,
                    "query": "Probe",
                    "mediaType": "tv",
                    "year": 2024,
                },
            )
            self.assertEqual(200, status, document)
            searches_after_search = list(provider.searches)

            status, decided = self.request(
                value,
                "POST",
                f"/api/tasks/{task_id}/items/{item_id}/recovery/decision",
                {
                    "kind": "metadata_correction",
                    "expectedCheckpointVersion": version,
                    "query": "Probe",
                    "year": 2024,
                    "mediaType": "tv",
                    "providerId": "901",
                },
            )
            self.assertEqual(200, status, decided)
            status, continued = self.request(
                value,
                "POST",
                f"/api/tasks/{task_id}/items/{item_id}/recovery/continue",
                {
                    "expectedCheckpointVersion": decided["checkpoint"]["checkpoint_version"],
                },
            )
            self.assertEqual(202, status, continued)

            settled = self._resident_pass(value, prefix="candidate-analysis")
            self.assertIsNotNone(settled)
            item = value.repository.get_item(item_id)
            self.assertEqual("waiting_confirm", item.status.value, item)
            # The saved correction analyzed by the exact provider identity the
            # operator selected from the same year's candidates.
            self.assertEqual(["901"], provider.identity_lookups)
            self.assertEqual(searches_after_search, provider.searches)
            self.assertTrue((value.source_root / TV_MEDIA).exists())

    def test_saved_query_without_a_candidate_reanalyzes_with_the_same_year(self):
        provider = RecordingYearProvider()
        with self.correction_journey(provider, tv=True) as value:
            task_id, item_id, _review_id = self._ids(value)
            version = self._checkpoint_version(value, task_id, item_id)
            status, decided = self.request(
                value,
                "POST",
                f"/api/tasks/{task_id}/items/{item_id}/recovery/decision",
                {
                    "kind": "metadata_correction",
                    "expectedCheckpointVersion": version,
                    "query": "Probe",
                    "year": 2024,
                    "mediaType": "tv",
                },
            )
            self.assertEqual(200, status, decided)
            status, continued = self.request(
                value,
                "POST",
                f"/api/tasks/{task_id}/items/{item_id}/recovery/continue",
                {
                    "expectedCheckpointVersion": decided["checkpoint"]["checkpoint_version"],
                },
            )
            self.assertEqual(202, status, continued)

            settled = self._resident_pass(value, prefix="query-analysis")
            self.assertIsNotNone(settled)
            item = value.repository.get_item(item_id)
            self.assertEqual("waiting_confirm", item.status.value, item)
            # Without a selected candidate the analysis searched with the same
            # corrected year and matched the candidate that year returns. The
            # matched TV identity is enriched through the same Provider.
            self.assertEqual(
                [("tv", "Probe", 2025), ("tv", "Probe", 2024)],
                provider.searches,
            )
            self.assertEqual(["901"], provider.identity_lookups)
            self.assertTrue((value.source_root / TV_MEDIA).exists())

    def test_s04_batch_uses_the_season_verified_work_and_keeps_a_mixed_correction_sibling(self):
        provider = SeasonAwareTheBoysProvider()
        with entrance_journey(
            self,
            recognition_rules=[TV_RULE],
            provider_registry=MetadataProviderRegistry((provider,)),
            viewer_token=VIEWER_TOKEN,
        ) as value:
            for number in range(1, 9):
                self._write_media(value, f"黑袍纠察队.2024.S04E{number:02d}.mkv")
            self._write_media(value, "未知剧.2024.S04E01.mkv")
            self._admit(value, limit=20)
            (task,) = value.repository.list_tasks()
            self._resident_pass(value, prefix="the-boys-s04")
            items = value.repository.list_items(task.task_id)
            for _ in range(20):
                settled = {
                    "waiting_confirm",
                    "waiting_metadata_correction",
                    "failed",
                }
                if all(item.status.value in settled for item in items):
                    break
                self._resident_pass(value, prefix="the-boys-s04")
                items = value.repository.list_items(task.task_id)
            self.assertEqual(len(items), 9)
            by_title = {}
            for item in items:
                evidence = value.repository.list_evidence_for_item(item.item_id, limit=4)
                metadata = next(
                    (
                        section.value
                        for record in evidence
                        if (section := record.section("metadata")).available
                        and section.value is not None
                    ),
                    {},
                )
                by_title[item.source_path] = (item, metadata)
            for number in range(1, 9):
                name = f"黑袍纠察队.2024.S04E{number:02d}.mkv"
                item, metadata = by_title[name]
                self.assertEqual("success", item.status.value, (name, item))
                self.assertIn(f"S04E{number:02d}", str(item.destination_path), item)
                self.assertEqual("2019", metadata.get("providerId"), (name, metadata))
                self.assertEqual(4, metadata.get("season"), (name, metadata))
                self.assertEqual([number], metadata.get("episodes"), (name, metadata))
                self.assertIn(
                    f"Season 4 episodes {number} verified",
                    " ".join(metadata.get("matchReasons") or ()),
                    (name, metadata),
                )
            unknown, unknown_metadata = by_title["未知剧.2024.S04E01.mkv"]
            self.assertEqual("waiting_metadata_correction", unknown.status.value)
            status, detail = self.request(
                value,
                "GET",
                f"/api/tasks/{task.task_id}/items/{unknown.item_id}/recovery",
            )
            self.assertEqual(200, status, detail)
            self.assertEqual("metadata_correction", detail["decision"]["kind"])
            self.assertIn("No compatible candidates", detail["decision"]["reason"])
            self.assertEqual(unknown.item_id, detail["item_id"])
            self.assertEqual([None] * 9, provider.search_years)
            self.assertEqual(
                8,
                len([path for path in value.target_root.rglob("*.mkv") if path.is_file()]),
            )
            self.assertFalse(
                any(
                    "未知剧" in path.name for path in value.target_root.rglob("*") if path.is_file()
                )
            )

    def test_wrong_saved_tv_identity_reopens_the_same_editable_decision(self):
        provider = ReopeningProvider()
        with self.correction_journey(provider, tv=True) as value:
            task_id, item_id, review_id = self._ids(value)
            version = self._checkpoint_version(value, task_id, item_id)
            status, decided = self.request(
                value,
                "POST",
                f"/api/tasks/{task_id}/items/{item_id}/recovery/decision",
                {
                    "kind": "metadata_correction",
                    "expectedCheckpointVersion": version,
                    "query": "Probe",
                    "year": 2025,
                    "mediaType": "tv",
                    "providerId": "bad",
                },
            )
            self.assertEqual(200, status, decided)
            status, continued = self.request(
                value,
                "POST",
                f"/api/tasks/{task_id}/items/{item_id}/recovery/continue",
                {
                    "expectedCheckpointVersion": decided["checkpoint"]["checkpoint_version"],
                },
            )
            self.assertEqual(202, status, continued)
            self.assertIsNotNone(self._resident_pass(value, prefix="bad-identity"))
            item = value.repository.get_item(item_id)
            self.assertEqual("waiting_metadata_correction", item.status.value, item)
            reopened = value.repository.get_metadata_correction(review_id)
            self.assertEqual("pending", reopened.status.value)
            self.assertEqual(1, len(value.repository.list_metadata_correction_audit(review_id)))

            status, detail = self.request(
                value,
                "GET",
                f"/api/tasks/{task_id}/items/{item_id}/recovery",
            )
            self.assertEqual(200, status, detail)
            self.assertEqual("metadata_correction", detail["decision"]["kind"])
            self.assertEqual(review_id, detail["decision"]["review_id"])
            self.assertIn("was not found", detail["decision"]["reason"])
            self.assertEqual("Probe", detail["decision"]["query"])
            self.assertEqual(1, len(value.repository.list_metadata_correction_audit(review_id)))

            status, corrected = self.request(
                value,
                "POST",
                f"/api/tasks/{task_id}/items/{item_id}/recovery/decision",
                {
                    "kind": "metadata_correction",
                    "expectedCheckpointVersion": detail["checkpoint"]["checkpoint_version"],
                    "query": "Probe",
                    "year": 2024,
                    "mediaType": "tv",
                    "providerId": "901",
                },
            )
            self.assertEqual(200, status, corrected)
            status, continued = self.request(
                value,
                "POST",
                f"/api/tasks/{task_id}/items/{item_id}/recovery/continue",
                {
                    "expectedCheckpointVersion": corrected["checkpoint"]["checkpoint_version"],
                },
            )
            self.assertEqual(202, status, continued)
            self.assertIsNotNone(self._resident_pass(value, prefix="corrected-identity"))
            item = value.repository.get_item(item_id)
            self.assertEqual("waiting_confirm", item.status.value, item)
            self.assertEqual(2, len(value.repository.list_metadata_correction_audit(review_id)))
            self.assertTrue((value.source_root / TV_MEDIA).exists())
            self.assertFalse(any(path.is_file() for path in value.target_root.rglob("*")))

    def test_failed_candidate_selection_then_correction_uses_only_the_newest_decision(self):
        provider = CandidateMismatchProvider()
        with entrance_journey(
            self,
            recognition_rules=[TV_RULE],
            provider_registry=MetadataProviderRegistry((provider,)),
            viewer_token=VIEWER_TOKEN,
        ) as value:
            self._write_media(value, TV_MEDIA)
            self._admit(value, limit=5)
            (task,) = value.repository.list_tasks()
            # The first Worker pass runs the admitted analysis and publishes
            # the Task's items; a settled item is then read back durably.
            self._resident_pass(value, prefix="metadata-search")
            (item,) = value.repository.list_items(task.task_id)
            for _ in range(8):
                if item.status.value in {
                    "waiting_metadata",
                    "waiting_metadata_correction",
                    "waiting_confirm",
                }:
                    break
                self._resident_pass(value, prefix="candidate-start")
                item = value.repository.get_item(item.item_id)
            self.assertEqual("waiting_metadata", item.status.value, item)

            status, detail = self.request(
                value,
                "GET",
                f"/api/tasks/{task.task_id}/items/{item.item_id}/recovery",
            )
            self.assertEqual(200, status, detail)
            self.assertEqual("metadata", detail["decision"]["kind"])
            wrong = next(
                choice
                for choice in detail["decision"]["candidates"]
                if choice["provider_id"] == "wrong"
            )
            status, decided = self.request(
                value,
                "POST",
                f"/api/tasks/{task.task_id}/items/{item.item_id}/recovery/decision",
                {
                    "kind": "metadata",
                    "expectedCheckpointVersion": detail["checkpoint"]["checkpoint_version"],
                    "candidateRank": wrong["rank"],
                },
            )
            self.assertEqual(200, status, decided)
            status, continued = self.request(
                value,
                "POST",
                f"/api/tasks/{task.task_id}/items/{item.item_id}/recovery/continue",
                {
                    "expectedCheckpointVersion": decided["checkpoint"]["checkpoint_version"],
                },
            )
            self.assertEqual(202, status, continued)
            self.assertIsNotNone(self._resident_pass(value, prefix="candidate-wrong"))
            item = value.repository.get_item(item.item_id)
            self.assertEqual("waiting_metadata_correction", item.status.value, item)

            status, correction = self.request(
                value,
                "GET",
                f"/api/tasks/{task.task_id}/items/{item.item_id}/recovery",
            )
            self.assertEqual(200, status, correction)
            self.assertEqual("metadata_correction", correction["decision"]["kind"])
            self.assertIn("Season 1", correction["decision"]["reason"])
            status, decided = self.request(
                value,
                "POST",
                f"/api/tasks/{task.task_id}/items/{item.item_id}/recovery/decision",
                {
                    "kind": "metadata_correction",
                    "expectedCheckpointVersion": correction["checkpoint"]["checkpoint_version"],
                    "query": "Probe",
                    "year": 2025,
                    "mediaType": "tv",
                    "providerId": "2019",
                },
            )
            self.assertEqual(200, status, decided)
            status, continued = self.request(
                value,
                "POST",
                f"/api/tasks/{task.task_id}/items/{item.item_id}/recovery/continue",
                {
                    "expectedCheckpointVersion": decided["checkpoint"]["checkpoint_version"],
                },
            )
            self.assertEqual(202, status, continued)
            self.assertIsNotNone(self._resident_pass(value, prefix="newest-decision"))
            item = value.repository.get_item(item.item_id)
            self.assertEqual("waiting_confirm", item.status.value, item)
            self.assertTrue((value.source_root / TV_MEDIA).exists())
            self.assertFalse(any(path.is_file() for path in value.target_root.rglob("*")))

    def test_reopened_candidate_review_replaces_candidates_and_keeps_decision_audit(self):
        provider = CandidateMismatchProvider()
        with entrance_journey(
            self,
            recognition_rules=[TV_RULE],
            provider_registry=MetadataProviderRegistry((provider,)),
            viewer_token=VIEWER_TOKEN,
            max_provider_requests=2,
        ) as value:
            self._write_media(value, TV_MEDIA)
            self._admit(value, limit=5)
            (task,) = value.repository.list_tasks()
            # The first Worker pass runs the admitted analysis and publishes
            # the Task's items; a settled item is then read back durably.
            self._resident_pass(value, prefix="metadata-search")
            (item,) = value.repository.list_items(task.task_id)
            for _ in range(8):
                if item.status.value == "waiting_metadata":
                    break
                self._resident_pass(value, prefix="candidate-reopen")
                item = value.repository.get_item(item.item_id)
            self.assertEqual("waiting_metadata", item.status.value, item)
            first_review = value.repository.get_metadata_review_for_item(item.item_id)
            self.assertIsNotNone(first_review)

            status, detail = self.request(
                value,
                "GET",
                f"/api/tasks/{task.task_id}/items/{item.item_id}/recovery",
            )
            self.assertEqual(200, status, detail)
            self.assertEqual("metadata", detail["decision"]["kind"])
            first_candidate_version = detail["checkpoint"]["checkpoint_version"]
            wrong = next(
                choice
                for choice in detail["decision"]["candidates"]
                if choice["provider_id"] == "wrong"
            )
            status, decided = self.request(
                value,
                "POST",
                f"/api/tasks/{task.task_id}/items/{item.item_id}/recovery/decision",
                {
                    "kind": "metadata",
                    "expectedCheckpointVersion": detail["checkpoint"]["checkpoint_version"],
                    "candidateRank": wrong["rank"],
                },
            )
            self.assertEqual(200, status, decided)
            status, continued = self.request(
                value,
                "POST",
                f"/api/tasks/{task.task_id}/items/{item.item_id}/recovery/continue",
                {
                    "expectedCheckpointVersion": decided["checkpoint"]["checkpoint_version"],
                },
            )
            self.assertEqual(202, status, continued)
            self.assertIsNotNone(self._resident_pass(value, prefix="candidate-wrong"))
            item = value.repository.get_item(item.item_id)
            self.assertEqual("waiting_metadata_correction", item.status.value, item)

            status, correction = self.request(
                value,
                "GET",
                f"/api/tasks/{task.task_id}/items/{item.item_id}/recovery",
            )
            self.assertEqual(200, status, correction)
            self.assertEqual("metadata_correction", correction["decision"]["kind"])
            # Save only a corrected query; the Provider still returns the same
            # two comparable works, so the item must return to candidate review.
            status, decided = self.request(
                value,
                "POST",
                f"/api/tasks/{task.task_id}/items/{item.item_id}/recovery/decision",
                {
                    "kind": "metadata_correction",
                    "expectedCheckpointVersion": correction["checkpoint"]["checkpoint_version"],
                    "query": "Probe",
                    "year": 2025,
                    "mediaType": "tv",
                },
            )
            self.assertEqual(200, status, decided)
            status, continued = self.request(
                value,
                "POST",
                f"/api/tasks/{task.task_id}/items/{item.item_id}/recovery/continue",
                {
                    "expectedCheckpointVersion": decided["checkpoint"]["checkpoint_version"],
                },
            )
            self.assertEqual(202, status, continued)
            self.assertIsNotNone(self._resident_pass(value, prefix="candidate-reopen-again"))
            item = value.repository.get_item(item.item_id)
            self.assertEqual("waiting_metadata", item.status.value, item)

            reopened = value.repository.get_metadata_review_for_item(item.item_id)
            self.assertEqual(first_review.review_id, reopened.review_id)
            self.assertEqual("pending", reopened.status.value)
            self.assertEqual(
                1, len(value.repository.list_metadata_review_audit(reopened.review_id))
            )
            status, reopened_detail = self.request(
                value,
                "GET",
                f"/api/tasks/{task.task_id}/items/{item.item_id}/recovery",
            )
            self.assertEqual(200, status, reopened_detail)
            self.assertEqual("metadata", reopened_detail["decision"]["kind"])
            self.assertEqual(first_review.review_id, reopened_detail["decision"]["review_id"])
            self.assertEqual(2, len(reopened_detail["decision"]["candidates"]))

            # The pre-reopen candidate checkpoint fence cannot select a
            # candidate in the reopened snapshot.
            status, stale = self.request(
                value,
                "POST",
                f"/api/tasks/{task.task_id}/items/{item.item_id}/recovery/decision",
                {
                    "kind": "metadata",
                    "expectedCheckpointVersion": first_candidate_version,
                    "candidateRank": wrong["rank"],
                },
            )
            self.assertEqual(409, status, stale)
            self.assertEqual("stale_checkpoint", stale["error"]["code"], stale)

            correct = next(
                choice
                for choice in reopened_detail["decision"]["candidates"]
                if choice["provider_id"] == "2019"
            )
            status, decided = self.request(
                value,
                "POST",
                f"/api/tasks/{task.task_id}/items/{item.item_id}/recovery/decision",
                {
                    "kind": "metadata",
                    "expectedCheckpointVersion": reopened_detail["checkpoint"][
                        "checkpoint_version"
                    ],
                    "candidateRank": correct["rank"],
                },
            )
            self.assertEqual(200, status, decided)
            status, continued = self.request(
                value,
                "POST",
                f"/api/tasks/{task.task_id}/items/{item.item_id}/recovery/continue",
                {
                    "expectedCheckpointVersion": decided["checkpoint"]["checkpoint_version"],
                },
            )
            self.assertEqual(202, status, continued)
            self.assertIsNotNone(self._resident_pass(value, prefix="candidate-correct"))
            item = value.repository.get_item(item.item_id)
            self.assertEqual("waiting_confirm", item.status.value, item)
            resolved = value.repository.get_metadata_review(reopened.review_id)
            self.assertEqual("resolved", resolved.status.value)
            self.assertEqual(
                2, len(value.repository.list_metadata_review_audit(reopened.review_id))
            )
            self.assertTrue((value.source_root / TV_MEDIA).exists())
            self.assertFalse(any(path.is_file() for path in value.target_root.rglob("*")))

    def _ids(self, value):
        (task,) = value.repository.list_tasks()
        (item,) = value.repository.list_items(task.task_id)
        review = value.repository.get_metadata_correction_for_item(item.item_id)
        return task.task_id, item.item_id, review.review_id


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
