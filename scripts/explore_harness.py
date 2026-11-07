"""Explore real-Python browser harness (Task 51.1 / Slice 51).

One process serves the built V2 artifact (``/ui-v2/*`` through the real
``MediaFlowApi`` static layer) and the real ``/api/v1/explore/*`` boundary over
a temporary SQLite runtime database. The production ``TMDBAdapter`` stack
(``TMDBProvider`` over ``TMDBClient``/``HttpxTransport``) is driven with an
in-process ``httpx.MockTransport`` fake upstream: no real TMDB account,
credential, network egress, production configuration, user media, Storage
adapter or Task engine is involved, and the token value is a throwaway.

The journey must prove zero side effects:
- ``storage_adapters`` exposes one spy that records and refuses any call, so a
  single Storage touch during Explore reads becomes a visible failure;
- ``/__harness__/stats`` snapshots every durable table count except the
  permitted auth/history logs, so any Task, execution, review, discovery or
  configuration write would change the snapshot;
- ``/__harness__/stats`` also reports every fake-upstream request actually
  issued, which the browser spec asserts is non-zero while the external
  network is never used.

Failure journeys use the real provider failure families through
``POST /__harness__/failure``: ``upstream_auth`` makes every upstream read
answer 401 (provider authentication failure: the API principal must survive),
``search_500`` fails the search read with HTTP 500 before self-healing
(bounded first-load failure plus explicit retry) and ``genre_503`` fails only
the filter-catalog read so the options error/recovery entry can be exercised
next to an already-successful work list.

``/__harness__/stats`` additionally reports every ``vote_count.gte`` floor the
adapter actually sent (``voteFloors``), so a browser assertion can prove the
chosen minimum vote count really reached the fake upstream instead of only
appearing in the echoed query.
"""

from __future__ import annotations

import argparse
import json
import re
import socketserver
import sqlite3
import sys
import threading
from contextlib import closing
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mediaflow.application.metadata import MetadataProviderRegistry  # noqa: E402
from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal  # noqa: E402
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository  # noqa: E402
from mediaflow.infrastructure.tmdb import (  # noqa: E402
    TMDBClient,
    TMDBConfig,
    TMDBProvider,
)
from mediaflow.interfaces.service_api import MediaFlowApi  # noqa: E402
from mediaflow.interfaces.v2_ui import asset_root  # noqa: E402

HARNESS_TOKEN = "explore-harness-token"

PRINCIPAL = ResolvedApiPrincipal(
    "explore-harness",
    HARNESS_TOKEN,
    frozenset({ApiPermission.READ}),
)

GENRES = {
    "movie": [
        {"id": 28, "name": "动作"},
        {"id": 878, "name": "科幻"},
        {"id": 18, "name": "剧情"},
        {"id": 35, "name": "喜剧"},
        {"id": 10749, "name": "爱情"},
    ],
    "tv": [
        {"id": 10759, "name": "动作与冒险"},
        {"id": 16, "name": "动画"},
        {"id": 18, "name": "剧情"},
        {"id": 35, "name": "喜剧"},
        {"id": 10765, "name": "科幻与奇幻"},
    ],
}

LANGUAGES = [
    {"iso_639_1": "zh", "english_name": "Chinese", "name": "中文"},
    {"iso_639_1": "en", "english_name": "English", "name": "English"},
    {"iso_639_1": "ja", "english_name": "Japanese", "name": "日本語"},
    {"iso_639_1": "ko", "english_name": "Korean", "name": "한국어"},
    {"iso_639_1": "fr", "english_name": "French", "name": "Français"},
]

TITLE_STEMS = {
    "movie": [
        "深空回声",
        "城市边缘的光",
        "沉默的第十二个夏天",
        "在所有被命名的河流都干涸之前我们仍然记得那座灯塔",
        "午夜法庭",
        "纸飞机计划",
        "低语山谷",
        "第二次日落",
    ],
    "tv": [
        "北岸列车",
        "未完成的交响",
        "山海邮局",
        "漫长的一致",
        "午夜厨房",
        "昨日星球",
        "孤岛来信",
        "漫长的春天",
    ],
}

WORK_COUNTS = {"movie": 45, "tv": 30}
PAGE_SIZE = 20

_lock = threading.Lock()
_failure_mode = "none"
_search_failures_used = 0
_stats = {"tmdb_requests": 0, "routes": {}, "vote_floors": [], "list_pages": []}


def _works(media_type: str) -> list[dict[str, object]]:
    stems = TITLE_STEMS[media_type]
    genres = GENRES[media_type]
    works: list[dict[str, object]] = []
    for index in range(WORK_COUNTS[media_type]):
        cycle, position = divmod(index, len(stems))
        title = stems[position] if cycle == 0 else f"{stems[position]} 第 {cycle + 1} 部"
        unrated = index % 9 == 7
        year = 1995 + (index * 3) % 30
        works.append(
            {
                "id": 603_000 + index,
                "title": title,
                "original_title": f"Original {title}",
                "name": title,
                "original_name": f"Original {title}",
                "release_date": f"{year}-{(index % 9) + 1:02d}-{(index % 9) + 1:02d}",
                "first_air_date": f"{year}-{(index % 9) + 1:02d}-{(index % 9) + 1:02d}",
                "vote_average": None if unrated else round(5 + (index * 13) % 45 / 10, 1),
                "vote_count": 0 if unrated else 120 + index * 53,
                "genre_ids": [
                    genres[index % len(genres)]["id"],
                    genres[(index + 2) % len(genres)]["id"],
                ],
                "original_language": LANGUAGES[index % 3]["iso_639_1"],
                "poster_path": f"/harness-{media_type}-{index}.jpg",
                "backdrop_path": f"/harness-{media_type}-{index}-bg.jpg",
                "overview": (
                    f"《{title}》是探索假上游提供的作品简介,用于验证详情字段、"
                    "评分、图片引用与 TMDB 外链的真实读取链路。"
                ),
                "runtime": 90 + index % 60,
                "seasons": 1 + index % 6,
                "episodes": (1 + index % 6) * 12 + index % 5,
            }
        )
    return works


WORKS = {kind: _works(kind) for kind in ("movie", "tv")}


def _list_payload(media_type: str, params: dict[str, list[str]]) -> dict[str, object]:
    def one(name: str) -> str | None:
        values = params.get(name)
        return values[0] if values else None

    page = int(one("page") or "1")
    wanted_genres = one("with_genres")
    wanted_language = one("with_original_language")
    wanted_year = one("primary_release_year") or one("first_air_date_year")
    min_average = one("vote_average.gte")
    min_votes = one("vote_count.gte")
    query = one("query")
    sort_by = one("sort_by") or "popularity.desc"

    works = list(WORKS[media_type])
    if wanted_genres is not None:
        wanted = {int(value) for value in wanted_genres.split(",") if value}
        works = [
            work
            for work in works
            if wanted.issubset(set(work["genre_ids"]))  # type: ignore[arg-type]
        ]
    if wanted_language is not None:
        works = [work for work in works if work["original_language"] == wanted_language]
    if wanted_year is not None:
        works = [work for work in works if str(work["release_date"]).startswith(f"{wanted_year}-")]
    if min_average is not None:
        threshold = float(min_average)
        works = [
            work
            for work in works
            if work["vote_average"] is not None and float(work["vote_average"]) >= threshold
        ]
    if min_votes is not None:
        works = [work for work in works if int(work["vote_count"]) >= int(min_votes)]
    if query is not None:
        needle = query.casefold()
        works = [
            work
            for work in works
            if needle in str(work["title"]).casefold()
            or needle in str(work["original_title"]).casefold()
        ]
    if sort_by.startswith("vote_average"):
        works.sort(
            key=lambda work: float(work["vote_average"] or -1),
            reverse=True,
        )
    elif sort_by.startswith("primary_release") or sort_by.startswith("first_air"):
        works.sort(key=lambda work: str(work["release_date"]), reverse=True)

    total = len(works)
    # The fake upstream keeps the real provider shape: a query with no
    # matches reports zero total pages. Only the production adapter
    # normalizes that to its internal one-page empty window.
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    start = (page - 1) * PAGE_SIZE
    return {
        "page": page,
        "total_pages": total_pages,
        "total_results": total,
        "results": works[start : start + PAGE_SIZE],
    }


def _detail_payload(media_type: str, work_id: str) -> dict[str, object] | None:
    for work in WORKS[media_type]:
        if str(work["id"]) == work_id:
            genre_names = [
                next(
                    (str(genre["name"]) for genre in GENRES[media_type] if genre["id"] == genre_id),
                    "",
                )
                for genre_id in work["genre_ids"]
            ]
            return {
                **work,
                "genres": [{"name": name} for name in genre_names if name],
                "number_of_seasons": work["seasons"],
                "number_of_episodes": work["episodes"],
            }
    return None


def _record(route: str) -> None:
    with _lock:
        _stats["tmdb_requests"] += 1
        _stats["routes"][route] = _stats["routes"].get(route, 0) + 1


def _failure_response(request: httpx.Request) -> httpx.Response | None:
    with _lock:
        mode = _failure_mode
        if mode == "upstream_auth":
            return httpx.Response(
                401,
                json={
                    "status_code": 7,
                    "status_message": "Invalid API key: harness credential refused.",
                },
            )
        if mode == "search_500" and "/search/" in request.url.path:
            return httpx.Response(
                500,
                json={"status_code": 500, "status_message": "harness upstream fault"},
            )
        if mode == "genre_503" and "/genre/" in request.url.path:
            return httpx.Response(
                503,
                json={"status_code": 503, "status_message": "harness catalog fault"},
            )
        return None


def fake_tmdb_transport(request: httpx.Request) -> httpx.Response:
    """The only upstream this harness can reach: in-process, deterministic."""
    path = request.url.path
    if path.startswith("/"):
        path = path[1:]
    if path.startswith("3/"):
        path = path[2:]
    _record(path)
    failure = _failure_response(request)
    if failure is not None:
        return failure

    params: dict[str, list[str]] = {}
    for key, value in request.url.params.multi_items():
        params.setdefault(key, []).append(value)
    floors = params.get("vote_count.gte")
    if floors:
        # Evidence: the adapter really sent this floor on this discover route.
        with _lock:
            _stats["vote_floors"].append(f"{path}:{floors[0]}")
    if path.startswith(("discover/", "search/")):
        payload = _list_payload(path.split("/")[1], params)
        with _lock:
            _stats["list_pages"].append(
                {
                    "route": path,
                    "page": payload["page"],
                    "totalPages": payload["total_pages"],
                    "totalResults": payload["total_results"],
                }
            )
        return httpx.Response(200, json=payload)
    if path.startswith("genre/") and path.endswith("/list"):
        return httpx.Response(200, json={"genres": GENRES[path.split("/")[1]]})
    if path == "configuration/languages":
        return httpx.Response(200, json=LANGUAGES)
    detail = re.fullmatch(r"(movie|tv)/(\d+)", path)
    if detail is not None:
        payload = _detail_payload(detail.group(1), detail.group(2))
        if payload is None:
            return httpx.Response(404, json={"status_code": 34, "status_message": "not found"})
        return httpx.Response(200, json=payload)
    return httpx.Response(404, json={"status_code": 34, "status_message": "not found"})


class SpyStorage:
    """Any Storage invocation during the journey is recorded and refused."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name: str):
        def record_and_refuse(*args: object, **kwargs: object) -> object:
            self.calls.append(name)
            raise AssertionError(f"Explore journey must not touch Storage ({name})")

        return record_and_refuse


SPY_STORAGE = SpyStorage()


def build_api(database: Path) -> MediaFlowApi:
    repository = SQLiteTaskRepository(database)
    config = TMDBConfig(access_token="harness-tmdb-token")
    transport_client = httpx.Client(transport=httpx.MockTransport(fake_tmdb_transport))
    from mediaflow.infrastructure.tmdb import HttpxTransport

    client = TMDBClient(config, transport=HttpxTransport(config, client=transport_client))
    provider = TMDBProvider(client)

    def registry_factory(_provider_ids: object) -> MetadataProviderRegistry:
        return MetadataProviderRegistry((provider,))

    return MediaFlowApi(
        repository,
        None,
        principals=(PRINCIPAL,),
        metadata_provider_registry_factory=registry_factory,
        storage_adapters={"explore-spy": SPY_STORAGE},
    )


EFFECT_TABLE_PATTERN = re.compile(
    r"^(tasks|task_|files_|manual_|media_discovery|execution_|conflict_|file_locks|"
    r"metadata_|recognition_|classification_|automation_|notification_|storage_)",
)
SKIP_TABLE_PATTERN = re.compile(r"^(security_audit|operational_logs|schema_version)")


def effect_counts(database: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    with closing(sqlite3.connect(f"file:{database}?mode=ro", uri=True)) as connection:
        tables = [
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        ]
        for table in sorted(tables):
            if SKIP_TABLE_PATTERN.match(table):
                continue
            if not EFFECT_TABLE_PATTERN.match(table):
                continue
            counts[table] = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    return counts


STATE: dict[str, object] = {"api": None, "database": None}


def application(environ, start_response):  # noqa: ANN001, ANN201
    path = str(environ.get("PATH_INFO", ""))
    method = str(environ.get("REQUEST_METHOD", "GET")).upper()
    if path.startswith("/__harness__/"):
        global _failure_mode
        if path == "/__harness__/health" and method == "GET":
            document: dict[str, object] = {"status": "ok"}
        elif path == "/__harness__/stats" and method == "GET":
            with _lock:
                document = {
                    "failureMode": _failure_mode,
                    "tmdbRequests": _stats["tmdb_requests"],
                    "upstreamRoutes": dict(_stats["routes"]),
                    "voteFloors": list(_stats["vote_floors"]),
                    "upstreamListPages": list(_stats["list_pages"]),
                }
            database = STATE["database"]
            if isinstance(database, Path):
                document["effects"] = effect_counts(database)
            document["storageCalls"] = list(SPY_STORAGE.calls)
        elif path == "/__harness__/failure" and method == "POST":
            length = int(environ.get("CONTENT_LENGTH") or 0)
            payload = json.loads(environ["wsgi.input"].read(length) or b"{}")
            requested = str(payload.get("mode") or "none")
            if requested not in {"none", "upstream_auth", "search_500", "genre_503"}:
                document = {"error": "unknown failure mode"}
            else:
                with _lock:
                    _failure_mode = requested
                document = {"failureMode": requested}
        else:
            document = {"error": "harness route not found"}
        body = json.dumps(document).encode("utf-8")
        status = "404 Not Found" if "error" in document else "200 OK"
        start_response(
            status,
            [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
            ],
        )
        return [body]
    api = STATE["api"]
    return api(environ, start_response)  # type: ignore[misc]


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - wsgiref API
        return


class ThreadingWSGIServer(socketserver.ThreadingMixIn, WSGIServer):
    daemon_threads = True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4187)
    parser.add_argument("--database", type=Path, default=None)
    args = parser.parse_args(argv)

    if not (asset_root() / "index.html").is_file():
        print(
            "harness: built V2 artifact is missing; run `npm --prefix web run build` first",
            file=sys.stderr,
        )
        return 2

    database = args.database
    if database is None:
        import tempfile

        database = Path(tempfile.mkdtemp(prefix="mediaflow-explore-harness-")) / (
            "explore-harness.sqlite3"
        )
    database.parent.mkdir(parents=True, exist_ok=True)

    STATE["api"] = build_api(database)
    STATE["database"] = database

    with make_server(
        args.host,
        args.port,
        application,
        server_class=ThreadingWSGIServer,
        handler_class=QuietHandler,
    ) as server:
        print(
            f"explore harness: http://{args.host}:{args.port}/ui-v2/ (database {database})",
            flush=True,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
