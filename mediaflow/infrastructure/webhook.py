from __future__ import annotations

import urllib.error
import urllib.request

from mediaflow.application.notification import WebhookTransportError
from mediaflow.domain.notification import WebhookRequest


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class UrllibWebhookTransport:
    """HTTPS webhook adapter that deliberately refuses redirects."""

    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(_NoRedirect)

    def send(self, request: WebhookRequest) -> int:
        value = urllib.request.Request(
            request.url,
            data=request.body,
            headers=request.headers,
            method="POST",
        )
        try:
            with self._opener.open(value, timeout=request.timeout_seconds) as response:
                return int(response.status)
        except urllib.error.HTTPError as error:
            return int(error.code)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise WebhookTransportError("webhook transport failed") from error
