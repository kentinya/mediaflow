#!/usr/bin/env python3
"""Isolated real-Python browser harness for the empty-instance account journey.

One real ``MediaFlowApi`` serves the built V2 artifact and a temporary SQLite
database. The harness exposes only test-only controls for host-issued one-time
codes and a same-version restart; every account/session mutation still goes
through ``AccountService`` and the ordinary HTTP auth endpoints.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import threading
import urllib.parse
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from wsgiref.simple_server import WSGIServer, make_server

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mediaflow.application.accounts import AccountService, hash_password  # noqa: E402
from mediaflow.domain.accounts import Account  # noqa: E402
from mediaflow.domain.security import ApiRole  # noqa: E402
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository  # noqa: E402
from mediaflow.interfaces.service_api import MediaFlowApi  # noqa: E402
from mediaflow.interfaces.v2_ui import asset_root  # noqa: E402


class _ThreadingWSGIServer(WSGIServer):
    daemon_threads = True


class AppState:
    def __init__(self, database: Path) -> None:
        self.database = database
        self.lock = threading.Lock()
        self.repository = SQLiteTaskRepository(database)
        self.accounts = AccountService(self.repository)
        self.bootstrap = {
            "version": 1,
            "persistence": {"databasePath": str(database)},
        }
        self.api = self._build_api()

    def _build_api(self) -> MediaFlowApi:
        return MediaFlowApi(
            self.repository,
            account_service=self.accounts,
            management_only=True,
            bootstrap_document=self.bootstrap,
        )

    def restart(self) -> None:
        with self.lock:
            self.repository.close()
            self.repository = SQLiteTaskRepository(self.database)
            self.accounts = AccountService(self.repository)
            self.api = self._build_api()


STATE: AppState | None = None


def _json_response(start_response, status: int, document: object):
    body = json.dumps(document, ensure_ascii=False).encode("utf-8")
    start_response(
        f"{status} {HTTPStatus(status).phrase}",
        [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
        ],
    )
    return [body]


def application(environ, start_response):
    assert STATE is not None
    path = str(environ.get("PATH_INFO", ""))
    method = str(environ.get("REQUEST_METHOD", "GET")).upper()
    query = urllib.parse.parse_qs(str(environ.get("QUERY_STRING", "")))

    if path == "/__harness__/health" and method == "GET":
        return _json_response(start_response, 200, {"status": "ok"})
    if path == "/__harness__/issue-setup-code" and method == "POST":
        try:
            code, expires_at = STATE.accounts.issue_first_admin_code()
        except Exception as error:
            return _json_response(
                start_response,
                409,
                {"error": {"code": getattr(error, "code", "conflict"), "message": str(error)}},
            )
        return _json_response(
            start_response,
            200,
            {"code": code, "expiresAt": expires_at.isoformat()},
        )
    if path == "/__harness__/issue-reset-code" and method == "POST":
        username = (query.get("username") or [""])[0]
        try:
            code, expires_at = STATE.accounts.issue_reset_code(username)
        except Exception as error:
            return _json_response(
                start_response,
                404,
                {"error": {"code": getattr(error, "code", "not_found"), "message": str(error)}},
            )
        return _json_response(
            start_response,
            200,
            {"code": code, "expiresAt": expires_at.isoformat()},
        )
    if path == "/__harness__/create-account" and method == "POST":
        # Test-only fixture control for the account-switch journey.  The
        # product's user-management surface is a later Slice outcome, so the
        # harness creates one ordinary read-only account directly through the
        # same durable repository used by AccountService.
        length = int(environ.get("CONTENT_LENGTH") or 0)
        raw = environ["wsgi.input"].read(length) if length > 0 else b"{}"
        try:
            body = json.loads(raw or b"{}")
            username = str(body.get("username", ""))
            password = str(body.get("password", ""))
            role = ApiRole(str(body.get("role", ApiRole.VIEWER.value)))
        except (ValueError, UnicodeDecodeError) as error:
            return _json_response(
                start_response, 422, {"error": {"code": "invalid_fixture", "message": str(error)}}
            )
        if STATE.repository.get_account_by_username(username) is not None:
            return _json_response(
                start_response, 409, {"error": {"code": "fixture_exists", "message": username}}
            )
        now = datetime.now(UTC)
        STATE.repository.create_account(
            Account(
                f"harness-{username}",
                username,
                (role,),
                True,
                now,
                now,
                now,
            ),
            hash_password(password),
        )
        return _json_response(start_response, 201, {"username": username, "role": role.value})
    if path == "/__harness__/account-state" and method == "GET":
        return _json_response(
            start_response,
            200,
            {
                "accountCount": STATE.repository.count_accounts(),
                "firstAdministratorRequired": STATE.accounts.setup_required(),
            },
        )
    if path == "/__harness__/restart" and method == "POST":
        STATE.restart()
        return _json_response(start_response, 200, {"restarted": True})

    return STATE.api(environ, start_response)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4195)
    parser.add_argument("--database")
    arguments = parser.parse_args()
    if not (asset_root() / "index.html").is_file():
        print(
            "the built V2 artifact is missing; run `npm --prefix web run build`",
            file=sys.stderr,
        )
        return 2
    database = (
        Path(arguments.database)
        if arguments.database
        else Path(tempfile.mkdtemp(prefix="mediaflow-account-harness-")) / "runtime.sqlite3"
    )
    database.parent.mkdir(parents=True, exist_ok=True)
    global STATE
    STATE = AppState(database)
    with make_server(
        arguments.host,
        arguments.port,
        application,
        server_class=_ThreadingWSGIServer,
    ) as server:
        print(
            f"web account harness: http://{arguments.host}:{arguments.port}/",
            flush=True,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
