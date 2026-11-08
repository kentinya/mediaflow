#!/usr/bin/env python3
"""Real-Python browser harness for the OpenList metadata-only Files journey.

This harness starts the built V2 artifact, the real ``MediaFlowApi``, temporary
SQLite repositories and one real ``OpenListStorage`` adapter over a bounded
loopback OpenList v4 server.  The provider's ``/api/fs/get`` endpoint always
returns HTTP 405, while directory listing, native move and native rename stay
available.  The browser journey proves that the ordinary files page can browse,
commit a bounded selection, review the exact summary, confirm it and let the
real Worker complete native moves without fetching any download link.

The fixture records every provider request so the browser proof can assert the
endpoint, the exact ``refresh: false`` directory requests and the absence of
content reads and unapproved mutations.  No production configuration, media,
credential or external service is involved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mediaflow.infrastructure.openlist_storage import (  # noqa: E402
    OpenListStorage,
    OpenListStorageConfig,
)
from mediaflow.interfaces.v2_ui import asset_root  # noqa: E402
from scripts import operations_inventory_harness as inventory  # noqa: E402

OPENLIST_TOKEN_ENV = "MEDIAFLOW_OPENLIST_HARNESS_TOKEN"
OPENLIST_TOKEN = "openlist-harness-throwaway-token"


def _json_response(start_response, status: str, document: dict[str, object]):
    body = json.dumps(document, ensure_ascii=False).encode("utf-8")
    start_response(
        status,
        [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
        ],
    )
    return [body]


class OpenListFixture:
    """A bounded OpenList v4 server with an auditable request ledger."""

    def __init__(self, entries: dict[str, tuple[bool, bytes]]) -> None:
        self.entries = dict(entries)
        self.calls: list[dict[str, object]] = []
        self._lock = threading.Lock()
        state = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args: object) -> None:
                return

            def _reply(self, status: int, document: dict[str, object] | None = None) -> None:
                body = b"" if document is None else json.dumps(document).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _business(self, code: int, message: str = "failure") -> None:
                self._reply(200, {"code": code, "message": message, "data": None})

            def _record(self, method: str, body: dict[str, object] | None = None) -> None:
                with state._lock:
                    state.calls.append(
                        {
                            "method": method,
                            "path": self.path.split("?", 1)[0],
                            "body": body,
                            "authorized": self.headers.get("Authorization") == OPENLIST_TOKEN,
                        }
                    )

            def do_GET(self) -> None:  # noqa: N802
                self._record("GET")
                if self.headers.get("Authorization") != OPENLIST_TOKEN:
                    self._reply(401)
                    return
                if self.path == "/ping":
                    self._reply(200)
                    return
                self._reply(405)

            def do_POST(self) -> None:  # noqa: N802
                raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                body = json.loads(raw or b"{}")
                self._record("POST", body)
                if self.headers.get("Authorization") != OPENLIST_TOKEN:
                    self._reply(401)
                    return
                with state._lock:
                    if self.path == "/api/fs/list":
                        self._list(body)
                    elif self.path == "/api/fs/move":
                        self._move(body)
                    elif self.path == "/api/fs/rename":
                        self._rename(body)
                    else:
                        self._reply(405)

            def _list(self, body: dict[str, object]) -> None:
                path = str(body.get("path", ""))
                page = body.get("page")
                per_page = body.get("per_page")
                if body.get("refresh") is not False:
                    self._business(400, "refresh must be false")
                    return
                if type(page) is not int or type(per_page) is not int or page < 1 or per_page < 1:
                    self._business(400, "invalid pagination")
                    return
                value = state.entries.get(path)
                if value is None:
                    self._business(404, "not found")
                    return
                if not value[0]:
                    self._business(400, "not a directory")
                    return
                prefix = path.rstrip("/") + "/"
                children = [
                    key
                    for key in sorted(state.entries)
                    if key.startswith(prefix) and "/" not in key[len(prefix) :]
                ]
                start = (page - 1) * per_page
                selected = children[start : start + per_page]
                self._reply(
                    200,
                    {
                        "code": 200,
                        "message": "success",
                        "data": {
                            "content": [state.document(key) for key in selected],
                            "total": len(children),
                        },
                    },
                )

            def _move(self, body: dict[str, object]) -> None:
                source_dir = str(body["src_dir"]).rstrip("/")
                target_dir = str(body["dst_dir"]).rstrip("/")
                overwrite = bool(body.get("overwrite"))
                names = body.get("names")
                if not isinstance(names, list):
                    self._business(400, "invalid names")
                    return
                for name in names:
                    source = f"{source_dir}/{name}"
                    target = f"{target_dir}/{name}"
                    if source not in state.entries:
                        self._business(404, "not found")
                        return
                    if target in state.entries and not overwrite:
                        self._business(409, "exists")
                        return
                for name in names:
                    state.relocate(f"{source_dir}/{name}", f"{target_dir}/{name}")
                self._reply(200, {"code": 200, "message": "success", "data": None})

            def _rename(self, body: dict[str, object]) -> None:
                source = str(body["path"])
                target = f"{source.rsplit('/', 1)[0]}/{body['name']}"
                overwrite = bool(body.get("overwrite"))
                if source not in state.entries:
                    self._business(404, "not found")
                    return
                if target in state.entries and not overwrite:
                    self._business(409, "exists")
                    return
                state.relocate(source, target)
                self._reply(200, {"code": 200, "message": "success", "data": None})

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}"

    def start(self) -> OpenListFixture:
        self._thread.start()
        return self

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def document(self, path: str) -> dict[str, object]:
        directory, payload = self.entries[path]
        return {
            "name": path.rsplit("/", 1)[-1],
            "size": 0 if directory else len(payload),
            "is_dir": directory,
            "modified": "2026-10-08T00:00:00Z",
        }

    def relocate(self, source: str, target: str) -> None:
        for key in tuple(self.entries):
            if key == source:
                self.entries[target] = self.entries.pop(key)
            elif key.startswith(source + "/"):
                self.entries[target + key[len(source) :]] = self.entries.pop(key)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "entries": [
                    {
                        "path": path,
                        "directory": directory,
                        "size": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }
                    for path, (directory, payload) in sorted(self.entries.items())
                ],
                "calls": list(self.calls),
            }


FIXTURE_ENTRIES: dict[str, tuple[bool, bytes]] = {
    "/Downloads": (True, b""),
    "/Downloads/Movies": (True, b""),
    "/Downloads/Movies/Movies": (True, b""),
    "/Downloads/Movies/Movies/Anime": (True, b""),
    "/Downloads/Movies/Movies/Anime/One (2001) [tmdbid-101]": (True, b""),
    "/Downloads/Movies/Movies/Anime/Two (2002) [tmdbid-102]": (True, b""),
    "/Downloads/One.2001.mkv": (False, b"openlist one metadata-only media"),
    "/Downloads/Two.2002.mkv": (False, b"openlist two metadata-only media"),
}

STATE: OpenListFixture | None = None


def application(environ, start_response):
    path = str(environ.get("PATH_INFO", ""))
    method = str(environ.get("REQUEST_METHOD", "GET")).upper()
    if path == "/__harness__/openlist-state" and method == "GET":
        fixture = STATE
        if fixture is None:
            return _json_response(start_response, "503 Service Unavailable", {"ready": False})
        return _json_response(start_response, "200 OK", fixture.snapshot())
    return inventory.application(environ, start_response)


def main(argv: list[str] | None = None) -> int:
    global STATE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4190)
    args = parser.parse_args(argv)
    if not (asset_root() / "index.html").is_file():
        print(
            "harness: built V2 artifact is missing; run `npm --prefix web run build` first",
            file=sys.stderr,
        )
        return 2

    fixture = OpenListFixture(FIXTURE_ENTRIES).start()
    STATE = fixture
    os.environ[OPENLIST_TOKEN_ENV] = OPENLIST_TOKEN
    database = Path(inventory.tempfile_dir()) / "openlist-metadata.sqlite3"
    database.parent.mkdir(parents=True, exist_ok=True)
    managed_root = database.parent / "managed"
    storage_adapter = OpenListStorage(
        OpenListStorageConfig(
            "source-storage",
            "OpenList source",
            fixture.base_url,
            OPENLIST_TOKEN,
            root_path="/Downloads",
            max_retries=0,
        )
    )
    storage_adapters = {"source-storage": storage_adapter}

    def mutate(document: dict[str, object]) -> None:
        document["storages"][0] = {
            "id": "source-storage",
            "name": "OpenList source",
            "type": "openlist",
            "rootPath": "/Downloads",
            "readOnly": False,
            "enabled": True,
            "options": {
                "baseUrl": fixture.base_url,
                "tokenEnv": OPENLIST_TOKEN_ENV,
                "maxRetries": 0,
                "pageSize": 100,
            },
        }
        document["resourceLibraries"][0]["storagePath"] = ""
        document["resourceLibraries"][0].pop("displayRootPath", None)
        for library in document["mediaLibraries"]:
            library["storageId"] = "source-storage"

    repository, managed, api = inventory.build_managed_fixture(
        database,
        managed_root,
        storage_adapters=storage_adapters,
        document_mutator=mutate,
    )
    inventory.STATE = inventory.AppState(
        database,
        repository=repository,
        api=api,
        managed=managed,
        storage_adapters=storage_adapters,
    )
    server = inventory.make_server(
        args.host,
        args.port,
        application,
        server_class=inventory.ThreadingWSGIServer,
        handler_class=inventory.QuietHandler,
    )
    print(f"OpenList metadata harness: http://{args.host}:{args.port}/ui-v2/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        storage_adapter.close()
        fixture.close()
        repository.close()
        managed.configuration_repository.close()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
