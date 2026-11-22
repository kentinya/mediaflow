"""Advance one resident service through its real assembly for focused tests.

The production entry is a long-lived loop.  Tests that need exactly one step
patch the loop boundary and call the same service composition the entry uses,
so their assertions keep exercising the real Worker/Scheduler/Notification
handlers instead of a second implementation.
"""

from __future__ import annotations

import json
import os
from contextlib import ExitStack
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from mediaflow.application.resident_runtime import ResidentLoop
from mediaflow.infrastructure.runtime_configuration import load_management_bootstrap
from mediaflow.resident_entry import (
    _run_notification_worker,
    _run_scheduler,
    _run_worker,
)

_RUNNERS = {
    "worker": _run_worker,
    "scheduler": _run_scheduler,
    "notification-worker": _run_notification_worker,
}


def run_resident_step(
    service: str,
    config_path: str | Path,
    *,
    stdout: StringIO | None = None,
) -> tuple[int, str]:
    """Run one real resident step and return its status and captured output."""

    output = stdout or StringIO()
    configuration = load_management_bootstrap(
        json.loads(Path(config_path).read_text(encoding="utf-8"))
    )

    def run_one_step(loop, _stop, _sleep):
        try:
            return loop._step(loop)
        except Exception as error:  # match the real loop's bounded fault boundary
            reason, detail = loop._reason_for(error)
            loop.note(reason, detail)
            return 0

    with ExitStack() as stack:
        stack.enter_context(patch.object(ResidentLoop, "run", run_one_step))
        if service == "worker":
            # A real resident process keeps its registration alive after a
            # step; a one-step test must not look like a graceful shutdown.
            stack.enter_context(
                patch(
                    "mediaflow.application.automation.ResidentProcessingWorker.stop",
                    return_value=None,
                )
            )
        code = _RUNNERS[service](configuration, str(config_path), stdout=output)
    return code, output.getvalue()


def run_api_entry(
    config_path: str | Path,
    *,
    stdout: StringIO | None = None,
    stderr: StringIO | None = None,
    skip_preflight: bool = True,
) -> int:
    """Run the fixed API entry once, optionally skipping deployment preflight."""

    from mediaflow.resident_entry import main as service_main

    output = stdout or StringIO()
    errors = stderr or StringIO()
    environment = {
        "MEDIAFLOW_CONFIG": str(config_path),
        "MEDIAFLOW_DATA_DIR": str(Path(config_path).parent),
    }
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, environment, clear=False))
        if skip_preflight:
            stack.enter_context(
                patch("mediaflow.resident_entry.container_preflight_errors", return_value=[])
            )
        return service_main(["api"], stdout=output, stderr=errors)


def serve_once(factory):
    """Adapt an old ``make_server`` fixture to the production Waitress seam."""

    def serve(app, *, host, port, threads):
        with factory(host, port, app) as server:
            server.serve_forever()

    return serve
