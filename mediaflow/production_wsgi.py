"""Production WSGI serving adapter.

MediaFlow's operator Web/API is a WSGI application.  The development listener
uses the Python standard library for trusted-loopback work; production Compose
uses this adapter and the declared Waitress dependency instead.
"""

from __future__ import annotations


def serve(
    app,
    *,
    host: str,
    port: int,
    threads: int = 4,
) -> None:
    """Serve ``app`` with Waitress until the process is stopped."""

    if isinstance(threads, bool) or not isinstance(threads, int) or threads < 1:
        raise ValueError("production WSGI threads must be a positive integer")
    if not 1 <= port <= 65535:
        raise ValueError("production WSGI port must be between 1 and 65535")
    from waitress import serve as waitress_serve

    # Waitress removes X-Forwarded-* headers by default. The WSGI application
    # itself decides whether a forwarded HTTPS scheme may mark the session
    # cookie Secure, so the deployment's trusted reverse proxy must be able to
    # pass that header through. Authentication still requires the account
    # session; a forwarded header alone grants no identity or authority.
    waitress_serve(
        app,
        host=host,
        port=port,
        threads=threads,
        ident="MediaFlow",
        channel_timeout=120,
        clear_untrusted_proxy_headers=False,
    )
