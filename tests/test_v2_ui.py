from __future__ import annotations

import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote

from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.service_api import MediaFlowApi
from mediaflow.interfaces.v2_ui import load_v2_assets, reset_v2_ui_cache, v2_ui_asset

INDEX_BYTES = b"<!doctype html><html><body>V2 index</body></html>"
ASSET_JS = b"console.log('built v2 asset');\n"
ASSET_CSS = b".mf-shell{color:#edf5ef}\n"
FAVICON_SVG = b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"


class ExplodingRepository:
    def __getattr__(self, name):
        raise AssertionError(f"static UI must not access repository method {name}")


def request(api, path: str, method: str = "GET", token: str | None = "unused-token"):
    status = []
    headers = []
    query = ""
    if "?" in path:
        path, query = path.split("?", 1)
    environ = {
        "REQUEST_METHOD": method,
        # WSGI servers expose PATH_INFO after percent-decoding the request
        # path; model that here so encoded spaces/slashes exercise the same
        # boundary as production.
        "PATH_INFO": unquote(path),
        "QUERY_STRING": query,
        "CONTENT_LENGTH": "0",
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(),
    }
    if token is not None:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"

    def start_response(value, values):
        status.append(value)
        headers.extend(values)

    body = b"".join(api(environ, start_response))
    return int(status[0].split()[0]), dict(headers), body


def build_artifact(root: Path) -> None:
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_bytes(INDEX_BYTES)
    (root / "assets" / "index-abc123.js").write_bytes(ASSET_JS)
    (root / "assets" / "index-def456.css").write_bytes(ASSET_CSS)
    (root / "favicon.svg").write_bytes(FAVICON_SVG)


def api_status_without_token() -> int:
    """Status of an unauthenticated canonical API read against a real
    repository, proving /api authentication stays intact beside the Web root."""

    with tempfile.TemporaryDirectory() as directory:
        with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
            principal = ResolvedApiPrincipal(
                "viewer", "unused-token", frozenset({ApiPermission.READ})
            )
            api = MediaFlowApi(repository, principals=(principal,))
            status, _, _ = request(api, "/api/auth/principal", token=None)
            return status


class V2UiStaticTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name) / "dist"
        build_artifact(self.root)
        self._env = patch.dict(os.environ, {"MEDIAFLOW_UI_V2_ASSET_ROOT": str(self.root)})
        self._env.start()
        self.addCleanup(self._env.stop)
        self.addCleanup(reset_v2_ui_cache)
        reset_v2_ui_cache()
        principal = ResolvedApiPrincipal("viewer", "unused-token", frozenset({ApiPermission.READ}))
        self.api = MediaFlowApi(ExplodingRepository(), principals=(principal,))

    def test_entry_document_and_client_routes_are_served_read_only(self) -> None:
        for path in (
            "/",
            "/explore",
            "/resourcelib/files",
            "/medialib/files",
            "/operations",
            "/configuration",
            "/storage",
            "/rules",
            "/unknown-client-route",
        ):
            with self.subTest(path=path):
                status, headers, body = request(self.api, path)
                self.assertEqual(status, 200)
                self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
                self.assertEqual(body, INDEX_BYTES)

    def test_built_assets_are_served_with_deterministic_bytes(self) -> None:
        status, headers, body = request(self.api, "/assets/index-abc123.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/javascript; charset=utf-8")
        self.assertEqual(body, ASSET_JS)
        status, headers, body = request(self.api, "/assets/index-def456.css")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/css; charset=utf-8")
        self.assertEqual(body, ASSET_CSS)
        status, headers, body = request(self.api, "/favicon.svg")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "image/svg+xml")
        self.assertEqual(body, FAVICON_SVG)
        status, headers, body = request(self.api, "/index.html")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertEqual(body, INDEX_BYTES)

    def test_v2_static_responses_carry_the_existing_safe_headers(self) -> None:
        _, headers, _ = request(self.api, "/")
        self.assertEqual(headers["Cache-Control"], "no-store")
        # The current V2 artifact response carries the exact TMDB image source;
        # every other directive and header keeps the shared static hardening.
        self.assertEqual(
            headers["Content-Security-Policy"],
            "default-src 'self'; connect-src 'self'; "
            "script-src 'self'; style-src 'self'; img-src 'self' https://image.tmdb.org; "
            "object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'none'",
        )
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(headers["Permissions-Policy"], "camera=(), microphone=(), geolocation=()")

    def test_v2_static_serving_is_get_only(self) -> None:
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            status, _, _ = request(self.api, "/", method=method)
            self.assertEqual(status, 405)
            status, _, _ = request(self.api, "/resourcelib/files", method=method)
            self.assertEqual(status, 405)

    def test_unknown_assets_traversal_and_non_builtin_types_fail_closed(self) -> None:
        (self.root / "notes.md").write_bytes(b"private note")
        (self.root / "secret.env").write_bytes(b"SECRET=value")
        for path in (
            "/assets/index-zzz999.js",
            "/nope.js",
            "/notes.md",
            "/secret.env",
            "/../../etc/passwd",
            "/..%2f..%2fetc%2fpasswd",
        ):
            status, _, _ = request(self.api, path)
            self.assertEqual(status, 404, path)

    def test_retired_web_prefix_is_an_ordinary_unknown_client_route(self) -> None:
        """The retired Web prefix keeps no redirect, notice or second product.

        Its extensionless addresses are ordinary unknown client routes: the
        SPA entry document is served and the browser renders the same generic
        not-found view as any other unknown route. Its static asset addresses
        are unknown files and stay 404.
        """

        for path in (
            "/ui-v2",
            "/ui-v2/",
            "/ui-v2/explore",
            "/ui-v2/resourcelib/files?resourceLibraryId=source&path=Movies",
            "/ui-v2/rules/edit/recognitionTypes/A",
        ):
            with self.subTest(path=path):
                status, headers, body = request(self.api, path)
                self.assertEqual(status, 200)
                self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
                self.assertEqual(body, INDEX_BYTES)
        for path in (
            "/ui-v2/assets/index-abc123.js",
            "/ui-v2/app.js",
            "/ui/app.js",
            "/ui/style.css",
            "/ui/../ui/app.js",
        ):
            with self.subTest(path=path):
                status, _, body = request(self.api, path)
                self.assertEqual(status, 404)
                self.assertNotIn(b"MediaFlow", body)
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            status, _, _ = request(self.api, "/ui-v2/resourcelib/files", method=method)
            self.assertEqual(status, 405)

    def test_retired_ui_routes_are_ordinary_unknown_routes(self) -> None:
        # The V1 static product is gone: every retired path is the same ordinary
        # unknown route as any other unknown sibling, including a query, an
        # encoded spelling and a non-GET method. The boundary never reaches the
        # repository or publishes a redirect, notice page or alternate product.
        for path in ("/ui", "/ui/", "/ui?tab=settings"):
            with self.subTest(path=path):
                status, headers, body = request(self.api, path)
                self.assertEqual(status, 200)
                self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
                self.assertEqual(body, INDEX_BYTES)
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            status, _, _ = request(self.api, "/ui", method=method)
            self.assertEqual(status, 405)

    def test_api_namespace_is_never_served_by_the_static_boundary(self) -> None:
        """The API branch is decided by path before any artifact lookup.

        An unauthenticated canonical API read never returns the entry document,
        a retired versioned prefix is an unknown JSON route that never reaches
        authentication, storage or a business service, and no Web address can
        reach the API branch.
        """

        principal = ResolvedApiPrincipal("viewer", "unused-token", frozenset({ApiPermission.READ}))
        with SQLiteTaskRepository(Path(self._temporary.name, "api.sqlite3")) as repository:
            api = MediaFlowApi(repository, principals=(principal,))
            status, headers, _ = request(api, "/api/auth/principal", token=None)
        self.assertEqual(status, 401)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        for path in (
            "/api/v1/auth/principal",
            "/api/v1/tasks",
            "/api/v1/tasks/task-1/cancel",
            "/api/v2/tasks",
            "/api/v2/some/unknown/route",
        ):
            with self.subTest(path=path):
                status, headers, _ = request(self.api, path)
                self.assertEqual(status, 404)
                self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        for method in ("GET", "POST", "PUT", "DELETE"):
            status, headers, _ = request(self.api, "/api/v1/storages", method=method)
            self.assertEqual(status, 404, method)
            self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")

    def test_health_is_its_own_liveness_branch(self) -> None:
        status, headers, body = request(self.api, "/health", token=None)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertIn(b'"processAlive"', body)
        for method in ("POST", "PUT", "DELETE"):
            status, headers, _ = request(self.api, "/health", method=method)
            self.assertEqual(status, 405, method)
            self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")

    def test_missing_artifact_fails_closed_with_safe_404(self) -> None:
        empty = Path(self._temporary.name) / "empty"
        empty.mkdir()
        with patch.dict(os.environ, {"MEDIAFLOW_UI_V2_ASSET_ROOT": str(empty)}):
            reset_v2_ui_cache()
            for path in (
                "/",
                "/explore",
                "/rules/edit/recognitionTypes/proof.js",
                "/assets/index-abc123.js",
            ):
                status, _, _ = request(self.api, path)
                self.assertEqual(status, 404, path)

    def test_asset_loader_binds_to_the_configured_root(self) -> None:
        assets = load_v2_assets(self.root)
        self.assertEqual(
            set(assets),
            {
                "/",
                "/index.html",
                "/assets/index-abc123.js",
                "/assets/index-def456.css",
                "/favicon.svg",
            },
        )
        self.assertEqual(
            assets["/assets/index-abc123.js"], ("text/javascript; charset=utf-8", ASSET_JS)
        )

    def test_v2_asset_resolution_rejects_traversal_and_unknown_files(self) -> None:
        self.assertIsNone(v2_ui_asset("/../../etc/passwd"))
        self.assertIsNone(v2_ui_asset("/missing.js"))
        self.assertIsNone(v2_ui_asset("/../ui/app.js"))
        status, _, _ = request(self.api, "/ui/app.js")
        self.assertEqual(status, 404)
        status, _, _ = request(self.api, "/api/v1/auth/principal")
        self.assertEqual(status, 404)

    def test_rules_edit_routes_with_legal_dotted_ids_receive_the_entry_document(self) -> None:
        """The backend rules identity contract accepts bounded IDs containing
        dots — including file-like shapes such as ``proof.js``, ``proof.env``
        or ``proof.type.bak`` that the backend legally publishes — so a refresh
        of any such edit route must serve the SPA entry document instead of
        being misread as an unknown asset file."""

        for path in (
            "/rules/edit/recognitionTypes/proof.type",
            "/rules/edit/namingPolicies/season.01",
            "/rules/edit/recognitionTypes/proof.js",
            "/rules/edit/recognitionTypes/proof.env",
            "/rules/edit/recognitionTypes/proof.type.bak",
            "/rules/edit/recognitionTypes/proof+type",
            "/rules/edit/recognitionTypes/proof%40type",
            "/rules/edit/recognitionTypes/proof%20type",
            f"/rules/edit/recognitionTypes/{'a' * 64}",
        ):
            status, headers, body = request(self.api, path)
            self.assertEqual(status, 200, path)
            self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8", path)
            self.assertEqual(body, INDEX_BYTES, path)

    def test_rules_edit_route_allowlist_stays_narrow(self) -> None:
        """Only the supported rules edit shape falls back to the entry doc;
        unknown families, non-rules dotted assets and traversal keep failing
        closed. The identity segment is never second-guessed by its suffix."""

        for path in (
            "/rules/edit/notAFamily/proof.type",
            "/rules/edit/notAFamily/ordinary-id",
            "/rules/other/recognitionTypes/proof.type",
            "/rules/edit/recognitionTypes/proof!.js",
            "/rules/edit/recognitionTypes/-invalid.js",
            "/rules/edit/recognitionTypes/bad%ZZ.js",
            "/rules/edit/recognitionTypes/proof%2Ftype.js",
            "/rules/edit/recognitionTypes/proof%5Ctype.js",
            f"/rules/edit/recognitionTypes/{'a' * 65}",
            "/../../etc/passwd",
            "/notes.md",
            "/rules/edit/notAFamily/proof.type.bak",
        ):
            status, _, _ = request(self.api, path)
            self.assertEqual(status, 404, path)
        # A missing family segment is generic SPA fallthrough (existing
        # behavior), never an identity-bearing route; a deeper dotted final
        # segment is refused rather than served as an asset or the entry
        # document; and a deeper extensionless route stays generic fallthrough.
        status, _, body = request(self.api, "/rules/edit/recognitionTypes")
        self.assertEqual(status, 200)
        self.assertEqual(body, INDEX_BYTES)
        status, _, _ = request(self.api, "/rules/edit/recognitionTypes/proof.type/extra.js")
        self.assertEqual(status, 404)
        status, _, body = request(self.api, "/rules/edit/recognitionTypes/proof.type/extra")
        self.assertEqual(status, 200)
        self.assertEqual(body, INDEX_BYTES)
        (self.root / "notes.md").write_bytes(b"private note")
        status, _, _ = request(self.api, "/notes.md")
        self.assertEqual(status, 404)

    def test_v2_ui_never_touched_persistent_storage_or_api_state(self) -> None:
        # The repository explodes on any attribute access: a 200 static
        # response proves serving never reaches repositories or Storage, and
        # the unauthenticated API request proves /api auth is intact.
        status, _, _ = request(self.api, "/operations")
        self.assertEqual(status, 200)
        status, _, _ = request(self.api, "/ui-v2/operations")
        self.assertEqual(status, 200)
        self.assertEqual(api_status_without_token(), 401)


if __name__ == "__main__":
    unittest.main()
