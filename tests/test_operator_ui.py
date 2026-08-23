from __future__ import annotations

import io
import json
import unittest

from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.interfaces.operator_ui import APP_JS, INDEX_HTML, STYLE_CSS
from mediaflow.interfaces.service_api import MediaFlowApi


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


class OperatorUiTests(unittest.TestCase):
    def setUp(self) -> None:
        principal = ResolvedApiPrincipal("viewer", "unused-token", frozenset({ApiPermission.READ}))
        self.api = MediaFlowApi(ExplodingRepository(), None, principals=(principal,))

    def test_static_routes_are_public_read_only_and_hardened(self) -> None:
        expected = {
            "/ui": ("text/html; charset=utf-8", INDEX_HTML),
            "/ui/": ("text/html; charset=utf-8", INDEX_HTML),
            "/ui/app.js": ("text/javascript; charset=utf-8", APP_JS),
            "/ui/style.css": ("text/css; charset=utf-8", STYLE_CSS),
        }
        for path, (content_type, body) in expected.items():
            with self.subTest(path=path):
                status, headers, actual = request(self.api, path)
                self.assertEqual(status, 200)
                self.assertEqual(actual, body)
                self.assertEqual(headers["Content-Type"], content_type)
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        status, _, document = request(self.api, "/ui/app.js", "POST")
        self.assertEqual(status, 405)
        self.assertEqual(json.loads(document)["error"]["code"], "method_not_allowed")

    def test_assets_are_self_contained_and_credentials_are_memory_only(self) -> None:
        html = INDEX_HTML.decode()
        script = APP_JS.decode()
        combined = html + script + STYLE_CSS.decode()
        self.assertNotIn("http://", combined)
        self.assertNotIn("https://", combined)
        self.assertNotIn("local" + "Storage", script)
        self.assertNotIn("session" + "Storage", script)
        self.assertNotIn("document." + "cookie", script)
        self.assertNotIn("innerHTML", script)
        self.assertIn("textContent", script)
        self.assertIn('type="password"', html)
        self.assertIn("tokenInput.value = ''", script)
        self.assertIn("token = ''", script)
        self.assertIn("'Authorization': `Bearer ${token}`", script)

    def test_dashboard_and_review_requests_are_bounded(self) -> None:
        html = INDEX_HTML.decode()
        script = APP_JS.decode()
        self.assertIn('data-view="files"', html)
        self.assertIn("/api/v1/dashboard?recentLimit=10", script)
        self.assertIn("?status=pending&limit=100", script)
        self.assertIn("?limit=100", script)
        self.assertIn("/api/v1/files?", script)
        self.assertIn("limit=100", script)
        self.assertIn("showDetail('files'", script)
        self.assertIn("resourceLibrary", script)
        self.assertIn("recognitionType", script)
        self.assertIn("providerId", script)
        self.assertIn("scanStatus", script)
        self.assertIn("renderFileReMatchForm", script)
        self.assertIn("metadata-reviews", script)
        self.assertIn("classification-reviews", script)
        self.assertIn("encodeURIComponent(id)", script)

    def test_scheduler_and_notification_views_are_bounded_and_read_only(self) -> None:
        html = INDEX_HTML.decode()
        script = APP_JS.decode()
        self.assertIn('data-view="schedules"', html)
        self.assertIn('data-view="notifications"', html)
        self.assertIn("/api/v1/schedules", script)
        self.assertIn("/audit?limit=100", script)
        self.assertIn("/api/v1/notifications?limit=100&status=", script)
        self.assertIn("Refresh notifications", script)
        self.assertIn("showScheduleAudit(id, data.previous_cursor)", script)
        self.assertIn("showScheduleAudit(id, data.next_cursor)", script)
        self.assertIn("renderNotifications(status, data.previous_cursor)", script)
        self.assertIn("renderNotifications(status, data.next_cursor)", script)
        self.assertIn("renderNotifications(selector.value)", script)
        self.assertIn(
            "['all', 'pending', 'delivering', 'retry', 'delivered', 'dead-letter']", script
        )
        self.assertIn("failureCategory", script)
        self.assertNotIn("notification-worker", script)
        self.assertNotIn("notifications/requeue", script)
        self.assertNotIn("scheduler tick", script)
        self.assertNotIn("webhook" + "Url", script)
        self.assertNotIn("signature", script.lower())

    def test_ui_generates_only_existing_safe_decision_shapes(self) -> None:
        script = APP_JS.decode()
        self.assertIn("['skip', 'rename']", script)
        self.assertIn("{strategy}", script)
        self.assertIn("'candidateRank'", script)
        self.assertIn("'choiceRank'", script)
        self.assertNotIn("overwrite", script.lower())
        self.assertIn("Queue DryRun job", script)
        self.assertIn("'/api/v1/jobs', {method: 'POST'", script)
        self.assertNotIn("/api/v1/tasks/${encodeURIComponent(id)}/resume", script)
        self.assertNotIn("actor", script.lower())
        self.assertNotIn("mediaLibraryId", script)
        self.assertIn("Task was not resumed", script)


if __name__ == "__main__":
    unittest.main()
