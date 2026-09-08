from __future__ import annotations

import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.infrastructure.sqlite_runtime import SQLiteTaskRepository
from mediaflow.interfaces.operator_ui import APP_JS, INDEX_HTML, STYLE_CSS
from mediaflow.interfaces.service_api import MediaFlowApi
from mediaflow.interfaces.v2_ui import load_v2_assets, reset_v2_ui_cache, v2_ui_asset

INDEX_BYTES = b"<!doctype html><html><body>V2 index</body></html>"
ASSET_JS = b"console.log('built v2 asset');\n"
ASSET_CSS = b".mf-shell{color:#edf5ef}\n"
FAVICON_SVG = b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"


class ExplodingRepository:
    def __getattr__(self, name):
        raise AssertionError(f"static UI must not access repository method {name}")


def request(api, path: str, method: str = "GET"):
    status = []
    headers = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": "0",
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(),
    }

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


def api_dashboard_status_without_token() -> int:
    """Status of the unauthenticated Dashboard request against a real
    repository, proving /api/v1 authentication stays intact beside V2."""

    with tempfile.TemporaryDirectory() as directory:
        with SQLiteTaskRepository(Path(directory, "runtime.sqlite3")) as repository:
            principal = ResolvedApiPrincipal(
                "viewer", "unused-token", frozenset({ApiPermission.READ})
            )
            api = MediaFlowApi(repository, None, principals=(principal,))
            status, _, _ = request(api, "/api/v1/dashboard")
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
        self.api = MediaFlowApi(ExplodingRepository(), None, principals=(principal,))

    def test_entry_document_and_client_routes_are_served_read_only(self) -> None:
        for path in ("/ui-v2", "/ui-v2/", "/ui-v2/dashboard", "/ui-v2/unknown-client-route"):
            status, headers, body = request(self.api, path)
            self.assertEqual(status, 200)
            self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
            self.assertEqual(body, INDEX_BYTES)

    def test_built_assets_are_served_with_deterministic_bytes(self) -> None:
        status, headers, body = request(self.api, "/ui-v2/assets/index-abc123.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/javascript; charset=utf-8")
        self.assertEqual(body, ASSET_JS)
        status, headers, body = request(self.api, "/ui-v2/assets/index-def456.css")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/css; charset=utf-8")
        self.assertEqual(body, ASSET_CSS)
        status, headers, body = request(self.api, "/ui-v2/favicon.svg")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "image/svg+xml")
        self.assertEqual(body, FAVICON_SVG)

    def test_v2_static_responses_carry_the_existing_safe_headers(self) -> None:
        _, headers, _ = request(self.api, "/ui-v2/")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(
            headers["Content-Security-Policy"],
            "default-src 'self'; connect-src 'self'; "
            "script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'none'",
        )
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(headers["Permissions-Policy"], "camera=(), microphone=(), geolocation=()")

    def test_v2_static_serving_is_get_only(self) -> None:
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            status, _, _ = request(self.api, "/ui-v2/", method=method)
            self.assertEqual(status, 405)

    def test_unknown_assets_traversal_and_non_builtin_types_fail_closed(self) -> None:
        (self.root / "notes.md").write_bytes(b"private note")
        (self.root / "secret.env").write_bytes(b"SECRET=value")
        for path in (
            "/ui-v2/assets/index-zzz999.js",
            "/ui-v2/nope.js",
            "/ui-v2/notes.md",
            "/ui-v2/secret.env",
            "/ui-v2/../../etc/passwd",
            "/ui-v2/..%2f..%2fetc%2fpasswd",
        ):
            status, _, _ = request(self.api, path)
            self.assertEqual(status, 404, path)

    def test_v2_prefix_never_bridges_into_api_or_static_siblings(self) -> None:
        status, headers, _ = request(self.api, "/ui-v2/api/v1/dashboard")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertEqual(api_dashboard_status_without_token(), 401)

    def test_v1_ui_routes_remain_available_and_unchanged(self) -> None:
        expected = {
            "/ui": ("text/html; charset=utf-8", INDEX_HTML),
            "/ui/": ("text/html; charset=utf-8", INDEX_HTML),
            "/ui/app.js": ("text/javascript; charset=utf-8", APP_JS),
            "/ui/style.css": ("text/css; charset=utf-8", STYLE_CSS),
        }
        for path, (content_type, body) in expected.items():
            status, headers, served = request(self.api, path)
            self.assertEqual(status, 200)
            self.assertEqual(headers["Content-Type"], content_type)
            self.assertEqual(served, body)
        status, _, _ = request(self.api, "/ui/app.js", method="POST")
        self.assertEqual(status, 405)

    def test_missing_artifact_fails_closed_with_safe_404(self) -> None:
        empty = Path(self._temporary.name) / "empty"
        empty.mkdir()
        with patch.dict(os.environ, {"MEDIAFLOW_UI_V2_ASSET_ROOT": str(empty)}):
            reset_v2_ui_cache()
            for path in ("/ui-v2", "/ui-v2/", "/ui-v2/dashboard"):
                status, _, _ = request(self.api, path)
                self.assertEqual(status, 404)
            status, _, _ = request(self.api, "/ui-v2/assets/index-abc123.js")
            self.assertEqual(status, 404)

    def test_asset_loader_binds_to_the_configured_root(self) -> None:
        assets = load_v2_assets(self.root)
        self.assertEqual(
            set(assets),
            {
                "/ui-v2",
                "/ui-v2/",
                "/ui-v2/index.html",
                "/ui-v2/assets/index-abc123.js",
                "/ui-v2/assets/index-def456.css",
                "/ui-v2/favicon.svg",
            },
        )
        self.assertEqual(
            assets["/ui-v2/assets/index-abc123.js"], ("text/javascript; charset=utf-8", ASSET_JS)
        )

    def test_v2_asset_resolution_rejects_traversal_and_unknown_files(self) -> None:
        self.assertIsNone(v2_ui_asset("/ui-v2/../../etc/passwd"))
        self.assertIsNone(v2_ui_asset("/ui-v2/missing.js"))
        self.assertIsNone(v2_ui_asset("/ui-v2/../ui/app.js"))
        status, _, _ = request(self.api, "/ui-v2/ui/app.js")
        self.assertEqual(status, 404)

    def test_v2_ui_never_touched_persistent_storage_or_api_state(self) -> None:
        # The repository explodes on any attribute access: a 200 static
        # response proves serving never reaches repositories or Storage, and
        # the unauthenticated API request proves /api/v1 auth is intact.
        status, _, _ = request(self.api, "/ui-v2/dashboard")
        self.assertEqual(status, 200)
        self.assertEqual(api_dashboard_status_without_token(), 401)


if __name__ == "__main__":
    unittest.main()
