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
from mediaflow.domain.metadata import MediaCandidate, MediaType
from mediaflow.final_cli import final_main
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


class MetadataSearchYearTests(unittest.TestCase):
    """The real recovery search journey over one temporary managed runtime."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.clock = _Clock()
        self.environment = patch.dict(
            os.environ,
            {"TMDB_ACCESS_TOKEN": "sentinel-tmdb", "MEDIAFLOW_API_TOKEN": ADMIN_TOKEN},
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

    def _run_cli(self, value, *arguments: str) -> None:
        output, errors = io.StringIO(), io.StringIO()
        with patch(
            "mediaflow.final_cli.metadata_provider_registry_from_environment",
            return_value=value.provider_registry,
        ):
            code = final_main(
                ["--config", str(value.config), *arguments],
                stdout=output,
                stderr=errors,
            )
        self.assertEqual(0, code, errors.getvalue())

    def _resident_pass(self, value, *, prefix: str):
        from mediaflow.application.manual_organize_execution import (
            ManualOrganizeExecutionService,
        )
        from mediaflow.application.manual_task_engine import ManualTaskEngineWorker
        from mediaflow.application.task_scheduling import TaskSchedulingService
        from mediaflow.final_cli import _automatic_task_runner
        from mediaflow.infrastructure.local_storage import LocalStorage

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
            "mediaflow.final_cli.metadata_provider_registry_from_environment",
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
            self._run_cli(value, "organize", "--execute", "--limit", "5")
            (task,) = value.repository.list_tasks()
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
            "HTTP_AUTHORIZATION": f"Bearer {token}",
        }
        result = b"".join(value.api(environ, lambda status, _h: statuses.append(status)))
        return int(statuses[0].split()[0]), (json.loads(result) if result else {})

    def _checkpoint_version(self, value, task_id: str, item_id: str) -> str:
        status, detail = self.request(
            value, "GET", f"/api/v1/tasks/{task_id}/items/{item_id}/recovery"
        )
        self.assertEqual(200, status, detail)
        self.assertEqual("metadata_correction", detail["decision"]["kind"], detail)
        return detail["checkpoint"]["checkpoint_version"]

    def _search(self, value, task_id: str, item_id: str, body: dict, *, token: str = ADMIN_TOKEN):
        return self.request(
            value,
            "POST",
            f"/api/v1/tasks/{task_id}/items/{item_id}/recovery/metadata-search",
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
            len(value.repository.list_recovery_continuations(item_id, limit=10)),
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
                f"/api/v1/tasks/{task_id}/items/{item_id}/recovery/decision",
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
                f"/api/v1/tasks/{task_id}/items/{item_id}/recovery/continue",
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
                f"/api/v1/tasks/{task_id}/items/{item_id}/recovery/decision",
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
                f"/api/v1/tasks/{task_id}/items/{item_id}/recovery/continue",
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

    def _ids(self, value):
        (task,) = value.repository.list_tasks()
        (item,) = value.repository.list_items(task.task_id)
        review = value.repository.get_metadata_correction_for_item(item.item_id)
        return task.task_id, item.item_id, review.review_id


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
